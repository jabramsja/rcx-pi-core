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

### D003: H2 Stage 0→1 Transition Correctness

```
Decision ID: D003
Date: 2026-02-19
Owner: RCX Core Team
Scope: Test H2 criteria 3-4 — staged bootstrap transition + G2/G7 preservation

1. Target L4 Gate(s)
   Gate: G8 (Irreducible Primitive Consensus)
   Why now: D001+D002 confirmed pattern set is finite and micro-matcher is
   feasible (31 LOC). Remaining question: does staged bootstrap actually work?

2. Proposed Change (Least-Lazy Path)
   Write micro_substitute + micro_step + micro_run (research artifact).
   Validate 5 canonical test vectors against expected terminal states.
   AST-verify G2 (no domain branching) and G7 (non-recursive).

3. Pass/Fail Evidence Commands
   Pass: PYTHONHASHSEED=0 pytest tests/research/test_d003_staged_bootstrap.py -v
   Fail: any vector diverges OR domain branching OR recursion OR LOC cap exceeded

4. Risks and Rollback Trigger
   Risk: None (research artifact in tests/research/, not production import).
   Rollback: Delete file if falsified.

5. Not-in-Scope
   - Production code changes
   - H1 or H3 experiments
   - Actual Boot0/Boot1 implementation
   - Stage 0→1 runtime transition mechanism

6. Decision Outcome
   Outcome: GO
   Rationale: D002 proved micro-matcher feasible. Stage 0 transition is the
   next logical gate for H2. Fast, isolated, directly produces G8 evidence.

7. Execution Result (2026-02-19)
   Status: EXECUTED — H2 criteria 3-4 MET

   Evidence:
   - micro_substitute: 14 LOC, micro_step: 7 LOC
   - Total Stage 0 kernel: 52 LOC (micro_match 31 + micro_substitute 14 + micro_step 7)
   - For comparison: bootstrap match alone is ~90 LOC. Stage 0 is 42% the size.
   - All 5 test vectors produce correct terminal states:
     V1: literal match -> match_done/success
     V2: var bind -> match_done/success with bindings
     V3: match failure -> match_done/no_match
     V4: simple subst -> subst_done with result 42
     V5: structural subst -> subst_done with {head:1, tail:2}
   - G2 preserved: AST check confirms no domain key references in micro_step
   - G7 preserved: AST check confirms no self-calls in micro_step or micro_run
   - No new BOOTSTRAP_PRIMITIVE markers (Python: 4, JS: 8 — unchanged)
   - All vectors converge in <100 steps
   - 21 tests pass, no production code modified

   H2 criterion 3 (Stage 0→1 identical results): MET
   H2 criterion 4 (G2/G7 preserved): MET
   H2 status: ALL 4 CRITERIA MET — staged bootstrap is feasible

   Implication for G8: eval_step is REDUCIBLE_WITH staged bootstrap.
   The circular dependency (eval_step needs match/subst, match/subst are
   projections needing eval_step) can be broken by a 52-LOC Stage 0 kernel.
   Whether to actually implement this is a separate decision.
```

### D004: Production Pilot GO/NO-GO Decision Package

```
Decision ID: D004
Date: 2026-02-19
Owner: RCX Core Team
Scope: GO/NO-GO/DEFER decision for production staged bootstrap pilot

1. Target L4 Gate(s)
   Gate: G8 (Irreducible Primitive Consensus)
   Why now: D001-D003 established H2 feasibility in research artifacts
   (52 LOC Stage 0 kernel, all 4 criteria MET). The question shifts from
   "is it possible?" to "should we attempt production integration, and
   under what constraints?"

2. Proposed Change (Least-Lazy Path)
   This decision card is a DECISION PACKAGE ONLY. No runtime code changes.

   D004 produces a GO/NO-GO/DEFER verdict based on:
   a) Risk-benefit analysis: what does staged bootstrap buy vs. cost?
   b) Production LOC budget and blast-radius inventory
   c) Invariant preservation checklist
   d) Rollback trigger specification

   If GO: authorizes a bounded D005 pilot (separate decision card).
   If NO-GO: records reasoning, closes production pilot path.
   If DEFER: records reasoning, preserves option for future re-evaluation.

3. Pass/Fail Evidence Commands
   This is a decision package — evidence is analytical, not executable.
   Supporting evidence:
     PYTHONHASHSEED=0 pytest tests/research/ -v  # D001-D003 research artifacts
     pytest tests/docs/test_doc_contracts.py -v   # Doc consistency
   Decision inputs:
     - Research evidence: D001 (finite patterns), D002 (31 LOC), D003 (52 LOC)
     - Production constraints: 4 bootstrap primitives, debt=12, infra<=48
     - L3 parity requirement: any production change must mirror in JS

4. Risks and Rollback Trigger
   D004 risk: ZERO (decision package, no code changes).
   For a future pilot (if GO), risks would include:
   - Stage 0 kernel introduces new failure mode in production boot path
   - LOC growth beyond budget signals complexity leak
   - L3 parity cannot be maintained for staged bootstrap
   Rollback trigger (for future pilot): any test regression, any new
   bootstrap primitive, debt exceeds ceiling, L3 parity broken.

5. Not-in-Scope
   - Actual Stage 0 production implementation (would be D005+ if GO)
   - H1 (fuel threading) or H3 (negative control) experiments
   - Boot1 loop contract work (parallel NEXT item)
   - Any changes to eval_step, step_mu, or match_mu
   - L4ExitChecklist G8 reclassification (premature until pilot succeeds)
   - eval_step.js modifications

6. Decision Outcome
   Outcome: GO/NO-GO/DEFER (pending founder review)

   GO criteria (all required):
   - Research evidence is sufficient (D001-D003: YES)
   - Production LOC budget is bounded (proposed: <=100 net new in selfhost/)
   - All invariants enumerable and preservable
   - Rollback path is clean (revert to single-stage boot)
   - Benefit exceeds risk at current project stage

   NO-GO criteria (any sufficient):
   - Risk exceeds benefit (L4 is SINK, not blocking any NEXT work)
   - Invariants cannot be preserved without new primitives
   - L3 parity cost is prohibitive

   DEFER criteria:
   - Evidence is sufficient but timing is wrong (other NEXT items higher priority)
   - Benefit is real but risk tolerance is currently low

7. Pilot Scope Boundaries (if GO)

   | Boundary | Constraint |
   |----------|------------|
   | Max production LOC | <=100 net new in rcx_pi/selfhost/ |
   | Forbidden changes | eval_seed.step(), match(), substitute(), step_kernel_mu() |
   | Bootstrap primitives | Must remain exactly 4 (no increase) |
   | BOOTSTRAP_PRIMITIVE markers | Py:4, JS:8 (no increase) |
   | Debt ceiling | Must remain <=12 (L2 floor) |
   | Infra ceiling | Must remain <=48 |
   | L3 parity | If any production change, JS must mirror |
   | Seed files | No modifications to kernel.v1, match.v2, subst.v2 |
   | Test regression | Zero tolerance — any failure terminates pilot |

8. Stop Conditions (immediate pilot termination, if authorized)

   | # | Condition | Action |
   |---|-----------|--------|
   | S1 | Any existing test fails | STOP. Revert. |
   | S2 | New bootstrap primitive required | STOP. Primitive count is invariant. |
   | S3 | Stage 0 exceeds 100 LOC in production | STOP. Complexity leak. |
   | S4 | JS parity cannot be maintained | STOP. L3 is non-negotiable. |
   | S5 | Analysis reveals no material benefit | NO-GO. Record and close. |
   | S6 | Founder determines risk > benefit | NO-GO. Defer to future L4. |

9. Gate Mapping

   | L4 Gate | De-risks? | How |
   |---------|-----------|-----|
   | G8 (Irreducible Primitive Consensus) | PRIMARY | Demonstrates eval_step REDUCIBLE_WITH in production context |
   | G2 (eval_step Minimality) | Indirect | Stage 0 preserves no-domain-branching (proven D003) |
   | G7 (eval_step Non-Recursive) | Indirect | Stage 0 preserves non-recursive (proven D003) |
   | G1, G3-G6 | No | Already PASS; pilot must not regress them |
```

---

## References

- `mu/docs/core/L4ExitChecklist.v0.md` — Gate definitions (G1-G8)
- `mu/docs/core/G8CpsFeasibility.v0.md` — Hypothesis definitions (H1-H3)
- `mu/docs/core/L4MicroAbi.v0.md` — ABI surface mapped to gates
