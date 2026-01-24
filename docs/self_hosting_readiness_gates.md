# Self-hosting Readiness Gates (v1)

These gates define when it is rational to attempt self-hosting/meta-circular work.
They are intended to be **measurable** and **testable**.

## Gate A: Deterministic Trace Contract (Trace Core)
**Must be true**
- A canonical trace schema exists (v1) and is enforced by tests.
- Trace canonicalization helper exists (single source of truth).

**Evidence**
- `docs/schemas/rcx-trace-event.v1.json` exists.
- Unit tests validate canonicalization rules.

## Gate B: Replay Gate (Trace → Replay → No Diff)
**Must be true**
- A replay CLI exists and fails non-zero on mismatch.
- CI runs trace → replay → verifies no tracked diffs.

**Evidence**
- A dedicated test/CI gate exists and fails on intentional drift.

## Gate C: Deterministic IO + Snapshot Contract
**Must be true**
- Canonical JSON writing policy is implemented + tested.
- Deterministic FS enumeration is implemented + tested.
- Snapshot merge outputs are byte-identical across repeated runs.

**Evidence**
- Unit tests for JSON canon + FS canon.
- Snapshot determinism gate is green.

## Gate D: VM Spec Freeze (ISA + Loader)
**Must be true**
- Minimal ISA is written and versioned.
- Loader/container format is written and versioned.
- A reference interpreter test plan exists.

**Evidence**
- `docs/vm/isa_v1.md` (or equivalent) exists.
- Opcode semantics are covered by fixtures/tests (even if interpreter is hosted).

## Gate E: Minimal Seed Loop (Deterministic Rehydration)
**Must be true**
- A minimal RCX program can rebuild a tiny artifact deterministically.
- The loop is stable across environments we care about (CI + local).

**Evidence**
- Golden fixtures + CI gate verifies byte-identical output.

## Gate F: Meta-circular Scope Definition (Subset v1)
**Must be true**
- The exact scope of “meta-circular subset v1” is written.
- The meta loop has deterministic success criteria.

**Evidence**
- A spec doc exists + tests enforce it.
