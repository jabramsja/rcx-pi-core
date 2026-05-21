'use strict';
/**
 * RCX CLI Main — Seed loading, projection composition, self-tests, CLI output
 *
 * This is the runtime entrypoint. When executed directly or via eval_step.js shim:
 *   1. Loads and verifies 12 seeds at startup (+ registered lazy/runtime seeds on demand)
 *   2. Composes projection arrays
 *   3. If --json-api in process.argv, delegates to api/json_handlers.js
 *   4. Otherwise runs self-tests (console output with "All tests passed: true")
 *
 * BOOTSTRAP_PRIMITIVE: projection_loader
 * (fs.readFileSync is the irreducible I/O primitive)
 */

const fs = require('fs');
const path = require('path');

// Core modules
const { validateNoKernelReservedFields } = require('../core/security');
const muContainers = require('../core/container_factory');
const stage0Vm = require('../core/stage0_vm');
const {
  getSeedSubdir,
  loadVerifiedSeedImage,
  SEED_IMAGE_VERIFICATION_MODES,
  SEED_CHECKSUMS,
  EXPECTED_PROJECTION_IDS,
} = require('../core/seed_loader');

function validateCombinedBridgeOrdering(projections) {
  const ids = [];
  for (const proj of projections) {
    if (proj && typeof proj === 'object' && !Array.isArray(proj)) {
      ids.push(proj.id);
    } else {
      throw new Error(
        `SECURITY: Non-dict projection in bridge ordering validation: ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`
      );
    }
  }

  const requiredBridgeIds = [
    'bridge.var.check_existing', 'bridge.lookup.found_same',
    'bridge.lookup.found_different', 'bridge.lookup.not_found_yet',
    'bridge.lookup.not_found',
  ];

  const missing = requiredBridgeIds.filter(id => !ids.includes(id));
  if (missing.length > 0) {
    throw new Error('SECURITY: Bridge ordering invariant failed; missing bridge projections: ' + JSON.stringify(missing));
  }

  if (!ids.includes('match.var')) {
    throw new Error('SECURITY: Bridge ordering invariant failed; missing match.var');
  }

  const matchVarIdx = ids.indexOf('match.var');
  for (const bridgeId of requiredBridgeIds) {
    const bridgeIdx = ids.indexOf(bridgeId);
    if (bridgeIdx >= matchVarIdx) {
      throw new Error(`SECURITY: Bridge ordering invariant failed; ${bridgeId} (index ${bridgeIdx}) must be before match.var (index ${matchVarIdx})`);
    }
  }

  const foundSameIdx = ids.indexOf('bridge.lookup.found_same');
  const foundDiffIdx = ids.indexOf('bridge.lookup.found_different');
  if (foundSameIdx > foundDiffIdx) {
    throw new Error('SECURITY: Bridge ordering invariant failed; bridge.lookup.found_same must precede bridge.lookup.found_different');
  }
}

function loadVerifiedSeed(seedName) {
  const seedPath = path.join(muRoot, getSeedSubdir(seedName), seedName);
  const raw = fs.readFileSync(seedPath);
  return loadVerifiedSeedImage(seedName, raw, SEED_IMAGE_VERIFICATION_MODES.CLI);
}

// mu/ root is 3 levels up from cli/
const muRoot = path.join(__dirname, '..', '..', '..');

const kernel = loadVerifiedSeed('kernel.v1.json');
const matchSeed = loadVerifiedSeed('match.v2.json');
const substSeed = loadVerifiedSeed('subst.v2.json');
const recurrenceSeed = loadVerifiedSeed('recurrence.v1.json');
const recurrenceV2Seed = loadVerifiedSeed('recurrence.v2.json');
const exhaustionSeed = loadVerifiedSeed('exhaustion.v1.json');
const fixSeed = loadVerifiedSeed('fix.v1.json');
const bridgeSeed = loadVerifiedSeed('bootstrap_structural.v1.json');
const hemisphereSeed = loadVerifiedSeed('hemispheres.v1.json');
const engineSeed = loadVerifiedSeed('rcx_engine.v1.json');
const metabolizationSeed = loadVerifiedSeed('metabolization.v1.json');
const metabolizeCycleSeed = loadVerifiedSeed('metabolize_cycle.v1.json');

// S1-C: Load ALL compiled Stage0 bundles for VM execution path
const compiledDir = path.join(muRoot, 'stage0', 'compiled');
const { validateBundle, stage0VmStep, muDeepEqual } = stage0Vm; // CONTRABAND_OK: VM bundle loading for kernel step
const kernelBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'kernel_v1.compiled.v1.json'), 'utf8'));
const bridgeBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'bootstrap_structural_v1.compiled.v1.json'), 'utf8'));
const matchBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'match_v2.compiled.v1.json'), 'utf8'));
const substBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'subst_v2.compiled.v1.json'), 'utf8'));
validateBundle(kernelBundle);
validateBundle(bridgeBundle);
validateBundle(matchBundle);
validateBundle(substBundle);

// N15 provenance: verify bundle source_digest matches SEED_CHECKSUMS
function verifyBundleProvenance(bundle) {
  const sourceSeed = bundle.source_seed;
  const sourceDigest = bundle.source_digest;
  if (!sourceSeed || !sourceDigest) return; // Hand-authored bundles may lack these
  const seedName = sourceSeed.endsWith('.json') ? sourceSeed : sourceSeed + '.json';
  if (!(seedName in SEED_CHECKSUMS)) return; // Unknown seed — cannot verify
  const expected = 'sha256:' + SEED_CHECKSUMS[seedName];
  if (sourceDigest !== expected) {
    throw new Error(
      `SECURITY: Bundle provenance mismatch for '${seedName}'. ` +
      `Bundle claims source_digest=${sourceDigest}, ` +
      `but SEED_CHECKSUMS says ${expected}. ` +
      `Compiled bundle may be stale or tampered.`
    );
  }
}
verifyBundleProvenance(kernelBundle);
verifyBundleProvenance(bridgeBundle);
verifyBundleProvenance(matchBundle);
verifyBundleProvenance(substBundle);

// P7-d: Partitioned projections for VM path
const kernelV1Projections = kernel.projections;

// Compose projection arrays
const allProjections = muContainers.list([...kernel.projections, ...matchSeed.projections, ...substSeed.projections]);
const bridgeProjections = bridgeSeed.projections;
const recurrenceProjections = recurrenceSeed.projections;
const exhaustionProjections = exhaustionSeed.projections;
const fixProjections = fixSeed.projections;
const hemisphereProjections = hemisphereSeed.projections;
const engineProjections = engineSeed.projections;
const metabolizationProjections = metabolizationSeed.projections;
const metabolizeCycleProjections = metabolizeCycleSeed.projections;
const recurrenceV2Projections = recurrenceV2Seed.projections;

const seedProjectionMap = Object.assign(Object.create(null), {
  'recurrence.v1.json': recurrenceProjections,
  'recurrence.v2.json': recurrenceV2Projections,
  'exhaustion.v1.json': exhaustionProjections,
  'fix.v1.json': fixProjections,
  // Scheduler projections are verified and lazy-loaded by pipeline.js at the boundary.
  'rcx_engine_scheduler.v1.json': null,
});

const allProjectionsWithBridge = muContainers.list([
  ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
]);
validateCombinedBridgeOrdering(allProjectionsWithBridge);

const allProjectionsWithRecurrenceAndBridge = muContainers.list([
  ...recurrenceProjections, ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
]);
validateCombinedBridgeOrdering(allProjectionsWithRecurrenceAndBridge);

const allProjectionsWithExhaustion = muContainers.list([
  ...exhaustionProjections, ...recurrenceProjections, ...allProjections
]);

const allProjectionsWithExhaustionAndBridge = muContainers.list([
  ...exhaustionProjections, ...recurrenceProjections,
  ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
]);
validateCombinedBridgeOrdering(allProjectionsWithExhaustionAndBridge);

// Load parity vectors for tests and API
const parityVectorsPath = path.join(muRoot, '..', 'tests', 'fixtures', 'parity_vectors.json');
let parityVectors;
try {
  parityVectors = stage0Vm.muCopy(JSON.parse(fs.readFileSync(parityVectorsPath, 'utf8')), true, 'Parity vector parse tree');
} catch (e) {
  parityVectors = muContainers.record([
    ['vectors', muContainers.list()],
    ['security_vectors', muContainers.list()],
  ]);
}

// Seeds context — passed to self-tests and API handlers
const seedsContext = {
  allProjections, allProjectionsWithBridge, allProjectionsWithExhaustion,
  allProjectionsWithExhaustionAndBridge, allProjectionsWithRecurrenceAndBridge,
  recurrenceProjections, exhaustionProjections, hemisphereProjections,
  engineProjections, metabolizationProjections, metabolizeCycleProjections,
  seedProjectionMap,
  parityVectors,
  kernel, matchSeed, substSeed, bridgeSeed,
  recurrenceSeed, exhaustionSeed, hemisphereSeed, engineSeed, metabolizationSeed,
  recurrenceV2Seed, fixSeed, metabolizeCycleSeed,
  bridgeProjections, fixProjections, recurrenceV2Projections,
  SEED_CHECKSUMS, EXPECTED_PROJECTION_IDS,
  validateCombinedBridgeOrdering,
  // S1-C: ALL compiled VM bundles
  kernelBundle, bridgeBundle, matchBundle, substBundle,
  stage0VmStep, muDeepEqual,
};

// JSON API mode
if (process.argv.includes('--json-api')) {
  const apiArg = process.argv[process.argv.indexOf('--json-api') + 1];
  const { handleJsonApi } = require('../api/json_handlers');
  handleJsonApi(apiArg, seedsContext);
} else {
  // Run self-tests for the human CLI path only. JSON API parity calls need the
  // same loaded seed context without paying the diagnostic self-test suite.
  const runSelfTests = require('../tests/self_tests');
  runSelfTests(seedsContext);
}
