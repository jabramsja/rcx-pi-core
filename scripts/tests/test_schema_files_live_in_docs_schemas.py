from __future__ import annotations

from pathlib import Path


def test_schema_files_live_in_docs_schemas():
    """
    Repo rule:
      - JSON schema artifacts must live under docs/schemas/
      - docs/ root should not accumulate *schema*.json files (keeps docs tidy + predictable)
    """
    root = Path(__file__).resolve().parents[2]
    docs = root / "docs"
    schemas = docs / "schemas"

    assert schemas.is_dir(), "docs/schemas must exist"

    # Allow-list: files under docs/schemas are fine.
    # Disallow: any JSON schema-looking files directly under docs/ root.
    bad = sorted(p.name for p in docs.glob("*.json") if "schema" in p.name.lower())

    assert bad == [], (
        f"Schema JSON files must live in docs/schemas/, found in docs/: {bad}"
    )
