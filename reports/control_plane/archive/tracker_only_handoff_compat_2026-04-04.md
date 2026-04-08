# Tracker-Only Handoff Compatibility

Date: 2026-04-04
Status: Routed malformed-input remediation staged
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
3. `force_add_files: null` is now treated as an omitted optional field for this
   tracker-only fallback path instead of crashing during tracker-note synthesis.
4. Non-string `commit_message` values are coerced before fallback tracker-note
   synthesis so malformed routing records fail closed through validation instead
   of throwing an attribute error.
5. Regression coverage now proves both the dispatcher-facing routing-record
   path and the receipt-facing handoff validation path, including the malformed
   optional-input cases that triggered the follow-on bot review.

## Validation

- `python3 -m py_compile mu/tools/executors/commit_executor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_receipt.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short -k 'prepare_handoff'`
- `./tools/checks/check_docs_consistency.sh`
- `./tools/session/founder_session_attest.sh closeout`

## Routed closeout note

The first routed `commit` replay for this wave proved the original missing-note
bug surface: an `UPDATE_TRACKER_ONLY` routing record with no `tracker_note_text`
now makes it through Step 3, Step 4, Step 5, and supervisor review cleanly.
That replay then failed later at `pre-push-fast` for a separate governance
reason: this maintenance slice needed an explicit `FOUNDER_OVERRIDE` marker to
clear the rolling structural quota.

The follow-on replay surfaced two more malformed-input crash paths in bot
review. This remediation round widens the same wave just enough to close those
paths honestly before rerunning the routed commit pipeline:

- normalize `force_add_files: null` before tracker-note synthesis
- coerce non-string `commit_message` before tracker-note synthesis
- lock both cases with narrow regression tests
