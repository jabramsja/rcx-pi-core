# N3-Engine-Run-Algorithm-Manifest-Authority-Source-Lock-2026-05-25

Date: 2026-05-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25
Class: L4_ENABLER
Category: control-plane tracker/package sync plus recovery/Phase B handoff-builder automation
Phase-A-Lock: LOCKED
Phase-A-Lock-Reason: same-wave `TASKS.md` tracker proof now exists at `TASKS.md:432`, but this Phase B enabler package only repairs package/tracker binding and handoff/receipt recovery automation; it does not grant future structural source inspection or implementation work.
Authorization: LIMITED-GO for the current Phase B pre-supervisor enabler package only. NO-GO remains for source inspection, implementation, or runtime changes until a later Phase A review accepts the structural successor.
Tracker proof: PRESENT at `TASKS.md:432` for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25`.
Bridge disposition: tracker-proof blocker repaired for the current enabler package; handoff/receipt recovery now uses builder/API surfaces; Phase B now stages the commit-ready packet status before refreshing receipt-backed handoff authority.
Blocking finding: The previous staged package claimed `L4_STRUCTURAL` while changing only tracker/control-plane/indicator files, and recovery could only repair some handoff/receipt failures through narrow manual or standalone paths. The current package binds the tracker/control-plane/tooling/test repair as `L4_ENABLER`.
Reviewer-blocker resolution: The same-wave tracker note is staged, this packet/tracker now classify the current pre-supervisor package as an enabler handoff, and recovery uses the owning Phase B/commit builders instead of fabricating receipt authority. The Phase B dispatcher handoff builder rejects decision-only receipt stubs and plan/routing wave drift before writing `phase_b_handoff.json`, and Phase B reruns the supervisor after staging the final packet status so receipts cannot authorize a stale index. The future source-lock remains a separate structural successor gated by Phase A and L4 structural evidence.
Purpose: Preserve the bounded Phase A successor plan for the N3 run_algorithm manifest authority source-lock wave while staging the tracker/package proof and recovery builder automation needed for pre-supervisor validation. After a later bridge review accepts Phase A, the successor may only move run_algorithm accepted-set authority into explicit Mu-owned metadata in `mu/seed_registry_manifest.v1.json` and derive Python/JS run_algorithm acceptance from that metadata through the exact conditional files listed below.

## Scope

Current rewrite scope:

- `README.md`
- `TASKS.md`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_recovery_gate.py`
- `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`
- `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`

No runtime, substrate, seed, registry, projection, generated manifest, scheduler, push, PR, Claude, hidden/local-memory, or unrelated tooling edit scope is granted by this enabler package. Executor/recovery scope is limited to Phase B dispatcher handoff rebuild and recovery builder selection for handoff/receipt failures.

Evidence scope used for this rewrite:

- This packet file.
- `README.md:21`, synced to the tracked-marker count in `STATUS.md:84` and `STATUS.md:90`.
- `TASKS.md:432`, the same-wave tracker note for this package.
- `TASKS.md:630-638`, including the active parent queue and every-wave packet/tracker requirement.
- The targeted tracker lookup `rg -n "n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25|N3-Engine-Run-Algorithm-Manifest-Authority-Source-Lock" TASKS.md`, which now returns the same-wave tracker note.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestFixHandoffReceiptBuilderRefresh mu/tests/tools/test_recovery_gate.py::TestStagePathSymlinkAliasRecovery::test_missing_phase_b_handoff_routes_to_builder_refresh mu/tests/tools/test_recovery_gate.py::TestStagePathSymlinkAliasRecovery::test_handoff_receipt_rejection_routes_to_builder_refresh mu/tests/tools/test_recovery_gate.py::TestTier2FixesMap::test_all_tier2_registered mu/tests/tools/test_phase_b_executor.py::TestPrepareCommitHandoff::test_dispatcher_builder_rebuilds_handoff_with_phase_b_receipt mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_run_phase_b_restages_final_packet_status_before_handoff_receipt --tb=short` (`11 passed`).
- `python3 tools/checks/enforce_l4_execution_contract.py --files README.md TASKS.md mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json --wave-id n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25 --wave-class L4_ENABLER`.
- Governing predecessor lines `reports/control_plane/n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19_2026-05-19.md:229-265` and `:336-341`.

Tracker blocker status:

- The same-wave `TASKS.md` tracker-entry blocker is cleared for this enabler package by `TASKS.md:432`.
- Future source inspection or implementation still requires later Phase A acceptance and a structural package with runtime/substrate and gate-linked test evidence.

Conditional successor write set, if and only if a later Phase A review grants GO:

- `TASKS.md`: maintain only the same-wave tracker entry for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25`.
- `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`: keep the successor packet synchronized with the implemented result.
- `mu/seed_registry_manifest.v1.json`: add explicit run_algorithm authority metadata as the source of truth.
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`: validate/export `authority.run_algorithm` metadata and update `SEED_REGISTRY_MANIFEST_SHA256` in lockstep with the manifest bytes.
- `mu/host/js/core/seed_loader.js`: validate/export `authority.run_algorithm` metadata and update `SEED_REGISTRY_MANIFEST_SHA256` in lockstep with the manifest bytes.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`: replace the Python host allowlist source with manifest-derived run_algorithm authority.
- `mu/host/js/engine/pipeline.js`: replace the JavaScript host allowlist source with manifest-derived run_algorithm authority while preserving scheduler lazy-load behavior as a load path only.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`: prove Python and JavaScript accept exactly the manifest-authorized set and reject non-authorized registered seeds and rogue seed-map injection.
- `mu/tests/structural/test_rcx_enginenew_scheduler.py`: preserve the Python scheduler boundary load path.
- `mu/tests/parity/test_rcx_engine_scheduler_parity.py`: preserve Python/JS scheduler boundary parity.

No directory-level scope is granted by the parent paths above.

## Work items

Current enabler package work items:

1. Record same-wave tracker proof for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25` at `TASKS.md:432`.
2. Classify the current docs/tracker/control-plane/indicator/tooling/test handoff as `L4_ENABLER`, not `L4_STRUCTURAL`.
3. Sync root `README.md` tracked-marker count to canonical `STATUS.md` truth for founder attestation.
4. Add a Phase B-owned dispatcher handoff rebuild API that can regenerate `phase_b_handoff.json` only when an existing supervisor receipt path is supplied and validated.
5. Add recovery classification/fix routing for handoff/receipt failures: use the Phase B builder when receipt evidence exists, arm Phase B retry when COMMIT_GO receipt evidence is absent, and use commit-builder standalone only for non-Phase-B staged recovery.
6. Stage the commit-ready packet status before final handoff generation and rerun the supervisor so `pre_commit_receipt_path` binds the same index that commit_executor receives.
7. Keep Phase A locked for future source inspection and implementation work until a later Phase A review grants GO.
8. Do not inspect source or implementation files for the future structural successor from this enabler package.
9. Do not relist the already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work from `TASKS.md:633` as pending.

Conditional successor work items after tracker proof exists and Phase A receives GO:

1. Verify and cite the same-wave `TASKS.md` tracker entry before any source or implementation inspection.
2. Lock `mu/seed_registry_manifest.v1.json` as the only accepted-set authority source for run_algorithm eligibility metadata.
3. Validate/export the manifest `authority.run_algorithm` metadata in `seed_integrity.py` and `seed_loader.js`, with only the forced manifest SHA256 constant updates in those files.
4. Replace duplicated Python/JS host accepted-set allowlists in `engine_pipeline.py` and `pipeline.js` with metadata-derived acceptance that does not infer authority from seed names, seed status, dependencies, projection ids, scheduler behavior, compatibility load paths, or host exception tables.
5. Preserve the accepted run_algorithm seed set exactly as:
   - `recurrence.v1.json`
   - `recurrence.v2.json`
   - `exhaustion.v1.json`
   - `fix.v1.json`
   - `rcx_engine_scheduler.v1.json`
6. Preserve `recurrence.v1.json` compatibility acceptance and scheduler lazy-load behavior only as load-path compatibility, not as independent authority sources.
7. Add focused coverage only in the three named test files proving the manifest-derived accepted set, rejection of non-authorized registered seeds and rogue seed-map injection, and preservation of scheduler boundary load/parity behavior.
8. Keep manifest integrity limited to metadata validation/export plus manifest SHA lockstep in the two named loader/integrity files; do not widen into binary/TLV, production loader defaults, seed checksums, or broader checksum-policy work.

## Constraints

- No runtime/source-lock implementation work is authorized by this enabler package.
- No source or implementation inspection is authorized until a later Phase A review accepts the structural successor.
- This packet plus the same-wave tracker note at `TASKS.md:432` satisfies tracker proof for the current enabler handoff only; it is not Phase A GO.
- This rewrite may edit only the current staged enabler package: `README.md`, `TASKS.md`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, this packet, and the same-wave L4 indicator artifact if regenerated.
- Do not edit any file outside the exact conditional successor write set listed in Scope after tracker proof and Phase A GO exist.
- Do not edit `mu/programs/*.json`, generated manifests, ratchet baselines, Stage0, scheduler seed projections, substrate, production loader defaults, binary/TLV paths, seed checksums, checksum policy, or integrity logic beyond the two named manifest-integrity surfaces.
- Do not add host exception tables or make Python/JavaScript semantically smarter than the manifest metadata.
- Do not infer run_algorithm authority from seed file names, manifest status fields, dependency lists, projection ids, scheduler behavior, or compatibility load paths.
- Do not edit dispatcher, commit, push, PR, receipt, check, hidden/local-memory, or unrelated tooling surfaces. Executor/builder scope is limited to Phase B handoff rebuild and recovery builder selection in the two named executor files.
- Existing dispatcher/pipeline tooling may be used operationally after this enabler package passes validation; this packet grants no write scope beyond the named Phase B/recovery builder repair.
- Do not edit Claude files.
- Do not claim `FOUNDER_OVERRIDE:<wave_id>` or treat the parent queue override as a substitute for same-wave tracker proof.
- Do not use this packet to relist already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not hand-author `/mu` semantic fixes outside the dispatcher/pipeline path.

## Stop conditions

- Stop with NO-GO before source or implementation inspection if the same-wave `TASKS.md` tracker entry for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25` is absent or uncited. Tracker proof is currently present at `TASKS.md:432`; Phase A GO remains absent.
- Stop if any review attempts to treat this enabler handoff, this packet, the parent queue tracker, or the parent queue `FOUNDER_OVERRIDE` as Phase A GO or implementation authorization.
- Stop if the current docs/tracker/control-plane/indicator package is treated as `L4_STRUCTURAL` without runtime/substrate and gate-linked test deltas.
- Stop if Phase A cannot keep the future implementation write set within the exact files named in Scope.
- Stop if the accepted run_algorithm seed set would differ from the five listed seeds.
- Stop if the design requires host exception tables, seed-name inference, dependency inference, projection-id inference, or other host-only semantic interpretation.
- Stop if preserving `recurrence.v1.json` compatibility or scheduler lazy-load behavior would become a second authority source rather than load-path compatibility.
- Stop if a needed change touches any excluded file, policy, or surface named in Constraints.
- Stop if a needed change requires dispatcher, commit, push, PR, receipt, check, hidden/local-memory, Claude, unrelated tooling edits, or executor/builder edits outside the named Phase B/recovery files.
- Stop if current code evidence in a later implementation phase proves a listed work item is already landed; remove that item from pending work and acceptance criteria rather than relisting it as unresolved.

## Acceptance criteria

Packet rewrite acceptance criteria for the current enabler handoff:

- The packet contains required Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The packet states that same-wave `TASKS.md` tracker proof exists at `TASKS.md:432`.
- The packet records the previous structural-classification failure as a package defect: a docs/tracker/control-plane/indicator-only handoff cannot be `L4_STRUCTURAL`.
- The root `README.md` tracked-marker count matches canonical `STATUS.md` truth.
- The packet cites that `TASKS.md:638` requires both a control-plane packet and a `TASKS.md` tracker entry for every wave.
- The packet does not claim Phase A GO, implementation authorization, source-inspection authorization, packet-local override authority, or same-wave override authority.
- The packet states that this current staged package is `L4_ENABLER` and has no runtime/substrate or structural L4 gate-test delta.
- The current rewrite scope is limited to the eight files listed in Current rewrite scope.
- Focused tests prove handoff/receipt recovery classification, Phase B dispatcher builder refresh, Phase B retry on absent receipt evidence, commit-builder fallback for non-Phase-B staged recovery, Tier 2 registration, and commit-ready packet status receipt refresh.
- The conditional successor write set is bounded to exactly the ten files listed in Scope, with no directory-level grant and no builder/receipt/check, dispatcher/executor/commit/push/PR, same-wave pipeline repair, hidden/local-memory, Claude, or unrelated tooling write surface beyond the current named enabler repair.

Future Phase A GO acceptance criteria after the tracker blocker is cleared:

- Same-wave `TASKS.md` tracker proof for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25` exists before source or implementation inspection and is cited in this packet.
- Implementation proves `mu/seed_registry_manifest.v1.json` is the source of truth for run_algorithm acceptance metadata.
- Implementation proves Python and JavaScript derive the same accepted set from the manifest metadata and accept exactly `recurrence.v1.json`, `recurrence.v2.json`, `exhaustion.v1.json`, `fix.v1.json`, and `rcx_engine_scheduler.v1.json`.
- Implementation proves non-authorized seeds are rejected without host exception tables or inferred authority.
- Implementation preserves `recurrence.v1.json` compatibility acceptance and scheduler lazy-load behavior only as load-path compatibility.
- Implementation does not change excluded files or policies listed in Constraints.
- Focused validation includes the three named test files for the manifest-derived accepted set and scheduler boundary behavior plus existing L4 execution-contract, host-semantics ratchet, host-authority inventory ratchet, docs consistency, and wave-indicator collection checks appropriate to the final touched files.

## Grounding / Authorization

- `TASKS.md:630-638`: `[NEXT-CODEX-POST-REDTEAM]` is founder-authorized and OPEN; remaining structural reduction requires separate bounded packets; every wave requires a control-plane packet plus TASKS tracker entry; manual pipeline repair is allowed only as a same-wave mechanical unblocker with a guard or precise follow-up automation packet.
- `README.md:21`, `STATUS.md:84`, and `STATUS.md:90`: root README tracked-marker count must match canonical current tracked-marker truth.
- `TASKS.md:432`: same-wave tracker proof exists for `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25`, with this package classified as `L4_ENABLER`.
- `mu/tools/executors/phase_b_executor.py`: Phase B owns `prepare_dispatcher_commit_handoff_from_routing_record`, which rebuilds dispatcher-visible handoffs through Phase B/commit builders only when a receipt path is supplied, repo-contained, shaped like a real supervisor receipt, and bound to the same routing wave as the tracked packet. Phase B also stages the commit-ready packet status before the final handoff and reruns the supervisor so the receipt path cannot authorize a stale staged diff.
- `mu/tools/executors/recovery_gate.py`: recovery classifies handoff/receipt failures as Tier 2, chooses Phase B builder refresh when receipt evidence exists, arms Phase B retry when COMMIT_GO receipt evidence is absent, and leaves commit-builder standalone refresh as the non-Phase-B fallback.
- `TASKS.md:633`: current code truth says the engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration work landed and must not be relisted as unresolved.
- `TASKS.md:638`: every wave requires a control-plane packet plus a `TASKS.md` tracker entry. The parent queue `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05` authorizes the queue protocol only; it is not Phase A GO and is not implementation authorization.
- `rg -n "n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25|N3-Engine-Run-Algorithm-Manifest-Authority-Source-Lock" TASKS.md` returns `TASKS.md:432`, so same-wave tracker proof exists for this package.
- Authorization resolution: LIMITED-GO for current Phase B pre-supervisor enabler validation only; NO-GO remains for source inspection and implementation until a later Phase A review accepts the structural successor.
- `reports/control_plane/n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19_2026-05-19.md:229-265`: governing predecessor locks the successor to exact files and forbids `mu/programs/*.json`, generated manifests, ratchet baselines, Stage0, scheduler seed projections, substrate, production loader defaults, binary/TLV paths, seed checksums, checksum policy, integrity logic beyond the two named manifest-integrity surfaces, dispatcher/executor/commit/push/PR surfaces, Claude files, hidden/local-memory surfaces, and unrelated tooling.
- `reports/control_plane/n3-engine-pipeline-run-algorithm-authority-source-prereq-2026-05-19_2026-05-19.md:336-341`: governing predecessor stop conditions require NO-GO if same-wave tracker proof is absent before source or implementation inspection; tracker proof is now present, but Phase A GO remains a separate requirement.
- No `FOUNDER_OVERRIDE:<wave_id>` is claimed by this packet. The parent queue override at `TASKS.md:638` authorizes the queue protocol; the same-wave tracker proof is the tracker note at `TASKS.md:432`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25`
- Active packet: `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `README.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`
  - `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25`
- Active packet: `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f1eead35207b67c2f83d6557885b40c3983a10f7f828d6121729b0e546c0293f`
- Indicator artifact: `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`
- Current staged files:
  - `README.md`
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25_2026-05-25.md`
  - `reports/l4_wave_indicators/n3-engine-run-algorithm-manifest-authority-source-lock-2026-05-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
