# Keep final commit approval fresh after long native validation

Date: 2026-09-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-commit-receipt-order-r1-2026-09-22
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: c326bf66dce5d7d67eb38ded08fda288a96665e5766b7bbe58e72dd69c05a7e2
Purpose: Unblock the preserved R6 fleet/prevention wave by fixing the reproduced commit receipt ordering defect under existing row40; no new numbered task or unrelated hardening.

## Scope

Seven exact paths: two existing source/test files, two trackers, native packet/indicator and optional generated report. No new governed files, growth-cap changes, recovery classifier redesign, lifecycle expansion or numbered queue row.

Files and surfaces in scope:

- TASKS.md -- Existing row40 owns this actual landing blocker; preserve all268task IDs/39parked obligations and explicit R6/cleanup/Mu order.
- CHANGELOG.md -- Record only the demonstrated receipt-ordering repair.
- mu/tools/executors/commit_executor.py -- Place final fresh supervisor/receipt authority after long mechanical gates and before Git commit; preserve all existing native safety/continuation behavior.
- mu/tests/tools/test_commit_executor_receipt.py -- Fast behavioral proof for a gate taking longer than the receipt lifetime, final staged-state authority, gate failure ordering, and existing commit contracts.
- reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md -- Full packet authored by native PhaseA from this STUB.
- reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json -- Native indicator.
- reports/deferred/non_blocking/workingrcx-commit-receipt-order-r1-2026-09-22_bridge_nonblockers.md -- Optional exact same-wave native report; do not require creating or persisting an absent report.
- TASKS.md -- tracker-sync authority. The 2026-09-22 tracker sync note for wave `workingrcx-commit-receipt-order-r1-2026-09-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read reproduced evidence /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-native-prevention-r6-evidence-2026-09-22/receipt_expiry_root_cause.json and installed_precommit_hook_diagnostic.json. The existing meta_bridge_supervisor verifier allows1800seconds. R6 consumed2426seconds between final approval and failed commit. Current staged-SHA mismatch is exactly explained by native post-failure packet-status demotion: reversing only that status in memory yields approved SHA74b734371497313bc7a7b36735d9c25a56edddc861e7482bca952b580bd020b9. Do not treat the recovery label stale_active_items as proven root cause; unchanged checker passed34references.
2. Repair the native commit sequence in the existing commit_executor.py so all potentially long mechanical pre-commit/targeted-pytest/private-attribute checks and candidate mutations settle before final fresh supervisor approval and exact receipt-chain verification. Preserve supervisor package/evidence, handoff receipt authority, staged/index binding, candidate authority, hold behavior and post-commit continuation. Do not simply increase or disable receipt lifetime, rewrite timestamps, reuse old approval, bypass a test, or manually commit. Choose the smallest ordering change that satisfies these existing contracts; fresh final approval must be immediately usable by the actual Git hook.
3. Add focused fast regression coverage through existing public commit execution seams, using controlled elapsed time rather than a40minute sleep. Prove a long successful gate still reaches Git with fresh correct authority; failed checks never authorize Git; post-review staged mutation and invalid receipts still reject. Preserve all landed PR1310 canonical growth-cap producer/rejection and no-replay/pager regressions. No new test module, cap/exception changes or unrelated hardening.
4. Root supplies this external STUB only; PhaseA owns the full packet and native pipeline owns code/tests/review/commit/push/CI/merge. Run collection before full evidence and keep tool tests separate from docs. All model roles are Codex gpt-6-astra/max, commit providerless. Admit the exact optional nonblockers output before locking, but do not create or retain it merely as a requirement.
5. Keep existing row40 and todo synchronized with actual terminal evidence. Preserve all268unique task IDs/39parked obligations, four unrelated PRIMARY edits, R6 index/branch/candidate/receipts, older stashes/journals and all37consumed fleet operations. This small dependency exists only because the loaded PRIMARY committer stranded R6; it must land and synchronize before any expensive unchanged R6 retry. Do not port the entire R6 lifecycle candidate into this narrow bootstrap.
6. After verified landing, re-ground the smallest supported R6 continuation using freshly committed code; no frozen-contract overwrite or old receipt reuse. Preserve this ordering fix in the combined eventual R6/dev result. Required eligible folder retirement/useful-work integration remain ahead of Mu; separately owned unsafe targets must not blanket-block unrelated production. This bootstrap alone is not fleet cleanup completion.

## Constraints

- Existing row40 actual blocker only; seven paths; no new numbered queue row.
- Root writes external STUB/tracker/evidence only. Native pipeline owns packet/source/test/staging/commit/merge.
- No receipt TTL increase, stale receipt reuse, forged timestamps, skipped gates, hand staging/commit/push, broad retry loops or global pytest options.
- No edits to R6 carrier/index, Claude surfaces, runtime/hosts/seeds, existing fleet operations or journals. Preserve unrelated PRIMARY WIP and retained useful work.
- Optional exact same-wave generated nonblocking report is admitted but not mandatory. Hypothetical/nonblocking findings remain deferred.

## Stop conditions

- Stop only for reproduced mandatory out-of-scope dependencies before mutation; do not widen silently.
- Fail closed on changed candidate/invalid authority. Do not label existing preserved work landed or cleaned.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- Actual long-gate receipt expiry is prevented by correct native ordering without weakening existing receipt age/hash/decision authority.
- Focused behavioral regressions and all declared evidence pass; existing providerless commit, canonical cap producer, pager and no-replay behavior remain intact.
- Native review/commit/CI/merge/PRIMARY sync complete; same existing task keeps preserved R6, cleanup/useful work and Mu order explicit. No false fleet closure.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-commit-receipt-order-r1-2026-09-22`.
- Governing packet: this file, `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`.
- TASKS.md authority: the 2026-09-22 tracker sync note for wave `workingrcx-commit-receipt-order-r1-2026-09-22` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-commit-receipt-order-r1-2026-09-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-commit-receipt-order-r1-2026-09-22`
- Active packet: `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`
  - `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-commit-receipt-order-r1-2026-09-22 --output reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`, `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-commit-receipt-order-r1-2026-09-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-commit-receipt-order-r1-2026-09-22`
- Active packet: `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `11118335bd18577dae4bd6bd698a8c7e85b8ada52b859257514f82bdc9877163`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/checks/check_theater_risk_ratchet.py --json && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_commit_outcome_pager_lifetime.py mu/tests/tools/test_pr_disposition_no_replay_finalization.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`, `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/workingrcx-commit-receipt-order-r1-2026-09-22_2026-09-22.md`
  - `reports/l4_wave_indicators/workingrcx-commit-receipt-order-r1-2026-09-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
