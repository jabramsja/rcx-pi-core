"""
Algorithm State Normalization Adapters (Gate 2)

These adapters convert raw algorithm state to normalized form for structural
execution. Per AlgorithmNormalizationSpec.v0.md:
- Internal execution uses normalized state
- Denormalization only at external I/O boundaries

Adapter window closure rule: These adapters must be removed or strictly gated
before Gate 4 begins (hard requirement per adversary review).

See:
- roadmap/AlgorithmNormalizationSpec.v0.md
- roadmap/MetaCircular_Boot0_GatePlan.md (Gate 2)
"""

from __future__ import annotations

from typing import Any

from .match_mu import normalize_for_match, denormalize_from_match
from .mu_type import Mu


# =============================================================================
# Recurrence Adapters
# =============================================================================

def normalize_recurrence_input(raw_state: dict) -> Mu:
    """
    Normalize raw recurrence input for structural execution.

    Raw format:
        {"_detect_closure": {"trace": <Mu list>, "result": <Mu value>}}

    Returns normalized Mu form (linked-list encoding).
    """
    if not isinstance(raw_state, dict):
        raise ValueError(f"Recurrence input must be dict, got {type(raw_state)}")

    if "_detect_closure" not in raw_state:
        raise ValueError("Recurrence input must have '_detect_closure' key")

    return normalize_for_match(raw_state)


def denormalize_recurrence_output(normalized_state: Mu) -> dict:
    """
    Denormalize recurrence output for external I/O.

    Per spec: denormalization only at external I/O boundaries.
    """
    result = denormalize_from_match(normalized_state)

    if not isinstance(result, dict):
        raise ValueError(f"Recurrence output must denormalize to dict, got {type(result)}")

    return result


# =============================================================================
# Exhaustion Adapters
# =============================================================================

def normalize_exhaustion_input(raw_state: dict) -> Mu:
    """
    Normalize raw exhaustion input for structural execution.

    Raw format:
        {"_detect_exhaustion": {
            "trace": <Mu list>,
            "frozen": <Mu list or null>,
            "tau_step": <Mu value or null>,
            "operator_ids": <Mu list>
        }}

    Returns normalized Mu form (linked-list encoding).
    """
    if not isinstance(raw_state, dict):
        raise ValueError(f"Exhaustion input must be dict, got {type(raw_state)}")

    if "_detect_exhaustion" not in raw_state:
        raise ValueError("Exhaustion input must have '_detect_exhaustion' key")

    return normalize_for_match(raw_state)


def denormalize_exhaustion_output(normalized_state: Mu) -> dict:
    """
    Denormalize exhaustion output for external I/O.

    Per spec: denormalization only at external I/O boundaries.
    """
    result = denormalize_from_match(normalized_state)

    if not isinstance(result, dict):
        raise ValueError(f"Exhaustion output must denormalize to dict, got {type(result)}")

    return result


# =============================================================================
# RCX Engine Adapters
# =============================================================================

def normalize_engine_input(raw_state: dict) -> Mu:
    """
    Normalize raw engine input for structural execution.

    Raw format:
        {"_run_engine": {
            "projections": <list of projection dicts>,
            "input": <Mu value>
        }}

    Returns normalized Mu form (linked-list encoding).
    """
    if not isinstance(raw_state, dict):
        raise ValueError(f"Engine input must be dict, got {type(raw_state)}")

    if "_run_engine" not in raw_state:
        raise ValueError("Engine input must have '_run_engine' key")

    return normalize_for_match(raw_state)


def denormalize_engine_output(normalized_state: Mu) -> dict:
    """
    Denormalize engine output for external I/O.

    Per spec: denormalization only at external I/O boundaries.
    """
    result = denormalize_from_match(normalized_state)

    if not isinstance(result, dict):
        raise ValueError(f"Engine output must denormalize to dict, got {type(result)}")

    return result


# =============================================================================
# Generic Adapter (for intermediate algorithm states)
# =============================================================================

def normalize_algorithm_state(raw_state: Mu) -> Mu:
    """
    Normalize any algorithm state for structural execution.

    This is the generic entry point. Use algorithm-specific adapters
    when input validation is needed.
    """
    return normalize_for_match(raw_state)


def denormalize_algorithm_state(normalized_state: Mu) -> Mu:
    """
    Denormalize algorithm state for external I/O.

    Per AlgorithmNormalizationSpec.v0.md:
    - The denormalizer is part of the trusted I/O boundary
    - Must be deterministic
    - Must be tested (round-trip stability)
    """
    return denormalize_from_match(normalized_state)


# =============================================================================
# Round-trip Verification (for testing)
# =============================================================================

def verify_roundtrip(raw_state: Mu) -> tuple[bool, str]:
    """
    Verify that normalize → denormalize preserves structure.

    Returns:
        (success, error_message)
    """
    try:
        normalized = normalize_for_match(raw_state)
        denormalized = denormalize_from_match(normalized)

        # Check structural equivalence
        from .mu_type import mu_equal
        if not mu_equal(raw_state, denormalized):
            return False, f"Round-trip changed structure: {raw_state} → {denormalized}"

        return True, ""
    except Exception as e:
        return False, f"Round-trip failed: {e}"
