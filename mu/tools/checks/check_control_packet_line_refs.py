#!/usr/bin/env python3
"""Reject code line-number references inside control packets.

doc-governance forbids citing code by line number in docs/packets: a line
number drifts the moment surrounding code changes, producing a stale
reference that a Codex bridge round later rejects only after a multi-minute
review cycle. This checker mechanizes that written rule at packet-authoring /
dispatch time so a control packet under ``reports/control_plane/`` that cites
code as ``<path>.<ext>:<line>`` fails closed BEFORE the first bridge round.

Matcher design (deliberately narrow — a closed lexical pattern, NOT a general
heuristic):

    A known source-file extension (py, js, md, sh, json, yaml, yml, txt) that is
    immediately preceded by a dot AND immediately followed by a colon and one
    or more digits -- e.g. ``loader.py:128`` or ``eval_step.js:42``.

The leading dot, the closed extension set, and the ``:`` + digits suffix keep
the false-positive surface tiny *by construction*. The matcher does NOT flag:

  - host:port           ``localhost:8099``  (no dotted source extension before ``:``)
  - clock times         ``14:30``, ``12:34:56``  (no extension)
  - numeric ranges      ``10:20``  (no extension)
  - words ending in an extension's letters  ``bash:42``, ``mypy:5``  (no dot)
  - dotted names whose extension is not immediately followed by ``:`` + digits
    ``foo.python:42``  (the colon does not follow the ``py`` token)

Cite code by FUNCTION NAME instead of file:line.

Exit codes: 0 clean, 1 offending reference(s) found, 2 read error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Closed set of source-file extensions. Intentionally small: broadening this
# set widens the matcher's edge surface. Mirrors the extensions named in the
# governing packet (control-packet-line-ref-lint-2026-06-01). ``yml`` is the
# YAML twin of ``yaml`` -- GitHub workflow files use ``.yml`` -- so a citation
# like ``.github/workflows/ci.yml:<line>`` is the same stale-line-number form
# as ``ci.yaml:<line>``; including one without the other left an inconsistent
# gap (bridge round 1). Adding ``yml`` keeps the set closed and anchored, not a
# general heuristic.
CODE_EXTENSIONS: tuple[str, ...] = ("py", "js", "md", "sh", "json", "yaml", "yml", "txt")

# Longest-first alternation so an extension that is a prefix of another (``js``
# inside ``json``) cannot shadow the longer match. Correctness does not depend
# on ordering (the ``:`` + digits anchor forces backtracking either way), but
# longest-first keeps the first attempt authoritative and obvious to a reader.
_EXT_ALTERNATION = "|".join(sorted(CODE_EXTENSIONS, key=len, reverse=True))

# Extension-anchored colon-digit pattern. The leading ``\.`` and the ``:\d+``
# suffix are what reject host:port, clock times, numeric ranges, and words that
# merely end in an extension's letters.
LINE_REF_RE = re.compile(r"\.(?:" + _EXT_ALTERNATION + r"):\d+")

REMEDIATION = (
    "Cite code by function name instead of file:line. Line numbers drift when "
    "surrounding code changes, producing stale references that fail bridge review."
)


def find_offending_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(1-based line number, line text)`` for each offending line.

    A line offends when it contains at least one extension-anchored
    colon-digit reference. Lines are reported once regardless of how many
    references they carry; the stripped line text is returned for reporting.
    """
    offenses: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if LINE_REF_RE.search(line):
            offenses.append((lineno, line.strip()))
    return offenses


def scan_path(path: Path) -> list[tuple[int, str]]:
    """Scan a single control-packet file and return offending lines."""
    text = path.read_text(encoding="utf-8")
    return find_offending_lines(text)


def format_offenses(path: str, offenses: list[tuple[int, str]]) -> str:
    """Render one report line per offense: path, line number, offending text."""
    return "\n".join(
        f"{path}:{lineno}: code line-number reference: {text}"
        for lineno, text in offenses
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reject code line-number references (<path>.<ext>:<line>) in "
            "control packets. Cite code by function name instead."
        )
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Control-packet path(s) to scan.",
    )
    args = parser.parse_args(argv)

    total = 0
    for raw in args.paths:
        try:
            offenses = scan_path(Path(raw))
        except OSError as exc:
            print(f"{raw}: cannot read: {exc}", file=sys.stderr)
            return 2
        if offenses:
            total += len(offenses)
            print(format_offenses(raw, offenses), file=sys.stderr)

    if total:
        print(
            f"\n{total} code line-number reference(s) found. {REMEDIATION}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
