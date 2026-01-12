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
    [--orbit-seed MU]          (world runner only; default chosen heuristically)
    [--out-dir DIR]

Output:
  Clears scrollback+screen and prints a compact leaderboard summary only.

Notes:
  - When --runner auto:
      * motif-shaped input (μ(...) / mu(...)) -> omega-cli if available else trace-cli else none
      * world-shaped input -> NONE (contract: world-like auto must choose none)
USAGE
}

WORLD=""
N=10
MUTS=3
APPLY="both"
RUNNER="auto"
OUT_DIR="sandbox_runs"
ORBIT_SEED=""

while [ $# -gt 0 ]; do
  case "$1" in
    --world) WORLD="${2-}"; shift 2;;
    --seeds) N="${2-10}"; shift 2;;
    --mutations) MUTS="${2-3}"; shift 2;;
    --apply) APPLY="${2-both}"; shift 2;;
    --runner) RUNNER="${2-auto}"; shift 2;;
    --orbit-seed) ORBIT_SEED="${2-}"; shift 2;;
    --out-dir) OUT_DIR="${2-sandbox_runs}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

cd "$(git rev-parse --show-toplevel)"

test -f scripts/mutation_sandbox.sh || { echo "Not found: scripts/mutation_sandbox.sh" >&2; exit 2; }
test -f scripts/clean_print.sh || { echo "Not found: scripts/clean_print.sh" >&2; exit 2; }
mkdir -p "$OUT_DIR"

# Pick deterministic default world if not specified (exclude .git + sandbox_runs)
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

# Determine motif-shape vs world-shape from first non-empty, non-comment line
first_token="$(
  awk '
    /^[[:space:]]*$/ { next }
    /^[[:space:]]*#/ { next }
    { gsub(/^[[:space:]]+/, "", $0); print $0; exit }
  ' "$WORLD" 2>/dev/null || true
)"

is_motif=0
if [[ "${first_token:-}" == μ* || "${first_token:-}" == mu* ]]; then
  is_motif=1
fi

# WORLD-like heuristic: any non-comment line containing '->'
is_world_like=0
if awk 'BEGIN{ok=0} /^[[:space:]]*#/ {next} /->/ {ok=1; exit} END{exit ok?0:1}' "$WORLD" 2>/dev/null; then
  is_world_like=1
fi

# Auto runner selection
EFFECTIVE_RUNNER="$RUNNER"
if [ "$RUNNER" = "auto" ]; then
  if [ "$is_motif" -eq 1 ]; then
    if python3 -m rcx_omega.cli.omega_cli --help >/dev/null 2>&1; then
      EFFECTIVE_RUNNER="omega-cli"
    elif python3 -m rcx_omega.cli.trace_cli --help >/dev/null 2>&1; then
      EFFECTIVE_RUNNER="trace-cli"
    else
      EFFECTIVE_RUNNER="none"
    fi
  else
    # CONTRACT: world-like auto must choose none (not trace-cli)
    if [ "$is_world_like" -eq 1 ]; then
      EFFECTIVE_RUNNER="none"
    else
      # Non-world (weird file): fall back safely
      if python3 -m rcx_pi.worlds.world_trace_cli --help >/dev/null 2>&1; then
        EFFECTIVE_RUNNER="trace-cli"
      else
        EFFECTIVE_RUNNER="none"
      fi
    fi
  fi
fi

# Choose orbit seed if not provided and runner is trace-cli for world-shaped
if [ -z "${ORBIT_SEED:-}" ]; then
  base="$(basename "$WORLD")"
  base="${base%.mu}"
  if [[ "$base" == *pingpong* ]]; then
    ORBIT_SEED="ping"
  else
    ORBIT_SEED='[omega,[a,b]]'
  fi
fi

WORK_LOG="${TMPDIR:-/tmp}/rcx_mutation_leaderboard_work.log"
SUMMARY="${TMPDIR:-/tmp}/rcx_mutation_leaderboard_summary.txt"

bash scripts/clean_print.sh --work "$WORK_LOG" --summary "$SUMMARY" -- \
  python3 - "$WORLD" "$N" "$MUTS" "$APPLY" "$RUNNER" "$EFFECTIVE_RUNNER" "$OUT_DIR" "$SUMMARY" "$is_motif" "$is_world_like" "$ORBIT_SEED" <<'PY'
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

world = sys.argv[1]
n = int(sys.argv[2])
muts = sys.argv[3]
apply = sys.argv[4]
requested_runner = sys.argv[5]
effective_runner = sys.argv[6]
out_dir = sys.argv[7]
summary_path = Path(sys.argv[8])
is_motif = bool(int(sys.argv[9]))
is_world_like = bool(int(sys.argv[10]))
orbit_seed = sys.argv[11]

def run_seed(seed: int) -> dict:
    cmd = [
        "bash", "scripts/mutation_sandbox.sh", world,
        "--seed", str(seed),
        "--mutations", str(muts),
        "--apply", str(apply),
        "--out-dir", str(out_dir),
        "--run", "--score",
        "--runner", str(effective_runner),
        "--json",
    ]
    # Only pass orbit seed when we truly run world trace
    if (not is_motif) and effective_runner == "trace-cli":
        cmd += ["--orbit-seed", str(orbit_seed)]

    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        return {"seed": seed, "ok": False, "rc": p.returncode, "err": (p.stderr or p.stdout)[:1200]}

    try:
        obj = json.loads(p.stdout)
    except Exception:
        return {"seed": seed, "ok": False, "rc": p.returncode, "err": "JSON parse failed"}

    # Prefer comparison score when present
    score_b = None
    score_m = None
    try:
        scores = ((obj.get("comparison") or {}).get("scores") or {})
        b = scores.get("baseline") or {}
        m = scores.get("mutated") or {}
        if isinstance(b, dict): score_b = b.get("score")
        if isinstance(m, dict): score_m = m.get("score")
    except Exception:
        pass

    run_dir = ((obj.get("paths") or {}).get("run_dir")) or ""
    runner_used = ((obj.get("run") or {}).get("runner")) or effective_runner

    return {
        "seed": seed,
        "ok": True,
        "rc": p.returncode,
        "runner": runner_used,
        "score_b": score_b,
        "score_m": score_m,
        "run_dir": run_dir,
    }

rows = [run_seed(i) for i in range(1, n + 1)]

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
lines.append(f"-- detected: {'motif' if is_motif else 'world'} --")

# Contract marker for the test:
if requested_runner == "auto" and (not is_motif) and is_world_like and effective_runner == "none":
    lines.append("-- runner: none")

lines.append(f"-- runner: {requested_runner} (effective: {effective_runner})  apply: {apply}  mutations: {muts}  seeds: {n} --")
if (not is_motif) and effective_runner == "trace-cli":
    lines.append(f"-- orbit_seed: {orbit_seed} --")
lines.append("")

lines.append("seed | runner     | score_b | score_m | rc | run_dir")
lines.append("-----+------------+---------+---------+----+------------------------------")

for r in rows:
    if not r.get("ok"):
        lines.append(f"{r['seed']:>4} | (fail)     |   -     |   -     | {r['rc']:<2} | (see work log)")
        continue
    run_dir = r.get("run_dir") or ""
    short = run_dir.replace("sandbox_runs/", "…runs/") if run_dir else ""
    rn = (r.get("runner") or "none")[:10]
    sb = r.get("score_b")
    sm = r.get("score_m")
    lines.append(f"{r['seed']:>4} | {rn:<10} | {sb!s:>7} | {sm!s:>7} | {r['rc']:<2} | {short}")

best = next((r for r in rows_sorted if r.get("ok") and isinstance(r.get("score_m"), (int, float))), None)
lines.append("")
if best:
    lines.append(f"best_seed: {best['seed']}  score_m: {best['score_m']}  score_b: {best['score_b']}  runner: {best.get('runner')}")
    lines.append(f"best_run_dir: {best.get('run_dir')}")
else:
    lines.append("best_seed: (none)  NOTE: no numeric score_m produced (runner may be none/skip).")

summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

