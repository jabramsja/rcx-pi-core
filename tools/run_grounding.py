#!/usr/bin/env python3
"""
Run the RCX grounding agent on specified files.

This agent converts abstract structural claims into concrete executable tests.
Use this to lock in behavior with real tests, not just verbal claims.

Usage:
    python tools/run_grounding.py rcx_pi/selfhost/eval_seed.py
    python tools/run_grounding.py rcx_pi/selfhost/match_mu.py rcx_pi/selfhost/subst_mu.py
"""

import sys
import json
import subprocess
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


GROUNDING_PROMPT = Path("tools/agents/grounding_prompt.md").read_text()


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


async def run_grounding(files: list[str]) -> str:
    """Run the grounding agent on the specified files."""

    file_list = ", ".join(files)
    prompt = f"""You are the RCX Grounding Agent. Your instructions are:

{GROUNDING_PROMPT}

---

Now ground the claims in these files: {file_list}

Read each file, identify claims in docs/comments, and verify they have executable tests.
Produce a grounding report following the format in your instructions.
"""

    result_text = ""

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=30,
        )
    ):
        if hasattr(message, 'result') and message.result:
            result_text = message.result

    return result_text


async def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_grounding.py <file1> [file2] ...")
        print("Example: python tools/run_grounding.py rcx_pi/selfhost/eval_seed.py")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running grounding on: {', '.join(files)}")
    print("=" * 60)

    result = await run_grounding(files)

    print(result)
    print("=" * 60)

    # Compliance validation
    is_compliant, error = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict
    if "UNGROUNDED" in result and "PARTIALLY" not in result:
        print("\nUNGROUNDED - claims lack tests")
        sys.exit(1)
    elif "THEATER" in result:
        print("\nTHEATER - tests exist but don't verify claims")
        sys.exit(2)
    elif "PARTIALLY_GROUNDED" in result:
        print("\nPARTIALLY_GROUNDED - some claims verified")
    elif "GROUNDED" in result:
        print("\nGROUNDED - all claims have executable tests")
    else:
        print("\nGROUNDING REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
