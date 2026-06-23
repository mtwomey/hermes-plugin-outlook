# hermes-plugin-outlook

Hermes native plugin for **Robert Half Outlook / M365** email and calendar.

Provides 23 tools covering email (list, read, search, send, reply, forward, move) and
calendar (list, create, update, delete, respond, find meeting times, free/busy).

Uses **SPA refresh-token auth** — no Azure AD app registration required, no admin
consent needed. The token is extracted once from your browser and rotates automatically
at runtime.

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

## Credential Extraction (one-time setup)

Outlook Web stores your login tokens in `localStorage`. The snippet below reads them
and calls `copy()` to put all four values on your clipboard as a JSON blob in one shot —
no manual digging through DevTools storage.

### Step 1 — Open the browser console

1. Go to **`https://outlook.office.com`** in Chrome or Edge, logged in as your RHI account
2. Open DevTools: **`Cmd+Option+I`** (macOS) → click the **Console** tab

### Step 2 — Run the extraction snippet

Paste this entire block into the Console and press **Enter**:

```javascript
(() => {
  const keys = Object.keys(localStorage).filter(k => k.includes('msal'));
  const rtKey = keys.find(k => {
    try { return JSON.parse(localStorage[k])?.credentialType === 'RefreshToken'; }
    catch(e) { return false; }
  });
  if (!rtKey) {
    console.error('No MSAL RefreshToken found — make sure you are logged into outlook.office.com');
    return;
  }
  const rt = JSON.parse(localStorage[rtKey]);
  const tenant_id = rt.homeAccountId.split('.')[1];
  const client_id = rt.clientId;
  const refresh_token = rt.secret;
  const accountKey = keys.find(k => {
    try {
      const v = JSON.parse(localStorage[k]);
      return v?.homeAccountId === rt.homeAccountId && v?.username;
    } catch(e) { return false; }
  });
  const email = accountKey ? JSON.parse(localStorage[accountKey]).username : '';
  const blob = JSON.stringify({ tenant_id, client_id, refresh_token, email });
  copy(blob);
  console.log('✓ All credentials copied to clipboard as JSON!');
  console.log('  tenant_id:    ', tenant_id);
  console.log('  client_id:    ', client_id);
  console.log('  email:        ', email || '(not found — you will be prompted)');
  console.log('  refresh_token:', refresh_token.substring(0, 20) + '... (' + refresh_token.length + ' chars)');
})();
```

You should see `✓ All credentials copied to clipboard as JSON!` in the console.

> **Tip:** If you see `No MSAL RefreshToken found`, make sure you're on the
> `https://outlook.office.com` tab (not Teams or SharePoint) and that you are
> fully logged in. Click your inbox first to trigger a token refresh, then re-run.

### Step 3 — Run setup

**Leave the JSON blob in your clipboard** (don't copy anything else), then:

```bash
./setup.sh install
```

The setup script reads the clipboard automatically, shows you a preview of all four
values, and stores them in Keychain with a single `[Y/n]` confirmation.

---

## Token Renewal

> **⚠️ SPA tokens have a fixed 24-hour hard lifetime (`AADSTS700084`).**
> If no Outlook tool is called for >24 hours, the token chain expires and you need
> to re-extract from your browser.

When you see `AADSTS700084` errors:

1. Go to `https://outlook.office.com` in your browser (this reissues a fresh token)
2. Re-run the console snippet above — it copies the new blob to your clipboard
3. Run `./setup.sh creds` — detects the blob and updates all credentials in one step

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

1. A refresh token is extracted once from the browser's MSAL localStorage cache.
2. At runtime the plugin POSTs to `login.microsoftonline.com` with spoofed browser
   headers to exchange it for a short-lived access token (1 hour).
3. The response includes a new refresh token, which is written back to Keychain
   automatically — the token chain is self-sustaining as long as it's used regularly.

No Azure AD app registration, no admin consent, no OAuth redirect flow required.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `AADSTS700084` | Token expired (>24h). Re-extract and run `./setup.sh creds` |
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
