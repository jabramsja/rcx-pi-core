# Phase-A-Canonical-Missing-Packet-Path-Repair-2026-05-22

Date: 2026-05-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: phase-a-canonical-missing-packet-path-repair-2026-05-22
Phase-A-Lock: LOCKED
Purpose: Create and lock a control-plane packet for the Phase A canonical missing-packet path repair. Scope is executor routing/tooling only: TASKS-bound tracker sync notes must be able to route an absent canonical packet into Phase A, and Phase A must create that exact tracked packet instead of minting a dated duplicate. Do not touch JS runtime or Mu semantic runtime files.

## Scope

This Phase A plan covers the control-surface repair authorized by `TASKS.md:429`
for `phase-a-canonical-missing-packet-path-repair-2026-05-22`.

Files and directories in implementation scope:

- Governing packet: `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`.
- Executor routing/tooling implementation surface: `mu/tools/executors/phase_a_executor.py` and `mu/tools/executors/executor_dispatch.py`, limited to canonical tracked-packet propagation and lookup behavior.
- Focused regression surface named by `TASKS.md:429`: `mu/tests/tools/test_phase_a_executor.py` and `mu/tests/tools/test_executor_dispatch.py`, limited to `TestDispatcherFreshnessRefresh`, `TestPhaseATrackedPacketReuse`, and `TestFindTrackedPacket`.
- L4 evidence surface: `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`.
- Tracker authority reference: `TASKS.md:429` only. `TASKS.md` is already the authorizing tracker source for this plan and is not a pending implementation edit unless same-wave L4 validation later proves a detector-visible tracker metadata gap.

## Work Items

Complete or verify the bounded Phase A repair items named by `TASKS.md:429`:

1. Ensure the Phase A surface routing path carries the TASKS-bound `tracked_packet` for tracker sync notes even when the referenced canonical packet does not exist yet.
2. Ensure Phase A draft creation uses the validated `tracked_packet` path as the packet destination instead of creating a dated duplicate packet path.
3. Keep the canonical packet destination exactly `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`.
4. Add or preserve focused regression coverage for both behaviors in the test surfaces named above.
5. Collect the same-wave L4 indicator artifact at `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`.
6. Run the same-wave evidence command and strict L4 staged contract check from `TASKS.md:429`.

If current code truth during the implementation phase proves any item is already landed, treat that item as verified rather than reimplementing it, and keep the remaining work bounded to the unproven gap.

## Constraints

- This is an `L4_ENABLER` control-surface repair, not an L4 structural runtime wave.
- Do not touch JS runtime files.
- Do not touch Mu semantic runtime files.
- Do not touch Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, or Claude-related surfaces.
- Do not broaden into deferred-report cleanup, tracker reorganization, unrelated executor refactors, or broad docs synchronization.
- Do not create a dated duplicate packet for this wave. The canonical packet path is the governing packet path above.
- Do not use stale packet wording as proof that implementation work is still pending; current code truth controls during implementation review.

## Stop Conditions

Stop and return the packet for re-routing if any of the following occurs:

- The repair requires changes outside the explicit file and directory scope above.
- The repair requires JS runtime, Mu semantic runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, or Claude-related edits.
- Phase A cannot validate the TASKS-bound `tracked_packet` without relaxing path validation or allowing arbitrary packet destinations.
- The implementation path would create or require a dated duplicate packet instead of the canonical packet path in this plan.
- Same-wave L4 validation cannot bind the packet, tracker authority, indicator artifact, and staged diff to `phase-a-canonical-missing-packet-path-repair-2026-05-22`.

## Acceptance Criteria

- Phase A routing can carry an absent TASKS-bound `tracked_packet` into the Phase A draft creation path.
- Phase A draft creation creates or reuses exactly `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`, not a suffixed or dated duplicate path.
- Focused regression evidence covers the Phase A routing path, tracked-packet reuse, and tracked-packet discovery behavior.
- The following evidence command passes:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_a_executor.py mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh mu/tests/tools/test_executor_dispatch.py::TestPhaseATrackedPacketReuse mu/tests/tools/test_executor_dispatch.py::TestFindTrackedPacket --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id phase-a-canonical-missing-packet-path-repair-2026-05-22 --wave-class L4_ENABLER
```

- The same-wave indicator artifact is collected with:

```bash
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id phase-a-canonical-missing-packet-path-repair-2026-05-22 --output reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json
```

- No files outside the explicit implementation, regression, governing packet, tracker-authority, or indicator surfaces above are changed for this wave.

## Grounding / Authorization

- TASKS authorization: `TASKS.md:429` authorizes `[NEXT-CODEX-POST-REDTEAM]` for `phase-a-canonical-missing-packet-path-repair-2026-05-22` as `Class: L4_ENABLER`, `target_gate_id: G8`, with packet path `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`.
- Governing packet authority: this file, `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`, is the governing Phase A packet for the same wave id.
- Primary blocker class: `INTEGRATION`.
- Primary invariant: `INV_STRUCTURAL_FORWARD_MOTION`.
- Bootstrap endgame policy: `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`.
- Boot0 track: `V1`; Boot0 progress state: `HOLD`.
- Authorization: standing pipeline-bug-fix authorization for this control-surface `L4_ENABLER` packet repair, mechanically bound to the same wave id.
- `FOUNDER_OVERRIDE:phase-a-canonical-missing-packet-path-repair-2026-05-22`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `phase-a-canonical-missing-packet-path-repair-2026-05-22`
- Active packet: `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`
  - `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `phase-a-canonical-missing-packet-path-repair-2026-05-22`
- Active packet: `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `66fe2fa892fd3272513ef6a60d340c0c75fe7215c41f0ebf703e03748c9bb6b8`
- Indicator artifact: `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_a_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/phase-a-canonical-missing-packet-path-repair-2026-05-22.md`
  - `reports/l4_wave_indicators/phase-a-canonical-missing-packet-path-repair-2026-05-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
