#!/usr/bin/env python3
"""
Shared CLI/runtime helpers for standard file-based agent runners.

This module intentionally targets the high-duplication runners that all:
- accept one or more file paths,
- build a prompt from a per-agent prompt template,
- run via Claude Agent SDK query loop,
- validate compliance + verdict and map to exit codes.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# Ensure repo root is on sys.path for consistent import resolution
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    build_sdk_options,
    extract_text_from_message,
    extract_verdict_secure,
    resolve_agent_model,
    sanitize_for_prompt,
    validate_compliance,
)


@dataclass(frozen=True)
class StandardFileRunnerConfig:
    agent_name: str
    parser_description: str
    files_help: str
    run_message_prefix: str
    action_line_prefix: str
    task_instructions: str
    max_turns: int
    verdict_messages: Mapping[str, tuple[str, int]]
    default_message_prefix: str


def _sanitize_files(files: list[str]) -> list[str]:
    # Security: sanitize file paths before prompt injection.
    return [f.replace("\n", "_").replace("\r", "_").replace("`", "_")[:200] for f in files[:20]]


async def run_agent_prompt(
    *,
    agent_name: str,
    prompt_text: str,
    action_line: str,
    task_instructions: str,
    model_override: str | None = None,
    allowed_tools: list[str] | None = None,
    max_turns: int = 20,
) -> str:
    """Run a generic agent prompt with shared SDK execution loop."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except Exception as exc:
        raise RuntimeError(
            "claude_agent_sdk is unavailable or incompatible in this environment"
        ) from exc

    agent_model = resolve_agent_model(agent_name, model_override)
    tools = allowed_tools or ["Read", "Grep", "Glob"]
    action_line_safe = sanitize_for_prompt(action_line, max_len=2000)

    agent_title = agent_name.replace("-", " ").title()
    prompt = (
        f"You are the RCX {agent_title} Agent. Your instructions are:\n\n"
        f"{prompt_text}\n\n---\n\n"
        f"{action_line_safe}\n\n"
        f"{task_instructions}\n"
    )

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=tools,
            max_turns=max_turns,
            model=agent_model,
            require_model_kwarg=True,
        ),
    ):
        extracted = extract_text_from_message(message)
        if extracted:
            fragments.append(extracted)
        if hasattr(message, "result") and message.result:
            result_text = message.result

    if not result_text and fragments:
        result_text = "\n".join(dict.fromkeys(fragments))

    return result_text


async def run_standard_file_agent(
    config: StandardFileRunnerConfig,
    files: list[str],
    prompt_text: str,
    model_override: str | None = None,
    task_instructions_override: str | None = None,
) -> str:
    """Run a standard file-based agent using shared execution logic."""
    safe_files = _sanitize_files(files)
    file_list = ", ".join(safe_files)
    task_instructions = task_instructions_override or config.task_instructions
    return await run_agent_prompt(
        agent_name=config.agent_name,
        prompt_text=prompt_text,
        action_line=f"Now {config.action_line_prefix}: {file_list}",
        task_instructions=task_instructions,
        model_override=model_override,
        allowed_tools=["Read", "Grep", "Glob"],
        max_turns=config.max_turns,
    )


def finalize_standard_result(config: StandardFileRunnerConfig, result_text: str) -> int:
    """Validate compliance + verdict mapping and print terminal message.

    Returns the process exit code.
    """
    is_compliant, error, _ = validate_compliance(result_text)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        return 3

    verdict = extract_verdict_secure(result_text, agent_name=config.agent_name)
    message, exit_code = config.verdict_messages.get(
        verdict,
        (f"{config.default_message_prefix} (verdict: {verdict})", 0),
    )
    print(f"\n{message}")
    return exit_code


def parse_standard_file_runner_args(config: StandardFileRunnerConfig) -> argparse.Namespace:
    """Build and parse standard runner CLI args."""
    parser = argparse.ArgumentParser(description=config.parser_description)
    parser.add_argument("files", nargs="+", help=config.files_help)
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help=f"Override model for {config.agent_name} (default uses policy)",
    )
    return parser.parse_args()


def print_standard_runner_header(config: StandardFileRunnerConfig, files: list[str]) -> None:
    print(f"{config.run_message_prefix}: {', '.join(files)}")
    print("=" * 60)


def print_standard_runner_footer() -> None:
    print("=" * 60)


def exit_with_code(code: int) -> None:
    if code:
        sys.exit(code)
