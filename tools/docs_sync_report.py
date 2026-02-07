#!/usr/bin/env python3
"""
Docs sync report and fail-closed checker.

Checks:
1. Every markdown file is classified by docs registry.
2. Every docs/<subfolder>/ containing markdown is registered.
3. Tracker-only section headers (NOW/NEXT/VECTOR/SINK) appear only in root canonical docs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Ensure repo root is at position 0 for imports
_repo_root = str(Path(__file__).resolve().parents[1])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from tools.shared_doc_config import (
    REPO_ROOT,
    classify_md_path,
    get_registered_docs_subfolders,
)


TRACKER_SECTION_PATTERN = re.compile(r"^##\s*(NOW|NEXT|VECTOR|SINK)\b", re.MULTILINE)


def collect_report() -> dict:
    report: dict = {
        "unclassified_markdown": [],
        "unregistered_docs_subfolders": [],
        "tracker_section_violations": [],
    }

    markdown_files = sorted(REPO_ROOT.rglob("*.md"))

    for md_file in markdown_files:
        rel = str(md_file.relative_to(REPO_ROOT))
        classification = classify_md_path(md_file)
        if classification == "unknown":
            report["unclassified_markdown"].append(rel)

        content = md_file.read_text(encoding="utf-8")
        match = TRACKER_SECTION_PATTERN.search(content)
        if match and classification != "root_canonical":
            report["tracker_section_violations"].append(
                {"path": rel, "section": match.group(1)}
            )

    docs_root = REPO_ROOT / "docs"
    discovered: set[str] = set()
    for md_file in docs_root.rglob("*.md"):
        rel = md_file.relative_to(docs_root)
        if len(rel.parts) >= 2:
            discovered.add(rel.parts[0])

    registered = get_registered_docs_subfolders()
    report["unregistered_docs_subfolders"] = sorted(discovered - registered)

    return report


def print_report(report: dict) -> None:
    print("=== Docs Sync Report ===")

    unclassified = report["unclassified_markdown"]
    unregistered = report["unregistered_docs_subfolders"]
    placement = report["tracker_section_violations"]

    print(f"Unclassified markdown files: {len(unclassified)}")
    for path in unclassified[:20]:
        print(f"  - {path}")
    if len(unclassified) > 20:
        print(f"  ... and {len(unclassified) - 20} more")

    print(f"Unregistered docs subfolders: {len(unregistered)}")
    for folder in unregistered:
        print(f"  - docs/{folder}/")

    print(f"Tracker section placement violations: {len(placement)}")
    for item in placement[:20]:
        print(f"  - {item['path']}: ## {item['section']}")
    if len(placement) > 20:
        print(f"  ... and {len(placement) - 20} more")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs sync and governance coverage.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero on violations")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    args = parser.parse_args()

    report = collect_report()
    violations = (
        len(report["unclassified_markdown"])
        + len(report["unregistered_docs_subfolders"])
        + len(report["tracker_section_violations"])
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)

    if args.check and violations > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
