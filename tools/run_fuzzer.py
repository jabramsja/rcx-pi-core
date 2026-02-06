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
import anyio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import extract_verdict_secure, validate_compliance

FUZZER_PROMPT = Path("tools/agents/fuzzer_prompt.md").read_text()


async def run_fuzzer(files: list[str]) -> str:
    """Run the fuzzer agent on the specified files."""

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)
    prompt = f"""You are the RCX Fuzzer Agent. Your instructions are:

{FUZZER_PROMPT}

---

Now fuzz these files: {file_list}

Read each file and identify fuzz targets. Generate Property-Based Tests using Hypothesis.
Produce a fuzzer report following the format in your instructions.
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
        print("Usage: python tools/run_fuzzer.py <file1> [file2] ...")
        print("Example: python tools/run_fuzzer.py rcx_pi/selfhost/eval_seed.py")
        sys.exit(1)

    files = sys.argv[1:]
    print(f"Running fuzzer on: {', '.join(files)}")
    print("=" * 60)

    result = await run_fuzzer(files)

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
