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
- v2 trace schema + observability events (RCX_TRACE_V2=1)
- Stall/Fix execution semantics v0 (RCX_EXECUTION_V0=1)
- ExecutionEngine + value_hash() + _motif_to_json()
- Record Mode v0 (execution → trace for stall/fix events)
- Minimal Native Execution Primitive doc (Boundary Question answered)
- v2 replay validation (_validate_v2_execution_sequence)

---

## Boundary Question (Answered)

What is the smallest, host-independent execution primitive that RCX must possess
such that a structural program can cause new structure to emerge only via
Stall → Fix → Trace → Closure, and in no other way?

**Answer:** The Structural Reduction Loop (MATCH → REDUCE/STALL → TRACE → NORMAL_FORM).
See `docs/MinimalNativeExecutionPrimitive.v0.md` for invariants and non-goals.

---

## NOW (tight, measurable, no new architecture)

1. **Trace Reading Primer (for humans)** ✅
   - Deliverable: `docs/TraceReadingPrimer.v0.md`
   - Done:
     - v1 vs v2 event types documented
     - Verb table: START/STALL/FIXED/END
     - Hash fields explained (value_hash, before_hash, after_hash)
     - 2 annotated examples with validation walkthrough
     - 60-second method checklist

2. **Record→Replay Gate (single command, end-to-end)** ✅
   - Deliverable: `test_record_replay_gate_end_to_end` in test_replay_gate_v2.py
   - Run: `PYTHONHASHSEED=0 pytest tests/test_replay_gate_v2.py::test_record_replay_gate_end_to_end -v`
   - Done:
     - Runs record mode on tiny input
     - Writes temp trace
     - Runs replay --check-canon + v2 validation
     - Re-runs record mode, asserts bit-for-bit identical

3. **Flag Discipline Contract** ✅
   - Deliverable: `docs/Flags.md`
   - Done:
     - RCX_TRACE_V2=1: observability only
     - RCX_EXECUTION_V0=1: execution/record only
     - PYTHONHASHSEED=0: determinism
     - Default OFF invariant documented
     - Flag combinations table

---

## NEXT (still small, but capability growth)

4. **Consume execution.fix from trace (true cycle replay)**
   - Purpose: close the loop so a trace can drive a full stall→fix progression
   - Deliverable:
     - extend replay to optionally apply execution.fix events to the engine
     - new golden fixture: "stall + fix + fixed + end" where fix is consumed, not just validated
   - Done when:
     - replay can execute a fix when present
     - still rejects invalid ordering/hashes
     - v1 unchanged

5. **Minimal "Closure-as-termination" fixture family**
   - Purpose: make "normal form termination" a first-class, tested concept
   - Deliverable: 2 fixtures:
     - stall_at_end.v2.jsonl (normal form)
     - stall_then_fix_then_end.v2.jsonl (resolved)
   - Done when: tests distinguish the two cleanly and deterministically.

---

## VECTOR (design-first, defer implementation unless you promote)

6. **"Second independent encounter" semantics**
   - Deliverable: `docs/IndependentEncounter.v0.md`
   - Defines:
     - what counts as "independent"
     - how it's tracked (hash lineage? ancestry bookkeeping? tokenization?)
     - what event signals closure becomes unavoidable
   - Done when: you can implement later without re-arguing definitions.

7. **Bytecode VM mapping v1 (upgrade from v0)**
   - Deliverable: `BytecodeMapping.v1.md`
   - Includes:
     - how MATCH/REDUCE/STALL/FIX map to ops
     - what state lives in registers vs trace
     - determinism constraints carried forward
   - Done when: it's implementable but still deferred.

---

## SINK (requires explicit promotion)

- Multi-value/concurrent execution
- ROUTE/CLOSE opcodes (if ever needed)
- Full VM bootstrap / meta-circular execution
- Performance-first optimizations
