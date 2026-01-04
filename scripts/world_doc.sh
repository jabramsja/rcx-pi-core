#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/world_doc.sh <world.mu> [--json] [--top N]

Emits:
  - Default: deterministic Markdown "world card" (counts + histogram + top-N rule-like lines in textual order).
  - --json: stable JSON summary for tooling.

Notes:
  - Tooling inspector only; does NOT change runtime semantics.
  - "Rule-like" lines are conservatively detected as non-comment lines containing "->" (route/rewrite arrow),
    or lines starting with keywords (rule|rewrite|when|defrule), or containing ":=".
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi
WORLD="$1"; shift || true
AS_JSON=0
TOP=25

while [ $# -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1; shift;;
    --top) TOP="${2-25}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

python3 - "$WORLD" "$AS_JSON" "$TOP" <<'PY'
from __future__ import annotations
import json, re, sys
from pathlib import Path
from typing import Any

world = Path(sys.argv[1])
as_json = bool(int(sys.argv[2]))
top_n = int(sys.argv[3])

if not world.is_file():
    raise SystemExit(f"ERROR: file not found: {world}")

lines = world.read_text(encoding="utf-8", errors="replace").splitlines()

# Conservative detector (matches RCX-π .mu syntax shown in repo)
rule_like = re.compile(
    r"^\s*(?!#)(?:"
    r"(?:rule|rewrite|when|defrule)\b"
    r"|.*->.*"
    r"|.*:=.*"
    r")",
    re.IGNORECASE,
)

# Extract a simple "action" for histogram:
#   [..] -> ra|lobe|sink
#   X -> rewrite (...)
#   otherwise: "other"
action_re = re.compile(r"->\s*([A-Za-z_]+)", re.IGNORECASE)

rules: list[dict[str, Any]] = []
hist: dict[str, int] = {}

for lineno, raw in enumerate(lines, start=1):
    if not rule_like.search(raw):
        continue
    text = raw.rstrip()

    act = "other"
    m = action_re.search(text)
    if m:
        act = m.group(1).lower()

    hist[act] = hist.get(act, 0) + 1
    rules.append({"idx": len(rules) + 1, "line": lineno, "action": act, "text": text})

top_rules = rules[: max(0, top_n)]

out = {
    "world": str(world),
    "precedence_basis": "textual order (earlier lines first)",
    "rule_like_count": len(rules),
    "action_histogram": {k: hist[k] for k in sorted(hist.keys())},
    "top_n": top_n,
    "top_rules": top_rules,
}

if as_json:
    print(json.dumps(out, ensure_ascii=False, indent=2))
else:
    # Deterministic markdown
    print(f"# World auto-doc: `{world}`")
    print()
    print("- precedence_basis: textual order (earlier lines first)")
    print(f"- rule_like_count: {out['rule_like_count']}")
    print()
    print("## Action histogram")
    if out["action_histogram"]:
        for k in sorted(out["action_histogram"].keys()):
            print(f"- `{k}`: {out['action_histogram'][k]}")
    else:
        print("- (none detected)")
    print()
    print(f"## Top {top_n} rule-like lines (in precedence order)")
    if top_rules:
        for r in top_rules:
            print(f"{r['idx']:>3}. line {r['line']}  [{r['action']}]  {r['text']}")
    else:
        print("(none detected)")
PY
