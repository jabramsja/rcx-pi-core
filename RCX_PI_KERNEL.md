# RCX-π Kernel Overview

**Status: This file is a pointer. See canonical docs below.**

---

## Current Architecture (Phase 1-2 Complete)

The kernel has 4 primitives only:
- `compute_identity(mu)` - SHA-256 of canonical JSON
- `detect_stall(before, after)` - Compare hashes
- `record_trace(entry)` - Append to history
- `gate_dispatch(event, context)` - Route to seed handlers

**Implementation:** `rcx_pi/kernel.py`

Pattern matching and projection application are NOT kernel primitives - they are seed responsibility (EVAL_SEED).

---

## Canonical Documentation

| Doc | Purpose |
|-----|---------|
| `docs/RCXKernel.v0.md` | Kernel specification (4 primitives, seed hierarchy) |
| `docs/EVAL_SEED.v0.md` | Evaluator specification (match, substitute, step) |
| `docs/StructuralPurity.v0.md` | Guardrails for Mu purity |
| `docs/MuType.v0.md` | Universal data type definition |

---

## Current Phase: Phase 3 (EVAL_SEED as Mu)

Phase 2 (Python EVAL_SEED) is complete. Phase 3 requires expressing EVAL_SEED logic as Mu projections without host recursion.

See `TASKS.md` for detailed status.
