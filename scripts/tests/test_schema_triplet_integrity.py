from __future__ import annotations

import subprocess
from pathlib import Path


def _run_schema(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = r.stdout.strip()
    assert out, f"no output from: {' '.join(cmd)}"
    return out


def _parse_triplet(line: str) -> tuple[str, str, str]:
    parts = line.split()
    assert len(parts) == 3, (
        f"expected 3-part schema triplet, got {len(parts)}: {line!r}"
    )
    return parts[0], parts[1], parts[2]


def test_schema_triplets_point_to_real_files():
    repo = Path(__file__).resolve().parents[2]

    checks = [
        (
            ["python3", str(repo / "rcx_pi" / "program_descriptor_cli.py"), "--schema"],
            "rcx-program-descriptor.v1",
        ),
        (
            ["python3", str(repo / "rcx_pi" / "program_run_cli.py"), "--schema"],
            "rcx-program-run.v1",
        ),
        (
            [
                "python3",
                str(repo / "scripts" / "snapshot_merge.py"),
                "--schema",
                "A",
                "B",
                "--out",
                "OUT.json",
            ],
            "rcx.snapshot.v1",
        ),
    ]

    for cmd, expected_tag in checks:
        tag, doc_md, schema_json = _parse_triplet(_run_schema(cmd))
        assert tag == expected_tag

        doc_path = repo / doc_md
        schema_path = repo / schema_json

        assert doc_path.exists(), f"missing schema doc: {doc_md}"
        assert schema_path.exists(), f"missing schema json: {schema_json}"


def test_schema_doc_consts_are_valid_when_present():
    repo = Path(__file__).resolve().parents[2]
    docs = repo / "docs"
    assert docs.is_dir()

    # Any schema json that declares a schema_doc const must point to an existing docs/*.md file.
    for p in (docs / "schemas").rglob("*.json"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        needle = '"schema_doc"'
        if needle not in txt:
            continue
        # lightweight parse: look for '"const": "docs/....md"' near schema_doc
        if '"const"' not in txt:
            continue
        # Only enforce if a docs/*.md string is present at all
        if "docs/" not in txt or ".md" not in txt:
            continue

        # crude but reliable for our format: find all docs/*.md substrings
        import re

        for md in re.findall(r"docs/[A-Za-z0-9_\-\.]+\.md", txt):
            assert (repo / md).exists(), (
                f"{p}: schema_doc const points to missing file: {md}"
            )
