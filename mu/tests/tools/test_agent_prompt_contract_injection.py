"""Ensure all review runners inject the shared red-team prompt contract."""

from pathlib import Path
import re

import pytest

from mu.tests.tools.module_loader import load_module


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"
LEGACY_CHECKOUT_ROOT = Path("/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX")
RUNTIME_AGENTS = (
    "verifier",
    "adversary",
    "expert",
    "structural-proof",
    "grounding",
    "fuzzer",
    "translator",
    "visualizer",
    "advisor",
)


@pytest.fixture
def shared_agent_utils():
    return load_module("shared_agent_utils", TOOLS_DIR / "runners" / "shared_agent_utils.py")


@pytest.fixture(params=[
    pytest.param(LEGACY_CHECKOUT_ROOT / ".scratch/worktrees/active-checkout", id="nested"),
    pytest.param(Path("/rcx-test-checkouts/ordinary"), id="ordinary"),
    pytest.param(LEGACY_CHECKOUT_ROOT, id="canonical"),
])
def active_checkout(request, monkeypatch):
    root = request.param.resolve()
    monkeypatch.setattr(Path, "cwd", classmethod(lambda cls: root))
    return root


def _assert_prompt_contract(prompt, agent, active_repo_root):
    assert "RCX Red-Team Contract (Injected)" in prompt, f"Contract missing for {agent}"
    assert "VERDICT:" in prompt, f"Verdict protocol missing for {agent}"
    assert "git stash" in prompt, f"Read-only repo-state rule missing for {agent}"
    assert "active repo root" in prompt or "current repo root" in prompt, (
        f"Current-checkout path rule missing for {agent}"
    )
    assert str(active_repo_root) in prompt, f"Active checkout path missing for {agent}"
    assert "Do not redirect to external plan/report files" in prompt, (
        f"In-band review rule missing for {agent}"
    )
    injected_checkout = (
        "## Active Checkout (Injected)\n\n"
        f"- Current repo root for this run: `{active_repo_root}`\n"
    )
    assert prompt.count(injected_checkout) == 1, f"Active checkout injection missing or duplicated for {agent}"
    # Exempt only the verified runtime injection. Replacing the root throughout
    # the prompt would hide stale template paths when the active root is PRIMARY.
    contract_and_template = prompt.replace(injected_checkout, "", 1)
    assert str(LEGACY_CHECKOUT_ROOT) not in contract_and_template, (
        f"Hardcoded checkout path still present for {agent}"
    )


def test_contract_injected_for_all_runtime_agents(shared_agent_utils):
    for agent in RUNTIME_AGENTS:
        prompt = shared_agent_utils.load_agent_prompt_with_contract(agent)
        _assert_prompt_contract(prompt, agent, Path.cwd().resolve())


@pytest.mark.parametrize("agent", RUNTIME_AGENTS)
def test_contract_accepts_active_checkout(shared_agent_utils, active_checkout, agent):
    prompt = shared_agent_utils.load_agent_prompt_with_contract(agent)
    _assert_prompt_contract(prompt, agent, active_checkout)


@pytest.mark.parametrize("source", ["template", "contract"])
@pytest.mark.parametrize("stale_reference", [
    pytest.param(LEGACY_CHECKOUT_ROOT / ".scratch/worktrees/foreign-checkout/file.py", id="foreign-worktree"),
    pytest.param(LEGACY_CHECKOUT_ROOT, id="canonical-root"),
])
def test_contract_rejects_stale_source_paths(
    shared_agent_utils, active_checkout, tmp_path, monkeypatch, source, stale_reference,
):
    sources = {
        "template": shared_agent_utils.get_agent_prompt_path("verifier"),
        "contract": shared_agent_utils.REDTEAM_CONTRACT_PATH,
    }
    for kind, path in sources.items():
        text = path.read_text()
        if kind == source:
            text += f"\nReview this hardcoded checkout: `{stale_reference}`\n"
        (tmp_path / path.name).write_text(text)
    monkeypatch.setattr(shared_agent_utils, "AGENT_PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(shared_agent_utils, "REDTEAM_CONTRACT_PATH", tmp_path / sources["contract"].name)

    prompt = shared_agent_utils.load_agent_prompt_with_contract("verifier")
    assert f"- Current repo root for this run: `{active_checkout}`\n" in prompt
    assert f"Review this hardcoded checkout: `{stale_reference}`" in prompt
    with pytest.raises(AssertionError, match="Hardcoded checkout path still present for verifier"):
        _assert_prompt_contract(prompt, "verifier", active_checkout)


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
