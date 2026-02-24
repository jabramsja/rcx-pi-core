'use strict';
/**
 * RCX Terminal Classification
 *
 * Terminal shape checks, hemisphere keys, engine exit reasons.
 * Depends on: core/constants.js only
 */

// Terminal shape key sets (mirrors Python step_mu.py:42-47)
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

// Hemisphere constants (mirrors Python step_mu.py:1626-1632)
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

/**
 * Classify a value into exactly one terminal kind.
 * Returns one of TERMINAL_KINDS. Pure structural check — no side effects.
 * Priority: kernel_done > recurrence > exhaustion > engine > non_terminal.
 * Cross-substrate parity: must match Python classify_terminal_kind() exactly.
 */
function classifyTerminalKind(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return 'non_terminal';
  if (value._mode === 'done' && '_result' in value && '_stall' in value) return 'kernel_done';
  const keys = new Set(Object.keys(value));
  if (setsEqual(keys, RECURRENCE_TERMINAL_KEYS)) return 'recurrence_terminal';
  if (setsEqual(keys, EXHAUSTION_TERMINAL_KEYS)) return 'exhaustion_terminal';
  if (setsEqual(keys, ENGINE_TERMINAL_KEYS)) return 'engine_terminal';
  return 'non_terminal';
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
 */
function deriveEngineExitReason(engineResult) {
  if (engineResult.closure_detected) return 'closure';
  if (engineResult.exhaustion_detected) return 'exhaustion';
  if (engineResult.stall) return 'stall';
  return 'completed';
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
