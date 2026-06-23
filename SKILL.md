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

### Email
| Tool | Description |
|---|---|
| `outlook_list_emails` | List recent emails in a folder |
| `outlook_read_email` | Read full email content by ID |
| `outlook_search_emails` | Search by keyword, sender, or subject |
| `outlook_list_folders` | List all mailbox folders |
| `outlook_mark_read` | Mark an email as read |
| `outlook_move_email` | Move email to another folder |
| `outlook_send_email` | Compose and send a new email |
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
# Reply to sender only
outlook_reply_email(email_id="<id>", body="Thanks!")
# Reply-all
outlook_reply_email(email_id="<id>", body="Got it, everyone.", reply_all=true)
# Forward
outlook_forward_email(email_id="<id>", to="mgr@company.com", comment="FYI")
```

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
| `tenant_id` | Azure AD Tenant ID (e.g. `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) |
| `client_id` | OAuth2 Client ID for the Outlook Web first-party app |
| `refresh_token` | SPA refresh token from browser |

### Extracting from browser (one-time setup)

1. Log into https://outlook.office.com in Chrome/Edge
2. Open DevTools → Application → Storage → Session Storage → `https://outlook.office.com`
3. Find the key matching pattern `.*login.microsoftonline.com.*` — the value is a JSON blob
4. Inside that blob find `"tenantId"` → copy as `tenant_id`
5. Find `"clientId"` → copy as `client_id`
6. Find `"secret"` under a key containing `"refreshtoken"` → copy as `refresh_token`
7. Run `./setup.sh install` and paste the values when prompted

### Token renewal after expiry

If you get `AADSTS700084` errors:
1. Open outlook.office.com in your browser (this reissues a fresh token)
2. Repeat the extraction steps above
3. Run `./setup.sh creds` and re-enter just the `refresh_token`

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
