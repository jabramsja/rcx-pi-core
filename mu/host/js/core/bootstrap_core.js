'use strict';
/**
 * RCX Bootstrap Core — Irreducible TCB
 *
 * Contains ONLY the irreducible evaluation primitives:
 *   match, substitute, applyProjection, step, run
 * Plus helpers: isKernelTerminal, isKernelIntermediate, makeUndefinedMotif
 *
 * Budget: ≤400 non-blank non-comment lines (gate-enforced).
 *
 * Depends on: core/constants.js, core/types.js, core/normalize.js, core/security.js
 */

const { MAX_DEPTH, NO_MATCH, RcxError } = require('./constants');
const { isVar, isValidMu, muHashCached, muHashControlCached } = require('./types');
const { normalize, denormalize } = require('./normalize');

/**
 * @host_recursion — recursive pattern matching
 * (host debt, not a bootstrap primitive)
 *
 * Match pattern against input, returning bindings or NO_MATCH.
 */
function match(pattern, input, _depth = 0) {
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded in match (${MAX_DEPTH})`);
  }

  // Gate 3: Auto-normalize input when pattern uses normalized dict format.
  if (_depth === 0 && typeof pattern === 'object' && pattern !== null &&
      !Array.isArray(pattern) && pattern._type === 'dict') {
    input = normalize(input);
  }

  if (isVar(pattern)) {
    return { [pattern.var]: input };
  }

  if (pattern === null) {
    return input === null ? {} : NO_MATCH;
  }

  if (typeof pattern !== 'object') {
    return pattern === input ? {} : NO_MATCH;
  }

  if (Array.isArray(pattern)) {
    if (!Array.isArray(input) || pattern.length !== input.length) {
      return NO_MATCH;
    }
    const bindings = Object.create(null);
    for (let i = 0; i < pattern.length; i++) {
      const sub = match(pattern[i], input[i], _depth + 1);
      if (sub === NO_MATCH) return NO_MATCH;
      for (const [k, v] of Object.entries(sub)) {
        if (Object.hasOwn(bindings, k) && muHashControlCached(bindings[k]) !== muHashControlCached(v)) {
          return NO_MATCH;
        }
        bindings[k] = v;
      }
    }
    return bindings;
  }

  if (typeof pattern === 'object') {
    if (typeof input !== 'object' || input === null || Array.isArray(input)) {
      return NO_MATCH;
    }
    const pKeys = new Set(Object.keys(pattern));
    const iKeys = new Set(Object.keys(input));

    // Gate 3: Allow pattern to omit _type key while input has it (list only).
    if (pKeys.size !== iKeys.size) {
      const inputExtra = [...iKeys].filter(k => !pKeys.has(k));
      const patternExtra = [...pKeys].filter(k => !iKeys.has(k));
      const typeIsList = (input._type === 'list');
      if (!(inputExtra.length === 1 && inputExtra[0] === '_type' && patternExtra.length === 0 && typeIsList)) {
        return NO_MATCH;
      }
    } else {
      for (const k of pKeys) {
        if (!iKeys.has(k)) return NO_MATCH;
      }
    }
    const bindings = Object.create(null);
    for (const k of pKeys) {
      const sub = match(pattern[k], input[k], _depth + 1);
      if (sub === NO_MATCH) return NO_MATCH;
      for (const [bk, bv] of Object.entries(sub)) {
        if (Object.hasOwn(bindings, bk) && muHashControlCached(bindings[bk]) !== muHashControlCached(bv)) {
          return NO_MATCH;
        }
        bindings[bk] = bv;
      }
    }
    return bindings;
  }

  return NO_MATCH;
}

/**
 * @host_recursion — recursive substitution
 * (host debt, not a bootstrap primitive)
 *
 * Substitute variable sites in body with bound values.
 */
function substitute(body, bindings, _depth = 0) {
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded in substitute (${MAX_DEPTH})`);
  }

  if (isVar(body)) {
    const name = body.var;
    if (!Object.hasOwn(bindings, name)) {
      throw new Error(`Unbound variable: ${name}`);
    }
    return bindings[name];
  }

  if (body === null || typeof body !== 'object') {
    return body;
  }

  if (Array.isArray(body)) {
    return body.map(elem => substitute(elem, bindings, _depth + 1));
  }

  const result = Object.create(null);
  for (const [k, v] of Object.entries(body)) {
    result[k] = substitute(v, bindings, _depth + 1);
  }
  return result;
}

/**
 * Apply a single projection to input.
 */
function applyProjection(projection, input) {
  const bindings = match(projection.pattern, input);
  if (bindings === NO_MATCH) {
    return NO_MATCH;
  }
  let result = substitute(projection.body, bindings);

  // Gate 3: Auto-denormalize output when body uses normalized dict format.
  if (typeof projection.body === 'object' && projection.body !== null &&
      !Array.isArray(projection.body) && projection.body._type === 'dict') {
    result = denormalize(result);
  }

  return result;
}

/**
 * BOOTSTRAP_PRIMITIVE: eval_step
 * Apply first matching projection.
 * This is the irreducible core — analogous to Forth's NEXT.
 *
 * @host_iteration — for loop over projections (first-match-wins)
 */
function step(projections, input) {
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to step()');
  }

  for (const proj of projections) {
    const result = applyProjection(proj, input);
    if (result !== NO_MATCH) {
      return result;
    }
  }
  return input;
}

/**
 * Check if result is a kernel terminal state {_mode:"done", _result:..., _stall:...}.
 * Parity with Python is_kernel_terminal() in step_mu.py.
 */
function isKernelTerminal(result) {
  return typeof result === 'object' && result !== null &&
    result._mode === 'done' && Object.hasOwn(result, '_result') && Object.hasOwn(result, '_stall');
}

/**
 * Check if result is an intermediate kernel state (mid-execution).
 * Parity with Python is_kernel_intermediate() in step_mu.py.
 */
function isKernelIntermediate(result) {
  if (result === null || typeof result !== 'object' || Array.isArray(result)) return false;
  if (Object.hasOwn(result, '_subst_ctx') || Object.hasOwn(result, '_match_ctx') || Object.hasOwn(result, '_kernel_ctx')) return true;
  if (Object.hasOwn(result, '_mode') && result._mode !== 'done') return true;
  return false;
}

/**
 * Create a canonical undefined-result motif (NorthStarSemantics.v0.md Section A).
 * Parity with Python make_undefined_motif() in step_mu.py.
 */
function makeUndefinedMotif(op, lhs, rhs, cause, details = null) {
  function safeHash(value) {
    if (value === null || value === undefined) return null;
    try { return muHashCached(value); }
    catch (_e) { return null; }
  }
  return {
    _undefined: true,
    op: op,
    lhs_hash: safeHash(lhs),
    rhs_hash: safeHash(rhs),
    cause: cause,
    details: details,
  };
}

/**
 * BOOTSTRAP_PRIMITIVE: max_steps (termination guard)
 * Run projections until fixpoint (stall or max steps).
 *
 * @host_iteration — for loop until stall/max_steps
 */
const MAX_RUN_STEPS = 10000; // Hard cap — prevents unbounded trace accumulation

function run(projections, input, maxSteps = MAX_RUN_STEPS) {
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to run()');
  }
  if (typeof maxSteps !== 'number' || maxSteps < 0 || maxSteps > MAX_RUN_STEPS) {
    maxSteps = MAX_RUN_STEPS;
  }

  let current = input;
  let currentHash = muHashControlCached(input, 'run');
  const trace = [];

  for (let i = 0; i < maxSteps; i++) {
    let matchedId = null;
    for (const proj of projections) {
      if (match(proj.pattern, current) !== NO_MATCH) {
        matchedId = proj.id ?? 'unknown';
        break;
      }
    }

    trace.push({ step: i, projection: matchedId, state: current });

    const next = step(projections, current);

    const nextHash = muHashControlCached(next, 'run.stall');
    if (nextHash === currentHash) {
      return { result: current, steps: i, stalled: true, trace };
    }
    current = next;
    currentHash = nextHash;
  }
  return { result: current, steps: maxSteps, stalled: false, trace };
}

module.exports = {
  match,
  substitute,
  applyProjection,
  step,
  run,
  isKernelTerminal,
  isKernelIntermediate,
  makeUndefinedMotif,
  NO_MATCH,
};
