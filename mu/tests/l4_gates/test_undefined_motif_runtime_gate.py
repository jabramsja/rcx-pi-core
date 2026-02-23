"""L4 gate: Undefined motif runtime integration (Wave 22).

Proves that make_undefined_motif / makeUndefinedMotif exist in both substrates,
produce hashable Mu values with the canonical v0 key-set, and are wired into
the kernel stall path (return_meta=True).

Test classes:
1. TestMotifShapeLock — v0 key-set, types, pure-data property
2. TestMotifHashability — passes mu_hash_cached, stable across calls
3. TestMotifDeterminism — same inputs produce same output and hash
4. TestContractSplitLock — semantic undefined returns motif; contract
   violations still throw typed errors
5. TestCrossSubstrateParity — Python and JS produce same motif fields
6. TestSourceLock — helper exists in both runtime files
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    make_undefined_motif,
    step_kernel_mu,
    classify_terminal_kind,
)
from rcx_pi.selfhost.mu_type import mu_hash_cached

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PY_RUNTIME = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
JS_RUNTIME = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"

# Canonical v0 key-set
V0_KEYS = frozenset({"_undefined", "op", "lhs_hash", "rhs_hash", "cause", "details"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _simple_motif(**overrides):
    """Produce a motif with test defaults."""
    defaults = dict(op="test_op", lhs={"a": 1}, rhs={"b": 2}, cause="test_cause")
    defaults.update(overrides)
    return make_undefined_motif(**defaults)


def _run_js_api(request_dict: dict, *, timeout: int = 60) -> dict:
    """Call JS eval_step.js JSON API and return parsed response."""
    result = subprocess.run(
        ["node", str(JS_RUNTIME), "--json-api", json.dumps(request_dict)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=timeout,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(f"No JSON_API_RESPONSE in JS output: {result.stdout[:500]}")


# ===========================================================================
# 1. Motif Shape Lock
# ===========================================================================
class TestMotifShapeLock:
    """v0 motif has exact key-set, correct types, and is pure data."""

    def test_v0_keys_exact(self):
        motif = _simple_motif()
        assert set(motif.keys()) == V0_KEYS

    def test_undefined_flag_is_true(self):
        motif = _simple_motif()
        assert motif["_undefined"] is True

    def test_op_is_string(self):
        motif = _simple_motif()
        assert isinstance(motif["op"], str)

    def test_lhs_hash_is_string_or_none(self):
        motif = _simple_motif()
        assert isinstance(motif["lhs_hash"], str)
        motif_none = _simple_motif(lhs=None)
        assert motif_none["lhs_hash"] is None

    def test_rhs_hash_is_string_or_none(self):
        motif = _simple_motif()
        assert isinstance(motif["rhs_hash"], str)
        motif_none = _simple_motif(rhs=None)
        assert motif_none["rhs_hash"] is None

    def test_cause_is_string(self):
        motif = _simple_motif()
        assert isinstance(motif["cause"], str)

    def test_details_default_none(self):
        motif = _simple_motif()
        assert motif["details"] is None

    def test_details_dict_preserved(self):
        motif = _simple_motif(details={"reason": "test"})
        assert motif["details"] == {"reason": "test"}

    def test_motif_is_pure_data_dict(self):
        """No callables, no special types — plain JSON-serializable dict."""
        motif = _simple_motif()
        # Roundtrip through JSON proves pure data
        roundtrip = json.loads(json.dumps(motif, sort_keys=True))
        assert roundtrip["_undefined"] is True
        assert roundtrip["op"] == "test_op"


# ===========================================================================
# 2. Hashability Lock
# ===========================================================================
class TestMotifHashability:
    """Motif must pass through existing hash pipeline."""

    def test_mu_hash_cached_succeeds(self):
        motif = _simple_motif()
        h = mu_hash_cached(motif)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_with_none_fields(self):
        motif = _simple_motif(lhs=None, rhs=None, details=None)
        h = mu_hash_cached(motif)
        assert isinstance(h, str)


# ===========================================================================
# 3. Determinism Lock
# ===========================================================================
class TestMotifDeterminism:
    """Same inputs must produce identical motif and hash."""

    def test_same_inputs_same_motif(self):
        m1 = make_undefined_motif(op="x", lhs={"k": 1}, rhs=None, cause="c")
        m2 = make_undefined_motif(op="x", lhs={"k": 1}, rhs=None, cause="c")
        assert m1 == m2

    def test_same_inputs_same_hash(self):
        m1 = make_undefined_motif(op="x", lhs={"k": 1}, rhs=None, cause="c")
        m2 = make_undefined_motif(op="x", lhs={"k": 1}, rhs=None, cause="c")
        assert mu_hash_cached(m1) == mu_hash_cached(m2)

    def test_different_causes_different_hash(self):
        m1 = make_undefined_motif(op="x", lhs=None, rhs=None, cause="a")
        m2 = make_undefined_motif(op="x", lhs=None, rhs=None, cause="b")
        assert mu_hash_cached(m1) != mu_hash_cached(m2)


# ===========================================================================
# 4. Contract Split Lock
# ===========================================================================
class TestContractSplitLock:
    """Semantic undefined returns motif in meta; contract violations stay errors."""

    def test_kernel_stall_meta_contains_undefined_motif(self):
        """When kernel stalls (no matching projection), meta has undefined_motif."""
        # Use a projection that won't match the input
        proj = {"pattern": {"__never_match__": True}, "body": "irrelevant"}
        meta = step_kernel_mu(
            [proj], {"actual": "input"},
            return_meta=True, max_steps=10,
        )
        assert meta["stall"] is True
        assert meta["termination_reason"] == "kernel_stall"
        assert "undefined_motif" in meta
        motif = meta["undefined_motif"]
        assert motif["_undefined"] is True
        assert motif["op"] == "kernel"
        assert motif["cause"] == "no_matching_projection"
        assert isinstance(motif["lhs_hash"], str)

    def test_projection_applied_meta_no_undefined_motif(self):
        """When projection matches, meta should NOT have undefined_motif."""
        proj = {
            "id": "p.match",
            "pattern": {"x": {"var": "v"}},
            "body": {"ok": {"var": "v"}},
        }
        meta = step_kernel_mu(
            [proj], {"x": 42},
            return_meta=True, max_steps=100,
        )
        assert meta["stall"] is False
        assert "undefined_motif" not in meta

    def test_contract_violation_still_raises(self):
        """Non-Mu input triggers contract error, not motif."""
        with pytest.raises((TypeError, ValueError)):
            step_kernel_mu([{"pattern": 1, "body": 1}], object(), return_meta=True)

    def test_motif_not_confused_with_terminal(self):
        """Undefined motif is non_terminal by classifier."""
        motif = _simple_motif()
        assert classify_terminal_kind(motif) == "non_terminal"


# ===========================================================================
# 5. Cross-Substrate Parity Lock
# ===========================================================================
class TestCrossSubstrateParity:
    """Python and JS produce motifs with same field structure."""

    def test_js_motif_has_v0_keys(self):
        """JS makeUndefinedMotif produces the same key-set."""
        resp = _run_js_api({
            "action": "step_kernel_meta",
            "input": {"actual": "input"},
            "projections": [{"pattern": {"__never_match__": True}, "body": "irrelevant"}],
            "maxSteps": 10,
        })
        assert resp["success"] is True, f"JS API failed: {resp}"
        result = resp["result"]
        assert result["stall"] is True
        assert "undefined_motif" in result
        js_motif = result["undefined_motif"]
        assert set(js_motif.keys()) == {"_undefined", "op", "lhs_hash", "rhs_hash", "cause", "details"}
        assert js_motif["_undefined"] is True
        assert js_motif["op"] == "kernel"
        assert js_motif["cause"] == "no_matching_projection"

    def test_js_motif_lhs_hash_matches_python(self):
        """Python and JS produce the same lhs_hash for same input."""
        test_input = {"actual": "input"}
        py_hash = mu_hash_cached(test_input)
        resp = _run_js_api({
            "action": "step_kernel_meta",
            "input": test_input,
            "projections": [{"pattern": {"__never_match__": True}, "body": "x"}],
            "maxSteps": 10,
        })
        assert resp["success"] is True
        js_motif = resp["result"]["undefined_motif"]
        assert js_motif["lhs_hash"] == py_hash


# ===========================================================================
# 6. Source Lock
# ===========================================================================
class TestSourceLock:
    """Helper functions exist in both runtime source files."""

    def test_python_has_make_undefined_motif(self):
        src = PY_RUNTIME.read_text()
        assert re.search(r"def make_undefined_motif\(", src)

    def test_js_has_make_undefined_motif(self):
        src = JS_RUNTIME.read_text()
        assert re.search(r"function makeUndefinedMotif\(", src)

    def test_python_kernel_stall_calls_make_undefined_motif(self):
        src = PY_RUNTIME.read_text()
        assert "make_undefined_motif(" in src

    def test_js_kernel_stall_calls_make_undefined_motif(self):
        src = JS_RUNTIME.read_text()
        assert "makeUndefinedMotif(" in src
