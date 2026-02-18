#!/usr/bin/env python3
"""
Run the RCX structural-proof agent on a claim.

This agent demands CONCRETE PROOF that operations can be done structurally.
Use this BEFORE approving any plan that claims pattern matching works.

Usage:
    python tools/runners/run_structural_proof.py "linked list append can be done with finite projections"
    python tools/runners/run_structural_proof.py "match can be expressed as Mu projections"
"""

import sys
import argparse
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent.parent))

from tools.runners.agent_runner_common import (
    StandardFileRunnerConfig,
    exit_with_code,
    finalize_standard_result,
    print_standard_runner_footer,
    run_agent_prompt,
)
from tools.runners.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    load_agent_prompt_with_contract,
)

STRUCTURAL_PROOF_PROMPT = load_agent_prompt_with_contract("structural-proof")
CONFIG = StandardFileRunnerConfig(
    agent_name="structural-proof",
    parser_description="Run RCX structural-proof agent on a claim.",
    files_help="N/A",
    run_message_prefix="Verifying claim",
    action_line_prefix="verify this claim",
    task_instructions=(
        "Search the codebase for relevant projections and trace through them manually. "
        "Produce a structural proof report following the format in your instructions."
    ),
    max_turns=30,
    verdict_messages={
        "PROVEN": ("CLAIM PROVEN", 0),
        "UNPROVEN": ("CLAIM UNPROVEN - need concrete projections", 1),
        "IMPOSSIBLE_AS_CLAIMED": ("CLAIM IMPOSSIBLE - cannot be done structurally", 2),
        "NO_STRUCTURAL_CLAIMS": ("NO STRUCTURAL CLAIMS - nothing to verify", 0),
        "REQUIRES_CI_VERIFICATION": ("REQUIRES CI VERIFICATION - execution unavailable", 0),
    },
    default_message_prefix="STRUCTURAL PROOF REVIEW COMPLETE",
)


async def run_structural_proof(claim: str, model_override: str | None = None) -> str:
    """Run the structural-proof agent on a claim."""
    return await run_agent_prompt(
        agent_name=CONFIG.agent_name,
        prompt_text=STRUCTURAL_PROOF_PROMPT,
        action_line=f'Verify this claim: "{claim}"',
        task_instructions=CONFIG.task_instructions,
        model_override=model_override,
        allowed_tools=["Read", "Grep", "Glob"],
        max_turns=CONFIG.max_turns,
    )


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
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
