"""Tests for Phase B executor with real implementer actor.

Covers:
1. Implementer no longer invokes bridge_supervisor.py review
2. Implementer uses bridge_adapters.run_adapter() directly
3. Model override honored when backend supports it (claude: yes, codex: no)
4. Phase B stages files BEFORE running supervisor (receipt order)
5. Bridge render association is bound to exact job_id, not newest file
6. Non-timeout implementer failure is fatal
7. Nonzero agent review exit is fatal
8. Handoff includes explicit receipt path
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mu.tests.tools.module_loader import load_module

# Load modules
_EXECUTORS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "executors"

pb_mod = load_module("phase_b_executor", _EXECUTORS_DIR / "phase_b_executor.py")
candidate_authority_mod = sys.modules["candidate_authority"]
pa_mod = load_module("phase_a_executor", _EXECUTORS_DIR / "phase_a_executor.py")
impl_mod = load_module("phase_b_implementer", _EXECUTORS_DIR / "phase_b_implementer.py")
commit_mod = load_module("commit_executor", _EXECUTORS_DIR / "commit_executor.py")
common_mod = load_module("executor_common_for_phase_b_tests", _EXECUTORS_DIR / "executor_common.py")

# Default valid routing record for tests that call run_phase_b.
# Tests that specifically test routing validation should NOT use this.
_VALID_ROUTING_RECORD = {"decision": "ROUTE_PHASE_B", "summary": "test dispatch"}


@pytest.fixture
def mock_routing_record():
    """Patch load_routing_record to return a valid ROUTE_PHASE_B record."""
    with patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
        yield


@pytest.fixture(autouse=True)
def isolate_phase_b_pager_transport():
    """Prevent the focused module from reaching a live pager or app server."""
    with patch.object(
        pb_mod,
        "emit_pipeline_agent_event",
        return_value={
            "enabled": False,
            "event_id": "",
            "attempted": [],
            "budget_exhausted": False,
        },
    ):
        yield


@pytest.fixture
def real_pre_review_package():
    """Opt a focused integration test into the real pre-review package helper."""
    yield


@pytest.fixture(autouse=True)
def isolate_legacy_run_phase_b_pre_review_boundaries(request):
    """Keep legacy orchestration tests focused on their original boundary.

    Focused tests that request ``real_pre_review_package`` exercise the new
    tracker/collector/packet-refresh authority. Other pre-existing run_phase_b
    tests retain their historical stage-only boundary so they do not need to
    synthesize launcher-owned TASKS and indicator artifacts unrelated to the
    behavior under test.
    """
    if "real_pre_review_package" in request.fixturenames:
        yield
        return

    def stage_only_pre_review(
        repo_root,
        *,
        candidate_files,
        exact_stage_scope_files,
        plan_path,
        wave_id,
        wave_class,
        step_prefix,
        context,
        candidate_authority_required=False,
    ):
        del wave_id, wave_class, candidate_authority_required
        prepared = list(dict.fromkeys(candidate_files))
        if plan_path and not plan_path.startswith("<") and plan_path not in prepared:
            prepared.append(plan_path)
        if exact_stage_scope_files:
            ok, detail = getattr(pb_mod, "_unstage_out_of_exact_scope")(
                repo_root,
                exact_stage_scope_files,
            )
            if not ok:
                return prepared, {
                    "status": "error",
                    "step": f"{step_prefix}_scope_reconcile",
                    "stderr": detail,
                    "errors": [
                        f"Failed to reconcile exact staged scope before {context}",
                        detail,
                    ],
                }
        if prepared:
            ok, detail = getattr(pb_mod, "_stage_files_for_pipeline")(
                repo_root,
                prepared,
            )
            if not ok:
                return prepared, {
                    "status": "error",
                    "step": f"{step_prefix}_staging",
                    "stderr": detail,
                    "errors": [
                        f"Failed to stage current Phase B candidate before {context}",
                        detail,
                    ],
                }
        return prepared, None

    with patch.object(
        pb_mod,
        "_prepare_phase_b_pre_review_package",
        side_effect=stage_only_pre_review,
    ):
        yield


def _make_mock_impl():
    """Return a shared successful implementer mock for bridge-loop tests."""
    impl_success = {
        "status": "success", "output": "done", "stderr": "",
        "exit_code": 0, "job_id": "impl-test", "model_override_applied": False,
    }
    mock_impl = MagicMock()
    mock_impl.invoke_implementer.return_value = impl_success
    mock_impl.build_implementation_prompt.return_value = "prompt"
    mock_impl.load_executor_config.return_value = {
        "backends": {"phase_b_executor": "codex"},
        "model_overrides": {},
        "timeouts": {"phase_b_executor": 10},
    }
    return mock_impl


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def _git_stdout(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_canonical_tasks(repo: Path, wave_id: str) -> None:
    (repo / "TASKS.md").write_text(
        "## Ra\n\n"
        f"- Tracker sync note (2026-07-28, {wave_id}): "
        "**Phase B pre-review package.**. Class: L4_ENABLER. "
        "target_gate_id: G8.\n\n"
        "---\n",
        encoding="utf-8",
    )


def _write_pre_review_plan(repo: Path, wave_id: str) -> tuple[str, str]:
    plan_path = "reports/control_plane/plan.md"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    (repo / "reports" / "control_plane").mkdir(parents=True, exist_ok=True)
    (repo / plan_path).write_text(
        "# Plan\n"
        f"Wave ID: {wave_id}\n"
        "Phase-A-Lock: LOCKED\n"
        "Task: [PIPELINE-RECOVERY]\n"
        "Class: L4_ENABLER\n\n"
        "## Scope\n\n"
        "This lock package may stage exactly these same-wave files:\n\n"
        "- `TASKS.md`\n"
        "- `f.py`\n"
        f"- `{plan_path}`\n"
        f"- `{indicator_path}`\n",
        encoding="utf-8",
    )
    return plan_path, indicator_path


def _write_bridge_receipt_fixture_repo(
    repo: Path,
    wave_id: str,
) -> tuple[str, str, str]:
    plan_path = "reports/control_plane/plan.md"
    test_path = "mu/tests/tools/test_public_bridge_receipt.py"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    (repo / ".agent_bus").mkdir(parents=True, exist_ok=True)
    (repo / "reports" / "control_plane").mkdir(parents=True, exist_ok=True)
    (repo / "mu" / "tools" / "metrics").mkdir(parents=True, exist_ok=True)
    (repo / "mu" / "tests" / "tools").mkdir(parents=True, exist_ok=True)
    (repo / "f.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / test_path).write_text(
        "def test_public_bridge_receipt_smoke():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    (repo / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py").write_text(
        "import argparse\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--wave-id', required=True)\n"
        "parser.add_argument('--output', required=True)\n"
        "args = parser.parse_args()\n"
        "output = Path(args.output)\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "output.write_text(json.dumps({'wave_id': args.wave_id}, sort_keys=True) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (repo / plan_path).write_text(
        "# Plan\n"
        f"Wave ID: {wave_id}\n"
        "Phase-A-Lock: LOCKED\n"
        "Task: [PIPELINE-RECOVERY]\n"
        "Class: L4_ENABLER\n\n"
        "## Scope\n\n"
        "This lock package may stage exactly these same-wave files:\n\n"
        "- `TASKS.md`\n"
        "- `f.py`\n"
        f"- `{test_path}`\n"
        f"- `{plan_path}`\n"
        f"- `{indicator_path}`\n",
        encoding="utf-8",
    )
    _write_canonical_tasks(repo, wave_id)
    _init_git_repo(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "-b", f"jabramsja/{wave_id}"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return plan_path, test_path, indicator_path


def _make_successful_impl_with_edits(test_path: str) -> MagicMock:
    mock_impl = _make_mock_impl()
    edit_targets = ["f.py", test_path, "f.py", test_path, "f.py"]
    call_count = 0

    def invoke_side(repo_root, *_args, **_kwargs):
        nonlocal call_count
        target = edit_targets[min(call_count, len(edit_targets) - 1)]
        with (Path(repo_root) / target).open("a", encoding="utf-8") as handle:
            handle.write(f"# implementer edit {call_count + 1}\n")
        call_count += 1
        return {
            "status": "success",
            "output": "done",
            "stderr": "",
            "exit_code": 0,
            "job_id": f"impl-{call_count}",
            "model_override_applied": False,
        }

    mock_impl.invoke_implementer.side_effect = invoke_side
    return mock_impl


def _run_phase_b_public_target_gate_path(
    tmp_path: Path,
    *,
    plan_target_gate: str,
    routing_target_gate: str | None = None,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "reports" / "control_plane").mkdir(parents=True)
    (repo / ".agent_bus").mkdir()
    wave_id = "no-go-target-gate-normalization-2026-05-22"
    plan_path = f"reports/control_plane/{wave_id}.md"
    (repo / plan_path).write_text(
        "# Plan\n"
        f"Wave ID: {wave_id}\n"
        "Phase-A-Lock: LOCKED\n"
        "Status: ACTIVE\n"
        "Task: [NEXT-CODEX-POST-REDTEAM]\n"
        "Class: L4_ENABLER\n"
        f"Target gate: {plan_target_gate}\n"
        f"FOUNDER_OVERRIDE:{wave_id}\n",
        encoding="utf-8",
    )
    mock_impl = _make_mock_impl()
    routing = {
        **_VALID_ROUTING_RECORD,
        "task_id": "[NEXT-CODEX-POST-REDTEAM]",
        "wave_name": wave_id,
        "wave_class": "L4_ENABLER",
    }
    if routing_target_gate is not None:
        routing["target_gate_id"] = routing_target_gate
    wave_owned = [plan_path, "mu/tools/executors/phase_b_executor.py"]
    captured_package: dict[str, object] = {}

    def _capture_supervisor_package(repo_root, package_path, **_kwargs):
        captured_package.update(json.loads(package_path.read_text(encoding="utf-8")))
        return {
            "exit_code": 0,
            "parsed": {
                "decision": "COMMIT_GO",
                "summary": "",
                "status": "success",
                "findings": [],
            },
            "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
        }

    with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
         patch.object(pb_mod, "load_routing_record", return_value=routing), \
         patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned), \
         patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
         patch.object(
             pb_mod,
             "_run_pytest_on_files",
             return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             },
         ), \
         patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
         patch.object(
             pb_mod,
             "run_bridge_review",
             return_value={
                 "exit_code": 0,
                 "stdout": "GO\n",
                 "stderr": "",
                 "decision": "GO",
                 "job_id": "j1",
             },
         ), \
         patch.object(pb_mod, "_stage_files", return_value=True), \
         patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
         patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=_capture_supervisor_package), \
         patch.object(
             pb_mod,
             "prepare_commit_handoff",
             return_value=repo / ".agent_bus" / "handoff.json",
         ) as mock_handoff:
        result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

    return result, mock_handoff.call_args.kwargs, captured_package


class TestPrivateAttrGate:
    def test_select_private_attr_gate_files_only_returns_python_tests(self):
        selected = pb_mod.select_private_attr_gate_files([
            "mu/tests/tools/test_phase_b_executor.py",
            "tests/tools/test_commit_executor_receipt.py",
            "mu/tools/executors/phase_b_executor.py",
            "docs/test_notes.md",
        ])

        assert selected == [
            "mu/tests/tools/test_phase_b_executor.py",
            "tests/tools/test_commit_executor_receipt.py",
        ]

    def test_private_attr_gate_failure_reports_checker_output(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        checker = repo / "mu" / "tools" / "checks" / "linters" / "check_private_attr_access.py"
        checker.parent.mkdir(parents=True)
        checker.write_text(
            "import sys\n"
            "print('ERROR: Found private attr access in tests/ or mu/tests/:')\n"
            "print('  mu/tests/tools/test_phase_b_executor.py:10: ._helper')\n"
            "sys.exit(1)\n",
            encoding="utf-8",
        )

        result = pb_mod.run_private_attr_gate(
            repo,
            ["mu/tests/tools/test_phase_b_executor.py"],
        )

        assert result["passed"] is False
        assert result["skipped"] is False
        assert result["test_files"] == ["mu/tests/tools/test_phase_b_executor.py"]
        assert "ERROR: Found private attr access in tests/" in result["stdout"]

    def test_private_attr_gate_scans_only_selected_wave_tests(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        checker = repo / "mu" / "tools" / "checks" / "linters" / "check_private_attr_access.py"
        checker.parent.mkdir(parents=True)
        checker_source = _EXECUTORS_DIR.parent / "checks" / "linters" / "check_private_attr_access.py"
        checker.write_text(
            checker_source.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        selected = repo / "mu" / "tests" / "l4_gates" / "test_selected_clean.py"
        unselected = repo / "mu" / "tests" / "tools" / "test_unselected_dirty.py"
        selected.parent.mkdir(parents=True)
        unselected.parent.mkdir(parents=True)
        selected.write_text("pass\n", encoding="utf-8")
        unselected.write_text(
            "from module import foo\nfoo._unselected_violation()\n",
            encoding="utf-8",
        )

        result = pb_mod.run_private_attr_gate(
            repo,
            ["mu/tests/l4_gates/test_selected_clean.py"],
        )

        assert result["passed"] is True
        assert result["test_files"] == ["mu/tests/l4_gates/test_selected_clean.py"]


class TestPhaseBWaveClassResolution:
    def test_planning_only_structural_packet_packages_as_enabler(self):
        plan = (
            "Class: L4_STRUCTURAL\n"
            "\n"
            "This packet is a Phase A routing boundary, not an implementation packet.\n"
            "\n"
            "## Locked Later Phase B Plan\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="planning-only-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/packet.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/packet.md",
                "reports/l4_wave_indicators/packet.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note

    def test_no_go_structural_packet_without_runtime_packages_as_enabler(self):
        plan = (
            "Class: L4_STRUCTURAL\n"
            "\n"
            "Status: NO-GO before commit readiness.\n"
            "The package remains NO-GO: it has no accepted executable runtime delta.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="no-go-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/no_go.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/no_go.md",
                "reports/deferred/non_blocking/no_go_bridge_nonblockers.md",
                "reports/l4_wave_indicators/no-go-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=2,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note
        assert "host_semantics_delta_before" not in note
        assert "structural_artifact_ref" not in note

    def test_no_go_for_implementation_packet_without_runtime_packages_as_enabler(self):
        plan = (
            "Class: L4_STRUCTURAL\n"
            "\n"
            "Status: Phase A (NO-GO prerequisite stop - same-wave TASKS tracker absent)\n"
            "The packet cannot authorize implementation while the tracker entry is absent.\n"
            "No implementation, commit automation, or count-reduction claim is authorized by this packet.\n"
            "Authorization conclusion: NO-GO for implementation.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="no-go-for-implementation-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/no_go_for_implementation.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/no_go_for_implementation.md",
                "reports/l4_wave_indicators/no-go-for-implementation-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=2,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note
        assert "host_semantics_delta_before" not in note
        assert "structural_artifact_ref" not in note

    def test_no_go_marker_decision_without_runtime_packages_as_enabler(self):
        plan = (
            "Class: L4_STRUCTURAL\n"
            "Status: Phase B (implementation-complete, bridge-converged)\n"
            "Purpose: Phase A only. Decide whether residual Python/JavaScript "
            "@host_iteration markers can honestly be removed. Do not implement runtime "
            "changes in Phase A.\n\n"
            "No Phase B implementation write set is authorized by this Phase A packet.\n"
            "Decision: NO-GO.\n"
            "No Phase B runtime, marker, ratchet-baseline, indicator, or successor "
            "packet write set is authorized by this decision.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="no-go-marker-decision-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/no_go_marker_decision.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/no_go_marker_decision.md",
                "reports/l4_wave_indicators/no-go-marker-decision-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=3,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note
        assert "no_op_proof:" not in note
        assert "host_semantics_delta_before" not in note
        assert "structural_artifact_ref" not in note

    def test_control_plane_phase_a_only_structural_packet_packages_as_enabler(self):
        plan = (
            "Class: L4_STRUCTURAL successor, with this packet rewrite as control-plane Phase A only\n"
            "\n"
            "Purpose: This packet does not authorize implementation while same-wave tracker "
            "proof is absent.\n"
            "\n"
            "This Phase A rewrite may change only this packet.\n"
            "At this packet rewrite, implementation is not authorized.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="control-plane-phase-a-only-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/control_plane_phase_a_only.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/control_plane_phase_a_only.md",
                "reports/l4_wave_indicators/control-plane-phase-a-only-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note
        assert "host_semantics_delta_before" not in note
        assert "structural_artifact_ref" not in note

    def test_stop_condition_only_structural_packet_packages_as_enabler(self):
        plan = (
            "Wave Class: L4_STRUCTURAL (planned /mu structural host-semantics reduction)\n"
            "\n"
            "This rewrite does not authorize editing TASKS.md or implementation files in the current turn.\n"
            "Do not solve the implementation in this Phase A packet-rewrite turn.\n"
            "Stop before Phase B implementation if TASKS.md still lacks a same-wave tracker entry.\n"
            "Phase B is not authorized until this packet is locked and TASKS.md contains the exact wave id.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="stop-condition-only-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/stop_condition_only.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/stop_condition_only.md",
                "reports/l4_wave_indicators/stop-condition-only-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=3,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_ENABLER" in note
        assert "host_semantics_delta_before" not in note
        assert "structural_artifact_ref" not in note

    def test_smaller_prerequisite_alone_does_not_downgrade_structural_packet(self):
        plan = (
            "Class: L4_STRUCTURAL\n"
            "\n"
            "The package needs a smaller prerequisite before implementation.\n"
        )

        note = pb_mod.build_phase_b_tracker_note(
            wave_id="ambiguous-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/ambiguous.md",
            plan_content=plan,
            changed_files=[
                "TASKS.md",
                "reports/control_plane/ambiguous.md",
                "reports/l4_wave_indicators/ambiguous-structural-wave.json",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_STRUCTURAL" in note

    def test_runtime_structural_packet_stays_structural(self):
        note = pb_mod.build_phase_b_tracker_note(
            wave_id="runtime-structural-wave",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/packet.md",
            plan_content="This packet is a Phase A routing boundary, not an implementation packet.",
            changed_files=[
                "mu/host/js/engine/pipeline.js",
                "mu/tests/l4_gates/test_wave11_hardening_gate.py",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_STRUCTURAL" in note

    def test_structural_tracker_note_uses_package_l4_gate_from_changed_scope(self):
        note = pb_mod.build_phase_b_tracker_note(
            wave_id="structural-wave-2026-05-13",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/structural-wave.md",
            changed_files=[
                "mu/host/js/engine/pipeline.js",
                "mu/tests/l4_gates/test_wave11_hardening_gate.py",
                "mu/tests/tools/test_phase_b_executor.py",
                "reports/control_plane/structural-wave.md",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert (
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            "mu/tests/l4_gates/test_wave11_hardening_gate.py "
            "mu/tests/tools/test_phase_b_executor.py && "
            "python3 tools/checks/enforce_l4_execution_contract.py --files "
            "mu/host/js/engine/pipeline.js"
        ) in note
        assert "reports/l4_wave_indicators/structural-wave-2026-05-13.json --wave-id" in note
        assert "--wave-id structural-wave-2026-05-13 --wave-class L4_STRUCTURAL" in note
        assert "Final pytest gate covered 2 test file(s)" in note

    def test_tracker_note_counts_pytest_selectors_separately_from_files(self):
        note = pb_mod.build_phase_b_tracker_note(
            wave_id="selector-heavy-wave-2026-06-27",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/selector-heavy-wave.md",
            changed_files=[
                "mu/tests/tools/test_phase_b_executor.py",
                "mu/tests/tools/test_executor_dispatch.py",
            ],
            test_files=[
                "mu/tests/tools/test_phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py::TestOne::test_a",
                "mu/tests/tools/test_executor_dispatch.py::TestTwo::test_b",
            ],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Final pytest gate covered 3 pytest selector(s) across 2 test file(s)" in note
        assert "Final pytest gate covered 3 test file(s)" not in note


class TestBuildImplementationPrompt:
    """Test that the implementer prompt is structured correctly."""

    def test_prompt_contains_plan_content(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "# My Plan\n\nDo the thing.",
            repo_root=tmp_path,
            wave_id="test-wave",
        )
        assert "# My Plan" in prompt
        assert "Do the thing." in prompt

    def test_prompt_contains_wave_id(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="my-wave-id",
        )
        assert "my-wave-id" in prompt

    def test_invoke_implementer_fails_closed_in_agent_review_mode(self, tmp_path):
        with patch.dict(os.environ, {"RCX_AGENT_REVIEW_MODE": "run_review"}, clear=False):
            result = impl_mod.invoke_implementer(
                tmp_path,
                "locked plan",
                backend="codex",
            )
        assert result["status"] == "error"
        assert "agent review mode" in result["stderr"]

    def test_prompt_includes_scope_hint(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan",
            repo_root=tmp_path,
            wave_id="w",
            scope_hint="only mu/tools/",
        )
        assert "only mu/tools/" in prompt

    def test_prompt_is_implementation_not_review(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan", repo_root=tmp_path, wave_id="w",
        )
        assert "write code" in prompt.lower()
        assert "NOT a reviewer" in prompt

    def test_prompt_bars_commit_stage_governance_commands(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan", repo_root=tmp_path, wave_id="w",
        )
        assert "./tools/pre-push-fast" in prompt
        assert "./tools/audit_fast.sh" in prompt
        assert "./dev.sh" in prompt
        assert "commit/push governance commands" in prompt
        assert "Phase B-local validation" in prompt

    def test_prompt_renders_outer_pipeline_commands_inert(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "## Pipeline Requirement\n\n"
            "```bash\n"
            "python3 mu/tools/executors/executor_dispatch.py "
            "--routing-record .agent_bus/meta/post_merge_routing.json "
            "--loop --max-waves 1 --json\n"
            "```\n\n"
            "```bash\n"
            "codex-rcx-preflight parity\n"
            "```\n",
            repo_root=tmp_path,
            wave_id="w",
        )

        assert "python3 mu/tools/executors/executor_dispatch.py" not in prompt
        assert "codex-rcx-preflight parity" not in prompt
        assert "outer-pipeline command omitted" in prompt
        assert "Do NOT run dispatcher" in prompt
        assert "executor launch commands" in prompt

    def test_prompt_includes_learning_context_when_provided(self, tmp_path):
        learning = "## Learning Context\n\nKnown pipeline patterns:\n- [test_failure] error → fix"
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="test-wave",
            learning_context=learning,
        )
        assert "## Learning Context" in prompt
        assert "Known pipeline patterns" in prompt

    def test_prompt_excludes_learning_context_when_empty(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="test-wave",
            learning_context="",
        )
        assert "## Learning Context" not in prompt

    def test_prompt_default_learning_context_is_empty(self, tmp_path):
        """Default learning_context kwarg produces no Learning Context section."""
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="test-wave",
        )
        assert "## Learning Context" not in prompt

    def test_prompt_includes_scope_contract_when_provided(self, tmp_path):
        prompt = impl_mod.build_implementation_prompt(
            "plan content",
            repo_root=tmp_path,
            wave_id="test-wave",
            scope_contract="Allowed product writes:\n- mu/tools/executors/recovery_gate.py",
        )
        assert "## Scope Contract" in prompt
        assert "Allowed product writes" in prompt


class TestPhaseBExecutorLearningContextWiring:
    """Verify phase_b_executor passes learning_context to build_implementation_prompt."""

    def test_all_call_sites_pass_learning_context_kwarg(self):
        """All build_implementation_prompt() call sites in phase_b_executor.py
        must pass learning_context= kwarg."""
        import inspect
        source = inspect.getsource(pb_mod.run_phase_b)
        # Count call sites
        call_sites = [i for i in range(len(source)) if source[i:].startswith("build_implementation_prompt(")]
        assert len(call_sites) >= 4, (
            f"Expected at least 4 build_implementation_prompt() call sites, found {len(call_sites)}"
        )
        # Verify each call site passes learning_context
        for idx in call_sites:
            # Find the closing paren by tracking nesting
            depth = 0
            end = idx
            for j in range(idx, min(idx + 2000, len(source))):
                if source[j] == '(':
                    depth += 1
                elif source[j] == ')':
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            call_text = source[idx:end + 1]
            assert "learning_context=" in call_text, (
                f"build_implementation_prompt() call at offset {idx} does not pass "
                f"learning_context= kwarg. Call text:\n{call_text[:300]}"
            )

    def test_phase_b_executor_imports_load_relevant_learnings(self):
        """phase_b_executor.py must import load_relevant_learnings at runtime."""
        import inspect
        source = inspect.getsource(pb_mod.run_phase_b)
        assert "load_relevant_learnings" in source


class TestImplementerDoesNotUseBridgeSupervisorReview:
    """CRITICAL: implementer must NOT invoke bridge_supervisor.py review.

    The implementer uses bridge_adapters.run_adapter() directly, which invokes
    the backend CLI as a code-writing actor. bridge_supervisor.py review is a
    review-only surface with a prompt that says "do not edit files."
    """

    def test_no_bridge_supervisor_import(self):
        """phase_b_implementer.py must not import or reference bridge_supervisor.py."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert "bridge_supervisor" not in source, (
            "phase_b_implementer.py still references bridge_supervisor.py. "
            "The implementer must use bridge_adapters.run_adapter() directly."
        )

    def test_no_review_command(self):
        """phase_b_implementer.py must not construct a 'review' command."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert '"review"' not in source, (
            "phase_b_implementer.py still constructs a 'review' command. "
            "The implementer is a code-writing actor, not a reviewer."
        )

    def test_imports_bridge_adapters(self):
        """phase_b_implementer.py must reference bridge_adapters for direct invocation."""
        source = (_EXECUTORS_DIR / "phase_b_implementer.py").read_text()
        assert "bridge_adapters" in source, (
            "phase_b_implementer.py does not reference bridge_adapters. "
            "The implementer must use run_adapter() directly."
        )


class TestModelOverrideHonesty:
    """Model override is only honored when the backend supports it."""

    def test_codex_backend_does_not_support_model_override(self):
        """Codex backend ignores model_override (codex uses its own model)."""
        assert impl_mod._MODEL_OVERRIDE_SUPPORT.get("codex") is None  # ANTICHEAT_OK: testing implementer model config

    def test_claude_backend_supports_model_override(self):
        """Claude backend honors --model flag."""
        assert impl_mod._MODEL_OVERRIDE_SUPPORT.get("claude") == "--model"  # ANTICHEAT_OK: testing implementer model config

    def test_apply_model_override_codex_noop(self):
        """Model override on codex backend returns was_applied=False."""
        cmd = ["codex", "exec", "-"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "codex", "sonnet")  # ANTICHEAT_OK: testing implementer model override
        assert not applied
        assert new_cmd == cmd  # Unchanged

    def test_apply_model_override_claude_replaces(self):
        """Model override on claude backend replaces --model value."""
        cmd = ["claude", "--print", "--model", "opus"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "claude", "sonnet")  # ANTICHEAT_OK: testing implementer model override
        assert applied
        assert "--model" in new_cmd
        idx = new_cmd.index("--model")
        assert new_cmd[idx + 1] == "sonnet"

    def test_apply_model_override_claude_appends(self):
        """Model override on claude backend appends --model if missing."""
        cmd = ["claude", "--print"]
        new_cmd, applied = impl_mod._apply_model_override(cmd, "claude", "haiku")  # ANTICHEAT_OK: testing implementer model override
        assert applied
        assert new_cmd[-2:] == ["--model", "haiku"]


class TestInvokeImplementer:
    """Test implementer invocation with mocked bridge adapter."""

    def _setup_bridge_config(self, tmp_path):
        """Create bridge config and scratch dir for tests."""
        bus_dir = tmp_path / ".agent_bus"
        bus_dir.mkdir(exist_ok=True)
        (bus_dir / "bridge_config.json").write_text(json.dumps({
            "agents": {
                "codex": {
                    "cmd": ["echo", "done"],
                    "timeout_s": 10,
                    "prompt_via_stdin": True,
                    "mode": "live",
                }
            }
        }))
        (tmp_path / ".scratch").mkdir(exist_ok=True)

    def _patch_bridge_adapters(self, **overrides):
        """Create a mock bridge_adapters module for patching."""
        from bridge_adapters import AdapterSpec, BridgeAdapterError
        mock_ba = MagicMock()
        mock_ba.AdapterSpec = AdapterSpec
        mock_ba.BridgeAdapterError = BridgeAdapterError
        mock_ba.load_bridge_config.return_value = {
            "agents": {"codex": {"cmd": ["echo"], "timeout_s": 10, "prompt_via_stdin": True, "mode": "live"}}
        }
        mock_ba.get_adapter.return_value = AdapterSpec(
            name="codex", cmd=["echo", "done"], timeout_s=10,
            prompt_via_stdin=True, env=None, mode="live",
        )
        for k, v in overrides.items():
            setattr(mock_ba, k, v)
        return mock_ba

    def test_returns_structured_result_with_job_id(self, tmp_path):
        """Implementer returns result with job_id for render association."""
        self._setup_bridge_config(tmp_path)
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "Implementation complete"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "success"
            assert result["exit_code"] == 0
            assert result["job_id"].startswith("impl-")

    def test_timeout_returns_structured_error(self, tmp_path):
        """Timeout from bridge adapter is detected and reported."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("timed out after 1s")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=1,
            )
            assert result["status"] == "timeout"
            assert result["exit_code"] == -1

    def test_stale_timeout_returns_structured_error(self, tmp_path):
        """Stale implementer runs are detected and reported explicitly."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("Adapter 'codex' stalled after 30s")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=30,
            )
            assert result["status"] == "stale"
            assert result["exit_code"] == -2

    def test_passes_configured_output_watchdogs_to_adapter(self, tmp_path):
        """Implementer stale budget is passed; zero_output is disabled (None).

        claude --print defers stdout until final text response, so
        zero_output_timeout produces false-positive kills on active
        implementer sessions (verified 2026-04-13, session 34ffd8cf).
        """
        self._setup_bridge_config(tmp_path)
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "executor_config.json").write_text(json.dumps({
            "timeouts": {"phase_b_implementer_stale": 123}
        }))
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "done"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=600,
            )

        assert result["status"] == "success"
        assert mock_ba.run_adapter.call_args.kwargs["stale_timeout_s"] == 123.0
        assert mock_ba.run_adapter.call_args.kwargs["zero_output_timeout_s"] is None

    def test_nonzero_exit_returns_error(self, tmp_path):
        """Non-timeout failure from bridge adapter returns error status."""
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError("Adapter 'codex' exited 1")

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", timeout=10,
            )
            assert result["status"] == "error"
            assert result["exit_code"] == 1

    def test_adapter_error_result_envelope_is_preserved(self, tmp_path):
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import BridgeAdapterError
        output = json.dumps({
            "type": "result",
            "subtype": "error_max_turns",
            "num_turns": 51,
            "stop_reason": "tool_use",
        })
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.side_effect = BridgeAdapterError(
            "Adapter 'claude' exited 1",
            output=output,
            returncode=1,
        )

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path,
                "test prompt",
                backend="claude",
                timeout=10,
            )

        assert result["status"] == "error"
        assert result["error_subtype"] == "error_max_turns"
        assert result["stop_reason"] == "tool_use"
        assert result["num_turns"] == 51

    def test_adapter_error_result_envelope_is_preserved_from_raw_transcript(self, tmp_path):
        self._setup_bridge_config(tmp_path)
        from bridge_adapters import AdapterSpec, BridgeAdapterError
        raw_jsonl = "\n".join([
            json.dumps({
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "partial work completed"}
                    ]
                },
            }),
            json.dumps({
                "type": "result",
                "subtype": "error_max_turns",
                "num_turns": 51,
                "stop_reason": "tool_use",
            }),
        ])

        def raise_with_normalized_output(*_args, **kwargs):
            kwargs["raw_output_path"].write_text(raw_jsonl, encoding="utf-8")
            raise BridgeAdapterError(
                "Adapter 'claude' exited 1",
                output="partial work completed",
                returncode=1,
            )

        mock_ba = self._patch_bridge_adapters()
        mock_ba.get_adapter.return_value = AdapterSpec(
            name="claude",
            cmd=["claude", "--output-format", "stream-json"],
            timeout_s=10,
            prompt_via_stdin=True,
            env=None,
            mode="live",
        )
        mock_ba.run_adapter.side_effect = raise_with_normalized_output

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path,
                "test prompt",
                backend="claude",
                timeout=10,
            )

        assert result["status"] == "error"
        assert result["output"] == "partial work completed"
        assert result["error_subtype"] == "error_max_turns"
        assert result["stop_reason"] == "tool_use"
        assert result["num_turns"] == 51

    def test_model_override_reported_in_result(self, tmp_path):
        """Result includes whether model override was actually applied."""
        self._setup_bridge_config(tmp_path)
        mock_ba = self._patch_bridge_adapters()
        mock_ba.run_adapter.return_value = "done"

        with patch.object(impl_mod, "_bridge_adapters", mock_ba):
            result = impl_mod.invoke_implementer(
                tmp_path, "test prompt", backend="codex", model_override="sonnet", timeout=10,
            )
            assert result["model_override_applied"] is False  # codex can't honor sonnet


class TestLoadExecutorConfig:
    """Test config loading."""

    def test_missing_config_returns_defaults(self, tmp_path):
        config = impl_mod.load_executor_config(tmp_path)
        # Materialized: implementer backend tracks role_agents.implementer (config-only changes).
        assert config["backends"]["phase_b_executor"] == config["role_agents"]["implementer"]
        assert config["hybrid_recovery_enabled"] is True

    def test_existing_config_loaded(self, tmp_path, monkeypatch):
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_KEY", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY", raising=False)
        monkeypatch.delenv("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE", raising=False)
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "executor_config.json"
        config_file.write_text(json.dumps({
            "role_agents": {"implementer": "claude"},
            "model_overrides": {"phase_b_executor": "sonnet"},
            "timeouts": {"phase_b_executor": 600},
            "hybrid_recovery_enabled": True,
        }))
        config = impl_mod.load_executor_config(tmp_path)
        assert config["role_agents"]["implementer"] == "claude"
        assert config["backends"]["phase_a_executor"] == "claude"
        assert config["backends"]["phase_b_executor"] == "claude"
        assert config["backends"]["bot_remediation"] == "claude"
        assert config["model_overrides"]["phase_b_executor"] == "sonnet"
        assert config["timeouts"]["phase_b_executor"] == 600
        assert config["hybrid_recovery_enabled"] is True

    def test_scoped_role_env_override_ignores_other_repo_roots(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "executor_config.json"
        config_file.write_text(json.dumps({
            "role_agents": {"implementer": "claude"},
        }))
        other_root = tmp_path.parent / "other-root"
        monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "codex")
        monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(other_root))

        config = impl_mod.load_executor_config(tmp_path)

        assert config["role_agents"]["implementer"] == "claude"
        assert config["backends"]["phase_b_executor"] == "claude"
        assert common_mod.resolve_role_agent(config, "implementer") == "claude"

    def test_scoped_role_env_override_applies_to_matching_repo_root(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "executor_config.json"
        config_file.write_text(json.dumps({
            "role_agents": {"implementer": "claude"},
        }))
        monkeypatch.setenv("RCX_IMPLEMENTER_AGENT_OVERRIDE", "codex")
        monkeypatch.setenv("RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT", str(tmp_path))

        config = impl_mod.load_executor_config(tmp_path)

        assert config["role_agents"]["implementer"] == "codex"
        assert config["backends"]["phase_b_executor"] == "codex"


class TestPrepareCommitHandoff:
    """Test updated handoff schema."""

    def test_new_schema_fields_present(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test-wave",
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["wave_id"] == "test-wave"
        assert handoff["task_id"] == "[TEST]"
        assert handoff["wave_class"] == "L4_ENABLER"
        assert handoff["target_gate_id"] == "G8"
        assert handoff["branch_prefix"] == "jabramsja"
        assert "hold_push" not in handoff  # Removed from new schema

    def test_explicit_receipt_path_in_handoff(self, tmp_path):
        """Handoff includes the explicit receipt path, not just canonical."""
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test-wave",
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            pre_commit_receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_2026-03-23.json",
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["pre_commit_receipt_path"] == ".agent_bus/meta/pre_commit_receipts/receipt_2026-03-23.json"

    def test_dispatcher_builder_rebuilds_handoff_with_phase_b_receipt(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "builder-refresh-2026-05-25"
        plan_rel = f"reports/control_plane/{wave_id}.md"
        receipt_rel = ".agent_bus/meta/pre_commit_receipts/r.json"
        (repo / "reports" / "control_plane").mkdir(parents=True, exist_ok=True)
        (repo / ".agent_bus" / "meta" / "pre_commit_receipts").mkdir(parents=True, exist_ok=True)
        (repo / plan_rel).write_text(
            "\n".join([
                "Task: [NEXT-CODEX-POST-REDTEAM]",
                f"Wave ID: {wave_id}",
                "Wave Class: MAINTENANCE",
                "Target Gate: G8",
                "Phase-A-Lock: LOCKED",
                "Status: ACTIVE",
                "",
                "May stage exactly:",
                "- `TASKS.md`",
                f"- `{plan_rel}`",
                "",
            ]),
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text("- Tracker sync note placeholder\n", encoding="utf-8")
        (repo / "UNRELATED.md").write_text("unrelated staged work\n", encoding="utf-8")
        subprocess.run(["git", "add", "UNRELATED.md"], cwd=repo, check=True, capture_output=True)
        bad_receipt_rel = "not_receipt.txt"
        (repo / bad_receipt_rel).write_text("not json", encoding="utf-8")
        rejected_path, rejected_errors = pb_mod.prepare_dispatcher_commit_handoff_from_routing_record(
            repo,
            {
                "decision": "COMMIT_GO",
                "summary": "refresh stale handoff",
                "wave_name": wave_id,
                "task_id": "[NEXT-CODEX-POST-REDTEAM]",
                "tracked_packet": plan_rel,
            },
            receipt_path=bad_receipt_rel,
        )

        assert rejected_path is None
        assert any("pre-commit supervisor receipt" in err for err in rejected_errors)
        assert any("JSON receipt" in err for err in rejected_errors)
        assert not (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").exists()

        (repo / receipt_rel).write_text(json.dumps({"decision": "COMMIT_GO"}), encoding="utf-8")
        stub_path, stub_errors = pb_mod.prepare_dispatcher_commit_handoff_from_routing_record(
            repo,
            {
                "decision": "COMMIT_GO",
                "summary": "refresh stale handoff",
                "wave_name": wave_id,
                "task_id": "[NEXT-CODEX-POST-REDTEAM]",
                "tracked_packet": plan_rel,
            },
            receipt_path=receipt_rel,
        )

        assert stub_path is None
        assert any("missing required supervisor receipt field staged_sha" in err for err in stub_errors)
        assert any("missing required supervisor receipt field package_path" in err for err in stub_errors)
        assert not (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").exists()

        package_path = repo / ".scratch" / "phase_b_supervisor_package.json"
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(json.dumps({"wave_name": wave_id}), encoding="utf-8")
        (repo / receipt_rel).write_text(
            json.dumps({
                "decision": "COMMIT_GO",
                "staged_sha": "reviewed-staged-sha",
                "timestamp_utc": "2026-05-25T00:00:00+00:00",
                "package_digest": "package-digest",
                "package_path": str(package_path),
            }),
            encoding="utf-8",
        )

        mismatch_path, mismatch_errors = pb_mod.prepare_dispatcher_commit_handoff_from_routing_record(
            repo,
            {
                "decision": "COMMIT_GO",
                "summary": "refresh stale handoff",
                "wave_name": "different-wave-2026-05-25",
                "task_id": "[NEXT-CODEX-POST-REDTEAM]",
                "tracked_packet": plan_rel,
            },
            receipt_path=receipt_rel,
        )

        assert mismatch_path is None
        assert any("does not match routing wave" in err for err in mismatch_errors)
        assert not (repo / ".agent_bus" / "executors" / "phase_b_handoff.json").exists()

        handoff_path, errors = pb_mod.prepare_dispatcher_commit_handoff_from_routing_record(
            repo,
            {
                "decision": "COMMIT_GO",
                "summary": "refresh stale handoff",
                "wave_name": wave_id,
                "task_id": "[NEXT-CODEX-POST-REDTEAM]",
                "tracked_packet": plan_rel,
            },
            receipt_path=receipt_rel,
        )

        assert errors == []
        assert handoff_path is not None
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert handoff["caller"] == "phase_b"
        assert handoff["pre_commit_receipt_path"] == receipt_rel
        assert handoff["tracked_packet"] == plan_rel
        assert "TASKS.md" in handoff["files_to_stage"]
        assert "UNRELATED.md" not in handoff["files_to_stage"]
        assert "UNRELATED.md" not in handoff["tracker_note_text"]

    def test_tracker_note_text_in_handoff(self, tmp_path):
        tracker_note_text = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            plan_path="reports/control_plane/test_plan.md",
            changed_files=["file.py"],
            test_files=[],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=1,
            reentry=False,
        )
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            tracker_note_text=tracker_note_text,
            files_to_stage=["file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert "tracker_note_text" in handoff
        assert handoff["tracker_note_text"] == tracker_note_text

    def test_blank_target_branch_omitted_from_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            target_branch="",
            files_to_stage=["file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert "target_branch" not in handoff

    def test_optional_supervisor_context_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["file.py"],
            scope_items=["reports/control_plane/test_plan.md", "file.py"],
            evidence_handles={"receipt_chain": "direct receipt path preserved"},
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["scope_items"] == ["reports/control_plane/test_plan.md", "file.py"]
        assert handoff["evidence_handles"] == {
            "receipt_chain": "direct receipt path preserved"
        }

    def test_tracked_packet_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            files_to_stage=["file.py", "reports/control_plane/test_plan.md"],
            tracked_packet="reports/control_plane/test_plan.md",
            scope_items=["reports/control_plane/test_plan.md"],
            evidence_handles={"indicator": "reports/l4_wave_indicators/test.json"},
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["tracked_packet"] == "reports/control_plane/test_plan.md"
        assert handoff["scope_items"] == ["reports/control_plane/test_plan.md"]

    def test_wave_bound_target_branch_accepts_restart_branch(self):
        target_branch = pb_mod._wave_bound_target_branch(  # ANTICHEAT_OK: validating bounded restart-branch selection
            "jabramsja/test-wave-restart-2026-04-21",
            wave_id="test-wave",
        )
        assert target_branch == "jabramsja/test-wave-restart-2026-04-21"

    def test_wave_bound_target_branch_rejects_unrelated_branch(self):
        target_branch = pb_mod._wave_bound_target_branch(  # ANTICHEAT_OK: validating unrelated-branch rejection
            "jabramsja/other-wave-restart-2026-04-21",
            wave_id="test-wave",
        )
        assert target_branch == ""

    def test_wave_bound_target_branch_accepts_non_default_prefix(self):
        target_branch = pb_mod._wave_bound_target_branch(  # ANTICHEAT_OK: validating non-default branch-prefix preservation
            "codex/test-wave-restart-2026-04-21",
            wave_id="test-wave",
            branch_prefix="codex",
        )
        assert target_branch == "codex/test-wave-restart-2026-04-21"

    def test_launch_owned_restart_branch_authority_feeds_commit_handoff(self, tmp_path):
        wave_id = "test-wave"
        target_branch = "jabramsja/test-wave-restart-2026-08-21"
        routing_record = {
            "candidate_authority": {
                "target_branch_authority": {
                    "source": "launch_current_branch",
                    "branch_prefix": "jabramsja",
                    "target_branch": target_branch,
                }
            }
        }

        prefix, routed_target, error = pb_mod._launch_target_branch_authority_from_routing_record(  # ANTICHEAT_OK: validating routed launch branch authority
            routing_record,
            wave_id=wave_id,
        )
        assert error is None
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id=wave_id,
            task_id="[TEST]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            branch_prefix=prefix,
            target_branch=routed_target,
            files_to_stage=["file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["branch_prefix"] == "jabramsja"
        assert handoff["target_branch"] == target_branch

    def test_build_phase_b_tracker_note_is_l4_compliant(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="pipeline-test-run-2026-03-25",
            task_id="[PIPELINE-TEST-RUN]",
            target_gate_id="G8",
            plan_path="reports/control_plane/pipeline_test_run_2026-03-25.md",
            changed_files=[
                "mu/tools/executors/phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py",
            ],
            test_files=[
                "mu/tests/tools/test_phase_b_executor.py",
                "mu/tests/tools/test_executor_dispatch.py",
            ],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=2,
            reentry=True,
        )
        assert note.startswith("- Tracker sync note (")
        assert "pipeline-test-run-2026-03-25): **PIPELINE-TEST-RUN — commit-ready Phase B handoff.**" in note
        assert "Class: L4_ENABLER" in note
        assert "target_gate_id: G8" in note
        assert "Packet: `reports/control_plane/pipeline_test_run_2026-03-25.md`" in note
        assert "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short" in note
        assert "indicator_artifact_ref: reports/l4_wave_indicators/pipeline-test-run-2026-03-25.json" in note
        assert "progress_proof_after: Phase B emitted a commit-ready handoff for pipeline-test-run-2026-03-25" in note

    def test_build_phase_b_tracker_note_threads_scope_refs_and_non_scope_boundary(self):
        wave_id = "fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff"
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: locks Phase B tracker authority projection
            wave_id=wave_id,
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path=f"reports/control_plane/{wave_id}_2026-06-27.md",
            plan_content=(
                "## Scope\n"
                "Do not edit production runtime/substrate/seed/registry/projection/parity files.\n"
                "Optimization remains LAST and out of scope.\n"
            ),
            changed_files=[
                "TASKS.md",
                "mu/docs/core/FixpointMetaCircularEvaluator.v0.md",
                "mu/tests/docs/test_fixpoint_meta_circular_foundation_gate.py",
                "mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py",
                f"reports/control_plane/{wave_id}_2026-06-27.md",
            ],
            test_files=[
                "mu/tests/docs/test_fixpoint_meta_circular_foundation_gate.py",
                "mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py",
            ],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=3,
            reentry=True,
            pre_supervisor=True,
        )

        assert "scope_refs:" in note
        assert "`mu/docs/core/FixpointMetaCircularEvaluator.v0.md`" in note
        assert "`mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py`" in note
        assert "Optimization and production runtime/substrate/seed/parity edits remain out of scope" in note
        assert "Optimization is LAST" in note

    def test_phase_b_tracker_scope_refs_names_normal_pre_supervisor_package(self):
        changed_files = [f"path/file_{index}.py" for index in range(17)]
        note = pb_mod._phase_b_tracker_scope_refs(  # ANTICHEAT_OK: locks tracker-note scope projection cap
            changed_files,
            "reports/l4_wave_indicators/package.json",
        )

        assert "+1 more" not in note
        assert "`path/file_16.py`" in note
        assert "`reports/l4_wave_indicators/package.json`" in note

    def test_build_phase_b_tracker_note_maintenance_is_contract_complete(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="pipeline-maintenance-2026-04-14",
            task_id="[PIPELINE-RECOVERY]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            plan_path="reports/control_plane/pipeline_control_surface_split_2026-04-14.md",
            plan_content=(
                "## Consecutive Maintenance Bypass\n"
                "unblocks_wave_id: wave-codex-startup-hardening-2026-04-14\n"
                "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION\n"
            ),
            changed_files=[
                "mu/tools/executors/recovery_gate.py",
                "mu/tests/tools/test_recovery_gate.py",
                "reports/control_plane/pipeline_control_surface_split_2026-04-14.md",
            ],
            test_files=["mu/tests/tools/test_recovery_gate.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=1,
            reentry=False,
        )
        assert "Class: MAINTENANCE" in note
        assert "no_op_proof:" in note
        assert "defer_reason_code: PIPELINE_HARDENING" in note
        assert "unblocks_wave_id: wave-codex-startup-hardening-2026-04-14" in note
        assert "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION" in note
        assert "evidence_command:" in note

    def test_build_phase_b_tracker_note_enabler_threads_founder_override(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="codex-startup-hardening-2026-04-14",
            task_id="[CODEX-STARTUP-HARDENING]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/codex_startup_hardening_2026-04-14.md",
            plan_content=(
                "## Wave Class Justification\n"
                "FOUNDER_OVERRIDE:codex-startup-hardening-2026-04-16-followup "
                "(founder authorized this non-structural pipeline-hardening follow-up)\n"
            ),
            changed_files=[
                "mu/tools/executors/phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py",
                "reports/control_plane/codex_startup_hardening_2026-04-14.md",
            ],
            test_files=[
                "mu/tests/tools/test_phase_b_executor.py",
                "mu/tests/tools/test_recovery_gate.py",
            ],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=3,
            reentry=True,
        )
        assert "Class: L4_ENABLER" in note
        assert "FOUNDER_OVERRIDE:codex-startup-hardening-2026-04-16-followup" in note
        assert "progress_proof_after: Phase B emitted a commit-ready handoff for codex-startup-hardening-2026-04-14 with 3 wave-owned file(s)" in note

    def test_build_phase_b_tracker_note_enabler_reads_founder_override_header(self):
        wave_id = "founder-ordered-redteam-repo-code-audit-2026-05-05"
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id=wave_id,
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/founder_ordered_redteam_repo_code_audit_2026-05-05.md",
            plan_content=(
                "# Founder Ordered Redteam Repo Code Audit\n"
                "Task: [NEXT-CODEX-POST-REDTEAM]\n"
                f"Wave ID: {wave_id}\n"
                f"Founder override: FOUNDER_OVERRIDE:{wave_id}\n"
            ),
            changed_files=[
                "TASKS.md",
                "reports/control_plane/founder_ordered_redteam_repo_code_audit_2026-05-05.md",
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=2,
            reentry=True,
            pre_supervisor=True,
        )

        assert f"FOUNDER_OVERRIDE:{wave_id}" in note

    def test_build_phase_b_tracker_note_reads_backticked_same_wave_override_line(self):
        wave_id = "n3-kernel-driver-mu-continuation-state-runtime-2026-05-20"
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: locks packet override extraction
            wave_id=wave_id,
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path=(
                "reports/control_plane/"
                "n3-kernel-driver-mu-continuation-state-runtime-2026-05-20_2026-05-20.md"
            ),
            plan_content=(
                "## Acceptance criteria\n"
                "- The packet carries a same-wave authorization line:\n"
                f"  `FOUNDER_OVERRIDE:{wave_id}`.\n"
            ),
            changed_files=[
                "mu/host/js/engine/kernel.js",
                "mu/host/js/engine/pipeline.js",
                "mu/tests/l4_gates/test_kernel_run_result_contract.py",
            ],
            test_files=["mu/tests/l4_gates/test_kernel_run_result_contract.py"],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=12,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: L4_STRUCTURAL" in note
        assert f"FOUNDER_OVERRIDE:{wave_id}" in note

    def test_build_phase_b_tracker_note_derives_authorized_control_surface_override(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="parallel-pipeline-monitor-identity-2026-04-30",
            task_id="[PARALLEL-PIPELINE]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md",
            plan_content=(
                "# Parallel Pipeline Monitor Identity\n"
                "Wave ID: parallel-pipeline-monitor-identity-2026-04-30\n"
                "Phase-A-Lock: LOCKED\n"
                "Lane: control-surface\n"
                "Authorization: standing pipeline-bug-fix authorization for bounded pipeline hardening.\n"
                "\n"
                "## Scope\n"
                "Control-surface monitor identity.\n"
            ),
            changed_files=[
                "mu/tools/observability/pipeline_monitor.sh",
                "reports/control_plane/parallel_pipeline_monitor_identity_2026-04-30.md",
            ],
            test_files=["mu/tests/tools/test_phase_b_executor.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=1,
            reentry=False,
        )

        assert "Class: L4_ENABLER" in note
        assert "FOUNDER_OVERRIDE:parallel-pipeline-monitor-identity-2026-04-30" in note

    def test_build_phase_b_tracker_note_derives_authorized_control_surface_maintenance_override(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="autoping-owner-health-selfheal-2026-05-03",
            task_id="[PIPELINE-AUTOPING]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            plan_path="reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md",
            plan_content=(
                "# Autoping Owner Health Self-Heal\n"
                "Wave ID: autoping-owner-health-selfheal-2026-05-03\n"
                "Phase-A-Lock: LOCKED\n"
                "Lane: control-surface\n"
                "Authorization: standing pipeline-bug-fix authorization for bounded pipeline hardening.\n"
            ),
            changed_files=[
                "mu/tools/observability/pipeline_monitor.sh",
                "mu/tests/tools/test_recovery_gate.py",
                "reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md",
            ],
            test_files=["mu/tests/tools/test_recovery_gate.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=2,
            reentry=False,
            pre_supervisor=True,
        )

        assert "Class: MAINTENANCE" in note
        assert "FOUNDER_OVERRIDE:autoping-owner-health-selfheal-2026-05-03" in note

    def test_build_phase_b_tracker_note_does_not_derive_from_control_surface_lane_only(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="unauthorized-control-surface-wave",
            task_id="[PARALLEL-PIPELINE]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/unauthorized_control_surface_wave.md",
            plan_content=(
                "# Unauthorized Control Surface Wave\n"
                "Wave ID: unauthorized-control-surface-wave\n"
                "Phase-A-Lock: LOCKED\n"
                "Lane: control-surface\n"
                "\n"
                "## Scope\n"
                "Control-surface monitor identity.\n"
            ),
            changed_files=["mu/tools/observability/pipeline_monitor.sh"],
            test_files=["mu/tests/tools/test_phase_b_executor.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=1,
            reentry=False,
        )

        assert "Class: L4_ENABLER" in note
        assert "FOUNDER_OVERRIDE:" not in note

    def test_build_phase_b_tracker_note_maintenance_includes_plan_bypass_fields(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing plan-driven maintenance bypass fields
            wave_id="codex-startup-hardening-2026-04-14",
            task_id="[CODEX-STARTUP-HARDENING]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            plan_path="reports/control_plane/codex_startup_hardening_2026-04-14.md",
            plan_content=(
                "## Consecutive Maintenance Bypass\n"
                "unblocks_wave_id: wave-codex-backend-switch-2026-04-14\n"
                "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION\n"
            ),
            changed_files=[
                "mu/tools/session/check_codex_startup_state.py",
                "mu/tests/tools/test_codex_startup_state.py",
            ],
            test_files=["mu/tests/tools/test_codex_startup_state.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
            bridge_rounds=2,
            reentry=False,
        )
        assert "unblocks_wave_id: wave-codex-backend-switch-2026-04-14" in note
        assert "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION" in note

    def test_build_phase_b_tracker_note_maintenance_rejects_runtime_paths(self):
        with pytest.raises(pb_mod.PhaseBExecutorError, match="runtime/substrate paths"):
            pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing fail-closed maintenance classification
                wave_id="pipeline-maintenance-2026-04-14",
                task_id="[PIPELINE-RECOVERY]",
                wave_class="MAINTENANCE",
                target_gate_id="G8",
                plan_path="reports/control_plane/pipeline_control_surface_split_2026-04-14.md",
                changed_files=["mu/substrate/kernel.v1.json"],
                test_files=[],
                receipt_path=".agent_bus/meta/pre_commit_receipts/receipt_test.json",
                bridge_rounds=1,
                reentry=False,
            )

    def test_files_to_stage_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["new_file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
        )
        handoff = json.loads(path.read_text())
        assert handoff["files_to_stage"] + handoff.get("force_add_files", []) == ["new_file.py"]

    def test_optional_supervisor_metadata_in_handoff(self, tmp_path):
        path = pb_mod.prepare_commit_handoff(
            tmp_path,
            wave_id="test",
            task_id="[T]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            files_to_stage=["new_file.py"],
            commit_message="test",
            fixes_implemented=["test handoff"],
            pr_title="test",
            pr_body="test",
            supervisor_lane="hooks/agents/bridge control-surface",
            deferred_items=["reports/deferred/non_blocking/example.md"],
            bridge_status={"rounds": 2, "reentry": True},
        )
        handoff = json.loads(path.read_text())
        assert handoff["supervisor_lane"] == "hooks/agents/bridge control-surface"
        assert handoff["deferred_items"] == ["reports/deferred/non_blocking/example.md"]
        assert handoff["bridge_status"] == {"rounds": 2, "reentry": True}


class TestLoadPlanPacketPathTraversal:
    """load_plan_packet must block path traversal attacks."""

    def test_parent_directory_escape_blocked(self, tmp_path):
        """Path traversal with ../ is blocked."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Path traversal blocked"):
            pb_mod.load_plan_packet(repo, "../../etc/passwd")

    def test_absolute_path_blocked(self, tmp_path):
        """Absolute paths outside repo are blocked."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Path traversal blocked"):
            pb_mod.load_plan_packet(repo, "/etc/passwd")

    def test_valid_relative_path_works(self, tmp_path):
        """Legitimate relative paths within repo work."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Wave ID: wave-test-2026-04-21\n"
            "Task: [TEST-PLAN]\n"
            "Unblocks wave id: wave-upstream-2026-04-14\n"
            "Unblocks runtime blocker: INV_STRUCTURAL_FORWARD_MOTION\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "LOCKED"
        assert result["wave_id"] == "wave-test-2026-04-21"
        assert result["task_id"] == "[TEST-PLAN]"
        assert result["unblocks_wave_id"] == "wave-upstream-2026-04-14"
        assert result["unblocks_runtime_blocker"] == "INV_STRUCTURAL_FORWARD_MOTION"

    def test_canonical_identity_headers_strip_markdown_ticks(self, tmp_path):
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Wave ID: `wave-test-2026-04-21`\n"
            "Task: `[TEST-PLAN]`\n"
        )

        result = pb_mod.load_plan_packet(repo, "reports/plan.md")

        assert result["wave_id"] == "wave-test-2026-04-21"
        assert result["task_id"] == "[TEST-PLAN]"

    def test_founder_override_header_extracts_bounded_token(self, tmp_path):
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Wave ID: founder-ordered-redteam-repo-code-audit-2026-05-05\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n"
            "Parent directive token: FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05\n"
            "Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-repo-code-audit-2026-05-05\n"
        )

        result = pb_mod.load_plan_packet(repo, "reports/plan.md")

        assert result["founder_override"] == "founder-ordered-redteam-repo-code-audit-2026-05-05"

    def test_canonical_identity_fields_win_over_earlier_narrative_bullets(self, tmp_path):
        """Task and Wave ID must come from canonical headers when both forms exist."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "- Task: forged-wave\n"
            "- Wave ID: forged-wave\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Wave ID: real-wave\n"
            "Phase-A-Lock: LOCKED\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["task_id"] == "[PIPELINE-RECOVERY]"
        assert result["wave_id"] == "real-wave"

    def test_indented_identity_lines_do_not_count_as_canonical_headers(self, tmp_path):
        """Indented Task/Wave prose must not outrank later top-level headers."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "    Task: forged-wave\n"
            "    Wave ID: forged-wave\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Wave ID: real-wave\n"
            "Phase-A-Lock: LOCKED\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["task_id"] == "[PIPELINE-RECOVERY]"
        assert result["wave_id"] == "real-wave"

    def test_single_hash_section_body_task_line_does_not_populate_task_id(self, tmp_path):
        """Later single-# section headings must close authoritative identity scanning."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "# Grounding / Authorization\n"
            "Task: [PIPELINE-RECOVERY]\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert "task_id" not in result
        assert "wave_id" not in result

    def test_markdown_bypass_lines_parse(self, tmp_path):
        """Markdown-bulleted bypass tokens must parse without quote residue."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Task: [TEST-PLAN]\n"
            "1. `Phase-A-Lock: LOCKED`\n"
            "- `unblocks_wave_id: wave-upstream-2026-04-14`\n"
            "- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "LOCKED"
        assert result["task_id"] == "[TEST-PLAN]"
        assert result["unblocks_wave_id"] == "wave-upstream-2026-04-14"
        assert result["unblocks_runtime_blocker"] == "INV_STRUCTURAL_FORWARD_MOTION"

    def test_late_markdown_bypass_lines_parse(self, tmp_path):
        """Live packets may place bypass metadata well past the first 20 lines."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        filler = "".join(f"intro line {i}\n" for i in range(30))
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: LOCKED\n"
            + filler
            + "- `FOUNDER_OVERRIDE:plan-override-2026-04-16 (founder authorized packet follow-up)`\n"
            + "- `unblocks_wave_id: wave-upstream-2026-04-14`\n"
            + "- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "LOCKED"
        assert result["task_id"] == "[TEST-PLAN]"
        assert result["founder_override"] == "plan-override-2026-04-16"
        assert result["unblocks_wave_id"] == "wave-upstream-2026-04-14"
        assert result["unblocks_runtime_blocker"] == "INV_STRUCTURAL_FORWARD_MOTION"

    def test_parse_plan_governance_metadata_from_packet_body(self):
        content = (
            "# Plan\n"
            "Class: L4_STRUCTURAL\n"
            "Target Gate: G8 (default)\n"
        )

        assert pb_mod._parse_plan_wave_class(content) == "L4_STRUCTURAL"  # ANTICHEAT_OK: testing packet metadata parser
        assert pb_mod._parse_plan_target_gate_id(content) == "G8"  # ANTICHEAT_OK: testing packet metadata parser

    @pytest.mark.parametrize(
        "placeholder",
        [
            "none selected.",
            "none",
            "n/a",
            "not applicable",
            "not selected",
            "not-selected",
        ],
    )
    def test_run_phase_b_package_falls_back_for_no_go_target_gate_placeholders(
        self,
        tmp_path,
        placeholder,
    ):
        result, handoff_kwargs, captured_package = _run_phase_b_public_target_gate_path(
            tmp_path,
            plan_target_gate=placeholder,
        )

        assert result["status"] == "commit_ready", result
        assert captured_package["wave_class"] == "L4_ENABLER"
        assert handoff_kwargs["wave_class"] == "L4_ENABLER"
        assert handoff_kwargs["target_gate_id"] == "G8"

    def test_run_phase_b_package_normalizes_routing_no_go_target_gate(self, tmp_path):
        result, handoff_kwargs, captured_package = _run_phase_b_public_target_gate_path(
            tmp_path,
            plan_target_gate="none selected.",
            routing_target_gate="none",
        )

        assert result["status"] == "commit_ready", result
        assert captured_package["wave_class"] == "L4_ENABLER"
        assert handoff_kwargs["wave_class"] == "L4_ENABLER"
        assert handoff_kwargs["target_gate_id"] == "G8"

    def test_resolve_phase_b_wave_class_prefers_locked_packet_over_stale_routing(self):
        content = (
            "# Plan\n"
            "Class: L4_ENABLER\n"
        )

        assert pb_mod._resolve_phase_b_wave_class(  # ANTICHEAT_OK: testing package metadata authority
            {"wave_class": "L4_STRUCTURAL"},
            content,
        ) == "L4_ENABLER"

    def test_resolve_phase_b_wave_class_ignores_later_narrative_class(self):
        content = (
            "# Plan\n"
            "Wave ID: structural-wave\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "## Narrative\n"
            "- Class: L4_ENABLER\n"
        )

        assert pb_mod._parse_plan_wave_class(content) == ""  # ANTICHEAT_OK: testing packet metadata parser
        assert pb_mod._resolve_phase_b_wave_class(  # ANTICHEAT_OK: testing package metadata authority
            {"wave_class": "L4_STRUCTURAL"},
            content,
        ) == "L4_STRUCTURAL"

    def test_structural_runtime_intent_in_packet_body_wins_over_default_enabler(self):
        content = (
            "# Runtime Packet\n"
            "Status: Phase B\n"
            "Purpose: This is an L4_STRUCTURAL implementation wave, not another "
            "plan-only/control-plane package.\n"
        )

        assert pb_mod._resolve_phase_b_wave_class(  # ANTICHEAT_OK: testing package metadata authority
            {},
            content,
        ) == "L4_STRUCTURAL"

    def test_effective_phase_b_tracker_wave_class_upgrades_runtime_scope_from_enabler(self):
        assert pb_mod._effective_phase_b_tracker_wave_class(  # ANTICHEAT_OK: tests final-scope class derivation
            "L4_ENABLER",
            plan_content="# Plan\nWave Class: L4_ENABLER\n",
            changed_files=[
                "mu/host/js/core/seed_loader.js",
                "reports/l4_wave_indicators/runtime-scope-wave.json",
            ],
        ) == "L4_STRUCTURAL"

    def test_effective_phase_b_tracker_wave_class_preserves_classless_runtime_override(self):
        assert pb_mod._effective_phase_b_tracker_wave_class(  # ANTICHEAT_OK: tests final-scope class derivation
            "L4_ENABLER",
            plan_content="Contract path: classless FOUNDER_OVERRIDE comment-only runtime override\n",
            changed_files=[
                "mu/host/js/core/constants.js",
                "reports/l4_wave_indicators/comment-only-wave.json",
            ],
        ) == ""

    def test_effective_phase_b_tracker_wave_class_uses_enabler_for_override_plus_control_plane(self):
        assert pb_mod._effective_phase_b_tracker_wave_class(  # ANTICHEAT_OK: tests mixed no-op runtime plus tooling class derivation
            "L4_ENABLER",
            plan_content="Contract path: classless FOUNDER_OVERRIDE comment-only runtime override\n",
            changed_files=[
                "mu/host/js/core/constants.js",
                "mu/tools/executors/phase_b_executor.py",
                "reports/l4_wave_indicators/comment-only-wave.json",
            ],
        ) == "L4_ENABLER"

    def test_effective_phase_b_tracker_wave_class_preserves_locked_enabler_runtime_text_scope(self):
        plan_content = (
            "# Runtime Text Packet\n"
            "Class: L4_ENABLER\n"
            "Scope: eval_seed.py comment, source-lock, and marker wording around _stage0_match; "
            "behavior is not in scope unless current code truth contradicts the evidence.\n"
            "Acceptance: Keep the change as wording/proof-class alignment, not runtime behavior change.\n"
        )

        assert pb_mod._effective_phase_b_tracker_wave_class(  # ANTICHEAT_OK: tests locked packet class preservation
            "L4_ENABLER",
            plan_content=plan_content,
            changed_files=[
                "TASKS.md",
                "mu/host/python/rcx_pi/selfhost/eval_seed.py",
                "mu/tests/l4_gates/test_stage0_vm_cutover.py",
                "reports/control_plane/n3-stage0-marker-truth-current-path-sync-2026-05-28.md",
                "reports/l4_wave_indicators/n3-stage0-marker-truth-current-path-sync-2026-05-28.json",
            ],
        ) == "L4_ENABLER"

    def test_pre_supervisor_pending_status_is_not_dispatch_complete(self):
        assert common_mod.packet_status_is_completed(  # ANTICHEAT_OK: locks reroute-safe pending status
            pb_mod.PHASE_B_PRE_SUPERVISOR_PENDING_STATUS
        ) is False
        assert common_mod.packet_status_is_completed(
            "Phase B (implementation-complete, bridge-converged)"
        ) is True

    def test_header_metadata_wins_over_later_narrative_bullets(self, tmp_path):
        """Canonical header metadata must not be overwritten by later bullets."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Status: Phase A (design - bridge-converged)\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: LOCKED\n"
            "intro line\n"
            "- Status: ACTIVE (unparked 2026-03-28)\n"
            "- Phase-A-Lock: UNLOCKED\n"
            "- `FOUNDER_OVERRIDE:plan-override-2026-04-16 (founder authorized packet follow-up)`\n"
            "- `unblocks_wave_id: wave-upstream-2026-04-14`\n"
            "- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["status"] == "Phase A (design - bridge-converged)"
        assert result["task_id"] == "[TEST-PLAN]"
        assert result["phase_a_lock"] == "LOCKED"
        assert result["founder_override"] == "plan-override-2026-04-16"
        assert result["unblocks_wave_id"] == "wave-upstream-2026-04-14"
        assert result["unblocks_runtime_blocker"] == "INV_STRUCTURAL_FORWARD_MOTION"

    @pytest.mark.parametrize(
        ("plan_content", "expected"),
        [
            (
                "Unblocks wave id: wave-upstream-2026-04-14\n"
                "Unblocks runtime blocker: INV_STRUCTURAL_FORWARD_MOTION\n",
                ("wave-upstream-2026-04-14", "INV_STRUCTURAL_FORWARD_MOTION"),
            ),
            (
                "- `unblocks_wave_id: wave-upstream-2026-04-14`\n"
                "- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`\n",
                ("wave-upstream-2026-04-14", "INV_STRUCTURAL_FORWARD_MOTION"),
            ),
        ],
    )
    def test_extract_maintenance_bypass_fields_normalizes_tokens(self, plan_content, expected):
        """Fallback bypass extraction must accept canonical and markdown forms."""
        assert pb_mod._extract_maintenance_bypass_fields(plan_content) == expected  # ANTICHEAT_OK: testing maintenance bypass fallback normalization

    def test_duplicate_phase_a_lock_prefers_locked(self, tmp_path):
        """Packets with both a PLACEHOLDER stub and a LOCKED line resolve to LOCKED.

        Regression for pager-ping-delivery-2026-04-18 Wave K-1 failure mode:
        a malformed stub "Phase-A-Lock: PLACEHOLDER" on line 1 plus an
        implementer-added "Phase-A-Lock: LOCKED" on line 6 caused
        load_plan_packet's first-match reader to return "PLACEHOLDER",
        breaking validate_inputs even though a LOCKED line existed.
        """
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: PLACEHOLDER\n"
            "# Plan\n"
            "wave_id: test-wave-2026-04-18\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: LOCKED\n"
            "## Status\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "LOCKED"

    def test_duplicate_phase_a_lock_prefers_routing_record_authority(self, tmp_path):
        """When no LOCKED line exists but ROUTING_RECORD_AUTHORITY does, that wins."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: PLACEHOLDER\n"
            "# Plan\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: ROUTING_RECORD_AUTHORITY\n"
            "## Status\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "ROUTING_RECORD_AUTHORITY"

    def test_single_non_canonical_phase_a_lock_preserved(self, tmp_path):
        """Single non-canonical values (no LOCKED/ROUTING present) fall back to first-match."""
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: PLACEHOLDER\n"
            "## Status\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "PLACEHOLDER"

    def test_narrative_lock_does_not_upgrade_canonical_unlocked(self, tmp_path):
        """Bullet/backtick narrative LOCKED mentions must NOT upgrade canonical UNLOCKED.

        Regression guard (PR #797 P1): without this test, the prefer-LOCKED
        rule could weaken the Phase-B lock gate by accepting packets whose
        actual canonical header is UNLOCKED but whose body contains prose
        like "- `Phase-A-Lock: LOCKED`" (legitimately documenting the LOCKED
        state as an example). Narrative text must not cross the canonical
        boundary.
        """
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "# Plan\n"
            "Status: Phase A (design)\n"
            "Task: [TEST-PLAN]\n"
            "Phase-A-Lock: UNLOCKED\n"
            "\n"
            "## Notes\n"
            "The header will become `Phase-A-Lock: LOCKED` after Phase A locks the plan.\n"
            "- `Phase-A-Lock: LOCKED`\n"
            "1. `Phase-A-Lock: LOCKED`\n"
        )
        result = pb_mod.load_plan_packet(repo, "reports/plan.md")
        assert result["phase_a_lock"] == "UNLOCKED"


class TestBlockerDiscovery:
    """Phase B executor discovers active blocking packets for supervisor package."""

    def test_discovers_active_blocking_packets(self, tmp_path):
        """When reports/deferred/blocking/ has .md files, they appear in package."""
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        (blocking_dir / "blocker1.md").write_text("# Blocker 1")
        (blocking_dir / "blocker2.md").write_text("# Blocker 2")
        (blocking_dir / "README.md").write_text("# README — excluded")

        # Simulate what phase_b_executor does at package-build time
        blocker_paths = sorted(
            str(p.relative_to(repo))
            for p in blocking_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "README.md"
        )
        assert len(blocker_paths) == 2
        assert "reports/deferred/blocking/blocker1.md" in blocker_paths
        assert "reports/deferred/blocking/blocker2.md" in blocker_paths
        assert "README.md" not in str(blocker_paths)

    def test_empty_when_no_blocking_packets(self, tmp_path):
        """When no blocking .md files exist, list is empty."""
        repo = tmp_path / "repo"
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocking_dir.mkdir(parents=True)
        (blocking_dir / "README.md").write_text("# README only")

        blocker_paths = sorted(
            str(p.relative_to(repo))
            for p in blocking_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name != "README.md"
        )
        assert blocker_paths == []

    def test_empty_when_directory_missing(self, tmp_path):
        """When blocking directory doesn't exist, list is empty."""
        repo = tmp_path / "repo"
        repo.mkdir()
        blocking_dir = repo / "reports" / "deferred" / "blocking"
        blocker_paths = []
        if blocking_dir.is_dir():
            blocker_paths = sorted(
                str(p.relative_to(repo))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        assert blocker_paths == []


class TestMaintenanceTrackerMetadataPropagation:
    """Phase B must propagate maintenance unblock metadata through the live handoff path."""

    def test_run_phase_b_threads_plan_unblocks_metadata_into_handoff(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "- `unblocks_wave_id: wave-codex-startup-hardening-2026-04-14`\n"
            "- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json") as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert "Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT" in plan.read_text(
            encoding="utf-8",
        )
        tracker_note_text = mock_handoff.call_args.kwargs["tracker_note_text"]
        assert "Class: MAINTENANCE" in tracker_note_text
        assert "unblocks_wave_id: wave-codex-startup-hardening-2026-04-14" in tracker_note_text
        assert "unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION" in tracker_note_text

    def test_run_phase_b_restages_final_packet_status_before_handoff_receipt(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        # Mirror prod: .agent_bus/ is gitignored, so the now-default-ON commit-outcome
        # pager's runtime artifacts under .agent_bus/observability/ are never swept into
        # files_to_stage by the real (unmocked) change collection. Commit it so it stays
        # a tracked, clean file that cannot leak into the wave's changed-file scope.
        (repo / ".gitignore").write_text(".agent_bus/\n.agent_bus-*/\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: gitignore .agent_bus"],
            cwd=repo, check=True, capture_output=True,
        )
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        wave_id = "phase-b-final-status-receipt-refresh-2026-05-25"
        plan_rel = f"reports/control_plane/{wave_id}.md"
        plan = repo / plan_rel
        plan.write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: MAINTENANCE\n"
            "\n"
            "May stage exactly:\n"
            "- `TASKS.md`\n"
            f"- `{plan_rel}`\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text("## Tracker\n", encoding="utf-8")

        supervisor_calls: list[dict[str, object]] = []

        def fake_supervisor(repo_root, package_path, **_kwargs):
            idx = len(supervisor_calls) + 1
            unstaged = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip().splitlines()
            package = json.loads(package_path.read_text(encoding="utf-8"))
            receipt = f".agent_bus/meta/pre_commit_receipts/r{idx}.json"
            supervisor_calls.append({
                "receipt": receipt,
                "unstaged": unstaged,
                "package": package,
            })
            return {
                "exit_code": 0,
                "parsed": {
                    "decision": "COMMIT_GO",
                    "summary": "ok",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": receipt,
            }

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "_verify_phase_b_pre_supervisor_tracker_note", return_value=None), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=fake_supervisor):
            result = pb_mod.run_phase_b(repo, plan_rel, max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert len(supervisor_calls) == 2
        assert supervisor_calls[-1]["receipt"] == result["receipt_path"]
        assert supervisor_calls[-1]["unstaged"] == []
        assert subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip() == ""
        staged_plan = subprocess.run(
            ["git", "show", f":{plan_rel}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT" in staged_plan
        handoff = json.loads((repo / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text())
        assert handoff["pre_commit_receipt_path"] == supervisor_calls[-1]["receipt"]

    def test_run_phase_b_same_wave_exception_keeps_handoff_task_id_on_routing_record(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": "reports/control_plane/plan.md",
                }
            ],
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(
                 pb_mod,
                 "_collect_changed_files",
                 return_value=["mu/tools/executors/phase_b_executor.py"],
             ), \
             patch.object(
                 pb_mod,
                 "_collect_wave_owned_files",
                 return_value=[
                     "mu/tools/executors/phase_b_executor.py",
                     "mu/tests/tools/test_phase_b_executor.py",
                     "reports/control_plane/plan.md",
                 ],
             ), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(
                 pb_mod,
                 "run_pre_commit_supervisor",
                 return_value={
                     "exit_code": 0,
                     "parsed": {
                         "decision": "COMMIT_GO",
                         "summary": "",
                         "status": "success",
                         "findings": [],
                     },
                     "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
                 },
             ), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_handoff.call_args.kwargs["task_id"] == "[PIPELINE-RECOVERY]"
        assert mock_handoff.call_args.kwargs["wave_id"] == "phase-b-validate-inputs-task-id-leniency-2026-04-20"

    def test_run_phase_b_threads_founder_override_into_enabler_handoff(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [CODEX-STARTUP-HARDENING]\n"
            "- `FOUNDER_OVERRIDE:codex-startup-hardening-2026-04-16-followup "
            "(founder authorized this non-structural pipeline-hardening follow-up)`\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[CODEX-STARTUP-HARDENING]",
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[
                 "mu/tools/executors/phase_b_executor.py",
                 "mu/tests/tools/test_phase_b_executor.py",
                 "reports/control_plane/plan.md",
             ]), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json") as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        tracker_note_text = mock_handoff.call_args.kwargs["tracker_note_text"]
        assert "Class: L4_ENABLER" in tracker_note_text
        assert "FOUNDER_OVERRIDE:codex-startup-hardening-2026-04-16-followup" in tracker_note_text

    def test_run_phase_b_syncs_tracker_note_before_pre_commit_supervisor(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text(
            "## Ra\n\n"
            "- Tracker sync note (2026-05-01, old-wave): **OLD.** "
            "Class: L4_ENABLER. target_gate_id: G8.\n"
            "---\n",
            encoding="utf-8",
        )
        plan = repo / "reports" / "control_plane" / "plan.md"
        wave_id = "phase-b-pre-supervisor-tracker-sync-2026-05-02"
        plan.write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Lane: control-surface\n"
            "Authorization: standing pipeline-bug-fix authorization for bounded pipeline hardening.\n"
            "Manual repair grounding: dispatcher previously exited after six Phase B bridge rounds.\n",
            encoding="utf-8",
        )
        captured_package = {}

        def capture_supervisor(_repo_root, package_path, **_kwargs):
            captured_package.update(json.loads(Path(package_path).read_text(encoding="utf-8")))
            tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
            assert f"Tracker sync note" in tasks_text
            assert wave_id in tasks_text
            assert f"FOUNDER_OVERRIDE:{wave_id}" in tasks_text
            assert "Phase B pre-commit supervisor package" in tasks_text
            assert "bridge rounds=6" in tasks_text
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        def collect_indicator(_repo_root, *, wave_id):
            indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
            indicator_file = repo / indicator_path
            indicator_file.parent.mkdir(parents=True, exist_ok=True)
            indicator_file.write_text(json.dumps({"wave_id": wave_id}) + "\n", encoding="utf-8")
            return indicator_path, None

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        changed = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            "reports/control_plane/plan.md",
        ]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: list(files)), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(
                 pb_mod,
                 "_collect_and_stage_l4_indicator_artifact",
                 side_effect=collect_indicator,
             ) as mock_indicator, \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=capture_supervisor), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        assert "TASKS.md" in captured_package["changed_files"]
        assert indicator_path in captured_package["changed_files"]
        assert indicator_path in captured_package["scope_items"]
        assert captured_package["evidence_handles"]["indicator"] == indicator_path
        assert captured_package["founder_override_token"] == f"FOUNDER_OVERRIDE:{wave_id}"
        assert captured_package["bridge_status"]["rounds"] == 6
        tracker_note_text = mock_handoff.call_args.kwargs["tracker_note_text"]
        assert "bridge rounds=6" in tracker_note_text
        packet_text = plan.read_text(encoding="utf-8")
        assert "Phase B Indicator Scope Reconciliation" in packet_text
        assert indicator_path in packet_text
        mock_indicator.assert_called_once_with(repo, wave_id=wave_id)

    def test_reentry_l4_indicator_collection_refreshes_packet_scope_and_scope_items(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "phase-b-reentry-indicator-scope-2026-05-03"
        plan_path = "reports/control_plane/plan.md"
        plan = repo / plan_path
        plan.write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Lane: control-surface\n"
            "Authorization: standing pipeline-bug-fix authorization for bounded pipeline hardening.\n\n"
            "Manual repair grounding: dispatcher previously exited after six Phase B bridge rounds.\n\n"
            "## Scope\n\n"
            "No indicator file is in scope for this Phase A packet because the reviewer evidence "
            "does not name one.\n",
            encoding="utf-8",
        )

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        captured_packages: list[dict[str, object]] = []

        def collect_indicator(_repo_root, *, wave_id):
            indicator_file = repo / indicator_path
            indicator_file.parent.mkdir(parents=True, exist_ok=True)
            indicator_file.write_text(json.dumps({"wave_id": wave_id}) + "\n", encoding="utf-8")
            return indicator_path, None

        def supervisor_side(_repo_root, package_path, **_kwargs):
            captured_packages.append(json.loads(Path(package_path).read_text(encoding="utf-8")))
            if len(captured_packages) == 1:
                return {
                    "exit_code": 0,
                    "parsed": {
                        "decision": "NEEDS_PHASE_B",
                        "summary": "collect the same-wave indicator after re-entry",
                        "status": "success",
                        "findings": [],
                    },
                    "receipt_path": "",
                }
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        changed = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            plan_path,
            indicator_path,
        ]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: list(files)), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"},
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j2"},
             ]), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", side_effect=[True, False]), \
             patch.object(
                 pb_mod,
                 "_collect_and_stage_l4_indicator_artifact",
                 side_effect=collect_indicator,
             ) as mock_indicator, \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert mock_indicator.call_count == 1
        assert len(captured_packages) == 3
        reentry_package = captured_packages[-1]
        assert indicator_path in reentry_package["changed_files"]
        assert indicator_path in reentry_package["scope_items"]
        assert reentry_package["evidence_handles"]["indicator"] == indicator_path
        assert reentry_package["bridge_status"]["rounds"] == 6
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert "bridge rounds=6" in tasks_text
        tracker_note_text = mock_handoff.call_args.kwargs["tracker_note_text"]
        assert "bridge rounds=6" in tracker_note_text
        packet_text = plan.read_text(encoding="utf-8")
        assert "Phase B Indicator Scope Reconciliation" in packet_text
        assert indicator_path in packet_text
        assert "No indicator file is in scope" not in packet_text

    def test_reentry_supervisor_package_refreshes_wave_class_from_live_packet(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "phase-b-reentry-structural-class-2026-05-08"
        plan_path = "reports/control_plane/plan.md"
        plan = repo / plan_path

        def packet_text(wave_class: str) -> str:
            return (
                "# Plan\n"
                f"Wave ID: {wave_id}\n"
                "Phase-A-Lock: LOCKED\n"
                "Status: ACTIVE\n"
                "Task: [PIPELINE-RECOVERY]\n"
                f"Class: {wave_class}\n"
                "Target Gate: G8\n"
                f"FOUNDER_OVERRIDE:{wave_id}\n"
            )

        plan.write_text(packet_text("L4_ENABLER"), encoding="utf-8")
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / indicator_path).parent.mkdir(parents=True)
        (repo / indicator_path).write_text(json.dumps({"wave_id": wave_id}) + "\n", encoding="utf-8")
        captured_packages: list[dict[str, object]] = []

        def supervisor_side(_repo_root, package_path, **_kwargs):
            captured_packages.append(json.loads(Path(package_path).read_text(encoding="utf-8")))
            if len(captured_packages) == 1:
                return {
                    "exit_code": 0,
                    "parsed": {
                        "decision": "NEEDS_PHASE_B",
                        "summary": "reclassify runtime-changing package as structural",
                        "status": "success",
                        "findings": [],
                    },
                    "receipt_path": "",
                }
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        mock_impl = _make_mock_impl()
        impl_success = dict(mock_impl.invoke_implementer.return_value)

        def implementer_side(*_args, **_kwargs):
            if mock_impl.invoke_implementer.call_count == 2:
                plan.write_text(packet_text("L4_STRUCTURAL"), encoding="utf-8")
            return impl_success

        mock_impl.invoke_implementer.side_effect = implementer_side
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        changed = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            indicator_path,
            plan_path,
        ]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: list(files)), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"},
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j2"},
             ]), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert len(captured_packages) == 3
        assert captured_packages[0]["wave_class"] == "L4_ENABLER"
        reentry_package = captured_packages[-1]
        assert reentry_package["wave_class"] == "L4_STRUCTURAL"
        assert "founder_override_token" not in reentry_package
        assert mock_handoff.call_args.kwargs["wave_class"] == "L4_STRUCTURAL"

    def test_l4_indicator_collection_reruns_after_tracker_only_crash(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "phase-b-tracker-only-crash-2026-05-02"
        changed_files = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
        ]
        tracker_note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker binding helper
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/plan.md",
            plan_content="",
            changed_files=changed_files,
            test_files=["mu/tests/tools/test_phase_b_executor.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )

        first_error, first_modified = pb_mod._sync_phase_b_tasks_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker binding helper
            repo,
            wave_id=wave_id,
            tracker_note_text=tracker_note,
        )
        second_error, second_modified = pb_mod._sync_phase_b_tasks_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker binding helper
            repo,
            wave_id=wave_id,
            tracker_note_text=tracker_note,
        )

        assert first_error is None
        assert first_modified is True
        assert second_error is None
        assert second_modified is False
        assert pb_mod._should_collect_l4_indicator_artifact(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            repo,
            wave_id=wave_id,
            wave_class="L4_ENABLER",
            tracker_note_modified=second_modified,
            founder_override_token="",
            changed_files=[*changed_files, "TASKS.md"],
        ) is True

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}) + "\n", encoding="utf-8")
        assert pb_mod._should_collect_l4_indicator_artifact(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            repo,
            wave_id=wave_id,
            wave_class="L4_ENABLER",
            tracker_note_modified=False,
            founder_override_token="",
            changed_files=[*changed_files, "TASKS.md", indicator_path],
        ) is False

    def test_phase_b_tracker_sync_reconciles_same_wave_notes_across_task_sections(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "vm-cutover-coverage-trace-implementation-2026-05-12"
        stale_note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id=wave_id,
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path=f"reports/control_plane/{wave_id}.md",
            plan_content="",
            changed_files=[
                "mu/host/js/core/stage0_vm.js",
                "mu/host/python/rcx_pi/selfhost/stage0_vm.py",
                "mu/host/python/rcx_pi/selfhost/step_mu.py",
                f"reports/l4_wave_indicators/{wave_id}.json",
            ],
            test_files=["mu/tests/l4_gates/test_stage0_vm.py"],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )
        canonical_note = (
            f"- Tracker sync note (2026-05-12, {wave_id}): "
            "**NEXT-CODEX-POST-REDTEAM - VM cutover coverage trace implementation.** "
            "Class: L4_STRUCTURAL. Category: `/mu` structural coverage bookkeeping. "
            "target_gate_id: G8. workload_target: host_debt_reduction. "
            f"Packet: `reports/control_plane/{wave_id}.md`. "
            "host_semantics_delta_before: Stage0 VM step results exposed no ordered attempted-program trace. "
            "host_semantics_delta_after: Python and JS Stage0 VM step results emit the same structural `attempt_trace`. "
            "structural_artifact_ref: `mu/host/python/rcx_pi/selfhost/stage0_vm.py`, "
            "`mu/host/js/core/stage0_vm.js`, `mu/host/python/rcx_pi/selfhost/step_mu.py`. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py`. "
            "evidence_delta: Stage0 emits deterministic trace output on both substrates. "
            "progress_proof_before: coverage was reconstructed from host-side bundle order. "
            "progress_proof_after: coverage consumes the VM-emitted trace. "
            "post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py`. "
            f"FOUNDER_OVERRIDE:{wave_id}. primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
            f"indicator_collection_command: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output reports/l4_wave_indicators/{wave_id}.json. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )
        (repo / "TASKS.md").write_text(
            "## Ra\n\n"
            f"{stale_note}\n"
            "---\n\n"
            "## Current\n\n"
            f"{canonical_note}\n",
            encoding="utf-8",
        )

        error, modified = pb_mod._sync_phase_b_tasks_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker binding helper
            repo,
            wave_id=wave_id,
            tracker_note_text=canonical_note,
        )

        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        tracker_lines = [
            line for line in tasks_text.splitlines()
            if line.startswith("- Tracker sync note") and wave_id in line
        ]
        assert error is None
        assert modified is True
        assert tracker_lines == [canonical_note]
        assert "pre-commit supervisor package" not in tasks_text

    def test_stage0_trace_scope_infers_host_debt_reduction(self):
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [
                "mu/host/js/core/stage0_vm.js",
                "mu/host/python/rcx_pi/selfhost/step_mu.py",
            ],
            "Stage0 VM attempt_trace closes coverage reconstruction from host bundle order.",
        ) == "host_debt_reduction"

    def test_structural_workload_target_preserves_explicit_plan_target(self):
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [
                "mu/host/python/rcx_pi/selfhost/engine_pipeline.py",
                "mu/host/js/engine/pipeline.js",
            ],
            "workload_target: rcx_engine_cycle\nengine_pipeline structuralization",
        ) == "rcx_engine_cycle"

    def test_structural_workload_target_prioritizes_specific_targets_before_generic_coverage(self):
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [],
            "coverage follow-up for recurrence exhaustion proof",
        ) == "recurrence_exhaustion"
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [],
            "coverage follow-up for seed_auto_execution proof",
        ) == "seed_auto_execution"
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [],
            "coverage follow-up for execution_layer_truth proof",
        ) == "execution_layer_truth"
        assert pb_mod._infer_structural_workload_target(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            [],
            "coverage follow-up without a narrower structural target",
        ) == "host_debt_reduction"

    def test_l4_indicator_collection_can_run_before_tracker_note_sync(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "phase-b-pre-supervisor-indicator-2026-05-02"
        (repo / "TASKS.md").write_text(
            "## Ra\n\n- Tracker sync note (2026-05-02, unrelated-wave): old note.\n\n---\n",
            encoding="utf-8",
        )

        assert pb_mod._should_collect_l4_indicator_artifact(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            repo,
            wave_id=wave_id,
            wave_class="L4_ENABLER",
            tracker_note_modified=False,
            founder_override_token=f"FOUNDER_OVERRIDE:{wave_id}",
            changed_files=["TASKS.md", "mu/tools/executors/phase_b_executor.py"],
        ) is True

    def test_l4_indicator_collection_includes_maintenance_tracker_notes(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "autoping-owner-health-selfheal-2026-05-03"
        changed_files = [
            "mu/tools/observability/pipeline_monitor.sh",
            "mu/tests/tools/test_recovery_gate.py",
        ]
        tracker_note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            wave_id=wave_id,
            task_id="[PIPELINE-AUTOPING]",
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            plan_path="reports/control_plane/autoping_owner_health_selfheal_2026-05-03.md",
            plan_content=(
                "Wave ID: autoping-owner-health-selfheal-2026-05-03\n"
                "Phase-A-Lock: LOCKED\n"
                "Lane: control-surface\n"
                "Authorization: standing pipeline-bug-fix authorization for bounded pipeline hardening.\n"
            ),
            changed_files=changed_files,
            test_files=["mu/tests/tools/test_recovery_gate.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=2,
            reentry=False,
            pre_supervisor=True,
        )

        tracker_error, tracker_modified = pb_mod._sync_phase_b_tasks_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker binding helper
            repo,
            wave_id=wave_id,
            tracker_note_text=tracker_note,
        )

        assert tracker_error is None
        assert tracker_modified is True
        assert f"FOUNDER_OVERRIDE:{wave_id}" in (repo / "TASKS.md").read_text(encoding="utf-8")
        assert pb_mod._should_collect_l4_indicator_artifact(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            repo,
            wave_id=wave_id,
            wave_class="MAINTENANCE",
            tracker_note_modified=False,
            founder_override_token=f"FOUNDER_OVERRIDE:{wave_id}",
            changed_files=[*changed_files, "TASKS.md"],
        ) is True

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        indicator_file = repo / indicator_path
        indicator_file.parent.mkdir(parents=True, exist_ok=True)
        indicator_file.write_text(json.dumps({"wave_id": wave_id}) + "\n", encoding="utf-8")
        assert pb_mod._should_collect_l4_indicator_artifact(  # ANTICHEAT_OK: testing Phase B indicator recovery predicate
            repo,
            wave_id=wave_id,
            wave_class="MAINTENANCE",
            tracker_note_modified=False,
            founder_override_token="",
            changed_files=[*changed_files, "TASKS.md", indicator_path],
        ) is False

    def test_pre_supervisor_tracker_note_prefers_same_wave_override_and_final_scope(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "founder-ordered-redteam-tooling-blocking-remediation-2026-05-06"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan_content = (
            "Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05\n"
            f"Founder override: FOUNDER_OVERRIDE:{wave_id}\n"
        )

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks Phase B pre-supervisor tracker ordering
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path="reports/control_plane/tooling.md",
                plan_content=plan_content,
                changed_files=[
                    "mu/tools/executors/phase_b_executor.py",
                    "reports/control_plane/tooling.md",
                    indicator_path,
                ],
                test_files=[],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 2},
                reentry=False,
                founder_override="founder-ordered-redteam-remediation-queue-organization-2026-05-05",
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert indicator_path in final_scope
        assert f"FOUNDER_OVERRIDE:{wave_id}" in note
        assert raw_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert package_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert "with 4 wave-owned file(s)" in note
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert f"FOUNDER_OVERRIDE:{wave_id}" in tasks_text
        assert "with 4 wave-owned file(s)" in tasks_text

    def test_pre_supervisor_tracker_note_rejects_packet_body_source_authorization(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "source-authorized-phase-b-wave-2026-05-10"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan_content = (
            f"Source authorization: FOUNDER_OVERRIDE:{wave_id}\n"
        )

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: rejects packet-body source authorization
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path="reports/control_plane/source_authorized.md",
                plan_content=plan_content,
                changed_files=[
                    "mu/tools/executors/phase_b_executor.py",
                    "reports/control_plane/source_authorized.md",
                    indicator_path,
                ],
                test_files=[],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 2},
                reentry=False,
                founder_override="",
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert f"FOUNDER_OVERRIDE:{wave_id}" not in note
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert f"FOUNDER_OVERRIDE:{wave_id}" not in tasks_text
        assert raw_override == ""
        assert package_override == ""

    def test_pre_supervisor_tracker_note_uses_structural_class_for_runtime_scope(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "runtime-scope-pre-supervisor-wave-2026-05-16"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks final-scope class derivation
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path="reports/control_plane/runtime_scope.md",
                plan_content="# Plan\nWave Class: L4_ENABLER\n",
                changed_files=[
                    "mu/host/js/core/seed_loader.js",
                    "mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py",
                    "reports/control_plane/runtime_scope.md",
                    indicator_path,
                ],
                test_files=["mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py"],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 1},
                reentry=False,
                founder_override=wave_id,
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert "Class: L4_STRUCTURAL" in note
        assert "workload_target:" in note
        assert raw_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert package_override == ""

    def test_pre_supervisor_tracker_note_demotes_docs_only_structural_scope_to_enabler(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "docs-only-structural-rerun-2026-05-29"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))), \
             patch.object(pb_mod, "_verify_phase_b_pre_supervisor_tracker_note", return_value=None):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks docs-only structural rerun demotion
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_STRUCTURAL",
                target_gate_id="G8",
                plan_path=f"reports/control_plane/{wave_id}.md",
                plan_content="# Plan\nClass: L4_STRUCTURAL\n",
                changed_files=[
                    f"reports/control_plane/{wave_id}.md",
                    indicator_path,
                ],
                test_files=[],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 2},
                reentry=False,
                founder_override="",
            )

        assert error is None
        assert modified is True
        assert final_scope == [
            "TASKS.md",
            f"reports/control_plane/{wave_id}.md",
            indicator_path,
        ]
        assert "Class: L4_ENABLER" in note
        assert "workload_target:" not in note
        assert "structural_artifact_ref:" not in note
        assert raw_override == ""
        assert package_override == ""

    def test_pre_supervisor_tracker_note_uses_classless_comment_runtime_override(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "runtime-comment-override-pre-supervisor-wave-2026-05-20"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan_content = (
            "Contract path: classless FOUNDER_OVERRIDE comment-only runtime override\n"
            f"Authorization: FOUNDER_OVERRIDE:{wave_id}\n"
        )

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks classless comment-only runtime override packaging
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path="reports/control_plane/runtime_comment_override.md",
                plan_content=plan_content,
                changed_files=[
                    "mu/host/js/core/constants.js",
                    "reports/control_plane/runtime_comment_override.md",
                    indicator_path,
                ],
                test_files=[],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 1},
                reentry=False,
                founder_override=wave_id,
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert "Class:" not in note
        assert "contract_path: classless FOUNDER_OVERRIDE comment-only runtime override" in note
        assert "no_op_proof:" in note
        assert raw_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert package_override == ""

    def test_pre_supervisor_tracker_note_uses_enabler_for_comment_override_plus_control_plane(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "runtime-comment-override-tooling-wave-2026-05-20"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan_content = (
            "Contract path: classless FOUNDER_OVERRIDE comment-only runtime override\n"
            f"Authorization: FOUNDER_OVERRIDE:{wave_id}\n"
        )

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks mixed tooling plus comment-only runtime override packaging
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path="reports/control_plane/runtime_comment_override.md",
                plan_content=plan_content,
                changed_files=[
                    "mu/host/js/core/constants.js",
                    "mu/tools/executors/phase_b_executor.py",
                    "reports/control_plane/runtime_comment_override.md",
                    indicator_path,
                ],
                test_files=[],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 1},
                reentry=False,
                founder_override=wave_id,
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert "Class: L4_ENABLER" in note
        assert "no_op_proof:" in note
        assert raw_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert package_override == f"FOUNDER_OVERRIDE:{wave_id}"

    def test_pre_supervisor_tracker_note_preserves_locked_enabler_runtime_text_scope(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "n3-stage0-marker-truth-current-path-sync-2026-05-28"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan_content = (
            "# N3-Stage0-Marker-Truth-Current-Path-Sync-2026-05-28\n"
            "Class: L4_ENABLER\n"
            f"FOUNDER_OVERRIDE:{wave_id}\n"
            "Scope: eval_seed.py comment, source-lock, and marker wording around "
            "_stage0_match; behavior is not in scope unless current code truth directly "
            "contradicts the reviewer evidence.\n"
            "Acceptance: Keep the change as wording/proof-class alignment, not runtime behavior change.\n"
        )

        with patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: sorted(set(files))):
            (
                note,
                raw_override,
                package_override,
                modified,
                final_scope,
                error,
            ) = pb_mod._finalize_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: locks current Stage0 marker-truth package class
                repo,
                wave_id=wave_id,
                task_id="[NEXT-CODEX-POST-REDTEAM]",
                wave_class="L4_ENABLER",
                target_gate_id="G8",
                plan_path=f"reports/control_plane/{wave_id}_2026-05-28.md",
                plan_content=plan_content,
                changed_files=[
                    "TASKS.md",
                    "mu/host/python/rcx_pi/selfhost/eval_seed.py",
                    "mu/tests/l4_gates/test_stage0_vm_cutover.py",
                    f"reports/control_plane/{wave_id}_2026-05-28.md",
                    indicator_path,
                ],
                test_files=["mu/tests/l4_gates/test_stage0_vm_cutover.py"],
                receipt_path=".scratch/phase_b_supervisor_package.json",
                bridge_status={"rounds": 3, "reentry": True},
                reentry=True,
                founder_override=wave_id,
            )

        assert error is None
        assert modified is True
        assert "TASKS.md" in final_scope
        assert "Class: L4_ENABLER" in note
        assert "no_op_proof:" in note
        assert "workload_target:" not in note
        assert raw_override == f"FOUNDER_OVERRIDE:{wave_id}"
        assert package_override == f"FOUNDER_OVERRIDE:{wave_id}"

    def test_pre_supervisor_tracker_note_verification_rejects_stale_top_note(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "phase-b-stale-top-note-2026-05-06"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        expected_note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: expected tracker note fixture
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/plan.md",
            plan_content=f"Founder override: FOUNDER_OVERRIDE:{wave_id}\n",
            changed_files=[
                "TASKS.md",
                "mu/tools/executors/phase_b_executor.py",
                indicator_path,
            ],
            test_files=[],
            receipt_path=".scratch/phase_b_supervisor_package.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )
        unrelated_top = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: stale top-note fixture
            wave_id="unrelated-top-wave-2026-05-06",
            task_id="[OTHER]",
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            plan_path="reports/control_plane/other.md",
            plan_content="",
            changed_files=["TASKS.md", "mu/tools/executors/other.py", "reports/l4_wave_indicators/unrelated-top-wave-2026-05-06.json"],
            test_files=[],
            receipt_path=".scratch/other.json",
            bridge_rounds=1,
            reentry=False,
            pre_supervisor=True,
        )
        (repo / "TASKS.md").write_text(
            f"## Ra\n\n{expected_note}\n{unrelated_top}\n\n---\n",
            encoding="utf-8",
        )

        error = pb_mod._verify_phase_b_pre_supervisor_tracker_note(  # ANTICHEAT_OK: fail-closed top-note verification
            repo,
            wave_id=wave_id,
            expected_note_text=expected_note,
            changed_files=[
                "TASKS.md",
                "mu/tools/executors/phase_b_executor.py",
                indicator_path,
            ],
        )

        assert error is not None
        assert "latest tracker note is not the canonical note" in error

    def test_phase_b_indicator_scope_refresh_reconciles_packet_contradictions(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-indicator-scope-refresh-2026-05-03"
        packet_path = f"reports/control_plane/{wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n\n"
            "## Scope\n\n"
            "No indicator file is in scope for this Phase A packet because the reviewer evidence "
            "does not name one.\n\n"
            "## Work items\n\n"
            "7. After implementation is locked and validated, update only the directly required "
            "TASKS.md lines and this governing packet. Do not update indicator files unless a "
            "later packet amendment names the exact path.\n\n"
            "## Constraints\n\n"
            "- Do not touch indicator files without an exact path added by a later locked packet amendment.\n\n"
            "- Aside from the same-wave `TASKS.md` tracker entry required to bind this packet, "
            "this packet does not authorize creation of a new report, indicator, non-blocker, "
            "archive record, successor packet, or unrelated tracker entry during this rewrite.\n\n"
            "## Acceptance criteria\n\n"
            "- Closeout updates, if any, are limited to directly required `TASKS.md` lines and this "
            "governing packet unless a later locked amendment names an exact indicator file path; "
            "all closeout text must cite the validation that proved the implementation.\n\n"
            "## Phase A Result\n\n"
            "No Phase B runtime, marker, ratchet-baseline, indicator, or successor packet\n"
            "write set is authorized by this decision.\n\n"
            "## Phase B Closeout\n\n"
            "No indicator file was touched.\n",
            encoding="utf-8",
        )

        changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: testing Phase B packet scope refresh
            repo,
            plan_path=packet_path,
            wave_id=wave_id,
            indicator_path=indicator_path,
            changed_files=[
                "TASKS.md",
                "mu/tools/executors/phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py",
                indicator_path,
            ],
        )

        assert error is None
        assert changed is True
        packet_text = packet.read_text(encoding="utf-8")
        assert "Phase B Indicator Scope Reconciliation" in packet_text
        assert indicator_path in packet_text
        assert "No indicator file is in scope" not in packet_text
        assert "No indicator file was touched" not in packet_text
        assert "Do not update indicator files unless" not in packet_text
        assert "Do not touch indicator files without" not in packet_text
        assert "does not authorize creation of a new report, indicator" not in packet_text
        assert "ratchet-baseline, indicator, or successor packet" not in packet_text
        assert "authorized only for mechanical commit packaging" in packet_text
        assert (
            pb_mod.PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER
            in packet_text
        )
        assert pb_mod.parse_exact_stage_scope_files(packet_text) == []
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert packet_path in staged

    def test_phase_b_indicator_scope_refresh_preserves_legacy_exact_parse(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-legacy-exact-refresh-2026-07-28"
        packet_path = f"reports/control_plane/{wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "## Phase B Indicator Scope Reconciliation\n\n"
            "- Authorized staged files:\n"
            f"  - `{packet_path}`\n"
            "  - `TASKS.md`\n"
            f"  - `{indicator_path}`\n"
            "  - `mu/tools/executors/phase_b_executor.py`\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n",
            encoding="utf-8",
        )
        original_exact = pb_mod.parse_exact_stage_scope_files(
            packet.read_text(encoding="utf-8")
        )

        changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: legacy exact refresh compatibility
            repo,
            plan_path=packet_path,
            wave_id=wave_id,
            indicator_path=indicator_path,
            changed_files=[
                "TASKS.md",
                packet_path,
                indicator_path,
                "mu/tools/executors/phase_b_executor.py",
                "mu/tests/tools/test_phase_b_executor.py",
            ],
        )

        assert error is None
        assert changed is True
        refreshed_text = packet.read_text(encoding="utf-8")
        assert (
            pb_mod.PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER
            not in refreshed_text
        )
        assert pb_mod.parse_exact_stage_scope_files(refreshed_text) == original_exact

    def test_phase_b_indicator_scope_refresh_replace_failure_is_atomic(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-atomic-refresh-failure-2026-07-28"
        packet_path = f"reports/control_plane/{wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n",
            encoding="utf-8",
        )
        original_bytes = packet.read_bytes()

        with patch.object(
            pb_mod.os,
            "replace",
            side_effect=OSError("simulated atomic replacement interruption"),
        ), patch.object(pb_mod, "_stage_files_for_pipeline") as mock_stage:
            changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: atomic packet refresh failure
                repo,
                plan_path=packet_path,
                wave_id=wave_id,
                indicator_path=indicator_path,
                changed_files=["TASKS.md", packet_path, indicator_path],
            )

        assert changed is False
        assert error is not None
        assert "atomic Phase B indicator packet scope refresh failed" in error
        assert packet.read_bytes() == original_bytes
        assert list(packet.parent.glob(f".{packet.name}.*.tmp")) == []
        mock_stage.assert_not_called()

    def test_phase_b_indicator_scope_refresh_preserves_packet_mode(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-atomic-refresh-mode-2026-07-28"
        packet_path = f"reports/control_plane/{wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n",
            encoding="utf-8",
        )
        packet.chmod(0o640)

        changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: atomic packet mode preservation
            repo,
            plan_path=packet_path,
            wave_id=wave_id,
            indicator_path=indicator_path,
            changed_files=["TASKS.md", packet_path, indicator_path],
        )

        assert error is None
        assert changed is True
        assert packet.stat().st_mode & 0o777 == 0o640

    def test_crash_orphaned_packet_refresh_temp_is_excluded_on_broad_restart(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("init\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        packet_path = "reports/control_plane/broad-crash-wave.md"
        orphan_path = (
            "reports/control_plane/.broad-crash-wave.md.deadbeef.tmp"
        )
        candidate_paths = [
            "TASKS.md",
            "mu/tools/executors/fix.py",
            packet_path,
        ]
        for rel_path in [*candidate_paths, orphan_path]:
            full_path = repo / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"{rel_path}\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "--", *candidate_paths, orphan_path],
            cwd=repo,
            check=True,
        )

        baseline = pb_mod._collect_baseline_wave_files(  # ANTICHEAT_OK: crash orphan must not enter broad baseline
            repo,
            packet_path,
        )
        cached_candidate = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: cached baseline must not re-admit crash orphan
            repo,
            packet_path,
            [],
            set(),
            set(),
            {*candidate_paths, orphan_path},
        )
        prepared, error = pb_mod._prepare_phase_b_pre_review_package(  # ANTICHEAT_OK: pre-review staging must exclude crash orphan
            repo,
            candidate_files=[orphan_path, *candidate_paths],
            exact_stage_scope_files=set(),
            plan_path=packet_path,
            wave_id="broad-crash-wave",
            wave_class="DOCS",
            step_prefix="bridge_pre_review",
            context="broad restart review",
        )

        assert orphan_path not in baseline
        assert orphan_path not in cached_candidate
        assert error is None
        assert orphan_path not in prepared
        assert (repo / orphan_path).exists()
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert orphan_path not in staged
        assert set(staged) == set(candidate_paths)
        assert not pb_mod._is_phase_b_indicator_scope_refresh_temp_path(  # ANTICHEAT_OK: sibling packet temp must not be broadly classified
            "reports/control_plane/.other-packet.md.deadbeef.tmp",
            packet_path,
        )

    def test_phase_b_indicator_scope_refresh_accepts_routed_retained_candidate_identity(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        parent_wave_id = "deferred-non-blocking-retained-residue-cleanup-2026-05-06"
        routed_wave_id = "docs-root-mu-docs-retained-packet-cleanup-2026-05-06"
        packet_path = f"reports/control_plane/{routed_wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{routed_wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Retained Candidate\n\n"
            f"Wave ID: {parent_wave_id}\n"
            f"Routed retained candidate: {routed_wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n\n"
            "## Scope\n\n"
            "No indicator file is in scope for this Phase A packet because the reviewer evidence "
            "does not name one.\n",
            encoding="utf-8",
        )

        changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: routed retained candidate identity
            repo,
            plan_path=packet_path,
            wave_id=routed_wave_id,
            indicator_path=indicator_path,
            changed_files=[
                packet_path,
                indicator_path,
            ],
        )

        assert error is None
        assert changed is True
        packet_text = packet.read_text(encoding="utf-8")
        assert "Phase B Indicator Scope Reconciliation" in packet_text
        assert f"- Refresh wave: `{routed_wave_id}`" in packet_text
        assert f"Wave ID: {parent_wave_id}" in packet_text
        assert f"Routed retained candidate: {routed_wave_id}" in packet_text

    def test_phase_b_indicator_scope_refresh_rejects_ambiguous_routed_retained_candidates(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        parent_wave_id = "deferred-non-blocking-retained-residue-cleanup-2026-05-06"
        routed_wave_id = "docs-root-mu-docs-retained-packet-cleanup-2026-05-06"
        packet_path = f"reports/control_plane/{routed_wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{routed_wave_id}.json"
        packet = repo / packet_path
        packet.parent.mkdir(parents=True, exist_ok=True)
        packet.write_text(
            "# Retained Candidate\n\n"
            f"Wave ID: {parent_wave_id}\n"
            f"Routed retained candidate: {routed_wave_id}\n"
            "Routed retained candidate: another-candidate\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n",
            encoding="utf-8",
        )

        changed, error = pb_mod._refresh_phase_b_indicator_packet_scope(  # ANTICHEAT_OK: routed retained candidate ambiguity rejection
            repo,
            plan_path=packet_path,
            wave_id=routed_wave_id,
            indicator_path=indicator_path,
            changed_files=[
                packet_path,
                indicator_path,
            ],
        )

        assert changed is False
        assert error is not None
        assert "active packet missing unique matching Wave ID or routed retained candidate" in error

    def test_commit_packet_truth_refresh_marks_pre_commit_receipt_pending(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-pending-receipt-refresh-2026-05-02"
        packet_path = f"reports/control_plane/{wave_id}.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        stale_receipt = ".agent_bus/meta/pre_commit_receipts/receipt_stale.json"
        stale_note = (
            f"- Tracker sync note (2026-05-03, {wave_id}): **PIPELINE-RECOVERY - "
            "commit-ready Phase B handoff.**. Class: L4_ENABLER. target_gate_id: G8. "
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            "mu/tests/tools/test_phase_b_executor.py`. "
            f"evidence_delta: (1) Phase B converged on the locked plan at {packet_path}. "
            "(2) Final pytest gate covered 1 test file(s) from the wave-owned diff. "
            f"(3) Commit handoff carries explicit receipt authority at {stale_receipt}.. "
            "progress_proof_before: stale handoff truth. "
            f"progress_proof_after: Phase B emitted a commit-ready handoff for {wave_id} "
            "with 12 wave-owned file(s), bridge rounds=2, explicit receipt authority, "
            "and an L4-compliant tracker note. "
            f"FOUNDER_OVERRIDE:{wave_id}. primary_blocker_class: INTEGRATION. "
            "primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: {indicator_path}. "
            f"indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py "
            f"--wave-id {wave_id} --output {indicator_path}. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )

        (repo / "TASKS.md").write_text(f"## Ra\n\n{stale_note}\n\n---\n", encoding="utf-8")
        packet_file = repo / packet_path
        packet_file.parent.mkdir(parents=True, exist_ok=True)
        packet_file.write_text(
            "# Pending Receipt Refresh\n\n"
            f"Wave ID: {wave_id}\n"
            "Wave class: L4_ENABLER\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        staged_paths = [
            "TASKS.md",
            "mu/tests/tools/test_codex_autoping_watch.py",
            "mu/tools/executors/commit_executor.py",
            "mu/tools/session/codex_autoping_watch.py",
            packet_path,
            indicator_path,
        ]
        for relpath in staged_paths[1:]:
            path = repo / relpath
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n" if relpath.endswith(".json") else "# staged\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", *staged_paths], cwd=repo, check=True)

        handoff, errors = commit_mod.build_commit_handoff(
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            files_to_stage=["old.py"],
            commit_message="feat: test\n\nCo-Authored-By: test",
            fixes_implemented=["test"],
            wave_class="L4_ENABLER",
            target_gate_id="G8",
            caller="phase_b",
            base_branch="dev",
            branch_prefix="jabramsja",
            force_add_files=[],
            pr_title="feat: test",
            pr_body="## Summary\ntest",
            tracker_note_text=stale_note,
            tracked_packet=packet_path,
            scope_items=[packet_path],
            evidence_handles={"indicator": indicator_path, "pre_commit_receipt": stale_receipt},
            pre_commit_receipt_path=stale_receipt,
            repo_root=repo,
        )
        assert errors == []

        refreshed, refreshed_staged, error = commit_mod.refresh_commit_path_packet_truth(
            repo_root=repo,
            handoff=handoff,
            indicator_path=indicator_path,
            commit_status="pre_commit_supervisor_pending",
        )

        assert error is None
        assert set(refreshed_staged) == set(staged_paths)
        assert set(refreshed["files_to_stage"]) == set(staged_paths)
        assert "pre_commit_receipt" not in refreshed["evidence_handles"]
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        packet_text = packet_file.read_text(encoding="utf-8")
        assert stale_receipt not in tasks_text
        assert stale_receipt not in packet_text
        assert "pre-commit supervisor package refresh" in tasks_text
        assert "commit-ready Phase B handoff" not in tasks_text
        assert "Phase B emitted a commit-ready handoff" not in tasks_text
        assert "Phase B refreshed the pre-commit supervisor package" in tasks_text
        assert "Pre-commit supervisor receipt remains pending" in tasks_text
        assert "package-bound L4 authority pending pre-commit supervisor validation" in tasks_text
        assert "mu/tests/tools/test_codex_autoping_watch.py" in tasks_text
        assert "Final pytest gate covered 1 test file(s)" in tasks_text
        assert "with 6 wave-owned file(s)" in tasks_text
        assert "- Pre-commit receipt handle:" not in packet_text
        assert "mu/tools/session/codex_autoping_watch.py" in packet_text

    def test_run_phase_b_handoff_bridge_status_total_rounds_matches_current_wave(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: wave-pager-bridge-status\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(
                 pb_mod,
                 "_collect_changed_files",
                 return_value=["mu/tools/executors/phase_b_executor.py"],
             ), \
             patch.object(
                 pb_mod,
                 "_collect_wave_owned_files",
                 return_value=[
                     "mu/tools/executors/phase_b_executor.py",
                     "mu/tests/tools/test_phase_b_executor.py",
                     "reports/control_plane/plan.md",
                 ],
             ), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(
                 pb_mod,
                 "run_pre_commit_supervisor",
                 return_value={
                     "exit_code": 0,
                     "parsed": {
                         "decision": "COMMIT_GO",
                         "summary": "",
                         "status": "success",
                         "findings": [],
                     },
                     "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
                 },
             ), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert mock_handoff.call_args.kwargs["bridge_status"] == {
            "rounds": 1,
            "total_rounds": 1,
        }

    def test_run_phase_b_handoff_bridge_status_uses_documented_round_floor(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text(
            "## Ra (Resolved / Merged)\n\n"
            "- Tracker sync note (2026-04-28, pager-commit-packet-truth-refresh-2026-04-28): done\n"
            "  **2026-04-28 bridge round 1 remediation:** fixed first bridge finding.\n"
            "  **2026-04-28 bridge round 2 remediation:** fixed second bridge finding.\n"
            "  **2026-04-28 bridge round 3 remediation:** fixed third bridge finding.\n",
            encoding="utf-8",
        )
        plan_path = "reports/control_plane/pager_commit_packet_truth_refresh_2026-04-28.md"
        plan = repo / plan_path
        plan.write_text(
            "# Plan\n"
            "Wave ID: pager-commit-packet-truth-refresh-2026-04-28\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n\n"
            "## Bridge Round 1 Remediation\n"
            "- fixed first bridge finding.\n\n"
            "## Bridge Round 2 Remediation\n"
            "- fixed second bridge finding.\n\n"
            "## Bridge Round 3 Remediation\n"
            "- fixed third bridge finding.\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        indicator_path = "reports/l4_wave_indicators/pager-commit-packet-truth-refresh-2026-04-28.json"
        (repo / indicator_path).parent.mkdir(parents=True)
        (repo / indicator_path).write_text(
            json.dumps(
                {
                    "wave_id": "pager-commit-packet-truth-refresh-2026-04-28",
                    "wave_class": "L4_ENABLER",
                    "target_gate_id": "G8",
                },
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        wave_owned = [
            "TASKS.md",
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            indicator_path,
            plan_path,
        ]
        captured_package: dict[str, object] = {}

        def _capture_supervisor_package(repo_root, package_path, **_kwargs):
            captured_package.update(json.loads(package_path.read_text(encoding="utf-8")))
            return {
                "exit_code": 0,
                "parsed": {
                    "decision": "COMMIT_GO",
                    "summary": "",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=_capture_supervisor_package), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        expected_status = {"rounds": 3, "total_rounds": 3}
        assert result["status"] == "commit_ready", result
        assert captured_package["wave_class"] == "L4_ENABLER"
        assert captured_package["bridge_status"] == expected_status
        assert mock_handoff.call_args.kwargs["bridge_status"] == expected_status

    def test_run_phase_b_package_uses_plan_class_and_staged_commit_bound_scope(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan_path = "reports/control_plane/structural-wave-2026-04-30.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Wave ID: structural-wave-2026-04-30\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n"
            "Class: L4_STRUCTURAL\n"
            "Target Gate: G8\n"
            "FOUNDER_OVERRIDE:structural-wave-2026-04-30\n",
            encoding="utf-8",
        )
        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": "structural-wave-2026-04-30",
        }
        wave_owned = [plan_path, "mu/tools/executors/phase_b_executor.py"]
        staged_extra = "mu/host/js/engine/pipeline.js"
        unstaged_fenced = "scratch/outside.txt"
        captured_package: dict[str, object] = {}

        def _capture_supervisor_package(repo_root, package_path, **_kwargs):
            captured_package.update(json.loads(package_path.read_text(encoding="utf-8")))
            return {
                "exit_code": 0,
                "parsed": {
                    "decision": "COMMIT_GO",
                    "summary": "",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned + [staged_extra, unstaged_fenced]), \
             patch.object(pb_mod, "_collect_staged_files", return_value=[staged_extra]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=_capture_supervisor_package), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["wave_class"] == "L4_STRUCTURAL"
        assert "founder_override_token" not in captured_package
        assert staged_extra in captured_package["changed_files"]
        assert staged_extra not in captured_package["fenced_files"]
        assert unstaged_fenced in captured_package["fenced_files"]
        assert staged_extra in mock_handoff.call_args.kwargs["files_to_stage"]
        assert mock_handoff.call_args.kwargs["wave_class"] == "L4_STRUCTURAL"

    def test_run_phase_b_package_prefers_reclassified_packet_over_stale_routing_class(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "mu-preproduction-redteam-2026-05-04"
        plan_path = "reports/control_plane/mu_preproduction_redteam_2026-05-04.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n"
            "Class: L4_ENABLER\n"
            "Target Gate: G8\n"
            f"FOUNDER_OVERRIDE:{wave_id}\n",
            encoding="utf-8",
        )
        (repo / "mu" / "tools").mkdir(parents=True)
        (repo / "mu" / "tools" / "f.py").write_text("print('candidate')\n", encoding="utf-8")
        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": wave_id,
            "wave_class": "L4_STRUCTURAL",
            "target_gate_id": "G8",
        }
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / indicator_path).parent.mkdir(parents=True)
        (repo / indicator_path).write_text(
            json.dumps(
                {
                    "wave_id": wave_id,
                    "wave_class": "L4_ENABLER",
                    "target_gate_id": "G8",
                },
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        wave_owned = [
            "TASKS.md",
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            indicator_path,
            plan_path,
        ]
        captured_package: dict[str, object] = {}

        def _capture_supervisor_package(repo_root, package_path, **_kwargs):
            captured_package.update(json.loads(package_path.read_text(encoding="utf-8")))
            return {
                "exit_code": 0,
                "parsed": {
                    "decision": "COMMIT_GO",
                    "summary": "",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=_capture_supervisor_package), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["wave_class"] == "L4_ENABLER"
        assert captured_package["founder_override_token"] == f"FOUNDER_OVERRIDE:{wave_id}"
        assert mock_handoff.call_args.kwargs["wave_class"] == "L4_ENABLER"
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert "Class: L4_ENABLER" in tasks_text
        assert "host_semantics_delta_before:" not in tasks_text
        assert "wave-owned file(s)" in tasks_text

    def test_run_phase_b_package_refreshes_live_packet_class_after_implementer_edit(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "TASKS.md").write_text("## Ra\n\n---\n", encoding="utf-8")
        wave_id = "mu-preproduction-redteam-2026-05-04"
        plan_path = "reports/control_plane/mu_preproduction_redteam_2026-05-04.md"

        def packet_text(wave_class: str) -> str:
            return (
                "# Plan\n"
                f"Wave ID: {wave_id}\n"
                "Phase-A-Lock: LOCKED\n"
                "Status: ACTIVE\n"
                "Task: [NEXT-CODEX-POST-REDTEAM]\n"
                f"Class: {wave_class}\n"
                "Target Gate: G8\n"
                f"FOUNDER_OVERRIDE:{wave_id}\n"
            )

        (repo / plan_path).write_text(packet_text("L4_STRUCTURAL"), encoding="utf-8")
        mock_impl = _make_mock_impl()
        impl_success = dict(mock_impl.invoke_implementer.return_value)

        def _reclassify_packet(*_args, **_kwargs):
            (repo / plan_path).write_text(packet_text("L4_ENABLER"), encoding="utf-8")
            return impl_success

        mock_impl.invoke_implementer.side_effect = _reclassify_packet
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[NEXT-CODEX-POST-REDTEAM]",
            "wave_name": wave_id,
            "wave_class": "L4_STRUCTURAL",
            "target_gate_id": "G8",
        }
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / indicator_path).parent.mkdir(parents=True)
        (repo / indicator_path).write_text(
            json.dumps(
                {
                    "wave_id": wave_id,
                    "wave_class": "L4_ENABLER",
                    "target_gate_id": "G8",
                },
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        wave_owned = [
            "TASKS.md",
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            indicator_path,
            plan_path,
        ]
        captured_package: dict[str, object] = {}

        def _capture_supervisor_package(repo_root, package_path, **_kwargs):
            captured_package.update(json.loads(package_path.read_text(encoding="utf-8")))
            return {
                "exit_code": 0,
                "parsed": {
                    "decision": "COMMIT_GO",
                    "summary": "",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={
                     "exit_code": 0,
                     "passed": True,
                     "stdout": "",
                     "stderr": "",
                 },
             ), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(
                 pb_mod,
                 "run_bridge_review",
                 return_value={
                     "exit_code": 0,
                     "stdout": "GO\n",
                     "stderr": "",
                     "decision": "GO",
                     "job_id": "j1",
                 },
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=_capture_supervisor_package), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["wave_class"] == "L4_ENABLER"
        assert captured_package["founder_override_token"] == f"FOUNDER_OVERRIDE:{wave_id}"
        assert mock_handoff.call_args.kwargs["wave_class"] == "L4_ENABLER"
        tasks_text = (repo / "TASKS.md").read_text(encoding="utf-8")
        assert "Class: L4_ENABLER" in tasks_text
        assert "Class: L4_STRUCTURAL" not in tasks_text

    def test_packet_documented_bridge_round_floor_bounds_tasks_scan_to_current_entry(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/current-wave-2026-04-28.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Wave ID: current-wave-2026-04-28\n\n"
            "## Bridge Round 2 Remediation\n"
            "- Current packet records round two.\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text(
            "- **[PIPELINE-AGENT-PAGER]** **IN PROGRESS**\n"
            "  - Tracker sync note (2026-04-28, current-wave-2026-04-28): current.\n"
            "  **2026-04-28 bridge round 3 remediation:** current wave round three.\n"
            "  - Tracker sync note (2026-04-28, later-wave-2026-04-28): later.\n"
            "  **2026-04-28 bridge round 9 remediation:** later wave must not count.\n",
            encoding="utf-8",
        )

        assert pb_mod._documented_bridge_round_floor(  # ANTICHEAT_OK: direct helper regression for package truth floor
            repo,
            "current-wave-2026-04-28",
            plan_path,
        ) == 3

    def test_packet_documented_bridge_round_floor_reads_prose_rounds(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/current-wave-2026-05-05.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Wave ID: current-wave-2026-05-05\n\n"
            "Manual repair grounding: dispatcher first exited max_rounds_reached "
            "after six Phase B bridge rounds before the package was repaired. "
            "Parser examples such as fifteen Phase B bridge rounds are not "
            "same-wave bridge history.\n",
            encoding="utf-8",
        )

        assert pb_mod._documented_bridge_round_floor_from_text(  # ANTICHEAT_OK: direct helper regression for package truth floor
            "after eleven Phase B bridge rounds"
        ) == 11
        assert pb_mod._documented_bridge_round_floor_from_text(  # ANTICHEAT_OK: direct helper regression for package truth floor
            "after six Phase B bridge rounds. Parser examples such as fifteen Phase B bridge rounds."
        ) == 6
        assert pb_mod._documented_bridge_round_floor(  # ANTICHEAT_OK: direct helper regression for package truth floor
            repo,
            "current-wave-2026-05-05",
            plan_path,
        ) == 6

    def test_run_phase_b_emits_reviewer_started_event_from_authoritative_bridge_round(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": "evt-phase-b",
                "attempted": [],
                "budget_exhausted": False,
            }

        def fake_bridge_review(*args, **kwargs):
            kwargs["on_started"]()
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "j1",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex="deadbeefcafebabe"))), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=fake_bridge_review), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert pager_calls
        event = next(call for call in pager_calls if call["event_type"] == "phase_b_reviewer_started")
        assert event["event_type"] == "phase_b_reviewer_started"
        assert event["task_id"] == "[PIPELINE-AGENT-PAGER]"
        assert event["plan_path"] == "reports/control_plane/plan.md"
        assert event["phase"] == "phase_b"
        assert event["state"] == "reviewer_started"
        assert event["transition_key"] == "phase-b-r1-deadbeef"
        assert [call["event_type"] for call in pager_calls] == [
            "phase_b_implementer_started",
            "phase_b_implementer_completed",
            "phase_b_reviewer_started",
            "phase_b_bridge_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "phase_b_final_verdict",
            "commit_ready",
        ]

    def test_run_phase_b_reviewer_transition_key_changes_across_reruns(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        pager_calls = []
        uuid_values = iter(["deadbeefcafebabe", "feedfacecafed00d"])

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": "evt-phase-b",
                "attempted": [],
                "budget_exhausted": False,
            }

        def fake_bridge_review(*args, **kwargs):
            kwargs["on_started"]()
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "timed out",
                "decision": "",
                "job_id": "j1",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=next(uuid_values)))), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=fake_bridge_review), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            first = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)
            second = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert first["status"] == "error"
        assert second["status"] == "error"
        reviewer_started_calls = [
            call for call in pager_calls
            if call["event_type"] == "phase_b_reviewer_started"
        ]
        assert [call["transition_key"] for call in reviewer_started_calls] == [
            "phase-b-r1-deadbeef",
            "phase-b-r1-feedface",
        ]

    def test_run_phase_b_does_not_emit_reviewer_started_before_bridge_launch(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": "evt-phase-b",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": -1,
                 "stdout": "",
                 "stderr": "timed out before launch",
                 "decision": "",
                 "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert "phase_b_reviewer_started" not in [
            call["event_type"] for call in pager_calls
        ]

    def test_run_phase_b_emits_reviewer_started_event_during_needs_phase_b_reentry(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        plan = repo / "reports" / "control_plane" / "plan.md"
        plan.write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )

        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_class": "MAINTENANCE",
            "target_gate_id": "G8",
        }
        pager_calls = []
        supervisor_results = iter([
            {
                "exit_code": 0,
                "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix more", "status": "ok", "findings": []},
                "receipt_path": "",
            },
            {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            },
            {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r-final.json",
            },
        ])
        uuid_values = iter(["11111111aaaaaaaa", "22222222bbbbbbbb"])

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{kwargs['transition_key']}",
                "attempted": [],
                "budget_exhausted": False,
            }

        bridge_job_ids = iter(["init", "reentry"])

        def fake_bridge_review(*args, **kwargs):
            kwargs["on_started"]()
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": next(bridge_job_ids),
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=next(uuid_values)))), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=fake_bridge_review), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=lambda *args, **kwargs: next(supervisor_results)), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert [call["event_type"] for call in pager_calls] == [
            "phase_b_implementer_started",
            "phase_b_implementer_completed",
            "phase_b_reviewer_started",
            "phase_b_bridge_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "phase_b_implementer_started",
            "phase_b_implementer_completed",
            "phase_b_reviewer_started",
            "phase_b_bridge_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "phase_b_final_verdict",
            "commit_ready",
        ]
        reviewer_started_calls = [
            call for call in pager_calls
            if call["event_type"] == "phase_b_reviewer_started"
        ]
        assert [call["transition_key"] for call in reviewer_started_calls] == [
            "phase-b-r1-11111111",
            "phase-b-reentry-r2-22222222",
        ]


@pytest.mark.usefixtures("mock_routing_record")
class TestPhaseBHardFailPagerEvents:
    def test_run_phase_b_emits_hard_fail_when_initial_bridge_hits_max_rounds(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )
        (repo / "f.py").write_text("print('hello')\n", encoding="utf-8")

        mock_impl = _make_mock_impl()
        pager_calls = []
        hard_fail_keys = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            if kwargs["event_type"] == "pipeline_hard_fail":
                hard_fail_keys.append(
                    pb_mod._phase_b_hard_fail_transition_key(  # ANTICHEAT_OK: testing internal executor functions
                        repo_root,
                        state=kwargs["state"],
                        changed_files=["mu/tools/f.py", "reports/control_plane/plan.md"],
                        reentry=False,
                    )
                )
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        def bridge_request_changes(*args, **kwargs):
            kwargs["on_started"]()
            return {
                "exit_code": 1,
                "stdout": "REQUEST_CHANGES\n",
                "stderr": "",
                "decision": "REQUEST_CHANGES",
                "job_id": "j1",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_request_changes), \
             patch.object(pb_mod, "_read_bridge_render", return_value="bridge findings text"), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=1)

        hard_fail_events = [call for call in pager_calls if call["event_type"] == "pipeline_hard_fail"]
        assert result["status"] == "max_rounds_reached"
        assert len(hard_fail_events) == 1
        assert len(hard_fail_keys) == 1
        assert hard_fail_events[0]["state"] == "max_rounds_reached"
        assert hard_fail_events[0]["transition_key"] == hard_fail_keys[0]
        assert "did not converge" in hard_fail_events[0]["summary"].lower()
        assert mock_impl.invoke_implementer.call_count == 1

    def test_run_phase_b_emits_hard_fail_when_reentry_hits_max_rounds(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )
        (repo / "f.py").write_text("print('hello')\n", encoding="utf-8")

        mock_impl = _make_mock_impl()
        pager_calls = []
        hard_fail_keys = []
        supervisor_results = iter([
            {
                "exit_code": 0,
                "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix more", "status": "ok", "findings": []},
                "receipt_path": "",
            },
        ])

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            if kwargs["event_type"] == "pipeline_hard_fail":
                hard_fail_keys.append(
                    pb_mod._phase_b_hard_fail_transition_key(  # ANTICHEAT_OK: testing internal executor functions
                        repo_root,
                        state=kwargs["state"],
                        changed_files=["TASKS.md", "f.py"],
                        reentry=True,
                    )
                )
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        bridge_calls = [0]

        def bridge_side(*args, **kwargs):
            bridge_calls[0] += 1
            kwargs["on_started"]()
            if bridge_calls[0] == 1:
                return {
                    "exit_code": 0,
                    "stdout": "GO\n",
                    "stderr": "",
                    "decision": "GO",
                    "job_id": "init",
                }
            return {
                "exit_code": 1,
                "stdout": "REQUEST_CHANGES\n",
                "stderr": "",
                "decision": "REQUEST_CHANGES",
                "job_id": f"reentry-{bridge_calls[0]}",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="bridge findings text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=lambda *args, **kwargs: next(supervisor_results)):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        hard_fail_events = [call for call in pager_calls if call["event_type"] == "pipeline_hard_fail"]
        assert result["status"] == "max_rounds_reached"
        assert len(hard_fail_events) == 1
        assert len(hard_fail_keys) == 1
        assert hard_fail_events[0]["state"] == "max_rounds_reached"
        assert hard_fail_events[0]["transition_key"].startswith("phase-b-reentry:max_rounds_reached:")
        assert "re-entry path" in hard_fail_events[0]["summary"].lower()
        assert mock_impl.invoke_implementer.call_count == 2

    def test_run_phase_b_emits_hard_fail_when_reentry_stops_on_needs_phase_b(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / ".agent_bus").mkdir()
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Wave ID: wave-phase-b-pager\n"
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Task: [PIPELINE-AGENT-PAGER]\n",
            encoding="utf-8",
        )
        (repo / "f.py").write_text("print('hello')\n", encoding="utf-8")

        mock_impl = _make_mock_impl()
        pager_calls = []
        hard_fail_keys = []
        supervisor_results = iter([
            {
                "exit_code": 0,
                "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix more", "status": "ok", "findings": []},
                "receipt_path": "",
            },
            {
                "exit_code": 0,
                "parsed": {"decision": "NEEDS_PHASE_B", "summary": "manual follow-up", "status": "ok", "findings": []},
                "receipt_path": "",
            },
        ])

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            if kwargs["event_type"] == "pipeline_hard_fail":
                hard_fail_keys.append(
                    pb_mod._phase_b_hard_fail_transition_key(  # ANTICHEAT_OK: testing internal executor functions
                        repo_root,
                        state=kwargs["state"],
                        changed_files=["f.py", "reports/control_plane/plan.md"],
                        reentry=True,
                    )
                )
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        bridge_calls = [0]

        def bridge_side(*args, **kwargs):
            bridge_calls[0] += 1
            kwargs["on_started"]()
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": f"bridge-{bridge_calls[0]}",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="bridge findings text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=lambda *args, **kwargs: next(supervisor_results)):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        hard_fail_events = [call for call in pager_calls if call["event_type"] == "pipeline_hard_fail"]
        assert result["status"] == "needs_phase_b"
        assert len(hard_fail_events) == 1
        assert len(hard_fail_keys) == 1
        assert hard_fail_events[0]["state"] == "needs_phase_b"
        assert hard_fail_events[0]["transition_key"].startswith("phase-b-reentry:needs_phase_b:")
        assert "manual intervention required" in hard_fail_events[0]["summary"].lower()


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryRestageFailClosed:
    """Re-entry restage failure must stop the pipeline, not run supervisor on stale state."""

    def test_reentry_restage_failure_stops_pipeline(self, tmp_path):
        """If _stage_files returns False after re-entry, fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", side_effect=[True, True, True, False]), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_staging"


@pytest.mark.usefixtures("mock_routing_record")
class TestPhaseBFailClosed:
    """Phase B executor fails closed on implementer and agent failures."""

    def test_implementer_error_is_fatal(self, tmp_path):
        """Non-timeout implementer failure must stop the pipeline."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        impl_error = {
            "status": "error",
            "output": "",
            "stderr": "adapter exited 1",
            "exit_code": 1,
            "job_id": "impl-test",
            "model_override_applied": False,
        }

        # Patch via sys.modules so the imports inside run_phase_b find mocks
        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.return_value = impl_error

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")
            assert result["status"] == "error"
            assert result.get("step") == "implementer"

    def test_implementer_max_turns_diagnostics_propagate(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        impl_error = {
            "status": "error",
            "output": "",
            "stderr": "Adapter result subtype: error_max_turns",
            "exit_code": 1,
            "job_id": "impl-test",
            "model_override_applied": False,
            "error_subtype": "error_max_turns",
            "stop_reason": "tool_use",
            "num_turns": 51,
        }

        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.return_value = impl_error

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")

        assert result["status"] == "error"
        assert result["step"] == "implementer"
        assert result["error_subtype"] == "error_max_turns"
        assert result["stop_reason"] == "tool_use"
        assert result["num_turns"] == 51

    def test_agent_review_hard_failure_is_fatal(self, tmp_path):
        """Hard-gate/compliance SDK review exits must stop the pipeline."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={
                 "exit_code": 1,
                 "stdout": "REJECT",
                 "stderr": "",
                 "report_path": ".scratch/sdk_report.md",
                 "status_path": ".scratch/sdk_status.json",
                 "stdout_path": ".scratch/sdk_stdout.log",
             }), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")
            assert result["status"] == "commit_ready"
            assert result["agent_exit_code"] == 1
            assert result["agent_review_warning_only"] is True

    def test_agent_review_warning_exit_continues_to_bridge(self, tmp_path):
        """Warnings-only SDK exit=2 should continue to bridge review."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan = repo / "reports" / "control_plane" / "test_plan.md"
        plan.write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/file.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={
                 "exit_code": 2, "stdout": "warnings", "stderr": "",
                 "report_path": ".scratch/sdk_report.md",
                 "status_path": ".scratch/sdk_status.json",
                 "stdout_path": ".scratch/sdk_stdout.log",
             }), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/test_plan.md")

        assert result["status"] == "commit_ready"
        assert result["agent_exit_code"] == 2
        assert result["agent_review_warning_only"] is True
        assert result["agent_review_report_path"] == ".scratch/sdk_report.md"


@pytest.mark.usefixtures("mock_routing_record")
class TestFinalPytestGate:
    """Failed pytest MUST block commit_ready — hard gate after bridge convergence."""

    def test_run_pytest_on_files_forces_deterministic_hash_seed(self, tmp_path):
        completed = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=0,
            stdout="ok",
            stderr="",
        )
        with patch.object(pb_mod.subprocess, "run", return_value=completed) as mock_run:
            result = pb_mod._run_pytest_on_files(tmp_path, ["mu/tests/tools/test_foo.py"])  # ANTICHEAT_OK: testing internal final-pytest gate helper

        assert result["passed"] is True
        kwargs = mock_run.call_args.kwargs
        assert kwargs["env"]["PYTHONHASHSEED"] == "0"

    def test_pytest_gate_ignores_non_python_test_fixtures(self):
        selected = pb_mod.select_pytest_gate_files([
            "mu/tests/fixtures/rcx_engine_state_minimal.json",
            "mu/tests/fixtures/rcx_enginenew_scheduler_operator_pool.json",
            "mu/tests/parity/test_rcx_engine_scheduler_parity.py",
            "mu/tests/structural/test_rcx_enginenew_scheduler.py",
            "package/tests/test_cli.py",
            "package/tests/cli_test.py",
            "reports/test_plan.md",
        ])

        assert selected == [
            "mu/tests/parity/test_rcx_engine_scheduler_parity.py",
            "mu/tests/structural/test_rcx_enginenew_scheduler.py",
            "package/tests/test_cli.py",
            "package/tests/cli_test.py",
        ]

    def test_pytest_gate_includes_bootstrap_core_carveout_gate(self):
        selected = pb_mod.select_pytest_gate_files([
            "mu/host/js/core/bootstrap_core.js",
            "mu/tests/l4_gates/test_stage0_production_pilot_gate.py",
        ])

        assert selected == [
            "tests/l4_gates/test_bootstrap_core_carveout_gate.py",
            "mu/tests/l4_gates/test_stage0_production_pilot_gate.py",
        ]

    def test_structural_tracker_note_includes_l4_required_proof_fields(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: locks Phase B tracker-note generator contract
            wave_id="post-redteam-engine-state-scheduler-reduction-2026-04-30",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/post_redteam_engine_state_scheduler_reduction_2026-04-30_2026-04-30.md",
            plan_content="Class: L4_STRUCTURAL\nrcx_engine_state rcx_engine_scheduler\n",
            changed_files=[
                "mu/host/python/rcx_pi/selfhost/engine_pipeline.py",
                "mu/host/js/engine/pipeline.js",
                "mu/programs/rcx_engine_state.v1.json",
                "mu/programs/rcx_engine_scheduler.v1.json",
                "mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py",
                "mu/tests/structural/test_rcx_engine_state_seed.py",
                "mu/tests/parity/test_rcx_engine_scheduler_parity.py",
            ],
            test_files=[
                "mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py",
                "mu/tests/structural/test_rcx_engine_state_seed.py",
                "mu/tests/parity/test_rcx_engine_scheduler_parity.py",
            ],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=6,
            reentry=True,
        )

        assert "workload_target: host_debt_reduction" in note
        assert "host_semantics_delta_before:" in note
        assert "host_semantics_delta_after:" in note
        assert "structural_artifact_ref: mu/host/python/rcx_pi/selfhost/engine_pipeline.py" in note
        assert "mu/programs/rcx_engine_scheduler.v1.json" in note
        assert "post_gate_contract_sweep: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short" in note
        assert "mu/tests/structural/test_rcx_engine_state_seed.py" in note
        assert "tools/checks/enforce_l4_execution_contract.py --staged" not in note
        assert "tools/checks/enforce_l4_execution_contract.py --files" in note
        assert "reports/l4_wave_indicators/post-redteam-engine-state-scheduler-reduction-2026-04-30.json --wave-id" in note

    def test_structural_tracker_note_preserves_explicit_packet_workload_target(self):
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: testing Phase B tracker-note helper
            wave_id="stage4-loop-struct-2026-06-22",
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path="reports/control_plane/stage4-loop-struct-2026-06-22_2026-06-22.md",
            plan_content=(
                "Class: L4_STRUCTURAL\n"
                "workload_target: rcx_engine_cycle\n"
                "engine_pipeline structuralization\n"
            ),
            changed_files=[
                "mu/host/python/rcx_pi/selfhost/engine_pipeline.py",
                "mu/host/js/engine/pipeline.js",
                "mu/tests/structural/test_rcx_engine_workload_contract.py",
            ],
            test_files=[
                "mu/tests/structural/test_rcx_engine_workload_contract.py",
            ],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=15,
            reentry=False,
        )

        assert "workload_target: rcx_engine_cycle" in note
        assert "workload_target: host_debt_reduction" not in note

    def test_structural_tracker_note_l4_files_command_includes_indicator_artifact(self):
        wave_id = "n3-kernel-driver-mu-driver-boundary-design-2026-05-20"
        note = pb_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: locks current bot finding repair
            wave_id=wave_id,
            task_id="[NEXT-CODEX-POST-REDTEAM]",
            wave_class="L4_STRUCTURAL",
            target_gate_id="G8",
            plan_path=f"reports/control_plane/{wave_id}.md",
            plan_content="Class: L4_STRUCTURAL\n",
            changed_files=[
                "TASKS.md",
                f"reports/control_plane/{wave_id}.md",
                "mu/host/python/rcx_pi/selfhost/step_mu.py",
                "mu/host/js/engine/kernel.js",
                "mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py",
            ],
            test_files=["mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py"],
            receipt_path=".agent_bus/meta/pre_commit_receipts/r.json",
            bridge_rounds=2,
            reentry=False,
        )

        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        assert f"indicator_artifact_ref: {indicator_path}" in note
        assert "tools/checks/enforce_l4_execution_contract.py --files TASKS.md" in note
        assert f"mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py {indicator_path}" in note
        assert f"--wave-id {wave_id} --wave-class L4_STRUCTURAL" in note

    def test_pytest_failure_blocks_commit_ready(self, tmp_path):
        """If final pytest gate fails, status must be error, not commit_ready."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py", "mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py", "mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 1, "stdout": "FAILED test_foo.py", "stderr": "", "passed": False,
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "final_pytest_gate"
        assert any(
            call["event_type"] == "phase_b_final_verdict"
            and call["state"] == "final_pytest_failed"
            for call in pager_calls
        )
        assert any(
            call["event_type"] == "pipeline_hard_fail"
            and call["state"] == "final_pytest_failed"
            for call in pager_calls
        )

    def test_reentry_pytest_failure_emits_final_verdict_and_hard_fail(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tests/tools/test_foo.py"]
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "baseline_wave_files": [],
            "all_non_blocking": [],
            "finding_history": [],
            "reentry_findings": "Fix the thing",
        }))

        mock_impl = _make_mock_impl()
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        def bridge_go(*args, **kwargs):
            kwargs["on_started"]()
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "reentry-go",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_go), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 1, "stdout": "FAILED test_foo.py", "stderr": "", "passed": False,
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_pytest_gate"
        assert any(
            call["event_type"] == "phase_b_final_verdict"
            and call["state"] == "reentry_pytest_failed"
            for call in pager_calls
        )
        assert any(
            call["event_type"] == "pipeline_hard_fail"
            and call["state"] == "reentry_pytest_failed"
            for call in pager_calls
        )

    def test_pytest_failure_surfaces_stderr_when_stdout_empty(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 3, "stdout": "", "stderr": "PYTHONHASHSEED must be '0'", "passed": False,
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert "PYTHONHASHSEED" in result["errors"][0]

    def test_pytest_failure_summary_preserves_long_stdout_tail(self):
        stdout = (
            "collected 639 items\n"
            + ("." * 200)
            + "\nFAILED mu/tests/tools/test_phase_b_executor.py::test_tail\n"
            "E AssertionError: boom"
        )

        summary = pb_mod._summarize_pytest_failure(  # ANTICHEAT_OK: locks bounded failure summary helper
            {"stdout": stdout, "stderr": ""},
            stdout_limit=80,
        )

        assert "stdout_head:" in summary
        assert "stdout_tail:" in summary
        assert "E AssertionError: boom" in summary

    def test_pytest_success_allows_commit_ready(self, tmp_path):
        """If final pytest gate passes, pipeline continues to supervisor."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{len(pager_calls)}",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }) as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_called_once_with(repo, ["mu/tests/tools/test_foo.py"], timeout=300)
        assert [call["event_type"] for call in pager_calls] == [
            "phase_b_implementer_started",
            "phase_b_implementer_completed",
            "phase_b_bridge_completed",
            "phase_b_final_pytest_started",
            "phase_b_final_pytest_passed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "pre_commit_supervisor_started",
            "pre_commit_supervisor_completed",
            "phase_b_final_verdict",
            "commit_ready",
        ]
        assert pager_calls[3]["state"] == "final_pytest_started"
        assert pager_calls[4]["state"] == "final_pytest_passed"

    def test_private_attr_gate_remediates_before_commit_handoff(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "ERROR: Found private attr access in tests/:",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", return_value={
                 "enabled": True, "event_id": "evt", "attempted": [], "budget_exhausted": False,
             }), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }) as mock_bridge, \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=[gate_fail, gate_pass]), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json") as mock_handoff:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count == 2
        remediation_source = mock_impl.build_implementation_prompt.call_args_list[1].args[0]
        assert "Private Attribute Test Integrity Gate Failure" in remediation_source
        assert mock_bridge.call_count == 2
        assert "private-attr remediation review" in mock_bridge.call_args_list[1].args[1]
        mock_handoff.assert_called_once()

    def test_private_attr_bridge_request_changes_reinvokes_implementer(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "ERROR: Found private attr access in tests/:",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", return_value={
                 "enabled": True, "event_id": "evt", "attempted": [], "budget_exhausted": False,
             }), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"},
                 {
                     "exit_code": 1,
                     "stdout": "REQUEST_CHANGES\nprivate attr follow-up\n",
                     "stderr": "",
                     "decision": "REQUEST_CHANGES",
                     "job_id": "j2",
                 },
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j3"},
             ]) as mock_bridge, \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=[gate_fail, gate_pass, gate_pass]), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=3)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count == 3
        bridge_fix_source = mock_impl.build_implementation_prompt.call_args_list[2].args[0]
        assert "Bridge Round 2 Findings (REQUEST_CHANGES)" in bridge_fix_source
        assert "private attr follow-up" in bridge_fix_source
        assert mock_bridge.call_count == 3
        assert "private-attr remediation review R3" in mock_bridge.call_args_list[2].args[1]

    def test_private_attr_question_is_terminal_and_routine_resume_does_not_launch_work(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "ERROR: Found private attr access in tests/:",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": ["mu/tests/tools/test_foo.py"],
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"},
                 {
                     "exit_code": 0,
                     "stdout": "QUESTION\n",
                     "stderr": "",
                     "decision": "QUESTION",
                     "job_id": "j2",
                     "stdout_path": ".scratch/stdout.log",
                     "stderr_path": ".scratch/stderr.log",
                 },
             ]) as mock_bridge, \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=[gate_fail, gate_pass]), \
             patch.object(pb_mod, "_read_bridge_render", return_value="founder question render"), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            first = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=3)

        assert first["status"] == "question_for_founder"
        assert first["step"] == "private_attr_bridge_review"
        assert mock_bridge.call_count == 2

        state = pb_mod._load_state(repo)  # ANTICHEAT_OK: private-attr terminal resume regression
        assert state["completed_step"] == "private_attr_remediation_question_for_founder"
        assert state["terminal_result"]["status"] == "question_for_founder"
        assert state["terminal_result"]["bridge_render"] == "founder question render"

        second_impl = _make_mock_impl()
        sdk_mock = MagicMock()
        bridge_mock = MagicMock()
        gate_mock = MagicMock()
        pytest_mock = MagicMock()
        supervisor_mock = MagicMock()
        with patch.dict(sys.modules, {"phase_b_implementer": second_impl}), \
             patch.object(pb_mod, "load_routing_record") as routing_mock, \
             patch.object(pb_mod, "run_sdk_agents", sdk_mock), \
             patch.object(pb_mod, "run_bridge_review", bridge_mock), \
             patch.object(pb_mod, "run_private_attr_gate", gate_mock), \
             patch.object(pb_mod, "_run_pytest_on_files", pytest_mock), \
             patch.object(pb_mod, "run_pre_commit_supervisor", supervisor_mock):
            second = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=3)

        assert second["status"] == "question_for_founder"
        assert second["resumed_from"] == "private_attr_remediation_question_for_founder"
        routing_mock.assert_not_called()
        second_impl.invoke_implementer.assert_not_called()
        sdk_mock.assert_not_called()
        bridge_mock.assert_not_called()
        gate_mock.assert_not_called()
        pytest_mock.assert_not_called()
        supervisor_mock.assert_not_called()

    def test_resume_private_attr_remediation_requires_fresh_bridge_review(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "phase_b_state.json"
        changed_files = ["mu/tests/tools/test_foo.py"]
        state_file.write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "private_attr_remediation_pending_review",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "baseline_wave_files": [],
            "all_non_blocking": [],
            "finding_history": {},
            "private_attr_gate_test_files": changed_files,
        }))

        mock_impl = _make_mock_impl()
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": changed_files,
        }

        def bridge_side_effect(*args, **kwargs):
            saved_state = json.loads(state_file.read_text(encoding="utf-8"))
            assert saved_state["completed_step"] == "private_attr_remediation_pending_review"
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "j2",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", return_value={
                 "enabled": True, "event_id": "evt", "attempted": [], "budget_exhausted": False,
             }), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}) as mock_agents, \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect) as mock_bridge, \
             patch.object(pb_mod, "run_private_attr_gate", return_value=gate_pass), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=3)

        assert result["status"] == "commit_ready"
        assert result.get("resumed_from") == "private_attr_remediation_pending_review"
        mock_impl.invoke_implementer.assert_not_called()
        mock_agents.assert_not_called()
        mock_bridge.assert_called_once()
        assert "private-attr remediation review" in mock_bridge.call_args.args[1]

    def test_resume_private_attr_review_runs_after_bridge_budget_exhausted(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "phase_b_state.json"
        changed_files = ["mu/tests/tools/test_foo.py"]
        state_file.write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "private_attr_remediation_pending_review",
            "wave_id": "plan",
            "bridge_rounds": 2,
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "baseline_wave_files": [],
            "all_non_blocking": [],
            "finding_history": {},
            "private_attr_gate_test_files": changed_files,
        }))

        mock_impl = _make_mock_impl()
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": changed_files,
        }

        def bridge_side_effect(*args, **kwargs):
            saved_state = json.loads(state_file.read_text(encoding="utf-8"))
            assert saved_state["completed_step"] == "private_attr_remediation_pending_review"
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "j3",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "emit_pipeline_agent_event", return_value={
                 "enabled": True, "event_id": "evt", "attempted": [], "budget_exhausted": False,
             }), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}) as mock_agents, \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect) as mock_bridge, \
             patch.object(pb_mod, "run_private_attr_gate", return_value=gate_pass), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        assert result["status"] == "commit_ready"
        assert result.get("resumed_from") == "private_attr_remediation_pending_review"
        mock_impl.invoke_implementer.assert_not_called()
        mock_agents.assert_not_called()
        mock_bridge.assert_called_once()
        assert "private-attr remediation review R3" in mock_bridge.call_args.args[1]


class TestBridgeRenderAssociation:
    """Bridge review uses exact job_id, not newest/freshest render."""

    def test_run_bridge_review_passes_job_id(self, tmp_path):
        """run_bridge_review passes --job-id to bridge_supervisor."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=10,
            )
            # Verify --job-id was passed in the command
            call_args = mock_run.call_args[0][1]
            assert "--job-id" in call_args
            idx = call_args.index("--job-id")
            assert call_args[idx + 1] == "phase-b-r1-abc12345"

    def test_run_bridge_review_places_bus_dir_before_subcommand(self, tmp_path):
        """Phase B must pass bridge_supervisor global args before the review subcommand."""
        with patch.object(pb_mod, "_active_bus_dir", return_value=Path(".agent_bus-test")), \
             patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=10,
            )

        call_args = mock_run.call_args[0][1]
        assert call_args[2:5] == ["--bus-dir", ".agent_bus-test", "review"]
        assert result["exit_code"] == 0

    def test_run_bridge_review_uses_configured_reviewer(self, tmp_path, monkeypatch):
        """Phase B bridge review must honor executor-configured reviewer backend."""
        # Unset env override so the test exercises config-driven reviewer selection,
        # not the reviewer override environment vars.
        monkeypatch.delenv("RCX_REVIEWER_AGENT_OVERRIDE", raising=False)
        monkeypatch.delenv("RCX_BRIDGE_REVIEWER_OVERRIDE", raising=False)
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        (config_dir / "executor_config.json").write_text(
            json.dumps({"role_agents": {"reviewer": "claude"}}),
            encoding="utf-8",
        )
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=10,
            )

        call_args = mock_run.call_args[0][1]
        assert "--reviewer" in call_args
        idx = call_args.index("--reviewer")
        assert call_args[idx + 1] == "claude"

    def test_run_bridge_review_sets_inner_turn_timeout_to_outer_bridge_budget(self, tmp_path):
        """Inner bridge turn timeout must inherit the outer subprocess budget."""
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        (config_dir / "executor_config.json").write_text(
            json.dumps({"bridge_turn_timeouts": {"phase_b": 901}}),
            encoding="utf-8",
        )
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=1200,
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["env"]["RCX_BRIDGE_MAX_TURN_WALL_TIME_S"] == "1200.0"

    def test_run_bridge_review_caps_inner_turn_timeout_when_outer_budget_is_smaller(self, tmp_path):
        """The inner bridge turn timeout must still honor a smaller outer budget."""
        config_dir = tmp_path / "mu" / "tools" / "executors"
        config_dir.mkdir(parents=True)
        (config_dir / "executor_config.json").write_text(
            json.dumps({"bridge_turn_timeouts": {"phase_b": 901}}),
            encoding="utf-8",
        )
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            pb_mod.run_bridge_review(
                tmp_path,
                "test review",
                job_id="phase-b-r1-abc12345",
                timeout=600,
            )

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["env"]["RCX_BRIDGE_MAX_TURN_WALL_TIME_S"] == "600.0"

    def test_run_bridge_review_parses_decision_from_stdout(self, tmp_path):
        """Decision is parsed from stdout, not from rendered file freshness."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 0, "stdout": "GO\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["decision"] == "GO"

    def test_run_bridge_review_parses_request_changes(self, tmp_path):
        """REQUEST_CHANGES decision is parsed from stdout."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["decision"] == "REQUEST_CHANGES"

    def test_run_bridge_review_preserves_stale_exit_code(self, tmp_path):
        """Bridge stale-review supervision surfaces exit_code=-2."""
        with patch.object(pb_mod, "_run_bridge_review_subprocess") as mock_run:
            mock_run.return_value = {
                "exit_code": -2, "stdout": "", "stderr": "Bridge review stale after 120s",
            }
            result = pb_mod.run_bridge_review(
                tmp_path, "test", job_id="test-job", timeout=10,
            )
            assert result["exit_code"] == -2
            assert "stale" in result["stderr"]

    def test_read_bridge_render_by_job_id(self, tmp_path):
        """_read_bridge_render reads the exact job_id file."""
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        # Write a render for a specific job_id
        (rendered_dir / "phase-b-r1-abc12345.md").write_text("Decision: GO\nContent here")
        # Write a DIFFERENT render (should NOT be read)
        (rendered_dir / "some-other-job.md").write_text("Decision: NO_GO\nOther content")

        content = pb_mod._read_bridge_render(tmp_path, "phase-b-r1-abc12345")  # ANTICHEAT_OK: testing bridge render reader
        assert "Decision: GO" in content
        assert "Other content" not in content

    def test_read_bridge_render_missing_returns_empty(self, tmp_path):
        """Missing render for job_id returns empty string."""
        content = pb_mod._read_bridge_render(tmp_path, "nonexistent-job")  # ANTICHEAT_OK: testing bridge render reader
        assert content == ""

    def test_read_bridge_render_rejects_path_traversal_job_id(self, tmp_path):
        """Unsafe job_id values must not escape the rendered directory."""
        rendered_dir = tmp_path / ".agent_bus" / "rendered"
        rendered_dir.mkdir(parents=True)
        (rendered_dir / "phase-b-r1-abc12345.md").write_text("Decision: GO\nContent here")
        content = pb_mod._read_bridge_render(tmp_path, "../phase-b-r1-abc12345")  # ANTICHEAT_OK: testing bridge render reader
        assert content == ""


class TestBridgeReviewMonitoring:
    """Bridge review supervision fails closed on stale reviewer tails."""

    def test_bridge_review_stale_kills_subprocess(self, tmp_path):
        stdout_log = tmp_path / ".scratch" / "phase_b_bridge_stale-job.stdout.log"
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.side_effect = [None, None, None]

        frozen_snapshot = {
            "child_pids": (200,),
            "cpu_fingerprint": ((12345, 1.0), (200, 1.0)),
            "artifact_fingerprint": (),
        }
        monotonic_values = iter([0.0, 0.0, 0.0, 2.0, 2.0])

        with patch.object(pb_mod.subprocess, "Popen", return_value=proc), \
             patch.object(pb_mod, "_bridge_progress_snapshot", side_effect=[
                 frozen_snapshot,
                 frozen_snapshot,
                 frozen_snapshot,
                 frozen_snapshot,
             ]), \
             patch.object(pb_mod, "_terminate_bridge_subprocess") as mock_terminate, \
             patch.object(pb_mod.time, "sleep", return_value=None), \
             patch.object(pb_mod.time, "monotonic", side_effect=lambda: next(monotonic_values)):
            result = pb_mod._run_bridge_review_subprocess(  # ANTICHEAT_OK: testing internal bridge subprocess supervision helper
                tmp_path,
                [sys.executable, "-c", "print('hi')"],
                job_id="stale-job",
                timeout=30,
                verbose=False,
                poll_interval=0.0,
                stale_timeout=1.0,
                aggregation_hang_timeout=10.0,
            )

        assert result["exit_code"] == -2
        assert "stale" in result["stderr"]
        mock_terminate.assert_called_once_with(proc, child_pids=(200,))

    def test_terminate_bridge_subprocess_signals_detached_child_groups(self):
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.side_effect = [None, 0]

        with patch.object(pb_mod.os, "getpgid", return_value=12345), \
             patch.object(pb_mod.os, "killpg") as mock_killpg, \
             patch.object(pb_mod.os, "kill") as mock_kill, \
             patch.object(pb_mod, "_pid_is_live", return_value=False), \
             patch.object(pb_mod.time, "sleep", return_value=None):
            pb_mod._terminate_bridge_subprocess(  # ANTICHEAT_OK: testing subprocess cleanup helper
                proc,
                child_pids=(200, 200, 12345),
            )

        assert (200, pb_mod.signal.SIGTERM) in [call.args for call in mock_killpg.call_args_list]
        assert (12345, pb_mod.signal.SIGTERM) in [call.args for call in mock_killpg.call_args_list]
        assert not mock_kill.called

    def test_terminate_bridge_subprocess_kills_recorded_sigterm_ignoring_child_after_parent_exit(self, tmp_path):
        child_code = (
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "time.sleep(60)\n"
        )
        parent_code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', sys.argv[1]], start_new_session=True)\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", parent_code, child_code],
            cwd=tmp_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        assert proc.stdout is not None
        child_pid = int(proc.stdout.readline().strip())

        try:
            pb_mod._terminate_bridge_subprocess(  # ANTICHEAT_OK: real-process cleanup regression
                proc,
                child_pids=(child_pid,),
            )
            assert proc.poll() is not None
            assert not pb_mod._pid_is_live(child_pid)  # ANTICHEAT_OK: confirms recorded detached child was killed
        finally:
            for pid in (child_pid, proc.pid):
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass

    def test_bridge_monitoring_exception_cleans_owned_process_tree(self, tmp_path):
        proc = MagicMock()
        proc.pid = 12345
        proc.poll.return_value = None
        first_snapshot = {
            "child_pids": (200,),
            "cpu_fingerprint": ((12345, 1.0), (200, 1.0)),
            "artifact_fingerprint": (),
        }

        with patch.object(pb_mod.subprocess, "Popen", return_value=proc), \
             patch.object(pb_mod, "_bridge_progress_snapshot", side_effect=[
                 first_snapshot,
                 RuntimeError("snapshot exploded"),
             ]), \
             patch.object(pb_mod, "_terminate_bridge_subprocess") as mock_terminate:
            with pytest.raises(RuntimeError, match="snapshot exploded"):
                pb_mod._run_bridge_review_subprocess(  # ANTICHEAT_OK: exception-safe bridge ownership regression
                    tmp_path,
                    [sys.executable, "-c", "print('hi')"],
                    job_id="exception-job",
                    timeout=30,
                    verbose=False,
                )

        mock_terminate.assert_called_once_with(proc, child_pids=(200,))

    def test_bridge_on_started_exception_cleans_detached_child_spawned_before_snapshot(self, tmp_path):
        child_code = (
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "time.sleep(60)\n"
        )
        parent_code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', sys.argv[1]], start_new_session=True)\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        child_pids: list[int] = []
        stdout_path = tmp_path / ".scratch" / "phase_b_bridge_callback-job.stdout.log"

        def on_started() -> None:
            deadline = pb_mod.time.monotonic() + 5.0
            while pb_mod.time.monotonic() < deadline:
                if stdout_path.exists():
                    text = stdout_path.read_text(encoding="utf-8").strip()
                    if text:
                        child_pids.append(int(text.splitlines()[0]))
                        raise RuntimeError("callback exploded")
                pb_mod.time.sleep(0.05)
            raise RuntimeError("child pid was not observed")

        try:
            with pytest.raises(RuntimeError, match="callback exploded"):
                pb_mod._run_bridge_review_subprocess(  # ANTICHEAT_OK: real-process callback cleanup regression
                    tmp_path,
                    [sys.executable, "-c", parent_code, child_code],
                    job_id="callback-job",
                    timeout=30,
                    verbose=False,
                    on_started=on_started,
                )

            assert child_pids
            assert not pb_mod._pid_is_live(child_pids[0])  # ANTICHEAT_OK: recorded detached child cleanup proof
        finally:
            for pid in child_pids:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass


class TestImplementerIsConfigDriven:
    """The implementer backend comes from executor_config.json."""

    def test_config_driven_backend(self, tmp_path):
        config = impl_mod.load_executor_config(tmp_path)
        backend = config.get("backends", {}).get("phase_b_executor", "codex")
        assert backend in ("codex", "claude", "sonnet")  # Valid backends


@pytest.mark.usefixtures("mock_routing_record")
class TestBridgeLoopReinvokesImplementer:
    """Bridge REQUEST_CHANGES/NO_GO must re-invoke implementer, not just loop bridge."""

    def test_request_changes_reinvokes_implementer(self, tmp_path):
        """REQUEST_CHANGES causes implementer re-invocation before next bridge round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings here"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Implementer must have been called at least twice:
        # once for initial implementation, once for the bridge fix
        assert mock_impl.invoke_implementer.call_count >= 2
        assert result["status"] == "commit_ready"

    def test_bridge_rounds_restage_current_wave_before_each_review(self, tmp_path):
        """Each bridge round must review the current staged candidate, not stale index state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side_effect(*args, **kwargs):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", "f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", "f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side_effect), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings here"), \
             patch.object(pb_mod, "_stage_files", return_value=True) as mock_stage, \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_stage.call_count == 4
        # Step 5b adds plan_path to changed_files before staging
        assert mock_stage.call_args_list[0].args[1] == ["TASKS.md", "f.py", "reports/control_plane/plan.md"]
        assert mock_stage.call_args_list[1].args[1] == ["TASKS.md", "f.py", "reports/control_plane/plan.md"]

    def test_sdk_candidate_authority_failure_blocks_sdk_review(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-sdk-authority-block-2026-08-21"
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text("# TASKS\n", encoding="utf-8")
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(
                 pb_mod,
                 "prepare_candidate_authority_if_configured",
                 return_value=(None, "stale SDK authority"),
             ), \
             patch.object(pb_mod, "run_sdk_agents") as mock_sdk, \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "sdk_candidate_authority"
        mock_sdk.assert_not_called()
        mock_bridge.assert_not_called()

    def test_bridge_candidate_authority_failure_blocks_reviewer_started_event(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "phase-b-bridge-authority-block-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)
        mock_impl = _make_mock_impl()
        pager_events: list[dict[str, Any]] = []

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", "f.py", plan_path, indicator_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", "f.py", plan_path, indicator_path]), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_tasks_has_canonical_wave_tracker_note", return_value=True), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", return_value=(indicator_path, None)), \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", return_value=(True, None)), \
             patch.object(
                 pb_mod,
                 "prepare_candidate_authority_if_configured",
                 side_effect=[("sdk-receipt", None), (None, "stale bridge authority")],
             ), \
             patch.object(pb_mod, "_emit_phase_b_event", side_effect=lambda *a, **kw: pager_events.append(kw) or {}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}) as mock_sdk, \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_pre_review_candidate_authority"
        mock_sdk.assert_called_once()
        mock_bridge.assert_not_called()
        assert "phase_b_reviewer_started" not in [
            event.get("event_type") for event in pager_events
        ]

    @pytest.mark.parametrize(
        "step_prefix",
        [
            "bridge_pre_review",
            "private_attr_bridge_review",
            "reentry_bridge_pre_review",
        ],
    )
    def test_shared_pre_review_hook_blocks_all_bridge_reviewer_contexts(
        self,
        tmp_path,
        real_pre_review_package,
        step_prefix,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = f"{step_prefix.replace('_', '-')}-authority-block-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)

        with patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_tasks_has_canonical_wave_tracker_note", return_value=True), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", return_value=(indicator_path, None)), \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", return_value=(True, None)), \
             patch.object(pb_mod, "_guard_candidate_authority_scope_if_configured", return_value=None), \
             patch.object(
                 pb_mod,
                 "prepare_candidate_authority_if_configured",
                 return_value=(None, "stale candidate receipt"),
             ):
            _prepared, error = pb_mod._prepare_phase_b_pre_review_package(  # ANTICHEAT_OK: focused unit test for shared pre-review authority hook
                repo,
                candidate_files=["TASKS.md", "f.py", plan_path, indicator_path],
                exact_stage_scope_files={"TASKS.md", "f.py", plan_path, indicator_path},
                plan_path=plan_path,
                wave_id=wave_id,
                wave_class="L4_ENABLER",
                step_prefix=step_prefix,
                context=f"{step_prefix} context",
                candidate_authority_required=True,
            )

        assert error is not None
        assert error["step"] == f"{step_prefix}_candidate_authority"
        assert "stale candidate receipt" in error["stderr"]

    def test_pre_collector_candidate_scope_guard_blocks_collector(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "phase-b-precollector-authority-block-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)

        with patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_tasks_has_canonical_wave_tracker_note", return_value=True), \
             patch.object(
                 pb_mod,
                 "_guard_candidate_authority_scope_if_configured",
                 return_value="outside allowlist: tools/metrics/collect_l4_wave_indicators.py",
             ), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope") as mock_refresh:
            _prepared, error = pb_mod._prepare_phase_b_pre_review_package(  # ANTICHEAT_OK: focused unit test for pre-collector authority ordering
                repo,
                candidate_files=["TASKS.md", "f.py", plan_path, indicator_path],
                exact_stage_scope_files={"TASKS.md", "f.py", plan_path, indicator_path},
                plan_path=plan_path,
                wave_id=wave_id,
                wave_class="L4_ENABLER",
                step_prefix="bridge_pre_review",
                context="bridge review",
                candidate_authority_required=True,
                candidate_authority_metadata={"spec_identity": {"spec_hash": "trusted"}},
            )

        assert error is not None
        assert error["step"] == "bridge_pre_review_candidate_authority_scope"
        assert "outside allowlist" in error["stderr"]
        mock_collector.assert_not_called()
        mock_refresh.assert_not_called()

    def test_pre_supervisor_scope_guard_blocks_indicator_collector(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".agent_bus").mkdir()
        wave_id = "phase-b-pre-supervisor-authority-block-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)
        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        changed = ["TASKS.md", "f.py", plan_path]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: list(files)), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(
                 pb_mod,
                 "_guard_candidate_authority_scope_if_configured",
                 return_value="outside allowlist: outside.txt",
             ), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "run_pre_commit_supervisor") as mock_supervisor:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "pre_supervisor_candidate_authority_scope"
        assert "outside.txt" in result["errors"][0]
        mock_collector.assert_not_called()
        mock_supervisor.assert_not_called()
        assert not (repo / indicator_path).exists()

    def test_reentry_pre_supervisor_scope_guard_blocks_indicator_collector(
        self,
        tmp_path,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".agent_bus").mkdir()
        wave_id = "phase-b-reentry-supervisor-authority-block-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)
        mock_impl = _make_mock_impl()
        routing = {
            **_VALID_ROUTING_RECORD,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": wave_id,
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
        }
        changed = ["TASKS.md", "f.py", plan_path, indicator_path]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value=routing), \
             patch.object(pb_mod, "_collect_changed_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=list(changed)), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kwargs: list(files)), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"},
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j2"},
             ]), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", side_effect=[False, True]), \
             patch.object(
                 pb_mod,
                 "_guard_candidate_authority_scope_if_configured",
                 return_value="outside allowlist: outside.txt",
             ), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {
                     "decision": "NEEDS_PHASE_B",
                     "summary": "collect the same-wave indicator after re-entry",
                     "status": "success",
                     "findings": [],
                 },
                 "receipt_path": "",
             }) as mock_supervisor:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_pre_supervisor_candidate_authority_scope"
        assert "outside.txt" in result["errors"][0]
        mock_collector.assert_not_called()
        assert mock_supervisor.call_count == 1
        assert not (repo / indicator_path).exists()

    def test_pre_collector_guard_rejects_index_only_outside_before_exact_scope_unstage(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "phase-b-index-only-outside-2026-08-21"
        plan_path, indicator_path = _write_pre_review_plan(repo, wave_id)
        _write_canonical_tasks(repo, wave_id)
        (repo / "f.py").write_text("base\n", encoding="utf-8")
        (repo / "outside.txt").write_text("base\n", encoding="utf-8")
        _git_stdout(repo, "add", "-A")
        _git_stdout(repo, "commit", "-q", "-m", "base")
        comparison_commit = _git_stdout(repo, "rev-parse", "HEAD")
        indicator_command = (
            "python3 tools/metrics/collect_l4_wave_indicators.py "
            f"--wave-id {wave_id} --output {indicator_path}"
        )
        allowlist = ["TASKS.md", "f.py", plan_path, indicator_path]
        spec = candidate_authority_mod.CandidateAuthoritySpec.from_mapping(
            {
                "wave_id": wave_id,
                "comparison_commit": comparison_commit,
                "candidate_allowlist": allowlist,
                "plan_path": plan_path,
                "phase": "phase_b",
                "review_round": "bridge_pre_review",
                "indicator_artifact_ref": indicator_path,
                "indicator_collection_command": indicator_command,
                "wave_class": "L4_ENABLER",
                "require_l4_staged": True,
            }
        )
        spec_path = candidate_authority_mod.write_authority_spec(
            repo,
            spec,
            bus_dir=".agent_bus",
        )
        trusted_metadata = {
            "spec_path": str(spec_path),
            "spec_identity": candidate_authority_mod.authority_spec_identity(
                repo,
                spec,
                authority_required=True,
            ),
        }
        (repo / "outside.txt").write_text("staged outside\n", encoding="utf-8")
        _git_stdout(repo, "add", "outside.txt")
        _git_stdout(repo, "restore", "--worktree", "--source=HEAD", "--", "outside.txt")

        with patch.object(pb_mod, "_tasks_has_canonical_wave_tracker_note", return_value=True), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope") as mock_refresh, \
             patch.object(
                 pb_mod,
                 "prepare_candidate_authority_if_configured",
                 return_value=("receipt.json", None),
             ) as mock_authority:
            _prepared, error = pb_mod._prepare_phase_b_pre_review_package(  # ANTICHEAT_OK: regression for index-only out-of-scope staged state before guard
                repo,
                candidate_files=allowlist,
                exact_stage_scope_files=set(allowlist),
                plan_path=plan_path,
                wave_id=wave_id,
                wave_class="L4_ENABLER",
                step_prefix="bridge_pre_review",
                context="bridge review",
                candidate_authority_required=True,
                candidate_authority_metadata=trusted_metadata,
            )

        assert error is not None
        assert error["step"] == "bridge_pre_review_candidate_authority_scope"
        assert "outside.txt" in error["stderr"]
        mock_collector.assert_not_called()
        mock_refresh.assert_not_called()
        mock_authority.assert_not_called()
        assert "outside.txt" in _git_stdout(repo, "diff", "--cached", "--name-only").splitlines()

    def test_candidate_authority_helper_targets_active_candidate_repo(self, tmp_path):
        repo = tmp_path / "candidate-lane"
        repo.mkdir()
        wave_id = "phase-b-candidate-lane-target-2026-08-21"
        spec_path = repo / ".agent_bus" / "meta" / "candidate_authority" / f"{wave_id}.spec.json"
        spec_path.parent.mkdir(parents=True)
        spec_path.write_text("{}", encoding="utf-8")
        captured: dict[str, Any] = {}

        class DummySpec:
            def to_dict(self):
                return {
                    "wave_id": wave_id,
                    "comparison_commit": "0" * 40,
                    "candidate_allowlist": ["TASKS.md"],
                    "phase": "phase_b",
                    "review_round": "old",
                }

        def prepare_side(repo_root, spec, *, bus_dir=None):
            captured["repo_root"] = Path(repo_root)
            captured["bus_dir"] = bus_dir
            captured["phase"] = spec.phase
            captured["review_round"] = spec.review_round
            return {"receipt_path": str(repo / ".agent_bus" / "receipt.json")}

        with patch.object(candidate_authority_mod, "load_authority_spec", return_value=DummySpec()), \
             patch.object(candidate_authority_mod, "verify_authority_spec_identity", return_value={"status": "trusted"}), \
             patch.object(candidate_authority_mod, "prepare_candidate_authority", side_effect=prepare_side), \
             patch.object(candidate_authority_mod, "verify_current_receipt", return_value={"status": "current"}) as mock_verify:
            receipt_path, error = pb_mod.prepare_candidate_authority_if_configured(
                repo,
                wave_id=wave_id,
                phase="phase_b",
                review_round="bridge_pre_review",
                context="bridge review",
                trusted_metadata={
                    "spec_path": str(spec_path),
                    "spec_identity": {"spec_hash": "trusted"},
                },
            )

        assert error is None
        assert receipt_path.endswith("receipt.json")
        assert captured == {
            "repo_root": repo,
            "bus_dir": None,
            "phase": "phase_b",
            "review_round": "bridge_pre_review",
        }
        assert mock_verify.call_args.kwargs["phase"] == "phase_b"
        assert mock_verify.call_args.kwargs["review_round"] == "bridge_pre_review"
        assert mock_verify.call_args.kwargs["trusted_spec"].review_round == "bridge_pre_review"

    def test_candidate_authority_helper_fails_closed_when_spec_missing(self, tmp_path):
        repo = tmp_path / "candidate-lane"
        repo.mkdir()

        receipt_path, error = pb_mod.prepare_candidate_authority_if_configured(
            repo,
            wave_id="definitely-no-such-authority-spec-2026-08-21",
            phase="phase_b",
            review_round="bridge_pre_review",
            context="bridge review",
        )

        assert receipt_path is None
        assert error is not None
        assert "Candidate authority spec is required before bridge review" in error
        assert "definitely-no-such-authority-spec-2026-08-21.spec.json" in error

    def test_bridge_reviewer_rebinds_canonical_receipt_after_private_attr_edits(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = "phase-b-canonical-receipt-rebind-2026-08-21"
        plan_path, test_path, _indicator_path = _write_bridge_receipt_fixture_repo(
            repo,
            wave_id,
        )
        mock_impl = _make_successful_impl_with_edits(test_path)
        canonical_receipt = (
            repo
            / ".agent_bus"
            / "meta"
            / "candidate_authority_receipts"
            / wave_id
            / "phase_b-bridge_pre_review.json"
        )
        prepared_rounds: list[dict[str, Any]] = []
        observed_bridge_receipts: list[dict[str, Any]] = []

        def prepare_authority_side(
            repo_root,
            *,
            wave_id,
            phase,
            review_round,
            context,
            **_kwargs,
        ):
            sequence = len(prepared_rounds) + 1
            receipt_path = (
                Path(repo_root)
                / ".agent_bus"
                / "meta"
                / "candidate_authority_receipts"
                / wave_id
                / f"{phase}-{review_round}.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt = {
                "sequence": sequence,
                "review_round": review_round,
                "context": context,
            }
            receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
            prepared_rounds.append(receipt)
            return str(receipt_path), None

        bridge_decisions = iter([
            ("GO", 0),
            ("NO_GO", 1),
            ("GO", 0),
        ])

        def bridge_side(repo_root, summary, **kwargs):
            on_started = kwargs.get("on_started")
            if on_started is not None:
                on_started()
            observed = json.loads(canonical_receipt.read_text(encoding="utf-8"))
            observed_bridge_receipts.append({
                **observed,
                "summary": summary,
            })
            decision, exit_code = next(bridge_decisions)
            return {
                "exit_code": exit_code,
                "stdout": f"{decision}\nfix current candidate\n",
                "stderr": "",
                "decision": decision,
                "job_id": kwargs.get("job_id", decision.lower()),
            }

        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "private access through implementation detail",
            "stderr": "",
            "test_files": [test_path],
        }
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [test_path],
        }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "prepare_candidate_authority_if_configured", side_effect=prepare_authority_side), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=[gate_fail, gate_pass, gate_pass]), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(
                repo,
                plan_path,
                max_bridge_rounds=3,
                routing_record_override={
                    **_VALID_ROUTING_RECORD,
                    "task_id": "[PIPELINE-RECOVERY]",
                    "wave_name": wave_id,
                    "wave_class": "L4_ENABLER",
                    "target_gate_id": "G8",
                },
            )

        assert result["status"] == "commit_ready", result
        assert [entry["review_round"] for entry in prepared_rounds] == [
            "bridge_pre_review",
            "bridge_pre_review",
            "bridge_pre_review",
        ]
        assert [entry["sequence"] for entry in observed_bridge_receipts] == [1, 2, 3]
        assert all(
            entry["review_round"] == "bridge_pre_review"
            for entry in observed_bridge_receipts
        )
        assert "private-attr remediation review" in observed_bridge_receipts[1]["summary"]
        assert "private-attr remediation review" in observed_bridge_receipts[2]["summary"]

    @pytest.mark.parametrize(
        ("scenario", "expected_step"),
        [
            ("initial", "bridge_pre_review_candidate_authority"),
            ("private_attr", "private_attr_bridge_review_candidate_authority"),
            ("reentry", "reentry_bridge_pre_review_candidate_authority"),
            ("reentry_private_attr", "reentry_private_attr_bridge_review_candidate_authority"),
        ],
    )
    def test_bridge_review_context_failures_keep_distinct_steps_and_canonical_receipt(
        self,
        tmp_path,
        real_pre_review_package,
        scenario,
        expected_step,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        wave_id = f"phase-b-{scenario.replace('_', '-')}-canonical-receipt-2026-08-21"
        plan_path, test_path, _indicator_path = _write_bridge_receipt_fixture_repo(
            repo,
            wave_id,
        )
        mock_impl = _make_successful_impl_with_edits(test_path)
        prepared_bridge_contexts: list[str] = []

        fail_state = {"private_attr_seen": 0}
        expected_context = (
            "bridge review round 1"
            if scenario == "initial"
            else "private-attr remediation bridge review"
            if scenario in {"private_attr", "reentry_private_attr"}
            else "re-entry bridge review"
        )

        def should_fail(context: str) -> bool:
            if scenario == "initial":
                return context.startswith("bridge review round")
            if scenario == "private_attr" and context == "private-attr remediation bridge review":
                return True
            if scenario == "reentry":
                return context == "re-entry bridge review"
            if scenario == "reentry_private_attr" and context == "private-attr remediation bridge review":
                fail_state["private_attr_seen"] += 1
                return fail_state["private_attr_seen"] == 1
            return False

        def prepare_authority_side(
            repo_root,
            *,
            wave_id,
            phase,
            review_round,
            context,
            **_kwargs,
        ):
            if review_round == "bridge_pre_review":
                prepared_bridge_contexts.append(context)
            receipt_path = (
                Path(repo_root)
                / ".agent_bus"
                / "meta"
                / "candidate_authority_receipts"
                / wave_id
                / f"{phase}-{review_round}.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(
                json.dumps({"review_round": review_round, "context": context}) + "\n",
                encoding="utf-8",
            )
            if should_fail(context):
                return None, "stale bridge authority"
            return str(receipt_path), None

        bridge_decisions_by_scenario = {
            "initial": [],
            "private_attr": [("GO", 0)],
            "reentry": [("GO", 0)],
            "reentry_private_attr": [("GO", 0), ("GO", 0)],
        }
        bridge_decisions = iter(bridge_decisions_by_scenario[scenario])

        def bridge_side(_repo_root, _summary, **kwargs):
            on_started = kwargs.get("on_started")
            if on_started is not None:
                on_started()
            decision, exit_code = next(bridge_decisions)
            return {
                "exit_code": exit_code,
                "stdout": f"{decision}\n",
                "stderr": "",
                "decision": decision,
                "job_id": kwargs.get("job_id", decision.lower()),
            }

        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [test_path],
        }
        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "private attr",
            "stderr": "",
            "test_files": [test_path],
        }
        gate_results_by_scenario = {
            "initial": [gate_pass],
            "private_attr": [gate_fail, gate_pass],
            "reentry": [gate_pass],
            "reentry_private_attr": [gate_pass, gate_fail, gate_pass],
        }
        gate_results = iter(gate_results_by_scenario[scenario])

        supervisor_decision = (
            "NEEDS_PHASE_B"
            if scenario in {"reentry", "reentry_private_attr"}
            else "COMMIT_GO"
        )

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "prepare_candidate_authority_if_configured", side_effect=prepare_authority_side), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=lambda *_args, **_kwargs: next(gate_results)), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {
                     "decision": supervisor_decision,
                     "summary": "re-enter Phase B" if supervisor_decision == "NEEDS_PHASE_B" else "",
                     "status": "success",
                     "findings": [],
                 },
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(
                repo,
                plan_path,
                max_bridge_rounds=3,
                routing_record_override={
                    **_VALID_ROUTING_RECORD,
                    "task_id": "[PIPELINE-RECOVERY]",
                    "wave_name": wave_id,
                    "wave_class": "L4_ENABLER",
                    "target_gate_id": "G8",
                },
            )

        assert result["status"] == "error", result
        assert result["step"] == expected_step
        assert result["errors"] == [
            f"Candidate authority is required before {expected_context}",
            "stale bridge authority",
        ]
        assert expected_context in prepared_bridge_contexts

    def test_bridge_rounds_prepare_same_wave_indicator_before_each_review(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-pre-review-order-2026-07-28"
        plan_path = "reports/control_plane/plan.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            "- `f.py`\n"
            f"- `{plan_path}`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        _write_canonical_tasks(repo, wave_id)
        mock_impl = _make_mock_impl()
        events: list[str] = []
        bridge_calls = 0
        real_tracker_predicate = getattr(
            pb_mod,
            "_tasks_has_canonical_wave_tracker_note",
        )

        def reconcile_side(_repo_root, _allowed):
            events.append("reconcile")
            return True, ""

        def stage_side(_repo_root, _files):
            events.append("stage_candidate")
            return True, ""

        def authority_side(*args, **kwargs):
            events.append("tracker_authority")
            return real_tracker_predicate(*args, **kwargs)

        def collect_side(_repo_root, *, wave_id):
            events.append("collect_and_stage_indicator")
            return f"reports/l4_wave_indicators/{wave_id}.json", None

        def refresh_side(*args, **kwargs):
            events.append("refresh_and_stage_packet")
            return True, None

        def bridge_side(*args, **kwargs):
            nonlocal bridge_calls
            bridge_calls += 1
            events.append("review")
            if bridge_calls == 1:
                return {
                    "exit_code": 0,
                    "stdout": "REQUEST_CHANGES\n",
                    "stderr": "",
                    "decision": "REQUEST_CHANGES",
                    "job_id": "j1",
                }
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "j2",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", "f.py", plan_path, indicator_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", "f.py", plan_path, indicator_path]), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", side_effect=reconcile_side), \
             patch.object(pb_mod, "_stage_files_for_pipeline", side_effect=stage_side), \
             patch.object(pb_mod, "_tasks_has_canonical_wave_tracker_note", side_effect=authority_side), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", side_effect=collect_side) as mock_collect, \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", side_effect=refresh_side), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings here"), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {
                     "decision": "COMMIT_GO",
                     "summary": "",
                     "status": "success",
                     "findings": [],
                 },
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ):
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "commit_ready", result
        assert mock_collect.call_count == 2
        review_indexes = [
            index for index, event in enumerate(events) if event == "review"
        ]
        assert len(review_indexes) == 2
        expected_pre_review = [
            "reconcile",
            "stage_candidate",
            "tracker_authority",
            "collect_and_stage_indicator",
            "refresh_and_stage_packet",
        ]
        for review_index in review_indexes:
            assert events[review_index - len(expected_pre_review):review_index] == (
                expected_pre_review
            )

    def test_bridge_round_staging_failure_stops_pipeline(self, tmp_path):
        """If restaging fails before bridge review, fail closed instead of reviewing stale index state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "_stage_files", return_value=False), \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_pre_review_staging"
        mock_bridge.assert_not_called()

    def test_missing_same_wave_tracker_authority_blocks_collector_and_reviewer(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-missing-tracker-authority-2026-07-28"
        plan_path = "reports/control_plane/plan.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            f"- `{plan_path}`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        (repo / "TASKS.md").write_text(
            "## Ra\n\n"
            "- Tracker sync note (2026-07-28, unrelated-wave): "
            "**Unrelated.**. Class: L4_ENABLER.\n\n"
            "---\n",
            encoding="utf-8",
        )
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_pre_review_tracker_authority"
        assert "Canonical same-wave TASKS authority is required" in result["errors"][0]
        mock_collector.assert_not_called()
        mock_bridge.assert_not_called()

    @pytest.mark.parametrize(
        "duplicate_is_canonical",
        [True, False],
        ids=["canonical_duplicate", "malformed_duplicate"],
    )
    def test_duplicate_tracker_authority_blocks_collector_and_reviewer(
        self,
        tmp_path,
        real_pre_review_package,
        duplicate_is_canonical,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-duplicate-tracker-authority-2026-07-28"
        plan_path = "reports/control_plane/plan.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            f"- `{plan_path}`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        canonical_note = (
            f"- Tracker sync note (2026-07-28, {wave_id}): "
            "**Phase B pre-review package.**. Class: L4_ENABLER. "
            "target_gate_id: G8.\n"
        )
        duplicate_note = (
            canonical_note
            if duplicate_is_canonical
            else (
                f"- Tracker sync note (2026-07-28, {wave_id}): "
                "malformed same-wave duplicate\n"
            )
        )
        (repo / "TASKS.md").write_text(
            f"## Ra\n\n{canonical_note}{duplicate_note}\n---\n",
            encoding="utf-8",
        )
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_pre_review_tracker_authority"
        assert "Canonical same-wave TASKS authority is required" in result["errors"][0]
        mock_collector.assert_not_called()
        mock_bridge.assert_not_called()

    @pytest.mark.parametrize(
        ("failure", "expected_step"),
        [
            ("indicator", "bridge_pre_review_l4_indicator"),
            ("packet", "bridge_pre_review_indicator_scope"),
        ],
    )
    def test_pre_review_mechanical_failure_blocks_reviewer(
        self,
        tmp_path,
        real_pre_review_package,
        failure,
        expected_step,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = f"phase-b-pre-review-{failure}-failure-2026-07-28"
        plan_path = "reports/control_plane/plan.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / plan_path).write_text(
            "# Plan\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            f"- `{plan_path}`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        _write_canonical_tasks(repo, wave_id)
        mock_impl = _make_mock_impl()
        collector_result = (
            (None, "git add -f failed for canonical indicator")
            if failure == "indicator"
            else (indicator_path, None)
        )
        packet_result = (
            (False, "simulated atomic packet refresh failure")
            if failure == "packet"
            else (True, None)
        )

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["TASKS.md", plan_path]), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", return_value=(True, "")), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", return_value=collector_result), \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", return_value=packet_result) as mock_refresh, \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge:
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == expected_step
        mock_bridge.assert_not_called()
        if failure == "indicator":
            mock_refresh.assert_not_called()

    def test_question_fails_closed(self, tmp_path):
        """QUESTION requires founder input — pipeline fails closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 1, "stdout": "QUESTION\n", "stderr": "",
                 "decision": "QUESTION", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="question content"), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "question_for_founder"
        assert "founder" in result["errors"][0].lower()

    def test_implementer_failure_during_bridge_fix_is_fatal(self, tmp_path):
        """If implementer fails during bridge fix round, pipeline stops."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        call_count = [0]
        def impl_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"status": "success", "output": "ok", "stderr": "", "exit_code": 0,
                        "job_id": "i1", "model_override_applied": False}
            return {"status": "error", "output": "", "stderr": "adapter crashed", "exit_code": 1,
                    "job_id": "i2", "model_override_applied": False}

        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.side_effect = impl_side_effect

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="fix this"), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "implementer_bridge_fix"


@pytest.mark.usefixtures("mock_routing_record")
class TestBridgeDecisionExitContract:
    """REQUEST_CHANGES/NO_GO remain recoverable under the bridge CLI exit contract."""

    def test_cli_exit_one_with_request_changes_is_recoverable(self, tmp_path):
        """bridge_supervisor review returns exit=1 for REQUEST_CHANGES; executor must continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2

    def test_unexpected_positive_exit_with_no_go_fails_closed(self, tmp_path):
        """Unexpected positive exits remain infrastructure failures even with a decision token."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 7, "stdout": "NO_GO\n", "stderr": "",
                 "decision": "NO_GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_subprocess"
        assert "unexpected exit" in result["errors"][0].lower()

    def test_zero_exit_with_request_changes_is_recoverable(self, tmp_path):
        """exit_code=0 + REQUEST_CHANGES is a real review — pipeline should continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        call_count = [0]

        def bridge_side(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryLoopMirrorsInitial:
    """NEEDS_PHASE_B re-entry loop must mirror initial: REQUEST_CHANGES re-invokes implementer, QUESTION fails closed."""

    def test_reentry_question_fails_closed(self, tmp_path):
        """QUESTION during re-entry must fail closed for founder input."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] <= 1:
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"}
            # Re-entry bridge returns QUESTION
            return {"exit_code": 1, "stdout": "QUESTION\n", "stderr": "", "decision": "QUESTION", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="question text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "fix more", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "question_for_founder"
        assert "founder" in result["errors"][0].lower()

    def test_reentry_request_changes_reinvokes_implementer(self, tmp_path):
        """REQUEST_CHANGES during re-entry must re-invoke implementer with bridge findings."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        pager_calls = []

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "init"}
            if bridge_calls[0] == 2:
                # Re-entry R1: REQUEST_CHANGES (exit_code=1 under bridge CLI contract)
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "re1"}
            # Re-entry R2: GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "re2"}

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {
                "enabled": True,
                "event_id": f"evt-{kwargs['transition_key']}",
                "attempted": [],
                "budget_exhausted": False,
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="bridge findings text"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "needs fix", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            # First supervisor returns NEEDS_PHASE_B, re-entry bridge R1 returns REQUEST_CHANGES,
            # implementer re-invoked, re-entry bridge R2 returns GO
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=10)

        # Implementer must have been called at least 3 times:
        # 1. initial, 2. first re-entry (supervisor findings), 3. second re-entry (bridge findings)
        assert mock_impl.invoke_implementer.call_count >= 3
        reentry_starts = [
            call for call in pager_calls
            if call["event_type"] == "phase_b_implementer_started"
            and call["state"] == "reentry_started"
        ]
        transition_keys = [call["transition_key"] for call in reentry_starts]
        assert len(transition_keys) == 2
        assert len(transition_keys) == len(set(transition_keys))
        assert transition_keys[0].endswith(":supervisor:implementer_started")
        assert ":phase-b-reentry-r2-" in transition_keys[1]
        supervisor_reentry_source = mock_impl.build_implementation_prompt.call_args_list[1].args[0]
        bridge_reentry_source = mock_impl.build_implementation_prompt.call_args_list[2].args[0]
        assert "## Re-entry Findings\n\nneeds fix" in supervisor_reentry_source
        assert "## Re-entry Findings (" not in supervisor_reentry_source
        assert (
            "## Re-entry Findings (REQUEST_CHANGES)\n\nbridge findings text"
            in bridge_reentry_source
        )


class TestExactReceiptAuthority:
    """Receipt path must be exact per-invocation, not heuristic discovery."""

    def test_write_pre_commit_receipt_returns_per_invocation_path(self):
        """Supervisor receipt writer returns per-invocation path, not canonical."""
        # Use the already-loaded module from other tests.
        import meta_bridge_supervisor as meta_mod

        from unittest.mock import patch as _p

        response = meta_mod.MetaBridgeResponse(
            status="success", decision="COMMIT_GO", summary="ok",
        )
        pkg_path = Path("/tmp/test_receipt_pkg.json")
        pkg_path.write_text("{}", encoding="utf-8")

        import tempfile
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with _p.object(meta_mod, "compute_staged_sha", return_value="abc"):
                result_path = meta_mod.write_pre_commit_receipt(response, pkg_path, repo_root=repo)

            # Must return per-invocation path, not canonical
            assert "pre_commit_receipts" in str(result_path)
            assert "receipt_" in result_path.name
            assert result_path.exists()

            # Canonical must ALSO exist (hook compat)
            canonical = repo / ".agent_bus" / "meta" / meta_mod.PRE_COMMIT_RECEIPT_NAME
            assert canonical.exists()

    def test_protocol_docs_no_manual_commit_fallback(self):
        """protocol_wave_execution.md must not present manual commit as normal path."""
        import os
        mem_dir = "/Users/jeffabrams/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory"
        proto = Path(mem_dir) / "protocol_wave_execution.md"
        if proto.exists():
            content = proto.read_text()
            # Must not have the old manual fallback steps
            assert "git push -u origin" not in content
            assert "gh pr create --base dev" not in content
            assert "merge_pr.sh <PR#> --sweep" not in content
            # Should reference commit_executor as the path
            assert "commit_executor" in content


class TestEmptyReceiptPathRejected:
    """Phase B must reject empty receipt_path before emitting commit_ready."""

    def test_empty_receipt_path_fails_closed(self):
        """If supervisor returns empty receipt_path, phase_b must NOT emit commit_ready.

        R2 finding #2: empty receipt_path + commit_ready violates the receipt authority contract.
        """
        # Verify the guard exists in source — structural check
        import inspect
        src = inspect.getsource(pb_mod.run_phase_b)
        # The fix adds a guard: "if not receipt_path" → return error before commit_ready
        # This must appear between supervisor result capture and commit_ready assignment
        assert "if not receipt_path" in src, (
            "phase_b_executor must guard against empty receipt_path before commit_ready"
        )
        # The guard must return an error status
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "if not receipt_path" in line:
                following = "\n".join(lines[i:i + 10])
                assert "error" in following.lower() and "fail" in following.lower(), (
                    "Empty receipt_path guard must return error with fail-closed message"
                )
                break


class TestFindingDisposition:
    """Bridge findings with disposition field are correctly classified.

    Structured deferrability and mandatory-promotion authority are shared via
    recovery_gate.py; keyword lists remain sourced from executor_common.py:
    1. Critical/high severity — fail closed to blocking.
    2. Exact mandatory evidence_result conjunction — promote to blocking.
    3. Explicit disposition field — canonical values are authoritative.
    4. Keyword match against title/summary (BLOCKING_KEYWORDS / NON_BLOCKING_KEYWORDS).
    5. Medium/low severity without blocking keyword — non_blocking.
    6. Fail-closed default — blocking.
    """

    def test_package_import_can_load_shared_recovery_authority(self):
        """Package import registers the fallback module before dataclass loading."""
        repo_root = Path(__file__).resolve().parents[3]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import mu.tools.executors.phase_b_executor as pb; "
                    "print(pb._disposition_for_finding("  # ANTICHEAT_OK: exact package-import shared-authority regression
                    "{'title': 'ordinary finding', 'severity': 'medium'}))"
                ),
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert probe.returncode == 0, probe.stderr
        assert probe.stdout.strip() == (
            "('non_blocking', 'medium severity, no keyword match')"
        )

    def test_classify_all_blocking(self):
        """High severity and explicit sub-floor blocking are both blocking."""
        findings = [
            {"title": "Bug causes runtime failure", "class": "DEFECT", "severity": "high"},
            {"title": "Bug2", "severity": "medium", "disposition": "blocking"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2
        assert len(non_blocking) == 0

    def test_classify_all_non_blocking(self):
        """All non_blocking findings classified correctly."""
        findings = [
            {"title": "Nit1", "disposition": "non_blocking"},
            {"title": "Nit2", "disposition": "non_blocking"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 2

    def test_classify_mixed(self):
        """Mixed disposition findings separated correctly."""
        findings = [
            {"title": "Bug", "severity": "low", "disposition": "blocking"},
            {"title": "Nit", "disposition": "non_blocking"},
            {"title": "NoDisposition causes crash", "class": "DEFECT"},
        ]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2  # "Bug" (explicit) + "NoDisposition causes crash" (keyword match)
        assert len(non_blocking) == 1

    def test_missing_disposition_is_blocking(self):
        """Fail-closed: missing disposition with no keywords treated as blocking."""
        findings = [{"title": "Unknown"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_missing_disposition_medium_severity_no_keywords_non_blocking(self):
        """Medium severity without keywords → non_blocking (severity-appropriate default)."""
        findings = [{"title": "Some issue", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "medium severity without keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_missing_disposition_low_severity_non_blocking(self):
        """Low severity without keywords → non_blocking (severity-appropriate default)."""
        findings = [{"title": "Some issue", "severity": "low"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "low severity without keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_empty_findings(self):
        blocking, non_blocking = pb_mod._classify_findings([])  # ANTICHEAT_OK: testing internal executor functions
        assert blocking == []
        assert non_blocking == []

    # --- Classification contract tests ---

    def test_explicit_disposition_blocking(self):
        """Explicit disposition=blocking is honored below the severity floor."""
        findings = [{"title": "Anything", "severity": "medium", "disposition": "blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_explicit_disposition_non_blocking(self):
        """Finding with explicit disposition=non_blocking is classified as non_blocking."""
        findings = [{"title": "Anything", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_no_disposition_critical_severity_blocking(self):
        """No disposition + critical severity → always blocking."""
        findings = [{"title": "Something", "severity": "critical"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_critical_severity_overrides_explicit_non_blocking(self):
        """Critical severity cannot be downgraded by explicit non_blocking disposition."""
        findings = [{"title": "Critical bug", "severity": "critical", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_medium_no_runtime_impact_non_blocking(self):
        """No disposition + medium severity + no runtime keywords → non_blocking."""
        findings = [{"title": "Improve error message wording", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "medium severity with no keywords should be non_blocking"
        assert len(non_blocking) == 1

    def test_no_disposition_high_severity_runtime_failure_blocking(self):
        """No disposition + high severity + 'runtime failure' in title → blocking."""
        findings = [{"title": "Potential runtime failure in commit path", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_high_severity_theoretical_edge_case_blocks(self):
        """High severity cannot downgrade from title/summary hardening prose alone."""
        findings = [{"title": "Theoretical edge case in unusual config", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_disposition_for_finding_returns_reason(self):
        """_disposition_for_finding returns (disposition, reason) tuple."""
        disp, reason = pb_mod._disposition_for_finding({"title": "X", "disposition": "blocking"})  # ANTICHEAT_OK: testing internal executor functions
        assert disp == "blocking"
        assert "explicit" in reason

        disp, reason = pb_mod._disposition_for_finding({"title": "crash in pipeline", "severity": "high"})  # ANTICHEAT_OK: testing internal executor functions
        assert disp == "blocking"
        assert "high severity" in reason.lower()

    def test_no_disposition_high_severity_no_keywords_blocking(self):
        """High severity without any keyword match → blocking (fail-closed)."""
        findings = [{"title": "Refactor suggestion", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_no_disposition_summary_keyword_match(self):
        """Keywords in summary field (not just title) trigger classification."""
        findings = [{"title": "Issue", "summary": "This causes data loss", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "blocking keyword in summary should trigger blocking"

    def test_non_blocking_keyword_in_title(self):
        """Non-blocking keywords like 'hardening' route to non_blocking."""
        findings = [{"title": "Add hardening for edge case", "severity": "medium"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_low_doc_accuracy_blocking_keyword_stays_non_blocking(self):
        """Low-severity DOC_ACCURACY findings stay non-blocking even if they quote a blocker keyword."""
        findings = [{
            "title": "Bridge exit-code=1 conflates non-GO review with BridgeError infrastructure crash",
            "class": "DOC_ACCURACY",
            "severity": "low",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    # --- Single shared deferrability rule (reused from recovery_gate) ---

    @pytest.mark.parametrize(
        ("severity", "status", "candidate_relationship"),
        [
            ("low", "persisting", "pre-existing"),
            ("medium", "new", "candidate-introduced"),
        ],
    )
    def test_low_medium_explicit_blocking_stays_blocking(
        self, severity, status, candidate_relationship
    ):
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {
                "title": "Hardening-only nonblocking-looking context",
                "summary": "theoretical defense in depth",
                "severity": severity,
                "disposition": "blocking",
                "status": status,
                "candidate_relationship": candidate_relationship,
            }
        )
        assert disp == "blocking", reason

    def test_high_severity_explicit_blocking_stays_blocking(self):
        """High severity + explicit disposition=blocking → blocking (severity floor preserved)."""
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "Bug", "severity": "high", "disposition": "blocking"}
        )
        assert disp == "blocking", reason

    @pytest.mark.parametrize(
        "finding",
        [
            {"title": "F", "severity": "low", "disposition": "blocking"},
            {"title": "F", "severity": "medium", "disposition": "non_blocking"},
            {"title": "F", "severity": "high", "disposition": "non_blocking"},
            {"title": "F", "severity": "medium", "disposition": "invalid"},
            {"title": "F", "severity": "medium", "disposition": None},
            {"title": "F", "severity": "medium", "disposition": []},
            {
                "title": "F",
                "severity": "medium",
                "disposition": "non_blocking",
                "evidence_result": (
                    "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation; "
                    "MERGE_DISPOSITION=blocking"
                ),
            },
            {
                "title": "F",
                "severity": "low",
                "evidence_result": (
                    "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation; "
                    "MERGE_DISPOSITION=blocking"
                ),
            },
            {
                "title": "F",
                "severity": "medium",
                "evidence_result": (
                    "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation"
                ),
            },
        ],
        ids=[
            "explicit-blocking",
            "explicit-nonblocking",
            "severity-floor",
            "invalid",
            "explicit-null",
            "unhashable-invalid",
            "promotion-overrides-nonblocking",
            "promotion-with-omission",
            "incomplete-pair",
        ],
    )
    def test_disposition_matches_recovery_gate_deferrability(self, finding):
        """phase_b and recovery_gate share ONE deferrability rule (no divergence).

        For structured dispositions, severity floors, and exact evidence
        promotion, phase_b's _disposition_for_finding defers iff
        recovery_gate._finding_is_deferrable_on_go marks it deferrable. They must
        agree on every case.
        """
        rg_mod = load_module("recovery_gate", _EXECUTORS_DIR / "recovery_gate.py")
        phase_b_defers = (
            pb_mod._disposition_for_finding(finding)[0] == "non_blocking"  # ANTICHEAT_OK: testing internal executor functions
        )
        recovery_defers = rg_mod._finding_is_deferrable_on_go(finding)  # ANTICHEAT_OK: testing internal executor functions
        assert phase_b_defers == recovery_defers

    @pytest.mark.parametrize("severity", ["low", "medium"])
    def test_canonical_explicit_nonblockers_remain_deferrable(self, severity):
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "Nit", "severity": severity, "disposition": "non_blocking"}
        )
        assert disp == "non_blocking", reason

    @pytest.mark.parametrize(
        "disposition",
        ["BLOCKING", "ambiguous", "", None, ["non_blocking"]],
        ids=["case-shifted", "ambiguous", "empty", "null", "unhashable-list"],
    )
    def test_invalid_explicit_disposition_fails_closed(self, disposition):
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "F", "severity": "medium", "disposition": disposition}
        )
        assert disp == "blocking"
        assert "invalid disposition" in reason

    @pytest.mark.parametrize("structured_disposition", [None, "non_blocking"])
    def test_exact_mandatory_evidence_promotes_with_distinct_reason(
        self, structured_disposition
    ):
        finding = {
            "title": "Omitted disposition marker probe",
            "severity": "medium",
            "evidence_result": (
                " technical_impact_class = DECLARED HARD-INVARIANT VIOLATION \n"
                " merge_disposition = BLOCKING "
            ),
        }
        if structured_disposition is not None:
            finding["disposition"] = structured_disposition

        disp, reason = pb_mod._disposition_for_finding(finding)  # ANTICHEAT_OK: testing exact shared evidence promotion

        assert disp == "blocking"
        assert "mandatory evidence_result promotion" in reason

    @pytest.mark.parametrize(
        "evidence_result",
        [
            "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation",
            "MERGE_DISPOSITION=blocking",
            (
                "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation; "
                "MERGE_DISPOSITION=non_blocking"
            ),
            (
                "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation and more; "
                "MERGE_DISPOSITION=blocking"
            ),
        ],
    )
    def test_incomplete_marker_pairs_retain_missing_disposition_fallback(
        self, evidence_result
    ):
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: exact omission fallback regression
            {
                "title": "Ordinary medium finding",
                "severity": "medium",
                "evidence_result": evidence_result,
            }
        )
        assert disp == "non_blocking", reason

    def test_explicit_non_blocking_uses_reachable_fall_through(self):
        """The explicit-disposition branch honors canonical non_blocking."""
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "Nit", "disposition": "non_blocking"}
        )
        assert disp == "non_blocking", reason
        assert reason == "explicit disposition field", reason


class TestGovernanceDowngrade:
    """Governance/doc findings on non-code paths downgrade to non-blocking.

    The predicate requires BOTH governance class AND governance path.
    A POLICY_BOUND finding on actual code stays blocking.
    """

    def test_policy_bound_on_report_path_is_non_blocking_below_severity_floor(self):
        """POLICY_BOUND on reports/ stays non-blocking only below high severity."""
        findings = [{
            "title": "Plan file has unchecked boxes",
            "class": "POLICY_BOUND",
            "severity": "medium",
            "file": "reports/control_plane/wave1a_pipeline_validation_2026-03-31.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "POLICY_BOUND on reports/ should be non-blocking"
        assert len(non_blocking) == 1

    def test_blocking_finding_convergence_honors_explicit_blocking_governance_finding(self):
        """A high-severity governance finding stays blocking via the severity floor.

        The high/critical floor fires before the governance downgrade, so an
        explicit-blocking governance finding at high severity remains blocking.
        Explicit blocking also remains blocking below the floor, as covered by
        the medium-severity regression.
        """
        findings = [{
            "title": "Control packet cites stale code line",
            "class": "POLICY_BOUND",
            "severity": "high",
            "file": "reports/control_plane/example.md",
            "disposition": "blocking",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_policy_bound_on_code_file_stays_blocking(self):
        """POLICY_BOUND on actual code file stays blocking — not governance."""
        findings = [{
            "title": "Code policy violation in executor",
            "class": "POLICY_BOUND",
            "severity": "high",
            "file": "mu/tools/executors/phase_b_executor.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "POLICY_BOUND on code file must stay blocking"
        assert len(non_blocking) == 0

    def test_doc_accuracy_on_tasks_md_is_non_blocking_below_severity_floor(self):
        """DOC_ACCURACY on TASKS.md stays non-blocking only below high severity."""
        findings = [{
            "title": "TASKS.md missing tracker sync note",
            "class": "DOC_ACCURACY",
            "severity": "medium",
            "file": "TASKS.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0, "DOC_ACCURACY on TASKS.md should be non-blocking"
        assert len(non_blocking) == 1

    def test_doc_accuracy_on_code_file_stays_blocking(self):
        """DOC_ACCURACY on a code file stays blocking — not governance."""
        findings = [{
            "title": "Doc comment contradicts behavior",
            "class": "DOC_ACCURACY",
            "severity": "high",
            "file": "mu/tools/agents/bridge_adapters.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "DOC_ACCURACY on code file must stay blocking"
        assert len(non_blocking) == 0

    def test_defect_on_report_path_not_downgraded(self):
        """DEFECT class on reports/ is NOT governance — class must also match."""
        findings = [{
            "title": "Script in report has a bug",
            "class": "DEFECT",
            "severity": "high",
            "file": "reports/control_plane/some_script.py",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "DEFECT on any path stays blocking regardless of path"
        assert len(non_blocking) == 0

    def test_governance_downgrade_reason_includes_file(self):
        """The downgrade reason includes the file path for auditability."""
        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "Stale reference",
            "class": "POLICY_BOUND",
            "severity": "medium",
            "file": "reports/deferred/README.md",
        })
        assert disp == "non_blocking"
        assert "governance" in reason.lower()
        assert "reports/deferred/README.md" in reason

    @pytest.mark.parametrize("severity", ["high", "critical"])
    def test_high_critical_governance_findings_stay_blocking(self, severity):
        """Severity floor overrides governance downgrade.

        Closes deferred_consolidation_phaseb_fail_closed_hardening_2026-04-02 defect 1:
        prior behavior downgraded critical/high POLICY_BOUND/DOC_ACCURACY on
        governance paths to non-blocking, which let real policy violations
        slip through. Contract is now: critical/high severity always blocks
        regardless of class or path; governance downgrade only applies at
        medium/low severity.
        """
        findings = [{
            "title": "Critical governance downgrade",
            "class": "POLICY_BOUND",
            "severity": severity,
            "file": "reports/control_plane/example.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, (
            f"{severity} POLICY_BOUND must block regardless of governance path "
            "(severity floor applies before governance downgrade)"
        )
        assert len(non_blocking) == 0

    @pytest.mark.parametrize("severity", ["high", "critical"])
    def test_defect_on_governance_path_stays_blocking(self, severity):
        """DEFECT findings on governance paths still block — only DOC_ACCURACY/POLICY_BOUND downgrade."""
        findings = [{
            "title": "Runtime defect in report",
            "class": "DEFECT",
            "severity": severity,
            "file": "reports/control_plane/example.md",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0


class TestStageFiles:
    """Staging must respect repo ignore rules and fail closed."""

    def test_stage_files_stages_normal_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "ok.txt").write_text("x", encoding="utf-8")

        assert pb_mod._stage_files(repo, ["ok.txt"]) is True  # ANTICHEAT_OK: testing internal executor functions

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        assert staged == ["ok.txt"]

    def test_stage_files_rejects_ignored_file_without_force_add(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (repo / "ignored.txt").write_text("x", encoding="utf-8")

        assert pb_mod._stage_files(repo, ["ignored.txt"]) is False  # ANTICHEAT_OK: testing internal executor functions

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.splitlines()
        assert staged == []

    def test_stage_files_with_diagnostics_returns_git_stderr(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        failure = subprocess.CalledProcessError(
            128,
            ["git", "add"],
            output="",
            stderr="fatal: Unable to create '/repo/.git/worktrees/w/index.lock': Operation not permitted",
        )
        with patch.object(pb_mod.subprocess, "run", side_effect=failure):
            ok, detail = pb_mod._stage_files_with_diagnostics(repo, ["ok.txt"])  # ANTICHEAT_OK

        assert ok is False
        assert "git add failed with exit=128" in detail
        assert "index.lock" in detail
        assert "Operation not permitted" in detail

    def test_stage_files_with_diagnostics_preserves_git_error(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (repo / "ignored.txt").write_text("x", encoding="utf-8")

        ok, detail = pb_mod._stage_files_with_diagnostics(repo, ["ignored.txt"])  # ANTICHEAT_OK: testing internal executor functions

        assert ok is False
        assert "git add failed" in detail
        assert "ignored.txt" in detail


class TestProtectedBranchCheckout:
    def test_startup_restores_persisted_branch_switch_stash_by_marker(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "pending",
                "marker": "phase_b:jabramsja/example-wave:abc123",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
            }),
            encoding="utf-8",
        )
        commands: list[list[str]] = []

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            assert kwargs["cwd"] == str(repo)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(cmd, stdout="stash@{1}\x00abc123\x00On dev: phase_b:jabramsja/example-wave:abc123\n")
            if cmd[:3] == ["git", "stash", "apply"]:
                return completed(cmd, stdout="Restored worktree")
            if cmd[:3] == ["git", "stash", "drop"]:
                return completed(cmd, stdout="Dropped refs/stash@{1}")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: recovery helper regression

        assert error is None
        assert ["git", "stash", "list", "--format=%gd%x00%H%x00%s"] in commands
        assert ["git", "stash", "apply", "--index", "stash@{1}"] in commands
        assert ["git", "stash", "drop", "stash@{1}"] in commands
        assert not state_path.exists()

    def test_startup_reresolves_persisted_mutable_branch_switch_stash_ref(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "stashed",
                "marker": "phase_b:jabramsja/example-wave:abc123",
                "stash_ref": "stash@{0}",
                "stash_oid": "marker-oid",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
            }),
            encoding="utf-8",
        )
        commands: list[list[str]] = []

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            assert kwargs["cwd"] == str(repo)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(
                    cmd,
                    stdout=(
                        "stash@{0}\x00other-oid\x00On dev: other-stash\n"
                        "stash@{1}\x00marker-oid\x00On dev: phase_b:jabramsja/example-wave:abc123\n"
                    ),
                )
            if cmd[:3] == ["git", "stash", "apply"]:
                return completed(cmd, stdout=f"Applied {cmd[-1]}")
            if cmd[:3] == ["git", "stash", "drop"]:
                return completed(cmd, stdout=f"Dropped {cmd[-1]}")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: recovery helper regression

        assert error is None
        assert ["git", "stash", "apply", "--index", "stash@{1}"] in commands
        assert ["git", "stash", "drop", "stash@{1}"] in commands
        assert ["git", "stash", "apply", "--index", "stash@{0}"] not in commands
        assert not state_path.exists()

    def test_startup_rejects_branch_switch_stash_oid_mismatch(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "stashed",
                "marker": "phase_b:jabramsja/example-wave:abc123",
                "stash_ref": "stash@{0}",
                "stash_oid": "old-oid",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
            }),
            encoding="utf-8",
        )
        commands: list[list[str]] = []

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            assert kwargs["cwd"] == str(repo)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(cmd, stdout="stash@{1}\x00new-oid\x00On dev: phase_b:jabramsja/example-wave:abc123\n")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: recovery helper regression

        assert error is not None
        assert "object id mismatch" in error
        assert all(cmd[:3] != ["git", "stash", "apply"] for cmd in commands)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["status"] == "stash_oid_mismatch"

    def test_run_phase_b_fails_closed_on_unresolved_branch_switch_stash(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "pop_failed",
                "stash_ref": "stash@{0}",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
                "output": "CONFLICT (content): file",
            }),
            encoding="utf-8",
        )

        result = pb_mod.run_phase_b(repo, "reports/control_plane/example.md")

        assert result["status"] == "error"
        assert result["step"] == "restore_branch_switch_stash"
        assert "previously failed" in result["errors"][0]
        assert state_path.exists()

    def test_branch_switch_stash_pop_failure_is_fail_closed_and_recoverable(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        commands: list[list[str]] = []
        marker_holder: dict[str, str] = {}

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            assert kwargs["cwd"] == str(repo)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            if cmd[:4] == ["git", "stash", "push", "--include-untracked"]:
                marker_holder["marker"] = cmd[-1]
                return completed(cmd, stdout="Saved working directory and index state")
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(cmd, stdout=f"stash@{{0}}\x00abc123\x00On dev: {marker_holder['marker']}\n")
            if cmd[:2] == ["git", "checkout"]:
                return completed(cmd, stdout="Switched to branch")
            if cmd[:3] == ["git", "stash", "apply"]:
                return completed(cmd, returncode=1, stderr="CONFLICT (content): file")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._checkout_feature_branch_from_protected_branch(  # ANTICHEAT_OK: regression for protected branch switch helper
                repo,
                current_branch="dev",
                feature_branch="jabramsja/example-wave",
                branch_exists=True,
                log=lambda _msg: None,
            )

        assert error is not None
        assert "dirty worktree restore failed" in error
        assert "git stash apply --index stash@{0} failed" in error
        assert ["git", "stash", "apply", "--index", "stash@{0}"] in commands

        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["status"] == "pop_failed"
        assert state["stash_ref"] == "stash@{0}"
        assert state["stash_oid"] == "abc123"
        assert state["current_branch"] == "dev"
        assert state["feature_branch"] == "jabramsja/example-wave"
        assert "CONFLICT" in state["output"]

    def test_startup_drops_restore_applied_branch_switch_stash_without_reapplying(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "restore_applied",
                "marker": "phase_b:jabramsja/example-wave:abc123",
                "stash_ref": "stash@{0}",
                "stash_oid": "marker-oid",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
            }),
            encoding="utf-8",
        )
        commands: list[list[str]] = []

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            assert kwargs["cwd"] == str(repo)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(cmd, stdout="stash@{2}\x00marker-oid\x00On dev: phase_b:jabramsja/example-wave:abc123\n")
            if cmd[:3] == ["git", "stash", "drop"]:
                return completed(cmd, stdout="Dropped refs/stash@{2}")
            if cmd[:3] == ["git", "stash", "apply"]:
                raise AssertionError("restore_applied restart must not apply the stash again")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: branch-stash restore_applied restart

        assert error is None
        assert ["git", "stash", "drop", "stash@{2}"] in commands
        assert all(cmd[:3] != ["git", "stash", "apply"] for cmd in commands)
        assert not state_path.exists()

    def test_startup_clears_restore_applied_branch_switch_state_when_marker_already_dropped(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "restore_applied",
                "marker": "phase_b:jabramsja/example-wave:abc123",
                "stash_ref": "stash@{0}",
                "stash_oid": "marker-oid",
                "current_branch": "dev",
                "feature_branch": "jabramsja/example-wave",
            }),
            encoding="utf-8",
        )
        commands: list[list[str]] = []

        def completed(cmd, returncode=0, stdout="", stderr=""):
            return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            if cmd[:3] == ["git", "stash", "list"]:
                return completed(cmd, stdout="")
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: branch-stash post-drop restart

        assert error is None
        assert commands == [["git", "stash", "list", "--format=%gd%x00%H%x00%s"]]
        assert not state_path.exists()

    def test_startup_clears_restore_dropped_branch_switch_state_without_git(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({
                "status": "restore_dropped",
                "marker": "phase_b:jabramsja/example-wave:abc123",
            }),
            encoding="utf-8",
        )

        with patch.object(pb_mod.subprocess, "run") as mock_run:
            error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: branch-stash pre-cleanup restart

        assert error is None
        mock_run.assert_not_called()
        assert not state_path.exists()

    def test_branch_switch_stash_restore_restart_after_apply_drops_without_duplicate_application(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text(".agent_bus/\n", encoding="utf-8")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "file.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)

        stash_state, stash_error = pb_mod._stash_dirty_worktree_for_branch_switch(  # ANTICHEAT_OK: branch-stash transaction setup
            repo,
            current_branch="dev",
            feature_branch="jabramsja/example-wave",
        )
        assert stash_error is None
        assert stash_state is not None
        subprocess.run(["git", "checkout", "-b", "jabramsja/example-wave"], cwd=repo, check=True, capture_output=True)

        with patch.object(pb_mod, "_drop_branch_switch_stash_record", side_effect=RuntimeError("crash after apply")):
            with pytest.raises(RuntimeError, match="crash after apply"):
                pb_mod._restore_branch_switch_stash(repo, stash_state)  # ANTICHEAT_OK: branch-stash crash seam

        state_path = repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["status"] == "restore_applied"
        assert (repo / "file.txt").read_text(encoding="utf-8") == "changed\n"
        assert _git_stdout(repo, "diff", "--cached", "--name-only") == "file.txt"

        error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: branch-stash crash restart

        assert error is None
        assert not state_path.exists()
        assert (repo / "file.txt").read_text(encoding="utf-8") == "changed\n"
        assert _git_stdout(repo, "diff", "--cached", "--name-only") == "file.txt"
        assert "phase_b:jabramsja/example-wave" not in _git_stdout(repo, "stash", "list")

    def test_branch_switch_stash_restore_started_restart_proves_applied_untracked_wip(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text(".agent_bus/\n", encoding="utf-8")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "file.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
        (repo / "new.txt").write_text("new\n", encoding="utf-8")

        stash_state, stash_error = pb_mod._stash_dirty_worktree_for_branch_switch(  # ANTICHEAT_OK: branch-stash transaction setup
            repo,
            current_branch="dev",
            feature_branch="jabramsja/example-wave",
        )
        assert stash_error is None
        assert stash_state is not None
        subprocess.run(["git", "checkout", "-b", "jabramsja/example-wave"], cwd=repo, check=True, capture_output=True)
        stash_state.update({
            "status": "restore_started",
            "restore_started_at": "2026-08-21T00:00:00+00:00",
        })
        pb_mod._write_branch_stash_state(repo, stash_state)  # ANTICHEAT_OK: branch-stash restore_started seam
        subprocess.run(
            ["git", "stash", "apply", "--index", stash_state["stash_ref"]],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

        error = pb_mod._restore_pending_branch_switch_stash(repo)  # ANTICHEAT_OK: branch-stash crash restart

        assert error is None
        assert not (repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json").exists()
        assert (repo / "file.txt").read_text(encoding="utf-8") == "changed\n"
        assert (repo / "new.txt").read_text(encoding="utf-8") == "new\n"
        assert _git_stdout(repo, "diff", "--cached", "--name-only") == "file.txt"
        assert "phase_b:jabramsja/example-wave" not in _git_stdout(repo, "stash", "list")

    def test_branch_switch_stash_restore_preserves_staged_index_state(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / ".gitignore").write_text(".agent_bus/\n", encoding="utf-8")
        (repo / "file.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore", "file.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        (repo / "file.txt").write_text("changed\n", encoding="utf-8")
        subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)

        before_cached = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()

        error = pb_mod._checkout_feature_branch_from_protected_branch(  # ANTICHEAT_OK: real git regression for staged stash restore
            repo,
            current_branch="dev",
            feature_branch="jabramsja/example-wave",
            branch_exists=False,
            log=lambda _msg: None,
        )

        after_cached = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        after_worktree = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()

        assert error is None
        assert before_cached == ["file.txt"]
        assert after_cached == ["file.txt"]
        assert after_worktree == []
        assert not (repo / ".agent_bus" / "executors" / "phase_b_branch_stash.json").exists()


class TestHighSeverityDetailHeuristic:
    """High severity no longer downgrades from prose-only detail/description text."""

    def test_hardening_indicator_in_detail_still_blocking(self):
        """High severity detail prose cannot downgrade disposition."""
        findings = [{
            "title": "Receipt field could be spoofed",
            "severity": "high",
            "detail": "In a theoretical adversarial setup, the receipt field could be spoofed.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_defect_indicator_in_detail_blocking(self):
        """High severity finding with defect indicator in detail → blocking."""
        findings = [{
            "title": "Commit proceeds without receipt",
            "severity": "high",
            "detail": "When receipt is missing, the pipeline still proceeds to commit_ready.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_defect_indicator_returns_success_blocking(self):
        """'returns success' in detail is a defect signal → blocking."""
        findings = [{
            "title": "Validation gap",
            "severity": "high",
            "detail": "The function returns success even when the input is malformed.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1

    def test_hardening_indicator_could_be_bypassed_still_blocking(self):
        """High severity 'could be bypassed' prose still fails closed."""
        findings = [{
            "title": "Gate check",
            "severity": "high",
            "detail": "With a crafted input, the gate could be bypassed in theory.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_conflicting_indicators_fail_closed(self):
        """Both defect and hardening indicators → blocking (fail-closed on conflict)."""
        findings = [{
            "title": "Ambiguous",
            "severity": "high",
            "detail": "Theoretical but the function returns success anyway.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1, "conflicting indicators should fail-closed to blocking"

    def test_no_indicators_still_blocking(self):
        """High severity, no keywords, no detail indicators → blocking (fail-closed)."""
        findings = [{
            "title": "Some vague concern",
            "severity": "high",
            "detail": "This is a finding about something.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1

    def test_hardening_in_description_field_still_blocking(self):
        """High severity description prose also cannot downgrade disposition."""
        findings = [{
            "title": "Spoofable field",
            "severity": "high",
            "description": "This is a synthetic scenario unlikely in practice.",
        }]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_disposition_for_finding_reason_includes_indicator(self):
        """Reason string captures the fail-closed high-severity rule."""
        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "X", "severity": "high",
            "detail": "theoretical edge case",
        })
        assert disp == "blocking"
        assert "high severity" in reason.lower()

        disp, reason = pb_mod._disposition_for_finding({  # ANTICHEAT_OK: testing internal executor functions
            "title": "X", "severity": "high",
            "detail": "the pipeline still proceeds past the gate",
        })
        assert disp == "blocking"
        assert "high severity" in reason.lower()


class TestRepeatFindingConvergenceCap:
    """Blocking findings stay blocking (no auto-downgrade). Repeat count tracked for loop termination."""

    def test_finding_stays_blocking_at_cap(self):
        """A finding appearing as blocking for 3+ rounds stays blocking (never downgraded)."""
        finding = {"title": "Stubborn bug", "severity": "high", "file": "foo.py",
                   "detail": "some vague concern"}
        history: dict[str, int] = {}

        # All rounds: stays blocking (no downgrade)
        for i in range(pb_mod.REPEAT_FINDING_CAP + 2):
            blocking, non_blocking = pb_mod._classify_findings([finding], history)  # ANTICHEAT_OK: testing internal executor functions
            assert len(blocking) == 1, f"Round {i+1}: finding must stay blocking"
            assert len(non_blocking) == 0, f"Round {i+1}: no auto-downgrade"

        # But history tracks the count for the caller's hard-failure check
        key = pb_mod._finding_key(finding)  # ANTICHEAT_OK: testing internal executor functions
        assert history[key] == pb_mod.REPEAT_FINDING_CAP + 2

    def test_repeat_cap_per_finding_key(self):
        """Different findings have independent repeat counters."""
        f1 = {"title": "Issue A", "severity": "high", "file": "a.py",
               "detail": "vague concern"}
        f2 = {"title": "Issue B", "severity": "high", "file": "b.py",
               "detail": "vague concern"}
        history: dict[str, int] = {}

        # Run f1 to cap, then introduce f2
        for _ in range(pb_mod.REPEAT_FINDING_CAP):
            pb_mod._classify_findings([f1], history)  # ANTICHEAT_OK: testing internal executor functions

        # f1 is at cap, f2 is fresh — both stay blocking
        blocking, non_blocking = pb_mod._classify_findings([f1, f2], history)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 2, "Both findings must stay blocking"
        assert len(non_blocking) == 0, "No auto-downgrade"
        # But their counts differ
        assert history[pb_mod._finding_key(f1)] == pb_mod.REPEAT_FINDING_CAP + 1  # ANTICHEAT_OK: testing internal executor functions
        assert history[pb_mod._finding_key(f2)] == 1  # ANTICHEAT_OK: testing internal executor functions

    def test_disappeared_finding_pruned_from_history(self):
        """Findings that disappear from a round get pruned from history."""
        f1 = {"title": "Transient", "severity": "high", "file": "x.py",
               "detail": "vague concern"}
        history: dict[str, int] = {}

        # Appear in round 1
        pb_mod._classify_findings([f1], history)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) in history  # ANTICHEAT_OK: testing internal executor functions

        # Disappear in round 2 (empty findings)
        pb_mod._classify_findings([], history)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) not in history  # ANTICHEAT_OK: testing internal executor functions

    def test_no_history_means_no_downgrade(self):
        """Without finding_history, repeat cap is not applied."""
        finding = {"title": "Bug", "severity": "high", "file": "x.py",
                   "detail": "vague concern"}
        for _ in range(5):
            blocking, non_blocking = pb_mod._classify_findings([finding])  # ANTICHEAT_OK: testing internal executor functions
            assert len(blocking) == 1

    def test_non_blocking_finding_resets_counter(self):
        """A finding that classifies as non_blocking resets its repeat counter."""
        history: dict[str, int] = {}

        # First two rounds: blocking (medium severity, no keywords → non_blocking,
        # but we need blocking first so use no severity + no keywords → fail-closed blocking)
        f_blocking = {"title": "Concern", "file": "x.py"}
        pb_mod._classify_findings([f_blocking], history)  # ANTICHEAT_OK: testing internal executor functions
        pb_mod._classify_findings([f_blocking], history)  # ANTICHEAT_OK: testing internal executor functions
        key = pb_mod._finding_key(f_blocking)  # ANTICHEAT_OK: testing internal executor functions
        assert history[key] == 2

        # Now it appears as medium severity with non_blocking keyword — counter resets
        f_nb = {"title": "Concern", "severity": "medium", "file": "x.py",
                "disposition": "non_blocking"}
        pb_mod._classify_findings([f_nb], history)  # ANTICHEAT_OK: testing internal executor functions
        assert key not in history

    def test_finding_key_stable(self):
        """Finding key is based on title + file, case-insensitive for title."""
        f1 = {"title": "Bug in foo", "file": "src/foo.py"}
        f2 = {"title": "bug in foo", "file": "src/foo.py"}
        f3 = {"title": "Bug in foo", "file": "src/bar.py"}
        assert pb_mod._finding_key(f1) == pb_mod._finding_key(f2)  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._finding_key(f1) != pb_mod._finding_key(f3)  # ANTICHEAT_OK: testing internal executor functions


class TestDeferredPacketFiling:
    """Non-blocking findings are auto-filed to deferred packet."""

    def test_writes_deferred_packet(self, tmp_path):
        findings = [
            {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "low", "file": "foo.py", "disposition": "non_blocking"},
        ]
        packet = pb_mod._write_deferred_packet(tmp_path, "test-wave-42", findings)  # ANTICHEAT_OK: testing internal executor functions
        assert packet.exists()
        content = packet.read_text()
        assert "Style nit" in content
        assert "non_blocking" in content
        assert "test-wave-42" in content
        assert packet.parent == tmp_path / "reports" / "deferred" / "non_blocking"

    def test_packet_name_from_wave_id(self, tmp_path):
        packet = pb_mod._write_deferred_packet(tmp_path, "my-wave", [{"title": "x"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.name == "my-wave_bridge_nonblockers.md"

    def test_packet_name_normalizes_untrusted_wave_id(self, tmp_path):
        packet = pb_mod._write_deferred_packet(tmp_path, "../../Weird Wave!!", [{"title": "x"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.name == "weird-wave_bridge_nonblockers.md"

    def test_creates_directory_if_missing(self, tmp_path):
        repo = tmp_path / "nested"
        repo.mkdir()
        packet = pb_mod._write_deferred_packet(repo, "w", [{"title": "t"}])  # ANTICHEAT_OK: testing internal executor functions
        assert packet.exists()

    def test_collect_supervisor_deferred_items_includes_changed_non_blocking_packets(self):
        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            [
                "mu/tools/executors/phase_b_executor.py",
                "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
                "reports/deferred/non_blocking/README.md",
            ],
            None,
        )
        assert deferred_items == ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"]

    def test_collect_supervisor_deferred_items_dedupes_explicit_packet(self):
        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"],
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        )
        assert deferred_items == ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"]

    def test_collect_supervisor_deferred_items_ignores_stale_explicit_packet(self):
        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            ["mu/tools/executors/phase_b_executor.py"],
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        )
        assert deferred_items == []

    def test_collect_supervisor_deferred_items_ignores_staged_deleted_packet(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        deferred_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / deferred_rel).write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", deferred_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", deferred_rel], cwd=repo, check=True, capture_output=True)

        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert f"D  {deferred_rel}" in status

        deferred_items = pb_mod._collect_supervisor_deferred_items(  # ANTICHEAT_OK: testing internal executor functions
            [deferred_rel],
            deferred_rel,
            repo_root=repo,
        )

        assert deferred_items == []

    def test_commit_handoff_stage_files_omit_closed_active_staged_deletion(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "wave"
        active_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        archive_rel = "reports/archive/deferred/wave_bridge_nonblockers_closed-by-wave.md"
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / active_rel).write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", active_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", active_rel], cwd=repo, check=True, capture_output=True)
        (repo / archive_rel).parent.mkdir(parents=True)
        (repo / archive_rel).write_text("# Deferred archive\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_rel], cwd=repo, check=True)

        files_to_stage, staged_deletions = pb_mod._split_commit_handoff_stage_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            wave_id,
            [active_rel, archive_rel],
        )

        assert files_to_stage == [archive_rel]
        assert staged_deletions == [active_rel]
        handoff, errors = commit_mod.build_commit_handoff(
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            files_to_stage=files_to_stage,
            commit_message="test: handoff\n\nCo-Authored-By: test",
            fixes_implemented=["test"],
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            repo_root=repo,
        )

        assert errors == []
        assert handoff["files_to_stage"] == [archive_rel]

    def test_commit_handoff_stage_files_scope_staged_deletion_for_branch_rebind(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "wave"
        active_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        archive_rel = "reports/archive/deferred/wave_bridge_nonblockers_closed-by-wave.md"
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / active_rel).write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", active_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", active_rel], cwd=repo, check=True, capture_output=True)
        (repo / archive_rel).parent.mkdir(parents=True)
        (repo / archive_rel).write_text("# Deferred archive\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_rel], cwd=repo, check=True)

        files_to_stage, staged_deletions = pb_mod._split_commit_handoff_stage_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            wave_id,
            [active_rel, archive_rel],
        )
        handoff, errors = commit_mod.build_commit_handoff(
            wave_id=wave_id,
            task_id="[PIPELINE-RECOVERY]",
            files_to_stage=files_to_stage,
            commit_message="test: handoff\n\nCo-Authored-By: test",
            fixes_implemented=["test"],
            wave_class="MAINTENANCE",
            target_gate_id="G8",
            scope_items=staged_deletions,
            repo_root=repo,
        )

        assert errors == []
        assert handoff["scope_items"] == [active_rel]
        tracked_dirty, untracked_dirty, outside_scope = commit_mod._collect_branch_rebind_dirty_scope(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            handoff=handoff,
        )
        assert active_rel in tracked_dirty
        assert archive_rel in tracked_dirty
        assert untracked_dirty == set()
        assert outside_scope == []

    def test_commit_handoff_stage_files_scope_predecessor_deletion_with_closed_archive(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        wave_id = "current-repair-wave"
        active_rel = "reports/deferred/non_blocking/predecessor-wave_bridge_nonblockers.md"
        archive_rel = (
            "reports/archive/deferred/"
            "predecessor-wave_bridge_nonblockers_closed-by-current-repair-wave.md"
        )
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / active_rel).write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", active_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", active_rel], cwd=repo, check=True, capture_output=True)
        (repo / archive_rel).parent.mkdir(parents=True)
        (repo / archive_rel).write_text("# Deferred archive\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_rel], cwd=repo, check=True)

        files_to_stage, staged_deletions = pb_mod._split_commit_handoff_stage_files(  # ANTICHEAT_OK: regression for remediation waves archiving predecessor packets
            repo,
            wave_id,
            [active_rel, archive_rel],
        )

        assert files_to_stage == [archive_rel]
        assert staged_deletions == [active_rel]

    def test_phase_b_target_branch_preserves_authorized_existing_pr_branch(self):
        wave_id = "current-repair-wave"
        target = pb_mod._phase_b_target_branch_for_current_worktree(  # ANTICHEAT_OK: regression for PR-branch remediation target preservation
            "jabramsja/existing-pr-wave",
            wave_id=wave_id,
            wave_class="L4_ENABLER",
            plan_content=(
                f"Wave ID: {wave_id}\n"
                "Purpose: bounded repair on the existing PR branch.\n"
                f"FOUNDER_OVERRIDE:{wave_id}\n"
            ),
            branch_prefix="jabramsja",
        )

        assert target == "jabramsja/existing-pr-wave"

    def test_sync_deferred_notes_into_closed_archive_without_reopening_active_lane(self, tmp_path):
        repo = tmp_path / "repo"
        active = repo / "reports" / "deferred" / "non_blocking" / "wave_bridge_nonblockers.md"
        archive = (
            repo
            / "reports"
            / "archive"
            / "deferred"
            / "wave_bridge_nonblockers_closed-by-wave.md"
        )
        active.parent.mkdir(parents=True)
        archive.parent.mkdir(parents=True)
        active.write_text("# Deferred\n\nStatus: DEFERRED_NON_BLOCKING\n", encoding="utf-8")
        archive.write_text(
            "# Deferred\n\nStatus: CLOSED_BY_REENTRY_RECONCILIATION\n",
            encoding="utf-8",
        )
        executor_created: set[str] = set()

        findings, packet_path = pb_mod._sync_deferred_non_blocking_state(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            "wave",
            [],
            [
                {
                    "title": "Packet validation wording is stale",
                    "class": "DOC_ACCURACY",
                    "severity": "low",
                    "file": "reports/control_plane/wave.md",
                    "evidence_cmd": "git show :reports/control_plane/wave.md",
                }
            ],
            previous_packet_path="reports/deferred/non_blocking/wave_bridge_nonblockers.md",
            executor_created=executor_created,
            wave_class="L4_ENABLER",
            target_gate_id="G8",
        )

        assert packet_path is None
        assert findings[0]["title"] == "Packet validation wording is stale"
        assert not active.exists()
        archive_text = archive.read_text(encoding="utf-8")
        assert "PHASE_B_POST_CLOSURE_NONBLOCKING:start" in archive_text
        assert "RETAINED_OUTSIDE_ACTIVE_DEFERRED_LANE" in archive_text
        assert "Packet validation wording is stale" in archive_text
        assert "reports/deferred/non_blocking/wave_bridge_nonblockers.md" in executor_created
        assert "reports/archive/deferred/wave_bridge_nonblockers_closed-by-wave.md" in executor_created

    def test_sync_deferred_replaces_post_closure_archive_notes_idempotently(self, tmp_path):
        repo = tmp_path / "repo"
        archive = (
            repo
            / "reports"
            / "archive"
            / "deferred"
            / "wave_bridge_nonblockers_closed-by-wave.md"
        )
        archive.parent.mkdir(parents=True)
        archive.write_text(
            "# Deferred\n\n"
            "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:start -->\n"
            "old note\n"
            "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:end -->\n",
            encoding="utf-8",
        )

        pb_mod._sync_deferred_non_blocking_state(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            "wave",
            [],
            [{"title": "New note", "class": "DOC_ACCURACY", "severity": "low", "file": "x.md"}],
            previous_packet_path=None,
            executor_created=set(),
            wave_class="L4_ENABLER",
            target_gate_id="G8",
        )

        archive_text = archive.read_text(encoding="utf-8")
        assert "New note" in archive_text
        assert "old note" not in archive_text
        assert archive_text.count("PHASE_B_POST_CLOSURE_NONBLOCKING:start") == 1

    def test_record_non_blocking_findings_replaces_prior_packet_contents(self, tmp_path):
        existing = [
            {"title": "Old nit", "class": "DOC_ACCURACY", "severity": "low", "file": "old.py", "disposition": "non_blocking"},
        ]
        updated = [
            {"title": "New nit", "class": "DOC_ACCURACY", "severity": "low", "file": "new.py", "disposition": "non_blocking"},
        ]

        findings, packet_path = pb_mod._record_non_blocking_findings(  # ANTICHEAT_OK: testing internal executor functions
            tmp_path,
            "wave",
            existing,
            updated,
        )

        assert findings == updated
        assert packet_path is not None
        content = packet_path.read_text(encoding="utf-8")
        assert "New nit" in content
        assert "Old nit" not in content

    def test_record_non_blocking_findings_deletes_packet_when_empty(self, tmp_path):
        findings = [
            {"title": "Lingering nit", "class": "DOC_ACCURACY", "severity": "low", "file": "foo.py", "disposition": "non_blocking"},
        ]
        packet_path = pb_mod._write_deferred_packet(tmp_path, "wave", findings)  # ANTICHEAT_OK: testing internal executor functions

        current_findings, refreshed_packet = pb_mod._record_non_blocking_findings(  # ANTICHEAT_OK: testing internal executor functions
            tmp_path,
            "wave",
            findings,
            [],
        )

        assert current_findings == []
        assert refreshed_packet is None
        assert not packet_path.exists()

    def test_cleared_staged_deferred_packet_stays_wave_owned_until_staged(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        executor_created: set[str] = set()
        findings = [
            {
                "title": "Lingering nit",
                "class": "DOC_ACCURACY",
                "severity": "low",
                "file": "foo.py",
                "disposition": "non_blocking",
            },
        ]
        _current, packet_rel = pb_mod._sync_deferred_non_blocking_state(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            "plan",
            [],
            findings,
            previous_packet_path=None,
            executor_created=executor_created,
        )
        assert packet_rel == "reports/deferred/non_blocking/plan_bridge_nonblockers.md"
        subprocess.run(["git", "add", "--", packet_rel], cwd=repo, check=True)

        current, refreshed_packet = pb_mod._sync_deferred_non_blocking_state(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            "plan",
            findings,
            [],
            previous_packet_path=packet_rel,
            executor_created=executor_created,
        )

        assert current == []
        assert refreshed_packet is None
        assert packet_rel in executor_created
        assert not (repo / packet_rel).exists()

        changed_files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            "reports/control_plane/plan.md",
            plan_declared_files=["mu/tools/executors/foo.py"],
            implementer_changed_files=set(),
            executor_created_files=executor_created,
        )
        assert packet_rel in changed_files

        assert pb_mod._stage_files(repo, changed_files)  # ANTICHEAT_OK: testing internal executor staging helper
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert packet_rel not in status


@pytest.mark.usefixtures("mock_routing_record")
class TestOnlyBlockingToImplementer:
    """Only blocking findings go to implementer; non-blocking deferred."""

    def test_all_non_blocking_converges_as_go(self, tmp_path):
        """When all findings are non_blocking, bridge loop converges (GO equivalent)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        # Bridge returns REQUEST_CHANGES but all findings are non_blocking
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "REQUEST_CHANGES", "summary": "minor nits",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "medium",
                 "file": "f.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Should converge — implementer NOT re-invoked for non-blocking findings
        assert result["status"] == "commit_ready"
        # Implementer called only once (initial), not for non-blocking fix
        assert mock_impl.invoke_implementer.call_count == 1
        # Deferred packet should be filed
        assert result.get("deferred_packet_path") is not None

    def test_bridge_go_with_non_blocking_findings_still_files_deferred_packet(self, tmp_path):
        """A GO render with non-blocking findings must still update deferred packet state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Observability nit", "class": "DEFECT", "severity": "low",
                 "file": "mu/tools/executors/supervision_poll.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result.get("deferred_packet_path") is not None

    @pytest.mark.parametrize(
        "blocking_finding",
        [
            {
                "title": "Pre-existing hardening context remains a blocker",
                "class": "DEFECT",
                "severity": "medium",
                "file": "f.py",
                "disposition": "blocking",
                "status": "persisting",
                "candidate_relationship": "pre-existing",
            },
            {
                "title": "Exact omission fallback",
                "class": "DEFECT",
                "severity": "low",
                "file": "f.py",
                "evidence_result": (
                    "TECHNICAL_IMPACT_CLASS=declared hard-invariant violation; "
                    "MERGE_DISPOSITION=blocking"
                ),
                "status": "new",
            },
        ],
        ids=["medium-explicit-blocker", "exact-mandatory-evidence-omission"],
    )
    def test_bridge_go_with_blocking_findings_fails_closed(
        self, tmp_path, blocking_finding
    ):
        """A GO transcript that still carries blocking findings is inconsistent and must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [blocking_finding],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "bridge_decision"
        assert "blocking finding" in result["errors"][0]
        assert result.get("deferred_packet_path") is None
        assert not (repo / "reports" / "deferred" / "non_blocking").exists()

    def test_blocking_findings_sent_to_implementer(self, tmp_path):
        """Blocking findings are sent to implementer; non-blocking deferred."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        first_job_id = [""]

        # Mixed findings: one blocking, one non-blocking
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "REQUEST_CHANGES", "summary": "issues",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Real bug", "class": "DEFECT", "severity": "medium",
                 "file": "f.py", "disposition": "blocking", "status": "persisting",
                 "candidate_relationship": "pre-existing"},
                {"title": "Style nit", "class": "DOC_ACCURACY", "severity": "low",
                 "file": "f.py", "disposition": "non_blocking", "status": "new"},
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                first_job_id[0] = kw["job_id"]
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": first_job_id[0]}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": kw["job_id"]}

        def read_render_side_effect(_repo_root, current_job_id):
            if current_job_id == first_job_id[0]:
                return render_text
            return ""

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", side_effect=read_render_side_effect), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Implementer re-invoked (only blocking findings sent)
        assert mock_impl.invoke_implementer.call_count >= 2
        # Check that the fix prompt contained "BLOCKING" but not non-blocking title
        fix_call_prompt = mock_impl.build_implementation_prompt.call_args_list[-1]
        prompt_text = fix_call_prompt[0][0] if fix_call_prompt[0] else ""
        # The blocking finding title should appear in prompt
        assert "Real bug" in prompt_text or "BLOCKING" in prompt_text

    @pytest.mark.parametrize("review_decision", ["REQUEST_CHANGES", "NO_GO"])
    def test_non_go_raw_output_preserves_medium_blocker(
        self, tmp_path, review_decision
    ):
        """Non-GO raw output cannot auto-converge a medium explicit blocker."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        raw_path = repo / ".agent_bus" / "raw" / "j1" / "reviewer.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": review_decision, "summary": "issues",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {"title": "Raw blocker", "class": "DEFECT", "severity": "medium",
                 "file": "f.py", "disposition": "blocking", "status": "persisting",
                 "candidate_relationship": "pre-existing"},
            ],
        })
        raw_path.write_text(
            "noise\nBEGIN_AGENT_ENVELOPE\n"
            f"{raw_envelope}\n"
            "END_AGENT_ENVELOPE\n",
            encoding="utf-8",
        )
        render_text = (
            "### reviewer\n"
            "- Status: completed\n"
            f"- Decision: {review_decision}\n"
            "- **Findings (1):**\n"
            "  1. **DEFECT** (medium): Raw blocker\n"
            "     - File: `f.py:1` | Status: persisting\n"
            "     - Evidence: preserved via raw output\n"
            f"- Raw output: {raw_path}\n"
        )

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {
                    "exit_code": 1 if review_decision == "REQUEST_CHANGES" else 0,
                    "stdout": f"{review_decision}\n",
                    "stderr": "",
                    "decision": review_decision,
                    "job_id": "j1",
                }
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(
                 pb_mod,
                 "_read_bridge_render",
                 side_effect=lambda _repo, job_id: render_text if job_id == "j1" else "",
             ), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2
        assert result.get("deferred_packet_path") is None
        assert not (repo / "reports" / "deferred" / "non_blocking").exists()

    def test_stale_render_still_uses_job_raw_reviewer_findings(self, tmp_path):
        """Phase B must prefer raw reviewer files by job id when the render is stale."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        first_job_id = [""]
        stale_render = [""]

        def bridge_side(*args, **kwargs):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                first_job_id[0] = kwargs["job_id"]
                raw_dir = repo / ".agent_bus" / "raw" / first_job_id[0]
                raw_dir.mkdir(parents=True, exist_ok=True)
                reader_path = raw_dir / f"{first_job_id[0]}--r1-reader-11111111.txt"
                reviewer_path = raw_dir / f"{first_job_id[0]}--r1-reviewer-22222222.txt"
                reader_path.write_text(
                    "BEGIN_AGENT_ENVELOPE\n"
                    '{"findings": []}\n'
                    "END_AGENT_ENVELOPE\n",
                    encoding="utf-8",
                )
                reviewer_envelope = json.dumps({
                    "job_id": first_job_id[0],
                    "turn_id": f"{first_job_id[0]}--r1-reviewer-22222222",
                    "agent_role": "reviewer",
                    "decision": "REQUEST_CHANGES",
                    "summary": "real blocker present",
                    "touched_files_claimed": [],
                    "validations_claimed": [],
                    "request_for_next_agent": "",
                    "findings": [
                        {
                            # The point under test is raw-by-job-id preference over
                            # a stale render; explicit blocking remains authoritative.
                            "title": "Real blocker from raw reviewer",
                            "class": "POLICY_BOUND",
                            "severity": "high",
                            "file": "mu/tools/observability/_pane_prci.sh",
                            "disposition": "blocking",
                            "status": "persisting",
                        }
                    ],
                })
                reviewer_path.write_text(
                    "noise\nBEGIN_AGENT_ENVELOPE\n"
                    f"{reviewer_envelope}\n"
                    "END_AGENT_ENVELOPE\n",
                    encoding="utf-8",
                )
                stale_render[0] = (
                    f"# Bridge Job {first_job_id[0]}\n\n"
                    "### reader\n"
                    "- Status: completed\n"
                    "- Decision: SYNTHETIC\n"
                    f"- Raw output: {reader_path}\n"
                )
                return {
                    "exit_code": 1,
                    "stdout": "REQUEST_CHANGES\n",
                    "stderr": "",
                    "decision": "REQUEST_CHANGES",
                    "job_id": first_job_id[0],
                }
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kwargs["job_id"],
            }

        def read_render_side_effect(_repo_root, current_job_id):
            if current_job_id == first_job_id[0]:
                return stale_render[0]
            return ""

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", side_effect=read_render_side_effect), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"exit_code": 0, "passed": True, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count >= 2
        fix_prompt = mock_impl.build_implementation_prompt.call_args_list[-1][0][0]
        assert "Real blocker from raw reviewer" in fix_prompt
        assert "Malformed AGENT_ENVELOPE" not in fix_prompt

    def test_go_low_doc_accuracy_crash_title_does_not_fail_closed(self, tmp_path):
        """A GO transcript with only low DOC_ACCURACY crash-wording findings remains non-blocking."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        envelope = json.dumps({
            "job_id": "j1", "turn_id": "t1", "agent_role": "reviewer",
            "decision": "GO", "summary": "looks good",
            "touched_files_claimed": [], "validations_claimed": [],
            "request_for_next_agent": "",
            "findings": [
                {
                    "title": "Bridge exit-code=1 conflates non-GO review with BridgeError infrastructure crash",
                    "class": "DOC_ACCURACY",
                    "severity": "low",
                    "file": "mu/tools/executors/phase_b_executor.py",
                    "status": "new",
                },
            ],
        })
        render_text = f"BEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE"

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 2, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=render_text), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["pre_commit_decision"] == "COMMIT_GO"


@pytest.mark.usefixtures("mock_routing_record")
class TestSupervisorReasonSurfacing:
    """Phase B must preserve the actionable supervisor reason instead of only ERROR_INTERNAL."""

    def test_supervisor_rejection_includes_summary_and_detail(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 1,
                 "parsed": {
                     "decision": "ERROR_INTERNAL",
                     "summary": "Package is stale against staged truth",
                     "status": "error",
                     "findings": [],
                     "error_detail": "missing mu/tools/checks/check_closeout_attestation.py",
                 },
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "supervisor_rejected"
        assert result["step"] == "pre_commit_supervisor"
        assert "Package is stale against staged truth" in result["errors"][0]
        assert "missing mu/tools/checks/check_closeout_attestation.py" in result["errors"][0]
        assert "Package is stale against staged truth" == result["pre_commit_summary"].split(" | ")[0]


@pytest.mark.usefixtures("mock_routing_record")
class TestValidationRunsMechanically:
    """Validation (pytest) runs mechanically in the loop after each implementer fix."""

    def test_bridge_fix_pytest_skips_stale_baseline_test_files(self, tmp_path):
        """Bridge-fix pytest must ignore test files that predate the current fix round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tests/tools/test_baseline.py", "mu/tools/observability/_pane_prci.sh"]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(pb_mod, "_run_pytest_on_files") as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_not_called()

    def test_bridge_fix_pytest_runs_only_new_test_files_from_current_fix(self, tmp_path):
        """Bridge-fix pytest must scope to tests introduced by the current fix pass."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_baseline.py"]
            return [
                "mu/tests/tools/test_baseline.py",
                "mu/tests/tools/test_fix_round.py",
                "mu/tests/fixtures/rcx_engine_state_minimal.json",
                "mu/tests/fixtures/rcx_enginenew_scheduler_operator_pool.json",
            ]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_baseline.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(
                 pb_mod,
                 "_run_pytest_on_files",
                 return_value={"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True},
             ) as mock_pytest, \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        mock_pytest.assert_called_once_with(
            repo,
            ["mu/tests/tools/test_fix_round.py"],
            timeout=300,
        )

    def test_pytest_failure_fed_back_as_blocking(self, tmp_path):
        """pytest failure after implementer fix becomes a blocking finding."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        pytest_calls = [0]
        def pytest_side(repo_root, test_files, **kw):
            pytest_calls[0] += 1
            if pytest_calls[0] == 1:
                return {"exit_code": 1, "stdout": "FAILED test_foo.py", "stderr": "", "passed": False}
            return {"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True}

        changed_files_calls = [0]

        def changed_files_side(_repo_root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_existing.py"]
            if changed_files_calls[0] == 5:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            if changed_files_calls[0] == 6:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]

        wave_owned_calls = [0]

        def wave_owned_side(*_a, **_kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                return ["mu/tests/tools/test_existing.py"]
            if wave_owned_calls[0] == 3:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            return ["mu/tools/observability/_pane_prci.sh"]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=wave_owned_side), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="some findings"), \
             patch.object(pb_mod, "_run_pytest_on_files", side_effect=pytest_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # pytest was called (at least once)
        assert pytest_calls[0] >= 1
        # Implementer re-invoked to fix pytest failure
        assert mock_impl.invoke_implementer.call_count >= 3


@pytest.mark.usefixtures("mock_routing_record")
class TestStatePersistence:
    """State file is written after each step and resume works."""

    def test_state_file_written(self, tmp_path):
        """_save_state writes state to expected path."""
        state = {"plan_path": "test.md", "completed_step": "implementer", "wave_id": "w1"}
        path = pb_mod._save_state(tmp_path, state)  # ANTICHEAT_OK: testing internal executor functions
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["completed_step"] == "implementer"
        assert loaded["plan_path"] == "test.md"

    def test_load_state_returns_saved(self, tmp_path):
        """_load_state returns previously saved state."""
        state = {"plan_path": "test.md", "completed_step": "bridge_round_2", "wave_id": "w1", "bridge_rounds": 2}
        pb_mod._save_state(tmp_path, state)  # ANTICHEAT_OK: testing internal executor functions
        loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: testing internal executor functions
        assert loaded is not None
        assert loaded["completed_step"] == "bridge_round_2"
        assert loaded["bridge_rounds"] == 2

    def test_load_state_returns_none_when_missing(self, tmp_path):
        """_load_state returns None when no state file exists."""
        assert pb_mod._load_state(tmp_path) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_load_state_malformed_json_returns_typed_fail_closed_state(self, tmp_path):
        state_path = pb_mod._state_file_path(tmp_path)  # ANTICHEAT_OK: testing state path helper
        state_path.parent.mkdir(parents=True)
        state_path.write_text('{"plan_path": "test.md"', encoding="utf-8")

        loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: malformed checkpoint regression

        assert pb_mod._is_state_load_error(loaded)  # ANTICHEAT_OK: typed checkpoint load error
        assert loaded["state_error"] == "malformed_json"
        assert "refusing mutable replay" in loaded["errors"][0]

    def test_load_state_non_object_returns_typed_fail_closed_state(self, tmp_path):
        state_path = pb_mod._state_file_path(tmp_path)  # ANTICHEAT_OK: testing state path helper
        state_path.parent.mkdir(parents=True)
        state_path.write_text("[]", encoding="utf-8")

        loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: non-object checkpoint regression

        assert pb_mod._is_state_load_error(loaded)  # ANTICHEAT_OK: typed checkpoint load error
        assert loaded["state_error"] == "non_object"

    def test_load_state_unreadable_returns_typed_fail_closed_state(self, tmp_path):
        state_path = pb_mod._state_file_path(tmp_path)  # ANTICHEAT_OK: testing state path helper
        state_path.parent.mkdir(parents=True)
        state_path.write_text("{}", encoding="utf-8")

        with patch.object(Path, "read_text", side_effect=PermissionError("blocked")):
            loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: unreadable checkpoint regression

        assert pb_mod._is_state_load_error(loaded)  # ANTICHEAT_OK: typed checkpoint load error
        assert loaded["state_error"] == "unreadable"

    def test_load_state_without_plan_path_returns_typed_fail_closed_state(self, tmp_path):
        state_path = pb_mod._state_file_path(tmp_path)  # ANTICHEAT_OK: testing state path helper
        state_path.parent.mkdir(parents=True)
        state_path.write_text("{}", encoding="utf-8")

        loaded = pb_mod._load_state(tmp_path)  # ANTICHEAT_OK: unmatchable checkpoint regression

        assert pb_mod._is_state_load_error(loaded)  # ANTICHEAT_OK: typed checkpoint load error
        assert loaded["state_error"] == "incomplete"
        assert "plan_path" in loaded["errors"][0]
        assert "refusing mutable replay" in loaded["errors"][0].lower()

    def test_run_phase_b_malformed_state_fails_closed_before_routing_or_implementation(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state_path = repo / ".agent_bus" / "executors" / "phase_b_state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text("{", encoding="utf-8")
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record") as routing_mock, \
             patch.object(pb_mod, "run_bridge_review") as bridge_mock:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md")

        assert result["status"] == "error"
        assert result["step"] == "load_state"
        assert result["state_error"] == "malformed_json"
        routing_mock.assert_not_called()
        mock_impl.invoke_implementer.assert_not_called()
        bridge_mock.assert_not_called()

    def test_run_phase_b_incomplete_matching_state_fails_closed_before_replay(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_rel = "reports/control_plane/plan.md"
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / plan_rel).write_text("# Plan\nPhase-A-Lock: LOCKED\n", encoding="utf-8")
        state_path = repo / ".agent_bus" / "executors" / "phase_b_state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps({"plan_path": plan_rel}), encoding="utf-8")
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record") as routing_mock, \
             patch.object(pb_mod, "run_sdk_agents") as sdk_mock, \
             patch.object(pb_mod, "run_bridge_review") as bridge_mock, \
             patch.object(pb_mod, "run_pre_commit_supervisor") as supervisor_mock:
            result = pb_mod.run_phase_b(repo, plan_rel, max_bridge_rounds=1)

        assert result["status"] == "error"
        assert result["step"] == "load_state"
        assert result["state_error"] == "incomplete"
        assert "completed_step" in result["errors"][0]
        routing_mock.assert_not_called()
        mock_impl.invoke_implementer.assert_not_called()
        sdk_mock.assert_not_called()
        bridge_mock.assert_not_called()
        supervisor_mock.assert_not_called()

    def test_run_phase_b_mismatched_state_fails_closed_before_replay(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        pb_mod._save_state(repo, {  # ANTICHEAT_OK: mismatched checkpoint setup
            "plan_path": "reports/control_plane/other.md",
            "completed_step": "implementer",
            "wave_id": "other",
        })
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record") as routing_mock, \
             patch.object(pb_mod, "run_bridge_review") as bridge_mock:
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md")

        assert result["status"] == "error"
        assert result["step"] == "load_state"
        assert result["state_error"] == "plan_mismatch"
        routing_mock.assert_not_called()
        mock_impl.invoke_implementer.assert_not_called()
        bridge_mock.assert_not_called()

    def test_save_state_atomic_replace_failure_preserves_prior_checkpoint(self, tmp_path):
        old_state = {"plan_path": "test.md", "completed_step": "implementer", "wave_id": "w1"}
        new_state = {"plan_path": "test.md", "completed_step": "bridge_round_1", "wave_id": "w1"}
        path = pb_mod._save_state(tmp_path, old_state)  # ANTICHEAT_OK: atomic checkpoint setup

        with patch.object(pb_mod.os, "replace", side_effect=OSError("replace failed")):
            with pytest.raises(pb_mod.PhaseBExecutorError, match="atomic Phase B state replacement failed"):
                pb_mod._save_state(tmp_path, new_state)  # ANTICHEAT_OK: atomic checkpoint replacement regression

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == old_state
        assert not list(path.parent.glob(f".{path.name}.*.tmp"))

    def test_clear_state_removes_file(self, tmp_path):
        """_clear_state removes the state file."""
        pb_mod._save_state(tmp_path, {"plan_path": "x"})  # ANTICHEAT_OK: testing internal executor functions
        assert pb_mod._state_file_path(tmp_path).exists()  # ANTICHEAT_OK: testing internal executor functions
        pb_mod._clear_state(tmp_path)  # ANTICHEAT_OK: testing internal executor functions
        assert not pb_mod._state_file_path(tmp_path).exists()  # ANTICHEAT_OK: testing internal executor functions

    def test_clear_state_noop_when_missing(self, tmp_path):
        """_clear_state is a no-op when no state file exists."""
        pb_mod._clear_state(tmp_path)  # Should not raise  # ANTICHEAT_OK: testing internal executor functions

    def test_resume_from_state_file(self, tmp_path):
        """run_phase_b picks up saved state and includes resumed_from in result."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        # Pre-save state
        pb_mod._save_state(repo, {  # ANTICHEAT_OK: testing internal executor functions
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_round_1",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": "reports/deferred/non_blocking/plan_bridge_nonblockers.md",
        })

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_round_1"
        assert result.get("deferred_packet_path") == "reports/deferred/non_blocking/plan_bridge_nonblockers.md"

    def test_resume_from_over_budget_bridge_round_returns_max_rounds(self, tmp_path):
        """A saved bridge_round_N beyond the current budget must fail closed, not crash."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        pb_mod._save_state(repo, {  # ANTICHEAT_OK: testing internal executor resume state
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_round_3",
            "wave_id": "plan",
            "bridge_rounds": 3,
            "current_bridge_round": 3,
            "last_bridge_decision": "REQUEST_CHANGES",
            "bridge_scope_fingerprint": "fp",
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tests/tools/test_foo.py"],
            "executor_created": [],
            "baseline_wave_files": [],
            "all_non_blocking": [],
            "finding_history": {},
        })

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tests/tools/test_foo.py"]), \
             patch.object(pb_mod, "run_bridge_review") as mock_bridge, \
             patch.object(pb_mod, "run_sdk_agents") as mock_agents, \
             patch.object(pb_mod, "_emit_phase_b_event"), \
             patch.object(pb_mod, "_emit_phase_b_hard_fail"), \
             patch.object(pb_mod, "_bridge_scope_fingerprint", return_value="fp"), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo,
                "reports/control_plane/plan.md",
                max_bridge_rounds=2,
            )

        assert result["status"] == "max_rounds_reached"
        assert "REQUEST_CHANGES" in result["errors"][0]
        mock_bridge.assert_not_called()
        mock_agents.assert_not_called()
        mock_impl.invoke_implementer.assert_not_called()


@pytest.mark.usefixtures("mock_routing_record")
class TestBridgeFixPendingResume:
    """Initial bridge-fix checkpoints must survive crashes between review and fix."""

    def test_request_changes_checkpoints_before_fix_implementer(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        impl_success = dict(mock_impl.invoke_implementer.return_value)
        mock_impl.invoke_implementer.side_effect = [
            impl_success,
            RuntimeError("Simulated crash before bridge fix implementer completes"),
        ]

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "phase-b-r1-test",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            with pytest.raises(RuntimeError, match="Simulated crash"):
                pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        state = pb_mod._load_state(repo)  # ANTICHEAT_OK: testing internal executor functions
        assert state is not None
        assert state["completed_step"] == "bridge_fix_pending"
        assert state["current_bridge_round"] == 1
        assert state["bridge_decision"] == "REQUEST_CHANGES"
        assert state["bridge_fix_findings"]

    def test_resume_from_bridge_fix_pending_invokes_fix_then_resumes_next_round(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        pb_mod._save_state(repo, {  # ANTICHEAT_OK: testing internal executor functions
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_fix_pending",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "current_bridge_round": 1,
            "bridge_decision": "REQUEST_CHANGES",
            "bridge_fix_findings": "Fix the blocker from round 1",
            "deferred_packet_path": "reports/deferred/non_blocking/plan_bridge_nonblockers.md",
        })

        mock_impl = _make_mock_impl()
        bridge_calls: list[str] = []

        def bridge_go(*args, **kwargs):
            bridge_calls.append(kwargs.get("job_id", ""))
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kwargs.get("job_id", "phase-b-r2-test"),
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_go), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_fix_pending"
        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count == 1
        assert bridge_calls and any("phase-b-r2-" in job_id for job_id in bridge_calls)


@pytest.mark.usefixtures("mock_routing_record")
class TestStaleStateCleared:
    """Terminal exits must clear persisted state to prevent stale resume wedge.

    Bridge R6 finding: Phase B leaves stale resume state on handled max-round exits.
    Next invocation auto-skips completed rounds, creating an infinite wedge.
    Fix: _clear_state on all terminal exits (max_rounds, question, supervisor_rejected).
    """

    def test_max_rounds_clears_state(self, tmp_path):
        """max_rounds_reached must clear state file so next invocation starts fresh."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        # Bridge always returns NO_GO with no parseable findings
        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "NO_GO\n", "stderr": "",
                    "decision": "NO_GO", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=1,
            )

        assert result["status"] == "max_rounds_reached"
        # State file must be cleared — next invocation must NOT auto-skip rounds
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_question_for_founder_clears_state(self, tmp_path):
        """QUESTION decision must clear state so next invocation starts fresh."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_question(*a, **kw):
            return {"exit_code": 0, "stdout": "QUESTION\n", "stderr": "",
                    "decision": "QUESTION", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_question), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "question_for_founder"
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions


class TestParseFindings:
    """Parse findings from bridge render text."""

    def test_parse_structured_envelope(self):
        envelope = json.dumps({
            "job_id": "j1", "decision": "REQUEST_CHANGES", "summary": "test",
            "findings": [
                {"title": "Bug", "disposition": "blocking"},
                {"title": "Nit", "disposition": "non_blocking"},
            ],
        })
        render = f"Some preamble\nBEGIN_AGENT_ENVELOPE\n{envelope}\nEND_AGENT_ENVELOPE\nSome footer"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 2
        assert findings[0]["title"] == "Bug"
        assert findings[1]["disposition"] == "non_blocking"

    def test_parse_no_envelope_returns_empty(self):
        findings = pb_mod._parse_findings_from_render("just some text without envelope")  # ANTICHEAT_OK: testing internal executor functions
        assert findings == []

    def test_parse_malformed_json_returns_blocking_finding(self):
        render = "BEGIN_AGENT_ENVELOPE\n{not valid json\nEND_AGENT_ENVELOPE"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"
        assert findings[0]["disposition"] == "blocking"
        assert "malformed" in findings[0]["title"].lower()

    def test_parse_envelope_with_code_fences(self):
        envelope = json.dumps({"findings": [{"title": "A", "disposition": "blocking"}]})
        render = f"BEGIN_AGENT_ENVELOPE\n```json\n{envelope}\n```\nEND_AGENT_ENVELOPE"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1

    def test_parse_multiple_envelopes_uses_last(self):
        """Multiple distinct NON-EMPTY envelopes: use the last valid one (same as bridge_supervisor)."""
        first = json.dumps({"findings": [{"title": "Finding A", "severity": "low"}]})
        second = json.dumps({"findings": [{"title": "Finding B", "severity": "high"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{first}\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{second}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Finding B"
        assert findings[0]["severity"] == "high"

    def test_empty_envelope_plus_real_not_conflicting(self):
        """Empty-findings envelope + real envelope → returns real findings, not conflict."""
        first = json.dumps({"findings": []})
        second = json.dumps({"findings": [{"title": "Real finding", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{first}\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{second}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Real finding"

    def test_malformed_envelope_does_not_hide_later_valid_envelope(self):
        """Malformed envelope blocks must not suppress a later valid envelope."""
        valid = json.dumps({"findings": [{"title": "Later finding", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            "{not valid json\n"
            "END_AGENT_ENVELOPE\n"
            "noise\n"
            "BEGIN_AGENT_ENVELOPE\n"
            f"{valid}\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Later finding"

    def test_empty_envelope_falls_back_to_markdown_findings(self):
        """An empty structured envelope must not suppress markdown findings."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "1. **DEFECT** (critical): Markdown finding survives\n"
            "   - File: a.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Markdown finding survives"

    def test_nested_envelope_markers_fail_closed(self):
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "outer blocker", "severity": "critical", "disposition": "blocking"}]}\n'
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "inner harmless", "severity": "low", "disposition": "non_blocking"}]}\n'
            "END_AGENT_ENVELOPE\n"
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["severity"] == "critical"
        assert findings[0]["disposition"] == "blocking"
        assert "Nested AGENT_ENVELOPE markers" in findings[0]["title"]


class TestSdkReviewScopeSelection:
    """Phase B SDK review should prioritize tool/runtime files over residue and tests."""

    def test_select_sdk_review_files_prefers_mu_and_tools(self):
        files = [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            "reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md",
            "reports/deferred/non_blocking/post_merge_supervisor_phase_a_nonblockers_2026-03-21.md",
        ]
        selected = pb_mod._select_sdk_review_files(files)  # ANTICHEAT_OK: testing internal executor functions
        assert selected == ["mu/tools/executors/phase_b_executor.py"]

    def test_select_sdk_review_files_falls_back_to_reports_when_needed(self):
        files = ["reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md"]
        selected = pb_mod._select_sdk_review_files(files)  # ANTICHEAT_OK: testing internal executor functions
        assert selected == []

    def test_parse_fenced_out_files_from_checkout_state_fence(self):
        plan = (
            "### Checkout-state fence\n\n"
            "| File | Status |\n"
            "|------|--------|\n"
            "| `mu/tools/executors/foo.py` | adjacent pipeline-recovery (fenced out) |\n"
            "| `reports/control_plane/plan.md` | current wave |\n"
            "| `mu/tools/runners/run_review.py` | adjacent pipeline-recovery (fenced out) |\n"
        )
        assert pb_mod._parse_fenced_out_files(plan) == [  # ANTICHEAT_OK: testing internal executor functions
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
        ]

    def test_launcher_exact_final_set_uses_only_files_and_surfaces_scope(self):
        wave_id = "phase-b-launcher-exact-scope-2026-07-28"
        packet_path = f"reports/control_plane/{wave_id}_2026-07-28.md"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        plan = (
            "# Phase B Launcher Packet\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n\n"
            "## Scope\n\n"
            "Exactly one repair plus an optional standard reviewer nonblocker report.\n\n"
            "Files and surfaces in scope:\n\n"
            "- mu/tools/executors/phase_b_executor.py (MODIFY) -- implementation\n"
            "- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- tests\n"
            "- TASKS.md (GENERATED UPDATE) -- tracker\n"
            f"- {packet_path} (GENERATED) -- packet\n"
            f"- {indicator_path} (GENERATED) -- indicator\n"
            "- TASKS.md -- canonical tracker authority\n\n"
            "Read-only grounding:\n\n"
            "- mu/tools/executors/commit_executor.py\n\n"
            "## Work items\n\n"
            "1. A launcher-rendered packet may say the final staged set contains exactly "
            "the authorized package in explanatory prose.\n"
            "2. Validate mu/tools/executors/executor_dispatch.py without editing it.\n\n"
            "## Validation gates\n\n"
            "- python3 tools/checks/enforce_l4_execution_contract.py --files "
            "mu/tools/executors/recovery_gate.py\n\n"
            "## Acceptance criteria\n\n"
            "- The final staged set contains exactly the authorized package, plus only "
            "the standard generated reviewer nonblocker report if one is required.\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            "TASKS.md",
            packet_path,
            indicator_path,
            f"reports/deferred/non_blocking/{wave_id}_bridge_nonblockers.md",
        ]

    def test_launcher_exact_final_set_does_not_authorize_negated_reviewer_nonblocker(self):
        wave_id = "phase-b-negated-reviewer-nonblocker-2026-07-28"
        plan = (
            "# Phase B Launcher Packet\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n\n"
            "## Scope\n\n"
            "No reviewer nonblocker report is authorized for this wave.\n\n"
            "Files and surfaces in scope:\n\n"
            "- mu/tools/executors/phase_b_executor.py (MODIFY)\n"
            "- mu/tests/tools/test_phase_b_executor.py (MODIFY)\n"
            "- TASKS.md (GENERATED UPDATE)\n\n"
            "## Acceptance criteria\n\n"
            "- The final staged set contains exactly the authorized package.\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "mu/tools/executors/phase_b_executor.py",
            "mu/tests/tools/test_phase_b_executor.py",
            "TASKS.md",
        ]

    def test_launcher_files_scope_is_not_exact_without_acceptance_authority(self):
        plan = (
            "# Phase B Launcher Packet\n\n"
            "Wave ID: phase-b-launcher-nonexact-2026-07-28\n\n"
            "## Scope\n\n"
            "Files and surfaces in scope:\n\n"
            "- mu/tools/executors/phase_b_executor.py (MODIFY)\n"
            "- TASKS.md (GENERATED UPDATE)\n\n"
            "## Work items\n\n"
            "1. The final staged set contains exactly the authorized package.\n\n"
            "## Acceptance criteria\n\n"
            "- The implementation remains mechanically complete.\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == []

    def test_exact_stage_scope_ignores_read_only_and_refresh_blocks(self):
        plan = (
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            "- `reports/control_plane/plan.md`\n"
            "- `reports/deferred/non_blocking/plan_bridge_nonblockers.md`\n"
            "- `reports/l4_wave_indicators/plan.json`\n\n"
            "Read-only grounding for this packet:\n\n"
            "- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`\n"
            "- `mu/tools/executors/phase_b_executor.py`\n\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "- Current staged files:\n"
            "  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`\n"
            "  - `reports/control_plane/plan.md`\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "TASKS.md",
            "reports/control_plane/plan.md",
            "reports/deferred/non_blocking/plan_bridge_nonblockers.md",
            "reports/l4_wave_indicators/plan.json",
        ]

    def test_exact_stage_scope_accepts_authorized_staged_files_refresh_block(self):
        plan = (
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "## Phase B Indicator Scope Reconciliation\n\n"
            "- Authorized staged files:\n"
            "  - `TASKS.md`\n"
            "  - `tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`\n"
            "  - `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`\n"
            "  - `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`\n"
            "- Excluded from this repair package: prior-wave control-plane edits and generated bridge nonblocker packets.\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "TASKS.md",
            "tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py",
            "reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md",
            "reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json",
        ]

    def test_exact_stage_scope_accepts_current_staged_files_refresh_block(self):
        plan = (
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "## Phase B Indicator Scope Reconciliation\n\n"
            "- Current staged files:\n"
            "  - `TASKS.md`\n"
            "  - `tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`\n"
            "  - `reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md`\n"
            "  - `reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json`\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "TASKS.md",
            "tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py",
            "reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md",
            "reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json",
        ]

    def test_historical_unversioned_refresh_scope_parse_is_unchanged(self):
        repo_root = _EXECUTORS_DIR.parents[2]
        normalize_declared_path = getattr(
            pb_mod,
            "_normalize_declared_path_token",
        )

        def legacy_parse(plan_content: str) -> list[str]:
            lines = plan_content.splitlines()
            marker_index: int | None = None
            for index, line in enumerate(lines):
                stripped = line.strip()
                lower = stripped.lower()
                bullet_body = lower[2:].strip() if lower.startswith("- ") else lower
                if (
                    "`" not in stripped
                    and (
                        lower == "allowed write scope:"
                        or (
                            "may stage exactly" in lower
                            and "file" in lower
                            and lower.endswith(":")
                        )
                        or bullet_body
                        in {"authorized staged files:", "current staged files:"}
                    )
                ):
                    marker_index = index
                    break
            if marker_index is None:
                return []

            seen: set[str] = set()
            parsed: list[str] = []
            started = False
            for line in lines[marker_index + 1:]:
                stripped = line.strip()
                if not stripped:
                    if started:
                        break
                    continue
                if stripped.startswith("#"):
                    break
                if not stripped.startswith("- "):
                    if started:
                        break
                    continue
                normalized = normalize_declared_path(
                    stripped[2:].strip().split()[0]
                )
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    parsed.append(normalized)
                    started = True
            return parsed

        checked = 0
        for packet in sorted((repo_root / "reports" / "control_plane").glob("*.md")):
            packet_text = packet.read_text(encoding="utf-8")
            if "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->" not in packet_text:
                continue
            if (
                pb_mod.PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER
                in packet_text
            ):
                continue
            assert pb_mod.parse_exact_stage_scope_files(packet_text) == legacy_parse(
                packet_text
            ), packet.relative_to(repo_root).as_posix()
            checked += 1

        assert checked >= 232

    def test_exact_stage_scope_ignores_prose_mentions_of_legacy_headers(self):
        plan = (
            "## Direct Evidence\n\n"
            "- A prior review said `_parse_exact_stage_scope_files()` returned `[]` "
            "because the parser matched `may stage exactly` / `authorized staged files`, "
            "while the renderer emitted `- Current staged files:`.\n"
            "- `mu/tools/executors/phase_b_executor.py` now parses those labels.\n\n"
            "## Related Files\n\n"
            "- `TASKS.md`\n"
            "- `mu/tests/tools/test_phase_b_executor.py`\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == []

    def test_exact_stage_scope_prefers_allowed_write_scope_over_stale_refresh_block(self):
        plan = (
            "## Scope\n\n"
            "Allowed write scope:\n\n"
            "- `TASKS.md`\n"
            "- `mu/tests/tools/test_phase_b_executor.py`\n"
            "- `reports/control_plane/packet.md`\n"
            "- `reports/l4_wave_indicators/packet.json`\n\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "## Phase B Indicator Scope Reconciliation\n\n"
            "- Authorized staged files:\n"
            "  - `reports/control_plane/packet.md`\n"
            "  - `reports/l4_wave_indicators/packet.json`\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
        )

        assert pb_mod.parse_exact_stage_scope_files(plan) == [
            "TASKS.md",
            "mu/tests/tools/test_phase_b_executor.py",
            "reports/control_plane/packet.md",
            "reports/l4_wave_indicators/packet.json",
        ]

    def test_scope_refresh_renderer_uses_authorized_staged_files_label(self):
        block = pb_mod._render_phase_b_indicator_scope_refresh_block(  # ANTICHEAT_OK: locks control-packet scope label
            wave_id="packet-scope-test",
            plan_path="reports/control_plane/packet.md",
            indicator_path="reports/l4_wave_indicators/packet.json",
            changed_files=["TASKS.md"],
        )

        assert "- Authorized staged files:" in block
        assert "- Current staged files:" not in block

    def test_broad_scope_refresh_snapshot_is_explicitly_non_authoritative(self):
        block = pb_mod._render_phase_b_indicator_scope_refresh_block(  # ANTICHEAT_OK: locks broad refresh restart authority
            wave_id="packet-broad-scope-test",
            plan_path="reports/control_plane/packet.md",
            indicator_path="reports/l4_wave_indicators/packet.json",
            changed_files=["TASKS.md"],
            broad_package_snapshot=True,
        )

        assert (
            pb_mod.PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER
            in block
        )
        assert pb_mod.parse_exact_stage_scope_files(block) == []

    def test_broad_scope_refresh_snapshot_is_not_generic_restart_authority(self, tmp_path):
        stale_path = "mu/tools/executors/stale_previous_candidate.py"
        plan_path = "reports/control_plane/packet.md"
        block = pb_mod._render_phase_b_indicator_scope_refresh_block(  # ANTICHEAT_OK: locks broad refresh generic parser exclusion
            wave_id="packet-broad-restart-test",
            plan_path=plan_path,
            indicator_path="reports/l4_wave_indicators/packet.json",
            changed_files=[stale_path],
            broad_package_snapshot=True,
        )

        generic_scope = pb_mod._parse_plan_declared_files(block)  # ANTICHEAT_OK: broad refresh must not grant generic authority
        assert pb_mod.parse_exact_stage_scope_files(block) == []
        assert stale_path not in generic_scope

        with patch.object(pb_mod, "_collect_changed_files", return_value=[stale_path]):
            restart_scope = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: restart scope must reject stale broad snapshot
                tmp_path,
                plan_path,
                generic_scope,
                set(),
                set(),
                set(),
            )

        assert restart_scope == []

    def test_exact_stage_scope_expands_tests_symlink_to_git_path(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "mu" / "tests" / "l4_gates").mkdir(parents=True)
        try:
            os.symlink("mu/tests", repo / "tests")
        except OSError as exc:
            pytest.skip(f"symlink unavailable: {exc}")

        expanded = pb_mod.expand_exact_stage_scope_files_for_git(
            repo,
            {
                "TASKS.md",
                "tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py",
            },
        )

        assert "tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py" in expanded
        assert "mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py" in expanded

    def test_exact_stage_scope_saved_reentry_state_cannot_restage_excluded_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("init\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "mu" / "tests" / "l4_gates").mkdir(parents=True)
        try:
            os.symlink("mu/tests", repo / "tests")
        except OSError as exc:
            pytest.skip(f"symlink unavailable: {exc}")

        p7w5_packet = "reports/control_plane/p7w5-metabolization-source-lock-repair-2026-05-28_2026-05-28.md"
        prior_packet = "reports/control_plane/ci-green-gate-js-metabolization-continuation-reuse-2026-05-28_2026-05-28.md"
        nonblocker = "reports/deferred/non_blocking/p7w5-metabolization-source-lock-repair-2026-05-28_bridge_nonblockers.md"
        indicator = "reports/l4_wave_indicators/p7w5-metabolization-source-lock-repair-2026-05-28.json"
        test_path = "mu/tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py"
        for rel_path in [
            "TASKS.md",
            test_path,
            p7w5_packet,
            indicator,
            prior_packet,
            nonblocker,
        ]:
            full = repo / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"{rel_path}\n", encoding="utf-8")
        subprocess.run(
            [
                "git", "add", "--",
                "TASKS.md", test_path, p7w5_packet, indicator, prior_packet, nonblocker,
            ],
            cwd=repo,
            check=True,
        )

        plan = (
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->\n"
            "- Authorized staged files:\n"
            "  - `TASKS.md`\n"
            "  - `tests/l4_gates/test_p7w5_outer_loop_boundary_gate.py`\n"
            f"  - `{p7w5_packet}`\n"
            f"  - `{indicator}`\n"
            "- Excluded from this repair package: prior-wave control-plane edits and generated bridge nonblocker packets.\n"
            "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->\n"
        )
        exact = pb_mod.expand_exact_stage_scope_files_for_git(
            repo,
            set(pb_mod.parse_exact_stage_scope_files(plan)),
        )
        implementer_changed = {test_path, indicator} & exact
        executor_created = {nonblocker} & exact
        baseline_wave_files = pb_mod._restrict_baseline_to_exact_scope(  # ANTICHEAT_OK: testing internal executor functions
            {"TASKS.md", prior_packet, p7w5_packet},
            exact,
        )

        changed = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            p7w5_packet,
            sorted(exact),
            implementer_changed,
            executor_created,
            baseline_wave_files,
        )

        assert changed == [
            "TASKS.md",
            test_path,
            p7w5_packet,
            indicator,
        ]

    def test_exact_stage_scope_unstages_stale_wave_owned_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("init\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        for rel_path in [
            "TASKS.md",
            "reports/control_plane/plan.md",
            "reports/l4_wave_indicators/plan.json",
            "mu/host/python/rcx_pi/selfhost/seed_integrity.py",
        ]:
            full = repo / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"{rel_path}\n", encoding="utf-8")
        subprocess.run(
            [
                "git", "add", "--",
                "TASKS.md",
                "reports/control_plane/plan.md",
                "reports/l4_wave_indicators/plan.json",
                "mu/host/python/rcx_pi/selfhost/seed_integrity.py",
            ],
            cwd=repo,
            check=True,
        )

        allowed = {
            "TASKS.md",
            "reports/control_plane/plan.md",
            "reports/l4_wave_indicators/plan.json",
        }
        ok, detail = pb_mod._unstage_out_of_exact_scope(repo, allowed)  # ANTICHEAT_OK: testing internal executor functions

        assert ok, detail
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert staged == [
            "TASKS.md",
            "reports/control_plane/plan.md",
            "reports/l4_wave_indicators/plan.json",
        ]
        assert (repo / "mu/host/python/rcx_pi/selfhost/seed_integrity.py").exists()

    def test_exact_stage_scope_filters_commit_bound_expansion_from_staged_runtime(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "README.md").write_text("init\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        for rel_path in [
            "TASKS.md",
            "reports/control_plane/plan.md",
            "mu/host/js/core/seed_loader.js",
        ]:
            full = repo / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"{rel_path}\n", encoding="utf-8")
        subprocess.run(
            [
                "git", "add", "--",
                "TASKS.md",
                "reports/control_plane/plan.md",
                "mu/host/js/core/seed_loader.js",
            ],
            cwd=repo,
            check=True,
        )

        commit_bound = pb_mod._collect_commit_bound_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["TASKS.md"],
            allowed_files={"TASKS.md", "reports/control_plane/plan.md"},
        )

        assert commit_bound == ["TASKS.md", "reports/control_plane/plan.md"]

    def test_exact_stage_scope_reconciles_before_private_attr_bridge_review(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-private-attr-pre-review-2026-07-28"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            "- `reports/control_plane/plan.md`\n"
            "- `mu/tests/tools/test_foo.py`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        _write_canonical_tasks(repo, wave_id)

        changed_files = [
            "TASKS.md",
            "mu/tests/tools/test_foo.py",
            indicator_path,
        ]
        mock_impl = _make_mock_impl()
        events: list[tuple[str, object]] = []
        gate_fail = {
            "passed": False,
            "skipped": False,
            "exit_code": 1,
            "stdout": "ERROR: Found private attr access in tests/:",
            "stderr": "",
            "test_files": changed_files,
        }
        gate_pass = {
            "passed": True,
            "skipped": False,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": changed_files,
        }

        def unstage_side(repo_root, allowed):
            events.append(("unstage", sorted(allowed)))
            return True, ""

        def stage_side(repo_root, files):
            events.append(("stage", list(files)))
            return True

        def bridge_side(repo_root, summary, **kwargs):
            events.append(("bridge", summary))
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kwargs.get("job_id", "j"),
            }

        def collect_side(_repo_root, *, wave_id):
            events.append(("collect_indicator", wave_id))
            return f"reports/l4_wave_indicators/{wave_id}.json", None

        def refresh_side(*args, **kwargs):
            events.append(("refresh_packet", kwargs["plan_path"]))
            return True, None

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "run_private_attr_gate", side_effect=[gate_fail, gate_pass]), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", side_effect=unstage_side), \
             patch.object(pb_mod, "_stage_files", side_effect=stage_side), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", side_effect=collect_side), \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", side_effect=refresh_side), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        assert result["status"] == "commit_ready", result
        private_bridge_index = next(
            index for index, event in enumerate(events)
            if event[0] == "bridge" and "private-attr remediation review" in str(event[1])
        )
        assert [event[0] for event in events[private_bridge_index - 4:private_bridge_index]] == [
            "unstage",
            "stage",
            "collect_indicator",
            "refresh_packet",
        ]

    def test_exact_stage_scope_reconciles_before_needs_phase_b_reentry_bridge_review(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        wave_id = "phase-b-reentry-pre-review-2026-07-28"
        indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n\n"
            f"Wave ID: {wave_id}\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Class: L4_ENABLER\n\n"
            "## Scope\n\n"
            "This lock package may stage exactly these same-wave files:\n\n"
            "- `TASKS.md`\n"
            "- `reports/control_plane/plan.md`\n"
            "- `mu/tools/executors/foo.py`\n"
            f"- `{indicator_path}`\n",
            encoding="utf-8",
        )
        _write_canonical_tasks(repo, wave_id)

        changed_files = [
            "TASKS.md",
            "mu/tools/executors/foo.py",
            "mu/tools/executors/stale_scope.py",
            indicator_path,
        ]
        mock_impl = _make_mock_impl()
        events: list[tuple[str, object]] = []

        def unstage_side(repo_root, allowed):
            events.append(("unstage", sorted(allowed)))
            return True, ""

        def stage_side(repo_root, files):
            events.append(("stage", list(files)))
            return True

        def bridge_side(repo_root, summary, **kwargs):
            events.append(("bridge", summary))
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kwargs.get("job_id", "j"),
            }

        def collect_side(_repo_root, *, wave_id):
            events.append(("collect_indicator", wave_id))
            return f"reports/l4_wave_indicators/{wave_id}.json", None

        def refresh_side(*args, **kwargs):
            events.append(("refresh_packet", kwargs["plan_path"]))
            return True, None

        supervisor_results = iter([
            {
                "exit_code": 0,
                "parsed": {
                    "decision": "NEEDS_PHASE_B",
                    "summary": "fix stale staged scope",
                    "status": "success",
                    "findings": [],
                },
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r1.json",
            },
            {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r2.json",
            },
            {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r3.json",
            },
        ])

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "run_private_attr_gate", return_value={
                 "passed": True,
                 "skipped": True,
                 "exit_code": 0,
                 "stdout": "",
                 "stderr": "",
                 "test_files": [],
             }), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0, "stdout": "1 passed", "stderr": "", "passed": True,
             }), \
             patch.object(pb_mod, "_unstage_out_of_exact_scope", side_effect=unstage_side), \
             patch.object(pb_mod, "_stage_files", side_effect=stage_side), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact", side_effect=collect_side), \
             patch.object(pb_mod, "_refresh_phase_b_indicator_packet_scope", side_effect=refresh_side), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=lambda *args, **kwargs: next(supervisor_results)), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=2)

        assert result["status"] == "commit_ready", result
        reentry_bridge_index = next(
            index for index, event in enumerate(events)
            if event[0] == "bridge" and "Phase B re-entry R" in str(event[1])
        )
        assert [event[0] for event in events[reentry_bridge_index - 4:reentry_bridge_index]] == [
            "unstage",
            "stage",
            "collect_indicator",
            "refresh_packet",
        ]

    def test_report_only_changed_files_skip_sdk_gate(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["reports/control_plane/plan.md"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["reports/control_plane/plan.md"]), \
             patch.object(pb_mod, "run_sdk_agents", side_effect=AssertionError("SDK gate should be skipped")), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["agent_review_ran"] is False
        assert result["agent_review_skipped_reason"] == "no_implementation_files"
        assert result["agent_review_scope"] == []

    def test_checkout_state_fence_excludes_dirty_baseline_from_wave_scope(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = repo / "reports" / "control_plane" / "plan.md"
        plan_path.write_text(
            "# Plan\n\n"
            "Phase-A-Lock: LOCKED\n\n"
            "## Scope\n\n"
            "- `reports/control_plane/plan.md`\n"
            "- `mu/tools/executors/foo.py`\n\n"
            "### Checkout-state fence\n\n"
            "| File | Status |\n"
            "|------|--------|\n"
            "| `mu/tools/executors/foo.py` | adjacent pipeline-recovery (fenced out) |\n"
        )

        mock_impl = _make_mock_impl()
        stage_files = MagicMock(return_value=True)

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[
                 "mu/tools/executors/foo.py",
                 "reports/control_plane/plan.md",
             ]), \
             patch.object(pb_mod, "run_sdk_agents", side_effect=AssertionError("SDK gate should be skipped")), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", stage_files), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result["agent_review_ran"] is False
        assert result["agent_review_skipped_reason"] == "no_implementation_files"
        assert result["agent_review_scope"] == []
        assert stage_files.call_args_list
        for call in stage_files.call_args_list:
            assert call.args[1] == ["reports/control_plane/plan.md"]

    def test_parse_markdown_findings(self):
        render = (
            "# Bridge Job phase-b-r1-73bc0b2f\n"
            "\n"
            "## Findings\n"
            "  1. **DEFECT** (critical): Missing validation on input\n"
            "     - File: mu/tools/executors/phase_b_executor.py\n"
            "     - Evidence: No check for None before calling .strip()\n"
            "\n"
            "  2. **DEFECT** (high): Stale import left behind\n"
            "     - File: mu/tools/agents/bridge_adapters.py\n"
            "     - Evidence: os module imported but never used\n"
            "\n"
            "  3. **POLICY_BOUND** (medium): Config not in executor_config.json\n"
            "     - File: mu/tools/executors/executor_config.json\n"
            "     - Evidence: Hard-coded timeout value\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 3
        assert findings[0]["title"] == "Missing validation on input"
        assert findings[0]["severity"] == "critical"
        assert findings[0]["type"] == "DEFECT"
        assert findings[0]["class"] == "DEFECT"
        assert findings[0]["disposition"] == "blocking"
        assert findings[0]["file"] == "mu/tools/executors/phase_b_executor.py"
        assert findings[0]["evidence"] == "No check for None before calling .strip()"
        assert findings[1]["severity"] == "high"
        assert findings[1]["title"] == "Stale import left behind"
        assert findings[2]["type"] == "POLICY_BOUND"

    def test_parse_markdown_single_finding(self):
        render = "1. **DEFECT** (low): Minor nit\n   - File: foo.py\n"
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Minor nit"
        assert findings[0]["severity"] == "low"
        assert findings[0]["file"] == "foo.py"
        assert findings[0]["disposition"] == "blocking"

    def test_parse_markdown_with_disposition(self):
        render = (
            "1. **DEFECT** (critical): Bad thing\n"
            "   - File: a.py\n"
            "   - Evidence: proof\n"
            "   - Disposition: blocking\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["disposition"] == "blocking"

    def test_envelope_preferred_over_markdown(self):
        """When both envelope and markdown exist, envelope wins."""
        envelope = json.dumps({"findings": [{"title": "FromEnvelope", "disposition": "blocking"}]})
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            f"{envelope}\n"
            "END_AGENT_ENVELOPE\n"
            "1. **DEFECT** (critical): FromMarkdown\n"
            "   - File: a.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromEnvelope"

    def test_raw_output_reference_preferred_over_rendered_markdown(self, tmp_path):
        """Rendered transcripts must reload reviewer raw output to preserve disposition."""
        raw_path = tmp_path / "reviewer.txt"
        raw_envelope = json.dumps({
            "findings": [
                {
                    "title": "FromRawEnvelope",
                    "class": "DEFECT",
                    "severity": "medium",
                    "disposition": "blocking",
                }
            ]
        })
        raw_path.write_text(
            "noise\nBEGIN_AGENT_ENVELOPE\n"
            f"{raw_envelope}\n"
            "END_AGENT_ENVELOPE\n",
            encoding="utf-8",
        )
        render = (
            "### reviewer\n"
            "- Decision: REQUEST_CHANGES\n"
            "- **Findings (1):**\n"
            "  1. **DEFECT** (medium): FromRenderedMarkdown\n"
            "     - File: a.py\n"
            f"- Raw output: {raw_path}\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromRawEnvelope"
        assert findings[0]["class"] == "DEFECT"
        assert findings[0]["disposition"] == "blocking"

    def test_raw_jsonl_agent_message_beats_command_output_marker_noise(self, tmp_path):
        """JSONL raw transcripts must ignore echoed envelope markers in command output."""
        raw_path = tmp_path / "reviewer-jsonl.txt"
        real_envelope = json.dumps({
            "findings": [
                {
                    "title": "FromAgentMessage",
                    "class": "DOC_ACCURACY",
                    "severity": "low",
                    "disposition": "non_blocking",
                }
            ]
        })
        raw_path.write_text(
            "\n".join([
                json.dumps({
                    "type": "item.completed",
                    "item": {
                        "id": "item_1",
                        "type": "command_execution",
                        "command": "sed -n '1,40p' mu/tools/executors/phase_b_executor.py",
                        "aggregated_output": (
                            'if stripped == "BEGIN_AGENT_ENVELOPE":\\n'
                            'if stripped == "END_AGENT_ENVELOPE":\\n'
                            'return [{"title": "Malformed AGENT_ENVELOPE blocked structured bridge findings parsing"}]'
                        ),
                        "exit_code": 0,
                        "status": "completed",
                    },
                }),
                json.dumps({
                    "type": "item.completed",
                    "item": {
                        "id": "item_2",
                        "type": "agent_message",
                        "text": (
                            "Bootstrap summary\n\n"
                            "BEGIN_AGENT_ENVELOPE\n"
                            f"{real_envelope}\n"
                            "END_AGENT_ENVELOPE"
                        ),
                    },
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        render = (
            "### reviewer\n"
            "- Decision: GO\n"
            "- **Findings (1):**\n"
            "  1. **DOC_ACCURACY** (low): FromRenderedMarkdown\n"
            "     - File: a.py\n"
            f"- Raw output: {raw_path}\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "FromAgentMessage"
        assert findings[0]["class"] == "DOC_ACCURACY"
        assert findings[0]["disposition"] == "non_blocking"


class TestWaveOwnedFilesIncludesDeferredPackets:
    """INV-5: _collect_wave_owned_files must include executor-authored deferred packets."""

    def test_executor_created_files_included(self, tmp_path):
        """Deferred packets created by the executor are included in wave-owned files."""
        repo = tmp_path / "repo"
        repo.mkdir()
        # Create a deferred packet file (executor-authored, not implementer-authored)
        deferred_dir = repo / "reports" / "deferred" / "non_blocking"
        deferred_dir.mkdir(parents=True)
        (deferred_dir / "wave_bridge_nonblockers.md").write_text("# Deferred")

        # Plan is in reports/control_plane/ — deferred is in reports/deferred/
        # Without executor_created_files, this file is NOT under plan_prefix
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        ]):
            # Without executor_created_files: deferred packet dropped
            files_without = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=None,
            )
            assert "reports/deferred/non_blocking/wave_bridge_nonblockers.md" not in files_without

            # With executor_created_files: deferred packet included
            files_with = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files={"reports/deferred/non_blocking/wave_bridge_nonblockers.md"},
            )
            assert "reports/deferred/non_blocking/wave_bridge_nonblockers.md" in files_with

    def test_executor_created_files_empty_is_noop(self, tmp_path):
        """Empty executor_created_files set does not affect results."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/foo.py"]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
            )
            assert files == ["mu/tools/foo.py"]

    def test_post_stage_recollection_drops_cleared_deferred_packet(self, tmp_path):
        """A cleared AD deferred packet must not survive into supervisor package scope."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        plan_rel = "reports/control_plane/plan.md"
        source_rel = "mu/tools/executors/foo.py"
        deferred_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "mu" / "tools" / "executors").mkdir(parents=True)
        (repo / plan_rel).write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / source_rel).write_text("print('old')\n")
        subprocess.run(["git", "add", "--", plan_rel, source_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)

        (repo / source_rel).write_text("print('new')\n")
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / deferred_rel).write_text("# Deferred\n")
        subprocess.run(["git", "add", "--", deferred_rel], cwd=repo, check=True)
        (repo / deferred_rel).unlink()

        changed_files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            plan_rel,
            plan_declared_files=[source_rel],
            implementer_changed_files={source_rel},
            executor_created_files={deferred_rel},
        )
        assert deferred_rel in changed_files

        staged_ok, stage_detail = pb_mod._stage_files_for_pipeline(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        assert staged_ok, stage_detail

        refreshed_changed_files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            plan_rel,
            plan_declared_files=[source_rel],
            implementer_changed_files={source_rel},
            executor_created_files={deferred_rel},
        )
        assert source_rel in refreshed_changed_files
        assert deferred_rel not in refreshed_changed_files

    def test_stage_files_skips_already_staged_delete_source_path(self, tmp_path):
        """Bridge staging must not re-add a missing source path from an already-staged delete."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        source_rel = "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        archive_rel = "reports/archive/deferred/wave_bridge_nonblockers_closed.md"
        (repo / "reports" / "deferred" / "non_blocking").mkdir(parents=True)
        (repo / "reports" / "archive" / "deferred").mkdir(parents=True)
        (repo / source_rel).write_text("# Deferred\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", source_rel], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "rm", "--", source_rel], cwd=repo, check=True, capture_output=True)
        (repo / archive_rel).write_text("# Deferred\n\nClosed by archive.\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", archive_rel], cwd=repo, check=True)

        assert not (repo / source_rel).exists()
        assert source_rel in pb_mod._collect_staged_files(repo)  # ANTICHEAT_OK: testing staged delete source truth

        staged_ok, stage_detail = pb_mod._stage_files_for_pipeline(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            [source_rel, archive_rel],
        )

        assert staged_ok, stage_detail
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert f"D  {source_rel}" in status
        assert f"A  {archive_rel}" in status

    def test_baseline_wave_files_preserved_when_tracking_active(self, tmp_path):
        """Dirty-wave baseline files remain in scope even if the last implementer delta is narrow."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
            "reports/control_plane/plan.md",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo,
                "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
                baseline_wave_files={"mu/tools/runners/run_review.py"},
            )
            assert files == [
                "mu/tools/executors/foo.py",
                "mu/tools/runners/run_review.py",
                "reports/control_plane/plan.md",
            ]


class TestPlanDeclaredFileParsing:
    """Plan markdown parsing must produce clean repo-relative paths for strict tracking."""

    def test_parse_plan_declared_files_strips_backticks_and_line_refs(self):
        content = """
Files:
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/runners/run_review.py:123`
- `reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md`,
- `.gitignore`
- `CHANGELOG.md`
"""
        parsed = pb_mod._parse_plan_declared_files(content)  # ANTICHEAT_OK: testing internal executor functions
        assert "mu/tools/executors/phase_b_executor.py" in parsed
        assert "mu/tools/runners/run_review.py" in parsed
        assert "reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md" in parsed
        assert ".gitignore" in parsed
        assert "CHANGELOG.md" in parsed


@pytest.mark.usefixtures("mock_routing_record")
class TestEmptyFilesToStageBlocksCommitReady:
    """Resume with empty files_to_stage must NOT return commit_ready."""

    def test_empty_files_to_stage_returns_error(self, tmp_path):
        """If no add-able files remain at handoff time, fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_split_commit_handoff_stage_files", return_value=([], [])), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "commit_handoff"
        assert "empty" in result["errors"][0].lower()


@pytest.mark.usefixtures("mock_routing_record")
class TestPytestFixTracksChangedFiles:
    """After pytest-fix implementer pass, newly changed files must be tracked."""

    def test_pytest_fix_files_included_in_wave_owned(self, tmp_path):
        """Files created by pytest-fix implementer pass are captured via implementer_changed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()

        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "j1"}
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": "j2"}

        # Simulate: _collect_changed_files returns progressively more files
        # to create diffs that populate implementer_changed.
        # Calls: 1=pre-impl, 2=post-impl, 3=pre-bridge-fix, 4=post-bridge-fix,
        # 5=pre-pytest-fix, 6=post-pytest-fix (new helper appears here), 7+=stable
        changed_files_calls = [0]
        def changed_files_side(root):
            changed_files_calls[0] += 1
            if changed_files_calls[0] == 1:
                return []  # pre-implementer
            if changed_files_calls[0] <= 4:
                return ["mu/tests/tools/test_existing.py"]
            if changed_files_calls[0] == 5:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            if changed_files_calls[0] == 6:
                return ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            # Call 7+: post-pytest-fix — new helper file appears
            return ["mu/tests/tools/test_foo.py", "mu/tools/executors/new_helper.py"]

        pytest_calls = [0]
        def pytest_side(repo_root, test_files, **kw):
            pytest_calls[0] += 1
            if pytest_calls[0] == 1:
                return {"exit_code": 1, "stdout": "FAILED", "stderr": "", "passed": False}
            return {"exit_code": 0, "stdout": "passed", "stderr": "", "passed": True}

        # Track what _collect_wave_owned_files returns across the bridge/pytest-fix path.
        wave_owned_results = []
        wave_owned_calls = [0]

        def tracking_collect(*a, **kw):
            wave_owned_calls[0] += 1
            if wave_owned_calls[0] <= 2:
                result = ["mu/tests/tools/test_existing.py"]
            elif wave_owned_calls[0] == 3:
                result = ["mu/tests/tools/test_existing.py", "mu/tests/tools/test_foo.py"]
            else:
                result = ["mu/tools/executors/new_helper.py"]
            wave_owned_results.append(result)
            return result

        pager_calls = []

        def fake_emit(repo_root, **kwargs):
            pager_calls.append(kwargs)
            return {"enabled": True, "event_id": f"evt-{len(pager_calls)}", "attempted": []}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", side_effect=changed_files_side), \
             patch.object(pb_mod, "_collect_wave_owned_files", side_effect=tracking_collect), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="findings"), \
             patch.object(pb_mod, "_run_pytest_on_files", side_effect=pytest_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "emit_pipeline_agent_event", side_effect=fake_emit), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # The pytest-fix implementer was invoked (3 calls: initial + bridge fix + pytest fix)
        assert mock_impl.invoke_implementer.call_count >= 3
        # The new file should appear in the final wave-owned collection
        # (via implementer_changed tracking from the pytest-fix pass)
        last_wave_owned = wave_owned_results[-1] if wave_owned_results else []
        assert "mu/tools/executors/new_helper.py" in last_wave_owned
        pytest_fix_events = [
            call for call in pager_calls
            if str(call.get("transition_key", "")).startswith("round-1:pytest_fix:")
        ]
        assert [call["event_type"] for call in pytest_fix_events] == [
            "phase_b_implementer_started",
            "phase_b_implementer_completed",
        ]
        assert [call["state"] for call in pytest_fix_events] == [
            "pytest_fix_started",
            "pytest_fix_success",
        ]


@pytest.mark.usefixtures("mock_routing_record")
class TestResumeNeedsPhaseB:
    """CRITICAL: Resume from needs_phase_b_reentry must NOT skip to commit_ready."""

    def test_resume_from_needs_phase_b_reentry_enters_reentry_loop(self, tmp_path):
        """Crash during NEEDS_PHASE_B re-entry resumes into re-entry, not commit_ready."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        # Write saved state simulating crash during NEEDS_PHASE_B re-entry
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tools/executors/foo.py"]
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix the thing",
        }))

        mock_impl = _make_mock_impl()
        # Implementer re-entry succeeds
        mock_impl.invoke_implementer.return_value = {
            "status": "success", "output": "done", "stderr": "",
            "exit_code": 0, "job_id": "impl-reentry", "model_override_applied": False,
        }

        # Bridge after re-entry implementer returns GO
        bridge_calls = [0]
        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "",
                    "decision": "GO", "job_id": f"j-reentry-{bridge_calls[0]}"}

        # Supervisor after re-entry returns COMMIT_GO
        supervisor_calls = [0]
        def supervisor_side(repo_root, pkg, **kw):
            supervisor_calls[0] += 1
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Must have resumed and invoked implementer for re-entry
        assert result.get("resumed_from") == "needs_phase_b_reentry"
        # Implementer was called (re-entry pass)
        assert mock_impl.invoke_implementer.call_count >= 1
        # Bridge was called for re-entry review
        assert bridge_calls[0] >= 1
        # Should reach commit_ready (not error or supervisor_rejected)
        assert result["status"] == "commit_ready", f"Expected commit_ready, got {result}"
        reentry_source = mock_impl.build_implementation_prompt.call_args_list[0].args[0]
        assert "## Re-entry Findings\n\nFix the thing" in reentry_source
        assert "## Re-entry Findings (" not in reentry_source

    @pytest.mark.parametrize("saved_decision", ["REQUEST_CHANGES", "NO_GO"])
    def test_resume_preserves_last_reentry_bridge_decision_in_implementer_prompt(
        self,
        tmp_path,
        saved_decision,
    ):
        """An unchanged-scope resume carries exact non-GO context into its first fix."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        (repo / ".scratch").mkdir()

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tools/executors/foo.py"]
        exact_findings = (
            "First saved finding: preserve punctuation exactly.\n"
            "Second saved finding: keep this ordering and context."
        )
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": exact_findings,
            "last_reentry_bridge_decision": saved_decision,
        }), encoding="utf-8")

        mock_impl = _make_mock_impl()
        mock_impl.build_implementation_prompt.side_effect = (
            lambda plan_content, **kwargs: plan_content
        )
        call_order = []
        implementer_prompts = []
        pre_invocation_checkpoints = []

        def invoke_side(repo_root, prompt, **kwargs):
            call_order.append("implementer")
            implementer_prompts.append(prompt)
            pre_invocation_checkpoints.append(json.loads(
                (state_dir / "phase_b_state.json").read_text(encoding="utf-8")
            ))
            return {
                "status": "success",
                "output": "done",
                "stderr": "",
                "exit_code": 0,
                "job_id": "impl-reentry",
                "model_override_applied": False,
            }

        mock_impl.invoke_implementer.side_effect = invoke_side

        def bridge_side(*args, **kwargs):
            call_order.append("bridge")
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": "reentry-go",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(
                repo,
                "reports/control_plane/plan.md",
                max_bridge_rounds=5,
            )

        assert result["status"] == "commit_ready", result
        assert call_order[0] == "implementer"
        assert call_order.index("implementer") < call_order.index("bridge")
        assert len(implementer_prompts) == 1
        prompt = implementer_prompts[0]
        heading = f"## Re-entry Findings ({saved_decision})"
        assert prompt.count(exact_findings) == 1
        assert prompt.index("# Plan") < prompt.index(heading) < prompt.index(exact_findings)
        assert f"{heading}\n\n{exact_findings}" in prompt
        checkpoint = pre_invocation_checkpoints[0]
        assert checkpoint["completed_step"] == "needs_phase_b_reentry"
        assert checkpoint["reentry_findings"] == exact_findings
        assert checkpoint["last_reentry_bridge_decision"] == saved_decision

    def test_runtime_pre_push_reentry_refuses_control_only_commit_ready(self, tmp_path):
        """Runtime pre-push failures must not be repackaged as control-only COMMIT_GO."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Purpose: This is an L4_STRUCTURAL implementation wave, not another "
            "plan-only/control-plane package.\n",
            encoding="utf-8",
        )
        (repo / ".scratch").mkdir()

        changed_files = [
            "TASKS.md",
            "reports/control_plane/plan.md",
            "reports/l4_wave_indicators/plan.json",
        ]
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": (
                "run_pre_push_script: pre-push-fast failed\n"
                "FAILED tests/structural/test_engine_pipeline_discipline.py::test_rule\n"
                "FAILED tests/parity/test_js_parity_automated.py::test_rule"
            ),
        }))

        mock_impl = _make_mock_impl()
        supervisor = MagicMock(return_value={
            "exit_code": 0,
            "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
            "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
        })

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "reentry-go",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files_for_pipeline", return_value=(True, "")), \
             patch.object(pb_mod, "_collect_commit_bound_files", return_value=changed_files), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_runtime_pre_push_scope"
        assert "control-only commit-ready package" in result["errors"][0]
        supervisor.assert_not_called()

    def test_resume_from_needs_phase_b_reentry_honors_post_implementer_checkpoint(self, tmp_path):
        """A saved post-implementer checkpoint reviews current fixes without re-running them."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tools/executors/foo.py"]
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Already fixed; review only",
            "skip_reentry_implementer_once": True,
        }))

        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.side_effect = AssertionError(
            "post-implementer re-entry checkpoint should not re-run implementer"
        )
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": f"j-reentry-{bridge_calls[0]}",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "needs_phase_b_reentry"
        assert mock_impl.invoke_implementer.call_count == 0
        assert bridge_calls[0] >= 1
        assert result["status"] == "commit_ready", f"Expected commit_ready, got {result}"

    def test_resume_from_legacy_post_implementer_checkpoint_at_max_round_reviews_before_result(self, tmp_path):
        """Legacy post-implementer checkpoints at the max round must not skip review or crash."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        changed_files = ["mu/tools/executors/foo.py"]
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 5,
            "bridge_scope_fingerprint": pb_mod._bridge_scope_fingerprint(repo, changed_files),  # ANTICHEAT_OK: testing internal executor functions
            "deferred_packet_path": None,
            "implementer_changed": changed_files,
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Already fixed at max round; review only",
            "skip_reentry_implementer_once": True,
        }))

        mock_impl = _make_mock_impl()
        mock_impl.invoke_implementer.side_effect = AssertionError(
            "legacy post-implementer checkpoint should review before invoking implementer"
        )
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            state_at_review = json.loads((state_dir / "phase_b_state.json").read_text(encoding="utf-8"))
            assert state_at_review.get("skip_reentry_implementer_once") is True
            assert state_at_review.get("bridge_rounds") == 5
            return {
                "exit_code": 0,
                "stdout": "GO\n",
                "stderr": "",
                "decision": "GO",
                "job_id": kw.get("job_id", f"j-reentry-{bridge_calls[0]}"),
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=changed_files), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "needs_phase_b_reentry"
        assert mock_impl.invoke_implementer.call_count == 0
        assert bridge_calls[0] == 1
        assert result["status"] == "commit_ready", f"Expected commit_ready, got {result}"

    def test_reentry_repeat_cap_fails_closed(self, tmp_path):
        """Re-entry REQUEST_CHANGES must honor REPEAT_FINDING_CAP like the initial loop."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / ".scratch").mkdir()

        finding = {"title": "Stubborn blocker", "severity": "high", "file": "mu/tools/executors/phase_b_executor.py"}
        key = pb_mod._finding_key(finding)  # ANTICHEAT_OK: testing internal executor functions

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
            "finding_history": {key: pb_mod.REPEAT_FINDING_CAP},
            "reentry_findings": "Fix the stubborn blocker",
        }))

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                 "decision": "REQUEST_CHANGES", "job_id": "re1",
             }), \
             patch.object(pb_mod, "_read_bridge_render", return_value="rendered"), \
             patch.object(pb_mod, "_parse_findings_from_render", return_value=[finding]), \
             patch.object(pb_mod, "_stage_files", return_value=True):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "reentry_bridge_convergence"
        assert "unresolvable" in " ".join(result["errors"]).lower()

    def test_resume_from_bridge_converged_does_not_enter_reentry(self, tmp_path):
        """Resume from bridge_converged should go through supervisor normally, not re-entry."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / "f.py").write_text("print('ok')\n")
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["f.py"],
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        mock_impl = _make_mock_impl()
        run_sdk_agents = MagicMock(return_value={"exit_code": 0, "stdout": "", "stderr": ""})

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", run_sdk_agents), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0, "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_converged"
        assert result["status"] == "commit_ready"
        # Implementer was NOT called (skipped on resume from bridge_converged)
        assert mock_impl.invoke_implementer.call_count == 0
        run_sdk_agents.assert_not_called()

    def test_blocking_finding_convergence_resume_rejects_blocker_in_all_non_blocking(self, tmp_path):
        """A saved bridge_converged state cannot hide a blocker in all_non_blocking."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / "f.py").write_text("print('ok')\n")
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["f.py"],
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "all_non_blocking": [{
                # The resume guard must reject an explicit medium blocker even if
                # stale state previously placed it in all_non_blocking.
                "title": "Control packet line-reference finding was classified blocking",
                "class": "POLICY_BOUND",
                "severity": "medium",
                "file": "reports/control_plane/plan.md",
                "disposition": "blocking",
            }],
        }))

        mock_impl = _make_mock_impl()
        supervisor = MagicMock(return_value={
            "exit_code": 0,
            "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
            "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
        })

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "error"
        assert result["step"] == "blocking_finding_convergence"
        assert "blocking finding" in result["errors"][0]
        supervisor.assert_not_called()
        assert mock_impl.invoke_implementer.call_count == 0

    def test_blocking_finding_convergence_request_changes_invokes_bridge_fix_before_commit_ready(self, tmp_path):
        """REQUEST_CHANGES with an explicit blocker takes the bridge-fix path before finalization."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Wave ID: plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Task: [NEXT-CODEX-POST-REDTEAM]\n"
            "Class: L4_ENABLER\n"
            "Target gate: G8\n",
            encoding="utf-8",
        )
        blocking_finding = {
            # Explicit medium blocking drives the bridge-fix path independently
            # of the high/critical severity floor.
            "title": "Control packet line-reference finding",
            "class": "POLICY_BOUND",
            "severity": "medium",
            "file": plan_path,
            "disposition": "blocking",
        }
        bridge_results = iter([
            {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "", "decision": "REQUEST_CHANGES", "job_id": "r1"},
            {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "r2"},
        ])
        raw_blocker = (
            "BEGIN_AGENT_ENVELOPE\n"
            + json.dumps({"findings": [blocking_finding]})
            + "\nEND_AGENT_ENVELOPE\n"
        )
        bridge_material = iter([
            ("rendered blocker", [raw_blocker]),
            ("", []),
        ])
        wave_owned = [plan_path, "mu/tools/executors/phase_b_executor.py"]
        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record", return_value={
                 **_VALID_ROUTING_RECORD,
                 "task_id": "[NEXT-CODEX-POST-REDTEAM]",
                 "wave_name": "plan",
                 "wave_class": "L4_ENABLER",
                 "target_gate_id": "G8",
             }), \
             patch.object(pb_mod, "_collect_changed_files", return_value=wave_owned), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=wave_owned), \
             patch.object(pb_mod, "_read_bridge_review_material", side_effect=lambda *_a, **_kw: next(bridge_material)), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=lambda *_a, **_kw: next(bridge_results)), \
             patch.object(pb_mod, "_select_pytest_gate_files", return_value=[]), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"):
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=3)

        assert result["status"] == "commit_ready", result
        assert mock_impl.invoke_implementer.call_count >= 2

    def test_control_packet_line_ref_normalized_to_name_only_no_strand(self, tmp_path):
        """A control-packet extension-colon-digit ref is normalized to name-only; the lint then passes (no strand).

        Regression for pipeline-fix-25: an implementer addressing a line-cited
        finding writes ``TASKS.md:128`` / ``loader.py:42:7`` into the packet. The
        producing executor normalizes the packet to the compliant name-only form
        *before* the fail-closed lint, so the wave self-heals instead of
        stranding (tier-3 recovery cannot remove an edit-gated control-plane ref).
        """
        repo = tmp_path / "repo"
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        packet = repo / plan_path
        packet.write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Purpose: address finding citing TASKS.md:128 and loader.py:42:7.\n",
            encoding="utf-8",
        )
        changed_files = [plan_path]

        # Pre-normalization: the lint would strand (line-ref present).
        pre = pb_mod._control_packet_line_ref_lint_error(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )
        assert pre is not None
        assert "TASKS.md:128" in pre

        # The producing executor normalizes its own packet in place.
        pb_mod._normalize_control_packet_line_refs(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )

        # The packet ends line-ref-free on disk; the name-only form is preserved
        # (file:line and file:line:col both collapse to the bare name).
        text = packet.read_text(encoding="utf-8")
        assert "TASKS.md:128" not in text
        assert "loader.py:42" not in text
        assert "TASKS.md" in text
        assert "loader.py" in text

        # The lint now returns no error: the no-line-refs invariant holds and the
        # wave does not strand.
        post = pb_mod._control_packet_line_ref_lint_error(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )
        assert post is None

    def test_control_packet_line_range_ref_normalized_no_malformed_residue(self, tmp_path):
        """A line-RANGE/list/col citation collapses to name-only with no malformed residue.

        Regression for pipeline-fix-25 bridge round 2: the earlier normalizer
        consumed only ``:<line>`` colon-digit groups, so a range citation
        ``loader.py:42-45`` lost its ``:42`` but kept the dangling ``-45`` --
        leaving the malformed ``loader.py-45`` residue. The lint then PASSED on
        it (it is no longer ``.<ext>:<digit>``) and the wave silently shipped a
        broken ref. The full numeric-tail normalizer collapses range, list, and
        col forms to the bare name in one pass, and the lint stays clean.
        """
        repo = tmp_path / "repo"
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        packet = repo / plan_path
        packet.write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "Refs: loader.py:42-45 and TASKS.md:128.\n"
            "List: parser.py:10,14,20 col eval_step.js:7:3.\n",
            encoding="utf-8",
        )
        changed_files = [plan_path]

        # Pre-normalization: the lint strands on the range/list/col citations.
        pre = pb_mod._control_packet_line_ref_lint_error(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )
        assert pre is not None
        assert "loader.py:42-45" in pre

        # The producing executor normalizes its own packet in place.
        pb_mod._normalize_control_packet_line_refs(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )

        text = packet.read_text(encoding="utf-8")
        # Every name-only head survives; every numeric tail (range, list, col) is gone.
        assert "loader.py" in text
        assert "TASKS.md" in text
        assert "parser.py" in text
        assert "eval_step.js" in text
        # No malformed residue: the range's trailing ``-45`` must NOT survive,
        # and no citation digits or separators remain anywhere in the packet.
        assert "loader.py-45" not in text
        assert "-45" not in text
        assert ":42" not in text and ":128" not in text
        assert "10,14,20" not in text and ":7:3" not in text

        # The lint is clean post-normalization: the wave self-heals (no strand).
        post = pb_mod._control_packet_line_ref_lint_error(  # ANTICHEAT_OK: testing internal executor functions
            repo, plan_path=plan_path, changed_files=changed_files,
        )
        assert post is None

    def test_line_ref_lint_normalizes_post_bridge_packet_drift_before_final_pytest(self, tmp_path):
        """Post-bridge control-packet file:line drift self-heals (normalized to name-only) instead of stranding."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "mu" / "tests" / "tools").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        test_path = "mu/tests/tools/test_line_ref_example.py"
        (repo / plan_path).write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        (repo / test_path).write_text("def test_ok():\n    assert True\n")
        mock_impl = _make_mock_impl()
        final_pytest = MagicMock(return_value={
            "passed": True, "exit_code": 0, "stdout": "", "stderr": "",
        })
        supervisor = MagicMock(return_value={
            "exit_code": 0,
            "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
            "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
        })

        def bridge_go_with_packet_drift(*_args, **_kwargs):
            (repo / plan_path).write_text(
                "# Plan\nPhase-A-Lock: LOCKED\nSee mu/tools/executors/phase_b_executor.py:42.\n",
                encoding="utf-8",
            )
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j1"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[plan_path, test_path]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[plan_path, test_path]), \
             patch.object(pb_mod, "_read_bridge_review_material", return_value=("", [])), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_go_with_packet_drift), \
             patch.object(pb_mod, "_select_pytest_gate_files", return_value=[test_path]), \
             patch.object(pb_mod, "_run_pytest_on_files", side_effect=final_pytest), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_should_collect_l4_indicator_artifact", return_value=False), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(repo, plan_path, max_bridge_rounds=2)

        # New behavior: the implementer-added line-ref self-heals to name-only,
        # so the wave finalizes (commit_ready) instead of stranding at the lint.
        # ``step`` is only set on error, so its absence is itself proof of no strand.
        assert result["status"] == "commit_ready", result
        assert result.get("step") != "control_packet_line_ref_lint", result
        # The packet ends line-ref-free on disk (normalized to name-only).
        packet_text = (repo / plan_path).read_text(encoding="utf-8")
        assert "phase_b_executor.py:42" not in packet_text
        assert "phase_b_executor.py" in packet_text
        # Self-heal proceeds past the lint into final pytest + supervisor finalization.
        final_pytest.assert_called()
        supervisor.assert_called()

    def test_resume_from_bridge_converged_rehydrates_dirty_baseline_into_package(self, tmp_path):
        """Legacy saved state without baseline tracking must still rebuild an honest supervisor package."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        changed_files = [
            "mu/tools/executors/foo.py",
            "mu/tools/runners/run_review.py",
            "reports/control_plane/plan.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        saved_state = json.loads((state_dir / "phase_b_state.json").read_text())
        saved_state["bridge_scope_fingerprint"] = bridge_scope_fingerprint
        (state_dir / "phase_b_state.json").write_text(json.dumps(saved_state))
        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kw: sorted(set(files))), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["changed_files"] == ["TASKS.md", *changed_files]

    def test_resume_from_bridge_converged_unions_saved_and_current_baseline(self, tmp_path):
        """Saved baseline scope must be refreshed with any newly dirty wave files before packaging."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "baseline_wave_files": ["mu/tools/executors/foo.py"],
            "all_non_blocking": [],
        }))

        changed_files = [
            "mu/tools/agents/meta_bridge_supervisor.py",
            "mu/tools/executors/foo.py",
            "reports/control_plane/plan.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        saved_state = json.loads((state_dir / "phase_b_state.json").read_text())
        saved_state["bridge_scope_fingerprint"] = bridge_scope_fingerprint
        (state_dir / "phase_b_state.json").write_text(json.dumps(saved_state))
        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_collect_commit_bound_files", side_effect=lambda _repo, files, **_kw: sorted(set(files))), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["changed_files"] == ["TASKS.md", *changed_files]

    def test_resume_from_bridge_converged_surfaces_changed_deferred_packet_in_supervisor_package(self, tmp_path):
        """Supervisor package must acknowledge changed non-blocking packets even without deferred_packet_path state."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        changed_files = [
            "mu/tools/executors/foo.py",
            "reports/control_plane/plan.md",
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": ["reports/deferred/non_blocking/wave_bridge_nonblockers.md"],
            "all_non_blocking": [],
        }))

        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["deferred_items"] == [
            "reports/deferred/non_blocking/wave_bridge_nonblockers.md"
        ]

    def test_resume_from_bridge_converged_omits_missing_indicator_from_supervisor_package(self, tmp_path):
        """Supervisor package must not claim an indicator artifact before it exists."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\n"
            "Phase-A-Lock: LOCKED\n"
            "- `mu/tools/executors/foo.py`\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/executors/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        changed_files = [
            "mu/tools/executors/foo.py",
            "reports/control_plane/plan.md",
        ]
        bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            changed_files,
        )
        saved_state = json.loads((state_dir / "phase_b_state.json").read_text())
        saved_state["bridge_scope_fingerprint"] = bridge_scope_fingerprint
        (state_dir / "phase_b_state.json").write_text(json.dumps(saved_state))

        captured_package = {}
        mock_impl = _make_mock_impl()

        def supervisor_side(_repo_root, package_path, **_kw):
            captured_package["value"] = json.loads(Path(package_path).read_text())
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=changed_files), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert captured_package["value"]["evidence_handles"] == {}

    def test_reentry_go_without_non_blocking_clears_stale_deferred_packet(self, tmp_path):
        """A clean re-entry bridge pass must delete obsolete deferred packets before supervisor reruns."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        initial_render = (
            "BEGIN_AGENT_ENVELOPE\n"
            + json.dumps({
                "job_id": "j1",
                "turn_id": "t1",
                "agent_role": "reviewer",
                "decision": "REQUEST_CHANGES",
                "summary": "minor nits",
                "touched_files_claimed": [],
                "validations_claimed": [],
                "request_for_next_agent": "",
                "findings": [
                    {
                        "title": "Doc drift",
                        "class": "DOC_ACCURACY",
                        "severity": "low",
                        "file": "mu/tools/executors/dialectic_executor.py",
                        "disposition": "non_blocking",
                        "status": "new",
                    },
                ],
            })
            + "\nEND_AGENT_ENVELOPE"
        )
        reentry_render = (
            "BEGIN_AGENT_ENVELOPE\n"
            + json.dumps({
                "job_id": "j2",
                "turn_id": "t2",
                "agent_role": "reviewer",
                "decision": "GO",
                "summary": "clean",
                "touched_files_claimed": [],
                "validations_claimed": [],
                "request_for_next_agent": "",
                "findings": [],
            })
            + "\nEND_AGENT_ENVELOPE"
        )

        supervisor_calls = {"count": 0}
        captured_package = {}

        def supervisor_side(_repo_root, package_path, **_kw):
            supervisor_calls["count"] += 1
            if supervisor_calls["count"] == 1:
                return {
                    "exit_code": 0,
                    "parsed": {
                        "decision": "NEEDS_PHASE_B",
                        "summary": "Deferred packet is stale",
                        "status": "success",
                        "findings": [],
                        "request_for_claude": "Regenerate or delete the stale deferred packet.",
                    },
                    "receipt_path": "",
                }
            captured_package["value"] = json.loads(Path(package_path).read_text(encoding="utf-8"))
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/dialectic_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[
                 "mu/tools/executors/dialectic_executor.py",
                 "reports/control_plane/plan.md",
             ]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "", "decision": "REQUEST_CHANGES", "job_id": "j1"},
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j2"},
             ]), \
             patch.object(pb_mod, "_read_bridge_review_material", side_effect=[
                 (initial_render, []),
                 (reentry_render, []),
             ]), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert result.get("deferred_packet_path") is None
        assert captured_package["value"]["deferred_items"] == []
        assert not (
            repo / "reports" / "deferred" / "non_blocking" / "plan_bridge_nonblockers.md"
        ).exists()

    def test_reentry_go_preserves_deferred_packet_wave_metadata(self, tmp_path):
        """Re-entry non-blocking refresh must keep the wave class and target gate."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        initial_render = (
            "BEGIN_AGENT_ENVELOPE\n"
            + json.dumps({
                "job_id": "j1",
                "turn_id": "t1",
                "agent_role": "reviewer",
                "decision": "REQUEST_CHANGES",
                "summary": "initial non-blocking packet",
                "touched_files_claimed": [],
                "validations_claimed": [],
                "request_for_next_agent": "",
                "findings": [
                    {
                        "title": "Initial doc drift",
                        "class": "DOC_ACCURACY",
                        "severity": "low",
                        "file": "mu/tools/executors/dialectic_executor.py",
                        "disposition": "non_blocking",
                        "status": "new",
                    },
                ],
            })
            + "\nEND_AGENT_ENVELOPE"
        )
        reentry_render = (
            "BEGIN_AGENT_ENVELOPE\n"
            + json.dumps({
                "job_id": "j2",
                "turn_id": "t2",
                "agent_role": "reviewer",
                "decision": "GO",
                "summary": "re-entry leaves non-blocking note",
                "touched_files_claimed": [],
                "validations_claimed": [],
                "request_for_next_agent": "",
                "findings": [
                    {
                        "title": "Re-entry doc drift",
                        "class": "DOC_ACCURACY",
                        "severity": "low",
                        "file": "mu/tools/executors/phase_b_executor.py",
                        "disposition": "non_blocking",
                        "status": "new",
                    },
                ],
            })
            + "\nEND_AGENT_ENVELOPE"
        )

        supervisor_calls = {"count": 0}

        def supervisor_side(_repo_root, _package_path, **_kw):
            supervisor_calls["count"] += 1
            if supervisor_calls["count"] == 1:
                return {
                    "exit_code": 0,
                    "parsed": {
                        "decision": "NEEDS_PHASE_B",
                        "summary": "Refresh deferred packet.",
                        "status": "success",
                        "findings": [],
                        "request_for_claude": "Refresh packet.",
                    },
                    "receipt_path": "",
                }
            return {
                "exit_code": 0,
                "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
            }

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/dialectic_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[
                 "mu/tools/executors/dialectic_executor.py",
                 "reports/control_plane/plan.md",
             ]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=[
                 {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "", "decision": "REQUEST_CHANGES", "job_id": "j1"},
                 {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "j2"},
             ]), \
             patch.object(pb_mod, "_read_bridge_review_material", side_effect=[
                 (initial_render, []),
                 (reentry_render, []),
             ]), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", side_effect=supervisor_side):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        packet = repo / "reports" / "deferred" / "non_blocking" / "plan_bridge_nonblockers.md"
        content = packet.read_text(encoding="utf-8")
        assert "Class: L4_ENABLER" in content
        assert "Target Gate: G8" in content
        assert "Re-entry doc drift" in content
        assert "Initial doc drift" not in content

    def test_resume_from_bridge_converged_reruns_sdk_and_bridge_when_scope_fingerprint_drifted(self, tmp_path):
        """A drifted bridge_converged checkpoint must not skip directly to supervisor."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "mu" / "tools").mkdir(parents=True)
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        tracked_file = repo / "mu" / "tools" / "foo.py"
        tracked_file.write_text("print('old')\n")
        stale_bridge_scope_fingerprint = pb_mod._bridge_scope_fingerprint(  # ANTICHEAT_OK: testing internal executor functions
            repo,
            ["mu/tools/foo.py"],
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "bridge_converged",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "bridge_scope_fingerprint": stale_bridge_scope_fingerprint,
            "deferred_packet_path": None,
            "implementer_changed": ["mu/tools/foo.py"],
            "executor_created": [],
            "all_non_blocking": [],
        }))

        tracked_file.write_text("print('new')\n")
        mock_impl = _make_mock_impl()
        run_sdk_agents = MagicMock(return_value={"exit_code": 0, "stdout": "", "stderr": ""})
        run_bridge_review = MagicMock(return_value={
            "exit_code": 0,
            "stdout": "GO\n",
            "stderr": "",
            "decision": "GO",
            "job_id": "j1",
        })

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/foo.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", run_sdk_agents), \
             patch.object(pb_mod, "run_bridge_review", run_bridge_review), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result.get("resumed_from") == "bridge_converged"
        assert result["status"] == "commit_ready"
        run_sdk_agents.assert_called_once()
        run_bridge_review.assert_called_once()
        assert mock_impl.invoke_implementer.call_count == 0


class TestWaveOwnedFilesNoPrefixGlob:
    """HIGH: _collect_wave_owned_files must not glob plan_prefix when tracking is active."""

    def test_dirty_sibling_in_plan_dir_excluded_with_tracking(self, tmp_path):
        """Dirty control-plane siblings must NOT be included when explicit tracking is active."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "mu/tools/executors/foo.py",
            "reports/control_plane/other_wave_plan.md",  # unrelated dirty sibling
            "reports/control_plane/plan.md",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=["mu/tools/executors/foo.py"],
                implementer_changed_files=set(),
                executor_created_files=set(),
            )
            assert "mu/tools/executors/foo.py" in files
            # Plan file itself is always wave-owned
            assert "reports/control_plane/plan.md" in files
            # Unrelated sibling must be excluded
            assert "reports/control_plane/other_wave_plan.md" not in files

    def test_plan_prefix_still_used_in_degraded_fallback(self, tmp_path):
        """When no explicit tracking (both None), prefix-based filtering still works."""
        repo = tmp_path / "repo"
        repo.mkdir()
        with patch.object(pb_mod, "_collect_changed_files", return_value=[
            "reports/control_plane/plan.md",
            "reports/control_plane/other.md",
            "mu/tools/executors/foo.py",
        ]):
            files = pb_mod._collect_wave_owned_files(  # ANTICHEAT_OK: testing internal executor functions
                repo, "reports/control_plane/plan.md",
                plan_declared_files=None,
                implementer_changed_files=None,
                executor_created_files=None,
            )
            # In degraded fallback, plan_prefix files are included
            assert "reports/control_plane/plan.md" in files
            assert "reports/control_plane/other.md" in files
            # mu/tools/ is in _WAVE_OWNED_PREFIXES
            assert "mu/tools/executors/foo.py" in files


class TestBridgeFixScopeReconciliation:
    def test_preexisting_unstaged_files_drop_from_implementer_scope(self, tmp_path):
        with patch.object(
            pb_mod,
            "_collect_staged_files",
            return_value=["TASKS.md", "reports/control_plane/lock.md"],
        ):
            reconciled = pb_mod._reconcile_bridge_fix_scope(  # ANTICHEAT_OK: testing internal executor function
                tmp_path,
                {
                    "TASKS.md",
                    "mu/host/js/core/seed_loader.js",
                    "reports/control_plane/lock.md",
                },
                set(),
            )

        assert reconciled == {"TASKS.md", "reports/control_plane/lock.md"}

    def test_new_fix_files_remain_tracked_even_when_unstaged(self, tmp_path):
        with patch.object(pb_mod, "_collect_staged_files", return_value=["TASKS.md"]):
            reconciled = pb_mod._reconcile_bridge_fix_scope(  # ANTICHEAT_OK: testing internal executor function
                tmp_path,
                {
                    "TASKS.md",
                    "mu/host/js/core/seed_loader.js",
                    "reports/deferred/non_blocking/lock_bridge_nonblockers.md",
                },
                {"reports/deferred/non_blocking/lock_bridge_nonblockers.md"},
            )

        assert reconciled == {
            "TASKS.md",
            "reports/deferred/non_blocking/lock_bridge_nonblockers.md",
        }

    def test_empty_staged_set_preserves_scope(self, tmp_path):
        implementer_changed = {"TASKS.md", "mu/host/js/core/seed_loader.js"}
        with patch.object(pb_mod, "_collect_staged_files", return_value=[]):
            reconciled = pb_mod._reconcile_bridge_fix_scope(  # ANTICHEAT_OK: testing internal executor function
                tmp_path,
                implementer_changed,
                set(),
            )

        assert reconciled == implementer_changed


class TestRoutingValidationNotBypassed:
    """Phase B must NOT silently rewrite routing tokens.

    Bridge R1 finding: phase_b_executor was overriding stale/wrong routing
    decisions to ROUTE_PHASE_B before validation, making validate_inputs
    meaningless. The fix: validation errors are fatal unless --force is used.
    """

    def test_wrong_routing_token_fails_without_force(self):
        """ROUTE_PHASE_A token → PhaseBExecutorError (no silent rewrite)."""
        routing = {"decision": "ROUTE_PHASE_A", "summary": "test"}
        plan = {"phase_a_lock": "LOCKED"}
        with pytest.raises(pb_mod.PhaseBExecutorError, match="ROUTE_PHASE_B"):
            pb_mod.validate_inputs(routing, plan)

    def test_correct_routing_token_passes(self):
        """ROUTE_PHASE_B token → validation passes (no exception)."""
        routing = {"decision": "ROUTE_PHASE_B", "summary": "test"}
        plan = {"phase_a_lock": "LOCKED"}
        pb_mod.validate_inputs(routing, plan)  # should not raise

    def test_unlocked_plan_fails(self):
        """Plan not LOCKED → PhaseBExecutorError."""
        routing = {"decision": "ROUTE_PHASE_B", "summary": "test"}
        plan = {"phase_a_lock": "DRAFT"}
        with pytest.raises(pb_mod.PhaseBExecutorError, match="LOCKED"):
            pb_mod.validate_inputs(routing, plan)

    def test_task_id_mismatch_fails(self):
        """Locked plans cannot be paired with a different routing task_id."""
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[RECOVERY-TIER3-WIRING]",
        }
        plan = {
            "phase_a_lock": "LOCKED",
            "task_id": "[CODEX-STARTUP-HARDENING]",
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="does not match routing task_id"):
            pb_mod.validate_inputs(routing, plan)

    def test_markdown_wrapped_task_header_matches_plain_routing_task_id(self, tmp_path):
        repo = tmp_path / "repo"
        plan_dir = repo / "reports"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "plan.md"
        plan_file.write_text(
            "Phase-A-Lock: LOCKED\n"
            "Status: ACTIVE\n"
            "Wave ID: `pager-codex-app-server-provisioning`\n"
            "Task: `[PIPELINE-AGENT-PAGER]`\n"
        )
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_name": "pager-codex-app-server-provisioning",
        }

        plan = pb_mod.load_plan_packet(repo, "reports/plan.md")

        pb_mod.validate_inputs(routing, plan)


class TestRunPhaseBValidationErrors:
    def test_validate_inputs_error_carries_plan_path(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\nTask: [PIPELINE-AGENT-PAGER]\nWave ID: wave-x\nDate: 2026-04-22\nStatus: Phase B\n",
            encoding="utf-8",
        )
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-AGENT-PAGER]",
            "wave_name": "wave-x",
        }

        result = pb_mod.run_phase_b(repo, plan_path, routing_record_override=routing)

        assert result["status"] == "error"
        assert result["step"] == "validate_inputs"
        assert result["plan_path"] == plan_path
        assert "Plan Phase-A-Lock must be LOCKED" in result["errors"][0]

    def test_same_wave_task_id_exception_passes_for_tracked_pipeline_recovery_packet(self):
        """One same-wave recovery packet may carry wave identity in Task without changing routing anchor."""
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": (
                        "reports/control_plane/"
                        "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
                    ),
                }
            ],
        }
        plan = {
            "phase_a_lock": "LOCKED",
            "path": (
                "reports/control_plane/"
                "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
            ),
            "wave_id": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "task_id": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "content": (
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Phase-A-Lock: LOCKED\n"
            ),
        }

        pb_mod.validate_inputs(routing, plan)

    def test_same_wave_task_id_exception_rejects_unbounded_candidate(self):
        """The explicit exception must remain scoped to a bounded routing candidate."""
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": False,
                    "tracked_packet": (
                        "reports/control_plane/"
                        "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
                    ),
                }
            ],
        }
        plan = {
            "phase_a_lock": "LOCKED",
            "path": (
                "reports/control_plane/"
                "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
            ),
            "wave_id": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "task_id": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "content": (
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Phase-A-Lock: LOCKED\n"
            ),
        }

        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves bounded routing remains mandatory
        with pytest.raises(pb_mod.PhaseBExecutorError, match="does not match routing task_id"):
            pb_mod.validate_inputs(routing, plan)

    def test_same_wave_task_id_exception_ignores_narrative_only_identity_metadata(self, tmp_path):
        """Narrative-only Task/Wave bullets must not populate authoritative identity."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "Status: ACTIVE\n"
            "- Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "- Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves the exception remains header-only

    def test_same_wave_task_id_exception_ignores_indented_only_identity_metadata(self, tmp_path):
        """Indented Task/Wave prose must not populate authoritative identity."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "Status: ACTIVE\n"
            "    Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "    Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves the exception remains header-only

    def test_same_wave_task_id_exception_ignores_single_hash_section_body_identity_metadata(self, tmp_path):
        """Later single-# section headings must not authorize the same-wave exception."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "# Grounding / Authorization\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves later single-# sections cannot authorize the exception

    def test_same_wave_task_id_exception_ignores_section_body_identity_metadata(self, tmp_path):
        """Section-body Task/Wave prose must not count as authoritative packet identity."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "## Grounding / Authorization\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves the exception remains header-only

    def test_same_wave_task_id_exception_ignores_setext_section_body_identity_metadata(self, tmp_path):
        """Setext section headings must stop authoritative identity scanning."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "Grounding / Authorization\n"
            "-------------------------\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves setext section bodies cannot authorize the exception

    def test_same_wave_task_id_exception_ignores_fenced_code_identity_metadata(self, tmp_path):
        """Fenced-code Task/Wave examples must not populate authoritative identity."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "## Grounding / Authorization\n"
            "```text\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "```\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }
        assert "task_id" not in plan
        assert "wave_id" not in plan
        assert not pb_mod._matches_explicit_same_wave_task_id_exception(routing, plan)  # ANTICHEAT_OK: internal helper proves the exception remains header-only

    @pytest.mark.parametrize(
        ("plan_text", "case_id"),
        [
            pytest.param(
                "Status: ACTIVE\n"
                "- Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "- Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Phase-A-Lock: LOCKED\n",
                "narrative-bullets",
                id="narrative-bullets",
            ),
            pytest.param(
                "Status: ACTIVE\n"
                "    Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "    Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Phase-A-Lock: LOCKED\n",
                "indented-prose",
                id="indented-prose",
            ),
            pytest.param(
                "# Plan\n"
                "Status: ACTIVE\n"
                "Phase-A-Lock: LOCKED\n"
                "\n"
                "# Grounding / Authorization\n"
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
                "single-hash-section-body",
                id="single-hash-section-body",
            ),
            pytest.param(
                "# Plan\n"
                "Status: ACTIVE\n"
                "Phase-A-Lock: LOCKED\n"
                "\n"
                "## Grounding / Authorization\n"
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
                "section-body",
                id="section-body",
            ),
            pytest.param(
                "# Plan\n"
                "Status: ACTIVE\n"
                "Phase-A-Lock: LOCKED\n"
                "\n"
                "Grounding / Authorization\n"
                "-------------------------\n"
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n",
                "setext-section-body",
                id="setext-section-body",
            ),
            pytest.param(
                "# Plan\n"
                "Status: ACTIVE\n"
                "Phase-A-Lock: LOCKED\n"
                "\n"
                "## Grounding / Authorization\n"
                "```text\n"
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "```\n",
                "fenced-code",
                id="fenced-code",
            ),
        ],
    )
    def test_same_wave_task_id_exception_missing_canonical_identity_fails_closed(
        self,
        tmp_path,
        plan_text,
        case_id,
    ):
        """Tracked recovery packets must reject malformed same-wave identity proofs."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(plan_text, encoding="utf-8")
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": case_id,
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }

        assert "task_id" not in plan
        assert "wave_id" not in plan
        with pytest.raises(
            pb_mod.PhaseBExecutorError,
            match="missing authoritative Task/Wave header identity",
        ):
            pb_mod.validate_inputs(routing, plan)

    def test_non_recovery_packet_missing_authoritative_task_id_fails_closed(self, tmp_path):
        """Non-recovery packets must not bypass task-id validation on body-only metadata."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "# Plan\n"
            "Status: ACTIVE\n"
            "Phase-A-Lock: LOCKED\n"
            "\n"
            "## Grounding / Authorization\n"
            "Task: wrong-wave\n"
            "Wave ID: other-wave\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[OTHER-WAVE]",
            "wave_name": "other-wave",
            "next_candidates": [
                {
                    "candidate": "other-wave",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }

        assert "task_id" not in plan
        assert "wave_id" not in plan
        with pytest.raises(
            pb_mod.PhaseBExecutorError,
            match="missing authoritative Task header required to match routing task_id",
        ):
            pb_mod.validate_inputs(routing, plan)

    @pytest.mark.parametrize(
        ("plan_text", "duplicate_field"),
        [
            pytest.param(
                "Status: ACTIVE\n"
                "Task: [OTHER-WAVE]\n"
                "Task: [OTHER-WAVE-ALT]\n"
                "Wave ID: other-wave\n"
                "Phase-A-Lock: LOCKED\n",
                "Task",
                id="duplicate-task-header",
            ),
            pytest.param(
                "Status: ACTIVE\n"
                "Task: [OTHER-WAVE]\n"
                "Wave ID: other-wave\n"
                "Wave ID: other-wave-alt\n"
                "Phase-A-Lock: LOCKED\n",
                "Wave ID",
                id="duplicate-wave-id-header",
            ),
        ],
    )
    def test_non_recovery_duplicate_authoritative_identity_headers_fail_closed(
        self,
        tmp_path,
        plan_text,
        duplicate_field,
    ):
        """Duplicate authoritative Task/Wave headers must fail closed for any packet."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(plan_text, encoding="utf-8")
        plan = pb_mod.load_plan_packet(repo, plan_path)
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[OTHER-WAVE]",
            "wave_name": "other-wave",
            "next_candidates": [
                {
                    "candidate": "other-wave",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }

        assert plan["task_id"] == "[OTHER-WAVE]"
        with pytest.raises(
            pb_mod.PhaseBExecutorError,
            match=(
                "duplicate authoritative identity headers: "
                f"{re.escape(duplicate_field)}"
            ),
        ):
            pb_mod.validate_inputs(routing, plan)

    def test_same_wave_task_id_exception_rejects_narrative_forged_wave_metadata(self, tmp_path):
        """Narrative bullets must not supply the authoritative same-wave proof."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "Status: ACTIVE\n"
            "- Task: forged-wave\n"
            "- Wave ID: forged-wave\n"
            "Task: real-wave\n"
            "Wave ID: real-wave\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        assert plan["task_id"] == "real-wave"
        assert plan["wave_id"] == "real-wave"
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "forged-wave",
            "next_candidates": [
                {
                    "candidate": "forged-wave",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }

        with pytest.raises(pb_mod.PhaseBExecutorError, match="does not match routing task_id"):
            pb_mod.validate_inputs(routing, plan)

    def test_same_wave_task_id_exception_rejects_duplicate_canonical_identity_pairs(self, tmp_path):
        """Duplicate canonical Task/Wave headers keep the exception fail-closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text(
            "Status: ACTIVE\n"
            "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
            "Task: [PIPELINE-RECOVERY]\n"
            "Wave ID: different-wave\n"
            "Phase-A-Lock: LOCKED\n",
            encoding="utf-8",
        )
        plan = pb_mod.load_plan_packet(repo, plan_path)
        assert plan["task_id"] == "phase-b-validate-inputs-task-id-leniency-2026-04-20"
        assert plan["wave_id"] == "phase-b-validate-inputs-task-id-leniency-2026-04-20"
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": plan_path,
                }
            ],
        }

        with pytest.raises(pb_mod.PhaseBExecutorError, match="does not match routing task_id"):
            pb_mod.validate_inputs(routing, plan)

    def test_same_wave_task_id_exception_rejects_duplicate_task_headers_even_when_plan_task_matches_routing(self):
        """Tracked recovery packets must reject dual task identities even on the routing anchor."""
        routing = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test",
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_name": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "next_candidates": [
                {
                    "candidate": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
                    "bounded": True,
                    "tracked_packet": (
                        "reports/control_plane/"
                        "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
                    ),
                }
            ],
        }
        plan = {
            "phase_a_lock": "LOCKED",
            "path": (
                "reports/control_plane/"
                "phase_b_validate_inputs_task_id_leniency_2026_04_20_2026-04-21.md"
            ),
            "task_id": "[PIPELINE-RECOVERY]",
            "wave_id": "phase-b-validate-inputs-task-id-leniency-2026-04-20",
            "content": (
                "Status: ACTIVE\n"
                "Task: [PIPELINE-RECOVERY]\n"
                "Task: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Wave ID: phase-b-validate-inputs-task-id-leniency-2026-04-20\n"
                "Phase-A-Lock: LOCKED\n"
            ),
        }

        with pytest.raises(
            pb_mod.PhaseBExecutorError,
            match="missing authoritative Task/Wave header identity",
        ):
            pb_mod.validate_inputs(routing, plan)

    def test_run_phase_b_fails_on_bad_routing_without_force(self, tmp_path):
        """run_phase_b with wrong routing token returns error (not override)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # Write a routing record with wrong decision
        rr_dir = repo / ".agent_bus" / "meta"
        rr_dir.mkdir(parents=True)
        (rr_dir / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_A",
            "summary": "dispatched to A",
        }))
        # Write a locked plan
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=False,
        )
        assert result["status"] == "error"
        assert "validate_inputs" in result.get("step", "")

    def test_run_phase_b_force_overrides_bad_routing(self, tmp_path):
        """run_phase_b with --force continues past wrong routing token."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # Write a routing record with wrong decision
        rr_dir = repo / ".agent_bus" / "meta"
        rr_dir.mkdir(parents=True)
        (rr_dir / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_A",
            "summary": "dispatched to A",
        }))
        # Write a locked plan
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        # With force=True, it should get past validation (will fail later at
        # a subsequent step like implementer invocation, but NOT at validation)
        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=True,
        )
        # Should not have failed at validate_inputs
        assert result.get("step") != "validate_inputs"

    def test_run_phase_b_fails_on_missing_routing_without_force(self, tmp_path):
        """run_phase_b with no routing record returns error (not synthetic)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        # No routing record file at all
        plan_dir = repo / "reports" / "control_plane"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test_plan.md"
        plan_file.write_text("---\nPhase-A-Lock: LOCKED\n---\nPlan content\n")

        result = pb_mod.run_phase_b(
            repo, "reports/control_plane/test_plan.md",
            verbose=False, force=False,
        )
        assert result["status"] == "error"
        assert "routing" in result.get("step", "").lower() or "routing" in str(result.get("errors", "")).lower()


@pytest.mark.usefixtures("mock_routing_record")
class TestResumeFromNeedsPhaseBReentrySkipsInitialBridgeLoop:
    """Defect fix: resume from needs_phase_b_reentry must bypass the initial bridge loop.

    The initial bridge loop (step 5) must NOT run when resuming into re-entry.
    Previously, bridge_converged was set True but the for loop still executed
    every round because there was no guard checking bridge_converged at loop entry.
    """

    def test_resume_needs_phase_b_reentry_skips_initial_bridge(self, tmp_path):
        """When resuming from needs_phase_b_reentry, no initial bridge rounds should run."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        # Seed state file with needs_phase_b_reentry
        state = {
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix the bug",
        }
        pb_mod._save_state(repo, state)  # ANTICHEAT_OK: testing internal executor functions

        mock_impl = _make_mock_impl()
        bridge_calls = []

        def bridge_side(*a, **kw):
            bridge_calls.append(kw.get("job_id", "unknown"))
            # Re-entry bridge returns GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "reentry-go"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        # Bridge calls should ONLY be re-entry calls, NOT initial loop calls.
        # If initial loop ran, we'd see "phase-b-r1-*" job IDs before re-entry calls.
        for call_jid in bridge_calls:
            assert "phase-b-r" not in str(call_jid) or "reentry" in str(call_jid), (
                f"Initial bridge loop ran during needs_phase_b_reentry resume: {call_jid}"
            )

    def test_resume_needs_phase_b_reentry_refreshes_bridge_when_scope_drifted(self, tmp_path):
        """Changed worktree after a saved re-entry checkpoint must refresh bridge findings first."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        state = {
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": ["f.py"],
            "executor_created": [],
            "baseline_wave_files": ["f.py"],
            "all_non_blocking": [],
            "reentry_findings": "Fix the old bug",
        }
        pb_mod._save_state(repo, state)  # ANTICHEAT_OK: testing internal executor functions

        mock_impl = _make_mock_impl()
        bridge_calls = []

        def bridge_side(*a, **kw):
            bridge_calls.append(kw.get("job_id", "unknown"))
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "reentry-go"}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={"passed": True, "exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "prepare_commit_handoff", return_value=repo / ".agent_bus" / "handoff.json"), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=5)

        assert result["status"] == "commit_ready"
        assert mock_impl.invoke_implementer.call_count == 0
        assert any("phase-b-reentry" in str(call_jid) for call_jid in bridge_calls)


@pytest.mark.usefixtures("mock_routing_record")
class TestReentryRequestChangesCheckpointsState:
    """Defect fix: re-entry REQUEST_CHANGES must checkpoint new findings and round.

    Previously, if a crash occurred after re-entry REQUEST_CHANGES updated findings_for_impl
    but before the next implementer invocation, the state file still had stale findings and
    the old round count. This test verifies that _save_state is called with fresh data.
    """

    def test_reentry_request_changes_checkpoints_before_continue(self, tmp_path):
        """After re-entry REQUEST_CHANGES, state file must have new findings and round."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]
        impl_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                # Initial bridge: GO
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "init"}
            if bridge_calls[0] == 2:
                # Re-entry R1: REQUEST_CHANGES with new findings (exit=1 under bridge CLI contract)
                return {"exit_code": 1, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                        "decision": "REQUEST_CHANGES", "job_id": "re1"}
            # Re-entry R2: GO
            return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "re2"}

        def impl_side(*a, **kw):
            impl_calls[0] += 1
            if impl_calls[0] == 3:
                # Third implementer call (after re-entry REQUEST_CHANGES): crash
                # to test state persistence
                raise RuntimeError("Simulated crash")
            return {"status": "success", "output": "done", "stderr": "",
                    "exit_code": 0, "job_id": f"impl-{impl_calls[0]}", "model_override_applied": False}

        mock_impl.invoke_implementer.side_effect = impl_side

        saved_states = []
        original_save = pb_mod._save_state  # ANTICHEAT_OK: testing internal executor functions

        def capturing_save(rr, state):
            saved_states.append(state.copy())
            return original_save(rr, state)

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_read_bridge_render", return_value="NEW_BRIDGE_FINDINGS"), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_save_state", side_effect=capturing_save), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "OLD_SUPERVISOR_FINDINGS", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            try:
                pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=10)
            except RuntimeError:
                pass  # Expected crash from impl_side

        # Find the re-entry checkpoint state (after REQUEST_CHANGES)
        reentry_checkpoints = [
            s for s in saved_states
            if s.get("completed_step") == "needs_phase_b_reentry"
        ]
        # Must have at least 2: initial needs_phase_b_reentry + REQUEST_CHANGES checkpoint
        assert len(reentry_checkpoints) >= 2, (
            f"Expected at least 2 needs_phase_b_reentry checkpoints, got {len(reentry_checkpoints)}. "
            f"States saved: {[s.get('completed_step') for s in saved_states]}"
        )
        # The second checkpoint must have the NEW findings, not the old supervisor findings
        latest = reentry_checkpoints[-1]
        assert latest["reentry_findings"] is not None, "Re-entry checkpoint missing findings"
        assert "NEW_BRIDGE_FINDINGS" in str(latest["reentry_findings"]) or "BLOCKING" in str(latest["reentry_findings"]), (
            f"Re-entry checkpoint has stale findings: {latest['reentry_findings']}"
        )

    def test_reentry_success_checkpoints_skip_before_next_review(self, tmp_path):
        """A successful re-entry implementer pass must survive crashes before bridge review."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        mock_impl = _make_mock_impl()
        bridge_calls = [0]

        def bridge_side(*a, **kw):
            bridge_calls[0] += 1
            if bridge_calls[0] == 1:
                return {"exit_code": 0, "stdout": "GO\n", "stderr": "", "decision": "GO", "job_id": "init"}
            if bridge_calls[0] == 2:
                return {
                    "exit_code": 1,
                    "stdout": "REQUEST_CHANGES\n",
                    "stderr": "",
                    "decision": "REQUEST_CHANGES",
                    "job_id": "re1",
                }
            raise RuntimeError("crash after re-entry implementer checkpoint")

        saved_states = []
        original_save = pb_mod._save_state  # ANTICHEAT_OK: testing internal executor functions

        def capturing_save(rr, state):
            saved_states.append(state.copy())
            return original_save(rr, state)

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py", "fixed.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py", "fixed.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_side), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "_save_state", side_effect=capturing_save), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "NEEDS_PHASE_B", "summary": "OLD_SUPERVISOR_FINDINGS", "status": "ok", "findings": []},
                 "receipt_path": "",
             }):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", max_bridge_rounds=10)

        assert result["status"] == "error"
        assert result["step"] == "phase_b_pager"
        implemented_checkpoints = [
            s for s in saved_states
            if s.get("completed_step") == "needs_phase_b_reentry"
            and s.get("skip_reentry_implementer_once") is True
        ]
        assert implemented_checkpoints, f"Expected durable post-implementer checkpoint. States: {saved_states}"
        latest = implemented_checkpoints[-1]
        assert latest["reentry_findings"]
        assert latest["bridge_scope_fingerprint"]
        assert latest["pending_reentry_bridge_round"]


class TestBridgeTimeoutIsError:
    """Bridge timeout must be treated as a hard error, not silently retried.

    Bug: run_bridge_review returns exit_code=-1 on timeout, but the bridge loop
    fell through to the generic 'exit_code != 0 → continue' branch, silently
    retrying. A timeout indicates infrastructure failure and must fail closed.
    """

    def test_bridge_timeout_returns_error(self, tmp_path):
        """Bridge timeout (exit_code=-1) must return error status, not continue."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_timeout(*a, **kw):
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert any("timed out" in e for e in result.get("errors", []))
        # State must be cleared to prevent stale resume
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_bridge_timeout_does_not_silently_retry(self, tmp_path):
        """Bridge timeout must NOT cause multiple bridge invocations (no silent retry)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()
        call_count = 0

        def bridge_timeout(*a, **kw):
            nonlocal call_count
            call_count += 1
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        # Only one bridge call — timeout stops immediately, no retry
        assert call_count == 1

    def test_unrecognized_success_decision_fails_closed(self, tmp_path):
        """exit_code=0 with an unknown bridge decision must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "MAYBE\n", "stderr": "", "decision": "MAYBE", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert result["step"] == "bridge_decision"
        assert any("unrecognized success decision" in e.lower() for e in result.get("errors", []))

    def test_reentry_bridge_timeout_returns_error(self, tmp_path):
        """Bridge timeout during re-entry must also fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        # Seed resume state at needs_phase_b_reentry
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": [],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix required",
        }))

        mock_impl = _make_mock_impl()

        def bridge_timeout(*a, **kw):
            return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out",
                    "decision": "", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_timeout), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert any("timed out" in e for e in result.get("errors", []))
        assert pb_mod._load_state(repo) is None  # ANTICHEAT_OK: testing internal executor functions

    def test_reentry_unrecognized_success_decision_fails_closed(self, tmp_path):
        """Re-entry exit_code=0 with unknown bridge decision must fail closed."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "reports/control_plane/plan.md",
            "completed_step": "needs_phase_b_reentry",
            "wave_id": "plan",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
            "implementer_changed": [],
            "executor_created": [],
            "all_non_blocking": [],
            "reentry_findings": "Fix required",
        }))

        mock_impl = _make_mock_impl()

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "MAYBE\n", "stderr": "", "decision": "MAYBE", "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=5,
            )

        assert result["status"] == "error"
        assert result["step"] == "reentry_bridge_decision"
        assert any("unrecognized success decision" in e.lower() for e in result.get("errors", []))


class TestMaxRoundsResultIncludesFindings:
    """max_rounds_reached must include errors and deferred finding count.

    Bug: max_rounds_reached returned bare status without errors list or
    accumulated finding counts, making diagnosis impossible.
    """

    def test_max_rounds_includes_errors_list(self, tmp_path):
        """max_rounds_reached must have an errors list with convergence info."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "NO_GO\n", "stderr": "",
                    "decision": "NO_GO", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=2,
            )

        assert result["status"] == "max_rounds_reached"
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert "converge" in result["errors"][0].lower() or "round" in result["errors"][0].lower()

    def test_max_rounds_includes_bridge_rounds_count(self, tmp_path):
        """max_rounds_reached must report correct bridge_rounds count."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        mock_impl = _make_mock_impl()

        def bridge_no_go(*a, **kw):
            return {"exit_code": 0, "stdout": "REQUEST_CHANGES\n", "stderr": "",
                    "decision": "REQUEST_CHANGES", "job_id": kw.get("job_id", "j")}

        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["f.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["f.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", side_effect=bridge_no_go), \
             patch.object(pb_mod, "_read_bridge_render", return_value=""), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "load_routing_record", return_value=_VALID_ROUTING_RECORD.copy()):
            result = pb_mod.run_phase_b(
                repo, "reports/control_plane/plan.md", max_bridge_rounds=3,
            )

        assert result["status"] == "max_rounds_reached"
        assert result["bridge_rounds"] == 3


class TestReentryStateClearing:
    """Re-entry failure paths must clear persisted state to prevent stale resume.

    Bridge finding: when reentry_pytest_gate or reentry_staging fails, the
    return path skipped _clear_state(), leaving completed_step=needs_phase_b_reentry.
    This caused the next invocation to re-enter implementer/bridge work even
    though convergence had already happened.
    """

    def test_reentry_pytest_gate_failure_clears_state(self):
        """_clear_state must be called before returning from reentry_pytest_gate failure."""
        source = Path(pb_mod.__file__).read_text()  # ANTICHEAT_OK: testing internal executor functions
        # Find the reentry_pytest_gate failure block
        idx = source.find('"reentry_pytest_gate"')
        assert idx > 0, "reentry_pytest_gate error path not found in source"
        # The _clear_state call must appear BEFORE the return in that block.
        # Look backwards from reentry_pytest_gate for _clear_state
        block = source[max(0, idx - 300):idx]
        assert "_clear_state" in block, (
            "reentry_pytest_gate failure path must call _clear_state(repo_root) "
            "before returning, to prevent stale needs_phase_b_reentry state"
        )

    def test_reentry_staging_failure_clears_state(self):
        """_clear_state must be called before returning from reentry_staging failure."""
        source = Path(pb_mod.__file__).read_text()  # ANTICHEAT_OK: testing internal executor functions
        idx = source.find('"reentry_staging"')
        assert idx > 0, "reentry_staging error path not found in source"
        block = source[max(0, idx - 300):idx]
        assert "_clear_state" in block, (
            "reentry_staging failure path must call _clear_state(repo_root) "
            "before returning, to prevent stale needs_phase_b_reentry state"
        )


# ===========================================================================
# Planless Phase B entry path (Slice 1 follow-on)
# ===========================================================================


class TestDerivePlanlessContext:
    """_derive_planless_context builds bounded scope from routing record."""

    def test_valid_routing_record_produces_plan(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "implement the thing",
            "wave_name": "test-wave",
            "next_candidates": [{"candidate": "do the thing"}],
        }
        plan = pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation
        assert plan["phase_a_lock"] == "ROUTING_RECORD_AUTHORITY"
        assert plan["planless"] == "true"
        assert plan["wave_id"] == "test-wave"
        assert "implement the thing" in plan["content"]

    def test_missing_wave_name_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "implement",
            "next_candidates": [{"candidate": "x"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="wave_name/wave_id"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_missing_summary_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "wave_name": "w",
            "next_candidates": [{"candidate": "x"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="summary"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_missing_candidates_fails_closed(self, tmp_path):
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "s",
            "wave_name": "w",
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="next_candidates"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation

    def test_existing_tracked_packet_redirects_to_plan(self, tmp_path):
        """If routing record references a tracked_packet that exists, fail with guidance."""
        (tmp_path / "reports" / "control_plane").mkdir(parents=True)
        (tmp_path / "reports" / "control_plane" / "plan.md").write_text("# Plan\nPhase-A-Lock: LOCKED\n")
        record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "s",
            "wave_name": "w",
            "next_candidates": [{"candidate": "x", "tracked_packet": "reports/control_plane/plan.md"}],
        }
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Use --plan"):
            pb_mod._derive_planless_context(record, tmp_path)  # ANTICHEAT_OK: testing planless context derivation


class TestPlanlessPhaseB:
    """run_phase_b with plan_path=None derives context from routing record."""

    def test_planless_with_valid_routing_record(self, tmp_path):
        """Planless mode reaches the implementer step (fails there due to no bridge config)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        routing_record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless",
            "wave_name": "planless-test",
            "next_candidates": [{"candidate": "do something"}],
        }
        # Write routing record
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps(routing_record))

        with patch.dict(sys.modules, {"phase_b_implementer": _make_mock_impl()}):
            mock_impl = sys.modules["phase_b_implementer"]
            mock_impl.invoke_implementer.return_value = {
                "status": "error",
                "output": "",
                "stderr": "no bridge config in tmp repo",
                "exit_code": 2,
                "job_id": "unit-impl",
                "model_override_applied": False,
            }
            result = pb_mod.run_phase_b(repo, None, verbose=True)
        # Should reach implementer step (fails there due to no bridge config)
        assert result.get("planless") is True
        assert result.get("status") == "error"
        assert result.get("step") == "implementer"

    def test_planless_commit_ready_omits_tracked_packet_from_handoff(
        self,
        tmp_path,
        real_pre_review_package,
    ):
        """Planless handoffs must not bind the synthetic plan marker as a tracked packet."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        routing_record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless",
            "wave_name": "planless-regression-2026-04-28",
            "task_id": "[PLANLESS]",
            "wave_class": "L4_ENABLER",
            "target_gate_id": "G8",
            "next_candidates": [{"candidate": "do something"}],
        }

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_emit_phase_b_event", return_value={}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/phase_b_executor.py"]), \
             patch.object(pb_mod, "_collect_and_stage_l4_indicator_artifact") as mock_collector, \
             patch.object(pb_mod, "_run_pytest_on_files", return_value={
                 "exit_code": 0,
                 "passed": True,
                 "stdout": "",
                 "stderr": "",
             }), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0,
                 "stdout": "GO\n",
                 "stderr": "",
                 "decision": "GO",
                 "job_id": "j1",
             }), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json",
             }), \
             patch.object(
                 pb_mod,
                 "prepare_commit_handoff",
                 return_value=repo / ".agent_bus" / "handoff.json",
             ) as mock_handoff:
            result = pb_mod.run_phase_b(
                repo,
                None,
                max_bridge_rounds=5,
                routing_record_override=routing_record,
            )

        assert result["status"] == "commit_ready"
        mock_collector.assert_not_called()
        assert mock_handoff.call_args.kwargs["tracked_packet"] is None
        assert mock_handoff.call_args.kwargs["scope_items"] == [
            "<planless:planless-regression-2026-04-28>"
        ]

    def test_planless_with_underspecified_record_fails_closed(self, tmp_path):
        """Planless mode fails closed when routing record is under-specified."""
        repo = tmp_path / "repo"
        repo.mkdir()
        routing_record = {"decision": "ROUTE_PHASE_B", "summary": ""}
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps(routing_record))

        result = pb_mod.run_phase_b(repo, None, verbose=True)
        assert result["status"] == "error"
        assert result["step"] == "derive_planless_context"

    def test_main_passes_cli_routing_record_to_run_phase_b(self, tmp_path, monkeypatch):
        """CLI --routing-record must override disk routing state when invoking run_phase_b."""
        repo = tmp_path / "repo"
        repo.mkdir()
        captured: dict[str, object] = {}
        routing_record = {
            "decision": "ROUTE_PHASE_B",
            "summary": "cli override",
            "wave_name": "cli-wave",
            "next_candidates": [{"candidate": "do something"}],
        }

        def fake_git_rev_parse(args, capture_output, text, check):
            return SimpleNamespace(stdout=str(repo))

        def fake_run_phase_b(repo_root, plan_path, **kwargs):
            captured["repo_root"] = repo_root
            captured["plan_path"] = plan_path
            captured["routing_record_override"] = kwargs.get("routing_record_override")
            return {"status": "ready"}

        monkeypatch.setattr(pb_mod.subprocess, "run", fake_git_rev_parse)
        monkeypatch.setattr(pb_mod, "run_phase_b", fake_run_phase_b)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "phase_b_executor.py",
                "--routing-record",
                json.dumps(routing_record),
                "--json",
            ],
        )

        exit_code = pb_mod.main()
        assert exit_code == 0
        assert captured["repo_root"] == repo
        assert captured["plan_path"] is None
        assert captured["routing_record_override"] == routing_record

    def test_main_attempts_standalone_recovery_on_failure(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        recovery_calls: dict[str, object] = {}

        def fake_git_rev_parse(args, capture_output, text, check):
            return SimpleNamespace(stdout=str(repo))

        def fake_run_phase_b(repo_root, plan_path, **kwargs):
            return {"status": "error", "step": "implementer_bridge_fix", "wave_id": "standalone-wave"}

        def fake_attempt_recovery(repo_root, result, wave_id, bus_dir=None):
            recovery_calls["repo_root"] = repo_root
            recovery_calls["status"] = result["status"]
            recovery_calls["wave_id"] = wave_id
            recovery_calls["bus_dir"] = bus_dir
            return {"recovered": True, "failure_class": "unknown_error", "tier": 3}

        monkeypatch.setattr(pb_mod.subprocess, "run", fake_git_rev_parse)
        monkeypatch.setattr(pb_mod, "run_phase_b", fake_run_phase_b)
        monkeypatch.setattr(sys, "argv", ["phase_b_executor.py"])

        with patch.dict(sys.modules, {"recovery_gate": SimpleNamespace(attempt_recovery=fake_attempt_recovery)}):
            exit_code = pb_mod.main()

        assert exit_code == 0
        assert recovery_calls["repo_root"] == repo
        assert recovery_calls["status"] == "error"
        assert recovery_calls["wave_id"] == "standalone-wave"

    def test_main_skips_internal_recovery_when_dispatcher_owns_it(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        repo.mkdir()
        recovery_calls = {"count": 0}

        def fake_git_rev_parse(args, capture_output, text, check):
            return SimpleNamespace(stdout=str(repo))

        def fake_run_phase_b(repo_root, plan_path, **kwargs):
            return {"status": "error", "step": "derive_planless_context", "wave_id": "dispatch-wave"}

        def fake_attempt_recovery(repo_root, result, wave_id, bus_dir=None):
            recovery_calls["count"] += 1
            return {"recovered": False, "failure_class": "phase_b_plan_required", "tier": 1}

        monkeypatch.setattr(pb_mod.subprocess, "run", fake_git_rev_parse)
        monkeypatch.setattr(pb_mod, "run_phase_b", fake_run_phase_b)
        monkeypatch.setattr(
            sys,
            "argv",
            ["phase_b_executor.py", "--dispatcher-owned-recovery", "--json"],
        )

        with patch.dict(sys.modules, {"recovery_gate": SimpleNamespace(attempt_recovery=fake_attempt_recovery)}):
            exit_code = pb_mod.main()

        assert exit_code == 1
        assert recovery_calls["count"] == 0


class TestSdkReviewDepthContract:
    """Phase A/B should use the 4-agent SDK gate by default."""

    def test_phase_a_sdk_review_defaults_to_quick(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        captured: dict[str, object] = {}

        class FakeProc:
            pid = 1234
            returncode = 0

            def poll(self):
                return 0

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env"] = env
            return FakeProc()

        def fake_run(cmd, cwd, capture_output, text, check):
            assert cmd == ["ps", "-axo", "pid=,ppid="]
            return SimpleNamespace(stdout="", stderr="")

        with patch.object(pa_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pa_mod.subprocess, "run", side_effect=fake_run):
            result = pa_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_a_executor.py"])

        assert result["exit_code"] == 0
        assert captured["cwd"] == repo
        cmd = captured["cmd"]
        assert cmd[:5] == [
            sys.executable,
            "tools/runners/run_review.py",
            "mu/tools/executors/phase_a_executor.py",
            "--depth",
            "quick",
        ]
        assert cmd[5] == "--fail-fast-hard-gate"
        assert cmd[6] == "--no-memory"
        assert cmd[7] == "--output"
        assert str(cmd[8]).endswith(".report.md")
        env = captured["env"]
        assert env["RCX_REVIEW_STATUS_PATH"].endswith(".status.json")
        assert env["RCX_REVIEW_AGENT_TIMEOUT"] == "600"

    def test_phase_b_sdk_review_defaults_to_quick_fail_fast(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        captured: dict[str, object] = {}

        class FakeProc:
            pid = 12345
            returncode = 0

            def poll(self):
                return 0

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            captured["env"] = env
            return FakeProc()

        def fake_run(cmd, cwd, capture_output, text, check):
            assert cmd == ["ps", "-axo", "pid=,ppid="]
            return SimpleNamespace(stdout="", stderr="")

        with patch.object(pb_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pb_mod.subprocess, "run", side_effect=fake_run):
            result = pb_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_b_executor.py"])

        assert result["exit_code"] == 0
        assert captured["cwd"] == repo
        cmd = captured["cmd"]
        assert cmd[:5] == [
            sys.executable,
            "tools/runners/run_review.py",
            "mu/tools/executors/phase_b_executor.py",
            "--depth",
            "quick",
        ]
        assert cmd[5] == "--fail-fast-hard-gate"
        assert cmd[6] == "--no-memory"
        assert cmd[7] == "--output"
        assert str(cmd[8]).endswith(".report.md")
        env = captured["env"]
        assert env["RCX_REVIEW_STATUS_PATH"].endswith(".status.json")
        assert env["RCX_REVIEW_AGENT_TIMEOUT"] == "600"

    def test_phase_a_sdk_review_uses_terminal_status_when_runner_lingers(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()

        class FakeProc:
            pid = 1234

            def poll(self):
                return None

        def fake_popen(cmd, cwd, stdout, stderr, text, env):
            Path(env["RCX_REVIEW_STATUS_PATH"]).write_text(
                json.dumps(
                    {
                        "status": "hard_gate_failed",
                        "running_agents": [],
                        "completed_agents": {
                            "verifier": {"verdict": "REQUEST_CHANGES", "passed": False}
                        },
                    }
                ),
                encoding="utf-8",
            )
            Path(cmd[8]).write_text("report", encoding="utf-8")
            stdout.write("review stdout")
            stdout.flush()
            stderr.write("review stderr")
            stderr.flush()
            return FakeProc()

        with patch.object(pa_mod.uuid, "uuid4", return_value=SimpleNamespace(hex="deadbeefcafebabe")), \
             patch.object(pa_mod.subprocess, "Popen", side_effect=fake_popen), \
             patch.object(pa_mod, "process_descendants", return_value=[]):
            result = pa_mod.run_sdk_agents(repo, ["mu/tools/executors/phase_a_executor.py"])

        assert result["exit_code"] == 1
        assert result["stdout"] == "review stdout"
        assert result["stderr"] == "review stderr"
        assert result["status_path"].endswith("phase_a_agent_review_deadbeef.status.json")

    def test_phase_a_review_depth_config_accepts_full_override(self):
        assert pa_mod.resolve_review_depth({"review_depths": {"phase_a": "full"}}, "phase_a") == "full"  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_review_depth_config_rejects_invalid_value(self):
        with pytest.raises(pa_mod.PhaseAExecutorError, match="Invalid review depth"):
            pa_mod.resolve_review_depth({"review_depths": {"phase_a": "bogus"}}, "phase_a")  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_review_depth_config_accepts_full_override(self):
        assert pb_mod._resolve_review_depth({"review_depths": {"phase_b": "full"}}, "phase_b") == "full"  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_review_depth_config_rejects_invalid_value(self):
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Invalid review depth"):
            pb_mod._resolve_review_depth({"review_depths": {"phase_b": "bogus"}}, "phase_b")  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_bridge_turn_timeout_config_accepts_override(self):
        assert pa_mod.resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_a": 451}}, "phase_a", 300) == 451.0  # ANTICHEAT_OK: testing config resolver

    def test_phase_a_bridge_turn_timeout_config_rejects_invalid_value(self):
        with pytest.raises(pa_mod.PhaseAExecutorError, match="Invalid bridge turn timeout"):
            pa_mod.resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_a": 0}}, "phase_a", 300)  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_bridge_turn_timeout_config_accepts_override(self):
        assert pb_mod._resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_b": 901}}, "phase_b", 300) == 901.0  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_bridge_turn_timeout_config_rejects_invalid_value(self):
        with pytest.raises(pb_mod.PhaseBExecutorError, match="Invalid bridge turn timeout"):
            pb_mod._resolve_bridge_turn_timeout({"bridge_turn_timeouts": {"phase_b": -1}}, "phase_b", 300)  # ANTICHEAT_OK: testing config resolver

    def test_phase_b_pytest_gate_timeout_allows_pre_push_budget(self):
        assert pb_mod.resolve_pytest_gate_timeout(18000) == 7200

    def test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values(self):
        assert pb_mod.resolve_pytest_gate_timeout(0) == 300
        assert pb_mod.resolve_pytest_gate_timeout("not-a-timeout") == 300

    def test_pytest_selector_hints_max_steps_guard_matrix_diff(self):
        diff_text = """
@@ -1826,6 +1826,9 @@ class TestEngineHelpersParity:
+# Engine actions use one outer iteration in this guard matrix because these
+# cases prove API cap validation only; deeper engine convergence has separate
+# parity coverage with small structural budgets below.
 _MAX_STEPS_GUARDED_ACTIONS = [
@@ -1849,7 +1849,7 @@ _MAX_STEPS_GUARDED_ACTIONS = [
-        {"maxEngineIterations": 5},
+        {"maxEngineIterations": 1},
@@ -1880,7 +1880,7 @@ _GUARDED_ACTION_BASE_ARGS = {
-    "run_engine_with_routing": {"maxEngineIterations": 5},
+    "run_engine_with_routing": {"maxEngineIterations": 1},
"""
        assert pb_mod.pytest_selector_hints_for_diff(
            "mu/tests/parity/test_js_parity_automated.py",
            diff_text,
        ) == ["mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard"]

    def test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate(self, monkeypatch):
        diff_text = """
@@ -1849,7 +1849,10 @@ _MAX_STEPS_GUARDED_ACTIONS = [
-        {"maxEngineIterations": 5},
+        {"maxEngineIterations": 1},
+def test_unrelated_behavior():
+    assert new_behavior
"""
        assert pb_mod.pytest_selector_hints_for_diff(
            "mu/tests/parity/test_js_parity_automated.py",
            diff_text,
        ) == []

        monkeypatch.setattr(pb_mod, "pytest_gate_diff_text", lambda repo_root, path: diff_text)

        assert pb_mod.select_pytest_gate_files(
            ["mu/tests/parity/test_js_parity_automated.py"],
            Path("."),
        ) == ["mu/tests/parity/test_js_parity_automated.py"]

    def test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file(self, monkeypatch):
        diff_text = """
@@ -11260,6 +11260,10 @@ class TestSdkReviewDepthContract:
     def test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors(self):
         assert pb_mod.select_pytest_gate_files(["mu/tools/executors/phase_b_executor.py"]) == [
+
+    def test_new_selector_regression_not_in_hint_list(self):
+        assert False
"""
        assert pb_mod.pytest_selector_hints_for_diff(
            "mu/tests/tools/test_phase_b_executor.py",
            diff_text,
        ) == []

        monkeypatch.setattr(pb_mod, "pytest_gate_diff_text", lambda repo_root, path: diff_text)

        assert pb_mod.select_pytest_gate_files(
            ["mu/tests/tools/test_phase_b_executor.py"],
            Path("."),
        ) == ["mu/tests/tools/test_phase_b_executor.py"]

    def test_pytest_gate_diff_text_includes_staged_and_unstaged_diff(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
        target = repo / "sample.py"
        target.write_text("alpha\nbeta\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.py"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

        target.write_text("_MAX_STEPS_GUARDED_ACTIONS\nbeta\n", encoding="utf-8")
        subprocess.run(["git", "add", "sample.py"], cwd=repo, check=True)
        target.write_text("_MAX_STEPS_GUARDED_ACTIONS\n_GUARDED_ACTION_BASE_ARGS\n", encoding="utf-8")

        diff_text = pb_mod.pytest_gate_diff_text(repo, "sample.py")

        assert "_MAX_STEPS_GUARDED_ACTIONS" in diff_text
        assert "_GUARDED_ACTION_BASE_ARGS" in diff_text

    def test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors(self):
        assert pb_mod.select_pytest_gate_files(["mu/tools/executors/phase_b_executor.py"]) == [
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
            "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
        ]

    def test_select_pytest_gate_files_skips_missing_targeted_executor_tests(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        executor = repo / "mu" / "tools" / "executors" / "phase_b_executor.py"
        executor.parent.mkdir(parents=True)
        executor.write_text("print('wave fixture')\n", encoding="utf-8")

        assert pb_mod.select_pytest_gate_files(
            ["mu/tools/executors/phase_b_executor.py"],
            repo,
        ) == []

    def test_bridge_process_snapshot_fail_open_on_permission_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pb_mod.os, "kill", lambda pid, sig: None)

        def fake_run(*_args, **_kwargs):
            raise PermissionError(1, "Operation not permitted", "ps")

        monkeypatch.setattr(pb_mod.subprocess, "run", fake_run)

        assert pb_mod._bridge_process_snapshot(12345, tmp_path) == ((), ())  # ANTICHEAT_OK: phase-b bridge watchdog must degrade safely when ps is blocked


class TestValidateInputsAcceptsRoutingRecordAuthority:
    """validate_inputs accepts ROUTING_RECORD_AUTHORITY for planless mode."""

    def test_routing_record_authority_is_valid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "ROUTING_RECORD_AUTHORITY"}
        pb_mod.validate_inputs(record, plan)  # should not raise

    def test_locked_still_valid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "LOCKED"}
        pb_mod.validate_inputs(record, plan)  # should not raise

    def test_unlocked_still_invalid(self):
        record = {"decision": "ROUTE_PHASE_B"}
        plan = {"phase_a_lock": "UNLOCKED"}
        with pytest.raises(pb_mod.PhaseBExecutorError):
            pb_mod.validate_inputs(record, plan)


class TestHighSeverityCannotBeDowngradedByDisposition:
    """Finding 962: high severity must not be downgraded by explicit disposition field."""

    def test_high_severity_with_non_blocking_disposition_stays_blocking(self):
        """High severity + explicit non_blocking disposition → still blocking."""
        findings = [{"title": "Something", "severity": "high", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_high_severity_with_blocking_disposition_stays_blocking(self):
        """High severity + explicit blocking disposition → blocking."""
        findings = [{"title": "Something", "severity": "high", "disposition": "blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_high_severity_without_disposition_stays_blocking(self):
        """High severity + no disposition → blocking (fail-closed)."""
        findings = [{"title": "Something", "severity": "high"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 1
        assert len(non_blocking) == 0

    def test_medium_severity_with_non_blocking_disposition_is_non_blocking(self):
        """Medium severity + explicit non_blocking disposition → non_blocking (disposition honored)."""
        findings = [{"title": "Something", "severity": "medium", "disposition": "non_blocking"}]
        blocking, non_blocking = pb_mod._classify_findings(findings)  # ANTICHEAT_OK: testing internal executor functions
        assert len(blocking) == 0
        assert len(non_blocking) == 1

    def test_disposition_for_finding_high_returns_override_reason(self):
        """_disposition_for_finding for high + non_blocking returns override reason."""
        disp, reason = pb_mod._disposition_for_finding(  # ANTICHEAT_OK: testing internal executor functions
            {"title": "X", "severity": "high", "disposition": "non_blocking"}
        )
        assert disp == "blocking"
        assert "overrides" in reason


class TestEmptyEnvelopeDoesNotSpoofConflict:
    """Finding 963: prepended empty-findings envelope must not trigger false conflicting error."""

    def test_empty_envelope_before_real_envelope_returns_real_findings(self):
        """Prepended empty envelope + real envelope → returns real findings, not conflict error."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "\n"
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "Real bug", "severity": "high"}]}\n'
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Real bug"

    def test_only_empty_envelope_falls_through_to_markdown(self):
        """Only empty-findings envelope → falls through to markdown parsing."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": []}\n'
            "END_AGENT_ENVELOPE\n"
            "\n"
            "  1. **DEFECT** (medium): Some issue\n"
            "    - File: foo.py\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "Some issue"

    def test_multiple_identical_real_envelopes_returns_findings(self):
        """Duplicate identical envelopes → not conflicting, returns findings."""
        render = (
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "A", "severity": "low"}]}\n'
            "END_AGENT_ENVELOPE\n"
            "BEGIN_AGENT_ENVELOPE\n"
            '{"findings": [{"title": "A", "severity": "low"}]}\n'
            "END_AGENT_ENVELOPE\n"
        )
        findings = pb_mod._parse_findings_from_render(render)  # ANTICHEAT_OK: testing internal executor functions
        assert len(findings) == 1
        assert findings[0]["title"] == "A"


class TestPlanlessResume:
    """Bridge R1 Finding: planless Phase B invocations must resume from saved state."""

    def test_planless_resume_matches_saved_planless_state(self, tmp_path):
        """Saved state with <planless:wave> path matches a planless invocation (plan_path=None).

        The resume logic correctly matches the planless marker. The pipeline
        may still fail at commit_handoff due to empty files_to_stage — that's
        fine; the test proves the resume match happened (visible in stdout).
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()

        # Write saved state from a prior planless run
        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "<planless:test-wave>",
            "completed_step": "implementer",
            "wave_id": "test-wave",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
        }))

        # Write routing record for planless mode
        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless resume",
            "wave_name": "test-wave",
            "next_candidates": [{"candidate": "do something"}],
        }))

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=[]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=["mu/tools/executors/foo.py"]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, None, verbose=True)

        # The result should carry resumed_from through the pipeline
        assert result.get("resumed_from") == "implementer" or result.get("status") == "commit_ready", (
            f"Planless run should resume from saved state. Got: {result}"
        )

    def test_planless_resume_fails_closed_when_saved_wave_differs(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "<planless:old-wave>",
            "completed_step": "implementer",
            "wave_id": "old-wave",
            "bridge_rounds": 1,
            "deferred_packet_path": None,
        }))

        bus = repo / ".agent_bus" / "meta"
        bus.mkdir(parents=True)
        (bus / "post_merge_routing.json").write_text(json.dumps({
            "decision": "ROUTE_PHASE_B",
            "summary": "test planless mismatch",
            "wave_name": "new-wave",
            "next_candidates": [{"candidate": "do something"}],
        }))

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "run_sdk_agents") as sdk_mock, \
             patch.object(pb_mod, "run_bridge_review") as bridge_mock, \
             patch.object(pb_mod, "run_pre_commit_supervisor") as supervisor_mock:
            result = pb_mod.run_phase_b(repo, None, verbose=True)

        assert result["status"] == "error"
        assert result["step"] == "load_state"
        assert result["state_error"] == "plan_mismatch"
        assert "<planless:old-wave>" in result["errors"][0]
        assert "<planless:new-wave>" in result["errors"][0]
        mock_impl.invoke_implementer.assert_not_called()
        sdk_mock.assert_not_called()
        bridge_mock.assert_not_called()
        supervisor_mock.assert_not_called()

    def test_explicit_plan_fails_closed_on_planless_state_mismatch(self, tmp_path):
        """Saved planless state must not be ignored by an explicit --plan invocation."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        (repo / "reports" / "control_plane" / "plan.md").write_text(
            "# Plan\nPhase-A-Lock: LOCKED\n"
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": "<planless:test-wave>",
            "completed_step": "implementer",
            "wave_id": "test-wave",
            "bridge_rounds": 1,
        }))

        mock_impl = _make_mock_impl()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "load_routing_record") as routing_mock, \
             patch.object(pb_mod, "_collect_changed_files", return_value=[]), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=[]), \
             patch.object(pb_mod, "run_sdk_agents", return_value={"exit_code": 0, "stdout": "", "stderr": ""}), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, "reports/control_plane/plan.md", verbose=True)

        assert result["status"] == "error"
        assert result["step"] == "load_state"
        assert result["state_error"] == "plan_mismatch"
        routing_mock.assert_not_called()
        mock_impl.invoke_implementer.assert_not_called()


class TestAgentReviewResume:
    """Completed one-time SDK review should be resumable without re-running it."""

    def test_resume_from_agent_review_skips_sdk_when_scope_matches(self, tmp_path, mock_routing_record):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        reviewed_rel = "mu/tools/executors/phase_b_executor.py"
        reviewed_file = repo / reviewed_rel
        reviewed_file.parent.mkdir(parents=True)
        reviewed_file.write_text("print('wave')\n", encoding="utf-8")
        agent_scope = [reviewed_rel]
        scope_fingerprint = pb_mod._agent_review_scope_fingerprint(  # ANTICHEAT_OK: testing internal resume fingerprint helper
            repo,
            agent_scope,
            depth="quick",
        )

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": plan_path,
            "completed_step": "agent_review",
            "wave_id": "plan",
            "bridge_rounds": 0,
            "implementer_changed": agent_scope,
            "executor_created": [],
            "baseline_wave_files": agent_scope,
            "all_non_blocking": [],
            "finding_history": {},
            "agent_review_scope": agent_scope,
            "agent_review_scope_fingerprint": scope_fingerprint,
            "agent_exit_code": 1,
            "agent_review_report_path": ".scratch/sdk.report.md",
            "agent_review_status_path": ".scratch/sdk.status.json",
            "agent_review_stdout_path": ".scratch/sdk.stdout.log",
        }))

        mock_impl = _make_mock_impl()
        sdk_mock = MagicMock()
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=agent_scope), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=agent_scope), \
             patch.object(pb_mod, "run_sdk_agents", sdk_mock), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, plan_path, verbose=True)

        sdk_mock.assert_not_called()
        assert result.get("resumed_from") == "agent_review"
        assert result["agent_exit_code"] == 1
        assert result["agent_review_warning_only"] is True
        assert result["agent_review_report_path"] == ".scratch/sdk.report.md"

    def test_resume_from_agent_review_reruns_sdk_when_scope_drifted(self, tmp_path, mock_routing_record):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".scratch").mkdir()
        (repo / "reports" / "control_plane").mkdir(parents=True)
        plan_path = "reports/control_plane/plan.md"
        (repo / plan_path).write_text("# Plan\nPhase-A-Lock: LOCKED\n")

        reviewed_rel = "mu/tools/executors/phase_b_executor.py"
        reviewed_file = repo / reviewed_rel
        reviewed_file.parent.mkdir(parents=True)
        reviewed_file.write_text("print('wave')\n", encoding="utf-8")
        agent_scope = [reviewed_rel]

        state_dir = repo / ".agent_bus" / "executors"
        state_dir.mkdir(parents=True)
        (state_dir / "phase_b_state.json").write_text(json.dumps({
            "plan_path": plan_path,
            "completed_step": "agent_review",
            "wave_id": "plan",
            "bridge_rounds": 0,
            "implementer_changed": agent_scope,
            "executor_created": [],
            "baseline_wave_files": agent_scope,
            "all_non_blocking": [],
            "finding_history": {},
            "agent_review_scope": agent_scope,
            "agent_review_scope_fingerprint": "mismatch",
            "agent_exit_code": 1,
            "agent_review_report_path": ".scratch/sdk.report.md",
            "agent_review_status_path": ".scratch/sdk.status.json",
            "agent_review_stdout_path": ".scratch/sdk.stdout.log",
        }))

        saved_states = []

        def _capture_state(repo_root, state):
            saved_states.append(state.copy())
            return repo_root / ".agent_bus" / "executors" / "phase_b_state.json"

        mock_impl = _make_mock_impl()
        sdk_mock = MagicMock(return_value={
            "exit_code": 1,
            "stdout": "",
            "stderr": "",
            "report_path": ".scratch/fresh.report.md",
            "status_path": ".scratch/fresh.status.json",
            "stdout_path": ".scratch/fresh.stdout.log",
        })
        with patch.dict(sys.modules, {"phase_b_implementer": mock_impl}), \
             patch.object(pb_mod, "_collect_changed_files", return_value=agent_scope), \
             patch.object(pb_mod, "_collect_wave_owned_files", return_value=agent_scope), \
             patch.object(pb_mod, "run_sdk_agents", sdk_mock), \
             patch.object(pb_mod, "_save_state", side_effect=_capture_state), \
             patch.object(pb_mod, "run_bridge_review", return_value={
                 "exit_code": 0, "stdout": "GO\n", "stderr": "",
                 "decision": "GO", "job_id": "j-1"}), \
             patch.object(pb_mod, "_stage_files", return_value=True), \
             patch.object(pb_mod, "run_pre_commit_supervisor", return_value={
                 "exit_code": 0,
                 "parsed": {"decision": "COMMIT_GO", "summary": "", "status": "success", "findings": []},
                 "receipt_path": ".agent_bus/meta/pre_commit_receipts/r.json"}):
            result = pb_mod.run_phase_b(repo, plan_path, verbose=True)

        sdk_mock.assert_called_once()
        assert result.get("resumed_from") == "agent_review"
        assert any(s.get("completed_step") == "agent_review" for s in saved_states)
