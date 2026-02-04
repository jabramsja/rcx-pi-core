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

# RCX JSON Schemas

Canonical location for JSON Schemas used by RCX tooling and fixtures.

Notes:
- `$id` URIs are stable identifiers and may not match filesystem paths.
- Consumers should ignore unknown fields unless stated otherwise.
