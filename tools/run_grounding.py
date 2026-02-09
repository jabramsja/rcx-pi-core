#!/usr/bin/env python3
"""
Run the RCX grounding agent on specified files.

This agent converts abstract structural claims into concrete executable tests.
Use this to lock in behavior with real tests, not just verbal claims.

Usage:
    python tools/run_grounding.py rcx_pi/selfhost/eval_seed.py
    python tools/run_grounding.py rcx_pi/selfhost/match_mu.py rcx_pi/selfhost/subst_mu.py
"""

import sys
import argparse
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

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

GROUNDING_PROMPT = load_agent_prompt_with_contract("grounding")


async def run_grounding(files: list[str], model_override: str | None = None) -> str:
    """Run the grounding agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    agent_model = resolve_agent_model("grounding", model_override)
    prompt = f"""You are the RCX Grounding Agent. Your instructions are:

{GROUNDING_PROMPT}

---

Now ground the claims in these files: {file_list}

Read each file, identify claims in docs/comments, and verify they have executable tests.
Produce a grounding report following the format in your instructions.
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
        description="Run RCX grounding agent on specified files."
    )
    parser.add_argument("files", nargs="+", help="Files to review")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for grounding (default uses policy)",
    )
    args = parser.parse_args()

    files = args.files
    print(f"Running grounding on: {', '.join(files)}")
    print("=" * 60)

    result = await run_grounding(files, model_override=args.model)

    print(result)
    print("=" * 60)

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="grounding")
    if verdict == "UNGROUNDED":
        print("\nUNGROUNDED - claims lack tests")
        sys.exit(1)
    elif verdict == "THEATER":
        print("\nTHEATER - tests exist but don't verify claims")
        sys.exit(2)
    elif verdict == "PARTIALLY_GROUNDED":
        print("\nPARTIALLY_GROUNDED - some claims verified")
    elif verdict == "GROUNDED":
        print("\nGROUNDED - all claims have executable tests")
    else:
        print(f"\nGROUNDING REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
