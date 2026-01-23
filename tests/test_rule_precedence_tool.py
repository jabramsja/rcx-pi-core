from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_rule_precedence_json_shape(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text(
        "\n".join(
            [
                "# comment",
                "rule a: x -> y",
                "  something",
                "rewrite b: y -> z",
                "when c: z -> q",
            ]
        ),
        encoding="utf-8",
    )
    p = _run(["bash", "scripts/rule_precedence.sh", str(w), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["precedence_basis"] == "textual order (earlier rules first)"
    assert obj["rule_count_detected"] == 3
    assert obj["rules"][0]["line"] == 2
    assert "rule a" in obj["rules"][0]["text"]


def test_rule_precedence_top(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("rule a: x\nrule b: y\nrule c: z\n", encoding="utf-8")
    p = _run(["bash", "scripts/rule_precedence.sh", str(w), "--json", "--top", "2"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["rule_count_detected"] == 2


def test_rule_precedence_detects_real_world():
    # Ensure detector matches RCX-π real .mu syntax (route/rewrite lines like "[x] -> ra").
    world = Path("rcx_pi_rust/mu_programs/rcx_core.mu")
    assert world.is_file()
    p = _run(["bash", "scripts/rule_precedence.sh", str(world), "--json"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["rule_count_detected"] > 0
