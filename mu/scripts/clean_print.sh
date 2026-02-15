#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/clean_print.sh --summary <path> --work <path> -- <command...>

Behavior:
  - Runs <command...> with stdout+stderr redirected to --work
  - Requires that the command produces/updates the --summary file itself
  - Clears scrollback+screen, then prints ONLY the summary file
  - If the command fails, prints the work log and exits nonzero

Notes:
  - This is designed so ⌘A copies only the final, clean output.
USAGE
}

SUMMARY=""
WORK=""

while [ $# -gt 0 ]; do
  case "$1" in
    --summary) SUMMARY="${2-}"; shift 2;;
    --work) WORK="${2-}"; shift 2;;
    --) shift; break;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [ -z "${SUMMARY:-}" ] || [ -z "${WORK:-}" ] || [ $# -lt 1 ]; then
  usage
  exit 2
fi

# Ensure parent dirs exist
mkdir -p "$(dirname "$SUMMARY")" "$(dirname "$WORK")"
: > "$WORK"

# Run the payload quietly (full log goes to WORK)
if ! ( "$@" ) >"$WORK" 2>&1; then
  cat "$WORK"
  exit 1
fi

if [ ! -f "$SUMMARY" ]; then
  echo "ERROR: summary file not created: $SUMMARY" >&2
  echo "--- work log ---" >&2
  cat "$WORK" >&2
  exit 1
fi

# Clear scrollback + screen, then print only the summary
printf '\033[3J\033[H\033[2J'
cat "$SUMMARY"
