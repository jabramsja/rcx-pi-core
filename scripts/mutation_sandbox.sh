#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/mutation_sandbox.sh <world.mu> [--seed N] [--mutations K] [--out-dir DIR] [--json] [--apply flip|shuffle|both]

Purpose:
  Create an ISOLATED mutation sandbox run:
    - Reads the input .mu world
    - Applies deterministic, conservative mutations to "rule-like" lines
    - Writes outputs under sandbox_runs/ (or --out-dir)
    - Produces a stable report.json (and optional stdout JSON via --json)

Conservative mutations:
  - flip:    change only terminal route tokens in lines like "-> ra|lobe|sink"
  - shuffle: reorder rule-like lines (deterministically) while keeping all lines
  - both:    shuffle then flip

Rule-like line detector (conservative):
  - non-comment lines containing "->" OR ":=" OR starting with rule|rewrite|when|defrule

Outputs:
  <out-dir>/<run_id>/
    - baseline.mu
    - mutated.mu
    - report.json

Exit codes:
  0 success
  2 usage / file errors
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi
WORLD="$1"; shift || true

SEED=1
MUTS=1
OUT_DIR="sandbox_runs"
AS_JSON=0
APPLY="both"

while [ $# -gt 0 ]; do
  case "$1" in
    --seed) SEED="${2-1}"; shift 2;;
    --mutations) MUTS="${2-1}"; shift 2;;
    --out-dir) OUT_DIR="${2-sandbox_runs}"; shift 2;;
    --json) AS_JSON=1; shift;;
    --apply) APPLY="${2-both}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

test -f "$WORLD" || { echo "ERROR: world not found: $WORLD" >&2; exit 2; }
mkdir -p "$OUT_DIR"

python3 - "$WORLD" "$SEED" "$MUTS" "$OUT_DIR" "$AS_JSON" "$APPLY" <<'PY'
from __future__ import annotations
import json, re, sys, time, hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

world_path = Path(sys.argv[1])
seed = int(sys.argv[2])
muts = max(0, int(sys.argv[3]))
out_dir = Path(sys.argv[4])
as_json = bool(int(sys.argv[5]))
apply = sys.argv[6].strip().lower()

if apply not in {"flip", "shuffle", "both"}:
    raise SystemExit("ERROR: --apply must be one of: flip|shuffle|both")

text = world_path.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

# Conservative detector
rule_like = re.compile(
    r"^\s*(?!#)(?:"
    r"(?:rule|rewrite|when|defrule)\b"
    r"|.*->.*"
    r"|.*:=.*"
    r")",
    re.IGNORECASE,
)

# Strict flip target: terminal "-> ra|lobe|sink" (ignore other arrows)
flip_re = re.compile(r"(->\s*)(ra|lobe|sink)\s*$", re.IGNORECASE)

@dataclass
class MutEvent:
    kind: str
    line_no: int
    before: str
    after: str

def stable_rng(seed_bytes: bytes):
    # tiny deterministic PRNG using sha256 chaining (portable, no random module)
    state = hashlib.sha256(seed_bytes).digest()
    while True:
        state = hashlib.sha256(state).digest()
        yield int.from_bytes(state[:8], "big")

rng = stable_rng(f"rcx-mutation-sandbox:{seed}".encode("utf-8"))

def pick(n: int) -> int:
    if n <= 0:
        return 0
    return next(rng) % n

# Identify rule-like line indices
idxs: List[int] = [i for i, ln in enumerate(lines) if rule_like.search(ln)]
events: List[MutEvent] = []

baseline_rule_like_count = len(idxs)
mut_lines = list(lines)

def do_shuffle():
    if len(idxs) < 2:
        return
    # Deterministic Fisher–Yates over the rule-like lines only
    bucket = [mut_lines[i] for i in idxs]
    for j in range(len(bucket) - 1, 0, -1):
        k = pick(j + 1)
        bucket[j], bucket[k] = bucket[k], bucket[j]
    for pos, i in enumerate(idxs):
        mut_lines[i] = bucket[pos]

def do_flip(k_times: int):
    # Gather flippable positions
    flips: List[int] = []
    for i in idxs:
        if flip_re.search(mut_lines[i]):
            flips.append(i)
    if not flips or k_times <= 0:
        return
    targets = ["ra", "lobe", "sink"]
    for _ in range(k_times):
        i = flips[pick(len(flips))]
        before = mut_lines[i]
        m = flip_re.search(before)
        if not m:
            continue
        cur = m.group(2).lower()
        choices = [t for t in targets if t != cur]
        new = choices[pick(len(choices))]
        after = flip_re.sub(lambda mm: f"{mm.group(1)}{new}", before)
        if after != before:
            mut_lines[i] = after
            events.append(MutEvent(kind="flip", line_no=i + 1, before=before, after=after))

# Apply mutations
if apply in {"shuffle", "both"}:
    do_shuffle()
if apply in {"flip", "both"}:
    do_flip(muts)

mut_text = "\n".join(mut_lines) + ("\n" if text.endswith("\n") else "")

# Run-id (timestamp + short hash)
stamp = int(time.time())
h = hashlib.sha256(f"{world_path}:{seed}:{muts}:{apply}:{stamp}".encode("utf-8")).hexdigest()[:8]
run_id = f"run_{stamp}_{h}"
run_dir = out_dir / run_id
run_dir.mkdir(parents=True, exist_ok=False)

baseline_out = run_dir / "baseline.mu"
mut_out = run_dir / "mutated.mu"
baseline_out.write_text(text, encoding="utf-8")
mut_out.write_text(mut_text, encoding="utf-8")

mut_rule_like_count = sum(1 for ln in mut_lines if rule_like.search(ln))
flips_applied = sum(1 for e in events if e.kind == "flip")

report: dict[str, Any] = {
    "run_id": run_id,
    "world_in": str(world_path),
    "seed": seed,
    "mutations_requested": muts,
    "apply": apply,
    "paths": {
        "run_dir": str(run_dir),
        "baseline_mu": str(baseline_out),
        "mutated_mu": str(mut_out),
        "report_json": str(run_dir / "report.json"),
    },
    "metrics": {
        "baseline_rule_like_count": baseline_rule_like_count,
        "mutated_rule_like_count": mut_rule_like_count,
        "flips_applied": flips_applied,
        "events": [e.__dict__ for e in events[:200]],
    },
    "notes": [
        "Sandbox is isolated: writes only under out-dir/run_id/",
        "Mutations are conservative and deterministic for a given seed + apply mode.",
        "This tool does NOT change runtime semantics directly; it only produces mutated copies for experimentation.",
    ],
}
(run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if as_json:
    print(json.dumps(report, ensure_ascii=False, indent=2))
else:
    print(f"OK: wrote {run_dir}")
    print(f"- baseline: {baseline_out}")
    print(f"- mutated:  {mut_out}")
    print(f"- report:   {run_dir / 'report.json'}")
    if events:
        print(f"- events:   {len(events)} (showing up to 3)")
        for e in events[:3]:
            print(f"  - flip line {e.line_no}: {e.before.strip()}  =>  {e.after.strip()}")
    else:
        print("- events:   0 (no flippable rules found; try --apply shuffle or a different world)")
PY
