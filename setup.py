"""
setup.py for hermes-plugin-outlook.

Usage:
    ./setup.sh install [--yes]   # Install (symlink, enable, store creds)
    ./setup.sh remove  [--yes]   # Uninstall (remove symlink, disable plugin)
    ./setup.sh status            # Show current install/credential state
    ./setup.sh creds   [--yes]   # Re-enter or update stored credentials
    ./setup.sh log debug         # Enable DEBUG logging (requires Hermes restart)
    ./setup.sh log quiet         # Disable debug logging (back to WARNING)
    ./setup.sh log status        # Show current log level setting

Credentials are stored in macOS Keychain under service "hermes-outlook".
The refresh token is obtained by extracting it from the browser's MSAL cache
(see README.md for instructions).
"""

import argparse
import os
import sys
from pathlib import Path

from ruamel.yaml import YAML
import keyring


# ── Constants ─────────────────────────────────────────────────────────────────

PLUGIN_NAME      = "outlook"
KEYCHAIN_SERVICE = "hermes-outlook"

HERMES_HOME  = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
PLUGINS_DIR  = HERMES_HOME / "plugins"
CONFIG_FILE  = HERMES_HOME / "config.yaml"

REPO_DIR    = Path(__file__).resolve().parent
PLUGIN_LINK = PLUGINS_DIR / PLUGIN_NAME

# Credentials stored in Keychain
KEYS = ["email", "tenant_id", "client_id", "refresh_token"]

CRED_PROMPTS = {
    "email": {
        "label":     "Your Outlook email address (e.g. mattwo01@roberthalf.com)",
        "default":   "mattwo01@roberthalf.com",
        "is_secret": False,
    },
    "tenant_id": {
        "label":     "Azure AD Tenant ID (extract from browser — see README)",
        "default":   "",
        "is_secret": False,
    },
    "client_id": {
        "label":     "OAuth2 Client ID (extract from browser — see README)",
        "default":   "",
        "is_secret": False,
    },
    "refresh_token": {
        "label":     "Outlook refresh token (extract from browser MSAL cache — see README)",
        "default":   "",
        "is_secret": True,
    },
}

_KEYCHAIN_CACHE: dict = {}


# ── Keychain helpers ──────────────────────────────────────────────────────────

def _keychain_store(key: str, value: str) -> None:
    keyring.set_password(KEYCHAIN_SERVICE, key, value)
    _KEYCHAIN_CACHE[key] = value


def _keychain_read(key: str):
    if key in _KEYCHAIN_CACHE:
        return _KEYCHAIN_CACHE[key]
    val = keyring.get_password(KEYCHAIN_SERVICE, key)
    _KEYCHAIN_CACHE[key] = val
    return val


def _keychain_delete(key: str) -> None:
    try:
        keyring.delete_password(KEYCHAIN_SERVICE, key)
    except Exception:
        pass
    _KEYCHAIN_CACHE.pop(key, None)


def _prompt_cred(key: str, existing=None) -> str:
    info    = CRED_PROMPTS.get(key, {"label": key, "default": "", "is_secret": False})
    label   = info["label"]
    default = existing or info.get("default", "")
    hint    = f" [{default[:6]}{'...' if len(default) > 6 else ''}]" if default else ""
    if info.get("is_secret"):
        import getpass
        value = getpass.getpass(f"  {label}{hint}: ").strip()
    else:
        value = input(f"  {label}{hint}: ").strip()
    return value or default


def cred_status() -> dict:
    return {k: (_keychain_read(k) is not None) for k in KEYS}


# ── Config helpers ────────────────────────────────────────────────────────────

def _read_config():
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(CONFIG_FILE) as f:
        return yaml.load(f), yaml


def _write_config(data, yaml) -> None:
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(data, f)


def _is_enabled() -> bool:
    if not CONFIG_FILE.exists():
        return False
    data, _ = _read_config()
    plugins = data.get("plugins", {})
    return PLUGIN_NAME in (plugins.get("enabled") or [])


def _enable_plugin() -> None:
    data, yaml = _read_config()
    if "plugins" not in data:
        data["plugins"] = {}
    if "enabled" not in data["plugins"] or data["plugins"]["enabled"] is None:
        data["plugins"]["enabled"] = []
    if PLUGIN_NAME not in data["plugins"]["enabled"]:
        data["plugins"]["enabled"].append(PLUGIN_NAME)
        _write_config(data, yaml)
        print(f"  ✓ Added '{PLUGIN_NAME}' to plugins.enabled in config.yaml")
    else:
        print(f"  ✓ '{PLUGIN_NAME}' already in plugins.enabled")


def _disable_plugin() -> None:
    data, yaml = _read_config()
    plugins = data.get("plugins", {})
    enabled = plugins.get("enabled") or []
    if PLUGIN_NAME in enabled:
        enabled.remove(PLUGIN_NAME)
        data["plugins"]["enabled"] = enabled
        _write_config(data, yaml)
        print(f"  ✓ Removed '{PLUGIN_NAME}' from plugins.enabled")
    else:
        print(f"  ✓ '{PLUGIN_NAME}' was not in plugins.enabled")


# ── Commands ──────────────────────────────────────────────────────────────────

def _finish_install():
    print(f"\n  ✅ {PLUGIN_NAME} plugin installed.")
    print("  ➡  Restart Hermes to activate tools.\n")


def cmd_status():
    print(f"\n{'─'*55}")
    print(f" Status: {PLUGIN_NAME} plugin")
    print(f"{'─'*55}")

    link_ok    = PLUGIN_LINK.is_symlink() and PLUGIN_LINK.resolve() == REPO_DIR
    enabled_ok = _is_enabled()

    print(f"  Plugin symlink : {'✓' if link_ok else '✗'} {PLUGIN_LINK}")
    print(f"  Enabled        : {'✓' if enabled_ok else '✗'} (plugins.enabled in config.yaml)")

    creds = cred_status()
    for key, stored in creds.items():
        print(f"  Cred [{key:16s}]: {'✓' if stored else '✗ NOT STORED'}")

    print()
    if link_ok and enabled_ok and all(creds.values()):
        print("  ✅ Ready — restart Hermes to activate the plugin.")
    else:
        print("  ❌ Run: ./setup.sh install")
    print()

    # Smoke test: try a token refresh if all creds are present
    if link_ok and enabled_ok and all(creds.values()):
        print("  Running connectivity check...")
        _smoke_test()


def _smoke_test():
    """Attempt a token refresh to verify credentials are valid."""
    import json
    import urllib.request
    import urllib.parse
    import urllib.error

    creds = {k: _keychain_read(k) for k in KEYS}
    params = urllib.parse.urlencode({
        "client_id":     creds["client_id"],
        "grant_type":    "refresh_token",
        "refresh_token": creds["refresh_token"],
        "scope":         "https://outlook.office.com/.default offline_access",
    }).encode()

    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{creds['tenant_id']}/oauth2/v2.0/token",
        data=params, method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin":       "https://outlook.office.com",
            "User-Agent":   "Mozilla/5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if "access_token" in data:
            print("  ✅ Token refresh successful — plugin is functional.")
        else:
            err = data.get("error", "unknown")
            print(f"  ⚠️  Token response OK but no access_token: {err}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body)
            print(f"  ✗ Token refresh failed: HTTP {e.code} — {err.get('error', '')} — {err.get('error_description', '')[:100]}")
        except Exception:
            print(f"  ✗ Token refresh failed: HTTP {e.code} — {body[:150]}")
    except Exception as e:
        print(f"  ✗ Connectivity check failed: {e}")


def cmd_install(yes: bool = False):
    print(f"\nInstalling {PLUGIN_NAME} plugin...")

    # 1. Symlink
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    if PLUGIN_LINK.is_symlink():
        if PLUGIN_LINK.resolve() == REPO_DIR:
            print(f"  ✓ Symlink already correct: {PLUGIN_LINK}")
        else:
            PLUGIN_LINK.unlink()
            PLUGIN_LINK.symlink_to(REPO_DIR)
            print(f"  ✓ Symlink updated: {PLUGIN_LINK} → {REPO_DIR}")
    elif PLUGIN_LINK.exists():
        print(f"  ⚠️  {PLUGIN_LINK} exists but is not a symlink. Remove it manually.")
        sys.exit(1)
    else:
        PLUGIN_LINK.symlink_to(REPO_DIR)
        print(f"  ✓ Symlink created: {PLUGIN_LINK} → {REPO_DIR}")

    # 2. Enable in config.yaml
    _enable_plugin()

    # 3. Credentials
    existing_creds = cred_status()
    all_stored     = all(existing_creds.values())

    if all_stored and yes:
        print("  ✓ All credentials already stored. Skipping re-entry (--yes).")
        _finish_install()
        return

    if all_stored and not yes:
        ans = input("\n  Credentials already stored. Re-enter? [y/N]: ").strip().lower()
        if ans != "y":
            print("  ✓ Using existing credentials.")
            _finish_install()
            return

    print("\n  Enter credentials (leave blank to keep existing value):\n")
    for key in KEYS:
        existing = _keychain_read(key)
        value    = _prompt_cred(key, existing)
        if value:
            _keychain_store(key, value)
            print(f"  ✓ Stored: {key}")
        elif existing:
            print(f"  ✓ Kept existing: {key}")
        else:
            print(f"  ⚠️  Skipped (no value): {key}")

    _finish_install()


def cmd_remove(yes: bool = False):
    print(f"\nRemoving {PLUGIN_NAME} plugin...")
    if not yes:
        ans = input("  This will remove the symlink and disable the plugin. Continue? [y/N]: ").strip().lower()
        if ans != "y":
            print("  Aborted.")
            return

    if PLUGIN_LINK.is_symlink():
        PLUGIN_LINK.unlink()
        print(f"  ✓ Removed symlink: {PLUGIN_LINK}")
    else:
        print(f"  ✓ No symlink found at {PLUGIN_LINK}")

    _disable_plugin()

    if not yes:
        ans = input("\n  Also delete stored credentials from Keychain? [y/N]: ").strip().lower()
        if ans == "y":
            for key in KEYS:
                _keychain_delete(key)
            print("  ✓ Credentials removed from Keychain.")

    print(f"\n  ✅ {PLUGIN_NAME} plugin removed. Restart Hermes to deactivate.\n")


def cmd_creds(yes: bool = False):
    print(f"\nUpdating credentials for {PLUGIN_NAME}...\n")
    for key in KEYS:
        existing = _keychain_read(key)
        value    = _prompt_cred(key, existing)
        if value:
            _keychain_store(key, value)
            print(f"  ✓ Updated: {key}")
        elif existing:
            print(f"  ✓ Kept existing: {key}")
        else:
            print(f"  ⚠️  No value provided for: {key}")
    print()


# ── Log management ────────────────────────────────────────────────────────────

def cmd_log(action: str = "status"):
    if not _is_enabled():
        print(f"  ⚠️  Plugin '{PLUGIN_NAME}' is not enabled — run './setup.sh install' first")
        sys.exit(1)

    data, yaml = _read_config()

    def _get_level():
        plugins = data.get("plugins") or {}
        config  = plugins.get("config") or {}
        plugin  = config.get(PLUGIN_NAME) or {}
        return plugin.get("log_level")

    def _set_level(level_or_none):
        from ruamel.yaml import CommentedMap
        if "plugins" not in data or data["plugins"] is None:
            data["plugins"] = CommentedMap()
        if "config" not in data["plugins"] or data["plugins"]["config"] is None:
            data["plugins"]["config"] = CommentedMap()
        if PLUGIN_NAME not in data["plugins"]["config"] or data["plugins"]["config"][PLUGIN_NAME] is None:
            data["plugins"]["config"][PLUGIN_NAME] = CommentedMap()
        if level_or_none is None:
            data["plugins"]["config"][PLUGIN_NAME].pop("log_level", None)
        else:
            data["plugins"]["config"][PLUGIN_NAME]["log_level"] = level_or_none
        _write_config(data, yaml)

    if action == "status":
        level    = _get_level() or "WARNING (default)"
        log_file = HERMES_HOME / "logs" / f"{PLUGIN_NAME}.log"
        print(f"\n  Log level for plugins.config.{PLUGIN_NAME}: {level}")
        if log_file.exists():
            print(f"  Log file: {log_file}  ({log_file.stat().st_size // 1024} KB)")
        else:
            print(f"  Log file: {log_file}  (not yet created)")
        print()

    elif action == "debug":
        _set_level("DEBUG")
        print(f"  ✓ Log level set to DEBUG. Restart Hermes to apply.")
        print(f"  ➡  tail -f {HERMES_HOME}/logs/{PLUGIN_NAME}.log")

    elif action == "quiet":
        _set_level(None)
        print(f"  ✓ Log level reset to WARNING (default). Restart Hermes to apply.")

    else:
        print(f"  Unknown log action: {action!r}. Use: debug | quiet | status")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="setup.py", description=f"{PLUGIN_NAME} plugin setup")
    sub    = parser.add_subparsers(dest="command")

    install_p = sub.add_parser("install", help="Install plugin (symlink + enable + credentials)")
    install_p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    remove_p = sub.add_parser("remove", help="Remove plugin (unlink + disable)")
    remove_p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    sub.add_parser("status", help="Show install and credential status")

    creds_p = sub.add_parser("creds", help="Re-enter stored credentials")
    creds_p.add_argument("--yes", "-y", action="store_true")

    log_p = sub.add_parser("log", help="Manage plugin log level")
    log_p.add_argument("log_action", nargs="?", choices=["debug", "quiet", "status"], default="status")

    args = parser.parse_args()

    if args.command == "install":
        cmd_install(yes=args.yes)
    elif args.command == "remove":
        cmd_remove(yes=args.yes)
    elif args.command == "status":
        cmd_status()
    elif args.command == "creds":
        cmd_creds(yes=args.yes)
    elif args.command == "log":
        cmd_log(args.log_action)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
