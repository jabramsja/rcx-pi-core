# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

---

## Current Phase

```
PHASE: 7d-1
NAME: step_mu Wired to Structural Kernel
```

## Self-Hosting Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms are Mu projections | DONE (iteration is Python scaffolding) |
| **L2: Operational** | kernel loop (iteration/selection) is Mu projections | PARTIAL (selection structural, execution Python) |
| **L3: Full Bootstrap** | RCX runs RCX with no Python | FUTURE |

**Terminology Note:** The "kernel" in L2 refers to `kernel.v1.json` (7 structural Mu projections), NOT the `Kernel` class in kernel.py (Python scaffolding for hash/trace/dispatch). See `docs/core/MetaCircularKernel.v0.md` for full clarification.

## What This Means

- **L1 Algorithmic self-hosting achieved** (see Self-Hosting Levels table): `match_mu()` and `subst_mu()` use Mu projections from seeds, not Python recursion
- **L2 Operational PARTIAL**: Projection SELECTION is structural (linked-list cursor in kernel.v1), but projection EXECUTION still uses Python for-loop in `step_kernel_mu`
- **Phase 7d-1 complete**: `step_mu()` delegates to `step_kernel_mu()` which uses kernel projections for selection. The execution loop remains Python (marked with @host_iteration)
- **True L2 requires Phase 8**: Recursive kernel projections that eliminate the execution loop

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

## Debt Status

```
THRESHOLD: 15
CURRENT: 14 (11 tracked + 3 AST_OK)
TARGET: 12 (deferred to Phase 8c+)
```

**Debt breakdown:**
- @host_recursion: 3 (eval_seed match/substitute)
- @host_builtin: 3 (eval_seed, deep_eval)
- @host_iteration: 3 (run_mu, step_kernel_mu, projection_runner)
- @host_mutation: 2 (eval_seed, deep_eval)
- AST_OK bootstrap: 3

**Phase 8b outcome (2026-01-28):**
- Simplified step_kernel_mu to MECHANICAL operation (no semantic branching)
- Added `is_kernel_terminal()` - simple structural marker detection
- Added `extract_kernel_result()` - mechanical unpacking
- Loop body: ~35 lines → ~15 lines
- eval_step reclassified as BOOTSTRAP_PRIMITIVE (not debt)
- Net debt change: 15 → 14

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

## Key Files

- Design doc: `docs/core/MetaCircularKernel.v0.md`
- Self-hosting: `rcx_pi/selfhost/` (match_mu, subst_mu, step_mu)
- Seeds: `seeds/match.v1.json`, `seeds/subst.v1.json`, `seeds/classify.v1.json`, `seeds/eval.v1.json`
- Task list: `TASKS.md`
- Grounding tests: `tests/structural/` (status, seeds, type tags, projection order)

---

## Recommended Next Action

**Status:** Phase 8 DESIGN v2 READY (2026-01-28). 9-agent review reached consensus on honest boundaries.

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

**Debt reduction:** 15 → 14 (eval_step reclassified as BOOTSTRAP_PRIMITIVE)

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

**Last updated:** 2026-01-28
**Next milestone:** Phase 8c (oscillation detection) or Phase 8d (EngineNews trace model)
