# RCX-π Kernel Overview

**Status: LEGACY - See `docs/RCXKernel.v0.md` for current architecture**

---

## Historical Context

This document described the original RCX-π kernel based on:
- PureEvaluator with closures stored in `meta["fn"]`
- Motif-encoded bytecode VM
- Projection system with pattern matching built into the kernel

This architecture has been superseded by a simpler design where:
- The kernel has only 4 primitives (hash, stall detect, trace, dispatch)
- Pattern matching is seed responsibility, not kernel
- Seeds are pure Mu (no Python functions)
- Self-hosting is achieved via EVAL_SEED

---

## Current Architecture

See `docs/RCXKernel.v0.md` for the new kernel specification:

**Kernel Primitives (4 only):**
- `compute_identity(mu)` - SHA-256 of canonical JSON
- `detect_stall(before, after)` - Compare hashes
- `record_trace(entry)` - Append to history
- `gate_dispatch(event, context)` - Route to seed handlers

**NOT kernel primitives:**
- Pattern matching (seed responsibility)
- Projection application (seed responsibility)
- Rule selection (seed responsibility)

**Key insight:** The kernel is maximally dumb. Seeds define all semantics.

---

## Why the Change

The original architecture had Python closures (`meta["fn"]`) embedded in motifs. This violated structural purity - we were programming ABOUT RCX, not IN RCX.

The new architecture ensures:
1. Seeds are pure Mu (JSON-compatible, no Python functions)
2. The evaluator (EVAL_SEED) is itself structure
3. Self-hosting proves emergence from structure alone

---

## Legacy Code

The following modules implement the legacy architecture and remain for backward compatibility with existing tests:

| Module | Purpose | Status |
|--------|---------|--------|
| `core/motif.py` | Motif object | Still used |
| `engine/evaluator_pure.py` | Closure-based evaluator | Legacy |
| `programs.py` | Hosted closures (swap, dup, etc.) | Legacy |
| `bytecode_vm.py` | Bytecode VM with v1b opcodes | Being evolved |

---

## Migration Path

1. New kernel code goes in `rcx_pi/kernel.py` (when created)
2. Seeds go in `seeds/` directory as JSON files
3. Legacy tests continue to pass
4. New tests use the new architecture

---

## References

- `docs/RCXKernel.v0.md` - New kernel specification
- `docs/StructuralPurity.v0.md` - Guardrails for Mu purity
- `docs/MuType.v0.md` - The universal data type
- `Why_RCX_PI_VM_EXISTS.md` - Alignment document
