#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/audits/audit_semantic_purity.sh
exec "$(dirname "$0")/audits/audit_semantic_purity.sh" "$@"
