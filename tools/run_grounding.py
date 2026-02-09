#!/usr/bin/env python3
"""Run the RCX grounding agent on specified files."""

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

GROUNDING_PROMPT = load_agent_prompt_with_contract("grounding")
CONFIG = StandardFileRunnerConfig(
    agent_name="grounding",
    parser_description="Run RCX grounding agent on specified files.",
    files_help="Files to review",
    run_message_prefix="Running grounding on",
    action_line_prefix="ground the claims in these files",
    task_instructions=(
        "Read each file, identify claims in docs/comments, and verify they have executable tests. "
        "Produce a grounding report following the format in your instructions."
    ),
    max_turns=30,
    verdict_messages={
        "UNGROUNDED": ("UNGROUNDED - claims lack tests", 1),
        "THEATER": ("THEATER - tests exist but don't verify claims", 2),
        "PARTIALLY_GROUNDED": ("PARTIALLY_GROUNDED - some claims verified", 0),
        "GROUNDED": ("GROUNDED - all claims have executable tests", 0),
    },
    default_message_prefix="GROUNDING REVIEW COMPLETE",
)


async def run_grounding(files: list[str], model_override: str | None = None) -> str:
    return await run_standard_file_agent(CONFIG, files, GROUNDING_PROMPT, model_override=model_override)


async def main():
    args = parse_standard_file_runner_args(CONFIG)
    files = args.files
    print_standard_runner_header(CONFIG, files)

    result = await run_grounding(files, model_override=args.model)

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
