from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "docs" / "fixtures"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_snapshot_merge_rejects_mismatched_program_rules(tmp_path: Path):
    a = _load(FIX / "snapshot_rcx_core_v1.json")
    b = _load(FIX / "snapshot_rcx_core_v1.json")
    # mutate rules (in-memory)
    b["program"]["rules"] = list(b["program"]["rules"]) + ["[X] -> ra"]

    ap = tmp_path / "a.json"
    bp = tmp_path / "b.json"
    ap.write_text(json.dumps(a, indent=2) + "\n", encoding="utf-8")
    bp.write_text(json.dumps(b, indent=2) + "\n", encoding="utf-8")

    out = tmp_path / "out.json"
    r = subprocess.run(
        [str(ROOT / "scripts" / "snapshot_merge.py"), str(ap), str(bp), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "program.rules" in (r.stderr + r.stdout)


def test_snapshot_merge_deterministic_union_same_inputs(tmp_path: Path):
    a = FIX / "snapshot_rcx_core_v1.json"
    b = FIX / "snapshot_rcx_core_v1.json"
    out1 = tmp_path / "m1.json"
    out2 = tmp_path / "m2.json"

    subprocess.check_call([str(ROOT / "scripts" / "snapshot_merge.py"), str(a), str(b), "--out", str(out1)])
    subprocess.check_call([str(ROOT / "scripts" / "snapshot_merge.py"), str(a), str(b), "--out", str(out2)])

    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")

    m = _load(out1)
    assert m["schema"] == "rcx.snapshot.v1"
    assert m["world"] == "rcx_core"
    assert m["state"]["trace"] == []
    assert m["state"]["step_counter"] == 0
    assert m["state"]["current"] is None


def test_snapshot_merge_union_semantics_baseline_plus_variant(tmp_path: Path):
    a = FIX / "snapshot_rcx_core_v1.json"
    b = FIX / "snapshot_rcx_core_v1_variant.json"
    out = tmp_path / "merged.json"

    subprocess.check_call([str(ROOT / "scripts" / "snapshot_merge.py"), str(a), str(b), "--out", str(out)])
    m = _load(out)

    assert m["schema"] == "rcx.snapshot.v1"
    assert m["world"] == "rcx_core"

    # Fresh-start invariants
    assert m["state"]["trace"] == []
    assert m["state"]["step_counter"] == 0
    assert m["state"]["current"] is None

    # Union semantics (the point of the tool)
    ra = set(m["state"]["ra"])
    lobes = set(m["state"]["lobes"])
    sink = set(m["state"]["sink"])

    assert "[null,a]" in ra
    assert "[null,b]" in ra

    assert "[inf,a]" in lobes
    assert "[inf,b]" in lobes
    assert "[omega,[a,b]]" in lobes
    assert "[omega,[b,c]]" in lobes

    assert "[paradox,a]" in sink
    assert "[paradox,b]" in sink
