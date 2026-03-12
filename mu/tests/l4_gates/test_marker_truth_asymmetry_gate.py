"""L4 gate: marker-truth asymmetry fix (MT1).

Proves that scoped sites have honest markers: list_to_linked retains
@host_iteration (kernel-path), while collectOntologyEvidence (Py+JS) was
reclassified to BOUNDARY in P7 Wave 3 (off kernel path). Ratchet baseline
reflects the corrected counts.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


class TestMarkerTruthAsymmetryGate:
    """Gate: marker-truth sites honestly marked (list_to_linked kernel, ontology evidence boundary)."""

    def test_python_list_to_linked_marked(self):
        """Python list_to_linked has @host_iteration marker."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        text = path.read_text()
        # Find the function and verify marker is on the for-loop line
        lines = text.splitlines()
        found = False
        for line in lines:
            if "for item in reversed(items):" in line and "@host_iteration" in line:
                found = True
                break
        assert found, "list_to_linked for-loop must have @host_iteration marker"

    def test_python_collect_ontology_evidence_boundary(self):
        """Python _collect_ontology_evidence reclassified as BOUNDARY (P7 Wave 3 — off kernel path)."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
        text = path.read_text()
        lines = text.splitlines()
        for line in lines:
            if "_collect_ontology_evidence" in line and "def " in line:
                assert "@host_iteration" not in line, (
                    "_collect_ontology_evidence still has @host_iteration (reclassified P7w3)"
                )
                assert "BOUNDARY" in line, (
                    "_collect_ontology_evidence must have BOUNDARY comment (P7w3 reclassification)"
                )
                return
        pytest.fail("_collect_ontology_evidence def line not found")

    def test_js_collect_ontology_evidence_boundary(self):
        """JS collectOntologyEvidence reclassified as BOUNDARY (P7 Wave 3 — off kernel path)."""
        path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
        text = path.read_text()
        # Find the function and verify marker is NOT in the preceding JSDoc
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function collectOntologyEvidence(" in line:
                # Check the JSDoc block above (within 5 lines)
                block = "\n".join(lines[max(0, i - 5):i])
                assert "@host_iteration" not in block, (
                    "collectOntologyEvidence JSDoc still has @host_iteration (reclassified P7w3)"
                )
                assert "BOUNDARY" in block, (
                    "collectOntologyEvidence JSDoc must have BOUNDARY comment (P7w3 reclassification)"
                )
                return
        pytest.fail("collectOntologyEvidence function not found in pipeline.js")

    def test_ratchet_baseline_reflects_mt1(self):
        """Ratchet baseline reflects the MT1 marker additions."""
        baseline_path = REPO_ROOT / "tools" / "checks" / "host_semantics_baseline.json"
        data = json.loads(baseline_path.read_text())
        py = data["counts"]["python"]
        js = data["counts"]["javascript"]
        # MT1 added 2 Python iteration markers and 1 JS iteration marker
        # Wave 4f corrected JS count: header self-references no longer inflate baseline
        # Real JS iteration markers: 10 (was 11 when constants.js header was counted)
        assert py["host_iteration"] >= 12, (
            f"Python host_iteration baseline must be >= 12 (MT1), got {py['host_iteration']}"
        )
        assert js["host_iteration"] >= 10, (
            f"JS host_iteration baseline must be >= 10 (honest count, wave 4f), got {js['host_iteration']}"
        )
