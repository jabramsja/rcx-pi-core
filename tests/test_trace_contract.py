import json
import subprocess
import sys


def _run(cmd, stdin: str | None = None) -> str:
    p = subprocess.run(
        cmd,
        input=stdin,
        check=True,
        capture_output=True,
        text=True,
    )
    return p.stdout.strip() + "\n"


def _run_omega_json(expr: str) -> str:
    return _run([sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", expr])


def _run_trace_json(expr: str) -> str:
    """
    Prefer trace_cli if available. If not, try omega_cli --trace.
    Return raw JSON stdout.
    """
    # 1) trace_cli path (module exists in tree)
    try:
        return _run([sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", expr])
    except subprocess.CalledProcessError as e:
        # 2) fallback: omega_cli --trace (some repos use this)
        try:
            return _run(
                [
                    sys.executable,
                    "-m",
                    "rcx_omega.cli.omega_cli",
                    "--trace",
                    "--json",
                    expr,
                ]
            )
        except subprocess.CalledProcessError:
            # raise the original error but include stderr for visibility
            raise AssertionError(
                "Could not obtain trace JSON via trace_cli or omega_cli --trace.\n"
                f"trace_cli stderr:\n{e.stderr}"
            ) from e


def test_trace_json_has_stable_top_level_contract():
    expr = "μ(μ())"

    # Ensure omega itself works (and gives result)
    omega_raw = _run_omega_json(expr)
    omega = json.loads(omega_raw)
    assert "result" in omega

    trace_raw = _run_trace_json(expr)
    trace = json.loads(trace_raw)

    # We want some stable top-level markers.
    # Different RCX revisions may name these slightly differently; accept any of these.
    candidate_keys = {
        "schema_version",
        "schema",
        "version",
        "trace",
        "steps",
        "events",
        "summary",
        "result",
        "input",
        "expr",
    }

    present = candidate_keys.intersection(trace.keys())
    assert present, (
        f"Trace JSON missing expected top-level markers. Keys={sorted(trace.keys())}"
    )
