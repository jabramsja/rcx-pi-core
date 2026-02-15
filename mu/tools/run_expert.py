#!/usr/bin/env python3
"""Run the RCX expert agent on specified files."""

import sys
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from tools.agent_runner_common import (
    StandardFileRunnerConfig,
    exit_with_code,
    finalize_standard_result,
    parse_standard_file_runner_args,
    print_standard_runner_footer,
    print_standard_runner_header,
    run_standard_file_agent,
)
from tools.shared_agent_utils import (
    load_agent_prompt_with_contract,
)

EXPERT_PROMPT = load_agent_prompt_with_contract("expert")
CONFIG = StandardFileRunnerConfig(
    agent_name="expert",
    parser_description="Run RCX expert agent on specified files.",
    files_help="Files to review",
    run_message_prefix="Running expert review on",
    action_line_prefix="review these files",
    task_instructions=(
        "Read each file and produce an expert review following the format in your instructions. "
        "Focus on: unnecessary complexity, simpler approaches, emergent patterns, self-hosting concerns."
    ),
    max_turns=25,
    verdict_messages={
        "OVER_ENGINEERED": ("OVER_ENGINEERED - simplification needed", 1),
        "COULD_SIMPLIFY": ("COULD_SIMPLIFY - minor improvements possible", 0),
        "MINIMAL": ("MINIMAL - code is appropriately simple", 0),
    },
    default_message_prefix="EXPERT REVIEW COMPLETE",
)


async def run_expert(files: list[str], model_override: str | None = None) -> str:
    return await run_standard_file_agent(CONFIG, files, EXPERT_PROMPT, model_override=model_override)


async def main():
    args = parse_standard_file_runner_args(CONFIG)
    files = args.files
    print_standard_runner_header(CONFIG, files)

    result = await run_expert(files, model_override=args.model)

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
