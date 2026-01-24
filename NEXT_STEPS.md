# RCX-π Next Steps Plan (Layered Growth)
Generated: 2026-01-23

This plan follows the repo rule: **RCX-π kernel is DONE / FROZEN; all growth is by layering**.

This document reflects **actual completed work**, not aspirational state.

---

## Current status (verified, green)


### Schema-triplet canon (current)

- The canonical runner is `rcx_pi/cli_schema_run.py` (execute `--schema` commands + strict-parse the schema-triplet output).
- Use it anywhere a script or test needs to validate schema output, rather than duplicating parsing logic.

- `dev` is PR-only with required checks
- CI policy is canonical and enforced
- `green_gate` is authoritative
- Kernel code is immutable by convention and practice
- Determinism is enforced by tests and fixtures, not trust

---

## Completed layers (LOCKED)

### ✅ 1) Serialization + full state snapshot (FOUNDATION) — DONE

Status: **COMPLETE and test-locked**

What exists now:
- Stable JSON snapshot format
- Deterministic save / load parity
- Round-trip snapshot tests proving identical behavior
- Snapshot integrity guarded by hash + tests

This layer is considered **structurally complete**.
Future changes require a new versioned layer.

---

### ✅ 2) Orbit / ω-limit visual explorer (SENSEMAKING) — DONE (v1)

Status: **COMPLETE (v1), layered**

What exists now:
- Deterministic orbit trace export (JSON)
- DOT / SVG artifact generation
- Provenance fixtures with semantic validation
- Idempotent artifact generation (tracked-file clean)
- Explorer tooling without kernel contamination

This layer is **observational only** and does not affect execution semantics.

---

## Active frontier (NEXT)

### ▶ 3) Lobe merge strategies (CONTROLLED INTEGRATION)

Status: **NEXT ACTIVE WORK**

Goal:
Define how lobes can be combined **without modifying the kernel**.

Planned deliverables:
- One explicit, documented merge policy
- Deterministic merge tool operating on snapshots
- Tests proving merge does not alter unrelated behavior

Constraints:
- No kernel mutation
- Merge logic must live entirely in a layer/tool
- Output must itself be snapshot-able and replayable

This is the **next structurally meaningful step**.

---

## Deferred (blocked by design)

### ⏸ 4) Rule mutation sandbox

Status: **INTENTIONALLY DEFERRED**

Reason:
Mutation is meaningless without:
- Stable snapshot semantics ✔
- Observable orbit dynamics ✔
- Defined lobe merge behavior ❌ (this is the blocker)

This remains out of scope until lobe merging is complete and trusted.

---

## Explicitly out of scope for RCX-π

### 🚫 5) RCX-Ω / meta-circular work

Tracked separately.
Must live in a different repo / governance zone.
No Ω work is permitted to leak into π-core.

---

## Working agreement (still binding)

- Kernel stays immutable
- New behavior = new layer or tool
- Tests define truth
- Green gate is law
- If behavior is not test-locked, it is not real

---

## Summary (one-line)

**RCX-π is now in the “controlled integration” phase.  
Lobe merge semantics are the only legitimate next move.**
