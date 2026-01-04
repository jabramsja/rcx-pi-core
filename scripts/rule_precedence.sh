#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/rule_precedence.sh <world.mu> [--json] [--top N]

Outputs:
  - Default: human-readable precedence order based on textual rule appearance.
  - --json: emits a stable JSON summary.

Notes:
  - Tooling inspector only; does NOT change runtime semantics.
  - Precedence here is "earlier rules first" as written in the .mu file.
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi
WORLD="$1"; shift || true
JSON=0
TOP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1; shift;;
    --top) TOP="${2-0}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

python3 - "$WORLD" "$JSON" "$TOP" <<'PY'
from __future__ import annotations
import json, re, sys
from pathlib import Path

world = Path(sys.argv[1])
as_json = bool(int(sys.argv[2]))
top = int(sys.argv[3])

if not world.is_file():
    raise SystemExit(f"ERROR: file not found: {world}")

txt = world.read_text(encoding="utf-8", errors="replace").splitlines()

# Conservative detection: only obvious rule-like lines.
# Conservative detection: rule-like lines in RCX-π .mu worlds.
# - Skip comments (# ...)
# - Match "->" rewrite/route lines (core world syntax)
# - Also match explicit keywords if present
rule_re = re.compile(
    r"^\s*(?!#)(?:"
    r"(?:rule|rewrite|when|defrule)\b"
    r"|.*->.*"
    r"|.*:=.*"
    r")",
    re.IGNORECASE,
)

rules: list[dict] = []
for i, line in enumerate(txt, start=1):
    if rule_re.search(line):
        rules.append({"idx": len(rules) + 1, "line": i, "text": line.rstrip()})

if top > 0:
    rules = rules[:top]

out = {
    "world": str(world),
    "rule_count_detected": len(rules),
    "precedence_basis": "textual order (earlier rules first)",
    "rules": rules,
}

if as_json:
    print(json.dumps(out, ensure_ascii=False, indent=2))
else:
    print(f"world: {world}")
    print("precedence_basis: textual order (earlier rules first)")
    print(f"rules_detected: {len(rules)}")
    for r in rules:
        print(f"{r['idx']:>3}. line {r['line']}: {r['text']}")
PY
