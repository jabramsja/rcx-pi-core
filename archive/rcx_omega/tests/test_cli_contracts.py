import json
import subprocess
import sys


def _run(cmd, *, input_text=None):
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )


def test_contract_trace_to_analyze_has_header_and_converged():
    # trace -> analyze should work and include stable markers
    trace = _run([sys.executable, "-m", "rcx_omega.cli.trace_cli", "--json", "void"])
    obj = json.loads(trace.stdout)
    assert "steps" in obj and isinstance(obj["steps"], list)

    analyzed = _run(
        [sys.executable, "-m", "rcx_omega.cli.analyze_cli"], input_text=trace.stdout
    )

    assert "== Ω analyze ==" in analyzed.stdout
    assert "analyze: trace" in analyzed.stdout
    # this is the key UX/contract line for trace payloads
    assert "converged:" in analyzed.stdout


def test_contract_omega_to_analyze_has_header_and_summary():
    # omega -> analyze should work and include stable markers
    omega = _run([sys.executable, "-m", "rcx_omega.cli.omega_cli", "--json", "μ(μ())"])
    obj = json.loads(omega.stdout)
    assert "result" in obj

    analyzed = _run(
        [sys.executable, "-m", "rcx_omega.cli.analyze_cli"], input_text=omega.stdout
    )

    assert "== Ω analyze ==" in analyzed.stdout
    assert "analyze: summary" in analyzed.stdout
    # stable summary line (either classification or at minimum "classification:" line)
    assert "classification:" in analyzed.stdout
