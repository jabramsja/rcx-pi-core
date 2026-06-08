"""Regression tests for tracker-note marker codespan extraction.

Guards a latent fail-open in ``_tracker_marker_value``, which is DUPLICATED in
``mu/tools/executors/commit_executor.py`` and
``mu/tools/agents/meta_bridge_supervisor.py`` (``phase_b_executor`` delegates to
the commit_executor copy). Both extractors walk inline-code (backtick) spans, so
a backtick-wrapped ``evidence_command`` always extracted in full. But for an
UN-backtick-wrapped value:

  * a value containing a marker-name substring (e.g. ``--note evidence_delta:foo``)
    was TRUNCATED at that substring, dropping the rest of the real command, and
  * a trailing sentence/separator period (``... && echo ok.``) was carried into
    the extracted command.

The #52 pre-merge supervisor path
(``meta_bridge_supervisor._extract_tracker_note_evidence_command`` ->
``_run_wave_evidence_with_restore``) RUNS the extracted ``evidence_command``, and
gates it on ``package_evidence_command == declared_evidence_command``. Because
both sides used the same (buggy) extractor they truncated identically, matched,
and the truncated command RAN -- a truncated command can PASS where the full
command would FAIL, letting a broken wave merge.

The hardening requires a GENUINE next-marker boundary -- the ``". "`` separator
of the canonical note format (see ``tracker_sync_note.render_tracker_sync_note``)
-- before ending a value, and strips a single trailing sentence period from
un-backtick-wrapped values. Backtick-wrapped extraction is preserved byte-for-byte.

Wave: evidence-command-extraction-codespan-2026-06-08
"""

from __future__ import annotations

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT

# bridge_adapters is a hard import dependency of meta_bridge_supervisor.
load_module("bridge_adapters", REPO_ROOT / "mu" / "tools" / "agents" / "bridge_adapters.py")
_commit = load_module(
    "commit_executor_for_codespan_tests",
    REPO_ROOT / "mu" / "tools" / "executors" / "commit_executor.py",
)
_meta = load_module(
    "meta_bridge_supervisor_for_codespan_tests",
    REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py",
)
# tracker_sync_note is the canonical BUILDER of the note format. Both extractor
# marker lists MUST cover every "field:" marker it can emit, so the builder
# completeness tests below render a real note through it and assert no marker
# over-reads into the next field.
_tracker_sync_note = load_module(
    "tracker_sync_note_for_codespan_tests",
    REPO_ROOT / "mu" / "tools" / "executors" / "tracker_sync_note.py",
)

# The two duplicated low-level extractors under test, reached through each
# module's public test seam (the underscore-prefixed implementations are
# canonical; these public names delegate to them, so the suite does not reach
# into a module-private helper -- the test-integrity gate forbids that).
_MARKER_VALUE = {
    "commit_executor": _commit.tracker_marker_value,
    "meta_bridge_supervisor": _meta.tracker_marker_value,
}
# The public evidence_command extraction helpers (raw value + inline-code strip).
_EVIDENCE_COMMAND = {
    "commit_executor": _commit.tracker_evidence_command_value,
    "meta_bridge_supervisor": _meta.extract_tracker_note_evidence_command,
}
SURFACES = sorted(_MARKER_VALUE)


@pytest.mark.parametrize("surface", SURFACES)
def test_backtick_wrapped_embedded_marker_and_chain_extracts_full(surface):
    """(a) Backtick-wrapped command with embedded marker text + an ``&&`` chain
    extracts in full -- the embedded ``evidence_delta:`` inside the codespan is
    ignored and the whole command survives."""
    note = (
        'evidence_command: `grep -q "evidence_delta: x" f '
        "&& grep -q boot0_track_id g`. evidence_delta: real delta."
    )
    assert (
        _EVIDENCE_COMMAND[surface](note)
        == 'grep -q "evidence_delta: x" f && grep -q boot0_track_id g'
    )


@pytest.mark.parametrize("surface", SURFACES)
def test_unwrapped_embedded_marker_substring_not_truncated(surface):
    """(b) An un-backtick-wrapped value with an embedded marker-name substring
    (``evidence_delta:foo``, preceded by a plain space rather than ``". "``) is
    NOT truncated at that substring."""
    note = (
        "evidence_command: python3 x.py --note evidence_delta:foo done. "
        "evidence_delta: real."
    )
    assert _EVIDENCE_COMMAND[surface](note) == "python3 x.py --note evidence_delta:foo done"


@pytest.mark.parametrize("surface", SURFACES)
def test_trailing_sentence_period_stripped_before_next_marker(surface):
    """(c) The separator period before the next marker does not leak into the
    executed command."""
    note = "evidence_command: python3 -m pytest -q && echo ok. evidence_delta: real."
    assert _EVIDENCE_COMMAND[surface](note) == "python3 -m pytest -q && echo ok"


@pytest.mark.parametrize("surface", SURFACES)
def test_trailing_sentence_period_stripped_final_marker(surface):
    """(c') A trailing period is stripped even when evidence_command is the final
    marker (the note's closing period). Otherwise ``wc -l STATUS.md.`` would run
    against a nonexistent file."""
    note = "evidence_command: wc -l STATUS.md."
    assert _EVIDENCE_COMMAND[surface](note) == "wc -l STATUS.md"


@pytest.mark.parametrize("surface", SURFACES)
def test_genuine_next_marker_boundary_still_splits(surface):
    """(d) A genuine ``". marker:"`` boundary still ends the current value -- the
    value does not over-read into the following marker."""
    note = "evidence_command: python3 run.py. evidence_delta: only this is the delta."
    marker_value = _MARKER_VALUE[surface]
    assert marker_value(note, "evidence_command") == "python3 run.py"
    assert marker_value(note, "evidence_delta") == "only this is the delta"


@pytest.mark.parametrize("surface", SURFACES)
def test_backtick_wrapped_raw_value_is_byte_identical(surface):
    """Parity-preserving: the RAW backtick-wrapped value (before inline-code
    strip) is unchanged -- it still carries the closing ```. `` for
    ``_strip_tracker_inline_code`` to remove."""
    note = "evidence_command: `echo hi`. evidence_delta: d."
    assert _MARKER_VALUE[surface](note, "evidence_command") == "`echo hi`."


@pytest.mark.parametrize("surface", SURFACES)
def test_double_period_value_keeps_its_own_sentence_period(surface):
    """A value whose own text ends in a period, followed by the ``". "``
    separator (double period in the raw note), keeps exactly one period and stops
    at the genuine boundary."""
    note = (
        "evidence_command: run a.py. evidence_delta: the value ends here.. "
        "progress_proof_before: next."
    )
    # evidence_command stops at the genuine evidence_delta boundary.
    assert _MARKER_VALUE[surface](note, "evidence_command") == "run a.py"
    # evidence_delta keeps its own sentence period (only the separator dropped).
    assert _MARKER_VALUE[surface](note, "evidence_delta") == "the value ends here."


# ---------------------------------------------------------------------------
# (e) The two duplicated implementations MUST agree. The #52 supervisor compares
#     the package-transported evidence_command (extracted in commit_executor /
#     phase_b_executor) against the tracker-declared one (extracted in
#     meta_bridge_supervisor) for byte equality before running it. Any drift
#     would either skip evidence silently (inequality) or run a different
#     command than was declared.
# ---------------------------------------------------------------------------

_AGREEMENT_NOTES = [
    'evidence_command: `grep -q "evidence_delta: x" f && grep -q boot0_track_id g`. '
    "evidence_delta: real.",
    "evidence_command: python3 x.py --note evidence_delta:foo done. evidence_delta: real.",
    "evidence_command: python3 -m pytest -q && echo ok. evidence_delta: real.",
    "evidence_command: wc -l STATUS.md.",
    "evidence_command: python3 run.py. evidence_delta: only this is the delta.",
    "evidence_command: run a.py. progress_proof_before: did x. evidence_delta: y. "
    "FOUNDER_OVERRIDE:some-wave-id. boot0_progress_state: HOLD.",
    "evidence_command: `python3 -m pytest -q mu/tests/tools/test_x.py`. evidence_delta: (1) ok.",
    "",
    "no markers in this text at all",
]
_AGREEMENT_MARKERS = [
    "evidence_command",
    "evidence_delta",
    "workload_target",
    "FOUNDER_OVERRIDE",
    "boot0_progress_state",
]


@pytest.mark.parametrize("note", _AGREEMENT_NOTES)
@pytest.mark.parametrize("marker", _AGREEMENT_MARKERS)
def test_both_extractors_agree(marker, note):
    commit_value = _commit.tracker_marker_value(note, marker)
    meta_value = _meta.tracker_marker_value(note, marker)
    assert commit_value == meta_value, (
        f"extractor drift for marker={marker!r}: "
        f"commit_executor={commit_value!r} != meta_bridge_supervisor={meta_value!r} "
        f"(note={note!r})"
    )


@pytest.mark.parametrize("note", _AGREEMENT_NOTES)
def test_public_evidence_command_helpers_agree(note):
    assert (
        _commit.tracker_evidence_command_value(note)
        == _meta.extract_tracker_note_evidence_command(note)
    )


# ---------------------------------------------------------------------------
# (f) L4_STRUCTURAL markers must act as value boundaries. Regression for a
#     second fail-open: the extractor marker list OMITTED the structural markers
#     (workload_target, host_semantics_delta_before/after, structural_artifact_ref,
#     post_gate_contract_sweep), so workload_target over-read past
#     ". host_semantics_delta_before: ..." to "seed_auto_execution. "
#     "host_semantics_delta_before: before". That over-read string is not a known
#     workload key, so commit_executor._structural_workload_evidence_modules
#     returned () and _test_files_cover_structural_tracker_evidence then accepted
#     an UNRELATED l4_gates test path as structural evidence (a fail-open). The
#     fix adds every builder-emitted marker to both extractor lists.
# ---------------------------------------------------------------------------

_STRUCTURAL_NOTE = (
    "Class: L4_STRUCTURAL. target_gate_id: G8. workload_target: seed_auto_execution. "
    "host_semantics_delta_before: before scope. host_semantics_delta_after: after scope. "
    "structural_artifact_ref: reports/structural_ref. evidence_command: `pytest`. "
    "evidence_delta: ok. post_gate_contract_sweep: `sweep`. boot0_progress_state: HOLD."
)

_STRUCTURAL_BOUNDARY_CASES = [
    ("workload_target", "seed_auto_execution"),
    ("host_semantics_delta_before", "before scope"),
    ("host_semantics_delta_after", "after scope"),
    ("structural_artifact_ref", "reports/structural_ref"),
]


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("marker, expected", _STRUCTURAL_BOUNDARY_CASES)
def test_structural_marker_stops_at_next_marker(surface, marker, expected):
    """An L4_STRUCTURAL marker value ends at the genuine next-marker boundary --
    it does not over-read into the following structural field."""
    assert _MARKER_VALUE[surface](_STRUCTURAL_NOTE, marker) == expected


# ---------------------------------------------------------------------------
# (g) Builder-completeness: render a REAL note through the canonical builder
#     (tracker_sync_note.render_tracker_sync_note) and assert every marker it
#     emits is a recognized boundary, so none over-reads into the next field.
#     This pins both extractor lists to the builder -- the structural guard that
#     would have caught the omitted-structural-marker fail-open above. If a future
#     builder field is added without updating the extractor lists, the preceding
#     marker over-reads and one of these cases fails.
# ---------------------------------------------------------------------------


def _full_structural_tracker_note():
    fields = _tracker_sync_note.TrackerSyncNoteFields(
        wave_id="codespan-completeness",
        title="Builder completeness probe",
        wave_class="L4_STRUCTURAL",
        target_gate_id="G8",
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_TYPED_FAIL_CLOSED_OUTCOMES",
        indicator_artifact_ref="reports/ind.json",
        indicator_collection_command="collect-cmd",
        workload_target="seed_auto_execution",
        host_semantics_delta_before="before-sentinel",
        host_semantics_delta_after="after-sentinel",
        structural_artifact_ref="reports/structural-sentinel",
        evidence_command="evcmd-sentinel",
        evidence_delta="evdelta-sentinel",
        progress_proof_before="ppb-sentinel",
        progress_proof_after="ppa-sentinel",
        post_gate_contract_sweep="sweep-sentinel",
        packet_ref="reports/control_plane/packet-sentinel.md",
    )
    return _tracker_sync_note.render_tracker_sync_note(fields)


# (marker, expected raw extraction) for fields the builder emitted above.
# Backtick-wrapped markers (Packet, post_gate_contract_sweep) keep their inline
# code span + trailing "`." for _strip_tracker_inline_code; plain markers extract
# their sentinel verbatim. Covers the previously-omitted structural markers.
_BUILDER_MARKER_EXPECTATIONS = [
    ("Packet", "`reports/control_plane/packet-sentinel.md`."),
    ("workload_target", "seed_auto_execution"),
    ("host_semantics_delta_before", "before-sentinel"),
    ("host_semantics_delta_after", "after-sentinel"),
    ("structural_artifact_ref", "reports/structural-sentinel"),
    ("evidence_delta", "evdelta-sentinel"),
    ("progress_proof_before", "ppb-sentinel"),
    ("progress_proof_after", "ppa-sentinel"),
    ("post_gate_contract_sweep", "`sweep-sentinel`."),
    ("boot0_progress_state", "HOLD"),
]


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("marker, expected", _BUILDER_MARKER_EXPECTATIONS)
def test_builder_emitted_marker_extracts_without_overread(surface, marker, expected):
    note = _full_structural_tracker_note()
    assert _MARKER_VALUE[surface](note, marker) == expected


@pytest.mark.parametrize("surface", SURFACES)
def test_builder_backtick_evidence_command_extracts_full(surface):
    """The builder backtick-wraps evidence_command; the public helper returns the
    inner command verbatim from a real rendered note."""
    note = _full_structural_tracker_note()
    assert _EVIDENCE_COMMAND[surface](note) == "evcmd-sentinel"
