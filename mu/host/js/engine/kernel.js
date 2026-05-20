'use strict';
/**
 * RCX Engine Kernel
 *
 * stepKernel, runStructural, stepKernelStructural.
 * These are kernel orchestration, NOT bootstrap primitives.
 *
 * Depends on: core/*
 */

const { NO_MATCH, RcxError } = require('../core/constants');
const { isValidMu, muHash, muHashCached, muHashControlCached } = require('../core/types');
const muContainers = require('../core/container_factory');
const { normalize, denormalize, normalizeProjection, listToLinked } = require('../core/normalize');
const { validateNoKernelReservedFields, validateAlgorithmRuntimeFields, rejectNonlinearProjections } = require('../core/security');
const { step, match, isKernelTerminal, isKernelIntermediate, makeUndefinedMotif, _stepTrusted, _applyProjectionTrusted } = require('../core/bootstrap_core');
const { _stage0VmStepTrusted, muDeepEqual } = require('../core/stage0_vm'); // W6A: trusted path — bundles loaded at module level in main.js // CONTRABAND_OK: stage0_vm is our module, not Node.js vm

// S1-B: VM cutover flags (parity with Python step_mu.py)
// Founder GO 2026-03-15: VM path is now primary for match.v2/subst.v2
const _STAGE0_VM_CUTOVER = true;
let _STAGE0_SHADOW_ENABLED = false; // Shadow disabled (cutover=true makes shadow dead code)

/**
 * S1-C: Kernel step — ALL projections via Stage0 VM.
 * No coverage system in JS — pure execution only.
 * Parity with Python _step_kernel_with_vm in step_mu.py.
 */
function _assertVmMatchResult(result, bundleId) {
  // NB10 fix: fail-closed assertion on VM match result shape (parity with Python KeyError)
  // null is valid Mu (void/no-structure). Only reject undefined (missing field).
  if (result.root === undefined) {
    throw new Error(
      `SECURITY: _stage0VmStepTrusted returned status='match' for ${bundleId} but .root is undefined. ` +
      `Bundle may be malformed or VM produced invalid output.`);
  }
}

/**
 * W6A trusted path: bundles MUST be pre-validated via main.js loader.
 * Callers constructing custom vmConfig MUST call validateBundle() on each bundle
 * before passing to this function. Unvalidated bundles may cause internal errors
 * or mis-dispatch (fail-open). See main.js lines 237-245 for validation pattern.
 */
function _stepKernelWithVM(kernelBundle, bridgeBundle, matchBundle, substBundle, inputValue) {
  // 1. kernel.v1 via Stage0 VM (S1-C: was host _applyProjectionTrusted)
  const kernelResult = _stage0VmStepTrusted(kernelBundle, inputValue);
  if (kernelResult.status === 'match') { _assertVmMatchResult(kernelResult, 'kernel.v1'); return kernelResult.root; }

  // 2. bridge via Stage0 VM (S1-C: was host _applyProjectionTrusted)
  if (bridgeBundle) {
    const bridgeResult = _stage0VmStepTrusted(bridgeBundle, inputValue);
    if (bridgeResult.status === 'match') { _assertVmMatchResult(bridgeResult, 'bridge'); return bridgeResult.root; }
  }

  // 3. match.v2 via Stage0 VM
  const matchResult = _stage0VmStepTrusted(matchBundle, inputValue);
  if (matchResult.status === 'match') { _assertVmMatchResult(matchResult, 'match.v2'); return matchResult.root; }

  // 4. subst.v2 via Stage0 VM
  const substResult = _stage0VmStepTrusted(substBundle, inputValue);
  if (substResult.status === 'match') { _assertVmMatchResult(substResult, 'subst.v2'); return substResult.root; }

  return inputValue; // stall
}

/**
 * Internal: kernel loop only (returnMeta path).
 * Caller must provide pre-validated, pre-normalized kernelInput.
 * No input/projection validation or normalization — just the state machine.
 *
 * @host_iteration — residual kernel driver watchdog; supplied Mu fuel owns progress.
 * Caller-supplied kernelFuel consumes one Mu linked-list node per kernel step.
 * Omitted kernelFuel preserves the legacy no-fuel watchdog path without
 * synthesizing a host-counted compatibility fuel budget from maxSteps.
 * Removing that omitted-fuel path requires a separate Mu continuation-state
 * caller migration; do not hide it behind helper, recursion, or synthetic
 * maxSteps-derived fuel.
 */
function _stepKernelCore(kernelProjections, kernelInput, domainInput, validator, maxSteps, vmConfig, kernelFuel = undefined) {
  if (typeof maxSteps !== 'number' || !Number.isFinite(maxSteps) || !Number.isInteger(maxSteps)) {
    throw new RcxError(
      'api.bad_request',
      `maxSteps must be a finite integer watchdog, got ${typeof maxSteps}`
    );
  }
  if (maxSteps < 0) {
    throw new RcxError('api.bad_request', `maxSteps must be >= 0, got ${maxSteps}`);
  }
  let current = kernelInput;
  let currentHash = muHashControlCached(kernelInput, 'stepKernel');
  const callerSuppliedFuel = kernelFuel !== undefined;
  let fuelCursor = kernelFuel;
  let stepsUsed = 0;
  while (!callerSuppliedFuel || fuelCursor !== null) {
    if (stepsUsed >= maxSteps) {
      validator(domainInput, 'stepKernel output');
      const meta = {
        output: domainInput,
        stall: true,
        termination_reason: 'max_steps_exhausted',
        steps_used: stepsUsed,
        max_steps: maxSteps,
      };
      if (callerSuppliedFuel) {
        meta.fuel_supplied = true;
        meta.fuel_remaining = fuelCursor;
        meta.fuel_exhausted = false;
      }
      return meta;
    }

    if (callerSuppliedFuel) {
      if (typeof fuelCursor !== 'object' || Array.isArray(fuelCursor) ||
          !Object.hasOwn(fuelCursor, 'head') || !Object.hasOwn(fuelCursor, 'tail')) {
        throw new Error('SECURITY: kernelFuel must be a Mu head/tail linked list');
      }
    }

    let result = undefined;
    if (vmConfig && _STAGE0_VM_CUTOVER) {
      result = _stepKernelWithVM(
        vmConfig.kernelBundle, vmConfig.bridgeBundle,
        vmConfig.matchBundle, vmConfig.substBundle, current);
    } else {
      result = _stepTrusted(kernelProjections, current);
      // P7-d shadow: run VM path too, assert equivalence
      if (vmConfig && _STAGE0_SHADOW_ENABLED) {
        const vmResult = _stepKernelWithVM(
          vmConfig.kernelBundle, vmConfig.bridgeBundle,
          vmConfig.matchBundle, vmConfig.substBundle, current);
        const hostStalled = result === current;
        const vmStalled = vmResult === current;
        if (hostStalled !== vmStalled) {
          throw new Error(
            `P7-d shadow: polarity divergence — hostStalled=${hostStalled}, vmStalled=${vmStalled}`);
        }
        if (!hostStalled && !muDeepEqual(result, vmResult)) {
          throw new Error(
            `P7-d shadow: output divergence`);
        }
      }
    }
    if (callerSuppliedFuel) {
      fuelCursor = fuelCursor.tail;
    }
    stepsUsed++;

    if (isKernelTerminal(result)) {
      const stall = result._stall === true;
      const reason = stall ? 'kernel_stall' : 'projection_applied';
      if (stall) {
        validator(domainInput, 'stepKernel output');
        const meta = {
          output: domainInput,
          stall: true,
          termination_reason: reason,
          steps_used: stepsUsed,
          max_steps: maxSteps,
          undefined_motif: makeUndefinedMotif('kernel', domainInput, null, 'no_matching_projection'),
        };
        if (callerSuppliedFuel) {
          meta.fuel_supplied = true;
          meta.fuel_remaining = fuelCursor;
          meta.fuel_exhausted = false;
        }
        return meta;
      }
      const output = denormalize(result._result);
      validator(output, 'stepKernel output');
      const meta = { output, stall: false, termination_reason: reason, steps_used: stepsUsed, max_steps: maxSteps };
      if (callerSuppliedFuel) {
        meta.fuel_supplied = true;
        meta.fuel_remaining = fuelCursor;
        meta.fuel_exhausted = false;
      }
      return meta;
    }

    if (!isKernelIntermediate(result)) {
      const resultHash = muHashControlCached(result, 'stepKernel.stall');
      if (resultHash === currentHash) {
        validator(domainInput, 'stepKernel output');
        const meta = { output: domainInput, stall: true, termination_reason: 'hash_stall', steps_used: stepsUsed, max_steps: maxSteps };
        if (callerSuppliedFuel) {
          meta.fuel_supplied = true;
          meta.fuel_remaining = fuelCursor;
          meta.fuel_exhausted = false;
        }
        return meta;
      }
      currentHash = resultHash;
    }

    current = result;
  }
  validator(domainInput, 'stepKernel output');
  const meta = {
    output: domainInput,
    stall: true,
    termination_reason: 'fuel_exhausted',
    steps_used: stepsUsed,
    max_steps: maxSteps,
  };
  if (callerSuppliedFuel) {
    meta.fuel_supplied = true;
    meta.fuel_remaining = fuelCursor;
    meta.fuel_exhausted = true;
  }
  return meta;
}

// _stepKernelCoreNonMeta DELETED (Wave 1).
// Replaced by _stepKernelCore + public adapter shim in stepKernel().
// All internal callers now use _stepKernelCore directly.

/**
 * BOOTSTRAP PRIMITIVE: Kernel entry point with security validation.
 * Validates domain input before wrapping with kernel state.
 */
function stepKernel(projections, domainInput, domainProjections, options = {}) {
  const {
    maxSteps = 10000,
    shouldNormalize = true,
    validationMode = 'domain',
    returnMeta = false,
    kernelFuel = undefined,
  } = options;
  const hasKernelFuel = Object.hasOwn(options, 'kernelFuel');
  if (typeof maxSteps !== 'number' || !Number.isFinite(maxSteps) || !Number.isInteger(maxSteps)) {
    throw new RcxError(
      'api.bad_request',
      `maxSteps must be a finite integer watchdog, got ${typeof maxSteps}`
    );
  }
  if (maxSteps < 0) {
    throw new RcxError('api.bad_request', `maxSteps must be >= 0, got ${maxSteps}`);
  }

  let validator;
  if (validationMode === 'domain') {
    validator = validateNoKernelReservedFields;
  } else if (validationMode === 'algorithm_runtime') {
    validator = validateAlgorithmRuntimeFields;
  } else {
    throw new Error(
      `SECURITY: invalid validationMode '${validationMode}'. ` +
      `Expected 'domain' or 'algorithm_runtime'.`
    );
  }

  // SECURITY: Validate input and projection payloads at selected boundary mode.
  validator(domainInput, 'domainInput');
  for (let i = 0; i < domainProjections.length; i++) {
    const proj = domainProjections[i];
    if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) {
      throw new Error(
        `SECURITY: domainProjections[${i}] must be an object, got ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`
      );
    }
    if (!('pattern' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'pattern' key`);
    }
    if (!('body' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'body' key`);
    }
    if (!isValidMu(proj.pattern)) {
      throw new Error(`SECURITY: domainProjections[${i}].pattern is not valid Mu`);
    }
    if (!isValidMu(proj.body)) {
      throw new Error(`SECURITY: domainProjections[${i}].body is not valid Mu`);
    }
    validator(proj.pattern, `domainProjections[${i}].pattern`);
    validator(proj.body, `domainProjections[${i}].body`);

    const projId = (typeof proj.id === 'string') ? proj.id : '';
    if (projId.startsWith('kernel.')) {
      throw new Error(
        `SECURITY: stepKernel expects DOMAIN projections only, ` +
        `got kernel projection at index ${i}: ${projId}`
      );
    }
  }

  // SECURITY: Reject non-linear domain projections (fail-closed).
  // Core kernel (match.v2) silently overwrites bindings on repeated variables.
  // step_kernel_meta(kernelMode='bridge') is still treated as a direct external
  // kernel API — non-linear domain projections are rejected here regardless.
  // Bridge algorithm execution (runAlgorithmWithBridge) bypasses stepKernel entirely.
  rejectNonlinearProjections(domainProjections, 'stepKernel');

  if (hasKernelFuel) {
    if (!isValidMu(kernelFuel)) {
      throw new Error('SECURITY: kernelFuel must be valid Mu linked-list data');
    }
    let fuelCursor = kernelFuel;
    for (let fuelNodeCount = 0; fuelCursor !== null; fuelNodeCount++) {
      if (typeof fuelCursor !== 'object' || Array.isArray(fuelCursor) ||
          !Object.hasOwn(fuelCursor, 'head') || !Object.hasOwn(fuelCursor, 'tail') ||
          Object.keys(fuelCursor).length !== 2) {
        throw new Error('SECURITY: kernelFuel must be a Mu head/tail linked list');
      }
      fuelCursor = fuelCursor.tail;
    }
  }

  const normalizedInput = shouldNormalize ? normalize(domainInput) : domainInput;
  const normalizedProjs = shouldNormalize
    ? domainProjections.map(normalizeProjection)
    : domainProjections;
  const kernelDomainProjs = normalizedProjs.map(proj => muContainers.record([
    ['pattern', proj.pattern],
    ['body', proj.body],
  ]));

  const kernelInput = muContainers.record([
    ['_step', normalizedInput],
    ['_projs', listToLinked(kernelDomainProjs)],
  ]);

  // P7-d: Build vmConfig from options if bundles provided
  const vmConfig = options.vmConfig || null;

  if (returnMeta) {
    return _stepKernelCore(projections, kernelInput, domainInput, validator, maxSteps, vmConfig, hasKernelFuel ? kernelFuel : undefined);
  }

  // Non-meta mode: compatibility shim over canonical _stepKernelCore.
  // Preserves FULL legacy { result, steps, stalled, trace } observable behavior.
  // result = normalize(output) so caller's denormalize() round-trips correctly.
  // stalled preserves legacy semantics (false on max-steps — NB4 public debt deferred).
  const canonical = _stepKernelCore(projections, kernelInput, domainInput, validator, maxSteps, vmConfig, hasKernelFuel ? kernelFuel : undefined);
  const isFuelExhaustion = canonical.termination_reason === 'fuel_exhausted';
  const isLegacyStall = canonical.termination_reason === 'hash_stall' || canonical.termination_reason === 'kernel_stall' || isFuelExhaustion;
  return muContainers.record([
    ['result', normalize(canonical.output)],  // re-normalize so caller denormalize() works
    ['steps', isFuelExhaustion ? canonical.steps_used : isLegacyStall ? canonical.steps_used - 1 : canonical.steps_used],  // legacy uses 0-indexed steps on stall
    ['stalled', isLegacyStall],  // legacy: false on max-steps (NB4 public debt deferred)
    ['trace', muContainers.list()],
  ]);
}

/**
 * Phase 8d: Run with structural trace accumulation.
 * Parameterized: takes kernelProjections instead of module-global.
 *
 * BOUNDARY: Trace infrastructure — off kernel path. Reclassified P7W5: was host iteration marker.
 */
function runStructural(kernelProjections, domainProjections, input, maxSteps = 10000, vmConfig = null) {
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to runStructural()');
  }
  validateNoKernelReservedFields(input, 'runStructural input');

  for (let idx = 0; idx < domainProjections.length; idx++) {
    const proj = domainProjections[idx];
    if (typeof proj === 'object' && proj !== null) {
      if ('pattern' in proj) {
        validateNoKernelReservedFields(proj.pattern, `runStructural projection[${idx}].pattern`);
      }
      if ('body' in proj) {
        validateNoKernelReservedFields(proj.body, `runStructural projection[${idx}].body`);
      }
      // SECURITY: Reject kernel-prefixed projection IDs (parity with stepKernel guard).
      const projId = (typeof proj.id === 'string') ? proj.id : '';
      if (projId.startsWith('kernel.')) {
        throw new Error(
          `SECURITY: runStructural expects DOMAIN projections only, ` +
          `got kernel projection at index ${idx}: ${projId}`
        );
      }
    }
  }

  // SECURITY: Reject non-linear domain projections (fail-closed).
  // Mirrors stepKernel guard — runStructural is also a direct external entry point.
  rejectNonlinearProjections(domainProjections, 'runStructural');

  // Pre-normalize projections once (constant across all trace steps).
  const validator = validateNoKernelReservedFields;
  const normalizedProjs = domainProjections.map(normalizeProjection);
  const kernelDomainProjs = normalizedProjs.map(proj => muContainers.record([
    ['pattern', proj.pattern],
    ['body', proj.body],
  ]));
  const linkedProjs = listToLinked(kernelDomainProjs);

  const traceEntries = muContainers.list();
  let current = input;
  let currentHash = muHashControlCached(input, 'runStructural');

  for (let i = 0; i < maxSteps; i++) {
    const normalizedCurrent = normalize(current);
    const kernelInput = muContainers.record([
      ['_step', normalizedCurrent],
      ['_projs', linkedProjs],
    ]);
    const meta = _stepKernelCore(kernelProjections, kernelInput, current, validator, 10000, vmConfig);
    const result = meta.output;
    // Resolve matched projection ID: use Stage 0 match (proven equivalent
    // to match.v2 by parity tests). First-match-wins: first projection whose
    // pattern matches current is the one the kernel applied.
    // O(N) match calls vs the previous O(N*K) kernel runs per step.
    let matchedId = null;
    if (meta.termination_reason === 'projection_applied') {
      for (const proj of domainProjections) {
        if (typeof proj === 'object' && proj !== null && 'pattern' in proj) {
          const bindings = match(proj.pattern, current);
          if (bindings !== NO_MATCH) {
            matchedId = proj.id ?? null;
            break;
          }
        }
      }
    }

    validateNoKernelReservedFields(result, 'runStructural output');
    const traceEntry = muContainers.record([
      ['step', i],
      ['state', current],
      ['projection', matchedId],
    ]);
    traceEntries.push(traceEntry);

    const resultHash = muHashControlCached(result, 'runStructural.stall');
    if (resultHash === currentHash) {
      const stallEntry = muContainers.record([
        ['step', i + 1],
        ['state', result],
        ['projection', null],
        ['stall', true],
      ]);
      traceEntries.push(stallEntry);
      return muContainers.record([
        ['result', result],
        ['trace', listToLinked(traceEntries)],
        ['stall', true],
        ['steps', i + 1],
      ]);
    }

    current = result;
    currentHash = resultHash;
  }

  const maxEntry = muContainers.record([
    ['step', maxSteps],
    ['state', current],
    ['projection', null],
    ['max_steps', true],
  ]);
  traceEntries.push(maxEntry);
  return muContainers.record([
    ['result', current],
    ['trace', listToLinked(traceEntries)],
    ['stall', false],
    ['steps', maxSteps],
  ]);
}

/**
 * Phase 8d: stepKernel with structural trace.
 * Parameterized: takes kernelProjections instead of module-global.
 */
function stepKernelStructural(kernelProjections, domainProjections, domainInput, options = {}) {
  const { maxSteps = 10000, vmConfig = null } = options;
  return runStructural(kernelProjections, domainProjections, domainInput, maxSteps, vmConfig);
}

module.exports = {
  stepKernel,
  runStructural,
  stepKernelStructural,
  // Internal: exported for pipeline.js canonical kernel step
  _stepKernelCore,
  // P7-d: exported for shadow mode control and testing
  _stepKernelWithVM,
  get _STAGE0_SHADOW_ENABLED() { return _STAGE0_SHADOW_ENABLED; },
  set _STAGE0_SHADOW_ENABLED(v) { _STAGE0_SHADOW_ENABLED = v; },
};
