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
const { isValidMu, muHash, muHashCached, muHashControl, muHashControlCached } = require('../core/types');
const { normalize, denormalize, normalizeProjection, listToLinked } = require('../core/normalize');
const { validateNoKernelReservedFields, validateAlgorithmRuntimeFields } = require('../core/security');
const { step } = require('../core/bootstrap_core');
const { isTerminalShape, isEngineTerminal, deriveEngineExitReason, setsEqual } = require('../core/terminal_classification');
const { stepKernel, runStructural, _stepKernelCoreNonMeta } = require('./kernel');
const seedLoader = require('../core/seed_loader');

// JS built-in property names that must never be used as inject_key.
// Prevents prototype chain poisoning via boundary requests.
const FORBIDDEN_INJECT_KEYS = new Set([
  '__proto__', 'constructor', 'toString', 'valueOf',  // AST_OK_JS: string literal in security blocklist, not prototype access
  'hasOwnProperty', 'isPrototypeOf', 'propertyIsEnumerable',
  'toLocaleString', '__defineGetter__', '__defineSetter__',
  '__lookupGetter__', '__lookupSetter__',
]);

// --- Engine seed boundary-ops derivation (A10: boundary dispatch authority) ---
let _engineSeed = null;
let _boundaryOps = null;
const _EXPECTED_BOUNDARY_OPS = new Set(['run_trace', 'hash_trace', 'run_algorithm']);

function _loadEngineSeed() {
  if (_engineSeed !== null) return _engineSeed;
  _engineSeed = require('../core/seed_loader').loadVerifiedSeed('rcx_engine.v1.json', 'programs');
  return _engineSeed;
}

function _ensureBoundaryOps() {
  if (_boundaryOps !== null) return _boundaryOps;
  const seed = _loadEngineSeed();
  const ops = new Set();
  for (const p of seed.projections) {
    const body = p.body;
    if (body !== null && typeof body === 'object' && !Array.isArray(body)) {
      const br = body._boundary_request;
      if (br !== null && typeof br === 'object' && !Array.isArray(br)) {
        if ('operation' in br) {
          const op = br.operation;
          if (typeof op !== 'string') {
            throw new RcxError('input.shape_mismatch',
              `engine seed invariant: boundary op must be string, ` +
              `got ${typeof op} in projection ${p.id || '?'}`);
          }
          ops.add(op);
        }
      }
    }
  }
  if (ops.size !== 3) {
    throw new RcxError('input.shape_mismatch',
      `engine seed invariant: expected 3 boundary ops, got ${ops.size}`);
  }
  if (!setsEqual(ops, _EXPECTED_BOUNDARY_OPS)) {
    throw new RcxError('input.shape_mismatch',
      `engine seed invariant: expected ${JSON.stringify([..._EXPECTED_BOUNDARY_OPS].sort())}, ` +
      `got ${JSON.stringify([...ops].sort())}`);
  }
  _boundaryOps = ops;
  return _boundaryOps;
}

function _clearBoundaryOpsCache() {
  _engineSeed = null;
  _boundaryOps = null;
}

/**
 * Run an algorithm (recurrence/exhaustion) through bridge-backed meta-circular kernel.
 * Pre-validates and pre-normalizes projections once (constant across all iterations).
 * Only current input is re-normalized per iteration.
 * BOUNDARY: Algorithm harness — off kernel path. Reclassified P7W5: was host iteration marker.
 */
function runAlgorithmWithBridge(allProjs, input, domainProjs, maxSteps, vmConfig) {
  // Validate input and projections once at entry (same checks as stepKernel).
  const validator = validateAlgorithmRuntimeFields;
  validator(input, 'domainInput');
  for (let i = 0; i < domainProjs.length; i++) {
    const proj = domainProjs[i];
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

  // Pre-normalize projections once (constant across all iterations).
  const normalizedProjs = domainProjs.map(normalizeProjection);
  const kernelDomainProjs = normalizedProjs.map(proj => ({
    pattern: proj.pattern,
    body: proj.body
  }));
  const linkedProjs = listToLinked(kernelDomainProjs);

  let current = input;
  let currentHash = muHashControlCached(current, 'runAlgorithmWithBridge');
  let steps = 0;
  const limit = maxSteps ?? 200;
  while (steps < limit) {
    const normalizedInput = normalize(current);
    const kernelInput = { _step: normalizedInput, _projs: linkedProjs };
    const wrapped = _stepKernelCoreNonMeta(allProjs, kernelInput, 10000, vmConfig || null);
    const next = denormalize(wrapped.result);
    validator(next, 'runAlgorithmWithBridge.intermediate');
    const nextHash = muHashControlCached(next, 'runAlgorithmWithBridge.stall');
    if (nextHash === currentHash) break;
    current = next;
    currentHash = nextHash;
    steps++;
  }
  return current;
}

/**
 * Run a sub-algorithm (recurrence/exhaustion) to completion.
 * Mirrors Python _run_sub_algorithm() (step_mu.py:1404).
 * Parameterized: takes kernelProjections and seedProjectionMap.
 */
function runSubAlgorithm(kernelProjections, seedProjectionMap, algorithmProjs, initial, maxIterations, vmConfig) {
  let current = initial;
  let currentHash = muHashControlCached(initial, 'runSubAlgorithm');
  for (let i = 0; i < maxIterations; i++) {
    const result = runAlgorithmWithBridge(kernelProjections, current, algorithmProjs, 200, vmConfig);
    if (isTerminalShape(result)) return result;
    const resultHash = muHashControlCached(result, 'runSubAlgorithm.stall');
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
    if (entry === null || typeof entry !== 'object' || !('state' in entry)) {
      const entryType = entry === null ? 'null' : typeof entry;
      const detail = typeof entry === 'object' && entry !== null ? ' without \'state\'' : '';
      throw new RcxError('trace.malformed_entry',
        `hash_trace_for_recurrence: malformed trace entry (expected dict with 'state' key, got ${entryType}${detail})`);
    }
    entry = Object.assign(Object.create(null), entry);
    if (isValidMu(entry.state)) {
      entry.state_hash = muHashControl(entry.state, 'hashTraceForRecurrence');
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

// --- Boundary operation handlers (A10: seed-derived dispatch) ---
const MAX_BOUNDARY_TRACE_STEPS = 10000;

function boundaryOpRunTrace(kernelProjections, seedProjectionMap, request, reqInput, maxAlgorithmIterations, vmConfig) {
  if (typeof reqInput !== 'object' || reqInput === null || Array.isArray(reqInput)) {
    throw new RcxError('api.bad_request',
      `run_trace input must be object, got ${reqInput === null ? 'null' : Array.isArray(reqInput) ? 'array' : typeof reqInput}`);
  }
  if (!('projections' in reqInput) || !('value' in reqInput)) {
    throw new RcxError('api.bad_request',
      "run_trace input must include 'projections' and 'value'");
  }
  const projs = reqInput.projections;
  if (!Array.isArray(projs)) {
    throw new RcxError('api.bad_request',
      `run_trace input 'projections' must be array, got ${typeof projs}`);
  }
  for (let i = 0; i < projs.length; i++) {
    if (typeof projs[i] !== 'object' || projs[i] === null || Array.isArray(projs[i])) {
      throw new RcxError('api.bad_request',
        `run_trace projection[${i}] must be object, got ${projs[i] === null ? 'null' : Array.isArray(projs[i]) ? 'array' : typeof projs[i]}`);
    }
    if (!('pattern' in projs[i]) || !('body' in projs[i])) {
      throw new RcxError('api.bad_request',
        `run_trace projection[${i}] must have 'pattern' and 'body' keys`);
    }
  }
  // max_steps parity policy: normalize-fallback.
  // Numeric finite → floor to int. Non-numeric/boolean/NaN/±Infinity → fallback to 100.
  // Matches Python parity exactly.
  let traceMaxSteps = reqInput.max_steps ?? 100;
  if (typeof traceMaxSteps !== 'number' || traceMaxSteps !== traceMaxSteps || !isFinite(traceMaxSteps)) traceMaxSteps = 100;
  traceMaxSteps = Math.floor(traceMaxSteps);
  if (traceMaxSteps < 0) traceMaxSteps = 100;
  if (traceMaxSteps > MAX_BOUNDARY_TRACE_STEPS) traceMaxSteps = MAX_BOUNDARY_TRACE_STEPS;
  const raw = runStructural(kernelProjections, projs, reqInput.value, traceMaxSteps, vmConfig || null);
  return { result: raw.result, trace: raw.trace, stall: raw.stall };
}

function boundaryOpHashTrace(kernelProjections, seedProjectionMap, request, reqInput, maxAlgorithmIterations, vmConfig) {
  return hashTraceForRecurrence(reqInput);
}

function boundaryOpRunAlgorithm(kernelProjections, seedProjectionMap, request, reqInput, maxAlgorithmIterations, vmConfig) {
  if (!('algorithm' in request)) {
    throw new RcxError('api.bad_request',
      "run_algorithm request must include 'algorithm'");
  }
  const algoName = request.algorithm;
  if (typeof algoName !== 'string') {
    throw new RcxError('api.bad_request',
      `run_algorithm 'algorithm' must be string, got ${typeof algoName}`);
  }
  const algoProjs = seedProjectionMap[algoName];
  if (!algoProjs) {
    throw new RcxError('api.bad_request', `Unknown algorithm seed: ${algoName}`);
  }
  return runSubAlgorithm(kernelProjections, seedProjectionMap, algoProjs, reqInput, maxAlgorithmIterations, vmConfig);
}

// Dispatch map: operation name → handler function (A10 structural displacement).
// Authority for valid operations comes from seed-derived _ensureBoundaryOps().
const BOUNDARY_DISPATCH = Object.freeze({
  run_trace: boundaryOpRunTrace,
  hash_trace: boundaryOpHashTrace,
  run_algorithm: boundaryOpRunAlgorithm,
});

// Test-only dispatch override. No production path sets this; null falls through
// to frozen BOUNDARY_DISPATCH. Allows tests to inject a handler that returns
// pre-existing ontology_promotion to exercise the overwrite guard.
let testDispatchOverride = null;
// Structural test mode flag — replaces process.env.RCX_TEST_MODE (host env leak).
// Tests must call enableTestMode() before using setTestDispatchOverride.
let _testModeEnabled = false;
function enableTestMode() { _testModeEnabled = true; }
function setTestDispatchOverride(override) {
  // A16: gate behind explicit test mode — fail-closed outside tests.
  if (!_testModeEnabled) {
    throw new RcxError('api.bad_request',
      'setTestDispatchOverride is test-only (call enableTestMode() first)');
  }
  if (override !== null) {
    if (typeof override !== 'object' || Array.isArray(override)) {
      throw new RcxError('input.shape_mismatch',
        `setTestDispatchOverride: override must be null or plain object, ` +
        `got ${Array.isArray(override) ? 'array' : typeof override}`);
    }
    const validKeys = new Set(Object.keys(BOUNDARY_DISPATCH));
    for (const key of Object.keys(override)) {
      if (!validKeys.has(key)) {
        throw new RcxError('input.shape_mismatch',
          `setTestDispatchOverride: unknown operation key '${key}', ` +
          `valid keys: ${JSON.stringify([...validKeys].sort())}`);
      }
      if (typeof override[key] !== 'function') {
        throw new RcxError('input.shape_mismatch',
          `setTestDispatchOverride: handler for '${key}' must be function, ` +
          `got ${typeof override[key]}`);
      }
    }
  }
  testDispatchOverride = override;
}

/**
 * Service a boundary effect request from the engine state machine.
 * Parameterized: takes kernelProjections and seedProjectionMap.
 * Dispatches via seed-derived operation authority (A10): handler-map lookup
 * replaces host if/elif dispatch. Validates request shape before any
 * field dereference.
 */
function serviceBoundaryEffect(kernelProjections, seedProjectionMap, request, maxAlgorithmIterations, emitFn, iteration, state, vmConfig) {
  // --- Request shape validation (typed fail-closed, no raw TypeError) ---
  if (typeof request !== 'object' || request === null || Array.isArray(request)) {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request',
      `boundary request must be object, got ${request === null ? 'null' : Array.isArray(request) ? 'array' : typeof request}`);
  }
  for (const key of ['operation', 'input', 'context', 'inject_key']) {
    if (!(key in request)) {
      emitFn('fail_closed', iteration, state, 'api.bad_request');
      throw new RcxError('api.bad_request',
        `boundary request missing required key: ${key}`);
    }
  }
  const operation = request.operation;
  if (typeof operation !== 'string') {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request',
      `boundary operation must be string, got ${typeof operation}`);
  }
  if (typeof request.context !== 'object' || request.context === null || Array.isArray(request.context)) {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request',
      `boundary context must be object, got ${request.context === null ? 'null' : Array.isArray(request.context) ? 'array' : typeof request.context}`);
  }
  const injectKey = request.inject_key;
  if (typeof injectKey !== 'string') {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request',
      `boundary inject_key must be string, got ${typeof injectKey}`);
  }
  const reqInput = request.input;
  const context = Object.assign(Object.create(null), request.context);

  // SECURITY: inject_key must not be kernel-reserved or JS built-in.
  if (KERNEL_RESERVED_FIELDS.has(injectKey) || FORBIDDEN_INJECT_KEYS.has(injectKey)) {
    emitFn('fail_closed', iteration, state, 'input.reserved_field');
    throw new RcxError('input.reserved_field',
      `SECURITY: inject_key '${injectKey}' is forbidden (kernel-reserved or JS built-in). ` +
      `Boundary requests cannot inject reserved fields.`
    );
  }

  // --- Seed-derived operation authority (A10 displacement) ---
  const validOps = _ensureBoundaryOps();
  if (!validOps.has(operation)) {
    emitFn('fail_closed', iteration, state, 'api.bad_request');
    throw new RcxError('api.bad_request', `Unknown boundary operation: ${operation}`);
  }

  // Dispatch coverage invariant: map keys must match seed-derived ops
  const dispatchKeys = new Set(Object.keys(BOUNDARY_DISPATCH));
  if (!setsEqual(dispatchKeys, validOps)) {
    throw new RcxError('input.shape_mismatch',
      `boundary dispatch/authority mismatch: dispatch=${JSON.stringify(Object.keys(BOUNDARY_DISPATCH).sort())}, ` +
      `seed=${JSON.stringify([...validOps].sort())}`);
  }

  const handler = (testDispatchOverride ?? BOUNDARY_DISPATCH)[operation];
  if (!handler) {
    throw new RcxError('input.shape_mismatch',
      `boundary dispatch missing handler for validated op: ${operation}`);
  }
  const result = handler(kernelProjections, seedProjectionMap, request, reqInput, maxAlgorithmIterations, vmConfig);

  validateNoKernelReservedFields(result, `boundary_result(${operation})`);

  // Producer-side ontology promotion candidate (A14): one-shot, opt-in only.
  if (context.emit_ontology_candidate === true) {
    delete context.emit_ontology_candidate;
    const evidence = context.ontology_candidate_evidence;
    delete context.ontology_candidate_evidence;
    if (typeof result !== 'object' || result === null || Array.isArray(result)) {
      throw new RcxError('input.shape_mismatch',
        `boundary_result(${operation}): emit_ontology_candidate requested ` +
        `but result is not object`);
    }
    // Correction #3: reject overwrite of handler-originated record.
    if ('ontology_promotion' in result) {
      throw new RcxError('input.shape_mismatch',
        `boundary_result(${operation}): emit_ontology_candidate requested ` +
        `but result already contains ontology_promotion`);
    }
    result.ontology_promotion = buildOntologyPromotionCandidate(
      evidence, `boundary_result(${operation}).ontology_candidate_evidence`
    );
    // Correction #2: re-validate reserved fields after producer attach.
    validateNoKernelReservedFields(result, `boundary_result(${operation}).post_producer`);
  }

  // Ontology promotion enforcement (A12): validate promotion records if present.
  if (result && typeof result === 'object' && 'ontology_promotion' in result) {
    const promo = result.ontology_promotion;
    if (typeof promo !== 'object' || promo === null || Array.isArray(promo)) {
      throw new RcxError('input.shape_mismatch',
        `boundary_result(${operation}).ontology_promotion must be object, ` +
        `got ${promo === null ? 'null' : Array.isArray(promo) ? 'array' : typeof promo}`);
    }
    validateOntologyPromotionRecord(
      promo,
      `boundary_result(${operation}).ontology_promotion`
    );
  }

  // Evidence collector (A17): one-shot, opt-in only.
  if (context.collect_ontology_candidate_evidence === true) {
    delete context.collect_ontology_candidate_evidence;
    // C1: no-overwrite guard — reject if observation already exists.
    if ('ontology_candidate_observation' in context) {
      throw new RcxError('input.shape_mismatch',
        `boundary_result(${operation}): collect_ontology_candidate_evidence ` +
        `requested but context already contains ontology_candidate_observation`);
    }
    context.ontology_candidate_observation = collectOntologyEvidence(result, operation);
  }

  // SECURITY: Reject inject_key collision with existing context keys.
  // Prevents boundary requests from silently overwriting domain context state.
  // Parity with Python _service_boundary_effect inject_key collision guard.
  if (injectKey in context) {
    emitFn('fail_closed', iteration, state, 'input.inject_key_collision');
    throw new RcxError('input.inject_key_collision',
      `SECURITY: inject_key '${injectKey}' already exists in context. ` +
      `Cannot overwrite existing context state.`);
  }
  context[injectKey] = result;
  return context;
}

/**
 * Validate shape/type of _run_engine or _tail_call re-entry payload.
 * Fail-closed: throws RcxError (not raw TypeError) on malformed payloads.
 */
function validateReentryPayload(payload, context) {
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
    throw new RcxError('input.shape_mismatch',
      `${context}: re-entry payload must be dict, got ${payload === null ? 'null' : Array.isArray(payload) ? 'array' : typeof payload}`
    );
  }
  if (!('projections' in payload)) {
    throw new RcxError('input.shape_mismatch',
      `${context}: re-entry payload missing required key 'projections'`
    );
  }
  if (!('input' in payload)) {
    throw new RcxError('input.shape_mismatch',
      `${context}: re-entry payload missing required key 'input'`
    );
  }
  if (!Array.isArray(payload.projections)) {
    throw new RcxError('input.shape_mismatch',
      `${context}: re-entry payload 'projections' must be list, got ${typeof payload.projections}`
    );
  }
  if (!isValidMu(payload.input)) {
    throw new RcxError('input.invalid_type',
      `${context}: re-entry payload 'input' is not valid Mu, got ${typeof payload.input}`
    );
  }
  if (payload.frozen !== null && payload.frozen !== undefined) {
    if (!isValidMu(payload.frozen)) {
      throw new RcxError('input.invalid_type',
        `${context}: re-entry payload 'frozen' is not valid Mu, got ${typeof payload.frozen}`
      );
    }
  }
  validateNoKernelReservedFields(payload.input, `${context} input`);
  if (payload.frozen !== null && payload.frozen !== undefined) {
    validateNoKernelReservedFields(payload.frozen, `${context} frozen`);
  }
}

/**
 * Validate an ontology promotion record against INV_OPROMO_1..4.
 * Fail-closed: throws RcxError (not raw TypeError) on any invariant violation.
 * Check order: INV_OPROMO_4 (shape) → 1 → 2 → 3.
 */
function validateOntologyPromotionRecord(record, contextStr) {
  // Entry guard: reject null/non-object/array before any property access
  if (typeof record !== 'object' || record === null || Array.isArray(record)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: record must be object, got ${record === null ? 'null' : Array.isArray(record) ? 'array' : typeof record}`);
  }
  // --- INV_OPROMO_4: shape/provenance ---
  const requiredKeys = [
    'witness_traces', 'seed_configs', 'closure_structure',
    'perturbation_log', 'derivation_timestamp', 'substrate_versions',
    'tau_lineage', 'authority',
  ];
  for (const key of requiredKeys) {
    if (!(key in record)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_4 missing required field '${key}'`);
    }
  }

  const witnessTraces = record.witness_traces;
  const seedConfigs = record.seed_configs;
  const closureStructure = record.closure_structure;
  const perturbationLog = record.perturbation_log;
  const derivationTimestamp = record.derivation_timestamp;
  const substrateVersions = record.substrate_versions;
  const tauLineage = record.tau_lineage;
  const authority = record.authority;

  if (!Array.isArray(witnessTraces)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'witness_traces' must be array, got ${typeof witnessTraces}`);
  }
  if (!Array.isArray(seedConfigs)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'seed_configs' must be array, got ${typeof seedConfigs}`);
  }
  if (typeof closureStructure !== 'object' || closureStructure === null || Array.isArray(closureStructure)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'closure_structure' must be object`);
  }
  if (typeof perturbationLog !== 'object' || perturbationLog === null || Array.isArray(perturbationLog)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'perturbation_log' must be object`);
  }
  if (typeof derivationTimestamp !== 'string' || derivationTimestamp === '') {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'derivation_timestamp' must be non-empty string`);
  }
  if (typeof substrateVersions !== 'object' || substrateVersions === null || Array.isArray(substrateVersions)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'substrate_versions' must be object`);
  }
  for (const svKey of ['python', 'js']) {
    if (!(svKey in substrateVersions) || typeof substrateVersions[svKey] !== 'string') {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_4 'substrate_versions' must contain string key '${svKey}'`);
    }
  }
  if (!Array.isArray(tauLineage) || tauLineage.length === 0) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'tau_lineage' must be non-empty array`);
  }
  if (typeof authority !== 'object' || authority === null || Array.isArray(authority)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'authority' must be object`);
  }
  for (const authKey of ['source', 'seed_file', 'projection_ids']) {
    if (!(authKey in authority)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_4 'authority' missing required field '${authKey}'`);
    }
  }
  if (typeof authority.source !== 'string') {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'authority.source' must be string`);
  }
  if (typeof authority.seed_file !== 'string') {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'authority.seed_file' must be string`);
  }
  if (!Array.isArray(authority.projection_ids) || authority.projection_ids.length === 0) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4 'authority.projection_ids' must be non-empty array`);
  }
  for (const pid of authority.projection_ids) {
    if (typeof pid !== 'string') {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_4 'authority.projection_ids' entries must be strings`);
    }
  }

  // --- INV_OPROMO_1: recurrence witnesses ---
  // Type-validate seed_configs entries before Set construction to prevent silent coercion
  for (let i = 0; i < seedConfigs.length; i++) {
    if (typeof seedConfigs[i] !== 'string') {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_1 seed_configs[${i}] must be string, got ${typeof seedConfigs[i]}`);
    }
  }
  if (witnessTraces.length < 2) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_1 requires >= 2 witness_traces, got ${witnessTraces.length}`);
  }
  const witnessPairs = new Set();
  const witnessSeedConfigs = new Set();
  for (let i = 0; i < witnessTraces.length; i++) {
    const w = witnessTraces[i];
    if (typeof w !== 'object' || w === null || Array.isArray(w)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_1 witness_traces[${i}] must be object`);
    }
    if (!('trace_id' in w) || typeof w.trace_id !== 'string') {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_1 witness_traces[${i}] must have string 'trace_id'`);
    }
    if (!('seed_config' in w) || typeof w.seed_config !== 'string') {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_1 witness_traces[${i}] must have string 'seed_config'`);
    }
    const pairKey = `${w.seed_config}\0${w.trace_id}`;
    if (witnessPairs.has(pairKey)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_1 duplicate (seed_config, trace_id) pair: (${w.seed_config}, ${w.trace_id})`);
    }
    witnessPairs.add(pairKey);
    witnessSeedConfigs.add(w.seed_config);
  }
  if (witnessSeedConfigs.size < 2) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_1 requires >= 2 distinct seed_configs in witnesses, got ${witnessSeedConfigs.size}`);
  }
  const seedConfigSet = new Set(seedConfigs);
  if (!setsEqual(seedConfigSet, witnessSeedConfigs)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_1 seed_configs field inconsistent with witness_traces`);
  }

  // --- INV_OPROMO_2: perturbation stability ---
  for (const plogKey of ['removals_tested', 'additions_tested', 'pattern_survived_all']) {
    if (!(plogKey in perturbationLog)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: INV_OPROMO_2 'perturbation_log' missing '${plogKey}'`);
    }
  }
  if (!Array.isArray(perturbationLog.removals_tested) || perturbationLog.removals_tested.length === 0) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_2 'removals_tested' must be non-empty array`);
  }
  if (!Array.isArray(perturbationLog.additions_tested) || perturbationLog.additions_tested.length === 0) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_2 'additions_tested' must be non-empty array`);
  }
  if (perturbationLog.pattern_survived_all !== true) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_2 'pattern_survived_all' must be true, got ${perturbationLog.pattern_survived_all}`);
  }

  // --- INV_OPROMO_3: host cannot mint (seed authority only) ---
  if (authority.source !== 'seed') {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_3 authority.source must be 'seed', got '${authority.source}'`);
  }
  const seedFile = authority.seed_file;
  // Full-lock gate: only accept seeds with checksum + projection ID verification
  if (!seedLoader.isFullyLockedSeed(seedFile)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_3 seed not verification-locked: ${seedFile}`);
  }
  let seedProjIds;
  try {
    const subdir = seedLoader.getSeedSubdir(seedFile);
    const seed = seedLoader.loadVerifiedSeed(seedFile, subdir);
    seedProjIds = new Set(seed.projections.map(p => p.id));
  } catch (err) {
    if (err instanceof RcxError) throw err;
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_3 seed resolution failed for '${seedFile}': ${err.message}`);
  }
  const missingIds = authority.projection_ids.filter(pid => !seedProjIds.has(pid));
  if (missingIds.length > 0) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_3 projection_ids not found in seed '${seedFile}': ${JSON.stringify(missingIds)}`);
  }
}

/**
 * Build an ontology promotion candidate record from runtime evidence.
 * Assembles the 8-field record required by the A12 validator.
 * Auto-generates derivation_timestamp and substrate_versions.
 * Enforces authority.source = 'seed' regardless of evidence input.
 */
function buildOntologyPromotionCandidate(evidence, contextStr) {
  if (typeof evidence !== 'object' || evidence === null || Array.isArray(evidence)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: evidence must be object, ` +
      `got ${evidence === null ? 'null' : Array.isArray(evidence) ? 'array' : typeof evidence}`);
  }
  const requiredKeys = [
    'witness_traces', 'seed_configs', 'closure_structure',
    'perturbation_log', 'tau_lineage', 'authority',
  ];
  for (const key of requiredKeys) {
    if (!(key in evidence)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: evidence missing required key '${key}'`);
    }
  }
  const authority = evidence.authority;
  if (typeof authority !== 'object' || authority === null || Array.isArray(authority)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: evidence 'authority' must be object, ` +
      `got ${authority === null ? 'null' : Array.isArray(authority) ? 'array' : typeof authority}`);
  }
  for (const authKey of ['seed_file', 'projection_ids']) {
    if (!(authKey in authority)) {
      throw new RcxError('input.shape_mismatch',
        `${contextStr}: evidence 'authority' missing '${authKey}'`);
    }
  }

  const seedFile = authority.seed_file;

  // Correction #5: full-lock gate (early reject, before checksum lookup).
  if (!seedLoader.isFullyLockedSeed(seedFile)) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_3/producer seed not verification-locked: '${seedFile}'`);
  }

  // Correction #1: typed fail-closed for seed checksum resolution.
  const checksum = seedLoader.getSeedChecksum(seedFile);
  if (checksum === null) {
    throw new RcxError('input.shape_mismatch',
      `${contextStr}: INV_OPROMO_4/producer seed checksum not found ` +
      `for '${seedFile}' — seed not in CORE_SEED_CHECKSUMS registry`);
  }

  return {
    witness_traces: evidence.witness_traces,
    seed_configs: evidence.seed_configs,
    closure_structure: evidence.closure_structure,
    perturbation_log: evidence.perturbation_log,
    tau_lineage: evidence.tau_lineage,
    derivation_timestamp: 'derived:' + checksum,  // CONTRABAND_OK: deterministic derivation from seed checksum (replaces wall-clock new Date())
    substrate_versions: { python: checksum, js: checksum },
    authority: {
      source: 'seed',
      seed_file: authority.seed_file,
      projection_ids: authority.projection_ids,
    },
  };
}

/**
 * Build an observation record from a boundary result (A17).
 * Extracts trace metadata when available, computes control_hash.
 * BOUNDARY — evidence collection (off kernel path, engine boundary-effect servicing)
 */
function collectOntologyEvidence(result, operation) {
  const controlHash = muHashControlCached(result, 'evidence_collector');

  let traceLen = null;
  let stall = null;
  let projectionIds = null;

  if (result !== null && typeof result === 'object' && !Array.isArray(result) && 'trace' in result) {
    traceLen = 0;
    const projSet = new Set();
    const visited = new Set();  // Cycle detection (parity with Python visited_ids)
    const MAX_DRAIN = 100000;   // Iteration cap (parity with Python _MAX_TRACE_ENTRIES_HARD_CAP)
    let node = result.trace;
    while (node !== null && typeof node === 'object' && 'head' in node) {
      if (visited.has(node)) break;   // cyclic — stop draining
      visited.add(node);
      if (traceLen >= MAX_DRAIN) break;  // iteration cap — defense-in-depth
      traceLen++;
      const entry = node.head;
      // C4: only collect string IDs — skip int/dict/null for parity with Python.
      if (entry !== null && typeof entry === 'object' && typeof entry.projection === 'string') {
        projSet.add(entry.projection);
      }
      node = ('tail' in node) ? node.tail : null;
    }
    projectionIds = [...projSet].sort();
    stall = result.stall ?? null;
  }

  return {
    operation: operation,
    trace_len: traceLen,
    stall: stall,
    projection_ids: projectionIds,
    control_hash: controlHash,
    collected_at: 'derived:' + controlHash,  // CONTRABAND_OK: deterministic derivation from control hash (replaces wall-clock new Date())
  };
}

// Boot1 re-entry depth limit
const BOOT1_MAX_REENTRY_DEPTH = 20;

/**
 * Host loop that drives the engine state machine (rcx_engine.v1.json).
 * Parameterized: takes kernelProjections, seedProjectionMap, and engineProjections.
 * BOUNDARY: host orchestrator loop (off kernel path — CALLS stepKernel, not called BY it).
 * Reclassified P7W4: was host iteration debt, now BOUNDARY.
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
    vmConfig: pipelineVmConfig = null,
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
        kernelProjections, seedProjectionMap, nextState._boundary_request, maxAlgorithmIterations, emit, iteration, state, pipelineVmConfig
      );
      continue;
    }

    if (typeof nextState === 'object' && nextState !== null
        && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
      const tailPayload = nextState._tail_call;
      validateReentryPayload(tailPayload, 'trampoline _tail_call');
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
 * BOUNDARY: Engine pipeline runner — off kernel path. Reclassified P7W5: was host iteration marker.
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
    vmConfig: recursiveVmConfig = null,
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
          kernelProjections, seedProjectionMap, nextState._boundary_request, maxAlgorithmIterations, emit, iteration, state, recursiveVmConfig
        );
        continue;
      }

      if (typeof nextState === 'object' && nextState !== null
          && '_run_engine' in nextState && Object.keys(nextState).length === 1) {
        const payload = nextState._run_engine;
        validateReentryPayload(payload, 'Boot1 _run_engine');
        curProjections = payload.projections;
        curInput = payload.input;
        curMaxSteps = payload.max_steps ?? curMaxSteps;
        curFrozen = payload.frozen ?? null;
        remainingIterations = remainingIterations - iteration - 1;
        depth++;
        reentry = true;
        break;
      }

      if (typeof nextState === 'object' && nextState !== null
          && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
        const payload = nextState._tail_call;
        validateReentryPayload(payload, 'Boot1 _tail_call');
        curProjections = payload.projections;
        curInput = payload.input;
        curMaxSteps = payload.max_steps ?? curMaxSteps;
        curFrozen = payload.frozen ?? null;
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
  validateReentryPayload,
  validateOntologyPromotionRecord,
  buildOntologyPromotionCandidate,
  collectOntologyEvidence,
  runAlgorithmWithBridge,
  runSubAlgorithm,
  hashTraceForRecurrence,
  serviceBoundaryEffect,
  runEnginePipeline,
  runEnginePipelineRecursive,
  _clearBoundaryOpsCache,
  _ensureBoundaryOps,
  setTestDispatchOverride,
  enableTestMode,
};
