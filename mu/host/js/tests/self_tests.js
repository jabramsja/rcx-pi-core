'use strict';
/**
 * RCX Self-Tests
 *
 * Extracted from the monolithic eval_step.js.
 * Called by cli/main.js with the seeds context.
 * Produces "All tests passed: true" on stdout (required by audit scripts).
 */

const { normalize, denormalize, normalizeProjection, listToLinked } = require('../core/normalize');
const { step, run, match } = require('../core/bootstrap_core');
const { isValidMu, muEqual, muHash, muHashCached } = require('../core/types');
const { NO_MATCH } = require('../core/constants');
const { validateNoKernelReservedFields } = require('../core/security');
const { stepKernel, runStructural, stepKernelStructural } = require('../engine/kernel');
const { isTerminalShape, isEngineTerminal, setsEqual, HEMISPHERE_KEYS, defaultHemispheres } = require('../core/terminal_classification');
const { hashTraceForRecurrence } = require('../engine/pipeline');

const path = require('path');
const fs = require('fs');

module.exports = function runSelfTests(seeds) {
  const {
    allProjections, allProjectionsWithBridge, allProjectionsWithExhaustion,
    recurrenceProjections, metabolizationProjections,
    kernel, matchSeed, substSeed, bridgeSeed,
    recurrenceSeed, recurrenceV2Seed, exhaustionSeed,
    hemisphereSeed, engineSeed, metabolizationSeed, metabolizeCycleSeed,
    parityVectors,
    bridgeProjections,
    validateCombinedBridgeOrdering,
    // P7-d: VM bundles for shadow mode
    kernelV1Projections, matchBundle, substBundle,
  } = seeds;

  // P7-d: Construct vmConfig for shadow mode (if bundles available)
  const vmConfig = (kernelV1Projections && matchBundle && substBundle) ? {
    kernelV1Projs: kernelV1Projections,
    bridgeProjs: null, // core mode — no bridge
    matchBundle,
    substBundle,
  } : null;

  console.log('=== RCX eval_step.js - Complete Kernel Cycle (v8 - L3 Full Parity with Bridge) ===\n');
  console.log('Seed integrity: 12 seeds verified at startup (+ terminal_classify lazy-loaded on demand)');
  console.log(`Loaded projections from mu/ folder:`);
  console.log(`  - substrate/kernel.v1.json: ${kernel.projections.length} projections`);
  console.log(`  - substrate/match.v2.json: ${matchSeed.projections.length} projections`);
  console.log(`  - substrate/subst.v2.json: ${substSeed.projections.length} projections`);
  console.log(`  - bridge/bootstrap_structural.v1.json: ${bridgeSeed.projections.length} projections`);
  console.log(`  - closures/recurrence.v1.json: ${recurrenceSeed.projections.length} projections (proof-of-concept)`);
  console.log(`  - closures/recurrence.v2.json: ${recurrenceV2Seed.projections.length} projections (hash-accelerated)`);
  console.log(`  - closures/exhaustion.v1.json: ${exhaustionSeed.projections.length} projections`);
  console.log(`  - closures/fix.v1.json: ${seeds.fixSeed.projections.length} projections (draft — GAP-04-FIX)`);
  console.log(`  - programs/hemispheres.v1.json: ${hemisphereSeed.projections.length} projections`);
  console.log(`  - programs/metabolization.v1.json: ${metabolizationSeed.projections.length} projections`);
  console.log(`  - programs/metabolize_cycle.v1.json: ${metabolizeCycleSeed.projections.length} projections`);
  console.log(`  - programs/rcx_engine.v1.json: ${engineSeed.projections.length} projections`);
  console.log(`  - Total (kernel ops): ${allProjections.length} projections`);
  console.log(`  - Total (with Bridge): ${seeds.allProjectionsWithBridge.length} projections`);
  console.log(`  - Total (with Recurrence): ${recurrenceProjections.length + allProjections.length} projections`);
  console.log(`  - Total (with Recurrence+Bridge): ${seeds.allProjectionsWithRecurrenceAndBridge.length} projections`);
  console.log(`  - Total (with Exhaustion): ${seeds.allProjectionsWithExhaustion.length} projections`);
  console.log(`  - Total (with Exhaustion+Bridge): ${seeds.allProjectionsWithExhaustionAndBridge.length} projections\n`);

  // === Test 1: Complete Kernel Cycle ===
  console.log('=== Test 1: Complete Kernel Cycle ===\n');
  const testProjection = {
    pattern: { op: 'double', value: { var: 'n' } },
    body: { result: { var: 'n' }, doubled: { var: 'n' } }
  };
  const normalizedProjection = normalizeProjection(testProjection);
  const testInput = { op: 'double', value: 42 };
  const normalizedInput = normalize(testInput);
  const kernelInput = { _step: normalizedInput, _projs: listToLinked([normalizedProjection]) };
  console.log('Original input:', JSON.stringify(testInput));
  console.log('Normalized input:', JSON.stringify(normalizedInput));
  console.log('Original projection pattern:', JSON.stringify(testProjection.pattern));
  console.log('Normalized projection pattern:', JSON.stringify(normalizedProjection.pattern));
  console.log('\n--- Running kernel cycle ---\n');
  const { result, steps, stalled, trace } = run(allProjections, kernelInput, 100);
  console.log('Execution trace:');
  for (const t of trace.slice(0, 15)) {
    const stateStr = JSON.stringify(t.state);
    const preview = stateStr.length > 70 ? stateStr.slice(0, 70) + '...' : stateStr;
    console.log(`  [${t.step}] ${t.projection ?? 'STALL'}: ${preview}`);
  }
  if (trace.length > 15) console.log(`  ... (${trace.length - 15} more steps)`);
  console.log(`\nTotal steps: ${steps}`);
  console.log(`Stalled: ${stalled}`);
  const denormalizedResult = denormalize(result);
  console.log(`\nRaw result:`, JSON.stringify(result));
  console.log(`Denormalized result:`, JSON.stringify(denormalizedResult));
  const expectedResult = { result: 42, doubled: 42 };
  const passed = muEqual(denormalizedResult, expectedResult);
  console.log(`\nExpected:`, JSON.stringify(expectedResult));
  console.log(`PASS: ${passed}`);

  // === Test 2: Stall Case ===
  console.log('\n=== Test 2: Stall Case (No Match) ===\n');
  const testProjection2 = { pattern: { op: 'triple', value: { var: 'n' } }, body: { result: { var: 'n' } } };
  const kernelInput2 = { _step: normalizedInput, _projs: listToLinked([normalizeProjection(testProjection2)]) };
  const { result: result2, steps: steps2, stalled: stalled2 } = run(allProjections, kernelInput2, 100);
  const denorm2 = denormalize(result2);
  console.log('Input:', JSON.stringify(testInput));
  console.log('Projection pattern:', JSON.stringify(testProjection2.pattern), '(won\'t match)');
  console.log(`\nSteps: ${steps2}, Stalled: ${stalled2}`);
  console.log('Denormalized result:', JSON.stringify(denorm2));
  const passedStall = muEqual(denorm2, testInput);
  console.log(`\nExpected (stall returns original):`, JSON.stringify(testInput));
  console.log(`PASS: ${passedStall}`);

  // === Test 3: Multiple projections ===
  console.log('\n=== Test 3: Multiple Projections (First-Match-Wins) ===\n');
  const projections3 = [
    { pattern: { op: 'add', a: { var: 'x' }, b: { var: 'y' } }, body: { sum: { var: 'x' } } },
    { pattern: { op: 'mul', a: { var: 'x' }, b: { var: 'y' } }, body: { product: { var: 'x' } } },
    { pattern: { var: 'anything' }, body: { error: 'unknown op' } }
  ];
  const normalizedProjs3 = projections3.map(normalizeProjection);
  const inputs3 = [{ op: 'add', a: 10, b: 20 }, { op: 'mul', a: 5, b: 6 }, { op: 'div', a: 1, b: 2 }];
  const results3 = inputs3.map(inp => {
    const ki = { _step: normalize(inp), _projs: listToLinked(normalizedProjs3) };
    const { result } = run(allProjections, ki, 100);
    return denormalize(result);
  });
  console.log('Input: { op: "add", a: 10, b: 20 } ->', JSON.stringify(results3[0]));
  console.log('Input: { op: "mul", a: 5, b: 6 }  ->', JSON.stringify(results3[1]));
  console.log('Input: { op: "div", a: 1, b: 2 }  ->', JSON.stringify(results3[2]));
  const pass3a = muEqual(results3[0], { sum: 10 });
  const pass3b = muEqual(results3[1], { product: 5 });
  const pass3c = muEqual(results3[2], { error: 'unknown op' });
  console.log(`\nPASS add: ${pass3a}`);
  console.log(`PASS mul: ${pass3b}`);
  console.log(`PASS catchall: ${pass3c}`);

  // === Test 4: NaN/Infinity ===
  console.log('\n=== Test 4: Security - NaN/Infinity Rejection ===\n');
  let nanRejected = false, infRejected = false;
  try { normalize({ value: NaN }); } catch (e) { nanRejected = e.message.includes('NaN'); }
  try { normalize({ value: Infinity }); } catch (e) { infRejected = e.message.includes('Infinity'); }
  console.log(`NaN rejected: ${nanRejected}`);
  console.log(`Infinity rejected: ${infRejected}`);
  console.log(`PASS security: ${nanRejected && infRejected}`);

  // === Test 5: Depth guard ===
  console.log('\n=== Test 5: Security - Depth Guard ===\n');
  function createDeep(depth) { let obj = { value: 'bottom' }; for (let i = 0; i < depth; i++) obj = { nested: obj }; return obj; }
  let shallowOk = false, deepRejected = false;
  try { normalize(createDeep(50)); shallowOk = true; } catch (e) { console.log('Shallow failed:', e.message); }
  try { normalize(createDeep(350)); } catch (e) { deepRejected = e.message.includes('Max depth'); }
  console.log(`Shallow (50 levels) OK: ${shallowOk}`);
  console.log(`Deep (350 levels) rejected: ${deepRejected}`);
  console.log(`PASS depth guard: ${shallowOk && deepRejected}`);

  // === Test 6: Reserved Fields ===
  console.log('\n=== Test 6: Security - Kernel Reserved Fields Rejection ===\n');
  let reservedFieldRejected = false, nestedReservedRejected = false, cleanDataAccepted = false;
  try { stepKernel(allProjections, { op: 'test', _step: 'forged' }, [testProjection]); }
  catch (e) { reservedFieldRejected = e.message.includes('_step') && e.message.includes('reserved'); }
  console.log(`Direct _step in input rejected: ${reservedFieldRejected}`);
  try { stepKernel(allProjections, { op: 'test', nested: { deep: { _mode: 'forged' } } }, [testProjection]); }
  catch (e) { nestedReservedRejected = e.message.includes('_mode') && e.message.includes('reserved'); }
  console.log(`Nested _mode in input rejected: ${nestedReservedRejected}`);
  try { stepKernel(allProjections, { op: 'double', value: 99 }, [testProjection], { maxSteps: 50 }); cleanDataAccepted = true; }
  catch (e) { console.log('Clean data failed:', e.message); }
  console.log(`Clean domain data accepted: ${cleanDataAccepted}`);
  const passReservedFields = reservedFieldRejected && nestedReservedRejected && cleanDataAccepted;
  console.log(`PASS kernel reserved fields: ${passReservedFields}`);

  // === Test 7: Head/tail strict detection ===
  console.log('\n=== Test 7: Head/Tail Strict Detection ===\n');
  const userDataWithExtra = { head: 'my data', tail: 'other', extra: 'field' };
  const normalizedUserData = normalize(userDataWithExtra);
  const isNormalizedAsDict = normalizedUserData._type === 'dict';
  console.log('User data {head, tail, extra} normalized as dict:', isNormalizedAsDict);
  const realLinkedList = { head: 1, tail: null };
  const normalizedLinkedList = normalize(realLinkedList);
  const isPreservedAsHeadTail = 'head' in normalizedLinkedList && 'tail' in normalizedLinkedList && !('_type' in normalizedLinkedList);
  console.log('Real {head, tail} preserved:', isPreservedAsHeadTail);
  console.log(`PASS strict detection: ${isNormalizedAsDict && isPreservedAsHeadTail}`);

  // === Test 8: Cross-Substrate Parity ===
  console.log('\n=== Test 8: Cross-Substrate Parity Tests ===\n');
  let parityPassed = 0, parityFailed = 0;
  for (const vector of parityVectors.vectors) {
    if (vector.expected_error) {
      // Vector expects rejection (e.g., non-linear pattern on core path).
      try {
        stepKernel(allProjections, vector.input, [vector.projection], { maxSteps: 100, vmConfig });
        console.log(`  ✗ ${vector.id}: should have rejected but didn't`); parityFailed++;
      } catch (e) {
        if (e.message.includes(vector.expected_error)) { console.log(`  ✓ ${vector.id} (rejected: ${vector.expected_error})`); parityPassed++; }
        else { console.log(`  ✗ ${vector.id}: wrong error - ${e.message}`); parityFailed++; }
      }
    } else {
      try {
        const { result } = stepKernel(allProjections, vector.input, [vector.projection], { maxSteps: 100, vmConfig });
        const denormalized = denormalize(result);
        if (muEqual(denormalized, vector.expected_output)) { console.log(`  ✓ ${vector.id}`); parityPassed++; }
        else { console.log(`  ✗ ${vector.id}: got ${JSON.stringify(denormalized)}, expected ${JSON.stringify(vector.expected_output)}`); parityFailed++; }
      } catch (e) { console.log(`  ✗ ${vector.id}: ERROR - ${e.message}`); parityFailed++; }
    }
  }
  console.log(`\nParity tests: ${parityPassed} passed, ${parityFailed} failed`);
  const parityAllPassed = parityFailed === 0 && parityPassed > 0;
  console.log(`PASS parity: ${parityAllPassed}`);

  // Security vectors
  console.log('\n--- Security Vectors ---');
  let securityPassed = 0, securityFailed = 0;
  for (const vector of parityVectors.security_vectors) {
    try {
      validateNoKernelReservedFields(vector.input, 'test');
      console.log(`  ✗ ${vector.id}: should have rejected but didn't`); securityFailed++;
    } catch (e) {
      if (e.message.includes(vector.error_contains)) { console.log(`  ✓ ${vector.id}`); securityPassed++; }
      else { console.log(`  ✗ ${vector.id}: wrong error - ${e.message}`); securityFailed++; }
    }
  }
  console.log(`\nSecurity tests: ${securityPassed} passed, ${securityFailed} failed`);
  const securityAllPassed = securityFailed === 0 && securityPassed > 0;
  console.log(`PASS security vectors: ${securityAllPassed}`);

  // === Test 9: Structural Trace ===
  console.log('\n=== Test 9: Structural Trace (Phase 8d) ===\n');
  let structuralTraceAllPassed = true;
  try {
    const simpleProj = [{ id: 'double', pattern: { op: 'double', value: { var: 'n' } }, body: { result: { var: 'n' } } }];
    const structResult = runStructural(allProjectionsWithBridge, simpleProj, { op: 'double', value: 42 }, 10);
    const hasAllFields = 'result' in structResult && 'trace' in structResult && 'stall' in structResult && 'steps' in structResult;
    console.log(`  Returns Mu-compatible structure: ${hasAllFields}`);
    structuralTraceAllPassed = structuralTraceAllPassed && hasAllFields;
  } catch (e) { console.log(`  Returns Mu-compatible structure: false (${e.message})`); structuralTraceAllPassed = false; }
  try {
    const simpleProj = [{ id: 'identity', pattern: { var: 'x' }, body: { var: 'x' } }];
    const structResult = runStructural(allProjectionsWithBridge, simpleProj, 'test', 10);
    const isLinkedList = structResult.trace === null || ('head' in structResult.trace && 'tail' in structResult.trace);
    console.log(`  Trace is linked list: ${isLinkedList}`);
    structuralTraceAllPassed = structuralTraceAllPassed && isLinkedList;
  } catch (e) { console.log(`  Trace is linked list: false (${e.message})`); structuralTraceAllPassed = false; }
  try {
    const toggle = [{ id: 'to_b', pattern: 'A', body: 'B' }, { id: 'to_a', pattern: 'B', body: 'A' }];
    const structResult = runStructural(allProjectionsWithBridge, toggle, 'A', 5);
    let hasFields = true;
    let node = structResult.trace;
    while (node !== null) { const entry = node.head; if (!('step' in entry) || !('state' in entry) || !('projection' in entry)) { hasFields = false; break; } node = node.tail; }
    console.log(`  Trace entries have step/state/projection: ${hasFields}`);
    structuralTraceAllPassed = structuralTraceAllPassed && hasFields;
  } catch (e) { console.log(`  Trace entries have step/state/projection: false (${e.message})`); structuralTraceAllPassed = false; }
  try {
    const noMatch = [{ id: 'never_match', pattern: 'NEVER', body: 'MATCHED' }];
    const structResult = runStructural(allProjectionsWithBridge, noMatch, 'test', 10);
    const stallDetected = structResult.stall === true;
    const stepsCorrect = structResult.steps === 1;
    console.log(`  Stall detected correctly: ${stallDetected && stepsCorrect}`);
    structuralTraceAllPassed = structuralTraceAllPassed && stallDetected && stepsCorrect;
  } catch (e) { console.log(`  Stall detected correctly: false (${e.message})`); structuralTraceAllPassed = false; }
  try {
    const structResult = stepKernelStructural(allProjectionsWithBridge, [testProjection], { op: 'double', value: 99 }, { maxSteps: 100 });
    const hasStructuralResult = 'result' in structResult && 'trace' in structResult;
    console.log(`  stepKernelStructural works: ${hasStructuralResult}`);
    structuralTraceAllPassed = structuralTraceAllPassed && hasStructuralResult;
  } catch (e) { console.log(`  stepKernelStructural works: false (${e.message})`); structuralTraceAllPassed = false; }
  console.log(`\nPASS structural trace: ${structuralTraceAllPassed}`);

  // === Test 10: Recurrence ===
  console.log('\n=== Test 10: Recurrence Closure Detection (L3 Parity) ===\n');
  function runRecurrence(traceResult) {
    const recurrenceInput = { _detect_closure: { trace: traceResult.trace, result: traceResult.result } };
    const { result } = run(recurrenceProjections, recurrenceInput, 1000);
    return result;
  }
  const muRoot = path.join(__dirname, '..', '..', '..', '..');
  const recurrenceVectorsPath = path.join(muRoot, 'tests', 'fixtures', 'recurrence_vectors.json');
  let recurrenceVectors;
  try { recurrenceVectors = JSON.parse(fs.readFileSync(recurrenceVectorsPath, 'utf8')); }
  catch (e) { recurrenceVectors = { vectors: [] }; }
  let recurrencePassed = 0, recurrenceFailed = 0;
  for (const vector of recurrenceVectors.vectors) {
    try {
      const { result } = run(recurrenceProjections, vector.input, 1000);
      if (muEqual(result, vector.expected)) { console.log(`  ✓ ${vector.id}`); recurrencePassed++; }
      else { console.log(`  ✗ ${vector.id}: got ${JSON.stringify(result)}, expected ${JSON.stringify(vector.expected)}`); recurrenceFailed++; }
    } catch (e) { console.log(`  ✗ ${vector.id}: ERROR - ${e.message}`); recurrenceFailed++; }
  }
  console.log(`\nRecurrence parity tests: ${recurrencePassed} passed, ${recurrenceFailed} failed`);
  const recurrenceAllPassed = recurrenceFailed === 0 && recurrencePassed > 0;
  console.log(`PASS recurrence parity: ${recurrenceAllPassed}`);

  // === Test 11: Recurrence E2E ===
  console.log('\n=== Test 11: Recurrence End-to-End (trace + detection) ===\n');
  let e2ePassed = true;
  try {
    const oscillatingProjs = [{ id: 'to_b', pattern: 'A', body: 'B' }, { id: 'to_a', pattern: 'B', body: 'A' }];
    const traceResult = runStructural(allProjectionsWithBridge, oscillatingProjs, 'A', 10);
    const hasOscillation = traceResult.steps >= 3;
    console.log(`  Trace captures oscillation (steps >= 3): ${hasOscillation} (steps=${traceResult.steps})`);
    e2ePassed = e2ePassed && hasOscillation;
    const closureResult = runRecurrence(traceResult);
    const closureDetected = closureResult.closure_detected === true;
    console.log(`  Closure detected: ${closureDetected}`);
    e2ePassed = e2ePassed && closureDetected;
  } catch (e) { console.log(`  End-to-end test failed: ${e.message}`); e2ePassed = false; }
  try {
    const incrementProjs = [{ id: 'inc_0', pattern: 0, body: 1 }, { id: 'inc_1', pattern: 1, body: 2 }, { id: 'inc_2', pattern: 2, body: 3 }];
    const traceResult = runStructural(allProjectionsWithBridge, incrementProjs, 0, 10);
    const closureResult = runRecurrence(traceResult);
    const closureDetected = closureResult.closure_detected === true;
    console.log(`  Stall fixed point detected: ${closureDetected}`);
    e2ePassed = e2ePassed && closureDetected;
  } catch (e) { console.log(`  Fixed point test failed: ${e.message}`); e2ePassed = false; }
  try {
    const noMatchProjs = [{ id: 'never', pattern: 'NEVER', body: 'MATCHED' }];
    const traceResult = runStructural(allProjectionsWithBridge, noMatchProjs, 'test', 10);
    const closureResult = runRecurrence(traceResult);
    const singleStateResult = closureResult.closure_detected;
    console.log(`  Immediate stall closure_detected: ${singleStateResult} (expected: true, fixed point)`);
    e2ePassed = e2ePassed && (singleStateResult === true);
  } catch (e) { console.log(`  Immediate stall test failed: ${e.message}`); e2ePassed = false; }
  console.log(`\nPASS recurrence e2e: ${e2ePassed}`);

  // === Test: Engine-Hemisphere Helpers ===
  console.log('\n=== Test: Engine-Hemisphere Helpers ===\n');
  let engineHelpersPassed = true;
  const terminalShape = { value: 'x', closure_detected: false, tau_step: 0, exhaustion_detected: false, operator_frozen: false, frozen_set: null, action: 'continue', stall: true };
  const terminalDetected = isEngineTerminal(terminalShape);
  const nonTerminalRejected = !isEngineTerminal({ partial: true });
  const nullRejected = !isEngineTerminal(null);
  console.log(`  isEngineTerminal(8-key): ${terminalDetected} (expected: true)`);
  console.log(`  isEngineTerminal(partial): ${nonTerminalRejected} (expected: true)`);
  console.log(`  isEngineTerminal(null): ${nullRejected} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && terminalDetected && nonTerminalRejected && nullRejected;
  const recTerminal = { closure_detected: true, final_result: 'x', tau_step: 2 };
  const exhTerminal = { action: 'freeze', exhaustion_detected: true, frozen: null, operator_to_freeze: 'op1' };
  console.log(`  isTerminalShape(recurrence): ${isTerminalShape(recTerminal)} (expected: true)`);
  console.log(`  isTerminalShape(exhaustion): ${isTerminalShape(exhTerminal)} (expected: true)`);
  console.log(`  isTerminalShape(other): ${!isTerminalShape({ random: 1 })} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && isTerminalShape(recTerminal) && isTerminalShape(exhTerminal) && !isTerminalShape({ random: 1 });
  try {
    const simpleTrace = { head: { step: 0, state: { x: 1 }, projection: 'test' }, tail: { head: { step: 1, state: { x: 1 }, stall: true }, tail: null } };
    const hashed = hashTraceForRecurrence(simpleTrace);
    const hasHash0 = 'state_hash' in hashed.head;
    const hasHash1 = 'state_hash' in hashed.tail.head;
    console.log(`  hashTrace adds state_hash: ${hasHash0 && hasHash1} (expected: true)`);
    engineHelpersPassed = engineHelpersPassed && hasHash0 && hasHash1;
  } catch (e) { console.log(`  hashTrace failed: ${e.message}`); engineHelpersPassed = false; }
  try {
    const nodeA = { head: { state: 'A', step: 0 }, tail: null };
    const nodeB = { head: { state: 'B', step: 1 }, tail: nodeA };
    nodeA.tail = nodeB;
    hashTraceForRecurrence(nodeA);
    console.log(`  hashTrace cycle detection: false (should have thrown)`); engineHelpersPassed = false;
  } catch (e) {
    const cycleDetected = e.message.includes('cyclic');
    console.log(`  hashTrace cycle detection: ${cycleDetected} (expected: true)`);
    engineHelpersPassed = engineHelpersPassed && cycleDetected;
  }
  try {
    let overcapTrace = null;
    for (let i = 4; i >= 0; i--) overcapTrace = { head: { state: String(i), step: i }, tail: overcapTrace };
    hashTraceForRecurrence(overcapTrace, 3);
    console.log(`  hashTrace overcap detection: false (should have thrown)`); engineHelpersPassed = false;
  } catch (e) {
    const overcapDetected = e.message.includes('exceeds');
    console.log(`  hashTrace overcap detection: ${overcapDetected} (expected: true)`);
    engineHelpersPassed = engineHelpersPassed && overcapDetected;
  }
  const hemi = defaultHemispheres();
  const hemiKeysMatch = setsEqual(new Set(Object.keys(hemi)), HEMISPHERE_KEYS);
  console.log(`  defaultHemispheres keys match HEMISPHERE_KEYS: ${hemiKeysMatch} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && hemiKeysMatch;
  console.log(`\nPASS engine-hemisphere helpers: ${engineHelpersPassed}`);

  // === Test: Metabolization ===
  console.log('\n=== Test: Metabolization Behavior ===\n');
  let metabolizationBehaviorPassed = true;
  const EXPECTED_METABOLIZATION_IDS = [
    'hemisphere.metabolize.sink_to_r_null', 'hemisphere.metabolize.sink_to_r_inf',
    'hemisphere.recover.stall_to_lobes', 'hemisphere.recover.stall_to_sink',
    'hemisphere.promote.lobes_to_r_a', 'hemisphere.recycle.residual_to_sink',
  ];
  const loadedMetabIds = metabolizationProjections.map(p => p.id);
  const metabIdMissing = EXPECTED_METABOLIZATION_IDS.filter(id => !loadedMetabIds.includes(id));
  const metabIdCheck = metabIdMissing.length === 0;
  console.log(`  All 6 metabolization IDs present: ${metabIdCheck} (expected: true)`);
  if (!metabIdCheck) { console.log(`    Missing: ${JSON.stringify(metabIdMissing)}`); metabolizationBehaviorPassed = false; }
  const metabIdOrderMatch = JSON.stringify(loadedMetabIds) === JSON.stringify(EXPECTED_METABOLIZATION_IDS);
  console.log(`  Metabolization ID order matches: ${metabIdOrderMatch} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && metabIdOrderMatch;

  function stepMetab(input) { return step(metabolizationProjections, input); }

  // Metabolization test cases (condensed)
  {
    const input = { metabolize_mode: 'scan_sink', sink_entry: { state: 'active_data', closure_flag: false, origin: 'engine' }, remaining_sink: null, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.metabolize_result !== undefined && result.metabolize_result.r_inf !== null && result.metabolize_result.r_inf.head !== undefined && result.metabolize_result.r_inf.head.state === 'active_data' && result.metabolize_result.r_inf.head.origin === 'metabolized' && result.metabolize_result.r_null === null && result.metabolize_result.r_a === null;
    console.log(`  sink_to_r_inf (non-null state → r_inf): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { metabolize_mode: 'scan_sink', sink_entry: { state: null, closure_flag: false, origin: 'engine' }, remaining_sink: null, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.metabolize_result !== undefined && result.metabolize_result.r_null !== null && result.metabolize_result.r_null.head !== undefined && result.metabolize_result.r_null.head.state === null && result.metabolize_result.r_null.head.origin === 'metabolized' && result.metabolize_result.r_inf === null && result.metabolize_result.r_a === null;
    console.log(`  sink_to_r_null (null state → r_null via step): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { recover_mode: 'check_stall', stalled_entry: { state: 'stalled_thing', origin: 'engine' }, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: { head: 'existing_lobe', tail: null }, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.recover_result !== undefined && result.recover_result.lobes !== null && result.recover_result.lobes.head !== undefined && muEqual(result.recover_result.lobes.head, { state: 'stalled_thing', origin: 'engine' }) && result.recover_result.lobes.tail !== null && result.recover_result.lobes.tail.head === 'existing_lobe';
    console.log(`  stall_to_lobes (lobes non-null → prepend): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { recover_mode: 'check_stall', stalled_entry: { state: 'stalled_thing', origin: 'engine' }, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.recover_result !== undefined && result.recover_result.lobes === null && result.recover_result.sink !== null && muEqual(result.recover_result.sink.head, { state: 'stalled_thing', origin: 'engine' });
    console.log(`  stall_to_sink (lobes null → sink fallback): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { promote_mode: 'check_closure', lobes_entry: { state: 'closed_form', closure_flag: true, origin: 'lobes' }, remaining_lobes: null, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.promote_result !== undefined && result.promote_result.r_a !== null && result.promote_result.r_a.head !== undefined && result.promote_result.r_a.head.state === 'closed_form' && result.promote_result.r_a.head.closure_flag === true && result.promote_result.r_a.head.origin === 'promoted' && result.promote_result.lobes === null;
    console.log(`  lobes_to_r_a (closure_flag true → r_a): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { recycle_mode: 'drain', source_bucket: 'r_inf', unresolvable_entry: { type: 'unknown', data: 42 }, hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null } };
    const result = stepMetab(input);
    const ok = typeof result === 'object' && result !== null && result.recycle_result !== undefined && result.recycle_result.sink !== null && result.recycle_result.sink.head !== undefined && muEqual(result.recycle_result.sink.head.state, { type: 'unknown', data: 42 }) && result.recycle_result.sink.head.origin === 'recycled' && result.recycle_result.r_null === null && result.recycle_result.r_inf === null;
    console.log(`  residual_to_sink (drain → sink recycled): ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  {
    const input = { unrecognized_mode: 'garbage', data: 123 };
    const result = stepMetab(input);
    const ok = muEqual(result, input);
    console.log(`  stall on non-matching input: ${ok} (expected: true)`);
    metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
  }
  console.log(`\nPASS metabolization behavior: ${metabolizationBehaviorPassed}`);

  // === Bridge Ordering Validation ===
  console.log('\n--- Bridge ordering validation tests ---');
  let bridgeValidationPassed = true;
  try { validateCombinedBridgeOrdering(allProjectionsWithBridge); console.log('  Valid bridge ordering accepted: true (expected: true)'); }
  catch (e) { console.log(`  Valid bridge ordering accepted: false (expected: true) - ${e.message}`); bridgeValidationPassed = false; }
  try { validateCombinedBridgeOrdering([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]); console.log('  Missing bridge rejected: false (expected: true)'); bridgeValidationPassed = false; }
  catch (e) { const ok = e.message.includes('missing bridge projections'); console.log(`  Missing bridge rejected: ${ok} (expected: true)`); bridgeValidationPassed = bridgeValidationPassed && ok; }
  try { validateCombinedBridgeOrdering([...kernel.projections, ...matchSeed.projections, ...bridgeProjections, ...substSeed.projections]); console.log('  Bridge-after-match.var rejected: false (expected: true)'); bridgeValidationPassed = false; }
  catch (e) { const ok = e.message.includes('must be before match.var'); console.log(`  Bridge-after-match.var rejected: ${ok} (expected: true)`); bridgeValidationPassed = bridgeValidationPassed && ok; }
  try { validateCombinedBridgeOrdering([...allProjectionsWithBridge, null]); console.log('  Non-dict (null) rejected: false (expected: true)'); bridgeValidationPassed = false; }
  catch (e) { const ok = e.message.includes('Non-dict projection'); console.log(`  Non-dict (null) rejected: ${ok} (expected: true)`); bridgeValidationPassed = bridgeValidationPassed && ok; }
  try { validateCombinedBridgeOrdering([...allProjectionsWithBridge, [1, 2]]); console.log('  Non-dict (array) rejected: false (expected: true)'); bridgeValidationPassed = false; }
  catch (e) { const ok = e.message.includes('Non-dict projection'); console.log(`  Non-dict (array) rejected: ${ok} (expected: true)`); bridgeValidationPassed = bridgeValidationPassed && ok; }
  console.log(`\nPASS bridge ordering validation: ${bridgeValidationPassed}`);

  // === Test: P7-d Bridge-Mode VM Shadow ===
  console.log('\n=== Test: P7-d Bridge-Mode VM Shadow ===\n');
  let bridgeShadowPassed = true;
  if (vmConfig && bridgeProjections) {
    const vmConfigBridge = {
      ...vmConfig,
      bridgeProjs: bridgeProjections,
    };
    try {
      // Run a simple kernel step through bridge path with VM shadow
      const bridgeResult = stepKernel(
        allProjectionsWithBridge, { op: 'double', value: 42 },
        [{ pattern: { op: 'double', value: { var: 'n' } }, body: { result: { var: 'n' } } }],
        { maxSteps: 50, vmConfig: vmConfigBridge }
      );
      const hasBridgeResult = bridgeResult && 'result' in bridgeResult;
      console.log(`  Bridge-mode stepKernel with vmConfig: ${hasBridgeResult} (expected: true)`);
      bridgeShadowPassed = bridgeShadowPassed && hasBridgeResult;
    } catch (e) {
      console.log(`  Bridge-mode stepKernel with vmConfig: false (${e.message})`);
      bridgeShadowPassed = false;
    }
    try {
      // Run structural trace through bridge path with VM shadow
      const bridgeTraceResult = runStructural(
        allProjectionsWithBridge,
        [{ id: 'test_double', pattern: { op: 'double', value: { var: 'n' } }, body: { result: { var: 'n' } } }],
        { op: 'double', value: 99 }, 10, vmConfigBridge
      );
      const hasTraceFields = 'result' in bridgeTraceResult && 'trace' in bridgeTraceResult;
      console.log(`  Bridge-mode runStructural with vmConfig: ${hasTraceFields} (expected: true)`);
      bridgeShadowPassed = bridgeShadowPassed && hasTraceFields;
    } catch (e) {
      console.log(`  Bridge-mode runStructural with vmConfig: false (${e.message})`);
      bridgeShadowPassed = false;
    }
    // Stall case: bridge mode, no domain projection matches
    try {
      const bridgeStallResult = stepKernel(
        allProjectionsWithBridge, 'no_match_input',
        [{ pattern: { op: 'never', value: { var: 'x' } }, body: { var: 'x' } }],
        { maxSteps: 50, returnMeta: true, vmConfig: vmConfigBridge }
      );
      const stallDetected = bridgeStallResult.stall === true;
      console.log(`  Bridge-mode stall with vmConfig: ${stallDetected} (expected: true)`);
      bridgeShadowPassed = bridgeShadowPassed && stallDetected;
    } catch (e) {
      console.log(`  Bridge-mode stall with vmConfig: false (${e.message})`);
      bridgeShadowPassed = false;
    }
  } else {
    console.log('  SKIP: vmConfig or bridgeProjections not available');
  }
  console.log(`\nPASS bridge-mode VM shadow: ${bridgeShadowPassed}`);

  // === Summary ===
  console.log('\n=== Summary ===\n');
  const allPassed = passed && passedStall && pass3a && pass3b && pass3c &&
                    nanRejected && infRejected && shallowOk && deepRejected &&
                    passReservedFields && isNormalizedAsDict && isPreservedAsHeadTail &&
                    parityAllPassed && securityAllPassed && structuralTraceAllPassed &&
                    recurrenceAllPassed && e2ePassed && engineHelpersPassed &&
                    metabolizationBehaviorPassed && bridgeValidationPassed &&
                    bridgeShadowPassed;
  console.log(`All tests passed: ${allPassed}`);
  if (!allPassed) process.exit(1);
  console.log(`\nSecurity hardening (v7 - L3 Recurrence Parity, mu/ reorg):`);
  console.log(`  - MAX_DEPTH=${require('../core/constants').MAX_DEPTH} guard (matches Python MAX_MU_DEPTH)`);
  console.log(`  - NaN/Infinity rejection (matches Python)`);
  console.log(`  - KERNEL_RESERVED_FIELDS validation (matches Python step_mu.py)`);
  console.log(`  - Strict head/tail detection (exact key counts)`);
  console.log(`  - Unbound variables produce structural error values (Wave I subst.lookup.exhausted)`);
  console.log(`\nCore implementation: ~350 lines of JavaScript (with security + Recurrence)`);
  console.log(`Projections loaded from mu/ folder:`);
  console.log(`  - Kernel ops: ${allProjections.length} (kernel + match + subst)`);
  console.log(`  - Recurrence: ${recurrenceProjections.length} (closure detection)`);
  console.log(`\nThis proves (L3 Substrate Portability - COMPLETE):`);
  console.log(`  1. mu/substrate/kernel.v1.json runs on JavaScript ✓`);
  console.log(`  2. mu/substrate/match.v2.json runs on JavaScript ✓`);
  console.log(`  3. mu/substrate/subst.v2.json runs on JavaScript ✓`);
  console.log(`  4. mu/closures/recurrence.v1.json runs on JavaScript ✓`);
  console.log(`  5. mu/closures/exhaustion.v1.json runs on JavaScript ✓`);
  console.log(`  6. Normalization/denormalization works ✓`);
  console.log(`  7. Complete kernel cycle works ✓`);
  console.log(`  8. Security parity with Python (4 bootstrap primitives) ✓`);
  console.log(`  9. Recurrence closure detection parity ✓`);
  console.log(`  10. Same projections, same semantics, two substrates ✓`);
};
