# Changelog

All notable changes to RCX are documented in this file.

## 2026-02-02

### Architectural Gap: match.v2 / Non-Linear Pattern Incompatibility

**Problem (discovered in 9-agent review):** match.v2.json states "Linear patterns only (no conflict detection)", but enginenews.v1.json and exhaust.v1.json rely on non-linear patterns (same variable twice for equality). These seeds work via bootstrap (eval_seed) but CANNOT run through the meta-circular kernel.

**Impact:** Seeds could not be declared META_CIRCULAR. Tests passed via bootstrap, hiding architectural incompatibility.

**Solution:**
- Added North Star #14 (execution layer declaration) and #15 (true self-hosting path)
- Added Cross-Seed Compatibility Check to AgentGuardrails.v0.md
- Updated enginenews.v1.json and exhaust.v1.json with `"execution_layer": "BOOTSTRAP"`
- Created VECTOR item for match.v3 (non-linear pattern support)
- Created design doc `docs/core/MatchV3NonLinear.v0.md`

**Files:**
- `TASKS.md` - Added North Star #14, #15; added match.v3 to VECTOR
- `docs/agents/AgentGuardrails.v0.md` - Added Cross-Seed Compatibility Check section
- `seeds/enginenews.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `seeds/exhaust.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `docs/core/MatchV3NonLinear.v0.md` - Design doc for non-linear pattern support

**Lesson Learned:** 9-agent review verified correctness but not architectural fit. New guardrails require verifying execution path matches claims, not just that tests pass.

---

### Step 6: Operator Exhaustion (Rule 3.1) - COMPLETE

**Problem:** Need to detect when an operator has been applied continuously since τ was logged without making progress (Rule 3.1 from RCXEngineNew.pdf).

**Solution:**
- Created `seeds/exhaust.v1.json` with 11 projections
- Three-phase state machine: find_tau → scan → check_frozen → terminal
- Non-linear patterns for equality detection (binding conflict detection)
- First-match-wins ordering (scan_same before scan_different)
- Frozen list as Mu linked-list, NOT Python set

**Projections (exhaust.v1.json):**
- `exhaust.init_null`, `exhaust.init` - Entry points
- `exhaust.find_match`, `exhaust.find_continue`, `exhaust.find_not_found` - Find τ phase
- `exhaust.scan_same`, `exhaust.scan_different`, `exhaust.scan_end` - Scan phase
- `exhaust.frozen_found`, `exhaust.frozen_check_tail`, `exhaust.do_freeze` - Freeze phase

**Testing:**
- 17 parity tests in `tests/test_exhaustion_parity.py`
- 10 fuzzer tests in `tests/test_exhaustion_fuzzer.py`
- 6 test vectors in `tests/fixtures/exhaustion_vectors.json`
- 6 cross-substrate tests (Python and JS produce identical results)

**Security:**
- KERNEL_RESERVED_FIELDS updated to 20 (12 kernel + 4 EngineNews + 4 exhaustion)
- Both Python and JavaScript have identical reserved fields
- Automated parity test at `test_js_parity_automated.py::test_python_js_constants_match`

**Files:**
- `seeds/exhaust.v1.json` - 11 projections
- `tests/test_exhaustion_parity.py` - 17 tests
- `tests/test_exhaustion_fuzzer.py` - 10 tests
- `tests/fixtures/exhaustion_vectors.json` - 6 vectors
- `substrates/js/eval_step.js` - Updated with exhaust.v1.json loading
- `rcx_pi/selfhost/seed_integrity.py` - Added exhaust.v1.json checksum
- `docs/core/OperatorExhaustion.v0.md` - Design doc updated to IMPLEMENTED

## 2026-02-01

### Agent Guardrails (Anti-Hallucination Infrastructure)

**Problem:** LLMs can hallucinate plausible-sounding file paths and code snippets. Previous agent outputs weren't verified for evidence.

**Solution:**
- Created `docs/agents/AgentGuardrails.v0.md` - spec requiring FILE:LINE + code evidence
- Created `tools/validate_agent_compliance.py` - regex-based output validator
- Created `tests/tools/test_validate_agent_compliance.py` - 43 tests for validator
- Created `.claude/hooks/validate-agent-compliance.sh` - automatic SubagentStop hook
- Updated all 9 agent prompts with MANDATORY verification protocol section

**Evidence Format (required for all findings):**
```
FINDING: [description]
FILE: /absolute/path
LINES: start-end
CODE:
    [paste from Read tool output]
VERIFIED: Yes
```

**Validator Features:**
- Line ending normalization (handles Windows/Mac/Unix)
- CODE block validation (accepts tabs OR 2+ spaces)
- Hallucination word detection (13 words blocked)
- STATUS.md check (must be read in first 50 lines)

**Files:**
- `docs/agents/AgentGuardrails.v0.md` - specification
- `tools/validate_agent_compliance.py` - validator script
- `tests/tools/test_validate_agent_compliance.py` - 43 tests
- `.claude/hooks/validate-agent-compliance.sh` - automatic hook
- `.claude/settings.json` - hook configuration
- `tools/agents/archive_pre_guardrails/` - archived old prompts

**Agent Model Updates:**
- Expert upgraded from Sonnet to Opus
- Visualizer upgraded from Haiku to Sonnet
- All agents now use Opus (4) or Sonnet (5) - no Haiku

### Additional Fuzzer Tests (9-agent findings)

- Created `tests/structural/test_entropy_budget_enforcement.py` - EntropyBudget.md grounding
- Created `tests/test_denormalize_type_confusion_fuzzer.py` - type confusion attacks
- Created `tests/test_normalize_malformed_fuzzer.py` - malformed structure handling

### Git Tracking

- `.claude/` directory now tracked (agents, hooks, settings.json) - was previously gitignored
- Enables reproducible agent setup across machines

## 2026-01-31

### Cross-Substrate Parity Verification (9-agent Round 3 Fix)

**Problem (Grounding finding):** Previous JS parity tests were "theater" - they just
parsed strings like "0 failed" from stdout. No test actually ran the same input through
both Python and JavaScript and compared the outputs.

**Fixes:**

- **JS JSON API Mode** (`substrates/js/eval_step.js`)
  - Added `--json-api` command line option for machine-readable output
  - Actions: `run_vector`, `run_all_vectors`, `run_enginenews`, `get_constants`
  - Outputs JSON on single line for easy parsing by Python tests
  - Fixed EngineNews e2e test expectations: stall IS a closure (fixed point)

- **Actual Cross-Substrate Comparison** (`tests/test_js_parity_automated.py`)
  - Added `_normalize_for_cross_substrate()` - handles int/float equivalence (JS doesn't distinguish)
  - Added `_cross_substrate_equal()` - compares normalized outputs
  - New `test_actual_cross_substrate_comparison` - runs SAME 20 parity vectors through BOTH substrates
  - New `test_python_js_constants_match` - verifies MAX_DEPTH=300 and KERNEL_RESERVED_FIELDS match

- **Git Tracking** (`.gitignore`)
  - `substrates/js/eval_step.js` now tracked in git (was previously gitignored)
  - Required for CI to run JS parity tests

**Test Results:**
- 13 JS parity tests: PASSED (including actual comparison)
- 2025 functional tests: PASSED
- Cross-substrate parity is now ACTUALLY VERIFIED, not just claimed

**Known Limitation (documented, not a bug):**
- JavaScript doesn't distinguish between integers and floats (0 === 0.0)
- Cross-substrate comparison normalizes all numbers to float for comparison
- Semantically equivalent; only representation differs

## 2026-01-30

### Step 5: EngineNews Structural Closure Detection (COMPLETE)

**Implementation:**
- Created `seeds/enginenews.v1.json` with 9 projections for Rule 2.2 (Closure-on-Second-Demand)
- Projections: init, end_of_trace, check_state_stall, check_state_maxsteps, check_state,
  found_in_seen, not_in_head, not_found, unwrap
- Non-linear patterns for state equality (same variable `{"var": "state"}` twice)
- Seen-set is Mu linked-list, NOT Python set
- All closure detection logic is in projections (DATA), not Python code

**Key Design Decision: Non-linear Patterns**
- `enginenews.found_in_seen` uses `{"var": "state"}` in both `_state` and `_check_list.head`
- eval_seed.match() binding conflict detection (lines 331-336, 351-355) enforces equality
- This is bootstrap primitive (like Forth's NEXT), not semantic debt
- Both Python and JS substrates handle binding conflicts identically

**Tests:**
- `tests/test_enginenews_parity.py` - 23+ parity tests including:
  - TestEngineNewsProjections: seed structure validation
  - TestEngineNewsParity: parity vector tests
  - TestEngineNewsIntegration: integration with run_mu_structural
  - TestEngineNewsSpecCompliance: Rule 2.2 grounding tests
  - TestEngineNewsClosureObjectStructure: exact Omega(tau) structure
  - TestEngineNewsExactProjectionCount: 9 projections exactly
- `tests/test_enginenews_fuzzer.py` - Property-based fuzzer tests:
  - TestEngineNewsDeterminism: same input -> same output
  - TestEngineNewsClosureSemantics: Rule 2.2 semantics
  - TestEngineNewsEdgeCases: numeric, string, null states
  - TestEngineNewsTypeDistinctness: 0 vs false vs null
  - TestEngineNewsTraceFormats: stall, max_steps entries
  - TestEngineNewsComplexStates: nested state equality
- `tests/fixtures/enginenews_vectors.json` - 5 parity vectors

**7-Agent Review (Second Pass):**
| Agent | Verdict | Summary |
|-------|---------|---------|
| Verifier | APPROVE | All 12 North Star invariants maintained |
| Adversary | SECURE | Non-linear pattern concern RESOLVED |
| Expert | MINIMAL | Code appropriately sized |
| Structural-proof | PROVEN | All 4 structural claims verified |
| Grounding | GROUNDED | All claims have executable tests |
| Fuzzer | DESIGN COMPLETE | Comprehensive fuzzer code provided |
| Advisor | RESOLVED | Architecture is sound |

**Documentation:**
- Updated `docs/core/EngineNewsStructural.v0.md` - marked IMPLEMENTED
- Updated `docs/core/SelfHosting.v0.md` - added EngineNews section
- Updated `docs/core/BootstrapPrimitives.v0.md` - added binding conflict note
- Updated `STATUS.md` - Step 5 DONE
- Updated `TASKS.md` - all checkboxes marked complete

### Second 7-Agent Adversarial Review (Complete)

**Verdicts:**
- Verifier: CONDITIONAL_APPROVE (all 12 invariants maintained)
- Adversary: SECURE (11/11 attacks blocked, defensive cache copy verified)
- Expert: COULD_SIMPLIFY (2 trivial import issues in conftest.py)
- Structural-proof: CLAIMS_HONEST (L2 PARTIAL proven with concrete evidence)
- Grounding: GROUNDED (all 4 claims have executable tests)
- Fuzzer: GAPS_EXIST (4 boundary gaps: depth=100, width=900-1000, cache at scale, mixed)
- Advisor: ON_TRACK (Step 5 needs concrete success criteria)

### Security Fixes
- **Cache Mutation Vulnerability** (Adversary finding - CLOSED)
  - `projection_loader.py`: Returns `list(cache[0])` defensive copy
  - `step_mu.py`: Returns `list(_combined_kernel_cache)` defensive copy
  - New test: `test_mutation_does_not_affect_cache()` in test_projection_loader.py
  - Updated caching tests to verify content equality, not object identity

### Code Quality
- **Duplicate Code Consolidated** (Expert finding - CLOSED)
  - `run_until_done()` moved to `tests/conftest.py` as shared utility
  - `test_phase7c_integration.py` now imports from conftest
  - `test_parity_python.py` now imports from conftest
  - Removed ~70 lines of duplicate code

### Testing
- **Dict kv-pair Regression Tests** (Grounding finding - CLOSED)
  - Added `TestDictKvPairFormat` class (4 tests)
  - Tests exact structural format: `{"head": key, "tail": {"head": value, "tail": null}}`
  - Tests sorted key order, nested preservation

- **Malformed Linked List Tests** (Fuzzer finding - CLOSED)
  - Added `TestMalformedLinkedListEdgeCases` class (9 tests)
  - Tests head-only, tail-only, malformed tail types
  - Tests circular reference detection
  - Tests deeply nested and wide dict handling

### Documentation
- **CRITICAL: EngineNews Must Be Structural**
  - Updated TASKS.md Step 5 with concrete success criteria
  - EngineNews rules MUST be Mu projections, NOT Python code
  - Closure detection must be pattern matching on traces
  - This ensures emergence is structural, not "Python did it"
  - Added `enginenews.v1.json` requirements (≥4 projections)

- **STATUS.md**: Added second 7-agent review verdicts table
- **TASKS.md**: Updated Step 5 with structural requirements and success criteria

### Test Count
- 913 tests pass in fast audit
- 1669 tests pass in full suite (2 expected idempotency failures from uncommitted changes)

## 2026-01-29

### Security Hardening (7-agent review)
- **Deprecation Enforcement** (HIGH priority fix)
  - Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
  - New code using deprecated Kernel class will now FAIL tests (not just warn)
  - Removed `TestKernelIntegration` class (4 tests) - used deprecated Kernel
  - Coverage already exists via test_step_mu_parity.py, test_kernel_projections.py

- **Step Budget Test Coverage** (coverage gap fix)
  - Created `tests/structural/test_step_budget.py` (18 tests)
  - Tests: basics, limits, reset, thread safety, no-deprecation verification
  - Grounds the claim that step budget functions are ACTIVE (not deprecated)

- **Archive Protection** (MEDIUM priority fix)
  - Added `tests/archive/conftest.py` with `pytest_ignore_collect` hook
  - `pytest tests/archive/` now collects 0 tests (was 134)
  - Prevents accidental execution of deprecated tests

- **CI Contraband/AST Police** (MEDIUM priority fix)
  - Added contraband.sh and ast_police.py to `scripts/green_gate.sh`
  - CI now runs [PY 1/4] syntax, [PY 2/4] contraband, [PY 3/4] AST, [PY 4/4] tests
  - Catches host smuggling before merge (was only in local audit_all.sh)

- **Audit Claims Grounding Tests** (grounding agent recommendation)
  - Created `tests/structural/test_audit_claims_grounding.py` (18 tests)
  - Tests verify: archive blocking, deprecation enforcement, audit script structure
  - Tests verify: lambda guardrails exist, step budget coverage exists
  - Fully grounds all audit infrastructure claims

### Architecture Cleanup
- **kernel.py Clarification** (7-agent review)
  - Added architecture comment block explaining two distinct concerns:
    1. ACTIVE: Step budget functions (get_step_budget, etc.) - used by self-hosting
    2. LEGACY: Kernel class - NOT used by self-hosting, only for testing
  - Added deprecation warning to `Kernel` class and `create_kernel()` factory
  - Moved `test_kernel_v0.py` to `tests/archive/legacy/`
  - Created `tests/structural/test_lambda_calculus_guardrails.py` with 11 guardrail tests
  - Updated docs/core/MetaCircularKernel.v0.md with deprecation note and max_steps clarification

- **Documentation: kernel.v1.json as Canonical Kernel**
  - Updated README.md: Core modules table now lists kernel.v1.json as "THE canonical kernel"
  - Updated docs/core/SelfHosting.v0.md: kernel.py noted as "not canonical; see kernel.v1.json"
  - Updated docs/core/RCXKernel.v0.md: Added status column marking kernel.v1.json as canonical
  - Updated docs/audit/MetaCircularReadiness.v1.md: Current status references kernel.v1.json

- **Audit Stack Cleanup**
  - Updated tools/audit_fast.sh: Removed archived test_kernel_v0.py from explicit test list
  - tests/conftest.py already has `"archive"` in collect_ignore (no change needed)
  - Lambda calculus guardrails auto-included via tests/structural/ in audit_fast.sh

### Testing
- **Lambda Calculus Guardrail Tests Migrated** (11 tests)
  - Migrated from test_eval_seed_v0.py to dedicated structural test file
  - Tests prove: no closures, no self-application, no Y-combinator, no higher-order matching
  - These are NORTH STAR invariant enforcement tests

### Documentation
- **STATUS.md**: Fixed @host_recursion count (3 → 2)
- **Added tests for `is_kernel_intermediate()`** (12 tests)
  - Documents key finding: `{"mode": "subst"}` (value) vs `{"subst": ...}` (key)
  - Proves mu_equal stall detection works correctly for unbound variables

### L2 Grounding & Boundary Validation
- **Docstring False Positive Fix**
  - Fixed eval_seed.py:70 docstring being counted as debt by debt_dashboard.sh
  - Was matching `@host_` pattern in docstring text

- **L2 Cursor Grounding Tests** (7 tests)
  - Created `tests/structural/test_l2_cursor_grounding.py`
  - Proves `_remaining` is structural (head/tail), not arithmetic index
  - Tests kernel.wrap creates _remaining from _projs linked list
  - Tests kernel.try consumes head, kernel.match_fail advances to tail

- **Boundary Validation Fuzzer** (27 tests)
  - Created `tests/test_boundary_validation_fuzzer.py`
  - Tests assert_seed_pure with valid/invalid inputs (lambdas, functions, builtins)
  - Tests validate_type_tag whitelist enforcement (list/dict only)
  - Tests get_var_name validation (empty names, non-var sites)

- **Kernel Bridge Fuzzer** (26 tests)
  - Created `tests/test_kernel_bridge_fuzzer.py`
  - Tests list_to_linked (preserves length, order, produces valid Mu)
  - Tests normalize_projection (pattern/body normalization)
  - Integration tests for projection list conversion

- **SelfHosting.v0.md Update**
  - Documented legacy Kernel class deletion (~350 lines removed)
  - Clarified kernel.py now only contains step budget infrastructure

## 2026-01-28

### Testing
- **Fuzzer Configuration Fully Standardized** (3x 9-agent review)
  - Fixed `deadline=None` in test_apply_mu_fuzzer.py (10 tests → `deadline=5000` or `deadline=10000`)
  - Standardized `max_depth=3` default across ALL 6 fuzzer generators:
    - test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py
    - test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py
  - Fixed 29 call site overrides: `max_depth=4` → `max_depth=3` across 4 files
  - Fixed docstring bug in test_apply_mu_fuzzer.py ("default 5" → "default 3")
  - Documentation claims now match reality (STATUS.md is single source of truth)
  - Prevents tests from hanging on pathological inputs
  - All 772 core tests pass

### Self-Hosting
- **Phase 7d-1: Wire step_mu to Structural Kernel** (L2 PARTIAL)
  - `step_mu()` delegates to `step_kernel_mu()` which uses structural kernel
  - Added helpers: `list_to_linked()`, `normalize_projection()`, `load_combined_kernel_projections()`
  - Kernel uses linked-list cursor for projection SELECTION (structural)
  - Projection EXECUTION still uses Python for-loop in `step_kernel_mu`
  - Behavioral change: unbound variables now stall instead of raising KeyError

- **Honest Assessment (7-agent review)**
  - structural-proof agent found: execution loop still Python (lines 229-261)
  - Added `@host_iteration` decorator to `step_kernel_mu()` (honest debt tracking)
  - Debt: 15 → 15 (moved location, not eliminated)
  - L2 PARTIAL: selection structural, execution Python
  - True L2 requires Phase 8 recursive kernel design
  - 7d-2/7d-3 PAUSED pending Phase 8

- **Phase 7a: Kernel Projections Seed**
  - Created `seeds/kernel.v1.json` with 7 kernel projections
  - Projections: kernel.wrap, kernel.stall, kernel.try, kernel.match_success, kernel.match_fail, kernel.subst_success, kernel.unwrap
  - 30 manual trace tests pass (success, failure, empty, fallthrough)
  - Tests in `tests/test_kernel_projections.py`

- **Phase 7b: Match/Subst Context Passthrough**
  - Created `seeds/match.v2.json` with `_match_ctx` passthrough + match.fail catch-all
  - Created `seeds/subst.v2.json` with `_subst_ctx` passthrough
  - Context enables kernel to preserve state across mode transitions

- **Phase 7c: Integration Testing**
  - 20 integration tests: kernel → match → subst → kernel cycles
  - Tests in `tests/test_phase7c_integration.py`
  - Context preservation verified through full cycles
  - Security: domain data can't forge `_mode` (underscore prefix)

### Tests
- **v2 Parity Tests**
  - Created `tests/test_match_v2_parity.py` (19 tests)
  - Created `tests/test_subst_v2_parity.py` (18 tests)
  - 37 tests verify v2 seeds preserve v1 behavior
  - Tests: seed structure compatibility, functional parity, context design

### Debt Tracking
- **Comprehensive Debt Audit**
  - Found and marked 4 @host_iteration markers (step_mu, run_mu, eval_seed.step, projection_runner)
  - Added `# @host_iteration` comment marker for nested function debt
  - Updated `debt_dashboard.sh` to count both decorator and comment markers
  - Debt: 15 (12 tracked + 3 AST_OK)

- **Debt Target Revision**
  - Original target was 9, revised to 12 per structural-proof agent
  - run_mu outer loop stays as L3 boundary (scaffolding, not semantic debt)
  - 7d-1 moved debt from step_mu to step_kernel_mu (net: 15 → 15)
  - True debt reduction (15 → 12) deferred to Phase 8

### Docs
- **Doc Consistency Fixes**
  - All design docs now reference STATUS.md for debt numbers (no hardcoded values)
  - `docs/core/SelfHosting.v0.md`: Removed hardcoded debt breakdown
  - `docs/core/MetaCircularKernel.v0.md`: Updated status VECTOR → NEXT
  - `docs/core/DebtCategories.v0.md`: Removed outdated DEBT_THRESHOLD values

### Security
- **Kernel Projection Order Validation**
  - Added `validate_kernel_projections_first()` call in step_mu() production path
  - Domain projections can no longer run before kernel projections
  - Tests in `tests/structural/test_projection_order_security.py`

### Process
- **7 Agent Review Complete**
  - verifier: APPROVE WITH DOC FIXES
  - adversary: AT_RISK (security concerns documented)
  - expert: MINIMAL (code is clean)
  - structural-proof: PARTIALLY PROVEN (debt 15→9 unrealistic, revised to 15→12)
  - grounding: GROUNDED (all claims backed by tests)
  - fuzzer: GAPS (3 property tests recommended before 7d)
  - advisor: PROCEED NOW (foundation strong)

### Tooling
- **Pre-commit Hook Improvements**
  - Added debt ceiling check to `tools/pre-commit-doc-check`
  - Hook now warns if debt exceeds THRESHOLD from STATUS.md
  - Updated `CLAUDE.md` with clearer workflow documentation
  - Added "Development Workflow" section to `STATUS.md`
  - Two pre-commit scripts documented: `pre-commit-check.sh` (full) vs `pre-commit-doc-check` (hook)

## 2026-01-27

### Agents
- **Advisor Agent** - New strategic advisor for when stuck on design decisions
  - Created `tools/agents/advisor_prompt.md` and `.claude/agents/advisor.md`
  - Provides options, trade-off analysis, creative solutions
  - Verdict types: OPTIONS_PROVIDED / RECOMMENDATION / NEEDS_MORE_CONTEXT
  - Advisor PROPOSES, other agents VALIDATE

- **Agent Documentation Completion**
  - Created 4 missing prompt files in `tools/agents/` (now all 10 agents tracked in git):
    - `grounding_prompt.md`, `fuzzer_prompt.md`, `translator_prompt.md`, `visualizer_prompt.md`
  - All agents now have "STATUS.md wins" override rule
  - structural-proof has exec/non-exec modes (Mode A: run, Mode B: CI verification)

- **Archived**: `tools/verification_checklist.md` → `docs/archive/verification_checklist_v0.md`
  - Superseded by `tools/agents/verifier_prompt.md` (verifier agent)

### Design
- **Phase 7 Design: Meta-Circular Kernel** (PR #168)
  - Created `docs/core/MetaCircularKernel.v0.md` (VECTOR status)
  - Defines how kernel loop becomes structural (projections select projections)
  - Key design: linked-list cursor eliminates arithmetic (head/tail destructuring)
  - Structural-proof agent verified cursor approach is SOUND and STRUCTURAL
  - v0.2 revision addresses agent-identified gaps:
    - Context preservation via `_match_ctx` / `_subst_ctx` fields
    - Structural NO_MATCH: `{"_mode": "match_done", "_status": "no_match"}`
    - Namespace protection: `_` prefix for kernel-internal fields
    - Simplified from 11 to 7 kernel projections
  - Total projections: 7 kernel + 32 existing = 39 for fully self-hosted kernel

### Tooling
- **STATUS.md: Single Source of Truth for Project Phase**
  - Created `STATUS.md` as canonical source for current phase and self-hosting level
  - All agents now read STATUS.md before assessments (MANDATORY)
  - Self-hosting levels: L1 (Algorithmic), L2 (Operational), L3 (Full Bootstrap)
  - Agent Enforcement Guide table: what applies NOW vs LATER
  - When advancing phases: update ONE file, not 8+ agent files

- **Agent Semantic Phase Scope**
  - Updated all 8 agent `.md` files with semantic scope (L1/L2/L3, not phase numbers)
  - Agents reference STATUS.md for current level, not hardcoded version
  - Distinguishes scaffolding debt (acceptable at current L) from semantic debt (must fix)
  - Updated `docs/agents/AgentRig.v0.md` with semantic Phase Scope table
  - Prevents phase drift: agents adapt automatically when STATUS.md updates

### Tests
- **Kernel Loop Fuzzer Tests** (PR #167)
  - 11 property-based tests for apply_mu, step_mu, run_mu
  - TestApplyMuDeterminism: 3 tests (determinism, var pattern, literal match)
  - TestApplyMuParity: 1 test (apply_mu == apply_projection)
  - TestStepMuDeterminism: 3 tests (determinism, empty projections, stall idempotent)
  - TestStepMuParity: 2 tests (step_mu == step, first-match-wins)
  - TestRunMuDeterminism: 2 tests (determinism, immediate stall)
  - 3000+ random examples stress-test kernel loop stability
  - Closes fuzzer gap identified by agents before Phase 7

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
