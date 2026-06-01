# Commit Evidence Guard Setroles Show 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: commit-evidence-guard-setroles-show-2026-06-01
Phase-A-Lock: LOCKED
Purpose: Narrow structural fix for the 2026-05-30 standalone NEEDS_PHASE_B footgun: a commit handoff whose evidence_command read env-AWARE EFFECTIVE state (`python3 mu/tools/executors/set_roles.py --show`) was paired with a COMMITTED-config claim; the env-aware output (EFFECTIVE reviewer + an env-shadow warning) contradicted the committed claim, so the Codex pre-commit supervisor correctly rejected the package after gates 1-10 already passed -- wasting a full supervisor cycle. Add a build-time guard in commit_executor's handoff construction (build_commit_handoff and/or _validate_tracker_note_text) that REJECTS a tracker-note evidence_command which reads env-aware effective-state tooling -- scoped to the EXACT observed footgun: an evidence_command literally containing both `set_roles.py` and `--show` -- with a clear message directing the author to a committed-state read instead (e.g. `grep -A2 role_agents mu/tools/executors/executor_config.json` or `git diff`). This is a NARROW literal-pattern check (closed edge surface), NOT a general env-aware-command detector (that class diverges in review). Do NOT broaden beyond the `set_roles.py` + `--show` literal pattern.

## Scope

Tooling-only change (L4_ENABLER; touches NO runtime dir). Explicit in-scope files:

- `mu/tools/executors/commit_executor.py` -- in the handoff-construction path (`build_commit_handoff` and/or `_validate_tracker_note_text`), reject a tracker-note `evidence_command` whose text contains BOTH the literal `set_roles.py` AND the literal `--show`, raising a clear build-time error that names a committed-state-read alternative (e.g. `grep -A2 role_agents mu/tools/executors/executor_config.json` or `git diff`). Match ONLY that literal pair; leave every other `evidence_command` untouched.
- `mu/tests/tools/test_commit_executor_receipt.py` -- ADD a regression test to this EXISTING file (it already exercises `build_commit_handoff`, so the test-file count stays flat and no growth-cap bump is needed): assert the guard REJECTS a `set_roles.py --show` `evidence_command` and ACCEPTS a committed-state `evidence_command` (e.g. a grep / pytest / git-diff command).

No other files or directories are in scope. Code is cited by path and function name only; no file:line references (doc-governance + the control-packet line-ref lint).

- `reports/deferred/non_blocking/commit-evidence-guard-setroles-show-2026-06-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks for this wave (from the `[NEXT-CODEX-POST-REDTEAM]` tracker note for `commit-evidence-guard-setroles-show-2026-06-01` in TASKS.md; evidence_delta items 1-3):

1. In `mu/tools/executors/commit_executor.py`, add a build-time guard in the handoff-construction path (`build_commit_handoff` / `_validate_tracker_note_text`) that rejects a tracker-note `evidence_command` literally containing both `set_roles.py` and `--show`, with an error message that names a committed-state-read alternative.
2. In `mu/tests/tools/test_commit_executor_receipt.py`, add ONE regression test proving the guard REJECTS a `set_roles.py --show` evidence_command and ACCEPTS a committed-state evidence_command.

Both items are still pending in current code: the cited `mu/tools/executors/commit_executor.py` and `mu/tests/tools/test_commit_executor_receipt.py` exist (the test file already exercises `build_commit_handoff`), but neither the literal-pair guard nor its regression test is asserted by this wave yet.

## Constraints

What is explicitly NOT in scope:

- Do NOT broaden the guard beyond the exact `set_roles.py` + `--show` literal pair. NO general env-aware-command detector, NO heuristic, NO regex over arbitrary "effective-state" tooling -- that class diverges in review.
- Do NOT touch any runtime dir (`mu/host/`, `rcx_pi/selfhost/`). This is L4_ENABLER, tooling-only.
- Do NOT create new files. The regression test is ADDED to the existing `mu/tests/tools/test_commit_executor_receipt.py`; no new test file, no growth-cap bump.
- Do NOT modify other `evidence_command` validation paths or any other executor surface.
- Do NOT add file:line references or hardcoded counts to this packet (doc-governance).

## Stop conditions

- STOP and request founder/reviewer guidance if the fix cannot be expressed as the narrow `set_roles.py` + `--show` literal pair (e.g. the footgun recurs through a differently-worded env-aware command) -- do NOT widen to a general detector without a new decision.
- STOP if the guard would require touching a runtime dir or any file outside the two in-scope paths.
- STOP if adding the regression test would require a new test file or a growth-cap bump.
- STOP after the two in-scope edits land and the validation gate passes; do NOT pursue adjacent refactors of the handoff-construction path.
- Phase A STOP (this turn): rewrite the packet only. Do NOT implement the guard or edit `commit_executor.py` / the test in this turn; implementation happens in Phase B.

## Acceptance criteria

- `build_commit_handoff` / `_validate_tracker_note_text` raise a clear build-time error when a tracker-note `evidence_command` contains both `set_roles.py` and `--show`, and the message names a committed-state-read alternative.
- An `evidence_command` that does NOT contain that literal pair is accepted unchanged (no behavior change for any other command).
- A regression test in `mu/tests/tools/test_commit_executor_receipt.py` covers BOTH the reject (`set_roles.py --show`) and the accept (committed-state command) cases.
- Validation gate passes: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- No new files; no growth-cap bump; no runtime dir touched; no file:line references in this packet.

## Grounding / Authorization

- TASKS.md authorizes this wave under the `[NEXT-CODEX-POST-REDTEAM]` tracker note for `commit-evidence-guard-setroles-show-2026-06-01` (Class: L4_ENABLER; target_gate_id: G8; primary_blocker_class: INTEGRATION; primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES; bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP; boot0_track_id: V1; boot0_progress_state: HOLD).
- Governing packet: this file (`reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md`).
- Indicator artifact: `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`, collected via `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id commit-evidence-guard-setroles-show-2026-06-01 --output reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`.
- Evidence command (validation gate): `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- FOUNDER_OVERRIDE:commit-evidence-guard-setroles-show-2026-06-01
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md; the same-wave `FOUNDER_OVERRIDE:commit-evidence-guard-setroles-show-2026-06-01` line above lets commit automation derive the same-wave override mechanically for commit-gate + pre-push adjacency-cap clearance.

## Request from Post-Merge Supervisor

Narrow structural fix for the 2026-05-30 standalone NEEDS_PHASE_B footgun: a commit handoff whose evidence_command read env-AWARE EFFECTIVE state (`python3 mu/tools/executors/set_roles.py --show`) was paired with a COMMITTED-config claim; the env-aware output (EFFECTIVE reviewer + an env-shadow warning) contradicted the committed claim, so the Codex pre-commit supervisor correctly rejected the package after gates 1-10 already passed -- wasting a full supervisor cycle. Add a build-time guard in commit_executor's handoff construction (build_commit_handoff and/or _validate_tracker_note_text) that REJECTS a tracker-note evidence_command which reads env-aware effective-state tooling -- scoped to the EXACT observed footgun: an evidence_command literally containing both `set_roles.py` and `--show` -- with a clear message directing the author to a committed-state read instead (e.g. `grep -A2 role_agents mu/tools/executors/executor_config.json` or `git diff`). This is a NARROW literal-pattern check (closed edge surface), NOT a general env-aware-command detector (that class diverges in review). Do NOT broaden beyond the `set_roles.py` + `--show` literal pattern.

Routed next-candidate:
commit-evidence-guard-setroles-show-2026-06-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `commit-evidence-guard-setroles-show-2026-06-01`
- Active packet: `reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md`
- Indicator artifact: `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md`
  - `reports/deferred/non_blocking/commit-evidence-guard-setroles-show-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `commit-evidence-guard-setroles-show-2026-06-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/commit-evidence-guard-setroles-show-2026-06-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `commit-evidence-guard-setroles-show-2026-06-01`
- Active packet: `reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7851a2f990bd69c942c823cca822da7a583cc44f95a83847e7a9429fa5ac635c`
- Indicator artifact: `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/commit_evidence_guard_setroles_show_2026-06-01.md`
  - `reports/deferred/non_blocking/commit-evidence-guard-setroles-show-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/commit-evidence-guard-setroles-show-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
