---
description: "Agent review tiers and when to run agents"
globs: [".claude/agents/*", "tools/agents/*", "tools/runners/*"]
---

9 native agents in `.claude/agents/`. SDK orchestrator: `tools/runners/run_review.py`. Canonical docs: `mu/docs/agents/AgentRunbook.v0.md`.

Current Codex pipeline rule: do not use `run_review.py` as the normal
pre-merge path while `mu/tools/executors/executor_config.json` has
`agent_review_enabled=false`. Use dispatcher / Phase B / pre-commit supervisor /
commit executor instead.

| Tier | Command | When |
|------|---------|------|
| Codex Pipeline | `executor_dispatch.py` / Phase B / commit executor | Current Codex waves |
| SDK Quick | `run_review.py --pr --depth quick` | Explicit Claude/SDK review only |
| SDK Full | `run_review.py --pr --depth full` | Explicit Claude/SDK review only |
| SDK Rigorous | `run_review.py --pr --rigorous` | Explicit Claude/SDK review only |
| Docs-only | Skip agents, just run tests | No runtime changes |

**Rule:** If you touched `rcx_pi/selfhost/` or `mu/`, complete the active
executor review path before saying "done." Do not replace the configured
dispatcher/Phase B path with `run_review.py` unless an explicit SDK review wave
requires it.
