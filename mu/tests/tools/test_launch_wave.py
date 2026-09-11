"""Regression tests for the launch_wave dispatcher-wave setup builder.

launch_wave mechanizes the full per-wave setup from one wave-config as a SIMPLE
sequential chain over the existing builders (no transactional/rollback layer).
These tests cover:

  * the sequential setup (all artifacts produced from one config),
  * the baked-in packet fences (packet-integrity, line-ref lint, asterisk-free
    title, run_mu # SPEED_OK),
  * the fail-closed precondition (the dispatcher's own pre-Phase-B gate),
  * the 3-guard verification,
  * the optional dispatcher launch (off by default), and
  * the bounded re-run recovery contract: a partial run re-run with the SAME
    wave-config converges to exactly one canonical copy of each artifact.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "mu" / "tools" / "executors"))
import launch_wave as lw  # noqa: E402,I001  (path insert must precede import)
import tracker_sync_note as tsn  # noqa: E402  (reuse proof for the note builder)
import executor_common as ec  # noqa: E402  (public seam for the routing-record path)
import executor_dispatch as ed  # noqa: E402  (public dispatcher seams)
import commit_executor as ce  # noqa: E402  (authoritative continuation producer)
from meta_bridge_supervisor import compute_repo_state  # noqa: E402  (public state seam)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                           #
# --------------------------------------------------------------------------- #

_NOTE_HEADER_RE = re.compile(r"^- Tracker sync note \([^,]+,\s*([^)]+)\):", re.MULTILINE)
_DISPATCHER_OVERRIDE_ENV_KEYS_FOR_TEST = (
    ec.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
    "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE",
    *(
        key
        for env_keys in ec.ROLE_AGENT_ENV_VARS.values()
        for key in env_keys
    ),
)


def _git(repo, *args):
    subprocess.run(
        ["git", *args], cwd=str(repo), check=True, capture_output=True
    )


@pytest.fixture
def wave_repo(tmp_path, monkeypatch):
    """A minimal git repo with the structure launch_wave's builders expect."""
    repo = tmp_path
    launcher_source = repo / "mu" / "tools" / "executors"
    launcher_source.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[tool.placeholder]\n", encoding="utf-8")
    (repo / "reports" / "control_plane").mkdir(parents=True)
    # The Ra section must already carry at least one tracker note so the upsert
    # builder has a canonical insertion anchor.
    (repo / "TASKS.md").write_text(
        "# TASKS\n\n## Ra\n\n"
        "- Tracker sync note (2026-06-18, seed-wave): **Seed.** Class: MAINTENANCE. "
        "target_gate_id: G8. FOUNDER_OVERRIDE:seed-wave.\n\n"
        "---\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    monkeypatch.setattr(lw, "SCRIPT_DIR", launcher_source)
    return repo


def make_config(**overrides):
    """Build a fresh L4_ENABLER WaveConfig (re-run tests need fresh objects)."""
    base = dict(
        wave_id="demo-launcher-wave-2026-06-19",
        title="Demo Launcher Wave 2026-06-19",
        task_id="[NEXT-CODEX-POST-REDTEAM]",
        purpose="Demo wave for the launch_wave builder regression test.",
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        primary_blocker_class="DESIGN",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref="reports/l4_wave_indicators/demo.json",
        indicator_collection_command=(
            "python3 tools/metrics/collect_l4_wave_indicators.py "
            "--wave-id demo --output reports/l4_wave_indicators/demo.json"
        ),
        evidence_command="PYTHONHASHSEED=0 python3 -m pytest -q --tb=short",
        evidence_delta="New builder mechanizes the setup.",
        progress_proof_before="no builder",
        progress_proof_after="builder exists",
        scope_items=["mu/tools/executors/launch_wave.py (NEW)"],
        work_items=["Create the builder", "Add the regression test"],
        constraints=["No runtime/substrate changes"],
        stop_conditions=["Halt on a red gate"],
        acceptance_criteria=["Builder exists", "Test passes"],
        date="2026-06-19",
    )
    base.update(overrides)
    return lw.WaveConfig(**base)


def _phase_b_packet_content(config):
    content = lw.render_wave_packet(config)
    content = content.replace(
        "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)",
        "Status: Phase B (pre-supervisor pending, bridge-converged)",
    )
    content = content.replace("Phase-A-Lock: UNLOCKED", "Phase-A-Lock: LOCKED")
    content += (
        "\n<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
        "## Phase B Indicator Scope Reconciliation\n\n"
        f"- Refresh wave: `{config.wave_id}`\n"
        f"- Active packet: `{config.tracked_packet}`\n"
        "- Purpose: Phase B mechanically collected and staged same-wave scope "
        "before pre-commit supervisor review.\n"
        "- Authorized staged files:\n"
        "  - `TASKS.md`\n"
        "  - `mu/tools/executors/phase_b_executor.py`\n"
        "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
    )
    return content


def _same_wave_deferred_non_blocking_path(config):
    return (
        "reports/deferred/non_blocking/"
        f"{config.wave_id}_bridge_nonblockers.md"
    )


def _commit_recovery_packet_content(repo, config, downstream_status):
    """Produce the exact post-lock packet through the public commit refresh."""
    assert downstream_status in (
        ce.COMMIT_RETRY_PENDING_STATUS,
        ce.COMMIT_RETRY_RESTORED_STATUS,
    )
    phase_b_status = "Status: Phase B (pre-supervisor pending, bridge-converged)"
    content = _phase_b_packet_content(config).replace(
        phase_b_status,
        f"Status: {downstream_status}",
        1,
    )
    packet_path = repo / config.tracked_packet
    packet_path.write_text(content, encoding="utf-8")

    indicator_path = repo / config.indicator_artifact_ref
    indicator_path.parent.mkdir(parents=True, exist_ok=True)
    indicator_path.write_text(
        json.dumps({"wave_id": config.wave_id}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    deferred_rel = _same_wave_deferred_non_blocking_path(config)
    deferred_path = repo / deferred_rel
    deferred_path.parent.mkdir(parents=True, exist_ok=True)
    deferred_path.write_text(
        f"# Same-wave non-blocking findings for {config.wave_id}\n",
        encoding="utf-8",
    )
    _git(
        repo,
        "add",
        "--",
        "TASKS.md",
        config.tracked_packet,
        config.indicator_artifact_ref,
        deferred_rel,
    )

    tracker_note = _tracker_note_line(
        (repo / "TASKS.md").read_text(encoding="utf-8"),
        config.wave_id,
    )
    handoff, errors = ce.build_commit_handoff(
        wave_id=config.wave_id,
        task_id=config.task_id,
        files_to_stage=[
            "TASKS.md",
            config.tracked_packet,
            config.indicator_artifact_ref,
            deferred_rel,
        ],
        commit_message="Refresh the same-wave recovery packet",
        fixes_implemented=["Refresh exact same-wave deferred authorization"],
        wave_class=config.wave_class,
        target_gate_id=config.target_gate_id,
        caller="phase_b",
        tracker_note_text=tracker_note,
        tracked_packet=config.tracked_packet,
        deferred_items=[deferred_rel],
        repo_root=repo,
    )
    assert errors == []
    _refreshed_handoff, staged_paths, error = ce.refresh_commit_path_packet_truth(
        repo_root=repo,
        handoff=handoff,
        indicator_path=config.indicator_artifact_ref,
        commit_status="pre_commit_supervisor_pending",
    )
    assert error is None
    assert deferred_rel in staged_paths
    return packet_path.read_text(encoding="utf-8")


def _canonical_handoff_sha_for_test(handoff):
    canonical = json.dumps(
        handoff,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _tracker_note_line(content, wave_id):
    matches = [
        line
        for line in content.splitlines()
        if line.startswith("- Tracker sync note ") and f", {wave_id}):" in line
    ]
    assert len(matches) == 1
    return matches[0]


def _phase_b_tracker_note_line(note_line):
    note_line = note_line.replace(
        "**Demo Launcher Wave 2026-06-19.**",
        "**NEXT-CODEX-POST-REDTEAM - Phase B pre-commit supervisor package.**",
    )
    note_line = note_line.replace(
        "evidence_delta: New builder mechanizes the setup.",
        "evidence_delta: (1) Phase B converged on the locked plan. "
        "(2) Final pytest gate covered wave-owned files. "
        "scope_refs: `TASKS.md`, `mu/tools/executors/phase_b_executor.py`.",
    )
    note_line = note_line.replace(
        "progress_proof_after: builder exists.",
        "progress_proof_after: Phase B staged a canonical tracker note before "
        "pre-commit supervisor validation; reentry=true.",
    )
    return note_line


def _artifact_counts(repo, wave_id):
    """Return (packet count, tracker-note count, routing-candidate count)."""
    packets = list((repo / "reports" / "control_plane").glob(f"{wave_id}_*.md"))
    tasks = (repo / "TASKS.md").read_text(encoding="utf-8")
    notes = [m for m in _NOTE_HEADER_RE.findall(tasks) if m.strip() == wave_id]
    routing_path = repo / ".agent_bus" / "meta" / "post_merge_routing.json"
    candidates = []
    if routing_path.exists():
        record = json.loads(routing_path.read_text(encoding="utf-8"))
        candidates = [
            c for c in record.get("next_candidates", []) if c.get("candidate") == wave_id
        ]
    return len(packets), len(notes), len(candidates)


def _write_bridge_config(repo, agents):
    path = ec.bridge_config_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"agents": agents}, indent=2) + "\n", encoding="utf-8")
    return path


def _authority_allowlist(config):
    return [
        "TASKS.md",
        config.tracked_packet,
        _authority_indicator_ref(config),
        "mu/tools/executors/candidate_authority.py",
    ]


def _authority_indicator_ref(config):
    return f"reports/l4_wave_indicators/{config.wave_id}.json"


def _authority_indicator_command(config):
    indicator_ref = _authority_indicator_ref(config)
    return (
        "python3 tools/metrics/collect_l4_wave_indicators.py "
        f"--wave-id {config.wave_id} --output {indicator_ref}"
    )


def _write_fake_indicator_collector(repo):
    collector = repo / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    collector.parent.mkdir(parents=True, exist_ok=True)
    collector.write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser(); p.add_argument('--wave-id', required=True); "
        "p.add_argument('--output', required=True); a=p.parse_args()\n"
        "out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)\n"
        "out.write_text(json.dumps({'wave_id': a.wave_id}, sort_keys=True)+'\\n')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "--", str(collector.relative_to(repo))], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "collector"], cwd=repo, check=True)
    return collector


def _head_sha(repo):
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
    ).strip()


def _clone_repo(repo, target):
    subprocess.run(["git", "clone", "-q", str(repo), str(target)], check=True)
    assert _head_sha(repo) == _head_sha(target)
    return target


def _authority_config_for_repo(repo):
    probe = make_config()
    return make_config(
        indicator_artifact_ref=_authority_indicator_ref(probe),
        indicator_collection_command=_authority_indicator_command(probe),
        comparison_commit=_head_sha(repo),
        candidate_allowlist=_authority_allowlist(probe),
        pre_review_authority=True,
    )


def _post_commit_authority_config_for_repo(repo):
    """Build the exact candidate-authority config required for R4 re-entry."""
    probe = make_config(
        implementer_agent="codex",
        reviewer_agent="codex",
        pager_route="codex",
        request_for_agent="Implement the bounded continuation consumer.",
        request_for_claude=(
            "Deprecated compatibility input must not become route authority."
        ),
    )
    return dataclasses.replace(
        probe,
        indicator_artifact_ref=_authority_indicator_ref(probe),
        indicator_collection_command=_authority_indicator_command(probe),
        comparison_commit=_head_sha(repo),
        candidate_allowlist=_authority_allowlist(probe),
        pre_review_authority=True,
    )


def _expanded_post_commit_packet_content(config):
    """Model the exact config-bound packet after Phase A locks it."""
    return _phase_b_packet_content(config)


def _prepare_post_commit_resume_state(
    repo,
    config,
    *,
    bus_dir=".agent_bus-post-commit",
    detached_launch=False,
):
    """Produce an exact committed Phase B handoff + continuation fixture."""
    target_branch = f"jabramsja/{config.wave_id}"
    if detached_launch:
        _git(repo, "checkout", "-q", "--detach", config.comparison_commit)
    else:
        _git(repo, "checkout", "-q", "-b", target_branch)

    lw.run_wave_setup(repo, config, bus_dir=bus_dir)
    routing_path = ec.routing_record_path(repo, bus_dir)
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    assert routing["head_sha"] == config.comparison_commit
    assert routing["merge_sha"] == config.comparison_commit
    assert routing["blocker_report_paths"] == []

    target_authority = routing["candidate_authority"].get(
        "target_branch_authority"
    )
    if detached_launch:
        assert target_authority is None
        _git(repo, "switch", "-q", "-c", target_branch)
    else:
        assert target_authority == {
            "source": "launch_current_branch",
            "branch_prefix": "jabramsja",
            "target_branch": target_branch,
        }

    packet_path = repo / config.tracked_packet
    packet_path.write_text(
        _expanded_post_commit_packet_content(config),
        encoding="utf-8",
    )
    _git(repo, "add", "--", "TASKS.md", config.tracked_packet)
    _git(repo, "commit", "-q", "-m", "phase b candidate")
    commit_sha = _head_sha(repo)

    tracker_note = _tracker_note_line(
        (repo / "TASKS.md").read_text(encoding="utf-8"),
        config.wave_id,
    )
    handoff, errors = ce.build_commit_handoff(
        wave_id=config.wave_id,
        task_id=config.task_id,
        files_to_stage=["TASKS.md", config.tracked_packet],
        commit_message="Phase B continuation candidate",
        fixes_implemented=["Implemented the bounded continuation candidate"],
        wave_class=config.wave_class,
        target_gate_id=config.target_gate_id,
        caller="phase_b",
        target_branch=target_branch,
        tracker_note_text=tracker_note,
        tracked_packet=config.tracked_packet,
        pager_route=config.pager_route or None,
        repo_root=repo,
        bus_dir=bus_dir,
    )
    assert errors == []
    assert handoff["target_branch"] == target_branch

    handoff_path = ec.agent_bus_path(
        repo,
        bus_dir,
        "executors",
        "phase_b_handoff.json",
    )
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    continuation_path = ec.agent_bus_path(
        repo,
        bus_dir,
        "executors",
        f"commit_executor_{config.wave_id}.json",
    )
    continuation_path.write_text(
        json.dumps(
            {
                "version": ce.COMMIT_CONTINUATION_VERSION,
                "status": ce.CONTINUATION_ACTIVE_STATUS,
                "handoff_sha": _canonical_handoff_sha_for_test(handoff),
                "target_branch": target_branch,
                "commit_sha": commit_sha,
                "receipt_decision": "COMMIT_GO",
                "steps_completed": ["validate_inputs", "git_commit"],
                "updated_at_unix": 1,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sentinel_path = repo / bus_dir / "sentinel" / "preexisting.bin"
    sentinel_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel_path.write_bytes(b"pre-existing-bus-artifact\x00\xff")

    fresh, freshness_detail = ed.validate_routing_record_freshness(routing, repo)
    assert fresh is False
    assert freshness_detail.startswith("Routing record is stale:")
    return {
        "target_branch": target_branch,
        "routing_path": routing_path,
        "handoff_path": handoff_path,
        "continuation_path": continuation_path,
        "candidate_spec_path": Path(routing["candidate_authority"]["spec_path"]),
        "launch_target_authority_present": target_authority is not None,
    }


def _post_commit_resume_snapshot(repo, bus_dir):
    """Capture every tracked byte and every pre-existing bus artifact."""
    tracked_raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    tracked_paths = [
        item.decode("utf-8", "surrogateescape")
        for item in tracked_raw.split(b"\0")
        if item
    ]
    tracked_files = {
        rel_path: (
            (repo / rel_path).read_bytes()
            if (repo / rel_path).is_file()
            else None
        )
        for rel_path in tracked_paths
    }
    bus_path = repo / bus_dir
    bus_files = (
        {
            path.relative_to(repo).as_posix(): path.read_bytes()
            for path in sorted(bus_path.rglob("*"))
            if path.is_file()
        }
        if bus_path.exists()
        else {}
    )
    return {
        "tracked_files": tracked_files,
        "bus_files": bus_files,
        "index": subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout,
        "status": subprocess.run(
            ["git", "status", "--porcelain=v1", "-z"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout,
        "head": _head_sha(repo),
        "branch": subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    }


def _forbid_post_commit_resume_setup(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("post-commit continuation must not invoke setup")

    for name in (
        "setup_packet",
        "setup_tracker_note",
        "setup_routing_record",
        "setup_candidate_authority_spec",
        "setup_bridge_config",
        "setup_bridge_max_turns_override",
        "prestage_l4_indicator",
    ):
        monkeypatch.setattr(lw, name, forbidden)


def _run_post_commit_resume(repo, config, state, monkeypatch, *, bus_dir):
    """Run the public launcher and prove its unchanged command resumes commit-only."""
    fake_executor_dir = repo.parent / f"{repo.name}-fake-commit-executor"
    fake_executor_dir.mkdir(parents=True, exist_ok=True)
    (fake_executor_dir / "commit_executor.py").write_text(
        "import json\n"
        "import sys\n"
        'print(json.dumps({"status": "success", "argv": sys.argv[1:]}))\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ed, "SCRIPT_DIR", fake_executor_dir)

    before = _post_commit_resume_snapshot(repo, bus_dir)
    commit_only_dispatches = []
    _forbid_post_commit_resume_setup(monkeypatch)

    class Result:
        returncode = 0

    def runner(cmd, **kwargs):
        assert _post_commit_resume_snapshot(repo, bus_dir) == before
        assert kwargs["cwd"] == str(repo)
        assert cmd == lw.build_dispatch_command(repo, config, bus_dir=bus_dir)
        routing = json.loads(state["routing_path"].read_text(encoding="utf-8"))
        dispatch_result = ed.dispatch(
            routing,
            config=ec.DEFAULT_EXECUTOR_CONFIG,
            repo_root=repo,
            routing_record_path=state["routing_path"],
            bus_dir=bus_dir,
        )
        commit_payload = json.loads(dispatch_result["stdout"])
        commit_only_dispatches.append(commit_payload)
        assert dispatch_result["status"] == "success"
        assert dispatch_result["executor"] == "commit_executor"
        assert dispatch_result["chained_from"] == "retry_commit_only"
        assert commit_payload["status"] == "success"
        assert commit_payload["argv"] == [
            "--json",
            "--handoff",
            str(state["handoff_path"]),
            "--bus-dir",
            bus_dir,
        ]
        return Result()

    result = lw.run_wave_setup(
        repo,
        config,
        launch=True,
        runner=runner,
        bus_dir=bus_dir,
    )

    assert len(commit_only_dispatches) == 1
    assert result.launch["launched"] is True
    assert result.tracker_note_written is False
    assert result.routing_record_path == str(state["routing_path"])
    assert result.candidate_authority_spec_path == str(
        state["candidate_spec_path"]
    )
    assert _post_commit_resume_snapshot(repo, bus_dir) == before
    return result


def _rewrite_json(path, mutate):
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sync_continuation_handoff_digest(state):
    handoff = json.loads(state["handoff_path"].read_text(encoding="utf-8"))
    digest = _canonical_handoff_sha_for_test(handoff)
    _rewrite_json(
        state["continuation_path"],
        lambda payload: payload.__setitem__("handoff_sha", digest),
    )


def _mutate_post_commit_resume_proof(
    repo,
    config,
    state,
    case,
    *,
    bus_dir,
):
    routing_path = state["routing_path"]
    handoff_path = state["handoff_path"]
    continuation_path = state["continuation_path"]
    proposed = config

    if case == "native_config_mismatch":
        proposed = dataclasses.replace(
            config,
            work_items=["Changed same-wave native contract"],
        )
    elif case == "launch_override_version":
        _rewrite_json(
            routing_path,
            lambda payload: payload[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY].__setitem__(
                "version", 2
            ),
        )
    elif case == "route_head_mismatch":
        _rewrite_json(
            routing_path,
            lambda payload: payload.__setitem__("head_sha", "0" * 40),
        )
    elif case == "route_merge_mismatch":
        _rewrite_json(
            routing_path,
            lambda payload: payload.__setitem__("merge_sha", "0" * 40),
        )
    elif case == "route_blockers_nonempty":
        _rewrite_json(
            routing_path,
            lambda payload: payload.__setitem__(
                "blocker_report_paths",
                ["reports/deferred/blocking/foreign.md"],
            ),
        )
    elif case == "route_missing":
        routing_path.unlink()
    elif case == "candidate_identity_mismatch":
        _rewrite_json(
            routing_path,
            lambda payload: payload["candidate_authority"]["spec_identity"].__setitem__(
                "spec_hash", "0" * 64
            ),
        )
    elif case == "candidate_spec_mismatch":
        _rewrite_json(
            state["candidate_spec_path"],
            lambda payload: payload.__setitem__("reviewer_agent", "claude"),
        )
    elif case == "candidate_spec_missing":
        state["candidate_spec_path"].unlink()
    elif case == "receipt_non_string":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__(
                "receipt_decision", ["COMMIT_GO"]
            ),
        )
    elif case == "receipt_non_go":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__("receipt_decision", "NO_GO"),
        )
    elif case == "handoff_digest_missing":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.pop("handoff_sha"),
        )
    elif case == "handoff_digest_mismatch":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__("handoff_sha", "0" * 64),
        )
    elif case == "handoff_target_missing":
        _rewrite_json(
            handoff_path,
            lambda payload: payload.pop("target_branch"),
        )
        _sync_continuation_handoff_digest(state)
    elif case == "handoff_target_mismatch":
        _rewrite_json(
            handoff_path,
            lambda payload: payload.__setitem__(
                "target_branch", f"{state['target_branch']}-restart"
            ),
        )
        _sync_continuation_handoff_digest(state)
    elif case == "continuation_wave_mismatch":
        foreign_path = ec.agent_bus_path(
            repo,
            bus_dir,
            "executors",
            "commit_executor_foreign-wave.json",
        )
        continuation_path.rename(foreign_path)
    elif case == "continuation_commit_mismatch":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__("commit_sha", "0" * 40),
        )
    elif case == "continuation_no_forward_commit":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__("commit_sha", config.comparison_commit),
        )
    elif case == "continuation_branch_mismatch":
        _rewrite_json(
            continuation_path,
            lambda payload: payload.__setitem__(
                "target_branch", f"{state['target_branch']}-restart"
            ),
        )
    elif case == "current_branch_mismatch":
        _git(repo, "checkout", "-q", "-b", "jabramsja/foreign-current-branch")
    elif case == "current_head_mismatch":
        _git(repo, "commit", "--allow-empty", "-q", "-m", "later local commit")
    elif case == "current_head_rewound_to_comparison":
        _git(repo, "checkout", "-q", "--detach", config.comparison_commit)
    elif case == "nonancestor_commit":
        pass
    elif case == "route_fresh":
        current_state_sha = compute_repo_state(repo).state_sha
        _rewrite_json(
            routing_path,
            lambda payload: payload.__setitem__("state_sha", current_state_sha),
        )
    elif case == "route_indeterminate":
        _rewrite_json(
            routing_path,
            lambda payload: payload.__setitem__("state_sha", ["stale-shaped"]),
        )
    elif case == "launch_target_mismatch":
        _rewrite_json(
            routing_path,
            lambda payload: payload["candidate_authority"][
                "target_branch_authority"
            ].__setitem__(
                "target_branch", f"{state['target_branch']}-restart"
            ),
        )
    elif case == "dispatcher_not_ready":
        pass
    else:
        raise AssertionError(f"unknown post-commit proof mutation: {case}")
    return proposed


def _assert_post_commit_resume_refused(
    repo,
    config,
    monkeypatch,
    *,
    bus_dir,
):
    """Require the existing immutable-contract refusal before every producer."""
    before = _post_commit_resume_snapshot(repo, bus_dir)
    dispatch_calls = []
    _forbid_post_commit_resume_setup(monkeypatch)

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("invalid continuation proof must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(
            repo,
            config,
            launch=True,
            runner=runner,
            bus_dir=bus_dir,
        )

    assert dispatch_calls == []
    assert _post_commit_resume_snapshot(repo, bus_dir) == before


def _assert_no_setup_artifacts(repo, config, *, bus_dir=".agent_bus"):
    assert not (repo / config.tracked_packet).exists()
    assert config.wave_id not in (repo / "TASKS.md").read_text(encoding="utf-8")
    assert not (repo / bus_dir).exists()


def _phase_b_locked_implementing_packet_content(config, *, clarification=False):
    """Render the one narrow post-Phase-A packet accepted for R4 re-entry."""
    content = lw.render_wave_packet(config).replace(
        "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)",
        "Status: Phase B (locked, implementing)",
        1,
    ).replace(
        "Phase-A-Lock: UNLOCKED",
        "Phase-A-Lock: LOCKED",
        1,
    )
    if clarification:
        content += (
            "\n## Non-normative review clarification\n\n"
            "This optional section carries no machine or scope authority.\n"
        )
    content += (
        "\n<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
        "## Phase B Indicator Scope Reconciliation\n\n"
        f"- Refresh wave: `{config.wave_id}`\n"
        f"- Active packet: `{config.tracked_packet}`\n"
        f"- Indicator artifact: `{config.indicator_artifact_ref}`\n"
        "- Purpose: Phase B mechanically collected and staged this same-wave "
        "L4 indicator before review.\n"
        "- Authorized staged files:\n"
        "  - `TASKS.md`\n"
        f"  - `{config.tracked_packet}`\n"
        f"  - `{config.indicator_artifact_ref}`\n"
        "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
    )
    return content


def _sha256_path(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _terminal_receipt_paths(repo, bus_dir):
    return (
        ec.agent_bus_path(
            repo,
            bus_dir,
            "meta",
            "launch_wave_dispatch_terminal.json",
        ),
        ec.agent_bus_path(
            repo,
            bus_dir,
            "meta",
            "launch_wave_dispatch_terminal.claimed.json",
        ),
    )


def _prepare_native_phase_b_terminal_state(
    repo,
    *,
    bus_dir=".agent_bus-phase-b-terminal",
    returncode=73,
    clarification=False,
    mutate_before_return=None,
):
    """Run one fake completed dispatcher failure and return its exact authority."""
    _write_fake_indicator_collector(repo)
    config = _post_commit_authority_config_for_repo(repo)
    available_path, claimed_path = _terminal_receipt_paths(repo, bus_dir)
    observed = {"commands": [], "receipt_visible_before_return": None}

    def runner(cmd, **kwargs):
        observed["commands"].append((cmd, kwargs))
        observed["receipt_visible_before_return"] = (
            available_path.exists(),
            claimed_path.exists(),
        )
        packet_path = repo / config.tracked_packet
        packet_path.write_text(
            _phase_b_locked_implementing_packet_content(
                config,
                clarification=clarification,
            ),
            encoding="utf-8",
        )
        _git(repo, "add", "--", "TASKS.md", config.tracked_packet)
        assert packet_path.read_bytes() == subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=repo,
        )
        if mutate_before_return is not None:
            mutate_before_return(repo, config, bus_dir)
        return subprocess.CompletedProcess(cmd, returncode)

    with pytest.raises(lw.LaunchWaveError, match="dispatcher launch failed"):
        lw.run_wave_setup(
            repo,
            config,
            launch=True,
            runner=runner,
            bus_dir=bus_dir,
        )

    routing_path = ec.routing_record_path(repo, bus_dir)
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    spec_path = Path(routing["candidate_authority"]["spec_path"])
    return {
        "config": config,
        "bus_dir": bus_dir,
        "available_path": available_path,
        "claimed_path": claimed_path,
        "routing_path": routing_path,
        "spec_path": spec_path,
        "packet_path": repo / config.tracked_packet,
        "tasks_path": repo / "TASKS.md",
        "indicator_path": repo / config.indicator_artifact_ref,
        "observed": observed,
    }


def _phase_b_resume_authority_snapshot(repo, state):
    """Capture immutable candidate bytes at the Phase B dispatcher boundary."""
    config = state["config"]

    def optional_bytes(path):
        path = Path(path)
        return path.read_bytes() if path.is_file() else None

    def index_bytes(rel_path):
        result = subprocess.run(
            ["git", "show", f":{rel_path}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    return {
        "packet": optional_bytes(state["packet_path"]),
        "packet_index": index_bytes(config.tracked_packet),
        "tasks": optional_bytes(state["tasks_path"]),
        "tasks_index": index_bytes("TASKS.md"),
        "routing": optional_bytes(state["routing_path"]),
        "candidate_spec": optional_bytes(state["spec_path"]),
        "indicator": optional_bytes(state["indicator_path"]),
        "indicator_index": index_bytes(config.indicator_artifact_ref),
        "index": subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout,
    }


def _forbid_phase_b_resume_producers(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Phase B continuation must not rerun tracked producers")

    for name in (
        "setup_packet",
        "setup_tracker_note",
        "setup_routing_record",
        "setup_candidate_authority_spec",
        "prestage_l4_indicator",
    ):
        monkeypatch.setattr(lw, name, forbidden)


def _write_phase_b_resume_bridge(repo, bus_dir, *, agents=None, **extra):
    path = ec.bridge_config_path(repo, bus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "agents": agents
        if agents is not None
        else {
            "sentinel": {
                "cmd": ["python3", "sentinel_agent.py"],
                "display_name": "Sentinel",
                "mode": "live",
                "prompt_via_stdin": True,
                "timeout_s": 17,
                "env": {"KEEP": "yes"},
                "unknown_agent_field": {"keep": True},
            }
        },
        "unknown_top_level": {"keep": True},
        **extra,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _rewrite_terminal_receipt_packet_hashes(state):
    _rewrite_json(
        state["available_path"],
        lambda payload: payload.update(
            {
                "packet_worktree_sha256": _sha256_path(state["packet_path"]),
                "packet_index_sha256": hashlib.sha256(
                    subprocess.check_output(
                        ["git", "show", f":{state['config'].tracked_packet}"],
                        cwd=state["packet_path"].parents[2],
                    )
                ).hexdigest(),
            }
        ),
    )


# --------------------------------------------------------------------------- #
# Launcher source / target Git common-dir guard                               #
# --------------------------------------------------------------------------- #


def test_launcher_common_dir_guard_accepts_canonical_target(wave_repo):
    config = make_config()

    result = lw.run_wave_setup(wave_repo, config)

    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert (wave_repo / config.tracked_packet).is_file()


def test_launcher_common_dir_guard_accepts_registered_linked_worktree(wave_repo):
    linked = wave_repo.parent / f"{wave_repo.name}-linked"
    _git(wave_repo, "worktree", "add", "-q", "--detach", str(linked), "HEAD")
    config = make_config()

    result = lw.run_wave_setup(linked, config)

    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert (linked / config.tracked_packet).is_file()


def test_launcher_common_dir_guard_rejects_identical_head_standalone_clone(wave_repo):
    clone = _clone_repo(wave_repo, wave_repo.parent / f"{wave_repo.name}-clone")
    config = make_config()

    with pytest.raises(lw.LaunchWaveError, match="exact resolved Git common directory"):
        lw.run_wave_setup(clone, config)

    _assert_no_setup_artifacts(clone, config)


def test_launcher_common_dir_guard_scrubs_inherited_git_repository_env(
    wave_repo,
    monkeypatch,
):
    clone = _clone_repo(wave_repo, wave_repo.parent / f"{wave_repo.name}-clone")
    for key in ("GIT_DIR", "GIT_COMMON_DIR"):
        monkeypatch.setenv(key, str(wave_repo / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(wave_repo))
    seen_probe_envs = []
    real_run = subprocess.run

    def run_spy(cmd, *args, **kwargs):
        if list(cmd) == ["git", "rev-parse", "--git-common-dir"]:
            seen_probe_envs.append(dict(kwargs.get("env") or {}))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lw.subprocess, "run", run_spy)
    config = make_config()

    with pytest.raises(lw.LaunchWaveError, match="exact resolved Git common directory"):
        lw.run_wave_setup(clone, config)

    assert len(seen_probe_envs) == 2
    for env in seen_probe_envs:
        assert "GIT_DIR" not in env
        assert "GIT_COMMON_DIR" not in env
        assert "GIT_WORK_TREE" not in env
    _assert_no_setup_artifacts(clone, config)


def test_launcher_common_dir_guard_rejects_source_probe_failure(wave_repo, monkeypatch):
    bad_source = wave_repo.parent / f"{wave_repo.name}-not-a-source-repo"
    bad_source.mkdir()
    monkeypatch.setattr(lw, "SCRIPT_DIR", bad_source)
    config = make_config()

    with pytest.raises(lw.LaunchWaveError, match="launcher source Git common-dir"):
        lw.run_wave_setup(wave_repo, config)

    _assert_no_setup_artifacts(wave_repo, config)


def test_launcher_common_dir_guard_rejects_target_probe_failure(wave_repo):
    bad_target = wave_repo.parent / f"{wave_repo.name}-not-a-target-repo"
    bad_target.mkdir()

    with pytest.raises(lw.LaunchWaveError, match="target repo_root Git common-dir"):
        lw.run_wave_setup(bad_target, make_config())

    assert not (bad_target / "reports").exists()
    assert not (bad_target / ".agent_bus").exists()


def test_launcher_common_dir_guard_rejects_malformed_probe_output(
    wave_repo,
    monkeypatch,
):
    real_run = subprocess.run

    class _Malformed:
        returncode = 0
        stdout = ".git\nextra\n"
        stderr = ""

    def malformed_run(cmd, *args, **kwargs):
        if list(cmd) == ["git", "rev-parse", "--git-common-dir"]:
            return _Malformed()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lw.subprocess, "run", malformed_run)
    config = make_config()

    with pytest.raises(lw.LaunchWaveError, match="malformed output"):
        lw.run_wave_setup(wave_repo, config)

    _assert_no_setup_artifacts(wave_repo, config)


def test_launcher_common_dir_guard_rejects_timed_out_probe(wave_repo, monkeypatch):
    real_run = subprocess.run

    def timeout_run(cmd, *args, **kwargs):
        if list(cmd) == ["git", "rev-parse", "--git-common-dir"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lw.subprocess, "run", timeout_run)
    config = make_config()

    with pytest.raises(lw.LaunchWaveError, match="timed out"):
        lw.run_wave_setup(wave_repo, config)

    _assert_no_setup_artifacts(wave_repo, config)


def test_run_wave_setup_repo_identity_failure_precedes_mutation_and_dispatch(
    wave_repo,
):
    clone = _clone_repo(wave_repo, wave_repo.parent / f"{wave_repo.name}-clone")
    config = make_config()
    runner_called = False

    class _R:
        returncode = 0

    def runner(cmd, **kwargs):
        nonlocal runner_called
        runner_called = True
        return _R()

    with pytest.raises(lw.LaunchWaveError, match="exact resolved Git common directory"):
        lw.run_wave_setup(
            clone,
            config,
            launch=True,
            bus_dir=".agent_bus-identity",
            runner=runner,
        )

    assert runner_called is False
    _assert_no_setup_artifacts(clone, config, bus_dir=".agent_bus-identity")


def test_prepare_review_repo_identity_failure_precedes_authority_mutation(
    wave_repo,
):
    clone = _clone_repo(wave_repo, wave_repo.parent / f"{wave_repo.name}-clone")
    config = _authority_config_for_repo(clone)

    with pytest.raises(lw.LaunchWaveError, match="exact resolved Git common directory"):
        lw.prepare_review_authority(
            clone,
            config,
            bus_dir=".agent_bus-authority",
            phase="phase_b",
            review_round="manual-recovery",
        )

    _assert_no_setup_artifacts(clone, config, bus_dir=".agent_bus-authority")


def test_repo_identity_failure_precedes_config_validation(wave_repo):
    clone = _clone_repo(wave_repo, wave_repo.parent / f"{wave_repo.name}-clone")
    invalid_config = make_config(title="Bad *Title*")

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(clone, invalid_config)

    assert "exact resolved Git common directory" in str(exc.value)
    assert "invalid wave-config" not in str(exc.value)
    _assert_no_setup_artifacts(clone, invalid_config)


# --------------------------------------------------------------------------- #
# Sequential setup                                                            #
# --------------------------------------------------------------------------- #


def test_full_sequential_setup_produces_all_artifacts(wave_repo):
    config = make_config()
    result = lw.run_wave_setup(wave_repo, config)

    packet = wave_repo / config.tracked_packet
    assert packet.is_file()
    assert result.tracked_packet == config.tracked_packet
    assert result.tracker_note_written is True
    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert result.launch["launched"] is False

    # One canonical copy of each artifact.
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)

    # Routing record carries the single next-candidate for this wave.
    routing = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text()
    )
    assert routing["wave_name"] == config.wave_id
    assert [c["candidate"] for c in routing["next_candidates"]] == [config.wave_id]
    assert routing["next_candidates"][0]["tracked_packet"] == config.tracked_packet
    assert "candidate_authority" not in routing
    assert "candidate_authority_required" not in routing
    assert result.candidate_authority_spec_path is None


_NATIVE_PACKET_STRUCTURED_FIELDS = (
    "scope_items",
    "work_items",
    "constraints",
    "stop_conditions",
    "acceptance_criteria",
)


@pytest.mark.parametrize("field_name", _NATIVE_PACKET_STRUCTURED_FIELDS)
@pytest.mark.parametrize(
    ("input_kind", "bad_value"),
    (
        pytest.param("missing", None, id="missing"),
        pytest.param("empty", [], id="empty"),
        pytest.param("malformed", "not-a-list", id="malformed"),
        pytest.param("blank-item", ["valid item", " \t "], id="blank-item"),
    ),
)
def test_native_stub_packet_contract_refuses_incomplete_sections_before_mutation(
    wave_repo,
    field_name,
    input_kind,
    bad_value,
):
    """Every native structured section fails before any launcher-owned mutation."""
    probe = make_config()
    _write_indicator_generator(wave_repo)
    indicator_command = (
        f"{sys.executable} gen_indicator.py {probe.indicator_artifact_ref}"
    )
    if input_kind == "missing":
        config_data = dataclasses.asdict(
            make_config(indicator_collection_command=indicator_command)
        )
        config_data.pop(field_name)
        config = lw.WaveConfig.from_dict(config_data)
    else:
        config = make_config(
            indicator_collection_command=indicator_command,
            **{field_name: bad_value},
        )

    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    routing_path.write_text('{"sentinel": "routing-before"}\n', encoding="utf-8")
    bridge_path = _write_bridge_config(
        wave_repo,
        {"sentinel": {"cmd": ["python3", "sentinel_agent.py"]}},
    )
    indicator_path = wave_repo / config.indicator_artifact_ref
    indicator_path.parent.mkdir(parents=True, exist_ok=True)
    indicator_path.write_text("indicator-before\n", encoding="utf-8")

    before = {
        "tasks": tasks_path.read_bytes(),
        "routing": routing_path.read_bytes(),
        "bridge": bridge_path.read_bytes(),
        "indicator": indicator_path.read_bytes(),
        "staged": _staged_paths(wave_repo),
    }
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("invalid native packet config must not dispatch")

    with pytest.raises(lw.LaunchWaveError) as excinfo:
        lw.run_wave_setup(wave_repo, config, launch=True, runner=runner)

    assert field_name in str(excinfo.value)
    assert not (wave_repo / config.tracked_packet).exists()
    assert tasks_path.read_bytes() == before["tasks"]
    assert routing_path.read_bytes() == before["routing"]
    assert bridge_path.read_bytes() == before["bridge"]
    assert indicator_path.read_bytes() == before["indicator"]
    assert _staged_paths(wave_repo) == before["staged"]
    assert dispatch_calls == []


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        pytest.param("evidence_command", "", id="blank-evidence-command"),
        pytest.param(
            "evidence_command",
            "python3 -m pytest first.py\npython3 -m pytest second.py",
            id="multiline-evidence-command",
        ),
        pytest.param("slow_functions", "run_mu", id="non-list-slow-functions"),
        pytest.param(
            "slow_functions",
            ["run_mu", "  "],
            id="blank-slow-function",
        ),
        pytest.param(
            "slow_functions",
            ["run_mu", "walk_mu\nrewrite_mu"],
            id="multiline-slow-function",
        ),
    ],
)
def test_native_stub_packet_contract_refuses_invalid_validation_before_mutation(
    wave_repo,
    field_name,
    bad_value,
):
    config = make_config(**{field_name: bad_value})
    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)

    with pytest.raises(lw.LaunchWaveError, match=field_name):
        lw.run_wave_setup(wave_repo, config)

    assert tasks_path.read_bytes() == before_tasks
    assert not (wave_repo / config.tracked_packet).exists()
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged


def test_native_stub_packet_contract_rejects_dispatch_truncated_stem_before_mutation(
    wave_repo,
):
    config = make_config(wave_id="w" * 70)
    tracked_packet_stem = Path(config.tracked_packet).stem
    assert len(tracked_packet_stem) == 81

    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("invalid native packet stem must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="tracked_packet stem must remain exact through normal Phase A dispatch",
    ):
        lw.run_wave_setup(wave_repo, config, launch=True, runner=runner)

    assert tasks_path.read_bytes() == before_tasks
    assert not (wave_repo / config.tracked_packet).exists()
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged
    assert dispatch_calls == []


@pytest.mark.parametrize("setup_helper", ["tracker", "routing"])
def test_native_stub_packet_contract_direct_helpers_reject_incomplete_input_before_mutation(
    wave_repo,
    setup_helper,
):
    config = make_config(evidence_command="")
    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)

    with pytest.raises(lw.LaunchWaveError, match="evidence_command"):
        if setup_helper == "tracker":
            lw.setup_tracker_note(wave_repo, config)
        else:
            lw.setup_routing_record(wave_repo, config)

    assert tasks_path.read_bytes() == before_tasks
    assert not (wave_repo / config.tracked_packet).exists()
    assert not ec.routing_record_path(wave_repo).exists()
    assert _staged_paths(wave_repo) == before_staged


def test_native_stub_packet_contract_refuses_unbound_authorization_before_mutation(
    wave_repo,
):
    config = make_config(
        authorization_note=(
            "The acceptance criteria may be superseded during this attempt."
        )
    )
    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("unbound native authorization must not dispatch")

    with pytest.raises(lw.LaunchWaveError, match="authorization_note"):
        lw.run_wave_setup(wave_repo, config, launch=True, runner=runner)

    assert tasks_path.read_bytes() == before_tasks
    assert not (wave_repo / config.tracked_packet).exists()
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged
    assert dispatch_calls == []


def test_native_stub_packet_contract_routing_marker_and_digest_binding(wave_repo):
    config = make_config()
    lw.setup_packet(wave_repo, config)

    record = lw.setup_routing_record(wave_repo, config)
    envelope = record[lw.NATIVE_STUB_PACKET_CONTRACT_KEY]
    launch_authority = record[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY]
    contract = envelope["contract"]

    assert lw.NATIVE_STUB_PACKET_CONTRACT_KEY == "native_stub_packet_contract"
    assert set(envelope) == {"required", "producer", "version", "digest", "contract"}
    assert envelope["required"] is True
    assert envelope["producer"] == "launch_wave.py"
    assert isinstance(envelope["version"], int)
    assert not isinstance(envelope["version"], bool)
    assert envelope["version"] == 1
    assert re.fullmatch(r"[0-9a-f]{64}", envelope["digest"])
    assert contract == {
        "identity": {
            "wave_id": config.wave_id,
            "task_id": config.task_id,
            "title": config.title,
            "date": config.date,
            "tracked_packet": config.tracked_packet,
        },
        "purpose": config.purpose,
        "scope_summary": config.scope_summary,
        "scope_items": config.scope_items,
        "work_items": config.work_items,
        "constraints": config.constraints,
        "stop_conditions": config.stop_conditions,
        "acceptance_criteria": config.acceptance_criteria,
        "evidence_command": config.evidence_command,
        "slow_functions": config.slow_functions,
    }
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    assert envelope["digest"] == hashlib.sha256(canonical).hexdigest()
    assert envelope == lw.build_native_stub_packet_contract(config)
    assert lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY == (
        "launch_wave_override_authority"
    )
    assert set(launch_authority) == {
        "version",
        "implementer_agent",
        "reviewer_agent",
        "pager_route",
        "max_turns",
    }
    assert launch_authority == {
        "version": 1,
        "implementer_agent": "",
        "reviewer_agent": "",
        "pager_route": "",
        "max_turns": None,
    }
    assert type(launch_authority["version"]) is int
    assert launch_authority == lw.build_launch_wave_override_authority(config)

    on_disk = json.loads(
        ec.routing_record_path(wave_repo).read_text(encoding="utf-8")
    )
    assert on_disk[lw.NATIVE_STUB_PACKET_CONTRACT_KEY] == envelope
    assert on_disk[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY] == launch_authority
    assert on_disk["wave_name"] == contract["identity"]["wave_id"]
    assert on_disk["task_id"] == contract["identity"]["task_id"]
    assert on_disk["next_candidates"][0]["tracked_packet"] == contract["identity"][
        "tracked_packet"
    ]
    packet = (wave_repo / config.tracked_packet).read_text(encoding="utf-8")
    digest_line = (
        lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX + envelope["digest"]
    )
    assert packet.count(lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE) == 1
    assert packet.count(digest_line) == 1
    assert config.tracked_packet == (
        f"reports/control_plane/{config.wave_id}_{config.date}.md"
    )


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        ("implementer_agent", "codex"),
        ("reviewer_agent", "codex"),
        ("pager_route", "codex"),
        ("max_turns", 73),
    ],
)
def test_native_launch_override_authority_changes_deterministically_on_fresh_routes(
    wave_repo,
    field_name,
    changed_value,
):
    config = make_config()
    lw.setup_packet(wave_repo, config)
    changed = dataclasses.replace(config, **{field_name: changed_value})
    expected = lw.build_launch_wave_override_authority(changed)

    first_bus = f".agent_bus-{field_name}-first"
    second_bus = f".agent_bus-{field_name}-second"
    first_record = lw.setup_routing_record(wave_repo, changed, bus_dir=first_bus)
    second_record = lw.setup_routing_record(wave_repo, changed, bus_dir=second_bus)
    first_authority = first_record[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY]
    second_authority = second_record[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY]
    def canonical_bytes(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    assert canonical_bytes(first_authority) == canonical_bytes(expected)
    assert canonical_bytes(second_authority) == canonical_bytes(expected)
    assert canonical_bytes(first_authority) != canonical_bytes(
        lw.build_launch_wave_override_authority(config)
    )
    assert json.loads(
        ec.routing_record_path(wave_repo, first_bus).read_text(encoding="utf-8")
    )[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY] == expected
    assert json.loads(
        ec.routing_record_path(wave_repo, second_bus).read_text(encoding="utf-8")
    )[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY] == expected


@pytest.mark.parametrize(
    ("field_name", "changed_value"),
    [
        (None, None),
        ("implementer_agent", "codex"),
        ("reviewer_agent", "codex"),
        ("pager_route", "codex"),
        ("max_turns", 73),
    ],
)
def test_native_launch_override_authority_rejects_pre_field_or_changed_route(
    wave_repo,
    field_name,
    changed_value,
):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    routing_path = ec.routing_record_path(wave_repo)
    routing = lw.setup_routing_record(wave_repo, config)

    proposed = config
    if field_name is None:
        assert routing.pop(lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY) == (
            lw.build_launch_wave_override_authority(config)
        )
        routing_path.write_text(
            json.dumps(routing, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    else:
        proposed = dataclasses.replace(config, **{field_name: changed_value})

    tasks_path = wave_repo / "TASKS.md"
    before = {
        "packet": packet_path.read_bytes(),
        "tasks": tasks_path.read_bytes(),
        "routing": routing_path.read_bytes(),
        "staged": _staged_paths(wave_repo),
    }
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("an existing same-attempt route must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ) as excinfo:
        lw.run_wave_setup(
            wave_repo,
            proposed,
            launch=True,
            runner=runner,
        )

    assert "same-wave launch override authority" in str(excinfo.value)
    assert packet_path.read_bytes() == before["packet"]
    assert tasks_path.read_bytes() == before["tasks"]
    assert routing_path.read_bytes() == before["routing"]
    assert _staged_paths(wave_repo) == before["staged"]
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert dispatch_calls == []


def test_native_locked_precommit_packet_for_historical_simple_config_still_dispatches(
    wave_repo,
):
    config = make_config()
    assert config.candidate_authority_enabled() is False
    assert config.comparison_commit == ""

    lw.run_wave_setup(wave_repo, config)
    packet_path = wave_repo / config.tracked_packet
    locked_packet = _phase_b_packet_content(config)
    packet_path.write_text(locked_packet, encoding="utf-8")
    dispatch_calls = []

    class Result:
        returncode = 0

    def runner(cmd, **_kwargs):
        dispatch_calls.append(cmd)
        return Result()

    result = lw.run_wave_setup(
        wave_repo,
        make_config(),
        launch=True,
        runner=runner,
    )

    assert dispatch_calls == [lw.build_dispatch_command(wave_repo, config)]
    assert result.launch["launched"] is True
    assert result.tracker_note_written is True
    assert result.candidate_authority_spec_path is None
    assert packet_path.read_text(encoding="utf-8") == locked_packet
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)


@pytest.mark.parametrize(
    "detached_launch",
    [False, True],
    ids=["present-launch-target-authority", "detached-launch-no-target-authority"],
)
def test_native_post_commit_relaunch_dispatches_commit_only_before_setup_mutation(
    wave_repo,
    monkeypatch,
    detached_launch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-positive"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
        detached_launch=detached_launch,
    )

    result = _run_post_commit_resume(
        wave_repo,
        config,
        state,
        monkeypatch,
        bus_dir=bus_dir,
    )

    assert state["launch_target_authority_present"] is (not detached_launch)
    assert result.launch["launch_overrides"] == {
        "implementer_agent": "codex",
        "reviewer_agent": "codex",
        "pager_route": "codex",
    }


def test_native_post_commit_failure_does_not_create_phase_b_terminal_receipt(
    wave_repo,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-no-terminal-receipt"
    _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    available, claimed = _terminal_receipt_paths(wave_repo, bus_dir)
    _forbid_post_commit_resume_setup(monkeypatch)

    with pytest.raises(lw.LaunchWaveError, match="dispatcher launch failed"):
        lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 41),
            bus_dir=bus_dir,
        )

    assert not available.exists()
    assert not claimed.exists()


@pytest.mark.parametrize(
    ("field_name", "mismatched_value"),
    [
        ("implementer_agent", "claude"),
        ("reviewer_agent", "claude"),
        ("pager_route", "claude"),
        ("max_turns", 73),
    ],
)
def test_native_post_commit_version_1_launch_override_value_mismatch_refuses_before_setup(
    wave_repo,
    monkeypatch,
    field_name,
    mismatched_value,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = f".agent_bus-post-commit-override-{field_name}"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    expected = lw.build_launch_wave_override_authority(config)
    _rewrite_json(
        state["routing_path"],
        lambda payload: payload[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY].__setitem__(
            field_name,
            mismatched_value,
        ),
    )
    actual = json.loads(state["routing_path"].read_text(encoding="utf-8"))[
        lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY
    ]

    assert actual == {**expected, field_name: mismatched_value}
    assert actual["version"] == lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_VERSION == 1
    assert actual[field_name] != expected[field_name]
    _assert_post_commit_resume_refused(
        wave_repo,
        config,
        monkeypatch,
        bus_dir=bus_dir,
    )


@pytest.mark.parametrize(
    "proof_case",
    [
        "native_config_mismatch",
        "launch_override_version",
        "route_head_mismatch",
        "route_merge_mismatch",
        "route_blockers_nonempty",
        "route_missing",
        "candidate_identity_mismatch",
        "candidate_spec_mismatch",
        "candidate_spec_missing",
        "receipt_non_string",
        "receipt_non_go",
        "handoff_digest_missing",
        "handoff_digest_mismatch",
        "handoff_target_missing",
        "handoff_target_mismatch",
        "continuation_wave_mismatch",
        "continuation_commit_mismatch",
        "continuation_no_forward_commit",
        "continuation_branch_mismatch",
        "current_branch_mismatch",
        "current_head_mismatch",
        "current_head_rewound_to_comparison",
        "nonancestor_commit",
        "route_fresh",
        "route_indeterminate",
        "launch_target_mismatch",
        "dispatcher_not_ready",
    ],
)
def test_native_post_commit_relaunch_required_authority_mismatch_refuses_before_setup(
    wave_repo,
    proof_case,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-refusal"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    proposed = _mutate_post_commit_resume_proof(
        wave_repo,
        config,
        state,
        proof_case,
        bus_dir=bus_dir,
    )
    if proof_case == "dispatcher_not_ready":
        monkeypatch.setattr(
            lw,
            "post_commit_continuation_ready_for_record",
            lambda *_args, **_kwargs: (False, "dispatcher commit-only not ready"),
        )
    elif proof_case == "continuation_no_forward_commit":
        monkeypatch.setattr(
            lw,
            "post_commit_git_authority_matches",
            lambda *_args, **_kwargs: True,
        )
    elif proof_case == "nonancestor_commit":
        real_run = subprocess.run

        class NonAncestorResult:
            returncode = 1
            stdout = ""
            stderr = ""

        def nonancestor_comparison(cmd, *args, **kwargs):
            if list(cmd) == [
                "git",
                "merge-base",
                "--is-ancestor",
                config.comparison_commit,
                "HEAD",
            ]:
                return NonAncestorResult()
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(lw.subprocess, "run", nonancestor_comparison)

    _assert_post_commit_resume_refused(
        wave_repo,
        proposed,
        monkeypatch,
        bus_dir=bus_dir,
    )


def test_native_post_commit_indeterminate_git_proof_refuses_before_setup_or_dispatch(
    wave_repo,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-git-indeterminate"
    _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    real_run = subprocess.run
    head_probe_attempts = []

    def fail_head_probe(cmd, *args, **kwargs):
        if (
            list(cmd) == ["git", "rev-parse", "HEAD"]
            and kwargs.get("capture_output") is True
            and kwargs.get("timeout") == 30
        ):
            head_probe_attempts.append(list(cmd))
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lw.subprocess, "run", fail_head_probe)

    _assert_post_commit_resume_refused(
        wave_repo,
        config,
        monkeypatch,
        bus_dir=bus_dir,
    )

    assert head_probe_attempts


def test_native_post_commit_timestamp_is_diagnostic_only_for_valid_resume(
    wave_repo,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-timestamp-valid"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
        detached_launch=True,
    )
    _rewrite_json(
        state["routing_path"],
        lambda payload: payload.__setitem__(
            "timestamp_utc", "untrusted diagnostic timestamp"
        ),
    )

    _run_post_commit_resume(
        wave_repo,
        config,
        state,
        monkeypatch,
        bus_dir=bus_dir,
    )


def test_native_post_commit_timestamp_cannot_grant_missing_continuation_authority(
    wave_repo,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-timestamp-refusal"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    _rewrite_json(
        state["routing_path"],
        lambda payload: payload.__setitem__(
            "timestamp_utc", "2099-12-31T23:59:59+00:00"
        ),
    )
    state["continuation_path"].unlink()

    _assert_post_commit_resume_refused(
        wave_repo,
        config,
        monkeypatch,
        bus_dir=bus_dir,
    )


def test_native_post_commit_arbitrary_stale_state_sha_grants_nothing_alone(
    wave_repo,
    monkeypatch,
):
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = ".agent_bus-post-commit-stale-only"
    state = _prepare_post_commit_resume_state(
        wave_repo,
        config,
        bus_dir=bus_dir,
    )
    _rewrite_json(
        state["routing_path"],
        lambda payload: payload.__setitem__("state_sha", "f" * 64),
    )
    state["candidate_spec_path"].unlink()
    state["handoff_path"].unlink()
    state["continuation_path"].unlink()

    _assert_post_commit_resume_refused(
        wave_repo,
        config,
        monkeypatch,
        bus_dir=bus_dir,
    )


def test_native_stub_packet_contract_digest_binds_exact_validation_payload():
    config = make_config(
        evidence_command="PYTHONHASHSEED=0 python3 -m pytest -k 'exact value'",
        slow_functions=["run_mu", "walk_mu"],
    )
    envelope = lw.build_native_stub_packet_contract(config)
    content = lw.render_wave_packet(config)

    changed_evidence = dataclasses.replace(
        config,
        evidence_command="PYTHONHASHSEED=0  python3 -m pytest -k 'exact value'",
    )
    reversed_slow_functions = dataclasses.replace(
        config,
        slow_functions=["walk_mu", "run_mu"],
    )
    empty_slow_functions = dataclasses.replace(config, slow_functions=[])

    assert envelope["contract"]["evidence_command"] == config.evidence_command
    assert envelope["contract"]["slow_functions"] == ["run_mu", "walk_mu"]
    assert envelope["digest"] != lw.build_native_stub_packet_contract(
        changed_evidence
    )["digest"]
    assert envelope["digest"] != lw.build_native_stub_packet_contract(
        reversed_slow_functions
    )["digest"]
    assert envelope["digest"] != lw.build_native_stub_packet_contract(
        empty_slow_functions
    )["digest"]
    assert f"- evidence_command: `{config.evidence_command}`" in content
    assert (
        "- Slow-kernel guard-tests (`run_mu`, `walk_mu`) carry an in-function "
        "`# SPEED_OK: <reason>` annotation so they stay out of the green-gate "
        "speed lane."
    ) in content
    empty_content = lw.render_wave_packet(empty_slow_functions)
    assert "Slow-kernel guard-tests" not in empty_content


def test_native_stub_packet_contract_renders_complete_canonical_packet():
    config = make_config(
        purpose="Unique native packet purpose.",
        scope_summary="Unique native packet scope summary.",
        scope_items=["scope item alpha", "scope item beta"],
        work_items=["work item alpha", "work item beta"],
        constraints=["constraint alpha", "constraint beta"],
        stop_conditions=["stop condition alpha", "stop condition beta"],
        acceptance_criteria=["acceptance alpha", "acceptance beta"],
        evidence_command="python3 -m pytest exact-evidence.py",
        slow_functions=["run_mu", "walk_mu"],
    )

    content = lw.render_wave_packet(config)

    def section_body(title):
        matches = list(
            re.finditer(
                rf"^## {re.escape(title)}\n\n(?P<body>.*?)(?=^## |\Z)",
                content,
                flags=re.MULTILINE | re.DOTALL,
            )
        )
        assert len(matches) == 1
        return matches[0].group("body").rstrip("\n")

    scope_authority = (
        "TASKS.md -- tracker-sync authority. The "
        f"{config.date} tracker sync note for wave `{config.wave_id}` is the single "
        "source of truth for this packet's L4 fields; the packet derives from it."
    )
    expected = {
        "Scope": (
            f"{config.scope_summary}\n\nFiles and surfaces in scope:\n\n"
            f"- {config.scope_items[0]}\n- {config.scope_items[1]}\n"
            f"- {scope_authority}"
        ),
        "Work items": (
            f"1. {config.work_items[0]}\n2. {config.work_items[1]}"
        ),
        "Constraints": (
            f"- {config.constraints[0]}\n- {config.constraints[1]}"
        ),
        "Stop conditions": (
            f"- {config.stop_conditions[0]}\n- {config.stop_conditions[1]}"
        ),
        "Validation gates": (
            f"- evidence_command: `{config.evidence_command}`\n"
            "- Slow-kernel guard-tests (`run_mu`, `walk_mu`) carry an in-function "
            "`# SPEED_OK: <reason>` annotation so they stay out of the green-gate "
            "speed lane."
        ),
        "Acceptance criteria": (
            f"- {config.acceptance_criteria[0]}\n"
            f"- {config.acceptance_criteria[1]}"
        ),
    }

    assert f"\nPurpose: {config.purpose}\n" in content
    envelope = lw.build_native_stub_packet_contract(config)
    assert content.count(lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE) == 1
    assert content.count(
        lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX + envelope["digest"]
    ) == 1
    for title, expected_body in expected.items():
        body = section_body(title)
        assert body
        assert body == expected_body
    for builder_owned_item in (
        config.purpose,
        config.scope_summary,
        *config.scope_items,
        *config.work_items,
        *config.constraints,
        *config.stop_conditions,
        *config.acceptance_criteria,
    ):
        assert content.count(builder_owned_item) == 1
    assert lw.check_packet_fences(content, config) == []


def test_native_stub_packet_contract_rejects_same_wave_normative_relaunch_before_mutation(
    wave_repo,
):
    """A corrected normative config must use a fresh wave id, never amend in place."""
    probe = make_config()
    _write_indicator_generator(wave_repo)
    indicator_command = (
        f"{sys.executable} gen_indicator.py {probe.indicator_artifact_ref}"
    )
    config = make_config(indicator_collection_command=indicator_command)
    bridge_path = _write_bridge_config(
        wave_repo,
        {"sentinel": {"cmd": ["python3", "sentinel_agent.py"]}},
    )

    lw.run_wave_setup(wave_repo, config)

    packet_path = wave_repo / config.tracked_packet
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    indicator_path = wave_repo / config.indicator_artifact_ref
    original_routing = json.loads(routing_path.read_text(encoding="utf-8"))
    original_envelope = original_routing[lw.NATIVE_STUB_PACKET_CONTRACT_KEY]
    before = {
        "packet": packet_path.read_bytes(),
        "tasks": tasks_path.read_bytes(),
        "routing": routing_path.read_bytes(),
        "bridge": bridge_path.read_bytes(),
        "indicator": indicator_path.read_bytes(),
        "staged": _staged_paths(wave_repo),
    }
    corrected_item = "Replace the original normative work items in place"
    corrected = make_config(
        indicator_collection_command=indicator_command,
        work_items=[corrected_item],
    )
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("same-wave corrected config must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ) as excinfo:
        lw.run_wave_setup(
            wave_repo,
            corrected,
            launch=True,
            runner=runner,
        )

    assert "fresh wave id" in str(excinfo.value)
    assert packet_path.read_bytes() == before["packet"]
    assert tasks_path.read_bytes() == before["tasks"]
    assert routing_path.read_bytes() == before["routing"]
    assert bridge_path.read_bytes() == before["bridge"]
    assert indicator_path.read_bytes() == before["indicator"]
    assert _staged_paths(wave_repo) == before["staged"]
    assert dispatch_calls == []
    packet_text = packet_path.read_text(encoding="utf-8")
    assert config.work_items[0] in packet_text
    assert corrected_item not in packet_text
    persisted_envelope = json.loads(
        routing_path.read_text(encoding="utf-8")
    )[lw.NATIVE_STUB_PACKET_CONTRACT_KEY]
    assert persisted_envelope == original_envelope


@pytest.mark.parametrize("change_normative_item", [False, True])
def test_native_stub_packet_contract_rejects_same_wave_route_downgrade_before_mutation(
    wave_repo,
    change_normative_item,
):
    """A marked native attempt cannot be downgraded by changing its route."""
    probe = make_config()
    _write_indicator_generator(wave_repo)
    indicator_command = (
        f"{sys.executable} gen_indicator.py {probe.indicator_artifact_ref}"
    )
    config = make_config(indicator_collection_command=indicator_command)
    bridge_path = _write_bridge_config(
        wave_repo,
        {"sentinel": {"cmd": ["python3", "sentinel_agent.py"]}},
    )
    lw.run_wave_setup(wave_repo, config)

    packet_path = wave_repo / config.tracked_packet
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    indicator_path = wave_repo / config.indicator_artifact_ref
    before = {
        "packet": packet_path.read_bytes(),
        "tasks": tasks_path.read_bytes(),
        "routing": routing_path.read_bytes(),
        "bridge": bridge_path.read_bytes(),
        "indicator": indicator_path.read_bytes(),
        "staged": _staged_paths(wave_repo),
    }
    changed_item = "Replace native work while downgrading the same attempt"
    downgraded = dataclasses.replace(
        config,
        routing_decision="ROUTE_PHASE_B",
        work_items=(
            [changed_item] if change_normative_item else list(config.work_items)
        ),
    )
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("same-wave native route downgrade must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.setup_packet(wave_repo, downgraded)

    assert packet_path.read_bytes() == before["packet"]
    assert routing_path.read_bytes() == before["routing"]

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(
            wave_repo,
            downgraded,
            launch=True,
            runner=runner,
        )

    assert packet_path.read_bytes() == before["packet"]
    assert tasks_path.read_bytes() == before["tasks"]
    assert routing_path.read_bytes() == before["routing"]
    assert bridge_path.read_bytes() == before["bridge"]
    assert indicator_path.read_bytes() == before["indicator"]
    assert _staged_paths(wave_repo) == before["staged"]
    assert dispatch_calls == []
    packet_text = packet_path.read_text(encoding="utf-8")
    assert config.work_items[0] in packet_text
    assert changed_item not in packet_text
    persisted_routing = json.loads(routing_path.read_text(encoding="utf-8"))
    assert persisted_routing["decision"] == "ROUTE_PHASE_A"
    assert lw.NATIVE_STUB_PACKET_CONTRACT_KEY in persisted_routing


@pytest.mark.parametrize(
    "change_case",
    [
        "route_downgrade",
        "missing_validation_metadata",
        "evidence_command",
        "slow_function_order",
        "title_identity",
        "dated_packet_identity",
    ],
)
def test_native_stub_packet_contract_rejects_packet_only_replacement_before_mutation(
    wave_repo,
    change_case,
):
    """Packet-side provenance protects an interrupted step-1-only attempt."""
    config = make_config(slow_functions=["run_mu", "walk_mu"])
    packet_path = lw.setup_packet(wave_repo, config)
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    assert not routing_path.exists()
    before = {
        "packet": packet_path.read_bytes(),
        "tasks": tasks_path.read_bytes(),
        "staged": _staged_paths(wave_repo),
    }

    if change_case == "route_downgrade":
        changed = dataclasses.replace(config, routing_decision="ROUTE_PHASE_B")
    elif change_case == "missing_validation_metadata":
        changed = dataclasses.replace(config, evidence_command="")
    elif change_case == "evidence_command":
        changed = dataclasses.replace(
            config,
            evidence_command="python3 -m pytest changed-validation.py",
        )
    elif change_case == "slow_function_order":
        changed = dataclasses.replace(
            config,
            slow_functions=["walk_mu", "run_mu"],
        )
    elif change_case == "title_identity":
        changed = dataclasses.replace(config, title="Changed Same-Wave Packet Title")
    else:
        changed = make_config(
            date="2026-06-20",
            slow_functions=list(config.slow_functions),
        )
        assert changed.tracked_packet != config.tracked_packet

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, changed)

    assert packet_path.read_bytes() == before["packet"]
    assert tasks_path.read_bytes() == before["tasks"]
    assert not routing_path.exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before["staged"]
    if changed.tracked_packet != config.tracked_packet:
        assert not (wave_repo / changed.tracked_packet).exists()


@pytest.mark.parametrize(
    "tamper_case",
    [
        "digest",
        "missing_marker",
        "malformed_marker",
        "missing_digest",
        "malformed_digest",
        "malformed_extra_digest_in_clarification",
        "malformed_marker_missing_digest_route_downgrade",
    ],
)
@pytest.mark.parametrize("packet_source", ["worktree", "index"])
def test_native_stub_packet_contract_rejects_packet_only_provenance_tamper_before_mutation(
    wave_repo,
    tamper_case,
    packet_source,
):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    envelope = lw.build_native_stub_packet_contract(config)
    packet_text = packet_path.read_text(encoding="utf-8")
    if tamper_case == "digest":
        packet_text = packet_text.replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX + envelope["digest"],
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX + ("0" * 64),
            1,
        )
    elif tamper_case == "missing_marker":
        packet_text = packet_text.replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE + "\n",
            "",
            1,
        )
    elif tamper_case == "malformed_marker":
        packet_text = packet_text.replace(
            "producer=launch_wave.py",
            "producer=other.py",
            1,
        )
    elif tamper_case == "missing_digest":
        packet_text = packet_text.replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX
            + envelope["digest"]
            + "\n",
            "",
            1,
        )
    elif tamper_case == "malformed_digest":
        packet_text = packet_text.replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX + envelope["digest"],
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX.rstrip(),
            1,
        )
    elif tamper_case == "malformed_extra_digest_in_clarification":
        packet_text += (
            "\n## Non-normative review clarification\n\n"
            "Native-Stub-Packet-Contract-Digest " + ("0" * 64) + "\n"
        )
    else:
        packet_text = packet_text.replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE,
            lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE.replace(":", "", 1),
            1,
        ).replace(
            lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX
            + envelope["digest"]
            + "\n",
            "",
            1,
        )
    packet_path.write_text(packet_text, encoding="utf-8")
    packet_bytes = packet_path.read_bytes()
    indexed_before = None
    if packet_source == "index":
        _git(wave_repo, "add", "--", config.tracked_packet)
        indexed_before = subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=wave_repo,
        )
        packet_path.unlink()
    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)

    relaunch_config = (
        dataclasses.replace(config, routing_decision="ROUTE_PHASE_B")
        if tamper_case == "malformed_marker_missing_digest_route_downgrade"
        else config
    )
    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, relaunch_config)

    if packet_source == "worktree":
        assert packet_path.read_bytes() == packet_bytes
    else:
        assert not packet_path.exists()
        assert subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=wave_repo,
        ) == indexed_before == packet_bytes
    assert tasks_path.read_bytes() == before_tasks
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged


@pytest.mark.parametrize("packet_source", ["worktree", "index"])
def test_native_stub_packet_contract_rejects_indented_packet_only_provenance_route_downgrade_before_mutation(
    wave_repo,
    packet_source,
):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    packet_text = packet_path.read_text(encoding="utf-8")
    packet_text = packet_text.replace(
        lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE,
        " " + lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE,
        1,
    ).replace(
        lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX,
        " " + lw.NATIVE_STUB_PACKET_CONTRACT_DIGEST_PREFIX,
        1,
    )
    packet_path.write_text(packet_text, encoding="utf-8")
    packet_bytes = packet_path.read_bytes()
    indexed_before = None
    if packet_source == "index":
        _git(wave_repo, "add", "--", config.tracked_packet)
        indexed_before = subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=wave_repo,
        )
        packet_path.unlink()

    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    downgraded = dataclasses.replace(config, routing_decision="ROUTE_PHASE_B")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, downgraded)

    if packet_source == "worktree":
        assert packet_path.read_bytes() == packet_bytes
    else:
        assert not packet_path.exists()
        assert subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=wave_repo,
        ) == indexed_before == packet_bytes
    assert tasks_path.read_bytes() == before_tasks
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged


def test_native_stub_packet_contract_rejects_index_only_route_downgrade_before_mutation(
    wave_repo,
):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    _git(wave_repo, "add", "--", config.tracked_packet)
    indexed_before = subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    )
    packet_path.unlink()
    tasks_path = wave_repo / "TASKS.md"
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    downgraded = dataclasses.replace(config, routing_decision="ROUTE_PHASE_B")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, downgraded)

    assert not packet_path.exists()
    assert subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    ) == indexed_before
    assert tasks_path.read_bytes() == before_tasks
    assert not ec.routing_record_path(wave_repo).exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged


def test_native_stub_packet_contract_rejects_routing_only_changed_direct_setup(
    wave_repo,
):
    config = make_config()
    routing_path = ec.routing_record_path(wave_repo)
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)
    packet_path.unlink()
    assert not packet_path.exists()
    before_routing = routing_path.read_bytes()
    before_tasks = (wave_repo / "TASKS.md").read_bytes()
    before_staged = _staged_paths(wave_repo)
    changed = dataclasses.replace(
        config,
        evidence_command="python3 -m pytest changed-validation.py",
    )

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.setup_packet(wave_repo, changed)

    assert not packet_path.exists()
    assert routing_path.read_bytes() == before_routing
    assert (wave_repo / "TASKS.md").read_bytes() == before_tasks
    assert _staged_paths(wave_repo) == before_staged


def test_native_launch_override_authority_rejects_unmarked_same_attempt_route(
    wave_repo,
):
    config = make_config()
    routing_path = ec.routing_record_path(wave_repo)
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_routing = {
        "decision": "ROUTE_PHASE_A",
        "wave_name": config.wave_id,
        "task_id": config.task_id,
        "next_candidates": [
            {
                "candidate": config.wave_id,
                "bounded": True,
                "tracked_packet": config.tracked_packet,
            }
        ],
    }
    routing_path.write_text(
        json.dumps(legacy_routing, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tasks_path = wave_repo / "TASKS.md"
    before_routing = routing_path.read_bytes()
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ) as excinfo:
        lw.setup_packet(wave_repo, config)

    assert "same-wave launch override authority" in str(excinfo.value)
    assert not (wave_repo / config.tracked_packet).exists()
    assert tasks_path.read_bytes() == before_tasks
    assert routing_path.read_bytes() == before_routing
    assert _staged_paths(wave_repo) == before_staged


def test_native_launch_override_authority_full_setup_does_not_retrofit_unmarked_route(
    wave_repo,
):
    config = make_config()
    routing_path = ec.routing_record_path(wave_repo)
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_routing = {
        "decision": "ROUTE_PHASE_A",
        "wave_name": config.wave_id,
        "task_id": config.task_id,
        "next_candidates": [
            {
                "candidate": config.wave_id,
                "bounded": True,
                "tracked_packet": config.tracked_packet,
            }
        ],
    }
    routing_path.write_text(
        json.dumps(legacy_routing, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tasks_path = wave_repo / "TASKS.md"
    before_routing = routing_path.read_bytes()
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    dispatch_calls = []

    def runner(*args, **kwargs):
        dispatch_calls.append((args, kwargs))
        raise AssertionError("an existing unmarked route must not dispatch")

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ) as excinfo:
        lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=runner,
        )

    assert "same-wave launch override authority" in str(excinfo.value)
    assert not (wave_repo / config.tracked_packet).exists()
    assert tasks_path.read_bytes() == before_tasks
    assert routing_path.read_bytes() == before_routing
    assert _staged_paths(wave_repo) == before_staged
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert dispatch_calls == []


def test_native_stub_packet_contract_direct_setup_preserves_unmarked_route_behavior(
    wave_repo,
):
    """Packet-only setup does not infer native applicability from an unmarked route."""
    config = make_config(routing_decision="ROUTE_PHASE_B")
    packet_path = lw.setup_packet(wave_repo, config)
    assert lw.NATIVE_STUB_PACKET_CONTRACT_MARKER_LINE not in packet_path.read_text(
        encoding="utf-8"
    )
    routing_path = ec.routing_record_path(wave_repo)
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_routing = {
        "decision": "ROUTE_PHASE_B",
        "wave_name": config.wave_id,
        "task_id": config.task_id,
        "next_candidates": [
            {
                "candidate": config.wave_id,
                "bounded": True,
                "tracked_packet": config.tracked_packet,
            }
        ],
    }
    routing_path.write_text(
        json.dumps(legacy_routing, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    before_packet = packet_path.read_bytes()
    before_routing = routing_path.read_bytes()

    rerun_path = lw.setup_packet(
        wave_repo,
        make_config(routing_decision="ROUTE_PHASE_B"),
    )

    assert rerun_path == packet_path
    assert packet_path.read_bytes() == before_packet
    assert routing_path.read_bytes() == before_routing
    assert lw.NATIVE_STUB_PACKET_CONTRACT_KEY not in json.loads(
        routing_path.read_text(encoding="utf-8")
    )


def test_native_stub_packet_contract_rejects_changed_partial_packet_before_mutation(
    wave_repo,
):
    """Step-1 packet truth prevents changed-config recovery before routing exists."""
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    assert not routing_path.exists()
    before_packet = packet_path.read_bytes()
    before_tasks = tasks_path.read_bytes()
    before_staged = _staged_paths(wave_repo)
    corrected_item = "Mutate the partial attempt's normative work item"
    corrected = make_config(work_items=[corrected_item])

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, corrected)

    assert packet_path.read_bytes() == before_packet
    assert tasks_path.read_bytes() == before_tasks
    assert not routing_path.exists()
    assert not (wave_repo / ".agent_bus" / "bridge_config.json").exists()
    assert not (wave_repo / config.indicator_artifact_ref).exists()
    assert _staged_paths(wave_repo) == before_staged
    assert corrected_item not in packet_path.read_text(encoding="utf-8")


def test_native_stub_packet_contract_allows_corrected_fresh_wave_id(wave_repo):
    """An unrelated existing native route does not block the required fresh attempt."""
    original = make_config()
    lw.run_wave_setup(wave_repo, original)
    corrected_item = "Use corrected normative work under a fresh attempt identity"
    corrected = make_config(
        wave_id="demo-launcher-wave-corrected-2026-06-19",
        title="Demo Launcher Wave Corrected 2026-06-19",
        work_items=[corrected_item],
    )

    result = lw.run_wave_setup(wave_repo, corrected)

    corrected_packet = wave_repo / corrected.tracked_packet
    assert result.wave_id == corrected.wave_id
    assert corrected_packet.is_file()
    assert corrected_item in corrected_packet.read_text(encoding="utf-8")
    routing = json.loads(ec.routing_record_path(wave_repo).read_text(encoding="utf-8"))
    assert routing["wave_name"] == corrected.wave_id
    assert (
        routing[lw.NATIVE_STUB_PACKET_CONTRACT_KEY]["contract"]["identity"]["wave_id"]
        == corrected.wave_id
    )


def test_authority_config_writes_bus_local_spec(wave_repo):
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
        precommit_inventory=True,
    )

    result = lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    spec_path = Path(result.candidate_authority_spec_path)
    assert spec_path.is_file()
    assert ".agent_bus-authority" in str(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["wave_id"] == config.wave_id
    assert spec["comparison_commit"] == comparison_commit
    assert spec["candidate_allowlist"] == sorted(_authority_allowlist(config))
    assert spec["indicator_artifact_ref"] == config.indicator_artifact_ref
    routing = json.loads(
        (
            wave_repo / ".agent_bus-authority" / "meta" / "post_merge_routing.json"
        ).read_text(encoding="utf-8")
    )
    assert routing["candidate_authority_required"] is True
    authority = routing["candidate_authority"]
    assert authority["required"] is True
    assert authority["precommit_inventory"] is True
    assert authority["spec_path"] == str(spec_path)
    identity = authority["spec_identity"]
    assert identity["identity_version"] == 1
    assert identity["wave_id"] == config.wave_id
    assert identity["comparison_commit"] == comparison_commit
    assert identity["candidate_allowlist"] == sorted(_authority_allowlist(config))
    assert identity["candidate_allowlist_hash"]
    assert identity["plan_path"] == config.tracked_packet
    assert identity["indicator_artifact_ref"] == config.indicator_artifact_ref
    assert identity["indicator_collection_command"] == config.indicator_collection_command
    assert identity["authority_required"] is True
    assert identity["spec_hash"]
    assert "target_branch_authority" not in authority


def test_authority_scope_guard_runs_before_l4_indicator_prestage(wave_repo):
    _write_fake_indicator_collector(wave_repo)
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    (wave_repo / "outside.txt").write_text("outside scope\n", encoding="utf-8")

    with pytest.raises(lw.LaunchWaveError, match="before L4 indicator pre-stage") as excinfo:
        lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    assert "outside.txt" in str(excinfo.value)
    assert not (wave_repo / config.indicator_artifact_ref).exists()


def test_authority_config_records_launch_owned_restart_branch(wave_repo):
    config = make_config()
    comparison_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=wave_repo,
        text=True,
    ).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=comparison_commit,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    target_branch = f"jabramsja/{config.wave_id}-restart-20260821"
    subprocess.run(
        ["git", "checkout", "-q", "-b", target_branch],
        cwd=wave_repo,
        check=True,
    )

    lw.run_wave_setup(wave_repo, config, bus_dir=".agent_bus-authority")

    routing = json.loads(
        (
            wave_repo / ".agent_bus-authority" / "meta" / "post_merge_routing.json"
        ).read_text(encoding="utf-8")
    )
    assert routing["candidate_authority"]["target_branch_authority"] == {
        "source": "launch_current_branch",
        "branch_prefix": "jabramsja",
        "target_branch": target_branch,
    }


def test_authority_config_validation_fails_closed_on_bad_schema(wave_repo):
    config = make_config()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit="not-a-commit",
        candidate_allowlist=["TASKS.md", "TASKS.md"],
        pre_review_authority=True,
    )

    errors = config.validate(wave_repo)

    assert any("duplicate candidate allowlist path" in error for error in errors)
    assert any("invalid comparison_commit" in error for error in errors)


def test_authority_config_accepts_hyphenated_aliases(wave_repo):
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    raw = dataclasses.asdict(make_config())
    probe = lw.WaveConfig.from_dict(raw)
    raw["indicator_artifact_ref"] = _authority_indicator_ref(probe)
    raw["indicator_collection_command"] = _authority_indicator_command(probe)
    raw.pop("comparison_commit", None)
    raw.pop("candidate_allowlist", None)
    raw.pop("pre_review_authority", None)
    raw.pop("precommit_inventory", None)
    raw["comparison-commit"] = base
    raw["candidate-allowlist"] = _authority_allowlist(probe)
    raw["pre-review-authority"] = True
    raw["precommit-inventory"] = True

    config = lw.WaveConfig.from_dict(raw)

    assert config.comparison_commit == base
    assert config.candidate_allowlist == _authority_allowlist(config)
    assert config.pre_review_authority is True
    assert config.precommit_inventory is True


def test_prepare_review_refuses_when_reviewer_active(wave_repo):
    config = make_config()
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=base,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    db = wave_repo / ".agent_bus-active" / "bridge.db"
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE jobs (job_id TEXT, status TEXT)")
    conn.execute("INSERT INTO jobs VALUES ('phase-b-r1-active', 'REVIEWER_RUNNING')")
    conn.commit()
    conn.close()

    with pytest.raises(lw.LaunchWaveError, match="reviewer job"):
        lw.prepare_review_authority(
            wave_repo,
            config,
            bus_dir=".agent_bus-active",
            phase="phase_b",
            review_round="manual-recovery",
        )


def test_prepare_review_uses_shared_builder_without_launching(wave_repo):
    _write_fake_indicator_collector(wave_repo)
    config = make_config()
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wave_repo, text=True).strip()
    config = make_config(
        indicator_artifact_ref=_authority_indicator_ref(config),
        indicator_collection_command=_authority_indicator_command(config),
        comparison_commit=base,
        candidate_allowlist=_authority_allowlist(config),
        pre_review_authority=True,
    )
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    (wave_repo / "mu" / "tools" / "executors").mkdir(parents=True, exist_ok=True)
    (wave_repo / "mu" / "tools" / "executors" / "candidate_authority.py").write_text(
        "# candidate\n",
        encoding="utf-8",
    )

    result = lw.prepare_review_authority(
        wave_repo,
        config,
        bus_dir=".agent_bus-authority",
        phase="phase_b",
        review_round="manual-recovery",
    )

    assert result["prepared"] is True
    assert Path(result["authority_spec_path"]).is_file()
    assert Path(result["receipt_path"]).is_file()
    assert (wave_repo / config.indicator_artifact_ref).is_file()


def test_setup_reuses_existing_builders(wave_repo):
    """The artifacts must be byte/shape-identical to the existing builders' output.

    Proves reuse behaviorally (without reaching into private internals): the
    TASKS.md note is exactly what tracker_sync_note.render_tracker_sync_note
    produces, and the routing record carries the auto-populated fields that only
    executor_common.build_post_merge_routing_record emits.
    """
    config = make_config()
    lw.run_wave_setup(wave_repo, config)

    # Tracker note builder reuse: the note in TASKS.md is byte-identical to the
    # canonical renderer's output for the same fields.
    expected_note = tsn.render_tracker_sync_note(lw.build_tracker_fields(config))
    tasks = (wave_repo / "TASKS.md").read_text(encoding="utf-8")
    assert expected_note in tasks

    # Routing-record builder reuse: only build_post_merge_routing_record emits
    # this auto-populated field set.
    routing = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text()
    )
    for key in ("state_sha", "head_sha", "timestamp_utc", "blocker_report_paths"):
        assert key in routing


# --------------------------------------------------------------------------- #
# Founder-override propagation into the routing record                        #
# --------------------------------------------------------------------------- #


def test_routing_record_carries_founder_override_for_commit_autobump(wave_repo):
    """The launcher threads the wave's FOUNDER_OVERRIDE into the routing record.

    Regression for the gate-authoring strand: a wave that adds a governed test
    file and DECLARES a FOUNDER_OVERRIDE still stranded at the commit-executor
    Step-5e growth-cap auto-bump, because ``setup_routing_record`` never passed
    ``config.founder_override`` to ``build_and_write_routing_record``. The record
    then carried no ``founder_override`` field and the commit flow's
    ``_extract_founder_override_from_routing_record`` returned "" -> the auto-bump
    fail-closed ``no_founder_override``. The launcher must make the declared
    override durable in the routing record so the extractor returns a non-empty
    token (the same token Gate 8 validates).
    """
    config = make_config()
    lw.setup_packet(wave_repo, config)  # routing builder validates the packet exists
    record = lw.setup_routing_record(wave_repo, config)

    # config.founder_override defaults to the wave_id (the declared override).
    assert config.founder_override == config.wave_id

    # The returned record AND the persisted record both carry the override.
    assert record["founder_override"] == config.founder_override
    on_disk = json.loads(
        (wave_repo / ".agent_bus" / "meta" / "post_merge_routing.json").read_text(
            encoding="utf-8"
        )
    )
    assert on_disk["founder_override"] == config.founder_override

    # Exercise the commit consumer through its public routing-record handoff
    # path. A tracker-only record with no tracker text must carry the launcher's
    # persisted token into the synthesized canonical tracker note.
    commit_record = {
        "wave_name": on_disk["wave_name"],
        "task_id": on_disk["task_id"],
        "summary": on_disk["summary"],
        "decision": "UPDATE_TRACKER_ONLY",
        "files_to_stage": ["TASKS.md"],
        "wave_class": config.wave_class,
        "target_gate_id": config.target_gate_id,
        "founder_override": on_disk["founder_override"],
    }
    handoff, errors = ce.prepare_handoff_from_routing_record(
        commit_record,
        wave_repo,
    )

    assert errors == []
    assert handoff is not None
    assert (
        f"FOUNDER_OVERRIDE:{config.founder_override}"
        in handoff["tracker_note_text"]
    )


def test_routing_record_omits_founder_override_when_builder_not_threaded(wave_repo):
    """Backward-compat: the optional param defaults empty, so existing direct
    callers and records are byte-unchanged (no ``founder_override`` key emitted),
    and threading a non-empty override adds exactly that one key.
    """
    config = make_config()
    lw.setup_packet(wave_repo, config)  # a valid tracked_packet must exist on disk

    # Direct builder call WITHOUT founder_override == every existing caller today.
    record, errors = ec.build_post_merge_routing_record(
        wave_name=config.wave_id,
        task_id=config.task_id,
        tracked_packet=config.tracked_packet,
        request_for_claude=config.request_for_claude,
        request_for_agent=config.request_for_agent,
        summary=config.routing_summary,
        repo_root=wave_repo,
    )
    assert errors == []
    assert "founder_override" not in record

    # Threading a non-empty override adds exactly that key (the bare token).
    threaded, threaded_errors = ec.build_post_merge_routing_record(
        wave_name=config.wave_id,
        task_id=config.task_id,
        tracked_packet=config.tracked_packet,
        request_for_claude=config.request_for_claude,
        request_for_agent=config.request_for_agent,
        summary=config.routing_summary,
        repo_root=wave_repo,
        founder_override=config.founder_override,
    )
    assert threaded_errors == []
    assert threaded["founder_override"] == config.founder_override


# --------------------------------------------------------------------------- #
# Baked-in fences                                                             #
# --------------------------------------------------------------------------- #


def test_generated_packet_carries_baked_in_fences(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    content = packet_path.read_text(encoding="utf-8")

    # The builder's public fence check is clean for the generated packet.
    assert lw.check_packet_fences(content, config) == []

    # packet-integrity: Scope mentions TASKS.md + a bare FOUNDER_OVERRIDE line.
    assert "## Scope" in content
    assert "TASKS.md" in content
    assert f"\nFOUNDER_OVERRIDE:{config.wave_id}\n" in content

    # line-ref lint: no code line-number references like `<file>.py:<n>`.
    assert not re.search(r"\.(?:py|js|md|sh|json|yaml|yml|txt):\d+", content)

    # asterisk-free title (the H1 line).
    title_line = content.splitlines()[0]
    assert title_line == f"# {config.title}"
    assert "*" not in title_line


def test_run_mu_speed_ok_fence_baked_when_slow_function_present(wave_repo):
    config = make_config(slow_functions=["run_mu"])
    content = lw.render_wave_packet(config)
    assert "run_mu" in content
    assert "# SPEED_OK" in content
    assert lw.check_packet_fences(content, config) == []

    # The fence is real: stripping the annotation makes the check fail.
    stripped = content.replace("# SPEED_OK", "(annotation removed)")
    errors = lw.check_packet_fences(stripped, config)
    assert any("run_mu # SPEED_OK" in e for e in errors)


def test_tooling_only_packet_has_no_unannotated_run_mu(wave_repo):
    config = make_config()  # no slow_functions
    content = lw.render_wave_packet(config)
    # A tooling-only wave never introduces an un-annotated run_mu mention.
    assert "run_mu" not in content
    assert lw.check_packet_fences(content, config) == []


def test_builder_refuses_packet_failing_line_ref_fence(wave_repo):
    # A work item that cites code by file:line must be rejected fail-closed.
    config = make_config(
        work_items=["Patch the bug cited at loader.py:128 in the kernel"]
    )
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_packet(wave_repo, config)
    assert "line-ref lint" in str(exc.value)


def test_fence_failure_persists_no_offending_packet(wave_repo):
    """Bridge round 4 DEFECT: a fence failure must NOT leave an offending packet.

    The repro put a code line-ref in ``purpose`` (which feeds create_plan_draft's
    draft, the Purpose/Scope/Request sections). create_plan_draft used to write
    that draft to disk BEFORE the fence check ran, so the offending packet
    persisted (Status: Phase A, containing loader.py:128) even though setup_packet
    raised. The fence check now gates the write: a failing fence raises before any
    packet is written.
    """
    config = make_config(
        purpose="Fix the crash at loader.py:128 in the bootstrap loader."
    )
    wave_id = config.wave_id

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_packet(wave_repo, config)
    assert "line-ref lint" in str(exc.value)

    # No packet persisted: not at the deterministic path, and none by glob.
    assert not (wave_repo / config.tracked_packet).exists()
    assert _artifact_counts(wave_repo, wave_id)[0] == 0


def test_run_wave_setup_fence_failure_persists_no_packet(wave_repo):
    """End-to-end mirror of the bridge round 4 repro via run_wave_setup.

    setup_packet is the first step, so a line-ref in ``purpose`` must fail the
    whole setup closed with no artifact of any kind persisted.
    """
    config = make_config(
        purpose="Patch the regression at loader.py:128 before shipping."
    )
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, config)
    assert "line-ref lint" in str(exc.value)
    assert not (wave_repo / config.tracked_packet).exists()
    assert _artifact_counts(wave_repo, config.wave_id) == (0, 0, 0)


# --------------------------------------------------------------------------- #
# Fail-closed precondition                                                    #
# --------------------------------------------------------------------------- #


def test_fail_closed_precondition_raises_when_tracker_entry_missing(wave_repo):
    config = make_config()
    # Create the packet but NOT the tracker note: the dispatcher would hold.
    lw.setup_packet(wave_repo, config)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_fail_closed_precondition(wave_repo, config)
    assert "fail-closed precondition" in str(exc.value)


def test_fail_closed_precondition_passes_after_full_setup(wave_repo):
    config = make_config()
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    # Now the same-wave TASKS entry exists -> no raise.
    lw.verify_fail_closed_precondition(wave_repo, config)


# --------------------------------------------------------------------------- #
# 3-guard verification                                                        #
# --------------------------------------------------------------------------- #


def test_three_guard_verify_raises_when_tracker_note_missing(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_three_guards(wave_repo, config, packet_path)
    assert "guard 3" in str(exc.value)


def test_three_guard_verify_raises_when_founder_override_stripped(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    # Tamper the packet: remove the FOUNDER_OVERRIDE authorization line.
    tampered = packet_path.read_text(encoding="utf-8").replace(
        f"FOUNDER_OVERRIDE:{config.wave_id}", "AUTH REMOVED"
    )
    packet_path.write_text(tampered, encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.verify_three_guards(wave_repo, config, packet_path)
    assert "guard 2" in str(exc.value)


def test_three_guard_verify_passes_after_full_setup(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.verify_three_guards(wave_repo, config, packet_path)  # no raise


# --------------------------------------------------------------------------- #
# Bounded re-run recovery contract                                            #
# --------------------------------------------------------------------------- #


def test_rerun_recovery_converges_after_partial_setup(wave_repo):
    """Partial run (steps 1-2) + full re-run with SAME config -> one of each."""
    config = make_config()
    wave_id = config.wave_id

    # Partial setup: run the packet + tracker-note steps, then abort.
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 0)

    # Re-run the full chain with the SAME wave-config.
    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)

    # Re-running again stays convergent (idempotent).
    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_rerun_recovery_after_partial_routing(wave_repo):
    """Abort after the routing step; re-run converges with no duplicate."""
    config = make_config()
    wave_id = config.wave_id

    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)

    lw.run_wave_setup(wave_repo, make_config())
    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_each_artifact_step_is_individually_idempotent(wave_repo):
    config = make_config()
    wave_id = config.wave_id

    # Run each artifact step twice; none may duplicate its artifact.
    lw.setup_packet(wave_repo, config)
    lw.setup_packet(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_tracker_note(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)
    lw.setup_routing_record(wave_repo, config)

    assert _artifact_counts(wave_repo, wave_id) == (1, 1, 1)


def test_packet_content_is_byte_stable_across_reruns(wave_repo):
    config = make_config()
    first = lw.setup_packet(wave_repo, config).read_text(encoding="utf-8")
    second = lw.setup_packet(wave_repo, make_config()).read_text(encoding="utf-8")
    assert first == second


def test_setup_packet_preserves_locked_phase_b_packet_on_rerun(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    advanced = _phase_b_packet_content(config)
    packet_path.write_text(advanced, encoding="utf-8")

    rerun_path = lw.setup_packet(wave_repo, make_config())

    assert rerun_path == packet_path
    assert packet_path.read_text(encoding="utf-8") == advanced


@pytest.mark.parametrize(
    "downstream_status",
    (
        "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT",
        "IMPLEMENTED / LOCAL EVIDENCE",
    ),
)
def test_same_config_recovery_restores_staged_commit_packet_mutations(
    wave_repo,
    downstream_status,
):
    """A later commit-owned packet outranks and survives an older Phase B blob."""
    config = make_config()
    lw.run_wave_setup(wave_repo, config)
    packet_path = wave_repo / config.tracked_packet
    phase_b_content = _phase_b_packet_content(config)
    commit_content = _commit_recovery_packet_content(
        wave_repo,
        config,
        downstream_status,
    )
    deferred_path = _same_wave_deferred_non_blocking_path(config)

    packet_path.write_text(commit_content, encoding="utf-8")
    _git(wave_repo, "add", "--", config.tracked_packet)
    indexed_commit_bytes = subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    )

    # Model an interrupted recovery that left the earlier Phase B packet in the
    # worktree while the commit-owned packet remains durable in the index.
    packet_path.write_text(phase_b_content, encoding="utf-8")
    assert packet_path.read_text(encoding="utf-8") != commit_content

    result = lw.run_wave_setup(wave_repo, make_config())

    restored = packet_path.read_text(encoding="utf-8")
    assert result.wave_id == config.wave_id
    assert restored == commit_content
    assert packet_path.read_bytes() == indexed_commit_bytes
    assert subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    ) == indexed_commit_bytes
    assert f"Status: {downstream_status}" in restored
    assert "Phase-A-Lock: LOCKED" in restored
    assert (
        f"- `{deferred_path}`\n"
        "  - Same-wave Phase B/commit generated deferred non-blocking bridge "
        "findings packet only; no unrelated deferred report is authorized by this wave."
    ) in restored
    assert restored.count(
        "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->"
    ) == 1
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)


def test_same_config_recovery_rejects_unauthorized_post_lock_scope_mutation(
    wave_repo,
):
    """An exact machine block cannot authorize a wrong-wave Scope entry."""
    config = make_config()
    lw.run_wave_setup(wave_repo, config)
    packet_path = wave_repo / config.tracked_packet
    authorized_path = _same_wave_deferred_non_blocking_path(config)
    other_path = (
        "reports/deferred/non_blocking/"
        "other-wave-2026-06-19_bridge_nonblockers.md"
    )
    authorized = _commit_recovery_packet_content(
        wave_repo,
        config,
        "IMPLEMENTED / LOCAL EVIDENCE",
    )
    tampered = authorized.replace(
        f"- `{authorized_path}`\n"
        "  - Same-wave Phase B/commit generated deferred non-blocking",
        f"- `{other_path}`\n"
        "  - Same-wave Phase B/commit generated deferred non-blocking",
        1,
    )
    assert tampered != authorized
    assert f"  - `{authorized_path}`" in tampered
    assert f"- `{other_path}`" in tampered

    packet_path.write_text(tampered, encoding="utf-8")
    _git(wave_repo, "add", "--", config.tracked_packet)
    packet_before = packet_path.read_bytes()
    indexed_before = subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    )
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    tasks_before = tasks_path.read_bytes()
    routing_before = routing_path.read_bytes()
    staged_before = _staged_paths(wave_repo)

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, make_config())

    assert packet_path.read_bytes() == packet_before
    assert subprocess.check_output(
        ["git", "show", f":{config.tracked_packet}"],
        cwd=wave_repo,
    ) == indexed_before == packet_before
    assert tasks_path.read_bytes() == tasks_before
    assert routing_path.read_bytes() == routing_before
    assert _staged_paths(wave_repo) == staged_before


def test_same_config_recovery_rejects_status_with_lone_machine_marker(
    wave_repo,
):
    """A marker-like clarification cannot authorize a downstream status."""
    config = make_config()
    lw.run_wave_setup(wave_repo, config)
    packet_path = wave_repo / config.tracked_packet
    unauthorized = lw.render_wave_packet(config).replace(
        "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)",
        "Status: IMPLEMENTED / LOCAL EVIDENCE",
        1,
    ).replace(
        "Phase-A-Lock: UNLOCKED",
        "Phase-A-Lock: LOCKED",
        1,
    )
    unauthorized += (
        "\n## Non-normative review clarification\n\n"
        "<!-- COMMIT_PATH_TRUTH_REFRESH:start -->\n"
    )
    packet_path.write_text(unauthorized, encoding="utf-8")
    _git(wave_repo, "add", "--", config.tracked_packet)
    packet_before = packet_path.read_bytes()
    tasks_path = wave_repo / "TASKS.md"
    routing_path = ec.routing_record_path(wave_repo)
    tasks_before = tasks_path.read_bytes()
    routing_before = routing_path.read_bytes()
    staged_before = _staged_paths(wave_repo)

    with pytest.raises(
        lw.LaunchWaveError,
        match="corrected-config-relaunch-required",
    ):
        lw.run_wave_setup(wave_repo, make_config())

    assert packet_path.read_bytes() == packet_before
    assert tasks_path.read_bytes() == tasks_before
    assert routing_path.read_bytes() == routing_before
    assert _staged_paths(wave_repo) == staged_before


def test_setup_packet_restores_staged_phase_b_packet_after_worktree_clobber(wave_repo):
    config = make_config()
    packet_path = lw.setup_packet(wave_repo, config)
    advanced = _phase_b_packet_content(config)
    packet_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", config.tracked_packet)

    packet_path.write_text(lw.render_wave_packet(config), encoding="utf-8")
    assert "Phase-A-Lock: UNLOCKED" in packet_path.read_text(encoding="utf-8")

    lw.setup_packet(wave_repo, make_config())

    assert packet_path.read_text(encoding="utf-8") == advanced


def test_setup_tracker_note_restores_staged_phase_b_note_after_worktree_clobber(wave_repo):
    config = make_config()
    lw.setup_tracker_note(wave_repo, config)
    tasks_path = wave_repo / "TASKS.md"
    initial = tasks_path.read_text(encoding="utf-8")
    initial_note = _tracker_note_line(initial, config.wave_id)
    advanced_note = _phase_b_tracker_note_line(initial_note)
    advanced = initial.replace(initial_note, advanced_note)
    tasks_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", "TASKS.md")

    tasks_path.write_text(initial, encoding="utf-8")
    assert "scope_refs:" not in tasks_path.read_text(encoding="utf-8")

    lw.setup_tracker_note(wave_repo, make_config())

    assert tasks_path.read_text(encoding="utf-8") == advanced


def test_tracker_block_adjacency_restores_staged_phase_b_note_after_predecessor_child(
    wave_repo,
):
    config = make_config(wave_id="demo-wave-2026-06-27")
    tasks_path = wave_repo / "TASKS.md"
    seed_content = tasks_path.read_text(encoding="utf-8")
    seed_note = _tracker_note_line(seed_content, "seed-wave")
    seed_child = "  - Recovery evidence: this remains attached to seed-wave."
    tasks_path.write_text(
        seed_content.replace(
            seed_note + "\n\n---\n",
            seed_note + "\n\n" + seed_child + "\n\n---\n",
        ),
        encoding="utf-8",
    )

    lw.setup_tracker_note(wave_repo, config)
    initial = tasks_path.read_text(encoding="utf-8")
    initial_note = _tracker_note_line(initial, config.wave_id)
    advanced_note = _phase_b_tracker_note_line(initial_note)
    advanced = initial.replace(initial_note, advanced_note)
    tasks_path.write_text(advanced, encoding="utf-8")
    _git(wave_repo, "add", "TASKS.md")

    missing_note = initial.replace(initial_note + "\n\n", "")
    tasks_path.write_text(missing_note, encoding="utf-8")
    assert f", {config.wave_id}):" not in tasks_path.read_text(encoding="utf-8")

    lw.setup_tracker_note(wave_repo, config)

    restored = tasks_path.read_text(encoding="utf-8")
    assert restored == advanced
    assert _tracker_note_line(restored, config.wave_id) == advanced_note
    assert restored.count(f", {config.wave_id}):") == 1
    assert "scope_refs:" in restored
    assert (
        restored.index(seed_note)
        < restored.index(seed_child)
        < restored.index(advanced_note)
    )


# --------------------------------------------------------------------------- #
# bridge_config sync convergence                                              #
# --------------------------------------------------------------------------- #


def test_bridge_config_sync_is_noop_when_absent(wave_repo):
    # No bridge_config.json on this bus -> graceful no-op (safe to re-run).
    assert lw.setup_bridge_config(wave_repo) is None
    assert lw.setup_bridge_config(wave_repo) is None


def test_bridge_config_sync_converges(wave_repo):
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text(
        json.dumps(
            {
                "agents": {
                    "claude": {
                        "cmd": ["claude", "--model", "stale-model"],
                        "display_name": "Claude",
                        "mode": "review",
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    path1 = lw.setup_bridge_config(wave_repo)
    after_first = (bus / "bridge_config.json").read_text(encoding="utf-8")
    path2 = lw.setup_bridge_config(wave_repo)
    after_second = (bus / "bridge_config.json").read_text(encoding="utf-8")

    assert path1 == path2  # idempotent target
    assert after_first == after_second  # converged: second run is a no-op


def test_setup_bridge_config_fails_closed_on_malformed_json(wave_repo):
    """Bridge round 2 DEFECT: a PRESENT-but-malformed bridge_config must NOT be
    silently skipped as if absent; the setup must fail closed.

    The sync builder returns the same None for an absent file (the intended
    no-op) and for a present-but-unparseable file; the launcher splits those so a
    broken live config can never be reported as a clean setup.
    """
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo)
    msg = str(exc.value)
    assert "bridge_config" in msg
    assert "malformed" in msg or "unreadable" in msg


def test_setup_bridge_config_fails_closed_on_non_object(wave_repo):
    """A present bridge_config lacking an 'agents' object is malformed for sync
    purposes -> fail closed, not a silent skip."""
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text('{"no_agents_key": 1}', encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo)
    assert "agents" in str(exc.value)


def test_run_wave_setup_fails_closed_on_malformed_bridge_config(wave_repo):
    """End-to-end: a malformed live bridge_config fails the WHOLE setup closed.

    Directly refutes the bridge round 2 repro, where run_wave_setup returned
    raised=false / bridge_config_path=null / precondition_ok=true / guards_ok=true
    over a malformed config. The launcher must raise instead, and must NOT touch
    the broken file (no silent rewrite).
    """
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, make_config())
    # The broken file is left untouched (not silently rewritten or "repaired").
    assert (bus / "bridge_config.json").read_text(encoding="utf-8") == "{not valid json"


def test_rerun_recovers_after_malformed_bridge_config_fixed(wave_repo):
    """The fail-closed bridge_config step composes with the re-run recovery.

    A malformed bridge_config fails step 4 closed AFTER steps 1-3 wrote their
    artifacts (simple-sequential, no rollback). Fixing the file and re-running the
    SAME config converges to exactly one canonical copy of each artifact -- the
    bounded re-run recovery contract, now with the new fail-closed step in line.
    """
    config = make_config()
    bus = wave_repo / ".agent_bus"
    bus.mkdir(exist_ok=True)
    (bus / "bridge_config.json").write_text("{not valid json", encoding="utf-8")

    # First run fails closed at the bridge_config step (after packet/note/routing).
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, config)
    # Steps 1-3 already persisted their artifacts -> one of each, no duplicates.
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)

    # Fix the bridge_config, re-run the SAME config -> converges (still one each).
    (bus / "bridge_config.json").write_text(
        json.dumps(
            {"agents": {"claude": {"cmd": ["claude"], "display_name": "C",
                                   "mode": "review"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    result = lw.run_wave_setup(wave_repo, make_config())
    assert result.bridge_config_path is not None
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)


def test_setup_bridge_config_auto_seeds_fresh_namespaced_bus(wave_repo):
    """PIPELINE-FIX-33: a fresh namespaced bus with NO bridge_config is seeded from
    the canonical default bus, then synced -- no manual pre-seed needed.

    Before this fix, launching a wave on a fresh worktree required the orchestrator
    to hand-run ensure_bridge_config_path + sync first, because setup_bridge_config
    no-op'd over the absent namespaced config. Now setup_bridge_config seeds it from
    the trusted same-repo default and returns the namespaced path with agents present.
    """
    # Trusted seed source: the canonical default-bus bridge_config.
    default_bus = wave_repo / ".agent_bus"
    default_bus.mkdir(exist_ok=True)
    (default_bus / "bridge_config.json").write_text(
        json.dumps(
            {
                "agents": {
                    "claude": {
                        "cmd": ["claude", "--model", "seed-model"],
                        "display_name": "Claude",
                        "mode": "review",
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    assert not namespaced.exists()  # fresh bus: no bridge_config of its own yet

    result = lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")

    # Seeded into the namespaced bus and synced -> returns that bus's path with the
    # configured agent present (no manual ensure+sync pre-step was needed).
    assert result == namespaced
    assert namespaced.exists()
    seeded = json.loads(namespaced.read_text(encoding="utf-8"))
    assert isinstance(seeded.get("agents"), dict)
    assert "claude" in seeded["agents"]

    # A second run over the now-healthy seeded config converges (no-op-equivalent):
    # the seeder short-circuits on the present file and the sync stays idempotent.
    result2 = lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")
    assert result2 == namespaced
    assert "claude" in json.loads(namespaced.read_text(encoding="utf-8"))["agents"]


def test_setup_bridge_config_auto_seed_does_not_overwrite_present_malformed(wave_repo):
    """The auto-seed must NOT weaken the present-but-malformed fail-closed.

    Even with a valid trusted seed source available, a PRESENT-but-malformed
    bridge_config on the active bus is left untouched (the seeder short-circuits on
    an existing file) and still fails the setup closed -- it is never silently
    overwritten or 'repaired' by the seed.
    """
    # A valid trusted seed source exists on the default bus...
    default_bus = wave_repo / ".agent_bus"
    default_bus.mkdir(exist_ok=True)
    (default_bus / "bridge_config.json").write_text(
        json.dumps(
            {"agents": {"claude": {"cmd": ["claude"], "display_name": "C",
                                   "mode": "review"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    # ...but the active namespaced bus already has a MALFORMED bridge_config.
    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    namespaced.parent.mkdir(parents=True, exist_ok=True)
    namespaced.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7")
    msg = str(exc.value)
    assert "bridge_config" in msg
    assert "malformed" in msg or "unreadable" in msg

    # The malformed file was NOT overwritten by the seed (left byte-identical).
    assert namespaced.read_text(encoding="utf-8") == "{not valid json"


def test_setup_bridge_config_noop_when_no_seed_source_on_namespaced_bus(wave_repo):
    """Genuine no-source case still no-ops on a fresh namespaced bus.

    With NO trusted seed source available (no default-bus bridge_config and no other
    source), the seeder copies nothing, so setup_bridge_config returns None and
    creates no file -- and re-running stays a no-op.
    """
    namespaced = ec.bridge_config_path(wave_repo, ".agent_bus-x7")
    assert not namespaced.exists()

    assert lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7") is None
    assert not namespaced.exists()  # the seeder created nothing
    assert lw.setup_bridge_config(wave_repo, bus_dir=".agent_bus-x7") is None


def test_launch_max_turns_updates_existing_bridge_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    result = lw.run_wave_setup(
        wave_repo,
        make_config(implementer_agent="claude", reviewer_agent="claude", max_turns=42),
    )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["claude"]["cmd"]
    assert cmd.count("--max-turns") == 1
    assert cmd[cmd.index("--max-turns") + 1] == "42"
    assert result.launch["launch_overrides"] == {
        "implementer_agent": "claude",
        "reviewer_agent": "claude",
        "max_turns": 42,
    }
    assert result.launch["bridge_max_turns_override"]["agents"] == ["claude"]


def test_launch_max_turns_appends_to_claude_bridge_command_without_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--model", "claude-opus-4-8"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    result = lw.run_wave_setup(
        wave_repo,
        make_config(
            implementer_agent="claude",
            reviewer_agent="claude",
            max_turns=37,
        ),
    )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["claude"]["cmd"]
    assert cmd[-2:] == ["--max-turns", "37"]
    assert cmd.count("--max-turns") == 1
    assert result.launch["launch_overrides"] == {
        "implementer_agent": "claude",
        "reviewer_agent": "claude",
        "max_turns": 37,
    }
    assert result.launch["bridge_max_turns_override"]["max_turns"] == 37
    assert result.launch["bridge_max_turns_override"]["agents"] == ["claude"]


def test_launch_max_turns_rejects_codex_exec_without_verified_override(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "codex": {
                "mode": "live",
                "display_name": "Codex",
                "cmd": [
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
                ],
                "prompt_via_stdin": True,
                "timeout_s": 1200,
                "env": {},
            }
        },
    )

    config = make_config(
        implementer_agent="codex",
        reviewer_agent="codex",
        pager_route="codex",
        max_turns=37,
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, config)

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    cmd = bridge["agents"]["codex"]["cmd"]
    assert "--max-turns" not in cmd
    assert "max_turns=37" not in cmd
    assert "codex" in str(exc.value)
    assert "verified max-turn override" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_rejects_codex_exec_with_unsupported_token(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "codex": {
                "mode": "live",
                "display_name": "Codex",
                "cmd": ["codex", "exec", "-", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 1200,
                "env": {},
            }
        },
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(
            wave_repo,
            make_config(
                implementer_agent="codex",
                reviewer_agent="codex",
                pager_route="codex",
                max_turns=37,
            ),
        )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    assert bridge["agents"]["codex"]["cmd"] == [
        "codex",
        "exec",
        "-",
        "--max-turns",
        "100",
    ]
    assert "codex" in str(exc.value)
    assert "--max-turns" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_rejects_mixed_agents_without_partial_mutation(wave_repo):
    bridge_path = _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            },
            "custom": {
                "mode": "live",
                "display_name": "Custom",
                "cmd": ["python3", "custom_agent.py"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            },
        },
    )

    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "claude", "reviewer": "custom"},
                "bridge_agent_defaults": {"claude": {}, "custom": {}},
                "pipeline_agent_pager": {"enabled": False, "route": "notify-only"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(
            wave_repo,
            make_config(
                implementer_agent="claude",
                reviewer_agent="custom",
                max_turns=42,
            ),
        )

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    assert bridge["agents"]["claude"]["cmd"] == [
        "claude",
        "--print",
        "--max-turns",
        "100",
    ]
    assert bridge["agents"]["custom"]["cmd"] == ["python3", "custom_agent.py"]
    assert "custom" in str(exc.value)
    assert "support a max-turn override" in str(exc.value)


def test_launch_max_turns_does_not_mutate_executor_config(wave_repo):
    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"role_agents": {"implementer": "claude", "reviewer": "claude"}}),
        encoding="utf-8",
    )
    before = config_path.read_text(encoding="utf-8")
    _write_bridge_config(
        wave_repo,
        {
            "claude": {
                "mode": "live",
                "display_name": "Claude",
                "cmd": ["claude", "--print", "--max-turns", "100"],
                "prompt_via_stdin": True,
                "timeout_s": 900,
                "env": {},
            }
        },
    )

    lw.run_wave_setup(wave_repo, make_config(max_turns=55))

    assert config_path.read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------- #
# L4 indicator pre-stage (kills the agent_review_crash indicator-absent strand) #
# --------------------------------------------------------------------------- #

_PRESTAGE_WARNING = "L4 indicator pre-stage skipped"


def _staged_paths(repo):
    """Return the list of paths currently staged in the index (vs HEAD)."""
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    return out.split()


def _write_indicator_generator(repo):
    """Write a generator the wave_repo can actually run: it creates the artifact
    at the output path passed as argv[1] (stands in for the canonical collector,
    which is absent from the tmp repo)."""
    gen = repo / "gen_indicator.py"
    gen.write_text(
        "import json, os, sys\n"
        "out = sys.argv[1]\n"
        "os.makedirs(os.path.dirname(out) or '.', exist_ok=True)\n"
        "with open(out, 'w', encoding='utf-8') as fh:\n"
        "    json.dump({'wave_id': 'demo', 'indicator': True}, fh)\n",
        encoding="utf-8",
    )
    return gen


def test_prestage_l4_indicator_collects_and_stages_artifact(wave_repo, capsys):
    """(a) A config WITH an indicator command -> after setup the indicator artifact
    exists on disk AND is staged in the index, so the L4 ``--staged`` contract
    finds it PRESENT at Phase-B review (instead of stranding on indicator-absent).
    """
    _write_indicator_generator(wave_repo)
    artifact_ref = "reports/l4_wave_indicators/demo.json"
    config = make_config(
        indicator_artifact_ref=artifact_ref,
        indicator_collection_command=f"python3 gen_indicator.py {artifact_ref}",
    )

    lw.run_wave_setup(wave_repo, config)

    # Exists on disk AND staged in the git index.
    assert (wave_repo / artifact_ref).is_file()
    assert artifact_ref in _staged_paths(wave_repo)
    # Success path: no fail-open warning was emitted.
    assert _PRESTAGE_WARNING not in capsys.readouterr().err


def test_prestage_l4_indicator_fail_open_on_nonzero_command(wave_repo, capsys):
    """(b) A config whose indicator command exits non-zero -> setup still SUCCEEDS
    (fail-open): the whole launch completes, a warning is logged, and the launch is
    NOT aborted. commit_executor Step 5 remains the commit-time authority.
    """
    artifact_ref = "reports/l4_wave_indicators/demo.json"
    config = make_config(
        indicator_artifact_ref=artifact_ref,
        # A command that always fails -> exercises the fail-open path.
        indicator_collection_command='python3 -c "import sys; sys.exit(3)"',
    )

    # MUST NOT raise: a failing pre-stage can never abort a wave launch.
    result = lw.run_wave_setup(wave_repo, config)
    assert result.precondition_ok is True
    assert result.guards_ok is True
    assert result.launch["launched"] is False

    # Fail-open warning emitted, and nothing staged (the command failed).
    assert _PRESTAGE_WARNING in capsys.readouterr().err
    assert artifact_ref not in _staged_paths(wave_repo)


def test_prestage_l4_indicator_noop_when_indicator_fields_empty(wave_repo, capsys):
    """(c) A config with empty indicator fields -> a silent no-op: no command is
    run, no warning is logged, and nothing is staged.

    Tested against the helper directly because the full run_wave_setup chain
    requires non-empty indicator fields at the tracker-note step; the no-op is a
    property of the helper itself.
    """
    config = make_config(
        indicator_artifact_ref="",
        indicator_collection_command="",
    )

    lw.prestage_l4_indicator(wave_repo, config)

    # Silent no-op: no warning, nothing staged, no indicator dir created.
    assert capsys.readouterr().err == ""
    assert _staged_paths(wave_repo) == []
    assert not (wave_repo / "reports" / "l4_wave_indicators").exists()


# --------------------------------------------------------------------------- #
# Optional dispatcher launch                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bus_dir", [None, ".agent_bus-unlocked-phase-a-retry"])
def test_same_config_unlocked_phase_a_failure_then_success_keeps_setup_retry(
    wave_repo,
    monkeypatch,
    bus_dir,
):
    _write_fake_indicator_collector(wave_repo)
    config = _post_commit_authority_config_for_repo(wave_repo)
    packet_path = wave_repo / config.tracked_packet
    initial_packet = lw.render_wave_packet(config).encode("utf-8")
    routing_path = ec.routing_record_path(wave_repo, bus_dir)
    available_path, claimed_path = _terminal_receipt_paths(wave_repo, bus_dir)
    calls = []

    def runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert cmd == lw.build_dispatch_command(wave_repo, config, bus_dir=bus_dir)
        assert "phase-b" not in cmd
        assert not claimed_path.exists()
        assert packet_path.read_bytes() == initial_packet
        routing = json.loads(routing_path.read_text(encoding="utf-8"))
        assert routing["decision"] == "ROUTE_PHASE_A"
        assert len(routing["next_candidates"]) == 1
        _git(wave_repo, "add", "--", "TASKS.md", config.tracked_packet)
        if len(calls) == 1:
            assert not available_path.exists()
            return subprocess.CompletedProcess(cmd, 73)
        return subprocess.CompletedProcess(cmd, 0)

    with pytest.raises(lw.LaunchWaveError, match="dispatcher launch failed"):
        lw.run_wave_setup(
            wave_repo, config, launch=True, runner=runner, bus_dir=bus_dir
        )

    receipt_before = available_path.read_bytes()
    receipt = json.loads(receipt_before)
    assert receipt["returncode"] == 73
    assert receipt["packet_worktree_sha256"] == hashlib.sha256(initial_packet).hexdigest()
    assert receipt["packet_index_sha256"] == receipt["packet_worktree_sha256"]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unlocked Phase A retry must not claim or dispatch Phase B")

    monkeypatch.setattr(lw, "_claim_dispatch_terminal_receipt", forbidden)
    monkeypatch.setattr(lw, "build_phase_b_dispatch_command", forbidden)

    # A prior available failure receipt must not block this retry or a later
    # idempotent setup after routing metadata has been refreshed.
    for _attempt in range(2):
        result = lw.run_wave_setup(
            wave_repo, config, launch=True, runner=runner, bus_dir=bus_dir
        )
        assert result.launch["returncode"] == 0
        assert result.tracker_note_written is True
        assert available_path.read_bytes() == receipt_before
        assert not claimed_path.exists()
        assert packet_path.read_bytes() == initial_packet
        assert subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"], cwd=wave_repo
        ) == initial_packet
        assert _artifact_counts(wave_repo, config.wave_id)[:2] == (1, 1)

    assert len(calls) == 3


def test_dispatch_terminal_receipt_binds_exact_post_return_authority(wave_repo):
    state = _prepare_native_phase_b_terminal_state(wave_repo)
    config = state["config"]
    available_path = state["available_path"]
    claimed_path = state["claimed_path"]

    assert state["observed"]["receipt_visible_before_return"] == (False, False)
    assert available_path.is_file()
    assert not claimed_path.exists()
    receipt = json.loads(available_path.read_text(encoding="utf-8"))
    expected_keys = {
        "version",
        "state",
        "wave_id",
        "task_id",
        "tracked_packet",
        "native_stub_packet_contract_digest",
        "routing_record_path",
        "routing_record_sha256",
        "packet_worktree_sha256",
        "packet_index_sha256",
        "candidate_authority_spec_path",
        "candidate_authority_spec_sha256",
        "returncode",
    }
    assert set(receipt) == expected_keys
    assert type(receipt["version"]) is int
    assert receipt["version"] == lw.LAUNCH_WAVE_DISPATCH_TERMINAL_VERSION == 1
    assert receipt["state"] == "available"
    assert receipt["wave_id"] == config.wave_id
    assert receipt["task_id"] == config.task_id
    assert receipt["tracked_packet"] == config.tracked_packet
    assert receipt["native_stub_packet_contract_digest"] == (
        lw.build_native_stub_packet_contract(config)["digest"]
    )
    assert receipt["routing_record_path"] == state["routing_path"].relative_to(
        wave_repo
    ).as_posix()
    assert receipt["routing_record_sha256"] == _sha256_path(state["routing_path"])
    assert receipt["packet_worktree_sha256"] == _sha256_path(state["packet_path"])
    assert receipt["packet_index_sha256"] == hashlib.sha256(
        subprocess.check_output(
            ["git", "show", f":{config.tracked_packet}"],
            cwd=wave_repo,
        )
    ).hexdigest()
    assert receipt["candidate_authority_spec_path"] == state[
        "spec_path"
    ].relative_to(wave_repo).as_posix()
    assert receipt["candidate_authority_spec_sha256"] == _sha256_path(
        state["spec_path"]
    )
    assert type(receipt["returncode"]) is int
    assert receipt["returncode"] == 73
    assert not list(available_path.parent.glob(f".{available_path.name}.*.tmp"))


def test_dispatch_terminal_receipt_claim_is_atomic_and_single_use(
    wave_repo,
    monkeypatch,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=".agent_bus-phase-b-claim-race",
    )
    _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    available_path = state["available_path"]
    claimed_path = state["claimed_path"]
    available_bytes = available_path.read_bytes()
    receipt_read_barrier = threading.Barrier(2)
    competing_resume_refused = threading.Event()
    runner_calls = []
    original_read_text = Path.read_text

    def synchronized_read_text(path, *args, **kwargs):
        content = original_read_text(path, *args, **kwargs)
        if path == available_path:
            receipt_read_barrier.wait(timeout=10)
        return content

    def runner(cmd, **_kwargs):
        runner_calls.append(cmd)
        assert not available_path.exists()
        assert claimed_path.read_bytes() == available_bytes
        assert competing_resume_refused.wait(timeout=10)
        raise InterruptedError("leave the winning public claim in place")

    def resume_once(_index):
        try:
            lw.run_wave_setup(
                wave_repo,
                state["config"],
                launch=True,
                runner=runner,
                bus_dir=state["bus_dir"],
            )
        except InterruptedError:
            return "claimed", "runner interrupted"
        except lw.LaunchWaveError as exc:
            competing_resume_refused.set()
            return "refused", str(exc)
        raise AssertionError("the winning dispatcher runner must interrupt")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(Path, "read_text", synchronized_read_text)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resume_once, range(2)))

    assert sorted(result[0] for result in results) == ["claimed", "refused"]
    refusal = next(detail for outcome, detail in results if outcome == "refused")
    assert "terminal receipt" in refusal
    assert len(runner_calls) == 1
    assert not available_path.exists()
    assert claimed_path.read_bytes() == available_bytes

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=lambda *_args, **_kwargs: pytest.fail(
                "a consumed receipt must not dispatch"
            ),
            bus_dir=state["bus_dir"],
        )
    assert not available_path.exists()
    assert claimed_path.read_bytes() == available_bytes


@pytest.mark.parametrize(
    "runner_outcome",
    ["zero", "exception", "none", "bool", "string"],
)
def test_dispatch_terminal_receipt_is_not_minted_without_normal_integer_nonzero_return(
    wave_repo,
    runner_outcome,
):
    _write_fake_indicator_collector(wave_repo)
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = f".agent_bus-no-terminal-{runner_outcome}"
    available_path, claimed_path = _terminal_receipt_paths(wave_repo, bus_dir)

    def runner(cmd, **_kwargs):
        assert not available_path.exists()
        assert not claimed_path.exists()
        if runner_outcome == "exception":
            raise RuntimeError("runner failed before returning")
        returncode = {
            "zero": 0,
            "none": None,
            "bool": True,
            "string": "9",
        }[runner_outcome]
        return type("Result", (), {"returncode": returncode})()

    if runner_outcome == "zero":
        result = lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=runner,
            bus_dir=bus_dir,
        )
        assert result.launch["returncode"] == 0
    else:
        expected = RuntimeError if runner_outcome == "exception" else lw.LaunchWaveError
        with pytest.raises(expected):
            lw.run_wave_setup(
                wave_repo,
                config,
                launch=True,
                runner=runner,
                bus_dir=bus_dir,
            )

    assert not available_path.exists()
    assert not claimed_path.exists()


@pytest.mark.parametrize(
    "missing_authority",
    ["routing", "packet_worktree", "packet_index", "candidate_spec"],
)
def test_dispatch_terminal_receipt_refuses_missing_hash_authority(
    wave_repo,
    missing_authority,
):
    _write_fake_indicator_collector(wave_repo)
    config = _post_commit_authority_config_for_repo(wave_repo)
    bus_dir = f".agent_bus-unhashable-{missing_authority}"
    available_path, claimed_path = _terminal_receipt_paths(wave_repo, bus_dir)

    def runner(cmd, **_kwargs):
        packet_path = wave_repo / config.tracked_packet
        packet_path.write_text(
            _phase_b_locked_implementing_packet_content(config),
            encoding="utf-8",
        )
        _git(wave_repo, "add", "--", "TASKS.md", config.tracked_packet)
        routing_path = ec.routing_record_path(wave_repo, bus_dir)
        routing = json.loads(routing_path.read_text(encoding="utf-8"))
        spec_path = Path(routing["candidate_authority"]["spec_path"])
        if missing_authority == "routing":
            routing_path.unlink()
        elif missing_authority == "packet_worktree":
            packet_path.unlink()
        elif missing_authority == "packet_index":
            subprocess.run(
                ["git", "update-index", "--force-remove", "--", config.tracked_packet],
                cwd=wave_repo,
                check=True,
            )
        else:
            spec_path.unlink()
        return subprocess.CompletedProcess(cmd, 19)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=runner,
            bus_dir=bus_dir,
        )

    assert not available_path.exists()
    assert not claimed_path.exists()


@pytest.mark.parametrize("clarification", [False, True], ids=["base", "clarification"])
def test_exact_phase_b_terminal_receipt_resumes_once_without_phase_a_or_producers(
    wave_repo,
    monkeypatch,
    clarification,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-phase-b-positive-{clarification}",
        clarification=clarification,
    )
    config = state["config"]
    bridge_path = _write_phase_b_resume_bridge(
        wave_repo,
        state["bus_dir"],
    )
    bridge_before = bridge_path.read_bytes()
    authority_before = _phase_b_resume_authority_snapshot(wave_repo, state)
    terminal_payload = json.loads(
        state["available_path"].read_text(encoding="utf-8")
    )
    events = []
    real_setup_bridge = lw.setup_bridge_config
    real_setup_max_turns = lw.setup_bridge_max_turns_override

    def setup_bridge(repo_root, *, bus_dir=None):
        assert not state["available_path"].exists()
        assert state["claimed_path"].is_file()
        events.append("setup_bridge_config")
        return real_setup_bridge(repo_root, bus_dir=bus_dir)

    def setup_max_turns(repo_root, proposed, *, bus_dir=None):
        assert events == ["setup_bridge_config"]
        assert state["claimed_path"].is_file()
        events.append("setup_bridge_max_turns_override")
        return real_setup_max_turns(repo_root, proposed, bus_dir=bus_dir)

    def runner(cmd, **kwargs):
        events.append("runner")
        assert json.loads(
            state["claimed_path"].read_text(encoding="utf-8")
        ) == terminal_payload
        assert not state["available_path"].exists()
        assert cmd == lw.build_phase_b_dispatch_command(
            wave_repo,
            config,
            bus_dir=state["bus_dir"],
        )
        assert cmd[2] == "phase-b"
        assert "--plan" in cmd
        assert cmd[cmd.index("--plan") + 1] == config.tracked_packet
        assert "--routing-record-path" in cmd
        assert cmd[cmd.index("--routing-record-path") + 1] == str(
            state["routing_path"]
        )
        assert "--bus-dir" in cmd
        assert cmd[cmd.index("--bus-dir") + 1] == state["bus_dir"]
        assert "--routing-record" not in cmd
        assert kwargs["cwd"] == str(wave_repo)
        env = kwargs["env"]
        assert env["RCX_IMPLEMENTER_AGENT_OVERRIDE"] == "codex"
        assert env["RCX_REVIEWER_AGENT_OVERRIDE"] == "codex"
        assert env["RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE"] == "codex"
        assert _phase_b_resume_authority_snapshot(wave_repo, state) == authority_before
        return subprocess.CompletedProcess(cmd, 0)

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", setup_bridge)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", setup_max_turns)

    result = lw.run_wave_setup(
        wave_repo,
        config,
        launch=True,
        runner=runner,
        bus_dir=state["bus_dir"],
    )

    assert events == [
        "setup_bridge_config",
        "setup_bridge_max_turns_override",
        "runner",
    ]
    assert result.launch["launched"] is True
    assert result.launch["returncode"] == 0
    assert result.tracker_note_written is False
    assert bridge_path.read_bytes() == bridge_before
    assert _phase_b_resume_authority_snapshot(wave_repo, state) == authority_before
    assert not state["available_path"].exists()
    assert not state["claimed_path"].exists()

    repeat_calls = []
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=lambda *args, **kwargs: repeat_calls.append((args, kwargs)),
            bus_dir=state["bus_dir"],
        )
    assert repeat_calls == []


@pytest.mark.parametrize(
    "receipt_case",
    [
        "malformed-json",
        "extra-key",
        "missing-key",
        "version",
        "state",
        "wave-id",
        "task-id",
        "tracked-packet",
        "native-digest",
        "route-path",
        "route-sha",
        "worktree-sha",
        "index-sha",
        "candidate-path",
        "candidate-sha",
        "zero-returncode",
        "bool-returncode",
    ],
)
def test_phase_b_resume_rejects_every_terminal_receipt_mismatch_before_bridge_mutation(
    wave_repo,
    monkeypatch,
    receipt_case,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-bad-receipt-{receipt_case}",
    )
    bridge_path = _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    if receipt_case == "malformed-json":
        state["available_path"].write_text("{not-json", encoding="utf-8")
    else:
        def mutate(payload):
            if receipt_case == "extra-key":
                payload["unexpected"] = True
            elif receipt_case == "missing-key":
                payload.pop("wave_id")
            elif receipt_case == "version":
                payload["version"] = 2
            elif receipt_case == "state":
                payload["state"] = "claimed"
            elif receipt_case == "wave-id":
                payload["wave_id"] = "other-wave"
            elif receipt_case == "task-id":
                payload["task_id"] = "[OTHER]"
            elif receipt_case == "tracked-packet":
                payload["tracked_packet"] = "reports/control_plane/other.md"
            elif receipt_case == "native-digest":
                payload["native_stub_packet_contract_digest"] = "0" * 64
            elif receipt_case == "route-path":
                payload["routing_record_path"] = ".agent_bus-other/meta/post_merge_routing.json"
            elif receipt_case == "route-sha":
                payload["routing_record_sha256"] = "0" * 64
            elif receipt_case == "worktree-sha":
                payload["packet_worktree_sha256"] = "0" * 64
            elif receipt_case == "index-sha":
                payload["packet_index_sha256"] = "0" * 64
            elif receipt_case == "candidate-path":
                payload["candidate_authority_spec_path"] = ".agent_bus-other/spec.json"
            elif receipt_case == "candidate-sha":
                payload["candidate_authority_spec_sha256"] = "0" * 64
            elif receipt_case == "zero-returncode":
                payload["returncode"] = 0
            elif receipt_case == "bool-returncode":
                payload["returncode"] = True
            else:
                raise AssertionError(receipt_case)

        _rewrite_json(state["available_path"], mutate)

    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])
    producer_calls = []

    def forbidden(*args, **kwargs):
        producer_calls.append((args, kwargs))
        raise AssertionError("invalid receipt must fail before bridge mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert producer_calls == []
    assert bridge_path.is_file()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before
    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()


@pytest.mark.parametrize(
    "receipt_state",
    ["missing", "already-claimed", "available-symlink", "claimed-symlink"],
)
def test_phase_b_resume_refuses_missing_preclaimed_or_symlink_receipt_before_bridge(
    wave_repo,
    monkeypatch,
    receipt_state,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-receipt-state-{receipt_state}",
    )
    bridge_path = _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    original = state["available_path"].read_bytes()
    target = state["available_path"].with_name("terminal-receipt-target.json")
    if receipt_state == "missing":
        state["available_path"].unlink()
    elif receipt_state == "already-claimed":
        state["claimed_path"].write_bytes(original)
    elif receipt_state == "available-symlink":
        state["available_path"].unlink()
        target.write_bytes(original)
        state["available_path"].symlink_to(target.name)
    elif receipt_state == "claimed-symlink":
        target.write_bytes(original)
        state["claimed_path"].symlink_to(target.name)
    else:
        raise AssertionError(receipt_state)

    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("invalid receipt state must fail before mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert calls == []
    assert bridge_path.is_file()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before


def test_phase_b_index_only_advanced_state_without_receipt_never_falls_through(
    wave_repo,
    monkeypatch,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=".agent_bus-index-only-no-receipt",
    )
    bridge_path = _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    state["available_path"].unlink()
    state["packet_path"].unlink()
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("indexed Phase B authority must refuse before mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert calls == []
    assert bridge_path.is_file()
    assert not state["packet_path"].exists()
    assert not state["available_path"].exists()
    assert not state["claimed_path"].exists()


def test_phase_b_available_receipt_without_packet_never_falls_through(
    wave_repo,
    monkeypatch,
):
    state = _prepare_native_phase_b_terminal_state(wave_repo)
    _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    state["packet_path"].unlink()
    _git(wave_repo, "update-index", "--force-remove", "--", state["config"].tracked_packet)
    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])

    def forbidden(*_args, **_kwargs):
        raise AssertionError("missing packet must refuse before setup or dispatch")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before


def _invalid_phase_b_packet_content(valid, case):
    start = "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->"
    heading = "## Phase B Indicator Scope Reconciliation"
    end = "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->"
    block = valid[valid.index(start) :]
    if case == "phase-a-status":
        return valid.replace(
            "Status: Phase B (locked, implementing)",
            "Status: Phase A (design -- not yet agent-reviewed or bridge-converged)",
            1,
        )
    if case == "duplicate-status":
        return valid.replace(
            "Status: Phase B (locked, implementing)",
            "Status: Phase B (locked, implementing)\n"
            "Status: Phase B (locked, implementing)",
            1,
        )
    if case == "pre-supervisor-status":
        return valid.replace(
            "Status: Phase B (locked, implementing)",
            "Status: Phase B (pre-supervisor pending, bridge-converged)",
            1,
        )
    if case == "implemented-pending-status":
        return valid.replace(
            "Status: Phase B (locked, implementing)",
            "Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT",
            1,
        )
    if case == "implemented-local-status":
        return valid.replace(
            "Status: Phase B (locked, implementing)",
            "Status: IMPLEMENTED / LOCAL EVIDENCE",
            1,
        )
    if case == "missing-lock":
        return valid.replace("Phase-A-Lock: LOCKED\n", "", 1)
    if case == "unlocked":
        return valid.replace("Phase-A-Lock: LOCKED", "Phase-A-Lock: UNLOCKED", 1)
    if case == "duplicate-lock":
        return valid.replace(
            "Phase-A-Lock: LOCKED",
            "Phase-A-Lock: LOCKED\nPhase-A-Lock: LOCKED",
            1,
        )
    if case == "duplicate-indicator":
        return valid.rstrip() + "\n\n" + block
    if case == "missing-indicator":
        return valid[: valid.index(start)].rstrip() + "\n"
    if case == "missing-indicator-start":
        return valid.replace(f"{start}\n", "", 1)
    if case == "missing-indicator-end":
        return valid.replace(end, "", 1)
    if case == "indicator-out-of-order":
        return valid.replace(f"{start}\n{heading}", f"{heading}\n{start}", 1)
    if case == "indicator-end-before-start":
        return valid.replace(start, "<!-- __indicator_placeholder__ -->", 1).replace(
            end,
            start,
            1,
        ).replace("<!-- __indicator_placeholder__ -->", end, 1)
    if case == "unknown-machine-marker":
        return valid.replace(
            start,
            "<!-- UNKNOWN_PHASE_B_MACHINE_BLOCK:start -->\n"
            "<!-- UNKNOWN_PHASE_B_MACHINE_BLOCK:end -->\n"
            f"{start}",
            1,
        )
    if case == "unknown-h2":
        return valid.rstrip() + "\n\n## Unknown Machine Authority\n\n- no\n"
    if case == "base-h2-out-of-order":
        first, second = "## Scope", "## Work items"
        return valid.replace(first, "## __first_placeholder__", 1).replace(
            second,
            first,
            1,
        ).replace("## __first_placeholder__", second, 1)
    if case == "duplicate-base-h2":
        first = "## Scope"
        return valid.replace(first, f"{first}\n\n{first}", 1)
    if case == "tail-after-indicator":
        return valid.rstrip() + "\n\nOut-of-order authority tail.\n"
    if case == "duplicate-clarification":
        clarification = (
            "## Non-normative review clarification\n\n"
            "This optional section carries no machine or scope authority.\n"
        )
        return valid.rstrip() + "\n\n" + clarification
    reserved_blocks = {
        "commit-generated": (
            "<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->",
            "## Commit-Time Generated Governance Authorization",
            "<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->",
        ),
        "deferred": (
            "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->",
            "## Same-Wave Deferred Non-Blocking Authorization",
            "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->",
        ),
        "commit-path": (
            "<!-- COMMIT_PATH_TRUTH_REFRESH:start -->",
            "## Commit Path Truth Refresh",
            "<!-- COMMIT_PATH_TRUTH_REFRESH:end -->",
        ),
    }
    if case in reserved_blocks:
        reserved_start, reserved_heading, reserved_end = reserved_blocks[case]
        return (
            valid.rstrip()
            + f"\n\n{reserved_start}\n{reserved_heading}\n\n- no\n{reserved_end}\n"
        )
    if case == "l4-tracker":
        return (
            valid.rstrip()
            + "\n\n<!-- L4_FIELDS_FROM_TRACKER:start -->\n"
            "- target_gate_id: G8\n"
            "<!-- L4_FIELDS_FROM_TRACKER:end -->\n"
        )
    raise AssertionError(case)


@pytest.mark.parametrize(
    "packet_case",
    [
        "phase-a-status",
        "duplicate-status",
        "pre-supervisor-status",
        "implemented-pending-status",
        "implemented-local-status",
        "missing-lock",
        "unlocked",
        "duplicate-lock",
        "duplicate-indicator",
        "missing-indicator",
        "missing-indicator-start",
        "missing-indicator-end",
        "indicator-out-of-order",
        "indicator-end-before-start",
        "unknown-machine-marker",
        "unknown-h2",
        "base-h2-out-of-order",
        "duplicate-base-h2",
        "tail-after-indicator",
        "duplicate-clarification",
        "commit-generated",
        "deferred",
        "l4-tracker",
        "commit-path",
    ],
)
def test_phase_b_resume_rejects_every_noncanonical_status_or_machine_block_before_claim(
    wave_repo,
    monkeypatch,
    packet_case,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-bad-packet-{packet_case}",
        clarification=(packet_case == "duplicate-clarification"),
    )
    bridge_path = _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    valid = state["packet_path"].read_text(encoding="utf-8")
    state["packet_path"].write_text(
        _invalid_phase_b_packet_content(valid, packet_case),
        encoding="utf-8",
    )
    _git(wave_repo, "add", "--", state["config"].tracked_packet)
    _rewrite_terminal_receipt_packet_hashes(state)
    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])
    bridge_calls = []

    def forbidden(*args, **kwargs):
        bridge_calls.append((args, kwargs))
        raise AssertionError("invalid packet must fail before bridge mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert bridge_calls == []
    assert bridge_path.is_file()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before
    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()


@pytest.mark.parametrize(
    "authority_case",
    [
        "config",
        "route-decision",
        "launch-authority",
        "native-envelope",
        "tracker-note",
        "candidate-spec",
        "worktree-index-mismatch",
        "missing-worktree",
        "missing-index",
        "extra-same-wave-packet",
        "outside-candidate-scope",
    ],
)
def test_phase_b_resume_rejects_each_immutable_authority_mismatch_before_bridge_mutation(
    wave_repo,
    monkeypatch,
    authority_case,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-bad-authority-{authority_case}",
    )
    config = state["config"]
    proposed = config
    bridge_path = _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    if authority_case == "config":
        proposed = dataclasses.replace(config, work_items=["changed authority"])
    elif authority_case == "route-decision":
        _rewrite_json(
            state["routing_path"],
            lambda payload: payload.__setitem__("decision", "ROUTE_PHASE_B"),
        )
    elif authority_case == "launch-authority":
        _rewrite_json(
            state["routing_path"],
            lambda payload: payload[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY].__setitem__(
                "pager_route", "claude"
            ),
        )
    elif authority_case == "native-envelope":
        _rewrite_json(
            state["routing_path"],
            lambda payload: payload[lw.NATIVE_STUB_PACKET_CONTRACT_KEY].__setitem__(
                "digest", "0" * 64
            ),
        )
    elif authority_case == "tracker-note":
        state["tasks_path"].write_text(
            state["tasks_path"].read_text(encoding="utf-8").replace(
                f", {config.wave_id}):",
                ", other-wave):",
                1,
            ),
            encoding="utf-8",
        )
        _git(wave_repo, "add", "--", "TASKS.md")
    elif authority_case == "candidate-spec":
        _rewrite_json(
            state["spec_path"],
            lambda payload: payload.__setitem__("reviewer_agent", "claude"),
        )
    elif authority_case == "worktree-index-mismatch":
        state["packet_path"].write_text(
            state["packet_path"].read_text(encoding="utf-8").replace(
                "\n<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->",
                "\n## Non-normative review clarification\n\n"
                "Worktree-only clarification.\n\n"
                "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->",
                1,
            ),
            encoding="utf-8",
        )
        _rewrite_terminal_receipt_packet_hashes(state)
    elif authority_case == "missing-worktree":
        state["packet_path"].unlink()
    elif authority_case == "missing-index":
        subprocess.run(
            ["git", "update-index", "--force-remove", "--", config.tracked_packet],
            cwd=wave_repo,
            check=True,
        )
    elif authority_case == "extra-same-wave-packet":
        extra = (
            wave_repo
            / "reports"
            / "control_plane"
            / f"{config.wave_id}_other.md"
        )
        extra.write_text(state["packet_path"].read_text(encoding="utf-8"), encoding="utf-8")
    elif authority_case == "outside-candidate-scope":
        (wave_repo / "outside.txt").write_text("outside\n", encoding="utf-8")
        _git(wave_repo, "add", "--", "outside.txt")
    else:
        raise AssertionError(authority_case)

    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])
    bridge_calls = []

    def forbidden(*args, **kwargs):
        bridge_calls.append((args, kwargs))
        raise AssertionError("authority mismatch must fail before bridge mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            proposed,
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert bridge_calls == []
    assert bridge_path.is_file()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before
    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()


@pytest.mark.parametrize(
    "forbidden_case",
    ["handoff", "commit-continuation", "reader", "reviewer", "sdk-running"],
)
def test_phase_b_resume_forbidden_lifecycle_evidence_is_read_only_and_preclaim(
    wave_repo,
    monkeypatch,
    forbidden_case,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-forbidden-{forbidden_case}",
    )
    config = state["config"]
    _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    if forbidden_case == "handoff":
        artifact = ec.agent_bus_path(
            wave_repo,
            state["bus_dir"],
            "executors",
            "phase_b_handoff.json",
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"sentinel":"handoff"}\n', encoding="utf-8")
    elif forbidden_case == "commit-continuation":
        artifact = ec.agent_bus_path(
            wave_repo,
            state["bus_dir"],
            "executors",
            f"commit_executor_{config.wave_id}.json",
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"sentinel":"continuation"}\n', encoding="utf-8")
    elif forbidden_case in {"reader", "reviewer"}:
        artifact = wave_repo / state["bus_dir"] / "bridge.db"
        conn = sqlite3.connect(artifact)
        conn.execute("CREATE TABLE jobs (job_id TEXT, status TEXT)")
        status = "READER_RUNNING" if forbidden_case == "reader" else "REVIEWER_RUNNING"
        conn.execute("INSERT INTO jobs VALUES (?, ?)", (f"{forbidden_case}-job", status))
        conn.commit()
        conn.close()
    else:
        artifact = wave_repo / ".scratch" / "phase_b_agent_review_r4.status.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps({"status": "running", "running_agents": ["verifier"]}) + "\n",
            encoding="utf-8",
        )
    artifact_before = artifact.read_bytes()
    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])
    bridge_calls = []

    def forbidden(*args, **kwargs):
        bridge_calls.append((args, kwargs))
        raise AssertionError("active lifecycle evidence must refuse before mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            config,
            launch=True,
            runner=forbidden,
            bus_dir=state["bus_dir"],
        )

    assert bridge_calls == []
    assert artifact.read_bytes() == artifact_before
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before
    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()


@pytest.mark.parametrize("reset_to_unlocked", [False, True], ids=["locked", "unlocked"])
@pytest.mark.parametrize("runner_outcome", ["runtime-error", "keyboard", "none"])
def test_phase_b_resume_interruption_leaves_claimed_and_later_relaunch_fails_closed(
    wave_repo,
    monkeypatch,
    runner_outcome,
    reset_to_unlocked,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-interrupted-{runner_outcome}",
    )
    _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    terminal_payload = json.loads(
        state["available_path"].read_text(encoding="utf-8")
    )

    def runner(cmd, **_kwargs):
        assert state["claimed_path"].is_file()
        assert not state["available_path"].exists()
        if runner_outcome == "runtime-error":
            raise RuntimeError("unexpected runner failure")
        if runner_outcome == "keyboard":
            raise KeyboardInterrupt()
        return type("Running", (), {"returncode": None})()

    expected = {
        "runtime-error": RuntimeError,
        "keyboard": KeyboardInterrupt,
        "none": lw.LaunchWaveError,
    }[runner_outcome]
    with pytest.raises(expected):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=runner,
            bus_dir=state["bus_dir"],
        )

    assert not state["available_path"].exists()
    assert json.loads(state["claimed_path"].read_text(encoding="utf-8")) == terminal_payload
    if reset_to_unlocked:
        state["packet_path"].write_text(
            lw.render_wave_packet(state["config"]), encoding="utf-8"
        )
        _git(wave_repo, "add", "--", state["config"].tracked_packet)
    before = _post_commit_resume_snapshot(wave_repo, state["bus_dir"])

    def forbidden(*_args, **_kwargs):
        raise AssertionError("an interrupted claim must refuse before bridge mutation")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)
    repeated_calls = []
    with pytest.raises(lw.LaunchWaveError, match="already claimed"):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=lambda *args, **kwargs: repeated_calls.append((args, kwargs)),
            bus_dir=state["bus_dir"],
        )
    assert repeated_calls == []
    assert state["claimed_path"].is_file()
    assert _post_commit_resume_snapshot(wave_repo, state["bus_dir"]) == before


def test_phase_b_resume_normal_nonzero_replaces_claim_with_new_available_receipt(
    wave_repo,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=".agent_bus-phase-b-nonzero-replacement",
        returncode=73,
    )
    _write_phase_b_resume_bridge(wave_repo, state["bus_dir"])
    first = json.loads(state["available_path"].read_text(encoding="utf-8"))

    def runner(cmd, **_kwargs):
        assert state["claimed_path"].is_file()
        assert not state["available_path"].exists()
        return subprocess.CompletedProcess(cmd, 29)

    with pytest.raises(lw.LaunchWaveError, match="dispatcher launch failed"):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=runner,
            bus_dir=state["bus_dir"],
        )

    assert state["available_path"].is_file()
    assert not state["claimed_path"].exists()
    second = json.loads(state["available_path"].read_text(encoding="utf-8"))
    assert second == {**first, "returncode": 29}


@pytest.mark.parametrize("bridge_case", ["absent", "malformed", "non-object"])
def test_phase_b_resume_bridge_failure_occurs_after_claim_and_before_dispatch(
    wave_repo,
    bridge_case,
):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=f".agent_bus-phase-b-bridge-{bridge_case}",
    )
    bridge_path = ec.bridge_config_path(wave_repo, state["bus_dir"])
    bridge_before = None
    if bridge_case == "malformed":
        bridge_path.write_text("{not-json", encoding="utf-8")
        bridge_before = bridge_path.read_bytes()
    elif bridge_case == "non-object":
        bridge_path.write_text("[]\n", encoding="utf-8")
        bridge_before = bridge_path.read_bytes()
    dispatch_calls = []

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=lambda *args, **kwargs: dispatch_calls.append((args, kwargs)),
            bus_dir=state["bus_dir"],
        )

    assert dispatch_calls == []
    assert not state["available_path"].exists()
    assert state["claimed_path"].is_file()
    if bridge_case == "absent":
        assert not bridge_path.exists()
    else:
        assert bridge_path.read_bytes() == bridge_before


@pytest.mark.parametrize("selected_source", [0, 1, 2])
def test_phase_b_resume_bridge_seed_uses_first_existing_declared_source_after_claim(
    wave_repo,
    monkeypatch,
    selected_source,
):
    carrier = (
        wave_repo.parent
        / f"{wave_repo.name}-phase-b-seed-carrier-{selected_source}"
    )
    _git(
        wave_repo,
        "worktree",
        "add",
        "-q",
        "-b",
        f"phase-b-seed-carrier-{selected_source}",
        str(carrier),
    )
    (carrier / ".gitignore").write_text(
        ".agent_bus\n.agent_bus-*\n",
        encoding="utf-8",
    )
    _git(carrier, "add", "--", ".gitignore")
    _git(carrier, "commit", "-q", "-m", "ignore runtime buses")
    state = _prepare_native_phase_b_terminal_state(
        carrier,
        bus_dir=f".agent_bus-phase-b-seed-order-{selected_source}",
    )
    active_path = ec.bridge_config_path(carrier, state["bus_dir"])
    assert not active_path.exists()
    sources = [
        ec.bridge_config_path(carrier),
        ec.bridge_config_path(wave_repo, state["bus_dir"]),
        ec.bridge_config_path(wave_repo),
    ]
    for index, source in enumerate(sources[selected_source:], start=selected_source):
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(
                {
                    "agents": {
                        "sentinel": {
                            "cmd": ["python3", f"seed-{index}.py"],
                            "display_name": f"Seed {index}",
                            "mode": "live",
                        }
                    },
                    "selected_seed": index,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    _forbid_phase_b_resume_producers(monkeypatch)
    runner_observed = []

    def runner(cmd, **_kwargs):
        assert state["claimed_path"].is_file()
        runner_observed.append(
            json.loads(active_path.read_text(encoding="utf-8"))["selected_seed"]
        )
        return subprocess.CompletedProcess(cmd, 0)

    result = lw.run_wave_setup(
        carrier,
        state["config"],
        launch=True,
        runner=runner,
        bus_dir=state["bus_dir"],
    )

    assert result.launch["returncode"] == 0
    assert runner_observed == [selected_source]
    assert json.loads(active_path.read_text(encoding="utf-8"))["selected_seed"] == (
        selected_source
    )


def test_phase_b_resume_preserves_live_bridge_fields_and_reconciles_only_defaults(
    wave_repo,
):
    executor_config = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    example_config = wave_repo / "mu" / "tools" / "agents" / "bridge_config.example.json"
    executor_config.parent.mkdir(parents=True, exist_ok=True)
    example_config.parent.mkdir(parents=True, exist_ok=True)
    executor_config.write_text(
        json.dumps(
            {
                "role_agents": {"implementer": "codex", "reviewer": "codex"},
                "bridge_agent_defaults": {
                    "claude": {
                        "display_name": "Claude Current",
                        "model": "claude-current",
                        "effort": "high",
                    },
                    "codex": {
                        "display_name": "Codex Current",
                        "model": "gpt-current",
                        "reasoning_effort": "xhigh",
                    },
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    example_config.write_text(
        json.dumps(
            {
                "agents": {
                    "claude": {
                        "cmd": ["claude", "--model", "example", "--max-turns", "88"],
                    },
                    "codex": {
                        "cmd": [
                            "codex",
                            "exec",
                            "-",
                            "-m",
                            "example",
                            "-c",
                            'model_reasoning_effort="low"',
                            "--sandbox",
                            "danger-full-access",
                        ],
                        "display_name": "Codex Example",
                        "mode": "live",
                        "prompt_via_stdin": True,
                        "timeout_s": 1200,
                        "env": {"EXAMPLE": "kept"},
                        "seed_only": {"keep": True},
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _git(
        wave_repo,
        "add",
        "--",
        executor_config.relative_to(wave_repo).as_posix(),
        example_config.relative_to(wave_repo).as_posix(),
    )
    _git(wave_repo, "commit", "-q", "-m", "bridge sync inputs")
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=".agent_bus-phase-b-bridge-sync",
    )
    live_agents = {
        "claude": {
            "cmd": [
                "claude",
                "--print",
                "--model",
                "stale",
                "--effort",
                "low",
                "--max-turns",
                "12",
                "--keep-arg",
                "keep-value",
            ],
            "display_name": "Claude Stale",
            "mode": "custom-mode",
            "prompt_via_stdin": False,
            "timeout_s": 321,
            "env": {"LIVE": "kept"},
            "unknown_agent_field": ["keep"],
        },
        "custom": {
            "cmd": ["python3", "custom.py", "--opaque", "value"],
            "display_name": "Custom",
            "mode": "custom",
            "prompt_via_stdin": True,
            "timeout_s": 654,
            "env": {"CUSTOM": "kept"},
            "unknown_agent_field": {"keep": True},
        },
    }
    bridge_path = _write_phase_b_resume_bridge(
        wave_repo,
        state["bus_dir"],
        agents=live_agents,
        invocation_unknown=["keep"],
    )
    runner_bridge = {}

    def runner(cmd, **_kwargs):
        assert state["claimed_path"].is_file()
        runner_bridge.update(json.loads(bridge_path.read_text(encoding="utf-8")))
        return subprocess.CompletedProcess(cmd, 0)

    result = lw.run_wave_setup(
        wave_repo,
        state["config"],
        launch=True,
        runner=runner,
        bus_dir=state["bus_dir"],
    )

    assert result.launch["returncode"] == 0
    assert state["config"].max_turns is None
    assert runner_bridge["unknown_top_level"] == {"keep": True}
    assert runner_bridge["invocation_unknown"] == ["keep"]
    claude = runner_bridge["agents"]["claude"]
    assert claude["cmd"] == [
        "claude",
        "--print",
        "--model",
        "claude-current",
        "--effort",
        "high",
        "--max-turns",
        "88",
        "--keep-arg",
        "keep-value",
    ]
    assert claude["display_name"] == "Claude Current"
    assert {key: claude[key] for key in (
        "mode",
        "prompt_via_stdin",
        "timeout_s",
        "env",
        "unknown_agent_field",
    )} == {
        "mode": "custom-mode",
        "prompt_via_stdin": False,
        "timeout_s": 321,
        "env": {"LIVE": "kept"},
        "unknown_agent_field": ["keep"],
    }
    assert runner_bridge["agents"]["custom"] == live_agents["custom"]
    codex = runner_bridge["agents"]["codex"]
    assert codex["cmd"] == [
        "codex",
        "exec",
        "-",
        "-m",
        "gpt-current",
        "-c",
        'model_reasoning_effort="xhigh"',
        "--sandbox",
        "danger-full-access",
    ]
    assert codex["display_name"] == "Codex Current"
    assert codex["mode"] == "live"
    assert codex["prompt_via_stdin"] is True
    assert codex["timeout_s"] == 1200
    assert codex["env"] == {"EXAMPLE": "kept"}
    assert codex["seed_only"] == {"keep": True}


def test_phase_b_terminal_receipt_is_bus_local(wave_repo, monkeypatch):
    state = _prepare_native_phase_b_terminal_state(
        wave_repo,
        bus_dir=".agent_bus-phase-b-bus-a",
    )
    bus_b = ".agent_bus-phase-b-bus-b"
    other_available, other_claimed = _terminal_receipt_paths(
        wave_repo,
        bus_b,
    )
    receipt_before = state["available_path"].read_bytes()
    lw.setup_routing_record(wave_repo, state["config"], bus_dir=bus_b)
    lw.setup_candidate_authority_spec(wave_repo, state["config"], bus_dir=bus_b)
    _write_phase_b_resume_bridge(wave_repo, bus_b)
    bus_b_before = _post_commit_resume_snapshot(wave_repo, bus_b)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a receipt from another bus must not authorize resume")

    _forbid_phase_b_resume_producers(monkeypatch)
    monkeypatch.setattr(lw, "setup_bridge_config", forbidden)
    monkeypatch.setattr(lw, "setup_bridge_max_turns_override", forbidden)

    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(
            wave_repo,
            state["config"],
            launch=True,
            runner=forbidden,
            bus_dir=bus_b,
        )

    assert calls == []
    assert state["available_path"].read_bytes() == receipt_before
    assert not state["claimed_path"].exists()
    assert not other_available.exists()
    assert not other_claimed.exists()
    assert _post_commit_resume_snapshot(wave_repo, bus_b) == bus_b_before


def test_launch_off_by_default_runs_no_subprocess(wave_repo):
    calls = []

    def runner(*a, **k):
        calls.append((a, k))
        raise AssertionError("runner must not be called when launch is off")

    result = lw.run_wave_setup(wave_repo, make_config(), runner=runner)
    assert calls == []
    assert result.launch["launched"] is False
    assert result.launch["command"][0] == sys.executable
    assert "executor_dispatch.py" in result.launch["command"][1]
    # Routing-mode argv, NOT the flat --wave-id/--plan form the dispatcher rejects.
    assert "--routing-record" in result.launch["command"]
    assert "--wave-id" not in result.launch["command"]
    assert "--plan" not in result.launch["command"]


def test_launch_invokes_runner_when_enabled(wave_repo):
    calls = []
    observed_authorities = []

    class _R:
        returncode = 0

    def runner(cmd, **k):
        calls.append(cmd)
        routing = json.loads(
            ec.routing_record_path(wave_repo).read_text(encoding="utf-8")
        )
        observed_authorities.append(
            routing[lw.LAUNCH_WAVE_OVERRIDE_AUTHORITY_KEY]
        )
        return _R()

    config = make_config()
    result = lw.run_wave_setup(
        wave_repo, config, launch=True, runner=runner
    )
    assert len(calls) == 1
    assert "executor_dispatch.py" in calls[0][1]
    assert "--routing-record" in calls[0]
    assert observed_authorities == [
        lw.build_launch_wave_override_authority(config)
    ]
    assert result.launch["launched"] is True
    assert result.launch["returncode"] == 0


def test_launch_omitted_pins_preserve_runner_environment_shape(wave_repo, monkeypatch):
    for key in _DISPATCHER_OVERRIDE_ENV_KEYS_FOR_TEST:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(wave_repo / "parent"))

    calls = []

    class _R:
        returncode = 0

    def runner(cmd, **k):
        calls.append(k)
        return _R()

    config = make_config()
    assert config.implementer_agent == ""
    assert config.reviewer_agent == ""
    assert config.pager_route == ""

    result = lw.run_wave_setup(wave_repo, config, launch=True, runner=runner)

    assert calls == [{"cwd": str(wave_repo)}]
    assert "environment_overrides" not in result.launch


def test_launch_partial_pins_scrub_stale_parent_override_env(wave_repo, monkeypatch):
    monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_REVIEWER_AGENT_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_BRIDGE_REVIEWER_OVERRIDE", "claude")
    monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", "/tmp/stale-root")
    monkeypatch.setenv("RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE", "claude")
    captured = {}

    class _R:
        returncode = 0

    def runner(cmd, **k):
        captured["kwargs"] = k
        return _R()

    result = lw.run_wave_setup(
        wave_repo,
        make_config(implementer_agent="codex"),
        launch=True,
        runner=runner,
    )

    env = captured["kwargs"]["env"]
    assert env["RCX_IMPLEMENTER_AGENT_OVERRIDE"] == "codex"
    assert env["RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT"] == str(wave_repo.resolve())
    assert "RCX_REVIEWER_AGENT_OVERRIDE" not in env
    assert "RCX_BRIDGE_REVIEWER_OVERRIDE" not in env
    assert "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE" not in env
    assert result.launch["environment_overrides"] == {
        "RCX_IMPLEMENTER_AGENT_OVERRIDE": "codex",
    }


def test_config_accepts_valid_role_and_pager_pins(wave_repo):
    config = make_config(
        implementer_agent="codex",
        reviewer_agent="codex",
        pager_route="codex",
    )
    assert config.validate(wave_repo) == []


def test_config_accepts_valid_max_turns_override(wave_repo):
    assert make_config(max_turns=100).validate(wave_repo) == []


@pytest.mark.parametrize("bad_max_turns", [0, -1, 1.5, "50", True, 1001])
def test_config_rejects_invalid_max_turns_override(wave_repo, bad_max_turns):
    errors = make_config(max_turns=bad_max_turns).validate(wave_repo)
    assert any("max_turns" in error for error in errors)


def test_config_validation_uses_configured_bridge_agent_defaults(wave_repo):
    config_path = wave_repo / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "bridge_agent_defaults": {
                    "localcodex": {
                        "display_name": "Local Codex",
                        "model": "gpt-local",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert make_config(implementer_agent="localcodex").validate(wave_repo) == []


def test_config_rejects_invalid_role_and_pager_pins(wave_repo):
    config = make_config(
        implementer_agent="missing-impl",
        reviewer_agent="missing-reviewer",
        pager_route="pager-nowhere",
    )

    errors = config.validate(wave_repo)

    assert any("implementer_agent" in error for error in errors)
    assert any("reviewer_agent" in error for error in errors)
    assert any("pager_route" in error for error in errors)


def test_launch_threads_role_and_pager_pins_to_dispatcher_env(wave_repo):
    captured = {}

    class _R:
        returncode = 0

    def runner(cmd, **k):
        captured["cmd"] = cmd
        captured["kwargs"] = k
        return _R()

    result = lw.run_wave_setup(
        wave_repo,
        make_config(
            implementer_agent="codex",
            reviewer_agent="codex",
            pager_route="codex",
        ),
        launch=True,
        runner=runner,
    )

    env = captured["kwargs"]["env"]
    expected = {
        "RCX_IMPLEMENTER_AGENT_OVERRIDE": "codex",
        "RCX_REVIEWER_AGENT_OVERRIDE": "codex",
        "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE": "codex",
    }
    for key, value in expected.items():
        assert env[key] == value
    assert captured["kwargs"]["cwd"] == str(wave_repo)
    assert result.launch["environment_overrides"] == expected
    assert set(result.launch["environment_overrides"]) == set(expected)


def test_dispatch_command_targets_dispatcher_routing_mode(wave_repo):
    """The launch argv must be the dispatcher's routing-mode form.

    executor_dispatch exposes surface subcommands (phase-a/phase-b/...) and a
    default routing mode (``--routing-record <path>``). It has NO ``--wave-id``
    or top-level ``--plan`` flag and rejects them (bridge round 1 DEFECT). The
    builder must emit routing mode pointed at the same routing record the
    routing step writes, so the dispatcher consumes the record and routes to
    Phase A.
    """
    config = make_config()
    cmd = lw.build_dispatch_command(wave_repo, config)

    assert cmd[0] == sys.executable
    assert cmd[1].endswith("executor_dispatch.py")
    assert "--routing-record" in cmd
    # The argv carries the exact record path the routing step writes/reads.
    routing_path = str(ec.routing_record_path(wave_repo))
    assert cmd[cmd.index("--routing-record") + 1] == routing_path
    # The first token after the program is NOT a surface subcommand, so the
    # dispatcher takes its routing-mode branch.
    assert cmd[2] not in {"phase-a", "phase-b", "pre-commit-supervisor",
                          "commit", "post-merge-supervisor"}
    # None of the dispatcher-rejected flat flags are present.
    assert "--wave-id" not in cmd
    assert "--plan" not in cmd


def test_dispatch_command_threads_bus_dir(wave_repo):
    """A bus_dir override is forwarded to the dispatcher and the record path."""
    cmd = lw.build_dispatch_command(wave_repo, make_config(), bus_dir=".agent_bus-x7")
    assert "--bus-dir" in cmd
    assert cmd[cmd.index("--bus-dir") + 1] == ".agent_bus-x7"
    routing_path = str(ec.routing_record_path(wave_repo, ".agent_bus-x7"))
    assert cmd[cmd.index("--routing-record") + 1] == routing_path


def test_launch_fails_closed_on_dispatcher_failure(wave_repo):
    """A non-zero dispatcher returncode must raise, not report a launch.

    Bridge round 1 DEFECT: a failed dispatcher subprocess was reported as a
    completed launch ({'launched': True, 'returncode': 99}). The launcher must
    fail closed so a failed dispatcher can never look like a launched wave.
    """
    class _R:
        returncode = 99

    def runner(cmd, **k):
        return _R()

    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.run_wave_setup(wave_repo, make_config(), launch=True, runner=runner)
    assert "dispatcher launch failed" in str(exc.value)
    assert "99" in str(exc.value)


def test_maybe_launch_fails_closed_on_none_returncode(wave_repo):
    """A runner result with no/None returncode also fails closed (not a launch)."""
    class _R:
        returncode = None

    with pytest.raises(lw.LaunchWaveError):
        lw.maybe_launch_dispatcher(
            wave_repo, make_config(), launch=True, runner=lambda *a, **k: _R()
        )


# --------------------------------------------------------------------------- #
# Config + CLI                                                                #
# --------------------------------------------------------------------------- #


def test_config_validation_rejects_underscore_wave_id():
    config = make_config(
        wave_id="bad_wave_id",
        tracked_packet="reports/control_plane/bad_wave_id_2026-06-19.md",
    )
    errors = config.validate()
    assert any("normalized kebab id" in e for e in errors)


def test_config_validation_rejects_asterisk_title():
    config = make_config(title="Bad *Title*")
    assert any("asterisk-free" in e for e in config.validate())


def test_config_requires_explicit_date_no_wall_clock():
    """Bridge round 2 DEFECT: the builder must never derive 'date' from the wall
    clock -- that drifts tracked_packet across calendar days and orphans the
    earlier packet on a re-run. 'date' is a required, explicit input, and the
    module carries no wall-clock dependency at all.
    """
    # The module no longer imports/holds a wall clock (nothing to read or mock).
    assert not hasattr(lw, "datetime")

    # from_dict without 'date' -> missing required key (fail-closed), same class
    # of error as any other required field.
    data = dataclasses.asdict(make_config())
    data.pop("date", None)
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict(data)
    assert "missing required key" in str(exc.value)
    assert "date" in str(exc.value)


def test_config_rejects_blank_date():
    """A blank/whitespace date fails closed (no silent wall-clock fallback)."""
    with pytest.raises(lw.LaunchWaveError) as exc:
        make_config(date="")
    assert "date" in str(exc.value)
    with pytest.raises(lw.LaunchWaveError):
        make_config(date="   ")


def test_tracked_packet_is_deterministic_from_config_date():
    """The same config yields the same tracked_packet no matter when it runs.

    Refutes the cross-UTC-day duplicate packet: with date an explicit input (not
    the wall clock), the derived packet path is identical across re-constructions,
    so a re-run of the SAME config can never produce a second, date-shifted
    packet. A different explicit date is still honored deterministically.
    """
    p1 = make_config(date="2026-06-19").tracked_packet
    p2 = make_config(date="2026-06-19").tracked_packet
    assert (
        p1 == p2 == "reports/control_plane/demo-launcher-wave-2026-06-19_2026-06-19.md"
    )
    p3 = make_config(date="2026-06-20").tracked_packet
    assert p3 == "reports/control_plane/demo-launcher-wave-2026-06-19_2026-06-20.md"
    assert p3 != p1


def test_run_wave_setup_rejects_invalid_config(wave_repo):
    config = make_config(title="Bad *Title*")
    with pytest.raises(lw.LaunchWaveError):
        lw.run_wave_setup(wave_repo, config)


def test_from_dict_rejects_unknown_key():
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict({"wave_id": "w", "bogus": 1})
    assert "unknown key" in str(exc.value)


def test_from_dict_rejects_missing_required_key():
    with pytest.raises(lw.LaunchWaveError) as exc:
        lw.WaveConfig.from_dict({"wave_id": "demo-wave-2026-06-19"})
    assert "missing required key" in str(exc.value)


def test_cli_main_runs_setup_from_json_config(wave_repo, capsys):
    config = make_config()
    config_dict = {
        "wave_id": config.wave_id,
        "title": config.title,
        "task_id": config.task_id,
        "purpose": config.purpose,
        "wave_class": config.wave_class,
        "target_gate_id": config.target_gate_id,
        "primary_blocker_class": config.primary_blocker_class,
        "primary_invariant_id": config.primary_invariant_id,
        "indicator_artifact_ref": config.indicator_artifact_ref,
        "indicator_collection_command": config.indicator_collection_command,
        "evidence_command": config.evidence_command,
        "evidence_delta": config.evidence_delta,
        "progress_proof_before": config.progress_proof_before,
        "progress_proof_after": config.progress_proof_after,
        "scope_items": config.scope_items,
        "work_items": config.work_items,
        "constraints": config.constraints,
        "stop_conditions": config.stop_conditions,
        "acceptance_criteria": config.acceptance_criteria,
        "date": config.date,
    }
    config_file = wave_repo / "wave_config.json"
    config_file.write_text(json.dumps(config_dict), encoding="utf-8")

    rc = lw.main([str(config_file), "--repo-root", str(wave_repo)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["wave_id"] == config.wave_id
    assert out["precondition_ok"] is True
    assert out["guards_ok"] is True
    assert _artifact_counts(wave_repo, config.wave_id) == (1, 1, 1)
