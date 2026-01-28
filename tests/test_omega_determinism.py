import json
import os
import subprocess
import sys


def _run_omega(expr: str) -> str:
    """
    Run omega_cli in JSON mode and return raw stdout.
    We keep this test strict: same input should yield identical bytes across runs.
    """
    p = subprocess.run(
        [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", expr],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    # normalize trailing whitespace only (avoid false diffs from newline)
    return p.stdout.strip() + "\n"


def test_omega_json_is_deterministic_for_canonical_expression():
    expr = "μ(μ())"
    a = _run_omega(expr)
    b = _run_omega(expr)

    # Must be byte-stable (within same env/commit)
    assert a == b

    # Must be valid JSON with expected stable marker(s)
    obj = json.loads(a)
    assert "result" in obj
