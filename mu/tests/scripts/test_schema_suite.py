"""Consolidated schema tests — CLI schema helpers, flags, and repo conventions.

Merged from 5 small test files (wave15, 2026-03-12) for growth cap headroom:
  test_cli_schema_helper.py, test_rcx_umbrella_cli_schema_triplet.py,
  test_world_trace_schema_flag.py, test_snapshot_schema_flag.py,
  test_schema_files_live_in_docs_schemas.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from rcx_pi.cli_schema import schema_triplet
from rcx_pi.cli_schema_run import run_schema_triplet


# --- cli_schema_helper tests ---


def test_schema_triplet_is_space_delimited_triplet():
    out = schema_triplet("tag.v1", "docs/a.md", "mu/docs/schemas/a.json")
    assert out == "tag.v1 docs/a.md mu/docs/schemas/a.json"
    assert out.count(" ") == 2


def test_schema_triplet_preserves_inputs_verbatim():
    out = schema_triplet("x", "y", "z")
    assert out == "x y z"


# --- umbrella CLI schema triplet ---


def test_rcx_cli_world_trace_schema_triplet_is_parseable():
    res = run_schema_triplet(
        ["python3", "-m", "rcx_pi.rcx_cli", "world", "trace", "--schema"],
        expected_tag="rcx-world-trace.v1",
    )
    assert res.trip.tag.endswith(".v1")


# --- world_trace --schema flag ---


def test_world_trace_schema_flag():
    repo_root = Path(__file__).resolve().parents[3]
    cli = repo_root / "rcx_pi" / "worlds" / "world_trace_cli.py"

    r = subprocess.run(
        ["python3", str(cli), "--schema"],
        capture_output=True,
        text=True,
    )

    assert r.returncode == 0
    assert "rcx-world-trace.v1" in r.stdout
    assert "mu/docs/schemas/world_trace_json_schema.md" in r.stdout


# --- snapshot --schema flag ---


def test_snapshot_schema_flag():
    repo_root = Path(__file__).resolve().parents[3]
    tool = repo_root / "scripts" / "snapshot" / "snapshot_merge.py"
    assert tool.exists(), f"missing: {tool}"

    r = subprocess.run(
        ["python3", str(tool), "--schema", "A", "B", "--out", "OUT.json"],
        capture_output=True,
        text=True,
    )
    # --schema should exit early successfully (tool prints schema line)
    assert r.returncode == 0
    out = r.stdout.strip()
    assert (
        out
        == "rcx.snapshot.v1 docs/snapshot_json_schema.md mu/docs/schemas/rcx.snapshot.v1.schema.json"
    )


# --- schema file location convention ---


def test_schema_files_live_in_docs_schemas():
    """
    Repo rule:
      - JSON schema artifacts must live under mu/docs/schemas/
      - docs/ root should not accumulate *schema*.json files (keeps docs tidy + predictable)
    """
    root = Path(__file__).resolve().parents[3]
    docs = root / "mu" / "docs"
    schemas = docs / "schemas"

    assert schemas.is_dir(), "docs/schemas must exist"

    # Allow-list: files under docs/schemas are fine.
    # Disallow: any JSON schema-looking files directly under docs/ root.
    bad = sorted(p.name for p in docs.glob("*.json") if "schema" in p.name.lower())

    assert bad == [], (
        f"Schema JSON files must live in mu/docs/schemas/, found in docs/: {bad}"
    )
