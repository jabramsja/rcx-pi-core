# Wave Packet: tier3-short-circuit-2026-04-17

## Status: Phase B (locked, implementing)
## Phase-A-Lock: LOCKED

## Goal

Close `reports/deferred/blocking/recovery_gate_tier3_unactionable_exhaust_2026-04-17.md`
by adopting **structural fix candidate #2: Adaptive iteration count**.

When `recovery_gate.run_recovery_loop` encounters a "no valid fix" response
from the recovery agent (`action: "skip"` or `action: "escalate"` with no
concrete commands to apply), advancing to iterations 2 and 3 produces 2 more
wasted codex-xhigh calls with the same diagnostic conclusion. Observed
2026-04-17 on PR #783 wave cascade: 3 × ~70s iterations, all returning
"unknown_error → escalate," consuming ~3.5 min and budget for zero new
information.

Candidate #2 terminates the loop early if iteration 1 returns a non-actionable
response. Candidate #1 (learning-store short-circuit) and candidate #3
(demote BOT_FINDINGS_PENDING to tier-2) are deferred — candidate #2 is the
smallest bounded structural fix for the observed wastage.

## Scope

Control-surface / tooling + tests only. 2 file edits + 1 wave packet.

**Files (3 total):**

- `mu/tools/executors/recovery_gate.py` — in `run_recovery_loop` (currently
  near lines 3080-3220), after parsing the agent's JSON response into
  `action` / `commands`: if `action in {"skip", "escalate"}` AND iteration
  number < `max_iterations - 1`, log "tier-3 iter N returned non-actionable
  action={action}; short-circuiting remaining iterations" and break out of
  the loop with `outcome = "short_circuited_non_actionable"`. The subsequent
  return path should record the short-circuit in the recovery_log.json +
  recovery_status.json with `exhausted=True` (same terminal semantics) but
  `detail` reflects the short-circuit reason. `_make_result(...)` signature
  may need a new kwarg or a new helper; pick the least-invasive shape.
- `mu/tests/tools/test_recovery_gate.py` — add 2 regression tests in a new
  class `TestTier3ShortCircuit`:
  - `test_skip_action_on_iter_1_short_circuits`: mock the recovery agent
    subprocess to return `{"action": "skip", "commands": [], "explanation": "..."}`,
    run `run_recovery_loop` with `max_iterations=3`, assert only 1 agent
    iteration was spawned + loop returned exhausted with
    short-circuit detail.
  - `test_shell_action_on_iter_1_continues_to_iter_2`: mock iter 1 to return
    a shell action + make the action fail verification; assert iter 2 runs
    (so we don't short-circuit on genuine attempts).
- `reports/control_plane/tier3_short_circuit_2026-04-17.md` — this packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, runtime, or any `*.js` file.

## Implementation Guidance for Phase B implementer (claude-opus-4-7)

1. Read `mu/tools/executors/recovery_gate.py:3080-3220` for the current
   `run_recovery_loop` structure. Identify the point where the agent's JSON
   response is parsed into `action`/`commands`.
2. Add the short-circuit check AFTER successful parse, BEFORE dispatching
   on action. Look for existing patterns like `if action == "skip":` —
   there is already branching on action type; the new behavior is "when
   action is non-actionable AND iter < max-1, break early."
3. Register the short-circuit outcome in `_log_tier3_attempt` / status
   updates so the recovery_log.json entry makes the reason visible.
4. Tests live in `mu/tests/tools/test_recovery_gate.py`. Model after the
   existing `TestHybridDelegateRuntime` class (uses FakePopen + monkeypatch
   to stub the agent subprocess).
5. Preserve backward compatibility: if `max_iterations == 1`, the
   short-circuit check has no effect (loop already exits normally).
6. Do NOT touch `recovery_gate.py` beyond the `run_recovery_loop` function
   body + associated helpers. No public API changes.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8 (reduces wasted recovery-agent budget + time on
  unactionable failures, enabling faster pipeline cycle time for future
  hardening waves)
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`
- **Evidence delta:**
  1. `recovery_gate.run_recovery_loop` short-circuits on non-actionable
     agent response (skip/escalate with empty commands) at iteration 1,
     saving up to 2 × codex-xhigh invocations per exhausted cycle
     (approximately 2-3 minutes + budget per observed PR #783-class
     recovery).
  2. Two new regression tests verify (a) short-circuit fires on non-actionable
     iter 1, (b) short-circuit does NOT fire on actionable iter 1 that later
     fails verification.
  3. Existing test_recovery_gate.py tests (847 as of PR #788) continue to
     pass unchanged.
- **Indicator artifact:** `reports/l4_wave_indicators/tier3-short-circuit-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:tier3-short-circuit-2026-04-17
  (founder authorized in-session via "continue" + "up to you" for
  autonomous progression through open hardening deferreds; wave also
  invoked via full pipeline dispatcher path per "try to use pipeline"
  directive.)

## Verification Plan

1. Phase B bridge review (codex reviewer) — must converge on no blocking
   findings. If reviewer flags scope expansion or alternate candidates
   preferred, defer to a future wave (do NOT re-architect in-line).
2. Step 8b targeted pytest on `test_recovery_gate.py` — 849 tests (847
   pre-existing + 2 new) must PASS.
3. Pre-push-fast ratchet sweep + `enforce_l4_execution_contract.py` PASS on
   L4_ENABLER.

## Stop Conditions

- Abort if pytest fails or any pre-existing test regresses.
- Abort if bridge review returns blocking findings on the short-circuit
  contract shape (e.g., reviewer prefers candidate #1 or #3).
- Abort if L4 contract enforcement rejects the classification.

## Closeout

On merge, commit_executor step 16 cleans up worktree + branch. Archive
`reports/deferred/blocking/recovery_gate_tier3_unactionable_exhaust_2026-04-17.md`
with `_CLOSED_by_PR<N>` suffix (performed by the implementer; PR # resolved
at commit time). 3 remaining pipeline-hardening deferreds stay open:
- `commit_executor_step16_cascade_block_2026-04-17.md`
- `pipeline_monitor_watcher_staleness_2026-04-17.md`
- `hybrid_recovery_inert_structural_gaps_2026-04-17.md` (3 sub-gaps)
- NEW (to file separately): `commit_executor_step15_commented_review_detection_2026-04-17.md`
