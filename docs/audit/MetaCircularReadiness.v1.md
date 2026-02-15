<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-03
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# RCX Meta-Circular Readiness Definition (v1)

> **Current status:** See `STATUS.md` for current phase and L-level. This doc defines the criteria.

> ⚠️ **FUTURE ACCEPTANCE CRITERIA** — This document defines gates and criteria for meta-circular readiness (L4 - True Self-Hosting). No section implies current achievement unless explicitly marked PASS. See `STATUS.md` for what is actually achieved vs planned.

**Status: DESIGN DOCUMENT — No code changes.**

This document defines explicit, measurable criteria for meta-circular readiness. It is the single authoritative definition for v1.

---

## 1. Definition: Meta-Circular (v1)

**Meta-circular execution** means: RCX can execute a definition of itself (or a strict subset) inside itself, producing behavior that is:

1. **Deterministic**: Same input → same output (diff-empty, CI-verified)
2. **Stable**: The meta loop does not diverge or require host intervention
3. **Testable**: Golden fixtures validate the meta loop behavior
4. **Versioned**: "Meta-circular subset v1" is explicitly scoped and frozen

---

## 2. Prerequisites (Hard Gates)

These gates MUST be passed before meta-circular work begins. Each gate is binary (pass/fail) and CI-enforced.

### Gate 1: Deterministic Trace Contract

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Canonical trace schema exists (v1) | `docs/schemas/rcx-trace-event.v1.json` | PASS |
| Trace canonicalization helper exists | `rcx_pi/trace_canon.py` | PASS |
| Unit tests validate canonicalization | `tests/test_replay_gate_idempotent.py` | PASS |

### Gate 2: Replay Determinism

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Replay CLI exists | `python -m rcx_pi.rcx_cli replay` | PASS |
| Replay gate enforces diff-empty | `tests/test_replay_gate_idempotent.py` | PASS |
| Golden fixtures exist | `tests/fixtures/traces/*.v1.jsonl` | PASS |
| Rust acceleration bit-for-bit compatible | `archive/rcx_pi_rust/src/replay_cli.rs` | PASS |

### Gate 3: Entropy Sealing

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Entropy budget documented | `EntropyBudget.md` | PASS |
| PYTHONHASHSEED=0 enforced | CI environment | PASS |
| No RNG in deterministic paths | Code audit | PASS |
| Dict/set iteration sealed | Explicit sorted() | PASS |

### Gate 4: Bytecode Mapping (v0) — ARCHIVED

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Trace event → op mapping defined | `docs/archive/bytecode/BytecodeMapping.v0.md` | ARCHIVED |
| Minimal VM state model defined | `docs/archive/bytecode/BytecodeMapping.v0.md` | ARCHIVED |
| Reserved ops documented (stall/fix/closure) | `docs/archive/bytecode/BytecodeMapping.v0.md` | ARCHIVED |
| Fail-loud policy defined | `docs/archive/bytecode/BytecodeMapping.v0.md` | ARCHIVED |

**Note**: Bytecode approach has been superseded by kernel + seeds architecture. See Section 9.

### Gate 5: Reference Interpreter — SUPERSEDED

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Minimal bytecode program runs deterministically | — | SUPERSEDED |
| Opcode semantics covered by fixtures | — | SUPERSEDED |

**Superseded**: Gate 5 (bytecode interpreter) has been replaced by the kernel + EVAL_SEED approach. Self-hosting is achieved via Phase 5 (`step_mu` uses `match_mu` + `subst_mu` Mu projections). See `docs/core/SelfHosting.v0.md`.

---

## 3. Meta-Circular Subset (v1 Scope)

The v1 meta-circular subset is intentionally minimal. It includes ONLY:

### In Scope

| Component | Definition |
|-----------|------------|
| **Trace replay** | Parse JSONL → canonicalize → emit canonical JSONL |
| **Event types** | trace.start, step, trace.end (frozen v1 schema) |
| **Mu payload** | JSON-ish values (null, bool, int, string, array, object) |
| **Canonicalization** | Key order v→type→i→t→mu→meta, deep-sort dicts |
| **Contiguity check** | event.i must be 0..n-1 in order |

### Explicitly Out of Scope (v1)

| Component | Reason |
|-----------|--------|
| **Closure semantics** | Requires Stall → Fix loop execution |
| **Bucket routing** | Requires execution semantics |
| **Pattern evaluation** | Requires closure semantics |
| **Self-modifying behavior** | Requires meta loop stability first |
| **Performance optimization** | Correctness before speed |
| **Concurrency** | Forbidden by EntropyBudget.md |

**Note on v2 Observability**: Stall/fix events are now OBSERVABLE via v2 trace events (`reduction.stall`, `reduction.applied`, `reduction.normal`) gated by `RCX_TRACE_V2=1`. Execution semantics (v0) are implemented and gated by `RCX_EXECUTION_V0=1`. See `docs/execution/StallFixObservability.v0.md`.

> **Implementation Status:** See STATUS.md and TASKS.md for current state.

---

## 4. Success Criteria for v1

The meta-circular subset v1 is considered complete when:

### 4.1 Minimal Meta Loop

A program expressed as RCX structure can:
1. Read a trace JSONL
2. Canonicalize each event
3. Emit canonical JSONL
4. Pass the replay gate (diff-empty vs Python reference)

### 4.2 Determinism Proof

| Requirement | Verification |
|-------------|--------------|
| Same input → same output | CI gate |
| No host-language semantics in output | Code audit |
| Bit-for-bit match with Python reference | diff-empty |

### 4.3 Golden Fixture Coverage

All fixtures in `tests/fixtures/traces/*.v1.jsonl` must:
- Pass through the meta loop
- Produce output identical to Python `trace_canon.py`
- Be verified by CI on every commit

---

## 5. Readiness Checklist

Before attempting meta-circular execution:

- [x] Gate 1: Deterministic Trace Contract
- [x] Gate 2: Replay Determinism
- [x] Gate 3: Entropy Sealing
- [x] Gate 4: Bytecode Mapping (v0) — ARCHIVED (superseded by kernel + seeds)
- [x] v2 Observability (stall/fix observable, debug-only)
- [x] Gate 5: Reference Interpreter — SUPERSEDED by kernel + EVAL_SEED (Phase 5 complete)

**Current Status**: Self-hosting achieved via kernel + seeds (Phase 5). Bytecode approach archived.

---

## 6. Unblock Conditions

To unblock Gate 5 and proceed to meta-circular implementation:

### Completed (v2 Observability)

1. ✅ **Add stall trace event type** — `reduction.stall` in v2 schema
2. ✅ **Add fix trace event type** — `reduction.applied` in v2 schema
3. ✅ **v2 fixtures and gate** — `tests/fixtures/traces_v2/`, `tests/test_replay_gate_v2.py`

### Completed (Execution Semantics v0)

4. ✅ **Implement Stall → Fix → Closure execution loop** — `RCX_EXECUTION_V0=1`
5. ✅ **Execution engine with stall/fix events** — `docs/execution/StallFixExecution.v0.md`
6. ✅ **Golden fixtures for execution semantics** — `tests/fixtures/traces_v2/recurrence_spec_v0/`
7. ✅ **Determinism gate for execution output** — replay gate passes

> **Note:** See TASKS.md Ra section for completion status.

---

## 7. Anti-Patterns (Forbidden)

The following are explicitly forbidden in meta-circular v1:

| Anti-Pattern | Reason |
|--------------|--------|
| Host-language eval() | Smuggles Python/Rust semantics |
| Reflection on host objects | Non-deterministic, host-dependent |
| Dynamic code generation | Untraced, non-reproducible |
| Ambient state | Violates entropy sealing |
| Implicit ordering | Must be explicit and sorted |
| Floating point | Forbidden by EntropyBudget.md |

---

## 8. Milestone Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| M0. Host baseline | PASS | — |
| M1. Determinism contracts | PASS | Gates 1-3 |
| M2. VM spec on paper | ARCHIVED | Bytecode superseded by kernel + seeds |
| M2.5. Observability (v2) | PASS | v2 trace events (debug-only) |
| M3. Reference interpreter | SUPERSEDED | Replaced by kernel + EVAL_SEED (Phase 5) |
| M4. Organism extraction | SUPERSEDED | Replaced by Phase 4 (match/subst as Mu) |
| M5. Seeded self-host loop | PASS | Phase 5: step_mu uses match_mu + subst_mu |
| M6. Algorithmic self-hosting | PASS | match/subst as Mu projections (Phase 6d) |
| M7. Operational self-hosting | DESIGN | Phase 7: kernel loop as projections |
| M8. Full meta-circular | FUTURE | RCX runs RCX with no Python |

### Self-Hosting Levels (Clarification)

**Important:** "Self-hosting" has multiple levels. Achieving one level does not mean all levels are complete.

| Level | Description | Status | Evidence |
|-------|-------------|--------|----------|
| **L1: Algorithmic** | Core algorithms (match, subst) expressed as Mu projections | ACHIEVED | mu/substrate/match.v2.json, mu/substrate/subst.v2.json |
| **L2: Operational** | Kernel state machine expressed as Mu projections | ACHIEVED | mu/substrate/kernel.v1.json (for-loop accepted as bootstrap primitive) |
| **L3: Substrate Portability** | Projections run on minimal, auditable substrate | ACHIEVED | JS parity (mu/host/js/eval_step.js) |

> **Note:** See STATUS.md for authoritative L-level definitions and current state.

**Meta-circular requirement:** Both self-hosting AND meta-circularity are needed. The evaluator must run itself - projections select projections. If Python provides iteration, emergence might be a Python artifact.

---

## 9. Kernel + Seeds Architecture (Current)

**Bytecode is archived.** The kernel + seeds architecture has replaced bytecode as the path to self-hosting.

**Architecture:**
- Pattern matching is **seed responsibility**, not kernel
- Seeds are pure Mu (no Python functions)
- Self-hosting = EVAL_SEED runs EVAL_SEED
- Bootstrap primitives: see `docs/core/BootstrapPrimitives.v0.md` for canonical list

**Seed Locations (mu/ directory):**
- `mu/substrate/kernel.v1.json` - Structural kernel (~7 Mu projections) - **canonical kernel**
- `mu/substrate/match.v2.json`, `mu/substrate/subst.v2.json` - Match/substitute with context passthrough
- `mu/closures/recurrence.v1.json`, `mu/closures/exhaustion.v1.json` - Closure detection
- `mu/utilities/classify.v1.json`, `mu/utilities/eval.v1.json` - Type classification, evaluation

**Python Host:**
- `rcx_pi/selfhost/step_mu.py` - step_kernel_mu uses kernel.v1 + match.v2 + subst.v2
- `rcx_pi/selfhost/eval_seed.py` - EVAL_SEED evaluator (apply_projection, step)
- Comprehensive test coverage including fuzzer (see STATUS.md for counts)

> **Note:** See STATUS.md for current test count and implementation state.

**Superseded:**
- Gates 4 and 5 (bytecode) are superseded by kernel + seeds
- Bytecode docs moved to `docs/archive/bytecode/`
- `rcx_pi/bytecode_vm.py` is legacy code

See `docs/core/RCXKernel.v0.md`, `docs/core/SelfHosting.v0.md`, and `docs/core/StructuralPurity.v0.md`.

---

## Version

Document version: v1.3 (clarified self-hosting levels, added Phase 7 context)
Last updated: 2026-01-27
Dependencies:
- `docs/schemas/rcx-trace-event.v1.json` (replay, frozen)
- `docs/schemas/rcx-trace-event.v2.json` (observability)
- `docs/archive/bytecode/BytecodeMapping.v0.md` (archived)
- `docs/execution/StallFixObservability.v0.md`
- `docs/core/RCXKernel.v0.md` (kernel architecture)
- `docs/core/SelfHosting.v0.md` (self-hosting design)
- `docs/core/MetaCircularKernel.v0.md` (Phase 7 design, VECTOR)
- `docs/core/StructuralPurity.v0.md` (guardrails)
- `EntropyBudget.md`
