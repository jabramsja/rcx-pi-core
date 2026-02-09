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

EXPERT_PROMPT = load_agent_prompt_with_contract("expert")


async def run_expert(files: list[str], model_override: str | None = None) -> str:
    """Run the expert agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    agent_model = resolve_agent_model("expert", model_override)
    prompt = f"""You are the RCX Expert Agent. Your instructions are:

{EXPERT_PROMPT}

---

Now review these files: {file_list}

Read each file and produce an expert review following the format in your instructions.
Focus on: unnecessary complexity, simpler approaches, emergent patterns, self-hosting concerns.
"""

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=25,
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
        description="Run RCX expert agent on specified files."
    )
    parser.add_argument("files", nargs="+", help="Files to review")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for expert (default uses policy)",
    )
    args = parser.parse_args()

    files = args.files
    print(f"Running expert review on: {', '.join(files)}")
    print("=" * 60)

    result = await run_expert(files, model_override=args.model)

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
