'use strict';
/**
 * RCX Engine Routing
 *
 * runHemisphereRouting, runEngineWithRouting.
 * Depends on: core/*, core/terminal_classification.js, engine/pipeline.js, engine/kernel.js
 */

const { RcxError } = require('../core/constants');
const { HEMISPHERE_KEYS, setsEqual, defaultHemispheres, deriveEngineExitReason } = require('../core/terminal_classification');
const { stepKernel } = require('./kernel');
const { runEnginePipeline, runEnginePipelineRecursive } = require('./pipeline');

/**
 * Route engine result to hemispheres with input shape validation.
 * Parameterized: takes allProjections and hemisphereProjections.
 * Mirrors Python run_hemisphere_routing() (step_mu.py:1592-1621).
 */
function runHemisphereRouting(allProjections, hemisphereProjections, engineResult, hemispheres) {
  if (engineResult === null || typeof engineResult !== 'object' || Array.isArray(engineResult)) {
    throw new RcxError('input.invalid_type', 'engine_result must be a dict');
  }
  const wrapped = {
    route_hemisphere: {
      engine_result: engineResult,
      hemispheres: hemispheres,
    }
  };
  let current = wrapped;
  const limit = 30;
  for (let i = 0; i < limit; i++) {
    const meta = stepKernel(
      allProjections, current, hemisphereProjections,
      { returnMeta: true }
    );
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
 * Chain runEnginePipeline -> runHemisphereRouting.
 * Parameterized: takes all projection sets.
 * Mirrors Python run_engine_with_routing() (step_mu.py:1635-1672).
 */
function runEngineWithRouting(allProjections, hemisphereProjections, kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, hemispheres, engineKwargs, boot1Mode) {
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

  let engineResult;
  if (boot1Mode) {
    engineResult = runEnginePipelineRecursive(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, engineKwargs);
  } else {
    engineResult = runEnginePipeline(kernelProjections, seedProjectionMap, engineProjections, projections, inputValue, engineKwargs);
  }
  const updatedHemispheres = runHemisphereRouting(allProjections, hemisphereProjections, engineResult, hemispheres);

  const outputKeys = new Set(Object.keys(updatedHemispheres));
  if (typeof updatedHemispheres !== 'object' || !setsEqual(outputKeys, HEMISPHERE_KEYS)) {
    throw new RcxError('input.shape_mismatch', 'runHemisphereRouting returned unexpected shape');
  }

  return { engine_result: engineResult, hemispheres: updatedHemispheres };
}

module.exports = {
  runHemisphereRouting,
  runEngineWithRouting,
};
