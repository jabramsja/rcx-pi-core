# PR 1219 P0IBRRCP Normal-Root Recorded-Child Cleanup R4

Date: 2026-09-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP]
Wave ID: pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 86c2177b8f335fafc10943a247e3db9e4784daa3a4d4fd458d21f78d4b7556bb
Purpose: Land only the reproduced normal-root cleanup blocker from exact PR 1255 merge authority: before returning after a normal bridge-root exit, terminate and reap child PIDs already recorded by the current or immediately prior authoritative progress snapshot.

## Scope

From exact PR 1255 merge, repair only normal bridge-root return for child PIDs already captured by authoritative progress snapshots, prove it with one synchronized regression, and advance TASKS to PBNOGO reconstruction.

Files and surfaces in scope:

- mu/tools/executors/phase_b_executor.py (MODIFY) -- preserve current and prior authoritative child snapshots and terminate/reap their union before returning on normal root exit.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- add or refine one deterministic synchronized real-process regression proving a recorded detached child cannot survive successful normal return.
- TASKS.md (MODIFY) -- record PR 1255 as landed, make this row CURRENT/LANDED as appropriate, preserve every queue/TODO/stopped-attempt item, and leave PBNOGO reconstruction NEXT after merge.
- reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md (GENERATED) -- sole launcher-owned canonical packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct fresh only from exact merge 922081269684f74404ba2c405ddab57c5af4f4eb. Preserve every stopped normal-root candidate, branch, bus, packet, source, and target unchanged as noncomplete evidence.
2. Retain the prior authoritative child PID tuple until root status is known; capture the current snapshot without erasing previously recorded ownership.
3. On normal root exit, invoke the existing bounded termination/reaping helper on the sorted union of current and prior recorded child PIDs before reading logs and returning the original exit code and output.
4. After a nonterminal poll, advance prior snapshot authority and preserve existing heartbeat, timeout, stale-progress, exception, output, and recovery behavior.
5. Add a synchronized regression that observes the detached child before allowing the parent to exit and proves the child is dead when the helper returns successfully, with a test-only final cleanup safety net.
6. Update narrow TASKS truth, run exact evidence, and complete normal dispatch, Codex review, providerless commit, CI, merge, and postmerge cleanup.

## Constraints

- Do not modify bridge adapters/supervisors, dispatcher, launcher, recovery, checkpoint semantics, terminal transport, receipts, role/provider configuration, runtime, substrate, seed, host semantics, Mu semantics, or unrelated docs.
- Do not absorb pre-first-snapshot ownership, on_started failure behavior, PID reuse, cancellation, generic exceptional cleanup, in-flight implementer ownership, or full P0T3 process-tree closure.
- Do not edit Claude-owned files or use provider-local memory as evidence. Every model-bearing role is Codex gpt-5.6-sol ultra and commit execution remains providerless.
- Use launch_wave.py with immutable clean source/target worktrees. No hand-authored packet, manual candidate patching, staging, commit, push, PR, merge, or stopped-lane folding.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from 922081269684f74404ba2c405ddab57c5af4f4eb; if a launch worktree is dirty; if identity collides; or if Codex/providerless authority is unavailable.
- Stop and preserve only if the reproduced normal-return blocker requires a functional path outside the allowlist; create a smaller fresh launch_wave.py prerequisite instead of widening in place.
- Do not stop or widen for pre-first-snapshot cases, PID reuse, documentation polish, or any nonblocking finding.
- If bounded review does not converge, preserve the lane and split only the reproduced blocker into fresh narrower builder-launched packets.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Only allowlisted paths change, with exactly one launcher-owned canonical packet and no packet alias or hand-authored packet.
- Launch metadata proves exact base 922081269684f74404ba2c405ddab57c5af4f4eb, implementer/reviewer/pager Codex, and providerless commit execution.
- A detached child recorded by the current or immediately prior authoritative snapshot is terminated and reaped before normal root return while root exit code and output remain unchanged.
- The deterministic synchronized real-process regression reproduces the former leak and proves cleanup without broadening process ownership.
- Focused Phase B tests, staged L4 enforcement, pre-push-fast, and required CI pass.
- TASKS preserves all queue/TODO/stopped evidence, records PR 1255 accurately, lands this row, and leaves PBNOGO reconstruction NEXT.
- Fresh review clearance, normal merge, and terminal postmerge cleanup complete.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP]; wave id `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`.
- TASKS.md authority: the 2026-09-01 tracker sync note for wave `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b9d20e5a221ed72d8dfec37bc6bc9e1749d039de2b3a23325337fb1e46f67c1b`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md. (2) Final pytest gate covered 8 pytest selector(s) across 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
