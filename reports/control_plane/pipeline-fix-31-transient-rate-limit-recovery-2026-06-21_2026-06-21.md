# NEXT-CODEX-POST-REDTEAM - classify a transient adapter rate/session/spend-limit as TRANSIENT and back-off-retry instead of exhausting tier-3 recovery

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-fix-31-transient-rate-limit-recovery-2026-06-21
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL recovery hardening (founder-directed: always harden the pipeline when it breaks so the same failure self-heals). VERIFIED ROOT CAUSE: when a bridge adapter (e.g. claude) hits a TRANSIENT rate / session / spend / usage limit, it exits non-zero with a limit message in its output (observed on PR #1140: `Adapter 'claude' exited 1 ... You've hit your session limit - resets 3:50am`). recovery_gate.classify_failure only treats kill codes (`_TRANSIENT_KILL_CODES = {-9,-15,137}`) as transient; an exit-1 rate/session-limit is classified non-transient, so the 3 tier-3 recovery iterations all fail immediately and EXHAUST, stranding the wave even though the limit is temporary and resets on its own. CODE TRUTH (verified 2026-06-21): the existing TRANSIENT_KILL handler `fix_transient_kill` (recovery_gate.py) is a NO-OP -- it returns `retryable` "with same parameters" and performs NO wait; the dispatcher's recovered->retry path (executor_dispatch.py) then `continue`s IMMEDIATELY with no `sleep` and no reset-aware pause; and the per-tuple budget is `MAX_ATTEMPTS_PER_TUPLE = 2`. So routing a session-limit exit-1 through TRANSIENT_KILL would burn BOTH retries IMMEDIATELY against an un-reset limit and still exhaust tier-3 -- the very bug. FIX: detect the transient rate / session / spend / usage-limit text in the adapter result envelope inside classify_failure and classify it as a DEDICATED sibling transient class wired to a NEW handler that performs a REAL, BOUNDED, RESET-AWARE back-off WAIT before the retry proceeds (parse the reset time when the message carries one, e.g. `resets 3:50am`, and wait until it, capped at a bounded maximum; otherwise apply a fixed bounded back-off). The wait MUST be realized inside the recovery handler (the dispatcher does not pause) and MUST be bounded (a hard cap, never unbounded). Do NOT reuse the no-op `fix_transient_kill` and do NOT change kill-code behavior. Result: a wave that hits a temporary limit performs a bounded reset-aware WAIT and then continues, rather than burning immediate retries, exhausting tier-3, and stranding for a manual finish.

## Scope

Detect a transient adapter rate/session/spend/usage-limit in recovery_gate.classify_failure and route it to a NEW bounded, reset-aware back-off WAIT handler (the existing transient handler `fix_transient_kill` is a no-op that does not wait) instead of exhausting tier-3. Recovery tooling + an existing test file only; no runtime dirs; no new test file. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tools/executors/recovery_gate.py (MODIFY) -- in `classify_failure`, before the non-transient fall-through, detect a transient rate/session/spend/usage-limit signature in the adapter result envelope (the result output/error/detail text matching session/usage/spend/monthly/rate-limit phrasing) and return a DEDICATED sibling transient classification (a NEW `FailureClass`, NOT TRANSIENT_KILL -- TRANSIENT_KILL's handler `fix_transient_kill` is a no-op that does not wait, and re-purposing it would change kill-code behavior). Wire the new class in `FAILURE_HANDLERS` to a NEW handler that performs a real, BOUNDED, RESET-AWARE back-off WAIT: when the limit text carries a reset time, parse it and wait until reset, capped at a bounded maximum; otherwise wait a fixed bounded back-off. The wait MUST be performed inside the handler (the dispatcher's recovered->retry path continues immediately with no sleep) and MUST be injectable/mockable so the regression asserts the back-off without a real multi-second sleep. Optionally give the new class its own bounded `_max_attempts_for_failure` budget (analogous to UPSTREAM_CONNECTIVITY) so a couple of bounded waits can span a reset. Do NOT change the no-op `fix_transient_kill` or any kill-code behavior.
- mu/tests/tools/test_recovery_gate.py (MODIFY -- existing file, do NOT create a new test file) -- add a regression: a result dict carrying a session-limit message (exit code 1, limit text) classifies as the NEW sibling transient class (not test_failure/unknown_error and not TRANSIENT_KILL) AND its handler performs a bounded reset-aware WAIT -- assert, via an injected/patched sleep (no real multi-second sleep), that a positive bounded delay is applied, that a parsed reset time drives the wait when present, and that the delay is capped at the bounded maximum.
- reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read recovery_gate `classify_failure`, the FailureClass enum (TRANSIENT_KILL), `_TRANSIENT_KILL_CODES`, the `fix_transient_kill` handler (a NO-OP -- returns retryable, does NOT wait) + its FAILURE_HANDLERS wiring, the `_max_attempts_for_failure` budget (`MAX_ATTEMPTS_PER_TUPLE = 2`), and the shape of the `result` dict classify_failure receives (where the adapter output/error/detail text lives).
2. Add transient rate/session/spend/usage-limit detection in classify_failure that inspects the result envelope text (not just exit code) and returns the NEW sibling transient class; keep it precise (match limit phrasing) to avoid misclassifying real failures as transient.
3. Wire the new class in FAILURE_HANDLERS to a NEW dedicated handler that performs a REAL, BOUNDED, RESET-AWARE back-off WAIT before retry (parse the reset time when present and wait until it, capped at a bounded maximum; else a fixed bounded back-off). Realize the wait INSIDE the handler (the dispatcher does not pause) via an injectable sleep; never loop or wait unbounded. Do NOT reuse or modify the no-op `fix_transient_kill` (reusing it would not wait; modifying it would change kill-code behavior).
4. Add the regression to the EXISTING mu/tests/tools/test_recovery_gate.py (no new test file): assert the session-limit result classifies as the new sibling transient class AND that the handler applies a bounded reset-aware wait (via an injected sleep -- positive bounded delay, reset-time-driven when present, capped), with no real multi-second sleep.
5. Run the evidence_command; confirm the recovery_gate suite passes; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**). Recovery tooling + tests only.
- Do NOT create a new test file; add the regression to the existing mu/tests/tools/test_recovery_gate.py.
- Precise detection: match the rate/session/spend/usage/monthly-limit signature only; do NOT broaden so that genuine test_failure/unknown_error are misclassified as transient (that would mask real bugs).
- REQUIRED: a real, BOUNDED, RESET-AWARE back-off WAIT performed inside the handler before retry -- never an immediate retry and never an unbounded loop/wait (a hard cap is mandatory). Reusing the no-op `fix_transient_kill`, or relying on the dispatcher to pause (it does not -- it `continue`s immediately), is FORBIDDEN, because that retries immediately and burns the 2-attempt budget against an un-reset limit. Do NOT change `fix_transient_kill` or kill-code behavior.

## Stop conditions

- Stop done when the evidence_command passes (a session-limit result classifies as the new sibling transient class AND its handler applies a bounded reset-aware back-off WAIT, proven via an injected sleep) and the indicator is collected.
- Halt as POLICY_BOUND if the adapter result envelope does not actually carry the limit text at classify_failure (then the fix belongs in the adapter layer surfacing it) -- surface that precisely rather than guessing.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- classify_failure returns the NEW sibling transient classification (NOT TRANSIENT_KILL) for an adapter result carrying a rate/session/spend/usage-limit message (any exit code).
- That class's handler performs a REAL, BOUNDED, RESET-AWARE back-off WAIT before retry (reset-time-driven when present, capped at a bounded maximum; fixed bounded back-off otherwise), realized inside the handler and injectable for test -- no immediate retry, no unbounded wait.
- The no-op `fix_transient_kill`, kill-code transient behavior, and all other failure classifications are unchanged; genuine failures are NOT misclassified as transient.
- Regression in the existing test file proves BOTH the new classification AND the bounded reset-aware wait (via an injected sleep -- positive bounded delay, reset-aware, capped); no runtime dirs; no new test file.
- evidence_command clean; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21` is canonical for this packet's L4 fields.
- Authorization: Founder-directed 2026-06-21 (harden recovery so a transient limit never strands a wave again). This is the LANDED structural fix for the transient rate/session-limit tier-3 exhaustion that stranded PR #1140 (filing != fixing). Auto-authorized structural pipeline fix (feedback_manual_then_structural_autonomy).

FOUNDER_OVERRIDE:pipeline-fix-31-transient-rate-limit-recovery-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21`
- Active packet: `reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-31-transient-rate-limit-recovery-2026-06-21 --output reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-31-transient-rate-limit-recovery-2026-06-21`
- Active packet: `reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7e833b022db1c79198bb619136eb149526a7618ec08db6901163b6b38773ff73`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-fix-31-transient-rate-limit-recovery-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
