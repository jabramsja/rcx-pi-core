# RCX-π Core — Minimal Structural Runtime

A projection-based computational substrate where **structure is the primitive**.

## Current Status: Phase 8c — Gates 1-5 COMPLETE

| Level | Description | Status |
|-------|-------------|--------|
| **L1** | match/subst algorithms as Mu projections | ✅ DONE |
| **L2** | Kernel state machine as Mu projections | ✅ FULL |
| **L3** | Substrate portability (Python + JS) | ✅ COMPLETE |
| **Gates 1-5** | Meta-circular parity (structural default) | ✅ COMPLETE |
| **Hemispheres v0** | Native structural routing (12 projections) | ✅ DONE |

- **3,235+ tests** across 90+ test files
- **12 semantic debt** (irreducible bootstrap floor)
- **43 CRITICAL_TEST_FILES** protected from silent skipping
- **47 core projections** across 5 L3-complete seeds + 12 hemisphere projections

**Hemispheres v0:** Routing decisions expressed as pure Mu projections (`mu/programs/hemispheres.v1.json`).
Three automatic routes: null→r_null, closure→r_a, default→lobes. Cross-substrate parity verified.

See `STATUS.md` for full details.

### Development Rules (Enforced)

- All changes go through PRs
- CI green is mandatory (`scripts/green_gate.sh`)
- Structural purity enforced: program IN RCX, not ABOUT RCX
- Security tools have grounding tests (tests actually test what they claim)

### Key Documentation

- `STATUS.md` - Current phase, debt counts, testing tiers (source of truth)
- `TASKS.md` - Canonical task tracker
- `mu/docs/core/MetaCircularKernel.v0.md` - Kernel architecture
- `mu/docs/core/BootstrapPrimitives.v0.md` - 4 bootstrap primitives (mu_equal eliminated)
- `mu/docs/core/EngineNewsStructural.v0.md` - EngineNews closure detection spec
- `mu/docs/roadmap/ContentAddressedMu.md` - Content-Addressed Mu (Level 0+1 IMPLEMENTED, mu_equal eliminated)


## CI (Green Gate)


### CLI schema-triplet contract

All `--schema` emitters are validated via the canonical runner at `rcx_pi/cli_schema_run.py` (single source of truth for executing schema commands and strict-parsing the schema-triplet output).

Before you open a PR, run the local gate:

    ./scripts/green_gate.sh

See `STATUS.md` for testing tiers and `CLAUDE.md` for development workflow.



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

### Seeds (Mu Projections)

| Seed | Purpose |
|------|---------|
| `mu/substrate/kernel.v1.json` | Structural kernel (7 projections) - state machine |
| `mu/substrate/match.v2.json` | Pattern matching (8 projections) - with context passthrough |
| `mu/substrate/subst.v2.json` | Substitution (12 projections) - with context passthrough |
| `mu/bridge/bootstrap_structural.v1.json` | Non-linear pattern support (5 projections) |
| `mu/closures/recurrence.v1.json` | Closure detection (9 projections) - Rule 2.2♢ (proof-of-concept) |
| `mu/closures/recurrence.v2.json` | Hash-accelerated closure detection (9 projections) - production |
| `mu/closures/exhaustion.v1.json` | Operator exhaustion (11 projections) - Rule 3.1 |
| `mu/programs/hemispheres.v1.json` | Hemisphere routing (12 projections) - native structural routing |
| `mu/programs/paxos_demo.v1.json` | Paxos deadlock demo (6 projections) - application |
| `mu/programs/rcx_engine.v1.json` | Engine orchestration (11 projections) - structural specification |
| `mu/utilities/classify.v1.json` | Type classification (~6 projections) |
| `mu/utilities/eval.v1.json` | Evaluation (~7 projections) |

### Core Modules

| Module | Purpose |
|-------|---------|
| `rcx_pi/selfhost/step_mu.py` | Kernel execution (uses kernel.v1 + match.v2 + subst.v2) |
| `rcx_pi/selfhost/match_mu.py` | Pattern matching as Mu projections |
| `rcx_pi/selfhost/subst_mu.py` | Substitution as Mu projections |
| `rcx_pi/selfhost/eval_seed.py` | Bootstrap evaluator (apply_projection, step) |
| `rcx_pi/selfhost/mu_type.py` | Mu type validation and structural equality |
| `rcx_pi/selfhost/kernel.py` | Step budget infrastructure only |

### Testing

```
Tier 1: ./tools/audit_fast.sh    ~3 min   Core + security tests (local iteration)
Tier 2: ./tools/audit_all.sh     ~5-8 min All tests + fuzzers (before push)
Tier 3: pytest tests/stress/     ~10+ min Deep edge cases
```

Security tools have grounding tests in `tests/tools/` that verify the tools actually detect what they claim.

### Archived (superseded)

| Module | Status |
|--------|--------|
| `archive/mu_legacy/host/python/rcx_pi/bytecode_vm.py` | ARCHIVED - superseded by kernel + seeds |
| `archive/archive/docs/bytecode/` | ARCHIVED |
| `tests/archive/` | Legacy tests for deleted code |

Run `PYTHONHASHSEED=0 pytest` to verify health.

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
```

If `scripts/green_gate.sh` finishes without errors, RCX-π Core is healthy.

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
  - `scripts/rule_precedence.sh mu/mu_programs/rcx_core.mu --top 25`
- Emit a stable JSON summary:
  - `scripts/rule_precedence.sh mu/mu_programs/rcx_core.mu --json`

## CLI Quickstart
See `mu/docs/cli/cli_quickstart.md` for the umbrella `rcx` command and the JSON-emitting tools.

---

*Last updated: 2026-02-14*
