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
- ✅ 137 tests passing
- ✅ Kernel invariants
- ✅ Contract tests

### D2. Rust
- ✅ classify / repl / orbit / snapshot examples
- ✅ State save & restore

### D3. Repo-wide green gate
- ✅ `scripts/green_gate.sh`
- ✅ Python syntax check
- ✅ Full pytest
- ✅ Rust example suite
- ✅ Canonical health signal

---

## E. DOCUMENTATION

### E1. README.md
- ✅ Mentions `green_gate.sh` as authoritative
- ✅ `run_all.py` marked legacy

### E2. README_BOOTSTRAP.md
- ✅ AI onboarding guide
- ✅ Repo mental model
- ✅ World semantics

### E3. Kernel snapshot
- ✅ rcx-pi-green-002 documented
- ✅ Features frozen
- ✅ Test status recorded

### E4. Legacy helpers
- 🟡 `rcx_python_examples/run_all.py`
- 🟡 Kept for historical reference
- 🟡 Not used as a gate

---

## F. TOOLING EXTENSIONS


- ✅ JSON diff / inspection
**Status:** 🟡 OPTIONAL
- ✅ World auto-documentation
- ✅ JSON diff / inspection
- ✅ Rule precedence visualization

---

## G. CONTRACT EXTENSIONS

**Status:** 🟡 OPTIONAL
- ✅ Rewrite termination contracts
- ✅ Snapshot integrity checks
- ⬜ CI hook for `green_gate.sh`

---

## H. MUTATION & EVOLUTION TOOLS

**Status:** ⏸ DEFERRED

- ⬜ Rule mutation sandbox (isolated)
- ⬜ World scoring metrics
- ⬜ Orbit visualization

---

## I. RCX-Ω / META-CIRCULAR LAYERS

**Status:** 🚫 OUT OF SCOPE (TRACKED)

- ⬜ Self-hosting evaluator
- ⬜ Motif-defined evaluator
- ⬜ Meta-projection layers
- ⬜ Observer curvature modeling
- ⬜ Emergent world generation

---

## GLOBAL RULES

- Kernel is immutable
- Green gate is law
- New behavior = new layer
- Tests override docs
- Docs override ideas
- No experimental code enters core

---

**Current kernel:** `rcx-pi-green-002`  
**Green status:** VERIFIED
------------------------------------------------------------
Governance & Execution Rails (Binding)

All RCX-Ω work is governed by:

  docs/RCX_OMEGA_GOVERNANCE.md

This document defines:
- The Frozen / Staging / Vector zones
- The NOW / NEXT / VECTOR queues
- Readiness-detected promotion rules (including self-hosting)
- Execution discipline and conflict resolution

If there is any ambiguity:
- Governance overrides enthusiasm
- Tests override documentation
- Repo state overrides conversation state
------------------------------------------------------------
