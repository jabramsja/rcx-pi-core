#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/snapshot_integrity_check.sh <baseline.json> <current.json> [--only PATH] [--ignore k1,k2,...] [--json]

Purpose:
  A tiny "snapshot integrity" tool for CI/tooling that checks whether two JSON snapshots are semantically equal
  for a chosen stable subset.

Defaults:
  --only result
  --ignore kind,schema_version

Options:
  --only PATH        Compare only a top-level key (default: result). (Matches scripts/json_diff.sh semantics.)
  --ignore CSV       Ignore top-level keys (default: kind,schema_version).
  --json             Emit a stable JSON summary (still uses exit codes).

Exit codes:
  0 OK (integrity holds)
  1 Mismatch detected
  2 Usage / file errors
USAGE
}

if [ $# -lt 2 ]; then usage; exit 2; fi
BASE="$1"; CURR="$2"; shift 2 || true

ONLY="result"
IGNORE="kind,schema_version"
AS_JSON=0

while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2-}"; shift 2;;
    --ignore) IGNORE="${2-}"; shift 2;;
    --json) AS_JSON=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

test -f "$BASE" || { echo "ERROR: baseline not found: $BASE" >&2; exit 2; }
test -f "$CURR" || { echo "ERROR: current not found: $CURR" >&2; exit 2; }
test -x scripts/json_diff.sh || { echo "ERROR: missing executable scripts/json_diff.sh" >&2; exit 2; }

set +e
OUT="$(bash scripts/json_diff.sh "$BASE" "$CURR" --only "$ONLY" --ignore "$IGNORE" 2>&1)"
RC=$?
set -e

if [ "$AS_JSON" -eq 1 ]; then
  python3 - "$BASE" "$CURR" "$ONLY" "$IGNORE" "$RC" "$OUT" <<'PY'
from __future__ import annotations
import json, sys
base, curr, only, ignore, rc, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6]
obj = {
  "baseline": base,
  "current": curr,
  "only": only,
  "ignore": [s for s in (ignore.split(",") if ignore else []) if s],
  "ok": (rc == 0),
  "tool_output": out.strip(),
}
print(json.dumps(obj, ensure_ascii=False, indent=2))
PY
else
  echo "$OUT"
fi

# Propagate json_diff.sh semantics (0 ok, 1 mismatch, 2 error)
exit "$RC"
