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

import json

from .eval_seed import NO_MATCH, host_iteration, step as eval_step
from .match_mu import match_mu, normalize_for_match, denormalize_from_match
from .subst_mu import subst_mu
from .mu_type import Mu, assert_mu, mu_equal
from .kernel import get_step_budget
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

# Gate 3 policy (minimal reserved set):
# Some algorithm-internal underscore keys are intentionally not in KERNEL_RESERVED_FIELDS
# because they are confined to algorithm state payloads under entrypoint subtrees and
# would over-constrain domain representations if globally reserved. This allowlist is
# locked by tests/structural/test_reserved_field_policy.py to prevent silent drift.
ALGORITHM_INTERNAL_UNRESERVED_FIELDS = frozenset({  # AST_OK: security policy allowlist
    "_closure",
    "_frozen_check",
    "_head",
    "_maxsteps",
    "_op_ids",
    "_operator",
    "_other",
    "_rest",
    "_state",
    "_tau_op",
    "_tau_operator",
    "_trace",
})

# Gate 4 prep (2026-02-07): strict allowlist for algorithm-runtime kernel entry.
# This mode is only for trusted internal algorithm execution (recurrence/exhaustion)
# and is narrower than "allow all reserved fields". Unknown underscore fields fail closed.
ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS = (
    ALGORITHM_ENTRYPOINT_KEYS
    | ALGORITHM_INTERNAL_UNRESERVED_FIELDS
    | frozenset((
        "_check_list",
        "_current",
        "_frozen",
        "_mode",
        "_operator_ids",
        "_phase",
        "_result",
        "_seen",
        "_stall",
        "_step",
        "_tau_step",
        "_type",
    ))
)


def _iter_normalized_dict_pairs(value: Mu) -> list[tuple[str, Mu]] | None:
    """
    Return list of (key, value) if value is a normalized dict encoding.

    Normalized dict format (from normalize_for_match):
      {"_type":"dict","head":{"head":<key>,"tail":{"head":<val>,"tail":null}},"tail": ...}

    Returns None if structure doesn't match normalized dict encoding.

    Gate 3 Security: This allows validate_no_kernel_reserved_fields to check
    keys inside normalized dict representations, preventing bypass attacks.
    """
    if not isinstance(value, dict):
        return None
    # Empty dict sentinel: {"_type": "dict"}
    if set(value.keys()) == {"_type"}:
        return [] if value.get("_type") == "dict" else None
    if "_type" in value and value.get("_type") != "dict":
        return None
    if "head" not in value or "tail" not in value:
        return None

    pairs: list[tuple[str, Mu]] = []
    current: Mu = value
    visited_nodes: set[int] = set()
    while True:
        if not isinstance(current, dict):
            return None
        # Security hardening: reject cyclic structures to avoid infinite loops.
        node_id = id(current)
        if node_id in visited_nodes:
            return None
        visited_nodes.add(node_id)
        if "_type" in current and current.get("_type") != "dict":
            return None
        if "head" not in current or "tail" not in current:
            return None
        kv = current.get("head")
        if not isinstance(kv, dict):
            return None
        if set(kv.keys()) != {"head", "tail"}:
            return None
        key = kv.get("head")
        if not isinstance(key, str):
            return None
        kv_tail = kv.get("tail")
        if not isinstance(kv_tail, dict):
            return None
        if set(kv_tail.keys()) != {"head", "tail"}:
            return None
        if kv_tail.get("tail") is not None:
            return None
        val = kv_tail.get("head")
        pairs.append((key, val))
        tail = current.get("tail")
        if tail is None:
            break
        current = tail
    return pairs


def _looks_like_normalized_dict_candidate(value: Mu) -> bool:
    """
    Check whether a value appears to be a normalized dict encoding candidate.

    This is intentionally conservative so regular domain objects are not
    misclassified. If this returns True and pair iteration fails, validators
    should fail closed to prevent encoded-key bypasses.
    """
    if not isinstance(value, dict):
        return False
    if value.get("_type") == "dict":
        return True
    if "head" not in value or "tail" not in value:
        return False
    kv = value.get("head")
    if not isinstance(kv, dict):
        return False
    # Candidate only when head itself looks like a kv-pair node.
    if set(kv.keys()) != {"head", "tail"}:
        return False
    key = kv.get("head")
    if not isinstance(key, str):
        return False
    kv_tail = kv.get("tail")
    return isinstance(kv_tail, dict)


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
        # Gate 3 Security: Check normalized dict encoding (keys stored as values).
        # Without this, reserved fields in normalized dicts bypass validation.
        pairs = _iter_normalized_dict_pairs(value)
        if pairs is not None:
            for key, val in pairs:
                entering_algorithm = key in ALGORITHM_ENTRYPOINT_KEYS
                if key in KERNEL_RESERVED_FIELDS and not _in_algorithm_subtree:
                    raise ValueError(
                        f"SECURITY: {context} cannot contain kernel-reserved field: {key}. "
                        f"Reserved fields: {sorted(KERNEL_RESERVED_FIELDS)}"
                    )
                validate_no_kernel_reserved_fields(
                    val, context, _depth + 1,
                    _in_algorithm_subtree=(_in_algorithm_subtree or entering_algorithm)
                )
            return
        if _looks_like_normalized_dict_candidate(value):
            raise ValueError(
                f"SECURITY: {context} contains malformed normalized dict encoding. "
                "Failing closed to prevent reserved-field bypass."
            )

        # Regular dict: check keys directly
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


def validate_algorithm_runtime_fields(
    value: Mu,
    context: str = "input",
    _depth: int = 0,
) -> None:
    """
    Validate trusted algorithm runtime state at kernel entry.

    Gate 4 prep: algorithm execution requires underscore-heavy state keys at the
    top level (for example `_mode`, `_phase`) that domain validation rejects.
    This validator is stricter than a blanket bypass:
    - Unknown underscore fields are rejected (fail closed).
    - Underscore keys inside normalized dict encodings are also checked.

    This mode is for internal algorithm execution only.
    """
    MAX_VALIDATION_DEPTH = 100
    if _depth > MAX_VALIDATION_DEPTH:
        raise ValueError(
            f"SECURITY: {context} exceeded maximum validation depth ({MAX_VALIDATION_DEPTH}). "
            f"Possible deeply nested attack structure."
        )

    if isinstance(value, dict):
        pairs = _iter_normalized_dict_pairs(value)
        if pairs is not None:
            for key, val in pairs:
                if key.startswith("_") and key not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
                    raise ValueError(
                        f"SECURITY: {context} contains unsupported algorithm underscore field: {key}. "
                        f"Allowed: {sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)}"
                    )
                validate_algorithm_runtime_fields(val, context, _depth + 1)
            return
        if _looks_like_normalized_dict_candidate(value):
            raise ValueError(
                f"SECURITY: {context} contains malformed normalized dict encoding. "
                "Failing closed."
            )

        for key, val in value.items():
            if isinstance(key, str) and key.startswith("_"):
                if key not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
                    raise ValueError(
                        f"SECURITY: {context} contains unsupported algorithm underscore field: {key}. "
                        f"Allowed: {sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)}"
                    )
            validate_algorithm_runtime_fields(val, context, _depth + 1)
    elif isinstance(value, list):
        for item in value:
            validate_algorithm_runtime_fields(item, context, _depth + 1)


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

    Returns a deep copy to prevent callers from mutating the cache.
    (Adversary finding: shallow copy allows cache poisoning via dict mutation)

    Returns:
        Combined list of kernel, match, and subst projections.
    """
    global _combined_kernel_cache
    if _combined_kernel_cache is not None:
        # Deep copy via JSON round-trip (Mu is JSON-compatible)
        return json.loads(json.dumps(_combined_kernel_cache))

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
    # Deep copy via JSON round-trip (Mu is JSON-compatible)
    return json.loads(json.dumps(_combined_kernel_cache))


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


def _validate_combined_bridge_ordering(projections: list[Mu]) -> None:
    """
    Validate critical ordering invariants for bridge-enabled kernel composition.

    These checks are runtime guardrails for future seed/config changes:
    - Bridge projections must exist.
    - Bridge variable interception must run before match.var.
    - Bridge lookup success must run before lookup conflict branch.
    """
    ids: list[Mu] = []
    for proj in projections:
        if isinstance(proj, dict):
            ids.append(proj.get("id"))

    required_bridge_ids = (
        "bridge.var.check_existing",
        "bridge.lookup.found_same",
        "bridge.lookup.found_different",
        "bridge.lookup.not_found_yet",
        "bridge.lookup.not_found",
    )
    missing: list[str] = []
    for proj_id in required_bridge_ids:
        if proj_id not in ids:
            missing.append(proj_id)
    if missing:
        raise ValueError(
            "SECURITY: Bridge ordering invariant failed; missing bridge projections: "
            f"{missing}"
        )

    if "match.var" not in ids:
        raise ValueError("SECURITY: Bridge ordering invariant failed; missing match.var")

    match_var_idx = ids.index("match.var")
    for bridge_id in required_bridge_ids:
        bridge_idx = ids.index(bridge_id)
        if bridge_idx >= match_var_idx:
            raise ValueError(
                "SECURITY: Bridge ordering invariant failed; "
                f"{bridge_id} (index {bridge_idx}) must be before match.var "
                f"(index {match_var_idx})"
            )

    found_same_idx = ids.index("bridge.lookup.found_same")
    found_diff_idx = ids.index("bridge.lookup.found_different")
    if found_same_idx > found_diff_idx:
        raise ValueError(
            "SECURITY: Bridge ordering invariant failed; "
            "bridge.lookup.found_same must precede bridge.lookup.found_different"
        )


def load_combined_kernel_with_bridge_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + bootstrap_structural + subst.v2 projections.

    This variant uses bootstrap_structural.v1 which provides non-linear pattern
    support (binding conflict detection) as structural projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns a deep copy to prevent callers from mutating the cache.
    (Adversary finding: shallow copy allows cache poisoning via dict mutation)

    Required for META_CIRCULAR seeds:
    - recurrence.v1.json (uses non-linear patterns for state equality)
    - exhaustion.v1.json (uses non-linear patterns for operator equality)

    Returns:
        Combined list of kernel, match.v2, bootstrap_structural, and subst projections.
    """
    global _combined_kernel_bridge_cache
    if _combined_kernel_bridge_cache is not None:
        _validate_combined_bridge_ordering(_combined_kernel_bridge_cache)
        # Deep copy via JSON round-trip (Mu is JSON-compatible)
        return json.loads(json.dumps(_combined_kernel_bridge_cache))

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
    _validate_combined_bridge_ordering(_combined_kernel_bridge_cache)
    # Deep copy via JSON round-trip (Mu is JSON-compatible)
    return json.loads(json.dumps(_combined_kernel_bridge_cache))


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
def step_kernel_mu(
    projections: list[Mu],
    input_value: Mu,
    *,
    kernel_mode: str = "core",
    validation_mode: str = "domain",
) -> Mu:
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
        kernel_mode: `core` uses kernel+match.v2+subst.v2. `bridge` uses
            kernel+bridge+match.v2+subst.v2.
        validation_mode: `domain` uses reserved-field protection for untrusted
            domain inputs. `algorithm_runtime` allows trusted algorithm state
            with strict underscore allowlisting.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
        ValueError: If input contains kernel-reserved fields (security).
    """
    assert_mu(input_value, "step_kernel_mu.input")

    if validation_mode == "domain":
        validator = validate_no_kernel_reserved_fields
    elif validation_mode == "algorithm_runtime":
        validator = validate_algorithm_runtime_fields
    else:
        raise ValueError(
            "SECURITY: invalid validation_mode. Expected 'domain' or 'algorithm_runtime', "
            f"got: {validation_mode}"
        )

    # SECURITY: Validate input at the selected boundary mode
    validator(input_value, "step_kernel_mu input")

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
                validator(proj["pattern"], f"projection[{i}].pattern")
            if "body" in proj:
                validator(proj["body"], f"projection[{i}].body")

    # Load combined kernel projections
    if kernel_mode == "core":
        kernel_projs = load_combined_kernel_projections()
    elif kernel_mode == "bridge":
        kernel_projs = load_combined_kernel_with_bridge_projections()
    else:
        raise ValueError(
            "SECURITY: invalid kernel_mode. Expected 'core' or 'bridge', "
            f"got: {kernel_mode}"
        )

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
    budget = get_step_budget()
    started_budget = False
    if not budget.is_active():
        budget.start()
        started_budget = True

    # Phase 8b: Simplified mechanical loop - no semantic decisions inside
    try:
        for _ in range(max_steps):
            # Account for kernel-driver work in the shared global budget.
            budget.consume(1)
            result = eval_step(kernel_projs, current)

            # Terminal state check - simple structural marker detection
            if is_kernel_terminal(result):
                output = extract_kernel_result(result, input_value)
                validator(output, "step_kernel_mu output")
                return output

            # Stall check - no change means no progress
            # Skip for intermediate kernel states (they have deep nested structures
            # and are mid-execution by definition, not stalls)
            if not is_kernel_intermediate(result) and mu_equal(result, current):
                validator(input_value, "step_kernel_mu output")
                return input_value

            current = result

        # Max steps exceeded - return original input (stall)
        validator(input_value, "step_kernel_mu output")
        return input_value
    finally:
        if started_budget:
            budget.stop()


def run_algorithm_meta_circular(
    projections: list[Mu],
    input_value: Mu,
    *,
    execution_mode: str = "structural",
) -> Mu:
    """
    Run an internal algorithm (recurrence, exhaustion).

    Gate 4 cutover:
    - Default mode (`execution_mode="structural"`) runs through step_kernel_mu
      with bridge support and algorithm-runtime validation.
    - Bootstrap execution is retained only as an explicit debug fallback
      (`execution_mode="bootstrap"`).

    Security and parity properties:
    - Structural mode uses `kernel_mode="bridge"` to keep non-linear matching
      behavior aligned with recurrence/exhaustion requirements.
    - Structural mode uses `validation_mode="algorithm_runtime"` so trusted
      underscore-heavy algorithm state is allowlisted, while unknown underscore
      fields still fail closed.
    - Bootstrap fallback remains available for controlled debugging only.

    Args:
        projections: Algorithm projections (recurrence.v1 or exhaustion.v1).
        input_value: Algorithm entry point or intermediate state.
        execution_mode: `structural` (default) or `bootstrap` (debug fallback).

    Returns:
        Algorithm result after single projection application.

    Raises:
        ValueError: If execution_mode is not recognized.
    """
    assert_mu(input_value, "run_algorithm_meta_circular.input")

    if execution_mode == "structural":
        return step_kernel_mu(
            projections,
            input_value,
            kernel_mode="bridge",
            validation_mode="algorithm_runtime",
        )
    if execution_mode == "bootstrap":
        return step_algorithm_with_bridge(projections, input_value)

    raise ValueError(
        "SECURITY: invalid execution_mode. Expected 'structural' or 'bootstrap', "
        f"got: {execution_mode}"
    )


def step_algorithm_with_bridge(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Run algorithm projections (recurrence, exhaustion) with bridge-enabled matching.

    EXECUTION MODEL (Gate 3):
    Algorithm seeds now use NORMALIZED patterns (linked-list dict format).
    Input is normalized before matching so patterns can match correctly.
    Output is DENORMALIZED for backwards compatibility with Kernel and tests.
    (Gate 4+ may transition to fully normalized internal state.)

    Algorithm projections require NON-LINEAR PATTERN SUPPORT (same variable
    can appear twice, and binding conflicts must be detected). Python's
    match() handles this correctly.

    The bootstrap_structural bridge PROVES that non-linear pattern support
    CAN be implemented structurally (via bridge.var.check_existing and
    bridge.lookup.* projections). This satisfies the META_CIRCULAR declaration.

    Args:
        projections: Algorithm projections (recurrence.v1 or exhaustion.v1).
        input_value: Algorithm state (entry point or intermediate).

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
    """
    from rcx_pi.selfhost.eval_seed import step
    from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match

    assert_mu(input_value, "step_algorithm_with_bridge.input")
    validate_algorithm_runtime_fields(input_value, "step_algorithm_with_bridge input")
    validate_kernel_projections_first(projections)

    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            continue
        proj_id = proj.get("id", "")
        if isinstance(proj_id, str) and proj_id.startswith("kernel."):
            raise ValueError(
                f"SECURITY: step_algorithm_with_bridge expects algorithm/domain projections only, "
                f"got kernel projection at index {i}: {proj_id}"
            )
        if "pattern" in proj:
            validate_algorithm_runtime_fields(
                proj["pattern"], f"step_algorithm_with_bridge projection[{i}].pattern"
            )
        if "body" in proj:
            validate_algorithm_runtime_fields(
                proj["body"], f"step_algorithm_with_bridge projection[{i}].body"
            )

    # Gate 3: Normalize input for matching against normalized seed patterns.
    # normalize_for_match is idempotent, so already-normalized state is unchanged.
    normalized_input = normalize_for_match(input_value)

    # Single bootstrap step: preserves first-match-wins semantics without
    # embedding a projection-application loop in this helper.
    normalized_result = step(projections, normalized_input)
    if mu_equal(normalized_result, normalized_input):
        return input_value

    result = denormalize_from_match(normalized_result)
    validate_algorithm_runtime_fields(result, "step_algorithm_with_bridge output")
    return result


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

    validate_no_kernel_reserved_fields(input_value, "apply_mu input")
    validate_no_kernel_reserved_fields(pattern, "apply_mu pattern")
    validate_no_kernel_reserved_fields(body, "apply_mu body")

    # Use Mu-based match (runs match projections via kernel loop)
    bindings = match_mu(pattern, input_value)
    if bindings is NO_MATCH:
        return NO_MATCH

    # Use Mu-based substitute (runs subst projections via kernel loop)
    result = subst_mu(body, bindings)
    validate_no_kernel_reserved_fields(result, "apply_mu output")
    return result


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
    assert_mu(initial, "run_mu_structural.initial")
    validate_no_kernel_reserved_fields(initial, "run_mu_structural initial")
    validate_kernel_projections_first(projections)
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            continue
        if "pattern" in proj:
            validate_no_kernel_reserved_fields(
                proj["pattern"], f"run_mu_structural projection[{i}].pattern"
            )
        if "body" in proj:
            validate_no_kernel_reserved_fields(
                proj["body"], f"run_mu_structural projection[{i}].body"
            )

    budget = get_step_budget()
    started_budget = False
    if not budget.is_active():
        budget.start()
        started_budget = True

    trace_entries = []
    current = initial

    try:
        for i in range(max_steps):
            # Single-pass structural step: identify first match and apply it once.
            # This avoids the previous double-evaluation path (pre-match + step_mu).
            matched_id = None
            result = current
            for proj in projections:
                if not isinstance(proj, dict):
                    continue
                pattern = proj.get("pattern")
                body = proj.get("body")
                if pattern is None or body is None:
                    continue
                bindings = match_mu(pattern, current)
                if bindings is not NO_MATCH:
                    matched_id = proj.get("id")
                    try:
                        result = subst_mu(body, bindings)
                    except KeyError:
                        # Parity with step_mu: unresolved substitution stalls and
                        # returns original input rather than bubbling an exception.
                        result = current
                    break

            validate_no_kernel_reserved_fields(result, "run_mu_structural output")
            trace_entries.append({
                "step": i,
                "state": current,
                "projection": matched_id
            })

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
    finally:
        if started_budget:
            budget.stop()
