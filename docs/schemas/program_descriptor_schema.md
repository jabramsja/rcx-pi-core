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

# ProgramDescriptor Schema (v1)

**Schema tag:** `rcx-program-descriptor.v1`

This document describes the *metadata-only* JSON shape emitted by:

- `python3 -m rcx_pi.programs.program_descriptor_cli <program>`
- `python3 -m rcx_pi.programs.program_descriptor_cli --schema`

## Required top-level fields

- `schema` (string)
- `schema_doc` (string)
- `kind` (string) — currently `mu_program`
- `name` (string)
- `language` (string) — currently `mu`
- `source_path` (string) — repo-relative path to the program artifact
- `source_sha256` (string) — sha256 of file contents
- `entrypoint` (string) — stable tool used to run/trace the program
- `determinism` (object)
- `version` (string) — currently `v1`

## Notes

- This descriptor is **pure metadata**. No execution is performed.
- The sha256 is intended for integrity + provenance, not for security guarantees.
