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
