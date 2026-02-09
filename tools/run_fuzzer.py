#!/usr/bin/env python3
"""
Run the RCX fuzzer agent on specified files.

This agent generates Property-Based Tests using Hypothesis to smash code
with 1000+ random inputs. Catches edge cases that unit tests miss.

Usage:
    python tools/run_fuzzer.py rcx_pi/selfhost/eval_seed.py
    python tools/run_fuzzer.py rcx_pi/selfhost/mu_type.py rcx_pi/selfhost/match_mu.py
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

FUZZER_PROMPT = load_agent_prompt_with_contract("fuzzer")


async def run_fuzzer(files: list[str], model_override: str | None = None) -> str:
    """Run the fuzzer agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    agent_model = resolve_agent_model("fuzzer", model_override)
    prompt = f"""You are the RCX Fuzzer Agent. Your instructions are:

{FUZZER_PROMPT}

---

Now fuzz these files: {file_list}

Read each file and identify fuzz targets. Generate Property-Based Tests using Hypothesis.
Produce a fuzzer report following the format in your instructions.
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
        description="Run RCX fuzzer agent on specified files."
    )
    parser.add_argument("files", nargs="+", help="Files to review")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for fuzzer (default uses policy)",
    )
    args = parser.parse_args()

    files = args.files
    print(f"Running fuzzer on: {', '.join(files)}")
    print("=" * 60)

    result = await run_fuzzer(files, model_override=args.model)

    print(result)
    print("=" * 60)

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, error, _ = validate_compliance(result)
    if not is_compliant:
        print(f"\n⚠️  COMPLIANCE FAILURE: {error}")
        print("Agent output did not meet AgentGuardrails.v0 requirements.")
        sys.exit(3)

    # Check verdict using secure marker-based extraction (shared_agent_utils)
    verdict = extract_verdict_secure(result, agent_name="fuzzer")
    if verdict == "BROKEN":
        print("\nBROKEN - consistent failures found")
        sys.exit(1)
    elif verdict == "FRAGILE":
        print("\nFRAGILE - flaky tests detected")
        sys.exit(2)
    elif verdict == "ROBUST":
        print("\nROBUST - all property tests pass")
    elif verdict == "NOT_EXECUTED":
        print("\nNOT_EXECUTED - fuzzer could not run tests")
        sys.exit(2)
    else:
        print(f"\nFUZZER REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
