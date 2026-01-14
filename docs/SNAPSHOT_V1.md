# Snapshot v1 (RCX-π) — Canonical State Serialization

This document defines the **stable, deterministic** snapshot format for RCX-π runtime state.

## Goals
- Deterministic round-trip: save → reset → load must preserve behavior.
- Versioned: future formats must not break old snapshots silently.
- Portable: format must be stable across machines/OS/arch.

## Snapshot v1 fields (minimum)
- `version`: integer (must be `1`)
- `world`: string (world/program name, if applicable)
- `rules`: ordered list (preserve precedence)
- `r_a`: list of Mu terms
- `lobes`: list of Mu terms
- `sink`: list of Mu terms
- `meta`: object (optional; reserved for future)

## Determinism requirements
- Ordering is part of the meaning (especially rules/precedence).
- No host-only pointers or non-serializable closures.
- Loading a snapshot must not re-order or re-normalize terms.

## Round-trip contract
A snapshot is **valid** only if this holds:

1. Start from a known world + seed set.
2. Run a small, fixed probe suite (classify/orbit/omega samples).
3. Save snapshot.
4. Reset runtime.
5. Load snapshot.
6. Re-run the same probe suite.
7. Outputs must match byte-for-byte (or structurally, if JSON normalized).

See: `tests/test_snapshot_roundtrip_v1.py`.
