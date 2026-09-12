# Ordinary bridge-fix outcome and complete dispatcher boundary R3C6-R4

Date: 2026-09-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IBRRCO-BRIDGE-FIX-REPLAY-R3C6-R4]
Wave ID: pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 7fe7a376cd1e417a80e5669559117fde7caab56f5d9eea54e07f13adb7313940
Purpose: Correct the existing R3C6 queue slot's proven locked-scope contradiction, not add a prerequisite. Preserve/reuse the stopped R3's bounded ordinary outcome, identity, CLI and success-continuation implementation, and complete its actually blocked protected-error dispatcher boundary. Both valid success and protected error outcomes must satisfy the same at-most-once checkpoint contract through native public entrypoints.

## Scope

The complete ordinary bridge-fix outcome boundary: existing producer states/identity/actor-free finalizer, its native CLI, and direct dispatcher handling of BOTH finalized-success continuation and protected ordinary errors. This intentionally authorizes the exact dispatcher-error exception forbidden by R3. All other lifecycle recovery stays unchanged. No new queue item.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py and mu/tests/tools/test_phase_b_executor.py: reuse bounded R3 ordinary at-most-once outcome, independent identity, finalizer and standalone protected-error behavior; adjust only as required for its explicit consumer contract.
- mu/tools/executors/executor_dispatch.py and mu/tests/tools/test_executor_dispatch.py: both finalized-success continuation and protected ordinary-error preservation through surface/routing CLI entrypoints and their actual retry/chain consumers.
- TASKS.md, CHANGELOG.md and this wave's builder-generated packet/indicator/optional nonblocker report; no other production or queue task.
- TASKS.md -- tracker-sync authority. The 2026-09-12 tracker sync note for wave `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Preserve the exact sealed R3C5-R2 bridge_fix_plan_authority and independent anchors while adding explicit, versioned, strictly typed ordinary mutation states equivalent to PENDING, IN_FLIGHT and SUCCESS_PENDING_FINALIZE. Keep them distinct from existing outer Phase B checkpoint names and from private-review/reentry state.
2. After validating the existing actor authority, atomically persist and verify IN_FLIGHT before invocation. A failed save invokes zero actors. A recovered valid IN_FLIGHT returns deterministic ambiguous-outcome error with zero implementer/reviewer calls, preserves the checkpoint, and does not read or adopt actor-mutable plan bytes. Explicit non-success in the original invocation retains existing caller-visible failure semantics while leaving IN_FLIGHT as restart truth; do not add a known-failure retry state.
3. Immediately after explicit actor success, strictly validate and atomically save a digest-bound, independently context-bound SUCCESS_PENDING_FINALIZE result before pager emission, pytest, scope refresh, review or other fallible post-actor work. Preserve exact success result, round/decision/findings/checkpoint identity, next-state intent and unchanged sealed authority. If saving fails, IN_FLIGHT remains and no replay becomes authorized.
4. Use one idempotent actor-free finalizer for a valid sealed success. Recovery invokes zero actors and establishes the same existing bridge_round_N or bridge_converged checkpoint as uninterrupted success. Finalization may be resumed, but the bridge-fix actor must never be repeated. Post-success pytest or validation failure preserves SUCCESS_PENDING_FINALIZE and invokes zero remediation/bridge-fix actors; automatic pytest remediation is deferred post-Mu by the existing task.
5. Retain malformed/foreign identity rejection before actors without adopting mutable plan bytes, including the independently authorized planless-recovery check and protected Path-valued JSON error serialization already implemented in R3. Preserve existing explicit actor-failure semantics; do not add a retry state.
6. Retain the proven explicit finalized-success continuation: native Phase B CLI, dispatcher surface and normal routing CLI schedule the later original Phase B invocation with exact bridge_round_N/bridge_converged checkpoint preserved and zero actors during finalization. Validate result/checkpoint/routing identity without false handoff or separately owned reentry flags.
7. Complete the missing protected ordinary-error contract at the direct dispatcher boundary BEFORE generic recovery or checkpoint clearing. Cover actual emitted ordinary authority, mutation/ambiguous outcome, finalizer and post-success validation errors, and shared pre-actor error steps only when the selected bus's ordinary checkpoint owns that invocation. The native CLI must emit a serializable honest error. Surface and normal routing entrypoints, their CLI retry loops, A-to-B chaining and continuation-result consumers must retain it as non-retryable for this protected case: zero attempt_recovery calls, zero checkpoint clearing, zero new Phase B invocation, unchanged checkpoint bytes and zero replay actors. Do not key authority on incidental prose or mislabel this as post_reentry_needs_phase_b.
8. Extend the preserved real CLI-to-dispatcher probe into public-entrypoint regression tests before the error fix. Exercise both supported dispatcher CLI entry paths with default and selected bus as appropriate, real ordinary IN_FLIGHT and SUCCESS_PENDING_FINALIZE errors, successful continuation and the later invocation's protected error. Isolate real process/model calls only; keep producer, CLI, result decoding, dispatcher retry/chain behavior and checkpoint filesystem logic intact. Include explicit original actor-failure and unrelated lifecycle controls to prove the exception is narrow. No AST fragments or private-attribute test-integrity bypasses.
9. Run the complete two declared modules after correction; do not require an exact count. Verify the same staged bytes at review with native authority/L4 gates. Synchronize this wave's nonblocking report, TASKS and CHANGELOG honestly: the reproduced core error defect is resolved only after its regression passes, not by relabeling it.
10. Synchronize ALL live TASKS owners: Program Queue header, Live repository truth, Binding order, Parallelism rule/current serial work, current task heading and existing closure baton. PR #1291 is the landed predecessor; stopped R3/R2 remain noncomplete preserved evidence; R4 replaces this same current slot; exact P0IBRRCP closure stays NEXT. Preserve all later identities/order and both consumed cleanup outcomes. Do not copy the whole primary tracker over the fresh base or claim cleanup complete.

## Constraints

- Launch one fresh carrier only from exact PR #1291 merge fdfc58d52c717785a5696a8c3d36f9c934ee0030 after independently verifying remote dev and the stopped R3 owner. R3 source/test hunks are preserved work to reuse, not a request to redesign or rediscover them. Exact read-only source carrier: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-pr1219-r3c6-r3-20260912. Exact terminal snapshot: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/r3c6-r3-evidence-2026-09-12/terminal_packet_scope_stop/; manifest SHA256 22bb8afb0eda81902d36e20167d1fa9fae063f8cbc0eb79c5335b66c22ca70d7. The completed required-defect supervisor evidence is in the sibling supervisor_review_after_reentry_round2/ directory; the original public probe is in the sibling review_reentry_round2/ archive and R3 .scratch/review-phase-b-reentry-r2-f89e2661/test_dispatch_ordinary_probe.py. Inspect only these named interfaces/evidence as needed.
- Never import the old packet, index, checkpoint, receipt, review counter or candidate authority. Reconstruct/reuse only bounded code/test hunks from the unchanged exact base under fresh native authority. R3's latest test/doc additions were interrupted and require new validation; its 1422 count applies to the prior completed candidate.
- Preserve R3C5-R2 sealed input authority and independent anchors, landed private-review R2, QUESTION, initial implementation, process ownership, reentry, INV2 and routing/model authority. Dispatcher recovery may change ONLY for ordinary protected-error outcomes and ordinary finalized-success continuation. Unlike R3, the ordinary error fence is expressly REQUIRED, not a deferred generic-recovery redesign. All unrelated and explicit original actor-failure recovery behavior remains unchanged.
- No production changes outside phase_b_executor.py and executor_dispatch.py. No changes to recovery_gate/classifier/timeouts, commit executor, launcher/builders, bridge adapters/supervisors, candidate_authority, model configs, receipts/collectors, Claude-owned surfaces, runtime or Mu. The observed native process_timeout retry is separate evidence, not a request to repair that mechanism here.
- No actor retry/reset, durable known-failure retry state, inferred success, automatic post-success pytest remediation, reentry impersonation, false commit handoff, or checkpoint deletion to force progress. A protected error stays an honest terminal error for the current invocation; a finalized success remains nonterminal continuation, not an error disguised as success.
- All selected local model roles remain Codex gpt-6-astra/max. Native launch_wave/dispatcher/Phase A/B/commit/recovery owners generate/refine the packet, implement, stage, review, commit, push and merge. Do not spawn subagents, run sibling executors from inside an implementer, or hand-edit generated authority.
- Eight required candidate paths plus the exact optional same-wave nonblocker report only. No fleet action, PR cleanup, process killing, indexing change, consumed-operation replay, extra precursor or later PR1219 task.
- Convergence/token discipline: reuse the already demonstrated bounded implementation. Prove the exact blocked error consumer early with intact modules and isolated process/model boundaries, then correct it and run the declared complete modules. Do not repeat the full 1422-test baseline merely to rediscover its known defect; focused red/green evidence suffices before the full corrected run. Required native validation gates still run. Do not broaden into hypothetical variants or remove guards to get green.

## Stop conditions

- Do not launch unless R3 is inactive and hash-preserved, comparison authority is exact fdfc58d52c717785a5696a8c3d36f9c934ee0030, and branch/carrier/bus/packet identities are fresh.
- Stop with a concrete reproduction if the required ordinary success/error consumer contract cannot be implemented within the declared two production files and two test files, or would alter a separately owned lifecycle. Do not widen a locked packet, reset counters or resume the stopped R3.
- Missing protected-error preservation is a failure of this explicitly required ordinary recovery feature, not a non-blocking hypothetical. The already reproduced supervisor defect must be resolved and tested; do not retain it as a deferred finding while claiming this packet complete. New unrelated/non-blocking observations must not expand this wave.
- Transient selected-model capacity is transport availability, not a code defect. Retain Astra/max and native bounded handling; no downgrade or capacity repair wave.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`

## Acceptance criteria

- Every ordinary bridge-fix attempt has verified durable IN_FLIGHT before invocation; save failure and valid ambiguous recovery invoke zero actors and preserve authority/checkpoint.
- Only explicit validated actor success creates SUCCESS_PENDING_FINALIZE, before fallible post-actor work. Its version/types/digest and independent context reject substituted authority without adopting live state.
- Valid recovered success invokes zero actors and idempotently finalizes into the existing round/convergence checkpoint. Post-success validation failure retains success and launches no remediation.
- Public run_phase_b interruption/normal-flow regressions and both complete declared modules pass. Private-review R2, reentry and other separately owned behavior remain unchanged.
- Valid finalized success preserves its checkpoint through actual native Phase B and both dispatcher CLI entry paths and schedules the exact later original Phase B command without recovery/finalization actors.
- Protected ordinary errors from the native CLI, including the exact reproduced IN_FLIGHT ambiguity and post-success failures, preserve the selected checkpoint through both public dispatcher entry paths and relevant chain-result consumers. No generic recovery, checkpoint clearing or another Phase B invocation occurs. Result/exit behavior remains an honest error; isolated controls prove explicit actor failures and unrelated lifecycles keep their original behavior.
- The preserved failing error-consumer probe is reproduced red then passes green as an intact public regression; existing success-continuation, independent-identity, private-review/reentry controls and both complete declared modules pass.
- Only eight required candidate paths plus the exact same-wave optional nonblocker change. Independent native reviews/supervisors, staged L4, pre-push, CI and merge pass. All live TASKS owners identify this same-slot R4 and existing closure next, with all later queue/TODO items and consumed cleanup outcomes preserved.

## Grounding / Authorization

- Task: [PR1219-P0IBRRCO-BRIDGE-FIX-REPLAY-R3C6-R4]; wave id `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`.
- TASKS.md authority: the 2026-09-12 tracker sync note for wave `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12 --output reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`, `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `d39276fb45c8b58ca0fe93eea485c36211af3d99a7969cfebc9fc3fddfcb0f4b`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`, `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_2026-09-12.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrco-bridge-fix-replay-r3c6-r4-2026-09-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
