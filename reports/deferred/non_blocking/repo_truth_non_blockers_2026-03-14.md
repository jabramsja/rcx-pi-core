# Repo Truth Non-Blockers (Active Residue)

Extracted on 2026-03-14 from:

- `reports/codex/Archive/non_blockers/drift_2026-03-12_repo_redteam_non_blockers.md`
- `reports/codex/Archive/non_blockers/redteam_2026-03-14_p7a_p7d_non_blockers.md`

Archived as stale/resolved from the source snapshots:

- the old JS public-path `vmConfig` wiring concern is resolved
- the old startup-cost-before-use concern is resolved
- Hypothesis fuzzer timeout in hemisphere routing parity tests is resolved
- old blocker carryovers N10/N11 were archived to `reports/archive/deferred/repo_truth_blockers_2026-03-14.md`

2026-05-06 cleanup note: resolved sections N4, N6, N7, N9, N12, N13,
N15, N16, N17, and N19 were moved to
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_partial-closed-by-deferred-non-blocking-cleanup-2026-05-06.md`.
Truth-sweep note (2026-05-07): resolved Claude-referencing section N18 was moved
to
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_partial_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`.
The active packet now retains only current `/mu` structural advisory status and
does not authorize `/mu` implementation.

2026-05-12 cleanup note: closed duplicate Stage0 capture provenance pointer
N14 was moved to
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N14_stage0_duplicate_pointer_closed-by-stage0-capture-provenance-deferred-cleanup-2026-05-12.md`.
N1 VM coverage bookkeeping is closed by PR #940 /
`vm-cutover-coverage-trace-implementation-2026-05-12` and archived as
historical evidence at
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N1_vm_coverage_bookkeeping_closed-by-vm-cutover-coverage-trace-implementation-2026-05-12.md`.
N3 broad host-surface boundary remains live in this active packet. N5 JS
pipeline shape governance is closed by
`js-engine-pipeline-shape-governance-test-2026-05-12` / PR #937 and archived
as historical evidence at
`reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N5_js_pipeline_governance_closed-by-post-js-pipeline-governance-deferred-cleanup-2026-05-12.md`.

2026-05-13 transparent JS Proxy provenance closure: the separate retained
transparent Proxy advisory is closed by
`transparent-js-live-container-provenance-implementation-2026-05-13` and
archived at
`reports/archive/deferred/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-transparent-js-live-container-provenance-implementation-2026-05-13.md`.
The active repo-truth retained advisory in this packet remains N3 broad
host-surface boundary only.

2026-05-13 successor routing note: PR #944 /
`broad-host-surface-reduction-boundary-2026-05-13` and PR #945 /
`broad-host-surface-next-boundary-slice-2026-05-13` closed bounded JS
host-surface slices, and PR #946 closed only generated DOC_ACCURACY bridge
residue. N3 remains active because those slices do not prove broad
host-surface elimination. The next bounded successor route is
`reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`,
which must use dispatcher-first Phase A to select one exact source-grounded
slice or leave N3 active with a precise next packet. Baseline-only cleanup is
not N3 closure.

2026-05-10 triage evidence refresh:

- N1 was advisory in this 2026-05-10 snapshot because `_step_kernel_with_vm`
  reconstructed coverage
  events in host code at `mu/host/python/rcx_pi/selfhost/step_mu.py:1035`
  through `mu/host/python/rcx_pi/selfhost/step_mu.py:1142`; exact bookkeeping
  proof is routed to
  `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
  Current closure is recorded in the 2026-05-12 VM cutover coverage trace
  implementation note below.
- N3 remains an architectural progress boundary, not a single implementable
  defect; `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  exits 0 with no increases/decreases and
  `python3 tools/checks/check_host_authority_inventory_ratchet.py` exits 0
  with `311 total` / `217 authority`.
- N5 was still advisory in this 2026-05-10 snapshot because
  `mu/host/js/engine/pipeline.js` was a large single engine pipeline file
  (`wc -l` reported 1160 lines) and no decomposition contract was present in
  this active packet. Current closure is recorded below and archived after the
  focused structural guard landed.
- N14 overlapped the then-active Stage0 capture advisory retained in
  `redteam_2026-03-14_repo_non_blockers.md`; the 2026-05-12 cleanup closed
  and archived that duplicate pointer after
  `stage0-capture-path-provenance-implementation-2026-05-12` landed.
- Next-wave packet routing emitted by
  `repo-truth-mu-structural-advisory-triage-2026-05-09`:
  `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`,
  `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`,
  `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`,
  and `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
  This packet remains advisory evidence only and does not authorize direct
  `/mu` structural implementation.

2026-05-11 reconciliation:

- N2 is closed/superseded by PR #927 / merge
  `8334c369d7a302cca568de0a088ea9ca1bd1c2f5` and commit
  `ee69f0a0b9b9023bc278b91e7b72419eede6f813`.
  Current `mu/tests/parity/test_js_vm_bridge_parity.py` uses the public
  `stepKernel(..., {returnMeta:true, vmConfig})` entrypoint with instrumented
  Stage0 bundles and ordering-sensitive negative controls, while
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py` scans both
  `_stage0VmStepTrusted` and `StepTrusted` fragments. The old JS bridge
  source-lock/e2e ordering slice is archived at
  `reports/archive/deferred/repo_truth_non_blockers_2026-03-14_partial-closed-by-post-js-bridge-remaining-mu-nonblocking-reconciliation-2026-05-11.md`
  and is no longer live pending work.
- N1 was live under
  `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
  at this reconciliation point; current closure is recorded in the 2026-05-12
  VM cutover coverage trace implementation note below.
- N3 remains a broad architectural boundary observation with no direct
  implementation route; any broad host-surface reduction requires a separate
  bounded packet.
- N5 is now closed by
  `js-engine-pipeline-shape-governance-test-2026-05-12` and archived as
  historical evidence; it is not a live advisory in this active packet.
- N14 was a duplicate pointer to the canonical Stage0 route and is now closed
  by `stage0-capture-path-provenance-implementation-2026-05-12`; the archived
  duplicate pointer is
  `reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N14_stage0_duplicate_pointer_closed-by-stage0-capture-provenance-deferred-cleanup-2026-05-12.md`.
- Transparent JS Proxy provenance is classified in
  `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  and governed by
  `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`;
  it is not a separate section in this repo-truth source packet.

2026-05-12 post-JS pipeline governance cleanup:

- N5 JS pipeline shape governance is closed after PR #937 and the same-wave
  structural guard recorded in `TASKS.md` under
  `js-engine-pipeline-shape-governance-test-2026-05-12`.
- The preserved N5 historical text was moved to
  `reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N5_js_pipeline_governance_closed-by-post-js-pipeline-governance-deferred-cleanup-2026-05-12.md`.
- Active repo-truth retained advisory in this packet is N3 broad host-surface
  boundary only. N1 VM coverage bookkeeping is closed by PR #940 /
  `vm-cutover-coverage-trace-implementation-2026-05-12`. Transparent JS Proxy
  provenance is closed by
  `transparent-js-live-container-provenance-implementation-2026-05-13` and
  archived separately.
- This cleanup performed no runtime, Stage0, seed, scheduler, registry, parity,
  production `/mu`, host-oracle, or Claude-related implementation work.

2026-05-12 VM cutover coverage trace implementation closure:

- N1 VM coverage bookkeeping is closed by PR #940 /
  `vm-cutover-coverage-trace-implementation-2026-05-12`.
- Python and JS Stage0 VM step results now emit the same structural
  `attempt_trace` shape with ordered attempted program IDs, final
  match/stall outcome, and matched program ID.
- Python `_step_kernel_with_vm` now records `record_no_match` /
  `record_match` from the VM-emitted attempt trace instead of deriving
  coverage from host-side bundle order.
- Evidence:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py mu/tests/l4_gates/test_stage0_vm_cutover.py --tb=short`,
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short`,
  and `node mu/host/js/eval_step.js`.
- Historical N1 source text moved to
  `reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N1_vm_coverage_bookkeeping_closed-by-vm-cutover-coverage-trace-implementation-2026-05-12.md`.
- Active repo-truth retained advisory in this packet is now N3 broad
  host-surface boundary only. Transparent JS Proxy provenance is closed by
  `transparent-js-live-container-provenance-implementation-2026-05-13` and
  archived separately.

## Active Non-Blockers

### N3. P7-d is execution-path progress, not broad host-surface reduction

- **Outcome:** retained architectural boundary observation.
- **Governing route:** no direct implementation route; future broad
  host-surface reduction must be authorized by a separate bounded control-plane
  packet from the structural lane.
- **Current proof gap:** tracked markers remain much smaller than the broader
  authority and total inventory ledgers, so execution-path progress must not be
  reported as broad host-surface elimination.
- **Hard stop before implementation:** do not implement broad host-surface
  reduction from this observation; route exact runtime/control-plane work in a
  successor packet with file scope and validation.
- **Doctrine boundary:** future reductions must program in Mu or narrow
  bootstrap assumptions, not move more semantic authority into Python or
  JavaScript host code.

- tracked markers are flat
- the broader authority and total inventory ledgers remain much larger than the
  narrow tracked-marker ledger
**Why deferred:** This is an honest observation, not a fixable defect. P7-d reduces
host-semantic debt on the kernel execution path (match/subst/step), but the broader
authority inventory (217 sites) and total inventory (312 sites) include all runtime
functions — most of which are not on the kernel path. Reducing the broader inventory
requires eliminating host constructs in engine pipeline, hemisphere routing, ontology
promotion, etc. — each of which is a separate L4 workstream.
**No single fix** — this is the nature of incremental reduction.
