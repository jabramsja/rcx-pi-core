"""D002: H2 Micro-Matcher Feasibility — Research Artifact

Tests H2 criterion 2: Can a micro-matcher handling ONLY the D001-enumerated
pattern set (5 matching primitives, 5 key signatures, 3 same-var constraints)
be expressed in <=50 LOC?

NOT production code. This file lives in tests/research/ and is never imported
by rcx_pi/. It validates that a staged bootstrap (Stage 0 micro-matcher) is
feasible in principle.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D002)
               mu/docs/core/G8CpsFeasibility.v0.md (H2 criterion 2)
"""

import inspect
import json
import textwrap
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# ---------------------------------------------------------------------------
# Micro-matcher: Stage 0 research prototype
# Handles exactly the 5 primitives from D001:
#   1. null_check    — pattern None matches value None
#   2. literal_string — pattern "x" matches value "x"
#   3. var_bind       — {"var": "name"} binds any value
#   4. nested_var_bind — {"var": {"var": "name"}} matches {"var": X}, binds X
#   5. dict_shape     — dict with exact key set, recurse into values
# Same-var equality: if a var name is already bound, value must equal binding.
# ---------------------------------------------------------------------------

_UNSET = object()


def micro_match(pattern, value, bindings=None):
    if bindings is None:
        bindings = {}
    if pattern is None:
        return bindings if value is None else None
    if isinstance(pattern, (str, int, float, bool)):
        return bindings if pattern == value else None
    if isinstance(pattern, dict):
        if "var" in pattern and len(pattern) == 1:
            var_val = pattern["var"]
            if isinstance(var_val, dict) and "var" in var_val and len(var_val) == 1:
                if not (isinstance(value, dict) and "var" in value and len(value) == 1):
                    return None
                name = var_val["var"]
                bound = bindings.get(name, _UNSET)
                if bound is not _UNSET:
                    return bindings if bound == value["var"] else None
                bindings[name] = value["var"]
                return bindings
            name = var_val
            bound = bindings.get(name, _UNSET)
            if bound is not _UNSET:
                return bindings if bound == value else None
            bindings[name] = value
            return bindings
        if not isinstance(value, dict) or pattern.keys() != value.keys():
            return None
        for key in pattern:
            if micro_match(pattern[key], value[key], bindings) is None:
                return None
        return bindings
    return None


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

SEEDS_DIR = REPO_ROOT / "mu" / "substrate"


def _load_projections(*seed_names):
    """Load projections from seed files."""
    projections = []
    for name in seed_names:
        seed = json.loads((SEEDS_DIR / name).read_text())
        for p in seed["projections"]:
            projections.append((name, p["id"], p["pattern"], p.get("body")))
    return projections


def _make_test_value(pattern, var_values):
    """Create a concrete value from a pattern by substituting var values."""
    if pattern is None:
        return None
    if isinstance(pattern, (str, int, float, bool)):
        return pattern
    if isinstance(pattern, dict):
        if "var" in pattern and len(pattern) == 1:
            var_val = pattern["var"]
            if isinstance(var_val, dict) and "var" in var_val and len(var_val) == 1:
                name = var_val["var"]
                return {"var": var_values.get(name, f"test_{name}")}
            name = var_val
            return var_values.get(name, f"test_{name}")
        return {k: _make_test_value(v, var_values) for k, v in pattern.items()}
    return pattern


def _extract_var_names(pattern):
    """Extract all var names from a pattern (for test value generation)."""
    names = set()
    if isinstance(pattern, dict):
        if "var" in pattern and len(pattern) == 1:
            var_val = pattern["var"]
            if isinstance(var_val, dict) and "var" in var_val and len(var_val) == 1:
                names.add(var_val["var"])
            elif isinstance(var_val, str):
                names.add(var_val)
        else:
            for v in pattern.values():
                names.update(_extract_var_names(v))
    return names


ALL_PROJECTIONS = _load_projections("match.v2.json", "subst.v2.json")


# ---------------------------------------------------------------------------
# Core tests: every projection matches its expected input
# ---------------------------------------------------------------------------

class TestMicroMatcherAllProjections:
    """Validate micro_match against all 21 match.v2 + subst.v2 patterns."""

    @pytest.mark.parametrize(
        "seed_name,proj_id,pattern,body",
        ALL_PROJECTIONS,
        ids=[f"{s}:{pid}" for s, pid, _, _ in ALL_PROJECTIONS],
    )
    def test_pattern_matches_constructed_value(self, seed_name, proj_id, pattern, body):
        var_names = _extract_var_names(pattern)
        var_values = {name: f"val_{name}" for name in var_names}
        test_value = _make_test_value(pattern, var_values)
        result = micro_match(pattern, test_value)
        assert result is not None, f"{proj_id}: expected match, got None"
        for name in var_names:
            assert name in result, f"{proj_id}: var '{name}' not in bindings"

    @pytest.mark.parametrize(
        "seed_name,proj_id,pattern,body",
        ALL_PROJECTIONS,
        ids=[f"{s}:{pid}" for s, pid, _, _ in ALL_PROJECTIONS],
    )
    def test_wrong_literal_rejects(self, seed_name, proj_id, pattern, body):
        """Changing a literal string in the value should cause mismatch."""
        if not isinstance(pattern, dict):
            pytest.skip("non-dict pattern")
        var_names = _extract_var_names(pattern)
        var_values = {name: f"val_{name}" for name in var_names}
        test_value = _make_test_value(pattern, var_values)
        # Find a literal key and corrupt it
        for key in pattern:
            if isinstance(pattern[key], str):
                corrupted = dict(test_value)
                corrupted[key] = "CORRUPTED_LITERAL"
                result = micro_match(pattern, corrupted)
                assert result is None, f"{proj_id}: should reject corrupted '{key}'"
                return
        pytest.skip("no literal string to corrupt")


# ---------------------------------------------------------------------------
# Same-var equality constraint tests (3 cases from D001)
# ---------------------------------------------------------------------------

class TestSameVarConstraints:
    """D001 identified 3 same-var equality constraints. Test each."""

    def test_match_equal_same_var(self):
        """match.equal: 'same' at pattern_focus and value_focus must be equal."""
        pattern = ALL_PROJECTIONS[2][2]  # match.equal
        assert ALL_PROJECTIONS[2][1] == "match.equal"
        # Same values -> match
        value_ok = _make_test_value(pattern, {"same": 42, "b": {}, "s": None, "ctx": {}})
        result = micro_match(pattern, value_ok)
        assert result is not None
        assert result["same"] == 42
        # Different values -> reject
        value_bad = dict(value_ok)
        value_bad["value_focus"] = 99
        result = micro_match(pattern, value_bad)
        assert result is None, "same-var constraint should reject different values"

    def test_match_typed_descend_same_type(self):
        """match.typed.descend: same-var 'type' at pattern/value focus type tag."""
        pattern = ALL_PROJECTIONS[4][2]  # match.typed.descend
        assert ALL_PROJECTIONS[4][1] == "match.typed.descend"
        value_ok = _make_test_value(pattern, {
            "type": "list", "ph": "a", "pt": "b", "vh": "c", "vt": "d",
            "b": {}, "s": None, "ctx": {},
        })
        result = micro_match(pattern, value_ok)
        assert result is not None
        assert result["type"] == "list"
        # Different _type -> reject
        value_bad = dict(value_ok)
        value_bad["value_focus"] = {"_type": "WRONG", "head": "c", "tail": "d"}
        result = micro_match(pattern, value_bad)
        assert result is None

    def test_subst_lookup_found_same_name(self):
        """subst.lookup.found: 'n' at lookup_name and lookup_bindings.name."""
        proj = [p for p in ALL_PROJECTIONS if p[1] == "subst.lookup.found"][0]
        pattern = proj[2]
        value_ok = _make_test_value(pattern, {
            "n": "x", "v": 42, "_rest": None, "b": {}, "c": None, "ctx": {},
        })
        result = micro_match(pattern, value_ok)
        assert result is not None
        assert result["n"] == "x"
        # Different name -> reject
        value_bad = dict(value_ok)
        value_bad["lookup_bindings"] = {"name": "WRONG", "value": 42, "rest": None}
        result = micro_match(pattern, value_bad)
        assert result is None


# ---------------------------------------------------------------------------
# Nested var bind tests (2 cases from D001)
# ---------------------------------------------------------------------------

class TestNestedVarBind:
    """D001 identified 2 nested_var_bind sites. Test each."""

    def test_match_var_nested_bind(self):
        """match.var: pattern_focus is {"var": {"var": "name"}}."""
        proj = [p for p in ALL_PROJECTIONS if p[1] == "match.var"][0]
        pattern = proj[2]
        value = _make_test_value(pattern, {
            "name": "x", "value": 42, "bindings": None, "stack": None, "ctx": {},
        })
        assert value["pattern_focus"] == {"var": "x"}
        result = micro_match(pattern, value)
        assert result is not None
        assert result["name"] == "x"
        assert result["value"] == 42

    def test_subst_var_nested_bind(self):
        """subst.var: focus is {"var": {"var": "name"}}."""
        proj = [p for p in ALL_PROJECTIONS if p[1] == "subst.var"][0]
        pattern = proj[2]
        value = _make_test_value(pattern, {
            "name": "y", "b": {}, "c": None, "ctx": {},
        })
        assert value["focus"] == {"var": "y"}
        result = micro_match(pattern, value)
        assert result is not None
        assert result["name"] == "y"


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------

class TestNegativeCases:
    """Ensure micro_match rejects non-matching inputs."""

    def test_wrong_key_set(self):
        result = micro_match({"a": 1, "b": 2}, {"a": 1, "c": 2})
        assert result is None

    def test_extra_key(self):
        result = micro_match({"a": 1}, {"a": 1, "b": 2})
        assert result is None

    def test_missing_key(self):
        result = micro_match({"a": 1, "b": 2}, {"a": 1})
        assert result is None

    def test_null_vs_non_null(self):
        assert micro_match(None, "x") is None
        assert micro_match("x", None) is None

    def test_literal_mismatch(self):
        assert micro_match("match", "subst") is None
        assert micro_match(42, 43) is None

    def test_nested_var_non_var_value(self):
        """nested_var_bind rejects values that aren't {"var": X}."""
        pattern = {"var": {"var": "name"}}
        assert micro_match(pattern, "not_a_var_dict") is None
        assert micro_match(pattern, {"not_var": "x"}) is None
        assert micro_match(pattern, {"var": "x", "extra": 1}) is None

    def test_dict_vs_non_dict(self):
        assert micro_match({"a": 1}, "string") is None
        assert micro_match({"a": 1}, 42) is None
        assert micro_match({"a": 1}, None) is None


# ---------------------------------------------------------------------------
# LOC measurement (D002 criterion 2: <= 50 LOC)
# ---------------------------------------------------------------------------

class TestLOCMeasurement:
    """Verify micro_match core is <= 50 LOC (excluding comments/blank lines)."""

    def test_matcher_loc_under_threshold(self):
        source = inspect.getsource(micro_match)
        lines = source.split("\n")
        # Count non-blank, non-comment lines (exclude def line per convention)
        code_lines = [
            line for line in lines[1:]  # skip def line
            if line.strip() and not line.strip().startswith("#")
        ]
        loc = len(code_lines)
        assert loc <= 50, f"micro_match is {loc} LOC, exceeds 50 LOC threshold"

    def test_no_new_primitives(self):
        """micro_match uses only standard Python — no imports, no I/O, no globals."""
        source = inspect.getsource(micro_match)
        assert "import " not in source
        assert "open(" not in source
        assert "print(" not in source
        assert "global " not in source
        assert "sys." not in source
        assert "os." not in source


# ---------------------------------------------------------------------------
# Projection count validation (matches D001)
# ---------------------------------------------------------------------------

class TestD001Consistency:
    """Verify D001 counts are still accurate."""

    def test_total_projection_count(self):
        assert len(ALL_PROJECTIONS) == 21

    def test_match_projection_count(self):
        match_projs = [p for p in ALL_PROJECTIONS if p[0] == "match.v2.json"]
        assert len(match_projs) == 8

    def test_subst_projection_count(self):
        subst_projs = [p for p in ALL_PROJECTIONS if p[0] == "subst.v2.json"]
        assert len(subst_projs) == 13

    def test_distinct_top_level_signatures(self):
        sigs = set()
        for _, _, pattern, _ in ALL_PROJECTIONS:
            if isinstance(pattern, dict):
                sigs.add(tuple(sorted(pattern.keys())))
        assert len(sigs) == 5
