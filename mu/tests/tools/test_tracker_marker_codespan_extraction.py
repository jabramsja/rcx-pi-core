"""Regression tests for tracker-note evidence_command extraction (fail-closed).

The tracker-note marker extractor ``_tracker_marker_value`` is DUPLICATED in
``mu/tools/executors/commit_executor.py`` and
``mu/tools/agents/meta_bridge_supervisor.py``. The #52 pre-commit supervisor
path (``meta_bridge_supervisor._extract_tracker_note_evidence_command`` ->
``_run_wave_evidence_with_restore``) RUNS the extracted ``evidence_command`` and
gates it on ``package_evidence_command == declared_evidence_command`` before
running, then on ``exit == 0`` after.

Both extractors walk inline-code (backtick) spans, so a backtick-wrapped
``evidence_command`` -- the only form the canonical builder
(``tracker_sync_note.render_tracker_sync_note``, which ALWAYS backtick-wraps the
value) emits -- is extracted in full, embedded ``. marker:`` text and all. That
canonical path must stay byte-for-byte unchanged.

But an UN-backtick-wrapped value is non-canonical, and there is no reliable
text-only way to tell an embedded ``. marker:`` inside a shell command from a
real next-field boundary. The pre-fix extractor TRUNCATED such a value at the
embedded marker substring:

    evidence_command: echo ok. evidence_delta:foo && false. evidence_delta: real.

stopped at ``. evidence_delta:`` and both copies returned only ``echo ok.`` --
a PASSING prefix. Because both sides truncated identically the compare matched,
and the supervisor RAN ``echo ok.`` (exit 0) in place of the full command (whose
``&& false`` would FAIL): a fail-OPEN for manually-authored / legacy unwrapped
tracker notes (codex bot P2 counterexample).

The fix does NOT add another free-text boundary heuristic. Instead a non-canonical
(un-backtick-wrapped) ``evidence_command`` extracts to an always-failing sentinel
(``NONCANONICAL_EVIDENCE_COMMAND``) so the supervisor's wave_evidence gate FAILS
(-> NEEDS_PHASE_B): fail-CLOSED. A plain empty value is deliberately NOT used: the
supervisor SKIPS the wave_evidence gate when both declared and transported
evidence_command are empty, which would re-open the hole.

Wave: evidence-command-failclosed-unbacktick-2026-06-08
"""

from __future__ import annotations

import subprocess

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT

# bridge_adapters is a hard import dependency of meta_bridge_supervisor.
load_module("bridge_adapters", REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py")
_commit = load_module(
    "commit_executor_for_failclosed_tests",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)
_meta = load_module(
    "meta_bridge_supervisor_for_failclosed_tests",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)

# The two duplicated extractors under test, reached through each module's public
# test seam (the underscore-prefixed implementations are canonical; these public
# names delegate to them, so the suite does not reach into a module-private helper
# -- the test-integrity gate forbids that).
_MARKER_VALUE = {
    "commit_executor": _commit.tracker_marker_value,
    "meta_bridge_supervisor": _meta.tracker_marker_value,
}
_EVIDENCE_COMMAND = {
    "commit_executor": _commit.tracker_evidence_command_value,
    "meta_bridge_supervisor": _meta.extract_tracker_note_evidence_command,
}
SURFACES = sorted(_MARKER_VALUE)

# The codex bot P2 counterexample: an un-backtick-wrapped evidence_command whose
# own text contains a ". evidence_delta:" substring AND an "&& false" that must
# make the FULL command fail. The pre-fix extractor truncated to "echo ok." (a
# passing prefix), masking the "&& false".
_BOT_P2_NOTE = "evidence_command: echo ok. evidence_delta:foo && false. evidence_delta: real."


def _bash_exit_code(command: str) -> int:
    return subprocess.run(["bash", "-c", command], capture_output=True, text=True).returncode


@pytest.mark.parametrize("surface", SURFACES)
def test_unbacktick_evidence_command_not_truncated_to_passing_prefix(surface):
    """(P2) The un-backtick value is NOT truncated to ``echo ok`` / ``echo ok.``.

    Pinning the exact pre-fix output ``echo ok.`` makes this assertion FAIL on the
    current (pre-fix) extractor and PASS after the fix.
    """
    extracted = _EVIDENCE_COMMAND[surface](_BOT_P2_NOTE)
    assert extracted not in ("echo ok", "echo ok."), (
        "un-backtick evidence_command must NOT be truncated at the embedded "
        f"'. evidence_delta:' substring; got {extracted!r}"
    )


@pytest.mark.parametrize("surface", SURFACES)
def test_unbacktick_evidence_command_fails_closed_when_run(surface):
    """The extracted command for an un-backtick value MUST exit non-zero, so the
    #52 supervisor wave_evidence gate FAILS (-> NEEDS_PHASE_B). Proven by behavior:
    running the extracted command fails, whereas the pre-fix truncated prefix
    (``echo ok``) would have PASSED -- the fail-OPEN being closed."""
    extracted = _EVIDENCE_COMMAND[surface](_BOT_P2_NOTE)
    assert _bash_exit_code(extracted) != 0, (
        f"un-backtick evidence_command must fail closed; extracted={extracted!r}"
    )
    # Documents the fail-OPEN that is being closed: the truncated prefix passes.
    assert _bash_exit_code("echo ok.") == 0


@pytest.mark.parametrize("surface", SURFACES)
def test_unbacktick_evidence_command_returns_fail_closed_sentinel(surface):
    """The non-canonical value extracts to the shared fail-closed sentinel, and
    the sentinel itself is identical across both copies (so the supervisor's
    package-vs-declared compare matches and then the gate runs-and-fails)."""
    assert _EVIDENCE_COMMAND[surface](_BOT_P2_NOTE) == _commit.NONCANONICAL_EVIDENCE_COMMAND
    assert _commit.NONCANONICAL_EVIDENCE_COMMAND == _meta.NONCANONICAL_EVIDENCE_COMMAND


@pytest.mark.parametrize("surface", SURFACES)
def test_unwrapped_value_without_embedded_marker_also_fails_closed(surface):
    """ANY un-backtick value is non-canonical -- not only ones with an embedded
    marker substring. A plain unwrapped command also fails closed."""
    note = "evidence_command: python3 -m pytest -q. evidence_delta: real."
    assert _EVIDENCE_COMMAND[surface](note) == _commit.NONCANONICAL_EVIDENCE_COMMAND


@pytest.mark.parametrize("surface", SURFACES)
def test_backtick_wrapped_canonical_path_unchanged(surface):
    """The canonical (backtick-wrapped) path is preserved byte-for-byte: a command
    with embedded marker text inside the codespan plus an ``&&`` chain extracts in
    full -- the embedded ``evidence_delta:`` is ignored and the whole command
    survives."""
    note = (
        'evidence_command: `grep -q "evidence_delta: x" f '
        "&& grep -q boot0_track_id g`. evidence_delta: real delta."
    )
    assert (
        _EVIDENCE_COMMAND[surface](note)
        == 'grep -q "evidence_delta: x" f && grep -q boot0_track_id g'
    )
    # A simple canonical command, and a canonical command that is the final marker.
    assert (
        _EVIDENCE_COMMAND[surface]("evidence_command: `python3 -m pytest -q`. evidence_delta: ok.")
        == "python3 -m pytest -q"
    )
    assert _EVIDENCE_COMMAND[surface]("evidence_command: `wc -l STATUS.md`.") == "wc -l STATUS.md"


@pytest.mark.parametrize("surface", SURFACES)
def test_backtick_wrapped_raw_marker_value_unchanged(surface):
    """Parity-preserving: the RAW backtick-wrapped value (before inline-code strip)
    still carries the closing ```. `` for ``_strip_tracker_inline_code`` to remove --
    the marker-level extraction is byte-for-byte unchanged."""
    note = "evidence_command: `echo hi`. evidence_delta: d."
    assert _MARKER_VALUE[surface](note, "evidence_command") == "`echo hi`."


@pytest.mark.parametrize("surface", SURFACES)
def test_absent_evidence_command_stays_empty(surface):
    """A note with NO evidence_command marker extracts ``""`` -- it must NOT fail
    closed. The supervisor's both-empty branch legitimately skips the gate for a
    wave that declares no evidence_command (e.g. a MAINTENANCE wave)."""
    note = "Class: MAINTENANCE. no_op_proof: nothing changed. boot0_progress_state: HOLD."
    assert _EVIDENCE_COMMAND[surface](note) == ""


def test_fail_closed_sentinel_is_actually_fail_closed():
    """The sentinel itself MUST exit non-zero -- the property the whole fix relies
    on. If it ever exits 0, every non-canonical evidence_command would fail OPEN."""
    assert _bash_exit_code(_commit.NONCANONICAL_EVIDENCE_COMMAND) != 0


# ---------------------------------------------------------------------------
# The two duplicated implementations MUST agree. The #52 supervisor compares the
# package-transported evidence_command (extracted in commit_executor) against the
# tracker-declared one (extracted in meta_bridge_supervisor) for byte equality
# before running it. Any drift would either skip evidence silently (inequality on
# a canonical note) or, for a non-canonical note, fail to converge on the sentinel.
# ---------------------------------------------------------------------------

_AGREEMENT_NOTES = [
    _BOT_P2_NOTE,
    'evidence_command: `grep -q "evidence_delta: x" f && grep boot0_track_id g`. evidence_delta: real.',
    "evidence_command: python3 x.py --note evidence_delta:foo done. evidence_delta: real.",
    "evidence_command: `python3 -m pytest -q mu/tests/tools/test_x.py`. evidence_delta: (1) ok.",
    "evidence_command: plain unwrapped command with no following markers",
    "Class: MAINTENANCE. no_op_proof: x. boot0_progress_state: HOLD.",
    "",
    "no markers in this text at all",
]
_AGREEMENT_MARKERS = [
    "evidence_command",
    "evidence_delta",
    "FOUNDER_OVERRIDE",
    "boot0_progress_state",
]


@pytest.mark.parametrize("note", _AGREEMENT_NOTES)
@pytest.mark.parametrize("marker", _AGREEMENT_MARKERS)
def test_both_marker_extractors_agree(marker, note):
    commit_value = _commit.tracker_marker_value(note, marker)
    meta_value = _meta.tracker_marker_value(note, marker)
    assert commit_value == meta_value, (
        f"extractor drift for marker={marker!r}: "
        f"commit_executor={commit_value!r} != meta_bridge_supervisor={meta_value!r} "
        f"(note={note!r})"
    )


@pytest.mark.parametrize("note", _AGREEMENT_NOTES)
def test_both_evidence_command_extractors_agree(note):
    assert (
        _commit.tracker_evidence_command_value(note)
        == _meta.extract_tracker_note_evidence_command(note)
    )
