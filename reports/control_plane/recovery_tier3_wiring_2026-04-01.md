# Recovery Tier 3 Wiring + Pipeline Gap Fixes

Date: 2026-04-01
Status: Phase A (design — not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Task: [RECOVERY-TIER3-WIRING]
Design reference: mu/docs/agents/PipelineRecovery.v0.md

---

## 1. Scope

**Files in scope (write):**
- `mu/tools/executors/recovery_gate.py` — Tier 3 wiring, `needs_phase_b` reclassification, denylist expansion, sensitive-path blocking
- `mu/tools/executors/executor_dispatch.py` — Tier 3 dispatch integration, `phase-a`/`phase-b` surface routing through recovery, timeout baseline fix
- `mu/tools/executors/commit_executor.py` — pre-commit pytest gate for affected test files
- `mu/tests/tools/test_recovery_gate.py` — unit tests for new and changed `recovery_gate` behavior
- `mu/tests/tools/test_executor_dispatch.py` — integration tests for dispatcher Tier 3 and surface behavior
- `mu/tests/tools/test_commit_executor_receipt.py` — commit-executor targeted pytest gate coverage

**Files in scope (read-only context):**
- `mu/docs/agents/PipelineRecovery.v0.md` — design spec
- `mu/tools/executors/executor_common.py` — shared utilities

---

## 2. Work Items

All 9 items from TASKS.md `[RECOVERY-TIER3-WIRING]`, grouped by file:

### recovery_gate.py

**(1) Wire `run_recovery_loop()` into `attempt_recovery()`.**
Currently Tier 3 falls through to a placeholder response. Replace that placeholder with a call to `run_recovery_loop(repo_root, result, wave_id)` and translate the loop result into the standard `_make_result()` format.

**(2) Reclassify `needs_phase_b` from Tier 4 terminal to Tier 3 recoverable.**
Move `"needs_phase_b"` out of `_TERMINAL_STATUSES`. Add a Tier 3 `FailureClass` value for it and detect it before the terminal-policy branch in `classify_failure()`, including embedded status lines in executor stdout.

**(4) Expand Tier 3 denylist to pattern-based.**
Current `_DANGEROUS_COMMANDS` uses exact substring matching. Add subcommand-form patterns for `git reset`, `git checkout --`, `git restore --source`, and `git restore --staged`.

**(5) Block edits to repo-internal sensitive paths.**
Reject Tier 3 fixes that propose reads or writes touching `.git/config` or `.git/hooks/`, both in shell commands and file-edit actions.

### executor_dispatch.py

**(3) Fix Tier 2 sequential timeout cap.**
`_apply_recovery_overrides()` must always re-base timeout bumps on the first pre-recovery baseline, not on a previously overridden timeout.

**(6) Surface command paths (`phase-a`, `phase-b`) route through dispatcher recovery.**
The modular entrypoints currently bypass `attempt_recovery()`. Route those surfaces through the same recovery-aware execution path used by the dispatcher.

**(7) P1 bot PR#706: Process-tree cleanup before timeout retry.**
Timeout retries must clean up the executor process tree before the next attempt so grandchildren do not survive the timeout kill.

**(8) P2 bot PR#706: Timeout bump cap re-bases on original baseline.**
Same root cause as item (3): compute bumps from the preserved original baseline, never from an already bumped timeout.

### commit_executor.py

**(9) Pre-commit pytest gate on affected test files.**
Manual `commit_executor.py` invocations bypass the existing Phase B pytest gate. Add a targeted pytest step before commit that maps staged Python files to mirrored tests and blocks commit on failure.

---

## 3. Constraints (Not in Scope)

- No changes to `bridge_supervisor`, `bridge_adapters`, or agent SDK imports from `recovery_gate.py`
- No changes to seeds, runtime kernel, or projection logic
- No Tier 4 behavior changes; escalation-only policy remains intact
- No learning-store implementation in this packet
- No weakening of existing dangerous-command coverage; only additive hardening
- Items (3) and (8) share a single implementation fix

---

## 4. Stop Conditions

- **STOP** if any change requires importing bridge-supervisor or agent SDK code into `recovery_gate.py`
- **STOP** if `needs_phase_b` reclassification breaks dispatcher terminal-outcome handling for actual founder-stop states
- **STOP** if Tier 3 wiring introduces nondeterministic tests
- **STOP** if process-tree cleanup requires a new dependency; use stdlib-only cleanup

---

## 5. Acceptance Criteria

1. `attempt_recovery()` returns a real recovery result for Tier 3 failure classes
2. `needs_phase_b` routes through Tier 3 recovery instead of Tier 4 escalation
3. Sequential Tier 2 timeouts re-base on the original timeout baseline
4. Dangerous-command coverage catches `git reset`, `git checkout --`, and `git restore --source/--staged`
5. Fixes touching `.git/config` or `.git/hooks/` are blocked
6. `phase-a` and `phase-b` surfaces route through recovery-aware execution
7. Timeout cleanup reaps the process tree before retry
8. `commit_executor.py` runs targeted pytest before commit
9. Existing recovery/dispatcher coverage continues to pass with the new behavior

---

## 6. Grounding

**TASKS.md authorization:** `[RECOVERY-TIER3-WIRING]` NEXT (2026-03-31, founder-authorized)
**Parent task:** `[PIPELINE-RECOVERY]` IN PROGRESS — this packet closes the Tier 3 wiring and immediate pipeline gaps exposed by PR #706
**Governing packet:** This file (`reports/control_plane/recovery_tier3_wiring_2026-04-01.md`)
**Depends on:** PR #706 (Tier 2 auto-retry + Tier 3 recovery loop function) — landed
**Design spec:** `mu/docs/agents/PipelineRecovery.v0.md`
**Lane:** control-surface (pipeline hardening)

---

## 7. 2026-04-01 Follow-Up: Tier 3 Response Hardening

Follow-up after commit `9c7e7c1c`:

- `mu/tools/executors/recovery_gate.py` now salvages prose-wrapped JSON responses from `claude --print` instead of requiring the whole response body to be raw JSON.
- The Tier 3 prompt now feeds the prior malformed response back into the next iteration and explicitly tells the recovery agent to use `skip` or `escalate` when the root cause is caller-supplied env/CLI state outside repo control.
- `mu/tests/tools/test_recovery_gate.py` now locks both regressions:
  - prose-wrapped fenced JSON still drives recovery
  - malformed prose is reflected into the next iteration prompt so the model can re-emit structured JSON instead of burning the remaining loop on the same mistake

Behavioral proof:

- Forced routed Phase A failure via `RCX_AGENT_PREFLIGHT_FORCE_FAIL=1 python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name recovery_tier3_recovery_probe_2026-04-01 --max-rounds 2 --json -v`
- Dispatcher automatically classified the Phase A SDK failure as `agent_review_crash` and entered Tier 3 recovery
- The patched Tier 3 loop returned a structured one-iteration `skip` for wave `recovery-tier3-recovery-probe-2026-04-01` instead of the earlier timeout + repeated prose parse-error pattern
- Recovery log evidence: `.agent_bus/recovery/recovery_log.json` entry `tier3_iter1_skip` explaining that `RCX_AGENT_PREFLIGHT_FORCE_FAIL=1` is caller-supplied parent-process state the loop cannot safely clear
