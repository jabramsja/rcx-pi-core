#!/usr/bin/env python3
"""
Run the RCX advisor agent on a problem.

This agent provides strategic advice when stuck - multiple options,
trade-off analysis, and creative solutions.

Now with WEB SEARCH: Can search for how other systems solve similar problems.

Usage:
    python tools/run_advisor.py "How should we represent bindings structurally?"
    python tools/run_advisor.py "Multiple approaches exist for X, which should we choose?"
    python tools/run_advisor.py "How do other interpreters handle meta-circularity?" --web
"""

import sys
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

from tools.shared_agent_utils import (
    extract_text_from_message,
    extract_verdict_secure,
    load_agent_prompt_with_contract,
    validate_compliance,
)

ADVISOR_PROMPT = load_agent_prompt_with_contract("advisor")


async def run_advisor(
    problem: str,
    context_files: list[str] | None = None,
    web_search: bool = False,
) -> str:
    """Run the advisor agent on a problem.

    Args:
        problem: The problem description
        context_files: Optional list of files to consider
        web_search: If True, enable web search for external solutions
    """

    file_context = ""
    if context_files:
        # Security: Sanitize file paths to prevent prompt injection via newlines
        safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in context_files[:20]]
        file_context = f"\n\nRelevant files to consider: {', '.join(safe_files)}"

    web_instructions = ""
    if web_search:
        web_instructions = """

## Web Search Available

You have access to WebSearch. USE IT when:
- The problem involves patterns used by other systems (interpreters, compilers, VMs)
- Looking for academic/industry solutions to similar problems
- Need examples of how others solved this type of challenge
- The codebase alone doesn't have enough context

Search for relevant papers, blog posts, GitHub repos, or documentation.
Synthesize findings into RCX-relevant options.
"""

    prompt = f"""You are the RCX Advisor Agent. Your instructions are:

{ADVISOR_PROMPT}
{web_instructions}
---

The team is stuck on this problem: "{problem}"{file_context}

Read relevant files (STATUS.md, TASKS.md, and any context files).
{"Also search the web for how other systems solve similar problems." if web_search else ""}
Provide multiple options with trade-off analysis.
Produce an advisor report following the format in your instructions.
"""

    # Include WebSearch if enabled
    tools = ["Read", "Grep", "Glob"]
    if web_search:
        tools.append("WebSearch")

    result_text = ""
    fragments: list[str] = []

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            allowed_tools=tools,
            max_turns=30 if web_search else 25,
        )
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
    if len(sys.argv) < 2:
        print("Usage: python tools/run_advisor.py \"<problem description>\" [--files file1 ...] [--web]")
        print("Example: python tools/run_advisor.py \"How should we represent bindings?\"")
        print("Example: python tools/run_advisor.py \"How do other interpreters handle this?\" --web")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    problem = args[0]
    context_files = []
    web_search = "--web" in args

    if "--files" in args:
        files_idx = args.index("--files")
        # Get files until we hit another flag or end
        for i in range(files_idx + 1, len(args)):
            if args[i].startswith("--"):
                break
            context_files.append(args[i])

    print(f"Advising on: {problem}")
    if context_files:
        print(f"Context files: {', '.join(context_files)}")
    if web_search:
        print("🌐 Web search ENABLED - will search for external solutions")
    print("=" * 60)

    result = await run_advisor(
        problem,
        context_files if context_files else None,
        web_search=web_search,
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
    verdict = extract_verdict_secure(result, agent_name="advisor")
    if verdict == "NEEDS_MORE_CONTEXT":
        print("\nNEEDS_MORE_CONTEXT - provide more information")
        sys.exit(2)
    elif verdict in {"FLAWED_APPROACH", "HIDDEN_CONSTRAINTS"}:
        print(f"\nADVISOR FLAGS ISSUES ({verdict})")
        sys.exit(2)
    elif verdict == "VIABLE_PATH":
        print("\nVIABLE_PATH - assumptions survived advisor attacks")
    else:
        print(f"\nADVISOR REVIEW COMPLETE (verdict: {verdict})")


if __name__ == "__main__":
    anyio.run(main)
