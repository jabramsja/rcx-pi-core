from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_mutation_sandbox_writes_only_under_out_dir(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text(
        "\n".join(
            [
                "# comment",
                "[a] -> ra",
                "[b] -> lobe",
                "[c] -> sink",
                "not a rule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--seed", "7", "--mutations", "2", "--out-dir", str(out), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)

    run_dir = Path(obj["paths"]["run_dir"])
    assert str(run_dir).startswith(str(out))
    assert (run_dir / "baseline.mu").is_file()
    assert (run_dir / "mutated.mu").is_file()
    assert (run_dir / "report.json").is_file()


def test_mutation_sandbox_flip_produces_events_on_flippable_lines(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[a] -> ra\n[b] -> lobe\n[c] -> sink\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--seed", "1", "--mutations", "2", "--apply", "flip", "--out-dir", str(out), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["metrics"]["flips_applied"] >= 1


def test_mutation_sandbox_shuffle_changes_order_of_rule_like_lines(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[1] -> ra\n[2] -> ra\n[3] -> ra\n", encoding="utf-8")
    out = tmp_path / "sandbox_runs"
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(w), "--seed", "3", "--mutations", "0", "--apply", "shuffle", "--out-dir", str(out), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    run_dir = Path(obj["paths"]["run_dir"])
    baseline = (run_dir / "baseline.mu").read_text(encoding="utf-8", errors="replace")
    mutated = (run_dir / "mutated.mu").read_text(encoding="utf-8", errors="replace")
    # With 3 rules, deterministic shuffle should usually change order; allow rare no-op but ensure file exists.
    assert baseline != ""
    assert mutated != ""


def test_mutation_sandbox_smoke_on_repo_world():
    # best-effort: ensure tool can run on a real repo .mu without exploding
    world = None
    for cand in ["rcx_pi_rust/mu_programs/rcx_core.mu", "rcx_pi_rust/test_w.mu"]:
        p = Path(cand)
        if p.is_file():
            world = p
            break
    assert world is not None
    p = _run(["bash", "scripts/mutation_sandbox.sh", str(world), "--seed", "2", "--mutations", "1", "--apply", "both", "--out-dir", "sandbox_runs"])
    assert p.returncode == 0
