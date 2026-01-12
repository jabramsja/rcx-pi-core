from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_world_trace_json_contract_minimal_world():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "world_trace.sh"
    assert script.exists(), f"missing: {script}"

    # Tiny inline "world" payload. Keep it permissive: the CLI should accept a minimal motif.
    # If your CLI expects a different minimal input shape, adjust ONLY this payload (not the contract assertions).
    world_json = '{"seed":[null,"a"]}\n'

    r = subprocess.run(
        ["bash", str(script), "--json", "--pretty", "--max-steps", "3"],
        cwd=str(repo_root),
        input=world_json,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout + "\n" + r.stderr)

    out = r.stdout.strip()
    assert out, "expected JSON output on stdout"
    data = json.loads(out)

    # ---- Contract: top-level shape ----
    assert isinstance(data, dict), f"expected object, got {type(data)}"

    # Required keys (stable surface). These should not change without intent.
    required = {"ok", "orbit", "classification"}
    missing = required - set(data.keys())
    assert not missing, f"missing keys: {sorted(missing)}; got keys={sorted(data.keys())}"

    # No surprise top-level keys (tighten later only if desired)
    allowed = required | {"meta", "stats", "warnings"}
    extra = set(data.keys()) - allowed
    assert not extra, f"unexpected keys: {sorted(extra)}; allowed={sorted(allowed)}"

    # Types
    assert isinstance(data["ok"], bool)
    assert isinstance(data["orbit"], list)
    assert isinstance(data["classification"], str)

    # Orbit elements should be JSON-serializable (not bytes, not weird objects)
    for i, state in enumerate(data["orbit"][:10]):
        assert state is None or isinstance(state, (dict, list, str, int, float, bool)), (
            f"orbit[{i}] invalid JSON type: {type(state)}"
        )
