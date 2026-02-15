#!/usr/bin/env bash
# DEPRECATED (Round 19C, 2026-02-14)
# Merged into scripts/goldens_check.sh --update
# This wrapper remains for backward compatibility.
exec "$(dirname "$0")/goldens_check.sh" --update
