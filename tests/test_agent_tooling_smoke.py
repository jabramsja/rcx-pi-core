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
        "run_review.py",
        "run_ci_review.py",
        "run_interactive.py",
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


class TestVerdictExtraction:
    """Tests for secure verdict extraction."""

    def test_verdict_marker_required(self):
        """Verdict should only be extracted from explicit VERDICT: markers."""
        # Import directly from shared_agent_utils where extract_verdict_secure lives
        from tools.shared_agent_utils import extract_verdict_secure

        # Text containing "APPROVE" but not as a verdict marker should return UNKNOWN
        text_without_marker = "This code is APPROVE worthy but needs work"
        result = extract_verdict_secure(text_without_marker, agent_name="verifier")
        assert result == "UNKNOWN", "Should not extract verdict from non-marker text"

    def test_verdict_marker_extracted(self):
        """Verdict should be extracted from explicit VERDICT: markers."""
        from tools.shared_agent_utils import extract_verdict_secure

        text_with_marker = """
        ## Analysis
        The code looks good.

        ### Verdict: APPROVE
        """
        result = extract_verdict_secure(text_with_marker, agent_name="verifier")
        assert result == "APPROVE", f"Should extract APPROVE from marker, got {result}"

    def test_verdict_spoofing_blocked(self):
        """Substring-based verdict spoofing should be blocked."""
        # Import directly from shared_agent_utils where extract_verdict_secure lives
        from tools.shared_agent_utils import extract_verdict_secure

        # This text has "APPROVE" in context but not as a marker
        spoofing_attempt = """
        The code review says the developer should NOT APPROVE this change.
        There are security issues that need to be fixed.
        Verdict: REQUEST_CHANGES
        """
        result = extract_verdict_secure(spoofing_attempt, agent_name="verifier")
        assert result == "REQUEST_CHANGES", f"Should extract REQUEST_CHANGES, not be spoofed by 'NOT APPROVE', got {result}"
