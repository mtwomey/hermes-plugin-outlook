"""
hermes-plugin-outlook — Microsoft Outlook (M365) email and calendar plugin.
Hermes calls register(ctx) once at startup.
"""
from pathlib import Path
from hermes_plugin_core import setup_logging
from hermes_plugin_core.config import get_log_level
from . import schemas, tools

_SKILL_MD = Path(__file__).parent / "SKILL.md"


def register(ctx):
    setup_logging("outlook", get_log_level("outlook"))

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
        ctx.register_tool(name=schema["name"], toolset="outlook", schema=schema, handler=handler)

    if _SKILL_MD.exists():
        ctx.register_skill("outlook", _SKILL_MD)
