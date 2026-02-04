"""
Seed Integrity Fuzzer - Property-Based Tests for Seed Validation Functions

Tests the security-critical functions that protect against malicious seed files:
- verify_checksum() - Detects tampering via SHA256
- validate_seed_structure() - Ensures required schema
- validate_projection_ids() - Ensures expected projections present

Added 2026-01-29 after 7-agent steelman review identified this as a fuzzer gap.
"""

import json
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pathlib import Path
from unittest.mock import patch

from rcx_pi.selfhost.seed_integrity import (
    compute_checksum,
    verify_checksum,
    validate_seed_structure,
    validate_projection_ids,
    load_verified_seed,
    SEED_CHECKSUMS,
    EXPECTED_PROJECTION_IDS,
)


# =============================================================================
# Strategies for generating test inputs
# =============================================================================

# Random bytes that can tamper with content
random_bytes = st.binary(min_size=1, max_size=1000)

# Random strings for field names and values
random_strings = st.text(min_size=0, max_size=50)

# Random meta dictionaries (may or may not have required fields)
random_meta = st.dictionaries(
    keys=random_strings,
    values=st.one_of(random_strings, st.integers(), st.booleans()),
    max_size=5,
)

# Valid meta (always has required fields)
valid_meta = st.fixed_dictionaries({
    "version": st.text(min_size=1, max_size=10),
    "name": st.text(min_size=1, max_size=20),
    "description": st.text(min_size=1, max_size=100),
})

# Random projections (may or may not have required fields)
random_projection = st.dictionaries(
    keys=random_strings,
    values=st.one_of(random_strings, st.integers(), st.dictionaries(random_strings, random_strings, max_size=3)),
    max_size=5,
)

# Valid projection (always has required fields)
valid_projection = st.fixed_dictionaries({
    "id": st.text(min_size=1, max_size=30).filter(lambda x: x.strip()),
    "pattern": st.dictionaries(random_strings, random_strings, max_size=3),
    "body": st.dictionaries(random_strings, random_strings, max_size=3),
})


@st.composite
def malformed_seed(draw):
    """Generate a seed that may or may not have required structure."""
    # Sometimes include meta, sometimes don't
    has_meta = draw(st.booleans())
    has_projections = draw(st.booleans())

    seed = {}
    if has_meta:
        seed["meta"] = draw(st.one_of(random_meta, valid_meta))
    if has_projections:
        seed["projections"] = draw(st.one_of(
            st.lists(random_projection, max_size=3),
            st.lists(valid_projection, max_size=3),
            st.text(),  # Sometimes not even a list
            st.integers(),  # Sometimes a number
        ))

    # Add random extra keys
    for key in draw(st.lists(random_strings.filter(lambda k: k not in ["meta", "projections"]), max_size=3)):
        seed[key] = draw(random_strings)

    return seed


# =============================================================================
# Checksum Fuzzing
# =============================================================================

class TestChecksumFuzzing:
    """Fuzz tests for checksum computation and verification."""

    @given(content=st.binary(min_size=0, max_size=10000))
    @settings(deadline=5000)
    def test_checksum_is_64_hex_chars(self, content):
        """Checksum is always 64 hex characters (SHA256)."""
        checksum = compute_checksum(content)
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

    @given(content=st.binary(min_size=1, max_size=10000))
    @settings(deadline=5000)
    def test_checksum_is_deterministic(self, content):
        """Same content always produces same checksum."""
        c1 = compute_checksum(content)
        c2 = compute_checksum(content)
        assert c1 == c2

    @given(c1=st.binary(min_size=1, max_size=1000), c2=st.binary(min_size=1, max_size=1000))
    @settings(deadline=5000)
    def test_different_content_different_checksum(self, c1, c2):
        """Different content produces different checksum (with high probability)."""
        assume(c1 != c2)
        assert compute_checksum(c1) != compute_checksum(c2)

    @given(seed_name=st.sampled_from(list(SEED_CHECKSUMS.keys())),
           tamper=st.binary(min_size=1, max_size=100))
    @settings(deadline=5000)
    def test_tampered_content_fails_verification(self, seed_name, tamper):
        """Any tampering with known seeds fails checksum verification."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path(seed_name)
        if not seed_path.exists():
            assume(False)  # Skip if seed doesn't exist

        original = seed_path.read_bytes()
        tampered = original + tamper

        with pytest.raises(ValueError, match="integrity check failed"):
            verify_checksum(seed_name, tampered)

    @given(seed_prefix=st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters=("_", "-")
    )))
    @settings(deadline=5000)
    def test_unknown_seed_name_rejected(self, seed_prefix):
        """Unknown seed names are rejected."""
        seed_name = f"unknown_{seed_prefix}.json"
        assume(seed_name not in SEED_CHECKSUMS)
        with pytest.raises(ValueError, match="Unknown seed"):
            verify_checksum(seed_name, b"test content")


# =============================================================================
# Structure Validation Fuzzing
# =============================================================================

class TestStructureValidationFuzzing:
    """Fuzz tests for seed structure validation."""

    @given(seed=malformed_seed())
    @settings(deadline=5000)
    def test_malformed_seeds_handled(self, seed):
        """Malformed seeds either pass (if valid) or raise ValueError."""
        try:
            validate_seed_structure("test.json", seed)
            # If it passed, verify it has required structure
            assert "meta" in seed
            assert "projections" in seed
            assert isinstance(seed["projections"], list)
        except ValueError:
            # Expected for malformed seeds
            pass

    @given(meta=valid_meta, projections=st.lists(valid_projection, min_size=0, max_size=5))
    @settings(deadline=5000)
    def test_valid_structure_always_passes(self, meta, projections):
        """Valid structure always passes validation."""
        seed = {"meta": meta, "projections": projections}
        # Should not raise
        validate_seed_structure("test.json", seed)

    @given(projections=st.lists(valid_projection, min_size=1, max_size=5))
    @settings(deadline=5000)
    def test_missing_meta_always_fails(self, projections):
        """Missing meta always fails."""
        seed = {"projections": projections}
        with pytest.raises(ValueError, match="missing 'meta'"):
            validate_seed_structure("test.json", seed)

    @given(meta=valid_meta)
    @settings(deadline=5000)
    def test_missing_projections_always_fails(self, meta):
        """Missing projections always fails."""
        seed = {"meta": meta}
        with pytest.raises(ValueError, match="missing 'projections'"):
            validate_seed_structure("test.json", seed)

    @given(meta=valid_meta, non_list=st.one_of(st.integers(), st.text(), st.dictionaries(st.text(), st.text())))
    @settings(deadline=5000)
    def test_projections_not_list_fails(self, meta, non_list):
        """Projections that aren't a list always fail."""
        assume(not isinstance(non_list, list))
        seed = {"meta": meta, "projections": non_list}
        with pytest.raises(ValueError, match="must be a list"):
            validate_seed_structure("test.json", seed)


# =============================================================================
# Projection ID Validation Fuzzing
# =============================================================================

class TestProjectionIdValidationFuzzing:
    """Fuzz tests for projection ID validation."""

    @given(seed_name=st.sampled_from(list(EXPECTED_PROJECTION_IDS.keys())))
    @settings(deadline=5000)
    def test_real_seeds_pass_id_validation(self, seed_name):
        """Real seeds pass projection ID validation."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path(seed_name)
        if not seed_path.exists():
            assume(False)

        with open(seed_path) as f:
            seed = json.load(f)

        # Should not raise
        validate_projection_ids(seed_name, seed)

    @given(
        seed_name=st.sampled_from(list(EXPECTED_PROJECTION_IDS.keys())),
        remove_idx=st.integers(min_value=0, max_value=10)
    )
    @settings(deadline=5000)
    def test_missing_projection_fails(self, seed_name, remove_idx):
        """Missing a projection fails validation."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path(seed_name)
        if not seed_path.exists():
            assume(False)

        with open(seed_path) as f:
            seed = json.load(f)

        # Remove one projection
        if not seed["projections"]:
            assume(False)
        idx = remove_idx % len(seed["projections"])
        removed = seed["projections"].pop(idx)

        # Should fail
        with pytest.raises(ValueError, match="missing expected projection IDs"):
            validate_projection_ids(seed_name, seed)

    @given(unknown_seed=st.text(min_size=1, max_size=30).filter(
        lambda x: x not in EXPECTED_PROJECTION_IDS
    ))
    @settings(deadline=5000)
    def test_unknown_seed_skips_validation(self, unknown_seed):
        """Unknown seed names skip projection ID validation (for extensibility)."""
        seed = {"projections": []}
        # Should not raise (skips validation for unknown seeds)
        validate_projection_ids(unknown_seed, seed)


# =============================================================================
# Order Sensitivity Tests (Security Critical)
# =============================================================================

class TestProjectionOrderSecurity:
    """Tests that projection order is validated (security critical)."""

    @given(seed_name=st.sampled_from([k for k in EXPECTED_PROJECTION_IDS.keys() if "kernel" not in k]))
    @settings(deadline=5000)
    def test_wrap_must_be_last(self, seed_name):
        """Wrap projection must be last (catch-all position)."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path(seed_name)
        if not seed_path.exists():
            assume(False)

        with open(seed_path) as f:
            seed = json.load(f)

        # Move wrap to first position
        projections = seed["projections"]
        wrap_idx = next(
            (i for i, p in enumerate(projections) if p.get("id", "").endswith(".wrap")),
            None
        )
        if wrap_idx is None or wrap_idx == 0:
            assume(False)

        # Move wrap to front
        wrap_proj = projections.pop(wrap_idx)
        projections.insert(0, wrap_proj)

        # Should fail
        with pytest.raises(ValueError, match="must be last"):
            validate_projection_ids(seed_name, seed)

    def test_kernel_wrap_must_be_first(self):
        """Kernel wrap must be first (entry point)."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path("kernel.v1.json")
        if not seed_path.exists():
            pytest.skip("kernel.v1.json not found")

        with open(seed_path) as f:
            seed = json.load(f)

        # Move kernel.wrap to last position
        projections = seed["projections"]
        wrap_idx = next(
            (i for i, p in enumerate(projections) if p.get("id") == "kernel.wrap"),
            None
        )
        if wrap_idx is None:
            pytest.skip("kernel.wrap not found")

        # Move wrap to end
        wrap_proj = projections.pop(wrap_idx)
        projections.append(wrap_proj)

        # Should fail
        with pytest.raises(ValueError, match="must be first"):
            validate_projection_ids("kernel.v1.json", seed)

    def test_kernel_unwrap_must_be_last(self):
        """Kernel unwrap must be last (exit point)."""
        from rcx_pi.selfhost.seed_integrity import get_seed_path

        seed_path = get_seed_path("kernel.v1.json")
        if not seed_path.exists():
            pytest.skip("kernel.v1.json not found")

        with open(seed_path) as f:
            seed = json.load(f)

        # Move kernel.unwrap to second-to-last position (swap with second-to-last)
        # Keep kernel.wrap first to avoid triggering the "must be first" error
        projections = seed["projections"]
        unwrap_idx = next(
            (i for i, p in enumerate(projections) if p.get("id") == "kernel.unwrap"),
            None
        )
        if unwrap_idx is None or len(projections) < 3:
            pytest.skip("kernel.unwrap not found or not enough projections")

        # Swap unwrap with second-to-last (if unwrap is last)
        if unwrap_idx == len(projections) - 1:
            projections[-1], projections[-2] = projections[-2], projections[-1]

        # Should fail
        with pytest.raises(ValueError, match="must be last"):
            validate_projection_ids("kernel.v1.json", seed)


# =============================================================================
# Full Load Pipeline Fuzzing
# =============================================================================

class TestFullLoadPipelineFuzzing:
    """Fuzz tests for the full verified load pipeline."""

    @given(content=st.binary(min_size=0, max_size=1000))
    @settings(deadline=5000)
    def test_random_bytes_rejected(self, content):
        """Random bytes are rejected (not valid JSON or seed)."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(content)
            seed_file = Path(f.name)

        try:
            # Should either fail JSON parse or validation
            with pytest.raises((json.JSONDecodeError, ValueError, UnicodeDecodeError)):
                load_verified_seed(seed_file, verify=True)
        finally:
            os.unlink(seed_file)

    @given(seed=malformed_seed())
    @settings(deadline=5000)
    def test_malformed_json_seeds_handled(self, seed):
        """Malformed JSON seeds are properly handled."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(seed, f)
            seed_file = Path(f.name)

        try:
            # Try loading without checksum verification (checksum would fail anyway)
            loaded = load_verified_seed(seed_file, verify=False)
            # If it loaded, structure was at least valid JSON
            assert isinstance(loaded, dict)
        except (ValueError, TypeError):
            # Expected for malformed seeds
            pass
        finally:
            os.unlink(seed_file)


# =============================================================================
# Injection Attack Tests
# =============================================================================

class TestInjectionAttacks:
    """Tests for various injection attack attempts."""

    @given(injection=st.text(min_size=1, max_size=100))
    @settings(deadline=5000)
    def test_path_traversal_in_seed_name_rejected(self, injection):
        """Path traversal attempts in seed name are rejected."""
        # Try to inject path traversal
        malicious_name = f"../../../{injection}.json"

        with pytest.raises(ValueError, match="Unknown seed"):
            verify_checksum(malicious_name, b"test")

    @given(null_bytes=st.integers(min_value=1, max_value=10))
    @settings(deadline=5000)
    def test_null_byte_injection_rejected(self, null_bytes):
        """Null byte injection in seed name is rejected."""
        malicious_name = f"match.v1\x00.json"

        # Either unknown seed error or checksum mismatch
        with pytest.raises(ValueError):
            verify_checksum(malicious_name, b"test")

    @given(unicode_injection=st.text(alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters=(".", "_", "-")
    ), min_size=1, max_size=20))
    @settings(deadline=5000)
    def test_unicode_seed_name_variations(self, unicode_injection):
        """Unicode variations in seed names are rejected."""
        assume(unicode_injection not in SEED_CHECKSUMS)

        with pytest.raises(ValueError, match="Unknown seed"):
            verify_checksum(unicode_injection + ".json", b"test")
