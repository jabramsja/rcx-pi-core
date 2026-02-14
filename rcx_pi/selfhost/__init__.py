"""
RCX Self-Hosting Core

This subpackage contains the core self-hosting implementation:
- mu_type: Mu type validation and guardrails
- kernel: Minimal kernel (4 primitives)
- eval_seed: EVAL_SEED evaluator
- match_mu: Pattern matching as Mu projections
- subst_mu: Substitution as Mu projections
- step_mu: Self-hosting step (uses match_mu + subst_mu)
- seed_integrity: Seed file integrity verification (checksums, structure)

Architecture: Kernel (4 primitives) + Seeds (Mu projections)
See docs/core/RCXKernel.v0.md and docs/core/SelfHosting.v0.md
"""
