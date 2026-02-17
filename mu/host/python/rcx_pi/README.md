<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-03
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# rcx_pi Package Structure

## Core Self-Hosting (`selfhost/`)

The kernel + seeds architecture for self-hosting:

| Module | Purpose |
|--------|---------|
| `mu_type.py` | Mu type validation and guardrails |
| `kernel.py` | 4 kernel primitives (identity, stall, trace, dispatch) |
| `eval_seed.py` | EVAL_SEED evaluator (match, substitute, step) |
| `match_mu.py` | Pattern matching as Mu projections |
| `subst_mu.py` | Substitution as Mu projections |
| `step_mu.py` | Self-hosting step (uses match_mu + subst_mu) |

See `mu/docs/core/RCXKernel.v0.md` and `mu/docs/core/SelfHosting.v0.md`.

## Active Modules (top-level)

| Module | Purpose |
|--------|---------|
| `deep_eval.py` | Deep evaluation machinery |
| `trace_canon.py` | Trace canonicalization |
| `projection_coverage.py` | Coverage analysis |
| `rule_motifs_v0.py` | Rule motif observability |

## CLI Tools

| Module | Purpose |
|--------|---------|
| `rcx_cli.py` | Umbrella CLI router |
| `cli_schema.py` | Schema triplet parsing |
| `cli_schema_run.py` | Schema triplet runner |
| `replay_cli.py` | Trace replay |

## Re-export Shims

| Module | Delegates to |
|--------|-------------|
| `eval_seed.py` | `selfhost.eval_seed` |
| `kernel.py` | `selfhost.kernel` |
| `match_mu.py` | `selfhost.match_mu` |
| `mu_type.py` | `selfhost.mu_type` |
| `step_mu.py` | `selfhost.step_mu` |
| `subst_mu.py` | `selfhost.subst_mu` |
| `worlds_probe.py` | `worlds.worlds_probe` |

## Deprecated & Archived Code

### Why some "dead" code paths remain

Several modules contain try/except ImportError blocks for the archived Rust substrate
(`rcx_pi_rust`). These are **intentional graceful degradation**, not forgotten code:

| Module | Deprecated path | What still works |
|--------|----------------|------------------|
| `worlds/worlds_probe.py` | Rust-backed world probing (lines 168-184) | Synthetic worlds: `godel_liar`, `rcx_triad_router` |
| `worlds/world_trace_cli.py` | Orbit traces via Rust backend | `--schema` mode (schema triplet output) |
| `worlds/archive/worlds_bridge.py` | All of it (shells out to `rcx_pi_rust`) | Nothing — kept because `worlds_probe` and `world_trace_cli` import from it |

**Why not delete them?** The `worlds_probe` and `world_trace_cli` modules are actively
used (tests, audit scripts, CI). Their working functionality (synthetic worlds, schema
output) is interleaved with the deprecated Rust paths. Removing the Rust code paths
would require refactoring the control flow, which is not justified until these modules
are rewritten to use `step_mu` (a potential future VECTOR item).

**Why not rewrite them now?** The Rust bridge provided `classify_with_world` and
`orbit_with_world_parsed` — execution of worlds through the Rust substrate. Replacing
this with `step_mu` would be a feature addition (making non-synthetic worlds work
again), not a bug fix. Boot1 is the current priority.

### Archived modules (Round 24H, PR #314)

The following were removed from `rcx_pi/` and moved to `archive/rcx_pi_legacy/`:

- `program_descriptor.py`, `program_descriptor_cli.py`, `program_descriptor_lib.py`
- `program_run.py`, `program_run_cli.py`
- `rcx_cli.py`'s `program` subcommand
- 14 additional legacy modules (~2,500 LOC total)

These depended on the pre-L3 Motif evaluator stack and/or the Rust substrate.

## Spec Architecture

- Base specs (`core`, `paradox_1over0`, `godel_liar`) describe *native worlds*
- Composite specs (`rcx_triad`, `rcx_triad_plus`) describe *selection lenses*
- `rcx_triad_router` must satisfy **100% coverage** of composite specs
- New Mu seeds:
  - go into base worlds *only if native*
  - otherwise go into `triad_plus_routes.py`

Never embed new semantics directly into base worlds.
