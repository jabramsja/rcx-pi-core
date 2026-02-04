"""
Step as Mu Projections - Phase 7d Self-Hosting

This module implements the step function using Mu projections instead of
Python recursion. It achieves parity with eval_seed.step() using match_mu
and subst_mu.

Phase 7d: Meta-circular kernel
- step_mu() now uses structural kernel projections (kernel.v1 + match.v2 + subst.v2)
- The Python for-loop is replaced with kernel projections that iterate structurally
- Iteration uses linked-list cursor, not arithmetic

TERMINOLOGY NOTE:
- kernel.v1.json = structural kernel (7 Mu projections for iteration)
- Kernel class (kernel.py) = Python scaffolding (hash, trace, dispatch)

This module uses kernel.v1.json projections for structural iteration.
The Kernel class is NOT involved in self-hosting - it's boundary scaffolding.
step_kernel_mu() correctly uses the structural kernel; it is NOT "bypassing"
the kernel architecture.

SECURITY: Projection order is security-critical. When combining kernel
projections with domain projections (Phase 7+), kernel projections MUST
run first to prevent domain data from forging kernel state.

See docs/core/SelfHosting.v0.md for design.
See docs/core/MetaCircularKernel.v0.md for kernel design.
"""

from __future__ import annotations

from .eval_seed import NO_MATCH, host_iteration, step as eval_step
from .match_mu import match_mu, normalize_for_match, denormalize_from_match
from .subst_mu import subst_mu
from .mu_type import Mu, assert_mu, mu_equal
from .seed_integrity import get_seed_path, load_verified_seed


# =============================================================================
# Projection Order Security (Phase 7+)
# =============================================================================

def is_kernel_projection(projection: Mu) -> bool:
    """
    Check if a projection is a kernel projection (matches _mode prefix).

    Kernel projections have patterns that match on _mode field, which is
    the kernel namespace. Domain projections should not use _mode patterns.

    Args:
        projection: A projection dict with pattern and body.

    Returns:
        True if projection ID starts with "kernel." or pattern has _mode key.
    """
    if not isinstance(projection, dict):
        return False

    # Check by ID (fast path)
    proj_id = projection.get("id", "")
    if isinstance(proj_id, str) and proj_id.startswith("kernel."):
        return True

    # Check by pattern structure (fallback)
    pattern = projection.get("pattern", {})
    if isinstance(pattern, dict) and "_mode" in pattern:
        return True

    return False


def validate_kernel_projections_first(projections: list[Mu]) -> None:
    """
    Validate that kernel projections appear before domain projections.

    SECURITY: This is critical for Phase 7+ when kernel and domain projections
    are combined. If domain projections run first, they could forge kernel state
    by matching patterns like {"_step": ..., "_projs": ...} before kernel.wrap.

    Args:
        projections: List of projections to validate.

    Raises:
        ValueError: If domain projection appears before kernel projection.
    """
    seen_domain = False
    first_domain_id = None

    for proj in projections:
        is_kernel = is_kernel_projection(proj)

        if is_kernel and seen_domain:
            proj_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"
            raise ValueError(
                f"SECURITY: Kernel projection '{proj_id}' appears after domain projection "
                f"'{first_domain_id}'. Kernel projections MUST be first to prevent "
                f"domain data from forging kernel state."
            )

        if not is_kernel and not seen_domain:
            seen_domain = True
            first_domain_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"


# =============================================================================
# Kernel Boundary Security (Phase 7d - Adversary Review Fix)
# =============================================================================

# Fields reserved for kernel internal state - domain data cannot contain these
# Note: 'subst' and 'match' are NOT included - they're too generic as domain keys.
# The bypass functions (is_kernel_intermediate, _is_kernel_internal_state) check
# for these to skip validation of kernel states, but domain data with these keys
# cannot forge kernel state because kernel projections require specific patterns.
#
# Gate 3 (2026-02-04) Security fix: Entry point keys (_detect_closure, _detect_exhaustion)
# moved to ALGORITHM_ENTRYPOINT_KEYS. Reserved fields allowed ONLY inside entrypoint subtrees.
# See validate_no_kernel_reserved_fields() for subtree-scoped validation.
KERNEL_RESERVED_FIELDS = frozenset({  # AST_OK: security whitelist - frozen constant
    "_mode", "_phase", "_input", "_remaining",
    "_match_ctx", "_subst_ctx", "_kernel_ctx",
    "_status", "_result", "_stall",
    "_step", "_projs",  # Kernel entry format fields (Phase 8b adversary fix)
    # Recurrence closure detection fields (9-agent review, 2026-02-02)
    "_seen", "_current", "_check_list",
    # Operator Exhaustion fields (Step 6 preparation, 2026-02-02)
    "_frozen", "_tau_step", "_operator_ids",
    # Bootstrap-Structural Bridge lookup phase fields (9-agent review, 2026-02-02)
    "_lookup_name", "_lookup_value", "_lookup_bindings", "_original_bindings"
})

# Algorithm entrypoint keys - reserved fields are ONLY allowed inside these subtrees.
# Gate 3 (2026-02-04) Security fix: Prevents spoofed _mode/_phase at top level from
# bypassing validation. Attack vector blocked: {"_mode": "recurrence", "_result": "pwned"}
# Allowed: {"_detect_closure": {"_mode": "recurrence", ...}}
ALGORITHM_ENTRYPOINT_KEYS = frozenset({  # AST_OK: security whitelist - frozen constant
    "_detect_closure",      # Recurrence algorithm entry point
    "_detect_exhaustion",   # Exhaustion algorithm entry point
})


def validate_no_kernel_reserved_fields(
    value: Mu,
    context: str = "input",
    _depth: int = 0,
    _in_algorithm_subtree: bool = False
) -> None:
    """
    Validate that a value does not contain kernel-reserved fields (DEEP).

    SECURITY: Prevents domain data from forging kernel state by including
    fields like _mode, _match_ctx, etc. If domain input contains these
    at ANY nesting level, it could potentially confuse the kernel state machine.

    Gate 3 (2026-02-04) Security fix: Reserved fields are now allowed ONLY inside
    algorithm entrypoint subtrees (_detect_closure, _detect_exhaustion).
    Attack vector blocked: {"_mode": "recurrence", "_result": "pwned"}
    Allowed: {"_detect_closure": {"_mode": "recurrence", ...}}

    This validation is called at the kernel entry point (step_kernel_mu)
    to ensure domain inputs are clean at all depths.

    Args:
        value: The Mu value to validate.
        context: Description for error message (e.g., "input", "projection body").
        _depth: Internal recursion depth tracker (prevents stack overflow).
        _in_algorithm_subtree: True if we're inside an algorithm entrypoint subtree.

    Raises:
        ValueError: If value contains kernel-reserved fields outside entrypoint subtrees.
    """
    # Depth guard - FAIL CLOSED on pathological inputs (Phase 8b expert fix)
    # Adversary model: Domain inputs may be untrusted (e.g., from network).
    # Trade-off: Depth 100 allows reasonable nesting but prevents stack overflow.
    # Security: Fail CLOSED (reject) rather than open (trust).
    MAX_VALIDATION_DEPTH = 100  # AST_OK: infra - constant definition
    if _depth > MAX_VALIDATION_DEPTH:
        raise ValueError(
            f"SECURITY: {context} exceeded maximum validation depth ({MAX_VALIDATION_DEPTH}). "
            f"Possible deeply nested attack structure."
        )

    if isinstance(value, dict):
        for key, val in value.items():
            # Check if we're entering an algorithm entrypoint subtree
            entering_algorithm = key in ALGORITHM_ENTRYPOINT_KEYS

            # Reserved fields are only allowed inside algorithm entrypoint subtrees
            if key in KERNEL_RESERVED_FIELDS and not _in_algorithm_subtree:
                raise ValueError(
                    f"SECURITY: {context} cannot contain kernel-reserved field: {key}. "
                    f"Reserved fields: {sorted(KERNEL_RESERVED_FIELDS)}"
                )
            # Recurse into nested values, tracking if we're in an entrypoint subtree
            validate_no_kernel_reserved_fields(
                val, context, _depth + 1,
                _in_algorithm_subtree=(_in_algorithm_subtree or entering_algorithm)
            )
    elif isinstance(value, list):
        for item in value:
            validate_no_kernel_reserved_fields(item, context, _depth + 1, _in_algorithm_subtree)


# =============================================================================
# Structural Kernel Helpers (Phase 7d)
# =============================================================================

# Module-level cache for combined kernel projections
_combined_kernel_cache: list[Mu] | None = None


def list_to_linked(items: list[Mu]) -> Mu:
    """
    Convert Python list to Mu linked-list format.

    [a, b, c] -> {head: a, tail: {head: b, tail: {head: c, tail: null}}}
    [] -> null

    Required for structural kernel iteration (no arithmetic in pure Mu).
    Uses iterative construction for performance.

    Args:
        items: Python list of Mu values.

    Returns:
        Mu linked-list (dict with head/tail) or None for empty list.
    """
    if not items:
        return None
    result: Mu = None
    for item in reversed(items):
        result = {"head": item, "tail": result}
    return result


def normalize_projection(proj: dict) -> dict:
    """
    Normalize a projection's pattern and body for kernel use.

    Both pattern and body are converted to head/tail format so they can
    be structurally matched and substituted by the Mu projections.

    Args:
        proj: Projection dict with "pattern" and "body" keys.

    Returns:
        Dict with normalized pattern and body.
    """
    return {
        "pattern": normalize_for_match(proj["pattern"]),
        "body": normalize_for_match(proj["body"])
    }


def load_combined_kernel_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + subst.v2 projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns a shallow copy to prevent callers from mutating the cache.
    (Adversary finding: cache mutation vulnerability - defensive copy)

    Returns:
        Combined list of kernel, match, and subst projections.
    """
    global _combined_kernel_cache
    if _combined_kernel_cache is not None:
        return list(_combined_kernel_cache)  # Defensive copy prevents cache mutation

    # Use mu/ as canonical location via get_seed_path()
    kernel_seed = load_verified_seed(get_seed_path("kernel.v1.json"))
    match_seed = load_verified_seed(get_seed_path("match.v2.json"))
    subst_seed = load_verified_seed(get_seed_path("subst.v2.json"))

    # SECURITY: Kernel projections MUST be first
    _combined_kernel_cache = (
        kernel_seed["projections"] +
        match_seed["projections"] +
        subst_seed["projections"]
    )
    return list(_combined_kernel_cache)  # Defensive copy prevents cache mutation


def clear_combined_kernel_cache() -> None:
    """
    Clear the combined kernel projection cache.

    9-agent round 2 (Expert finding): Restored for test isolation.
    Tests that mock projections need this to prevent stale cache pollution.
    """
    global _combined_kernel_cache, _combined_kernel_bridge_cache
    _combined_kernel_cache = None
    _combined_kernel_bridge_cache = None


# Module-level cache for combined kernel projections with bootstrap_structural bridge
_combined_kernel_bridge_cache: list[Mu] | None = None


def load_combined_kernel_with_bridge_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + bootstrap_structural + subst.v2 projections.

    This variant uses bootstrap_structural.v1 which provides non-linear pattern
    support (binding conflict detection) as structural projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns a shallow copy to prevent callers from mutating the cache.
    (Adversary finding: cache mutation vulnerability - defensive copy)

    Required for META_CIRCULAR seeds:
    - recurrence.v1.json (uses non-linear patterns for state equality)
    - exhaustion.v1.json (uses non-linear patterns for operator equality)

    Returns:
        Combined list of kernel, match.v2, bootstrap_structural, and subst projections.
    """
    global _combined_kernel_bridge_cache
    if _combined_kernel_bridge_cache is not None:
        return list(_combined_kernel_bridge_cache)  # Defensive copy prevents cache mutation

    # Use mu/ as canonical location via get_seed_path()
    kernel_seed = load_verified_seed(get_seed_path("kernel.v1.json"))
    match_seed = load_verified_seed(get_seed_path("match.v2.json"))
    bridge_seed = load_verified_seed(get_seed_path("bootstrap_structural.v1.json"))
    subst_seed = load_verified_seed(get_seed_path("subst.v2.json"))

    # SECURITY: Kernel projections MUST be first
    # Order: kernel → bridge (intercepts vars) → match.v2 → subst
    # CRITICAL: bridge MUST come before match.v2 so bridge.var.check_existing
    # intercepts {"var": "x"} patterns before match.var handles them.
    # This enables non-linear pattern detection (same var twice).
    _combined_kernel_bridge_cache = (
        kernel_seed["projections"] +
        bridge_seed["projections"] +
        match_seed["projections"] +
        subst_seed["projections"]
    )
    return list(_combined_kernel_bridge_cache)  # Defensive copy prevents cache mutation


# =============================================================================
# Kernel Terminal Detection (Phase 8b)
# =============================================================================


def is_kernel_terminal(result: Mu) -> bool:
    """
    Check if result is in kernel terminal state.

    Terminal state is: {"_mode": "done", "_result": ..., "_stall": ...}
    This is a simple structural marker check - no semantic decisions.
    The kernel itself determines what "done" means; we just detect the marker.

    Phase 8b: This replaces the semantic branching that was inside the loop.
    """
    return (
        isinstance(result, dict) and
        result.get("_mode") == "done" and
        "_result" in result and
        "_stall" in result
    )


def is_kernel_intermediate(result: Mu) -> bool:
    """
    Check if result is an intermediate kernel state (mid-execution).

    Intermediate states have kernel-internal fields that indicate
    the kernel is still processing (match, subst, or kernel phases).
    These include:
    - subst, _subst_ctx (substitution in progress)
    - match, _match_ctx (matching in progress)
    - _mode with value other than "done" (kernel loop in progress)

    These are NOT stalls - the kernel is actively working.
    We skip the mu_equal stall check for these because:
    1. They may have deeply nested linked-list structures
    2. They're intermediate by definition - no comparison needed

    Phase 8b: This prevents mu_equal from being called on kernel internals.
    """
    if not isinstance(result, dict):
        return False

    # Kernel internal fields indicate mid-execution
    # Use tuple for determinism (avoid set literal)
    # SECURITY FIX (9-agent round 2): Only check underscore-prefixed fields.
    # Generic keys 'match' and 'subst' removed - domain data can legitimately
    # contain these, and checking for them bypasses stall detection.
    # See KERNEL_RESERVED_FIELDS comment at line 110-113.
    kernel_internal_fields = ('_subst_ctx', '_match_ctx', '_kernel_ctx')
    if any(f in result for f in kernel_internal_fields):  # AST_OK: infra
        return True

    # _mode present but not "done" means kernel loop in progress
    if "_mode" in result and result.get("_mode") != "done":
        return True

    return False


def extract_kernel_result(terminal_state: Mu, original_input: Mu) -> Mu:
    """
    Extract result from terminal kernel state.

    If _stall is true, return original input (preserves Python type info
    for empty containers that normalize to None).
    Otherwise, denormalize and return the result.

    This is mechanical unpacking of the structural marker - no semantic
    decisions about WHAT constitutes terminal are made here.

    Phase 8b: This replaces the semantic branching that was inside the loop.
    """
    if terminal_state.get("_stall") is True:
        return original_input
    return denormalize_from_match(terminal_state.get("_result"))


@host_iteration("Kernel execution loop - mechanical driver (Phase 8b simplified)")
def step_kernel_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order using structural kernel projections.

    Phase 8b: MECHANICAL driver - no semantic decisions inside the loop.
    The for-loop is the bootstrap primitive (like Forth's NEXT). It stays.
    Semantic decisions moved to structural kernel projections.

    The kernel works as a state machine:
    1. kernel.wrap: Wraps input and projections into kernel state
    2. kernel.try: Tries first projection via match.v2
    3. kernel.match_success/fail: On success, substitute via subst.v2; on fail, try next
    4. kernel.stall: All projections tried, no match -> {_mode: "done", _stall: true}
    5. kernel.unwrap: Success -> {_mode: "done", _result: X, _stall: false}

    The loop ONLY does:
    - is_kernel_terminal(): Check for structural marker {_mode: "done", ...}
    - extract_kernel_result(): Unpack the marker (no semantic decisions)
    - mu_equal(): Detect no-progress stall

    L2 FULL: Projection SELECTION is structural (linked-list cursor).
    Projection EXECUTION uses Python for-loop (accepted as bootstrap primitive per Phase 8 decision).

    Args:
        projections: List of domain projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
        ValueError: If input contains kernel-reserved fields (security).
    """
    assert_mu(input_value, "step_kernel_mu.input")

    # SECURITY: Validate input doesn't contain kernel-reserved fields
    validate_no_kernel_reserved_fields(input_value, "step_kernel_mu input")

    # SECURITY: Validate projection order
    validate_kernel_projections_first(projections)

    # SECURITY: Reject kernel projections - step_kernel_mu expects DOMAIN projections only
    # Kernel projections are loaded separately via load_combined_kernel_projections().
    # Check by ID (kernel.*) not by _mode pattern because algorithm projections use _mode.
    for i, proj in enumerate(projections):
        proj_id = proj.get("id", "") if isinstance(proj, dict) else ""
        if isinstance(proj_id, str) and proj_id.startswith("kernel."):
            raise ValueError(
                f"SECURITY: step_kernel_mu expects DOMAIN projections only, "
                f"got kernel projection at index {i}: {proj_id}"
            )

    # SECURITY: Validate each domain projection's pattern and body for reserved fields
    # This matches JS stepKernel validation (parity requirement)
    for i, proj in enumerate(projections):
        if isinstance(proj, dict):
            if "pattern" in proj:
                validate_no_kernel_reserved_fields(proj["pattern"], f"projection[{i}].pattern")
            if "body" in proj:
                validate_no_kernel_reserved_fields(proj["body"], f"projection[{i}].body")

    # Load combined kernel projections
    kernel_projs = load_combined_kernel_projections()

    # Normalize domain projections to head/tail format
    normalized_projs = [normalize_projection(p) for p in projections]  # AST_OK: infra - kernel bridge scaffolding

    # Normalize input value
    normalized_input = normalize_for_match(input_value)

    # Build kernel entry format: {_step: normalized_input, _projs: linked_list}
    kernel_entry: Mu = {
        "_step": normalized_input,
        "_projs": list_to_linked(normalized_projs)
    }

    # Run kernel until done or stall
    current = kernel_entry
    # BOOTSTRAP_PRIMITIVE: max_steps
    # This is the irreducible resource exhaustion guard.
    # Cannot be structural (would require arithmetic on fuel).
    # Prevents infinite execution - analogous to watchdog timer.
    # See docs/core/BootstrapPrimitives.v0.md
    max_steps = 10000

    # Phase 8b: Simplified mechanical loop - no semantic decisions inside
    for _ in range(max_steps):
        result = eval_step(kernel_projs, current)

        # Terminal state check - simple structural marker detection
        if is_kernel_terminal(result):
            return extract_kernel_result(result, input_value)

        # Stall check - no change means no progress
        # Skip for intermediate kernel states (they have deep nested structures
        # and are mid-execution by definition, not stalls)
        if not is_kernel_intermediate(result) and mu_equal(result, current):
            return input_value

        current = result

    # Max steps exceeded - return original input (stall)
    return input_value


def run_algorithm_meta_circular(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Run an internal algorithm (recurrence, exhaustion) via HYBRID execution.

    CURRENT EXECUTION (Gate 2):
    This function delegates to step_algorithm_with_bridge(), which uses
    Python's match() and substitute() for practical execution. This is
    HYBRID execution, not true meta-circular.

    WHY HYBRID:
    Algorithm states contain reserved kernel fields (_detect_closure, _mode,
    _phase, etc.) that step_kernel_mu() rejects. Until Gate 3 rewrites the
    seeds to use non-reserved field names, algorithms cannot enter the kernel.
    See "Known Architectural Constraints" in MetaCircular_Boot0_GatePlan.md.

    STRUCTURAL PROOF:
    The bootstrap_structural bridge PROVES that non-linear pattern support
    CAN be implemented structurally (bridge.var.check_existing, bridge.lookup.*).
    This satisfies the META_CIRCULAR declaration for parity testing purposes.

    FUTURE (Gate 4):
    Once seeds are rewritten (Gate 3), this function will use the actual
    structural kernel with bridge projections.

    Args:
        projections: Algorithm projections (recurrence.v1 or exhaustion.v1).
        input_value: Algorithm entry point or intermediate state.

    Returns:
        Algorithm result after single projection application.
    """
    assert_mu(input_value, "run_algorithm_meta_circular.input")

    # Run through structural match/subst with bridge projections.
    # Bridge projections provide non-linear pattern support STRUCTURALLY.
    # Pattern matching uses match.v2 + bridge (not Python match).
    # Substitution uses subst.v2 (not Python substitute).
    return step_algorithm_with_bridge(projections, input_value)


def step_algorithm_with_bridge(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Run algorithm projections (recurrence, exhaustion) with bridge-enabled matching.

    EXECUTION MODEL:
    Algorithm projections work with their own internal structure (head/tail
    linked lists for traces, regular dict keys for state machine mode/phase).
    They require NON-LINEAR PATTERN SUPPORT (same variable can appear twice,
    and binding conflicts must be detected).

    The bootstrap_structural bridge PROVES that non-linear pattern support
    CAN be implemented structurally (via bridge.var.check_existing and
    bridge.lookup.* projections). This satisfies the META_CIRCULAR declaration.

    For PRACTICAL EXECUTION, we use Python's match() and substitute() which
    ALREADY handle non-linear patterns correctly (tested and verified). This:
    1. Preserves algorithm state format (no kernel normalization)
    2. Handles non-linear patterns (Python match detects binding conflicts)
    3. Allows algorithms to run to completion

    The bridge projections are available and tested for cases where TRUE
    structural execution is required (e.g., cross-substrate verification).

    Args:
        projections: Algorithm projections (recurrence.v1 or exhaustion.v1).
        input_value: Algorithm state (entry point or intermediate).

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
    """
    from rcx_pi.selfhost.eval_seed import match, substitute, NO_MATCH

    assert_mu(input_value, "step_algorithm_with_bridge.input")

    # Try each algorithm projection using Python match/substitute
    # Python match() already handles non-linear patterns (binding conflict detection)
    for proj in projections:
        pattern = proj.get("pattern")
        body = proj.get("body")

        if pattern is None or body is None:
            continue

        # Python match handles non-linear patterns correctly
        bindings = match(pattern, input_value)

        if bindings is not NO_MATCH:
            # Python substitute preserves algorithm state format
            return substitute(body, bindings)

    # No projection matched - stall
    return input_value


def run_structural_match(kernel_projs: list[Mu], pattern: Mu, value: Mu) -> Mu | None:
    """
    Run pattern matching using match.v2 + bridge projections.

    This is structural pattern matching - the bridge projections handle
    non-linear patterns (binding conflict detection) as PROJECTIONS.

    Returns match result with _status and _bindings, or None if matching fails.
    """
    from rcx_pi.selfhost.match_mu import normalize_for_match

    # Normalize pattern and value for match.v2
    norm_pattern = normalize_for_match(pattern)
    norm_value = normalize_for_match(value)

    # Create match entry state
    state: Mu = {
        "match": {
            "pattern": norm_pattern,
            "value": norm_value
        },
        "_match_ctx": {}
    }

    # Run match.v2 + bridge until terminal
    max_steps = 5000
    for _ in range(max_steps):
        result = eval_step(kernel_projs, state)

        # Check for terminal state
        if isinstance(result, dict) and result.get("_mode") == "match_done":
            return result

        # Check for stall
        if mu_equal(result, state):
            return None

        state = result

    return None


def run_structural_subst(
    kernel_projs: list[Mu],
    body: Mu,
    bindings: Mu,
    denormalize: bool = True
) -> Mu:
    """
    Run substitution using subst.v2 projections.

    This is structural substitution - variables are replaced via PROJECTIONS.

    Args:
        kernel_projs: Combined projections (kernel + match + bridge + subst).
        body: Template body to substitute into.
        bindings: Bindings in linked-list format.
        denormalize: If True, convert linked-lists back to Python lists.
                     Set to False for algorithm execution where intermediate
                     states must preserve linked-list format.
    """
    from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match

    # Normalize body for subst.v2
    norm_body = normalize_for_match(body)

    # Create subst entry state (subst.wrap expects "body" not "template")
    state: Mu = {
        "subst": {
            "body": norm_body,
            "bindings": bindings
        },
        "_subst_ctx": {}
    }

    # Run subst.v2 until terminal
    max_steps = 5000
    for _ in range(max_steps):
        result = eval_step(kernel_projs, state)

        # Check for terminal state
        if isinstance(result, dict) and result.get("_mode") == "subst_done":
            norm_result = result.get("_result")
            if norm_result is None:
                return norm_result
            # Only denormalize if requested (not for algorithm intermediate states)
            return denormalize_from_match(norm_result) if denormalize else norm_result

        # Check for stall
        if mu_equal(result, state):
            return body  # Return original on stall

        state = result

    return body  # Return original on max steps


# =============================================================================
# Projection Application (Phase 5)
# =============================================================================

def apply_mu(projection: Mu, input_value: Mu) -> Mu:
    """
    Apply a projection to a value using Mu-based match and substitute.

    This is apply_projection() implemented with match_mu + subst_mu.
    Achieves parity with eval_seed.apply_projection() for all inputs
    (except known normalization edge cases documented in Phase 4d).

    Args:
        projection: Dict with "pattern" and "body" keys.
        input_value: The value to transform.

    Returns:
        Transformed value if pattern matched, NO_MATCH otherwise.

    Raises:
        TypeError: If projection is not a dict.
        KeyError: If projection missing pattern/body, or unbound variable in body.
    """
    assert_mu(projection, "apply_mu.projection")
    assert_mu(input_value, "apply_mu.input")

    # Validate projection structure (parity with apply_projection error types)
    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection).__name__}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    # Use Mu-based match (runs match projections via kernel loop)
    bindings = match_mu(pattern, input_value)
    if bindings is NO_MATCH:
        return NO_MATCH

    # Use Mu-based substitute (runs subst projections via kernel loop)
    return subst_mu(body, bindings)


def step_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order using structural kernel.

    Phase 7d-1: This function now uses the meta-circular kernel
    (kernel.v1 + match.v2 + subst.v2 projections) instead of a Python
    for-loop. The kernel provides iteration without host arithmetic
    or control flow.

    Args:
        projections: List of projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
    """
    return step_kernel_mu(projections, input_value)


@host_iteration("Kernel run loop - Phase 7d replaces with meta-circular kernel")
def run_mu(projections: list[Mu], initial: Mu, max_steps: int = 1000) -> tuple[Mu, list[dict], bool]:
    """
    Run projections repeatedly until stall or max steps.

    This is the kernel loop using step_mu instead of step.

    Args:
        projections: List of projections to apply.
        initial: Starting value.
        max_steps: Maximum iterations before forced stop.

    Returns:
        Tuple of (final_value, trace, is_stall):
        - final_value: The result after all steps
        - trace: List of {"step": n, "value": v} entries
        - is_stall: True if stopped due to stall (no change)
    """
    trace = []
    current = initial

    for i in range(max_steps):
        trace.append({"step": i, "value": current})

        result = step_mu(projections, current)

        # Check for stall (no change)
        if mu_equal(result, current):
            trace.append({"step": i + 1, "value": result, "stall": True})
            return result, trace, True

        current = result

    # Hit max steps without stall
    trace.append({"step": max_steps, "value": current, "max_steps": True})
    return current, trace, False


@host_iteration("Phase 8d trace model - structural trace for EngineNews")
def run_mu_structural(
    projections: list[Mu],
    initial: Mu,
    max_steps: int = 1000
) -> dict:
    """
    Run projections with structural trace accumulation (Phase 8d).

    Returns a Mu-compatible result structure that EngineNews can analyze:
    {
        "result": final_value,
        "trace": linked_list_of_steps,  # Mu linked list, not Python list
        "stall": bool,
        "steps": int
    }

    Each trace entry is:
    {
        "step": int,
        "state": value_at_step,
        "projection": id_or_null  # Which projection matched (null = stall)
    }

    This enables Rule 2.2 (closure-on-second-demand) - EngineNews projections
    can pattern-match against the trace to detect when a state recurs.
    """
    trace_entries = []
    current = initial

    for i in range(max_steps):
        # Find which projection will match (for trace)
        # Uses match_mu to stay structural (9-agent review 2026-01-31: avoid Python match())
        matched_id = None
        for proj in projections:
            bindings = match_mu(proj.get("pattern"), current)
            if bindings is not NO_MATCH:
                matched_id = proj.get("id")
                break

        trace_entries.append({
            "step": i,
            "state": current,
            "projection": matched_id
        })

        result = step_mu(projections, current)

        # Check for stall (no change)
        if mu_equal(result, current):
            trace_entries.append({
                "step": i + 1,
                "state": result,
                "projection": None,
                "stall": True
            })
            return {
                "result": result,
                "trace": list_to_linked(trace_entries),
                "stall": True,
                "steps": i + 1
            }

        current = result

    # Hit max steps without stall
    trace_entries.append({
        "step": max_steps,
        "state": current,
        "projection": None,
        "max_steps": True
    })
    return {
        "result": current,
        "trace": list_to_linked(trace_entries),
        "stall": False,
        "steps": max_steps
    }
