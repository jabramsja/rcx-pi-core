from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_term_check_list_trace_infers_steps(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps([{"state": "a"}, {"state": "b"}, {"state": "c"}]), encoding="utf-8"
    )
    p = _run(["bash", "scripts/rewrite_termination_check.sh", str(t), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["steps_inferred"] == 3


def test_term_check_embedded_steps(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps({"trace": [{"x": 1}, {"x": 2}], "halt_reason": "completed"}),
        encoding="utf-8",
    )
    p = _run(["bash", "scripts/rewrite_termination_check.sh", str(t), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["steps_inferred"] == 2
    assert obj["halt_reason_meta"] == "completed"


def test_term_check_max_steps_violation(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(json.dumps([1, 2, 3, 4]), encoding="utf-8")
    p = _run(
        [
            "bash",
            "scripts/rewrite_termination_check.sh",
            str(t),
            "--json",
            "--max-steps",
            "3",
        ]
    )
    assert p.returncode == 1
    obj = json.loads(p.stdout)
    assert obj["violation"]["kind"] == "max_steps"


def test_term_check_loop_detection(tmp_path: Path):
    t = tmp_path / "t.json"
    t.write_text(
        json.dumps([{"state": "a"}, {"state": "b"}, {"state": "a"}]), encoding="utf-8"
    )
    p = _run(
        ["bash", "scripts/rewrite_termination_check.sh", str(t), "--json", "--loop"]
    )
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["loop_detected"] is True
    assert obj["loop"]["period"] == 2


def test_contract_doc_exists_and_has_markers():
    p = Path("docs/RCX_REWRITE_TERMINATION_CONTRACTS.md")
    assert p.is_file()
    txt = p.read_text(encoding="utf-8", errors="replace")
    assert "Halt reasons" in txt
    assert "max_steps" in txt
    assert "loop_detected" in txt or "loop_detected" in txt.lower()
