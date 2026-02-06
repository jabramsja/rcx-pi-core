"""Ensure all review runners inject the shared red-team prompt contract."""

from pathlib import Path
import importlib.util
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_contract_injected_for_all_runtime_agents():
    shared_agent_utils = _load_module("shared_agent_utils", TOOLS_DIR / "shared_agent_utils.py")
    load_prompt = shared_agent_utils.load_agent_prompt_with_contract

    agents = [
        "verifier",
        "adversary",
        "expert",
        "structural-proof",
        "grounding",
        "fuzzer",
        "translator",
        "visualizer",
        "advisor",
    ]

    for agent in agents:
        prompt = load_prompt(agent)
        assert "RCX Red-Team Contract (Injected)" in prompt, f"Contract missing for {agent}"
        assert "VERDICT:" in prompt, f"Verdict protocol missing for {agent}"


def test_runners_use_shared_contract_loader():
    runner_files = [
        "run_review.py",
        "run_ci_review.py",
        "run_interactive.py",
        "run_verifier.py",
        "run_adversary.py",
        "run_expert.py",
        "run_structural_proof.py",
        "run_grounding.py",
        "run_fuzzer.py",
        "run_translator.py",
        "run_visualizer.py",
        "run_advisor.py",
    ]

    for name in runner_files:
        content = (TOOLS_DIR / name).read_text()
        assert "load_agent_prompt_with_contract" in content, (
            f"{name} does not use shared contract loader"
        )
        direct_read = re.search(r'Path\("tools/agents/.+_prompt\.md"\)\.read_text\(\)', content)
        assert direct_read is None, f"{name} still reads prompt directly: {direct_read.group(0)}"
