# BLOCKING: recovery_gate tier-3 exhausts on unactionable findings (no short-circuit)

**Date filed**: 2026-04-17
**Observed on**: PR #783 (observability-pane-and-deferred-doc-cleanup-2026-04-17)
**Severity**: BLOCKING (wastes ~5 min of codex-xhigh per cascade + blocks PR merge)

## Symptom

When commit_executor invokes `recovery_gate.attempt_recovery` on a
`bot_findings_pending` result where the underlying finding is unactionable
(false positive, non-retracted bot comment, or no fixable diff target),
Tier 3 runs 3 × `codex exec --json -m gpt-5.4 -c model_reasoning_effort="xhigh"`
iterations (max_iterations = 3). Each iteration does unbounded exploration on
an undiagnosable issue, burns ~1 min of codex-xhigh budget, returns "no valid
fix", and advances to the next iteration. After 3 iterations:
`recovery_status.json:state=tier3_exhausted, outcome=exhausted, recovered=False`
and commit_executor exits 1.

## Root cause (file:line)

- `mu/tools/executors/recovery_gate.py:3043-3215` — `run_recovery_loop()` has no
  classifier for "tier-3 will not make progress on this failure class for this
  error signal". Every invocation runs the full 3-iteration budget.
- `mu/tools/executors/recovery_gate.py:3135-3154` — Each iteration spawns
  `subprocess.Popen(codex_exec_cmd, timeout=spec.timeout_s)` with
  `spec.timeout_s = 1200` (per `bridge_config.json` codex adapter spec).
- No pre-invocation check: does the failure signal resemble a case where tier-3
  historically produced no fix? (Learning store exists for this class of check,
  per `check_learned_patterns` at `recovery_gate.py:5331`, but is not consulted
  for the "unactionable bot finding" case specifically.)

## Reproduction (verified 2026-04-17)

Wave A: tier-3 invoked at 22:18:42, finished 22:22:15 = 3m33s for 3 iterations.
Each iteration terminated normally (no codex timeout), just "no valid fix
proposed". `detail: max 3 Tier 3 iterations exhausted`. All 3 codex sessions
shown in `.scratch/recovery_agent_observability-pane-and-deferred-doc-cleanup-2026-04-17-unknown-{1,2,3}.txt`.
Reasoning logs show codex-xhigh trying to locate a "concrete repair target" but
concluding "No stderr/stdout, an unknown failing step, and empty git status
leave no concrete repair target" — an accurate diagnosis that the finding is
unactionable, but not actionable as a recovery.

## Structural fix candidates

1. **Learned-pattern short-circuit**: consult learning store BEFORE tier-3 invocation.
   If the fingerprint `bot_findings_pending + adapter_no_changes` has 2+ prior
   failures, skip tier-3 and jump directly to auto-defer + escalate.

2. **Adaptive iteration count**: start with 1 iteration; only advance to iteration 2
   if iteration 1 returned a concrete proposed-fix (even if it didn't verify).
   Terminates early on "no valid fix" without burning 3× budget.

3. **Failure-class allowlist for tier-3**: restrict `BOT_FINDINGS_PENDING` from
   tier-3 candidacy. Demote it to tier-2 (`_auto_defer_bot_findings` is
   effectively the tier-2 handler for this class).

## Acceptance criteria for the fix wave

- Pick candidate #1 (learning-store short-circuit) — aligns with existing
  `check_learned_patterns` infrastructure.
- Regression test in `mu/tests/tools/test_recovery_gate.py`: mock 2 prior
  failed fingerprint observations, verify tier-3 skipped on 3rd invocation.
- No runtime/substrate/host/projection/seed touches. L4_ENABLER class.
