#!/usr/bin/env python3
"""
Run the RCX verifier agent on specified files.

This is REAL automation using the Claude Agent SDK.
It runs the verifier agent with the prompt from tools/agents/verifier_prompt.md.

Usage:
    python tools/run_verifier.py rcx_pi/eval_seed.py
    python tools/run_verifier.py rcx_pi/eval_seed.py rcx_pi/kernel.py
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

VERIFIER_PROMPT = load_agent_prompt_with_contract("verifier")


async def run_verifier(files: list[str], model_override: str | None = None) -> str:
    """Run the verifier agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    agent_model = resolve_agent_model("verifier", model_override)
    prompt = f"""You are the RCX Verifier Agent. Your instructions are:

{VERIFIER_PROMPT}

---

Now verify these files: {file_list}

Read each file and produce a verification report following the format in your instructions.
"""

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=20,
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
        description="Run RCX verifier agent on specified files."
    )
    parser.add_argument("files", nargs="+", help="Files to review")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for verifier (default uses policy)",
    )
    args = parser.parse_args()

    files = args.files
    print(f"Running verifier on: {', '.join(files)}")
    print("=" * 60)

    result = await run_verifier(files, model_override=args.model)

    print(result)
    print("=" * 60)

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="verifier")
    if verdict == "APPROVE":
        print("\nVERIFICATION PASSED (APPROVE)")
    elif verdict == "REQUEST_CHANGES":
        print("\nVERIFICATION FAILED (REQUEST_CHANGES)")
        sys.exit(1)
    elif verdict == "NEEDS_DISCUSSION":
        print("\nVERIFICATION NEEDS DISCUSSION")
        sys.exit(2)
    else:
        print(f"\nVERIFICATION COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
