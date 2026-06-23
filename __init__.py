"""
Hermes plugin entry point for the outlook plugin.

Hermes calls register(ctx) once at startup. Keep this file thin —
all logic lives in tools.py and schemas.py.
"""

import logging
import os
from pathlib import Path

from . import schemas, tools

_SKILL_MD  = Path(__file__).parent / "SKILL.md"
_PLUGIN_DIR = Path(__file__).parent


def _get_log_level() -> str:
    """
    Read plugins.config.outlook.log_level from config.yaml.
    Falls back to WARNING on any error.

    Set via: ./setup.sh log debug|quiet
    Applied at Hermes startup — requires restart to take effect.
    """
    try:
        from ruamel.yaml import YAML
        hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        config_yaml = hermes_home / "config.yaml"
        if not config_yaml.exists():
            return "WARNING"
        yaml = YAML()
        with open(config_yaml) as f:
            data = yaml.load(f) or {}
        plugins = data.get("plugins") or {}
        config  = plugins.get("config") or {}
        plugin  = config.get("outlook") or {}
        return str(plugin.get("log_level") or "WARNING").upper()
    except Exception:
        return "WARNING"


def register(ctx) -> None:
    """Register all outlook tools and the bundled skill with the Hermes plugin context."""

    # Configure logging — level set by `./setup.sh log debug|quiet`
    # Reads plugins.config.outlook.log_level from config.yaml.
    import sys as _sys
    _scripts = Path(__file__).parent / "scripts"
    if str(_scripts) not in _sys.path:
        _sys.path.insert(0, str(_scripts))
    from logging_utils import setup_logging  # noqa: E402
    setup_logging("outlook", _get_log_level())

    # ------------------------------------------------------------------
    # IMPORTANT: ctx.register_tool() requires BOTH name= and toolset=
    # as positional-or-keyword arguments. Passing schema= alone causes
    # a silent failure — the plugin appears "enabled" but registers
    # ZERO tools. Always use the explicit form below.
    # ------------------------------------------------------------------
    _REGISTRY = [
        (schemas.PING,                 tools.outlook_ping),
        # Email
        (schemas.LIST_EMAILS,          tools.outlook_list_emails),
        (schemas.READ_EMAIL,           tools.outlook_read_email),
        (schemas.SEARCH_EMAILS,        tools.outlook_search_emails),
        (schemas.LIST_FOLDERS,         tools.outlook_list_folders),
        (schemas.MARK_READ,            tools.outlook_mark_read),
        (schemas.MOVE_EMAIL,           tools.outlook_move_email),
        (schemas.SEND_EMAIL,           tools.outlook_send_email),
        (schemas.REPLY_EMAIL,          tools.outlook_reply_email),
        (schemas.FORWARD_EMAIL,        tools.outlook_forward_email),
        # Calendar
        (schemas.LIST_EVENTS,          tools.outlook_list_events),
        (schemas.GET_EVENT,            tools.outlook_get_event),
        (schemas.SEARCH_EVENTS,        tools.outlook_search_events),
        (schemas.CREATE_EVENT,         tools.outlook_create_event),
        (schemas.UPDATE_EVENT,         tools.outlook_update_event),
        (schemas.DELETE_EVENT,         tools.outlook_delete_event),
        (schemas.RESPOND_EVENT,        tools.outlook_respond_event),
        (schemas.GET_ATTENDEE_STATUS,  tools.outlook_get_attendee_status),
        (schemas.FIND_MEETING_TIMES,   tools.outlook_find_meeting_times),
        (schemas.LIST_CALENDARS,       tools.outlook_list_calendars),
        (schemas.GET_SCHEDULE,         tools.outlook_get_schedule),
        (schemas.ADD_ATTENDEES,        tools.outlook_add_attendees),
        (schemas.REMOVE_ATTENDEES,     tools.outlook_remove_attendees),
    ]

    for schema, handler in _REGISTRY:
        ctx.register_tool(
            name=schema["name"],  # ← REQUIRED — do not omit
            toolset="outlook",    # ← REQUIRED — do not omit
            schema=schema,
            handler=handler,
        )

    # Register the bundled skill so agents can load it via
    # skill_view(name="outlook:outlook")
    # No ~/.hermes/skills/ symlink needed.
    if _SKILL_MD.exists():
        ctx.register_skill("outlook", _SKILL_MD)
