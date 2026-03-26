"""Keep reasoning validator verdict coverage aligned with shared verdict registry."""

from pathlib import Path

from mu.tests.tools.module_loader import load_module

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"


shared_agent_utils = load_module("shared_agent_utils", TOOLS_DIR / "runners" / "shared_agent_utils.py")
validate_agent_reasoning = load_module("validate_agent_reasoning", TOOLS_DIR / "runners" / "validate_agent_reasoning.py")

AGENT_PASS_VERDICTS = shared_agent_utils.AGENT_PASS_VERDICTS
AGENT_VERDICTS = shared_agent_utils.AGENT_VERDICTS
VERDICT_REQUIREMENTS = validate_agent_reasoning.VERDICT_REQUIREMENTS


def _runtime_verdicts() -> set[str]:
    return {
        verdict
        for agent, verdicts in AGENT_VERDICTS.items()
        if not agent.startswith("deep_")
        for verdict in verdicts
    }


def test_reasoning_validator_covers_all_runtime_verdicts():
    runtime_verdicts = _runtime_verdicts()
    missing = runtime_verdicts - set(VERDICT_REQUIREMENTS)
    assert not missing, f"VERDICT_REQUIREMENTS missing runtime verdicts: {sorted(missing)}"


def test_pass_verdicts_are_registered_for_each_agent():
    for agent, pass_verdicts in AGENT_PASS_VERDICTS.items():
        if agent.startswith("deep_"):
            continue
        defined = set(AGENT_VERDICTS.get(agent, []))
        unknown = set(pass_verdicts) - defined
        assert not unknown, (
            f"AGENT_PASS_VERDICTS[{agent}] contains verdicts not in AGENT_VERDICTS: "
            f"{sorted(unknown)}"
        )
