#!/usr/bin/env python3
"""
Run the RCX translator agent on specified files.

This agent explains code logic to the non-technical founder in plain English.
Detects scope creep and host smuggling.

Usage:
    python tools/run_translator.py rcx_pi/selfhost/eval_seed.py
    python tools/run_translator.py rcx_pi/selfhost/step_mu.py --request "Add kernel loop"
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

TRANSLATOR_PROMPT = load_agent_prompt_with_contract("translator")


async def run_translator(
    files: list[str],
    request: str | None = None,
    model_override: str | None = None,
) -> str:
    """Run the translator agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    agent_model = resolve_agent_model("translator", model_override)
    request_context = ""
    if request:
        request_context = f"\n\n**Original Request:** {request}"

    prompt = f"""You are the RCX Translator Agent. Your instructions are:

{TRANSLATOR_PROMPT}

---

Now translate these files to plain English: {file_list}{request_context}

Read each file and explain what it does in simple terms a non-coder can understand.
Detect host smuggling and scope creep.
Produce a translator report following the format in your instructions.
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
        description="Run RCX translator agent on specified files."
    )
    parser.add_argument("files", nargs="+", help="Files to review")
    parser.add_argument("--request", help="Original request text for intent matching")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for translator (default uses policy)",
    )
    args = parser.parse_args()
    files = args.files
    request = args.request

    print(f"Running translator on: {', '.join(files)}")
    if request:
        print(f"Original request: {request}")
    print("=" * 60)

    result = await run_translator(
        files,
        request,
        model_override=args.model,
    )

    print(result)
    print("=" * 60)

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="translator")
    if verdict in {"DEVIATES", "SCOPE_CREEP", "HOST_SMUGGLING"}:
        print("\nDEVIATES - code doesn't match intent")
        sys.exit(1)
    elif verdict == "NEEDS_DISCUSSION":
        print("\nNEEDS_DISCUSSION - clarification required")
        sys.exit(2)
    elif verdict == "MATCHES_INTENT":
        print("\nMATCHES_INTENT - code matches original request")
    else:
        print(f"\nTRANSLATOR REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
