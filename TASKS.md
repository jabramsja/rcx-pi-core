# RCX Task List (Canonical)

This file is the single source of truth for authorized work.
If a task is not listed here, it is NOT to be implemented.

---

## North Star (Keep This True)

1. RCX VM is not a "runner". It is a substrate where **structure is the primitive**.
2. "Code = data" means execution is graph/mu transformation, not host-language semantics.
3. **Stall → Fix → Trace → Closure** is the native engine loop; everything else must serve it.
4. Closures/gates must be **explicit, deterministic, and measurable** (fixtures + replay).
5. Emergence must be attributable to RCX dynamics, not "Python did it".
6. Host languages are scaffolding only; their assumptions must not leak into semantics.
7. Buckets (r_null / r_inf / r_a / lobes / sink) are **native routing states**, not metaphors.
8. Seeds must be minimal (void/empty) and growth must be structurally justified.
9. Determinism is a hard invariant: same seed + rules ⇒ same trace/fixtures.
10. A "program" is a pressure vessel: seed + allowable gates + thresholds + observation outputs.
11. Enginenews-like specs are target workloads to prove: "does ω/closure actually emerge?"
12. Every task must answer: "Does this reduce host smuggling and increase native emergence?"

---

## Governance (Non-Negotiable)

- Do not add new subsystems, execution models, or architectures without explicit approval.
- Do not create "new tests" to bypass a failing test; fix the failing test or the code.
- Do not leave broken files/tests behind and add replacements.
- Minimize file creation. Prefer editing existing files.
- v1 replay semantics are frozen. Any new observability must be v2 and gated.

---

## Ra (Resolved / Merged)

- Deterministic trace core (v1) complete
- Replay semantics frozen (v1)
- Entropy sealing contract in place
- Golden fixtures in place
- Replay gate + CI enforcement in place
- Rust replay acceleration bit-for-bit compatible

---

## Lobe: Stall/Fix Observability (v2, non-breaking)

### NOW (blocking)

1. **Write Stall/Fix Observability design doc** ✅
   - Deliverable: `docs/StallFixObservability.v0.md`
   - Done: doc in PR #80

2. **Implement v2 trace schema (alongside v1)** ✅
   - Deliverables:
     - `docs/schemas/rcx-trace-event.v2.json`
     - v2 canonicalizer updates in `trace_canon.py`
   - Done: schema created, canonicalizer accepts v=1 or v=2

3. **Emit v2 events (flagged) for:** ✅
   - reduction.stall (pattern match failed)
   - reduction.applied (rule transformed value)
   - reduction.normal (no rule matched)
   - Deliverables:
     - Feature flag: `RCX_TRACE_V2=1` (off by default)
     - Instrumentation in `pattern_matching.py` and `rules_pure.py`
   - Done:
     - With flag OFF: v1 fixtures unchanged (bit-for-bit)
     - With flag ON: v2 events appear as expected

4. **Add minimal v2 fixtures + gate (separate from v1)** ✅
   - Deliverables:
     - `tests/fixtures/traces_v2/observer.v2.jsonl`
     - `tests/test_replay_gate_v2.py`
   - Done: v2 gate passes, v1 gate untouched

5. **Bytecode mapping v0 alignment pass** ✅
   - Input: `BytecodeMapping.v0.md`
   - Deliverable: update mapping to include new v2 observability events (as "debug-only")
   - Done: PR #81 merged, doc now references v2 debug-only opcodes

6. **Stall/Fix Execution Semantics (v0)** ✅
   - Design doc: `docs/StallFixExecution.v0.md`
   - Feature flag: `RCX_EXECUTION_V0=1` (off by default)
   - Decisions: Q1=A (Rule ID only), Q2=A (serialize stalls), Q3=A (whole value stalls)
   - Phases:
     - **Phase 1: Schema + Validation** ✅ (PR #85)
       - v2 schema extended with execution.stall, execution.fix, execution.fixed
       - ExecutionEngine class in trace_canon.py
       - value_hash() for deterministic references
     - **Phase 2: Golden Fixture + Tests** ✅ (PR #85)
       - `tests/fixtures/traces_v2/stall_fix.v2.jsonl`
       - Execution engine tests in test_replay_gate_v2.py
     - **Phase 3: Integration** ✅ (PR #86)
       - ExecutionEngine wired into PatternMatcher
       - Pattern match failure → STALL (when execution_engine provided)
       - _motif_to_json() for deterministic value serialization
   - Done: All tests pass, all CI green

---

## Meta-circular Readiness (Docs only)

7. **MetaCircularReadiness.v1.md review pass** ✅
   - Deliverable: ensure it references the current frozen invariants and v2 observability plan
   - Done: PR #83 merged, doc updated to v1.1 with v2 observability references

---

## Boundary Question (Unanswered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

This question defines the boundary between substrate completion and
Sink-level capability growth. Anything beyond answering this question
requires explicit promotion.

**Operational restatement:**

What is the minimal native execution loop that can:
(a) detect a true stall,
(b) apply a structurally justified fix,
(c) record that as a trace event, and
(d) make closure unavoidable on second independent encounter,
without importing semantics from the host language?

---

## Lobe: Minimal Native Execution Primitive

### NOW (blocking)

8. **Minimal Native Execution Primitive (v0)** ✅
   - Deliverable: `docs/MinimalNativeExecutionPrimitive.v0.md`
   - Purpose: Answer the Boundary Question above
   - Done:
     - Doc defines Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM)
     - 5 invariants explicit and testable
     - 7 non-goals enumerated (no scope creep)
     - Uses existing primitives only (Motif, PatternMatcher, ExecutionEngine, value_hash)

9. **Doc coherence pass (NOW-A)** ✅
   - Purpose: Align terminology across docs
   - Done:
     - Both docs use: `reduction.*` = observability, `execution.*` = state transitions
     - No CLOSE opcode language (both say "normal form detected, not commanded")
     - v0 marked as replay-only, single-value, STALL/FIX only

10. **Gate wiring verification (NOW-B)** ✅
    - Purpose: Confirm existing gates are correctly wired (no new capability)
    - Done:
      - v1 gates green (test_replay_gate_idempotent.py)
      - v2 gates green (test_replay_gate_v2.py: 17 tests)
      - Fixtures: `traces/` (4 v1), `traces_v2/` (3 v2)
      - Clean repo after pytest (no tracked diffs)

11. **Replay validation for v2 execution events (NOW-C)** ✅
    - Purpose: Prove Stall→Fix→Trace loop is deterministic and replayable (trace-consumption only)
    - Done:
      - `_validate_v2_execution_sequence()` in replay_cli.py
      - Validates: fix-without-stall, fixed-without-stall, hash mismatch, double stall
      - Accepts: stall at trace end (normal form), valid stall→fixed cycle
      - v1 unchanged, v2 fixtures pass validation

---

## Sink Promotion Candidate

12. **Record Mode v0: execution → trace for stall/fix events** ✅
    - Purpose: Emit execution.* events during actual reduction (inverse of replay)
    - Flag: `RCX_EXECUTION_V0=1` (reuse existing flag, default OFF)
    - Scope:
      - Single-value path only, no concurrency
      - Emit `execution.stall` when PatternMatcher mismatch causes true stall
      - Emit `execution.fixed` ONLY if prior `execution.stall` exists for same value_hash in same run
        (do NOT emit fixed on normal reductions without preceding stall)
      - Collect events into trace output
    - Deliverables:
      - Edit `rcx_pi/reduction/pattern_matching.py`: call `engine.fixed()` after successful reduction IF engine is stalled
      - Edit `rcx_pi/trace_canon.py` ExecutionEngine: track stall state to gate fixed emission
      - Add ONE golden fixture: `tests/fixtures/traces_v2/record_mode.v2.jsonl` (generated from tiny deterministic input)
      - Edit `tests/test_replay_gate_v2.py`: add record → replay → validate gate
    - Done:
      - Gate: (engine present) ∧ (engine STALLED) ∧ (hash match) ∧ (RCX_EXECUTION_V0=1)
      - 4 tests: stall→fix cycle, no-fixed-without-stall, fixture match, replay validation
      - Re-record determinism verified (PYTHONHASHSEED=0)

---

## Sink (Unknown / Deferred)

- Full RCX bytecode VM bootstrap
- Meta-circular execution without host language
- Performance-first optimizations before semantic lock
