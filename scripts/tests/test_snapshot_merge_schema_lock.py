from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "docs" / "fixtures"
SCHEMA_PATH = ROOT / "docs" / "schemas" / "snapshot.v1.schema.json"


@pytest.mark.skipif(not SCHEMA_PATH.exists(), reason="snapshot schema JSON not found at docs/schemas/snapshot.v1.schema.json")
def test_snapshot_merge_output_validates_against_schema(tmp_path: Path):
    out = tmp_path / "merged.json"

    subprocess.check_call(
        [
            str(ROOT / "scripts" / "snapshot_merge.py"),
            str(FIX / "snapshot_rcx_core_v1.json"),
            str(FIX / "snapshot_rcx_core_v1_variant.json"),
            "--out",
            str(out),
        ]
    )

    merged = json.loads(out.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    from jsonschema import Draft7Validator

    Draft7Validator(schema).validate(merged)
