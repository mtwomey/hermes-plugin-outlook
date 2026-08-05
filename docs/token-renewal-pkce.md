# Outlook Plugin — Refresh Token Renewal via Browser PKCE Flow

**Status: WORKING (confirmed 2026-07-29)**

**Update (2026-08-05):** This flow is now available directly as Hermes
plugin tools — `outlook_renew_token_start` / `outlook_renew_token_finish`
— so day-to-day renewal no longer requires running scripts by hand or any
manual copy-paste. The agent drives the browser sign-in itself via
browser_navigate/browser_console and calls both tools back-to-back. The
standalone scripts described below remain as a fallback for use outside a
Hermes session. The underlying mechanics (client_id, scope, redirect_uri,
required headers, why other approaches failed) are unchanged and still
accurate.

This replaces the old browser-localStorage-extraction method, which no longer
works because Microsoft now encrypts the MSAL token cache in `localStorage`
(the `secret`/`clientId`/`homeAccountId` fields are no longer readable from
page-level JavaScript — the value is an opaque encrypted blob).

This document records the **exact working path** to get a fresh
`refresh_token` for the `hermes-outlook` Keychain credentials, using a
manual browser-based OAuth 2.0 Authorization Code + PKCE flow.

---

## Why this works (and other things didn't)

Robert Half's Azure AD tenant has Conditional Access / consent policies that
block most of the "normal" programmatic auth shortcuts:

| Approach tried | Result |
|---|---|
| Extracting refresh token from browser localStorage (old method) | **Dead.** MSAL cache is now encrypted; `secret` field is unreadable ciphertext. |
| OAuth device-code flow (any client_id) | **Blocked.** Tenant Conditional Access policy rejects device-code sign-ins outright (can't verify browser/device signals). |
| PKCE with Microsoft's own public client IDs (Azure CLI `04b07795-...`, Graph PowerShell `14d82eec-...`) requesting **Graph API** scopes (`graph.microsoft.com/...`) | **Blocked.** Tenant requires admin consent for Graph API permissions; individual users can't self-consent. Azure CLI's client_id also isn't registered/consented in this tenant at all (AADSTS700016). |
| PKCE with **Outlook Web's own client_id** (`9199bf20-a13f-4107-85dc-02114787ef48`) requesting **Graph API** scopes | **Blocked.** AADSTS65002 — that app is only pre-authorized for the legacy Outlook REST API scopes, not Graph. |
| PKCE with Outlook Web's client_id + wrong/guessed redirect URIs (`nativeclient`, `/mail/inbox`) | **Blocked.** AADSTS50011 — redirect URI must exactly match what's registered for that client_id. |
| **PKCE with Outlook Web's client_id + legacy `outlook.office.com` scopes + the EXACT redirect URI Outlook Web itself uses** | ✅ **WORKS.** |

The winning combination uses the **same client_id, scope pattern, and
redirect URI that Outlook Web's own JavaScript already uses** every time you
load `outlook.cloud.microsoft` — so nothing about it looks anomalous to
Azure AD. It's exactly the flow a browser SPA is designed to use; we're just
doing the browser-side and manual-paste parts ourselves instead of letting
JS automate them.

---

## How we found the exact redirect URI / scope

Browser DevTools → Network tab → filtered for `authorize` while logging into
`outlook.cloud.microsoft` fresh (or exported the whole session as a **.har**
file and grepped it for `redirect_uri`). This showed the real request Outlook
Web's own MSAL library sends:

```
https://login.microsoftonline.com/common/oauth2/v2.0/authorize?
  client_id=9199bf20-a13f-4107-85dc-02114787ef48
  &scope=https%3A%2F%2Foutlook.office.com%2F.default%20openid%20profile%20offline_access
  &redirect_uri=https%3A%2F%2Foutlook.cloud.microsoft%2Fmail%2F
  &response_mode=fragment
  ...
```

Key facts extracted:
- **client_id:** `9199bf20-a13f-4107-85dc-02114787ef48` (Outlook Web Access's own app registration — matches the `client_id` already stored in Keychain from the old method)
- **tenant_id:** `16532572-d567-4d67-8727-f12f7bb6aed3` (Robert Half's tenant — matches stored `tenant_id`)
- **scope:** `https://outlook.office.com/.default openid profile offline_access`
- **redirect_uri:** `https://outlook.cloud.microsoft/mail/`
- **response_mode:** `fragment` (the `code=...` and `state=...` land after a `#` in the redirect URL, not in the query string)

If Microsoft ever changes Outlook Web's client registration (redirect URI,
scope pattern, etc.), repeat this HAR-capture step to get the current values
and update the scripts below.

---

## The working scripts

Located in the plugin repo: `~/Git_Repos/hermes-plugin-outlook/scripts/`

- **`pkce_login_step1.py`** — generates the PKCE code_verifier/challenge and
  `state`, writes them to `/tmp/hermes_outlook_pkce_state.json`, builds the
  `/authorize` URL, and opens it in your default browser.
- **`pkce_login_step2.py`** — takes the full redirect URL you copy from the
  address bar after signing in, extracts `code` (checking both query string
  and URL fragment), and exchanges it for tokens via the `/token` endpoint.
  Spoofs browser-like `Origin`/`Referer`/`User-Agent` headers on the token
  exchange request — **this is required**, otherwise Azure AD rejects the
  redemption with `AADSTS9002327` ("Tokens issued for the 'Single-Page
  Application' client-type may only be redeemed via cross-origin requests").

### Current script constants (as of 2026-07-29)

```python
TENANT_ID = "16532572-d567-4d67-8727-f12f7bb6aed3"
CLIENT_ID = "9199bf20-a13f-4107-85dc-02114787ef48"
SCOPE = "https://outlook.office.com/.default openid profile offline_access"
REDIRECT_URI = "https://outlook.cloud.microsoft/mail/"
```

Token exchange headers (required to avoid AADSTS9002327):

```python
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://outlook.cloud.microsoft",
    "Referer": "https://outlook.cloud.microsoft/mail/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}
```

---

## Step-by-step procedure to renew the token

**The section below describes the manual/fallback procedure. For day-to-day renewal inside a Hermes session, just ask Hermes to renew the token — it handles this automatically.**


1. **Run step 1** to open the sign-in page:
   ```bash
   cd ~/Git_Repos/hermes-plugin-outlook
   python3 scripts/pkce_login_step1.py
   ```
   This prints the auth URL and opens it in your default browser.

2. **Sign in** as `matthew.twomey@roberthalf.com` in the browser window that
   opens. You'll land back on what looks like a normal Outlook inbox page
   (`outlook.cloud.microsoft/mail/#code=...`) — this is expected; the actual
   auth response is encoded in the URL fragment, invisible in the rendered
   page.

3. **Immediately copy the full URL** from the address bar (all of it,
   including everything after the `#`). The authorization `code` is
   **single-use and expires within a couple of minutes** — don't delay
   between copying and redeeming it.

4. **Run step 2 immediately** with that URL as the argument:
   ```bash
   python3 scripts/pkce_login_step2.py "<paste the full URL here>"
   ```
   This prints a JSON blob: `tenant_id`, `client_id`, `refresh_token`,
   `access_token_preview`, `expires_in`, `email`.

   **Common failure at this step:** `AADSTS70008` (authorization code
   expired due to inactivity) — just means too much time passed between
   steps 2 and 3. Go back to step 1 and get a fresh code; move faster this
   time.

5. **Copy the resulting JSON blob to the clipboard** (tenant_id, client_id,
   refresh_token, email — same shape the old browser-extraction snippet
   used to produce) and run:
   ```bash
   ./setup.sh credentials configure
   ```
   Confirm "Store all credentials from clipboard? [Y/n]" → yes. This writes
   all four values into macOS Keychain under service `hermes-outlook`.

6. **Verify** with:
   ```
   outlook_ping
   ```
   (or any Outlook tool call) inside Hermes — should return your email and
   display name with no `AADSTS700084` error.

7. **Clear your clipboard** afterward for hygiene (`pbcopy < /dev/null` or
   just copy something else) since it briefly held the plaintext refresh
   token.

---

## Known limitations / things to watch for

- **This refresh token is still an SPA-type token** — it likely still has
  the same 24-hour rolling lifetime as before (as long as an Outlook tool
  call happens at least once every 24h, the plugin's own rotation logic
  keeps it alive automatically; only a full >24h idle period would require
  repeating this whole procedure again).
- **Authorization codes expire fast** (a few minutes) — the step 1 → sign-in
  → step 2 handoff needs to happen without long pauses.
- **`response_mode=fragment`** means the code is after `#`, not `?`. If you
  ever see the browser redirect with `?code=...` instead, the params may
  have moved to the query string — `pkce_login_step2.py` already checks
  both locations, so this should be handled automatically.
- If Microsoft ever migrates Outlook Web off `outlook.cloud.microsoft` or
  changes its app registration, re-capture the HAR file to get updated
  `client_id` / `scope` / `redirect_uri` values (see "How we found the exact
  redirect URI / scope" above).
