from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_world_score_list_trace(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps([{"state": "a"}, {"state": "b"}, {"state": "c"}]), encoding="utf-8"
    )
    p = _run(["bash", "scripts/world_score.sh", str(t), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["steps_inferred"] == 3
    assert obj["unique_states"] == 3
    assert obj["loop_detected"] is False
    assert obj["score"] > 0.0


def test_world_score_embedded_steps(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps({"steps": [{"state": 1}, {"state": 2}], "halt_reason": "completed"}),
        encoding="utf-8",
    )
    p = _run(["bash", "scripts/world_score.sh", str(t), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["steps_inferred"] == 2
    assert "halt_reason" in obj["meta_present_keys"]


def test_world_score_loop_detection(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps([{"state": "a"}, {"state": "b"}, {"state": "a"}]), encoding="utf-8"
    )
    p = _run(["bash", "scripts/world_score.sh", str(t), "--json", "--loop"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["loop_detected"] is True
    assert obj["loop"]["period"] == 2


def test_world_score_max_steps_violation(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([1, 2, 3, 4]), encoding="utf-8")
    p = _run(["bash", "scripts/world_score.sh", str(t), "--json", "--max-steps", "3"])
    assert p.returncode == 1
    obj = json.loads(p.stdout)
    assert obj["violation"]["kind"] == "max_steps"
