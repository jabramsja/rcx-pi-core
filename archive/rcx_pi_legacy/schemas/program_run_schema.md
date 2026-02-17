<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-03
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# RCX Program Run JSON Contract (v1)

This describes the JSON emitted by `python -m rcx_pi.program_run_cli`.

## Shape

- `schema`: fixed tag `rcx-program-run.v1`
- `schema_doc`: path to this doc
- `program`: registry name (e.g. `succ-list`)
- `input`: list of ints provided to the program
- `output`: list of ints returned by the program
- `ok`: boolean success flag (true on success)
- `warnings`: optional list of warning strings
- `meta`: provenance + determinism fields

## Determinism

`meta.determinism.inputs_hash` is the SHA256 of a stable JSON encoding of `{program, input}`.
