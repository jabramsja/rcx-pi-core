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
const { isVar, isValidMu, muHashCached, muHashControlCached, _NO_BUDGET, consumeBudget } = require('./types');
const muContainers = require('./container_factory');
const { normalize, denormalize } = require('./normalize');
const { assertNotLambdaCalculus } = require('./security');

/**
 * BOUNDARY: match() is OFF the kernel execution path (Wave H onward).
 * Kernel path: stepKernel → _stepTrusted → applyProjection → stage0Match.
 * match() is only called by the public API, not by the kernel.
 * Reclassified P7W4: was host recursion debt, now BOUNDARY.
 */
function match(pattern, input, _depth = 0, _validated = false, _budget = _NO_BUDGET) {
  // --- Structural budget path (opt-in) ---
  if (_budget !== _NO_BUDGET) {
    if (_depth === 0 && !_validated) {
      if (!isValidMu(pattern)) {
        throw new RcxError('input.invalid_type', 'Invalid Mu pattern in match()');
      }
      if (!isValidMu(input)) {
        throw new RcxError('input.invalid_type', 'Invalid Mu input in match()');
      }
    }

    const [ok, remaining] = consumeBudget(_budget);
    if (!ok) return NO_MATCH;

    if (isVar(pattern)) {
      if (!pattern.var) return NO_MATCH;
      return { [pattern.var]: input };
    }
    if (pattern === null) return input === null ? {} : NO_MATCH;
    if (typeof pattern !== 'object') return pattern === input ? {} : NO_MATCH;

    if (Array.isArray(pattern)) {
      if (!Array.isArray(input) || pattern.length !== input.length) return NO_MATCH;
      const bindings = Object.create(null);
      for (let i = 0; i < pattern.length; i++) {
        const sub = match(pattern[i], input[i], _depth, true, remaining);
        if (sub === NO_MATCH) return NO_MATCH;
        for (const [k, v] of Object.entries(sub)) {
          if (Object.hasOwn(bindings, k) && muHashCached(bindings[k]) !== muHashCached(v)) return NO_MATCH;
          bindings[k] = v;
        }
      }
      return bindings;
    }

    if (typeof pattern === 'object') {
      if (typeof input !== 'object' || input === null || Array.isArray(input)) return NO_MATCH;
      const pKeys = new Set(Object.keys(pattern));
      const iKeys = new Set(Object.keys(input));
      if (pKeys.size !== iKeys.size) {
        const inputExtra = [...iKeys].filter(k => !pKeys.has(k));
        const patternExtra = [...pKeys].filter(k => !iKeys.has(k));
        const typeIsList = (input._type === 'list');
        if (!(inputExtra.length === 1 && inputExtra[0] === '_type' && patternExtra.length === 0 && typeIsList)) return NO_MATCH;
      } else {
        for (const k of pKeys) { if (!iKeys.has(k)) return NO_MATCH; }
      }
      const bindings = Object.create(null);
      for (const k of pKeys) {
        const sub = match(pattern[k], input[k], _depth, true, remaining);
        if (sub === NO_MATCH) return NO_MATCH;
        for (const [bk, bv] of Object.entries(sub)) {
          if (Object.hasOwn(bindings, bk) && muHashCached(bindings[bk]) !== muHashCached(bv)) return NO_MATCH;
          bindings[bk] = bv;
        }
      }
      return bindings;
    }
    return NO_MATCH;
  }

  // --- Integer depth path (default — existing behavior, zero overhead) ---
  // Parity with Python _match_inner: depth overflow returns NO_MATCH (not throw).
  // This allows step() to try the next projection gracefully.
  if (_depth > MAX_DEPTH) {
    return NO_MATCH;
  }

  // Entry validation — validate once at depth 0, not on every recursive call.
  // _validated=true skips this (trusted callers already validated input).
  if (_depth === 0 && !_validated) {
    if (!isValidMu(pattern)) {
      throw new RcxError('input.invalid_type', 'Invalid Mu pattern in match()');
    }
    if (!isValidMu(input)) {
      throw new RcxError('input.invalid_type', 'Invalid Mu input in match()');
    }
  }

  // Gate 3: Auto-normalize input when pattern uses normalized dict format.
  if (_depth === 0 && !_validated && typeof pattern === 'object' && pattern !== null &&
      !Array.isArray(pattern) && pattern._type === 'dict') {
    input = normalize(input);
  }

  if (isVar(pattern)) {
    if (!pattern.var) return NO_MATCH;  // F-25: parity with Python _match_inner:269-270
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
        // Non-linear conflict: use content hash, not control hash. Conflict
        // detection compares structural data identity; numeric leaves on the
        // Stage 4 path are StructuralNumbers numerals, not host numbers.
        if (Object.hasOwn(bindings, k) && muHashCached(bindings[k]) !== muHashCached(v)) {
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
        // Non-linear conflict: use content hash, not control hash. Conflict
        // detection compares structural data identity; numeric leaves on the
        // Stage 4 path are StructuralNumbers numerals, not host numbers.
        if (Object.hasOwn(bindings, bk) && muHashCached(bindings[bk]) !== muHashCached(bv)) {
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
 * BOUNDARY: substitute() is OFF the kernel execution path (Wave H onward).
 * Kernel path: stepKernel → _stepTrusted → applyProjection → stage0Substitute.
 * substitute() is only called by the public API, not by the kernel.
 * Reclassified P7W4: was host recursion debt, now BOUNDARY.
 */
function substitute(body, bindings, _depth = 0, _budget = _NO_BUDGET) {
  // --- Structural budget path (opt-in) ---
  if (_budget !== _NO_BUDGET) {
    const [ok, remaining] = consumeBudget(_budget);
    if (!ok) throw new Error('Structural depth budget exhausted in substitute');

    if (_depth === 0) {
      if (!isValidMu(body)) {
        throw new RcxError('input.invalid_type', 'Invalid Mu body in substitute()');
      }
    }

    if (isVar(body)) {
      const name = body.var;
      if (!Object.hasOwn(bindings, name)) throw new Error(`Unbound variable: ${name}`);
      return bindings[name];
    }
    if (body === null || typeof body !== 'object') return body;
    if (Array.isArray(body)) {
      return muContainers.list(body.map(elem => substitute(elem, bindings, _depth, remaining)));
    }
    const result = muContainers.record();
    for (const [k, v] of Object.entries(body)) {
      result[k] = substitute(v, bindings, _depth, remaining);
    }
    return result;
  }

  // --- Integer depth path (default — existing behavior, zero overhead) ---
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded in substitute (${MAX_DEPTH})`);
  }

  // Entry validation — validate once at depth 0, not on every recursive call.
  if (_depth === 0) {
    if (!isValidMu(body)) {
      throw new RcxError('input.invalid_type', 'Invalid Mu body in substitute()');
    }
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
    return muContainers.list(body.map(elem => substitute(elem, bindings, _depth + 1)));
  }

  const result = muContainers.record();
  for (const [k, v] of Object.entries(body)) {
    result[k] = substitute(v, bindings, _depth + 1);
  }
  return result;
}

/**
 * Apply a single projection to input.
 */
function applyProjection(projection, input) {
  // Parity with Python apply_projection: validate projection + input + lambda-calc guard
  if (!isValidMu(projection) || typeof projection !== 'object' || projection === null || Array.isArray(projection))
    throw new RcxError('input.invalid_type', 'Projection must be a valid Mu object');
  if (!('pattern' in projection) || !('body' in projection))
    throw new RcxError('input.invalid_type', "Projection must have 'pattern' and 'body' keys");
  if (!isValidMu(input))
    throw new RcxError('input.invalid_type', 'Invalid Mu input in applyProjection()');
  assertNotLambdaCalculus(projection);

  // Gate 3: Auto-normalize input when pattern uses normalized dict format.
  // stage0Match does not auto-normalize; do it here (parity with Python).
  let inputVal = input;
  if (typeof projection.pattern === 'object' && projection.pattern !== null &&
      !Array.isArray(projection.pattern) && projection.pattern._type === 'dict') {
    inputVal = normalize(inputVal);
  }
  const bindings = stage0Match(projection.pattern, inputVal);
  if (bindings === NO_MATCH) {
    return NO_MATCH;
  }
  let result = stage0Substitute(projection.body, bindings);

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
 * BOUNDARY: projection scan used by bootstrap helpers; tracked iteration lives
 * on the active engine kernel driver loop.
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
 * Internal: apply projection without validating input.
 * ONLY for use by kernel loops that have already validated at the boundary.
 * Matches Python _apply_projection_trusted() parity.
 */
function _applyProjectionTrusted(projection, input) {
  const pattern = projection.pattern;
  let inputVal = input;

  // Gate 3: auto-normalize input when pattern uses _type:"dict" (parity with Python)
  if (typeof pattern === 'object' && pattern !== null &&
      !Array.isArray(pattern) && pattern._type === 'dict') {
    inputVal = normalize(inputVal);
  }

  // Stage 0 match — sole production path (parity with Python, flag removed Wave 9).
  const bindings = stage0Match(pattern, inputVal);
  if (bindings === NO_MATCH) return NO_MATCH;
  // Stage 0 substitute — body validation fine (seeds verified at load time).
  let result = stage0Substitute(projection.body, bindings);
  if (typeof projection.body === 'object' && projection.body !== null &&
      !Array.isArray(projection.body) && projection.body._type === 'dict') {
    result = denormalize(result);
  }
  return result;
}

/**
 * Internal: step without validating input.
 * ONLY for use by kernel loops that have already validated at the boundary.
 * Matches Python _step_trusted() parity.
 */
function _stepTrusted(projections, input) {
  for (const proj of projections) {
    const result = _applyProjectionTrusted(proj, input);
    if (result !== NO_MATCH) return result;
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
  return muContainers.record([['_undefined', true], ['op', op], ['lhs_hash', safeHash(lhs)], ['rhs_hash', safeHash(rhs)], ['cause', cause], ['details', details]]);
}

/**
 * BOOTSTRAP_PRIMITIVE: max_steps (termination guard)
 * Run projections until fixpoint (stall or max steps).
 * Single-pass: each step matches + applies in one loop (N6 fix).
 *
 * BOUNDARY: Outer loop scaffolding — NOT on the kernel execution path.
 * Reclassified P7W5: was host iteration marker, now BOUNDARY.
 */
const MAX_RUN_STEPS = 10000; // Hard cap — prevents unbounded trace accumulation

function run(projections, input, maxSteps = MAX_RUN_STEPS) {
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to run()');
  }
  if (typeof maxSteps !== 'number' || maxSteps < 0 || maxSteps > MAX_RUN_STEPS) {
    maxSteps = MAX_RUN_STEPS;
  }
  // Validate projections up front (public boundary parity with applyProjection)
  for (const proj of projections) {
    if (!isValidMu(proj) || typeof proj !== 'object' || proj === null || Array.isArray(proj))
      throw new RcxError('input.invalid_type', 'Projection must be a valid Mu object');
    if (!('pattern' in proj) || !('body' in proj))
      throw new RcxError('input.invalid_type', "Projection must have 'pattern' and 'body' keys");
    assertNotLambdaCalculus(proj);
  }

  let current = input;
  let currentHash = muHashControlCached(input, 'run');
  const trace = muContainers.list();
  for (let i = 0; i < maxSteps; i++) {
    let matchedId = null;
    let next = current;
    for (const proj of projections) {
      const result = _applyProjectionTrusted(proj, current);
      if (result !== NO_MATCH) {
        matchedId = proj.id ?? 'unknown';
        next = result;
        break;
      }
    }

    trace.push(muContainers.record([['step', i], ['projection', matchedId], ['state', current]]));

    const nextHash = muHashControlCached(next, 'run.stall');
    if (nextHash === currentHash) {
      return muContainers.record([['result', current], ['steps', i], ['stalled', true], ['trace', trace]]);
    }
    current = next;
    currentHash = nextHash;
  }
  return muContainers.record([['result', current], ['steps', maxSteps], ['stalled', false], ['trace', trace]]);
}

// ---------------------------------------------------------------------------
// Stage 0 micro-kernel (D005 — sole production path since Wave H 2026-03-11)
// Worklist match + substitute. Flag removed Wave 9 (parity with Python).
// See L4DecisionCard.v0.md D005.
// ---------------------------------------------------------------------------

/**
 * Stage 0 match: pure merge, explicit worklist. Returns NO_MATCH on failure.
 * Traversal is worklist-based; there are no self-recursive calls.
 * P7W4: Array branch removed (dead code — all kernel inputs normalized to head/tail).
 */
function stage0Match(pattern, input, bindings, _depth = 0) {
  let current = bindings ?? Object.create(null);
  const work = [{ pattern, input, depth: _depth }];
  while (work.length > 0) {
    const frame = work.pop();
    pattern = frame.pattern; input = frame.input;
    const depth = frame.depth;
    if (depth > MAX_DEPTH) return NO_MATCH;

    // Stage 4 StructuralNumbers cutover: host numeric leaves are no longer
    // matcher-domain data. A stray number fails closed before it can bind
    // through a variable site or match through content-hash equality.
    if (typeof pattern === 'number' || typeof input === 'number') return NO_MATCH;

    // Variable site
    if (isVar(pattern)) {
      const name = pattern.var;
      if (!name) return NO_MATCH;  // F-25: parity with Python _stage0_match
      const seen = new WeakSet(), pending = [[input, 0]]; while (pending.length) {  // AST_OK_JS: path-local cycle detection for fail-closed Stage 4 matcher scan
        const [candidate, exit] = pending.pop(); if (typeof candidate === 'number') return NO_MATCH;
        if (candidate !== null && typeof candidate === 'object') { if (exit) { seen.delete(candidate); continue; } if (seen.has(candidate)) return NO_MATCH;
          seen.add(candidate); pending.push([candidate, 1]); for (const v of (Array.isArray(candidate) ? candidate : Object.values(candidate))) pending.push([v, 0]); }
      }
      if (Object.hasOwn(current, name)) {
        // Non-linear conflict: use content hash, not control hash. Conflict
        // detection compares structural data identity; numeric leaves on the
        // Stage 4 path are StructuralNumbers numerals, not host numbers.
        if (muHashCached(current[name]) !== muHashCached(input)) return NO_MATCH;
      } else current = Object.assign(Object.create(null), current, { [name]: input });
      continue;
    }

    // Null
    if (pattern === null) { if (input !== null) return NO_MATCH; continue; }

    // Non-numeric primitives: content-addressed equality collapses the
    // remaining bool/string scalar dispatch into one muHashCached comparison
    // (parity with Python _stage0_match).
    // The isValidMu validity guard keeps invalid/non-Mu values (raw arrays,
    // undefined) from reaching muHashCached (which throws on non-valid-Mu) —
    // they fall through to NO_MATCH.
    if (typeof pattern !== 'object') {
      if (isValidMu(pattern) && isValidMu(input) && muHashCached(pattern) === muHashCached(input)) continue;
      return NO_MATCH;
    }

    // Array branch REMOVED (P7W4): After normalization, all arrays become head/tail
    // linked lists (objects). No kernel-path code passes raw JS arrays to stage0Match.
    // Verified: zero seed patterns/bodies contain raw arrays.
    // If a raw array reaches here, it falls through to the object branch or NO_MATCH.

    // Object (Gate-3: allow pattern to omit _type when input has _type="list")
    if (typeof pattern === 'object') {
      if (typeof input !== 'object' || input === null || Array.isArray(input)) return NO_MATCH;
      const pKeys = Object.keys(pattern), iKeys = Object.keys(input), iKeySet = new Set(iKeys);
      if (pKeys.length !== iKeys.length) {
        const pKeySet = new Set(pKeys), inputExtra = iKeys.filter(k => !pKeySet.has(k));
        const patternExtra = pKeys.filter(k => !iKeySet.has(k)), typeIsList = (input._type === 'list');
        if (!(inputExtra.length === 1 && inputExtra[0] === '_type' && patternExtra.length === 0 && typeIsList)) return NO_MATCH;
      } else {
        for (const k of pKeys) if (!iKeySet.has(k)) return NO_MATCH;
      }
      for (let i = pKeys.length - 1; i >= 0; i--) {
        const k = pKeys[i]; work.push({ pattern: pattern[k], input: input[k], depth: depth + 1 });
      }
      continue;
    }
    return NO_MATCH;
  }
  return current;
}

/**
 * Stage 0 substitute: explicit worklist tree walk. Throws on unbound variable.
 * Traversal is worklist-based; there are no self-recursive calls.
 */
function stage0Substitute(body, bindings, _depth = 0) {
  const values = [], work = [{ op: 'eval', value: body, depth: _depth }];
  while (work.length > 0) {
    const frame = work.pop();
    if (frame.op === 'list') {
      const start = values.length - frame.count, items = values.slice(start);
      values.length = start; values.push(muContainers.list(items));
      continue;
    }
    if (frame.op === 'record') {
      const start = values.length - frame.keys.length, result = muContainers.record();
      for (let i = 0; i < frame.keys.length; i++) result[frame.keys[i]] = values[start + i];
      values.length = start; values.push(result);
      continue;
    }
    const value = frame.value, depth = frame.depth;
    if (depth > MAX_DEPTH) throw new Error(`Stage 0 substitute depth exceeded ${MAX_DEPTH}`);
    if (value === null || typeof value !== 'object') {
      values.push(value);
      continue;
    }
    if (isVar(value)) {
      const name = value.var;
      if (!Object.hasOwn(bindings, name)) {
        throw new Error(`Unbound variable: ${name}`);
      }
      values.push(bindings[name]);
      continue;
    }
    if (Array.isArray(value)) {
      work.push({ op: 'list', count: value.length });
      for (let i = value.length - 1; i >= 0; i--) work.push({ op: 'eval', value: value[i], depth: depth + 1 });
      continue;
    }
    const entries = Object.entries(value);
    work.push({ op: 'record', keys: entries.map(([k]) => k) });
    for (let i = entries.length - 1; i >= 0; i--) work.push({ op: 'eval', value: entries[i][1], depth: depth + 1 });
  }
  return values.pop();
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
  stage0Match,
  stage0Substitute,
  _applyProjectionTrusted,
  _stepTrusted,
};
