"""
L4 Gate: evidence_walker.v1.json proof-class verification.

Python proves structural trace walking for ontology evidence collection.
JavaScript source-locks the same seed registry entries but intentionally does
not load evidence_walker.v1 into the JS runtime path.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_evidence_walker_gate.py -v
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.step_mu import (
    run_mu,  # SPEED_OK: boundary wrapper tested via run_mu
)
from rcx_pi.selfhost.seed_integrity import (
    load_verified_seed,
    get_seed_path,
    EXPECTED_PROJECTION_IDS,
    SEED_CHECKSUMS,
)
from tests.repo_root import REPO_ROOT


# ---------------------------------------------------------------------------
# Gate Tests
# ---------------------------------------------------------------------------

class TestEvidenceWalkerSeedGate:
    """Gate: evidence_walker.v1.json loaded and verified in Python."""

    def test_seed_loads_with_4_projections(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        assert len(seed["projections"]) == 4

    def test_projection_ids_registered(self):
        assert "evidence_walker.v1.json" in EXPECTED_PROJECTION_IDS
        assert len(EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]) == 4

    def test_checksum_registered(self):
        assert "evidence_walker.v1.json" in SEED_CHECKSUMS


class TestEvidenceWalkerJsRegistryGate:
    """Gate: JS registry source-lock for evidence_walker.v1, not runtime parity."""

    def test_js_seed_checksums_contains_evidence_walker(self):
        """JS SEED_CHECKSUMS must include evidence_walker.v1.json."""
        import re
        js_main = REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js"
        source = js_main.read_text()
        match = re.search(r"evidence_walker\.v1\.json.*?:\s*'([a-f0-9]+)'", source)
        assert match, "evidence_walker.v1.json not found in JS SEED_CHECKSUMS"
        py_checksum = SEED_CHECKSUMS["evidence_walker.v1.json"]
        assert match.group(1) == py_checksum, (
            f"JS/Python checksum mismatch: JS={match.group(1)} Python={py_checksum}"
        )

    def test_js_projection_ids_contains_evidence_walker(self):
        """JS EXPECTED_PROJECTION_IDS must include evidence_walker.v1.json."""
        import re
        js_main = REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js"
        source = js_main.read_text()
        assert "'evidence_walker.v1.json'" in source or '"evidence_walker.v1.json"' in source, (
            "evidence_walker.v1.json not found in JS EXPECTED_PROJECTION_IDS"
        )
        py_ids = EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]
        for pid in py_ids:
            assert pid in source, f"JS missing projection ID: {pid}"

    def test_js_runtime_seed_projection_map_does_not_load_evidence_walker(self):
        """JS must not imply runtime parity by loading evidence_walker.v1."""
        import re
        js_main = REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js"
        source = js_main.read_text()
        match = re.search(
            r"const seedProjectionMap = Object\.assign\(Object\.create\(null\), \{(?P<body>.*?)\n\}\);",
            source,
            re.DOTALL,
        )
        assert match, "JS seedProjectionMap block not found"
        assert "evidence_walker.v1.json" not in match.group("body")


@pytest.mark.slow
class TestEvidenceWalkerWiringGate:
    """Gate: evidence walker produces correct output for trace inputs."""

    def test_null_trace_produces_done(self):
        """Null trace → evidence_done with null collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        wrapped = {"evidence_walk": {"trace": None}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert isinstance(result, dict)
        assert "evidence_done" in result
        assert result["evidence_done"]["collected"] is None

    def test_trace_with_projection_collects_entry(self):
        """Trace entry with projection → raw entry collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0, "projection": "test.id"}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Mu runtime normalizes single-element {head,tail:null} to Python list
        if isinstance(collected, list):
            assert len(collected) == 1
            assert collected[0]["projection"] == "test.id"
        else:
            assert collected["head"]["projection"] == "test.id"

    def test_trace_without_projection_collects_entry(self):
        """Trace entry without projection → raw entry still collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {"head": {"state": "a", "step": 0}, "tail": None}
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        if isinstance(collected, list):
            assert len(collected) == 1
            assert "projection" not in collected[0]
        else:
            assert "projection" not in collected["head"]

    def test_multi_entry_trace(self):
        """Multi-entry trace → all entries collected."""
        projs = load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]
        trace = {
            "head": {"state": "a", "step": 0, "projection": "p1"},
            "tail": {
                "head": {"state": "b", "step": 1},
                "tail": {
                    "head": {"state": "c", "step": 2, "projection": "p2"},
                    "tail": None,
                },
            },
        }
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=30)
        assert "evidence_done" in result
        collected = result["evidence_done"]["collected"]
        # Count entries
        count = 0
        node = collected
        if isinstance(node, list):
            count = len(node)
        else:
            while isinstance(node, dict) and "head" in node:
                count += 1
                node = node.get("tail")
        assert count == 3
