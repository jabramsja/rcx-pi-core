"""
Pytest configuration for RCX tests.

Provides:
- Projection coverage tracking (enable with RCX_PROJECTION_COVERAGE=1)
- Skips tests that require optional modules (rcx_omega, scripts)
- Shared test utilities (apply_mu for Phase 4d integration)
- Hypothesis configuration for deterministic fuzzing
"""

import os
import pytest

from rcx_pi.eval_seed import NO_MATCH
from rcx_pi.match_mu import match_mu
from rcx_pi.subst_mu import subst_mu
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
    from hypothesis import settings  # Expert finding: removed unused Verbosity, Phase

    # CI profile: full fuzzing (default example counts from test decorators)
    settings.register_profile(
        "ci",
        print_blob=True,
        derandomize=False,
    )

    # Dev profile: fast fuzzing (50 examples max for rapid iteration)
    settings.register_profile(
        "dev",
        max_examples=50,
        print_blob=True,
        derandomize=False,
    )

    # Default profile (same as CI)
    settings.register_profile(
        "default",
        print_blob=True,
        derandomize=False,
    )

    # Load profile from environment: HYPOTHESIS_PROFILE=dev for fast local runs
    # Note: uses os imported at module level (line 11)
    profile = os.environ.get("HYPOTHESIS_PROFILE", "default")
    settings.load_profile(profile)

except ImportError:
    pass  # hypothesis not installed, skip configuration


# =============================================================================
# Shared Test Utilities
# =============================================================================

def apply_mu(projection: dict, value):
    """
    Apply a projection to a value using Mu-based match and substitute.

    This is the integration of match_mu + subst_mu (Phase 4d).
    Shared utility to avoid duplication across test files.

    Args:
        projection: Dict with "pattern" and "body" keys
        value: The value to match against the pattern

    Returns:
        The substituted body if pattern matches, NO_MATCH otherwise

    Raises:
        TypeError: If projection is not a dict
        KeyError: If projection missing pattern/body, or unbound variable in body
    """
    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection).__name__}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    bindings = match_mu(pattern, value)

    if bindings is NO_MATCH:
        return NO_MATCH

    return subst_mu(body, bindings)

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
    "test_enginenews_parity.py",
    "test_enginenews_fuzzer.py",
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
