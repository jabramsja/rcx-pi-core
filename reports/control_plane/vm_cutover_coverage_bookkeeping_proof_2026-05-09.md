# VM Cutover Coverage Bookkeeping Proof

Date: 2026-05-10
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: vm-cutover-coverage-bookkeeping-proof-2026-05-09
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: /mu structural evidence
Source authorization: routed-by-repo-truth-mu-structural-advisory-triage-2026-05-09
Routing source: reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md

## Scope

- Reproduce the `repo_truth_non_blockers_2026-03-14.md` N1 claim that Python
  VM cutover coverage bookkeeping is reconstructed in host code rather than
  directly locked by VM-emitted evidence.
- Read-only evidence surfaces:
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `mu/host/python/rcx_pi/selfhost/step_mu.py`
  - existing coverage tests under `mu/tests/`
- Phase A may propose a later bounded implementation packet only after proving
  the exact bookkeeping gap still reproduces.

- `reports/deferred/non_blocking/vm-cutover-coverage-bookkeeping-proof-2026-05-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Reproduce the coverage-path evidence at `_step_kernel_with_vm`.
2. Decide whether the correct next action is focused proof coverage, Stage0 VM
   attempt/match event materialization, or no-op closure by existing tests.
3. If implementation is needed, define a later Phase B scope that narrows host
   coverage reconstruction by deriving bookkeeping from Stage0 VM structural
   program attempts or a parity-preserving VM result trace.

## Constraints

- Do not edit runtime, Stage0, coverage, seed, scheduler, registry, parity, or
  production `/mu` code in Phase A.
- Do not add host-only bookkeeping semantics. Any later implementation must
  reduce or bound the existing host reconstruction assumption.
- Preserve Python/JS parity claims. JS has no coverage system, so a Python
  coverage proof must not imply JS behavior that does not exist.
- Do not edit Claude-related files.

## Stop Conditions

- Stop if current tests already prove exact `record_no_match` / `record_match`
  parity.
- Stop if the only possible fix would add host-only coverage semantics instead
  of deriving proof from Mu/Stage0 execution structure.
- Stop if implementation would need broader Stage0 or runtime changes before a
  locked Phase A packet exists.

## Acceptance Criteria

- Phase A records current file:line and command evidence for the coverage gap.
- Any later implementation packet states how it programs in Mu or narrows the
  bootstrap coverage reconstruction boundary without adding host-only semantics.
- No runtime implementation occurs before Phase A is reviewed and locked.

## Grounding / Authorization

- TASKS.md authorization:
  `TASKS.md:508` routes `[NEXT-CODEX-POST-REDTEAM]` to this packet as
  `vm-cutover-coverage-bookkeeping-proof-2026-05-09`, class `L4_ENABLER`,
  category `/mu` structural evidence, and states that the packet is Phase
  A-only with no runtime or Stage0 edit authorization.
- Same-wave override:
  `FOUNDER_OVERRIDE:vm-cutover-coverage-bookkeeping-proof-2026-05-09`.
- Source advisory:
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md` N1.
- Routing triage:
  `reports/control_plane/repo_truth_mu_structural_advisory_triage_2026-05-09.md`.
- Authorization:
  repo-truth-mu-structural-advisory-triage-2026-05-09 routing packet plus
  the TASKS.md same-wave override above.

## Phase A Evidence Record (2026-05-10)

### Commands

- `codex-rcx-preflight parity`
  - Result: exit 0.
  - Relevant startup evidence: staged L4 contract skipped because there are no
    staged files; host semantics ratchet passed with no increases/decreases;
    host authority inventory ratchet passed at `312 total` / `217 authority`;
    docs consistency passed; `mu/tests/l4_gates/test_stage0_vm_cutover.py`
    passed `39 passed`; JS `eval_step.js` passed; JS debt check passed.
- `nl -ba reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md | sed -n '20,75p'`
  - Result: exit 0.
  - Evidence: lines 26-30 route N1 to this packet because
    `_step_kernel_with_vm` reconstructs coverage events in host code; lines
    62-72 state that existing cutover gates prove equivalence and polarity, but
    not exact `record_no_match` / `record_match` bookkeeping parity.
- `nl -ba mu/host/python/rcx_pi/selfhost/step_mu.py | sed -n '1035,1142p'`
  - Result: exit 0.
  - Evidence: `_step_kernel_with_vm` imports coverage at line 1067, enables
    coverage from host state at line 1070, calls the Stage0 VM per bundle at
    lines 1076, 1093, 1109, and 1127, and then emits coverage bookkeeping by
    walking host-side `program_order` at lines 1080-1084, 1087-1089,
    1097-1101, 1104-1106, 1113-1118, 1121-1124, 1131-1135, and 1138-1140.
- `nl -ba mu/host/python/rcx_pi/selfhost/stage0_vm.py | sed -n '700,729p;820,864p'`
  - Result: exit 0.
  - Evidence: Stage0 iterates `bundle["program_order"]` at lines 708 and
    713-721, but the match and stall result payloads return only `status`,
    `matched_program_id`, `root`, and aggregate metrics at lines 820-828 and
    857-864.
    It does not emit the ordered attempted program IDs or no-match events that
    Python coverage records.
- `nl -ba mu/host/js/core/stage0_vm.js | sed -n '734,758p;840,893p'`
  - Result: exit 0.
  - Evidence: JS Stage0 has the same aggregate-attempt shape: it iterates
    `bundle.program_order` at lines 740 and 745-753, and its match and stall
    result payloads return only `status`, `matched_program_id`, `root`, and
    aggregate metrics at lines 855-860 and 887-892.
- `rg -n "record_no_match|record_match|projection_coverage|coverage\\." mu/tests`
  - Result: exit 0.
  - Evidence: test references are limited to pytest coverage enable/report
    plumbing, one cutover call with `record_coverage=False`, and generic
    "coverage" wording. No existing test asserts exact `coverage.record_no_match`
    or `coverage.record_match` parity for the VM cutover path.
- `nl -ba mu/tests/l4_gates/test_stage0_vm_cutover.py | sed -n '1,230p;318,345p'`
  - Result: exit 0.
  - Evidence: the direct VM/host equivalence helper calls
    `_step_kernel_with_vm(..., record_coverage=False)` at line 121, while the
    cutover comparison at lines 323-341 asserts output equality only.
- `nl -ba mu/tests/l4_gates/test_stage0_vm.py | sed -n '724,744p;1120,1130p'`
  - Result: exit 0.
  - Evidence: Stage0 tests lock first-match-wins and stall status at lines
    727-743, and only assert aggregate metric lower bounds at lines 1123-1129.
    They do not prove an exact attempted-program trace.

### Reproduction Result

The N1 claim still reproduces. The live cutover path executes Stage0 VM bundles,
but coverage bookkeeping is still reconstructed by host Python after each VM
result:

- Match path: `_step_kernel_with_vm` receives `matched_program_id`, then walks
  the corresponding host-side bundle `program_order` until that ID to emit
  `coverage.record_no_match(...)`, followed by
  `coverage.record_match(...)`.
- Stall path: `_step_kernel_with_vm` treats a VM stall as proof that every
  program in the corresponding host-side bundle order was tried, then emits
  `coverage.record_no_match(...)` for each program.
- Stage0 result shape gives enough aggregate evidence to know a match or stall
  occurred, but it does not directly emit the ordered attempted program IDs or
  no-match/match events used by Python coverage.

### Decision

Current tests do not satisfy the stop condition for exact
`record_no_match` / `record_match` parity. A no-op closure would overstate the
proof class: existing tests prove VM execution, output equivalence, polarity,
first-match-wins, stall status, trusted/public Stage0 parity, and aggregate
attempt metrics, but not exact coverage bookkeeping composition.

The correct later implementation direction is Stage0 VM attempt/match event
materialization, or an equivalent parity-preserving VM result trace. Focused
Python-only coverage assertions against the current reconstruction would lock
the host assumption instead of reducing it.

### Later Phase B Packet Boundary

A later implementation packet should narrow the bootstrap coverage
reconstruction boundary without adding host-only bookkeeping semantics:

- Extend the Stage0 VM result contract in both Python and JS with a structural,
  substrate-neutral trace such as ordered attempted program IDs plus final
  match/stall status, or an equivalent event list.
- Add Python/JS parity tests for the new Stage0 trace shape. JS still has no
  coverage system, so the parity claim must be about VM structural trace output,
  not JS coverage behavior.
- Update Python `_step_kernel_with_vm` coverage emission to derive
  `record_no_match` / `record_match` from the VM-emitted trace rather than
  reconstructing attempts solely from host-side bundle order.
- Add Python coverage tests that assert the VM-derived trace produces the same
  `record_no_match` / `record_match` composition as the legacy trusted host path.

No runtime, Stage0, coverage, seed, scheduler, registry, parity, production
`/mu`, or Claude-related files were changed in this Phase A evidence packet.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `vm-cutover-coverage-bookkeeping-proof-2026-05-09`
- Active packet: `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
  - `reports/deferred/non_blocking/vm-cutover-coverage-bookkeeping-proof-2026-05-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `vm-cutover-coverage-bookkeeping-proof-2026-05-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/vm-cutover-coverage-bookkeeping-proof-2026-05-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `vm-cutover-coverage-bookkeeping-proof-2026-05-09`
- Active packet: `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0af4593af39e2e386ce49079074fc3612337f9fad401b782e44b688875a8c098`
- Indicator artifact: `reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id vm-cutover-coverage-bookkeeping-proof-2026-05-09 --output reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`
  - `reports/deferred/non_blocking/vm-cutover-coverage-bookkeeping-proof-2026-05-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/vm-cutover-coverage-bookkeeping-proof-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
