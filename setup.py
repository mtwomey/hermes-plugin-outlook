#!/usr/bin/env python3
"""
setup.py for hermes-plugin-outlook.

Usage:
    python setup.py install       # install plugin into Hermes
    python setup.py uninstall     # remove plugin from Hermes
    python setup.py status        # show installation status
    python setup.py credentials   # manage credentials
    python setup.py log           # manage log level
    python setup.py audit         # check compliance
    python setup.py test          # run smoke tests
"""
import json
import subprocess
from pathlib import Path

from hermes_plugin_core.setup_cli import SetupCLI, PluginConfig
from hermes_plugin_core.keychain import cred_get, cred_set

config = PluginConfig(
    plugin_key="outlook",
    service="hermes-outlook",
    repo_dir=Path(__file__).parent.resolve(),
    keys=["email", "tenant_id", "client_id", "refresh_token"],
    cred_prompts={
        "email":         ("Your Outlook email address (e.g. mattwo01@roberthalf.com)", "mattwo01@roberthalf.com", False),
        "tenant_id":     ("Azure AD Tenant ID (extract from browser — see README)", "", False),
        "client_id":     ("OAuth2 Client ID (extract from browser — see README)", "", False),
        "refresh_token": ("Outlook refresh token (extract from browser MSAL cache — see README)", "", True),
    },
    requirements=[],
    has_skill_stub=True,
    skill_stub_category="email",
)


# ---------------------------------------------------------------------------
# Clipboard helpers
# ---------------------------------------------------------------------------

def _pbpaste() -> str:
    """Read current clipboard contents via pbpaste. Returns empty string on failure."""
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return ""


def _read_clipboard_json() -> dict | None:
    """Try to read a credentials JSON blob from the clipboard.

    Returns a dict with any of {email, tenant_id, client_id, refresh_token}
    that were present, or None if the clipboard doesn't look like our blob.
    """
    raw = _pbpaste()
    if not raw:
        return None
    try:
        blob = json.loads(raw)
    except ValueError:
        return None
    # Must contain at least one of our expected keys to count as our blob
    if not any(k in blob for k in ("tenant_id", "client_id", "refresh_token", "email")):
        return None
    return blob


# ---------------------------------------------------------------------------
# OutlookSetupCLI — clipboard-first credential flow
# ---------------------------------------------------------------------------

class OutlookSetupCLI(SetupCLI):
    """Extends SetupCLI with an Outlook-specific clipboard-first credential flow.

    When the browser console snippet has been run and the JSON blob is on the
    clipboard, credentials are read automatically — no manual copy/paste needed.
    Falls back to per-key prompts if no blob is detected.
    """

    def _prompt_credentials(self, yes: bool = False) -> None:
        cfg = self.config
        keys = cfg.keys

        existing_creds = {k: cred_get(cfg.service, k) for k in keys}
        all_stored = all(existing_creds.values())

        if all_stored and yes:
            return

        if all_stored and not yes:
            ans = input("\n  Credentials already stored. Re-enter? [y/N]: ").strip().lower()
            if ans != "y":
                print("  ✓ Using existing credentials.")
                return

        print(f"\n{cfg.plugin_key} credential setup")
        print("=" * 50)
        print("  See README.md for the browser console snippet that copies")
        print("  all four values as a JSON blob to your clipboard in one shot.\n")

        # --- Primary path: clipboard JSON blob ---
        blob = _read_clipboard_json()
        if blob:
            rt = blob.get("refresh_token", "")
            print("  ✓ Found credentials JSON blob in clipboard:")
            print(f"       tenant_id:     {blob.get('tenant_id', '(missing)')}")
            print(f"       client_id:     {blob.get('client_id', '(missing)')}")
            print(f"       email:         {blob.get('email', '(missing)')}")
            if rt:
                print(f"       refresh_token: {rt[:20]}... ({len(rt)} chars)")
            else:
                print("       refresh_token: (missing)")
            print()
            ans = input("  Store all credentials from clipboard? [Y/n]: ").strip().lower()
            if ans in ("", "y"):
                missing = []
                for key in keys:
                    value = blob.get(key, "").strip()
                    if value:
                        cred_set(cfg.service, key, value)
                        display = (
                            f"{value[:20]}... ({len(value)} chars)"
                            if len(value) > 40
                            else value
                        )
                        print(f"  ✓ {key}: stored from clipboard ({display})")
                    else:
                        missing.append(key)
                if missing:
                    print(f"\n  ⚠  Not in blob: {', '.join(missing)} — enter manually:\n")
                    for key in missing:
                        self._prompt_single_key(key, existing_creds.get(key))
                return
            # User declined clipboard blob — fall through to per-key prompts

        # --- Fallback: prompt each key individually ---
        if not blob:
            print("  ⚠  No credentials JSON blob found in clipboard.")
            print("       Run the browser console snippet (see README.md),")
            print("       then re-run. Or enter values manually:\n")
        else:
            print()  # User declined the blob offer

        for key in keys:
            self._prompt_single_key(key, existing_creds.get(key))

    def _prompt_single_key(self, key: str, existing: str | None) -> None:
        """Prompt for a single credential key, with special handling for refresh_token."""
        cfg = self.config
        label, default, is_secret = cfg.cred_prompts[key]
        fallback = existing or default

        if key == "refresh_token":
            print(f"\n  {label}:")
            print("    The token is too long to type or paste in the terminal (macOS TTY limit).")
            print("    Copy it to your clipboard (or run the browser console snippet),")
            print("    then press Enter.")
            ans = input("    Press Enter when clipboard is ready (or type 'skip'): ").strip().lower()
            if ans == "skip":
                if existing:
                    print(f"  ✓ Kept existing: {key}")
                else:
                    print(f"  ⚠  Skipped (no value): {key}")
                return
            value = _pbpaste()
            if not value:
                print("  ⚠  Clipboard is empty — skipping refresh_token")
                return
            if len(value) < 100:
                print(f"  ⚠  Clipboard content looks too short ({len(value)} chars).")
                ans2 = input("    Store it anyway? [y/N]: ").strip().lower()
                if ans2 != "y":
                    if existing:
                        print(f"  ✓ Kept existing: {key}")
                    return
            cred_set(cfg.service, key, value)
            print(f"  ✓ Got token from clipboard ({len(value)} chars) — stored")
            return

        hint = f" [{fallback[:6]}{'...' if len(fallback) > 6 else ''}]" if fallback else ""
        prompt_text = f"  {label}{hint}: "
        if is_secret:
            import getpass
            value = getpass.getpass(prompt_text).strip()
        else:
            value = input(prompt_text).strip()

        value = value or fallback
        if value:
            cred_set(cfg.service, key, value)
            print(f"  ✓ {key} stored")
        else:
            print(f"  ⚠  {key} skipped (empty)")


if __name__ == "__main__":
    OutlookSetupCLI(config).run()
