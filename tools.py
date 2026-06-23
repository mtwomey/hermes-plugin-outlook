"""
Tool handler functions for the outlook plugin.

Authentication strategy
-----------------------
Authenticates to the Outlook REST API (outlook.office.com/api/v2.0)
using a refresh token extracted from the user's browser MSAL cache.
No Azure AD app registration or IT admin consent is required.

The refresh token is exchanged for a short-lived access token (1 hour)
by posting to the Microsoft token endpoint with spoofed browser headers.
The response includes a new refresh token, which is written back to
Keychain — so the token chain is self-sustaining as long as at least
one Outlook tool call is made within every 24-hour window.

IMPORTANT: SPA refresh tokens have a FIXED 24-hour hard lifetime (AADSTS700084).
If no Outlook tool is called for >24 hours, the token chain expires and
credentials must be re-extracted from the browser.

Rules
-----
- Every handler: def outlook_<verb>(args: dict, **kwargs) -> str
- Every handler MUST return json.dumps({...}) — never a raw dict or None
- Every handler MUST catch all exceptions and return {"error": "..."}
- Credentials are loaded LAZILY on first call — NOT at import time
"""

import json
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))

log = logging.getLogger("outlook")

# ── Lazy credential + token singleton ────────────────────────────────────────

_state: dict = {}          # populated on first _get_creds() call
_token_lock  = threading.Lock()
_token_cache: dict = {"access_token": None, "expires_at": 0.0}
_REFRESH_BUFFER_SECS = 120   # refresh 2 min before expiry


def _get_creds() -> dict:
    """Load credentials from Keychain on first call; return cached after that."""
    if not _state:
        try:
            from keychain_utils import fetch_credential, CredentialError  # noqa: F401
            SERVICE = "hermes-outlook"
            keys = ["email", "refresh_token", "tenant_id", "client_id"]
            env_map = {
                "email":         "OUTLOOK_EMAIL",
                "refresh_token": "OUTLOOK_REFRESH_TOKEN",
                "tenant_id":     "OUTLOOK_TENANT_ID",
                "client_id":     "OUTLOOK_CLIENT_ID",
            }
            creds = {k: fetch_credential(SERVICE, k, env_fallback=env_map[k]) for k in keys}
            _state.update(creds)
        except Exception as e:
            raise RuntimeError(
                f"Outlook credentials not found. "
                f"Run `./setup.sh install` in the plugin directory to store credentials. ({e})"
            )
    return _state


def _get_access_token() -> str:
    """Return a valid access token, refreshing via the stored refresh token if needed."""
    import urllib.request, urllib.parse  # noqa: E401

    with _token_lock:
        if (_token_cache["access_token"]
                and time.time() < _token_cache["expires_at"] - _REFRESH_BUFFER_SECS):
            return _token_cache["access_token"]

        creds = _get_creds()
        params = urllib.parse.urlencode({
            "client_id":     creds["client_id"],
            "grant_type":    "refresh_token",
            "refresh_token": creds["refresh_token"],
            "scope":         "https://outlook.office.com/.default offline_access",
        }).encode()

        req = urllib.request.Request(
            f"https://login.microsoftonline.com/{creds['tenant_id']}/oauth2/v2.0/token",
            data=params,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin":       "https://outlook.office.com",
                "Referer":      "https://outlook.office.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            try:
                err = json.loads(body)
                code = err.get("error", "unknown_error")
                desc = err.get("error_description", body[:300])
            except Exception:
                code = str(e.code)
                desc = body[:300]
            log.error("Token refresh failed — HTTP %s | error=%s | %s", e.code, code, desc)
            raise RuntimeError(f"Token refresh failed (HTTP {e.code}): {code} — {desc}") from e

        if "error" in data:
            code = data["error"]
            desc = data.get("error_description", "")
            log.error("Token refresh failed — error=%s | %s", code, desc)
            raise RuntimeError(f"Token refresh failed: {code} — {desc}")

        access_token  = data["access_token"]
        expires_in    = int(data.get("expires_in", 3600))
        new_refresh   = data.get("refresh_token")

        _token_cache["access_token"] = access_token
        _token_cache["expires_at"]   = time.time() + expires_in

        if new_refresh and new_refresh != creds["refresh_token"]:
            try:
                from keychain_utils import store_credential
                store_credential("hermes-outlook", "refresh_token", new_refresh)
                _state["refresh_token"] = new_refresh
                log.info("refresh token rotated and saved to Keychain")
            except Exception as e:
                log.warning("failed to rotate refresh token: %s", e)

        return access_token


def _api(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated Outlook REST API call."""
    import urllib.request, urllib.parse  # noqa: E401
    token = _get_access_token()
    if "?" in path:
        base, qs = path.split("?", 1)
        url = f"https://outlook.office.com/api/v2.0{base}?{urllib.parse.quote(qs, safe='=&$,@:/')}"
    else:
        url = f"https://outlook.office.com/api/v2.0{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_text[:300]}")


# ── Date helpers ──────────────────────────────────────────────────────────────

_CST = "Central Standard Time"

def _dt(value: str, tz: str = _CST, end_of_day: bool = False) -> str:
    """Resolve a natural-language or ISO date string to ISO datetime."""
    if not value:
        return value
    from date_utils import parse_dt
    return parse_dt(value, tz, end_of_day=end_of_day)


def _dt_range(value: str, tz: str = _CST) -> tuple[str, str]:
    """Resolve a range phrase to (start_iso, end_iso)."""
    from date_utils import parse_date_range
    return parse_date_range(value, tz)


def _is_range_phrase(value: str) -> bool:
    from date_utils import is_range_phrase
    return is_range_phrase(value)


# ── Event formatter ───────────────────────────────────────────────────────────

def _fmt_event(e: dict) -> dict:
    """Normalise a raw Outlook calendar event into a clean dict."""
    start     = e.get("Start", {})
    end       = e.get("End", {})
    organizer = e.get("Organizer", {}).get("EmailAddress", {})
    attendees = [
        {
            "name":   a.get("EmailAddress", {}).get("Name", ""),
            "email":  a.get("EmailAddress", {}).get("Address", ""),
            "status": a.get("Status", {}).get("Response", "none"),
            "type":   a.get("Type", "required"),
        }
        for a in e.get("Attendees", [])
    ]
    return {
        "id":              e.get("Id", ""),
        "subject":         e.get("Subject", "(no subject)"),
        "start":           start.get("DateTime", "")[:16].replace("T", " "),
        "end":             end.get("DateTime", "")[:16].replace("T", " "),
        "timezone":        start.get("TimeZone", ""),
        "location":        e.get("Location", {}).get("DisplayName", ""),
        "body":            "",   # not fetched in list calls — use outlook_get_event
        "is_all_day":      e.get("IsAllDay", False),
        "is_cancelled":    e.get("IsCancelled", False),
        "is_online":       e.get("IsOnlineMeeting", False),
        "online_url":      e.get("OnlineMeeting", {}).get("JoinUrl", "") if e.get("OnlineMeeting") else "",
        "organizer":       organizer.get("Name", ""),
        "organizer_email": organizer.get("Address", ""),
        "attendees":       attendees,
        "response":        e.get("ResponseStatus", {}).get("Response", "none"),
        "recurrence":      bool(e.get("Recurrence")),
        "sensitivity":     e.get("Sensitivity", "normal"),
    }


# ── Ping ──────────────────────────────────────────────────────────────────────

def outlook_ping(args: dict, **kwargs) -> str:
    """Verify connectivity and authentication."""
    log.debug("outlook_ping: called")
    try:
        data = _api("GET", "/me?$select=DisplayName,EmailAddress")
        log.debug("outlook_ping: ok email=%s", data.get("EmailAddress", ""))
        return json.dumps({
            "status":       "ok",
            "email":        data.get("EmailAddress", ""),
            "display_name": data.get("DisplayName", ""),
        })
    except Exception as e:
        log.warning("outlook_ping error: %s", e)
        return json.dumps({"error": str(e)})


# ── Email handlers ────────────────────────────────────────────────────────────

def outlook_list_emails(args: dict, **kwargs) -> str:
    """List recent emails in a mailbox folder."""
    folder      = args.get("folder", "inbox")
    limit       = min(int(args.get("limit", 20)), 50)
    unread_only = bool(args.get("unread_only", False))
    log.debug("outlook_list_emails: folder=%s limit=%s unread_only=%s", folder, limit, unread_only)
    try:
        select = "Id,Subject,From,ReceivedDateTime,IsRead"
        params = f"$top={limit}&$select={select}&$orderby=ReceivedDateTime desc"
        if unread_only:
            params += "&$filter=IsRead eq false"
        data = _api("GET", f"/me/mailfolders/{folder}/messages?{params}")
        emails = [
            {
                "id":      m["Id"],
                "subject": m.get("Subject", "(no subject)"),
                "from":    m.get("From", {}).get("EmailAddress", {}).get("Name", ""),
                "date":    m.get("ReceivedDateTime", "")[:10],
                "unread":  not m.get("IsRead", True),
            }
            for m in data.get("value", [])
        ]
        return json.dumps({"folder": folder, "total_found": len(emails), "emails": emails})
    except Exception as e:
        log.warning("outlook_list_emails error: folder=%s %s", folder, e)
        return json.dumps({"error": str(e)})


def outlook_read_email(args: dict, **kwargs) -> str:
    """Read full email body by ID."""
    email_id = args.get("email_id", "")
    log.debug("outlook_read_email: email_id=%s", email_id)
    try:
        import re
        select = "Id,Subject,From,ToRecipients,CcRecipients,ReceivedDateTime,Body,Attachments,IsRead"
        m = _api("GET", f"/me/messages/{email_id}?$select={select}&$expand=Attachments")
        to  = ", ".join(r["EmailAddress"]["Address"] for r in m.get("ToRecipients", []))
        cc  = ", ".join(r["EmailAddress"]["Address"] for r in m.get("CcRecipients", []))
        attachments = [a.get("Name", "") for a in m.get("Attachments", [])]
        body = m.get("Body", {}).get("Content", "")
        if m.get("Body", {}).get("ContentType", "") == "HTML":
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s{2,}", " ", body).strip()
        return json.dumps({
            "id":          m.get("Id", ""),
            "subject":     m.get("Subject", "(no subject)"),
            "from":        m.get("From", {}).get("EmailAddress", {}).get("Name", ""),
            "to":          to,
            "cc":          cc,
            "date":        m.get("ReceivedDateTime", "")[:19].replace("T", " "),
            "body":        body[:8000],
            "attachments": attachments,
        })
    except Exception as e:
        log.warning("outlook_read_email error: email_id=%s %s", email_id, e)
        return json.dumps({"error": str(e)})


def outlook_search_emails(args: dict, **kwargs) -> str:
    """Search emails by keyword, sender, or subject."""
    query  = args.get("query", "")
    folder = args.get("folder", "inbox")
    limit  = min(int(args.get("limit", 20)), 50)
    log.debug("outlook_search_emails: query=%r folder=%s limit=%s", query, folder, limit)
    try:
        select = "Id,Subject,From,ReceivedDateTime,IsRead"
        if query.startswith("from:"):
            addr = query[5:].strip()
            filter_param = (
                f"$filter=ReceivedDateTime ge 2000-01-01T00:00:00Z"
                f" and from/emailAddress/address eq '{addr}'"
            )
            params = f"$top={limit}&$select={select}&$orderby=ReceivedDateTime desc&{filter_param}"
        elif query.startswith("subject:"):
            subj = query[8:].strip()
            filter_param = (
                f"$filter=ReceivedDateTime ge 2000-01-01T00:00:00Z"
                f" and contains(subject,'{subj}')"
            )
            params = f"$top={limit}&$select={select}&$orderby=ReceivedDateTime desc&{filter_param}"
        else:
            params = f'$top={limit}&$select={select}&$search="{query}"'

        data = _api("GET", f"/me/mailfolders/{folder}/messages?{params}")
        emails = [
            {
                "id":      m["Id"],
                "subject": m.get("Subject", "(no subject)"),
                "from":    m.get("From", {}).get("EmailAddress", {}).get("Name", ""),
                "date":    m.get("ReceivedDateTime", "")[:10],
                "unread":  not m.get("IsRead", True),
            }
            for m in data.get("value", [])
        ]
        return json.dumps({"folder": folder, "query": query, "total_found": len(emails), "emails": emails})
    except Exception as e:
        log.warning("outlook_search_emails error: query=%s %s", query, e)
        return json.dumps({"error": str(e)})


def outlook_list_folders(args: dict, **kwargs) -> str:
    """List all mailbox folders."""
    log.debug("outlook_list_folders: called")
    try:
        data = _api("GET", "/me/mailfolders?$top=100&$select=Id,DisplayName,UnreadItemCount,TotalItemCount")
        folders = [
            {
                "id":           f["Id"],
                "name":         f.get("DisplayName", ""),
                "unread_count": f.get("UnreadItemCount", 0),
                "total_count":  f.get("TotalItemCount", 0),
            }
            for f in data.get("value", [])
        ]
        return json.dumps({"folders": folders})
    except Exception as e:
        log.warning("outlook_list_folders error: %s", e)
        return json.dumps({"error": str(e)})


def outlook_mark_read(args: dict, **kwargs) -> str:
    """Mark an email as read."""
    email_id = args.get("email_id", "")
    log.info("outlook_mark_read: email_id=%s", email_id)
    try:
        _api("PATCH", f"/me/messages/{email_id}", {"IsRead": True})
        return json.dumps({"status": "ok", "id": email_id})
    except Exception as e:
        log.warning("outlook_mark_read error: email_id=%s %s", email_id, e)
        return json.dumps({"error": str(e)})


def outlook_move_email(args: dict, **kwargs) -> str:
    """Move an email to another folder."""
    email_id           = args.get("email_id", "")
    destination_folder = args.get("destination_folder", "")
    log.info("outlook_move_email: email_id=%s dest=%s", email_id, destination_folder)
    try:
        result = _api("POST", f"/me/messages/{email_id}/move", {"DestinationId": destination_folder})
        return json.dumps({"status": "ok", "id": result.get("Id", email_id), "moved_to": destination_folder})
    except Exception as e:
        log.warning("outlook_move_email error: email_id=%s %s", email_id, e)
        return json.dumps({"error": str(e)})


def outlook_send_email(args: dict, **kwargs) -> str:
    """Compose and send a new email."""
    to           = args.get("to", "")
    subject      = args.get("subject", "")
    body         = args.get("body", "")
    cc           = args.get("cc", "")
    bcc          = args.get("bcc", "")
    body_type    = args.get("body_type", "Text")
    save_to_sent = bool(args.get("save_to_sent", True))
    log.info("outlook_send_email: to=%r subject=%r", to, subject)
    try:
        def _addrs(csv: str) -> list:
            return [{"EmailAddress": {"Address": a.strip()}} for a in csv.split(",") if a.strip()]

        message: dict = {
            "Subject":      subject,
            "Body":         {"ContentType": body_type, "Content": body},
            "ToRecipients": _addrs(to),
        }
        if cc:
            message["CcRecipients"] = _addrs(cc)
        if bcc:
            message["BccRecipients"] = _addrs(bcc)

        _api("POST", "/me/sendmail", {"Message": message, "SaveToSentItems": save_to_sent})
        return json.dumps({"status": "ok", "message": f"Email sent to {to}"})
    except Exception as e:
        log.warning("outlook_send_email error: to=%s %s", to, e)
        return json.dumps({"error": str(e)})


def outlook_reply_email(args: dict, **kwargs) -> str:
    """Reply (or reply-all) to an existing email."""
    email_id  = args.get("email_id", "")
    body      = args.get("body", "")
    reply_all = bool(args.get("reply_all", False))
    body_type = args.get("body_type", "Text")
    log.info("outlook_reply_email: email_id=%s reply_all=%s", email_id, reply_all)
    try:
        action = "replyall" if reply_all else "reply"
        _api("POST", f"/me/messages/{email_id}/{action}", {"Comment": body})
        return json.dumps({"status": "ok", "action": action})
    except Exception as e:
        log.warning("outlook_reply_email error: email_id=%s %s", email_id, e)
        return json.dumps({"error": str(e)})


def outlook_forward_email(args: dict, **kwargs) -> str:
    """Forward an email to new recipients."""
    email_id = args.get("email_id", "")
    to       = args.get("to", "")
    comment  = args.get("comment", "")
    log.info("outlook_forward_email: email_id=%s to=%r", email_id, to)
    try:
        to_list = [{"EmailAddress": {"Address": a.strip()}} for a in to.split(",") if a.strip()]
        payload: dict = {"ToRecipients": to_list}
        if comment:
            payload["Comment"] = comment
        _api("POST", f"/me/messages/{email_id}/forward", payload)
        return json.dumps({"status": "ok", "forwarded_to": to})
    except Exception as e:
        log.warning("outlook_forward_email error: email_id=%s %s", email_id, e)
        return json.dumps({"error": str(e)})


# ── Calendar handlers ─────────────────────────────────────────────────────────

def outlook_list_events(args: dict, **kwargs) -> str:
    """List calendar events in a date range."""
    start       = args.get("start", "")
    end         = args.get("end", "")
    calendar_id = args.get("calendar_id", "calendar")
    limit       = min(int(args.get("limit", 20)), 50)
    log.debug("outlook_list_events: start=%r end=%r", start, end)
    try:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        if start and _is_range_phrase(start):
            start, end = _dt_range(start)
        else:
            if not start:
                start = now.strftime("%Y-%m-%dT00:00:00")
            else:
                start = _dt(start)
            if not end:
                end_dt = datetime.fromisoformat(start) + timedelta(days=7)
                end = end_dt.strftime("%Y-%m-%dT23:59:59")
            else:
                end = _dt(end, end_of_day=True)

        select = "Id,Subject,Start,End,Location,IsAllDay,IsCancelled,IsOnlineMeeting,OnlineMeeting,Organizer,Attendees,ResponseStatus,Recurrence,Sensitivity"
        params = (
            f"$top={limit}&$select={select}"
            f"&startDateTime={start}&endDateTime={end}"
            f"&$orderby=Start/DateTime asc"
        )
        data = _api("GET", f"/me/calendarView?{params}")
        events = [_fmt_event(e) for e in data.get("value", [])]
        return json.dumps({"total_found": len(events), "events": events})
    except Exception as e:
        log.warning("outlook_list_events error: start=%s %s", start, e)
        return json.dumps({"error": str(e)})


def outlook_get_event(args: dict, **kwargs) -> str:
    """Get full details of a single calendar event including body/notes."""
    event_id = args.get("event_id", "")
    log.debug("outlook_get_event: event_id=%s", event_id)
    try:
        import re
        select = "Id,Subject,Start,End,Location,IsAllDay,IsCancelled,IsOnlineMeeting,OnlineMeeting,Organizer,Attendees,ResponseStatus,Recurrence,Sensitivity,Body,BodyPreview"
        e = _api("GET", f"/me/events/{event_id}?$select={select}")
        result = _fmt_event(e)
        body = e.get("Body", {}).get("Content", "")
        if e.get("Body", {}).get("ContentType", "") == "HTML":
            body = re.sub(r"<[^>]+>", " ", body)
            body = re.sub(r"\s{2,}", " ", body).strip()
        result["body"]         = body[:4000]
        result["body_preview"] = e.get("BodyPreview", "")[:500]
        return json.dumps(result)
    except Exception as e:
        log.warning("outlook_get_event error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_search_events(args: dict, **kwargs) -> str:
    """Search calendar events by keyword."""
    query = args.get("query", "")
    limit = min(int(args.get("limit", 20)), 50)
    log.debug("outlook_search_events: query=%r limit=%s", query, limit)
    try:
        select = "Id,Subject,Start,End,Location,IsAllDay,IsCancelled,IsOnlineMeeting,OnlineMeeting,Organizer,Attendees,ResponseStatus,Recurrence,Sensitivity"
        params = f"$top={limit}&$select={select}&$filter=contains(Subject,'{query}')"
        data = _api("GET", f"/me/calendar/events?{params}")
        events = [_fmt_event(e) for e in data.get("value", [])]
        return json.dumps({"query": query, "total_found": len(events), "events": events})
    except Exception as e:
        log.warning("outlook_search_events error: query=%s %s", query, e)
        return json.dumps({"error": str(e)})


def outlook_create_event(args: dict, **kwargs) -> str:
    """Create a new calendar event."""
    subject    = args.get("subject", "")
    start      = args.get("start", "")
    end        = args.get("end", "")
    attendees  = args.get("attendees", "")
    location   = args.get("location", "")
    body       = args.get("body", "")
    is_online  = bool(args.get("is_online", False))
    is_all_day = bool(args.get("is_all_day", False))
    timezone   = args.get("timezone", _CST)
    log.info("outlook_create_event: subject=%r start=%r", subject, start)
    try:
        payload: dict = {
            "Subject":          subject,
            "Start":            {"DateTime": _dt(start, timezone), "TimeZone": timezone},
            "End":              {"DateTime": _dt(end,   timezone), "TimeZone": timezone},
            "IsAllDay":         is_all_day,
            "IsOnlineMeeting":  is_online,
        }
        if location:
            payload["Location"] = {"DisplayName": location}
        if body:
            payload["Body"] = {"ContentType": "Text", "Content": body}
        if attendees:
            emails = [a.strip() for a in attendees.split(",") if a.strip()]
            payload["Attendees"] = [
                {"EmailAddress": {"Address": em}, "Type": "Required"}
                for em in emails
            ]
        result = _api("POST", "/me/calendar/events", payload)
        ev = _fmt_event(result)
        return json.dumps({"status": "ok", "id": ev["id"], "subject": ev["subject"],
                           "start": ev["start"], "end": ev["end"]})
    except Exception as e:
        log.warning("outlook_create_event error: subject=%s %s", subject, e)
        return json.dumps({"error": str(e)})


def outlook_update_event(args: dict, **kwargs) -> str:
    """Update an existing calendar event."""
    event_id = args.get("event_id", "")
    subject  = args.get("subject", "")
    start    = args.get("start", "")
    end      = args.get("end", "")
    location = args.get("location", "")
    body     = args.get("body", "")
    timezone = args.get("timezone", _CST)
    log.info("outlook_update_event: event_id=%s", event_id)
    try:
        payload: dict = {}
        if subject:
            payload["Subject"] = subject
        if start:
            payload["Start"] = {"DateTime": _dt(start, timezone), "TimeZone": timezone}
        if end:
            payload["End"] = {"DateTime": _dt(end, timezone), "TimeZone": timezone}
        if location:
            payload["Location"] = {"DisplayName": location}
        if body:
            payload["Body"] = {"ContentType": "Text", "Content": body}
        if not payload:
            return json.dumps({"error": "No fields to update — provide at least one of: subject, start, end, location, body"})
        result = _api("PATCH", f"/me/events/{event_id}", payload)
        ev = _fmt_event(result)
        return json.dumps({"status": "ok", "id": ev["id"], "subject": ev["subject"],
                           "start": ev["start"], "end": ev["end"]})
    except Exception as e:
        log.warning("outlook_update_event error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_delete_event(args: dict, **kwargs) -> str:
    """Delete/cancel a calendar event."""
    import urllib.request  # noqa: E401
    event_id = args.get("event_id", "")
    log.info("outlook_delete_event: event_id=%s", event_id)
    try:
        token = _get_access_token()
        url = f"https://outlook.office.com/api/v2.0/me/events/{event_id}"
        req = urllib.request.Request(
            url, method="DELETE",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30):
            pass
        return json.dumps({"status": "ok", "id": event_id})
    except Exception as e:
        log.warning("outlook_delete_event error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_respond_event(args: dict, **kwargs) -> str:
    """Accept, tentatively accept, or decline a calendar event invitation."""
    event_id = args.get("event_id", "")
    response = args.get("response", "")
    comment  = args.get("comment", "")
    log.info("outlook_respond_event: event_id=%s response=%s", event_id, response)
    try:
        valid = {"accept", "tentativelyAccept", "decline"}
        if response not in valid:
            return json.dumps({"error": f"Invalid response '{response}'. Use: {sorted(valid)}"})
        payload: dict = {"SendResponse": True}
        if comment:
            payload["Comment"] = comment
        _api("POST", f"/me/events/{event_id}/{response}", payload)
        return json.dumps({"status": "ok", "id": event_id, "response": response})
    except Exception as e:
        log.warning("outlook_respond_event error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_get_attendee_status(args: dict, **kwargs) -> str:
    """Check who has accepted/declined/pending for a calendar event."""
    event_id = args.get("event_id", "")
    log.debug("outlook_get_attendee_status: event_id=%s", event_id)
    try:
        e = _api("GET", f"/me/events/{event_id}?$select=Subject,Organizer,Attendees")
        attendees = [
            {
                "name":   a.get("EmailAddress", {}).get("Name", ""),
                "email":  a.get("EmailAddress", {}).get("Address", ""),
                "status": a.get("Status", {}).get("Response", "none"),
                "type":   a.get("Type", "required"),
            }
            for a in e.get("Attendees", [])
        ]
        summary: dict = {"accepted": 0, "declined": 0, "tentativelyAccepted": 0, "none": 0}
        for a in attendees:
            s = a["status"]
            summary[s] = summary.get(s, 0) + 1
        return json.dumps({
            "subject":   e.get("Subject", ""),
            "organizer": e.get("Organizer", {}).get("EmailAddress", {}).get("Name", ""),
            "summary":   summary,
            "attendees": attendees,
        })
    except Exception as e:
        log.warning("outlook_get_attendee_status error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_find_meeting_times(args: dict, **kwargs) -> str:
    """Find available meeting times when all attendees are free."""
    attendees        = args.get("attendees", "")
    duration_minutes = int(args.get("duration_minutes", 60))
    start            = args.get("start", "")
    end              = args.get("end", "")
    timezone         = args.get("timezone", _CST)
    log.debug("outlook_find_meeting_times: attendees=%r", attendees)
    try:
        from datetime import datetime, timedelta
        if not start:
            tomorrow = datetime.now() + timedelta(days=1)
            start = tomorrow.strftime("%Y-%m-%dT08:00:00")
        else:
            start = _dt(start, timezone)
        if not end:
            end_dt = datetime.fromisoformat(start) + timedelta(days=5)
            end = end_dt.strftime("%Y-%m-%dT17:00:00")
        else:
            end = _dt(end, timezone)

        emails = [a.strip() for a in attendees.split(",") if a.strip()]
        payload = {
            "Attendees": [{"Type": "Required", "EmailAddress": {"Address": em}} for em in emails],
            "TimeConstraint": {
                "Timeslots": [{"Start": {"DateTime": start, "TimeZone": timezone},
                               "End":   {"DateTime": end,   "TimeZone": timezone}}]
            },
            "MeetingDuration":            f"PT{duration_minutes}M",
            "MaxCandidates":              10,
            "IsOrganizerOptional":        False,
            "ReturnSuggestionReasons":    True,
            "MinimumAttendeePercentage":  100,
        }
        result = _api("POST", "/me/findmeetingtimes", payload)
        suggestions = []
        for s in result.get("MeetingTimeSuggestions", []):
            mt        = s.get("MeetingTimeSlot", {})
            start_str = mt.get("Start", {}).get("DateTime", "")[:16].replace("T", " ")
            end_str   = mt.get("End",   {}).get("DateTime", "")[:16].replace("T", " ")
            avail = [
                {
                    "email":        a.get("Attendee", {}).get("EmailAddress", {}).get("Address", ""),
                    "availability": a.get("Availability", "unknown"),
                }
                for a in s.get("AttendeeAvailability", [])
            ]
            suggestions.append({
                "start":                 start_str,
                "end":                   end_str,
                "confidence":            s.get("Confidence", 0),
                "attendee_availability": avail,
                "suggestion_reason":     s.get("SuggestionReason", ""),
            })
        return json.dumps({
            "duration_minutes":  duration_minutes,
            "total_suggestions": len(suggestions),
            "suggestions":       suggestions,
        })
    except Exception as e:
        log.warning("outlook_find_meeting_times error: attendees=%s %s", attendees, e)
        return json.dumps({"error": str(e)})


def outlook_list_calendars(args: dict, **kwargs) -> str:
    """List all calendars in the mailbox."""
    log.debug("outlook_list_calendars: called")
    try:
        data = _api("GET", "/me/calendars?$select=Id,Name,Owner,Color,IsDefaultCalendar,CanEdit")
        calendars = [
            {
                "id":         c.get("Id", ""),
                "name":       c.get("Name", ""),
                "owner":      c.get("Owner", {}).get("Name", ""),
                "color":      c.get("Color", ""),
                "is_default": c.get("IsDefaultCalendar", False),
                "can_edit":   c.get("CanEdit", False),
            }
            for c in data.get("value", [])
        ]
        return json.dumps({"calendars": calendars})
    except Exception as e:
        log.warning("outlook_list_calendars error: %s", e)
        return json.dumps({"error": str(e)})


def outlook_get_schedule(args: dict, **kwargs) -> str:
    """Get free/busy schedule (authenticated user's own calendar only)."""
    emails   = args.get("emails", "")
    start    = args.get("start", "")
    end      = args.get("end", "")
    timezone = args.get("timezone", _CST)
    log.debug("outlook_get_schedule: emails=%r", emails)
    try:
        from datetime import datetime, timedelta
        if not start:
            start = datetime.now().strftime("%Y-%m-%dT08:00:00")
        else:
            start = _dt(start, timezone)
        if not end:
            end_dt = datetime.fromisoformat(start) + timedelta(days=1)
            end = end_dt.strftime("%Y-%m-%dT18:00:00")
        else:
            end = _dt(end, timezone)

        email_list = [e.strip() for e in emails.split(",") if e.strip()]
        schedules = []
        for email in email_list:
            params = (
                f"$top=50&$select=Subject,Start,End,ShowAs"
                f"&startDateTime={start}&endDateTime={end}"
            )
            try:
                s_data = _api("GET", f"/me/calendarView?{params}")
                items = [
                    {
                        "start":   i.get("Start", {}).get("DateTime", "")[:16].replace("T", " "),
                        "end":     i.get("End",   {}).get("DateTime", "")[:16].replace("T", " "),
                        "status":  i.get("ShowAs", "Busy"),
                        "subject": i.get("Subject", ""),
                    }
                    for i in s_data.get("value", [])
                ]
                schedules.append({"email": email, "busy_blocks": items})
            except Exception:
                schedules.append({
                    "email": email,
                    "note":  "Free/busy for other users: use outlook_find_meeting_times instead.",
                    "busy_blocks": [],
                })
        return json.dumps({"schedules": schedules})
    except Exception as e:
        log.warning("outlook_get_schedule error: emails=%s %s", emails, e)
        return json.dumps({"error": str(e)})


def outlook_add_attendees(args: dict, **kwargs) -> str:
    """Add attendees to an existing event."""
    event_id  = args.get("event_id", "")
    attendees = args.get("attendees", "")
    log.info("outlook_add_attendees: event_id=%s attendees=%r", event_id, attendees)
    try:
        existing      = _api("GET", f"/me/events/{event_id}?$select=Attendees")
        current       = existing.get("Attendees", [])
        current_emails = {a.get("EmailAddress", {}).get("Address", "").lower() for a in current}
        new_emails    = [e.strip() for e in attendees.split(",") if e.strip()]
        to_add        = [em for em in new_emails if em.lower() not in current_emails]
        if not to_add:
            return json.dumps({"status": "ok", "id": event_id, "added": [], "note": "All attendees already on the event"})
        updated = current + [{"EmailAddress": {"Address": em}, "Type": "Required"} for em in to_add]
        _api("PATCH", f"/me/events/{event_id}", {"Attendees": updated})
        return json.dumps({"status": "ok", "id": event_id, "added": to_add})
    except Exception as e:
        log.warning("outlook_add_attendees error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})


def outlook_remove_attendees(args: dict, **kwargs) -> str:
    """Remove attendees from an existing event."""
    event_id  = args.get("event_id", "")
    attendees = args.get("attendees", "")
    log.info("outlook_remove_attendees: event_id=%s attendees=%r", event_id, attendees)
    try:
        existing    = _api("GET", f"/me/events/{event_id}?$select=Attendees")
        current     = existing.get("Attendees", [])
        remove_set  = {e.strip().lower() for e in attendees.split(",") if e.strip()}
        kept        = [a for a in current if a.get("EmailAddress", {}).get("Address", "").lower() not in remove_set]
        removed     = [a.get("EmailAddress", {}).get("Address", "") for a in current
                       if a.get("EmailAddress", {}).get("Address", "").lower() in remove_set]
        _api("PATCH", f"/me/events/{event_id}", {"Attendees": kept})
        return json.dumps({"status": "ok", "id": event_id, "removed": removed})
    except Exception as e:
        log.warning("outlook_remove_attendees error: event_id=%s %s", event_id, e)
        return json.dumps({"error": str(e)})
