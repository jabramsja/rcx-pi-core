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
N1 VM coverage bookkeeping, N3 broad host-surface boundary, and N5 JS pipeline
shape governance remain live in this active packet.

2026-05-10 triage evidence refresh:

- N1 remains advisory because `_step_kernel_with_vm` reconstructs coverage
  events in host code at `mu/host/python/rcx_pi/selfhost/step_mu.py:1035`
  through `mu/host/python/rcx_pi/selfhost/step_mu.py:1142`; exact bookkeeping
  proof is routed to
  `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
- N3 remains an architectural progress boundary, not a single implementable
  defect; `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  exits 0 with no increases/decreases and
  `python3 tools/checks/check_host_authority_inventory_ratchet.py` exits 0
  with `312 total` / `217 authority`.
- N5 remains advisory because `mu/host/js/engine/pipeline.js` is still a large
  single engine pipeline file (`wc -l` reports 1160 lines) and no decomposition
  contract is present in this active packet. It is routed to
  `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
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
- N1 remains live under
  `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
- N3 remains a broad architectural boundary observation with no direct
  implementation route; any broad host-surface reduction requires a separate
  bounded packet.
- N5 remains live under
  `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
- N14 was a duplicate pointer to the canonical Stage0 route and is now closed
  by `stage0-capture-path-provenance-implementation-2026-05-12`; the archived
  duplicate pointer is
  `reports/archive/deferred/repo_truth_non_blockers_2026-03-14_N14_stage0_duplicate_pointer_closed-by-stage0-capture-provenance-deferred-cleanup-2026-05-12.md`.
- Transparent JS Proxy provenance is classified in
  `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  and governed by
  `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`;
  it is not a separate section in this repo-truth source packet.

## Active Non-Blockers

### N1. Python VM cutover coverage reconstruction is not directly locked

- **Outcome:** retained live advisory.
- **Governing route:** `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
- **Current proof gap:** the completed Phase A packet reproduced that
  `_step_kernel_with_vm` still reconstructs coverage bookkeeping from host-side
  bundle order because Stage0 results do not emit ordered attempted-program
  traces or no-match/match events.
- **Hard stop before implementation:** no runtime, Stage0, coverage, seed,
  scheduler, registry, parity, or production `/mu` edits are authorized by this
  source packet or by the completed Phase A evidence packet.
- **Doctrine boundary:** future work must derive bookkeeping proof from
  Mu/Stage0 structural execution or a parity-preserving VM trace; it must not
  add host-only coverage semantics.

- `_step_kernel_with_vm()` reconstructs coverage semantics for compiled
  `match.v2` / `subst.v2`
- the current cutover gate proves equivalence and polarity, but not exact
  `record_no_match` / `record_match` bookkeeping parity
**Why deferred:** The cutover gate tests prove behavioral equivalence (same input → same
output) and polarity (VM path produces same match/subst results as host path). Adding
exact bookkeeping parity tests requires instrumenting the VM to emit coverage events,
which is a new capability in the Stage0 VM. **Target packet:**
`reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.

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

### N5. `pipeline.js` still has no explicit size/shape governance

- **Outcome:** retained live governance advisory.
- **Governing route:** `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
- **Current proof gap:** the completed Phase A packet reproduced that
  `mu/host/js/engine/pipeline.js` remains a 1160-line engine pipeline and that
  scoped docs/tests do not define a sufficient module ownership or
  decomposition contract.
- **Hard stop before implementation:** no JS runtime, Stage0, coverage, Proxy
  provenance, scheduler, seed, or module-split implementation is authorized by
  this source packet or by the completed Phase A governance packet.
- **Doctrine boundary:** future governance must preserve seed-driven boundary
  operations and must not move Mu semantic decisions into JavaScript module
  structure.

- the file remains large (`wc -l` reports 1160 lines)
- there is no explicit cap or decomposition contract comparable to the JS
  bootstrap-core governance gate
**Why deferred:** pipeline.js is the JS engine pipeline — it handles boundary dispatch,
ontology promotion, algorithm routing, and evidence collection. These are logically
related functions that share state (seedProjectionMap, kernelProjections). Splitting
into smaller files would create circular dependency issues or require a module loader.
The file is well-sectioned with clear function boundaries. A LOC cap without
decomposition guidance would be arbitrary. **Target packet:**
`reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`.
