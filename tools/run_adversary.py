#!/usr/bin/env python3
"""Run the RCX adversary agent on specified files."""

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

ADVERSARY_PROMPT = load_agent_prompt_with_contract("adversary")
CONFIG = StandardFileRunnerConfig(
    agent_name="adversary",
    parser_description="Run RCX adversary agent on specified files.",
    files_help="Files to attack/review",
    run_message_prefix="Running adversary on",
    action_line_prefix="attack these files",
    task_instructions=(
        "Read each file and try to find vulnerabilities. Produce an adversary report "
        "following the format in your instructions."
    ),
    max_turns=25,
    verdict_messages={
        "VULNERABLE": ("VULNERABILITIES FOUND - review required", 1),
        "NEEDS_HARDENING": ("NEEDS_HARDENING - security improvements recommended", 2),
        "SECURE": ("SECURE - no vulnerabilities found", 0),
    },
    default_message_prefix="ADVERSARY REVIEW COMPLETE",
)


async def run_adversary(files: list[str], model_override: str | None = None) -> str:
    return await run_standard_file_agent(CONFIG, files, ADVERSARY_PROMPT, model_override=model_override)


async def main():
    args = parse_standard_file_runner_args(CONFIG)
    files = args.files
    print_standard_runner_header(CONFIG, files)

    result = await run_adversary(files, model_override=args.model)

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
