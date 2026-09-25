---
name: outlook
description: "Robert Half Outlook / M365 email and calendar integration. Provides read, search, compose, and calendar management via the Outlook REST API with SPA refresh-token auth."
version: 1.0.0
author: Hermes Agent
tags: [outlook, email, calendar, m365, robert-half]
triggers:
  - "check my work email"
  - "read outlook email"
  - "look at my outlook calendar"
  - "send an email from work"
  - "schedule a meeting in outlook"
  - "check robert half email"
  - "check my outlook"
---

# Outlook Plugin

## Modifying this plugin (read before changing any tool)

Live tools come from **this** repo (`~/Git_Repos/hermes-plugin-outlook`):
- `tools.py` — handler bodies, signature `def outlook_send_email(args: dict, **kwargs)`
- `schemas.py` — per-tool schema constants (`SEND_EMAIL`, `LIST_EMAILS`, …), **not** a `TOOL_SCHEMAS` list

A new parameter must be added to **both** files, or it compiles fine and is silently uncallable.

`~/Git_Repos/hermes-skill-outlook/scripts/outlook_server.py` is a **superseded MCP server** — editing it changes nothing at runtime. Confirm the real target with
`grep -n "def outlook_send_email" ~/Git_Repos/hermes-plugin-outlook/tools.py` before patching.

**Native plugins load in-process at startup — there is no hot-reload.** Code changes require a full Hermes restart. After restarting, confirm the reload landed via `tool_describe("outlook_send_email")` and check the new parameter is present before relying on it.

Note that `skill_manage` cannot patch this skill (it is plugin-provided, not in `~/.hermes/skills/`); edit this file directly.

## Overview

Manages **Robert Half Outlook** (mattwo01@roberthalf.com) email and calendar.
Uses the Outlook REST API (`outlook.office.com/api/v2.0`) with SPA refresh-token
authentication — no Azure AD app registration required.

> **Note:** This plugin manages the **work/Robert Half** account.
> For personal/home email use the `imap` plugin (mtwomey@beakstar.com).

---

## Tools

### Connectivity
| Tool | Description |
|---|---|
| `outlook_ping` | Check connectivity and authentication |

### Auth / Token Renewal
| Tool | Description |
|---|---|
| `outlook_renew_token_start` | Begin renewing the refresh token — returns an auth_url for the agent to navigate to |
| `outlook_renew_token_finish` | Complete renewal by exchanging the captured redirect URL for a fresh token |

**Token lifetime:** the refresh token is issued to a single-page app and has a hard
**24-hour** lifetime that cannot be extended. A daily `invalid_grant` /
`AADSTS700084` is expected behavior, not a misconfiguration.

**Renewal procedure that works:**
1. `outlook_renew_token_start` → returns `auth_url`
2. Drive that URL with the **playwright-extension** tools. `browser_exec` with
   `local=true` fails outright when the default browser is not Chromium
   (`browser.use_real_profile` error) — do not retry it, switch tools.
3. On the "Pick an account" screen, the target account may show *Signed in* — clicking
   it can complete the whole flow with no password prompt.
4. The snapshot `ref` often goes stale mid-click because the page already redirected.
   That is success, not failure: re-snapshot and read the URL.
5. An Outlook **mail-app error page** after the redirect is irrelevant (it is OWA
   failing to load, not auth). What matters is the `#code=...` fragment in the URL.
6. `outlook_renew_token_finish` with that full URL **immediately** — the code expires
   in ~2 minutes.

### Email
| Tool | Description |
|---|---|
| `outlook_list_emails` | List recent emails in a folder |
| `outlook_read_email` | Read full email content by ID |
| `outlook_search_emails` | Search by keyword, sender, or subject |
| `outlook_list_folders` | List all mailbox folders |
| `outlook_mark_read` | Mark an email as read |
| `outlook_move_email` | Move email to another folder |
| `outlook_send_email` | Compose and send a new email (supports `attachments`) |
| `outlook_reply_email` | Reply to an email (sender or reply-all) |
| `outlook_forward_email` | Forward an email to new recipients |

### Calendar
| Tool | Description |
|---|---|
| `outlook_list_events` | List events in a date range |
| `outlook_get_event` | Get full event details including notes/body |
| `outlook_search_events` | Search events by keyword |
| `outlook_create_event` | Create a new calendar event |
| `outlook_update_event` | Update an existing event |
| `outlook_delete_event` | Delete (cancel) an event |
| `outlook_respond_event` | Accept / tentatively accept / decline an invitation |
| `outlook_get_attendee_status` | Check who has accepted/declined |
| `outlook_find_meeting_times` | Find free meeting slots for attendees |
| `outlook_list_calendars` | List all calendars in the mailbox |
| `outlook_get_schedule` | Get free/busy blocks for a time window |
| `outlook_add_attendees` | Add attendees to an existing event |
| `outlook_remove_attendees` | Remove attendees from an existing event |

---

## Common Patterns

### Reading recent email
```
outlook_list_emails(folder="inbox", limit=20, unread_only=true)
outlook_read_email(email_id="<id from list>")
```

### Searching email
```
# By sender
outlook_search_emails(query="from:alice@company.com")
# By subject keyword
outlook_search_emails(query="subject:budget")
# Full-text
outlook_search_emails(query="quarterly review")
```

### Sending / replying
```
# New email
outlook_send_email(to="bob@example.com", subject="Hello", body="Hi Bob!")
# With attachments — comma-separated local paths
outlook_send_email(to="bob@example.com", subject="Report",
                   body="Attached.", attachments="/path/a.pdf,/path/b.xlsx")
# Reply to sender only
outlook_reply_email(email_id="<id>", body="Thanks!")
# Reply-all
outlook_reply_email(email_id="<id>", body="Got it, everyone.", reply_all=true)
# Forward
outlook_forward_email(email_id="<id>", to="mgr@company.com", comment="FYI")
```

**Attachments:** files are base64-encoded into Graph `FileAttachment` objects.
Graph rejects sendMail payloads over ~4 MB and base64 inflates raw bytes by ~33%,
so the guard trips at ~3 MB raw — above that, send a share link instead.
A missing path returns a clear error rather than a Graph 400.

After sending anything important, verify it by reading the message back from
`sentitems` and checking its `attachments` field. The tool's own success message
confirms the API accepted the call, not that the file rode along.

### Calendar events
```
# This week's events
outlook_list_events(start="this week")
# Events today
outlook_list_events(start="today")
# Create a meeting
outlook_create_event(
  subject="Weekly Sync",
  start="next Monday at 10am",
  end="next Monday at 11am",
  attendees="alice@company.com,bob@company.com",
  is_online=true
)
# Accept an invitation
outlook_respond_event(event_id="<id>", response="accept")
# Decline with a message
outlook_respond_event(event_id="<id>", response="decline", comment="Conflict — out of office")
```

### Finding meeting times
```
outlook_find_meeting_times(
  attendees="alice@company.com,bob@company.com",
  duration_minutes=60,
  start="next Monday",
  end="next Friday"
)
```

---

## Authentication Model

This plugin uses **M365 SPA (Single-Page Application) refresh token** authentication:

1. A refresh token is extracted once from the user's browser MSAL cache.
2. At runtime, the plugin exchanges it for a short-lived access token (1 hour) using
   spoofed browser headers.
3. The response includes a new refresh token, which is rotated back to Keychain
   automatically — the token chain is self-sustaining.

> **⚠️ SPA tokens have a FIXED 24-hour hard lifetime (AADSTS700084).**
> If no Outlook tool is called for >24 hours, the chain expires and credentials
> must be re-extracted from the browser.

---

## Credential Setup

Credentials are stored in macOS Keychain under service name `hermes-outlook`.

**Keys required:**

| Key | Description |
|---|---|
| `email` | `mattwo01@roberthalf.com` |
| `tenant_id` | Azure AD Tenant ID |
| `client_id` | OAuth2 Client ID for the Outlook Web first-party app |
| `refresh_token` | SPA refresh token from browser |

See `README.md` for the browser console snippet that extracts all four values
and copies them to your clipboard in one shot.

### Token renewal after expiry

If any outlook_* tool call fails with a token-expiry error (AADSTS700084 or
AADSTS70008), renew it:

1. Call `outlook_renew_token_start` — returns an auth_url.
2. Navigate to it with your own browser tool (browser_navigate). Drive any
   account-picker/login/MFA steps that appear — do not assume one call
   finishes it (see docs/token-renewal-pkce.md for known behavior).
3. Once signed in, get the true current URL via
   `browser_console(expression='window.location.href')` — do not trust
   browser_navigate's own returned snapshot, which may show rendered page
   content instead of the redirect URL.
4. Call `outlook_renew_token_finish(redirect_url=<that URL>)` immediately
   — the code expires within about 2 minutes.
5. Retry the original failed call — no Hermes restart needed.

Fallback (outside a Hermes session): `scripts/pkce_login_step1.py` +
`scripts/pkce_login_step2.py`, then `./setup.sh credentials configure`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `AADSTS700084` error | Token expired. Re-extract from browser and run `./setup.sh creds` |
| `HTTP 401` on first call | Check tenant_id and client_id. Re-run `./setup.sh creds` |
| `Credential not found` error | Run `./setup.sh install` |
| Tools not appearing | Check `./setup.sh status` and restart Hermes |
| Empty folder results | Use `outlook_list_folders` to find exact folder name |

### Enable debug logging
```bash
./setup.sh log debug
# restart Hermes, then:
tail -f ~/.hermes/logs/outlook.log
```

---

## Pitfalls

- **Token expires after 24 hours of inactivity (`AADSTS700084`)** — the SPA refresh token has a hard 24-hour lifetime. If no Outlook tool is called within that window the chain expires and must be renewed via the PKCE flow described in the Token renewal section above.
- **`outlook_get_schedule` only reads the authenticated user's own calendar** — due to Outlook REST v2 limitations it cannot fetch other attendees' free/busy. Use `outlook_find_meeting_times` when you need availability across multiple people.
- **`outlook_update_event` body replaces the entire description** — omit the `body` parameter if you only want to change the time or subject; passing it will overwrite existing notes.
- **Folder names are case-sensitive and must be exact** — use `outlook_list_folders` to find the correct name before moving or listing; guessing "Inbox" vs "inbox" can return empty results.
- **Range phrases in `outlook_list_events`** — when `start` is a range phrase like `"this week"`, do NOT pass `end`; the tool sets both automatically and a manual `end` will conflict.
- **Credentials not loaded at startup** — credential loading is lazy (first tool call). If `outlook_ping` returns a credentials error, run `./setup.sh creds` and restart Hermes.

---

## Setup Commands

```bash
./setup.sh install     # Full install (symlink + enable + credentials)
./setup.sh status      # Check install and credential state
./setup.sh creds       # Update stored credentials
./setup.sh log debug   # Enable DEBUG logging (requires Hermes restart)
./setup.sh log quiet   # Back to WARNING
./setup.sh log status  # Show current log level
./setup.sh remove      # Uninstall the plugin
```
