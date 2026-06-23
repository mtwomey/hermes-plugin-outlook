#!/usr/bin/env bash
# Thin launcher — delegates to setup.py under the Hermes venv Python.
exec "$HOME/.hermes/hermes-agent/venv/bin/python3" "$(dirname "${BASH_SOURCE[0]}")/setup.py" "$@"
