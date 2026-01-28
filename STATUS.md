# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

---

## Current Phase

```
PHASE: 6d
NAME: Algorithmic Self-Hosting Complete
```

## Self-Hosting Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms are Mu projections | COMPLETE |
| **L2: Operational** | kernel loop (iteration/selection) is Mu projections | DESIGN |
| **L3: Full Bootstrap** | RCX runs RCX with no Python | FUTURE |

## What This Means

- **Algorithmic self-hosting achieved**: `match_mu()` and `subst_mu()` use Mu projections from seeds, not Python recursion
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
| Match/subst must be Mu projections | L1 COMPLETE | REQUIRED - enforce now |
| Kernel loop must be Mu projections | L2 DESIGN | ADVISORY - note as debt, don't fail |
| Python iteration in `step_mu` | Scaffolding | ACCEPTABLE - will be fixed in Phase 7 |
| Python recursion in algorithms | Semantic debt | FAIL - must use projections |
| Unmarked host operations | Debt violation | FAIL - must mark with `@host_*` |

## Key Files

- Design doc: `docs/core/MetaCircularKernel.v0.md`
- Self-hosting: `rcx_pi/selfhost/` (match_mu, subst_mu, step_mu)
- Seeds: `seeds/match.v1.json`, `seeds/subst.v1.json`, `seeds/classify.v1.json`
- Task list: `TASKS.md`

---

**Last updated:** 2026-01-27
**Next milestone:** Phase 7 promotion from VECTOR to NEXT
