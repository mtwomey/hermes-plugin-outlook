"""
hermes-plugin-outlook — Microsoft Outlook (M365) email and calendar plugin for Hermes Agent.

Entry point called by Hermes when the plugin is loaded.
Registers all tool schemas and their handler functions with the plugin context.
"""

import logging
import os
import sys
from pathlib import Path

from . import schemas, tools

# Make scripts/ available for keychain_utils, logging_utils
_SCRIPTS_DIR = Path(__file__).parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_SKILL_MD = Path(__file__).parent / "SKILL.md"


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


def register(ctx):
    """
    Called by Hermes when the plugin is loaded.
    Registers all tool schemas + handlers with the plugin context.
    """
    from logging_utils import setup_logging
    log = setup_logging(PLUGIN_NAME, _get_log_level())
    log.debug("outlook plugin: register() called")

    # ── Register tools ────────────────────────────────────────────────────────
    pairs = [
        (schemas.PING,               tools.outlook_ping),
        # Email
        (schemas.LIST_EMAILS,        tools.outlook_list_emails),
        (schemas.READ_EMAIL,         tools.outlook_read_email),
        (schemas.SEARCH_EMAILS,      tools.outlook_search_emails),
        (schemas.LIST_FOLDERS,       tools.outlook_list_folders),
        (schemas.MARK_READ,          tools.outlook_mark_read),
        (schemas.MOVE_EMAIL,         tools.outlook_move_email),
        (schemas.SEND_EMAIL,         tools.outlook_send_email),
        (schemas.REPLY_EMAIL,        tools.outlook_reply_email),
        (schemas.FORWARD_EMAIL,      tools.outlook_forward_email),
        # Calendar
        (schemas.LIST_EVENTS,        tools.outlook_list_events),
        (schemas.GET_EVENT,          tools.outlook_get_event),
        (schemas.SEARCH_EVENTS,      tools.outlook_search_events),
        (schemas.CREATE_EVENT,       tools.outlook_create_event),
        (schemas.UPDATE_EVENT,       tools.outlook_update_event),
        (schemas.DELETE_EVENT,       tools.outlook_delete_event),
        (schemas.RESPOND_EVENT,      tools.outlook_respond_event),
        (schemas.GET_ATTENDEE_STATUS,  tools.outlook_get_attendee_status),
        (schemas.FIND_MEETING_TIMES,   tools.outlook_find_meeting_times),
        (schemas.LIST_CALENDARS,     tools.outlook_list_calendars),
        (schemas.GET_SCHEDULE,       tools.outlook_get_schedule),
        (schemas.ADD_ATTENDEES,      tools.outlook_add_attendees),
        (schemas.REMOVE_ATTENDEES,   tools.outlook_remove_attendees),
    ]

    for schema, handler in pairs:
        ctx.register_tool(name=schema["name"], toolset=PLUGIN_NAME, schema=schema, handler=handler)
        log.debug("outlook: registered tool %s", schema["name"])

    # ── Register bundled skill ────────────────────────────────────────────────
    if _SKILL_MD.exists():
        ctx.register_skill(PLUGIN_NAME, _SKILL_MD)

    log.info("outlook plugin: %d tools registered", len(pairs))
