"""Keep reasoning validator verdict coverage aligned with shared verdict registry."""

from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


shared_agent_utils = _load_module("shared_agent_utils", TOOLS_DIR / "runners" / "shared_agent_utils.py")
validate_agent_reasoning = _load_module("validate_agent_reasoning", TOOLS_DIR / "runners" / "validate_agent_reasoning.py")

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
