# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

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
| **L2: Operational** | kernel state machine EXPRESSED as Mu projections | PARTIAL (selection structural, execution Python) |
| **L3: Full Bootstrap** | RCX runs RCX on minimal substrate | FUTURE (Forth-style bootstrap - see below) |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (research question) |

**Terminology Honesty:**
- "Projection-based" means the ALGORITHM is expressed as Mu projections (data)
- Python's `eval_step()` EXECUTES those projections (like Forth's NEXT executes threaded code)
- This is NOT "self-hosting" in the traditional sense - Python is the execution engine
- The "kernel" in L2 refers to `kernel.v1.json` (7 projections), NOT the deprecated `Kernel` class

## What This Means

- **L1 Algorithmic DONE**: `match_mu()` and `subst_mu()` algorithms are expressed as Mu projections in seeds. Python's `eval_step()` executes them.
- **L2 Operational PARTIAL**: Projection SELECTION is structural (linked-list cursor in kernel.v1). Projection EXECUTION is Python (`for` loop in `step_kernel_mu`).
- **Python's role**: `eval_step()` is a bootstrap primitive (like Forth's NEXT). It applies projections using Python pattern matching. This is irreducible in current architecture.

## L2 Completion Criteria (Explicit)

**L2 PARTIAL (current status):**
- [x] Kernel state machine is 7 Mu projections (`kernel.v1.json`)
- [x] Match v2 with context passthrough (8 projections, `_match_ctx`)
- [x] Subst v2 with context passthrough (12 projections, `_subst_ctx`)
- [x] Projection selection uses linked-list cursor (`_remaining` field, no index arithmetic)
- [x] `step_kernel_mu()` wired to use structural kernel
- [x] Security hardening complete (12 reserved fields, deep validation)
- [ ] Python for-loop still drives kernel execution (`step_mu.py:397-410`)

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

### L3 Target: Forth-Style Bootstrap (NEXT)

L3 is defined as **Forth-style bootstrap** - algorithms as projections, executed by minimal primitives:

| Component | Role | Precedent |
|-----------|------|-----------|
| **Bootstrap Primitives** | eval_step, mu_equal, stack_guard, projection_loader | Like Forth's NEXT, Lisp's EVAL |
| **Algorithms** | match, subst, classify, eval - expressed as Mu projections | Threaded code in Forth |
| **Python's Role** | Substrate for bootstrap primitives | Inner interpreter in Forth |

**What "self-hosting" means at L3:**
- All algorithms are Mu projections (data, not code)
- Bootstrap primitives execute projections (irreducible)
- Python is explicitly marked substrate, not hidden dependency
- This is what Lisp, Forth, and PyPy actually do

### L4 Research: True Self-Hosting (SINK)

L4 asks: **Can bootstrap primitives be eliminated or made substrate-independent?**

| Primitive | L4 Question | Possible Path |
|-----------|-------------|---------------|
| `eval_step` | Can it be a projection? | Requires meta-level substrate |
| `mu_equal` | Can structural equality be structural? | Possibly via comparison projections |
| `stack_guard` | Can depth be Mu data? | Count in Mu, not Python |
| `projection_loader` | Can Mu load Mu? | Possibly, with file I/O primitive |

**L4 Status:** Open research question in SINK. Not promised, not ruled out.

**Key Insight:** L3 doesn't close L4 - it opens it. By making bootstrap primitives explicit and minimal, we know exactly what would need to change. If L4 is possible, L3 is the path to it.

**The Honest Answer:** Forth has NEXT. Lisp has EVAL. Some primitive always exists. The question is: what's the minimal primitive, and can it be substrate-independent (e.g., hardware, WASM)?

## Development Workflow

**Before committing, run:**
```bash
./tools/pre-commit-check.sh       # Full checks: syntax, contraband, AST, docs
./tools/check_docs_consistency.sh # Verify STATUS.md matches reality
./tools/debt_dashboard.sh         # Check debt doesn't exceed ceiling
```

**Git hook (auto-runs on commit):**
```bash
# Install once:
ln -sf ../../tools/pre-commit-doc-check .git/hooks/pre-commit
```

The pre-commit hook checks doc consistency, debt ceiling, and warns if core code changed without STATUS.md update. See `CLAUDE.md` for full workflow details.

## Testing Tiers

```
Tier 1: Fast Audit    ./tools/audit_fast.sh    ~3 min   Core tests only
Tier 2: Full Audit    ./tools/audit_all.sh     ~5-8 min Core + Fuzzer tests
Tier 3: Stress Tests  pytest tests/stress/     ~10+ min Deep edge cases
```

| Tier | What It Tests | When to Run |
|------|---------------|-------------|
| Tier 1 | Core algorithms, syntax, contraband | Local iteration |
| Tier 2 | All tests including 200+ example fuzzers | Before push, CI |
| Tier 3 | Deep nesting, wide structures, pathological inputs | Comprehensive validation |

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
THRESHOLD: 14
CURRENT: 13 (9 tracked decorators + 4 AST_OK)
TARGET: 12 (deferred to Phase 8c+)
```

**Debt breakdown:**
- @host_recursion: 2 (eval_seed match/substitute)
- @host_builtin: 3 (eval_seed, deep_eval)
- @host_iteration: 2 (run_mu, step_kernel_mu)
- @host_mutation: 2 (eval_seed, deep_eval)
- AST_OK bootstrap: 4 (includes MAX_VALIDATION_DEPTH stack guard)

**Scaffolding ceiling (prevents unbounded accumulation):**
- AST_OK:infra ceiling: 35 (current ~31)
- AST_OK:infra is NOT debt, but capped to prevent drift

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
  - KERNEL_RESERVED_FIELDS: 12 fields (added `_step`, `_projs`)
  - Depth guard fails CLOSED (raises ValueError at depth > 100)
- Net debt: 13 (9 tracked decorators + 4 AST_OK)

**Phase 7d-2/7d-3 PAUSED:**
- Original plan assumed 7d-1 eliminated the loop (it didn't, it moved it)
- 7d-2/7d-3 depend on 7d-1 being complete - they are not viable until Phase 8c+
- See phase-7d-complete-design.md for full agent analysis

Note: run_mu outer loop is scaffolding (L3 boundary), not removed in Phase 7.

## Agent Enforcement Guide

Use this to determine what standards apply NOW vs LATER:

| Condition | Status | Agent Action |
|-----------|--------|--------------|
| Match/subst must be Mu projections | L1 DONE | REQUIRED - enforce now |
| Kernel loop must be Mu projections | L2 PARTIAL | `step_mu` uses structural kernel; `run_mu` still Python |
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
- [x] `tests/structural/test_projection_loader.py` - Factory loader tests (36 tests)
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
- Seeds: `seeds/match.v1.json`, `seeds/subst.v1.json`, `seeds/classify.v1.json`, `seeds/eval.v1.json`
- Task list: `TASKS.md`
- Grounding tests: `tests/structural/` (status, seeds, type tags, projection order, audit claims)

---

## Recommended Next Action

**Status:** Phase 8b COMPLETE (2026-01-28). 9-agent review SHIP verdict. 1480+ tests passing.

**Security Hardening (2026-01-29, 7-agent review):**
- Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
- New code using deprecated Kernel will FAIL tests (not just warn)
- Removed `TestKernelIntegration` (4 tests) - used deprecated Kernel
- Created `tests/structural/test_step_budget.py` (18 tests) for ACTIVE infrastructure
- Created `tests/structural/test_audit_claims_grounding.py` (18 tests) for audit verification
- Added `tests/archive/README.md` documenting archive purpose

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
6. All 1343+ tests pass

**Tests created:**
- `tests/test_phase8b_mechanical_kernel.py` (31 tests)
- `tests/test_phase8b_grounding_gaps.py` (12 tests)

**Debt:** 14 (eval_step reclassified as BOOTSTRAP_PRIMITIVE; MAX_VALIDATION_DEPTH added; debt_dashboard.sh comment counting corrected)

---

**Completed (Phase 7c):**
- [x] Created `seeds/kernel.v1.json` with 7 kernel projections
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

**Last updated:** 2026-01-29
**Next milestone:** Phase 8c (oscillation detection) or Phase 8d (EngineNews trace model)
