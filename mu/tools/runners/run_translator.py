#!/usr/bin/env python3
"""
Run the RCX translator agent on specified files.

This agent explains code logic to the non-technical founder in plain English.
Detects scope creep and host smuggling.

Usage:
    python tools/run_translator.py rcx_pi/selfhost/eval_seed.py
    python tools/run_translator.py rcx_pi/selfhost/step_mu.py --request "Add kernel loop"
"""

import sys
import argparse
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
    print_standard_runner_footer,
    print_standard_runner_header,
    run_standard_file_agent,
)
from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    load_agent_prompt_with_contract,
)

TRANSLATOR_PROMPT = load_agent_prompt_with_contract("translator")
CONFIG = StandardFileRunnerConfig(
    agent_name="translator",
    parser_description="Run RCX translator agent on specified files.",
    files_help="Files to review",
    run_message_prefix="Running translator on",
    action_line_prefix="translate these files to plain English",
    task_instructions=(
        "Read each file and explain what it does in simple terms a non-coder can understand. "
        "Detect host smuggling and scope creep. Produce a translator report following the format "
        "in your instructions."
    ),
    max_turns=25,
    verdict_messages={
        "DEVIATES": ("DEVIATES - code doesn't match intent", 1),
        "SCOPE_CREEP": ("DEVIATES - code doesn't match intent", 1),
        "HOST_SMUGGLING": ("DEVIATES - code doesn't match intent", 1),
        "NEEDS_DISCUSSION": ("NEEDS_DISCUSSION - clarification required", 2),
        "MATCHES_INTENT": ("MATCHES_INTENT - code matches original request", 0),
    },
    default_message_prefix="TRANSLATOR REVIEW COMPLETE",
)


async def run_translator(
    files: list[str],
    request: str | None = None,
    model_override: str | None = None,
) -> str:
    task_instructions = CONFIG.task_instructions
    if request:
        task_instructions = (
            f"{task_instructions}\n\n"
            f"Original request (intent to validate): {request}"
        )
    return await run_standard_file_agent(
        CONFIG,
        files,
        TRANSLATOR_PROMPT,
        model_override=model_override,
        task_instructions_override=task_instructions,
    )


async def main():
    parser = argparse.ArgumentParser(description=CONFIG.parser_description)
    parser.add_argument("files", nargs="+", help=CONFIG.files_help)
    parser.add_argument("--request", help="Original request text for intent matching")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for translator (default uses policy)",
    )
    args = parser.parse_args()
    files = args.files
    request = args.request

    print_standard_runner_header(CONFIG, files)
    if request:
        print(f"Original request: {request}")

    result = await run_translator(
        files,
        request,
        model_override=args.model,
    )

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
