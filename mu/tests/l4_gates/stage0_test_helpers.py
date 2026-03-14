"""Shared test helpers for Stage0 VM tests.

Extracted to avoid triplication of the JS subprocess runner across
test_stage0_vm.py, test_lower_stage0.py, and parity tests.
"""

import json
import os
import subprocess

from tests.repo_root import REPO_ROOT


def source_step(projections, input_value):
    """Run the host Stage0 path (_step_trusted) on input_value (single step).

    Extracted to avoid duplication across test_stage0_vm.py and
    test_lower_stage0.py.
    """
    from rcx_pi.selfhost.eval_seed import _step_trusted  # ANTICHEAT_OK: parity evidence against source path
    return _step_trusted(projections, input_value)


def run_js_stage0(action, bundle_path, input_value=None):
    """Call JS Stage0 VM via subprocess and return parsed result.

    Args:
        action: "validate", "step", or "run".
        bundle_path: Relative path to bundle JSON (from repo root).
        input_value: Optional input Mu value for step/run actions.

    Returns:
        Parsed JSON response from the JS runner.

    Raises:
        RuntimeError: If the JS runner produces no JSON response.
    """
    request = {"action": action, "bundle_path": bundle_path}
    if input_value is not None:
        request["input"] = input_value
    runner = os.path.join(str(REPO_ROOT), "tests", "l4_gates",
                          "stage0_vm_runner.js")
    result = subprocess.run(
        ["node", runner, json.dumps(request)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=30,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"JS runner produced no JSON response.\n"
        f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}")
