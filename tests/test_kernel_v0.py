"""
Tests for RCX Kernel v0.

Tests the 4 kernel primitives and the main loop.
See docs/core/RCXKernel.v0.md for specification.
"""

import pytest

from rcx_pi.kernel import (
    compute_identity,
    detect_stall,
    record_trace,
    gate_dispatch,
    Kernel,
    create_kernel,
)
from rcx_pi.mu_type import is_mu


# =============================================================================
# Primitive Tests: compute_identity
# =============================================================================


class TestComputeIdentity:
    """Tests for compute_identity() primitive."""

    def test_returns_hex_string(self):
        """Identity hash is a 64-char hex string (SHA-256)."""
        h = compute_identity({"a": 1})
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        """Same value always produces same hash."""
        mu = {"x": [1, 2, {"y": 3}]}
        h1 = compute_identity(mu)
        h2 = compute_identity(mu)
        assert h1 == h2

    def test_different_values_different_hash(self):
        """Different values produce different hashes."""
        h1 = compute_identity({"a": 1})
        h2 = compute_identity({"a": 2})
        assert h1 != h2

    def test_dict_key_order_irrelevant(self):
        """Dict key order doesn't affect hash (canonical form)."""
        h1 = compute_identity({"z": 1, "a": 2})
        h2 = compute_identity({"a": 2, "z": 1})
        assert h1 == h2

    def test_true_and_one_different_hash(self):
        """True and 1 produce different hashes (not Python coercion)."""
        h1 = compute_identity(True)
        h2 = compute_identity(1)
        assert h1 != h2

    def test_false_and_zero_different_hash(self):
        """False and 0 produce different hashes."""
        h1 = compute_identity(False)
        h2 = compute_identity(0)
        assert h1 != h2

    def test_none_has_hash(self):
        """None (null) has a valid hash."""
        h = compute_identity(None)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_empty_structures_have_hash(self):
        """Empty dict and list have valid (different) hashes."""
        h_dict = compute_identity({})
        h_list = compute_identity([])
        assert len(h_dict) == 64
        assert len(h_list) == 64
        assert h_dict != h_list

    def test_non_mu_raises(self):
        """Non-Mu value raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            compute_identity(lambda x: x)
        assert "Mu" in str(exc_info.value)

    def test_nested_lambda_raises(self):
        """Lambda nested in structure raises TypeError."""
        with pytest.raises(TypeError):
            compute_identity({"fn": lambda x: x})


# =============================================================================
# Primitive Tests: detect_stall
# =============================================================================


class TestDetectStall:
    """Tests for detect_stall() primitive."""

    def test_same_hash_is_stall(self):
        """Same hash returns True (stall)."""
        h = "abc123"
        assert detect_stall(h, h) is True

    def test_different_hash_not_stall(self):
        """Different hashes return False (no stall)."""
        assert detect_stall("abc123", "def456") is False

    def test_empty_strings(self):
        """Empty strings are equal (stall)."""
        assert detect_stall("", "") is True

    def test_realistic_hashes(self):
        """Works with realistic SHA-256 hashes."""
        h1 = compute_identity({"a": 1})
        h2 = compute_identity({"a": 1})
        h3 = compute_identity({"a": 2})
        assert detect_stall(h1, h2) is True
        assert detect_stall(h1, h3) is False


# =============================================================================
# Primitive Tests: record_trace
# =============================================================================


class TestRecordTrace:
    """Tests for record_trace() primitive."""

    def test_appends_entry(self):
        """Entry is appended to trace."""
        trace = []
        record_trace(trace, {"step": 0})
        assert len(trace) == 1
        assert trace[0] == {"step": 0}

    def test_multiple_entries(self):
        """Multiple entries are appended in order."""
        trace = []
        record_trace(trace, {"step": 0})
        record_trace(trace, {"step": 1})
        record_trace(trace, {"step": 2})
        assert len(trace) == 3
        assert [e["step"] for e in trace] == [0, 1, 2]

    def test_non_mu_entry_raises(self):
        """Non-Mu entry raises TypeError."""
        trace = []
        with pytest.raises(TypeError) as exc_info:
            record_trace(trace, lambda x: x)
        assert "Mu" in str(exc_info.value)

    def test_complex_mu_entry(self):
        """Complex Mu structure can be recorded."""
        trace = []
        entry = {"step": 0, "data": {"nested": [1, 2, {"deep": True}]}}
        record_trace(trace, entry)
        assert trace[0] == entry


# =============================================================================
# Primitive Tests: gate_dispatch
# =============================================================================


class TestGateDispatch:
    """Tests for gate_dispatch() primitive."""

    def test_calls_handler(self):
        """Handler is called with context."""
        called_with = []

        def handler(ctx):
            called_with.append(ctx)
            return {"handled": True}

        handlers = {"test": handler}
        result = gate_dispatch(handlers, "test", {"input": 1})

        assert len(called_with) == 1
        assert called_with[0] == {"input": 1}
        assert result == {"handled": True}

    def test_returns_handler_result(self):
        """Returns what handler returns."""
        def handler(ctx):
            return {"value": ctx["x"] * 2}

        handlers = {"double": handler}
        result = gate_dispatch(handlers, "double", {"x": 21})
        assert result == {"value": 42}

    def test_missing_handler_raises(self):
        """KeyError raised if handler not registered."""
        handlers = {}
        with pytest.raises(KeyError) as exc_info:
            gate_dispatch(handlers, "missing", {})
        assert "missing" in str(exc_info.value)

    def test_non_mu_context_raises(self):
        """Non-Mu context raises TypeError."""
        def handler(ctx):
            return ctx

        handlers = {"test": handler}
        with pytest.raises(TypeError) as exc_info:
            gate_dispatch(handlers, "test", lambda x: x)
        assert "Mu" in str(exc_info.value)

    def test_handler_returning_non_mu_raises(self):
        """Handler returning non-Mu raises TypeError."""
        def bad_handler(ctx):
            return lambda x: x  # Not Mu!

        handlers = {"bad": bad_handler}
        with pytest.raises(TypeError) as exc_info:
            gate_dispatch(handlers, "bad", {"input": 1})
        assert "Mu" in str(exc_info.value)


# =============================================================================
# Kernel Class Tests
# =============================================================================


class TestKernelInit:
    """Tests for Kernel initialization."""

    def test_create_kernel(self):
        """create_kernel() returns a Kernel instance."""
        k = create_kernel()
        assert isinstance(k, Kernel)

    def test_empty_trace_on_init(self):
        """New kernel has empty trace."""
        k = create_kernel()
        assert k.get_trace() == []

    def test_no_handlers_on_init(self):
        """New kernel has no handlers."""
        k = create_kernel()
        assert k.has_handler("step") is False
        assert k.has_handler("stall") is False


class TestKernelHandlerRegistration:
    """Tests for handler registration."""

    def test_register_handler(self):
        """Handler can be registered."""
        k = create_kernel()

        def my_handler(ctx):
            return ctx

        k.register_handler("test", my_handler)
        assert k.has_handler("test") is True

    def test_handler_is_wrapped(self):
        """Registered handler is wrapped with purity guardrail."""
        k = create_kernel()

        def my_handler(ctx):
            return {"result": ctx["value"] + 1}

        k.register_handler("step", my_handler)

        # Handler should work with valid Mu
        result = k.gate_dispatch("step", {"value": 5})
        assert result == {"result": 6}

    def test_wrapped_handler_rejects_non_mu_input(self):
        """Wrapped handler rejects non-Mu input."""
        k = create_kernel()

        def my_handler(ctx):
            return ctx

        k.register_handler("test", my_handler)

        with pytest.raises(TypeError):
            k.gate_dispatch("test", lambda x: x)

    def test_wrapped_handler_rejects_non_mu_output(self):
        """Wrapped handler rejects non-Mu output."""
        k = create_kernel()

        def bad_handler(ctx):
            return lambda x: x  # Bad!

        k.register_handler("bad", bad_handler)

        with pytest.raises(TypeError):
            k.gate_dispatch("bad", {"input": 1})


class TestKernelTrace:
    """Tests for kernel trace management."""

    def test_get_trace_returns_copy(self):
        """get_trace() returns a copy, not the internal list."""
        k = create_kernel()
        k.record_trace({"step": 0})

        trace = k.get_trace()
        trace.append({"injected": True})  # Modify the copy

        assert len(k.get_trace()) == 1  # Original unchanged

    def test_clear_trace(self):
        """clear_trace() empties the trace."""
        k = create_kernel()
        k.record_trace({"step": 0})
        k.record_trace({"step": 1})
        assert len(k.get_trace()) == 2

        k.clear_trace()
        assert k.get_trace() == []


class TestKernelStep:
    """Tests for kernel.step() - single step execution."""

    def test_step_calls_handler(self):
        """step() calls the 'step' handler."""
        k = create_kernel()
        calls = []

        def step_handler(ctx):
            calls.append(ctx)
            return ctx["mu"]  # Identity - returns same value

        k.register_handler("step", step_handler)

        result, is_stall = k.step({"value": 1})

        assert len(calls) == 1
        assert calls[0]["mu"] == {"value": 1}

    def test_step_records_trace(self):
        """step() records a trace entry."""
        k = create_kernel()

        def identity_handler(ctx):
            return ctx["mu"]

        k.register_handler("step", identity_handler)

        k.step({"value": 1})

        trace = k.get_trace()
        assert len(trace) == 1
        assert "before_hash" in trace[0]
        assert "after_hash" in trace[0]
        assert "step" in trace[0]

    def test_step_detects_stall(self):
        """step() detects stall when value unchanged."""
        k = create_kernel()

        def identity_handler(ctx):
            return ctx["mu"]  # Same value = stall

        k.register_handler("step", identity_handler)

        _, is_stall = k.step({"value": 1})
        assert is_stall is True

    def test_step_detects_no_stall(self):
        """step() detects no stall when value changed."""
        k = create_kernel()

        def transform_handler(ctx):
            return {"value": ctx["mu"]["value"] + 1}  # Different value

        k.register_handler("step", transform_handler)

        _, is_stall = k.step({"value": 1})
        assert is_stall is False

    def test_step_calls_stall_handler(self):
        """step() calls 'stall' handler when stall detected."""
        k = create_kernel()
        stall_calls = []

        def identity_handler(ctx):
            return ctx["mu"]

        def stall_handler(ctx):
            stall_calls.append(ctx)
            return ctx["mu"]

        k.register_handler("step", identity_handler)
        k.register_handler("stall", stall_handler)

        k.step({"value": 1})

        assert len(stall_calls) == 1
        assert stall_calls[0]["mu"] == {"value": 1}
        assert "trace" in stall_calls[0]

    def test_step_without_step_handler_raises(self):
        """step() raises KeyError if no 'step' handler."""
        k = create_kernel()

        with pytest.raises(KeyError) as exc_info:
            k.step({"value": 1})
        assert "step" in str(exc_info.value)

    def test_step_non_mu_raises(self):
        """step() with non-Mu value raises TypeError."""
        k = create_kernel()

        def identity_handler(ctx):
            return ctx["mu"]

        k.register_handler("step", identity_handler)

        with pytest.raises(TypeError):
            k.step(lambda x: x)


class TestKernelRun:
    """Tests for kernel.run() - full execution loop."""

    def test_run_stops_on_stall(self):
        """run() stops when stall detected."""
        k = create_kernel()

        def identity_handler(ctx):
            return ctx["mu"]  # Always stall

        k.register_handler("step", identity_handler)

        final, trace, reason = k.run({"value": 1}, max_steps=100)

        assert reason == "stall"
        assert len(trace) == 1  # Stopped after first stall

    def test_run_stops_on_max_steps(self):
        """run() stops when max_steps reached."""
        k = create_kernel()
        counter = [0]

        def increment_handler(ctx):
            counter[0] += 1
            return {"value": counter[0]}  # Always different = no stall

        k.register_handler("step", increment_handler)

        final, trace, reason = k.run({"value": 0}, max_steps=10)

        assert reason == "max_steps"
        assert len(trace) == 10

    def test_run_returns_final_value(self):
        """run() returns the final Mu value."""
        k = create_kernel()

        # Transform 3 times then stall
        call_count = [0]

        def transform_handler(ctx):
            call_count[0] += 1
            if call_count[0] < 3:
                return {"value": ctx["mu"]["value"] + 1}
            return ctx["mu"]  # Stall on 3rd call

        k.register_handler("step", transform_handler)

        final, _, _ = k.run({"value": 0}, max_steps=100)

        assert final == {"value": 2}

    def test_run_calls_init_handler(self):
        """run() calls 'init' handler if registered."""
        k = create_kernel()
        init_calls = []

        def init_handler(ctx):
            init_calls.append(ctx)
            return ctx["mu"]

        def identity_handler(ctx):
            return ctx["mu"]

        k.register_handler("init", init_handler)
        k.register_handler("step", identity_handler)

        k.run({"value": 1}, max_steps=5)

        assert len(init_calls) == 1
        assert init_calls[0]["mu"] == {"value": 1}
        assert init_calls[0]["max_steps"] == 5

    def test_run_trace_is_valid_mu(self):
        """run() trace entries are all valid Mu."""
        k = create_kernel()

        def identity_handler(ctx):
            return ctx["mu"]

        k.register_handler("step", identity_handler)

        _, trace, _ = k.run({"value": 1})

        for entry in trace:
            assert is_mu(entry), f"Trace entry is not Mu: {entry}"


# =============================================================================
# Integration Tests
# =============================================================================


class TestKernelIntegration:
    """Integration tests for kernel behavior."""

    def test_countdown_to_zero(self):
        """Kernel can run a simple countdown program."""
        k = create_kernel()

        def countdown_handler(ctx):
            value = ctx["mu"]["n"]
            if value <= 0:
                return ctx["mu"]  # Stall at 0
            return {"n": value - 1}

        k.register_handler("step", countdown_handler)

        final, trace, reason = k.run({"n": 5}, max_steps=100)

        assert reason == "stall"
        assert final == {"n": 0}
        assert len(trace) == 6  # 5 decrements + 1 stall

    def test_accumulator(self):
        """Kernel can run an accumulator program."""
        k = create_kernel()

        def accumulate_handler(ctx):
            items = ctx["mu"]["items"]
            acc = ctx["mu"]["acc"]
            if not items:
                return ctx["mu"]  # Stall when done
            return {"items": items[1:], "acc": acc + items[0]}

        k.register_handler("step", accumulate_handler)

        final, trace, reason = k.run(
            {"items": [1, 2, 3, 4, 5], "acc": 0},
            max_steps=100
        )

        assert reason == "stall"
        assert final["acc"] == 15
        assert final["items"] == []

    def test_trace_hash_continuity(self):
        """Trace has continuous hash chain (after_hash[n] matches before_hash[n+1])."""
        k = create_kernel()
        counter = [0]

        def increment_handler(ctx):
            counter[0] += 1
            if counter[0] < 5:
                return {"value": counter[0]}
            return ctx["mu"]  # Stall

        k.register_handler("step", increment_handler)

        _, trace, _ = k.run({"value": 0}, max_steps=100)

        # Check hash continuity
        for i in range(len(trace) - 1):
            assert trace[i]["after_hash"] == trace[i + 1]["before_hash"], (
                f"Hash discontinuity at step {i}: "
                f"{trace[i]['after_hash']} != {trace[i + 1]['before_hash']}"
            )


# =============================================================================
# Kernel Boundary Tests (Grounding requirement)
# =============================================================================


class TestKernelBoundaries:
    """Tests for kernel boundary conditions.

    These tests verify behavior at the edges of valid input ranges,
    ensuring robust handling of edge cases.
    """

    def test_trace_limit_enforced(self):
        """MAX_TRACE_ENTRIES limit is enforced by record_trace."""
        from rcx_pi.kernel import MAX_TRACE_ENTRIES

        trace = []
        # Fill to limit
        for i in range(MAX_TRACE_ENTRIES):
            record_trace(trace, {"step": i})

        # One more should raise
        with pytest.raises(RuntimeError, match="Trace size limit exceeded"):
            record_trace(trace, {"step": "overflow"})

    def test_trace_at_limit_minus_one(self):
        """Trace at limit-1 can accept one more entry."""
        from rcx_pi.kernel import MAX_TRACE_ENTRIES

        trace = []
        for i in range(MAX_TRACE_ENTRIES - 1):
            record_trace(trace, {"step": i})

        # Should succeed (exactly at limit after this)
        record_trace(trace, {"step": "final"})
        assert len(trace) == MAX_TRACE_ENTRIES

    def test_compute_identity_empty_dict(self):
        """Empty dict has deterministic identity."""
        h1 = compute_identity({})
        h2 = compute_identity({})
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_identity_empty_list(self):
        """Empty list has deterministic identity."""
        h1 = compute_identity([])
        h2 = compute_identity([])
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_identity_deeply_nested(self):
        """Deeply nested structure has valid identity."""
        # Build 100-level deep structure
        value = "leaf"
        for _ in range(100):
            value = {"nested": value}

        h = compute_identity(value)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_detect_stall_hash_prefix_collision(self):
        """Different hashes with same prefix are not stalls."""
        # Two hashes that happen to share prefix
        h1 = "a" * 64
        h2 = "a" * 63 + "b"
        assert detect_stall(h1, h2) is False

    def test_gate_dispatch_empty_handler_name(self):
        """Empty string handler name is valid if registered."""
        def handler(ctx):
            return {"result": "ok"}

        handlers = {"": handler}
        result = gate_dispatch(handlers, "", {"input": 1})
        assert result == {"result": "ok"}

    def test_kernel_run_zero_max_steps(self):
        """run() with max_steps=0 returns immediately."""
        k = create_kernel()

        def identity(ctx):
            return ctx["mu"]

        k.register_handler("step", identity)

        # Note: max_steps=0 means no steps taken
        final, trace, reason = k.run({"value": 1}, max_steps=0)

        # Should return without taking any steps
        assert reason == "max_steps"
        assert len(trace) == 0
        assert final == {"value": 1}

    def test_kernel_run_max_steps_one(self):
        """run() with max_steps=1 takes exactly one step."""
        k = create_kernel()
        call_count = [0]

        def counting_handler(ctx):
            call_count[0] += 1
            return {"value": call_count[0]}

        k.register_handler("step", counting_handler)

        _, trace, reason = k.run({"value": 0}, max_steps=1)

        assert len(trace) == 1
        assert call_count[0] == 1
