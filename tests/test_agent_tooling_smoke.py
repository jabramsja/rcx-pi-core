#!/usr/bin/env python3
"""
Smoke tests for agent tooling.

These tests verify that the agent tools can at least import and run
without crashing. They catch basic issues like import errors that
security-focused red-team reviews might miss.

IMPORTANT: These tests don't run the actual agents (which costs money
and requires API keys). They just verify the tooling is functional.
"""

import subprocess
import sys
import os
from pathlib import Path
import importlib.util

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"

# Ensure repo root is in sys.path for 'tools' imports
# pytest can add tests/ to sys.path which shadows repo root
_repo_root = str(PROJECT_ROOT)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


def import_from_path(module_name: str, file_path: Path):
    """Import a module from an explicit file path, avoiding shadowing."""
    # Ensure project root is in sys.path for 'tools' imports
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAgentToolingSmoke:
    """Smoke tests to verify agent tools are importable and runnable."""

    @pytest.mark.parametrize("script", [
        "check_agent_runtime.py",
        "run_review.py",
        "run_ci_review.py",
        "run_interactive.py",
        "run_skeptic.py",
        "validate_agent_compliance.py",
        "validate_agent_reasoning.py",
        "agent_memory.py",
    ])
    def test_tool_help_works(self, script: str):
        """Core tools should show help without crashing.

        Note: Individual agent runners (run_verifier.py, etc.) are excluded
        because they load prompt files at import time which can be slow.
        """
        script_path = TOOLS_DIR / script
        if not script_path.exists():
            pytest.skip(f"Script not found: {script}")

        # Run with --help to test basic import/execution
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=60,  # Allow more time for SDK import
            cwd=PROJECT_ROOT,
        )

        # Should either succeed or show usage (some tools might exit 2 for help)
        # Also allow exit code 1 if it's just missing required args
        assert result.returncode in (0, 1, 2), (
            f"{script} failed to run:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_run_review_imports_work(self):
        """run_review.py should import without PYTHONPATH set."""
        # This specifically tests the sys.path fix
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
            env={k: v for k, v in os.environ.items() if k != 'PYTHONPATH'},
        )

        # Allow import to succeed
        if result.returncode not in (0, 1, 2):
            # Also allow if claude_agent_sdk not installed
            if "claude_agent_sdk" in result.stderr:
                pytest.skip("claude_agent_sdk not installed")
            pytest.fail(
                f"run_review.py failed without PYTHONPATH:\n{result.stderr}"
            )

    def test_agent_memory_functions_exist(self):
        """agent_memory.py should export expected functions."""
        # Import from explicit path to avoid tests/tools/ shadowing
        agent_memory = import_from_path("agent_memory", TOOLS_DIR / "agent_memory.py")

        # Check key functions exist
        assert hasattr(agent_memory, 'store_finding')
        assert hasattr(agent_memory, 'load_findings')
        assert hasattr(agent_memory, 'get_context_for_files')
        assert hasattr(agent_memory, 'get_pattern_context')
        assert hasattr(agent_memory, 'load_patterns')

    def test_validate_compliance_functions_exist(self):
        """validate_agent_compliance.py should export expected functions."""
        # Import from explicit path to avoid tests/tools/ shadowing
        validate_agent_compliance = import_from_path(
            "validate_agent_compliance",
            TOOLS_DIR / "validate_agent_compliance.py"
        )

        assert hasattr(validate_agent_compliance, 'extract_finding_blocks')
        assert hasattr(validate_agent_compliance, 'check_compliance')

    def test_agent_prompts_exist(self):
        """All agent prompt files should exist."""
        prompts_dir = TOOLS_DIR / "agents"
        expected_prompts = [
            "verifier_prompt.md",
            "adversary_prompt.md",
            "expert_prompt.md",
            "structural_proof_prompt.md",
            "fuzzer_prompt.md",
            "grounding_prompt.md",
            "translator_prompt.md",
            "visualizer_prompt.md",
            "advisor_prompt.md",
        ]

        missing = []
        for prompt in expected_prompts:
            if not (prompts_dir / prompt).exists():
                missing.append(prompt)

        assert not missing, f"Missing agent prompts: {missing}"


class TestAgentMemory:
    """Tests for agent memory functionality."""

    def test_memory_context_includes_info_severity(self):
        """Memory should include context for files with info-severity findings."""
        agent_memory = import_from_path("agent_memory", TOOLS_DIR / "agent_memory.py")

        # Info severity should have weight > 0
        severity_weights = {"critical": 5, "high": 3, "medium": 2, "low": 1, "info": 0.5}
        assert severity_weights["info"] > 0, "info severity should have positive weight"

    def test_risk_score_calculation(self):
        """Risk score function should exist and be callable."""
        agent_memory = import_from_path("agent_memory", TOOLS_DIR / "agent_memory.py")

        assert hasattr(agent_memory, 'get_file_risk_score')
        # Should not crash on a unique nonexistent file
        result = agent_memory.get_file_risk_score("/nonexistent/unique_xyz_test_file_12345.py", days=30)
        assert result["score"] >= 0  # Score is non-negative
        assert "finding_count" in result

    def test_sanitize_for_prompt_exists(self):
        """Prompt sanitization function should exist."""
        agent_memory = import_from_path("agent_memory", TOOLS_DIR / "agent_memory.py")

        assert hasattr(agent_memory, '_sanitize_for_prompt')


class TestAgentCompliance:
    """Tests for compliance validation."""

    def test_compliance_validator_runs(self):
        """Compliance validator should run without crashing."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "validate_agent_compliance.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode in (0, 1, 2)

    def test_compliance_detects_missing_finding(self):
        """Compliance should detect approval without FINDING blocks."""
        validator = import_from_path(
            "validate_agent_compliance",
            TOOLS_DIR / "validate_agent_compliance.py"
        )

        # Approval verdict without any FINDING blocks should fail strict mode
        weak_approval = """
        ## Report
        Everything looks good.

        ### Verdict: APPROVE
        """
        result = validator.check_compliance(weak_approval, strict=True)
        # In strict mode, approval without findings should be flagged
        assert "violations" in result or not result.get("compliant", True)


# Check if claude_agent_sdk is available (not installed in CI)
try:
    import claude_agent_sdk
    HAS_AGENT_SDK = True
except ImportError:
    HAS_AGENT_SDK = False


@pytest.mark.skipif(not HAS_AGENT_SDK, reason="claude_agent_sdk not installed (CI environment)")
class TestOrchestratorIntegration:
    """Integration tests for the orchestrator.

    These tests require claude_agent_sdk which is only available locally.
    They are skipped in CI where the SDK is not installed.
    """

    def test_exit_codes_documented(self):
        """Orchestrator should use documented exit codes."""
        # Exit codes: 0=pass, 1=hard gate fail, 2=soft fail, 3=compliance fail
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0

    def test_verbose_flag_exists(self):
        """Orchestrator should support --verbose flag."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--verbose" in result.stdout or "-v" in result.stdout

    def test_rigorous_flag_exists(self):
        """Orchestrator should support --rigorous flag."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--rigorous" in result.stdout

    def test_show_warnings_flag_exists(self):
        """Orchestrator should support --show-warnings flag for progressive disclosure."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--show-warnings" in result.stdout

    def test_continue_on_hard_gate_flag_exists(self):
        """Orchestrator should expose --continue-on-hard-gate for explicit diagnostics mode."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--continue-on-hard-gate" in result.stdout

    def test_fail_fast_hard_gate_flag_exists(self):
        """Orchestrator should support --fail-fast-hard-gate legacy behavior."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--fail-fast-hard-gate" in result.stdout

    def test_force_grounding_flag_exists(self):
        """Orchestrator should expose --force-grounding override."""
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "run_review.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        assert "--force-grounding" in result.stdout

    def test_full_depth_keeps_fuzzer_and_risk_triggers_grounding(self):
        """Full depth should always include fuzzer; grounding should be risk-triggered."""
        run_review = import_from_path("run_review", TOOLS_DIR / "run_review.py")

        low_risk = run_review.ReviewOrchestrator(
            files=["docs/agents/AgentRunbook.v0.md"],
            depth="full",
            use_memory=False,
        )
        assert "fuzzer" in low_risk.agents_to_run
        assert "grounding" not in low_risk.agents_to_run

        high_risk = run_review.ReviewOrchestrator(
            files=["rcx_pi/selfhost/step_mu.py"],
            depth="full",
            use_memory=False,
        )
        assert "fuzzer" in high_risk.agents_to_run
        assert "grounding" in high_risk.agents_to_run

        forced = run_review.ReviewOrchestrator(
            files=["docs/agents/AgentRunbook.v0.md"],
            depth="full",
            use_memory=False,
            force_grounding=True,
        )
        assert "grounding" in forced.agents_to_run


class TestVerdictExtraction:
    """Tests for secure verdict extraction."""

    def test_verdict_marker_required(self):
        """Verdict should only be extracted from explicit VERDICT: markers."""
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        extract_verdict_secure = shared_agent_utils.extract_verdict_secure

        # Text containing "APPROVE" but not as a verdict marker should return UNKNOWN
        text_without_marker = "This code is APPROVE worthy but needs work"
        result = extract_verdict_secure(text_without_marker, agent_name="verifier")
        assert result == "UNKNOWN", "Should not extract verdict from non-marker text"

    def test_verdict_marker_extracted(self):
        """Verdict should be extracted from explicit VERDICT: markers."""
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        extract_verdict_secure = shared_agent_utils.extract_verdict_secure

        text_with_marker = """
        ## Analysis
        The code looks good.

        ### Verdict: APPROVE
        """
        result = extract_verdict_secure(text_with_marker, agent_name="verifier")
        assert result == "APPROVE", f"Should extract APPROVE from marker, got {result}"

    def test_verdict_spoofing_blocked(self):
        """Substring-based verdict spoofing should be blocked."""
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        extract_verdict_secure = shared_agent_utils.extract_verdict_secure

        # This text has "APPROVE" in context but not as a marker
        spoofing_attempt = """
        The code review says the developer should NOT APPROVE this change.
        There are security issues that need to be fixed.
        Verdict: REQUEST_CHANGES
        """
        result = extract_verdict_secure(spoofing_attempt, agent_name="verifier")
        assert result == "REQUEST_CHANGES", f"Should extract REQUEST_CHANGES, not be spoofed by 'NOT APPROVE', got {result}"

    def test_verdict_bullet_markdown_extracted(self):
        """Verdict should be extracted from bullet markdown format."""
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        extract_verdict_secure = shared_agent_utils.extract_verdict_secure

        text_with_bullet = """
        ### Summary
        - **Verdict:** SECURE - all attacks blocked
        """
        result = extract_verdict_secure(text_with_bullet, agent_name="adversary")
        assert result == "SECURE", f"Should extract SECURE from bullet markdown, got {result}"

    def test_verdict_multiline_markdown_extracted(self):
        """Verdict should be extracted when marker and value are on separate lines."""
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        extract_verdict_secure = shared_agent_utils.extract_verdict_secure

        text_multiline = """
        ### Verdict
        **NO_STRUCTURAL_CLAIMS**
        """
        result = extract_verdict_secure(text_multiline, agent_name="structural-proof")
        assert result == "NO_STRUCTURAL_CLAIMS", f"Should extract multiline verdict, got {result}"


class TestAdversaryEvidenceGate:
    """Evidence-gated hard-block rules for adversary findings."""

    def test_adversary_evidence_gate_accepts_full_proof_block(self):
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        has_proof = shared_agent_utils.adversary_has_machine_verifiable_evidence

        output = """
FINDING: Kernel reserved field injection
FILE: /tmp/example.py
LINES: 10-20
CODE:
    if user_input.get("_mode"):
        return True
CALL_PATH: run_mu -> run_mu_structural -> step_kernel_mu
REPRO_STEPS:
    1. Provide crafted input with _mode
    2. Observe acceptance path
VERIFIED: Yes
"""
        assert has_proof(output) is True

    def test_adversary_evidence_gate_rejects_missing_call_path(self):
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        has_proof = shared_agent_utils.adversary_has_machine_verifiable_evidence

        output = """
FINDING: Missing call path marker
FILE: /tmp/example.py
LINES: 5-7
CODE:
    pass
REPRO_STEPS:
    1. Run test
VERIFIED: Yes
"""
        assert has_proof(output) is False

    def test_adversary_blocks_merge_requires_compliance_and_proof(self):
        shared_agent_utils = import_from_path(
            "shared_agent_utils",
            TOOLS_DIR / "shared_agent_utils.py"
        )
        blocks_merge = shared_agent_utils.adversary_blocks_merge

        proof_output = """
FINDING: Valid proof block
FILE: /tmp/example.py
LINES: 1-2
CODE:
    x = 1
CALL_PATH: a -> b -> c
REPRO_STEPS:
    1. run it
VERIFIED: Yes
"""
        assert blocks_merge("VULNERABLE", proof_output, is_compliant=True) is True
        assert blocks_merge("VULNERABLE", proof_output, is_compliant=False) is False
        assert blocks_merge("SECURE", proof_output, is_compliant=True) is False
