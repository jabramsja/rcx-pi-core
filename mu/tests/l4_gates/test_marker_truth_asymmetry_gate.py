"""L4 gate: marker-truth asymmetry fix (MT1).

Proves that the 3 scoped sites have honest @host_iteration markers
and that the ratchet baseline reflects the corrected counts.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


class TestMarkerTruthAsymmetryGate:
    """Gate: 3 marker-truth sites are honestly marked in both substrates."""

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

    def test_python_collect_ontology_evidence_marked(self):
        """Python _collect_ontology_evidence has AST_OK: infra (structural walker boundary)."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        text = path.read_text()
        lines = text.splitlines()
        for line in lines:
            if "_collect_ontology_evidence" in line and "def " in line:
                assert "AST_OK: infra" in line, (
                    "_collect_ontology_evidence must have AST_OK: infra (structural walker boundary)"
                )
                assert "@host_iteration" not in line, (
                    "_collect_ontology_evidence must not have @host_iteration (displaced by evidence_walker.v1.json)"
                )
                return
        pytest.fail("_collect_ontology_evidence def line not found")

    def test_js_collect_ontology_evidence_marked(self):
        """JS collectOntologyEvidence has @host_iteration marker."""
        path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
        text = path.read_text()
        # Find the function and verify marker is in the preceding JSDoc
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function collectOntologyEvidence(" in line:
                # Check the JSDoc block above (within 5 lines)
                block = "\n".join(lines[max(0, i - 5):i])
                assert "@host_iteration" in block, (
                    "collectOntologyEvidence JSDoc must have @host_iteration marker"
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
        # Wave rt6: evidence_walker.v1.json displaced 1 @host_iteration → 11
        assert py["host_iteration"] >= 11, (
            f"Python host_iteration baseline must be >= 11, got {py['host_iteration']}"
        )
        assert js["host_iteration"] >= 11, (
            f"JS host_iteration baseline must be >= 11 (MT1), got {js['host_iteration']}"
        )
