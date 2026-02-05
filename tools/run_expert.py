#!/usr/bin/env python3
"""
Run the RCX expert agent on specified files.

This agent reviews code for unnecessary complexity, suggests simpler approaches,
and identifies emergent patterns.

Usage:
    python tools/run_expert.py rcx_pi/eval_seed.py
    python tools/run_expert.py rcx_pi/eval_seed.py rcx_pi/kernel.py
"""

import sys
import json
import subprocess
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


EXPERT_PROMPT = Path("tools/agents/expert_prompt.md").read_text()


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


async def run_expert(files: list[str]) -> str:
    """Run the expert agent on the specified files."""

    file_list = ", ".join(files)
    prompt = f"""You are the RCX Expert Agent. Your instructions are:

{EXPERT_PROMPT}

---

Now review these files: {file_list}

Read each file and produce an expert review following the format in your instructions.
Focus on: unnecessary complexity, simpler approaches, emergent patterns, self-hosting concerns.
"""

    result_text = ""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=25,
        )
    ):
        if hasattr(message, 'result') and message.result:
            result_text = message.result

    return result_text


async def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_expert.py <file1> [file2] ...")
        print("Example: python tools/run_expert.py rcx_pi/eval_seed.py")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running expert review on: {', '.join(files)}")
    print("=" * 60)

    result = await run_expert(files)

    print(result)
    print("=" * 60)

    # Compliance validation
    is_compliant, error = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict
    if "OVER_ENGINEERED" in result:
        print("\nOVER_ENGINEERED - simplification needed")
        sys.exit(1)
    elif "COULD_SIMPLIFY" in result:
        print("\nCOULD_SIMPLIFY - minor improvements possible")
    elif "MINIMAL" in result:
        print("\nMINIMAL - code is appropriately simple")
    else:
        print("\nEXPERT REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
