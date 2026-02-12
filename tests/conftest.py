"""
Pytest configuration for RCX tests.

Provides:
- Projection coverage tracking (enable with RCX_PROJECTION_COVERAGE=1)
- Skips tests that require optional modules (rcx_omega, scripts)
- Shared test utilities (run_until_done for kernel integration)
- Hypothesis configuration for deterministic fuzzing
"""

import os
import sys
from pathlib import Path

# Ensure repo root is at position 0 in sys.path for 'tools' imports
# pytest adds tests/ to sys.path which can shadow repo root's tools package
REPO_ROOT = Path(__file__).parent.parent
_repo_root_str = str(REPO_ROOT)
if sys.path[0] != _repo_root_str:
    if _repo_root_str in sys.path:
        sys.path.remove(_repo_root_str)
    sys.path.insert(0, _repo_root_str)

import pytest

from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.step_mu import clear_combined_kernel_cache

# =============================================================================
# Hypothesis Configuration (lossless optimization)
# =============================================================================
# - Database caches found examples for faster reruns (uses .hypothesis/ by default)
# - print_blob=True makes failures easy to reproduce
# - derandomize=False keeps search random but seeded for CI reproducibility
# NOTE: Do NOT set database=None - that DISABLES the database. Omit to use default.

try:
    from hypothesis import settings, HealthCheck

    # ==========================================================================
    # Hypothesis Profiles for CI Split
    # ==========================================================================
    # ci_fast: Quick feedback for PRs (~50 examples per test)
    # ci_full: Comprehensive fuzzing for dev merges/nightly (~500 examples)
    #
    # Usage:
    #   HYPOTHESIS_PROFILE=ci_fast pytest ...  # Fast gate (~3-5 min)
    #   HYPOTHESIS_PROFILE=ci_full pytest ...  # Full fuzz (~15-18 min)
    # ==========================================================================

    # Fast CI profile: quick feedback for PRs (50 examples)
    settings.register_profile(
        "ci_fast",
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=True,
        derandomize=False,
    )

    # Full CI profile: comprehensive fuzzing for dev/nightly (500 examples)
    settings.register_profile(
        "ci_full",
        max_examples=500,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=True,
        derandomize=False,
    )

    # Aliases for backward compatibility
    settings.register_profile(
        "dev",
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=True,
        derandomize=False,
    )

    settings.register_profile(
        "ci",
        max_examples=500,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=True,
        derandomize=False,
    )

    # Default profile: same as ci_fast for local development (fast feedback)
    # Use HYPOTHESIS_PROFILE=ci_full for comprehensive local fuzzing
    settings.register_profile(
        "default",
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
        print_blob=True,
        derandomize=False,
    )

    # Load profile from environment: HYPOTHESIS_PROFILE=ci_fast for fast CI
    profile = os.environ.get("HYPOTHESIS_PROFILE", "default")
    settings.load_profile(profile)

except ImportError:
    pass  # hypothesis not installed, skip configuration


# =============================================================================
# Shared Test Utilities
# =============================================================================
# NOTE: apply_mu was removed from here (9-agent Expert finding 2026-02-01).
# Tests should import from rcx_pi.step_mu which has assert_mu() validation.
# The conftest version lacked this validation, creating a parity gap.

# Skip tests that require optional modules not present in this repo
collect_ignore = [
    "test_semantic_goldens.py",     # requires rcx_omega
    "test_semantic_invariants.py",  # requires rcx_omega
    "test_normalize_graphviz_svg.py",  # requires scripts module
    "archive",  # archived tests (e.g., bytecode VM - superseded by kernel approach)
]

# SECURITY: These test files are CRITICAL and must NEVER be in collect_ignore
# Adding them to collect_ignore would silently disable security tests
# 7-agent adversary review finding (2026-01-30)
CRITICAL_TEST_FILES = frozenset({
    # Debt and security enforcement
    "test_debt_enforcement.py",
    "test_security_boundary_fuzzer.py",
    "test_seed_integrity_fuzzer.py",
    # Core algorithm parity tests
    "test_match_parity.py",
    "test_subst_parity.py",
    "test_kernel_projections.py",
    # Security tool grounding tests (verify security checks actually work)
    "test_contraband_detection.py",
    "test_seed_police_detection.py",
    "test_ast_police_detection.py",
    "test_check_test_theater_detection.py",
    # Adversarial and security fuzzer tests
    "test_eval_seed_adversary.py",
    "test_kernel_security_fuzzer.py",
    # Self-hosting verification (L1/L2 compliance)
    "test_self_hosting_v0.py",
    # Grounding gap verification
    "test_phase8b_grounding_gaps.py",
    # Structural trace fuzzer (closure detection robustness - 7-agent critical gap)
    "test_structural_trace_fuzzer.py",
    # Boundary validation fuzzers (9-agent review 2026-01-30)
    "test_boundary_validation_fuzzer.py",
    "test_kernel_bridge_fuzzer.py",
    # L2 cursor grounding tests (structural cursor operations)
    "test_l2_cursor_grounding.py",
    # L3 Parity tests - CRITICAL for substrate portability (9-agent review 2026-01-31)
    "test_match_v2_parity.py",
    "test_subst_v2_parity.py",
    "test_parity_python.py",
    "test_step_mu_parity.py",
    # EngineNews tests - CRITICAL for closure detection (9-agent review 2026-01-31)
    "test_recurrence_parity.py",
    "test_recurrence_fuzzer.py",
    # mu_equal parity fuzzer - CRITICAL for binding conflict detection (9-agent review 2026-01-31)
    "test_mu_equal_parity_fuzzer.py",
    # L3 JS automated parity - CRITICAL for substrate portability (9-agent round 2)
    "test_js_parity_automated.py",
    # Normalization/bindings roundtrip fuzzers - CRITICAL for kernel boundary (9-agent round 2)
    "test_normalization_roundtrip.py",
    "test_normalization_roundtrip_fuzzer.py",
    "test_bindings_roundtrip_fuzzer.py",
    # Structural trace and integration (9-agent round 3 - advisor critical gap)
    "test_structural_trace.py",
    "test_eval_seed_parity.py",
    "test_eval_seed_v0.py",
    # Kernel recommended fuzzers - CRITICAL for kernel security (9-agent recommendations)
    "test_kernel_recommended_fuzzers.py",
    # Boundary validation fuzzers - CRITICAL for malformed input rejection (9-agent round 4)
    "test_normalize_malformed_fuzzer.py",
    "test_denormalize_type_confusion_fuzzer.py",
    # Entropy budget enforcement - CRITICAL for determinism (9-agent round 4)
    "test_entropy_budget_enforcement.py",
    # Agent compliance validator - CRITICAL for guardrail enforcement (9-agent self-review)
    "test_validate_agent_compliance.py",
    # Spec ground truth tests - CRITICAL for catching "both wrong in same way" bugs
    "test_spec_ground_truth.py",
    # Agent fuzzer findings #1017-#1021 (9-agent review, 2026-02-07)
    "test_cross_seed_boundary_fuzzer.py",
    "test_algorithm_oscillation_fuzzer.py",
    "test_nonlinear_bridge_fuzzer.py",
    "test_normalized_injection_fuzzer.py",
    "test_trace_malformation_fuzzer.py",
})


def pytest_configure(config):
    """Configure pytest: enforce determinism, enable coverage if requested."""
    # Enforce PYTHONHASHSEED=0 for deterministic dict ordering
    hashseed = os.environ.get("PYTHONHASHSEED")
    if hashseed != "0":
        raise RuntimeError(
            f"PYTHONHASHSEED must be '0' for deterministic tests, got {hashseed!r}. "
            "Run with: PYTHONHASHSEED=0 pytest ..."
        )

    # SECURITY: Verify critical test files are NOT in collect_ignore
    # This prevents silently disabling security tests (7-agent adversary finding)
    ignored_critical = CRITICAL_TEST_FILES & set(collect_ignore)
    if ignored_critical:
        raise RuntimeError(
            f"CRITICAL TEST FILES in collect_ignore: {ignored_critical}. "
            "These files contain security tests and MUST NOT be ignored. "
            "Remove them from collect_ignore."
        )

    # Enable projection coverage if requested
    if os.environ.get("RCX_PROJECTION_COVERAGE") == "1":
        from rcx_pi.projection_coverage import coverage
        coverage.enable()
        coverage.reset()


def pytest_collection_modifyitems(config, items):
    """Auto-mark hypothesis property-based tests with the 'fuzzer' marker.

    This avoids blanket-marking entire files (which would skip deterministic
    tests colocated with hypothesis tests).  Any collected test item where
    ``item.obj.is_hypothesis_test`` is True gets the ``fuzzer`` marker so
    that ``-m "not fuzzer"`` deselects *only* the generated property tests.
    """
    fuzzer_marker = pytest.mark.fuzzer
    for item in items:
        if getattr(item.obj, "is_hypothesis_test", False):
            item.add_marker(fuzzer_marker)


def pytest_unconfigure(config):
    """Print projection coverage report at end of test run."""
    if os.environ.get("RCX_PROJECTION_COVERAGE") == "1":
        from rcx_pi.projection_coverage import coverage
        print("\n")
        print(coverage.report())


@pytest.fixture(autouse=True)
def reset_state_between_tests():
    """Reset state before each test to prevent cross-test pollution.

    Some tests (e.g., test_step_budget.py) set custom budget limits.
    Without this fixture, subsequent tests may fail with "step limit exceeded"
    if the budget was left in an active state with a low limit.

    9-agent round 2 (Expert finding): Also clear kernel projection cache
    to prevent stale cache pollution when tests mock projections.
    """
    reset_step_budget()
    clear_combined_kernel_cache()
    yield
    reset_step_budget()
    clear_combined_kernel_cache()


# =============================================================================
# CI Skip Hardening (RCX_CI=1 converts skips to failures)
# =============================================================================

def skip_or_fail_in_ci(reason: str):
    """
    Skip test locally, but FAIL in CI (when RCX_CI=1).

    Use this for tests that skip on external failures (e.g., CLI failures).
    In CI, we want these to be hard failures so regressions aren't masked.

    Usage:
        if exit_code != 0:
            skip_or_fail_in_ci(f"CLI failed with exit code {exit_code}")
    """
    if os.environ.get("RCX_CI") == "1":
        pytest.fail(f"CI FAILURE (would skip locally): {reason}")
    else:
        pytest.skip(reason)


# =============================================================================
# Kernel Execution Utility (Expert finding: consolidated from duplicates)
# =============================================================================

def run_until_done(projections, initial, max_steps: int = 100):
    """
    Run projections until kernel.unwrap fires (produces non-kernel output).

    Consolidated from duplicate implementations in test_phase7c_integration.py
    and test_parity_python.py (7-agent review, Expert finding).

    Args:
        projections: List of Mu projections
        initial: Initial Mu value to evaluate
        max_steps: Maximum steps before timeout (default 100)

    Returns:
        Tuple of (final_result, trace, is_stall)
        - final_result: The final Mu value
        - trace: List of all intermediate states
        - is_stall: True if evaluation stalled (no change or reached final state)
    """
    from rcx_pi.selfhost.eval_seed import step
    from rcx_pi.selfhost.mu_type import mu_equal

    trace = [initial]
    current = initial

    for _ in range(max_steps):
        result = step(projections, current)
        trace.append(result)

        # Check for stall (no change)
        if mu_equal(result, current):
            return result, trace, True

        current = result

        # Check if we've reached final result (not a kernel/match/subst state)
        if isinstance(result, dict):
            # Check for mode markers (internal state format)
            mode = result.get("_mode") or result.get("mode")
            # Check for entry format (match/subst requests)
            is_entry_format = "match" in result or "subst" in result
            # Check for kernel entry format
            is_kernel_entry = "_step" in result

            if mode is None and not is_entry_format and not is_kernel_entry:
                # No mode field and not entry format - final unwrapped result
                return result, trace, True
        else:
            # Primitive result
            return result, trace, True

    return current, trace, False
