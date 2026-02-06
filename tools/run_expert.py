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
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import extract_verdict_secure, validate_compliance

EXPERT_PROMPT = Path("tools/agents/expert_prompt.md").read_text()


async def run_expert(files: list[str]) -> str:
    """Run the expert agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
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

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="expert")
    if verdict == "OVER_ENGINEERED":
        print("\nOVER_ENGINEERED - simplification needed")
        sys.exit(1)
    elif verdict == "COULD_SIMPLIFY":
        print("\nCOULD_SIMPLIFY - minor improvements possible")
    elif verdict == "MINIMAL":
        print("\nMINIMAL - code is appropriately simple")
    else:
        print(f"\nEXPERT REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
