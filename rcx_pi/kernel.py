"""
RCX Kernel v0 - Minimal Structural Runtime

The kernel provides exactly 4 primitives:
1. compute_identity(mu) - SHA-256 of canonical JSON
2. detect_stall(before, after) - Compare identity hashes
3. record_trace(entry) - Append to trace history
4. gate_dispatch(event, context) - Call seed-provided handler

The kernel is "dumb" - it doesn't know how to match patterns or apply
projections. Seeds define all semantics via handlers.

See docs/core/RCXKernel.v0.md for the full specification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from rcx_pi.mu_type import (
    Mu,
    assert_mu,
    assert_handler_pure,
    validate_kernel_boundary,
    mark_bootstrap,
)


# =============================================================================
# Kernel Primitives
# =============================================================================


def compute_identity(mu: Mu) -> str:
    """
    Compute deterministic identity hash (Ξ) of a Mu value.

    Uses SHA-256 of canonical JSON serialization.

    Args:
        mu: Any valid Mu value.

    Returns:
        Hex string of SHA-256 hash (64 characters).

    Raises:
        TypeError: If mu is not a valid Mu.
    """
    # Guardrail: validate input is Mu
    assert_mu(mu, "compute_identity input")  # guardrail

    # Canonical JSON: sorted keys, no extra whitespace, ASCII-safe
    canonical = json.dumps(mu, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
    hash_bytes = hashlib.sha256(canonical.encode('utf-8')).digest()
    return hash_bytes.hex()


def detect_stall(before_hash: str, after_hash: str) -> bool:
    """
    Detect if a stall occurred (identity unchanged).

    A stall means the value did not change after an attempted transformation.

    Args:
        before_hash: Identity hash before transformation.
        after_hash: Identity hash after transformation.

    Returns:
        True if hashes are equal (stall), False otherwise.
    """
    # Note: comparing strings with Python == is OK (not Mu comparison)
    return before_hash == after_hash


def record_trace(trace: list, entry: Mu) -> None:
    """
    Append an entry to the trace history.

    The trace is a list of Mu entries recording execution history.

    Args:
        trace: The trace list to append to.
        entry: A Mu value representing the trace entry.

    Raises:
        TypeError: If entry is not a valid Mu.
    """
    # Guardrail: validate entry is Mu
    assert_mu(entry, "record_trace entry")  # guardrail
    trace.append(entry)


def gate_dispatch(handlers: dict, event: str, context: Mu) -> Mu:
    """
    Dispatch an event to the appropriate seed handler.

    The kernel doesn't interpret events - it just routes them to handlers
    provided by seeds.

    Args:
        handlers: Dict mapping event names to handler functions.
        event: The event name (e.g., "step", "stall", "init").
        context: Mu value providing context to the handler.

    Returns:
        Mu value returned by the handler.

    Raises:
        TypeError: If context is not Mu or handler returns non-Mu.
        KeyError: If no handler registered for event.
    """
    # Guardrail: validate context is Mu
    assert_mu(context, f"gate_dispatch({event}) context")  # guardrail

    if event not in handlers:
        raise KeyError(f"No handler registered for event: {event}")

    handler = handlers[event]
    result = handler(context)

    # Guardrail: validate handler returned Mu
    assert_mu(result, f"gate_dispatch({event}) result")  # guardrail

    return result


# =============================================================================
# Kernel Class
# =============================================================================


class Kernel:
    """
    RCX Kernel - minimal structural runtime.

    The kernel maintains:
    - A trace (history of events)
    - A handler table (seed-provided event handlers)

    The kernel does NOT maintain:
    - Current value (that's the caller's responsibility)
    - Projections/rules (that's seed responsibility)
    """

    def __init__(self) -> None:
        """Initialize an empty kernel."""
        self._trace: list[Mu] = []
        self._handlers: dict[str, Callable[[Mu], Mu]] = {}
        self._step_counter: int = 0

    # -------------------------------------------------------------------------
    # Primitives (delegate to module functions)
    # -------------------------------------------------------------------------

    def compute_identity(self, mu: Mu) -> str:
        """Compute identity hash of a Mu value."""
        return compute_identity(mu)

    def detect_stall(self, before_hash: str, after_hash: str) -> bool:
        """Detect if a stall occurred."""
        return detect_stall(before_hash, after_hash)

    def record_trace(self, entry: Mu) -> None:
        """Record an entry to the trace."""
        record_trace(self._trace, entry)

    def gate_dispatch(self, event: str, context: Mu) -> Mu:
        """Dispatch an event to the registered handler."""
        return gate_dispatch(self._handlers, event, context)

    # -------------------------------------------------------------------------
    # Handler Registration
    # -------------------------------------------------------------------------

    def register_handler(self, event: str, handler: Callable[[Mu], Mu]) -> None:
        """
        Register a handler for an event.

        Handlers are wrapped with assert_handler_pure to ensure Mu in/out.

        Args:
            event: Event name (e.g., "step", "stall", "init").
            handler: Function that takes Mu context and returns Mu result.
        """
        # Wrap handler with purity guardrail (assert_handler_pure on prev line)
        wrapped = assert_handler_pure(handler, f"handler:{event}")
        self._handlers[event] = wrapped  # wrapped via assert_handler_pure above

    def has_handler(self, event: str) -> bool:
        """Check if a handler is registered for an event."""
        return event in self._handlers

    # -------------------------------------------------------------------------
    # Trace Access
    # -------------------------------------------------------------------------

    def get_trace(self) -> list[Mu]:
        """
        Return the current trace.

        Returns a copy to prevent external mutation.
        """
        return list(self._trace)

    def clear_trace(self) -> None:
        """Clear the trace history."""
        self._trace.clear()
        self._step_counter = 0

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------

    def step(self, mu: Mu) -> tuple[Mu, bool]:
        """
        Execute one step of the kernel loop.

        This is the core execution primitive:
        1. Compute identity hash of current value
        2. Dispatch "step" event to seed (seed transforms value)
        3. Compute identity hash of result
        4. Record trace entry
        5. Detect stall (hash unchanged)
        6. If stall, dispatch "stall" event

        Args:
            mu: Current Mu value.

        Returns:
            Tuple of (new_mu, is_stall).

        Raises:
            KeyError: If "step" handler not registered.
        """
        # Guardrail: validate input
        assert_mu(mu, "kernel.step input")  # guardrail

        # 1. Compute identity before
        before_hash = self.compute_identity(mu)

        # 2. Dispatch to seed's step handler
        # The seed does ALL the work: selects projection, applies it, returns result
        context = {"mu": mu, "hash": before_hash, "step": self._step_counter}
        result = self.gate_dispatch("step", context)

        # 3. Compute identity after
        after_hash = self.compute_identity(result)

        # 4. Record trace
        trace_entry = {
            "step": self._step_counter,
            "before_hash": before_hash,
            "after_hash": after_hash,
        }
        self.record_trace(trace_entry)
        self._step_counter += 1

        # 5. Detect stall
        is_stall = self.detect_stall(before_hash, after_hash)

        # 6. If stall, dispatch stall event
        if is_stall and self.has_handler("stall"):
            stall_context = {
                "mu": result,
                "hash": after_hash,
                "trace": self.get_trace(),
            }
            result = self.gate_dispatch("stall", stall_context)

        return result, is_stall

    def run(self, mu: Mu, max_steps: int = 1000) -> tuple[Mu, list[Mu], str]:
        """
        Run the kernel loop until stall or max_steps.

        Args:
            mu: Initial Mu value.
            max_steps: Maximum number of steps before forced stop.

        Returns:
            Tuple of (final_mu, trace, halt_reason).
            halt_reason is one of: "stall", "max_steps".
        """
        # Guardrail: validate input
        assert_mu(mu, "kernel.run input")  # guardrail

        # Dispatch init event if handler exists
        if self.has_handler("init"):
            init_context = {"mu": mu, "max_steps": max_steps}
            mu = self.gate_dispatch("init", init_context)

        current = mu
        for _ in range(max_steps):
            current, is_stall = self.step(current)
            if is_stall:
                return current, self.get_trace(), "stall"

        return current, self.get_trace(), "max_steps"


# =============================================================================
# Factory Function
# =============================================================================


def create_kernel() -> Kernel:
    """
    Create a new kernel instance.

    This is the recommended way to create a kernel.
    """
    return Kernel()
