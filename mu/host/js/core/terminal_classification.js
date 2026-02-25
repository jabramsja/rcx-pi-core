'use strict';
/**
 * RCX Terminal Classification
 *
 * Terminal shape checks, hemisphere keys, engine exit reasons.
 * Structural displacement (Wave 25): classify/exit-reason logic delegated
 * to terminal_classify.v1.json seed projections via step().
 * kernel_done stays host-side (key-membership check).
 *
 * Depends on: core/constants.js, core/bootstrap_core.js, core/seed_loader.js
 */

const { step } = require('./bootstrap_core');

// Terminal shape key sets — concrete compatibility exports (kept this wave).
// Mirrors Python step_mu.py frozenset constants.
const RECURRENCE_TERMINAL_KEYS = new Set(['closure_detected', 'final_result', 'tau_step']);
const EXHAUSTION_TERMINAL_KEYS = new Set(['action', 'exhaustion_detected', 'frozen', 'operator_to_freeze']);
const ENGINE_TERMINAL_KEYS = new Set([
  'value', 'closure_detected', 'tau_step', 'exhaustion_detected',
  'operator_frozen', 'frozen_set', 'action', 'stall',
]);

// Engine exit reason enum (mirrors Python ENGINE_EXIT_REASONS)
const ENGINE_EXIT_REASONS = new Set(['closure', 'exhaustion', 'stall', 'completed']);

// Terminal kind enum — unified classification of all terminal states.
const TERMINAL_KINDS = new Set([
  'kernel_done',
  'recurrence_terminal',
  'exhaustion_terminal',
  'engine_terminal',
  'non_terminal',
]);

// Hemisphere constants (mirrors Python step_mu.py)
const HEMISPHERE_KEY_ORDER = ['r_null', 'r_inf', 'r_a', 'lobes', 'sink'];
const HEMISPHERE_KEYS = new Set(HEMISPHERE_KEY_ORDER);

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

// Cached terminal classify seed projections (lazy-loaded)
let _tcProjections = null;
function _loadTcProjections() {
  if (!_tcProjections) {
    const { loadVerifiedSeed } = require('./seed_loader');
    const seed = loadVerifiedSeed('terminal_classify.v1.json', 'utilities');
    _tcProjections = seed.projections;
  }
  return _tcProjections;
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
  // Structural seed classification via projection matching
  const projs = _loadTcProjections();
  const result = step(projs, { _tc: value });
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
 * Structural displacement (Wave 25): delegates to terminal_classify.v1.json
 * seed projections via step().
 */
function deriveEngineExitReason(engineResult) {
  const projs = _loadTcProjections();
  const wrapped = {
    _tc_exit: {
      cd: !!engineResult.closure_detected,
      ed: !!engineResult.exhaustion_detected,
      st: !!engineResult.stall,
    },
  };
  const result = step(projs, wrapped);
  return typeof result === 'string' ? result : 'completed';
}

function defaultHemispheres() {
  return { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null };
}

module.exports = {
  RECURRENCE_TERMINAL_KEYS,
  EXHAUSTION_TERMINAL_KEYS,
  ENGINE_TERMINAL_KEYS,
  ENGINE_EXIT_REASONS,
  TERMINAL_KINDS,
  HEMISPHERE_KEY_ORDER,
  HEMISPHERE_KEYS,
  setsEqual,
  classifyTerminalKind,
  isTerminalShape,
  isEngineTerminal,
  deriveEngineExitReason,
  defaultHemispheres,
};
