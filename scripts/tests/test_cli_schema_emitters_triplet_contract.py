from __future__ import annotations

import re
import subprocess
from rcx_pi.cli_schema_run import parse_schema_triplet_stdout, run_schema_triplet


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = r.stdout

    # Hard contract: exactly ONE non-empty stdout line.
    assert out.endswith("\n") or out == "", f"stdout should end with newline: {out!r}"
    lines = [ln for ln in out.splitlines() if ln.strip() != ""]
    assert len(lines) == 1, (
        f"expected exactly 1 non-empty stdout line, got {len(lines)}: {lines!r}"
    )
    return lines[0]


_TRIPLET_RE = re.compile(r"^[^\s]+\s+[^\s]+\s+[^\s]+$")


def _assert_triplet(s: str) -> None:
    assert _TRIPLET_RE.fullmatch(s), (
        f"expected 3 space-delimited fields (no extra whitespace): {s!r}"
    )
    parts = s.split(" ")
    assert len(parts) == 3, f"expected exactly 3 fields, got {len(parts)}: {s!r}"

    tag, doc, schema = parts

    # Tag sanity
    assert "." in tag, f"tag should look versioned (contain '.'): {tag!r}"

    # Doc path conventions
    assert doc.startswith("docs/"), f"doc path should be under docs/: {doc!r}"
    assert doc.endswith(".md"), f"doc path should be a markdown file: {doc!r}"

    # Schema path conventions
    assert schema.startswith("docs/schemas/"), (
        f"schema path should be under docs/schemas/: {schema!r}"
    )
    assert schema.endswith(".json"), f"schema path should be a json file: {schema!r}"


def test_schema_emitters_are_strict_triplets():
    outs = [
        _run(["python3", "rcx_pi/program_descriptor_cli.py", "--schema"]),
        _run(["python3", "rcx_pi/program_run_cli.py", "--schema"]),
        _run(["python3", "-m", "rcx_pi.worlds.world_trace_cli", "--schema"]),
        _run(
            [
                "python3",
                "scripts/snapshot_merge.py",
                "--schema",
                "A",
                "B",
                "--out",
                "OUT.json",
            ]
        ),
    ]
    for o in outs:
        _assert_triplet(o)
