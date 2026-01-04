#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/mutation_sandbox.sh <world.mu>
    [--seed N]
    [--mutations K]
    [--out-dir DIR]
    [--json]
    [--apply flip|shuffle|both]
    [--run]
    [--score]
    [--max-steps N]
    [--runner auto|omega-cli|trace-cli|none]

Purpose:
  Create an ISOLATED mutation sandbox run:
    - Reads the input .mu world
    - Applies deterministic, conservative mutations to "rule-like" lines
    - Writes outputs under sandbox_runs/ (or --out-dir)
    - Produces report.json

Optional:
  --run     Attempt to run baseline + mutated via available runner(s), capturing stdout/stderr and JSON if produced.
  --score   If trace-shaped JSON is produced, compute world scores & snapshot integrity checks.
  --max-steps N  Gate (exit 1) if inferred steps > N (uses scripts/world_score.sh --max-steps).
  --runner ...   Force runner selection:
                 auto (default): prefer omega-cli, then trace-cli, else none
                 omega-cli:      python3 -m rcx_omega.cli.omega_cli  (uses --file; prefers --trace)
                 trace-cli:      python3 -m rcx_omega.cli.trace_cli  (uses --file)
                 none:           mutation-only (no execution)

Runner behavior (important):
  This tool executes baseline.mu and mutated.mu only when a runner supports --file (rcx_omega CLIs do).
  If a run does not emit JSON, scoring is skipped for that side (but the run still succeeds).

Conservative mutations:
  - flip:    change only terminal route tokens in lines like "-> ra|lobe|sink"
  - shuffle: reorder rule-like lines (deterministically) while keeping all lines
  - both:    shuffle then flip

Rule-like detector (conservative):
  - non-comment lines containing "->" OR ":=" OR starting with rule|rewrite|when|defrule

Outputs:
  <out-dir>/<run_id>/
    - baseline.mu
    - mutated.mu
    - report.json
    - (optional) baseline.out.txt / mutated.out.txt
    - (optional) baseline.json / mutated.json
    - (optional) baseline.score.json / mutated.score.json
    - (optional) comparison.json
    - (optional) snapshot_integrity.json

Exit codes:
  0 success
  1 violation detected (e.g., --max-steps exceeded)
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
DO_RUN=0
DO_SCORE=0
MAX_STEPS=0
RUNNER="auto"

while [ $# -gt 0 ]; do
  case "$1" in
    --seed) SEED="${2-1}"; shift 2;;
    --mutations) MUTS="${2-1}"; shift 2;;
    --out-dir) OUT_DIR="${2-sandbox_runs}"; shift 2;;
    --json) AS_JSON=1; shift;;
    --apply) APPLY="${2-both}"; shift 2;;
    --run) DO_RUN=1; shift;;
    --score) DO_SCORE=1; shift;;
    --max-steps) MAX_STEPS="${2-0}"; shift 2;;
    --runner) RUNNER="${2-auto}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

test -f "$WORLD" || { echo "ERROR: world not found: $WORLD" >&2; exit 2; }
mkdir -p "$OUT_DIR"

python3 - "$WORLD" "$SEED" "$MUTS" "$OUT_DIR" "$AS_JSON" "$APPLY" "$DO_RUN" "$DO_SCORE" "$MAX_STEPS" "$RUNNER" <<'PY'
from __future__ import annotations
import json, re, sys, time, hashlib, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

world_path = Path(sys.argv[1])
seed = int(sys.argv[2])
muts = max(0, int(sys.argv[3]))
out_dir = Path(sys.argv[4])
as_json = bool(int(sys.argv[5]))
apply = sys.argv[6].strip().lower()
do_run = bool(int(sys.argv[7]))
do_score = bool(int(sys.argv[8]))
max_steps = int(sys.argv[9])
runner_mode = sys.argv[10].strip().lower()

if apply not in {"flip", "shuffle", "both"}:
    raise SystemExit("ERROR: --apply must be one of: flip|shuffle|both")
if runner_mode not in {"auto", "omega-cli", "trace-cli", "none"}:
    raise SystemExit("ERROR: --runner must be one of: auto|omega-cli|trace-cli|none")

text = world_path.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

rule_like = re.compile(
    r"^\s*(?!#)(?:"
    r"(?:rule|rewrite|when|defrule)\b"
    r"|.*->.*"
    r"|.*:=.*"
    r")",
    re.IGNORECASE,
)
flip_re = re.compile(r"(->\s*)(ra|lobe|sink)\s*$", re.IGNORECASE)

@dataclass
class MutEvent:
    kind: str
    line_no: int
    before: str
    after: str

def stable_rng(seed_bytes: bytes):
    state = hashlib.sha256(seed_bytes).digest()
    while True:
        state = hashlib.sha256(state).digest()
        yield int.from_bytes(state[:8], "big")

rng = stable_rng(f"rcx-mutation-sandbox:{seed}".encode("utf-8"))

def pick(n: int) -> int:
    if n <= 0:
        return 0
    return next(rng) % n

idxs: List[int] = [i for i, ln in enumerate(lines) if rule_like.search(ln)]
events: List[MutEvent] = []
baseline_rule_like_count = len(idxs)
mut_lines = list(lines)

def do_shuffle():
    if len(idxs) < 2:
        return
    bucket = [mut_lines[i] for i in idxs]
    for j in range(len(bucket) - 1, 0, -1):
        k = pick(j + 1)
        bucket[j], bucket[k] = bucket[k], bucket[j]
    for pos, i in enumerate(idxs):
        mut_lines[i] = bucket[pos]

def do_flip(k_times: int):
    flips: List[int] = [i for i in idxs if flip_re.search(mut_lines[i])]
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

if apply in {"shuffle", "both"}:
    do_shuffle()
if apply in {"flip", "both"}:
    do_flip(muts)

mut_text = "\n".join(mut_lines) + ("\n" if text.endswith("\n") else "")

stamp = int(time.time())
h = hashlib.sha256(f"{world_path}:{seed}:{muts}:{apply}:{stamp}".encode("utf-8")).hexdigest()[:8]
run_id = f"run_{stamp}_{h}"
run_dir = out_dir / run_id
run_dir.mkdir(parents=True, exist_ok=False)

baseline_mu = run_dir / "baseline.mu"
mutated_mu = run_dir / "mutated.mu"
baseline_mu.write_text(text, encoding="utf-8")
mutated_mu.write_text(mut_text, encoding="utf-8")

mut_rule_like_count = sum(1 for ln in mut_lines if rule_like.search(ln))
flips_applied = sum(1 for e in events if e.kind == "flip")

def try_json_load(s: str) -> Optional[Any]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None

def run_cmd(cmd: list[str], timeout: int = 180) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    return p.returncode, p.stdout, p.stderr

def module_available(mod: str) -> bool:
    p = subprocess.run([sys.executable, "-m", mod, "--help"], text=True, capture_output=True)
    return p.returncode in (0, 2)

def runner_auto() -> str:
    # Prefer omega-cli (can emit trace), then trace-cli, else none
    if module_available("rcx_omega.cli.omega_cli"):
        return "omega-cli"
    if module_available("rcx_omega.cli.trace_cli"):
        return "trace-cli"
    return "none"

chosen_runner = runner_mode
if chosen_runner == "auto":
    chosen_runner = runner_auto()

run_artifacts: dict[str, Any] = {"runner": chosen_runner, "baseline": {}, "mutated": {}, "notes": []}

def write_text(path: Path, s: str) -> None:
    path.write_text(s, encoding="utf-8", errors="replace")

def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def run_one(label: str, world_file: Path) -> None:
    out_txt = run_dir / f"{label}.out.txt"
    out_json = run_dir / f"{label}.json"
    info: dict[str, Any] = {
        "exit_code": None,
        "stdout_path": str(out_txt),
        "json_path": None,
        "json_ok": False,
        "world_used": str(world_file),
        "cmd_used": None,
    }

    if chosen_runner == "omega-cli":
        # Try the most meaningful form first: --trace + --json + --file
        cmd_candidates = [
            [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "--trace", "--file", str(world_file)],
            [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "--file", str(world_file)],
        ]
    elif chosen_runner == "trace-cli":
        cmd_candidates = [
            [sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "--file", str(world_file)],
        ]
    else:
        cmd_candidates = []

    if not cmd_candidates:
        info["exit_code"] = 0
        write_text(out_txt, "NOTE: runner=none; mutation-only run\n")
        run_artifacts[label] = info
        return

    last_rc, last_so, last_se = 1, "", ""
    for cmd in cmd_candidates:
        rc, so, se = run_cmd(cmd, timeout=180)
        combined = (so or "") + (("\n" + se) if se else "")
        write_text(out_txt, combined)
        info["exit_code"] = rc
        info["cmd_used"] = " ".join(cmd)
        obj = try_json_load(so)
        if obj is not None:
            write_json(out_json, obj)
            info["json_path"] = str(out_json)
            info["json_ok"] = True
            run_artifacts[label] = info
            return
        last_rc, last_so, last_se = rc, so, se

    # No JSON from any candidate
    run_artifacts["notes"].append(f"{label}: runner produced no JSON (cmd tried: {info.get('cmd_used')})")
    run_artifacts[label] = info

force_rc1 = False
comparison: dict[str, Any] = {"enabled": False}

def score_one(label: str, json_path: Optional[str]) -> Optional[dict[str, Any]]:
    if not json_path:
        return None
    p = Path(json_path)
    if not p.is_file():
        return None
    cmd = ["bash", "scripts/world_score.sh", str(p), "--json", "--loop"]
    if max_steps > 0:
        cmd += ["--max-steps", str(max_steps)]
    pr = subprocess.run(cmd, text=True, capture_output=True, check=False)
    obj = try_json_load(pr.stdout)
    if obj is None:
        return None
    score_path = run_dir / f"{label}.score.json"
    write_json(score_path, obj)
    d: dict[str, Any] = {"score_path": str(score_path), "score": obj.get("score"), "violation": obj.get("violation"), "exit_code": pr.returncode}
    if pr.returncode == 1:
        d["_force_rc1"] = True
    return d

if do_run:
    run_one("baseline", baseline_mu)
    run_one("mutated", mutated_mu)

if do_run and do_score:
    b = run_artifacts.get("baseline", {})
    m = run_artifacts.get("mutated", {})
    bs = score_one("baseline", b.get("json_path"))
    ms = score_one("mutated", m.get("json_path"))

    if bs and bs.pop("_force_rc1", False):
        force_rc1 = True
    if ms and ms.pop("_force_rc1", False):
        force_rc1 = True

    snap = None
    if b.get("json_path") and m.get("json_path"):
        pr = subprocess.run(
            ["bash", "scripts/snapshot_integrity_check.sh", b["json_path"], m["json_path"], "--json"],
            text=True,
            capture_output=True,
            check=False,
        )
        snap_obj = try_json_load(pr.stdout)
        if snap_obj is not None:
            snap_path = run_dir / "snapshot_integrity.json"
            write_json(snap_path, snap_obj)
            snap = {"path": str(snap_path), "ok": bool(snap_obj.get("ok")), "exit_code": pr.returncode}

    comparison = {
        "enabled": True,
        "runner": chosen_runner,
        "scores": {"baseline": bs, "mutated": ms},
        "snapshot_integrity": snap,
        "notes": [
            "If json_ok is false, that runner run did not emit JSON; scoring is skipped for that side.",
            "With omega-cli --trace, baseline/mutated should diverge once the CLI actually consumes the .mu file.",
        ],
    }
    write_json(run_dir / "comparison.json", comparison)

rc_final = 1 if force_rc1 else 0

report: dict[str, Any] = {
    "run_id": run_id,
    "world_in": str(world_path),
    "seed": seed,
    "mutations_requested": muts,
    "apply": apply,
    "paths": {
        "run_dir": str(run_dir),
        "baseline_mu": str(baseline_mu),
        "mutated_mu": str(mutated_mu),
        "report_json": str(run_dir / "report.json"),
    },
    "metrics": {
        "baseline_rule_like_count": baseline_rule_like_count,
        "mutated_rule_like_count": mut_rule_like_count,
        "flips_applied": flips_applied,
        "events": [e.__dict__ for e in events[:200]],
    },
    "run": run_artifacts if do_run else {"runner": chosen_runner, "enabled": False},
    "comparison": comparison,
    "notes": [
        "Sandbox is isolated: writes only under out-dir/run_id/",
        "Mutations are conservative and deterministic for a given seed + apply mode.",
        "Runner ladder now uses rcx_omega CLIs with --file (omega_cli preferred).",
    ],
}

(run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if as_json:
    print(json.dumps(report, ensure_ascii=False, indent=2))
else:
    print(f"OK: wrote {run_dir}")
    print(f"- baseline: {baseline_mu}")
    print(f"- mutated:  {mutated_mu}")
    print(f"- report:   {run_dir / 'report.json'}")
    if do_run:
        print(f"- runner:   {chosen_runner}")
        if run_artifacts.get("notes"):
            print("- runner_notes:")
            for n in run_artifacts["notes"][:10]:
                print(f"  - {n}")
    if do_score and do_run:
        print(f"- comparison: {run_dir / 'comparison.json'}")

sys.exit(rc_final)
PY
