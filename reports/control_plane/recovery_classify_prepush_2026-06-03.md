# Recovery Classify Prepush 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-classify-prepush-2026-06-02
Class: L4_ENABLER (control-plane/pipeline tooling -- no runtime/substrate dir)
Phase-A-Lock: LOCKED
Authorization: FOUNDER_OVERRIDE:recovery-classify-prepush-2026-06-02 -- standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (L4_ENABLER control-plane/pipeline tooling; no runtime/substrate change). See "Grounding / Authorization".
Purpose: Fix `recovery_gate.classify_failure` so a PRE-PUSH pytest/test failure whose test CONTENT contains merge-state strings is classified `FailureClass.TEST_FAILURE` (recovery re-invokes the implementer to fix the failing test) instead of `FailureClass.PR_CONFLICTING` (which finds no PR -> `tier2_failed` recovered=False -> the wave STRANDS, observed 2026-06-02 on the post-merge-verify wave). The bounded fix evaluates the pre-push pytest/test-failure branch (`_looks_like_pre_push_pytest_failure` -> TEST_FAILURE) BEFORE the broad `pr_conflicting` substring match, while keeping the genuine PR-conflict path for ACTUAL conflicts.

## Scope

Files/directories in scope (L4_ENABLER -- control-plane/pipeline tooling only, no runtime/substrate dir):

- `mu/tools/executors/recovery_gate.py` -- modify `classify_failure` ONLY: reorder/guard so the pre-push pytest/test-failure classification (`_looks_like_pre_push_pytest_failure(step_lower, l4_signal)` -> TEST_FAILURE) is evaluated BEFORE the broad `pr_conflicting` substring match. Read-only use of the helper `_looks_like_pre_push_pytest_failure` and `FailureClass.{PR_CONFLICTING,TEST_FAILURE,PRE_PUSH_FAILED}`.
- `mu/tests/tools/test_recovery_gate.py` -- add the regression test(s) to the EXISTING file (no new test file -- growth cap).
- `reports/control_plane/recovery_classify_prepush_2026-06-03.md` -- this governing Phase A packet.
- `TASKS.md` -- `[NEXT-CODEX-POST-REDTEAM]` tracker-sync note for wave `recovery-classify-prepush-2026-06-02` (commit-handoff tracker sync only; the authorization note already exists).
- `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json` -- indicator artifact (generated mechanically by the indicator collection command).

Cite code by function name only; no file:line.

- `reports/deferred/non_blocking/recovery-classify-prepush-2026-06-02_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks for this wave (from the TASKS.md `[NEXT-CODEX-POST-REDTEAM]` note and the routed Post-Merge Supervisor request):

1. In `recovery_gate.classify_failure`, evaluate the pre-push pytest/test-failure classification (`_looks_like_pre_push_pytest_failure(step_lower, l4_signal)` -> `FailureClass.TEST_FAILURE`) BEFORE the broad `pr_conflicting` substring match (`mergeable=conflicting` / `mergestatestatus=dirty` / `mergestatestatus=behind` / `mergeable_state=behind` in `reason_lower` / `combined_lower` / `stdout_lower`).
2. Guard the reorder: classify TEST_FAILURE ahead of the substring match ONLY when the failure is a pre-push pytest failure (step contains `run_pre_push_script` OR the `pre-push-fast failed` signal, PLUS a pytest-assertion indicator), so a pre-push-fast test failure whose test CONTENT contains merge-state strings classifies TEST_FAILURE.
3. Preserve the EXPLICIT `result.get('failure_class') == 'pr_conflicting'` / embedded-stdout/stderr tag path AND a genuine PR-conflict path for ACTUAL conflicts (a real `mergeable=conflicting` signal from a PR-state check, on a non-pre-push step). Do NOT weaken classification of real conflicts.
4. Add regression coverage to the EXISTING `mu/tests/tools/test_recovery_gate.py` (no new test file -- growth cap):
   - status failed + step `run_pre_push_script` + a `pre-push-fast failed` / `AssertionError` signal whose text ALSO contains `mergestatestatus=dirty` -> classifies `TEST_FAILURE`, NOT `PR_CONFLICTING`.
   - a genuine PR-conflict result (real `mergeable=conflicting`, non-pre-push step) -> still classifies `PR_CONFLICTING`.
5. Run the validation gate (see Acceptance criteria) and collect the indicator artifact for the wave.

## Constraints

Explicitly NOT in scope:

- Do NOT change `fix_pr_conflicting`.
- Do NOT change the `FailureClass` enum (no new members, no renames).
- Do NOT change any other classification branch in `classify_failure` beyond the bounded reorder/guard above.
- Do NOT create a new test file -- extend the EXISTING `mu/tests/tools/test_recovery_gate.py` (growth cap).
- Do NOT touch runtime/substrate dirs (`rcx_pi/selfhost/`, `mu/host/`, seeds, scheduler, registry, projection, parity, or production `/mu` semantics). L4_ENABLER MUST NOT touch runtime dirs.
- No L3/JS parity change: `recovery_gate` is Python-only control-plane tooling; no `mu/host/js/` mirror is required because no projection semantics change.
- No file:line citations anywhere in the packet or docs (cite code by function name; doc-governance: no line numbers).

## Stop conditions

- STOP after the `classify_failure` reorder/guard plus the regression test(s) land and the validation gate is green; do not extend the fix beyond `classify_failure` and the existing test file.
- STOP and escalate (scope breach) if the fix appears to require modifying `fix_pr_conflicting`, the `FailureClass` enum, another classifier branch, or any runtime/substrate dir.
- STOP and narrow the guard if any genuine PR-conflict case (real `mergeable=conflicting`, non-pre-push step) stops classifying `PR_CONFLICTING` -- the pre-push guard is too broad.
- Phase-A-Lock MUST be LOCKED (bridge-converged) before Phase B implementation begins; do not implement from this UNLOCKED draft.

## Acceptance criteria

- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k "classify or pr_conflicting or pre_push or test_failure"`.
- New regression test proves: a pre-push test failure (step `run_pre_push_script`, `pre-push-fast failed`/`AssertionError`) whose text contains `mergestatestatus=dirty` -> `TEST_FAILURE`; and a genuine `mergeable=conflicting` non-pre-push result -> `PR_CONFLICTING`.
- `classify_failure` evaluates the pre-push pytest/test-failure branch -> `TEST_FAILURE` BEFORE the `pr_conflicting` substring match (matches the TASKS.md `progress_proof_after`).
- Diff is scoped to `classify_failure` + the existing `test_recovery_gate.py` only; `fix_pr_conflicting` and the `FailureClass` enum are unchanged.
- Test-file growth cap respected (no new test file added).
- Indicator artifact collected: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-classify-prepush-2026-06-02 --output reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`.

## Grounding / Authorization

- TASKS.md authority: `[NEXT-CODEX-POST-REDTEAM]` tracker-sync note (2026-06-03, recovery-classify-prepush-2026-06-02). Class: L4_ENABLER. target_gate_id: G8. Packet: `reports/control_plane/recovery_classify_prepush_2026-06-03.md`. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES. indicator_artifact_ref: `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- FOUNDER_OVERRIDE:recovery-classify-prepush-2026-06-02
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (L4_ENABLER control-plane/pipeline tooling fix; no runtime/substrate change). This mirrors the `FOUNDER_OVERRIDE:recovery-classify-prepush-2026-06-02` recorded in the TASKS.md tracker note for this wave, so commit automation can derive the same-wave override mechanically (commit-gate + pre-push adjacency-cap clearance).
- Governing packet: this file (`reports/control_plane/recovery_classify_prepush_2026-06-03.md`); routed next-candidate `recovery-classify-prepush-2026-06-02` from the Post-Merge Supervisor (verbatim request below).
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py -k "classify or pr_conflicting or pre_push or test_failure"`.
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id recovery-classify-prepush-2026-06-02 --output reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`.

## Request from Post-Merge Supervisor

Fix recovery_gate.classify_failure so a PRE-PUSH pytest/test failure is NOT misclassified as pr_conflicting. READ FIRST: `classify_failure` in mu/tools/executors/recovery_gate.py, the helper `_looks_like_pre_push_pytest_failure`, and FailureClass.PR_CONFLICTING / TEST_FAILURE / PRE_PUSH_FAILED. BUG: the pr_conflicting branch (the block returning FailureClass.PR_CONFLICTING) matches BROAD substrings -- 'mergeable=conflicting' / 'mergestatestatus=dirty' / 'mergestatestatus=behind' / 'mergeable_state=behind' in reason_lower/combined_lower/stdout_lower -- and is evaluated BEFORE the `_looks_like_pre_push_pytest_failure` -> TEST_FAILURE classification. So a pre-push-fast pytest failure whose TEST CONTENT contains those merge-state strings (observed 2026-06-02: the _resolve_post_merge_verify_root regression test, which asserts 'dirty linked verify root must not run git merge --ff-only' and mocks git rev-parse origin/dev / worktree list) is misclassified pr_conflicting -> fix_pr_conflicting runs, finds no PR ('could not determine PR number'), tier2_failed recovered=False -> the wave STRANDS instead of recovery re-invoking the implementer to fix the failing test. PRECISE, BOUNDED FIX: reorder/guard classify_failure so the pre-push pytest/test-failure classification (`_looks_like_pre_push_pytest_failure(step_lower, l4_signal)` -> TEST_FAILURE) is evaluated BEFORE the pr_conflicting SUBSTRING match -- i.e. when the failure is a pre-push pytest failure (step contains run_pre_push_script OR the 'pre-push-fast failed' signal, plus a pytest-assertion indicator), classify TEST_FAILURE even if the text contains merge-state substrings. KEEP the EXPLICIT `result.get('failure_class') == 'pr_conflicting'` / embedded-stdout/stderr tag AND a genuine PR-conflict path for ACTUAL conflicts (a real mergeable=conflicting signal from a PR-state check, not a pre-push step). Do NOT change fix_pr_conflicting, the FailureClass enum, or other classifications. ADD A REGRESSION TEST to the EXISTING mu/tests/tools/test_recovery_gate.py (do NOT create a new test file -- growth cap): a result with status failed + step run_pre_push_script + a 'pre-push-fast failed'/AssertionError signal whose text ALSO contains 'mergestatestatus=dirty' classifies TEST_FAILURE, not PR_CONFLICTING; and a genuine PR-conflict result (real mergeable=conflicting, non-pre-push step) still classifies PR_CONFLICTING.

Routed next-candidate:
recovery-classify-prepush-2026-06-02

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `recovery-classify-prepush-2026-06-02`
- Active packet: `reports/control_plane/recovery_classify_prepush_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_classify_prepush_2026-06-03.md`
  - `reports/deferred/non_blocking/recovery-classify-prepush-2026-06-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-classify-prepush-2026-06-02`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-classify-prepush-2026-06-02_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-classify-prepush-2026-06-02`
- Active packet: `reports/control_plane/recovery_classify_prepush_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `fffa6517c10cc4c0f333054b39f0632d184a860973251ea4e3ca95c136e17fe7`
- Indicator artifact: `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery_classify_prepush_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery_classify_prepush_2026-06-03.md`
  - `reports/deferred/non_blocking/recovery-classify-prepush-2026-06-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-classify-prepush-2026-06-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
