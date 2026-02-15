from __future__ import annotations

import json
from pathlib import Path
from subprocess import run, PIPE

import jsonschema


def _run(args, cwd: Path):
    return run(
        ["python3", "-m", "rcx_pi.program_run_cli", *args],
        cwd=str(cwd),
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )


def test_program_run_jsonschema_smoke():
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "docs" / "schemas" / "program_run_schema.json"
    assert schema_path.exists(), f"missing schema: {schema_path}"
    schema = json.loads(schema_path.read_text())

    r = _run(["succ-list", "[1,2,3]"], repo_root)
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"

    data = json.loads(r.stdout)
    jsonschema.validate(instance=data, schema=schema)
