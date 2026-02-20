<!-- DOC_STATUS: REFERENCE -->
<!-- DOC_SCOPE: Codex→Claude prompt quality and audit contract for multi-wave sessions -->

# Codex→Claude Audit Contract v1

> **Current State**: See [`STATUS.md`](../STATUS.md) for L4 gate snapshot and current phase.
> **Authorization**: See [`TASKS.md`](../TASKS.md) for wave tracker sync notes and authorized work.
> **Scope**: This document defines DESIGN only — prompt quality standards and audit discipline for Codex→Claude multi-wave sessions.

## Purpose

Lock prompt quality and audit discipline so that multi-wave Claude sessions
produce verifiable, non-theatrical results. Every prompt must be machine-auditable
and every wave must leave a traceable evidence trail.

## Required Preflight Docs Read Order

Before any wave execution, Claude must read (in order):

1. `STATUS.md` — current phase, debt counts, gate snapshot
2. `TASKS.md` — Ra/NEXT/VECTOR/SINK, North Star invariants
3. `roadmap/MANIFEST.md` — canonical reading order and document roles
4. `ROADMAP.md` — sequence overview

## Required Prompt Fields

Every multi-wave Codex→Claude prompt must include these 7 fields:

| # | Field | Purpose |
|---|-------|---------|
| 1 | **Preflight gate** | What must be verified before work starts |
| 2 | **Primary uncertainty** | The single biggest risk or unknown |
| 3 | **Allowed/forbidden scope** | Explicit boundaries (what to touch, what not to) |
| 4 | **Evidence delta** | What new evidence this wave must produce |
| 5 | **Stop conditions** | When to stop (success criteria or failure modes) |
| 6 | **Validation gates** | Exact test/check commands to run before declaring done |
| 7 | **Push/merge block** | Explicit "no push without GO PUSH" or equivalent |

## Required Report Sections

Every wave completion report must include:

1. **Preflight result** — dev HEAD, branch, tree status, open PRs
2. **Gap fixes applied** — file-by-file summary of changes
3. **Contract consistency proof** — wave class, metadata, checker behavior
4. **Validation matrix** — exact pass counts for all required checks
5. **Branch/commit/PR-ready** — push command, PR target, merge instruction

## Anti-Theater Clauses

These rules prevent governance churn from substituting for real progress:

1. **No docs-only substitution for required L4_CLASS_A wave.** If a wave claims
   runtime progress, it must have executable runtime delta. Docs, tests, and
   governance changes do not count as L4_CLASS_A evidence.

2. **No runtime comment-only credit.** Changing comments or docstrings in
   runtime files does not satisfy L4_CLASS_A requirements. At least one
   non-comment line must change in a runtime/substrate directory.

3. **No status inflation without executable evidence.** STATUS.md gate
   advancement requires test evidence commands that pass, not narrative claims.

4. **Governance ratio cap.** Max 1 consecutive MAINTENANCE wave without an
   L4_CLASS_A wave. If 2 consecutive waves yield zero runtime evidence,
   freeze nonessential tooling until the next evidence wave ships.

5. **WIP cap.** Max 2 concurrent NEXT workstreams. Additional items must
   wait in VECTOR until a NEXT slot opens.

## Enforcement

- Wave classification: `tools/checks/enforce_l4_execution_contract.py`
- Prompt field locks: `tests/docs/test_status_tasks_consistency.py`
- Anti-theater detection: agent review (verifier + adversary)
- Gate evidence: `mu/docs/core/L4ExitChecklist.v0.md` evidence commands

## References

- [`STATUS.md`](../STATUS.md) — Current L4 status and gate snapshot
- [`TASKS.md`](../TASKS.md) — Wave tracker sync notes
- [`roadmap/L4ExecutionContract.v1.md`](L4ExecutionContract.v1.md) — Wave classification policy
- [`CLAUDE.md`](../CLAUDE.md) — Session onboarding and prompt contract section
