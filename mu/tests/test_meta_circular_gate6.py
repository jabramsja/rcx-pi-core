"""
Gate 6 Integration Tests: META_CIRCULAR recurrence and exhaustion.

These tests verify that recurrence.v1 and exhaustion.v1 are declared
META_CIRCULAR and run via structural kernel + bridge.

Key verification:
1. Seeds declare execution_layer: META_CIRCULAR
2. Seeds require bootstrap_structural.v1 bridge for non-linear pattern support
3. Kernel with bridge (kernel.v1 + match.v2 + bootstrap_structural + subst.v2) loads correctly
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.step_mu import (
    run_algorithm_meta_circular,
    load_combined_kernel_with_bridge_projections,
    clear_combined_kernel_cache,
)
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal
from tests.conftest import run_until_stable

pytestmark = pytest.mark.slow

# JSON null -> Python None alias for readability
null = None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def recurrence_projections() -> list:
    """Load recurrence projections from seed file."""
    seed = load_verified_seed(get_seed_path("recurrence.v1.json"))
    return seed["projections"]


@pytest.fixture(scope="module")
def exhaustion_projections() -> list:
    """Load exhaustion projections from seed file."""
    seed = load_verified_seed(get_seed_path("exhaustion.v1.json"))
    return seed["projections"]


@pytest.fixture(scope="module")
def recurrence_seed() -> dict:
    """Load full recurrence seed for meta inspection."""
    return load_verified_seed(get_seed_path("recurrence.v1.json"))


@pytest.fixture(scope="module")
def exhaustion_seed() -> dict:
    """Load full exhaustion seed for meta inspection."""
    return load_verified_seed(get_seed_path("exhaustion.v1.json"))


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset kernel cache between tests."""
    clear_combined_kernel_cache()
    yield
    clear_combined_kernel_cache()


def run_until_stable_meta_circular(projections: list, value: dict, max_steps: int = 100) -> dict:
    """Run projections using META_CIRCULAR layer (run_algorithm_meta_circular) until stall."""
    reset_step_budget()
    current = value
    for _ in range(max_steps):
        result = run_algorithm_meta_circular(projections, current)
        if mu_equal(result, current):
            return result
        current = result
    return current


# =============================================================================
# Meta Declaration Tests
# =============================================================================


class TestMetaCircularDeclaration:
    """Verify seeds declare META_CIRCULAR execution layer."""

    def test_recurrence_declares_meta_circular(self, recurrence_seed):
        """recurrence.v1 must declare execution_layer: META_CIRCULAR."""
        meta = recurrence_seed["meta"]
        assert meta.get("execution_layer") == "META_CIRCULAR", (
            f"Expected META_CIRCULAR, got {meta.get('execution_layer')}"
        )
        assert meta.get("meta_circular_capable") is True, (
            "recurrence.v1 must declare meta_circular_capable: true"
        )

    def test_exhaustion_declares_meta_circular(self, exhaustion_seed):
        """exhaustion.v1 must declare execution_layer: META_CIRCULAR."""
        meta = exhaustion_seed["meta"]
        assert meta.get("execution_layer") == "META_CIRCULAR", (
            f"Expected META_CIRCULAR, got {meta.get('execution_layer')}"
        )
        assert meta.get("meta_circular_capable") is True, (
            "exhaustion.v1 must declare meta_circular_capable: true"
        )

    def test_recurrence_requires_bridge(self, recurrence_seed):
        """recurrence.v1 must require bootstrap_structural bridge for non-linear patterns."""
        meta = recurrence_seed["meta"]
        assert meta.get("requires_bridge") == "bootstrap_structural.v1", (
            f"Expected requires_bridge: bootstrap_structural.v1, got {meta.get('requires_bridge')}"
        )

    def test_exhaustion_requires_bridge(self, exhaustion_seed):
        """exhaustion.v1 must require bootstrap_structural bridge for non-linear patterns."""
        meta = exhaustion_seed["meta"]
        assert meta.get("requires_bridge") == "bootstrap_structural.v1", (
            f"Expected requires_bridge: bootstrap_structural.v1, got {meta.get('requires_bridge')}"
        )


# =============================================================================
# Recurrence Meta-Circular Tests
# =============================================================================


class TestRecurrenceMetaCircular:
    """Test recurrence detection through meta-circular kernel.

    Algorithm seeds run through run_algorithm_meta_circular() which now uses
    step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")
    by default.
    """

    def test_no_closure_meta_circular(self, recurrence_projections):
        """No closure detected via meta-circular kernel."""
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": null
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert result.get("closure_detected") is False
        assert result.get("tau_step") is None
        assert result.get("final_result") == "final"

    def test_closure_detected_meta_circular(self, recurrence_projections):
        """Closure detected when state recurs (non-linear pattern match)."""
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": "A", "projection": "p3"},
                            "tail": null
                        }
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == 2  # Step where state A recurred
        assert result.get("final_result") == "final"

    def test_recurrence_parity_no_closure(self, recurrence_projections):
        """Meta-circular produces same result as bootstrap for no-closure case."""
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "X", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "Y", "projection": "p2"},
                        "tail": null
                    }
                },
                "result": "done"
            }
        }

        bootstrap_result = run_until_stable(recurrence_projections, input_data)
        meta_result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert mu_equal(bootstrap_result, meta_result), (
            f"Parity violation:\n"
            f"  Bootstrap: {bootstrap_result}\n"
            f"  Meta-circular: {meta_result}"
        )

    def test_recurrence_parity_with_closure(self, recurrence_projections):
        """Meta-circular produces same result as bootstrap for closure case."""
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": {"value": 1}, "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": {"value": 2}, "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": {"value": 1}, "projection": "p3"},
                            "tail": null
                        }
                    }
                },
                "result": "done"
            }
        }

        bootstrap_result = run_until_stable(recurrence_projections, input_data)
        meta_result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert mu_equal(bootstrap_result, meta_result), (
            f"Parity violation:\n"
            f"  Bootstrap: {bootstrap_result}\n"
            f"  Meta-circular: {meta_result}"
        )


# =============================================================================
# Exhaustion Meta-Circular Tests
# =============================================================================


class TestExhaustionMetaCircular:
    """Test exhaustion detection through meta-circular kernel.

    Algorithm seeds run through run_algorithm_meta_circular() which now uses
    step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")
    by default.
    """

    def test_no_tau_continues_meta_circular(self, exhaustion_projections):
        """No tau_step means no exhaustion possible (meta-circular).

        This test passes because exhaustion.init_null terminates immediately
        without entering the intermediate state machine.
        """
        input_data = {
            "_detect_exhaustion": {
                "trace": null,
                "frozen": null,
                "tau_step": null,
                "operator_ids": null
            }
        }

        result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert result.get("exhaustion_detected") is False
        assert result.get("action") == "continue"

    def test_single_op_exhausted_meta_circular(self, exhaustion_projections):
        """Same operator since tau_step should be frozen (meta-circular)."""
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op1"},
                        "tail": null
                    }
                },
                "frozen": null,
                "tau_step": 0,
                "operator_ids": {"head": "op1", "tail": null}
            }
        }

        result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert result.get("exhaustion_detected") is True
        assert result.get("operator_to_freeze") == "op1"
        assert result.get("action") == "freeze"

    def test_different_op_not_exhausted_meta_circular(self, exhaustion_projections):
        """Different operator after tau_step means not exhausted (meta-circular)."""
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op2"},
                        "tail": null
                    }
                },
                "frozen": null,
                "tau_step": 0,
                "operator_ids": {
                    "head": "op1",
                    "tail": {"head": "op2", "tail": null}
                }
            }
        }

        result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert result.get("exhaustion_detected") is False
        assert result.get("action") == "continue"

    def test_exhaustion_parity_no_tau(self, exhaustion_projections):
        """Meta-circular produces same result as bootstrap for no-tau case."""
        input_data = {
            "_detect_exhaustion": {
                "trace": null,
                "frozen": null,
                "tau_step": null,
                "operator_ids": null
            }
        }

        bootstrap_result = run_until_stable(exhaustion_projections, input_data)
        meta_result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert mu_equal(bootstrap_result, meta_result), (
            f"Parity violation:\n"
            f"  Bootstrap: {bootstrap_result}\n"
            f"  Meta-circular: {meta_result}"
        )

    def test_exhaustion_parity_with_exhaustion(self, exhaustion_projections):
        """Meta-circular produces same result as bootstrap for exhaustion case."""
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op1"},
                        "tail": null
                    }
                },
                "frozen": null,
                "tau_step": 0,
                "operator_ids": {"head": "op1", "tail": null}
            }
        }

        bootstrap_result = run_until_stable(exhaustion_projections, input_data)
        meta_result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert mu_equal(bootstrap_result, meta_result), (
            f"Parity violation:\n"
            f"  Bootstrap: {bootstrap_result}\n"
            f"  Meta-circular: {meta_result}"
        )


# =============================================================================
# Kernel Loading Tests
# =============================================================================


class TestKernelWithBridgeLoading:
    """Test that kernel.v1 + match.v2 + bootstrap_structural + subst.v2 loads correctly."""

    def test_kernel_with_bridge_projections_loaded(self):
        """Verify combined kernel with bridge projections load correctly."""
        projs = load_combined_kernel_with_bridge_projections()

        # kernel.v1 = 7, match.v2 = 8, bridge = 5, subst.v2 = 12 = 32
        assert len(projs) == 32, f"Expected 32 projections, got {len(projs)}"

    def test_kernel_includes_bridge(self):
        """Verify combined kernel includes bridge projections."""
        projs = load_combined_kernel_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        # Bridge projections should be present
        assert "bridge.var.check_existing" in ids
        assert "bridge.lookup.found_same" in ids
        assert "bridge.lookup.found_different" in ids
        assert "bridge.lookup.not_found" in ids

    def test_kernel_has_match_var(self):
        """Verify match.var is present (bridge intercepts before it)."""
        projs = load_combined_kernel_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        # match.var is still present, bridge intercepts before it
        assert "match.var" in ids, "match.var should be present"
        # Verify bridge comes before match.var
        bridge_idx = ids.index("bridge.var.check_existing")
        match_var_idx = ids.index("match.var")
        assert bridge_idx < match_var_idx, "bridge must come before match.var"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestMetaCircularEdgeCases:
    """Edge cases for meta-circular execution.

    Tests verify boundary conditions and complex state handling through
    run_algorithm_meta_circular().
    """

    def test_empty_trace_recurrence(self, recurrence_projections):
        """Empty trace should return no closure (meta-circular).

        This test passes because recurrence.end_of_trace terminates immediately
        when _current is null without entering the state machine.
        """
        input_data = {
            "_detect_closure": {
                "trace": null,
                "result": "done"
            }
        }

        result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert result.get("closure_detected") is False

    def test_complex_state_equality(self, recurrence_projections):
        """Complex nested states should compare correctly (non-linear)."""
        complex_state = {"nested": {"deep": [1, 2, 3]}}
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": complex_state, "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": {"other": "state"}, "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": complex_state, "projection": "p3"},
                            "tail": null
                        }
                    }
                },
                "result": "done"
            }
        }

        result = run_until_stable_meta_circular(recurrence_projections, input_data)

        assert result.get("closure_detected") is True
        assert result.get("tau_step") == 2

    def test_already_frozen_operator(self, exhaustion_projections):
        """Already frozen operator should be skipped (meta-circular)."""
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op1"},
                        "tail": null
                    }
                },
                "frozen": {"head": "op1", "tail": null},  # Already frozen
                "tau_step": 0,
                "operator_ids": {"head": "op1", "tail": null}
            }
        }

        result = run_until_stable_meta_circular(exhaustion_projections, input_data)

        assert result.get("exhaustion_detected") is False
        assert result.get("action") == "already_frozen"
