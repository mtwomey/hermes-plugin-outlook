#!/usr/bin/env python3
"""
Step 1 of manual-paste PKCE login: generate the auth URL and save the PKCE
verifier + state to a temp file. Print the URL, user signs in in a real
browser, then copies the FULL resulting URL (from the address bar, even
though the page itself is just a blank "you have signed in" confirmation)
and passes it to pkce_login_step2.py.
"""
import base64
import hashlib
import json
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pkce_config import TENANT_ID, CLIENT_ID, SCOPE, REDIRECT_URI

STATE_FILE = "/tmp/hermes_outlook_pkce_state.json"


def main():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    with open(STATE_FILE, "w") as f:
        json.dump({
            "verifier": verifier,
            "state": state,
            "tenant_id": TENANT_ID,
            "client_id": CLIENT_ID,
            "scope": SCOPE,
            "redirect_uri": REDIRECT_URI,
        }, f)

    auth_params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "fragment",
        "scope": SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    auth_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize?{auth_params}"

    print(f"Opening browser to sign in...\n{auth_url}\n")
    print("After signing in, copy the FULL URL from your browser's address bar")
    print("(the params will be after a '#' since response_mode=fragment)")
    print("and pass it to pkce_login_step2.py")
    webbrowser.open(auth_url)


if __name__ == "__main__":
    main()
