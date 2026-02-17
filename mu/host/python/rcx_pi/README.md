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

## Spec Architecture

- Base specs (`core`, `paradox_1over0`, `godel_liar`) describe *native worlds*
- Composite specs (`rcx_triad`, `rcx_triad_plus`) describe *selection lenses*
- `rcx_triad_router` must satisfy **100% coverage** of composite specs
- New Mu seeds:
  - go into base worlds *only if native*
  - otherwise go into `triad_plus_routes.py`

Never embed new semantics directly into base worlds.
