"""Ensure all review runners inject the shared red-team prompt contract."""

from pathlib import Path
import re

from mu.tests.tools.module_loader import load_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"


def test_contract_injected_for_all_runtime_agents():
    shared_agent_utils = load_module("shared_agent_utils", TOOLS_DIR / "runners" / "shared_agent_utils.py")
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
        assert "git stash" in prompt, f"Read-only repo-state rule missing for {agent}"
        assert "active repo root" in prompt or "current repo root" in prompt, (
            f"Current-checkout path rule missing for {agent}"
        )
        assert str(Path.cwd().resolve()) in prompt, f"Active checkout path missing for {agent}"
        assert "Do not redirect to external plan/report files" in prompt, (
            f"In-band review rule missing for {agent}"
        )
        assert "/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/" not in prompt, (
            f"Hardcoded checkout path still present for {agent}"
        )


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
        content = (TOOLS_DIR / "runners" / name).read_text()
        assert "load_agent_prompt_with_contract" in content, (
            f"{name} does not use shared contract loader"
        )
        direct_read = re.search(r'Path\("tools/agents/.+_prompt\.md"\)\.read_text\(\)', content)
        assert direct_read is None, f"{name} still reads prompt directly: {direct_read.group(0)}"
