# Agent Execution Capability Non-Blockers (2026-03-15)

## NB1. run_deep_analysis.py still restricts agents to read-only
- `run_deep_analysis.py:232` hardcodes `allowed_tools=["Read", "Glob", "Grep"]` with explicit `# No Bash for security` comment.
- **Why deferred:** Deep analysis is a separate entrypoint for monthly/pre-release use. Its security-conscious restriction is intentional for that context. Enabling Bash there requires its own review. Target: deep-analysis hardening wave.

## NB2. SDK agents use full Bash, native agents use Bash(readonly)
- SDK `run_review.py` grants `Bash` (unrestricted). Native `.claude/agents/` use `Bash(readonly)` (read-only mode).
- **Why deferred:** The mismatch is real but acceptable for now — SDK agents run in the orchestrator context where full Bash is safe. Native agents run in Claude Code sessions where readonly is appropriate. Future: investigate `permission_mode='plan'` for SDK agents.
