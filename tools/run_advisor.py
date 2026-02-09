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
import argparse
import anyio
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from tools.agent_runner_common import (
    StandardFileRunnerConfig,
    exit_with_code,
    finalize_standard_result,
    print_standard_runner_footer,
    run_agent_prompt,
)
from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    load_agent_prompt_with_contract,
)

ADVISOR_PROMPT = load_agent_prompt_with_contract("advisor")
CONFIG = StandardFileRunnerConfig(
    agent_name="advisor",
    parser_description="Run RCX advisor agent on a strategic problem.",
    files_help="N/A",
    run_message_prefix="Advising on",
    action_line_prefix="evaluate this problem",
    task_instructions=(
        "Read relevant files (STATUS.md, TASKS.md, and any context files). "
        "Provide multiple options with trade-off analysis. "
        "Produce an advisor report following the format in your instructions."
    ),
    max_turns=25,
    verdict_messages={
        "NEEDS_MORE_CONTEXT": ("NEEDS_MORE_CONTEXT - provide more information", 2),
        "FLAWED_APPROACH": ("ADVISOR FLAGS ISSUES (FLAWED_APPROACH)", 2),
        "HIDDEN_CONSTRAINTS": ("ADVISOR FLAGS ISSUES (HIDDEN_CONSTRAINTS)", 2),
        "VIABLE_PATH": ("VIABLE_PATH - assumptions survived advisor attacks", 0),
    },
    default_message_prefix="ADVISOR REVIEW COMPLETE",
)


async def run_advisor(
    problem: str,
    context_files: list[str] | None = None,
    web_search: bool = False,
    model_override: str | None = None,
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

    action_line = f'The team is stuck on this problem: "{problem}"{file_context}'
    task_instructions = (
        f"{CONFIG.task_instructions}\n"
        f"{'Also search the web for how other systems solve similar problems.' if web_search else ''}"
    )
    prompt_text = ADVISOR_PROMPT + web_instructions
    tools = ["Read", "Grep", "Glob"]
    if web_search:
        tools.append("WebSearch")

    return await run_agent_prompt(
        agent_name=CONFIG.agent_name,
        prompt_text=prompt_text,
        action_line=action_line,
        task_instructions=task_instructions,
        model_override=model_override,
        allowed_tools=tools,
        max_turns=30 if web_search else CONFIG.max_turns,
    )


async def main():
    parser = argparse.ArgumentParser(
        description="Run RCX advisor agent on a strategic problem."
    )
    parser.add_argument("problem", help="Problem statement for advisor")
    parser.add_argument("--files", nargs="*", default=[], help="Context files")
    parser.add_argument("--web", action="store_true", help="Enable web search tool")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for advisor (default uses policy)",
    )
    args = parser.parse_args()
    problem = args.problem
    context_files = args.files
    web_search = args.web

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
        model_override=args.model,
    )

    print(result)
    print_standard_runner_footer()
    exit_with_code(finalize_standard_result(CONFIG, result))


if __name__ == "__main__":
    anyio.run(main)
