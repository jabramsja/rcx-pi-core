from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = r.stdout.strip()
    assert out, f"no output from: {' '.join(cmd)}\nSTDERR:\n{r.stderr}"
    return out


def _parse_triplet(line: str) -> tuple[str, str, str]:
    parts = line.split()
    assert len(parts) == 3, (
        f"expected 3-part schema triplet, got {len(parts)}: {line!r}"
    )
    return parts[0], parts[1], parts[2]


def test_rcx_umbrella_cli_schema_triplets_point_to_real_files():
    repo = Path(__file__).resolve().parents[2]

    checks = [
        (
            ["python3", "-m", "rcx_pi.rcx_cli", "program", "describe", "--schema"],
            "rcx-program-descriptor.v1",
        ),
        (
            ["python3", "-m", "rcx_pi.rcx_cli", "program", "run", "--schema"],
            "rcx-program-run.v1",
        ),
        (
            ["python3", "-m", "rcx_pi.rcx_cli", "world", "trace", "--schema"],
            "rcx-world-trace.v1",
        ),
    ]

    for cmd, expected_tag in checks:
        tag, doc_md, schema_json = _parse_triplet(_run(cmd))
        assert tag == expected_tag

        doc_path = repo / doc_md
        schema_path = repo / schema_json

        assert doc_path.exists(), f"missing schema doc: {doc_md}"
        assert schema_path.exists(), f"missing schema json: {schema_json}"
