from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import candidate_authority as ca  # noqa: E402
import executor_common as ec  # noqa: E402


WAVE_ID = "candidate-authority-test-2026-08-21"
INDICATOR = f"reports/l4_wave_indicators/{WAVE_ID}.json"
INDICATOR_COMMAND = (
    "python3 tools/metrics/collect_l4_wave_indicators.py "
    f"--wave-id {WAVE_ID} --output {INDICATOR}"
)
BUS_DIR = ".agent_bus-test"
CODEX_CMD = [
    "codex",
    "exec",
    "-",
    "--json",
    "-m",
    "gpt-5.5",
    "-c",
    'model_reasoning_effort="xhigh"',
    "--sandbox",
    "danger-full-access",
]
CLAUDE_CMD = [
    "claude",
    "--print",
    "--model",
    "claude-opus-4-8",
    "--effort",
    "max",
]


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
    _write_bridge_config(repo)
    return repo, _git(repo, "rev-parse", "HEAD")


def _ignore_bus(repo: Path, bus_dir: str = BUS_DIR) -> None:
    exclude = repo / ".git" / "info" / "exclude"
    pattern = f"/{bus_dir}/"
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if pattern not in existing.splitlines():
        if existing and not existing.endswith("\n"):
            existing += "\n"
        exclude.write_text(existing + pattern + "\n", encoding="utf-8")


def _write_bridge_config(
    repo: Path,
    *,
    bus_dir: str = BUS_DIR,
    codex_cmd: list[object] | None = None,
    claude_cmd: list[object] | None = None,
) -> Path:
    _ignore_bus(repo, bus_dir)
    path = repo / bus_dir / "bridge_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agents": {
            "codex": {
                "display_name": "Codex 5.5 xhigh",
                "cmd": list(CODEX_CMD if codex_cmd is None else codex_cmd),
                "env": {"RCX_TEST_SECRET": "not-serialized"},
            },
            "claude": {
                "display_name": "Claude Opus 4.8 max",
                "cmd": list(CLAUDE_CMD if claude_cmd is None else claude_cmd),
                "env": {"RCX_TEST_SECRET": "not-serialized"},
            },
        }
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _spec(
    base: str,
    allowlist: list[str],
    *,
    review_round: str = "r1",
    reviewer_agent: str = "codex",
) -> ca.CandidateAuthoritySpec:
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
            "reviewer_agent": reviewer_agent,
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


def test_reviewer_launch_provenance_extracts_exact_codex_model_effort(tmp_path: Path):
    repo, _base = _init_repo(tmp_path)

    provenance = ec.reviewer_launch_provenance(
        repo,
        bus_dir=BUS_DIR,
        selected_agent="codex",
    )

    assert provenance["selected_agent"] == "codex"
    assert provenance["model"] == "gpt-5.5"
    assert provenance["effort"] == "xhigh"
    assert provenance["bridge_config_path"] == f"{BUS_DIR}/bridge_config.json"
    assert len(provenance["command_sha256"]) == 64
    assert len(provenance["bridge_config_sha256"]) == 64
    serialized = json.dumps(provenance, sort_keys=True)
    assert "RCX_TEST_SECRET" not in serialized
    assert "danger-full-access" not in serialized


@pytest.mark.parametrize(
    ("selected_agent", "cmd", "expected_model", "expected_effort"),
    [
        ("codex", CODEX_CMD, "gpt-5.5", "xhigh"),
        ("claude", CLAUDE_CMD, "claude-opus-4-8", "max"),
        (
            "codex",
            [
                "codex",
                "exec",
                "-",
                "--json",
                "--model",
                "gpt-5.5",
                "-c",
                "model_reasoning_effort=xhigh",
            ],
            "gpt-5.5",
            "xhigh",
        ),
    ],
)
def test_reviewer_launch_provenance_supports_provider_polymorphic_shapes(
    tmp_path: Path,
    selected_agent: str,
    cmd: list[str],
    expected_model: str,
    expected_effort: str,
):
    repo, _base = _init_repo(tmp_path)
    if selected_agent == "codex":
        _write_bridge_config(repo, codex_cmd=cmd)
    else:
        _write_bridge_config(repo, claude_cmd=cmd)

    provenance = ec.reviewer_launch_provenance(
        repo,
        bus_dir=BUS_DIR,
        selected_agent=selected_agent,
    )

    assert provenance["model"] == expected_model
    assert provenance["effort"] == expected_effort


@pytest.mark.parametrize(
    ("cmd", "match"),
    [
        (["codex", "exec", "-c", 'model_reasoning_effort="xhigh"'], "missing --model"),
        (["codex", "exec", "-m"], "missing a value"),
        (["codex", "exec", "-m", ""], "cannot be empty"),
        (["codex", "exec", "-m", "gpt-5.5", "-m", "gpt-5.5"], "duplicate"),
        (
            ["codex", "exec", "-m", "gpt-5.5", "-c", 'model_reasoning_effort="'],
            "malformed",
        ),
        (
            ["codex", "exec", "-m", "gpt-5.5", "--effort", "xhigh", "-c", "model_reasoning_effort=xhigh"],
            "duplicate",
        ),
        (["codex", "exec", "-m", "gpt-5.5", "--effort", ""], "cannot be empty"),
        (["codex", "exec", "-m", "gpt-5.5", "--effort", 4], "must be a string"),
    ],
)
def test_reviewer_launch_provenance_rejects_malformed_or_ambiguous_selectors(
    tmp_path: Path,
    cmd: list[object],
    match: str,
):
    repo, _base = _init_repo(tmp_path)
    _write_bridge_config(repo, codex_cmd=cmd)

    with pytest.raises(ec.ExecutorCommonError, match=match):
        ec.reviewer_launch_provenance(repo, bus_dir=BUS_DIR, selected_agent="codex")


def test_reviewer_launch_provenance_rejects_missing_agent_and_default_bus(tmp_path: Path):
    repo, _base = _init_repo(tmp_path)
    _write_bridge_config(repo, bus_dir=".agent_bus")

    with pytest.raises(ec.ExecutorCommonError, match="absent"):
        ec.reviewer_launch_provenance(repo, bus_dir=BUS_DIR, selected_agent="missing")
    with pytest.raises(ec.ExecutorCommonError, match="namespaced"):
        ec.reviewer_launch_provenance(repo, bus_dir=".agent_bus", selected_agent="codex")


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
    assert receipt["reviewer_agent"] == "codex"
    assert receipt["reviewer_launch_provenance"]["model"] == "gpt-5.5"
    assert receipt["reviewer_launch_provenance"]["effort"] == "xhigh"
    assert len(receipt["reviewer_launch_provenance_hash"]) == 64
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


def test_receipt_verification_rejects_missing_or_malformed_reviewer_provenance(
    tmp_path: Path,
):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=BUS_DIR,
    )
    receipt_path = Path(receipt["receipt_path"])
    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered.pop("reviewer_launch_provenance")
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="reviewer_launch_provenance"):
        ca.verify_current_receipt(repo, receipt_path)

    tampered["reviewer_launch_provenance"] = {"selected_agent": "codex"}
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="reviewer_launch_provenance"):
        ca.verify_current_receipt(repo, receipt_path)


def test_receipt_verification_rejects_removed_reviewer_provenance_downgrade(
    tmp_path: Path,
):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=BUS_DIR,
    )
    receipt_path = Path(receipt["receipt_path"])
    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered.pop("reviewer_agent")
    tampered.pop("reviewer_launch_provenance")
    tampered.pop("reviewer_launch_provenance_hash")
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="reviewer_launch_provenance"):
        ca.verify_current_receipt(repo, receipt_path)


def test_receipt_verification_rejects_reviewer_bridge_config_drift(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=BUS_DIR,
    )
    bridge_path = repo / BUS_DIR / "bridge_config.json"
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    bridge["agents"]["codex"]["display_name"] = "Codex drifted"
    bridge_path.write_text(json.dumps(bridge, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="reviewer_launch_provenance"):
        ca.verify_current_receipt(repo, Path(receipt["receipt_path"]))


def test_receipt_verification_rejects_reviewer_command_drift(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    receipt = ca.prepare_candidate_authority(
        repo,
        _spec(base, _default_allowlist()),
        bus_dir=BUS_DIR,
    )
    _write_bridge_config(
        repo,
        codex_cmd=[
            "codex",
            "exec",
            "-",
            "--json",
            "-m",
            "gpt-5.4",
            "-c",
            'model_reasoning_effort="xhigh"',
        ],
    )

    with pytest.raises(ca.CandidateAuthorityError, match="reviewer_launch_provenance"):
        ca.verify_current_receipt(repo, Path(receipt["receipt_path"]))


def test_launch_bound_spec_identity_rejects_bus_spec_tampering(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    spec = _spec(base, _default_allowlist())
    trusted_identity = ca.authority_spec_identity(
        repo,
        spec,
        authority_required=True,
    )
    tampered = ca.CandidateAuthoritySpec.from_mapping(
        {
            **spec.to_dict(),
            "candidate_allowlist": [*_default_allowlist(), "src/extra.txt"],
        }
    )

    with pytest.raises(ca.CandidateAuthorityError, match="launch-bound identity"):
        ca.verify_authority_spec_identity(repo, tampered, trusted_identity)


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("wave_id", "wrong-wave"),
        ("phase", "wrong_phase"),
        ("review_round", "wrong_round"),
        ("plan_path", "TASKS.md"),
        ("plan_hash", "0" * 64),
        ("indicator_hash", "0" * 64),
        ("literal_base_inventory", []),
        ("literal_base_inventory_hash", "0" * 64),
        ("staged_literal_base_inventory", []),
        ("staged_literal_base_inventory_hash", "0" * 64),
        ("index_tree_hash", "0" * 40),
        ("staged_binary_diff_sha256", "0" * 64),
        ("l4_contract", {"status": "passed"}),
        ("l4_contract_hash", "0" * 64),
        ("reviewer_agent", "claude"),
        ("reviewer_launch_provenance", {"selected_agent": "codex"}),
        ("reviewer_launch_provenance_hash", "0" * 64),
    ],
)
def test_receipt_verification_uses_trusted_spec_and_recomputed_evidence(
    tmp_path: Path,
    field: str,
    tampered_value,
):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    spec = _spec(base, _default_allowlist(), review_round="trusted-round")
    receipt = ca.prepare_candidate_authority(
        repo,
        spec,
        bus_dir=".agent_bus-test",
    )
    receipt_path = Path(receipt["receipt_path"])
    tampered = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered[field] = tampered_value
    receipt_path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(
        ca.CandidateAuthorityError,
        match="tampered|mismatched|reviewer_launch_provenance",
    ):
        ca.verify_current_receipt(
            repo,
            receipt_path,
            trusted_spec=spec,
            phase="phase_b",
            review_round="trusted-round",
        )


def test_receipt_verification_rejects_caller_owned_round_mismatch(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "src" / "keep.txt").write_text("changed\n", encoding="utf-8")
    spec = _spec(base, _default_allowlist(), review_round="trusted-round")
    receipt = ca.prepare_candidate_authority(
        repo,
        spec,
        bus_dir=".agent_bus-test",
    )

    with pytest.raises(ca.CandidateAuthorityError, match="review_round"):
        ca.verify_current_receipt(
            repo,
            Path(receipt["receipt_path"]),
            trusted_spec=spec,
            phase="phase_b",
            review_round="different-round",
        )


def test_pre_mutation_scope_guard_is_read_only_and_rejects_outside_state(tmp_path: Path):
    repo, base = _init_repo(tmp_path)
    (repo / "outside.txt").write_text("outside\n", encoding="utf-8")

    with pytest.raises(ca.CandidateAuthorityError, match="outside allowlist"):
        ca.guard_candidate_scope_before_mutation(repo, _spec(base, _default_allowlist()))

    assert _git(repo, "diff", "--cached", "--name-only") == ""


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
