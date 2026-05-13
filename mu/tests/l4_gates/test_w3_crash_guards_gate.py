"""
L4 gate tests for W3-CRASH: Runtime Crash Guards.

Verifies fixes for 4 fuzzer-confirmed crash/false-positive paths:
- F-10: denormalize_from_match crashes on malformed kv nodes (typed + legacy loops)
- F-11: match() raises ValueError on empty var-name {"var": ""}
- F-12: bindings_to_dict() silently accepts non-string binding names
- F-13: _iter_normalized_dict_pairs() cap 100 vs MAX_MU_WIDTH 1000
"""
import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT
from rcx_pi.selfhost.eval_seed import match, NO_MATCH, _stage0_match  # ANTICHEAT_OK: founder-approved direct call for gate test
from rcx_pi.selfhost.match_mu import denormalize_from_match, bindings_to_dict
from rcx_pi.selfhost.step_mu import _iter_normalized_dict_pairs  # ANTICHEAT_OK: founder-approved direct call for gate test
from rcx_pi.selfhost.mu_type import MAX_MU_WIDTH

JS_TRUST_MU_PRELUDE = """
const muContainers = require('./mu/host/js/core/container_factory');
function trustMu(value) {
  if (Array.isArray(value)) return muContainers.list(value.map(trustMu));
  if (value !== null && typeof value === 'object') {
    return muContainers.record(Object.keys(value).map(key => [key, trustMu(value[key])]));
  }
  return value;
}
"""


# ---------------------------------------------------------------------------
# F-10: denormalize_from_match malformed kv guards
# ---------------------------------------------------------------------------

class TestF10DenormalizeMalformedKv:
    """F-10: Malformed dict-kv nodes are skipped, not crash."""

    def test_typed_dict_none_tail_no_crash(self):
        """Exact crash repro: kv node with None tail in typed dict."""
        # Typed dict with one malformed kv (tail is None instead of {head: val, tail: ...})
        malformed = {
            "_type": "dict",
            "head": {"head": "key1", "tail": None},  # malformed: tail should be {head: val}
            "tail": None,
        }
        # Should not crash — malformed kv is skipped
        result = denormalize_from_match(malformed)
        assert isinstance(result, dict)

    def test_typed_dict_malformed_first_valid_second(self):
        """Malformed first kv + valid second kv preserves the valid pair."""
        malformed_kv = {"head": "bad_key", "tail": None}
        valid_kv = {"head": "good_key", "tail": {"head": 42, "tail": None}}
        typed_dict = {
            "_type": "dict",
            "head": malformed_kv,
            "tail": {"head": valid_kv, "tail": None},
        }
        result = denormalize_from_match(typed_dict)
        assert isinstance(result, dict)
        assert result.get("good_key") == 42

    def test_legacy_dict_malformed_kv_tail_no_crash(self):
        """Legacy dict: kv node with None tail doesn't crash (no-crash lock).

        Classifier may route to list or dict path depending on projection
        result. Either way, the function must not raise.
        """
        kv_good = {"head": "good", "tail": {"head": 1, "tail": None}}
        kv_bad = {"head": "bad", "tail": None}  # malformed: kv tail should be {head: val}
        legacy = {
            "head": kv_bad,
            "tail": {"head": kv_good, "tail": None},
        }
        # Must not crash — result type depends on classifier routing
        result = denormalize_from_match(legacy)
        assert result is not None

    def test_legacy_dict_malformed_kv_nondict_head_regression(self):
        """Regression lock: non-dict kv node in legacy linked list doesn't crash."""
        kv_ok = {"head": "ok", "tail": {"head": 42, "tail": None}}
        legacy = {
            "head": kv_ok,
            "tail": {"head": 99, "tail": None},  # head is int, not kv-pair
        }
        # Must not crash
        result = denormalize_from_match(legacy)
        assert result is not None

    def test_cross_substrate_parity_malformed_kv(self):
        """Python result equals JS result for same malformed input."""
        # Typed dict with malformed kv node
        malformed_input = {
            "_type": "dict",
            "head": {"head": "key1", "tail": None},
            "tail": {
                "head": {"head": "key2", "tail": {"head": 99, "tail": None}},
                "tail": None,
            },
        }
        py_result = denormalize_from_match(malformed_input)

        js_script = (
            "const { denormalize } = require('./mu/host/js/core/normalize');\n"
            f"{JS_TRUST_MU_PRELUDE}\n"
            f"const input = {json.dumps(malformed_input)};\n"
            "try {\n"
            "  const result = denormalize(trustMu(input));\n"
            "  console.log(JSON.stringify(result));\n"
            "} catch (e) {\n"
            "  console.log(JSON.stringify({__error: e.message}));\n"
            "}\n"
        )
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert proc.returncode == 0, f"JS error: {proc.stderr}"
        js_result = json.loads(proc.stdout.strip())

        # Both should produce the same dict (malformed kv skipped, valid kv kept)
        assert py_result == js_result, (
            f"Cross-substrate parity failure:\n  Python: {py_result}\n  JS: {js_result}"
        )


# ---------------------------------------------------------------------------
# F-10 adjacent: legacy LIST loop structural guard
# ---------------------------------------------------------------------------

class TestF10LegacyListStructuralGuard:
    """Legacy list loop: non-dict tail node raises fail-closed."""

    def test_legacy_list_nondict_tail_raises(self):
        """denormalize_from_match({'head': 1, 'tail': 42}) raises (fail-closed).

        Red-team finding: legacy list loop accessed current["head"] without
        checking isinstance(current, dict), causing TypeError on int tail.
        Original W3 fix: silent truncation. Current fix: fail-closed raise.
        """
        malformed = {"head": 1, "tail": 42}
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(malformed)

    def test_legacy_list_string_tail_raises(self):
        """Legacy list with string tail raises (fail-closed)."""
        malformed = {"head": "a", "tail": "not_a_node"}
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(malformed)

    def test_cross_substrate_parity_malformed_legacy_list(self):
        """Both substrates raise on malformed legacy list (parity)."""
        malformed_input = {"head": 1, "tail": 42}

        # Python raises
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(malformed_input)

        # JS also raises
        js_script = (
            "const { denormalize } = require('./mu/host/js/core/normalize');\n"
            f"{JS_TRUST_MU_PRELUDE}\n"
            f"const input = {json.dumps(malformed_input)};\n"
            "try {\n"
            "  denormalize(trustMu(input));\n"
            "  console.log('ERROR: should have thrown');\n"
            "  process.exit(1);\n"
            "} catch (e) {\n"
            "  console.log(e.message);\n"
            "}\n"
        )
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=10,
        )
        assert proc.returncode == 0, f"JS error: {proc.stderr}"
        assert "Improper linked list tail" in proc.stdout, (
            f"JS did not raise on improper tail: {proc.stdout}"
        )


# ---------------------------------------------------------------------------
# F-11: Empty var-name returns NO_MATCH
# ---------------------------------------------------------------------------

class TestF11EmptyVarNameNoMatch:
    """F-11: match({"var": ""}, x) returns NO_MATCH, not ValueError."""

    def test_empty_var_match_int(self):
        assert match({"var": ""}, 42) is NO_MATCH

    def test_empty_var_match_str(self):
        assert match({"var": ""}, "hello") is NO_MATCH

    def test_empty_var_match_none(self):
        assert match({"var": ""}, None) is NO_MATCH

    def test_empty_var_match_dict(self):
        assert match({"var": ""}, {"a": 1}) is NO_MATCH

    def test_stage0_match_empty_var_int(self):
        """Direct _stage0_match call — founder-approved for gate tests."""
        result = _stage0_match({"var": ""}, 42)
        assert result is NO_MATCH

    def test_stage0_match_empty_var_dict(self):
        result = _stage0_match({"var": ""}, {"x": 1})
        assert result is NO_MATCH

    def test_stage0_match_empty_var_with_bindings(self):
        result = _stage0_match({"var": ""}, 42, bindings={"x": 1})
        assert result is NO_MATCH


# ---------------------------------------------------------------------------
# F-25 JS parity: stage0Match rejects empty var name
# ---------------------------------------------------------------------------

class TestF25JsStage0MatchEmptyVar:
    """F-25: JS stage0Match({var: ""}, x) returns NO_MATCH — direct call proof."""

    def test_js_stage0_match_empty_var(self):
        """stage0Match({var: ""}, 42) must return NO_MATCH, not bind {"": 42}."""
        js_script = (
            "const { stage0Match } = require('./mu/host/js/core/bootstrap_core');\n"
            "const { NO_MATCH } = require('./mu/host/js/core/constants');\n"
            "const r = stage0Match({var: ''}, 42);\n"
            "if (r !== NO_MATCH) {\n"
            "  process.stderr.write('FAIL: got ' + JSON.stringify(r));\n"
            "  process.exit(1);\n"
            "}\n"
            "console.log('PASS');\n"
        )
        proc = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert proc.returncode == 0, f"JS stage0Match empty-var failed: {proc.stderr}"
        assert proc.stdout.strip() == "PASS"


# ---------------------------------------------------------------------------
# F-12: bindings_to_dict non-string name guard
# ---------------------------------------------------------------------------

class TestF12BindingsNonStringName:
    """F-12: Non-string binding names raise ValueError."""

    def test_int_name_raises(self):
        linked = {"name": 0, "value": 42, "rest": None}
        try:
            bindings_to_dict(linked)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "int" in str(e)

    def test_float_name_raises(self):
        linked = {"name": 1.5, "value": "x", "rest": None}
        try:
            bindings_to_dict(linked)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "float" in str(e)

    def test_bool_name_raises(self):
        linked = {"name": True, "value": 1, "rest": None}
        try:
            bindings_to_dict(linked)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "bool" in str(e)

    def test_list_name_raises(self):
        linked = {"name": [1, 2], "value": "x", "rest": None}
        try:
            bindings_to_dict(linked)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "list" in str(e)

    def test_valid_string_name_still_works(self):
        linked = {"name": "x", "value": 42, "rest": None}
        result = bindings_to_dict(linked)
        assert result == {"x": 42}

    def test_valid_multi_binding(self):
        linked = {
            "name": "a",
            "value": 1,
            "rest": {"name": "b", "value": 2, "rest": None},
        }
        result = bindings_to_dict(linked)
        assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# F-13: _iter_normalized_dict_pairs width cap
# ---------------------------------------------------------------------------

def _make_normalized_dict(n: int):
    """Build a normalized dict linked list with n key-value pairs."""
    current = None
    for i in range(n - 1, -1, -1):
        kv = {"head": f"k{i}", "tail": {"head": i, "tail": None}}
        current = {"head": kv, "tail": current}
    return {"_type": "dict", "head": current["head"], "tail": current.get("tail")} if current else None


class TestF13WidthCap:
    """F-13: _iter_normalized_dict_pairs uses MAX_MU_WIDTH, not 100."""

    def test_100_entry_accepted(self):
        value = _make_normalized_dict(100)
        result = _iter_normalized_dict_pairs(value)
        assert result is not None
        assert len(result) == 100

    def test_101_entry_accepted(self):
        """101 entries: was broken when cap was 100."""
        value = _make_normalized_dict(101)
        result = _iter_normalized_dict_pairs(value)
        assert result is not None
        assert len(result) == 101

    def test_max_mu_width_accepted(self):
        value = _make_normalized_dict(MAX_MU_WIDTH)
        result = _iter_normalized_dict_pairs(value)
        assert result is not None
        assert len(result) == MAX_MU_WIDTH

    def test_max_mu_width_plus_1_rejected(self):
        value = _make_normalized_dict(MAX_MU_WIDTH + 1)
        result = _iter_normalized_dict_pairs(value)
        assert result is None
