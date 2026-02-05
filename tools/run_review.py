#!/usr/bin/env python3
"""
RCX Review Orchestrator - Intelligent multi-agent code review.

This orchestrator runs multiple review agents IN PARALLEL and synthesizes
their findings into a unified report. It's the "one command to rule them all".

Features:
- Parallel execution of compatible agents (3-4x faster than sequential)
- Automatic depth selection based on change size
- Unified compliance validation
- Synthesized report with all findings
- Agent memory: stores findings for regression tracking

Usage:
    # Full review (all 9 agents)
    python tools/run_review.py rcx_pi/selfhost/

    # Quick review (4 core agents only)
    python tools/run_review.py rcx_pi/selfhost/step_mu.py --depth quick

    # PR review (analyzes git diff, auto-selects depth)
    python tools/run_review.py --pr

    # Founder review (adds translator + visualizer)
    python tools/run_review.py rcx_pi/selfhost/ --founder

    # Disable memory (no finding storage)
    python tools/run_review.py rcx_pi/selfhost/ --no-memory

    # Associate findings with a PR
    python tools/run_review.py --pr --pr-number 123

Depth levels:
    quick:  verifier, adversary, expert, structural-proof (4 agents)
    full:   + grounding, fuzzer (6 agents)
    founder: + translator, visualizer (8 agents)
    all:    + advisor (9 agents)

Agent Memory:
    Findings are stored in .agent_memory/findings.json for:
    - Regression checking: warns when reviewing files with previously-fixed issues
    - Learning: track what agents find over time
    - Accountability: link findings to PRs
"""

import sys
import os
import json
import subprocess
import asyncio
import argparse
import re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

# Import agent memory for persistent finding storage
from tools.agent_memory import (
    store_finding,
    load_findings,
)

# Import shared FINDING extraction (single source of truth)
from tools.validate_agent_compliance import extract_finding_blocks


# =============================================================================
# Agent Definitions
# =============================================================================

def load_agent_prompt(name: str) -> str:
    """Load agent prompt from tools/agents/{name}_prompt.md"""
    path = Path(f"tools/agents/{name}_prompt.md")
    if path.exists():
        return path.read_text()
    raise FileNotFoundError(f"Agent prompt not found: {path}")


def create_agent_definitions() -> dict[str, AgentDefinition]:
    """Create all 9 agent definitions with their specialized prompts."""

    return {
        # === HARD GATE AGENTS (must pass for PR approval) ===
        "verifier": AgentDefinition(
            description="Verifies code against North Star invariants. Use for compliance checks.",
            prompt=load_agent_prompt("verifier"),
            tools=["Read", "Grep", "Glob"],
            model="opus"
        ),
        "adversary": AgentDefinition(
            description="Red team agent that tries to break code. Use for security review.",
            prompt=load_agent_prompt("adversary"),
            tools=["Read", "Grep", "Glob"],
            model="opus"
        ),
        "expert": AgentDefinition(
            description="Expert code reviewer for complexity and simplification. Use for quality review.",
            prompt=load_agent_prompt("expert"),
            tools=["Read", "Grep", "Glob"],
            model="opus"
        ),
        "structural-proof": AgentDefinition(
            description="Demands concrete proof of structural claims. Use for projection verification.",
            prompt=load_agent_prompt("structural_proof"),
            tools=["Read", "Grep", "Glob"],
            model="sonnet"
        ),

        # === DEPTH AGENTS (thorough verification) ===
        "grounding": AgentDefinition(
            description="Converts claims into executable tests. Use for test coverage verification.",
            prompt=load_agent_prompt("grounding"),
            tools=["Read", "Grep", "Glob"],
            model="sonnet"
        ),
        "fuzzer": AgentDefinition(
            description="Property-based testing with Hypothesis. Use for edge case discovery.",
            prompt=load_agent_prompt("fuzzer"),
            tools=["Read", "Grep", "Glob"],
            model="sonnet"
        ),

        # === FOUNDER AGENTS (human-readable output) ===
        "translator": AgentDefinition(
            description="Explains code in plain English. Use for founder review.",
            prompt=load_agent_prompt("translator"),
            tools=["Read", "Grep", "Glob"],
            model="sonnet"
        ),
        "visualizer": AgentDefinition(
            description="Creates Mermaid diagrams of structures. Use for visual verification.",
            prompt=load_agent_prompt("visualizer"),
            tools=["Read", "Grep", "Glob"],
            model="sonnet"
        ),

        # === ADVISORY AGENT (non-gating) ===
        "advisor": AgentDefinition(
            description="Strategic advisor for design decisions. Use when stuck.",
            prompt=load_agent_prompt("advisor"),
            tools=["Read", "Grep", "Glob"],
            model="opus"
        ),
    }


# =============================================================================
# Depth Configuration
# =============================================================================

DEPTH_AGENTS = {
    "quick": ["verifier", "adversary", "expert", "structural-proof"],
    "full": ["verifier", "adversary", "expert", "structural-proof", "grounding", "fuzzer"],
    "founder": ["verifier", "adversary", "expert", "structural-proof", "grounding", "fuzzer", "translator", "visualizer"],
    "all": ["verifier", "adversary", "expert", "structural-proof", "grounding", "fuzzer", "translator", "visualizer", "advisor"],
}

# Agents that can run in parallel (no dependencies)
PARALLEL_GROUPS = [
    ["verifier", "adversary", "expert", "structural-proof"],  # Group 1: Core review
    ["grounding", "fuzzer"],                                   # Group 2: Testing
    ["translator", "visualizer"],                              # Group 3: Founder
    ["advisor"],                                               # Group 4: Advisory
]

HARD_GATE_AGENTS = {"verifier", "adversary", "expert", "structural-proof"}


# =============================================================================
# Compliance Validation
# =============================================================================

def validate_compliance(output: str) -> tuple[bool, str, dict]:
    """Run compliance validation on agent output.

    Returns (is_compliant, error_message, metrics).
    """
    try:
        result = subprocess.run(
            ["python3", "tools/validate_agent_compliance.py", "--json", "--strict"],
            input=output,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0 and not result.stdout:
            return False, f"Validator crashed: {result.stderr}", {}

        metrics = json.loads(result.stdout)
        if not metrics.get("compliant", False):
            violations = metrics.get("violations", ["Unknown violation"])
            return False, "; ".join(violations), metrics

        return True, "", metrics
    except subprocess.TimeoutExpired:
        return False, "Validator timeout (>30s)", {}
    except json.JSONDecodeError as e:
        return False, f"Validator returned invalid JSON: {e}", {}
    except Exception as e:
        return False, f"Validation error: {e}", {}


# =============================================================================
# Result Extraction
# =============================================================================

@dataclass
class AgentResult:
    """Result from a single agent run."""
    name: str
    output: str
    verdict: str
    is_compliant: bool
    compliance_error: str
    is_hard_gate: bool
    passed: bool
    findings_stored: int = 0  # Count of findings stored in memory


# =============================================================================
# Finding Extraction (for Agent Memory)
# =============================================================================

def extract_findings_from_output(agent_name: str, output: str, verdict: str) -> list[dict]:
    """Extract structured findings from agent output for memory storage.

    Uses the shared extract_finding_blocks() from validate_agent_compliance.py
    which handles both markdown and indented CODE blocks.
    """
    # Use shared extraction (single source of truth)
    blocks = extract_finding_blocks(output)

    findings = []
    for block in blocks:
        # Parse line number from LINES field (e.g., "123-127" -> 123)
        line = None
        if block.lines:
            try:
                line = int(block.lines.split('-')[0])
            except (ValueError, IndexError):
                pass

        # Determine severity based on verdict
        severity = verdict_to_severity(agent_name, verdict)

        findings.append({
            "message": block.finding,
            "file": block.file_path,
            "line": line,
            "severity": severity,
        })

    return findings


def verdict_to_severity(agent_name: str, verdict: str) -> str:
    """Map agent verdict to finding severity."""
    # Critical verdicts
    if verdict in {"VULNERABLE", "BROKEN", "IMPOSSIBLE_AS_CLAIMED", "THEATER"}:
        return "critical"
    # High severity
    if verdict in {"REQUEST_CHANGES", "OVER_ENGINEERED", "UNPROVEN", "UNGROUNDED", "FRAGILE", "NOT_EXECUTED"}:
        return "high"
    # Medium
    if verdict in {"COULD_SIMPLIFY", "PARTIALLY_GROUNDED", "DEVIATES", "RED_FLAGS", "CONCERNS", "NEEDS_HARDENING"}:
        return "medium"
    # Low/info - passing verdicts
    if verdict in {
        "APPROVE", "SECURE", "MINIMAL", "PROVEN", "GROUNDED", "ROBUST", "CLEAN", "MATCHES_INTENT",
        "NO_STRUCTURAL_CLAIMS", "REQUIRES_CI_VERIFICATION",  # structural-proof passes
        "OPTIONS_PROVIDED", "RECOMMENDATION",  # advisor passes
    }:
        return "info"
    return "medium"


def extract_verdict(agent_name: str, output: str) -> str:
    """Extract verdict from agent output.

    Security fix: Look for explicit VERDICT: markers first to prevent
    spoofing via incidental mentions of verdict words in output text.
    """
    # Verdicts must match what agent prompts actually define
    verdicts = {
        "verifier": ["APPROVE", "REQUEST_CHANGES", "NEEDS_DISCUSSION"],
        "adversary": ["SECURE", "VULNERABLE", "NEEDS_HARDENING"],
        "expert": ["MINIMAL", "COULD_SIMPLIFY", "OVER_ENGINEERED"],
        "structural-proof": [
            "PROVEN", "UNPROVEN", "IMPOSSIBLE_AS_CLAIMED",
            "NO_STRUCTURAL_CLAIMS",  # When no structural claims exist to verify
            "REQUIRES_CI_VERIFICATION",  # Mode B: execution unavailable
        ],
        "grounding": ["GROUNDED", "PARTIALLY_GROUNDED", "UNGROUNDED", "THEATER"],
        "fuzzer": ["ROBUST", "FRAGILE", "BROKEN", "NOT_EXECUTED"],
        "translator": ["MATCHES_INTENT", "DEVIATES", "NEEDS_DISCUSSION"],
        "visualizer": ["CLEAN", "RED_FLAGS"],
        "advisor": ["OPTIONS_PROVIDED", "RECOMMENDATION", "NEEDS_MORE_CONTEXT"],
    }

    valid_verdicts = set(verdicts.get(agent_name, []))
    if not valid_verdicts:
        return "UNKNOWN"

    # Priority 1: Look for explicit VERDICT: or **Verdict:** markers (same line)
    # Pattern: "### Verdict: APPROVE" or "**Verdict:** SECURE"
    verdict_pattern = re.compile(
        r'(?:^|\n)\s*(?:\*\*)?(?:###?\s*)?[Vv][Ee][Rr][Dd][Ii][Cc][Tt](?:\*\*)?[:\s]+(\w+)',
        re.MULTILINE
    )
    for match in verdict_pattern.finditer(output):
        found = match.group(1).upper()
        if found in valid_verdicts:
            return found
        # Check if this is start of a compound verdict
        for v in valid_verdicts:
            if v.startswith(found) or found in v:
                context = output[match.start():match.start()+100]
                if v in context.upper():
                    return v

    # Priority 2: Multi-line verdict (verdict on next line after header)
    # Pattern: "### Verdict\n\n**NO_STRUCTURAL_CLAIMS**" or "### Verdict\nAPPROVE"
    multiline_pattern = re.compile(
        r'(?:^|\n)\s*(?:\*\*)?(?:###?\s*)?[Vv][Ee][Rr][Dd][Ii][Cc][Tt](?:\*\*)?\s*\n+\s*(?:\*\*)?([A-Z_]+)',
        re.MULTILINE
    )
    for match in multiline_pattern.finditer(output):
        found = match.group(1).upper()
        if found in valid_verdicts:
            return found

    # Priority 3: Fallback to substring match in last 500 chars
    tail = output[-500:] if len(output) > 500 else output
    for verdict in verdicts.get(agent_name, []):
        if verdict in tail:
            return verdict

    return "UNKNOWN"


def agent_passed(agent_name: str, verdict: str) -> bool:
    """Determine if an agent's verdict indicates pass.

    Pass verdicts must align with what agent prompts define as acceptable outcomes.
    """
    pass_verdicts = {
        "verifier": {"APPROVE"},
        "adversary": {"SECURE", "NEEDS_HARDENING"},  # NEEDS_HARDENING = soft pass (advisory)
        "expert": {"MINIMAL", "COULD_SIMPLIFY"},
        "structural-proof": {
            "PROVEN",
            "NO_STRUCTURAL_CLAIMS",  # Nothing to verify = pass
            "REQUIRES_CI_VERIFICATION",  # Needs CI, not a failure
        },
        "grounding": {"GROUNDED", "PARTIALLY_GROUNDED"},
        "fuzzer": {"ROBUST"},  # NOT_EXECUTED is NOT a pass
        "translator": {"MATCHES_INTENT"},
        "visualizer": {"CLEAN"},
        "advisor": {"OPTIONS_PROVIDED", "RECOMMENDATION"},
    }
    return verdict in pass_verdicts.get(agent_name, set())


# =============================================================================
# Orchestrator
# =============================================================================

class ReviewOrchestrator:
    """Orchestrates parallel agent execution and result synthesis."""

    def __init__(self, files: list[str], depth: str = "full", verbose: bool = False,
                 use_memory: bool = True, pr_number: int | None = None):
        self.files = files
        self.depth = depth
        self.verbose = verbose
        self.use_memory = use_memory
        self.pr_number = pr_number
        self.agents_to_run = DEPTH_AGENTS.get(depth, DEPTH_AGENTS["full"])
        self.agent_definitions = create_agent_definitions()
        self.results: list[AgentResult] = []
        self.regression_warnings: list[dict] = []
        self.total_findings_stored: int = 0

    async def run_single_agent(self, agent_name: str) -> AgentResult:
        """Run a single agent and return its result."""
        if self.verbose:
            print(f"  Starting {agent_name}...")

        file_list = ", ".join(self.files)
        agent_def = self.agent_definitions[agent_name]

        prompt = f"""You are the RCX {agent_name.replace('-', ' ').title()} Agent.

{agent_def.prompt}

---

Now review these files: {file_list}

Produce a report following the format in your instructions.
"""

        result_text = ""

        try:
            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    allowed_tools=["Read", "Grep", "Glob"],
                    max_turns=30,
                )
            ):
                if hasattr(message, 'result') and message.result:
                    result_text = message.result
        except Exception as e:
            result_text = f"AGENT ERROR: {e}"

        # Validate compliance
        is_compliant, compliance_error, _ = validate_compliance(result_text)

        # Extract verdict
        verdict = extract_verdict(agent_name, result_text)
        passed = agent_passed(agent_name, verdict) and is_compliant

        # Store findings in memory (if enabled and findings exist)
        findings_stored = 0
        if self.use_memory and result_text:
            findings = extract_findings_from_output(agent_name, result_text, verdict)
            for finding in findings:
                try:
                    store_finding(
                        agent=agent_name,
                        message=finding["message"],
                        file=finding.get("file"),
                        line=finding.get("line"),
                        severity=finding.get("severity", "info"),
                        pr=self.pr_number,
                    )
                    findings_stored += 1
                except Exception as e:
                    if self.verbose:
                        print(f"    Warning: Failed to store finding: {e}")

        if self.verbose:
            status = "✓" if passed else "✗"
            memory_note = f" ({findings_stored} stored)" if findings_stored else ""
            print(f"  {status} {agent_name}: {verdict}{memory_note}")

        return AgentResult(
            name=agent_name,
            output=result_text,
            verdict=verdict,
            is_compliant=is_compliant,
            compliance_error=compliance_error,
            is_hard_gate=agent_name in HARD_GATE_AGENTS,
            passed=passed,
            findings_stored=findings_stored,
        )

    async def run_agent_group(self, agents: list[str]) -> list[AgentResult]:
        """Run a group of agents in parallel."""
        agents_in_scope = [a for a in agents if a in self.agents_to_run]
        if not agents_in_scope:
            return []

        tasks = [self.run_single_agent(agent) for agent in agents_in_scope]
        return await asyncio.gather(*tasks)

    def check_for_regressions(self) -> list[dict]:
        """Check if any files being reviewed have previously-fixed issues."""
        if not self.use_memory:
            return []

        warnings = []
        all_findings = load_findings()

        # Get fixed findings for files we're reviewing
        fixed_findings = [f for f in all_findings if f.get("fixed")]

        for finding in fixed_findings:
            finding_file = finding.get("file", "")
            if not finding_file:
                continue

            # Check if any of our review files match this fixed finding
            for review_file in self.files:
                if finding_file in review_file or review_file in finding_file:
                    warnings.append({
                        "finding_id": finding.get("id"),
                        "file": finding_file,
                        "message": finding.get("message", ""),
                        "agent": finding.get("agent", ""),
                        "severity": finding.get("severity", "info"),
                    })
                    break

        return warnings

    async def run_all(self) -> list[AgentResult]:
        """Run all agents in parallel groups."""
        print(f"\n{'='*60}")
        print(f"RCX REVIEW ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Files: {', '.join(self.files)}")
        print(f"Depth: {self.depth} ({len(self.agents_to_run)} agents)")
        if self.use_memory:
            print(f"Memory: enabled")
        print(f"{'='*60}\n")

        # Check for regressions before running
        if self.use_memory:
            self.regression_warnings = self.check_for_regressions()
            if self.regression_warnings:
                print(f"⚠️  REGRESSION CHECK: {len(self.regression_warnings)} previously-fixed issue(s) in reviewed files:")
                for w in self.regression_warnings[:5]:  # Show first 5
                    print(f"   #{w['finding_id']} [{w['agent']}] {w['message'][:50]}...")
                if len(self.regression_warnings) > 5:
                    print(f"   ... and {len(self.regression_warnings) - 5} more")
                print()

        all_results = []

        for i, group in enumerate(PARALLEL_GROUPS):
            group_agents = [a for a in group if a in self.agents_to_run]
            if not group_agents:
                continue

            print(f"Phase {i+1}: Running {', '.join(group_agents)} in parallel...")
            group_results = await self.run_agent_group(group_agents)
            all_results.extend(group_results)

            # Check hard gate failures - stop early if critical failure
            hard_gate_failures = [r for r in group_results if r.is_hard_gate and not r.passed]
            if hard_gate_failures and i == 0:  # Only stop after first group
                print(f"\n⚠️  Hard gate failure(s) detected. Stopping early.")
                break

        self.results = all_results
        self.total_findings_stored = sum(r.findings_stored for r in all_results)
        return all_results

    def synthesize_report(self) -> str:
        """Synthesize all agent results into a unified report."""
        lines = [
            f"# RCX Review Report",
            f"",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Files:** {', '.join(self.files)}",
            f"**Depth:** {self.depth}",
        ]

        if self.use_memory:
            lines.append(f"**Findings Stored:** {self.total_findings_stored}")

        lines.extend([
            f"",
            "## Summary",
            "",
        ])

        # Regression warnings (if any)
        if self.regression_warnings:
            lines.append("### ⚠️ Regression Watch")
            lines.append("")
            lines.append("Previously-fixed issues may have regressed in reviewed files:")
            lines.append("")
            lines.append("| ID | Agent | File | Issue |")
            lines.append("|----|-------|------|-------|")
            for w in self.regression_warnings:
                msg = w['message'][:40] + "..." if len(w['message']) > 40 else w['message']
                lines.append(f"| #{w['finding_id']} | {w['agent']} | {w['file']} | {msg} |")
            lines.append("")

        # Summary table
        lines.append("| Agent | Verdict | Status |")
        lines.append("|-------|---------|--------|")

        hard_gate_passed = True
        for result in self.results:
            status = "✅ Pass" if result.passed else "❌ Fail"
            if not result.is_compliant:
                status = "⚠️ Non-compliant"
            gate = " (GATE)" if result.is_hard_gate else ""
            lines.append(f"| {result.name}{gate} | {result.verdict} | {status} |")

            if result.is_hard_gate and not result.passed:
                hard_gate_passed = False

        lines.append("")

        # Overall verdict
        if hard_gate_passed:
            lines.append("## Overall: ✅ APPROVED")
        else:
            lines.append("## Overall: ❌ BLOCKED")
            lines.append("")
            lines.append("Hard gate agent(s) failed. Address findings before merge.")

        lines.append("")

        # Individual reports (collapsed)
        lines.append("## Detailed Reports")
        lines.append("")

        for result in self.results:
            lines.append(f"### {result.name.title()}")
            lines.append("")
            if not result.is_compliant:
                lines.append(f"**⚠️ Compliance Error:** {result.compliance_error}")
                lines.append("")
            lines.append("```")
            # Truncate very long outputs
            output = result.output
            if len(output) > 3000:
                output = output[:3000] + "\n... (truncated)"
            lines.append(output)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def get_exit_code(self) -> int:
        """Get appropriate exit code based on results."""
        # Check compliance failures
        compliance_failures = [r for r in self.results if not r.is_compliant]
        if compliance_failures:
            return 3

        # Check hard gate failures
        hard_gate_failures = [r for r in self.results if r.is_hard_gate and not r.passed]
        if hard_gate_failures:
            return 1

        # Check soft failures
        soft_failures = [r for r in self.results if not r.is_hard_gate and not r.passed]
        if soft_failures:
            return 2

        return 0


# =============================================================================
# Git Integration
# =============================================================================

def get_changed_files() -> list[str]:
    """Get files changed in current branch vs main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            files = [f for f in result.stdout.strip().split('\n') if f]
            # Filter to relevant files
            return [f for f in files if f.endswith('.py') or f.endswith('.json')]
    except Exception:
        pass
    return []


def auto_select_depth(files: list[str]) -> str:
    """Auto-select review depth based on changed files."""
    if not files:
        return "quick"

    core_files = [f for f in files if 'selfhost' in f or 'mu/' in f]

    if len(core_files) > 2:
        return "full"
    return "quick"


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="RCX Review Orchestrator - Intelligent multi-agent code review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Depth levels:
  quick    4 agents: verifier, adversary, expert, structural-proof
  full     6 agents: + grounding, fuzzer
  founder  8 agents: + translator, visualizer
  all      9 agents: + advisor

Examples:
  python tools/run_review.py rcx_pi/selfhost/
  python tools/run_review.py rcx_pi/selfhost/step_mu.py --depth quick
  python tools/run_review.py --pr --depth full
  python tools/run_review.py rcx_pi/selfhost/ --founder --output report.md
"""
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Files or directories to review"
    )
    parser.add_argument(
        "--depth",
        choices=["quick", "full", "founder", "all"],
        default="full",
        help="Review depth (default: full)"
    )
    parser.add_argument(
        "--pr",
        action="store_true",
        help="Review files changed in current PR (git diff vs main)"
    )
    parser.add_argument(
        "--founder",
        action="store_true",
        help="Include founder-friendly output (translator + visualizer)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Write report to file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--rigorous",
        action="store_true",
        help="Rigorous mode: validate reasoning quality, challenge approvals with skeptic"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable agent memory (finding storage and regression checking)"
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        help="PR number to associate with findings (for tracking)"
    )

    args = parser.parse_args()

    # Determine files to review
    if args.pr:
        files = get_changed_files()
        if not files:
            print("No Python/JSON files changed in current branch.")
            sys.exit(0)
        print(f"PR mode: reviewing {len(files)} changed files")
    elif args.files:
        files = args.files
    else:
        print("Error: specify files or use --pr")
        parser.print_help()
        sys.exit(1)

    # Determine depth
    depth = args.depth
    if args.founder:
        depth = "founder"
    if args.pr and depth == "full":
        depth = auto_select_depth(files)
        print(f"Auto-selected depth: {depth}")

    # Run orchestrator
    orchestrator = ReviewOrchestrator(
        files,
        depth=depth,
        verbose=args.verbose,
        use_memory=not args.no_memory,
        pr_number=args.pr_number,
    )
    await orchestrator.run_all()

    # Rigorous mode: validate reasoning and challenge approvals
    if args.rigorous:
        print("\n🔬 RIGOROUS MODE: Validating reasoning quality...")

        from tools.validate_agent_reasoning import validate_reasoning
        from tools.run_skeptic import run_skeptic

        approvals_to_challenge = []

        for result in orchestrator.results:
            # Validate reasoning quality
            reasoning = validate_reasoning(result.output)

            if not reasoning.is_valid:
                print(f"  ⚠️ {result.name}: Reasoning invalid - {reasoning.violations[0]}")
                result.passed = False  # Downgrade to failed

            elif reasoning.requires_challenge:
                approvals_to_challenge.append(result)
                print(f"  🔍 {result.name}: APPROVAL - will challenge with skeptic")

            else:
                print(f"  ✓ {result.name}: Reasoning valid")

        # Challenge approvals with skeptic
        if approvals_to_challenge:
            print(f"\n🔍 Challenging {len(approvals_to_challenge)} approval(s) with skeptic...")

            for result in approvals_to_challenge:
                skeptic_result = await run_skeptic(
                    agent_output=result.output,
                    files=files,
                    original_agent=result.name,
                )

                if skeptic_result["verdict"] == "OVERRIDE":
                    print(f"  ❌ Skeptic OVERRIDES {result.name}'s approval")
                    result.passed = False
                    result.verdict = f"{result.verdict} (SKEPTIC OVERRIDE)"
                elif skeptic_result["verdict"] == "CONCERNS":
                    print(f"  ⚠️ Skeptic has CONCERNS about {result.name}'s approval")
                    if skeptic_result["high_severity_count"] > 0:
                        result.passed = False
                        result.verdict = f"{result.verdict} (SKEPTIC: {skeptic_result['high_severity_count']} HIGH)"
                else:
                    print(f"  ✅ Skeptic CONFIRMS {result.name}'s approval")

    # Generate report
    report = orchestrator.synthesize_report()

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    # Save report if requested
    if args.output:
        args.output.write_text(report)
        print(f"\nReport saved to: {args.output}")

    # Exit with appropriate code
    exit_code = orchestrator.get_exit_code()
    if exit_code == 0:
        print("\n✅ Review passed")
    elif exit_code == 1:
        print("\n❌ Review failed (hard gate)")
    elif exit_code == 2:
        print("\n⚠️ Review passed with warnings")
    else:
        print("\n⚠️ Compliance failures detected")

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
