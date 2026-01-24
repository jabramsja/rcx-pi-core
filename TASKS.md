# RCX-π TASKS (CANONICAL MASTER LIST)

This file enumerates **all known tasks** for the RCX-π repository.  
Tasks are never deleted. Status changes only.

RCX-π is a **finished minimal kernel**.  
All future growth occurs by *layering*, never by mutation of the core.

---

## STATUS LEGEND

- ✅ DONE – completed, verified, frozen
- 🔒 FROZEN – must not be modified
- 🟡 OPTIONAL – safe extension, not required
- ⏸ DEFERRED – explicitly not active
- 🚫 OUT OF SCOPE – tracked but not part of RCX-π Core

---

## A. RCX-π CORE KERNEL

**Status:** ✅ DONE / 🔒 FROZEN  
**Tag:** `rcx-pi-green-002`

### A1. Motifs
- ✅ Single constructor `μ(...)`
- ✅ VOID / UNIT
- ✅ Structural equality
- ✅ No hidden host data

### A2. Evaluator
- ✅ PureEvaluator
- ✅ Structural reduction
- ✅ Hosted closures via `meta["fn"]`
- ✅ Deterministic execution

### A3. Numbers (Peano)
- ✅ `num(n)`
- ✅ `motif_to_int`
- ✅ Addition
- ✅ Tests pass

### A4. Lists
- ✅ CONS/NIL encoding
- ✅ Python round-trip helpers
- ✅ Shape-only validation

### A5. Closures
- ✅ swap / dup / rotate / reverse / append
- ✅ seq / map combinators
- ✅ add1

### A6. Bytecode VM
- ✅ Motif-encoded stack machine
- ✅ Opcode set
- ✅ Bytecode closure execution

### A7. Projection system
- ✅ Structural pattern matching
- ✅ Variable motifs
- ✅ Projection + activation

### A8. Program registry
- ✅ Named programs
- ✅ `succ-list` canonical example

---

## B. RUST MU RUNTIME

**Status:** ✅ DONE / 🔒 FROZEN

- ✅ r_a / lobes / sink routing
- ✅ Rewrite(Mu)
- ✅ Deterministic precedence
- ✅ Fallback classifier

Worlds:
- ✅ rcx_core.mu
- ✅ vars_demo.mu (precedence fixed)
- ✅ pingpong.mu
- ✅ paradox_1over0.mu

---

## C. PYTHON ↔ RUST BRIDGE

**Status:** ✅ DONE / 🔒 FROZEN

- ✅ MU ↔ JSON conversion
- ✅ Round-trip stability
- ✅ Behavioral parity verified

---

## D. TESTING & GATES

**Status:** ✅ DONE

### D1. Python
- ✅ Kernel invariants
- ✅ Contract tests
- ✅ Orbit artifact regression coverage

### D2. Rust
- ✅ classify / repl / orbit / snapshot examples
- ✅ State save & restore
- ✅ Snapshot integrity verification

### D3. Repo-wide green gate
- ✅ `scripts/green_gate.sh`
- ✅ Python syntax check
- ✅ Full pytest suite
- ✅ Rust example suite
- ✅ Canonical health signal

### D4. Orbit artifact determinism (NEW)
- ✅ SVG normalization test (Graphviz comment stripping)
- ✅ Orbit SVG idempotence verification
- ✅ Orbit DOT / index fixture stability
- ✅ Orbit artifact re-run produces byte-identical outputs

### D5. Orbit provenance semantics (NEW)
- ✅ Provenance schema validated
- ✅ Supports state entries as strings or `{i, mu}` objects
- ✅ Semantic linkage enforced: `state[i-1] → state[i]`
- ✅ Backward compatibility for `from/to` vs `pattern/template`

---

## E. TOOLING & WORKFLOWS

**Status:** ✅ DONE

- ✅ Deterministic CI gates for all orbit artifacts
- ✅ Manual-safe PR merge flow (no auto-merge dependency)
- ✅ Rebase-before-merge enforcement
- ✅ `scripts/merge_pr_clean.sh` for canonical PR hygiene

---

## F. DOCUMENTATION

**Status:** 🟡 PARTIAL / IN PROGRESS

### F1. README.md
- ✅ Mentions `green_gate.sh` as authoritative
- ✅ `run_all.py` marked legacy

### F2. README_BOOTSTRAP.md
- ✅ AI onboarding guide
- ✅ Repo mental model
- ✅ World semantics

### F3. Spine & governance docs
- 🟡 RCX minimal spine manifest alignment
- 🟡 NEXT_STEPS.md reconciliation
- 🟡 CHANGELOG.md backfill for recent gate additions

---

## G. EXPLICITLY OUT OF SCOPE

- 🚫 Kernel mutation
- 🚫 Self-modifying evaluator
- 🚫 Non-deterministic execution
- 🚫 Heuristic or probabilistic rewrite rules

---

## H. NEXT TRACKED WORK (NOT STARTED)

- ⏸ Documentation consolidation pass
- ⏸ Optional visualization tooling (read-only)
- ⏸ External consumer packaging (wheel / crate)

---

**End of file.**