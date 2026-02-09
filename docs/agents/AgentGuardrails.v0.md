<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-08
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Agent Guardrails v0

> **TL;DR:** Every finding needs `FILE:LINE` + code snippet. No citation = rejected.

---

**Operational shortcut:** Use `docs/agents/AgentRunbook.v0.md` for trigger map and gate rules.

## Core Rule

```
FINDING: [description]
FILE: /absolute/path/file.py
LINES: 123-127
CODE:
    actual_code_from_read_tool()
PROPOSED_FIX:
    [concrete fix - actual code, not vague advice]
VERIFIED: Yes
```

**PROPOSED_FIX is REQUIRED for FAIL/VULNERABLE/OVER_ENGINEERED findings.**
Show the actual fix, not just "add marker" - show WHERE and WHAT.

**Findings without this format are REJECTED by the human reviewer.**

---

## Before Any Assessment

1. Use **Read** tool on `STATUS.md` (current phase, debt counts)
2. Use **Read** tool on `TASKS.md` (work items, context)
3. Use **Read/Grep** tools to verify claims (never rely on docs alone)

---

## FORBIDDEN

- Claims based only on docs/summaries
- "Probably" or "likely" without verification
- `VERIFIED: No` findings (reject them yourself)
- Citing code from memory (must be from Read tool output)

---

## Agent Quick Reference

| Agent | Primary Search | Reject If |
|-------|----------------|-----------|
| **Verifier** | Grep `@host_` in `rcx_pi/` | No file:line for debt claims |
| **Adversary** | Grep `isinstance` in `rcx_pi/selfhost/` | No exploit code path shown |
| **Expert** | Grep function name in `tests/` | Dead code claim without usage search |
| **Structural-Proof** | Read `mu/**/*.json` | Structural claim without projection evidence |
| **Grounding** | Grep `def test_` in `tests/` | Gap claim without test search |
| **Fuzzer** | Grep `@given` in `tests/` | Coverage claim without fuzzer count |
| **Translator** | Read actual `.py` files | Explanation without code evidence |
| **Visualizer** | Read data structure definitions | Diagram without source file:line |
| **Advisor** | Read `TASKS.md`, relevant code | Strategy without architecture evidence |

---

## Verification Protocol

```
1. IDENTIFY claim to verify
2. USE Read or Grep tool to find evidence
3. CITE exact file:line from tool output
4. SHOW code snippet (copy from Read output)
5. MARK as VERIFIED: Yes

If you cannot verify:
→ State: "UNVERIFIED - [reason]"
→ Do NOT hallucinate evidence
```

---

## Multi-File Findings

```
FINDING: [description]
PRIMARY_FILE: /path/file1.py
LINES: 123-127
CODE:
    primary_code()
RELATED:
  - /path/file2.py:45-48 (calls this function)
  - /path/file3.py:200 (tests this behavior)
VERIFIED: Yes
```

---

## Prompt Snippet (Include When Spawning Agents)

```
MANDATORY: Every finding requires FILE:LINE + code snippet from Read/Grep output.

Before any analysis:
1. Read STATUS.md (current phase)
2. Read TASKS.md (context)

For EVERY finding, use this format:
FINDING: [description]
FILE: /path/file.py
LINES: 123-127
CODE:
    [paste from Read tool output]
VERIFIED: Yes

FORBIDDEN: Claims without evidence, "probably/likely", citing from memory.
Findings without file:line evidence will be REJECTED.
```

---

## Compliance Validation

Agent outputs are checked for:
- [ ] At least 1 `FILE:` citation per finding
- [ ] At least 1 `CODE:` block per finding
- [ ] Zero `VERIFIED: No` entries
- [ ] `STATUS.md` mentioned in first 50 lines
- [ ] No hallucination words (see `tools/validate_agent_compliance.py:HALLUCINATION_WORDS` for current list)

**Non-compliant outputs require revision before acceptance.**

---

## Reasoning Requirements (MANDATORY for Approvals)

**Approval verdicts require explicit reasoning traces:**

```
### CHECKED
- [what you verified, with file:line]
- [minimum 3 items for APPROVE/SECURE/PROVEN verdicts]
- [minimum 2 items for MINIMAL/GROUNDED verdicts]

### NOT_CHECKED
- [what you did NOT verify and why]
- [REQUIRED for any approval - acknowledges limitations]
```

**Why this matters:**
- Prevents overconfident approvals
- Makes review scope explicit
- Enables skeptic challenge on approvals
- Catches "rubber stamp" verdicts

**Enforcement:**
- `tools/validate_agent_reasoning.py` checks for CHECKED/NOT_CHECKED sections
- `run_review.py --rigorous` challenges approvals missing these sections
- Approval without NOT_CHECKED = overconfident = challenged by skeptic

---

## When Protocol Cannot Be Followed

| Situation | Action |
|-----------|--------|
| File doesn't exist | State: `FILE_NOT_FOUND: /path` |
| Grep returns 100+ results | State: `SAMPLE_VERIFIED: 10 of 150 matches checked` |
| Code changed since doc written | State: `DOC_STALE: doc says X, code shows Y at file:line` |
| Cannot find evidence for claim | State: `UNVERIFIED: searched [locations], found nothing` |

**These are not rejections - they're honest limitations.**

---

## Cross-Seed Compatibility Check (MANDATORY for Seed Reviews)

When reviewing any new or modified seed file, verify:

### 1. Pattern Requirements
```
FINDING: Pattern requirements
FILE: mu/[name].json
LINES: [meta section]
CODE:
    "requires_patterns": ["linear"] or ["non-linear"]
VERIFIED: Yes/No
```

- **Linear patterns**: Same variable can only appear once per pattern
- **Non-linear patterns**: Same variable appears twice (enforces equality via binding conflict)
- match.v2.json is LINEAR ONLY - seeds requiring non-linear patterns are BOOTSTRAP-DEPENDENT

### 2. Execution Layer Declaration
```
FINDING: Execution layer
FILE: mu/[name].json
LINES: [meta section]
CODE:
    "execution_layer": "BOOTSTRAP" or "META_CIRCULAR"
VERIFIED: Yes/No
```

- **BOOTSTRAP**: Runs via eval_seed.step() - Python/JS substrate provides non-linear support
- **META_CIRCULAR**: Runs via step_kernel_mu (kernel.v1 + match.v2 + subst.v2)
- If claiming META_CIRCULAR, show test that runs through step_kernel_mu

### 3. Integration Shape Compatibility
For seeds that chain together (e.g., enginenews → exhaust):

```
FINDING: Integration shape
UPSTREAM: [seed A output format]
DOWNSTREAM: [seed B input format]
BRIDGE: [projection or host code that adapts]
VERIFIED: Yes/No
```

- If no bridge exists, document as "requires host orchestration"

### 4. Reserved Fields Compatibility
```
FINDING: Reserved fields
FILE: mu/[name].json
FIELDS_USED: [list of _underscore fields]
IN_KERNEL_RESERVED: Yes/No (check step_mu.py KERNEL_RESERVED_FIELDS)
VERIFIED: Yes/No
```

---

## Execution Path Verification (MANDATORY for Integration Claims)

**Problem identified and addressed (2026-02-03):** Tests were verifying BEHAVIOR but not EXECUTION PATH. All tests could pass via bootstrap layer even when claimed meta-circular path was never executed. The following verification protocol is now MANDATORY.

### 1. Claim vs Reality Check
```
FINDING: Execution path verification
CLAIMED_PATH: [e.g., "runs through step_kernel_mu with bootstrap_structural"]
ACTUAL_TEST: [specific test file:line that verifies this path]
VERIFIED: Yes/No

If No: The claim is UNVERIFIED - behavior may be correct via different path
```

### 2. Projection Execution Evidence
For any claim that specific projections are executed:
```
FINDING: Projection execution
PROJECTION_ID: bridge.lookup.found_same
TEST_FILE: tests/test_execution_path.py
TEST_LINE: 45-67
EVIDENCE_TYPE: [trace log | unique output only possible from this projection | structural marker]
VERIFIED: Yes/No
```

**Valid evidence types:**
- **Trace log**: Test captures which projection IDs fired during execution
- **Unique output**: Test asserts output that can ONLY come from specific projection (not just correct behavior)
- **Structural marker**: Projection leaves unique marker in output that no other projection produces

**INVALID evidence:**
- "Tests pass" (behavior-only verification)
- "Documentation says X" (docs don't execute code)
- "Seed file exists" (files don't execute themselves)

### 3. Wiring Verification
When claiming code is wired to use a specific path:
```
FINDING: Wiring verification
FUNCTION: run_algorithm_meta_circular
FILE: rcx_pi/selfhost/step_mu.py
LINES: 400-420
CALLS: [what does it actually call?]
EXPECTED_CALL: step_kernel_mu with bootstrap_structural
ACTUAL_CALL: eval_seed.step (different path!)
VERIFIED: WIRING_MISMATCH
```

### 4. Integration Test Requirements
For any META_CIRCULAR claim, require:
```
TEST REQUIREMENT: At least one test must:
1. Run the specific claimed path (not just any path that works)
2. Verify execution via trace/unique-output/marker (not just behavior)
3. FAIL if the wrong path is used (even if behavior is correct)
```

### Anti-Pattern Detection
**Reject these patterns:**
- "Gate 6 complete" + "pending integration" (contradiction)
- "Tests pass" without execution path evidence
- "Declared META_CIRCULAR" without test showing meta-circular execution
- "Bootstrap_structural wired" without test showing bridge projections fire

---

## Cross-Substrate Parity (MANDATORY)

**HARD REQUIREMENT**: JavaScript and Python must produce identical results for ALL operations.

This is not optional. The JS bootstrap exists to prove substrate independence. If JS and Python diverge, we have two different runtimes instead of one portable system.

### Parity Verification Protocol

When reviewing any code change:
```
FINDING: Cross-substrate parity
PYTHON_FILE: /path/to/python_impl.py
JS_FILE: mu/host/js/eval_step.js
PARITY_TEST: tests/test_js_parity_automated.py::[TestClass]::[test_name]
VERIFIED: Yes/No
```

### Required Parity Tests

| Operation | Test |
|-----------|------|
| normalize/denormalize | `test_python_js_normalization_matches` |
| projection execution | `test_actual_cross_substrate_comparison` |
| constants (MAX_DEPTH, etc.) | `test_python_js_constants_match` |
| recurrence algorithm | `test_recurrence_with_bridge_*` |
| exhaustion algorithm | `test_exhaustion_with_bridge_*` |

### Anti-Pattern Detection

**Reject these patterns:**
- Python-only feature without JS equivalent
- JS-only feature without Python equivalent
- "JS parity not needed" claims (always needed)
- Tests that only run one substrate

---

## History

| Date | Change |
|------|--------|
| 2026-02-08 | Hardened: CODE block size cap (8KB), CHECKED/NOT_CHECKED blank-line tolerance, consolidated skeptic fail-closed |
| 2026-02-04 | Added Cross-Substrate Parity section (JS/Python parity is mandatory) |
| 2026-02-03 | Added Execution Path Verification (discovered tests verify behavior not path) |
| 2026-02-02 | Added Cross-Seed Compatibility Check (architectural gap found in 9-agent review) |
| 2026-02-01 | Initial version (9-agent review found hallucination issues) |
| 2026-02-01 | Simplified from 319 lines to ~120 (Expert feedback) |
| 2026-02-01 | Fixed tool references: Read/Grep not bash (Translator feedback) |
| 2026-02-01 | Added edge case handling (Fuzzer feedback) |
| 2026-02-01 | Added compliance validation checklist (Advisor feedback) |
| 2026-02-01 | 9-agent self-review fixes: line endings, tab indentation, expanded hallucination words |
