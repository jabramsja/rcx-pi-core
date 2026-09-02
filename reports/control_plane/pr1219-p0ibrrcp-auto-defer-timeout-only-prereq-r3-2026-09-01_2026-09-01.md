# PR 1219 P0IBRRCP Auto-Defer Timeout-Only Prerequisite R3

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IBRRCP-AUTO-DEFER-TIMEOUT-ONLY-PREREQ-R3]
Wave ID: pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 273f988c984a057f8a4aec87381ac43ec47e9b3944aab9be00436d7d9b76ff09
Purpose: Land only the still-reproduced report-auto-defer failure from exact PR 1257 merge authority: replace report-thread mutation plus amend and hook-enabled 60-second force-push with a normal report child commit, immediate ordinary continuation checkpoint, the existing explicit pre-push guard, a 300-second hook-bypassed fast-forward push, and only-then eligible bot-thread resolution.

## Scope

Fresh timeout-only reconstruction from exact PR 1257 merge authority. Own only report-write/thread ordering, amend-to-child-commit, ordinary checkpoint, explicit existing guard, 300-second --no-verify fast-forward push, controlled subprocess failures, and focused proof. Exclude arbitrary crash consistency, descendant authentication, exactly-once execution, resolver transactions, and the separately queued recovery-timeout environment containment.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- separate report writing from existing eligible bot-thread resolution; replace only the reproduced amend/force-push strand with a normal child commit, immediate ordinary continuation checkpoint, existing explicit pre-push guard, exact-target --no-verify 300-second push, push checkpoint, only-then resolver, and controlled CalledProcessError/TimeoutExpired returns.
- mu/tests/tools/test_commit_executor_receipt.py (MODIFY) -- prove exact report/stage/receipt/child-commit/checkpoint/guard/push/thread ordering, command shapes, timeout recurrence removal, and controlled subprocess failures without arbitrary process-kill cases.
- TASKS.md (MODIFY) -- record PBNOGO R2 LANDED through PR 1257 at exact merge 3f479ad9c15ba14aaeed0f45549aa22dc72b4a4c, make auto-defer timeout R3 CURRENT/LANDED as appropriate, leave recovery-timeout environment containment sole immediate NEXT, preserve every queue/TODO/stopped/PR/fleet item, and do not duplicate aliases.
- reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md (GENERATED) -- sole launcher-owned canonical packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reconstruct fresh only from exact merge 3f479ad9c15ba14aaeed0f45549aa22dc72b4a4c. Preserve stopped auto-defer R1/R2 targets, branches, buses, packets, candidates, commits, reviews, and incident evidence unchanged; never resume, copy, mutate, or use them as source authority.
2. Keep P0/P1, critical-path, and P2/non-critical classification unchanged. Split local report writing from remote resolution so report creation performs no gh query/mutation and the existing eligible-bot-thread resolver cannot run before successful push plus git_push checkpoint.
3. Stage the report, mint the existing receipt, and create a normal child commit with the existing commit subprocess environment. Do not amend. Read the new HEAD, reset steps through git_commit using the existing helper, clear only existing per-head stale fields, and immediately call the ordinary continuation checkpoint API.
4. Run the existing bot-remediation pre-push guard for the child commit. Preserve replay-safe behavior; require at least one successful recorded guard for the exact continuation HEAD before push, without claiming exactly-once execution.
5. After guard success, checkpoint run_pre_push_script, then push exactly --no-verify origin <target-branch> with timeout=300 and no force. Checkpoint git_push after success.
6. Only after successful push and git_push checkpoint invoke the existing eligible-bot-thread resolver. Preserve bot-only filtering, human-thread exclusion, already-resolved skip, and non-fatal resolver-error policy.
7. Catch CalledProcessError and TimeoutExpired from the report stage/commit/guard/push strand and return controlled bot_findings_pending or equivalent non-success without reaching thread resolution, PR-head refresh, CI, or merge.
8. Add focused regressions for normal child commit, immediate checkpoint-before-guard, replay-permitted guard ordering, exact 300-second no-verify push, absence of amend/force/implicit hook, no GraphQL before git_push checkpoint, and controlled guard/push errors/timeouts.
9. Update narrow TASKS truth and complete normal Phase A, Phase B, providerless commit, pre-push, PR, CI, review, merge, and cleanup. Then builder-launch fresh recovery-timeout environment containment from the actual R3 merge.

## Constraints

- Functional and test scope is exactly commit_executor.py and test_commit_executor_receipt.py, plus TASKS.md and same-wave generated governance. Add no other functional or test file.
- Do not change classification, review waiting, bot/human thread eligibility, merge/CI policy, receipt schema, continuation schema, normal remediation, recovery routing, bridge adapters, launcher, dispatcher, hooks, role/model defaults, runtime, substrate, seed, host, or Mu semantics.
- Do not add crash-before-checkpoint authentication, multiple-descendant adjudication, atomic continuation writes, durable guard receipts, exactly-once guard/resolver semantics, remote compensation, generic interruption handling, or resolver transactions. None is required by the reproduced incident.
- Do not absorb recovery-timeout environment containment, provider-terminal R4B, root-exit R4C, or any later queue obligation. Do not fix unrelated edge cases or nonblockers.
- Use launch_wave.py with an immutable clean detached source. No hand-authored packet, manual candidate patching, staging, commit, push, PR mutation, merge, or stopped-lane folding.
- Every model-bearing role is Codex gpt-5.6-sol ultra and commit execution remains providerless. Do not edit Claude-owned files or use provider-local memory as evidence.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from 3f479ad9c15ba14aaeed0f45549aa22dc72b4a4c; if the launch worktree is dirty; if identity collides; or if Codex/providerless authority is unavailable.
- Stop as NEEDS_RESCOPING if the reproduced timeout-only repair requires a functional or test file outside commit_executor.py and test_commit_executor_receipt.py; split only that active blocker into a fresh narrower builder wave.
- Stop as DEFECT if the final path still amends, force-pushes, invokes an implicit push hook, retains timeout=60, lets TimeoutExpired escape, resolves any bot thread before git_push checkpoint, or treats failed guard/push as success.
- Do not stop or widen for crash-window authentication, atomic continuation, exactly-once execution, durable resolver transactions, recovery-timeout containment, later queue work, documentation polish, or any other non-occurring edge case.
- If the same exact timeout/order blocker repeats after one focused correction or bounded review stops converging, preserve the lane and split only the active blocker into fresh narrower launch_wave.py stubs.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`

## Acceptance criteria

- Only allowlisted paths change, with exactly one launcher-owned canonical packet and no packet alias or hand-authored packet.
- Launch metadata proves exact base 3f479ad9c15ba14aaeed0f45549aa22dc72b4a4c, implementer/reviewer/pager Codex, and providerless commit execution.
- Classification, report content, bot-thread eligibility, human exclusion, and resolver-error policy remain unchanged; report generation performs no GitHub query or mutation.
- The report is recorded in a normal child commit using the existing receipt and commit environment. Amend and force push are absent.
- The exact new HEAD and reset steps are checkpointed immediately before the existing replay-safe pre-push guard; at least one successful guard is checkpointed for that HEAD before push.
- Push is exactly --no-verify origin <target-branch> with timeout=300 after guard success, followed by git_push checkpoint. CalledProcessError or TimeoutExpired returns controlled non-success.
- Only after git_push checkpoint may the existing eligible-bot-thread resolver run; focused tests prove no earlier GraphQL query or mutation on normal or failure paths.
- Focused evidence, staged L4 enforcement, relevant commit/receipt tests, pre-push-fast, required CI, Codex review clearance, providerless commit, merge, and terminal cleanup pass.
- TASKS preserves all queue/TODO/stopped/PR/fleet evidence, records PR 1257 accurately, lands auto-defer R3, and leaves recovery-timeout environment containment sole immediate NEXT.
- After merge, a fresh builder-launched recovery-timeout environment-containment wave is pinned to the actual R3 merge SHA; provider-terminal R4B remains serialized behind it.

## Grounding / Authorization

- Task: [PR1219-P0IBRRCP-AUTO-DEFER-TIMEOUT-ONLY-PREREQ-R3]; wave id `pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a4445ef09b6598d1f87c80030fc40d233d3f0e46916ccdcd252049bd9fc8c403`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01_2026-09-01.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-auto-defer-timeout-only-prereq-r3-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
