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

- docs/fixtures/snapshot_rcx_core_v1.json

Regenerate (from repo root):

    (cd rcx_pi_rust && cargo build --examples)
    (cd rcx_pi_rust && cargo run --example snapshot_json_cli -- rcx_core "[null,a]" "[inf,a]" "[paradox,a]" "[omega,[a,b]]" > ../docs/fixtures/snapshot_rcx_core_v1.json)

Roundtrip proof (write -> wipe -> restore -> same behavior):

    (cd rcx_pi_rust && cargo run --example snapshot_roundtrip_cli)
