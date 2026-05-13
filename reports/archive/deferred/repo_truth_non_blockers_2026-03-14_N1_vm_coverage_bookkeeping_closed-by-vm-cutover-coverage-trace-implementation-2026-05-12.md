# Archived N1 VM Coverage Bookkeeping Advisory

Source: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
Section: `N1. Python VM cutover coverage reconstruction is not directly locked`
Closed by: `vm-cutover-coverage-trace-implementation-2026-05-12`
Closed on: 2026-05-12

## Closure Evidence

- Python Stage0 VM results now emit `attempt_trace` with ordered
  `attempted_program_ids`, final `outcome`, and `matched_program_id`.
- JS Stage0 VM results emit the same `attempt_trace` shape.
- Python `_step_kernel_with_vm` now records coverage from the VM-emitted trace,
  not host-side `bundle["program_order"]`.
- Focused coverage tests assert match and stall composition and include a
  negative control where the host bundle order is intentionally unrelated to
  the VM trace.
- Evidence commands:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py mu/tests/l4_gates/test_stage0_vm_cutover.py --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short`
  - `node mu/host/js/eval_step.js`

## Archived Source Text

### N1. Python VM cutover coverage reconstruction is not directly locked

- **Outcome:** retained live advisory.
- **Governing route:** `reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
- **Current proof gap:** the completed Phase A packet reproduced that
  `_step_kernel_with_vm` still reconstructs coverage bookkeeping from host-side
  bundle order because Stage0 results do not emit ordered attempted-program
  traces or no-match/match events.
- **Hard stop before implementation:** no runtime, Stage0, coverage, seed,
  scheduler, registry, parity, or production `/mu` edits are authorized by this
  source packet or by the completed Phase A evidence packet.
- **Doctrine boundary:** future work must derive bookkeeping proof from
  Mu/Stage0 structural execution or a parity-preserving VM trace; it must not
  add host-only coverage semantics.

- `_step_kernel_with_vm()` reconstructs coverage semantics for compiled
  `match.v2` / `subst.v2`
- the current cutover gate proves equivalence and polarity, but not exact
  `record_no_match` / `record_match` bookkeeping parity

**Why deferred:** The cutover gate tests prove behavioral equivalence (same
input -> same output) and polarity (VM path produces same match/subst results
as host path). Adding exact bookkeeping parity tests requires instrumenting the
VM to emit coverage events, which is a new capability in the Stage0 VM.
**Target packet:**
`reports/control_plane/vm_cutover_coverage_bookkeeping_proof_2026-05-09.md`.
