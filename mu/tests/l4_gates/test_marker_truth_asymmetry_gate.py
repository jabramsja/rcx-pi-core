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


def _find_line_index(lines: list[str], needle: str) -> int:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    pytest.fail(f"Could not find line containing {needle!r}")


def _leading_jsdoc_block(lines: list[str], function_index: int) -> str:
    for index in range(function_index - 1, -1, -1):
        if lines[index].strip() == "/**":
            return "\n".join(lines[index:function_index])
        if lines[index].strip().startswith("function "):
            break
    pytest.fail(f"Could not find JSDoc block before line {function_index + 1}")


def _js_function_body(lines: list[str], function_index: int) -> str:
    body = []
    depth = 0
    opened = False
    for line in lines[function_index:]:
        body.append(line)
        if "{" in line:
            opened = True
        depth += line.count("{") - line.count("}")
        if opened and depth == 0:
            return "\n".join(body)
    pytest.fail(f"Could not find JS function body ending after line {function_index + 1}")


def _js_host_iteration_sites() -> list[tuple[Path, int, str]]:
    sites = []
    js_root = REPO_ROOT / "mu" / "host" / "js"
    for path in sorted(js_root.rglob("*.js")):
        if "/tests/" in path.as_posix():
            continue
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            if "@host_iteration" in line:
                sites.append((path, line_no, line))
    return sites


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

    def test_js_active_kernel_core_loop_is_mu_fuel_governed_with_watchdog(self):
        """JS tracked iteration marker now names the residual fuel-governed watchdog loop."""
        path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
        lines = path.read_text().splitlines()
        function_index = _find_line_index(lines, "function _stepKernelCore(")
        jsdoc = _leading_jsdoc_block(lines, function_index)
        body = _js_function_body(lines, function_index)

        assert "@host_iteration" in jsdoc, (
            "_stepKernelCore must carry the residual JS @host_iteration marker"
        )
        assert "residual kernel driver watchdog" in jsdoc
        assert "supplied Mu fuel owns progress" in jsdoc
        assert "for (let i = 0; i < maxSteps; i++)" not in body, (
            "_stepKernelCore reintroduced the old maxSteps-owned kernel loop"
        )
        assert "while (!fuelSupplied || fuelCursor !== null)" in body, (
            "_stepKernelCore must drive supplied-fuel progress from the Mu linked-list cursor"
        )
        assert "if (stepsUsed >= maxSteps)" in body, (
            "_stepKernelCore must keep maxSteps as a watchdog check"
        )
        assert "fuelCursor = fuelCursor.tail" in body and "stepsUsed++" in body, (
            "_stepKernelCore must consume one Mu fuel node per kernel step"
        )

    def test_js_host_iteration_inventory_is_not_stale_bootstrap_step_only(self):
        """The sole JS host-iteration marker is on the active kernel loop, not bootstrap step."""
        kernel_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
        bootstrap_path = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"
        sites = _js_host_iteration_sites()

        assert len(sites) == 1, (
            "JS @host_iteration marker count must remain one; move the marker, do not add one"
        )
        assert sites[0][0] == kernel_path, (
            f"JS @host_iteration must be in kernel.js, got {sites}"
        )
        assert all(site[0] != bootstrap_path for site in sites), (
            "bootstrap_core.step must not retain stale JS @host_iteration tracking"
        )

    def test_js_bootstrap_step_is_boundary_not_tracked_host_iteration(self):
        """bootstrap_core.step may scan projections, but it is not the tracked kernel loop."""
        path = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"
        lines = path.read_text().splitlines()
        function_index = _find_line_index(lines, "function step(projections, input)")
        jsdoc = _leading_jsdoc_block(lines, function_index)
        body = _js_function_body(lines, function_index)

        assert "@host_iteration" not in jsdoc
        assert "@host_iteration" not in body
        assert "BOUNDARY" in jsdoc
        assert "for (const proj of projections)" in body


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
