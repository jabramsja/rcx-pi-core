"""
Engine Pipeline — Boot2 (Engine Orchestration)

This module contains the engine orchestration layer (Boot2), extracted from
step_mu.py to enforce the 3-layer bootstrap model:

  Boot0 (eval_seed.py):  Raw stepping, no seeds
  Boot1 (step_mu.py):    Kernel orchestration (step_kernel_mu, apply_mu, run_mu)
  Boot2 (THIS FILE):     Engine orchestration (run_engine_pipeline, boundary effects,
                          hemisphere routing, metabolization)

Dependency direction: Boot2 → Boot1 → Boot0 (one-way, enforced by
tools/checks/check_boot_layer_boundaries.py).

The JS substrate already has this separation:
  Boot1: engine/kernel.js + core/terminal_classification.js
  Boot2: engine/pipeline.js + engine/routing.js

This extraction achieves Python↔JS structural parity for the bootstrap model.

IMPORTANT: This module must NOT be imported by Boot0 (eval_seed.py) or
Boot1 (step_mu.py). Callers import directly from engine_pipeline.
"""

from __future__ import annotations

from .eval_seed import step as eval_step, _step_trusted
from .mu_type import Mu, assert_mu, is_mu, mu_hash, mu_hash_control, mu_hash_control_cached
from .seed_integrity import (
    get_seed_path,
    load_verified_seed,
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
    SEED_REGISTRY_MANIFEST,
    RUN_ALGORITHM_AUTHORITY_SEEDS,
)
from .projection_loader import make_projection_loader

# Boot1 imports — engine_pipeline (Boot2) depends on kernel orchestration (Boot1).
# This is the allowed direction: Boot2 → Boot1.
from .step_mu import (
    RcxEngineError,
    classify_terminal_kind,
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
    run_mu,
    run_mu_structural,
    run_algorithm_meta_circular,
    _run_sub_algorithm,
    _STRUCTURAL_NUMBER_ADD_PROJECTIONS,
    _SN_ZERO,
    _SN_ONE,
    _SN_PROJECTION_STEP_LIMIT,
    _get_hemisphere_keys,
    _get_hemisphere_key_order,
    _load_tc_projections,
)


# =============================================================================
# Boundary Operations (A10: seed-derived authority)
# =============================================================================

# Cached loader for engine seed (A10: boundary dispatch authority displacement)
_load_engine_projections, _clear_engine_proj_cache = make_projection_loader("rcx_engine.v1.json")
_MAX_BOUNDARY_TRACE_STEPS = 10000


# Boundary operation set — seed-derived from rcx_engine.v1.json (A10 displacement).
# Authority lives in engine projection bodies (body._boundary_request.operation).
# _EXPECTED_BOUNDARY_OPS is a fail-closed safety guard (duplicate literals),
# NOT authority-of-truth. Authority is seed-derived; expected set catches corruption.
_boundary_ops_cache: frozenset | None = None
_EXPECTED_BOUNDARY_OPS = frozenset({"run_trace", "hash_trace", "run_algorithm"})  # AST_OK: constant — fail-closed guard


def _load_boundary_ops() -> frozenset[str]:  # AST_OK: infra — seed-derived boundary ops
    """Derive valid boundary operations from rcx_engine.v1.json (cached).

    Scans projection bodies for _boundary_request.operation literal strings.
    Fail-closed: raises RcxEngineError if seed yields unexpected op set.
    """
    global _boundary_ops_cache
    if _boundary_ops_cache is not None:
        return _boundary_ops_cache
    projs = _load_engine_projections()
    ops: set[str] = set()  # AST_OK: infra — seed-derived op collection
    for p in projs:  # AST_OK: infra — seed projection scan
        body = p.get("body")
        if isinstance(body, dict):
            br = body.get("_boundary_request")
            if isinstance(br, dict):
                if "operation" in br:
                    op = br["operation"]
                    if not isinstance(op, str):
                        raise RcxEngineError("input.shape_mismatch",
                            f"engine seed invariant: boundary op must be string, "
                            f"got {type(op).__name__} in projection {p.get('id', '?')}")
                    ops.add(op)
    op_set = frozenset(ops)
    # Fail-closed invariants (A10 Requirement A)
    if len(op_set) != 3:
        raise RcxEngineError("input.shape_mismatch",
            f"engine seed invariant: expected 3 boundary ops, got {len(op_set)}")
    if op_set != _EXPECTED_BOUNDARY_OPS:
        raise RcxEngineError("input.shape_mismatch",
            f"engine seed invariant: expected {sorted(_EXPECTED_BOUNDARY_OPS)}, got {sorted(op_set)}")
    _boundary_ops_cache = op_set
    return _boundary_ops_cache


def _clear_boundary_ops_cache() -> None:
    """Clear engine projection and boundary ops caches (for testing)."""
    global _boundary_ops_cache
    _clear_engine_proj_cache()
    _boundary_ops_cache = None


# =============================================================================
# Re-entry Payload Validation
# =============================================================================

def _validate_reentry_payload(payload: object, context: str) -> None:
    """Validate shape/type of _run_engine or _tail_call re-entry payload.

    Fail-closed: raises RcxEngineError (not raw TypeError/KeyError) on
    malformed payloads. Checks structure first, then reserved-field depth.
    """
    if not isinstance(payload, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context}: re-entry payload must be dict, got {type(payload).__name__}",
        )
    if "projections" not in payload:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context}: re-entry payload missing required key 'projections'",
        )
    if "input" not in payload:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context}: re-entry payload missing required key 'input'",
        )
    if not isinstance(payload["projections"], list):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context}: re-entry payload 'projections' must be list, "
            f"got {type(payload['projections']).__name__}",
        )
    if not is_mu(payload["input"]):
        raise RcxEngineError(
            "input.invalid_type",
            f"{context}: re-entry payload 'input' is not valid Mu, "
            f"got {type(payload['input']).__name__}",
        )
    frozen = payload.get("frozen")
    if frozen is not None:
        if not is_mu(frozen):
            raise RcxEngineError(
                "input.invalid_type",
                f"{context}: re-entry payload 'frozen' is not valid Mu, "
                f"got {type(frozen).__name__}",
            )
    if "max_steps" in payload:
        max_steps = payload["max_steps"]
        if not isinstance(max_steps, dict) or set(max_steps.keys()) != {"_num"}:
            raise RcxEngineError(
                "input.invalid_type",
                f"{context}: re-entry payload 'max_steps' must be a "
                f"StructuralNumbers numeral, got {type(max_steps).__name__}",
            )
        _sn_node = max_steps["_num"]
        _sn_seen_nodes: set[int] = set()
        while _sn_node is not None:
            if not isinstance(_sn_node, dict):
                raise RcxEngineError(
                    "input.invalid_type",
                    f"{context}: re-entry payload 'max_steps' malformed StructuralNumbers numeral",
                )
            _sn_node_id = id(_sn_node)
            if _sn_node_id in _sn_seen_nodes:
                raise RcxEngineError(
                    "input.invalid_type",
                    f"{context}: re-entry payload 'max_steps' cyclic StructuralNumbers numeral",
                )
            _sn_seen_nodes.add(_sn_node_id)
            if len(_sn_node) != 1:
                raise RcxEngineError(
                    "input.invalid_type",
                    f"{context}: re-entry payload 'max_steps' numeral node must have one key",
                )
            _sn_digit_key, _sn_digit_value = next(iter(_sn_node.items()))
            if _sn_digit_key == "xH":
                if _sn_digit_value is not None:
                    raise RcxEngineError(
                        "input.invalid_type",
                        f"{context}: re-entry payload 'max_steps' malformed xH terminator",
                    )
                break
            if _sn_digit_key in ("xI", "xO"):
                if _sn_digit_value is None:
                    raise RcxEngineError(
                        "input.invalid_type",
                        f"{context}: re-entry payload 'max_steps' malformed StructuralNumbers numeral",
                    )
                _sn_node = _sn_digit_value
                continue
            raise RcxEngineError(
                "input.invalid_type",
                f"{context}: re-entry payload 'max_steps' malformed StructuralNumbers digit",
            )
    validate_no_kernel_reserved_fields(payload["input"], f"{context} input")
    if frozen is not None:
        validate_no_kernel_reserved_fields(frozen, f"{context} frozen")


# =============================================================================
# JS CORE Seed Registries (Ontology Promotion)
# =============================================================================

# JS CORE seed registry keys are derived from the verified canonical manifest,
# matching seed_loader.js CORE_* derivation from record.js_core_locked.
_JS_CORE_SEED_REGISTRY_KEYS = frozenset(  # AST_OK: infra — manifest-derived JS CORE registry view
    seed_name
    for seed_name, record in SEED_REGISTRY_MANIFEST["seeds"].items()
    if record["js_core_locked"]
)


def _derive_opromo_fully_locked_seeds() -> frozenset:  # AST_OK: infra — A13 lock derivation
    """Derive OPROMO fully-locked seed set by registry intersection.

    Rule (same shape as JS isFullyLockedSeed):
        locked = JS_CORE_checksums ∩ JS_CORE_projection_ids ∩ PY_checksums ∩ PY_projection_ids

    This ensures a seed is accepted only if it is verification-locked in BOTH substrates.
    Returns frozenset of seed names.
    """
    return (
        _JS_CORE_SEED_REGISTRY_KEYS  # Covers both checksums and projection_ids (collapsed)
        & _JS_CORE_SEED_REGISTRY_KEYS  # Identity — kept for parity with JS intersection shape
        & frozenset(SEED_CHECKSUMS.keys())  # AST_OK: infra — registry key extraction
        & frozenset(EXPECTED_PROJECTION_IDS.keys())  # AST_OK: infra — registry key extraction
    )


_OPROMO_FULLY_LOCKED_SEEDS = _derive_opromo_fully_locked_seeds()


# =============================================================================
# Ontology Promotion Validation (A12)
# =============================================================================

def _validate_ontology_promotion_record(record: dict, context_str: str) -> None:  # AST_OK: infra — A12 ontology promotion enforcement
    """Validate an ontology promotion record against INV_OPROMO_1..4.

    Fail-closed: raises RcxEngineError (not raw TypeError/KeyError) on
    any invariant violation. Check order: INV_OPROMO_4 (shape) → 1 → 2 → 3.
    """
    # Entry guard: reject non-dict input before any key access
    if not isinstance(record, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: record must be dict, got {type(record).__name__}",
        )
    # --- INV_OPROMO_4: shape/provenance (all required fields + types) ---
    required_keys = (
        "witness_traces", "seed_configs", "closure_structure",
        "perturbation_log", "derivation_timestamp", "substrate_versions",
        "tau_lineage", "authority",
    )
    for key in required_keys:
        if key not in record:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_4 missing required field '{key}'",
            )

    witness_traces = record["witness_traces"]
    seed_configs = record["seed_configs"]
    closure_structure = record["closure_structure"]
    perturbation_log = record["perturbation_log"]
    derivation_timestamp = record["derivation_timestamp"]
    substrate_versions = record["substrate_versions"]
    tau_lineage = record["tau_lineage"]
    authority = record["authority"]

    if not isinstance(witness_traces, list):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'witness_traces' must be list, "
            f"got {type(witness_traces).__name__}",
        )
    if not isinstance(seed_configs, list):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'seed_configs' must be list, "
            f"got {type(seed_configs).__name__}",
        )
    if not isinstance(closure_structure, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'closure_structure' must be dict, "
            f"got {type(closure_structure).__name__}",
        )
    if not isinstance(perturbation_log, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'perturbation_log' must be dict, "
            f"got {type(perturbation_log).__name__}",
        )
    if not isinstance(derivation_timestamp, str) or not derivation_timestamp:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'derivation_timestamp' must be non-empty string",
        )
    if not isinstance(substrate_versions, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'substrate_versions' must be dict, "
            f"got {type(substrate_versions).__name__}",
        )
    for sv_key in ("python", "js"):
        if sv_key not in substrate_versions or not isinstance(substrate_versions[sv_key], str):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_4 'substrate_versions' must contain string key '{sv_key}'",
            )
    if not isinstance(tau_lineage, list) or len(tau_lineage) == 0:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'tau_lineage' must be non-empty list",
        )
    if not isinstance(authority, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'authority' must be dict, "
            f"got {type(authority).__name__}",
        )
    for auth_key in ("source", "seed_file", "projection_ids"):
        if auth_key not in authority:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_4 'authority' missing required field '{auth_key}'",
            )
    if not isinstance(authority["source"], str):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'authority.source' must be string",
        )
    if not isinstance(authority["seed_file"], str):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'authority.seed_file' must be string",
        )
    if not isinstance(authority["projection_ids"], list) or len(authority["projection_ids"]) == 0:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4 'authority.projection_ids' must be non-empty list",
        )
    for pid in authority["projection_ids"]:
        if not isinstance(pid, str):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_4 'authority.projection_ids' entries must be strings",
            )

    # --- INV_OPROMO_1: recurrence witnesses ---
    # Type-validate seed_configs entries before set()/sorted() to prevent raw TypeError
    for i, sc in enumerate(seed_configs):
        if not isinstance(sc, str):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_1 seed_configs[{i}] must be string, "
                f"got {type(sc).__name__}",
            )
    if len(witness_traces) < 2:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_1 requires >= 2 witness_traces, got {len(witness_traces)}",
        )
    witness_pairs = set()
    witness_seed_configs = set()
    for i, w in enumerate(witness_traces):
        if not isinstance(w, dict):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_1 witness_traces[{i}] must be dict",
            )
        if "trace_id" not in w or not isinstance(w["trace_id"], str):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_1 witness_traces[{i}] must have string 'trace_id'",
            )
        if "seed_config" not in w or not isinstance(w["seed_config"], str):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_1 witness_traces[{i}] must have string 'seed_config'",
            )
        pair = (w["seed_config"], w["trace_id"])
        if pair in witness_pairs:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_1 duplicate (seed_config, trace_id) pair: {pair}",
            )
        witness_pairs.add(pair)
        witness_seed_configs.add(w["seed_config"])

    if len(witness_seed_configs) < 2:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_1 requires >= 2 distinct seed_configs in witnesses, "
            f"got {len(witness_seed_configs)}",
        )
    seed_config_set = set(seed_configs)
    if seed_config_set != witness_seed_configs:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_1 seed_configs field inconsistent with witness_traces",
        )

    # --- INV_OPROMO_2: perturbation stability ---
    for plog_key in ("removals_tested", "additions_tested", "pattern_survived_all"):
        if plog_key not in perturbation_log:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: INV_OPROMO_2 'perturbation_log' missing '{plog_key}'",
            )
    removals = perturbation_log["removals_tested"]
    additions = perturbation_log["additions_tested"]
    survived = perturbation_log["pattern_survived_all"]
    if not isinstance(removals, list) or len(removals) == 0:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_2 'removals_tested' must be non-empty list",
        )
    if not isinstance(additions, list) or len(additions) == 0:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_2 'additions_tested' must be non-empty list",
        )
    if survived is not True:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_2 'pattern_survived_all' must be true, got {survived!r}",
        )

    # --- INV_OPROMO_3: host cannot mint (seed authority only) ---
    if authority["source"] != "seed":
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_3 authority.source must be 'seed', "
            f"got {authority['source']!r}",
        )
    seed_file = authority["seed_file"]
    # Full-lock gate: restrict to seeds that are verification-locked in BOTH substrates.
    # Must match JS isFullyLockedSeed() (intersection of CORE_SEED_CHECKSUMS ∩ CORE_SEED_PROJECTION_IDS).
    # Python SEED_CHECKSUMS covers all 17 seeds; JS CORE only covers 3.
    # Parity requires both substrates to accept the same set.
    if seed_file not in _OPROMO_FULLY_LOCKED_SEEDS:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_3 seed not verification-locked: {seed_file}",
        )
    try:
        seed_path = get_seed_path(seed_file)
        seed = load_verified_seed(seed_path)
        seed_proj_ids = {p["id"] for p in seed["projections"]}  # AST_OK: infra — set comp for O(1) lookup, not Mu data
    except Exception as exc:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_3 seed resolution failed for "
            f"'{seed_file}': {exc}",
        ) from exc
    missing_ids = [pid for pid in authority["projection_ids"] if pid not in seed_proj_ids]  # AST_OK: infra — filter for error reporting
    if missing_ids:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_3 projection_ids not found in seed "
            f"'{seed_file}': {missing_ids}",
        )


def _build_ontology_promotion_candidate(  # AST_OK: infra — producer-side record assembly
    evidence: dict | None,
    context_str: str,
) -> dict:
    """Build an ontology promotion candidate record from runtime evidence.

    Assembles the 8-field record required by the A12 validator.
    Auto-generates derivation_timestamp and substrate_versions.
    Enforces authority.source = "seed" regardless of evidence input.
    """
    if not isinstance(evidence, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: evidence must be dict, "
            f"got {type(evidence).__name__}",
        )
    required_keys = (
        "witness_traces", "seed_configs", "closure_structure",
        "perturbation_log", "tau_lineage", "authority",
    )
    for key in required_keys:
        if key not in evidence:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: evidence missing required key '{key}'",
            )
    authority = evidence["authority"]
    if not isinstance(authority, dict):
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: evidence 'authority' must be dict, "
            f"got {type(authority).__name__}",
        )
    for auth_key in ("seed_file", "projection_ids"):
        if auth_key not in authority:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"{context_str}: evidence 'authority' missing '{auth_key}'",
            )

    seed_file = authority["seed_file"]

    # Correction #5: full-lock gate (early reject, before checksum lookup).
    if seed_file not in _OPROMO_FULLY_LOCKED_SEEDS:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_3/producer seed not verification-locked: "
            f"'{seed_file}'",
        )

    # Correction #1: typed fail-closed for seed checksum resolution.
    checksum = SEED_CHECKSUMS.get(seed_file)
    if checksum is None:
        raise RcxEngineError(
            "input.shape_mismatch",
            f"{context_str}: INV_OPROMO_4/producer seed checksum not found "
            f"for '{seed_file}' — seed not in SEED_CHECKSUMS registry",
        )

    return {
        "witness_traces": evidence["witness_traces"],
        "seed_configs": evidence["seed_configs"],
        "closure_structure": evidence["closure_structure"],
        "perturbation_log": evidence["perturbation_log"],
        "tau_lineage": evidence["tau_lineage"],
        "derivation_timestamp": "derived:" + checksum,
        "substrate_versions": {"python": checksum, "js": checksum},
        "authority": {
            "source": "seed",
            "seed_file": authority["seed_file"],
            "projection_ids": authority["projection_ids"],
        },
    }


# =============================================================================
# Engine Terminal Detection (Boot2 layer)
# =============================================================================

def _is_engine_terminal(value: Mu) -> bool:  # AST_OK: infra — engine terminal shape detection
    """Check if engine has produced its final unwrapped result.

    After engine.exhaustion_done → engine.unwrap, the output has shape:
    {value, closure_detected, tau_step, exhaustion_detected, operator_frozen,
     frozen_set, action, stall}
    Delegates to classify_terminal_kind() for single-source terminal logic.
    """
    return classify_terminal_kind(value) == "engine_terminal"


def _classify_engine_step(next_state: Mu, state: Mu) -> tuple:
    """Classify one engine step output as a transition type.

    Pure function — no observer emissions, no validation, no error raising.
    Callers handle all side effects AFTER classification.

    Wave 4A: Extracted from duplicated if/elif chains in run_engine_pipeline
    (trampoline) and _run_engine_recursive (Boot1).

    Args:
        next_state: result of _step_trusted(engine_projs, state)
        state: previous engine state (for identity-stall detection)

    Returns one of:
        ("stall_terminal", state)       — identity stall, state IS engine terminal
        ("stall_non_terminal", state)   — identity stall, state is NOT terminal
        ("boundary", request_dict)      — _boundary_request detected
        ("reentry", payload_dict)       — _run_engine re-entry envelope
        ("tail_call", payload_dict)     — _tail_call re-entry envelope
        ("terminal", next_state)        — engine terminal result (non-stall)
        ("continue", next_state)        — engine advanced, keep stepping
    """
    # Identity stall — no projection matched
    if next_state is state:
        if _is_engine_terminal(state):
            return ("stall_terminal", state)
        return ("stall_non_terminal", state)

    # Boundary effect request
    if isinstance(next_state, dict) and "_boundary_request" in next_state:  # AST_OK: infra — boundary dispatch check
        return ("boundary", next_state["_boundary_request"])

    # Re-entry envelope (_run_engine)
    if isinstance(next_state, dict) and "_run_engine" in next_state and len(next_state) == 1:  # AST_OK: infra — re-entry detection
        return ("reentry", next_state["_run_engine"])

    # Tail-call envelope
    if isinstance(next_state, dict) and "_tail_call" in next_state and len(next_state) == 1:  # AST_OK: infra — tail-call detection
        return ("tail_call", next_state["_tail_call"])

    # Engine terminal result
    if _is_engine_terminal(next_state):
        return ("terminal", next_state)

    # Engine advanced internally
    return ("continue", next_state)


def _derive_engine_exit_reason(engine_result: dict) -> str:  # AST_OK: infra — pure derivation from terminal flags
    """Derive engine_exit_reason from the existing 8-key terminal dict.

    Priority: closure > exhaustion > stall > completed.
    Does NOT modify engine_result.

    Structural displacement (Wave 25): exit-reason derivation now delegated to
    terminal_classify.v1.json seed projections via eval_step().
    """
    tc_projs = _load_tc_projections()
    wrapped = {"_tc_exit": {
        "cd": bool(engine_result.get("closure_detected")),
        "ed": bool(engine_result.get("exhaustion_detected")),
        "st": bool(engine_result.get("stall")),
    }}
    result = eval_step(tc_projs, wrapped)
    return result if isinstance(result, str) else "completed"


# =============================================================================
# Ontology Evidence Collection (A17)
# =============================================================================

def _collect_ontology_evidence(  # BOUNDARY: evidence collection (off kernel path, engine boundary-effect servicing)
    result,
    operation: str,
) -> dict:
    """Build an observation record from a boundary result.

    Extracts trace metadata (trace_len, stall, projection_ids) when available,
    computes control_hash, and timestamps the observation. Returns a 6-field dict.

    Trace walking is structural: evidence_walker.v1.json projections iterate
    the linked-list trace via pattern matching (no host loops). Boundary
    post-processes the walker output: count total, filter non-string pids,
    deduplicate, sort.
    """
    # Control hash of the boundary result.
    control_hash = mu_hash_control_cached(result, "evidence_collector")

    trace_len = None
    stall = None
    projection_ids = None

    if isinstance(result, dict) and "trace" in result:  # AST_OK: infra — boundary type guard
        # Structural trace walking via evidence_walker.v1.json
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        wrapped = {"evidence_walk": {"trace": result["trace"]}}
        walker_result, _trace, _stall = run_mu(projs, wrapped, max_steps=5000)

        # Extract collected entries from walker output
        collected = None
        if isinstance(walker_result, dict) and "evidence_done" in walker_result:  # AST_OK: infra — boundary unwrap
            collected = walker_result["evidence_done"].get("collected")
        elif isinstance(result, dict) and "trace" in result:  # AST_OK: infra — boundary fallback
            # Walker stalled (e.g. head-only trace nodes) — fall back to raw trace drain
            collected = result["trace"]

        # Boundary post-processing: count entries, extract string pids, dedup, sort
        # Mu runtime denormalizes {head, tail} to Python list; handle both formats
        trace_len = 0
        pids = []
        if isinstance(collected, list):  # AST_OK: infra — boundary list drain (Mu denormalization)
            trace_len = len(collected)
            for entry in collected:
                if isinstance(entry, dict):
                    pid = entry.get("projection")
                    if isinstance(pid, str):
                        pids.append(pid)
        else:
            node = collected
            visited_ids: set[int] = set()  # AST_OK: cycle — cycle detection guard
            _max_drain = _MAX_TRACE_ENTRIES_HARD_CAP
            while isinstance(node, dict) and "head" in node:  # AST_OK: infra — boundary linked-list drain (walker output)
                nid = id(node)
                if nid in visited_ids:
                    break  # cyclic — stop draining
                visited_ids.add(nid)
                if trace_len >= _max_drain:
                    break  # iteration cap — defense-in-depth
                trace_len += 1
                entry = node["head"]
                if isinstance(entry, dict):  # AST_OK: infra — boundary type guard
                    pid = entry.get("projection")
                    # C4: only collect string IDs — skip int/dict/None to avoid
                    # TypeError on sorted() and maintain parity with JS.
                    if isinstance(pid, str):  # AST_OK: infra — boundary string filter
                        pids.append(pid)
                node = node.get("tail")
        projection_ids = sorted(set(pids))
        stall = result.get("stall")

    return {
        "operation": operation,
        "trace_len": trace_len,
        "stall": stall,
        "projection_ids": projection_ids,
        "control_hash": control_hash,
        "collected_at": "derived:" + control_hash,
    }


# =============================================================================
# Engine Constants
# =============================================================================

_BOOT1_MAX_REENTRY_DEPTH = 20  # AST_OK: infra — Boot1 recursive re-entry depth limit

# Engine exit reason enum — derived from 8-key terminal flags, priority order.
# Pure function: reads existing flags, never changes the terminal shape.
ENGINE_EXIT_REASONS = frozenset(["closure", "exhaustion", "stall", "completed"])

_MAX_TRACE_ENTRIES_HARD_CAP = 100000  # AST_OK: infra - constant definition


# =============================================================================
# Boundary Effect Dispatch
# =============================================================================

def _boundary_op_run_trace(request, req_input, max_algorithm_iterations):
    """Handler for 'run_trace' boundary operation."""
    if not isinstance(req_input, dict):
        raise RcxEngineError("api.bad_request",
            f"run_trace input must be dict, got {type(req_input).__name__}")
    if "projections" not in req_input or "value" not in req_input:
        raise RcxEngineError("api.bad_request",
            "run_trace input must include 'projections' and 'value'")
    projs = req_input["projections"]
    if not isinstance(projs, (list, tuple)):
        raise RcxEngineError("api.bad_request",
            f"run_trace input 'projections' must be list, got {type(projs).__name__}")
    for i, p in enumerate(projs):
        if not isinstance(p, dict):
            raise RcxEngineError("api.bad_request",
                f"run_trace projection[{i}] must be dict, got {type(p).__name__}")
        if "pattern" not in p or "body" not in p:
            raise RcxEngineError("api.bad_request",
                f"run_trace projection[{i}] must have 'pattern' and 'body' keys")
    # max_steps boundary contract: absent key defaults to the bootstrap clock.
    # Explicit values are StructuralNumbers budget data and fail closed if dirty.
    if "max_steps" in req_input:
        max_steps = req_input["max_steps"]
        if not isinstance(max_steps, dict) or set(max_steps.keys()) != {"_num"}:
            raise RcxEngineError(
                "api.bad_request",
                f"run_trace input 'max_steps' must be a StructuralNumbers numeral, got {type(max_steps).__name__}",
            )
        _sn_node = max_steps["_num"]
        if _sn_node is None:
            trace_max_steps = 0
        else:
            trace_max_steps = 0
            _sn_weight = 1
            _sn_seen_nodes: set[int] = set()
            while True:
                if not isinstance(_sn_node, dict):
                    raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' malformed StructuralNumbers numeral")
                _sn_node_id = id(_sn_node)
                if _sn_node_id in _sn_seen_nodes:
                    raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' cyclic StructuralNumbers numeral")
                _sn_seen_nodes.add(_sn_node_id)
                if len(_sn_node) != 1:
                    raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' numeral node must have one key")
                _sn_digit_key, _sn_digit_value = next(iter(_sn_node.items()))
                if _sn_digit_key == "xH":
                    if _sn_digit_value is not None:
                        raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' malformed xH terminator")
                    trace_max_steps = trace_max_steps + _sn_weight
                    if trace_max_steps > _MAX_BOUNDARY_TRACE_STEPS:
                        raise RcxEngineError(
                            "api.bad_request",
                            f"run_trace input 'max_steps' exceeds boundary cap of {_MAX_BOUNDARY_TRACE_STEPS}",
                        )
                    break
                if _sn_digit_key == "xI":
                    trace_max_steps = trace_max_steps + _sn_weight
                    if trace_max_steps > _MAX_BOUNDARY_TRACE_STEPS:
                        raise RcxEngineError(
                            "api.bad_request",
                            f"run_trace input 'max_steps' exceeds boundary cap of {_MAX_BOUNDARY_TRACE_STEPS}",
                        )
                elif _sn_digit_key != "xO":
                    raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' malformed StructuralNumbers digit")
                if not isinstance(_sn_digit_value, dict):
                    raise RcxEngineError("api.bad_request", "run_trace input 'max_steps' malformed StructuralNumbers numeral")
                _sn_node = _sn_digit_value
                _sn_weight = _sn_weight * 2
                if _sn_weight > _MAX_BOUNDARY_TRACE_STEPS:
                    raise RcxEngineError(
                        "api.bad_request",
                        f"run_trace input 'max_steps' exceeds boundary cap of {_MAX_BOUNDARY_TRACE_STEPS}",
                    )
    else:
        trace_max_steps = 100
    # HF2 parity: hard resource cap to prevent unbounded trace (matches JS MAX_BOUNDARY_TRACE_STEPS).
    if trace_max_steps > _MAX_BOUNDARY_TRACE_STEPS:
        raise RcxEngineError("api.bad_request",
            f"run_trace input 'max_steps' exceeds boundary cap of {_MAX_BOUNDARY_TRACE_STEPS}")
    raw = run_mu_structural(projs, req_input["value"], max_steps=trace_max_steps)
    return {"result": raw["result"], "trace": raw["trace"], "stall": raw["stall"]}


def _boundary_op_hash_trace(request, req_input, max_algorithm_iterations):
    """Handler for 'hash_trace' boundary operation."""
    return hash_trace_for_recurrence(req_input)


def _boundary_op_run_algorithm(request, req_input, max_algorithm_iterations):
    """Handler for 'run_algorithm' boundary operation."""
    if "algorithm" not in request:
        raise RcxEngineError("api.bad_request",
            "run_algorithm request must include 'algorithm'")
    algo_name = request["algorithm"]
    if not isinstance(algo_name, str):
        raise RcxEngineError("api.bad_request",
            f"run_algorithm 'algorithm' must be string, got {type(algo_name).__name__}")
    if algo_name not in RUN_ALGORITHM_AUTHORITY_SEEDS:
        raise RcxEngineError("api.bad_request",
            f"run_algorithm 'algorithm' must be an authorized algorithm seed, "
            f"got {algo_name!r}. Allowed: {sorted(RUN_ALGORITHM_AUTHORITY_SEEDS)}")
    algo_projs = load_verified_seed(get_seed_path(algo_name))["projections"]
    return _run_sub_algorithm(algo_projs, req_input, max_algorithm_iterations)


# === BoundaryRequest / BoundaryResponse Contract (Canonical Machine Contract v3) ===
#
# BoundaryRequest = {operation: str, input: Mu, context: dict, inject_key: str}
# BoundaryResponse = context with result injected at inject_key
#
# Closed operation set (seed-derived authority via _load_boundary_ops()):
#   "run_trace"      — execute trace via run_mu()
#   "hash_trace"     — SHA256 per trace entry
#   "run_algorithm"  — run sub-algorithm via step_kernel_mu()
#
# Dispatch map: operation name → handler function (A10 structural displacement).
# Operation names in keys are structurally paired with handlers; authority for
# which operations are valid comes from seed-derived _load_boundary_ops().
_BOUNDARY_DISPATCH = {
    "run_trace": _boundary_op_run_trace,
    "hash_trace": _boundary_op_hash_trace,
    "run_algorithm": _boundary_op_run_algorithm,
}


def _service_boundary_effect(  # AST_OK: infra — shared boundary effect handler
    request: dict,
    max_algorithm_iterations: int,
    emit_fn,
    step: int,
    state: Mu,
) -> dict:
    """Service a boundary effect request from the engine state machine.

    Shared implementation for both Boot1 recursive and trampoline engine paths.
    Dispatches via seed-derived operation authority (A10): handler-map lookup
    replaces host if/elif dispatch. Validates request shape before any
    field dereference.

    Args:
        request: The _boundary_request dict from engine output.
        max_algorithm_iterations: Max iterations for sub-algorithm convergence.
        emit_fn: Observer emit callback (for error reporting).
        step: Zero-based engine step index (for error reporting).
        state: Current engine state (for error reporting).

    Returns:
        context dict with result injected at inject_key.

    Raises:
        RcxEngineError: On malformed request, reserved inject_key, unknown
            operation, or reserved fields in boundary result.
    """
    # --- Request shape validation (typed fail-closed, no raw KeyError) ---
    if not isinstance(request, dict):
        emit_fn("fail_closed", step, state, error_code="api.bad_request")
        raise RcxEngineError("api.bad_request",
            f"boundary request must be dict, got {type(request).__name__}")
    for key in ("operation", "input", "context", "inject_key"):
        if key not in request:
            emit_fn("fail_closed", step, state, error_code="api.bad_request")
            raise RcxEngineError("api.bad_request",
                f"boundary request missing required key: {key}")
    operation = request["operation"]
    if not isinstance(operation, str):
        emit_fn("fail_closed", step, state, error_code="api.bad_request")
        raise RcxEngineError("api.bad_request",
            f"boundary operation must be string, got {type(operation).__name__}")
    if not isinstance(request["context"], dict):
        emit_fn("fail_closed", step, state, error_code="api.bad_request")
        raise RcxEngineError("api.bad_request",
            f"boundary context must be dict, got {type(request['context']).__name__}")
    inject_key = request["inject_key"]
    if not isinstance(inject_key, str):
        emit_fn("fail_closed", step, state, error_code="api.bad_request")
        raise RcxEngineError("api.bad_request",
            f"boundary inject_key must be string, got {type(inject_key).__name__}")

    req_input = request["input"]
    context = dict(request["context"])

    # SECURITY: inject_key must not be a kernel-reserved field.
    # Prevents boundary requests from forging kernel state.
    if inject_key in KERNEL_RESERVED_FIELDS:
        emit_fn("fail_closed", step, state, error_code="input.reserved_field")
        raise RcxEngineError("input.reserved_field",
            f"SECURITY: inject_key '{inject_key}' is a kernel-reserved field. "
            f"Boundary requests cannot inject reserved fields."
        )

    # --- Seed-derived operation authority (A10 displacement) ---
    valid_ops = _load_boundary_ops()
    if operation not in valid_ops:
        emit_fn("fail_closed", step, state, error_code="api.bad_request")
        raise RcxEngineError("api.bad_request",
            f"Unknown boundary operation: {operation}. "
            f"Valid: {sorted(valid_ops)}")

    # Dispatch coverage invariant: map keys must match seed-derived ops
    if frozenset(_BOUNDARY_DISPATCH) != valid_ops:
        raise RcxEngineError("input.shape_mismatch",
            f"boundary dispatch/authority mismatch: dispatch={sorted(_BOUNDARY_DISPATCH)}, "
            f"seed={sorted(valid_ops)}")

    handler = _BOUNDARY_DISPATCH.get(operation)
    if handler is None:
        raise RcxEngineError("input.shape_mismatch",
            f"boundary dispatch missing handler for validated op: {operation}")
    result = handler(request, req_input, max_algorithm_iterations)

    # INVARIANT: boundary results re-enter engine state (domain level).
    # Domain-level validation is mandatory here regardless of which internal
    # validator the handler used (e.g., algorithm_runtime for run_algorithm).
    # Kernel-reserved fields (_mode, _remaining, _seen, etc.) must not leak
    # into engine state. Both Python and JS enforce this same assumption.
    validate_no_kernel_reserved_fields(result, context=f"boundary_result({operation})")

    # Producer-side ontology promotion candidate (A14): one-shot, opt-in only.
    if context.get("emit_ontology_candidate") is True:
        del context["emit_ontology_candidate"]
        evidence = context.pop("ontology_candidate_evidence", None)
        if not isinstance(result, dict):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"boundary_result({operation}): emit_ontology_candidate requested "
                f"but result is not dict (got {type(result).__name__})",
            )
        # Correction #3: reject overwrite of handler-originated record.
        if "ontology_promotion" in result:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"boundary_result({operation}): emit_ontology_candidate requested "
                f"but result already contains ontology_promotion",
            )
        # F-44: Copy result before mutation to avoid poisoning handler return value
        result = {**result}
        result["ontology_promotion"] = _build_ontology_promotion_candidate(
            evidence,
            f"boundary_result({operation}).ontology_candidate_evidence",
        )
        # Correction #2: re-validate reserved fields after producer attach.
        validate_no_kernel_reserved_fields(
            result, context=f"boundary_result({operation}).post_producer",
        )

    # Ontology promotion enforcement (A12): validate promotion records if present.
    if isinstance(result, dict) and "ontology_promotion" in result:
        promo = result["ontology_promotion"]
        if not isinstance(promo, dict):
            raise RcxEngineError(
                "input.shape_mismatch",
                f"boundary_result({operation}).ontology_promotion must be dict, "
                f"got {type(promo).__name__}",
            )
        _validate_ontology_promotion_record(
            promo,
            f"boundary_result({operation}).ontology_promotion",
        )

    # Evidence collector (A17): one-shot, opt-in only.
    if context.get("collect_ontology_candidate_evidence") is True:
        del context["collect_ontology_candidate_evidence"]
        # C1: no-overwrite guard — reject if observation already exists.
        if "ontology_candidate_observation" in context:
            raise RcxEngineError(
                "input.shape_mismatch",
                f"boundary_result({operation}): collect_ontology_candidate_evidence "
                f"requested but context already contains ontology_candidate_observation",
            )
        context["ontology_candidate_observation"] = _collect_ontology_evidence(
            result, operation,
        )

    # SECURITY: Reject inject_key collision with existing context keys.
    # Prevents boundary requests from silently overwriting domain context state.
    if inject_key in context:
        emit_fn("fail_closed", step, state, error_code="input.inject_key_collision")
        raise RcxEngineError("input.inject_key_collision",
            f"boundary inject_key '{inject_key}' already exists in context. "
            f"Cannot overwrite existing context state.")
    context[inject_key] = result
    return context


# =============================================================================
# Trace Hashing
# =============================================================================

def hash_trace_for_recurrence(trace: Mu, max_entries: int = 10000) -> Mu:  # AST_OK: infra — boundary scaffolding, iterative
    """Add state_hash to each entry in a Mu linked-list trace.

    Walks the trace (boundary operation, not a projection) and adds
    mu_hash(state) to each entry.  This enables recurrence.v2 to compare
    hash strings instead of deep structural equality.

    Uses iterative linked-list traversal to avoid Python recursion limit
    on long traces (max_steps can exceed Python's ~1000 frame limit).

    Args:
        trace: Mu linked-list of trace entries (from run_mu_structural).
        max_entries: Defense-in-depth iteration cap. Clamped to
            _MAX_TRACE_ENTRIES_HARD_CAP (100000) regardless of caller
            request (adversary finding #3). Default 10000 is 100x the
            engine pipeline default (max_steps=100).

    Returns:
        New Mu linked-list with state_hash added to each entry.

    Raises:
        ValueError: If cyclic linked list detected or entry cap exceeded.
    """
    # Collect entries iteratively (avoids recursion limit on long traces)
    # SECURITY: Clamp max_entries to hard cap (adversary finding #3)
    max_entries = min(max_entries, _MAX_TRACE_ENTRIES_HARD_CAP)
    entries = []
    visited = set()  # AST_OK: cycle — cycle detection guard
    current = trace
    while isinstance(current, dict) and "head" in current:
        node_id = id(current)
        if node_id in visited:
            raise ValueError("hash_trace_for_recurrence: cyclic linked list detected")
        visited.add(node_id)
        if len(entries) >= max_entries:
            raise ValueError(f"hash_trace_for_recurrence: trace exceeds {max_entries} entries")
        entry = current["head"]
        if not isinstance(entry, dict) or "state" not in entry:
            raise ValueError(
                "hash_trace_for_recurrence: malformed trace entry "
                f"(expected dict with 'state' key, got {type(entry).__name__}"
                + (f" without 'state'" if isinstance(entry, dict) else "")
                + ")"
            )
        entry = dict(entry)
        entry["state_hash"] = mu_hash_control(entry["state"], "hash_trace_for_recurrence")
        entries.append(entry)
        current = current.get("tail")
    # Rebuild linked list from tail to head
    result = current  # Preserve terminal (None or non-list value)
    for entry in reversed(entries):
        result = {"head": entry, "tail": result}
    return result


# =============================================================================
# Engine Pipeline (Boot1 Recursive + Trampoline)
# =============================================================================

def _run_engine_recursive(  # AST_OK: infra — Boot1 engine loop (iterative re-entry)
    projections: list[Mu],
    input_value: Mu,
    *,
    max_steps: int = 100,
    frozen: Mu = None,
    max_engine_iterations: int = 20,
    max_algorithm_iterations: int = 50,
    observer: list | None = None,
    _recursion_depth: int = 0,
) -> Mu:
    """Boot1 engine pipeline with iterative re-entry (no host recursion).

    Handles engine re-entry signals (_run_engine, _tail_call) via an explicit
    outer loop with frame state update, eliminating host stack dependency.
    Semantically identical to the trampoline path.

    Re-entry depth bounded by _BOOT1_MAX_REENTRY_DEPTH (safety invariant S2).
    Per-entry step budget bounded by remaining_iterations (same as trampoline).
    """
    # Boundary Mu validation: reject non-Mu input before entering engine loop
    assert_mu(input_value, "_run_engine_recursive.input")

    # Observer type guard: reject non-list before engine loop entry
    if observer is not None and not isinstance(observer, list):  # AST_OK: boundary
        raise TypeError(
            f"observer.invalid_type: observer must be list or None, got {type(observer).__name__}"
        )

    engine_projs = load_verified_seed(get_seed_path("rcx_engine.v1.json"))["projections"]

    # Frame state for iterative re-entry
    depth = _recursion_depth
    remaining_iterations = max_engine_iterations
    cur_projections = projections
    cur_input = input_value
    if isinstance(max_steps, bool) or not isinstance(max_steps, int):
        raise RcxEngineError(
            "api.bad_request",
            f"max_steps must be a non-negative integer watchdog, got {type(max_steps).__name__}",
        )
    if max_steps < 0:
        raise RcxEngineError(
            "api.bad_request",
            f"max_steps must be >= 0, got {max_steps}",
        )
    cur_max_steps = _SN_ZERO
    for _ in range(max_steps):
        _sn_add_state = {"_add": {"a": cur_max_steps, "b": _SN_ONE}}
        _sn_add_hash = mu_hash_control_cached(
            _sn_add_state,
            "run_engine_pipeline max_steps.structural_add.initial",
        )
        _sn_add_result = None
        for _sn_guard in range(_SN_PROJECTION_STEP_LIMIT):
            _sn_result = _step_trusted(_STRUCTURAL_NUMBER_ADD_PROJECTIONS, _sn_add_state)
            _sn_result_hash = mu_hash_control_cached(
                _sn_result,
                "run_engine_pipeline max_steps.structural_add.stall",
            )
            if _sn_result_hash == _sn_add_hash:
                _sn_add_result = _sn_result
                break
            _sn_add_state = _sn_result
            _sn_add_hash = _sn_result_hash
        if _sn_add_result is None:
            raise RcxEngineError(
                "execution.max_steps",
                "run_engine_pipeline max_steps: StructuralNumbers add projection did not settle",
            )
        cur_max_steps = _sn_add_result
        if not isinstance(cur_max_steps, dict) or set(cur_max_steps.keys()) != {"_num"}:
            raise RcxEngineError(
                "execution.invalid_result",
                "run_engine_pipeline max_steps: StructuralNumbers ADD produced malformed numeral",
            )
    cur_frozen = frozen

    # Observer event helper — uses mutable depth counter, preserves ts across re-entry
    _obs_ts = [0]

    def _emit(event_name, step_num, state_val, error_code=None, **extra):
        if observer is None:
            return
        state_hash = None
        if isinstance(state_val, (dict, list, str, int, float, bool)) or state_val is None:
            try:
                state_hash = mu_hash(state_val)
            except Exception:
                pass
        event = {
            "event_name": event_name,
            "step": step_num,
            "state_hash": state_hash,
            "error_code": error_code,
            "substrate": "python",
            "timestamp": _obs_ts[0],
            "boot1_depth": depth,
        }
        if extra:
            event.update(extra)
        observer.append(event)
        _obs_ts[0] += 1

    # Running total of engine iterations across all re-entry passes
    _total_iterations = [0]

    # Outer loop: handles re-entry without host recursion
    while True:
        if depth >= _BOOT1_MAX_REENTRY_DEPTH:
            raise RcxEngineError(
                "engine.boot1_depth_exceeded",
                f"Boot1 re-entry depth {depth} exceeds "
                f"limit {_BOOT1_MAX_REENTRY_DEPTH}. Possible infinite re-entry loop."
            )

        # Per-re-entry validation (initial entry already validated above)
        if depth > _recursion_depth:
            assert_mu(cur_input, "_run_engine_recursive.input")

        # obsTs preserved across re-entry (monotonic per-run, like _total_iterations).
        # Feed engine its initial input
        state: Mu = {"_run_engine": {"projections": cur_projections, "input": cur_input, "max_steps": cur_max_steps, "frozen": cur_frozen}}

        # Engine stepping loop (per re-entry pass)
        reentry = False
        for iteration in range(remaining_iterations):  # AST_OK: infra — Boot1 boundary host loop iteration
            # W5A: capture zero-based step index from total counter before increment.
            # All observer emissions in this iteration use step_index (monotonic across re-entry).
            step_index = _total_iterations[0]
            next_state = _step_trusted(engine_projs, state)

            _emit("step_boundary", step_index, state)
            _total_iterations[0] += 1

            # Wave 4A: classify engine step via shared classifier
            transition, payload = _classify_engine_step(next_state, state)

            if transition == "stall_terminal":
                if isinstance(payload, dict):  # AST_OK: infra — terminal signal check
                    if payload.get("closure_detected"):
                        _emit("closure_detected", step_index, payload)
                    if payload.get("stall"):
                        _emit("stall_detected", step_index, payload)
                _emit("engine_terminal", step_index, payload,
                      engine_exit_reason=_derive_engine_exit_reason(payload),
                      engine_iterations_used=_total_iterations[0])
                return payload

            elif transition == "stall_non_terminal":
                _emit("fail_closed", step_index, payload, error_code="engine.stalled_non_terminal")
                raise RcxEngineError(
                    "engine.stalled_non_terminal",
                    f"Boot1 engine stalled at iteration {iteration} (depth {depth}) "
                    f"without producing terminal result. "
                    f"State keys: {sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
                )

            elif transition == "boundary":
                state = _service_boundary_effect(
                    payload,
                    max_algorithm_iterations, _emit, step_index, state,
                )
                continue

            elif transition == "reentry":
                _validate_reentry_payload(payload, "Boot1 _run_engine")
                cur_projections = payload["projections"]
                cur_input = payload["input"]
                cur_max_steps = payload.get("max_steps", cur_max_steps)
                cur_frozen = payload.get("frozen")
                remaining_iterations = remaining_iterations - iteration - 1
                depth += 1
                reentry = True
                break

            elif transition == "tail_call":
                _validate_reentry_payload(payload, "Boot1 _tail_call")
                cur_projections = payload["projections"]
                cur_input = payload["input"]
                cur_max_steps = payload.get("max_steps", cur_max_steps)
                cur_frozen = payload.get("frozen")
                remaining_iterations = remaining_iterations - iteration - 1
                depth += 1
                reentry = True
                break

            elif transition == "terminal":
                if isinstance(payload, dict):  # AST_OK: infra — terminal signal check
                    if payload.get("closure_detected"):
                        _emit("closure_detected", step_index, payload)
                    if payload.get("stall"):
                        _emit("stall_detected", step_index, payload)
                _emit("engine_terminal", step_index, payload,
                      engine_exit_reason=_derive_engine_exit_reason(payload),
                      engine_iterations_used=_total_iterations[0])
                return payload

            else:  # "continue"
                state = payload

        if reentry:
            continue

        # FAIL CLOSED: engine loop exhausted without terminal result
        _emit("fail_closed", _total_iterations[0] - 1, state, error_code="engine.exhausted")
        raise RcxEngineError(
            "engine.exhausted",
            f"Boot1 engine pipeline exhausted {remaining_iterations} iterations "
            f"(depth {depth}) without terminal result. "
            f"State keys: {sorted(state.keys()) if isinstance(state, dict) else type(state).__name__}"
        )


def run_engine_pipeline(  # AST_OK: infra — boundary host loop, services engine state machine
    projections: list[Mu],
    input_value: Mu,
    *,
    max_steps: int = 100,
    frozen: Mu = None,
    max_engine_iterations: int = 20,
    max_algorithm_iterations: int = 50,
    max_iterations: int | None = None,
    observer: list | None = None,
    use_boot1_recursive: bool = True,
    return_meta: bool = False,
) -> Mu:
    """Host loop that drives the engine state machine defined in rcx_engine.v1.json.

    The engine projections emit _boundary_request effects (algebraic effects pattern):
      {_boundary_request: {operation, input, context, inject_key}}

    This function is the GENERIC effect handler. It:
      1. Steps engine projections (eval_seed.step)
      2. If result contains _boundary_request, services the operation
      3. Injects result into context at inject_key
      4. Feeds context back to engine
      5. Repeats until engine produces final result (no _boundary_request)

    The host knows THREE generic operations (not engine-specific phases):
      - run_trace:     generate execution trace
      - hash_trace:    compute mu_hash per entry (boundary primitive)
      - run_algorithm: run a sub-algorithm seed to completion

    Engine projections decide WHAT to do and WHERE to put results.
    Python services these generic boundary primitives; routing decisions
    come from projections, not host code. Any host (JS, Rust, FPGA) can
    implement the same 3 operations.

    Args:
        max_engine_iterations: Max outer loop iterations (engine state machine
            has ~7 phases; 20 is generous). Controls engine orchestration.
        max_algorithm_iterations: Max inner iterations for sub-algorithms
            (recurrence/exhaustion). Controls convergence within a phase.
        max_iterations: DEPRECATED — if provided, sets both engine and algorithm
            limits for backwards compatibility. Will be removed.
        return_meta: When True, returns metadata envelope with fields:
            `engine_result` (8-key dict, unchanged), `engine_exit_reason` (str),
            `engine_iterations_used` (int), `max_engine_iterations` (int).
            Reason enum: closure, exhaustion, stall, completed.

    Raises:
        RuntimeError: If engine loop exhausts without producing terminal result.
    """
    # Boundary Mu validation: reject non-Mu input before entering engine loop
    assert_mu(input_value, "run_engine_pipeline.input")

    # SECURITY: Reject domain input containing kernel-reserved fields.
    # Engine pipeline is a public entry point — user input must be clean.
    validate_no_kernel_reserved_fields(input_value, "run_engine_pipeline input")

    # SECURITY: Validate frozen for kernel-reserved fields (parity with input validation)
    if frozen is not None:
        validate_no_kernel_reserved_fields(frozen, "run_engine_pipeline frozen")

    # Observer type guard: reject non-list before engine loop entry
    if observer is not None and not isinstance(observer, list):  # AST_OK: boundary
        raise TypeError(
            f"observer.invalid_type: observer must be list or None, got {type(observer).__name__}"
        )

    # Boot1 type guard: reject non-bool to prevent truthy-string routing bugs
    if not isinstance(use_boot1_recursive, bool):  # AST_OK: boundary
        raise TypeError(
            f"use_boot1_recursive must be bool, got {type(use_boot1_recursive).__name__}"
        )

    # Backwards compatibility: max_iterations sets both limits
    if max_iterations is not None:
        max_engine_iterations = max_iterations
        max_algorithm_iterations = max_iterations

    if isinstance(max_steps, bool) or not isinstance(max_steps, int):
        raise RcxEngineError(
            "api.bad_request",
            f"max_steps must be a non-negative integer watchdog, got {type(max_steps).__name__}",
        )
    if max_steps < 0:
        raise RcxEngineError(
            "api.bad_request",
            f"max_steps must be >= 0, got {max_steps}",
        )
    structural_max_steps = _SN_ZERO
    for _ in range(max_steps):
        _sn_add_state = {"_add": {"a": structural_max_steps, "b": _SN_ONE}}
        _sn_add_hash = mu_hash_control_cached(
            _sn_add_state,
            "run_engine_pipeline_recursive max_steps.structural_add.initial",
        )
        _sn_add_result = None
        for _sn_guard in range(_SN_PROJECTION_STEP_LIMIT):
            _sn_result = _step_trusted(_STRUCTURAL_NUMBER_ADD_PROJECTIONS, _sn_add_state)
            _sn_result_hash = mu_hash_control_cached(
                _sn_result,
                "run_engine_pipeline_recursive max_steps.structural_add.stall",
            )
            if _sn_result_hash == _sn_add_hash:
                _sn_add_result = _sn_result
                break
            _sn_add_state = _sn_result
            _sn_add_hash = _sn_result_hash
        if _sn_add_result is None:
            raise RcxEngineError(
                "execution.max_steps",
                "run_engine_pipeline_recursive max_steps: StructuralNumbers add projection did not settle",
            )
        structural_max_steps = _sn_add_result
        if not isinstance(structural_max_steps, dict) or set(structural_max_steps.keys()) != {"_num"}:
            raise RcxEngineError(
                "execution.invalid_result",
                "run_engine_pipeline_recursive max_steps: StructuralNumbers ADD produced malformed numeral",
            )

    # Meta path: capture observer events for iteration count, derive reason from result.
    # Internal functions and 8-key terminal shape are unchanged.
    if return_meta:
        meta_observer = observer if observer is not None else []
        baseline = sum(1 for e in meta_observer if e.get("event_name") == "step_boundary")
        if use_boot1_recursive:
            engine_result = _run_engine_recursive(
                projections, input_value,
                max_steps=max_steps, frozen=frozen,
                max_engine_iterations=max_engine_iterations,
                max_algorithm_iterations=max_algorithm_iterations,
                observer=meta_observer,
            )
        else:
            engine_result = run_engine_pipeline(
                projections, input_value,
                max_steps=max_steps, frozen=frozen,
                max_engine_iterations=max_engine_iterations,
                max_algorithm_iterations=max_algorithm_iterations,
                observer=meta_observer,
                use_boot1_recursive=False,
                return_meta=False,
            )
        iterations_used = sum(1 for e in meta_observer if e.get("event_name") == "step_boundary") - baseline
        return {
            "engine_result": engine_result,
            "engine_exit_reason": _derive_engine_exit_reason(engine_result),
            "engine_iterations_used": iterations_used,
            "max_engine_iterations": max_engine_iterations,
        }

    # Boot1 shadow: opt-in recursive engine loop (parity with trampoline)
    if use_boot1_recursive:
        return _run_engine_recursive(
            projections, input_value,
            max_steps=max_steps, frozen=frozen,
            max_engine_iterations=max_engine_iterations,
            max_algorithm_iterations=max_algorithm_iterations,
            observer=observer,
        )

    engine_projs = load_verified_seed(get_seed_path("rcx_engine.v1.json"))["projections"]

    # Observer event helper — no-op when observer is None
    _obs_ts = [0]  # mutable counter for logical timestamp

    def _emit(event_name, step, state_val, error_code=None, **extra):
        if observer is None:
            return
        state_hash = None
        if isinstance(state_val, (dict, list, str, int, float, bool)) or state_val is None:
            try:
                state_hash = mu_hash(state_val)
            except Exception:
                pass
        event = {
            "event_name": event_name,
            "step": step,
            "state_hash": state_hash,
            "error_code": error_code,
            "substrate": "python",
            "timestamp": _obs_ts[0],
        }
        if extra:
            event.update(extra)
        observer.append(event)
        _obs_ts[0] += 1

    # Feed engine its initial input (always use full config form → engine.init_config)
    state: Mu = {"_run_engine": {"projections": projections, "input": input_value, "max_steps": structural_max_steps, "frozen": frozen}}

    # Generic effect handler loop
    for iteration in range(max_engine_iterations):  # AST_OK: infra — boundary host loop iteration
        # Step engine projections — trusted: engine state built from validated input
        next_state = _step_trusted(engine_projs, state)

        _emit("step_boundary", iteration, state)

        # Wave 4A: classify engine step via shared classifier
        transition, payload = _classify_engine_step(next_state, state)

        if transition == "stall_terminal":
            if isinstance(payload, dict):  # AST_OK: infra — terminal signal check
                if payload.get("closure_detected"):
                    _emit("closure_detected", iteration, payload)
                if payload.get("stall"):
                    _emit("stall_detected", iteration, payload)
            _emit("engine_terminal", iteration, payload,
                  engine_exit_reason=_derive_engine_exit_reason(payload),
                  engine_iterations_used=iteration + 1)
            return payload

        elif transition == "stall_non_terminal":
            _emit("fail_closed", iteration, payload, error_code="engine.stalled_non_terminal")
            raise RcxEngineError(
                "engine.stalled_non_terminal",
                f"Engine stalled at iteration {iteration} without producing terminal result. "
                f"State keys: {sorted(payload.keys()) if isinstance(payload, dict) else type(payload).__name__}"
            )

        elif transition == "boundary":
            state = _service_boundary_effect(
                payload,
                max_algorithm_iterations, _emit, iteration, state,
            )
            continue

        elif transition == "tail_call":
            _validate_reentry_payload(payload, "trampoline _tail_call")
            state = {"_run_engine": payload}
            continue

        elif transition == "terminal":
            if isinstance(payload, dict):  # AST_OK: infra — terminal signal check
                if payload.get("closure_detected"):
                    _emit("closure_detected", iteration, payload)
                if payload.get("stall"):
                    _emit("stall_detected", iteration, payload)
            _emit("engine_terminal", iteration, payload,
                  engine_exit_reason=_derive_engine_exit_reason(payload),
                  engine_iterations_used=iteration + 1)
            return payload

        elif transition == "reentry":
            # Trampoline: validate and wrap re-entry payload back into _run_engine envelope.
            # Boot1 handles this by frame update; trampoline feeds it back to
            # engine projections which expect the {"_run_engine": ...} shape.
            _validate_reentry_payload(payload, "trampoline _run_engine")
            state = {"_run_engine": payload}

        else:  # "continue"
            state = payload

    # FAIL CLOSED: engine loop exhausted without terminal result
    _emit("fail_closed", max_engine_iterations - 1, state, error_code="engine.exhausted")
    raise RcxEngineError(
        "engine.exhausted",
        f"Engine pipeline exhausted {max_engine_iterations} iterations without terminal result. "
        f"State keys: {sorted(state.keys()) if isinstance(state, dict) else type(state).__name__}"
    )


# =============================================================================
# Hemisphere Routing & Metabolization (Boot2)
# =============================================================================

def run_hemisphere_routing(engine_result: Mu, hemispheres: Mu) -> Mu:  # AST_OK: infra — hemisphere boundary validation
    """Route engine result to hemispheres with input shape validation.

    Wraps input in route_hemisphere shape before running hemisphere projections.
    This prevents direct injection of internal hemi_* shapes (bypass vulnerability).

    Args:
        engine_result: Engine output dict (8-field terminal shape).
        hemispheres: Current hemisphere state dict (r_null, r_inf, r_a, lobes, sink).

    Returns:
        Updated hemispheres dict with entry routed to appropriate hemisphere.

    Raises:
        ValueError: If engine_result is not a dict.
        RuntimeError: If hemisphere routing stalls.
    """
    if not isinstance(engine_result, dict):
        raise ValueError("engine_result must be a dict")
    projs = load_verified_seed(get_seed_path("hemispheres.v1.json"))["projections"]
    wrapped = {"route_hemisphere": {"engine_result": engine_result, "hemispheres": hemispheres}}
    validate_no_kernel_reserved_fields(wrapped, "run_hemisphere_routing input")
    structural_result = run_mu_structural(
        projs,
        wrapped,
        max_steps=30,
        kernel_mode="core",
        validation_mode="algorithm_runtime",
        trace_output=False,
        reject_nonlinear=True,
    )
    result = structural_result["result"]
    # Stall is the EXPECTED completion signal: init→classify→add→unwrap→stall
    # Verify the result looks like a completed hemisphere dict
    if isinstance(result, dict) and set(result.keys()) == _get_hemisphere_keys():
        return result
    raise RcxEngineError(
        "input.shape_mismatch",
        f"Hemisphere routing did not produce valid hemisphere dict. "
        f"Got: {sorted(result.keys()) if isinstance(result, dict) else type(result).__name__}"
    )


# --- Metabolization Cycle (Structural Walker) ---

def count_hemisphere_entries(hemispheres: dict, max_entries_per_bucket: int = 1000) -> int:  # AST_OK: infra — boundary validation
    """Count entries and validate linked-list structure across all hemisphere buckets.

    The Mu runtime normalizes {head, tail} linked lists to Python lists.
    Each bucket is either None (empty) or a Python list of entry dicts.
    Validates structure and returns total entry count for dynamic step budget.

    Args:
        hemispheres: 5-bucket hemisphere dict.
        max_entries_per_bucket: Depth guard per bucket (defense-in-depth).

    Returns:
        Total entry count across all buckets.

    Raises:
        ValueError: If any bucket has invalid type or exceeds depth guard.
    """
    count = 0
    for bucket_name in _get_hemisphere_key_order():  # AST_OK: infra — seed-derived key iteration
        bucket = hemispheres[bucket_name]
        if bucket is None:
            continue
        if not isinstance(bucket, list):
            raise ValueError(
                f"hemisphere bucket '{bucket_name}' must be null or list, "
                f"got {type(bucket).__name__}"
            )
        if len(bucket) > max_entries_per_bucket:
            raise ValueError(
                f"hemisphere bucket '{bucket_name}' exceeds depth guard "
                f"({max_entries_per_bucket}), possible cyclic structure"
            )
        for i, entry in enumerate(bucket):
            if not isinstance(entry, dict):
                raise RcxEngineError(
                    "input.shape_mismatch",
                    f"hemisphere bucket '{bucket_name}' entry[{i}] must be a plain object, "
                    f"got {type(entry).__name__}"
                )
        count += len(bucket)
    return count


def run_metabolization_cycle(hemispheres: Mu) -> Mu:  # AST_OK: infra — boundary host wrapper
    """Run structural metabolization cycle over hemispheres.

    Loads metabolize_cycle.v1.json projections and runs them via run_mu().
    No host iteration — the iteration is structural (walker projections
    pattern-match on linked-list structure).

    Phases: sink scan (route to r_null/r_inf) → lobes promotion (closure_flag=true → r_a)
            → lobes order restore (reverse) → exit.

    Args:
        hemispheres: 5-bucket hemisphere dict {r_null, r_inf, r_a, lobes, sink}.

    Returns:
        Updated hemispheres dict after metabolization.

    Raises:
        TypeError: If hemispheres is not a dict.
        ValueError: If hemispheres has wrong key set or malformed linked lists.
        RcxEngineError: If metabolization cycle does not produce valid output.
    """
    # Input validation (fail-closed)
    if not isinstance(hemispheres, dict):  # AST_OK: boundary
        raise TypeError(f"hemispheres must be dict, got {type(hemispheres).__name__}")
    actual = set(hemispheres.keys())
    expected = _get_hemisphere_keys()
    if actual != expected:
        missing = sorted(expected - actual, key=str)
        extra = sorted(actual - expected, key=str)
        raise ValueError(f"hemispheres shape mismatch: missing={missing}, extra={extra}")

    # Recursive list validation + budget calculation (single pass)
    entry_count = count_hemisphere_entries(hemispheres)  # raises on malformed nodes

    projs = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))["projections"]
    wrapped = {"metabolize_cycle": {"hemispheres": hemispheres}}
    step_budget = max(20, 4 * entry_count + 10)

    result, _trace, stall = run_mu(projs, wrapped, max_steps=step_budget)

    # Output validation (symmetric with input)
    if not isinstance(result, dict) or set(result.keys()) != expected:
        raise RcxEngineError(
            "input.shape_mismatch",
            "Metabolization cycle did not produce valid hemispheres"
        )
    count_hemisphere_entries(result)  # raises on malformed output nodes

    return result


# --- Engine → Hemisphere Integration ---

def _default_hemispheres():  # AST_OK: infra
    """Canonical empty hemisphere state. Seed-derived key order (A9)."""
    return {k: None for k in _get_hemisphere_key_order()}  # AST_OK: infra — seed-derived key iteration


def run_engine_with_routing(projections, input_value, hemispheres=None, **engine_kwargs):
    """Chain run_engine_pipeline() → run_hemisphere_routing() → run_metabolization_cycle().

    Top-level integration: projections → trace → recurrence → exhaustion → routing → metabolization.

    Args:
        projections: Application projections to run.
        input_value: Initial input value.
        hemispheres: Current hemisphere state (default: empty 5-bucket).
        **engine_kwargs: Passed to run_engine_pipeline (max_steps, frozen, etc.)

    Returns:
        {"engine_result": <8-field dict>, "hemispheres": <updated 5-field dict>}

    Raises:
        TypeError: If hemispheres is not a dict.
        ValueError: If hemispheres has wrong key set.
        RcxEngineError: If routing or metabolization output has unexpected shape.
    """
    if hemispheres is None:
        hemispheres = _default_hemispheres()
    else:
        if not isinstance(hemispheres, dict):  # AST_OK: boundary
            raise TypeError(f"hemispheres must be dict, got {type(hemispheres).__name__}")
        actual = set(hemispheres.keys())
        expected = _get_hemisphere_keys()
        if actual != expected:
            missing = sorted(expected - actual, key=str)
            extra = sorted(actual - expected, key=str)
            raise ValueError(f"hemispheres shape mismatch: missing={missing}, extra={extra}")

    use_boot1 = engine_kwargs.pop("use_boot1_recursive", True)
    if not isinstance(use_boot1, bool):  # AST_OK: boundary
        raise TypeError(
            f"use_boot1_recursive must be bool, got {type(use_boot1).__name__}"
        )

    # Observer type guard: validate before forwarding to run_engine_pipeline
    obs = engine_kwargs.get("observer")
    if obs is not None and not isinstance(obs, list):  # AST_OK: boundary
        raise TypeError(
            f"observer.invalid_type: observer must be list or None, got {type(obs).__name__}"
        )

    engine_result = run_engine_pipeline(
        projections, input_value, use_boot1_recursive=use_boot1, **engine_kwargs
    )
    updated_hemispheres = run_hemisphere_routing(engine_result, hemispheres)

    # Fail-closed: validate output shape before returning
    if not isinstance(updated_hemispheres, dict) or set(updated_hemispheres.keys()) != _get_hemisphere_keys():  # AST_OK: boundary
        raise RcxEngineError("input.shape_mismatch", "run_hemisphere_routing returned unexpected shape")

    # Run metabolization cycle (structural walker — no host iteration)
    updated_hemispheres = run_metabolization_cycle(updated_hemispheres)

    return {"engine_result": engine_result, "hemispheres": updated_hemispheres}
