#!/usr/bin/env python3
"""
Run the RCX visualizer agent on specified files or structures.

This agent draws Mu structures as Mermaid diagrams. Use this to visually verify
structural claims - Python lists show as blobs, linked lists show as chains.

Usage:
    python tools/run_visualizer.py rcx_pi/selfhost/step_mu.py
    python tools/run_visualizer.py mu/substrate/kernel.v1.json
    python tools/run_visualizer.py --structure '{"head": 1, "tail": {"head": 2, "tail": null}}'
"""

import sys
import argparse
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent.parent))

from tools.runners.agent_runner_common import (
    StandardFileRunnerConfig,
    exit_with_code,
    finalize_standard_result,
    print_standard_runner_footer,
    run_agent_prompt,
    sanitize_files,
)
from tools.runners.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    load_agent_prompt_with_contract,
)

VISUALIZER_PROMPT = load_agent_prompt_with_contract("visualizer")
CONFIG = StandardFileRunnerConfig(
    agent_name="visualizer",
    parser_description="Run RCX visualizer agent on files or a specific structure.",
    files_help="Files to visualize",
    run_message_prefix="Running visualizer on",
    action_line_prefix="visualize this target",
    task_instructions=(
        "Read the files/structure and produce Mermaid diagrams showing the actual structure. "
        "Flag any Python lists (red blobs) vs proper linked lists (chains). "
        "Produce a visualization report following the format in your instructions."
    ),
    max_turns=20,
    verdict_messages={
        "STRUCTURAL_LIES": ("⚠️  RED FLAGS DETECTED - structural lies found", 1),
        "PYTHON_SMUGGLING": ("⚠️  RED FLAGS DETECTED - Python smuggling found", 1),
        "CLEAN": ("VISUALIZATION COMPLETE", 0),
    },
    default_message_prefix="⚠️  VISUALIZATION INCOMPLETE",
    default_exit_code=1,  # UNKNOWN verdict = red flag for visualizer
)


async def run_visualizer(
    files: list[str] | None = None,
    structure: str | None = None,
    model_override: str | None = None,
) -> str:
    """Run the visualizer agent on files or a specific structure."""
    if structure:
        target = f"this Mu structure:\n```json\n{structure}\n```"
    elif files:
        target = f"these files: {', '.join(sanitize_files(files))}"
    else:
        target = "the relevant data structures"

    return await run_agent_prompt(
        agent_name=CONFIG.agent_name,
        prompt_text=VISUALIZER_PROMPT,
        action_line=f"Now visualize {target}",
        task_instructions=CONFIG.task_instructions,
        model_override=model_override,
        allowed_tools=["Read", "Grep", "Glob"],
        max_turns=CONFIG.max_turns,
    )


async def main():
    parser = argparse.ArgumentParser(
        description="Run RCX visualizer agent on files or a specific structure."
    )
    parser.add_argument("files", nargs="*", help="Files to visualize")
    parser.add_argument("--structure", help="Inline JSON structure to visualize")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for visualizer (default uses policy)",
    )
    args = parser.parse_args()

    files = args.files
    structure = args.structure

    if not files and not structure:
        parser.print_help()
        sys.exit(1)

    if structure:
        print(f"Visualizing structure: {structure[:50]}...")
    else:
        print(f"Running visualizer on: {', '.join(files)}")
    print("=" * 60)

    result = await run_visualizer(
        files if files else None,
        structure,
        model_override=args.model,
    )

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
