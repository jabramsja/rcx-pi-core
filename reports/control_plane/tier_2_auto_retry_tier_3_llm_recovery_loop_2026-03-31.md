# Tier 2 Auto-Retry + Tier 3 LLM Recovery Loop

Date: 2026-03-31
Status: Phase A LOCKED
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave class: L4_ENABLER

---

## Scope

Implement Tier 2 (auto-retry with adjustment) and Tier 3 (LLM diagnosis loop) in `mu/tools/executors/recovery_gate.py`. Wire Tier 2 into the dispatcher. Design doc: `mu/docs/agents/PipelineRecovery.v0.md`.

### Files in scope
- `mu/tools/executors/recovery_gate.py` — add Tier 2 fix functions + Tier 3 recovery loop
- `mu/tools/executors/executor_dispatch.py` — wire Tier 2 retry adjustments into dispatcher
- `mu/tests/tools/test_recovery_gate.py` — tests for Tier 2 + Tier 3
- `mu/tests/tools/test_executor_dispatch.py` — integration tests for Tier 2 in dispatcher

### Files NOT in scope
- `phase_a_executor.py`, `phase_b_executor.py`, `commit_executor.py` — no changes
- `bridge_supervisor.py`, `bridge_adapters.py` — recovery does NOT use bridge stack
- Runtime files under `rcx_pi/selfhost/` or `mu/host/` — no changes

---

## Work Items

### W1. Tier 2 auto-retry functions in recovery_gate.py

Four fix functions matching the design doc:

1. **`fix_process_timeout`** — Read current timeout from executor_config.json, increase by 50% (capped at 2x original), write adjusted value to `RCX_RECOVERY_TIMEOUT_OVERRIDE` env var. Return the new timeout.
2. **`fix_transient_kill`** — No-op fix (just marks as retryable). The dispatcher already retries; this function signals "safe to retry with same parameters."
3. **`fix_aggregation_hang`** — Clear bridge state files (`.agent_bus/bridge.lock`, stale bridge DB jobs for this wave). Return list of cleared files.
4. **`fix_implementer_stale`** — Increase stale timeout via `RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE` env var (50% increase, capped 2x).

Register all four in `_TIER2_FIXES` dict (same pattern as `_TIER1_FIXES`).

### W2. Tier 2 dispatcher integration in executor_dispatch.py

In the recovery gate section of the retry loop (already wired):
- After `attempt_recovery()` returns with `tier == 2` and `recovered == True`:
  - Apply any env var overrides the fix function set
  - Grant one extra retry attempt (same `continue` pattern as Tier 1)
  - Log the adjustment: `[dispatch] Tier 2 recovery: {action} — retrying with adjusted parameters`

Currently `tier in (2, 3)` returns `not_implemented`. Change to:
- Tier 2 with registered fix: call fix, retry if fixed
- Tier 3: still `not_implemented` (separate work item W3)

### W3. Tier 3 LLM recovery loop in recovery_gate.py

New function `run_recovery_loop(repo_root, result, wave_id, max_iterations=3)`:

```
for i in range(max_iterations):
    1. Build diagnosis prompt (~2K tokens):
       - Failure class, tier, step, stderr (last 100 lines), stdout (last 50 lines)
       - Current git status --short
       - The specific gate/check that failed
    2. Call: subprocess.run(["claude", "--print", "-p", prompt], timeout=60, capture_output=True)
       - Model: inherited (no override — uses whatever claude defaults to)
       - NOT through bridge adapter stack (bootstrap paradox)
    3. Parse response: expect JSON with {"action": "shell"|"edit"|"skip"|"escalate", "commands": [...], "explanation": "..."}
    4. If action == "shell": run each command via subprocess.run(timeout=30)
       If action == "edit": apply edits (file_path, old_text, new_text)
       If action == "skip": return recovered=False with explanation
       If action == "escalate": return recovered=False, exhausted=True
    5. Verify: re-run the specific failed gate/check
       If passes: return recovered=True
       If fails: loop (next iteration gets the new error)
```

Safety constraints:
- Max 3 iterations
- 60s timeout per claude call, 30s per shell command
- No `rm -rf`, no `git push`, no `git reset --hard` in shell commands (denylist)
- Token budget: ~2000 input, ~500 output per iteration
- All attempts logged to recovery_log.json

### W4. Tests

**Tier 2 tests** (in test_recovery_gate.py):
- `test_fix_process_timeout_increases_timeout` — verify 50% increase, 2x cap
- `test_fix_transient_kill_returns_retryable` — verify it marks as retryable
- `test_fix_aggregation_hang_clears_bridge_state` — verify lock/state cleanup
- `test_fix_implementer_stale_increases_stale_timeout` — verify env var set
- `test_tier2_registered_in_fixes_map` — verify all 4 in _TIER2_FIXES

**Tier 3 tests** (in test_recovery_gate.py):
- `test_recovery_loop_diagnose_and_fix` — mock claude --print returning shell fix, verify it runs
- `test_recovery_loop_max_iterations` — verify stops after 3
- `test_recovery_loop_escalate_action` — verify escalate returns exhausted
- `test_recovery_loop_dangerous_command_blocked` — verify denylist blocks rm -rf etc
- `test_recovery_loop_timeout` — verify claude call timeout handled

**Dispatcher integration** (in test_executor_dispatch.py):
- `test_tier2_recovery_retries_with_adjustment` — verify Tier 2 grants retry
- `test_tier3_still_not_implemented` — verify Tier 3 returns not_implemented (wired in next wave)

---

## Constraints

- recovery_gate.py imports ONLY stdlib + executor_common.py (no bridge, no SDK agents)
- Tier 3 calls `claude --print` via subprocess, NOT through bridge_adapters
- No changes to runtime files
- No new files — all code goes in existing recovery_gate.py and existing test files

## Stop Conditions

- All W1-W4 work items implemented and tested
- Existing 311 tests still pass
- audit_fast green
- No runtime file changes

## Acceptance Criteria

- Tier 2 failures (timeout, transient kill, aggregation hang, implementer stale) are auto-fixed and retried
- Tier 3 recovery loop function (`run_recovery_loop`) exists with diagnosis → fix → verify cycle
- Tier 3 is **NOT wired into the dispatcher** — `attempt_recovery()` still returns `not_implemented` for tier 3 failures. Wiring is deferred to the next wave
- Basic dangerous command denylist in place (exact-match strings). Expanded pattern-based denylist deferred to next wave
- Basic repo-escape blocking for edits (resolve + prefix check). Repo-internal sensitive paths (`.git/config`) not yet blocked — deferred to next wave
- Tier 1 and Tier 2 recovery attempts are durably logged to recovery_log.json. Tier 3 logging deferred until Tier 3 is wired live
- Tests cover Tier 2 fix functions, recovery loop basics, and dispatcher integration

## Known Residue (deferred to next wave: RECOVERY-TIER3-WIRING)

- Tier 2 sequential timeout bumps can exceed 2x cap (re-bases on overridden config)
- Tier 3 denylist misses destructive git subcommand forms (pattern-based needed)
- Tier 3 edit containment allows `.git/config` mutation (needs sensitive-path blocklist)
- Tier 3 not durably logged until wired into dispatcher
- `needs_phase_b` over-classified as terminal in recovery_gate.py (should be Tier 3 recoverable)

## Grounding

- **Authorization:** `[PIPELINE-RECOVERY]` in TASKS.md NEXT section (founder-authorized 2026-03-31)
- **Design:** `mu/docs/agents/PipelineRecovery.v0.md` (Tier 2 §103-112, Tier 3 §114-142)
- **Prior work:** PR #704 (Phase 1 classifier + Tier 1), PR #705 (dispatcher wiring + hardening)
- **Motivation:** Pipeline failed today on structural wave — recovery gate fired `tier=3, recovered=False` because Tier 3 doesn't exist yet
