<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-02-18
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: none

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
-->

# G8 CPS Feasibility Study v0

**Purpose:** Turn L4-G8 (Irreducible Primitive Consensus) from UNPROVEN into a structured feasibility path with falsifiable hypotheses and explicit stop conditions.

**Status:** SINK research. No implementation proposed. This document defines experiments, not commitments.

**Context:** G8 asks whether the 4 bootstrap primitives are truly irreducible. The current classification (see `L4ExitChecklist.v0.md`) labels `eval_step` as IRREDUCIBLE due to circular dependency, and `max_steps`/`stack_guard`/`projection_loader` as REDUCIBLE_WITH specific architectural changes. This study tests whether those classifications hold under scrutiny.

---

## Core Question

**Can CPS (Continuation-Passing Style) transformation break the circular dependency that makes `eval_step` appear irreducible?**

The circular dependency: projections need `eval_step` to run, but structural match/subst ARE projections that need `eval_step`. If CPS can thread continuations through the evaluation, a staged bootstrap might break this cycle.

---

## Hypotheses

### H1 (Positive): Structural Fuel Threading

**Claim:** The host `for` loop in `rcx_run` can be replaced by a structural fuel counter without semantic regression.

**Mechanism:** Instead of `for i in range(fuel)`, the fuel becomes a Mu linked-list that `rcx_step` consumes one node per step. When the list is empty, evaluation stops.

```
# Current (host loop):
rcx_run(state, fuel=100) → for i in range(100): state = rcx_step(state)

# Proposed (structural fuel):
rcx_run(state, fuel={head: null, tail: {head: null, tail: ...}})  # 100 nodes
→ rcx_step consumes one fuel node per step
→ empty fuel → fuel_exhausted status
```

**Success criteria:**
1. A test harness demonstrates `rcx_step` accepting a fuel linked-list and producing correct terminal states for at least 5 canonical vectors (identity stall, single match, multi-step convergence, fuel exhaustion, nested structure)
2. Results are identical to current `run_mu()` output on same inputs
3. No new bootstrap primitive introduced

**Failure criteria:**
1. Fuel threading requires `eval_step` to inspect fuel (violates G2 — no domain branching)
2. Fuel linked-list construction itself requires a host loop (circular: need loop to build fuel that replaces loop)
3. Performance degrades >100x (structural counter is O(fuel) space vs O(1) integer)

**Minimal experiment:**
```bash
# If implemented as isolated test:
pytest tests/research/test_h1_fuel_threading.py -v
```

**Stop condition:** If failure criterion 1 is hit (eval_step must branch on fuel), H1 is FALSIFIED. Fuel threading cannot work without changing eval_step's contract, which would invalidate G2.

---

### H2 (Positive): Staged Continuation Envelopes

**Claim:** The circular dependency (eval_step needs match/subst, match/subst are projections needing eval_step) can be broken by a two-stage bootstrap where Stage 0 uses a hardcoded micro-matcher and Stage 1 uses projection-based match/subst.

**Mechanism:** Stage 0 is a fixed-function matcher that can match ONLY the patterns used by match.v2.json and subst.v2.json (a finite, known set). Stage 1 loads match.v2/subst.v2 and uses them for everything else. The circular dependency breaks because Stage 0 doesn't need projections — it IS the initial substrate.

```
# Current (circular):
eval_step → match/subst → projections → eval_step

# Proposed (staged):
Stage 0: micro_eval_step → hardcoded_match(only match.v2 patterns) → load match.v2/subst.v2
Stage 1: eval_step → match.v2/subst.v2 projections → eval_step (self-sustaining)
```

**Success criteria:**
1. The set of patterns used by match.v2.json and subst.v2.json is enumerable (finite, closed)
2. A micro-matcher that handles ONLY those patterns is expressible in <50 LOC
3. Stage 0 → Stage 1 transition produces identical results to current single-stage bootstrap
4. eval_step's contract (G2, G7) is preserved in Stage 1

**Failure criteria:**
1. The pattern set used by match.v2/subst.v2 is not finite (some pattern generates new patterns)
2. The micro-matcher exceeds 200 LOC (larger than current bootstrap match/subst — no reduction achieved)
3. Stage 0 → Stage 1 transition introduces a new primitive (total primitive count increases)

**Minimal experiment:**
```bash
# Pattern enumeration (no code needed — analysis only):
python3 -c "
import json
from pathlib import Path
seeds_dir = Path('mu/substrate')
for name in ['match.v2.json', 'subst.v2.json']:
    seed = json.loads((seeds_dir / name).read_text())
    for p in seed['projections']:
        print(f\"{name}: {p['id']} pattern keys: {sorted(p['pattern'].keys()) if isinstance(p['pattern'], dict) else type(p['pattern']).__name__}\")
"
```

**Stop condition:** If the pattern set is not finite (failure criterion 1), H2 is FALSIFIED. The circular dependency is genuinely irreducible — no finite stage can bootstrap an open-ended matcher.

**Experimental result (D001, 2026-02-19):**

Criterion 1 tested via pattern enumeration against `mu/substrate/match.v2.json` and `mu/substrate/subst.v2.json`. Full evidence in `L4DecisionCard.v0.md` D001 §7.

| Metric | Value |
|--------|-------|
| Total projections | 20 (8 match + 12 subst) |
| Distinct top-level key signatures | 5 |
| Matching primitives required | 5 (var_bind, dict_shape, literal_string, null_check, nested_var_bind) |
| Same-var equality constraints | 3 |
| Max pattern nesting depth | 3 |
| Self-referential patterns | 0 |

**Result: Criterion 1 MET — pattern set is FINITE AND CLOSED.** No projection body creates new projection definitions. All 20 patterns are static JSON. A micro-matcher handling exactly these 5 matching primitives across 5 top-level key signatures is feasible in principle.

**D002 result (2026-02-19):** Criterion 2 tested via standalone micro-matcher prototype in `tests/research/test_d002_micro_matcher.py`. Evidence in `L4DecisionCard.v0.md` D002 §7.

- micro_match() core: **31 LOC** (threshold: 50) — 66% smaller than bootstrap _match_inner (~90 LOC)
- Handles all 5 D001 primitives and all 3 same-var constraints
- 56 tests pass, no new primitives, no I/O, no globals
- **Criterion 2 MET**

**H2 status: CRITERIA 1-2 MET (of 4).** Pattern set is finite (D001). Micro-matcher is feasible at 31 LOC (D002). Criteria 3-4 (Stage 0→1 transition, G2/G7 preservation) remain UNTESTED and would require a staged bootstrap prototype.

**Implication for G8:** The circular dependency is NOT inherently irreducible. A staged bootstrap is structurally possible — Stage 0 can handle a known, finite pattern set with a 31-LOC micro-matcher that is strictly simpler than the bootstrap it replaces. Whether the engineering cost of Stage 0→1 transition is justified is a separate question from whether it's possible.

---

### H3 (Negative Control): Host Loop Elimination Without CPS

**Claim (intentionally likely false):** The host `for` loop in `run_engine_pipeline()` can be eliminated entirely — no host iteration, no CPS, no fuel — while preserving deterministic termination.

**Why this is likely false:** Without any iteration mechanism (host or structural), there is no way to apply projections more than once. A single `rcx_step` can apply one projection. Reaching a fixed point requires repeated application. Either the host provides iteration or Mu data encodes it — there is no third option.

**Purpose:** This negative control validates the falsification discipline. If H3 cannot be falsified, the methodology is broken.

**Success criteria:**
1. A mechanism is found that applies projections repeatedly without host iteration AND without structural fuel/CPS
2. The mechanism preserves deterministic termination (no unbounded execution)

**Failure criteria (expected):**
1. No such mechanism exists: iteration is either host-provided or data-encoded
2. Any proposed mechanism is isomorphic to a host loop or structural counter

**Minimal experiment:**
```bash
# Thought experiment only. Attempt to write rcx_run without loop or fuel:
# rcx_run(state) = ??? (must apply rcx_step N times for unknown N)
# If N is unknown at call time, something must count. QED.
```

**Stop condition:** If no non-isomorphic mechanism is proposed after analysis, H3 is FALSIFIED (expected). This confirms that iteration is genuinely irreducible in some form.

---

## Hypothesis Matrix

| ID | Claim | Type | Status | Success Path | Failure Path | Effort |
|----|-------|------|--------|-------------|-------------|--------|
| H1 | Structural fuel replaces host loop | Positive | UNTESTED | Fuel linked-list as Mu data | eval_step must branch on fuel (violates G2) | Medium (test harness) |
| H2 | Staged bootstrap breaks circular dep | Positive | **CRITERIA 1-2 MET** (2/4) | Finite pattern set → micro-matcher (31 LOC) | Pattern set not finite OR micro-matcher too large | Low (analysis + enumeration) |
| H3 | Loop elimination without any mechanism | Negative | UNTESTED | (Would invalidate methodology) | No non-isomorphic mechanism exists (expected) | Minimal (thought experiment) |

---

## Decision Tree

```
Start: G8 UNPROVEN
  │
  ├─ H3 FALSIFIED? (expected YES)
  │   ├─ YES → Methodology validated. Iteration is irreducible in some form.
  │   └─ NO → Methodology broken. Re-examine assumptions.
  │
  ├─ H1 result?
  │   ├─ SUCCESS → max_steps classification confirmed REDUCIBLE_WITH fuel threading.
  │   │            Reclassify: max_steps = REDUCIBLE (proven). stack_guard likely follows.
  │   └─ FAILURE → max_steps classification confirmed IRREDUCIBLE (eval_step can't branch on fuel).
  │               G2 and G3 are in tension. Document as architectural constraint.
  │
  └─ H2 result?
      ├─ SUCCESS → eval_step classification changes from IRREDUCIBLE to REDUCIBLE_WITH staged bootstrap.
      │            This is the major L4 breakthrough. Opens path to true meta-circularity.
      └─ FAILURE → eval_step confirmed IRREDUCIBLE. Circular dependency is genuine.
                   L4 requires a meta-level VM (outside current architecture).
```

---

## Stop Conditions (Global)

| Condition | Action |
|-----------|--------|
| H2 + H3 both FALSIFIED | G8 resolved: eval_step is IRREDUCIBLE, max_steps determined by H1. Update L4ExitChecklist. |
| H1 + H2 both SUCCESS | G8 resolved: all primitives are REDUCIBLE_WITH. L4 path is open. Create VECTOR item for staged implementation. |
| H1 FAILURE + H2 SUCCESS | Partial resolution: iteration remains host-provided, but circular dependency broken. Reclassify primitives. |
| Any hypothesis requires >200 LOC of new production code | STOP. This is a feasibility study, not an implementation. Create VECTOR item if promising. |
| CPS transform introduces new primitive | STOP. Net primitive count must not increase. |

---

## Relationship to Existing Work

- **Boot0 Architecture (v0.4):** H2's staged bootstrap is a formalization of Boot0 → Boot1 transition. Boot0 already contains bootstrap match/subst; H2 asks whether that bootstrap can be reduced to a micro-matcher.
- **Boot1 Loop Contract:** H1's fuel threading is compatible with Boot1's recursive shadow. Both address iteration control; H1 does it structurally, Boot1 does it recursively.
- **Content-Addressed Mu:** Level 1 (mu_equal demoted) shows primitives CAN be reduced. H1 and H2 ask whether more primitives follow.

---

## References

- `mu/docs/core/L4ExitChecklist.v0.md` — G8 gate definition and current UNPROVEN status
- `mu/docs/core/L4MicroAbi.v0.md` — ABI surface that G8 classifies
- `mu/docs/core/Boot0Architecture.v0.md` — Staged bootstrap precedent
- `mu/docs/core/BootstrapPrimitives.v0.md` — Current primitive specification
- `mu/docs/core/Boot1LoopContract.v0.md` — Boot1 recursive loop (related to H1)
