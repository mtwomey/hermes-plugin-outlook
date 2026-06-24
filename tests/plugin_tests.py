"""
Smoke tests for hermes-plugin-outlook.
Run with: python setup.py test
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes_plugin_core.testing import TestSuite, expect_ok


def register_tests(suite: TestSuite):
    suite.add("ping", test_ping)
    suite.add("list folders", test_list_folders)
    suite.add("list inbox (recent)", test_list_inbox)
    suite.add("list calendars", test_list_calendars)
    suite.add("list events (upcoming)", test_list_events)
    suite.add("search events", test_search_events)
    suite.add("find meeting times", test_find_meeting_times)


def test_ping():
    from tools import outlook_ping
    expect_ok(outlook_ping({}))


def test_list_folders():
    from tools import outlook_list_folders
    result = json.loads(outlook_list_folders({}))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "folders" in result, f"expected 'folders' key"


def test_list_inbox():
    from tools import outlook_list_emails
    result = json.loads(outlook_list_emails({"folder": "inbox", "limit": 3}))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "emails" in result, f"expected 'emails' key"


def test_list_calendars():
    from tools import outlook_list_calendars
    result = json.loads(outlook_list_calendars({}))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "calendars" in result, f"expected 'calendars' key"
    assert len(result["calendars"]) > 0, "expected at least one calendar"


def test_list_events():
    from tools import outlook_list_events
    result = json.loads(outlook_list_events({"start": "today", "limit": 5}))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "events" in result, f"expected 'events' key"


def test_search_events():
    from tools import outlook_search_events
    result = json.loads(outlook_search_events({"query": "meeting", "limit": 3}))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "events" in result, f"expected 'events' key"


def test_find_meeting_times():
    from tools import outlook_find_meeting_times
    result = json.loads(outlook_find_meeting_times({
        "attendees": "mattwo01@roberthalf.com",
        "duration_minutes": 30,
        "start": "tomorrow",
    }))
    assert "error" not in result, f"error: {result.get('error')}"
    assert "suggestions" in result, f"expected 'suggestions' key"
