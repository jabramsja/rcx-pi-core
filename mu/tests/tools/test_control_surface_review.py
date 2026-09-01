"""Tests for control-surface reviewer hardening.

Covers:
1. Control-surface invariant checker detects all 5 invariant classes
2. Checker skips when no control-surface files are touched
3. Bridge reviewer prompt activates control-surface mode for relevant files
4. Bridge reviewer prompt does NOT activate for non-control-surface files
5. Pre-commit supervisor Gate 9 wires the checker correctly
6. Existing Phase B fixes still hold (regression guard)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


cs_mod = load_module(
    "check_control_surface_invariants",
    REPO_ROOT / "tools" / "checks" / "check_control_surface_invariants.py",
)


class TestControlSurfaceDetection:
    """Checker correctly identifies control-surface files."""

    _tc = staticmethod(cs_mod._touches_control_surface)  # ANTICHEAT_OK: testing checker internal API

    def test_executor_file_is_control_surface(self):
        assert self._tc(["mu/tools/executors/phase_b_executor.py"])

    def test_implementer_file_is_control_surface(self):
        assert self._tc(["mu/tools/executors/phase_b_implementer.py"])

    def test_supervisor_file_is_control_surface(self):
        assert self._tc(["mu/tools/agents/meta_bridge_supervisor.py"])

    def test_client_file_is_control_surface(self):
        assert self._tc(["mu/tools/agents/meta_bridge_client.py"])

    def test_regular_file_is_not_control_surface(self):
        assert not self._tc(["mu/host/python/rcx_pi/selfhost/step_mu.py"])

    def test_test_file_is_not_control_surface(self):
        assert not self._tc(["mu/tests/tools/test_phase_b_executor.py"])

    def test_mu_bridge_supervisor_is_control_surface(self):
        assert self._tc(["mu/tools/agents/bridge_supervisor.py"])

    def test_tools_bridge_supervisor_is_control_surface(self):
        assert self._tc(["tools/agents/bridge_supervisor.py"])

    def test_mu_runner_is_control_surface(self):
        assert self._tc(["mu/tools/runners/run_review.py"])

    def test_mu_shared_agent_utils_is_control_surface(self):
        assert self._tc(["mu/tools/runners/shared_agent_utils.py"])

    def test_mu_closeout_attestation_is_control_surface(self):
        assert self._tc(["mu/tools/checks/check_closeout_attestation.py"])

    def test_mu_invariant_checker_is_control_surface(self):
        assert self._tc(["mu/tools/checks/check_control_surface_invariants.py"])

    def test_executor_config_is_control_surface(self):
        assert self._tc(["mu/tools/executors/executor_config.json"])

    def test_executor_common_is_control_surface(self):
        assert self._tc(["mu/tools/executors/executor_common.py"])

    def test_executor_dispatch_is_control_surface(self):
        assert self._tc(["mu/tools/executors/executor_dispatch.py"])

    def test_bridge_reviewer_prompt_is_control_surface(self):
        assert self._tc(["mu/tools/agents/templates/bridge_reviewer_prompt.txt"])

    def test_bridge_adapters_is_control_surface(self):
        assert self._tc(["mu/tools/agents/bridge_adapters.py"])

    def test_tools_bridge_adapters_is_control_surface(self):
        assert self._tc(["tools/agents/bridge_adapters.py"])

    def test_dotslash_prefix_activates(self):
        assert self._tc(["./mu/tools/executors/phase_b_executor.py"])

    def test_dot_segment_activates(self):
        assert self._tc(["mu/tools/executors/./phase_b_executor.py"])

    def test_mixed_list_detects_control_surface(self):
        assert cs_mod._touches_control_surface([  # ANTICHEAT_OK: testing checker internal API
            "README.md",
            "mu/tools/executors/commit_executor.py",  # control surface
        ])

    def test_claude_md_activates_control_surface(self):
        assert self._tc(["CLAUDE.md"])

    def test_meta_bridge_task_activates_control_surface(self):
        assert self._tc(["mu/tools/agents/templates/meta_bridge_task.txt"])


class TestBridgeReviewerPromptContract:
    """Bridge reviewer prompt must not invite bootstrap recap before the envelope."""

    def test_bridge_reviewer_prompt_requires_silent_bootstrap_read(self):
        prompt = (REPO_ROOT / "tools" / "agents" / "templates" / "bridge_reviewer_prompt.txt").read_text()
        assert "read FOUNDER_SESSION_BOOTSTRAP.md in the repo root silently" in prompt
        assert "Do not summarize it." in prompt
        assert "briefly summarizing the key behavioral and procedural rules" not in prompt
        assert "brief bootstrap summary" not in prompt


class TestInvariantChecksOnRealRepo:
    """Run invariant checks against the actual repo to verify current truth."""

    def test_inv1_implementer_not_review_mode(self):
        passed, msg = cs_mod.check_implementer_not_review_mode(REPO_ROOT)
        assert passed, f"INV-1 failed: {msg}"

    def test_inv2_bridge_loop_reinvokes_implementer(self):
        passed, msg = cs_mod.check_bridge_loop_reinvokes_implementer(REPO_ROOT)
        assert passed, f"INV-2 failed: {msg}"

    def test_inv3_receipt_writer_returns_per_invocation(self):
        passed, msg = cs_mod.check_receipt_writer_returns_per_invocation(REPO_ROOT)
        assert passed, f"INV-3 failed: {msg}"

    def test_inv4_client_no_heuristic_discovery(self):
        passed, msg = cs_mod.check_client_no_heuristic_discovery(REPO_ROOT)
        assert passed, f"INV-4 failed: {msg}"

    def test_inv5_checks_repo_tracked_claude_md(self):
        """INV-5 checks repo-tracked CLAUDE.md (not external memory)."""
        passed, msg = cs_mod.check_docs_no_manual_commit_fallback(REPO_ROOT)
        assert passed, f"INV-5 failed: {msg}"
        assert "fallback" not in msg.lower() or "no manual" in msg.lower()

    def test_inv6_commit_executor_receipt_authority(self):
        """INV-6: commit_executor step 7 verifies both handoff and supervisor receipts."""
        passed, msg = cs_mod.check_commit_executor_receipt_authority(REPO_ROOT)
        assert passed, f"INV-6 failed: {msg}"
        assert "both receipts" in msg.lower()


class TestINV5RepoOnlyDocs:
    """INV-5 checks repo-tracked CLAUDE.md only — no external memory dependence."""

    def test_inv5_fails_on_manual_merge_in_claude_md(self, tmp_path):
        """INV-5 must fail when CLAUDE.md has standalone manual merge_pr.sh instruction."""
        (tmp_path / "CLAUDE.md").write_text(
            "## Workflow\n\n"
            "**PR merge:** Use `bash mu/tools/hooks/merge_pr.sh <PR#> --sweep`\n"
        )
        passed, msg = cs_mod.check_docs_no_manual_commit_fallback(tmp_path)
        assert not passed, f"INV-5 should fail on standalone merge_pr.sh: {msg}"

    def test_inv5_fails_on_git_push_in_claude_md(self, tmp_path):
        """INV-5 must fail when CLAUDE.md has manual git push instruction."""
        (tmp_path / "CLAUDE.md").write_text(
            "## Commit Fallback\n\n"
            "If the executor fails, run:\n"
            "  git push -u origin jabramsja/wave\n"
            "  gh pr create --base dev\n"
        )
        passed, msg = cs_mod.check_docs_no_manual_commit_fallback(tmp_path)
        assert not passed, f"INV-5 should fail on git push in CLAUDE.md: {msg}"

    def test_inv5_passes_when_claude_md_uses_executor(self, tmp_path):
        """INV-5 passes when CLAUDE.md references executor, not manual steps."""
        (tmp_path / "CLAUDE.md").write_text(
            "## Workflow\n\n"
            "**PR merge:** Use `commit_executor.py` for the full pipeline. "
            "The executor calls merge_pr.sh internally.\n"
        )
        passed, msg = cs_mod.check_docs_no_manual_commit_fallback(tmp_path)
        assert passed, f"INV-5 should pass with executor-based CLAUDE.md: {msg}"

    def test_inv5_passes_on_clean_content(self, tmp_path):
        """INV-5 must pass when commit section has no manual steps."""
        (tmp_path / "CLAUDE.md").write_text(
            "## Workflow\n\n"
            "Use `commit_executor.py` for the full pipeline.\n"
        )
        template_path = tmp_path / "mu" / "tools" / "agents" / "templates" / "meta_bridge_task.txt"
        template_path.parent.mkdir(parents=True)
        template_path.write_text("Use `commit_executor.py` for the full commit path.\n")
        passed, msg = cs_mod.check_docs_no_manual_commit_fallback(tmp_path)
        assert passed, f"INV-5 should pass on clean content: {msg}"

    def test_normalize_path_caches_git_toplevel_lookup(self):
        """_normalize_path should not shell out once per path."""
        cs_mod._git_toplevel.cache_clear()  # ANTICHEAT_OK: cache behavior is the subject under test
        completed = MagicMock(stdout="/repo\n")
        with patch.object(cs_mod.subprocess, "run", return_value=completed) as mock_run:
            assert cs_mod._normalize_path("/repo/mu/tools/executors/phase_b_executor.py") == "mu/tools/executors/phase_b_executor.py"  # ANTICHEAT_OK: normalize helper is the subject under test
            assert cs_mod._normalize_path("/repo/CLAUDE.md") == "CLAUDE.md"  # ANTICHEAT_OK: normalize helper is the subject under test
        assert mock_run.call_count == 1
        cs_mod._git_toplevel.cache_clear()  # ANTICHEAT_OK: test cleanup for module-level cache

    def test_normalize_path_collapses_dot_segments(self):
        cs_mod._git_toplevel.cache_clear()  # ANTICHEAT_OK: cache behavior is the subject under test
        completed = MagicMock(stdout="/repo\n")
        with patch.object(cs_mod.subprocess, "run", return_value=completed):
            assert cs_mod._normalize_path("mu/tools/executors/./phase_b_executor.py") == "mu/tools/executors/phase_b_executor.py"  # ANTICHEAT_OK: normalize helper is the subject under test
            assert cs_mod._normalize_path("/repo/mu/tools/agents/../executors/phase_b_executor.py") == "mu/tools/executors/phase_b_executor.py"  # ANTICHEAT_OK: normalize helper is the subject under test
        cs_mod._git_toplevel.cache_clear()  # ANTICHEAT_OK: test cleanup for module-level cache


class TestCheckerSkipsNonControlSurface:
    """Checker passes immediately when no control-surface files are touched."""

    def test_skips_for_regular_files(self):
        results, all_passed = cs_mod.run_all(
            REPO_ROOT, changed_files=["README.md", "STATUS.md"]
        )
        assert all_passed
        assert results[0]["name"] == "control_surface_skip"

    def test_activates_for_control_surface_files(self):
        results, all_passed = cs_mod.run_all(
            REPO_ROOT,
            changed_files=["mu/tools/executors/phase_b_executor.py"],
        )
        assert all_passed  # Should pass since repo is correct
        assert any(r["name"].startswith("INV-") for r in results)


class TestCheckerDetectsViolations:
    """Checker correctly catches invariant violations on synthetic repos."""

    def test_detects_review_mode_implementer(self, tmp_path):
        """INV-1: implementer that references bridge_supervisor fails."""
        exe_dir = tmp_path / "mu" / "tools" / "executors"
        exe_dir.mkdir(parents=True)
        (exe_dir / "phase_b_implementer.py").write_text(
            'import subprocess\nbridge_supervisor = "tools/agents/bridge_supervisor.py"\n'
            'cmd = ["python3", bridge_supervisor, "review"]\n'
        )
        passed, msg = cs_mod.check_implementer_not_review_mode(tmp_path)
        assert not passed

    def test_detects_missing_implementer_reinvocation(self, tmp_path):
        """INV-2: bridge loop without invoke_implementer in RC block fails."""
        exe_dir = tmp_path / "mu" / "tools" / "executors"
        exe_dir.mkdir(parents=True)
        (exe_dir / "phase_b_executor.py").write_text(
            'if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):\n'
            '    log("just continuing")\n'
            '    continue\n'
        )
        passed, msg = cs_mod.check_bridge_loop_reinvokes_implementer(tmp_path)
        assert not passed

    def test_detects_canonical_receipt_return(self, tmp_path):
        """INV-3: receipt writer returning canonical path fails."""
        agents_dir = tmp_path / "mu" / "tools" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "meta_bridge_supervisor.py").write_text(
            'def write_pre_commit_receipt(response, pkg, repo_root=None):\n'
            '    canonical_path = "receipt.json"\n'
            '    return canonical_path\n'
        )
        passed, msg = cs_mod.check_receipt_writer_returns_per_invocation(tmp_path)
        assert not passed

    def test_detects_ambiguous_per_invocation_metadata_return(self, tmp_path):
        """INV-3 must fail on metadata names that only mention per_invocation."""
        agents_dir = tmp_path / "mu" / "tools" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "meta_bridge_supervisor.py").write_text(
            'def write_pre_commit_receipt(response, pkg, repo_root=None):\n'
            '    canonical_path = "receipt.json"\n'
            '    canonical_path.write_text("x")\n'
            '    per_invocation_metadata = {"path": canonical_path}\n'
            '    return per_invocation_metadata["path"]\n'
        )
        passed, msg = cs_mod.check_receipt_writer_returns_per_invocation(tmp_path)
        assert not passed

    def test_detects_heuristic_receipt_discovery(self, tmp_path):
        """INV-4: client that sorts directory for receipt fails."""
        agents_dir = tmp_path / "mu" / "tools" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "meta_bridge_client.py").write_text(
            'receipts = sorted(per_inv_dir.iterdir(), key=lambda p: p.name)\n'
            'receipt_path = receipts[0]\n'
        )
        passed, msg = cs_mod.check_client_no_heuristic_discovery(tmp_path)
        assert not passed

    def test_detects_missing_handoff_receipt_authority(self, tmp_path):
        """INV-6 must fail when step 7 checks only the supervisor receipt."""
        exe_dir = tmp_path / "mu" / "tools" / "executors"
        exe_dir.mkdir(parents=True)
        (exe_dir / "commit_executor.py").write_text(
            'def run_commit_pipeline(handoff, repo_root):\n'
            '    # Step 7: validate_receipt\n'
            '    receipt_path_from_supervisor = ".scratch/receipt.json"\n'
            '    receipt_file = repo_root / receipt_path_from_supervisor\n'
            '    if not receipt_file.exists():\n'
            '        return False\n'
            '    # Step 8: next\n'
            '    return True\n'
        )
        passed, msg = cs_mod.check_commit_executor_receipt_authority(tmp_path)
        assert not passed

    def test_detects_listdir_receipt_discovery(self, tmp_path):
        """INV-4: client using os.listdir for receipt discovery fails."""
        agents_dir = tmp_path / "mu" / "tools" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "meta_bridge_client.py").write_text(
            'files = os.listdir(receipt_dir)\n'
            'receipt = sorted(files)[-1]\n'
        )
        passed, msg = cs_mod.check_client_no_heuristic_discovery(tmp_path)
        assert not passed

    def test_detects_glob_receipt_discovery(self, tmp_path):
        """INV-4: client using glob for receipt discovery fails."""
        agents_dir = tmp_path / "mu" / "tools" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "meta_bridge_client.py").write_text(
            'receipt_files = list(receipt_dir.glob("receipt_*.json"))\n'
            'latest = sorted(receipt_files)[-1]\n'
        )
        passed, msg = cs_mod.check_client_no_heuristic_discovery(tmp_path)
        assert not passed


class TestBridgeReviewerPromptActivation:
    """Bridge reviewer prompt injects control-surface obligations for relevant files."""

    def test_control_surface_mode_activates(self):
        """When control-surface files are in changed_actual, proof obligations appear."""
        # Import the bridge_supervisor module's detection function
        bs_path = REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py"
        bs_mod = load_module("bridge_supervisor_test", bs_path)

        assert bs_mod._touches_control_surface("mu/tools/executors/phase_b_executor.py")  # ANTICHEAT_OK: testing bridge reviewer detection

        instructions = bs_mod._build_code_review_instructions(  # ANTICHEAT_OK: testing bridge prompt builder
            changed_actual="mu/tools/executors/phase_b_executor.py, mu/tools/agents/meta_bridge_client.py",
            staged="mu/tools/executors/phase_b_executor.py",
            unstaged="",
            validation_results_text="all pass",
            reader_summary="implementation done",
            diff_text="+ some code",
        )
        assert "CONTROL-SURFACE EVIDENCE TOPICS (activated" in instructions
        assert "Implementer surface" in instructions
        assert "Bridge loop mechanics" in instructions
        assert "Receipt authority chain" in instructions
        assert "invoke_implementer" not in instructions or "bridge_adapters" in instructions  # instructions reference the concept

    def test_control_surface_mode_does_not_activate_for_regular_files(self):
        """Regular files do not trigger control-surface review."""
        bs_path = REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py"
        bs_mod = load_module("bridge_supervisor_test2", bs_path)

        instructions = bs_mod._build_code_review_instructions(  # ANTICHEAT_OK: testing bridge prompt builder
            changed_actual="mu/host/python/rcx_pi/selfhost/step_mu.py",
            staged="mu/host/python/rcx_pi/selfhost/step_mu.py",
            unstaged="",
            validation_results_text="all pass",
            reader_summary="kernel fix",
            diff_text="+ code",
        )
        assert "CONTROL-SURFACE EVIDENCE TOPICS (activated" not in instructions


class TestBridgeReviewerMuPathActivation:
    """Bridge reviewer must activate for mu/tools/agents/bridge_supervisor.py path."""

    def test_mu_bridge_supervisor_activates_bridge_review(self):
        bs_path = REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py"
        bs_mod = load_module("bridge_supervisor_test_mu", bs_path)
        assert bs_mod._touches_control_surface("mu/tools/agents/bridge_supervisor.py")  # ANTICHEAT_OK: testing bridge reviewer detection

    def test_mu_bridge_supervisor_in_prompt(self):
        bs_path = REPO_ROOT / "tools" / "agents" / "bridge_supervisor.py"
        bs_mod = load_module("bridge_supervisor_test_mu2", bs_path)
        instructions = bs_mod._build_code_review_instructions(  # ANTICHEAT_OK: testing bridge prompt builder
            changed_actual="mu/tools/agents/bridge_supervisor.py",
            staged="mu/tools/agents/bridge_supervisor.py",
            unstaged="", validation_results_text="pass",
            reader_summary="bridge fix", diff_text="+ code",
        )
        assert "CONTROL-SURFACE EVIDENCE TOPICS (activated" in instructions


class TestMetaBridgePromptControlSurface:
    """Pre-commit supervisor prompt injects control-surface obligations."""

    def test_meta_bridge_prompt_has_control_surface_placeholder(self):
        template = (REPO_ROOT / "mu" / "tools" / "agents" / "templates" / "meta_bridge_task.txt").read_text()
        assert "$control_surface_obligations" in template

    def test_meta_bridge_prompt_builder_injects_for_control_files(self):
        """build_meta_reviewer_prompt includes obligations when changed_files touch control surface."""
        import meta_bridge_supervisor as mbs
        package = {
            "task_id": "[TEST]", "wave_name": "test", "lane": "test",
            "changed_files": ["mu/tools/executors/phase_b_executor.py"],
            "scope_items": [], "fixes_implemented": [], "deferred_items": [],
            "bridge_status": {}, "evidence_handles": {},
            "blocker_report_paths": [], "current_judgment": "COMMIT_GO",
        }
        prompt = mbs.build_meta_reviewer_prompt(package, [], REPO_ROOT)
        assert "CONTROL-SURFACE REVIEW MODE" in prompt
        assert "mu/tools/executors/phase_b_implementer.py" in prompt
        assert "mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt()" in prompt
        assert "mu/tools/agents/meta_bridge_client.py::run_meta_bridge_package()" in prompt
        assert "mu/tools/executors/phase_b_executor.py::prepare_commit_handoff()" in prompt
        assert "mu/tools/executors/commit_executor.py" in prompt

    def test_meta_bridge_prompt_builder_skips_for_regular_files(self):
        """build_meta_reviewer_prompt does not inject obligations for regular files."""
        import meta_bridge_supervisor as mbs
        package = {
            "task_id": "[TEST]", "wave_name": "test", "lane": "test",
            "changed_files": ["README.md"],
            "scope_items": [], "fixes_implemented": [], "deferred_items": [],
            "bridge_status": {}, "evidence_handles": {},
            "blocker_report_paths": [], "current_judgment": "COMMIT_GO",
        }
        prompt = mbs.build_meta_reviewer_prompt(package, [], REPO_ROOT)
        assert "CONTROL-SURFACE REVIEW MODE" not in prompt


class TestRunnerControlSurfaceContext:
    """SDK agent runner injects control-surface context for relevant files."""

    def test_runner_builds_context_for_control_files(self):
        """build_control_surface_context returns obligations for control-surface files."""
        sau_path = REPO_ROOT / "tools" / "runners" / "shared_agent_utils.py"
        sau_mod = load_module("shared_agent_utils_test_cs", sau_path)
        ctx = sau_mod.build_control_surface_context(["mu/tools/executors/phase_b_executor.py"])
        assert "CONTROL-SURFACE REVIEW MODE" in ctx
        assert "bridge_adapters" in ctx
        assert "mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt()" in ctx
        assert "mu/tools/agents/meta_bridge_client.py::run_meta_bridge_package()" in ctx
        assert "mu/tools/hooks/pre_commit_receipt.py" not in ctx
        assert "mu/tools/executors/meta_bridge_client.py" not in ctx

    def test_runner_returns_empty_for_regular_files(self):
        """build_control_surface_context returns empty for non-control files."""
        sau_path = REPO_ROOT / "tools" / "runners" / "shared_agent_utils.py"
        sau_mod = load_module("shared_agent_utils_test_cs2", sau_path)
        ctx = sau_mod.build_control_surface_context(["README.md"])
        assert ctx == ""

    def test_runner_detects_mu_bridge_supervisor(self):
        """build_control_surface_context activates for mu/ bridge path."""
        sau_path = REPO_ROOT / "tools" / "runners" / "shared_agent_utils.py"
        sau_mod = load_module("shared_agent_utils_test_cs3", sau_path)
        ctx = sau_mod.build_control_surface_context(["mu/tools/agents/bridge_supervisor.py"])
        assert "CONTROL-SURFACE REVIEW MODE" in ctx

    def test_runner_detects_dot_segment_control_surface(self):
        """build_control_surface_context normalizes dot-segment control-surface paths."""
        sau_path = REPO_ROOT / "tools" / "runners" / "shared_agent_utils.py"
        sau_mod = load_module("shared_agent_utils_test_cs4", sau_path)
        ctx = sau_mod.build_control_surface_context(["mu/tools/executors/./phase_b_executor.py"])
        assert "CONTROL-SURFACE REVIEW MODE" in ctx


class TestRegressionGuard:
    """Existing Phase B fixes must still hold."""

    def test_implementer_source_no_bridge_supervisor(self):
        src = (REPO_ROOT / "mu" / "tools" / "executors" / "phase_b_implementer.py").read_text()
        assert "bridge_supervisor" not in src

    def test_executor_stages_before_supervisor(self):
        src = (REPO_ROOT / "mu" / "tools" / "executors" / "phase_b_executor.py").read_text()
        # "Stage files BEFORE" must appear before "Running pre-commit supervisor"
        stage_idx = src.find("Stage files BEFORE")
        supervisor_idx = src.find("Running pre-commit supervisor")
        assert stage_idx > 0
        assert supervisor_idx > stage_idx

    def test_no_freshness_matching_in_executor(self):
        """Executor must not use render-age freshness matching on bridge outputs.

        st_mtime_ns / getmtime usage for SDK gate supervision (heartbeat,
        stale-run detection) is approved per the supervision design.
        render_age freshness matching on bridge renders remains forbidden.
        """
        src = (REPO_ROOT / "mu" / "tools" / "executors" / "phase_b_executor.py").read_text()
        assert "render_age" not in src


class TestINV2LoopBodyCheck:
    """INV-2 checker must reject invoke_implementer in unrelated if-branches."""

    def test_invoke_implementer_in_unrelated_branch_rejected(self):
        """Pattern B requires invoke_implementer as a DIRECT statement in for-body,
        not nested inside an unrelated if-branch.

        R2 finding #4: A loop where RC/NO_GO only 'continue's and invoke_implementer
        lives in a separate if-branch must NOT pass.
        """
        import ast
        import inspect

        # Read the checker source to verify the fix
        checker_src = (REPO_ROOT / "tools" / "checks" / "check_control_surface_invariants.py").read_text()

        # The check for loop_body_has_implementer must iterate over node.body
        # (direct statements) and reject nested if-branches
        assert "for stmt in node.body" in checker_src, (
            "INV-2 checker must iterate over direct for-body statements, "
            "not use ast.walk(node) which includes all nested branches"
        )
        assert "not isinstance(stmt, ast.If)" in checker_src, (
            "INV-2 checker must exclude if-statements when checking for "
            "direct loop-body invoke_implementer (Pattern B)"
        )
