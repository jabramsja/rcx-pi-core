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
    [--runner auto|rust-examples|trace-cli|none]

Purpose:
  Create an ISOLATED mutation sandbox run:
    - Reads the input .mu world
    - Applies deterministic, conservative mutations to "rule-like" lines
    - Writes outputs under sandbox_runs/ (or --out-dir)
    - Produces report.json

Optional:
  --run     Run baseline + mutated through a best-effort runner ladder and capture outputs.
  --score   If traces (JSON) are available, compute world scores & snapshot integrity checks.
  --max-steps N  Gate (exit 1) if inferred steps > N (uses scripts/world_score.sh --max-steps).
  --runner ...   Force runner selection:
                 auto (default): try rust-examples, then trace-cli, else none
                 rust-examples: use `python3 -m rcx_pi_rust.cli.examples_cli` if available
                 trace-cli:     use `python3 -m rcx_omega.cli.trace_cli` if available (world-agnostic, best-effort)
                 none:          mutation-only (no execution)

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
    - (optional) baseline.out.txt / mutated.out.txt
    - (optional) baseline.json / mutated.json
    - (optional) baseline.score.json / mutated.score.json
    - (optional) comparison.json

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
if runner_mode not in {"auto", "rust-examples", "trace-cli", "none"}:
    raise SystemExit("ERROR: --runner must be one of: auto|rust-examples|trace-cli|none")

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

baseline_out = run_dir / "baseline.mu"
mut_out = run_dir / "mutated.mu"
baseline_out.write_text(text, encoding="utf-8")
mut_out.write_text(mut_text, encoding="utf-8")

mut_rule_like_count = sum(1 for ln in mut_lines if rule_like.search(ln))
flips_applied = sum(1 for e in events if e.kind == "flip")

def which_module(mod: str) -> bool:
    # best-effort: `python -m mod --help` should exit 0/2; any output means importable.
    p = subprocess.run([sys.executable, "-m", mod, "--help"], text=True, capture_output=True)
    return p.returncode in (0, 2)

def run_cmd(cmd: list[str], timeout: int = 60) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    return p.returncode, p.stdout, p.stderr

def try_json_load(s: str) -> Optional[Any]:
    s = s.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None

def runner_auto() -> str:
    # Prefer the rust examples CLI if available, else trace_cli, else none.
    if which_module("rcx_pi_rust.cli.examples_cli"):
        return "rust-examples"
    if which_module("rcx_omega.cli.trace_cli"):
        return "trace-cli"
    return "none"

chosen_runner = runner_mode
if chosen_runner == "auto":
    chosen_runner = runner_auto()

# Runner adapters:
# - rust-examples: run the existing examples suite (not world-specific), but we still record baseline/mutated as artifacts.
#   If there is a way to point it at a world file, we won't assume it; we just run and capture outputs.
# - trace-cli: best-effort call trace_cli with fixed expr (world-agnostic), and save JSON as a "trace sample".
# - none: skip.
run_artifacts: dict[str, Any] = {"runner": chosen_runner, "baseline": {}, "mutated": {}, "notes": []}

def write_text(path: Path, s: str) -> None:
    path.write_text(s, encoding="utf-8", errors="replace")

def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def do_one(label: str) -> None:
    out_txt = run_dir / f"{label}.out.txt"
    out_json = run_dir / f"{label}.json"
    info: dict[str, Any] = {"exit_code": None, "stdout_path": str(out_txt), "json_path": None, "json_ok": False}

    if chosen_runner == "rust-examples":
        rc, so, se = run_cmd([sys.executable, "-m", "rcx_pi_rust.cli.examples_cli"], timeout=120)
        combined = (so or "") + (("\n" + se) if se else "")
        write_text(out_txt, combined)
        info["exit_code"] = rc
        # try to find a JSON blob in stdout (rare). If not, json_path stays None.
        obj = try_json_load(so)
        if obj is not None:
            write_json(out_json, obj)
            info["json_path"] = str(out_json)
            info["json_ok"] = True

    elif chosen_runner == "trace-cli":
        # World-agnostic: trace_cli on a stable expr. Save JSON to label.json.
        rc, so, se = run_cmd([sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "μ(μ())"], timeout=60)
        combined = (so or "") + (("\n" + se) if se else "")
        write_text(out_txt, combined)
        info["exit_code"] = rc
        obj = try_json_load(so)
        if obj is not None:
            write_json(out_json, obj)
            info["json_path"] = str(out_json)
            info["json_ok"] = True
        else:
            run_artifacts["notes"].append("trace-cli did not emit valid JSON on stdout")

    else:
        info["exit_code"] = 0
        write_text(out_txt, "NOTE: runner=none; mutation-only run\n")

    run_artifacts[label] = info

# For now baseline/mutated runs are symmetric (they don't actually execute the mutated world unless future runner supports it).
# Still useful: it validates the runner ladder, and sets up comparison plumbing.
if do_run:
    do_one("baseline")
    do_one("mutated")

comparison: dict[str, Any] = {"enabled": False}
rc_final = 0

def score_one(label: str, json_path: Optional[str]) -> Optional[dict[str, Any]]:
    if not json_path:
        return None
    p = Path(json_path)
    if not p.is_file():
        return None
    # Score using world_score.sh (it accepts trace-shaped JSON best-effort)
    cmd = ["bash", "scripts/world_score.sh", str(p), "--json", "--loop"]
    if max_steps > 0:
        cmd += ["--max-steps", str(max_steps)]
    pr = subprocess.run(cmd, text=True, capture_output=True, check=False)
    outp = pr.stdout.strip()
    obj = try_json_load(outp)
    if obj is None:
        return None
    score_path = run_dir / f"{label}.score.json"
    write_json(score_path, obj)
    if pr.returncode == 1:
        # violation (e.g., max-steps)
        nonlocal_rc = 1
        return {"score_path": str(score_path), "score": obj.get("score"), "violation": obj.get("violation"), "exit_code": pr.returncode, "_force_rc1": True}
    return {"score_path": str(score_path), "score": obj.get("score"), "violation": obj.get("violation"), "exit_code": pr.returncode}

# Python doesn't allow nonlocal at module scope; do it via flag:
force_rc1 = False

if do_run and do_score:
    b = run_artifacts.get("baseline", {})
    m = run_artifacts.get("mutated", {})
    bjson = b.get("json_path")
    mjson = m.get("json_path")

    bs = score_one("baseline", bjson)
    ms = score_one("mutated", mjson)

    if bs and bs.get("_force_rc1"):
        force_rc1 = True
        bs.pop("_force_rc1", None)
    if ms and ms.get("_force_rc1"):
        force_rc1 = True
        ms.pop("_force_rc1", None)

    snap = None
    if bjson and mjson:
        pr = subprocess.run(
            ["bash", "scripts/snapshot_integrity_check.sh", bjson, mjson, "--json"],
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
            "Current runner ladder may not execute mutated world semantics yet; this is plumbing + safety scaffolding.",
            "Once a runner supports 'world file' input, baseline/mutated will diverge meaningfully in outputs.",
        ],
    }
    write_json(run_dir / "comparison.json", comparison)

if force_rc1:
    rc_final = 1

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
    "run": run_artifacts if do_run else {"runner": chosen_runner, "enabled": False},
    "comparison": comparison,
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
    if do_run:
        print(f"- runner:   {chosen_runner}")
    if do_score and do_run:
        print(f"- comparison: {run_dir / 'comparison.json'}")

sys.exit(rc_final)
PY
