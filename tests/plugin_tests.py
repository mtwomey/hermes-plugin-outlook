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
