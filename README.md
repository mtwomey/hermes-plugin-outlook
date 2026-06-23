# hermes-plugin-outlook

Hermes native plugin for Microsoft Outlook (M365) — email and calendar via the Outlook REST API v2.

## What this provides

22 tools covering:
- **Email**: list, read, search, send, reply, forward, move, mark-read, list folders
- **Calendar**: list/search/get/create/update/delete events, respond to invites, find meeting times, check attendee status, manage attendees, get schedule, list calendars

## Authentication

This plugin authenticates using a **refresh token** extracted from the browser's MSAL token cache. No Azure AD app registration or IT admin consent is required — it re-uses the same OAuth2 client that the Outlook web app itself uses.

### Token expiry

SPA refresh tokens have a **24-hour hard limit** (AADSTS700084). As long as at least one Outlook tool call is made every 24 hours, the token chain self-renews automatically. If no call is made for >24 hours, credentials must be re-extracted from the browser.

### Extracting credentials from the browser

1. Open `https://outlook.office.com` in Chrome/Edge and log in
2. Open DevTools → Application → Local Storage → `https://outlook.office.com`
3. Find a key that looks like: `msal.<client_id>.token.keys.*`
4. Extract:
   - **tenant_id**: the GUID in the token URL (login.microsoftonline.com/`<tenant_id>`/)
   - **client_id**: the `clientId` in the MSAL key (UUID string)
   - **refresh_token**: In Local Storage find an entry with `"credentialType": "RefreshToken"` — copy the `"secret"` value

Alternatively use the browser console:
```javascript
// Find all MSAL keys
Object.keys(localStorage).filter(k => k.includes('msal'))

// Find refresh token
Object.entries(localStorage)
  .find(([k,v]) => v.includes('"credentialType":"RefreshToken"'))
```

## Install

```bash
cd ~/Git_Repos/hermes-plugin-outlook
./setup.sh install
```

Then restart Hermes.

## Commands

```bash
./setup.sh status            # Check install + credentials + connectivity
./setup.sh install [--yes]   # Install / re-install
./setup.sh remove  [--yes]   # Remove symlink and disable plugin
./setup.sh creds   [--yes]   # Update stored credentials
./setup.sh log debug         # Enable DEBUG logging
./setup.sh log quiet         # Back to WARNING
./setup.sh log status        # Show current log level
```

## Files

```
hermes-plugin-outlook/
├── __init__.py        # Plugin entry point — registers all tools with Hermes
├── schemas.py         # Tool JSON schemas (what the LLM sees)
├── tools.py           # Tool handler implementations
├── setup.py           # Install/remove/status/creds/log management
├── setup.sh           # Thin launcher for setup.py under Hermes venv
├── plugin.yaml        # Plugin metadata
├── scripts/
│   ├── keychain_utils.py   # macOS Keychain credential helpers
│   ├── date_utils.py       # Natural-language date parsing
│   └── logging_utils.py    # Rotating file + stderr logging
└── README.md
```

## Keychain

Credentials are stored in macOS Keychain under service `hermes-outlook`:
- `email` — your Outlook email address
- `tenant_id` — Azure AD tenant ID
- `client_id` — OAuth2 client ID
- `refresh_token` — SPA refresh token (auto-rotated on each use)
