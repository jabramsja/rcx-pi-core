# RCX Task List (Canonical)

---

## Ra (Resolved / Merged)

- Canonical schema-triplet runner (`rcx_pi/cli_schema_run.py`)
- CLI schema emitters unified and idempotent
- Orbit artifact idempotence gate stabilized
- Schema-flag tests refactored to canonical runner
- cli_smoke schema checks fully canonical

---

## Lobe: Deterministic Trace Core (v1)

### NOW (blocking)

1. **Define canonical trace event contract (v1)**
   - Deliverable: `docs/schemas/rcx-trace-event.v1.json`
   - Rules: stable field set, stable ordering, no implicit timestamps
   - Done when: schema exists and is validated by tests

2. **Trace canonicalization helper (single source of truth)**
   - Deliverable: `rcx_pi/trace_canon.py`
   - Behavior: normalize event ordering and optional fields deterministically
   - Done when: unit tests prove canonical output across permutations

3. **Replay CLI skeleton (python-only)**
   - Deliverable: `python -m rcx_pi.rcx_cli replay ...`
   - Behavior: trace → replay → artifact emit
   - Done when: non-zero exit on replay mismatch

### NEXT

4. **Replay gate: trace → replay → diff empty**
   - Deliverable: CI gate enforcing deterministic replay
   - Done when: CI fails on any tracked diff

5. **Entropy sealing checklist + tests**
   - Deliverable: `docs/EntropyBudget.md`
   - Covers: RNG seeds, hash ordering, filesystem order, locale/time, floats
   - Done when: each entropy source is sealed or explicitly allowed

6. **Golden trace fixtures**
   - Deliverable: `tests/fixtures/traces/*.jsonl`
   - Done when: fixtures replay cleanly and are used by replay gate

### VECTOR (intentionally deferred)

7. **Rust replay acceleration layer**
   - Blocked on: python replay semantics frozen

8. **Bytecode / VM mapping draft**
   - Deliverable: mapping of trace events → bytecode ops

9. **Meta-circular readiness definition**
   - Deliverable: explicit self-hosting criteria (v1)

---

## Sink (Unknown / Deferred)

- Full RCX bytecode VM bootstrap
- Meta-circular execution without host language
- Performance-first optimizations before semantic lock
