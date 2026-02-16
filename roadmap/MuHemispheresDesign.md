# Mu-Only Hemispheres Design Outline (Draft)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document defines DESIGN only. V0 core + engine integration IMPLEMENTED.

Status: v0 core + engine integration IMPLEMENTED (2026-02-11). See `TASKS.md` for current work items and `STATUS.md` for hemisphere parity status.

## Purpose
Define native structural routing states for RCX: `r_null`, `r_inf`, `r_a`, `lobes`, and `sink`. Routing must be expressed as Mu projections, not host logic.

## Scope
1. Routing semantics and promotion rules for hemisphere placement.
2. Minimal structural data model for hemisphere entries.
3. Execution-layer requirements and tests.

## Definitions
1. `r_null`: repository for void or zero-structure outputs.
2. `r_inf`: repository for unbounded or diverging structures.
3. `r_a`: repository for closed, stable structures (post-closure).
4. `lobes`: repository for emerging structures pending closure.
5. `sink`: repository for contradictions or rejected structures that may later be re-expressed.

## Data Model (Structural)
1. Each hemisphere is a Mu linked list of entries.
2. Each entry is a Mu structure with explicit fields such as `state`, `trace_ref`, `closure_flag`, and `origin`.
3. Entries must be deterministic and free of host-only metadata.

## Routing Rules (High Level)
1. First encounter of a structure routes to `lobes`.
2. Second independent encounter with closure evidence promotes to `r_a`.
3. Contradictions or non-resolvable conflicts route to `sink`.
4. Divergence or unbounded growth routes to `r_inf`.
5. Zero-structure or void outputs route to `r_null`.

## Promotion and Re-Expression

**CURRENT_ENFORCED** (proven by existing seeds and tests):
1. Engine signals are classified by projection priority: exhaustion > null > closure > stall > default.
2. Each signal routes to exactly one bucket via `hemispheres.v1.json` (12 projections).
3. 5-bucket shape parity enforced across Python and JS substrates.
4. Fail-closed on invalid engine_result or hemisphere shape.

**FUTURE_TARGET** (VECTOR — no projections exist, no implementation yet):
1. `lobes` to `r_a` requires explicit closure evidence (structural, not host-derived).
2. `sink` re-expression (metabolization): sink contents re-enter the system via r_inf or r_null for processing, then route to lobes/r_a or recycle back to sink. Requires new metabolization projections in `hemispheres.v1.json` (or a v2 seed). See `TASKS.md` VECTOR: "Hemisphere Metabolization Contract".
3. Stall recovery: stalled structures check lobes first (preferred recovery), then sink if lobes cannot accept. Requires lobes-compatibility predicate (not yet designed).
4. Any promotion or re-expression must be observable and traceable with deterministic events.

## Execution Layer Requirements
1. Routing projections must run in the meta-circular kernel after normalization refactor.
2. If a bootstrap path is used during transition, it must be declared and tested as such.

## Observability
1. Routing decisions must be representable as trace events without violating v2 determinism.
2. Observability must not become a new semantic channel.

## Tests Required
1. Parity vectors for routing decisions across Python and JS substrates.
2. Execution-path verification tests proving routing runs via structural projections.
3. Determinism fuzzers for routing stability.

## Integration (IMPLEMENTED 2026-02-11)

Engine output flows to hemisphere routing via `run_engine_with_routing()`:

    projections → run_engine_pipeline() → engine_result (8-field)
                                           ↓
                                  run_hemisphere_routing(engine_result, hemispheres)
                                           ↓
                                  updated hemispheres (5 buckets)

Usage:

    from rcx_pi.selfhost.step_mu import run_engine_with_routing
    result = run_engine_with_routing(projs, input_value)
    # result["engine_result"] — 8-field engine output
    # result["hemispheres"] — updated 5-bucket dict

Fail-closed validation on both input (hemisphere shape) and output (routing result shape).
`hash_trace_for_recurrence` cycle guard added (visited set + iteration cap).

**JS L3 Parity (2026-02-12):** All 4 orchestration functions ported to `mu/host/js/eval_step.js`:
`runEnginePipeline()`, `hashTraceForRecurrence()`, `runHemisphereRouting()`, `runEngineWithRouting()`.
rcx_engine.v1.json loaded in JS (9 seeds total). 36 cross-substrate parity tests pass.

## FUTURE_TARGET: Hemisphere Metabolization Contract (VECTOR)

> **Status:** VECTOR — design only. No projections exist. No implementation. Not enforced.
> **Authorization:** `TASKS.md` VECTOR: "Hemisphere Metabolization Contract".
> **Prerequisite:** CURRENT_ENFORCED routing (12 projections) must remain green.

### Not Implemented

Nothing in this section is implemented, tested, or enforced. The projections listed below are design sketches only. Implementation requires explicit VECTOR → NEXT promotion in `TASKS.md` with all promotion criteria met.

### Cycle Definition

    sink → (r_inf | r_null) metabolization → (lobes | r_a) storage → residual → sink

Hemispheres r_inf and r_null are dialectically opposed: r_inf absorbs unbounded/diverging forms, r_null absorbs void/zero forms. This opposition drives structural change. Material that cannot be metabolized recycles to sink.

### Phase Breakdown

1. **Intake:** Engine result with exhaustion or contradiction signal enters sink via existing `hemisphere.classify.exhaustion` projection (CURRENT_ENFORCED).

2. **Metabolization:** r_inf and r_null inspect sink entries and absorb forms matching their domain.
   - r_inf takes unbounded/diverging structures from sink.
   - r_null takes void/zero-structure forms from sink.
   - Structural predicate required: what distinguishes "unbounded" from "void" at the Mu level. Must not use host-only heuristics.

3. **Recovery:** Stalled structures attempt lobes first (preferred recovery), then sink if lobes cannot accept.
   - Requires a lobes-compatibility predicate (structural, not host-derived).
   - Founder directive: "If stalled, check lobes first, then sink."

4. **Promotion:** Lobes entries with closure evidence promote to r_a.
   - Closure evidence must be structural (e.g., closure_flag from recurrence detection).
   - Consistent with existing routing rule: closure_detected → r_a.

5. **Residual:** Unresolvable material cycles back to sink for potential future re-expression.

### Missing Projection IDs (Design Spec)

| Projection ID | Phase | Pattern Sketch | Body Sketch |
|---------------|-------|----------------|-------------|
| `hemisphere.metabolize.sink_to_r_inf` | metabolization | `{metabolize_mode: "scan_sink", sink_entry: {state: <unbounded>, ...}, ...}` | `{metabolize_mode: "route", target: "r_inf", entry: ..., remaining_sink: ...}` |
| `hemisphere.metabolize.sink_to_r_null` | metabolization | `{metabolize_mode: "scan_sink", sink_entry: {state: null, ...}, ...}` | `{metabolize_mode: "route", target: "r_null", entry: ..., remaining_sink: ...}` |
| `hemisphere.recover.stall_to_lobes` | recovery | `{recover_mode: "check_stall", stalled_entry: ..., lobes: <non_null>, ...}` | `{recover_mode: "route", target: "lobes", entry: ..., ...}` |
| `hemisphere.recover.stall_to_sink` | recovery | `{recover_mode: "check_stall", stalled_entry: ..., lobes: null, ...}` | `{recover_mode: "route", target: "sink", entry: ..., ...}` |
| `hemisphere.promote.lobes_to_r_a` | promotion | `{promote_mode: "check_closure", lobes_entry: {closure_flag: true, ...}, ...}` | `{promote_mode: "route", target: "r_a", entry: ..., remaining_lobes: ...}` |
| `hemisphere.recycle.residual_to_sink` | residual | `{recycle_mode: "drain", source_bucket: <name>, unresolvable_entry: ..., ...}` | `{recycle_mode: "route", target: "sink", entry: ..., ...}` |

Pattern/body sketches are structural intent only. Final patterns must be valid Mu with linear-only variables (consistent with hemispheres.v1.json).

### Trigger Semantics

**Automatic run mode:** After each engine → hemisphere routing cycle, run one metabolization pass over all buckets. Single pass, deterministic. Implementation: new host function `run_hemisphere_metabolize(hemispheres)` wrapping metabolization projections, called after `run_hemisphere_routing` in `run_engine_with_routing`.

**Manual/debug step mode:** Expose step-by-step metabolization via `step_kernel_mu` with metabolization projections. No new host function needed. Debug tooling wraps with trace output.

Both modes required per founder directive.

### Engine Exception Policy Dependency

**Option A (current, active):** Engine raises RuntimeError/RcxError on exhaustion and stall. Structure is lost — never reaches hemisphere routing. Sink never receives failed engine structures.

**Option B (deferred):** Engine catches exhaustion/stall, synthesizes terminal engine_result with failure signals, returns to caller. Hemisphere routing classifies to sink. Requires:
- Synthesized engine_result MUST route to sink (never lobes/r_a/r_inf/r_null)
- Adversarial test: forged synthesized result with closure=true must still sink (exhaustion dominates)
- Both substrates produce identical synthesized results (L3 parity)

Option B enables metabolization (structures reach sink instead of being lost). Enable ONLY when metabolization projections are designed and sink-safety invariants are tested.

Code touchpoints for Option B (when promoted):
- Python: `step_mu.py:1466-1469` (stall), `step_mu.py:1518-1521` (exhaustion)
- JS: `eval_step.js:1869-1872` (stall), `eval_step.js:1921-1924` (exhaustion)

### Promotion Criteria (VECTOR → NEXT)

All must be met before any implementation begins:
1. Re-expression trigger model locked (automatic + manual/debug).
2. At least 4 metabolization projection specs drafted with valid Mu pattern/body.
3. Extended truth-table coverage criteria defined (≥8 metabolization transitions).
4. Engine exception policy Option B designed with sink-safety invariants.
5. Explicit VECTOR → NEXT promotion in `TASKS.md` with rationale.

### Criterion 3: Metabolization Truth-Table (>=8 transitions)

The following truth-table defines the complete set of metabolization transitions covering all 5 buckets. Each row specifies a source bucket, an input condition, a route target, and expected outcome. Transitions T1-T6 correspond to the 6 designed projection IDs. Transitions T7-T10 are adversarial/edge-case transitions that validate sink-safety.

| ID | Source Bucket | Input Condition | Projection / Rule | Route Target | Expected Outcome |
|----|---------------|-----------------|-------------------|--------------|------------------|
| T1 | sink | `sink_entry.state` matches unbounded predicate (non-null, non-void structural form) | `hemisphere.metabolize.sink_to_r_inf` | r_inf | Entry removed from sink, prepended to r_inf. Remaining sink entries unchanged. |
| T2 | sink | `sink_entry.state` is null (void/zero-structure) | `hemisphere.metabolize.sink_to_r_null` | r_null | Entry removed from sink, prepended to r_null. Remaining sink entries unchanged. |
| T3 | (stalled entry) | Stalled entry + lobes is non-null (lobes can accept) | `hemisphere.recover.stall_to_lobes` | lobes | Stalled entry routed to lobes for recovery attempt. |
| T4 | (stalled entry) | Stalled entry + lobes is null (lobes cannot accept) | `hemisphere.recover.stall_to_sink` | sink | Stalled entry routed to sink as fallback. |
| T5 | lobes | `lobes_entry.closure_flag` is true (closure evidence present) | `hemisphere.promote.lobes_to_r_a` | r_a | Entry removed from lobes, prepended to r_a. Remaining lobes entries unchanged. |
| T6 | r_inf, r_null, or lobes | Entry is unresolvable after metabolization/recovery attempt | `hemisphere.recycle.residual_to_sink` | sink | Unresolvable entry recycled back to sink for future re-expression. |
| T7 | sink | **ADVERSARIAL:** Forged closure in exhaustion result — `sink_entry` has `closure_flag: true` but was routed to sink via `hemisphere.classify.exhaustion` (exhaustion_detected dominates closure) | No metabolization projection matches | sink (remains) | Entry stays in sink. Forged closure_flag does NOT cause promotion to r_a. Sink-safety preserved. |
| T8 | sink | Sink entry with `state: null` AND `closure_flag: true` — exhaustion victim with null state and forged closure | `hemisphere.metabolize.sink_to_r_null` (null state matches void predicate) | r_null | Entry moves to r_null based on state predicate, NOT closure_flag. No path from r_null to r_a exists. Sink-safety preserved. |
| T9 | sink | Sink entry with non-null, non-void state that does NOT match unbounded predicate | `hemisphere.recycle.residual_to_sink` | sink (recycled) | Entry recycled back to sink unchanged. Material preserved for future re-expression cycles. |
| T10 | lobes | `lobes_entry.closure_flag` is false (no closure evidence) | No promotion projection matches | lobes (remains) | Entry stays in lobes. Promotion requires explicit closure evidence. No implicit promotion. |

**Coverage verification:**
- **r_null**: Target of T2, T8. Source: none (terminal).
- **r_inf**: Target of T1. Source: none (terminal).
- **r_a**: Target of T5. Source: none (promotion is one-way).
- **lobes**: Target of T3. Source of T5, T10 (promotion or retention).
- **sink**: Target of T4, T6, T7, T9. Source of T1, T2, T8 (metabolization out) and T9 (recycle in).
- **Adversarial**: T7 (forged closure in exhaustion victim), T8 (null+closure compound forgery), T9 (unmetabolizable residual).

**Structural predicate note (Open Question #4 dependency):**
The unbounded-vs-void distinction in T1/T2 depends on Open Question #4. The truth-table uses `state: null` as the void predicate and "non-null structural form" as the unbounded predicate. The final predicate design must be structural (not host-derived) and must be locked before VECTOR → NEXT promotion.

### Criterion 4: Engine Exception Policy Option B Design

> **Status:** Design only. No implementation. Enable ONLY when metabolization projections exist and sink-safety invariants are tested.

#### Synthesized engine_result Shape

When the engine pipeline encounters an exception (non-terminal stall or iteration exhaustion), Option B catches the exception and synthesizes a terminal engine_result instead of raising RuntimeError/RcxError. The synthesized result has the standard 8-field terminal shape:

```json
{
  "value": "<last engine state or null if unavailable>",
  "closure_detected": false,
  "tau_step": 0,
  "exhaustion_detected": true,
  "operator_frozen": null,
  "frozen_set": null,
  "action": "exception_sink",
  "stall": "<true if stall-originated, false if iteration-exhaustion>"
}
```

**Field rationale:**
- `closure_detected: false` — MANDATORY. Synthesized results NEVER claim closure.
- `tau_step: 0` — No meaningful recurrence step occurred.
- `exhaustion_detected: true` — MANDATORY. Ensures `hemisphere.classify.exhaustion` fires first.
- `action: "exception_sink"` — Unique action value distinguishing synthesized exceptions from `"done"` or `"freeze"`. Must NOT be `"freeze"` (triggers trampoline re-entry).
- `stall` — Preserves causal distinction: `true` for stall exceptions, `false` for exhaustion exceptions.

**Two synthesis sites (per substrate):**

| Exception Type | Python Location | JS Location | `stall` field |
|----------------|-----------------|-------------|---------------|
| Non-terminal stall | `step_mu.py` (~line 1502) | `eval_step.js` (~line 1936) | `true` |
| Iteration exhaustion | `step_mu.py` (~line 1563) | `eval_step.js` (~line 2002) | `false` |

#### Sink-Safety Invariants (S1-S5)

| ID | Invariant | Rationale |
|----|-----------|-----------|
| S1 | Synthesized engine_result MUST have `exhaustion_detected: true` | Ensures `hemisphere.classify.exhaustion` fires first (exhaustion > all other classify projections). |
| S2 | Synthesized engine_result MUST have `closure_detected: false` | Prevents false closure claims. |
| S3 | Synthesized engine_result MUST NOT have `action: "freeze"` | `action: "freeze"` triggers trampoline re-entry. Exceptions must terminate. |
| S4 | Both substrates MUST produce identical synthesized results for same exception | L3 parity requirement. |
| S5 | `_is_engine_terminal()` / `isEngineTerminal()` MUST return true for synthesized results | Synthesized result must pass standard terminal shape check. |

#### Adversarial Test Specs (Design Only)

| Test ID | Description | Expected Behavior |
|---------|-------------|-------------------|
| ADV-B1 | Forged closure in synthesized result | Routes to **sink** (not r_a). Exhaustion dominates closure. |
| ADV-B2 | Forged action=freeze in synthesized result | `engine.exhaustion_done_freeze` MUST NOT match (synthesized results bypass engine projections). |
| ADV-B3 | Null value in synthesized result | Routes to **sink** (not r_null). `exhaustion_detected: true` fires before `hemisphere.classify.null`. |
| ADV-B4 | Cross-substrate divergence | Field-by-field identical (S4). |
| ADV-B5 | Synthesized result shape validation | Terminal check passes (S5). Hemisphere routing completes. Entry in sink. |
| ADV-B6 | Double-exception guard | Metabolization of synthesized sink entry stalls → residual recycles to sink (T6/T9). No infinite loop. |

**Enablement guard:** Option B disabled by default. Requires: (1) metabolization projections exist in seed file, (2) S1-S5 tests pass, (3) ADV-B1 through ADV-B6 pass on both substrates, (4) T1-T10 test coverage.

## Open Questions
1. Minimum entry schema for each hemisphere.
2. ~~Whether re-expression from `sink` is automatic or requires explicit triggers.~~ Answered: both modes (automatic + manual/debug step). See Trigger Semantics above.
3. How `r_inf` detection is bounded without host-only heuristics.
4. What structural predicate distinguishes "unbounded" from "void" at the Mu level (required for metabolization).
