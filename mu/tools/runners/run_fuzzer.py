#!/usr/bin/env python3
"""Run the RCX fuzzer agent on specified files."""

import sys
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent.parent))

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

FUZZER_PROMPT = load_agent_prompt_with_contract("fuzzer")
CONFIG = StandardFileRunnerConfig(
    agent_name="fuzzer",
    parser_description="Run RCX fuzzer agent on specified files.",
    files_help="Files to review",
    run_message_prefix="Running fuzzer on",
    action_line_prefix="fuzz these files",
    task_instructions=(
        "Read each file and identify fuzz targets. Generate Property-Based Tests using Hypothesis. "
        "Produce a fuzzer report following the format in your instructions."
    ),
    max_turns=30,
    verdict_messages={
        "BROKEN": ("BROKEN - consistent failures found", 1),
        "FRAGILE": ("FRAGILE - flaky tests detected", 2),
        "ROBUST": ("ROBUST - all property tests pass", 0),
        "NOT_EXECUTED": ("NOT_EXECUTED - fuzzer could not run tests", 2),
    },
    default_message_prefix="FUZZER REVIEW COMPLETE",
)


async def run_fuzzer(files: list[str], model_override: str | None = None) -> str:
    return await run_standard_file_agent(CONFIG, files, FUZZER_PROMPT, model_override=model_override)


async def main():
    args = parse_standard_file_runner_args(CONFIG)
    files = args.files
    print_standard_runner_header(CONFIG, files)

    result = await run_fuzzer(files, model_override=args.model)

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
