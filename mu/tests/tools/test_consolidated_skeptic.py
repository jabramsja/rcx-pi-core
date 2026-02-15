"""Tests for consolidated skeptic (run_skeptic.py).

Verifies:
1. Per-agent verdict mapping (OVERRIDE targets one agent only)
2. AGENT: ALL applies to every approved agent
3. Malformed output (missing AGENT: marker) degrades to warning
4. Single skeptic invocation in rigorous mode (no sequential fan-out)
"""
import ast
import sys
import os
import types
from pathlib import Path
from unittest import mock

import pytest

# Fix `tools` package in sys.modules.
# pytest's collection of tests/tools/ pre-loads `tools` in sys.modules pointing
# at tests/tools/__init__.py, shadowing the repo-root tools/ package. We need to
# fix this before importing run_skeptic, which uses `from tools.* import ...`.
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

_real_tools_init = os.path.join(_repo_root, 'tools', '__init__.py')
if 'tools' in sys.modules:
    _existing = sys.modules['tools']
    _existing_file = getattr(_existing, '__file__', '') or ''
    if 'tests' in _existing_file:
        # Wrong tools package loaded — replace with real one
        _real_tools = types.ModuleType('tools')
        _real_tools.__file__ = _real_tools_init
        _real_tools.__path__ = [os.path.join(_repo_root, 'tools')]
        _real_tools.__package__ = 'tools'
        sys.modules['tools'] = _real_tools

# Import parsing helpers without triggering SDK import.
# run_skeptic imports claude_agent_sdk at module level, which may fail on
# architecture-mismatched environments (e.g. arm64 Python + x86_64 wheel).
# We mock the SDK so only the pure-Python parsing functions are loaded.
_sdk_mock = mock.MagicMock()
with mock.patch.dict(sys.modules, {
    "claude_agent_sdk": _sdk_mock,
}):
    # Force re-import if already cached with real SDK
    for mod_name in list(sys.modules):
        if "run_skeptic" in mod_name or "agent_runner_common" in mod_name:
            del sys.modules[mod_name]
    from tools.run_skeptic import (
        _extract_per_agent_verdicts,
        _extract_global_concerns,
        _extract_verdict,
        _validate_concern_tags,
    )


# =============================================================================
# Test 1: Consolidated override maps to one agent only
# =============================================================================

class TestOverrideMapsToOneAgent:
    """AGENT_VERDICT: override on one agent must NOT affect others."""

    def test_single_override_leaves_others_confirmed(self):
        text = """
## Consolidated Skeptic Review

### Per-Agent Assessment

AGENT_VERDICT: verifier: CONFIRMED
AGENT_VERDICT: adversary: OVERRIDE
AGENT_VERDICT: expert: CONFIRMED
AGENT_VERDICT: structural-proof: CONFIRMED

### Concerns Raised

AGENT: adversary
CONCERN: Adversary missed prototype pollution in denormalize
FILE: mu/host/js/eval_step.js
LINES: 770-780
SEVERITY: HIGH
VERIFIED: Yes

### Final Assessment
OVERALL_VERDICT: CONCERNS
"""
        agent_names = ["verifier", "adversary", "expert", "structural-proof"]
        verdicts = _extract_per_agent_verdicts(text, agent_names)

        assert verdicts["adversary"] == "OVERRIDE"
        assert verdicts["verifier"] == "CONFIRMED"
        assert verdicts["expert"] == "CONFIRMED"
        assert verdicts["structural-proof"] == "CONFIRMED"

    def test_multiple_overrides_target_individually(self):
        text = """
AGENT_VERDICT: verifier: OVERRIDE
AGENT_VERDICT: adversary: OVERRIDE
AGENT_VERDICT: expert: CONFIRMED
"""
        verdicts = _extract_per_agent_verdicts(text, ["verifier", "adversary", "expert"])

        assert verdicts["verifier"] == "OVERRIDE"
        assert verdicts["adversary"] == "OVERRIDE"
        assert verdicts["expert"] == "CONFIRMED"

    def test_missing_agent_verdict_defaults_to_unknown(self):
        """Agents not explicitly evaluated by skeptic default to UNKNOWN (fail-closed)."""
        text = "AGENT_VERDICT: verifier: CONCERNS"
        verdicts = _extract_per_agent_verdicts(text, ["verifier", "adversary", "expert"])

        assert verdicts["verifier"] == "CONCERNS"
        assert verdicts["adversary"] == "UNKNOWN"
        assert verdicts["expert"] == "UNKNOWN"

    def test_empty_output_defaults_to_unknown_fail_closed(self):
        """When skeptic output has NO parsed verdicts, all agents default to UNKNOWN (fail-closed)."""
        text = "Some output with no AGENT_VERDICT markers at all."
        verdicts = _extract_per_agent_verdicts(text, ["verifier", "adversary", "expert"])

        assert verdicts["verifier"] == "UNKNOWN"
        assert verdicts["adversary"] == "UNKNOWN"
        assert verdicts["expert"] == "UNKNOWN"


# =============================================================================
# Test 2: AGENT: ALL applies to every approved agent
# =============================================================================

class TestAgentAllApplies:
    """AGENT: ALL concerns must be visible for every agent."""

    def test_agent_all_extracts_global_concerns(self):
        text = """
### Global Blind Spots

AGENT: ALL
CONCERN: No agent checked for recursive stack overflow in match()
FILE: rcx_pi/selfhost/step_mu.py
LINES: 200-210
SEVERITY: MEDIUM
VERIFIED: Yes

AGENT: verifier
CONCERN: Minor formatting issue
FILE: tools/run_review.py
LINES: 100-105
SEVERITY: LOW
VERIFIED: Yes
"""
        concerns = _extract_global_concerns(text)
        assert len(concerns) == 1
        assert "recursive stack overflow" in concerns[0]

    def test_multiple_agent_all_concerns(self):
        text = """
AGENT: ALL
CONCERN: Missing input validation on projection patterns

AGENT: ALL
CONCERN: No timeout on structural recursion
"""
        concerns = _extract_global_concerns(text)
        assert len(concerns) == 2
        assert "input validation" in concerns[0]
        assert "timeout" in concerns[1]

    def test_agent_all_does_not_contaminate_per_agent(self):
        """AGENT: ALL should not create per-agent verdicts."""
        text = """
AGENT_VERDICT: verifier: CONFIRMED
AGENT_VERDICT: expert: CONFIRMED

AGENT: ALL
CONCERN: Global blind spot found
"""
        verdicts = _extract_per_agent_verdicts(text, ["verifier", "expert"])
        assert verdicts["verifier"] == "CONFIRMED"
        assert verdicts["expert"] == "CONFIRMED"
        # ALL is not an agent verdict — it's a separate concern channel


# =============================================================================
# Test 3: Malformed output degrades to warning, not silent pass
# =============================================================================

class TestMalformedOutputDegradesToWarning:
    """Concerns without AGENT: tag must produce warnings, not silently pass."""

    def test_untagged_concern_produces_warning(self):
        text = """
### Concerns Raised

CONCERN: Found a potential issue with match recursion
FILE: rcx_pi/selfhost/step_mu.py
LINES: 150-160
SEVERITY: MEDIUM
VERIFIED: Yes
"""
        warnings = _validate_concern_tags(text, ["verifier", "adversary"])
        assert len(warnings) == 1
        assert "UNTAGGED CONCERN" in warnings[0]
        assert "match recursion" in warnings[0]

    def test_tagged_concern_produces_no_warning(self):
        text = """
AGENT: adversary
CONCERN: Budget amplification possible
FILE: rcx_pi/selfhost/projection_runner.py
LINES: 50-60
SEVERITY: HIGH
VERIFIED: Yes
"""
        warnings = _validate_concern_tags(text, ["verifier", "adversary"])
        assert len(warnings) == 0

    def test_unknown_agent_name_produces_warning(self):
        text = """
AGENT: nonexistent_agent
CONCERN: Something was missed
FILE: foo.py
LINES: 1-5
SEVERITY: LOW
VERIFIED: Yes
"""
        warnings = _validate_concern_tags(text, ["verifier", "adversary"])
        assert len(warnings) == 1
        assert "UNKNOWN AGENT" in warnings[0]

    def test_agent_all_is_valid(self):
        text = """
AGENT: ALL
CONCERN: Global blind spot
FILE: foo.py
LINES: 1-5
SEVERITY: MEDIUM
VERIFIED: Yes
"""
        warnings = _validate_concern_tags(text, ["verifier", "adversary"])
        assert len(warnings) == 0

    def test_mixed_tagged_and_untagged(self):
        text = """
AGENT: verifier
CONCERN: Verifier missed X
FILE: a.py
LINES: 1-2
SEVERITY: LOW
VERIFIED: Yes

CONCERN: Orphan concern without agent tag
FILE: b.py
LINES: 3-4
SEVERITY: MEDIUM
VERIFIED: Yes

AGENT: ALL
CONCERN: Global issue
FILE: c.py
LINES: 5-6
SEVERITY: LOW
VERIFIED: Yes
"""
        warnings = _validate_concern_tags(text, ["verifier", "adversary"])
        assert len(warnings) == 1
        assert "UNTAGGED CONCERN" in warnings[0]
        assert "Orphan concern" in warnings[0]


# =============================================================================
# Test 4: Single skeptic invocation in rigorous mode
# =============================================================================

class TestSingleSkepticInvocation:
    """Rigorous mode must call run_consolidated_skeptic once, not N+1 times."""

    def test_one_consolidated_call_not_per_agent(self):
        """Verify run_review calls run_consolidated_skeptic exactly once,
        not run_skeptic N times + convergence check."""

        review_path = Path(__file__).parent.parent.parent / "tools" / "run_review.py"
        tree = ast.parse(review_path.read_text())

        # Find the rigorous block start dynamically by locating the
        # `if args.rigorous and approvals_to_challenge:` guard.
        rigorous_line = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and hasattr(node, 'test'):
                src = ast.dump(node.test)
                if "rigorous" in src and "approvals_to_challenge" in src:
                    rigorous_line = node.lineno
                    break
        assert rigorous_line is not None, (
            "Could not find 'if args.rigorous and approvals_to_challenge' in run_review.py"
        )

        # Find all calls to run_skeptic and run_consolidated_skeptic
        run_skeptic_calls = []
        run_consolidated_calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    if func.id == "run_skeptic":
                        run_skeptic_calls.append(node.lineno)
                    elif func.id == "run_consolidated_skeptic":
                        run_consolidated_calls.append(node.lineno)
                elif isinstance(func, ast.Attribute):
                    if func.attr == "run_skeptic":
                        run_skeptic_calls.append(node.lineno)
                    elif func.attr == "run_consolidated_skeptic":
                        run_consolidated_calls.append(node.lineno)

        # There should be exactly 1 consolidated call in the rigorous block
        assert len(run_consolidated_calls) == 1, (
            f"Expected 1 run_consolidated_skeptic call, found {len(run_consolidated_calls)} "
            f"at lines {run_consolidated_calls}"
        )

        # There should be NO legacy run_skeptic calls in the rigorous section
        # (run_skeptic may still exist for CLI/backward-compat but not in the
        # rigorous orchestration path)
        rigorous_skeptic_calls = [ln for ln in run_skeptic_calls if ln > rigorous_line]
        assert len(rigorous_skeptic_calls) == 0, (
            f"Found {len(rigorous_skeptic_calls)} legacy run_skeptic calls in rigorous section "
            f"at lines {rigorous_skeptic_calls}. Should use run_consolidated_skeptic only."
        )


# =============================================================================
# Verdict extraction edge cases
# =============================================================================

class TestVerdictExtraction:
    """Verify verdict parsing handles edge cases."""

    def test_overall_verdict_extracted(self):
        assert _extract_verdict("Skeptic Verdict: CONFIRMED") == "CONFIRMED"
        assert _extract_verdict("Skeptic Verdict: OVERRIDE") == "OVERRIDE"
        assert _extract_verdict("Skeptic Verdict: CONCERNS") == "CONCERNS"

    def test_no_verdict_returns_unknown(self):
        assert _extract_verdict("No verdict here") == "UNKNOWN"

    def test_challenge_result_fallback(self):
        assert _extract_verdict("CHALLENGE_RESULT: REJECTED") == "OVERRIDE"
        assert _extract_verdict("CHALLENGE_RESULT: CONFIRMED") == "CONFIRMED"

    def test_case_insensitive_agent_verdict(self):
        text = "AGENT_VERDICT: Verifier: confirmed"
        verdicts = _extract_per_agent_verdicts(text, ["verifier"])
        assert verdicts["verifier"] == "CONFIRMED"
