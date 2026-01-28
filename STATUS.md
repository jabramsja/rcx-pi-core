# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

---

## Current Phase

```
PHASE: 6d
NAME: Algorithmic Self-Hosting Done
```

## Self-Hosting Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms are Mu projections | DONE (iteration is Python scaffolding) |
| **L2: Operational** | kernel loop (iteration/selection) is Mu projections | DESIGN |
| **L3: Full Bootstrap** | RCX runs RCX with no Python | FUTURE |

## What This Means

- **L1 Algorithmic self-hosting achieved** (see Self-Hosting Levels table): `match_mu()` and `subst_mu()` use Mu projections from seeds, not Python recursion
- **Kernel loop is still Python scaffolding**: The for-loop in `step_mu()` that tries projections in order is Python
- **Phase 7 in design**: `docs/core/MetaCircularKernel.v0.md` (VECTOR status) defines how to make kernel loop structural

## Debt Status

```
THRESHOLD: 11
CURRENT: 11 (8 tracked + 3 AST_OK)
TARGET: 9
```

## Agent Enforcement Guide

Use this to determine what standards apply NOW vs LATER:

| Condition | Status | Agent Action |
|-----------|--------|--------------|
| Match/subst must be Mu projections | L1 DONE | REQUIRED - enforce now |
| Kernel loop must be Mu projections | L2 DESIGN | ADVISORY - note as debt, don't fail |
| Python iteration in `step_mu` | Scaffolding | ACCEPTABLE - will be fixed in Phase 7 |
| Python recursion in algorithms | Semantic debt | FAIL - must use projections |
| Unmarked host operations | Debt violation | FAIL - must mark with `@host_*` |

## Phase 7 Blockers (Agent Findings - 2026-01-27)

These must be resolved before promoting Phase 7 from VECTOR to NEXT:

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

**Status:** Phase 7a COMPLETE (2026-01-27). Ready for Phase 7b.

**Completed:**
- [x] Created `seeds/kernel.v1.json` with 7 kernel projections
- [x] 30 manual trace tests pass (success, failure, empty, fallthrough)
- [x] Projection order regression tests pass

**Do:**
- Begin Phase 7b: Add `_match_ctx` passthrough to match.v2.json
- Add `_subst_ctx` passthrough to subst.v2.json
- Run parity tests (v2 seeds == v1 behavior)

**Do NOT:**
- Modify match.v1.json or subst.v1.json directly (copy to v2 first)
- Skip parity tests before integration

---

**Last updated:** 2026-01-27
**Next milestone:** Phase 7b complete (match/subst context passthrough)
