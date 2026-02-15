"""Ensure agent prompt verdict tokens stay in sync with runtime verdict registry."""

from pathlib import Path
import re
import importlib.util

PROJECT_ROOT = Path(__file__).parents[2]
PROMPTS_DIR = PROJECT_ROOT / "tools" / "agents"
TOOLS_DIR = PROJECT_ROOT / "tools"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


shared_agent_utils = _load_module("shared_agent_utils", TOOLS_DIR / "shared_agent_utils.py")
AGENT_VERDICTS = shared_agent_utils.AGENT_VERDICTS


def _prompt_agent_name(prompt_file: Path) -> str:
    stem = prompt_file.stem
    if stem == "structural_proof_prompt":
        return "structural-proof"
    return stem.replace("_prompt", "")


def _extract_prompt_verdicts(text: str) -> set[str]:
    # Extract verdict tokens from bullet list format:
    #   - `TOKEN`: description text
    # Each prompt has "### Verdict" followed by instruction line then bullet list.
    tokens: set[str] = set()
    in_verdict_section = False
    for line in text.split("\n"):
        if re.match(r"###\s*Verdict", line):
            in_verdict_section = True
            continue
        if in_verdict_section:
            # Stop at next section header
            if line.strip().startswith("#") and "Verdict" not in line:
                break
            # Match bullet lines: "- `TOKEN`: ..."
            m = re.match(r"\s*-\s*`([A-Z_]+)`", line)
            if m:
                tokens.add(m.group(1))
    return tokens


def test_prompt_verdict_tokens_exist_in_registry():
    prompt_files = sorted(PROMPTS_DIR.glob("*_prompt.md"))
    assert prompt_files, "No prompt files found under tools/agents/"

    for prompt_file in prompt_files:
        agent_name = _prompt_agent_name(prompt_file)
        if agent_name not in AGENT_VERDICTS:
            # Ignore archived/auxiliary prompt files that are not runtime agents.
            continue
        text = prompt_file.read_text()
        prompt_tokens = _extract_prompt_verdicts(text)
        assert prompt_tokens, f"No verdict token list found in {prompt_file.name}"
        unknown = prompt_tokens - set(AGENT_VERDICTS[agent_name])
        assert not unknown, (
            f"Prompt {prompt_file.name} has verdicts not in AGENT_VERDICTS[{agent_name}]: "
            f"{sorted(unknown)}"
        )
