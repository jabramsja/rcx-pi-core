#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/audits/audit_fast.sh
exec "$(dirname "$0")/audits/audit_fast.sh" "$@"
