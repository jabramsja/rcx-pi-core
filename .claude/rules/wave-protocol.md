---
description: "Wave protocol: executor-based Phase A/B/commit pipeline rules"
globs: ["mu/tools/executors/*", "mu/tools/agents/*", ".agent_bus/**"]
---

Executors in `mu/tools/executors/` own the Phase A/B/commit pipeline. See `mu/docs/agents/AgentBridgeProtocol.v0.md` for bridge details.

**Phase B = invoke `phase_b_executor.py`.** The executor invokes the implementer (via bridge adapter, not bridge review mode), runs agents, runs bridge loop, stages files, runs supervisor, and produces a commit handoff. Semantic/manual fallback is NOT a normal Phase B path. The only exception is `BOOTSTRAP_PHASE_B_EXCEPTION` — when the wave directly modifies the executor/implementer surfaces themselves.

**Commit protocol:** Use `commit_executor.py` for commit-through-merge. Use `meta_bridge_client.py` for supervisor calls (not raw subprocess). Use `tracker_sync_note.py` for tracker notes (not freeform prose). Hook verifies receipt — fail-closed verification. Commit only after a real handoff artifact exists. See `protocol_wave_execution.md` in memory for exact commands.

**Bridge bootstrap:** Every bridge invocation requires Codex to read `FOUNDER_SESSION_BOOTSTRAP.md` first. Injected automatically via `bridge_reviewer_prompt.txt` template.
