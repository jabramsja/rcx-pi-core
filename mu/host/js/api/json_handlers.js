'use strict';
/**
 * RCX JSON API Mode
 *
 * Handles --json-api action dispatch for cross-substrate verification.
 * Depends on: core/*, engine/*, and the seeds context from cli/main.js
 */

const { classifyError, RcxError } = require('../core/constants');
const { isValidMu, muHash, muHashCached } = require('../core/types');
const { normalize, denormalize } = require('../core/normalize');
const { validateNoKernelReservedFields, validateAlgorithmRuntimeFields } = require('../core/security');
const { step, run, match } = require('../core/bootstrap_core');
const { HEMISPHERE_KEYS, setsEqual, defaultHemispheres, deriveEngineExitReason } = require('../core/terminal_classification');
const { stepKernel, runStructural } = require('../engine/kernel');
const { runAlgorithmWithBridge, runEnginePipeline, runEnginePipelineRecursive, hashTraceForRecurrence } = require('../engine/pipeline');
const { runHemisphereRouting, runMetabolizationCycle, runEngineWithRouting } = require('../engine/routing');

// API-level caps for externally reachable endpoints.
const API_MAX_STEPS = 10000;
const API_MAX_ENGINE_ITERATIONS = 100;
const API_MAX_ALGORITHM_ITERATIONS = 200;

function guardMaxSteps(value, fieldName) {
  if (value == null) return;
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    throw new RcxError('api.bad_request', `${fieldName} must be an integer, got ${typeof value}`);
  }
  if (value < 0) {
    throw new RcxError('api.bad_request', `${fieldName} must be >= 0, got ${value}`);
  }
  if (value > API_MAX_STEPS) {
    throw new RcxError('api.bad_request', `${fieldName} exceeds API cap of ${API_MAX_STEPS}`);
  }
}

function guardIterationCap(value, fieldName, cap) {
  if (value == null) return;
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    throw new RcxError('api.bad_request', `${fieldName} must be an integer, got ${typeof value}`);
  }
  if (value < 0) {
    throw new RcxError('api.bad_request', `${fieldName} must be >= 0, got ${value}`);
  }
  if (value > cap) {
    throw new RcxError('api.bad_request', `${fieldName} exceeds API cap of ${cap}`);
  }
}

/**
 * Handle a JSON API request.
 * @param {string} apiArg - The JSON string from --json-api argv
 * @param {Object} seeds - Context object with all projection sets:
 *   {
 *     allProjections, allProjectionsWithBridge, allProjectionsWithExhaustion,
 *     allProjectionsWithExhaustionAndBridge, allProjectionsWithRecurrenceAndBridge,
 *     recurrenceProjections, exhaustionProjections, hemisphereProjections,
 *     engineProjections, metabolizationProjections, seedProjectionMap,
 *     parityVectors, kernel, matchSeed, substSeed, bridgeSeed,
 *     recurrenceSeed, exhaustionSeed, hemisphereSeed, engineSeed, metabolizationSeed,
 *     SEED_CHECKSUMS, MAX_DEPTH, MAX_MU_WIDTH,
 *   }
 */
function handleJsonApi(apiArg, seeds) {
  const {
    allProjections, allProjectionsWithBridge, allProjectionsWithExhaustion,
    allProjectionsWithExhaustionAndBridge,
    recurrenceProjections, exhaustionProjections, hemisphereProjections,
    engineProjections, metabolizationProjections, metabolizeCycleProjections,
    seedProjectionMap,
    parityVectors,
    kernel, matchSeed, substSeed, bridgeSeed,
    recurrenceSeed, exhaustionSeed, hemisphereSeed, engineSeed, metabolizationSeed,
    allProjectionsWithRecurrenceAndBridge,
    SEED_CHECKSUMS: seedChecksums,
  } = seeds;

  // Helper: run Recurrence on trace result
  function runRecurrence(traceResult) {
    const recurrenceInput = {
      _detect_closure: {
        trace: traceResult.trace,
        result: traceResult.result
      }
    };
    const { result } = run(recurrenceProjections, recurrenceInput, 1000);
    return result;
  }

  try {
    const request = JSON.parse(apiArg);
    let response;

    if (request.action === 'run_vector') {
      const { input, projection } = request;
      try {
        const { result } = stepKernel(
          allProjections, input, [projection], { maxSteps: 100 }
        );
        const denormalized = denormalize(result);
        response = { success: true, result: denormalized };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_all_vectors') {
      const results = [];
      for (const vector of parityVectors.vectors) {
        try {
          const { result } = stepKernel(
            allProjections, vector.input, [vector.projection], { maxSteps: 100 }
          );
          const denormalized = denormalize(result);
          results.push({ id: vector.id, success: true, result: denormalized, expected: vector.expected_output });
        } catch (e) {
          results.push({ id: vector.id, success: false, error_code: classifyError(e), error: e.message });
        }
      }
      response = { success: true, results };
    } else if (request.action === 'run_recurrence') {
      const { projections, input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const traceResult = runStructural(allProjectionsWithBridge, projections ?? [], input, maxSteps ?? 100);
        const closureResult = runRecurrence(traceResult);
        response = { success: true, result: closureResult };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_exhaustion') {
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        validateNoKernelReservedFields(input, 'run_exhaustion input');
        let current = input;
        let steps = 0;
        const limit = maxSteps ?? 200;
        while (steps < limit) {
          const next = step(allProjectionsWithExhaustion, current);
          if (muHashCached(current) === muHashCached(next)) break;
          current = next;
          steps++;
        }
        response = { success: true, result: current };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'get_constants') {
      const { MAX_DEPTH } = require('../core/constants');
      const { MAX_MU_WIDTH } = require('../core/types');
      response = {
        success: true,
        MAX_DEPTH,
        max_width: MAX_MU_WIDTH,
        KERNEL_RESERVED_FIELDS: [...require('../core/constants').KERNEL_RESERVED_FIELDS],
        seed_integrity_verified: true,
        seed_count: Object.keys(seedChecksums).length,
        kernel_projection_count: kernel.projections.length,
        match_projection_count: matchSeed.projections.length,
        subst_projection_count: substSeed.projections.length,
        bridge_projection_count: bridgeSeed.projections.length,
        recurrence_projection_count: recurrenceSeed.projections.length,
        exhaustion_projection_count: exhaustionSeed.projections.length,
        hemisphere_projection_count: hemisphereSeed.projections.length,
        metabolization_projection_count: metabolizationSeed.projections.length,
        total_with_bridge: allProjectionsWithBridge.length,
        total_with_recurrence_bridge: allProjectionsWithRecurrenceAndBridge.length,
        total_with_exhaustion_bridge: allProjectionsWithExhaustionAndBridge.length
      };
    } else if (request.action === 'normalize_roundtrip') {
      const { value } = request;
      try {
        const normalized = normalize(value);
        const denormalized = denormalize(normalized);
        response = { success: true, normalized, denormalized };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_mu') {
      const { value } = request;
      const { MAX_DEPTH } = require('../core/constants');
      const { MAX_MU_WIDTH } = require('../core/types');
      response = { success: true, is_valid: isValidMu(value), max_depth: MAX_DEPTH, max_width: MAX_MU_WIDTH };
    } else if (request.action === 'run_recurrence_with_bridge') {
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const result = runAlgorithmWithBridge(allProjectionsWithBridge, input, recurrenceProjections, maxSteps);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_exhaustion_with_bridge') {
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const result = runAlgorithmWithBridge(allProjectionsWithBridge, input, exhaustionProjections, maxSteps);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_reserved_fields') {
      const { value } = request;
      try {
        validateNoKernelReservedFields(value, 'test');
        response = { success: true, valid: true, error: '' };
      } catch (e) {
        response = { success: true, valid: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_algorithm_runtime_fields') {
      const { value } = request;
      try {
        validateAlgorithmRuntimeFields(value, 'test');
        response = { success: true, valid: true, error: '' };
      } catch (e) {
        response = { success: true, valid: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_structural_trace') {
      const { projections: userProjs, input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const traceResult = runStructural(allProjectionsWithBridge, userProjs ?? [], input, maxSteps ?? 100);
        const traceArray = [];
        let node = traceResult.trace;
        while (node && typeof node === 'object' && 'head' in node) {
          traceArray.push(node.head);
          node = node.tail;
        }
        response = { success: true, result: traceResult.result, trace: traceArray, stall: traceResult.stall, steps: traceResult.steps };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_hemisphere') {
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        let current = input;
        let steps = 0;
        const limit = maxSteps ?? 100;
        while (steps < limit) {
          const wrapped = stepKernel(
            allProjections, current, hemisphereProjections, { returnMeta: true }
          );
          if (wrapped.stall) break;
          current = wrapped.output;
          steps++;
        }
        response = { success: true, result: current };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_engine_pipeline') {
      const { projections: userProjs, input, maxSteps, frozen, maxEngineIterations, maxAlgorithmIterations } = request;
      if (request.boot1LoopMode != null && typeof request.boot1LoopMode !== 'boolean') {
        response = { success: false, error_code: 'type_error', error: 'boot1LoopMode must be boolean if provided, got ' + typeof request.boot1LoopMode };
      } else {
        const boot1Mode = request.boot1LoopMode ?? true;
        const observerEvents = request.observer_strict !== undefined
          ? (Array.isArray(request.observer_strict) ? request.observer_strict : request.observer_strict === null ? null : (() => { throw new RcxError('observer.invalid_type', 'observer_strict must be an array or null, got ' + typeof request.observer_strict); })())
          : (request.observer ? [] : null);
        try {
          guardMaxSteps(maxSteps, 'maxSteps');
          guardIterationCap(maxEngineIterations, 'maxEngineIterations', API_MAX_ENGINE_ITERATIONS);
          guardIterationCap(maxAlgorithmIterations, 'maxAlgorithmIterations', API_MAX_ALGORITHM_ITERATIONS);
          const opts = {
            maxSteps: maxSteps ?? 100,
            frozen: frozen ?? null,
            maxEngineIterations: maxEngineIterations ?? 20,
            maxAlgorithmIterations: maxAlgorithmIterations ?? 50,
            observer: observerEvents,
          };
          let result;
          if (boot1Mode) {
            result = runEnginePipelineRecursive(allProjectionsWithBridge, seedProjectionMap, engineProjections, userProjs ?? [], input, opts);
          } else {
            result = runEnginePipeline(allProjectionsWithBridge, seedProjectionMap, engineProjections, userProjs ?? [], input, opts);
          }
          response = { success: true, result };
          if (Array.isArray(observerEvents)) response.observer_events = observerEvents;
        } catch (e) {
          response = { success: false, error_code: classifyError(e), error: e.message };
          if (Array.isArray(observerEvents)) response.observer_events = observerEvents;
        }
      }
    } else if (request.action === 'hash_trace') {
      const { trace, maxEntries } = request;
      try {
        const result = hashTraceForRecurrence(trace, maxEntries ?? 10000);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_hemisphere_routing') {
      const { engine_result, hemispheres } = request;
      try {
        const result = runHemisphereRouting(allProjections, hemisphereProjections, engine_result, hemispheres ?? defaultHemispheres());
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_engine_with_routing') {
      if (request.boot1LoopMode != null && typeof request.boot1LoopMode !== 'boolean') {
        response = { success: false, error_code: 'type_error', error: 'boot1LoopMode must be boolean if provided, got ' + typeof request.boot1LoopMode };
      } else {
        const boot1Mode = request.boot1LoopMode ?? true;
        const { projections: userProjs, input, hemispheres, maxSteps, frozen, maxEngineIterations, maxAlgorithmIterations } = request;
        const observerEvents = request.observer_strict !== undefined
          ? (Array.isArray(request.observer_strict) ? request.observer_strict : request.observer_strict === null ? null : (() => { throw new RcxError('observer.invalid_type', 'observer_strict must be an array or null, got ' + typeof request.observer_strict); })())
          : (request.observer ? [] : null);
        try {
          guardMaxSteps(maxSteps, 'maxSteps');
          guardIterationCap(maxEngineIterations, 'maxEngineIterations', API_MAX_ENGINE_ITERATIONS);
          guardIterationCap(maxAlgorithmIterations, 'maxAlgorithmIterations', API_MAX_ALGORITHM_ITERATIONS);
          const result = runEngineWithRouting(
            allProjections, hemisphereProjections, allProjectionsWithBridge, seedProjectionMap, engineProjections,
            userProjs ?? [], input,
            hemispheres ?? null,
            {
              maxSteps: maxSteps ?? 100,
              frozen: frozen ?? null,
              maxEngineIterations: maxEngineIterations ?? 20,
              maxAlgorithmIterations: maxAlgorithmIterations ?? 50,
              observer: observerEvents,
            },
            boot1Mode,
            metabolizeCycleProjections
          );
          response = { success: true, result };
          if (Array.isArray(observerEvents)) response.observer_events = observerEvents;
        } catch (e) {
          response = { success: false, error_code: classifyError(e), error: e.message };
          if (Array.isArray(observerEvents)) response.observer_events = observerEvents;
        }
      }
    } else if (request.action === 'step_kernel_meta') {
      const { input, projections: domainProjs, maxSteps: reqMaxSteps, kernelMode } = request;
      guardMaxSteps(reqMaxSteps, 'maxSteps');
      try {
        const kernelProjs = (kernelMode === 'bridge')
          ? allProjectionsWithBridge
          : allProjections;
        const meta = stepKernel(kernelProjs, input, domainProjs ?? [], {
          maxSteps: reqMaxSteps ?? 100,
          returnMeta: true,
          validationMode: 'domain',
        });
        response = { success: true, result: meta };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_engine_pipeline_meta') {
      const { projections: userProjs, input, maxSteps, frozen, maxEngineIterations: reqMaxEngineIter, maxAlgorithmIterations } = request;
      if (request.boot1LoopMode != null && typeof request.boot1LoopMode !== 'boolean') {
        response = { success: false, error_code: 'type_error', error: 'boot1LoopMode must be boolean if provided, got ' + typeof request.boot1LoopMode };
      } else {
        const boot1Mode = request.boot1LoopMode ?? true;
        const metaObserver = request.observer_strict !== undefined
          ? (Array.isArray(request.observer_strict) ? request.observer_strict : request.observer_strict === null ? null : (() => { throw new RcxError('observer.invalid_type', 'observer_strict must be an array or null, got ' + typeof request.observer_strict); })())
          : [];
        const maxEngIter = reqMaxEngineIter ?? 20;
        const baseline = Array.isArray(metaObserver)
          ? metaObserver.filter(e => e.event_name === 'step_boundary').length
          : 0;
        try {
          guardMaxSteps(maxSteps, 'maxSteps');
          guardIterationCap(reqMaxEngineIter, 'maxEngineIterations', API_MAX_ENGINE_ITERATIONS);
          guardIterationCap(maxAlgorithmIterations, 'maxAlgorithmIterations', API_MAX_ALGORITHM_ITERATIONS);
          const opts = {
            maxSteps: maxSteps ?? 100,
            frozen: frozen ?? null,
            maxEngineIterations: maxEngIter,
            maxAlgorithmIterations: maxAlgorithmIterations ?? 50,
            observer: metaObserver,
          };
          let engineResult;
          if (boot1Mode) {
            engineResult = runEnginePipelineRecursive(allProjectionsWithBridge, seedProjectionMap, engineProjections, userProjs ?? [], input, opts);
          } else {
            engineResult = runEnginePipeline(allProjectionsWithBridge, seedProjectionMap, engineProjections, userProjs ?? [], input, opts);
          }
          const iterationsUsed = Array.isArray(metaObserver)
            ? metaObserver.filter(e => e.event_name === 'step_boundary').length - baseline
            : 0;
          response = {
            success: true,
            result: {
              engine_result: engineResult,
              engine_exit_reason: deriveEngineExitReason(engineResult),
              engine_iterations_used: iterationsUsed,
              max_engine_iterations: maxEngIter,
            },
          };
        } catch (e) {
          response = { success: false, error_code: classifyError(e), error: e.message };
        }
      }
    } else if (request.action === 'run_metabolization_cycle') {
      const { hemispheres } = request;
      try {
        const result = runMetabolizationCycle(allProjections, metabolizeCycleProjections, hemispheres ?? null);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'step_metabolization') {
      const { input } = request;
      try {
        validateNoKernelReservedFields(input, 'step_metabolization input');
        const result = step(metabolizationProjections, input);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'list_actions') {
      response = {
        success: true,
        actions: [
          'run_vector', 'run_all_vectors', 'run_recurrence', 'run_exhaustion',
          'get_constants', 'normalize_roundtrip', 'validate_mu',
          'run_recurrence_with_bridge', 'run_exhaustion_with_bridge',
          'validate_reserved_fields', 'validate_algorithm_runtime_fields',
          'run_structural_trace', 'run_hemisphere', 'run_engine_pipeline',
          'hash_trace', 'run_hemisphere_routing', 'run_engine_with_routing',
          'run_metabolization_cycle', 'step_metabolization',
          'step_kernel_meta', 'run_engine_pipeline_meta', 'list_actions'
        ]
      };
    } else {
      response = { success: false, error_code: 'api.unknown_action', error: `Unknown action: ${request.action}` };
    }

    console.log('JSON_API_RESPONSE:' + JSON.stringify(response));
  } catch (e) {
    console.log('JSON_API_RESPONSE:' + JSON.stringify({ success: false, error_code: classifyError(e), error: e.message }));
  }
}

module.exports = { handleJsonApi, guardMaxSteps, API_MAX_STEPS };
