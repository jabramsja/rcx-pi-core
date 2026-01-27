# Claude Code Instructions for RCX

This file is read by Claude Code at session start. It contains project-specific instructions.

## Current Status (2026-01-27)

**Phase 6d Complete:** Iterative validation and code cleanup.
- Core self-hosting: `rcx_pi/selfhost/` (mu_type, kernel, eval_seed, match_mu, subst_mu, step_mu, classify_mu)
- Seeds: `seeds/match.v1.json`, `seeds/subst.v1.json`, `seeds/classify.v1.json`
- `_check_empty_var_names()` now iterative with explicit stack
- Removed deprecated `_seen` params and unused `Any` imports
- 53 fuzzer tests, 10,000+ random examples verify parity
- Debt: 11 total (8 tracked + 3 AST_OK), threshold 11 (at ceiling)
- All 6 agents APPROVE stack for Phase 7 readiness

## Pre-Push Checklist

**BEFORE pushing or creating a PR, run these agents locally (uses Max subscription):**

1. **Verifier** - Check North Star invariants
2. **Adversary** - Red team for vulnerabilities
3. **Expert** - Code quality review
4. **Structural-proof** - Verify Mu projection claims

**For core kernel/seed code, also run:**
5. **Grounding** - Write executable tests
6. **Fuzzer** - Property-based testing (Hypothesis)

To run: Ask Claude Code to "run verifier/adversary/expert/structural-proof on [files]"

## Agent Summary (8 agents)

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| verifier | North Star invariant compliance | Every PR with rcx_pi/ changes |
| adversary | Security/attack surface analysis | New modules, security-sensitive code |
| expert | Code quality, simplification | Complex code, before major refactors |
| structural-proof | Verify Mu projection claims | When claiming "pure structural" |
| grounding | Convert claims to executable tests | Core kernel/seed code |
| fuzzer | Property-based testing (1000+ inputs) | Core kernel/seed code |
| translator | Plain English explanation | On request (founder review) |
| visualizer | Mermaid diagrams of Mu structures | On request (founder review) |

See `docs/agents/AgentRig.v0.md` for full agent rig documentation.

## Cost Model

- **Local agents (ask Claude Code)**: Uses Max subscription - FREE
- **CI agents (GitHub Actions)**: Uses API - COSTS MONEY (manual trigger only)
- **Local tools (python tools/run_*.py)**: Uses API key - COSTS MONEY

## Standard Workflow

```
1. ./tools/pre-commit-check.sh          # Quick local checks
2. Ask Claude Code to run agents        # Uses subscription (free)
3. git push                              # CI runs tests/audit (free)
4. [Optional] Manual CI agent trigger   # Only when needed (costs $)
```

## Key Files

- `TASKS.md` - Canonical task list, single source of truth
- `docs/core/` - Core design specs (RCXKernel, EVAL_SEED, SelfHosting, MuType)
- `docs/agents/AgentRig.v0.md` - Agent rig documentation
- `tools/pre-commit-check.sh` - Quick guardrails
- `tools/debt_dashboard.sh` - Host debt inventory
- `rcx_pi/selfhost/` - Core self-hosting implementation

## North Star Invariants

1. Structure is the primitive (not host language semantics)
2. Stall → Fix → Trace → Closure is the native loop
3. Seeds must be minimal, growth structurally justified
4. Determinism is a hard invariant
5. Every task must reduce host smuggling
