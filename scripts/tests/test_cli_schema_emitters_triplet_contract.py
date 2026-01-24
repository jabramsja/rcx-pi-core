from __future__ import annotations

import subprocess


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def test_schema_emitters_are_triplets():
    outs = [
        _run(["python3", "rcx_pi/program_descriptor_cli.py", "--schema"]),
        _run(["python3", "rcx_pi/program_run_cli.py", "--schema"]),
        _run(["python3", "-m", "rcx_pi.worlds.world_trace_cli", "--schema"]),
        _run(
            [
                "python3",
                "scripts/snapshot_merge.py",
                "--schema",
                "A",
                "B",
                "--out",
                "OUT.json",
            ]
        ),
    ]
    for o in outs:
        parts = o.split()
        assert len(parts) == 3, f"expected 3 parts, got {len(parts)}: {o}"
