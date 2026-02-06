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
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import (
    extract_text_from_message,
    load_agent_prompt_with_contract,
    validate_compliance,
)

VISUALIZER_PROMPT = load_agent_prompt_with_contract("visualizer")


async def run_visualizer(files: list[str] | None = None, structure: str | None = None) -> str:
    """Run the visualizer agent on files or a specific structure."""

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
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=20,
        )
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
    if len(sys.argv) < 2:
        print("Usage: python tools/run_visualizer.py <file1> [file2] ...")
        print("       python tools/run_visualizer.py --structure '<json>'")
        print("Example: python tools/run_visualizer.py mu/substrate/kernel.v1.json")
        sys.exit(1)

    # Parse args
    files = []
    structure = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--structure" and i + 1 < len(sys.argv):
            structure = sys.argv[i + 1]
            i += 2
        else:
            files.append(sys.argv[i])
            i += 1

    if structure:
        print(f"Visualizing structure: {structure[:50]}...")
    else:
        print(f"Running visualizer on: {', '.join(files)}")
    print("=" * 60)

    result = await run_visualizer(files if files else None, structure)

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
