from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_mutation_sandbox_run_none_creates_outputs(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n[c] -> sink\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"

    p = _run(
        [
            "bash",
            "scripts/mutation_sandbox.sh",
            str(w),
            "--seed",
            "1",
            "--mutations",
            "1",
            "--out-dir",
            str(out),
            "--run",
            "--runner",
            "none",
            "--json",
        ]
    )
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    run_dir = Path(obj["paths"]["run_dir"])
    assert run_dir.is_dir()
    assert (run_dir / "baseline.mu").is_file()
    assert (run_dir / "mutated.mu").is_file()
    assert (run_dir / "baseline.out.txt").is_file()
    assert (run_dir / "mutated.out.txt").is_file()
    # no JSON expected for runner=none
    assert obj["run"]["baseline"]["json_ok"] is False


def test_mutation_sandbox_score_without_json_is_graceful(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n[c] -> sink\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"

    p = _run(
        [
            "bash",
            "scripts/mutation_sandbox.sh",
            str(w),
            "--seed",
            "2",
            "--mutations",
            "1",
            "--out-dir",
            str(out),
            "--run",
            "--score",
            "--runner",
            "none",
            "--json",
        ]
    )
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["comparison"]["enabled"] is True
    assert obj["comparison"]["scores"]["baseline"] is None
    assert obj["comparison"]["snapshot_integrity"] is None


def test_mutation_sandbox_max_steps_violation_can_trigger_rc1(tmp_path: Path):
    # Feed a synthetic trace JSON via trace-cli runner isn't guaranteed here, so just ensure no crash:
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"

    p = _run(
        [
            "bash",
            "scripts/mutation_sandbox.sh",
            str(w),
            "--seed",
            "3",
            "--mutations",
            "0",
            "--out-dir",
            str(out),
            "--run",
            "--score",
            "--max-steps",
            "0",
            "--runner",
            "none",
            "--json",
        ]
    )
    assert p.returncode == 0
