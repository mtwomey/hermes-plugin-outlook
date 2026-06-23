"""
hermes-plugin-outlook — Microsoft Outlook (M365) email and calendar plugin for Hermes Agent.

Entry point called by Hermes when the plugin is loaded.
Registers all tool schemas and their handler functions with the plugin context.
"""

import logging
import os
import sys
from pathlib import Path

# Make scripts/ available for keychain_utils, date_utils, logging_utils
sys.path.insert(0, str(Path(__file__).parent / "scripts"))


PLUGIN_NAME = "outlook"


def _get_log_level() -> str:
    """Read log level from plugins.config.outlook.log_level in config.yaml."""
    try:
        hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        config_file = hermes_home / "config.yaml"
        if not config_file.exists():
            return "WARNING"
        from ruamel.yaml import YAML
        yaml = YAML()
        with open(config_file) as f:
            data = yaml.load(f)
        plugins = data.get("plugins") or {}
        config  = plugins.get("config") or {}
        plugin  = config.get(PLUGIN_NAME) or {}
        return plugin.get("log_level", "WARNING")
    except Exception:
        return "WARNING"


def setup(ctx):
    """
    Called by Hermes when the plugin is loaded.
    Registers all tool schemas + handlers with the plugin context.
    """
    from logging_utils import setup_logging
    log = setup_logging(PLUGIN_NAME, _get_log_level())
    log.debug("outlook plugin: setup() called")

    # ── Import schemas and tools ──────────────────────────────────────────────
    from schemas import (
        PING,
        LIST_EMAILS, READ_EMAIL, SEARCH_EMAILS, LIST_FOLDERS,
        MARK_READ, MOVE_EMAIL, SEND_EMAIL, REPLY_EMAIL, FORWARD_EMAIL,
        LIST_EVENTS, GET_EVENT, SEARCH_EVENTS, CREATE_EVENT, UPDATE_EVENT,
        DELETE_EVENT, RESPOND_EVENT, GET_ATTENDEE_STATUS, FIND_MEETING_TIMES,
        LIST_CALENDARS, GET_SCHEDULE, ADD_ATTENDEES, REMOVE_ATTENDEES,
    )
    from tools import (
        outlook_ping,
        outlook_list_emails, outlook_read_email, outlook_search_emails, outlook_list_folders,
        outlook_mark_read, outlook_move_email, outlook_send_email, outlook_reply_email,
        outlook_forward_email,
        outlook_list_events, outlook_get_event, outlook_search_events, outlook_create_event,
        outlook_update_event, outlook_delete_event, outlook_respond_event,
        outlook_get_attendee_status, outlook_find_meeting_times,
        outlook_list_calendars, outlook_get_schedule, outlook_add_attendees, outlook_remove_attendees,
    )

    # ── Register tools ────────────────────────────────────────────────────────
    pairs = [
        (PING,               outlook_ping),
        # Email
        (LIST_EMAILS,        outlook_list_emails),
        (READ_EMAIL,         outlook_read_email),
        (SEARCH_EMAILS,      outlook_search_emails),
        (LIST_FOLDERS,       outlook_list_folders),
        (MARK_READ,          outlook_mark_read),
        (MOVE_EMAIL,         outlook_move_email),
        (SEND_EMAIL,         outlook_send_email),
        (REPLY_EMAIL,        outlook_reply_email),
        (FORWARD_EMAIL,      outlook_forward_email),
        # Calendar
        (LIST_EVENTS,        outlook_list_events),
        (GET_EVENT,          outlook_get_event),
        (SEARCH_EVENTS,      outlook_search_events),
        (CREATE_EVENT,       outlook_create_event),
        (UPDATE_EVENT,       outlook_update_event),
        (DELETE_EVENT,       outlook_delete_event),
        (RESPOND_EVENT,      outlook_respond_event),
        (GET_ATTENDEE_STATUS,  outlook_get_attendee_status),
        (FIND_MEETING_TIMES,   outlook_find_meeting_times),
        (LIST_CALENDARS,     outlook_list_calendars),
        (GET_SCHEDULE,       outlook_get_schedule),
        (ADD_ATTENDEES,      outlook_add_attendees),
        (REMOVE_ATTENDEES,   outlook_remove_attendees),
    ]

    for schema, handler in pairs:
        ctx.register_tool(schema=schema, handler=handler)
        log.debug("outlook: registered tool %s", schema["name"])

    log.info("outlook plugin: %d tools registered", len(pairs))
