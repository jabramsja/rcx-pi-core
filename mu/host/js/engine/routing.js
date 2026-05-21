'use strict';
/**
 * RCX Engine Routing
 *
 * runHemisphereRouting, runMetabolizationCycle, runEngineWithRouting.
 * Depends on: core/*, core/terminal_classification.js, engine/pipeline.js, engine/kernel.js
 */

const { RcxError } = require('../core/constants');
const muContainers = require('../core/container_factory');
const { HEMISPHERE_KEYS, HEMISPHERE_KEY_ORDER, setsEqual, defaultHemispheres, deriveEngineExitReason } = require('../core/terminal_classification');
const { validateNoKernelReservedFields } = require('../core/security');
const { stepKernel } = require('./kernel');
const { runEnginePipeline, runEnginePipelineRecursive } = require('./pipeline');

const KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000;

/**
 * Route engine result to hemispheres with input shape validation.
 * Parameterized: takes allProjections and hemisphereProjections.
 * Mirrors Python run_hemisphere_routing() (step_mu.py:1592-1621).
 */
function runHemisphereRouting(allProjections, hemisphereProjections, engineResult, hemispheres, vmConfig) {
  if (engineResult === null || typeof engineResult !== 'object' || Array.isArray(engineResult)) {
    throw new RcxError('input.invalid_type', 'engine_result must be a dict');
  }
  const wrapped = muContainers.record([
    ['route_hemisphere', muContainers.record([
      ['engine_result', engineResult],
      ['hemispheres', hemispheres],
    ])],
  ]);
  validateNoKernelReservedFields(wrapped, 'runHemisphereRouting input');
  let current = wrapped;
  const limit = 30;
  for (let i = 0; i < limit; i++) {
    let packet = stepKernel(
      allProjections, current, hemisphereProjections,
      {
        maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG,
        validationMode: 'algorithm_runtime',
        returnPacket: true,
        vmConfig: vmConfig || null,
      }
    );
    // BOUNDARY: routing drives explicit Mu continuation data returned by the kernel driver.
    while (packet.kind === 'continuation') {
      packet = stepKernel(
        allProjections, current, hemisphereProjections,
        {
          maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG,
          validationMode: 'algorithm_runtime',
          returnPacket: true,
          vmConfig: vmConfig || null,
          continuationState: packet.continuation,
        }
      );
    }
    const meta = packet.result;
    if (meta.stall) break;
    current = meta.output;
  }
  if (typeof current === 'object' && current !== null &&
      setsEqual(new Set(Object.keys(current)), HEMISPHERE_KEYS)) {
    return current;
  }
  throw new RcxError(
    'input.shape_mismatch',
    `Hemisphere routing did not produce valid hemisphere dict. ` +
    `Got: ${typeof current === 'object' && current !== null ? JSON.stringify(Object.keys(current).sort()) : typeof current}`
  );
}

/**
 * Count entries and validate linked-list structure across all hemisphere buckets.
 * Mirrors Python count_hemisphere_entries().
 */
function countHemisphereEntries(hemispheres, maxEntriesPerBucket) {
  if (maxEntriesPerBucket === undefined) maxEntriesPerBucket = 1000;
  let count = 0;
  const keyOrder = HEMISPHERE_KEY_ORDER;
  for (let i = 0; i < keyOrder.length; i++) {
    const bucketName = keyOrder[i];
    const bucket = hemispheres[bucketName];
    if (bucket === undefined) {
      throw new RcxError('input.shape_mismatch',
        `hemisphere bucket '${bucketName}' is undefined (expected null or array)`);
    }
    if (bucket === null) continue;
    if (!Array.isArray(bucket)) {
      throw new RcxError('input.shape_mismatch',
        `hemisphere bucket '${bucketName}' must be null or array, got ${typeof bucket}`);
    }
    if (bucket.length > maxEntriesPerBucket) {
      throw new RcxError('input.shape_mismatch',
        `hemisphere bucket '${bucketName}' exceeds depth guard (${maxEntriesPerBucket}), possible cyclic structure`);
    }
    for (let j = 0; j < bucket.length; j++) {
      if (bucket[j] === null || typeof bucket[j] !== 'object' || Array.isArray(bucket[j])) {
        throw new RcxError('input.shape_mismatch',
          `hemisphere bucket '${bucketName}' entry[${j}] must be object, got ${bucket[j] === null ? 'null' : Array.isArray(bucket[j]) ? 'array' : typeof bucket[j]}`);
      }
    }
    count += bucket.length;
  }
  return count;
}

/**
 * Run structural metabolization cycle over hemispheres.
 * Loads metabolize_cycle.v1.json projections and runs via stepKernel loop.
 * No host iteration — iteration is structural (walker projections pattern-match).
 * Mirrors Python run_metabolization_cycle().
 */
function runMetabolizationCycle(allProjections, metabolizeCycleProjections, hemispheres, vmConfig) {
  // Input validation (fail-closed)
  if (hemispheres === null || typeof hemispheres !== 'object' || Array.isArray(hemispheres)) {
    throw new RcxError('input.invalid_type', `hemispheres must be dict, got ${typeof hemispheres}`);
  }
  const actual = new Set(Object.keys(hemispheres));
  if (!setsEqual(actual, HEMISPHERE_KEYS)) {
    const missing = [...HEMISPHERE_KEYS].filter(k => !actual.has(k)).sort();
    const extra = [...actual].filter(k => !HEMISPHERE_KEYS.has(k)).sort();
    throw new RcxError('input.shape_mismatch',
      `hemispheres shape mismatch: missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
  }

  // Recursive list validation + budget calculation
  const entryCount = countHemisphereEntries(hemispheres);

  const wrapped = muContainers.record([
    ['metabolize_cycle', muContainers.record([
      ['hemispheres', hemispheres],
    ])],
  ]);
  validateNoKernelReservedFields(wrapped, 'runMetabolizationCycle input');
  const stepBudget = Math.max(20, 4 * entryCount + 10);

  let current = wrapped;
  for (let i = 0; i < stepBudget; i++) {
    let packet = stepKernel(
      allProjections, current, metabolizeCycleProjections,
      {
        maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG,
        validationMode: 'algorithm_runtime',
        returnPacket: true,
        vmConfig: vmConfig || null,
      }
    );
    // BOUNDARY: metabolization drives explicit Mu continuation data returned by the kernel driver.
    while (packet.kind === 'continuation') {
      packet = stepKernel(
        allProjections, current, metabolizeCycleProjections,
        {
          maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG,
          validationMode: 'algorithm_runtime',
          returnPacket: true,
          vmConfig: vmConfig || null,
          continuationState: packet.continuation,
        }
      );
    }
    const meta = packet.result;
    if (meta.stall) break;
    current = meta.output;
  }

  // Output validation (symmetric with input)
  if (typeof current !== 'object' || current === null ||
      !setsEqual(new Set(Object.keys(current)), HEMISPHERE_KEYS)) {
    throw new RcxError('input.shape_mismatch',
      'Metabolization cycle did not produce valid hemispheres');
  }
  countHemisphereEntries(current);  // raises on malformed output nodes

  return current;
}

/**
 * Chain runEnginePipeline -> runHemisphereRouting -> runMetabolizationCycle.
 * Parameterized: takes all projection sets.
 * Mirrors Python run_engine_with_routing() (step_mu.py).
 */
function runEngineWithRouting(allProjections, hemisphereProjections, kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, hemispheres, engineKwargs, boot1Mode, metabolizeCycleProjections, vmConfig) {
  if (hemispheres === undefined || hemispheres === null) {
    hemispheres = defaultHemispheres();
  } else {
    if (typeof hemispheres !== 'object' || Array.isArray(hemispheres)) {
      throw new RcxError('input.invalid_type', `hemispheres must be dict, got ${Array.isArray(hemispheres) ? 'array' : typeof hemispheres}`);
    }
    const actual = new Set(Object.keys(hemispheres));
    if (!setsEqual(actual, HEMISPHERE_KEYS)) {
      const missing = [...HEMISPHERE_KEYS].filter(k => !actual.has(k)).sort();
      const extra = [...actual].filter(k => !HEMISPHERE_KEYS.has(k)).sort();
      throw new RcxError('input.shape_mismatch', `hemispheres shape mismatch: missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
    }
  }

  const obs = engineKwargs ? engineKwargs.observer : undefined;
  if (obs !== undefined && obs !== null && !Array.isArray(obs)) {
    throw new RcxError('observer.invalid_type',
      `observer must be array or null, got ${typeof obs}`);
  }

  // P7-d: Split vmConfig by phase — bridge for engine pipeline, core for routing/metabolization.
  // Engine pipeline uses allProjectionsWithBridge (bridge kernel projections) → bridge vmConfig.
  // Hemisphere routing and metabolization use allProjections (core, no bridge) → core vmConfig.
  const engineOpts = vmConfig
    ? Object.assign({}, engineKwargs, { vmConfig })
    : engineKwargs;
  const coreVmConfig = vmConfig
    ? Object.assign({}, vmConfig, { bridgeBundle: null })
    : null;
  let engineResult;
  if (boot1Mode) {
    engineResult = runEnginePipelineRecursive(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, engineOpts);
  } else {
    engineResult = runEnginePipeline(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, engineOpts);
  }
  let updatedHemispheres = runHemisphereRouting(allProjections, hemisphereProjections, engineResult, hemispheres, coreVmConfig);

  const outputKeys = new Set(Object.keys(updatedHemispheres));
  if (typeof updatedHemispheres !== 'object' || !setsEqual(outputKeys, HEMISPHERE_KEYS)) {
    throw new RcxError('input.shape_mismatch', 'runHemisphereRouting returned unexpected shape');
  }

  // Run metabolization cycle (structural walker — no host iteration)
  if (metabolizeCycleProjections) {
    updatedHemispheres = runMetabolizationCycle(allProjections, metabolizeCycleProjections, updatedHemispheres, coreVmConfig);
  }

  return muContainers.record([
    ['engine_result', engineResult],
    ['hemispheres', updatedHemispheres],
  ]);
}

module.exports = {
  runHemisphereRouting,
  runMetabolizationCycle,
  countHemisphereEntries,
  runEngineWithRouting,
};
