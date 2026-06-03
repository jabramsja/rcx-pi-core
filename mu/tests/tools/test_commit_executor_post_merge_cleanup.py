"""Tests for commit_executor's post-merge cleanup helper.

Covers:
1. Happy path: on base_branch, wave branch + worktree + stashes removed.
2. cleanup_root not on base_branch → skipped with warning (no destruction).
3. Wave branch missing → branch_deleted=False with warning, other steps still run.
4. Worktree distinct path that doesn't exist → worktree step skipped cleanly.
5. No executor-owned stashes for wave_id → 0 dropped, unrelated stashes preserved.
6. Worktree removal unlocks branch so branch_deleted succeeds (order matters).
"""

from __future__ import annotations

import json
import os
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


def test_resolve_verify_root_rejects_dead_linked_worktree_inside_enclosing_repo(tmp_path):
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
    # Guard precondition: git still lists it (unpruned), so the dead path really
    # is what _find_linked_worktree_for_branch returns — only the worktree-root
    # validation stands between it and the verify root.
    assert (
        commit_mod._find_linked_worktree_for_branch(inner, "dev")  # ANTICHEAT_OK: testing private helper
        is not None
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
