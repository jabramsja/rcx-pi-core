#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/audits/audit_all.sh
exec "$(dirname "$0")/audits/audit_all.sh" "$@"
