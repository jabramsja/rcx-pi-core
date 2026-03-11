"""
Wave B Security Gate Tests — net-new coverage only.

Tests denormalize consolidation regression, MAX_DENORM_ITER boundaries,
improper-tail fail-closed behavior, and applyProjection trust-split parity.
Does NOT duplicate depth alignment (test_validation_depth_alignment_gate.py owns that).
"""
import ast
import os

import pytest

from tests.repo_root import REPO_ROOT

# Public API imports only (anti-cheat: no underscored imports)
from rcx_pi.selfhost.match_mu import (
    normalize_for_match,
    denormalize_from_match,
    MAX_DENORM_ITER,
    VALID_TYPE_TAGS,
)
from rcx_pi.selfhost.eval_seed import (
    apply_projection,
)
from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH

JS_DIR = REPO_ROOT / "mu" / "host" / "js"


# =============================================================================
# Denormalize Consolidation Regression Tests
# =============================================================================

class TestDenormalizeConsolidation:
    """Verify all 4 denormalize paths produce correct results after helper extraction."""

    def test_typed_list_roundtrip(self):
        """Typed list normalizes and denormalizes correctly."""
        original = [1, 2, 3, "hello", None]
        normalized = normalize_for_match(original)
        result = denormalize_from_match(normalized)
        assert result == original

    def test_typed_dict_roundtrip(self):
        """Typed dict normalizes and denormalizes correctly."""
        original = {"a": 1, "b": "two", "c": None}
        normalized = normalize_for_match(original)
        result = denormalize_from_match(normalized)
        assert result == original

    def test_legacy_list_roundtrip(self):
        """Legacy (untyped) list linked list denormalizes correctly."""
        # Build a legacy head/tail list without _type tag
        legacy_list = {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": None}}}
        result = denormalize_from_match(legacy_list)
        assert result == [1, 2, 3]

    def test_legacy_dict_roundtrip(self):
        """Legacy (untyped) dict linked list denormalizes correctly."""
        # Build a legacy dict encoding: kv-pair linked list
        kv1 = {"head": "a", "tail": {"head": 1, "tail": None}}
        kv2 = {"head": "b", "tail": {"head": 2, "tail": None}}
        legacy_dict = {"head": kv1, "tail": {"head": kv2, "tail": None}}
        result = denormalize_from_match(legacy_dict)
        assert result == {"a": 1, "b": 2}

    def test_nested_typed_containers(self):
        """Nested typed containers roundtrip correctly."""
        original = {"x": [1, {"y": 2}], "z": []}
        normalized = normalize_for_match(original)
        result = denormalize_from_match(normalized)
        assert result == original

    def test_empty_typed_list(self):
        """Empty typed list roundtrips."""
        normalized = normalize_for_match([])
        result = denormalize_from_match(normalized)
        assert result == []

    def test_empty_typed_dict(self):
        """Empty typed dict roundtrips."""
        normalized = normalize_for_match({})
        result = denormalize_from_match(normalized)
        assert result == {}


# =============================================================================
# MAX_DENORM_ITER Boundary Tests
# =============================================================================

class TestMaxDenormIterBoundary:
    """Verify the MAX_DENORM_ITER=10000 guard triggers correctly."""

    def test_constant_value(self):
        """MAX_DENORM_ITER is 10000 (parity with JS constants.js)."""
        assert MAX_DENORM_ITER == 10000

    def test_large_list_within_limit(self):
        """A list within the iteration limit denormalizes successfully."""
        # Build a normalized list with 100 elements (well within limit)
        original = list(range(100))
        normalized = normalize_for_match(original)
        result = denormalize_from_match(normalized)
        assert result == original

    def test_circular_reference_detected(self):
        """Circular linked list is detected and raises ValueError."""
        # Build a circular linked list
        node = {"head": 1, "tail": None}
        node["tail"] = node  # circular!
        with pytest.raises(ValueError, match="Circular reference"):
            denormalize_from_match({"_type": "list", "head": 1, "tail": node})


# =============================================================================
# Improper Tail Fail-Closed Tests
# =============================================================================

class TestImproperTailFailClosed:
    """Verify that non-null tail terminators raise, not silently drop data."""

    def test_typed_list_improper_tail_raises(self):
        """Typed list with non-null tail terminator raises ValueError."""
        bad_list = {
            "_type": "list",
            "head": 1,
            "tail": {"head": 2, "tail": "IMPROPER"}
        }
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(bad_list)

    def test_typed_dict_improper_tail_raises(self):
        """Typed dict with non-null tail terminator raises ValueError."""
        kv = {"head": "key", "tail": {"head": "val", "tail": None}}
        bad_dict = {
            "_type": "dict",
            "head": kv,
            "tail": 42  # improper!
        }
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(bad_dict)

    def test_legacy_list_improper_tail_raises(self):
        """Legacy list with non-null tail terminator raises ValueError."""
        bad_list = {"head": 1, "tail": {"head": 2, "tail": "IMPROPER"}}
        with pytest.raises(ValueError, match="improper linked list tail"):
            denormalize_from_match(bad_list)


# =============================================================================
# applyProjection Trust-Split Parity
# =============================================================================

class TestApplyProjectionTrustSplit:
    """Verify the public/trusted split exists and has correct structure."""

    def test_python_apply_projection_validates_input(self):
        """Public apply_projection calls assert_mu; trusted path does not."""
        import rcx_pi.selfhost.eval_seed as mod
        source_tree = ast.parse(open(mod.__file__).read())
        # Find both function bodies and check for assert_mu calls
        for node in ast.walk(source_tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == "apply_projection":
                    # Public path must call assert_mu
                    calls = [
                        n.func.id for n in ast.walk(node)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ]
                    assert "assert_mu" in calls, \
                        "apply_projection must call assert_mu"
                elif node.name == "_apply_projection_trusted":
                    # Trusted path must NOT call assert_mu
                    calls = [
                        n.func.id for n in ast.walk(node)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    ]
                    assert "assert_mu" not in calls, \
                        "_apply_projection_trusted must NOT call assert_mu"

    def test_python_trusted_path_exists_in_source(self):
        """_apply_projection_trusted function exists in eval_seed.py source."""
        import rcx_pi.selfhost.eval_seed as mod
        source = ast.parse(open(mod.__file__).read())
        func_names = [n.name for n in ast.walk(source) if isinstance(n, ast.FunctionDef)]
        assert "_apply_projection_trusted" in func_names

    def test_js_trusted_path_exists_in_source(self):
        """_applyProjectionTrusted function exists in bootstrap_core.js source."""
        js_path = JS_DIR / "core" / "bootstrap_core.js"
        content = js_path.read_text()
        assert "function _applyProjectionTrusted(" in content
        assert "function applyProjection(" in content


# =============================================================================
# JS Denormalize Safety (JSON.stringify Removal)
# =============================================================================

class TestJsDenormalizeSafety:
    """Verify JS denormalize uses safe error messages, not JSON.stringify."""

    def test_no_json_stringify_in_denormalize(self):
        """normalize.js denormalize must not use JSON.stringify in error paths."""
        js_path = JS_DIR / "core" / "normalize.js"
        content = js_path.read_text()
        # Find denormalize function body
        start = content.index("function denormalize(")
        # JSON.stringify should NOT appear after the denormalize function definition
        denorm_body = content[start:]
        assert "JSON.stringify" not in denorm_body, \
            "denormalize must not use JSON.stringify (fragile on circular/BigInt)"

    def test_safe_summary_helper_exists(self):
        """_safeSummary helper exists in normalize.js."""
        js_path = JS_DIR / "core" / "normalize.js"
        content = js_path.read_text()
        assert "function _safeSummary(" in content

    def test_js_collect_helpers_exist(self):
        """_collectListElements and _collectDictKVPairs helpers exist."""
        js_path = JS_DIR / "core" / "normalize.js"
        content = js_path.read_text()
        assert "function _collectListElements(" in content
        assert "function _collectDictKVPairs(" in content


# =============================================================================
# Python Denormalize Consolidation Source Checks
# =============================================================================

class TestPythonDenormalizeConsolidation:
    """Verify Python denormalize uses consolidated helpers."""

    def test_helpers_exist_in_source(self):
        """_collect_kv_pairs and _collect_elements exist in match_mu.py."""
        import rcx_pi.selfhost.match_mu as mod
        source = ast.parse(open(mod.__file__).read())
        func_names = [n.name for n in ast.walk(source) if isinstance(n, ast.FunctionDef)]
        assert "_collect_kv_pairs" in func_names
        assert "_collect_elements" in func_names

    def test_no_inline_max_denorm_iter(self):
        """No inline MAX_DENORM_ITER = 10000 definitions inside functions."""
        import rcx_pi.selfhost.match_mu as mod
        source = open(mod.__file__).read()
        # Count occurrences of "MAX_DENORM_ITER = 10000"
        count = source.count("MAX_DENORM_ITER = 10000")
        # Should be exactly 1 (the module-level definition)
        assert count == 1, \
            f"Expected 1 module-level MAX_DENORM_ITER definition, found {count}"

    def test_module_level_constant_exported(self):
        """MAX_DENORM_ITER is importable from match_mu."""
        from rcx_pi.selfhost.match_mu import MAX_DENORM_ITER
        assert MAX_DENORM_ITER == 10000


# =============================================================================
# Seed Status Sidecar Registry
# =============================================================================

class TestSeedStatusRegistry:
    """Verify SEED_STATUS sidecar registry exists and is well-formed."""

    def test_seed_status_importable(self):
        """SEED_STATUS is importable from seed_integrity."""
        from rcx_pi.selfhost.seed_integrity import SEED_STATUS
        assert isinstance(SEED_STATUS, dict)

    def test_seed_status_does_not_modify_checksums(self):
        """SEED_CHECKSUMS values are still plain strings (not dicts)."""
        from rcx_pi.selfhost.seed_integrity import SEED_CHECKSUMS
        for name, value in SEED_CHECKSUMS.items():
            assert isinstance(value, str), \
                f"SEED_CHECKSUMS['{name}'] should be str, got {type(value)}"

    def test_legacy_poc_seeds_marked(self):
        """v1 seeds that have v2 replacements are marked legacy-poc."""
        from rcx_pi.selfhost.seed_integrity import SEED_STATUS
        assert SEED_STATUS.get("recurrence.v1.json") == "legacy-poc"
        assert SEED_STATUS.get("match.v1.json") == "legacy-poc"
        assert SEED_STATUS.get("subst.v1.json") == "legacy-poc"

    def test_seed_status_values_valid(self):
        """All SEED_STATUS values are from the allowed set."""
        from rcx_pi.selfhost.seed_integrity import SEED_STATUS
        allowed = {"production", "legacy-poc"}
        for name, status in SEED_STATUS.items():
            assert status in allowed, \
                f"SEED_STATUS['{name}'] = '{status}' not in {allowed}"
