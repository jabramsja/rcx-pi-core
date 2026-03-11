#!/bin/bash
# =============================================================================
# Sync native subagent files from source-of-truth agent prompts
#
# Regenerates .claude/agents/*.md from:
#   1. tools/agents/_contract_redteam.md (shared red-team contract)
#   2. tools/agents/*_prompt.md (per-agent lens prompts)
#
# Usage: bash tools/sync_native_agents.sh
# =============================================================================

set -eo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$REPO_ROOT" << 'PYEOF'
import sys
import re
from pathlib import Path

repo = Path(sys.argv[1])
source_dir = repo / "tools" / "agents"
target_dir = repo / ".claude" / "agents"
contract_path = source_dir / "_contract_redteam.md"

MAX_TURNS = {
    "adversary": 40, "verifier": 45, "expert": 40, "structural-proof": 45,
    "grounding": 40, "fuzzer": 35, "translator": 30, "visualizer": 25, "advisor": 30,
}

target_dir.mkdir(parents=True, exist_ok=True)

# Load contract, strip DOC_STATUS HTML comment header
contract_text = contract_path.read_text()
contract_body = re.sub(r'<!--\n.*?-->\n*', '', contract_text, flags=re.DOTALL).strip()

synced = 0
for prompt_file in sorted(source_dir.glob("*_prompt.md")):
    agent_name = prompt_file.stem.replace("_prompt", "")
    turns = MAX_TURNS.get(agent_name, 30)

    # Parse YAML frontmatter
    text = prompt_file.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3:
        print(f"  SKIP: {agent_name} (no frontmatter)")
        continue

    frontmatter = parts[1].strip()
    body = parts[2].strip()

    # Extract name and description from frontmatter (name is canonical)
    name_match = re.search(r'^name:\s*(.+)$', frontmatter, re.MULTILINE)
    desc_match = re.search(r'^description:\s*(.+)$', frontmatter, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else agent_name
    description = desc_match.group(1).strip() if desc_match else f"{agent_name} agent"

    # Use YAML name for filename (e.g., structural-proof, not structural_proof)
    file_name = name
    turns = MAX_TURNS.get(file_name, MAX_TURNS.get(agent_name, 30))

    # Build native agent file
    native = f"""---
name: {name}
description: {description}
tools:
  - Read
  - Grep
  - Glob
  - Bash(readonly)
permissionMode: plan
maxTurns: {turns}
memory: project
---

{contract_body}

---

{body}
"""

    target_file = target_dir / f"{file_name}.md"
    target_file.write_text(native)
    synced += 1
    print(f"  synced: {agent_name} -> .claude/agents/{file_name}.md")

print(f"\nSynced {synced} native agent files from tools/agents/ -> .claude/agents/")
print(f"Contract source: tools/agents/_contract_redteam.md")
PYEOF
