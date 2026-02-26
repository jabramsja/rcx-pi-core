"""
A11 gate tests: Ontology Promotion Contract governance.

Wave class: L4_ENABLER (contract-only, no runtime changes).

Tests verify:
1. Contract document exists and has required structure
2. All 4 invariant IDs are present with required fields
3. TASKS.md and STATUS.md reference the contract
4. Enabler lock: no runtime host files changed in this wave
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
CONTRACT_PATH = REPO_ROOT / "mu" / "docs" / "core" / "OntologyPromotionContract.v0.md"

# Runtime host directories that must NOT be touched in an L4_ENABLER wave
RUNTIME_HOST_DIRS = [
    REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost",
    REPO_ROOT / "mu" / "host" / "js" / "engine",
    REPO_ROOT / "mu" / "host" / "js" / "core",
    REPO_ROOT / "mu" / "host" / "js" / "api",
    REPO_ROOT / "mu" / "host" / "js" / "cli",
]

INVARIANT_IDS = [
    "INV_OPROMO_1",
    "INV_OPROMO_2",
    "INV_OPROMO_3",
    "INV_OPROMO_4",
]

REQUIRED_FIELDS_PER_INVARIANT = [
    "rationale",
    "measurable check",
    "fail-closed rule",
]


class TestContractExists:
    """Verify the contract document exists and has required structure."""

    def test_contract_file_exists(self):
        assert CONTRACT_PATH.exists(), (
            f"OntologyPromotionContract.v0.md not found at {CONTRACT_PATH}"
        )

    def test_contract_has_doc_status_header(self):
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        assert "DOC_STATUS" in content, "Contract must have DOC_STATUS header"
        assert "TYPE: DESIGN_SPEC" in content, "Contract must be DESIGN_SPEC type"

    def test_contract_has_scope_note(self):
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        assert "v0 is contract-only" in content, (
            "Contract must include v0 scope note (contract-only, runtime deferred to A12)"
        )
        assert "runtime enforcement deferred to a12" in content.lower(), (
            "Contract must state runtime enforcement is deferred to A12"
        )

    def test_contract_has_grounding_tests(self):
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        assert "test_ontology_promotion_contract_gate" in content, (
            "Contract GROUNDING_TESTS must reference this gate test file"
        )


class TestInvariantCompleteness:
    """Verify all 4 invariant IDs are present with required fields."""

    def test_all_invariant_ids_present(self):
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        for inv_id in INVARIANT_IDS:
            assert inv_id in content, (
                f"Missing invariant {inv_id} in contract"
            )

    @pytest.mark.parametrize("inv_id", INVARIANT_IDS)
    def test_invariant_has_required_fields(self, inv_id):
        content = CONTRACT_PATH.read_text(encoding="utf-8")

        # Find the section for this invariant
        inv_pos = content.find(inv_id)
        assert inv_pos >= 0, f"{inv_id} not found in contract"

        # Get content from this invariant to the next ### heading or end
        rest = content[inv_pos:]
        next_heading = rest.find("\n### ", 1)
        if next_heading > 0:
            section = rest[:next_heading]
        else:
            section = rest

        section_lower = section.lower()
        for field in REQUIRED_FIELDS_PER_INVARIANT:
            assert field.lower() in section_lower, (
                f"{inv_id} missing required field: '{field}'"
            )

    def test_inv_opromo_1_recurrence_witnesses(self):
        """INV_OPROMO_1 must require >= 2 recurrence witnesses."""
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        # Find section
        pos = content.find("INV_OPROMO_1")
        section = content[pos:content.find("\n### ", pos + 1)]
        assert ">= 2" in section or ">=2" in section or "at least two" in section.lower(), (
            "INV_OPROMO_1 must specify >= 2 independent recurrence witnesses"
        )

    def test_inv_opromo_2_perturbation_stability(self):
        """INV_OPROMO_2 must reference bounded perturbation."""
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        pos = content.find("INV_OPROMO_2")
        section = content[pos:content.find("\n### ", pos + 1)]
        assert "perturbation" in section.lower(), (
            "INV_OPROMO_2 must reference bounded perturbation"
        )

    def test_inv_opromo_3_host_cannot_mint(self):
        """INV_OPROMO_3 must prohibit host from minting ontology tokens."""
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        pos = content.find("INV_OPROMO_3")
        section = content[pos:content.find("\n### ", pos + 1)]
        assert "host" in section.lower(), (
            "INV_OPROMO_3 must reference host prohibition"
        )
        assert "seed" in section.lower(), (
            "INV_OPROMO_3 must reference seed authority"
        )

    def test_inv_opromo_4_provenance(self):
        """INV_OPROMO_4 must require provenance lineage."""
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        pos = content.find("INV_OPROMO_4")
        section = content[pos:]
        assert "provenance" in section.lower(), (
            "INV_OPROMO_4 must reference provenance lineage"
        )
        assert "tau-lineage" in section.lower() or "τ-lineage" in section.lower(), (
            "INV_OPROMO_4 must reference tau-lineage"
        )


class TestGovernanceReferences:
    """Verify TASKS.md and STATUS.md reference the contract."""

    def test_tasks_md_has_a11_tracker(self):
        tasks_path = REPO_ROOT / "TASKS.md"
        content = tasks_path.read_text(encoding="utf-8")
        assert "wave-a11" in content.lower() or "a11" in content.lower(), (
            "TASKS.md must contain A11 tracker sync note"
        )

    def test_status_md_references_contract(self):
        status_path = REPO_ROOT / "STATUS.md"
        content = status_path.read_text(encoding="utf-8")
        assert "OntologyPromotionContract" in content, (
            "STATUS.md must reference OntologyPromotionContract.v0.md"
        )


class TestEnablerLock:
    """Verify A11 is truly L4_ENABLER: no runtime host changes."""

    def test_no_runtime_host_files_changed(self):
        """A11 must not touch runtime host files.

        Checks staged + unstaged diffs (pre-commit context) and HEAD^..HEAD
        (post-commit context) to verify no runtime host paths are changed
        in the A11 wave specifically. The origin/dev...HEAD range is NOT
        used because this branch may carry prior waves (e.g., A10) that
        legitimately changed runtime files.
        """
        runtime_prefixes = [
            "mu/host/python/rcx_pi/selfhost/",
            "mu/host/js/engine/",
            "mu/host/js/core/",
            "mu/host/js/api/",
            "mu/host/js/cli/",
        ]

        changed_files: set[str] = set()

        def _collect(args: list[str]) -> None:
            result = subprocess.run(
                args, cwd=str(REPO_ROOT),
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                changed_files.update(
                    f.strip() for f in result.stdout.strip().split("\n")
                    if f.strip()
                )

        # Staged changes (pre-commit state)
        _collect(["git", "diff", "--cached", "--name-only"])
        # Unstaged changes
        _collect(["git", "diff", "--name-only"])

        # If nothing staged/unstaged, check last commit (post-commit state)
        if not changed_files:
            _collect(["git", "diff", "--name-only", "HEAD~1..HEAD"])

        violations = [
            f for f in changed_files
            if any(f.startswith(prefix) for prefix in runtime_prefixes)
        ]
        assert not violations, (
            f"L4_ENABLER wave must not touch runtime host files. "
            f"Violations: {violations}"
        )

    def test_contract_in_docs_directory(self):
        """Contract must reside in mu/docs/core/."""
        assert CONTRACT_PATH.parent.name == "core", (
            "Contract must be in mu/docs/core/"
        )
        assert CONTRACT_PATH.parent.parent.name == "docs", (
            "Contract must be in mu/docs/core/"
        )

    def test_contract_does_not_import_runtime(self):
        """Contract doc must not contain import statements or code blocks
        that would indicate runtime changes."""
        content = CONTRACT_PATH.read_text(encoding="utf-8")
        # Contract is markdown, not Python — should not have Python imports
        assert "from rcx_pi" not in content, (
            "Contract doc must not import from rcx_pi"
        )
        assert "import step_mu" not in content, (
            "Contract doc must not import step_mu"
        )
