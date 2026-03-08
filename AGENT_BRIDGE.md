# Agent Bridge

Purpose: define the tracked operator contract for automated Claude <-> Codex collaboration.

This file is **not** the live conversation ledger anymore.
Runtime bridge state lives in untracked `.agent_bus/`.

## Model

Bridge v1 is intentionally narrow:
1. one local supervisor process
2. one writer agent
3. one read-only reviewer agent
4. turn-based execution
5. SQLite bus for state and transcripts

This keeps the collaboration auditable without introducing dual-writer merge problems or background-daemon complexity.

## Rules

1. One supervisor run at a time.
2. One writer, one reviewer.
3. Git state is the source of truth for changed files.
4. `.agent_bus/` is runtime state and must stay untracked.
5. This file stays static; transcripts are rendered elsewhere.

## Tracked vs Untracked

Tracked in the repo:
- `AGENT_BRIDGE.md` — operator contract and entrypoint
- `mu/docs/agents/AgentBridgeProtocol.v0.md` — detailed protocol/spec
- `tools/agents/bridge_supervisor.py` — bridge CLI
- `tools/agents/bridge_schema.sql` — SQLite schema
- `tools/agents/bridge_adapters.py` — generic command adapters
- `tools/agents/templates/` — prompt templates
- `tools/agents/bridge_config.example.json` — config template

Untracked runtime state:
- `.agent_bus/bridge.db`
- `.agent_bus/bridge_config.json`
- `.agent_bus/prompts/`
- `.agent_bus/raw/`
- `.agent_bus/rendered/`
- `.agent_bus/validations/`

## Quick Start

```bash
python3 tools/agents/bridge_supervisor.py init
cp tools/agents/bridge_config.example.json .agent_bus/bridge_config.json
# edit .agent_bus/bridge_config.json with real local CLI commands

python3 tools/agents/bridge_supervisor.py submit \
  --task-file /path/to/task.txt \
  --wave-class MAINTENANCE \
  --reader claude \
  --reviewer codex \
  --allow-edits \
  --check "./tools/pre-push-fast"

# Non-interactive (original behavior)
python3 tools/agents/bridge_supervisor.py run <job_id>

# Interactive with live streaming + pause before reviewer
python3 tools/agents/bridge_supervisor.py run <job_id> -v --pause-after-reader

# Resume a paused job (runs reviewer)
python3 tools/agents/bridge_supervisor.py continue <job_id> -v

python3 tools/agents/bridge_supervisor.py status <job_id>
python3 tools/agents/bridge_supervisor.py render <job_id>
```

## Operating Rules

1. Single supervisor instance at a time.
2. Writer may edit only if the submitted job allows edits.
3. Reviewer is read-only by contract.
4. Git state, not agent prose, is the source of truth for changed files.
5. If the repo state changes during review, the review is stale and must be rerun.
6. `.agent_bus/` is local runtime state and must not be committed.

## Round Format

Bridge v1 does not append rounds to this tracked file.
The supervisor renders `.agent_bus/rendered/<job_id>.md` from:
- job metadata
- per-turn envelope summaries
- recorded validation results

The required machine envelope from each agent remains:

```text
BEGIN_AGENT_ENVELOPE
{ ...json... }
END_AGENT_ENVELOPE
```

## Scope Guard

Bridge v1 is for local orchestration only.
It does **not** include:
- background daemon mode
- file watching
- worktrees
- dual-writer collaboration
- markdown-as-database

## Detailed Spec

See [mu/docs/agents/AgentBridgeProtocol.v0.md](mu/docs/agents/AgentBridgeProtocol.v0.md) for:
- bus schema
- state machine
- adapter contract
- prompt envelope contract
- transcript rendering rules

Questions? Concerns? Thoughts? -- Think hard
