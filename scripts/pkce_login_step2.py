#!/usr/bin/env python3
"""
Step 2 of manual-paste PKCE login: takes the full redirect URL the user
copied from the browser address bar after signing in, extracts the auth
code, exchanges it for tokens, and prints the resulting credential JSON.

Usage: python3 scripts/pkce_login_step2.py "<pasted URL>"
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pkce_config import TOKEN_EXCHANGE_HEADERS

STATE_FILE = "/tmp/hermes_outlook_pkce_state.json"


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: pkce_login_step2.py '<pasted redirect URL>'"}))
        return

    pasted_url = sys.argv[1]

    with open(STATE_FILE) as f:
        state_data = json.load(f)

    parsed = urllib.parse.urlparse(pasted_url)
    # Auth response may land in the query string OR the fragment (after '#')
    # depending on response_mode; check both.
    params = urllib.parse.parse_qs(parsed.query)
    if "code" not in params and parsed.fragment:
        params = urllib.parse.parse_qs(parsed.fragment)

    if "error" in params:
        print(json.dumps({"error": params.get("error_description", params["error"])[0]}))
        return
    if "code" not in params:
        print(json.dumps({"error": "No 'code' parameter found in pasted URL"}))
        return

    code = params["code"][0]
    returned_state = params.get("state", [None])[0]
    if returned_state != state_data["state"]:
        print(json.dumps({"error": "State mismatch — possible stale/reused URL. Re-run step1."}))
        return

    token_data = urllib.parse.urlencode({
        "client_id": state_data["client_id"],
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": state_data["redirect_uri"],
        "code_verifier": state_data["verifier"],
        "scope": state_data["scope"],
    }).encode()

    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{state_data['tenant_id']}/oauth2/v2.0/token",
        data=token_data, method="POST",
        headers=TOKEN_EXCHANGE_HEADERS,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tok = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": e.read().decode()}))
        return

    out = {
        "tenant_id": state_data["tenant_id"],
        "client_id": state_data["client_id"],
        "refresh_token": tok.get("refresh_token", ""),
        "access_token_preview": tok.get("access_token", "")[:30] + "...",
        "expires_in": tok.get("expires_in"),
        "email": "mattwo01@roberthalf.com",
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
