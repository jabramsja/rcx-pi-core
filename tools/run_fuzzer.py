#!/usr/bin/env python3
"""
Run the RCX fuzzer agent on specified files.

This agent generates Property-Based Tests using Hypothesis to smash code
with 1000+ random inputs. Catches edge cases that unit tests miss.

Usage:
    python tools/run_fuzzer.py rcx_pi/selfhost/eval_seed.py
    python tools/run_fuzzer.py rcx_pi/selfhost/mu_type.py rcx_pi/selfhost/match_mu.py
"""

import sys
import json
import subprocess
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


FUZZER_PROMPT = Path("tools/agents/fuzzer_prompt.md").read_text()


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


async def run_fuzzer(files: list[str]) -> str:
    """Run the fuzzer agent on the specified files."""

    file_list = ", ".join(files)
    prompt = f"""You are the RCX Fuzzer Agent. Your instructions are:

{FUZZER_PROMPT}

---

Now fuzz these files: {file_list}

Read each file and identify fuzz targets. Generate Property-Based Tests using Hypothesis.
Produce a fuzzer report following the format in your instructions.
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
        print("Usage: python tools/run_fuzzer.py <file1> [file2] ...")
        print("Example: python tools/run_fuzzer.py rcx_pi/selfhost/eval_seed.py")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running fuzzer on: {', '.join(files)}")
    print("=" * 60)

    result = await run_fuzzer(files)

    print(result)
    print("=" * 60)

    # Compliance validation
    is_compliant, error = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict
    if "BROKEN" in result:
        print("\nBROKEN - consistent failures found")
        sys.exit(1)
    elif "FRAGILE" in result:
        print("\nFRAGILE - flaky tests detected")
        sys.exit(2)
    elif "ROBUST" in result:
        print("\nROBUST - all property tests pass")
    else:
        print("\nFUZZER REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
