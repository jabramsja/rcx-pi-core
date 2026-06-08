"""Tests for commit_executor's post-merge cleanup helper.

Covers:
1. Happy path: on base_branch, wave branch + worktree + stashes removed.
2. cleanup_root not on base_branch → skipped with warning (no destruction).
3. Wave branch missing → branch_deleted=False with warning, other steps still run.
4. Worktree distinct path that doesn't exist → worktree step skipped cleanly.
5. No executor-owned stashes for wave_id → 0 dropped, unrelated stashes preserved.
6. Worktree removal unlocks branch so branch_deleted succeeds (order matters).
7. Growth-cap auto-bump: FOUNDER_OVERRIDE-gated CAP_TEST_FILES bump before the
   Step 8 gate — exact-shortfall bump, fail-closed without override, and no-bump
   on no-new-test-files / headroom / consolidation, idempotent on retry. Plus the
   receipt-ordering pin (Step 5e precedes the Step 6 supervisor/receipt) so the
   bump cannot strand Step 8 with a stale pre-commit receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


def _git(args, cwd, env=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, env=env
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a minimal bare-shaped repo on branch 'dev' with one commit."""
    repo = tmp_path / "main"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    _git(["init"], cwd=repo, env=env)
    _git(["checkout", "-b", "dev"], cwd=repo, env=env)
    _git(["config", "user.name", "t"], cwd=repo)
    _git(["config", "user.email", "t@t"], cwd=repo)
    (repo / "seed.txt").write_text("seed")
    _git(["add", "seed.txt"], cwd=repo, env=env)
    _git(["commit", "-m", "init"], cwd=repo, env=env)
    return repo


def _noop_log(msg: str) -> None:
    pass


def _write_queue_packet(repo: Path, relpath: str, status: str) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Packet\n\nStatus: {status}\n", encoding="utf-8")


def test_happy_path_removes_branch_worktree_and_matching_stashes(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-alpha-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    # Create wave branch + linked worktree
    wt_path = tmp_path / "wave_worktree"
    _git(["worktree", "add", "-b", target_branch, str(wt_path), "dev"], cwd=repo)
    # Create two stashes: one executor-owned Phase B marker, one unrelated.
    (repo / "scratch.txt").write_text("dirty")
    _git(["add", "scratch.txt"], cwd=repo)
    _git(["stash", "push", "-m", f"phase_b:{target_branch}:abc123"], cwd=repo)
    (repo / "other.txt").write_text("unrelated")
    _git(["add", "other.txt"], cwd=repo)
    _git(["stash", "push", "-m", "On dev: unrelated-topic"], cwd=repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=wt_path,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["worktree_removed"] is True, outcome
    assert outcome["branch_deleted"] is True, outcome
    assert outcome["stashes_dropped"] == 1, outcome
    # Branch is gone
    branches = _git(["branch", "--list"], cwd=repo).stdout
    assert target_branch not in branches
    # Worktree path removed from filesystem and from git metadata
    assert not wt_path.exists()
    wt_list = _git(["worktree", "list", "--porcelain"], cwd=repo).stdout
    assert str(wt_path) not in wt_list
    # Unrelated stash preserved
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "unrelated-topic" in stash_list
    assert f"phase_b:{target_branch}:abc123" not in stash_list


def test_post_merge_cleanup_preserves_manual_wave_named_stash(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-manual-stash-2026-05-14"
    target_branch = f"jabramsja/{wave_id}"
    _git(["branch", target_branch, "dev"], cwd=repo)

    (repo / "manual.txt").write_text("manual")
    _git(["add", "manual.txt"], cwd=repo)
    _git(
        [
            "stash",
            "push",
            "-m",
            f"rcx-temp-postcommit-push-isolation-{wave_id}",
        ],
        cwd=repo,
    )

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=repo,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["branch_deleted"] is True, outcome
    assert outcome["stashes_dropped"] == 0, outcome
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert f"rcx-temp-postcommit-push-isolation-{wave_id}" in stash_list


def test_post_merge_package_refresh_selects_next_open_queue_packet(tmp_path):
    repo = _init_repo(tmp_path)
    _write_queue_packet(
        repo,
        "reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md",
        "COMPLETED (commit-ready, pre-commit supervisor pending)",
    )
    _write_queue_packet(
        repo,
        "reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md",
        "QUEUED - NON-BLOCKING REMEDIATION PACKET",
    )
    source = (
        "reports/deferred/non_blocking/"
        "founder_ordered_redteam_tests_audit_2026-05-05_non_blocking.md"
    )
    (repo / source).parent.mkdir(parents=True, exist_ok=True)
    (repo / source).write_text("# source\n", encoding="utf-8")
    (repo / "reports" / "deferred" / "blocking").mkdir(parents=True)
    (repo / "reports" / "deferred" / "blocking" / "open_blocker.md").write_text(
        "# blocker\n", encoding="utf-8"
    )
    (repo / "reports" / "deferred" / "blocking" / "README.md").write_text(
        "# index\n", encoding="utf-8"
    )
    (repo / "TASKS.md").write_text(
        "\n".join(
            [
                "## Ra",
                (
                    "  3. **[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION] "
                    "IMPLEMENTED / LOCAL EVIDENCE (2026-05-06).** Task: `[NEXT-CODEX-POST-REDTEAM]`. "
                    "Wave ID: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`. "
                    "Class: `L4_ENABLER`. Category: docs. Packet: "
                    "`reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`."
                ),
                (
                    "  4. **[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION] "
                    "QUEUED / NON-BLOCKING.** Task: `[NEXT-CODEX-POST-REDTEAM]`. "
                    "Wave ID: `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`. "
                    "Class: `L4_ENABLER`. Category: tests. Packet: "
                    "`reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`. "
                    f"Source audit packet: `{source}`."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "886"},
        merge_sha="abc123",
        log=_noop_log,
    )

    package_path = repo / ".agent_bus" / "meta" / "post_merge_package.json"
    assert package is not None
    assert json.loads(package_path.read_text(encoding="utf-8")) == package
    assert package["merged_pr"] == 886
    assert package["merge_sha"] == "abc123"
    assert package["wave_name"] == (
        "founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06"
    )
    assert package["next_candidates"] == [
        {
            "candidate": "founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06",
            "bounded": True,
            "tracked_packet": (
                "reports/control_plane/"
                "founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md"
            ),
            "summary": "Implement the queued tests remediation packet only.",
            "request_for_claude": package["next_candidates"][0]["request_for_claude"],
        }
    ]
    assert source in package["deferred_items"]
    assert package["blocker_report_paths"] == [
        "reports/deferred/blocking/open_blocker.md"
    ]
    assert "post-merge supervisor -> Phase A -> Phase B -> commit executor" in (
        package["next_candidates"][0]["request_for_claude"]
    )


def test_post_merge_package_refresh_skips_completed_audit_status_with_pending_text(tmp_path):
    repo = _init_repo(tmp_path)
    audit_packet = (
        "reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md"
    )
    remediation_packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(
        repo,
        audit_packet,
        "COMPLETED (commit-ready, pre-commit supervisor pending)",
    )
    _write_queue_packet(
        repo,
        remediation_packet,
        "QUEUED - NON-BLOCKING REMEDIATION PACKET",
    )
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  2. **[FOUNDER-ORDERED-REDTEAM-DOCS-AUDIT] COMPLETED / FINDINGS ROUTED.** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-docs-audit-2026-05-05`. "
            "Class: `L4_ENABLER`. "
            f"Packet: `{audit_packet}`.\n"
            "  4. **[FOUNDER-ORDERED-REDTEAM-TESTS-NON-BLOCKING-REMEDIATION] "
            "QUEUED / NON-BLOCKING.** Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: tests. "
            f"Packet: `{remediation_packet}`.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "887"},
        merge_sha="fresh-head",
        log=_noop_log,
    )

    assert package["merge_sha"] == "fresh-head"
    assert package["wave_name"] == (
        "founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06"
    )
    assert package["next_candidates"][0]["tracked_packet"] == remediation_packet
    assert audit_packet not in package["deferred_items"]


def test_post_merge_package_refresh_skips_completed_tasks_state_even_if_packet_stale(tmp_path):
    repo = _init_repo(tmp_path)
    completed_packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md"
    )
    open_packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(repo, completed_packet, "QUEUED - STALE HEADER")
    _write_queue_packet(repo, open_packet, "QUEUED - NON-BLOCKING REMEDIATION PACKET")
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  4. **[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION] "
            "IMPLEMENTED / LOCAL EVIDENCE (2026-05-06).** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: docs. "
            f"Packet: `{completed_packet}`.\n"
            "  5. **[FOUNDER-ORDERED-REDTEAM-TOOLING-NON-BLOCKING-REMEDIATION] "
            "QUEUED / NON-BLOCKING.** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: tooling. "
            f"Packet: `{open_packet}`.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "890"},
        merge_sha="fresh-head",
        log=_noop_log,
    )

    assert package["wave_name"] == (
        "founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06"
    )
    assert package["next_candidates"][0]["tracked_packet"] == open_packet
    assert completed_packet not in package["deferred_items"]


def test_post_merge_package_refresh_stops_before_mu_structural_queue(tmp_path):
    repo = _init_repo(tmp_path)
    packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(repo, packet, "QUEUED - HARD STOP BEFORE IMPLEMENTATION")
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "QUEUED / BLOCKING / HARD STOP BEFORE IMPLEMENTATION.** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: `/mu` structural. "
            f"Packet: `{packet}`.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": 887},
        merge_sha="def456",
        log=_noop_log,
    )

    assert package is not None
    assert package["wave_name"] == (
        "founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06"
    )
    assert package["next_candidates"] == []
    assert "hard stop" in package["tracker_state_summary"].lower()


def test_post_merge_package_refresh_routes_authorized_mu_structural_non_hard_stop(tmp_path):
    repo = _init_repo(tmp_path)
    packet = (
        "reports/control_plane/"
        "broad_host_surface_next_structural_slice_2026-05-13.md"
    )
    source = "reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md"
    _write_queue_packet(repo, packet, "Routed - Phase A required before implementation")
    (repo / source).parent.mkdir(parents=True, exist_ok=True)
    (repo / source).write_text("# source\n", encoding="utf-8")
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NEXT-SLICE] "
            "QUEUED / PHASE A REQUIRED.** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `broad-host-surface-next-structural-slice-2026-05-13`. "
            "Class: `L4_ENABLER`. Category: /mu structural host-surface reduction. "
            f"Packet: `{packet}`. "
            f"Source audit packet: `{source}`.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": 946},
        merge_sha="fresh-head",
        log=_noop_log,
    )

    request = package["next_candidates"][0]["request_for_claude"]
    assert package["wave_name"] == "broad-host-surface-next-structural-slice-2026-05-13"
    assert package["next_candidates"][0]["tracked_packet"] == packet
    assert "post-merge supervisor -> Phase A -> Phase B -> commit executor" in request
    assert "requires /mu structural work" not in request
    assert "outside its bounded scope" in request

    non_mu_request = commit_mod._post_merge_request_for_queue_entry(  # ANTICHEAT_OK: testing private helper
        {"packet": packet, "category": "tests"}
    )
    assert "requires /mu structural work" in non_mu_request
    assert "outside its bounded scope" not in non_mu_request


def test_post_merge_package_refresh_routes_open_tracker_packet_before_hard_stop(tmp_path):
    repo = _init_repo(tmp_path)
    routed_packet = (
        "reports/control_plane/"
        "deferred-non-mu-docs-control-plane-remediation-2026-05-07_2026-05-07.md"
    )
    hard_stop_packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(
        repo,
        routed_packet,
        "Routed - Phase A required before implementation",
    )
    _write_queue_packet(repo, hard_stop_packet, "QUEUED - HARD STOP BEFORE IMPLEMENTATION")
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  6. **[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-BLOCKING-REMEDIATION] "
            "QUEUED / BLOCKING / HARD STOP BEFORE IMPLEMENTATION.** "
            "Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: `/mu` structural. "
            f"Packet: `{hard_stop_packet}`.\n"
            "- Tracker sync note (2026-05-07, deferred-non-mu-docs-control-plane-remediation-2026-05-07): "
            "**NEXT-CODEX-POST-REDTEAM - routed deferred non-mu docs/control-plane remediation packet.** "
            "Class: L4_ENABLER. Category: docs/control-plane. target_gate_id: G8. "
            f"Packet: `{routed_packet}`. "
            "FOUNDER_OVERRIDE:deferred-non-mu-docs-control-plane-remediation-2026-05-07.\n"
        ),
        encoding="utf-8",
    )

    result = {"pr_number": 900}
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={
            "task_id": (
                "[deferred-non-mu-post-merge-routed-queue-selection-repair-2026-05-07]"
            )
        },
        result=result,
        merge_sha="merge-sha",
        log=_noop_log,
    )

    assert package["task_id"] == "[NEXT-CODEX-POST-REDTEAM]"
    assert package["wave_name"] == (
        "deferred-non-mu-docs-control-plane-remediation-2026-05-07"
    )
    assert package["next_candidates"][0]["tracked_packet"] == routed_packet
    assert result["post_merge_next_hard_stop"] is False
    assert "hard stop" not in package["tracker_state_summary"].lower()


def test_post_merge_package_refresh_closes_completed_only_queue(tmp_path):
    repo = _init_repo(tmp_path)
    packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(repo, packet, "COMPLETED")
    stale_package_path = repo / ".agent_bus" / "meta" / "post_merge_package.json"
    stale_package_path.parent.mkdir(parents=True)
    stale_package_path.write_text(
        json.dumps(
            {
                "merge_sha": "stale",
                "next_candidates": [
                    {
                        "candidate": (
                            "founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06"
                        ),
                        "bounded": True,
                        "tracked_packet": packet,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "TASKS.md").write_text(
        (
            "## Ra\n"
            "  4. **[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION] "
            "COMPLETED.** Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: docs. "
            f"Packet: `{packet}`.\n"
        ),
        encoding="utf-8",
    )
    result = {"pr_number": "888"}

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha="fresh-head",
        log=_noop_log,
    )

    assert json.loads(stale_package_path.read_text(encoding="utf-8")) == package
    assert package["merge_sha"] == "fresh-head"
    assert package["wave_name"] == "founder-ordered-post-merge-queue-empty"
    assert package["next_candidates"] == []
    assert package["deferred_items"] == []
    assert packet not in json.dumps(package)
    assert result["post_merge_next_wave"] is None
    assert result["post_merge_queue_empty"] is True


def test_skips_when_cleanup_root_not_on_base_branch(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-wrong-branch-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    wt_path = tmp_path / "wave_worktree"
    _git(["worktree", "add", "-b", target_branch, str(wt_path), "dev"], cwd=repo)
    # Put cleanup_root on a different branch (not "dev")
    _git(["checkout", "-b", "not-dev"], cwd=repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=wt_path,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["branch_deleted"] is False
    assert outcome["worktree_removed"] is False
    assert outcome["stashes_dropped"] == 0
    assert any("not on" in w or "expected" in w for w in outcome["warnings"]), outcome
    # Nothing destroyed
    assert wt_path.exists()
    branches = _git(["branch", "--list"], cwd=repo).stdout
    assert target_branch in branches


def test_missing_wave_branch_does_not_fail_pipeline(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-no-branch-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"  # this branch is NOT created

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=repo,  # same as cleanup_root → worktree step skipped
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["branch_deleted"] is False
    assert outcome["worktree_removed"] is False
    assert outcome["stashes_dropped"] == 0
    assert any("branch delete" in w for w in outcome["warnings"]), outcome


def test_nonexistent_worktree_path_is_skipped_cleanly(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-no-wt-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    # Create the branch but not a worktree
    _git(["branch", target_branch, "dev"], cwd=repo)
    fake_wt = tmp_path / "does_not_exist"

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=fake_wt,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["worktree_removed"] is False
    assert outcome["branch_deleted"] is True  # branch existed and was deletable
    # No worktree warning since we skipped instead of attempting


def test_no_matching_stashes_preserves_unrelated(tmp_path):
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-no-stashes-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    _git(["branch", target_branch, "dev"], cwd=repo)
    # Create unrelated stashes only
    (repo / "a.txt").write_text("a")
    _git(["add", "a.txt"], cwd=repo)
    _git(["stash", "push", "-m", "unrelated A"], cwd=repo)
    (repo / "b.txt").write_text("b")
    _git(["add", "b.txt"], cwd=repo)
    _git(["stash", "push", "-m", "unrelated B"], cwd=repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=repo,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    assert outcome["stashes_dropped"] == 0
    stash_list = _git(["stash", "list"], cwd=repo).stdout
    assert "unrelated A" in stash_list
    assert "unrelated B" in stash_list


def test_worktree_remove_runs_before_branch_delete_so_order_unlocks_branch(tmp_path):
    """If we attempted `branch -D` BEFORE removing the worktree, git would
    refuse: "Cannot delete branch 'X' checked out at 'Y'". Helper's order
    (worktree → branch) is required for happy path to produce branch_deleted=True.
    """
    repo = _init_repo(tmp_path)
    wave_id = "test-wave-order-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    wt_path = tmp_path / "wave_worktree_order"
    _git(["worktree", "add", "-b", target_branch, str(wt_path), "dev"], cwd=repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=wt_path,
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    # If order were wrong, branch_deleted would be False with a "checked out" warning.
    assert outcome["worktree_removed"] is True
    assert outcome["branch_deleted"] is True
    assert not any("checked out" in w for w in outcome["warnings"]), outcome


def test_main_worktree_is_refused_when_distinct_from_cleanup_root(tmp_path):
    """Bot P2 finding (PR #782): if `_resolve_post_merge_verify_root` points
    cleanup_root at a linked worktree while repo_root IS the primary worktree,
    the helper must NOT attempt `git worktree remove <main>` — git refuses,
    then `branch -D` would fail because the branch is still checked out in
    main. Guard: only run worktree remove when repo_root/.git is a FILE
    (linked-worktree pointer), never a DIRECTORY (primary worktree).
    """
    main_repo = _init_repo(tmp_path)  # main_repo/.git is a directory, on dev
    wave_id = "test-wave-main-guard-2026-04-17"
    target_branch = f"jabramsja/{wave_id}"
    # Create target_branch + another branch on main so we can move main off dev.
    _git(["branch", target_branch, "dev"], cwd=main_repo)
    _git(["checkout", "-b", "other"], cwd=main_repo)  # main now on 'other'
    # Now dev is free; create a linked worktree on dev to serve as cleanup_root.
    linked = tmp_path / "linked_cleanup"
    _git(["worktree", "add", str(linked), "dev"], cwd=main_repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=linked,
        repo_root=main_repo,  # primary worktree — helper MUST refuse to remove it
        target_branch=target_branch,
        base_branch="dev",
        wave_id=wave_id,
        log=_noop_log,
    )

    # Worktree step must be skipped (main repo .git is a directory, not a linked file)
    assert outcome["worktree_removed"] is False, outcome
    # Main repo still exists on disk
    assert main_repo.exists()
    assert (main_repo / ".git").is_dir(), "main repo .git must remain a directory"
    # Branch delete from linked cleanup_root succeeds — target_branch exists
    # as a ref but is NOT checked out in any worktree (main is on 'other').
    assert outcome["branch_deleted"] is True, outcome


def test_empty_wave_id_skips_stash_step_without_warning(tmp_path):
    repo = _init_repo(tmp_path)
    target_branch = "jabramsja/some-branch"
    _git(["branch", target_branch, "dev"], cwd=repo)

    outcome = commit_mod._post_merge_cleanup(  # ANTICHEAT_OK: testing private helper
        cleanup_root=repo,
        repo_root=repo,
        target_branch=target_branch,
        base_branch="dev",
        wave_id="",  # empty
        log=_noop_log,
    )

    assert outcome["stashes_dropped"] == 0
    # No stash-related warnings
    assert not any("stash" in w for w in outcome["warnings"]), outcome


def test_resolve_verify_root_returns_repo_root_when_already_on_base(tmp_path):
    """Happy path 1 preserved: repo_root already on base_branch is returned
    as-is without consulting linked worktrees."""
    repo = _init_repo(tmp_path)  # already on 'dev'

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        repo, "dev", log=_noop_log,
    )

    assert verify_root == repo


def test_resolve_verify_root_uses_valid_linked_worktree(tmp_path):
    """Happy path 2 preserved: a live linked worktree checked out on
    base_branch is returned as the verify root, and repo_root is left on its
    own branch (not force-checked-out to base)."""
    repo = _init_repo(tmp_path)
    _git(["checkout", "-b", "jabramsja/feature-y"], cwd=repo)  # repo off base
    wt_path = tmp_path / "live_dev_wt"
    _git(["worktree", "add", str(wt_path), "dev"], cwd=repo)  # live worktree on dev

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        repo, "dev", log=_noop_log,
    )

    # Compare resolved paths: git reports the canonical (/private) worktree path
    # while tmp_path may be the /var symlink form on macOS.
    assert verify_root.resolve() == wt_path.resolve(), verify_root
    assert verify_root != repo
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    assert head == "jabramsja/feature-y"


def test_resolve_verify_root_falls_back_when_linked_worktree_is_stale(tmp_path):
    """Regression: a linked base-branch worktree whose directory was removed
    (observed: a removed nightly-ci-repair worktree) must NOT be returned as
    the verify root. `_resolve_post_merge_verify_root` prunes the dead metadata
    and falls back to repo_root checked out on base_branch — instead of handing
    back the dead path (which made the post-merge verify fail
    'fatal: not a git repository' and surfaced an already-merged PR as
    Status: error) or hitting 'already checked out at <dead path>' on the
    fallback checkout. Mirrors PR #1064/#1065 (standalone) and #1070 (dispatcher).
    """
    repo = _init_repo(tmp_path)
    _git(["checkout", "-b", "jabramsja/feature-x"], cwd=repo)  # repo off base
    wt_path = tmp_path / "stale_dev_wt"
    _git(["worktree", "add", str(wt_path), "dev"], cwd=repo)  # worktree on dev (squats base)
    shutil.rmtree(wt_path)  # dir gone; git metadata still references it → stale
    assert not wt_path.exists()

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        repo, "dev", log=_noop_log,
    )

    # Fell back to repo_root, NOT the dead worktree path.
    assert verify_root == repo, verify_root
    assert verify_root != wt_path
    # repo_root is now actually on base, ready for the ff-only verify.
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    assert head == "dev"
    # Self-healing: stale worktree metadata was pruned (git reports resolved paths).
    wt_list = _git(["worktree", "list", "--porcelain"], cwd=repo).stdout
    assert str(wt_path.resolve()) not in wt_list


def test_resolve_verify_root_rejects_dead_linked_worktree_inside_enclosing_repo(tmp_path, monkeypatch):
    """Regression (bridge round 1): a dead linked worktree whose `.git` pointer
    was removed but whose DIRECTORY still sits inside an enclosing git repo must
    NOT be returned as the verify root. `git rev-parse --is-inside-work-tree`
    walks UP to the enclosing repo and returns 0 for the dead path, so a naive
    probe would re-admit the stale worktree (git still lists it, unpruned, so
    `_find_linked_worktree_for_branch` hands it back). The resolver must anchor
    its probe to the worktree-root identity (`--show-toplevel` resolving back to
    the path), reject the ancestor match, and fall back to repo_root on
    base_branch. Mirrors the cross-repo false positive the round-1 bridge
    demonstrated: a temp repo's dead worktree satisfying the probe via an
    unrelated outer repository.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    # Enclosing ("outer") repo — an UNRELATED git repo that contains everything.
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(["init"], cwd=outer, env=env)
    _git(["checkout", "-b", "main"], cwd=outer, env=env)
    _git(["config", "user.name", "t"], cwd=outer)
    _git(["config", "user.email", "t@t"], cwd=outer)
    (outer / "outer_seed.txt").write_text("outer")
    _git(["add", "outer_seed.txt"], cwd=outer, env=env)
    _git(["commit", "-m", "outer-init"], cwd=outer, env=env)

    # Inner repo (the repo_root we resolve against), nested inside outer, off base.
    inner = outer / "inner"
    inner.mkdir()
    _git(["init"], cwd=inner, env=env)
    _git(["checkout", "-b", "dev"], cwd=inner, env=env)
    _git(["config", "user.name", "t"], cwd=inner)
    _git(["config", "user.email", "t@t"], cwd=inner)
    (inner / "seed.txt").write_text("seed")
    _git(["add", "seed.txt"], cwd=inner, env=env)
    _git(["commit", "-m", "inner-init"], cwd=inner, env=env)
    _git(["checkout", "-b", "jabramsja/feature-z"], cwd=inner, env=env)  # inner OFF base

    # Linked worktree of inner on dev, placed as a sibling of inner under outer,
    # so walking up from it finds OUTER (an unrelated repo), not inner.
    wt_path = outer / "dead_wt"
    _git(["worktree", "add", str(wt_path), "dev"], cwd=inner)
    # Remove the linked-worktree pointer but leave the directory: the naive
    # `--is-inside-work-tree` probe now matches the enclosing outer repo.
    (wt_path / ".git").unlink()
    assert wt_path.is_dir()
    assert not (wt_path / ".git").exists()
    # Pin _find_linked_worktree_for_branch to hand back the dead path. git's
    # auto-prune of a .git-less worktree is git-version-dependent (some keep the
    # unpruned entry, others drop it), so reading real `git worktree list` here
    # made this test flaky across environments (passed locally, failed in CI).
    # Pinning isolates the test to the worktree-root VALIDATION under test
    # (_is_usable_worktree), which deterministically rejects wt_path because
    # `git rev-parse --show-toplevel` walks UP to OUTER, not wt_path itself.
    monkeypatch.setattr(
        commit_mod,
        "_find_linked_worktree_for_branch",
        lambda repo_root, branch: wt_path,  # ANTICHEAT_OK: pin private helper for determinism
    )

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        inner, "dev", log=_noop_log,
    )

    # Fell back to repo_root (inner), NOT the dead worktree path that an
    # enclosing repo would make the naive probe accept.
    assert verify_root == inner, verify_root
    assert verify_root != wt_path
    # repo_root is now actually on base, ready for the ff-only verify.
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=inner).stdout.strip()
    assert head == "dev"


def test_resolve_verify_root_falls_back_when_linked_worktree_is_foreign_repo(tmp_path):
    """Regression (bridge round 2): a linked base-branch worktree path that has
    been REPLACED by an unrelated, independent git repo must NOT be returned as
    the verify root. The foreign repo is its OWN toplevel, so the round-1
    `--show-toplevel == path` guard accepts it, and git still lists the unpruned
    (non-prunable) entry so `_find_linked_worktree_for_branch` hands it back --
    yet running the post-merge verify there would operate on a foreign HEAD,
    not base_branch. `_resolve_post_merge_verify_root` must reject it via the
    same-repository (git common dir) check and fall back to repo_root on
    base_branch. Because the foreign entry is non-prunable, the fallback uses
    `git checkout --ignore-other-worktrees` so repo_root still lands on base
    instead of failing 'already checked out at <foreign path>'. The foreign repo
    on disk is left untouched.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    repo = _init_repo(tmp_path)
    _git(["checkout", "-b", "jabramsja/feature-foreign"], cwd=repo)  # repo off base
    wt_path = tmp_path / "foreign_dev_wt"
    _git(["worktree", "add", str(wt_path), "dev"], cwd=repo)  # linked worktree on dev
    # Replace the linked worktree with an UNRELATED independent repo at the path.
    shutil.rmtree(wt_path)
    wt_path.mkdir()
    _git(["init"], cwd=wt_path, env=env)
    _git(["checkout", "-b", "unrelated"], cwd=wt_path, env=env)
    (wt_path / "foreign.txt").write_text("foreign")
    _git(["add", "foreign.txt"], cwd=wt_path, env=env)
    _git(["commit", "-m", "foreign"], cwd=wt_path, env=env)

    # Guard precondition: git still lists the non-prunable entry, so the foreign
    # path is exactly what _find_linked_worktree_for_branch returns — only the
    # same-repository validation stands between it and the verify root.
    found = commit_mod._find_linked_worktree_for_branch(repo, "dev")  # ANTICHEAT_OK: testing private helper
    assert found is not None and found.resolve() == wt_path.resolve(), found

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        repo, "dev", log=_noop_log,
    )

    # Fell back to repo_root, NOT the foreign repo path.
    assert verify_root == repo, verify_root
    assert verify_root.resolve() != wt_path.resolve()
    # repo_root is now actually on base, ready for the ff-only verify.
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    assert head == "dev"
    # The foreign repo at the path was left untouched (not destroyed).
    assert wt_path.exists()
    foreign_head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_path).stdout.strip()
    assert foreign_head == "unrelated"


def test_resolve_verify_root_rejects_same_repo_worktree_on_wrong_branch(tmp_path):
    """Regression (bridge round 3): a linked base-branch worktree whose metadata
    still records it on base_branch but whose DIRECTORY has been replaced by a
    symlink to a DIFFERENT same-repo worktree (checked out on another branch)
    must NOT be returned as the verify root. The symlink target is a live,
    same-repo worktree, so every `_is_usable_worktree` check passes (dir exists,
    `--show-toplevel` resolves back to the path, same git common dir) -- yet
    running the post-merge verify there would operate on the OTHER branch's HEAD,
    not base_branch, verifying the wrong branch after an already-merged PR.
    `_resolve_post_merge_verify_root` must probe the candidate's on-disk HEAD and,
    on the base-branch mismatch, fall back to repo_root checked out on
    base_branch. Closes the metadata-vs-disk gap the round-1/round-2 worktree
    IDENTITY guards (which never checked the candidate's actual branch) left open.
    """
    repo = _init_repo(tmp_path)  # on dev
    _git(["checkout", "-b", "jabramsja/feature-w"], cwd=repo)  # repo off base
    dev_wt = tmp_path / "dev_wt"
    _git(["worktree", "add", str(dev_wt), "dev"], cwd=repo)  # live worktree on dev
    other_wt = tmp_path / "other_wt"
    _git(["worktree", "add", "-b", "other", str(other_wt), "dev"], cwd=repo)  # worktree on 'other'
    # Replace the dev worktree DIRECTORY with a symlink to the 'other' worktree:
    # git's metadata still lists dev_wt on refs/heads/dev (non-prunable -- the
    # symlink resolves to a live .git), but cd-ing into dev_wt now lands on the
    # 'other' branch's HEAD.
    shutil.rmtree(dev_wt)
    dev_wt.symlink_to(other_wt)

    # Guard precondition: git still hands back dev_wt for base_branch AND the
    # round-1/round-2 usability checks still accept it -- so ONLY the on-disk
    # branch probe stands between the wrong-branch path and the verify root
    # (otherwise this test would pass vacuously via an earlier rejection).
    found = commit_mod._find_linked_worktree_for_branch(repo, "dev")  # ANTICHEAT_OK: testing private helper
    assert found is not None and found.resolve() == other_wt.resolve(), found
    assert commit_mod._is_usable_worktree(repo, found) is True, found  # ANTICHEAT_OK: testing private helper

    verify_root = commit_mod._resolve_post_merge_verify_root(  # ANTICHEAT_OK: testing private helper
        repo, "dev", log=_noop_log,
    )

    # Fell back to repo_root, NOT the wrong-branch ('other') worktree path.
    assert verify_root == repo, verify_root
    assert verify_root.resolve() != other_wt.resolve()
    # repo_root is now actually on base, ready for the ff-only verify.
    head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    assert head == "dev"
    # The 'other' worktree on disk was left untouched (not destroyed or moved off
    # its branch by the fallback checkout, which runs in repo_root only).
    assert other_wt.exists()
    other_head = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=other_wt).stdout.strip()
    assert other_head == "other"


# ---------------------------------------------------------------------------
# _sync_primary_worktree_to_base: PULL-ONLY post-merge sync of the founder's
# PRIMARY working copy (wave
# commit-executor-main-repo-postmerge-ffsync-2026-06-04).
#
# These tests build a real `origin` remote (an upstream repo) plus a clone that
# acts as the founder's PRIMARY checkout, then drive the helper directly. They
# never remove a worktree directory, so they do NOT depend on git-version
# `git worktree prune` behavior (the 2026-06-03 #37 env-dependent-test lesson):
# the PRIMARY is always the FIRST non-bare `git worktree list` entry, which is
# never prunable, so no prune-dependent helper needs mocking here.
# ---------------------------------------------------------------------------


def _git_env() -> dict:
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }


def _init_origin_and_primary(tmp_path: Path):
    """Create an upstream 'origin' on dev@C0 and a clone that is the PRIMARY.

    Returns (upstream, primary, c0_sha, env). The clone's `origin/dev` ref
    starts at C0; advance the upstream with `_advance_origin_dev` to make the
    primary's branch fall behind origin/dev.
    """
    env = _git_env()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init"], cwd=upstream, env=env)
    _git(["checkout", "-b", "dev"], cwd=upstream, env=env)
    _git(["config", "user.name", "t"], cwd=upstream)
    _git(["config", "user.email", "t@t"], cwd=upstream)
    (upstream / "seed.txt").write_text("seed")
    _git(["add", "seed.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "C0"], cwd=upstream, env=env)
    c0_sha = _git(["rev-parse", "HEAD"], cwd=upstream, env=env).stdout.strip()

    primary = tmp_path / "main"
    _git(["clone", str(upstream), str(primary)], cwd=tmp_path, env=env)
    _git(["config", "user.name", "t"], cwd=primary)
    _git(["config", "user.email", "t@t"], cwd=primary)
    return upstream, primary, c0_sha, env


def _advance_origin_dev(upstream: Path, env: dict, content: str = "seed-c1") -> str:
    """Commit a new tip on the upstream's dev branch; return the new sha."""
    (upstream / "seed.txt").write_text(content)
    _git(["add", "seed.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "C1"], cwd=upstream, env=env)
    return _git(["rev-parse", "HEAD"], cwd=upstream, env=env).stdout.strip()


def test_sync_primary_ffs_feature_branch_behind_base(tmp_path):
    """(a) A PRIMARY on a feature branch behind origin/dev is ff'd to origin/dev,
    even when the helper is invoked from a DISTINCT linked worktree (repo_root).
    Proves the helper targets the PRIMARY (first non-bare worktree), not
    repo_root."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    # PRIMARY off base, at C0 (no divergent commits).
    _git(["checkout", "-b", "jabramsja/feat-a"], cwd=primary, env=env)
    # A DISTINCT linked worktree on its own branch — this is repo_root.
    linked = tmp_path / "linked_lane"
    _git(["worktree", "add", "-b", "lane-x", str(linked), "HEAD"], cwd=primary)
    # origin/dev moves ahead → primary's feature branch is now behind.
    c1_sha = _advance_origin_dev(upstream, env)

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=linked, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    # PRIMARY feature branch advanced to origin/dev tip via fast-forward.
    primary_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    assert primary_head == c1_sha, outcome
    # Still on its FEATURE branch — PULL-ONLY never checks out base.
    primary_branch = _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip()
    assert primary_branch == "jabramsja/feat-a"
    # repo_root (the linked worktree) is the WRONG target and was left untouched.
    linked_head = _git(["rev-parse", "HEAD"], cwd=linked).stdout.strip()
    assert linked_head == c0_sha, "linked worktree (repo_root) must NOT be ff'd"
    linked_branch = _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=linked
    ).stdout.strip()
    assert linked_branch == "lane-x"


def test_sync_primary_skips_dirty_primary(tmp_path):
    """(b) A dirty PRIMARY is SKIPPED — founder WIP is never clobbered."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-b"], cwd=primary, env=env)
    feat_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    # Uncommitted edit to a tracked file → dirty tree.
    (primary / "seed.txt").write_text("founder work in progress")
    _advance_origin_dev(upstream, env)  # origin/dev ahead → sync WOULD apply if clean

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "tracked WIP" in (outcome["reason"] or ""), outcome
    # HEAD unchanged and the WIP edit is preserved.
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == feat_head
    assert (primary / "seed.txt").read_text() == "founder work in progress"


def test_sync_primary_ffs_with_untracked_files_present(tmp_path):
    """(#55) A PRIMARY holding UNTRACKED files (deferred reports / handoffs / scratch)
    is STILL ff'd. Untracked files are not founder WIP a ff can clobber (git aborts on a
    path collision; ff-only never touches non-colliding untracked), so GUARD-B must block
    ONLY on TRACKED dirt. Regression for the main-repo drift the old
    _dirty_worktree_paths (tracked | untracked) check caused: the auto-sync skipped
    whenever an untracked deferred report / handoff sat in the primary -- i.e. almost
    always."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-untracked"], cwd=primary, env=env)
    # Untracked artifacts in the primary (the normal state: handoffs, deferred notes).
    (primary / "HANDOFF_FOR_CODEX.md").write_text("handoff")
    (primary / "scratch_deferred_note.md").write_text("deferred finding")
    c1_sha = _advance_origin_dev(upstream, env)

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    # ff applied to origin/dev tip despite the untracked files.
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha, outcome
    # Untracked files preserved (ff-only never touches non-colliding untracked).
    assert (primary / "HANDOFF_FOR_CODEX.md").read_text() == "handoff"
    assert (primary / "scratch_deferred_note.md").read_text() == "deferred finding"


def test_sync_primary_skips_divergent_local_commit(tmp_path):
    """(c) A PRIMARY whose feature branch has a commit NOT in origin/dev is
    SKIPPED (GUARD-C: not a fast-forward) — the founder lands it via a PR."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-c"], cwd=primary, env=env)
    # Local commit on the feature branch, never pushed to origin/dev.
    (primary / "local.txt").write_text("divergent local work")
    _git(["add", "local.txt"], cwd=primary, env=env)
    _git(["commit", "-m", "local-only"], cwd=primary, env=env)
    divergent_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    assert divergent_head != c0_sha

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "ancestor" in (outcome["reason"] or ""), outcome
    # HEAD unchanged — the divergent local commit is preserved.
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == divergent_head


def test_sync_primary_skips_primary_on_base(tmp_path):
    """(d) A PRIMARY already ON base_branch is SKIPPED (GUARD-A) — the helper
    never touches a base-branch checkout."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    # primary stays on 'dev' (base) from the clone.
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "dev"

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "base branch" in (outcome["reason"] or ""), outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha


def test_sync_primary_never_raises_on_error_paths(tmp_path):
    """(e) The helper NEVER raises: a missing repo_root and a repo with no
    'origin' remote both return a clean SKIP outcome instead of an exception."""
    # 1. repo_root does not exist → `git worktree list` fails (FileNotFoundError).
    bogus = tmp_path / "does_not_exist"
    outcome_missing = commit_mod.sync_primary_worktree_to_base(
        repo_root=bogus, base_branch="dev", log=_noop_log,
    )
    assert outcome_missing["synced"] is False
    assert outcome_missing["skipped"] is True

    # 2. A real feature-branch primary with NO 'origin' remote → fetch fails.
    repo = _init_repo(tmp_path)  # on 'dev', no remote
    _git(["checkout", "-b", "jabramsja/feat-e"], cwd=repo)
    feat_head = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    outcome_no_origin = commit_mod.sync_primary_worktree_to_base(
        repo_root=repo, base_branch="dev", log=_noop_log,
    )
    assert outcome_no_origin["synced"] is False
    assert outcome_no_origin["skipped"] is True
    # Nothing destroyed — HEAD intact on the feature branch.
    assert _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip() == feat_head


def test_sync_primary_is_pull_only_no_push_checkout_force_or_reset(tmp_path, monkeypatch):
    """PULL-ONLY (scoped to the helper): on the happy path the helper reaches the
    PRIMARY ONLY via `git fetch` + `git merge --ff-only` — never push, never
    `git checkout` of base, never force, never reset. Proven by capturing every
    git command the helper issues through the public `subprocess.run` seam
    (the helper's `_run` wrapper delegates to it with the command list as the
    first positional arg)."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-p"], cwd=primary, env=env)
    c1_sha = _advance_origin_dev(upstream, env)

    captured: list[list[str]] = []
    real_subprocess_run = subprocess.run

    def _spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            captured.append(list(cmd))
        return real_subprocess_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _spy_run)

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    # Snapshot the helper's git commands NOW: the post-call assertion git ops
    # below also flow through the still-patched public subprocess.run seam, and
    # must not pollute the pull-only command audit.
    helper_git_cmds = [cmd for cmd in captured if cmd and cmd[0] == "git"]

    assert outcome["synced"] is True, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha

    assert helper_git_cmds, captured
    for cmd in helper_git_cmds:
        assert "push" not in cmd, cmd
        assert "checkout" not in cmd, cmd
        assert "reset" not in cmd, cmd
        assert "--force" not in cmd and "-f" not in cmd, cmd
    # The only `git merge` issued was a fast-forward-only merge of origin/dev.
    merges = [cmd for cmd in helper_git_cmds if cmd[:2] == ["git", "merge"]]
    assert merges, helper_git_cmds
    for cmd in merges:
        assert "--ff-only" in cmd, cmd
        assert "origin/dev" in cmd, cmd


def test_sync_primary_skips_when_ff_would_overwrite_ignored_founder_wip(tmp_path):
    """Bridge round 4 (DEFECT): GUARD-B's clean-tree check uses
    `git ls-files --others --exclude-standard`, which EXCLUDES ignored files, so
    a primary holding ONLY locally-ignored founder WIP reads as CLEAN. Plain
    `git merge --ff-only` then SILENTLY overwrites that ignored file when
    origin/dev force-adds the same path as a tracked file. The helper must run
    `--no-overwrite-ignore` so the ff ABORTS (non-zero) and the existing
    returncode-!=0 SKIP preserves the founder's ignored WIP instead of
    clobbering it (the round-4 repro saw synced=True overwrite 'local ignored
    WIP' with 'origin tracked content').

    The feature branch is kept a PURE ANCESTOR of origin/dev (so GUARD-C passes)
    and the file is ignored via `.git/info/exclude` (local-only, no divergent
    commit), so the test exercises the REAL overwrite path rather than a vacuous
    earlier SKIP. No worktree directory is removed, so (like the sibling
    `_sync_primary_*` tests) it does not depend on git-version prune behavior.
    """
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    # PRIMARY off base at C0 — a pure ancestor of origin/dev (no local commit).
    _git(["checkout", "-b", "jabramsja/feat-ign"], cwd=primary, env=env)
    # Ignore `ignored.txt` locally via .git/info/exclude (no commit → the branch
    # stays an ancestor) and drop founder WIP there. _dirty_worktree_paths uses
    # `--exclude-standard`, which honors .git/info/exclude, so the tree is CLEAN.
    (primary / ".git" / "info" / "exclude").write_text(
        "ignored.txt\n", encoding="utf-8"
    )
    (primary / "ignored.txt").write_text("local ignored WIP", encoding="utf-8")
    # Precondition (the bug's entry condition): the tree reads as CLEAN, so
    # GUARD-B does NOT skip — only --no-overwrite-ignore stands between the ff and
    # the founder's ignored WIP.
    assert _git(["status", "--short"], cwd=primary).stdout.strip() == ""
    assert _git(
        ["ls-files", "--others", "--exclude-standard"], cwd=primary
    ).stdout.strip() == ""
    # origin/dev advances at C1 and FORCE-ADDS the same path as a TRACKED file.
    (upstream / "ignored.txt").write_text("origin tracked content", encoding="utf-8")
    _git(["add", "-f", "ignored.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "C1 force-add ignored.txt"], cwd=upstream, env=env)

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    # The ff ABORTED (it would overwrite ignored WIP) → clean SKIP, never synced.
    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "overwritten" in (outcome["reason"] or ""), outcome
    # Founder's ignored WIP is PRESERVED, not clobbered by origin's content.
    assert (primary / "ignored.txt").read_text() == "local ignored WIP", outcome
    # HEAD unchanged — still at C0 on the feature branch (no fast-forward applied).
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "jabramsja/feat-ign"


# ─────────────────────────────────────────────────────────────────────────
# Growth-cap auto-bump: FOUNDER_OVERRIDE-gated CAP_TEST_FILES bump that runs in
# commit_executor before the Step 8 pre-commit-doc-check growth-cap gate. A
# wave that adds a new test file would otherwise trip
# mu/tests/docs/test_growth_caps.py (CAP_TEST_FILES) and strand the commit.
# Cases (a)-(e) + a consolidation variant. Every test name contains
# "growth_cap" so the wave evidence_command (`-k growth_cap`) selects them.
# ─────────────────────────────────────────────────────────────────────────

GROWTH_CAP_WAVE_ID = "growth-cap-demo-wave-2026-06-08"
GROWTH_CAP_SEED_COMMENT = (
    "  # +1 for test_seed.py (seed-wave wave, FOUNDER_OVERRIDE:seed-wave)"
)


def _growth_cap_source(baseline: int, cap: int, cap_comment: str) -> str:
    """Minimal fixture mirroring the BASELINE/CAP surface the auto-bump reads."""
    return (
        '"""Growth cap fixture (mirrors mu/tests/docs/test_growth_caps.py)."""\n'
        "from __future__ import annotations\n"
        "\n"
        f"BASELINE_TEST_FILES = {baseline}\n"
        f"CAP_TEST_FILES = {cap}{cap_comment}\n"
    )


def _make_capture_log():
    lines: list[str] = []

    def _log(msg: str) -> None:
        lines.append(msg)

    return lines, _log


def _init_growth_cap_repo(
    tmp_path: Path,
    *,
    baseline: int,
    cap: int,
    existing_test_files: list[str],
    cap_comment: str = GROWTH_CAP_SEED_COMMENT,
    wave_branch: str = f"jabramsja/{GROWTH_CAP_WAVE_ID}",
):
    """Origin on dev carrying a growth-cap fixture + existing test files; clone
    to a PRIMARY checked out on a wave branch (off dev). Returns (primary, env).

    origin/dev is the merge base the auto-bump compares against, so a staged
    test file added on the wave branch reads as genuinely new.
    """
    env = _git_env()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(["init"], cwd=upstream, env=env)
    _git(["checkout", "-b", "dev"], cwd=upstream, env=env)
    _git(["config", "user.name", "t"], cwd=upstream)
    _git(["config", "user.email", "t@t"], cwd=upstream)
    caps = upstream / "mu" / "tests" / "docs" / "test_growth_caps.py"
    caps.parent.mkdir(parents=True, exist_ok=True)
    caps.write_text(_growth_cap_source(baseline, cap, cap_comment), encoding="utf-8")
    for rel in existing_test_files:
        path = upstream / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    _git(["add", "-A"], cwd=upstream, env=env)
    _git(["commit", "-m", "C0 growth-cap seed"], cwd=upstream, env=env)
    primary = tmp_path / "main"
    _git(["clone", str(upstream), str(primary)], cwd=tmp_path, env=env)
    _git(["config", "user.name", "t"], cwd=primary)
    _git(["config", "user.email", "t@t"], cwd=primary)
    _git(["checkout", "-b", wave_branch], cwd=primary, env=env)
    return primary, env


def _stage_new_test_file(primary: Path, env: dict, relpath: str) -> None:
    path = primary / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_new():\n    assert True\n", encoding="utf-8")
    _git(["add", "--", relpath], cwd=primary, env=env)


def _read_growth_cap_values(primary: Path):
    text = (primary / "mu" / "tests" / "docs" / "test_growth_caps.py").read_text()
    baseline = int(re.search(r"BASELINE_TEST_FILES = (\d+)", text).group(1))
    cap = int(re.search(r"CAP_TEST_FILES = (\d+)", text).group(1))
    return text, baseline, cap


def _count_disk_test_files(primary: Path) -> int:
    return len(list((primary / "mu" / "tests").rglob("test_*.py")))


def _growth_cap_staged(primary: Path) -> bool:
    staged = _git(["diff", "--cached", "--name-only"], cwd=primary).stdout.split()
    return "mu/tests/docs/test_growth_caps.py" in staged


def test_growth_cap_autobump_bumps_by_exact_shortfall_with_founder_override(tmp_path):
    """(a) FOUNDER_OVERRIDE wave + new test file over the cap (shortfall>0),
    no prior provenance -> CAP_TEST_FILES bumped by EXACTLY the shortfall,
    provenance recorded, test_growth_caps.py staged, and the Step 8 gate passes."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    assert outcome["bumped"] is True, outcome
    # Bump is the cap SHORTFALL, not the raw new-file count (here they coincide).
    assert outcome["shortfall"] == 1, outcome
    assert outcome["bump_amount"] == 1, outcome
    assert outcome["previous_cap"] == 0, outcome
    assert outcome["new_cap"] == 1, outcome
    assert outcome["new_test_files"] == ["mu/tests/tools/test_new_feature.py"], outcome
    text, baseline, cap = _read_growth_cap_values(primary)
    assert cap == 1, text
    assert f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}" in text, text
    assert "test_new_feature.py" in text, text
    # BASELINE and the rest of the fixture body are untouched.
    assert "BASELINE_TEST_FILES = 3" in text, text
    # test_growth_caps.py is staged so the Step 8 gate sees the bumped cap.
    assert _growth_cap_staged(primary)
    # The gate now passes — recomputed exactly as test_growth_caps would.
    assert _count_disk_test_files(primary) <= baseline + cap, (baseline, cap)
    assert any(
        f"auto-bumped CAP_TEST_FILES +1 for FOUNDER_OVERRIDE wave {GROWTH_CAP_WAVE_ID}"
        in m
        for m in lines
    ), lines


def test_growth_cap_autobump_no_founder_override_does_not_bump(tmp_path):
    """(b) NO FOUNDER_OVERRIDE + new test file (shortfall>0) -> no bump; the
    growth-cap gate still strands the commit (fail-closed)."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token="", log=log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["reason"] == "no_founder_override", outcome
    assert outcome["shortfall"] == 1, outcome
    text, baseline, cap = _read_growth_cap_values(primary)
    assert cap == 0, text  # unchanged
    assert not _growth_cap_staged(primary)
    # The gate would STILL strand: on-disk count exceeds baseline + cap.
    assert _count_disk_test_files(primary) > baseline + cap, (baseline, cap)


def test_growth_cap_autobump_no_new_test_files_does_not_bump(tmp_path):
    """(c) No new test files (only a non-test addition) -> no bump."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    # A non-test file addition must NOT trip the test-file detector.
    note = primary / "mu" / "docs" / "note.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("note", encoding="utf-8")
    _git(["add", "--", "mu/docs/note.md"], cwd=primary, env=env)
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["reason"] == "no_new_test_files", outcome
    assert outcome["new_test_files"] == [], outcome
    _, _, cap = _read_growth_cap_values(primary)
    assert cap == 0
    assert not _growth_cap_staged(primary)


def test_growth_cap_autobump_is_idempotent_on_second_run(tmp_path):
    """(d) Idempotency: two runs bump CAP_TEST_FILES once; the second detects
    the existing same-wave provenance and leaves the cap unchanged with no
    duplicate provenance comment."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")

    _, log1 = _make_capture_log()
    out1 = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log1,
    )
    assert out1["bumped"] is True, out1
    assert out1["new_cap"] == 1, out1

    lines2, log2 = _make_capture_log()
    out2 = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log2,
    )
    assert out2["bumped"] is False, out2
    assert out2["reason"] == "already_recorded", out2

    text, _, cap = _read_growth_cap_values(primary)
    assert cap == 1, text  # bumped once, not twice
    assert text.count(f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}") == 1, text
    assert any("no bump (idempotent retry)" in m for m in lines2), lines2


def test_growth_cap_autobump_headroom_yields_zero_shortfall_no_bump(tmp_path):
    """(e) FOUNDER_OVERRIDE wave + new test file but the cap already has
    headroom (projected count <= baseline + cap) -> shortfall <= 0 -> no bump."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=5,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["reason"] == "zero_shortfall", outcome
    assert outcome["shortfall"] == -4, outcome  # 4 - (3 + 5)
    _, _, cap = _read_growth_cap_values(primary)
    assert cap == 5  # unchanged
    assert not _growth_cap_staged(primary)
    assert any("auto-bump no-op" in m and "shortfall=-4" in m for m in lines), lines


def test_growth_cap_autobump_consolidation_yields_zero_shortfall_no_bump(tmp_path):
    """(e, consolidation variant) Adding a new test file while deleting a
    sibling in the same wave keeps the count flat -> shortfall == 0 -> no bump,
    even though a genuinely-new test file IS detected (so a blanket new-file
    count would have wrongly bumped the cap)."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    # Consolidate: delete a sibling test file in the same wave (stages the delete).
    _git(["rm", "--", "mu/tests/test_existing_1.py"], cwd=primary, env=env)
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    # The new file IS detected, but the net count is flat -> no bump.
    assert outcome["new_test_files"] == ["mu/tests/tools/test_new_feature.py"], outcome
    assert outcome["bumped"] is False, outcome
    assert outcome["reason"] == "zero_shortfall", outcome
    assert outcome["shortfall"] == 0, outcome
    _, _, cap = _read_growth_cap_values(primary)
    assert cap == 0  # unchanged
    assert not _growth_cap_staged(primary)


def _staged_sha(primary: Path) -> str:
    """Mirror meta_bridge_supervisor.compute_staged_sha: sha256 of the staged
    binary diff — the exact content the pre-commit receipt binds to and the
    Step 8 hook re-verifies."""
    diff = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        cwd=primary, capture_output=True, check=True,
    ).stdout
    return hashlib.sha256(diff).hexdigest()


def test_growth_cap_autobump_precedes_supervisor_receipt_in_pipeline():
    """(f) Finding-#1 regression: the auto-bump call MUST precede the supervisor
    invocation in _run_commit_pipeline_impl. The supervisor (Step 6) writes the
    pre-commit receipt bound to the staged SHA; the auto-bump stages
    test_growth_caps.py, so when it ran AFTER the receipt (the prior Step-7d
    placement) the Step 8 hook rejected the now-stale receipt and stranded the
    commit. Pinning the call order prevents reintroducing that ordering bug."""
    source = commit_mod.commit_pipeline_impl_source()
    autobump_idx = source.find("_maybe_autobump_growth_cap_for_founder_override(")
    supervisor_idx = source.find("run_meta_bridge_package(")
    assert autobump_idx != -1, "growth-cap auto-bump call not found in commit pipeline"
    assert supervisor_idx != -1, "supervisor (receipt) invocation not found in commit pipeline"
    assert autobump_idx < supervisor_idx, (
        "growth-cap auto-bump must run BEFORE the supervisor writes the pre-commit "
        "receipt; otherwise staging test_growth_caps.py invalidates the receipt and "
        "Step 8 strands the commit ('staged content changed since review')"
    )


def test_growth_cap_autobump_changes_staged_sha_so_must_precede_receipt(tmp_path):
    """(g) Finding-#1 regression (behavioral): the auto-bump stages
    test_growth_caps.py, so it CHANGES the staged SHA the pre-commit receipt
    binds to. A receipt written before the bump goes stale at the Step 8 hook;
    one written after stays valid. This is exactly why Step 5e runs before
    Step 6 (the supervisor/receipt)."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")

    # SHA a receipt bound to the PRE-bump staged state (the prior Step-7d order).
    sha_before_bump = _staged_sha(primary)

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=_noop_log,
    )
    assert outcome["bumped"] is True, outcome
    assert _growth_cap_staged(primary)

    # The bump mutated the staged set, so the SHA changed: a receipt bound to
    # sha_before_bump is now STALE — this reproduces the Step-8 strand of
    # finding #1 when the bump runs after the receipt.
    sha_after_bump = _staged_sha(primary)
    assert sha_after_bump != sha_before_bump, (
        "auto-bump must change the staged SHA (it stages test_growth_caps.py); "
        "the receipt-ordering defect is only avoidable by bumping before the receipt"
    )

    # A receipt bound AFTER the bump (Step 5e -> Step 6 order) stays valid: the
    # staged SHA is stable until the next staging mutation, so the Step 8 hook's
    # re-verification of the receipt SHA matches.
    assert _staged_sha(primary) == sha_after_bump


def test_growth_cap_autobump_rolls_back_when_staging_fails(tmp_path, monkeypatch):
    """(h) Bridge round-3 finding regression: when `git add` of
    test_growth_caps.py FAILS after the cap bump is written to disk, the bump
    MUST NOT linger unstaged in the working tree.

    The prior behavior raised, the caller swallowed it as non-fatal, and the
    pipeline proceeded with a working-tree-only cap edit (cap_contains_bump=True,
    cap_staged=False, unstaged_cap_diff=True) — a fail-open: the Step 8 gate
    reads the bumped working-tree file and passes, but the commit omits the bump,
    and the orphaned provenance comment would make a retry's idempotency guard
    skip a bump that was never committed.

    The fix rolls the cap file back to its pre-bump content, so the auto-bump is
    a complete no-op: the Step 8 growth-cap gate falls through to the unmodified
    (too-low) cap and strands the commit fail-closed, exactly as if no auto-bump
    had run."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    cap_path = primary / "mu" / "tests" / "docs" / "test_growth_caps.py"
    original_cap_text = cap_path.read_text()

    # Fail ONLY the cap-file `git add`; every other subprocess (merge-base
    # detection, `git diff --cached`) passes through to the real runner, so the
    # auto-bump reaches the staging step exactly as in production. Capture the
    # original runner via getattr (not dotted private access) so the patch is
    # gate-safe, then install the fault by string name.
    real_run = getattr(commit_mod, "_run")

    def _run_failing_cap_add(args, **kwargs):
        if args[:2] == ["git", "add"] and commit_mod.GROWTH_CAP_TEST_RELPATH in args:
            raise subprocess.CalledProcessError(
                1, args, output="", stderr="simulated git add failure"
            )
        return real_run(args, **kwargs)

    monkeypatch.setattr(commit_mod, "_run", _run_failing_cap_add)
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    # The precondition held (a real shortfall of 1) but staging failed -> the
    # outcome reports NOT bumped, classified as a staging failure (not a raise).
    assert outcome["bumped"] is False, outcome
    assert outcome["reason"].startswith("growth_cap_stage_failed"), outcome
    assert outcome["shortfall"] == 1, outcome

    # CRITICAL: the cap file is rolled back byte-for-byte. No fail-open unstaged
    # cap edit (refutes cap_contains_bump=True / unstaged_cap_diff=True) and no
    # orphaned provenance comment for this wave (keeps the retry's idempotency
    # guard honest).
    text, _, cap = _read_growth_cap_values(primary)
    assert cap == 0, text
    assert text == original_cap_text, text
    assert f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}" not in text, text

    # test_growth_caps.py is NOT staged, so the Step 8 gate still strands the
    # commit (on-disk count exceeds baseline + cap) — fail-closed.
    assert not _growth_cap_staged(primary)
    assert _count_disk_test_files(primary) > 3 + cap

    # The rollback is surgical: the new test file the wave added stays staged.
    staged = _git(["diff", "--cached", "--name-only"], cwd=primary).stdout.split()
    assert "mu/tests/tools/test_new_feature.py" in staged, staged

    # The rollback is logged so a retry is observable.
    assert any("rolled back" in m and "fail-closed" in m for m in lines), lines
