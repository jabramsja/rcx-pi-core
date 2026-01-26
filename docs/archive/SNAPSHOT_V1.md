# Snapshot v1 (RCX-π) — Canonical State Serialization

Canonical snapshot artifacts live in:

- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/rcx_pi_rust/snapshots/`

They use a stable, deterministic **`.state`** text format, with a sha256 lockfile:

- `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/rcx_pi_rust/snapshots/SHA256SUMS`

## Verification contracts
- `SHA256SUMS` pins expected sha256 for canonical snapshots.
- CI fails if a pinned snapshot changes unexpectedly.
- The Rust demo should show: wrote snapshot → wipe → restore → same behavior.
