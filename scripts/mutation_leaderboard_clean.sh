#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/mutation_leaderboard_clean.sh
    [--world PATH]
    [--seeds N]
    [--mutations K]
    [--apply flip|shuffle|both]
    [--runner auto|none|omega-cli|trace-cli]
    [--out-dir DIR]

Output:
  Clears scrollback+screen and prints a compact leaderboard summary only.

Notes:
  - This uses scripts/mutation_sandbox.sh and is safe to ⌘A copy.
USAGE
}

WORLD=""
N=10
MUTS=3
APPLY="both"
RUNNER="auto"
OUT_DIR="sandbox_runs"

while [ $# -gt 0 ]; do
  case "$1" in
    --world) WORLD="${2-}"; shift 2;;
    --seeds) N="${2-10}"; shift 2;;
    --mutations) MUTS="${2-3}"; shift 2;;
    --apply) APPLY="${2-both}"; shift 2;;
    --runner) RUNNER="${2-auto}"; shift 2;;
    --out-dir) OUT_DIR="${2-sandbox_runs}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

cd "$(git rev-parse --show-toplevel)"

test -f scripts/mutation_sandbox.sh || { echo "Not found: scripts/mutation_sandbox.sh" >&2; exit 2; }
mkdir -p "$OUT_DIR"

# Pick a deterministic world if not specified (exclude .git + sandbox_runs)
if [ -z "${WORLD:-}" ]; then
  WORLD="$(
    find . -type f -name '*.mu' \
      -not -path './.git/*' \
      -not -path './sandbox_runs/*' \
      | head -n 1 || true
  )"
  WORLD="${WORLD#./}"
fi

test -n "${WORLD:-}" || { echo "ERROR: no *.mu found" >&2; exit 2; }
test -f "$WORLD" || { echo "ERROR: world not found: $WORLD" >&2; exit 2; }

WORK_LOG="${TMPDIR:-/tmp}/rcx_mutation_leaderboard_work.log"
SUMMARY="${TMPDIR:-/tmp}/rcx_mutation_leaderboard_summary.txt"

# Delegate “quiet run + clean print” to clean_print helper.
bash scripts/clean_print.sh --work "$WORK_LOG" --summary "$SUMMARY" -- \
  python3 - "$WORLD" "$N" "$MUTS" "$APPLY" "$RUNNER" "$OUT_DIR" "$SUMMARY" <<'PY'
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

world = sys.argv[1]
n = int(sys.argv[2])
muts = sys.argv[3]
apply = sys.argv[4]
runner = sys.argv[5]
out_dir = sys.argv[6]
summary_path = Path(sys.argv[7])

def run_seed(seed: int):
    p = subprocess.run(
        ["bash", "scripts/mutation_sandbox.sh", world,
         "--seed", str(seed),
         "--mutations", str(muts),
         "--apply", str(apply),
         "--out-dir", str(out_dir),
         "--run", "--score",
         "--runner", str(runner),
         "--json"],
        text=True, capture_output=True
    )
    # 0=ok, 1=violation path (still valid report), others are failures
    if p.returncode not in (0, 1):
        return {"seed": seed, "ok": False, "rc": p.returncode, "err": (p.stderr or p.stdout)[:4000]}

    try:
        obj = json.loads(p.stdout)
    except Exception:
        return {"seed": seed, "ok": False, "rc": p.returncode, "err": "JSON parse failed"}

    cmp = obj.get("comparison") or {}
    scores = (cmp.get("scores") or {})
    b = scores.get("baseline") or {}
    m = scores.get("mutated") or {}
    snap = cmp.get("snapshot_integrity") or {}

    def score_of(x): return None if not x else x.get("score")
    run_dir = (obj.get("paths") or {}).get("run_dir")

    return {
        "seed": seed,
        "ok": True,
        "rc": p.returncode,
        "runner": (obj.get("run") or {}).get("runner"),
        "score_b": score_of(b),
        "score_m": score_of(m),
        "snap_ok": None if not snap else bool(snap.get("ok")),
        "run_dir": run_dir,
    }

rows = [run_seed(i) for i in range(1, n + 1)]

# "best" only defined if mutated score is numeric (not None)
def sort_key(r):
    sm = r.get("score_m")
    sb = r.get("score_b")
    smv = sm if isinstance(sm, (int, float)) else -1e9
    sbv = sb if isinstance(sb, (int, float)) else -1e9
    return (-smv, -sbv, r.get("seed", 0))

rows_sorted = sorted(rows, key=sort_key)

lines = []
lines.append("== RCX: mutation sandbox leaderboard (clean) ==")
lines.append(f"-- world: {world} --")
lines.append(f"-- runner: {runner}   apply: {apply}   mutations: {muts}   seeds: {n} --")
lines.append("")
lines.append("seed | runner     | score_b | score_m | snap_ok | rc | run_dir")
lines.append("-----+------------+---------+---------+---------+----+------------------------------")

for r in rows:
    if not r.get("ok"):
        lines.append(f"{r['seed']:>4} | (fail)     |   -     |   -     |   -     | {r['rc']:<2} | (see work log)")
        continue
    run_dir = r.get("run_dir") or ""
    short = run_dir.replace("sandbox_runs/", "…runs/") if run_dir else ""
    rn = (r.get("runner") or "none")[:10]
    sb = r.get("score_b")
    sm = r.get("score_m")
    lines.append(
        f"{r['seed']:>4} | {rn:<10} | {sb!s:>7} | {sm!s:>7} | {str(r.get('snap_ok')):>7} | {r['rc']:<2} | {short}"
    )

best = next((r for r in rows_sorted if r.get("ok") and isinstance(r.get("score_m"), (int, float))), None)
lines.append("")
if best:
    lines.append(f"best_seed: {best['seed']}  score_m: {best['score_m']}  score_b: {best['score_b']}  runner: {best.get('runner')}")
    lines.append(f"best_run_dir: {best.get('run_dir')}")
else:
    lines.append("best_seed: (none)  NOTE: no numeric score_m produced (runner may be skipping or emitting non-scoreable JSON).")

summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
