"""
Manifest Discoverability Ratchet — fail-closed enforcement.

Ensures every active core specification (DOC_STATUS TYPE: DESIGN_SPEC or
IMPLEMENTATION) in mu/docs/core/ is listed in roadmap/MANIFEST.md, and that
every mu/docs/core/ link in MANIFEST resolves to an existing file.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_manifest_discoverability.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

MANIFEST_PATH = REPO_ROOT / "roadmap" / "MANIFEST.md"
CORE_DOCS_DIR = REPO_ROOT / "mu" / "docs" / "core"

ACTIVE_TYPES = frozenset({"DESIGN_SPEC", "IMPLEMENTATION"})

# Regex to extract DOC_STATUS TYPE from doc headers
DOC_STATUS_TYPE_RE = re.compile(r"^TYPE:\s*(\S+)", re.MULTILINE)

# Regex to find mu/docs/core/ references in MANIFEST
CORE_LINK_RE = re.compile(r"mu/docs/core/[A-Za-z0-9_.]+\.md")


def _extract_doc_status_type(path: Path) -> str | None:
    """Extract the DOC_STATUS TYPE value from a markdown file's header."""
    text = path.read_text(encoding="utf-8")
    match = DOC_STATUS_TYPE_RE.search(text)
    return match.group(1) if match else None


class TestManifestDiscoverability:
    """Fail-closed: active core specs must be discoverable in MANIFEST.md."""

    def test_manifest_includes_active_core_specs(self):
        """Every DESIGN_SPEC and IMPLEMENTATION doc must appear in MANIFEST.md."""
        assert MANIFEST_PATH.exists(), "roadmap/MANIFEST.md missing"
        assert CORE_DOCS_DIR.exists(), "mu/docs/core/ missing"

        manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

        missing: list[str] = []
        for doc_path in sorted(CORE_DOCS_DIR.glob("*.md")):
            doc_type = _extract_doc_status_type(doc_path)
            if doc_type not in ACTIVE_TYPES:
                continue
            # Check if the filename appears in MANIFEST
            if doc_path.name not in manifest_text:
                missing.append(f"  {doc_path.name} (TYPE: {doc_type})")

        if missing:
            msg = (
                "\nActive core specs missing from roadmap/MANIFEST.md:\n"
                + "\n".join(missing)
                + "\n\nFix: Add these docs to MANIFEST.md so they are discoverable.\n"
                "Active = DOC_STATUS TYPE: DESIGN_SPEC or IMPLEMENTATION.\n"
            )
            pytest.fail(msg)

    def test_manifest_core_links_resolve(self):
        """Every mu/docs/core/ link in MANIFEST must resolve to an existing file."""
        assert MANIFEST_PATH.exists(), "roadmap/MANIFEST.md missing"

        manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
        links = sorted(set(CORE_LINK_RE.findall(manifest_text)))

        broken: list[str] = []
        for link in links:
            full_path = REPO_ROOT / link
            if not full_path.exists():
                broken.append(f"  {link}")

        if broken:
            msg = (
                "\nBroken mu/docs/core/ links in MANIFEST.md:\n"
                + "\n".join(broken)
                + "\n\nFix: Remove or update these links.\n"
            )
            pytest.fail(msg)
