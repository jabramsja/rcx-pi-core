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
    assert turns[0]["turn_id"] == f"{job_id}--r1-reviewer"
    assert turns[1]["turn_id"] == f"{job_id}--r1-reviewer-a2"
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


# --- Pause / Continue / Interactive ---


def _make_fake_config(repo_root: Path, fake_agent: Path) -> dict:
    return {
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


_FAKE_AGENT_SCRIPT = """\
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
"""


def _setup_bridge_repo(tmp_path: Path) -> tuple:
    """Create temp repo with fake agent and bridge config. Returns (paths, job_id)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_temp_repo(repo_root)
    paths = bridge.bridge_paths(repo_root)
    bridge.init_db(paths)

    fake_agent = repo_root / "fake_agent.py"
    fake_agent.write_text(_FAKE_AGENT_SCRIPT, encoding="utf-8")

    config = _make_fake_config(repo_root, fake_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return paths, fake_agent


def test_pause_after_reader_stops_before_reviewer(tmp_path: Path) -> None:
    """--pause-after-reader should stop with PAUSED and set AWAITING_REVIEWER_APPROVAL."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="pause test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="pause-test-job",
    )
    decision = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert decision == "PAUSED"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ?", (job_id,)).fetchall()

    assert job["status"] == "AWAITING_REVIEWER_APPROVAL"
    assert len(turns) == 1, "only reader should have run"
    assert turns[0]["agent_role"] == "reader"
    assert turns[0]["status"] == "completed"


def test_continue_resumes_paused_job_to_reviewer(tmp_path: Path) -> None:
    """continue_job should resume a paused job and run the reviewer to completion."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="continue test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="continue-test-job",
    )
    # Phase 1: run with pause
    decision = bridge.run_job(paths, job_id, pause_after_reader=True)
    assert decision == "PAUSED"

    # Phase 2: continue
    decision = bridge.continue_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert len(turns) == 2
    assert turns[0]["agent_role"] == "reader"
    assert turns[1]["agent_role"] == "reviewer"


def test_continue_rejects_non_paused_job(tmp_path: Path) -> None:
    """continue_job should raise BridgeError if job is not in paused state."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="not paused test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="not-paused-job",
    )
    with pytest.raises(bridge.BridgeError, match="not paused"):
        bridge.continue_job(paths, job_id)


def test_rendered_transcript_shows_paused_state(tmp_path: Path) -> None:
    """Rendered transcript should show founder-facing guidance when job is paused."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="render pause test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=2,
        acceptance_checks=[],
        job_id="render-pause-job",
    )
    bridge.run_job(paths, job_id, pause_after_reader=True)

    rendered_path = paths.rendered_dir / f"{job_id}.md"
    content = rendered_path.read_text(encoding="utf-8")
    assert "PAUSED" in content
    assert "awaiting founder review" in content
    assert "continue" in content


def test_verbose_mode_does_not_crash(tmp_path: Path) -> None:
    """Verbose (interactive) mode should work end-to-end without errors."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="verbose test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="verbose-test-job",
    )
    decision = bridge.run_job(paths, job_id, verbose=True)
    assert decision == "GO"


def test_non_interactive_behavior_unchanged(tmp_path: Path) -> None:
    """Default (non-interactive) run should still work exactly as before."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="default behavior test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="default-test-job",
    )
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns = conn.execute("SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)).fetchall()

    assert job["status"] == "DONE"
    assert len(turns) == 2
    assert {t["agent_role"] for t in turns} == {"reader", "reviewer"}


def test_crash_recovery_reviewer_completed_no_rerun(tmp_path: Path) -> None:
    """If reviewer completed but status stuck at REVIEWER_RUNNING, recovery applies recorded decision without rerunning."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="crash recovery test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="crash-recovery-job",
    )
    # Run to completion normally first
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash: force status back to REVIEWER_RUNNING (as if crash happened
    # after reviewer turn was recorded but before job status was updated to DONE)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            "UPDATE jobs SET status = 'REVIEWER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()
        turns_before = conn.execute(
            "SELECT count(*) as cnt FROM turns WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]

    # Recovery run should NOT add a new reviewer turn — should apply existing
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        turns_after = conn.execute(
            "SELECT count(*) as cnt FROM turns WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert turns_after == turns_before, "recovery should not add new turns"


def test_crash_recovery_reader_completed_reruns_validations(tmp_path: Path) -> None:
    """If reader completed but status stuck at READER_RUNNING, recovery reruns validations before advancing to reviewer."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="reader crash recovery test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="reader-crash-job",
    )
    # Run to completion normally
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash: force status to READER_RUNNING with current_round=1
    # (as if crash happened after reader turn recorded but before validations/reviewer)
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        # Delete the reviewer turn and validations to simulate incomplete state
        conn.execute("DELETE FROM turns WHERE job_id = ? AND agent_role = 'reviewer'", (job_id,))
        conn.execute("DELETE FROM validations WHERE job_id = ?", (job_id,))
        conn.execute(
            "UPDATE jobs SET status = 'READER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()
        # Verify no validations exist
        val_count = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert val_count == 0, "setup: validations should be cleared"

    # Recovery should rerun validations then run reviewer
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        validations = conn.execute(
            "SELECT * FROM validations WHERE job_id = ?", (job_id,)
        ).fetchall()
        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job_id,)
        ).fetchall()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"
    assert len(validations) > 0, "validations should have been rerun during recovery"
    assert any(t["agent_role"] == "reviewer" for t in turns), "reviewer should have run after recovery"


def test_crash_recovery_reader_with_partial_validations(tmp_path: Path) -> None:
    """If reader completed and some validations were committed before crash, recovery clears and reruns without PK collision."""
    paths, _ = _setup_bridge_repo(tmp_path)

    job_id = bridge.submit_job(
        paths,
        task_text="partial validation crash test",
        scope_hint=None,
        wave_class="MAINTENANCE",
        allow_edits=False,
        reader_agent="claude",
        reviewer_agent="codex",
        max_rounds=1,
        acceptance_checks=[],
        job_id="partial-val-crash-job",
    )
    # Run to completion normally
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    # Simulate crash after validations committed but before status update:
    # Keep validations, delete reviewer, reset status to READER_RUNNING
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("DELETE FROM turns WHERE job_id = ? AND agent_role = 'reviewer'", (job_id,))
        # Keep validation rows — this is the scenario that would cause PK collision
        val_count_before = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert val_count_before > 0, "setup: validations should exist"
        conn.execute(
            "UPDATE jobs SET status = 'READER_RUNNING', terminal_decision = NULL WHERE job_id = ?",
            (job_id,),
        )
        conn.commit()

    # Recovery should NOT crash with IntegrityError — should clear and rerun
    decision = bridge.run_job(paths, job_id)
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

    assert job["status"] == "DONE"
    assert job["terminal_decision"] == "GO"


# --- Hybrid review (Option C) ---


def test_review_job_synthetic_reader_then_reviewer(tmp_path: Path) -> None:
    """review_job should record synthetic reader turn and run reviewer to GO."""
    paths, _ = _setup_bridge_repo(tmp_path)

    decision = bridge.review_job(
        paths,
        task_text="test hybrid review",
        reader_summary="Implemented feature X. Changed foo.py and bar.py.",
        wave_class="MAINTENANCE",
        reviewer_agent="codex",
        acceptance_checks=[],
        verbose=True,
    )
    assert decision == "GO"

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        jobs = conn.execute("SELECT * FROM jobs").fetchall()
        assert len(jobs) == 1
        job = jobs[0]
        assert job["status"] == "DONE"
        assert job["terminal_decision"] == "GO"
        assert job["reader_agent"] == "claude-session"

        turns = conn.execute(
            "SELECT * FROM turns WHERE job_id = ? ORDER BY started_at", (job["job_id"],)
        ).fetchall()
        assert len(turns) == 2
        reader_turn = turns[0]
        reviewer_turn = turns[1]
        assert reader_turn["agent_role"] == "reader"
        assert reader_turn["status"] == "completed"
        assert reviewer_turn["agent_role"] == "reviewer"
        assert reviewer_turn["status"] == "completed"

        # Reader envelope should contain our summary
        reader_env = json.loads(reader_turn["envelope_json"])
        assert "feature X" in reader_env["summary"]

        # Validations should exist
        val_count = conn.execute(
            "SELECT count(*) as cnt FROM validations WHERE job_id = ?", (job["job_id"],)
        ).fetchone()["cnt"]
        assert val_count > 0


def test_review_job_rendered_transcript_includes_findings(tmp_path: Path) -> None:
    """Rendered transcript from review should include findings when present."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a fake reviewer that returns findings
    findings_agent = tmp_path / "repo" / "findings_agent.py"
    findings_agent.write_text("""\
import json
import re
import sys

prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
decision = "GO" if role == "reviewer" else "REQUEST_CHANGES"
findings = []
if role == "reviewer":
    findings = [{
        "class": "DEFECT",
        "severity": "medium",
        "title": "Missing null check",
        "file": "foo.py",
        "line_start": 42,
        "line_end": 42,
        "evidence_cmd": "grep -n null foo.py",
        "evidence_result": "no null check found",
        "status": "new"
    }]
    decision = "GO"
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job,
    "turn_id": turn_id,
    "agent_role": role,
    "decision": decision,
    "summary": "found a finding",
    "touched_files_claimed": [],
    "findings": findings,
    "validations_claimed": [],
    "request_for_next_agent": "fix the finding"
}, indent=2))
print("END_AGENT_ENVELOPE")
""", encoding="utf-8")

    config = _make_fake_config(tmp_path / "repo", findings_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    decision = bridge.review_job(
        paths,
        task_text="findings test",
        reader_summary="test implementation",
        reviewer_agent="codex",
    )
    assert decision == "GO"

    # Check rendered transcript includes finding details
    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute("SELECT * FROM jobs").fetchone()
    rendered_path = paths.rendered_dir / f"{job['job_id']}.md"
    content = rendered_path.read_text(encoding="utf-8")
    assert "DEFECT" in content
    assert "Missing null check" in content
    assert "foo.py" in content


def test_review_cli_subcommand(tmp_path: Path) -> None:
    """The review CLI subcommand should parse correctly."""
    args = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "test task",
        "--summary", "test summary",
        "--reviewer", "codex",
        "--wave-class", "MAINTENANCE",
        "-v",
    ])
    assert args.command == "review"
    assert args.task == "test task"
    assert args.summary == "test summary"
    assert args.reviewer == "codex"
    assert args.wave_class == "MAINTENANCE"
    assert args.verbose is True


def test_verbose_review_prints_structured_envelope(tmp_path: Path, capsys) -> None:
    """Verbose review should print structured envelope with findings to stdout."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a reviewer that returns findings
    findings_agent = tmp_path / "repo" / "findings_reviewer.py"
    findings_agent.write_text("""\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
role = "reviewer" if "You are the REVIEWER" in prompt else "reader"
turn_id = f"r{round_no}-{role}"
findings = [{
    "class": "DEFECT", "severity": "high", "title": "Null pointer",
    "file": "main.py", "line_start": 10, "status": "new",
    "evidence_cmd": "grep null main.py", "evidence_result": "crash at line 10",
    "line_end": 10
}]
print("BEGIN_AGENT_ENVELOPE")
print(json.dumps({
    "job_id": job, "turn_id": turn_id, "agent_role": role,
    "decision": "GO", "summary": "Found 1 issue but non-blocking",
    "touched_files_claimed": [], "findings": findings,
    "validations_claimed": [], "request_for_next_agent": "fix it"
}, indent=2))
print("END_AGENT_ENVELOPE")
""", encoding="utf-8")

    config = _make_fake_config(tmp_path / "repo", findings_agent)
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    decision = bridge.review_job(
        paths,
        task_text="envelope output test",
        reader_summary="test implementation",
        reviewer_agent="codex",
        verbose=True,
    )
    assert decision == "GO"

    captured = capsys.readouterr().out
    # Verify structured envelope is printed inline
    assert "REVIEWER (codex)" in captured
    assert "DEFECT (high): Null pointer" in captured
    assert "main.py:10" in captured
    assert "crash at line 10" in captured
    assert "fix it" in captured


def test_no_diff_flag_cli_parsing(tmp_path: Path) -> None:
    """The --no-diff flag should parse correctly on the review subcommand."""
    args = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "design question",
        "--summary", "context",
        "--no-diff",
    ])
    assert args.no_diff is True

    # Without --no-diff, default is False
    args2 = bridge.build_parser().parse_args([
        "--repo-root", str(tmp_path),
        "review",
        "--task", "code change",
        "--summary", "did stuff",
    ])
    assert args2.no_diff is False


def test_no_diff_review_omits_diff_from_reviewer_prompt(tmp_path: Path) -> None:
    """When include_diff=False, the reviewer prompt should not contain git diff content."""
    paths, _ = _setup_bridge_repo(tmp_path)

    # Create a file change so there IS a diff (but --no-diff should suppress it)
    (tmp_path / "repo" / "new_file.py").write_text("print('hello')\n")
    _git(tmp_path / "repo", "add", "new_file.py")

    # Create a reviewer that echoes back the prompt so we can inspect it
    echo_agent = tmp_path / "repo" / "echo_reviewer.py"
    echo_agent.write_text("""\
import json, re, sys
prompt = sys.stdin.read()
job = re.search(r"JOB_ID: (.+)", prompt).group(1).strip()
round_no = re.search(r"ROUND: (.+)", prompt).group(1).strip()
# Check if diff was suppressed
has_design_deliberation = "design deliberation" in prompt
envelope = {
    "job_id": job, "turn_id": f"{job}--r{round_no}-reviewer",
    "agent_role": "reviewer", "decision": "GO",
    "summary": f"diff_suppressed={has_design_deliberation}",
    "touched_files_claimed": [], "findings": [],
    "validations_claimed": [], "request_for_next_agent": ""
}
print(f"BEGIN_AGENT_ENVELOPE\\n{json.dumps(envelope)}\\nEND_AGENT_ENVELOPE")
""")

    config = json.loads((paths.bus_dir / "bridge_config.json").read_text())
    config["agents"]["codex"] = {
        "mode": "live",
        "cmd": [sys.executable, str(echo_agent)],
        "prompt_via_stdin": True,
        "timeout_s": 30,
    }
    (paths.bus_dir / "bridge_config.json").write_text(json.dumps(config))

    result = bridge.review_job(
        paths,
        task_text="Should we add event streaming?",
        reader_summary="Design deliberation about bridge UX improvements",
        include_diff=False,
    )
    assert result == "GO"

    # Verify the reviewer saw the "design deliberation" marker, not actual diff
    with bridge.open_db(paths) as conn:
        # Get the job_id from the most recent job
        row = conn.execute("SELECT job_id FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
        assert row is not None
        reviewer_env = bridge.latest_envelope(conn, row["job_id"], role="reviewer")
    assert reviewer_env is not None
    assert "diff_suppressed=True" in reviewer_env["summary"]
