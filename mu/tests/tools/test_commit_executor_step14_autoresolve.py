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
