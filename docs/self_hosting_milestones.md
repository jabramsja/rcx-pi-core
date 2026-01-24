# Self-hosting & Meta-circular Milestone Map (v1)

This is a **design-only** map. It does **not** authorize implementation jumps.
The goal is to keep our sequencing honest: contracts first, VM later, meta-circular last.

## Definitions (working)

- **Self-hosting (RCX VM)**: an RCX-defined bytecode/VM that can execute RCX programs without relying on Python/Rust for semantics (Python/Rust may remain as tooling during transition).
- **Meta-circular**: RCX can run a definition of (some version of) itself inside itself (interpreter/compiler/VM), producing behavior that is stable and testable.

## Milestones (ordered)

### M0. Host baseline (current reality)
RCX is hosted in Python with a Rust overlay for certain functionality, with CI gates for determinism where applicable.

**Exit criteria**
- Repo green gates are authoritative.
- Canonical contracts exist for any “public” outputs we depend on (schema-triplets already done).

### M1. Determinism contracts (Trace + IO)
Before any VM, we need deterministic observables:
- Trace contract (what happened)
- IO/snapshot contract (what is persisted/emitted)

**Exit criteria**
- Canonical trace schema exists + tests enforce it.
- Replay gate exists (trace → replay → diff empty).
- Canonical JSON/FS ordering policies are documented + tested.

### M2. VM spec (ISA + loader) on paper
Write the smallest VM spec that can host a subset of μ/evaluation.
No optimizations. No “nice-to-haves”.

**Exit criteria**
- Minimal ISA documented (ops, stack model, memory model).
- Loader format documented (bytecode container, versioning).
- Reference interpreter plan: how to test each opcode deterministically.

### M3. Reference interpreter (still hosted)
Implement the VM reference interpreter in the host language(s) as a stepping stone,
but with semantics frozen by tests so it can later be ported.

**Exit criteria**
- A minimal bytecode program can run deterministically under the reference interpreter.
- Golden fixtures exist for opcode semantics.

### M4. “Organism extraction” (map components)
Map current Python/Rust pieces into:
- VM responsibilities (must be in bytecode/VM eventually)
- Tooling responsibilities (can remain host-side)

**Exit criteria**
- A written mapping exists and is accepted as canonical.
- Explicit “what stays tooling” list exists.

### M5. Seeded self-host loop (minimal)
The system can rebuild/rehydrate a minimal core artifact deterministically using RCX-defined execution (even if still hosted).

**Exit criteria**
- Given seed input, the same build artifacts are produced byte-identically.
- CI gate catches drift.

### M6. Meta-circular attempt (strict subset)
Only after contracts + VM are stable:
RCX runs a definition of itself (or strict subset) inside itself.

**Exit criteria**
- A minimal meta loop passes deterministic tests.
- Clear versioning: “meta-circular subset v1” is defined and frozen.

## Explicit non-goals (until later)
- Performance/JIT
- Optimization passes
- Broad language features
- Concurrency
- “Clever” self-modifying behavior
