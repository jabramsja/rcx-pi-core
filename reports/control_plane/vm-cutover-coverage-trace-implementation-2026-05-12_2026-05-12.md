# Vm-Cutover-Coverage-Trace-Implementation-2026-05-12

Date: 2026-05-12
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: vm-cutover-coverage-trace-implementation-2026-05-12
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Target gate: G8
Purpose: Route retained N1 VM cutover coverage bookkeeping through a bounded Stage0 structural trace implementation packet.

## Scope

Files and directories in scope for the implementation wave:

- `reports/control_plane/vm-cutover-coverage-trace-implementation-2026-05-12_2026-05-12.md` - governing Phase A packet for this wave.
- `mu/host/python/rcx_pi/selfhost/stage0_vm.py` - Python Stage0 VM result contract for deterministic structural attempt trace output.
- `mu/host/js/core/stage0_vm.js` - JS Stage0 VM result contract for the same substrate-neutral trace shape and semantics.
- `mu/host/python/rcx_pi/selfhost/step_mu.py` - Python VM cutover coverage bookkeeping consumer, limited to deriving `record_no_match` / `record_match` from the VM-emitted trace.
- `mu/tests/l4_gates/test_stage0_vm.py` - focused Python Stage0 trace-shape and match/stall coverage.
- `mu/tests/l4_gates/test_stage0_vm_cutover.py` - focused Python VM cutover coverage composition tests.
- `mu/tests/parity/test_js_parity_automated.py` - Python/JS trace-shape parity coverage for Stage0 output only.
- `TASKS.md` - same-wave L4 tracker note and detector-visible authority only after implementation evidence exists.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` - active N1 source, to update only if implementation proves N1 closure.
- `reports/archive/deferred/` - archive destination only if N1 closure is proven and active source content is removed from the active deferred lane.
- `reports/l4_wave_indicators/` - same-wave indicator artifact destination if required by L4 closeout automation.
- `mu/tools/executors/phase_b_executor.py` - same-wave mechanical repair only for the commit-blocking duplicate tracker-note sync defect found during commit executor closeout.
- `mu/tests/tools/test_phase_b_executor.py` - focused regression coverage for the same-wave Phase B tracker-note sync repair.
- `mu/tools/executors/executor_config.json` - pre-push repair wave only to restore the tracked `commit_executor` timeout default rejected by the default-config guard.
- `mu/tools/executors/executor_dispatch.py` - pre-push repair wave mechanical fix only to keep dispatcher-owned `commit_executor` timeout recovery overrides in memory instead of writing tracked config defaults.
- `mu/tests/tools/test_executor_dispatch.py` - focused regression coverage for dispatcher-owned timeout override behavior and default-config drift.

This Phase A rewrite edits only this packet. Later implementation must remain within the scope list above unless reproduced code truth proves the packet must be revised before work continues.

## Work Items

1. Lock this same-wave implementation packet after Phase A agent review and bridge convergence; do not create a second successor packet for this wave.
2. Reproduce the governing N1 proof gap before implementation: active deferred N1 says `_step_kernel_with_vm` coverage bookkeeping is reconstructed from host-side bundle order because Stage0 results do not emit ordered attempted-program traces or match/no-match events.
3. Extend the Stage0 VM result contract in Python and JS with a deterministic structural attempt trace that expresses ordered attempted program IDs and final match/stall outcome in a substrate-neutral shape.
4. Update Python `_step_kernel_with_vm` so coverage bookkeeping derives `record_no_match` / `record_match` from the VM-emitted trace rather than reconstructing attempted order solely from `bundle["program_order"]`.
5. Preserve existing first-match-wins and no-match/match coverage composition semantics while reducing host-side reconstruction.
6. Add focused tests for Python Stage0 trace shape, JS Stage0 trace shape/parity, Python VM cutover coverage composition, and match/stall negative or control cases.
7. Add a detector-visible same-wave `TASKS.md` L4 tracker note and indicator binding only after implementation evidence exists.
8. Update the active deferred N1 source and archive closed N1 content only if the implementation proves N1 closure; otherwise leave N1 active with current limitations recorded.
9. If commit/supervisor evidence proves a pipeline-generated tracker-note contradiction blocks closure, repair the Phase B tracker-note sync mechanically in the same wave and cover it with focused executor tests; do not broaden into unrelated pipeline cleanup.
10. If pre-push evidence proves a dispatcher/config recovery leak blocks push, route a bounded repair wave that restores the tracked default and adds a dispatcher regression that prevents `commit_executor` timeout recovery from drifting `executor_config.json`.

## Constraints

- Do not edit Claude-related files.
- Do not touch unrelated runtime, seed, scheduler, registry, production `/mu`, transparent JS Proxy provenance, N3 broad host-surface boundary, or closed N5 JS pipeline governance work.
- Do not add Python-only coverage semantics to JS. JS parity is limited to Stage0 structural trace output shape and semantics.
- Do not increase host semantics ratchet counts or host authority inventory.
- Do not use host-side bundle order as the sole source for Python VM cutover coverage after the trace exists.
- Do not mark N1 closed, remove it from active deferred docs, or archive its source text unless current implementation evidence proves closure.
- Do not treat `TASKS.md` tracker text as proof that every work item remains unlanded. If executor reproduction proves an item is already implemented in current code, revise pending work items and acceptance criteria before continuing.
- Do not widen this wave to broad deferred cleanup, report index cleanup, pipeline recovery, or implementation outside the explicit scope list.
- If a manual repair is needed, add a same-wave mechanical fix or a precise next-wave automation packet before closure.
- Pipeline repair scope is limited to reproduced commit-closeout blockers for this package: the Phase B duplicate tracker-note sync defect and the pre-push `commit_executor` timeout default drift rejected by `test_load_default_config`. Do not touch commit executor, recovery, pager, autoping, or unrelated builder surfaces in this wave.

## Stop Conditions

- Stop before Phase B implementation if this packet is not locked by Phase A review and bridge convergence.
- Stop if reproducing current code truth shows the listed work is already implemented, partially obsolete, or materially different from the governing packet; rewrite this packet instead of implementing stale tasks.
- Stop if the implementation requires files or directories outside the explicit Scope list.
- Stop if the proposed trace shape cannot be mirrored in both Python and JS as substrate-neutral Stage0 output.
- Stop if the Python coverage consumer would still reconstruct attempted order solely from host-side `bundle["program_order"]`.
- Stop if preserving first-match-wins or existing no-match/match coverage composition would require new host-only semantics.
- Stop if host semantics ratchet or host authority inventory increases without a separate explicit authorization packet.
- Stop if N1 closure is not proven; leave deferred source active and do not archive it.
- Stop if same-wave `TASKS.md` authority, indicator binding, or `FOUNDER_OVERRIDE:vm-cutover-coverage-trace-implementation-2026-05-12` cannot be made detector-visible before commit closeout.

## Acceptance Criteria

- This packet contains explicit Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- Python and JS Stage0 VM results expose the same deterministic structural attempt trace shape for ordered attempted program IDs plus final match/stall outcome.
- Python `_step_kernel_with_vm` derives VM cutover coverage events from the VM-emitted trace and preserves existing first-match-wins plus `record_no_match` / `record_match` composition.
- Focused Python tests cover Stage0 trace shape and VM cutover coverage composition for match and stall/control cases.
- Focused JS/parity tests cover Stage0 trace shape semantics without adding a JS coverage system.
- Active deferred N1 is closed and archived only if current evidence proves closure; otherwise the deferred source remains active and accurately records remaining proof limits.
- N3 broad host-surface boundary and transparent JS Proxy provenance remain active unless routed by separate packets.
- Same-wave `TASKS.md` tracker authority includes `FOUNDER_OVERRIDE:vm-cutover-coverage-trace-implementation-2026-05-12` and binds the implementation, packet, evidence command, and indicator artifact.
- Phase B tracker-note sync mechanically reconciles same-wave tracker notes across `TASKS.md` sections so a stale pre-supervisor package note cannot coexist with the canonical implementation tracker for the same wave.
- Dispatcher timeout recovery keeps `commit_executor` overrides in memory only, while the tracked `executor_config.json` default remains `3600`.
- Required validation before commit executor closeout passes:
  - `git status --short --branch`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py mu/tests/l4_gates/test_stage0_vm_cutover.py --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short`
  - `node mu/host/js/eval_step.js`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `./tools/checks/check_docs_consistency.sh`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id vm-cutover-coverage-trace-implementation-2026-05-12`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_phase_b_tracker_sync_reconciles_same_wave_notes_across_task_sections mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_stage0_trace_scope_infers_host_debt_reduction mu/tests/tools/test_phase_b_executor.py::TestMaintenanceTrackerMetadataPropagation::test_l4_indicator_collection_reruns_after_tracker_only_crash --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_executor_dispatch.py::TestDispatcherConfig::test_load_default_config tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_uses_correct_key tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_tier2_commit_timeout_override_stays_in_memory tests/tools/test_executor_dispatch.py::TestRecoveryGateWiring::test_apply_overrides_writes_to_disk --tb=short`

## Grounding / Authorization

- TASKS.md line 292 authorizes the predecessor `[NEXT-CODEX-POST-REDTEAM]` L4_ENABLER wave `vm-cutover-coverage-bookkeeping-proof-2026-05-09` and binds it to `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
- TASKS.md line 544 records retained `/mu` advisory boundaries after Stage0 cleanup and says N1 VM coverage bookkeeping remained active.
- TASKS.md line 548 records the later deferred cleanup state where N1 VM coverage bookkeeping, N3 broad host-surface boundary, and transparent JS Proxy provenance remain active after N5 cleanup.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` lines 110-123 retain N1 as a live advisory, identify the proof gap, hard-stop implementation from that source alone, and require Mu/Stage0 structural execution or parity-preserving VM trace rather than host-only coverage semantics.
- `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md` lines 166-181 define the later Phase B packet boundary: extend Python and JS Stage0 VM result contracts with a structural substrate-neutral trace, add parity tests for trace shape, update Python coverage emission to derive from VM-emitted trace, and add Python coverage composition tests.
- Bridge reviewer REQUEST_CHANGES for this packet is authoritative for this rewrite: the previous Scope was only a goal statement, and the packet lacked explicit stop conditions.
- Runtime structural L4_STRUCTURAL authority: `FOUNDER_OVERRIDE:vm-cutover-coverage-trace-implementation-2026-05-12`.

Founder-facing handoff: Questions? Concerns? Thoughts? -- Think hard
