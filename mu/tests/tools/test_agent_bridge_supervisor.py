"""Tests for the agent bridge supervisor v1."""

from __future__ import annotations

import fcntl
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_module("bridge_supervisor", REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


def _init_temp_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.name", "Bridge Test")
    _git(repo, "config", "user.email", "bridge@example.com")
    (repo / "README.md").write_text("bridge test repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def test_parse_envelope_from_mixed_output() -> None:
    output = """Some prose\nBEGIN_AGENT_ENVELOPE\n{\n  \"job_id\": \"job-1\",\n  \"turn_id\": \"r1-reader\",\n  \"agent_role\": \"reader\",\n  \"decision\": \"REQUEST_CHANGES\",\n  \"summary\": \"Need review\",\n  \"touched_files_claimed\": [],\n  \"findings\": [],\n  \"validations_claimed\": [],\n  \"request_for_next_agent\": \"review\"\n}\nEND_AGENT_ENVELOPE\nMore prose\n"""
    envelope = bridge.parse_envelope(output)
    assert envelope["job_id"] == "job-1"
    assert envelope["decision"] == "REQUEST_CHANGES"


def test_init_db_creates_runtime_paths_and_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    assert paths.db_path.exists()
    assert paths.prompts_dir.exists()
    assert paths.raw_dir.exists()
    assert paths.rendered_dir.exists()
    assert paths.config_path.exists()


def test_run_job_end_to_end_with_fake_agents(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = repo_root / "fake_agent.py"
    fake_agent.write_text(
        """
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
summary = "review complete" if role == "reviewer" else "reader pass complete"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": summary,
    "touched_files_claimed": [],
    "findings": [],
    "validations_claimed": [],
    "request_for_next_agent": "none"
}, indent=2))
print("END_AGENT_ENVELOPE")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(fake_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="Implement bridge v1",
        scope_hint="tooling",
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="bridge-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()
        validations = conn.execute("SELECT * FROM validations WHERE job_id = ?", (job_id,)).fetchall()

    assert job["terminal_decision"] == "GO"
    assert job["status"] == "DONE"
    assert len(turns) == 2
    assert {turn["agent_role"] for turn in turns} == {"reader", "reviewer"}
    assert validations, "expected at least git-status validation"
    assert (paths.rendered_dir / f"{job_id}.md").exists()


# --- Negative path: envelope parsing ---


def test_parse_envelope_missing_block_raises() -> None:
    with pytest.raises(bridge.BridgeError, match="missing BEGIN_AGENT_ENVELOPE"):
        bridge.parse_envelope("Just prose, no envelope here")


def test_parse_envelope_invalid_json_raises() -> None:
    output = "BEGIN_AGENT_ENVELOPE\n{not valid json}\nEND_AGENT_ENVELOPE"
    with pytest.raises(bridge.BridgeError, match="not valid JSON"):
        bridge.parse_envelope(output)


def test_parse_envelope_missing_keys_raises() -> None:
    output = 'BEGIN_AGENT_ENVELOPE\n{"job_id": "x", "turn_id": "t"}\nEND_AGENT_ENVELOPE'
    with pytest.raises(bridge.BridgeError, match="missing keys"):
        bridge.parse_envelope(output)


# --- DEFECT-1: stale reviewer retry turn_id collision ---


def test_stale_reviewer_retry_no_turn_id_collision(tmp_path: Path) -> None:
    """Verify stale reviewer retry uses distinct turn_id (r1-reviewer-a2)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    stale_agent = repo_root / "stale_agent.py"
    stale_agent.write_text(
        """\
import json
import os
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"

# First reviewer call: create marker file to change repo state (triggers staleness)
if role == "reviewer":
    marker = os.path.join(os.getcwd(), "_staleness_marker.txt")
    if not os.path.exists(marker):
        with open(marker, "w") as f:
            f.write("stale trigger")

turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": "done",
    "touched_files_claimed": [],
    "findings": [],
    "validations_claimed": [],
    "request_for_next_agent": "none"
}, indent=2))
print("END_AGENT_ENVELOPE")
""",
        encoding="utf-8",
    )

    config = {
        "agents": {
            "claude": {
                "mode": "live",
                "cmd": [sys.executable, str(stale_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
            "codex": {
                "mode": "live",
                "cmd": [sys.executable, str(stale_agent)],
                "prompt_via_stdin": True,
                "timeout_s": 30,
                "env": {},
            },
        }
    }
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    job_id = bridge.submit_job(
        paths,
        task_text="staleness retry test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="stale-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? AND agent_role = 'reviewer' ORDER BY started_at",
            (job_id,),
        ).fetchall()

    assert len(turns) == 2, f"expected 2 reviewer turns (stale + retry), got {len(turns)}"
    assert turns[0]["turn_id"] == "r1-reviewer"
    assert turns[1]["turn_id"] == "r1-reviewer-a2"
    assert turns[0]["status"] == "stale"
    assert turns[1]["status"] == "completed"


# --- DESIGN-1: reviewer prompt includes staged diff ---


def test_reviewer_prompt_includes_staged_diff(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    (repo_root / "README.md").write_text("updated content for diff test\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")

    job_id = bridge.submit_job(
        paths,
        task_text="diff visibility test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=True,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="diff-test-job",
    )

    with bridge.open_db(paths) as conn:
        job = bridge.read_job(conn, job_id)
        prompt = bridge.build_reviewer_prompt(conn, paths, job, 1, [])

    assert "$staged_diff" not in prompt, "template variable not substituted"
    assert "README.md" in prompt, "staged diff should reference changed file"
    assert "+updated content for diff test" in prompt, "staged diff should show added line"


# --- DEFECT-4: single-supervisor file lock ---


def test_file_lock_blocks_concurrent_run(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    job_id = bridge.submit_job(
        paths,
        task_text="lock test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="lock-test-job",
    )

    lock_path = paths.bus_dir / "bridge.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fp = open(lock_path, "w")
    try:
        fcntl.flock(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(bridge.BridgeError, match="Another bridge supervisor"):
            bridge.run_job(paths, job_id)
    finally:
        fcntl.flock(fp, fcntl.LOCK_UN)
        fp.close()
