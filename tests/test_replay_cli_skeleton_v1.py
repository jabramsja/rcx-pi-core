from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-m", "rcx_pi.rcx_cli", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def test_replay_cli_ok_on_minimal_fixture(tmp_path: Path):
    trace = ROOT / "tests" / "fixtures" / "traces" / "minimal.v1.jsonl"
    out = tmp_path / "canon.jsonl"
    r = _run(["replay", "--trace", str(trace), "--out", str(out)])
    assert r.returncode == 0, r.stdout + "\n" + r.stderr
    assert out.exists()
    # should write something non-empty
    assert out.read_text(encoding="utf-8").strip() != ""


def test_replay_cli_check_canon_fails_if_input_not_canonical(tmp_path: Path):
    # Create a non-canonical trace: keys permuted and extra whitespace
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"type":"trace.start","i":0,"v":1}\n', encoding="utf-8")
    # Our canon format is compact with stable key order: {"v":1,"type":"...","i":0}\n
    r = _run(["replay", "--trace", str(bad), "--check-canon"])
    assert r.returncode == 1, r.stdout + "\n" + r.stderr
    assert "REPLAY_MISMATCH" in (r.stderr + r.stdout)


def test_replay_cli_expect_mismatch_is_nonzero(tmp_path: Path):
    trace = ROOT / "tests" / "fixtures" / "traces" / "minimal.v1.jsonl"
    exp = tmp_path / "expected.jsonl"
    exp.write_text("not-the-right-content\n", encoding="utf-8")
    r = _run(["replay", "--trace", str(trace), "--expect", str(exp)])
    assert r.returncode == 1, r.stdout + "\n" + r.stderr
    assert "REPLAY_MISMATCH" in (r.stderr + r.stdout)
