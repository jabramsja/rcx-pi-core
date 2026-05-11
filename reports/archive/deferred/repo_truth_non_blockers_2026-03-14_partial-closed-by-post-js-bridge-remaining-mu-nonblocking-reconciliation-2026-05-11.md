# Archived Closed Slice: repo_truth_non_blockers_2026-03-14 N2

Source packet:
`reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`

Archived by:
`post-js-bridge-remaining-mu-nonblocking-reconciliation-2026-05-11`

## Closed Finding

### N2. JS bridge-mode VM shadow evidence is still thinner than the core lane

Original active text:

- JS self-tests prove bridge-mode smoke behavior and bridge ordering validation.
- They do not yet directly lock the full `kernel.v1 -> bridge -> match.v2 ->
  subst.v2` ordering semantics under the VM-shadow lane.
- Target wave:
  `reports/control_plane/js_bridge_vm_ordering_evidence_2026-05-09.md`.

## Closure Evidence

- PR #927 merged at
  `8334c369d7a302cca568de0a088ea9ca1bd1c2f5`.
- The implementation commit was
  `ee69f0a0b9b9023bc278b91e7b72419eede6f813`.
- `mu/tests/parity/test_js_vm_bridge_parity.py:429` through
  `mu/tests/parity/test_js_vm_bridge_parity.py:440` now drives the proof
  through public `stepKernel(..., {returnMeta:true, vmConfig})`.
- `mu/tests/parity/test_js_vm_bridge_parity.py:483` through
  `mu/tests/parity/test_js_vm_bridge_parity.py:505` records public-entrypoint
  Stage0 bundle trace evidence, including `bundle.programs` access.
- `mu/tests/parity/test_js_vm_bridge_parity.py:657` through
  `mu/tests/parity/test_js_vm_bridge_parity.py:804` asserts the end-to-end
  ordering proof and same-output negative controls for
  `kernel -> bridge -> match -> subst` under the live JS VM kernel path.
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:196` through
  `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py:231` mechanically
  scans both `_stage0VmStepTrusted` and `StepTrusted` fragments outside the
  trusted allowlist.

## Outcome

Closed/superseded. The old source-lock/e2e ordering proof gap is no longer an
active deferred advisory. PR #927 and
`js-bridge-vm-ordering-source-lock-repair-2026-05-11` are closure evidence only;
they are not same-wave authorization for this reconciliation packet and are not
retained as unresolved pending work.
