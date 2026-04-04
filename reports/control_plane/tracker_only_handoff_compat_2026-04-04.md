# Tracker-Only Handoff Compatibility

Date: 2026-04-04
Status: Implementation ready for routed supervisor
Task: [PIPELINE-RECOVERY/tracker-only-handoff-compat-2026-04-04]
Wave ID: tracker-only-handoff-compat-2026-04-04

## Scope

Preserve routed `UPDATE_TRACKER_ONLY` compatibility after the stricter tracker
note contract landed. The commit surface should still accept a routing record
that omits `tracker_note_text` by synthesizing the same contract-complete note
shape that `validate_handoff()` now requires.

## Trigger

Bot review finding on merged PR #718:

- `commit_executor.py` could reject a legitimate tracker-only routing record at
  Step 1 because `prepare_handoff_from_routing_record()` still emitted the old
  short fallback note while `validate_handoff()` now requires a full tracker
  note contract.

## Changed surfaces

- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_executor_dispatch.py`

## Proof points

1. `prepare_handoff_from_routing_record()` now uses
   `_build_default_tracker_note_text()` for tracker-only fallback handoffs,
   instead of synthesizing the deprecated one-line note.
2. The routed fallback path stays strict: tracker-only records still need a
   valid summary and wave identity, but they no longer fail just because the
   tracker note was omitted upstream.
3. Regression coverage now proves both the dispatcher-facing routing-record
   path and the receipt-facing handoff validation path.

## Validation

- `python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_receipt.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short`
