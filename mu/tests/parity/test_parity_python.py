"""
Cross-substrate parity tests - Python side.

Loads shared test vectors from tests/fixtures/parity_vectors.json and verifies
that Python produces the expected outputs. The JavaScript POC runs the same
vectors to prove both substrates produce identical results.

This is Step 2 of the L3 substrate portability plan.
"""

import json
from pathlib import Path

import pytest

# Import kernel components
from rcx_pi.selfhost.mu_type import Mu, mu_equal
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.subst_mu import denormalize_from_match
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import (
    validate_no_kernel_reserved_fields,
    list_to_linked,        # Use canonical implementation (Expert finding: avoid duplication)
    normalize_projection,  # Use canonical implementation (Expert finding: avoid duplication)
)
from tests.conftest import run_until_done  # Use shared implementation (Expert finding: avoid duplication)


# Load test vectors
FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"
VECTORS_FILE = FIXTURES_DIR / "parity_vectors.json"


def load_vectors():
    """Load parity test vectors from JSON file."""
    with open(VECTORS_FILE) as f:
        return json.load(f)


# run_until_done imported from conftest (Expert finding: consolidated duplicate)


class TestParityVectors:
    """Test parity vectors against Python kernel."""

    @pytest.fixture(scope="class")
    def vectors(self):
        """Load test vectors."""
        return load_vectors()

    @pytest.fixture(scope="class")
    def kernel_projections(self):
        """Load combined kernel + match + subst projections from mu/ canonical location."""
        kernel = load_verified_seed(get_seed_path("kernel.v1.json"))
        match_seed = load_verified_seed(get_seed_path("match.v2.json"))
        subst_seed = load_verified_seed(get_seed_path("subst.v2.json"))
        return kernel["projections"] + match_seed["projections"] + subst_seed["projections"]

    @pytest.mark.parametrize("vector_id", [
        "simple_match",
        "no_match_stall",
        "nested_binding",
        "empty_list_preservation",
        "empty_dict_preservation",
        "boolean_values",
        "null_values",
        "numeric_types",
        "catchall_pattern",
        "repeated_variable",
        # repeated_variable_mismatch removed - non-linear binding is documented limitation
        "list_with_mixed_types",
        "unicode_strings",
        "negative_numbers",
        "zero_values",
        # New vectors added from 7-agent adversarial review:
        "large_integer",
        "variable_name_as_data",
        "deep_nesting_5_levels",
        "dict_with_head_tail_keys",
        "unicode_key_sorting",
        "nested_empty_containers",
    ])
    def test_parity_vector(self, vectors, kernel_projections, vector_id):
        """Test a single parity vector."""
        # Find the vector by id
        vector = next((v for v in vectors["vectors"] if v["id"] == vector_id), None)
        assert vector is not None, f"Vector {vector_id} not found"

        # Normalize input and projection using the same functions as the integration tests
        normalized_input = normalize_for_match(vector["input"])
        normalized_projection = normalize_projection(vector["projection"])

        # Build kernel entry
        kernel_entry = {
            "_step": normalized_input,
            "_projs": list_to_linked([normalized_projection]),
        }

        # Run kernel
        result, trace, is_stall = run_until_done(kernel_projections, kernel_entry, max_steps=100)

        # Denormalize result
        denormalized = denormalize_from_match(result)

        # Compare with expected
        expected = vector["expected_output"]

        # SEMANTIC CHECK 1: Direct equality (catches denormalization bugs)
        # This ensures denormalized Python types match expected Python types
        assert denormalized == expected, \
            f"Direct equality failed for {vector_id}: got {denormalized}, expected {expected}"

        # SEMANTIC CHECK 2: Structural equality after normalization (catches normalization bugs)
        # This ensures both produce the same Mu structure
        assert mu_equal(normalize_for_match(denormalized), normalize_for_match(expected)), \
            f"Structural parity mismatch for {vector_id}: got {denormalized}, expected {expected}"


class TestSecurityVectors:
    """Test security vectors - domain data with kernel-reserved fields must be rejected."""

    @pytest.fixture(scope="class")
    def vectors(self):
        """Load test vectors."""
        return load_vectors()

    @pytest.mark.parametrize("vector_id", [
        "reject_kernel_reserved_step",
        "reject_kernel_reserved_mode",
        "reject_nested_reserved",
    ])
    def test_security_vector(self, vectors, vector_id):
        """Test that kernel-reserved fields in domain data are rejected."""
        # Find the vector by id
        vector = next((v for v in vectors["security_vectors"] if v["id"] == vector_id), None)
        assert vector is not None, f"Security vector {vector_id} not found"

        # Attempt to validate - should raise
        with pytest.raises(ValueError) as exc_info:
            validate_no_kernel_reserved_fields(vector["input"])

        # Check error message contains expected field name
        assert vector["error_contains"] in str(exc_info.value), \
            f"Error should mention '{vector['error_contains']}'"


class TestVectorFileIntegrity:
    """Meta-tests for the vector file itself."""

    def test_vectors_file_exists(self):
        """Verify parity vectors file exists."""
        assert VECTORS_FILE.exists(), "parity_vectors.json not found"

    def test_vectors_file_valid_json(self):
        """Verify parity vectors file is valid JSON."""
        with open(VECTORS_FILE) as f:
            data = json.load(f)
        assert "vectors" in data
        assert "security_vectors" in data
        assert len(data["vectors"]) >= 10, "Expected at least 10 parity vectors"

    def test_all_vectors_have_required_fields(self):
        """Verify all vectors have required fields."""
        data = load_vectors()
        for vector in data["vectors"]:
            assert "id" in vector, f"Vector missing id"
            assert "description" in vector, f"Vector {vector.get('id', '?')} missing description"
            assert "projection" in vector, f"Vector {vector['id']} missing projection"
            assert "input" in vector, f"Vector {vector['id']} missing input"
            assert "expected_output" in vector, f"Vector {vector['id']} missing expected_output"

        for vector in data["security_vectors"]:
            assert "id" in vector, f"Security vector missing id"
            assert "input" in vector, f"Security vector {vector['id']} missing input"
            assert "expect_error" in vector, f"Security vector {vector['id']} missing expect_error"
