"""D009: H4 Structural Depth Threading — Research Artifact

RESEARCH ANALOG ONLY. This file demonstrates that stack_guard depth can be
expressed as Mu data (linked-list budget). It does NOT reduce or eliminate
stack_guard in production. Production mu_type.py / eval_seed.py are unchanged.

Tests H4 hypothesis: can stack_guard (MAX_MU_DEPTH) be expressed as Mu data
(linked-list depth budget) threaded through recursive traversal functions,
instead of compared against a hardcoded host integer constant?

Success criteria:
  C1: Research analogs (guarded_is_mu, guarded_match, guarded_substitute)
      produce correct results on 5+ canonical vectors.
  C2: Results identical to production functions on same inputs with
      budget = make_depth_budget(301) (parity with MAX_MU_DEPTH=300).
  C3: No new bootstrap primitive introduced.

Failure criteria (honest limitations):
  F1: Research analogs still use host isinstance for type dispatch.
  F2: make_depth_budget uses a host for-loop (construction is circular).
  F3: The if-budget-is-None check is a host operation (mechanism is host,
      only data is structural Mu).

Boundary lock criteria:
  B1: Off-by-one parity: _depth > MAX (strict >), not >=.
  B2: Failure mode parity: is_mu→False, match→NO_MATCH, substitute→TypeError.

Coverage: 3 primary enforcement surfaces (is_mu, match, substitute).
Stage 0 variants (_stage0_match, _stage0_substitute) use the identical depth
pattern and are not separately reimplemented — the primary 3 provide
sufficient G8 evidence.

Explicit non-goals for D009:
  - Memoization parity (production is_mu uses per-call memo; research analog omits it)
  - Cycle-detection parity (production is_mu uses _seen set with backtracking;
    research analog relies on budget exhaustion for termination on cyclic inputs)
  - JS cross-substrate analog
  - Production code changes of any kind
  If depth-threading is ever promoted to production, memoization, cycle-detection,
  and cross-substrate parity must be addressed in that future wave.

NOT production code. This file lives in tests/research/ and is never
imported by rcx_pi/.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D009)
               mu/docs/core/L4ExitChecklist.v0.md (G8, stack_guard)
"""

import ast
import inspect

import pytest

# Production functions — used ONLY for parity comparison, not as execution
# substrate for budget threading.
from rcx_pi.selfhost.eval_seed import (
    NO_MATCH,
    get_var_name,
    is_var,
    match,
    substitute,
)
from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH, is_mu, mu_hash_cached

from tests.repo_root import REPO_ROOT


# ---------------------------------------------------------------------------
# Structural depth budget: Mu linked-list (research-only)
# ---------------------------------------------------------------------------


def make_depth_budget(n):
    """Build a Mu linked-list of n nodes representing depth budget.

    Budget of n nodes allows n recursive levels (0 through n-1).
    For parity with production MAX_MU_DEPTH=300 (guard: _depth > 300),
    use make_depth_budget(301) to allow depths 0-300 (301 levels).

    NOTE: This function uses a Python for-loop to construct the budget.
    This is H4 failure criterion F2: budget construction itself requires
    a host loop. The circularity is real but bounded — construction is
    one-time setup, consumption is runtime.
    """
    budget = None  # empty = budget exhausted
    for _ in range(n):
        budget = {"head": None, "tail": budget}
    return budget


def depth_remaining(budget):
    """Count remaining budget nodes (for test assertions only)."""
    count = 0
    while budget is not None:
        count += 1
        budget = budget.get("tail") if isinstance(budget, dict) else None
    return count


def _consume(budget):
    """Pop one budget node, returning remaining tail. None if exhausted."""
    if budget is None:
        return None
    return budget.get("tail") if isinstance(budget, dict) else None


# ---------------------------------------------------------------------------
# Research analogs: depth-as-Mu-data versions of production functions
#
# KEY DESIGN: These are standalone reimplementations that mirror production
# logic but thread a Mu linked-list budget instead of integer _depth.
# Production functions are NOT called as execution substrate — they appear
# only in parity comparison tests (Class 2).
# ---------------------------------------------------------------------------


def guarded_is_mu(value, budget):
    """Research analog of is_mu() with Mu linked-list depth budget.

    Returns (bool, remaining_budget).
    On budget exhaustion: returns (False, None) — matches production
    is_mu() which returns False when _depth > MAX_MU_DEPTH.
    """
    if budget is None:
        return False, None

    if value is None:
        return True, budget
    if isinstance(value, bool):
        return True, budget
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (
            value != value or value == float("inf") or value == float("-inf")
        ):
            return False, budget
        return True, budget
    if isinstance(value, str):
        return True, budget

    remaining = _consume(budget)

    if type(value) is list:
        for item in value:
            ok, remaining = guarded_is_mu(item, remaining)
            if not ok:
                return False, remaining
        return True, remaining

    if type(value) is dict:
        if not all(type(k) is str for k in value.keys()):
            return False, remaining
        for v in value.values():
            ok, remaining = guarded_is_mu(v, remaining)
            if not ok:
                return False, remaining
        return True, remaining

    return False, budget


def guarded_match(pattern, input_value, budget):
    """Research analog of _match_inner() with Mu linked-list depth budget.

    Returns (bindings_dict | NO_MATCH, remaining_budget).
    On budget exhaustion: returns (NO_MATCH, None) — matches production
    _match_inner() which returns NO_MATCH when _depth > MAX_MU_DEPTH.
    """
    if budget is None:
        return NO_MATCH, None

    # Variable site
    if is_var(pattern):
        name = get_var_name(pattern)
        return {name: input_value}, budget

    # None
    if pattern is None:
        return ({} if input_value is None else NO_MATCH), budget

    # Bool (before int — bool is subclass of int)
    if isinstance(pattern, bool):
        if isinstance(input_value, bool) and pattern == input_value:
            return {}, budget
        return NO_MATCH, budget

    # Int
    if isinstance(pattern, int):
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            if pattern == input_value:
                return {}, budget
        return NO_MATCH, budget

    # Float
    if isinstance(pattern, float):
        if isinstance(input_value, float) and pattern == input_value:
            return {}, budget
        return NO_MATCH, budget

    # String
    if isinstance(pattern, str):
        if isinstance(input_value, str) and pattern == input_value:
            return {}, budget
        return NO_MATCH, budget

    remaining = _consume(budget)

    # List
    if isinstance(pattern, list):
        if not isinstance(input_value, list):
            return NO_MATCH, remaining
        if len(pattern) != len(input_value):
            return NO_MATCH, remaining
        bindings = {}
        for p_elem, i_elem in zip(pattern, input_value):
            sub_bindings, remaining = guarded_match(p_elem, i_elem, remaining)
            if sub_bindings is NO_MATCH:
                return NO_MATCH, remaining
            for k in sub_bindings:
                if k in bindings:
                    if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                        return NO_MATCH, remaining
            bindings = {**bindings, **sub_bindings}
        return bindings, remaining

    # Dict
    if isinstance(pattern, dict):
        if not isinstance(input_value, dict):
            return NO_MATCH, remaining
        pattern_keys = set(pattern.keys())
        input_keys = set(input_value.keys())
        if pattern_keys != input_keys:
            extra_is_type = input_keys - pattern_keys == {"_type"}
            no_pattern_extra = len(pattern_keys - input_keys) == 0
            type_is_list = input_value.get("_type") == "list"
            if not (extra_is_type and no_pattern_extra and type_is_list):
                return NO_MATCH, remaining
        bindings = {}
        for key in pattern:
            sub_bindings, remaining = guarded_match(
                pattern[key], input_value[key], remaining
            )
            if sub_bindings is NO_MATCH:
                return NO_MATCH, remaining
            for k in sub_bindings:
                if k in bindings:
                    if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                        return NO_MATCH, remaining
            bindings = {**bindings, **sub_bindings}
        return bindings, remaining

    return NO_MATCH, budget


def guarded_substitute(body, bindings, budget):
    """Research analog of substitute() with Mu linked-list depth budget.

    Returns substituted result.
    On budget exhaustion: raises TypeError — matches production
    substitute() which raises TypeError when _depth > MAX_MU_DEPTH.
    """
    if budget is None:
        raise TypeError(f"Max depth exceeded in guarded_substitute (budget exhausted)")

    # Variable site
    if is_var(body):
        name = get_var_name(body)
        if name not in bindings:
            raise KeyError(f"Unbound variable: {name}")
        return bindings[name]

    # Scalars
    if body is None or isinstance(body, (bool, int, float, str)):
        return body

    remaining = _consume(budget)

    # List
    if isinstance(body, list):
        return [guarded_substitute(elem, bindings, remaining) for elem in body]

    # Dict
    if isinstance(body, dict):
        return {k: guarded_substitute(v, bindings, remaining) for k, v in body.items()}

    raise TypeError(f"Invalid body type: {type(body)}")


# ---------------------------------------------------------------------------
# Test Vectors
# ---------------------------------------------------------------------------

# V1: Shallow dict — minimal valid Mu
V1_VALUE = {"a": 1, "b": "hello"}
V1_PATTERN = {"a": {"var": "x"}, "b": "hello"}
V1_EXPECTED_BINDINGS = {"x": 1}

# V2: 5-level nested dict
V2_VALUE = {"l1": {"l2": {"l3": {"l4": {"l5": "deep"}}}}}
V2_PATTERN = {"l1": {"l2": {"l3": {"l4": {"l5": {"var": "d"}}}}}}
V2_EXPECTED_BINDINGS = {"d": "deep"}

# V3: Boundary depth — used with exact-budget tests
def _make_nested(depth):
    """Build a depth-level nested dict {"k": {"k": ... {"k": "leaf"}}}."""
    result = "leaf"
    for _ in range(depth):
        result = {"k": result}
    return result

# V4: Substitute with 3-level body
V4_BODY = {"outer": {"inner": {"var": "x"}}}
V4_BINDINGS = {"x": 42}
V4_EXPECTED = {"outer": {"inner": 42}}

# V5: Real seed-like pattern (match + substitute cycle)
V5_PATTERN = {"status": {"var": "s"}, "data": {"var": "d"}}
V5_INPUT = {"status": "ready", "data": [1, 2, 3]}
V5_BODY = {"result": {"var": "d"}, "was": {"var": "s"}}
V5_EXPECTED_BINDINGS = {"s": "ready", "d": [1, 2, 3]}
V5_EXPECTED_SUBST = {"result": [1, 2, 3], "was": "ready"}


# ===========================================================================
# CLASS 1: SUCCESS CRITERIA
# ===========================================================================


class TestH4SuccessCriteria:
    """H4 success criteria: correct results on 5+ vectors."""

    def test_v1_shallow_dict(self):
        """V1: Shallow dict — is_mu true, match succeeds."""
        budget = make_depth_budget(10)
        ok, _ = guarded_is_mu(V1_VALUE, budget)
        assert ok

        budget = make_depth_budget(10)
        bindings, _ = guarded_match(V1_PATTERN, V1_VALUE, budget)
        assert bindings == V1_EXPECTED_BINDINGS

    def test_v2_nested_dict(self):
        """V2: 5-level nested dict — is_mu true, match succeeds."""
        budget = make_depth_budget(10)
        ok, _ = guarded_is_mu(V2_VALUE, budget)
        assert ok

        budget = make_depth_budget(10)
        bindings, _ = guarded_match(V2_PATTERN, V2_VALUE, budget)
        assert bindings == V2_EXPECTED_BINDINGS

    def test_v3_boundary_depth(self):
        """V3: Dict at exactly budget depth — pass at depth, fail at depth-1."""
        nested = _make_nested(5)  # 5 levels deep
        # Budget of 6 allows depths 0-5 (6 levels) — should pass
        budget = make_depth_budget(6)
        ok, _ = guarded_is_mu(nested, budget)
        assert ok, "Should pass with sufficient budget"

        # Budget of 5 allows depths 0-4 (5 levels) — should fail at level 5
        budget = make_depth_budget(5)
        ok, _ = guarded_is_mu(nested, budget)
        assert not ok, "Should fail with insufficient budget"

    def test_v4_substitute(self):
        """V4: Substitute with 3-level body produces correct result."""
        budget = make_depth_budget(10)
        result = guarded_substitute(V4_BODY, V4_BINDINGS, budget)
        assert result == V4_EXPECTED

    def test_v5_match_substitute_cycle(self):
        """V5: Match + substitute cycle on seed-like pattern."""
        budget = make_depth_budget(10)
        bindings, _ = guarded_match(V5_PATTERN, V5_INPUT, budget)
        assert bindings == V5_EXPECTED_BINDINGS

        budget = make_depth_budget(10)
        result = guarded_substitute(V5_BODY, bindings, budget)
        assert result == V5_EXPECTED_SUBST


# ===========================================================================
# CLASS 2: PARITY WITH PRODUCTION
# ===========================================================================


class TestH4ParityWithProduction:
    """H4 criterion 2: results identical to production functions."""

    @pytest.mark.parametrize(
        "value, label",
        [
            (V1_VALUE, "v1_shallow"),
            (V2_VALUE, "v2_nested"),
            (_make_nested(10), "v3_10level"),
            ([1, "two", [3, {"four": 4}]], "mixed_list"),
        ],
    )
    def test_is_mu_parity(self, value, label):
        """guarded_is_mu with budget=301 matches production is_mu."""
        budget = make_depth_budget(301)
        guarded_result, _ = guarded_is_mu(value, budget)
        prod_result = is_mu(value)
        assert guarded_result == prod_result, (
            f"is_mu parity failure on {label}: "
            f"guarded={guarded_result}, production={prod_result}"
        )

    @pytest.mark.parametrize(
        "pattern, input_val, label",
        [
            (V1_PATTERN, V1_VALUE, "v1_shallow"),
            (V2_PATTERN, V2_VALUE, "v2_nested"),
            (V5_PATTERN, V5_INPUT, "v5_seed_like"),
            ({"key": "nomatch"}, {"key": "different"}, "literal_fail"),
        ],
    )
    def test_match_parity(self, pattern, input_val, label):
        """guarded_match with budget=301 matches production match."""
        budget = make_depth_budget(301)
        guarded_result, _ = guarded_match(pattern, input_val, budget)
        prod_result = match(pattern, input_val)
        assert guarded_result == prod_result, (
            f"match parity failure on {label}: "
            f"guarded={guarded_result}, production={prod_result}"
        )

    @pytest.mark.parametrize(
        "body, bindings, label",
        [
            (V4_BODY, V4_BINDINGS, "v4_nested_body"),
            (V5_BODY, V5_EXPECTED_BINDINGS, "v5_seed_like"),
            ("literal", {}, "scalar_passthrough"),
            ([{"var": "a"}, 2], {"a": 99}, "list_body"),
        ],
    )
    def test_substitute_parity(self, body, bindings, label):
        """guarded_substitute with budget=301 matches production substitute."""
        budget = make_depth_budget(301)
        guarded_result = guarded_substitute(body, bindings, budget)
        prod_result = substitute(body, bindings)
        assert guarded_result == prod_result, (
            f"substitute parity failure on {label}: "
            f"guarded={guarded_result}, production={prod_result}"
        )


# ===========================================================================
# CLASS 3: BOUNDARY LOCK (acceptance-critical)
# ===========================================================================


class TestH4BoundaryLock:
    """Off-by-one parity and failure mode parity — required for evidence quality."""

    # --- Off-by-one: _depth > MAX (strict >), not >= ---

    def test_off_by_one_is_mu(self):
        """Structure at depth 300 with budget 301 passes; budget 300 fails.

        Production: _depth starts 0, guard is _depth > 300. Depth 300 valid.
        Research: budget 301 allows 301 levels (0-300). Budget 300 allows 300
        levels (0-299), so depth 300 fails.
        """
        nested = _make_nested(300)  # 300 dict levels wrapping "leaf"

        # Budget 301 = 301 levels (0-300): depth 300 should PASS
        budget = make_depth_budget(301)
        ok, _ = guarded_is_mu(nested, budget)
        assert ok, "Depth 300 with budget 301 must pass (parity with _depth > 300)"

        # Budget 300 = 300 levels (0-299): depth 300 should FAIL
        budget = make_depth_budget(300)
        ok, _ = guarded_is_mu(nested, budget)
        assert not ok, "Depth 300 with budget 300 must fail (off-by-one parity)"

    def test_off_by_one_match(self):
        """Pattern match at depth 300 with budget 301 succeeds; budget 300 fails."""
        nested_pattern = _make_nested(300)
        nested_input = _make_nested(300)

        budget = make_depth_budget(301)
        result, _ = guarded_match(nested_pattern, nested_input, budget)
        assert result is not NO_MATCH, "Match at depth 300 with budget 301 must succeed"

        budget = make_depth_budget(300)
        result, _ = guarded_match(nested_pattern, nested_input, budget)
        assert result is NO_MATCH, "Match at depth 300 with budget 300 must fail"

    def test_off_by_one_substitute(self):
        """Substitute at depth 300 with budget 301 succeeds; budget 300 raises."""
        # Build a 300-level nested body with no variables (passthrough)
        nested_body = _make_nested(300)

        budget = make_depth_budget(301)
        result = guarded_substitute(nested_body, {}, budget)
        assert result == nested_body, "Substitute at depth 300 with budget 301 must succeed"

        budget = make_depth_budget(300)
        with pytest.raises(TypeError):
            guarded_substitute(nested_body, {}, budget)

    # --- Failure mode parity ---

    def test_failure_mode_is_mu(self):
        """Budget exhaustion in guarded_is_mu returns False (not exception)."""
        nested = _make_nested(5)
        budget = make_depth_budget(2)  # Too shallow
        ok, _ = guarded_is_mu(nested, budget)
        assert ok is False, "guarded_is_mu must return False on budget exhaustion"

    def test_failure_mode_match(self):
        """Budget exhaustion in guarded_match returns NO_MATCH (not exception)."""
        nested_pattern = _make_nested(5)
        nested_input = _make_nested(5)
        budget = make_depth_budget(2)  # Too shallow
        result, _ = guarded_match(nested_pattern, nested_input, budget)
        assert result is NO_MATCH, "guarded_match must return NO_MATCH on budget exhaustion"

    def test_failure_mode_substitute(self):
        """Budget exhaustion in guarded_substitute raises TypeError."""
        nested_body = _make_nested(5)
        budget = make_depth_budget(2)  # Too shallow
        with pytest.raises(TypeError, match="budget exhausted"):
            guarded_substitute(nested_body, {}, budget)


# ===========================================================================
# CLASS 4: NO PRIMITIVE INCREASE
# ===========================================================================


class TestH4NoPrimitiveIncrease:
    """No new bootstrap primitives introduced by D009."""

    def test_no_bootstrap_primitive_markers_in_research(self):
        """This research artifact must not introduce BOOTSTRAP_PRIMITIVE markers."""
        source_path = __file__
        with open(source_path) as f:
            content = f.read()
        # Check only the code BEFORE this test (avoid self-reference)
        before_test = content.split("test_no_bootstrap_primitive_markers_in_research")[0]
        assert "BOOTSTRAP_PRIMITIVE" not in before_test, (
            "Research artifact must not introduce new BOOTSTRAP_PRIMITIVE markers"
        )

    def test_python_bootstrap_primitive_count(self):
        """Exactly 4 BOOTSTRAP_PRIMITIVE markers in rcx_pi/selfhost/."""
        selfhost_dir = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
        count = 0
        for py_file in selfhost_dir.glob("*.py"):
            count += py_file.read_text().count("BOOTSTRAP_PRIMITIVE")
        assert count == 4, (
            f"Expected 4 BOOTSTRAP_PRIMITIVE markers in selfhost/, found {count}"
        )

    def test_js_bootstrap_primitive_count(self):
        """JS BOOTSTRAP_PRIMITIVE marker count is exactly 7."""
        js_dir = REPO_ROOT / "mu" / "host" / "js"
        content = "\n".join(f.read_text() for f in sorted(js_dir.rglob("*.js")))
        count = content.count("BOOTSTRAP_PRIMITIVE")
        assert count == 7, (
            f"Expected 7 BOOTSTRAP_PRIMITIVE markers in JS modules, found {count}"
        )

    def test_total_bootstrap_primitive_count(self):
        """Total BOOTSTRAP_PRIMITIVE markers across both substrates is exactly 11."""
        selfhost_dir = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
        py_count = 0
        for py_file in selfhost_dir.glob("*.py"):
            py_count += py_file.read_text().count("BOOTSTRAP_PRIMITIVE")

        js_dir = REPO_ROOT / "mu" / "host" / "js"
        js_content = "\n".join(f.read_text() for f in sorted(js_dir.rglob("*.js")))
        js_count = js_content.count("BOOTSTRAP_PRIMITIVE")

        total = py_count + js_count
        assert total == 11, (
            f"Expected 11 total BOOTSTRAP_PRIMITIVE markers (Py:4 + JS:7), "
            f"found {total} (Py:{py_count} + JS:{js_count})"
        )


# ===========================================================================
# CLASS 5: FAILURE CRITERIA (honest limitations)
# ===========================================================================


class TestH4FailureCriteria:
    """H4 failure criteria — documenting honestly what depth threading cannot achieve."""

    def test_f1_research_analogs_use_isinstance(self):
        """F1: guarded_match/guarded_substitute use host isinstance for type dispatch.

        AST-verify that isinstance appears in all three research analogs.
        This is isomorphic to production — type dispatch remains host code.
        """
        for func in [guarded_is_mu, guarded_match, guarded_substitute]:
            source = inspect.getsource(func)
            tree = ast.parse(source)
            has_isinstance = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "isinstance"
                for node in ast.walk(tree)
            )
            assert has_isinstance, (
                f"{func.__name__} should use isinstance "
                f"(documenting F1: type dispatch remains host code)"
            )

    def test_f2_budget_construction_requires_host_loop(self):
        """F2: make_depth_budget uses a host for-loop — construction is circular."""
        source = inspect.getsource(make_depth_budget)
        tree = ast.parse(source)
        has_for = any(isinstance(node, ast.For) for node in ast.walk(tree))
        assert has_for, (
            "make_depth_budget should use a for-loop (documenting F2: "
            "budget construction requires host iteration)"
        )

    def test_f3_budget_check_is_host_operation(self):
        """F3: budget exhaustion check (if budget is None) is a host operation.

        The mechanism checking depth remains host code — only the data
        (budget linked-list) is structural Mu. AST-verify that all three
        research analogs compare budget against None.
        """
        for func in [guarded_is_mu, guarded_match, guarded_substitute]:
            source = inspect.getsource(func)
            tree = ast.parse(source)
            has_none_check = any(
                isinstance(node, ast.Compare)
                and any(
                    isinstance(comp, ast.Constant) and comp.value is None
                    for comp in node.comparators
                )
                for node in ast.walk(tree)
            )
            assert has_none_check, (
                f"{func.__name__} should check budget against None "
                f"(documenting F3: mechanism is host, data is Mu)"
            )


# ===========================================================================
# CLASS 6: STRUCTURAL PROPERTIES
# ===========================================================================


class TestH4StructuralProperties:
    """Verify structural properties of depth budget threading."""

    def test_budget_is_valid_mu(self):
        """Depth budget linked-list must be valid Mu data."""
        budget = make_depth_budget(5)
        assert is_mu(budget), "Depth budget must be valid Mu"
        assert is_mu(None), "Empty budget (None) must be valid Mu"

    def test_budget_consumption_is_monotonic(self):
        """Each recursive level consumes exactly one budget node."""
        budget = make_depth_budget(5)
        remaining_counts = [depth_remaining(budget)]

        # Manually consume budget nodes
        current = budget
        for _ in range(5):
            current = _consume(current)
            remaining_counts.append(depth_remaining(current))

        # Each step decreases budget by exactly 1
        for i in range(1, len(remaining_counts)):
            assert remaining_counts[i] == remaining_counts[i - 1] - 1, (
                f"Budget not monotonically decreasing: {remaining_counts}"
            )
        assert remaining_counts[-1] == 0, "Should reach zero after consuming all nodes"

    def test_zero_budget_immediate_guard(self):
        """Zero budget must immediately trigger guard (same as _depth > MAX)."""
        # is_mu: returns False
        ok, _ = guarded_is_mu({"a": 1}, None)
        assert ok is False, "Zero budget must return False for compound Mu"

        # match: returns NO_MATCH
        result, _ = guarded_match({"a": {"var": "x"}}, {"a": 1}, None)
        assert result is NO_MATCH, "Zero budget must return NO_MATCH"

        # substitute: raises TypeError
        with pytest.raises(TypeError):
            guarded_substitute({"a": {"var": "x"}}, {"x": 1}, None)

    def test_budget_does_not_leak_into_bindings(self):
        """Budget nodes must not appear in match bindings or substitute output."""
        budget = make_depth_budget(10)
        bindings, _ = guarded_match(V5_PATTERN, V5_INPUT, budget)
        assert bindings is not NO_MATCH
        # Check no binding value contains budget structure
        for k, v in bindings.items():
            assert not (isinstance(v, dict) and set(v.keys()) == {"head", "tail"}), (
                f"Budget leaked into binding '{k}': {v}"
            )

        budget = make_depth_budget(10)
        result = guarded_substitute(V5_BODY, bindings, budget)
        # Result should be the expected substitution, not budget-contaminated

        def _contains_budget_shape(val):
            if isinstance(val, dict) and set(val.keys()) == {"head", "tail"}:
                return True
            if isinstance(val, dict):
                return any(_contains_budget_shape(v) for v in val.values())
            if isinstance(val, list):
                return any(_contains_budget_shape(v) for v in val)
            return False

        assert not _contains_budget_shape(result), (
            f"Budget leaked into substitute output: {result}"
        )

    def test_budget_nodes_minimal_keys(self):
        """Budget nodes contain only {head, tail} — no domain-specific keys."""
        budget = make_depth_budget(3)
        current = budget
        while current is not None:
            assert isinstance(current, dict)
            assert set(current.keys()) == {"head", "tail"}, (
                f"Budget node has unexpected keys: {set(current.keys())}"
            )
            current = current.get("tail")

    def test_cyclic_input_fails_closed(self):
        """Cyclic Python object must fail-closed quickly, not hang.

        Research analogs omit cycle-detection (_seen set) — this is an
        explicit D009 non-goal. Budget exhaustion serves as the termination
        bound: a cyclic reference recurses until budget is None, then
        returns False. This test verifies fail-closed behavior (no hang,
        no stack overflow) with a small budget.
        """
        import time

        cyclic = {}
        cyclic["self"] = cyclic  # True Python cycle

        budget = make_depth_budget(10)
        start = time.monotonic()
        ok, _ = guarded_is_mu(cyclic, budget)
        elapsed = time.monotonic() - start

        assert ok is False, "Cyclic input must return False (fail-closed)"
        assert elapsed < 1.0, (
            f"Cyclic input took {elapsed:.2f}s — budget should terminate instantly"
        )

    def test_research_functions_loc(self):
        """Research functions must be ≤150 LOC total (stop condition).

        Target was 120 LOC; actual is ~145 LOC. This is evidence that depth
        threading (intra-recursive reimplementation of is_mu + match +
        substitute) is ~3x more complex than fuel threading (D006: ~50 LOC
        for outer-loop wrapper fuel_step + fuel_run). The extra complexity
        comes from reimplementing type dispatch and recursive traversal
        for all Mu types, vs D006 which called step_mu unchanged.
        """
        total = 0
        for func in [make_depth_budget, depth_remaining, _consume,
                      guarded_is_mu, guarded_match, guarded_substitute]:
            lines = [
                line for line in inspect.getsource(func).splitlines()
                if line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith('"""')
                and not line.strip().startswith("'")
            ]
            total += len(lines)
        assert total <= 150, (
            f"Research functions total {total} LOC (stop condition: 150)"
        )
