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
    [--orbit-seed SEEDTERM]

Notes:
  - This script’s "trace-cli" runner treats input as a WORLD (.mu rules).
  - It stages baseline/mutated into rcx_pi_rust/mu_programs and calls:
        python -m rcx_pi.worlds.world_trace_cli <WORLD_NAME> <SEEDTERM> --json
  - Scoring is done via scripts/world_score.sh reading trace JSON from stdin.
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi

WORLD=""

# Backward compatible: positional world.mu
if [ $# -ge 1 ] && [[ "${1:-}" != --* ]]; then
  WORLD="$1"
  shift
fi

SEED=1
MUTS=1
OUT_DIR=sandbox_runs
AS_JSON=0
APPLY=both
DO_RUN=0
DO_SCORE=0
MAX_STEPS=0
RUNNER=auto
ORBIT_SEED=""

while [ $# -gt 0 ]; do
  case "$1" in
    --world)      WORLD="$2"; shift 2;;
    --orbit-seed) ORBIT_SEED="$2"; shift 2;;
    --seed)       SEED="$2"; shift 2;;
    --mutations)  MUTS="$2"; shift 2;;
    --out-dir)    OUT_DIR="$2"; shift 2;;
    --json)       AS_JSON=1; shift;;
    --apply)      APPLY="$2"; shift 2;;
    --run)        DO_RUN=1; shift;;
    --score)      DO_SCORE=1; shift;;
    --max-steps)  MAX_STEPS="$2"; shift 2;;
    --runner)     RUNNER="$2"; shift 2;;
    -h|--help)    usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [ -z "${WORLD:-}" ]; then
  echo "ERROR: missing world (provide positional <world.mu> or --world <world.mu>)" >&2
  usage
  exit 2
fi

test -f "$WORLD" || { echo "ERROR: world not found: $WORLD" >&2; exit 2; }
mkdir -p "$OUT_DIR"

python3 - "$WORLD" "$SEED" "$MUTS" "$OUT_DIR" "$AS_JSON" "$APPLY" "$DO_RUN" "$DO_SCORE" "$MAX_STEPS" "$RUNNER" "$ORBIT_SEED" <<'PY'
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

world_path = Path(sys.argv[1])
seed = int(sys.argv[2])
muts = int(sys.argv[3])
out_dir = Path(sys.argv[4])
as_json = bool(int(sys.argv[5]))
apply = sys.argv[6]
do_run = bool(int(sys.argv[7]))
do_score = bool(int(sys.argv[8]))
max_steps = int(sys.argv[9])
runner = sys.argv[10]
orbit_seed = sys.argv[11] if len(sys.argv) > 11 else "ping"

text = world_path.read_text(encoding="utf-8", errors="replace")

# Normalize baseline text to end with exactly one newline so comparisons are meaningful
baseline_text = text.rstrip("\n") + "\n"

stamp = int(time.time())
run_id = f"run_{stamp}_{seed}"
run_dir = out_dir / run_id
run_dir.mkdir(parents=True, exist_ok=True)

baseline_mu = run_dir / "baseline.mu"
baseline_mu.write_text(baseline_text, encoding="utf-8")

report: dict = {
    "run_id": run_id,
    "world_in": str(world_path),
    "seed": seed,
    "paths": {"run_dir": str(run_dir), "baseline_mu": str(baseline_mu)},
    "run": {"runner": runner, "enabled": True},
}
comparison: dict = {}

def _stage_world_for_rust_mu_programs(src_path: Path, tag: str, run_dir: Path) -> str:
    mu_dir = Path("rcx_pi_rust") / "mu_programs"
    mu_dir.mkdir(parents=True, exist_ok=True)
    run_id_env = os.environ.get("RCX_SANDBOX_RUN_ID") or run_dir.name or str(int(time.time()))
    world_name = f"__sandbox_{run_id_env}_{tag}"
    dst = mu_dir / f"{world_name}.mu"
    dst.write_text(src_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return world_name

def run_trace_and_score(world_name: str, label: str) -> dict:
    p = subprocess.run(
        [sys.executable, "-m", "rcx_pi.worlds.world_trace_cli",
         world_name, orbit_seed,
         "--max-steps", str(max_steps if max_steps > 0 else 50),
         "--json"],
        capture_output=True,
        text=True,
    )

    trace_payload = (p.stdout or "").strip()
    (run_dir / f"trace_{label}.json").write_text(trace_payload + "\n", encoding="utf-8")
    (run_dir / f"trace_{label}.stderr.txt").write_text((p.stderr or "") + "\n", encoding="utf-8")

    sp = subprocess.run(
        ["scripts/world_score.sh", "-", "--json"],
        input=trace_payload,
        capture_output=True,
        text=True,
    )
    (run_dir / f"world_score_{label}.stdout.json").write_text((sp.stdout or "") + "\n", encoding="utf-8")
    (run_dir / f"world_score_{label}.stderr.txt").write_text((sp.stderr or "") + "\n", encoding="utf-8")

    if sp.stdout.strip():
        try:
            score_obj = json.loads(sp.stdout)
        except Exception as e:
            score_obj = {"score": 0.0, "note": f"world_score JSON parse failed: {e}"}
    else:
        score_obj = {"score": 0.0, "note": (sp.stderr.strip() or f"world_score empty stdout rc={sp.returncode}")}

    return {
        "score": float(score_obj.get("score") or 0.0),
        "rule_signature": score_obj.get("rule_signature"),
        "trace_signature": score_obj.get("trace_signature"),
        "unique_states": score_obj.get("unique_states"),
        "steps_inferred": score_obj.get("steps_inferred"),
        "orbit_kind": score_obj.get("orbit_kind"),
        "orbit_period": score_obj.get("orbit_period"),
        "novelty_rate": score_obj.get("novelty_rate"),
        "loop_detected": score_obj.get("loop_detected"),
        "note": score_obj.get("note"),
    }

if runner != "trace-cli":
    # Even when we skip execution/scoring, we must still produce mutated.mu and keep JSON keys stable.
    rng = random.Random(seed)
    base_lines = baseline_text.splitlines()

    def _is_rule_line(ln: str) -> bool:
        s = ln.strip()
        return bool(s) and (not s.startswith("#")) and ("->" in s)

    rule_lines = [i for i, ln in enumerate(base_lines) if _is_rule_line(ln)]

    def mutate_rule_line_light(ln: str) -> str:
        if "->" not in ln:
            return ln
        left_raw, right_raw = ln.split("->", 1)
        left = left_raw.rstrip()
        right0 = right_raw.strip()
        choices = ["ra", "lobe", "sink"]
        if right0 in choices:
            newt = rng.choice([c for c in choices if c != right0])
            return left + " -> " + newt
        return ln

    n_mut = int(muts) if int(muts) > 0 else 5
    picks = rule_lines[:min(n_mut, len(rule_lines))]

    lines2 = base_lines[:]
    flips_applied = 0
    if apply in ("flip", "both"):
        for idx in picks:
            if 0 <= idx < len(lines2):
                before = lines2[idx]
                after = mutate_rule_line_light(before)
                if after != before:
                    flips_applied += 1
                lines2[idx] = after

    shuffles_applied = 0
    if apply in ("shuffle", "both") and len(picks) > 1:
        subset = [lines2[i] for i in picks if 0 <= i < len(lines2)]
        rng.shuffle(subset)
        k = 0
        for idx in picks:
            if 0 <= idx < len(lines2) and k < len(subset):
                lines2[idx] = subset[k]
                k += 1
        shuffles_applied = 1

    mutated_text = "\n".join(lines2).rstrip("\n") + "\n"
    mutated_mu_path = run_dir / "mutated.mu"
    mutated_mu_path.write_text(mutated_text, encoding="utf-8")
    report["paths"]["mutated_mu"] = str(mutated_mu_path)

    # Contract: when --run is requested but runner is "none"/skipped, still create run artifact files.
    # These stubs keep the tool outputs stable for tests and downstream scripts.
    baseline_out = run_dir / "baseline.out.txt"
    baseline_err = run_dir / "baseline.err.txt"
    mutated_out  = run_dir / "mutated.out.txt"
    mutated_err  = run_dir / "mutated.err.txt"
    baseline_out.write_text("runner skipped (runner != trace-cli)\n", encoding="utf-8")
    baseline_err.write_text("", encoding="utf-8")
    mutated_out.write_text("runner skipped (runner != trace-cli)\n", encoding="utf-8")
    mutated_err.write_text("", encoding="utf-8")
    report["paths"]["baseline_out"] = str(baseline_out)
    report["paths"]["mutated_out"]  = str(mutated_out)

    report["metrics"] = {
        "flips_applied": flips_applied,
        "shuffles_applied": shuffles_applied,
        "mutated_rule_indices": picks,
    }

    report["run"]["enabled"] = False
    report["run"]["note"] = f"runner section skipped (runner={runner})"
    report["run"]["baseline"] = {"enabled": False, "note": "no execution (runner != trace-cli)"}
    report["run"]["mutated"]  = {"enabled": False, "note": "no execution (runner != trace-cli)"}

    report["comparison"] = {
        "enabled": True,
        "note": "comparison/scoring skipped (runner != trace-cli); mutated.mu still produced",
    }
else:
    rng = random.Random(seed)

    base_lines = baseline_text.splitlines()

    def _is_rule_line(ln: str) -> bool:
        s = ln.strip()
        return bool(s) and (not s.startswith("#")) and ("->" in s)

    rule_lines = [i for i, ln in enumerate(base_lines) if _is_rule_line(ln)]


    # Exclude core stepping rules from mutation TARGETS (omega/expand/collapse stay frozen)

    def _lhs_of_rule_line(ln: str) -> str:

        return ln.split('->', 1)[0].strip() if '->' in ln else ''

    def _is_core_lhs(lhs: str) -> bool:

        return lhs.startswith('[omega') or lhs.startswith('[expand') or lhs.startswith('[collapse')

    rule_lines = [i for i in rule_lines if not _is_core_lhs(_lhs_of_rule_line(base_lines[i].strip()))]

    # Rewrite-cycle lines are the ones that actually govern your [omega] <-> [expand] behavior.
    cycle_rules: list[int] = []
    for i, ln in enumerate(base_lines):
        s = ln.strip()
        if (not s) or s.startswith("#") or ("->" not in s):
            continue
        lhs, rhs = s.split("->", 1)
        lhs = lhs.strip()
        rhs = rhs.strip()
        if rhs.startswith("rewrite(") and (lhs.startswith("[omega,") or lhs.startswith("[expand,")):
            cycle_rules.append(i)

    def swap_omega_expand(s: str) -> str:
        if "omega" in s:
            return s.replace("omega", "__TMP__", 1).replace("expand", "omega", 1).replace("__TMP__", "expand", 1)
        if "expand" in s:
            return s.replace("expand", "__TMP__", 1).replace("omega", "expand", 1).replace("__TMP__", "omega", 1)
        return s

    def mutate_rule_line(ln: str) -> str:
        if "->" not in ln:
            return ln

        left_raw, right_raw = ln.split("->", 1)
        left = left_raw.rstrip()
        right0 = right_raw.strip()

        choices = ["ra", "lobe", "sink"]

        # --- rewrite(...) rules: do a real structural mutation (not a no-op swap) ---
        if right0.startswith("rewrite("):
            lhs = left.strip()

            # Special-case the omega/expand cycle rules so we actually change the seed's behavior.
            if lhs.startswith("[omega,"):
                # Break the omega<->expand 2-cycle by nesting or routing to collapse.
                candidates = [
                    "rewrite([expand,[x]])",
                    "rewrite([collapse,[x]])",
                    "rewrite([expand,[x]])",
                ]
                candidates = [c for c in candidates if c != right0]
                if candidates:
                    return f"{left} -> {candidates[0]}"

            if lhs.startswith("[expand,"):
                candidates = [
                    "rewrite([expand,[x]])",
                    "rewrite([collapse,[x]])",
                    "rewrite([expand,[x]])",
                ]
                candidates = [c for c in candidates if c != right0]
                if candidates:
                    return f"{left} -> {candidates[0]}"

            # Generic fallback: simple omega/expand token swap (can still help elsewhere)
            r = right0
            if "omega" in r or "expand" in r:
                r1 = r.replace("omega", "__TMP__", 1).replace("expand", "omega", 1).replace("__TMP__", "expand", 1)
                if r1 != r:
                    return f"{left} -> {r1}"

            return ln

        # --- terminal targets ---
        if right0 in choices:
            newt = rng.choice([c for c in choices if c != right0])
            return f"{left} -> {newt}"

        return ln
        left_raw, right_raw = ln.split("->", 1)
        left = left_raw.rstrip()
        right0 = right_raw.strip()

        choices = ["ra", "lobe", "sink"]

        if right0.startswith("rewrite("):
            right1 = swap_omega_expand(right0)
            l = left.strip()
            # avoid trivial self-identity if possible
            if l.startswith("[omega") and "rewrite([omega" in right1:
                right1 = right1.replace("rewrite([omega", "rewrite([expand", 1)
            if l.startswith("[expand") and "rewrite([expand" in right1:
                right1 = right1.replace("rewrite([expand", "rewrite([omega", 1)
            if right1 != right0:
                return f"{left} -> {right1}"
            return ln

        if right0 in choices:
            new = rng.choice([c for c in choices if c != right0])
            return f"{left} -> {new}"

        return ln

    n_mut = int(muts) if int(muts) > 0 else 5
    HOT_PATTERNS = ("[hook", "rewrite([hook", "[lobe", "[sink")

    # Rules that are typically "dead picks" for orbit seeds like [omega,[a]] because they don't affect the stepping surface.
    DEAD_PREFIXES = ("[sink,", "[null,")
    def _is_dead_rule(i: int) -> bool:
        s = base_lines[i].lstrip()
        return any(s.startswith(p) for p in DEAD_PREFIXES)

    hot = [i for i in rule_lines if any(p in base_lines[i] for p in HOT_PATTERNS)]
    cold = [i for i in rule_lines if i not in hot]
    # Drop dead-end rules from mutation target pools
    hot = [i for i in hot if not _is_dead_rule(i)]
    cold = [i for i in cold if not _is_dead_rule(i)]

    rng.shuffle(hot)
    rng.shuffle(cold)

    picks = (hot + cold)[:min(n_mut, len(rule_lines))]



    # Post-pick scrub: remove dead picks and refill from eligible rules

    picks = [i for i in picks if not _is_dead_rule(i)]

    eligible = [i for i in rule_lines if (i not in picks) and (not _is_dead_rule(i))]

    need = max(0, min(n_mut, len(rule_lines)) - len(picks))

    if need and eligible:

        rng.shuffle(eligible)

        picks += eligible[:need]

    # --- post-pick guardrails: core rules never mutate; hook must be reachable ---
    def _lhs_of_idx(i: int) -> str:
        try:
            s = base_lines[i].strip()
        except Exception:
            return ''
        if (not s) or s.startswith('#') or ('->' not in s):
            return ''
        return s.split('->', 1)[0].strip()

    def _is_core_lhs(lhs: str) -> bool:
        return lhs.startswith('[omega,') or lhs.startswith('[expand,') or lhs.startswith('[collapse')

    # 1) Drop any accidentally-selected core rules (belt + suspenders)
    picks = [i for i in picks if (not _is_core_lhs(_lhs_of_idx(int(i))))]

    # 2) Force include the hook rule if present (so mutations can affect the orbit)
    hook_rules = [i for i, ln in enumerate(base_lines) if ln.strip().startswith('[hook,x]') and ('->' in ln) and (not ln.strip().startswith('#'))]
    if hook_rules:
        if all(int(i) != int(hook_rules[0]) for i in picks):
            picks = [int(hook_rules[0])] + [int(i) for i in picks]
    else:
        report.setdefault('notes', []).append('note: no [hook,x] rule found to force-pick')

    # If muts is small, force inclusion of a cycle rule if we have one.
    if cycle_rules and (len(picks) < 2 or all(i not in cycle_rules for i in picks)):
        picks = list(dict.fromkeys((cycle_rules[:1] + picks)))
        # POST_FORCE_SCRUB_HOOK_V2: after cycle-rule forcing, re-scrub core picks and force-include hook
        def _lhs_of_idx_post(i: int) -> str:
            try:
                s = base_lines[int(i)].strip()
            except Exception:
                return ''
            if (not s) or s.startswith('#') or ('->' not in s):
                return ''
            return s.split('->', 1)[0].strip()

        def _is_core_lhs_post(lhs: str) -> bool:
            return lhs.startswith('[omega,') or lhs.startswith('[expand,') or lhs.startswith('[collapse')

        picks = [int(i) for i in picks]
        picks = [i for i in picks if (not _is_core_lhs_post(_lhs_of_idx_post(i)))]

        hook_rules = [i for i, ln in enumerate(base_lines)
                      if ln.strip().startswith('[hook,x]') and ('->' in ln) and (not ln.strip().startswith('#'))]
        if hook_rules:
            h = int(hook_rules[0])
            if all(int(i) != h for i in picks):
                picks = [h] + picks

        picks = list(dict.fromkeys(picks))

    mutated_mu_path = run_dir / "mutated.mu"
    os.environ.setdefault("RCX_SANDBOX_RUN_ID", run_dir.name)

    base_world_path = run_dir / "__sandbox_baseline_world.mu"
    base_world_path.write_text(baseline_text, encoding="utf-8")
    base_world_name = _stage_world_for_rust_mu_programs(base_world_path, "baseline", run_dir)

    base_score = run_trace_and_score(base_world_name, "baseline")
    base_sig = base_score.get("trace_signature")

    best_mut_score = None
    best_mut_text = None

    max_attempts = 40
    for attempt in range(1, max_attempts + 1):
        lines2 = base_lines[:]  # list of lines

        if apply in ("flip", "both", "shuffle"):
            for idx in picks:
                if 0 <= idx < len(lines2):
                    ln = lines2[idx]
                    if ln.lstrip().startswith('[omega,') or ln.lstrip().startswith('[expand,') or ln.lstrip().startswith('[collapse]'):
                        lines2[idx] = ln
                    else:
                        lines2[idx] = mutate_rule_line(lines2[idx])

        if apply in ("shuffle", "both") and len(picks) > 1:
            subset = [lines2[i] for i in picks if 0 <= i < len(lines2)]
            rng.shuffle(subset)
            k = 0
            for idx in picks:
                if 0 <= idx < len(lines2) and k < len(subset):
                    lines2[idx] = subset[k]
                    k += 1

        mutated_text = "\n".join(lines2).rstrip("\n") + "\n"

        # Guard against pure no-op (e.g., only whitespace differences)
        if mutated_text == baseline_text and cycle_rules:
            j = rng.choice(cycle_rules)
            # Make omega self-nest (cycle breaker) on that cycle rule
            ln = lines2[j]
            if "->" in ln:
                left_raw, _ = ln.split("->", 1)
                left = left_raw.rstrip()
                # forced_semantic_mutation DISABLED: would have written rewrite([omega,[x]])
                lines2[j] = lines2[j]

                mutated_text = "\n".join(lines2).rstrip("\n") + "\n"
                report.setdefault("notes", []).append("forced_semantic_mutation: DISABLED (blocked omega self-nesting)")

        mutated_mu_path.write_text(mutated_text, encoding="utf-8")

        mut_world_path = run_dir / f"__sandbox_mutated_world_a{attempt}.mu"
        mut_world_path.write_text(mutated_text, encoding="utf-8")
        mut_world_name = _stage_world_for_rust_mu_programs(mut_world_path, f"mutated_a{attempt}", run_dir)

        mut_score = run_trace_and_score(mut_world_name, "mutated")
        mut_sig = mut_score.get("trace_signature")

        report.setdefault("mutation_attempts", []).append({
            "attempt": attempt,
            "mutated_rule_indices": picks,
            "baseline_trace_signature": base_sig,
            "mutated_trace_signature": mut_sig,
            "mutated_world_file": mut_world_name,
        })

        best_mut_score = mut_score
        best_mut_text = mutated_text

        if base_sig and mut_sig and base_sig != mut_sig:
            break

    if best_mut_text is not None:
        mutated_mu_path.write_text(best_mut_text, encoding="utf-8")

    comparison["scores"] = {"baseline": base_score, "mutated": best_mut_score}
    report["comparison"] = comparison

    # Compatibility debug filenames
    (run_dir / "trace_raw.json").write_text((run_dir / "trace_baseline.json").read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "world_score_stdout.json").write_text((run_dir / "world_score_baseline.stdout.json").read_text(encoding="utf-8"), encoding="utf-8")

report_path = run_dir / "report.json"
report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")



# CONTRACT SHIM: normalize report for stable JSON contracts (no obj dependency)
def _ensure(d: dict, key: str, default):
    if key not in d or d[key] is None:
        d[key] = default
    return d[key]

# Ensure run subtree exists
run = _ensure(report, 'run', {})
run.setdefault('enabled', True)
run.setdefault('runner', runner)

# Ensure baseline/mutated subtrees exist
b = _ensure(run, 'baseline', {})
m = _ensure(run, 'mutated', {})

# Default contract flags
for side in (b, m):
    side.setdefault('enabled', False)
    side.setdefault('json_ok', False)

# Motif gate contract: omega-cli asked to run on world-like .mu -> mark skipped
if (run.get('runner') == 'omega-cli'):
    wt = ''
    try:
        wt = Path(world_path).read_text(encoding='utf-8', errors='replace')
    except Exception:
        wt = ''
    is_world_like = any(('->' in ln) and (not ln.lstrip().startswith('#')) for ln in wt.splitlines())
    if is_world_like:
        b['skipped'] = True
        m['skipped'] = True
        b.setdefault('note', 'skipped: omega-cli expects motif input, got world-like .mu')
        m.setdefault('note', 'skipped: omega-cli expects motif input, got world-like .mu')

# Ensure comparison subtree exists and has scores keys even when runner is none/skip
cmp = _ensure(report, 'comparison', {})
cmp.setdefault('enabled', bool(do_score))
cmp.setdefault('scores', {'baseline': None, 'mutated': None})
cmp.setdefault('snapshot_integrity', None)

# Persist report.json for humans/debugging
report_path = run_dir / 'report.json'
report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

# Emit single JSON object to stdout
print(json.dumps(report))
PY
