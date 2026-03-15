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
9. [`mu/docs/core/HemisphereExecutionChecklist.v0.md`](../mu/docs/core/HemisphereExecutionChecklist.v0.md) - Hemisphere Metabolization execution gates (E1-E5)
10. [`roadmap/ContentAddressedMu.md`](./ContentAddressedMu.md) - Content-addressed Mu (Levels 0-1 implemented)
11. [`mu/docs/audit/MetaCircularReadiness.v1.md`](../mu/docs/audit/MetaCircularReadiness.v1.md) - Meta-circular readiness definition
12. [`mu/docs/core/UniversalEval.v0.md`](../mu/docs/core/UniversalEval.v0.md) - Universal eval (SINK/research, not deprecated)
13. [`mu/docs/core/NorthStarSemantics.v0.md`](../mu/docs/core/NorthStarSemantics.v0.md) - Canonical semantic policy lock (undefined-as-structure, zero canonicalization, bounded non-closure, routing tie-break)
14. [`mu/docs/core/Why_RCX_PI_VM_EXISTS.md`](../mu/docs/core/Why_RCX_PI_VM_EXISTS.md) - Why the host is a dumb bootstrap (doctrine — referenced by CLAUDE.md rule 9)
15. [`mu/docs/core/StructuralPurity.v0.md`](../mu/docs/core/StructuralPurity.v0.md) - Structural purity guardrails (doctrine — referenced by FOUNDER_SESSION_BOOTSTRAP.md)

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
| `HemisphereExecutionChecklist.v0.md` | Execution gates (E1-E5) for Hemisphere Metabolization | Gate evidence updates |
| `ContentAddressedMu.md` | Design spec (Levels 0-2 implemented, Level 3 deferred) | Design evolves |
| `NorthStarSemantics.v0.md` | Canonical semantic policy lock (undefined, zero, non-closure, tie-break) | Semantic decisions locked or deferred |
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

## L4 Execution Contracts

| Document | Role |
|----------|------|
| [`roadmap/L4ExecutionContract.v2.md`](L4ExecutionContract.v2.md) | Wave classification policy v2 (L4_STRUCTURAL / L4_ENABLER / MAINTENANCE) |
| [`roadmap/L4ExecutionContract.v1.md`](L4ExecutionContract.v1.md) | Superseded v1 (historical reference) |
| [`roadmap/CodexClaudeAuditContract.v1.md`](CodexClaudeAuditContract.v1.md) | Prompt quality and audit discipline for multi-wave sessions |

## Canonical L4 Research Packet

Governance lane status (SINK or VECTOR) does not remove active evidence docs from MANIFEST discoverability. These documents contain live research evidence (D001-D003 feasibility results) that must remain findable regardless of governance classification. The G8 decision path is VECTOR P1; the full L4 rewrite is SINK S1.

| Document | Role |
|----------|------|
| [`mu/docs/core/L4ExitChecklist.v0.md`](../mu/docs/core/L4ExitChecklist.v0.md) | Gate definitions (G1-G8) and current pass/fail status |
| [`mu/docs/core/L4MicroAbi.v0.md`](../mu/docs/core/L4MicroAbi.v0.md) | ABI surface mapped to L4 gates |
| [`mu/docs/core/G8CpsFeasibility.v0.md`](../mu/docs/core/G8CpsFeasibility.v0.md) | H1-H3 hypotheses and experimental results (D001-D003) |
| [`mu/docs/core/L4DecisionCard.v0.md`](../mu/docs/core/L4DecisionCard.v0.md) | Decision cards (D001-D004) with evidence and outcomes |

## Active Core Specifications

These `mu/docs/core/` documents have DOC_STATUS TYPE = DESIGN_SPEC or IMPLEMENTATION and must remain listed here for discoverability. Enforced by `tests/docs/test_manifest_discoverability.py`.

| Document | TYPE | Domain |
|----------|------|--------|
| [`mu/docs/core/BootstrapStructuralBridge.v0.md`](../mu/docs/core/BootstrapStructuralBridge.v0.md) | DESIGN_SPEC | Structural bridge bootstrap |
| [`mu/docs/core/EVAL_SEED.v0.md`](../mu/docs/core/EVAL_SEED.v0.md) | DESIGN_SPEC | Seed evaluation |
| [`mu/docs/core/EngineNewFixContract.v0.md`](../mu/docs/core/EngineNewFixContract.v0.md) | IMPLEMENTATION | Engine fix contract |
| [`mu/docs/core/EngineNewsStructural.v0.md`](../mu/docs/core/EngineNewsStructural.v0.md) | IMPLEMENTATION | Engine news (structural) |
| [`mu/docs/core/MetaCircularKernel.v0.md`](../mu/docs/core/MetaCircularKernel.v0.md) | IMPLEMENTATION | Meta-circular kernel |
| [`mu/docs/core/MuDagAbiSpike.v0.md`](../mu/docs/core/MuDagAbiSpike.v0.md) | DESIGN_SPEC | DAG ABI spike |
| [`mu/docs/core/ObserverEventContract.v0.md`](../mu/docs/core/ObserverEventContract.v0.md) | DESIGN_SPEC | Observer events |
| [`mu/docs/core/OntologyPromotionContract.v0.md`](../mu/docs/core/OntologyPromotionContract.v0.md) | DESIGN_SPEC | Ontology promotion |
| [`mu/docs/core/OperatorExhaustion.v0.md`](../mu/docs/core/OperatorExhaustion.v0.md) | IMPLEMENTATION | Operator exhaustion |
| [`mu/docs/core/RCXEngine.v0.md`](../mu/docs/core/RCXEngine.v0.md) | DESIGN_SPEC | Engine pipeline |
| [`mu/docs/core/RCXKernel.v0.md`](../mu/docs/core/RCXKernel.v0.md) | DESIGN_SPEC | Kernel architecture |
| [`mu/docs/core/RecursiveKernel.v0.md`](../mu/docs/core/RecursiveKernel.v0.md) | DESIGN_SPEC | Recursive kernel |
| [`mu/docs/core/TypedNumericEnvelopes.v0.md`](../mu/docs/core/TypedNumericEnvelopes.v0.md) | DESIGN_SPEC | P6 VECTOR: cross-substrate int/float lexical parity decision |
| [`mu/docs/core/recurrence_v2_design.md`](../mu/docs/core/recurrence_v2_design.md) | IMPLEMENTATION | Recurrence v2 |

## Agent Infrastructure

These `mu/docs/agents/` documents define the multi-agent review system and bridge collaboration protocol.

| Document | TYPE | Domain |
|----------|------|--------|
| [`mu/docs/agents/AgentBridgeProtocol.v0.md`](../mu/docs/agents/AgentBridgeProtocol.v0.md) | REFERENCE | Claude ↔ Codex bridge protocol |
| [`mu/docs/agents/AgentRunbook.v0.md`](../mu/docs/agents/AgentRunbook.v0.md) | REFERENCE | Agent runner usage and workflow tiers |
| [`mu/docs/agents/AgentRig.v0.md`](../mu/docs/agents/AgentRig.v0.md) | REFERENCE | Agent trust model and architecture |
| [`mu/docs/agents/AgentGuardrails.v0.md`](../mu/docs/agents/AgentGuardrails.v0.md) | REFERENCE | Agent output format requirements |

## Why This Architecture

- **Single source of truth**: State in STATUS.md, authorization in TASKS.md
- **Roadmap as pointers**: Links to canonical docs, not copies of them
- **Minimal updates**: Only canonical docs change as work progresses
- **No drift**: Roadmap docs stay stable because they define sequence, not state
