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
rcx program describe rcx_pi_rust/mu_programs/rcx_core.mu --json

### Program run (named RCX-π programs)

rcx program run succ-list "[1,2,3]" --pretty
printf '[4,5]' | rcx program run succ-list --stdin --pretty
rcx program run succ-list --input-file /tmp/input.json --pretty

### World trace (Mu worlds via Rust orbit_cli)

rcx world trace pingpong ping --max-steps 12 --pretty
rcx trace pingpong ping --max-steps 6 --pretty

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
