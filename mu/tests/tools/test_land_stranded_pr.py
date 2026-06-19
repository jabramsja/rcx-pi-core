"""Tests for the stranded-PR landing op + the extended shared conflict helper.

Wave: stranded-pr-landing-op-2026-06-19. Closes the recurring
stranded-PR-behind-base treadmill — a committed PR that re-conflicts on the
shared ``TASKS.md`` / growth-cap files every time the base branch advances —
WITHOUT ``--admin``, force-merge, or hand-resolving review threads.

FAST + hermetic: temp dirs, mocked ``gh`` / ``git`` via ``subprocess.run``, no
network. Nothing is marked slow.

Proves (mapping to the locked packet's TESTS section):
  (a) the EXTENDED ``_try_auto_resolve_pr_conflict`` auto-resolves a TASKS.md
      tracker-note conflict (BOTH notes kept) AND a test_growth_caps.py CAP
      conflict (per-CAP BASE+UNION value covering the merged file count + UNION of
      inline comments), individually AND together — including the both-sides-add-
      distinct-files regression that the old MAX-of-totals logic stranded;
  (b) it FAILS CLOSED in BOTH dimensions — (i) FILENAME: a third, unknown file
      in the conflict set (with TASKS.md, and unknown-alone); (ii) CONTENT: a
      non-CAP/non-comment line inside test_growth_caps.py AND a non-tracker-note
      line inside TASKS.md each abort WITHOUT rewriting the file — so the
      filename subset is necessary but NOT sufficient;
  (c) the merge-phase path REUSES the existing Step 14-16 merge phase
      (``_run_post_commit_pipeline``) via injection, and NEVER passes ``--admin``;
  (d) the merge-phase RE-CONFLICT path — the shared helper as invoked by the
      Step-14 pre-CI gate / CI-wait midpoll / late merge retry — auto-resolves a
      growth-cap conflict arising AFTER bring-current;
  (e) the ENTRYPOINT resolves the PR head branch + OID (mocked ``gh``), checks
      out that exact head, and VERIFIES local HEAD matches the resolved head OID
      BEFORE bring-current — failing closed (shared helper NEVER invoked, no
      worktree mutated) when the head cannot be resolved OR local HEAD does not
      match.
"""

from __future__ import annotations

import inspect
import json
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit_mod = load_module(
    "commit_executor",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)

CONFLICTING_PAYLOAD = '{"mergeable":"CONFLICTING","mergeStateStatus":"DIRTY"}'
GROWTH_CAP_RELPATH = "mu/tests/docs/test_growth_caps.py"


def _gh(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=""
    )


def _write_receipt_chain(
    repo_root: Path,
    *,
    wave_id: str = "stranded-wave",
    target_branch: str = "wave/x",
    pr_number: str = "1107",
    commit_sha: str = "abc1234",
    **overrides,
) -> Path:
    """Drop an ACTIVE post-commit continuation record — the receipt-chain artifact
    the entrypoint's authority gate requires — into the executors bus the gate
    scans (``agent_bus_path(repo_root, None, "executors")``, the same resolution
    the gate uses with no active bus). Mirrors what the normal commit flow writes
    after a ``COMMIT_GO`` supervisor receipt + the commit. Returns the record path.
    """
    ex_dir = commit_mod.agent_bus_path(repo_root, None, "executors")
    ex_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": commit_mod.COMMIT_CONTINUATION_VERSION,
        "status": commit_mod.CONTINUATION_ACTIVE_STATUS,
        "handoff_sha": "h0",
        "target_branch": target_branch,
        "commit_sha": commit_sha,
        "receipt_decision": "COMMIT_GO",
        "steps_completed": ["git_commit"],
        "pr_number": pr_number,
    }
    payload.update(overrides)
    path = ex_dir / f"commit_executor_{wave_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_growth_cap_conflict(repo_root: Path, body: str) -> Path:
    cap_dir = repo_root / "mu" / "tests" / "docs"
    cap_dir.mkdir(parents=True, exist_ok=True)
    path = cap_dir / "test_growth_caps.py"
    path.write_text(body, encoding="utf-8")
    return path


def _parse_cap(text: str, name: str) -> int:
    """Extract the integer value of a resolved ``CAP_*`` assignment line."""
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(\d+)", text, re.MULTILINE)
    assert match is not None, f"{name} not found in resolved text:\n{text}"
    return int(match.group(1))


def _make_helper_fake_run(
    conflicted_relpaths: list[str],
    *,
    aborted: dict | None = None,
    commit_env: dict | None = None,
    added: list | None = None,
):
    """Mock subprocess.run for ``_try_auto_resolve_pr_conflict``: gh reports
    CONFLICTING, the base merge conflicts, ``git diff`` reports the supplied
    conflicted relpaths, and add/commit/push/abort succeed. The real resolvers
    run against the real on-disk files in the temp repo (hermetic)."""

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["gh", "pr", "view"]:
            return _gh(stdout=CONFLICTING_PAYLOAD)
        if cmd[:2] == ["git", "fetch"]:
            return _gh()
        if cmd[:3] == ["git", "merge", "--abort"]:
            if aborted is not None:
                aborted["flag"] = True
            return _gh()
        if cmd[:2] == ["git", "merge"] and cmd[2:3] == ["origin/dev"]:
            return _gh(returncode=1)  # conflict
        if cmd[:3] == ["git", "diff", "--name-only"]:
            return _gh(stdout="".join(f"{p}\n" for p in conflicted_relpaths))
        if cmd[:3] == ["git", "add", "--"]:
            if added is not None:
                added.append(list(cmd))
            return _gh()
        if cmd[:2] == ["git", "commit"]:
            if commit_env is not None:
                commit_env.update(kwargs.get("env") or {})
            return _gh()
        return _gh()

    return fake_run


# ───────────────────────── content-guard validator ──────────────────────────


class TestIsGrowthCapLineOnly:
    """The growth-cap content-level guard mirrors ``_is_tracker_note_only``."""

    def test_accepts_cap_assignment_with_inline_comment(self):
        assert commit_mod._is_growth_cap_line_only(  # ANTICHEAT_OK: validator verify
            ["CAP_TEST_FILES = 145  # +1 for test_x.py (wave)\n"]
        )

    def test_accepts_cap_assignment_without_comment(self):
        assert commit_mod._is_growth_cap_line_only(["CAP_TOOL_SCRIPTS = 55\n"])  # ANTICHEAT_OK: validator verify

    def test_accepts_comment_only_line(self):
        assert commit_mod._is_growth_cap_line_only(["# Per-wave caps from policy\n"])  # ANTICHEAT_OK: validator verify

    def test_accepts_blank_lines(self):
        assert commit_mod._is_growth_cap_line_only(["\n", "CAP_X = 1\n", "\n"])  # ANTICHEAT_OK: validator verify

    def test_accepts_empty_buffer(self):
        assert commit_mod._is_growth_cap_line_only([])  # ANTICHEAT_OK: validator verify

    def test_rejects_code_line(self):
        assert not commit_mod._is_growth_cap_line_only(["x = compute_count()\n"])  # ANTICHEAT_OK: validator verify

    def test_rejects_baseline_assignment(self):
        # A BASELINE_* change is a phase-boundary event, not mechanical.
        assert not commit_mod._is_growth_cap_line_only(["BASELINE_TEST_FILES = 190\n"])  # ANTICHEAT_OK: validator verify

    def test_rejects_prose(self):
        assert not commit_mod._is_growth_cap_line_only(["This is a random line.\n"])  # ANTICHEAT_OK: validator verify


# ───────────────────── increment-annotation file counter ─────────────────────


class TestAnnotationIncrement:
    """``annotation_increment`` (public seam over ``_annotation_increment``) —
    the ``+N`` file count an annotation carries.

    The crux of the base+union fix: a resolved CAP_* sums these over the UNIONed
    annotations so it covers every distinct file either side added.
    """

    def test_single_file_increment(self):
        assert commit_mod.annotation_increment(
            "+1 for test_x.py (wave, FOUNDER_OVERRIDE:w)"
        ) == 1

    def test_multi_file_increment(self):
        assert commit_mod.annotation_increment(
            "+3 for post-redteam engine-state/scheduler tests (wave)"
        ) == 3

    def test_leading_whitespace_tolerated(self):
        assert commit_mod.annotation_increment("  +2 for a.py; b.py") == 2

    def test_non_increment_note_counts_zero(self):
        # A bare policy remark contributes no file count (degrades to base).
        assert commit_mod.annotation_increment("base ann") == 0
        assert commit_mod.annotation_increment("") == 0


# ──────────────────── increment-annotation file identity ─────────────────────


class TestAnnotationIdentity:
    """``annotation_identity`` (public seam over ``_annotation_identity``) — the
    dedup KEY that makes the UNION count DISTINCT files. Same file annotated with
    different wording on the two sides ⇒ same identity ⇒ counted ONCE (the bridge
    round-1 over-count fix)."""

    def test_subject_is_the_file_dropping_provenance(self):
        # The trailing "( … )" provenance is NOT part of the identity.
        assert commit_mod.annotation_identity(
            "+1 for test_x.py (wave, FOUNDER_OVERRIDE:w)"
        ) == "test_x.py"

    def test_same_file_different_provenance_is_one_identity(self):
        # The crux: two waves/sides annotate the SAME file with DIFFERENT notes —
        # full strings differ, identity is equal, so the union counts it once.
        a = commit_mod.annotation_identity("+1 for test_shared.py (same-wave, note-a)")
        b = commit_mod.annotation_identity("+1 for test_shared.py (same-wave, note-b)")
        assert a == b == "test_shared.py"

    def test_distinct_files_are_distinct_identities(self):
        ident = commit_mod.annotation_identity
        assert ident("+1 for test_a.py (w)") != ident("+1 for test_b.py (w)")

    def test_no_provenance_paren_tolerated(self):
        assert commit_mod.annotation_identity("+1 for test_x.py") == "test_x.py"

    def test_multi_file_prose_subject_preserved(self):
        assert commit_mod.annotation_identity(
            "+3 for post-redteam engine-state/scheduler tests (wave)"
        ) == "post-redteam engine-state/scheduler tests"

    def test_non_increment_note_keys_on_full_text(self):
        # No leading "+N" ⇒ keep the whole note as its key, so distinct notes union.
        assert commit_mod.annotation_identity("base ann") == "base ann"


# ────────────────────── growth-cap resolver (pure file) ──────────────────────


class TestResolveGrowthCapsConflict:
    """``resolve_growth_caps_conflict`` (public seam over
    ``_resolve_growth_caps_conflict``) — per-CAP BASE+UNION value (covers the
    merged file count, not ``max(totals)``) + UNION of inline comments."""

    def test_no_conflict_returns_true_unchanged(self, tmp_path):
        path = tmp_path / "test_growth_caps.py"
        original = "CAP_TEST_FILES = 144  # +1 for a.py\nBASELINE = 190\n"
        path.write_text(original, encoding="utf-8")
        assert commit_mod.resolve_growth_caps_conflict(path) is True
        assert path.read_text(encoding="utf-8") == original

    def test_single_cap_base_union_value_union_comments_origin_first(self, tmp_path):
        # Append-only model: a common ancestor documented test_shared.py (base =
        # 145 - 2 documented = 143 on BOTH sides); HEAD then added test_b.py and
        # origin added test_a.py — DISTINCT files, both landing the cap at 145. The
        # merged tree carries shared + a + b, so the resolved cap must be base +
        # UNION = 143 + 3 = 146 (covers BOTH distinct files), NOT max(145,145)=145
        # (which would drop one of them — the undercount this fix closes).
        path = tmp_path / "test_growth_caps.py"
        path.write_text(
            "BASELINE_TEST_FILES = 190\n"
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145  # +1 for test_shared.py (shared-wave); +1 for test_b.py (wave-b)\n"
            "=======\n"
            "CAP_TEST_FILES = 145  # +1 for test_shared.py (shared-wave); +1 for test_a.py (wave-a)\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        assert commit_mod.resolve_growth_caps_conflict(path) is True
        resolved = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved and ">>>>>>>" not in resolved
        # base (143) + UNION of both sides' added files (3) — COVERS both distinct
        # files, above max(145, 145) = 145.
        assert _parse_cap(resolved, "CAP_TEST_FILES") == 146
        # UNION of inline annotations, origin (merged-first) before HEAD, deduped.
        assert resolved.index("+1 for test_a.py") < resolved.index("+1 for test_b.py")
        assert resolved.count("test_shared.py") == 1
        # Untouched surrounding content preserved.
        assert "BASELINE_TEST_FILES = 190" in resolved

    def test_same_file_different_provenance_counts_once(self, tmp_path):
        # Bridge round-1 finding-2 regression: BOTH sides added the SAME ONE file
        # (test_shared.py) but annotated it with DIFFERENT wording — the same wave
        # re-annotated on the two merge sides. The full annotation STRINGS differ,
        # but it is ONE file, so the cap must stay 145 (base 144 + union 1), NOT
        # 146. Deduping the union by full string (then summing +N) double-counted
        # the one file as +2 — the over-bump this fix closes. The kept annotation
        # is origin's (merged-first), and the file appears exactly once.
        path = tmp_path / "test_growth_caps.py"
        path.write_text(
            "BASELINE_TEST_FILES = 190\n"
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145  # +1 for test_shared.py (same-wave, note-b)\n"
            "=======\n"
            "CAP_TEST_FILES = 145  # +1 for test_shared.py (same-wave, note-a)\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        assert commit_mod.resolve_growth_caps_conflict(path) is True
        resolved = path.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved and ">>>>>>>" not in resolved
        # ONE file ⇒ 145, never the 146 the full-string-deduped sum produced.
        assert _parse_cap(resolved, "CAP_TEST_FILES") == 145
        assert "146" not in resolved
        # The file is recorded exactly once (origin's note-a kept, merged-first).
        assert resolved.count("test_shared.py") == 1
        assert "note-a" in resolved and "note-b" not in resolved

    def test_multiple_caps_in_one_block_per_name_base_union(self, tmp_path):
        # Two caps in one block, each resolved INDEPENDENTLY to base+union, with
        # DIFFERENT shapes. CAP_TEST_FILES: both sides added a distinct file (145
        # each ⇒ base 144 ⇒ 144+2 = 146). CAP_TOOL_SCRIPTS: only HEAD bumped (+1 for
        # tool_b.sh over the shared base 54); origin kept the ancestor value 54 with
        # no annotation (base 54) ⇒ 54+1 = 55 = HEAD's value (the one tool it added).
        path = tmp_path / "test_growth_caps.py"
        path.write_text(
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145  # +1 for test_b.py (wave-b)\n"
            "CAP_TOOL_SCRIPTS = 55  # +1 for tool_b.sh (wave-b)\n"
            "=======\n"
            "CAP_TEST_FILES = 145  # +1 for test_a.py (wave-a)\n"
            "CAP_TOOL_SCRIPTS = 54\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        assert commit_mod.resolve_growth_caps_conflict(path) is True
        resolved = path.read_text(encoding="utf-8")
        assert _parse_cap(resolved, "CAP_TEST_FILES") == 146  # base 144 + union 2
        assert _parse_cap(resolved, "CAP_TOOL_SCRIPTS") == 55  # base 54 + union 1
        assert "+1 for test_a.py" in resolved and "+1 for test_b.py" in resolved
        assert "+1 for tool_b.sh" in resolved

    def test_rejects_semantic_line_unmodified(self, tmp_path):
        path = tmp_path / "test_growth_caps.py"
        original = (
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145\n"
            "config = rebuild_everything()\n"  # non-CAP/non-comment semantic line
            "=======\n"
            "CAP_TEST_FILES = 146\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(original, encoding="utf-8")
        assert commit_mod.resolve_growth_caps_conflict(path) is False
        assert path.read_text(encoding="utf-8") == original  # UNMODIFIED

    def test_rejects_baseline_change_unmodified(self, tmp_path):
        path = tmp_path / "test_growth_caps.py"
        original = (
            "<<<<<<< HEAD\n"
            "BASELINE_TEST_FILES = 191\n"
            "=======\n"
            "BASELINE_TEST_FILES = 190\n"
            ">>>>>>> origin/dev\n"
        )
        path.write_text(original, encoding="utf-8")
        assert commit_mod.resolve_growth_caps_conflict(path) is False
        assert path.read_text(encoding="utf-8") == original

    def test_rejects_nested_markers(self, tmp_path):
        path = tmp_path / "test_growth_caps.py"
        path.write_text(
            "<<<<<<< HEAD\n"
            "<<<<<<< HEAD\n"
            "CAP_X = 1\n"
            "=======\n"
            "CAP_X = 2\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        assert commit_mod.resolve_growth_caps_conflict(path) is False

    def test_rejects_dangling_marker(self, tmp_path):
        path = tmp_path / "test_growth_caps.py"
        path.write_text("<<<<<<< HEAD\nCAP_X = 1\n", encoding="utf-8")
        assert commit_mod.resolve_growth_caps_conflict(path) is False


# ───────────── shared helper end-to-end: (a) resolve + (b) fail-closed ────────


class TestSharedHelperKnownMechanicalConflicts:
    """(a)/(b): the EXTENDED ``_try_auto_resolve_pr_conflict`` two-layer gate.

    Bring-current reuses this same helper, so these cases cover it directly.
    """

    def _resolve(self, tmp_path, conflicted, **kw):
        return commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: helper verify
            tmp_path,
            pr_number="1107",
            base_branch="dev",
            branch_name="wave/stranded",
            log=None,
        )

    # (a) ── growth-cap alone ────────────────────────────────────────────────
    def test_resolves_growth_cap_conflict_alone(self, tmp_path):
        # Both sides landed the cap at 145 but added DISTINCT files (base 144 each)
        # ⇒ base+union resolves to 146, COVERING both — where the old max(145,145)
        # = 145 would drop one file and strand the bring-current commit.
        cap = _write_growth_cap_conflict(
            tmp_path,
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145  # +1 for test_b.py (wave-b)\n"
            "=======\n"
            "CAP_TEST_FILES = 145  # +1 for test_a.py (wave-a)\n"
            ">>>>>>> origin/dev\n",
        )
        fake = _make_helper_fake_run([GROWTH_CAP_RELPATH])
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, [GROWTH_CAP_RELPATH])
        assert result["resolved"] is True
        assert result["action"] == "mechanical_conflict_resolved"
        resolved = cap.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved
        assert _parse_cap(resolved, "CAP_TEST_FILES") == 146  # base 144 + union 2
        assert "+1 for test_a.py" in resolved and "+1 for test_b.py" in resolved
        assert resolved.index("+1 for test_a.py") < resolved.index("+1 for test_b.py")

    # (a) ── REGRESSION: both sides add DISTINCT files ⇒ base+union COVERS the
    #        merged count where max-of-totals UNDERCOUNTS (the confirmed #1107
    #        bring-current strand). ──────────────────────────────────────────────
    def test_both_sides_add_distinct_files_resolves_to_covering_union(self, tmp_path):
        # Faithful model of landing PR #1107: HEAD (the stranded PR) added the
        # pager test (+1 over the shared base 142); origin/dev added 3 DISTINCT
        # structural-numbers tests (+3). After merging dev the worktree carries
        # BOTH sets, so the cap must cover base + UNION = 142 + (1 + 3) = 146 test
        # files above baseline 190 — i.e. 336. max(143, 145) = 145 ⇒ 190 + 145 =
        # 335 ⇒ the growth-cap gate's `assert 336 <= 335` fails ⇒ the bring-current
        # `git commit` exits 1 ⇒ the op is stranded (the bug). The CAP_TOOL_SCRIPTS
        # conflict models the same shape: each side added a DISTINCT tool script
        # (+1 each over a shared base 53) ⇒ 53 + 2 = 55 where max(54, 54) = 54.
        cap = _write_growth_cap_conflict(
            tmp_path,
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 143  # +1 for test_pager.py (pager-wave)\n"
            "CAP_TOOL_SCRIPTS = 54  # +1 for tool_head.sh (head-wave)\n"
            "=======\n"
            "CAP_TEST_FILES = 145  # +1 for test_sn_add.py (sn-add); "
            "+1 for test_sn_mul.py (sn-mul); +1 for test_sn_sub.py (sn-sub)\n"
            "CAP_TOOL_SCRIPTS = 54  # +1 for tool_origin.py (origin-wave)\n"
            ">>>>>>> origin/dev\n",
        )
        fake = _make_helper_fake_run([GROWTH_CAP_RELPATH])
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, [GROWTH_CAP_RELPATH])
        assert result["resolved"] is True
        assert result["action"] == "mechanical_conflict_resolved"
        resolved = cap.read_text(encoding="utf-8")
        assert "<<<<<<<" not in resolved and ">>>>>>>" not in resolved
        test_cap = _parse_cap(resolved, "CAP_TEST_FILES")
        tool_cap = _parse_cap(resolved, "CAP_TOOL_SCRIPTS")
        # base+union, NOT max-of-totals.
        assert test_cap == 146, f"CAP_TEST_FILES resolved {test_cap}, want base+union 146"
        assert tool_cap == 55, f"CAP_TOOL_SCRIPTS resolved {tool_cap}, want base+union 55"
        # UNION of every side's inline annotation preserved — no file dropped.
        for fname in (
            "test_pager.py", "test_sn_add.py", "test_sn_mul.py", "test_sn_sub.py"
        ):
            assert fname in resolved, fname
        for tool in ("tool_head.sh", "tool_origin.py"):
            assert tool in resolved, tool
        # The resolved caps PASS the growth-cap gate for the merged tree, where
        # max-of-totals would FAIL it. Mirrors test_growth_caps.py's
        # `assert count <= BASELINE + CAP`; 190 / 68 are the #1107-era baselines.
        baseline_tests, merged_test_count = 190, 336
        baseline_tools, merged_tool_count = 68, 68 + 55
        assert merged_test_count <= baseline_tests + test_cap  # base+union PASSES
        assert baseline_tests + max(143, 145) < merged_test_count  # max-of-totals FAILS
        assert merged_tool_count <= baseline_tools + tool_cap
        assert baseline_tools + max(54, 54) < merged_tool_count

    # (a) ── TASKS.md alone (both notes kept) ─────────────────────────────────
    def test_resolves_tasks_md_conflict_alone_keeps_both(self, tmp_path):
        (tmp_path / "TASKS.md").write_text(
            "<<<<<<< HEAD\n"
            "- Tracker sync note (head-wave): ok.\n"
            "=======\n"
            "- Tracker sync note (origin-wave): ok.\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        commit_env: dict = {}
        fake = _make_helper_fake_run(["TASKS.md"], commit_env=commit_env)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, ["TASKS.md"])
        assert result["resolved"] is True
        # Pre-existing action label preserved (existing Step-14 contract green).
        assert result["action"] == "tasks_md_resolved"
        assert commit_env.get("RCX_SKIP_RECEIPT_CHECK") == "1"
        resolved = (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        assert "origin-wave" in resolved and "head-wave" in resolved
        assert resolved.index("origin-wave") < resolved.index("head-wave")

    # (a) ── BOTH together ────────────────────────────────────────────────────
    def test_resolves_tasks_md_and_growth_cap_together(self, tmp_path):
        (tmp_path / "TASKS.md").write_text(
            "<<<<<<< HEAD\n"
            "- Tracker sync note (head-wave): ok.\n"
            "=======\n"
            "- Tracker sync note (origin-wave): ok.\n"
            ">>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        cap = _write_growth_cap_conflict(
            tmp_path,
            "<<<<<<< HEAD\nCAP_TEST_FILES = 145  # +1 for test_b.py (wave-b)\n"
            "=======\nCAP_TEST_FILES = 145  # +1 for test_a.py (wave-a)\n"
            ">>>>>>> origin/dev\n",
        )
        added: list = []
        fake = _make_helper_fake_run(["TASKS.md", GROWTH_CAP_RELPATH], added=added)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, ["TASKS.md", GROWTH_CAP_RELPATH])
        assert result["resolved"] is True
        assert result["action"] == "mechanical_conflict_resolved"
        # Both files staged in one add.
        assert added and "TASKS.md" in added[0] and GROWTH_CAP_RELPATH in added[0]
        assert "<<<<<<<" not in (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        # base 144 + union of both distinct files (2) = 146, covering both.
        assert _parse_cap(cap.read_text(encoding="utf-8"), "CAP_TEST_FILES") == 146

    # (b)(i) ── FILENAME GATE: third unknown file alongside TASKS.md ──────────
    def test_fails_closed_unknown_file_with_tasks_md(self, tmp_path):
        (tmp_path / "TASKS.md").write_text(
            "<<<<<<< HEAD\n- Tracker sync note (h): ok.\n=======\n"
            "- Tracker sync note (o): ok.\n>>>>>>> origin/dev\n",
            encoding="utf-8",
        )
        aborted: dict = {"flag": False}
        fake = _make_helper_fake_run(["TASKS.md", "rcx_pi/selfhost/core.py"], aborted=aborted)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, ["TASKS.md", "rcx_pi/selfhost/core.py"])
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert aborted["flag"] is True  # git merge --abort fired
        # Allowed file left untouched (helper aborted before any rewrite/stage).
        assert "<<<<<<<" in (tmp_path / "TASKS.md").read_text(encoding="utf-8")

    # (b)(i) ── FILENAME GATE: unknown file alone ─────────────────────────────
    def test_fails_closed_unknown_file_alone(self, tmp_path):
        aborted: dict = {"flag": False}
        fake = _make_helper_fake_run(["mu/host/js/core/bootstrap_core.js"], aborted=aborted)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, ["mu/host/js/core/bootstrap_core.js"])
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "non-TASKS.md" in result["detail"]
        assert aborted["flag"] is True

    # (b)(ii) ── CONTENT GUARD: semantic line inside test_growth_caps.py ──────
    def test_fails_closed_semantic_line_in_growth_cap(self, tmp_path):
        body = (
            "<<<<<<< HEAD\n"
            "CAP_TEST_FILES = 145\n"
            "danger = wipe_repo()\n"  # semantic, non-CAP/non-comment
            "=======\n"
            "CAP_TEST_FILES = 146\n"
            ">>>>>>> origin/dev\n"
        )
        cap = _write_growth_cap_conflict(tmp_path, body)
        aborted: dict = {"flag": False}
        fake = _make_helper_fake_run([GROWTH_CAP_RELPATH], aborted=aborted)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, [GROWTH_CAP_RELPATH])
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "non-CAP/non-comment" in result["detail"]
        assert aborted["flag"] is True
        # File UNMODIFIED — the filename subset alone never auto-resolves it.
        assert cap.read_text(encoding="utf-8") == body

    # (b)(ii) ── CONTENT GUARD: non-tracker-note line inside TASKS.md ─────────
    def test_fails_closed_non_tracker_note_in_tasks_md(self, tmp_path):
        body = (
            "<<<<<<< HEAD\n"
            "- Tracker sync note (ok): ok.\n"
            "=======\n"
            "Arbitrary prose that is not a tracker note.\n"
            ">>>>>>> origin/dev\n"
        )
        (tmp_path / "TASKS.md").write_text(body, encoding="utf-8")
        aborted: dict = {"flag": False}
        fake = _make_helper_fake_run(["TASKS.md"], aborted=aborted)
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = self._resolve(tmp_path, ["TASKS.md"])
        assert result["resolved"] is False
        assert result["action"] == "aborted"
        assert "tracker-note" in result["detail"]
        assert aborted["flag"] is True
        assert (tmp_path / "TASKS.md").read_text(encoding="utf-8") == body


# ─────────────── (c) merge-phase reuse + no --admin, (d) re-conflict ──────────


class TestMergePhaseReuseAndReConflict:
    def _precondition_fake_run(self, head="wave/x", oid="abc1234", calls=None):
        def fake_run(cmd, **kwargs):
            if calls is not None:
                calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout=f'{{"headRefName":"{head}","headRefOid":"{oid}"}}')
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout=head)
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout=oid)
            return _gh()

        return fake_run

    # (c) ── reuse the existing Step 14-16 merge phase via injection ──────────
    def test_land_stranded_reuses_post_commit_merge_phase(self, tmp_path):
        # Receipt-chain authority for the exact head is a precondition; without it
        # the entrypoint fails closed before bring-current (covered separately).
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234"
        )
        recorded: dict = {}
        helper_calls: list = []

        def spy_helper(repo_root, *, pr_number, base_branch, branch_name, log=None):
            helper_calls.append(branch_name)
            return {"resolved": True, "action": "no_action", "detail": "current"}

        def recorder_pcp(**kwargs):
            recorded.update(kwargs)
            return {
                "status": "success",
                "merge_sha": "deadbeefcafef00d",
                "steps_completed": list(kwargs["result"]["steps_completed"])
                + ["wait_ci", "ensure_review_clear_and_merge", "post_merge_cleanup"],
            }

        fake = self._precondition_fake_run(head="wave/x", oid="abc1234")
        with patch.object(commit_mod.subprocess, "run", side_effect=fake), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=spy_helper
        ), patch.object(
            commit_mod, "_run_post_commit_pipeline", side_effect=recorder_pcp
        ), patch.object(
            commit_mod, "_continuation_record_path", return_value=tmp_path / "cont.json"
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "success"
        # Bring-current happened on the verified head, exactly once.
        assert helper_calls == ["wave/x"]
        # The EXISTING merge phase was invoked (reuse, not reimplement) ...
        assert recorded["target_branch"] == "wave/x"
        assert recorded["base_branch"] == "dev"
        # ... with Steps 11-13 pre-marked so it skips straight to Step 14-16.
        assert recorded["result"]["steps_completed"] == [
            "run_pre_push_script",
            "git_push",
            "ensure_pr",
        ]
        assert recorded["result"]["pr_number"] == "1107"

    def test_merge_phase_source_never_passes_admin_and_merges_via_merge_pr_sh(self):
        # (c): Step 16 merges via merge_pr.sh WITHOUT --admin. The merge phase
        # shells merge_pr.sh with --sweep only, and "--admin" is never passed as
        # a subprocess argument (a quoted string literal) ANYWHERE in the module
        # — docstrings/comments that describe the no-admin guarantee in prose are
        # allowed, an actual `"--admin"`/`'--admin'` argument is not.
        module_src = inspect.getsource(commit_mod)
        assert '"--admin"' not in module_src
        assert "'--admin'" not in module_src
        phase_src = inspect.getsource(commit_mod._run_post_commit_pipeline)  # ANTICHEAT_OK: source verify
        assert "merge_pr.sh" in phase_src
        assert '"--sweep"' in phase_src
        assert "--admin" not in phase_src

    # (d) ── re-conflict path: the SAME helper the gates re-invoke resolves it ──
    def test_merge_phase_reconflict_helper_resolves_growth_cap(self, tmp_path):
        # The growth-cap conflict that re-appears AFTER bring-current is handled
        # by the SAME _try_auto_resolve_pr_conflict the Step-14 pre-CI gate,
        # CI-wait midpoll, and late merge retry re-invoke (asserted by source
        # linkage below). Behaviorally, that helper resolves the growth-cap
        # re-conflict instead of stranding it.
        cap = _write_growth_cap_conflict(
            tmp_path,
            "<<<<<<< HEAD\nCAP_TEST_FILES = 146  # +1 for test_mine.py (mine-wave)\n"
            "=======\nCAP_TEST_FILES = 146  # +1 for test_theirs.py (theirs-wave)\n"
            ">>>>>>> origin/dev\n",
        )
        fake = _make_helper_fake_run([GROWTH_CAP_RELPATH])
        with patch.object(commit_mod.subprocess, "run", side_effect=fake):
            result = commit_mod._try_auto_resolve_pr_conflict(  # ANTICHEAT_OK: re-conflict verify
                tmp_path,
                pr_number="1107",
                base_branch="dev",
                branch_name="wave/stranded",
                log=None,
            )
        assert result["resolved"] is True
        assert result["action"] == "mechanical_conflict_resolved"
        # base 145 + union of both distinct files (2) = 147, covering both.
        assert _parse_cap(cap.read_text(encoding="utf-8"), "CAP_TEST_FILES") == 147

    def test_step_14_to_16_callers_reinvoke_the_shared_helper(self):
        # Source linkage: the Step-14 pre-CI gate AND the late merge retry both
        # call _try_auto_resolve_pr_conflict, and the CI-wait threads the
        # midpoll auto-resolve context — so a mid-gate re-conflict on the
        # growth-cap file is covered by the same (now-extended) code path.
        phase_src = inspect.getsource(commit_mod._run_post_commit_pipeline)  # ANTICHEAT_OK: source verify
        assert phase_src.count("_try_auto_resolve_pr_conflict(") >= 2
        assert "midpoll_autoresolve" in phase_src


# ─────────────── (e) entrypoint resolve + checkout + VERIFY head ──────────────


class TestEntrypointResolveCheckoutVerify:
    def _spy_helper(self, flag):
        def helper(*args, **kwargs):
            flag["called"] = True
            return {"resolved": True, "action": "no_action", "detail": "x"}

        return helper

    def test_success_verifies_head_then_brings_current_then_merges(self, tmp_path):
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234"
        )
        calls: list = []
        helper_flag: dict = {"called": False, "branch": None}

        def spy_helper(repo_root, *, pr_number, base_branch, branch_name, log=None):
            helper_flag["called"] = True
            helper_flag["branch"] = branch_name
            return {"resolved": True, "action": "no_action", "detail": "current"}

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout="wave/x")
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout="abc1234")
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=spy_helper
        ), patch.object(
            commit_mod, "_run_post_commit_pipeline", return_value={"status": "success"}
        ), patch.object(
            commit_mod, "_continuation_record_path", return_value=tmp_path / "cont.json"
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "success"
        # Head verified, bring-current ran on the resolved head branch.
        assert helper_flag == {"called": True, "branch": "wave/x"}
        # Checkout of the exact head occurred before bring-current.
        assert ["git", "checkout", "wave/x"] in calls

    def test_fails_closed_when_head_unresolvable_no_checkout_no_helper(self, tmp_path):
        calls: list = []
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout="", returncode=1)  # gh cannot resolve
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ), patch.object(
            commit_mod, "_run_post_commit_pipeline", return_value={"status": "success"}
        ) as pcp:
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "resolve_pr_head"
        assert helper_flag["called"] is False  # helper NEVER invoked
        assert pcp.called is False  # merge phase NEVER invoked
        # No worktree mutation: not even a checkout was attempted.
        assert not any(c[:2] == ["git", "checkout"] for c in calls)

    def test_fails_closed_when_head_fields_missing(self, tmp_path):
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout="{}")  # no headRefName / headRefOid
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "resolve_pr_head"
        assert helper_flag["called"] is False

    def test_fails_closed_when_local_head_oid_mismatch(self, tmp_path):
        # Authority is satisfied so the flow reaches the head-OID proof; the OID
        # mismatch (not the authority gate) is what fails it closed here.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234"
        )
        calls: list = []
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout="wave/x")
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout="deadbeef")  # local HEAD != resolved head OID
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "verify_pr_head"
        assert helper_flag["called"] is False  # helper NEVER invoked
        # NO worktree mutation: the OID mismatch is PROVEN before any checkout, so
        # no checkout ever runs. (The bridge-flagged defect was checking out FIRST
        # and verifying AFTER — which mutated the worktree on a mismatch.)
        assert not any(c[:2] == ["git", "checkout"] for c in calls)
        # dev is never merged into the (stale) branch and the branch is not pushed.
        assert not any(c[:2] == ["git", "merge"] for c in calls)
        assert not any(c[:2] == ["git", "push"] for c in calls)

    def test_fails_closed_when_checked_out_branch_mismatch(self, tmp_path):
        # Authority satisfied; the post-checkout branch mismatch fails it closed.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234"
        )
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout="some/other-branch")  # wrong branch checked out
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout="abc1234")
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "verify_pr_head"
        assert helper_flag["called"] is False


# ───────────── receipt-chain authority gate (bridge re-entry finding) ─────────


class TestStrandedLandingAuthorityHelper:
    """``_stranded_landing_authority`` — the content-matched receipt-chain gate.

    Authority == an ACTIVE post-commit continuation record (the artifact written
    only after a COMMIT_GO/COMMIT_GO_HOLD_PUSH supervisor receipt + commit, and
    cleared on a successful merge) whose ``target_branch`` == the PR head AND
    ``pr_number`` == the PR being landed.
    """

    def _auth(self, repo_root, *, pr_number="1107", head_ref="wave/x"):
        return commit_mod._stranded_landing_authority(  # ANTICHEAT_OK: authority verify
            repo_root, pr_number=pr_number, head_ref=head_ref, log=None
        )

    def test_authorizes_active_go_record_matching_branch_and_pr(self, tmp_path):
        path = _write_receipt_chain(
            tmp_path, wave_id="w1", target_branch="wave/x", pr_number="1107",
            commit_sha="abc1234",
        )
        out = self._auth(tmp_path)
        assert out["authorized"] is True
        # Returns the matched record path (threaded back as continuation_path so a
        # successful merge clears the SAME record that authorized the land).
        assert out["path"] == path
        assert out["record"]["commit_sha"] == "abc1234"

    def test_unauthorized_when_no_record(self, tmp_path):
        out = self._auth(tmp_path)
        assert out["authorized"] is False
        assert out["path"] is None and out["record"] is None

    def test_unauthorized_on_pr_number_mismatch(self, tmp_path):
        _write_receipt_chain(tmp_path, target_branch="wave/x", pr_number="1107")
        # The clean PR #999 has no chain of its own — the #1107 chain must not
        # authorize landing a different PR.
        assert self._auth(tmp_path, pr_number="999")["authorized"] is False

    def test_unauthorized_on_target_branch_mismatch(self, tmp_path):
        _write_receipt_chain(tmp_path, target_branch="wave/x", pr_number="1107")
        assert self._auth(tmp_path, head_ref="wave/y")["authorized"] is False

    def test_unauthorized_on_non_go_receipt(self, tmp_path):
        # A commit that did NOT pass supervisor receipt validation is not landable.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107",
            receipt_decision="COMMIT_NO_GO",
        )
        assert self._auth(tmp_path)["authorized"] is False

    def test_unauthorized_on_non_active_status(self, tmp_path):
        # A merged PR's record is DELETED; a non-ACTIVE status must also fail.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107",
            status="post_merge_done",
        )
        assert self._auth(tmp_path)["authorized"] is False

    def test_unauthorized_on_missing_git_commit_step(self, tmp_path):
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107",
            steps_completed=["validate_inputs"],
        )
        assert self._auth(tmp_path)["authorized"] is False

    def test_unauthorized_on_empty_commit_sha(self, tmp_path):
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="",
        )
        assert self._auth(tmp_path)["authorized"] is False

    def test_unauthorized_on_wrong_version(self, tmp_path):
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", version=999,
        )
        assert self._auth(tmp_path)["authorized"] is False


class TestEntrypointReceiptChainGate:
    """Entrypoint-level fail-closed: a PR number alone cannot push/commit/merge,
    and a clean non-stranded PR is not landed by this bypass path."""

    def _spy_helper(self, flag):
        def helper(*args, **kwargs):
            flag["called"] = True
            return {"resolved": True, "action": "no_action", "detail": "x"}

        return helper

    def test_pr_number_alone_cannot_push_commit_merge(self, tmp_path):
        # NO receipt chain exists. The resolved head is valid, but a PR number
        # ALONE must NOT push, commit, or merge — fail closed at the authority gate
        # with the shared helper AND the merge phase both never invoked.
        calls: list = []
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ), patch.object(
            commit_mod, "_run_post_commit_pipeline", return_value={"status": "success"}
        ) as pcp:
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "authority"
        assert helper_flag["called"] is False  # bring-current (commit+push) NEVER ran
        assert pcp.called is False             # merge phase NEVER ran
        # Not even a worktree/remote mutation: no fetch, checkout, merge, push, or
        # commit was issued — a PR number alone touches nothing.
        for verb in ("fetch", "checkout", "merge", "push", "commit"):
            assert not any(c[:2] == ["git", verb] for c in calls), verb

    def test_clean_non_stranded_pr_not_landed(self, tmp_path):
        # A chain exists ONLY for stranded PR #1107 on wave/x. A DIFFERENT, clean
        # PR #999 (its own head) has no chain → not landable by this bypass path.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234"
        )
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"feature/clean","headRefOid":"f00dface"}')
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ), patch.object(
            commit_mod, "_run_post_commit_pipeline", return_value={"status": "success"}
        ) as pcp:
            result = commit_mod.land_stranded_pr(tmp_path, "999", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "authority"
        assert helper_flag["called"] is False
        assert pcp.called is False

    def test_already_merged_pr_record_cleared_not_relanded(self, tmp_path):
        # Simulate an already-merged PR whose record is no longer ACTIVE (the real
        # flow DELETES it on merge; a non-ACTIVE record must also fail closed).
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234",
            status="post_merge_done",
        )
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "authority"
        assert helper_flag["called"] is False

    def test_non_go_receipt_not_landed(self, tmp_path):
        # A commit that never earned a GO supervisor receipt is not landable.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="abc1234",
            receipt_decision="COMMIT_NO_GO",
        )
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "authority"
        assert helper_flag["called"] is False

    def test_head_force_pushed_off_receipt_commit_fails_closed(self, tmp_path):
        # The branch + PR match an active chain, but the CURRENT head OID does NOT
        # descend from the receipt-validated commit (a force-push to an unrelated
        # commit after the receipt). Fail closed at the authority gate, BEFORE any
        # checkout/merge/push — the head we'd land is not the one that chain
        # authorized.
        _write_receipt_chain(
            tmp_path, target_branch="wave/x", pr_number="1107", commit_sha="0ldc0mm17"
        )
        calls: list = []
        helper_flag: dict = {"called": False}

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            if cmd[:3] == ["git", "merge-base", "--is-ancestor"]:
                return _gh(returncode=1)  # head does NOT descend from receipt commit
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout="wave/x")
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout="abc1234")  # would-be checkout OID == head OID
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=self._spy_helper(helper_flag)
        ):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "error"
        assert result["step"] == "authority"
        assert helper_flag["called"] is False
        # Rejected pre-mutation: no checkout, no merge, no push of the bad head.
        assert not any(c[:2] == ["git", "checkout"] for c in calls)
        assert not any(c[:2] == ["git", "merge"] for c in calls)
        assert not any(c[:2] == ["git", "push"] for c in calls)

    def test_authorized_land_threads_receipt_record_as_continuation_path(self, tmp_path):
        # POSITIVE control + the clear-on-merge loop: a genuinely stranded PR with a
        # valid active chain DOES land, and the merge phase receives the EXACT
        # receipt record path — so its clear-on-merge deletes the record that
        # authorized this land (a re-land of the now-merged PR then fails closed).
        record_path = _write_receipt_chain(
            tmp_path, wave_id="stranded-wave", target_branch="wave/x",
            pr_number="1107", commit_sha="abc1234",
        )
        recorded: dict = {}

        def recorder_pcp(**kwargs):
            recorded.update(kwargs)
            return {"status": "success", "merge_sha": "deadbeef", "steps_completed": []}

        def spy_helper(repo_root, *, pr_number, base_branch, branch_name, log=None):
            return {"resolved": True, "action": "no_action", "detail": "current"}

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["gh", "pr", "view"]:
                return _gh(stdout='{"headRefName":"wave/x","headRefOid":"abc1234"}')
            if cmd[:2] == ["git", "rev-parse"] and "--abbrev-ref" in cmd:
                return _gh(stdout="wave/x")
            if cmd[:2] == ["git", "rev-parse"]:
                return _gh(stdout="abc1234")
            return _gh()

        with patch.object(commit_mod.subprocess, "run", side_effect=fake_run), patch.object(
            commit_mod, "_try_auto_resolve_pr_conflict", side_effect=spy_helper
        ), patch.object(commit_mod, "_run_post_commit_pipeline", side_effect=recorder_pcp):
            result = commit_mod.land_stranded_pr(tmp_path, "1107", base_branch="dev", log=None)

        assert result["status"] == "success"
        assert recorded["continuation_path"] == record_path
