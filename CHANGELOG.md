# Changelog

All notable changes to RCX are documented in this file.

## 2026-01-25

### Tooling
- **Rule Motif Observability v0** (PR #108)
  - `rules --print-rule-motifs` CLI command
  - `rule_motifs_v0()` pure helper returning all 8 rule motifs
  - `emit_rule_loaded_events()` generates v2 JSONL (`rule.loaded` events)
  - `RULE_IDS` canonical list for anti-drift testing
  - 11 subprocess CLI tests

- **Rule Motif Validation Gate v0** (PR #111)
  - `rules --check-rule-motifs` CLI command
  - `rules --check-rule-motifs-from <path>` for custom validation
  - `validate_rule_motifs_v0()` pure helper with validation rules:
    - Structure, id uniqueness, variable binding, host leakage, canonicalization
  - 16 subprocess CLI tests (positive + negative cases)

- **Trace Canon Helper v1** (PR #66)
  - `canon_jsonl()` function for JSONL serialization
  - 7 tests in `test_trace_canon_v1.py`
  - v2 event support (accepts both v1 and v2 events)

### Runtime
- **Second Independent Encounter v0** (NEXT #16)
  - Stall memory tracking: `_stall_memory` maps pattern_id → value_hash
  - Closure signal detection: `_check_second_independent_encounter()`
  - Memory clearing on `execution.fixed`: `_clear_stall_memory_for_value()`
  - Public API: `closure_evidence`, `has_closure` properties
  - `stall()` and `consume_stall()` now return bool (closure detected)
  - 15 tests in `test_second_independent_encounter.py`
  - All 8 pathological scenarios from IndependentEncounter.v0.md tested

### Docs
- Updated `docs/RuleAsMotif.v0.md` to reflect implementation status
- Updated `docs/cli_quickstart.md` with rules commands
- Updated `docs/IndependentEncounter.v0.md` to IMPLEMENTED status

## Unreleased

- Schema-triplet canonicalization: added `rcx_pi/cli_schema_run.py` as the single source of truth and updated CLI smoke + tests to route schema checks through the canonical runner (PRs #59–#62).

## 2026-01-24

### Runtime
- **v2 Execution Semantics (RCX_EXECUTION_V0=1)**
  - ExecutionEngine with stall/fix/fixed state machine
  - Public consume API: `consume_stall`, `consume_fix`, `consume_fixed`
  - Public getter: `current_value_hash` for post-condition assertions
  - `value_hash()` for deterministic value references
  - Record Mode v0: execution → trace for stall/fix events

### Tooling
- **Anti-theater guardrails**
  - `--print-exec-summary` CLI flag for v2 execution summary
  - `execution_summary_v2()` pure helper (derives state from events only)
  - `tools/audit_exec_summary.sh` non-test reality anchor
  - `test_cli_print_exec_summary_end_to_end` subprocess CLI test

### Docs
- `docs/TraceReadingPrimer.v0.md` - Human-readable trace guide
- `docs/Flags.md` - Flag discipline contract
- `docs/MinimalNativeExecutionPrimitive.v0.md` - Boundary question answered
- Removed `NEXT_STEPS.md` (redundant with TASKS.md)

### Tests
- v2 replay validation (`validate_v2_execution_sequence`)
- Record→Replay gate end-to-end determinism test
- Closure-as-termination fixture family (stall_at_end, stall_then_fix_then_end)

### Process
- TASKS.md is now the single canonical task tracker
- All v2 work gated by feature flags (default OFF)

Format:
- Date (YYYY-MM-DD)
- Category: Docs / Schemas / Runtime / Tests / Tooling
- Notes: Must distinguish "frozen contract" vs "future target"

## 2026-01-12

### Tooling
- Kernel step-003/004: stabilize world_trace_cli invocation (script + module); tests now 216 passed, 1 skipped.
- Verified repo green gate (212 passed, 1 skipped).
- Freeze tag created on dev: `rcx-freeze-verified-2026-01-12` → `18c2dad`.
- Quarantine cleanup / ignore rules for accidental CLI-arg files.
- Added world trace CLI (Python).
- Added core MU freezer utility (`rcx_pi_rust/scripts/freeze_core_mu.py`).

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

## 2026-01-23

### Tests
- Enforced **orbit artifact idempotence** for tracked files.
  - Re-running `scripts/build_orbit_artifacts.sh` no longer dirties the working tree.
- Formalized **orbit provenance semantics**:
  - Provenance entries validated against emitted state transitions.
  - Supports both legacy (`from` / `to`) and current (`pattern` / `template`) schemas.
  - State entries may be strings or structured objects (e.g. `{"i": 0, "mu": "ping"}`).

### Tooling
- Added Graphviz SVG normalization to strip version-specific metadata.
  - SVG fixtures are now stable across Graphviz versions.
- Added `scripts/merge_pr_clean.sh` helper for repositories with auto-merge disabled.
  - Rebase head onto base, safe force-push, gate wait, manual merge, post-merge sync.
  - Convenience script only; repository policy unchanged.

### Process
- Confirmed layered-growth rule enforcement:
  - Kernel remains frozen.
  - All new behavior implemented via tools, fixtures, or validation layers.
- Green gate verified after each change sequence.

Notes:
- No kernel or runtime semantics were modified.
- All changes live strictly outside the frozen RCX-π core.
