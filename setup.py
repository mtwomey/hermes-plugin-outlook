#!/usr/bin/env python3
"""
setup.py for hermes-plugin-outlook.

Usage:
    python setup.py install       # install plugin into Hermes
    python setup.py uninstall     # remove plugin from Hermes
    python setup.py status        # show installation status
    python setup.py credentials   # manage credentials
    python setup.py log           # manage log level
    python setup.py audit         # check compliance
    python setup.py test          # run smoke tests
"""
from pathlib import Path
from hermes_plugin_core.setup_cli import SetupCLI, PluginConfig

config = PluginConfig(
    plugin_key="outlook",
    service="hermes-outlook",
    repo_dir=Path(__file__).parent.resolve(),
    keys=["email", "tenant_id", "client_id", "refresh_token"],
    cred_prompts={
        "email":         ("Your Outlook email address (e.g. mattwo01@roberthalf.com)", "mattwo01@roberthalf.com", False),
        "tenant_id":     ("Azure AD Tenant ID (extract from browser — see README)", "", False),
        "client_id":     ("OAuth2 Client ID (extract from browser — see README)", "", False),
        "refresh_token": ("Outlook refresh token (extract from browser MSAL cache — see README)", "", True),
    },
    requirements=[],
)

if __name__ == "__main__":
    SetupCLI(config).run()
