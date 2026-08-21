from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import candidate_authority as ca  # noqa: E402


WAVE_ID = "candidate-authority-test-2026-08-21"
INDICATOR = f"reports/l4_wave_indicators/{WAVE_ID}.json"
INDICATOR_COMMAND = (
    "python3 tools/metrics/collect_l4_wave_indicators.py "
    f"--wave-id {WAVE_ID} --output {INDICATOR}"
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tools" / "metrics").mkdir(parents=True)
    (repo / "reports" / "control_plane").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "TASKS.md").write_text("# TASKS\n", encoding="utf-8")
    (repo / "reports" / "control_plane" / "plan.md").write_text(
        f"Wave ID: {WAVE_ID}\nFOUNDER_OVERRIDE:{WAVE_ID}\n",
        encoding="utf-8",
    )
    (repo / "src" / "keep.txt").write_text("base\n", encoding="utf-8")
    (repo / "src" / "delete.txt").write_text("delete me\n", encoding="utf-8")
    (repo / "tools" / "metrics" / "collect_l4_wave_indicators.py").write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser(); p.add_argument('--wave-id', required=True); "
        "p.add_argument('--output', required=True); a=p.parse_args()\n"
        "out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text(json.dumps({'wave_id': a.wave_id, 'static': True}, sort_keys=True)+'\\n')\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _spec(base: str, allowlist: list[str], *, review_round: str = "r1") -> ca.CandidateAuthoritySpec:
    return ca.CandidateAuthoritySpec.from_mapping(
        {
            "wave_id": WAVE_ID,
            "comparison_commit": base,
            "candidate_allowlist": allowlist,
            "plan_path": "reports/control_plane/plan.md",
            "phase": "phase_b",
            "review_round": review_round,
            "indicator_artifact_ref": INDICATOR,
            "indicator_collection_command": INDICATOR_COMMAND,
            "wave_class": "L4_ENABLER",
            "require_l4_staged": True,
        }
    )


def _default_allowlist() -> list[str]:
    return [
        "TASKS.md",
        "reports/control_plane/plan.md",
        INDICATOR,
        "src/keep.txt",
        "src/delete.txt",
        "src/new.txt",
    ]


def test_literal_base_inventory_tracks_rename_delete_and_untracked(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    _git(repo, "mv", "src/keep.txt", "src/renamed.txt")
    (repo / "src" / "delete.txt").unlink()
    (repo / "src" / "loose.txt").write_text("loose\n", encoding="utf-8")

    inventory = ca.collect_literal_base_inventory(repo, base)

    assert {
        (entry["kind"], entry["status"], entry.get("old_path"), entry["path"])
        for entry in inventory
    } == {
        ("tracked", "R", "src/keep.txt", "src/renamed.txt"),
        ("tracked", "D", None, "src/delete.txt"),
        ("untracked", "??", None, "src/loose.txt"),
    }


def test_prepare_stages_exact_allowlist_with_deletion_and_untracked(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    (repo / "src" / "delete.txt").unlink()
    (repo / "src" / "new.txt").write_text("new\n", encoding="utf-8")

    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=".agent_bus-test",
    )

    staged = _git(repo, "diff", "--cached", "--name-status").splitlines()
    assert "M\tsrc/keep.txt" in staged
    assert "D\tsrc/delete.txt" in staged
    assert "A\tsrc/new.txt" in staged
    assert f"A\t{INDICATOR}" in staged
    assert _git(repo, "ls-files", "--others", "--exclude-standard") == ""
    assert Path(receipt["receipt_path"]).is_file()
    assert ca.verify_current_receipt(repo, Path(receipt["receipt_path"]))["status"] == "current"


def test_outside_path_rejected_before_staging(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "outside.txt").write_text("outside\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="outside allowlist"):
        ca.prepare_candidate_authority(
            repo,
            _spec(base, _default_allowlist()),
            bus_dir=".agent_bus-test",
        )


def test_index_only_staged_path_outside_allowlist_rejected(tmp_path: Path):
    repo, _base = _init_repo(tmp_path)
    (repo / "outside.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "commit", "-q", "-m", "outside base")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / "outside.txt").write_text("staged outside\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "restore", "--worktree", "--source=HEAD", "--", "outside.txt")
    (repo / "src" / "keep.txt").write_text("allowed\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="outside allowlist: outside.txt"):
        ca.prepare_candidate_authority(
            repo,
            _spec(base, _default_allowlist()),
            bus_dir=".agent_bus-test",
        )


def test_receipt_rejects_post_receipt_candidate_mutation(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=".agent_bus-test",
    )

    (repo / "src" / "keep.txt").write_text("changed again\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="stale"):
        ca.verify_current_receipt(repo, Path(receipt["receipt_path"]))


def test_receipt_rejects_post_receipt_index_only_outside_mutation(tmp_path: Path):
    repo, _base = _init_repo(tmp_path)
    (repo / "outside.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "commit", "-q", "-m", "outside base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=".agent_bus-test",
    )

    (repo / "outside.txt").write_text("staged outside\n", encoding="utf-8")
    _git(repo, "add", "outside.txt")
    _git(repo, "restore", "--worktree", "--source=HEAD", "--", "outside.txt")

    with pytest.raises(ca.CandidateAuthorityError, match="outside allowlist: outside.txt"):
        ca.verify_current_receipt(repo, Path(receipt["receipt_path"]))


def test_receipt_tampering_is_rejected(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=".agent_bus-test",
    )
    receipt_path = Path(receipt["receipt_path"])
    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered["wave_id"] = "wrong-wave"
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="tampered|mismatched"):
        ca.verify_current_receipt(repo, receipt_path)


def test_prepare_is_deterministic_for_same_candidate(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    spec = _spec(base, _default_allowlist())

    first = ca.prepare_candidate_authority(repo, spec, bus_dir=".agent_bus-test")
    first_text = Path(first["receipt_path"]).read_text(encoding="utf-8")
    second = ca.prepare_candidate_authority(repo, spec, bus_dir=".agent_bus-test")
    second_text = Path(second["receipt_path"]).read_text(encoding="utf-8")

    assert first["receipt_path"] == second["receipt_path"]
    assert first_text == second_text
