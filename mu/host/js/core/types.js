'use strict';
/**
 * RCX Type Validation and Hashing
 *
 * Depends on: core/constants.js, crypto/util (Node built-ins)
 */

const crypto = require('crypto');
const { types: utilTypes } = require('util');
const { MAX_DEPTH, RcxError } = require('./constants');

const MAX_MU_WIDTH = 1000;

// =============================================================================
// Structural Depth Budget (D009 Productionization)
// =============================================================================
// Budget is a Mu linked list: {head: null, tail: <budget>} or null (exhausted).
// Created once at module load and frozen (Object.freeze) for immutability.
// Shared across all calls (depth-only semantics: each recursion level reads
// budget.tail but never modifies the original).
// =============================================================================

// Sentinel for "no budget provided" — distinct from null (= budget exhausted).
const _NO_BUDGET = Object.freeze({ _sentinel: 'NO_BUDGET' });

/**
 * Create a structural depth budget of given size. Returns frozen Mu linked-list.
 */
function makeDepthBudget(depth) {
  let budget = null;
  for (let i = 0; i < depth; i++) {
    budget = { head: null, tail: budget };
  }
  // Recursively freeze (Q5: immutability enforcement)
  function deepFreeze(obj) {
    if (obj !== null && typeof obj === 'object') {
      Object.freeze(obj);
      deepFreeze(obj.tail);
    }
  }
  deepFreeze(budget);
  return budget;
}

/**
 * Consume one level from budget. Returns [ok, remaining].
 *
 * Budget is always either null (exhausted) or a well-formed linked-list
 * node {head: null, tail: <budget>} constructed by makeDepthBudget().
 * All callers are internal — no external input reaches this function.
 * typeof check removed (P7 Wave 2): trusting well-formed budget,
 * parity with Python consume_budget simplification.
 */
function consumeBudget(budget) {
  if (budget === null) {
    return [false, null];
  }
  if ('tail' in budget) {
    return [true, budget.tail];
  }
  return [false, null];
}

// Module-level shared budget (frozen — immutable).
const _STRUCTURAL_DEPTH_BUDGET = makeDepthBudget(MAX_DEPTH + 1);

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
    !utilTypes.isProxy(mu) &&
    !Array.isArray(mu) &&
    Object.keys(mu).length === 1 &&
    Object.hasOwn(mu, 'var') && typeof mu.var === 'string'
  );
}

/**
 * Check if value is a valid Mu type.
 * Rejects NaN, Infinity, functions, undefined, symbols.
 * Enforces depth and width limits matching Python (MAX_DEPTH=300, MAX_WIDTH=1000).
 * Rejects objects with Symbol keys (not valid Mu).
 * Detects reference cycles via WeakSet with backtracking (matches Python is_mu's _seen set).
 * Backtracking allows DAGs (shared references) while catching true cycles.
 * @host_builtin - BOOTSTRAP: type validation primitive
 */
function isValidMu(value, _depth = 0, _seen, _budget = _NO_BUDGET) {
  // --- Structural budget path (opt-in) ---
  if (_budget !== _NO_BUDGET) {
    const [ok, remaining] = consumeBudget(_budget);
    if (!ok) return false;  // Budget exhausted

    if (value === null) return true;
    if (value === undefined) return false;

    const t = typeof value;
    if (t === 'boolean' || t === 'string') return true;
    if (t === 'number') return isValidNumber(value);
    if (t === 'function' || t === 'symbol') return false;
    if (utilTypes.isProxy(value)) return false;

    if (!_seen) _seen = new WeakSet();  // AST_OK_JS: cycle detection for is_mu budget path (matches Python _seen set)
    if (_seen.has(value)) return false;
    _seen.add(value);

    if (Array.isArray(value)) {
      if (Object.getPrototypeOf(value) !== Array.prototype) { _seen.delete(value); return false; }
      if (value.length > MAX_MU_WIDTH) { _seen.delete(value); return false; }
      if (Object.getOwnPropertySymbols(value).length > 0) { _seen.delete(value); return false; }
      if (Object.keys(value).length !== value.length) { _seen.delete(value); return false; }
      if (Object.getOwnPropertyNames(value).length !== value.length + 1) { _seen.delete(value); return false; }
      for (let i = 0; i < value.length; i++) {
        const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
        if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) { _seen.delete(value); return false; }
      }
      // Depth-only: same 'remaining' passed to all siblings
      const result = value.every(v => isValidMu(v, _depth, _seen, remaining));
      _seen.delete(value);
      return result;
    }

    if (t === 'object') {
      const prototype = Object.getPrototypeOf(value);
      if (prototype !== Object.prototype && prototype !== null) { _seen.delete(value); return false; }
      const keys = Object.keys(value);
      if (keys.length > MAX_MU_WIDTH) { _seen.delete(value); return false; }
      if (Object.getOwnPropertySymbols(value).length > 0) { _seen.delete(value); return false; }
      if (Object.getOwnPropertyNames(value).length !== keys.length) { _seen.delete(value); return false; }
      if (!keys.every(k => typeof k === 'string')) { _seen.delete(value); return false; }
      for (const k of keys) {
        const descriptor = Object.getOwnPropertyDescriptor(value, k);
        if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) { _seen.delete(value); return false; }
      }
      const result = keys.every(k => isValidMu(value[k], _depth, _seen, remaining));
      _seen.delete(value);
      return result;
    }

    return false;
  }

  // --- Integer depth path (default — existing behavior, zero overhead) ---
  // Depth guard (matches Python MAX_MU_DEPTH)
  if (_depth > MAX_DEPTH) return false;

  if (value === null) return true;
  if (value === undefined) return false;

  const t = typeof value;
  if (t === 'boolean' || t === 'string') return true;
  if (t === 'number') return isValidNumber(value);
  if (t === 'function' || t === 'symbol') return false;
  if (utilTypes.isProxy(value)) return false;

  // Cycle detection for objects and arrays (matches Python is_mu's _seen set with backtracking).
  // Backtracking (delete after subtree check) allows DAGs (shared references) while catching cycles.
  if (!_seen) _seen = new WeakSet();  // AST_OK_JS: cycle detection for is_mu (matches Python _seen set)
  if (_seen.has(value)) return false;
  _seen.add(value);

  if (Array.isArray(value)) {
    if (Object.getPrototypeOf(value) !== Array.prototype) { _seen.delete(value); return false; }
    // Width guard (matches Python MAX_MU_WIDTH)
    if (value.length > MAX_MU_WIDTH) { _seen.delete(value); return false; }
    if (Object.getOwnPropertySymbols(value).length > 0) { _seen.delete(value); return false; }
    if (Object.keys(value).length !== value.length) { _seen.delete(value); return false; }
    if (Object.getOwnPropertyNames(value).length !== value.length + 1) { _seen.delete(value); return false; }
    for (let i = 0; i < value.length; i++) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
      if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) { _seen.delete(value); return false; }
    }
    const ok = value.every(v => isValidMu(v, _depth + 1, _seen));
    _seen.delete(value);
    return ok;
  }

  if (t === 'object') {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) { _seen.delete(value); return false; }
    const keys = Object.keys(value);
    // Width guard (matches Python MAX_MU_WIDTH)
    if (keys.length > MAX_MU_WIDTH) { _seen.delete(value); return false; }
    // Reject Symbol keys (not valid Mu - Object.keys ignores them but we check explicitly)
    if (Object.getOwnPropertySymbols(value).length > 0) { _seen.delete(value); return false; }
    if (Object.getOwnPropertyNames(value).length !== keys.length) { _seen.delete(value); return false; }
    // Validate all string keys are actually strings (defensive)
    if (!keys.every(k => typeof k === 'string')) { _seen.delete(value); return false; }
    for (const k of keys) {
      const descriptor = Object.getOwnPropertyDescriptor(value, k);
      if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) { _seen.delete(value); return false; }
    }
    const ok = keys.every(k => isValidMu(value[k], _depth + 1, _seen));
    _seen.delete(value);
    return ok;
  }

  return false;
}

/**
 * DEMOTED PRIMITIVE: mu_equal (Content-Addressed Mu Level 1)
 * Previously a bootstrap primitive. Now derivable from muHashCached.
 * Retained for test convenience only — all production stall-detection
 * uses muHashCached directly (P7 Wave 2 demotion, parity with Python).
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
 * Canonical Mu JSON string used by hashing and hash-cache keys.
 */
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

/**
 * Compute deterministic SHA-256 hash of a Mu value.
 * Matches Python mu_hash() for all JSON-native types: canonical JSON with sorted keys.
 * NOTE: Integral floats diverge cross-substrate (Python json.dumps(1.0) -> "1.0",
 * JS JSON.stringify(1.0) -> "1"). Control-flow paths use muHashControl which
 * canonicalizes numerics to avoid this divergence.
 * @host_builtin: BOOTSTRAP_PRIMITIVE (irreducible, required for hash-accelerated closure detection)
 */
function muHash(value) {
  if (!isValidMu(value)) {
    throw new RcxError('input.invalid_type', 'muHash: value is not valid Mu');
  }
  // Must match Python: json.dumps(value, sort_keys=True, ensure_ascii=False)
  // Python uses `, ` between items and `: ` between key/value (separators=(', ', ': '))
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
  if (!isValidMu(value)) {
    throw new RcxError('input.invalid_type', 'muHashCached: value is not valid Mu');
  }
  const canonical = canonicalize(value);
  const cached = _muHashCache.get(canonical);
  if (cached !== undefined) {
    // LRU: delete and re-insert to move to end (most recently used)
    _muHashCache.delete(canonical);
    _muHashCache.set(canonical, cached);
    return cached;
  }
  const hash = crypto.createHash('sha256').update(canonical, 'utf8').digest('hex');
  _muHashCache.set(canonical, hash);
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
  // D009 depth budget primitives
  _NO_BUDGET,
  makeDepthBudget,
  consumeBudget,
  _STRUCTURAL_DEPTH_BUDGET,
};
