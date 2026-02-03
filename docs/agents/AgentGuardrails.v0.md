# Agent Guardrails v0

> **TL;DR:** Every finding needs `FILE:LINE` + code snippet. No citation = rejected.

---

## Core Rule

```
FINDING: [description]
FILE: /absolute/path/file.py
LINES: 123-127
CODE:
    actual_code_from_read_tool()
VERIFIED: Yes
```

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
- [ ] No hallucination words (`probably`, `likely`, `seems`, `assume`, `appears`, `possibly`, `could`, `perhaps`, `suggests`)

**Non-compliant outputs require revision before acceptance.**

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

## History

| Date | Change |
|------|--------|
| 2026-02-02 | Added Cross-Seed Compatibility Check (architectural gap found in 9-agent review) |
| 2026-02-01 | Initial version (9-agent review found hallucination issues) |
| 2026-02-01 | Simplified from 319 lines to ~120 (Expert feedback) |
| 2026-02-01 | Fixed tool references: Read/Grep not bash (Translator feedback) |
| 2026-02-01 | Added edge case handling (Fuzzer feedback) |
| 2026-02-01 | Added compliance validation checklist (Advisor feedback) |
| 2026-02-01 | 9-agent self-review fixes: line endings, tab indentation, expanded hallucination words |
