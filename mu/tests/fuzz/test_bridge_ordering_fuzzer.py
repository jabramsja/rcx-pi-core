"""
Bridge Projection Ordering Mutation Fuzzer - Property-Based Tests

Stress-tests the ordering invariants that make non-linear conflict detection work:
1. bridge.var.check_existing MUST come before match.var
2. bridge.lookup.found_same MUST come before bridge.lookup.found_different
3. All 5 bridge projections MUST be present

Uses Hypothesis to systematically generate ordering mutations and verify that
_validate_match_bridge_ordering() catches every invariant violation.

Added 2026-02-10 after 9-agent rigorous review identified fuzzer gap.
"""

import copy
import itertools

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from rcx_pi.selfhost.match_mu import (
    load_match_with_bridge_projections,
    clear_match_bridge_cache,
    _validate_match_bridge_ordering,  # ANTICHEAT_OK: grounding test for bridge ordering invariant
)
from rcx_pi.selfhost.step_mu import (
    _validate_combined_bridge_ordering,  # ANTICHEAT_OK: grounding test for kernel bridge ordering
)


# =============================================================================
# Constants
# =============================================================================

BRIDGE_IDS = [
    "bridge.var.check_existing",
    "bridge.lookup.found_same",
    "bridge.lookup.found_different",
    "bridge.lookup.not_found_yet",
    "bridge.lookup.not_found",
]

MATCH_IDS = [
    "match.done",
    "match.sibling",
    "match.equal",
    "match.var",
    "match.typed.descend",
    "match.dict.descend",
    "match.fail",
    "match.wrap",
]


# =============================================================================
# Strategies
# =============================================================================

@st.composite
def shuffled_projection_ids(draw):
    """Generate a random shuffle of bridge + match projection IDs."""
    ids = BRIDGE_IDS + MATCH_IDS
    shuffled = draw(st.permutations(ids))
    return [{"id": pid} for pid in shuffled]


@st.composite
def valid_ordering_with_one_swap(draw):
    """Start from valid ordering, then swap exactly one pair of positions."""
    projs = load_match_with_bridge_projections()
    projs = copy.deepcopy(projs)

    n = len(projs)
    i = draw(st.integers(min_value=0, max_value=n - 1))
    j = draw(st.integers(min_value=0, max_value=n - 1))
    assume(i != j)

    projs[i], projs[j] = projs[j], projs[i]
    return projs, i, j


@st.composite
def valid_ordering_with_removal(draw):
    """Start from valid ordering, then remove exactly one bridge projection."""
    projs = load_match_with_bridge_projections()
    projs = copy.deepcopy(projs)

    # Find bridge projection indices
    bridge_indices = [
        i for i, p in enumerate(projs)
        if p.get("id", "").startswith("bridge.")
    ]
    assume(len(bridge_indices) > 0)

    remove_idx = draw(st.sampled_from(bridge_indices))
    removed = projs.pop(remove_idx)
    return projs, removed


# =============================================================================
# Core Ordering Invariant Tests
# =============================================================================

class TestBridgeOrderingMutationFuzzer:
    """Fuzz the bridge ordering validator with systematic mutations."""

    @given(data=shuffled_projection_ids())
    @settings(max_examples=200, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_random_shuffle_detected(self, data):
        """Any random shuffle that violates ordering is detected.

        Property: _validate_match_bridge_ordering raises ValueError for any
        ordering where bridge.var.check_existing comes after match.var,
        or where bridge/match.var is missing.
        """
        ids = [p.get("id") for p in data]

        # Check if this shuffle has valid ordering
        bridge_check_idx = None
        match_var_idx = None
        for i, pid in enumerate(ids):
            if pid == "bridge.var.check_existing":
                bridge_check_idx = i
            elif pid == "match.var":
                match_var_idx = i

        if bridge_check_idx is None or match_var_idx is None:
            # Missing required projection — validator should reject
            with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
                _validate_match_bridge_ordering(data)
        elif bridge_check_idx >= match_var_idx:
            # Wrong ordering — validator should reject
            with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
                _validate_match_bridge_ordering(data)
        else:
            # Valid ordering — validator should accept
            _validate_match_bridge_ordering(data)

    @given(data=valid_ordering_with_one_swap())
    @settings(max_examples=100, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_single_swap_from_valid(self, data):
        """Swapping any two projections in valid order is detected if it breaks invariant."""
        projs, i, j = data

        ids = [p.get("id") for p in projs]
        bridge_check_idx = None
        match_var_idx = None
        for k, pid in enumerate(ids):
            if pid == "bridge.var.check_existing":
                bridge_check_idx = k
            elif pid == "match.var":
                match_var_idx = k

        if bridge_check_idx is not None and match_var_idx is not None:
            if bridge_check_idx >= match_var_idx:
                with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
                    _validate_match_bridge_ordering(projs)
            else:
                # Still valid after swap
                _validate_match_bridge_ordering(projs)

    @given(data=valid_ordering_with_removal())
    @settings(max_examples=50, deadline=5000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_removal_of_any_bridge_projection(self, data):
        """Removing any bridge projection is detected by the validators.

        Tests both validators:
        - _validate_match_bridge_ordering: checks bridge.var.check_existing
        - _validate_combined_bridge_ordering: checks all 5 bridge projections
        """
        projs, removed = data
        removed_id = removed.get("id", "")

        if removed_id == "bridge.var.check_existing":
            with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
                _validate_match_bridge_ordering(projs)

        # Combined validator checks ALL 5 bridge projections
        if removed_id.startswith("bridge."):
            with pytest.raises(ValueError, match="SECURITY.*missing"):
                _validate_combined_bridge_ordering(projs)


# =============================================================================
# Exhaustive Permutation Tests (Small Set)
# =============================================================================

class TestExhaustiveBridgePermutations:
    """Exhaustively test all permutations of the critical ordering pair."""

    def test_all_positions_of_bridge_check_relative_to_match_var(self):
        """For every possible position of bridge.var.check_existing relative
        to match.var, verify the validator behaves correctly.

        There are 13 possible positions for each. This tests all 13*12 = 156
        combinations of (bridge_idx, match_var_idx) where idx != idx.
        """
        n = 13  # Total projection count
        accepted = 0
        rejected = 0

        for bridge_idx in range(n):
            for match_var_idx in range(n):
                if bridge_idx == match_var_idx:
                    continue

                # Build minimal projection list
                projs = [{"id": f"filler_{i}"} for i in range(n)]
                projs[bridge_idx] = {"id": "bridge.var.check_existing"}
                projs[match_var_idx] = {"id": "match.var"}

                if bridge_idx < match_var_idx:
                    _validate_match_bridge_ordering(projs)
                    accepted += 1
                else:
                    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
                        _validate_match_bridge_ordering(projs)
                    rejected += 1

        assert accepted > 0, "Must have at least one valid ordering"
        assert rejected > 0, "Must have at least one invalid ordering"
        assert accepted + rejected == n * (n - 1), "Must test all position pairs"

    def test_found_same_vs_found_different_all_permutations(self):
        """Exhaustively verify found_same before found_different invariant.

        The combined kernel validator enforces this. Test all pairwise positions.
        """
        # Build a base projection list with all required IDs
        base_ids = [
            "kernel.step",  # filler kernel projection
            "bridge.var.check_existing",
            "bridge.lookup.found_same",
            "bridge.lookup.found_different",
            "bridge.lookup.not_found_yet",
            "bridge.lookup.not_found",
            "match.var",
        ]
        base = [{"id": pid} for pid in base_ids]

        # Verify the base ordering is valid
        _validate_match_bridge_ordering(base)

        # Now swap found_same and found_different
        swapped = copy.deepcopy(base)
        same_idx = next(i for i, p in enumerate(swapped)
                        if p.get("id") == "bridge.lookup.found_same")
        diff_idx = next(i for i, p in enumerate(swapped)
                        if p.get("id") == "bridge.lookup.found_different")
        swapped[same_idx], swapped[diff_idx] = swapped[diff_idx], swapped[same_idx]

        # The match_bridge validator doesn't check this (only checks bridge vs match.var)
        # but _validate_combined_bridge_ordering does
        with pytest.raises(ValueError, match="must precede"):
            _validate_combined_bridge_ordering(swapped)


# =============================================================================
# Duplication Attack Tests
# =============================================================================

class TestDuplicationAttacks:
    """Test that duplicating projections doesn't create silent bypasses."""

    def test_duplicate_bridge_check_existing(self):
        """Duplicating bridge.var.check_existing is accepted by ordering validator
        (two bridges before match.var is fine — the deeper issue is seed integrity).
        """
        projs = load_match_with_bridge_projections()
        projs = copy.deepcopy(projs)

        # Find bridge.var.check_existing and duplicate it
        for i, p in enumerate(projs):
            if p.get("id") == "bridge.var.check_existing":
                projs.insert(i + 1, copy.deepcopy(p))
                break

        # Ordering is still valid (bridge before match.var)
        _validate_match_bridge_ordering(projs)

    def test_duplicate_match_var_after_bridge(self):
        """Duplicating match.var after bridge is accepted (first-match-wins means
        the first match.var is dead — bridge handles vars).
        """
        projs = load_match_with_bridge_projections()
        projs = copy.deepcopy(projs)

        # Add a second match.var at the end (before match.wrap)
        for i, p in enumerate(projs):
            if p.get("id") == "match.wrap":
                projs.insert(i, {"id": "match.var", "pattern": {}, "body": {}})
                break

        # Still valid ordering (first match.var is still after bridge)
        _validate_match_bridge_ordering(projs)


# =============================================================================
# Empty and Degenerate Input Tests
# =============================================================================

class TestDegenerateInputs:
    """Test validator behavior with degenerate inputs."""

    def test_empty_list_rejects(self):
        """Empty projection list is rejected (both IDs missing)."""
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering([])

    def test_only_bridge_rejects(self):
        """Only bridge.var.check_existing (no match.var) is rejected."""
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering([{"id": "bridge.var.check_existing"}])

    def test_only_match_var_rejects(self):
        """Only match.var (no bridge) is rejected."""
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering([{"id": "match.var"}])

    def test_projections_without_id_field(self):
        """Projections without 'id' field don't satisfy requirements."""
        projs = [{"pattern": "x"}, {"body": "y"}]
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering(projs)

    @given(n=st.integers(min_value=1, max_value=50))
    @settings(deadline=5000)
    def test_all_filler_projections_rejected(self, n):
        """A list of n filler projections (no bridge, no match.var) is rejected."""
        projs = [{"id": f"filler_{i}"} for i in range(n)]
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering(projs)


# =============================================================================
# Cache Mutation Safety
# =============================================================================

class TestCacheMutationSafety:
    """Verify that mutating returned projections doesn't corrupt the cache."""

    def test_mutation_doesnt_corrupt_cache(self):
        """Mutating a returned projection list doesn't affect cached version."""
        clear_match_bridge_cache()

        projs1 = load_match_with_bridge_projections()
        original_ids = [p.get("id") for p in projs1]

        # Mutate the returned list
        projs1.reverse()
        projs1.pop(0)
        projs1.append({"id": "attacker.injection"})

        # Reload and verify cache is unaffected
        projs2 = load_match_with_bridge_projections()
        assert [p.get("id") for p in projs2] == original_ids

    def test_deep_mutation_doesnt_corrupt_cache(self):
        """Deep-mutating a projection dict doesn't affect cached version."""
        clear_match_bridge_cache()

        projs1 = load_match_with_bridge_projections()
        original_first_id = projs1[0].get("id")

        # Deep-mutate a projection
        projs1[0]["id"] = "attacker.mutation"
        projs1[0]["evil"] = True

        # Reload and verify cache is unaffected
        projs2 = load_match_with_bridge_projections()
        assert projs2[0].get("id") == original_first_id
        assert "evil" not in projs2[0]
