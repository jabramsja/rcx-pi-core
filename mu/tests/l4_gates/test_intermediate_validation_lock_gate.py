"""
Gate test: Intermediate Validation Lock (F-37)

Proves that JS runAlgorithmWithBridge() validates intermediate results
after denormalize and before re-feeding them into the loop body.

Gap: JS runAlgorithmWithBridge (pipeline.js) denormalizes wrapped.result
and re-feeds as `current` without calling validateAlgorithmRuntimeFields.
Python step_kernel_mu validates output at every exit path (step_mu.py:1474).

Two tests:
1. Behavioral rejection: patched _stepKernelCoreNonMeta returns unsupported
   underscore field (_injected) -> validator rejects at intermediate check.
2. Source lock: validator(next, ...) appears between denormalize(wrapped.result)
   and current = next in pipeline.js source.

Note: _mode and _stall are NOT negative examples -- they are in
ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS (constants.js:119,124).
The real gap is unsupported underscore fields like _injected, _exploit.
"""

import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

JS_PIPELINE = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"


class TestIntermediateValidationBehavior:
    """F-37: JS runAlgorithmWithBridge rejects unsupported underscore fields
    in intermediate results."""

    def test_js_rejects_unsupported_underscore_in_intermediate(self):
        """Patched kernel returns {_injected: true} -> validator rejects."""
        # Patch _stepKernelCoreNonMeta BEFORE requiring pipeline.js.
        # Pipeline destructures _stepKernelCoreNonMeta at module load time
        # (line 17), so we must patch the kernel module export before
        # pipeline is loaded. Node caches by resolved path, so patching
        # the kernel export object before pipeline's require('./kernel')
        # makes pipeline pick up the patched function.
        js_script = (
            "const kernel = require('./mu/host/js/engine/kernel');\n"
            "kernel._stepKernelCore = function(_a, _k, _d, _v, _m, _vm) {\n"  # ANTICHEAT_OK: JS kernel module patch for behavioral gate test
            "  return { output: { _injected: true, value: 42 },\n"
            "           stall: false, termination_reason: 'projection_applied',\n"
            "           steps_used: 1, max_steps: 10000 };\n"
            "};\n"
            "const { runAlgorithmWithBridge } = require('./mu/host/js/engine/pipeline');\n"
            "try {\n"
            "  runAlgorithmWithBridge(\n"
            "    [], {value: 1},\n"
            "    [{pattern: {var: 'x'}, body: {var: 'x'}, id: 'test.identity'}],\n"
            "    10\n"
            "  );\n"
            "  console.log('NO_ERROR');\n"
            "  process.exit(1);\n"
            "} catch (e) {\n"
            "  if (e.message.includes('unsupported algorithm underscore field: _injected')) {\n"
            "    console.log('REJECTED');\n"
            "    process.exit(0);\n"
            "  } else {\n"
            "    console.log('WRONG_ERROR:' + e.message);\n"
            "    process.exit(1);\n"
            "  }\n"
            "}\n"
        )
        result = subprocess.run(
            ["node", "-e", js_script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        assert result.returncode == 0, (
            f"Expected REJECTED but got exit {result.returncode}.\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr[:500]}"
        )
        assert result.stdout.strip() == "REJECTED"


class TestIntermediateValidationSourceLock:
    """Source lock: validator call must sit between denormalize and reassignment
    in runAlgorithmWithBridge loop body."""

    def test_validator_between_denormalize_and_reassignment(self):
        """pipeline.js: validator(next, ...) appears between
        denormalize(wrapped.result) and current = next."""
        source = JS_PIPELINE.read_text()
        lines = source.split('\n')

        denorm_idx = None
        validator_idx = None
        reassign_idx = None

        for i, line in enumerate(lines):
            # Wave 1: runAlgorithmWithBridge now uses canonical _stepKernelCore
            # Output is already denormalized (canonical.output)
            if 'canonical.output' in line or 'denormalize(wrapped.result)' in line:
                denorm_idx = i
            if denorm_idx is not None and validator_idx is None:
                if 'validator(next' in line and 'intermediate' in line:
                    validator_idx = i
            if denorm_idx is not None and 'current = next' in line:
                reassign_idx = i
                break

        assert denorm_idx is not None, (
            "pipeline.js: missing canonical.output or denormalize(wrapped.result) — "
            "runAlgorithmWithBridge loop body structure changed"
        )
        assert reassign_idx is not None, (
            "pipeline.js: missing 'current = next' after output extraction — "
            "runAlgorithmWithBridge loop body structure changed"
        )
        assert validator_idx is not None, (
            "pipeline.js: missing validator(next, '...intermediate...') — "
            "F-37 intermediate validation call not found between "
            "denormalize and reassignment"
        )
        assert denorm_idx < validator_idx < reassign_idx, (
            f"pipeline.js: validator call at line {validator_idx + 1} is not "
            f"between denormalize (line {denorm_idx + 1}) and "
            f"reassignment (line {reassign_idx + 1})"
        )
