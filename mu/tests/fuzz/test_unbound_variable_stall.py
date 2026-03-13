"""
Fuzz test: unbound variable substitution path.

Exercises the production path where a projection body contains a variable
({"var": "x"}) that was NOT bound during pattern matching. Both _stage0_substitute
and substitute raise KeyError("Unbound variable: x") — fail-closed behavior.

This gap was identified by the fuzzer agent (2026-03-11): hypothesis doesn't
naturally generate the specific (body-has-var, pattern-lacks-var) pair.

Usage:
    PYTHONHASHSEED=0 pytest tests/fuzz/test_unbound_variable_stall.py -v
"""

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite

from rcx_pi.selfhost.eval_seed import (
    _stage0_substitute,  # ANTICHEAT_OK: fuzz-testing kernel-internal substitution path
    substitute,
    apply_projection,
    NO_MATCH,
)
from rcx_pi.selfhost.mu_type import is_mu


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Variable names: 1-8 alphanumeric chars, no underscore prefix (reserved)
var_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=8,
).filter(lambda k: not k.startswith("_") and len(k) > 0)

# Simple Mu values for bindings
mu_leaf = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.text(max_size=20),
)


@composite
def body_with_unbound_vars(draw):
    """Generate (body, bindings, unbound_names) where body has unbound vars.

    Strategy: generate a body containing var sites, then generate bindings
    that deliberately omit at least one variable name actually used in the body.
    """
    num_vars = draw(st.integers(min_value=1, max_value=4))
    all_var_names = draw(
        st.lists(var_names, min_size=num_vars, max_size=num_vars, unique=True)
    )

    # Build body with var references — track which names are actually used
    body_type = draw(st.sampled_from(["single_var", "dict_with_vars", "list_with_vars"]))

    if body_type == "single_var":
        body = {"var": all_var_names[0]}
        used_names = [all_var_names[0]]
    elif body_type == "dict_with_vars":
        body = {}
        for i, name in enumerate(all_var_names):
            body[f"key{i}"] = {"var": name}
        used_names = list(all_var_names)
    else:
        body = [{"var": name} for name in all_var_names]
        used_names = list(all_var_names)

    # Bindings: provide values for SOME used names, deliberately omit at least one
    num_bound = draw(st.integers(min_value=0, max_value=max(0, len(used_names) - 1)))
    bound_names = used_names[:num_bound]
    bindings = {}
    for name in bound_names:
        bindings[name] = draw(mu_leaf)

    unbound = set(used_names) - set(bindings)
    assume(len(unbound) > 0)

    return body, bindings, unbound


@composite
def body_fully_bound(draw):
    """Generate (body, bindings) where all vars are bound."""
    num_vars = draw(st.integers(min_value=1, max_value=4))
    all_var_names = draw(
        st.lists(var_names, min_size=num_vars, max_size=num_vars, unique=True)
    )

    body_type = draw(st.sampled_from(["single_var", "dict_with_vars", "list_with_vars"]))

    if body_type == "single_var":
        body = {"var": all_var_names[0]}
    elif body_type == "dict_with_vars":
        body = {}
        for i, name in enumerate(all_var_names):
            body[f"key{i}"] = {"var": name}
    else:
        body = [{"var": name} for name in all_var_names]

    bindings = {}
    for name in all_var_names:
        bindings[name] = draw(mu_leaf)

    return body, bindings


# ---------------------------------------------------------------------------
# Tests: _stage0_substitute (production kernel path)
# ---------------------------------------------------------------------------


class TestStage0UnboundVariable:
    """_stage0_substitute must raise KeyError on unbound variables (fail-closed)."""

    @given(data=body_with_unbound_vars())
    @settings(deadline=5000)
    def test_raises_on_unbound(self, data):
        """Unbound variable in body raises KeyError."""
        body, bindings, _unbound = data
        with pytest.raises(KeyError, match="Unbound variable"):
            _stage0_substitute(body, bindings)

    @given(data=body_fully_bound())
    @settings(deadline=5000)
    def test_succeeds_when_fully_bound(self, data):
        """All variables bound => substitution succeeds with valid Mu result."""
        body, bindings = data
        result = _stage0_substitute(body, bindings)
        assert is_mu(result), f"Result must be valid Mu, got {type(result)}"


# ---------------------------------------------------------------------------
# Tests: substitute (public boundary path)
# ---------------------------------------------------------------------------


class TestSubstituteUnboundVariable:
    """substitute() must also raise KeyError on unbound variables."""

    @given(data=body_with_unbound_vars())
    @settings(deadline=5000)
    def test_raises_on_unbound(self, data):
        """Boundary substitute also fails closed on unbound vars."""
        body, bindings, _unbound = data
        with pytest.raises(KeyError, match="Unbound variable"):
            substitute(body, bindings)


# ---------------------------------------------------------------------------
# Tests: apply_projection (end-to-end unbound detection)
# ---------------------------------------------------------------------------


class TestApplyProjectionUnboundVariable:
    """apply_projection propagates KeyError when body has unbound vars."""

    @given(var_name=var_names, literal=mu_leaf.filter(lambda x: x is not None))
    @settings(deadline=5000)
    def test_matching_pattern_unbound_body_raises(self, var_name, literal):
        """Projection: pattern matches (literal), body has unbound var => KeyError."""
        projection = {
            "pattern": literal,
            "body": {"var": var_name},
        }
        with pytest.raises(KeyError, match="Unbound variable"):
            apply_projection(projection, literal)

    @given(var_name=var_names, literal=mu_leaf.filter(lambda x: x is not None))
    @settings(deadline=5000)
    def test_non_matching_pattern_returns_no_match(self, var_name, literal):
        """Projection: pattern doesn't match => NO_MATCH (unbound var never reached)."""
        projection = {
            "pattern": "WILL_NOT_MATCH_SENTINEL_12345",
            "body": {"var": var_name},
        }
        result = apply_projection(projection, literal)
        assert result is NO_MATCH
