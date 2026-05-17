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

const SEED_REGISTRY_MANIFEST_NAME = 'seed_registry_manifest.v1.json';
const SEED_REGISTRY_MANIFEST_SCHEMA = 'rcx.seed_registry_manifest.v1';
const SEED_REGISTRY_MANIFEST_SHA256 =
  '175ba95a371914f3d38bbe960ccd9300b44ea907d020164deb25947292bb7d29';

const manifestPath = path.join(__dirname, '..', '..', '..', SEED_REGISTRY_MANIFEST_NAME);
const manifestBytes = fs.readFileSync(manifestPath);
const manifestActualSha256 = crypto.createHash('sha256').update(manifestBytes).digest('hex');
if (manifestActualSha256 !== SEED_REGISTRY_MANIFEST_SHA256) {
  throw new Error(
    `Seed registry manifest checksum mismatch: ${SEED_REGISTRY_MANIFEST_NAME} ` +
    `(expected ${SEED_REGISTRY_MANIFEST_SHA256}, got ${manifestActualSha256})`
  );
}

const manifestRaw = new TextDecoder('utf-8', { fatal: true }).decode(manifestBytes);
const SEED_REGISTRY_MANIFEST = muCopy(
  JSON.parse(manifestRaw),
  true,
  'Seed registry manifest parse tree'
);
if (
  SEED_REGISTRY_MANIFEST === null ||
  typeof SEED_REGISTRY_MANIFEST !== 'object' ||
  Array.isArray(SEED_REGISTRY_MANIFEST)
) {
  throw new Error('Seed registry manifest must be a plain object');
}
if (SEED_REGISTRY_MANIFEST.schema !== SEED_REGISTRY_MANIFEST_SCHEMA) {
  throw new Error(`Seed registry manifest schema mismatch: ${SEED_REGISTRY_MANIFEST.schema}`);
}
const manifestSeeds = SEED_REGISTRY_MANIFEST.seeds;
if (
  manifestSeeds === null ||
  typeof manifestSeeds !== 'object' ||
  Array.isArray(manifestSeeds) ||
  Object.keys(manifestSeeds).length === 0
) {
  throw new Error('Seed registry manifest must contain non-empty seeds object');
}

const validManifestSubdirs = new Set(['substrate', 'closures', 'bridge', 'programs', 'utilities']);
const validManifestStatuses = new Set(['production', 'legacy-poc']);
const requiredManifestKeys = [
  'subdir',
  'sha256',
  'projection_ids',
  'status',
  'dependencies',
  'js_cli_registered',
  'js_core_locked',
];
for (const [seedName, record] of Object.entries(manifestSeeds)) {
  if (typeof seedName !== 'string' || !seedName.endsWith('.json')) {
    throw new Error(`Seed registry manifest has invalid seed name: ${seedName}`);
  }
  if (record === null || typeof record !== 'object' || Array.isArray(record)) {
    throw new Error(`Seed registry manifest record for ${seedName} must be a plain object`);
  }
  for (const key of requiredManifestKeys) {
    if (!(key in record)) {
      throw new Error(`Seed registry manifest record for ${seedName} missing key '${key}'`);
    }
  }
  if (!validManifestSubdirs.has(record.subdir)) {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid subdir`);
  }
  if (typeof record.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(record.sha256)) {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid sha256`);
  }
  let projectionIdsValid = Array.isArray(record.projection_ids);
  if (projectionIdsValid) {
    for (const projectionId of record.projection_ids) {
      if (typeof projectionId !== 'string') {
        projectionIdsValid = false;
        break;
      }
    }
  }
  if (!projectionIdsValid) {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid projection_ids`);
  }
  if (!validManifestStatuses.has(record.status)) {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid status`);
  }
  let dependenciesValid = Array.isArray(record.dependencies);
  if (dependenciesValid) {
    for (const dep of record.dependencies) {
      if (typeof dep !== 'string') {
        dependenciesValid = false;
        break;
      }
    }
  }
  if (!dependenciesValid) {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid dependencies`);
  }
  if (typeof record.js_cli_registered !== 'boolean' || typeof record.js_core_locked !== 'boolean') {
    throw new Error(`Seed registry manifest record for ${seedName} has invalid JS flags`);
  }
}

const registeredManifestSeeds = new Set(Object.keys(manifestSeeds));
for (const [seedName, record] of Object.entries(manifestSeeds)) {
  for (const dep of record.dependencies) {
    if (!registeredManifestSeeds.has(dep)) {
      throw new Error(`Seed registry manifest record for ${seedName} depends on unknown seed ${dep}`);
    }
  }
}

const SEED_REGISTRY_RECORDS = SEED_REGISTRY_MANIFEST.seeds;
const SEED_CHECKSUMS = Object.create(null);
const EXPECTED_PROJECTION_IDS = Object.create(null);
const CORE_SEED_CHECKSUMS = Object.create(null);
const CORE_SEED_PROJECTION_IDS = Object.create(null);
for (const [seedName, record] of Object.entries(SEED_REGISTRY_RECORDS)) {
  if (record.js_cli_registered) {
    SEED_CHECKSUMS[seedName] = record.sha256;
    EXPECTED_PROJECTION_IDS[seedName] = record.projection_ids.slice();
  }
  if (record.js_core_locked) {
    CORE_SEED_CHECKSUMS[seedName] = record.sha256;
    CORE_SEED_PROJECTION_IDS[seedName] = record.projection_ids.slice();
  }
}

const SEED_DEPENDENCIES = Object.create(null);
for (const [seedName, record] of Object.entries(SEED_REGISTRY_RECORDS)) {
  if (record.dependencies.length > 0) {
    SEED_DEPENDENCIES[seedName] = record.dependencies.slice();
  }
}

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

const SEED_SUBDIRS = Object.create(null);
for (const [seedName, record] of Object.entries(SEED_REGISTRY_RECORDS)) {
  SEED_SUBDIRS[seedName] = record.subdir;
}

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
 * @param {string} subdir - Caller-visible subdir, checked against manifest data
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeed(seedName, subdir) {
  const manifestSubdir = getSeedSubdir(seedName);
  if (subdir !== manifestSubdir) {
    throw new Error(
      `Seed ${seedName} subdir mismatch: manifest has ${manifestSubdir}, caller supplied ${subdir}`
    );
  }
  const seedPath = path.join(__dirname, '..', '..', '..', manifestSubdir, seedName);
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

module.exports = {
  loadVerifiedSeed,
  loadVerifiedSeedImage,
  getSeedSubdir,
  isFullyLockedSeed,
  getSeedChecksum,
  validateSeedDependencies,
  SEED_REGISTRY_MANIFEST,
  SEED_CHECKSUMS,
  EXPECTED_PROJECTION_IDS,
  CORE_SEED_CHECKSUMS,
  CORE_SEED_PROJECTION_IDS,
  SEED_SUBDIRS,
  SEED_DEPENDENCIES,
};
