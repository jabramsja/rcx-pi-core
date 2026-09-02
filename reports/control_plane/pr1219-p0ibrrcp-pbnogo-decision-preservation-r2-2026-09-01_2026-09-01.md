# PR 1219 P0IBRRCP PBNOGO Decision Preservation R2

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PBNOGO-INTEGRATION]
Wave ID: pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 61c6919779937178eccaa06a81d1c6c848cd840ae3e2a80eaf868f5a189dd2e9
Purpose: Land only the reproduced Phase B decision-erasure blocker from exact PR 1256 merge authority: REQUEST_CHANGES and NO_GO must remain non-GO even when every finding is explicitly nonblocking; only GO may defer nonblocking findings and converge.

## Scope

From exact PR 1256 merge, bind nonblocking deferral to an actual GO decision at the three existing Phase B convergence sites, prove negative and positive controls, and advance TASKS to auto-defer timeout R3.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- require decision GO before syncing/defering nonblocking findings or declaring GO-equivalent convergence in the bridge-fix helper, ordinary bridge loop, and re-entry bridge loop.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- replace the false-green REQUEST_CHANGES expectation and prove REQUEST_CHANGES, NO_GO, and GO behavior at all three convergence sites.
- TASKS.md (MODIFY) -- record PR 1256 as landed, make the existing PBNOGO row CURRENT/LANDED as appropriate without duplication, preserve every queue/TODO/stopped item, and leave auto-defer timeout R3 NEXT.
- reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md (GENERATED) -- sole launcher-owned canonical packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct fresh only from exact merge 0a4c24120141723d70e6dd1c476ffaa70b1ff9ca. Preserve stopped PBNOGO R1 and auto-defer R1/R2 worktrees, branches, buses, packets, candidates, and reviews unchanged as noncomplete evidence.
2. Use one small shared decision predicate or equivalent minimal condition so only bridge_decision == GO authorizes deferred-nonblocking sync and GO-equivalent convergence at all three existing sites.
3. For REQUEST_CHANGES and NO_GO, do not add that round's findings to all_non_blocking and do not create/update a deferred packet; preserve full parsed/raw context for the existing bounded correction path and retain round/repeat caps.
4. Preserve existing GO behavior: explicitly nonblocking findings may be recorded and converge; GO with blocking findings remains nonconverged.
5. Preserve terminal QUESTION, malformed/unrecognized decisions, nonzero bridge exits, provider parsing, receipts, pager events, recovery, and commit behavior.
6. Update narrow TASKS truth, run focused evidence, and complete normal dispatch, Codex review, providerless commit, CI, merge, and postmerge cleanup.

## Constraints

- Do not change finding classification, severity/disposition semantics, provider envelopes, bridge adapters, commit executor, recovery, dispatcher, launcher, role/model configuration, runtime, substrate, seed, host semantics, Mu semantics, or unrelated docs.
- Do not absorb auto-defer persistence/timeout behavior, resolver repair, crash atomicity, exactly-once behavior, QUESTION journaling, process-tree closure, recovery-timeout containment, provider-terminal, root-exit, or another queued obligation.
- Do not edit Claude-owned files or use provider-local memory as evidence. Every model-bearing role is Codex gpt-5.6-sol ultra and commit execution remains providerless.
- Use launch_wave.py with immutable clean source/target worktrees. No hand-authored packet, manual candidate patching, staging, commit, push, PR mutation, merge, or stopped-lane folding.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from 0a4c24120141723d70e6dd1c476ffaa70b1ff9ca; if a launch worktree is dirty; if identity collides; or if Codex/providerless authority is unavailable.
- Stop and preserve only if decision preservation requires a functional or test path outside phase_b_executor.py and test_phase_b_executor.py; create a smaller fresh launch_wave.py prerequisite instead of widening.
- Do not stop or widen for auto-defer persistence details, documentation polish, pagination, provenance hardening, or another nonblocking/non-occurring edge case.
- If the same decision-authority blocker repeats after one focused correction or bounded review stops converging, preserve the lane and split only the active blocker into fresh narrower builder-launched packets.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Only allowlisted paths change, with exactly one launcher-owned canonical packet and no packet alias or hand-authored packet.
- Launch metadata proves exact base 0a4c24120141723d70e6dd1c476ffaa70b1ff9ca, implementer/reviewer/pager Codex, and providerless commit execution.
- REQUEST_CHANGES and NO_GO with explicitly nonblocking findings remain nonconverged at all three sites, do not write that round to deferred state, and enter the existing bounded implementer path.
- GO with the same findings retains deferred-state creation and convergence; GO with blocking findings, QUESTION, malformed decisions, infrastructure exits, and caps remain unchanged.
- Focused regressions replace the false-green negative control and cover all three mirrors; staged L4 enforcement, pre-push-fast, and required CI pass.
- TASKS preserves all queue/TODO/stopped evidence, records PR 1256 accurately, lands PBNOGO, and leaves auto-defer timeout R3 NEXT.
- Fresh review clearance, normal merge, and terminal postmerge cleanup complete.

## Grounding / Authorization

- Task: [PBNOGO-INTEGRATION]; wave id `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f0b8b4b298ad3b5a41f60cc161fea4a7f8dbffa56693efc179142ffadc2aee93`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-pbnogo-decision-preservation-r2-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
