# RCX Task List (Canonical)

This file is the single source of truth for authorized work.
If a task is not listed here, it is NOT to be implemented.

---

## North Star (Keep This True)

1. RCX VM is not a "runner". It is a substrate where **structure is the primitive**.
2. "Code = data" means execution is graph/mu transformation, not host-language semantics.
3. **Stall → Fix → Trace → Closure** is the native engine loop; everything else must serve it.
4. Closures/gates must be **explicit, deterministic, and measurable** (fixtures + replay).
5. Emergence must be attributable to RCX dynamics, not "Python did it".
6. Host languages are scaffolding only; their assumptions must not leak into semantics.
7. Buckets (r_null / r_inf / r_a / lobes / sink) are **native routing states**, not metaphors.
8. Seeds must be minimal (void/empty) and growth must be structurally justified.
9. Determinism is a hard invariant: same seed + rules ⇒ same trace/fixtures.
10. A "program" is a pressure vessel: seed + allowable gates + thresholds + observation outputs.
11. Enginenews-like specs are target workloads to prove: "does ω/closure actually emerge?"
12. Every task must answer: "Does this reduce host smuggling and increase native emergence?"
13. **L3 Parity: Python and JavaScript must run identical projections with identical semantics.**
    - Same seeds: kernel.v1, match.v2, subst.v2, recurrence.v1, exhaustion.v1 (all 47 projections)
    - Same bootstrap primitives: eval_step, mu_equal, max_steps, stack_guard, projection_loader
    - Any change to Python projection behavior MUST be mirrored in JS
    - Any new seed MUST be loaded and tested in BOTH substrates
14. **Seeds must declare their execution layer.** Every seed is either:
    - **BOOTSTRAP**: Runs via eval_seed.step() only (Python/JS substrate provides non-linear pattern support)
    - **META-CIRCULAR**: Runs via step_kernel_mu (kernel.v1 + match.v2 + subst.v2)
    - If a seed claims META-CIRCULAR, tests MUST verify it through step_kernel_mu
    - Seeds requiring non-linear patterns (same var twice for equality) are BOOTSTRAP until bootstrap_structural bridge exists
    - Current BOOTSTRAP seeds: recurrence.v1, exhaustion.v1 (require non-linear patterns)
    - Current META-CIRCULAR seeds: kernel.v1, match.v2, subst.v2, classify.v1, eval.v1 (linear only)
15. **True self-hosting is the path.** The goal is structural computation without host semantics:
    - **L1 (Algorithmic)**: match/subst algorithms as Mu projections ✓ DONE
    - **L2 (Operational)**: kernel loop as Mu projections ✓ DONE (with bootstrap primitive acceptance)
    - **L3 (Substrate Portability)**: same projections run on Python AND JavaScript ✓ DONE
    - **L4 (True Self-Hosting)**: eliminate bootstrap primitives OR make them substrate-independent
    - Programs must run accurately and structurally, without host semantics (except irreducible bootstrap)
    - Tests must verify the CLAIMED execution path, not just correctness
    - If tests pass via bootstrap but fail via meta-circular kernel, that's a real bug (not theater)

---

## Governance (Non-Negotiable)

- Do not add new subsystems, execution models, or architectures without explicit approval.
- Do not create "new tests" to bypass a failing test; fix the failing test or the code.
- Do not leave broken files/tests behind and add replacements.
- Minimize file creation. Prefer editing existing files.
- v1 replay semantics are frozen. Any new observability must be v2 and gated.
- **L3 Parity Rule**: Changes to `rcx_pi/selfhost/` or `mu/` MUST be mirrored in `mu/host/js/eval_step.js`.
  - Run `node mu/host/js/eval_step.js` to verify all JS tests pass
  - Run `./tools/check_js_debt.sh` to verify JS debt markers match Python
  - Run `./tools/contraband_js.sh` to verify no forbidden patterns (determinism, purity)
  - Run `./tools/ast_police_js.sh` to catch JS patterns that bypass grep
  - Run `./tools/check_test_theater_js.sh` to catch vacuous JS assertions
  - Run `./tools/seed_police.sh` to verify seed integrity and no host leakage
  - New seeds must be loaded in both Python and JavaScript
  - Parity vectors must pass on both substrates before merge
- **Pre-commit doc review**: Before committing changes to `rcx_pi/`, `prototypes/`, or `mu/`:
  1. Read relevant docs in `docs/` (e.g., EVAL_SEED.v0.md, DeepStep.v0.md)
  2. Update docs if implementation differs from spec
  3. Update TASKS.md status if completing/progressing items
  4. Verify JS parity if projection behavior changed
- **Agent runbook**: Agent usage follows `docs/agents/AgentRunbook.v0.md` (trigger map, gate rules, and evidence requirements)
- **Roadmap rule**: Documents in `roadmap/` define SEQUENCE and DESIGN only.
  - Current state lives in STATUS.md; authorization lives in TASKS.md
  - Gate completion updates TASKS.md (Ra/NEXT/VECTOR), not roadmap docs
  - Draft specs live in `roadmap/`; approved specs migrate to `docs/core/`
  - See `roadmap/MANIFEST.md` for reading order and linking rules

---

## Promotion Criteria (Non-Negotiable)

- **SINK → VECTOR**: Item must have a clear semantic question to answer. A design doc must be written before any implementation. Promotion must be explicit and documented in this file.
- **VECTOR → NEXT**: Design doc must be complete and reviewed. Semantics must be locked. Implementation scope must be bounded and testable. Observability must precede mechanics.
- Promotion is never implicit. Moving an item between sections requires updating this file with rationale.
- **PR rule**: Any PR that implements a VECTOR/SINK item without an explicit promotion note in this file must be rejected.
- No implementation work may begin on VECTOR items. VECTOR is design-only.
- No SINK item may advance without answering: "What semantic question does this resolve?"

---

## Ra (Resolved / Merged)

Items here are implemented and verified under current invariants. Changes require explicit promotion through VECTOR and new tests. Completed NOW/NEXT items are archived here.

- Deterministic trace core (v1) complete
- Replay semantics frozen (v1)
- Entropy sealing contract in place
- Golden fixtures in place
- Replay gate + CI enforcement in place
- Rust replay acceleration bit-for-bit compatible
- v2 trace schema + observability events (RCX_TRACE_V2=1)
- Stall/Fix execution semantics v0 (RCX_EXECUTION_V0=1)
- ExecutionEngine + value_hash(); motif serialization (_motif_to_json) is test infrastructure only
- Record Mode v0 (execution → trace for stall/fix events)
- Minimal Native Execution Primitive doc (Boundary Question answered)
- v2 replay validation (validate_v2_execution_sequence)
- Anti-theater guardrails:
  - `--print-exec-summary` CLI flag + `execution_summary_v2()` pure helper
  - `test_cli_print_exec_summary_end_to_end` (subprocess CLI test)
  - `tools/audit_exec_summary.sh` (non-test reality anchor)
- Trace Reading Primer (`docs/TraceReadingPrimer.v0.md`)
- Record→Replay Gate (`test_record_replay_gate_end_to_end`)
- Flag Discipline Contract (`docs/Flags.md`)
- Consume execution.fix from trace (true cycle replay)
- Closure-as-termination fixture family (`stall_at_end.v2.jsonl`, `stall_then_fix_then_end.v2.jsonl`)
- IndependentEncounter pathological fixtures + tests
- Recurrence spec stress-test harness (`tests/test_recurrence_spec_v0.py`)
- CI audit gate (`tools/audit_all.sh` + `.github/workflows/audit_all.yml`)
- Closure Evidence reporting flag + CLI test (`--print-closure-evidence`, `closure_evidence_v2()`)
- Rule Motif Observability v0 (`rcx_pi/rule_motifs_v0.py`, `rules --print-rule-motifs`, 11 CLI tests)
- Rule Motif Validation Gate v0 (`validate_rule_motifs_v0()`, `rules --check-rule-motifs`, 16 CLI tests)
- Trace canon helper v1 (`canon_jsonl()`, 7 tests in `test_trace_canon_v1.py`)
- Second Independent Encounter v0 (stall memory tracking, closure signal detection, 25 tests)
- Closure Evidence Events v0 (design complete, `--print-closure-evidence` CLI, `closure_evidence_v2()` helper)
- Recurrence Spec v0 (stress test harness, 18 tests in `test_recurrence_spec_v0.py`, 4 fixtures)
- Bytecode VM v0/v1a/v1b — **ARCHIVED** (superseded by kernel + seeds approach)
  - Code: `rcx_pi/bytecode_vm.py` (legacy, not maintained)
  - Docs: `docs/archive/bytecode/` (archived)
- Mu Type v0 (`rcx_pi/mu_type.py`, `docs/MuType.v0.md`, 58 tests)
- Structural Purity Guardrails v0 (`docs/StructuralPurity.v0.md`, 32 additional tests):
  - `has_callable()`, `assert_no_callables()`, `assert_seed_pure()`
  - `assert_handler_pure()`, `validate_kernel_boundary()`
  - `tools/audit_semantic_purity.sh` extended with checks 9-11
- RCX Kernel Phase 1 (`rcx_pi/kernel.py`, `docs/RCXKernel.v0.md`, 47 tests)
- EVAL_SEED v0 (`rcx_pi/eval_seed.py`, `docs/EVAL_SEED.v0.md`, 125 tests):
  - Core operations: `match`, `substitute`, `apply_projection`, `step`
  - Only special form: `{"var": "x"}` (variable binding)
  - Kernel handlers: step, stall, init
  - Answer: EVAL_SEED is tractable (~200 lines)
  - Adversary tests: 43 attack tests in `test_eval_seed_adversary.py`
- Verification Agent Infrastructure (`tools/agents/`):
  - Verifier agent: read-only audit against North Star invariants
  - Adversary agent: red team attack testing
  - PR verification reminder workflow (auto-comment on sensitive file changes)
  - RATCHET debt policy: threshold can only decrease, never increase
- RCX Kernel Phase 4-5: Algorithmic Self-Hosting (L1) Done:
  - Phase 4a: `match_mu()` as Mu projections (`mu/substrate/match.v1.json`, 23 parity tests)
  - Phase 4b: `subst_mu()` as Mu projections (`mu/substrate/subst.v1.json`, 17 parity tests)
  - Phase 4d: Integration tests (67 total: 28 parity + 27 grounding + 12 fuzzer)
  - Phase 5: `step_mu()` uses match_mu + subst_mu (33 tests: 22 parity + 11 self-hosting)
  - `tests/structural/test_apply_mu_grounding.py` - direct `step()` execution tests
  - `tests/test_apply_mu_fuzzer.py` - Hypothesis property-based tests
- Self-Hosting Security Hardening (PR #149):
  - Thread-safe step budget: `threading.local()` for concurrent execution safety
  - Cycle detection in `normalize_for_match()` and `denormalize_from_match()`
  - Global projection step budget: `_ProjectionStepBudget` class (50,000 step limit)
  - Resource exhaustion guardrails: MAX_MU_DEPTH=300, MAX_MU_WIDTH=1000
  - Comprehensive fuzzer tests (`tests/test_selfhost_fuzzer.py`, 53 tests, 10,000+ examples):
    - `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
    - `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
    - `TestHostileUnicodeHandling`: emoji, RTL, zero-width, homoglyphs
    - `TestNearLimitStress`: width 900-1000, depth 190-200
  - Budget exhaustion tests: nested calls, thread isolation
  - Empty variable name rejection (parity with eval_seed.py)
- Package Reorganization (PR #145):
  - Core self-hosting files moved to `rcx_pi/selfhost/` subpackage
  - Re-export stubs at original locations for backward compatibility
  - Audit script updated to support both layouts
  - Files: mu_type.py, kernel.py, eval_seed.py, match_mu.py, subst_mu.py, step_mu.py
- Comprehensive Debt Tracking (PR #155):
  - All ~289 LOC semantic debt now marked with `@host_*` decorators
  - DEBT_THRESHOLD updated: 14 → 23 (17 tracked + 5 AST_OK + 1 review)
  - Design decisions documented (empty collection normalization, head/tail collision)
  - 10 new tests for edge cases (TestMatchParityHeadTailCollision, TestMatchParityEmptyCollections)
- QoL Infrastructure (PRs #131+):
  - Agent reports as PR comments (verifier, adversary, expert, structural-proof)
  - Debt dashboard (`tools/debt_dashboard.sh`)
  - Pre-commit local checks (`tools/pre-commit-check.sh`)
  - Projection test coverage (`rcx_pi/projection_coverage.py`)
  - Agent memory across sessions (`tools/agent_memory.py`)
  - Trace visualization (`tools/trace_viewer.py`)
- Seed Integrity Verification (PR #157):
  - SHA256 checksum verification for seed files (match.v1.json, subst.v1.json)
  - Structure validation (meta, projections keys, required fields)
  - Projection ID verification (expected IDs present, wrap is last)
  - 27 tests in `tests/test_seed_integrity.py`
  - Security foundation: seeds now verified on load (adversary finding closed)
- Phase 6a: Lookup as Mu Projections (PR #158):
  - Added `subst.lookup.found` and `subst.lookup.next` projections to subst.v1.json
  - Lookup is now structural: pattern matching with non-linear vars (same name binds same value)
  - Removed 2 `@host_builtin` decorators from subst_mu.py
- Phase 6b: Classification as Mu Projections:
  - Created `mu/utilities/classify.v1.json` with 6 projections for linked list classification
  - Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
  - `denormalize_from_match()` now uses `classify_linked_list()` instead of `is_dict_linked_list()`
  - Classification distinguishes dict-encoding (all kv-pairs with string keys) from list-encoding
  - Handles edge cases: nested dicts in key position, circular references, primitives
  - Removed 2 `@host_builtin` decorators from match_mu.py (is_kv_pair_linked, is_dict_linked_list)
  - DEBT_THRESHOLD: 21 → 19 (ratchet tightened)
  - 26 new tests in `tests/test_classify_mu.py`
- Boot0 Architecture v0.4 (`docs/core/Boot0Architecture.v0.md`) - 9-agent reviewed 2026-01-31:
  - Hex0-inspired staged bootstrap design: Boot0 → Boot1 → Boot2
  - 5 irreducible bootstrap primitives: eval_step, mu_equal, max_steps, stack_guard, projection_loader
  - Boot0=structural, Boot1=none, Boot2=kernel validation boundaries
  - v0.4: Added "stable semantics, shrinking substrate", JSON as Phase 0 format, explicit handshake ABI, security invariants, L3 parity contract
  - Design COMPLETE, implementation DEFERRED per 9-agent Advisor recommendation
  - L3 is complete; Boot0 extraction can wait until L4 research drives it
- mu_equal Phase 1/2 Review (9-agent dialectic 2026-01-31):
  - **Phase 1 DONE**: Centralized binding conflict checks to call mu_equal (2-line fix in eval_seed.py)
  - **Phase 2 DEFERRED**: Structural recursion to replace json.dumps - NOT WORTH IT
  - Reason: json.dumps IS structural equality for JSON data. Mu IS JSON by definition.
  - 9-agent consensus: "Cosmetic change, not semantic. Both use host mechanisms."
  - Structural-proof: "Cannot find ONE example where json.dumps gives wrong answer"
  - Expert: "4 lines → 40-60 lines with identical semantics"
  - L4 research question remains open: "Can mu_equal become projections?"
  - Parity fuzzer created: `tests/test_mu_equal_parity_fuzzer.py` (13 tests, 500+ inputs)
- Testing Tier System (2026-01-28):
  - 9-agent review resolved fuzzer hang issue (rejected circuit breaker, chose Option B)
  - Tier 1: `audit_fast.sh` (~3 min) - Core tests for local iteration
  - Tier 2: `audit_all.sh` (~5-8 min) - Core + Fuzzer for CI
  - Tier 3: `tests/stress/` (~10+ min) - Deep edge cases for comprehensive validation
  - Fuzzer settings standardized: `max_depth=3` (generators AND call sites), `deadline=5000`
  - Files standardized (6): test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py, test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py
  - Call site overrides fixed: 29 instances of `max_depth=4` → `max_depth=3` across 4 files
  - Hypothesis profiles: `HYPOTHESIS_PROFILE=dev` for fast local fuzzer runs (50 examples)
  - See STATUS.md "Testing Tiers" for current config (single source of truth)
  - DEBT_THRESHOLD: 23 → 21 (ratchet tightened)
  - `resolve_lookups()` Python function deprecated (kept for backward compat)
  - 37 subst parity tests pass with structural lookup
- Phase 6c: Normalization as Iterative + Type Tags:
  - `normalize_for_match()`: recursive → iterative with explicit stack
  - `denormalize_from_match()`: recursive → iterative with explicit stack
  - Removed 2 `@host_recursion` decorators from match_mu.py
  - Removed 2 `# AST_OK: bootstrap` comments (recursive comprehensions eliminated)
  - isinstance() at Python↔Mu boundary is scaffolding, not semantic debt
  - Type tags (`_type: "list"` or `_type: "dict"`) resolve list/dict ambiguity
  - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
  - Security: `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` function
  - 24 new property-based fuzzer tests (`test_type_tags_fuzzer.py`)
  - All 1020 self-hosting tests pass
- Expert Review Cleanup (PR #163):
  - Deleted `resolve_lookups()` dead code from subst_mu.py (~47 lines)
  - Updated "Phase 3" comments to "BOOTSTRAP" in eval_seed.py
  - DEBT_THRESHOLD: 15 → 14 (ratchet tightened after dead code removal)
  - All 1038 tests pass, 53 fuzzer tests pass
- Phase 6d: Iterative Validation + Code Cleanup (PR #165):
  - `_check_empty_var_names()` converted to iterative with explicit stack
  - Reclassified `bindings_to_dict`/`dict_to_bindings` as boundary scaffolding
  - Deleted `lookup_binding()` dead code from subst_mu.py (~25 lines)
  - Removed unused `bindings` parameter from `run_subst_projections()`
  - Removed unused `from typing import Any` imports from match_mu.py, subst_mu.py
  - Removed deprecated `_seen` parameter from `normalize_for_match()`, `denormalize_from_match()`
  - Added 18 tests for empty var name rejection (parity between match_mu and subst_mu)
  - DEBT_THRESHOLD: 14 → 11 (ratchet tightened: 8 tracked + 3 AST_OK)
  - All 1036 tests pass, all 6 agents APPROVE for Phase 7 readiness
- Kernel Loop Fuzzer Tests (pre-Phase 7):
  - Added 11 property-based tests for apply_mu, step_mu, run_mu
  - TestApplyMuDeterminism: 3 tests (determinism, var pattern, literal match)
  - TestApplyMuParity: 1 test (apply_mu == apply_projection)
  - TestStepMuDeterminism: 3 tests (determinism, empty projections, stall idempotent)
  - TestStepMuParity: 2 tests (step_mu == step, first-match-wins)
  - TestRunMuDeterminism: 2 tests (determinism, immediate stall)
  - 3000+ random examples stress-test kernel loop stability
  - Closes fuzzer gap identified by agents before Phase 7
- rcx_engine.v1.json Test Coverage (2026-02-03):
  - Created `tests/fixtures/rcx_engine_vectors.json` - 7 test vectors
  - Created `tests/test_rcx_engine_parity.py` - 15 tests
  - All 6 engine projections now tested (grounding agent finding addressed)
  - Note: rcx_engine has `status: design_only` - projections tested but not in production

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (empty by design; only populated if an invariant is broken)

*(No active items - all invariants intact)*

---

## NEXT (short, bounded follow-ups)

### Phase 7: Meta-Circular Kernel (L2 Operational Self-Hosting)

**Promoted from VECTOR:** 2026-01-27
**Rationale:** All 7 agents APPROVE. Design complete (MetaCircularKernel.v0.md v0.2). All blockers resolved.

**Goal:** Replace Python for-loop in `step_mu()` with structural kernel projections.

**Sub-phases:**

- [x] **Phase 7a: Kernel Projections Seed** (DONE 2026-01-28)
  - Created `mu/substrate/kernel.v1.json` with 7 projections (in mu/substrate/)
  - 30 manual trace tests pass (success, failure, empty projections)
  - Projection order regression tests pass

- [x] **Phase 7b: Match/Subst Context Passthrough** (DONE 2026-01-28)
  - Created match.v2.json with `_match_ctx` passthrough + match.fail catch-all
  - Created subst.v2.json with `_subst_ctx` passthrough
  - Parity tests pass (v2 seeds == v1 behavior)

- [x] **Phase 7c: Integration Testing** (DONE 2026-01-28)
  - 20 integration tests: kernel → match → subst → kernel
  - Context preservation verified through full cycles
  - Security: domain data can't forge `_mode` (underscore prefix)

**Phase 7d Blockers (from agent review 2026-01-28):**

All blockers resolved 2026-01-28:

1. [x] **SECURITY: Call validate_kernel_projections_first() in production** (adversary)
   - Fixed: Added call in step_mu() at line 154
   - Domain projections can no longer run before kernel

2. [x] **TESTING: Add v2 parity tests** (grounding)
   - Fixed: Created test_match_v2_parity.py (19 tests)
   - Fixed: Created test_subst_v2_parity.py (18 tests)
   - 37 new parity tests verify v2 preserves v1 behavior

3. [x] **DEBT: Track projection_runner iteration debt** (advisor)
   - Fixed: Added "# @host_iteration" marker in projection_runner.py
   - Fixed: Updated debt_dashboard.sh to count comment markers
   - Debt now accurately shows 15 (was 14)

4. [x] **DEBT: Update target to phased approach** (structural-proof, advisor)
   - Fixed: Updated TASKS.md with 7d-1, 7d-2, 7d-3 sub-phases
   - Fixed: Updated STATUS.md with phased debt reduction plan (15→14→13→12)
   - Note: Original target was 9, revised to 12 per structural-proof (run_mu stays as L3 boundary)

- [x] **Phase 7d-1: Wire step_mu to kernel** - DONE 2026-01-28 (L2 PARTIAL)
  - [x] Modify `step_mu()` to call structural kernel (step_kernel_mu)
  - [x] Call validate_kernel_projections_first() for security
  - [x] Added helpers: list_to_linked, normalize_projection, load_combined_kernel_projections
  - [x] Parity tests: 106 core tests pass (existing + fuzzer)
  - [x] 7-agent review revealed: execution loop still Python (honest assessment)
  - [x] Added @host_iteration to step_kernel_mu (honest debt tracking)
  - Note: Behavioral change - unbound variables now stall instead of raising KeyError
  - **Outcome:** Projection SELECTION is structural (linked-list cursor). Projection EXECUTION is Python.
  - **Debt:** 15 → 15 (moved location, not eliminated)

- [x] **Phase 7d-2: Migrate projection_runner** - CLOSED (not applicable per Phase 8 decision)
  - Phase 8 decided: "Option 1 (accept as bootstrap primitive)"
  - The for-loop is accepted as irreducible - no migration needed
  - L2 FULL achieved via explicit acceptance

- [x] **Phase 7d-3: Eliminate projection_runner iteration** - CLOSED (not applicable per Phase 8 decision)
  - Same as 7d-2: loop is accepted as bootstrap primitive
  - If L4 pursues CPS/trampolining, new tasks will be created

**Success criteria:**
- [x] `mu/substrate/kernel.v1.json` exists with 7 projections
- [x] Manual trace tests pass for success/failure/empty cases
- [x] Match/subst context passthrough tests pass
- [x] Phase 7d blockers resolved (security, testing, debt tracking) - 2026-01-28
- [x] v2 parity tests pass (37 tests: 19 match + 18 subst) - 2026-01-28
- [x] Doc inconsistencies fixed (all .md files reference STATUS.md for debt) - 2026-01-28
- [x] Kernel projections pass parity tests with Python `step_mu` - 2026-01-28 (106 tests)
- [x] step_mu delegates to step_kernel_mu (structural selection) - 2026-01-28
- [x] All 1293+ existing tests still pass - 2026-01-28
- [x] L2 PARTIAL achieved: selection structural, execution Python - 2026-01-28
- [x] L2 FULL achieved: PARTIAL + explicit acceptance of for-loop as bootstrap primitive - 2026-01-28
- [x] Debt floor: 12 (irreducible bootstrap substrate) - no further reduction without L4 architecture

**Recommended fuzzer additions (from agent review):**
- [x] Add fuzzer tests for kernel projection ordering (500+ examples) - 2026-02-01
- [x] Add fuzzer tests for mode transition completeness (500+ examples) - 2026-02-01
- [x] Add fuzzer tests for context passthrough stress (500+ examples) - 2026-02-01
- [x] Add property-based tests for _step/_projs field fuzzing (500+ examples) - 2026-02-01
- [x] Add depth boundary fuzzing (95-105 range) - 2026-02-01

**Debt status**: See `STATUS.md` for current counts and threshold.

---

### Phase 8: Bootstrap Primitives + Mechanical Kernel (DONE 2026-01-28)

**Goal:** Document irreducible primitives, simplify kernel loop to mechanical operation.

- [x] **Phase 8a: Bootstrap Primitives** (DONE 2026-01-28)
  - Created `docs/core/BootstrapPrimitives.v0.md`
  - Marked 5 primitives: eval_step, mu_equal, max_steps, stack_guard, projection_loader
  - 36 tests in `test_bootstrap_primitives.py`, 18 fuzzer tests

- [x] **Phase 8b: Mechanical Kernel** (DONE 2026-01-28)
  - Added `is_kernel_terminal()` and `extract_kernel_result()` helpers
  - Simplified loop to ~15 lines (was ~35)
  - Fixed empty container type preservation
  - 31 tests + 12 grounding tests

- [x] **Phase 8b Security Hardening** (DONE 2026-01-28, 9-agent reviewed)
  - Added KERNEL_RESERVED_FIELDS (12 fields) with deep validation
  - Changed depth guard to fail CLOSED (raises ValueError at depth > 100)
  - Added `_step` and `_projs` to reserved fields (kernel entry format protection)
  - 35 tests in `test_step_mu_kernel_integration.py`
  - 844 total tests passing

**Next:** L3 Substrate Portability + EngineNews Demo (5-step plan from 7-agent review)

### L3 + EngineNews Implementation Plan

**Goal:** Prove projections are substrate-portable AND demo EngineNews on RCX

**Sequence (7-agent reviewed, 2026-01-30):**

| Step | Task | Status | Effort |
|------|------|--------|--------|
| 1 | Fix JS security gaps | **DONE** | ~80 LOC (KERNEL_RESERVED_FIELDS, type tag, dict kv-pair fix) |
| 2 | Create cross-substrate parity tests | **DONE** | ~120 LOC + 20 vectors (`tests/test_parity_python.py`) |
| 3 | Phase 8d in Python (trace model) | **DONE** | ~80 LOC + 14 tests (`tests/test_structural_trace.py`) |
| 4 | Port trace to JS POC | **DONE** | ~80 LOC + 5 tests |
| 5 | EngineNews in Python | **DONE** | `mu/closures/recurrence.v1.json` (9 projections) |
| 6 | EngineNews in JS (L3 parity) | **DONE** | JS POC v5 with EngineNews tests |
| 7 | ACTUAL cross-substrate verification | **DONE** | JSON API + actual output comparison (9-agent Round 3 fix, 2026-01-31) |

---

### Step 1: Fix JS Security Gaps ✅ DONE

**Location:** `mu/host/js/eval_step.js`

**Completed (2026-01-30):**
- [x] Add `KERNEL_RESERVED_FIELDS` validation (12 fields)
- [x] Add `validate_type_tag()` for type injection prevention
- [x] Add deep validation at kernel entry point
- [x] Fix dict kv-pair normalization parity (critical bug)

---

### Step 2: Cross-Substrate Parity Tests ✅ DONE

**Goal:** Prove JS matches Python BEFORE adding features

**Completed (2026-01-30):**
- [x] Created `tests/fixtures/parity_vectors.json` with 20 parity + 3 security vectors
- [x] Created `tests/test_parity_python.py` (20 parity + 3 security tests)
- [x] JS POC passes all 20 parity vectors
- [x] Added semantic checks: direct equality + structural normalization

---

### Step 3: Phase 8d - EngineNews Trace Model (Python) ✅ DONE

**Goal:** Structural trace accumulation for EngineNews Rule 2.2 (closure-on-second-demand)

**Completed (2026-01-30):**
- [x] `run_mu_structural()` in `step_mu.py` - returns Mu-compatible trace format
- [x] Trace is Mu linked-list: `{head: entry, tail: {head: entry, tail: ...}}`
- [x] Each entry: `{step, state, projection}` (projection=None for stall)
- [x] `list_to_linked()` helper for Python list → Mu linked-list
- [x] 14 tests in `tests/test_structural_trace.py`:
  - Trace format tests (linked-list structure, required fields)
  - Stall detection tests (projection=None for unmatched)
  - Closure detection capability tests (oscillation captured)

**EngineNews Alignment:**
- Stall detection: `mu_equal(before, after)` → exists (primitive)
- Fix operation: domain projections → exists (structural)
- Promote: kernel selection → exists (kernel.v1)
- **Closure**: trace accumulation → **DONE** (run_mu_structural)

---

### Step 4: Port Trace to JS POC ✅ DONE

**Completed (2026-01-30):**
- [x] `runStructural()` in `mu/host/js/eval_step.js`
- [x] Returns `{result, trace, stall, steps}` matching Python
- [x] Trace as Mu linked-list format
- [x] 5 structural trace tests pass in JS

---

### Step 5: EngineNews Demo (CRITICAL: Must Be Structural) ✅ DONE

**GATES (from 7-agent review 2026-01-30):**
- [x] Design doc: `docs/core/EngineNewsStructural.v0.md` (explicit criteria)
- [x] Property-based fuzzer: `tests/test_structural_trace_fuzzer.py` (23 tests)
- [x] CRITICAL_TEST_FILES updated: structural trace fuzzer protected
- [x] Implementation: `mu/closures/recurrence.v1.json` (9 projections)
- [x] Parity tests: `tests/test_recurrence_parity.py` (24 tests)
- [x] Fuzzer tests: `tests/test_recurrence_fuzzer.py` (property-based)

**REQUIREMENT:** EngineNews rules MUST be expressed as Mu projections, NOT Python code.

**Why this matters (from 7-agent review):**
- If EngineNews runs via Python loops/logic, emergence might be a Python artifact
- For structural honesty, closure detection must be pattern matching on traces
- The bootstrap (eval_step, mu_equal) is acceptable - the LOGIC must be projections

**Implementation (COMPLETE):**

1. Created `mu/closures/recurrence.v1.json` with 9 projections:
   - `enginenews.init` - Entry point: _detect_closure -> internal state
   - `enginenews.end_of_trace` - End of trace (null) -> no closure
   - `enginenews.check_state_stall` - Extract state from stall entry
   - `enginenews.check_state_maxsteps` - Extract state from max_steps entry
   - `enginenews.check_state` - Extract state from normal entry
   - `enginenews.found_in_seen` - State in seen-set -> closure detected!
   - `enginenews.not_in_head` - State not in head -> check tail
   - `enginenews.not_found` - State not found -> add and advance
   - `enginenews.unwrap` - Extract final closure evidence

2. Key design decision: **Non-linear patterns for state equality**
   - `enginenews.found_in_seen` uses `{"var": "state"}` twice in pattern
   - eval_seed.match() binding conflict detection enforces equality
   - This is bootstrap (like Forth's NEXT), not semantic debt

3. Success criteria (ALL MET):
   - [x] `recurrence.v1.json` exists with 9 projections
   - [x] EngineNews projections run via eval_seed.step(), NOT Python loops
   - [x] Closure detection is structural: projection matches trace pattern
   - [x] Seen-set is Mu linked-list, NOT Python set
   - [x] No Python `if/for/while` in closure detection path (only in bootstrap)
   - [x] 7-agent review: All agents APPROVE

**The demonstration (COMPLETE):**
- Same projections (kernel.v1 + match.v2 + subst.v2 + enginenews.v1)
- Same input (EngineNews workload)
- Same trace output
- Same closure detection
- **Python:** Full EngineNews support ✅
- **JavaScript:** Full EngineNews support ✅ (v5, 2026-01-30)

**This proves:** All meaning is in projections. Host provides only mechanical execution. Emergence is structural, not a Python artifact. L3 Substrate Portability is COMPLETE.

---

### Step 6: Operator Exhaustion (Rule 3.1) ✅ COMPLETE

**Completed:** 2026-02-02
**Design Doc:** `docs/core/OperatorExhaustion.v0.md`

**Goal:** Detect when operators are exhausted (Rule 3.1) - τ transitions to frozen state.

**Implementation:**
- Created `mu/closures/exhaustion.v1.json` with 11 projections (separate seed, not added to enginenews)
- Three-phase state machine: find_tau → scan → check_frozen → terminal
- Non-linear patterns for equality (same var twice enforces binding conflict detection)
- First-match-wins ordering (scan_same before scan_different, frozen_found before frozen_check_tail)
- Frozen list as Mu linked-list, NOT Python set

**Projections in exhaustion.v1.json:**
- `exhaust.init_null` - No tau_step → continue (no exhaustion possible)
- `exhaust.init` - Start find phase with tau_step
- `exhaust.find_match` - Found tau_step in trace
- `exhaust.find_continue` - Keep searching for tau_step
- `exhaust.find_not_found` - tau_step not in trace → continue
- `exhaust.scan_same` - Same operator, keep scanning (non-linear pattern)
- `exhaust.scan_different` - Different operator → not exhausted
- `exhaust.scan_end` - End of trace, check frozen list
- `exhaust.frozen_found` - Operator already frozen (non-linear pattern)
- `exhaust.frozen_check_tail` - Continue searching frozen list
- `exhaust.do_freeze` - Freeze the operator

**Success criteria (ALL MET):**
- [x] Design doc reviewed by all 9 agents (2026-02-02)
- [x] `mu/closures/exhaustion.v1.json` created with 11 projections (2026-02-02)
- [x] Exhaustion detection is structural (projections, not Python)
- [x] Parity tests for Python (17 tests in `test_exhaustion_parity.py`)
- [x] JavaScript loads exhaustion.v1.json (47 total projections)
- [x] Property-based fuzzer tests (10 tests in `test_exhaustion_fuzzer.py`)
- [x] Cross-substrate parity vectors verified (6 cross-substrate tests pass)
- [x] KERNEL_RESERVED_FIELDS updated to 20 fields (Python and JS match)
- [x] Automated parity test verifies Python/JS reserved fields match

---

### Step 7: Bootstrap-Structural Bridge (Non-Linear Pattern Support)

**Promoted from VECTOR:** 2026-02-02
**Rationale:** All 9 agents approved with security hardening applied. Design complete. Semantics locked (22 test vectors).

**Design Doc:** `docs/core/BootstrapStructuralBridge.v0.md`
**Location:** `mu/bridge/bootstrap_structural.v1.json`

**Goal:** Enable recurrence.v1 and exhaustion.v1 to run through meta-circular kernel (step_kernel_mu) instead of bootstrap (eval_seed).

**Why this matters:**
- Currently, recurrence.v1 and exhaustion.v1 use non-linear patterns (same var twice for equality)
- Non-linear patterns work via eval_seed.match() binding conflict detection (BOOTSTRAP)
- match.v2.json is "linear only" - no binding conflict projections
- Result: These seeds work but CANNOT run through step_kernel_mu
- This bridge adds binding conflict detection as projections

**Implementation plan (7 gates from Advisor):**
1. [x] Gate 1: Create `mu/bridge/` directory structure (2026-02-02)
2. [x] Gate 2-4: Implement bridge projections (5 projections in bootstrap_structural.v1.json) (2026-02-02)
3. [x] Gate 5: Wire step_mu to use match.v2 + bootstrap_structural bridge (2026-02-02)
4. [x] Gate 6: Update recurrence.v1 and exhaustion.v1 to META_CIRCULAR (2026-02-02)
5. [x] Gate 7: Cross-substrate parity verification (JS port) (2026-02-03)

**Projections (5 in bridge, combined with match.v2 at runtime):**
- `bridge.var.check_existing` - Entry: start lookup for variable binding
- `bridge.lookup.found_same` - Found binding with same value (non-linear OK)
- `bridge.lookup.found_different` - Found binding with different value → NO_MATCH
- `bridge.lookup.not_found_yet` - Name not at head, continue searching
- `bridge.lookup.not_found` - Name not in bindings, add new binding

**Security hardening (applied 2026-02-02):**
- KERNEL_RESERVED_FIELDS updated: 20 → 24 fields
- Added: `_lookup_name`, `_lookup_value`, `_lookup_bindings`, `_original_bindings`
- Python and JS in parity (both have 24 fields)

**Test vectors (22 total):**
- Linear Parity Tests (5): linear_ok, linear_nested, linear_list, linear_catchall, linear_empty_dict
- Non-Linear Detection Tests (8): nonlinear_same, nonlinear_diff, nested_nonlinear, triple_same, triple_one_diff, nonlinear_list, nonlinear_list_diff, nonlinear_complex
- Edge Cases (4): empty_bindings_first, null_value_binding, empty_list_match, type_mismatch
- Security Vectors (3): reserved_var_ok, lookup_injection, ordering_critical
- Cross-Substrate Parity (3): parity_unicode, parity_float, parity_deep

**9-agent review (2026-02-02):**
| Agent | Verdict |
|-------|---------|
| Verifier | APPROVE |
| Adversary | SECURE |
| Expert | MINIMAL |
| Structural-proof | STRUCTURALLY_SOUND |
| Grounding | ADEQUATELY_GROUNDED |
| Fuzzer | NEEDS_MORE (non-blocking) |
| Translator | MATCHES_INTENT |
| Visualizer | ARCHITECTURALLY_ALIGNED |
| Advisor | READY_FOR_PROMOTION |

**Success criteria:**
- [x] `mu/bridge/bootstrap_structural.v1.json` created with 5 projections (2026-02-02)
- [x] `load_combined_kernel_with_bridge_projections()` wires match.v2 + bootstrap_structural (2026-02-02)
- [x] All 31 bridge test vectors pass (tests/test_bootstrap_structural_bridge.py) (2026-02-02)
- [x] Binding conflict detection is structural (projections, not Python) (2026-02-02)
- [x] recurrence.v1 and exhaustion.v1 declared META_CIRCULAR (Gate 6) (2026-02-02)
- [x] Execution path verification: bridge projections ACTUALLY fire (2026-02-03)
  - tests/test_execution_path_verification.py (9 tests)
  - Tests use tracing to prove which projections execute
  - Tests FAIL if bridge projections don't fire (even if behavior correct)
- [x] Cross-substrate parity verified (Python and JS) (Gate 7) (2026-02-03)
- [x] All tests pass (1622 fast audit, 2446 full audit) (2026-02-03)

**Current architecture (2026-02-03):**
- Bridge projections VERIFIED to fire for non-linear pattern matching
- Algorithm execution (recurrence, exhaustion) uses Python match/substitute
  - Reason: Structural normalization converts dict→linked-list, breaking algorithm state format
  - This is documented scaffolding, not hidden debt
- Two execution layers:
  1. Structural layer: match.v2 + bridge (for pattern matching with non-linear support)
  2. Practical layer: Python match/substitute (for algorithm execution)
- Path to true meta-circular algorithm execution documented in BootstrapStructuralBridge.v0.md

---

**Cross-substrate verification (9-agent Round 3 fix, 2026-01-31):**
- Previous tests just parsed strings from JS stdout (theater)
- Now runs SAME 20 parity vectors through BOTH substrates via JSON API
- Compares actual outputs, handles int/float normalization
- See `tests/test_js_parity_automated.py::test_actual_cross_substrate_comparison`

**7-Agent Review Results (2026-01-30):**
| Agent | Verdict | Key Finding |
|-------|---------|-------------|
| Verifier | APPROVE | All 12 North Star invariants maintained |
| Adversary | SECURE | Non-linear pattern concern RESOLVED (binding conflict detection works) |
| Expert | MINIMAL | Code appropriately sized |
| Structural-proof | PROVEN | All 4 structural claims verified |
| Grounding | GROUNDED | All claims have executable tests |
| Fuzzer | DESIGN COMPLETE | Comprehensive fuzzer tests provided |
| Advisor | RESOLVED | Architecture is sound |

---

## VECTOR (design-only; semantics locked, no implementation allowed)

**Active designs:**
- Debt Categories v0 (`docs/core/DebtCategories.v0.md`) - Scaffolding vs semantic debt distinction
- Projection Indexing - Preprocess projections into structural trie/decision-tree for O(log N) matching instead of O(N) linear scan. Index is Mu data (structural). **Promotion criteria:** Profile real workloads first; if projection matching is >50% of runtime, promote to NEXT.

**Completed (moved to Ra):**
- ~~Operator Exhaustion v0~~ (`docs/core/OperatorExhaustion.v0.md`) - **MOVED TO Ra** (IMPLEMENTED 2026-02-02)
  - Step 6 complete: 11 projections in `mu/closures/exhaustion.v1.json`
  - 27 tests (17 parity + 10 fuzzer), cross-substrate parity verified

**Promoted to NEXT:**
- Meta-Circular Kernel v0 (`docs/core/MetaCircularKernel.v0.md`) - **Promoted 2026-01-27**
  - All 7 agents APPROVE (verifier, adversary, expert, structural-proof, grounding, fuzzer, advisor)
  - Design complete: 7 kernel projections, linked-list cursor, context passthrough
  - See NEXT section for Phase 7 implementation plan

**Completed designs (now in Ra):**
- RCX Kernel v0 (`docs/core/RCXKernel.v0.md`)
- Structural Purity v0 (`docs/core/StructuralPurity.v0.md`)
- Self-Hosting v0 (`docs/core/SelfHosting.v0.md`)
- EVAL_SEED v0 (`docs/core/EVAL_SEED.v0.md`)
- EngineNews Structural v0 (`docs/core/EngineNewsStructural.v0.md`) - Step 5 closure detection
- Operator Exhaustion v0 (`docs/core/OperatorExhaustion.v0.md`) - Step 6 operator freeze
- Second Independent Encounter (`docs/execution/IndependentEncounter.v0.md`)
- Enginenews Spec Mapping (`docs/execution/EnginenewsSpecMapping.v0.md`)
- Closure Evidence Events (`docs/execution/ClosureEvidence.v0.md`)
- Rule-as-Motif (`docs/execution/RuleAsMotif.v0.md`)

**Archived (superseded):**
- Bytecode VM v0/v1 → `docs/archive/bytecode/`

---

## SINK (ideas parked; may not advance without explicit promotion decision)

- Multi-value/concurrent execution
- Performance-first optimizations
- ~~Full VM bootstrap / meta-circular execution~~ → Promoted to VECTOR #14 (RCX Kernel v0)
- Projection caching optimization (post-Phase 8) - cache normalized projections for repeated use; use content-based hash, NOT id(). From withdrawn KernelSeedRealignment.v0.md.
