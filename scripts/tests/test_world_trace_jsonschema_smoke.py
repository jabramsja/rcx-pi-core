from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("check-jsonschema") is None,
    reason="check-jsonschema not installed; schema smoke test is optional",
)
def test_world_trace_output_validates_against_jsonschema():
    repo_root = Path(__file__).resolve().parents[2]
    cli = repo_root / "rcx_pi" / "worlds" / "world_trace_cli.py"
    schema = repo_root / "docs" / "world_trace_json_schema.json"

    assert cli.exists(), f"missing: {cli}"
    assert schema.exists(), f"missing: {schema}"

    # Generate one canonical sample deterministically.
    r = subprocess.run(
        ["python3", str(cli), "rcx_core", "ping", "--json"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + "\n" + r.stderr

    # Ensure it's valid JSON (sanity)
    data = json.loads(r.stdout)
    assert isinstance(data, dict)

    # Validate via CLI tool.
    v = subprocess.run(
        ["check-jsonschema", "-", "--schemafile", str(schema)],
        cwd=str(repo_root),
        input=r.stdout,
        capture_output=True,
        text=True,
    )
    assert v.returncode == 0, v.stdout + "\n" + v.stderr
