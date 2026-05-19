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
  '74dea09a1022ecaba89e8834b9a8bff3f9498f05b6fb4d79b0e5d0ad8707597f';

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
const EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS = Object.freeze([
  'exhaustion.v1.json',
  'fix.v1.json',
  'rcx_engine_scheduler.v1.json',
  'recurrence.v1.json',
  'recurrence.v2.json',
]);
const RUN_ALGORITHM_AUTHORITY_SEEDS = Object.create(null);
for (const [seedName, record] of Object.entries(SEED_REGISTRY_RECORDS)) {
  if (!Object.prototype.hasOwnProperty.call(record, 'authority')) {
    continue;
  }
  const authority = record.authority;
  if (authority === null || typeof authority !== 'object' || Array.isArray(authority)) {
    throw new Error(`Seed registry manifest record for ${seedName} authority must be a plain object`);
  }
  if (!Object.prototype.hasOwnProperty.call(authority, 'run_algorithm')) {
    throw new Error(`Seed registry manifest record for ${seedName} authority missing 'run_algorithm'`);
  }
  if (typeof authority.run_algorithm !== 'boolean') {
    throw new Error(
      `Seed registry manifest record for ${seedName} authority.run_algorithm must be boolean`
    );
  }
  if (authority.run_algorithm) {
    RUN_ALGORITHM_AUTHORITY_SEEDS[seedName] = true;
  }
}
Object.freeze(RUN_ALGORITHM_AUTHORITY_SEEDS);
const runAlgorithmAuthoritySeedNames = Object.keys(RUN_ALGORITHM_AUTHORITY_SEEDS).sort();
if (JSON.stringify(runAlgorithmAuthoritySeedNames) !== JSON.stringify(EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS)) {
  throw new Error(
    'Seed registry manifest authority.run_algorithm set mismatch: ' +
    `expected ${JSON.stringify(EXPECTED_RUN_ALGORITHM_AUTHORITY_SEEDS)}, ` +
    `got ${JSON.stringify(runAlgorithmAuthoritySeedNames)}`
  );
}
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

for (const registry of [EXPECTED_PROJECTION_IDS, CORE_SEED_PROJECTION_IDS, SEED_DEPENDENCIES]) {
  for (const value of Object.values(registry)) {
    Object.freeze(value);
  }
}
Object.freeze(SEED_CHECKSUMS);
Object.freeze(EXPECTED_PROJECTION_IDS);
Object.freeze(CORE_SEED_CHECKSUMS);
Object.freeze(CORE_SEED_PROJECTION_IDS);
Object.freeze(SEED_DEPENDENCIES);
Object.freeze(SEED_SUBDIRS);

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

const SEED_IMAGE_VERIFICATION_MODES = Object.freeze({
  CORE: 'manifest-core',
  CLI: 'manifest-cli',
});

const SEED_IMAGE_VERIFICATION_VIEWS = Object.freeze({
  [SEED_IMAGE_VERIFICATION_MODES.CORE]: Object.freeze({
    checksumRegistry: CORE_SEED_CHECKSUMS,
    projectionIdRegistry: CORE_SEED_PROJECTION_IDS,
    checksumRegistryName: 'CORE_SEED_CHECKSUMS',
    projectionIdRegistryName: 'CORE_SEED_PROJECTION_IDS',
  }),
  [SEED_IMAGE_VERIFICATION_MODES.CLI]: Object.freeze({
    checksumRegistry: SEED_CHECKSUMS,
    projectionIdRegistry: EXPECTED_PROJECTION_IDS,
    checksumRegistryName: 'SEED_CHECKSUMS',
    projectionIdRegistryName: 'EXPECTED_PROJECTION_IDS',
  }),
});

const MU_BINARY_TAGS = Object.freeze({
  NULL: 0x00,
  TRUE: 0x01,
  FALSE: 0x02,
  INT64: 0x03,
  FLOAT64: 0x04,
  STRING: 0x05,
  LIST: 0x06,
  DICT: 0x07,
});

const SEED_BINARY_MIGRATION_POLICY_ID = 'rcx.seed_binary_migration.v1.integer_projection_sidecar';
const SEED_BINARY_CHECKSUM_POLICY_ID = 'sha256:json+mu-binary-projections.v1';
const SEED_BINARY_PROJECTION_KEY_ORDER = Object.freeze(['id', 'pattern', 'body']);

class MuBinaryDecodeError extends Error {
  constructor(message) {
    super(message);
    this.name = 'MuBinaryDecodeError';
  }
}

const MU_BINARY_CODEC = Object.freeze({
  toBuffer(binaryBytes) {
    if (Buffer.isBuffer(binaryBytes)) {
      return binaryBytes;
    }
    if (binaryBytes instanceof ArrayBuffer) {
      return Buffer.from(binaryBytes);
    }
    if (ArrayBuffer.isView(binaryBytes)) {
      return Buffer.from(
        binaryBytes.buffer,
        binaryBytes.byteOffset,
        binaryBytes.byteLength
      );
    }
    if (Array.isArray(binaryBytes)) {
      for (let i = 0; i < binaryBytes.length; i++) {
        const byte = binaryBytes[i];
        if (!Number.isInteger(byte) || byte < 0 || byte > 255) {
          throw new TypeError(
            `MuBinary byte array entry at index ${i} must be an integer in 0..255`
          );
        }
      }
      return Buffer.from(binaryBytes);
    }
    throw new TypeError(
      `MuBinary input must be bytes, got ${binaryBytes === null ? 'null' : typeof binaryBytes}`
    );
  },

  requireAvailable(data, offset, length, label, tagOffset) {
    if (offset + length <= data.length) {
      return;
    }
    const have = Math.max(data.length - offset, 0);
    throw new MuBinaryDecodeError(
      `Truncated ${label} at offset ${tagOffset} (need ${length} bytes, have ${have})`
    );
  },

  readUInt32(data, offset, label, tagOffset) {
    this.requireAvailable(data, offset, 4, label, tagOffset);
    return data.readUInt32BE(offset);
  },

  decodeAt(data, offset) {
    if (offset >= data.length) {
      throw new MuBinaryDecodeError(
        `Unexpected end of data at offset ${offset} (data length ${data.length})`
      );
    }

    const tagOffset = offset;
    const tag = data[offset];
    offset += 1;

    if (tag === MU_BINARY_TAGS.NULL) {
      return [null, offset, false];
    }
    if (tag === MU_BINARY_TAGS.TRUE) {
      return [true, offset, false];
    }
    if (tag === MU_BINARY_TAGS.FALSE) {
      return [false, offset, false];
    }
    if (tag === MU_BINARY_TAGS.INT64) {
      this.requireAvailable(data, offset, 8, 'int64', tagOffset);
      const value = data.readBigInt64BE(offset);
      const numberValue = Number(value);
      if (!Number.isFinite(numberValue) || BigInt(numberValue) !== value) {
        throw new MuBinaryDecodeError(
          `int64 at offset ${tagOffset} cannot be represented exactly as a JavaScript Number`
        );
      }
      return [numberValue, offset + 8, false];
    }
    if (tag === MU_BINARY_TAGS.FLOAT64) {
      this.requireAvailable(data, offset, 8, 'float64', tagOffset);
      return [data.readDoubleBE(offset), offset + 8, true];
    }
    if (tag === MU_BINARY_TAGS.STRING) {
      const length = this.readUInt32(data, offset, 'string length', tagOffset);
      offset += 4;
      this.requireAvailable(data, offset, length, 'string data', tagOffset);
      let value;
      try {
        value = new TextDecoder('utf-8', { fatal: true }).decode(
          data.subarray(offset, offset + length)
        );
      } catch (error) {
        throw new MuBinaryDecodeError(
          `Malformed UTF-8 string at offset ${tagOffset}: ${error.message}`
        );
      }
      return [value, offset + length, false];
    }
    if (tag === MU_BINARY_TAGS.LIST) {
      const count = this.readUInt32(data, offset, 'list count', tagOffset);
      offset += 4;
      const items = [];
      let sawFloat64 = false;
      for (let i = 0; i < count; i++) {
        const decoded = this.decodeAt(data, offset);
        items.push(decoded[0]);
        offset = decoded[1];
        sawFloat64 = sawFloat64 || decoded[2];
      }
      return [items, offset, sawFloat64];
    }
    if (tag === MU_BINARY_TAGS.DICT) {
      const count = this.readUInt32(data, offset, 'dict count', tagOffset);
      offset += 4;
      const result = Object.create(null);
      let sawFloat64 = false;
      for (let i = 0; i < count; i++) {
        const keyDecoded = this.decodeAt(data, offset);
        const key = keyDecoded[0];
        offset = keyDecoded[1];
        if (typeof key !== 'string') {
          throw new MuBinaryDecodeError(
            `Dict key must decode to string, got ${typeof key} at offset ${offset}`
          );
        }
        if (Object.prototype.hasOwnProperty.call(result, key)) {
          throw new MuBinaryDecodeError(`Duplicate dict key '${key}' at offset ${tagOffset}`);
        }
        const valueDecoded = this.decodeAt(data, offset);
        result[key] = valueDecoded[0];
        offset = valueDecoded[1];
        sawFloat64 = sawFloat64 || keyDecoded[2] || valueDecoded[2];
      }
      return [result, offset, sawFloat64];
    }
    throw new MuBinaryDecodeError(
      `Unknown tag 0x${tag.toString(16).padStart(2, '0')} at offset ${tagOffset}`
    );
  },

  decodeValue(binaryBytes) {
    const data = this.toBuffer(binaryBytes);
    const decoded = this.decodeAt(data, 0);
    if (decoded[1] !== data.length) {
      throw new MuBinaryDecodeError(
        `Trailing data: decoded ${decoded[1]} bytes but data is ${data.length} bytes`
      );
    }
    return decoded[0];
  },

  decodeValueWithMetadata(binaryBytes) {
    const data = this.toBuffer(binaryBytes);
    const decoded = this.decodeAt(data, 0);
    if (decoded[1] !== data.length) {
      throw new MuBinaryDecodeError(
        `Trailing data: decoded ${decoded[1]} bytes but data is ${data.length} bytes`
      );
    }
    return {
      value: decoded[0],
      sawFloat64: decoded[2],
    };
  },

  rejectNonIntegerSeedNumerics(value, pathLabel) {
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) {
        throw new MuBinaryDecodeError(
          `Seed binary projection contains non-finite numeric value at ${pathLabel}`
        );
      }
      if (!Number.isInteger(value)) {
        throw new MuBinaryDecodeError(
          `Seed binary projection contains non-integer numeric value ${value} at ${pathLabel}`
        );
      }
      return;
    }
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        this.rejectNonIntegerSeedNumerics(value[i], `${pathLabel}[${i}]`);
      }
      return;
    }
    if (value !== null && typeof value === 'object') {
      for (const [key, nested] of Object.entries(value)) {
        this.rejectNonIntegerSeedNumerics(nested, `${pathLabel}.${key}`);
      }
    }
  },

  decodeSeedProjections(binaryBytes) {
    const decoded = this.decodeValueWithMetadata(binaryBytes);
    const projections = decoded.value;
    if (!Array.isArray(projections)) {
      throw new MuBinaryDecodeError(
        `Seed binary image must decode to projections array, got ${
          projections === null ? 'null' : typeof projections
        }`
      );
    }
    if (decoded.sawFloat64) {
      throw new MuBinaryDecodeError(
        'Seed binary projection contains FLOAT64 numeric data; current seed images are integer-only'
      );
    }
    for (let i = 0; i < projections.length; i++) {
      const proj = projections[i];
      if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) {
        throw new MuBinaryDecodeError(
          `Seed binary projection[${i}] must be a plain object, ` +
          `got ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`
        );
      }
      for (const key of ['id', 'pattern', 'body']) {
        if (!(key in proj)) {
          throw new MuBinaryDecodeError(`Seed binary projection ${i} missing key '${key}'`);
        }
      }
      const projectionKeys = Object.keys(proj);
      if (JSON.stringify(projectionKeys) !== JSON.stringify(SEED_BINARY_PROJECTION_KEY_ORDER)) {
        throw new MuBinaryDecodeError(
          `Seed binary projection ${i} has non-canonical key order: ` +
          `${JSON.stringify(projectionKeys)}`
        );
      }
      if (typeof proj.id !== 'string') {
        throw new MuBinaryDecodeError(
          `Seed binary projection ${i} id must be a string, got ${typeof proj.id}`
        );
      }
      this.rejectNonIntegerSeedNumerics(proj.pattern, `projection[${i}].pattern`);
      this.rejectNonIntegerSeedNumerics(proj.body, `projection[${i}].body`);
    }
    return muCopy(projections, true, 'Decoded binary seed projections');
  },

  requireMigrationPolicy(policyId) {
    if (policyId !== SEED_BINARY_MIGRATION_POLICY_ID) {
      throw new Error(`Unsupported seed binary migration policy: ${policyId}`);
    }
  },

  minimalSeedProjections(seed) {
    return seed.projections.map(projection => ({
      id: projection.id,
      pattern: projection.pattern,
      body: projection.body,
    }));
  },

  proofChainPayload(seedName, jsonSha256, binarySha256, projectionIds, migrationPolicyId) {
    return {
      binary_sha256: binarySha256,
      checksum_policy_id: SEED_BINARY_CHECKSUM_POLICY_ID,
      json_sha256: jsonSha256,
      migration_policy_id: migrationPolicyId,
      projection_ids: projectionIds,
      seed_name: seedName,
    };
  },

  proofChainSha256(payload) {
    return crypto
      .createHash('sha256')
      .update(Buffer.from(JSON.stringify(payload), 'utf8'))
      .digest('hex');
  },

  buildMigrationProof(
    seedName,
    seedBytes,
    binaryImage,
    verificationMode,
    migrationPolicyId = SEED_BINARY_MIGRATION_POLICY_ID
  ) {
    this.requireMigrationPolicy(migrationPolicyId);
    const imageBytes = Buffer.isBuffer(seedBytes) ? seedBytes : Buffer.from(seedBytes);
    const binaryBytes = this.toBuffer(binaryImage);
    const verificationView = SEED_IMAGE_VERIFICATION_VIEWS[verificationMode];
    if (!verificationView) {
      throw new Error(`Unknown seed image verification mode: ${verificationMode}`);
    }

    const seed = loadVerifiedSeedImage(seedName, imageBytes, verificationMode);
    const decodedProjections = this.decodeSeedProjections(binaryBytes);
    const decodedProjectionIds = decodedProjections.map(projection => projection.id);
    const expectedProjectionIds = verificationView.projectionIdRegistry[seedName];
    if (JSON.stringify(decodedProjectionIds) !== JSON.stringify(expectedProjectionIds)) {
      throw new Error(
        `Seed binary projection ID mismatch for ${seedName}: ` +
        `expected ${JSON.stringify(expectedProjectionIds)}, got ${JSON.stringify(decodedProjectionIds)}`
      );
    }

    const expectedProjections = this.minimalSeedProjections(seed);
    if (JSON.stringify(decodedProjections) !== JSON.stringify(expectedProjections)) {
      throw new Error(`Seed binary source/binary mismatch for ${seedName}`);
    }
    if (binaryBytes.length >= imageBytes.length) {
      throw new Error(
        `Generated seed binary image for ${seedName} is not smaller than JSON ` +
        `(${binaryBytes.length} >= ${imageBytes.length})`
      );
    }

    const jsonSha256 = crypto.createHash('sha256').update(imageBytes).digest('hex');
    const binarySha256 = crypto.createHash('sha256').update(binaryBytes).digest('hex');
    const chainPayload = this.proofChainPayload(
      seedName,
      jsonSha256,
      binarySha256,
      decodedProjectionIds,
      migrationPolicyId
    );
    return {
      seed_name: seedName,
      migration_policy_id: migrationPolicyId,
      checksum_policy_id: SEED_BINARY_CHECKSUM_POLICY_ID,
      json_sha256: jsonSha256,
      binary_sha256: binarySha256,
      proof_chain_sha256: this.proofChainSha256(chainPayload),
      projection_ids: decodedProjectionIds,
      projection_count: decodedProjections.length,
      json_size: imageBytes.length,
      binary_size: binaryBytes.length,
      binary_is_smaller: binaryBytes.length < imageBytes.length,
    };
  },

  verifyMigrationArtifact(
    seedName,
    seedBytes,
    binaryImage,
    expectedProof,
    verificationMode,
    migrationPolicyId = SEED_BINARY_MIGRATION_POLICY_ID
  ) {
    if (expectedProof === null || typeof expectedProof !== 'object' || Array.isArray(expectedProof)) {
      throw new Error('Seed binary proof must be an object');
    }
    const computedProof = this.buildMigrationProof(
      seedName,
      seedBytes,
      binaryImage,
      verificationMode,
      migrationPolicyId
    );
    const expectedKeys = Object.keys(expectedProof).sort();
    const computedKeys = Object.keys(computedProof).sort();
    if (JSON.stringify(expectedKeys) !== JSON.stringify(computedKeys)) {
      throw new Error(
        `Seed binary proof key set mismatch for ${seedName}: ` +
        `expected keys ${JSON.stringify(expectedKeys)}, got ${JSON.stringify(computedKeys)}`
      );
    }
    for (const key of computedKeys) {
      if (JSON.stringify(expectedProof[key]) !== JSON.stringify(computedProof[key])) {
        throw new Error(
          `Seed binary proof mismatch for ${seedName}: ${key} ` +
          `expected ${JSON.stringify(expectedProof[key])}, got ${JSON.stringify(computedProof[key])}`
        );
      }
    }
    return computedProof;
  },
});

const decodeMuBinaryValue = MU_BINARY_CODEC.decodeValue.bind(MU_BINARY_CODEC);
const decodeSeedBinaryProjections = MU_BINARY_CODEC.decodeSeedProjections.bind(MU_BINARY_CODEC);
const buildSeedBinaryMigrationProof = MU_BINARY_CODEC.buildMigrationProof.bind(MU_BINARY_CODEC);
const verifySeedBinaryMigrationArtifact = MU_BINARY_CODEC.verifyMigrationArtifact.bind(MU_BINARY_CODEC);

/**
 * Verify, parse, and validate a seed JSON image without performing file I/O.
 * @param {string} seedName - Seed filename (e.g., 'terminal_classify.v1.json')
 * @param {Buffer|string} seedBytes - Raw seed JSON bytes
 * @param {string} verificationMode - Closed manifest view selector
 * @param {?Buffer} binaryImage - Optional smaller MuBinary sidecar bytes
 * @param {?object} expectedBinaryProof - Required proof object when binaryImage is set
 * @returns {object} Parsed seed object
 */
function loadVerifiedSeedImage(
  seedName,
  seedBytes,
  verificationMode,
  binaryImage = null,
  expectedBinaryProof = null
) {
  const imageBytes = Buffer.isBuffer(seedBytes) ? seedBytes : Buffer.from(seedBytes);
  const verificationView = SEED_IMAGE_VERIFICATION_VIEWS[verificationMode];
  if (!verificationView) {
    throw new Error(`Unknown seed image verification mode: ${verificationMode}`);
  }
  const {
    checksumRegistry,
    projectionIdRegistry,
    checksumRegistryName,
    projectionIdRegistryName,
  } = verificationView;

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

  // Canonical production seed images are integer-only. Scan number syntax before
  // JSON.parse so JS cannot silently collapse 1.0/1e0 into the same Number as 1.
  let inString = false;
  let escaped = false;
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === '"') {
        inString = false;
      }
      continue;
    }
    if (ch === '"') {
      inString = true;
      continue;
    }
    if (ch !== '-' && (ch < '0' || ch > '9')) {
      continue;
    }

    const start = i;
    if (ch === '-') {
      i++;
    }
    while (i < raw.length && raw[i] >= '0' && raw[i] <= '9') {
      i++;
    }
    let decimalOrExponent = false;
    if (raw[i] === '.') {
      decimalOrExponent = true;
      i++;
      while (i < raw.length && raw[i] >= '0' && raw[i] <= '9') {
        i++;
      }
    }
    if (raw[i] === 'e' || raw[i] === 'E') {
      decimalOrExponent = true;
      i++;
      if (raw[i] === '+' || raw[i] === '-') {
        i++;
      }
      while (i < raw.length && raw[i] >= '0' && raw[i] <= '9') {
        i++;
      }
    }
    if (decimalOrExponent) {
      throw new Error(
        `Seed ${seedName} contains non-integer JSON numeric literal ${raw.slice(start, i)}`
      );
    }
    i--;
  }

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

  const hasBinaryImage = binaryImage !== null && binaryImage !== undefined;
  const hasBinaryProof = expectedBinaryProof !== null && expectedBinaryProof !== undefined;
  if (hasBinaryImage !== hasBinaryProof) {
    throw new Error('binaryImage and expectedBinaryProof must be provided together');
  }
  if (hasBinaryImage) {
    const binaryBytes = MU_BINARY_CODEC.toBuffer(binaryImage);
    MU_BINARY_CODEC.verifyMigrationArtifact(
      seedName,
      imageBytes,
      binaryBytes,
      expectedBinaryProof,
      verificationMode
    );
    return muCopy(
      {
        ...seed,
        projections: MU_BINARY_CODEC.decodeSeedProjections(binaryBytes),
      },
      true,
      'Verified binary seed image'
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
    SEED_IMAGE_VERIFICATION_MODES.CORE
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
  decodeMuBinaryValue,
  decodeSeedBinaryProjections,
  buildSeedBinaryMigrationProof,
  verifySeedBinaryMigrationArtifact,
  MuBinaryDecodeError,
  SEED_BINARY_MIGRATION_POLICY_ID,
  SEED_BINARY_CHECKSUM_POLICY_ID,
  SEED_IMAGE_VERIFICATION_MODES,
  SEED_REGISTRY_MANIFEST,
  RUN_ALGORITHM_AUTHORITY_SEEDS,
  SEED_CHECKSUMS,
  EXPECTED_PROJECTION_IDS,
  CORE_SEED_CHECKSUMS,
  CORE_SEED_PROJECTION_IDS,
  SEED_SUBDIRS,
  SEED_DEPENDENCIES,
};
