"""
Cross-substrate mu_hash parity test.

Verifies that Python mu_hash() and JavaScript muHash() produce
identical SHA-256 hashes for the same Mu values. This is critical
for Content-Addressed Mu: if canonical JSON diverges between
substrates, the hash-accelerated equality guarantee fails silently.

Adversarial edge cases tested:
- Unicode (Latin, CJK, emoji, line/paragraph separators)
- Control characters (newline, tab)
- Empty containers and strings
- Boolean vs integer distinction (true ≠ 1)
- Key sorting in nested objects
- Special characters in keys and values
- Production-like structures (traces, engine state)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import mu_hash


VECTORS_PATH = Path(__file__).parents[1] / "fixtures" / "hashing_vectors.json"
JS_HASH_SCRIPT = Path(__file__).parents[2] / "mu" / "host" / "js" / "hash_vectors.js"


def load_vectors():
    with open(VECTORS_PATH) as f:
        return json.load(f)["vectors"]


# =============================================================================
# Python-side hash tests
# =============================================================================


class TestPythonHashDeterminism:
    """Verify Python mu_hash is deterministic and distinguishes types."""

    def test_all_vectors_produce_hashes(self):
        """Every vector produces a valid 64-char hex hash."""
        for v in load_vectors():
            h = mu_hash(v["value"])
            assert len(h) == 64, f"{v['id']}: hash length {len(h)}, expected 64"
            assert all(c in "0123456789abcdef" for c in h), f"{v['id']}: non-hex chars in hash"

    def test_bool_vs_int_different_hashes(self):
        """true and 1 must produce different hashes (anti-coercion)."""
        h_true = mu_hash(True)
        h_one = mu_hash(1)
        assert h_true != h_one, "true and 1 must hash differently"

    def test_false_vs_zero_different_hashes(self):
        """false and 0 must produce different hashes."""
        h_false = mu_hash(False)
        h_zero = mu_hash(0)
        assert h_false != h_zero, "false and 0 must hash differently"

    def test_dict_key_order_irrelevant(self):
        """Same dict with different insertion order must hash identically."""
        h1 = mu_hash({"z": 1, "a": 2, "m": 3})
        h2 = mu_hash({"a": 2, "m": 3, "z": 1})
        assert h1 == h2, "Dict key order must not affect hash"

    def test_all_vectors_unique(self):
        """All vectors produce distinct hashes (except bool_vs_int pair which are deliberately different values)."""
        vectors = load_vectors()
        hashes = {}
        for v in vectors:
            h = mu_hash(v["value"])
            if h in hashes:
                # Only acceptable collision: impossible with SHA-256 for these inputs
                pytest.fail(f"Hash collision: {v['id']} and {hashes[h]} both hash to {h[:16]}...")
            hashes[h] = v["id"]


# =============================================================================
# Cross-substrate parity test
# =============================================================================


class TestCrossSubstrateHashParity:
    """Verify Python and JS produce identical hashes for all vectors."""

    def test_python_js_hashes_match(self):
        """Python mu_hash and JS muHash produce identical results for all vectors."""
        vectors = load_vectors()

        # Compute Python hashes
        py_hashes = {}
        for v in vectors:
            py_hashes[v["id"]] = mu_hash(v["value"])

        # Run JS hash computation
        result = subprocess.run(
            ["node", str(JS_HASH_SCRIPT), str(VECTORS_PATH)],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"JS hash script failed: {result.stderr}"

        js_hashes = json.loads(result.stdout)

        # Compare every vector
        failures = []
        for v in vectors:
            vid = v["id"]
            py_h = py_hashes[vid]
            js_h = js_hashes.get(vid)
            if js_h is None:
                failures.append(f"  {vid}: missing from JS output")
            elif py_h != js_h:
                failures.append(f"  {vid}: Python={py_h[:16]}... JS={js_h[:16]}...")

        assert not failures, (
            f"mu_hash parity failures ({len(failures)}/{len(vectors)}):\n"
            + "\n".join(failures)
        )

    def test_js_script_exists(self):
        """JS hash script exists and is readable."""
        assert JS_HASH_SCRIPT.exists(), f"Missing: {JS_HASH_SCRIPT}"


# =============================================================================
# Canonical JSON edge case tests
# =============================================================================


class TestCanonicalJsonEdgeCases:
    """Test specific canonical JSON serialization edge cases."""

    def test_unicode_preserved_not_escaped(self):
        """Non-ASCII Unicode must be preserved, not escaped to \\uXXXX."""
        # Python ensure_ascii=False keeps Unicode as-is
        # JS JSON.stringify also keeps Unicode as-is (modern Node.js)
        canonical = json.dumps("café", sort_keys=True, ensure_ascii=False)
        assert "café" in canonical, f"Unicode should be preserved: {canonical}"
        assert "\\u" not in canonical, f"Unicode should not be escaped: {canonical}"

    def test_forward_slash_not_escaped(self):
        """Forward slash must NOT be escaped (Python default, JS default)."""
        canonical = json.dumps("a/b", sort_keys=True, ensure_ascii=False)
        assert "/" in canonical, f"Forward slash should not be escaped: {canonical}"
        assert "\\/" not in canonical, f"Forward slash should not be escaped: {canonical}"

    def test_separators_are_python_default(self):
        """Canonical JSON uses Python default separators: ', ' and ': '."""
        canonical = json.dumps({"a": 1, "b": 2}, sort_keys=True, ensure_ascii=False)
        assert '{"a": 1, "b": 2}' == canonical, f"Unexpected separators: {canonical}"
