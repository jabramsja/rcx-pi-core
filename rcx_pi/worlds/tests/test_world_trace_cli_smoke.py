import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def run(args):
    # Run as a module so rcx_pi imports always resolve correctly.
    return subprocess.run(
        [sys.executable, "-m", "rcx_pi.worlds.world_trace_cli", *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

def test_world_trace_cli_help_smoke():
    r = run(["--help"])
    assert r.returncode == 0
    joined = (r.stdout + "\n" + r.stderr).lower()

    # Smoke expectations: we got help text and it includes key flags.
    assert "usage:" in joined
    assert "world_trace_cli" in joined
    for flag in ("--max-steps", "--json", "--pretty", "--raw"):
        assert flag in joined

def test_world_trace_cli_rejects_obviously_bad_input():
    r = run(["trace", "--file", "definitely-not-a-real-file.mu"])
    assert r.returncode != 0
    joined = (r.stdout + "\n" + r.stderr).lower()
    assert ("error" in joined) or ("no such file" in joined) or ("not found" in joined)
