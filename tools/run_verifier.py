#!/usr/bin/env python3
"""
Run the RCX verifier agent on specified files.

This is REAL automation using the Claude Agent SDK.
It runs the verifier agent with the prompt from .claude/agents/verifier.md.

Usage:
    python tools/run_verifier.py rcx_pi/eval_seed.py
    python tools/run_verifier.py rcx_pi/eval_seed.py rcx_pi/kernel.py
"""

import sys
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


VERIFIER_PROMPT = Path(".claude/agents/verifier.md").read_text()


async def run_verifier(files: list[str]) -> str:
    """Run the verifier agent on the specified files."""

    file_list = ", ".join(files)
    prompt = f"""You are the RCX Verifier Agent. Your instructions are:

{VERIFIER_PROMPT}

---

Now verify these files: {file_list}

Read each file and produce a verification report following the format in your instructions.
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
        print("Usage: python tools/run_verifier.py <file1> [file2] ...")
        print("Example: python tools/run_verifier.py rcx_pi/eval_seed.py")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running verifier on: {', '.join(files)}")
    print("=" * 60)

    result = await run_verifier(files)

    print(result)
    print("=" * 60)

    # Check verdict
    if "**APPROVE**" in result or "APPROVE" in result.split("VERDICT")[-1]:
        print("\nVERIFICATION PASSED (APPROVE)")
    elif "**REQUEST_CHANGES**" in result or "REQUEST_CHANGES" in result:
        print("\nVERIFICATION FAILED (REQUEST_CHANGES)")
        sys.exit(1)
    elif "**NEEDS_DISCUSSION**" in result or "NEEDS_DISCUSSION" in result:
        print("\nVERIFICATION NEEDS DISCUSSION")
        sys.exit(2)
    else:
        print("\nVERIFICATION COMPLETE (no clear verdict)")


if __name__ == "__main__":
    anyio.run(main)
