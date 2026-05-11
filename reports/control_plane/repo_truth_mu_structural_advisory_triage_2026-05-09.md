# Repo Truth Mu Structural Advisory Triage

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: repo-truth-mu-structural-advisory-triage-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural non-blocking triage
Source authorization: FOUNDER_OVERRIDE:repo-truth-mu-structural-advisory-triage-2026-05-09
Packet: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

Purpose: route the remaining active deferred non-blocking `/mu` structural
advisories through the dispatcher before any implementation work.
## Scope

- Read and reconcile the active non-blocking packets:
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- Verify each retained item against current code with file:line or command
  evidence.
- Deduplicate overlapping Stage0 capture findings.
- Produce bounded follow-up packet/task routing for any implementation-worthy
  `/mu` structural advisory.
- Archive or update only advisory material proven closed by current code.

- `reports/deferred/non_blocking/repo-truth-mu-structural-advisory-triage-2026-05-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

- Reproduce the active deferred non-blocking `/mu` advisory inventory from
  `reports/deferred/non_blocking/`.
- Reconcile the three active advisory packets listed in Scope against current
  code truth.
- Remove any advisory from pending work items and acceptance criteria when
  current code evidence proves it is already implemented.
- Keep unresolved advisories active with current file:line or command evidence
  and a bounded next-wave routing decision.
- Deduplicate overlapping Stage0 capture findings before generating any
  follow-up packet.
- Emit only dispatcher-first Phase A routing for implementation-worthy `/mu`
  structural work; do not manually implement runtime changes in this triage
  wave.

## Constraints

- Use the dispatcher pipeline: post-merge routing record -> Phase A -> Phase B
  -> commit executor.
- Do not edit Claude-related files.
- Do not hand-implement runtime changes in this triage wave.
- Do not add semantic host debt. Any later `/mu` implementation packet must
  reduce or narrow host bootstrap assumptions and preserve Python/JS parity.
- If implementation is warranted, split into bounded packets instead of merging
  unrelated provenance, Stage0, and governance work.

## Stop Conditions

- Stop before runtime implementation if the next edit would touch Python/JS
  runtime, Stage0, seed, scheduler, registry, parity, or production `/mu` code
  without a locked Phase A implementation packet.
- Stop and route a mechanical fix if dispatcher, builder, recovery, or commit
  automation selects a completed or wrong-wave packet.
- Leave an advisory active if current evidence cannot prove closure.

## Acceptance Criteria

- Active non-blocking inventory is reproduced from the filesystem.
- Each retained advisory has current evidence and a bounded next-wave decision.
- Closed items are archived with provenance and `reports/deferred/non_blocking/README.md`
  remains consistent with the active lane.
- Any generated implementation packet states how it programs in Mu or narrows
  bootstrap debt without adding host-only semantics.

## Grounding / Authorization

- TASKS.md grounding: `TASKS.md:292` contains the detector-visible tracker
  entry for `[NEXT-CODEX-POST-REDTEAM]`, wave
  `repo-truth-mu-structural-advisory-triage-2026-05-09`, Class `L4_ENABLER`,
  and Packet
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization: FOUNDER_OVERRIDE:repo-truth-mu-structural-advisory-triage-2026-05-09
- Governing packet refs:
  - `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- TASKS.md authorizes this dispatcher-first triage wave only. It does not prove
  every listed advisory remains unlanded; current code truth controls closure
  and routing decisions.

## Phase B Implementation Evidence

Execution inventory command:
`find reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' ! -name README.md -print | sort`.

Current active non-blocking `/mu` structural inventory:

1. `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
2. `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
3. `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`

No advisory material was archived in this triage wave. Current code evidence did
not prove any retained advisory closed; each unresolved item remains active with
a bounded routed packet below.

### Reconciled Advisory Decisions

| Source | Retained item | Current evidence | Decision |
| --- | --- | --- | --- |
| `repo_truth_non_blockers_2026-03-14.md` | N1 coverage bookkeeping proof | `_step_kernel_with_vm` still reconstructs coverage in host Python at `mu/host/python/rcx_pi/selfhost/step_mu.py:1035` through `mu/host/python/rcx_pi/selfhost/step_mu.py:1142`. | Route `vm-cutover-coverage-bookkeeping-proof-2026-05-09`. |
| `repo_truth_non_blockers_2026-03-14.md` | N2 JS bridge VM ordering evidence | JS bridge smoke coverage remains at `mu/host/js/tests/self_tests.js:461` through `mu/host/js/tests/self_tests.js:514`; `mu/host/js/engine/kernel.js:23` through `mu/host/js/engine/kernel.js:27` still states JS has no coverage system. | Route `js-bridge-vm-ordering-evidence-2026-05-09`. |
| `repo_truth_non_blockers_2026-03-14.md` | N3 broad host-surface reduction boundary | `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` exits 0 with no increases/decreases; `python3 tools/checks/check_host_authority_inventory_ratchet.py` exits 0 with `312 total` / `217 authority`. | Keep as architectural boundary; no implementation packet. |
| `repo_truth_non_blockers_2026-03-14.md` | N5 JS engine pipeline shape governance | `wc -l mu/host/js/engine/pipeline.js` reports `1160`; no decomposition contract is present in the active packet. | Route `js-engine-pipeline-shape-governance-2026-05-09`. |
| `repo_truth_non_blockers_2026-03-14.md` N14 and `redteam_2026-03-14_repo_non_blockers.md` N1 | Stage0 capture path provenance boundary | Python stores `captures[name] = val` at `mu/host/python/rcx_pi/selfhost/stage0_vm.py:796` through `mu/host/python/rcx_pi/selfhost/stage0_vm.py:807`; JS stores `captures[name] = val` at `mu/host/js/core/stage0_vm.js:831` through `mu/host/js/core/stage0_vm.js:841`; materialization deep-copies at Python `:374` through `:383` and JS `:369` through `:380`. Direct repro exits 0 with Python `match / NoneType / False / None` and JS `match / false / true / null`. | Deduplicate to canonical Stage0 packet `stage0-capture-path-provenance-boundary-2026-05-09`. |
| `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md` | Transparent JavaScript Proxy boundary | `mu/host/js/core/types.js:116` through `mu/host/js/core/types.js:158` and `:176` through `:220` rely on fail-closed host reflection; direct `node` probe exits 0 with `plainValid:true`, `proxyValid:true`, and a successful `proxyHash`. | Route `transparent-js-proxy-provenance-boundary-2026-05-09` for a Phase A policy/architecture decision before any host-oracle work. |

### Follow-Up Routing Emitted

The following control-plane packets are routed as dispatcher-first Phase A work.
They do not authorize hand implementation from this triage wave:

1. `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
2. `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
3. `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
4. `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
5. `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`

Each generated packet states the required Phase A boundary and how any later
implementation must either program in Mu, narrow bootstrap debt, or preserve a
structural proof boundary without adding host-only semantics.

## Validation Used

- `find reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' ! -name README.md -print | sort` exited 0 and listed the three active source packets above.
- Stage0 direct Python and JS repro commands exited 0 with the outputs recorded
  in the table above.
- Transparent Proxy direct JS probe exited 0 with `proxyValid:true` and a
  successful cached hash, proving the boundary remains policy-bound rather than
  code-closed.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` exited 0.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` exited 0.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `repo-truth-mu-structural-advisory-triage-2026-05-09`
- Active packet: `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/repo-truth-mu-structural-advisory-triage-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: the artifact above is the only tracker-binding indicator for
  this wave. The transparent Proxy indicator listed in the historical staged-file
  snapshot below was an adjacent routed follow-up artifact generated in the same
  package, not a second tracker-binding indicator for this triage wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
  - `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  - `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
  - `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
  - `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  - `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/repo-truth-mu-structural-advisory-triage-2026-05-09_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/repo-truth-mu-structural-advisory-triage-2026-05-09.json`
  - `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json` (adjacent routed follow-up artifact; not tracker-binding for this wave)
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `repo-truth-mu-structural-advisory-triage-2026-05-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/repo-truth-mu-structural-advisory-triage-2026-05-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `repo-truth-mu-structural-advisory-triage-2026-05-09`
- Active packet: `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c06453bb691f52201dfc303c99a6272c45003a9157e1a9eeb24051608e2c3bfb`
- Indicator artifact: `reports/l4_wave_indicators/repo-truth-mu-structural-advisory-triage-2026-05-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/repo-truth-mu-structural-advisory-triage-2026-05-09.json`
- Scope note: `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json`
  in the historical staged-file snapshot below is an adjacent routed follow-up
  artifact; the evidence handle above remains the only tracker-binding indicator
  for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`
  - `reports/control_plane/js_engine_pipeline_shape_governance_2026-05-09.md`
  - `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`
  - `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`
  - `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
  - `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/repo-truth-mu-structural-advisory-triage-2026-05-09_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/repo-truth-mu-structural-advisory-triage-2026-05-09.json`
  - `reports/l4_wave_indicators/transparent-js-proxy-provenance-boundary-2026-05-09.json` (adjacent routed follow-up artifact; not tracker-binding for this wave)
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
