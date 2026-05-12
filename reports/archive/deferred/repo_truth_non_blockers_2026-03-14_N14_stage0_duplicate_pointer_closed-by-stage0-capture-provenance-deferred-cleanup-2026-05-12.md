# Repo Truth Non-Blockers N14 Partial Closure

Source packet: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
Closed by: `stage0-capture-provenance-deferred-cleanup-2026-05-12`
Closure grounding: `stage0-capture-path-provenance-implementation-2026-05-12`

This archive contains only the duplicate N14 Stage0 capture provenance pointer
removed from the active repo-truth packet. The active source packet keeps N1 VM
coverage bookkeeping, N3 broad host-surface boundary, and N5 JS pipeline shape
governance live.

Current closure evidence:

- Python `capture_path` copies only Mu-domain captures with
  `reject_non_mu=True` at `mu/host/python/rcx_pi/selfhost/stage0_vm.py:825`
  through `mu/host/python/rcx_pi/selfhost/stage0_vm.py:826`.
- JavaScript `capture_path` copies only Mu-domain captures via
  `safeMuCopy(val, true, 'capture_path')` at
  `mu/host/js/core/stage0_vm.js:889`.
- `mu/tests/l4_gates/test_stage0_vm.py:1374` through
  `mu/tests/l4_gates/test_stage0_vm.py:1476` prove valid Python/Node capture
  parity and direct non-Mu capture rejection at `capture_path`.

## Archived Section: N14. Stage0 capture_ref returns null/None for hostile leaves (design gap)

- **Outcome:** duplicate pointer closed by the successor Stage0 implementation;
  not a separate active packet.
- **Governing route:** `reports/control_plane/stage0_capture_path_provenance_boundary_2026-05-09.md`.
- **Closure route:** `reports/control_plane/stage0_capture_path_provenance_implementation_2026_05_12_2026-05-12.md`.

- capture_ref deep-copies via _safe_mu_copy. Non-Mu types (subclasses) are canonicalized to null/None.
- Bridge considers this a "successful match on hostile input" since the VM returns match with root=null.
- Design decision before successor implementation: null/None was the fail-closed canonical value for non-Mu inputs. The successor implementation tightened the boundary by rejecting non-Mu direct capture at `capture_path`.
- Status: duplicate advisory closed, not a separate pending packet.
