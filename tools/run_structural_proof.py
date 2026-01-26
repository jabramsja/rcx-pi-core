#!/usr/bin/env python3
"""
Run the RCX structural-proof agent on a claim.

This agent demands CONCRETE PROOF that operations can be done structurally.
Use this BEFORE approving any plan that claims pattern matching works.

Usage:
    python tools/run_structural_proof.py "linked list append can be done with finite projections"
    python tools/run_structural_proof.py "match can be expressed as Mu projections"
"""

import sys
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


STRUCTURAL_PROOF_PROMPT = Path("tools/agents/structural_proof_prompt.md").read_text()


async def run_structural_proof(claim: str) -> str:
    """Run the structural-proof agent on a claim."""

    prompt = f"""You are the RCX Structural Proof Agent. Your instructions are:

{STRUCTURAL_PROOF_PROMPT}

---

Verify this claim: "{claim}"

Search the codebase for relevant projections and trace through them manually.
Produce a structural proof report following the format in your instructions.
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
        print("Usage: python tools/run_structural_proof.py \"<claim to verify>\"")
        print("Example: python tools/run_structural_proof.py \"linked list append works with finite projections\"")
        sys.exit(1)

    claim = " ".join(sys.argv[1:])
    print(f"Verifying claim: {claim}")
    print("=" * 60)

    result = await run_structural_proof(claim)

    print(result)
    print("=" * 60)

    if "PROVEN" in result:
        print("\nCLAIM PROVEN")
    elif "UNPROVEN" in result:
        print("\nCLAIM UNPROVEN - need concrete projections")
        sys.exit(1)
    elif "IMPOSSIBLE" in result:
        print("\nCLAIM IMPOSSIBLE - cannot be done structurally")
        sys.exit(2)
    else:
        print("\nSTRUCTURAL PROOF REVIEW COMPLETE")


if __name__ == "__main__":
    anyio.run(main)
