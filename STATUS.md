# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

> **Document Architecture**: See [`roadmap/MANIFEST.md`](roadmap/MANIFEST.md) for reading order and linking rules across STATUS.md, TASKS.md, and roadmap docs.

---

## Current Phase

```
PHASE: 8b
NAME: Mechanical Kernel (Security Hardened)
```

## Projection-Based Architecture Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms EXPRESSED as Mu projections | DONE (Python executes projections) |
| **L2: Operational** | kernel state machine EXPRESSED as Mu projections | FULL (decision: accept for-loop as bootstrap primitive) |
| **L3: Substrate Portability** | Same projections on Python and JavaScript substrates | COMPLETE |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (research question) |

**Terminology Honesty:**
- "Projection-based" means the ALGORITHM is expressed as Mu projections (data)
- Python's `eval_step()` EXECUTES those projections (like Forth's NEXT executes threaded code)
- This is NOT "self-hosting" in the traditional sense - Python is the execution engine
- The "kernel" in L2 refers to `kernel.v1.json` (7 projections), NOT the deprecated `Kernel` class

## What This Means

- **L1 Algorithmic DONE**: `match_mu()` and `subst_mu()` algorithms are expressed as Mu projections in seeds. Python's `eval_step()` executes them.
- **L2 Operational FULL**: Projection SELECTION is structural (linked-list cursor in kernel.v1). Projection EXECUTION is Python (`for` loop in `step_kernel_mu`) - accepted as bootstrap primitive per Phase 8 decision.
- **Python's role**: `eval_step()` is a bootstrap primitive (like Forth's NEXT). It applies projections using Python pattern matching. This is irreducible in current architecture.

## L2 Completion Criteria (Explicit)

**L2 FULL (current status - PARTIAL + explicit acceptance):**
- [x] Kernel state machine is 7 Mu projections (`kernel.v1.json`)
- [x] Match v2 with context passthrough (8 projections, `_match_ctx`) - used by kernel
- [x] Subst v2 with context passthrough (12 projections, `_subst_ctx`) - used by kernel
- [x] Projection selection uses linked-list cursor (`_remaining` field, no index arithmetic)
- [x] `step_kernel_mu()` wired to use structural kernel
- [x] Security hardening complete (22 reserved fields, deep validation)
- [ ] Python for-loop still drives kernel execution (`step_mu.py:397-410`)

**Seed version note:** `match_mu()` and `subst_mu()` standalone functions use v1 seeds for direct invocation. The kernel (`step_kernel_mu`) uses v2 seeds which add context passthrough (`_match_ctx`, `_subst_ctx`) for kernel integration.

**L2 FULL (target - requires decision):**
The gap from PARTIAL to FULL is the Python for-loop in `step_kernel_mu()`. Options:
1. **Accept as bootstrap primitive** (Forth precedent) - Loop is like Forth's NEXT, irreducible
2. **CPS/Trampolining** - Convert loop to continuation-passing, projections chain via Mu data
3. **Structural fuel counter** - `max_steps` becomes Mu data that decrements structurally

**Current decision:** Option 1 (accept as bootstrap primitive). The for-loop is marked with `@host_iteration` and documented as irreducible. L2 FULL = L2 PARTIAL + explicit acceptance.

**L2 EXCLUDED (by design):**
- `eval_step()` is bootstrap primitive (irreducible)
- `run_mu()` outer loop is L3 boundary (repeat-until-stall scaffolding)
- `projection_runner.py` iteration (composition pattern, not execution)

## L3/L4 Definition (Bootstrap Architecture)

### L3: Substrate Portability (ACHIEVED via JS POC)

L3 is defined as **projections run on minimal, auditable substrate**:

| Component | Role | Python | JS |
|-----------|------|--------|-----|
| **kernel.v1.json** | Kernel state machine (7 projections) | ✅ | ✅ |
| **match.v2.json** | Pattern matching (8 projections) | ✅ | ✅ |
| **subst.v2.json** | Substitution (12 projections) | ✅ | ✅ |
| **recurrence.v1.json** | Closure detection (9 projections) | ✅ | ✅ |
| **Python Substrate** | ~2000 LOC, 2,100+ tests, production-ready | ✅ PRIMARY | - |
| **JS Substrate** | ~600 LOC core + inline tests, auditable, portability proof | - | ✅ COMPLETE |
| **Bootstrap Primitives** | eval_step, mu_equal, max_steps, stack_guard, projection_loader | Same in both | Same in both |

**What L3 proves:**
- The SAME projections (all 4 seed files) run on Python AND JavaScript
- All semantics are in the projections (data), not the host (code)
- The host provides only mechanical execution (the 5 bootstrap primitives)
- EngineNews closure detection works identically on both substrates

**L3 Parity Requirement (MANDATORY - North Star #13):**
- Any change to Python projection behavior MUST be mirrored in JavaScript
- **Core L3 seeds** (kernel, match, subst, recurrence, exhaustion, bootstrap_structural) MUST be loaded in BOTH substrates
- **Utility seeds** (classify.v1, eval.v1) and **application seeds** (rcx_engine.v1) are Python-only for now
- Parity vectors in `tests/fixtures/` are shared by both implementations
- Run `node mu/host/js/eval_step.js` after Python changes to verify JS parity
- Run `./tools/check_js_debt.sh` to verify JS debt markers match Python
- Violation of parity breaks L3 and must be fixed before merge

**L3 Seed Categories:**
| Category | Seeds | JS Loaded | Notes |
|----------|-------|-----------|-------|
| **Substrate (Core)** | kernel.v1, match.v2, subst.v2 | ✅ | Required for L3 |
| **Closures (Core)** | recurrence.v1, exhaustion.v1 | ✅ | Required for L3 |
| **Bridge** | bootstrap_structural.v1 | ✅ | Non-linear pattern support |
| **Utilities** | classify.v1, eval.v1 | Python-only | Optional - helper algorithms |
| **Programs** | rcx_engine.v1 | Python-only | Design-only, not production |

**JS Debt Tracking (matches Python):**
- JS file has DEBT SUMMARY header with counts
- Functions marked with `@host_iteration`, `@host_recursion`, `@host_builtin`
- Bootstrap primitives marked with `BOOTSTRAP_PRIMITIVE`
- `tools/check_js_debt.sh` validates markers are present
- `tools/contraband_js.sh` validates no forbidden patterns (determinism, purity)
- Both audit scripts (fast/all) run JS debt check and contraband check
- All semantics are in the projections (data), not the host (code)
- The host provides only mechanical execution (the 5 bootstrap primitives)
- This is the Hex0/Forth precedent: meaning in data, mechanics in minimal runner

**JS Contraband Patterns (blocked by contraband_js.sh):**
- `eval(`, `Function(` - Code injection breaks purity
- `setTimeout`, `setInterval` - Async breaks determinism
- `Math.random`, `Date.now`, `new Date(` - Non-determinism
- `process.env` - Environment leakage
- `child_process`, `exec(`, `spawn(` - Subprocess spawning
- `fs.write*`, `fs.append*`, `fs.unlink`, `fs.rm*` - File mutation (read-only allowed)
- `require.*http`, `fetch(` - Network access breaks determinism

**JS AST Police (blocked by ast_police_js.sh):**
- Indirect eval: `window['eval']`, `globalThis.eval`, `(0,eval)`
- String concatenation bypass: `'ev'+'al'`
- Scope manipulation: `with()`, `debugger`
- Prototype pollution: `__proto__`, `Object.setPrototypeOf`
- Reflection bypass: `Reflect.construct`, `Reflect.apply`
- Async: `async function`, `await`, generators (`function*`, `yield`)
- Hidden state: `Proxy`, `WeakMap`, `WeakSet`, `Symbol.for`, `Symbol.iterator`
- Note: `const SENTINEL = Symbol('name')` is allowed for sentinel values

**JS Theater Check (blocked by check_test_theater_js.sh):**
- Vacuous assertions: `assert(true)`, `assert(1)`, `assert(!false)`
- Self-comparison: `x === x`
- Empty test bodies
- Commented-out assertions
- TODO/FIXME test placeholders

**Seed Police (blocked by seed_police.sh):**
- Missing required fields: `id`, `pattern`, `body`
- Theater projections: empty patterns, trivial bodies, duplicate IDs
- Host leakage: `lambda`, `def `, `function(`, `=>`, `eval(` in string values
- Security: reserved field misuse in non-kernel projections
- Cross-seed ID collisions (except versioned families like v1/v2)

**JS POC location:** `mu/host/js/eval_step.js` (~600 LOC core + inline tests)
- Now tracked in git (required for CI)
- Includes `--json-api` mode for machine-readable output (cross-substrate verification)

### L4 Research: True Self-Hosting (SINK)

L4 asks: **Can bootstrap primitives be eliminated entirely?**

| Primitive | L4 Question | Possible Path |
|-----------|-------------|---------------|
| `eval_step` | Can it be a projection? | Requires meta-level substrate |
| `mu_equal` | Can structural equality be structural? | Possibly via comparison projections |
| `stack_guard` | Can depth be Mu data? | Count in Mu, not Python |
| `projection_loader` | Can Mu load Mu? | Possibly, with file I/O primitive |

**L4 Status:** Open research question in SINK. Not promised, not ruled out.

**Key Insight:** L3 doesn't close L4 - it opens it. By making bootstrap primitives explicit and minimal (~600 LOC core in JS), we know exactly what would need to change.

**The Honest Answer:** Forth has NEXT. Lisp has EVAL. Some primitive always exists. The question is: what's the minimal primitive? The JS POC at ~600 LOC core is our current answer - auditable, portable, mechanical.

### Cross-Substrate Testing Strategy

**Status:** GROUNDED (Steps 1-5 complete, 2026-01-31)

Cross-substrate parity tests verify L3 (substrate portability):
- [x] Shared JSON test vectors: `tests/fixtures/parity_vectors.json` (20 parity + 3 security = 23 vectors)
- [x] Python tests: `tests/test_parity_python.py` (20 parity tests + 3 security tests)
- [x] JS tests: `mu/host/js/eval_step.js` (20 parity tests pass)
- [x] Structural trace tests: `tests/test_structural_trace.py` (14 tests)
- [x] **ACTUAL cross-substrate comparison** (9-agent Round 3 fix, 2026-01-31):
  - `tests/test_js_parity_automated.py::test_actual_cross_substrate_comparison`
  - Runs SAME 20 vectors through BOTH Python and JS kernels via JSON API
  - Compares actual outputs (not just string parsing)
  - Handles int/float normalization (JS doesn't distinguish)
- [x] CI workflow runs both: Python pytest + `node mu/host/js/eval_step.js`

**Security gaps in JS POC (adversary finding - FIXED 2026-01-30):**
- [x] `KERNEL_RESERVED_FIELDS` validation (added v4)
- [x] `validate_type_tag()` in denormalize (added v4 fix)
- [x] Dict kv-pair normalization parity fix (v4)
- [ ] Lambda calculus guard (future - not critical for L3)

## Development Workflow

**Before committing, run:**
```bash
./tools/pre-commit-doc-check      # Canonical commit gate (docs, debt, tracker, staged checks)
./tools/check_docs_consistency.sh # Verify STATUS.md matches reality
./tools/debt_dashboard.sh         # Check debt doesn't exceed ceiling
```

**Git hook (auto-runs on commit):**
```bash
# Install once:
ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit
```

The pre-commit hook checks doc consistency, debt ceiling, targeted staged-file checks, and tracker sync. See `CLAUDE.md` for full workflow details.

## Testing Tiers

```
Tier 1: Fast Audit    ./tools/audit_fast.sh    ~3 min   Core tests only
Tier 2: Full Audit    ./tools/audit_all.sh     ~5-8 min Core + Fuzzer tests
Tier 3: Stress Tests  pytest tests/stress/     ~10+ min Deep edge cases
```

| Tier | What It Tests | When to Run |
|------|---------------|-------------|
| Tier 1 | Core algorithms, syntax, contraband, security tool grounding | Local iteration |
| Tier 2 | All tests including 200+ example fuzzers | Before push, CI |
| Tier 3 | Deep nesting, wide structures, pathological inputs | Comprehensive validation |

**Tier 1 includes (2026-02-01):**
- `tests/structural/` (17 files) - structural claims grounding
- `tests/tools/` (4 files) - security tool grounding tests (including validator)
- 20 core test files including adversarial and self-hosting tests
- 34 CRITICAL_TEST_FILES protected from silent skipping

**Fuzzer Settings (standardized 2026-01-28):**
- `max_depth=3` in ALL test generators (prevents pathological nesting after normalization)
- `deadline=5000` on ALL fuzzer tests (5 second timeout per example)
- Stress tests use `deadline=10000-30000` for deep edge cases
- Files standardized: test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py, test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py

**For fast local iteration:**
```bash
HYPOTHESIS_PROFILE=dev pytest tests/test_bootstrap_fuzzer.py  # ~30 seconds
```

See `docs/TESTING_PERFORMANCE_ISSUE.md` for full context on testing strategy.

## Debt Status

```
THRESHOLD: 12
CURRENT: 12 (10 tracked decorators + 2 AST_OK bootstrap)
L2 FLOOR: 12 (see explanation below)
INFRA_CEILING: 37
INFRA_CURRENT: 36
```

**Debt breakdown:**
- @host_recursion: 2 (eval_seed match/substitute - BOOTSTRAP)
- @host_builtin: 3 (eval_seed, deep_eval)
- @host_iteration: 3 (run_mu, step_kernel_mu, run_mu_structural - BOOTSTRAP)
- @host_mutation: 2 (eval_seed, deep_eval)
- AST_OK bootstrap: 2 (eval_seed list/dict comprehensions)

**Gate 6 note (2026-02-02):**
- run_algorithm_meta_circular: Delegates to eval_step (no new iteration debt)
- load_combined_kernel_v3_projections: Available for future use (no debt)
- No debt increase - Gate 6 uses existing bootstrap layer

**Why 12 is the L2 floor (not a target for reduction):**
The `match()` and `substitute()` in eval_seed.py are NOT "reference implementations" - they ARE the bootstrap primitives that `eval_step()` uses to apply ANY projection. The production path is:
1. `step_kernel_mu()` → `eval_step()` (on kernel.v1 + match.v2 + subst.v2)
2. `eval_step()` → `apply_projection()` → `match()` + `substitute()` (eval_seed.py)
3. `run_mu_structural()` → structural trace for EngineNews (Phase 8d)
4. `run_algorithm_meta_circular()` → trusted algorithm execution (recurrence, exhaustion)

These cannot be eliminated because:
- eval_step needs to apply projections (pattern match + substitute)
- match_mu/subst_mu use eval_step to apply THEIR projections
- run_mu_structural provides trace accumulation for EngineNews
- run_algorithm_meta_circular runs trusted internal algorithms through eval_step
- Circular dependency: eliminating them would require eval_step to not exist

The debt of 12 represents the IRREDUCIBLE BOOTSTRAP SUBSTRATE for L2. L4 paths are documented:
- **Boot0 Architecture v0.4** (`docs/core/Boot0Architecture.v0.md`) - staged bootstrap design, 9-agent reviewed
- **L4 research questions**: Can mu_equal/eval_step become projections? CPS/trampolining?
- Implementation DEFERRED until L4 research drives it (L3 complete first)

**Reclassified as infrastructure (not debt):**
- match_mu.py:708 - boundary conversion function (AST_OK: infra)
- step_mu.py:148 - constant definition (AST_OK: infra)

**Scaffolding ceiling (prevents unbounded accumulation):**
- AST_OK:infra ceiling: 37 (current 36)
- AST_OK:infra is NOT debt, but capped to prevent drift
- Gate 6 added 3 new infra markers for kernel v3 and algorithm runner

Note: projection_runner has a comment mentioning @host_iteration but uses composition pattern, not decoration.

**Note on boundary scaffolding:**
The `while` loops in `match_mu.py` (normalize_for_match, denormalize_from_match, bindings_to_dict, etc.) are NOT counted as debt. These are Python API conversion functions that convert between Python types and Mu linked lists at the boundary. They are explicitly documented as "boundary scaffolding" in their docstrings. Boundary scaffolding is expected to remain indefinitely as part of the Python API layer - it's not a target for structural replacement.

**Phase 8b outcome (2026-01-28):**
- Simplified step_kernel_mu to MECHANICAL operation (no semantic branching)
- Added `is_kernel_terminal()` - simple structural marker detection
- Added `extract_kernel_result()` - mechanical unpacking
- Loop body: ~35 lines → ~15 lines
- eval_step reclassified as BOOTSTRAP_PRIMITIVE (not debt)
- **Security hardening (9-agent reviewed):**
  - Deep validation: recursive check prevents nested smuggling
  - KERNEL_RESERVED_FIELDS: 24 fields (12 base + 4 EngineNews + 4 Exhaustion + 4 Bridge)
  - Depth guard fails CLOSED (raises ValueError at depth > 100)
- Net debt: 12 (10 tracked decorators + 2 AST_OK bootstrap)

**Phase 7d-2/7d-3 CLOSED (per Phase 8 decision):**
- Phase 8 decided: "Option 1 (accept as bootstrap primitive)"
- The for-loop in step_kernel_mu is accepted as irreducible (like Forth's NEXT)
- L2 FULL = L2 PARTIAL + explicit acceptance - this is ACHIEVED
- 7d-2/7d-3 are no longer needed; they assumed we'd eliminate the loop
- If L4 pursues CPS/trampolining, new tasks will be created

Note: run_mu outer loop is scaffolding (L3 boundary), not removed in Phase 7.

## Agent Enforcement Guide

Use this to determine what standards apply NOW vs LATER:

| Condition | Status | Agent Action |
|-----------|--------|--------------|
| Match/subst must be Mu projections | L1 DONE | REQUIRED - enforce now |
| Kernel loop must be Mu projections | L2 FULL | `step_mu` uses structural kernel; for-loop accepted as bootstrap |
| Python iteration in `step_mu` | FIXED (7d-1) | No longer debt - uses structural kernel |
| Python iteration in `run_mu` | L3 boundary | ACCEPTABLE - outer loop scaffolding |
| Python recursion in algorithms | Semantic debt | FAIL - must use projections |
| Unmarked host operations | Debt violation | FAIL - must mark with `@host_*` |

## Phase 7 Blockers (Agent Findings - 2026-01-27)

These were resolved before promoting Phase 7 from VECTOR to NEXT (promoted 2026-01-27):

**Fuzzer agent (Phase 7 readiness VERIFIED):**
- [x] Create `tests/test_phase7_readiness_fuzzer.py` (32 tests, ~700 lines):
  - [x] Seed projection coverage (no unintended stalls)
  - [x] Kernel trace integrity (traces are replay-complete)
  - [x] Kernel state injection resistance (domain data can't forge `_mode`/`_phase`)
- [x] Non-linear pattern fuzzer tests (documents current first-occurrence-wins behavior)

**Grounding agent (13 claims UNGROUNDED):**
- [x] Seed projection count tests (match=7, subst=12, classify=6, eval=7)
- [x] Seed schema validation tests (id, pattern, body required)
- [x] Type tag security tests (whitelist enforcement)

**Adversary agent (SECURE, recommendations):**
- [x] Add projection order regression test (first-match-wins is security-critical)
- [x] Seed checksum update tool - CLOSED (existing test workflow sufficient, see adversary report 2026-01-27)
- [x] Document classify_mu.py string key assumption as known limitation (see DebtCategories.v0.md)

**Expert agent (SIMPLIFIED):**
- [x] Consolidate projection loader pattern → `projection_loader.py` (factory)
- [x] Consolidate runner pattern → `projection_runner.py` (factory)
- [x] Move test-only helpers out of match_mu.py - CLOSED (expert review found NO test-only code, all is production)

**Structural-proof agent:**
- [x] L1 claims PROVEN (match_mu, subst_mu, classify use projections)
- [x] L2 design verified structurally sound (linked-list cursor, context passthrough, meta-circularity confirmed 2026-01-27)

**Additional tests (2026-01-28):**
- [x] `tests/structural/test_projection_loader.py` - Factory loader tests (13 tests)
- [x] `tests/structural/test_projection_runner.py` - Factory runner tests (33 tests)
- [x] `tests/test_kernel_loop_fuzzer.py` - L2 kernel iteration fuzz tests (16 tests)
- [x] `tests/test_context_passthrough_fuzzer.py` - Context preservation fuzz tests (12 tests)
- [x] `tests/structural/test_step_mu_kernel_integration.py` - Kernel integration tests (30 tests)

**Security fix (2026-01-28 - Adversary review):**
- [x] Implemented `KERNEL_RESERVED_FIELDS` boundary validation in `step_mu.py`
- [x] `validate_no_kernel_reserved_fields()` rejects domain inputs with kernel fields
- [x] Fields protected: `_mode`, `_phase`, `_input`, `_remaining`, `_match_ctx`, `_subst_ctx`, `_kernel_ctx`, `_status`, `_result`, `_stall`, `_step`, `_projs`
- [x] Deep validation: recursive check prevents nested smuggling attacks (e.g., `{"outer": {"_mode": "done"}}`)
- [x] Fail closed: Depth limit (100) raises ValueError, doesn't silently trust remaining structure

## Key Files

- Design doc: `docs/core/MetaCircularKernel.v0.md`
- Self-hosting: `rcx_pi/selfhost/` (match_mu, subst_mu, step_mu)
- **mu/ folder (new organized structure):**
  - Substrate: `mu/substrate/` (kernel.v1, match.v2, subst.v2)
  - Closures: `mu/closures/` (recurrence.v1, exhaustion.v1)
  - Programs: `mu/programs/` (rcx_engine.v1)
  - Host: `mu/host/js/eval_step.js`, `mu/host/python/selfhost`
- Task list: `TASKS.md`
- **Documentation governance:** `docs/core/DocGovernance.v0.md` (Three Laws, tiered governance)
- **Doc tests:** `tests/docs/` (118 tests: contracts, freshness, governance, root files)
- Grounding tests: `tests/structural/` (status, seeds, type tags, projection order, audit claims)

---

## Recommended Next Action

**Status:** Phase 8b COMPLETE (2026-01-28). 9-agent review SHIP verdict. 2,100+ tests passing.

**L3 Substrate Portability Progress (2026-01-30):**
- Step 1 DONE: JS POC security hardened (v4) - KERNEL_RESERVED_FIELDS validation, dict kv-pair fix
- Step 2 DONE: Cross-substrate parity tests - 20 vectors pass on both Python and JS
- Step 3 DONE: Phase 8d trace model in Python - run_mu_structural() + 14 tests
- Step 4 DONE: Port trace to JS POC - runStructural() + 5 tests
- Step 5 DONE: EngineNews structural closure detection (mu/closures/recurrence.v1.json, 9 projections)

**Step 5 EngineNews Implementation (2026-01-30):**
- Created `mu/closures/recurrence.v1.json` with 9 projections for structural closure detection
- Implements Rule 2.2 (Closure-on-Second-Demand) via pattern matching on traces
- Closure detection uses non-linear patterns (same var twice) for state equality
- Non-linear pattern enforcement provided by eval_seed.match() binding conflict detection
- 24 parity tests in `tests/test_recurrence_parity.py`
- 22 parity vectors in `tests/fixtures/recurrence_vectors.json`
- Property-based fuzzer tests in `tests/test_recurrence_fuzzer.py`
- 7-agent review: All agents APPROVE (adversary concern RESOLVED)

**Test files (must be tracked in git):**
- `tests/test_parity_python.py` - 20 parity + 3 security tests
- `tests/test_structural_trace.py` - 14 structural trace tests
- `tests/test_structural_trace_fuzzer.py` - 23 property-based fuzzer tests (7-agent critical gap closed)
- `tests/fixtures/parity_vectors.json` - 23 shared test vectors

**Critical Bug Fix (2026-01-30 - Adversarial Review):**
- Fixed Python/JS dict kv-pair normalization parity bug
- Python: `{"head": key, "tail": {"head": value, "tail": null}}`
- JS was wrong: `{"head": key, "tail": value}` (now fixed to match Python)
- Added type tag validation to JS denormalize() for security parity

**7-Agent Review Implementation (2026-01-30):**
Addressed findings from comprehensive 7-agent adversarial peer review:
- **Expert finding (consolidated):** Removed duplicate `run_until_done()` - now shared via `conftest.py`
- **Grounding finding (closed):** Added `TestDictKvPairFormat` - exact kv-pair structure regression tests
- **Fuzzer finding (closed):** Added `TestMalformedLinkedListEdgeCases` - edge case handling tests
- **Adversary finding (closed):** Added defensive cache copy to projection_loader.py and step_mu.py
- **Tests added:** 13 new tests in `tests/test_normalization_roundtrip.py`, 1 new cache mutation test
- **Test updates:** `test_phase7c_integration.py` and `test_parity_python.py` now use shared `run_until_done()`
- **Test updates:** `test_projection_loader.py` and `test_classify_mu.py` updated for defensive copy behavior

**Second 7-Agent Review Verdicts (2026-01-30):**
| Agent | Verdict | Summary |
|-------|---------|---------|
| Verifier | CONDITIONAL_APPROVE | All 12 invariants maintained |
| Adversary | SECURE | 11/11 attacks blocked |
| Expert | COULD_SIMPLIFY | 2 trivial import issues |
| Structural-proof | CLAIMS_HONEST | L2 PARTIAL proven, gaps documented |
| Grounding | GROUNDED | All claims have tests |
| Fuzzer | GAPS_EXIST | 4 boundary gaps identified |
| Advisor | ON_TRACK | Step 5 needs concrete criteria |

**Fuzzer Gap Resolution (2026-01-30):**
- Gap 1 (CRITICAL) CLOSED: `tests/test_structural_trace_fuzzer.py` (23 property-based tests)
- Tests run_mu_structural() for: termination, structure validity, trace format, stall detection, determinism, oscillation detection
- Added to CRITICAL_TEST_FILES (cannot be silently skipped)

**CRITICAL: EngineNews Must Be Structural (2026-01-30):**
Step 5 (EngineNews Demo) requires that EngineNews rules are expressed as Mu projections,
NOT Python code. Closure detection must be pattern matching on traces, not Python loops.
This is essential for structural honesty - emergence must be attributable to RCX dynamics,
not "Python did it". See TASKS.md Step 5 for concrete success criteria.

**Security Hardening (2026-01-29, 7-agent review):**
- Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
- New code using deprecated Kernel will FAIL tests (not just warn)
- Removed `TestKernelIntegration` (4 tests) - used deprecated Kernel
- Created `tests/structural/test_step_budget.py` (18 tests) for ACTIVE infrastructure
- Created `tests/structural/test_audit_claims_grounding.py` (18 tests) for audit verification
- Added `tests/archive/README.md` documenting archive purpose

**CI/Audit Infrastructure Hardening (2026-01-30, 9-agent review):**
- Created `tests/tools/` directory with grounding tests for security tools (65+ tests):
  - `test_contraband_detection.py` (65 tests) - verifies contraband.sh patterns work
  - `test_contraband_js_detection.py` (34 tests) - verifies contraband_js.sh patterns
  - `test_ast_police_detection.py` (23 tests) - verifies ast_police.py detection
  - `test_ast_police_js_detection.py` (32 tests) - verifies AST patterns in JS
  - `test_check_test_theater_detection.py` (7 tests) - verifies theater check
  - `test_check_test_theater_js_detection.py` (16 tests) - verifies JS theater check
  - `test_seed_police_detection.py` (16 tests) - verifies seed_police.sh
- Added `import builtins` detection to contraband.sh (closes eval/exec bypass)
- Added `base64/codecs` detection to contraband.sh (encoding bypass defense-in-depth)
- Added AST_OK category validation (8 approved categories prevent bypass abuse)
- Added CRITICAL_TEST_FILES protection (32 files cannot be silently skipped):
  - Debt/security enforcement, core parity tests, tool grounding tests
  - Adversarial tests, self-hosting tests, grounding verification
- Updated audit_fast.sh to include security-critical tests in Tier 1
- Single source of truth: THRESHOLD and INFRA_CEILING read from STATUS.md

**Agent Guardrails (Anti-Hallucination, 2026-02-01):**
- Created `docs/agents/AgentGuardrails.v0.md` - requires FILE:LINE + code evidence
- Created `tools/validate_agent_compliance.py` - validates agent output format
- Created `tests/tools/test_validate_agent_compliance.py` (43 tests)
- Created `.claude/hooks/validate-agent-compliance.sh` - automatic SubagentStop hook
- Updated all 9 agent prompts with MANDATORY verification protocol
- Agent models: Opus (verifier, adversary, expert, advisor), Sonnet (others) - no Haiku

**Known Security Limitations (9-agent consensus, 2026-01-30):**
These were reviewed by all 9 agents and deemed NOT_RELEVANT or DEFENSE_IN_DEPTH:
1. **Unicode homoglyphs** (Cyrillic/Greek lookalikes): NOT_RELEVANT - Attack defeats itself.
   Homoglyphs in patterns won't match ASCII in real seeds; attacker would need to
   modify BOTH pattern AND target, which gains nothing. Seeds are audited.
2. **Test theater gaps** (vacuous assertions): FIX_LATER - Quality issue, not security.
   Current tests verify real behavior; theater detection is for new code.
3. **JS inline comment exclusion**: ALREADY_DONE - contraband_js.sh patterns work correctly.

**Architecture Cleanup (2026-01-29):**
- kernel.py: DELETED legacy Kernel class (~350 lines removed)
  - KEPT: Step budget infrastructure (get_step_budget, reset_step_budget, MAX_PROJECTION_STEPS)
  - DELETED: Kernel class, create_kernel(), compute_identity(), detect_stall(), gate_dispatch(), record_trace()
- Archived: `test_kernel_v0.py` moved to `tests/archive/legacy/`
- Created: `tests/structural/test_lambda_calculus_guardrails.py` (11 tests)
- Added: Tests for `is_kernel_intermediate()` (12 tests)
- Note: `MAX_PROJECTION_STEPS=50000` (kernel.py) is NOT used by step_kernel_mu which uses `max_steps=10000`

**Security Fuzzers (2026-01-29):**
- Created `tests/test_security_boundary_fuzzer.py` (24 tests) - validate_no_kernel_reserved_fields
  - Tests depth guards, nested smuggling, unicode homoglyphs, list traversal
- Created `tests/test_seed_integrity_fuzzer.py` (21 tests) - seed validation functions
  - Tests checksum tampering, structure validation, projection order security, injection attacks

**L2 Grounding & Boundary Validation (2026-01-29):**
- Fixed docstring false positive at eval_seed.py:70 (was being counted as debt)
- Updated SelfHosting.v0.md re: kernel.py cleanup (legacy Kernel class deleted)
- Created `tests/structural/test_l2_cursor_grounding.py` (7 tests) - proves linked-list cursor:
  - Verifies `_remaining` is structural (head/tail), not arithmetic index
  - Tests kernel.wrap creates _remaining from _projs linked list
  - Tests kernel.try consumes head, kernel.match_fail advances to tail
- Created `tests/test_boundary_validation_fuzzer.py` (27 tests) - boundary guards:
  - Tests assert_seed_pure with valid/invalid inputs (lambdas, functions, builtins)
  - Tests validate_type_tag whitelist enforcement (list/dict only)
  - Tests get_var_name validation (empty names, non-var sites)
- Created `tests/test_kernel_bridge_fuzzer.py` (26 tests) - kernel bridge functions:
  - Tests list_to_linked (preserves length, order, produces valid Mu)
  - Tests normalize_projection (pattern/body normalization)
  - Integration tests for projection list conversion

**Phase 8a IMPLEMENTED (2026-01-28):**

All 5 bootstrap primitives marked with `# BOOTSTRAP_PRIMITIVE`:
1. `eval_step` - `rcx_pi/selfhost/eval_seed.py:step()`
2. `mu_equal` - `rcx_pi/selfhost/mu_type.py:mu_equal()`
3. `max_steps` - `rcx_pi/selfhost/step_mu.py:241`
4. `stack_guard` - `rcx_pi/selfhost/mu_type.py:MAX_MU_DEPTH`
5. `projection_loader` - `rcx_pi/selfhost/seed_integrity.py:load_verified_seed()`

**mu_equal Bootstrap Primitive Review (2026-01-31):**
- **Phase 1 DONE**: eval_seed.py binding conflict detection now calls mu_equal (was inline json.dumps)
- **Phase 2 DEFERRED**: External reviewer proposed replacing json.dumps with structural recursion
- **9-agent consensus: NOT WORTH IT** - json.dumps IS structural equality for JSON data
  - Structural-proof: "Cannot find ONE example where json.dumps gives wrong answer"
  - Expert: "4 lines → 40-60 lines with identical semantics, both use host mechanisms"
  - Translator: "You're trading one set of Python dependencies for a different set"
- **L4 question remains open**: Can mu_equal become Mu projections? (comparison via pattern matching)
- **Parity fuzzer**: `tests/test_mu_equal_parity_fuzzer.py` proves equivalence (13 tests, 500+ inputs)

**Document updated with:**
- Scope and Self-Hosting Levels section
- EngineNews Compatibility section
- Hidden/Implicit Primitives section
- Known Limitations section

**Tests created:**
- `tests/structural/test_bootstrap_primitives.py` (36 tests)
- `tests/test_bootstrap_fuzzer.py` (18 property-based tests)

**See `docs/core/BootstrapPrimitives.v0.md`** for full specification.

**Phase 8b IMPLEMENTED (2026-01-28):**

Simplified step_kernel_mu to MECHANICAL operation:
1. Added `is_kernel_terminal()` - simple structural marker detection
2. Added `extract_kernel_result()` - mechanical unpacking
3. Removed ~20 lines of semantic branching from loop
4. Loop body now only checks structural markers + stall detection
5. Fixed empty container type preservation (KNOWN LIMITATION resolved):
   - `[]` now normalizes to `{"_type": "list"}` (was `None`)
   - `{}` now normalizes to `{"_type": "dict"}` (was `None`)
   - Denormalization correctly reverses typed sentinels
   - Normalization is now idempotent
6. All 2,100+ tests pass

**Tests created:**
- `tests/test_phase8b_mechanical_kernel.py` (31 tests)
- `tests/test_phase8b_grounding_gaps.py` (12 tests)

**Debt:** 12 (10 tracked decorators + 2 AST_OK bootstrap = L2 floor)

---

**Completed (Phase 7c):**
- [x] Created `mu/substrate/kernel.v1.json` with 7 kernel projections
- [x] 30 manual trace tests pass (success, failure, empty, fallthrough)
- [x] Created `match.v2.json` with context passthrough + match.fail catch-all
- [x] Created `subst.v2.json` with context passthrough
- [x] 20 integration tests pass (kernel → match → subst → kernel)
- [x] 7 agent review complete (2026-01-28)

**Completed (Phase 7d-1):**
- [x] Wired step_mu to structural kernel (kernel.v1 + match.v2 + subst.v2)
- [x] Added helpers: list_to_linked, normalize_projection, load_combined_kernel_projections
- [x] Updated test_step_mu_parity.py for behavioral difference (unbound vars stall instead of error)
- [x] All 106 core tests pass
- [x] 7-agent review identified execution loop still Python (honest assessment)
- [x] Added @host_iteration to step_kernel_mu (honest debt tracking)
- [x] 9-agent review of Phase 8 design completed (2026-01-28)

**Behavioral Change (7d-1):**
- **Before:** Unbound variables raised `KeyError`
- **After:** Unbound variables cause stall (return original input)
- This is more consistent with pure Mu semantics where errors become stalls

**PAUSED (requires Phase 8 implementation):**
- Phase 7d-2: Migrate projection_runner to step_mu
- Phase 7d-3: Eliminate projection_runner iteration
- Reason: 7d-1 moved the loop, didn't eliminate it. Phase 8 addresses this properly.

---

**Last updated:** 2026-02-07 (Gate 4 cutover complete; structural runtime is default)
**Next milestone:** Gate 5 - Meta-Circular Parity

**Gate Snapshot (Canonical):**
- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: IN_PROGRESS (parity verification and cleanup)

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

**Known Architectural Constraints:** See "Known Architectural Constraints" section in [`roadmap/MetaCircular_Boot0_GatePlan.md`](roadmap/MetaCircular_Boot0_GatePlan.md) for authoritative documentation of:
- Why kernel reserved fields block algorithm entry
- Why kernel-internal bypass exists for hybrid execution
- Why trace matching uses different matcher than execution
- Resolution path through Gates 3-5

**mu/ Folder Reorganization (2026-02-02):**
New organized structure makes architecture visible:
- `mu/substrate/` - Kernel VM: kernel.v1, match.v1, match.v2, subst.v1, subst.v2
- `mu/closures/` - Closure detection: recurrence.v1 (was enginenews), exhaustion.v1 (was exhaust)
- `mu/programs/` - Applications: rcx_engine.v1 (orchestrates recurrence + exhaustion)
- `mu/utilities/` - Helpers: classify.v1, eval.v1
- `mu/host/js/` - JavaScript bootstrap: eval_step.js
- `mu/host/python/selfhost` - Python bootstrap (symlink to rcx_pi/selfhost)

**Architectural Gap Discovery (2026-02-02):**
9-agent review of Step 6 revealed: match.v2.json is "linear only" but enginenews.v1 and exhaust.v1 require non-linear patterns. These seeds work via bootstrap (eval_seed) but CANNOT run through the meta-circular kernel. This was documented but not caught because tests passed.

**Response:**
- Added North Star #14 (execution layer declaration) and #15 (true self-hosting path)
- Added Cross-Seed Compatibility Check to AgentGuardrails.v0.md
- Created VECTOR item for Bootstrap-Structural Bridge (non-linear pattern support)
- Updated seed meta sections with `"execution_layer": "BOOTSTRAP"` (at the time)
- **Resolved by Gate 4 cutover (2026-02-07):** recurrence/exhaustion now run structurally by default via kernel bridge path

**Completed (Steps 1-6):**
1. ✅ Fixed JS security gaps (KERNEL_RESERVED_FIELDS, type tag validation, dict kv-pair fix)
2. ✅ Cross-substrate parity tests (20 vectors, tests/test_parity_python.py)
3. ✅ Phase 8d trace model in Python (run_mu_structural, tests/test_structural_trace.py)
4. ✅ Ported trace to JS (runStructural in mu/host/js/eval_step.js)
5. ✅ EngineNews structural closure detection (mu/closures/recurrence.v1.json, 9 projections)
6. ✅ Operator Exhaustion (mu/closures/exhaustion.v1.json, 11 projections)

**L3 COMPLETE:** All projections run on both Python and JavaScript with identical semantics.

**Proof:**
- [x] kernel.v1.json: 7 projections (Python ✓, JS ✓) - META_CIRCULAR
- [x] match.v2.json: 8 projections (Python ✓, JS ✓) - META_CIRCULAR (linear only)
- [x] subst.v2.json: 12 projections (Python ✓, JS ✓) - META_CIRCULAR
- [x] recurrence.v1.json: 9 projections (Python ✓, JS ✓) - META_CIRCULAR (bridge-backed)
- [x] exhaustion.v1.json: 11 projections (Python ✓, JS ✓) - META_CIRCULAR (bridge-backed)
- [x] Total: 47 core projections across 5 L3-complete seeds
- [x] Additional: 43 projections in utilities/programs/bridge (90 total across all mu/)
- [x] 5 EngineNews + 6 Exhaust parity vectors pass on both substrates

**Bootstrap-Structural Bridge: IMPLEMENTED (Capability Proven)**
- Location: `mu/bridge/bootstrap_structural.v1.json` (5 projections)
- Design doc: `docs/core/BootstrapStructuralBridge.v0.md`
- Execution path verified: bridge projections DO fire for non-linear patterns
- Bridge capability proven; standalone runners removed (dead code cleanup)
- Note: JS substrate loads bridge projections (`mu/host/js/eval_step.js`) for structural parity paths.
  Production algorithm execution is now structural via kernel bridge path.

**Current Algorithm Execution:**
- `run_algorithm_meta_circular()` defaults to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Bootstrap fallback exists only as explicit debug mode (`execution_mode="bootstrap"`)
- Algorithm runtime is now true meta-circular for recurrence/exhaustion production path

**Path to True Meta-Circular Algorithm Execution:**
1. Algorithm projections (recurrence.v1, exhaustion.v1) expect their own format:
   - State machine: `{_mode: "recurrence", _phase: "scan", ...}`
   - Traces: linked-list `{head: entry, tail: ...}`
2. Structural match/subst normalize everything to linked-list format
3. Options for true meta-circular:
   - **Option A:** Rewrite algorithm projections to work with fully normalized format
   - **Option B:** Create normalization-free structural matcher for algorithm use
   - **Option C:** Accept Python match/substitute as bootstrap primitive for algorithms

**Agent Validator Enhancement (2026-02-03):**
- `tools/validate_agent_compliance.py` now verifies CODE matches FILE:LINE
- `--strict` mode (used by hook) catches fabricated citations
- All 9 agent prompts updated with fabrication warning
