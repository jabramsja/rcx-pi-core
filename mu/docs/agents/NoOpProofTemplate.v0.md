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

# NO-OP Proof Template

**Purpose:** When the correct action is "do nothing," prove it with evidence. Prevents silence theater (claiming no issues without checking).

---

## 1. When NO-OP Is Valid

A NO-OP conclusion requires ALL of:

1. The concern is classified as **DEFERRED** by the L4 Parity-Floor Policy (`CLAUDE.md` section "L4 Parity-Floor Policy (Evidence-First)").
2. No L4 gate's pass/fail evidence would change if the gap persists.
3. At least one evidence command was run to verify the current state.

If any condition is not met, the item is **BLOCKED_REVIEW**, not NO-OP.

---

## 2. Mandatory Proof Commands

Before concluding NO-OP, run at least one command from this list:

```bash
# Gate evidence still passes:
grep -rn "BOOTSTRAP_PRIMITIVE" mu/host/python/rcx_pi/selfhost/ mu/host/js/eval_step.js | grep -v test

# Parity constants still match:
pytest tests/parity/test_cross_substrate_constants.py -v

# Seed integrity still holds:
pytest tests/parity/test_seed_loading_parity.py -v

# Pipeline discipline still holds:
pytest tests/structural/test_engine_pipeline_discipline.py -v
```

The specific command depends on the concern being triaged. Choose the command whose output is relevant to the gate in question.

---

## 3. Evidence Table Format

Every NO-OP conclusion must include a table:

| Concern | Gate? | Evidence Command | Output Summary | Interpretation |
|---------|-------|-----------------|----------------|---------------|
| (description) | (gate ID or "none") | (command run) | (pass/fail + key output) | NO-OP / BLOCKED_REVIEW |

---

## 4. BLOCKED_REVIEW Format

If NO-OP cannot be proven, use:

```
BLOCKED_REVIEW
Concern: <description>
File: <exact file path>
Reason: <why NO-OP cannot be proven>
Required action: <what must happen before this can be resolved>
```

---

## 5. No Speculative Edits

- Do NOT make changes "while we're here" or "for consistency."
- Do NOT fix things that are not broken and not gate-mapped.
- If a concern is classified DEFERRED by the parity-floor policy, it stays deferred until explicitly promoted.
- The only valid reasons to act are: (a) a gate's evidence command fails, or (b) the concern is explicitly promoted to mandatory.

---

## References

- `CLAUDE.md` section "L4 Parity-Floor Policy (Evidence-First)" — Defines mandatory vs deferred classification
- `mu/docs/core/L4ExitChecklist.v0.md` — Gate pass/fail evidence commands
- `mu/docs/core/L4DecisionCard.v0.md` — Decision record for non-trivial changes
