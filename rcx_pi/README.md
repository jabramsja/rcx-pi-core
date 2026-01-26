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

See `docs/core/RCXKernel.v0.md` and `docs/core/SelfHosting.v0.md`.

## Legacy (top-level)

Older modules kept for compatibility:

| Module | Status |
|--------|--------|
| `bytecode_vm.py` | ARCHIVED - superseded by kernel + seeds |
| `deep_eval.py` | Deep evaluation machinery |
| `programs.py` | Legacy program definitions |

## Utilities

| Module | Purpose |
|--------|---------|
| `cli_*.py` | CLI tools |
| `program_*.py` | Program descriptors |
| `replay_cli.py` | Trace replay |
| `projection_coverage.py` | Coverage analysis |

## Spec Architecture

- Base specs (`core`, `paradox_1over0`, `godel_liar`) describe *native worlds*
- Composite specs (`rcx_triad`, `rcx_triad_plus`) describe *selection lenses*
- `rcx_triad_router` must satisfy **100% coverage** of composite specs
- New Mu seeds:
  - go into base worlds *only if native*
  - otherwise go into `triad_plus_routes.py`

Never embed new semantics directly into base worlds.
