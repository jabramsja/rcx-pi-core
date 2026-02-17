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

# CLI Schema Triplet Contract

## Schema triplet contract (v1)

Several RCX CLI entrypoints support `--schema`. When invoked, they must print exactly one line with exactly three space-delimited fields:

    <schema_tag> <schema_doc_path> <schema_json_path>

Example:

    rcx-world-trace.v1 mu/docs/schemas/world_trace_json_schema.md mu/docs/schemas/world_trace_json_schema.json

### Canonical helper

The canonical formatter and parser live in:

- rcx_pi/cli_schema.py
  - schema_triplet(tag, doc_md, schema_json) -> str
  - print_schema_triplet(tag, doc_md, schema_json) -> None
  - parse_schema_triplet(line) -> SchemaTriplet
  - parse_schema_triplet_tuple(line) -> (tag, doc_md, schema_json)

CLIs should route `--schema` output through `print_schema_triplet(...)` to keep formatting stable across refactors.

### Strictness rules

This contract is intentionally strict (tests enforce it):

- Exactly one non-empty stdout line.
- Exactly three fields separated by single spaces.
- No leading/trailing whitespace.
- No tabs or embedded whitespace inside any field.
- Paths are repo-relative and follow conventions:
  - doc: `mu/docs/schemas/*.md`
  - schema: `mu/docs/schemas/*.json`

### Covered emitters

Currently covered by this contract:

- python -m rcx_pi.worlds.world_trace_cli --schema
- scripts/snapshot_merge.py --schema
