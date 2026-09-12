# PR1219 P0IBRRCO preserved ownership repair landing R2

Date: 2026-09-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCO-IN-FLIGHT-IMPLEMENTER-OWNERSHIP]
Wave ID: pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 376dfb9e001fc92dc90e0c02d6416524242828114a2b79fccda56056184f9561
Purpose: Land the preserved, tested implementation of the EXISTING P0IBRRCO task after the R1 native recovery validation-budget dead end. This is the same queue slot, not a new prerequisite. Reuse the four source/test files in the read-only terminal candidate snapshot, including initial/private/reentry/SDK ownership and the completed post-GO pager-failure correction. Do not rebuild the repair from scratch, broaden scope, or treat historical approvals as current authority.

## Scope

Same P0IBRRCO ownership contract and same two production/two test modules. Native owner ports the preserved tested four-file candidate as implementation data, regenerates only this wave's governance, validates and lands; no recovery-budget or unrelated code changes.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py -- reuse the preserved tested in-flight/known-success ownership implementation, including SDK carry and post-GO ownership retention, preserving legitimate corrective mutation and QUESTION refusal.
- mu/tools/executors/executor_dispatch.py -- reuse the preserved bounded ownership integration across both existing public dispatcher routes, their continuation/refusal/recovery consumers, and no unrelated retry-policy changes.
- mu/tests/tools/test_phase_b_executor.py and mu/tests/tools/test_executor_dispatch.py -- deterministic reproduction-first public-path regressions and normal-path controls for this exact ownership contract.
- TASKS.md and CHANGELOG.md -- exact PR1293 closure landing, existing P0IBRRCO current scope, original P0IBRRC immediate successor and every later task in unchanged semantic order.
- reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md, reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json, optional reports/deferred/non_blocking/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_bridge_nonblockers.md -- native generated same-wave governance only; external config never enters staging.
- TASKS.md -- tracker-sync authority. The 2026-09-12 tracker sync note for wave `pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Verify fresh initial HEAD, comparison_commit and fetched origin/dev equal PR1293 merge c7fed5bba8de7898b686a636cecc42e379968eec. R1 was deliberately stopped after a repeated recovery validation-budget mismatch; its owners are absent, source hashes match the1613-test pass, and it has no CO commit. Do not replay its state, packet, routing, receipts, handoff or terminal authority.
2. Read-only implementation reference: /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/p0ibrrco-inflight-r1-evidence-2026-09-12/terminal_recovery_timeout_stop/candidate_snapshot. The corresponding four source/test files are authoritative only as preserved code bytes, never as execution or approval authority. Native owner should port these four files into the fresh carrier without discarding the proven repair or reimplementing it from scratch. Do not port old TASKS, CHANGELOG, packet, indicator, checkpoint, bus, receipt or model/config files.
3. Credit the archived R1 public before/after reproductions and completed native full1613-test result; bind the reused implementation to this new candidate with the same public regressions and independent review. The known closed findings are INV-2 integration, SDK ownership carry, and ownership consumed too early before post-GO pager/convergence checkpoint handling. Do not reopen unrelated hypothetical cases or add new contracts.
4. Keep ownership/outcome producer and both dispatcher consumers coherent. Preserve all existing PR1291 prepared-review and PR1292 ordinary bridge-fix guarantees, SDK review behavior, ordinary success, explicit actor failure, REQUEST_CHANGES/NO_GO corrective mutation and QUESTION refusal. Existing later P0IBRRC context semantics remain separately queued and must not be claimed complete.
5. Run the cheap current-candidate control-surface invariant check before the full suite: python3 mu/tools/checks/check_control_surface_invariants.py --json. Real implementer invocations must remain visible to its existing INV-2 predicate; never add cosmetic calls or edit the checker. Run the exact declared full two-module evidence with four work-stealing workers, already proven to pass all1613 tests in268.76s. This changes test scheduling, not test scope or assertions; never skip or weaken tests to fit a timeout.
6. Generate fresh same-wave governance through the native builder/executor and update only bounded TASKS/CHANGELOG entries. Preserve every queue/TODO identity and semantic order: CP PR1293 LANDED, this SAME CO slot CURRENT, P0IBRRC immediately NEXT, then all existing later tasks through Mu production and optimization last. Keep R1 evidence and all unrelated primary WIP/stashes/consumed fleet claims.
7. Complete native independent review, required current gates, providerless commit, push, PR, CI, merge and primary fast-forward. Stop once and preserve exact evidence if an actual blocker requires an excluded module or the same failed native recovery route repeats; no generic recovery fix, new prerequisite or stale receipt reuse.

## Constraints

- This is the existing P0IBRRCO queue position, not a new prerequisite. Root supplies this external stub and bounded tracker seed only; launch_wave.py/dispatcher/Phase A/Phase B/native commit and recovery own candidate code, full packets, staging, commits, pushes, reviews and merge.
- Use the live founder-selected Codex gpt-6-astra/max local roles, with providerless commit. Do not modify role/model/adapter configuration, Claude-owned surfaces or unrelated documentation.
- No production paths outside phase_b_executor.py and executor_dispatch.py. No launcher, executor_common, recovery_gate, supervisor, commit_executor, adapter, transport, inventory or runtime/seed/host/substrate changes. Bounded existing dispatcher consumers are explicitly in scope so ownership cannot be discarded at the outer boundary.
- No OS process-identity/signaling redesign, arbitrary-descendant containment, Darwin atomic-signaling work, PID-reuse mechanism, pre-first-snapshot cleanup expansion, or broader P0T3 lifecycle policy. An unresolved in-flight outcome must fail closed without guessing success from PID absence, timestamps or mutable file bytes.
- Do not change later RRC context semantics, RRT transport, RR refusal policy or IB inventory authority. Do not erase valid pending authority, replay completed mutators, restage prepared private-review checkpoints, bypass gates, import stopped candidate/receipt authority, or replay either consumed fleet operation.
- Do not fix the predecessor's LOW derived evidence wording, broaden packet-generation repair, add speculative safety cases, or create extra queue rows for nonblockers. Preserve unrelated user WIP, retained TASKS stash673a84136e45aba8d69686d41b2039e27447193d and all backups.
- Preserved source may be reused only as code/test reference from the explicit read-only snapshot; old execution artifacts and prior approvals are not new-candidate authority. Source snapshots must not be edited or staged. The prior300-second recovery cap belongs to excluded recovery_gate.py; do not redesign scheduling, test semantics, fixtures or recovery infrastructure to evade it.

## Stop conditions

- Before launch require exact c7fed5bba8de7898b686a636cecc42e379968eec base/primary/remote agreement, original R1 mutating owners absent, validated source hashes unchanged, fresh unique target/branch/bus/session, and selected Codex gpt-6-astra/max pins with providerless commit. Interrupted R1 has no normal-terminal continuation receipt; do not fabricate one.
- If the preserved four-file candidate cannot be reused without changing its proven behavior or touching an excluded path, identify the exact reproduced contradiction once and preserve the code and evidence. Do not manufacture a code change or repeat a known failed packet boundary.
- If a demonstrated blocker cannot be repaired within the two production modules and two test modules, preserve evidence and identify the exact required boundary once; do not loop on the same excluded path, hand-edit packet authority, or silently widen scope.
- Stop fail-closed if interrupted/ambiguous ownership can launch another mutator, start review/recovery, lose authority through generic dispatcher handling, or if normal known-success/explicit failure behavior is corrupted. Do not stop or widen for unrelated hypothetical/nonblocking cases.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`

## Acceptance criteria

- Existing R1 public before/after reproductions and tested code are credited; the reused four-file implementation is freshly bound and validated by the same full public-path suite and current independent review, without unnecessary reimplementation.
- Durable ownership is established before mutating invocation; ambiguous resumes perform zero new mutating or review/recovery actors and preserve authority. Known success is sealed before fallible post-success work and resumes only owed continuation; ordinary success and explicit actor-failure controls pass.
- Both public dispatcher routes and their relevant continuation/retry/recovery/error consumers preserve this same contract without generic retry or destructive state clearing. Existing bridge-fix and prepared private-review tests remain green.
- Only the eight required source/test/documentation/governance paths plus optional exact same-wave nonblocker change. Every original queue/TODO identity and semantic order is retained; CP is landed, CO is this existing current slot, RRC next, with no added precursor or fleet action.
- Declared focused/full-module evidence and all native gates, independent reviews, providerless commit, push, PR, CI, merge, primary fast-forward and honest terminal reporting complete without runtime/Mu closure claims.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCO-IN-FLIGHT-IMPLEMENTER-OWNERSHIP]; wave id `pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`.
- TASKS.md authority: the 2026-09-12 tracker sync note for wave `pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12 --output reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12`
- Active packet: `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7809f41cc646cf430e6ce319ea208c8aa02ef68e54f842da29391c16779a9cf8`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_executor_dispatch.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`, `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12_2026-09-12.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrco-inflight-implementer-ownership-r2-2026-09-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
