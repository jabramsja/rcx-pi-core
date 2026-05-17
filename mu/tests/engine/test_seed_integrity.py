"""
Tests for seed integrity verification.

These tests verify that:
1. Valid seeds pass integrity checks
2. Tampered seeds fail checksum verification
3. Malformed seeds fail structure validation
4. Missing projections are detected
"""

import json
import os
import pytest
import subprocess
import sys
from pathlib import Path

import rcx_pi.selfhost.seed_integrity as seed_integrity_module
from rcx_pi.selfhost.seed_integrity import (
    compute_checksum,
    verify_checksum,
    validate_seed_structure,
    validate_projection_ids,
    load_verified_seed,
    load_verified_seed_image,
    verify_all_seeds,
    get_seed_path,
    SEED_REGISTRY_MANIFEST,
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
    MU_SEED_LOCATIONS,
    SEED_DEPENDENCIES,
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
        seed_path = get_seed_path("match.v1.json")
        content = seed_path.read_bytes()
        # Should not raise
        verify_checksum("match.v1.json", content)

    def test_verify_checksum_subst_seed_valid(self):
        """Valid subst.v1.json passes checksum."""
        seed_path = get_seed_path("subst.v1.json")
        content = seed_path.read_bytes()
        # Should not raise
        verify_checksum("subst.v1.json", content)

    def test_verify_checksum_classify_seed_valid(self):
        """Valid classify.v1.json passes checksum."""
        seed_path = get_seed_path("classify.v1.json")
        content = seed_path.read_bytes()
        # Should not raise
        verify_checksum("classify.v1.json", content)

    def test_verify_checksum_tampered_fails(self):
        """Tampered content fails checksum."""
        # Start with valid content
        seed_path = get_seed_path("match.v1.json")
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
# Test: Manifest Registry Root
# =============================================================================


class TestSeedRegistryManifest:
    """Seed registry compatibility maps are derived from verified manifest data."""

    def test_manifest_data_derives_python_registry_views(self):
        """Python registry views must be projections of the canonical manifest."""
        records = SEED_REGISTRY_MANIFEST["seeds"]

        assert SEED_CHECKSUMS == {
            seed_name: record["sha256"]
            for seed_name, record in records.items()
        }
        assert EXPECTED_PROJECTION_IDS == {
            seed_name: record["projection_ids"]
            for seed_name, record in records.items()
        }
        assert MU_SEED_LOCATIONS == {
            seed_name: record["subdir"]
            for seed_name, record in records.items()
        }
        assert SEED_DEPENDENCIES == {
            seed_name: record["dependencies"]
            for seed_name, record in records.items()
            if record["dependencies"]
        }

    def test_manifest_checksum_precedes_manifest_parse(self):
        """Malformed manifest bytes fail at checksum before JSON parsing."""
        repo = Path(__file__).resolve().parents[3]
        script = """
from pathlib import Path

_original_read_bytes = Path.read_bytes

def fake_read_bytes(self):
    if self.name == "seed_registry_manifest.v1.json":
        return b'{"schema": '
    return _original_read_bytes(self)

Path.read_bytes = fake_read_bytes
import rcx_pi.selfhost.seed_integrity
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(repo),
            env={
                **os.environ,
                "PYTHONPATH": str(repo / "mu" / "host" / "python"),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            timeout=10,
        )

        assert proc.returncode != 0
        assert "manifest integrity check failed" in proc.stderr
        assert "JSONDecodeError" not in proc.stderr


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

    def test_non_dict_seed_fails(self):
        """Seed that isn't a dict fails with ValueError (not AttributeError)."""
        with pytest.raises(ValueError, match="must be a dict"):
            validate_seed_structure("test.json", [])
        with pytest.raises(ValueError, match="must be a dict"):
            validate_seed_structure("test.json", "not a dict")

    def test_meta_not_dict_fails(self):
        """Seed with non-dict meta fails with ValueError (not AttributeError)."""
        seed = {
            "meta": [],  # Should be dict
            "projections": []
        }
        with pytest.raises(ValueError, match="'meta' must be a dict"):
            validate_seed_structure("test.json", seed)

    def test_meta_as_string_fails(self):
        """Seed with string meta fails with ValueError."""
        seed = {
            "meta": "not a dict",
            "projections": []
        }
        with pytest.raises(ValueError, match="'meta' must be a dict"):
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
        seed_path = get_seed_path("match.v1.json")
        with open(seed_path) as f:
            seed = json.load(f)
        # Should not raise
        validate_projection_ids("match.v1.json", seed)

    def test_subst_seed_has_expected_ids(self):
        """subst.v1.json has all expected projection IDs."""
        seed_path = get_seed_path("subst.v1.json")
        with open(seed_path) as f:
            seed = json.load(f)
        # Should not raise
        validate_projection_ids("subst.v1.json", seed)

    def test_classify_seed_has_expected_ids(self):
        """classify.v1.json has all expected projection IDs."""
        seed_path = get_seed_path("classify.v1.json")
        with open(seed_path) as f:
            seed = json.load(f)
        # Should not raise
        validate_projection_ids("classify.v1.json", seed)

    def test_missing_projection_id_fails(self):
        """Seed missing expected projection ID fails."""
        seed = {
            "projections": [
                {"id": "match.done", "pattern": {}, "body": {}},
                # Missing other expected IDs
            ]
        }
        with pytest.raises(ValueError, match="projection ID mismatch"):
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
                {"id": "match.typed.descend", "pattern": {}, "body": {}},  # Phase 6c
                {"id": "match.dict.descend", "pattern": {}, "body": {}},
            ]
        }
        with pytest.raises(ValueError, match="projection order mismatch"):
            validate_projection_ids("match.v1.json", seed)

    def test_unknown_seed_fails_closed(self):
        """Unknown seed name must raise ValueError (fail-closed)."""
        seed = {"projections": []}
        with pytest.raises(ValueError, match="no entry in EXPECTED_PROJECTION_IDS"):
            validate_projection_ids("unknown.json", seed)


# =============================================================================
# Test: Full Verified Load
# =============================================================================


class TestVerifiedLoad:
    """Test load_verified_seed function."""

    def test_load_match_seed_verified(self):
        """Load match.v1.json with full verification."""
        seed_path = get_seed_path("match.v1.json")
        seed = load_verified_seed(seed_path)

        assert "meta" in seed
        assert "projections" in seed
        assert seed["meta"]["name"] == "MATCH_SEED"

    def test_load_subst_seed_verified(self):
        """Load subst.v1.json with full verification."""
        seed_path = get_seed_path("subst.v1.json")
        seed = load_verified_seed(seed_path)

        assert "meta" in seed
        assert "projections" in seed
        assert seed["meta"]["name"] == "SUBST_SEED"

    def test_load_classify_seed_verified(self):
        """Load classify.v1.json with full verification."""
        seed_path = get_seed_path("classify.v1.json")
        seed = load_verified_seed(seed_path)

        assert "meta" in seed
        assert "projections" in seed
        assert seed["meta"]["name"] == "CLASSIFY_SEED"

    def test_load_with_verify_false_skips_checks(self, tmp_path):
        """verify=False skips integrity checks."""
        # Create a seed that would fail checksum
        seed_file = tmp_path / "test.json"
        seed_file.write_text('{"meta": {"version": "1.0", "name": "TEST", "description": "test"}, "projections": []}')

        # Should work with verify=False
        seed = load_verified_seed(seed_file, verify=False)
        assert seed["meta"]["name"] == "TEST"

    def test_load_verified_seed_delegates_path_bytes_to_image_boundary(
        self, tmp_path, monkeypatch
    ):
        """Path loader reads bytes once, then delegates verification to image boundary."""
        seed_file = tmp_path / "delegated.v1.json"
        seed_bytes = (
            b'{"meta": {"version": "1.0", "name": "DELEGATED", '
            b'"description": "test"}, "projections": []}'
        )
        seed_file.write_bytes(seed_bytes)
        calls = []

        def fake_seed_image_loader(seed_name, image_bytes, verify=True):
            calls.append((seed_name, image_bytes, verify))
            return {"delegated": True}

        monkeypatch.setattr(
            seed_integrity_module,
            "load_verified_seed_image",
            fake_seed_image_loader,
        )

        assert seed_integrity_module.load_verified_seed(
            seed_file, verify=False
        ) == {"delegated": True}
        assert calls == [("delegated.v1.json", seed_bytes, False)]

    def test_load_nonexistent_raises(self):
        """Loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_verified_seed(Path("/nonexistent/path.json"))

    def test_load_unknown_seed_fails_closed(self, tmp_path):
        """I-7 boundary: load_verified_seed(verify=True) rejects unknown seeds.

        The primary gate is verify_checksum() which raises ValueError for any
        seed_name not in SEED_CHECKSUMS. This means validate_projection_ids()
        warn-only for unregistered names is a secondary layer — unknown seeds
        never reach it through the normal verified load path.
        """
        # Create a syntactically valid seed file with an unknown name
        unknown_seed = tmp_path / "unknown_attacker.v1.json"
        unknown_seed.write_text(
            '{"meta": {"version": "1.0", "name": "ATTACK", "description": "x"}, '
            '"projections": [{"id": "evil.inject", "pattern": {}, "body": {}}]}'
        )
        # verify=True must reject at checksum stage (fail-closed)
        with pytest.raises(ValueError, match="Unknown seed"):
            load_verified_seed(unknown_seed, verify=True)

    def test_load_current_kernel_seed_checksum_and_projection_ids(self):
        """Production JSON rcx_load boundary verifies current kernel seed bytes."""
        seed_path = get_seed_path("kernel.v1.json")
        content = seed_path.read_bytes()

        assert compute_checksum(content) == SEED_CHECKSUMS["kernel.v1.json"]

        seed = load_verified_seed(seed_path, verify=True)
        actual_ids = [proj["id"] for proj in seed["projections"]]
        assert actual_ids == EXPECTED_PROJECTION_IDS["kernel.v1.json"]

    def test_load_verified_seed_rejects_tampered_known_seed_before_json_parse(
        self, tmp_path
    ):
        """Tampered known seed bytes fail checksum before malformed JSON parsing."""
        tampered_seed = tmp_path / "kernel.v1.json"
        tampered_seed.write_bytes(b'{"meta": ')

        with pytest.raises(ValueError, match="integrity check failed"):
            load_verified_seed(tampered_seed, verify=True)

    def test_load_verified_seed_image_rejects_tampered_known_seed_before_json_parse(
        self,
    ):
        """Byte boundary fails checksum before malformed JSON parsing."""
        with pytest.raises(ValueError, match="integrity check failed"):
            load_verified_seed_image("kernel.v1.json", b'{"meta": ', verify=True)

    def test_load_verified_seed_rejects_malformed_projection_after_checksum(
        self, tmp_path, monkeypatch
    ):
        """A checksum-matching malformed projection fails through structure validation."""
        malformed_seed = tmp_path / "kernel.v1.json"
        content = json.dumps(
            {
                "meta": {
                    "version": "1.0",
                    "name": "KERNEL_SEED",
                    "description": "malformed projection control",
                },
                "projections": [None],
            }
        ).encode("utf-8")
        malformed_seed.write_bytes(content)
        monkeypatch.setitem(
            SEED_CHECKSUMS, "kernel.v1.json", compute_checksum(content)
        )

        with pytest.raises(ValueError, match="projection 0 must be a dict"):
            load_verified_seed(malformed_seed, verify=True)

    def test_load_verified_seed_image_validates_projection_order(
        self, monkeypatch
    ):
        """Byte boundary enforces registered projection IDs and order."""
        expected = EXPECTED_PROJECTION_IDS["kernel.v1.json"]
        wrong_order = list(reversed(expected))
        content = json.dumps(
            {
                "meta": {
                    "version": "1.0",
                    "name": "KERNEL_SEED",
                    "description": "projection order control",
                },
                "projections": [
                    {"id": projection_id, "pattern": {}, "body": {}}
                    for projection_id in wrong_order
                ],
            }
        ).encode("utf-8")
        monkeypatch.setitem(SEED_CHECKSUMS, "kernel.v1.json", compute_checksum(content))

        with pytest.raises(ValueError, match="projection order mismatch"):
            load_verified_seed_image("kernel.v1.json", content, verify=True)


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
        assert "classify.v1.json" in results
        assert results["match.v1.json"] is True
        assert results["subst.v1.json"] is True
        assert results["classify.v1.json"] is True


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

        # Should have loaded successfully (7 projections after Phase 6c type-tagged addition)
        assert len(projections) == 7
        assert projections[0]["id"] == "match.done"
        assert projections[-1]["id"] == "match.wrap"

    def test_subst_mu_loads_verified(self):
        """subst_mu loads projections with verification."""
        from rcx_pi.selfhost.subst_mu import load_subst_projections, clear_projection_cache

        clear_projection_cache()
        projections = load_subst_projections()

        # Should have loaded successfully (12 projections after Phase 6c type-tagged additions)
        assert len(projections) == 12
        assert projections[0]["id"] == "subst.done"
        assert projections[-1]["id"] == "subst.wrap"

    def test_classify_mu_loads_verified(self):
        """classify_mu loads projections with verification."""
        from rcx_pi.selfhost.classify_mu import load_classify_projections, clear_projection_cache

        clear_projection_cache()
        projections = load_classify_projections()

        # Should have loaded successfully (6 projections for Phase 6b classification)
        # Added classify.nested_not_kv to handle nested dict keys
        assert len(projections) == 6
        assert projections[0]["id"] == "classify.done"
        assert projections[-1]["id"] == "classify.wrap"


# =============================================================================
# Test: Checksums Match Reality
# =============================================================================


class TestChecksumsMatchReality:
    """Ensure hardcoded checksums match actual files."""

    def test_match_checksum_is_current(self):
        """match.v1.json checksum in SEED_CHECKSUMS matches file."""
        seed_path = get_seed_path("match.v1.json")
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
        seed_path = get_seed_path("subst.v1.json")
        actual = compute_checksum(seed_path.read_bytes())
        expected = SEED_CHECKSUMS["subst.v1.json"]
        assert actual == expected, (
            f"subst.v1.json checksum mismatch!\n"
            f"  File:     {actual}\n"
            f"  Expected: {expected}\n"
            f"  Update SEED_CHECKSUMS if seed was intentionally changed."
        )

    def test_classify_checksum_is_current(self):
        """classify.v1.json checksum in SEED_CHECKSUMS matches file."""
        seed_path = get_seed_path("classify.v1.json")
        actual = compute_checksum(seed_path.read_bytes())
        expected = SEED_CHECKSUMS["classify.v1.json"]
        assert actual == expected, (
            f"classify.v1.json checksum mismatch!\n"
            f"  File:     {actual}\n"
            f"  Expected: {expected}\n"
            f"  Update SEED_CHECKSUMS if seed was intentionally changed."
        )


# =============================================================================
# Test: Non-Finite Numeric Rejection (F1 hardening)
# =============================================================================


class TestNonFiniteNumericRejection:
    """Seed loader must reject NaN/Infinity for cross-substrate parity."""

    def test_nan_rejected(self, tmp_path):
        """JSON containing NaN is rejected deterministically."""
        seed_file = tmp_path / "nan_test.json"
        seed_file.write_text('{"meta": {"name": "T"}, "projections": [{"id": "x", "pattern": NaN, "body": {}}]}')
        with pytest.raises(ValueError, match="NaN"):
            load_verified_seed(seed_file, verify=False)

    def test_nan_rejected_by_seed_image_boundary(self):
        """The seed image boundary rejects non-finite numeric literals directly."""
        content = b'{"meta": {"name": "T"}, "projections": [{"id": "x", "pattern": NaN, "body": {}}]}'
        with pytest.raises(ValueError, match="NaN"):
            load_verified_seed_image("nan_test.json", content, verify=False)

    def test_infinity_rejected(self, tmp_path):
        """JSON containing Infinity is rejected deterministically."""
        seed_file = tmp_path / "inf_test.json"
        seed_file.write_text('{"meta": {"name": "T"}, "projections": [{"id": "x", "pattern": Infinity, "body": {}}]}')
        with pytest.raises(ValueError, match="Infinity"):
            load_verified_seed(seed_file, verify=False)

    def test_neg_infinity_rejected(self, tmp_path):
        """JSON containing -Infinity is rejected deterministically."""
        seed_file = tmp_path / "neginf_test.json"
        seed_file.write_text('{"meta": {"name": "T"}, "projections": [{"id": "x", "pattern": -Infinity, "body": {}}]}')
        with pytest.raises(ValueError, match="Infinity"):
            load_verified_seed(seed_file, verify=False)

    def test_normal_json_still_loads(self, tmp_path):
        """Normal JSON with standard types loads without error."""
        seed_file = tmp_path / "normal_test.json"
        seed_file.write_text('{"meta": {"name": "T"}, "projections": [{"id": "x", "pattern": {"a": 1}, "body": {"b": 2.5}}]}')
        seed = load_verified_seed(seed_file, verify=False)
        assert seed["projections"][0]["pattern"] == {"a": 1}


# =============================================================================
# Test: Seed Projection Mu Validity Invariant (test-time, not runtime)
# =============================================================================


class TestSeedProjectionMuValidity:
    """All registered seeds must have valid Mu in pattern and body fields."""

    def test_all_seed_projections_are_valid_mu(self):
        """Every projection pattern and body in checksummed seeds passes is_mu()."""
        from rcx_pi.selfhost.mu_type import is_mu

        for seed_name in SEED_CHECKSUMS:
            seed_path = get_seed_path(seed_name)
            seed = load_verified_seed(seed_path)
            for proj in seed["projections"]:
                proj_id = proj.get("id", "<unknown>")
                assert is_mu(proj["pattern"]), (
                    f"Seed {seed_name} projection {proj_id}: "
                    f"pattern is not valid Mu: {proj['pattern']!r}"
                )
                assert is_mu(proj["body"]), (
                    f"Seed {seed_name} projection {proj_id}: "
                    f"body is not valid Mu: {proj['body']!r}"
                )
