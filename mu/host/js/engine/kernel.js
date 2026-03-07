'use strict';
/**
 * RCX Engine Kernel
 *
 * stepKernel, resolveTraceProjectionId, runStructural, stepKernelStructural.
 * These are kernel orchestration, NOT bootstrap primitives.
 *
 * Depends on: core/*
 */

const { NO_MATCH, RcxError } = require('../core/constants');
const { isValidMu, muHash, muHashCached, muHashControlCached } = require('../core/types');
const { normalize, denormalize, normalizeProjection, listToLinked } = require('../core/normalize');
const { validateNoKernelReservedFields, validateAlgorithmRuntimeFields, rejectNonlinearProjections } = require('../core/security');
const { step, match, isKernelTerminal, isKernelIntermediate, makeUndefinedMotif, _stepTrusted } = require('../core/bootstrap_core');

/**
 * Internal: kernel loop only (returnMeta path).
 * Caller must provide pre-validated, pre-normalized kernelInput.
 * No validation, no normalization — just the state machine.
 */
function _stepKernelCore(kernelProjections, kernelInput, domainInput, validator, maxSteps) {
  let current = kernelInput;
  let currentHash = muHashControlCached(kernelInput, 'stepKernel');
  for (let i = 0; i < maxSteps; i++) {
    const result = _stepTrusted(kernelProjections, current);

    if (isKernelTerminal(result)) {
      const stall = result._stall === true;
      const reason = stall ? 'kernel_stall' : 'projection_applied';
      if (stall) {
        validator(domainInput, 'stepKernel output');
        return {
          output: domainInput,
          stall: true,
          termination_reason: reason,
          steps_used: i + 1,
          max_steps: maxSteps,
          undefined_motif: makeUndefinedMotif('kernel', domainInput, null, 'no_matching_projection'),
        };
      }
      const output = denormalize(result._result);
      validator(output, 'stepKernel output');
      return { output, stall: false, termination_reason: reason, steps_used: i + 1, max_steps: maxSteps };
    }

    if (!isKernelIntermediate(result)) {
      const resultHash = muHashControlCached(result, 'stepKernel.stall');
      if (resultHash === currentHash) {
        validator(domainInput, 'stepKernel output');
        return { output: domainInput, stall: true, termination_reason: 'hash_stall', steps_used: i + 1, max_steps: maxSteps };
      }
      currentHash = resultHash;
    }

    current = result;
  }
  validator(domainInput, 'stepKernel output');
  return { output: domainInput, stall: true, termination_reason: 'max_steps_exhausted', steps_used: maxSteps, max_steps: maxSteps };
}

/**
 * Internal: kernel loop only (non-meta path).
 * Caller must provide pre-validated, pre-normalized kernelInput.
 * No validation, no normalization — just the state machine.
 * Returns { result, steps, stalled, trace } (non-meta shape).
 */
function _stepKernelCoreNonMeta(kernelProjections, kernelInput, maxSteps) {
  let current = kernelInput;
  let currentHash = muHashControlCached(kernelInput, 'stepKernel.nonmeta');
  const trace = [];
  for (let i = 0; i < maxSteps; i++) {
    const next = _stepTrusted(kernelProjections, current);

    if (!isKernelIntermediate(next)) {
      const nextHash = muHashControlCached(next, 'stepKernel.nonmeta.stall');
      if (nextHash === currentHash) {
        return { result: current, steps: i, stalled: true, trace };
      }
      currentHash = nextHash;
    }

    current = next;
  }
  return { result: current, steps: maxSteps, stalled: false, trace };
}

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
  } = options;

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

  const normalizedInput = shouldNormalize ? normalize(domainInput) : domainInput;
  const normalizedProjs = shouldNormalize
    ? domainProjections.map(normalizeProjection)
    : domainProjections;
  const kernelDomainProjs = normalizedProjs.map(proj => ({
    pattern: proj.pattern,
    body: proj.body
  }));

  const kernelInput = {
    _step: normalizedInput,
    _projs: listToLinked(kernelDomainProjs)
  };

  if (returnMeta) {
    return _stepKernelCore(projections, kernelInput, domainInput, validator, maxSteps);
  }

  // Non-meta mode
  return _stepKernelCoreNonMeta(projections, kernelInput, maxSteps);
}

/**
 * Gate 5 parity: Resolve which projection produced nextValue from current.
 * Parameterized: takes kernelProjections instead of module-global.
 */
function resolveTraceProjectionId(kernelProjections, domainProjections, current, nextValue) {
  const nextValueHash = muHashControlCached(nextValue, 'resolveTraceProjectionId');
  for (const proj of domainProjections) {
    if (typeof proj !== 'object' || proj === null) continue;
    if (!('pattern' in proj) || !('body' in proj)) continue;
    const candidate = stepKernel(kernelProjections, current, [proj], {
      validationMode: 'domain',
      returnMeta: true,
    });
    if (candidate.stall) continue;
    if (muHashControlCached(candidate.output, 'resolveTraceProjectionId.match') === nextValueHash) {
      return proj.id ?? null;
    }
  }
  return null;
}

/**
 * Internal: resolve projection ID using pre-validated, pre-normalized state.
 * Same algorithm as resolveTraceProjectionId but skips redundant
 * validation/normalization/linking that was already done in runStructural.
 * Gate 5 parity: still probes each projection through the full kernel loop.
 */
function _resolveIdFast(kernelProjections, domainProjections, normalizedProjs, singleLinkedProjs,
                        normalizedCurrent, rawCurrent, nextValue, validator) {
  const nextValueHash = muHashControlCached(nextValue, 'resolveTraceProjectionId');
  for (let j = 0; j < normalizedProjs.length; j++) {
    const proj = normalizedProjs[j];
    if (typeof proj !== 'object' || proj === null) continue;
    if (!('pattern' in proj) || !('body' in proj)) continue;

    const kernelInput = { _step: normalizedCurrent, _projs: singleLinkedProjs[j] };
    const candidate = _stepKernelCore(kernelProjections, kernelInput, rawCurrent, validator, 10000);

    if (candidate.stall) continue;
    if (muHashControlCached(candidate.output, 'resolveTraceProjectionId.match') === nextValueHash) {
      return domainProjections[j].id ?? null;
    }
  }
  return null;
}

/**
 * Phase 8d: Run with structural trace accumulation.
 * Parameterized: takes kernelProjections instead of module-global.
 *
 * @host_iteration — for loop until stall/max_steps with trace
 */
function runStructural(kernelProjections, domainProjections, input, maxSteps = 10000) {
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
  // Eliminates redundant normalize/validate/link per stepKernel + resolveId call.
  const validator = validateNoKernelReservedFields;
  const normalizedProjs = domainProjections.map(normalizeProjection);
  const kernelDomainProjs = normalizedProjs.map(proj => ({
    pattern: proj.pattern,
    body: proj.body
  }));
  const linkedProjs = listToLinked(kernelDomainProjs);
  const singleLinkedProjs = kernelDomainProjs.map(proj => listToLinked([proj]));

  const traceEntries = [];
  let current = input;
  let currentHash = muHashControlCached(input, 'runStructural');

  for (let i = 0; i < maxSteps; i++) {
    const normalizedCurrent = normalize(current);
    const kernelInput = { _step: normalizedCurrent, _projs: linkedProjs };
    const meta = _stepKernelCore(kernelProjections, kernelInput, current, validator, 10000);
    const result = meta.output;
    const matchedId = _resolveIdFast(
      kernelProjections, domainProjections, normalizedProjs, singleLinkedProjs,
      normalizedCurrent, current, result, validator
    );

    validateNoKernelReservedFields(result, 'runStructural output');
    traceEntries.push({
      step: i,
      state: current,
      projection: matchedId
    });

    const resultHash = muHashControlCached(result, 'runStructural.stall');
    if (resultHash === currentHash) {
      traceEntries.push({
        step: i + 1,
        state: result,
        projection: null,
        stall: true
      });
      return {
        result: result,
        trace: listToLinked(traceEntries),
        stall: true,
        steps: i + 1
      };
    }

    current = result;
    currentHash = resultHash;
  }

  traceEntries.push({
    step: maxSteps,
    state: current,
    projection: null,
    max_steps: true
  });
  return {
    result: current,
    trace: listToLinked(traceEntries),
    stall: false,
    steps: maxSteps
  };
}

/**
 * Phase 8d: stepKernel with structural trace.
 * Parameterized: takes kernelProjections instead of module-global.
 */
function stepKernelStructural(kernelProjections, domainProjections, domainInput, options = {}) {
  const { maxSteps = 10000 } = options;
  return runStructural(kernelProjections, domainProjections, domainInput, maxSteps);
}

module.exports = {
  stepKernel,
  resolveTraceProjectionId,
  runStructural,
  stepKernelStructural,
  // Internal: exported for pipeline.js pre-validation optimization
  _stepKernelCoreNonMeta,
};
