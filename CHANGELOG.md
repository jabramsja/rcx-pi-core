# Changelog

All notable changes to RCX are documented in this file.

## 2026-01-27

### Tooling
- **Comprehensive Debt Tracking** (PR #155)
  - Marked ~289 LOC of previously unmarked semantic debt with `@host_*` decorators
  - match_mu.py: 7 decorators (3 `@host_recursion`, 4 `@host_builtin`)
  - subst_mu.py: 2 decorators (`@host_builtin`)
  - Updated DEBT_THRESHOLD: 14 → 23 (17 tracked + 5 AST_OK + 1 review)
  - Updated dashboard ceiling: 9 → 17
  - All semantic debt now fully tracked (was ~289 LOC unmarked)

### Tests
- **Head/Tail Collision Tests** (PR #155)
  - `TestMatchParityHeadTailCollision`: 5 tests verifying dicts with head/tail keys
  - Ensures user data like `{"head": "x", "tail": "y"}` isn't misclassified as linked list

- **Empty Collection Tests** (PR #155)
  - `TestMatchParityEmptyCollections`: 5 tests documenting known difference
  - Documents: `{}` and `[]` both normalize to `null` (intentional structural equivalence)
  - Tests explicitly mark this as "DOCUMENTED DIFFERENCE" vs parity

### Docs
- **Design Decisions Documented** (PR #155)
  - `docs/core/DebtCategories.v0.md`: Added "Known Design Decisions" section
  - Empty collection normalization explained with rationale
  - Head/tail collision handling documented

### Process
- All 6 agents reviewed: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Debt now at ceiling (23/23) with clear path to L2

### Security
- **Seed Integrity Verification** (PR #157)
  - `rcx_pi/selfhost/seed_integrity.py`: SHA256 checksum verification
  - Validates seed structure on load (meta, projections keys required)
  - Verifies expected projection IDs present and wrap is last
  - `match_mu.py` and `subst_mu.py` now use `load_verified_seed()`
  - 27 tests in `tests/test_seed_integrity.py`
  - Closes adversary finding: seeds were loaded without integrity verification

### Self-Hosting
- **Phase 6a: Lookup as Mu Projections** (PR #158)
  - Added `subst.lookup.found` and `subst.lookup.next` projections to subst.v1.json
  - Lookup is now structural: pattern matching with non-linear vars
  - `subst.var` now transitions to `phase: lookup` instead of creating marker
  - `subst.lookup.found`: name matches current binding → return value
  - `subst.lookup.next`: name doesn't match → continue with rest
  - Unbound variables stall (lookup_bindings becomes null, no projection matches)
  - Removed 2 `@host_builtin` decorators from subst_mu.py
  - DEBT_THRESHOLD: 23 → 21 (ratchet tightened)
  - 37 subst parity tests pass

- **Phase 6b: Classification as Mu Projections**
  - Created `seeds/classify.v1.json` with 6 projections for linked list classification
  - Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
  - `denormalize_from_match()` now uses `classify_linked_list()` instead of `is_dict_linked_list()`
  - `classify.nested_not_kv`: detects when "key" position has head/tail (not a string)
  - `classify.kv_continue`: element is valid kv-pair → continue scanning
  - `classify.not_kv`: element is not kv-pair → classify as list
  - Python pre-check validates: no cycles, all keys are strings (projections can't verify types)
  - Removed 2 `@host_builtin` decorators from match_mu.py
  - DEBT_THRESHOLD: 21 → 19 (ratchet tightened)
  - 26 tests in `tests/test_classify_mu.py`

- **Phase 6c: Normalization as Iterative + Type Tags**
  - `normalize_for_match()`: converted from recursive to iterative using explicit stack
  - `denormalize_from_match()`: converted from recursive to iterative using explicit stack
  - Removed 2 `@host_recursion` decorators from match_mu.py
  - Removed 2 `# AST_OK: bootstrap` comments (recursive comprehensions eliminated)
  - isinstance() checks at Python↔Mu boundary remain as scaffolding (not semantic debt)
  - **Type Tags** resolve list/dict ambiguity (previously `[["a", 1]]` and `{"a": 1}` normalized identically):
    - Lists get `_type: "list"`, dicts get `_type: "dict"` at root node
    - `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` for security
    - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
    - `classify_linked_list()` fast-path for type-tagged structures
  - 24 new property-based fuzzer tests (`tests/test_type_tags_fuzzer.py`)
  - All 1020 self-hosting tests pass
  - Agent review: verifier=APPROVE, adversary=HARDENED, structural-proof=PROVEN

## 2026-01-26

### Runtime
- **Thread-Safe Step Budget** (PR #149)
  - `_ProjectionStepBudget` uses `threading.local()` for thread isolation
  - Each thread gets independent budget tracking for concurrent execution
  - `get_step_budget()` and `reset_step_budget()` API

- **Cycle Detection** (PR #149)
  - `normalize_for_match()` detects circular references (raises ValueError)
  - `denormalize_from_match()` detects circular references (raises ValueError)
  - `is_dict_linked_list()` returns False on cycles instead of infinite loop

- **Resource Exhaustion Guardrails** (PR #149)
  - Global projection step budget: MAX_PROJECTION_STEPS = 50,000
  - Mu depth limit: MAX_MU_DEPTH = 200
  - Mu width limit: MAX_MU_WIDTH = 1,000
  - Empty variable name rejection in match_mu/subst_mu

### Tests
- **Comprehensive Fuzzer Tests** (PR #149)
  - `tests/test_selfhost_fuzzer.py`: 53 tests, 10,000+ random examples
  - `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
  - `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
  - `TestHostileUnicodeHandling`: emoji, RTL, zero-width, homoglyphs
  - `TestNearLimitStress`: width 900-1000, depth 190-200
  - All Hypothesis tests use deadline=5000 (prevents infinite hangs)

- **Adversary Tests** (PR #149)
  - `test_nested_calls_exhaust_budget`: verifies budget limits cascading calls
  - `test_budget_thread_isolation`: verifies no cross-thread contamination
  - `test_circular_in_is_dict_linked_list_returns_false`: cycle safety
  - `test_nested_circular_in_normalize_raises`: nested cycle detection

### Process
- All 6 agents approved: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Coverage rated ROBUST by fuzzer agent

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
