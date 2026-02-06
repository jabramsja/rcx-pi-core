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

from tools.shared_agent_utils import extract_verdict_secure, validate_compliance

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

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="structural-proof")
    if verdict == "PROVEN":
        print("\nCLAIM PROVEN")
    elif verdict == "UNPROVEN":
        print("\nCLAIM UNPROVEN - need concrete projections")
        sys.exit(1)
    elif verdict == "IMPOSSIBLE_AS_CLAIMED":
        print("\nCLAIM IMPOSSIBLE - cannot be done structurally")
        sys.exit(2)
    elif verdict == "NO_STRUCTURAL_CLAIMS":
        print("\nNO STRUCTURAL CLAIMS - nothing to verify")
    elif verdict == "REQUIRES_CI_VERIFICATION":
        print("\nREQUIRES CI VERIFICATION - execution unavailable")
    else:
        print(f"\nSTRUCTURAL PROOF REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
