"""
Subst v2 Parity Tests - Verify subst.v2.json preserves v1 behavior.

Phase 7b added context passthrough (_subst_ctx) to all substitution projections.
These tests verify that:
1. v2 seed structure is compatible with v1
2. All v1 projection IDs exist in v2
3. subst_mu() (using v1) behavior is unchanged
4. Execution parity: v1 and v2 produce identical substitution results

If these tests fail after modifying subst.v2.json, the change may have broken
backward compatibility with v1 behavior.
"""

import pytest

from rcx_pi.selfhost.subst_mu import subst_mu
from rcx_pi.selfhost.match_mu import normalize_for_match, dict_to_bindings
from rcx_pi.selfhost.projection_runner import make_projection_runner
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


class TestSubstV2SeedStructure:
    """Verify v2 seed structure is compatible with v1."""

    @pytest.fixture
    def v1_seed(self):
        return load_verified_seed(get_seed_path("subst.v1.json"))

    @pytest.fixture
    def v2_seed(self):
        return load_verified_seed(get_seed_path("subst.v2.json"))

    def test_v2_has_all_v1_projection_ids(self, v1_seed, v2_seed):
        """All v1 projection IDs must exist in v2."""
        v1_ids = {p["id"] for p in v1_seed["projections"]}
        v2_ids = {p["id"] for p in v2_seed["projections"]}

        missing = v1_ids - v2_ids
        assert not missing, f"v2 missing v1 projection IDs: {missing}"

    def test_v2_has_context_passthrough(self, v2_seed):
        """v2 projections must have _subst_ctx passthrough."""
        for proj in v2_seed["projections"]:
            # All v2 projections should reference _subst_ctx
            proj_str = str(proj)
            assert "_subst_ctx" in proj_str, f"Projection {proj['id']} missing _subst_ctx"

    def test_v2_projection_count(self, v1_seed, v2_seed):
        """v2 must have >= v1 projections (v2 may add new projections)."""
        v1_count = len(v1_seed["projections"])
        v2_count = len(v2_seed["projections"])

        assert v2_count == 13, (
            f"v2 has {v2_count} projections, expected 13"
        )
        assert v2_count >= v1_count, (
            f"v2 has {v2_count} projections, fewer than v1's {v1_count}"
        )

    def test_v2_wrap_is_last(self, v2_seed):
        """subst.wrap must be last projection (entry point)."""
        ids = [p["id"] for p in v2_seed["projections"]]
        assert ids[-1] == "subst.wrap", f"Last projection should be subst.wrap, got {ids[-1]}"

    def test_v2_done_is_first(self, v2_seed):
        """subst.done must be first projection (exit point)."""
        ids = [p["id"] for p in v2_seed["projections"]]
        assert ids[0] == "subst.done", f"First projection should be subst.done, got {ids[0]}"


class TestSubstMuBehaviorStable:
    """Verify subst_mu() behavior is unchanged (uses v1 internally)."""

    def test_literal_passthrough(self):
        """Literals pass through unchanged."""
        assert subst_mu(42, {}) == 42

    def test_string_passthrough(self):
        """Strings pass through unchanged."""
        assert subst_mu("hello", {}) == "hello"

    def test_variable_substitution(self):
        """Variables are substituted correctly."""
        assert subst_mu({"var": "x"}, {"x": 42}) == 42

    def test_dict_substitution(self):
        """Dict values are substituted correctly."""
        result = subst_mu({"a": {"var": "x"}, "b": 2}, {"x": 1})
        assert result == {"a": 1, "b": 2}

    def test_nested_substitution(self):
        """Nested structures are substituted correctly."""
        result = subst_mu(
            {"outer": {"inner": {"var": "v"}}},
            {"v": 99}
        )
        assert result == {"outer": {"inner": 99}}

    def test_multiple_variables(self):
        """Multiple variables are substituted correctly."""
        result = subst_mu(
            {"x": {"var": "a"}, "y": {"var": "b"}},
            {"a": 1, "b": 2}
        )
        assert result == {"x": 1, "y": 2}

    def test_no_substitution_needed(self):
        """Body without variables passes through unchanged."""
        result = subst_mu({"a": 1, "b": {"c": 2}}, {"unused": 99})
        assert result == {"a": 1, "b": {"c": 2}}

    def test_null_passthrough(self):
        """Null passes through unchanged."""
        assert subst_mu(None, {}) is None

    def test_bool_passthrough(self):
        """Booleans pass through unchanged."""
        assert subst_mu(True, {}) is True
        assert subst_mu(False, {}) is False

    def test_variable_to_dict(self):
        """Variable can be substituted with dict value."""
        result = subst_mu(
            {"result": {"var": "data"}},
            {"data": {"nested": {"value": 123}}}
        )
        assert result == {"result": {"nested": {"value": 123}}}

    def test_deeply_nested(self):
        """Deeply nested structures work correctly."""
        result = subst_mu(
            {"a": {"b": {"c": {"d": {"var": "x"}}}}},
            {"x": "deep"}
        )
        assert result == {"a": {"b": {"c": {"d": "deep"}}}}


class TestSubstV2ContextDesign:
    """Verify _subst_ctx design is correct."""

    def test_context_is_variable_bound(self):
        """_subst_ctx should be bound via variable pattern."""
        v2_seed = load_verified_seed(get_seed_path("subst.v2.json"))

        for proj in v2_seed["projections"]:
            pattern = proj["pattern"]
            body = proj["body"]

            # Context should be bound in pattern
            ctx_pattern = pattern.get("_subst_ctx")
            assert ctx_pattern == {"var": "ctx"}, (
                f"Projection {proj['id']} should bind _subst_ctx to 'ctx'"
            )

            # Context should be passed through in body
            ctx_body = body.get("_subst_ctx")
            assert ctx_body == {"var": "ctx"}, (
                f"Projection {proj['id']} should pass _subst_ctx unchanged"
            )

    def test_done_preserves_context(self):
        """subst.done should preserve context in output."""
        v2_seed = load_verified_seed(get_seed_path("subst.v2.json"))
        done_proj = next(p for p in v2_seed["projections"] if p["id"] == "subst.done")

        body = done_proj["body"]
        assert "_subst_ctx" in body, "subst.done must preserve _subst_ctx"
        assert body["_subst_ctx"] == {"var": "ctx"}, "subst.done must pass through context"


class TestSubstV1V2ExecutionParity:
    """Execution parity: v1 and v2 projections produce identical results.

    subst_mu() uses subst.v1.json internally, but the kernel uses subst.v2.json.
    This test runs the same normalized inputs through both seed versions and
    asserts output equivalence, catching semantic drift between v1 and v2.
    """

    @pytest.fixture(autouse=True)
    def _reset_budget(self):
        """Reset step budget before each test."""
        reset_step_budget()

    @pytest.fixture
    def v1_projections(self):
        return load_verified_seed(get_seed_path("subst.v1.json"))["projections"]

    @pytest.fixture
    def v2_projections(self):
        return load_verified_seed(get_seed_path("subst.v2.json"))["projections"]

    def _run_v1(self, v1_projs, norm_body, linked_bindings):
        """Run substitution through v1 projections (mode-based terminal)."""
        _, _, run = make_projection_runner("subst")
        initial = {"subst": {"body": norm_body, "bindings": linked_bindings}}
        final, steps, is_stall = run(v1_projs, initial, max_steps=200)
        assert not is_stall, f"v1 stalled at step {steps}: {final}"
        assert final.get("mode") == "subst_done", f"v1 unexpected terminal: {final}"
        return final["result"]

    def _run_v2(self, v2_projs, norm_body, linked_bindings):
        """Run substitution through v2 projections (_mode-based terminal)."""
        _, _, run = make_projection_runner("subst", terminal_field="_mode")
        ctx = {"_input": "parity_test", "_remaining": None}
        initial = {
            "subst": {"body": norm_body, "bindings": linked_bindings},
            "_subst_ctx": ctx,
        }
        final, steps, is_stall = run(v2_projs, initial, max_steps=200)
        assert not is_stall, f"v2 stalled at step {steps}: {final}"
        assert final.get("_mode") == "subst_done", f"v2 unexpected terminal: {final}"
        # Verify context passthrough as side-check
        assert mu_equal(final.get("_subst_ctx"), ctx), "v2 lost _subst_ctx"
        return final["_result"]

    def _assert_parity(self, v1_projs, v2_projs, body, bindings, label):
        """Assert v1 and v2 produce identical results for same inputs."""
        norm_body = normalize_for_match(body)
        linked = dict_to_bindings(bindings)
        r1 = self._run_v1(v1_projs, norm_body, linked)
        reset_step_budget()
        r2 = self._run_v2(v2_projs, norm_body, linked)
        assert mu_equal(r1, r2), (
            f"v1/v2 execution divergence on {label}: v1={r1!r}, v2={r2!r}"
        )

    def test_literal_parity(self, v1_projections, v2_projections):
        """Literal passthrough produces same result in v1 and v2."""
        self._assert_parity(v1_projections, v2_projections, 42, {}, "literal")

    def test_string_parity(self, v1_projections, v2_projections):
        """String passthrough produces same result in v1 and v2."""
        self._assert_parity(v1_projections, v2_projections, "hello", {}, "string")

    def test_null_parity(self, v1_projections, v2_projections):
        """Null passthrough produces same result in v1 and v2."""
        self._assert_parity(v1_projections, v2_projections, None, {}, "null")

    def test_bool_parity(self, v1_projections, v2_projections):
        """Boolean passthrough produces same result in v1 and v2."""
        self._assert_parity(v1_projections, v2_projections, True, {}, "bool_true")
        reset_step_budget()
        self._assert_parity(v1_projections, v2_projections, False, {}, "bool_false")

    def test_variable_substitution_parity(self, v1_projections, v2_projections):
        """Variable lookup produces same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"var": "x"}, {"x": 42}, "var_subst"
        )

    def test_dict_substitution_parity(self, v1_projections, v2_projections):
        """Dict with variable produces same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"a": {"var": "x"}, "b": 2}, {"x": 1}, "dict_subst"
        )

    def test_nested_substitution_parity(self, v1_projections, v2_projections):
        """Nested structures produce same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"outer": {"inner": {"var": "v"}}}, {"v": 99}, "nested_subst"
        )

    def test_multiple_variables_parity(self, v1_projections, v2_projections):
        """Multiple variable sites produce same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"x": {"var": "a"}, "y": {"var": "b"}}, {"a": 1, "b": 2},
            "multi_var"
        )

    def test_list_substitution_parity(self, v1_projections, v2_projections):
        """List body produces same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            [{"var": "a"}, 10, {"var": "b"}], {"a": 1, "b": 2},
            "list_subst"
        )

    def test_deeply_nested_parity(self, v1_projections, v2_projections):
        """Deeply nested dict produces same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"a": {"b": {"c": {"d": {"var": "x"}}}}}, {"x": "deep"},
            "deep_nested"
        )

    def test_no_vars_parity(self, v1_projections, v2_projections):
        """Body with no variables produces same result in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"a": 1, "b": {"c": 2}}, {"unused": 99}, "no_vars"
        )

    def test_var_to_dict_parity(self, v1_projections, v2_projections):
        """Variable substituted with dict value same in v1 and v2."""
        self._assert_parity(
            v1_projections, v2_projections,
            {"result": {"var": "data"}},
            {"data": {"nested": {"value": 123}}},
            "var_to_dict"
        )
