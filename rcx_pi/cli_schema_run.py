from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import subprocess

from rcx_pi.cli_schema import SchemaTriplet, parse_schema_triplet


@dataclass(frozen=True)
class SchemaRunResult:
    cmd: list[str]
    line: str
    trip: SchemaTriplet


def one_nonempty_stdout_line(stdout: str) -> str:
    """
    Return the single non-empty stdout line.

    Raises AssertionError with a helpful message if stdout is empty
    or contains multiple non-empty lines.
    """
    lines = [ln for ln in stdout.splitlines() if ln.strip() != ""]  # AST_OK: infra
    assert len(lines) == 1, (
        f"expected exactly 1 non-empty stdout line, got {len(lines)}: {lines!r}"
    )
    return lines[0]


def parse_schema_triplet_stdout(stdout: str) -> SchemaRunResult:
    """
    Parse a schema-triplet from stdout (expects exactly one non-empty line).
    """
    line = one_nonempty_stdout_line(stdout)
    trip = parse_schema_triplet(line)
    return SchemaRunResult(cmd=["<stdout>"], line=line, trip=trip)


def run_schema_triplet(
    cmd: list[str],
    *,
    cwd: Optional[Path] = None,
    expected_tag: Optional[str] = None,
) -> SchemaRunResult:
    """
    Run a `--schema` command, assert one-line stdout, strict-parse it,
    and (optionally) assert tag equals expected_tag.
    """
    r = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None
    )
    assert r.returncode == 0, (
        f"command failed (rc={r.returncode}): {cmd!r}\nstderr:\n{(r.stderr or '').strip()}"
    )
    line = one_nonempty_stdout_line(r.stdout or "")
    trip = parse_schema_triplet(line)
    if expected_tag is not None:
        assert trip.tag == expected_tag, (
            f"unexpected schema tag for {cmd!r}: got {trip.tag!r}, expected {expected_tag!r}"
        )
    return SchemaRunResult(cmd=cmd, line=line, trip=trip)
