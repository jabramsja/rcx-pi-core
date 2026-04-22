#!/usr/bin/env bash
# Derive wave-id flag for L4 execution contract enforcement.
#
# Shared by ci.yml and green_gate.yml to avoid duplicating the
# branch-prefix → wave-id derivation logic.
#
# Usage:
#   source tools/checks/derive_wave_id.sh "$BRANCH" --range "$RANGE"
#   source tools/checks/derive_wave_id.sh "$BRANCH" --staged
#   source tools/checks/derive_wave_id.sh "$BRANCH" --files "$FILE_LIST"
#   # Sets WAVE_ID_FLAG (empty string or "--wave-id=<suffix>")
#
# Args:
#   $1 — branch name (e.g., "jabramsja/foo" or "codex/bar")
#   $2 — mode: --range | --staged | --files
#   $3 — mode payload for --range / --files
#
# Output: Sets WAVE_ID_FLAG environment variable.
# Note: pre-push-fast still has its own inline logic (not yet migrated).

set -euo pipefail

BRANCH="${1:-}"
MODE="${2:-}"
MODE_VALUE="${3:-}"
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

_tasks_changed_for_mode() {
  case "$MODE" in
    --staged)
      git diff --cached --name-only 2>/dev/null | grep -qx "TASKS.md"
      ;;
    --range)
      [ -n "$MODE_VALUE" ] && git diff --name-only "$MODE_VALUE" 2>/dev/null | grep -qx "TASKS.md"
      ;;
    --files)
      [ -n "$MODE_VALUE" ] && printf '%s\n' "$MODE_VALUE" | grep -qx "TASKS.md"
      ;;
    *)
      return 1
      ;;
  esac
}

# Only set wave-id flag if TASKS.md is in scope AND the branch-derived suffix
# exists in a tracker note exactly. Restart branches therefore fall back cleanly
# when their suffix is not the authoritative wave id in TASKS.md.
if [ -n "$WAVE_ID_SUFFIX" ] && _tasks_changed_for_mode; then
  if grep -qE "Tracker sync note \([^,]+, ${WAVE_ID_SUFFIX}\):" TASKS.md 2>/dev/null; then
    WAVE_ID_FLAG="--wave-id=$WAVE_ID_SUFFIX"
  fi
fi

export WAVE_ID_FLAG
