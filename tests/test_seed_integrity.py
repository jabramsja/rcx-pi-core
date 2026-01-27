"""
Tests for seed integrity verification.

These tests verify that:
1. Valid seeds pass integrity checks
2. Tampered seeds fail checksum verification
3. Malformed seeds fail structure validation
4. Missing projections are detected
"""

import json
import pytest
from pathlib import Path

from rcx_pi.selfhost.seed_integrity import (
    compute_checksum,
    verify_checksum,
    validate_seed_structure,
    validate_projection_ids,
    load_verified_seed,
    verify_all_seeds,
    get_seeds_dir,
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
)


# =============================================================================
# Test: Checksum Computation
# =============================================================================


class TestChecksumComputation:
    """Test SHA256 checksum computation."""

    def test_compute_checksum_deterministic(self):
        """Same content produces same checksum."""
        content = b'{"test": 123}'
        c1 = compute_checksum(content)
        c2 = compute_checksum(content)
        assert c1 == c2

    def test_compute_checksum_different_content(self):
        """Different content produces different checksum."""
        c1 = compute_checksum(b'{"a": 1}')
        c2 = compute_checksum(b'{"a": 2}')
        assert c1 != c2

    def test_compute_checksum_is_sha256(self):
        """Checksum is 64 hex characters (SHA256)."""
        checksum = compute_checksum(b"test")
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)


# =============================================================================
# Test: Checksum Verification
# =============================================================================


class TestChecksumVerification:
    """Test checksum verification against known values."""

    def test_verify_checksum_match_seed_valid(self):
        """Valid match.v1.json passes checksum."""
        seed_path = get_seeds_dir() / "match.v1.json"
        content = seed_path.read_bytes()
        # Should not raise
        verify_checksum("match.v1.json", content)

    def test_verify_checksum_subst_seed_valid(self):
        """Valid subst.v1.json passes checksum."""
        seed_path = get_seeds_dir() / "subst.v1.json"
        content = seed_path.read_bytes()
        # Should not raise
        verify_checksum("subst.v1.json", content)

    def test_verify_checksum_tampered_fails(self):
        """Tampered content fails checksum."""
        # Start with valid content
        seed_path = get_seeds_dir() / "match.v1.json"
        content = seed_path.read_bytes()

        # Tamper with it
        tampered = content + b" "

        with pytest.raises(ValueError, match="integrity check failed"):
            verify_checksum("match.v1.json", tampered)

    def test_verify_checksum_unknown_seed(self):
        """Unknown seed name raises error."""
        with pytest.raises(ValueError, match="Unknown seed"):
            verify_checksum("unknown.json", b"test")


# =============================================================================
# Test: Structure Validation
# =============================================================================


class TestStructureValidation:
    """Test seed structure validation."""

    def test_valid_structure_passes(self):
        """Valid seed structure passes validation."""
        seed = {
            "meta": {"version": "1.0", "name": "TEST", "description": "test"},
            "projections": [
                {"id": "test.1", "pattern": {}, "body": {}}
            ]
        }
        # Should not raise
        validate_seed_structure("test.json", seed)

    def test_missing_meta_fails(self):
        """Seed without meta key fails."""
        seed = {"projections": []}
        with pytest.raises(ValueError, match="missing 'meta'"):
            validate_seed_structure("test.json", seed)

    def test_missing_projections_fails(self):
        """Seed without projections key fails."""
        seed = {"meta": {"version": "1.0", "name": "TEST", "description": "test"}}
        with pytest.raises(ValueError, match="missing 'projections'"):
            validate_seed_structure("test.json", seed)

    def test_missing_meta_fields_fails(self):
        """Meta missing required fields fails."""
        seed = {
            "meta": {"version": "1.0"},  # Missing name and description
            "projections": []
        }
        with pytest.raises(ValueError, match="meta missing keys"):
            validate_seed_structure("test.json", seed)

    def test_projections_not_list_fails(self):
        """Projections must be a list."""
        seed = {
            "meta": {"version": "1.0", "name": "TEST", "description": "test"},
            "projections": {}  # Should be list
        }
        with pytest.raises(ValueError, match="must be a list"):
            validate_seed_structure("test.json", seed)

    def test_projection_missing_id_fails(self):
        """Projection without id fails."""
        seed = {
            "meta": {"version": "1.0", "name": "TEST", "description": "test"},
            "projections": [
                {"pattern": {}, "body": {}}  # Missing id
            ]
        }
        with pytest.raises(ValueError, match="missing keys"):
            validate_seed_structure("test.json", seed)


# =============================================================================
# Test: Projection ID Validation
# =============================================================================


class TestProjectionIdValidation:
    """Test expected projection ID validation."""

    def test_match_seed_has_expected_ids(self):
        """match.v1.json has all expected projection IDs."""
        seed_path = get_seeds_dir() / "match.v1.json"
        with open(seed_path) as f:
            seed = json.load(f)
        # Should not raise
        validate_projection_ids("match.v1.json", seed)

    def test_subst_seed_has_expected_ids(self):
        """subst.v1.json has all expected projection IDs."""
        seed_path = get_seeds_dir() / "subst.v1.json"
        with open(seed_path) as f:
            seed = json.load(f)
        # Should not raise
        validate_projection_ids("subst.v1.json", seed)

    def test_missing_projection_id_fails(self):
        """Seed missing expected projection ID fails."""
        seed = {
            "projections": [
                {"id": "match.done", "pattern": {}, "body": {}},
                # Missing other expected IDs
            ]
        }
        with pytest.raises(ValueError, match="missing expected projection IDs"):
            validate_projection_ids("match.v1.json", seed)

    def test_wrap_not_last_fails(self):
        """Wrap projection not being last fails."""
        seed = {
            "projections": [
                {"id": "match.wrap", "pattern": {}, "body": {}},  # Should be last
                {"id": "match.done", "pattern": {}, "body": {}},
                {"id": "match.sibling", "pattern": {}, "body": {}},
                {"id": "match.equal", "pattern": {}, "body": {}},
                {"id": "match.var", "pattern": {}, "body": {}},
                {"id": "match.dict.descend", "pattern": {}, "body": {}},
            ]
        }
        with pytest.raises(ValueError, match="must be last"):
            validate_projection_ids("match.v1.json", seed)

    def test_unknown_seed_skips_validation(self):
        """Unknown seed name skips projection ID validation."""
        seed = {"projections": []}
        # Should not raise (unknown seeds skip this check)
        validate_projection_ids("unknown.json", seed)


# =============================================================================
# Test: Full Verified Load
# =============================================================================


class TestVerifiedLoad:
    """Test load_verified_seed function."""

    def test_load_match_seed_verified(self):
        """Load match.v1.json with full verification."""
        seed_path = get_seeds_dir() / "match.v1.json"
        seed = load_verified_seed(seed_path)

        assert "meta" in seed
        assert "projections" in seed
        assert seed["meta"]["name"] == "MATCH_SEED"

    def test_load_subst_seed_verified(self):
        """Load subst.v1.json with full verification."""
        seed_path = get_seeds_dir() / "subst.v1.json"
        seed = load_verified_seed(seed_path)

        assert "meta" in seed
        assert "projections" in seed
        assert seed["meta"]["name"] == "SUBST_SEED"

    def test_load_with_verify_false_skips_checks(self, tmp_path):
        """verify=False skips integrity checks."""
        # Create a seed that would fail checksum
        seed_file = tmp_path / "test.json"
        seed_file.write_text('{"meta": {"version": "1.0", "name": "TEST", "description": "test"}, "projections": []}')

        # Should work with verify=False
        seed = load_verified_seed(seed_file, verify=False)
        assert seed["meta"]["name"] == "TEST"

    def test_load_nonexistent_raises(self):
        """Loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_verified_seed(Path("/nonexistent/path.json"))


# =============================================================================
# Test: Verify All Seeds
# =============================================================================


class TestVerifyAllSeeds:
    """Test verify_all_seeds function."""

    def test_verify_all_seeds_passes(self):
        """All known seeds pass verification."""
        results = verify_all_seeds()

        assert "match.v1.json" in results
        assert "subst.v1.json" in results
        assert results["match.v1.json"] is True
        assert results["subst.v1.json"] is True


# =============================================================================
# Test: Integration with match_mu and subst_mu
# =============================================================================


class TestIntegrationWithLoaders:
    """Test that match_mu and subst_mu use verified loading."""

    def test_match_mu_loads_verified(self):
        """match_mu loads projections with verification."""
        from rcx_pi.selfhost.match_mu import load_match_projections, clear_projection_cache

        clear_projection_cache()
        projections = load_match_projections()

        # Should have loaded successfully
        assert len(projections) == 6
        assert projections[0]["id"] == "match.done"
        assert projections[-1]["id"] == "match.wrap"

    def test_subst_mu_loads_verified(self):
        """subst_mu loads projections with verification."""
        from rcx_pi.selfhost.subst_mu import load_subst_projections, clear_projection_cache

        clear_projection_cache()
        projections = load_subst_projections()

        # Should have loaded successfully (9 projections after Phase 6a lookup additions)
        assert len(projections) == 9
        assert projections[0]["id"] == "subst.done"
        assert projections[-1]["id"] == "subst.wrap"


# =============================================================================
# Test: Checksums Match Reality
# =============================================================================


class TestChecksumsMatchReality:
    """Ensure hardcoded checksums match actual files."""

    def test_match_checksum_is_current(self):
        """match.v1.json checksum in SEED_CHECKSUMS matches file."""
        seed_path = get_seeds_dir() / "match.v1.json"
        actual = compute_checksum(seed_path.read_bytes())
        expected = SEED_CHECKSUMS["match.v1.json"]
        assert actual == expected, (
            f"match.v1.json checksum mismatch!\n"
            f"  File:     {actual}\n"
            f"  Expected: {expected}\n"
            f"  Update SEED_CHECKSUMS if seed was intentionally changed."
        )

    def test_subst_checksum_is_current(self):
        """subst.v1.json checksum in SEED_CHECKSUMS matches file."""
        seed_path = get_seeds_dir() / "subst.v1.json"
        actual = compute_checksum(seed_path.read_bytes())
        expected = SEED_CHECKSUMS["subst.v1.json"]
        assert actual == expected, (
            f"subst.v1.json checksum mismatch!\n"
            f"  File:     {actual}\n"
            f"  Expected: {expected}\n"
            f"  Update SEED_CHECKSUMS if seed was intentionally changed."
        )
