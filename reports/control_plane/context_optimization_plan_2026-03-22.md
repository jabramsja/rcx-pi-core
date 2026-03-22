<!-- DOC_STATUS: REFERENCE -->
<!-- DOC_ROLE: Plan packet for context optimization wave -->

# Context Optimization Plan — CLAUDE.md + Memory Slimming

**Wave class:** MAINTENANCE
**Target gate:** G8
**Phase-A-Lock:** LOCKED
**Date:** 2026-03-22

---

## Problem Statement

Every Claude Code session loads CLAUDE.md (601 lines, 34KB) + MEMORY.md (89 lines) + all memory files referenced from MEMORY.md (~460 lines). Total context tax: **~1,150 lines / ~70KB before a single word of actual work.**

### Duplication Map (the real waste)

| Content | Location 1 | Location 2 | Location 3 |
|---------|-----------|-----------|-----------|
| Behavioral XML (12 rules) | CLAUDE.md:9-22 | MEMORY.md:5-18 | — |
| Procedural XML (9 rules) | CLAUDE.md:24-33 | MEMORY.md:20-29 | — |
| Wave protocol XML | CLAUDE.md:35-63 | MEMORY.md:31-62 | feedback_wave_discipline.md:18-57 |
| Commit pipeline (8 steps) | CLAUDE.md:50-59 | user_founder_preferences.md:21-31 | feedback_wave_discipline.md:39-48 |
| Bot thread resolution | CLAUDE.md workflow section | feedback_operational_gotchas.md:7-16 | — |
| Pre-commit supervisor | CLAUDE.md step 1b | feedback_pre_commit_gate.md | — |

**The behavioral XML block alone is loaded 2x per session (CLAUDE.md + MEMORY.md) — 58 lines of pure waste.**

---

## Scope

### In scope
1. **CLAUDE.md** — slim from 601 to ~250 lines
2. **MEMORY.md** — slim from 89 to ~25 lines (index only, no content)
3. **Memory files** — consolidate 19 files to ~6 files
4. **Archive** — save current manual protocol to `reports/archive/manual_wave_protocol_2026-03-22.md`
5. **Replace** manual Phase A/B/commit protocol references with executor-based workflow

### Out of scope
- STATUS.md, TASKS.md content
- Runtime code, seeds, tests
- Agent prompts, bridge config
- L4 contract enforcement scripts

### Stop conditions
- If slimming CLAUDE.md breaks pre-commit-doc-check → stop, investigate
- If memory consolidation loses a unique founder correction → stop, preserve it

---

## CLAUDE.md Optimization Plan

### Section-by-section decisions

| Section | Current Lines | Action | Target Lines | Rationale |
|---------|:---:|--------|:---:|-----------|
| BEHAVIORAL PROTOCOL XML | 74 | **Keep, compress** — remove `<wave_protocol>` (executors own this now), keep behavioral + procedural rules | ~40 | Wave protocol moves to executor docs; rules stay as authority |
| SESSION ONBOARDING | 28 | **Keep, slim** — cut the "everything else is reference" paragraph | ~20 | Still essential |
| What RCX Is | 22 | **Compress** — 3 sentences + 1 parity sentence | ~6 | Full rationale in Why_RCX_PI_VM_EXISTS |
| Current Status | 10 | **Delete** — just says "read STATUS.md" | 0 | Pointer is already in Session Onboarding |
| Agents | 85 | **Compress to table + ref** — keep "what agents are" + trigger table + key commands | ~25 | Detail lives in AgentRunbook.v0.md |
| Agent Bridge | 24 | **Compress** — 2-line summary + ref | ~5 | Detail in AgentBridgeProtocol.v0.md |
| Workflow | 66 | **Compress** — branching model (2 lines) + audit tiers table + "run audit_all before push" | ~20 | Cut command examples |
| Test Execution | 99 | **Compress** — classification table + auto-marking note + verification commands | ~30 | Cut examples, keep rules |
| Phase Transitions | 11 | **Delete** — 3 lines of "update STATUS.md" | 0 | Obvious |
| L4 Execution Contract | 32 | **Compress** — keep class table + ref to doc | ~15 | Full spec in L4ExecutionContract.v2.md |
| L4 Parity-Floor | 26 | **Move to doc ref** — one-line pointer | ~2 | On-demand reference |
| L4 Momentum Guardrails | 20 | **Move to doc ref** — one-line pointer | ~2 | On-demand reference |
| Codex→Claude Prompt Contract | 20 | **Move to doc ref** — one-line pointer | ~2 | On-demand reference |
| Key Files | 18 | **Keep** | ~18 | Quick reference |
| Doc Governance | 42 | **Compress** — Three Laws + verification command | ~12 | Cut examples |
| Governance & Invariants | 7 | **Keep** | ~7 | Points to TASKS.md |

**Projected total: ~204 lines** (from 601, 66% reduction)

### What moves where

| Removed from CLAUDE.md | New home |
|------------------------|----------|
| Wave protocol XML (Phase A/B/commit steps) | Executors own the protocol now. Archive old manual version to `reports/archive/` |
| L4 Parity-Floor Policy | Already in `roadmap/L4ExecutionContract.v2.md` |
| L4 Momentum Guardrails | Already in `TASKS.md` SINK section |
| Codex→Claude Prompt Contract | Remains in `mu/docs/agents/` reference |
| Detailed agent command examples | `mu/docs/agents/AgentRunbook.v0.md` |
| Detailed test execution examples | On-demand via `pytest --help` |

---

## Memory Optimization Plan

### MEMORY.md — Strip to pure index

**Current:** 89 lines (58 lines of verbatim XML + 31 lines of index)
**Target:** ~25 lines (pure index, no content)

Remove the entire "Founder Working Contract (XML)" block and "Canonical Sources" section. These are in CLAUDE.md already.

### Memory file consolidation

| Action | Files | Result |
|--------|-------|--------|
| **DELETE** (pure duplication of CLAUDE.md) | — | MEMORY.md XML block is the main win |
| **ARCHIVE + DELETE** | `feedback_wave_discipline.md` (68 lines) | Content is now: (a) behavioral rules in CLAUDE.md, (b) commit pipeline is executor-owned, (c) critical mistakes preserved in consolidated file |
| **CONSOLIDATE** into `feedback_consolidated.md` | 12 feedback files → 1 file | Each correction becomes 2-3 lines: rule + why |
| **DELETE** (stale) | `project_deferred_post_wave20.md` | PR counts are 2 weeks stale; items either done or still in TASKS.md |
| **UPDATE** | `project_next_wave_context.md` | Will be updated at wave end |
| **KEEP as-is** | `user_founder_preferences.md` | Unique content, slim the duplicated commit pipeline |
| **KEEP as-is** | `reference_custom_skills.md` | Skill reference, still current |
| **KEEP as-is** | `project_canonical_machine_direction.md` | Still-active architectural directive |
| **KEEP + UPDATE** | `feedback_use_implemented_automation.md` | Update to reflect executor completion |

### Consolidated feedback file structure

`feedback_consolidated.md` will contain one-liner rules extracted from the 12 individual files:

```
1. Fix issues, don't classify them to avoid work (deflection_pattern)
2. Identity: I work hard, think hard, produce excellent work (self_identity)
3. Bot threads: READ before resolving, check after EVERY push (operational_gotchas)
4. CI: check after push, fix immediately, commit ALL modified files (operational_gotchas)
5. L4 contract: wave_id = branch suffix, mu/tests/ not tests/, indicator needs -f (operational_gotchas)
6. No rule recitation — prove compliance through behavior (no_rule_recitation)
7. Investigate with commands, never hand-wave (investigate_dont_handwave)
8. Pre-commit: run supervisor explicitly, hook verifies receipt (pre_commit_gate)
9. Rigor over speed when founder sets that stance (rigor_over_speed)
10. Phase B = IMPLEMENT code, not commit planning docs (phase_b_means_implement)
11. Phase-A-Lock is routing signal, not founder gate (phase_a_lock_not_founder_gate)
12. NEEDS_PHASE_B = bridge loop only, not re-run agents (needs_phase_b_bridge_only)
13. Use web search, agents, bridge when stuck (team_resources)
14. Use every automation surface you've built (use_implemented_automation)
15. Between review phases: audit_fast only, full suite once at end (operational_gotchas)
```

Each with a one-line "Why" so I can judge edge cases.

### Archive strategy

`reports/archive/manual_wave_protocol_2026-03-22.md` will contain:
- The full Phase A/B/commit protocol as it existed before executors
- Preserved verbatim from `feedback_wave_discipline.md` + `CLAUDE.md` wave_protocol XML
- Marked as historical reference, not operational

---

## Validation

```bash
# Pre-commit doc check still passes
./tools/pre-commit-doc-check

# CLAUDE.md is under 300 lines
wc -l CLAUDE.md  # expect ~200-250

# Memory files are consolidated
ls ~/.claude/projects/*/memory/*.md | wc -l  # expect ~6-8 files

# MEMORY.md is under 30 lines
wc -l ~/.claude/projects/*/memory/MEMORY.md  # expect ~25

# No content lost — all unique corrections in consolidated file
grep -c "^[0-9]" ~/.claude/projects/*/memory/feedback_consolidated.md  # expect 17
```

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Pre-commit-doc-check references CLAUDE.md structure | Verify hook script doesn't grep for removed sections |
| Agents reference CLAUDE.md sections | Agent prompts reference STATUS.md/TASKS.md, not CLAUDE.md |
| Founder muscle memory for /wave protocol | Archive is accessible, executors are the replacement |
| Lost unique feedback | Consolidation preserves every correction with "Why" |

---

## Wave Class Justification

**MAINTENANCE** — no runtime files touched, no L4 gate progress. Pure governance/docs optimization.
- `no_op_proof`: Only CLAUDE.md, memory files, and archive docs changed
- `defer_reason_code`: CONTEXT_OPTIMIZATION
- `target_gate_id`: G8

---

## Execution order

1. Archive current manual protocol → `reports/archive/`
2. Write consolidated `feedback_consolidated.md`
3. Slim `user_founder_preferences.md` (remove duplicated commit pipeline)
4. Slim CLAUDE.md (section by section per table above)
5. Rewrite MEMORY.md as pure index
6. Delete superseded memory files
7. Update `project_next_wave_context.md`
8. Run validation commands
9. Commit
