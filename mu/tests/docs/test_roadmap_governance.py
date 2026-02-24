"""
Roadmap Document Governance Tests - Lightweight enforcement for roadmap/ folder.

The roadmap/ folder follows DIFFERENT rules than mu/docs/core/ and other governed folders:
- Roadmap docs define SEQUENCE and DESIGN only, not current state
- They must link UP to STATUS.md and TASKS.md (not duplicate their content)
- They do NOT require DOC_STATUS headers (they're planning docs, not specs)

This is enforced separately from the main doc governance per the exception
documented in DocGovernance.v0.md.

See roadmap/MANIFEST.md for the full linking rules.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_roadmap_governance.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
ROADMAP_FOLDER = REPO_ROOT / "roadmap"
ROOT_ROADMAP = REPO_ROOT / "ROADMAP.md"


# =============================================================================
# Helper Functions
# =============================================================================

def get_roadmap_docs() -> list[Path]:
    """Get all roadmap markdown docs (root ROADMAP + roadmap/ folder docs)."""
    docs: list[Path] = []
    if ROOT_ROADMAP.exists():
        docs.append(ROOT_ROADMAP)
    if ROADMAP_FOLDER.exists():
        docs.extend(sorted(ROADMAP_FOLDER.glob("*.md")))
    return docs


# =============================================================================
# Reference Header Checks
# =============================================================================

class TestRoadmapReferenceHeaders:
    """Roadmap docs must link UP to canonical sources."""

    def test_roadmap_folder_exists(self):
        """roadmap/ folder must exist."""
        assert ROADMAP_FOLDER.exists(), "roadmap/ folder missing"

    def test_manifest_exists(self):
        """MANIFEST.md must exist to define reading order."""
        manifest = ROADMAP_FOLDER / "MANIFEST.md"
        assert manifest.exists(), "roadmap/MANIFEST.md missing - required for linking rules"

    def test_root_roadmap_exists(self):
        """ROADMAP.md must exist at repo root."""
        assert ROOT_ROADMAP.exists(), "ROADMAP.md missing at repo root"

    def test_all_docs_have_status_reference(self):
        """All roadmap docs must reference STATUS.md."""
        missing = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Check for STATUS.md reference
            if not re.search(r'\[`?STATUS\.md`?\]', content):
                missing.append(doc_path.name)

        if missing:
            msg = "\nRoadmap docs missing STATUS.md reference:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add reference header per roadmap/MANIFEST.md linking rules:\n"
            msg += '  > **Current State**: See [`STATUS.md`](../STATUS.md) or [`STATUS.md`](STATUS.md)\n'
            pytest.fail(msg)

    def test_all_docs_have_tasks_reference(self):
        """All roadmap docs must reference TASKS.md."""
        missing = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Check for TASKS.md reference
            if not re.search(r'\[`?TASKS\.md`?\]', content):
                missing.append(doc_path.name)

        if missing:
            msg = "\nRoadmap docs missing TASKS.md reference:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add reference header per roadmap/MANIFEST.md linking rules:\n"
            msg += '  > **Authorization**: See [`TASKS.md`](../TASKS.md) or [`TASKS.md`](TASKS.md)\n'
            pytest.fail(msg)


# =============================================================================
# No Inline State Checks
# =============================================================================

class TestRoadmapNoInlineState:
    """Roadmap docs must not contain inline current state."""

    # Patterns that indicate inline state (not allowed in roadmap docs)
    FORBIDDEN_STATE_PATTERNS = [
        (r'^#+\s*Current State\s*$', "## Current State section header"),
        (r'\*\*(?:Completed|In Progress|Awaiting):\*\*', "**Completed:**/**In Progress:** lists"),
        (r'^\s*-\s*\[[ x]\]', "Checkbox task lists (use TASKS.md instead)"),
    ]

    def test_no_current_state_sections(self):
        """Roadmap docs should not have 'Current State' sections."""
        violations = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Remove code blocks (they might contain examples)
            content_no_code = re.sub(r'```[\s\S]*?```', '', content)

            for pattern, desc in self.FORBIDDEN_STATE_PATTERNS:
                if re.search(pattern, content_no_code, re.MULTILINE | re.IGNORECASE):
                    violations.append((doc_path.name, desc))
                    break  # One violation per doc is enough

        if violations:
            msg = "\nRoadmap docs with inline state (violates roadmap linking rules):\n"
            for doc, desc in sorted(set(violations)):
                msg += f"  - {doc}: {desc}\n"
            msg += "\nFix: Roadmap docs define SEQUENCE only. Track state in STATUS.md.\n"
            pytest.fail(msg)


# =============================================================================
# Link Validation
# =============================================================================

class TestRoadmapLinkValidation:
    """Validate that links in roadmap docs point to existing files."""

    def test_status_md_exists(self):
        """STATUS.md must exist at repo root."""
        assert (REPO_ROOT / "STATUS.md").exists(), "STATUS.md missing from repo root"

    def test_tasks_md_exists(self):
        """TASKS.md must exist at repo root."""
        assert (REPO_ROOT / "TASKS.md").exists(), "TASKS.md missing from repo root"

    def test_internal_links_valid(self):
        """Links within roadmap/ should point to existing files."""
        broken = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Find markdown links: [text](path)
            links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', content)

            for link_text, link_target in links:
                # Skip external links
                if link_target.startswith(('http://', 'https://', '#')):
                    continue

                # Resolve relative path from the doc's directory
                target_path = doc_path.parent / link_target

                # Normalize and check existence
                target_path = target_path.resolve()
                if not target_path.exists():
                    broken.append((doc_path.name, link_target))

        if broken:
            msg = "\nBroken links in roadmap docs:\n"
            for doc, target in sorted(set(broken)):
                msg += f"  - {doc} -> {target}\n"
            pytest.fail(msg)


# =============================================================================
# Scope Declaration Check
# =============================================================================

class TestRoadmapScopeDeclaration:
    """Roadmap docs should declare their scope."""

    # Acceptable scope declarations
    SCOPE_PATTERNS = [
        r'This document defines (?:SEQUENCE|DESIGN|EXIT CRITERIA)',
        r'\*\*Scope\*\*:.*(?:SEQUENCE|DESIGN|DECISION|sequence|design|only)',
        r'Draft specs live in `roadmap/`',
    ]

    def test_docs_declare_scope(self):
        """Roadmap docs should declare their limited scope."""
        missing_scope = []

        for doc_path in get_roadmap_docs():
            # Skip MANIFEST.md (it defines the rules, doesn't need to follow them)
            if doc_path.name == "MANIFEST.md":
                continue

            content = doc_path.read_text()

            has_scope = any(
                re.search(pattern, content, re.IGNORECASE)
                for pattern in self.SCOPE_PATTERNS
            )

            if not has_scope:
                missing_scope.append(doc_path.name)

        if missing_scope:
            msg = "\nRoadmap docs missing scope declaration:\n"
            for doc in sorted(missing_scope):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add scope line to reference header, e.g.:\n"
            msg += '  > **Scope**: This document defines SEQUENCE only.\n'
            pytest.fail(msg)


# =============================================================================
# Coverage Report
# =============================================================================

class TestRoadmapCoverage:
    """Report on roadmap doc coverage."""

    def test_minimum_roadmap_docs(self):
        """Verify minimum roadmap docs exist."""
        docs = get_roadmap_docs()
        MIN_DOCS = 3  # At least MANIFEST, ROADMAP, and one spec

        if len(docs) < MIN_DOCS:
            pytest.fail(
                f"Too few roadmap docs: {len(docs)} (minimum: {MIN_DOCS})\n"
                f"Expected at least: MANIFEST.md, ROADMAP.md, and one spec"
            )

    def test_required_docs_exist(self):
        """Required roadmap docs must exist."""
        required = ["MANIFEST.md", "L4ExecutionContract.v1.md", "L4ExecutionContract.v2.md"]
        missing = []

        for doc_name in required:
            if not (ROADMAP_FOLDER / doc_name).exists():
                missing.append(doc_name)

        if not ROOT_ROADMAP.exists():
            missing.append("../ROADMAP.md")

        if missing:
            msg = "\nRequired roadmap docs missing:\n"
            for doc in missing:
                if doc == "../ROADMAP.md":
                    msg += "  - ROADMAP.md\n"
                else:
                    msg += f"  - roadmap/{doc}\n"
            pytest.fail(msg)


class TestL4ExecutionContractDoc:
    """L4ExecutionContract v1 (superseded) and v2 (current) must exist."""

    L4_CONTRACT_V1_PATH = ROADMAP_FOLDER / "L4ExecutionContract.v1.md"
    L4_CONTRACT_V2_PATH = ROADMAP_FOLDER / "L4ExecutionContract.v2.md"

    def test_l4_contract_v1_exists(self):
        """L4ExecutionContract.v1.md must exist (historical reference)."""
        assert self.L4_CONTRACT_V1_PATH.exists(), (
            "roadmap/L4ExecutionContract.v1.md missing — required for historical reference."
        )

    def test_l4_contract_v1_marked_superseded(self):
        """L4ExecutionContract.v1.md must be marked as superseded."""
        text = self.L4_CONTRACT_V1_PATH.read_text(encoding="utf-8")
        assert "SUPERSEDED" in text, (
            "L4ExecutionContract.v1.md must be marked SUPERSEDED."
        )

    def test_l4_contract_v2_exists(self):
        """L4ExecutionContract.v2.md must exist (current policy)."""
        assert self.L4_CONTRACT_V2_PATH.exists(), (
            "roadmap/L4ExecutionContract.v2.md missing — required for 3-class wave classification."
        )

    def test_l4_contract_v2_has_three_wave_classes(self):
        """L4ExecutionContract.v2.md must define all 3 wave classes."""
        text = self.L4_CONTRACT_V2_PATH.read_text(encoding="utf-8")
        assert "L4_STRUCTURAL" in text, "Missing L4_STRUCTURAL wave class definition."
        assert "L4_ENABLER" in text, "Missing L4_ENABLER wave class definition."
        assert "MAINTENANCE" in text, "Missing MAINTENANCE wave class definition."

    def test_l4_contract_v2_has_enforcement_reference(self):
        """L4ExecutionContract.v2.md must reference the enforcement checker."""
        text = self.L4_CONTRACT_V2_PATH.read_text(encoding="utf-8")
        assert "enforce_l4_execution_contract.py" in text, (
            "L4ExecutionContract.v2.md must reference enforcement checker."
        )

    def test_l4_contract_v2_references_status_and_tasks(self):
        """L4ExecutionContract.v2.md must reference STATUS.md and TASKS.md."""
        text = self.L4_CONTRACT_V2_PATH.read_text(encoding="utf-8")
        assert "STATUS.md" in text, "Must reference STATUS.md."
        assert "TASKS.md" in text, "Must reference TASKS.md."


class TestCodexClaudeAuditContractDoc:
    """CodexClaudeAuditContract.v1.md must exist with required content."""

    AUDIT_CONTRACT_PATH = ROADMAP_FOLDER / "CodexClaudeAuditContract.v1.md"

    def test_audit_contract_doc_exists(self):
        """CodexClaudeAuditContract.v1.md must exist in roadmap/."""
        assert self.AUDIT_CONTRACT_PATH.exists(), (
            "roadmap/CodexClaudeAuditContract.v1.md missing — required for audit discipline."
        )

    def test_audit_contract_references_status_and_tasks(self):
        """CodexClaudeAuditContract.v1.md must reference STATUS.md and TASKS.md."""
        text = self.AUDIT_CONTRACT_PATH.read_text(encoding="utf-8")
        assert re.search(r'\[`?STATUS\.md`?\]', text), "Must reference STATUS.md."
        assert re.search(r'\[`?TASKS\.md`?\]', text), "Must reference TASKS.md."

    def test_audit_contract_has_anti_theater_clauses(self):
        """Must include anti-theater clauses."""
        text = self.AUDIT_CONTRACT_PATH.read_text(encoding="utf-8")
        assert "Anti-Theater" in text, "Must have anti-theater section."

    def test_audit_contract_has_preflight_docs(self):
        """Must include preflight docs read order."""
        text = self.AUDIT_CONTRACT_PATH.read_text(encoding="utf-8")
        assert "Preflight" in text, "Must reference preflight docs."


class TestManifestContractDiscoverability:
    """MANIFEST.md must include all contract docs for discoverability."""

    def test_manifest_includes_l4_execution_contract_v1(self):
        """MANIFEST.md must reference L4ExecutionContract.v1.md (superseded)."""
        manifest = (ROADMAP_FOLDER / "MANIFEST.md").read_text(encoding="utf-8")
        assert "L4ExecutionContract.v1.md" in manifest, (
            "MANIFEST.md must include L4ExecutionContract.v1.md for discoverability."
        )

    def test_manifest_includes_l4_execution_contract_v2(self):
        """MANIFEST.md must reference L4ExecutionContract.v2.md (current)."""
        manifest = (ROADMAP_FOLDER / "MANIFEST.md").read_text(encoding="utf-8")
        assert "L4ExecutionContract.v2.md" in manifest, (
            "MANIFEST.md must include L4ExecutionContract.v2.md for discoverability."
        )

    def test_manifest_includes_codex_claude_audit_contract(self):
        """MANIFEST.md must reference CodexClaudeAuditContract.v1.md."""
        manifest = (ROADMAP_FOLDER / "MANIFEST.md").read_text(encoding="utf-8")
        assert "CodexClaudeAuditContract.v1.md" in manifest, (
            "MANIFEST.md must include CodexClaudeAuditContract.v1.md for discoverability."
        )

    def test_manifest_includes_north_star_semantics(self):
        """MANIFEST.md must reference NorthStarSemantics.v0.md."""
        manifest = (ROADMAP_FOLDER / "MANIFEST.md").read_text(encoding="utf-8")
        assert "NorthStarSemantics.v0.md" in manifest, (
            "MANIFEST.md must include NorthStarSemantics.v0.md for discoverability."
        )


class TestNorthStarSemanticsLock:
    """NorthStarSemantics.v0.md must exist and be referenced in governance chain."""

    DOCS_CORE = REPO_ROOT / "mu" / "docs" / "core"

    def test_north_star_semantics_exists(self):
        """NorthStarSemantics.v0.md must exist in mu/docs/core/."""
        path = self.DOCS_CORE / "NorthStarSemantics.v0.md"
        assert path.exists(), "NorthStarSemantics.v0.md must exist"

    def test_status_references_semantics_lock(self):
        """STATUS.md must reference NorthStarSemantics.v0.md."""
        status = (REPO_ROOT / "STATUS.md").read_text(encoding="utf-8")
        assert "NorthStarSemantics.v0.md" in status, (
            "STATUS.md must reference NorthStarSemantics.v0.md"
        )

    def test_claude_md_references_semantics_lock(self):
        """CLAUDE.md must reference NorthStarSemantics.v0.md."""
        claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "NorthStarSemantics.v0.md" in claude, (
            "CLAUDE.md must reference NorthStarSemantics.v0.md"
        )

    def test_bootstrap_bridge_has_normative_pointer(self):
        """BootstrapStructuralBridge.v0.md must point to NorthStarSemantics as normative."""
        bridge = (self.DOCS_CORE / "BootstrapStructuralBridge.v0.md").read_text(encoding="utf-8")
        assert "NorthStarSemantics.v0.md" in bridge, (
            "BootstrapStructuralBridge.v0.md must reference NorthStarSemantics.v0.md"
        )
        assert "normative" in bridge.lower(), (
            "BootstrapStructuralBridge.v0.md must identify NorthStarSemantics as normative"
        )

    def test_semantics_lock_covers_required_policies(self):
        """NorthStarSemantics.v0.md must cover all required policy sections."""
        content = (self.DOCS_CORE / "NorthStarSemantics.v0.md").read_text(encoding="utf-8")
        for section in [
            "Undefined-as-Structure",
            "Zero Canonicalization",
            "Bounded Non-Closure",
            "Routing Tie-Break",
            "Boot0/Hex0",
        ]:
            assert section in content, (
                f"NorthStarSemantics.v0.md must contain '{section}' section"
            )
