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
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from tools.agent_runner_common import run_agent_prompt, sanitize_files

from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    HARD_GATE_AGENTS,
    agent_passed,
    extract_verdict_secure,
    load_agent_prompt_with_contract,
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

COMMENT_SNIPPET_CHARS_DEFAULT = 1000
ARTIFACT_MAX_CHARS_DEFAULT = 50000


def truncate_text(text: str, limit: int) -> tuple[str, bool]:
    """Truncate text with an explicit marker so artifacts remain bounded."""
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    marker = f"\n\n[...truncated at {limit} of {len(text)} chars...]\n"
    keep = max(0, limit - len(marker))
    return text[:keep] + marker, True


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

def _evaluate(agent_name: str, output: str) -> tuple[str, bool, bool, str]:
    """Extract verdict + compliance from agent output."""
    verdict = extract_verdict_secure(output, agent_name=agent_name)
    passed = agent_passed(agent_name, verdict)
    is_compliant, compliance_error, _ = validate_compliance(
        output, verify_files=True, verify_code=True
    )
    if not is_compliant:
        passed = False
    return verdict, passed, is_compliant, compliance_error


async def run_agent(
    agent_name: str,
    files: list[str],
    model_override: str | None = None,
) -> dict:
    """Run a single agent and return result dict."""

    prompt_text = load_agent_prompt_with_contract(agent_name)
    safe_files = sanitize_files(files)
    file_list = ", ".join(safe_files)

    ci_instructions = (
        "Be CONCISE. This is a CI review - focus on critical issues only.\n"
        "Produce a brief report (max 500 words) following your format."
    )

    result_text = await run_agent_prompt(
        agent_name=agent_name,
        prompt_text=prompt_text,
        action_line=f"Review these files: {file_list}",
        task_instructions=ci_instructions,
        model_override=model_override,
        max_turns=20,
    )

    verdict, passed, is_compliant, compliance_error = _evaluate(agent_name, result_text)
    retried = False

    # One retry for malformed outputs (UNKNOWN verdict or non-compliant format).
    if verdict == "UNKNOWN" or not is_compliant:
        retried = True
        retry_instructions = (
            f"{ci_instructions}\n\n"
            "IMPORTANT RETRY REQUIREMENTS:\n"
            "- You MUST include an explicit `VERDICT: <TOKEN>` line.\n"
            "- Every finding MUST include FINDING/FILE/LINES/CODE/VERIFIED fields.\n"
            "- Use only evidence from files you actually read."
        )
        retry_text = await run_agent_prompt(
            agent_name=agent_name,
            prompt_text=prompt_text,
            action_line=f"Review these files: {file_list}",
            task_instructions=retry_instructions,
            model_override=model_override,
            max_turns=20,
        )
        retry_verdict, retry_passed, retry_compliant, retry_error = _evaluate(agent_name, retry_text)
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
        "output": result_text,
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

def _build_summary_table(
    results: list[dict],
) -> tuple[list[str], list[dict], list[dict]]:
    """Build the shared summary table rows + classify failures.

    Returns (table_lines, hard_failures, soft_failures).
    """
    lines = [
        "| Agent | Gate | Verdict | Status |",
        "|-------|------|---------|--------|",
    ]
    hard_failures = []
    soft_failures = []
    for result in results:
        gate = "Hard" if result.get("is_hard_gate") else "Soft"
        if result["passed"]:
            status = "✅ Pass"
        elif result.get("is_hard_gate"):
            status = "❌ Block"
            hard_failures.append(result)
        else:
            status = "⚠️ Warn"
            soft_failures.append(result)
        lines.append(f"| {result['name']} | {gate} | {result['verdict']} | {status} |")
    return lines, hard_failures, soft_failures


def _result_label(result: dict) -> str:
    """Agent name with optional failure/warning badge."""
    label = result["name"]
    if not result["passed"] and result.get("is_hard_gate"):
        label += " ❌"
    elif not result["passed"]:
        label += " ⚠️"
    return label


def _summary_heading(hard_failures: list[dict], soft_failures: list[dict]) -> str:
    if hard_failures:
        return f"### ❌ Hard-gate issues found ({len(hard_failures)} blocker(s))"
    if soft_failures:
        return f"### ⚠️ Soft-gate warnings ({len(soft_failures)} warning(s))"
    return "### ✅ All checks passed"


def generate_ci_report(
    analysis: DiffAnalysis,
    results: list[dict],
    snippet_chars: int = COMMENT_SNIPPET_CHARS_DEFAULT,
) -> str:
    """Generate a CI-friendly review report."""

    table_rows, hard_failures, soft_failures = _build_summary_table(results)

    lines = [
        "## 🤖 RCX Automated Review",
        "",
        f"**Scope:** {analysis.summary}",
        f"**Agents:** {', '.join(analysis.agents_to_run)}",
        "",
        "### Summary",
        "",
        *table_rows,
        "",
        _summary_heading(hard_failures, soft_failures),
    ]

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
            label = _result_label(result)
            snippet, snippet_truncated = truncate_text(result["output"], snippet_chars)
            lines.append(f"#### {label}")
            lines.append("")
            if snippet_truncated:
                lines.append(
                    f"_Snippet truncated for PR readability (first {snippet_chars} chars)._"
                )
                lines.append("")
            lines.append("```")
            lines.append(snippet)
            lines.append("```")
            lines.append("")

        lines.append("</details>")
    else:
        lines.append("")

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by RCX CI Review at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")

    return "\n".join(lines)


def generate_full_report(
    analysis: DiffAnalysis,
    results: list[dict],
    artifact_max_chars: int = ARTIFACT_MAX_CHARS_DEFAULT,
) -> str:
    """Generate a full report artifact with larger (capped) agent outputs."""
    table_rows, hard_failures, soft_failures = _build_summary_table(results)

    lines = [
        "## 🤖 RCX Automated Review (Full Agent Outputs)",
        "",
        f"**Scope:** {analysis.summary}",
        f"**Agents:** {', '.join(analysis.agents_to_run)}",
        f"**Per-agent output cap:** {artifact_max_chars} chars",
        "",
        "### Summary",
        "",
        *table_rows,
        "",
        _summary_heading(hard_failures, soft_failures),
        "",
    ]

    for result in results:
        label = _result_label(result)
        output_text, output_truncated = truncate_text(result.get("output", ""), artifact_max_chars)

        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"- `verdict`: `{result['verdict']}`")
        lines.append(f"- `passed`: `{result['passed']}`")
        lines.append(f"- `is_compliant`: `{result['is_compliant']}`")
        lines.append(f"- `retried`: `{result['retried']}`")
        if result.get("compliance_error"):
            lines.append(f"- `compliance_error`: `{result['compliance_error']}`")
        lines.append(f"- `output_chars`: `{len(result.get('output', ''))}`")
        if output_truncated:
            lines.append(
                f"- `output_truncated`: `true` (stored first {artifact_max_chars} chars)"
            )
        lines.append("")
        lines.append("```")
        lines.append(output_text)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by RCX CI Review at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    return "\n".join(lines)


def build_results_artifact(
    analysis: DiffAnalysis,
    results: list[dict],
    artifact_max_chars: int = ARTIFACT_MAX_CHARS_DEFAULT,
) -> dict:
    """Create structured JSON artifact with truncation metadata."""
    payload = {
        "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": {
            "summary": analysis.summary,
            "risk_level": analysis.risk_level,
            "files_changed": analysis.files_changed,
            "lines_added": analysis.lines_added,
            "lines_removed": analysis.lines_removed,
            "agents_to_run": analysis.agents_to_run,
        },
        "artifact_limits": {
            "per_agent_output_chars": artifact_max_chars,
        },
        "results": [],
    }

    for result in results:
        output_full = result.get("output", "")
        output_capped, output_truncated = truncate_text(output_full, artifact_max_chars)
        item = deepcopy(result)
        item["output_original_chars"] = len(output_full)
        item["output_truncated"] = output_truncated
        item["output"] = output_capped
        payload["results"].append(item)

    return payload


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
        "--full-output",
        type=Path,
        help="Save full (larger) agent output report to file (defaults near --output)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Save structured JSON artifact with per-agent outputs (defaults near --output)",
    )
    parser.add_argument(
        "--comment-snippet-chars",
        type=int,
        default=COMMENT_SNIPPET_CHARS_DEFAULT,
        help=f"Per-agent snippet size for PR comment/report (default: {COMMENT_SNIPPET_CHARS_DEFAULT})",
    )
    parser.add_argument(
        "--artifact-max-chars",
        type=int,
        default=ARTIFACT_MAX_CHARS_DEFAULT,
        help=f"Per-agent output cap for full artifacts (default: {ARTIFACT_MAX_CHARS_DEFAULT})",
    )
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for all CI review agents (default uses per-agent policy)",
    )

    args = parser.parse_args()

    if args.comment_snippet_chars <= 0:
        print("⚠️ --comment-snippet-chars must be > 0")
        sys.exit(1)
    if args.artifact_max_chars <= 0:
        print("⚠️ --artifact-max-chars must be > 0")
        sys.exit(1)

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
    report = generate_ci_report(
        analysis,
        results,
        snippet_chars=args.comment_snippet_chars,
    )
    full_report = generate_full_report(
        analysis,
        results,
        artifact_max_chars=args.artifact_max_chars,
    )
    results_artifact = build_results_artifact(
        analysis,
        results,
        artifact_max_chars=args.artifact_max_chars,
    )

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Save report
    if args.output:
        def _validate_output_path(path_arg: Path) -> Path:
            # Security: Validate output path to prevent arbitrary file write.
            try:
                resolved = path_arg.resolve()
                cwd = Path.cwd().resolve()
                if not resolved.is_relative_to(cwd):
                    print(f"\n⚠️ Output path must be within project directory: {path_arg}")
                    sys.exit(1)
                return resolved
            except (OSError, ValueError) as e:
                print(f"\n⚠️ Invalid output path {path_arg}: {e}")
                sys.exit(1)

        summary_path = _validate_output_path(args.output)
        full_path_arg = args.full_output or args.output.with_name("review-report-full.md")
        json_path_arg = args.json_output or args.output.with_name("review-results.json")
        full_path = _validate_output_path(full_path_arg)
        json_path = _validate_output_path(json_path_arg)

        summary_path.write_text(report)
        full_path.write_text(full_report)
        json_path.write_text(json.dumps(results_artifact, indent=2), encoding="utf-8")
        print(f"\n📄 Summary report saved to: {summary_path}")
        print(f"📄 Full report saved to: {full_path}")
        print(f"📄 JSON artifact saved to: {json_path}")

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
