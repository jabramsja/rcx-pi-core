# RCX-π Next Steps Plan (Layered Growth)
Generated: 2026-01-14T00:17:27Z

This plan follows the repo rule: **RCX-π kernel is DONE/FROZEN; all growth is by layering**.

## Current status (confirmed)
- Branch protection enforced on `dev` (PR-only; required checks: `green-gate`, `test`)
- CI policy is canonical: `CI_POLICY.md`
- Local gate shortcut: `make green`
- Nightly drift detection: scheduled `rcx-green-gate` on `dev`

## What’s next (in the correct order)

### 1) Serialization + full state snapshot (FOUNDATION)
Goal: deterministically save/load the *entire* runtime state so runs are reproducible and evolvable.

Deliverables:
- A stable on-disk format (start with JSON; add TOML later if desired)
- `save-state` / `load-state` parity (Rust + Python bridge where applicable)
- Tests that round-trip state with no behavioral drift

Definition of done:
- `make green` passes
- A snapshot round-trip test proves identical behavior before/after load

### 2) Orbit / ω-limit visual explorer (SENSEMAKING)
Goal: make rewrite dynamics legible without changing the kernel.

Deliverables (layer/tool only):
- Export orbit traces as JSON
- Optional: DOT export to visualize cycles / attractors
- A small “visual explorer” CLI (even text-first is fine)

Definition of done:
- Demonstrate pingpong cycle and at least one non-trivial orbit
- Exports are deterministic and covered by tests (or goldens)

### 3) Lobe merge strategies (CONTROLLED INTEGRATION)
Goal: define how lobes combine without contaminating the frozen kernel.

Deliverables:
- A documented merge policy (and possibly multiple strategies)
- A tool/CLI that merges two lobe snapshots into a third (layered)

### 4) Rule mutation sandbox (DEFERRED UNTIL 1–3 EXIST)
Goal: safely explore mutation without entering core.

Deliverables:
- Isolated sandbox directory / tool entrypoint
- Scoring harness + constraints
- Explicit quarantine rules

### 5) RCX-Ω / meta-circular work (OUT OF SCOPE FOR π-CORE)
Tracked, but should live as a separate governed layer/repo/zone.

## Working agreement
- Kernel stays immutable
- New behavior = new layer/tool
- Tests override docs; green gate is law

## Status (post-serialization)

- ✅ Snapshot/serialization: Ra-for-now (tests/fixtures lock behavior)
- ✅ engine_run: checker accepts schema as alias for schema_version
- ✅ engine_run: emitter now includes schema_version (keeps schema for now)
- ✅ Deterministic gates: ./scripts/check_orbit_all.sh (green)

