'use strict';
/**
 * RCX Type Validation and Hashing
 *
 * Depends on: core/constants.js, crypto (Node built-in)
 */

const crypto = require('crypto');
const { MAX_DEPTH, RcxError } = require('./constants');

const MAX_MU_WIDTH = 1000;

/**
 * Check if a number is valid (rejects NaN, Infinity, -Infinity).
 * Matches Python's mu_type validation.
 */
function isValidNumber(n) {
  return typeof n === 'number' && !isNaN(n) && isFinite(n);
}

/**
 * Check if value is a variable site {"var": "name"}
 */
function isVar(mu) {
  return (
    mu !== null &&
    typeof mu === 'object' &&
    !Array.isArray(mu) &&
    Object.keys(mu).length === 1 &&
    typeof mu.var === 'string'
  );
}

/**
 * Check if value is a valid Mu type.
 * Rejects NaN, Infinity, functions, undefined, symbols.
 * Enforces depth and width limits matching Python (MAX_DEPTH=300, MAX_WIDTH=1000).
 * Rejects objects with Symbol keys (not valid Mu).
 * @host_builtin - BOOTSTRAP: type validation primitive
 */
function isValidMu(value, _depth = 0) {
  // Depth guard (matches Python MAX_MU_DEPTH)
  if (_depth > MAX_DEPTH) return false;

  if (value === null) return true;
  if (value === undefined) return false;

  const t = typeof value;
  if (t === 'boolean' || t === 'string') return true;
  if (t === 'number') return isValidNumber(value);
  if (t === 'function' || t === 'symbol') return false;

  if (Array.isArray(value)) {
    // Width guard (matches Python MAX_MU_WIDTH)
    if (value.length > MAX_MU_WIDTH) return false;
    return value.every(v => isValidMu(v, _depth + 1));
  }

  if (t === 'object') {
    const keys = Object.keys(value);
    // Width guard (matches Python MAX_MU_WIDTH)
    if (keys.length > MAX_MU_WIDTH) return false;
    // Reject Symbol keys (not valid Mu - Object.keys ignores them but we check explicitly)
    if (Object.getOwnPropertySymbols(value).length > 0) return false;
    // Validate all string keys are actually strings (defensive)
    if (!keys.every(k => typeof k === 'string')) return false;
    return keys.every(k => isValidMu(value[k], _depth + 1));
  }

  return false;
}

/**
 * ELIMINATED PRIMITIVE: mu_equal (Content-Addressed Mu Level 1)
 * Previously a bootstrap primitive. Now derivable from muHashCached.
 * Used in production stall-detection loops (pipeline.js, json_handlers.js)
 * and tests.
 * @host_builtin - convenience wrapper around muHashCached
 */
function muEqual(a, b) {
  if (!isValidMu(a) || !isValidMu(b)) {
    throw new RcxError('input.invalid_type', 'muEqual: value is not valid Mu');
  }
  return muHashCached(a) === muHashCached(b);
}

/**
 * Match Python's lexicographic Unicode code-point ordering for dict keys.
 * JS default string sort is UTF-16 code unit based and can diverge for
 * mixed BMP/non-BMP keys, so we compare by full code points.
 */
function compareMuStringKeysByCodepoint(a, b) {
  let ai = 0;
  let bi = 0;
  while (ai < a.length && bi < b.length) {
    const acp = a.codePointAt(ai);
    const bcp = b.codePointAt(bi);
    if (acp !== bcp) return acp - bcp;
    ai += acp > 0xffff ? 2 : 1;
    bi += bcp > 0xffff ? 2 : 1;
  }
  if (ai === a.length && bi === b.length) return 0;
  return ai === a.length ? -1 : 1;
}

/**
 * Compute deterministic SHA-256 hash of a Mu value.
 * Matches Python mu_hash(): canonical JSON with sorted keys.
 * @host_builtin: BOOTSTRAP_PRIMITIVE (irreducible, required for hash-accelerated closure detection)
 */
function muHash(value) {
  // Must match Python: json.dumps(value, sort_keys=True, ensure_ascii=False)
  // Python uses `, ` between items and `: ` between key/value (separators=(', ', ': '))
  function canonicalize(v) {
    if (v === null) return 'null';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v === 'number') return Object.is(v, -0) ? '-0.0' : JSON.stringify(v);
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) {
      return '[' + v.map(canonicalize).join(', ') + ']';
    }
    // Object: sort keys, use Python separators
    const keys = Object.keys(v).sort(compareMuStringKeysByCodepoint);
    const pairs = keys.map(k => JSON.stringify(k) + ': ' + canonicalize(v[k]));
    return '{' + pairs.join(', ') + '}';
  }
  return crypto.createHash('sha256').update(canonicalize(value), 'utf8').digest('hex');
}

/**
 * Compute deterministic SHA-256 hash with caching.
 * Mirrors Python mu_hash_cached(). Cache avoids re-hashing identical structures.
 * Used for hash-accelerated equality comparison (Content-Addressed Mu Level 1).
 */
const MAX_MU_HASH_CACHE = 10000;
const _muHashCache = new Map();
function muHashCached(value) {
  // Deterministic cache key: sorted-key JSON (JS-local, not cross-substrate)
  const key = JSON.stringify(value, (_, v) => {
    if (typeof v === 'number' && Object.is(v, -0)) return '\x00NEGZERO';
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const sorted = {};
      for (const k of Object.keys(v).sort(compareMuStringKeysByCodepoint)) sorted[k] = v[k];
      return sorted;
    }
    return v;
  });
  const cached = _muHashCache.get(key);
  if (cached !== undefined) {
    // LRU: delete and re-insert to move to end (most recently used)
    _muHashCache.delete(key);
    _muHashCache.set(key, cached);
    return cached;
  }
  const hash = muHash(value);
  _muHashCache.set(key, hash);
  // Evict oldest if over limit
  if (_muHashCache.size > MAX_MU_HASH_CACHE) {
    const oldest = _muHashCache.keys().next().value;
    _muHashCache.delete(oldest);
  }
  return hash;
}

// =============================================================================
// Numeric Hash Control (Control-Channel Safety Lock)
// =============================================================================
// Control-flow hash paths (stall detection, convergence, recurrence trace)
// must reject ambiguous numeric domain to prevent cross-substrate divergence.
// See NorthStarSemantics.v0.md §B.1 for policy.
// =============================================================================

/**
 * Canonicalize numeric domain: ±0 → 0. In JS all numbers are IEEE 754 doubles,
 * so there's no int/float distinction to resolve — only -0 needs canonicalization.
 */
function canonicalizeHashNumeric(value) {
  if (typeof value === 'number') return Object.is(value, -0) ? 0 : value;
  if (Array.isArray(value)) return value.map(canonicalizeHashNumeric);
  if (value !== null && typeof value === 'object') {
    const out = Object.create(null);
    for (const k of Object.keys(value)) out[k] = canonicalizeHashNumeric(value[k]);
    return out;
  }
  return value;
}

/**
 * Hash a Mu value for control-flow paths (stall, convergence, trace).
 * Validates Mu, canonicalizes numerics (±0→0), then delegates to muHash.
 */
function muHashControl(value, context) {
  context = context || 'muHashControl';
  if (!isValidMu(value)) {
    throw new RcxError('input.invalid_type',
      `${context}: value is not valid Mu`);
  }
  return muHash(canonicalizeHashNumeric(value));
}

/**
 * Hash a Mu value for control-flow paths with caching.
 * Validates Mu, canonicalizes numerics (±0→0), then delegates to muHashCached.
 */
function muHashControlCached(value, context) {
  context = context || 'muHashControlCached';
  if (!isValidMu(value)) {
    throw new RcxError('input.invalid_type',
      `${context}: value is not valid Mu`);
  }
  return muHashCached(canonicalizeHashNumeric(value));
}

module.exports = {
  MAX_MU_WIDTH,
  MAX_MU_HASH_CACHE,
  isValidNumber,
  isVar,
  isValidMu,
  muEqual,
  compareMuStringKeysByCodepoint,
  muHash,
  muHashCached,
  canonicalizeHashNumeric,
  muHashControl,
  muHashControlCached,
};
