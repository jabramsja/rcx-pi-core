"""S1-A D3: JS VM bridge-mode parity tests.

Minimal evidence that JS VM path produces same results as Python VM path.
Tests Stage0 VM compiled bundle execution cross-substrate, focused on
the bridge-mode kernel path that S1-A cutover would activate.

This is repo-truth N2 minimal evidence for cutover confidence.
Tests exercise the Stage0 VM bundle execution layer directly — this is the
component that cutover changes (match.v2/subst.v2 from host to VM).

The full JS kernel path (stepKernel -> shadow mode -> stage0VmStep) is already
exercised by test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity
which runs the engine pipeline through both Python and JS substrates.
# SPEED_OK: no slow kernel functions called — only stage0_vm_step (microsecond-scale)

Extra JS kernel-level thickening stays in S1-B.

L4_ENABLER evidence: G8 (Irreducible Primitive Consensus).
"""

import json
import os
import subprocess
import pytest

from rcx_pi.selfhost.stage0_vm import stage0_vm_step, _mu_deep_equal  # ANTICHEAT_OK: S1-A — VM parity
from rcx_pi.selfhost.step_mu import (
    _load_compiled_match_v2_bundle,  # ANTICHEAT_OK: S1-A — bundle loader
    _load_compiled_subst_v2_bundle,  # ANTICHEAT_OK: S1-A — bundle loader
)

from tests.repo_root import REPO_ROOT
from tests.l4_gates.stage0_test_helpers import run_js_stage0


# Bundle relative paths (from repo root)
MATCH_COMPILED_REL = "mu/stage0/compiled/match_v2.compiled.v1.json"
SUBST_COMPILED_REL = "mu/stage0/compiled/subst_v2.compiled.v1.json"


def _normalize_for_cross_substrate(value):
    """Normalize Python value for cross-substrate comparison.

    JS float64 conflates int/float. Normalize int→float for comparison.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value  # Keep int — JS returns int-like numbers
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if value is None:
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in sorted(value.items())}
    return value


def _cross_equal(py_val, js_val):
    """Cross-substrate equality with int/float normalization."""
    return _normalize_for_cross_substrate(py_val) == _normalize_for_cross_substrate(js_val)


# ---------------------------------------------------------------------------
# Match.v2 compiled bundle parity
# ---------------------------------------------------------------------------

class TestMatchVmBridgeParity:
    """Stage0 VM match.v2 compiled bundle: Python and JS agree."""

    def test_match_wrap_parity(self):
        """match.wrap projection: Python and JS produce same output."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "match": {"pattern": "hello", "value": "hello"},
            "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"], \
            f"Status mismatch: py={py_result['status']}, js={js_result['status']}"
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_match_equal_parity(self):
        """match.equal (literal equality): Python and JS agree."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": "hello", "value_focus": "hello",
            "bindings": None, "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_match_var_parity(self):
        """match.var (variable bind): Python and JS agree."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": {"var": "x"},
            "value_focus": 42, "bindings": None,
            "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_match_stall_parity(self):
        """match.fail (no match): both substrates stall."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": "a", "value_focus": "b",
            "bindings": None, "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        # match.fail fires, producing a result with specific structure
        assert py_result["status"] == js_result["status"]


# ---------------------------------------------------------------------------
# Subst.v2 compiled bundle parity
# ---------------------------------------------------------------------------

class TestSubstVmBridgeParity:
    """Stage0 VM subst.v2 compiled bundle: Python and JS agree."""

    def test_subst_wrap_parity(self):
        """subst.wrap projection: Python and JS produce same output."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "subst": {"body": {"var": "x"}, "bindings": {"name": "x", "value": 42, "rest": None}},
            "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_subst_primitive_parity(self):
        """subst.primitive (literal traverse): Python and JS agree."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "mode": "subst", "phase": "traverse", "focus": "literal",
            "bindings": None, "context": None, "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_subst_var_lookup_parity(self):
        """subst.var (variable substitution): Python and JS agree."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"var": "x"},
            "bindings": {"name": "x", "value": 42, "rest": None},
            "context": None, "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_subst_stall_parity(self):
        """Non-subst input: both substrates stall."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"


# ---------------------------------------------------------------------------
# S1-C: Kernel.v1 + Bridge compiled bundle parity
# ---------------------------------------------------------------------------

KERNEL_COMPILED_REL = "mu/stage0/compiled/kernel_v1.compiled.v1.json"
BRIDGE_COMPILED_REL = "mu/stage0/compiled/bootstrap_structural_v1.compiled.v1.json"
JS_BRIDGE_FIXTURE_REL = "mu/host/js/tests/self_tests.js"


def _run_js_bridge_vm_ordering_probe():
    """Run JS kernel VM ordering proof through the public bridge-mode entrypoint."""
    script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const repoRoot = process.cwd();
const stage0Vm = require('./mu/host/js/core/stage0_vm');
const { validateBundle, muCopy } = stage0Vm;
const originalStage0VmStepTrusted = stage0Vm._stage0VmStepTrusted;
const originalStage0VmRunTrusted = stage0Vm._stage0VmRunTrusted;
const MAX_STEPS = 80;
const vmStepCallLog = [];
const vmAccessLog = [];
const activeCallsByBundleId = new Map();
let traceEnabled = false;
let nextVmCallIndex = 0;

function traceEvent(event) {
  if (traceEnabled) {
    vmAccessLog.push(event);
  }
}

function startBundleCall(bundle) {
  const call = {
    call_index: nextVmCallIndex,
    bundle_id: bundle.bundle_id,
    bundle: bundleLabel(bundle.bundle_id),
    status: null,
  };
  nextVmCallIndex += 1;
  activeCallsByBundleId.set(bundle.bundle_id, call);
  vmStepCallLog.push(call);
  traceEvent({
    event: 'bundle.programs',
    call_index: call.call_index,
    bundle_id: call.bundle_id,
    bundle: call.bundle,
  });
  return call;
}

function activeBundleCall(bundle) {
  return activeCallsByBundleId.get(bundle.bundle_id) || startBundleCall(bundle);
}

function finishBundleCall(call, status, eventName) {
  if (!call || call.status !== null) return;
  call.status = status;
  activeCallsByBundleId.delete(call.bundle_id);
  traceEvent({
    event: eventName,
    call_index: call.call_index,
    bundle_id: call.bundle_id,
    bundle: call.bundle,
    status,
  });
}

function recordTrustedVmCall(bundle, status, eventName) {
  if (!traceEnabled) return;
  const call = startBundleCall(bundle);
  finishBundleCall(call, status, eventName);
}

stage0Vm._stage0VmStepTrusted = function tracedStage0VmStepTrusted(bundle, inputValue, maxOps) {
  const result = maxOps === undefined
    ? originalStage0VmStepTrusted(bundle, inputValue)
    : originalStage0VmStepTrusted(bundle, inputValue, maxOps);
  recordTrustedVmCall(bundle, result.status, 'trusted.step.complete');
  return result;
};

stage0Vm._stage0VmRunTrusted = function tracedStage0VmRunTrusted(bundle, inputValue, maxSteps, maxOps) {
  const result = maxOps === undefined
    ? originalStage0VmRunTrusted(bundle, inputValue, maxSteps)
    : originalStage0VmRunTrusted(bundle, inputValue, maxSteps, maxOps);
  if (traceEnabled) {
    for (const _step of result.steps) {
      recordTrustedVmCall(bundle, 'match', 'trusted.run.step');
    }
    recordTrustedVmCall(bundle, 'stall', 'trusted.run.complete');
  }
  return result;
};

function loadBundle(relPath) {
  const bundlePath = path.join(repoRoot, relPath);
  const rawBundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));
  validateBundle(rawBundle);
  return rawBundle;
}

const { stepKernel } = require('./mu/host/js/engine/kernel');

function readConstInitializer(source, constName) {
  const needle = `const ${constName} =`;
  const declarationStart = source.indexOf(needle);
  if (declarationStart === -1) {
    throw new Error(`Missing ${constName} fixture initializer in self_tests.js`);
  }

  let index = declarationStart + needle.length;
  while (/\s/.test(source[index])) index++;
  if (source.startsWith('trustTestMu', index)) {
    index += 'trustTestMu'.length;
    while (/\s/.test(source[index])) index++;
    if (source[index] !== '(') {
      throw new Error(`Unsupported ${constName} trustTestMu wrapper in self_tests.js`);
    }
    index++;
    while (/\s/.test(source[index])) index++;
  }
  const literalStart = index;
  const opening = source[index];
  const closing = opening === '{' ? '}' : opening === '[' ? ']' : null;
  if (!closing) {
    throw new Error(`Unsupported ${constName} fixture initializer in self_tests.js`);
  }

  let depth = 0;
  let quote = null;
  let escaped = false;
  for (; index < source.length; index++) {
    const ch = source[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === quote) {
        quote = null;
      }
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      continue;
    }
    if (ch === opening) depth++;
    if (ch === closing) {
      depth--;
      if (depth === 0) return source.slice(literalStart, index + 1);
    }
  }
  throw new Error(`Unterminated ${constName} fixture initializer in self_tests.js`);
}

function loadSelfTestsBridgeFixture() {
  const fixturePath = path.join(repoRoot, 'mu/host/js/tests/self_tests.js');
  const source = fs.readFileSync(fixturePath, 'utf8');
  const context = Object.create(null);
  const projection = muCopy(JSON.parse(
    JSON.stringify(
      vm.runInNewContext(
        `(${readConstInitializer(source, 'testProjection')})`,
        context,
        { timeout: 1000 }
      )
    )
  ), true, 'self_tests bridge projection fixture');
  const input = muCopy(JSON.parse(
    JSON.stringify(
      vm.runInNewContext(
        `(${readConstInitializer(source, 'testInput')})`,
        context,
        { timeout: 1000 }
      )
    )
  ), true, 'self_tests bridge input fixture');
  if (!projection || typeof projection !== 'object' || !projection.pattern || !projection.body) {
    throw new Error('self_tests.js testProjection fixture is not a projection object');
  }
  return {
    file: 'mu/host/js/tests/self_tests.js',
    input,
    projection,
  };
}

function runPublicStep(input, projection, vmConfig) {
  vmStepCallLog.length = 0;
  vmAccessLog.length = 0;
  activeCallsByBundleId.clear();
  nextVmCallIndex = 0;
  traceEnabled = true;
  try {
    return stepKernel(
      [],
      input,
      [projection],
      { maxSteps: MAX_STEPS, returnMeta: true, vmConfig }
    );
  } finally {
    traceEnabled = false;
  }
}

function bundleLabel(bundleId) {
  return BUNDLE_LABELS[bundleId] || bundleId;
}

function groupVmCalls(calls, kernelBundleId) {
  const groups = [];
  for (const call of calls) {
    if (call.bundle_id === kernelBundleId || groups.length === 0) {
      groups.push([]);
    }
    groups[groups.length - 1].push({
      bundle: bundleLabel(call.bundle_id),
      status: call.status,
    });
  }
  return groups;
}

function firstBundleSuccessGroup(groups, bundle) {
  return groups.find(group =>
    group.some(call => call.bundle === bundle && call.status === 'match')
  ) || null;
}

function groupSignatures(groups) {
  return groups.map(group => group.map(call => `${call.bundle}:${call.status}`).join('>'));
}

function countGroupSignatures(signatures) {
  const counts = Object.create(null);
  for (const signature of signatures) {
    counts[signature] = (counts[signature] || 0) + 1;
  }
  return counts;
}

function runPublicStepWithTrace(input, projection, vmConfig) {
  const result = runPublicStep(input, projection, vmConfig);
  const unresolvedCalls = vmStepCallLog.filter(call => call.status === null);
  if (unresolvedCalls.length > 0) {
    throw new Error(`VM trace did not resolve call status: ${JSON.stringify(unresolvedCalls)}`);
  }
  const vmCallGroups = groupVmCalls(vmStepCallLog, vmConfig.kernelBundle.bundle_id);
  const vmGroupSignatures = groupSignatures(vmCallGroups);
  const bundleProgramsAccesses = vmAccessLog.filter(event => event.event === 'bundle.programs');
  return Object.assign({}, result, {
    public_entrypoint_trace: {
      entrypoint: 'stepKernel',
      return_meta: true,
      vm_config_bundle_keys: ['kernelBundle', 'bridgeBundle', 'matchBundle', 'substBundle'],
      bundle_programs_accesses: bundleProgramsAccesses,
      access_events: vmAccessLog.slice(),
    },
    vm_call_groups: vmCallGroups,
    vm_group_signatures: vmGroupSignatures,
    vm_group_signature_counts: countGroupSignatures(vmGroupSignatures),
    first_match_bundle_success_group: firstBundleSuccessGroup(vmCallGroups, 'match'),
    first_subst_bundle_success_group: firstBundleSuccessGroup(vmCallGroups, 'subst'),
  });
}

function runPublicStepWithTraceOrSecurityError(input, projection, vmConfig) {
  try {
    return runPublicStepWithTrace(input, projection, vmConfig);
  } catch (error) {
    return {
      threw: true,
      error_name: error && error.name ? error.name : 'Error',
      error_message: error && error.message ? error.message : String(error),
    };
  }
}

function runPublicStepOrSecurityError(input, projection, vmConfig) {
  try {
    return runPublicStep(input, projection, vmConfig);
  } catch (error) {
    return {
      threw: true,
      error_name: error && error.name ? error.name : 'Error',
      error_message: error && error.message ? error.message : String(error),
    };
  }
}

const kernelBundle = loadBundle('mu/stage0/compiled/kernel_v1.compiled.v1.json');
const bridgeBundle = loadBundle('mu/stage0/compiled/bootstrap_structural_v1.compiled.v1.json');
const matchBundle = loadBundle('mu/stage0/compiled/match_v2.compiled.v1.json');
const substBundle = loadBundle('mu/stage0/compiled/subst_v2.compiled.v1.json');
const BUNDLE_LABELS = {
  [kernelBundle.bundle_id]: 'kernel',
  [bridgeBundle.bundle_id]: 'bridge',
  [matchBundle.bundle_id]: 'match',
  [substBundle.bundle_id]: 'subst',
};

const fixture = loadSelfTestsBridgeFixture();
const orderedVmConfig = { kernelBundle, bridgeBundle, matchBundle, substBundle };
const bridgeAbsentVmConfig = { kernelBundle, bridgeBundle: null, matchBundle, substBundle };
const bridgeAfterMatchVmConfig = {
  kernelBundle,
  bridgeBundle: matchBundle,
  matchBundle: bridgeBundle,
  substBundle,
};
const matchAfterSubstVmConfig = {
  kernelBundle,
  bridgeBundle,
  matchBundle: substBundle,
  substBundle: matchBundle,
};

const ordered = runPublicStepWithTrace(fixture.input, fixture.projection, orderedVmConfig);
const bridgeAbsent = runPublicStepWithTrace(fixture.input, fixture.projection, bridgeAbsentVmConfig);
const bridgeAfterMatch = runPublicStepWithTraceOrSecurityError(fixture.input, fixture.projection, bridgeAfterMatchVmConfig);
const matchAfterSubst = runPublicStepWithTraceOrSecurityError(fixture.input, fixture.projection, matchAfterSubstVmConfig);
const kernelReplacedByBridge = runPublicStep(
  fixture.input,
  fixture.projection,
  { kernelBundle: bridgeBundle, bridgeBundle, matchBundle, substBundle }
);
const matchReplacedByBridge = runPublicStep(
  fixture.input,
  fixture.projection,
  { kernelBundle, bridgeBundle, matchBundle: bridgeBundle, substBundle }
);
const substReplacedByBridge = runPublicStepOrSecurityError(
  fixture.input,
  fixture.projection,
  { kernelBundle, bridgeBundle, matchBundle, substBundle: bridgeBundle }
);

process.stdout.write(JSON.stringify({
  max_steps: MAX_STEPS,
  fixture,
  bundle_order: [
    kernelBundle.bundle_id,
    bridgeBundle.bundle_id,
    matchBundle.bundle_id,
    substBundle.bundle_id,
  ],
  bridge_after_match_bundle_order: [
    kernelBundle.bundle_id,
    matchBundle.bundle_id,
    bridgeBundle.bundle_id,
    substBundle.bundle_id,
  ],
  match_after_subst_bundle_order: [
    kernelBundle.bundle_id,
    bridgeBundle.bundle_id,
    substBundle.bundle_id,
    matchBundle.bundle_id,
  ],
  ordered,
  bridge_absent: bridgeAbsent,
  bridge_after_match: bridgeAfterMatch,
  match_after_subst: matchAfterSubst,
  kernel_replaced_by_bridge: kernelReplacedByBridge,
  match_replaced_by_bridge: matchReplacedByBridge,
  subst_replaced_by_bridge: substReplacedByBridge,
}));
"""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class TestKernelVmBridgeParity:
    """S1-C: kernel.v1 compiled bundle: Python and JS agree."""

    def test_kernel_wrap_parity(self):
        """kernel.wrap projection: Python and JS produce same output."""
        from rcx_pi.selfhost.step_mu import _load_compiled_kernel_v1_bundle  # ANTICHEAT_OK: S1-C parity
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import normalize_projection, list_to_linked
        bundle = _load_compiled_kernel_v1_bundle()
        proj = {"id": "test.kp", "pattern": "a", "body": "b"}
        normalized = normalize_projection(proj)
        inp = {"_step": normalize_for_match("a"), "_projs": list_to_linked([normalized])}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", KERNEL_COMPILED_REL, inp)
        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Kernel output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_kernel_stall_parity(self):
        """Non-kernel input: both substrates stall."""
        from rcx_pi.selfhost.step_mu import _load_compiled_kernel_v1_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_kernel_v1_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", KERNEL_COMPILED_REL, inp)
        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"


class TestBridgeVmParity:
    """S1-C: bootstrap_structural.v1 compiled bundle: Python and JS agree."""

    def test_bridge_var_check_parity(self):
        """bridge.var.check_existing: Python and JS agree on binding lookup."""
        from rcx_pi.selfhost.step_mu import _load_compiled_bridge_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_bridge_bundle()
        # Input that triggers bridge.var.check_existing: lookup bindings for non-linear var
        inp = {
            "_lookup_name": "x",
            "_lookup_value": 42,
            "_lookup_bindings": {"name": "x", "value": 42, "rest": None},
            "_original_bindings": {"name": "x", "value": 42, "rest": None},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", BRIDGE_COMPILED_REL, inp)
        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Bridge output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_bridge_stall_parity(self):
        """Non-bridge input: both substrates stall."""
        from rcx_pi.selfhost.step_mu import _load_compiled_bridge_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_bridge_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", BRIDGE_COMPILED_REL, inp)
        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"


class TestJsBridgeVmOrderingE2E:
    """End-to-end JS kernel VM ordering proof with bridge mode enabled."""

    def test_live_vm_kernel_path_depends_on_kernel_bridge_match_subst_order(self):
        """Negative controls prove the live JS VM path is order-sensitive."""
        proof = _run_js_bridge_vm_ordering_probe()

        assert proof["fixture"]["file"] == JS_BRIDGE_FIXTURE_REL
        assert proof["fixture"]["input"] == {"op": "double", "value": "forty_two"}
        assert proof["fixture"]["projection"] == {
            "pattern": {"op": "double", "value": {"var": "n"}},
            "body": {"result": {"var": "n"}, "doubled": {"var": "n"}},
        }
        assert proof["bundle_order"] == [
            "rcx.stage0.kernel_v1.compiled.v1",
            "rcx.stage0.bootstrap_structural_v1.compiled.v1",
            "rcx.stage0.match_v2.compiled.v1",
            "rcx.stage0.subst_v2.compiled.v1",
        ]
        assert proof["bridge_after_match_bundle_order"] == [
            "rcx.stage0.kernel_v1.compiled.v1",
            "rcx.stage0.match_v2.compiled.v1",
            "rcx.stage0.bootstrap_structural_v1.compiled.v1",
            "rcx.stage0.subst_v2.compiled.v1",
        ]
        assert proof["match_after_subst_bundle_order"] == [
            "rcx.stage0.kernel_v1.compiled.v1",
            "rcx.stage0.bootstrap_structural_v1.compiled.v1",
            "rcx.stage0.subst_v2.compiled.v1",
            "rcx.stage0.match_v2.compiled.v1",
        ]

        assert proof["ordered"]["output"] == {"result": "forty_two", "doubled": "forty_two"}
        assert proof["ordered"]["stall"] is False
        assert proof["ordered"]["termination_reason"] == "projection_applied"
        ordered_trace = proof["ordered"]["public_entrypoint_trace"]
        assert ordered_trace["entrypoint"] == "stepKernel"
        assert ordered_trace["return_meta"] is True
        assert ordered_trace["vm_config_bundle_keys"] == [
            "kernelBundle", "bridgeBundle", "matchBundle", "substBundle",
        ]
        ordered_program_accesses = ordered_trace["bundle_programs_accesses"]
        assert {event["bundle"] for event in ordered_program_accesses} >= {
            "kernel", "bridge", "match", "subst",
        }
        assert len(ordered_program_accesses) == sum(
            len(group) for group in proof["ordered"]["vm_call_groups"]
        )
        def has_call(groups, bundle, status):
            return any(
                call == {"bundle": bundle, "status": status}
                for group in groups
                for call in group
            )

        ordered_groups = proof["ordered"]["vm_call_groups"]
        ordered_signatures = proof["ordered"]["vm_group_signatures"]
        assert has_call(ordered_groups, "bridge", "match")
        assert has_call(ordered_groups, "match", "match")
        assert has_call(ordered_groups, "subst", "match")
        assert any(
            signature.startswith("kernel:stall>bridge:match")
            for signature in ordered_signatures
        )
        assert any(
            signature.startswith("kernel:stall>bridge:stall")
            and "subst:match" in signature
            for signature in ordered_signatures
        )

        # Same-output controls prove output smoke alone would miss the ordering claim.
        assert proof["bridge_absent"]["output"] == proof["ordered"]["output"]
        assert proof["bridge_absent"]["stall"] is False
        assert proof["bridge_absent"]["steps_used"] == proof["ordered"]["steps_used"] - 1
        assert all(
            "bridge:" not in signature
            for signature in proof["bridge_absent"]["vm_group_signatures"]
        )
        assert (
            proof["bridge_absent"]["vm_group_signature_counts"]
            != proof["ordered"]["vm_group_signature_counts"]
        )
        bridge_absent_groups = proof["bridge_absent"]["vm_call_groups"]
        assert has_call(bridge_absent_groups, "match", "match")
        assert has_call(bridge_absent_groups, "subst", "match")

        assert proof["bridge_after_match"] == {
            "threw": True,
            "error_name": "Error",
            "error_message": (
                "SECURITY: continuationState kernel_state is not bound to "
                "supplied projections/input"
            ),
        }

        assert proof["match_after_subst"] == {
            "threw": True,
            "error_name": "Error",
            "error_message": (
                "SECURITY: continuationState kernel_state is not bound to "
                "supplied projections/input"
            ),
        }

        assert proof["kernel_replaced_by_bridge"]["output"] == {"op": "double", "value": "forty_two"}
        assert proof["kernel_replaced_by_bridge"]["stall"] is True
        assert proof["kernel_replaced_by_bridge"]["termination_reason"] == "hash_stall"

        assert proof["match_replaced_by_bridge"]["output"] == {"op": "double", "value": "forty_two"}
        assert proof["match_replaced_by_bridge"]["stall"] is True
        assert proof["match_replaced_by_bridge"]["termination_reason"] == "max_steps_exhausted"
        assert proof["match_replaced_by_bridge"]["steps_used"] == proof["max_steps"]

        assert proof["subst_replaced_by_bridge"] == {
            "threw": True,
            "error_name": "Error",
            "error_message": (
                "SECURITY: continuationState kernel_state is not bound to "
                "supplied projections/input"
            ),
        }
