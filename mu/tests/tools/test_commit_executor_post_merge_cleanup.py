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

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
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


def _write_program_queue_packet(
    repo: Path,
    relpath: str,
    *,
    wave_id: str,
    status: str,
) -> None:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Packet\n\nStatus: {status}\nWave ID: {wave_id}\n",
        encoding="utf-8",
    )


def _write_program_queue_config(
    repo: Path,
    *,
    wave_id: str,
    title: str,
    tracked_packet: str,
) -> None:
    config_path = repo / "reports" / "control_plane" / f"{wave_id}_wave_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "wave_id": wave_id,
                "title": title,
                "tracked_packet": tracked_packet,
                "request_for_agent": f"Run the {title} launcher packet only.",
            }
        ),
        encoding="utf-8",
    )


def _merge_wave_with_pr(repo: Path, *, wave_id: str, pr_number: int) -> None:
    branch = f"jabramsja/{wave_id}"
    _git(["checkout", "-b", branch], cwd=repo)
    marker = repo / f"{wave_id}.txt"
    marker.write_text(f"{wave_id}\n", encoding="utf-8")
    _git(["add", marker.name], cwd=repo)
    _git(["commit", "-m", f"feat: Phase B implementation for {wave_id}"], cwd=repo)
    _git(["checkout", "dev"], cwd=repo)
    _git(
        [
            "merge",
            "--no-ff",
            branch,
            "-m",
            f"Merge pull request #{pr_number} from jabramsja/{branch}",
        ],
        cwd=repo,
    )


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


def test_post_merge_package_refresh_falls_back_to_simple_program_queue_item(tmp_path):
    repo = _init_repo(tmp_path)
    completed_packet = (
        "reports/control_plane/"
        "founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md"
    )
    _write_queue_packet(repo, completed_packet, "COMPLETED")
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "1. **Surreals** as structure. COMPLETED.\n"
            "2. **Recursive ordinals** as structure.\n"
            "3. **Optimization** -- LAST.\n\n"
            "**DROPPED (do not pursue):** large cardinals.\n"
            "**PARKED (needs splitting before retry):** bridge-lock fix.\n\n"
            "---\n\n"
            "## Ra\n"
            "  4. **[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION] "
            "COMPLETED.** Task: `[NEXT-CODEX-POST-REDTEAM]`. "
            "Wave ID: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`. "
            "Class: `L4_ENABLER`. Category: docs. "
            f"Packet: `{completed_packet}`.\n"
        ),
        encoding="utf-8",
    )
    result = {"pr_number": "1140"}

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha="9f9a3771",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == "recursive-ordinals-as-structure"
    assert package["next_candidates"] == [candidate]
    assert candidate["candidate"] == "recursive-ordinals-as-structure"
    assert candidate["bounded"] is True
    assert candidate["tracked_packet"] is None
    assert "launch_wave.py" in candidate["request_for_claude"]
    assert "executor_dispatch.py" in candidate["request_for_claude"]
    assert "commit_executor.py" in candidate["request_for_claude"]
    assert "post-merge queue empty" in candidate["request_for_claude"]
    assert "large cardinals" not in json.dumps(package)
    assert "bridge-lock" not in json.dumps(package)
    assert "Surreals" not in package["tracker_state_summary"]
    assert result["post_merge_next_wave"] == "recursive-ordinals-as-structure"
    assert result["post_merge_queue_empty"] is False


def test_post_merge_package_refresh_uses_matching_program_queue_config(tmp_path):
    repo = _init_repo(tmp_path)
    packet = "reports/control_plane/surreals-as-structure-2026-06-26_2026-06-26.md"
    config = "reports/control_plane/surreals-as-structure-2026-06-26_wave_config.json"
    (repo / config).parent.mkdir(parents=True, exist_ok=True)
    (repo / config).write_text(
        json.dumps(
            {
                "wave_id": "surreals-as-structure-2026-06-26",
                "tracked_packet": packet,
                "request_for_agent": "Run the Surreals launcher packet only.",
            }
        ),
        encoding="utf-8",
    )
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "1. **Surreals** as structure.\n"
            "2. **Recursive ordinals** as structure.\n\n"
            "---\n\n"
            "## Ra\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1158"},
        merge_sha="f8ebbd06",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == "surreals-as-structure-2026-06-26"
    assert candidate["tracked_packet"] == packet
    assert "Run the Surreals launcher packet only." in candidate["request_for_claude"]
    assert "launch_wave.py" in candidate["request_for_claude"]


def test_post_merge_package_refresh_keeps_unmerged_explicit_current_row_open(tmp_path):
    repo = _init_repo(tmp_path)
    p0imf_wave = "pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22"
    p0imrp_wave = "pr1219-p0imrp-receipt-model-provenance-2026-08-22"
    assert commit_mod._simple_program_queue_explicit_label_wave_id(  # ANTICHEAT_OK: testing private helper
        "[P0IMF] CURRENT"
    ) == ""
    assert commit_mod._simple_program_queue_merge_log_wave_ids(  # ANTICHEAT_OK: testing private helper
        {
            "wave_id": "plain-prose-current-row",
            "derived_wave_id": "plain-prose-current-row",
        }
    ) == set()
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "9. **[PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE-2026-08-22] CURRENT**\n"
            "10. **[PR1219-P0IMRP-RECEIPT-MODEL-PROVENANCE-2026-08-22] NEXT**\n"
            "11. **[ROLES-ALL-CODEX-PR1219-P0IM-CODEX-MODEL-BOOTSTRAP] "
            "QUEUED -- nonlaunchable until exact P0IMRP merge**\n"
            "\n---\n\n"
            "## Ra\n"
        ),
        encoding="utf-8",
    )

    result = {"pr_number": "1230"}
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha="d609cf19",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == p0imf_wave
    assert candidate["candidate"] == p0imf_wave
    assert candidate["tracked_packet"] is None
    assert result["post_merge_next_wave"] == p0imf_wave
    assert "-current" not in candidate["candidate"]
    assert "CURRENT" in package["tracker_state_summary"]
    assert p0imrp_wave not in candidate["candidate"]


def test_post_merge_package_refresh_advances_from_merged_explicit_current_row_without_wave_config(tmp_path):
    repo = _init_repo(tmp_path)
    p0imf_wave = "pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22"
    p0imrp_wave = "pr1219-p0imrp-receipt-model-provenance-2026-08-22"
    _merge_wave_with_pr(repo, wave_id=p0imf_wave, pr_number=1230)
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "9. **[PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE-2026-08-22] CURRENT**\n"
            "10. **[PR1219-P0IMRP-RECEIPT-MODEL-PROVENANCE-2026-08-22] NEXT**\n"
            "11. **[ROLES-ALL-CODEX-PR1219-P0IM-CODEX-MODEL-BOOTSTRAP] "
            "QUEUED -- nonlaunchable until exact P0IMRP merge**\n"
            "\n---\n\n"
            "## Ra\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1230"},
        merge_sha="d609cf19",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == p0imrp_wave
    assert candidate["candidate"] == p0imrp_wave
    assert candidate["tracked_packet"] is None
    assert "P0IMRP" in package["tracker_state_summary"]
    assert "P0IMF" not in candidate["summary"]


def test_post_merge_package_refresh_skips_completed_simple_program_queue_items_with_explicit_wave_id(tmp_path):
    repo = _init_repo(tmp_path)
    recursive_wave = "recursive-ordinals-as-structure-2026-06-26"
    recursive_packet = (
        f"reports/control_plane/{recursive_wave}_2026-06-26.md"
    )
    w_types_wave = "w-types-inductive-types-ast-as-inductive-structure-2026-06-26"
    w_types_packet = f"reports/control_plane/{w_types_wave}_2026-06-26.md"
    _write_program_queue_packet(
        repo,
        recursive_packet,
        wave_id=recursive_wave,
        status="IMPLEMENTED / LOCAL EVIDENCE",
    )
    _write_program_queue_packet(
        repo,
        w_types_packet,
        wave_id=w_types_wave,
        status="IMPLEMENTED / LOCAL EVIDENCE",
    )
    _write_program_queue_config(
        repo,
        wave_id=recursive_wave,
        title="Recursive Ordinals As Structure 2026-06-26",
        tracked_packet=recursive_packet,
    )
    _write_program_queue_config(
        repo,
        wave_id=w_types_wave,
        title="W Types Inductive Types AST As Inductive Structure 2026-06-26",
        tracked_packet=w_types_packet,
    )
    _merge_wave_with_pr(repo, wave_id=recursive_wave, pr_number=1160)
    _merge_wave_with_pr(repo, wave_id=w_types_wave, pr_number=1161)
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "1. **Recursive ordinals** as structure.\n"
            "2. **W-types / inductive types** "
            "(AST-as-inductive-structure; self-hosting building block).\n"
            "3. **Coinduction** (non-termination as structure). NEXT.\n"
            "4. **Fixpoint** -- meta-circular evaluator-as-structure.\n"
            "5. **Optimization** -- LAST.\n\n"
            "---\n\n"
            "## Ra\n"
            f"- Tracker sync note (2026-06-27, {recursive_wave}): "
            "**NEXT-CODEX-POST-REDTEAM -- pre-commit supervisor package refresh.** "
            f"Packet: `{recursive_packet}`. "
            "Pre-commit supervisor receipt remains pending for the current staged package.\n"
            f"- Tracker sync note (2026-06-27, {w_types_wave}): "
            "**NEXT-CODEX-POST-REDTEAM -- pre-commit supervisor package refresh.** "
            f"Packet: `{w_types_packet}`. "
            "Pre-commit supervisor receipt remains pending for the current staged package.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1161"},
        merge_sha="6a6b4217",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == "coinduction-non-termination-as-structure"
    assert candidate["candidate"] == "coinduction-non-termination-as-structure"
    assert candidate["tracked_packet"] is None
    assert "Coinduction" in package["tracker_state_summary"]
    assert "W-types" not in candidate["summary"]
    assert recursive_packet not in package["deferred_items"]
    assert w_types_packet not in package["deferred_items"]


def test_post_merge_package_refresh_does_not_skip_simple_queue_item_from_precommit_tracker_note_only(tmp_path):
    repo = _init_repo(tmp_path)
    w_types_wave = "w-types-inductive-types-ast-as-inductive-structure-2026-06-26"
    w_types_packet = f"reports/control_plane/{w_types_wave}_2026-06-26.md"
    _write_program_queue_packet(
        repo,
        w_types_packet,
        wave_id=w_types_wave,
        status="IMPLEMENTED / LOCAL EVIDENCE",
    )
    _write_program_queue_config(
        repo,
        wave_id=w_types_wave,
        title="W Types Inductive Types AST As Inductive Structure 2026-06-26",
        tracked_packet=w_types_packet,
    )
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "1. **W-types / inductive types** "
            "(AST-as-inductive-structure; self-hosting building block).\n"
            "2. **Coinduction** (non-termination as structure).\n\n"
            "---\n\n"
            "## Ra\n"
            f"- Tracker sync note (2026-06-27, {w_types_wave}): "
            "**NEXT-CODEX-POST-REDTEAM -- pre-commit supervisor package refresh.** "
            f"Packet: `{w_types_packet}`. "
            "Pre-commit supervisor receipt remains pending for the current staged package.\n"
        ),
        encoding="utf-8",
    )

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: testing private helper
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1161"},
        merge_sha="not-landed",
        log=_noop_log,
    )

    candidate = package["next_candidates"][0]
    assert package["wave_name"] == w_types_wave
    assert candidate["candidate"] == w_types_wave
    assert candidate["tracked_packet"] == w_types_packet
    assert "W-types / inductive types" in package["tracker_state_summary"]


def test_post_merge_package_refresh_orders_unnumbered_batons_before_numbered_row(
    tmp_path,
):
    repo = _init_repo(tmp_path)
    landed_wave = "landed-queue-prerequisite-2026-08-26"
    provider_isolation_wave = "test-provider-isolation-root-r3-2026-08-26"
    hybrid_reader_wave = "hybrid-reader-terminality-prerequisite-r1-2026-08-26"
    hybrid_reader_packet = f"reports/control_plane/{hybrid_reader_wave}.md"
    numbered_wave = (
        "roles-all-codex-pr1219-p0ibrrcp-normal-root-recorded-child-cleanup"
    )
    _write_program_queue_packet(
        repo,
        hybrid_reader_packet,
        wave_id=hybrid_reader_wave,
        status="QUEUED - AFTER PROVIDER ISOLATION",
    )
    _write_program_queue_config(
        repo,
        wave_id=hybrid_reader_wave,
        title="Hybrid Reader Terminality",
        tracked_packet=hybrid_reader_packet,
    )
    (repo / "TASKS.md").write_text(
        (
            "**Unnumbered prerequisite baton — outside-section decoy NEXT**\n\n"
            "## PROGRAM QUEUE (priority order)\n\n"
            f"**Unnumbered prerequisite baton — [{landed_wave.upper()}] LANDED**\n"
            "**Unnumbered landed prerequisite — ignored landed prose**\n"
            "**Unnumbered arbitrary baton — ignored arbitrary prose**\n"
            "**Unnumbered prerequisite baton — "
            f"[{provider_isolation_wave.upper()}] NEXT**\n"
            "**Unnumbered prerequisite baton — hybrid-reader terminality NEXT**\n"
            "**Unnumbered reconstruction baton — "
            "provider-neutral bridge context AFTER BOTH**\n"
            "23. **[ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP] NEXT**\n\n"
            "## NON-LAUNCHABLE PROGRAM GOVERNANCE AND HISTORY\n\n"
            "**Unnumbered reconstruction baton — outside-section reconstruction NEXT**\n"
        ),
        encoding="utf-8",
    )

    entries = commit_mod._simple_program_queue_entries(  # ANTICHEAT_OK: exact parser ordering regression
        repo,
        existing_wave_ids=set(),
    )
    assert [entry["wave_id"] for entry in entries] == [
        landed_wave,
        provider_isolation_wave,
        hybrid_reader_wave,
        "provider-neutral-bridge-context",
        numbered_wave,
    ]
    assert entries[3]["queue_text"] == "provider-neutral bridge context AFTER BOTH"

    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: unnumbered queue ordering regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1248"},
        merge_sha="provider-isolation-predecessor",
        log=_noop_log,
    )
    assert package["wave_name"] == provider_isolation_wave

    _merge_wave_with_pr(repo, wave_id=provider_isolation_wave, pr_number=1249)
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: completed baton skip regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1249"},
        merge_sha="provider-isolation-merge",
        log=_noop_log,
    )
    assert package["wave_name"] == hybrid_reader_wave
    assert package["next_candidates"][0]["tracked_packet"] == hybrid_reader_packet

    _merge_wave_with_pr(repo, wave_id=hybrid_reader_wave, pr_number=1250)
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: reconstruction baton ordering regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result={"pr_number": "1250"},
        merge_sha="hybrid-reader-merge",
        log=_noop_log,
    )
    assert package["wave_name"] == "provider-neutral-bridge-context"
    assert "AFTER BOTH" in package["tracker_state_summary"]
    assert numbered_wave not in json.dumps(package)


def test_exact_commit_post_merge_package_refresh_skips_merged_self_baton_and_selects_provider_isolation_r3(
    tmp_path,
):
    repo = _init_repo(tmp_path)
    (repo / ".gitignore").write_text(".agent_bus/\n", encoding="utf-8")
    _git(["add", ".gitignore"], cwd=repo)
    _git(["commit", "-m", "ignore active bus output"], cwd=repo)

    queue_fix_wave = "p0ibrrcp-postmerge-baton-queue-r1-2026-08-26"
    provider_isolation_wave = "test-provider-isolation-root-r3-2026-08-26"
    numbered_wave = (
        "roles-all-codex-pr1219-p0ibrrcp-normal-root-recorded-child-cleanup"
    )
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "**Unnumbered prerequisite baton — "
            f"[{queue_fix_wave.upper()}] CURRENT**\n"
            "**Unnumbered prerequisite baton — "
            f"[{provider_isolation_wave.upper()}] NEXT**\n"
            "**Unnumbered prerequisite baton — hybrid-reader terminality NEXT**\n"
            "**Unnumbered reconstruction baton — "
            "provider-neutral bridge context AFTER BOTH**\n"
            "23. **[ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP] NEXT**\n\n"
            "## NON-LAUNCHABLE PROGRAM GOVERNANCE AND HISTORY\n"
        ),
        encoding="utf-8",
    )
    _git(["add", "TASKS.md"], cwd=repo)
    _git(["commit", "-m", "record baton queue authority"], cwd=repo)
    _merge_wave_with_pr(repo, wave_id=queue_fix_wave, pr_number=1248)
    authority_sha = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

    # Contradict the live filesystem after the exact merge. The SHA-qualified
    # queue read must neither select this numbered row nor rewrite live TASKS.
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            "23. **[ROLES-ALL-CODEX-PR1219-P0IBRRCP-NORMAL-ROOT-RECORDED-CHILD-CLEANUP] CURRENT**\n\n"
            "## NON-LAUNCHABLE PROGRAM GOVERNANCE AND HISTORY\n"
        ),
        encoding="utf-8",
    )
    live_tasks = (repo / "TASKS.md").read_bytes()
    live_status = _git(
        ["status", "--porcelain=v1", "--untracked-files=all"], cwd=repo
    ).stdout
    live_entry = commit_mod._next_open_founder_ordered_queue_entry(repo)  # ANTICHEAT_OK: contradictory live queue proof
    assert live_entry is not None
    assert live_entry["wave_id"] == numbered_wave

    result = {"pr_number": "1248"}
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: exact merge self-skip regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha=authority_sha,
        log=_noop_log,
        queue_commit_sha=authority_sha,
    )

    assert package["merge_sha"] == authority_sha
    assert package["wave_name"] == provider_isolation_wave
    assert package["next_candidates"][0]["candidate"] == provider_isolation_wave
    assert numbered_wave not in json.dumps(package)
    assert result["post_merge_next_wave"] == provider_isolation_wave
    assert (repo / "TASKS.md").read_bytes() == live_tasks
    assert _git(
        ["status", "--porcelain=v1", "--untracked-files=all"], cwd=repo
    ).stdout == live_status


def test_post_merge_package_refresh_uses_exact_commit_over_stale_dirty_tree(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / ".gitignore").write_text(".agent_bus/\n", encoding="utf-8")
    _git(["add", ".gitignore"], cwd=repo)
    _git(["commit", "-m", "ignore active bus output"], cwd=repo)

    history_wave = "history-completed-queue-wave-2026-08-23"
    tracker_wave = "tracker-completed-queue-wave-2026-08-23"
    expected_wave = "expected-fetched-successor-2026-08-23"
    fallback_wave = "fallback-after-fetched-successor-2026-08-23"
    dirty_wave = "dirty-live-routed-wave-2026-08-23"
    standalone_wave = "standalone-governance-renewal-2026-08-23"
    expected_packet = f"reports/control_plane/{expected_wave}.md"
    generic_config = (
        "reports/control_plane/generic_fetched_successor_wave_config.json"
    )
    dirty_config = "reports/control_plane/aaa_dirty_live_wave_config.json"
    exact_blocker = "reports/deferred/blocking/exact_commit_blocker.md"
    dirty_packet = f"reports/control_plane/{dirty_wave}.md"
    dirty_blocker = "reports/deferred/blocking/dirty_live_blocker.md"

    _merge_wave_with_pr(repo, wave_id=history_wave, pr_number=1217)
    _write_program_queue_packet(
        repo,
        expected_packet,
        wave_id=expected_wave,
        status="QUEUED - EXACT COMMIT AUTHORITY",
    )
    _write_program_queue_packet(
        repo,
        dirty_packet,
        wave_id=dirty_wave,
        status="COMPLETED - NOT A ROUTED AUTHORITY ENTRY",
    )
    config_path = repo / generic_config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "title": "Generic fetched successor launcher",
                "tracked_packet": expected_packet,
                "request_for_agent": "Use the immutable fetched-tree request only.",
            }
        ),
        encoding="utf-8",
    )
    exact_blocker_path = repo / exact_blocker
    exact_blocker_path.parent.mkdir(parents=True, exist_ok=True)
    exact_blocker_path.write_text("# Exact commit blocker\n", encoding="utf-8")
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            f"1. **[{history_wave.upper()}] CURRENT**\n"
            f"2. **[{tracker_wave.upper()}] NEXT**\n"
            f"3. **[{expected_wave.upper()}] NEXT**\n"
            f"4. **[{fallback_wave.upper()}] LAST**\n\n"
            "---\n\n"
            "## Ra\n"
            f"- Tracker sync note (2026-08-23, {tracker_wave}): "
            "**COMPLETED / POST-MERGE.**\n"
            f"- Tracker sync note (2026-08-23, {standalone_wave}): "
            "**NEXT-CODEX-POST-REDTEAM - standalone governance renewal.** "
            "Packet: `(standalone governance renewal; no Phase-A packet)`.\n"
            f"- Tracker sync note (2026-08-23, {expected_wave}): "
            "**PRE-COMMIT / RECEIPT PENDING.**\n"
            f"- Tracker sync note (2026-08-23, {dirty_wave}): "
            "**STATUS AUTHORITY PROBE.** Class: L4_ENABLER. Category: tests. "
            f"Packet: `{dirty_packet}`.\n"
        ),
        encoding="utf-8",
    )
    _git(
        ["add", "TASKS.md", "reports/control_plane", "reports/deferred/blocking"],
        cwd=repo,
    )
    _git(["commit", "-m", "record immutable queue authority"], cwd=repo)
    authority_sha = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()

    # A later merge on the live branch proves exact completion history is
    # bounded to authority_sha rather than HEAD or another moving ref.
    _merge_wave_with_pr(repo, wave_id=expected_wave, pr_number=1218)
    live_head = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    _git(["update-ref", "refs/remotes/origin/dev", live_head], cwd=repo)
    authority_log = _git(
        ["log", "--merges", "--format=%s%n%b", authority_sha, "--"],
        cwd=repo,
    ).stdout
    live_log = _git(
        ["log", "--merges", "--format=%s%n%b", "HEAD", "--"],
        cwd=repo,
    ).stdout
    assert history_wave in authority_log
    assert expected_wave not in authority_log
    assert expected_wave in live_log

    # Deliberately make every live queue surface stale or contradictory.
    (repo / "TASKS.md").write_text(
        (
            "## PROGRAM QUEUE (priority order)\n\n"
            f"1. **[{expected_wave.upper()}] CURRENT**\n"
            f"2. **[{fallback_wave.upper()}] LAST**\n\n"
            "---\n\n"
            "## Ra\n"
            f"- Tracker sync note (2026-08-23, {expected_wave}): "
            "**COMPLETED / POST-MERGE.**\n"
            f"- Tracker sync note (2026-08-23, {dirty_wave}): "
            "**DIRTY LIVE ROUTE.** Class: L4_ENABLER. Category: tests. "
            f"Packet: `{dirty_packet}`.\n"
        ),
        encoding="utf-8",
    )
    config_path.unlink()
    dirty_config_path = repo / dirty_config
    dirty_config_path.write_text(
        json.dumps(
            {
                "wave_id": expected_wave,
                "tracked_packet": dirty_packet,
                "request_for_agent": "Use the dirty filesystem request.",
            }
        ),
        encoding="utf-8",
    )
    (repo / expected_packet).unlink()
    exact_blocker_path.unlink()
    _write_program_queue_packet(
        repo,
        dirty_packet,
        wave_id=dirty_wave,
        status="Routed - Phase A required before implementation",
    )
    dirty_blocker_path = repo / dirty_blocker
    dirty_blocker_path.write_text("# Dirty live blocker\n", encoding="utf-8")
    dirty_sentinel = repo / "dirty-untracked-sentinel.txt"
    dirty_sentinel.write_text("preserve me exactly\n", encoding="utf-8")

    observed_paths = [
        "TASKS.md",
        generic_config,
        dirty_config,
        expected_packet,
        exact_blocker,
        dirty_packet,
        dirty_blocker,
        dirty_sentinel.name,
    ]

    def git_visible_state() -> dict[str, object]:
        return {
            "branch": _git(["symbolic-ref", "--short", "HEAD"], cwd=repo).stdout,
            "head": _git(["rev-parse", "HEAD"], cwd=repo).stdout,
            "dev_ref": _git(["rev-parse", "refs/heads/dev"], cwd=repo).stdout,
            "origin_dev_ref": _git(
                ["rev-parse", "refs/remotes/origin/dev"], cwd=repo
            ).stdout,
            "porcelain": _git(
                ["status", "--porcelain=v1", "--untracked-files=all"], cwd=repo
            ).stdout,
            "cached_diff": _git(["diff", "--cached", "--binary"], cwd=repo).stdout,
            "content": {
                relpath: (repo / relpath).read_bytes()
                if (repo / relpath).is_file()
                else None
                for relpath in observed_paths
            },
        }

    before = git_visible_state()
    legacy_entry = commit_mod._next_open_founder_ordered_queue_entry(repo)  # ANTICHEAT_OK: compare legacy dirty filesystem queue parsing
    assert legacy_entry is not None
    assert legacy_entry["wave_id"] == dirty_wave

    result = {"pr_number": "1219"}
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: exact-commit queue/package regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha=authority_sha,
        log=_noop_log,
        queue_commit_sha=authority_sha,
    )
    after = git_visible_state()

    candidate = package["next_candidates"][0]
    assert package["merge_sha"] == authority_sha
    assert package["wave_name"] == expected_wave
    assert "queue_commit_sha" not in package
    assert candidate["candidate"] == expected_wave
    assert candidate["tracked_packet"] == expected_packet
    assert "immutable fetched-tree request" in candidate["request_for_claude"]
    assert "dirty filesystem request" not in candidate["request_for_claude"]
    assert package["blocker_report_paths"] == [exact_blocker]
    assert dirty_blocker not in package["blocker_report_paths"]
    assert result["post_merge_package_path"] == (
        ".agent_bus/meta/post_merge_package.json"
    )
    package_path = repo / result["post_merge_package_path"]
    assert json.loads(package_path.read_text(encoding="utf-8")) == package
    assert before == after


def test_exact_commit_queue_read_failure_preserves_existing_package(tmp_path):
    repo = _init_repo(tmp_path)
    commit_without_tasks = _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    (repo / "TASKS.md").write_text(
        "## PROGRAM QUEUE (priority order)\n\n1. **Dirty fallback** item.\n",
        encoding="utf-8",
    )
    package_path = repo / ".agent_bus" / "meta" / "post_merge_package.json"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    original_package = b'{"sentinel":"preserve-existing-package"}\n'
    package_path.write_bytes(original_package)
    result = {"pr_number": "1219", "sentinel": "unchanged"}
    original_result = dict(result)

    with pytest.raises(
        commit_mod.QueueCommitAuthorityError,
        match="required queue blob is absent",
    ):
        commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: fail-closed exact-object read regression
            repo_root=repo,
            handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
            result=result,
            merge_sha=commit_without_tasks,
            log=_noop_log,
            queue_commit_sha=commit_without_tasks,
        )

    assert package_path.read_bytes() == original_package
    assert result == original_result

    with pytest.raises(
        commit_mod.QueueCommitAuthorityError,
        match="merge_sha must equal queue_commit_sha",
    ):
        commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: reject split merge/content authority before writing
            repo_root=repo,
            handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
            result=result,
            merge_sha="f" * 40,
            log=_noop_log,
            queue_commit_sha=commit_without_tasks,
        )

    assert package_path.read_bytes() == original_package
    assert result == original_result


def test_post_merge_terminal_sweep_precedes_successor_package_authority():
    """A successor package cannot exist until cleanup and sweep both finish."""
    source = commit_mod.post_commit_pipeline_source()
    prepare_idx = source.find("prepare_terminal_sweep_receipt(")
    cleanup_idx = source.find("_post_merge_cleanup(")
    finalize_idx = source.find("finalize_terminal_sweep_receipt(")
    package_idx = source.find("_refresh_post_merge_package_for_next_open_queue(")

    assert prepare_idx != -1, "pre-cleanup terminal receipt capture not found"
    assert cleanup_idx != -1, "post-merge carrier cleanup not found"
    assert finalize_idx != -1, "post-cleanup terminal receipt finalization not found"
    assert package_idx != -1, "successor package publication not found"
    assert prepare_idx < cleanup_idx < finalize_idx < package_idx, (
        "terminal evidence must be captured before cleanup, then cleanup and "
        "terminal receipt finalization must both precede successor package "
        "authority"
    )


def test_step14_behind_refresh_rebinds_terminal_carrier_commit(
    tmp_path,
    monkeypatch,
):
    """Terminal preparation receives the carrier HEAD advanced by Step 14."""
    carrier = tmp_path / "carrier"
    carrier.mkdir()
    survivor = tmp_path / "survivor"
    survivor.mkdir()
    merge_script = carrier / "mu" / "tools" / "hooks" / "merge_pr.sh"
    merge_script.parent.mkdir(parents=True)
    merge_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    wave_id = "pr-disposition-apply-r2-2026-09-10"
    target_branch = f"jabramsja/{wave_id}"
    old_sha = "1" * 40
    refreshed_sha = "2" * 40
    merge_sha = "3" * 40
    candidate_sha = "4" * 64
    handoff = {
        "wave_id": wave_id,
        "branch_prefix": "jabramsja",
        "target_branch": target_branch,
        "base_branch": "dev",
    }
    continuation = {
        "commit_sha": old_sha,
        "pr_number": "1281",
        "receipt_decision": "COMMIT_GO",
        "staged_candidate_sha256": candidate_sha,
        "steps_completed": [
            "validate_inputs",
            "ensure_feature_branch",
            "validate_scope",
            "stage_files",
            "validate_tests",
            "pre_commit_supervisor",
            "validate_receipt",
            "run_pre_commit_script",
            "git_commit",
            "hold_check",
            "git_push",
            "ensure_pr",
        ],
    }
    carrier_state = {"head": old_sha}
    events: list[str] = []
    terminal_args: dict[str, str] = {}
    published: dict[str, object] = {}

    def auto_resolve(*args, **kwargs):
        assert carrier_state["head"] == old_sha
        carrier_state["head"] = refreshed_sha
        events.append("behind_refresh")
        return {
            "resolved": True,
            "action": "clean_merge",
            "detail": "merged origin/dev cleanly and pushed",
        }

    def wait_for_ci(*args, **kwargs):
        result = kwargs["result"]
        if "wait_ci" not in result["steps_completed"]:
            result["steps_completed"].append("wait_ci")
        return None

    def run_command(cmd, cwd=None, timeout=None, check=True, env=None):
        if cmd == ["git", "rev-parse", "HEAD"]:
            head = carrier_state["head"] if Path(cwd) == carrier else merge_sha
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{head}\n", stderr="")
        if cmd[:1] == ["bash"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd == ["git", "fetch", "origin", "dev"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd == ["git", "merge", "--ff-only", "origin/dev"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command {cmd!r} in {cwd}")

    class FakeTerminalAuthority:
        @staticmethod
        def requires_terminal_sweep(candidate_wave_id):
            return candidate_wave_id == wave_id

        @staticmethod
        def prepare_terminal_sweep_receipt(repo_root, **kwargs):
            events.append("prepare")
            terminal_args.update(kwargs)
            assert Path(repo_root) == survivor
            assert kwargs["carrier_root"] == carrier
            assert kwargs["carrier_commit_sha"] == refreshed_sha
            assert kwargs["candidate_sha256"] == candidate_sha
            return {
                "receipt": {"wave_id": wave_id, "merge_sha": merge_sha},
                "receipt_path": str(tmp_path / "terminal-receipt.json"),
            }

        @staticmethod
        def finalize_terminal_sweep_receipt(repo_root, prepared, **kwargs):
            events.append("finalize")
            assert Path(repo_root) == survivor
            return {
                "binding": {
                    "decision": "PASS",
                    "merge_sha": merge_sha,
                    "path": "terminal-receipt.json",
                    "sha256": "5" * 64,
                    "wave_id": wave_id,
                }
            }

        @staticmethod
        def validate_terminal_receipt_authority(
            repo_root,
            binding,
            *,
            expected_merge_sha,
        ):
            assert Path(repo_root) == survivor
            assert binding["merge_sha"] == expected_merge_sha == merge_sha
            return {"valid": True, "decision": "PASS", "error": ""}

    def cleanup(**kwargs):
        events.append("cleanup")
        return {
            "branch_deleted": True,
            "status": "success",
            "stashes_dropped": 0,
            "warnings": [],
            "worktree_removed": True,
        }

    def publish(**kwargs):
        events.append("publish")
        published.update(kwargs)
        return {"next_candidates": [{"candidate": "fleet-cleanup-builder"}]}

    monkeypatch.setattr(commit_mod, "validate_handoff", lambda *args, **kwargs: (True, []))
    monkeypatch.setattr(
        commit_mod,
        "_resolve_control_surface_founder_override_token",
        lambda *args, **kwargs: "",
    )
    monkeypatch.setattr(
        commit_mod,
        "_load_post_commit_continuation",
        lambda *args, **kwargs: dict(continuation),
    )
    monkeypatch.setattr(commit_mod, "_commit_lifecycle_pager_enabled", lambda *args: False)
    monkeypatch.setattr(commit_mod, "ensure_not_agent_review_mode", lambda *args: None)
    monkeypatch.setattr(
        commit_mod,
        "_maybe_demote_completed_handoff_state_for_commit_retry",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(commit_mod, "_try_auto_resolve_pr_conflict", auto_resolve)
    monkeypatch.setattr(commit_mod, "_wait_for_pr_ci", wait_for_ci)
    monkeypatch.setattr(commit_mod, "_parse_origin_owner_repo", lambda *args: ("o", "r"))
    monkeypatch.setattr(
        commit_mod,
        "_query_pr_review_state",
        lambda *args, **kwargs: {"headRefOid": refreshed_sha},
    )
    monkeypatch.setattr(commit_mod, "_has_fresh_connector_review", lambda *args: True)
    monkeypatch.setattr(
        commit_mod,
        "_extract_review_findings",
        lambda *args, **kwargs: {"outcome": "clear", "bot_findings": []},
    )
    monkeypatch.setattr(
        commit_mod,
        "_ensure_current_draft_pr_ready_for_review",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        commit_mod,
        "_resolve_post_merge_verify_root",
        lambda *args, **kwargs: survivor,
    )
    monkeypatch.setattr(
        commit_mod,
        "_sync_primary_worktree_to_base",
        lambda *args, **kwargs: {"status": "skipped"},
    )
    monkeypatch.setattr(
        commit_mod,
        "_load_pr_disposition_executor_module",
        lambda: FakeTerminalAuthority(),
    )
    monkeypatch.setattr(commit_mod, "_post_merge_cleanup", cleanup)
    monkeypatch.setattr(
        commit_mod,
        "_refresh_post_merge_package_for_next_open_queue",
        publish,
    )
    monkeypatch.setattr(commit_mod, "_clear_continuation_record", lambda *args: None)
    monkeypatch.setattr(commit_mod, "_run", run_command)

    result = commit_mod.run_commit_pipeline(handoff, repo_root=carrier)

    assert old_sha != refreshed_sha
    assert result["status"] == "success"
    assert result["commit_sha"] == refreshed_sha
    assert terminal_args["carrier_commit_sha"] == refreshed_sha
    assert published["terminal_receipt"]["decision"] == "PASS"
    assert events == ["behind_refresh", "prepare", "cleanup", "finalize", "publish"]


@pytest.mark.parametrize(
    ("decision", "expected_candidate"),
    [
        ("PASS", "fleet-cleanup-builder"),
        ("HOLD", "pr-disposition-reconciliation"),
    ],
)
def test_terminal_receipt_package_routes_one_non_apply_candidate(
    tmp_path,
    monkeypatch,
    decision,
    expected_candidate,
):
    """PASS routes Fleet and HOLD routes reconciliation; Apply stays consumed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    merge_sha = "a" * 40
    binding = {
        "decision": decision,
        "merge_sha": merge_sha,
        "receipt_path": "/surviving/common-dir/terminal-receipt.json",
        "wave_id": "pr-disposition-terminal-sweep-enabler-r1-2026-09-10",
    }

    class FakeTerminalAuthority:
        TERMINAL_FLEET_CANDIDATE = "fleet-cleanup-builder"
        TERMINAL_RECONCILIATION_CANDIDATE = "pr-disposition-reconciliation"

        def validate_terminal_receipt_authority(
            self,
            repo_root,
            terminal_receipt,
            *,
            expected_merge_sha,
        ):
            assert repo_root == repo
            assert terminal_receipt == binding
            assert expected_merge_sha == merge_sha
            return {"valid": True, "decision": decision}

    monkeypatch.setattr(
        commit_mod,
        "_load_pr_disposition_executor_module",
        lambda: FakeTerminalAuthority(),
    )
    monkeypatch.setattr(
        commit_mod,
        "_next_open_founder_ordered_queue_entry",
        lambda _repo_root, *, queue_commit_sha="": {
            "wave_id": "fleet-cleanup-builder-r1-2026-09-10"
        },
    )
    monkeypatch.setattr(
        commit_mod,
        "_post_merge_blocker_report_paths",
        lambda _repo_root, *, queue_commit_sha="": [],
    )

    result = {"pr_number": "1219"}
    package = commit_mod._refresh_post_merge_package_for_next_open_queue(  # ANTICHEAT_OK: receipt-bound terminal routing regression
        repo_root=repo,
        handoff={"task_id": "[NEXT-CODEX-POST-REDTEAM]"},
        result=result,
        merge_sha=merge_sha,
        log=_noop_log,
        terminal_receipt=binding,
    )

    candidates = package["next_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["candidate"] == expected_candidate
    assert candidates[0]["terminal_receipt"] == binding
    assert all("apply" not in item["candidate"].lower() for item in candidates)
    assert package["wave_name"] == expected_candidate
    assert package["terminal_receipt"] == binding
    assert result["post_merge_next_wave"] == expected_candidate
    assert json.loads(
        (repo / result["post_merge_package_path"]).read_text(encoding="utf-8")
    ) == package


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


def _advance_origin_dev_add_file(
    upstream: Path,
    env: dict,
    path: str = "origin_only.txt",
    content: str = "origin-only\n",
) -> str:
    """Commit a new non-overlapping file on upstream dev; return the new sha."""
    (upstream / path).write_text(content)
    _git(["add", path], cwd=upstream, env=env)
    _git(["commit", "-m", f"C1 add {path}"], cwd=upstream, env=env)
    return _git(["rev-parse", "HEAD"], cwd=upstream, env=env).stdout.strip()


def _primary_sync_transaction_manifests(primary: Path) -> list[Path]:
    raw_common = _git(["rev-parse", "--git-common-dir"], cwd=primary).stdout.strip()
    common_dir = Path(raw_common)
    if not common_dir.is_absolute():
        common_dir = primary / common_dir
    return sorted(
        common_dir.resolve().glob(
            "rcx_primary_worktree_sync_transactions/*/manifest.json"
        )
    )


def _primary_sync_transaction_root(primary: Path) -> Path:
    raw_common = _git(["rev-parse", "--git-common-dir"], cwd=primary).stdout.strip()
    common_dir = Path(raw_common)
    if not common_dir.is_absolute():
        common_dir = primary / common_dir
    return common_dir.resolve() / "rcx_primary_worktree_sync_transactions"


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


def test_sync_primary_ffs_and_restores_staged_and_unstaged_tracked_wip(tmp_path):
    """Clean-ancestor primary with tracked dirty WIP (staged + unstaged) is
    stash-isolated, fast-forwarded to origin/dev, then the WIP is restored in
    place -- the never-behind-dev stash-preserve path. Untracked founder files
    ride through the ff untouched and never enter the tracked-WIP stash."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-b"], cwd=primary, env=env)
    # Staged + unstaged tracked WIP on seed.txt (status MM).
    (primary / "seed.txt").write_text("staged founder WIP\n")
    _git(["add", "seed.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged founder WIP\n")
    # Untracked scratch must remain in the worktree and must NOT enter the
    # tracked-WIP stash.
    (primary / "scratch.txt").write_text("untracked scratch\n")
    # origin/dev advances with a NON-overlapping file, so the ff range does not
    # touch the tracked WIP path (seed.txt) -> restore is conflict-free.
    c1_sha = _advance_origin_dev_add_file(upstream, env)

    lines: list[str] = []
    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=lines.append,
    )

    # Fast-forwarded to origin/dev tip; still on the SAME feature branch.
    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["reason"] is None, outcome
    assert outcome["old_sha"] == c0_sha, outcome
    assert outcome["new_sha"] == c1_sha, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "jabramsja/feat-b"
    assert (primary / "origin_only.txt").read_text() == "origin-only\n"
    # Tracked WIP preserved: BOTH the staged (index) and unstaged (worktree) deltas.
    assert outcome["tracked_wip_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_overlap_paths"] == [], outcome
    assert outcome["tracked_wip_restored"] is True, outcome
    assert outcome["tracked_wip_left_stashed"] is False, outcome
    assert outcome["tracked_wip_restore_error"] is None, outcome
    assert _git(["show", ":seed.txt"], cwd=primary).stdout == "staged founder WIP\n"
    assert (primary / "seed.txt").read_text() == "unstaged founder WIP\n"
    status_lines = set(_git(["status", "--short"], cwd=primary).stdout.splitlines())
    assert "MM seed.txt" in status_lines, status_lines
    # Untracked founder file untouched and never stashed.
    assert (primary / "scratch.txt").read_text() == "untracked scratch\n"
    assert "?? scratch.txt" in status_lines, status_lines
    # The executor-owned tracked-WIP stash was popped, not left dangling.
    assert "commit_executor:primary_ffsync_transaction" not in _git(
        ["stash", "list"], cwd=primary
    ).stdout
    assert c1_sha != c0_sha


def test_sync_primary_stash_preserves_tracked_wip_and_clears_behind_dev(tmp_path):
    """Work-item-4 regression (never-behind-dev-stash-preserve-2026-07-04): a
    PRIMARY that is a clean ANCESTOR of origin/dev with tracked dirty WIP is
    stash-preserved and fast-forwarded, the tracked WIP is restored, a stale
    behind_dev signal is CLEARED, and untracked + ignored founder files are left
    completely untouched (never stashed, never overwritten). This is the
    deterministic post-merge sync the founder requires -- orchestrator-agnostic,
    IN THE PIPELINE (commit_executor Step 15b)."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-preserve"], cwd=primary, env=env)
    # Tracked dirty WIP on seed.txt (unstaged edit -> tracked-dirty).
    (primary / "seed.txt").write_text("founder tracked WIP\n")
    # Untracked founder file (the normal primary state: handoffs, deferred notes).
    (primary / "HANDOFF_FOR_CODEX.md").write_text("handoff untracked\n")
    # Ignored founder WIP (local-only via .git/info/exclude) -- never touched.
    (primary / ".git" / "info" / "exclude").write_text(
        "ignored_wip.txt\n", encoding="utf-8"
    )
    (primary / "ignored_wip.txt").write_text("local ignored WIP\n", encoding="utf-8")
    # Stale behind_dev signal from a prior behind wave -- must be cleared on sync.
    stale = primary / ".agent_bus" / "behind_dev.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"reason": "dirty_primary_worktree"}\n', encoding="utf-8")
    # origin/dev advances with a NON-overlapping file (pure fast-forward possible).
    c1_sha = _advance_origin_dev_add_file(upstream, env)

    lines: list[str] = []
    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=lines.append,
    )

    # HEAD fast-forwarded to origin/dev; observability recorded.
    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["reason"] is None, outcome
    assert Path(outcome["primary"]).resolve() == primary.resolve(), outcome
    assert outcome["old_sha"] == c0_sha, outcome
    assert outcome["new_sha"] == c1_sha, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "jabramsja/feat-preserve"
    assert (primary / "origin_only.txt").read_text() == "origin-only\n"
    # Tracked WIP preserved post-restore.
    assert outcome["tracked_wip_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_restored"] is True, outcome
    assert outcome["tracked_wip_left_stashed"] is False, outcome
    assert outcome["tracked_wip_restore_error"] is None, outcome
    assert (primary / "seed.txt").read_text() == "founder tracked WIP\n"
    status_lines = set(_git(["status", "--short"], cwd=primary).stdout.splitlines())
    assert " M seed.txt" in status_lines, status_lines
    # Untracked + ignored founder files untouched; never stashed.
    assert (primary / "HANDOFF_FOR_CODEX.md").read_text() == "handoff untracked\n"
    assert "?? HANDOFF_FOR_CODEX.md" in status_lines, status_lines
    assert (primary / "ignored_wip.txt").read_text() == "local ignored WIP\n"
    assert "commit_executor:primary_ffsync_transaction" not in _git(
        ["stash", "list"], cwd=primary
    ).stdout
    # behind_dev signal CLEARED (primary is current after the ff).
    assert outcome["behind_dev_signal_cleared"] is True, outcome
    assert not stale.exists()
    assert c1_sha != c0_sha


def test_sync_primary_dirty_overlap_fast_forwards_and_durably_holds_wip(tmp_path):
    """Staged/unstaged overlap is isolated before ff and retained in HELD."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-overlap"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("staged founder WIP\n")
    _git(["add", "seed.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged founder WIP\n")
    (primary / "scratch.txt").write_text("untracked scratch\n")
    c1_sha = _advance_origin_dev(upstream, env, content="origin seed c1\n")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["reason"] is None, outcome
    assert outcome["dirty_paths"] == ["scratch.txt", "seed.txt"], outcome
    assert outcome["tracked_wip_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_overlap_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_held_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_stash_marker"], outcome
    assert outcome["tracked_wip_stash_ref"], outcome
    assert outcome["tracked_wip_stash_oid"], outcome
    assert outcome["tracked_wip_restored"] is False, outcome
    assert outcome["tracked_wip_left_stashed"] is True, outcome
    assert outcome["tracked_wip_restore_error"] is None, outcome
    assert outcome["primary_sync_transaction_state"] == "HELD", outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    # Changed base content occupies the path; overlap is never auto-applied.
    assert _git(["show", ":seed.txt"], cwd=primary).stdout == "origin seed c1\n"
    assert (primary / "seed.txt").read_text() == "origin seed c1\n"
    assert (primary / "scratch.txt").read_text() == "untracked scratch\n"
    status_lines = set(_git(["status", "--short"], cwd=primary).stdout.splitlines())
    assert not any(line.endswith(" seed.txt") for line in status_lines)
    assert "?? scratch.txt" in status_lines
    assert c1_sha != c0_sha
    # The exact staged and unstaged states remain independently readable from
    # the predeclared stash object, and the common-dir journal is HELD.
    stash_oid = outcome["tracked_wip_stash_oid"]
    assert _git(["show", f"{stash_oid}^2:seed.txt"], cwd=primary).stdout == (
        "staged founder WIP\n"
    )
    assert _git(["show", f"{stash_oid}:seed.txt"], cwd=primary).stdout == (
        "unstaged founder WIP\n"
    )
    manifest_path = Path(outcome["primary_sync_transaction_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["state"] == "HELD", manifest
    assert manifest["held_tracked_paths"] == ["seed.txt"], manifest
    assert [entry["state"] for entry in manifest["state_history"]] == [
        "PREPARED",
        "STASHED",
        "ISOLATED",
        "FF_APPLIED",
        "HELD",
    ]
    assert manifest["worktree_identity"]["path"] == str(primary.resolve())
    assert manifest_path in _primary_sync_transaction_manifests(primary)
    assert not (primary / ".agent_bus" / "behind_dev.json").exists()


def test_sync_primary_restores_nonoverlap_while_overlap_remains_held(tmp_path):
    """One stash may retain overlap while exact non-overlap state is restored."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    (upstream / "other.txt").write_text("base other\n")
    _git(["add", "other.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "base adds other"], cwd=upstream, env=env)
    _git(["fetch", "origin", "dev"], cwd=primary)
    _git(["merge", "--ff-only", "origin/dev"], cwd=primary)
    _git(["checkout", "-b", "jabramsja/overlap-plus-restore"], cwd=primary)

    (primary / "seed.txt").write_text("staged overlap\n")
    (primary / "other.txt").write_text("staged nonoverlap\n")
    _git(["add", "seed.txt", "other.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged overlap\n")
    (primary / "other.txt").write_text("unstaged nonoverlap\n")
    c1_sha = _advance_origin_dev(upstream, env, content="origin overlap\n")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["new_sha"] == c1_sha, outcome
    assert outcome["tracked_wip_overlap_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_held_paths"] == ["seed.txt"], outcome
    assert outcome["tracked_wip_restored"] is True, outcome
    assert (primary / "seed.txt").read_text() == "origin overlap\n"
    assert _git(["show", ":other.txt"], cwd=primary).stdout == "staged nonoverlap\n"
    assert (primary / "other.txt").read_text() == "unstaged nonoverlap\n"
    manifest = json.loads(
        Path(outcome["primary_sync_transaction_path"]).read_text(encoding="utf-8")
    )
    assert manifest["state"] == "HELD", manifest
    assert manifest["restored_tracked_paths"] == ["other.txt"], manifest
    assert manifest["held_tracked_paths"] == ["seed.txt"], manifest


def test_sync_primary_skips_already_current_before_stashing_tracked_wip(tmp_path):
    """Tracked WIP on an already-current primary is not isolated in a stash."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-current"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("founder work in progress\n")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "already current" in (outcome["reason"] or ""), outcome
    assert outcome["tracked_wip_paths"] == [], outcome
    assert outcome["tracked_wip_stash_ref"] is None, outcome
    assert _git(["stash", "list"], cwd=primary).stdout.strip() == ""
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha
    assert (primary / "seed.txt").read_text() == "founder work in progress\n"


def test_sync_primary_ffs_over_noncolliding_untracked_files(tmp_path):
    """FIX-NEVERBEHIND-FF-UNTRACKED (hermetic ff-SUCCESS): a clean-ancestor
    primary that is behind origin/dev and holds ONLY non-colliding untracked
    founder scratch (handoffs, deferred notes) is FAST-FORWARDED, not skipped.
    `git merge --ff-only --no-overwrite-ignore` leaves non-colliding untracked
    files untouched, so never-behind is achieved WITHOUT clobbering founder WIP.

    This SUPERSEDES the old untracked-PRESENCE skip test
    (`test_sync_primary_writes_behind_dev_with_untracked_files_present`), whose
    non-colliding origin advance now fast-forwards under the changed behavior."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-untracked"], cwd=primary, env=env)
    # The normal founder-primary state: untracked scratch (handoffs, deferred
    # notes). origin/dev advances on seed.txt ONLY -> no collision with these.
    (primary / "HANDOFF_FOR_CODEX.md").write_text("handoff")
    (primary / "scratch_deferred_note.md").write_text("deferred finding")
    c1_sha = _advance_origin_dev(upstream, env)
    assert c1_sha != c0_sha

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    # Fast-forwarded to origin/dev tip (never-behind), still on the feature branch.
    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["reason"] is None, outcome
    assert outcome["new_sha"] == c1_sha, outcome
    # The untracked files WERE seen as dirty, but the ff proceeded anyway.
    assert outcome["dirty_paths"] == [
        "HANDOFF_FOR_CODEX.md",
        "scratch_deferred_note.md",
    ], outcome
    assert outcome["tracked_wip_paths"] == [], outcome
    primary_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    assert primary_head == c1_sha, outcome
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "jabramsja/feat-untracked"
    # Post-sync the primary is NOT behind origin/dev (behind_count == 0).
    behind = _git(
        ["rev-list", "--count", "HEAD..origin/dev"], cwd=primary
    ).stdout.strip()
    assert behind == "0", behind
    # Non-colliding untracked founder scratch left BYTE-IDENTICAL and still untracked.
    assert (primary / "HANDOFF_FOR_CODEX.md").read_text() == "handoff"
    assert (primary / "scratch_deferred_note.md").read_text() == "deferred finding"
    status = _git(["status", "--short"], cwd=primary).stdout
    assert "?? HANDOFF_FOR_CODEX.md" in status, status
    assert "?? scratch_deferred_note.md" in status, status
    # never-behind achieved WITHOUT writing a behind_dev skip signal.
    assert outcome["behind_dev_signal_written"] is False, outcome
    assert not (primary / ".agent_bus" / "behind_dev.json").exists(), outcome


def test_sync_primary_moves_nonignored_collision_and_holds_exact_backup(tmp_path):
    """An exact non-ignored collision moves to its predeclared durable backup."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-untracked-collide"], cwd=primary, env=env)
    # Untracked founder WIP at a path origin/dev is about to ADD as a tracked file.
    (primary / "founder-bytes.txt").write_text("local untracked WIP")
    (primary / "collide.txt").symlink_to("founder-bytes.txt")
    # A second, non-colliding untracked file must ALSO survive the safe skip.
    (primary / "keep.txt").write_text("keep me")
    # origin/dev advances by ADDING collide.txt as a TRACKED file -> real collision.
    c1_sha = _advance_origin_dev_add_file(
        upstream, env, path="collide.txt", content="origin tracked content\n"
    )
    assert c1_sha != c0_sha

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["primary_sync_transaction_state"] == "HELD", outcome
    assert outcome["untracked_collision_paths"] == ["collide.txt"], outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha, outcome
    # Origin's tracked bytes now occupy the source path; founder bytes are held
    # byte-identically at the exact backup declared before the move.
    assert (primary / "collide.txt").read_text() == "origin tracked content\n"
    backup = Path(outcome["untracked_wip_backup_paths"][0])
    assert backup.is_symlink()
    assert os.readlink(backup) == "founder-bytes.txt"
    assert (primary / "founder-bytes.txt").read_text() == "local untracked WIP"
    assert (primary / "keep.txt").read_text() == "keep me", outcome
    manifest = json.loads(
        Path(outcome["primary_sync_transaction_path"]).read_text(encoding="utf-8")
    )
    assert manifest["state"] == "HELD", manifest
    assert manifest["held_untracked_paths"] == ["collide.txt"], manifest
    assert manifest["backups"][0]["backup_path"] == str(backup)
    assert outcome["behind_dev_signal_written"] is False, outcome
    assert not (primary / ".agent_bus" / "behind_dev.json").exists()


def test_sync_primary_dual_classified_path_skips_before_transaction_and_retries(
    tmp_path,
):
    """A staged deletion plus recreated file is preserved without a journal."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    (upstream / "victim.txt").write_text("base victim\n", encoding="utf-8")
    _git(["add", "victim.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "add victim"], cwd=upstream, env=env)
    _git(["fetch", "origin", "dev"], cwd=primary, env=env)
    _git(["merge", "--ff-only", "origin/dev"], cwd=primary, env=env)
    _git(["checkout", "-b", "jabramsja/dual-classified"], cwd=primary, env=env)

    old_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    _git(["rm", "victim.txt"], cwd=primary, env=env)
    founder_bytes = b"recreated founder bytes\x00\n"
    (primary / "victim.txt").write_bytes(founder_bytes)
    (upstream / "victim.txt").write_text("origin changed victim\n", encoding="utf-8")
    _git(["add", "victim.txt"], cwd=upstream, env=env)
    _git(["commit", "-m", "change victim"], cwd=upstream, env=env)
    target_head = _git(["rev-parse", "HEAD"], cwd=upstream).stdout.strip()

    path_status_before = _git(
        ["status", "--short", "--", "victim.txt"], cwd=primary
    ).stdout
    index_delta_before = _git(
        ["diff", "--cached", "--binary", "--", "victim.txt"], cwd=primary
    ).stdout
    stash_before = _git(["stash", "list"], cwd=primary).stdout
    transaction_root = _primary_sync_transaction_root(primary)
    assert path_status_before.splitlines() == ["D  victim.txt", "?? victim.txt"]
    assert not transaction_root.exists()

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert outcome["dual_classified_wip_paths"] == ["victim.txt"], outcome
    assert "dual-classified" in (outcome["reason"] or ""), outcome
    assert "victim.txt" in (outcome["reason"] or ""), outcome
    assert outcome["primary_sync_transaction_path"] is None, outcome
    assert outcome["primary_sync_transaction_state"] is None, outcome
    assert outcome["recovery_hold"] is None, outcome
    assert outcome["behind_dev_signal_written"] is True, outcome
    signal = json.loads(
        (primary / ".agent_bus" / "behind_dev.json").read_text(encoding="utf-8")
    )
    assert signal["reason"] == "dual_classified_primary_wip", signal
    assert signal["dirty_paths"] == ["victim.txt"], signal

    # No transaction boundary was crossed: the exact HEAD, recreated bytes,
    # staged deletion, stash inventory, and journal-directory absence survive.
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == old_head
    assert (primary / "victim.txt").read_bytes() == founder_bytes
    assert _git(
        ["status", "--short", "--", "victim.txt"], cwd=primary
    ).stdout == path_status_before
    assert _git(
        ["diff", "--cached", "--binary", "--", "victim.txt"], cwd=primary
    ).stdout == index_delta_before
    assert _git(["stash", "list"], cwd=primary).stdout == stash_before
    assert not transaction_root.exists()

    # Once the user resolves the unsupported index/worktree combination, the
    # same path is retryable through the normal clean fast-forward path.
    _git(
        [
            "restore",
            "--source=HEAD",
            "--staged",
            "--worktree",
            "--",
            "victim.txt",
        ],
        cwd=primary,
    )
    retry = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    assert retry["synced"] is True, retry
    assert retry["primary_sync_transaction_path"] is None, retry
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == target_head
    assert (primary / "victim.txt").read_text(encoding="utf-8") == (
        "origin changed victim\n"
    )
    assert not (primary / ".agent_bus" / "behind_dev.json").exists()
    assert not transaction_root.exists()


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


def test_sync_primary_writes_behind_dev_signal_on_divergent_behind_skip(tmp_path):
    """Divergent and behind primary branches get a durable behind_dev signal."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-behind-div"], cwd=primary, env=env)
    (primary / "local.txt").write_text("divergent local work\n")
    _git(["add", "local.txt"], cwd=primary, env=env)
    _git(["commit", "-m", "local-only"], cwd=primary, env=env)
    divergent_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    linked = tmp_path / "linked_lane"
    _git(["worktree", "add", "-b", "lane-y", str(linked), "HEAD"], cwd=primary)
    c1_sha = _advance_origin_dev_add_file(upstream, env)

    lines: list[str] = []
    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=linked, base_branch="dev", log=lines.append,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "ancestor" in (outcome["reason"] or ""), outcome
    assert outcome["behind_count"] == 1, outcome
    assert outcome["ahead_count"] == 1, outcome
    assert outcome["behind_dev_signal_written"] is True, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == divergent_head
    assert c1_sha != divergent_head

    primary_signal = primary / ".agent_bus" / "behind_dev.json"
    lane_signal = linked / ".agent_bus" / "behind_dev.json"
    assert primary_signal.exists(), outcome
    assert not lane_signal.exists(), "signal must not land on the transient lane"
    signal = json.loads(primary_signal.read_text(encoding="utf-8"))
    assert Path(signal["primary"]).resolve() == primary.resolve()
    assert signal["base_ref"] == "origin/dev"
    assert signal["behind_count"] == 1
    assert signal["ahead_count"] == 1
    assert signal["reason"] == "divergent_local_commits"
    assert isinstance(signal["timestamp"], str) and signal["timestamp"]
    assert any("behind_dev" in line for line in lines), lines


def test_sync_primary_does_not_write_behind_dev_for_ahead_only_branch(tmp_path):
    """Ahead-only feature work is not behind dev and clears stale behind_dev."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-ahead-only"], cwd=primary, env=env)
    (primary / "local.txt").write_text("local work\n")
    _git(["add", "local.txt"], cwd=primary, env=env)
    _git(["commit", "-m", "local-only"], cwd=primary, env=env)
    local_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    stale = primary / ".agent_bus" / "behind_dev.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"reason": "stale"}\n', encoding="utf-8")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "ancestor" in (outcome["reason"] or ""), outcome
    assert outcome["behind_count"] == 0, outcome
    assert outcome["ahead_count"] == 1, outcome
    assert outcome["behind_dev_signal_written"] is False, outcome
    assert outcome["behind_dev_signal_cleared"] is True, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == local_head
    assert not stale.exists()
    assert c0_sha != local_head


def test_sync_primary_clears_behind_dev_signal_on_clean_ff(tmp_path):
    """A later clean ancestor fast-forward clears stale behind_dev."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-clearff"], cwd=primary, env=env)
    stale = primary / ".agent_bus" / "behind_dev.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"reason": "dirty_primary_worktree"}\n', encoding="utf-8")
    c1_sha = _advance_origin_dev(upstream, env)

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is True, outcome
    assert outcome["skipped"] is False, outcome
    assert outcome["behind_dev_signal_cleared"] is True, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    assert not stale.exists()
    assert c1_sha != c0_sha


def test_sync_primary_clears_stale_signal_when_already_current(tmp_path):
    """Already-current primary branches clear stale behind_dev without stashing."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-current-clear"], cwd=primary, env=env)
    stale = primary / ".agent_bus" / "behind_dev.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text('{"reason": "dirty_primary_worktree"}\n', encoding="utf-8")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert "already current" in (outcome["reason"] or ""), outcome
    assert outcome["behind_dev_signal_cleared"] is True, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha
    assert not stale.exists()


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
    (repo / "seed.txt").write_text("dirty before failed fetch\n")
    outcome_no_origin = commit_mod.sync_primary_worktree_to_base(
        repo_root=repo, base_branch="dev", log=_noop_log,
    )
    assert outcome_no_origin["synced"] is False
    assert outcome_no_origin["skipped"] is True
    assert "fetch origin dev failed" in (outcome_no_origin["reason"] or "")
    assert outcome_no_origin["tracked_wip_paths"] == []
    assert _git(["stash", "list"], cwd=repo).stdout.strip() == ""
    # Nothing destroyed — HEAD intact on the feature branch.
    assert _git(["rev-parse", "HEAD"], cwd=repo).stdout.strip() == feat_head
    assert (repo / "seed.txt").read_text() == "dirty before failed fetch\n"


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
    assert "locally ignored collision refused" in (outcome["reason"] or ""), outcome
    assert outcome["ignored_collision_paths"] == ["ignored.txt"], outcome
    assert outcome["primary_sync_transaction_path"] is None, outcome
    # Founder's ignored WIP is PRESERVED, not clobbered by origin's content.
    assert (primary / "ignored.txt").read_text() == "local ignored WIP", outcome
    # HEAD unchanged — still at C0 on the feature branch (no fast-forward applied).
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha
    assert _git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd=primary
    ).stdout.strip() == "jabramsja/feat-ign"


def test_sync_primary_ff_failure_restores_tracked_and_moved_collision(
    tmp_path, monkeypatch
):
    """A failed ff restores exact index/worktree and collision source state."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/feat-failure-restore"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("staged failure WIP\n")
    os.chmod(primary / "seed.txt", 0o755)
    _git(["add", "seed.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged failure WIP\n")
    (primary / "collide.txt").write_bytes(b"founder\x00collision\n")
    _advance_origin_dev_add_file(
        upstream, env, path="collide.txt", content="origin collision\n"
    )

    real_run = subprocess.run

    def _fail_only_ff(cmd, *args, **kwargs):
        if list(cmd[:2]) == ["git", "merge"]:
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="simulated ff failure"
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fail_only_ff)
    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )

    assert outcome["synced"] is False, outcome
    assert outcome["skipped"] is True, outcome
    assert outcome["primary_sync_transaction_state"] == "RECOVERED", outcome
    assert outcome["tracked_wip_restored"] is True, outcome
    assert outcome["tracked_wip_left_stashed"] is False, outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c0_sha
    assert _git(["show", ":seed.txt"], cwd=primary).stdout == "staged failure WIP\n"
    assert (primary / "seed.txt").read_text() == "unstaged failure WIP\n"
    assert stat.S_IMODE((primary / "seed.txt").stat().st_mode) == 0o755
    assert (primary / "collide.txt").read_bytes() == b"founder\x00collision\n"
    assert not Path(outcome["untracked_wip_backup_paths"][0]).exists()
    assert "commit_executor:primary_ffsync_transaction" not in _git(
        ["stash", "list"], cwd=primary
    ).stdout
    manifest = json.loads(
        Path(outcome["primary_sync_transaction_path"]).read_text(encoding="utf-8")
    )
    assert manifest["state"] == "RECOVERED", manifest
    assert manifest["restored_tracked_paths"] == ["seed.txt"], manifest
    assert manifest["restored_untracked_paths"] == ["collide.txt"], manifest


class _SimulatedPrimarySyncCrash(BaseException):
    pass


@pytest.mark.parametrize(
    "checkpoint_name",
    ["after_prepared", "after_stash_before_publish"],
)
def test_sync_primary_restart_recovers_pre_ff_tracked_checkpoints_idempotently(
    tmp_path, checkpoint_name
):
    """PREPARED and stash-before-publication crashes remain discoverable."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", f"jabramsja/restart-{checkpoint_name}"], cwd=primary)
    (primary / "seed.txt").write_text("staged restart WIP\n")
    _git(["add", "seed.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged restart WIP\n")
    c1_sha = _advance_origin_dev(upstream, env, content="origin changed seed\n")

    def _crash(name, _manifest):
        if name == checkpoint_name:
            raise _SimulatedPrimarySyncCrash(name)

    with pytest.raises(_SimulatedPrimarySyncCrash):
        commit_mod.sync_primary_worktree_to_base(
            repo_root=primary,
            base_branch="dev",
            log=_noop_log,
            checkpoint=_crash,
        )
    first_manifest = _primary_sync_transaction_manifests(primary)[0]
    first_state = json.loads(first_manifest.read_text(encoding="utf-8"))["state"]
    assert first_state == "PREPARED", first_state

    restarted = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    assert restarted["synced"] is True, restarted
    assert restarted["primary_sync_transaction_state"] == "HELD", restarted
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    first_after = json.loads(first_manifest.read_text(encoding="utf-8"))
    assert first_after["state"] == "RECOVERED", first_after
    assert any(
        item["manifest_path"] == str(first_manifest)
        and item["state"] == "RECOVERED"
        for item in restarted["recovered_transactions"]
    )

    manifest_count = len(_primary_sync_transaction_manifests(primary))
    retry = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    assert retry["skipped"] is True and "already current" in retry["reason"], retry
    assert len(_primary_sync_transaction_manifests(primary)) == manifest_count


def test_sync_primary_restart_recovers_move_before_publication(tmp_path):
    """A moved collision is restored from its PREPARED journal before retry."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/restart-move"], cwd=primary)
    (primary / "collide.txt").write_bytes(b"move-window\x00bytes")
    c1_sha = _advance_origin_dev_add_file(
        upstream, env, path="collide.txt", content="origin after move\n"
    )

    def _crash(name, _manifest):
        if name == "after_move_before_publish":
            raise _SimulatedPrimarySyncCrash(name)

    with pytest.raises(_SimulatedPrimarySyncCrash):
        commit_mod.sync_primary_worktree_to_base(
            repo_root=primary,
            base_branch="dev",
            log=_noop_log,
            checkpoint=_crash,
        )
    first_manifest = _primary_sync_transaction_manifests(primary)[0]
    prepared = json.loads(first_manifest.read_text(encoding="utf-8"))
    assert prepared["state"] == "PREPARED", prepared
    assert not (primary / "collide.txt").exists()
    assert Path(prepared["backups"][0]["backup_path"]).read_bytes() == (
        b"move-window\x00bytes"
    )

    restarted = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    assert restarted["synced"] is True, restarted
    assert restarted["primary_sync_transaction_state"] == "HELD", restarted
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha
    assert json.loads(first_manifest.read_text(encoding="utf-8"))["state"] == (
        "RECOVERED"
    )
    held_backup = Path(restarted["untracked_wip_backup_paths"][0])
    assert held_backup.read_bytes() == b"move-window\x00bytes"


def test_sync_primary_restart_finalizes_after_ff_before_publication(tmp_path):
    """ISOLATED plus target HEAD is enough to publish the intended HELD state."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/restart-after-ff"], cwd=primary)
    (primary / "seed.txt").write_text("staged after-ff WIP\n")
    _git(["add", "seed.txt"], cwd=primary, env=env)
    (primary / "seed.txt").write_text("unstaged after-ff WIP\n")
    c1_sha = _advance_origin_dev(upstream, env, content="origin after ff\n")

    def _crash(name, _manifest):
        if name == "after_fast_forward_before_publish":
            raise _SimulatedPrimarySyncCrash(name)

    with pytest.raises(_SimulatedPrimarySyncCrash):
        commit_mod.sync_primary_worktree_to_base(
            repo_root=primary,
            base_branch="dev",
            log=_noop_log,
            checkpoint=_crash,
        )
    manifest_path = _primary_sync_transaction_manifests(primary)[0]
    interrupted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert interrupted["state"] == "ISOLATED", interrupted
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == c1_sha

    restarted = commit_mod.sync_primary_worktree_to_base(
        repo_root=primary, base_branch="dev", log=_noop_log,
    )
    assert restarted["skipped"] is True, restarted
    assert "already current" in restarted["reason"], restarted
    finalized = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert finalized["state"] == "HELD", finalized
    assert finalized["held_tracked_paths"] == ["seed.txt"], finalized
    assert restarted["recovered_transactions"] == [
        {
            "manifest_path": str(manifest_path),
            "state": "HELD",
            "tracked_restored_paths": [],
            "tracked_held_paths": ["seed.txt"],
            "untracked_held_paths": [],
            "stash_ref": "stash@{0}",
            "stash_oid": finalized["stash_oid"],
        }
    ]


def test_primary_sync_journal_survives_candidate_worktree_removal(tmp_path):
    """The sole recovery authority lives in common-dir, never the caller lane."""
    upstream, primary, _c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/journal-survival"], cwd=primary)
    linked = tmp_path / "candidate_lane"
    _git(["worktree", "add", "-b", "candidate", str(linked), "HEAD"], cwd=primary)
    (primary / "seed.txt").write_text("held after candidate removal\n")
    _advance_origin_dev(upstream, env, content="origin journal survival\n")

    outcome = commit_mod.sync_primary_worktree_to_base(
        repo_root=linked, base_branch="dev", log=_noop_log,
    )
    manifest_path = Path(outcome["primary_sync_transaction_path"])
    assert outcome["primary_sync_transaction_state"] == "HELD", outcome
    assert manifest_path.is_file()
    assert linked.resolve() not in manifest_path.parents

    _git(["worktree", "remove", "--force", str(linked)], cwd=primary)
    assert not linked.exists()
    assert manifest_path.is_file()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["state"] == "HELD"


def test_terminal_action_refetches_after_diagnostic_and_rejects_dev_advance(
    tmp_path,
):
    """A diagnostic observation cannot authorize action after dev advances."""
    upstream, primary, c0_sha, env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/terminal-target"], cwd=primary)
    identity = commit_mod.bind_terminal_target_identity(primary, base_branch="dev")
    assert identity["bound"] is True, identity
    assert identity["expected_head"] == c0_sha

    routing_observation = commit_mod.observe_terminal_mutation_readiness(
        primary, identity, log=_noop_log,
    )
    assert routing_observation["decision"] == "OBSERVED_READY", routing_observation
    assert routing_observation["authority"] == (
        "diagnostic_only_not_terminal_authority"
    ), routing_observation
    assert routing_observation["mutation_authorized"] is False, routing_observation
    assert routing_observation["reusable"] is False, routing_observation
    assert routing_observation["fresh_fetch"] is True, routing_observation
    assert routing_observation["behind_count"] == 0, routing_observation

    c1_sha = _advance_origin_dev_add_file(upstream, env)
    callback_calls: list[str] = []

    def _terminal_action():
        callback_calls.append("called")
        return {"status": "done"}

    execution_boundary = commit_mod.execute_terminal_mutation_once(
        primary,
        identity,
        terminal_action=_terminal_action,
        log=_noop_log,
    )
    assert execution_boundary["decision"] == "HOLD", execution_boundary
    assert execution_boundary["fresh_fetch"] is True, execution_boundary
    assert execution_boundary["behind_count"] == 1, execution_boundary
    assert execution_boundary["fetched_base_sha"] == c1_sha, execution_boundary
    assert "behind origin/dev by 1" in execution_boundary["reason"]
    assert execution_boundary["action_invoked"] is False, execution_boundary
    assert callback_calls == []

    # Retry after resolving the behind state uses a fresh identity and invokes
    # the callback once total; the earlier diagnostic/HOLD results authorize
    # nothing and cannot be replayed.
    _git(["merge", "--ff-only", "origin/dev"], cwd=primary)
    refreshed_identity = commit_mod.bind_terminal_target_identity(
        primary, base_branch="dev"
    )
    refreshed = commit_mod.execute_terminal_mutation_once(
        primary,
        refreshed_identity,
        terminal_action=_terminal_action,
        log=_noop_log,
    )
    assert refreshed["decision"] == "ACTION_COMPLETED", refreshed
    assert refreshed["behind_count"] == 0, refreshed
    assert refreshed["action_invoked"] is True, refreshed
    assert refreshed["action_succeeded"] is True, refreshed
    assert refreshed["action_outcome"] == {"status": "done"}, refreshed
    assert refreshed["authority"] == (
        "action_outcome_only_not_terminal_authority"
    ), refreshed
    assert refreshed["mutation_authorized"] is False, refreshed
    assert refreshed["reusable"] is False, refreshed
    assert callback_calls == ["called"]


def test_terminal_action_holds_common_dir_lock_through_callback(tmp_path):
    """The lock covers callback entry and consumed authority cannot replay."""
    _upstream, primary, _c0_sha, _env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/terminal-lock"], cwd=primary)
    identity = commit_mod.bind_terminal_target_identity(primary, base_branch="dev")
    replay_identity = json.loads(json.dumps(identity))
    common_dir = Path(identity["common_dir_identity"]["path"])
    lock_path = common_dir / "rcx_primary_worktree_sync.lock"
    callback_calls: list[str] = []

    def _terminal_action():
        callback_calls.append("called")
        with open(lock_path, "a", encoding="utf-8") as competitor:
            with pytest.raises(OSError):
                fcntl.flock(
                    competitor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
        return "locked-action-result"

    outcome = commit_mod.execute_terminal_mutation_once(
        primary,
        identity,
        terminal_action=_terminal_action,
        log=_noop_log,
    )

    assert outcome["decision"] == "ACTION_COMPLETED", outcome
    assert outcome["action_outcome"] == "locked-action-result", outcome
    assert outcome["authority_consumed"] is True, outcome
    assert callback_calls == ["called"]
    attempt_path = Path(outcome["authority_record_path"])
    assert attempt_path.parent.parent == common_dir
    attempt_record = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt_record["operation_id"] == identity["operation_id"]
    assert attempt_record["state"] == "AUTHORITY_CONSUMED_OUTCOME_UNKNOWN"
    # The public result is returned only after the boundary releases the lock.
    with open(lock_path, "a", encoding="utf-8") as after_return:
        fcntl.flock(after_return.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(after_return.fileno(), fcntl.LOCK_UN)

    replayed = commit_mod.execute_terminal_mutation_once(
        primary,
        replay_identity,
        terminal_action=_terminal_action,
        log=_noop_log,
    )
    assert replayed["decision"] == "HOLD", replayed
    assert replayed["action_invoked"] is False, replayed
    assert replayed["action_succeeded"] is None, replayed
    assert replayed["action_outcome"] is None, replayed
    assert replayed["action_error"] is None, replayed
    assert replayed["authority_consumed"] is False, replayed
    assert "already attempted" in replayed["reason"], replayed
    assert callback_calls == ["called"]


def test_terminal_action_stale_identity_and_callback_failure_do_not_invoke_twice(
    tmp_path,
):
    """Stale identity invokes zero times; callback failure is never retried."""
    _upstream, primary, _c0_sha, _env = _init_origin_and_primary(tmp_path)
    _git(["checkout", "-b", "jabramsja/terminal-once"], cwd=primary)
    stale_identity = commit_mod.bind_terminal_target_identity(
        primary, base_branch="dev"
    )
    _git(["checkout", "-b", "jabramsja/terminal-once-drift"], cwd=primary)

    callback_calls: list[str] = []

    def _failing_action():
        callback_calls.append("called")
        raise RuntimeError("terminal action failed")

    stale = commit_mod.execute_terminal_mutation_once(
        primary,
        stale_identity,
        terminal_action=_failing_action,
        log=_noop_log,
    )
    assert stale["decision"] == "HOLD", stale
    assert "branch mismatch" in stale["reason"], stale
    assert stale["action_invoked"] is False, stale
    assert callback_calls == []

    refreshed_identity = commit_mod.bind_terminal_target_identity(
        primary, base_branch="dev"
    )
    retry_identity = json.loads(json.dumps(refreshed_identity))
    failed = commit_mod.execute_terminal_mutation_once(
        primary,
        refreshed_identity,
        terminal_action=_failing_action,
        log=_noop_log,
    )
    assert failed["decision"] == "ACTION_FAILED", failed
    assert failed["action_invoked"] is True, failed
    assert failed["action_succeeded"] is False, failed
    assert failed["action_outcome"] is None, failed
    assert failed["action_error"] == "RuntimeError: terminal action failed", failed
    assert failed["authority_consumed"] is True, failed
    assert callback_calls == ["called"]
    attempt_path = Path(failed["authority_record_path"])
    attempt_record = json.loads(attempt_path.read_text(encoding="utf-8"))
    assert attempt_record["operation_id"] == refreshed_identity["operation_id"]
    assert attempt_record["state"] == "AUTHORITY_CONSUMED_OUTCOME_UNKNOWN"

    retried = commit_mod.execute_terminal_mutation_once(
        primary,
        retry_identity,
        terminal_action=_failing_action,
        log=_noop_log,
    )
    assert retried["decision"] == "HOLD", retried
    assert retried["action_invoked"] is False, retried
    assert retried["action_succeeded"] is None, retried
    assert retried["action_outcome"] is None, retried
    assert retried["action_error"] is None, retried
    assert retried["authority_consumed"] is False, retried
    assert "already attempted" in retried["reason"], retried
    assert callback_calls == ["called"]
    lock_path = (
        Path(refreshed_identity["common_dir_identity"]["path"])
        / "rcx_primary_worktree_sync.lock"
    )
    with open(lock_path, "a", encoding="utf-8") as after_failure:
        fcntl.flock(after_failure.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(after_failure.fileno(), fcntl.LOCK_UN)


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


def _growth_cap_source(
    baseline: int,
    cap: int,
    cap_comment: str,
    *,
    tool_baseline: int | None = None,
    tool_cap: int | None = None,
    tool_comment: str = "",
) -> str:
    """Minimal fixture mirroring the BASELINE/CAP surface the auto-bump reads."""
    source = (
        '"""Growth cap fixture (mirrors mu/tests/docs/test_growth_caps.py)."""\n'
        "from __future__ import annotations\n"
        "\n"
        f"BASELINE_TEST_FILES = {baseline}\n"
        f"CAP_TEST_FILES = {cap}{cap_comment}\n"
    )
    if tool_baseline is not None and tool_cap is not None:
        source += (
            f"BASELINE_TOOL_SCRIPTS = {tool_baseline}\n"
            f"CAP_TOOL_SCRIPTS = {tool_cap}{tool_comment}\n"
        )
    return source


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
    existing_tool_scripts: list[str] | None = None,
    cap_comment: str = GROWTH_CAP_SEED_COMMENT,
    tool_baseline: int | None = None,
    tool_cap: int | None = None,
    tool_comment: str = "",
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
    caps.write_text(
        _growth_cap_source(
            baseline,
            cap,
            cap_comment,
            tool_baseline=tool_baseline,
            tool_cap=tool_cap,
            tool_comment=tool_comment,
        ),
        encoding="utf-8",
    )
    for rel in existing_test_files:
        path = upstream / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    for rel in existing_tool_scripts or []:
        path = upstream / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
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


def _stage_new_tool_script(primary: Path, env: dict, relpath: str) -> None:
    path = primary / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    _git(["add", "--", relpath], cwd=primary, env=env)


def _read_growth_cap_values(primary: Path):
    text = (primary / "mu" / "tests" / "docs" / "test_growth_caps.py").read_text()
    baseline = int(re.search(r"BASELINE_TEST_FILES = (\d+)", text).group(1))
    cap = int(re.search(r"CAP_TEST_FILES = (\d+)", text).group(1))
    return text, baseline, cap


def _read_tool_growth_cap_values(primary: Path):
    text = (primary / "mu" / "tests" / "docs" / "test_growth_caps.py").read_text()
    baseline = int(re.search(r"BASELINE_TOOL_SCRIPTS = (\d+)", text).group(1))
    cap = int(re.search(r"CAP_TOOL_SCRIPTS = (\d+)", text).group(1))
    return text, baseline, cap


def _count_disk_test_files(primary: Path) -> int:
    return len(list((primary / "mu" / "tests").rglob("test_*.py")))


def _count_disk_tool_scripts(primary: Path) -> int:
    tools_dir = primary / "mu" / "tools"
    return len(list(tools_dir.rglob("*.py"))) + len(list(tools_dir.rglob("*.sh")))


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


def test_growth_cap_autobump_tool_script_bumps_by_exact_shortfall_with_founder_override(tmp_path):
    """A FOUNDER_OVERRIDE wave that adds a new mu/tools script over
    CAP_TOOL_SCRIPTS gets the same pre-receipt cap-bump handling as test files."""
    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
        tool_baseline=0,
        tool_cap=0,
    )
    _stage_new_tool_script(primary, env, "mu/tools/session/new_switch.sh")
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    assert outcome["bumped"] is True, outcome
    assert outcome["new_tool_scripts"] == ["mu/tools/session/new_switch.sh"], outcome
    assert outcome["cap_bumps"]["CAP_TOOL_SCRIPTS"]["shortfall"] == 1, outcome
    assert outcome["cap_bumps"]["CAP_TOOL_SCRIPTS"]["bump_amount"] == 1, outcome
    text, baseline, cap = _read_tool_growth_cap_values(primary)
    assert cap == 1, text
    assert f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}" in text, text
    assert "new_switch.sh" in text, text
    assert _growth_cap_staged(primary)
    assert _count_disk_tool_scripts(primary) <= baseline + cap, (baseline, cap)
    assert any(
        f"auto-bumped CAP_TOOL_SCRIPTS +1 for FOUNDER_OVERRIDE wave {GROWTH_CAP_WAVE_ID}"
        in m
        for m in lines
    ), lines


def test_growth_cap_autobump_recorded_test_cap_still_bumps_tool_script(tmp_path):
    """A same-wave retry must not let recorded CAP_TEST_FILES provenance hide a
    still-missing CAP_TOOL_SCRIPTS bump in the same growth-cap file."""
    recorded_test_comment = (
        f"  # +1 for test_new_feature.py ({GROWTH_CAP_WAVE_ID} wave, "
        f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID})"
    )
    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=1,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
        cap_comment=recorded_test_comment,
        tool_baseline=0,
        tool_cap=0,
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    _stage_new_tool_script(primary, env, "mu/tools/session/new_switch.sh")
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    assert outcome["bumped"] is True, outcome
    assert outcome["cap_bumps"]["CAP_TEST_FILES"]["reason"] == "already_recorded", outcome
    assert outcome["cap_bumps"]["CAP_TOOL_SCRIPTS"]["reason"] == "bumped", outcome
    test_text, _, test_cap = _read_growth_cap_values(primary)
    assert test_cap == 1, test_text
    tool_text, _, tool_cap = _read_tool_growth_cap_values(primary)
    assert tool_cap == 1, tool_text
    assert "new_switch.sh" in tool_text, tool_text
    assert _growth_cap_staged(primary)
    assert any("CAP_TEST_FILES already records" in m for m in lines), lines
    assert any(
        f"auto-bumped CAP_TOOL_SCRIPTS +1 for FOUNDER_OVERRIDE wave {GROWTH_CAP_WAVE_ID}"
        in m
        for m in lines
    ), lines


def test_growth_cap_autobump_is_idempotent_on_second_run(tmp_path):
    """(d) Idempotency: two uncommitted runs produce one exact staged bump.

    The second run derives the postimage from HEAD and settles it without
    treating mutable same-wave text as committed P0IC3 provenance.
    """
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
    assert out2["retry_settled"] is True, out2
    assert out2["reason"] == "retry_settled", out2

    text, _, cap = _read_growth_cap_values(primary)
    assert cap == 1, text  # bumped once, not twice
    assert text.count(f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}") == 1, text
    assert any("settled retry" in m and "without another increment" in m for m in lines2), lines2


def _raw_growth_cap_repo_state(primary: Path) -> tuple[str, bytes, bytes]:
    return (
        _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip(),
        subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=primary,
            capture_output=True,
            check=True,
        ).stdout,
        subprocess.run(
            ["git", "status", "--porcelain=v1", "-z"],
            cwd=primary,
            capture_output=True,
            check=True,
        ).stdout,
    )


def test_growth_cap_autobump_all_surface_canonical_absence_is_non_mutating(tmp_path):
    """A minimal repo without the target retains the established absent no-op."""
    primary = _init_repo(tmp_path)
    env = _git_env()
    _stage_new_test_file(primary, env, "mu/tests/test_absent_growth_cap_target.py")
    target = primary / commit_mod.GROWTH_CAP_TEST_RELPATH

    assert not _git(
        ["ls-tree", "--name-only", "HEAD", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
        cwd=primary,
    ).stdout.strip()
    assert not _git(
        ["ls-files", "--stage", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
        cwd=primary,
    ).stdout.strip()
    assert not os.path.lexists(target)
    before = _raw_growth_cap_repo_state(primary)

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["retry_settled"] is False, outcome
    assert outcome["reason"] == "growth_cap_file_absent", outcome
    assert outcome["retry_authority_error"] == "", outcome
    assert outcome["commit_generated_governance_paths"] == [], outcome
    assert outcome["new_test_files"] == [], outcome
    assert outcome["new_tool_scripts"] == [], outcome
    assert _raw_growth_cap_repo_state(primary) == before
    assert not os.path.lexists(target)


@pytest.mark.parametrize(
    "target_state",
    ["head_only", "index_only", "worktree_only", "index_and_worktree"],
)
def test_growth_cap_autobump_partial_absence_remains_fail_closed(
    tmp_path,
    target_state,
):
    """Only simultaneous HEAD/index/worktree absence gets the absent no-op."""
    env = _git_env()
    if target_state == "head_only":
        primary, env = _init_growth_cap_repo(
            tmp_path,
            baseline=3,
            cap=0,
            existing_test_files=[
                "mu/tests/test_existing_1.py",
                "mu/tests/test_existing_2.py",
            ],
        )
        _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
        _git(["rm", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary, env=env)
    else:
        primary = _init_repo(tmp_path)
        _stage_new_test_file(primary, env, "mu/tests/test_partial_growth_cap_target.py")
        target = primary / commit_mod.GROWTH_CAP_TEST_RELPATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _growth_cap_source(1, 0, ""),
            encoding="utf-8",
        )
        if target_state in {"index_only", "index_and_worktree"}:
            _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary, env=env)
        if target_state == "index_only":
            target.unlink()

    target = primary / commit_mod.GROWTH_CAP_TEST_RELPATH
    target_existed_before = os.path.lexists(target)
    target_bytes_before = target.read_bytes() if target_existed_before else None
    target_mode_before = (
        stat.S_IMODE(os.lstat(target).st_mode) if target_existed_before else None
    )
    before = _raw_growth_cap_repo_state(primary)

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["retry_settled"] is False, outcome
    assert outcome["reason"] == "retry_authority_error", outcome
    assert outcome["retry_authority_error"], outcome
    assert outcome["commit_generated_governance_paths"] == [], outcome
    assert _raw_growth_cap_repo_state(primary) == before
    assert os.path.lexists(target) is target_existed_before
    if target_existed_before:
        assert target.read_bytes() == target_bytes_before
        assert stat.S_IMODE(os.lstat(target).st_mode) == target_mode_before


def _growth_cap_index_entry(primary: Path) -> tuple[str, str, str]:
    output = _git(
        ["ls-files", "--stage", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
        cwd=primary,
    ).stdout.strip().splitlines()
    assert len(output) == 1, output
    metadata, path = output[0].split("\t", 1)
    mode, oid, stage = metadata.split()
    assert path == commit_mod.GROWTH_CAP_TEST_RELPATH
    return mode, oid, stage


def _growth_cap_head_entry(primary: Path) -> tuple[str, str]:
    output = _git(
        ["ls-tree", "HEAD", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
        cwd=primary,
    ).stdout.strip()
    metadata, path = output.split("\t", 1)
    mode, object_type, oid = metadata.split()
    assert object_type == "blob"
    assert path == commit_mod.GROWTH_CAP_TEST_RELPATH
    return mode, oid


def _replace_growth_cap_index_entry(primary: Path, mode: str, oid: str) -> None:
    _git(
        [
            "update-index",
            "--cacheinfo",
            f"{mode},{oid},{commit_mod.GROWTH_CAP_TEST_RELPATH}",
        ],
        cwd=primary,
    )


@pytest.mark.parametrize(
    "retry_state",
    [
        "worktree_only_postimage",
        "index_only_postimage",
        "unstaged_dirty_postimage",
        "wrong_wave_postimage",
        "forged_same_wave_cap",
        "duplicate_provenance",
        "noncanonical_equivalent_bytes",
        "worktree_mode_drift",
        "head_advanced_without_cap",
        "unmerged_index_stages",
    ],
)
def test_commit_generated_governance_growth_cap_retry_rejects_non_authoritative_state(
    tmp_path,
    retry_state,
):
    """Only the exact HEAD preimage or exact generated postimage may settle."""
    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py",
            "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    first = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )
    assert first["bumped"] is True, first

    growth_path = primary / commit_mod.GROWTH_CAP_TEST_RELPATH
    postimage = growth_path.read_bytes()
    head_preimage = subprocess.run(
        ["git", "show", f"HEAD:{commit_mod.GROWTH_CAP_TEST_RELPATH}"],
        cwd=primary,
        capture_output=True,
        check=True,
    ).stdout
    head_mode, head_oid = _growth_cap_head_entry(primary)
    post_mode, post_oid, post_stage = _growth_cap_index_entry(primary)
    assert post_stage == "0"

    if retry_state == "worktree_only_postimage":
        _replace_growth_cap_index_entry(primary, head_mode, head_oid)
    elif retry_state == "index_only_postimage":
        growth_path.write_bytes(head_preimage)
    elif retry_state == "unstaged_dirty_postimage":
        growth_path.write_bytes(postimage + b"# unstaged retry drift\n")
    elif retry_state == "wrong_wave_postimage":
        wrong_wave = (
            head_preimage.decode("utf-8")
            .replace(
                "CAP_TEST_FILES = 0",
                "CAP_TEST_FILES = 1  # +1 for test_new_feature.py "
                "(other-wave wave, FOUNDER_OVERRIDE:other-wave)",
                1,
            )
            .encode("utf-8")
        )
        growth_path.write_bytes(wrong_wave)
        _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary)
    elif retry_state == "forged_same_wave_cap":
        forged = postimage.replace(b"CAP_TEST_FILES = 1", b"CAP_TEST_FILES = 2", 1)
        growth_path.write_bytes(forged)
        _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary)
    elif retry_state == "duplicate_provenance":
        canonical_token = f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}".encode("utf-8")
        forged = postimage.replace(
            canonical_token,
            canonical_token + b"; " + canonical_token,
            1,
        )
        growth_path.write_bytes(forged)
        _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary)
    elif retry_state == "noncanonical_equivalent_bytes":
        noncanonical = postimage.replace(b"CAP_TEST_FILES = 1", b"CAP_TEST_FILES=1", 1)
        growth_path.write_bytes(noncanonical)
        _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary)
    elif retry_state == "worktree_mode_drift":
        os.chmod(
            growth_path,
            stat.S_IMODE(os.lstat(growth_path).st_mode) | stat.S_IXUSR,
        )
    elif retry_state == "head_advanced_without_cap":
        # Simulate an intervening commit that absorbs the governed addition
        # but not Step 5e's staged cap postimage.  The next derivation now sees
        # no new governed path; it must reject the still-staged target instead
        # of falling through the legacy no-new-files no-op.
        _replace_growth_cap_index_entry(primary, head_mode, head_oid)
        _git(["commit", "-m", "advance HEAD without growth cap"], cwd=primary, env=env)
        growth_path.write_bytes(postimage)
        _git(["add", "--", commit_mod.GROWTH_CAP_TEST_RELPATH], cwd=primary)
    else:
        assert retry_state == "unmerged_index_stages"
        _git(
            ["update-index", "--force-remove", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
            cwd=primary,
        )
        index_info = (
            f"{head_mode} {head_oid} 1\t{commit_mod.GROWTH_CAP_TEST_RELPATH}\n"
            f"{head_mode} {head_oid} 2\t{commit_mod.GROWTH_CAP_TEST_RELPATH}\n"
            f"{post_mode} {post_oid} 3\t{commit_mod.GROWTH_CAP_TEST_RELPATH}\n"
        )
        subprocess.run(
            ["git", "update-index", "--index-info"],
            cwd=primary,
            input=index_info,
            text=True,
            capture_output=True,
            check=True,
        )

    head_before = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    index_before = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=primary,
        capture_output=True,
        check=True,
    ).stdout
    worktree_before = growth_path.read_bytes()
    worktree_mode_before = stat.S_IMODE(os.lstat(growth_path).st_mode)

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )

    assert outcome["bumped"] is False, outcome
    assert outcome["retry_settled"] is False, outcome
    assert outcome["reason"] == "retry_authority_error", outcome
    assert outcome["retry_authority_error"], outcome
    assert outcome["commit_generated_governance_paths"] == [], outcome
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == head_before
    assert subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=primary,
        capture_output=True,
        check=True,
    ).stdout == index_before
    assert growth_path.read_bytes() == worktree_before
    assert stat.S_IMODE(os.lstat(growth_path).st_mode) == worktree_mode_before


def test_commit_generated_governance_growth_cap_committed_continuation_remains_valid(
    tmp_path,
):
    """A successful commit expires retry authority and retains P0IC3 reuse."""
    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py",
            "mu/tests/test_existing_2.py",
        ],
    )
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    first = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )
    assert first["bumped"] is True, first
    _git(["commit", "-m", "commit exact generated growth cap"], cwd=primary, env=env)

    second = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )

    assert second["bumped"] is False, second
    assert second["retry_settled"] is False, second
    assert second["reason"] == "already_recorded", second
    assert second["commit_generated_governance_paths"] == [
        commit_mod.GROWTH_CAP_TEST_RELPATH
    ]
    text, _, cap = _read_growth_cap_values(primary)
    assert cap == 1, text
    assert text.count(f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}") == 1
    assert not _growth_cap_staged(primary)
    assert _git(
        ["diff", "--quiet", "--", commit_mod.GROWTH_CAP_TEST_RELPATH],
        cwd=primary,
    ).returncode == 0


def test_commit_generated_governance_rejects_unsupported_growth_cap_path(tmp_path):
    repo = _init_repo(tmp_path)
    handoff = {"wave_id": "commit-generated-unsupported-growth-cap-wave"}
    before = _git(["status", "--porcelain=v1", "-z"], cwd=repo).stdout

    refreshed, staged, error = commit_mod.refresh_commit_path_packet_truth(
        repo_root=repo,
        handoff=handoff,
        indicator_path="reports/l4_wave_indicators/unused.json",
        commit_status="pre_commit_supervisor_pending",
        commit_generated_governance_paths=["mu/tests/docs/not_growth_caps.py"],
        commit_generated_governance_provenance="bumped",
    )

    assert refreshed is handoff
    assert staged == []
    assert error == (
        "unsupported commit-generated governance path before supervisor: "
        "mu/tests/docs/not_growth_caps.py"
    )
    assert _git(["status", "--porcelain=v1", "-z"], cwd=repo).stdout == before


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


def test_growth_cap_autobump_ignores_untracked_stray_test_file(tmp_path):
    """Untracked-stray regression (count boundary): an UNTRACKED
    mu/tests/test_*.py on disk must NOT contribute to the cap bump. The auto-bump
    counts the COMMITTED (git-index) test set, so a wave that stages exactly ONE
    real new test under a valid FOUNDER_OVERRIDE bumps CAP_TEST_FILES by EXACTLY
    +1 — never +2 for a stray the commit never includes (which would permanently
    over-grant the cap, an invariant-weakening bypass). The prior on-disk rglob
    folded the stray in; this pins the boundary tightening to the git index."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    # The wave legitimately stages exactly ONE real new test file.
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")
    # A stray UNTRACKED test file sits in the working tree — never staged, never
    # committed (e.g. a generated/scratch test left behind in the checkout).
    stray = primary / "mu" / "tests" / "test_untracked_stray.py"
    stray.write_text("def test_stray():\n    assert True\n", encoding="utf-8")
    # Precondition: the on-disk rglob (the OLD count, and what the Step 8 gate
    # measures) sees 5 test files — committed test_growth_caps.py + 2 existing +
    # the staged new one + the untracked stray — so the OLD disk-based shortfall
    # would have been 2, i.e. the buggy bump would have been +2 (the defect).
    assert _count_disk_test_files(primary) == 5
    assert _count_disk_test_files(primary) - (3 + 0) == 2  # OLD (buggy) shortfall
    lines, log = _make_capture_log()

    outcome = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary, wave_id=GROWTH_CAP_WAVE_ID, base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID, log=log,
    )

    # The bump accounts for ONLY the staged file (+1), ignoring the untracked
    # stray: index count 4 - (baseline 3 + cap 0) = 1, NOT the disk count's 2.
    assert outcome["bumped"] is True, outcome
    assert outcome["reason"] == "bumped", outcome
    assert outcome["shortfall"] == 1, outcome
    assert outcome["bump_amount"] == 1, outcome
    assert outcome["previous_cap"] == 0, outcome
    assert outcome["new_cap"] == 1, outcome
    # The stray is untracked, so it is never detected as a new staged test file
    # and never named in the provenance comment.
    assert outcome["new_test_files"] == ["mu/tests/tools/test_new_feature.py"], outcome
    text, baseline, cap = _read_growth_cap_values(primary)
    assert cap == 1, text  # +1, NOT +2
    assert "test_new_feature.py" in text, text
    assert "test_untracked_stray.py" not in text, text
    assert _growth_cap_staged(primary)

    # The untracked stray was left untouched on disk and never staged.
    assert stray.exists()
    staged = _git(["diff", "--cached", "--name-only"], cwd=primary).stdout.split()
    assert "mu/tests/test_untracked_stray.py" not in staged, staged

    # Fail-closed, not fail-open: with the cap bumped by only +1, the disk-based
    # Step 8 gate (which still counts the stray) sees 5 > baseline + cap (4) and
    # strands the commit — exactly as any over-cap commit does. The cap was NOT
    # silently inflated to cover a file the commit never includes.
    assert _count_disk_test_files(primary) > baseline + cap, (baseline, cap)
    assert any(
        f"auto-bumped CAP_TEST_FILES +1 for FOUNDER_OVERRIDE wave {GROWTH_CAP_WAVE_ID}"
        in m
        for m in lines
    ), lines


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


# ─────────────────────────────────────────────────────────────────────────
# Growth-cap auto-bump CALL-SITE contract on the NORMAL commit path
# (wave: pipeline-growth-cap-autobump-normal-commit-override-2026-06-21)
#
# The sibling test_growth_cap_autobump_* cases above call the public auto-bump
# seam DIRECTLY with an explicit founder_override_token=. The two cases below
# instead drive a NORMAL (non-UPDATE_TRACKER_ONLY) commit through
# run_commit_pipeline -> _run_commit_pipeline_impl, so the Step-5e auto-bump
# receives the token RESOLVED at Step 1 from the tracker note
# (_resolve_control_surface_founder_override_token). This locks the verified
# call-site contract: that Step-1-resolved, tracker-note-inclusive
# founder_override_token is the exact value passed to the Step-5e
# _maybe_autobump_growth_cap_for_founder_override call — it is never reassigned
# between Step 1 and Step 5e — so a declared override auto-bumps on the normal
# commit path instead of stranding. Run against UNMODIFIED commit_executor.py;
# no commit_executor.py change is required (the original packet's proposed swap
# to `effective_founder_override_token`, a handoff-builder local, targets a
# variable that is out of scope at the Step-5e call site).
# ─────────────────────────────────────────────────────────────────────────


class _StopPipelineAfterGrowthCapAutobump(BaseException):
    """Sentinel raised by the Step-5e spy to halt the pipeline right after the
    growth-cap auto-bump, BEFORE the Step 6 supervisor (so no bridge is needed).

    Subclasses BaseException (NOT Exception) deliberately: the Step-5e call in
    _run_commit_pipeline_impl is wrapped in `except Exception` (an auto-bump
    error is non-fatal there), so an Exception sentinel would be swallowed and
    the pipeline would continue into the supervisor. A BaseException escapes
    that guard and propagates cleanly out of run_commit_pipeline (which has no
    try/finally around the impl call)."""


def _add_growth_cap_pipeline_scaffolding(primary: Path) -> None:
    """Add the minimal commit-pipeline fixture (a TASKS.md ## Ra section, an
    indicator collector stub, and a Phase B handoff receipt) onto the
    growth-cap PRIMARY so run_commit_pipeline can reach Step 5e.

    The indicator stub is written UNTRACKED (never git-added), exactly like the
    receipt suite's _setup_repo, so it is NOT detected as a new mu/tools script
    by the auto-bump's staged-additions-vs-merge-base scan
    (_new_mu_tool_scripts_vs_merge_base reads `git diff --cached
    --diff-filter=A`) — keeping the regression focused on CAP_TEST_FILES."""
    (primary / "TASKS.md").write_text(
        "## Ra\n\n- Tracker sync note (seed): init\n\n---\n", encoding="utf-8"
    )
    indicator = primary / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    indicator.parent.mkdir(parents=True, exist_ok=True)
    indicator.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json, pathlib\n"
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--wave-id")\n'
        'p.add_argument("--output")\n'
        "a = p.parse_args()\n"
        "out = pathlib.Path(a.output)\n"
        "out.parent.mkdir(parents=True, exist_ok=True)\n"
        'out.write_text(json.dumps({"wave_id": a.wave_id}))\n',
        encoding="utf-8",
    )
    receipt_dir = primary / ".agent_bus" / "meta"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "pre_commit_receipt.json").write_text(
        json.dumps({
            "decision": "COMMIT_GO", "staged_sha": "phase_b_sha",
            "timestamp_utc": "2026-03-24T00:00:00+00:00",
        }),
        encoding="utf-8",
    )


def _growth_cap_normal_commit_handoff(wave_id: str, *, declare_override: bool) -> dict:
    """A valid NON-UPDATE_TRACKER_ONLY (normal) commit handoff whose tracker
    note optionally declares this wave's FOUNDER_OVERRIDE. wave_class
    L4_ENABLER permits founder-override resolution; with declare_override=False
    and no tracked_packet, Step 1 resolves an EMPTY token (fail-closed) because
    neither the tracker note nor an authorized control-surface packet grants
    one."""
    note = (
        f"- Tracker sync note (2026-06-21, {wave_id}): **Growth-cap autobump "
        f"normal-commit call-site regression.** Class: L4_ENABLER. "
        f"target_gate_id: G8. "
        f"evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -q "
        f"mu/tests/tools/test_commit_executor_post_merge_cleanup.py "
        f"-k 'growth or autobump or cap' --tb=short`. "
        f"evidence_delta: (1) Locks the Step-1 -> Step-5e token flow. "
        f"(2) Proves the cap bumps on a declared override. "
        f"(3) Proves fail-closed without one. "
        f"progress_proof_before: call-site flow regression-unlocked. "
        f"progress_proof_after: call-site flow regression-locked. "
        f"primary_blocker_class: INTEGRATION. "
        f"primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
        f"indicator_artifact_ref: reports/l4_wave_indicators/{wave_id}.json. "
        f"indicator_collection_command: python3 "
        f"mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
        f"--output reports/l4_wave_indicators/{wave_id}.json. "
        f"bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        f"boot0_track_id: V1. boot0_progress_state: HOLD."
    )
    if declare_override:
        note = f"{note} FOUNDER_OVERRIDE:{wave_id} (test authorization)"
    return {
        "wave_id": wave_id,
        "task_id": "[TEST]",
        "wave_class": "L4_ENABLER",
        "target_gate_id": "G8",
        "caller": "phase_b",
        "branch_prefix": "jabramsja",
        "files_to_stage": ["mu/tests/tools/test_new_feature.py"],
        "force_add_files": [],
        "commit_message": "feat: growth-cap autobump call-site regression\n\nCo-Authored-By: test",
        "pr_title": "feat: growth-cap autobump call-site regression",
        "pr_body": "## Summary\nregression",
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "fixes_implemented": ["lock Step-1 -> Step-5e founder-override flow"],
        "tracker_note_text": note,
    }


def _drive_pipeline_capturing_autobump_token(primary, handoff, monkeypatch):
    """Drive run_commit_pipeline (which executes _run_commit_pipeline_impl) and
    capture the founder_override_token the Step-5e growth-cap auto-bump
    RECEIVES. A spy records the token, delegates to the REAL auto-bump (so a
    genuine bump/no-op is exercised end-to-end), then raises the BaseException
    sentinel to halt before the Step 6 supervisor. Returns (token, outcome).

    String-named getattr/setattr keep this gate-safe (no dotted private-attr
    access), matching the sibling `_run` patch above."""
    real_autobump = getattr(
        commit_mod, "_maybe_autobump_growth_cap_for_founder_override"
    )
    captured: dict = {}

    def _spy(repo_root, *, wave_id, base_branch, founder_override_token, log):
        captured["token"] = founder_override_token
        captured["outcome"] = real_autobump(
            repo_root,
            wave_id=wave_id,
            base_branch=base_branch,
            founder_override_token=founder_override_token,
            log=log,
        )
        raise _StopPipelineAfterGrowthCapAutobump()

    monkeypatch.setattr(
        commit_mod, "_maybe_autobump_growth_cap_for_founder_override", _spy
    )
    try:
        result = commit_mod.run_commit_pipeline(handoff, repo_root=primary)
    except _StopPipelineAfterGrowthCapAutobump:
        return captured["token"], captured["outcome"]
    raise AssertionError(
        "pipeline did not reach the Step-5e growth-cap auto-bump; it returned "
        f"early: {result}"
    )


def test_growth_cap_autobump_receives_resolved_override_on_normal_commit_path(
    tmp_path, monkeypatch
):
    """NORMAL (non-UPDATE_TRACKER_ONLY) commit whose tracker note declares the
    wave's FOUNDER_OVERRIDE, driven through run_commit_pipeline ->
    _run_commit_pipeline_impl: the Step-5e auto-bump RECEIVES the NON-EMPTY
    token Step 1 resolved from the tracker note
    (_resolve_control_surface_founder_override_token), so CAP_TEST_FILES bumps
    by the exact shortfall instead of stranding.

    Unlike the sibling test_growth_cap_autobump_* cases (which call the
    auto-bump seam directly with an explicit founder_override_token=), this
    exercises the pipeline's Step-1 -> Step-5e token RESOLUTION + flow against
    UNMODIFIED commit_executor.py — no source change is required."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _add_growth_cap_pipeline_scaffolding(primary)
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")

    handoff = _growth_cap_normal_commit_handoff(
        GROWTH_CAP_WAVE_ID, declare_override=True
    )
    token, outcome = _drive_pipeline_capturing_autobump_token(
        primary, handoff, monkeypatch
    )

    # The token Step 5e received is exactly the Step-1-resolved, tracker-note
    # inclusive FOUNDER_OVERRIDE — NON-EMPTY — proving the call-site contract.
    assert token == GROWTH_CAP_WAVE_ID, token
    # And it drives a real bump (non-empty token -> cap bumps by the shortfall).
    assert outcome["bumped"] is True, outcome
    assert outcome["shortfall"] == 1, outcome
    assert outcome["new_cap"] == 1, outcome
    text, _, cap = _read_growth_cap_values(primary)
    assert cap == 1, text
    assert f"FOUNDER_OVERRIDE:{GROWTH_CAP_WAVE_ID}" in text, text
    # test_growth_caps.py is staged so the Step 8 gate would see the bumped cap.
    assert _growth_cap_staged(primary)


def test_growth_cap_autobump_strands_without_declared_override_on_normal_commit_path(
    tmp_path, monkeypatch
):
    """Fail-closed companion: the SAME normal commit path with NO declared
    FOUNDER_OVERRIDE (and no tracked_packet authorizing the control surface)
    resolves an EMPTY token at Step 1, so the Step-5e auto-bump receives "" and
    does NOT bump — the growth-cap gate would still strand the commit exactly as
    today. Locks that the call-site flow never fabricates an override."""
    primary, env = _init_growth_cap_repo(
        tmp_path, baseline=3, cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py", "mu/tests/test_existing_2.py",
        ],
    )
    _add_growth_cap_pipeline_scaffolding(primary)
    _stage_new_test_file(primary, env, "mu/tests/tools/test_new_feature.py")

    handoff = _growth_cap_normal_commit_handoff(
        GROWTH_CAP_WAVE_ID, declare_override=False
    )
    token, outcome = _drive_pipeline_capturing_autobump_token(
        primary, handoff, monkeypatch
    )

    # No declared override -> Step 1 resolves an EMPTY token -> Step 5e no-op.
    assert token == "", token
    assert outcome["bumped"] is False, outcome
    assert outcome["reason"] == "no_founder_override", outcome
    # The genuine shortfall is unchanged; the cap is NOT bumped (fail-closed).
    assert outcome["shortfall"] == 1, outcome
    _, _, cap = _read_growth_cap_values(primary)
    assert cap == 0, cap
    assert not _growth_cap_staged(primary)


def test_commit_generated_governance_growth_cap_failed_attempt_retry_settles_before_supervisor(
    tmp_path,
    monkeypatch,
):
    """Drive the reproduced Step5e -> Step8 failure -> Step4 retry lifecycle."""
    import types

    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py",
            "mu/tests/test_existing_2.py",
        ],
    )
    _add_growth_cap_pipeline_scaffolding(primary)
    new_test_path = "mu/tests/tools/test_new_feature.py"
    _stage_new_test_file(primary, env, new_test_path)

    wave_id = GROWTH_CAP_WAVE_ID
    packet_path = "reports/control_plane/commit_generated_governance_retry.md"
    packet = primary / packet_path
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(
        "# Commit Generated Governance Retry\n\n"
        "Status: COMPLETED (commit-ready, supervisor COMMIT_GO)\n"
        f"Wave ID: {wave_id}\n"
        "Class: L4_ENABLER\n"
        "Target gate: G8\n\n"
        f"FOUNDER_OVERRIDE:{wave_id}\n",
        encoding="utf-8",
    )
    handoff = _growth_cap_normal_commit_handoff(wave_id, declare_override=True)
    handoff.update(
        {
            "files_to_stage": [new_test_path, packet_path, "TASKS.md"],
            "tracked_packet": packet_path,
            "scope_items": [packet_path],
        }
    )
    (primary / "TASKS.md").write_text(
        "# Tasks\n\n"
        "## Ra\n\n"
        f"{handoff['tracker_note_text']}\n"
        "  6. **[FOUNDER-ORDERED-REDTEAM-COMMIT-GENERATED-GOVERNANCE-RETRY] "
        "IMPLEMENTED / LOCAL EVIDENCE (2026-09-10).** "
        "Task: `[COMMIT-GENERATED-GOVERNANCE-RETRY]`. "
        f"Wave ID: `{wave_id}`. Class: `L4_ENABLER`. Packet: `{packet_path}`.\n\n"
        "---\n",
        encoding="utf-8",
    )

    hook = primary / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/usr/bin/env bash\necho retry-fixture >&2\nexit 17\n", encoding="utf-8")

    supervisor_receipt = primary / ".scratch" / "step6_retry_receipt.json"
    supervisor_receipt.parent.mkdir(parents=True, exist_ok=True)
    supervisor_receipt.write_text(
        json.dumps(
            {
                "decision": "COMMIT_GO",
                "staged_sha": "fixture",
                "timestamp_utc": "2026-09-10T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    supervisor_packages: list[dict] = []

    def _supervisor(package_path, *args, **kwargs):
        supervisor_packages.append(
            json.loads(Path(package_path).read_text(encoding="utf-8"))
        )
        return types.SimpleNamespace(
            decision="COMMIT_GO",
            summary="retry lifecycle fixture",
            receipt_path=".scratch/step6_retry_receipt.json",
        )

    monkeypatch.setattr(
        commit_mod,
        "_load_repo_meta_bridge_client",
        lambda repo_root: (_supervisor, Exception),
    )
    real_autobump = getattr(
        commit_mod, "_maybe_autobump_growth_cap_for_founder_override"
    )
    autobump_outcomes: list[dict] = []

    def _capture_autobump(*args, **kwargs):
        value = real_autobump(*args, **kwargs)
        autobump_outcomes.append(json.loads(json.dumps(value)))
        return value

    monkeypatch.setattr(
        commit_mod,
        "_maybe_autobump_growth_cap_for_founder_override",
        _capture_autobump,
    )

    base_head = _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip()
    first = commit_mod.run_commit_pipeline(handoff, repo_root=primary)

    assert first["status"] == "error", first
    assert first["step"] == "run_pre_commit_script", first
    assert "settle_commit_generated_governance" in first["steps_completed"]
    assert "build_and_run_supervisor" in first["steps_completed"]
    assert "validate_receipt" in first["steps_completed"]
    assert "git_commit" not in first["steps_completed"]
    assert autobump_outcomes[0]["bumped"] is True, autobump_outcomes[0]
    assert autobump_outcomes[0]["reason"] == "bumped", autobump_outcomes[0]
    growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
    growth_file = primary / growth_path
    first_postimage = growth_file.read_bytes()
    first_index_blob = subprocess.run(
        ["git", "show", f":{growth_path}"],
        cwd=primary,
        capture_output=True,
        check=True,
    ).stdout
    assert first_index_blob == first_postimage
    assert growth_path in json.loads(
        (primary / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text(
            encoding="utf-8"
        )
    )["files_to_stage"]
    assert commit_mod.COMMIT_RETRY_PENDING_STATUS in packet.read_text(encoding="utf-8")

    retry_handoff = json.loads(
        (primary / ".agent_bus" / "executors" / "phase_b_handoff.json").read_text(
            encoding="utf-8"
        )
    )
    second = commit_mod.run_commit_pipeline(retry_handoff, repo_root=primary)

    assert second["status"] == "error", second
    assert second["step"] == "run_pre_commit_script", second
    assert "restore_commit_retry_state" in second["steps_completed"]
    assert "settle_commit_generated_governance" in second["steps_completed"]
    assert "build_and_run_supervisor" in second["steps_completed"]
    assert second["steps_completed"].index("restore_commit_retry_state") < second[
        "steps_completed"
    ].index("settle_commit_generated_governance")
    assert second["steps_completed"].index("settle_commit_generated_governance") < second[
        "steps_completed"
    ].index("build_and_run_supervisor")
    assert len(autobump_outcomes) == 2, autobump_outcomes
    assert autobump_outcomes[1]["bumped"] is False, autobump_outcomes[1]
    assert autobump_outcomes[1]["retry_settled"] is True, autobump_outcomes[1]
    assert autobump_outcomes[1]["reason"] == "retry_settled", autobump_outcomes[1]

    retry_package = supervisor_packages[1]
    assert retry_package["changed_files"].count(growth_path) == 1
    assert retry_package["scope_items"].count(growth_path) == 1
    target_entries = _git(
        ["ls-files", "--stage", "--", growth_path], cwd=primary
    ).stdout.strip().splitlines()
    assert len(target_entries) == 1, target_entries
    assert target_entries[0].split()[2] == "0", target_entries
    assert subprocess.run(
        ["git", "show", f":{growth_path}"],
        cwd=primary,
        capture_output=True,
        check=True,
    ).stdout == first_postimage
    assert growth_file.read_bytes() == first_postimage
    final_text, _, final_cap = _read_growth_cap_values(primary)
    assert final_cap == 1, final_text
    assert final_text.count(f"FOUNDER_OVERRIDE:{wave_id}") == 1, final_text
    assert _git(["rev-parse", "HEAD"], cwd=primary).stdout.strip() == base_head


def test_commit_generated_governance_growth_cap_invalid_retry_stops_before_supervisor(
    tmp_path,
    monkeypatch,
):
    """A forged durable target is fatal even when Step 4 authorizes its path."""
    primary, env = _init_growth_cap_repo(
        tmp_path,
        baseline=3,
        cap=0,
        existing_test_files=[
            "mu/tests/test_existing_1.py",
            "mu/tests/test_existing_2.py",
        ],
    )
    _add_growth_cap_pipeline_scaffolding(primary)
    new_test_path = "mu/tests/tools/test_new_feature.py"
    _stage_new_test_file(primary, env, new_test_path)
    first = commit_mod.maybe_autobump_growth_cap_for_founder_override(
        repo_root=primary,
        wave_id=GROWTH_CAP_WAVE_ID,
        base_branch="dev",
        founder_override_token=GROWTH_CAP_WAVE_ID,
        log=_noop_log,
    )
    assert first["bumped"] is True, first
    growth_path = commit_mod.GROWTH_CAP_TEST_RELPATH
    growth_file = primary / growth_path
    growth_file.write_bytes(
        growth_file.read_bytes().replace(
            b"CAP_TEST_FILES = 1", b"CAP_TEST_FILES = 2", 1
        )
    )
    _git(["add", "--", growth_path], cwd=primary)

    supervisor_called = False

    def _supervisor(*args, **kwargs):
        nonlocal supervisor_called
        supervisor_called = True
        raise AssertionError("supervisor must not authorize forged retry bytes")

    monkeypatch.setattr(
        commit_mod,
        "_load_repo_meta_bridge_client",
        lambda repo_root: (_supervisor, Exception),
    )
    handoff = _growth_cap_normal_commit_handoff(
        GROWTH_CAP_WAVE_ID, declare_override=True
    )
    handoff["files_to_stage"] = [new_test_path, growth_path]
    result = commit_mod.run_commit_pipeline(handoff, repo_root=primary)

    assert result["status"] == "error", result
    assert result["step"] == "settle_commit_generated_governance", result
    assert "retry authority rejected candidate" in result["errors"][0]
    assert supervisor_called is False
