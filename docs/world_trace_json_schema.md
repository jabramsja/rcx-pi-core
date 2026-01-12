# world_trace JSON schema (stable surface)

This is the stable JSON output contract for:
- ./scripts/world_trace.sh --json [--pretty] ...

Top-level object keys (required):
- schema: string (version tag for this schema)
- world: string
- seed: string
- max_steps: int
- orbit: object
- trace: array

`orbit` object:
- kind: string
- period: int | null
- states: array[string]   # motif strings in visit order (may be 1+)

`trace`:
- array of step entries (object shape may evolve; keep backward compatible)

Notes:
- Additional top-level keys may be added in the future, but existing keys must remain.
