# Roadmap Document Manifest

> **This is the canonical reading-order source for the RCX repository.**
> It defines reading order, document roles, and linking rules.

## Canonical Reading Order

1. [`STATUS.md`](../STATUS.md) - Current state (L1-L4, phase, debt) - **ALWAYS READ FIRST**
2. [`TASKS.md`](../TASKS.md) - Authorized work, North Star invariants, governance
3. [`roadmap/MANIFEST.md`](./MANIFEST.md) - This file (reading order and linking rules)
4. [`ROADMAP.md`](../ROADMAP.md) - Sequence overview (what order, not current state)
5. [`mu/docs/core/Boot0Architecture.v0.md`](../mu/docs/core/Boot0Architecture.v0.md) - Staged bootstrap architecture
6. [`mu/docs/core/BootstrapPrimitives.v0.md`](../mu/docs/core/BootstrapPrimitives.v0.md) - 4 bootstrap primitives
7. [`mu/docs/core/SelfHosting.v0.md`](../mu/docs/core/SelfHosting.v0.md) - Self-hosting specification
8. [`mu/docs/core/Boot1LoopContract.v0.md`](../mu/docs/core/Boot1LoopContract.v0.md) - Boot1 recursive loop contract
9. [`roadmap/ContentAddressedMu.md`](./ContentAddressedMu.md) - Content-addressed Mu (Levels 0-1 implemented)
10. [`mu/docs/audit/MetaCircularReadiness.v1.md`](../mu/docs/audit/MetaCircularReadiness.v1.md) - Meta-circular readiness definition
11. [`mu/docs/core/UniversalEval.v0.md`](../mu/docs/core/UniversalEval.v0.md) - Universal eval (SINK/research, not deprecated)

## Document Roles

| Document | Role | Updates When |
|----------|------|--------------|
| `STATUS.md` | Current L1-L4 status, phase, debt | Any state change |
| `TASKS.md` | North Star, Ra/NEXT/VECTOR/SINK | Work promoted or completed |
| `ROADMAP.md` | Sequence view only | Reading order changes |
| `Hex0_Boot0_Checklist.md` | Operational CI and merge gates (`C1-C8`) | Gate policy changes |
| `MetaCircular_Boot0_GatePlan.md` | Gate definitions + exit criteria | Gate scope changes |
| `AlgorithmNormalizationSpec.v0.md` | Draft design spec | Design evolves |
| `MuHemispheresDesign.md` | Design spec (v0 core + engine integration) | Design evolves |
| `ContentAddressedMu.md` | Design spec (Levels 0-2 implemented, Level 3 deferred) | Design evolves |
| ~~`NormalizationDecisionMemo.md`~~ | Archived to `archive/docs/` (Round 24A) | N/A |

## Gate Levels and Execution Order

**Execution order (reordered per 9-agent review 2026-02-04):**
> Gate 1 → Gate 0 → Gate 2 → Gate 3 → Gate 4 → Gate 5

| Gates | Level | Scope | Status |
|-------|-------|-------|--------|
| 1, 0, 2-5 | L2/L3 | Structural algorithm execution | COMPLETE (2026-02-09) |
| 6-8 | L4 | Boot chain / substrate independence | PARKED |

**Rationale:** Spec (Gate 1) first; baseline freeze (Gate 0) immediately before code changes.

**Naming note:** Gate numbers (`0-8`) are conceptual architecture gates. `C1-C8` in `Hex0_Boot0_Checklist.md` are operational CI/merge gates.

## Linking Rules

1. **Roadmap docs link UP to canonical sources** - They reference STATUS.md and TASKS.md, never duplicate their content.

2. **Roadmap docs define sequence/design only** - They do not track current state or authorization.

3. **Gate completion updates TASKS.md** - When a gate completes, update TASKS.md (Ra section). The gate plan itself remains stable.

4. **Spec migration path**:
   - Draft specs live in `roadmap/`
   - Approved specs migrate to `mu/docs/core/`
   - Migration requires explicit review

5. **Baseline freeze (Gate 0)** - Introduced as TASKS.md NEXT item only when refactor begins. Does not need permanent tracking in roadmap docs.

## Why This Architecture

- **Single source of truth**: State in STATUS.md, authorization in TASKS.md
- **Roadmap as pointers**: Links to canonical docs, not copies of them
- **Minimal updates**: Only canonical docs change as work progresses
- **No drift**: Roadmap docs stay stable because they define sequence, not state
