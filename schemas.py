"""
Tool schemas for the outlook plugin — what the LLM sees.

Each constant is a JSON-Schema-style tool definition passed to
ctx.register_tool(schema=...) in __init__.py.
"""

# ── Ping ──────────────────────────────────────────────────────────────────────

PING = {
    "name": "outlook_ping",
    "description": (
        "Check connectivity and authentication to the Outlook REST API. "
        "Returns: {\"status\": \"ok\", \"email\": \"...\", \"display_name\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

# ── Email ─────────────────────────────────────────────────────────────────────

LIST_EMAILS = {
    "name": "outlook_list_emails",
    "description": (
        "List recent emails in a mailbox folder. "
        "Returns: {\"folder\": \"...\", \"total_found\": N, \"emails\": [{\"id\": \"...\", \"subject\": \"...\", \"from\": \"...\", \"date\": \"...\", \"unread\": bool}]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "folder":      {"type": "string",  "description": "Folder name (default: \"inbox\"). Use outlook_list_folders to see all."},
            "limit":       {"type": "integer", "description": "Max emails to return (default 20, max 50)."},
            "unread_only": {"type": "boolean", "description": "If true, only return unread messages (default false)."},
        },
        "required": [],
    },
}

READ_EMAIL = {
    "name": "outlook_read_email",
    "description": (
        "Read the full content of an email by its ID. "
        "Returns: {\"id\": \"...\", \"subject\": \"...\", \"from\": \"...\", \"to\": \"...\", \"cc\": \"...\", \"date\": \"...\", \"body\": \"...\", \"attachments\": [...]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_id": {"type": "string", "description": "The email ID (from outlook_list_emails or outlook_search_emails)."},
        },
        "required": ["email_id"],
    },
}

SEARCH_EMAILS = {
    "name": "outlook_search_emails",
    "description": (
        "Search emails by keyword, sender, or subject. "
        "Prefix with 'from:' to search by sender, 'subject:' to search subject line, or plain text for full-text search. "
        "Returns: same shape as outlook_list_emails plus \"query\" field, or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query":  {"type": "string",  "description": "Search term. Examples: \"from:boss@company.com\", \"subject:migration\", \"quarterly report\"."},
            "folder": {"type": "string",  "description": "Folder to search (default: \"inbox\")."},
            "limit":  {"type": "integer", "description": "Max results (default 20, max 50)."},
        },
        "required": ["query"],
    },
}

LIST_FOLDERS = {
    "name": "outlook_list_folders",
    "description": (
        "List all folders in the mailbox. "
        "Returns: {\"folders\": [{\"id\": \"...\", \"name\": \"...\", \"unread_count\": N, \"total_count\": N}]} or {\"error\": \"...\"}."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

MARK_READ = {
    "name": "outlook_mark_read",
    "description": (
        "Mark an email as read. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_id": {"type": "string", "description": "The email ID (from outlook_list_emails)."},
        },
        "required": ["email_id"],
    },
}

MOVE_EMAIL = {
    "name": "outlook_move_email",
    "description": (
        "Move an email to another folder. "
        "Common destination values: \"inbox\", \"deleteditems\", \"junkemail\", \"archive\". "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"moved_to\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_id":           {"type": "string", "description": "The email ID (from outlook_list_emails)."},
            "destination_folder": {"type": "string", "description": "Target folder name or ID (use outlook_list_folders to see options)."},
        },
        "required": ["email_id", "destination_folder"],
    },
}

SEND_EMAIL = {
    "name": "outlook_send_email",
    "description": (
        "Compose and send a new email on the user's behalf. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "to":           {"type": "string",  "description": "Comma-separated recipient email addresses."},
            "subject":      {"type": "string",  "description": "Email subject line."},
            "body":         {"type": "string",  "description": "Email body (plain text by default; set body_type=\"HTML\" for HTML)."},
            "cc":           {"type": "string",  "description": "Comma-separated CC addresses (optional)."},
            "bcc":          {"type": "string",  "description": "Comma-separated BCC addresses (optional)."},
            "body_type":    {"type": "string",  "description": "\"Text\" (default) or \"HTML\"."},
            "save_to_sent": {"type": "boolean", "description": "Save a copy to Sent Items (default true)."},
        },
        "required": ["to", "subject", "body"],
    },
}

REPLY_EMAIL = {
    "name": "outlook_reply_email",
    "description": (
        "Reply to an existing email. "
        "Returns: {\"status\": \"ok\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_id":  {"type": "string",  "description": "The email ID (from outlook_list_emails or outlook_search_emails)."},
            "body":      {"type": "string",  "description": "The reply body text."},
            "reply_all": {"type": "boolean", "description": "If true, reply to all recipients. Default false (sender only)."},
            "body_type": {"type": "string",  "description": "\"Text\" (default) or \"HTML\"."},
        },
        "required": ["email_id", "body"],
    },
}

FORWARD_EMAIL = {
    "name": "outlook_forward_email",
    "description": (
        "Forward an existing email to one or more recipients. "
        "Returns: {\"status\": \"ok\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "email_id": {"type": "string", "description": "The email ID (from outlook_list_emails or outlook_search_emails)."},
            "to":       {"type": "string", "description": "Comma-separated recipient email addresses."},
            "comment":  {"type": "string", "description": "Optional message to prepend above the forwarded content."},
        },
        "required": ["email_id", "to"],
    },
}

# ── Calendar ──────────────────────────────────────────────────────────────────

LIST_EVENTS = {
    "name": "outlook_list_events",
    "description": (
        "List calendar events in a date range. "
        "Range phrases like 'this week' or 'last month' automatically set both start AND end — pass only start in that case. "
        "Returns: {\"events\": [...], \"total_found\": N} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "start":       {"type": "string",  "description": "When to start listing. Prefer natural-language: 'today', 'this week', 'last month', 'next Monday'. Range phrases like 'this week' auto-set both start AND end. ISO also accepted. Default: today at midnight."},
            "end":         {"type": "string",  "description": "When to stop. Natural-language or ISO. Leave blank when start is a range phrase. Default: 7 days after start."},
            "calendar_id": {"type": "string",  "description": "Calendar ID or \"calendar\" for primary (default: \"calendar\")."},
            "limit":       {"type": "integer", "description": "Max events to return (default 20, max 50)."},
        },
        "required": [],
    },
}

GET_EVENT = {
    "name": "outlook_get_event",
    "description": (
        "Get full details of a single calendar event including body/notes. "
        "Returns: full event dict including body/notes, attendee responses, recurrence info, or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event ID (from outlook_list_events or outlook_search_events)."},
        },
        "required": ["event_id"],
    },
}

SEARCH_EVENTS = {
    "name": "outlook_search_events",
    "description": (
        "Search calendar events by keyword (subject, location, body). "
        "Returns: {\"events\": [...], \"total_found\": N} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string",  "description": "Search term — matched against subject, location, and body."},
            "limit": {"type": "integer", "description": "Max results (default 20, max 50)."},
        },
        "required": ["query"],
    },
}

CREATE_EVENT = {
    "name": "outlook_create_event",
    "description": (
        "Create a new calendar event. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"subject\": \"...\", \"start\": \"...\", \"end\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subject":    {"type": "string",  "description": "Event title/subject."},
            "start":      {"type": "string",  "description": "Start datetime. Prefer natural-language: 'next Monday at 10am', 'tomorrow at 2pm'. ISO also accepted."},
            "end":        {"type": "string",  "description": "End datetime. Same format as start."},
            "attendees":  {"type": "string",  "description": "Comma-separated email addresses to invite (optional)."},
            "location":   {"type": "string",  "description": "Location string (room name, address, or Teams link)."},
            "body":       {"type": "string",  "description": "Event description/notes (plain text)."},
            "is_online":  {"type": "boolean", "description": "If true, create as an online Teams meeting (default false)."},
            "is_all_day": {"type": "boolean", "description": "If true, create as all-day event (default false)."},
            "timezone":   {"type": "string",  "description": "Timezone name (default: \"Central Standard Time\")."},
        },
        "required": ["subject", "start", "end"],
    },
}

UPDATE_EVENT = {
    "name": "outlook_update_event",
    "description": (
        "Update (rename, reschedule, or edit notes/location) an existing calendar event. "
        "Only provided fields are changed. WARNING: body replaces the entire event description. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"subject\": \"...\", \"start\": \"...\", \"end\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event ID (from outlook_list_events or outlook_search_events)."},
            "subject":  {"type": "string", "description": "New title/subject (leave blank to keep unchanged)."},
            "start":    {"type": "string", "description": "New start datetime. Natural-language preferred. Leave blank to keep unchanged."},
            "end":      {"type": "string", "description": "New end datetime. Same format as start. Leave blank to keep."},
            "location": {"type": "string", "description": "New location (leave blank to keep)."},
            "body":     {"type": "string", "description": "New body/notes (leave blank to keep — WARNING: replaces entire body)."},
            "timezone": {"type": "string", "description": "Timezone for start/end if provided (default: \"Central Standard Time\")."},
        },
        "required": ["event_id"],
    },
}

DELETE_EVENT = {
    "name": "outlook_delete_event",
    "description": (
        "Delete (cancel) a calendar event. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event ID (from outlook_list_events)."},
        },
        "required": ["event_id"],
    },
}

RESPOND_EVENT = {
    "name": "outlook_respond_event",
    "description": (
        "Accept, tentatively accept, or decline a calendar event invitation. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"response\": \"...\"} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event ID (from outlook_list_events)."},
            "response": {"type": "string", "description": "One of \"accept\", \"tentativelyAccept\", or \"decline\"."},
            "comment":  {"type": "string", "description": "Optional message to include with the response."},
        },
        "required": ["event_id", "response"],
    },
}

GET_ATTENDEE_STATUS = {
    "name": "outlook_get_attendee_status",
    "description": (
        "Check who has accepted, declined, or not yet responded to a calendar event. "
        "Returns: {\"subject\": \"...\", \"organizer\": \"...\", \"summary\": {\"accepted\": N, \"declined\": N, \"tentative\": N, \"none\": N}, \"attendees\": [...]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string", "description": "The event ID (from outlook_list_events or outlook_search_events)."},
        },
        "required": ["event_id"],
    },
}

FIND_MEETING_TIMES = {
    "name": "outlook_find_meeting_times",
    "description": (
        "Find available meeting times when all attendees are free (free/busy lookup). "
        "Returns: {\"suggestions\": [{\"start\": \"...\", \"end\": \"...\", \"confidence\": N, \"attendee_availability\": [...]}]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "attendees":        {"type": "string",  "description": "Comma-separated email addresses of required attendees."},
            "duration_minutes": {"type": "integer", "description": "Desired meeting duration in minutes (default: 60)."},
            "start":            {"type": "string",  "description": "Start of search window. Natural-language preferred (e.g. 'tomorrow', 'next Monday'). Default: tomorrow 8am."},
            "end":              {"type": "string",  "description": "End of search window. Natural-language or ISO. Default: 5 days after start, up to 5pm each day."},
            "timezone":         {"type": "string",  "description": "Timezone for the search window (default: \"Central Standard Time\")."},
        },
        "required": ["attendees"],
    },
}

LIST_CALENDARS = {
    "name": "outlook_list_calendars",
    "description": (
        "List all calendars in the mailbox (primary, shared, group, etc.). "
        "Returns: {\"calendars\": [{\"id\": \"...\", \"name\": \"...\", \"owner\": \"...\", \"color\": \"...\", \"is_default\": bool}]} or {\"error\": \"...\"}."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

GET_SCHEDULE = {
    "name": "outlook_get_schedule",
    "description": (
        "Get the free/busy schedule for one or more people (view their availability blocks). "
        "Note: Due to Outlook REST v2 limitations, this tool only reads the authenticated user's own calendar. "
        "For other attendees' availability, use outlook_find_meeting_times. "
        "Returns: {\"schedules\": [{\"email\": \"...\", \"availability\": [...]}]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "emails":   {"type": "string", "description": "Comma-separated email addresses to check."},
            "start":    {"type": "string", "description": "Start of window. Natural-language preferred. Default: today at 8am."},
            "end":      {"type": "string", "description": "End of window. Natural-language or ISO. Default: 1 day after start."},
            "timezone": {"type": "string", "description": "Timezone (default: \"Central Standard Time\")."},
        },
        "required": ["emails"],
    },
}

ADD_ATTENDEES = {
    "name": "outlook_add_attendees",
    "description": (
        "Add one or more attendees to an existing event. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"added\": [...]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id":  {"type": "string", "description": "The event ID."},
            "attendees": {"type": "string", "description": "Comma-separated email addresses to add."},
        },
        "required": ["event_id", "attendees"],
    },
}

REMOVE_ATTENDEES = {
    "name": "outlook_remove_attendees",
    "description": (
        "Remove one or more attendees from an existing event. "
        "Returns: {\"status\": \"ok\", \"id\": \"...\", \"removed\": [...]} or {\"error\": \"...\"}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "event_id":  {"type": "string", "description": "The event ID."},
            "attendees": {"type": "string", "description": "Comma-separated email addresses to remove."},
        },
        "required": ["event_id", "attendees"],
    },
}
