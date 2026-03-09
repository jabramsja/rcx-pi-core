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

// Fail-closed: checksum + projection ID registries for seeds loaded by core modules.
// Must mirror entries in cli/main.js and Python seed_integrity.py.
const CORE_SEED_CHECKSUMS = {
  'terminal_classify.v1.json': '413acebcdcda2de65a87530924b27eca597e9cf3ec5e4f153a6cd5b4e3bcf7d7',
  'hemispheres.v1.json': 'fb212be1d4bedcdf4b805ff4394d47bee8cb1b7eda19b449e16536a22c683de8',
  'rcx_engine.v1.json': '1e32fcb989d18015be45ee7dd6d7b85a9ecfa8509d44562f04b7029c23ec684f',
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
};

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
 * Load and verify a seed file.
 * @param {string} seedName - Seed filename (e.g., 'terminal_classify.v1.json')
 * @param {string} subdir - Subdirectory under mu/ (e.g., 'utilities')
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeed(seedName, subdir) {
  const seedPath = path.join(__dirname, '..', '..', '..', subdir, seedName);
  const raw = fs.readFileSync(seedPath, 'utf8');

  // Compute hash early (needed for checksum compare below)
  const hash = crypto.createHash('sha256').update(raw).digest('hex');

  const seed = JSON.parse(raw);

  // Projection entry type guard (fail-closed — reject null/array/scalar before .id access)
  // ORDER MATTERS: must precede unknown-seed check so malformed-projection tests
  // using temp seed names still hit the type guard first.
  if (Array.isArray(seed.projections)) {
    for (let i = 0; i < seed.projections.length; i++) {
      const p = seed.projections[i];
      if (p === null || typeof p !== 'object' || Array.isArray(p)) {
        throw new Error(
          `Seed ${seedName}: projection[${i}] must be a plain object, ` +
          `got ${p === null ? 'null' : Array.isArray(p) ? 'array' : typeof p}`
        );
      }
    }
  }

  // F-46 FIX: Fail-closed on unknown seeds (parity with Python seed_integrity.py:329-330)
  const expected = CORE_SEED_CHECKSUMS[seedName];
  if (!expected) {
    throw new Error(
      `Unknown seed: ${seedName} (no checksum registered in CORE_SEED_CHECKSUMS)`
    );
  }

  // Checksum verification (fail-closed)
  if (hash !== expected) {
    throw new Error(`Seed checksum mismatch: ${seedName} (expected ${expected}, got ${hash})`);
  }

  // Projection ID verification (fail-closed)
  const expectedIds = CORE_SEED_PROJECTION_IDS[seedName];
  if (expectedIds) {
    const actualIds = seed.projections.map(p => p.id);
    if (JSON.stringify(actualIds) !== JSON.stringify(expectedIds)) {
      throw new Error(
        `Seed projection IDs mismatch: ${seedName} ` +
        `(expected ${JSON.stringify(expectedIds)}, got ${JSON.stringify(actualIds)})`
      );
    }
  }

  return seed;
}

function getSeedChecksum(seedName) {
  return CORE_SEED_CHECKSUMS[seedName] ?? null;
}

module.exports = { loadVerifiedSeed, getSeedSubdir, isFullyLockedSeed, getSeedChecksum, SEED_SUBDIRS };
