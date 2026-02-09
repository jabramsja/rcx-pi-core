#!/usr/bin/env python3
"""
RCX CI Review Agent - Automated PR review for GitHub Actions.

This agent is designed to run in CI and:
1. Analyzes the PR diff to understand what changed
2. Auto-selects appropriate review depth
3. Runs relevant agents in parallel
4. Posts a synthesized review comment to the PR

Usage:
    # In GitHub Actions workflow
    python tools/run_ci_review.py --pr-number 123

    # Local testing
    python tools/run_ci_review.py --local

Environment variables:
    GITHUB_TOKEN     - GitHub token for posting comments
    GITHUB_REPOSITORY - Owner/repo (e.g., "myorg/myrepo")
    PR_NUMBER        - PR number (alternative to --pr-number)
"""

import sys
import os
import json
import subprocess
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    HARD_GATE_AGENTS,
    agent_passed,
    build_sdk_options,
    extract_text_from_message,
    extract_verdict_secure,
    load_agent_prompt_with_contract,
    resolve_agent_model,
    validate_compliance,
)


# =============================================================================
# Configuration
# =============================================================================

# Risk levels based on file patterns
HIGH_RISK_PATTERNS = [
    "selfhost/step_mu.py",
    "selfhost/kernel.py",
    "selfhost/eval_seed.py",
    "mu/substrate/",
    "mu/closures/",
]

MEDIUM_RISK_PATTERNS = [
    "selfhost/",
    "mu/",
    "tests/structural/",
]

# Agents by risk level
RISK_AGENTS = {
    "high": ["verifier", "adversary", "expert", "structural-proof", "grounding", "fuzzer"],
    "medium": ["verifier", "adversary", "expert", "structural-proof"],
    "low": ["verifier", "expert"],
}


# =============================================================================
# Diff Analysis
# =============================================================================

@dataclass
class DiffAnalysis:
    """Analysis of a PR diff."""
    files_changed: list[str]
    lines_added: int
    lines_removed: int
    risk_level: str
    agents_to_run: list[str]
    summary: str


def analyze_diff(pr_number: int | None = None) -> DiffAnalysis:
    """Analyze the diff to determine review scope."""

    # Get changed files
    if pr_number:
        cmd = ["gh", "pr", "diff", str(pr_number), "--name-only"]
    else:
        cmd = ["git", "diff", "--name-only", "main...HEAD"]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    # Security: Check for command failure - don't fail silently
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get diff: {result.stderr}")
    files = [f for f in result.stdout.strip().split('\n') if f]

    # Filter to relevant files
    relevant_files = [f for f in files if f.endswith(('.py', '.json', '.js'))]

    # Get line counts
    if pr_number:
        stat_cmd = ["gh", "pr", "diff", str(pr_number), "--stat"]
    else:
        stat_cmd = ["git", "diff", "--stat", "main...HEAD"]

    stat_result = subprocess.run(stat_cmd, capture_output=True, text=True, timeout=30)
    # Note: stat failure is non-critical - we can proceed with 0 line counts

    lines_added = 0
    lines_removed = 0
    for line in stat_result.stdout.split('\n'):
        if '+' in line and '-' in line:
            # Parse "X insertions(+), Y deletions(-)"
            parts = line.split(',')
            for part in parts:
                if 'insertion' in part:
                    try:
                        lines_added = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                if 'deletion' in part:
                    try:
                        lines_removed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass

    # Determine risk level
    risk_level = "low"
    for f in relevant_files:
        for pattern in HIGH_RISK_PATTERNS:
            if pattern in f:
                risk_level = "high"
                break
        if risk_level == "high":
            break
        for pattern in MEDIUM_RISK_PATTERNS:
            if pattern in f:
                risk_level = "medium"

    # Override for large changes
    if lines_added + lines_removed > 500:
        risk_level = "high"
    elif lines_added + lines_removed > 100 and risk_level == "low":
        risk_level = "medium"

    agents = RISK_AGENTS[risk_level]

    summary = f"{len(relevant_files)} files, +{lines_added}/-{lines_removed} lines, {risk_level} risk"

    return DiffAnalysis(
        files_changed=relevant_files,
        lines_added=lines_added,
        lines_removed=lines_removed,
        risk_level=risk_level,
        agents_to_run=agents,
        summary=summary,
    )


# =============================================================================
# Agent Runner (simplified from run_review.py)
# =============================================================================

async def run_agent(
    agent_name: str,
    files: list[str],
    model_override: str | None = None,
) -> dict:
    """Run a single agent and return result dict."""

    prompt_text = load_agent_prompt_with_contract(agent_name)
    agent_model = resolve_agent_model(agent_name, model_override)

    # Security: Sanitize file paths to prevent prompt injection via newlines
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:200] for f in files[:20]]
    file_list = ", ".join(safe_files)  # Limit for context
    prompt = f"""You are the RCX {agent_name.replace('-', ' ').title()} Agent.

{prompt_text}

---

Review these files: {file_list}

Be CONCISE. This is a CI review - focus on critical issues only.
Produce a brief report (max 500 words) following your format.
"""

    async def _run_once(run_prompt: str) -> str:
        result_text_local = ""
        fragments_local: list[str] = []
        try:
            async for message in query(
                prompt=run_prompt,
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
                    fragments_local.append(extracted)
                if hasattr(message, 'result') and message.result:
                    result_text_local = message.result
        except Exception as e:
            result_text_local = f"Error: {e}"

        if not result_text_local and fragments_local:
            result_text_local = "\n".join(dict.fromkeys(fragments_local))
        return result_text_local

    def _evaluate(output: str) -> tuple[str, bool, bool, str]:
        verdict_local = extract_verdict_secure(output, agent_name=agent_name)
        passed_local = agent_passed(agent_name, verdict_local)
        is_compliant_local, compliance_error_local, _ = validate_compliance(
            output, verify_files=True, verify_code=True
        )
        if not is_compliant_local:
            passed_local = False
        return verdict_local, passed_local, is_compliant_local, compliance_error_local

    result_text = await _run_once(prompt)
    verdict, passed, is_compliant, compliance_error = _evaluate(result_text)
    retried = False

    # One retry for malformed outputs (UNKNOWN verdict or non-compliant format).
    if verdict == "UNKNOWN" or not is_compliant:
        retried = True
        retry_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT RETRY REQUIREMENTS:\n"
            "- You MUST include an explicit `VERDICT: <TOKEN>` line.\n"
            "- Every finding MUST include FINDING/FILE/LINES/CODE/VERIFIED fields.\n"
            "- Use only evidence from files you actually read.\n"
        )
        retry_text = await _run_once(retry_prompt)
        retry_verdict, retry_passed, retry_compliant, retry_error = _evaluate(retry_text)
        # Keep retry outcome if it produced any output.
        if retry_text.strip():
            result_text = retry_text
            verdict = retry_verdict
            passed = retry_passed
            is_compliant = retry_compliant
            compliance_error = retry_error

    is_hard_gate = agent_name in HARD_GATE_AGENTS
    blocks_merge = is_hard_gate and (not passed)

    return {
        "name": agent_name,
        "verdict": verdict,
        "passed": passed,
        "is_hard_gate": is_hard_gate,
        "blocks_merge": blocks_merge,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error,
        "retried": retried,
        "output": result_text[:2000],  # Truncate for comment size
    }


async def run_agents_parallel(
    agents: list[str],
    files: list[str],
    model_override: str | None = None,
) -> list[dict]:
    """Run multiple agents in parallel."""
    tasks = [run_agent(agent, files, model_override=model_override) for agent in agents]
    return await asyncio.gather(*tasks)


# =============================================================================
# Report Generation
# =============================================================================

def generate_ci_report(analysis: DiffAnalysis, results: list[dict]) -> str:
    """Generate a CI-friendly review report."""

    lines = [
        "## 🤖 RCX Automated Review",
        "",
        f"**Scope:** {analysis.summary}",
        f"**Agents:** {', '.join(analysis.agents_to_run)}",
        "",
        "### Summary",
        "",
        "| Agent | Gate | Verdict | Status |",
        "|-------|------|---------|--------|",
    ]

    hard_failures = [r for r in results if r.get("is_hard_gate") and not r.get("passed")]
    soft_failures = [r for r in results if (not r.get("is_hard_gate")) and not r.get("passed")]
    for result in results:
        gate = "Hard" if result.get("is_hard_gate") else "Soft"
        if result["passed"]:
            status = "✅ Pass"
        elif result.get("is_hard_gate"):
            status = "❌ Block"
        else:
            status = "⚠️ Warn"
        lines.append(f"| {result['name']} | {gate} | {result['verdict']} | {status} |")

    lines.append("")

    if not hard_failures and not soft_failures:
        lines.append("### ✅ All checks passed")
    elif hard_failures:
        lines.append(f"### ❌ Hard-gate issues found ({len(hard_failures)} blocker(s))")
    else:
        lines.append(f"### ⚠️ Soft-gate warnings ({len(soft_failures)} warning(s))")

    if soft_failures and not hard_failures:
        lines.append("")
        lines.append("_Soft-gate warnings do not block CI merge._")

    # Always show agent findings (even when CI passes) so reviewers can
    # see the reasoning behind verdicts like COULD_SIMPLIFY.
    agents_with_output = [r for r in results if r.get("output", "").strip()]
    if agents_with_output:
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand agent findings</summary>")
        lines.append("")

        for result in agents_with_output:
            label = result["name"]
            if not result["passed"] and result.get("is_hard_gate"):
                label += " ❌"
            elif not result["passed"]:
                label += " ⚠️"
            lines.append(f"#### {label}")
            lines.append("")
            lines.append("```")
            lines.append(result["output"][:1000])
            lines.append("```")
            lines.append("")

        lines.append("</details>")
    else:
        lines.append("")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by RCX CI Review at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")

    return "\n".join(lines)


# =============================================================================
# GitHub Integration
# =============================================================================

def post_pr_comment(pr_number: int, body: str) -> bool:
    """Post a comment to a PR using gh CLI."""
    try:
        # First, check if we already have a comment and delete it
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "comments"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            comments = json.loads(result.stdout).get("comments", [])
            for comment in comments:
                if "RCX Automated Review" in comment.get("body", ""):
                    # Delete old comment
                    # Security: Validate comment_id is numeric to prevent injection
                    comment_id = comment.get("id")
                    if comment_id and str(comment_id).isdigit():
                        # Use gh api which handles escaping properly
                        subprocess.run(
                            ["gh", "api", "-X", "DELETE", f"repos/:owner/:repo/issues/comments/{comment_id}"],
                            capture_output=True,
                            timeout=30
                        )

        # Post new comment
        result = subprocess.run(
            ["gh", "pr", "comment", str(pr_number), "--body", body],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to post comment: {e}")
        return False


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description="RCX CI Review Agent")
    parser.add_argument("--pr-number", type=int, help="PR number to review")
    parser.add_argument("--local", action="store_true", help="Local mode (no GitHub posting)")
    parser.add_argument("--post-comment", action="store_true", help="Post comment to PR")
    parser.add_argument("--output", "-o", type=Path, help="Save report to file")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for all CI review agents (default uses per-agent policy)",
    )

    args = parser.parse_args()

    # Get PR number from env if not specified
    pr_number = args.pr_number or os.environ.get("PR_NUMBER")
    if pr_number:
        try:
            pr_number = int(pr_number)
        except (ValueError, TypeError):
            print(f"⚠️ Invalid PR_NUMBER: {pr_number}. Running without PR context.")
            pr_number = None

    print("=" * 60)
    print("RCX CI REVIEW")
    print("=" * 60)

    # Analyze diff
    print("\n📊 Analyzing changes...")
    analysis = analyze_diff(pr_number)
    print(f"   {analysis.summary}")
    print(f"   Files: {', '.join(analysis.files_changed[:5])}")
    if len(analysis.files_changed) > 5:
        print(f"   ... and {len(analysis.files_changed) - 5} more")

    if not analysis.files_changed:
        print("\n✅ No relevant files changed. Skipping review.")
        sys.exit(0)

    # Run agents
    print(f"\n🤖 Running {len(analysis.agents_to_run)} agents in parallel...")
    results = await run_agents_parallel(
        analysis.agents_to_run,
        analysis.files_changed,
        model_override=args.model,
    )

    # Generate report
    report = generate_ci_report(analysis, results)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Save report
    if args.output:
        # Security: Validate output path to prevent arbitrary file write
        try:
            output_path = args.output.resolve()
            cwd = Path.cwd().resolve()
            if not output_path.is_relative_to(cwd):
                print(f"\n⚠️ Output path must be within project directory: {args.output}")
                sys.exit(1)
        except (OSError, ValueError) as e:
            print(f"\n⚠️ Invalid output path: {e}")
            sys.exit(1)
        args.output.write_text(report)
        print(f"\n📄 Report saved to: {args.output}")

    # Post to PR
    if args.post_comment and pr_number:
        print(f"\n📤 Posting comment to PR #{pr_number}...")
        if post_pr_comment(pr_number, report):
            print("   ✅ Comment posted")
        else:
            print("   ❌ Failed to post comment")

    # Exit code
    hard_failures = [r for r in results if r.get("is_hard_gate") and not r["passed"]]
    soft_failures = [r for r in results if (not r.get("is_hard_gate")) and not r["passed"]]
    if hard_failures:
        print(f"\n❌ {len(hard_failures)} hard-gate agent(s) reported blocking issues")
        sys.exit(1)
    if soft_failures:
        print(f"\n⚠️ {len(soft_failures)} soft-gate warning(s) reported (non-blocking)")
    print("\n✅ CI review completed")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
