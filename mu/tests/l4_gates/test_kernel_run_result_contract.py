"""
KernelRunResult contract lock tests.

Verifies that step_kernel_mu (Python) and _stepKernelCore (JS) both produce
the canonical KernelRunResult shape with identical fields and semantics.

These tests lock the contract defined in the Canonical Machine Contract
design packet (v3, 2026-03-16).
"""

from __future__ import annotations

import ast
import json
import subprocess
from copy import deepcopy

import pytest

import rcx_pi.selfhost.step_mu as step_mu_mod
from rcx_pi.selfhost.step_mu import step_kernel_mu
from tests.repo_root import REPO_ROOT


# -- KernelRunResult shape contract --

REQUIRED_FIELDS = {"output", "stall", "termination_reason", "steps_used", "max_steps"}
VALID_TERM_REASONS = {
    "projection_applied",
    "kernel_stall",
    "hash_stall",
    "max_steps_exhausted",
    "fuel_exhausted",
}
FUEL_FIELDS = {"fuel_supplied", "fuel_remaining", "fuel_exhausted"}
PACKET_FIELDS = {"kind", "result", "continuation"}
CONTINUATION_FIELDS = {
    "tag",
    "version",
    "kernel_state",
    "domain_input",
    "projection_cursor",
    "remaining_fuel",
    "fuel_mode",
    "steps_used",
    "watchdog_cap",
    "terminal",
}
TERMINAL_METADATA_FIELDS = {"reached", "reason", "error"}
SHARED_RESULT_FIELDS = (
    "output",
    "stall",
    "termination_reason",
    "steps_used",
    "max_steps",
)
def _shared_kernel_result(meta: dict) -> dict:
    return {field: meta[field] for field in SHARED_RESULT_FIELDS}

def _make_kernel_fuel(count: int):
    fuel = None
    for _ in range(count):
        fuel = {"head": None, "tail": fuel}
    return fuel


def _fuel_remaining_count(fuel) -> int:
    count = 0
    cursor = fuel
    while cursor is not None:
        assert isinstance(cursor, dict), f"fuel cursor must be dict/null, got {type(cursor).__name__}"
        assert set(cursor) == {"head", "tail"}
        count += 1
        cursor = cursor["tail"]
    return count


class TestKernelRunResultPython:
    """Python step_kernel_mu(return_meta=True) must produce KernelRunResult."""

    def test_raw_step_kernel_returns_packet_shape(self):
        """Raw Python kernel-driver call returns terminal-or-continuation packet."""
        packet = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            max_steps=100,
            return_packet=True,
        )
        assert set(packet.keys()) == PACKET_FIELDS
        assert packet["kind"] in {"terminal", "continuation"}
        if packet["kind"] == "terminal":
            assert packet["continuation"] is None
            assert REQUIRED_FIELDS <= set(packet["result"].keys())
        else:
            assert packet["result"] is None
            continuation = packet["continuation"]
            assert set(continuation.keys()) == CONTINUATION_FIELDS
            assert continuation["tag"] == "kernel_driver_continuation_state"
            assert continuation["version"] == 1
            assert continuation["fuel_mode"] in {"explicit", "omitted_compatibility"}
            assert continuation["remaining_fuel"] is None
            assert set(continuation["terminal"].keys()) == TERMINAL_METADATA_FIELDS
            assert continuation["terminal"] == {"reached": False, "reason": None, "error": None}

    def test_raw_step_kernel_terminal_packet_carries_kernel_run_result(self):
        """Terminal packets carry the existing KernelRunResult unchanged."""
        packet = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            kernel_fuel=None,
            max_steps=100,
            return_packet=True,
        )
        assert packet["kind"] == "terminal"
        assert packet["continuation"] is None
        assert REQUIRED_FIELDS <= set(packet["result"].keys())
        assert packet["result"]["termination_reason"] == "fuel_exhausted"
        assert packet["result"]["fuel_supplied"] is True

    def test_continuation_resume_rejects_unsupplied_projection_state(self):
        """Continuation resume must not execute projections absent from the call."""
        forged_projection = {
            "pattern": step_mu_mod.normalize_for_match({"x": 1}),
            "body": step_mu_mod.normalize_for_match({"x": 2}),
        }
        state = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "_step": step_mu_mod.normalize_for_match({"ignored": True}),
                "_projs": step_mu_mod.list_to_linked([forged_projection]),
            },
            "domain_input": {"ignored": True},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 1,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                [],
                {"ignored": True},
                continuation_state=state,
                return_meta=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_broader_matching_prefix_projection(self):
        """Continuation resume must not skip an earlier matching caller projection."""
        first = {"pattern": {"x": 1}, "body": {"winner": "first"}}
        second = {"pattern": {"x": 1}, "body": {"winner": "second"}}
        packet = step_kernel_mu(
            [second],
            {"x": 1},
            return_packet=True,
            max_steps=100,
        )
        assert packet["kind"] == "continuation"

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                [first, second],
                {"x": 1},
                continuation_state=packet["continuation"],
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_forged_later_phase_projection_state(self):
        """Continuation resume must reject later states whose selected projection no longer matches."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        forged = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "_mode": "match_done",
                "_status": "success",
                "_bindings": None,
                "_match_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 0}),
                    "_body": step_mu_mod.normalize_for_match({"x": 2}),
                    "_remaining": None,
                },
            },
            "domain_input": {"x": 0},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 5,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                projs,
                {"x": 0},
                continuation_state=forged,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_forged_match_success_precursor(self):
        """Packet mode must not advance a forged match state into success."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        forged = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "mode": "match",
                "pattern_focus": None,
                "value_focus": None,
                "bindings": None,
                "stack": None,
                "_match_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 0}),
                    "_body": step_mu_mod.normalize_for_match({"x": 2}),
                    "_remaining": None,
                },
            },
            "domain_input": {"x": 0},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 4,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                projs,
                {"x": 0},
                continuation_state=forged,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_forged_subst_done_result(self):
        """Continuation resume must not trust a caller-supplied subst_done result."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        state = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "_mode": "subst_done",
                "_result": step_mu_mod.normalize_for_match({"x": 999}),
                "_subst_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 1}),
                    "_remaining": None,
                },
            },
            "domain_input": {"x": 1},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 21,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=state,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_forged_final_subst_result_focus(self):
        """Continuation resume must bind final subst result focus to the selected body."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        state = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "mode": "subst",
                "phase": "result",
                "focus": step_mu_mod.normalize_for_match({"x": 999}),
                "bindings": None,
                "context": None,
                "_subst_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 1}),
                    "_remaining": None,
                },
            },
            "domain_input": {"x": 1},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 7,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=state,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_watchdog_cap_tampering(self):
        """Continuation watchdog metadata must stay bound to the supplied watchdog."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=2, return_packet=True)
        assert packet["kind"] == "continuation"

        forged = deepcopy(packet["continuation"])
        forged["watchdog_cap"] = 100

        with pytest.raises(ValueError, match="watchdog_cap"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=forged,
                return_packet=True,
                max_steps=2,
            )

    def test_continuation_resume_rejects_boolean_versions(self):
        """Python continuation version fields must reject bools like JS strict equality."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=2, return_packet=True)
        assert packet["kind"] == "continuation"
        assert packet["continuation"]["projection_cursor"] is not None

        forged = deepcopy(packet["continuation"])
        forged["version"] = True
        with pytest.raises(ValueError, match="version mismatch"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=forged,
                return_packet=True,
                max_steps=2,
            )

        forged = deepcopy(packet["continuation"])
        forged["projection_cursor"]["version"] = True
        with pytest.raises(ValueError, match="version mismatch"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=forged,
                return_packet=True,
                max_steps=2,
            )

    def test_continuation_resume_rejects_primitive_kernel_state_with_projection_cursor(self):
        """Python continuation resume rejects scalar kernel_state values carrying cursor authority."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=100, return_packet=True)
        assert packet["kind"] == "continuation"

        forged = deepcopy(packet["continuation"])
        forged["kernel_state"] = "forged_non_state"

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=forged,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_allows_cursorless_primitive_hash_stall_state(self):
        """Python cursorless scalar continuation states preserve defensive hash_stall."""
        projs = [{"pattern": "a", "body": "b"}]
        sentinel = "hash_stall_sentinel"
        packet = step_kernel_mu(projs, "a", max_steps=100, return_packet=True)
        assert packet["kind"] == "continuation"
        continuation = deepcopy(packet["continuation"])
        continuation["kernel_state"] = sentinel
        continuation["projection_cursor"] = None

        terminal = step_kernel_mu(
            projs,
            "a",
            continuation_state=continuation,
            return_packet=True,
            max_steps=100,
        )

        assert terminal["kind"] == "terminal"
        assert terminal["result"]["termination_reason"] == "hash_stall"
        assert terminal["result"]["output"] == "a"
        assert terminal["result"]["steps_used"] == 2

    @pytest.mark.parametrize("kernel_state", [{"foo": "bar"}, {"_mode": "bogus"}])
    def test_continuation_resume_rejects_unknown_kernel_state_shape(self, kernel_state):
        """Python continuation resume rejects object states that are not emitted kernel shapes."""
        state = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": kernel_state,
            "domain_input": {"x": 1},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 2,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }

        with pytest.raises(ValueError, match="kernel_state"):
            step_kernel_mu(
                [{"pattern": {"x": 1}, "body": {"x": 2}}],
                {"x": 1},
                continuation_state=state,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_steps_used_cursor_tampering(self):
        """Python continuation resume rejects steps_used values not bound to the cursor."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=100, return_packet=True)
        assert packet["kind"] == "continuation"

        forged = deepcopy(packet["continuation"])
        forged["steps_used"] = 100

        with pytest.raises(ValueError, match="steps_used"):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=forged,
                return_packet=True,
                max_steps=100,
            )

    def test_continuation_resume_rejects_steps_used_null_cursor_tampering(self):
        """Python continuation resume rejects cursorless steps_used tampering."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=100, return_packet=True)
        assert packet["kind"] == "continuation"
        packet = step_kernel_mu(
            projs,
            {"x": 1},
            continuation_state=packet["continuation"],
            return_packet=True,
            max_steps=100,
        )
        assert packet["kind"] == "continuation"
        assert packet["continuation"]["projection_cursor"] is None
        assert packet["continuation"]["steps_used"] == 2

        for forged_steps_used in (0, 1, 100):
            forged = deepcopy(packet["continuation"])
            forged["steps_used"] = forged_steps_used
            with pytest.raises(ValueError, match="steps_used"):
                step_kernel_mu(
                    projs,
                    {"x": 1},
                    continuation_state=forged,
                    return_packet=True,
                    max_steps=100,
                )

    def test_continuation_resume_rejects_subst_null_bindings_when_required(self):
        """Python continuation resume rejects null subst bindings for a bound projection."""
        projs = [{"pattern": {"x": {"var": "v"}}, "body": {"y": {"var": "v"}}}]
        packet = step_kernel_mu(projs, {"x": 1}, max_steps=100, return_packet=True)
        for _ in range(40):
            assert packet["kind"] == "continuation"
            kernel_state = packet["continuation"]["kernel_state"]
            if isinstance(kernel_state, dict) and "subst" in kernel_state:
                forged = deepcopy(packet["continuation"])
                forged["kernel_state"]["subst"]["bindings"] = None
                with pytest.raises(ValueError, match="kernel_state"):
                    step_kernel_mu(
                        projs,
                        {"x": 1},
                        continuation_state=forged,
                        return_packet=True,
                        max_steps=100,
                    )
                break
            packet = step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=packet["continuation"],
                return_packet=True,
                max_steps=100,
            )
        else:
            raise AssertionError("expected subst continuation state")

    @pytest.mark.parametrize(
        ("case_name", "expected_error"),
        [
            ("null_match_ctx", "_match_ctx"),
            ("null_match_request", "match request"),
            ("null_subst_ctx", "_subst_ctx"),
            ("null_subst_request", "subst request"),
            ("missing_bindings", "binding cursor"),
        ],
    )
    def test_continuation_resume_rejects_malformed_phase_fields(self, case_name, expected_error):
        """Python continuation resume rejects supplied null/missing phase fields like JS."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        state = {
            "tag": "kernel_driver_continuation_state",
            "version": 1,
            "kernel_state": {
                "_mode": "match_done",
                "_status": "success",
                "_bindings": None,
                "_match_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 1}),
                    "_body": step_mu_mod.normalize_for_match({"x": 2}),
                    "_remaining": None,
                },
                "_subst_ctx": {
                    "_input": step_mu_mod.normalize_for_match({"x": 1}),
                    "_remaining": None,
                },
            },
            "domain_input": {"x": 1},
            "projection_cursor": None,
            "remaining_fuel": None,
            "fuel_mode": "omitted_compatibility",
            "steps_used": 5,
            "watchdog_cap": 100,
            "terminal": {"reached": False, "reason": None, "error": None},
        }
        kernel_state = state["kernel_state"]
        if case_name == "null_match_ctx":
            kernel_state["_match_ctx"] = None
        elif case_name == "null_match_request":
            kernel_state["match"] = None
        elif case_name == "null_subst_ctx":
            kernel_state["_subst_ctx"] = None
        elif case_name == "null_subst_request":
            kernel_state["subst"] = None
        elif case_name == "missing_bindings":
            del kernel_state["_bindings"]
        else:  # pragma: no cover - parametrization guard
            raise AssertionError(case_name)

        with pytest.raises((TypeError, ValueError), match=expected_error):
            step_kernel_mu(
                projs,
                {"x": 1},
                continuation_state=state,
                return_packet=True,
                max_steps=100,
            )

    def test_projection_applied_shape(self):
        """Successful projection produces all required fields."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        meta = step_kernel_mu(projs, {"x": 1}, return_meta=True)
        assert isinstance(meta, dict)
        assert REQUIRED_FIELDS <= set(meta.keys()), f"Missing fields: {REQUIRED_FIELDS - set(meta.keys())}"
        assert meta["termination_reason"] in VALID_TERM_REASONS
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}

    def test_kernel_stall_shape(self):
        """No matching projection produces kernel_stall with undefined_motif."""
        meta = step_kernel_mu([], {"x": 1}, return_meta=True)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "kernel_stall"
        assert meta["stall"] is True
        assert "undefined_motif" in meta, "kernel_stall must include undefined_motif"
        assert meta["undefined_motif"]["_undefined"] is True

    def test_stall_shape(self):
        """Stall (kernel_stall or hash_stall) produces stall=True with required fields."""
        # No projections -> kernel_stall (no projection matches)
        meta = step_kernel_mu([], {"x": 1}, return_meta=True)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] in ("hash_stall", "kernel_stall")
        assert meta["stall"] is True

    def test_max_steps_exhausted_shape(self):
        """Oscillating projection with low max_steps produces max_steps_exhausted."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        meta = step_kernel_mu(projs, {"s": "a"}, return_meta=True, max_steps=4)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True, "NB4 fix: max_steps must have stall=True"
        assert meta["steps_used"] == 4
        assert FUEL_FIELDS.isdisjoint(meta), (
            "omitted kernel_fuel compatibility must not expose internal fuel metadata"
        )

    def test_no_fuel_compatibility_does_not_build_max_steps_fuel(self, monkeypatch):
        """Omitted kernel_fuel must not turn max_steps into a host-sized fuel list."""
        lengths = []
        original = step_mu_mod.list_to_linked

        def spy_list_to_linked(items):
            lengths.append(len(items))
            return original(items)

        monkeypatch.setattr(step_mu_mod, "list_to_linked", spy_list_to_linked)
        max_steps = 4
        meta = step_kernel_mu(
            [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            {"s": "a"},
            return_meta=True,
            max_steps=max_steps,
        )

        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["steps_used"] == max_steps
        assert max_steps + 1 not in lengths, lengths

    def test_kernel_fuel_zero_exhausts_before_attempting_step(self):
        """Python kernel fuel uses explicit empty Mu fuel as execution authority."""
        meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            return_meta=True,
            max_steps=100,
            kernel_fuel=None,
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["output"] == {"x": 1}
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_exhaustion_is_authority_not_max_steps(self):
        """Python Mu fuel exhaustion terminates before the numeric watchdog cap."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        fuel_count = 4
        meta = step_kernel_mu(
            projs,
            {"s": "a"},
            return_meta=True,
            max_steps=100,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == fuel_count
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_numeric_watchdog_reports_remaining_fuel(self):
        """Python numeric cap is a watchdog when Mu fuel still remains."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        max_steps = 3
        fuel_count = 5
        meta = step_kernel_mu(
            projs,
            {"s": "a"},
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == max_steps
        assert meta["max_steps"] == max_steps
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - max_steps

    @pytest.mark.parametrize(
        "bad_max_steps",
        [
            pytest.param(float("nan"), id="nan"),
            pytest.param(float("inf"), id="positive-infinity"),
            pytest.param(float("-inf"), id="negative-infinity"),
        ],
    )
    def test_kernel_watchdog_rejects_non_finite_max_steps(self, bad_max_steps):
        """Python rejects non-finite watchdog values before the fuel driver can run."""
        with pytest.raises(ValueError, match="max_steps"):
            step_kernel_mu(
                [{"pattern": {"x": 1}, "body": {"x": 2}}],
                {"x": 1},
                return_meta=True,
                max_steps=bad_max_steps,
                kernel_fuel=_make_kernel_fuel(2),
            )

    def test_python_watchdog_guard_does_not_add_math_host_capability(self):
        """The watchdog guard must not import math into the runtime kernel."""
        step_mu_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        tree = ast.parse(step_mu_path.read_text(), filename=str(step_mu_path))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".", 1)[0])
        assert "math" not in imported_modules

    def test_kernel_fuel_success_reports_remaining_mu_fuel(self):
        """Python successful projection returns remaining Mu fuel."""
        fuel_count = 80
        meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            return_meta=True,
            max_steps=100,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert 0 < meta["steps_used"] < fuel_count
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - meta["steps_used"]

    @pytest.mark.parametrize(
        "kernel_fuel",
        [
            [],
            {"head": None, "tail": 0},
            {"head": None, "tail": None, "extra": None},
        ],
    )
    def test_kernel_fuel_rejects_non_linked_mu_data(self, kernel_fuel):
        """Python kernel fuel fails closed when consumed fuel is not head/tail linked-list data."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        with pytest.raises(TypeError, match="kernel_fuel"):
            step_kernel_mu(
                projs,
                {"s": "a"},
                return_meta=True,
                max_steps=4,
                kernel_fuel=kernel_fuel,
            )

    def test_kernel_fuel_rejects_malformed_tail_before_returning_remaining(self):
        """Python validates the full fuel list before returning remaining fuel."""
        with pytest.raises(TypeError, match="kernel_fuel"):
            step_kernel_mu(
                [{"pattern": {"x": 1}, "body": {"x": 2}}],
                {"x": 1},
                return_meta=True,
                max_steps=100,
                kernel_fuel={"head": None, "tail": 0},
            )

    def test_undefined_motif_only_on_kernel_stall(self):
        """undefined_motif must NOT be present on non-kernel_stall results."""
        # projection_applied
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        meta = step_kernel_mu(projs, {"x": 1}, return_meta=True)
        assert "undefined_motif" not in meta, "undefined_motif must not appear on projection_applied"

        # max_steps_exhausted
        projs2 = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        meta2 = step_kernel_mu(projs2, {"s": "a"}, return_meta=True, max_steps=4)
        assert "undefined_motif" not in meta2, "undefined_motif must not appear on max_steps_exhausted"

    def test_return_meta_false_returns_bare_output(self):
        """return_meta=False returns bare Mu value, not KernelRunResult dict."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        result = step_kernel_mu(projs, {"x": 1}, return_meta=False)
        assert result == {"x": 2}
        assert not isinstance(result, dict) or "termination_reason" not in result


class TestKernelRunResultJS:
    """JS stepKernel via --json-api (live seeded kernel) must produce KernelRunResult."""

    def _run_json_api_response(self, payload: dict) -> dict:
        """Run JS via eval_step.js --json-api with real seed loading."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(payload)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        # Extract JSON_API_RESPONSE from stdout (self-tests print first)
        stdout = result.stdout
        marker = "JSON_API_RESPONSE:"
        idx = stdout.find(marker)
        assert idx >= 0, f"No JSON_API_RESPONSE in output: {stdout[-200:]}"
        json_str = stdout[idx + len(marker):]
        return json.loads(json_str.strip())

    def _run_json_api(self, payload: dict) -> dict:
        resp = self._run_json_api_response(payload)
        assert resp.get("success"), f"JS API error: {resp.get('error', 'unknown')}"
        return resp["result"]

    def _run_direct_step_kernel_with_max_steps(self, max_steps_expr: str) -> dict:
        script = f"""
const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
try {{
  stepKernel(
    [],
    {{ x: 1 }},
    [{{ pattern: {{ x: 1 }}, body: {{ x: 2 }} }}],
    {{
      returnMeta: true,
      maxSteps: {max_steps_expr},
      kernelFuel: {{ head: null, tail: {{ head: null, tail: null }} }},
    }}
  );
  console.log(JSON.stringify({{ success: true }}));
}} catch (e) {{
  console.log(JSON.stringify({{
    success: false,
    error_code: e.error_code || null,
    error: e.message,
  }}));
}}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_direct_step_kernel_rejects_unsupplied_projection_continuation(self):
        """JS continuation resume rejects embedded projections absent from the call."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const { normalize, listToLinked } = require('./mu/host/js/core/normalize');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const forgedProjection = muContainers.record([
  ['pattern', normalize(trust({ x: 1 }))],
  ['body', normalize(trust({ x: 2 }))],
]);
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['_step', normalize(trust({ ignored: true }))],
    ['_projs', listToLinked([forgedProjection])],
  ])],
  ['domain_input', trust({ ignored: true })],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 1],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    [],
    trust({ ignored: true }),
    [],
    { continuationState: state, returnMeta: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_broader_matching_prefix_projection(self):
        """JS continuation resume must not skip an earlier matching caller projection."""
        script = """
const fs = require('fs');
const path = require('path');
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const stage0Vm = require('./mu/host/js/core/stage0_vm');
const {
  getSeedSubdir,
  loadVerifiedSeedImage,
  SEED_IMAGE_VERIFICATION_MODES,
} = require('./mu/host/js/core/seed_loader');
const muRoot = path.join(process.cwd(), 'mu');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const kernel = loadVerifiedSeedImage(
  'kernel.v1.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('kernel.v1.json'), 'kernel.v1.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const matchSeed = loadVerifiedSeedImage(
  'match.v2.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('match.v2.json'), 'match.v2.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const substSeed = loadVerifiedSeedImage(
  'subst.v2.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('subst.v2.json'), 'subst.v2.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const compiledDir = path.join(muRoot, 'stage0', 'compiled');
const kernelBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'kernel_v1.compiled.v1.json'), 'utf8'));
const matchBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'match_v2.compiled.v1.json'), 'utf8'));
const substBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'subst_v2.compiled.v1.json'), 'utf8'));
stage0Vm.validateBundle(kernelBundle);
stage0Vm.validateBundle(matchBundle);
stage0Vm.validateBundle(substBundle);
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const vmConfig = { kernelBundle, bridgeBundle: null, matchBundle, substBundle };
const first = trust({ pattern: { x: 1 }, body: { winner: 'first' } });
const second = trust({ pattern: { x: 1 }, body: { winner: 'second' } });
const input = trust({ x: 1 });
let packet = stepKernel(
  allProjections,
  input,
  [second],
  { returnPacket: true, maxSteps: 100, vmConfig }
);
try {
  stepKernel(
    allProjections,
    input,
    [first, second],
    { continuationState: packet.continuation, returnPacket: true, maxSteps: 100, vmConfig }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_forged_later_phase_projection_state(self):
        """JS continuation resume rejects later states whose selected projection no longer matches."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const { normalize } = require('./mu/host/js/core/normalize');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['_mode', 'subst_done'],
    ['_result', normalize(trust({ x: 2 }))],
    ['_subst_ctx', muContainers.record([
      ['_input', normalize(trust({ x: 0 }))],
      ['_remaining', null],
    ])],
  ])],
  ['domain_input', trust({ x: 0 })],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 21],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    [],
    trust({ x: 0 }),
    [trust({ pattern: { x: 1 }, body: { x: 2 } })],
    { continuationState: state, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_forged_match_success_precursor(self):
        """JS packet mode must not advance a forged match state into success."""
        script = """
const fs = require('fs');
const path = require('path');
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const stage0Vm = require('./mu/host/js/core/stage0_vm');
const { normalize } = require('./mu/host/js/core/normalize');
const {
  getSeedSubdir,
  loadVerifiedSeedImage,
  SEED_IMAGE_VERIFICATION_MODES,
} = require('./mu/host/js/core/seed_loader');
const muRoot = path.join(process.cwd(), 'mu');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const kernel = loadVerifiedSeedImage(
  'kernel.v1.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('kernel.v1.json'), 'kernel.v1.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const matchSeed = loadVerifiedSeedImage(
  'match.v2.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('match.v2.json'), 'match.v2.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const substSeed = loadVerifiedSeedImage(
  'subst.v2.json',
  fs.readFileSync(path.join(muRoot, getSeedSubdir('subst.v2.json'), 'subst.v2.json')),
  SEED_IMAGE_VERIFICATION_MODES.CLI
);
const compiledDir = path.join(muRoot, 'stage0', 'compiled');
const kernelBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'kernel_v1.compiled.v1.json'), 'utf8'));
const matchBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'match_v2.compiled.v1.json'), 'utf8'));
const substBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'subst_v2.compiled.v1.json'), 'utf8'));
stage0Vm.validateBundle(kernelBundle);
stage0Vm.validateBundle(matchBundle);
stage0Vm.validateBundle(substBundle);
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const vmConfig = { kernelBundle, bridgeBundle: null, matchBundle, substBundle };
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['mode', 'match'],
    ['pattern_focus', null],
    ['value_focus', null],
    ['bindings', null],
    ['stack', null],
    ['_match_ctx', muContainers.record([
      ['_input', normalize(trust({ x: 0 }))],
      ['_body', normalize(trust({ x: 2 }))],
      ['_remaining', null],
    ])],
  ])],
  ['domain_input', trust({ x: 0 })],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 4],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    allProjections,
    trust({ x: 0 }),
    [domainProjection],
    { continuationState: state, returnPacket: true, maxSteps: 100, vmConfig }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_forged_subst_done_result(self):
        """JS continuation resume must not trust a caller-supplied subst_done result."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const { normalize } = require('./mu/host/js/core/normalize');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['_mode', 'subst_done'],
    ['_result', normalize(trust({ x: 999 }))],
    ['_subst_ctx', muContainers.record([
      ['_input', normalize(trust({ x: 1 }))],
      ['_remaining', null],
    ])],
  ])],
  ['domain_input', trust({ x: 1 })],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 21],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    [],
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: state, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_forged_final_subst_result_focus(self):
        """JS continuation resume must bind final subst result focus to the selected body."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const { normalize } = require('./mu/host/js/core/normalize');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['mode', 'subst'],
    ['phase', 'result'],
    ['focus', normalize(trust({ x: 999 }))],
    ['bindings', null],
    ['context', null],
    ['_subst_ctx', muContainers.record([
      ['_input', normalize(trust({ x: 1 }))],
      ['_remaining', null],
    ])],
  ])],
  ['domain_input', trust({ x: 1 })],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 7],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    [],
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: state, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_rejects_watchdog_cap_tampering(self):
        """JS continuation watchdog metadata must stay bound to the supplied watchdog."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const { normalize, normalizeProjection, listToLinked } = require('./mu/host/js/core/normalize');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const kernelProjection = normalizeProjection(domainProjection);
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', muContainers.record([
    ['_mode', 'kernel'],
    ['_phase', 'try'],
    ['_input', normalize(trust({ x: 1 }))],
    ['_remaining', listToLinked([kernelProjection])],
  ])],
  ['domain_input', trust({ x: 1 })],
  ['projection_cursor', muContainers.record([
    ['tag', 'kernel_projection_cursor'],
    ['version', 1],
    ['position', 1],
    ['exhausted', false],
  ])],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 1],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  stepKernel(
    [],
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: state, returnPacket: true, maxSteps: 1 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "watchdog_cap" in payload["error"]

    def test_direct_step_kernel_rejects_primitive_kernel_state(self):
        """JS continuation resume rejects scalar kernel_state values carrying cursor authority."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const fs = require('fs');
const path = require('path');
const { loadVerifiedSeedImage, getSeedSubdir, SEED_IMAGE_VERIFICATION_MODES } = require('./mu/host/js/core/seed_loader');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
function seed(name) {
  const raw = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}
const kernel = seed('kernel.v1.json');
const matchSeed = seed('match.v2.json');
const substSeed = seed('subst.v2.json');
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const packet = stepKernel(
  allProjections,
  trust({ x: 1 }),
  [domainProjection],
  { returnPacket: true, maxSteps: 100 }
);
packet.continuation.kernel_state = 'forged_non_state';
try {
  stepKernel(
    allProjections,
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: packet.continuation, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "kernel_state" in payload["error"]

    def test_direct_step_kernel_allows_cursorless_primitive_hash_stall_state(self):
        """JS cursorless scalar continuation states preserve defensive hash_stall."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const fs = require('fs');
const path = require('path');
const { loadVerifiedSeedImage, getSeedSubdir, SEED_IMAGE_VERIFICATION_MODES } = require('./mu/host/js/core/seed_loader');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
function seed(name) {
  const raw = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}
const kernel = seed('kernel.v1.json');
const matchSeed = seed('match.v2.json');
const substSeed = seed('subst.v2.json');
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const domainProjection = trust({ pattern: 'a', body: 'b' });
const state = muContainers.record([
  ['tag', 'kernel_driver_continuation_state'],
  ['version', 1],
  ['kernel_state', 'hash_stall_sentinel'],
  ['domain_input', 'a'],
  ['projection_cursor', null],
  ['remaining_fuel', null],
  ['fuel_mode', 'omitted_compatibility'],
  ['steps_used', 1],
  ['watchdog_cap', 100],
  ['terminal', muContainers.record([
    ['reached', false],
    ['reason', null],
    ['error', null],
  ])],
]);
try {
  const packet = stepKernel(
    allProjections,
    'a',
    [domainProjection],
    { continuationState: state, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({
    success: true,
    kind: packet.kind,
    reason: packet.result && packet.result.termination_reason,
    output: packet.result && packet.result.output,
    steps: packet.result && packet.result.steps_used,
  }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload == {
            "success": True,
            "kind": "terminal",
            "reason": "hash_stall",
            "output": "a",
            "steps": 2,
        }

    def test_direct_step_kernel_rejects_unknown_kernel_state_shape(self):
        """JS continuation resume rejects object states that are not emitted kernel shapes."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const malformedKernelStates = [
  muContainers.record([['foo', 'bar']]),
  muContainers.record([['_mode', 'bogus']]),
];
const errors = [];
for (const kernelState of malformedKernelStates) {
  const state = muContainers.record([
    ['tag', 'kernel_driver_continuation_state'],
    ['version', 1],
    ['kernel_state', kernelState],
    ['domain_input', trust({ x: 1 })],
    ['projection_cursor', null],
    ['remaining_fuel', null],
    ['fuel_mode', 'omitted_compatibility'],
    ['steps_used', 2],
    ['watchdog_cap', 100],
    ['terminal', muContainers.record([
      ['reached', false],
      ['reason', null],
      ['error', null],
    ])],
  ]);
  try {
    stepKernel(
      [],
      trust({ x: 1 }),
      [domainProjection],
      { continuationState: state, returnPacket: true, maxSteps: 100 }
    );
    errors.push(null);
  } catch (e) {
    errors.push(e.message);
  }
}
console.log(JSON.stringify({ errors }));
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert len(payload["errors"]) == 2
        assert all(error and "kernel_state" in error for error in payload["errors"])

    def test_direct_step_kernel_rejects_steps_used_cursor_tampering(self):
        """JS continuation resume rejects steps_used values not bound to the cursor."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const fs = require('fs');
const path = require('path');
const { loadVerifiedSeedImage, getSeedSubdir, SEED_IMAGE_VERIFICATION_MODES } = require('./mu/host/js/core/seed_loader');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
function seed(name) {
  const raw = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}
const kernel = seed('kernel.v1.json');
const matchSeed = seed('match.v2.json');
const substSeed = seed('subst.v2.json');
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const packet = stepKernel(
  allProjections,
  trust({ x: 1 }),
  [domainProjection],
  { returnPacket: true, maxSteps: 100 }
);
packet.continuation.steps_used = 100;
try {
  stepKernel(
    allProjections,
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: packet.continuation, returnPacket: true, maxSteps: 100 }
  );
  console.log(JSON.stringify({ success: true }));
} catch (e) {
  console.log(JSON.stringify({ success: false, error: e.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["success"] is False
        assert "steps_used" in payload["error"]

    def test_direct_step_kernel_rejects_steps_used_null_cursor_tampering(self):
        """JS continuation resume rejects cursorless steps_used tampering."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const fs = require('fs');
const path = require('path');
const { loadVerifiedSeedImage, getSeedSubdir, SEED_IMAGE_VERIFICATION_MODES } = require('./mu/host/js/core/seed_loader');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
function seed(name) {
  const raw = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}
const kernel = seed('kernel.v1.json');
const matchSeed = seed('match.v2.json');
const substSeed = seed('subst.v2.json');
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const domainProjection = trust({ pattern: { x: 1 }, body: { x: 2 } });
const first = stepKernel(
  allProjections,
  trust({ x: 1 }),
  [domainProjection],
  { returnPacket: true, maxSteps: 100 }
);
const second = stepKernel(
  allProjections,
  trust({ x: 1 }),
  [domainProjection],
  { continuationState: first.continuation, returnPacket: true, maxSteps: 100 }
);
const errors = [];
const originalStepsUsed = second.continuation.steps_used;
for (const forgedStepsUsed of [0, 1, 100]) {
  second.continuation.steps_used = forgedStepsUsed;
  try {
    stepKernel(
      allProjections,
      trust({ x: 1 }),
      [domainProjection],
      { continuationState: second.continuation, returnPacket: true, maxSteps: 100 }
    );
    errors.push(null);
  } catch (e) {
    errors.push(e.message);
  } finally {
    second.continuation.steps_used = originalStepsUsed;
  }
}
console.log(JSON.stringify({
  secondKind: second.kind,
  projectionCursor: second.continuation.projection_cursor,
  stepsUsed: second.continuation.steps_used,
  errors,
}));
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["secondKind"] == "continuation"
        assert payload["projectionCursor"] is None
        assert payload["stepsUsed"] == 2
        assert len(payload["errors"]) == 3
        assert all(error and "steps_used" in error for error in payload["errors"])

    def test_direct_step_kernel_rejects_subst_null_bindings_when_required(self):
        """JS continuation resume rejects null subst bindings for a bound projection."""
        script = """
const { stepKernel } = require('./mu/host/js/engine/kernel');
const muContainers = require('./mu/host/js/core/container_factory');
const fs = require('fs');
const path = require('path');
const { loadVerifiedSeedImage, getSeedSubdir, SEED_IMAGE_VERIFICATION_MODES } = require('./mu/host/js/core/seed_loader');
function trust(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(item => trust(item)));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trust(value[key])]));
  }
  return value;
}
function seed(name) {
  const raw = fs.readFileSync(path.join('mu', getSeedSubdir(name), name));
  return loadVerifiedSeedImage(name, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}
const kernel = seed('kernel.v1.json');
const matchSeed = seed('match.v2.json');
const substSeed = seed('subst.v2.json');
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const domainProjection = trust({ pattern: { x: { var: 'v' } }, body: { y: { var: 'v' } } });
let packet = stepKernel(
  allProjections,
  trust({ x: 1 }),
  [domainProjection],
  { returnPacket: true, maxSteps: 100 }
);
let error = null;
let found = false;
for (let i = 0; i < 40; i++) {
  if (packet.kind !== 'continuation') break;
  if (Object.hasOwn(packet.continuation.kernel_state, 'subst')) {
    found = true;
    packet.continuation.kernel_state.subst.bindings = null;
    try {
      stepKernel(
        allProjections,
        trust({ x: 1 }),
        [domainProjection],
        { continuationState: packet.continuation, returnPacket: true, maxSteps: 100 }
      );
    } catch (e) {
      error = e.message;
    }
    break;
  }
  packet = stepKernel(
    allProjections,
    trust({ x: 1 }),
    [domainProjection],
    { continuationState: packet.continuation, returnPacket: true, maxSteps: 100 }
  );
}
console.log(JSON.stringify({ found, error }));
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        payload = json.loads(result.stdout.strip())
        assert payload["found"] is True
        assert payload["error"] and "kernel_state" in payload["error"]

    def test_projection_applied_has_required_fields(self):
        """JS live kernel produces KernelRunResult on successful projection."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
        })
        assert REQUIRED_FIELDS <= set(meta.keys()), f"JS missing: {REQUIRED_FIELDS - set(meta.keys())}"
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert isinstance(meta["steps_used"], int)
        assert isinstance(meta["max_steps"], int)
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_kernel_stall_has_required_fields(self):
        """JS live kernel produces KernelRunResult on stall."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [],
            "input": {"x": 1},
            "maxSteps": 100,
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "kernel_stall"
        assert meta["stall"] is True
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_max_steps_stall_true(self):
        """JS live kernel: max_steps must have stall=true (NB4 parity)."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": 4,
        })
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True, "JS NB4: max_steps must have stall=true"
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_kernel_fuel_zero_exhausts_before_attempting_step(self):
        """JS live kernel consumes no step when caller supplies empty Mu fuel."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": None,
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["output"] == {"x": 1}
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_exhaustion_consumes_one_node_per_kernel_step(self):
        """JS live kernel classifies exact structural-fuel exhaustion at maxSteps."""
        fuel_count = 3
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": fuel_count,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == fuel_count
        assert meta["max_steps"] == fuel_count
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_numeric_watchdog_reports_remaining_fuel(self):
        """JS live kernel reports watchdog exhaustion while Mu fuel remains."""
        max_steps = 3
        fuel_count = 5
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == max_steps
        assert meta["max_steps"] == max_steps
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - max_steps

    @pytest.mark.parametrize(
        "max_steps_expr",
        [
            pytest.param("NaN", id="nan"),
            pytest.param("Infinity", id="positive-infinity"),
            pytest.param("-Infinity", id="negative-infinity"),
        ],
    )
    def test_direct_step_kernel_watchdog_rejects_non_finite_max_steps(self, max_steps_expr):
        """JS direct stepKernel rejects non-finite watchdog values before the fuel driver can run."""
        resp = self._run_direct_step_kernel_with_max_steps(max_steps_expr)
        assert resp["success"] is False
        assert resp.get("error_code") == "api.bad_request"
        assert "maxSteps" in resp.get("error", "")

    def test_kernel_fuel_success_reports_remaining_mu_fuel(self):
        """JS live kernel returns unconsumed Mu fuel when fuel exceeds required steps."""
        fuel_count = 80
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert 0 < meta["steps_used"] < fuel_count
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - meta["steps_used"]

    def test_kernel_fuel_success_shared_result_matches_python(self):
        """Fuel-backed JS success preserves the Python/JS KernelRunResult contract."""
        projections = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        input_value = {"x": 1}
        max_steps = 100
        fuel_count = 80

        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": projections,
            "input": input_value,
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        py_meta = step_kernel_mu(
            projections,
            input_value,
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )

        assert _shared_kernel_result(js_meta) == _shared_kernel_result(py_meta)
        assert js_meta["fuel_supplied"] is True
        assert js_meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(js_meta["fuel_remaining"]) == (
            fuel_count - py_meta["steps_used"]
        )

    def test_kernel_fuel_exhaustion_shared_result_matches_python_budget(self):
        """JS fuel exhaustion matches Python's shared fields for the same step budget."""
        projections = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        input_value = {"s": "a"}
        fuel_count = 4
        max_steps = 100

        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": projections,
            "input": input_value,
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        py_meta = step_kernel_mu(
            projections,
            input_value,
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )

        assert js_meta["output"] == py_meta["output"]
        assert js_meta["stall"] == py_meta["stall"] is True
        assert js_meta["steps_used"] == py_meta["steps_used"] == fuel_count
        assert js_meta["termination_reason"] == "fuel_exhausted"
        assert py_meta["termination_reason"] == "fuel_exhausted"
        assert js_meta["max_steps"] == py_meta["max_steps"] == max_steps
        assert js_meta["fuel_supplied"] is True
        assert py_meta["fuel_supplied"] is True
        assert js_meta["fuel_remaining"] is None
        assert py_meta["fuel_remaining"] is None
        assert js_meta["fuel_exhausted"] is True
        assert py_meta["fuel_exhausted"] is True

    @pytest.mark.parametrize(
        "kernel_fuel",
        [
            {"head": None, "tail": 0},
            {"head": None, "tail": None, "extra": None},
            [],
        ],
    )
    def test_kernel_fuel_rejects_non_linked_mu_data(self, kernel_fuel):
        """JSON API fuel is fail-closed as Mu head/tail linked-list data."""
        resp = self._run_json_api_response({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": kernel_fuel,
        })
        assert not resp.get("success")
        assert resp.get("error_code") == "api.bad_request"
        assert "kernelFuel" in resp.get("error", "")

    def test_field_set_parity_with_python(self):
        """JS and Python KernelRunResult must have identical required field sets."""
        # JS projection_applied via live seeded kernel
        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
        })
        js_fields = set(js_meta.keys())

        # Python projection_applied
        py_meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}], {"x": 1}, return_meta=True
        )
        py_fields = set(py_meta.keys())

        # Required fields must be present in both
        assert REQUIRED_FIELDS <= js_fields, f"JS missing: {REQUIRED_FIELDS - js_fields}"
        assert REQUIRED_FIELDS <= py_fields, f"Python missing: {REQUIRED_FIELDS - py_fields}"
        # Required fields must match exactly (no extra required fields on either side)
        js_required = js_fields & REQUIRED_FIELDS
        py_required = py_fields & REQUIRED_FIELDS
        assert js_required == py_required, (
            f"Required field mismatch: JS={js_required}, Python={py_required}"
        )
