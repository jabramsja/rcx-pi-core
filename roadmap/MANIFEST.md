# Roadmap Document Manifest

> This manifest defines reading order, document roles, and linking rules for the roadmap folder.

## Reading Order

1. [`STATUS.md`](../STATUS.md) - Current state (L1-L4, phase, debt) - **ALWAYS READ FIRST**
2. [`TASKS.md`](../TASKS.md) - Authorized work, North Star invariants, governance
3. [`ROADMAP.md`](./ROADMAP.md) - Sequence overview (what order, not current state)
4. Gate/spec docs as needed for specific work

## Document Roles

| Document | Role | Updates When |
|----------|------|--------------|
| `STATUS.md` | Current L1-L4 status, phase, debt | Any state change |
| `TASKS.md` | North Star, Ra/NEXT/VECTOR/SINK | Work promoted or completed |
| `ROADMAP.md` | Sequence view only | Reading order changes |
| `MetaCircular_Boot0_GatePlan.md` | Gate definitions + exit criteria | Gate scope changes |
| `AlgorithmNormalizationSpec.v0.md` | Draft design spec | Design evolves |
| `MuHemispheresDesign.md` | Design spec (v0 core + engine integration IMPLEMENTED) | Design evolves |
| `ContentAddressedMu.md` | Design spec (Levels 0-2 implemented, Level 3 deferred) | Design evolves |
| `NormalizationDecisionMemo.md` | Decision authorization | Rarely (decisions are final) |

## Gate Levels and Execution Order

**Execution order (reordered per 9-agent review 2026-02-04):**
> Gate 1 → Gate 0 → Gate 2 → Gate 3 → Gate 4 → Gate 5

| Gates | Level | Scope | Status |
|-------|-------|-------|--------|
| 1, 0, 2-5 | L2/L3 | Structural algorithm execution | COMPLETE (2026-02-09) |
| 6-8 | L4 | Boot chain / substrate independence | PARKED |

**Rationale:** Spec (Gate 1) first; baseline freeze (Gate 0) immediately before code changes.

## Linking Rules

1. **Roadmap docs link UP to canonical sources** - They reference STATUS.md and TASKS.md, never duplicate their content.

2. **Roadmap docs define sequence/design only** - They do not track current state or authorization.

3. **Gate completion updates TASKS.md** - When a gate completes, update TASKS.md (Ra section). The gate plan itself remains stable.

4. **Spec migration path**:
   - Draft specs live in `roadmap/`
   - Approved specs migrate to `docs/core/`
   - Migration requires explicit review

5. **Baseline freeze (Gate 0)** - Introduced as TASKS.md NEXT item only when refactor begins. Does not need permanent tracking in roadmap docs.

## Why This Architecture

- **Single source of truth**: State in STATUS.md, authorization in TASKS.md
- **Roadmap as pointers**: Links to canonical docs, not copies of them
- **Minimal updates**: Only canonical docs change as work progresses
- **No drift**: Roadmap docs stay stable because they define sequence, not state
