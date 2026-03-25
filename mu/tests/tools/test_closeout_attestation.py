"""Tests for closeout attestation checker.

Covers:
1. Attestation rejects GO when required evidence is missing
2. Attestation rejects overclaiming when invariant results are absent
3. Attestation distinguishes proof classes
4. Attestation passes on valid evidence
5. Machine-generated changed files used (not freehand)
6. Control-surface wave requires invariant proofs
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


att_mod = _load_module(
    "check_closeout_attestation",
    REPO_ROOT / "tools" / "checks" / "check_closeout_attestation.py",
)


class TestValidateAttestation:
    """Validate attestation rejects incomplete evidence."""

    def test_rejects_missing_changed_files(self):
        authorized, issues = att_mod.validate_attestation({"proofs": [{"claim": "x"}]})
        assert not authorized
        assert any("changed_files" in i for i in issues)

    def test_rejects_no_proofs(self):
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [],
        })
        assert not authorized
        assert any("No proofs" in i for i in issues)

    def test_rejects_blockers(self):
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [{"claim": "test", "proof_class": "BEHAVIORAL", "passed": True}],
            "blockers": [{"claim": "inv-1", "message": "failed"}],
        })
        assert not authorized
        assert any("Blocker" in i for i in issues)

    def test_rejects_unproved_areas(self):
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [{"claim": "test", "proof_class": "BEHAVIORAL", "passed": True}],
            "unproved": ["control surface invariants not checked"],
        })
        assert not authorized
        assert any("Unproved" in i for i in issues)

    def test_control_surface_wave_requires_invariant_proofs(self):
        """GO not authorized for control-surface wave without INV proofs."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [{"claim": "test_pass", "proof_class": "BEHAVIORAL", "passed": True}],
        })
        assert not authorized
        assert any("invariant proofs" in i.lower() for i in issues)

    def test_passes_valid_attestation(self):
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "test", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert authorized, issues
        assert not issues

    def test_passes_control_surface_with_invariant_proofs(self):
        """GO authorized for control-surface wave with proper INV + validation + receipt_chain proofs."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "tests", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: gate:control_surface_invariants", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: pytest mu/tests/tools/test_executor_dispatch.py", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "receipt_chain: phase_b_to_commit_executor", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert authorized, issues

    def test_rejects_control_surface_without_behavioral_validation(self):
        """GO not authorized for control-surface wave without BEHAVIORAL validation proof."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "tests", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert not authorized
        assert any("BEHAVIORAL validation-command" in i for i in issues)

    def test_rejects_control_surface_with_only_gate_validation(self):
        """GO not authorized when the only BEHAVIORAL validation is a gate check.

        This is the exact bug from Bridge R4: gate-style 'validation: gate:...'
        proofs were accepted as test execution proof, allowing GO with no actual
        tests executed.
        """
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "validation: gate:control_surface_invariants", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert not authorized
        assert any("gate-style" in i.lower() or "do not count" in i.lower() for i in issues)


    def test_rejects_receipt_chain_files_without_receipt_chain_proof(self):
        """GO not authorized when receipt-chain files are changed but no receipt_chain proof."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/commit_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "tests", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: gate:control_surface_invariants", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert not authorized
        assert any("receipt_chain" in i.lower() for i in issues)

    def test_passes_receipt_chain_files_with_receipt_chain_proof(self):
        """GO authorized when receipt-chain files are changed AND receipt_chain proof present."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/executors/commit_executor.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "tests", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: gate:control_surface_invariants", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: pytest mu/tests/tools/test_executor_dispatch.py", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "receipt_chain: phase_b_to_commit_executor", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert authorized, issues

    def test_non_receipt_chain_control_surface_does_not_need_receipt_proof(self):
        """Control-surface files outside the receipt chain don't need receipt_chain proof."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["mu/tools/agents/bridge_adapters.py"],
            "is_control_surface_wave": True,
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "INV-1: implementer-not-review-mode", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "INV-2: bridge-loop-reimplements", "proof_class": "SOURCE_LOCK", "passed": True},
                {"claim": "tests", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: gate:control_surface_invariants", "proof_class": "BEHAVIORAL", "passed": True},
                {"claim": "validation: pytest mu/tests/tools/", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert authorized, issues

    def test_rejects_declared_changed_files(self):
        """GO must be rejected when changed_files proof is DECLARED (caller-supplied)."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [
                {"claim": "changed_files", "proof_class": "DECLARED", "source": "caller"},
                {"claim": "test", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert not authorized
        assert any("DECLARED" in i for i in issues)

    def test_accepts_behavioral_changed_files(self):
        """GO authorized when changed_files proof is BEHAVIORAL (git-derived)."""
        authorized, issues = att_mod.validate_attestation({
            "changed_files": ["a.py"],
            "proofs": [
                {"claim": "changed_files", "proof_class": "BEHAVIORAL", "source": "git"},
                {"claim": "test", "proof_class": "BEHAVIORAL", "passed": True},
            ],
            "blockers": [],
            "unproved": [],
        })
        assert authorized


class TestProofClasses:
    """Proof classes are distinguished in attestation."""

    def test_git_derived_files_get_behavioral_proof(self):
        """When changed_files is None (derived from git), proof is BEHAVIORAL."""
        att = att_mod.generate_attestation(REPO_ROOT, changed_files=None)
        cf_proof = next(p for p in att["proofs"] if p["claim"] == "changed_files")
        assert cf_proof["proof_class"] == "BEHAVIORAL"
        assert "git" in cf_proof["source"]

    def test_caller_supplied_files_get_declared_proof(self):
        """When changed_files is caller-supplied, proof is DECLARED not BEHAVIORAL."""
        att = att_mod.generate_attestation(REPO_ROOT, changed_files=["README.md"])
        cf_proof = next(p for p in att["proofs"] if p["claim"] == "changed_files")
        assert cf_proof["proof_class"] == "DECLARED"
        assert "caller" in cf_proof["source"].lower()

    def test_source_lock_proof_for_invariants(self):
        att = att_mod.generate_attestation(
            REPO_ROOT,
            changed_files=["mu/tools/executors/phase_b_executor.py"],
        )
        inv_proofs = [p for p in att["proofs"] if p["proof_class"] == "SOURCE_LOCK"]
        assert len(inv_proofs) > 0, "Control-surface wave should produce SOURCE_LOCK proofs"


class TestGenerateAttestation:
    """Generate attestation from repo state."""

    def test_detects_control_surface_wave(self):
        att = att_mod.generate_attestation(
            REPO_ROOT,
            changed_files=["mu/tools/executors/phase_b_executor.py"],
        )
        assert att["is_control_surface_wave"] is True

    def test_non_control_surface_wave(self):
        att = att_mod.generate_attestation(
            REPO_ROOT,
            changed_files=["README.md"],
        )
        assert att["is_control_surface_wave"] is False

    def test_mu_runner_activates_control_surface(self):
        att = att_mod.generate_attestation(
            REPO_ROOT, changed_files=["mu/tools/runners/run_review.py"],
        )
        assert att["is_control_surface_wave"] is True

    def test_mu_shared_utils_activates_control_surface(self):
        att = att_mod.generate_attestation(
            REPO_ROOT, changed_files=["mu/tools/runners/shared_agent_utils.py"],
        )
        assert att["is_control_surface_wave"] is True

    def test_mu_closeout_checker_activates_control_surface(self):
        att = att_mod.generate_attestation(
            REPO_ROOT, changed_files=["mu/tools/checks/check_closeout_attestation.py"],
        )
        assert att["is_control_surface_wave"] is True

    def test_mu_invariant_checker_activates_control_surface(self):
        att = att_mod.generate_attestation(
            REPO_ROOT, changed_files=["mu/tools/checks/check_control_surface_invariants.py"],
        )
        assert att["is_control_surface_wave"] is True

    def test_includes_validation_commands(self):
        att = att_mod.generate_attestation(
            REPO_ROOT,
            changed_files=["a.py"],
            validation_commands=[
                {"command": "pytest tests", "exit_code": 0, "output": "5 passed"},
            ],
        )
        val_proofs = [p for p in att["proofs"] if "validation" in p["claim"]]
        assert len(val_proofs) == 1
        assert val_proofs[0]["passed"] is True

    def test_go_blocked_by_failed_invariant(self):
        """If control-surface invariant fails, go_authorized must be False."""
        # Create a temp repo with broken implementer
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "mu" / "tools" / "executors").mkdir(parents=True)
            (repo / "mu" / "tools" / "agents").mkdir(parents=True)
            # Broken implementer: references bridge_supervisor
            (repo / "mu" / "tools" / "executors" / "phase_b_implementer.py").write_text(
                'import bridge_supervisor\nsubprocess.run(["python3", "bridge_supervisor.py", "review"])\n'
            )
            (repo / "mu" / "tools" / "executors" / "phase_b_executor.py").write_text("")
            (repo / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py").write_text("")
            (repo / "mu" / "tools" / "agents" / "meta_bridge_client.py").write_text("")
            # Create the checker script (copy from real repo)
            checks_dir = repo / "tools" / "checks"
            checks_dir.mkdir(parents=True)
            import shutil
            shutil.copy2(
                REPO_ROOT / "tools" / "checks" / "check_control_surface_invariants.py",
                checks_dir / "check_control_surface_invariants.py",
            )

            att = att_mod.generate_attestation(
                repo,
                changed_files=["mu/tools/executors/phase_b_implementer.py"],
            )
            # Should have blocker from INV-1
            assert att["is_control_surface_wave"]
            assert not att["go_authorized"]
