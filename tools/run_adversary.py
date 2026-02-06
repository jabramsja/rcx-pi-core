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

from tools.shared_agent_utils import extract_verdict_secure, validate_compliance

ADVERSARY_PROMPT = Path("tools/agents/adversary_prompt.md").read_text()


async def run_adversary(files: list[str]) -> str:
    """Run the adversary agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
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

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="adversary")
    if verdict == "VULNERABLE":
        print("\nVULNERABILITIES FOUND - review required")
        sys.exit(1)
    elif verdict == "NEEDS_HARDENING":
        print("\nNEEDS_HARDENING - security improvements recommended")
        sys.exit(2)
    elif verdict == "SECURE":
        print("\nSECURE - no vulnerabilities found")
    else:
        print(f"\nADVERSARY REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
