# RCX-π Core — Minimal Structural Runtime v1


### Development Rules (Enforced)

- All changes go through PRs
- CI green is mandatory (`green-gate` + `test`)
- Development proceeds by **layering**, not arbitrary mutation
- Structural purity enforced: program IN RCX, not ABOUT RCX

If CI is not green, the change does not exist.

### Current Direction

Building a minimal self-hosting kernel. See:
- `docs/core/RCXKernel.v0.md` - Kernel architecture (4 primitives, seeds define semantics)
- `docs/core/StructuralPurity.v0.md` - Guardrails for Mu purity
- `TASKS.md` - Canonical task tracker


## CI (Green Gate)


### CLI schema-triplet contract

All `--schema` emitters are validated via the canonical runner at `rcx_pi/cli_schema_run.py` (single source of truth for executing schema commands and strict-parsing the schema-triplet output).

Before you open a PR, run the local gate:

    make green

Policy + definition of GREEN: see `CI_POLICY.md`.



This is the **minimal working implementation of RCX-π**, built entirely from a
single recursive motif structure `μ(...)`.  
Everything—numbers, pairs, triples, programs, projections, activation closures—
is represented as pure nested structure instead of syntax or bytecode.

RCX-π = *Computation without instructions.*  
Only shape. Only structure. The program **is** the data.

---

## World tracing (stable entrypoint)

Use the stable wrapper script (no PYTHONPATH required):

  ./scripts/world_trace.sh --help
  ./scripts/world_trace.sh --max-steps 50 --json --pretty < world.json

This delegates to: python3 -m rcx_pi.worlds.world_trace_cli


## Core Components

### Core Modules (see STATUS.md for current phase)

| Module | Purpose |
|-------|---------|
| `rcx_pi/kernel.py` | Minimal kernel (4 primitives: identity, stall, trace, dispatch) |
| `rcx_pi/eval_seed.py` | EVAL_SEED evaluator (match, substitute, apply_projection, step) |
| `rcx_pi/mu_type.py` | Mu type validation and guardrails |

### Legacy / Archived (not the current approach)

| Module | Purpose | Status |
|-------|---------|--------|
| `core/motif.py` | Motif object and `μ(...)` constructor | Legacy |
| `engine/evaluator_pure.py` | Closure-based evaluator | Legacy |
| `rcx_pi/bytecode_vm.py` | Bytecode VM | **ARCHIVED** - superseded by kernel + seeds |
| `docs/archive/bytecode/` | Bytecode documentation | **ARCHIVED** |

Run `pytest` to verify health. See `TASKS.md` for current phase status.

---

## ✅ Current Stable Capabilities (Layered)

The following capabilities are **stable, deterministic, and enforced by gate**.
All are implemented **outside the frozen kernel** as tools, fixtures, or validation layers.

- **Deterministic orbit artifact generation**
  - `scripts/build_orbit_artifacts.sh` is idempotent for tracked files
  - Re-running does not dirty the working tree

- **Orbit provenance semantics**
  - Provenance entries are validated against emitted state transitions
  - Supports legacy (`from`/`to`) and current (`pattern`/`template`) schemas
  - State entries may be strings or structured objects (`{"i":…, "mu":…}`)

- **Graphviz SVG normalization**
  - Version-specific metadata is stripped
  - SVG fixtures are stable across Graphviz versions

- **Snapshot + replay integrity**
  - Orbit, replay, and snapshot fixtures are schema-locked
  - Rust and Python paths agree on emitted structure

### Maintainer workflow helper (optional)

For repositories where auto-merge is disabled, a helper script is available:

    scripts/merge_pr_clean.sh <PR_NUMBER>

This performs a clean base sync, head rebase, gate verification, manual merge,
and post-merge sync. Repository policy remains unchanged.

## 🔒 Green Gate (Canonical Health Check)

The **only supported correctness gate** for this repository is:

```bash
scripts/green_gate.sh

If scripts/green_gate.sh finishes without red errors — RCX-π Core is healthy.

## JSON diff / inspection

Use `scripts/json_diff.sh` to compare JSON outputs semantically (object key order ignored; arrays remain order-sensitive).

Examples:
- Compare full docs (ignoring optional schema metadata):
  - `scripts/json_diff.sh a.json b.json --ignore kind,schema_version`
- Compare only the frozen minimum field:
  - `scripts/json_diff.sh a.json b.json --only result`

## Rule precedence visualization

Use `scripts/rule_precedence.sh` to inspect a `.mu` world file and list rule-like lines in **textual order** (earlier lines first).
This is a tooling inspector only; it does not change runtime semantics.

Examples:
- Show the first 25 rules detected:
  - `scripts/rule_precedence.sh rcx_pi_rust/mu_programs/rcx_core.mu --top 25`
- Emit a stable JSON summary:
  - `scripts/rule_precedence.sh rcx_pi_rust/mu_programs/rcx_core.mu --json`

## CLI Quickstart
See `docs/cli/cli_quickstart.md` for the umbrella `rcx` command and the JSON-emitting tools.

<!-- protection smoke: 2026-01-13T23:02:14Z -->


# protection proof: 2026-01-13T23:29:28Z
