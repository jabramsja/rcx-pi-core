from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
phase_a_mod = load_module(
    "phase_a_executor",
    _TOOLS_DIR / "executors" / "phase_a_executor.py",
)
# Single-source packet-L4 regression (wave: packet-l4-autopopulate-from-tracker-
# note-2026-06-08). The wave's declared evidence_command runs THIS file, so the
# refresh-path proof loads commit_executor here rather than in a new test file.
# phase_a_executor.create_plan_draft lazily `import commit_executor`, so registering
# it under that name now means the render path uses this same loaded instance.
commit_mod = load_module(
    "commit_executor",
    _TOOLS_DIR / "executors" / "commit_executor.py",
)
tracker_sync_note_mod = load_module(
    "tracker_sync_note",
    _TOOLS_DIR / "executors" / "tracker_sync_note.py",
)


def _write_phase_a_plan(repo: Path, *, plan_name: str = "pager_plan") -> Path:
    plan_dir = repo / "reports" / "control_plane"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan = plan_dir / f"{plan_name}.md"
    plan.write_text(
        "# Pager Plan\n"
        "Date: 2026-04-23\n"
        "Status: Phase A\n"
        "Task: [PIPELINE-AGENT-PAGER]\n"
        "Wave ID: pager-lifecycle-event-coverage-2026-04-23\n"
        "Phase-A-Lock: UNLOCKED\n"
        "\n"
        "## Scope\n"
        "Pager lifecycle events.\n"
        "## Work Items\n"
        "Emit lifecycle events.\n"
        "## Constraints\n"
        "No tmux scraping.\n"
        "## Stop Conditions\n"
        "Stop on non-authoritative state.\n"
        "## Acceptance Criteria\n"
        "Events are emitted.\n"
        "## Grounding / Authorization\n"
        "TASKS.md authorization.\n",
        encoding="utf-8",
    )
    return plan


def _fake_bridge(repo: Path, *, decision: str, exit_code: int = 0):
    def _run_bridge(repo_root, rel_plan_path, round_num, *, job_id, agent_review_context="", bus_dir=None):
        rendered = phase_a_mod.agent_bus_path(repo_root, bus_dir, "rendered", f"{job_id}.md")
        rendered.parent.mkdir(parents=True, exist_ok=True)
        rendered.write_text(f"Decision: {decision}\n", encoding="utf-8")
        return {"exit_code": exit_code, "stdout": decision, "stderr": "", "job_id": job_id}

    return _run_bridge


def test_create_plan_draft_writes_authoritative_routing_identity(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    plan = phase_a_mod.create_plan_draft(
        repo,
        "parallel_pipeline_agent_teams",
        {
            "request": "teammate worktrees",
            "summary": "agent teams",
            "task_id": "[PARALLEL-PIPELINE]",
            "wave_name": "parallel-pipeline-agent-teams",
        },
    )

    header = plan.read_text(encoding="utf-8").split("## Scope", 1)[0]
    assert "Task: [PARALLEL-PIPELINE]\n" in header
    assert "Wave ID: parallel-pipeline-agent-teams\n" in header
    assert header.index("Task: [PARALLEL-PIPELINE]") < header.index("Phase-A-Lock: UNLOCKED")


def test_extract_plan_scope_carries_bounded_candidate_detail():
    scope = phase_a_mod.extract_plan_scope(
        {
            "decision": "ROUTE_PHASE_A",
            "summary": "generic post-merge summary",
            "request_for_claude": "generic post-merge request",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": "founder-ordered-redteam-wave-packet-seed-2026-05-05",
            "next_candidates": [
                {
                    "candidate": "unbounded-background-item",
                    "bounded": False,
                    "summary": "must not be selected",
                    "request_for_claude": "must not leak into Phase A",
                },
                {
                    "candidate": "founder-ordered-redteam-wave-packet-seed-2026-05-05",
                    "bounded": True,
                    "summary": "create code/docs/tests/tooling audit packets",
                    "request_for_claude": "carry founder-ordered audit queue details into Phase A",
                },
            ],
        }
    )

    assert "generic post-merge request" in scope["request"]
    assert "carry founder-ordered audit queue details into Phase A" in scope["request"]
    assert "founder-ordered-redteam-wave-packet-seed-2026-05-05" in scope["request"]
    assert "must not leak into Phase A" not in scope["request"]
    assert "generic post-merge summary" in scope["summary"]
    assert "create code/docs/tests/tooling audit packets" in scope["summary"]
    assert scope["task_id"] == "[NEXT-CODEX-POST-REDTEAM]"


def test_lock_plan_inserts_missing_authoritative_routing_identity(tmp_path):
    repo = tmp_path / "repo"
    reports = repo / "reports" / "control_plane"
    reports.mkdir(parents=True)
    plan = reports / "parallel_pipeline_agent_teams.md"
    plan.write_text(
        "# Parallel Pipeline Agent Teams\n\n"
        "Date: 2026-04-30\n"
        "Status: Phase A\n"
        "Phase-A-Lock: UNLOCKED\n"
        "\n"
        "## Scope\n"
        "Task: narrative-only body value must not satisfy Phase B.\n",
        encoding="utf-8",
    )

    phase_a_mod.lock_plan(
        repo,
        "reports/control_plane/parallel_pipeline_agent_teams.md",
        routing_record={
            "task_id": "[PARALLEL-PIPELINE]",
            "wave_name": "parallel-pipeline-agent-teams",
        },
    )

    content = plan.read_text(encoding="utf-8")
    header = content.split("## Scope", 1)[0]
    assert "Task: [PARALLEL-PIPELINE]\n" in header
    assert "Wave ID: parallel-pipeline-agent-teams\n" in header
    assert "Phase-A-Lock: LOCKED\n" in header
    assert header.index("Wave ID: parallel-pipeline-agent-teams") < header.index("Phase-A-Lock: LOCKED")
    assert "Task: narrative-only body value" in content


def test_lock_plan_normalizes_review_sentinel_after_bridge_go(tmp_path):
    repo = tmp_path / "repo"
    reports = repo / "reports" / "control_plane"
    reports.mkdir(parents=True)
    plan = reports / "parallel_pipeline_agent_teams.md"
    plan.write_text(
        "# Parallel Pipeline Agent Teams\n\n"
        "Date: 2026-04-30\n"
        "Status: Phase A\n"
        "Task: [PARALLEL-PIPELINE]\n"
        "Wave ID: parallel-pipeline-agent-teams\n"
        "Phase-A-Lock: LOCKED_FOR_REVIEW\n"
        "\n"
        "## Scope\n"
        "Bridge-stage review sentinel.\n",
        encoding="utf-8",
    )

    phase_a_mod.lock_plan(
        repo,
        "reports/control_plane/parallel_pipeline_agent_teams.md",
        routing_record={
            "task_id": "[PARALLEL-PIPELINE]",
            "wave_name": "parallel-pipeline-agent-teams",
        },
    )

    header = plan.read_text(encoding="utf-8").split("## Scope", 1)[0]
    assert "Phase-A-Lock: LOCKED\n" in header
    assert "LOCKED_FOR_REVIEW" not in header
    assert "Status: Phase B (locked, implementing)\n" in header


def test_lock_plan_normalizes_pending_re_review_suffix_after_bridge_go(tmp_path):
    repo = tmp_path / "repo"
    reports = repo / "reports" / "control_plane"
    reports.mkdir(parents=True)
    plan = reports / "parallel_pipeline_agent_teams.md"
    plan.write_text(
        "# Parallel Pipeline Agent Teams\n\n"
        "Date: 2026-04-30\n"
        "Status: Phase A\n"
        "Task: [PARALLEL-PIPELINE]\n"
        "Wave ID: parallel-pipeline-agent-teams\n"
        "Phase-A-Lock: UNLOCKED pending bridge re-review\n"
        "\n"
        "## Scope\n"
        "Bridge-stage pending review sentinel.\n",
        encoding="utf-8",
    )

    phase_a_mod.lock_plan(
        repo,
        "reports/control_plane/parallel_pipeline_agent_teams.md",
        routing_record={
            "task_id": "[PARALLEL-PIPELINE]",
            "wave_name": "parallel-pipeline-agent-teams",
        },
    )

    header = plan.read_text(encoding="utf-8").split("## Scope", 1)[0]
    assert "Phase-A-Lock: LOCKED\n" in header
    assert "pending bridge re-review" not in header
    assert "Status: Phase B (locked, implementing)\n" in header


def test_run_phase_a_emits_entered_reviewer_and_go_events(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_phase_a_plan(repo)
    routing = {
        "decision": "ROUTE_PHASE_A",
        "task_id": "[PIPELINE-AGENT-PAGER]",
        "wave_name": "pager-lifecycle-event-coverage-2026-04-23",
    }
    pager_calls = []

    def fake_emit(repo_root, **kwargs):
        pager_calls.append(kwargs)
        return {"enabled": True, "event_id": kwargs["event_type"], "attempted": []}

    with patch.object(phase_a_mod, "load_routing_record", return_value=routing), \
         patch.object(phase_a_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
         patch.object(phase_a_mod, "run_sdk_agents", return_value={"exit_code": 0}), \
         patch.object(phase_a_mod, "run_bridge_design_review", side_effect=_fake_bridge(repo, decision="GO")), \
         patch.object(phase_a_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="aaaabbbbccccdddd"))):
        result = phase_a_mod.run_phase_a(repo, "pager_plan", max_bridge_rounds=1)

    assert result["status"] == "converged"
    assert [call["event_type"] for call in pager_calls] == [
        "phase_a_entered",
        "phase_a_reviewer_started",
        "phase_a_reviewer_completed",
        "phase_a_go",
    ]
    assert pager_calls[1]["transition_key"] == "phase-a-r1-aaaabbbb:reviewer_started"
    assert pager_calls[-1]["state"] == "go"


def test_run_phase_a_go_event_uses_namespaced_bus(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_phase_a_plan(repo)
    pager_calls = []

    def fake_emit(repo_root, **kwargs):
        pager_calls.append(kwargs)
        return {"enabled": True, "event_id": kwargs["event_type"], "attempted": []}

    with patch.object(phase_a_mod, "load_routing_record", return_value={"decision": "ROUTE_PHASE_A"}), \
         patch.object(phase_a_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
         patch.object(phase_a_mod, "run_sdk_agents", return_value={"exit_code": 0}), \
         patch.object(phase_a_mod, "run_bridge_design_review", side_effect=_fake_bridge(repo, decision="GO")), \
         patch.object(phase_a_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="bbbbccccddddeeee"))):
        result = phase_a_mod.run_phase_a(
            repo,
            "pager_plan",
            max_bridge_rounds=1,
            bus_dir=".agent_bus-test",
        )

    assert result["status"] == "converged"
    assert [call["event_type"] for call in pager_calls][-1] == "phase_a_go"
    assert {call["bus_dir"] for call in pager_calls} == {".agent_bus-test"}
    assert (repo / ".agent_bus-test" / "rendered" / "phase-a-r1-bbbbcccc.md").exists()
    assert not (repo / ".agent_bus" / "rendered" / "phase-a-r1-bbbbcccc.md").exists()


def test_run_phase_a_emits_question_fail_closed_event(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_phase_a_plan(repo)
    pager_calls = []

    def fake_emit(repo_root, **kwargs):
        pager_calls.append(kwargs)
        return {"enabled": True, "event_id": kwargs["event_type"], "attempted": []}

    with patch.object(phase_a_mod, "load_routing_record", return_value={"decision": "ROUTE_PHASE_A"}), \
         patch.object(phase_a_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
         patch.object(phase_a_mod, "run_sdk_agents", return_value={"exit_code": 0}), \
         patch.object(phase_a_mod, "run_bridge_design_review", side_effect=_fake_bridge(repo, decision="QUESTION", exit_code=1)), \
         patch.object(phase_a_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="1111222233334444"))):
        result = phase_a_mod.run_phase_a(repo, "pager_plan", max_bridge_rounds=1)

    assert result["status"] == "error"
    assert result["error"] == "Bridge returned QUESTION decision — requires human resolution"
    assert [call["event_type"] for call in pager_calls][-1] == "phase_a_question"
    assert pager_calls[-1]["transition_key"] == "phase-a-r1-11112222:question"


def test_run_phase_a_emits_implementer_transition_and_no_go_event(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_phase_a_plan(repo)
    pager_calls = []

    def fake_emit(repo_root, **kwargs):
        pager_calls.append(kwargs)
        return {"enabled": True, "event_id": kwargs["event_type"], "attempted": []}

    implementer_bus_dirs = []

    def fake_implementer(repo_root, prompt, *, backend, timeout, verbose, bus_dir=None):
        implementer_bus_dirs.append(bus_dir)
        plan = repo_root / "reports" / "control_plane" / "pager_plan.md"
        plan.write_text(plan.read_text(encoding="utf-8") + "\nImplementation note.\n", encoding="utf-8")
        return {"status": "success", "exit_code": 0, "stderr": ""}

    raw_dir = repo / ".agent_bus-test" / "raw" / "phase-a-r1-99990000"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "reviewer.txt").write_text(
        "BEGIN_AGENT_ENVELOPE\n"
        '{"findings":[{"title":"missing scope","severity":"critical","disposition":"blocking"}]}\n'
        "END_AGENT_ENVELOPE\n",
        encoding="utf-8",
    )

    with patch.object(phase_a_mod, "load_routing_record", return_value={"decision": "ROUTE_PHASE_A"}), \
         patch.object(phase_a_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
         patch.object(phase_a_mod, "run_sdk_agents", return_value={"exit_code": 0}), \
         patch.object(phase_a_mod, "run_bridge_design_review", side_effect=_fake_bridge(repo, decision="NO_GO", exit_code=1)), \
         patch.object(phase_a_mod, "_invoke_implementer", side_effect=fake_implementer), \
         patch.object(phase_a_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="99990000aaaabbbb"))):
        result = phase_a_mod.run_phase_a(repo, "pager_plan", max_bridge_rounds=1, bus_dir=".agent_bus-test")

    assert result["status"] == "max_rounds_reached"
    assert implementer_bus_dirs == [".agent_bus-test"]
    assert "phase_a_implementer_started" in [call["event_type"] for call in pager_calls]
    assert "phase_a_implementer_completed" in [call["event_type"] for call in pager_calls]
    assert [call["event_type"] for call in pager_calls][-1] == "phase_a_no_go"
    assert {call["bus_dir"] for call in pager_calls} == {".agent_bus-test"}


# ---------------------------------------------------------------------------
# Single-source packet L4-field block (wave packet-l4-autopopulate-from-tracker-
# note-2026-06-08). The control-plane packet's L4-field block must AUTO-DERIVE
# from the wave's canonical TASKS.md tracker note (the source of truth the #52
# supervisor + bot read) at BOTH render (phase_a_executor.create_plan_draft) and
# refresh (commit_executor.refresh_commit_path_packet_truth). The note wins on any
# divergence -- the packet can never declare an L4 value the note does not.
# ---------------------------------------------------------------------------

_PACKET_L4_WAVE = "packet-l4-autopopulate-from-tracker-note-2026-06-08"


def _canonical_packet_l4_tracker_note(
    wave_id: str = _PACKET_L4_WAVE,
    *,
    primary_blocker_class: str = "INTEGRATION",
) -> str:
    """Build a canonical L4_ENABLER tracker note declaring a known L4-field set X."""
    fields = tracker_sync_note_mod.TrackerSyncNoteFields(
        wave_id=wave_id,
        title="Packet L4 autopopulate from tracker note",
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        # Emit `Packet: ...` right after target_gate_id (the real note shape). The
        # default boundary list omits `Packet`, so a naive extractor over-captures
        # the packet path into target_gate_id; the derived block must not.
        packet_ref=f"reports/control_plane/{wave_id.replace('-', '_')}.md",
        primary_blocker_class=primary_blocker_class,
        primary_invariant_id="INV_TYPED_FAIL_CLOSED_OUTCOMES",
        indicator_artifact_ref=f"reports/l4_wave_indicators/{wave_id}.json",
        indicator_collection_command=(
            "python3 mu/tools/metrics/collect_l4_wave_indicators.py "
            f"--wave-id {wave_id} --output reports/l4_wave_indicators/{wave_id}.json"
        ),
        evidence_command=(
            "PYTHONHASHSEED=0 python3 -m pytest -q "
            "mu/tests/tools/test_phase_a_executor.py -k 'packet and (l4 or tracker)'"
        ),
        evidence_delta="packet L4 block now single-sources from the tracker note",
        progress_proof_before="packet/note L4 drift was possible",
        progress_proof_after="packet L4 block is note-derived",
        boot0_track_id="V1",
        boot0_progress_state="HOLD",
        date="2026-06-09",
    )
    return tracker_sync_note_mod.render_tracker_sync_note(fields)


def _l4_block_region(packet_text: str) -> str:
    """Return only the marker-delimited derived L4-field block of a packet."""
    after_start = packet_text.split(commit_mod.L4_FIELDS_FROM_TRACKER_START, 1)[1]
    return after_start.split(commit_mod.L4_FIELDS_FROM_TRACKER_END, 1)[0]


def _own_line_l4_block(packet_text: str) -> str:
    """Return the L4 block whose start/end markers each stand alone on their own line.

    Unlike :func:`_l4_block_region` (which splits on the FIRST marker occurrence), this
    skips an inline prose mention of the marker text -- a meta-packet may quote the
    delimiters in a backtick-wrapped sentence -- and returns the real machine-owned
    block, so a test can assert the block the reconciler actually targets.
    """
    lines = packet_text.split("\n")
    start_i = next(
        i for i, ln in enumerate(lines)
        if ln == commit_mod.L4_FIELDS_FROM_TRACKER_START
    )
    end_i = next(
        i for i in range(start_i + 1, len(lines))
        if lines[i] == commit_mod.L4_FIELDS_FROM_TRACKER_END
    )
    return "\n".join(lines[start_i:end_i + 1]) + "\n"


def _init_git_repo(tmp_path: Path) -> Path:
    """Minimal git repo for the commit-path refresh proof (mirrors pipeline setup)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "dev"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo, capture_output=True, env=env,
    )
    (repo / "TASKS.md").write_text(
        "## Ra\n\n- Tracker sync note (seed): init\n\n---\n", encoding="utf-8"
    )
    receipt_dir = repo / ".agent_bus" / "meta"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "pre_commit_receipt.json").write_text(
        json.dumps({
            "decision": "COMMIT_GO",
            "staged_sha": "phase_b_sha",
            "timestamp_utc": "2026-06-09T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    return repo


def test_packet_l4_block_derives_from_tracker_note_at_phase_a_render(tmp_path):
    """Render path: create_plan_draft derives the packet L4 block from the note.

    When the wave's canonical tracker note already exists in TASKS.md the drafted
    packet's L4-field block equals the note-derived block; when no note exists yet
    the supplied draft is kept verbatim (the commit-path refresh reconciles later).
    """
    note = _canonical_packet_l4_tracker_note()
    expected_block = commit_mod.render_l4_fields_block_from_tracker_note(note)

    repo = tmp_path / "with_note"
    (repo / "reports" / "control_plane").mkdir(parents=True)
    (repo / "TASKS.md").write_text(
        f"## Ra\n\n- Tracker sync note (seed): init\n{note}\n\n---\n",
        encoding="utf-8",
    )
    plan = phase_a_mod.create_plan_draft(
        repo,
        "packet_l4_autopopulate_from_tracker_note",
        {
            "request": "single-source the packet L4 block from the tracker note",
            "summary": "L4_ENABLER",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": _PACKET_L4_WAVE,
        },
    )
    rendered = plan.read_text(encoding="utf-8")
    assert expected_block.strip() in rendered
    rendered_block = _l4_block_region(rendered)
    assert "primary_blocker_class`: INTEGRATION." in rendered_block
    # target_gate_id must NOT over-capture the trailing `Packet:` field: the note
    # carries `target_gate_id: G8. Packet: ...`, and the derived gate value is G8.
    assert "`target_gate_id`: G8." in rendered_block
    assert "Packet:" not in rendered_block

    # No tracker note yet -> render keeps the supplied draft (no derived block).
    repo_no_note = tmp_path / "no_note"
    repo_no_note.mkdir()
    plan_no_note = phase_a_mod.create_plan_draft(
        repo_no_note,
        "packet_l4_autopopulate_from_tracker_note",
        {
            "request": "no canonical note exists yet",
            "summary": "L4_ENABLER",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": _PACKET_L4_WAVE,
        },
    )
    assert commit_mod.L4_FIELDS_FROM_TRACKER_START not in plan_no_note.read_text(
        encoding="utf-8"
    )


def test_packet_l4_tracker_marker_boundary_opt_in_is_backward_compatible():
    """The complete-marker boundary fixes target_gate_id over-capture, opt-in only.

    The canonical note emits `Packet:` immediately after `target_gate_id:`. The
    default 2-arg extractor must stay byte-for-byte (it over-captures the packet
    path -- preserving the fail-closed evidence_command + parity contract), while
    derivation passes the complete builder set so target_gate_id stops at `Packet:`.
    """
    note = _canonical_packet_l4_tracker_note()
    # Default 2-arg path UNCHANGED: still over-captures the packet path (this is the
    # exact behavior the fail-closed evidence_command + meta parity contract relies
    # on, so it must not move).
    default_value = commit_mod.tracker_marker_value(note, "target_gate_id")
    assert "Packet:" in default_value
    # Opt-in wider boundary set: a caller can pass marker_names so the value stops
    # at a builder field the default list omits.
    opt_in_value = commit_mod.tracker_marker_value(
        note, "target_gate_id", marker_names=("target_gate_id", "Packet", "evidence_command")
    )
    assert opt_in_value == "G8."
    assert "Packet:" not in opt_in_value
    # The public derivation wires the complete builder set, so no L4 field leaks the
    # trailing Packet path.
    derived = commit_mod.derive_l4_fields_from_tracker_note(note)
    assert derived["target_gate_id"] == "G8."
    assert all("Packet:" not in value for value in derived.values())


def test_packet_l4_block_reconcile_is_note_wins_over_divergent_value(tmp_path):
    """Reconcile: a divergent packet L4 value loses to the note's; never the reverse.

    The derived block is rendered solely from the note's marker values, AND any
    backtick-delimited L4 declaration outside the block is rewritten to the same
    note value, so a deliberately-divergent packet value (primary_blocker_class:
    DESIGN) is replaced by the note value (INTEGRATION) wherever it appears -- in the
    block AND in the body. Reconcile is idempotent.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    expected_block = commit_mod.render_l4_fields_block_from_tracker_note(note)
    divergent_packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n"
        "## Grounding\n"
        "- `primary_blocker_class: DESIGN`  (divergent supplied value, must lose)\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale derived block**\n\n"
        "- `primary_blocker_class`: DESIGN.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n"
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(divergent_packet, note)

    assert expected_block.strip() in reconciled
    block_region = _l4_block_region(reconciled)
    assert "DESIGN" not in block_region  # note wins inside the derived block
    assert "primary_blocker_class`: INTEGRATION." in block_region
    # Bridge finding #1: the divergent value must not survive ANYWHERE in the packet,
    # not only inside the derived block. The out-of-block declaration is the exact
    # drift vector the supervisor/bot flag, so the packet AS A WHOLE must no longer
    # declare it -- the body `primary_blocker_class: DESIGN` is conformed to the note.
    assert "DESIGN" not in reconciled
    assert "`primary_blocker_class: INTEGRATION`" in reconciled
    # Idempotent: a second reconcile against the same note is a no-op.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_reconcile_conforms_all_out_of_block_declaration_forms():
    """Every backtick-delimited out-of-block L4 declaration form conforms to the note.

    Bridge finding #1 hardening: the drift vector is any packet declaration of a value
    the note does not carry. Real packets declare L4 fields in the body in two
    inline-code forms -- ``field: VALUE`` (Grounding sublist; also mid-sentence) and
    ``field``: ``VALUE`` (the evidence_command line). Both, anywhere outside the
    derived block, are rewritten to the note value (note wins). A prose mention of a
    field name, the non-L4 ``Class:`` label, and the no-space ``FOUNDER_OVERRIDE:``
    token are left untouched.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    expected_evidence_command = (
        "`evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -q "
        "mu/tests/tools/test_phase_a_executor.py -k 'packet and (l4 or tracker)'`"
    )
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n"
        "## Scope\n"
        # A prose mention (not a backtick declaration) must NOT be rewritten.
        "Single-source primary_blocker_class and target_gate_id from the note.\n\n"
        "## Grounding / Authorization\n"
        "- `primary_blocker_class: DESIGN`\n"                # Form A, Grounding sublist
        "- Class: `L4_ENABLER`; `target_gate_id: G3`.\n"     # Form A, mid-sentence
        "- `evidence_command`: `echo WRONG-COMMAND`\n"       # Form B
        f"- Same-wave override: `FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}`\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale**\n\n- `primary_blocker_class`: DESIGN.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n"
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # No divergent value survives anywhere in the packet.
    assert "DESIGN" not in reconciled
    assert "G3" not in reconciled
    assert "WRONG-COMMAND" not in reconciled
    # Each form is conformed to the note value (note wins).
    assert "`primary_blocker_class: INTEGRATION`" in reconciled
    assert "`target_gate_id: G8`" in reconciled
    assert expected_evidence_command in reconciled
    # Non-declarations are preserved: the prose mention, the non-L4 Class label, and
    # the no-space FOUNDER_OVERRIDE token (the note carries no override to conform to).
    assert (
        "Single-source primary_blocker_class and target_gate_id from the note."
        in reconciled
    )
    assert "Class: `L4_ENABLER`" in reconciled
    assert f"`FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}`" in reconciled
    # Idempotent across all forms.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_reconcile_conforms_plain_and_bold_out_of_block_l4_decls():
    """Plain, bold, and compact multi-field out-of-block L4 declarations conform too.

    Bridge round 4 DEFECT: the inline-code conformer only rewrote backtick-delimited
    spans, so the PLAIN packet authoring forms survived reconciliation -- the finding
    showed ``- primary_blocker_class: DESIGN``, ``- indicator_artifact_ref: ...wrong``,
    and ``- evidence_command: `echo WRONG` `` all persisting next to a correct derived
    block. Real control packets overwhelmingly use these plain forms, plus bold labels
    (``- **target_gate_id:** G8``) and compact multi-field lines
    (``- bootstrap_endgame_policy: X. boot0_track_id: Y. boot0_progress_state: Z.``).
    Every one is a drift vector the supervisor/bot read, so the note must win on all of
    them; a prose mention, a ``##`` heading, and the non-L4 ``Class:`` label stay intact.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    derived = commit_mod.derive_l4_fields_from_tracker_note(note)
    clean = {
        label: commit_mod.clean_l4_body_value(derived[label])
        for label in ("primary_blocker_class", "indicator_artifact_ref",
                      "evidence_command", "target_gate_id",
                      "bootstrap_endgame_policy", "boot0_track_id", "boot0_progress_state")
    }
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n"
        # A `##` heading and a prose line that merely MENTION field names: untouched.
        "## primary_blocker_class and target_gate_id notes\n"
        "We single-source primary_blocker_class from the canonical tracker note.\n\n"
        "## Grounding / Authorization\n"
        "- Class: L4_ENABLER\n"                                    # non-L4 label: untouched
        "- primary_blocker_class: DESIGN\n"                        # plain label + plain value
        "- indicator_artifact_ref: reports/l4_wave_indicators/WRONGREF.json\n"  # plain path value
        "- evidence_command: `echo WRONG-COMMAND`\n"              # plain label + backtick value
        "- **target_gate_id:** G3\n"                              # bold label (colon inside bold)
        "- bootstrap_endgame_policy: WRONGPOLICY. "               # compact multi-field line
        "boot0_track_id: WRONGTRACK. boot0_progress_state: WRONGSTATE.\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale**\n\n- `primary_blocker_class`: DESIGN.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n"
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # No divergent value survives ANYWHERE in the packet (the round-4 defect).
    for divergent in (
        "DESIGN", "WRONGREF.json", "echo WRONG-COMMAND", "G3",
        "WRONGPOLICY", "WRONGTRACK", "WRONGSTATE",
    ):
        assert divergent not in reconciled, divergent
    # Each plain / bold form is conformed to the note value (note wins).
    assert f"- primary_blocker_class: {clean['primary_blocker_class']}" in reconciled
    assert f"- indicator_artifact_ref: {clean['indicator_artifact_ref']}" in reconciled
    assert f"- evidence_command: `{clean['evidence_command']}`" in reconciled
    assert f"- **target_gate_id:** {clean['target_gate_id']}" in reconciled
    assert (
        f"- bootstrap_endgame_policy: {clean['bootstrap_endgame_policy']}. "
        f"boot0_track_id: {clean['boot0_track_id']}. "
        f"boot0_progress_state: {clean['boot0_progress_state']}."
    ) in reconciled
    # Non-declarations are preserved: the `##` heading, the prose mention, the non-L4
    # `Class:` label.
    assert "## primary_blocker_class and target_gate_id notes" in reconciled
    assert "We single-source primary_blocker_class from the canonical tracker note." in reconciled
    assert "- Class: L4_ENABLER" in reconciled
    # Idempotent across all plain / bold / multi-field forms.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_reconcile_clears_stale_omitted_optional_l4_decl():
    """A stale out-of-block decl of a field the note OMITS is CLEARED (conform-to-absence).

    Deferred PR #1090 bot P2: the canonical L4_ENABLER tracker note omits the optional
    ``founder_override`` field, yet a packet may still carry a stale out-of-block
    declaration of it. Because the note is the single source, that leftover is drift the
    supervisor/bot flag -- so reconcile must CLEAR it to the bare colon (mirroring the
    block's ``- `founder_override`:`` omitted form), not leave it as authored. This
    covers BOTH authoring surfaces the reconciler reaches: the plain list item
    (``- founder_override: old-token``) AND the inline-code span
    (``- `founder_override: stale-inline```, the exact bot-P2 reproduction, plus the
    ``- `founder_override`: `...``` two-span form).

    The clear is scoped to the lowercase field-DECLARATION spelling. The uppercase
    ``FOUNDER_OVERRIDE:<wave>`` same-wave authorization TOKEN is a distinct entity the
    note does not govern, so it must SURVIVE the note's omission -- in BOTH the plain
    list-item form (which a conform-to-absence that ignored case would silently blank)
    and the backtick form. Fields the note DOES declare stay conformed-to-value, non-L4
    / human content is untouched, the machine-owned block stays byte-identical, and a
    second pass is a no-op.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    derived = commit_mod.derive_l4_fields_from_tracker_note(note)
    # Premise: the canonical note OMITS the optional founder_override field.
    assert derived["founder_override"] == ""
    clean_blocker = commit_mod.clean_l4_body_value(derived["primary_blocker_class"])
    derived_block = commit_mod.render_l4_fields_block_from_tracker_note(note)
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n"
        "## Grounding / Authorization\n"
        "- Class: L4_ENABLER\n"                       # non-L4 label: untouched
        "- primary_blocker_class: DESIGN\n"           # note DECLARES it: conform-to-value
        "- founder_override: old-token\n"             # plain, note OMITS: stale -> CLEAR
        "- `founder_override: stale-inline`\n"        # inline-code (bot P2): stale -> CLEAR
        "- `founder_override`: `stale-formb`\n"       # inline-code two-span: stale -> CLEAR
        f"- FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}\n"     # plain auth TOKEN: PRESERVE
        f"- Same-wave override: `FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}`\n"  # backtick TOKEN: PRESERVE
        "- We single-source founder_override from the canonical note.\n\n"  # prose: untouched
        + derived_block                               # block already canonical (byte-identity probe)
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # Every stale founder_override field declaration -- plain AND inline-code (both
    # forms) -- is cleared to the bare colon: no value, no trailing whitespace.
    assert "old-token" not in reconciled       # plain value gone
    assert "stale-inline" not in reconciled    # inline-code one-span value gone (bot P2)
    assert "stale-formb" not in reconciled     # inline-code two-span value gone
    assert "- founder_override:\n" in reconciled        # plain -> bare colon
    assert "`founder_override:`" in reconciled          # inline-code one-span -> bare colon
    assert "- founder_override: \n" not in reconciled   # no trailing space (git-diff clean)
    # The authorization TOKEN survives the note's omission in BOTH forms (note does not
    # govern it); the plain form is the case that a case-insensitive clear would blank.
    assert f"- FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}" in reconciled
    assert f"`FOUNDER_OVERRIDE:{_PACKET_L4_WAVE}`" in reconciled
    # A field the note declares stays conformed-to-value (existing behavior preserved).
    assert f"- primary_blocker_class: {clean_blocker}" in reconciled
    assert "DESIGN" not in reconciled
    # Non-L4 / human-authored content is untouched.
    assert "- Class: L4_ENABLER" in reconciled
    assert "- We single-source founder_override from the canonical note." in reconciled
    # The machine-owned block region is byte-identical before/after the conform step.
    assert _l4_block_region(reconciled) == _l4_block_region(packet)
    # Idempotent: a second pass over already-conformed text is a no-op.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_reconcile_clears_omitted_field_keeping_grouped_neighbor():
    """Clearing a note-omitted GROUPED field leaves no residue and keeps the neighbor.

    Deferred re-entry finding on the staged fix: on a compact line where the note OMITS
    the leading field (founder_override) but DECLARES the next (evidence_command),
    collapsing the omitted field to a bare colon stranded its grouping separator as a
    ``founder_override:.`` punctuation residue -- not an actually-empty declaration. The
    whole stale declaration (key + value + that separator) must instead be DROPPED so
    the line collapses to the surviving neighbor, which stays a detected, conformed
    declaration (not frozen by a merged/lost separator). The block stays byte-identical
    and a second pass is a no-op.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    derived = commit_mod.derive_l4_fields_from_tracker_note(note)
    assert derived["founder_override"] == ""
    clean_evidence = commit_mod.clean_l4_body_value(derived["evidence_command"])
    derived_block = commit_mod.render_l4_fields_block_from_tracker_note(note)
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n"
        "## Grounding / Authorization\n"
        # Compact line: omitted founder_override FOLLOWED BY declared evidence_command.
        "- founder_override: old-token. evidence_command: `echo WRONG`\n\n"
        + derived_block
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # The omitted leading field's stale value is gone...
    assert "old-token" not in reconciled
    # ...with NO punctuation residue: the cleared field must not survive as a
    # bare-but-non-empty `founder_override:.` (the orphaned grouping separator).
    assert "founder_override:." not in reconciled
    assert "founder_override:" not in reconciled.split(derived_block)[0]  # gone from body
    # The whole stale declaration was dropped, so the line collapses to the declared
    # neighbor, which leads and stays conformed-to-value (not frozen by a lost separator).
    assert f"- evidence_command: `{clean_evidence}`" in reconciled
    assert "echo WRONG" not in reconciled
    # Block untouched; idempotent.
    assert _l4_block_region(reconciled) == _l4_block_region(packet)
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_reconcile_binds_to_own_line_block_not_prose_marker_mention():
    """Reconcile targets the own-line machine block, never an inline prose marker mention.

    Re-entry blocking finding: a meta-packet that DOCUMENTS the machine-owned
    ``L4_FIELDS_FROM_TRACKER`` block quotes the start/end delimiters inline in a
    backtick-wrapped prose sentence, so the marker text appears twice -- once in prose,
    once as the real block. A naive first-``str.find`` bound to the earlier PROSE
    mention, so :func:`reconcile_packet_l4_fields_block` spliced a derived block into the
    prose sentence (corrupting it) and left the real block below stale. The marker
    lookup must instead bind to the marker that stands ALONE on its line: the real block
    is refreshed to the note, the prose sentence survives verbatim, no duplicate block is
    inserted, and the pass is idempotent.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    canonical_block = commit_mod.render_l4_fields_block_from_tracker_note(note)
    # A STALE real block (divergent blocker class) proves the real block is REFRESHED,
    # not merely left in place.
    stale_block = commit_mod.render_l4_fields_block_from_tracker_note(
        _canonical_packet_l4_tracker_note(primary_blocker_class="DESIGN")
    )
    assert stale_block != canonical_block

    start_marker = commit_mod.L4_FIELDS_FROM_TRACKER_START
    end_marker = commit_mod.L4_FIELDS_FROM_TRACKER_END
    # The exact authoring shape that triggered the finding: a work-item sentence that
    # quotes BOTH delimiters inline, positioned BEFORE the real block.
    prose = (
        f"4. Keep the machine-owned block region (between `{start_marker}` and "
        f"`{end_marker}`) byte-identical; only out-of-block decls are affected.\n"
    )
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\n\n## Work items\n\n"
        + prose + "\n" + stale_block
    )
    # Premise: the inline prose mention precedes the real own-line block (2 of each
    # marker), so a first-``find`` would bind to the prose marker, not the block.
    assert packet.count(start_marker) == 2 and packet.count(end_marker) == 2
    assert packet.find(start_marker) < packet.rfind(start_marker)

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # The prose sentence survives verbatim -- the discriminator that FAILS when the
    # replacement binds to the prose marker (which truncates/splices the sentence).
    assert prose in reconciled
    # No duplicate block was spliced into the prose: still exactly one inline mention
    # plus the one real block (2 of each marker, unchanged).
    assert reconciled.count(start_marker) == 2 and reconciled.count(end_marker) == 2
    # The own-line machine block was refreshed to the canonical note-derived block.
    assert _own_line_l4_block(reconciled) == canonical_block
    assert "DESIGN" not in reconciled  # the stale block value is gone
    # Idempotent: a second pass over already-conformed text is a no-op.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_refresh_conforms_plain_out_of_block_l4_decls(tmp_path):
    """Refresh path conforms plain out-of-block L4 declarations to the note (round 4).

    The round-4 defect through the real entrypoint: a staged packet whose plain
    ``- primary_blocker_class: DESIGN`` declaration diverges from the canonical note
    (INTEGRATION) is conformed by refresh_commit_path_packet_truth before the
    supervisor reads it, and the tracker note is never rewritten toward the packet.
    """
    note = _canonical_packet_l4_tracker_note(primary_blocker_class="INTEGRATION")
    repo = _init_git_repo(tmp_path)

    packet_rel = f"reports/control_plane/{_PACKET_L4_WAVE}.md"
    (repo / packet_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / packet_rel).write_text(
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\nClass: L4_ENABLER\nTarget gate: G8\n\n"
        "## Scope\n\n- `mu/tools/executors/commit_executor.py`\n\n"
        "## Grounding / Authorization\n"
        # Plain (non-backtick) out-of-block declaration: the round-4 drift vector.
        "- primary_blocker_class: DESIGN\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale derived block**\n\n- `primary_blocker_class`: DESIGN.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n",
        encoding="utf-8",
    )
    indicator_rel = f"reports/l4_wave_indicators/{_PACKET_L4_WAVE}.json"
    (repo / indicator_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / indicator_rel).write_text(
        json.dumps({"wave_id": _PACKET_L4_WAVE}), encoding="utf-8"
    )
    (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", "file.py", packet_rel], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "add", "-f", "--", indicator_rel], cwd=repo, check=True, capture_output=True
    )

    handoff = {
        "wave_id": _PACKET_L4_WAVE,
        "task_id": "[NEXT-CODEX-POST-REDTEAM]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": "G8",
        "caller": "phase_b",
        "branch_prefix": "jabramsja",
        "files_to_stage": ["file.py", packet_rel],
        "force_add_files": [],
        "commit_message": "feat: single-source packet L4 block\n\nCo-Authored-By: t",
        "pr_title": "feat: single-source packet L4 block",
        "pr_body": "## Summary\nx",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "fixes_implemented": ["derive packet L4 block from tracker note"],
        "tracker_note_text": note,
        "tracked_packet": packet_rel,
        "scope_items": [packet_rel],
    }

    refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
        repo_root=repo,
        handoff=handoff,
        indicator_path=indicator_rel,
        commit_status="pre_commit_supervisor_pending",
    )

    assert error is None, error
    refreshed_packet = (repo / packet_rel).read_text(encoding="utf-8")
    # The plain out-of-block declaration is conformed; no DESIGN survives anywhere.
    assert "- primary_blocker_class: INTEGRATION" in refreshed_packet
    assert "DESIGN" not in refreshed_packet
    # Never the reverse: the tracker note still declares INTEGRATION, not DESIGN.
    assert "DESIGN" not in refreshed["tracker_note_text"]
    assert (
        commit_mod.tracker_marker_value(
            refreshed["tracker_note_text"], "primary_blocker_class"
        )
        == "INTEGRATION."
    )


def test_packet_l4_reconcile_conforms_divergent_plain_target_gate_header():
    """Reconcile conforms a plain-text ``Target gate:`` header, not only backtick forms.

    Bridge round 3 NO_GO: a packet's plain-text ``Target gate: G3`` header -- the
    canonical packet header form, recognized by PACKET_TARGET_GATE_RE /
    _extract_target_gate_id_from_text -- survived a G8 tracker note while the backtick
    ``target_gate_id: G3`` declaration was conformed, so the packet AS A WHOLE still
    declared the divergent gate the supervisor/bot read. Reconcile must conform every
    gate form the extractor reads; note wins, the reverse never occurs.
    """
    note = _canonical_packet_l4_tracker_note()  # declares target_gate_id G8
    packet = (
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\nClass: L4_ENABLER\n"
        "Target gate: G3\n\n"                                  # plain header (the NO_GO form)
        "## Grounding\n"
        "- Class: `L4_ENABLER`; `target_gate_id: G3`.\n\n"    # backtick form (already conformed)
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale**\n\n- `target_gate_id`: G3.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n"
    )

    reconciled = commit_mod.reconcile_packet_l4_fields_block(packet, note)

    # The plain header is conformed (the NO_GO regression), AND no divergent gate
    # survives anywhere -- plain header, backtick form, and derived block all read G8.
    assert "Target gate: G8" in reconciled
    assert "Target gate: G3" not in reconciled
    assert "`target_gate_id: G8`" in reconciled
    assert "`target_gate_id`: G8." in _l4_block_region(reconciled)
    assert "G3" not in reconciled
    # The non-L4 ``Class:`` label is untouched (it is not an L4-block field).
    assert "Class: L4_ENABLER" in reconciled
    # Idempotent: re-running against the same note is a no-op.
    assert commit_mod.reconcile_packet_l4_fields_block(reconciled, note) == reconciled


def test_packet_l4_refresh_conforms_divergent_plain_target_gate_header(tmp_path):
    """Refresh path conforms a divergent plain-text ``Target gate:`` header to the note.

    Bridge round 3 NO_GO, through the real entrypoint: a staged packet whose plain
    ``Target gate: G3`` header diverges from the canonical note (target_gate_id G8) is
    conformed to G8 by refresh_commit_path_packet_truth before the supervisor reads
    it, and the tracker note is never rewritten toward the packet's divergent gate.
    """
    note = _canonical_packet_l4_tracker_note()  # declares target_gate_id G8
    repo = _init_git_repo(tmp_path)

    packet_rel = f"reports/control_plane/{_PACKET_L4_WAVE}.md"
    (repo / packet_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / packet_rel).write_text(
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\nClass: L4_ENABLER\n"
        "Target gate: G3\n\n"                                  # divergent plain header
        "## Scope\n\n- `mu/tools/executors/commit_executor.py`\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale derived block**\n\n- `target_gate_id`: G3.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n",
        encoding="utf-8",
    )
    indicator_rel = f"reports/l4_wave_indicators/{_PACKET_L4_WAVE}.json"
    (repo / indicator_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / indicator_rel).write_text(
        json.dumps({"wave_id": _PACKET_L4_WAVE}), encoding="utf-8"
    )
    (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", "file.py", packet_rel], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "add", "-f", "--", indicator_rel], cwd=repo, check=True, capture_output=True
    )

    handoff = {
        "wave_id": _PACKET_L4_WAVE,
        "task_id": "[NEXT-CODEX-POST-REDTEAM]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": "G8",
        "caller": "phase_b",
        "branch_prefix": "jabramsja",
        "files_to_stage": ["file.py", packet_rel],
        "force_add_files": [],
        "commit_message": "feat: single-source packet L4 block\n\nCo-Authored-By: t",
        "pr_title": "feat: single-source packet L4 block",
        "pr_body": "## Summary\nx",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "fixes_implemented": ["derive packet L4 block from tracker note"],
        "tracker_note_text": note,
        "tracked_packet": packet_rel,
        "scope_items": [packet_rel],
    }

    refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
        repo_root=repo,
        handoff=handoff,
        indicator_path=indicator_rel,
        commit_status="pre_commit_supervisor_pending",
    )

    assert error is None, error
    refreshed_packet = (repo / packet_rel).read_text(encoding="utf-8")
    # The divergent plain header is conformed to the note's gate; no G3 survives.
    assert "Target gate: G8" in refreshed_packet
    assert "G3" not in refreshed_packet
    assert "`target_gate_id`: G8." in _l4_block_region(refreshed_packet)
    # Never the reverse: the tracker note still declares G8, never the packet's G3.
    assert "target_gate_id: G8" in refreshed["tracker_note_text"]
    assert "G3" not in refreshed["tracker_note_text"]


def test_packet_l4_block_refresh_path_matches_tracker_note(tmp_path):
    """Refresh path: refresh_commit_path_packet_truth conforms the packet to the note.

    A staged packet carrying a divergent L4 block (DESIGN) is conformed to the
    canonical tracker note (INTEGRATION) before the supervisor reads it, and the
    tracker note itself is never rewritten toward the packet's divergent value.
    """
    note = _canonical_packet_l4_tracker_note()
    expected_block = commit_mod.render_l4_fields_block_from_tracker_note(note)
    repo = _init_git_repo(tmp_path)

    packet_rel = f"reports/control_plane/{_PACKET_L4_WAVE}.md"
    (repo / packet_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / packet_rel).write_text(
        f"# Packet\n\nWave ID: {_PACKET_L4_WAVE}\nClass: L4_ENABLER\nTarget gate: G8\n\n"
        "## Scope\n\n- `mu/tools/executors/commit_executor.py`\n\n"
        # Bridge finding #1: a divergent L4 declaration OUTSIDE the block (the real
        # Grounding-section drift vector) must also be conformed by the refresh path.
        "## Grounding / Authorization\n"
        "- `primary_blocker_class: DESIGN`  (out-of-block divergent value, must lose)\n\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_START}\n"
        "**stale derived block**\n\n"
        "- `primary_blocker_class`: DESIGN.\n"
        f"{commit_mod.L4_FIELDS_FROM_TRACKER_END}\n",
        encoding="utf-8",
    )
    indicator_rel = f"reports/l4_wave_indicators/{_PACKET_L4_WAVE}.json"
    (repo / indicator_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / indicator_rel).write_text(
        json.dumps({"wave_id": _PACKET_L4_WAVE}), encoding="utf-8"
    )
    (repo / "file.py").write_text("# changed code\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", "file.py", packet_rel], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "add", "-f", "--", indicator_rel], cwd=repo, check=True, capture_output=True
    )

    handoff = {
        "wave_id": _PACKET_L4_WAVE,
        "task_id": "[NEXT-CODEX-POST-REDTEAM]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": "G8",
        "caller": "phase_b",
        "branch_prefix": "jabramsja",
        "files_to_stage": ["file.py", packet_rel],
        "force_add_files": [],
        "commit_message": "feat: single-source packet L4 block\n\nCo-Authored-By: t",
        "pr_title": "feat: single-source packet L4 block",
        "pr_body": "## Summary\nx",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "fixes_implemented": ["derive packet L4 block from tracker note"],
        "tracker_note_text": note,
        "tracked_packet": packet_rel,
        "scope_items": [packet_rel],
    }

    refreshed, _staged, error = commit_mod.refresh_commit_path_packet_truth(
        repo_root=repo,
        handoff=handoff,
        indicator_path=indicator_rel,
        commit_status="pre_commit_supervisor_pending",
    )

    assert error is None, error
    refreshed_packet = (repo / packet_rel).read_text(encoding="utf-8")
    assert expected_block.strip() in refreshed_packet
    block_region = _l4_block_region(refreshed_packet)
    assert "DESIGN" not in block_region  # packet conformed to the note
    assert "primary_blocker_class`: INTEGRATION." in block_region
    # Bridge finding #1: the out-of-block Grounding declaration is conformed too, so
    # the refreshed packet AS A WHOLE no longer declares the divergent value (the
    # supervisor/bot read the whole packet, not only its derived block).
    assert "DESIGN" not in refreshed_packet
    assert "`primary_blocker_class: INTEGRATION`" in refreshed_packet
    # Never the reverse: the tracker note still declares INTEGRATION, not DESIGN.
    assert (
        commit_mod.tracker_marker_value(
            refreshed["tracker_note_text"], "primary_blocker_class"
        )
        == "INTEGRATION."
    )
    assert "DESIGN" not in refreshed["tracker_note_text"]
