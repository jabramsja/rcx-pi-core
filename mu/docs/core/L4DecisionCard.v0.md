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
```

---

## References

- `mu/docs/core/L4ExitChecklist.v0.md` — Gate definitions (G1-G8)
- `mu/docs/core/G8CpsFeasibility.v0.md` — Hypothesis definitions (H1-H3)
- `mu/docs/core/L4MicroAbi.v0.md` — ABI surface mapped to gates
