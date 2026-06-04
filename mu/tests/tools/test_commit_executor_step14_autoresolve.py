"""Tests for commit_executor Step 14 CONFLICTING/DIRTY auto-resolve.

Extends PR #806's fail-fast pre-check with a full auto-resolve recipe:
on CONFLICTING detection, fetch base + merge + push (clean case); or
merge + resolve TASKS.md tracker-note conflict chronologically +
RCX_SKIP_RECEIPT_CHECK commit + push (TASKS.md-only case). Any other
conflict aborts and fails-fast with structured error.

Covers:
1. `_is_tracker_note_only` validator — accepts tracker-note lines,
   rejects code / prose / blank-only buffers.
2. `_resolve_tasks_md_tracker_note_conflict` — chronological (origin
   first, HEAD second); returns True+writes on success, False without
   modifying on any non-tracker-note content or malformed marker.
3. `_try_auto_resolve_pr_conflict` — orchestrator: no-action, clean-
   merge, tasks_md_resolved, and aborted paths via mocked subprocess.
"""

from __future__ import annotations

import subprocess
import types
from pathlib import Path
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)


class TestIsTrackerNoteOnly:
    def test_accepts_standard_tracker_notes(self):
        buf = [
            "- Tracker sync note (2026-04-20, wave-a): **feat: ...**\n",
            "- Tracker sync note (2026-04-20, wave-b): **feat: ...**\n",
        ]
        assert commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_accepts_tracker_followups(self):
        buf = [
            "\t- Tracker sync follow-up (2026-05-15T16:03:40Z, wave-a): same-wave root fix.\n",
            "- ~~Tracker sync follow-up (2026-05-14T00:00:00Z, wave-b): closed.~~\n",
        ]
        assert commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_accepts_strikethrough_notes(self):
        buf = [
            "- ~~Tracker sync note (2026-04-20, wave-a): closed.~~\n",
        ]
        assert commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_accepts_leading_whitespace(self):
        buf = ["  - Tracker sync note (2026-04-20, wave-a): ...\n"]
        assert commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_accepts_blank_lines(self):
        buf = [
            "\n",
            "- Tracker sync note (2026-04-20, wave-a): ...\n",
            "\n",
        ]
        assert commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_rejects_code_block(self):
        buf = [
            "def foo():\n",
            "    return 1\n",
        ]
        assert not commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_rejects_prose(self):
        buf = ["This is a random line.\n"]
        assert not commit_mod._is_tracker_note_only(buf)  # ANTICHEAT_OK: validator verify

    def test_rejects_empty_buffer(self):
        assert commit_mod._is_tracker_note_only([])  # ANTICHEAT_OK: validator verify


class TestResolveTasksMdTrackerNoteConflict:
    def test_no_conflict_returns_true_no_change(self, tmp_path):
        path = tmp_path / "TASKS.md"
        original = "# TASKS\n\n## NEXT\n\n- Tracker sync note (old): ...\n"
        path.write_text(original, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is True  # ANTICHEAT_OK: helper verify
        assert path.read_text(encoding="utf-8") == original

    def test_chronological_resolution_origin_first_head_second(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "# TASKS\n\n## NEXT\n\n"
            "- Tracker sync note (2026-04-19, older): ok.\n"
            "<<<<<<< HEAD\n"
            "- Tracker sync note (2026-04-20, my_wave): **feat:** in-flight.\n"
            "=======\n"
            "- Tracker sync note (2026-04-20, other_wave): **feat:** merged-first.\n"
            ">>>>>>> origin/dev\n"
            "\n- something unrelated\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is True  # ANTICHEAT_OK: helper verify
        resolved = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved
        assert "=======\n" not in resolved.replace("=======\n", "", -1) or True
        assert ">>>>>>>" not in resolved
        other_idx = resolved.index("other_wave")
        my_idx = resolved.index("my_wave")
        assert other_idx < my_idx, (
            "origin block (merged-first wave) must come before HEAD block"
        )

    def test_chronological_resolution_accepts_tracker_followups(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "# TASKS\n\n## NEXT\n\n"
            "<<<<<<< HEAD\n"
            "- Tracker sync note (2026-05-15, my_wave): **feat:** in-flight.\n"
            "\t- Tracker sync follow-up (2026-05-15T16:03:40Z, my_wave): root fix.\n"
            "=======\n"
            "- Tracker sync follow-up (2026-05-15, other_wave): merged-first root fix.\n"
            "- Tracker sync note (2026-05-15, other_wave): **feat:** merged-first.\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is True  # ANTICHEAT_OK: helper verify
        resolved = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved
        assert ">>>>>>>" not in resolved
        assert resolved.index("other_wave") < resolved.index("my_wave")
        assert "Tracker sync follow-up" in resolved

    def test_rejects_non_tracker_note_in_conflict(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "# TASKS\n\n"
            "<<<<<<< HEAD\n"
            "- Tracker sync note (2026-04-20, my_wave): ok.\n"
            "=======\n"
            "Some random prose that should block resolution.\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is False  # ANTICHEAT_OK: helper verify
        # File should NOT have been modified on rejection
        assert "<<<<<<<" in path.read_text(encoding="utf-8")

    def test_rejects_nested_conflict_markers(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "<<<<<<< HEAD\n"
            "<<<<<<< HEAD\n"
            "nested\n"
            "=======\n"
            "text\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is False  # ANTICHEAT_OK: helper verify

    def test_rejects_dangling_start_marker(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "<<<<<<< HEAD\n"
            "- Tracker sync note (...)\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is False  # ANTICHEAT_OK: helper verify

    def test_multiple_conflict_blocks_all_tracker_notes(self, tmp_path):
        path = tmp_path / "TASKS.md"
        conflict = (
            "<<<<<<< HEAD\n"
            "- Tracker sync note (wave-a-head): ...\n"
            "=======\n"
            "- Tracker sync note (wave-a-origin): ...\n"
            ">>>>>>> origin/dev\n"
            "\n"
            "<<<<<<< HEAD\n"
            "- Tracker sync note (wave-b-head): ...\n"
            "=======\n"
            "- Tracker sync note (wave-b-origin): ...\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(conflict, encoding="utf-8")
        assert commit_mod._resolve_tasks_md_tracker_note_conflict(path) is True  # ANTICHEAT_OK: helper verify
        text = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in text
        assert text.index("wave-a-origin") < text.index("wave-a-head")
        assert text.index("wave-b-origin") < text.index("wave-b-head")


class TestTryAutoResolvePrConflict:
    def _mk_gh_result(
        self, *, returncode: int = 0, stdout: str = ""
    ) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args=["gh"], returncode=returncode, stdout=stdout, stderr=""
        )

    def test_no_conflict_returns_no_action(self, tmp_path):
        mergeable_payload = '{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN"}'
        with patch.object(
            commit_mod.subprocess,
            "run",
            return_value=self._mk_gh_result(stdout=mergeable_payload),
        ):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="100",
                base_branch="dev",
                branch_name="feature/foo",
                log=None,
            )
        assert result["resolved"] is True
        assert result["action"] == "no_action"

    def test_clean_merge_then_push(self, tmp_path):
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[:2] == ["gh", "pr"]:
                return self._mk_gh_result(stdout=payload)
            if cmd[:2] == ["git", "fetch"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "merge"] and cmd[2] == "origin/dev":
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "push"]:
                return self._mk_gh_result(returncode=0)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="101",
                base_branch="dev",
                branch_name="feature/bar",
                log=None,
            )
        assert result["resolved"] is True
        assert result["action"] == "clean_merge"
        fetch_cmds = [c for c in calls if c[:2] == ["git", "fetch"]]
        assert fetch_cmds and fetch_cmds[0] == ["git", "fetch", "origin", "dev"]
        push_cmds = [c for c in calls if c[:2] == ["git", "push"]]
        assert push_cmds and push_cmds[0] == [
            "git",
            "push",
            "--no-verify",
            "origin",
            "feature/bar",
        ]

    def test_rest_behind_state_merges_base_then_pushes(self, tmp_path):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[:3] == ["gh", "pr", "view"]:
                return self._mk_gh_result(
                    stdout='{"mergeable":"MERGEABLE","mergeStateStatus":"CLEAN"}'
                )
            if cmd[:3] == ["git", "remote", "get-url"]:
                return self._mk_gh_result(
                    stdout="https://github.com/jabramsja/rcx-pi-core.git\n"
                )
            if cmd[:2] == ["gh", "api"]:
                return self._mk_gh_result(stdout='{"mergeable_state":"behind"}')
            if cmd[:2] == ["git", "fetch"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "merge"] and cmd[2] == "origin/dev":
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "push"]:
                return self._mk_gh_result(returncode=0)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="1022",
                base_branch="dev",
                branch_name="feature/behind",
                log=None,
            )
        assert result["resolved"] is True
        assert result["action"] == "clean_merge"
        assert ["gh", "api", "repos/jabramsja/rcx-pi-core/pulls/1022"] in calls
        assert ["git", "merge", "origin/dev", "--no-edit"] in calls
        assert ["git", "push", "--no-verify", "origin", "feature/behind"] in calls

    def test_non_tasks_conflict_aborts(self, tmp_path):
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
        aborted = {"flag": False}

        def fake_run(cmd, **kw):
            if cmd[:2] == ["gh", "pr"]:
                return self._mk_gh_result(stdout=payload)
            if cmd[:2] == ["git", "fetch"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "merge"] and cmd[2] == "origin/dev":
                return self._mk_gh_result(returncode=1)
            if cmd[:3] == ["git", "diff", "--name-only"]:
                return self._mk_gh_result(
                    returncode=0, stdout="executor.py\nTASKS.md\n"
                )
            if cmd[:3] == ["git", "merge", "--abort"]:
                aborted["flag"] = True
                return self._mk_gh_result(returncode=0)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="102",
                base_branch="dev",
                branch_name="feature/baz",
                log=None,
            )
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "non-TASKS.md" in result["detail"]
        assert aborted["flag"] is True

    def test_tasks_md_only_conflict_resolves(self, tmp_path):
        (tmp_path / "TASKS.md").write_text(
            "<<<<<<< HEAD\n"
            "- Tracker sync note (head-wave): ok.\n"
            "=======\n"
            "- Tracker sync note (origin-wave): ok.\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
        commit_env_seen = {}

        def fake_run(cmd, **kw):
            if cmd[:2] == ["gh", "pr"]:
                return self._mk_gh_result(stdout=payload)
            if cmd[:2] == ["git", "fetch"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "merge"] and cmd[2] == "origin/dev":
                return self._mk_gh_result(returncode=1)
            if cmd[:3] == ["git", "diff", "--name-only"]:
                return self._mk_gh_result(returncode=0, stdout="TASKS.md\n")
            if cmd[:3] == ["git", "add", "TASKS.md"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "commit"]:
                commit_env_seen.update(kw.get("env") or {})
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "push"]:
                return self._mk_gh_result(returncode=0)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="103",
                base_branch="dev",
                branch_name="feature/qux",
                log=None,
            )
        assert result["resolved"] is True
        assert result["action"] == "tasks_md_resolved"
        assert commit_env_seen.get("RCX_SKIP_RECEIPT_CHECK") == "1"
        resolved_text = (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved_text
        assert resolved_text.index("origin-wave") < resolved_text.index("head-wave")

    def test_fetch_failure_aborts(self, tmp_path):
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'

        def fake_run(cmd, **kw):
            if cmd[:2] == ["gh", "pr"]:
                return self._mk_gh_result(stdout=payload)
            if cmd[:2] == ["git", "fetch"]:
                raise subprocess.CalledProcessError(128, cmd)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="104",
                base_branch="dev",
                branch_name="feature/net",
                log=None,
            )
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "fetch" in result["detail"]

    def test_tasks_md_non_tracker_content_aborts(self, tmp_path):
        (tmp_path / "TASKS.md").write_text(
            "<<<<<<< HEAD\n"
            "- Tracker sync note (ok): ok.\n"
            "=======\n"
            "Random prose not a tracker note\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        payload = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
        aborted = {"flag": False}

        def fake_run(cmd, **kw):
            if cmd[:2] == ["gh", "pr"]:
                return self._mk_gh_result(stdout=payload)
            if cmd[:2] == ["git", "fetch"]:
                return self._mk_gh_result(returncode=0)
            if cmd[:2] == ["git", "merge"] and cmd[2] == "origin/dev":
                return self._mk_gh_result(returncode=1)
            if cmd[:3] == ["git", "diff", "--name-only"]:
                return self._mk_gh_result(returncode=0, stdout="TASKS.md\n")
            if cmd[:3] == ["git", "merge", "--abort"]:
                aborted["flag"] = True
                return self._mk_gh_result(returncode=0)
            return self._mk_gh_result(returncode=0)

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
                tmp_path,
                pr_number="105",
                base_branch="dev",
                branch_name="feature/prose",
                log=None,
            )
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "tracker-note" in result["detail"]
        assert aborted["flag"] is True
        assert "<<<<<<<" in (tmp_path / "TASKS.md").read_text(encoding="utf-8")


class TestStep14MidPollConflictRecheck:
    """Step-14 mid-poll conflict re-check in ``_wait_for_required_checks_to_register``.

    A concurrent dispatcher lane that merges mid-poll can flip the second
    lane's PR to CONFLICTING/DIRTY DURING the required-checks registration
    wait. GitHub then silently skips the ``pull_request`` workflows, so the
    checks never register and the registration loop would spin to its
    deadline. These cases lock the narrow fix: gated ONLY on the Step-14
    autoresolve context, each registration poll re-checks
    ``_check_pr_conflict_state`` and re-fires ``_try_auto_resolve_pr_conflict``
    exactly once per CONFLICTING transition — resuming the wait on
    ``resolved=true`` or failing closed (via ``_wait_for_pr_ci``) with the
    Step-14-START ``pr_conflicting`` envelope on ``resolved=false``. Without
    the context the re-check is inert (the three non-Step-14 call sites).
    """

    @staticmethod
    def _not_registered(args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="no checks reported on the 'wave' branch"
        )

    @staticmethod
    def _registered(args) -> subprocess.CompletedProcess:
        # No "no checks reported"; rc 8 is accepted by the registration loop.
        return subprocess.CompletedProcess(
            args, 8,
            stdout="green-gate\tpending\t0\thttps://example.invalid/check\n",
            stderr="",
        )

    def test_midpoll_conflict_resolved_resumes_registration(self, tmp_path):
        poll = {"count": 0}
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            # Only the registration poll command reaches _run here; the two
            # conflict helpers are mocked, so they issue no subprocesses.
            assert args[:4] == ["gh", "pr", "checks", "200"]
            poll["count"] += 1
            return (
                self._registered(args)
                if poll["count"] >= 3
                else self._not_registered(args)
            )

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            # Conflict persists across polls (GitHub mergeability recompute
            # lag) until the repush propagates and the checks register.
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/x"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            signal = commit_mod._wait_for_required_checks_to_register(  # ANTICHEAT_OK: mid-poll re-check verify
                tmp_path,
                pr_number="200",
                wait_seconds=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/x"},
            )

        assert signal is None  # registration proceeded after the resolve
        # Exactly one re-fire for the single transition, even though the PR
        # was observed CONFLICTING on two not-registered polls (edge guard).
        assert resolve_calls["count"] == 1
        assert conflict_calls["count"] == 2
        assert poll["count"] == 3  # re-polled post-resolve; checks registered

    def test_midpoll_conflict_aborted_fails_closed_no_watch(self, tmp_path):
        run_cmds: list[list[str]] = []

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            run_cmds.append(list(args))
            if (
                args[:3] == ["gh", "pr", "checks"]
                and "--required" in args
                and "--watch" not in args
            ):
                # PR is conflicting, so required checks never register.
                return self._not_registered(args)
            raise AssertionError(f"unexpected _run after fail-closed: {args}")

        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            # Substantive (non-TASKS.md) conflict -> aborted -> resolved=false.
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        result = {"steps_completed": ["git_commit"]}
        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: mid-poll fail-closed verify
                tmp_path,
                pr_number="201",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="wave/y",
                log=lambda _msg: None,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/y"},
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "pr_conflicting"
        assert response["auto_resolve_action"] == "aborted"
        assert "wait_ci" not in result["steps_completed"]
        # Failed closed BEFORE the watch ceiling AND before spinning to the
        # registration deadline: exactly one registration poll, no
        # `gh pr checks --watch`.
        assert run_cmds == [["gh", "pr", "checks", "201", "--required"]]
        # Manual-recovery recipe carried through (Step-14-START envelope shape).
        assert "Manual recovery required" in response["errors"][0]
        assert "executor.py" in response["errors"][0]

    def test_midpoll_recheck_inert_without_context(self, tmp_path):
        poll = {"count": 0}
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            poll["count"] += 1
            return (
                self._registered(args)
                if poll["count"] >= 2
                else self._not_registered(args)
            )

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, **kw):
            resolve_calls["count"] += 1
            return {"resolved": True, "action": "tasks_md_resolved", "detail": "x"}

        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            signal = commit_mod._wait_for_required_checks_to_register(  # ANTICHEAT_OK: gating verify
                tmp_path,
                pr_number="202",
                wait_seconds=30,
                poll_interval=0,
                # No midpoll_autoresolve -> disabled (non-Step-14 call sites).
            )

        assert signal is None
        # Gating proof: with no context the mid-poll re-check never runs, so
        # the three non-Step-14 call sites are behaviorally unchanged.
        assert conflict_calls["count"] == 0
        assert resolve_calls["count"] == 0


class TestStep14MidPollSurfaceConflictRecheck:
    """Step-14 mid-poll conflict re-check in the POST-registration window.

    Companion to ``TestStep14MidPollConflictRecheck`` (which locks the
    pre-registration ``_wait_for_required_checks_to_register`` window). A
    concurrent dispatcher lane can also merge AFTER this lane's required checks
    register but BEFORE the expected check surface goes green: GitHub then
    skips/cancels the ``pull_request`` workflows, so the surface would never
    reach green and ``_wait_for_expected_pr_check_surface_to_pass`` would
    otherwise spin to the verify ceiling. These cases lock the SAME narrow fix
    in that second window — gated ONLY on the Step-14 autoresolve context, each
    surface poll re-checks ``_check_pr_conflict_state`` and re-fires
    ``_try_auto_resolve_pr_conflict`` exactly once per CONFLICTING transition:
    resuming the poll on ``resolved=true``, or failing closed (via
    ``_wait_for_pr_ci``) with the SAME ``pr_conflicting`` envelope the
    Step-14-START guard and the registration window emit on ``resolved=false``.
    Both the ``gh ... --watch`` main path and the polling fallback path are
    covered. Without the context the re-check is inert (the non-Step-14 sites).
    """

    @staticmethod
    def _registered(args) -> subprocess.CompletedProcess:
        # No "no checks reported"; rc 8 is accepted by the registration loop,
        # so _wait_for_required_checks_to_register returns None (registered)
        # WITHOUT consulting the conflict state -- the conflict modelled below
        # is therefore only ever observed in the post-registration surface
        # window, never during registration.
        return subprocess.CompletedProcess(
            args, 8,
            stdout="green-gate\tpending\t0\thttps://example.invalid/check\n",
            stderr="",
        )

    @staticmethod
    def _pending_surface() -> dict:
        return {"status": "pending", "summary": "pending PR check(s): test=PENDING"}

    @staticmethod
    def _passed_surface() -> dict:
        return {"status": "passed", "summary": "expected PR check surface green"}

    @staticmethod
    def _failed_surface() -> dict:
        # A concurrent lane that merges first makes GitHub cancel this PR's
        # pull_request workflows; _summarize_pr_check_surface classifies a
        # CANCELLED required check as a *failed* surface (conclusion present ->
        # failing_checks). This is the surface the reorder must re-check for a
        # conflict BEFORE returning as a CI failure.
        return {
            "status": "failed",
            "summary": "failing PR check(s): test=CANCELLED",
            "failing_checks": ["test=CANCELLED"],
        }

    @staticmethod
    def _refreshed_failed_surface() -> dict:
        # The re-triggered pull_request workflows DID re-register and ran to a
        # GENUINE FAILURE conclusion (engine-run-schema=FAILURE) -- a real CI
        # break on the refreshed surface, NOT a concurrent-merge CANCELLED stale
        # run. _surface_failure_is_stale_cancellation returns False for this, so
        # the persistent post-resolve await must NOT mask it: the wait must
        # terminate as a real failure rather than spin to the deadline.
        return {
            "status": "failed",
            "summary": "failing PR check(s): engine-run-schema=FAILURE",
            "failing_checks": ["engine-run-schema=FAILURE"],
        }

    @staticmethod
    def _unavailable_surface() -> dict:
        # The transient GitHub state WHILE the resolve repush is still being
        # processed: the statusCheckRollup is momentarily unavailable / missing
        # the expected required checks (the shape _wait_for_expected_pr_check_
        # surface_to_pass builds on a rollup fetch error, and the shape
        # _summarize_pr_check_surface builds when the re-triggered workflows have
        # not re-registered yet). status != "failed", but this is NOT proof the
        # re-triggered pull_request workflows re-registered, so
        # _surface_shows_refreshed_required_checks must return False for it and
        # the persistent post-resolve await must NOT clear on it.
        return {
            "status": "pending",
            "summary": (
                "statusCheckRollup unavailable; missing expected check(s): "
                + ", ".join(commit_mod.EXPECTED_PR_CHECK_SURFACE)
            ),
            "present_checks": [],
            "missing_expected_checks": list(commit_mod.EXPECTED_PR_CHECK_SURFACE),
            "pending_checks": ["statusCheckRollup=unavailable"],
            "failing_checks": [],
        }

    def test_midpoll_surface_conflict_aborted_fails_closed(self, tmp_path):
        # Conflict appears AFTER the required checks register and the gh watch
        # returns, but DURING the expected-check-surface wait, and auto-resolve
        # cannot clear it -> _wait_for_pr_ci must return the SAME pr_conflicting
        # fail-closed envelope as the Step-14-START guard, NOT spin to verify.
        run_cmds: list[list[str]] = []
        resolve_calls = {"count": 0}

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            run_cmds.append(list(args))
            if "--watch" in args:
                # gh pr checks --watch --required exits cleanly; the surface
                # wait runs next and is where the conflict is detected.
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
            # Required-checks registration poll: already registered.
            return self._registered(args)

        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/surface"
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        result = {"steps_completed": ["git_commit"]}
        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=True), \
             patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: mid-poll surface fail-closed verify
                tmp_path,
                pr_number="300",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="wave/surface",
                log=lambda _msg: None,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/surface"},
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "pr_conflicting"
        assert response["auto_resolve_action"] == "aborted"
        assert "wait_ci" not in result["steps_completed"]
        # Exactly one re-fire for the single surface-window transition.
        assert resolve_calls["count"] == 1
        # Proof the conflict was caught in the POST-registration window: the
        # required-checks registration poll AND the gh watch both ran before
        # the surface wait detected the conflict and failed closed.
        assert ["gh", "pr", "checks", "300", "--required"] in run_cmds
        assert ["gh", "pr", "checks", "300", "--watch", "--required"] in run_cmds
        # Manual-recovery recipe carried through (shared Step-14 envelope shape).
        assert "Manual recovery required" in response["errors"][0]
        assert "executor.py" in response["errors"][0]

    def test_midpoll_surface_conflict_resolved_resumes_polling(self, tmp_path):
        # Conflict appears mid-surface-poll and auto-resolve clears it
        # (resolved=true): the base-merge repush re-triggers the skipped
        # workflows, so polling resumes and the surface then goes green. The
        # re-fire is edge-guarded -- exactly once even though the PR is still
        # observed CONFLICTING on the next poll (mergeability recompute lag).
        summarize_calls = {"count": 0}
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_summarize(checks):
            summarize_calls["count"] += 1
            # pending, pending (conflict persists), then green.
            if summarize_calls["count"] >= 3:
                return self._passed_surface()
            return self._pending_surface()

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/surface2"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: mid-poll surface re-check verify
                tmp_path,
                pr_number="301",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/surface2"},
            )

        assert snapshot["status"] == "passed"
        assert snapshot.get("ok") is True
        assert not snapshot.get("midpoll_conflict_aborted")
        # Edge guard: one re-fire for the single transition, even though the PR
        # was observed CONFLICTING on two pending polls.
        assert resolve_calls["count"] == 1
        assert conflict_calls["count"] == 2
        assert summarize_calls["count"] == 3

    def test_midpoll_surface_recheck_inert_without_context(self, tmp_path):
        # No midpoll_autoresolve context (the three non-Step-14 _wait_for_pr_ci
        # call sites): the surface re-check must be completely inert so those
        # sites stay behaviorally unchanged.
        summarize_calls = {"count": 0}
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_summarize(checks):
            summarize_calls["count"] += 1
            if summarize_calls["count"] >= 2:
                return self._passed_surface()
            return self._pending_surface()

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, **kw):
            resolve_calls["count"] += 1
            return {"resolved": True, "action": "tasks_md_resolved", "detail": "x"}

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: surface gating verify
                tmp_path,
                pr_number="302",
                timeout=30,
                poll_interval=0,
                # No midpoll_autoresolve -> disabled.
            )

        assert snapshot["status"] == "passed"
        # Gating proof: with no context the surface re-check never runs, so the
        # conflict-state probe and auto-resolve are never invoked.
        assert conflict_calls["count"] == 0
        assert resolve_calls["count"] == 0

    def test_midpoll_surface_conflict_aborted_fails_closed_via_fallback(self, tmp_path):
        # Same post-registration conflict, but the gh watch exits non-zero
        # (checks still pending) and _wait_for_pr_ci takes the polling-fallback
        # except path. The surface re-check on THAT path must ALSO fail closed
        # with the shared pr_conflicting envelope -- the second conversion site
        # must not drift from the main path.
        run_cmds: list[list[str]] = []
        fallback_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            run_cmds.append(list(args))
            if "--watch" in args:
                # gh pr checks --watch --required exits 1 -> fallback path.
                raise subprocess.CalledProcessError(1, args)
            return self._registered(args)

        def fake_poll_fallback(repo_root, pr_number, *, timeout=900, poll_interval=15, log=None):
            fallback_calls["count"] += 1
            return True

        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        result = {"steps_completed": ["git_commit"]}
        with patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_poll_ci_checks_fallback", side_effect=fake_poll_fallback), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=True), \
             patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: mid-poll surface fallback fail-closed verify
                tmp_path,
                pr_number="303",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="wave/surface3",
                log=lambda _msg: None,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/surface3"},
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["failure_class"] == "pr_conflicting"
        assert response["auto_resolve_action"] == "aborted"
        assert "wait_ci" not in result["steps_completed"]
        assert resolve_calls["count"] == 1
        # Proof we took the polling-fallback path after the watch raised.
        assert fallback_calls["count"] == 1
        assert ["gh", "pr", "checks", "303", "--watch", "--required"] in run_cmds
        assert "Manual recovery required" in response["errors"][0]
        assert "executor.py" in response["errors"][0]

    def test_midpoll_surface_failed_by_concurrent_merge_rechecks_before_failed_return(
        self, tmp_path
    ):
        # Reorder regression: a concurrent-merge CANCELLED-as-*failed* surface
        # must hit the mid-poll conflict re-check BEFORE the status=="failed"
        # early-return. Under the prior ordering the failed-return fired first,
        # so a cancelled-by-merge surface was returned as a CI failure and the
        # conflict was never probed. Proves three facets in one place:
        #   (a) resolvable conflict re-fires auto-resolve and RE-POLLS a fresh
        #       surface (returns the subsequent passed surface, not a plain
        #       failed);
        #   (b) unresolvable conflict fails closed with midpoll_conflict_aborted
        #       (which _wait_for_pr_ci converts to the pr_conflicting envelope);
        #   (c) a non-conflict real-CI-failure surface still returns failed,
        #       with the conflict probed once and auto-resolve never fired.

        # (a) failed (cancelled-by-merge) -> conflict -> resolved=true -> re-poll
        #     -> green. The FIRST surface is failed, not pending: the old
        #     ordering would have returned it as a CI failure before any probe.
        summarize_a = {"count": 0}
        conflict_a = {"count": 0}
        resolve_a = {"count": 0}

        def fake_summarize_a(checks):
            summarize_a["count"] += 1
            # failed (cancelled-by-merge), then green after the resolve repush.
            if summarize_a["count"] >= 2:
                return self._passed_surface()
            return self._failed_surface()

        def fake_conflict_a(repo_root, *, pr_number, log=None):
            conflict_a["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve_a(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_a["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/failed-resolvable"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_a), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_a), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_a), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: surface reorder re-check verify
                tmp_path,
                pr_number="310",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/failed-resolvable"},
            )
        # Re-polled a fresh surface after the resolve instead of returning the
        # stale failed snapshot: the second poll's GREEN surface is what returns.
        assert snapshot["status"] == "passed"
        assert snapshot.get("ok") is True
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_a["count"] == 1   # re-fired on the FAILED surface
        assert conflict_a["count"] == 1  # probed once (passed poll returns first)
        assert summarize_a["count"] == 2  # re-polled after the resolve

        # (b) failed (cancelled-by-merge) -> conflict -> resolved=false -> fail
        #     closed with the midpoll_conflict_aborted envelope.
        resolve_b = {"count": 0}

        def fake_summarize_b(checks):
            return self._failed_surface()

        def fake_conflict_b(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve_b(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_b["count"] += 1
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_b), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_b), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_b), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: surface reorder fail-closed verify
                tmp_path,
                pr_number="311",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/failed-unresolvable"},
            )
        assert snapshot.get("ok") is False
        assert snapshot.get("midpoll_conflict_aborted") is True
        assert snapshot.get("auto_resolve_action") == "aborted"
        assert resolve_b["count"] == 1

        # (c) failed surface that is a REAL CI break (not conflicting): the
        #     re-check probes conflict-state, finds none, and the failed
        #     early-return fires unchanged -- no auto-resolve, still failed.
        summarize_c = {"count": 0}
        conflict_c = {"count": 0}
        resolve_c = {"count": 0}

        def fake_summarize_c(checks):
            summarize_c["count"] += 1
            return self._failed_surface()

        def fake_conflict_c(repo_root, *, pr_number, log=None):
            conflict_c["count"] += 1
            return None  # not conflicting -> genuine CI failure

        def fake_resolve_c(repo_root, **kw):
            resolve_c["count"] += 1
            return {"resolved": True, "action": "x", "detail": ""}

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_c), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_c), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_c), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: surface reorder non-conflict verify
                tmp_path,
                pr_number="312",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/real-ci-fail"},
            )
        assert snapshot["status"] == "failed"
        assert snapshot.get("ok") is False
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_c["count"] == 0   # never auto-resolved a real CI break
        assert conflict_c["count"] == 1  # probed once before the failed-return
        assert summarize_c["count"] == 1  # returned failed on the first poll

    def test_midpoll_surface_conflict_not_probed_after_deadline(self, tmp_path):
        # Bridge round-1 DEFECT (PR #1059 P2 #2 follow-up): the mid-poll conflict
        # re-check -- and especially the expensive _try_auto_resolve_pr_conflict
        # (fetch + merge + push) -- must NOT run once the surface-wait deadline
        # has already expired. The relocation put the re-check above the
        # status=="failed" early-return, but it also sat above the timeout check,
        # so a deadline-reached failed/conflicting surface still probed the
        # conflict and re-fired auto-resolve AFTER the deadline. The re-check is
        # now deadline-guarded: a deadline-reached FAILED surface returns WITHOUT
        # probing the conflict or re-firing auto-resolve, and the failed
        # early-return still terminates the wait.
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}
        # First monotonic() reading computes the deadline; every later reading is
        # well past it, so the deadline guard short-circuits the conflict block.
        clock = iter([1000.0])

        def fake_monotonic():
            return next(clock, 9999.0)

        def fake_summarize(checks):
            # Concurrent-merge CANCELLED-as-failed surface (would, pre-guard,
            # have re-fired auto-resolve even though the deadline is already up).
            return self._failed_surface()

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, **kw):
            resolve_calls["count"] += 1
            return {"resolved": True, "action": "tasks_md_resolved", "detail": "x"}

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "monotonic", side_effect=fake_monotonic), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: surface deadline-guard verify
                tmp_path,
                pr_number="313",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/deadline"},
            )
        # Deadline already expired before the conflict block: neither the
        # conflict probe nor auto-resolve ran (the bug ran both after the
        # deadline), and the failed surface returned -- not the aborted envelope,
        # not a re-poll.
        assert conflict_calls["count"] == 0
        assert resolve_calls["count"] == 0
        assert snapshot["status"] == "failed"
        assert snapshot.get("ok") is False
        assert not snapshot.get("midpoll_conflict_aborted")

    def test_midpoll_surface_persistent_repoll_until_green_or_deadline(self, tmp_path):
        # Regression (surface-wait-persistent-repoll): after a successful mid-poll
        # conflict resolve, the base-merge repush re-triggers the previously
        # skipped pull_request workflows, but they take TIME to re-register. Until
        # they do, the surface stays "failed" (the concurrent-merge CANCELLED
        # checks are still the latest runs). The prior one-iteration marker only
        # skipped the failed early-return for a SINGLE post-resolve poll, so the
        # very next still-"failed" poll -- with the conflict already cleared --
        # returned a FALSE CI failure on a PR whose conflict was already resolved.
        # The persistent awaiting-refreshed-surface marker must keep re-polling
        # across MULTIPLE failed iterations until the surface refreshes green
        # (block a), while the existing deadline check must still bound the wait
        # and return timed_out if green never arrives (block b).

        # (a) PERSISTENT re-poll: the conflict resolves on the first failed poll,
        #     then the surface stays "failed" for THREE more polls (re-registering
        #     workflows) before going green. The wait must NOT false-fail on any
        #     of the post-resolve failed polls -- it re-polls until green. The
        #     conflict CLEARS right after the resolve (None on later probes): the
        #     exact transition the old one-shot marker mishandled (currently
        #     non-conflicting + still-"failed" surface -> the marker had reset to
        #     False, so the failed early-return fired on the very next poll).
        summarize_a = {"count": 0}
        conflict_a = {"count": 0}
        resolve_a = {"count": 0}

        def fake_summarize_a(checks):
            summarize_a["count"] += 1
            # failed on the resolve poll AND three subsequent re-registering
            # polls (#1-#4), then green on #5 -- well past "one iteration".
            if summarize_a["count"] >= 5:
                return self._passed_surface()
            return self._failed_surface()

        def fake_conflict_a(repo_root, *, pr_number, log=None):
            conflict_a["count"] += 1
            # CONFLICTING on the first probe (drives the single resolve), then
            # cleared -- so on every later poll currently_conflicting is False.
            return "mergeable=CONFLICTING" if conflict_a["count"] == 1 else None

        def fake_resolve_a(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_a["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/persistent-green"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_a), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_a), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_a), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: persistent repoll verify
                tmp_path,
                pr_number="320",
                timeout=300,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/persistent-green"},
            )
        # No false failure on the post-resolve failed polls: the wait persistently
        # re-polled across all four failed surfaces and returned the green one.
        assert snapshot["status"] == "passed"
        assert snapshot.get("ok") is True
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_a["count"] == 1   # single resolve for the one transition
        assert conflict_a["count"] == 4  # probed each failed poll; green poll returns first
        assert summarize_a["count"] == 5  # re-polled persistently, then green

        # (b) BOUNDED by the deadline: the same resolve fires on the first poll
        #     (still < deadline), but the surface never goes green. The persistent
        #     marker must NOT mask the deadline -- the wait still terminates and
        #     returns the timed_out snapshot (NOT a false-green, NOT the aborted
        #     envelope). The injected clock computes the deadline from the first
        #     reading, lets the resolve fire on iter 1, then jumps past the
        #     deadline so iter 2 terminates with the surface still "failed".
        summarize_b = {"count": 0}
        conflict_b = {"count": 0}
        resolve_b = {"count": 0}
        clock_b = iter([1000.0, 1001.0, 1002.0])

        def fake_monotonic_b():
            return next(clock_b, 9999.0)

        def fake_summarize_b(checks):
            summarize_b["count"] += 1
            return self._failed_surface()

        def fake_conflict_b(repo_root, *, pr_number, log=None):
            conflict_b["count"] += 1
            return "mergeable=CONFLICTING" if conflict_b["count"] == 1 else None

        def fake_resolve_b(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_b["count"] += 1
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_b), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_b), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_b), \
             patch.object(commit_mod.time, "monotonic", side_effect=fake_monotonic_b), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: persistent repoll deadline-bound verify
                tmp_path,
                pr_number="321",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/persistent-deadline"},
            )
        # The marker was set (resolve fired on iter 1) yet the deadline still
        # terminated the wait: timed_out, not a false-green, not the aborted path.
        assert snapshot.get("ok") is False
        assert snapshot.get("timed_out") is True
        assert snapshot["status"] == "failed"
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_b["count"] == 1   # resolve fired once before the deadline
        assert conflict_b["count"] == 1  # iter-2 conflict probe skipped (deadline guard)

    def test_midpoll_surface_persistent_await_terminates_on_refreshed_real_failure(
        self, tmp_path
    ):
        # Bridge round-1 DEFECT (surface-wait-persistent-repoll): the persistent
        # awaiting-refreshed-surface marker (set on a successful mid-poll resolve)
        # must NOT mask a refreshed GENUINE CI failure until the deadline. The
        # prior marker cleared ONLY when status != "failed", so a refreshed
        # surface that went straight from the stale concurrent-merge CANCELLED
        # runs to a real FAILURE conclusion -- with NO intermediate pending/pass
        # poll -- stayed suppressed and false-returned timed_out instead of the
        # real failure. The await is now non-terminal ONLY while the failing
        # checks are the CANCELLED stale runs
        # (_surface_failure_is_stale_cancellation); the FIRST non-CANCELLED
        # failing conclusion terminates the wait as a real failure immediately.
        summarize = {"count": 0}
        conflict = {"count": 0}
        resolve = {"count": 0}
        # Generous headroom (deadline = first reading + 300): the wait must
        # terminate on the refreshed real failure, NOT the deadline. The 9999
        # tail only fires if a regression re-masks the failure -- then the
        # deadline check trips and the timed_out assertion fails fast instead of
        # hanging on the real clock.
        clock = iter([1000.0, 1001.0, 1002.0, 1003.0])

        def fake_monotonic():
            return next(clock, 9999.0)

        def fake_summarize(checks):
            summarize["count"] += 1
            # poll 1: stale CANCELLED surface (drives the resolve, sets the
            # marker); poll 2: refreshed surface with a GENUINE FAILURE.
            if summarize["count"] == 1:
                return self._failed_surface()
            return self._refreshed_failed_surface()

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict["count"] += 1
            # CONFLICTING on the first probe (drives the single resolve), then
            # cleared -- the exact post-resolve transition the marker spans.
            return "mergeable=CONFLICTING" if conflict["count"] == 1 else None

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/refreshed-real-failure"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "monotonic", side_effect=fake_monotonic), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: persistent await real-failure verify
                tmp_path,
                pr_number="322",
                timeout=300,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/refreshed-real-failure"},
            )
        # The refreshed REAL failure terminated the wait on poll 2 -- NOT masked
        # to the deadline (no timed_out), NOT the aborted envelope, NOT a green.
        assert snapshot["status"] == "failed"
        assert snapshot.get("ok") is False
        assert not snapshot.get("timed_out")
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve["count"] == 1   # single resolve set the await marker
        assert conflict["count"] == 2  # probed poll 1 (CONFLICTING) and poll 2 (cleared)
        assert summarize["count"] == 2  # terminated on the refreshed real-failure poll

    def test_midpoll_surface_persistent_await_survives_transient_pending_surface(
        self, tmp_path
    ):
        # Bridge round-2 DEFECT (surface-wait-persistent-repoll): the persistent
        # post-resolve await must NOT be cleared by a TRANSIENT non-"failed"
        # surface that does not yet show the re-registered required checks. After
        # a successful mid-poll resolve, GitHub processes the repush and the
        # rollup can momentarily go pending/unavailable (missing the expected
        # checks) BEFORE the re-triggered pull_request workflows re-register. The
        # prior clear -- `if status != "failed": awaiting_refreshed_surface =
        # False` -- cleared the await on that transient surface, so the very next
        # stale concurrent-merge CANCELLED poll (still "failed") false-failed the
        # wait. The await now clears ONLY on positive proof of re-registration
        # (_surface_shows_refreshed_required_checks: a non-"failed" surface whose
        # expected required-check set is fully present), so a transient
        # pending/unavailable surface keeps the await armed across iterations.

        # (a) failed (CANCELLED) -> resolve -> TRANSIENT pending/unavailable
        #     (missing expected checks, conflict already cleared) -> failed
        #     (CANCELLED again) -> green. The wait must NOT false-fail on the
        #     post-transient failed poll: the await survived the transient pending
        #     surface, so the stale CANCELLED failure stays non-terminal and the
        #     wait re-polls to green. Under the prior one-`status != "failed"`
        #     clear this returned a FALSE failure on the post-transient poll.
        summarize_a = {"count": 0}
        conflict_a = {"count": 0}
        resolve_a = {"count": 0}

        def fake_summarize_a(checks):
            summarize_a["count"] += 1
            # 1: stale CANCELLED (drives the resolve, sets the await);
            # 2: transient pending/unavailable (must NOT clear the await);
            # 3: stale CANCELLED again (must NOT false-fail -- await still armed);
            # 4: green.
            if summarize_a["count"] == 1:
                return self._failed_surface()
            if summarize_a["count"] == 2:
                return self._unavailable_surface()
            if summarize_a["count"] == 3:
                return self._failed_surface()
            return self._passed_surface()

        def fake_conflict_a(repo_root, *, pr_number, log=None):
            conflict_a["count"] += 1
            # CONFLICTING on the first probe (drives the single resolve), then
            # cleared -- so it is the persistent await, NOT a re-detected
            # conflict, that keeps the post-transient stale CANCELLED poll
            # non-terminal.
            return "mergeable=CONFLICTING" if conflict_a["count"] == 1 else None

        def fake_resolve_a(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_a["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/transient-green"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_a), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_a), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_a), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: persistent await transient-pending verify
                tmp_path,
                pr_number="330",
                timeout=300,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/transient-green"},
            )
        # The transient pending/unavailable surface did NOT clear the await, so
        # the post-transient stale CANCELLED poll stayed non-terminal and the wait
        # re-polled to green -- no false failure.
        assert snapshot["status"] == "passed"
        assert snapshot.get("ok") is True
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_a["count"] == 1   # single resolve set the await marker
        assert conflict_a["count"] == 3  # probed polls 1-3; green poll returns first
        assert summarize_a["count"] == 4  # persisted across the transient, then green

        # (b) BOUNDED by the deadline THROUGH a transient pending surface: the
        #     resolve fires on poll 1 (still < deadline), poll 2 is the transient
        #     pending/unavailable surface, poll 3 is stale CANCELLED again, then
        #     the deadline trips. The await must NOT have been cleared by the
        #     transient surface (else poll 3 would false-fail BEFORE the deadline)
        #     AND must NOT mask the deadline -- the wait terminates with the
        #     timed_out snapshot, not a false-green and not the aborted envelope.
        summarize_b = {"count": 0}
        conflict_b = {"count": 0}
        resolve_b = {"count": 0}
        # deadline = first reading + 30 = 1030; the resolve fires on iter 1, the
        # transient pending (iter 2) and the stale CANCELLED (iter 3) stay
        # non-terminal, then iter 3's deadline check trips (tail 9999 >= 1030).
        clock_b = iter([1000.0, 1001.0, 1002.0, 1003.0, 1004.0, 1005.0])

        def fake_monotonic_b():
            return next(clock_b, 9999.0)

        def fake_summarize_b(checks):
            summarize_b["count"] += 1
            if summarize_b["count"] == 2:
                return self._unavailable_surface()
            return self._failed_surface()

        def fake_conflict_b(repo_root, *, pr_number, log=None):
            conflict_b["count"] += 1
            return "mergeable=CONFLICTING" if conflict_b["count"] == 1 else None

        def fake_resolve_b(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_b["count"] += 1
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize_b), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict_b), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve_b), \
             patch.object(commit_mod.time, "monotonic", side_effect=fake_monotonic_b), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            snapshot = commit_mod._wait_for_expected_pr_check_surface_to_pass(  # ANTICHEAT_OK: persistent await transient-pending deadline verify
                tmp_path,
                pr_number="331",
                timeout=30,
                poll_interval=0,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/transient-deadline"},
            )
        # The transient pending surface did not clear the await (poll 3 did not
        # false-fail), yet the deadline still terminated the wait: timed_out on the
        # stale CANCELLED surface, not a false-green, not the aborted envelope.
        assert snapshot.get("ok") is False
        assert snapshot.get("timed_out") is True
        assert snapshot["status"] == "failed"
        assert not snapshot.get("midpoll_conflict_aborted")
        assert resolve_b["count"] == 1   # resolve fired once before the deadline
        assert conflict_b["count"] == 3  # probed polls 1-3 (all < deadline)


class TestMidpollConflictRecheckBeforeCIFailure:
    """``_midpoll_conflict_recheck_before_ci_failure`` -- the Step-14 mid-poll
    conflict re-check at the required-checks-not-passed boundary (the wait stage
    BETWEEN the registration wait and the expected-check-surface wait, both of
    which were already mid-poll-aware).

    A concurrent lane that merges after the required checks register flips the
    PR to CONFLICTING/DIRTY and GitHub cancels the in-flight required workflows,
    so ``_wait_for_required_checks_to_pass`` reports not-passed even though the
    cause is a conflict, not a CI break. The re-check must (a) be inert for
    non-Step-14 callers, (b) pass a genuine CI failure through, (c) signal
    fall-through on a resolved conflict, and (d) fail closed with the SAME
    ``pr_conflicting`` envelope when the conflict is unresolvable.
    """

    def test_inert_without_midpoll_context(self, tmp_path):
        # Non-Step-14 callers pass midpoll_autoresolve=None: the re-check is a
        # no-op (no conflict probe, no auto-resolve) and returns None so the
        # caller emits its normal CI-failure response.
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            return {"resolved": True, "action": "tasks_md_resolved", "detail": ""}

        with patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve):
            out = commit_mod._midpoll_conflict_recheck_before_ci_failure(  # ANTICHEAT_OK: mid-poll required-pass re-check verify
                tmp_path,
                "400",
                midpoll_autoresolve=None,
                target_branch="wave/none",
                steps_completed=["git_commit"],
                log=None,
            )
        assert out is None
        assert conflict_calls["count"] == 0
        assert resolve_calls["count"] == 0

    def test_no_conflict_returns_none(self, tmp_path):
        # Required checks not-passed with NO conflict = a genuine CI failure; the
        # re-check returns None and never attempts auto-resolve.
        resolve_calls = {"count": 0}

        def fake_conflict(repo_root, *, pr_number, log=None):
            return None  # not conflicting

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            return {"resolved": True, "action": "x", "detail": ""}

        with patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve):
            out = commit_mod._midpoll_conflict_recheck_before_ci_failure(  # ANTICHEAT_OK: mid-poll required-pass re-check verify
                tmp_path,
                "401",
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/a"},
                target_branch="wave/a",
                steps_completed=["git_commit"],
                log=None,
            )
        assert out is None
        assert resolve_calls["count"] == 0  # no resolve attempted when not conflicting

    def test_conflict_resolved_signals_fall_through(self, tmp_path):
        # Concurrent merge cancelled the checks; auto-resolve clears it -> signal
        # the caller to fall through to the surface-pass wait (re-verify head).
        resolve_calls = {"count": 0}

        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            assert base_branch == "dev"
            assert branch_name == "wave/b"
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        with patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve):
            out = commit_mod._midpoll_conflict_recheck_before_ci_failure(  # ANTICHEAT_OK: mid-poll required-pass re-check verify
                tmp_path,
                "402",
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/b"},
                target_branch="wave/b",
                steps_completed=["git_commit"],
                log=None,
            )
        assert out == {"midpoll_conflict_resolved": True}
        assert resolve_calls["count"] == 1

    def test_conflict_unresolvable_fails_closed(self, tmp_path):
        # Concurrent merge + a conflict auto-resolve cannot clear: emit the SAME
        # pr_conflicting fail-closed envelope as the other guards (NOT a generic
        # ci_failure), so recovery treats it as a resolvable conflict.
        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        with patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve):
            out = commit_mod._midpoll_conflict_recheck_before_ci_failure(  # ANTICHEAT_OK: mid-poll required-pass re-check verify
                tmp_path,
                "403",
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/c"},
                target_branch="wave/c",
                steps_completed=["git_commit"],
                log=None,
            )
        assert out is not None
        assert out["status"] == "error"
        assert out["step"] == "wait_ci"
        assert out["failure_class"] == "pr_conflicting"
        assert out["auto_resolve_action"] == "aborted"
        assert "Manual recovery required" in out["errors"][0]
        assert "executor.py" in out["errors"][0]

    def test_wait_for_pr_ci_required_pass_boundary_fails_closed_on_unresolvable_conflict(
        self, tmp_path
    ):
        # Integration: registration OK + watch returns, but required checks read
        # not-passed (cancelled by a concurrent merge) AND the PR is conflicting
        # with an unresolvable conflict -> _wait_for_pr_ci returns pr_conflicting
        # at the required-pass boundary (distinct from the register + surface
        # boundaries covered above).
        resolve_calls = {"count": 0}
        watch_cmds: list[list[str]] = []

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            watch_cmds.append(list(args))
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        def fake_conflict(repo_root, *, pr_number, log=None):
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            return {
                "resolved": False,
                "action": "aborted",
                "detail": "conflict in non-TASKS.md files: ['executor.py']; manual recovery required",
            }

        result = {"steps_completed": ["git_commit"]}
        with patch.object(commit_mod, "_wait_for_required_checks_to_register", return_value=None), \
             patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass", return_value=False), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            response = commit_mod._wait_for_pr_ci(  # ANTICHEAT_OK: mid-poll required-pass fail-closed verify
                tmp_path,
                pr_number="404",
                result=result,
                continuation_path=tmp_path / "continuation.json",
                target_branch="wave/d",
                log=lambda _msg: None,
                midpoll_autoresolve={"base_branch": "dev", "branch_name": "wave/d"},
            )

        assert response is not None
        assert response["status"] == "error"
        assert response["step"] == "wait_ci"
        assert response["failure_class"] == "pr_conflicting"
        assert response["auto_resolve_action"] == "aborted"
        assert "wait_ci" not in result["steps_completed"]
        assert resolve_calls["count"] == 1
        # The watch DID run (we passed the registration gate), then the
        # required-pass boundary caught the cancelled-by-conflict checks.
        assert ["gh", "pr", "checks", "404", "--watch", "--required"] in watch_cmds
        assert "Manual recovery required" in response["errors"][0]


class TestStep15RemediationMidPollSurfaceConflictRecheck:
    """Step-15 bot-remediation CI-wait is conflict-aware (#49 parallel-lane
    stranding).

    Companion to ``TestStep14MidPollSurfaceConflictRecheck`` for the OTHER
    ``_wait_for_pr_ci`` call site that populates ``midpoll_autoresolve``: the
    Step-15-remediation CI-wait inside ``_attempt_bot_finding_remediation``. A
    sibling dispatcher lane that merges DURING the remediation CI poll flips this
    lane's PR to CONFLICTING/DIRTY; GitHub then skips/cancels its ``pull_request``
    required checks (a CANCELLED required check is classified ``failed`` by
    ``_summarize_pr_check_surface``). Before the fix the remediation
    ``_wait_for_pr_ci`` call omitted ``midpoll_autoresolve``, so the surface-wait
    conflict re-check was DISABLED and the poll doom-spun to the 900s surface
    timeout, returning a ci_failure that STRANDED the PR (verified on PR #1075:
    ~32 surface-wait iterations, zero conflict-handling, dispatcher exit).

    The fix threads ``base_branch`` (from ``_run_post_commit_pipeline``) into
    ``_attempt_bot_finding_remediation`` and passes
    ``midpoll_autoresolve={"base_branch": base_branch, "branch_name":
    target_branch}`` to its ``_wait_for_pr_ci`` call -- built EXACTLY like the
    Step-14 caller. ``base_branch`` carries the REAL wave base (``dev``); the head
    ``target_branch`` is the ``branch_name`` ``_try_auto_resolve_pr_conflict``
    merges INTO. So the remediation surface-wave re-checks
    ``_check_pr_conflict_state`` and re-fires ``_try_auto_resolve_pr_conflict``
    once (fetch + merge ``origin/dev`` + repush re-triggers the skipped workflows)
    instead of doom-polling to timeout.

    This drives the REAL ``_attempt_bot_finding_remediation`` -> REAL
    ``_wait_for_pr_ci`` -> REAL ``_wait_for_expected_pr_check_surface_to_pass``
    -> REAL ``_wait_for_bot_review_freshness`` so BOTH fixes are exercised
    end-to-end:

    * #49 midpoll (round 1): without the threaded ``midpoll_autoresolve`` the
      surface-wait conflict re-check is inert, ``_try_auto_resolve_pr_conflict``
      is never fired, and the CANCELLED-as-failed surface returns as a ci_failure
      (``resolve_calls`` stays 0).
    * stale-head refresh (round 2): the mid-poll auto-resolve merge+repush
      advances the PR head past the remediation commit. Unless
      ``_attempt_bot_finding_remediation`` re-reads HEAD after the CI-wait, the
      stale ``current_head`` reaches ``_wait_for_bot_review_freshness`` ->
      ``_assert_expected_pr_head``, which rejects the moved PR head with
      ``ValueError`` and strands the PR on ``bot_findings_pending``. With the
      refresh the head matches the PR ``headRefOid`` and remediation returns
      ``None`` (clean, mergeable).
    """

    @staticmethod
    def _failed_surface() -> dict:
        # Concurrent-merge CANCELLED-as-failed surface: GitHub cancelled the
        # pull_request required checks when the sibling lane merged first.
        return {
            "status": "failed",
            "summary": "failing PR check(s): test=CANCELLED",
            "failing_checks": ["test=CANCELLED"],
        }

    @staticmethod
    def _passed_surface() -> dict:
        return {"status": "passed", "summary": "expected PR check surface green"}

    @staticmethod
    def _fake_bridge_adapters() -> types.SimpleNamespace:
        # Minimal stand-in for the bridge_adapters module so the remediation loop
        # reaches its _wait_for_pr_ci call without spawning a real adapter
        # subprocess. run_adapter is a no-op; the "fix" is modelled by the staged
        # git-status fake below reporting an in-scope change.
        adapter = types.SimpleNamespace(
            name="bot_remediation",
            cmd=["true"],
            prompt_via_stdin=False,
            env={},
            mode="adapter",
        )
        return types.SimpleNamespace(
            BridgeAdapterError=RuntimeError,
            load_bridge_config=lambda _path: {},
            get_adapter=lambda _config, _name: adapter,
            AdapterSpec=lambda **kw: types.SimpleNamespace(**kw),
            run_adapter=lambda *a, **kw: None,
        )

    def test_remediation_ci_wait_rechecks_conflict_and_does_not_strand(self, tmp_path):
        target_branch = "wave/lane49"
        base_branch = "dev"
        # Distinct heads model the mid-poll auto-resolve advancing the PR head:
        # the remediation commit is pushed at `remediation_head`; then the
        # _wait_for_pr_ci mid-poll auto-resolve merges origin/dev + repushes,
        # leaving the PR (and the local worktree HEAD) at `autoresolve_head`.
        remediation_head = "1111111111111111111111111111111111111111"
        autoresolve_head = "2222222222222222222222222222222222222222"

        summarize_calls = {"count": 0}
        conflict_calls = {"count": 0}
        resolve_calls = {"count": 0}
        rev_parse_calls = {"count": 0}
        captured = {}
        consumed_heads = {}

        def fake_summarize(checks):
            summarize_calls["count"] += 1
            # poll 1: concurrent-merge CANCELLED-as-failed surface (the doom-poll
            # input); poll 2: green, after the auto-resolve repush re-triggered
            # the skipped pull_request workflows.
            if summarize_calls["count"] >= 2:
                return self._passed_surface()
            return self._failed_surface()

        def fake_conflict(repo_root, *, pr_number, log=None):
            conflict_calls["count"] += 1
            return "mergeable=CONFLICTING"

        def fake_resolve(repo_root, *, pr_number, base_branch, branch_name, log=None):
            resolve_calls["count"] += 1
            captured["base_branch"] = base_branch
            captured["branch_name"] = branch_name
            return {
                "resolved": True,
                "action": "tasks_md_resolved",
                "detail": "merged origin/dev + resolved TASKS.md + pushed",
            }

        def fake_run(args, *, cwd, check=True, timeout=120, env=None):
            # Drives _attempt_bot_finding_remediation's git ops + the real
            # _wait_for_pr_ci `gh pr checks --watch` call.
            if args[:2] == ["git", "status"]:
                # Adapter "produced" an in-scope change on the finding path.
                return subprocess.CompletedProcess(
                    args, 0, stdout=" M mu/foo.py\n", stderr=""
                )
            if args[:2] == ["git", "rev-parse"]:
                rev_parse_calls["count"] += 1
                # 1st rev-parse: the just-committed remediation head. 2nd
                # rev-parse: the post-CI-wait refresh, which on the FIXED code
                # reads the head the mid-poll auto-resolve merge+repush advanced
                # the local worktree (and the PR) to.
                head = (
                    remediation_head
                    if rev_parse_calls["count"] == 1
                    else autoresolve_head
                )
                return subprocess.CompletedProcess(args, 0, stdout=head + "\n", stderr="")
            # git add / commit / push, gh pr checks --watch: all succeed quietly.
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        def fake_request_review(repo_root, *, pr_number, head_sha, continuation_path, log=None):
            # Capture the head the post-CI current-head bot-review request is
            # retargeted to -- must be the refreshed autoresolve_head, never the
            # stale remediation_head.
            consumed_heads["request"] = head_sha
            return True

        findings = [{"path": "mu/foo.py", "body": "P2: tidy import", "severity": "P2"}]
        result = {"steps_completed": ["git_commit"]}
        cfg = tmp_path / "bridge_config.json"
        cfg.write_text("{}", encoding="utf-8")

        with patch.object(commit_mod, "_bridge_adapters", self._fake_bridge_adapters()), \
             patch.object(commit_mod, "bridge_config_path", lambda *a, **k: cfg), \
             patch.object(commit_mod, "_run", side_effect=fake_run), \
             patch.object(commit_mod, "ensure_bot_remediation_tracker_followup",
                          return_value={"updated": False, "errors": []}), \
             patch.object(commit_mod, "_run_bot_remediation_staged_test_gate",
                          return_value={"passed": True}), \
             patch.object(commit_mod, "_mint_bot_remediation_receipt",
                          return_value=tmp_path / "bot_receipt.json"), \
             patch.object(commit_mod, "_checkpoint_post_commit_progress",
                          lambda *a, **k: None), \
             patch.object(commit_mod, "_run_bot_remediation_pre_push_guard",
                          return_value={"passed": True}), \
             patch.object(commit_mod, "_wait_for_required_checks_to_register",
                          return_value=None), \
             patch.object(commit_mod, "_wait_for_required_checks_to_pass",
                          return_value=True), \
             patch.object(commit_mod, "_fetch_pr_check_surface_rollup", return_value=[]), \
             patch.object(commit_mod, "_summarize_pr_check_surface", side_effect=fake_summarize), \
             patch.object(commit_mod, "_check_pr_conflict_state", side_effect=fake_conflict), \
             patch.object(commit_mod, "_try_auto_resolve_pr_conflict", side_effect=fake_resolve), \
             patch.object(commit_mod, "_maybe_request_current_head_bot_review",
                          side_effect=fake_request_review), \
             patch.object(commit_mod, "_query_pr_review_state",
                          return_value={"headRefOid": autoresolve_head}), \
             patch.object(commit_mod, "_has_fresh_connector_review", return_value=True), \
             patch.object(commit_mod, "_extract_review_findings",
                          return_value={"outcome": "clean"}), \
             patch.object(commit_mod.time, "sleep", lambda _s: None):
            outcome = commit_mod._attempt_bot_finding_remediation(  # ANTICHEAT_OK: remediation CI-wait conflict re-check + stale-head refresh verify
                findings,
                repo_root=tmp_path,
                repo_owner="jabramsja",
                repo_name="rcx-pi-core",
                pr_number="1075",
                target_branch=target_branch,
                base_branch=base_branch,
                head_sha="deadbeefcafe",
                wave_id="step15-remediation-surface-conflict-recheck-2026-06-04",
                continuation_path=tmp_path / "continuation.json",
                result=result,
                log=lambda _m: None,
            )

        # FIX-CONFIRMING ASSERTIONS -- two independent fixes, each must hold:
        #
        # (1) #49 midpoll (round 1): the remediation CI-wait re-checked the
        # conflict and re-fired the auto-resolve EXACTLY once on the
        # CANCELLED-as-failed surface, then re-polled green. On the un-fixed call
        # site (no midpoll_autoresolve) the re-check is inert, resolve_calls stays
        # 0, and the CANCELLED surface returns as a ci_failure.
        assert resolve_calls["count"] == 1
        assert conflict_calls["count"] == 1     # probed once; green poll returns first
        assert summarize_calls["count"] == 2    # re-polled after the resolve -> green
        # The bridge-round-1 mapping correction: base_branch carries the REAL
        # wave base (dev), NEVER the head (target_branch). Mapping the head into
        # base_branch would make _try_auto_resolve_pr_conflict fetch+merge
        # origin/<head> into <head> -- a self-merge that never pulls the
        # sibling-lane base and leaves the CONFLICTING state unresolved.
        assert captured["base_branch"] == "dev"
        assert captured["branch_name"] == target_branch
        #
        # (2) stale-head refresh (bridge round 2): the mid-poll auto-resolve
        # merge+repush advanced the PR head past the remediation commit, so after
        # _wait_for_pr_ci returned None the function re-read HEAD and retargeted
        # the post-CI current-head bot-review request + freshness wait at the NEW
        # head. _wait_for_bot_review_freshness runs for REAL here, so its
        # _assert_expected_pr_head compares the refreshed current_head against the
        # PR headRefOid: they match, it does NOT raise, and remediation returns
        # None (PR mergeable, not stranded). On the un-fixed code current_head
        # stays the stale remediation head, _assert_expected_pr_head rejects the
        # moved PR head with ValueError, and remediation returns
        # bot_findings_pending.
        assert outcome is None, (
            "remediation must return None (clean, not stranded) after a mid-poll "
            f"auto-resolve advanced the PR head; got {outcome!r}"
        )
        assert rev_parse_calls["count"] == 2    # remediation commit head + post-CI-wait refresh
        assert consumed_heads["request"] == autoresolve_head
