from __future__ import annotations

import subprocess

from rcx_pi.cli_schema import parse_schema_triplet


def _py(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip() != ""]
    assert len(lines) == 1, (
        f"expected exactly 1 non-empty stdout line, got {len(lines)}: {lines!r}"
    )
    return lines[0]


def test_python_entrypoints_schema_triplets_are_parseable():
    lines = [
        _py(["python3", "rcx_pi/program_descriptor_cli.py", "--schema"]),
        _py(["python3", "rcx_pi/program_run_cli.py", "--schema"]),
        _py(["python3", "-m", "rcx_pi.worlds.world_trace_cli", "--schema"]),
        _py(
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
    for line in lines:
        trip = parse_schema_triplet(line)
        assert trip.tag.endswith(".v1")
        assert trip.doc_md.startswith("docs/") and trip.doc_md.endswith(".md")
        assert trip.schema_json.startswith(
            "docs/schemas/"
        ) and trip.schema_json.endswith(".json")
