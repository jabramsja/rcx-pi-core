'use strict';
/**
 * RCX Engine Pipeline
 *
 * runEnginePipeline, runEnginePipelineRecursive, serviceBoundaryEffect,
 * runSubAlgorithm, runAlgorithmWithBridge, hashTraceForRecurrence.
 *
 * Depends on: core/*, core/terminal_classification.js, engine/kernel.js
 */

const { KERNEL_RESERVED_FIELDS, RcxError } = require('../core/constants');
const { isValidMu, muHash, muEqual, muHashCached } = require('../core/types');
const { denormalize } = require('../core/normalize');
const { validateNoKernelReservedFields } = require('../core/security');
const { step } = require('../core/bootstrap_core');
const { isTerminalShape, isEngineTerminal, deriveEngineExitReason } = require('../core/terminal_classification');
const { stepKernel, runStructural } = require('./kernel');

// JS built-in property names that must never be used as inject_key.
// Prevents prototype chain poisoning via boundary requests.
const FORBIDDEN_INJECT_KEYS = new Set([
  '__proto__', 'constructor', 'toString', 'valueOf',
  'hasOwnProperty', 'isPrototypeOf', 'propertyIsEnumerable',
  'toLocaleString', '__defineGetter__', '__defineSetter__',
  '__lookupGetter__', '__lookupSetter__',
]);

/**
 * Run an algorithm (recurrence/exhaustion) through bridge-backed meta-circular kernel.
 * @host_iteration (bridge-backed algorithm execution loop)
 */
function runAlgorithmWithBridge(allProjs, input, domainProjs, maxSteps) {
  let current = input;
  let steps = 0;
  const limit = maxSteps ?? 200;
  while (steps < limit) {
    const wrapped = stepKernel(
      allProjs, current, domainProjs,
      { validationMode: 'algorithm_runtime' }
    );
    const next = denormalize(wrapped.result);
    if (muEqual(current, next)) break;
    current = next;
    steps++;
  }
  return current;
}

/**
 * Run a sub-algorithm (recurrence/exhaustion) to completion.
 * Mirrors Python _run_sub_algorithm() (step_mu.py:1404).
 * Parameterized: takes kernelProjections and seedProjectionMap.
 */
function runSubAlgorithm(kernelProjections, seedProjectionMap, algorithmProjs, initial, maxIterations) {
  let current = initial;
  let currentHash = muHashCached(initial);
  for (let i = 0; i < maxIterations; i++) {
    const result = runAlgorithmWithBridge(kernelProjections, current, algorithmProjs, 200);
    if (isTerminalShape(result)) return result;
    const resultHash = muHashCached(result);
    if (resultHash === currentHash) return result;
    current = result;
    currentHash = resultHash;
  }
  return current;
}

/**
 * Add state_hash to each entry in a Mu linked-list trace.
 * Mirrors Python hash_trace_for_recurrence() (step_mu.py:1546-1589).
 * FAIL-CLOSED: throws on cycle or overcap.
 */
function hashTraceForRecurrence(trace, maxEntries) {
  maxEntries = maxEntries ?? 10000;
  const MAX_TRACE_ENTRIES_HARD_CAP = 100000;
  if (maxEntries > MAX_TRACE_ENTRIES_HARD_CAP) maxEntries = MAX_TRACE_ENTRIES_HARD_CAP;
  const entries = [];
  const visited = new Set();
  let current = trace;
  while (current !== null && typeof current === 'object' && 'head' in current) {
    if (visited.has(current)) {
      throw new RcxError('trace.cycle_detected', 'hash_trace_for_recurrence: cyclic linked list detected');
    }
    visited.add(current);
    if (entries.length >= maxEntries) {
      throw new RcxError('trace.overcap', `hash_trace_for_recurrence: trace exceeds ${maxEntries} entries`);
    }
    let entry = current.head;
    if (entry !== null && typeof entry === 'object' && 'state' in entry) {
      entry = Object.assign(Object.create(null), entry);
      if (isValidMu(entry.state)) {
        entry.state_hash = muHash(entry.state);
      }
    }
    entries.push(entry);
    current = current.tail !== undefined ? current.tail : null;
  }
  let result = current;
  for (let i = entries.length - 1; i >= 0; i--) {
    result = { head: entries[i], tail: result };
  }
  return result;
}

/**
 * Service a boundary effect request from the engine state machine.
 * Parameterized: takes kernelProjections and seedProjectionMap.
 */
function serviceBoundaryEffect(kernelProjections, seedProjectionMap, request, maxAlgorithmIterations, emitFn, iteration, state) {
  const operation = request.operation;
  const reqInput = request.input;
  const context = Object.assign(Object.create(null), request.context);
  const injectKey = request.inject_key;

  if (typeof injectKey !== 'string') {
    emitFn('fail_closed', iteration, state, 'input.reserved_field');
    throw new RcxError('input.reserved_field',
      `SECURITY: inject_key must be a string, got ${typeof injectKey}.`
    );
  }
  if (KERNEL_RESERVED_FIELDS.has(injectKey) || FORBIDDEN_INJECT_KEYS.has(injectKey)) {
    emitFn('fail_closed', iteration, state, 'input.reserved_field');
    throw new RcxError('input.reserved_field',
      `SECURITY: inject_key '${injectKey}' is forbidden (kernel-reserved or JS built-in). ` +
      `Boundary requests cannot inject reserved fields.`
    );
  }

  const MAX_BOUNDARY_TRACE_STEPS = 10000;

  let result;
  if (operation === 'run_trace') {
    let traceMaxSteps = reqInput.max_steps ?? 100;
    if (typeof traceMaxSteps !== 'number' || traceMaxSteps < 0) traceMaxSteps = 100;
    if (traceMaxSteps > MAX_BOUNDARY_TRACE_STEPS) traceMaxSteps = MAX_BOUNDARY_TRACE_STEPS;
    const raw = runStructural(kernelProjections, reqInput.projections, reqInput.value, traceMaxSteps);
    result = { result: raw.result, trace: raw.trace, stall: raw.stall };
  } else if (operation === 'hash_trace') {
    result = hashTraceForRecurrence(reqInput);
  } else if (operation === 'run_algorithm') {
    const algoName = request.algorithm;
    const algoProjs = seedProjectionMap[algoName];
    if (!algoProjs) {
      throw new RcxError('api.bad_request', `Unknown algorithm seed: ${algoName}`);
    }
    result = runSubAlgorithm(kernelProjections, seedProjectionMap, algoProjs, reqInput, maxAlgorithmIterations);
  } else {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request', `Unknown boundary operation: ${operation}`);
  }

  validateNoKernelReservedFields(result, `boundary_result(${operation})`);

  context[injectKey] = result;
  return context;
}

// Boot1 re-entry depth limit
const BOOT1_MAX_REENTRY_DEPTH = 20;

/**
 * Host loop that drives the engine state machine (rcx_engine.v1.json).
 * Parameterized: takes kernelProjections, seedProjectionMap, and engineProjections.
 * @host_iteration (boundary host loop, services engine state machine)
 */
function runEnginePipeline(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, options) {
  if (!isValidMu(inputValue)) {
    throw new RcxError('input.invalid_type', `runEnginePipeline: inputValue is not valid Mu (got ${typeof inputValue})`);
  }
  validateNoKernelReservedFields(inputValue, 'runEnginePipeline input');

  const {
    maxSteps = 100,
    frozen = null,
    maxEngineIterations = 20,
    maxAlgorithmIterations = 50,
    observer = null,
  } = options ?? {};

  // SECURITY: Validate frozen for kernel-reserved fields (parity with input validation)
  if (frozen !== null && frozen !== undefined) {
    validateNoKernelReservedFields(frozen, 'runEnginePipeline frozen');
  }

  if (observer !== null && !Array.isArray(observer)) {
    throw new RcxError('observer.invalid_type',
      `observer must be array or null, got ${typeof observer}`);
  }

  let obsTs = 0;
  function emit(eventName, stepNum, stateVal, errorCode, extra) {
    if (observer === null) return;
    let stateHash = null;
    try { stateHash = muHash(stateVal); } catch (_) { /* ignore */ }
    const event = {
      event_name: eventName,
      step: stepNum,
      state_hash: stateHash,
      error_code: errorCode ?? null,
      substrate: 'js',
      timestamp: obsTs,
    };
    if (extra) Object.assign(event, extra);
    observer.push(event);
    obsTs++;
  }

  let state = {
    _run_engine: {
      projections: projections,
      input: inputValue,
      max_steps: maxSteps,
      frozen: frozen,
    }
  };

  for (let iteration = 0; iteration < maxEngineIterations; iteration++) {
    const nextState = step(engineProjections, state);

    emit('step_boundary', iteration, state);

    if (nextState === state) {
      if (isEngineTerminal(state)) {
        if (typeof state === 'object' && state !== null) {
          if (state.closure_detected) emit('closure_detected', iteration, state);
          if (state.stall) emit('stall_detected', iteration, state);
        }
        emit('engine_terminal', iteration, state, null, {
          engine_exit_reason: deriveEngineExitReason(state),
          engine_iterations_used: iteration + 1,
        });
        return state;
      }
      emit('fail_closed', iteration, state, 'engine.stalled_non_terminal');
      throw new RcxError('engine.stalled_non_terminal',
        `Engine stalled at iteration ${iteration} without producing terminal result. ` +
        `State keys: ${typeof state === 'object' && state !== null ? JSON.stringify(Object.keys(state).sort()) : typeof state}`
      );
    }

    if (typeof nextState === 'object' && nextState !== null && '_boundary_request' in nextState) {
      state = serviceBoundaryEffect(
        kernelProjections, seedProjectionMap, nextState._boundary_request, maxAlgorithmIterations, emit, iteration, state
      );
      continue;
    }

    if (typeof nextState === 'object' && nextState !== null
        && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
      const tailPayload = nextState._tail_call;
      if (tailPayload && typeof tailPayload === 'object' && tailPayload.input) {
        validateNoKernelReservedFields(tailPayload.input, 'tail_call re-entry input');
      }
      state = { _run_engine: tailPayload };
      continue;
    }

    if (isEngineTerminal(nextState)) {
      if (typeof nextState === 'object' && nextState !== null) {
        if (nextState.closure_detected) emit('closure_detected', iteration, nextState);
        if (nextState.stall) emit('stall_detected', iteration, nextState);
      }
      emit('engine_terminal', iteration, nextState, null, {
        engine_exit_reason: deriveEngineExitReason(nextState),
        engine_iterations_used: iteration + 1,
      });
      return nextState;
    }

    state = nextState;
  }

  emit('fail_closed', maxEngineIterations - 1, state, 'engine.exhausted');
  throw new RcxError('engine.exhausted',
    `Engine pipeline exhausted ${maxEngineIterations} iterations without terminal result. ` +
    `State keys: ${typeof state === 'object' && state !== null ? JSON.stringify(Object.keys(state).sort()) : typeof state}`
  );
}

/**
 * Boot1 engine pipeline with iterative re-entry (no host recursion).
 * Parameterized: takes kernelProjections, seedProjectionMap, and engineProjections.
 * @host_iteration: for loop per re-entry pass (Boot1 iterative)
 */
function runEnginePipelineRecursive(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, options, recursionDepth) {
  if (!isValidMu(inputValue)) {
    throw new RcxError('input.invalid_type', `runEnginePipelineRecursive: inputValue is not valid Mu (got ${typeof inputValue})`);
  }

  const {
    maxSteps = 100,
    frozen = null,
    maxEngineIterations = 20,
    maxAlgorithmIterations = 50,
    observer = null,
  } = options ?? {};

  // SECURITY: Validate frozen for kernel-reserved fields (parity with input validation)
  if (frozen !== null && frozen !== undefined) {
    validateNoKernelReservedFields(frozen, 'runEnginePipelineRecursive frozen');
  }

  if (observer !== null && !Array.isArray(observer)) {
    throw new RcxError('observer.invalid_type',
      `observer must be array or null, got ${typeof observer}`);
  }

  let depth = recursionDepth ?? 0;
  const initialDepth = depth;
  let remainingIterations = maxEngineIterations;
  let curProjections = projections;
  let curInput = inputValue;
  let curMaxSteps = maxSteps;
  let curFrozen = frozen;

  let obsTs = 0;
  let totalIterations = 0;
  const emit = function(eventName, stepNum, stateVal, errorCode, extra) {
    if (observer === null) return;
    let stateHash = null;
    try { stateHash = muHash(stateVal); } catch (_) { /* ignore */ }
    const event = {
      event_name: eventName,
      step: stepNum,
      state_hash: stateHash,
      error_code: errorCode ?? null,
      substrate: 'js',
      timestamp: obsTs,
      boot1_depth: depth,
    };
    if (extra) Object.assign(event, extra);
    observer.push(event);
    obsTs++;
  };

  while (true) {
    if (depth >= BOOT1_MAX_REENTRY_DEPTH) {
      throw new RcxError('engine.boot1_depth_exceeded',
        `Boot1 re-entry depth ${depth} exceeds limit ${BOOT1_MAX_REENTRY_DEPTH}.`
      );
    }

    if (depth > initialDepth) {
      if (!isValidMu(curInput)) {
        throw new RcxError('input.invalid_type', 'runEnginePipelineRecursive: re-entry inputValue is not valid Mu');
      }
    }

    obsTs = 0;

    let state = {
      _run_engine: {
        projections: curProjections,
        input: curInput,
        max_steps: curMaxSteps,
        frozen: curFrozen,
      }
    };

    let reentry = false;
    for (let iteration = 0; iteration < remainingIterations; iteration++) {
      const nextState = step(engineProjections, state);

      emit('step_boundary', iteration, state);
      totalIterations++;

      if (nextState === state) {
        if (isEngineTerminal(state)) {
          if (typeof state === 'object' && state !== null) {
            if (state.closure_detected) emit('closure_detected', iteration, state);
            if (state.stall) emit('stall_detected', iteration, state);
          }
          emit('engine_terminal', iteration, state, null, {
            engine_exit_reason: deriveEngineExitReason(state),
            engine_iterations_used: totalIterations,
          });
          return state;
        }
        emit('fail_closed', iteration, state, 'engine.stalled_non_terminal');
        throw new RcxError('engine.stalled_non_terminal',
          `Boot1 engine stalled at iteration ${iteration} (depth ${depth}) without terminal result.`
        );
      }

      if (typeof nextState === 'object' && nextState !== null && '_boundary_request' in nextState) {
        state = serviceBoundaryEffect(
          kernelProjections, seedProjectionMap, nextState._boundary_request, maxAlgorithmIterations, emit, iteration, state
        );
        continue;
      }

      if (typeof nextState === 'object' && nextState !== null
          && '_run_engine' in nextState && Object.keys(nextState).length === 1) {
        const payload = nextState._run_engine;
        curProjections = payload.projections;
        curInput = payload.input;
        validateNoKernelReservedFields(curInput, 'Boot1 re-entry input');
        curMaxSteps = payload.max_steps ?? curMaxSteps;
        curFrozen = payload.frozen ?? null;
        if (curFrozen !== null) validateNoKernelReservedFields(curFrozen, 'Boot1 re-entry frozen');
        remainingIterations = remainingIterations - iteration - 1;
        depth++;
        reentry = true;
        break;
      }

      if (typeof nextState === 'object' && nextState !== null
          && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
        const payload = nextState._tail_call;
        curProjections = payload.projections;
        curInput = payload.input;
        validateNoKernelReservedFields(curInput, 'Boot1 tail_call input');
        curMaxSteps = payload.max_steps ?? curMaxSteps;
        curFrozen = payload.frozen ?? null;
        if (curFrozen !== null) validateNoKernelReservedFields(curFrozen, 'Boot1 tail_call frozen');
        remainingIterations = remainingIterations - iteration - 1;
        depth++;
        reentry = true;
        break;
      }

      if (isEngineTerminal(nextState)) {
        if (typeof nextState === 'object' && nextState !== null) {
          if (nextState.closure_detected) emit('closure_detected', iteration, nextState);
          if (nextState.stall) emit('stall_detected', iteration, nextState);
        }
        emit('engine_terminal', iteration, nextState, null, {
          engine_exit_reason: deriveEngineExitReason(nextState),
          engine_iterations_used: totalIterations,
        });
        return nextState;
      }

      state = nextState;
    }

    if (reentry) continue;

    emit('fail_closed', remainingIterations - 1, state, 'engine.exhausted');
    throw new RcxError('engine.exhausted',
      `Boot1 engine pipeline exhausted ${remainingIterations} iterations (depth ${depth}).`
    );
  }
}

module.exports = {
  BOOT1_MAX_REENTRY_DEPTH,
  runAlgorithmWithBridge,
  runSubAlgorithm,
  hashTraceForRecurrence,
  serviceBoundaryEffect,
  runEnginePipeline,
  runEnginePipelineRecursive,
};
