"""
Tests for step budget infrastructure (ACTIVE in kernel.py).

The step budget is cross-call resource accounting used by:
- match_mu.py
- subst_mu.py
- classify_mu.py
(projection_runner.py retired in Wave 3F)

This is ACTIVE infrastructure, NOT deprecated like the Kernel class.
See kernel.py lines 67-155 for implementation.
"""

import threading
import pytest

from rcx_pi.selfhost.kernel import (
    get_step_budget,
    reset_step_budget,
    MAX_PROJECTION_STEPS,
)


class TestStepBudgetBasics:
    """Basic step budget functionality."""

    def setup_method(self):
        """Reset budget before each test."""
        reset_step_budget()

    def test_get_step_budget_returns_budget(self):
        """get_step_budget() returns a budget object."""
        budget = get_step_budget()
        assert hasattr(budget, "start")
        assert hasattr(budget, "stop")
        assert hasattr(budget, "consume")
        assert hasattr(budget, "get_remaining")
        assert hasattr(budget, "get_total")

    def test_budget_inactive_by_default(self):
        """Budget is inactive until start() called."""
        budget = get_step_budget()
        assert budget.is_active() is False

    def test_budget_start_activates(self):
        """start() activates the budget."""
        budget = get_step_budget()
        budget.start()
        assert budget.is_active() is True
        budget.stop()

    def test_budget_stop_deactivates(self):
        """stop() deactivates the budget."""
        budget = get_step_budget()
        budget.start()
        budget.stop()
        assert budget.is_active() is False

    def test_consume_tracks_steps(self):
        """consume() increments total steps."""
        budget = get_step_budget()
        budget.start()

        assert budget.get_total() == 0
        budget.consume(10)
        assert budget.get_total() == 10
        budget.consume(5)
        assert budget.get_total() == 15

        budget.stop()

    def test_get_remaining_accuracy(self):
        """get_remaining() returns correct value."""
        budget = get_step_budget()
        budget.start(limit=100)

        assert budget.get_remaining() == 100
        budget.consume(30)
        assert budget.get_remaining() == 70
        budget.consume(70)
        assert budget.get_remaining() == 0

        budget.stop()

    def test_consume_inactive_is_noop(self):
        """consume() does nothing when inactive."""
        budget = get_step_budget()
        # Don't call start()
        budget.consume(100)  # Should not raise
        assert budget.get_total() == 0  # Not tracked


class TestStepBudgetLimits:
    """Step budget limit enforcement."""

    def setup_method(self):
        """Reset budget before each test."""
        reset_step_budget()

    def test_exceed_limit_raises(self):
        """Exceeding budget limit raises RuntimeError."""
        budget = get_step_budget()
        budget.start(limit=100)

        budget.consume(50)  # OK
        budget.consume(50)  # OK (at limit)

        with pytest.raises(RuntimeError, match=r"limit exceeded"):
            budget.consume(1)  # Over limit

        budget.stop()

    def test_default_limit_is_max_projection_steps(self):
        """Default limit is MAX_PROJECTION_STEPS."""
        budget = get_step_budget()
        budget.start()  # No explicit limit

        assert budget.get_remaining() == MAX_PROJECTION_STEPS
        budget.stop()

    def test_custom_limit(self):
        """Custom limit overrides default."""
        budget = get_step_budget()
        budget.start(limit=50)

        assert budget.get_remaining() == 50
        budget.stop()

    def test_error_message_includes_details(self):
        """Error message includes limit and total."""
        budget = get_step_budget()
        budget.start(limit=100)
        budget.consume(100)

        try:
            budget.consume(10)
            pytest.fail("Should have raised")
        except RuntimeError as e:
            msg = str(e)
            assert "100" in msg  # limit
            assert "110" in msg  # total (100 + 10)


class TestStepBudgetReset:
    """Step budget reset functionality."""

    def test_reset_creates_fresh_budget(self):
        """reset_step_budget() creates a fresh budget."""
        budget1 = get_step_budget()
        budget1.start()
        budget1.consume(50)

        reset_step_budget()

        budget2 = get_step_budget()
        assert budget2.get_total() == 0
        assert budget2.is_active() is False

    def test_reset_during_active_budget(self):
        """Reset works even with active budget."""
        budget = get_step_budget()
        budget.start(limit=100)
        budget.consume(50)

        reset_step_budget()

        # New budget is fresh
        budget2 = get_step_budget()
        budget2.start(limit=100)
        budget2.consume(100)  # Can consume full amount
        budget2.stop()


class TestStepBudgetThreadSafety:
    """Thread-local isolation of step budgets."""

    def test_budgets_isolated_per_thread(self):
        """Each thread gets its own budget."""
        results = {}
        errors = []

        def worker(thread_id, steps):
            try:
                reset_step_budget()
                budget = get_step_budget()
                budget.start(limit=steps * 2)

                for _ in range(steps):
                    budget.consume(1)

                results[thread_id] = budget.get_total()
                budget.stop()
            except Exception as e:
                errors.append((thread_id, e))

        # Run 5 threads with different step counts
        threads = [
            threading.Thread(target=worker, args=(i, (i + 1) * 10))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"

        # Each thread should have consumed its own allocation
        for i in range(5):
            expected = (i + 1) * 10
            assert results[i] == expected, f"Thread {i}: expected {expected}, got {results[i]}"

    def test_reset_in_one_thread_doesnt_affect_others(self):
        """Resetting in one thread doesn't affect others."""
        shared_state = {"thread1_consumed": 0, "thread2_consumed": 0}

        def thread1():
            budget = get_step_budget()
            budget.start(limit=100)
            budget.consume(50)
            shared_state["thread1_consumed"] = budget.get_total()
            budget.stop()

        def thread2():
            reset_step_budget()
            budget = get_step_budget()
            budget.start(limit=100)
            budget.consume(30)
            shared_state["thread2_consumed"] = budget.get_total()
            budget.stop()

        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should have its own count
        assert shared_state["thread1_consumed"] == 50
        assert shared_state["thread2_consumed"] == 30


class TestStepBudgetNoWarnings:
    """Verify step budget functions are NOT deprecated."""

    def test_get_step_budget_no_deprecation_warning(self):
        """get_step_budget() does NOT emit DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            budget = get_step_budget()

            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 0, (
                f"get_step_budget() should NOT emit DeprecationWarning, "
                f"got: {[str(dw.message) for dw in deprecation_warnings]}"
            )

    def test_reset_step_budget_no_deprecation_warning(self):
        """reset_step_budget() does NOT emit DeprecationWarning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            reset_step_budget()

            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 0

    def test_budget_operations_no_deprecation_warning(self):
        """Budget start/consume/stop do NOT emit warnings."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            budget = get_step_budget()
            budget.start()
            budget.consume(10)
            budget.get_remaining()
            budget.get_total()
            budget.stop()

            deprecation_warnings = [
                warning for warning in w
                if issubclass(warning.category, DeprecationWarning)
            ]
            assert len(deprecation_warnings) == 0
