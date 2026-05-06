# Founder Ordered Redteam Tests Non-Blocking Remediation

Date: 2026-05-06
Status: QUEUED - NON-BLOCKING REMEDIATION PACKET
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: tests
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking.md`
Queue order: non-`/mu` non-blocking remediation, after docs non-blocking remediation and before tooling non-blocking remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the non-blocking tests follow-up from the founder ordered
redteam audit output. It does not implement remediation.

## Source Findings

### N1 - Agent Tooling Smoke Test Skips Missing Core Scripts

Classification: NON-BLOCKING DEFECT

Surfaces: agent/tooling smoke tests, test fail-closed behavior.

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking.md`:

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
`reports/deferred/non_blocking/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking.md`:

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

## Remediation Scope For Future Wave

- Make the agent tooling smoke test fail closed for missing listed core scripts
  or otherwise explicitly separate optional tools from required tools.
- Reword or restructure the meta-circular evidence gate so source-lock claims
  do not label a fallback helper as the current production path.
- Preserve the separate behavioral Stage0 VM cutover proof as the live
  production-path evidence.

## Stop Conditions

- Stop if current test source truth proves either non-blocking finding has
  already been remediated; update the tracker instead of implementing stale
  work.
- Stop if remediation requires runtime or `/mu` structural behavior changes
  instead of tests/proof wording or fail-closed test behavior.
- Stop if remediation would require edits outside relevant tests and matching
  tracker/control-plane updates.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- Listed required agent tooling script disappearance no longer converts the
  smoke check into a skip.
- Meta-circular evidence gate wording and proof class no longer present a
  fallback helper as the current production path.
- Focused test evidence distinguishes behavioral production-path proof from
  source-lock fallback coverage.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `tests`, severity `non-blocking`, source audit packet path, and the
acceptance evidence once implemented.
