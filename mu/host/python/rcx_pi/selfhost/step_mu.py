"""
Step as Mu Projections - Phase 7d Self-Hosting

This module implements the step function using Mu projections instead of
Python recursion. It achieves parity with eval_seed.step() using match_mu
and subst_mu.

Phase 7d: Meta-circular kernel
- step_mu() now uses structural kernel projections (kernel.v1 + match.v2 + subst.v2)
- Kernel iteration uses linked-list cursor via host_iteration(), not arithmetic
- Engine pipeline (trampoline) and Boot1 recursive path both use _step_trusted for stepping

TERMINOLOGY NOTE:
- kernel.v1.json = structural kernel (7 Mu projections for iteration)
- Kernel class (kernel.py) = Python scaffolding (hash, trace, dispatch)

This module uses kernel.v1.json projections for structural iteration.
The Kernel class provides boundary scaffolding (hash, trace, dispatch)
while step_kernel_mu() drives the structural kernel.

SECURITY: Projection order is security-critical. When combining kernel
projections with domain projections (Phase 7+), kernel projections MUST
run first to prevent domain data from forging kernel state.

See mu/docs/core/SelfHosting.v0.md for design.
See mu/docs/core/MetaCircularKernel.v0.md for kernel design.
"""

from __future__ import annotations

import json

from .eval_seed import NO_MATCH, host_iteration, step as eval_step, _step_trusted
from .match_mu import match_mu, normalize_for_match, denormalize_from_match
from .subst_mu import subst_mu
from .mu_type import Mu, assert_mu, is_mu, mu_hash, mu_hash_cached, mu_hash_control, mu_hash_control_cached, MAX_MU_DEPTH, MAX_MU_WIDTH
from .kernel import get_step_budget
from collections.abc import Callable
from .seed_integrity import get_seed_path, load_verified_seed, MU_SEED_LOCATIONS, SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS
from .projection_loader import make_projection_loader

# Cached loader for terminal classification seed (structural displacement of classify/exit-reason logic)
_load_tc_projections, _clear_tc_proj_cache = make_projection_loader("terminal_classify.v1.json")
# Cached loader for hemisphere seed (A9: hemisphere key authority displacement)
_load_hemi_projections, _clear_hemi_proj_cache = make_projection_loader("hemispheres.v1.json")


# =============================================================================
# Typed Engine Error (parity with JS RcxError)
# =============================================================================

class RcxEngineError(RuntimeError):
    """Engine error with machine-readable error_code (mirrors JS RcxError).

    Subclasses RuntimeError so existing ``except RuntimeError`` and
    ``pytest.raises(RuntimeError, match=...)`` patterns remain valid.
    """

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


# Terminal shape key sets — seed-derived from terminal_classify.v1.json (A6 displacement).
# Authority lives in seed projections, not hardcoded frozensets.
_tc_key_sets_cache: dict | None = None


def _load_tc_key_sets() -> dict:  # AST_OK: infra — seed-derived terminal key sets
    """Derive terminal key sets from terminal_classify.v1.json seed (cached).

    Returns a fresh copy of {projection_id: frozenset(keys)} each call.
    Callers cannot mutate the internal cache (defensive copy pattern,
    same as projection_loader.py). Values are frozensets (already immutable).
    Only includes projections using the ``_tc`` wrapper (tc.recurrence,
    tc.exhaustion, tc.engine).
    """
    global _tc_key_sets_cache
    if _tc_key_sets_cache is not None:
        return dict(_tc_key_sets_cache)
    projs = _load_tc_projections()
    result = {}
    for p in projs:
        pat = p.get("pattern") or {}
        if "_tc" in pat:
            result[p["id"]] = frozenset(pat["_tc"].keys())
    _tc_key_sets_cache = result
    return dict(_tc_key_sets_cache)


def _clear_tc_cache() -> None:
    """Clear both projection and key-set caches (for testing)."""
    global _tc_key_sets_cache
    _clear_tc_proj_cache()
    _tc_key_sets_cache = None


# Hemisphere key sets — seed-derived from hemispheres.v1.json (A9 displacement).
# Authority lives in hemisphere.add.* projection IDs.
# _EXPECTED_HEMISPHERE_KEYS is a fail-closed safety guard (duplicate literals),
# NOT authority-of-truth. Authority is seed-derived; expected set catches corruption.
_hemi_key_sets_cache: tuple | None = None
_EXPECTED_HEMISPHERE_KEYS = frozenset({"r_null", "r_inf", "r_a", "lobes", "sink"})  # AST_OK: constant — fail-closed guard


def _load_hemisphere_keys() -> tuple[tuple[str, ...], frozenset[str]]:  # AST_OK: infra — seed-derived hemisphere keys
    """Derive hemisphere key order + frozenset from hemispheres.v1.json (cached).

    Extracts keys from hemisphere.add.* projection IDs. Projection order = key order.
    Fail-closed: raises RcxEngineError if seed yields unexpected key set.
    """
    global _hemi_key_sets_cache
    if _hemi_key_sets_cache is not None:
        return _hemi_key_sets_cache
    projs = _load_hemi_projections()
    prefix = "hemisphere.add."
    key_order = tuple(p["id"][len(prefix):] for p in projs if p["id"].startswith(prefix))
    key_set = frozenset(key_order)
    # Fail-closed invariants (A9 Requirement A)
    if len(key_order) != 5:
        raise RcxEngineError("input.shape_mismatch",
            f"hemisphere seed invariant: expected 5 keys, got {len(key_order)}")
    if len(key_order) != len(key_set):
        raise RcxEngineError("input.shape_mismatch",
            f"hemisphere seed invariant: duplicate keys in {key_order}")
    if key_set != _EXPECTED_HEMISPHERE_KEYS:
        raise RcxEngineError("input.shape_mismatch",
            f"hemisphere seed invariant: expected {sorted(_EXPECTED_HEMISPHERE_KEYS)}, got {sorted(key_set)}")
    _hemi_key_sets_cache = (key_order, key_set)
    return _hemi_key_sets_cache


def _get_hemisphere_key_order() -> tuple[str, ...]:  # AST_OK: infra
    """Return hemisphere key order tuple (seed-derived, cached)."""
    return _load_hemisphere_keys()[0]


def _get_hemisphere_keys() -> frozenset[str]:  # AST_OK: infra
    """Return hemisphere key frozenset (seed-derived, cached)."""
    return _load_hemisphere_keys()[1]


def _clear_hemi_cache() -> None:
    """Clear hemisphere projection and key caches (for testing)."""
    global _hemi_key_sets_cache
    _clear_hemi_proj_cache()
    _hemi_key_sets_cache = None


# Terminal kind enum — unified classification of all terminal states.
# Every dict result falls into exactly one kind. Pure structural check.
TERMINAL_KINDS = frozenset({  # AST_OK: constant — terminal classification enum
    "kernel_done",             # {_mode: "done", _result: ..., _stall: ...}
    "recurrence_terminal",     # {closure_detected, final_result, tau_step}
    "exhaustion_terminal",     # {action, exhaustion_detected, frozen, operator_to_freeze}
    "engine_terminal",         # 8-key unwrapped engine output
    "non_terminal",            # none of the above
})


def classify_terminal_kind(value) -> str:  # AST_OK: infra — unified terminal classification
    """Classify a value into exactly one terminal kind.

    Returns one of TERMINAL_KINDS. Pure structural check — no side effects.
    Priority: kernel_done > recurrence_terminal > exhaustion_terminal > engine_terminal > non_terminal.
    Cross-substrate parity: must match JS classifyTerminalKind() exactly.

    Structural displacement (Wave 25): classification logic now delegated to
    terminal_classify.v1.json seed projections via eval_step(). kernel_done
    stays host-side (requires key-membership check, not exact-key-match).

    Key-set prefilter (Wave 25 fix): only invoke eval_step when the dict's
    key set matches a known terminal shape. Engine-internal state with deep
    nesting never reaches eval_step/assert_mu, preventing pathological hangs.
    """
    if not isinstance(value, dict):
        return "non_terminal"
    # Kernel terminal: {_mode: "done", _result, _stall} — host-side (key-membership)
    if value.get("_mode") == "done" and "_result" in value and "_stall" in value:
        return "kernel_done"
    # Key-set prefilter: only candidate shapes reach the seed path.
    # This avoids eval_step (and its assert_mu walk) on engine-internal
    # state dicts that can be deeply nested.
    keys = frozenset(value.keys())
    if keys not in _load_tc_key_sets().values():
        return "non_terminal"
    # Structural seed classification via projection matching
    tc_projs = _load_tc_projections()
    result = eval_step(tc_projs, {"_tc": value})
    return result if isinstance(result, str) else "non_terminal"


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
# is_kernel_intermediate() checks for these to skip stall detection on kernel
# states, but domain data with these keys cannot forge kernel state because
# kernel projections require specific patterns.
#
# Gate 4 hardening (2026-02-07):
# Domain-mode validation is strict: kernel-reserved fields are rejected everywhere.
# Algorithm runtime uses a separate allowlist validator.
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
    "_lookup_name", "_lookup_value", "_lookup_bindings", "_original_bindings",
    # Engine pipeline dispatch field (Boot1 P2 hardening, 2026-02-14)
    "_run_engine",
    # Boot1 recursive loop contract field (Boot1 P3 hardening, 2026-02-14)
    "_tail_call",
    # Boundary effect dispatch field (adversary hardening, 2026-02-24)
    "_boundary_request"
})

# Algorithm entrypoint keys used by trusted algorithm runtime payloads.
ALGORITHM_ENTRYPOINT_KEYS = frozenset({  # AST_OK: security whitelist - frozen constant
    "_detect_closure",      # Recurrence algorithm entry point
    "_detect_exhaustion",   # Exhaustion algorithm entry point
})

# Gate 3 policy (minimal reserved set):
# Some algorithm-internal underscore keys are intentionally not in KERNEL_RESERVED_FIELDS
# because they are confined to algorithm state payloads under entrypoint subtrees and
# would over-constrain domain representations if globally reserved. This allowlist is
# locked by tests/test_gate4_algorithm_runtime_fuzzer.py and
# tests/structural/test_gate3_security_fix.py to prevent silent drift.
ALGORITHM_INTERNAL_UNRESERVED_FIELDS = frozenset({  # AST_OK: security policy allowlist
    "_closure",
    "_frozen_check",
    "_head",
    "_m",         # sentinel-skip: max_steps value (exhaustion.v1.json v1.3.0)
    "_maxsteps",
    "_op_ids",
    "_operator",
    "_other",
    "_rest",
    "_s",         # sentinel-skip: state value (exhaustion.v1.json v1.3.0)
    "_st",        # sentinel-skip: step value (exhaustion.v1.json v1.3.0)
    "_state",
    "_stl",       # sentinel-skip: stall value (exhaustion.v1.json v1.3.0)
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
        "_check_hash",
        "_check_list",
        "_current",
        "_frozen",
        "_mode",
        "_operator_ids",
        "_phase",
        "_result",
        "_seen",
        "_stall",
        "_state_hash",
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
    max_steps = MAX_MU_WIDTH
    steps = 0
    while True:
        steps += 1
        if steps > max_steps:
            return None
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
    keys = set(value.keys())
    if value.get("_type") == "dict":
        has_only_type = len(keys) == 1 and "_type" in keys
        has_typed_node = len(keys) == 3 and "_type" in keys and "head" in keys and "tail" in keys
        return has_only_type or has_typed_node
    if not (len(keys) == 2 and "head" in keys and "tail" in keys):
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
    if not isinstance(kv_tail, dict):
        return False
    if set(kv_tail.keys()) != {"head", "tail"}:
        return False
    tail = value.get("tail")
    return tail is None or isinstance(tail, dict)


_MAX_VALIDATION_DEPTH = MAX_MU_DEPTH  # AST_OK: infra — must cover full allowed depth (was 100, misses 100-300)


def _walk_and_validate(
    value: Mu,
    key_checker: Callable[[str], str | None],
    context: str,
    _depth: int = 0,
) -> None:
    """
    Walk a Mu value tree and validate keys via key_checker.

    Shared traversal for validate_no_kernel_reserved_fields and
    validate_algorithm_runtime_fields (expert finding: ~60% duplicate boilerplate).

    Args:
        value: The Mu value to validate.
        key_checker: Function that takes a key string and returns an error
            message if invalid, or None if valid.
        context: Description for error messages.
        _depth: Internal recursion depth tracker.
    Raises:
        ValueError: If key_checker rejects a key, depth exceeded, or
            malformed normalized dict detected.
    """
    if _depth > _MAX_VALIDATION_DEPTH:
        raise ValueError(
            f"SECURITY: {context} exceeded maximum validation depth ({_MAX_VALIDATION_DEPTH}). "
            f"Possible deeply nested attack structure."
        )

    if isinstance(value, dict):
        pairs = _iter_normalized_dict_pairs(value)
        if pairs is not None:
            for key, val in pairs:
                err = key_checker(key)
                if err:
                    raise ValueError(f"SECURITY: {context} {err}")
                _walk_and_validate(val, key_checker, context, _depth + 1)
            return
        if _looks_like_normalized_dict_candidate(value):
            raise ValueError(
                f"SECURITY: {context} contains malformed normalized dict encoding. "
                "Failing closed to prevent reserved-field bypass."
            )
        for key, val in value.items():
            err = key_checker(key)
            if err:
                raise ValueError(f"SECURITY: {context} {err}")
            _walk_and_validate(val, key_checker, context, _depth + 1)
    elif isinstance(value, list):
        for item in value:
            _walk_and_validate(item, key_checker, context, _depth + 1)


def _check_kernel_reserved(key: str) -> str | None:
    """Key checker: reject kernel-reserved fields."""
    if key in KERNEL_RESERVED_FIELDS:
        return (
            f"cannot contain kernel-reserved field: {key}. "
            f"Reserved fields: {sorted(KERNEL_RESERVED_FIELDS)}"
        )
    return None


def _check_algorithm_runtime(key: str) -> str | None:
    """Key checker: reject unknown underscore fields."""
    if isinstance(key, str) and key.startswith("_"):
        if key not in ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS:
            return (
                f"contains unsupported algorithm underscore field: {key}. "
                f"Allowed: {sorted(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS)}"
            )
    return None


def validate_no_kernel_reserved_fields(
    value: Mu,
    context: str = "input",
    _depth: int = 0,
) -> None:
    """
    Validate that a value does not contain kernel-reserved fields (DEEP).

    SECURITY: Prevents domain data from forging kernel state by including
    fields like _mode, _match_ctx, etc. Called at kernel entry point
    (step_kernel_mu) to ensure domain inputs are clean at all depths.
    """
    _walk_and_validate(value, _check_kernel_reserved, context, _depth)


def validate_algorithm_runtime_fields(
    value: Mu,
    context: str = "input",
    _depth: int = 0,
) -> None:
    """
    Validate trusted algorithm runtime state at kernel entry.

    Gate 4 prep: algorithm execution requires underscore-heavy state keys
    at the top level. This validator is stricter than a blanket bypass:
    unknown underscore fields are rejected (fail closed).
    """
    _walk_and_validate(value, _check_algorithm_runtime, context, _depth)


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
    for item in reversed(items):  # @host_iteration: list-to-linked-list conversion (parity with JS listToLinked)
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


def _load_combined_kernel_projections_shared() -> list[Mu]:
    """
    Private: populate and return the shared kernel projection cache.

    Internal trusted-path only. The returned list is the live module-level
    cache — callers MUST NOT mutate it. Used by step_kernel_mu where
    eval_step is verified read-only (no projection mutation).

    F-39: This helper restricts shared-cache access to private internal use.
    Public callers use load_combined_kernel_projections() which returns copies.
    """
    global _combined_kernel_cache
    if _combined_kernel_cache is not None:
        return _combined_kernel_cache

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
    return _combined_kernel_cache


def load_combined_kernel_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + subst.v2 projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns a deep copy. Callers may freely mutate the returned list
    without affecting the internal cache or other callers.

    Returns:
        Combined list of kernel, match, and subst projections.
    """
    return json.loads(json.dumps(_load_combined_kernel_projections_shared()))


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
        else:
            raise ValueError(
                f"SECURITY: Non-dict projection in bridge ordering validation: {type(proj).__name__}"
            )

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


def _load_combined_kernel_with_bridge_projections_shared() -> list[Mu]:
    """
    Private: populate and return the shared bridge kernel projection cache.

    Internal trusted-path only. The returned list is the live module-level
    cache — callers MUST NOT mutate it. Used by step_kernel_mu where
    eval_step is verified read-only (no projection mutation).

    F-39: This helper restricts shared-cache access to private internal use.
    Public callers use load_combined_kernel_with_bridge_projections() which
    returns copies.
    """
    global _combined_kernel_bridge_cache
    if _combined_kernel_bridge_cache is not None:
        return _combined_kernel_bridge_cache

    # Use mu/ as canonical location via get_seed_path()
    kernel_seed = load_verified_seed(get_seed_path("kernel.v1.json"))
    match_seed = load_verified_seed(get_seed_path("match.v2.json"))
    bridge_seed = load_verified_seed(get_seed_path("bootstrap_structural.v1.json"))
    subst_seed = load_verified_seed(get_seed_path("subst.v2.json"))

    # SECURITY: Kernel projections MUST come first
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
    return _combined_kernel_bridge_cache


def load_combined_kernel_with_bridge_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + bootstrap_structural + subst.v2 projections.

    This variant uses bootstrap_structural.v1 which provides non-linear pattern
    support (binding conflict detection) as structural projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns a deep copy. Callers may freely mutate the returned list
    without affecting the internal cache or other callers.

    Required for META_CIRCULAR seeds:
    - recurrence.v1.json (uses non-linear patterns for state equality)
    - exhaustion.v1.json (uses non-linear patterns for operator equality)

    Returns:
        Combined list of kernel, match.v2, bootstrap_structural, and subst projections.
    """
    return json.loads(json.dumps(_load_combined_kernel_with_bridge_projections_shared()))


# =============================================================================
# Kernel Terminal Detection (Phase 8b)
# =============================================================================


def is_kernel_terminal(result: Mu) -> bool:
    """
    Check if result is in kernel terminal state.

    Terminal state is: {"_mode": "done", "_result": ..., "_stall": ...}
    Delegates to classify_terminal_kind (host-side kernel_done check).
    """
    return classify_terminal_kind(result) == "kernel_done"


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
    We skip the stall check for these because:
    1. They may have deeply nested linked-list structures
    2. They're intermediate by definition - no comparison needed

    Phase 8b: This prevents stall detection from being called on kernel internals.
    """
    if not isinstance(result, dict):
        return False

    # Kernel internal fields indicate mid-execution
    # Use tuple for determinism (avoid set literal)
    # SECURITY FIX (9-agent round 2): Only check underscore-prefixed fields.
    # Generic keys 'match' and 'subst' removed - domain data can legitimately
    # contain these, and checking for them bypasses stall detection.
    # See KERNEL_RESERVED_FIELDS declaration and its preceding comment.
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


def make_undefined_motif(op: str, lhs, rhs, cause: str, details=None) -> dict:
    """Create a canonical undefined-result motif (NorthStarSemantics.v0.md Section A).

    Returns a hashable Mu dict representing a structurally undefined operation.
    Contract violations remain fail-closed errors; this is for semantic unknowns.
    """
    def _safe_hash(value):
        if value is None:
            return None
        try:
            return mu_hash_cached(value)
        except Exception:
            return None

    return {
        "_undefined": True,
        "op": op,
        "lhs_hash": _safe_hash(lhs),
        "rhs_hash": _safe_hash(rhs),
        "cause": cause,
        "details": details,
    }


@host_iteration("Kernel execution loop - mechanical driver (Phase 8b simplified)")
def step_kernel_mu(
    projections: list[Mu],
    input_value: Mu,
    *,
    kernel_mode: str = "core",
    validation_mode: str = "domain",
    return_meta: bool = False,
    max_steps: int = 10000,
) -> Mu | dict[str, Mu]:
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
    - mu_hash_control_cached(): Detect no-progress stall (hash comparison)

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
        return_meta: When True, returns metadata payload with fields:
            `output` (Mu), `stall` (bool), `termination_reason` (str),
            `steps_used` (int), `max_steps` (int).
            Reason enum: projection_applied, kernel_stall, hash_stall,
            max_steps_exhausted.
        max_steps: Maximum kernel iteration steps. Default 10000.
            For single-projection calls (e.g. apply_mu), 500 is sufficient.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
        If `return_meta=True`, returns a metadata dict with termination details.

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

    # SECURITY: Validate each domain projection structure and Mu validity
    # Fail closed: reject non-dict projections, missing pattern/body, non-Mu content
    # This matches JS stepKernel validation (parity requirement)
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            raise TypeError(
                f"SECURITY: projection[{i}] must be a dict, got {type(proj).__name__}"
            )
        if "pattern" not in proj:
            raise KeyError(
                f"SECURITY: projection[{i}] missing required 'pattern' key"
            )
        if "body" not in proj:
            raise KeyError(
                f"SECURITY: projection[{i}] missing required 'body' key"
            )
        assert_mu(proj["pattern"], f"projection[{i}].pattern")
        assert_mu(proj["body"], f"projection[{i}].body")
        validator(proj["pattern"], f"projection[{i}].pattern")
        validator(proj["body"], f"projection[{i}].body")

    # Load combined kernel projections via private shared helpers
    # (no deep copy — eval_step never mutates projections; F-39)
    if kernel_mode == "core":
        kernel_projs = _load_combined_kernel_projections_shared()
    elif kernel_mode == "bridge":
        kernel_projs = _load_combined_kernel_with_bridge_projections_shared()
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
    # INVARIANT: eval_step is functionally pure — it returns new structures,
    # never mutates its input. current_hash caching depends on this property.
    current = kernel_entry
    current_hash = mu_hash_control_cached(kernel_entry, "step_kernel_mu")
    # BOOTSTRAP_PRIMITIVE: max_steps
    # This is the irreducible resource exhaustion guard.
    # Cannot be structural (would require arithmetic on fuel).
    # Prevents infinite execution - analogous to watchdog timer.
    # See mu/docs/core/BootstrapPrimitives.v0.md
    budget = get_step_budget()
    started_budget = False
    if not budget.is_active():
        budget.start()
        started_budget = True

    # Phase 8b: Simplified mechanical loop - no semantic decisions inside
    try:
        for step_i in range(max_steps):
            # Account for kernel-driver work in the shared global budget.
            budget.consume(1)
            result = _step_trusted(kernel_projs, current)

            # Terminal state check - simple structural marker detection
            if is_kernel_terminal(result):
                is_stall = result.get("_stall") is True
                output = extract_kernel_result(result, input_value)
                validator(output, "step_kernel_mu output")
                if return_meta:
                    reason = "kernel_stall" if is_stall else "projection_applied"
                    meta = {
                        "output": output,
                        "stall": bool(is_stall),
                        "termination_reason": reason,
                        "steps_used": step_i + 1,
                        "max_steps": max_steps,
                    }
                    if is_stall:
                        meta["undefined_motif"] = make_undefined_motif(
                            op="kernel",
                            lhs=input_value,
                            rhs=None,
                            cause="no_matching_projection",
                        )
                    return meta
                return output

            # Stall check - no change means no progress
            # Skip for intermediate kernel states (they have deep nested structures
            # and are mid-execution by definition, not stalls)
            if not is_kernel_intermediate(result):
                result_hash = mu_hash_control_cached(result, "step_kernel_mu.stall")
                if result_hash == current_hash:
                    validator(input_value, "step_kernel_mu output")
                    if return_meta:
                        return {
                            "output": input_value,
                            "stall": True,
                            "termination_reason": "hash_stall",
                            "steps_used": step_i + 1,
                            "max_steps": max_steps,
                        }
                    return input_value
                current_hash = result_hash

            current = result

        # Max steps exceeded - return original input (stall)
        validator(input_value, "step_kernel_mu output")
        if return_meta:
            return {
                "output": input_value,
                "stall": True,
                "termination_reason": "max_steps_exhausted",
                "steps_used": max_steps,
                "max_steps": max_steps,
            }
        return input_value
    finally:
        if started_budget:
            budget.stop()


def run_algorithm_meta_circular(
    projections: list[Mu],
    input_value: Mu,
    *,
    execution_mode: str = "structural",
    allow_bootstrap_fallback: bool = False,
) -> Mu:
    """
    Run an internal algorithm (recurrence, exhaustion).

    Gate 4 cutover:
    - Default mode (`execution_mode="structural"`) runs through step_kernel_mu
      with bridge support and algorithm-runtime validation.
    - Bootstrap execution is retained only as an explicit debug fallback
      (`execution_mode="bootstrap"`) and requires `allow_bootstrap_fallback=True`.

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
        allow_bootstrap_fallback: Must be True to execute bootstrap fallback.

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
        if not allow_bootstrap_fallback:
            raise ValueError(
                "SECURITY: bootstrap fallback is disabled by default. "
                "Set allow_bootstrap_fallback=True for explicit debug use."
            )
        return step_algorithm_with_bridge(projections, input_value)

    raise ValueError(
        "SECURITY: invalid execution_mode. Expected 'structural' or 'bootstrap', "
        f"got: {execution_mode}"
    )


def step_algorithm_with_bridge(projections: list[Mu], input_value: Mu) -> Mu:
    """DEBUG_ONLY: Bootstrap algorithm execution (not used in production path).

    Production path uses ``run_algorithm_meta_circular(execution_mode="structural")``.
    This function exists only for controlled debugging via
    ``execution_mode="bootstrap", allow_bootstrap_fallback=True``.

    Runs algorithm projections (recurrence, exhaustion) with bridge-enabled
    matching. Input is normalized before matching, output is denormalized.

    Args:
        projections: Algorithm projections (recurrence.v1 or exhaustion.v1).
        input_value: Algorithm state (entry point or intermediate).

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
    """
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

    # Single bootstrap step — trusted because we validated at boundary above.
    normalized_result = _step_trusted(projections, normalized_input)
    if mu_hash_control_cached(normalized_result, "step_algorithm.stall") == mu_hash_control_cached(normalized_input, "step_algorithm.stall"):
        return input_value

    result = denormalize_from_match(normalized_result)
    validate_algorithm_runtime_fields(result, "step_algorithm_with_bridge output")
    return result


# =============================================================================
# Projection Application (Phase 5)
#
# SEMANTIC SPLIT (intentional, fail-closed):
#   apply_mu / match_mu: Uses match.v2 + bridge projections (non-linear
#       conflict detection). Required for non-linear patterns.
#   step_mu / run_mu: Uses core kernel (match.v2 without bridge).
#       Linear-only by contract. Rejects non-linear patterns with ValueError.
#   run_algorithm_meta_circular: Uses bridge kernel. Handles algorithm seeds
#       (recurrence, exhaustion) which contain non-linear patterns.
#
# See tests/structural/test_match_bridge_invariants.py::TestSplitSemanticsContract
# =============================================================================

def apply_mu(projection: Mu, input_value: Mu) -> Mu:
    """
    Apply a projection to a value using Mu-based match and substitute.

    Uses match_mu (match.v2 + bridge) for correct non-linear pattern
    handling. Achieves parity with eval_seed.apply_projection() for all
    inputs (except known normalization edge cases documented in Phase 4d).

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


def _has_nonlinear_vars(pattern: Mu) -> bool:
    """Check if pattern has non-linear variables (same var name appears twice).

    Used as fail-closed guard: step_mu/run_mu use core kernel which does NOT
    detect binding conflicts. Non-linear patterns must use apply_mu (bridge path)
    or run_algorithm_meta_circular.

    Traversal is structural: no host-identity dedup. Shared object references
    are traversed each time they appear, so aliased subtrees are correctly
    counted as repeated structure. Bounded only by iteration cap
    (MAX_MU_DEPTH * MAX_MU_WIDTH = 300K). Cyclic or pathological input
    hits the cap and fail-closes as non-linear.
    """
    var_counts: dict[str, int] = {}
    max_iterations = 300_000  # MAX_MU_DEPTH(300) * MAX_MU_WIDTH(1000)
    iterations = 0

    stack: list[Mu] = [pattern]
    while stack:
        iterations += 1
        if iterations > max_iterations:
            # Fail-closed: pathological/cyclic input, treat as non-linear.
            return True
        current = stack.pop()
        if isinstance(current, dict):
            if set(current.keys()) == {"var"} and isinstance(current["var"], str):
                name = current["var"]
                var_counts[name] = var_counts.get(name, 0) + 1
            else:
                stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)

    return any(count > 1 for count in var_counts.values())


def _reject_nonlinear_projections(projections: list[Mu], caller: str) -> None:
    """Fail-closed: reject projections with non-linear patterns on core kernel path.

    Core kernel (match.v2 without bridge) silently overwrites bindings when the
    same variable appears twice in a pattern. This produces wrong results for
    conflicting bindings instead of NO_MATCH.

    Non-linear patterns MUST use:
    - apply_mu() for single-projection application (uses match.v2 + bridge)
    - run_algorithm_meta_circular() for algorithm execution (uses bridge kernel)

    Raises:
        ValueError: If any projection has non-linear patterns.
    """
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            continue
        pattern = proj.get("pattern")
        if pattern is not None and _has_nonlinear_vars(pattern):
            proj_id = proj.get("id", f"projection[{i}]")
            raise ValueError(
                f"{caller}: projection '{proj_id}' has non-linear pattern "
                f"(same variable appears twice). Core kernel does not detect "
                f"binding conflicts. Use apply_mu() or "
                f"run_algorithm_meta_circular(kernel_mode='bridge') instead."
            )


def step_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order using structural kernel (core, linear-only).

    Uses core kernel (match.v2 without bridge). Non-linear patterns
    (same variable twice) are rejected — use apply_mu for those.

    Args:
        projections: List of projections to try (must be linear-only).
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If projections contain non-linear patterns.
        ValueError: If kernel projections appear after domain projections (security).
    """
    _reject_nonlinear_projections(projections, "step_mu")
    return step_kernel_mu(projections, input_value)


@host_iteration("Kernel run loop - for-loop accepted as bootstrap primitive (L2 FULL)")
def run_mu(projections: list[Mu], initial: Mu, max_steps: int = 1000) -> tuple[Mu, list[dict], bool]:
    """
    Run projections repeatedly until stall or max steps (core, linear-only).

    Uses core kernel (match.v2 without bridge). Non-linear patterns
    (same variable twice) are rejected — use run_algorithm_meta_circular
    with kernel_mode='bridge' for those.

    Args:
        projections: List of projections to apply (must be linear-only).
        initial: Starting value.
        max_steps: Maximum iterations before forced stop.

    Returns:
        Tuple of (final_value, trace, is_stall):
        - final_value: The result after all steps
        - trace: List of {"step": n, "value": v} entries
        - is_stall: True if stopped due to stall (no change)

    Raises:
        ValueError: If projections contain non-linear patterns.
    """
    assert_mu(initial, "run_mu.initial")
    validate_no_kernel_reserved_fields(initial, "run_mu initial")
    _reject_nonlinear_projections(projections, "run_mu")
    validate_kernel_projections_first(projections)
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            continue
        if "pattern" in proj:
            validate_no_kernel_reserved_fields(proj["pattern"], f"run_mu projection[{i}].pattern")
        if "body" in proj:
            validate_no_kernel_reserved_fields(proj["body"], f"run_mu projection[{i}].body")

    trace = []
    current = initial
    # INVARIANT: step_mu is functionally pure — current_hash caching is safe.
    current_hash = mu_hash_control_cached(initial, "run_mu")

    for i in range(max_steps):
        trace.append({"step": i, "value": current})

        result = step_mu(projections, current)

        # Check for stall (no change)
        result_hash = mu_hash_control_cached(result, "run_mu.stall")
        if result_hash == current_hash:
            trace.append({"step": i + 1, "value": result, "stall": True})
            return result, trace, True

        current = result
        current_hash = result_hash

    # Hit max steps without stall
    trace.append({"step": max_steps, "value": current, "max_steps": True})
    return current, trace, False


def _resolve_trace_projection_id(
    projections: list[Mu],
    current: Mu,
    next_value: Mu,
) -> Mu:
    """
    Resolve which projection produced `next_value` from `current` using bridge semantics.

    Gate 5 parity requirement:
    - `run_mu_structural` must share execution semantics with `step_kernel_mu`.
    - Projection ID extraction therefore probes each projection through
      `step_kernel_mu(..., kernel_mode="bridge")` instead of calling `match_mu`
      or `subst_mu` directly.

    Returns:
        Projection id if a matching projection is found, otherwise None.
    """
    # SECURITY: Do NOT suspend the step budget. Probes must consume from the
    # caller's budget to prevent unbounded computation (adversary finding #1).
    # Cache next_value hash — it doesn't change across iterations.
    next_value_hash = mu_hash_control_cached(next_value, "resolve_trace_projection")
    for proj in projections:
        if not isinstance(proj, dict):
            continue
        if "pattern" not in proj or "body" not in proj:
            continue
        candidate = step_kernel_mu(
            [proj],
            current,
            kernel_mode="bridge",
            validation_mode="domain",
            return_meta=True,
        )
        if candidate["stall"] is True:
            continue
        if mu_hash_control_cached(candidate["output"], "resolve_trace_projection.match") == next_value_hash:
            return proj.get("id")
    return None


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
    # INVARIANT: step_kernel_mu returns new structures — current_hash caching is safe.
    current_hash = mu_hash_control_cached(initial, "run_mu_structural")

    try:
        for i in range(max_steps):
            # Gate 5 parity: run the same bridge-backed kernel path as production.
            result = step_kernel_mu(
                projections,
                current,
                kernel_mode="bridge",
                validation_mode="domain",
            )
            matched_id = _resolve_trace_projection_id(projections, current, result)

            validate_no_kernel_reserved_fields(result, "run_mu_structural output")
            trace_entries.append({
                "step": i,
                "state": current,
                "projection": matched_id
            })

            # Check for stall (no change)
            result_hash = mu_hash_control_cached(result, "run_mu_structural.stall")
            if result_hash == current_hash:
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
            current_hash = result_hash

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


def _is_terminal_shape(value: Mu) -> bool:  # AST_OK: infra — terminal shape detection
    """Check if a value is a terminal output shape from recurrence or exhaustion.

    Terminal shapes are the final results that sub-algorithms produce:
    - recurrence: {closure_detected, final_result, tau_step}
    - exhaustion: {action, exhaustion_detected, frozen, operator_to_freeze}

    Detecting these early avoids unnecessary hash-stall iterations.
    Delegates to classify_terminal_kind() for single-source terminal logic.
    """
    kind = classify_terminal_kind(value)
    return kind == "recurrence_terminal" or kind == "exhaustion_terminal"


def _run_sub_algorithm(projs: list[Mu], initial: Mu, max_iterations: int) -> Mu:  # AST_OK: infra — boundary sub-algorithm runner
    """Run a sub-algorithm (recurrence/exhaustion) to completion.

    Services the boundary between engine phases: the engine projection
    defines WHICH algorithm to run, this function runs it to stall/terminal.

    Budget accounting: each inner step_kernel_mu call manages its own
    per-call budget (50k steps). The outer iteration count is bounded by
    max_iterations. No cross-iteration budget sharing — that causes
    premature exhaustion on slower CI runners.

    Terminates when:
    1. Semantic final shape detected (recurrence or exhaustion terminal output)
    2. Hash-stall fallback (no change between iterations)
    3. Iteration limit reached (fail-safe)
    """
    current = initial
    # INVARIANT: run_algorithm_meta_circular returns new structures — hash caching is safe.
    current_hash = mu_hash_control_cached(initial, "_run_sub_algorithm")
    for _ in range(max_iterations):  # AST_OK: infra — boundary iteration loop
        result = run_algorithm_meta_circular(projs, current)
        # Early termination: semantic final shape detected
        if _is_terminal_shape(result):
            return result
        # Hash-stall fallback: algorithm converged
        result_hash = mu_hash_control_cached(result, "_run_sub_algorithm.stall")
        if result_hash == current_hash:
            return result
        current = result
        current_hash = result_hash
    return current


# =============================================================================
# Backward-Compatibility Re-exports (Boot2 functions moved to engine_pipeline.py)
# KNOWN_COMPAT_SHIM: Remove in a future wave when all callers are updated.
# This import MUST be at the bottom of the file, after all definitions above,
# to avoid circular import issues. engine_pipeline.py imports from step_mu.py
# (Boot1 names), and step_mu.py re-exports from engine_pipeline.py here.
# =============================================================================
from .engine_pipeline import (  # noqa: E402 — intentional bottom-of-file import
    run_engine_pipeline,
    _run_engine_recursive,
    _validate_reentry_payload,
    _service_boundary_effect,
    _boundary_op_run_trace,
    _boundary_op_hash_trace,
    _boundary_op_run_algorithm,
    _BOUNDARY_DISPATCH,
    _ALGORITHM_SEED_ALLOWLIST,
    _load_boundary_ops,
    _load_engine_projections,
    _clear_boundary_ops_cache,
    _is_engine_terminal,
    _derive_engine_exit_reason,
    _collect_ontology_evidence,
    _validate_ontology_promotion_record,
    _build_ontology_promotion_candidate,
    _derive_opromo_fully_locked_seeds,
    _OPROMO_FULLY_LOCKED_SEEDS,
    _JS_CORE_SEED_REGISTRY_KEYS,
    ENGINE_EXIT_REASONS,
    _BOOT1_MAX_REENTRY_DEPTH,
    _MAX_TRACE_ENTRIES_HARD_CAP,
    hash_trace_for_recurrence,
    run_hemisphere_routing,
    count_hemisphere_entries,
    run_metabolization_cycle,
    _default_hemispheres,
    run_engine_with_routing,
)
