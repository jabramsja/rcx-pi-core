#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/checks/check_js_debt.sh
exec "$(dirname "$0")/checks/check_js_debt.sh" "$@"
