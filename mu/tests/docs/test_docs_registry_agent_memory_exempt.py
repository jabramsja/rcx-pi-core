r"""
Regression: `.claude/agent-memory/` markdown is docs-governance exempt.

Agent-written memory under `.claude/agent-memory/<role>/` (e.g. advisor/, expert/)
is agent runtime scratch, not governed documentation. Before this exemption it
classified as ``unknown`` via ``classify_md_path``, so
``docs_sync_report.collect_report()`` listed it under ``unclassified_markdown``
and ``docs_sync_report.py --check`` returned exit 1 -- blocking otherwise-clean
commits whenever advisor/expert memory existed on disk (it blocked the
packet-l4-autopopulate wave's commit when advisor memory existed under
.claude/agent-memory/advisor/).

The fix adds a single ``.claude/agent-memory/``-anchored regex to
``exempt_patterns`` in mu/tools/docs/docs_registry.json, mirroring the existing
``.claude/rules/`` agent-surface exemption. These tests pin that behavior and
guard against (a) the exemption regressing and (b) the exemption broadening past
the single ``.claude/agent-memory/`` prefix.

Evidence command:
    PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_docs_registry_agent_memory_exempt.py
"""

from __future__ import annotations

# PATH SETUP - Ensure repo root is at position 0 for 'tools' imports
# pytest adds tests/ to sys.path which can shadow repo root's tools package
import sys as _sys
from pathlib import Path as _Path
from tests.repo_root import REPO_ROOT as _REPO_ROOT
_repo_root = str(_REPO_ROOT)
if _sys.path[0] != _repo_root:
    if _repo_root in _sys.path:
        _sys.path.remove(_repo_root)
    _sys.path.insert(0, _repo_root)
# If tests/tools was imported first, it can shadow the repo tools package.
if "tools" in _sys.modules:
    _tools_mod = _sys.modules["tools"]
    _mod_file = str(getattr(_tools_mod, "__file__", "") or "")
    _mod_path = str(next(iter(getattr(_tools_mod, "__path__", [])), ""))
    if "tests/tools" in _mod_file or "tests/tools" in _mod_path:
        del _sys.modules["tools"]

import os
import tempfile
from pathlib import Path

from tools.docs.docs_sync_report import collect_report
from tools.docs.shared_doc_config import REPO_ROOT, classify_md_path


class TestAgentMemoryExempt:
    """`.claude/agent-memory/` markdown must classify as exempt, not unknown."""

    def test_agent_memory_advisor_md_classifies_exempt(self):
        """An advisor-memory markdown path is exempt (was 'unknown' before the fix)."""
        doc = REPO_ROOT / ".claude" / "agent-memory" / "advisor" / "sample.md"
        assert classify_md_path(doc) == "exempt", (
            "`.claude/agent-memory/advisor/*.md` must classify as exempt via "
            "docs_registry.json exempt_patterns; regressing the "
            r"`^\.claude/agent-memory/` entry re-breaks docs_sync_report --check "
            "(exit 1) on agent-written memory and blocks otherwise-clean commits"
        )

    def test_agent_memory_exemption_stays_anchored_to_prefix(self):
        """A non-agent-memory lookalike must NOT be exempted (anchored, not broadened).

        The exemption is the single ``.claude/agent-memory/`` prefix. A sibling
        directory (``agent-memory-lane2``) or a same-named file without the
        trailing slash (``agent-memoryX.md``) is distinct and must stay
        non-exempt -- guarding the constraint that the exemption is not widened.
        """
        for lookalike in (
            REPO_ROOT / ".claude" / "agent-memory-lane2" / "x.md",
            REPO_ROOT / ".claude" / "agent-memoryX.md",
        ):
            assert classify_md_path(lookalike) != "exempt", (
                f"{lookalike.relative_to(REPO_ROOT)} must NOT be exempt: the "
                "exemption is anchored to the single '.claude/agent-memory/' "
                "prefix and must not broaden"
            )

    def test_collect_report_excludes_agent_memory_markdown(self):
        """docs_sync_report.collect_report() must not list agent-memory md as unclassified.

        Exercises the real report function end-to-end. ``collect_report()`` walks
        the filesystem via ``rglob`` (it does not honor .gitignore, which is why
        gitignored agent-memory markdown tripped the check in the first place), so
        this creates a real markdown file under .claude/agent-memory/advisor/ --
        the directory that walk actually visits -- then removes it. With the
        exemption the file is absent from ``unclassified_markdown``; without it the
        file would classify ``unknown`` and appear there, so this test fails closed
        if the registry entry regresses.
        """
        advisor_dir = REPO_ROOT / ".claude" / "agent-memory" / "advisor"

        # Record directories we create so cleanup restores the tree as we found it
        # (deepest-first; .claude itself already exists and is never touched).
        created_dirs: list[Path] = []
        probe = advisor_dir
        while not probe.exists() and probe != REPO_ROOT:
            created_dirs.append(probe)
            probe = probe.parent
        advisor_dir.mkdir(parents=True, exist_ok=True)

        probe_file: Path | None = None
        try:
            fd, name = tempfile.mkstemp(
                dir=str(advisor_dir), prefix="regression_probe_", suffix=".md"
            )
            os.close(fd)
            probe_file = Path(name)
            probe_file.write_text("# agent-memory regression probe\n", encoding="utf-8")

            rel = str(probe_file.relative_to(REPO_ROOT))
            # Precondition: the real probe file is on the exempt classifier path.
            assert classify_md_path(probe_file) == "exempt"

            report = collect_report()
            assert rel not in report["unclassified_markdown"], (
                f"{rel} leaked into unclassified_markdown; the "
                r"`^\.claude/agent-memory/` exemption is not taking effect in "
                "docs_sync_report.collect_report()"
            )
            # No agent-memory markdown at all should be flagged unclassified.
            leaked = [
                p
                for p in report["unclassified_markdown"]
                if p.startswith(".claude/agent-memory/")
            ]
            assert not leaked, f"agent-memory markdown listed as unclassified: {leaked}"
        finally:
            if probe_file is not None and probe_file.exists():
                probe_file.unlink()
            for dpath in created_dirs:  # deepest-first
                try:
                    if dpath.exists() and not any(dpath.iterdir()):
                        dpath.rmdir()
                except OSError:
                    pass
