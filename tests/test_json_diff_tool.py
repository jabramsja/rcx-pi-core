from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_json_diff_ok_equal(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    # Same semantic object, different key order.
    a.write_text(json.dumps({"b": 2, "a": 1}), encoding="utf-8")
    b.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")

    p = _run(["bash", "scripts/json_diff.sh", str(a), str(b), "--quiet"])
    assert p.returncode == 0


def test_json_diff_detects_change(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": 1}), encoding="utf-8")
    b.write_text(json.dumps({"result": 2}), encoding="utf-8")

    p = _run(["bash", "scripts/json_diff.sh", str(a), str(b), "--quiet"])
    assert p.returncode == 1


def test_json_diff_ignore_optional_keys(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": {"x": 1}, "schema_version": "1.0.0"}), encoding="utf-8")
    b.write_text(json.dumps({"schema_version": "9.9.9", "result": {"x": 1}}), encoding="utf-8")

    p = _run(["bash", "scripts/json_diff.sh", str(a), str(b), "--ignore", "schema_version", "--quiet"])
    assert p.returncode == 0


def test_json_diff_only_scope(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": {"x": 1}, "seed": "aaa"}), encoding="utf-8")
    b.write_text(json.dumps({"result": {"x": 1}, "seed": "bbb"}), encoding="utf-8")

    # Compare only result; seed difference ignored.
    p = _run(["bash", "scripts/json_diff.sh", str(a), str(b), "--only", "result", "--quiet"])
    assert p.returncode == 0
