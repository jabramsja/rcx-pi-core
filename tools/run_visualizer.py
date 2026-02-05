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
import json
import subprocess
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


VISUALIZER_PROMPT = Path("tools/agents/visualizer_prompt.md").read_text()


def validate_compliance(output: str) -> tuple[bool, str]:
    """Run compliance validation on agent output.

    Returns (is_compliant, error_message).
    """
    try:
        result = subprocess.run(
            ["python3", "tools/validate_agent_compliance.py", "--json", "--strict"],
            input=output,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0 and not result.stdout:
            return False, f"Validator crashed: {result.stderr}"

        metrics = json.loads(result.stdout)
        if not metrics.get("compliant", False):
            violations = metrics.get("violations", ["Unknown violation"])
            return False, "; ".join(violations)

        return True, ""
    except Exception as e:
        return False, f"Validation error: {e}"


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

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=20,
        )
    ):
        if hasattr(message, 'result') and message.result:
            result_text = message.result

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

    # Compliance validation
    is_compliant, error = validate_compliance(result)
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
