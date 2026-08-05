"""
Shared OAuth2 PKCE constants for renewing the Outlook refresh token.

These values were reverse-engineered from Outlook Web's own MSAL auth flow
(HAR capture on 2026-07-29) — see docs/token-renewal-pkce.md for the full
derivation and why other client_id/scope/redirect_uri combinations fail.

If Microsoft changes Outlook Web's app registration, re-capture a HAR file
of a fresh outlook.cloud.microsoft login and update these values.
"""

TENANT_ID = "16532572-d567-4d67-8727-f12f7bb6aed3"
CLIENT_ID = "9199bf20-a13f-4107-85dc-02114787ef48"
SCOPE = "https://outlook.office.com/.default openid profile offline_access"
REDIRECT_URI = "https://outlook.cloud.microsoft/mail/"

# Required on the token exchange request or Azure AD rejects with
# AADSTS9002327 ("Tokens issued for the 'Single-Page Application'
# client-type may only be redeemed via cross-origin requests").
TOKEN_EXCHANGE_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://outlook.cloud.microsoft",
    "Referer": "https://outlook.cloud.microsoft/mail/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}
