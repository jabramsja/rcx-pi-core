# RCX Entropy Budget (Contract)

This document defines the entropy sealing policy for RCX deterministic execution.
All entropy sources must be classified as: **SEALED**, **FORBIDDEN**, or **EXPLICITLY ALLOWED**.

---

## Scope

This contract applies to:
- Trace generation
- Replay gates
- Golden fixture validation
- CI determinism checks

Sandbox/experimental paths (e.g. `worlds_mutate_*.py`) are explicitly out of scope for determinism guarantees, provided they are never exercised by determinism gates.

CI fixes must patch existing tests or fixtures where possible. Creating parallel tests to bypass failures is forbidden.

---

## Entropy Source Classification

| Source | Status | Notes |
|--------|--------|-------|
| **RNG (random module)** | FORBIDDEN | No ambient randomness in deterministic paths. Sandbox-only use must be labeled and excluded from gates. |
| **Unseeded RNG** | FORBIDDEN | Any future deterministic RNG use must be seeded from declared inputs and recorded in trace metadata. |
| **Wall-clock time** | FORBIDDEN (semantic) | Timestamps may exist for human inspection but must be stripped/normalized before replay comparison. |
| **PYTHONHASHSEED** | SEALED | CI must enforce `PYTHONHASHSEED=0`. |
| **Dict iteration order** | SEALED | Use explicit `sorted(d.keys())` or equivalent when iteration order affects output. |
| **Set iteration order** | SEALED | Never iterate over sets in deterministic paths; use `sorted(s)` if iteration is required. |
| **Filesystem order** | SEALED | Use `sorted()` on all directory listings (`os.listdir`, `glob`, `Path.iterdir`). |
| **Floating point** | FORBIDDEN | No floats in trace-sensitive computation. If unavoidable, document precision/rounding rules. |
| **Locale / encoding** | SEALED | All text I/O must use explicit `encoding='utf-8'`. No locale-dependent operations in deterministic paths. |
| **Rust HashMap iteration** | SEALED | Rust code must not rely on HashMap iteration order for deterministic output; use BTreeMap or explicit sorting. |
| **Object id / hash** | FORBIDDEN | Never use `id()` or `hash()` of objects in deterministic output. |
| **Thread / async ordering** | FORBIDDEN | No concurrency in deterministic paths. |

---

## Canonicalization Requirements

Before comparison, replay, or fixture validation, outputs must be canonicalized:

1. **JSON keys**: Lexicographically sorted at all nesting levels.
2. **Timestamps**: Stripped or normalized to a constant value.
3. **Metadata fields**: Non-semantic metadata (e.g. `generated_at`, `tool`) is informational only and must not affect replay comparison.

The canonical trace format is defined in `docs/schemas/rcx-trace-event.v1.json`.

---

## CI Enforcement

CI runs must:
1. Set `PYTHONHASHSEED=0` in environment.
2. Run replay gates that verify `trace → replay → diff empty`.
3. Fail on any tracked diff after deterministic operations.

---

## Violations

If an entropy source cannot be sealed, normalized, or made replayable, it is **not permitted** in deterministic RCX execution paths.

Any exception must be:
1. Explicitly documented in this file.
2. Scoped outside the trace/replay contract.
3. Approved before implementation.

---

## Current Known Exceptions

| File | Source | Justification |
|------|--------|---------------|
| `rcx_pi/worlds/worlds_mutate_*.py` | `random` | Sandbox/experimental evolution. Never exercised by determinism gates. |
| `rcx_pi/worlds/world_trace_cli.py` | `datetime.now()` | `meta.generated_at` is informational only; stripped during replay comparison. |

---

## Version

Contract version: v1
Last updated: 2026-01-24
