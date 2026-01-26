#!/usr/bin/env python3
"""
Run the RCX adversary agent on specified files.

This agent tries to BREAK things - find edge cases, type confusion,
lambda calculus smuggling, non-determinism.

Usage:
    python tools/run_adversary.py rcx_pi/eval_seed.py
"""

import sys
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


ADVERSARY_PROMPT = Path(".claude/agents/adversary.md").read_text()


async def run_adversary(files: list[str]) -> str:
    """Run the adversary agent on the specified files."""

    file_list = ", ".join(files)
    prompt = f"""You are the RCX Adversary Agent. Your instructions are:

{ADVERSARY_PROMPT}

---

Now attack these files: {file_list}

Read each file and try to find vulnerabilities. Produce an adversary report following the format in your instructions.
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
        print("Usage: python tools/run_adversary.py <file1> [file2] ...")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running adversary on: {', '.join(files)}")
    print("=" * 60)

    result = await run_adversary(files)

    print(result)
    print("=" * 60)

    if "VULNERABLE" in result:
        print("\nVULNERABILITIES FOUND - review required")
        sys.exit(1)
    elif "SECURE" in result:
        print("\nSECURE - no vulnerabilities found")
    else:
        print("\nADVERSARY REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
