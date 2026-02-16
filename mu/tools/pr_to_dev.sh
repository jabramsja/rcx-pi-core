#!/usr/bin/env bash
# Backward-compat wrapper — canonical location: tools/util/pr_to_dev.sh
exec "$(dirname "$0")/util/pr_to_dev.sh" "$@"
