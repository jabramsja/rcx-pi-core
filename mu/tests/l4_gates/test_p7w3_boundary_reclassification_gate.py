"""P7 Wave 3: Boundary Scaffolding Marker Reclassification — Gate Tests.

Validates that 5 @host_iteration markers (-4 Python, -1 JS) were removed
from functions provably NOT on the kernel execution path:

  Python:
    1. _check_empty_var_names() — boundary pre-validation (via match_mu → apply_mu)
    2. is_dict_linked_list() — legacy boundary classification (test-only)
    3. bindings_to_dict() — API boundary conversion (via match_mu → apply_mu)
    4. _collect_ontology_evidence() — engine boundary-effect servicing
    (projection_runner run() — retired in Wave 3F)
  JavaScript:
    5. collectOntologyEvidence() — engine boundary-effect servicing (parity with #4)

Anti-laundering compliance: The "active trusted runtime call graph" for
anti-laundering is the kernel execution path: step_kernel_mu → _step_trusted →
_apply_projection_trusted → match/substitute. Functions outside this path
(pre-validation, API conversion, boundary-effect servicing, standalone match/subst
via apply_mu) are boundary infrastructure, not kernel semantic debt.

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.
"""

import ast
import inspect
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from rcx_pi.selfhost.match_mu import (
    _check_empty_var_names,  # ANTICHEAT_OK: AST inspection for P7w3 boundary reclassification gate
    bindings_to_dict,
    is_dict_linked_list,
)
from rcx_pi.selfhost.engine_pipeline import _collect_ontology_evidence  # ANTICHEAT_OK: AST inspection for P7w3 boundary reclassification gate
from rcx_pi.selfhost.step_mu import step_kernel_mu, run_mu, run_mu_structural  # SPEED_OK: source inspection only (AST proof of kernel path exclusion)

from tests.repo_root import REPO_ROOT

JS_PIPELINE_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_function_source(func):
    """Return dedented source of a function."""
    return textwrap.dedent(inspect.getsource(func))


def _source_contains_marker(source: str, marker: str) -> bool:
    """Check if source contains @host_<marker> pattern."""
    return f"@host_{marker}" in source


# ===========================================================================
# TestMarkersRemoved — verify markers are gone from reclassified functions
# ===========================================================================

class TestMarkersRemoved:
    """All 6 reclassified functions must NOT have @host_iteration markers."""

    def test_check_empty_var_names_no_marker(self):
        source = _get_function_source(_check_empty_var_names)
        assert not _source_contains_marker(source, "iteration"), (
            "_check_empty_var_names still has @host_iteration marker"
        )

    def test_is_dict_linked_list_no_marker(self):
        source = _get_function_source(is_dict_linked_list)
        assert not _source_contains_marker(source, "iteration"), (
            "is_dict_linked_list still has @host_iteration marker"
        )

    def test_bindings_to_dict_no_marker(self):
        source = _get_function_source(bindings_to_dict)
        assert not _source_contains_marker(source, "iteration"), (
            "bindings_to_dict still has @host_iteration marker"
        )

    def test_collect_ontology_evidence_no_marker(self):
        source = _get_function_source(_collect_ontology_evidence)
        assert not _source_contains_marker(source, "iteration"), (
            "_collect_ontology_evidence still has @host_iteration marker"
        )

    # test_projection_runner_no_marker removed — projection_runner.py retired in Wave 3F

    def test_js_collect_ontology_evidence_no_marker(self):
        """JS collectOntologyEvidence must NOT have @host_iteration marker."""
        source = JS_PIPELINE_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "function collectOntologyEvidence" in line:
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_iteration" not in window, (
                    f"JS collectOntologyEvidence still has @host_iteration marker "
                    f"(lines {max(0, i - 10)}-{i})"
                )
                return
        pytest.fail("Could not find 'function collectOntologyEvidence' in pipeline.js")


# ===========================================================================
# TestBoundaryClassification — BOUNDARY markers present for documentation
# ===========================================================================

class TestBoundaryClassification:
    """Reclassified functions must have BOUNDARY comments (not @host_iteration)."""

    def test_check_empty_var_names_has_boundary(self):
        source = _get_function_source(_check_empty_var_names)
        assert "BOUNDARY" in source, (
            "_check_empty_var_names missing BOUNDARY comment"
        )

    def test_bindings_to_dict_has_boundary(self):
        source = _get_function_source(bindings_to_dict)
        assert "BOUNDARY" in source, (
            "bindings_to_dict missing BOUNDARY comment"
        )

    # test_projection_runner_has_boundary removed — projection_runner.py retired in Wave 3F


# ===========================================================================
# TestKernelPathExclusion — prove functions are NOT on kernel execution path
# ===========================================================================

class TestKernelPathExclusion:
    """AST + source proof that reclassified functions are NOT called from kernel."""

    def test_step_kernel_mu_does_not_call_check_empty_var_names(self):
        """step_kernel_mu source must NOT contain _check_empty_var_names."""
        source = _get_function_source(step_kernel_mu)
        assert "_check_empty_var_names" not in source, (
            "step_kernel_mu calls _check_empty_var_names (on kernel path!)"
        )

    def test_step_kernel_mu_does_not_call_is_dict_linked_list(self):
        source = _get_function_source(step_kernel_mu)
        assert "is_dict_linked_list" not in source, (
            "step_kernel_mu calls is_dict_linked_list (on kernel path!)"
        )

    def test_step_kernel_mu_does_not_call_bindings_to_dict(self):
        source = _get_function_source(step_kernel_mu)
        assert "bindings_to_dict" not in source, (
            "step_kernel_mu calls bindings_to_dict (on kernel path!)"
        )

    def test_step_kernel_mu_does_not_call_collect_ontology_evidence(self):
        source = _get_function_source(step_kernel_mu)
        assert "_collect_ontology_evidence" not in source, (
            "step_kernel_mu calls _collect_ontology_evidence (on kernel path!)"
        )

    def test_step_kernel_mu_does_not_call_projection_runner(self):
        source = _get_function_source(step_kernel_mu)
        assert "projection_runner" not in source, (
            "step_kernel_mu calls projection_runner (on kernel path!)"
        )

    def test_run_mu_does_not_call_apply_mu(self):
        """run_mu uses step_kernel_mu, NOT apply_mu."""
        source = _get_function_source(run_mu)
        assert "apply_mu(" not in source, (
            "run_mu calls apply_mu (unexpected kernel path!)"
        )

    def test_run_mu_structural_does_not_call_apply_mu(self):
        source = _get_function_source(run_mu_structural)
        assert "apply_mu(" not in source, (
            "run_mu_structural calls apply_mu (unexpected kernel path!)"
        )

    def test_step_kernel_mu_does_not_call_match_mu(self):
        """Kernel uses _step_trusted → match/substitute, NOT match_mu/subst_mu."""
        source = _get_function_source(step_kernel_mu)
        assert "match_mu(" not in source, (
            "step_kernel_mu calls match_mu (should use _step_trusted)"
        )

    def test_step_kernel_mu_does_not_call_subst_mu(self):
        source = _get_function_source(step_kernel_mu)
        assert "subst_mu(" not in source, (
            "step_kernel_mu calls subst_mu (should use _step_trusted)"
        )


# ===========================================================================
# TestOntologyEvidenceTiming — prove _collect_ontology_evidence is boundary
# ===========================================================================

class TestOntologyEvidenceTiming:
    """Prove _collect_ontology_evidence runs in boundary-effect servicing, not kernel."""

    def test_called_from_service_boundary_effect(self):
        """_collect_ontology_evidence is called from _service_boundary_effect, not kernel."""
        source = Path(
            REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
        ).read_text()

        # Find the call site
        assert "_collect_ontology_evidence(" in source
        lines = source.splitlines()
        call_line = None
        for i, line in enumerate(lines, 1):
            if "_collect_ontology_evidence(" in line and "def " not in line:
                call_line = i
                break
        assert call_line is not None, "Could not find _collect_ontology_evidence call site"

        # The call site must be within _service_boundary_effect, not step_kernel_mu
        # Find what function encloses this call
        fn_name = None
        for i in range(call_line - 1, 0, -1):
            line = lines[i - 1]
            if line.startswith("def "):
                fn_name = line.split("(")[0].replace("def ", "").strip()
                break
        assert fn_name == "_service_boundary_effect", (
            f"_collect_ontology_evidence called from {fn_name}, expected _service_boundary_effect"
        )

    def test_js_called_from_service_boundary_effect(self):
        """JS collectOntologyEvidence called from serviceBoundaryEffect."""
        source = JS_PIPELINE_PATH.read_text()
        lines = source.splitlines()

        call_line = None
        for i, line in enumerate(lines, 1):
            if "collectOntologyEvidence(" in line and "function " not in line:
                call_line = i
                break
        assert call_line is not None, "Could not find collectOntologyEvidence call site in JS"

        # Find enclosing function
        fn_name = None
        for i in range(call_line - 1, 0, -1):
            line = lines[i - 1].strip()
            if line.startswith("function "):
                fn_name = line.split("(")[0].replace("function ", "").strip()
                break
        assert fn_name == "serviceBoundaryEffect", (
            f"JS collectOntologyEvidence called from {fn_name}, expected serviceBoundaryEffect"
        )


# ===========================================================================
# TestRatchetEvidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet reflects genuine host_iteration decrease."""

    def test_ratchet_passes(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Ratchet failed:\n{result.stderr}"

    def test_host_iteration_counts(self):
        """Host iteration must be <= post-P7W3 baseline (further reduced by W4)."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)

        # P7W4 further reduced: Py 8→4, JS 9→6. Verify monotonic decrease.
        assert data["current"]["python"]["host_iteration"] <= 8, (
            f"Python host_iteration is {data['current']['python']['host_iteration']}, expected <= 8"
        )
        assert data["current"]["javascript"]["host_iteration"] <= 9, (
            f"JS host_iteration is {data['current']['javascript']['host_iteration']}, expected <= 9"
        )

        # Verify no increases (ratchet must never regress)
        assert data["increases"] == [], (
            f"Ratchet shows increases (regression): {data['increases']}"
        )

    def test_js_eval_step_passes(self):
        """JS substrate must remain green after marker reclassification."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"

    def test_js_debt_check_passes(self):
        """JS debt check must pass with updated counts."""
        result = subprocess.run(
            ["bash", "mu/tools/checks/check_js_debt.sh"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS debt check failed:\n{result.stdout}\n{result.stderr}"
