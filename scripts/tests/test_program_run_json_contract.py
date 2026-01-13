from __future__ import annotations

import json
from pathlib import Path
from subprocess import run, PIPE


def _run(args, cwd: Path):
    return run(
        ["python3", "-m", "rcx_pi.program_run_cli", *args],
        cwd=str(cwd),
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )


def test_program_run_json_contract():
    repo_root = Path(__file__).resolve().parents[2]

    # succ-list is guaranteed by rcx_pi.program_registry._ensure_defaults()
    program = "succ-list"
    inp = "[1,2,3]"

    r = _run([program, inp], repo_root)
    assert r.returncode == 0, f"stderr:\n{r.stderr}\nstdout:\n{r.stdout}"
    assert r.stdout.strip(), "expected json on stdout"

    data = json.loads(r.stdout)

    required = {"schema", "schema_doc", "program", "input", "output", "ok"}
    missing = required - set(data.keys())
    assert not missing, f"missing keys: {sorted(missing)}; got keys={sorted(data.keys())}"

    assert data["schema"] == "rcx-program-run.v1"
    assert data["program"] == program
    assert data["input"] == [1, 2, 3]
    assert isinstance(data["output"], list)
    assert all(isinstance(x, int) for x in data["output"])
    assert data["ok"] is True
