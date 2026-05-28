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
from .eval_seed import (
    NO_MATCH,
    host_iteration,
    step as eval_step,
    _step_trusted,
    _apply_projection_trusted,
    match as stage0_match,
)
from .match_mu import match_mu, normalize_for_match, denormalize_from_match
from .subst_mu import subst_mu
from .mu_type import (
    Mu,
    MAX_MU_DEPTH,
    MAX_MU_WIDTH,
    _compute_mu_hash,
    assert_mu,
    is_mu,
    mu_hash,
    mu_hash_cached,
    mu_hash_control,
    mu_hash_control_cached,
)
from .kernel import get_step_budget
from collections.abc import Callable
from .seed_integrity import get_seed_path, load_verified_seed, MU_SEED_LOCATIONS, SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS
from .projection_loader import make_projection_loader

# Cached loader for terminal classification seed (structural displacement of classify/exit-reason logic)
_load_tc_projections, _clear_tc_proj_cache = make_projection_loader("terminal_classify.v1.json")
# Cached loader for hemisphere seed (A9: hemisphere key authority displacement)
_load_hemi_projections, _clear_hemi_proj_cache = make_projection_loader("hemispheres.v1.json")

# Sentinel for "caller did not provide kernel fuel"; distinct from None, which
# is valid Mu data and means an exhausted linked-list fuel value.
_KERNEL_FUEL_UNSET: object = object()


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
    if not isinstance(value, dict):  # AST_OK:infra — type guard
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
    return result if isinstance(result, str) else "non_terminal"  # AST_OK:infra — type guard


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
    if not isinstance(projection, dict):  # AST_OK: infra — type guard for projection classification
        return False

    # Check by ID (fast path)
    proj_id = projection.get("id", "")
    if isinstance(proj_id, str) and proj_id.startswith("kernel."):  # AST_OK: infra — string type guard
        return True

    # Check by pattern structure (fallback)
    pattern = projection.get("pattern", {})
    if isinstance(pattern, dict) and "_mode" in pattern:  # AST_OK: infra — type guard for pattern shape
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
            proj_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"  # AST_OK:infra — type guard
            raise ValueError(
                f"SECURITY: Kernel projection '{proj_id}' appears after domain projection "
                f"'{first_domain_id}'. Kernel projections MUST be first to prevent "
                f"domain data from forging kernel state."
            )

        if not is_kernel and not seen_domain:
            seen_domain = True
            first_domain_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"  # AST_OK:infra — type guard


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
    if not isinstance(value, dict):  # AST_OK:infra — type guard
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
        if not isinstance(current, dict):  # AST_OK:infra — type guard
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
        if not isinstance(kv, dict):  # AST_OK:infra — type guard
            return None
        if set(kv.keys()) != {"head", "tail"}:
            return None
        key = kv.get("head")
        if not isinstance(key, str):  # AST_OK:infra — type guard
            return None
        kv_tail = kv.get("tail")
        if not isinstance(kv_tail, dict):  # AST_OK:infra — type guard
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
    if not isinstance(value, dict):  # AST_OK:infra — type guard
        return False
    keys = set(value.keys())
    if value.get("_type") == "dict":
        has_only_type = len(keys) == 1 and "_type" in keys
        has_typed_node = len(keys) == 3 and "_type" in keys and "head" in keys and "tail" in keys
        return has_only_type or has_typed_node
    if not (len(keys) == 2 and "head" in keys and "tail" in keys):
        return False
    kv = value.get("head")
    if not isinstance(kv, dict):  # AST_OK:infra — type guard
        return False
    # Candidate only when head itself looks like a kv-pair node.
    if set(kv.keys()) != {"head", "tail"}:
        return False
    key = kv.get("head")
    if not isinstance(key, str):  # AST_OK:infra — type guard
        return False
    kv_tail = kv.get("tail")
    if not isinstance(kv_tail, dict):  # AST_OK:infra — type guard
        return False
    if set(kv_tail.keys()) != {"head", "tail"}:
        return False
    tail = value.get("tail")
    return tail is None or isinstance(tail, dict)  # AST_OK:infra — type guard


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

    if isinstance(value, dict):  # AST_OK:infra — type guard
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
    elif isinstance(value, list):  # AST_OK:infra — type guard
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
    if isinstance(key, str) and key.startswith("_"):  # AST_OK:infra — type guard
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


def _validate_entry_point(
    projections: list[Mu],
    initial: Mu,
    validator,
    label: str,
    *,
    reject_nonlinear: bool = False,
) -> None:
    """Common entry-point validation for run_mu / run_mu_structural.

    Combines assert_mu, field validation, ordering, and projection field checks.
    """
    assert_mu(initial, f"{label}.initial")
    validator(initial, f"{label} initial")
    if reject_nonlinear:
        _reject_nonlinear_projections(projections, label)
    validate_kernel_projections_first(projections)
    _validate_projection_fields(projections, validator, label)


def _validate_projection_fields(
    projections: list[Mu],
    validator,
    label: str,
) -> None:
    """Validate projection pattern/body fields, skipping non-dict entries.

    Called by _validate_entry_point (for run_mu/run_mu_structural) and
    step_algorithm_with_bridge. Lenient mode: non-dict projections are
    skipped (not rejected) and missing pattern/body keys are tolerated.
    For strict validation (TypeError/KeyError on invalid projections),
    see step_kernel_mu's inline loop.
    """
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):  # AST_OK:infra — type guard
            continue
        if "pattern" in proj:
            validator(proj["pattern"], f"{label} projection[{i}].pattern")
        if "body" in proj:
            validator(proj["body"], f"{label} projection[{i}].body")


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
    for item in reversed(items):  # BOUNDARY: bounded boundary-normalization conversion loop (parity with JS listToLinked)
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
    # Defensive copy via JSON round-trip (ensures pure Mu, no host references)
    return json.loads(json.dumps(_load_combined_kernel_projections_shared()))


def clear_combined_kernel_cache() -> None:
    """
    Clear the combined kernel projection cache.

    9-agent round 2 (Expert finding): Restored for test isolation.
    Tests that mock projections need this to prevent stale cache pollution.
    Wave 3C: compiled bundle caches cleared via factory clear functions.
    """
    global _combined_kernel_cache, _combined_kernel_bridge_cache
    global _kernel_v1_cache, _bridge_proj_cache
    _combined_kernel_cache = None
    _combined_kernel_bridge_cache = None
    _kernel_v1_cache = None
    _bridge_proj_cache = None
    # Wave 3C: clear compiled bundle caches via factory (step_mu instances)
    _clear_compiled_match_v2_bundle()
    _clear_compiled_subst_v2_bundle()
    _clear_compiled_kernel_v1_bundle()
    _clear_compiled_bridge_bundle()
    # Wave 3C: also clear match_mu + subst_mu independent factory caches
    # (verifier finding: these are separate closures with separate _cache[0])
    from .match_mu import _clear_match_bundle, _clear_bridge_bundle  # ANTICHEAT_OK: infra — test isolation
    _clear_match_bundle()
    _clear_bridge_bundle()
    from .match_mu import clear_match_bridge_cache  # ANTICHEAT_OK: infra — test isolation
    clear_match_bridge_cache()
    from .subst_mu import _clear_compiled_subst_v2_bundle as _clear_subst_mu_bundle  # ANTICHEAT_OK: infra — test isolation
    _clear_subst_mu_bundle()
    # Wave 3D-B: clear classify_mu factory cache
    from .classify_mu import _clear_classify_bundle  # ANTICHEAT_OK: infra — test isolation
    _clear_classify_bundle()
    # S1-C: Also clear TC and hemisphere caches for complete test isolation
    _clear_tc_cache()
    _clear_hemi_cache()


# Module-level cache for combined kernel projections with bootstrap_structural bridge
_combined_kernel_bridge_cache: list[Mu] | None = None

# =============================================================================
# P7-d: Partitioned Kernel Projection Loaders + Compiled Bundle Loaders
# =============================================================================

# Partitioned caches: kernel.v1 only, bridge only
_kernel_v1_cache: list[Mu] | None = None
_bridge_proj_cache: list[Mu] | None = None

# Compiled bundle loaders (Wave 3C: consolidated via factory)
from .stage0_vm import make_compiled_bundle_loader  # ANTICHEAT_OK: infra — bundle loader factory

_load_compiled_match_v2_bundle, _clear_compiled_match_v2_bundle = make_compiled_bundle_loader("match_v2")
_load_compiled_subst_v2_bundle, _clear_compiled_subst_v2_bundle = make_compiled_bundle_loader("subst_v2")
_load_compiled_kernel_v1_bundle, _clear_compiled_kernel_v1_bundle = make_compiled_bundle_loader("kernel_v1")
_load_compiled_bridge_bundle, _clear_compiled_bridge_bundle = make_compiled_bundle_loader("bootstrap_structural_v1")


def _load_kernel_v1_projections_shared() -> list[Mu]:
    """Load ONLY kernel.v1 projections (no match/subst).

    Private shared-cache variant. Callers MUST NOT mutate the returned list.
    Used by _step_kernel_with_vm for host-path kernel.v1 execution.
    """
    global _kernel_v1_cache
    if _kernel_v1_cache is not None:
        return _kernel_v1_cache
    kernel_seed = load_verified_seed(get_seed_path("kernel.v1.json"))
    _kernel_v1_cache = kernel_seed["projections"]
    return _kernel_v1_cache


def _load_bridge_projections_shared() -> list[Mu]:
    """Load ONLY bootstrap_structural.v1 projections.

    Private shared-cache variant. Callers MUST NOT mutate the returned list.
    Used by _step_kernel_with_vm for host-path bridge execution.
    """
    global _bridge_proj_cache
    if _bridge_proj_cache is not None:
        return _bridge_proj_cache
    bridge_seed = load_verified_seed(get_seed_path("bootstrap_structural.v1.json"))
    _bridge_proj_cache = bridge_seed["projections"]
    return _bridge_proj_cache


def _verify_bundle_provenance(bundle: dict) -> None:  # AST_OK:infra — type guard
    """Verify compiled bundle's source_digest matches SEED_CHECKSUMS registry.

    N15 provenance: Fail-closed on mismatch. Uses SEED_CHECKSUMS as the
    canonical truth source — no source-file I/O needed. Works in both
    Python and JS substrates.

    The compiler (lower_stage0.py) computes SHA256 of the raw seed file bytes
    and embeds it as source_digest. This function verifies that claim against
    the independently-maintained SEED_CHECKSUMS registry.
    """
    from .seed_integrity import SEED_CHECKSUMS  # ANTICHEAT_OK: infra — provenance check
    source_seed = bundle.get("source_seed")
    source_digest = bundle.get("source_digest")
    if not source_seed or not source_digest:
        return  # Hand-authored bundles may lack these fields
    seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
    if seed_filename not in SEED_CHECKSUMS:
        return  # Unknown seed — cannot verify (hand-authored or test bundle)
    expected_digest = "sha256:" + SEED_CHECKSUMS[seed_filename]
    if source_digest != expected_digest:  # AST_OK:infra — type guard
        raise ValueError(
            f"SECURITY: Bundle provenance mismatch for '{seed_filename}'. "
            f"Bundle claims source_digest={source_digest}, "
            f"but SEED_CHECKSUMS says {expected_digest}. "
            f"Compiled bundle may be stale or tampered."
        )


# NOTE: _load_compiled_match_v2_bundle, _load_compiled_subst_v2_bundle,
# _load_compiled_kernel_v1_bundle, _load_compiled_bridge_bundle are now
# created by make_compiled_bundle_loader() above (Wave 3C consolidation).
# The factory provides: load, validate_bundle, N15 provenance, and caching.


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
        if isinstance(proj, dict):  # AST_OK:infra — type guard
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
    # Defensive copy via JSON round-trip (ensures pure Mu, no host references)
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
    if not isinstance(result, dict):  # AST_OK: infra — type guard for kernel state classification
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


# =============================================================================
# P7-d: Stage0 VM Kernel-Step Function
# =============================================================================

# Shadow mode flag: when True, step_kernel_mu uses VM for match.v2/subst.v2.
# When False (default), host path is primary with shadow VM comparison.
_STAGE0_VM_CUTOVER = True  # S1-B: VM path is now primary (founder GO 2026-03-15)
_STAGE0_SHADOW_ENABLED = False  # S1-B: Shadow disabled (cutover=True makes shadow dead code)


def _step_kernel_with_vm(
    kernel_bundle: dict,
    bridge_bundle: dict | None,
    match_bundle: dict,
    subst_bundle: dict,
    input_value: Mu,
    record_coverage: bool = True,
) -> Mu:
    """Kernel step: ALL projections via Stage0 VM.

    S1-C: kernel.v1 and bridge projections now execute via VM (previously host).
    Scope: step_kernel_mu cutover only. _step_trusted remains unchanged for
    run_engine_pipeline.

    Preserves first-match-wins ordering: kernel -> bridge -> match -> subst.
    Coverage semantics preserved: record_no_match for every tried-but-failed
    projection/program, record_match for the matched one, no record for
    projections/programs never tried (after the match).

    Args:
        kernel_bundle: Compiled kernel_v1 bundle for Stage0 VM.
        bridge_bundle: Compiled bootstrap_structural_v1 bundle (bridge mode only).
            None in core mode.
        match_bundle: Compiled match_v2 bundle for Stage0 VM.
        subst_bundle: Compiled subst_v2 bundle for Stage0 VM.
        input_value: Current kernel state (already normalized/wrapped).
        record_coverage: When False, skip all coverage recording.

    Returns:
        Transformed value if any projection matched, input unchanged on stall.
    """
    from rcx_pi.projection_coverage import coverage
    from rcx_pi.selfhost.stage0_vm import _stage0_vm_step_trusted  # W6A: trusted path — bundles are loader-cached

    cov_on = record_coverage and coverage.is_enabled()

    if cov_on:
        coverage.record_step()

    # 1. kernel.v1 via Stage0 VM (S1-C: was host _apply_projection_trusted)
    vm_result = _stage0_vm_step_trusted(kernel_bundle, input_value)
    if vm_result["status"] == "match":  # AST_OK:infra — type guard
        if cov_on:
            trace = vm_result["attempt_trace"]
            attempted_ids = trace["attempted_program_ids"]
            matched_id = trace["matched_program_id"]
            if trace["outcome"] != "match" or not attempted_ids or attempted_ids[-1] != matched_id:
                raise RuntimeError("Stage0 VM match trace does not end at matched program")
            for pid in attempted_ids[:-1]:
                coverage.record_no_match(pid)
            coverage.record_match(matched_id, input_value, vm_result["root"])
        return vm_result["root"]
    else:
        if cov_on:
            trace = vm_result["attempt_trace"]
            if trace["outcome"] != "stall" or trace["matched_program_id"] is not None:
                raise RuntimeError("Stage0 VM stall trace carried a matched program")
            for pid in trace["attempted_program_ids"]:
                coverage.record_no_match(pid)

    # 2. bridge via Stage0 VM (S1-C: was host _apply_projection_trusted)
    if bridge_bundle:
        vm_result = _stage0_vm_step_trusted(bridge_bundle, input_value)
        if vm_result["status"] == "match":  # AST_OK:infra — type guard
            if cov_on:
                trace = vm_result["attempt_trace"]
                attempted_ids = trace["attempted_program_ids"]
                matched_id = trace["matched_program_id"]
                if trace["outcome"] != "match" or not attempted_ids or attempted_ids[-1] != matched_id:
                    raise RuntimeError("Stage0 VM match trace does not end at matched program")
                for pid in attempted_ids[:-1]:
                    coverage.record_no_match(pid)
                coverage.record_match(matched_id, input_value, vm_result["root"])
            return vm_result["root"]
        else:
            if cov_on:
                trace = vm_result["attempt_trace"]
                if trace["outcome"] != "stall" or trace["matched_program_id"] is not None:
                    raise RuntimeError("Stage0 VM stall trace carried a matched program")
                for pid in trace["attempted_program_ids"]:
                    coverage.record_no_match(pid)

    # 3. match.v2 via Stage0 VM
    vm_result = _stage0_vm_step_trusted(match_bundle, input_value)
    if vm_result["status"] == "match":
        if cov_on:
            trace = vm_result["attempt_trace"]
            attempted_ids = trace["attempted_program_ids"]
            matched_id = trace["matched_program_id"]
            if trace["outcome"] != "match" or not attempted_ids or attempted_ids[-1] != matched_id:
                raise RuntimeError("Stage0 VM match trace does not end at matched program")
            for pid in attempted_ids[:-1]:
                coverage.record_no_match(pid)
            coverage.record_match(matched_id, input_value, vm_result["root"])
        return vm_result["root"]
    else:
        # Stall: all match.v2 programs tried and failed
        if cov_on:
            trace = vm_result["attempt_trace"]
            if trace["outcome"] != "stall" or trace["matched_program_id"] is not None:
                raise RuntimeError("Stage0 VM stall trace carried a matched program")
            for pid in trace["attempted_program_ids"]:
                coverage.record_no_match(pid)

    # 4. subst.v2 via Stage0 VM
    vm_result = _stage0_vm_step_trusted(subst_bundle, input_value)
    if vm_result["status"] == "match":
        if cov_on:
            trace = vm_result["attempt_trace"]
            attempted_ids = trace["attempted_program_ids"]
            matched_id = trace["matched_program_id"]
            if trace["outcome"] != "match" or not attempted_ids or attempted_ids[-1] != matched_id:
                raise RuntimeError("Stage0 VM match trace does not end at matched program")
            for pid in attempted_ids[:-1]:
                coverage.record_no_match(pid)
            coverage.record_match(matched_id, input_value, vm_result["root"])
        return vm_result["root"]
    else:
        if cov_on:
            trace = vm_result["attempt_trace"]
            if trace["outcome"] != "stall" or trace["matched_program_id"] is not None:
                raise RuntimeError("Stage0 VM stall trace carried a matched program")
            for pid in trace["attempted_program_ids"]:
                coverage.record_no_match(pid)

    return input_value  # stall


_KERNEL_DRIVER_CONTINUATION_KEYS = frozenset({  # AST_OK: constant - packet contract
    "tag",
    "version",
    "kernel_state",
    "domain_input",
    "projection_cursor",
    "remaining_fuel",
    "fuel_mode",
    "steps_used",
    "watchdog_cap",
    "terminal",
})
_KERNEL_PROJECTION_CURSOR_KEYS = frozenset({  # AST_OK: constant - packet contract
    "tag",
    "version",
    "position",
    "exhausted",
})
_KERNEL_TERMINAL_METADATA_KEYS = frozenset({  # AST_OK: constant - packet contract
    "reached",
    "reason",
    "error",
})
_KERNEL_TERMINAL_REASONS = frozenset({  # AST_OK: constant - packet contract
    "accepted",
    "fuel_exhausted",
    "watchdog_exhausted",
    "malformed_fuel",
    "error",
})
_KERNEL_PROJECTION_KEYS = frozenset({"pattern", "body"})  # AST_OK: constant - continuation key contract
_KERNEL_MATCH_CTX_KEYS = frozenset({"_input", "_body", "_remaining"})  # AST_OK: constant - continuation key contract
_KERNEL_MATCH_REQUEST_KEYS = frozenset({"pattern", "value"})  # AST_OK: constant - continuation key contract
_KERNEL_SUBST_CTX_KEYS = frozenset({"_input", "_remaining"})  # AST_OK: constant - continuation key contract
_KERNEL_SUBST_REQUEST_KEYS = frozenset({"body", "bindings"})  # AST_OK: constant - continuation key contract
_KERNEL_TRY_STATE_KEYS = frozenset({"_mode", "_phase", "_input", "_remaining"})  # AST_OK: constant - continuation key contract
_KERNEL_MATCH_DONE_SUCCESS_KEYS = frozenset({  # AST_OK: constant - continuation key contract
    "_mode",
    "_status",
    "_bindings",
    "_match_ctx",
})
_KERNEL_MATCH_DONE_NO_MATCH_KEYS = frozenset({"_mode", "_status", "_match_ctx"})  # AST_OK: constant - continuation key contract
_KERNEL_MATCH_REQUEST_STATE_KEYS = frozenset({"match", "_match_ctx"})  # AST_OK: constant - continuation key contract
_KERNEL_SUBST_REQUEST_STATE_KEYS = frozenset({"subst", "_subst_ctx"})  # AST_OK: constant - continuation key contract
_KERNEL_SUBST_DONE_KEYS = frozenset({"_mode", "_result", "_subst_ctx"})  # AST_OK: constant - continuation key contract
_KERNEL_MATCH_LOOKUP_STATE_KEYS = frozenset({  # AST_OK: constant - continuation key contract
    "mode",
    "_phase",
    "_lookup_name",
    "_lookup_value",
    "_lookup_bindings",
    "_original_bindings",
    "stack",
    "_match_ctx",
})
_KERNEL_MATCH_STATE_KEYS = frozenset({  # AST_OK: constant - continuation key contract
    "mode",
    "pattern_focus",
    "value_focus",
    "bindings",
    "stack",
    "_match_ctx",
})
_KERNEL_SUBST_TRAVERSE_STATE_KEYS = frozenset({  # AST_OK: constant - continuation key contract
    "mode",
    "phase",
    "focus",
    "bindings",
    "context",
    "_subst_ctx",
})
_KERNEL_SUBST_LOOKUP_STATE_KEYS = frozenset({  # AST_OK: constant - continuation key contract
    "mode",
    "phase",
    "lookup_name",
    "lookup_bindings",
    "bindings",
    "context",
    "_subst_ctx",
})


@host_iteration("Kernel execution loop - residual watchdog; supplied Mu fuel owns progress")
def step_kernel_mu(
    projections: list[Mu],
    input_value: Mu,
    *,
    kernel_mode: str = "core",
    validation_mode: str = "domain",
    return_meta: bool = False,
    max_steps: int = 10000,
    kernel_fuel: object = _KERNEL_FUEL_UNSET,
    continuation_state: Mu | None = None,
    return_packet: bool = False,
) -> Mu | dict[str, Mu]:
    """
    Perform exactly one single-step kernel-driver transition, or drive public compatibility.

    Terminal packets carry the existing KernelRunResult under ``result``.
    Nonterminal packets carry a Mu data continuation under ``continuation``.
    Omitted ``kernel_fuel`` remains an explicit compatibility fuel mode and
    never seeds ``remaining_fuel`` from ``max_steps`` or host counts.

    The kernel works as a state machine:
    1. kernel.wrap: Wraps input and projections into kernel state
    2. kernel.try: Tries first projection via match.v2
    3. kernel.match_success/fail: On success, substitute via subst.v2; on fail, try next
    4. kernel.stall: All projections tried, no match -> {_mode: "done", _stall: true}
    5. kernel.unwrap: Success -> {_mode: "done", _result: X, _stall: false}

    With ``return_packet=True``, the kernel-driver body ONLY does:
    - is_kernel_terminal(): Check for structural marker {_mode: "done", ...}
    - extract_kernel_result(): Unpack the marker (no semantic decisions)
    - mu_hash_control_cached(): Detect no-progress stall (hash comparison)

    L2 FULL: Projection SELECTION is structural (linked-list cursor).
    Projection EXECUTION uses a residual host transition driver; the returned
    continuation owns progress state across calls.

    Args:
        projections: List of domain projections to try.
        input_value: The value to transform.
        kernel_mode: `core` uses kernel+match.v2+subst.v2. `bridge` uses
            kernel+bridge+match.v2+subst.v2.
        validation_mode: `domain` uses reserved-field protection for untrusted
            domain inputs. `algorithm_runtime` allows trusted algorithm state
            with strict underscore allowlisting.
        return_meta: Public compatibility flag. Ignored when
            ``return_packet=True`` because terminal packets always carry the
            existing KernelRunResult shape under ``result``.
        max_steps: Maximum kernel iteration steps. Default 10000.
            For single-projection calls (e.g. apply_mu), 500 is sufficient.
        kernel_fuel: Optional Mu linked-list fuel. Omitted means legacy
            max_steps-only execution without synthetic compatibility fuel.
            Explicit None means empty fuel.

    Returns:
        When ``return_packet=True``, a KernelDriverStepPacket:
        - {"kind": "terminal", "result": KernelRunResult, "continuation": None}
        - {"kind": "continuation", "result": None, "continuation": KernelDriverContinuationState}
        Otherwise, the historical public output or KernelRunResult metadata.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
        ValueError: If input contains kernel-reserved fields (security).
    """
    if isinstance(max_steps, bool):  # AST_OK:security - watchdog type guard
        raise ValueError("SECURITY: max_steps must be a finite integer watchdog, got bool")
    if isinstance(max_steps, int):  # AST_OK:security - watchdog type guard
        watchdog_steps = max_steps
    elif isinstance(max_steps, float) and max_steps.is_integer():  # AST_OK:security - watchdog type guard
        watchdog_steps = int(max_steps)
    else:
        raise ValueError(
            f"SECURITY: max_steps must be a finite integer watchdog, got {type(max_steps).__name__}"
        )
    if watchdog_steps < 0:
        raise ValueError(f"SECURITY: max_steps must be >= 0, got {watchdog_steps}")
    max_steps = watchdog_steps
    if not isinstance(return_meta, bool):  # AST_OK: boundary - compatibility guard
        raise TypeError("SECURITY: return_meta must be bool")
    if not isinstance(return_packet, bool):  # AST_OK: boundary - compatibility guard
        raise TypeError("SECURITY: return_packet must be bool")
    if continuation_state is not None and kernel_fuel is not _KERNEL_FUEL_UNSET:
        raise ValueError("SECURITY: continuation_state carries remaining_fuel; do not also pass kernel_fuel")
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

    # SECURITY: Validate input at the selected boundary mode. Continuation
    # resume still binds to the caller-supplied domain input.
    validator(input_value, "step_kernel_mu input")

    # SECURITY: Validate projection order
    validate_kernel_projections_first(projections)

    # SECURITY: Reject kernel projections - step_kernel_mu expects DOMAIN projections only
    # Kernel projections are loaded separately via load_combined_kernel_projections().
    # Check by ID (kernel.*) not by _mode pattern because algorithm projections use _mode.
    for i, proj in enumerate(projections):
        proj_id = proj.get("id", "") if isinstance(proj, dict) else ""  # AST_OK:infra — type guard
        if isinstance(proj_id, str) and proj_id.startswith("kernel."):  # AST_OK:infra — type guard
            raise ValueError(
                f"SECURITY: step_kernel_mu expects DOMAIN projections only, "
                f"got kernel projection at index {i}: {proj_id}"
            )

    # SECURITY: Validate each domain projection structure and Mu validity
    # Fail closed: reject non-dict projections, missing pattern/body, non-Mu content
    # This matches JS stepKernel validation (parity requirement)
    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):  # AST_OK:infra — type guard
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

    # S1-C: Load ALL compiled bundles for VM path (kernel + bridge + match + subst)
    kernel_bundle = _load_compiled_kernel_v1_bundle()
    bridge_bundle = _load_compiled_bridge_bundle() if kernel_mode == "bridge" else None
    match_bundle = _load_compiled_match_v2_bundle()
    subst_bundle = _load_compiled_subst_v2_bundle()

    # Normalize domain projections and input for both new packets and resumes;
    # resume validation uses this canonical call authority before stepping.
    normalized_projs = [normalize_projection(p) for p in projections]  # AST_OK: infra - kernel bridge scaffolding
    normalized_input = normalize_for_match(input_value)
    kernel_entry: Mu = {
        "_step": normalized_input,
        "_projs": list_to_linked(normalized_projs)
    }

    caller_supplied_fuel = kernel_fuel is not _KERNEL_FUEL_UNSET
    if continuation_state is None:
        current = kernel_entry
        fuel_cursor = kernel_fuel if caller_supplied_fuel else None
        if caller_supplied_fuel:
            assert_mu(kernel_fuel, "step_kernel_mu.kernel_fuel")
            fuel_probe = kernel_fuel
            while fuel_probe is not None:
                if (
                    not isinstance(fuel_probe, dict)  # ANTICHEAT_OK: linked-list fuel boundary
                    or set(fuel_probe.keys()) != {"head", "tail"}
                ):
                    raise TypeError("SECURITY: kernel_fuel must be a Mu head/tail linked list")
                fuel_probe = fuel_probe["tail"]
        steps_used = 0
        watchdog_cap = max_steps
        domain_input = input_value
    else:
        assert_mu(continuation_state, "step_kernel_mu.continuation_state")
        if not isinstance(continuation_state, dict):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation_state must be a Mu dict")
        if set(continuation_state.keys()) != _KERNEL_DRIVER_CONTINUATION_KEYS:
            raise ValueError("SECURITY: continuation_state key set mismatch")
        if continuation_state.get("tag") != "kernel_driver_continuation_state":
            raise ValueError("SECURITY: continuation_state tag mismatch")
        continuation_version = continuation_state.get("version")
        if isinstance(continuation_version, bool) or continuation_version != 1:  # AST_OK: boundary - JS parity guard
            raise ValueError("SECURITY: continuation_state version mismatch")
        fuel_mode = continuation_state.get("fuel_mode")
        if fuel_mode not in ("explicit", "omitted_compatibility"):
            raise ValueError("SECURITY: continuation_state fuel_mode mismatch")
        raw_steps_used = continuation_state.get("steps_used")
        if isinstance(raw_steps_used, bool) or not isinstance(raw_steps_used, int):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation_state.steps_used must be a non-negative integer")
        if raw_steps_used < 0:
            raise ValueError("SECURITY: continuation_state.steps_used must be >= 0")
        raw_watchdog_cap = continuation_state.get("watchdog_cap")
        if raw_watchdog_cap is None:
            raise ValueError("SECURITY: continuation_state.watchdog_cap must match supplied max_steps")
        if isinstance(raw_watchdog_cap, bool) or not isinstance(raw_watchdog_cap, int):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation_state.watchdog_cap must be a non-negative integer")
        if raw_watchdog_cap < 0:
            raise ValueError("SECURITY: continuation_state.watchdog_cap must be >= 0")
        if raw_watchdog_cap != max_steps:
            raise ValueError("SECURITY: continuation_state.watchdog_cap must match supplied max_steps")
        projection_cursor = continuation_state.get("projection_cursor")
        if projection_cursor is not None:
            if not isinstance(projection_cursor, dict):  # AST_OK: boundary - continuation shape guard
                raise TypeError("SECURITY: projection_cursor must be a Mu dict or null")
            if set(projection_cursor.keys()) != _KERNEL_PROJECTION_CURSOR_KEYS:
                raise ValueError("SECURITY: projection_cursor key set mismatch")
            if projection_cursor.get("tag") != "kernel_projection_cursor":
                raise ValueError("SECURITY: projection_cursor tag mismatch")
            projection_cursor_version = projection_cursor.get("version")
            if isinstance(projection_cursor_version, bool) or projection_cursor_version != 1:  # AST_OK: boundary - JS parity guard
                raise ValueError("SECURITY: projection_cursor version mismatch")
            cursor_position = projection_cursor.get("position")
            if isinstance(cursor_position, bool) or not isinstance(cursor_position, int):  # AST_OK: boundary - continuation shape guard
                raise TypeError("SECURITY: projection_cursor.position must be a non-negative integer")
            if cursor_position < 0:
                raise ValueError("SECURITY: projection_cursor.position must be >= 0")
            if not isinstance(projection_cursor.get("exhausted"), bool):  # AST_OK: boundary - continuation shape guard
                raise TypeError("SECURITY: projection_cursor.exhausted must be bool")
        terminal = continuation_state.get("terminal")
        if not isinstance(terminal, dict):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation terminal metadata must be a Mu dict")
        if set(terminal.keys()) != _KERNEL_TERMINAL_METADATA_KEYS:
            raise ValueError("SECURITY: continuation terminal metadata key set mismatch")
        if not isinstance(terminal.get("reached"), bool):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation terminal.reached must be bool")
        reason = terminal.get("reason")
        if reason is not None and reason not in _KERNEL_TERMINAL_REASONS:
            raise ValueError("SECURITY: continuation terminal.reason mismatch")
        error = terminal.get("error")
        if error is not None and not isinstance(error, str):  # AST_OK: boundary - continuation shape guard
            raise TypeError("SECURITY: continuation terminal.error must be string or null")
        if (
            terminal.get("reached") is not False
            or terminal.get("reason") is not None
            or terminal.get("error") is not None
        ):
            raise ValueError("SECURITY: continuation terminal metadata must remain nonterminal")
        remaining_fuel = continuation_state.get("remaining_fuel")
        if fuel_mode == "explicit":
            assert_mu(remaining_fuel, "step_kernel_mu.continuation_state.remaining_fuel")
            fuel_probe = remaining_fuel
            while fuel_probe is not None:
                if (
                    not isinstance(fuel_probe, dict)  # ANTICHEAT_OK: linked-list fuel boundary
                    or set(fuel_probe.keys()) != {"head", "tail"}
                ):
                    raise TypeError("SECURITY: kernel_fuel must be a Mu head/tail linked list")
                fuel_probe = fuel_probe["tail"]
        elif remaining_fuel is not None:
            raise ValueError("SECURITY: omitted compatibility continuation must not carry remaining_fuel")
        # SECURITY: A continuation owns progress state, not projection authority.
        # Bind resume to the current call's supplied input/projection cursor
        # before stepping the embedded Mu kernel state.
        # Boundary validation above has already proven algorithm-runtime
        # continuation inputs are Mu; that trusted branch avoids re-running
        # assert_mu inside mu_hash_cached while preserving the canonical
        # SHA-256 hash contract. Keep the public/domain source-lock shape
        # visible before narrowing the trusted branch below.
        trusted_continuation_hash = validation_mode == "algorithm_runtime"

        normalized_input_hash = (
            _compute_mu_hash(json.dumps(kernel_entry["_step"], sort_keys=True, ensure_ascii=False, allow_nan=False))
            if trusted_continuation_hash
            else mu_hash(kernel_entry["_step"])
        )
        domain_input_hash = (
            _compute_mu_hash(json.dumps(input_value, sort_keys=True, ensure_ascii=False, allow_nan=False))
            if trusted_continuation_hash
            else mu_hash(input_value)
        )
        continuation_domain_input_hash = (
            _compute_mu_hash(json.dumps(continuation_state["domain_input"], sort_keys=True, ensure_ascii=False, allow_nan=False))
            if trusted_continuation_hash
            else mu_hash(continuation_state["domain_input"])
        )
        if continuation_domain_input_hash != domain_input_hash:
            raise ValueError("SECURITY: continuation_state domain_input is not bound to supplied input")

        from rcx_pi.selfhost.stage0_vm import _stage0_vm_run_bounded_trusted  # W6A: trusted path — loader-cached validator

        projection_hashes: set[str] = set()
        body_hashes: set[str] = set()
        projection_contexts: list[dict[str, Mu]] = []
        projection_sequence_hashes: list[str] = []
        prefix_has_match = False
        projection_authority_cursor = kernel_entry["_projs"]
        while projection_authority_cursor is not None:
            if (
                not isinstance(projection_authority_cursor, dict)  # AST_OK: boundary - Mu linked-list authority guard
                or set(projection_authority_cursor.keys()) != {"head", "tail"}
            ):
                raise TypeError("SECURITY: kernel projection cursor must be a Mu head/tail linked list")
            projection_authority = projection_authority_cursor["head"]
            if (
                not isinstance(projection_authority, dict)  # AST_OK: boundary - normalized projection authority guard
                or set(projection_authority.keys()) != _KERNEL_PROJECTION_KEYS
            ):
                raise TypeError("SECURITY: kernel projection cursor head must be a normalized projection")
            projection_hash = (
                _compute_mu_hash(json.dumps(projection_authority, sort_keys=True, ensure_ascii=False, allow_nan=False))
                if trusted_continuation_hash
                else mu_hash(projection_authority)
            )
            body_hash = (
                _compute_mu_hash(json.dumps(projection_authority["body"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                if trusted_continuation_hash
                else mu_hash(projection_authority["body"])
            )
            projection_hashes.add(projection_hash)
            body_hashes.add(body_hash)
            projection_sequence_hashes.append(projection_hash)
            match_result = None
            if validation_mode == "domain":
                match_outcome = _stage0_vm_run_bounded_trusted(
                    match_bundle,
                    {
                        "match": {
                            "pattern": projection_authority["pattern"],
                            "value": kernel_entry["_step"],
                        },
                        "_match_ctx": {
                            "_input": kernel_entry["_step"],
                            "_body": projection_authority["body"],
                            "_remaining": projection_authority_cursor["tail"],
                        },
                    },
                    terminal_field="_mode",
                    terminal_value="match_done",
                )
                if match_outcome["status"] == "terminal":
                    match_result = match_outcome["root"]
            projection_contexts.append({
                "projection": projection_authority,
                "projection_hash": projection_hash,
                "cursor": projection_authority_cursor,
                "rest": projection_authority_cursor["tail"],
                "body_hash": body_hash,
                "index": len(projection_contexts),
                "prefix_cleared": not prefix_has_match,
                "match_result": match_result,
            })
            if (
                validation_mode == "domain"
                and
                isinstance(match_result, dict)  # AST_OK: boundary - VM match terminal guard
                and match_result.get("_mode") == "match_done"
                and match_result.get("_status") == "success"
            ):
                prefix_has_match = True
            projection_authority_cursor = projection_authority_cursor["tail"]
        exhausted_prefix_cleared = not prefix_has_match
        for context in projection_contexts:
            index = context["index"]
            context["cursor_signature"] = projection_sequence_hashes[index:]
            context["rest_signature"] = projection_sequence_hashes[index + 1:]

        kernel_state = continuation_state["kernel_state"]
        kernel_state_is_object = isinstance(kernel_state, dict)  # AST_OK: boundary - continuation phase authority guard
        if not kernel_state_is_object:
            # Scalar Mu states can only come from the defensive hash-stall path:
            # they carry no projection authority and must resume as cursorless,
            # already-progressed continuations.
            if projection_cursor is not None:
                raise ValueError("SECURITY: continuation_state projection_cursor is not bound to kernel_state")
            if raw_steps_used == 0:
                raise ValueError("SECURITY: continuation_state steps_used is not bound to kernel_state phase")
            if raw_steps_used >= raw_watchdog_cap:
                raise ValueError("SECURITY: continuation_state steps_used is not bound to watchdog_cap")
        if kernel_state_is_object and projection_cursor is not None:
            if projection_cursor["position"] != raw_steps_used:
                raise ValueError("SECURITY: continuation_state steps_used/projection_cursor mismatch")
            if "_remaining" not in kernel_state:
                raise ValueError("SECURITY: continuation_state projection_cursor is not bound to kernel_state")
            if projection_cursor["exhausted"] != (kernel_state["_remaining"] is None):
                raise ValueError("SECURITY: continuation_state projection_cursor exhausted mismatch")
        elif kernel_state_is_object and "_remaining" in kernel_state:
            raise ValueError("SECURITY: continuation_state projection_cursor missing for kernel projection state")
        if kernel_state_is_object and is_kernel_terminal(kernel_state):
            raise ValueError("SECURITY: continuation_state kernel_state must be nonterminal")
        if (
            isinstance(kernel_state, dict)  # AST_OK: boundary - continuation phase authority guard
            and kernel_state.get("_mode") == "kernel"
            and kernel_state.get("_phase") == "try"
        ):
            if "_remaining" not in kernel_state:
                raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
            remaining_cursor = kernel_state["_remaining"]
            remaining_cursor_bound = False
            if remaining_cursor is None:
                remaining_cursor_bound = exhausted_prefix_cleared
            else:
                remaining_cursor_signature = []
                remaining_cursor_probe = remaining_cursor
                while remaining_cursor_probe is not None:
                    if (
                        not isinstance(remaining_cursor_probe, dict)  # AST_OK: boundary - Mu linked-list authority guard
                        or set(remaining_cursor_probe.keys()) != {"head", "tail"}
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor must be a Mu head/tail list")
                    remaining_projection = remaining_cursor_probe["head"]
                    if (
                        not isinstance(remaining_projection, dict)  # AST_OK: boundary - normalized projection authority guard
                        or set(remaining_projection.keys()) != _KERNEL_PROJECTION_KEYS
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor head must be a normalized projection")
                    remaining_cursor_signature.append(
                        _compute_mu_hash(json.dumps(remaining_projection, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(remaining_projection)
                    )
                    remaining_cursor_probe = remaining_cursor_probe["tail"]
                for context in projection_contexts:
                    if context["cursor_signature"] != remaining_cursor_signature:
                        continue
                    if validation_mode == "domain" and not context["prefix_cleared"]:
                        continue
                    remaining_cursor_bound = True
                    break
            if not remaining_cursor_bound:
                raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
        if isinstance(kernel_state, dict):  # AST_OK: boundary - continuation phase authority guard
            kernel_state_keys = set(kernel_state.keys())
            if "_match_ctx" in kernel_state:
                match_ctx = kernel_state["_match_ctx"]
                if not isinstance(match_ctx, dict):  # AST_OK: boundary - continuation phase authority guard
                    raise TypeError("SECURITY: continuation_state _match_ctx must be a Mu dict")
                if set(match_ctx.keys()) != _KERNEL_MATCH_CTX_KEYS:
                    raise ValueError("SECURITY: continuation_state _match_ctx key set mismatch")
                match_input_hash = (
                    _compute_mu_hash(json.dumps(match_ctx["_input"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                    if trusted_continuation_hash
                    else mu_hash(match_ctx["_input"])
                )
                if match_input_hash != normalized_input_hash:
                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                match_body_hash = (
                    _compute_mu_hash(json.dumps(match_ctx["_body"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                    if trusted_continuation_hash
                    else mu_hash(match_ctx["_body"])
                )
                match_remaining_signature = []
                match_remaining_probe = match_ctx["_remaining"]
                while match_remaining_probe is not None:
                    if (
                        not isinstance(match_remaining_probe, dict)  # AST_OK: boundary - Mu linked-list authority guard
                        or set(match_remaining_probe.keys()) != {"head", "tail"}
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor must be a Mu head/tail list")
                    match_remaining_projection = match_remaining_probe["head"]
                    if (
                        not isinstance(match_remaining_projection, dict)  # AST_OK: boundary - normalized projection authority guard
                        or set(match_remaining_projection.keys()) != _KERNEL_PROJECTION_KEYS
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor head must be a normalized projection")
                    match_remaining_signature.append(
                        _compute_mu_hash(json.dumps(match_remaining_projection, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(match_remaining_projection)
                    )
                    match_remaining_probe = match_remaining_probe["tail"]
                match_candidates = []
                for context in projection_contexts:
                    if context["rest_signature"] != match_remaining_signature:
                        continue
                    if context["body_hash"] != match_body_hash:
                        continue
                    if validation_mode == "domain" and not context["prefix_cleared"]:
                        continue
                    match_candidates.append(context)
                if not match_candidates:
                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                if "match" in kernel_state:
                    match_request = kernel_state["match"]
                    if not isinstance(match_request, dict):  # AST_OK: boundary - continuation phase authority guard
                        raise TypeError("SECURITY: continuation_state match request must be a Mu dict")
                    if set(match_request.keys()) != _KERNEL_MATCH_REQUEST_KEYS:
                        raise ValueError("SECURITY: continuation_state match request key set mismatch")
                    request_pattern_bound = False
                    request_pattern_hash = (
                        _compute_mu_hash(json.dumps(match_request["pattern"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(match_request["pattern"])
                    )
                    for context in match_candidates:
                        context_pattern_hash = (
                            _compute_mu_hash(json.dumps(context["projection"]["pattern"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(context["projection"]["pattern"])
                        )
                        if request_pattern_hash == context_pattern_hash:
                            request_pattern_bound = True
                            break
                    if not request_pattern_bound:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                    match_request_value_hash = (
                        _compute_mu_hash(json.dumps(match_request["value"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(match_request["value"])
                    )
                    if match_request_value_hash != normalized_input_hash:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                if (
                    validation_mode == "domain"
                    and
                    kernel_state_keys == _KERNEL_MATCH_STATE_KEYS
                    and
                    kernel_state.get("mode") == "match"
                    and kernel_state.get("pattern_focus") is None
                    and kernel_state.get("value_focus") is None
                    and kernel_state.get("stack") is None
                ):
                    success_bound_to_input = False
                    for context in match_candidates:
                        match_result = context["match_result"]
                        if (
                            not isinstance(match_result, dict)  # AST_OK: boundary - VM match terminal guard
                            or match_result.get("_mode") != "match_done"
                            or match_result.get("_status") != "success"
                        ):
                            continue
                        if "bindings" not in kernel_state:
                            raise TypeError("SECURITY: continuation_state binding cursor must be a Mu dict or null")
                        actual_bindings = kernel_state["bindings"]
                        actual_bindings_hash = (
                            _compute_mu_hash(json.dumps(actual_bindings, sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(actual_bindings)
                        )
                        expected_bindings_hash = (
                            _compute_mu_hash(json.dumps(match_result["_bindings"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(match_result["_bindings"])
                        )
                        if actual_bindings_hash == expected_bindings_hash:
                            success_bound_to_input = True
                            break
                    if not success_bound_to_input:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                if kernel_state.get("_mode") == "match_done":
                    status = kernel_state.get("_status")
                    if status == "success" and validation_mode == "domain":
                        success_bound_to_input = False
                        for context in match_candidates:
                            match_result = context["match_result"]
                            if (
                                not isinstance(match_result, dict)  # AST_OK: boundary - VM match terminal guard
                                or match_result.get("_mode") != "match_done"
                                or match_result.get("_status") != "success"
                            ):
                                continue
                            if "_bindings" not in kernel_state:
                                raise TypeError("SECURITY: continuation_state binding cursor must be a Mu dict or null")
                            actual_bindings = kernel_state["_bindings"]
                            actual_bindings_hash = (
                                _compute_mu_hash(json.dumps(actual_bindings, sort_keys=True, ensure_ascii=False, allow_nan=False))
                                if trusted_continuation_hash
                                else mu_hash(actual_bindings)
                            )
                            expected_bindings_hash = (
                                _compute_mu_hash(json.dumps(match_result["_bindings"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                                if trusted_continuation_hash
                                else mu_hash(match_result["_bindings"])
                            )
                            if actual_bindings_hash == expected_bindings_hash:
                                success_bound_to_input = True
                                break
                        if not success_bound_to_input:
                            raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                    elif status == "success":
                        pass
                    elif status == "no_match":
                        if validation_mode == "domain":
                            for context in match_candidates:
                                match_result = context["match_result"]
                                if (
                                    isinstance(match_result, dict)  # AST_OK: boundary - VM match terminal guard
                                    and match_result.get("_mode") == "match_done"
                                    and match_result.get("_status") == "success"
                                ):
                                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                    else:
                        raise ValueError("SECURITY: continuation_state match_done status mismatch")

            if "_subst_ctx" in kernel_state:
                subst_ctx = kernel_state["_subst_ctx"]
                if not isinstance(subst_ctx, dict):  # AST_OK: boundary - continuation phase authority guard
                    raise TypeError("SECURITY: continuation_state _subst_ctx must be a Mu dict")
                if set(subst_ctx.keys()) != _KERNEL_SUBST_CTX_KEYS:
                    raise ValueError("SECURITY: continuation_state _subst_ctx key set mismatch")
                subst_input_hash = (
                    _compute_mu_hash(json.dumps(subst_ctx["_input"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                    if trusted_continuation_hash
                    else mu_hash(subst_ctx["_input"])
                )
                if subst_input_hash != normalized_input_hash:
                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                subst_body = None
                subst_bindings = None
                if "subst" in kernel_state:
                    subst_request = kernel_state["subst"]
                    if not isinstance(subst_request, dict):  # AST_OK: boundary - continuation phase authority guard
                        raise TypeError("SECURITY: continuation_state subst request must be a Mu dict")
                    if set(subst_request.keys()) != _KERNEL_SUBST_REQUEST_KEYS:
                        raise ValueError("SECURITY: continuation_state subst request key set mismatch")
                    subst_body = subst_request["body"]
                    subst_bindings = subst_request["bindings"]
                elif "bindings" in kernel_state:
                    subst_bindings = kernel_state["bindings"]
                subst_body_hash = (
                    (
                        _compute_mu_hash(json.dumps(subst_body, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(subst_body)
                    )
                    if subst_body is not None else None
                )
                subst_remaining_signature = []
                subst_remaining_probe = subst_ctx["_remaining"]
                while subst_remaining_probe is not None:
                    if (
                        not isinstance(subst_remaining_probe, dict)  # AST_OK: boundary - Mu linked-list authority guard
                        or set(subst_remaining_probe.keys()) != {"head", "tail"}
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor must be a Mu head/tail list")
                    subst_remaining_projection = subst_remaining_probe["head"]
                    if (
                        not isinstance(subst_remaining_projection, dict)  # AST_OK: boundary - normalized projection authority guard
                        or set(subst_remaining_projection.keys()) != _KERNEL_PROJECTION_KEYS
                    ):
                        raise TypeError("SECURITY: continuation_state kernel projection cursor head must be a normalized projection")
                    subst_remaining_signature.append(
                        _compute_mu_hash(json.dumps(subst_remaining_projection, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(subst_remaining_projection)
                    )
                    subst_remaining_probe = subst_remaining_probe["tail"]
                subst_candidates = []
                for context in projection_contexts:
                    if context["rest_signature"] != subst_remaining_signature:
                        continue
                    if subst_body_hash is not None and context["body_hash"] != subst_body_hash:
                        continue
                    if validation_mode == "domain" and not context["prefix_cleared"]:
                        continue
                    subst_candidates.append(context)
                if not subst_candidates:
                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                subst_bound_to_input = False
                for context in subst_candidates:
                    match_result = context["match_result"]
                    if (
                        not isinstance(match_result, dict)  # AST_OK: boundary - VM match terminal guard
                        or match_result.get("_mode") != "match_done"
                        or match_result.get("_status") != "success"
                    ):
                        continue
                    expected_bindings = match_result["_bindings"]
                    subst_outcome = _stage0_vm_run_bounded_trusted(
                        subst_bundle,
                        {
                            "subst": {
                                "body": context["projection"]["body"],
                                "bindings": expected_bindings,
                            },
                            "_subst_ctx": {
                                "_input": kernel_entry["_step"],
                                "_remaining": context["rest"],
                            },
                        },
                        terminal_field="_mode",
                        terminal_value="subst_done",
                    )
                    expected_subst = subst_outcome["root"] if subst_outcome["status"] == "terminal" else None
                    if not isinstance(expected_subst, dict) or expected_subst.get("_mode") != "subst_done":  # AST_OK: boundary - VM subst terminal guard
                        continue
                    if kernel_state.get("_mode") == "subst_done":
                        kernel_result_hash = (
                            _compute_mu_hash(json.dumps(kernel_state.get("_result"), sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(kernel_state.get("_result"))
                        )
                        expected_result_hash = (
                            _compute_mu_hash(json.dumps(expected_subst["_result"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(expected_subst["_result"])
                        )
                        if kernel_result_hash == expected_result_hash:
                            subst_bound_to_input = True
                            break
                        continue
                    subst_bindings_hash = (
                        _compute_mu_hash(json.dumps(subst_bindings, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(subst_bindings)
                    )
                    expected_bindings_hash = (
                        _compute_mu_hash(json.dumps(expected_bindings, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(expected_bindings)
                    )
                    bindings_match = subst_bindings_hash == expected_bindings_hash
                    if (
                        bindings_match
                        and kernel_state.get("mode") == "subst"
                        and kernel_state.get("phase") == "result"
                        and kernel_state.get("context") is None
                        and (
                            (
                                _compute_mu_hash(json.dumps(kernel_state.get("focus"), sort_keys=True, ensure_ascii=False, allow_nan=False))
                                if trusted_continuation_hash
                                else mu_hash(kernel_state.get("focus"))
                            )
                            != (
                                _compute_mu_hash(json.dumps(expected_subst["_result"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                                if trusted_continuation_hash
                                else mu_hash(expected_subst["_result"])
                            )
                        )
                    ):
                        bindings_match = False
                    if bindings_match:
                        subst_bound_to_input = True
                        break
                if not subst_bound_to_input and validation_mode == "domain":
                    raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
        if kernel_state_is_object and not projection_hashes:
            expected_empty_state = {
                "_mode": "kernel",
                "_phase": "try",
                "_input": kernel_entry["_step"],
                "_remaining": None,
            }
            kernel_state_hash = (
                _compute_mu_hash(json.dumps(kernel_state, sort_keys=True, ensure_ascii=False, allow_nan=False))
                if trusted_continuation_hash
                else mu_hash(kernel_state)
            )
            expected_empty_state_hash = (
                _compute_mu_hash(json.dumps(expected_empty_state, sort_keys=True, ensure_ascii=False, allow_nan=False))
                if trusted_continuation_hash
                else mu_hash(expected_empty_state)
            )
            if (
                continuation_state["steps_used"] != 1
                or kernel_state_hash != expected_empty_state_hash
            ):
                raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
        elif kernel_state_is_object:
            state_nodes = [kernel_state]
            while state_nodes:
                state_node = state_nodes.pop()
                if not isinstance(state_node, dict):  # AST_OK: boundary - Mu state authority traversal
                    continue
                state_node_keys = set(state_node.keys())
                if state_node_keys == _KERNEL_PROJECTION_KEYS:
                    state_node_hash = (
                        _compute_mu_hash(json.dumps(state_node, sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(state_node)
                    )
                    if state_node_hash not in projection_hashes:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                for projection_cursor_key in ("_projs", "_remaining"):
                    if projection_cursor_key not in state_node:
                        continue
                    projection_cursor = state_node[projection_cursor_key]
                    while projection_cursor is not None:
                        if (
                            not isinstance(projection_cursor, dict)  # AST_OK: boundary - Mu linked-list authority guard
                            or set(projection_cursor.keys()) != {"head", "tail"}
                        ):
                            raise TypeError("SECURITY: continuation_state kernel projection cursor must be a Mu head/tail list")
                        projection_cursor_head_hash = (
                            _compute_mu_hash(json.dumps(projection_cursor["head"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                            if trusted_continuation_hash
                            else mu_hash(projection_cursor["head"])
                        )
                        if projection_cursor_head_hash not in projection_hashes:
                            raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                        projection_cursor = projection_cursor["tail"]
                if "_input" in state_node:
                    state_node_input_hash = (
                        _compute_mu_hash(json.dumps(state_node["_input"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(state_node["_input"])
                    )
                    if state_node_input_hash != normalized_input_hash:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                if "_body" in state_node:
                    state_node_body_hash = (
                        _compute_mu_hash(json.dumps(state_node["_body"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(state_node["_body"])
                    )
                    if state_node_body_hash not in body_hashes:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                if "body" in state_node and "pattern" not in state_node:
                    state_node_body_hash = (
                        _compute_mu_hash(json.dumps(state_node["body"], sort_keys=True, ensure_ascii=False, allow_nan=False))
                        if trusted_continuation_hash
                        else mu_hash(state_node["body"])
                    )
                    if state_node_body_hash not in body_hashes:
                        raise ValueError("SECURITY: continuation_state kernel_state is not bound to supplied projections/input")
                state_nodes.extend(state_node.values())
        if kernel_state_is_object:
            if "_mode" in kernel_state:
                kernel_state_mode = kernel_state.get("_mode")
                if kernel_state_mode == "kernel":
                    if kernel_state_keys != _KERNEL_TRY_STATE_KEYS:
                        raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
                    if kernel_state.get("_phase") != "try":
                        raise ValueError("SECURITY: continuation_state kernel_state phase mismatch")
                elif kernel_state_mode == "match_done":
                    status = kernel_state.get("_status")
                    if status == "success":
                        expected_kernel_state_keys = _KERNEL_MATCH_DONE_SUCCESS_KEYS
                    elif status == "no_match":
                        expected_kernel_state_keys = _KERNEL_MATCH_DONE_NO_MATCH_KEYS
                    else:
                        raise ValueError("SECURITY: continuation_state kernel_state match_done status mismatch")
                    if kernel_state_keys != expected_kernel_state_keys:
                        raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
                elif kernel_state_mode == "subst_done":
                    if kernel_state_keys != _KERNEL_SUBST_DONE_KEYS:
                        raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
                else:
                    raise ValueError("SECURITY: continuation_state kernel_state mode mismatch")
            elif "mode" in kernel_state:
                kernel_state_mode = kernel_state.get("mode")
                if kernel_state_mode == "match":
                    if kernel_state.get("_phase") == "lookup_binding":
                        expected_kernel_state_keys = _KERNEL_MATCH_LOOKUP_STATE_KEYS
                    else:
                        expected_kernel_state_keys = _KERNEL_MATCH_STATE_KEYS
                    if kernel_state_keys != expected_kernel_state_keys:
                        raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
                elif kernel_state_mode == "subst":
                    phase = kernel_state.get("phase")
                    if phase in ("traverse", "result"):
                        expected_kernel_state_keys = _KERNEL_SUBST_TRAVERSE_STATE_KEYS
                    elif phase == "lookup":
                        expected_kernel_state_keys = _KERNEL_SUBST_LOOKUP_STATE_KEYS
                    else:
                        raise ValueError("SECURITY: continuation_state kernel_state phase mismatch")
                    if kernel_state_keys != expected_kernel_state_keys:
                        raise ValueError("SECURITY: continuation_state kernel_state key set mismatch")
                else:
                    raise ValueError("SECURITY: continuation_state kernel_state mode mismatch")
            elif kernel_state_keys not in (_KERNEL_MATCH_REQUEST_STATE_KEYS, _KERNEL_SUBST_REQUEST_STATE_KEYS):
                raise ValueError("SECURITY: continuation_state kernel_state shape mismatch")
            if projection_cursor is None:
                minimum_steps_used = None
                if kernel_state_keys == _KERNEL_MATCH_REQUEST_STATE_KEYS:
                    minimum_steps_used = 2
                elif kernel_state_keys == _KERNEL_SUBST_REQUEST_STATE_KEYS:
                    minimum_steps_used = 5
                elif "_mode" in kernel_state:
                    if kernel_state.get("_mode") == "match_done":
                        minimum_steps_used = 4
                    elif kernel_state.get("_mode") == "subst_done":
                        minimum_steps_used = 8
                elif "mode" in kernel_state:
                    if kernel_state.get("mode") == "match":
                        minimum_steps_used = 3
                    elif kernel_state.get("mode") == "subst":
                        minimum_steps_used = 6
                if minimum_steps_used is not None and raw_steps_used < minimum_steps_used:
                    raise ValueError("SECURITY: continuation_state steps_used is not bound to kernel_state phase")
                if raw_steps_used >= raw_watchdog_cap:
                    raise ValueError("SECURITY: continuation_state steps_used is not bound to watchdog_cap")
        state = continuation_state
        current = state["kernel_state"]
        domain_input = state["domain_input"]
        validator(domain_input, "step_kernel_mu continuation input")
        caller_supplied_fuel = state["fuel_mode"] == "explicit"
        fuel_cursor = state["remaining_fuel"]
        steps_used = state["steps_used"]
        watchdog_cap = state["watchdog_cap"] if state["watchdog_cap"] is not None else max_steps

    # BOOTSTRAP_PRIMITIVE: max_steps
    # Residual watchdog boundary. The continuation carries the consumed-step
    # count; omitted no-fuel compatibility never creates synthetic Mu fuel.
    # See mu/docs/core/BootstrapPrimitives.v0.md
    budget = get_step_budget()
    started_budget = False
    if not budget.is_active():
        budget.start()
        started_budget = True

    try:
        while True:
            # INVARIANT: eval_step is functionally pure — it returns new structures,
            # never mutates its input. current_hash caching depends on this property.
            current_hash = mu_hash_control_cached(current, "step_kernel_mu")
            if caller_supplied_fuel and fuel_cursor is None:
                validator(domain_input, "step_kernel_mu output")
                packet = {
                    "kind": "terminal",
                    "result": {
                        "output": domain_input,
                        "stall": True,
                        "termination_reason": "fuel_exhausted",
                        "steps_used": steps_used,
                        "max_steps": watchdog_cap,
                        "fuel_supplied": True,
                        "fuel_remaining": fuel_cursor,
                        "fuel_exhausted": True,
                    },
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            if steps_used >= watchdog_cap:
                validator(domain_input, "step_kernel_mu output")
                canonical = {
                    "output": domain_input,
                    "stall": True,
                    "termination_reason": "max_steps_exhausted",
                    "steps_used": steps_used,
                    "max_steps": watchdog_cap,
                }
                if caller_supplied_fuel:
                    canonical["fuel_supplied"] = True
                    canonical["fuel_remaining"] = fuel_cursor
                    canonical["fuel_exhausted"] = False
                packet = {
                    "kind": "terminal",
                    "result": canonical,
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            if caller_supplied_fuel:
                assert_mu(fuel_cursor, "step_kernel_mu.kernel_fuel")
                fuel_probe = fuel_cursor
                while fuel_probe is not None:
                    if (
                        not isinstance(fuel_probe, dict)  # ANTICHEAT_OK: linked-list fuel boundary
                        or set(fuel_probe.keys()) != {"head", "tail"}
                    ):
                        raise TypeError("SECURITY: kernel_fuel must be a Mu head/tail linked list")
                    fuel_probe = fuel_probe["tail"]

            # Account for one kernel-driver transition in the shared global budget.
            budget.consume(1)
            # P7-d: shadow mode or cutover mode
            if _STAGE0_VM_CUTOVER:
                result = _step_kernel_with_vm(
                    kernel_bundle, bridge_bundle,
                    match_bundle, subst_bundle, current)
            else:
                result = _step_trusted(kernel_projs, current)

                # P7-d shadow: run VM path too, assert equivalence
                # Disabled when _step_trusted is monkeypatched (shadow is meaningless)
                if _STAGE0_SHADOW_ENABLED:
                    # record_coverage=False prevents double-counting
                    vm_result = _step_kernel_with_vm(
                        kernel_bundle, bridge_bundle,
                        match_bundle, subst_bundle, current,
                        record_coverage=False)
                    host_stalled = result is current
                    vm_stalled = vm_result is current
                    if host_stalled != vm_stalled:
                        raise AssertionError(
                            f"P7-d shadow: polarity divergence — "
                            f"host_stalled={host_stalled}, vm_stalled={vm_stalled}")
                    if not host_stalled:
                        from rcx_pi.selfhost.stage0_vm import _mu_deep_equal  # ANTICHEAT_OK: infra — parity check
                        if not _mu_deep_equal(result, vm_result):
                            raise AssertionError(
                                f"P7-d shadow: output divergence — "
                                f"host={result!r}, vm={vm_result!r}")

            if caller_supplied_fuel:
                fuel_cursor = fuel_cursor["tail"]
            steps_used += 1

            # Terminal state check - simple structural marker detection
            if is_kernel_terminal(result):
                is_stall = result.get("_stall") is True
                output = extract_kernel_result(result, domain_input)
                validator(output, "step_kernel_mu output")
                reason = "kernel_stall" if is_stall else "projection_applied"
                undefined = None
                if is_stall:
                    undefined = make_undefined_motif(
                        op="kernel",
                        lhs=domain_input,
                        rhs=None,
                        cause="no_matching_projection",
                    )
                canonical = {
                    "output": output,
                    "stall": bool(is_stall),
                    "termination_reason": reason,
                    "steps_used": steps_used,
                    "max_steps": watchdog_cap,
                }
                if undefined is not None:
                    canonical["undefined_motif"] = undefined
                if caller_supplied_fuel:
                    canonical["fuel_supplied"] = True
                    canonical["fuel_remaining"] = fuel_cursor
                    canonical["fuel_exhausted"] = False
                packet = {
                    "kind": "terminal",
                    "result": canonical,
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            if (
                isinstance(result, dict)  # AST_OK: boundary - empty projection terminal extraction
                and result.get("_mode") == "kernel"
                and result.get("_phase") == "try"
                and result.get("_remaining") is None
            ):
                validator(domain_input, "step_kernel_mu output")
                canonical = {
                    "output": domain_input,
                    "stall": True,
                    "termination_reason": "kernel_stall",
                    "steps_used": steps_used,
                    "max_steps": watchdog_cap,
                    "undefined_motif": make_undefined_motif(
                        op="kernel",
                        lhs=domain_input,
                        rhs=None,
                        cause="no_matching_projection",
                    ),
                }
                if caller_supplied_fuel:
                    canonical["fuel_supplied"] = True
                    canonical["fuel_remaining"] = fuel_cursor
                    canonical["fuel_exhausted"] = False
                packet = {
                    "kind": "terminal",
                    "result": canonical,
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            # Stall check - no change means no progress.
            # Skip for intermediate kernel states (they have deep nested structures
            # and are mid-execution by definition, not stalls).
            if not is_kernel_intermediate(result):
                result_hash = mu_hash_control_cached(result, "step_kernel_mu.stall")
                if result_hash == current_hash:
                    validator(domain_input, "step_kernel_mu output")
                    canonical = {
                        "output": domain_input,
                        "stall": True,
                        "termination_reason": "hash_stall",
                        "steps_used": steps_used,
                        "max_steps": watchdog_cap,
                    }
                    if caller_supplied_fuel:
                        canonical["fuel_supplied"] = True
                        canonical["fuel_remaining"] = fuel_cursor
                        canonical["fuel_exhausted"] = False
                    packet = {
                        "kind": "terminal",
                        "result": canonical,
                        "continuation": None,
                    }
                    if return_packet:
                        return packet
                    meta = packet["result"]
                    if return_meta:
                        return meta
                    return meta["output"]

            if caller_supplied_fuel and fuel_cursor is None:
                validator(domain_input, "step_kernel_mu output")
                packet = {
                    "kind": "terminal",
                    "result": {
                        "output": domain_input,
                        "stall": True,
                        "termination_reason": "fuel_exhausted",
                        "steps_used": steps_used,
                        "max_steps": watchdog_cap,
                        "fuel_supplied": True,
                        "fuel_remaining": fuel_cursor,
                        "fuel_exhausted": True,
                    },
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            if steps_used >= watchdog_cap:
                validator(domain_input, "step_kernel_mu output")
                canonical = {
                    "output": domain_input,
                    "stall": True,
                    "termination_reason": "max_steps_exhausted",
                    "steps_used": steps_used,
                    "max_steps": watchdog_cap,
                }
                if caller_supplied_fuel:
                    canonical["fuel_supplied"] = True
                    canonical["fuel_remaining"] = fuel_cursor
                    canonical["fuel_exhausted"] = False
                packet = {
                    "kind": "terminal",
                    "result": canonical,
                    "continuation": None,
                }
                if return_packet:
                    return packet
                meta = packet["result"]
                if return_meta:
                    return meta
                return meta["output"]

            projection_cursor = None
            if isinstance(result, dict) and "_remaining" in result:  # AST_OK: boundary - continuation shape construction
                projection_cursor = {
                    "tag": "kernel_projection_cursor",
                    "version": 1,
                    "position": steps_used,
                    "exhausted": result.get("_remaining") is None,
                }
            continuation = {
                "tag": "kernel_driver_continuation_state",
                "version": 1,
                "kernel_state": result,
                "domain_input": domain_input,
                "projection_cursor": projection_cursor,
                "remaining_fuel": fuel_cursor if caller_supplied_fuel else None,
                "fuel_mode": "explicit" if caller_supplied_fuel else "omitted_compatibility",
                "steps_used": steps_used,
                "watchdog_cap": watchdog_cap,
                "terminal": {
                    "reached": False,
                    "reason": None,
                    "error": None,
                },
            }
            packet = {
                "kind": "continuation",
                "result": None,
                "continuation": continuation,
            }
            if return_packet:
                return packet

            # BOUNDARY: legacy public no-fuel behavior explicitly drives returned
            # Mu continuation data through the already prepared caller context.
            # This does not seed or disguise Mu fuel and does not re-enter the
            # public validation/normalization boundary for self-returned packets.
            state = packet["continuation"]
            current = state["kernel_state"]
            domain_input = state["domain_input"]
            caller_supplied_fuel = state["fuel_mode"] == "explicit"
            fuel_cursor = state["remaining_fuel"]
            steps_used = state["steps_used"]
            watchdog_cap = state["watchdog_cap"] if state["watchdog_cap"] is not None else max_steps
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
        if not isinstance(proj, dict):  # AST_OK:infra — type guard
            continue
        proj_id = proj.get("id", "")
        if isinstance(proj_id, str) and proj_id.startswith("kernel."):  # AST_OK:infra — type guard
            raise ValueError(
                f"SECURITY: step_algorithm_with_bridge expects algorithm/domain projections only, "
                f"got kernel projection at index {i}: {proj_id}"
            )
    _validate_projection_fields(
        projections, validate_algorithm_runtime_fields, "step_algorithm_with_bridge"
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
    if not isinstance(projection, dict):  # AST_OK:infra — type guard
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
        if isinstance(current, dict):  # AST_OK:infra — type guard
            if set(current.keys()) == {"var"} and isinstance(current["var"], str):  # AST_OK:infra — type guard
                name = current["var"]
                var_counts[name] = var_counts.get(name, 0) + 1
            else:
                stack.extend(current.values())
        elif isinstance(current, list):  # AST_OK:infra — type guard
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
        if not isinstance(proj, dict):  # AST_OK:infra — type guard
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


# BOUNDARY: Outer loop scaffolding — calls step_kernel_mu(return_packet=True)
# but is NOT on the kernel execution path. Kernel path:
# step_kernel_mu(return_packet=True) → _step_trusted → _apply_projection_trusted
# → _stage0_match/_stage0_substitute. run_mu is L3 boundary scaffolding (repeat-until-stall).
# Reclassified P7W5: was @host_iteration, now BOUNDARY.
def run_mu(projections: list[Mu], initial: Mu, max_steps: int = 1000) -> tuple[Mu, list[dict], bool]:
    """
    BOUNDARY: Run projections repeatedly until stall or max steps (core, linear-only).
    Off kernel path — outer driver loop. Reclassified P7W5.

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
    _validate_entry_point(
        projections, initial, validate_no_kernel_reserved_fields, "run_mu",
        reject_nonlinear=True,
    )

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


# BOUNDARY: Trace infrastructure — calls step_kernel_mu(return_packet=True) but is NOT on the kernel
# execution path. Phase 8d structural trace for EngineNews.
# Reclassified P7W5: was @host_iteration, now BOUNDARY.
def run_mu_structural(
    projections: list[Mu],
    initial: Mu,
    max_steps: int = 1000,
    *,
    kernel_mode: str = "bridge",
    validation_mode: str = "domain",
    trace_output: bool = True,
    reject_nonlinear: bool = False,
) -> dict:
    """
    BOUNDARY: Run projections with structural trace accumulation (Phase 8d).
    Off kernel path — trace infrastructure. Reclassified P7W5.
    Default kernel discipline: kernel_mode="bridge", validation_mode="domain".

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
    if validation_mode == "domain":
        validator = validate_no_kernel_reserved_fields
    elif validation_mode == "algorithm_runtime":
        validator = validate_algorithm_runtime_fields
    else:
        raise ValueError(
            "SECURITY: invalid validation_mode. Expected 'domain' or 'algorithm_runtime', "
            f"got: {validation_mode}"
        )
    _validate_entry_point(
        projections,
        initial,
        validator,
        "run_mu_structural",
        reject_nonlinear=reject_nonlinear,
    )

    budget = get_step_budget()
    started_budget = False
    if not budget.is_active():
        budget.start()
        started_budget = True

    trace_entries = []
    current = initial
    # INVARIANT: step_kernel_mu(return_packet=True) returns new structures — current_hash caching is safe.
    current_hash = mu_hash_control_cached(initial, "run_mu_structural")

    try:
        for i in range(max_steps):
            # Gate 5 parity: run the same bridge-backed kernel path as production.
            # BOUNDARY: trace runner drives explicit kernel continuation values.
            packet = step_kernel_mu(
                projections,
                current,
                kernel_mode=kernel_mode,
                validation_mode=validation_mode,
                return_meta=True,
                return_packet=True,
            )
            while packet["kind"] == "continuation":
                packet = step_kernel_mu(
                    projections,
                    current,
                    kernel_mode=kernel_mode,
                    validation_mode=validation_mode,
                    return_meta=True,
                    continuation_state=packet["continuation"],
                    return_packet=True,
                )
            meta = packet["result"]
            result = meta["output"]
            # Resolve matched projection ID: use Stage 0 match (proven equivalent
            # to match.v2 by 33 parity tests in test_self_hosting_v0.py).
            # First-match-wins: the first projection whose pattern matches current
            # is the one the kernel applied.  O(N) match calls vs the previous
            # O(N*K) step_kernel_mu calls per step.
            matched_id = None
            if trace_output and meta["termination_reason"] == "projection_applied":
                for proj in projections:
                    if isinstance(proj, dict) and "pattern" in proj:  # AST_OK: infra — trace ID resolution
                        bindings = stage0_match(proj["pattern"], current)
                        if bindings is not NO_MATCH:
                            matched_id = proj.get("id")
                            break

            validator(result, "run_mu_structural output")
            if trace_output:
                trace_entries.append({
                    "step": i,
                    "state": current,
                    "projection": matched_id
                })

            # Check for stall (no change)
            result_hash = mu_hash_control_cached(result, "run_mu_structural.stall")
            if result_hash == current_hash:
                if trace_output:
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
        if trace_output:
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
