# Agent Bridge (Codex <-> Claude)

Purpose: a single shared ledger for structured handoff and convergence.

Important: true "direct agent-to-agent chat" is not possible here. Best practice is:
1) one agent makes changes,
2) the other agent reviews/challenges,
3) repeat until convergence.

This file makes that loop fast and auditable.

## Rules

1. Single writer at a time.
2. Never delete prior rounds; only append.
3. Every claim must include evidence (command/test/file refs).
4. If code changes are made, include exact files touched.
5. End each round with a clear `REQUEST_FOR_NEXT_AGENT`.

## Round Format (append-only)

Use this template exactly:

```md
## Round <ID> — <AgentName>
DATE: YYYY-MM-DD
BRANCH: <branch>
SCOPE: <short scope>

### Objective
<what this round is trying to prove/do>

### Changes
- <file path>: <what changed>

### Evidence
- Command: `<command>`
  - Result: <short result>
- File refs:
  - `<absolute/or-workspace path>:<line>`

### Findings
- P1/P2/P3: <finding or "None">

### Decision
GO | NO-GO | GO-WITH-RISKS
Reason: <1-3 lines>

### REQUEST_FOR_NEXT_AGENT
<single concrete request, acceptance checks, and expected output format>
```

## Acceptance Contract

When proposing completion, include:

- Required tests run and results
- `git diff --name-only` scope check
- Residual risk statement

## Non-Negotiables

- No hidden assumptions
- No silent scope expansion
- No "trust me" claims without reproducible evidence

## Starter Prompt for Claude

Use this with Claude:

```text
Use /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/AGENT_BRIDGE.md as the only collaboration ledger.
Read the latest round.
If there is a REQUEST_FOR_NEXT_AGENT, execute it and append a new round using the exact template in that file.
Do not rewrite prior rounds. Append only.
Provide evidence-first output (commands/tests/file refs), then decision (GO/NO-GO), then next request.
```

---

## Round 13A — Claude
DATE: 2026-02-10
BRANCH: dev (working tree, uncommitted)
SCOPE: GAP-04-FIX design contract — no runtime changes

### Objective
Turn GAP-04-FIX from "known gap" into a concrete, test-locked design contract promotable from VECTOR. Define Fix intent, input/output shapes, 5 invariants, disallowed behaviors, and 5 evidence items required for VECTOR → NEXT.

### Changes
- `docs/core/EngineNewFixContract.v0.md` (new): Design contract for EngineNew step 4 (Rule 0.6). DOC_STATUS header (DESIGN_SPEC). Defines input shape (stalled_state, stall_hash, tau_step, engine_iteration), output shape (fixed_state, fix_applied, fix_type), 5 invariants (I1: minimality, I2: structural purity, I3: idempotence safety, I4: stall-breaking, I5: no semantic drift), disallowed behaviors table, and 5 evidence items (E1–E5) for promotion.
- `tests/test_engine_cycle_mapping.py`: Extended `GapEntry` NamedTuple with `contract_doc` (str) and `invariants` (tuple[str, ...]) fields. Updated GAP-04-FIX entry with contract doc ref, 5 invariant IDs, and E1–E5 in unblock_condition. Added `TestGapContractDocs` class (6 tests): doc exists on disk, ≥3 invariants declared, invariant labels cross-referenced in doc text, E1–E5 referenced in unblock_condition, DOC_STATUS governance compliance, consistency guard for gaps without contract docs.
- `TASKS.md`: Expanded VECTOR GAP-04-FIX item with contract doc link and 5 explicit checkbox items (E1–E5).

### Evidence
- Command: `PYTHONHASHSEED=0 pytest -q tests/test_engine_cycle_mapping.py -v`
  - Result: 22 passed (16 existing + 6 new TestGapContractDocs)
- Command: `PYTHONHASHSEED=0 pytest -q tests/docs/test_roadmap_governance.py`
  - Result: 11 passed
- Command: `git diff --name-only`
  - Result: `TASKS.md`, `tests/test_engine_cycle_mapping.py` (2 modified files)
- Command: `git status --short`
  - Result: `M TASKS.md`, `M tests/test_engine_cycle_mapping.py`, `?? docs/core/EngineNewFixContract.v0.md` (new untracked), `?? AGENT_BRIDGE.md`, `?? reports/`
- Structural/gap tally: 8 structural / 2 gaps (unchanged)
- File refs:
  - `docs/core/EngineNewFixContract.v0.md:1` — new contract doc
  - `tests/test_engine_cycle_mapping.py:155` — GapEntry with contract_doc + invariants fields
  - `tests/test_engine_cycle_mapping.py:163` — GAP-04-FIX entry with 5 invariant IDs
  - `tests/test_engine_cycle_mapping.py:401` — TestGapContractDocs class (6 tests)
  - `TASKS.md:371` — GAP-04-FIX with E1–E5 checkboxes

### Findings
- None. All tests pass, tally unchanged, no runtime files touched.

### Decision
GO
Reason: GAP-04-FIX is now a test-locked design contract with 5 invariants (I1–I5), 5 evidence items (E1–E5), and cross-references enforced by 6 new tests. No runtime changes, no tally change, no ontology expansion. Ready for commit + PR.

### REQUEST_FOR_NEXT_AGENT
Commit and create PR for Round 13A:
1. `git add docs/core/EngineNewFixContract.v0.md tests/test_engine_cycle_mapping.py TASKS.md`
2. `git commit -m "docs(engine): add EngineNewFixContract.v0.md and lock GAP-04-FIX design contract"`
3. Push to new branch `feat/round13a-gap04-fix-contract`
4. Create PR against `dev` with title: "GAP-04-FIX: design contract with test-locked invariants and promotion checklist"
5. Acceptance: `pytest -q tests/test_engine_cycle_mapping.py` (22 pass), `pytest -q tests/docs/test_roadmap_governance.py` (11 pass), CI green.
6. Append Round 13B to AGENT_BRIDGE.md with commit SHA, PR URL, and CI status.

