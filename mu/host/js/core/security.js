'use strict';
/**
 * RCX Security Validation
 *
 * Matches Python step_mu.py security hardening.
 * Depends on: core/constants.js
 */

const {
  KERNEL_RESERVED_FIELDS,
  ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
  MAX_VALIDATION_DEPTH,
  MAX_DEPTH,
  RcxError,
} = require('./constants');
const { MAX_MU_WIDTH } = require('./types');

/**
 * If value is a normalized dict encoding, return list of [key, value] pairs.
 * Otherwise return null.
 *
 * Normalized dict format (from normalize):
 *   {"_type":"dict","head":{"head":<key>,"tail":{"head":<val>,"tail":null}},"tail": ...}
 *
 * Gate 3 Security: This allows validateNoKernelReservedFields to check
 * keys inside normalized dict representations, preventing bypass attacks.
 */
function iterNormalizedDictPairs(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null;
  const keys = Object.keys(value);
  // Empty dict sentinel: {"_type": "dict"}
  if (keys.length === 1 && value._type === 'dict') return [];
  if ('_type' in value && value._type !== 'dict') return null;
  if (!('head' in value) || !('tail' in value)) return null;

  const pairs = [];
  let current = value;
  let steps = 0;
  const visited = new Set();

  while (true) {
    if (current === null || typeof current !== 'object' || Array.isArray(current)) return null;
    // Security hardening: reject cyclic structures to avoid infinite loops.
    if (visited.has(current)) return null;
    visited.add(current);
    if ('_type' in current && current._type !== 'dict') return null;
    if (!('head' in current) || !('tail' in current)) return null;

    const kv = current.head;
    if (kv === null || typeof kv !== 'object' || Array.isArray(kv)) return null;
    const kvKeys = Object.keys(kv);
    if (kvKeys.length !== 2 || !('head' in kv) || !('tail' in kv)) return null;
    const key = kv.head;
    if (typeof key !== 'string') return null;

    const kvTail = kv.tail;
    if (kvTail === null || typeof kvTail !== 'object' || Array.isArray(kvTail)) return null;
    const kvTailKeys = Object.keys(kvTail);
    if (kvTailKeys.length !== 2 || !('head' in kvTail) || !('tail' in kvTail)) return null;
    if (kvTail.tail !== null) return null;

    pairs.push([key, kvTail.head]);
    if (current.tail === null) break;
    current = current.tail;
    steps++;
    // Parity with Python _iter_normalized_dict_pairs: both substrates process
    // exactly MAX_MU_WIDTH pairs max. Python increments steps at loop top
    // and checks steps > MAX_MU_WIDTH; JS increments after push and checks
    // steps >= MAX_MU_WIDTH. Both return null when a (MAX_MU_WIDTH+1)th pair
    // would be processed. W3-CRASH F-13: raised from 100 to MAX_MU_WIDTH.
    if (steps >= MAX_MU_WIDTH) return null;
  }
  return pairs;
}

/**
 * Check whether value appears to be a normalized dict encoding candidate.
 *
 * Conservative heuristic: explicit {_type:"dict"} or head/tail with kv-like head.
 * If candidate parsing fails, validators should fail closed.
 */
function looksLikeNormalizedDictCandidate(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  if (value._type === 'dict') {
    const keySet = new Set(keys);
    if (
      !(keySet.size === 1 && keySet.has('_type')) &&
      !(keySet.size === 3 && keySet.has('_type') && keySet.has('head') && keySet.has('tail'))
    ) {
      return false;
    }
    return true;
  }
  const keySet = new Set(keys);
  if (!(keySet.size === 2 && keySet.has('head') && keySet.has('tail'))) return false;
  const kv = value.head;
  if (kv === null || typeof kv !== 'object' || Array.isArray(kv)) return false;
  const kvKeys = Object.keys(kv);
  if (kvKeys.length !== 2 || !('head' in kv) || !('tail' in kv)) return false;
  if (typeof kv.head !== 'string') return false;
  const kvTail = kv.tail;
  if (kvTail === null || typeof kvTail !== 'object' || Array.isArray(kvTail)) return false;
  const kvTailKeys = Object.keys(kvTail);
  if (kvTailKeys.length !== 2 || !('head' in kvTail) || !('tail' in kvTail)) return false;
  return value.tail === null || (typeof value.tail === 'object' && !Array.isArray(value.tail));
}

/**
 * Walk a Mu value tree and validate keys via keyChecker callback.
 * Shared traversal for validateNoKernelReservedFields and
 * validateAlgorithmRuntimeFields (mirrors Python _walk_and_validate).
 */
function _walkAndValidate(value, keyChecker, context, _depth = 0) {
  if (_depth > MAX_VALIDATION_DEPTH) {
    throw new Error(
      `SECURITY: ${context} exceeded maximum validation depth (${MAX_VALIDATION_DEPTH}). ` +
      `Possible deeply nested attack structure. Failing closed.`
    );
  }

  if (value === null || typeof value !== 'object') {
    return;
  }

  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      _walkAndValidate(value[i], keyChecker, `${context}[${i}]`, _depth + 1);
    }
    return;
  }

  const dictPairs = iterNormalizedDictPairs(value);
  if (dictPairs !== null) {
    for (const [key, val] of dictPairs) {
      const err = keyChecker(key);
      if (err) {
        throw new RcxError('input.reserved_field', `SECURITY: ${context} ${err}`);
      }
      _walkAndValidate(val, keyChecker, `${context}.${key}`, _depth + 1);
    }
    return;
  }
  if (looksLikeNormalizedDictCandidate(value)) {
    throw new RcxError(
      'input.reserved_field',
      `SECURITY: Malformed normalized dict encoding at ${context}. Failing closed to prevent reserved-field bypass.`
    );
  }

  for (const [key, val] of Object.entries(value)) {
    const err = keyChecker(key);
    if (err) {
      throw new RcxError('input.reserved_field', `SECURITY: ${context} ${err}`);
    }
    _walkAndValidate(val, keyChecker, `${context}.${key}`, _depth + 1);
  }
}

function _checkKernelReserved(key) {
  if (KERNEL_RESERVED_FIELDS.has(key)) {
    return `contains kernel-reserved field '${key}'. Reserved fields are not allowed in domain input.`;
  }
  return null;
}

function _checkAlgorithmRuntime(key) {
  if (typeof key === 'string' && key.startsWith('_')) {
    if (!ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS.has(key)) {
      return (
        `contains unsupported algorithm underscore field: ${key}. ` +
        `Allowed: ${Array.from(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS).sort().join(', ')}`
      );
    }
  }
  return null;
}

/**
 * Validate that a value does not contain kernel-reserved fields.
 * Deep recursive check with depth guard (fail closed).
 * Matches Python step_mu.py:validate_no_kernel_reserved_fields()
 */
function validateNoKernelReservedFields(value, context = 'input', _depth = 0) {
  _walkAndValidate(value, _checkKernelReserved, context, _depth);
}

/**
 * Validate trusted algorithm runtime state at kernel entry.
 * Mirrors Python validate_algorithm_runtime_fields():
 * - unknown underscore fields are rejected (fail closed)
 * - underscore keys inside normalized dict encodings are validated
 */
function validateAlgorithmRuntimeFields(value, context = 'input', _depth = 0) {
  _walkAndValidate(value, _checkAlgorithmRuntime, context, _depth);
}

/**
 * Check if pattern has non-linear variables (same var name appears twice).
 * Fail-closed guard: stepKernel/runStructural use core kernel which does NOT
 * detect binding conflicts. Non-linear patterns must use runAlgorithmWithBridge.
 *
 * Bounded: iteration counter (MAX_DEPTH * MAX_MU_WIDTH) and identity-based
 * cycle detection prevent OOM on circular references or pathologically deep inputs.
 * Mirrors Python _has_nonlinear_vars() in step_mu.py.
 */
function hasNonlinearVars(pattern) {
  const varCounts = Object.create(null);
  const maxIterations = MAX_DEPTH * MAX_MU_WIDTH; // 300 * 1000 = 300,000
  const seen = new Set();
  let iterations = 0;

  const stack = [pattern];
  while (stack.length > 0) {
    iterations++;
    if (iterations > maxIterations) {
      // Fail-closed: pathological input, treat as non-linear.
      return true;
    }
    const current = stack.pop();
    if (current === null || typeof current !== 'object') continue;
    if (seen.has(current)) continue;

    if (Array.isArray(current)) {
      seen.add(current);
      for (let i = 0; i < current.length; i++) {
        stack.push(current[i]);
      }
    } else {
      seen.add(current);
      const keys = Object.keys(current);
      if (keys.length === 1 && keys[0] === 'var' && typeof current.var === 'string') {
        const name = current.var;
        varCounts[name] = (varCounts[name] || 0) + 1;
      } else {
        for (let i = 0; i < keys.length; i++) {
          stack.push(current[keys[i]]);
        }
      }
    }
  }

  for (const name in varCounts) {
    if (varCounts[name] > 1) return true;
  }
  return false;
}

/**
 * Fail-closed: reject projections with non-linear patterns on core kernel path.
 *
 * Core kernel (match.v2 without bridge) silently overwrites bindings when the
 * same variable appears twice in a pattern. This produces wrong results for
 * conflicting bindings instead of NO_MATCH.
 *
 * Mirrors Python _reject_nonlinear_projections() in step_mu.py.
 *
 * @param {Array} projections - Domain projections to check.
 * @param {string} caller - Name of calling function (for error messages).
 * @throws {RcxError} If any projection has non-linear patterns.
 */
function rejectNonlinearProjections(projections, caller) {
  for (let i = 0; i < projections.length; i++) {
    const proj = projections[i];
    if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) continue;
    const pattern = proj.pattern;
    if (pattern !== undefined && hasNonlinearVars(pattern)) {
      const projId = (typeof proj.id === 'string') ? proj.id : `projection[${i}]`;
      throw new RcxError(
        'input.nonlinear_pattern',
        `${caller}: projection '${projId}' has non-linear pattern ` +
        `(same variable appears twice). Core kernel does not detect ` +
        `binding conflicts. Use runAlgorithmWithBridge() instead.`
      );
    }
  }
}

module.exports = {
  iterNormalizedDictPairs,
  looksLikeNormalizedDictCandidate,
  validateNoKernelReservedFields,
  validateAlgorithmRuntimeFields,
  hasNonlinearVars,
  rejectNonlinearProjections,
};
