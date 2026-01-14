# Snapshot v1 (RCX-π) — Canonical State Serialization

This repo’s canonical snapshot artifacts live in `snapshots/` and use a stable, deterministic `.state` text format,
with a sha256 lockfile (`snapshots/SHA256SUMS`) to detect drift.

This document describes the current v1 snapshot format used by the Rust demo(s).

## Goals
- Deterministic round-trip: save → wipe/reset → load preserves behavior.
- Portable: snapshot files are stable across machines/OS/arch.
- Verifiable: `SHA256SUMS` locks known-good snapshots.

## File format (v1)

A snapshot file is UTF-8 text with these top-level sections:

### 1) PROGRAM section
Starts with:

    PROGRAM:

Followed by 0+ rule lines, each of the form:

    RULE <mu-term>

Ordering matters. Rules are applied in file order.

### 2) STATE section
Starts with:

    STATE:

Followed by 0+ state lines, each of the form:

    RA   <mu-term>
    LOBE <mu-term>
    SINK <mu-term>

Ordering matters for deterministic replay and comparisons.

## Verification
- `snapshots/SHA256SUMS` pins the expected sha256 for each canonical snapshot.
- CI fails if a pinned snapshot changes unexpectedly.
- The round-trip demo should show: wrote snapshot → wipe → restore → same behavior.

