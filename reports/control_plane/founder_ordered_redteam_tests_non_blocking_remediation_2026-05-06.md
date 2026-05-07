# Founder Ordered Redteam Tests Non-Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: tests
Severity: NON-BLOCKING
Source audit packet: `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`
Queue order: non-`/mu` non-blocking remediation, after docs non-blocking
remediation and before tooling non-blocking remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06
Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This locked packet governed the same-wave Phase B implementation of the
non-blocking tests follow-up from the founder ordered redteam audit output and
now records local evidence.

## Scope: Files/Directories In Scope

Writable implementation scope is limited to this explicit inventory:

- `mu/tests/tools/test_agent_tooling_smoke.py` - N1 fail-closed smoke-test
  remediation for listed required agent tooling scripts, or an explicit split
  between required and optional tooling.
- `mu/tests/l4_gates/test_meta_circular_evidence_gate.py` - N2 proof wording
  and source-lock test restructuring so fallback-helper coverage is not
  described as the current production path.
- `TASKS.md` - only the `[NEXT-CODEX-POST-REDTEAM]` entry for
  `[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION]`, with
  implementation status, focused evidence, and same-wave authority.
- `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
  - this governing packet, for status/evidence refresh only.
- `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
  - only if L4 indicator collection or commit automation requires the
  same-wave indicator artifact.

Read-only grounding and validation scope is limited to:

- `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`
  - source finding evidence.
- `mu/tests/l4_gates/test_stage0_vm_cutover.py` - behavioral production-path
  negative-control evidence for the Stage0 VM cutover path.
- `mu/host/python/rcx_pi/selfhost/step_mu.py` - read-only production cutover
  context cited by the source audit; no runtime edits are authorized here.

No directory-wide edits are authorized by this packet. Any path not listed
above is out of scope.

## Work Items

1. Resolve N1 in `mu/tests/tools/test_agent_tooling_smoke.py`: listed required
   core tooling script disappearance must fail the smoke check instead of
   converting the check into `pytest.skip(...)`. If any listed tool is
   intentionally optional, split it into an explicitly named optional set so
   only optional tools may skip.
2. Resolve N2 in `mu/tests/l4_gates/test_meta_circular_evidence_gate.py`:
   keep any useful source-lock coverage for `_apply_projection_trusted`, but
   reword or restructure the assertion so it is described as fallback-helper
   or compatibility coverage, not the sole/current production path.
3. Preserve the behavioral Stage0 VM cutover proof in
   `mu/tests/l4_gates/test_stage0_vm_cutover.py`: production-path evidence must
   remain behavioral and must continue to distinguish the cutover
   `step_kernel_mu` path from `_apply_projection_trusted` fallback coverage.
4. Refresh the `[NEXT-CODEX-POST-REDTEAM]` tracker entry in `TASKS.md` for
   `[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION]` with final
   implementation status, focused evidence, this packet path, this wave ID,
   category `tests`, severity `non-blocking`, and the same-wave founder
   override.
5. Refresh this packet with final evidence/status if implementation lands in
   the same wave. Do not relist already landed engine-state/scheduler seed,
   fixture, structural-test, scheduler-parity, or seed-registration work as
   unresolved.

## Constraints

- No runtime, substrate, seed, registry, scheduler, or production Stage0
  implementation edits are in scope. In particular, no writes are authorized to
  `mu/host/python/rcx_pi/selfhost/step_mu.py`; it is read-only grounding.
- No `/mu` structural remediation is in scope beyond the two listed
  `mu/tests/...` test files.
- No docs, tooling, CI, workflow, executor, hook, or audit-tooling remediation
  is in scope.
- No Claude-related file edits are in scope, including `CLAUDE.md`,
  `.claude/**`, and `~/.claude/**`.
- No new control-plane packet, deferred report, archive entry, or broad report
  index rewrite is in scope.
- No broad repo investigation, unrelated dirty-file inspection, `git diff`, or
  `git status` dependency is required to execute this packet.

## Stop Conditions

- Stop if current test source truth proves N1 or N2 has already been remediated;
  update only the scoped tracker/packet status and evidence instead of
  implementing stale work.
- Stop if fixing N1 requires creating, deleting, moving, or functionally
  changing agent tooling scripts rather than correcting the test's required vs
  optional behavior.
- Stop if fixing N2 requires changing Stage0 runtime behavior, changing
  `step_mu.py`, or changing the production cutover path rather than correcting
  proof wording/classification in tests.
- Stop if implementation requires writes outside the explicit scope inventory
  above.
- Stop if same-wave L4_ENABLER authority cannot be carried mechanically into
  the tracker/control-plane evidence.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- Missing listed required agent tooling scripts fail the smoke test with an
  explicit failure; missing optional tools may skip only if the optional list is
  explicit and separate from required core scripts.
- `mu/tests/l4_gates/test_meta_circular_evidence_gate.py` no longer presents
  `_apply_projection_trusted` source-lock coverage as the sole/current
  production path.
- Focused evidence distinguishes behavioral production-path proof from
  source-lock fallback-helper coverage, including the Stage0 VM cutover
  negative-control coverage in `mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- Focused validation includes the affected tests, at minimum:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_tooling_smoke.py mu/tests/l4_gates/test_meta_circular_evidence_gate.py mu/tests/l4_gates/test_stage0_vm_cutover.py`.
- The `[NEXT-CODEX-POST-REDTEAM]` tracker entry is updated with implementation
  status, evidence status, this packet path, this wave ID, and
  `FOUNDER_OVERRIDE:founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.

## Grounding / Authorization

FOUNDER_OVERRIDE:founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06

- `TASKS.md:433` authorizes the completed tests audit under
  `[NEXT-CODEX-POST-REDTEAM]`, records one blocking tests fail-closed defect
  plus two non-blocking test-integrity/proof-class findings, and states that
  remediation should be organized by category and severity without relisting
  already landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, or seed-registration work.
- `TASKS.md:435` records the organized remediation packet queue created by
  `founder-ordered-redteam-remediation-queue-organization-2026-05-05` and
  states that remediation was not implemented in that queue-organization wave.
- Current `TASKS.md` records
  `[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION]` as implemented
  with local evidence under `[NEXT-CODEX-POST-REDTEAM]`, wave ID
  `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`, class
  `L4_ENABLER`, category `tests`, this packet path, the archived
  non-blocking tests source audit packet path, and the N1/N2 finding inventory.
- Source authorization remains
  `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`;
  this Phase A packet adds the same-wave L4_ENABLER authority above so commit
  automation can derive the current wave override mechanically.

## Source Findings

### N1 - Agent Tooling Smoke Test Skips Missing Core Scripts

Classification: NON-BLOCKING DEFECT

Surfaces: agent/tooling smoke tests, test fail-closed behavior.

Source evidence preserved from
`reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`:

- Lines 44-53: `mu/tests/tools/test_agent_tooling_smoke.py:64` declares smoke
  coverage for importable/runnable agent tools; lines 67 through 76 enumerate
  eight core scripts; lines 77 through 85 state "Core tools should show help
  without crashing" but call `pytest.skip(...)` when a listed script path is
  absent.
- Lines 56-60 preserve current focused-pass output:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_tooling_smoke.py::TestAgentToolingSmoke::test_tool_help_works`
  exits with `8 passed in 1.16s`.
- Lines 65-82 preserve direct method-invocation output showing a missing script
  produces `skipped: Script not found: does/not/exist.py`.

### N2 - Meta-Circular Evidence Gate Retains A Source-Lock Claim For A Non-Production Fallback Path

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: L4 Stage0 / meta-circular evidence tests, source-lock-only
assertions, stale production-path wording.

Source evidence preserved from
`reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`:

- Lines 102-106: `mu/tests/l4_gates/test_meta_circular_evidence_gate.py:351`
  through `mu/tests/l4_gates/test_meta_circular_evidence_gate.py:366` assert by
  source text that `_apply_projection_trusted` calls `_stage0_match` and
  `_stage0_substitute`, with wording that calls it the "sole production path".
- Lines 107-117: current production cutover truth is recorded at
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1031`,
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1068`,
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1075` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1127`, and
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1303` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1308`.
- Lines 118-121: `mu/tests/l4_gates/test_stage0_vm_cutover.py:408` through
  `mu/tests/l4_gates/test_stage0_vm_cutover.py:430` prove by behavioral
  negative control that `_apply_projection_trusted` is not called on the cutover
  `step_kernel_mu` path.

## Implementation Evidence

Status: IMPLEMENTED / LOCAL EVIDENCE (2026-05-06).

- N1 resolved in `mu/tests/tools/test_agent_tooling_smoke.py`: the enumerated
  core tool scripts remain required, and missing required scripts now fail with
  `Required core tool script missing: {script}` instead of entering
  `pytest.skip(...)`. No optional tooling split was needed because the listed
  scripts are still the required core smoke set.
- N2 resolved in `mu/tests/l4_gates/test_meta_circular_evidence_gate.py`: the
  source-lock coverage for `_apply_projection_trusted` is now described as
  trusted fallback / compatibility-helper coverage. It no longer claims that the
  helper is the sole or current production `step_kernel_mu` path.
- Behavioral production-path proof remains separate and intact:
  `mu/tests/l4_gates/test_stage0_vm_cutover.py:408` through
  `mu/tests/l4_gates/test_stage0_vm_cutover.py:430` continue to prove by
  negative control that `_apply_projection_trusted` is not called on the cutover
  `step_kernel_mu` path. Read-only cutover context remains
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1031` with
  `_STAGE0_VM_CUTOVER = True` and
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1303` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1308` routing the live cutover
  branch through `_step_kernel_with_vm`.
- Focused local validation:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_agent_tooling_smoke.py mu/tests/l4_gates/test_meta_circular_evidence_gate.py mu/tests/l4_gates/test_stage0_vm_cutover.py`
  exits `0` with `113 passed, 17 skipped in 3.41s`.
- No runtime, substrate, seed, registry, scheduler, production Stage0,
  Claude-related, CI/workflow, or audit-tooling files were changed. Already
  landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, and seed-registration work was not relisted as unresolved.

## Tracker Update Note

Updated the `[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION]` entry
under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID, category
`tests`, severity `non-blocking`, source audit packet path, same-wave
`FOUNDER_OVERRIDE:founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`,
and the focused local acceptance evidence.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_meta_circular_evidence_gate.py`
  - `mu/tests/tools/test_agent_tooling_smoke.py`
  - `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ea0d07dd0025632a7a1aadb405c7c14917ab715105e86d75c8fef28d8849f5de`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_meta_circular_evidence_gate.py mu/tests/tools/test_agent_tooling_smoke.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_meta_circular_evidence_gate.py`
  - `mu/tests/tools/test_agent_tooling_smoke.py`
  - `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
