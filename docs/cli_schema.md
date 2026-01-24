

## Schema triplet contract (v1)

Several RCX CLI entrypoints support `--schema`. When invoked, they must print exactly one line with exactly three space-delimited fields:

    <schema_tag> <schema_doc_path> <schema_json_path>

Example:

    rcx-program-run.v1 docs/program_run_schema.md docs/schemas/program_run_schema.json

### Canonical helper

The canonical formatter for this output is:

- rcx_pi/cli_schema.py
  - schema_triplet(tag, doc_md, schema_json) -> str
  - print_schema_triplet(tag, doc_md, schema_json) -> None

CLIs should route `--schema` output through print_schema_triplet(...) to keep formatting stable across refactors.

### Covered emitters

Currently covered by this contract:

- rcx_pi/program_descriptor_cli.py --schema
- rcx_pi/program_run_cli.py --schema
- python -m rcx_pi.worlds.world_trace_cli --schema
- scripts/snapshot_merge.py --schema
