"""
RCX Kernel - Step Budget Infrastructure

This file contains the global projection step budget for resource accounting.
The step budget prevents resource exhaustion from nested/cascading match_mu/subst_mu calls.

STRUCTURAL KERNEL:
  The structural kernel is in seeds/kernel.v1.json (7 Mu projections).
  It is executed by step_kernel_mu() in step_mu.py.
  See docs/core/MetaCircularKernel.v0.md for details.

DELETED (2026-01-29):
  The legacy Kernel class, create_kernel(), compute_identity(), detect_stall(),
  gate_dispatch(), and record_trace() were removed. They were deprecated scaffolding
  not used by the self-hosting path. See git history for reference if needed.
"""

from __future__ import annotations

import threading

# Maximum total projection steps across all match_mu/subst_mu calls
# Prevents resource exhaustion from nested/cascading calls
MAX_PROJECTION_STEPS = 50000


# =============================================================================
# Global Projection Step Budget (Cross-Call Resource Accounting)
# =============================================================================

class _ProjectionStepBudget:
    """
    Tracks cumulative projection steps across all match_mu/subst_mu calls.

    This prevents resource exhaustion from cascading calls where each individual
    call stays under its local limit but the total exceeds safe bounds.

    Usage:
        budget = get_step_budget()
        budget.start()  # Reset at start of kernel.run()
        try:
            budget.consume(steps)  # Called by match_mu/subst_mu
        finally:
            budget.stop()

    The budget is thread-local to support concurrent execution.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._total_steps: int = 0
        self._limit: int = MAX_PROJECTION_STEPS

    def start(self, limit: int | None = None) -> None:
        """Start tracking with optional custom limit."""
        self._active = True
        self._total_steps = 0
        self._limit = limit if limit is not None else MAX_PROJECTION_STEPS

    def stop(self) -> None:
        """Stop tracking."""
        self._active = False

    def is_active(self) -> bool:
        """Check if budget tracking is active."""
        return self._active

    def consume(self, steps: int) -> None:
        """
        Consume steps from the budget.

        Args:
            steps: Number of steps to consume.

        Raises:
            RuntimeError: If budget exceeded.
        """
        if not self._active:
            return  # No budget tracking active

        self._total_steps += steps
        if self._total_steps > self._limit:
            raise RuntimeError(
                f"Global projection step limit exceeded ({self._limit} steps). "
                f"Total steps: {self._total_steps}. "
                f"Possible resource exhaustion from nested match/subst calls."
            )

    def get_remaining(self) -> int:
        """Get remaining steps in budget."""
        if not self._active:
            return MAX_PROJECTION_STEPS
        return max(0, self._limit - self._total_steps)

    def get_total(self) -> int:
        """Get total steps consumed."""
        return self._total_steps


# Thread-local storage for step budget
# Each thread gets its own budget instance to support concurrent execution
_BUDGET_STORAGE = threading.local()


def get_step_budget() -> _ProjectionStepBudget:
    """Get the thread-local projection step budget."""
    if not hasattr(_BUDGET_STORAGE, 'budget'):
        _BUDGET_STORAGE.budget = _ProjectionStepBudget()
    return _BUDGET_STORAGE.budget


def reset_step_budget() -> None:
    """Reset the thread-local step budget (for testing)."""
    _BUDGET_STORAGE.budget = _ProjectionStepBudget()
