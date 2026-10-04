# Measured lifecycle targeted-gate budget unblocker for preserved cleanup PR1329

Date: 2026-10-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-lifecycle-gate-budget-r1-2026-10-04
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: cfe475ad2d792708b3cc0f8394e276dc7ae0a6a17be78e7ab460499c5a59d1ae
Purpose: Unblock the actual repeated 240-second lifecycle targeted-gate cutoff preventing cleanup PR1329 from landing; preserve every test and resume the existing folder cleanup immediately after this bounded tooling correction.

## Scope

Two code/test surfaces only plus native packet, evidence, indicator and tracker/change-log outputs. This is the observed blocker inside existing program row38, not a new queue item or a redesign.

Files and surfaces in scope:

- TASKS.md
- CHANGELOG.md
- reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md
- reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_implementation_evidence.json
- reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json
- mu/tools/executors/commit_executor.py
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py
- reports/deferred/non_blocking/workingrcx-lifecycle-gate-budget-r1-2026-10-04_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-04 tracker sync note for wave `workingrcx-lifecycle-gate-budget-r1-2026-10-04` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read the real _run_pytest_on_files and its native Step8b caller. Diagnose using the archived timing command/output, not speculation. Exact cause: default non-fleet240s deadline vs measured260.699s successful wall time.
2. Use the smallest finite exact-selector policy for mu/tests/tools/test_worktree_lifecycle.py (600s measured slack). Keep ordinary selectors240s, exact full fleet900s and its four-worker policy; preserve max(caller_timeout,sum(per-selector budgets)). Do not broaden matches by basename or partial node selection.
3. Extend existing budget tests in test_commit_executor_post_merge_cleanup.py for exact lifecycle, mixed selectors, caller floor, unrelated/node selectors, nonzero outcomes and timeout failure. Reuse existing actual-helper/subprocess-boundary testing pattern and narrowly justified ANTICHEAT_OK conventions.
4. Keep implementation evidence compact and honest: original108-pass result is historical diagnostic evidence on preserved R2, not current enabler validation or merge authority. Record actual new commands/results and finite-budget behavior; no invented test counts or retrospective current-source hash claims.
5. Keep TASKS row38 and its linked working sequence accurate: land this measured blocker, resume preserved PR1329 using the landed native dispatcher/commit code with fresh gates, merge and sync PRIMARY, then five exact-target cleanup APPLY/VERIFY, PR1325 useful-work disposition and existing Mu owner. No extra numbered row or hypothetical prerequisite.

## Constraints

- Operator supplies WaveConfig STUB only; native PhaseA owns the full packet. Native actors own implementation, staging, commits, PR and merge.
- No changes to lifecycle source/tests in preserved R2, no resetting recovery counters or editing native authority/receipts, no reopening immutable R2 scope, no unchanged R2 restart.
- Preserve all test selectors, markers, import mode, validation environment, caller timeout floors, failure propagation and finite deadlines. No skip/xfail/assertion relaxation, PYTEST_ADDOPTS workaround or global timeout increase.
- No runtime/substrate/host semantics or Claude-owned surfaces; all LLM roles use current Codex gpt-6-astra/max policy, commit providerless.
- No folder deletion, PR1325/1329 closure, physical APPLY or production runtime work in this enabler. R2 and R1 source/index plus existing archives remain read-only. Successful enabler is not fleet completion.
- Defer nonblocking timeout-output diagnostics and recovery reinspection behavior to existing row40; do not expand this observed budget repair.

## Stop conditions

- Stop if the proposed repair needs a change outside declared allowlist or weakens any real gate; report the exact active blocker.
- Do not claim cleanup or landing from test/review success. No manual commit/merge, counter reset or force-push.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate`

## Acceptance criteria

- Exact full lifecycle module gets finite600s at the real helper; repeated240s policy is removed only for that exact selector.
- Regression command passes with complete selected tests, existing fleet900s/xdist policy preserved and failed/timed-out test runs still failing.
- Native pipeline lands this bounded enabler and syncs protectedPRIMARY; retained cleanup candidate is still byte-preserved until its separate native continuation.
- TASKS and evidence clearly leave PR1329 merge/five-target physical cleanup outstanding and next; no added queue row.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-lifecycle-gate-budget-r1-2026-10-04`.
- Governing packet: this file, `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`.
- TASKS.md authority: the 2026-10-04 tracker sync note for wave `workingrcx-lifecycle-gate-budget-r1-2026-10-04` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-lifecycle-gate-budget-r1-2026-10-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-lifecycle-gate-budget-r1-2026-10-04`
- Active packet: `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`
  - `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-lifecycle-gate-budget-r1-2026-10-04 --output reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`, `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-lifecycle-gate-budget-r1-2026-10-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-lifecycle-gate-budget-r1-2026-10-04`
- Active packet: `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9b0971c7d26b0e99b0fe6300bc4fd01cbb9a47983825ae5e044b17497e0eeb3f`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`, `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_2026-10-04.md`
  - `reports/control_plane/workingrcx-lifecycle-gate-budget-r1-2026-10-04_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-lifecycle-gate-budget-r1-2026-10-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
