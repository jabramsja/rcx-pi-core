# Archived Closed Sections: plan-learning-store-enforcement-2026-04-08

Date archived: 2026-05-06
Source packet: `reports/deferred/non_blocking/plan-learning-store-enforcement-2026-04-08-2026-04-08_bridge_nonblockers.md`
Reason: deferred non-blocking cleanup moved the code-closed finding out of the
active advisory lane.

## Archived Finding 2

`Layer 11 still overblocks safe glued python -m<module> invocations`

- Class: DEFECT
- Severity: low
- File: `mu/tools/executors/recovery_gate.py`
- Disposition: non_blocking

## Evidence

- `mu/tools/executors/recovery_gate.py:3457` through
  `mu/tools/executors/recovery_gate.py:3473` route `-m <module>` and glued
  `-m<module>` forms to module invocation mode and return `False` for the Layer
  11 positional-script check.
- Direct probe output from the 2026-05-06 cleanup:
  `python3 -mjson.tool data.json => False` and
  `python3 -mpytest tests/ => False`.
