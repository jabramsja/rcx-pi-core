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

# RCX CLI Quickstart

This repo ships a small family of CLIs that emit stable JSON contracts.

## Install (editable)

python3 -m pip install -e .

## Umbrella CLI: rcx

Routes to the underlying tools.

rcx --help
rcx program describe --schema
rcx program run --schema
rcx world trace --schema

### Program describe (Mu program descriptor)

rcx program describe rcx_core --json
rcx program describe mu/mu_programs/rcx_core.mu --json

### Program run (named RCX-π programs)

rcx program run succ-list "[1,2,3]" --pretty
printf '[4,5]' | rcx program run succ-list --stdin --pretty
rcx program run succ-list --input-file /tmp/input.json --pretty

### World trace (Mu worlds via Rust orbit_cli)

rcx world trace pingpong ping --max-steps 12 --pretty
rcx trace pingpong ping --max-steps 6 --pretty

### Rules (Rule motif observability + validation)

rcx rules --print-rule-motifs          # Emit rule.loaded v2 trace events as JSONL
rcx rules --check-rule-motifs          # Validate built-in rule motifs
rcx rules --check-rule-motifs-from FILE  # Validate rule motifs from JSON file

## Direct tools

rcx-program-descriptor --schema
rcx-program-run --schema
rcx-world-trace --schema

## JSON schemas

- Program descriptor: docs/program_descriptor_schema.json (tag: rcx-program-descriptor.v1)
- Program run:        docs/program_run_schema.json (tag: rcx-program-run.v1)
- World trace:        docs/world_trace_json_schema.md (tag: rcx-world-trace.v1)


## Umbrella command (non-conflicting)

If you already use `rcx` as a shell alias, use `rcx-cli` as the umbrella dispatcher:

- `rcx-cli --help`
- `rcx-cli program describe --schema`
- `rcx-cli program run succ-list "[1,2,3]" --pretty`
- `rcx-cli trace pingpong ping --max-steps 6 --pretty`
