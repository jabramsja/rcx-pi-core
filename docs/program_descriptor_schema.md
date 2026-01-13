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
