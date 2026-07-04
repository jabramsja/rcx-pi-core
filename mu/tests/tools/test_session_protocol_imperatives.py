"""Hermetic guard for the shared session-protocol standing imperatives.

The founder's emphatic 2026-07-04 directive — "you orchestrate; the pipeline/
recovery does the grunt work" — is persisted on the Claude side (CLAUDE.md +
memory + hourly cron). But the SHARED surface that BOTH orchestrators run at
startup (Claude preflight, the hourly protocol cron, AND Codex startup) is
``mu/tools/session/rcx_session_protocol.sh``. This test pins the AUTOMATE THE
GRUNT WORK imperative into section ``(b) SHARED STANDING IMPERATIVES`` of that
script, so an orchestrator=codex startup also enumerates it.

It is hermetic: it reads the committed script and asserts on its text only — no
subprocess, network, bridge, or DB. The placement assertion gives the test teeth
beyond a bare marker grep: a correct-but-misplaced (e.g. under section ``(c)``)
or numbered variant fails.
"""
from __future__ import annotations

import re

from tests.repo_root import REPO_ROOT

SCRIPT = REPO_ROOT / "mu" / "tools" / "session" / "rcx_session_protocol.sh"

MARKER = "AUTOMATE THE GRUNT WORK"
SECTION_B_HEADER = "(b) SHARED STANDING IMPERATIVES"
SECTION_C_HEADER = "(c) KEY PIPELINE COMMANDS"


def _lines() -> list[str]:
    return SCRIPT.read_text(encoding="utf-8").splitlines()


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"missing shared session-protocol script: {SCRIPT}"


def test_automate_grunt_work_marker_present() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert MARKER in text, f"{MARKER!r} standing imperative not found in {SCRIPT}"


def test_marker_is_a_dash_bullet_inside_section_b() -> None:
    lines = _lines()

    b_idx = next((i for i, ln in enumerate(lines) if SECTION_B_HEADER in ln), None)
    c_idx = next((i for i, ln in enumerate(lines) if SECTION_C_HEADER in ln), None)
    assert b_idx is not None, f"section (b) header not found: {SECTION_B_HEADER!r}"
    assert c_idx is not None, f"section (c) header not found: {SECTION_C_HEADER!r}"
    assert b_idx < c_idx, "section (b) header must precede section (c) header"

    # Section (b)'s rendered block ends at the first `echo ""` after its header.
    # Bounding the upper limit on that terminator (rather than merely on the (c)
    # header) is what rejects a bullet smuggled into the dead zone between (b)'s
    # closing blank and the (c) header/lead-in comment — that region is NOT
    # section (b). A `... < c_idx` bound would let such a stray marker pass.
    b_end = next(
        (i for i in range(b_idx + 1, len(lines)) if lines[i].strip() == 'echo ""'),
        None,
    )
    assert b_end is not None, 'no `echo ""` terminates section (b)'
    assert b_end < c_idx, (
        "section (b) terminator must precede the (c) header "
        f"(terminator at line {b_end + 1}, (c) header at line {c_idx + 1})"
    )

    marker_lines = [i for i, ln in enumerate(lines) if MARKER in ln]
    assert marker_lines, f"{MARKER!r} not found in {SCRIPT}"

    # Every occurrence of the marker must sit strictly inside section (b)'s
    # bullet block: after the (b) header and before its terminating `echo ""`.
    # This is what gives the test teeth beyond a bare grep — a marker added in
    # the wrong section, in the (b)/(c) gap, or in a stray comment fails here.
    for i in marker_lines:
        assert b_idx < i < b_end, (
            f"{MARKER!r} at line {i + 1} is not inside section (b)'s bullet block "
            f"(header at line {b_idx + 1}, section terminator at line {b_end + 1})"
        )

    # It must render as an UNNUMBERED dash bullet, matching the existing
    # `echo "    - <LABEL>: ..."` style — not a numbered item.
    bullet_re = re.compile(r'^\s*echo\s+"\s*-\s+' + re.escape(MARKER))
    assert any(bullet_re.match(lines[i]) for i in marker_lines), (
        f"{MARKER!r} is present in section (b) but not rendered as a dash "
        f'bullet in the `echo "    - <LABEL>: ..."` style'
    )
