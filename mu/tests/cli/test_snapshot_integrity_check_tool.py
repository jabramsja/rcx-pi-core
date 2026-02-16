from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_snapshot_ok_default_only_result(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": {"x": 1}, "kind": "A"}), encoding="utf-8")
    b.write_text(json.dumps({"result": {"x": 1}, "kind": "B"}), encoding="utf-8")
    p = _run(["bash", "scripts/snapshot_integrity_check.sh", str(a), str(b)])
    assert p.returncode == 0
    assert "OK: JSON equal" in (p.stdout + p.stderr)


def test_snapshot_mismatch_fails(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": {"x": 1}}), encoding="utf-8")
    b.write_text(json.dumps({"result": {"x": 2}}), encoding="utf-8")
    p = _run(["bash", "scripts/snapshot_integrity_check.sh", str(a), str(b), "--json"])
    assert p.returncode == 1
    obj = json.loads(p.stdout)
    assert obj["ok"] is False


def test_snapshot_custom_only(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"stats": {"n": 1}, "result": 10}), encoding="utf-8")
    b.write_text(json.dumps({"stats": {"n": 2}, "result": 10}), encoding="utf-8")
    p = _run(
        [
            "bash",
            "scripts/snapshot_integrity_check.sh",
            str(a),
            str(b),
            "--only",
            "result",
        ]
    )
    assert p.returncode == 0


def test_snapshot_json_shape(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps({"result": 1, "schema_version": 1}), encoding="utf-8")
    b.write_text(json.dumps({"result": 1, "schema_version": 2}), encoding="utf-8")
    p = _run(["bash", "scripts/snapshot_integrity_check.sh", str(a), str(b), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["only"] == "result"
    assert "schema_version" in obj["ignore"]
