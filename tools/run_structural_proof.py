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
import argparse
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    build_sdk_options,
    extract_text_from_message,
    extract_verdict_secure,
    load_agent_prompt_with_contract,
    resolve_agent_model,
    validate_compliance,
)

STRUCTURAL_PROOF_PROMPT = load_agent_prompt_with_contract("structural-proof")


async def run_structural_proof(claim: str, model_override: str | None = None) -> str:
    """Run the structural-proof agent on a claim."""
    agent_model = resolve_agent_model("structural-proof", model_override)

    prompt = f"""You are the RCX Structural Proof Agent. Your instructions are:

{STRUCTURAL_PROOF_PROMPT}

---

Verify this claim: "{claim}"

Search the codebase for relevant projections and trace through them manually.
Produce a structural proof report following the format in your instructions.
"""

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=30,
            model=agent_model,
            require_model_kwarg=True,
        ),
    ):
        extracted = extract_text_from_message(message)
        if extracted:
            fragments.append(extracted)
        if hasattr(message, 'result') and message.result:
            result_text = message.result

    if not result_text and fragments:
        result_text = "\n".join(dict.fromkeys(fragments))

    return result_text


async def main():
    parser = argparse.ArgumentParser(
        description="Run RCX structural-proof agent on a claim."
    )
    parser.add_argument("claim", nargs="+", help="Claim text to verify")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for structural-proof (default uses policy)",
    )
    args = parser.parse_args()

    claim = " ".join(args.claim)
    print(f"Verifying claim: {claim}")
    print("=" * 60)

    result = await run_structural_proof(claim, model_override=args.model)

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
