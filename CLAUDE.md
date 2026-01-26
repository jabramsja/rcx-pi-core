# Claude Code Instructions for RCX

This file is read by Claude Code at session start. It contains project-specific instructions.

## Pre-Push Checklist

**BEFORE pushing or creating a PR, run these agents locally (uses Max subscription):**

1. **Verifier** - Check North Star invariants
2. **Adversary** - Red team for vulnerabilities
3. **Expert** - Code quality review

To run: Ask Claude Code to "run verifier/adversary/expert on [files]"

## Agent Summary

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| verifier | North Star invariant compliance | Every PR with rcx_pi/ changes |
| adversary | Security/attack surface analysis | New modules, security-sensitive code |
| expert | Code quality, simplification | Complex code, before major refactors |
| structural-proof | Verify Mu projection claims | When claiming "pure structural" |

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
- `docs/` - Design specs (read before modifying related code)
- `tools/pre-commit-check.sh` - Quick guardrails
- `tools/debt_dashboard.sh` - Host debt inventory

## North Star Invariants

1. Structure is the primitive (not host language semantics)
2. Stall → Fix → Trace → Closure is the native loop
3. Seeds must be minimal, growth structurally justified
4. Determinism is a hard invariant
5. Every task must reduce host smuggling
