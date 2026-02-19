<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-19
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: none

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
-->

# L4 Decision Card Template

**Purpose:** Structured record for L4-related decisions. Every L4 change must have a decision card before implementation.

**Standing rule:** Least-lazy solution that materially de-risks the next L4 gate.

---

## Template

```
Decision ID: D<NNN>
Date: YYYY-MM-DD
Owner: <name or team>
Scope: <one-line summary>

1. Target L4 Gate(s)
   Gate: G<N> (<gate name>)
   Why now: <why this gate needs attention at this point>

2. Proposed Change (Least-Lazy Path)
   <concrete description, no aspirational prose>

3. Pass/Fail Evidence Commands
   Pass: <command that proves success>
   Fail: <command or condition that proves failure>

4. Risks and Rollback Trigger
   Risk: <what could go wrong>
   Rollback: <condition under which to revert>

5. Not-in-Scope
   - <item explicitly excluded>

6. Decision Outcome
   Outcome: GO | NO-GO | DEFER
   Rationale: <why this outcome>
```

---

## Decision Log

### D001: H2 Pattern Enumeration Experiment

```
Decision ID: D001
Date: 2026-02-19
Owner: RCX Core Team
Scope: Enumerate match.v2/subst.v2 pattern set to test G8 H2 feasibility

1. Target L4 Gate(s)
   Gate: G8 (Irreducible Primitive Consensus)
   Why now: H2 (staged continuation envelopes) is the lowest-effort hypothesis
   in G8CpsFeasibility.v0.md. Pattern enumeration is read-only analysis that
   directly produces G8 evidence.

2. Proposed Change (Least-Lazy Path)
   Run enumeration script against mu/substrate/match.v2.json and
   mu/substrate/subst.v2.json. Record pattern structures. Classify set as
   finite (H2 viable) or open-ended (H2 falsified).

3. Pass/Fail Evidence Commands
   Pass (H2 viable): All patterns enumerable, finite set, micro-matcher feasible
   Fail (H2 falsified): Patterns generate new patterns, or set is not closed
   Evidence command:
     python3 -c "
     import json; from pathlib import Path
     for n in ['match.v2.json', 'subst.v2.json']:
       seed = json.loads((Path('mu/substrate') / n).read_text())
       for p in seed['projections']:
         keys = sorted(p['pattern'].keys()) if isinstance(p['pattern'], dict) else type(p['pattern']).__name__
         print(f'{n}: {p[\"id\"]} -> {keys}')
     "

4. Risks and Rollback Trigger
   Risk: None (read-only analysis, zero runtime changes).
   Rollback: N/A.

5. Not-in-Scope
   - H1 fuel threading implementation
   - H3 negative control analysis
   - Any production code changes
   - Any new seed files

6. Decision Outcome
   Outcome: GO
   Rationale: Zero risk, directly produces G8 evidence, satisfies
   least-lazy standing rule. Next strict wave should execute this.

7. Execution Result (2026-02-19)
   Status: EXECUTED — H2 criterion 1 MET

   Evidence command run:
     python3 -c "
     import json; from pathlib import Path
     for n in ['match.v2.json', 'subst.v2.json']:
       seed = json.loads((Path('mu/substrate') / n).read_text())
       for p in seed['projections']:
         keys = sorted(p['pattern'].keys()) if isinstance(p['pattern'], dict) else type(p['pattern']).__name__
         print(f'{n}: {p[\"id\"]} -> {keys}')
     "

   Raw findings:
   - Total projections: 20 (8 match + 12 subst)
   - Distinct top-level key signatures: 5
   - Matching primitives required: 5 (var_bind, dict_shape, literal_string, null_check, nested_var_bind)
   - Same-var equality constraints: 3 (match.equal, match.typed.descend, subst.lookup.found)
   - Max pattern nesting depth: 3 (match.sibling, subst.ascend, subst.sibling, subst.typed.sibling, subst.typed.ascend)
   - Self-referential patterns (bodies creating new projections): 0

   Classification: FINITE AND CLOSED
   - All 20 patterns are static JSON — no pattern generates new patterns
   - Bodies produce data states, not new projection definitions
   - The pattern set is fully enumerable by a fixed-function micro-matcher

   H2 criterion 1 (enumerable, finite set): MET
   H2 criterion 2 (<50 LOC micro-matcher): PLAUSIBLE (not yet tested — requires D002)
   H2 criteria 3-4 (Stage 0→1 transition, G2/G7 preservation): UNTESTED (requires implementation)

   Next step: D002 — micro-matcher prototype (<50 LOC target) if H2 criterion 2 is pursued
```

### D002: H2 Micro-Matcher Feasibility Experiment

```
Decision ID: D002
Date: 2026-02-19
Owner: RCX Core Team
Scope: Test H2 criterion 2 — micro-matcher <=50 LOC handling D001 pattern set

1. Target L4 Gate(s)
   Gate: G8 (Irreducible Primitive Consensus)
   Why now: D001 confirmed pattern set is finite. Next question: is a
   micro-matcher small enough to qualify as a reduction over bootstrap match/subst?

2. Proposed Change (Least-Lazy Path)
   Write standalone micro-matcher in tests/research/ (research artifact only).
   Validate against all 20 match.v2/subst.v2 patterns. Measure LOC.

3. Pass/Fail Evidence Commands
   Pass: PYTHONHASHSEED=0 pytest tests/research/test_d002_micro_matcher.py -v
   Fail: matcher core >50 LOC OR cannot handle same-var OR needs new primitive
   LOC measurement: test_matcher_loc_under_threshold (self-verifying)

4. Risks and Rollback Trigger
   Risk: None (research artifact in tests/research/, not production import).
   Rollback: Delete file if falsified.

5. Not-in-Scope
   - H2 criteria 3-4 (Stage 0→1 transition, G2/G7 preservation)
   - Production code changes
   - H1 or H3 experiments
   - Substitution micro-implementation

6. Decision Outcome
   Outcome: GO
   Rationale: D001 proved finite pattern set. LOC test is fast, isolated,
   and directly answers whether micro-matcher reduction is real.

7. Execution Result (2026-02-19)
   Status: EXECUTED — H2 criterion 2 MET

   Evidence:
   - micro_match() function: 31 LOC (threshold: 50)
   - Handles all 5 D001 primitives: var_bind, dict_shape, literal_string,
     null_check, nested_var_bind
   - Handles all 3 same-var equality constraints correctly
   - 56 tests pass (20 positive matches, 18 literal rejection, 3 same-var,
     2 nested-var, 7 negative cases, 2 LOC/purity checks, 4 D001 consistency)
   - No new primitives introduced (no imports, no I/O, no globals)
   - No production code modified

   Comparison to bootstrap match/subst:
   - Bootstrap _match_inner: ~90 LOC (handles lists, type normalization, etc.)
   - Micro-matcher: 31 LOC (handles only D001 pattern set)
   - Reduction: 66% smaller — micro-matcher is strictly less complex

   H2 criterion 2 (<50 LOC micro-matcher): MET (31 LOC)
   H2 criteria 3-4 (Stage 0→1 transition, G2/G7 preservation): UNTESTED
   Next step: D003 (if pursued) — Stage 0→1 transition prototype
```

---

## References

- `mu/docs/core/L4ExitChecklist.v0.md` — Gate definitions (G1-G8)
- `mu/docs/core/G8CpsFeasibility.v0.md` — Hypothesis definitions (H1-H3)
- `mu/docs/core/L4MicroAbi.v0.md` — ABI surface mapped to gates
