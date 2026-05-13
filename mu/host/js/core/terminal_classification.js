'use strict';
/**
 * RCX Terminal Classification
 *
 * Terminal shape checks, hemisphere keys, engine exit reasons.
 * Structural displacement (Wave 25): classify/exit-reason logic delegated
 * to terminal_classify.v1.json seed projections via step().
 * A7: terminal key sets now seed-derived (not hardcoded Sets).
 * A8: cache hardening — defensive copy getters, single seed loader,
 *     unified cache clear, muBool parity fix for exit-reason coercion.
 * A9: hemisphere key authority displaced from hardcoded constants to
 *     seed-derived (hemispheres.v1.json hemisphere.add.* projection IDs).
 * kernel_done stays host-side (key-membership check).
 *
 * Depends on: core/constants.js, core/bootstrap_core.js, core/seed_loader.js
 */

const { step } = require('./bootstrap_core');
const { RcxError } = require('./constants');
const muContainers = require('./container_factory');

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * Deep-freeze an object tree (works on JSON-parsed Mu: no cycles, no Sets).
 * Arrays and plain objects are frozen recursively.
 */
function _deepFreeze(obj) {
  Object.freeze(obj);
  for (const v of Object.values(obj)) {
    if (v !== null && typeof v === 'object' && !Object.isFrozen(v)) {
      _deepFreeze(v);
    }
  }
  return obj;
}

/**
 * Python-compatible boolean coercion for Mu values.
 * Matches Python bool() semantics where JS !! diverges:
 *   - empty array []  => false  (JS !! would give true)
 *   - empty object {} => false  (JS !! would give true)
 *   - all primitives use JS truthiness (matches Python bool())
 */
function _muBool(value) {
  if (Array.isArray(value)) return value.length > 0;
  if (value !== null && typeof value === 'object') return Object.keys(value).length > 0;
  return !!value;
}

// ---------------------------------------------------------------------------
// Single seed loader cache (A8: eliminates duplicate loadVerifiedSeed calls)
// ---------------------------------------------------------------------------

let _tcSeed = null;
function _loadTcSeed() {
  if (!_tcSeed) {
    const { loadVerifiedSeed } = require('./seed_loader');
    _tcSeed = loadVerifiedSeed('terminal_classify.v1.json', 'utilities');
  }
  return _tcSeed;
}

// ---------------------------------------------------------------------------
// Terminal shape key sets — seed-derived from terminal_classify.v1.json
// ---------------------------------------------------------------------------
// Authority lives in seed projections, not hardcoded Sets.
// Mirrors Python _load_tc_key_sets() in step_mu.py.
// Internal Sets are private; exported getters return defensive copies (A8).

let _tcKeySets = null;
let _RECURRENCE_TERMINAL_KEYS = null;
let _EXHAUSTION_TERMINAL_KEYS = null;
let _ENGINE_TERMINAL_KEYS = null;

function _loadTcKeySets() {
  if (_tcKeySets) return _tcKeySets;
  const seed = _loadTcSeed();
  const result = {};
  for (const p of seed.projections) {
    const pat = p.pattern ?? {};
    if ('_tc' in pat) {
      result[p.id] = new Set(Object.keys(pat._tc));
    }
  }
  _tcKeySets = result;
  return result;
}

function _ensureKeySets() {
  if (_RECURRENCE_TERMINAL_KEYS) return;
  const sets = _loadTcKeySets();
  _RECURRENCE_TERMINAL_KEYS = sets['tc.recurrence'];
  _EXHAUSTION_TERMINAL_KEYS = sets['tc.exhaustion'];
  _ENGINE_TERMINAL_KEYS = sets['tc.engine'];
}

// ---------------------------------------------------------------------------
// Cached terminal classify seed projections (one-time deep-clone + freeze)
// ---------------------------------------------------------------------------

let _tcProjections = null;
function _loadTcProjections() {
  if (!_tcProjections) {
    const seed = _loadTcSeed();
    // One-time deep clone + deep freeze: closes mutation risk without
    // per-call overhead. Mirrors Python projection_loader.py's adversary-
    // hardened deep copy, but frozen instead of copied per call.
    _tcProjections = JSON.parse(JSON.stringify(seed.projections), (_key, value) => {
      if (Array.isArray(value)) return muContainers.list(value);
      if (value !== null && typeof value === 'object') {
        return muContainers.record(Object.keys(value).map(key => [key, value[key]]));
      }
      return value;
    });
    _tcProjections = _deepFreeze(_tcProjections);
  }
  return _tcProjections;
}

// ---------------------------------------------------------------------------
// Enum constants (internal — exported via defensive copy getters)
// ---------------------------------------------------------------------------

// Engine exit reason enum (mirrors Python ENGINE_EXIT_REASONS)
const _ENGINE_EXIT_REASONS = new Set(['closure', 'exhaustion', 'stall', 'completed']);

// Terminal kind enum — unified classification of all terminal states.
const _TERMINAL_KINDS = new Set([
  'kernel_done',
  'recurrence_terminal',
  'exhaustion_terminal',
  'engine_terminal',
  'non_terminal',
]);

// ---------------------------------------------------------------------------
// Hemisphere key sets — seed-derived from hemispheres.v1.json (A9 displacement)
// ---------------------------------------------------------------------------
// Authority lives in hemisphere.add.* projection IDs, not hardcoded arrays.
// _EXPECTED_HEMI_KEYS is a fail-closed safety guard (duplicate literals),
// NOT authority-of-truth. Authority is seed-derived; expected set catches corruption.

let _hemiSeed = null;
function _loadHemiSeed() {
  if (!_hemiSeed) {
    const { loadVerifiedSeed } = require('./seed_loader');
    _hemiSeed = loadVerifiedSeed('hemispheres.v1.json', 'programs');
  }
  return _hemiSeed;
}

const _EXPECTED_HEMI_KEYS = new Set(['r_null', 'r_inf', 'r_a', 'lobes', 'sink']);
let _hemiKeyOrder = null;
let _hemiKeySet = null;

function _ensureHemiKeys() {
  if (_hemiKeyOrder) return;
  const seed = _loadHemiSeed();
  const prefix = 'hemisphere.add.';
  const keys = seed.projections.filter(p => p.id.startsWith(prefix))
    .map(p => p.id.slice(prefix.length));
  const keySet = new Set(keys);
  // Fail-closed invariants (A9 Requirement A)
  if (keys.length !== 5) {
    throw new RcxError('input.shape_mismatch',
      `hemisphere seed invariant: expected 5 keys, got ${keys.length}`);
  }
  if (keys.length !== keySet.size) {
    throw new RcxError('input.shape_mismatch',
      'hemisphere seed invariant: duplicate keys');
  }
  if (!setsEqual(keySet, _EXPECTED_HEMI_KEYS)) {
    throw new RcxError('input.shape_mismatch',
      'hemisphere seed invariant: unexpected key set');
  }
  _hemiKeyOrder = keys;
  _hemiKeySet = keySet;
}

// ---------------------------------------------------------------------------
// Cache clear (A8+A9: clears all caches including hemisphere — exported for testing)
// ---------------------------------------------------------------------------

/**
 * Clear all terminal classification and hemisphere caches (for testing).
 * Mirrors Python _clear_tc_cache() + _clear_hemi_cache() in step_mu.py.
 */
function _clearTcCache() {
  _tcSeed = null;
  _tcProjections = null;
  _tcKeySets = null;
  _RECURRENCE_TERMINAL_KEYS = null;
  _EXHAUSTION_TERMINAL_KEYS = null;
  _ENGINE_TERMINAL_KEYS = null;
  _hemiSeed = null;
  _hemiKeyOrder = null;
  _hemiKeySet = null;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compare two Sets for equality.
 */
function setsEqual(a, b) {
  if (a.size !== b.size) return false;
  for (const item of a) {
    if (!b.has(item)) return false;
  }
  return true;
}

/**
 * Classify a value into exactly one terminal kind.
 * Returns one of TERMINAL_KINDS. Pure structural check — no side effects.
 * Priority: kernel_done > recurrence > exhaustion > engine > non_terminal.
 * Cross-substrate parity: must match Python classify_terminal_kind() exactly.
 *
 * Structural displacement (Wave 25): delegates to terminal_classify.v1.json
 * seed projections via step(). kernel_done stays host-side.
 */
function classifyTerminalKind(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return 'non_terminal';
  // kernel_done: host-side (key-membership check, not exact-key-match)
  if (value._mode === 'done' && '_result' in value && '_stall' in value) return 'kernel_done';
  // Key-set prefilter: only candidate shapes reach the seed path.
  // Avoids step() (and its assertMu walk) on engine-internal state dicts.
  _ensureKeySets();
  const keys = new Set(Object.keys(value));
  if (!setsEqual(keys, _RECURRENCE_TERMINAL_KEYS) &&
      !setsEqual(keys, _EXHAUSTION_TERMINAL_KEYS) &&
      !setsEqual(keys, _ENGINE_TERMINAL_KEYS)) {
    return 'non_terminal';
  }
  // Structural seed classification via projection matching
  const projs = _loadTcProjections();
  const wrapped = muContainers.record([['_tc', value]]);
  const result = step(projs, wrapped);
  return typeof result === 'string' ? result : 'non_terminal';
}

/**
 * Check for recurrence/exhaustion terminal output shape.
 * Mirrors Python _is_terminal_shape().
 */
function isTerminalShape(value) {
  const kind = classifyTerminalKind(value);
  return kind === 'recurrence_terminal' || kind === 'exhaustion_terminal';
}

/**
 * Check if engine has produced its final unwrapped result (8-key shape).
 * Mirrors Python _is_engine_terminal().
 */
function isEngineTerminal(value) {
  return classifyTerminalKind(value) === 'engine_terminal';
}

/**
 * Derive engine_exit_reason from the existing 8-key terminal dict.
 * Priority: closure > exhaustion > stall > completed.
 * Pure function — does NOT modify engine_result.
 * Mirrors Python _derive_engine_exit_reason().
 *
 * A8 parity fix: uses _muBool() instead of !! for boolean coercion.
 * Python uses bool() which returns False for empty containers ([], {}).
 * JS !! returns true for all objects. _muBool matches Python semantics.
 *
 * Structural displacement (Wave 25): delegates to terminal_classify.v1.json
 * seed projections via step().
 */
function deriveEngineExitReason(engineResult) {
  const projs = _loadTcProjections();
  const wrapped = muContainers.record([
    ['_tc_exit', muContainers.record([
      ['cd', _muBool(engineResult.closure_detected)],
      ['ed', _muBool(engineResult.exhaustion_detected)],
      ['st', _muBool(engineResult.stall)],
    ])],
  ]);
  const result = step(projs, wrapped);
  return typeof result === 'string' ? result : 'completed';
}

function defaultHemispheres() {
  _ensureHemiKeys();
  const h = muContainers.record();
  for (const k of _hemiKeyOrder) h[k] = null;
  return h;
}

// ---------------------------------------------------------------------------
// Exports — all Set/Array getters return defensive copies (A8 hardening).
// Callers cannot mutate internal state.
// ---------------------------------------------------------------------------

module.exports = {
  // Seed-derived terminal key sets — defensive copies (new Set each call)
  get RECURRENCE_TERMINAL_KEYS() { _ensureKeySets(); return new Set(_RECURRENCE_TERMINAL_KEYS); },
  get EXHAUSTION_TERMINAL_KEYS() { _ensureKeySets(); return new Set(_EXHAUSTION_TERMINAL_KEYS); },
  get ENGINE_TERMINAL_KEYS() { _ensureKeySets(); return new Set(_ENGINE_TERMINAL_KEYS); },
  // Enum constants — defensive copies
  get ENGINE_EXIT_REASONS() { return new Set(_ENGINE_EXIT_REASONS); },
  get TERMINAL_KINDS() { return new Set(_TERMINAL_KINDS); },
  get HEMISPHERE_KEY_ORDER() { _ensureHemiKeys(); return [..._hemiKeyOrder]; },
  get HEMISPHERE_KEYS() { _ensureHemiKeys(); return new Set(_hemiKeySet); },
  // Functions
  setsEqual,
  classifyTerminalKind,
  isTerminalShape,
  isEngineTerminal,
  deriveEngineExitReason,
  defaultHemispheres,
  _clearTcCache,
};
