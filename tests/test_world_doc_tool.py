from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def test_world_doc_json_shape(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text(
        "\n".join(
            [
                "# comment",
                "[a] -> ra",
                "[b] -> lobe",
                "PING -> rewrite (PONG)",
                "not a rule",
            ]
        ),
        encoding="utf-8",
    )
    p = _run(["bash", "scripts/world_doc.sh", str(w), "--json", "--top", "10"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["precedence_basis"] == "textual order (earlier lines first)"
    assert obj["rule_like_count"] == 3
    assert obj["action_histogram"]["ra"] == 1
    assert obj["action_histogram"]["lobe"] == 1
    assert obj["action_histogram"]["rewrite"] == 1
    assert len(obj["top_rules"]) == 3


def test_world_doc_markdown_emits_header(tmp_path: Path):
    w = tmp_path / "w.mu"
    w.write_text("[x] -> sink\n", encoding="utf-8")
    p = _run(["bash", "scripts/world_doc.sh", str(w), "--top", "5"])
    assert p.returncode == 0
    assert "# World auto-doc:" in p.stdout
    assert "Action histogram" in p.stdout


def test_world_doc_detects_real_world_file():
    # Ensure this works on an actual repo world
    world = Path("rcx_pi_rust/mu_programs/rcx_core.mu")
    assert world.is_file()
    p = _run(["bash", "scripts/world_doc.sh", str(world), "--json", "--top", "5"])
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj["rule_like_count"] > 0
