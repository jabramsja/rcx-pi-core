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
| **L2: Operational** | kernel loop (iteration/selection) is Mu projections | IN PROGRESS (7d-1 done, 7d-2/3 pending) |
| **L3: Full Bootstrap** | RCX runs RCX with no Python | FUTURE |

## What This Means

- **L1 Algorithmic self-hosting achieved** (see Self-Hosting Levels table): `match_mu()` and `subst_mu()` use Mu projections from seeds, not Python recursion
- **L2 Operational partially achieved**: `step_mu()` now uses structural kernel projections (kernel.v1 + match.v2 + subst.v2) instead of Python for-loop
- **Phase 7d-1 complete**: `docs/core/MetaCircularKernel.v0.md` describes the kernel design; step_mu is now wired to it

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
TARGET: 12 (via phased reduction: 15 → 14 → 13 → 12)
```

**Debt breakdown:**
- @host_recursion: 3 (eval_seed match/substitute)
- @host_builtin: 3 (eval_seed, deep_eval)
- @host_iteration: 3 (run_mu, eval_seed.step, projection_runner) - step_mu removed in 7d-1
- @host_mutation: 2 (eval_seed, deep_eval)
- AST_OK bootstrap: 3

**Phase 7d debt reduction plan (revised per structural-proof agent 2026-01-28):**
- 7d-1: Remove step_mu @host_iteration → 15 → 14 ✓ DONE
- 7d-2: Deprecate eval_seed.step → 14 → 13
- 7d-3: Eliminate projection_runner → 13 → 12

Note: run_mu outer loop is scaffolding (L3 boundary), not removed in Phase 7.
Note: Original target was 9, but structural-proof analysis shows only 3 @host_iteration markers are removable in Phase 7 (step_mu, eval_seed.step, projection_runner). The 4th (run_mu) remains as L3 boundary.

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

**Status:** Phase 7d-1 COMPLETE (2026-01-28). step_mu now uses structural kernel.

**Completed (Phase 7c):**
- [x] Created `seeds/kernel.v1.json` with 7 kernel projections
- [x] 30 manual trace tests pass (success, failure, empty, fallthrough)
- [x] Created `match.v2.json` with context passthrough + match.fail catch-all
- [x] Created `subst.v2.json` with context passthrough
- [x] 20 integration tests pass (kernel → match → subst → kernel)
- [x] 7 agent review complete (2026-01-28)

**Completed (Phase 7d-1):**
- [x] Wired step_mu to structural kernel (kernel.v1 + match.v2 + subst.v2)
- [x] Removed @host_iteration from step_mu (debt 15 → 14)
- [x] Added helpers: list_to_linked, normalize_projection, load_combined_kernel_projections
- [x] Updated test_step_mu_parity.py for behavioral difference (unbound vars stall instead of error)
- [x] All 106 core tests pass

**Behavioral Change (7d-1):**
- **Before:** Unbound variables raised `KeyError`
- **After:** Unbound variables cause stall (return original input)
- This is more consistent with pure Mu semantics where errors become stalls

**Do (ready to proceed):**
- Phase 7d-2: Migrate projection_runner to step_mu
- Phase 7d-3: Eliminate projection_runner iteration

**Do NOT:**
- Remove debt markers until Python iteration actually replaced
- Expect 13→9 in Phase 7 (structural-proof: realistic target is 12, run_mu stays)

---

**Last updated:** 2026-01-28
**Next milestone:** Phase 7d-2 (migrate projection_runner to step_mu)
