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
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    build_sdk_options,
    extract_text_from_message,
    load_agent_prompt_with_contract,
    resolve_agent_model,
    validate_compliance,
)

VISUALIZER_PROMPT = load_agent_prompt_with_contract("visualizer")


async def run_visualizer(
    files: list[str] | None = None,
    structure: str | None = None,
    model_override: str | None = None,
) -> str:
    """Run the visualizer agent on files or a specific structure."""
    agent_model = resolve_agent_model("visualizer", model_override)

    if structure:
        target = f"this Mu structure:\n```json\n{structure}\n```"
    elif files:
        target = f"these files: {', '.join(files)}"
    else:
        target = "the relevant data structures"

    prompt = f"""You are the RCX Visualizer Agent. Your instructions are:

{VISUALIZER_PROMPT}

---

Now visualize {target}

Read the files/structure and produce Mermaid diagrams showing the actual structure.
Flag any Python lists (red blobs) vs proper linked lists (chains).
Produce a visualization report following the format in your instructions.
"""

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=20,
            model=agent_model,
            require_model_kwarg=True,
        ),
    ):
        extracted = extract_text_from_message(message)
        if extracted:
            fragments.append(extracted)
        if hasattr(message, 'result') and message.result:
            result_text = message.result

    if not result_text and fragments:
        result_text = "\n".join(dict.fromkeys(fragments))

    return result_text


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
    print("=" * 60)

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check for red flags (Python lists detected)
    if "⚠️" in result or "PYTHON LIST" in result or "NOT STRUCTURAL" in result:
        print("\n⚠️  RED FLAGS DETECTED - Python structures found")
        sys.exit(1)
    else:
        print("\nVISUALIZATION COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
