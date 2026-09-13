# PR1219 P0IBRRC preserved reentry-private checkpoint handoff R2

Date: 2026-09-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRC-REENTRY-PRIVATE-ATTR-CHECKPOINT-AUTHORITY]
Wave ID: pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 0d172e070e5733d32aa4b87c1f1df4bbfcc85fba0f59e8e851b116219d671b21
Purpose: Land the EXISTING CURRENT P0IBRRC queue row30 through a fresh same-slot builder attempt, reusing the preserved tested R1 repair and validating its unfinished directly related handoff tests. No added prerequisite, queue identity or generic lifecycle-hardening wave. Preserve explicit reentry-private findings/runtime context and consumed-private-GO to fresh-supervisor continuation with coherent public dispatcher consumers.

## Scope

Same existing RRC row30, same two production/two test modules: reentry-private context producer, consumed private-GO to fresh-supervisor continuation, and both public dispatcher consumers. Reuse preserved repair, evaluate the stopped same-handoff test delta, bound any required fix to this transition; no generic recovery, transport, model, runtime or fleet change.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py -- reconstruct the preserved RRC context repair and consumed private-review GO to new supervisor NEEDS_PHASE_B continuation, preserving unresolved ownership, exact current findings/runtime flag and no repeated successful edit. Evaluate the stopped before-next-actor notification test only as part of this same producer/consumer handoff.
- mu/tools/executors/executor_dispatch.py -- reconstruct and validate both public consumers of the exact reentry-private and supervisor continuation; unresolved/mismatched authority must not fall into generic mutator replay. Do not change generic retry/recovery or terminal transport.
- mu/tests/tools/test_phase_b_executor.py and mu/tests/tools/test_executor_dispatch.py -- public-path before/after reproductions and controls for the affected checkpoint transitions, real producer-to-consumer handoff, guard invocation and no repeated successful mutator.
- TASKS.md and CHANGELOG.md -- bounded PR1294 ownership landing credit, existing RRC CURRENT and RRT immediately NEXT. Preserve every other task identity and semantic order, the held primary TASKS stash and both consumed fleet operations.
- reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md, reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json and optional reports/deferred/non_blocking/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_bridge_nonblockers.md -- fresh native same-wave packet, indicator and exact nonblocker report only. Root WaveConfig remains external and excluded from staging.
- TASKS.md -- tracker-sync authority. The 2026-09-12 tracker sync note for wave `pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Require fresh initial HEAD, comparison_commit and origin/dev to equal cdf2e02507cde0a3f1909ed00177ab1c474155a9. R1 is stopped, never resume it; create a new native Phase A packet and independent review. The same existing RRC row30 stays CURRENT; do not add or reorder a queue identity. Read the R1 terminal_stop_observation.json as root-cause/preservation evidence, not execution authority.
2. Read-only reconstruction source: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/p0ibrrc-reentry-private-r1-evidence-2026-09-12/recovery_delegate_848ed750_completed/candidate_snapshot/ contains exactly the two declared production modules and two tests which passed1720 full tests/307.92s, hash-bound in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/p0ibrrc-reentry-private-r1-evidence-2026-09-12/recovery_delegate_full_validation_observation.json. Native implementer may reconstruct those four files into this fresh candidate. Do not copy old TASKS, CHANGELOG, packet, indicator, .scratch, bus, state, receipts, handoff, counters or index.
3. Read /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/p0ibrrc-reentry-private-r1-evidence-2026-09-12/terminal_stop_observation.json and the bounded four-file delta between recovery_delegate_848ed750_completed/candidate_snapshot and stopped_second_delegate_0bb67eb6/candidate_snapshot. At the pre-signal sample the second delegate had changed tests only; at00:00:39Z during shutdown it also completed two tiny production changes: preserve supervisor_reentry_identity at the pre-actor state-save boundary, and validate supervisor_step string type before set membership. The stopped tests cover before-actor notification, commit-ready/review-interrupted outcomes through both dispatcher routes and supervisor-step refusal controls. NONE of this second delta has completed validation. Native implementer may reconstruct this delta on the tested repair, must establish a fresh before/after result for the actual handoff gap, and should retain only valid bounded corrections. No new wave or generic hardening.
4. Preserve the original before/after basis: R1 baseline item22 had2 expected missing-marker failures/1613 existing passes; its source snapshot and paired supervisor item12 evidence are preserved. Perform the minimal fresh public-path baseline check needed to bind reconstruction to exact PR1294; do not rerun exploratory searches or rebuild the already-tested repair from scratch. Credit PR1291/1292/1294 guarantees and retain ordinary/non-reentry controls.
5. Keep explicit reentry-private identity, exact current reentry_findings and boolean runtime_pre_push_failure_reentry through findings-driven bridge-fix pending, failure/interruption, sealed successful mutation/finalization and owed private review. Resume the owed continuation through Phase B and both dispatcher routes without replaying a successful mutator; the existing runtime scope guard must still refuse a control-only runtime reentry before supervisor calls.
6. After private review GO, a later supervisor NEEDS_PHASE_B must replace consumed private-review authority with the exact fresh supervisor-requested continuation, not strand the old prepared-review checkpoint or replay the completed private edit/review. Preserve the new continuation until its next mutator takes ownership; specifically establish the stopped before-actor-notification case through the public path and both dispatcher routes if the test is valid. Preserve unresolved/current-invocation authority on refusal.
7. Run cheap current control-surface invariants first: python3 mu/tools/checks/check_control_surface_invariants.py --json. Run focused same-handoff regressions while iterating, then the unchanged declared COMPLETE two-module evidence suite with four work-stealing workers. Do not alter production during a full validation run; rerun after any subsequent source/test change.
8. Validation environment lesson from the actual R1 rejection: use the ordinary OS temporary directory outside this Git worktree. Do not create .scratch/recovery_pytest_tmp, .scratch/private_go_repair or any new repo-local temporary test tree; no repository-nested TMPDIR or HYPOTHESIS_STORAGE_DIRECTORY. The default evidence command already passed in the initial R1 lane. If a fixture temporary root is explicitly selected, it must be external and have an appropriate command-local Git discovery ceiling. This is invocation hygiene, not permission to edit recovery_gate, weaken its scratch audit, shrink tests or bypass a timeout.
9. Native owners regenerate bounded same-wave TASKS/CHANGELOG/packet/indicator, preserving current row30 semantics and every later task. R1 is stopped/no landing and its evidence remains historical; no old packet status, supervisor GO or receipt is candidate approval. Correct any encountered bounded live-order references to PR1294 LANDED/RRC CURRENT/RRT NEXT, without rewriting unrelated historical tracker material.
10. After fresh independent reviews and required gates, native providerless commit/push/PR/CI/merge and primary fast-forward complete the task. Observe convergence, preserve actual failure evidence and never retry a known forbidden scratch pattern or scope contradiction. Do not add speculative hardening or prerequisites; RRT follows immediately after honest terminal closeout.

## Constraints

- Root supplies this external WaveConfig STUB and bounded tracker seed only. launch_wave.py, dispatcher, Phase A, Phase B and native commit/recovery own full packet generation, candidate implementation, staging, receipts, commits, pushes, PR review and merge. No manual git fallback or copied old authority.
- This is existing numbered CURRENT row30 P0IBRRC, a same-slot R2 replacement after stopped R1. Keep every queue/TODO identity and semantic order unchanged. P0IBRRT remains immediate successor, then RR/IB1/IB2, all later tasks, Mu production and optimization last.
- Only phase_b_executor.py and executor_dispatch.py may change production behavior, and only for the exact reentry-private context transition and its consumers. The two matching test modules and bounded TASKS/CHANGELOG/same-wave governance are allowed. Do not modify launcher, recovery_gate, commit_executor, executor_common, adapters, supervisors, invariant checkers, OS process handling or Claude-owned surfaces.
- Preserve recognized-verdict precedence, QUESTION refusal, retry/recovery classifications, generic terminal transport, SDK execution policy, candidate/receipt authority and ordinary non-reentry behavior. RRT transport, RR refusal handling and IB inventory work remain separately queued; no runtime/host/substrate/seed/projection changes.
- Use founder-selected Codex gpt-6-astra/max for all selected local pipeline roles, commit providerless. Committed role/model topology is already correct; do not modify it or revive a dormant provider.
- All stopped worktrees, archived sources and held stashes are read-only preservation evidence. In particular retain primary TASKS stash62a2dbee16f7530242d9a86ebe87152bb34fa251 and all earlier stashes; never pop/drop them or replay either consumed fleet cleanup operation.
- Do not add hypothetical hardening, redesign recovery time budgets, repair unrelated documentation or pursue preexisting nonblockers. The prior hard300-second recovery validator limitation is not permission to weaken tests or change excluded recovery infrastructure.
- Archive prompt qualification: recovery_delegate_848ed750_completed captured a mutable prompt later overwritten by SECOND0bb67eb6; it is not the matching848ed750 prompt. The exact FIRST prompt is in recovery_delegate_848ed750_input (SHA4c74f67270ae6ffb9462d98866002659d5369db372710e2eb01d06d246c83cb7). First raw and four tested files remain correctly bound. Read-only historical evidence only.

## Stop conditions

- Before launch require exact current dev/base, a fresh unused target/branch/bus/session, stopped R1 pane32 and absent owners, predecessor PR1294 landed with terminal exit0, and selected Codex gpt-6-astra/max roles with providerless commit.
- If the fresh public reproduction shows the obligation already satisfied, do not invent a new defect or widen the task. Return exact coverage/credit evidence through the native review for honest reclassification or closeout.
- If a reproduced active blocker requires an excluded production module, report that exact boundary once and preserve evidence; do not repeat a known producer-only scope contradiction, silently widen the packet or start a generic repair loop.
- Fail closed if the affected resume loses reentry identity/findings/runtime authority, bypasses the existing scope guard, repeats a completed mutator or corrupts ordinary behavior. Do not halt or add a wave for unrelated hypothetical cases or nonblockers.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`

## Acceptance criteria

- Fresh exact-base reproduction/validation binds the preserved RRC repair to PR1294 and preserves the credited PR1291/1292/1294 guarantees; no old approval authority is replayed.
- Affected reentry-private pending review, findings-driven bridge-fix pending, actor failure/interruption, successful finalization and recursive review checkpoints preserve explicit context, exact current findings and the runtime-pre-push boolean.
- Phase B and both public dispatcher routes resume only the owed reentry continuation, never duplicate a completed mutator or skip owed review, and preserve/refuse unresolved or mismatched authority without generic recovery replay.
- Private GO followed by fresh supervisor NEEDS_PHASE_B reaches the owed next invocation and commit-ready or rightful refusal through both public dispatcher routes, without replaying the completed private mutator/review. The unfinished same-handoff before-actor notification tests are evaluated and any reproduced gap is fixed within declared scope, with fresh passing evidence.
- The existing runtime-pre-push scope guard runs after each affected resume and refuses a control-only runtime reentry before any pre-commit supervisor call. Ordinary initial and non-reentry private-review paths retain existing semantics and acquire no reentry authority.
- Only the declared two production/two test modules and bounded same-wave governance change. No terminal transport, generic recovery, model, runtime or fleet-operation expansion.
- Current control-surface invariants, the full two-module evidence suite, independent reviews and required native gates pass; providerless commit/PR/CI/merge and primary fast-forward are verified honestly.
- RRC is the same existing queue obligation, RRT immediately follows, and every remaining queue/TODO identity and semantic order is preserved.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRC-REENTRY-PRIVATE-ATTR-CHECKPOINT-AUTHORITY]; wave id `pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`.
- TASKS.md authority: the 2026-09-12 tracker sync note for wave `pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12 --output reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6ae0c4e9af3c760278057687f908bb7e22ba8ed3a93ebb767e799c043006387f`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrc-reentry-private-checkpoint-r2-2026-09-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
