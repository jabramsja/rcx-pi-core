from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
phase_a_mod = load_module(
    "phase_a_executor",
    _TOOLS_DIR / "executors" / "phase_a_executor.py",
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
                    "tracked_packet": (
                        "reports/control_plane/"
                        "founder-ordered-redteam-wave-packet-seed-2026-05-05.md"
                    ),
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
    assert scope["tracked_packet"] == (
        "reports/control_plane/founder-ordered-redteam-wave-packet-seed-2026-05-05.md"
    )


def test_create_plan_draft_creates_missing_tracked_packet_exact_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    plan = phase_a_mod.create_plan_draft(
        repo,
        "founder-ordered-redteam-wave-packet-seed-2026-05-05",
        {
            "request": "route exact canonical packet",
            "summary": "phase a should not mint a dated duplicate",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": "founder-ordered-redteam-wave-packet-seed-2026-05-05",
            "tracked_packet": (
                "reports/control_plane/"
                "founder-ordered-redteam-wave-packet-seed-2026-05-05.md"
            ),
        },
    )

    assert plan == (
        repo
        / "reports"
        / "control_plane"
        / "founder-ordered-redteam-wave-packet-seed-2026-05-05.md"
    )
    assert plan.exists()
    assert not list((repo / "reports" / "control_plane").glob("*_2026-*.md"))


def test_create_plan_draft_accepts_date_suffixed_tracked_packet_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wave_id = "example-wave-2026-05-22"
    packet_rel = f"reports/control_plane/{wave_id}_2026-05-22.md"

    plan = phase_a_mod.create_plan_draft(
        repo,
        wave_id,
        {
            "request": "route existing tracker packet",
            "summary": "phase a should reuse the TASKS-bound suffixed packet",
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": wave_id,
            "tracked_packet": packet_rel,
        },
    )

    assert plan == repo / packet_rel
    assert plan.exists()
    assert not list(
        (repo / "reports" / "control_plane").glob(f"{wave_id}_2026-05-22_*.md")
    )


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
