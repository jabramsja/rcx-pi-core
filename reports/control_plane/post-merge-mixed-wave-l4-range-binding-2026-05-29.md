# Post-Merge Mixed-Wave L4 Range Binding

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: `[NEXT-CODEX-POST-REDTEAM]`
Wave ID: `post-merge-mixed-wave-l4-range-binding-2026-05-29`
Class: L4_ENABLER
Target Gate: G8
Lane: control-surface
Authorization: bounded pipeline repair with same-wave mechanized regression
FOUNDER_OVERRIDE:post-merge-mixed-wave-l4-range-binding-2026-05-29

## Scope

This is a bounded control-surface repair for the post-merge dev-push L4
execution-contract failure after PR #1041 merged.

Allowed product writes:

- `mu/tools/checks/enforce_l4_execution_contract.py`
- `mu/tests/tools/test_l4_execution_contract_enforcement.py`
- `reports/control_plane/post-merge-mixed-wave-l4-range-binding-2026-05-29.md`
- `reports/l4_wave_indicators/post-merge-mixed-wave-l4-range-binding-2026-05-29.json`
- `TASKS.md`

No runtime, substrate, seed, scheduler, registry, production workflow, or Mu
semantic changes are authorized by this packet.

## Direct Evidence

- GitHub `rcx-green-gate` dev push run `26641037224` failed in the
  `Enforce L4 execution contract` step before running green-gate tests.
- Local reproduction with range
  `80654e2420275df2bea07b2c450883564aa13460...aaf6eaa651cc66792a98012990dfdf91dcc6ff19`
  printed `WAVE_ID_FLAG=` followed by `Wave class: L4_ENABLER` and rejected
  executable runtime lines in `mu/host/js/core/stage0_vm.js`.
- `mu/tools/checks/enforce_l4_execution_contract.py` extracted touched TASKS
  tracker ids from added note lines, but `bind_note_from_touched_wave_ids()`
  selected the last added note without considering whether the range contained
  runtime files.
- The same range added a structural tracker note for
  `js-stage0-vm-trusted-run-hotpath-2026-05-29` before an enabler tracker note
  for `phase-b-recovery-classifier-scope-repair-2026-05-29`, and the runtime
  executable diff belonged to the structural wave.

## Repair

1. Teach touched-note binding to inspect the changed-file scope.
2. When a range contains runtime files and exactly one touched tracker note is
   `L4_STRUCTURAL`, bind that structural note even if a later enabler tracker
   note is in the same post-merge range.
3. When a runtime range touches more than one structural tracker note, fail
   closed and require explicit `--wave-id` instead of guessing.
4. Add unit coverage for the single-structural and ambiguous-structural binding
   cases.
5. Add a temp-repo CLI regression that recreates the post-merge structural
   plus recovery tracker ordering and proves the checker reports
   `Wave class: L4_STRUCTURAL`.

## Local Evidence

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_l4_execution_contract_enforcement.py -k 'touched_wave_ids or runtime_range_with_followup_enabler' --tb=short`
  - `4 passed, 184 deselected in 0.30s`
- `python3 tools/checks/enforce_l4_execution_contract.py --range 80654e2420275df2bea07b2c450883564aa13460...aaf6eaa651cc66792a98012990dfdf91dcc6ff19`
  - `Wave class: L4_STRUCTURAL`
  - `Changed files: 16`
  - `Runtime files: 3`
  - `Control-plane files: 2`
  - `L4 Execution Contract v2: L4_STRUCTURAL compliant`

## Proof Limit

This wave fixes the binding bug that blocked the dev-push gate for a mixed
post-merge range. It does not claim to optimize slow tests or close the separate
nightly slow-lane investigation.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `post-merge-mixed-wave-l4-range-binding-2026-05-29`
- Active packet: `reports/control_plane/post-merge-mixed-wave-l4-range-binding-2026-05-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `156190613853d5ee0435822edf851f61188ca1fac873c605e814620a5174da25`
- Indicator artifact: `reports/l4_wave_indicators/post-merge-mixed-wave-l4-range-binding-2026-05-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_l4_execution_contract_enforcement.py -k 'touched_wave_ids or runtime_range_with_followup_enabler' --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --range 80654e2420275df2bea07b2c450883564aa13460...aaf6eaa651cc66792a98012990dfdf91dcc6ff19`.
- Evidence delta: (1) Local reproduction of failed dev-push range now reports `Wave class: L4_STRUCTURAL`. (2) Focused tool regression covers single-structural runtime binding, ambiguous multi-structural refusal, and temp-repo CLI mixed structural-plus-enabler ordering. (3) Same-wave mechanical repair prevents later recovery tracker notes from stealing runtime-range ownership.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/post-merge-mixed-wave-l4-range-binding-2026-05-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
  - `mu/tools/checks/enforce_l4_execution_contract.py`
  - `reports/control_plane/post-merge-mixed-wave-l4-range-binding-2026-05-29.md`
  - `reports/l4_wave_indicators/post-merge-mixed-wave-l4-range-binding-2026-05-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
