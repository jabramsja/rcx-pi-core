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
- Entropy sealing contract (`EntropyBudget.md`) - RNG, timestamps, hash ordering, floats sealed
- Golden trace fixtures (`tests/fixtures/traces/*.v1.jsonl`) - minimal, multi-event, nested payload
- Replay gate runs all fixtures; CI enforces determinism
- Comprehensive freeze fixture (`replay_freeze.v1.jsonl`) - contiguity, nested mu, metadata
- Rust replay acceleration (`rcx_pi_rust/examples/replay_cli.rs`) - bit-for-bit compatible with Python

---

## Replay Semantics Frozen (v1)

**Status: FROZEN as of 2026-01-24**

The Python replay semantics are now locked. This freeze means:

1. **Replay definition locked**: canonical trace JSONL → deterministic replay → zero tracked diff (CI enforced)
2. **Trace event schema v1 locked**: `docs/schemas/rcx-trace-event.v1.json`
3. **Entropy contract locked**: `EntropyBudget.md`
4. **Golden fixtures validate behavior**: `tests/fixtures/traces/*.v1.jsonl`

**Constraints on future work:**
- Rust replay acceleration is permitted as a **performance layer only**
- No new execution models
- No semantic divergence from Python replay
- Rust must be **bit-for-bit compatible** with frozen replay semantics

---

## Lobe: Deterministic Trace Core (v1)

**Status: Complete. Replay semantics frozen. Rust acceleration shipped.**

### VECTOR (intentionally deferred)

5. **Bytecode / VM mapping draft**
   - Deliverable: mapping of trace events → bytecode ops

6. **Meta-circular readiness definition**
   - Deliverable: explicit self-hosting criteria (v1)

---

## Sink (Unknown / Deferred)

- Full RCX bytecode VM bootstrap
- Meta-circular execution without host language
- Performance-first optimizations before semantic lock
