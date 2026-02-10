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
    full:   + fuzzer always; grounding is risk-triggered (5-6 agents)
    founder: + translator, visualizer (7-8 agents)
    all:    + advisor (8-9 agents)

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
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Any

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

SDK_IMPORT_ERROR: Exception | None = None
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition
except Exception as _sdk_import_error:
    SDK_IMPORT_ERROR = _sdk_import_error
    query = None  # type: ignore[assignment]
    ClaudeAgentOptions = None  # type: ignore[assignment]
    AgentDefinition = Any  # type: ignore[assignment]

# Import agent memory for persistent finding storage
try:
    from tools.agent_memory import (
        store_finding,
        load_findings,
        get_context_for_files,
        get_pattern_context,
    )
    AGENT_MEMORY_AVAILABLE = True
    AGENT_MEMORY_IMPORT_ERROR = ""
except Exception as _agent_memory_error:
    AGENT_MEMORY_AVAILABLE = False
    AGENT_MEMORY_IMPORT_ERROR = str(_agent_memory_error)

    def store_finding(*args, **kwargs):
        return None

    def load_findings():
        return []

    def get_context_for_files(*args, **kwargs):
        return ""

    def get_pattern_context(*args, **kwargs):
        return ""

# Import shared FINDING extraction (single source of truth)
from tools.validate_agent_compliance import extract_finding_blocks
from tools.agent_runner_common import sanitize_files
from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    AGENT_PASS_VERDICTS,
    GOOD_VERDICTS,
    HARD_GATE_AGENTS,
    adversary_blocks_merge,
    agent_passed as shared_agent_passed,
    build_sdk_options,
    extract_text_from_message,
    extract_verdict_secure,
    load_agent_prompt_with_contract,
    resolve_agent_model,
    sanitize_for_prompt,
    validate_compliance as shared_validate_compliance,
)


# =============================================================================
# Agent Definitions
# =============================================================================

def create_agent_definitions(model_override: str | None = None) -> dict[str, AgentDefinition]:
    """Create all 9 agent definitions with their specialized prompts."""

    return {
        # === HARD GATE AGENTS (must pass for PR approval) ===
        "verifier": AgentDefinition(
            description="Verifies code against North Star invariants. Use for compliance checks.",
            prompt=load_agent_prompt_with_contract("verifier"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("verifier", model_override),
        ),
        "adversary": AgentDefinition(
            description="Red team agent that tries to break code. Use for security review.",
            prompt=load_agent_prompt_with_contract("adversary"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("adversary", model_override),
        ),
        "expert": AgentDefinition(
            description="Expert code reviewer for complexity and simplification. Use for quality review.",
            prompt=load_agent_prompt_with_contract("expert"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("expert", model_override),
        ),
        "structural-proof": AgentDefinition(
            description="Demands concrete proof of structural claims. Use for projection verification.",
            prompt=load_agent_prompt_with_contract("structural-proof"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("structural-proof", model_override),
        ),

        # === DEPTH AGENTS (thorough verification) ===
        "grounding": AgentDefinition(
            description="Converts claims into executable tests. Use for test coverage verification.",
            prompt=load_agent_prompt_with_contract("grounding"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("grounding", model_override),
        ),
        "fuzzer": AgentDefinition(
            description="Property-based testing with Hypothesis. Use for edge case discovery.",
            prompt=load_agent_prompt_with_contract("fuzzer"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("fuzzer", model_override),
        ),

        # === FOUNDER AGENTS (human-readable output) ===
        "translator": AgentDefinition(
            description="Explains code in plain English. Use for founder review.",
            prompt=load_agent_prompt_with_contract("translator"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("translator", model_override),
        ),
        "visualizer": AgentDefinition(
            description="Creates Mermaid diagrams of structures. Use for visual verification.",
            prompt=load_agent_prompt_with_contract("visualizer"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("visualizer", model_override),
        ),

        # === ADVISORY AGENT (non-gating) ===
        "advisor": AgentDefinition(
            description="Strategic advisor for design decisions. Use when stuck.",
            prompt=load_agent_prompt_with_contract("advisor"),
            tools=["Read", "Grep", "Glob"],
            model=resolve_agent_model("advisor", model_override),
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

# Runtime budget controls (major latency lever)
# 25 turns handles full-codebase reviews; agents hit turn limits at lower values
# on large scopes. Use --max-turns to override if needed.
AGENT_MAX_TURNS = {
    "verifier": 25,
    "adversary": 25,
    "expert": 20,
    "structural-proof": 20,
    "grounding": 18,
    "fuzzer": 20,
    "translator": 20,
    "visualizer": 15,
    "advisor": 18,
}

GROUNDING_HIGH_RISK_PATTERNS = (
    "rcx_pi/selfhost/",
    "mu/",
    "tests/structural/",
    "tests/fuzz/",
    "tests/test_js_parity_automated.py",
    "tools/run_review.py",
    "tools/validate_agent_compliance.py",
    "tools/validate_agent_reasoning.py",
)


def should_include_grounding(files: list[str]) -> bool:
    """Run grounding only on high-risk changes unless explicitly forced."""
    normalized = [f.replace("\\", "/") for f in files]
    for file_path in normalized:
        if any(pattern in file_path for pattern in GROUNDING_HIGH_RISK_PATTERNS):
            return True
    return len(files) >= 20

# =============================================================================
# Compliance Validation
# =============================================================================

def validate_compliance(output: str) -> tuple[bool, str, dict]:
    """Run compliance validation on agent output.

    Delegates to shared_agent_utils.validate_compliance with strict policy:
    all verification flags enabled.

    Note: imprecise citations (near-match/paraphrase) do NOT block compliance.
    Only true fabrications (missing file, no resemblance) set compliant=False.
    """
    return shared_validate_compliance(
        output,
        strict=True,
        verify_files=True,
        verify_code=True,
        json_output=True,
    )


def build_query_options(agent_def: AgentDefinition, max_turns: int) -> ClaudeAgentOptions:
    """Build SDK query options with explicit model wiring.

    Fail-closed: if SDK options cannot accept `model=`, raise RuntimeError.
    """
    if ClaudeAgentOptions is None:
        raise RuntimeError(f"claude_agent_sdk unavailable: {SDK_IMPORT_ERROR}")
    model = getattr(agent_def, "model", None)
    return build_sdk_options(
        ClaudeAgentOptions,
        allowed_tools=["Read", "Grep", "Glob"],
        max_turns=max_turns,
        model=model,
        require_model_kwarg=True,
    )


INFRA_FAILURE_EXIT_CODE = 4


async def run_agent_preflight(
    timeout_seconds: int = 20,
    model_override: str | None = None,
) -> tuple[bool, str]:
    """Validate SDK/runtime availability before launching review agents.

    This avoids burning runtime/tokens on known-bad infra states where all
    agents return transport/runtime errors instead of review output.
    """
    if os.getenv("RCX_AGENT_PREFLIGHT_FORCE_FAIL") == "1":
        return False, "Forced preflight failure via RCX_AGENT_PREFLIGHT_FORCE_FAIL=1"

    if SDK_IMPORT_ERROR is not None or query is None:
        return False, f"Claude SDK import failed: {SDK_IMPORT_ERROR}"

    try:
        verifier_def = create_agent_definitions(model_override=model_override)["verifier"]
        saw_message = False
        saw_result = False

        async def _ping() -> None:
            nonlocal saw_message, saw_result
            async for message in query(
                prompt="Preflight check. Reply with exactly: PONG",
                options=build_query_options(verifier_def, max_turns=1),
            ):
                saw_message = True
                extracted = extract_text_from_message(message)
                if extracted and extracted.strip():
                    saw_result = True
                if hasattr(message, "result") and message.result:
                    saw_result = True

        await asyncio.wait_for(_ping(), timeout=timeout_seconds)
        if not saw_message and not saw_result:
            return False, "Preflight query returned no messages/results"
        return True, ""
    except asyncio.TimeoutError:
        return False, f"SDK preflight timed out after {timeout_seconds}s"
    except Exception as exc:
        return False, f"SDK preflight query failed: {exc}"


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
    blocks_merge: bool
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
        severity = verdict_to_severity(verdict)

        findings.append({
            "message": block.finding,
            "file": block.file_path,
            "line": line,
            "severity": severity,
        })

    return findings


def verdict_to_severity(verdict: str) -> str:
    """Map agent verdict to finding severity."""
    # Critical verdicts
    if verdict in {"VULNERABLE", "BROKEN", "IMPOSSIBLE_AS_CLAIMED", "THEATER"}:
        return "critical"
    # High severity
    if verdict in {
        "REQUEST_CHANGES",
        "OVER_ENGINEERED",
        "UNPROVEN",
        "UNGROUNDED",
        "FRAGILE",
        "NOT_EXECUTED",
        "SCOPE_CREEP",
        "HOST_SMUGGLING",
        "STRUCTURAL_LIES",
        "PYTHON_SMUGGLING",
    }:
        return "high"
    # Medium
    if verdict in {
        "COULD_SIMPLIFY",
        "PARTIALLY_GROUNDED",
        "DEVIATES",
        "CONCERNS",
        "NEEDS_HARDENING",
        "HIDDEN_CONSTRAINTS",
        "FLAWED_APPROACH",
        "NEEDS_DISCUSSION",
    }:
        return "medium"
    # Low/info - passing verdicts (uses pre-computed GOOD_VERDICTS from shared_agent_utils)
    if verdict in GOOD_VERDICTS:
        return "info"
    return "medium"


def extract_verdict(agent_name: str, output: str) -> str:
    """Extract verdict from agent output using shared secure parsing."""
    return extract_verdict_secure(output, agent_name=agent_name)


def agent_passed(agent_name: str, verdict: str) -> bool:
    """Determine if an agent's verdict indicates pass.

    Pass verdicts must align with what agent prompts define as acceptable outcomes.
    """
    return shared_agent_passed(agent_name, verdict)


# =============================================================================
# Orchestrator
# =============================================================================

class ReviewOrchestrator:
    """Orchestrates parallel agent execution and result synthesis."""

    def __init__(self, files: list[str], depth: str = "full", verbose: bool = False,
                 use_memory: bool = True, pr_number: int | None = None,
                 show_warnings: bool = False,
                 continue_on_hard_gate: bool = True,
                 force_grounding: bool = False,
                 model_override: str | None = None,
                 agent_max_turns: dict | None = None):
        self.files = files
        self.depth = depth
        self.verbose = verbose
        self.use_memory = use_memory
        self.pr_number = pr_number
        self.show_warnings = show_warnings
        self.continue_on_hard_gate = continue_on_hard_gate
        self.force_grounding = force_grounding
        self.model_override = model_override
        self.agent_max_turns = agent_max_turns or dict(AGENT_MAX_TURNS)
        self.agents_to_run = self._resolve_agents_to_run(depth)
        self.agent_definitions = create_agent_definitions(model_override=model_override)
        self.results: list[AgentResult] = []
        self.regression_warnings: list[dict] = []
        self.soft_warnings: list[dict] = []  # Non-hard-gate failures
        self.total_findings_stored: int = 0
        self._hard_gate_failed: bool = False
        if self.use_memory and not AGENT_MEMORY_AVAILABLE:
            self.use_memory = False
            if self.verbose:
                print(
                    "⚠️  Agent memory disabled: "
                    f"{AGENT_MEMORY_IMPORT_ERROR}"
                )

    def _resolve_agents_to_run(self, depth: str) -> list[str]:
        """Resolve depth agent set with runtime policy adjustments.

        Policy:
        - `fuzzer` remains always-on for `full` and above to prevent fuzz drift.
        - `grounding` is risk-triggered unless explicitly forced.
        """
        agents = list(DEPTH_AGENTS.get(depth, DEPTH_AGENTS["full"]))
        if "grounding" in agents and not self.force_grounding:
            if not should_include_grounding(self.files):
                agents.remove("grounding")
        return agents

    async def run_single_agent(self, agent_name: str, retry_feedback: str = "") -> AgentResult:
        """Run a single agent and return its result.

        Args:
            agent_name: Name of the agent to run
            retry_feedback: If provided, include this feedback about previous failure
        """
        if self.verbose:
            print(f"  Starting {agent_name}...")

        file_list = ", ".join(sanitize_files(self.files))
        agent_def = self.agent_definitions[agent_name]

        # Build memory context (past findings + patterns)
        memory_context = ""
        if self.use_memory:
            file_context = get_context_for_files(self.files)
            pattern_context = get_pattern_context()
            if file_context or pattern_context:
                memory_context = file_context + pattern_context

        # Build retry feedback section if this is a retry
        retry_section = ""
        if retry_feedback:
            safe_feedback = sanitize_for_prompt(retry_feedback, max_len=500)
            retry_section = f"""
---
IMPORTANT: Your previous output failed compliance validation. Here's what went wrong:
{safe_feedback}

Please address these issues in your response. Ensure you:
1. Include proper FINDING blocks with FILE, LINES, CODE, and VERIFIED fields
2. Include a clear Verdict line
3. Do NOT fabricate code - only cite code you actually read with the Read tool
---
"""

        prompt = f"""You are the RCX {agent_name.replace('-', ' ').title()} Agent.

{agent_def.prompt}
{memory_context}
{retry_section}
---

Now review these files: {file_list}

Produce a report following the format in your instructions.
"""

        result_text = ""
        last_error = None
        message_text_fragments: list[str] = []
        max_turns = self.agent_max_turns.get(agent_name, 12)

        try:
            async for message in query(
                prompt=prompt,
                options=build_query_options(agent_def, max_turns)
            ):
                # Check for API errors on AssistantMessage
                if hasattr(message, 'error') and message.error:
                    last_error = message.error

                # Capture any text-like content as backup (SDK shape can vary)
                extracted = extract_text_from_message(message)
                if extracted:
                    message_text_fragments.append(extracted)

                # Primary: get result from ResultMessage
                if hasattr(message, 'result') and message.result:
                    result_text = message.result
        except Exception as e:
            # Preserve any text fragments collected before the error
            if message_text_fragments and not result_text:
                result_text = "\n".join(dict.fromkeys(message_text_fragments))
                result_text += f"\n\nAGENT ERROR (partial output above): {e}"
            else:
                result_text = f"AGENT ERROR: {e}"

        # If no result but we have an error, report it
        if not result_text and last_error:
            result_text = f"AGENT API ERROR: {last_error}"

        # If no result but we captured text fragments, use them as fallback
        if not result_text and message_text_fragments:
            # Deduplicate while preserving order
            result_text = "\n".join(dict.fromkeys(message_text_fragments))

        # Handle empty output as a special compliance failure
        if not result_text or not result_text.strip():
            is_compliant = False
            # Provide diagnostic info in verbose mode
            if self.verbose:
                print(
                    f"    DEBUG {agent_name}: result_text empty, "
                    f"last_error={last_error}, message_fragments={len(message_text_fragments)}"
                )
            compliance_error = (
                f"EMPTY OUTPUT: Agent returned no output. "
                f"API error: {last_error or 'none'}. "
                f"Extracted fragments: {len(message_text_fragments)}."
            )
        else:
            # Validate compliance
            is_compliant, compliance_error, compliance_metrics = validate_compliance(result_text)

            # Log imprecise citations as warnings (non-blocking)
            imprecise_count = compliance_metrics.get("imprecise_citations", 0)
            if imprecise_count > 0 and self.verbose:
                print(f"    ⚠️  {agent_name}: {imprecise_count} imprecise citation(s) (non-blocking)")

        # Extract verdict
        verdict = extract_verdict(agent_name, result_text)
        passed = agent_passed(agent_name, verdict) and is_compliant
        is_hard_gate = agent_name in HARD_GATE_AGENTS
        blocks_merge = is_hard_gate and not passed

        # Evidence-gated adversary blocking: failing adversary verdicts only block
        # when output is compliant and contains machine-checkable proof markers.
        if agent_name == "adversary" and blocks_merge:
            blocks_merge = adversary_blocks_merge(
                verdict=verdict,
                output=result_text,
                is_compliant=is_compliant,
            )

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
            is_hard_gate=is_hard_gate,
            blocks_merge=blocks_merge,
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
        """Check if any files being reviewed have previously-fixed issues.

        Security: Uses proper path normalization to prevent path traversal attacks.
        """
        if not self.use_memory:
            return []

        warnings = []
        all_findings = load_findings()

        # Get fixed findings for files we're reviewing
        fixed_findings = [f for f in all_findings if f.get("fixed")]

        # Normalize review file paths for safe comparison
        normalized_review_files = set()
        for review_file in self.files:
            try:
                normalized_review_files.add(Path(review_file).resolve())
            except (OSError, ValueError):
                # Skip invalid paths
                continue

        for finding in fixed_findings:
            finding_file = finding.get("file", "")
            if not finding_file:
                continue

            # Normalize finding file path and check for exact match
            try:
                finding_path = Path(finding_file).resolve()
            except (OSError, ValueError):
                continue

            # Check for exact path match (no substring matching)
            if finding_path in normalized_review_files:
                warnings.append({
                    "finding_id": finding.get("id"),
                    "file": finding_file,
                    "message": finding.get("message", ""),
                    "agent": finding.get("agent", ""),
                    "severity": finding.get("severity", "info"),
                })

        return warnings

    async def run_all(self) -> list[AgentResult]:
        """Run all agents in parallel groups."""
        print(f"\n{'='*60}")
        print(f"RCX REVIEW ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Files: {', '.join(self.files)}")
        print(f"Depth: {self.depth} ({len(self.agents_to_run)} agents)")
        if "grounding" not in self.agents_to_run and "grounding" in DEPTH_AGENTS.get(self.depth, []):
            print("Grounding: skipped (low-risk scope, use --force-grounding to include)")
        if self.use_memory:
            print(f"Memory: enabled")
        print(f"{'='*60}\n")

        # Check for regressions before running
        if self.use_memory:
            self.regression_warnings = self.check_for_regressions()
            if self.regression_warnings:
                # Progressive disclosure: summary by default, details with --show-warnings
                high_sev = sum(1 for w in self.regression_warnings if w.get('severity') in ('critical', 'high'))
                other = len(self.regression_warnings) - high_sev
                if self.show_warnings:
                    print(f"⚠️  REGRESSION CHECK: {len(self.regression_warnings)} previously-fixed issue(s):")
                    for w in self.regression_warnings:
                        sev = w.get('severity', 'unknown').upper()
                        print(f"   [{sev}] #{w['finding_id']} [{w['agent']}] {w['file']}")
                        print(f"         {w['message'][:80]}...")
                else:
                    sev_summary = f"{high_sev} HIGH" if high_sev else ""
                    if other:
                        sev_summary += ", " if sev_summary else ""
                        sev_summary += f"{other} other"
                    print(f"⚠️  REGRESSION CHECK: {len(self.regression_warnings)} warning(s) ({sev_summary}) — use --show-warnings for details")
                print()

        all_results = []

        for i, group in enumerate(PARALLEL_GROUPS):
            group_agents = [a for a in group if a in self.agents_to_run]
            if not group_agents:
                continue

            print(f"Phase {i+1}: Running {', '.join(group_agents)} in parallel...")
            group_results = await self.run_agent_group(group_agents)
            all_results.extend(group_results)

            # Check hard gate failures - retry compliance failures once, then stop if still failing
            hard_gate_failures = [r for r in group_results if r.blocks_merge]
            if hard_gate_failures and i == 0:  # Only stop after first group
                # Separate compliance failures from verdict failures
                compliance_failures = [r for r in hard_gate_failures if not r.is_compliant]
                verdict_failures = [r for r in hard_gate_failures if r.is_compliant]

                # Retry compliance failures with explicit feedback about what went wrong
                if compliance_failures:
                    print(f"\n🔄 Retrying {len(compliance_failures)} agent(s) with compliance failures...")
                    for r in compliance_failures:
                        error_preview = (r.compliance_error or "unknown")[:100]
                        print(f"   - {r.name}: {error_preview}")

                    retry_results = []
                    for r in compliance_failures:
                        print(f"   Retrying {r.name}...")
                        # Pass the compliance error as feedback so agent knows what to fix
                        retry_feedback = r.compliance_error or "Unknown compliance failure"
                        retry = await self.run_single_agent(r.name, retry_feedback=retry_feedback)
                        retry_results.append(retry)

                        if retry.is_compliant:
                            print(f"   ✓ {r.name}: Retry passed compliance")
                            # Replace in all_results
                            idx = all_results.index(r)
                            all_results[idx] = retry
                        else:
                            print(f"   ✗ {r.name}: Retry still non-compliant")
                            error_preview = (retry.compliance_error or "unknown")[:100]
                            print(f"     └─ {error_preview}")

                # Re-check hard gate failures after retry
                hard_gate_failures = [r for r in all_results if r.blocks_merge]

                if hard_gate_failures:
                    print(f"\n⚠️  Hard gate failure(s) after retry:")
                    for r in hard_gate_failures:
                        reason = "verdict" if r.is_compliant else "compliance"
                        print(f"   - {r.name}: {r.verdict} ({reason} failure)")
                        if not r.is_compliant and r.compliance_error:
                            error_preview = r.compliance_error[:200]
                            print(f"     └─ {error_preview}{'...' if len(r.compliance_error) > 200 else ''}")
                    print(f"\n   Run with --verbose for full details")
                    self._hard_gate_failed = True
                    if not self.continue_on_hard_gate:
                        self.results = all_results
                        self.total_findings_stored = sum(r.findings_stored for r in all_results)
                        return all_results
                    print("\n⚠️  Continuing despite hard gate failure (diagnostic mode)")

        self.results = all_results
        self._hard_gate_failed = any(r.blocks_merge for r in all_results)
        self.total_findings_stored = sum(r.findings_stored for r in all_results)

        # Collect soft warnings (non-hard-gate failures)
        # Uses verdict_to_severity() as single source of truth for severity mapping
        self.soft_warnings = [
            {
                'agent': r.name,
                'verdict': r.verdict,
                'severity': verdict_to_severity(r.verdict),
            }
            for r in all_results if not r.blocks_merge and not r.passed
        ]

        # End-of-run warning summary (progressive disclosure)
        total_warnings = len(self.regression_warnings) + len(self.soft_warnings)
        if total_warnings > 0:
            high_count = sum(1 for w in self.regression_warnings if w.get('severity') in ('critical', 'high'))
            high_count += sum(1 for w in self.soft_warnings if w.get('severity') in ('critical', 'high'))
            med_count = sum(1 for w in self.soft_warnings if w.get('severity') == 'medium')
            other_count = total_warnings - high_count - med_count

            if self.show_warnings:
                print(f"\n{'='*60}")
                print(f"⚠️  WARNING SUMMARY: {total_warnings} total warning(s)")
                print(f"{'='*60}")
                if self.soft_warnings:
                    print("\nSoft gate warnings (non-blocking):")
                    for w in self.soft_warnings:
                        print(f"  - {w['agent']}: {w['verdict']} [{w['severity'].upper()}]")
            else:
                parts = []
                if high_count:
                    parts.append(f"{high_count} HIGH")
                if med_count:
                    parts.append(f"{med_count} MEDIUM")
                if other_count:
                    parts.append(f"{other_count} other")
                sev_summary = ", ".join(parts) if parts else "all low"
                print(f"\n⚠️  {total_warnings} warning(s) ({sev_summary}) — use --show-warnings for details")

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

            if result.blocks_merge:
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
        hard_gate_failures = [r for r in self.results if r.blocks_merge]
        if hard_gate_failures:
            return 1

        # Check soft failures
        soft_failures = [r for r in self.results if not r.blocks_merge and not r.passed]
        if soft_failures:
            return 2

        return 0


def enforce_global_high_fail_closed(results: list[AgentResult], global_high: int) -> None:
    """Fail-closed policy: AGENT: ALL + HIGH concerns block all challenged approvals."""
    if global_high <= 0:
        return
    for result in results:
        result.passed = False
        result.verdict = f"{result.verdict} (SKEPTIC_GLOBAL_HIGH:{global_high})"
        result.blocks_merge = result.is_hard_gate and (not result.passed)


# =============================================================================
# Git Integration
# =============================================================================

def _get_base_branch() -> str:
    """Detect the default branch (dev, main, master, etc.).

    Raises FileNotFoundError if git is not installed (callers handle this).
    """
    for candidate in ["dev", "main", "master"]:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return candidate
        except subprocess.TimeoutExpired:
            continue
    return "dev"  # fallback


def get_changed_files() -> list[str]:
    """Get files changed in current branch vs base branch.

    Raises:
        RuntimeError: If git command fails (don't fail silently)
    """
    try:
        base = _get_base_branch()
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            # Don't fail silently - this could cause bad PRs to pass
            raise RuntimeError(f"git diff failed: {result.stderr}")
        files = [f for f in result.stdout.strip().split('\n') if f]
        # Filter to relevant files
        return [f for f in files if f.endswith('.py') or f.endswith('.json')]
    except subprocess.TimeoutExpired:
        raise RuntimeError("git diff timed out")
    except FileNotFoundError:
        raise RuntimeError("git not found - cannot determine changed files")


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
  full     5-6 agents: + fuzzer always; grounding risk-triggered
  founder  7-8 agents: + translator, visualizer
  all      8-9 agents: + advisor

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
        help="Review files changed in current PR (git diff vs base branch)"
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
        "--show-warnings",
        action="store_true",
        help="Show full warning details (default: summary only)"
    )
    parser.add_argument(
        "--force-grounding",
        action="store_true",
        help="Force grounding agent even for low-risk scopes"
    )
    parser.add_argument(
        "--fail-fast-hard-gate",
        action="store_true",
        help="Stop immediately after hard gate failures in phase 1 (legacy fail-fast behavior)"
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip mandatory SDK/runtime preflight (debugging only)"
    )
    parser.add_argument(
        "--preflight-timeout",
        type=int,
        default=20,
        help="Preflight timeout in seconds (default: 20)"
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        help="Override per-agent max_turns (use for large scopes that need more exploration)"
    )
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for all agents (default uses per-agent policy)"
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

    # Mandatory runtime preflight for real review runs.
    if not args.skip_preflight:
        print("🔧 Running agent runtime preflight...")
        preflight_ok, preflight_error = await run_agent_preflight(
            timeout_seconds=args.preflight_timeout,
            model_override=args.model,
        )
        if not preflight_ok:
            print("\n❌ AGENT PREFLIGHT FAILED")
            print(f"Reason: {preflight_error}")
            print("Action: run `PYTHONHASHSEED=0 python3 tools/check_agent_runtime.py` and fix runtime.")
            sys.exit(INFRA_FAILURE_EXIT_CODE)

    # Determine depth
    depth = args.depth
    if args.founder:
        depth = "founder"
    if args.rigorous:
        depth = "all"
    if args.pr and depth == "full":
        depth = auto_select_depth(files)
        print(f"Auto-selected depth: {depth}")

    # Apply max-turns override if specified (use local copy, don't mutate module-level)
    agent_max_turns = dict(AGENT_MAX_TURNS)
    if args.max_turns:
        for key in agent_max_turns:
            agent_max_turns[key] = args.max_turns
        print(f"Max turns override: {args.max_turns} for all agents")

    # Run orchestrator
    orchestrator = ReviewOrchestrator(
        files,
        depth=depth,
        verbose=args.verbose,
        use_memory=not args.no_memory,
        pr_number=args.pr_number,
        show_warnings=args.show_warnings,
        continue_on_hard_gate=(not args.fail_fast_hard_gate),
        force_grounding=args.force_grounding,
        model_override=args.model,
        agent_max_turns=agent_max_turns,
    )
    await orchestrator.run_all()

    # Reasoning validation and skeptic challenge are rigorous-only.
    hard_gate_failed = getattr(orchestrator, "_hard_gate_failed", False)
    approvals_to_challenge: list[AgentResult] = []
    if args.rigorous:
        if hard_gate_failed:
            print("\n⚠️  Hard gate failures detected — running rigorous checks anyway")

        print("\n📋 Validating reasoning quality...")
        try:
            from tools.validate_agent_reasoning import validate_reasoning
        except ModuleNotFoundError:
            from validate_agent_reasoning import validate_reasoning

        reasoning_failures: list[tuple[AgentResult, str]] = []
        for result in orchestrator.results:
            reasoning = validate_reasoning(result.output)
            if not reasoning.is_valid:
                reasoning_failures.append((result, reasoning.violations[0]))
                print(f"  ⚠️ {result.name}: Reasoning invalid - {reasoning.violations[0]}")
            elif reasoning.requires_challenge:
                approvals_to_challenge.append(result)
                print(f"  🔍 {result.name}: APPROVAL - will challenge with skeptic")
            else:
                print(f"  ✓ {result.name}: Reasoning valid")

        # Retry hard-gate agents with invalid reasoning only in rigorous mode.
        if reasoning_failures:
            hard_gate_failures = [(r, v) for r, v in reasoning_failures if r.blocks_merge]
            if hard_gate_failures:
                print(f"\n🔄 Retrying {len(hard_gate_failures)} hard gate agent(s) with format reminder...")
                for result, violation in hard_gate_failures:
                    print(f"  Retrying {result.name}...")
                    retry_feedback = f"Reasoning validation failed: {violation}"
                    retry_result = await orchestrator.run_single_agent(
                        result.name,
                        retry_feedback=retry_feedback,
                    )
                    retry_reasoning = validate_reasoning(retry_result.output)
                    if retry_reasoning.is_valid:
                        print(f"  ✓ {result.name}: Retry successful")
                        idx = orchestrator.results.index(result)
                        orchestrator.results[idx] = retry_result
                    else:
                        print(f"  ✗ {result.name}: Retry still invalid - {retry_reasoning.violations[0]}")
                        result.passed = False
                        if result.is_hard_gate:
                            result.blocks_merge = True

        if not approvals_to_challenge:
            print("\n🔍 RIGOROUS: no approvals to challenge")

    # Rigorous mode: consolidated skeptic challenge.
    if args.rigorous and approvals_to_challenge:
        print(f"\n🔍 RIGOROUS: Consolidated skeptic challenging {len(approvals_to_challenge)} approval(s)...")
        try:
            from tools.run_skeptic import run_consolidated_skeptic
        except ModuleNotFoundError:
            from run_skeptic import run_consolidated_skeptic

        agent_outputs = {result.name: result.output for result in approvals_to_challenge}
        skeptic_result = await run_consolidated_skeptic(
            agent_outputs=agent_outputs,
            files=files,
            model_override=args.model,
        )

        if not skeptic_result.get("is_compliant", False):
            print(f"  ⚠️  Skeptic output failed compliance: {skeptic_result.get('compliance_error', 'unknown')}")
            print("      Treating as UNKNOWN (fail-closed)")
            skeptic_result["verdict"] = "UNKNOWN"

        per_agent = skeptic_result.get("verdict_per_agent", {})
        for result in approvals_to_challenge:
            agent_verdict = per_agent.get(result.name, "UNKNOWN")
            if agent_verdict == "OVERRIDE":
                print(f"  ❌ Skeptic OVERRIDES {result.name}'s approval")
                result.passed = False
                result.verdict = f"{result.verdict} (SKEPTIC OVERRIDE)"
            elif agent_verdict == "CONCERNS":
                print(f"  ⚠️ Skeptic has CONCERNS about {result.name}'s approval")
            elif agent_verdict == "UNKNOWN":
                print(f"  ❓ Skeptic did not evaluate {result.name} — fail-closed")
                result.passed = False
                result.verdict = f"{result.verdict} (SKEPTIC_NOT_EVALUATED)"
            else:
                print(f"  ✅ Skeptic CONFIRMS {result.name}'s approval")

        global_concerns = skeptic_result.get("global_concerns", [])
        if global_concerns:
            print(f"\n  🎯 GLOBAL BLIND SPOTS (AGENT: ALL): {len(global_concerns)} found")
            for concern in global_concerns:
                print(f"    - {concern[:120]}")
            for result in approvals_to_challenge:
                result.verdict = f"{result.verdict} (GLOBAL_BLIND_SPOT)"

        # Fail-closed: if global concerns exist AND there are HIGH severity
        # findings, block all challenged approvals.
        global_high = skeptic_result.get("high_severity_count", 0)
        if global_concerns and global_high > 0:
            print(f"  ❌ Skeptic GLOBAL HIGH concerns ({global_high}) — fail-closed blocking all approvals")
            enforce_global_high_fail_closed(approvals_to_challenge, global_high)

        untagged = skeptic_result.get("untagged_warnings", [])
        if untagged:
            print(f"\n  ⚠️  UNTAGGED CONCERNS: {len(untagged)} concern(s) missing AGENT: marker")
            for warning in untagged:
                print(f"    - {warning}")

        if skeptic_result["verdict"] == "OVERRIDE":
            print("  ❌ Skeptic OVERALL OVERRIDE — significant blind spots")
            for result in approvals_to_challenge:
                agent_v = per_agent.get(result.name, "CONFIRMED")
                if agent_v != "CONFIRMED":
                    result.passed = False
                    result.verdict = f"{result.verdict} (SKEPTIC: {skeptic_result['high_severity_count']} HIGH)"
        elif skeptic_result["verdict"] == "CONCERNS":
            print(
                f"  ⚠️ Skeptic has CONCERNS — "
                f"{skeptic_result['high_severity_count']} HIGH, {skeptic_result['medium_severity_count']} MEDIUM"
            )
            if skeptic_result["high_severity_count"] > 0:
                for result in approvals_to_challenge:
                    agent_v = per_agent.get(result.name, "CONFIRMED")
                    if agent_v in ("CONCERNS", "OVERRIDE"):
                        result.passed = False
                        result.verdict = (
                            f"{result.verdict} (SKEPTIC_CONCERNS: {skeptic_result['high_severity_count']} HIGH)"
                        )
        elif skeptic_result["verdict"] == "UNKNOWN":
            print("  ❓ Skeptic returned UNKNOWN verdict — fail-closed, blocking approvals")
            for result in approvals_to_challenge:
                result.passed = False
                result.verdict = f"{result.verdict} (SKEPTIC_INCONCLUSIVE)"
        elif skeptic_result["verdict"] == "CONFIRMED":
            print("  ✅ Skeptic CONFIRMS all approvals — no blind spots")

        for result in approvals_to_challenge:
            result.blocks_merge = result.is_hard_gate and (not result.passed)

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
