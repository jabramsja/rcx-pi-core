---
description: "Agent review tiers and when to run agents"
globs: [".claude/agents/*", "tools/agents/*", "tools/runners/*"]
---

9 native agents in `.claude/agents/`. SDK orchestrator: `tools/runners/run_review.py`. Both are complementary. Canonical docs: `mu/docs/agents/AgentRunbook.v0.md`.

| Tier | Command | When |
|------|---------|------|
| Quick | `run_review.py --pr --depth quick` | Most commits |
| Full | `run_review.py --pr --depth full` | Pre-merge |
| Rigorous | `run_review.py --pr --rigorous` | Core/security changes |
| Docs-only | Skip agents, just run tests | No runtime changes |

**Rule:** If you touched `rcx_pi/selfhost/` or `mu/`, run agents before saying "done."
