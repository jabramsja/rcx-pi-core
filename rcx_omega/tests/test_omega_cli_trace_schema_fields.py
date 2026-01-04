import json
import os
import re
import subprocess
import sys


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _run_omega_trace(env: dict | None = None) -> dict:
    """
    Runs omega_cli in trace mode, returns parsed JSON.
    We intentionally treat JSON shape as contract-level only:
    - Must be JSON
    - Trace-shaped should include `steps` (list-like)
    We do NOT assume internal step fields.
    """
    cmd = [sys.executable, "-m", "rcx_omega.cli.omega_cli", "--trace", "--json", "μ(μ())"]
    p = subprocess.run(
        cmd,
        input=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=True,
    )
    # If anything leaks to stderr, keep it visible in failures.
    if p.stderr.strip():
        raise AssertionError(f"omega_cli wrote to stderr:\n{p.stderr}")

    out = p.stdout.strip()
    if not out:
        raise AssertionError("omega_cli produced empty stdout")

    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout was not valid JSON: {e}\nstdout:\n{out}") from e


def test_trace_env_off_does_not_inject_schema_fields():
    env = os.environ.copy()
    env.pop("RCX_OMEGA_ADD_SCHEMA_FIELDS", None)

    obj = _run_omega_trace(env=env)

    # Trace-shaped contract: must have steps (do not assume step fields)
    assert "steps" in obj, "trace-shaped JSON must include steps[]"
    assert isinstance(obj["steps"], list), "steps must be a list"

    # Env OFF: do not inject schema metadata
    assert "schema_version" not in obj, "schema_version must not appear when env is OFF"


def test_trace_env_on_injects_schema_version():
    env = os.environ.copy()
    env["RCX_OMEGA_ADD_SCHEMA_FIELDS"] = "1"

    obj = _run_omega_trace(env=env)

    assert "steps" in obj, "trace-shaped JSON must include steps[]"
    assert isinstance(obj["steps"], list), "steps must be a list"

    # Env ON: schema_version must appear (value may evolve, keep semver-shaped)
    assert "schema_version" in obj, "schema_version must appear when env is ON"
    sv = obj["schema_version"]
    assert isinstance(sv, str), "schema_version must be a string"
    assert SEMVER_RE.match(sv), f"schema_version must look like semver (x.y.z), got: {sv!r}"
