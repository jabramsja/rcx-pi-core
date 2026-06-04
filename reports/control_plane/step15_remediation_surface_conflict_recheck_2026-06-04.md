# Step15 Remediation Surface Conflict Recheck 2026-06-04

Date: 2026-06-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: step15-remediation-surface-conflict-recheck-2026-06-04
Phase-A-Lock: LOCKED
Class: L4_ENABLER (pipeline tooling; no runtime/substrate dir)
target_gate_id: G8
Purpose: Fix the parallel-lane stranding gap (#49): the commit_executor Step-15 bot-remediation CI-wait is NOT conflict-aware, so a PR that transitions to CONFLICTING during the Step-15 remediation CI poll (because a sibling lane merged) doom-polls for the pull_request-triggered required checks -- which GitHub silently skips on a CONFLICTING PR -- until the 900s surface-wait timeout, then concludes 'CI did not pass after remediation round N' and STRANDS the PR (verified on PR #1075: ~32 surface-wait iterations, zero conflict-handling, timeout, dispatcher exit). VERIFIED ROOT CAUSE: _wait_for_expected_pr_check_surface_to_pass accepts a midpoll_autoresolve context ({base_branch, branch_name}) that enables a mid-poll _check_pr_conflict_state + _try_auto_resolve_pr_conflict re-check (the #30/#31/#36 Step-14 fix); it defaults to None (disabled). _wait_for_pr_ci accepts midpoll_autoresolve and threads it to the surface-wait. BUT the Step-15-remediation CI-wait -- the _wait_for_pr_ci(...) call inside _attempt_bot_finding_remediation -- OMITS midpoll_autoresolve, so it is None and the conflict re-check is DISABLED for the remediation poll. FIX: pass midpoll_autoresolve to that _wait_for_pr_ci call inside _attempt_bot_finding_remediation, building the {base_branch, branch_name} context EXACTLY as the Step-14 caller builds it (the Step-14 caller constructs midpoll_autoresolve={base_branch: base_branch, branch_name: target_branch}: the branch_name key = target_branch -- the PR head branch _attempt_bot_finding_remediation already receives and already pushes to; the base_branch key = the wave's base branch = the base_branch the Step-14 caller passes = handoff['base_branch'] = dev = the branch origin/{base_branch} is fetched and merged FROM, which _attempt_bot_finding_remediation does NOT currently receive and so must be threaded in from its caller _run_post_commit_pipeline where base_branch is already a parameter; NEVER put target_branch in the base_branch key -- it is the head in this path, so merging origin/{target_branch} would self-merge the head and never pull the sibling-lane base), so a remediation-time concurrent-merge CONFLICTING transition is re-checked and _try_auto_resolve_pr_conflict is re-fired once (base merged in; the repush re-triggers the skipped pull_request workflows) instead of doom-polling to timeout -- mirroring Step-14 exactly. Cite code by FUNCTION NAME only; NO file:line in the plan.

## Scope

Files/directories in scope:
- `mu/tools/executors/commit_executor.py` -- ONLY the `_wait_for_pr_ci` call inside `_attempt_bot_finding_remediation` (the Step-15 bot-remediation CI-wait), plus the minimal base-branch threading that call needs to build the `{base_branch, branch_name}` midpoll_autoresolve context (add a `base_branch` parameter to `_attempt_bot_finding_remediation` and pass it from `_run_post_commit_pipeline`, where `base_branch` is already in scope; the head -- `target_branch` -- is already received and needs no threading).
- `mu/tests/tools/test_commit_executor_step14_autoresolve.py` -- add ONE regression test to this EXISTING file (no new test file; growth cap).

L4_ENABLER: pipeline tooling only; NO runtime/substrate directory is touched.

- `reports/deferred/non_blocking/step15-remediation-surface-conflict-recheck-2026-06-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (cited by function name; no file:line):
1. READ FIRST, in `mu/tools/executors/commit_executor.py`: `_wait_for_expected_pr_check_surface_to_pass` (the midpoll_autoresolve gating + the conflict re-check loop), `_midpoll_conflict_recheck_before_ci_failure`, `_wait_for_pr_ci` (how it accepts + threads midpoll_autoresolve), the EXISTING Step-14 `_wait_for_pr_ci` call site (how it constructs the `{base_branch, branch_name}` dict -- mirror it), and the `_wait_for_pr_ci` call inside `_attempt_bot_finding_remediation` (the exact call-site to fix).
2. Pass `midpoll_autoresolve={base_branch: base_branch, branch_name: target_branch}` to the `_wait_for_pr_ci` call inside `_attempt_bot_finding_remediation`, built EXACTLY as the Step-14 caller builds it (the Step-14 caller constructs `{base_branch: base_branch, branch_name: target_branch}`). The mapping is verified against `_try_auto_resolve_pr_conflict`, which does `git fetch origin {base_branch}` + `git merge origin/{base_branch}` INTO `{branch_name}`:
   - `branch_name` key = `target_branch` -- the PR head branch `_attempt_bot_finding_remediation` ALREADY receives (and already pushes to via `git push origin target_branch`). No threading is needed for this value.
   - `base_branch` key = the wave's base branch -- the same `base_branch` the Step-14 caller passes (`= handoff['base_branch']`, i.e. `dev`); this is the branch `_try_auto_resolve_pr_conflict` fetches and merges FROM. `_attempt_bot_finding_remediation` does NOT currently receive `base_branch`, so thread it in: add a `base_branch` parameter to `_attempt_bot_finding_remediation` and pass it from the caller `_run_post_commit_pipeline`, where `base_branch` is already a parameter and is already passed to the Step-14 `midpoll_autoresolve` construction. (Fallback only if threading is somehow unavailable: derive the base via `gh pr view <pr_number> --json baseRefName` -- but threading from `_run_post_commit_pipeline` is the correct mirror.)
   - Do NOT map `target_branch` into the `base_branch` key. `target_branch` is the PR head in this path, so `_try_auto_resolve_pr_conflict` would `git fetch origin <head>` + `git merge origin/<head>` into `<head>` -- a self-merge that never pulls the sibling-lane base, leaving the CONFLICTING state unresolved and defeating the fix.
3. Add ONE regression test to the EXISTING `mu/tests/tools/test_commit_executor_step14_autoresolve.py`, mirroring the existing Step-14 autoresolve test: drive a mid-poll CONFLICTING transition during the Step-15-remediation CI-wait and assert `_try_auto_resolve_pr_conflict` is invoked AND the surface-wait does NOT return a timeout/ci_failure when the conflict auto-resolves. The fix-confirming assertion must fail on the un-fixed code.

## Constraints

What is NOT in scope:
- Edits limited to `commit_executor.py` (the remediation `_wait_for_pr_ci` call + minimal base-branch threading into `_attempt_bot_finding_remediation` from `_run_post_commit_pipeline`) and the EXISTING `test_commit_executor_step14_autoresolve.py`. No other files.
- Non-Step-14 / non-remediation `_wait_for_pr_ci` and surface-wait callers (those that pass `midpoll_autoresolve=None`) MUST stay behaviorally unchanged.
- NO new test file (growth cap; reuse the existing Step-14 autoresolve test file).
- NO runtime/substrate directory edits (L4_ENABLER, pipeline tooling only).
- Do NOT change `_wait_for_expected_pr_check_surface_to_pass`, `_midpoll_conflict_recheck_before_ci_failure`, `_wait_for_pr_ci`, or the Step-14 caller beyond the minimal threading needed to mirror Step-14; do not invent new parameters or new conflict-handling semantics.
- Cite code by FUNCTION NAME only; NO file:line citations in the packet.

## Stop conditions

- The fix would exceed the single remediation call-site + minimal base-branch threading (e.g., it would require changing surface-wait / conflict-recheck internals or `_wait_for_pr_ci` semantics) -> STOP and re-plan.
- Mirroring the Step-14 midpoll_autoresolve construction is not possible without changing a non-remediation caller's behavior -> STOP and surface as POLICY_BOUND.
- The change would touch a runtime/substrate directory (reclassifying off L4_ENABLER) or implicate any `/mu` structural surface -> STOP (the parent directive orders `/mu` structural waves last with a hard stop).
- The validation gate fails after the change -> STOP, diagnose with commands; do NOT push.

## Acceptance criteria

- `_attempt_bot_finding_remediation`'s `_wait_for_pr_ci` call passes a non-None `midpoll_autoresolve={base_branch: base_branch, branch_name: target_branch}` built EXACTLY as the Step-14 caller builds it (the `base_branch` key carries the wave base branch / `handoff['base_branch']`, threaded in from `_run_post_commit_pipeline`; the `branch_name` key carries `target_branch`, the head the function already receives); a remediation-time CONFLICTING transition triggers `_check_pr_conflict_state` + one `_try_auto_resolve_pr_conflict` re-fire that fetches and merges `origin/{base_branch}` (the real base, NOT the head) instead of doom-polling to the 900s timeout.
- Non-Step-14 / non-remediation callers still pass `midpoll_autoresolve=None` and remain behaviorally unchanged.
- The new regression test in the EXISTING `test_commit_executor_step14_autoresolve.py` fails on the un-fixed code and passes on the fixed code.
- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- No new file created; no runtime/substrate directory touched; no file:line citations in the packet.

## Grounding / Authorization

- Task: `[NEXT-CODEX-POST-REDTEAM]` -- UNPARKED (2026-03-28, founder-authorized) per `TASKS.md`; the queue stays open for bounded downstream pipeline-tooling work, which this wave is.
- Governing packet (this file): `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`.
- Same-wave authorization in `TASKS.md`: Tracker sync note (2026-06-04, step15-remediation-surface-conflict-recheck-2026-06-04) binds this wave and carries the L4 fields below. Packet: `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`.
- Class: L4_ENABLER. target_gate_id: G8. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES.
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`
- evidence_delta: commit_executor `_attempt_bot_finding_remediation` now receives `base_branch` (threaded from `_run_post_commit_pipeline`) and passes `midpoll_autoresolve={base_branch: base_branch, branch_name: target_branch}` to its `_wait_for_pr_ci` CI-wait (built EXACTLY as the Step-14 caller does), so the Step-15-remediation surface-wait re-checks conflict + auto-resolves a mid-poll CONFLICTING transition (fetch + merge `origin/{base_branch}` + repush) instead of doom-polling the skipped pull_request checks to the 900s timeout. Non-Step-14/non-remediation callers unchanged. Regression test added to the existing `test_commit_executor_step14_autoresolve.py`.
- indicator_artifact_ref: `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
- indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id step15-remediation-surface-conflict-recheck-2026-06-04 --output reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.
- FOUNDER_OVERRIDE:step15-remediation-surface-conflict-recheck-2026-06-04
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md (auto-appended by build_commit_handoff for commit-gate + pre-push adjacency-cap clearance); this is a control-surface L4_ENABLER pipeline-tooling fix with no runtime/substrate dir, so commit automation derives the same-wave override mechanically from the `FOUNDER_OVERRIDE:<wave_id>` above.

## Request from Post-Merge Supervisor

Fix the parallel-lane stranding gap (#49): the commit_executor Step-15 bot-remediation CI-wait is NOT conflict-aware, so a PR that transitions to CONFLICTING during the Step-15 remediation CI poll (because a sibling lane merged) doom-polls for the pull_request-triggered required checks -- which GitHub silently skips on a CONFLICTING PR -- until the 900s surface-wait timeout, then concludes 'CI did not pass after remediation round N' and STRANDS the PR (verified on PR #1075: ~32 surface-wait iterations, zero conflict-handling, timeout, dispatcher exit). VERIFIED ROOT CAUSE: _wait_for_expected_pr_check_surface_to_pass accepts a midpoll_autoresolve context ({base_branch, branch_name}) that enables a mid-poll _check_pr_conflict_state + _try_auto_resolve_pr_conflict re-check (the #30/#31/#36 Step-14 fix); it defaults to None (disabled). _wait_for_pr_ci accepts midpoll_autoresolve and threads it to the surface-wait. BUT the Step-15-remediation CI-wait -- the _wait_for_pr_ci(...) call inside _attempt_bot_finding_remediation -- OMITS midpoll_autoresolve, so it is None and the conflict re-check is DISABLED for the remediation poll. FIX: pass midpoll_autoresolve to that _wait_for_pr_ci call inside _attempt_bot_finding_remediation, building the {base_branch, branch_name} context EXACTLY as the Step-14 caller builds it -- i.e. {base_branch: base_branch, branch_name: target_branch}. [Bridge-review correction 2026-06-04: the original routed request read 'base_branch = target_branch', but target_branch is the PR HEAD in this path (the function pushes `git push origin target_branch`) and _try_auto_resolve_pr_conflict fetches+merges origin/{base_branch}, so the base_branch key must carry the REAL base (handoff['base_branch'] = dev), NOT target_branch.] Correct mapping: branch_name = target_branch (the head the function already receives, no threading needed); base_branch = the wave base branch the Step-14 caller passes (handoff['base_branch'], = dev), which _attempt_bot_finding_remediation does NOT currently receive and so must be threaded in from its caller _run_post_commit_pipeline (where base_branch is already a parameter), or as a fallback derived via `gh pr view <pr_number> --json baseRefName`. RESULT: a remediation-time concurrent-merge CONFLICTING transition is re-checked and _try_auto_resolve_pr_conflict is re-fired once (base merged in; the repush re-triggers the skipped pull_request workflows), instead of doom-polling to timeout -- mirroring Step-14 exactly. READ FIRST (in mu/tools/executors/commit_executor.py): _wait_for_expected_pr_check_surface_to_pass (the midpoll_autoresolve gating + the conflict re-check loop), _midpoll_conflict_recheck_before_ci_failure, _wait_for_pr_ci (how it accepts + threads midpoll_autoresolve), the EXISTING Step-14 _wait_for_pr_ci call site (how it constructs the {base_branch, branch_name} dict -- mirror it), and the _wait_for_pr_ci call inside _attempt_bot_finding_remediation (the exact call-site to fix). SCOPE: ONLY mu/tools/executors/commit_executor.py (the remediation _wait_for_pr_ci call + any minimal base-branch threading it needs, from _run_post_commit_pipeline) + a regression test in the EXISTING mu/tests/tools/test_commit_executor_step14_autoresolve.py (mirror the existing Step-14 autoresolve test: drive a mid-poll CONFLICTING transition during the Step-15-remediation CI-wait and assert _try_auto_resolve_pr_conflict is invoked + the surface-wait does NOT return a timeout/ci_failure when the conflict auto-resolves). Non-Step-14/non-remediation callers (midpoll_autoresolve=None) MUST stay unchanged. NO new test file (use the existing test_commit_executor_step14_autoresolve.py -- growth cap). L4_ENABLER: pipeline tooling, no runtime/substrate dir. Cite code by FUNCTION NAME only; NO file:line in the plan.

Routed next-candidate:
step15-remediation-surface-conflict-recheck-2026-06-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `step15-remediation-surface-conflict-recheck-2026-06-04`
- Active packet: `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`
- Indicator artifact: `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`
  - `reports/deferred/non_blocking/step15-remediation-surface-conflict-recheck-2026-06-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `step15-remediation-surface-conflict-recheck-2026-06-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/step15-remediation-surface-conflict-recheck-2026-06-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `step15-remediation-surface-conflict-recheck-2026-06-04`
- Active packet: `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2faa0ce15904ed947cb16076c707b60d20cb7794142ae8f66b750cae0145377c`
- Indicator artifact: `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_step14_autoresolve.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_step14_autoresolve.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/step15_remediation_surface_conflict_recheck_2026-06-04.md`
  - `reports/deferred/non_blocking/step15-remediation-surface-conflict-recheck-2026-06-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/step15-remediation-surface-conflict-recheck-2026-06-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
