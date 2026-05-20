# N3-Kernel-Driver-Mu-Fuel-Runtime-Authority-Reduction-2026-05-20

Date: 2026-05-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Purpose: Close the remaining Python parity gap in kernel-driver Mu-fuel runtime authority after the JS fuel handoffs already recorded in `TASKS.md:393-396`. This wave does not relist the structural fuel source lock, JS fuel-threading prerequisite/proof, or JS Mu-fuel production integration as unresolved future work.

## Scope

Implemented Phase B scope:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`: add explicit `kernel_fuel` support to `step_kernel_mu` so Mu linked-list fuel can terminate execution before the numeric `max_steps` watchdog, matching the JS `kernelFuel` contract.
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`: add Python fuel authority tests and update the Python/JS shared fuel-exhaustion assertion so both substrates now report `fuel_exhausted` for the same fuel-backed execution budget.
- `mu/tests/parity/test_exhaustion_parity.py`: update the D006 parity proof so Python also receives supplied Mu fuel, reports `fuel_exhausted`, and rejects malformed tail fuel like JS.
- `mu/tools/executors/commit_executor.py`: repair standalone routing-record regeneration so a staged same-wave control-plane packet supplies the wave class/tracked packet when the routing record lacks `tracked_packet`.
- `mu/tests/tools/test_commit_executor_receipt.py`: lock that builder repair with a regression that stages a same-wave L4_STRUCTURAL packet and runtime file without an explicit `tracked_packet` candidate.
- `TASKS.md`, this packet, and `reports/l4_wave_indicators/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20.json`: bind the runtime/test change to detector-visible L4 authority and indicator evidence.

Recorded predecessor handoffs that this successor packet must sequence after:

- `TASKS.md:393`: `n3-kernel-driver-structural-fuel-source-lock-2026-05-20` is already recorded as a Phase B handoff.
- `TASKS.md:394`: `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20` is already recorded as a Phase B handoff.
- `TASKS.md:395`: `n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20` is already recorded as a Phase B handoff with focused `mu/tests/parity/test_exhaustion_parity.py -k d006` proof.
- `TASKS.md:396`: `n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20` is already recorded as an L4_STRUCTURAL commit-ready Phase B handoff over `mu/host/js/api/json_handlers.js`, `mu/host/js/engine/kernel.js`, `mu/tests/l4_gates/test_kernel_run_result_contract.py`, `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`, and `mu/tests/parity/test_exhaustion_parity.py`.

Future Phase B evidence/reconciliation scope, only after a detector-visible same-wave `TASKS.md` tracker entry exists and the recorded handoffs above are treated as predecessor baseline:

- `mu/host/js/engine/kernel.js` and `mu/host/js/api/json_handlers.js`: verify or repair only a residual JS authority regression not already covered by `TASKS.md:396`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py`: verify or repair only a remaining Python parity/authority gap not already closed by current code.
- `mu/tests/l4_gates/test_kernel_run_result_contract.py`, `mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`, and `mu/tests/parity/test_exhaustion_parity.py`: reuse or extend only for residual gaps not already proven by `TASKS.md:395-396`.
- Existing host-semantics and host-authority ratchet checks may be used as evidence surfaces; edit them only if a detector gap is directly reproduced.

## Work Items

Completed bounded tasks for this Phase B wave:

1. Recorded the current authorization truth in `TASKS.md` before commit packaging.
2. Reconciled `TASKS.md:393-396` as completed predecessor handoffs and did not reopen JS source-lock, JS fuel-threading prerequisite/proof, or JS production integration.
3. Closed the residual Python parity gap by adding optional `kernel_fuel` to `step_kernel_mu`.
4. Preserved `max_steps` as a numeric watchdog while allowing Mu fuel to own production exhaustion when supplied.
5. Extended the existing KernelRunResult L4 gate instead of adding duplicate D006/JS proof.
6. Repaired the D006 parity helper so Python no longer uses numeric `max_steps` as a fuel proxy.
7. Repaired the commit-executor builder failure reproduced during this wave: standalone routing-record reruns over a staged same-wave packet no longer default to MAINTENANCE when `tracked_packet` is absent from the routing record.
8. Captured focused gate, parity, host-semantics ratchet, host-authority inventory, and builder-regression evidence.

## Constraints

- Do not treat predecessor handoffs as current-wave implementation authority; this wave has its own detector-visible `TASKS.md` tracker note.
- Do not cite `TASKS.md:393-396` predecessor handoffs as current-wave implementation authority; they are predecessor baseline only.
- Do not treat the `TASKS.md:393-396` predecessor handoffs as missing or unresolved.
- Do not reopen JS fuel source lock, JS fuel-threading prerequisite/proof, or JS production integration unless current code evidence reproduces a specific residual defect not covered by those handoffs.
- Do not create new Mu fuel program/seed work merely because old packet wording described source definition as future work.
- Do not make Python or JavaScript smarter as a shortcut for missing Mu semantics.
- Do not merely rename markers, adjust comments, or weaken tests to satisfy ratchets.
- Do not broaden into Stage0, scheduler, seed registry, coverage bookkeeping, JS pipeline decomposition, docs cleanup, or Claude-related surfaces.
- Commit automation scope is limited to the reproduced same-wave builder misclassification that blocked this packet from re-entering the commit pipeline.
- Preserve Python/JavaScript parity; do not land a one-substrate authority model.
- Keep `max_steps` only as boundary compatibility or watchdog if it remains necessary.

## Design Trade-Offs

- Preferred direction: treat this packet as a successor/reconciliation wave, because the current TASKS evidence already records multiple N3 fuel handoffs.
- Authorization correction: the predecessor handoffs prove baseline sequencing, while `TASKS.md:579-587` plus the parent queue prove only bounded packetization until the exact same-wave tracker entry exists.
- Allowed implementation role: close only residual, reproduced authority gaps after same-wave tracker grounding and predecessor mapping. A no-op closeout is valid if current code and predecessor evidence already prove the authority move.
- Allowed host role: a host loop may remain as mechanical boundary plumbing or a hard watchdog, but it must not decide normal production continuation when Mu fuel is available.
- Rejected shortcut: relisting completed handoffs as pending would duplicate landed or commit-ready work and hide the real remaining proof question.
- Rejected authorization shortcut: treating the same-wave control-plane packet path or `FOUNDER_OVERRIDE` line alone as detector-visible `TASKS.md` grounding would violate the parent queue requirement.
- Testing risk: ordinary output equivalence is insufficient for any residual authority claim; gates must fail for the specific residual gap they are meant to prove.

## Stop Conditions

- Stop before widening beyond Python kernel-fuel parity; JS production integration remains predecessor baseline from `TASKS.md:396`.
- Stop if the proposed work item restates `TASKS.md:393-396` predecessor handoffs as unresolved pending work.
- Stop if the work requires broader ABI, Stage0, scheduler, seed-registry, coverage, or pipeline changes not named in this packet.
- Stop if the proposed implementation leaves host `max_steps` as the semantic execution driver.
- Stop if parity cannot be preserved in both Python and JavaScript within this bounded successor wave.

## Acceptance Criteria

Implemented acceptance:

- A detector-visible `TASKS.md` tracker entry exists for `n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20` under `[NEXT-CODEX-POST-REDTEAM]`.
- This packet sequences after `TASKS.md:393-396` and does not relist those handoffs as future unresolved work.
- Pending work excludes already-recorded source-lock, JS fuel-threading prerequisite/proof, and JS production integration slices.
- Python and JavaScript both expose fuel-backed kernel execution metadata where supplied fuel can produce `fuel_exhausted`.
- The focused L4 gate fails if Python falls back to numeric `max_steps` for a supplied Mu fuel budget.
- The focused parity gate fails if Python accepts malformed tail fuel that JS rejects.
- Standalone commit-executor reruns discover a staged same-wave L4_STRUCTURAL packet when the routing record lacks `tracked_packet`, so the generated handoff/tracker note cannot silently fall back to MAINTENANCE for a runtime diff.
- Host-semantics ratchet and host-authority inventory evidence are captured for closeout.

## Grounding / Authorization

- `TASKS.md:579-582` records `[NEXT-CODEX-POST-REDTEAM]` as unparked, founder-authorized, open, and still requiring separate bounded packets for remaining structural reduction.
- `TASKS.md:587` records the active founder-ordered queue directive that every wave requires a control-plane packet plus a `TASKS.md` tracker entry.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113` requires a separate bounded control-plane packet and a detector-visible `TASKS.md` tracker entry before any new structural reduction beyond the listed queue state; it authorizes packetization only and not direct unpacketed `/mu` implementation.
- Current-wave tracker authority: `TASKS.md` contains `n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20` with L4 structural runtime/test evidence.
- `TASKS.md:393` records the predecessor `n3-kernel-driver-structural-fuel-source-lock-2026-05-20` Phase B handoff under `[NEXT-CODEX-POST-REDTEAM]`.
- `TASKS.md:394` records the predecessor `n3-kernel-driver-js-fuel-threading-parity-prereq-2026-05-20` Phase B handoff under `[NEXT-CODEX-POST-REDTEAM]`.
- `TASKS.md:395` records the predecessor `n3-kernel-driver-js-fuel-threading-parity-proof-2026-05-20` Phase B handoff and focused D006 parity proof under `[NEXT-CODEX-POST-REDTEAM]`.
- `TASKS.md:396` records the predecessor `n3-js-kernel-driver-mu-fuel-production-integration-2026-05-20` L4_STRUCTURAL commit-ready Phase B handoff under `[NEXT-CODEX-POST-REDTEAM]`.
- Parent governing queue packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- Same-wave governing packet for this Phase A plan: `reports/control_plane/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20_2026-05-20.md`.
- FOUNDER_OVERRIDE:n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20

## Validation Evidence

- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20 --wave-class L4_STRUCTURAL` -> L4_STRUCTURAL compliant.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_kernel_run_result_contract.py --tb=short` -> `26 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_exhaustion_parity.py -k d006 --tb=short` -> `20 passed, 17 deselected`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_prepare_handoff_from_routing_record_standalone_discovers_staged_same_wave_packet --tb=short` -> `1 passed`.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` -> passed with Python `host_iteration=1` and JS `host_iteration=1`; no increases.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` -> passed with no unaccepted new total-inventory or authority-subset sites.
- `node mu/host/js/eval_step.js` -> all embedded JS substrate/parity tests passed.
- `./tools/checks/check_js_debt.sh` -> passed with JS debt marker truth unchanged.
- `./tools/checks/linters/contraband_js.sh`, `./tools/checks/linters/ast_police_js.sh`, and `./tools/checks/linters/seed_police.sh` -> passed.
- `./tools/checks/check_docs_consistency.sh` and `git diff --check` -> passed.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20`
- Active packet: `reports/control_plane/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20_2026-05-20.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tests/l4_gates/test_kernel_run_result_contract.py`
  - `mu/tests/parity/test_exhaustion_parity.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `reports/control_plane/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20_2026-05-20.md`
  - `reports/l4_wave_indicators/n3-kernel-driver-mu-fuel-runtime-authority-reduction-2026-05-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
