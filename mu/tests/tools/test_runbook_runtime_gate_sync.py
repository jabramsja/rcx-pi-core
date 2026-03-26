"""Ensure AgentRunbook gate table matches runtime hard-gate configuration."""

from pathlib import Path

from mu.tests.tools.module_loader import load_module

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "agents" / "AgentRunbook.v0.md"
TOOLS_DIR = PROJECT_ROOT / "tools"


shared_agent_utils = load_module("shared_agent_utils", TOOLS_DIR / "runners" / "shared_agent_utils.py")
HARD_GATE_AGENTS = shared_agent_utils.HARD_GATE_AGENTS


def _parse_runbook_hard_gates(text: str) -> set[str]:
    hard = set()
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("| Agent | Gate Type |"):
            in_table = True
            continue
        if in_table and not line.startswith("|"):
            break
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        agent = cells[0]
        gate_type = cells[1].lower()
        if gate_type == "hard":
            hard.add(agent)
    return hard


def test_runbook_gate_table_matches_runtime_hard_gates():
    assert RUNBOOK_PATH.exists(), f"Runbook not found: {RUNBOOK_PATH}"
    runbook_text = RUNBOOK_PATH.read_text()
    runbook_hard_gates = _parse_runbook_hard_gates(runbook_text)
    assert runbook_hard_gates == HARD_GATE_AGENTS, (
        "AgentRunbook hard-gate table is out of sync with runtime HARD_GATE_AGENTS.\n"
        f"runbook={sorted(runbook_hard_gates)} runtime={sorted(HARD_GATE_AGENTS)}"
    )
