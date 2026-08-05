# hermes-plugin-outlook

Hermes native plugin for **Robert Half Outlook / M365** email and calendar.

Provides 23 tools covering email (list, read, search, send, reply, forward, move) and
calendar (list, create, update, delete, respond, find meeting times, free/busy).

Uses **SPA refresh-token auth** — no Azure AD app registration required, no admin
consent needed. The token renews via a Hermes-agent-driven browser PKCE flow (or a
manual fallback script) and rotates automatically at runtime between renewals.

---

## Requirements

- macOS (uses Keychain for credential storage)
- Chrome or Edge browser, logged into `https://outlook.office.com` as `mattwo01@roberthalf.com`
- Hermes Agent installed

---

## Installation

```bash
cd ~/Git_Repos/hermes-plugin-outlook

# Step 1 — Extract credentials from your browser (see below)
# Step 2 — Run setup (reads credentials from clipboard automatically)
./setup.sh install

# Step 3 — Restart Hermes
```

---

## Credential Setup / Token Renewal

**Preferred method — inside a Hermes chat session:**

1. Ask Hermes to renew the Outlook token (or just try an Outlook tool — if
   the token has expired you'll get a message pointing you here).
2. Hermes calls `outlook_renew_token_start`, which returns a Microsoft
   sign-in URL.
3. Hermes navigates to it with its own browser tool and drives sign-in
   (account picker, password/MFA if needed) — you may need to approve an
   MFA prompt on your device, but there is no copy/paste required from you.
4. Once signed in, Hermes captures the resulting URL (which contains the
   authorization code) and calls `outlook_renew_token_finish` with it,
   which exchanges the code for a fresh refresh token and saves it to
   Keychain — no restart needed, Outlook tools work again immediately.

The authorization code is single-use and expires within a couple of
minutes, so this needs to happen promptly once sign-in completes — Hermes
handles the timing automatically.

**Fallback method — outside a Hermes session (e.g. plugin broken):**

```bash
cd ~/Git_Repos/hermes-plugin-outlook
python3 scripts/pkce_login_step1.py     # opens browser
# sign in, copy the resulting URL immediately
python3 scripts/pkce_login_step2.py "<pasted URL>"
# copy the printed JSON to your clipboard, then:
./setup.sh credentials configure
```

See `docs/token-renewal-pkce.md` for the full technical background on why
this flow works, how the exact client_id/scope/redirect_uri were
discovered, and what other approaches were tried and failed.

---

## Setup Commands

```bash
./setup.sh install       # Full install: symlink + enable + credentials
./setup.sh status        # Check install and credential state
./setup.sh creds         # Update stored credentials
./setup.sh log debug     # Enable DEBUG logging (requires Hermes restart)
./setup.sh log quiet     # Back to WARNING
./setup.sh log status    # Show current log level
./setup.sh remove        # Uninstall the plugin
```

---

## Auth Model

This plugin uses M365 SPA (Single-Page Application) refresh token authentication:

1. A refresh token is obtained via the PKCE renewal flow (agent-driven or manual
   fallback — see Credential Setup / Token Renewal above).
2. At runtime the plugin POSTs to `login.microsoftonline.com` with spoofed browser
   headers to exchange it for a short-lived access token (1 hour).
3. The response includes a new refresh token, which is written back to Keychain
   automatically — the token chain is self-sustaining as long as it's used regularly.
4. When the refresh token itself expires (~24h of inactivity), renewal uses a
   browser-driven OAuth 2.0 Authorization Code + PKCE flow — see the Credential
   Setup / Token Renewal section above. No Azure AD app registration or admin
   consent is required; the flow reuses Outlook Web's own already-consented
   client_id.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `AADSTS700084` | Token expired (>24h). Ask Hermes to renew it (outlook_renew_token_start/finish), or use the manual fallback scripts — see Credential Setup / Token Renewal section |
| `HTTP 401` | Wrong tenant_id or client_id. Re-run `./setup.sh creds` |
| `Credential not found` | Run `./setup.sh install` |
| Tools not appearing in Hermes | Run `./setup.sh status`, restart Hermes |
| Empty results from folder | Run `outlook_list_folders` to find exact folder name |

### Debug logging

```bash
./setup.sh log debug
# Restart Hermes, then:
tail -f ~/.hermes/logs/outlook.log
```
