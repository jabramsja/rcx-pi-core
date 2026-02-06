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

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

from tools.shared_agent_utils import extract_verdict_secure, validate_compliance


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

def load_agent_prompt(name: str) -> str:
    """Load agent prompt from tools/agents/{name}_prompt.md"""
    path = Path(f"tools/agents/{name}_prompt.md")
    if path.exists():
        return path.read_text()
    raise FileNotFoundError(f"Agent prompt not found: {path}")


async def run_agent(agent_name: str, files: list[str]) -> dict:
    """Run a single agent and return result dict."""

    prompt_text = load_agent_prompt(agent_name.replace("-", "_"))

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

    result_text = ""
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob"],
                max_turns=20,
            )
        ):
            if hasattr(message, 'result') and message.result:
                result_text = message.result
    except Exception as e:
        result_text = f"Error: {e}"

    # Extract verdict using secure VERDICT: marker parsing (shared_agent_utils)
    verdict = extract_verdict_secure(result_text, agent_name=agent_name)

    # NEEDS_HARDENING is NOT a pass - requires security fixes
    passed = verdict in {"APPROVE", "SECURE", "MINIMAL", "PROVEN", "GROUNDED", "ROBUST", "COULD_SIMPLIFY", "PARTIALLY_GROUNDED"}

    # Compliance validation (shared_agent_utils returns 3-tuple)
    is_compliant, compliance_error, _ = validate_compliance(
        result_text, verify_files=True, verify_code=True
    )
    if not is_compliant:
        passed = False  # Compliance failure = not passed

    return {
        "name": agent_name,
        "verdict": verdict,
        "passed": passed,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error,
        "output": result_text[:2000],  # Truncate for comment size
    }


async def run_agents_parallel(agents: list[str], files: list[str]) -> list[dict]:
    """Run multiple agents in parallel."""
    tasks = [run_agent(agent, files) for agent in agents]
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
        "| Agent | Verdict | Status |",
        "|-------|---------|--------|",
    ]

    all_passed = True
    for result in results:
        status = "✅" if result["passed"] else "❌"
        lines.append(f"| {result['name']} | {result['verdict']} | {status} |")
        if not result["passed"]:
            all_passed = False

    lines.append("")

    if all_passed:
        lines.append("### ✅ All checks passed")
    else:
        lines.append("### ❌ Issues found")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Click to expand findings</summary>")
        lines.append("")

        for result in results:
            if not result["passed"]:
                lines.append(f"#### {result['name']}")
                lines.append("")
                lines.append("```")
                lines.append(result["output"][:1000])
                lines.append("```")
                lines.append("")

        lines.append("</details>")

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
    results = await run_agents_parallel(analysis.agents_to_run, analysis.files_changed)

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
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n❌ {len(failed)} agent(s) reported issues")
        sys.exit(1)
    else:
        print("\n✅ All agents passed")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
