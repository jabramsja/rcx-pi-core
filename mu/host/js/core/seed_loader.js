'use strict';
/**
 * Side-effect-free seed loader for core modules.
 *
 * This loader does NOT import cli/main.js (which runs self-tests on import).
 * Core modules that need seed access use this instead.
 *
 * Path convention: seeds live at mu/<subdir>/<seedName>.
 * From __dirname (mu/host/js/core/), that is ../../../<subdir>/<seedName>.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { muCopy } = require('./stage0_vm');

// Fail-closed: checksum + projection ID registries for seeds loaded by core modules.
// Must mirror entries in cli/main.js and Python seed_integrity.py.
const CORE_SEED_CHECKSUMS = {
  'terminal_classify.v1.json': '413acebcdcda2de65a87530924b27eca597e9cf3ec5e4f153a6cd5b4e3bcf7d7',
  'hemispheres.v1.json': 'fb212be1d4bedcdf4b805ff4394d47bee8cb1b7eda19b449e16536a22c683de8',
  'rcx_engine.v1.json': '1e32fcb989d18015be45ee7dd6d7b85a9ecfa8509d44562f04b7029c23ec684f',
  'rcx_engine_state.v1.json': '7e4d05fcdca90e5c374ce45e094ad73b2a1bec9599254bd457db194c00fc29d0',
  'rcx_engine_scheduler.v1.json': '2e10c737f8d1a8b2fcd1a2a22b5f51e855c51372d691fce2a05e435744d78f65',
};

const CORE_SEED_PROJECTION_IDS = {
  'terminal_classify.v1.json': [
    'tc.recurrence',
    'tc.exhaustion',
    'tc.engine',
    'tc.exit.closure',
    'tc.exit.exhaustion',
    'tc.exit.stall',
    'tc.exit.completed',
  ],
  'hemispheres.v1.json': [
    'hemisphere.init',
    'hemisphere.classify.exhaustion',
    'hemisphere.classify.null',
    'hemisphere.classify.closure',
    'hemisphere.classify.stall',
    'hemisphere.classify.default',
    'hemisphere.add.r_null',
    'hemisphere.add.r_inf',
    'hemisphere.add.r_a',
    'hemisphere.add.lobes',
    'hemisphere.add.sink',
    'hemisphere.unwrap',
  ],
  'rcx_engine.v1.json': [
    'engine.init',
    'engine.init_config',
    'engine.trace_done',
    'engine.hash_done_fix',
    'engine.hash_done',
    'engine.fix_done_applied',
    'engine.fix_done_none',
    'engine.recurrence_done',
    'engine.exhaustion_done_freeze',
    'engine.exhaustion_done_terminal',
    'engine.unwrap',
  ],
  'rcx_engine_state.v1.json': [
    'engine_state.shape_valid',
    'engine_state.identity_stable',
    'engine_state.next_id_monotone',
    'engine_state.shape_invalid_missing_graph',
    'engine_state.shape_invalid_missing_omega',
    'engine_state.shape_invalid_missing_l_map',
    'engine_state.shape_invalid_missing_xi',
    'engine_state.shape_invalid_missing_rho',
    'engine_state.shape_invalid_missing_next_id',
  ],
  'rcx_engine_scheduler.v1.json': [
    'scheduler.invalid_missing_godel_unary_map',
    'scheduler.invalid_non_godel_head',
    'scheduler.invalid_godel_missing_code',
    'scheduler.invalid_godel_missing_domain',
    'scheduler.invalid_godel_missing_codomain',
    'scheduler.invalid_godel_missing_identity_map',
    'scheduler.reject_identity_map',
    'scheduler.reject_tail_identity_map',
    'scheduler.reject_third_identity_map',
    'scheduler.reject_unhandled_three_operator_pool',
    'scheduler.order_error_0010_before_0001',
    'scheduler.order_error_0100_before_0011',
    'scheduler.skip_frozen_head',
    'scheduler.skip_frozen_tail_member',
    'scheduler.skip_frozen_tail2_member',
    'scheduler.scan_frozen_tail',
    'scheduler.select_single_operator',
    'scheduler.select_0001_before_0010',
    'scheduler.select_0011_before_0100',
    'scheduler.reject_unhandled_two_operator_pool',
    'scheduler.pool_exhausted',
    'scheduler.reject_unhandled_operator_pool_shape',
  ],
};

// Seed dependencies — mirrors SEED_DEPENDENCIES in Python seed_integrity.py.
// Maps seed names to execution-time prerequisites (seeds whose projections must
// be present for the dependent seed's projections to produce correct output).
const SEED_DEPENDENCIES = {
  'kernel.v1.json': ['match.v2.json', 'subst.v2.json'],
  'match.v2.json': ['bootstrap_structural.v1.json'],
  'rcx_engine.v1.json': ['recurrence.v2.json', 'exhaustion.v1.json', 'fix.v1.json'],
  'hemispheres.v1.json': ['rcx_engine.v1.json'],
  'metabolize_cycle.v1.json': ['hemispheres.v1.json', 'metabolization.v1.json'],
};

/**
 * Validate that all execution-time dependencies are satisfied.
 * @param {Set<string>} loadedSeeds - Set of seed names that are loaded
 * @returns {string[]} Error messages (empty if all satisfied)
 */
function validateSeedDependencies(loadedSeeds) {
  const errors = [];
  for (const seedName of loadedSeeds) {
    const deps = SEED_DEPENDENCIES[seedName];
    if (!deps) continue;
    for (const dep of deps) {
      if (!loadedSeeds.has(dep)) {
        errors.push(`Seed ${seedName} requires ${dep} but it is not loaded`);
      }
    }
  }
  return errors;
}

// Map seed names to mu/ subfolders — mirrors MU_SEED_LOCATIONS in Python seed_integrity.py.
const SEED_SUBDIRS = {
  'kernel.v1.json': 'substrate',
  'match.v1.json': 'substrate',
  'match.v2.json': 'substrate',
  'subst.v1.json': 'substrate',
  'subst.v2.json': 'substrate',
  'bootstrap_structural.v1.json': 'bridge',
  'recurrence.v1.json': 'closures',
  'recurrence.v2.json': 'closures',
  'exhaustion.v1.json': 'closures',
  'fix.v1.json': 'closures',
  'classify.v1.json': 'utilities',
  'eval.v1.json': 'utilities',
  'terminal_classify.v1.json': 'utilities',
  'rcx_engine.v1.json': 'programs',
  'rcx_engine_state.v1.json': 'programs',
  'rcx_engine_scheduler.v1.json': 'programs',
  'hemispheres.v1.json': 'programs',
  'paxos_demo.v1.json': 'programs',
  'metabolization.v1.json': 'programs',
  'metabolize_cycle.v1.json': 'programs',
  'evidence_walker.v1.json': 'utilities',
};

/**
 * Get the subdirectory for a seed file.
 * @param {string} seedName - Seed filename
 * @returns {string} Subdirectory under mu/
 * @throws {Error} If seedName is not in SEED_SUBDIRS
 */
function getSeedSubdir(seedName) {
  const subdir = SEED_SUBDIRS[seedName];
  if (!subdir) {
    throw new Error(`Unknown seed: ${seedName} (not in SEED_SUBDIRS registry)`);
  }
  return subdir;
}

/**
 * Check if a seed is fully verification-locked (checksum + projection IDs).
 * INV_OPROMO_3 only accepts fully-locked seeds in JS.
 * @param {string} seedName - Seed filename
 * @returns {boolean}
 */
function isFullyLockedSeed(seedName) {
  return seedName in CORE_SEED_CHECKSUMS && seedName in CORE_SEED_PROJECTION_IDS;
}

/**
 * Verify, parse, and validate a seed JSON image without performing file I/O.
 * @param {string} seedName - Seed filename (e.g., 'terminal_classify.v1.json')
 * @param {Buffer|string} seedBytes - Raw seed JSON bytes
 * @param {object} checksumRegistry - Seed checksum registry
 * @param {object} projectionIdRegistry - Seed projection ID registry
 * @param {string} checksumRegistryName - Human-readable checksum registry name
 * @param {string} projectionIdRegistryName - Human-readable projection registry name
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeedImage(
  seedName,
  seedBytes,
  checksumRegistry,
  projectionIdRegistry,
  checksumRegistryName,
  projectionIdRegistryName
) {
  const imageBytes = Buffer.isBuffer(seedBytes) ? seedBytes : Buffer.from(seedBytes);

  // Compute hash of raw bytes before any parsing.
  const hash = crypto.createHash('sha256').update(imageBytes).digest('hex');

  // SECURITY: For known seeds, verify checksum BEFORE JSON.parse.
  // A tampered seed must never reach the parser — checksum is the first gate.
  // For unknown seeds (not in registry), we fall through to parse-then-reject
  // so that projection type guards can still fire for diagnostic clarity.
  const expected = checksumRegistry[seedName];
  if (expected) {
    // Known seed — verify checksum before parsing (fail-closed)
    if (hash !== expected) {
      throw new Error(`Seed checksum mismatch: ${seedName} (expected ${expected}, got ${hash})`);
    }
  }

  const raw = new TextDecoder('utf-8', { fatal: true }).decode(imageBytes);
  const seed = muCopy(JSON.parse(raw), true, 'Verified seed parse tree');

  if (seed === null || typeof seed !== 'object' || Array.isArray(seed)) {
    throw new Error(
      `Seed ${seedName} must be a plain object, ` +
      `got ${seed === null ? 'null' : Array.isArray(seed) ? 'array' : typeof seed}`
    );
  }
  if (!('meta' in seed)) {
    throw new Error(`Seed ${seedName} missing 'meta' key`);
  }
  if (!('projections' in seed)) {
    throw new Error(`Seed ${seedName} missing 'projections' key`);
  }

  const meta = seed.meta;
  const projections = seed.projections;
  if (meta === null || typeof meta !== 'object' || Array.isArray(meta)) {
    throw new Error(
      `Seed ${seedName} 'meta' must be a plain object, ` +
      `got ${meta === null ? 'null' : Array.isArray(meta) ? 'array' : typeof meta}`
    );
  }
  if (!Array.isArray(projections)) {
    throw new Error(
      `Seed ${seedName} 'projections' must be an array, got ${typeof projections}`
    );
  }

  for (const field of ['version', 'name', 'description']) {
    if (!(field in meta)) {
      throw new Error(`Seed ${seedName} meta missing key '${field}'`);
    }
  }

  for (let i = 0; i < projections.length; i++) {
    const p = projections[i];
    if (p === null || typeof p !== 'object' || Array.isArray(p)) {
      throw new Error(
        `Seed ${seedName}: projection[${i}] must be a plain object, ` +
        `got ${p === null ? 'null' : Array.isArray(p) ? 'array' : typeof p}`
      );
    }
    const proj = p;
    if (!('id' in proj)) {
      throw new Error(`Seed ${seedName} projection ${i} missing key 'id'`);
    }
    if (!('pattern' in proj)) {
      throw new Error(`Seed ${seedName} projection ${i} missing key 'pattern'`);
    }
    if (!('body' in proj)) {
      throw new Error(`Seed ${seedName} projection ${i} missing key 'body'`);
    }
  }

  // Fail-closed on unknown seeds (parity with Python seed_integrity.py)
  if (!expected) {
    throw new Error(
      `Unknown seed: ${seedName} (no checksum registered in ${checksumRegistryName})`
    );
  }

  // Projection ID verification (fail-closed: registry asymmetry = error)
  const expectedIds = projectionIdRegistry[seedName];
  if (!expectedIds) {
    throw new Error(
      `Seed ${seedName} has checksum but no projection IDs in ${projectionIdRegistryName} (registry asymmetry)`
    );
  }
  const actualIds = seed.projections.map(p => p.id);
  if (JSON.stringify(actualIds) !== JSON.stringify(expectedIds)) {
    throw new Error(
      `Seed projection IDs mismatch: ${seedName} ` +
      `(expected ${JSON.stringify(expectedIds)}, got ${JSON.stringify(actualIds)})`
    );
  }

  return seed;
}

/**
 * Load and verify a seed file.
 * @param {string} seedName - Seed filename (e.g., 'terminal_classify.v1.json')
 * @param {string} subdir - Subdirectory under mu/ (e.g., 'utilities')
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeed(seedName, subdir) {
  const seedPath = path.join(__dirname, '..', '..', '..', subdir, seedName);
  const raw = fs.readFileSync(seedPath);
  return loadVerifiedSeedImage(
    seedName,
    raw,
    CORE_SEED_CHECKSUMS,
    CORE_SEED_PROJECTION_IDS,
    'CORE_SEED_CHECKSUMS',
    'CORE_SEED_PROJECTION_IDS'
  );
}

function getSeedChecksum(seedName) {
  return CORE_SEED_CHECKSUMS[seedName] ?? null;
}

module.exports = { loadVerifiedSeed, loadVerifiedSeedImage, getSeedSubdir, isFullyLockedSeed, getSeedChecksum, validateSeedDependencies, SEED_SUBDIRS, SEED_DEPENDENCIES };
