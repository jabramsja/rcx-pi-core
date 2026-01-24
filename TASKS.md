# RCX Task List (Canonical)

---

## North Star (Keep This True)

1. RCX VM is not a “runner”. It is a substrate where **structure is the primitive**.
2. “Code = data” means execution is graph/mu transformation, not host-language semantics.
3. **Stall → Fix → Trace → Closure** is the native engine loop; everything else must serve it.
4. Closures/gates must be **explicit, deterministic, and measurable** (fixtures + replay).
5. Emergence must be attributable to RCX dynamics, not “Python did it”.
6. Host languages are scaffolding only; their assumptions must not leak into semantics.
7. Buckets (r_null / r_inf / r_a / lobes / sink) are **native routing states**, not metaphors.
8. Seeds must be minimal (void/empty) and growth must be structurally justified.
9. Determinism is a hard invariant: same seed + rules ⇒ same trace/fixtures.
10. A “program” is a pressure vessel: seed + allowable gates + thresholds + observation outputs.
11. Enginenews-like specs are target workloads to prove: “does ω/closure actually emerge?”
12. Every task must answer: “Does this reduce host smuggling and increase native emergence?”

---

## Ra (Resolved / Merged)

- Canonical schema-triplet runner (`rcx_pi/cli_schema_run.py`)
- CLI schema emitters unified and idempotent
- Orbit artifact idempotence gate stabilized
- Schema-flag tests refactored to canonical runner
- cli_smoke schema checks fully canonical
- Canonical trace event contract (v1) (`docs/schemas/rcx-trace-event.v1.json`)
- Trace canonicalization helper (`rcx_pi/trace_canon.py`)
- Replay CLI skeleton (python-only) (`python -m rcx_pi.rcx_cli replay ...`)
- Replay idempotence gate: trace → replay → tracked diff empty (`tests/test_replay_gate_idempotent.py`)

---

## Lobe: Deterministic Trace Core (v1)

### NOW (blocking)

1. **Entropy sealing checklist + tests**
   - Deliverable: `docs/EntropyBudget.md`
   - Covers: RNG seeds, hash ordering, filesystem order, locale/time, floats
   - Done when: each entropy source is sealed or explicitly allowed

2. **Golden trace fixtures**
   - Deliverable: `tests/fixtures/traces/*.jsonl`
   - Done when: fixtures replay cleanly and are used by replay gate

### NEXT

3. **Replay gate: trace → replay → diff empty (CI enforcement)**
   - Deliverable: CI gate enforcing deterministic replay
   - Done when: CI fails on any tracked diff

### VECTOR (intentionally deferred)

4. **Rust replay acceleration layer**
   - Blocked on: python replay semantics frozen

5. **Bytecode / VM mapping draft**
   - Deliverable: mapping of trace events → bytecode ops

6. **Meta-circular readiness definition**
   - Deliverable: explicit self-hosting criteria (v1)

---

## Sink (Unknown / Deferred)

- Full RCX bytecode VM bootstrap
- Meta-circular execution without host language
- Performance-first optimizations before semantic lock
