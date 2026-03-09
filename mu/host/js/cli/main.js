'use strict';
/**
 * RCX CLI Main — Seed loading, projection composition, self-tests, CLI output
 *
 * This is the runtime entrypoint. When executed directly or via eval_step.js shim:
 *   1. Loads and verifies all 13 seeds
 *   2. Composes projection arrays
 *   3. Runs self-tests (console output with "All tests passed: true")
 *   4. If --json-api in process.argv, delegates to api/json_handlers.js
 *
 * BOOTSTRAP_PRIMITIVE: projection_loader
 * (fs.readFileSync is the irreducible I/O primitive)
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Core modules
const { validateNoKernelReservedFields } = require('../core/security');

// Seed integrity verification — parity with Python's seed_integrity.py
const SEED_CHECKSUMS = {
  'kernel.v1.json': '8a4471648c8d77d4d5beedf3491c04b8154e282bbfbf52a958f8c5bcc5d94c4f',
  'match.v2.json': 'cd89ce2bef9668b2e0bb190ad8a615a53bd699d4a0ad3ff9d6c1429db5e3594d',
  'subst.v2.json': '0b735c52da437a6eae1478dc4c992269bff8978c7e9084d15ffcba6c06e3037f',
  'recurrence.v1.json': 'ad9944b340e22df187fe567875d2c75483d4201b1b5c0147e1e8ec63e0bbacd0',
  'recurrence.v2.json': 'f8bc7fc7f43f5423b0ecf0e78fd4b2d99699456ecff1e113d4c8e7167b213fa9',
  'exhaustion.v1.json': '8489398b8264dd547b231f67c98543bba1d6d45a24bb5504039395a24eb068d3',
  'bootstrap_structural.v1.json': 'dfaa1ea9de000e344fee1e61be9666e2876091fa64aff524857265929a261964',
  'hemispheres.v1.json': 'fb212be1d4bedcdf4b805ff4394d47bee8cb1b7eda19b449e16536a22c683de8',
  'rcx_engine.v1.json': '1e32fcb989d18015be45ee7dd6d7b85a9ecfa8509d44562f04b7029c23ec684f',
  'fix.v1.json': 'd961abcf1b9ba39c2eebcf049ae3351b51082a09c41deb0d71efef9eedadca34',
  'metabolization.v1.json': 'a1f60ff55dc3e9f7c0c12e247a337d5d942cbfb74beffd001336d3a77de9a1e7',
  'terminal_classify.v1.json': '413acebcdcda2de65a87530924b27eca597e9cf3ec5e4f153a6cd5b4e3bcf7d7',
  'metabolize_cycle.v1.json': 'f8888ecab6845193610499d15dea8a8e845d07ce04391457770ef32cac69dfd8',
};

// Expected projection IDs in security-critical order (first-match-wins)
const EXPECTED_PROJECTION_IDS = {
  'kernel.v1.json': [
    'kernel.wrap', 'kernel.stall', 'kernel.try', 'kernel.match_success',
    'kernel.match_fail', 'kernel.subst_success', 'kernel.unwrap',
  ],
  'match.v2.json': [
    'match.done', 'match.sibling', 'match.equal', 'match.var',
    'match.typed.descend', 'match.dict.descend', 'match.fail', 'match.wrap',
  ],
  'subst.v2.json': [
    'subst.done', 'subst.ascend', 'subst.sibling', 'subst.var',
    'subst.lookup.found', 'subst.lookup.next', 'subst.typed.descend',
    'subst.typed.sibling', 'subst.typed.ascend', 'subst.descend',
    'subst.primitive', 'subst.wrap',
  ],
  'recurrence.v1.json': [
    'recurrence.init', 'recurrence.end_of_trace', 'recurrence.check_state_stall',
    'recurrence.check_state_maxsteps', 'recurrence.check_state',
    'recurrence.found_in_seen', 'recurrence.not_in_head', 'recurrence.not_found',
    'recurrence.unwrap',
  ],
  'recurrence.v2.json': [
    'recurrence.init', 'recurrence.end_of_trace', 'recurrence.check_state_stall',
    'recurrence.check_state_maxsteps', 'recurrence.check_state',
    'recurrence.hash_match', 'recurrence.hash_no_match', 'recurrence.not_found',
    'recurrence.unwrap',
  ],
  'exhaustion.v1.json': [
    'exhaustion.init_null', 'exhaustion.init', 'exhaustion.find_match',
    'exhaustion.find_continue', 'exhaustion.find_not_found', 'exhaustion.scan_same',
    'exhaustion.scan_skip_sentinel_maxsteps', 'exhaustion.scan_skip_sentinel_stall',
    'exhaustion.scan_different', 'exhaustion.scan_end', 'exhaustion.frozen_found',
    'exhaustion.frozen_check_tail', 'exhaustion.do_freeze',
  ],
  'bootstrap_structural.v1.json': [
    'bridge.var.check_existing', 'bridge.lookup.found_same',
    'bridge.lookup.found_different', 'bridge.lookup.not_found_yet',
    'bridge.lookup.not_found',
  ],
  'hemispheres.v1.json': [
    'hemisphere.init', 'hemisphere.classify.exhaustion', 'hemisphere.classify.null',
    'hemisphere.classify.closure', 'hemisphere.classify.stall',
    'hemisphere.classify.default', 'hemisphere.add.r_null', 'hemisphere.add.r_inf',
    'hemisphere.add.r_a', 'hemisphere.add.lobes', 'hemisphere.add.sink',
    'hemisphere.unwrap',
  ],
  'rcx_engine.v1.json': [
    'engine.init', 'engine.init_config', 'engine.trace_done',
    'engine.hash_done_fix', 'engine.hash_done',
    'engine.fix_done_applied', 'engine.fix_done_none',
    'engine.recurrence_done', 'engine.exhaustion_done_freeze',
    'engine.exhaustion_done_terminal', 'engine.unwrap',
  ],
  'fix.v1.json': [
    'fix.init', 'fix.edge_add_guard', 'fix.edge_add', 'fix.vertex_add_guard', 'fix.vertex_add', 'fix.pass_through',
  ],
  'metabolization.v1.json': [
    'hemisphere.metabolize.sink_to_r_null', 'hemisphere.metabolize.sink_to_r_inf',
    'hemisphere.recover.stall_to_lobes', 'hemisphere.recover.stall_to_sink',
    'hemisphere.promote.lobes_to_r_a', 'hemisphere.recycle.residual_to_sink',
  ],
  'terminal_classify.v1.json': [
    'tc.recurrence', 'tc.exhaustion', 'tc.engine',
    'tc.exit.closure', 'tc.exit.exhaustion', 'tc.exit.stall', 'tc.exit.completed',
  ],
  'metabolize_cycle.v1.json': [
    'metabolize.cycle.init', 'metabolize.cycle.init_skip_sink',
    'metabolize.cycle.sink_to_r_null', 'metabolize.cycle.sink_to_r_inf',
    'metabolize.cycle.sink_next', 'metabolize.cycle.sink_done',
    'metabolize.cycle.lobes_start', 'metabolize.cycle.lobes_start_empty',
    'metabolize.cycle.lobes_promote', 'metabolize.cycle.lobes_keep',
    'metabolize.cycle.lobes_next', 'metabolize.cycle.lobes_done',
    'metabolize.cycle.lobes_reverse_step', 'metabolize.cycle.lobes_reverse_done',
    'metabolize.cycle.unwrap',
  ],
};

function verifySeedChecksum(seedName, rawContent) {
  const expected = SEED_CHECKSUMS[seedName];
  if (!expected) return;
  const actual = crypto.createHash('sha256').update(rawContent).digest('hex');
  if (actual !== expected) {
    throw new Error(`Seed ${seedName} checksum mismatch: expected ${expected}, got ${actual}`);
  }
}

function validateSeedStructure(seedName, seed) {
  if (!('meta' in seed) || seed.meta === null || typeof seed.meta !== 'object') {
    throw new Error(`Seed ${seedName}: missing or invalid 'meta' field`);
  }
  if (!('projections' in seed) || !Array.isArray(seed.projections)) {
    throw new Error(`Seed ${seedName}: missing or invalid 'projections' field`);
  }
  for (let i = 0; i < seed.projections.length; i++) {
    const proj = seed.projections[i];
    if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) {
      throw new Error(`Seed ${seedName}: projection[${i}] must be a plain object, got ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`);
    }
    if (!('id' in proj) || !('pattern' in proj) || !('body' in proj)) {
      throw new Error(`Seed ${seedName}: projection ${i} missing required field (id/pattern/body)`);
    }
  }
}

function validateProjectionIds(seedName, seed) {
  const expected = EXPECTED_PROJECTION_IDS[seedName];
  if (!expected) return;
  const actualIds = seed.projections.map(p => p.id);
  if (actualIds.length !== expected.length) {
    throw new Error(`Seed ${seedName}: expected ${expected.length} projections, got ${actualIds.length}`);
  }
  for (let i = 0; i < expected.length; i++) {
    if (actualIds[i] !== expected[i]) {
      throw new Error(`Seed ${seedName}: projection order mismatch at index ${i}: expected '${expected[i]}', got '${actualIds[i]}'`);
    }
  }
}

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

function loadVerifiedSeed(seedPath, seedName) {
  const raw = fs.readFileSync(seedPath, 'utf8');
  verifySeedChecksum(seedName, raw);
  const seed = JSON.parse(raw);
  validateSeedStructure(seedName, seed);
  validateProjectionIds(seedName, seed);
  return seed;
}

// mu/ root is 3 levels up from cli/
const muRoot = path.join(__dirname, '..', '..', '..');
const substrateDir = path.join(muRoot, 'substrate');
const closuresDir = path.join(muRoot, 'closures');
const bridgeDir = path.join(muRoot, 'bridge');
const programsDir = path.join(muRoot, 'programs');

const kernel = loadVerifiedSeed(path.join(substrateDir, 'kernel.v1.json'), 'kernel.v1.json');
const matchSeed = loadVerifiedSeed(path.join(substrateDir, 'match.v2.json'), 'match.v2.json');
const substSeed = loadVerifiedSeed(path.join(substrateDir, 'subst.v2.json'), 'subst.v2.json');
const recurrenceSeed = loadVerifiedSeed(path.join(closuresDir, 'recurrence.v1.json'), 'recurrence.v1.json');
const recurrenceV2Seed = loadVerifiedSeed(path.join(closuresDir, 'recurrence.v2.json'), 'recurrence.v2.json');
const exhaustionSeed = loadVerifiedSeed(path.join(closuresDir, 'exhaustion.v1.json'), 'exhaustion.v1.json');
const fixSeed = loadVerifiedSeed(path.join(closuresDir, 'fix.v1.json'), 'fix.v1.json');
const bridgeSeed = loadVerifiedSeed(path.join(bridgeDir, 'bootstrap_structural.v1.json'), 'bootstrap_structural.v1.json');
const hemisphereSeed = loadVerifiedSeed(path.join(programsDir, 'hemispheres.v1.json'), 'hemispheres.v1.json');
const engineSeed = loadVerifiedSeed(path.join(programsDir, 'rcx_engine.v1.json'), 'rcx_engine.v1.json');
const metabolizationSeed = loadVerifiedSeed(path.join(programsDir, 'metabolization.v1.json'), 'metabolization.v1.json');
const metabolizeCycleSeed = loadVerifiedSeed(path.join(programsDir, 'metabolize_cycle.v1.json'), 'metabolize_cycle.v1.json');

// Compose projection arrays
const allProjections = [...kernel.projections, ...matchSeed.projections, ...substSeed.projections];
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
});

const allProjectionsWithBridge = [
  ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithBridge);

const allProjectionsWithRecurrenceAndBridge = [
  ...recurrenceProjections, ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithRecurrenceAndBridge);

const allProjectionsWithExhaustion = [
  ...exhaustionProjections, ...recurrenceProjections, ...allProjections
];

const allProjectionsWithExhaustionAndBridge = [
  ...exhaustionProjections, ...recurrenceProjections,
  ...kernel.projections, ...bridgeProjections,
  ...matchSeed.projections, ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithExhaustionAndBridge);

// Load parity vectors for tests and API
const parityVectorsPath = path.join(muRoot, '..', 'tests', 'fixtures', 'parity_vectors.json');
let parityVectors;
try {
  parityVectors = JSON.parse(fs.readFileSync(parityVectorsPath, 'utf8'));
} catch (e) {
  parityVectors = { vectors: [], security_vectors: [] };
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
};

// Run self-tests
const runSelfTests = require('../tests/self_tests');
runSelfTests(seedsContext);

// JSON API mode
if (process.argv.includes('--json-api')) {
  const apiArg = process.argv[process.argv.indexOf('--json-api') + 1];
  const { handleJsonApi } = require('../api/json_handlers');
  handleJsonApi(apiArg, seedsContext);
}
