#!/usr/bin/env bash
# Derive wave-id flag for L4 execution contract enforcement.
#
# Shared by ci.yml and green_gate.yml to avoid duplicating the
# branch-prefix → wave-id derivation logic.
#
# Usage:
#   source tools/checks/derive_wave_id.sh "$BRANCH" "$RANGE"
#   # Sets WAVE_ID_FLAG (empty string or "--wave-id <suffix>")
#
# Args:
#   $1 — branch name (e.g., "jabramsja/foo" or "codex/bar")
#   $2 — git range (e.g., "origin/dev...HEAD") for TASKS.md diff check
#
# Output: Sets WAVE_ID_FLAG environment variable.
# Note: pre-push-fast still has its own inline logic (not yet migrated).

set -euo pipefail

BRANCH="${1:-}"
RANGE="${2:-}"
WAVE_ID_FLAG=""

if [ -z "$BRANCH" ]; then
  echo "WAVE_ID_FLAG="
  return 0 2>/dev/null || exit 0
fi

WAVE_ID_SUFFIX=""
if [[ "$BRANCH" == codex/* ]]; then
  WAVE_ID_SUFFIX="${BRANCH#codex/}"
elif [[ "$BRANCH" == jabramsja/* ]]; then
  WAVE_ID_SUFFIX="${BRANCH#jabramsja/}"
fi

# Only set wave-id flag if TASKS.md is in the diff AND the wave_id exists
# in a tracker note (exact match). Use = separator to prevent argparse from
# treating --suffix as a flag.
if [ -n "$WAVE_ID_SUFFIX" ] && [ -n "$RANGE" ] && git diff --name-only "$RANGE" 2>/dev/null | grep -qx "TASKS.md"; then
  if grep -qE "Tracker sync note \([^,]+, ${WAVE_ID_SUFFIX}\):" TASKS.md 2>/dev/null; then
    WAVE_ID_FLAG="--wave-id=$WAVE_ID_SUFFIX"
  fi
fi

export WAVE_ID_FLAG
