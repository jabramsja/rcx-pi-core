"""
EVAL_SEED v0 - Foundational Seed for RCX

This module implements the core operations needed to evaluate projections:
1. match(pattern, input) - structural pattern matching
2. substitute(body, bindings) - variable substitution
3. apply(projection, input) - match + substitute
4. step(projections, input) - select and apply first matching projection

The only special form is {"var": "<name>"} which matches anything and binds.

See mu/docs/core/EVAL_SEED.v0.md for specification.
"""

from __future__ import annotations

from .mu_type import Mu, assert_mu, mark_bootstrap, mu_hash_cached, MAX_MU_DEPTH, consume_budget, _NO_BUDGET


# _is_kernel_internal_state and its supporting constants (_VALID_MU_TYPES,
# _KNOWN_KERNEL_MODES, _KERNEL_CONTEXT_KEYS) were removed from production code.
# Zero production callers after caller-trust model replaced shape-based trust.
# The function is preserved in tests/structural/test_type_tag_security.py as a
# local fixture for regression testing the 3-layer check logic.


# =============================================================================
# HOST DEBT TRACKING
# =============================================================================
#
# NORTH STAR: See mu/docs/core/Why_RCX_PI_VM_EXISTS.md
# Host languages (Python, JavaScript) are bootstrap scaffolding, NOT the
# semantic destination. Every host operation marked below is tracked debt
# that must eventually be replaced by structural Mu projections. We program
# IN RCX, not ABOUT RCX. Meaning lives in projections (data), not host (code).
#
# Functions marked with @host_recursion, @host_iteration, or @host_builtin
# are using Python's call stack / loops / builtins instead of RCX kernel
# structural operations. This is TEMPORARY scaffolding.
#
# Each host debt site MUST:
# 1. Document WHY it exists
# 2. Have a projection-based equivalent planned
# 3. Be eliminated before self-hosting is complete
#
# Canonical counts: tools/checks/host_semantics_baseline.json
# Ratchet enforcer: tools/checks/check_host_semantics_ratchet.py
# =============================================================================


def _apply_host_debt(func, category: str, reason: str):
    """Shared implementation for all host-debt decorators.

    Sets _host_{category} and _host_{category}_reason attributes, then
    registers with mark_bootstrap. Each public decorator preserves its
    own name for grep-based audit counting (audit_semantic_purity.sh,
    debt_dashboard.sh, check_js_debt.sh).
    """
    setattr(func, f"_host_{category}", True)  # CONTRABAND_OK: decorator metadata for debt tracking
    setattr(func, f"_host_{category}_reason", reason)  # CONTRABAND_OK: decorator metadata for debt tracking
    mark_bootstrap(f"host_{category}:{func.__name__}", f"Host {category}: {reason}")
    return func


def host_recursion(reason: str):
    """Mark a function as using host recursion (Python call stack).

    Debt marker. The function works, but computation should eventually
    be done by RCX kernel iteration.

    Usage::

        >>> @host_recursion("reason why recursion exists")  # noqa: debt-example
        ... def my_function(args):
        ...     pass
    """
    def decorator(func):
        return _apply_host_debt(func, "recursion", reason)
    return decorator


def host_builtin(reason: str):
    """Mark code as using host builtins (len, sorted, sum, max, min, etc.).

    Debt marker. These operations should be structural in pure RCX.
    """
    def decorator(func):
        return _apply_host_debt(func, "builtin", reason)
    return decorator


def host_mutation(reason: str):
    """Mark code as using host mutation (.append, .pop, del, []=).

    Debt marker. RCX is immutable - each step produces new structure.
    """
    def decorator(func):
        return _apply_host_debt(func, "mutation", reason)
    return decorator


def host_iteration(reason: str):
    """Mark code as using host iteration (Python for-loops).

    Debt marker. The kernel loop should be structural projections,
    not Python iteration.
    """
    def decorator(func):
        return _apply_host_debt(func, "iteration", reason)
    return decorator


# =============================================================================
# NOT Lambda Calculus Guardrails
# =============================================================================
#
# EVAL_SEED implements STRUCTURAL pattern matching, NOT lambda calculus.
# Key differences:
# - {"var": "x"} is a HOLE MARKER, not a λ-binder
# - Variables bind VALUES, not functions/projections
# - No closures, no scopes, no self-application
# - Substitution is immediate (no delayed evaluation)
#
# If you can write the Y-combinator, this module has failed.
# =============================================================================
#
# BOOTSTRAP: assert_not_lambda_calculus
# --------------------------------------
# This runtime guardrail provides defense-in-depth against lambda calculus
# smuggling. It uses host recursion (ironic), but the test suite also covers
# these cases. Kept for belt-and-suspenders security at API boundary.
# =============================================================================


def assert_not_lambda_calculus(projection: "Mu") -> None:
    """
    Verify a projection doesn't smuggle in lambda calculus semantics.

    Checks:
    1. Body doesn't contain projection-like structures with free variables
       (which would create closure-like behavior)
    2. Pattern doesn't try to match projections (no higher-order matching)

    This is a design guardrail, not a complete static analysis.
    """
    if not isinstance(projection, dict):
        return

    if "pattern" not in projection or "body" not in projection:
        return

    pattern = projection["pattern"]
    body = projection["body"]

    # Collect variable names bound by the enclosing pattern. These will be
    # substituted away at evaluation time and do NOT create closure-like behavior.
    def _collect_pattern_vars(mu: "Mu", out: set, _depth: int = 0) -> None:
        if _depth > MAX_MU_DEPTH:
            return
        if is_var(mu):
            out.add(mu["var"])
            return
        if isinstance(mu, dict):
            for v in mu.values():
                _collect_pattern_vars(v, out, _depth + 1)
        elif isinstance(mu, list):
            for v in mu:
                _collect_pattern_vars(v, out, _depth + 1)

    bound_vars: set[str] = set()
    _collect_pattern_vars(pattern, bound_vars)

    # Check: pattern and body should not contain projection structures
    # (no higher-order pattern matching, no closure-like body smuggling)
    def _contains_free_var(mu: "Mu", _depth: int = 0) -> bool:
        """Check if mu contains a variable reference NOT bound by the enclosing pattern.

        Free vars in nested projection-shaped structures indicate closure-like
        behavior (they'd need runtime lookup, not substitution).
        Vars from the enclosing pattern are substituted away → inert output.
        """
        if _depth > MAX_MU_DEPTH:
            return False
        if is_var(mu):
            return mu["var"] not in bound_vars
        if isinstance(mu, dict):
            return any(_contains_free_var(v, _depth + 1) for v in mu.values())
        if isinstance(mu, list):
            return any(_contains_free_var(v, _depth + 1) for v in mu)
        return False

    def contains_projection_pattern(mu: "Mu", _depth: int = 0, *, check_vars: bool = False) -> bool:
        """Check if mu contains a projection-like structure.

        When check_vars=True (body check), only flags structures that contain
        FREE variable references (not bound by enclosing pattern) — inert
        projection-shaped output from substitution is allowed.
        """
        if _depth > MAX_MU_DEPTH:
            return False  # Bounded by assert_mu at caller; stop recursion
        if isinstance(mu, dict):
            # A structure with {"pattern": ..., "body": ...} is suspicious
            if "pattern" in mu and "body" in mu:
                if check_vars:
                    # Body check: only flag if nested structure has FREE variables
                    # (not bound by enclosing pattern — closure-like behavior).
                    # Vars from the enclosing pattern will be substituted → inert data.
                    # The "both vars" exception doesn't apply here because even
                    # {pattern: {var: free_x}, body: {var: free_y}} is closure-like
                    # if free_x/free_y aren't bound by the enclosing pattern.
                    if _contains_free_var(mu):
                        return True
                else:
                    # Pattern check: any projection shape is suspicious UNLESS
                    # both fields are vars (just matching any dict with those keys)
                    if not (is_var(mu.get("pattern")) and is_var(mu.get("body"))):
                        return True
            return any(contains_projection_pattern(v, _depth + 1, check_vars=check_vars) for v in mu.values())
        if isinstance(mu, list):
            return any(contains_projection_pattern(v, _depth + 1, check_vars=check_vars) for v in mu)
        return False

    if contains_projection_pattern(pattern):
        raise ValueError(
            "Projection pattern appears to match projection structures "
            "(higher-order patterns not allowed - this looks like lambda calculus)"
        )

    if contains_projection_pattern(body, check_vars=True):
        raise ValueError(
            "Projection body contains projection-like structures with free variables "
            "(closure-like behavior not allowed - this looks like lambda calculus)"
        )


# Sentinel for no match (not a valid Mu, so unambiguous)
class _NoMatch:
    """Sentinel indicating pattern did not match."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_MATCH"


NO_MATCH = _NoMatch()


# =============================================================================
# Core Operations
# =============================================================================


def is_var(mu: Mu) -> bool:
    """Check if mu is a variable site {"var": "<name>"}."""
    return (
        isinstance(mu, dict)
        and len(mu) == 1
        and "var" in mu
        and isinstance(mu["var"], str)
    )


def get_var_name(mu: Mu) -> str:
    """Extract variable name from {"var": "<name>"}.

    Raises:
        ValueError: If not a variable site or if variable name is empty.
    """
    if not is_var(mu):
        raise ValueError(f"Not a variable site: {mu}")
    name = mu["var"]
    if not name:
        raise ValueError("Variable name cannot be empty: {'var': ''}")
    return name


@host_recursion(
    "Recursive tree traversal for pattern matching. "
    "BOOTSTRAP PRIMITIVE: eval_step() calls this to apply ANY projection. "
    "match_mu.py expresses the ALGORITHM as projections; this function EXECUTES them."
)
@host_builtin(
    "len() for size, zip() for pairing, set() for key comparison, "
    "any() for aggregation, 'in' for membership, .items()/.keys() for iteration"
)
def match(pattern: Mu, input_value: Mu) -> dict[str, Mu] | _NoMatch:
    """
    Match pattern against input, returning bindings or NO_MATCH.

    Rules:
    - {"var": "x"} matches anything, binds to x
    - Literals match if equal (null, bool, int, float, str)
    - Lists match if same length and all elements match
    - Dicts match if same keys and all values match

    Args:
        pattern: The pattern to match (Mu with possible var sites).
        input_value: The value to match against (Mu).

    Returns:
        Dict of bindings {"var_name": value} if match, NO_MATCH otherwise.
    """
    # Guardrails — validate once at entry, not on every recursive call.
    # _match_inner recurses without re-validating (safe: sub-elements of
    # valid Mu are themselves valid Mu).
    assert_mu(pattern, "match.pattern")
    assert_mu(input_value, "match.input")

    # Gate 3: Auto-normalize input when pattern uses normalized dict format.
    # Normalization is idempotent, so already-normalized input is unchanged.
    # This allows normalized algorithm seeds to work with raw dict input.
    if isinstance(pattern, dict) and pattern.get("_type") == "dict":
        from rcx_pi.selfhost.match_mu import normalize_for_match
        input_value = normalize_for_match(input_value)

    return _match_inner(pattern, input_value, 0)


def _match_inner(pattern: Mu, input_value: Mu, _depth: int = 0,
                 _budget: object = _NO_BUDGET) -> dict[str, Mu] | _NoMatch:
    """Internal recursive matcher — no validation (already done at match() entry).

    This function contains 13 isinstance calls for Python type dispatch
    (plus 1 in match() = 14 isinstance calls total). These are NOT 14
    separate debt markers — they are all covered by the single host_builtin
    decorator on match(). Callers: match() (public entry) and
    _apply_projection_trusted() (kernel-internal fast path).

    When _budget is provided, uses structural Mu linked-list budget instead
    of integer _depth for depth limiting. Same semantics (depth-only: same
    remaining budget passed to all siblings at a given level).
    """
    # --- Structural budget path (opt-in) ---
    if _budget is not _NO_BUDGET:
        ok, remaining = consume_budget(_budget)
        if not ok:
            return NO_MATCH

        if is_var(pattern):
            var_name = pattern["var"]
            if not var_name:
                return NO_MATCH
            return {var_name: input_value}

        if pattern is None:
            return {} if input_value is None else NO_MATCH

        if isinstance(pattern, bool):
            if isinstance(input_value, bool) and pattern == input_value:
                return {}
            return NO_MATCH

        if isinstance(pattern, int):
            if isinstance(input_value, int) and not isinstance(input_value, bool):
                if pattern == input_value:
                    return {}
            return NO_MATCH

        if isinstance(pattern, float):
            if isinstance(input_value, float) and pattern == input_value:
                return {}
            return NO_MATCH

        if isinstance(pattern, str):
            if isinstance(input_value, str) and pattern == input_value:
                return {}
            return NO_MATCH

        if isinstance(pattern, list):
            if not isinstance(input_value, list):
                return NO_MATCH
            if len(pattern) != len(input_value):
                return NO_MATCH
            bindings: dict[str, Mu] = {}
            for p_elem, i_elem in zip(pattern, input_value):
                # Depth-only: same 'remaining' to all siblings
                sub_bindings = _match_inner(p_elem, i_elem, _depth, _budget=remaining)
                if sub_bindings is NO_MATCH:
                    return NO_MATCH
                for k in sub_bindings:
                    if k in bindings:
                        if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                            return NO_MATCH
                bindings = {**bindings, **sub_bindings}
            return bindings

        if isinstance(pattern, dict):
            if not isinstance(input_value, dict):
                return NO_MATCH
            pattern_keys = set(pattern.keys())
            input_keys = set(input_value.keys())
            if pattern_keys != input_keys:
                extra_is_type = (input_keys - pattern_keys == {"_type"})
                no_pattern_extra = (len(pattern_keys - input_keys) == 0)
                type_is_list = (input_value.get("_type") == "list")
                if not (extra_is_type and no_pattern_extra and type_is_list):
                    return NO_MATCH
            bindings = {}
            for key in pattern:
                sub_bindings = _match_inner(pattern[key], input_value[key], _depth, _budget=remaining)
                if sub_bindings is NO_MATCH:
                    return NO_MATCH
                for k in sub_bindings:
                    if k in bindings:
                        if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                            return NO_MATCH
                bindings = {**bindings, **sub_bindings}
            return bindings

        return NO_MATCH

    # --- Integer depth path (default — existing behavior, zero overhead) ---
    if _depth > MAX_MU_DEPTH:
        return NO_MATCH

    # Variable site - matches anything
    if is_var(pattern):
        var_name = pattern["var"]
        if not var_name:
            return NO_MATCH
        return {var_name: input_value}

    # None
    if pattern is None:
        return {} if input_value is None else NO_MATCH

    # Bool (must check before int because bool is subclass of int in Python)
    if isinstance(pattern, bool):
        if isinstance(input_value, bool) and pattern == input_value:
            return {}
        return NO_MATCH

    # Int
    if isinstance(pattern, int):
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            if pattern == input_value:
                return {}
        return NO_MATCH

    # Float
    if isinstance(pattern, float):
        if isinstance(input_value, float) and pattern == input_value:
            return {}
        return NO_MATCH

    # String
    if isinstance(pattern, str):
        if isinstance(input_value, str) and pattern == input_value:
            return {}
        return NO_MATCH

    # List
    if isinstance(pattern, list):
        if not isinstance(input_value, list):
            return NO_MATCH
        if len(pattern) != len(input_value):
            return NO_MATCH
        bindings: dict[str, Mu] = {}
        for p_elem, i_elem in zip(pattern, input_value):
            sub_bindings = _match_inner(p_elem, i_elem, _depth + 1)
            if sub_bindings is NO_MATCH:
                return NO_MATCH
            # Non-linear conflict check (same variable, different value)
            # Use mu_hash_cached (NOT mu_hash_control_cached) — control hash
            # canonicalizes 0.0→0 which breaks int/float type distinction.
            for k in sub_bindings:
                if k in bindings:
                    if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                        return NO_MATCH
            bindings = {**bindings, **sub_bindings}  # pure merge, no dict mutation
        return bindings

    # Dict
    if isinstance(pattern, dict):
        if not isinstance(input_value, dict):
            return NO_MATCH
        # Gate 3: Allow pattern to omit _type key while input has it.
        # This lets patterns use bare {head, tail} to match normalized lists
        # which have {head, tail, _type: "list"}.
        # IMPORTANT: Only allow for _type="list" - dicts require explicit _type in pattern.
        pattern_keys = set(pattern.keys())
        input_keys = set(input_value.keys())
        if pattern_keys != input_keys:
            # Check if the only difference is _type in input but not pattern
            extra_is_type = (input_keys - pattern_keys == {"_type"})
            no_pattern_extra = (len(pattern_keys - input_keys) == 0)
            type_is_list = (input_value.get("_type") == "list")
            if not (extra_is_type and no_pattern_extra and type_is_list):
                return NO_MATCH
        bindings = {}
        for key in pattern:
            sub_bindings = _match_inner(pattern[key], input_value[key], _depth + 1)
            if sub_bindings is NO_MATCH:
                return NO_MATCH
            # Non-linear conflict check (same variable, different value)
            # Use mu_hash_cached (NOT mu_hash_control_cached) — control hash
            # canonicalizes 0.0→0 which breaks int/float type distinction.
            for k in sub_bindings:
                if k in bindings:
                    if mu_hash_cached(bindings[k]) != mu_hash_cached(sub_bindings[k]):
                        return NO_MATCH
            bindings = {**bindings, **sub_bindings}  # pure merge, no dict mutation
        return bindings

    # Should not reach here if input is valid Mu
    return NO_MATCH


# ---------------------------------------------------------------------------
# Stage 0 micro-kernel (D005 production)
# Accumulator-style match + recursive substitute. Parallel path to _match_inner/substitute.
# Proves circular dependency is breakable. See L4DecisionCard.v0.md D005.
# Host debt: same surface as match()/substitute() — isinstance dispatch, Python call stack,
#   .append() mutation in _stage0_substitute. Markers added Wave H (2026-03-11).
# ---------------------------------------------------------------------------

# Stage0 production flag. When True, _apply_projection_trusted routes through
# _stage0_match/_stage0_substitute instead of _match_inner/substitute.
# Flipped to True in Wave H (2026-03-11) after 90 gate tests proving ON/OFF parity.
_STAGE0_PILOT = True


@host_recursion(
    "Stage 0 micro-match: isinstance dispatch + recursive dict/list traversal. "
    "BOOTSTRAP PRIMITIVE: breaks circular dependency (kernel → match → kernel). "
    "Same host surface as _match_inner but ~52 LOC accumulator-style."
)
@host_builtin(
    "isinstance, len, zip, set, .keys(), .get(), 'in' — same host-builtin surface as match(). "
    "Production path (_STAGE0_PILOT=True). Tracked separately from match() for ratchet accuracy."
)
def _stage0_match(pattern, input_value, bindings=None, _depth=0):
    """Stage 0 match: accumulator-style bindings. Returns NO_MATCH on failure."""
    if _depth > MAX_MU_DEPTH:
        return NO_MATCH
    current = bindings if bindings is not None else {}
    # Variable site
    if is_var(pattern):
        name = pattern["var"]
        if not name:
            return NO_MATCH
        if name in current:
            # Use mu_hash_cached (NOT mu_hash_control_cached) — control hash
            # canonicalizes 0.0→0 which breaks int/float type distinction.
            if mu_hash_cached(current[name]) != mu_hash_cached(input_value):
                return NO_MATCH
            return current
        return {**current, name: input_value}
    # None
    if pattern is None:
        return current if input_value is None else NO_MATCH
    # Bool (before int — bool is subclass of int)
    if isinstance(pattern, bool):
        if isinstance(input_value, bool) and pattern == input_value:
            return current
        return NO_MATCH
    # Int
    if isinstance(pattern, int):
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            if pattern == input_value:
                return current
        return NO_MATCH
    # Float
    if isinstance(pattern, float):
        if isinstance(input_value, float) and pattern == input_value:
            return current
        return NO_MATCH
    # String
    if isinstance(pattern, str):
        if isinstance(input_value, str) and pattern == input_value:
            return current
        return NO_MATCH
    # List
    if isinstance(pattern, list):
        if not isinstance(input_value, list) or len(pattern) != len(input_value):
            return NO_MATCH
        merged = current
        for p_elem, i_elem in zip(pattern, input_value):
            merged = _stage0_match(p_elem, i_elem, merged, _depth + 1)
            if merged is NO_MATCH:
                return NO_MATCH
        return merged
    # Dict (Gate-3: allow pattern to omit _type when input has _type="list")
    if isinstance(pattern, dict):
        if not isinstance(input_value, dict):
            return NO_MATCH
        pattern_keys = set(pattern.keys())
        input_keys = set(input_value.keys())
        if pattern_keys != input_keys:
            extra_is_type = (input_keys - pattern_keys == {"_type"})
            no_pattern_extra = (len(pattern_keys - input_keys) == 0)
            type_is_list = (input_value.get("_type") == "list")
            if not (extra_is_type and no_pattern_extra and type_is_list):
                return NO_MATCH
        merged = current
        for key in pattern:
            merged = _stage0_match(pattern[key], input_value[key], merged, _depth + 1)
            if merged is NO_MATCH:
                return NO_MATCH
        return merged
    return NO_MATCH


@host_recursion(
    "Stage 0 micro-substitute: isinstance dispatch + recursive dict/list traversal. "
    "BOOTSTRAP PRIMITIVE: breaks circular dependency (kernel → subst → kernel). "
    "Same host surface as substitute but ~27 LOC simple tree walk. "
    "Mutation eliminated (P7 Wave 1): dict/list built via generator expressions."
)
def _stage0_substitute(body, bindings, _depth=0):
    """Stage 0 substitute: recursive tree walk. Raises on unbound variable."""
    if _depth > MAX_MU_DEPTH:
        raise TypeError(f"Max depth exceeded in substitute ({MAX_MU_DEPTH})")
    if body is None:
        return None
    if isinstance(body, (bool, int, float, str)):
        return body
    if isinstance(body, dict):
        if is_var(body):
            name = get_var_name(body)
            if name not in bindings:
                raise KeyError(f"Unbound variable: {name}")
            return bindings[name]
        return dict(
            (k, _stage0_substitute(v, bindings, _depth + 1))
            for k, v in body.items()
        )
    if isinstance(body, list):
        return list(
            _stage0_substitute(item, bindings, _depth + 1)
            for item in body
        )
    return body


@host_recursion(
    "Recursive tree traversal for variable substitution. "
    "BOOTSTRAP PRIMITIVE: eval_step() calls this to apply ANY projection. "
    "subst_mu.py expresses the ALGORITHM as projections; this function EXECUTES them."
)
def substitute(body: Mu, bindings: dict[str, Mu], *, _depth: int = 0,
               _budget: object = _NO_BUDGET) -> Mu:
    """
    Substitute variable sites in body with bound values.

    Host debt: 3 isinstance calls for Python type dispatch on body values
    (None/bool/int/float/str check, list check, dict check). Tracked on
    match()'s @host_builtin decorator (same debt surface as _match_inner).

    When _budget is provided, uses structural Mu linked-list budget instead
    of integer _depth for depth limiting. Same semantics (depth-only: same
    remaining budget passed to all siblings at a given level).

    Args:
        body: The body with possible {"var": "x"} sites.
        bindings: Dict mapping variable names to values.

    Keyword Args (internal only — do NOT pass from external callers):
        _depth: Current recursion depth. Enforced by MAX_MU_DEPTH.
        _budget: Structural depth budget (Mu linked-list or None).

    Returns:
        Body with variables replaced by their bound values.

    Raises:
        KeyError: If a variable in body is not in bindings.
        TypeError: If depth exceeds MAX_MU_DEPTH or budget exhausted.
    """
    # --- Structural budget path (opt-in) ---
    if _budget is not _NO_BUDGET:
        ok, remaining = consume_budget(_budget)
        if not ok:
            raise TypeError(f"Structural depth budget exhausted in substitute")
        if _depth == 0:
            assert_mu(body, "substitute.body")

        if is_var(body):
            name = get_var_name(body)
            if name not in bindings:
                raise KeyError(f"Unbound variable: {name}")
            return bindings[name]

        if body is None or isinstance(body, (bool, int, float, str)):
            return body

        if isinstance(body, list):
            return [substitute(elem, bindings, _depth=_depth, _budget=remaining) for elem in body]  # AST_OK: bootstrap recursive substitution

        if isinstance(body, dict):
            return {k: substitute(v, bindings, _depth=_depth, _budget=remaining) for k, v in body.items()}  # AST_OK: bootstrap recursive substitution

        raise TypeError(f"Invalid body type: {type(body)}")

    # --- Integer depth path (default — existing behavior, zero overhead) ---
    if _depth > MAX_MU_DEPTH:
        raise TypeError(f"Max depth exceeded in substitute ({MAX_MU_DEPTH})")
    if _depth == 0:
        assert_mu(body, "substitute.body")

    # Variable site - replace with bound value
    if is_var(body):
        name = get_var_name(body)
        if name not in bindings:
            raise KeyError(f"Unbound variable: {name}")
        return bindings[name]

    # None, bool, int, float, str - return as-is
    if body is None or isinstance(body, (bool, int, float, str)):
        return body

    # List - recursively substitute
    if isinstance(body, list):
        return [substitute(elem, bindings, _depth=_depth + 1) for elem in body]  # AST_OK: bootstrap recursive substitution

    # Dict - recursively substitute values
    if isinstance(body, dict):
        return {k: substitute(v, bindings, _depth=_depth + 1) for k, v in body.items()}  # AST_OK: bootstrap recursive substitution

    # Should not reach here
    raise TypeError(f"Invalid body type: {type(body)}")


def apply_projection(projection: Mu, input_value: Mu) -> Mu | _NoMatch:
    """
    Apply a projection to an input value.

    Host debt (isinstance for type validation and normalization detection)
    is part of the same debt surface tracked on match()'s @host_builtin.

    A projection is {"pattern": P, "body": B}.
    If P matches input, return B with substitutions.
    Otherwise return NO_MATCH.

    Args:
        projection: Dict with "pattern" and "body" keys.
        input_value: The value to transform.

    Returns:
        Transformed value if pattern matched, NO_MATCH otherwise.
    """
    assert_mu(projection, "apply.projection")
    assert_mu(input_value, "apply.input")

    # Guardrail: reject lambda-calculus-like patterns
    assert_not_lambda_calculus(projection)

    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection)}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    bindings = match(pattern, input_value)

    if bindings is NO_MATCH:
        return NO_MATCH

    result = substitute(body, bindings)

    # Gate 3: Auto-denormalize output when body uses normalized dict format.
    # This maintains backwards compatibility with code expecting raw dicts.
    if isinstance(body, dict) and body.get("_type") == "dict":
        from rcx_pi.selfhost.match_mu import denormalize_from_match
        result = denormalize_from_match(result)

    return result


# BOOTSTRAP_PRIMITIVE: eval_step
# This is the irreducible execution primitive - like Forth's NEXT.
# The for-loop cannot be expressed as a projection because projections
# need something to apply them. This IS that something.
# See mu/docs/core/BootstrapPrimitives.v0.md for full justification.
def step(projections: list[Mu], input_value: Mu) -> Mu:
    """
    BOOTSTRAP PRIMITIVE: Apply first matching projection to value.

    This is the irreducible eval_step primitive - analogous to Forth's NEXT
    or the CPU instruction fetch-decode-execute cycle. Projections cannot
    apply themselves; something must try them in order.

    The for-loop is NOT debt - it is the bootstrap iteration that cannot
    be expressed as a projection without infinite regress.

    Args:
        projections: List of projections to try (first-match-wins).
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged (stall) otherwise.

    See: mu/docs/core/BootstrapPrimitives.v0.md
    """
    from rcx_pi.projection_coverage import coverage

    assert_mu(input_value, "step.input")

    if coverage.is_enabled():
        coverage.record_step()

    for proj in projections:
        # Get projection ID for coverage tracking (isinstance here is cosmetic —
        # apply_projection validates proj is dict; this just extracts a label)
        proj_id = proj.get("id", "<anonymous>") if isinstance(proj, dict) else "<invalid>"

        result = apply_projection(proj, input_value)
        if result is not NO_MATCH:
            if coverage.is_enabled():
                coverage.record_match(proj_id, input_value, result)
            return result
        else:
            if coverage.is_enabled():
                coverage.record_no_match(proj_id)

    # No match - return input unchanged (stall)
    return input_value


# =============================================================================
# Trusted Internal Entrypoints (caller-trust model)
# =============================================================================
#
# These bypass assert_mu validation entirely. Trust is EXPLICIT: only kernel
# loops that validated at the boundary may call these. Public callers must
# use step() / apply_projection() which always validate.
#
# Why not shape-based trust: _is_kernel_internal_state can be bypassed with
# nested non-Mu payloads (e.g. {"_mode":"kernel","bad":[{1,2}]}). Caller-trust
# eliminates shape-inference from the security model entirely.

def _apply_projection_trusted(projection: Mu, input_value: Mu) -> Mu | _NoMatch:
    """Internal: apply projection without validating input_value.

    ONLY for use by kernel loops that have already validated at the boundary.
    Callers: _step_trusted, step_kernel_mu (via _step_trusted).

    Host debt (isinstance) tracked on match()'s @host_builtin decorator.

    Note: Skips assert_not_lambda_calculus() by design. Kernel-internal
    projections come from verified seeds (integrity-checked at load time).
    The guardrail is only needed at the public apply_projection() boundary.
    """
    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection)}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    # Use _match_inner directly — no assert_mu on input_value
    if isinstance(pattern, dict) and pattern.get("_type") == "dict":
        from rcx_pi.selfhost.match_mu import normalize_for_match
        input_value = normalize_for_match(input_value)

    # D005 Stage 0 pilot routing (default OFF — zero behavior change at rest)
    if _STAGE0_PILOT:
        bindings = _stage0_match(pattern, input_value)
    else:
        bindings = _match_inner(pattern, input_value)

    if bindings is NO_MATCH:
        return NO_MATCH

    if _STAGE0_PILOT:
        result = _stage0_substitute(body, bindings)
    else:
        result = substitute(body, bindings)

    if isinstance(body, dict) and body.get("_type") == "dict":
        from rcx_pi.selfhost.match_mu import denormalize_from_match
        result = denormalize_from_match(result)

    return result


def _step_trusted(projections: list[Mu], input_value: Mu) -> Mu:
    """Internal: step without validating input_value.

    ONLY for use by kernel loops that have already validated at the boundary.
    Callers: step_kernel_mu, run_engine_pipeline, projection_runner.run.

    Host debt (isinstance for coverage ID, for-loop) tracked on the
    host_builtin decorator on match(). For-loop is bootstrap primitive (not debt).
    """
    from rcx_pi.projection_coverage import coverage

    if coverage.is_enabled():
        coverage.record_step()

    for proj in projections:
        proj_id = proj.get("id", "<anonymous>") if isinstance(proj, dict) else "<invalid>"

        result = _apply_projection_trusted(proj, input_value)
        if result is not NO_MATCH:
            if coverage.is_enabled():
                coverage.record_match(proj_id, input_value, result)
            return result
        else:
            if coverage.is_enabled():
                coverage.record_no_match(proj_id)

    return input_value


# NOTE: Kernel handler framework (create_step_handler, create_stall_handler,
# create_init_handler, create_eval_seed, register_eval_seed) removed in
# Gate 4 cleanup (2026-02-07). The legacy Kernel class they targeted was
# deleted in Phase 8b (2026-01-30).
