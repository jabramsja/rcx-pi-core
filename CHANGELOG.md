# Changelog

All notable changes to RCX-Ω are documented in this file.

Format:
- Date (YYYY-MM-DD)
- Category: Docs / Schemas / Runtime / Tests / Tooling
- Notes: Must distinguish "frozen contract" vs "future target"

## 2026-01-03

### Docs
- Frozen external CLI + JSON contracts in `docs/RCX_OMEGA_CONTRACTS.md`.
  - Notes: This freeze reflects CURRENT runtime behavior. Any future targets (e.g., `kind=omega_summary`) are explicitly marked as future and are NOT required today.

### Schemas
- Published optional JSON Schemas under `schemas/rcx-omega/`:
  - `trace.v1.schema.json`
  - `omega_summary.v1.schema.json`
- Policy: `kind` and `schema_version` are OPTIONAL and MUST remain opt-in + environment-gated. Default runtime output remains byte-for-byte identical.

### Process
- Added staging → stable promotion checklist in `docs/STAGING_TO_STABLE.md`.

### Runtime
- No runtime changes in this entry.

## 2026-01-03

### Runtime
- Added env-gated OPTIONAL schema fields to JSON producers:
  - Set `RCX_OMEGA_ADD_SCHEMA_FIELDS=1` to inject `schema_version` (and `kind` if absent).
  - Default output remains unchanged when the env var is not set.

### Docs
- Updated `docs/RCX_OMEGA_CONTRACTS.md` with a “Runtime Reality Notes” section to reflect current behavior:
  - `kind` may be omitted or may use legacy values (e.g., `omega`).
  - `kind=omega_summary` remains a FUTURE target, not a frozen requirement.
  - `schema_version` is OPTIONAL and opt-in only.

### Tests
- Verified green gate: `python3 -m pytest -q`

