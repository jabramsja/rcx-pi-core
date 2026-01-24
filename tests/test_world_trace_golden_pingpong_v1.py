from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT / "tests" / "fixtures" / "world_trace" / "pingpong.world_trace.v1.canon.json"
)

PYTHON = "python3"


def _canon_world_trace(obj: dict) -> str:
    # Strip volatile fields that change every run
    meta = obj.get("meta")
    if isinstance(meta, dict):
        meta.pop("generated_at", None)
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def test_world_trace_pingpong_is_deterministic_against_golden() -> None:
    assert FIXTURE.exists(), f"Missing fixture: {FIXTURE}"

    r = subprocess.run(
        [
            PYTHON,
            "-m",
            "rcx_pi.rcx_cli",
            "trace",
            "pingpong",
            "ping",
            "--max-steps",
            "6",
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout or "") + "\n" + (r.stderr or "")

    got_obj = json.loads(r.stdout)
    got = _canon_world_trace(got_obj)

    # Fixture may be pretty-printed or compact; normalize it before compare
    exp_obj = json.loads(FIXTURE.read_text(encoding="utf-8"))
    exp = _canon_world_trace(exp_obj)

    assert got == exp, "world_trace pingpong drifted vs golden fixture"
