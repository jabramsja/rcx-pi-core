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
};

/**
 * Load and verify a seed file.
 * @param {string} seedName - Seed filename (e.g., 'terminal_classify.v1.json')
 * @param {string} subdir - Subdirectory under mu/ (e.g., 'utilities')
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeed(seedName, subdir) {
  const seedPath = path.join(__dirname, '..', '..', '..', subdir, seedName);
  const raw = fs.readFileSync(seedPath, 'utf8');

  // Checksum verification (fail-closed)
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const expected = CORE_SEED_CHECKSUMS[seedName];
  if (expected && hash !== expected) {
    throw new Error(`Seed checksum mismatch: ${seedName} (expected ${expected}, got ${hash})`);
  }

  const seed = JSON.parse(raw);

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

module.exports = { loadVerifiedSeed };
