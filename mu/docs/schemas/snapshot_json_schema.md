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

# rcx.snapshot.v1 (JSON schema)

This schema captures a complete replayable snapshot: world identifier + program rules + RCXState buckets/registries/trace.

It is designed for:
- stable diffs (golden fixtures)
- roundtrip proof (save -> wipe -> restore -> same behavior)
- future replay tooling (load snapshot -> run -> emit trace/orbit)

## Schema id

- schema: rcx.snapshot.v1

## Shape (informal)

Top-level:
- schema: string (must be rcx.snapshot.v1)
- world: string (world/program name, e.g. rcx_core)
- program.rules: array[string]
  - each rule string uses the same canonical line format as serialize.rs, e.g.
    - [news,stable] -> ra
    - [PING,PING] -> rewrite [PONG,PING]
- state:
  - current: string | null
  - ra, lobes, sink: array[string]
  - step_counter: integer
  - null_reg, inf_reg: array[string]
  - trace: array of events
    - step: integer
    - phase: string
    - route: string
    - payload: string

## Golden fixture

- mu/docs/fixtures/snapshot_rcx_core_v1.json

Regeneration (historical — rcx_pi_rust archived in Round 23A):

The golden fixture is stable. Original generation used `archive/rcx_pi_rust/` Rust examples.
See `archive/rcx_pi_rust/` for historical tooling if regeneration is ever needed.
