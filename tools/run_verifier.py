#!/usr/bin/env python3
"""Run the RCX verifier agent on specified files."""

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

VERIFIER_PROMPT = load_agent_prompt_with_contract("verifier")
CONFIG = StandardFileRunnerConfig(
    agent_name="verifier",
    parser_description="Run RCX verifier agent on specified files.",
    files_help="Files to review",
    run_message_prefix="Running verifier on",
    action_line_prefix="verify these files",
    task_instructions=(
        "Read each file and produce a verification report following the format in your instructions."
    ),
    max_turns=20,
    verdict_messages={
        "APPROVE": ("VERIFICATION PASSED (APPROVE)", 0),
        "REQUEST_CHANGES": ("VERIFICATION FAILED (REQUEST_CHANGES)", 1),
        "NEEDS_DISCUSSION": ("VERIFICATION NEEDS DISCUSSION", 2),
    },
    default_message_prefix="VERIFICATION COMPLETE",
)


async def run_verifier(files: list[str], model_override: str | None = None) -> str:
    return await run_standard_file_agent(CONFIG, files, VERIFIER_PROMPT, model_override=model_override)


async def main():
    args = parse_standard_file_runner_args(CONFIG)
    files = args.files
    print_standard_runner_header(CONFIG, files)

    result = await run_verifier(files, model_override=args.model)

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
