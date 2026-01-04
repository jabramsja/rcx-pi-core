#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/json_diff.sh <left.json> <right.json> [--ignore k1,k2,...] [--only path1,path2,...] [--quiet]

Semantics:
  - Parses JSON and compares canonicalized structure (ordering-insensitive for objects).
  - By default compares entire document.
  - --ignore: remove these top-level keys before compare (comma-separated). (Safe for OPTIONAL schema metadata like kind/schema_version.)
  - --only: compare only these top-level keys (comma-separated). If provided, ignores everything else.
  - Exit code 0 if equal, 1 if different, 2 on usage/error.

Examples:
  scripts/json_diff.sh a.json b.json --ignore kind,schema_version
  scripts/json_diff.sh a.json b.json --only result
USAGE
}

if [ $# -lt 2 ]; then
  usage
  exit 2
fi

LEFT="$1"; RIGHT="$2"; shift 2
IGNORE=""
ONLY=""
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --ignore)
      IGNORE="${2-}"; shift 2;;
    --only)
      ONLY="${2-}"; shift 2;;
    --quiet)
      QUIET=1; shift 1;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      usage
      exit 2;;
  esac
done

python3 - <<'PY' "$LEFT" "$RIGHT" "$IGNORE" "$ONLY" "$QUIET"
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any

left_path = Path(sys.argv[1])
right_path = Path(sys.argv[2])
ignore_csv = sys.argv[3]
only_csv = sys.argv[4]
quiet = bool(int(sys.argv[5]))

def load(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"ERROR: file not found: {p}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: invalid JSON in {p}: {e}")

def canonical(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: canonical(x[k]) for k in sorted(x.keys())}
    if isinstance(x, list):
        # Lists are order-sensitive by default (JSON arrays are sequences).
        # We canonicalize their elements but keep order.
        return [canonical(v) for v in x]
    return x

def filter_top(obj: Any, ignore_keys: set[str], only_keys: set[str] | None) -> Any:
    if not isinstance(obj, dict):
        return obj
    if only_keys is not None:
        return {k: obj[k] for k in sorted(only_keys) if k in obj}
    if ignore_keys:
        return {k: obj[k] for k in obj.keys() if k not in ignore_keys}
    return obj

ignore_keys = {k.strip() for k in ignore_csv.split(",") if k.strip()} if ignore_csv else set()
only_keys = {k.strip() for k in only_csv.split(",") if k.strip()} if only_csv else None

L = load(left_path)
R = load(right_path)

Lf = filter_top(L, ignore_keys, only_keys)
Rf = filter_top(R, ignore_keys, only_keys)

Lc = canonical(Lf)
Rc = canonical(Rf)

if Lc == Rc:
    if not quiet:
        print("OK: JSON equal (semantic)")
    sys.exit(0)

# differ
if quiet:
    sys.exit(1)

# Print a minimal, paste-friendly diff hint (paths are top-level only).
print("DIFF: JSON differs (semantic)")
if only_keys is not None:
    print(f"scope: --only {','.join(sorted(only_keys))}")
elif ignore_keys:
    print(f"scope: --ignore {','.join(sorted(ignore_keys))}")
else:
    print("scope: full document")

# Show a compact summary of which top-level keys differ if dicts.
if isinstance(Lf, dict) and isinstance(Rf, dict):
    lk = set(Lf.keys()); rk = set(Rf.keys())
    only_l = sorted(lk - rk)
    only_r = sorted(rk - lk)
    both = sorted(lk & rk)
    changed = []
    for k in both:
        if canonical(Lf[k]) != canonical(Rf[k]):
            changed.append(k)
    if only_l: print("only-left:", only_l)
    if only_r: print("only-right:", only_r)
    if changed: print("changed:", changed)
else:
    print(f"left-type: {type(Lf).__name__} right-type: {type(Rf).__name__}")

sys.exit(1)
PY
