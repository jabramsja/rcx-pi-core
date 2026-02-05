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
import json
import subprocess
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


TRANSLATOR_PROMPT = Path("tools/agents/translator_prompt.md").read_text()


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


async def run_translator(files: list[str], request: str | None = None) -> str:
    """Run the translator agent on the specified files."""

    file_list = ", ".join(files)
    request_context = ""
    if request:
        request_context = f"\n\n**Original Request:** {request}"

    prompt = f"""You are the RCX Translator Agent. Your instructions are:

{TRANSLATOR_PROMPT}

---

Now translate these files to plain English: {file_list}{request_context}

Read each file and explain what it does in simple terms a non-coder can understand.
Detect host smuggling and scope creep.
Produce a translator report following the format in your instructions.
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
        print("Usage: python tools/run_translator.py <file1> [file2] ... [--request \"original request\"]")
        print("Example: python tools/run_translator.py rcx_pi/selfhost/eval_seed.py")
        sys.exit(1)

    # Parse args - extract --request if present
    files = []
    request = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--request" and i + 1 < len(sys.argv):
            request = sys.argv[i + 1]
            i += 2
        else:
            files.append(sys.argv[i])
            i += 1

    if not files:
        print("Error: No files specified")
        sys.exit(1)

    print(f"Running translator on: {', '.join(files)}")
    if request:
        print(f"Original request: {request}")
    print("=" * 60)

    result = await run_translator(files, request)

    print(result)
    print("=" * 60)

    # Compliance validation
    is_compliant, error = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict
    if "DEVIATES" in result:
        print("\nDEVIATES - code doesn't match intent")
        sys.exit(1)
    elif "NEEDS_DISCUSSION" in result:
        print("\nNEEDS_DISCUSSION - clarification required")
        sys.exit(2)
    elif "MATCHES_INTENT" in result:
        print("\nMATCHES_INTENT - code matches original request")
    else:
        print("\nTRANSLATOR REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
