"""L4 gate: marker-truth asymmetry fix (MT1).
Non-blocker sweep (2026-03-14): HOST_LOOP markers added to _match_inner loops,
projection_runner.py AST_OK infra markers added (projection_runner.py retired in Wave 3F). Ratchet baseline unchanged.

Proves that scoped sites have honest markers: list_to_linked is
BOUNDARY boundary-normalization evidence, not tracked @host_iteration, while
collectOntologyEvidence (Py+JS) was reclassified to BOUNDARY in P7 Wave 3
(off kernel path). Ratchet baseline reflects the corrected counts.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


class TestMarkerTruthAsymmetryGate:
    """Gate: marker-truth sites honestly marked as tracked debt or boundary evidence."""

    def test_python_list_to_linked_boundary_normalization_evidence(self):
        """Python list_to_linked is boundary-normalization evidence, not tracked debt."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        text = path.read_text()
        lines = text.splitlines()
        for line in lines:
            if "for item in reversed(items):" in line:
                assert "@host_iteration" not in line, (
                    "list_to_linked conversion loop must not count as tracked @host_iteration debt"
                )
                assert "BOUNDARY" in line and "boundary-normalization" in line, (
                    "list_to_linked conversion loop must remain boundary-normalization evidence"
                )
                return
        pytest.fail("list_to_linked for-loop not found in step_mu.py")

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

    def test_ratchet_baseline_reflects_current(self):
        """Ratchet baseline reflects direct list_to_linked/listToLinked demotion."""
        baseline_path = REPO_ROOT / "tools" / "checks" / "host_semantics_baseline.json"
        data = json.loads(baseline_path.read_text())
        py = data["counts"]["python"]
        js = data["counts"]["javascript"]
        assert py["host_iteration"] == 1
        assert js["host_iteration"] == 1
        assert data["total_python"] == 2
        assert data["total_javascript"] == 3
        assert data["total"] == 5

        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        ratchet = json.loads(result.stdout)
        assert ratchet["increases"] == [], (
            f"Ratchet shows increases: {ratchet['increases']}"
        )
        assert ratchet["current"]["python"]["host_iteration"] == 1
        assert ratchet["current"]["javascript"]["host_iteration"] == 1


class TestMT2IsinstanceMarkerCoverage:
    """MT2 gate: all isinstance calls in step_mu.py are annotated with AST_OK markers."""

    def test_step_mu_isinstance_fully_marked(self):
        """Every isinstance in step_mu.py has an AST_OK or ANTICHEAT_OK marker."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        lines = path.read_text().splitlines()
        unmarked = []
        for i, line in enumerate(lines, 1):
            if "isinstance" in line and "AST_OK" not in line and "ANTICHEAT_OK" not in line:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue  # Skip comments
                unmarked.append(f"  line {i}: {stripped}")
        assert not unmarked, (
            f"step_mu.py has {len(unmarked)} unmarked isinstance call(s):\n"
            + "\n".join(unmarked)
        )
