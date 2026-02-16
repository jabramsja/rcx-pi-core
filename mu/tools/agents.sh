#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/audits/agents.sh
exec "$(dirname "$0")/audits/agents.sh" "$@"
