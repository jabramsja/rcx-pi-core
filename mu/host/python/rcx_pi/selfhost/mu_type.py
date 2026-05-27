"""
Mu Type Definition and Validation.

A Mu is a JSON-compatible value: the portable, host-independent data type
for all RCX values. This module provides validation to ensure no Python-specific
types leak into the VM.

See mu/docs/core/MuType.v0.md for the full specification.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any


# Type alias for documentation (Python's type system can't express recursive JSON)
Mu = Any  # Actually: None | bool | int | float | str | List[Mu] | Dict[str, Mu]

# BOOTSTRAP_PRIMITIVE: stack_guard (MAX_MU_DEPTH)
# This is the irreducible depth limit that prevents stack overflow.
# Cannot be structural because Python's stack is runtime, not Mu data.
# Protects against deeply nested structures that would overflow during traversal.
# See mu/docs/core/BootstrapPrimitives.v0.md for full justification.
#
# Phase 8b note: Increased from 200 to 300 to support deeper kernel states.
# Kernel normalization converts dicts to linked-lists (head/tail chains),
# increasing depth proportional to dict width (N keys → ~2N depth levels).
# Must stay below ~400 to avoid Python's default recursion limit (~1000).
# Stress tests with max_steps > ~60 may need kernel-internal bypass.
MAX_MU_DEPTH = 300

# Maximum width (number of elements) for lists/dicts (prevents resource exhaustion)
# A dict/list with 1M keys could exhaust memory during validation
MAX_MU_WIDTH = 1000


# =============================================================================
# Structural Depth Budget (D009 Productionization)
# =============================================================================
# Budget is a Mu linked list: {"head": None, "tail": <budget>} or None (exhausted).
# Created once at module load and shared across all calls (depth-only semantics:
# each recursion level reads budget["tail"] but never modifies the original).
# See mu/tests/research/test_d009_h4_depth_threading.py for the research proof.
# =============================================================================


def make_depth_budget(depth: int) -> dict | None:
    """Create a structural depth budget of given size. Returns Mu linked-list.

    The for-loop is an irreducible bootstrap dependency (F2 from D009):
    constructing a linked list of length N requires host iteration.
    """
    budget = None
    for _ in range(depth):  # BOUNDARY: irreducible bootstrap linked-list construction (D009-F2, off kernel path — module-load only). Reclassified P7W4.
        budget = {"head": None, "tail": budget}
    return budget


def consume_budget(budget: dict | None) -> tuple[bool, dict | None]:
    """Consume one level from budget. Returns (ok, remaining).

    ok=True means budget was available and remaining is the tail.
    ok=False means budget is exhausted (None or malformed).

    Budget is always either None (exhausted) or a well-formed linked-list
    node {"head": None, "tail": <budget>} constructed by make_depth_budget().
    All callers are internal — no external input reaches this function.
    isinstance removed (P7 Wave 2): trusting well-formed budget eliminates
    one host_builtin dependency.
    """
    if budget is None:
        return (False, None)
    if "tail" in budget:
        return (True, budget["tail"])
    return (False, None)


# Sentinel for "no budget provided" — distinct from None (= budget exhausted).
# This is necessary because budget["tail"] = None for the last node, and we
# need to distinguish "caller didn't provide a budget" from "budget ran out."
_NO_BUDGET: object = object()

# Module-level shared budget (depth-only traversal reads but never modifies).
# Each node has a stable id() since it's created once — used as O(1) memo key.
_STRUCTURAL_DEPTH_BUDGET = make_depth_budget(MAX_MU_DEPTH + 1)


def is_mu(value: Any, _seen: set[int] | None = None, _depth: int = 0,
          _memo: dict[tuple[int, int], bool] | None = None,
          _budget: object = _NO_BUDGET) -> bool:
    """
    Check if a value is a valid Mu (JSON-compatible).

    A Mu is recursively composed of:
    - None (JSON null)
    - bool (JSON true/false)
    - int, float (JSON number)
    - str (JSON string)
    - list of Mu (JSON array)
    - dict with str keys and Mu values (JSON object)

    Args:
        value: The value to check.
        _seen: Internal parameter for cycle detection. Do not pass.
        _depth: Internal parameter for depth tracking. Do not pass.
        _memo: Internal parameter for per-call memoization. Do not pass.

    Returns:
        True if value is a valid Mu, False otherwise.

    Note:
        Circular references are detected and rejected (return False).
        Deep nesting beyond MAX_MU_DEPTH is rejected (return False).
        Wide structures beyond MAX_MU_WIDTH are rejected (return False).
        This prevents infinite recursion/stack overflow and resource exhaustion attacks.

        Per-call memoization: compound nodes already validated at a given depth
        are not re-walked. Memo key is (id(obj), depth) so that the same object
        at different depths is re-checked (depth affects validity). The memo is
        per-call only (no global cache) and fail-closed: only True results are
        memoized; False results and cycles are always re-checked.

    When _budget is provided (structural budget path):
        Uses structural Mu linked-list budget instead of integer _depth.
        Memo key uses id(_budget) for O(1) lookup (each node in the shared
        singleton has a unique, stable id). See D009 research.
    """
    # --- Structural budget path (opt-in) ---
    if _budget is not _NO_BUDGET:
        ok, remaining = consume_budget(_budget)
        if not ok:
            return False  # Budget exhausted

        if value is None:
            return True
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf')):
                return False
            return True
        if isinstance(value, str):
            return True

        value_type = type(value)
        if value_type is list or value_type is dict:
            if _seen is None:
                _seen = set()
            if _memo is None:
                _memo = {}
            value_id = id(value)
            memo_key = (value_id, id(_budget))
            if memo_key in _memo:
                return _memo[memo_key]
            if value_id in _seen:
                return False
            _seen.add(value_id)

        if value_type is list:
            if len(value) > MAX_MU_WIDTH:
                _seen.discard(value_id)
                return False
            # Depth-only: same 'remaining' passed to all siblings
            result = all(is_mu(item, _seen, _depth, _memo, _budget=remaining) for item in value)
            _seen.discard(value_id)
            if result:
                _memo[memo_key] = True
            return result
        if value_type is dict:
            if len(value) > MAX_MU_WIDTH:
                _seen.discard(value_id)
                return False
            result = (
                all(type(k) is str for k in value.keys()) and
                all(is_mu(v, _seen, _depth, _memo, _budget=remaining) for v in value.values())
            )
            _seen.discard(value_id)
            if result:
                _memo[memo_key] = True
            return result
        return False

    # --- Integer depth path (default — existing behavior, zero overhead) ---
    if _depth > MAX_MU_DEPTH:
        return False

    if value is None:
        return True
    # Check bool before int (bool is subclass of int in Python)
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        # Reject special float values that aren't JSON-compatible
        if isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf')):
            return False  # NaN or Infinity
        return True
    if isinstance(value, str):
        return True

    # For compound types, use exact type check (not isinstance) to reject subclasses.
    # Subclasses can have custom __getitem__/__iter__ that execute side effects,
    # which would be a security concern if accepting Python objects directly.
    # JSON deserialization always produces exact list/dict types, so this is safe.
    value_type = type(value)

    if value_type is list or value_type is dict:
        if _seen is None:
            _seen = set()
        if _memo is None:
            _memo = {}
        value_id = id(value)
        # Per-call memo: skip re-validation of nodes already proven valid at this depth.
        memo_key = (value_id, _depth)
        if memo_key in _memo:
            return _memo[memo_key]
        if value_id in _seen:
            # Circular reference detected - not valid Mu
            return False
        # Backtracking: add on entry, remove on exit.
        # O(1) per node (vs O(depth) for set copy).
        # Detects true cycles (ancestor→descendant) while accepting
        # DAGs (shared structure from match substitution).
        _seen.add(value_id)

    if value_type is list:
        # Width limit check (prevents resource exhaustion attacks)
        if len(value) > MAX_MU_WIDTH:
            _seen.discard(value_id)
            return False
        result = all(is_mu(item, _seen, _depth + 1, _memo) for item in value)
        _seen.discard(value_id)
        if result:
            _memo[memo_key] = True
        return result
    if value_type is dict:
        # Width limit check (prevents resource exhaustion attacks)
        if len(value) > MAX_MU_WIDTH:
            _seen.discard(value_id)
            return False
        result = (
            all(type(k) is str for k in value.keys()) and
            all(is_mu(v, _seen, _depth + 1, _memo) for v in value.values())
        )
        _seen.discard(value_id)
        if result:
            _memo[memo_key] = True
        return result
    # Anything else (function, class, object, bytes, set, tuple, subclasses, etc.) is not a Mu
    return False


def validate_mu(value: Any) -> bool:
    """
    Validate that a value is a portable Mu via JSON round-trip.

    This is stricter than is_mu() - it actually serializes and deserializes
    to catch edge cases. Uses allow_nan=False to reject NaN/Infinity.

    Returns:
        True if value round-trips through JSON correctly.
    """
    try:
        # allow_nan=False ensures NaN/Infinity raise ValueError
        serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
        deserialized = json.loads(serialized)
        reserialized = json.dumps(deserialized, sort_keys=True, ensure_ascii=False, allow_nan=False)
        return serialized == reserialized
    except (TypeError, ValueError, OverflowError):
        return False


def assert_mu(value: Any, context: str = "value") -> None:
    """
    Assert that a value is a valid Mu, raising TypeError if not.

    Args:
        value: The value to check.
        context: Description for error message (e.g., "R0 register").

    Raises:
        TypeError: If value is not a valid Mu.
    """
    if not is_mu(value):
        raise TypeError(
            f"{context} must be a Mu (JSON-compatible value), got {type(value).__name__}: {value!r}"
        )


def mu_type_name(value: Any) -> str:
    """
    Return the Mu type name for a value.

    Returns one of: "null", "bool", "int", "float", "str", "list", "dict", or "INVALID".
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if type(value) is list:
        return "list"
    if type(value) is dict:
        return "dict"
    return "INVALID"


# =============================================================================
# Structural Purity Guardrails
# =============================================================================
# These functions ensure we program IN RCX (using Mu) rather than ABOUT RCX
# (using Python constructs). See mu/docs/core/StructuralPurity.v0.md for rationale.
# =============================================================================


def find_callable_path(value: Any, path: str = "", _seen: set[int] | None = None,
                       _depth: int = 0) -> str | None:
    """
    Find the path to the first callable in a value.

    Args:
        value: The value to search.
        path: Current path (internal, builds up during recursion).
        _seen: Internal parameter for cycle detection. Do not pass.
        _depth: Internal parameter for depth tracking. Do not pass.

    Returns:
        Path string like "projections[0].handler" or None if no callable found.

    Note:
        Circular references are handled safely.
    """
    if callable(value):
        return path or "(root)"

    if _depth >= MAX_MU_DEPTH:
        return None  # Too deep — no callable found within depth limit

    # For compound types, check for circular references.
    # Uses isinstance (not type()) intentionally — catches callables hidden in subclasses.
    if isinstance(value, (list, dict)):
        if _seen is None:
            _seen = set()
        value_id = id(value)
        if value_id in _seen:
            return None
        # Backtracking: add on entry, remove on exit.
        # O(1) per node (vs O(depth) for set copy).
        _seen.add(value_id)
        found = None
        if isinstance(value, list):
            for i, item in enumerate(value):
                found = find_callable_path(item, f"{path}[{i}]", _seen, _depth + 1)
                if found:
                    break
        else:
            for k, v in value.items():
                found = find_callable_path(v, f"{path}.{k}" if path else k, _seen, _depth + 1)
                if found:
                    break
        _seen.discard(value_id)
        return found

    return None


def assert_no_callables(value: Any, context: str = "value") -> None:
    """
    Assert that a value contains no callables, raising TypeError if it does.

    This prevents Python functions/lambdas from leaking into Mu structures.

    Args:
        value: The value to check.
        context: Description for error message.

    Raises:
        TypeError: If value contains a callable.
    """
    path = find_callable_path(value)
    if path:
        raise TypeError(
            f"{context} contains callable at {path}. "
            f"Seeds must be pure Mu (no functions, lambdas, or methods)."
        )


def assert_seed_pure(seed: Any, context: str = "seed") -> None:
    """
    Verify a seed is pure Mu with no host contamination.

    Checks:
    1. Seed is valid Mu (JSON-compatible)
    2. No callable values anywhere in structure
    3. If seed has projections, each has pattern and body, both Mu

    Args:
        seed: The seed structure to validate.
        context: Description for error message.

    Raises:
        TypeError: If seed is not pure Mu.
        ValueError: If seed structure is invalid.
    """
    # Check 1: Must be valid Mu
    assert_mu(seed, context)

    # Check 2: No callables (redundant with is_mu, but explicit)
    assert_no_callables(seed, context)

    # Check 3: Validate projection structure if present
    if isinstance(seed, dict):
        seed_data = seed.get("seed", seed)
        if isinstance(seed_data, dict):
            projections = seed_data.get("projections", [])
            if isinstance(projections, list):
                for i, proj in enumerate(projections):
                    proj_ctx = f"{context}.projections[{i}]"
                    if not isinstance(proj, dict):
                        raise ValueError(f"{proj_ctx} must be a dict, got {type(proj).__name__}")
                    if "pattern" not in proj:
                        raise ValueError(f"{proj_ctx} missing 'pattern' field")
                    if "body" not in proj:
                        raise ValueError(f"{proj_ctx} missing 'body' field")
                    assert_mu(proj["pattern"], f"{proj_ctx}.pattern")
                    assert_mu(proj["body"], f"{proj_ctx}.body")


def assert_handler_pure(handler: Any, name: str) -> Any:
    """
    Wrap a handler function to verify Mu in, Mu out.

    This is a BOOTSTRAP guardrail. During Phase 1, handlers are Python
    functions. This wrapper ensures they respect Mu boundaries.

    WHY KEPT (0 production callers): Ready-to-wire guardrail for handler
    registration. Will be wired when handler dispatch is formalized (L4+).
    Tested in test_mu_type.py to prevent API drift until wired.

    Args:
        handler: The handler function to wrap.
        name: Name for error messages.

    Returns:
        Wrapped handler that validates input/output are Mu.

    Note:
        The handler itself is a Python callable (allowed during bootstrap).
        What's validated is that it receives Mu and returns Mu.
    """
    if not callable(handler):
        raise TypeError(f"Handler '{name}' must be callable, got {type(handler).__name__}")

    def wrapped(context: Mu) -> Mu:
        # Validate input is Mu
        assert_mu(context, f"{name} input")
        # Call original handler
        result = handler(context)
        # Validate output is Mu
        assert_mu(result, f"{name} output")
        return result

    # Preserve original function name for debugging
    wrapped.__name__ = f"pure_{name}"
    wrapped.__doc__ = f"Mu-pure wrapper for {name}"

    return wrapped


def validate_kernel_boundary(func_name: str, inputs: dict[str, Any], output: Any) -> None:
    """
    Validate that a kernel primitive respects Mu boundaries.

    Called by kernel primitives to ensure:
    - All Mu inputs are valid Mu
    - Output is valid Mu (if applicable)

    WHY KEPT (0 production callers): Ready-to-wire guardrail for kernel
    primitive boundary enforcement. Will be wired when kernel primitives
    are audited for Mu boundary compliance (L4+). Tested in test_mu_type.py
    to prevent API drift until wired.

    Args:
        func_name: Name of the kernel primitive.
        inputs: Dict of input name -> value for Mu inputs.
        output: The output value (or None if no Mu output).

    Raises:
        TypeError: If any boundary violation detected.
    """
    for input_name, value in inputs.items():
        assert_mu(value, f"{func_name} {input_name}")
    if output is not None:
        assert_mu(output, f"{func_name} output")


# =============================================================================
# Structural Equality (Anti-Python-Coercion)
# =============================================================================
# Python's == has type coercion (True == 1). We need structural equality
# that compares via canonical JSON serialization.
# =============================================================================


# DEMOTED PRIMITIVE: mu_equal (Content-Addressed Mu Level 1, 2026-02-10)
# Previously bootstrap primitive #5 for fixed-point detection.
# Now derivable: mu_equal(a, b) ≡ mu_hash_cached(a) == mu_hash_cached(b)
# Bootstrap primitives reduced from 5 to 4.
#
# WHY KEPT (not archived): ~30 call sites in tests + JS parity (muEqual).
# Tests use mu_equal for readability; all PRODUCTION code uses mu_hash_cached directly.
# Archiving would touch 30+ files for zero functional/security benefit.
# See mu/docs/core/BootstrapPrimitives.v0.md.
def mu_equal(a: Any, b: Any) -> bool:
    """
    Convenience wrapper: compare two Mu values for structural equality.

    Delegates to mu_hash_cached. No longer a bootstrap primitive — production
    code uses mu_hash_cached directly for stall detection and binding conflict.

    Args:
        a: First Mu value.
        b: Second Mu value.

    Returns:
        True if values are structurally identical.

    Raises:
        TypeError: If either value is not a valid Mu.
    """
    assert_mu(a, "mu_equal.a")
    assert_mu(b, "mu_equal.b")
    return mu_hash_cached(a) == mu_hash_cached(b)


# Cache for mu_hash: canonical JSON → SHA-256 hex digest
# Bounded LRU: evicts oldest entries when MAX_MU_HASH_CACHE exceeded.
# Prevents unbounded memory growth during long-running evaluations.
MAX_MU_HASH_CACHE = 10_000
_mu_hash_cache: OrderedDict[str, str] = OrderedDict()



def _compute_mu_hash(canonical: str) -> str:
    """SHA-256 of canonical JSON string. Single hash algorithm definition."""
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def mu_hash_cached(value: Any) -> str:
    """
    Compute deterministic hash of a Mu value with caching.

    Caches by canonical JSON serialization to avoid re-hashing identical
    structures. Used for hash-accelerated equality comparison (Content-Addressed
    Mu Level 1).

    Cache is bounded to MAX_MU_HASH_CACHE entries (LRU eviction).

    Args:
        value: A Mu value.

    Returns:
        Hex string of SHA-256 hash.

    Raises:
        TypeError: If value is not a valid Mu.
    """
    assert_mu(value, "mu_hash_cached")
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    cached = _mu_hash_cache.get(canonical)
    if cached is not None:
        # Move to end (most recently used)
        _mu_hash_cache.move_to_end(canonical)
        return cached
    h = _compute_mu_hash(canonical)
    _mu_hash_cache[canonical] = h
    # Evict oldest if over limit
    if len(_mu_hash_cache) > MAX_MU_HASH_CACHE:
        _mu_hash_cache.popitem(last=False)
    return h


def mu_hash(value: Any) -> str:
    """
    Compute deterministic hash of a Mu value.

    Uses SHA-256 of canonical JSON serialization.

    Args:
        value: A Mu value.

    Returns:
        Hex string of SHA-256 hash.

    Raises:
        TypeError: If value is not a valid Mu.
    """
    assert_mu(value, "mu_hash")
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return _compute_mu_hash(canonical)


# =============================================================================
# Numeric Hash Control (Control-Channel Safety Lock)
# =============================================================================
# Control-flow hash paths (stall detection, convergence, recurrence trace)
# must reject ambiguous numeric domain to prevent cross-substrate divergence.
# Python json.dumps(1.0) → "1.0" but JS JSON.stringify(1.0) → "1".
# These wrappers: validate Mu → reject non-integer floats → canonicalize → hash.
# Data-flow paths (observer output, undefined motif) use mu_hash directly.
# See NorthStarSemantics.v0.md §B.1 for policy.
# =============================================================================


def _canonicalize_hash_numeric(value: Any) -> Any:
    """Canonicalize numeric domain: integral float→int, ±0.0→0.

    This ensures 1.0 and 1 hash identically, and -0.0 maps to 0.
    Only used in control-channel wrappers after assert_hash_numeric_safe.
    No depth guard needed: callers validate via assert_mu(MAX_MU_DEPTH=300).

    Guard: only int-cast when abs(value) < 1e21 (JS JSON.stringify integer
    threshold). JS uses full integer form for values < 1e21, then switches
    to scientific notation at 1e21+. Python int() always uses full integer
    form. So int-casting is safe below 1e21 (both substrates agree on the
    string), but diverges at 1e21+ (Python: full digits, JS: scientific).
    """
    if isinstance(value, float):
        if value == 0.0:
            return 0
        if value.is_integer() and abs(value) < 1e21:
            return int(value)
        return value  # non-integer or large integral float — keep as-is
    if type(value) is list:
        return [_canonicalize_hash_numeric(v) for v in value]  # AST_OK: infra — numeric canonicalization helper
    if type(value) is dict:
        return {k: _canonicalize_hash_numeric(v) for k, v in value.items()}  # AST_OK: infra — numeric canonicalization helper
    return value  # str, int, bool, None — unchanged


def mu_hash_control(value: Any, context: str = "mu_hash_control") -> str:
    """Hash a Mu value for control-flow paths (stall, convergence, trace).

    Validates Mu, canonicalizes numerics (integral float→int, ±0→0), then
    delegates to mu_hash. Use this instead of mu_hash in control paths.
    """
    assert_mu(value, context)
    canonical_value = _canonicalize_hash_numeric(value)
    canonical = json.dumps(canonical_value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return _compute_mu_hash(canonical)


def mu_hash_control_cached(value: Any, context: str = "mu_hash_control_cached") -> str:
    """Hash a Mu value for control-flow paths with caching.

    Validates Mu, canonicalizes numerics (integral float→int, ±0→0), then
    delegates to mu_hash_cached. Use this instead of mu_hash_cached in control paths.
    """
    assert_mu(value, context)
    canonical_value = _canonicalize_hash_numeric(value)
    canonical = json.dumps(canonical_value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    cached = _mu_hash_cache.get(canonical)
    if cached is not None:
        _mu_hash_cache.move_to_end(canonical)
        return cached
    h = _compute_mu_hash(canonical)
    _mu_hash_cache[canonical] = h
    if len(_mu_hash_cache) > MAX_MU_HASH_CACHE:
        _mu_hash_cache.popitem(last=False)
    return h


# =============================================================================
# Bootstrap Markers
# =============================================================================
# Functions for marking Python code that will be replaced by seeds.
# =============================================================================


BOOTSTRAP_REGISTRY: list[str] = []


def mark_bootstrap(name: str, reason: str) -> None:
    """
    Mark a function/code section as bootstrap-only.

    Bootstrap code is Python that will be replaced by EVAL_SEED.
    This registry tracks what needs to be removed for true self-hosting.

    Args:
        name: Identifier for the bootstrap code.
        reason: Why this is bootstrap (what seed will replace it).
    """
    entry = f"{name}: {reason}"
    if entry not in BOOTSTRAP_REGISTRY:
        BOOTSTRAP_REGISTRY.append(entry)


def get_bootstrap_registry() -> list[str]:
    """Return list of all registered bootstrap code."""
    return list(BOOTSTRAP_REGISTRY)


def assert_no_bootstrap_in_production() -> None:
    """
    Assert that no bootstrap code is registered.

    Currently unreachable in production: @host_* decorators always populate
    BOOTSTRAP_REGISTRY on import, and L2 accepted these as irreducible.
    Retained as a design checkpoint for L4+ if bootstrap elimination becomes
    viable. Tests in test_mu_type.py validate both paths to prevent API drift.

    Raises:
        RuntimeError: If bootstrap code is still registered.
    """
    if BOOTSTRAP_REGISTRY:
        raise RuntimeError(
            f"Bootstrap code still present (should be replaced by seeds): "
            f"{BOOTSTRAP_REGISTRY}"
        )
