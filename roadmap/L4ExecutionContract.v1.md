<!-- DOC_STATUS: REFERENCE -->
<!-- DOC_SCOPE: L4 execution wave classification and anti-loophole enforcement -->

> **SUPERSEDED:** See [`L4ExecutionContract.v2.md`](L4ExecutionContract.v2.md) for the current 3-class wave classification policy. This v1 document is preserved for historical reference only.

# L4 Execution Contract v1

> **Current State**: See [`STATUS.md`](../STATUS.md) for L4 gate snapshot.
> **Authorization**: See [`TASKS.md`](../TASKS.md) for wave tracker sync notes.
> **Scope**: This document defines DESIGN only — wave classification policy and anti-loophole enforcement rules.

## Purpose

Prevent L4 progress from being bypassed by docs-only or governance-only churn.
Every wave that claims L4 progress must be machine-classifiable and auditable.

## Wave Classes

### L4_CLASS_A — Runtime/Substrate Progress

A wave classified as `L4_CLASS_A` **MUST** touch at least one file in a runtime
or substrate directory:

- `mu/host/` (Python or JS substrate code)
- `mu/substrate/` (kernel, match, subst seed files)
- `mu/closures/` (recurrence, exhaustion, fix seed files)
- `mu/bridge/` (bootstrap-structural bridge)
- `mu/programs/` (engine, hemispheres, metabolization seeds)
- `rcx_pi/selfhost/` (Python runtime)
- `tools/compilers/` (compilation tooling)

**Anti-loophole rules:**
- Docs-only or tests-only diff → auto-fail.
- Comment-only runtime delta → auto-fail. At least one non-comment line must change.
- The runtime delta must be *executable* (affects behavior, not just documentation).

### MAINTENANCE — Governance, Docs, Tooling

A wave classified as `MAINTENANCE` acknowledges it does not advance L4 directly.

**Required metadata in tracker sync note:**
- `NO_OP_PROOF: <reason why no runtime change was needed>`
- `target_gate_id: <Gn>` (which L4 gate this maintenance serves)

**Anti-loophole rules:**
- MUST NOT touch runtime/substrate directories listed above.
- No more than 1 consecutive `MAINTENANCE` wave without an `L4_CLASS_A` wave.

## Tracker Sync Note Format

Every wave's tracker sync note in `TASKS.md` must include:

```
Wave: <wave_id>
Class: L4_CLASS_A | MAINTENANCE
Gate: <target_gate_id>
Evidence: <what new evidence this wave produces>
```

For `MAINTENANCE` waves, add:
```
NO_OP_PROOF: <reason>
```

## Enforcement

Machine enforcement via `tools/checks/enforce_l4_execution_contract.py`:

| Mode | Usage | Where |
|------|-------|-------|
| `--staged` | Check staged files | Local pre-commit |
| `--range A...B` | Check commit range | CI (green_gate.yml) |
| `--files f1 f2` | Check explicit file list | Unit tests |

## References

- `STATUS.md` — Current L4 status and gate snapshot
- `TASKS.md` — Wave tracker sync notes
- `CLAUDE.md` — Summary of this contract (L4 Execution Contract section)
