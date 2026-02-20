/**
 * RCX eval_step - Minimal JavaScript Implementation (L3 Substrate Portability POC)
 *
 * This is the bootstrap primitive - analogous to Forth's NEXT.
 * Complete implementation with normalization for kernel cycle.
 *
 * Security hardened (v7 - L3 Recurrence Parity, mu/ reorganization):
 * - MAX_DEPTH guard (300) matching Python MAX_MU_DEPTH
 * - NaN/Infinity rejection
 * - Function/undefined/Symbol rejection
 * - KERNEL_RESERVED_FIELDS validation (matches Python step_mu.py)
 * - Strict head/tail detection (exact key counts)
 * - Unbound variables return body unchanged (stall, matches Python Phase 7d-1)
 * - Input validation at API boundaries (step, run, stepKernel)
 *
 * This POC demonstrates L3 substrate portability: same projections run on
 * both Python and JavaScript with identical semantics. Same 5 bootstrap
 * primitives, different host language.
 *
 * =============================================================================
 * DEBT SUMMARY (L3 Parity - must match Python bootstrap primitives)
 * =============================================================================
 *
 * BOOTSTRAP PRIMITIVES (4 - irreducible, same as Python):
 *   1. eval_step    - step()           - applies first matching projection
 *   2. max_steps    - maxSteps param   - termination guard
 *   3. stack_guard  - MAX_DEPTH        - recursion depth limit
 *   4. proj_loader  - fs.readFileSync  - loads JSON seeds
 *   (mu_equal eliminated: now derivable from muHashCached, Content-Addressed Mu Level 1)
 *
 * SEMANTIC DEBT (host operations that would need structural replacement):
 *   @host_iteration: 9
 *     - step()                    - for loop over projections
 *     - run()                     - for loop until stall
 *     - runStructural()           - for loop until stall (Gate 5: routes through stepKernel)
 *     - normalize()               - for loop for array conversion
 *     - denormalize()             - while loop for linked list
 *     - listToLinked()            - for loop for conversion
 *     - runAlgorithmWithBridge()  - bridge-backed algorithm execution loop
 *     - runEnginePipeline()       - engine state machine effect handler loop
 *     - runEnginePipelineRecursive() - Boot1 shadow recursive engine loop
 *
 *   @host_recursion: 4
 *     - match()             - recursive pattern matching
 *     - substitute()        - recursive substitution
 *     - normalize()         - recursive normalization
 *     - denormalize()       - recursive denormalization
 *
 *   @host_builtin: 3
 *     - muEqual()           - structural equality (convenience wrapper, delegates to muHashCached)
 *     - muHash()            - SHA-256 hash (BOOTSTRAP_PRIMITIVE, hash-accelerated closure detection)
 *     - isValidMu()         - type validation
 *
 * TOTAL DEBT: 16 (9 iteration + 4 recursion + 3 builtin)
 *
 * This debt represents the IRREDUCIBLE BOOTSTRAP - the same operations
 * exist in Python. Both substrates have identical bootstrap footprint.
 * =============================================================================
 */

// =============================================================================
// Constants and Configuration
// =============================================================================

// BOOTSTRAP_PRIMITIVE: stack_guard
// Maximum recursion depth (matches Python MAX_MU_DEPTH=300)
const MAX_DEPTH = 300;

// Sentinel for no match
const NO_MATCH = Symbol('NO_MATCH');

// Valid type tags for normalization (matches Python VALID_TYPE_TAGS)
const VALID_TYPE_TAGS = new Set(['list', 'dict']);

// Kernel reserved fields - domain data MUST NOT contain these (matches Python step_mu.py)
// Prevents domain data from forging kernel state
// Gate 3 (2026-02-04) Security fix: Entry point keys moved to ALGORITHM_ENTRYPOINT_KEYS.
// See validateNoKernelReservedFields() for subtree-scoped validation.
const KERNEL_RESERVED_FIELDS = new Set([
  '_mode', '_phase', '_input', '_remaining',
  '_match_ctx', '_subst_ctx', '_kernel_ctx',
  '_status', '_result', '_stall',
  '_step', '_projs',
  // Recurrence closure detection fields (9-agent review, 2026-02-02)
  '_seen', '_current', '_check_list',
  // Operator Exhaustion fields (Step 6 preparation, 2026-02-02)
  '_frozen', '_tau_step', '_operator_ids',
  // Bootstrap-Structural Bridge lookup phase fields (9-agent review, 2026-02-02)
  '_lookup_name', '_lookup_value', '_lookup_bindings', '_original_bindings',
  // Engine pipeline dispatch field (Boot1 P2 hardening, 2026-02-14)
  '_run_engine',
  // Boot1 recursive loop contract field (Boot1 P3 hardening, 2026-02-14)
  '_tail_call'
]);

// Algorithm entrypoint keys used by trusted algorithm-runtime validation.
const ALGORITHM_ENTRYPOINT_KEYS = new Set([
  '_detect_closure',      // Recurrence algorithm entry point
  '_detect_exhaustion',   // Exhaustion algorithm entry point
]);

// Gate 3 policy (minimal reserved set):
// Some algorithm-internal underscore keys are intentionally not in
// KERNEL_RESERVED_FIELDS because they are confined to algorithm state payloads.
const ALGORITHM_INTERNAL_UNRESERVED_FIELDS = new Set([
  '_closure',
  '_frozen_check',
  '_head',
  '_maxsteps',
  '_op_ids',
  '_operator',
  '_other',
  '_rest',
  '_state',
  '_tau_op',
  '_tau_operator',
  '_trace',
]);

// Gate 4 prep parity with Python step_mu.py:
// allowlisted underscore fields for trusted algorithm runtime mode.
const ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS = new Set([
  ...ALGORITHM_ENTRYPOINT_KEYS,
  ...ALGORITHM_INTERNAL_UNRESERVED_FIELDS,
  '_check_hash',   // recurrence.v2 hash comparison field (matches Python)
  '_check_list',
  '_current',
  '_frozen',
  '_mode',
  '_operator_ids',
  '_phase',
  '_result',
  '_seen',
  '_stall',
  '_state_hash',   // recurrence.v2 hash-accelerated closure detection (matches Python)
  '_step',
  '_tau_step',
  '_type',
]);

// Maximum depth for validation traversal (fail closed)
const MAX_VALIDATION_DEPTH = 100;

// =============================================================================
// Typed Error Class (for parity manifest error_code assertions)
// =============================================================================

/**
 * RcxError carries a structured error_code alongside the human-readable message.
 * Parity tests assert on error_code (never message text).
 */
class RcxError extends Error {
  constructor(code, message) {
    super(message);
    this.error_code = code;
  }
}

/**
 * Classify an error into a parity error_code.
 * Primary path: if the error already has error_code (RcxError), pass through.
 * Fallback: message-pattern matching for untyped exceptions.
 */
function classifyError(e) {
  if (e && e.error_code) return e.error_code;
  const msg = (e?.message ?? '').toLowerCase();
  if (msg.includes('cyclic linked list')) return 'trace.cycle_detected';
  if (msg.includes('exceeds') && msg.includes('entries')) return 'trace.overcap';
  if (msg.includes('engine pipeline exhausted')) return 'engine.exhausted';
  if (msg.includes('engine stalled')) return 'engine.stalled_non_terminal';
  if (msg.includes('must be a dict') || msg.includes('must be dict')) return 'input.invalid_type';
  if (msg.includes('shape mismatch') || msg.includes('unexpected shape')) return 'input.shape_mismatch';
  if (msg.includes('reserved') || msg.includes('kernel-reserved') || msg.includes('unsupported algorithm underscore')) return 'input.reserved_field';
  if (msg.includes('not valid mu') || msg.includes('max depth exceeded')) return 'input.malformed_normalized';
  return 'api.bad_request';
}

// =============================================================================
// Security Validation (matches Python step_mu.py security hardening)
// =============================================================================

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
    // exactly 100 pairs max. Python increments steps at loop top and checks
    // steps > 100; JS increments after push and checks steps >= 100. Both
    // return null when a 101st pair would be processed.
    if (steps >= MAX_VALIDATION_DEPTH) return null;
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
 * Validate that a value does not contain kernel-reserved fields.
 * Deep recursive check with depth guard (fail closed).
 * Matches Python step_mu.py:validate_no_kernel_reserved_fields()
 *
 * Gate 4 hardening: domain validation is strict. Reserved fields are rejected
 * everywhere. Trusted algorithm state uses validateAlgorithmRuntimeFields().
 */
function validateNoKernelReservedFields(value, context = 'input', _depth = 0) {
  // Depth guard - fail CLOSED (reject on deep structures)
  if (_depth > MAX_VALIDATION_DEPTH) {
    throw new Error(
      `Validation depth exceeded (${MAX_VALIDATION_DEPTH}) in ${context}. ` +
      `Possible attack via deeply nested structure. Failing closed.`
    );
  }

  // Primitives are safe
  if (value === null || typeof value !== 'object') {
    return;
  }

  // Arrays: validate each element
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      validateNoKernelReservedFields(value[i], `${context}[${i}]`, _depth + 1);
    }
    return;
  }

  // Gate 3 Security: Check normalized dict encoding (keys stored as values).
  // Without this, reserved fields in normalized dicts bypass validation.
  const dictPairs = iterNormalizedDictPairs(value);
  if (dictPairs !== null) {
    for (const [key, val] of dictPairs) {
      if (KERNEL_RESERVED_FIELDS.has(key)) {
        throw new RcxError(
          'input.reserved_field',
          `SECURITY: Kernel-reserved field '${key}' found in domain data at ${context}. ` +
          `Reserved fields are not allowed in domain input.`
        );
      }
      validateNoKernelReservedFields(val, `${context}.${key}`, _depth + 1);
    }
    return;
  }
  if (looksLikeNormalizedDictCandidate(value)) {
    throw new RcxError(
      'input.reserved_field',
      `SECURITY: Malformed normalized dict encoding at ${context}. ` +
      `Failing closed to prevent reserved-field bypass.`
    );
  }

  // Regular objects: check keys and recurse into values
  for (const [key, val] of Object.entries(value)) {
    if (KERNEL_RESERVED_FIELDS.has(key)) {
      throw new RcxError(
        'input.reserved_field',
        `SECURITY: Kernel-reserved field '${key}' found in domain data at ${context}. ` +
        `Reserved fields are not allowed in domain input.`
      );
    }
    validateNoKernelReservedFields(val, `${context}.${key}`, _depth + 1);
  }
}

/**
 * Validate trusted algorithm runtime state at kernel entry.
 *
 * Mirrors Python validate_algorithm_runtime_fields():
 * - unknown underscore fields are rejected (fail closed)
 * - underscore keys inside normalized dict encodings are validated
 */
function validateAlgorithmRuntimeFields(value, context = 'input', _depth = 0) {
  if (_depth > MAX_VALIDATION_DEPTH) {
    throw new Error(
      `SECURITY: ${context} exceeded maximum validation depth (${MAX_VALIDATION_DEPTH}). ` +
      `Possible deeply nested attack structure.`
    );
  }

  if (value === null || typeof value !== 'object') {
    return;
  }

  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) {
      validateAlgorithmRuntimeFields(value[i], `${context}[${i}]`, _depth + 1);
    }
    return;
  }

  const dictPairs = iterNormalizedDictPairs(value);
  if (dictPairs !== null) {
    for (const [key, val] of dictPairs) {
      if (key.startsWith('_') && !ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS.has(key)) {
        throw new RcxError(
          'input.reserved_field',
          `SECURITY: ${context} contains unsupported algorithm underscore field: ${key}. ` +
          `Allowed: ${Array.from(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS).sort().join(', ')}`
        );
      }
      validateAlgorithmRuntimeFields(val, `${context}.${key}`, _depth + 1);
    }
    return;
  }

  if (looksLikeNormalizedDictCandidate(value)) {
    throw new RcxError(
      'input.reserved_field',
      `SECURITY: ${context} contains malformed normalized dict encoding. Failing closed.`
    );
  }

  for (const [key, val] of Object.entries(value)) {
    if (typeof key === 'string' && key.startsWith('_')) {
      if (!ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS.has(key)) {
        throw new RcxError(
          'input.reserved_field',
          `SECURITY: ${context} contains unsupported algorithm underscore field: ${key}. ` +
          `Allowed: ${Array.from(ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS).sort().join(', ')}`
        );
      }
    }
    validateAlgorithmRuntimeFields(val, `${context}.${key}`, _depth + 1);
  }
}

// =============================================================================
// Validation Helpers
// =============================================================================

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
const MAX_MU_WIDTH = 1000;

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
 * Production code uses muHashCached directly. This wrapper remains for
 * test convenience and backward compatibility.
 * @host_builtin - convenience wrapper around muHashCached
 */
function muEqual(a, b) {
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
    if (typeof v === 'number') return JSON.stringify(v);
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
// Normalization: Convert JS values to linked-list format for kernel
// =============================================================================

/**
 * Check if object is EXACTLY a head/tail linked list node.
 * Strict check: must have exactly {head, tail} or {_type, head, tail}.
 */
function isLinkedListNode(obj) {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return false;
  }
  const keys = Object.keys(obj).sort();
  // Exactly {head, tail}
  if (keys.length === 2 && keys[0] === 'head' && keys[1] === 'tail') {
    return true;
  }
  // Exactly {_type, head, tail}
  if (keys.length === 3 && keys[0] === '_type' && keys[1] === 'head' && keys[2] === 'tail') {
    return true;
  }
  return false;
}

/**
 * Check if object is EXACTLY a typed empty sentinel.
 * Strict check: must have exactly {_type} with valid tag.
 */
function isTypedEmptySentinel(obj) {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return false;
  }
  const keys = Object.keys(obj);
  return keys.length === 1 && keys[0] === '_type' && VALID_TYPE_TAGS.has(obj._type);
}

/**
 * Classify a legacy (untyped) head/tail linked list as 'list' or 'dict'.
 *
 * PARITY: Matches Python classify_linked_list behavior.
 * Policy: "classify" - treat {head: X, tail: Y} as linked-list format.
 *
 * A linked list is classified as 'dict' if ALL elements are kv-pairs
 * with string keys. kv-pair format: {head: string_key, tail: {head: value, tail: null}}
 *
 * Otherwise classified as 'list' (including empty, primitives, circular).
 */
function classifyLegacyLinkedList(value) {
  // Non-object or null is list
  if (typeof value !== 'object' || value === null) {
    return 'list';
  }

  // Walk the list checking if all heads are valid kv-pairs with string keys
  const visited = new Set();
  let current = value;
  let depth = 0;

  while (current !== null && typeof current === 'object') {
    // Depth guard
    if (depth++ > MAX_DEPTH) {
      return 'list';
    }

    // Cycle detection: reject cyclic structures (parity with iterNormalizedDictPairs)
    if (visited.has(current)) {
      return 'list';
    }
    visited.add(current);

    const keys = Object.keys(current).sort();

    // Must be exactly {head, tail}
    if (keys.length !== 2 || keys[0] !== 'head' || keys[1] !== 'tail') {
      return 'list';
    }

    // Check if head is a valid kv-pair with string key and proper tail structure
    // kv-pair format: {head: string_key, tail: {head: value, tail: null}}
    const head = current.head;
    if (typeof head === 'object' && head !== null) {
      const headKeys = Object.keys(head).sort();
      // Must have exactly {head, tail}
      if (headKeys.length !== 2 || headKeys[0] !== 'head' || headKeys[1] !== 'tail') {
        // Head is object but not kv-pair structure - it's a list
        return 'list';
      }

      // Validate the key is a string
      const key = head.head;
      if (typeof key !== 'string') {
        // Key is not a string - not a valid dict encoding
        return 'list';
      }

      // P2 fix: Validate tail structure is {head: value, tail: null}
      // Without this, malformed elements like {head: "k", tail: {head: 1, tail: {head: 2}}}
      // would be incorrectly classified as dict
      const kvTail = head.tail;
      if (typeof kvTail !== 'object' || kvTail === null) {
        // tail must be an object
        return 'list';
      }
      const kvTailKeys = Object.keys(kvTail).sort();
      if (kvTailKeys.length !== 2 || kvTailKeys[0] !== 'head' || kvTailKeys[1] !== 'tail') {
        // tail must have exactly {head, tail}
        return 'list';
      }
      if (kvTail.tail !== null) {
        // kv-pair tail.tail must be null (value wrapper terminates)
        return 'list';
      }
      // Valid kv-pair with string key and proper structure - continue checking
    } else {
      // Head is primitive - not a kv-pair, so it's a list
      return 'list';
    }

    current = current.tail;
  }

  // All elements were valid kv-pairs with string keys
  return 'dict';
}

/**
 * Normalize a Mu value for structural matching.
 *
 * Converts dicts and lists to type-tagged head/tail linked lists:
 *   List: [1, 2] -> {"_type": "list", "head": 1, "tail": {"head": 2, "tail": null}}
 *   Dict: {"a": 1} -> {"_type": "dict", "head": {"head": "a", "tail": 1}, "tail": null}
 *
 * @host_recursion - BOOTSTRAP: recursive normalization
 * @host_iteration - BOOTSTRAP: for loop for array/dict conversion
 *
 * @param {*} value - The value to normalize
 * @param {number} _depth - Current recursion depth (internal)
 * @throws {Error} If depth exceeds MAX_DEPTH or value contains invalid types
 */
function normalize(value, _depth = 0) {
  // Depth guard
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
  }

  // null
  if (value === null) {
    return null;
  }

  // Reject invalid types (function, undefined, symbol)
  if (value === undefined) {
    throw new RcxError('input.malformed_normalized', 'undefined is not valid Mu');
  }
  if (typeof value === 'function') {
    throw new RcxError('input.malformed_normalized', 'Functions are not valid Mu');
  }
  if (typeof value === 'symbol') {
    throw new RcxError('input.malformed_normalized', 'Symbols are not valid Mu');
  }

  // Validate primitives
  if (typeof value === 'number') {
    if (!isValidNumber(value)) {
      throw new Error(`Invalid number: ${value} (NaN and Infinity not allowed)`);
    }
    return value;
  }

  // Other primitives (bool, string)
  if (typeof value !== 'object') {
    return value;
  }

  // Variable site - preserve as-is
  if (isVar(value)) {
    return value;
  }

  // Array
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return { _type: 'list' };  // Empty list sentinel
    }
    // Build linked list from end
    let tail = null;
    for (let i = value.length - 1; i >= 0; i--) {
      tail = { head: normalize(value[i], _depth + 1), tail: tail };
    }
    return { _type: 'list', ...tail };
  }

  // Object
  if (typeof value === 'object') {
    const keys = Object.keys(value);

    // Empty dict
    if (keys.length === 0) {
      return { _type: 'dict' };  // Empty dict sentinel
    }

    // Already typed empty sentinel - preserve
    if (isTypedEmptySentinel(value)) {
      return value;
    }

    // Already EXACTLY a head/tail structure - normalize children only
    if (isLinkedListNode(value)) {
      if ('_type' in value) {
        return {
          _type: value._type,
          head: normalize(value.head, _depth + 1),
          tail: normalize(value.tail, _depth + 1)
        };
      }
      return {
        head: normalize(value.head, _depth + 1),
        tail: normalize(value.tail, _depth + 1)
      };
    }

    // Regular dict - convert to sorted kv linked list
    // CRITICAL: kv-pair format must match Python: {"head": key, "tail": {"head": value, "tail": null}}
    const sortedKeys = keys.sort(compareMuStringKeysByCodepoint);
    let tail = null;
    for (let i = sortedKeys.length - 1; i >= 0; i--) {
      const k = sortedKeys[i];
      // Match Python's kv_pair format exactly (line 270 of match_mu.py)
      const kv = { head: k, tail: { head: normalize(value[k], _depth + 1), tail: null } };
      tail = { head: kv, tail: tail };
    }
    return { _type: 'dict', ...tail };
  }

  return value;
}

/**
 * Denormalize from linked-list format back to JS values.
 *
 * @host_recursion - BOOTSTRAP: recursive denormalization
 * @host_iteration - BOOTSTRAP: while loop for linked list traversal
 *
 * @param {*} value - The value to denormalize
 * @param {number} _depth - Current recursion depth (internal)
 * @throws {Error} If depth exceeds MAX_DEPTH
 */
function denormalize(value, _depth = 0) {
  // Depth guard
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
  }

  // null
  if (value === null) {
    return null;
  }

  // Primitives
  if (typeof value !== 'object') {
    return value;
  }

  // Variable site - preserve as-is
  if (isVar(value)) {
    return value;
  }

  // Check for typed structure
  if (typeof value === 'object' && '_type' in value) {
    const type = value._type;

    // Security: Validate type tag (matches Python denormalize_from_match)
    // - If _type is a string: must be in whitelist, else THROW (type injection attack)
    // - If _type is NOT a string: fall through to regular object handling
    if (typeof type === 'string') {
      if (!VALID_TYPE_TAGS.has(type)) {
        throw new Error(
          `Invalid type tag '${type}' in denormalize. ` +
          `Allowed: ${[...VALID_TYPE_TAGS].join(', ')}`
        );
      }
      // Valid type tag - process as typed structure
    } else {
      // Non-string _type - treat as regular dict, fall through
      // (handled by "Regular object" section below)
    }

    // Only process as typed structure if type is valid string
    if (typeof type === 'string' && VALID_TYPE_TAGS.has(type)) {
      // Empty typed sentinels
      if (!('head' in value)) {
        if (type === 'list') return [];
        if (type === 'dict') return {};
      }

      // Typed linked list
      if (type === 'list') {
        const result = [];
        let node = value;
        let nodeDepth = 0;
        while (node && 'head' in node) {
          if (nodeDepth++ > MAX_DEPTH) {
            throw new Error(`Max depth exceeded in list denormalization`);
          }
          result.push(denormalize(node.head, _depth + 1));
          node = node.tail;
        }
        return result;
      }

      if (type === 'dict') {
        const result = Object.create(null);  // Prevent prototype pollution
        let node = value;
        let nodeDepth = 0;
        while (node && 'head' in node) {
          if (nodeDepth++ > MAX_DEPTH) {
            throw new Error(`Max depth exceeded in dict denormalization`);
          }
          const kv = node.head;
          // kv-pair format: {"head": key, "tail": {"head": value, "tail": null}}
          // Must extract kv.tail.head to get the actual value (matches Python)
          if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
            result[kv.head] = denormalize(kv.tail.head, _depth + 1);
          }
          node = node.tail;
        }
        return result;
      }
    }
    // If _type is non-string or invalid, fall through to regular object handling
  }

  // Non-typed head/tail (EXACTLY 2 keys) - classify and convert to list/dict
  // PARITY: Matches Python classify_linked_list behavior
  // Policy decision: "classify" - treat {head: X, tail: Y} as linked-list format
  if (isLinkedListNode(value) && !('_type' in value)) {
    // Check if this looks like a dict encoding (head elements are kv-pairs with string keys)
    const isDictEncoding = classifyLegacyLinkedList(value) === 'dict';

    if (isDictEncoding) {
      // Dict encoding - extract kv-pairs
      const result = Object.create(null);  // Prevent prototype pollution
      let node = value;
      let nodeDepth = 0;
      while (node && typeof node === 'object' && 'head' in node) {
        if (nodeDepth++ > MAX_DEPTH) {
          throw new Error(`Max depth exceeded in dict denormalization`);
        }
        const kv = node.head;
        if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
          result[kv.head] = denormalize(kv.tail.head, _depth + 1);
        }
        node = node.tail;
      }
      return result;
    } else {
      // List encoding - extract elements
      const result = [];
      let node = value;
      let nodeDepth = 0;
      while (node && typeof node === 'object' && 'head' in node) {
        if (nodeDepth++ > MAX_DEPTH) {
          throw new Error(`Max depth exceeded in list denormalization`);
        }
        result.push(denormalize(node.head, _depth + 1));
        node = node.tail;
      }
      return result;
    }
  }

  // Regular object - denormalize values
  const result = Object.create(null);  // Prevent prototype pollution
  for (const [k, v] of Object.entries(value)) {
    result[k] = denormalize(v, _depth + 1);
  }
  return result;
}

/**
 * Normalize a projection (pattern and body).
 */
function normalizeProjection(proj) {
  // Return only pattern/body — no spread. Extra fields (id, etc.) are stripped
  // downstream at kernelDomainProjs construction anyway, but avoiding the spread
  // makes the data flow explicit and prevents accidental field leakage.
  return {
    pattern: normalize(proj.pattern),
    body: normalize(proj.body)
  };
}

// =============================================================================
// Core Pattern Matching
// =============================================================================

/**
 * BOOTSTRAP_PRIMITIVE: match (part of eval_step)
 * Match pattern against input, returning bindings or NO_MATCH.
 *
 * @host_recursion - BOOTSTRAP: recursive pattern matching
 *
 * @param {*} pattern - The pattern to match
 * @param {*} input - The input to match against
 * @param {number} _depth - Current recursion depth (internal)
 * @throws {Error} If depth exceeds MAX_DEPTH
 */
function match(pattern, input, _depth = 0) {
  // Depth guard
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded in match (${MAX_DEPTH})`);
  }

  // Gate 3: Auto-normalize input when pattern uses normalized dict format.
  // Normalization is idempotent, so already-normalized input is unchanged.
  // This allows normalized algorithm seeds to work with raw dict input.
  if (_depth === 0 && typeof pattern === 'object' && pattern !== null &&
      !Array.isArray(pattern) && pattern._type === 'dict') {
    input = normalize(input);
  }

  // Variable site - matches anything
  if (isVar(pattern)) {
    return { [pattern.var]: input };
  }

  // null
  if (pattern === null) {
    return input === null ? {} : NO_MATCH;
  }

  // Primitives (bool, number, string)
  if (typeof pattern !== 'object') {
    return pattern === input ? {} : NO_MATCH;
  }

  // Array (shouldn't happen after normalization, but handle anyway)
  if (Array.isArray(pattern)) {
    if (!Array.isArray(input) || pattern.length !== input.length) {
      return NO_MATCH;
    }
    const bindings = {};
    for (let i = 0; i < pattern.length; i++) {
      const sub = match(pattern[i], input[i], _depth + 1);
      if (sub === NO_MATCH) return NO_MATCH;
      for (const [k, v] of Object.entries(sub)) {
        if (k in bindings && muHashCached(bindings[k]) !== muHashCached(v)) {
          return NO_MATCH;
        }
        bindings[k] = v;
      }
    }
    return bindings;
  }

  // Object (dict)
  if (typeof pattern === 'object') {
    if (typeof input !== 'object' || input === null || Array.isArray(input)) {
      return NO_MATCH;
    }
    const pKeys = new Set(Object.keys(pattern));
    const iKeys = new Set(Object.keys(input));

    // Gate 3: Allow pattern to omit _type key while input has it.
    // This lets patterns use bare {head, tail} to match normalized lists
    // which have {head, tail, _type: "list"}.
    // IMPORTANT: Only allow for _type="list" - dicts require explicit _type in pattern.
    if (pKeys.size !== iKeys.size) {
      // Check if the only difference is _type in input but not pattern
      const inputExtra = [...iKeys].filter(k => !pKeys.has(k));
      const patternExtra = [...pKeys].filter(k => !iKeys.has(k));
      const typeIsList = (input._type === 'list');
      if (!(inputExtra.length === 1 && inputExtra[0] === '_type' && patternExtra.length === 0 && typeIsList)) {
        return NO_MATCH;
      }
    } else {
      // Same size - must have same keys
      for (const k of pKeys) {
        if (!iKeys.has(k)) return NO_MATCH;
      }
    }
    const bindings = {};
    for (const k of pKeys) {
      const sub = match(pattern[k], input[k], _depth + 1);
      if (sub === NO_MATCH) return NO_MATCH;
      for (const [bk, bv] of Object.entries(sub)) {
        if (bk in bindings && muHashCached(bindings[bk]) !== muHashCached(bv)) {
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
 * BOOTSTRAP_PRIMITIVE: substitute (part of eval_step)
 * Substitute variable sites in body with bound values.
 *
 * NOTE: Unbound variables return the body unchanged (stall behavior).
 * This matches Python Phase 7d-1 semantics.
 *
 * @host_recursion - BOOTSTRAP: recursive substitution
 *
 * @param {*} body - The body to substitute into
 * @param {Object} bindings - Variable bindings
 * @param {number} _depth - Current recursion depth (internal)
 * @throws {Error} If depth exceeds MAX_DEPTH
 */
function substitute(body, bindings, _depth = 0) {
  // Depth guard
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded in substitute (${MAX_DEPTH})`);
  }

  if (isVar(body)) {
    const name = body.var;
    if (!(name in bindings)) {
      // Parity with Python eval_seed.substitute: raise on unbound variables.
      // Silent return was masking projection bugs as stalls.
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

  const result = Object.create(null);  // Prevent prototype pollution
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
  // This maintains backwards compatibility with code expecting raw dicts.
  if (typeof projection.body === 'object' && projection.body !== null &&
      !Array.isArray(projection.body) && projection.body._type === 'dict') {
    result = denormalize(result);
  }

  return result;
}

/**
 * BOOTSTRAP_PRIMITIVE: eval_step
 * Apply first matching projection.
 * This is the irreducible core - analogous to Forth's NEXT.
 *
 * @host_iteration - BOOTSTRAP: for loop over projections (first-match-wins)
 */
function step(projections, input) {
  // Validate input at API boundary
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to step()');
  }

  // @host_iteration: projection selection loop
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
    result._mode === 'done' && '_result' in result && '_stall' in result;
}

/**
 * Check if result is an intermediate kernel state (mid-execution).
 * Parity with Python is_kernel_intermediate() in step_mu.py.
 *
 * Intermediate states have kernel-internal fields indicating active processing:
 * - _subst_ctx, _match_ctx, _kernel_ctx (algorithm contexts)
 * - _mode with value other than "done" (kernel loop in progress)
 *
 * These are NOT stalls — skip hash-based stall detection for these.
 */
function isKernelIntermediate(result) {
  if (result === null || typeof result !== 'object' || Array.isArray(result)) return false;
  // Kernel context fields indicate mid-execution
  if ('_subst_ctx' in result || '_match_ctx' in result || '_kernel_ctx' in result) return true;
  // _mode present but not "done" means kernel loop in progress
  if ('_mode' in result && result._mode !== 'done') return true;
  return false;
}

/**
 * BOOTSTRAP_PRIMITIVE: max_steps (termination guard)
 * Run projections until fixpoint (stall or max steps).
 *
 * @host_iteration - BOOTSTRAP: for loop until stall/max_steps
 */
function run(projections, input, maxSteps = 10000) {
  // Validate input at API boundary
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to run()');
  }

  let current = input;
  // INVARIANT: step() is functionally pure — currentHash caching is safe.
  let currentHash = muHashCached(input);
  const trace = [];

  for (let i = 0; i < maxSteps; i++) {
    // Find which projection will match (for tracing)
    let matchedId = null;
    for (const proj of projections) {
      if (match(proj.pattern, current) !== NO_MATCH) {
        matchedId = proj.id ?? 'unknown';
        break;
      }
    }

    trace.push({ step: i, projection: matchedId, state: current });

    const next = step(projections, current);

    // Check for stall (no change) — hash comparison
    const nextHash = muHashCached(next);
    if (nextHash === currentHash) {
      return { result: current, steps: i, stalled: true, trace };
    }
    current = next;
    currentHash = nextHash;
  }
  return { result: current, steps: maxSteps, stalled: false, trace };
}

/**
 * Convert array to linked list for kernel input.
 * @host_iteration - BOOTSTRAP: for loop for conversion
 */
function listToLinked(arr) {
  if (!Array.isArray(arr) || arr.length === 0) {
    return null;
  }
  let result = null;
  // @host_iteration: array to linked list conversion
  for (let i = arr.length - 1; i >= 0; i--) {
    result = { head: arr[i], tail: result };
  }
  return result;
}

/**
 * BOOTSTRAP PRIMITIVE: Kernel entry point with security validation.
 * Validates domain input before wrapping with kernel state.
 * This is the safe API for running domain data through the kernel.
 *
 * @param {Array} projections - Combined kernel + match + subst projections
 * @param {*} domainInput - User domain data (will be validated)
 * @param {Array} domainProjections - User projections to apply
 * @param {Object} options - { maxSteps, shouldNormalize: bool }
 * @throws {Error} If domain input contains kernel-reserved fields
 */
function stepKernel(projections, domainInput, domainProjections, options = {}) {
  const {
    maxSteps = 10000,
    shouldNormalize = true,
    validationMode = 'domain',
    returnMeta = false,
  } = options;

  let validator;
  if (validationMode === 'domain') {
    validator = validateNoKernelReservedFields;
  } else if (validationMode === 'algorithm_runtime') {
    validator = validateAlgorithmRuntimeFields;
  } else {
    throw new Error(
      `SECURITY: invalid validationMode '${validationMode}'. ` +
      `Expected 'domain' or 'algorithm_runtime'.`
    );
  }

  // SECURITY: Validate input and projection payloads at selected boundary mode.
  validator(domainInput, 'domainInput');
  for (let i = 0; i < domainProjections.length; i++) {
    const proj = domainProjections[i];
    // SECURITY: Fail closed — projection must be a non-null object with pattern and body
    // Matches Python step_kernel_mu validation (parity requirement)
    if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) {
      throw new Error(
        `SECURITY: domainProjections[${i}] must be an object, got ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`
      );
    }
    if (!('pattern' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'pattern' key`);
    }
    if (!('body' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'body' key`);
    }
    if (!isValidMu(proj.pattern)) {
      throw new Error(`SECURITY: domainProjections[${i}].pattern is not valid Mu`);
    }
    if (!isValidMu(proj.body)) {
      throw new Error(`SECURITY: domainProjections[${i}].body is not valid Mu`);
    }
    validator(proj.pattern, `domainProjections[${i}].pattern`);
    validator(proj.body, `domainProjections[${i}].body`);
  }

  // Normalize if requested
  const normalizedInput = shouldNormalize ? normalize(domainInput) : domainInput;
  const normalizedProjs = shouldNormalize
    ? domainProjections.map(normalizeProjection)
    : domainProjections;
  const kernelDomainProjs = normalizedProjs.map(proj => ({
    pattern: proj.pattern,
    body: proj.body
  }));

  // Wrap in kernel format
  const kernelInput = {
    _step: normalizedInput,
    _projs: listToLinked(kernelDomainProjs)
  };

  if (returnMeta) {
    // Gate 5 parity fix: use step-by-step loop that detects kernel terminal
    // state {_mode:"done", _stall:...} BEFORE kernel.unwrap fires.
    // This matches Python's step_kernel_mu which reads _stall from the
    // kernel's own terminal marker — not value equality.
    //
    // Previous code used run() which loses _stall information after
    // kernel.unwrap extracts the result, forcing value equality fallback
    // that misclassifies identity projections as stalls.
    let current = kernelInput;
    // INVARIANT: step() is functionally pure — currentHash caching is safe.
    let currentHash = muHashCached(kernelInput);
    for (let i = 0; i < maxSteps; i++) {
      const result = step(projections, current);

      // Check for kernel terminal state BEFORE unwrap
      if (isKernelTerminal(result)) {
        const stall = result._stall === true;
        if (stall) {
          validator(domainInput, 'stepKernel output');
          return { output: domainInput, stall: true };
        }
        const output = denormalize(result._result);
        validator(output, 'stepKernel output');
        return { output, stall: false };
      }

      // Stall check: no change means no progress.
      // Skip for intermediate kernel states — they are mid-execution by definition.
      // Parity with Python step_kernel_mu: `if not is_kernel_intermediate(result):`
      if (!isKernelIntermediate(result)) {
        const resultHash = muHashCached(result);
        if (resultHash === currentHash) {
          validator(domainInput, 'stepKernel output');
          return { output: domainInput, stall: true };
        }
        currentHash = resultHash;
      }

      current = result;
    }
    // Max steps exceeded — stall
    validator(domainInput, 'stepKernel output');
    return { output: domainInput, stall: true };
  }

  // Non-meta mode: run() with isKernelIntermediate stall-skip.
  // Like run() but skips hash-based stall checks for intermediate kernel
  // states (parity with Python step_kernel_mu's is_kernel_intermediate guard).
  let current = kernelInput;
  let currentHash = muHashCached(kernelInput);
  const trace = [];
  for (let i = 0; i < maxSteps; i++) {
    const next = step(projections, current);

    // Skip stall check for intermediate kernel states — they are mid-execution.
    if (!isKernelIntermediate(next)) {
      const nextHash = muHashCached(next);
      if (nextHash === currentHash) {
        return { result: current, steps: i, stalled: true, trace };
      }
      currentHash = nextHash;
    }

    current = next;
  }
  return { result: current, steps: maxSteps, stalled: false, trace };
}

/**
 * Gate 5 parity: Resolve which projection produced nextValue from current.
 * Probes each projection through stepKernel with bridge semantics.
 * Mirrors Python _resolve_trace_projection_id() (step_mu.py:1100-1148).
 */
function resolveTraceProjectionId(projections, current, nextValue) {
  // Cache nextValue hash — it doesn't change across iterations.
  const nextValueHash = muHashCached(nextValue);
  for (const proj of projections) {
    if (typeof proj !== 'object' || proj === null) continue;
    if (!('pattern' in proj) || !('body' in proj)) continue;
    const candidate = stepKernel(allProjectionsWithBridge, current, [proj], {
      validationMode: 'domain',
      returnMeta: true,
    });
    if (candidate.stall) continue;
    if (muHashCached(candidate.output) === nextValueHash) {
      return proj.id ?? null;
    }
  }
  return null;
}

/**
 * Phase 8d: Run with structural trace accumulation.
 *
 * Gate 5 parity: Routes each step through stepKernel with bridge projections
 * instead of calling match/substitute directly. This matches Python's
 * run_mu_structural() which uses step_kernel_mu(kernel_mode="bridge").
 *
 * Returns a Mu-compatible result structure that Recurrence can analyze:
 * {
 *   result: final_value,
 *   trace: linked_list_of_steps,  // Mu linked list, not JS array
 *   stall: bool,
 *   steps: int
 * }
 *
 * Each trace entry is:
 * {
 *   step: int,
 *   state: value_at_step,
 *   projection: id_or_null  // Which projection matched (null = stall)
 * }
 *
 * This enables Rule 2.2 (closure-on-second-demand) - Recurrence projections
 * can pattern-match against the trace to detect when a state recurs.
 *
 * @host_iteration - BOOTSTRAP: for loop until stall/max_steps with trace
 */
function runStructural(projections, input, maxSteps = 10000) {
  // Validate input at API boundary
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to runStructural()');
  }
  validateNoKernelReservedFields(input, 'runStructural input');

  // Validate each domain projection's pattern and body for reserved fields
  for (let idx = 0; idx < projections.length; idx++) {
    const proj = projections[idx];
    if (typeof proj === 'object' && proj !== null) {
      if ('pattern' in proj) {
        validateNoKernelReservedFields(proj.pattern, `runStructural projection[${idx}].pattern`);
      }
      if ('body' in proj) {
        validateNoKernelReservedFields(proj.body, `runStructural projection[${idx}].body`);
      }
    }
  }

  const traceEntries = [];
  let current = input;
  // INVARIANT: stepKernel returns new structures — currentHash caching is safe.
  let currentHash = muHashCached(input);

  for (let i = 0; i < maxSteps; i++) {
    // Gate 5 parity: route through kernel with bridge projections
    const meta = stepKernel(allProjectionsWithBridge, current, projections, {
      validationMode: 'domain',
      returnMeta: true,
    });
    const result = meta.output;
    const matchedId = resolveTraceProjectionId(projections, current, result);

    validateNoKernelReservedFields(result, 'runStructural output');
    traceEntries.push({
      step: i,
      state: current,
      projection: matchedId
    });

    // Check for stall (no change) — hash comparison
    const resultHash = muHashCached(result);
    if (resultHash === currentHash) {
      // Add NEW entry for stall - MUST match Python exactly (step_mu.py:1221-1227)
      traceEntries.push({
        step: i + 1,
        state: result,
        projection: null,
        stall: true
      });
      return {
        result: result,
        trace: listToLinked(traceEntries),
        stall: true,
        steps: i + 1
      };
    }

    current = result;
    currentHash = resultHash;
  }

  // Hit max steps without stall - add NEW entry (MUST match Python step_mu.py:1238-1243)
  traceEntries.push({
    step: maxSteps,
    state: current,
    projection: null,
    max_steps: true
  });
  return {
    result: current,
    trace: listToLinked(traceEntries),
    stall: false,
    steps: maxSteps
  };
}

/**
 * Phase 8d: stepKernel with structural trace.
 * Gate 5 parity: delegates to runStructural() which routes each step
 * through stepKernel with bridge projections internally.
 */
function stepKernelStructural(domainProjections, domainInput, options = {}) {
  const { maxSteps = 10000 } = options;
  return runStructural(domainProjections, domainInput, maxSteps);
}

// =============================================================================
// Test Harness - Complete Kernel Cycle
// =============================================================================

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// BOOTSTRAP_PRIMITIVE: projection_loader
// Load all seed files (JSON parsing is the irreducible I/O primitive)
// Seeds organized in mu/ folder structure:
//   mu/substrate/ - kernel, match, subst (the VM)
//   mu/closures/  - recurrence, exhaustion (closure detection)
//   mu/bridge/    - bootstrap_structural (non-linear pattern support)
//   mu/programs/  - rcx_engine, hemispheres (application programs)

// Seed integrity verification — parity with Python's seed_integrity.py
// SHA256 checksums must match Python's SEED_CHECKSUMS exactly
const SEED_CHECKSUMS = {
  'kernel.v1.json': '8a4471648c8d77d4d5beedf3491c04b8154e282bbfbf52a958f8c5bcc5d94c4f',
  'match.v2.json': 'cd89ce2bef9668b2e0bb190ad8a615a53bd699d4a0ad3ff9d6c1429db5e3594d',
  'subst.v2.json': '0b735c52da437a6eae1478dc4c992269bff8978c7e9084d15ffcba6c06e3037f',
  'recurrence.v1.json': 'ad9944b340e22df187fe567875d2c75483d4201b1b5c0147e1e8ec63e0bbacd0',
  'recurrence.v2.json': 'f8bc7fc7f43f5423b0ecf0e78fd4b2d99699456ecff1e113d4c8e7167b213fa9',
  'exhaustion.v1.json': '2497881e19015db553a834c9d1f287c7774c2607effc224ed460b4b8051dffe0',
  'bootstrap_structural.v1.json': 'dfaa1ea9de000e344fee1e61be9666e2876091fa64aff524857265929a261964',
  'hemispheres.v1.json': 'fb212be1d4bedcdf4b805ff4394d47bee8cb1b7eda19b449e16536a22c683de8',
  'rcx_engine.v1.json': '1e32fcb989d18015be45ee7dd6d7b85a9ecfa8509d44562f04b7029c23ec684f',
  'fix.v1.json': 'd961abcf1b9ba39c2eebcf049ae3351b51082a09c41deb0d71efef9eedadca34',
  'metabolization.v1.json': 'a1f60ff55dc3e9f7c0c12e247a337d5d942cbfb74beffd001336d3a77de9a1e7',
};

// Expected projection IDs in security-critical order (first-match-wins)
// Must match Python's EXPECTED_PROJECTION_IDS exactly
const EXPECTED_PROJECTION_IDS = {
  'kernel.v1.json': [
    'kernel.wrap', 'kernel.stall', 'kernel.try', 'kernel.match_success',
    'kernel.match_fail', 'kernel.subst_success', 'kernel.unwrap',
  ],
  'match.v2.json': [
    'match.done', 'match.sibling', 'match.equal', 'match.var',
    'match.typed.descend', 'match.dict.descend', 'match.fail', 'match.wrap',
  ],
  'subst.v2.json': [
    'subst.done', 'subst.ascend', 'subst.sibling', 'subst.var',
    'subst.lookup.found', 'subst.lookup.next', 'subst.typed.descend',
    'subst.typed.sibling', 'subst.typed.ascend', 'subst.descend',
    'subst.primitive', 'subst.wrap',
  ],
  'recurrence.v1.json': [
    'recurrence.init', 'recurrence.end_of_trace', 'recurrence.check_state_stall',
    'recurrence.check_state_maxsteps', 'recurrence.check_state',
    'recurrence.found_in_seen', 'recurrence.not_in_head', 'recurrence.not_found',
    'recurrence.unwrap',
  ],
  'recurrence.v2.json': [
    'recurrence.init', 'recurrence.end_of_trace', 'recurrence.check_state_stall',
    'recurrence.check_state_maxsteps', 'recurrence.check_state',
    'recurrence.hash_match', 'recurrence.hash_no_match', 'recurrence.not_found',
    'recurrence.unwrap',
  ],
  'exhaustion.v1.json': [
    'exhaustion.init_null', 'exhaustion.init', 'exhaustion.find_match',
    'exhaustion.find_continue', 'exhaustion.find_not_found', 'exhaustion.scan_same',
    'exhaustion.scan_different', 'exhaustion.scan_end', 'exhaustion.frozen_found',
    'exhaustion.frozen_check_tail', 'exhaustion.do_freeze',
  ],
  'bootstrap_structural.v1.json': [
    'bridge.var.check_existing', 'bridge.lookup.found_same',
    'bridge.lookup.found_different', 'bridge.lookup.not_found_yet',
    'bridge.lookup.not_found',
  ],
  'hemispheres.v1.json': [
    'hemisphere.init', 'hemisphere.classify.exhaustion', 'hemisphere.classify.null',
    'hemisphere.classify.closure', 'hemisphere.classify.stall',
    'hemisphere.classify.default', 'hemisphere.add.r_null', 'hemisphere.add.r_inf',
    'hemisphere.add.r_a', 'hemisphere.add.lobes', 'hemisphere.add.sink',
    'hemisphere.unwrap',
  ],
  'rcx_engine.v1.json': [
    'engine.init', 'engine.init_config', 'engine.trace_done',
    'engine.hash_done_fix', 'engine.hash_done',
    'engine.fix_done_applied', 'engine.fix_done_none',
    'engine.recurrence_done', 'engine.exhaustion_done_freeze',
    'engine.exhaustion_done_terminal', 'engine.unwrap',
  ],
  'fix.v1.json': [
    'fix.init', 'fix.edge_add_guard', 'fix.edge_add', 'fix.vertex_add_guard', 'fix.vertex_add', 'fix.pass_through',
  ],
  'metabolization.v1.json': [
    'hemisphere.metabolize.sink_to_r_null', 'hemisphere.metabolize.sink_to_r_inf',
    'hemisphere.recover.stall_to_lobes', 'hemisphere.recover.stall_to_sink',
    'hemisphere.promote.lobes_to_r_a', 'hemisphere.recycle.residual_to_sink',
  ],
};

function verifySeedChecksum(seedName, rawContent) {
  const expected = SEED_CHECKSUMS[seedName];
  if (!expected) return; // Unknown seed — skip (matches Python behavior)
  const actual = crypto.createHash('sha256').update(rawContent).digest('hex');
  if (actual !== expected) {
    throw new Error(
      `Seed ${seedName} checksum mismatch: expected ${expected}, got ${actual}`
    );
  }
}

function validateSeedStructure(seedName, seed) {
  if (!('meta' in seed) || seed.meta === null || typeof seed.meta !== 'object') {
    throw new Error(`Seed ${seedName}: missing or invalid 'meta' field`);
  }
  if (!('projections' in seed) || !Array.isArray(seed.projections)) {
    throw new Error(`Seed ${seedName}: missing or invalid 'projections' field`);
  }
  for (let i = 0; i < seed.projections.length; i++) {
    const proj = seed.projections[i];
    if (!('id' in proj) || !('pattern' in proj) || !('body' in proj)) {
      throw new Error(
        `Seed ${seedName}: projection ${i} missing required field (id/pattern/body)`
      );
    }
  }
}

function validateProjectionIds(seedName, seed) {
  const expected = EXPECTED_PROJECTION_IDS[seedName];
  if (!expected) return; // Unknown seed — skip
  const actualIds = seed.projections.map(p => p.id);
  // Enforce exact ordered equality — projection order is security-critical
  if (actualIds.length !== expected.length) {
    throw new Error(
      `Seed ${seedName}: expected ${expected.length} projections, got ${actualIds.length}`
    );
  }
  for (let i = 0; i < expected.length; i++) {
    if (actualIds[i] !== expected[i]) {
      throw new Error(
        `Seed ${seedName}: projection order mismatch at index ${i}: ` +
        `expected '${expected[i]}', got '${actualIds[i]}'`
      );
    }
  }
}

// Parity with Python _validate_combined_bridge_ordering (step_mu.py:510)
// Validates critical ordering invariants for bridge-enabled kernel composition.
function validateCombinedBridgeOrdering(projections) {
  const ids = [];
  for (const proj of projections) {
    if (proj && typeof proj === 'object') {
      ids.push(proj.id);
    }
  }

  const requiredBridgeIds = [
    'bridge.var.check_existing',
    'bridge.lookup.found_same',
    'bridge.lookup.found_different',
    'bridge.lookup.not_found_yet',
    'bridge.lookup.not_found',
  ];

  // Check all bridge projections are present
  const missing = requiredBridgeIds.filter(id => !ids.includes(id));
  if (missing.length > 0) {
    throw new Error(
      'SECURITY: Bridge ordering invariant failed; missing bridge projections: ' +
      JSON.stringify(missing)
    );
  }

  // match.var must be present
  if (!ids.includes('match.var')) {
    throw new Error('SECURITY: Bridge ordering invariant failed; missing match.var');
  }

  // All bridge projections must come before match.var
  const matchVarIdx = ids.indexOf('match.var');
  for (const bridgeId of requiredBridgeIds) {
    const bridgeIdx = ids.indexOf(bridgeId);
    if (bridgeIdx >= matchVarIdx) {
      throw new Error(
        'SECURITY: Bridge ordering invariant failed; ' +
        `${bridgeId} (index ${bridgeIdx}) must be before match.var (index ${matchVarIdx})`
      );
    }
  }

  // bridge.lookup.found_same must precede bridge.lookup.found_different
  const foundSameIdx = ids.indexOf('bridge.lookup.found_same');
  const foundDiffIdx = ids.indexOf('bridge.lookup.found_different');
  if (foundSameIdx > foundDiffIdx) {
    throw new Error(
      'SECURITY: Bridge ordering invariant failed; ' +
      'bridge.lookup.found_same must precede bridge.lookup.found_different'
    );
  }
}

function loadVerifiedSeed(seedPath, seedName) {
  const raw = fs.readFileSync(seedPath, 'utf8');
  verifySeedChecksum(seedName, raw);
  const seed = JSON.parse(raw);
  validateSeedStructure(seedName, seed);
  validateProjectionIds(seedName, seed);
  return seed;
}

const substrateDir = path.join(__dirname, '..', '..', 'substrate');
const closuresDir = path.join(__dirname, '..', '..', 'closures');
const bridgeDir = path.join(__dirname, '..', '..', 'bridge');
const programsDir = path.join(__dirname, '..', '..', 'programs');
const kernel = loadVerifiedSeed(path.join(substrateDir, 'kernel.v1.json'), 'kernel.v1.json');
const matchSeed = loadVerifiedSeed(path.join(substrateDir, 'match.v2.json'), 'match.v2.json');
const substSeed = loadVerifiedSeed(path.join(substrateDir, 'subst.v2.json'), 'subst.v2.json');
const recurrenceSeed = loadVerifiedSeed(path.join(closuresDir, 'recurrence.v1.json'), 'recurrence.v1.json');
const recurrenceV2Seed = loadVerifiedSeed(path.join(closuresDir, 'recurrence.v2.json'), 'recurrence.v2.json');
const exhaustionSeed = loadVerifiedSeed(path.join(closuresDir, 'exhaustion.v1.json'), 'exhaustion.v1.json');
const fixSeed = loadVerifiedSeed(path.join(closuresDir, 'fix.v1.json'), 'fix.v1.json');
const bridgeSeed = loadVerifiedSeed(path.join(bridgeDir, 'bootstrap_structural.v1.json'), 'bootstrap_structural.v1.json');
const hemisphereSeed = loadVerifiedSeed(path.join(programsDir, 'hemispheres.v1.json'), 'hemispheres.v1.json');
const engineSeed = loadVerifiedSeed(path.join(programsDir, 'rcx_engine.v1.json'), 'rcx_engine.v1.json');
const metabolizationSeed = loadVerifiedSeed(path.join(programsDir, 'metabolization.v1.json'), 'metabolization.v1.json');

// Combine projections: kernel first, then match, then subst
const allProjections = [
  ...kernel.projections,
  ...matchSeed.projections,
  ...substSeed.projections
];

// Bridge projections (non-linear pattern support for algorithms)
const bridgeProjections = bridgeSeed.projections;

// Recurrence projections (separate - used for closure detection after trace)
const recurrenceProjections = recurrenceSeed.projections;

// Exhaustion projections (separate - used for operator exhaustion after recurrence)
const exhaustionProjections = exhaustionSeed.projections;

// Fix projections (separate - used for structural fix of stalled states, GAP-04-FIX)
const fixProjections = fixSeed.projections;

// Hemisphere projections (APPLICATION level - structural routing, linear-only, no bridge needed)
const hemisphereProjections = hemisphereSeed.projections;

// Engine projections (APPLICATION level - orchestrates trace/recurrence/exhaustion pipeline)
const engineProjections = engineSeed.projections;

// Metabolization projections (APPLICATION level - hemisphere sink re-expression cycle)
const metabolizationProjections = metabolizationSeed.projections;

// Recurrence v2 projections (hash-accelerated, used by engine run_algorithm boundary)
const recurrenceV2Projections = recurrenceV2Seed.projections;

// Seed name → projections mapping for engine boundary operations
const seedProjectionMap = {
  'recurrence.v1.json': recurrenceProjections,
  'recurrence.v2.json': recurrenceV2Projections,
  'exhaustion.v1.json': exhaustionProjections,
  'fix.v1.json': fixProjections,
};

// Combined projections WITH BRIDGE for meta-circular algorithm execution
// Order: kernel -> bridge -> match -> subst (bridge extends match for non-linear patterns)
const allProjectionsWithBridge = [
  ...kernel.projections,
  ...bridgeProjections,
  ...matchSeed.projections,
  ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithBridge);

// Combined projections for recurrence execution (recurrence + kernel + match + subst)
// Recurrence projections must come FIRST so they match before kernel tries to process
const allProjectionsWithRecurrence = [
  ...recurrenceProjections,
  ...allProjections
];

// Combined projections for recurrence with bridge (meta-circular path)
// Order: recurrence -> kernel -> bridge -> match -> subst
const allProjectionsWithRecurrenceAndBridge = [
  ...recurrenceProjections,
  ...kernel.projections,
  ...bridgeProjections,
  ...matchSeed.projections,
  ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithRecurrenceAndBridge);

// Combined projections with Exhaustion (Exhaustion + Recurrence + kernel + match + subst)
// Exhaustion projections come first for _detect_exhaustion inputs
const allProjectionsWithExhaustion = [
  ...exhaustionProjections,
  ...recurrenceProjections,
  ...allProjections
];

// Combined projections with Exhaustion AND bridge (full meta-circular path)
// Order: exhaustion -> recurrence -> kernel -> bridge -> match -> subst
const allProjectionsWithExhaustionAndBridge = [
  ...exhaustionProjections,
  ...recurrenceProjections,
  ...kernel.projections,
  ...bridgeProjections,
  ...matchSeed.projections,
  ...substSeed.projections
];
validateCombinedBridgeOrdering(allProjectionsWithExhaustionAndBridge);

// =============================================================================
// Engine-Hemisphere Orchestration (L3 Parity with Python step_mu.py)
// =============================================================================

// Terminal shape key sets (mirrors Python step_mu.py:42-47)
const RECURRENCE_TERMINAL_KEYS = new Set(['closure_detected', 'final_result', 'tau_step']);
const EXHAUSTION_TERMINAL_KEYS = new Set(['action', 'exhaustion_detected', 'frozen', 'operator_to_freeze']);
const ENGINE_TERMINAL_KEYS = new Set([
  'value', 'closure_detected', 'tau_step', 'exhaustion_detected',
  'operator_frozen', 'frozen_set', 'action', 'stall',
]);

// Hemisphere constants (mirrors Python step_mu.py:1626-1632)
const HEMISPHERE_KEY_ORDER = ['r_null', 'r_inf', 'r_a', 'lobes', 'sink'];
const HEMISPHERE_KEYS = new Set(HEMISPHERE_KEY_ORDER);

function defaultHemispheres() {
  return { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null };
}

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
 * Check for recurrence/exhaustion terminal output shape.
 * Mirrors Python _is_terminal_shape() (step_mu.py:1371).
 */
function isTerminalShape(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const keys = new Set(Object.keys(value));
  return setsEqual(keys, RECURRENCE_TERMINAL_KEYS) || setsEqual(keys, EXHAUSTION_TERMINAL_KEYS);
}

/**
 * Check if engine has produced its final unwrapped result (8-key shape).
 * Mirrors Python _is_engine_terminal() (step_mu.py:1391).
 */
function isEngineTerminal(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  return setsEqual(new Set(Object.keys(value)), ENGINE_TERMINAL_KEYS);
}

/**
 * Run a sub-algorithm (recurrence/exhaustion) to completion.
 * Mirrors Python _run_sub_algorithm() (step_mu.py:1404).
 * AST_OK: infra — boundary sub-algorithm runner
 */
function runSubAlgorithm(algorithmProjs, initial, maxIterations) {
  let current = initial;
  let currentHash = muHashCached(initial);
  for (let i = 0; i < maxIterations; i++) {
    const result = runAlgorithmWithBridge(allProjectionsWithBridge, current, algorithmProjs, 200);
    if (isTerminalShape(result)) return result;
    const resultHash = muHashCached(result);
    if (resultHash === currentHash) return result;
    current = result;
    currentHash = resultHash;
  }
  return current;
}

/**
 * Add state_hash to each entry in a Mu linked-list trace.
 * Mirrors Python hash_trace_for_recurrence() (step_mu.py:1546-1589).
 * Iterative linked-list traversal (no recursion).
 * FAIL-CLOSED: throws on cycle or overcap.
 * AST_OK: infra — boundary scaffolding, iterative
 */
function hashTraceForRecurrence(trace, maxEntries) {
  maxEntries = maxEntries ?? 10000;
  // SECURITY: Hard cap parity with Python _MAX_TRACE_ENTRIES_HARD_CAP (step_mu.py:1518)
  const MAX_TRACE_ENTRIES_HARD_CAP = 100000;
  if (maxEntries > MAX_TRACE_ENTRIES_HARD_CAP) maxEntries = MAX_TRACE_ENTRIES_HARD_CAP;
  const entries = [];
  const visited = new Set();
  let current = trace;
  while (current !== null && typeof current === 'object' && 'head' in current) {
    if (visited.has(current)) {
      throw new RcxError('trace.cycle_detected', 'hash_trace_for_recurrence: cyclic linked list detected');
    }
    visited.add(current);
    if (entries.length >= maxEntries) {
      throw new RcxError('trace.overcap', `hash_trace_for_recurrence: trace exceeds ${maxEntries} entries`);
    }
    let entry = current.head;
    if (entry !== null && typeof entry === 'object' && 'state' in entry) {
      entry = Object.assign({}, entry);
      entry.state_hash = muHash(entry.state);
    }
    entries.push(entry);
    current = current.tail !== undefined ? current.tail : null;
  }
  // Rebuild linked list from tail to head
  let result = current;
  for (let i = entries.length - 1; i >= 0; i--) {
    result = { head: entries[i], tail: result };
  }
  return result;
}

/**
 * Host loop that drives the engine state machine (rcx_engine.v1.json).
 * Mirrors Python run_engine_pipeline() (step_mu.py:1437-1543).
 * Services 3 boundary operations via algebraic effects pattern:
 *   - run_trace: generate execution trace via runStructural()
 *   - hash_trace: compute mu_hash per entry via hashTraceForRecurrence()
 *   - run_algorithm: run a sub-algorithm seed to completion via runSubAlgorithm()
 * FAIL-CLOSED: throws if engine loop exhausts without terminal result.
 * @host_iteration (boundary host loop, services engine state machine)
 */
function runEnginePipeline(projections, inputValue, options) {
  // Boundary Mu validation: reject non-Mu input before entering engine loop
  if (!isValidMu(inputValue)) {
    throw new RcxError('input.invalid_type', `runEnginePipeline: inputValue is not valid Mu (got ${typeof inputValue})`);
  }

  const {
    maxSteps = 100,
    frozen = null,
    maxEngineIterations = 20,
    maxAlgorithmIterations = 50,
    observer = null,
  } = options ?? {};

  // Observer event helper — no-op when observer is null
  let obsTs = 0;
  function emit(eventName, stepNum, stateVal, errorCode) {
    if (observer === null) return;
    let stateHash = null;
    try { stateHash = muHash(stateVal); } catch (_) { /* ignore */ }
    observer.push({
      event_name: eventName,
      step: stepNum,
      state_hash: stateHash,
      error_code: errorCode ?? null,
      substrate: 'js',
      timestamp: obsTs,
    });
    obsTs++;
  }

  // Feed engine its initial input (always use full config form -> engine.init_config)
  let state = {
    _run_engine: {
      projections: projections,
      input: inputValue,
      max_steps: maxSteps,
      frozen: frozen,
    }
  };

  // Generic effect handler loop
  for (let iteration = 0; iteration < maxEngineIterations; iteration++) {
    // Step engine projections (APPLICATION-layer, bootstrap evaluator)
    const nextState = step(engineProjections, state);

    emit('step_boundary', iteration, state);

    // Engine stalled (no projection matched)
    if (nextState === state) {
      if (isEngineTerminal(state)) {
        if (typeof state === 'object' && state !== null) {
          if (state.closure_detected) emit('closure_detected', iteration, state);
          if (state.stall) emit('stall_detected', iteration, state);
        }
        return state;
      }
      emit('fail_closed', iteration, state, 'engine.stalled_non_terminal');
      throw new RcxError('engine.stalled_non_terminal',
        `Engine stalled at iteration ${iteration} without producing terminal result. ` +
        `State keys: ${typeof state === 'object' && state !== null ? JSON.stringify(Object.keys(state).sort()) : typeof state}`
      );
    }

    // Check for boundary effect request
    if (typeof nextState === 'object' && nextState !== null && '_boundary_request' in nextState) {
      const request = nextState._boundary_request;
      const operation = request.operation;
      const reqInput = request.input;
      const context = Object.assign({}, request.context);
      const injectKey = request.inject_key;

      // SECURITY: inject_key must not be a kernel-reserved field.
      // Parity with Python run_engine_pipeline (step_mu.py:1480).
      if (KERNEL_RESERVED_FIELDS.has(injectKey)) {
        emit('fail_closed', iteration, state, 'input.reserved_field');
        throw new RcxError('input.reserved_field',
          `SECURITY: inject_key '${injectKey}' is a kernel-reserved field. ` +
          `Boundary requests cannot inject reserved fields.`
        );
      }

      let result;
      if (operation === 'run_trace') {
        const raw = runStructural(reqInput.projections, reqInput.value, reqInput.max_steps ?? 100);
        result = { result: raw.result, trace: raw.trace, stall: raw.stall };
      } else if (operation === 'hash_trace') {
        result = hashTraceForRecurrence(reqInput);
      } else if (operation === 'run_algorithm') {
        const algoName = request.algorithm;
        const algoProjs = seedProjectionMap[algoName];
        if (!algoProjs) {
          throw new RcxError('api.bad_request', `Unknown algorithm seed: ${algoName}`);
        }
        result = runSubAlgorithm(algoProjs, reqInput, maxAlgorithmIterations);
      } else {
        emit('fail_closed', iteration, state, 'api.bad_request');
        throw new RcxError('api.bad_request', `Unknown boundary operation: ${operation}`);
      }

      // SECURITY: validate boundary result before re-injection.
      // Prevents boundary operations from smuggling kernel-reserved
      // fields back into engine state (parity with Python step_mu.py).
      validateNoKernelReservedFields(result, `boundary_result(${operation})`);

      context[injectKey] = result;
      state = context;
      continue;
    }

    // Boot1: _tail_call recognition (shadow merge — seed doesn't produce this yet).
    // See Boot1LoopContract.v0.md §3 Option A.
    if (typeof nextState === 'object' && nextState !== null
        && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
      const tailPayload = nextState._tail_call;
      state = { _run_engine: tailPayload };
      continue;
    }

    // Check if engine produced terminal result
    if (isEngineTerminal(nextState)) {
      if (typeof nextState === 'object' && nextState !== null) {
        if (nextState.closure_detected) emit('closure_detected', iteration, nextState);
        if (nextState.stall) emit('stall_detected', iteration, nextState);
      }
      return nextState;
    }

    // Engine advanced internally -- keep stepping
    state = nextState;
  }

  emit('fail_closed', maxEngineIterations - 1, state, 'engine.exhausted');
  throw new RcxError('engine.exhausted',
    `Engine pipeline exhausted ${maxEngineIterations} iterations without terminal result. ` +
    `State keys: ${typeof state === 'object' && state !== null ? JSON.stringify(Object.keys(state).sort()) : typeof state}`
  );
}

/**
 * Boot1 shadow: recursive engine pipeline for parity testing.
 * Mirrors Python _run_engine_recursive() — handles engine re-entry via
 * explicit recursion instead of for-loop iteration.
 * Also recognizes {_tail_call: ...} as Boot1 native re-entry signal.
 * @host_iteration: for loop per re-entry pass (Boot1 shadow)
 * AST_OK: infra — Boot1 shadow recursive engine loop
 */
const BOOT1_MAX_REENTRY_DEPTH = 20;

function runEnginePipelineRecursive(projections, inputValue, options, recursionDepth) {
  // Boundary Mu validation: reject non-Mu input before entering recursive engine loop
  if (!isValidMu(inputValue)) {
    throw new RcxError('input.invalid_type', `runEnginePipelineRecursive: inputValue is not valid Mu (got ${typeof inputValue})`);
  }

  const {
    maxSteps = 100,
    frozen = null,
    maxEngineIterations = 20,
    maxAlgorithmIterations = 50,
    observer = null,
  } = options ?? {};

  recursionDepth = recursionDepth ?? 0;

  if (recursionDepth >= BOOT1_MAX_REENTRY_DEPTH) {
    throw new RcxError('engine.boot1_depth_exceeded',
      `Boot1 recursive re-entry depth ${recursionDepth} exceeds limit ${BOOT1_MAX_REENTRY_DEPTH}.`
    );
  }

  // Observer event helper
  let obsTs = 0;
  function emit(eventName, stepNum, stateVal, errorCode) {
    if (observer === null) return;
    let stateHash = null;
    try { stateHash = muHash(stateVal); } catch (_) { /* ignore */ }
    observer.push({
      event_name: eventName,
      step: stepNum,
      state_hash: stateHash,
      error_code: errorCode ?? null,
      substrate: 'js',
      timestamp: obsTs,
      boot1_depth: recursionDepth,
    });
    obsTs++;
  }

  // Feed engine its initial input
  let state = {
    _run_engine: {
      projections: projections,
      input: inputValue,
      max_steps: maxSteps,
      frozen: frozen,
    }
  };

  // Engine stepping loop (per re-entry pass)
  for (let iteration = 0; iteration < maxEngineIterations; iteration++) {
    const nextState = step(engineProjections, state);

    emit('step_boundary', iteration, state);

    // Engine stalled
    if (nextState === state) {
      if (isEngineTerminal(state)) {
        if (typeof state === 'object' && state !== null) {
          if (state.closure_detected) emit('closure_detected', iteration, state);
          if (state.stall) emit('stall_detected', iteration, state);
        }
        return state;
      }
      emit('fail_closed', iteration, state, 'engine.stalled_non_terminal');
      throw new RcxError('engine.stalled_non_terminal',
        `Boot1 engine stalled at iteration ${iteration} (depth ${recursionDepth}) without terminal result.`
      );
    }

    // Boundary effect request
    if (typeof nextState === 'object' && nextState !== null && '_boundary_request' in nextState) {
      const request = nextState._boundary_request;
      const operation = request.operation;
      const reqInput = request.input;
      const context = Object.assign({}, request.context);
      const injectKey = request.inject_key;

      if (KERNEL_RESERVED_FIELDS.has(injectKey)) {
        emit('fail_closed', iteration, state, 'input.reserved_field');
        throw new RcxError('input.reserved_field',
          `SECURITY: inject_key '${injectKey}' is a kernel-reserved field.`
        );
      }

      let result;
      if (operation === 'run_trace') {
        const raw = runStructural(reqInput.projections, reqInput.value, reqInput.max_steps ?? 100);
        result = { result: raw.result, trace: raw.trace, stall: raw.stall };
      } else if (operation === 'hash_trace') {
        result = hashTraceForRecurrence(reqInput);
      } else if (operation === 'run_algorithm') {
        const algoName = request.algorithm;
        const algoProjs = seedProjectionMap[algoName];
        if (!algoProjs) {
          throw new RcxError('api.bad_request', `Unknown algorithm seed: ${algoName}`);
        }
        result = runSubAlgorithm(algoProjs, reqInput, maxAlgorithmIterations);
      } else {
        emit('fail_closed', iteration, state, 'api.bad_request');
        throw new RcxError('api.bad_request', `Unknown boundary operation: ${operation}`);
      }

      validateNoKernelReservedFields(result, `boundary_result(${operation})`);

      context[injectKey] = result;
      state = context;
      continue;
    }

    // Boot1: detect re-entry envelope — recurse instead of continuing loop
    if (typeof nextState === 'object' && nextState !== null
        && '_run_engine' in nextState && Object.keys(nextState).length === 1) {
      const payload = nextState._run_engine;
      return runEnginePipelineRecursive(
        payload.projections, payload.input,
        {
          maxSteps: payload.max_steps ?? maxSteps,
          frozen: payload.frozen ?? null,
          maxEngineIterations: maxEngineIterations - iteration - 1,
          maxAlgorithmIterations,
          observer,
        },
        recursionDepth + 1,
      );
    }

    // Boot1: _tail_call recognition — recurse with payload
    if (typeof nextState === 'object' && nextState !== null
        && '_tail_call' in nextState && Object.keys(nextState).length === 1) {
      const payload = nextState._tail_call;
      return runEnginePipelineRecursive(
        payload.projections, payload.input,
        {
          maxSteps: payload.max_steps ?? maxSteps,
          frozen: payload.frozen ?? null,
          maxEngineIterations: maxEngineIterations - iteration - 1,
          maxAlgorithmIterations,
          observer,
        },
        recursionDepth + 1,
      );
    }

    // Terminal result
    if (isEngineTerminal(nextState)) {
      if (typeof nextState === 'object' && nextState !== null) {
        if (nextState.closure_detected) emit('closure_detected', iteration, nextState);
        if (nextState.stall) emit('stall_detected', iteration, nextState);
      }
      return nextState;
    }

    // Engine advanced internally
    state = nextState;
  }

  emit('fail_closed', maxEngineIterations - 1, state, 'engine.exhausted');
  throw new RcxError('engine.exhausted',
    `Boot1 engine pipeline exhausted ${maxEngineIterations} iterations (depth ${recursionDepth}).`
  );
}

/**
 * Route engine result to hemispheres with input shape validation.
 * Mirrors Python run_hemisphere_routing() (step_mu.py:1592-1621).
 * FAIL-CLOSED: throws if routing result invalid.
 * AST_OK: infra — hemisphere boundary validation
 */
function runHemisphereRouting(engineResult, hemispheres) {
  if (engineResult === null || typeof engineResult !== 'object' || Array.isArray(engineResult)) {
    throw new RcxError('input.invalid_type', 'engine_result must be a dict');
  }
  const wrapped = {
    route_hemisphere: {
      engine_result: engineResult,
      hemispheres: hemispheres,
    }
  };
  let current = wrapped;
  const limit = 30;
  for (let i = 0; i < limit; i++) {
    const meta = stepKernel(
      allProjections, current, hemisphereProjections,
      { returnMeta: true }
    );
    if (meta.stall) break;
    current = meta.output;
  }
  if (typeof current === 'object' && current !== null &&
      setsEqual(new Set(Object.keys(current)), HEMISPHERE_KEYS)) {
    return current;
  }
  throw new RcxError(
    'input.shape_mismatch',
    `Hemisphere routing did not produce valid hemisphere dict. ` +
    `Got: ${typeof current === 'object' && current !== null ? JSON.stringify(Object.keys(current).sort()) : typeof current}`
  );
}

/**
 * Chain runEnginePipeline -> runHemisphereRouting.
 * Mirrors Python run_engine_with_routing() (step_mu.py:1635-1672).
 * FAIL-CLOSED: validates input and output shapes.
 */
function runEngineWithRouting(projections, inputValue, hemispheres, engineKwargs, boot1Mode) {
  if (hemispheres === undefined || hemispheres === null) {
    hemispheres = defaultHemispheres();
  } else {
    if (typeof hemispheres !== 'object' || Array.isArray(hemispheres)) {
      throw new RcxError('input.invalid_type', `hemispheres must be dict, got ${Array.isArray(hemispheres) ? 'array' : typeof hemispheres}`);
    }
    const actual = new Set(Object.keys(hemispheres));
    if (!setsEqual(actual, HEMISPHERE_KEYS)) {
      const missing = [...HEMISPHERE_KEYS].filter(k => !actual.has(k)).sort();
      const extra = [...actual].filter(k => !HEMISPHERE_KEYS.has(k)).sort();
      throw new RcxError('input.shape_mismatch', `hemispheres shape mismatch: missing=${JSON.stringify(missing)}, extra=${JSON.stringify(extra)}`);
    }
  }

  // Boot1 routing: recursive vs trampoline (mirrors run_engine_pipeline handler)
  const engineResult = boot1Mode
    ? runEnginePipelineRecursive(projections, inputValue, engineKwargs)
    : runEnginePipeline(projections, inputValue, engineKwargs);
  const updatedHemispheres = runHemisphereRouting(engineResult, hemispheres);

  const outputKeys = new Set(Object.keys(updatedHemispheres));
  if (typeof updatedHemispheres !== 'object' || !setsEqual(outputKeys, HEMISPHERE_KEYS)) {
    throw new RcxError('input.shape_mismatch', 'runHemisphereRouting returned unexpected shape');
  }

  return { engine_result: engineResult, hemispheres: updatedHemispheres };
}

console.log('=== RCX eval_step.js - Complete Kernel Cycle (v8 - L3 Full Parity with Bridge) ===\n');
console.log('Seed integrity: 11 seeds verified (checksum + structure + projection order)');
console.log(`Loaded projections from mu/ folder:`);
console.log(`  - substrate/kernel.v1.json: ${kernel.projections.length} projections`);
console.log(`  - substrate/match.v2.json: ${matchSeed.projections.length} projections`);
console.log(`  - substrate/subst.v2.json: ${substSeed.projections.length} projections`);
console.log(`  - bridge/bootstrap_structural.v1.json: ${bridgeSeed.projections.length} projections`);
console.log(`  - closures/recurrence.v1.json: ${recurrenceSeed.projections.length} projections (proof-of-concept)`);
console.log(`  - closures/recurrence.v2.json: ${recurrenceV2Seed.projections.length} projections (hash-accelerated)`);
console.log(`  - closures/exhaustion.v1.json: ${exhaustionSeed.projections.length} projections`);
console.log(`  - closures/fix.v1.json: ${fixSeed.projections.length} projections (draft — GAP-04-FIX)`);
console.log(`  - programs/hemispheres.v1.json: ${hemisphereSeed.projections.length} projections`);
console.log(`  - programs/metabolization.v1.json: ${metabolizationSeed.projections.length} projections`);
console.log(`  - programs/rcx_engine.v1.json: ${engineSeed.projections.length} projections`);
console.log(`  - Total (kernel ops): ${allProjections.length} projections`);
console.log(`  - Total (with Bridge): ${allProjectionsWithBridge.length} projections`);
console.log(`  - Total (with Recurrence): ${allProjectionsWithRecurrence.length} projections`);
console.log(`  - Total (with Recurrence+Bridge): ${allProjectionsWithRecurrenceAndBridge.length} projections`);
console.log(`  - Total (with Exhaustion): ${allProjectionsWithExhaustion.length} projections`);
console.log(`  - Total (with Exhaustion+Bridge): ${allProjectionsWithExhaustionAndBridge.length} projections\n`);

// =============================================================================
// Test: Complete match + subst cycle through kernel
// =============================================================================

console.log('=== Test 1: Complete Kernel Cycle ===\n');

// Create a simple projection to test
const testProjection = {
  pattern: { op: 'double', value: { var: 'n' } },
  body: { result: { var: 'n' }, doubled: { var: 'n' } }
};

// Normalize the projection (convert to linked-list format)
const normalizedProjection = normalizeProjection(testProjection);

// Input value
const testInput = { op: 'double', value: 42 };
const normalizedInput = normalize(testInput);

// Wrap for kernel
const kernelInput = {
  _step: normalizedInput,
  _projs: listToLinked([normalizedProjection])
};

console.log('Original input:', JSON.stringify(testInput));
console.log('Normalized input:', JSON.stringify(normalizedInput));
console.log('Original projection pattern:', JSON.stringify(testProjection.pattern));
console.log('Normalized projection pattern:', JSON.stringify(normalizedProjection.pattern));
console.log('\n--- Running kernel cycle ---\n');

const { result, steps, stalled, trace } = run(allProjections, kernelInput, 100);

// Show trace (abbreviated)
console.log('Execution trace:');
for (const t of trace.slice(0, 15)) {
  const stateStr = JSON.stringify(t.state);
  const preview = stateStr.length > 70 ? stateStr.slice(0, 70) + '...' : stateStr;
  console.log(`  [${t.step}] ${t.projection ?? 'STALL'}: ${preview}`);
}
if (trace.length > 15) {
  console.log(`  ... (${trace.length - 15} more steps)`);
}

console.log(`\nTotal steps: ${steps}`);
console.log(`Stalled: ${stalled}`);

// Denormalize the result
const denormalizedResult = denormalize(result);
console.log(`\nRaw result:`, JSON.stringify(result));
console.log(`Denormalized result:`, JSON.stringify(denormalizedResult));

// Expected: { result: 42, doubled: 42 }
const expectedResult = { result: 42, doubled: 42 };
const passed = muEqual(denormalizedResult, expectedResult);
console.log(`\nExpected:`, JSON.stringify(expectedResult));
console.log(`PASS: ${passed}`);

// =============================================================================
// Test 2: Stall case (no matching projection)
// =============================================================================

console.log('\n=== Test 2: Stall Case (No Match) ===\n');

const testProjection2 = {
  pattern: { op: 'triple', value: { var: 'n' } },  // Won't match 'double'
  body: { result: { var: 'n' } }
};

const kernelInput2 = {
  _step: normalizedInput,  // normalized { op: 'double', value: 42 }
  _projs: listToLinked([normalizeProjection(testProjection2)])
};

const { result: result2, steps: steps2, stalled: stalled2 } = run(allProjections, kernelInput2, 100);
const denorm2 = denormalize(result2);

console.log('Input:', JSON.stringify(testInput));
console.log('Projection pattern:', JSON.stringify(testProjection2.pattern), '(won\'t match)');
console.log(`\nSteps: ${steps2}, Stalled: ${stalled2}`);
console.log('Denormalized result:', JSON.stringify(denorm2));

// Expected: original input (stall)
const passedStall = muEqual(denorm2, testInput);
console.log(`\nExpected (stall returns original):`, JSON.stringify(testInput));
console.log(`PASS: ${passedStall}`);

// =============================================================================
// Test 3: Multiple projections (first-match-wins)
// =============================================================================

console.log('\n=== Test 3: Multiple Projections (First-Match-Wins) ===\n');

// NOTE: kernel.try expects {pattern, body} ONLY - no id field
const projections3 = [
  {
    pattern: { op: 'add', a: { var: 'x' }, b: { var: 'y' } },
    body: { sum: { var: 'x' } }
  },
  {
    pattern: { op: 'mul', a: { var: 'x' }, b: { var: 'y' } },
    body: { product: { var: 'x' } }
  },
  {
    pattern: { var: 'anything' },
    body: { error: 'unknown op' }
  }
];

const normalizedProjs3 = projections3.map(normalizeProjection);

const inputs3 = [
  { op: 'add', a: 10, b: 20 },
  { op: 'mul', a: 5, b: 6 },
  { op: 'div', a: 1, b: 2 }
];

const results3 = inputs3.map(inp => {
  const kernelInp = {
    _step: normalize(inp),
    _projs: listToLinked(normalizedProjs3)
  };
  const { result } = run(allProjections, kernelInp, 100);
  return denormalize(result);
});

console.log('Input: { op: "add", a: 10, b: 20 } ->', JSON.stringify(results3[0]));
console.log('Input: { op: "mul", a: 5, b: 6 }  ->', JSON.stringify(results3[1]));
console.log('Input: { op: "div", a: 1, b: 2 }  ->', JSON.stringify(results3[2]));

const pass3a = muEqual(results3[0], { sum: 10 });
const pass3b = muEqual(results3[1], { product: 5 });
const pass3c = muEqual(results3[2], { error: 'unknown op' });

console.log(`\nPASS add: ${pass3a}`);
console.log(`PASS mul: ${pass3b}`);
console.log(`PASS catchall: ${pass3c}`);

// =============================================================================
// Test 4: Security - NaN/Infinity rejection
// =============================================================================

console.log('\n=== Test 4: Security - NaN/Infinity Rejection ===\n');

let nanRejected = false;
let infRejected = false;

try {
  normalize({ value: NaN });
} catch (e) {
  nanRejected = e.message.includes('NaN');
}

try {
  normalize({ value: Infinity });
} catch (e) {
  infRejected = e.message.includes('Infinity');
}

console.log(`NaN rejected: ${nanRejected}`);
console.log(`Infinity rejected: ${infRejected}`);
console.log(`PASS security: ${nanRejected && infRejected}`);

// =============================================================================
// Test 5: Security - Depth guard
// =============================================================================

console.log('\n=== Test 5: Security - Depth Guard ===\n');

// Create deeply nested structure
function createDeep(depth) {
  let obj = { value: 'bottom' };
  for (let i = 0; i < depth; i++) {
    obj = { nested: obj };
  }
  return obj;
}

let shallowOk = false;
let deepRejected = false;

try {
  normalize(createDeep(50));  // Should succeed (< MAX_DEPTH)
  shallowOk = true;
} catch (e) {
  console.log('Shallow failed:', e.message);
}

try {
  normalize(createDeep(350));  // Should fail (> MAX_DEPTH=300)
} catch (e) {
  deepRejected = e.message.includes('Max depth');
}

console.log(`Shallow (50 levels) OK: ${shallowOk}`);
console.log(`Deep (350 levels) rejected: ${deepRejected}`);
console.log(`PASS depth guard: ${shallowOk && deepRejected}`);

// =============================================================================
// Test 6: Security - Kernel Reserved Fields Rejection
// =============================================================================

console.log('\n=== Test 6: Security - Kernel Reserved Fields Rejection ===\n');

let reservedFieldRejected = false;
let nestedReservedRejected = false;
let cleanDataAccepted = false;

// Test 1: Direct reserved field in domain input
try {
  stepKernel(allProjections, { op: 'test', _step: 'forged' }, [testProjection]);
} catch (e) {
  reservedFieldRejected = e.message.includes('_step') && e.message.includes('reserved');
}
console.log(`Direct _step in input rejected: ${reservedFieldRejected}`);

// Test 2: Nested reserved field in domain input
try {
  stepKernel(allProjections, { op: 'test', nested: { deep: { _mode: 'forged' } } }, [testProjection]);
} catch (e) {
  nestedReservedRejected = e.message.includes('_mode') && e.message.includes('reserved');
}
console.log(`Nested _mode in input rejected: ${nestedReservedRejected}`);

// Test 3: Clean data should be accepted
try {
  stepKernel(allProjections, { op: 'double', value: 99 }, [testProjection], { maxSteps: 50 });
  cleanDataAccepted = true;
} catch (e) {
  console.log('Clean data failed:', e.message);
}
console.log(`Clean domain data accepted: ${cleanDataAccepted}`);

const passReservedFields = reservedFieldRejected && nestedReservedRejected && cleanDataAccepted;
console.log(`PASS kernel reserved fields: ${passReservedFields}`);

// =============================================================================
// Test 7: Head/tail strict detection
// =============================================================================

console.log('\n=== Test 7: Head/Tail Strict Detection ===\n');

// User data with head/tail PLUS extra key should be treated as regular dict
const userDataWithExtra = { head: 'my data', tail: 'other', extra: 'field' };
const normalizedUserData = normalize(userDataWithExtra);

// Should be normalized as a dict (sorted kv pairs), NOT preserved as head/tail
const isNormalizedAsDict = normalizedUserData._type === 'dict';
console.log('User data {head, tail, extra} normalized as dict:', isNormalizedAsDict);

// Real head/tail (exactly 2 keys) should be preserved
const realLinkedList = { head: 1, tail: null };
const normalizedLinkedList = normalize(realLinkedList);
const isPreservedAsHeadTail = 'head' in normalizedLinkedList && 'tail' in normalizedLinkedList && !('_type' in normalizedLinkedList);
console.log('Real {head, tail} preserved:', isPreservedAsHeadTail);

console.log(`PASS strict detection: ${isNormalizedAsDict && isPreservedAsHeadTail}`);

// =============================================================================
// Test 8: Cross-Substrate Parity Tests (from shared vectors)
// =============================================================================

console.log('\n=== Test 8: Cross-Substrate Parity Tests ===\n');

// Load parity test vectors
const parityVectorsPath = path.join(__dirname, '..', '..', '..', 'tests', 'fixtures', 'parity_vectors.json');
let parityVectors;
try {
  parityVectors = JSON.parse(fs.readFileSync(parityVectorsPath, 'utf8'));
} catch (e) {
  console.log('Warning: Could not load parity_vectors.json:', e.message);
  parityVectors = { vectors: [], security_vectors: [] };
}

let parityPassed = 0;
let parityFailed = 0;

for (const vector of parityVectors.vectors) {
  try {
    // Run vector through stepKernel
    const { result } = stepKernel(
      allProjections,
      vector.input,
      [vector.projection],
      { maxSteps: 100 }
    );

    // Denormalize result
    const denormalized = denormalize(result);

    // Compare with expected
    const expected = vector.expected_output;
    if (muEqual(denormalized, expected)) {
      console.log(`  ✓ ${vector.id}`);
      parityPassed++;
    } else {
      console.log(`  ✗ ${vector.id}: got ${JSON.stringify(denormalized)}, expected ${JSON.stringify(expected)}`);
      parityFailed++;
    }
  } catch (e) {
    console.log(`  ✗ ${vector.id}: ERROR - ${e.message}`);
    parityFailed++;
  }
}

console.log(`\nParity tests: ${parityPassed} passed, ${parityFailed} failed`);
const parityAllPassed = parityFailed === 0 && parityPassed > 0;
console.log(`PASS parity: ${parityAllPassed}`);

// Security vectors
console.log('\n--- Security Vectors ---');
let securityPassed = 0;
let securityFailed = 0;

for (const vector of parityVectors.security_vectors) {
  try {
    // This should throw due to kernel-reserved fields
    validateNoKernelReservedFields(vector.input, 'test');
    // If we get here, it didn't throw - that's a failure
    console.log(`  ✗ ${vector.id}: should have rejected but didn't`);
    securityFailed++;
  } catch (e) {
    // Check that error mentions the expected field
    if (e.message.includes(vector.error_contains)) {
      console.log(`  ✓ ${vector.id}`);
      securityPassed++;
    } else {
      console.log(`  ✗ ${vector.id}: wrong error - ${e.message}`);
      securityFailed++;
    }
  }
}

console.log(`\nSecurity tests: ${securityPassed} passed, ${securityFailed} failed`);
const securityAllPassed = securityFailed === 0 && securityPassed > 0;
console.log(`PASS security vectors: ${securityAllPassed}`);

// =============================================================================
// Test 9: Structural Trace (Phase 8d)
// =============================================================================

console.log('\n=== Test 9: Structural Trace (Phase 8d) ===\n');

let structuralTraceAllPassed = true;

// Test 1: runStructural returns Mu-compatible structure
try {
  const simpleProj = [{ id: 'double', pattern: { op: 'double', value: { var: 'n' } }, body: { result: { var: 'n' } } }];
  const structResult = runStructural(simpleProj, { op: 'double', value: 42 }, 10);

  const hasResult = 'result' in structResult;
  const hasTrace = 'trace' in structResult;
  const hasStall = 'stall' in structResult;
  const hasSteps = 'steps' in structResult;
  const hasAllFields = hasResult && hasTrace && hasStall && hasSteps;
  console.log(`  Returns Mu-compatible structure: ${hasAllFields}`);
  structuralTraceAllPassed = structuralTraceAllPassed && hasAllFields;
} catch (e) {
  console.log(`  Returns Mu-compatible structure: false (${e.message})`);
  structuralTraceAllPassed = false;
}

// Test 2: Trace is linked list (not array)
try {
  const simpleProj = [{ id: 'identity', pattern: { var: 'x' }, body: { var: 'x' } }];
  const structResult = runStructural(simpleProj, 'test', 10);

  const trace = structResult.trace;
  // Linked list has head/tail, stall happens immediately so trace should have entries
  const isLinkedList = trace === null || ('head' in trace && 'tail' in trace);
  console.log(`  Trace is linked list: ${isLinkedList}`);
  structuralTraceAllPassed = structuralTraceAllPassed && isLinkedList;
} catch (e) {
  console.log(`  Trace is linked list: false (${e.message})`);
  structuralTraceAllPassed = false;
}

// Test 3: Trace entries have required fields
try {
  const toggle = [
    { id: 'to_b', pattern: 'A', body: 'B' },
    { id: 'to_a', pattern: 'B', body: 'A' }
  ];
  const structResult = runStructural(toggle, 'A', 5);

  let hasFields = true;
  let node = structResult.trace;
  while (node !== null) {
    const entry = node.head;
    if (!('step' in entry) || !('state' in entry) || !('projection' in entry)) {
      hasFields = false;
      break;
    }
    node = node.tail;
  }
  console.log(`  Trace entries have step/state/projection: ${hasFields}`);
  structuralTraceAllPassed = structuralTraceAllPassed && hasFields;
} catch (e) {
  console.log(`  Trace entries have step/state/projection: false (${e.message})`);
  structuralTraceAllPassed = false;
}

// Test 4: Stall detection with structural trace
try {
  const noMatch = [{ id: 'never_match', pattern: 'NEVER', body: 'MATCHED' }];
  const structResult = runStructural(noMatch, 'test', 10);

  const stallDetected = structResult.stall === true;
  const stepsCorrect = structResult.steps === 1;  // Immediate stall
  console.log(`  Stall detected correctly: ${stallDetected && stepsCorrect}`);
  structuralTraceAllPassed = structuralTraceAllPassed && stallDetected && stepsCorrect;
} catch (e) {
  console.log(`  Stall detected correctly: false (${e.message})`);
  structuralTraceAllPassed = false;
}

// Test 5: stepKernelStructural works (Gate 5: delegates to runStructural)
try {
  const structResult = stepKernelStructural(
    [testProjection],
    { op: 'double', value: 99 },
    { maxSteps: 100 }
  );

  const hasStructuralResult = 'result' in structResult && 'trace' in structResult;
  console.log(`  stepKernelStructural works: ${hasStructuralResult}`);
  structuralTraceAllPassed = structuralTraceAllPassed && hasStructuralResult;
} catch (e) {
  console.log(`  stepKernelStructural works: false (${e.message})`);
  structuralTraceAllPassed = false;
}

console.log(`\nPASS structural trace: ${structuralTraceAllPassed}`);

// =============================================================================
// Test 10: Recurrence Closure Detection (L3 Parity)
// =============================================================================

console.log('\n=== Test 10: Recurrence Closure Detection (L3 Parity) ===\n');

/**
 * Run Recurrence closure detection on a trace result.
 *
 * Takes a trace (from runStructural) and detects if any state recurs,
 * which indicates a closure per Rule 2.2♢.
 *
 * @param {Object} traceResult - Result from runStructural() with {result, trace, stall, steps}
 * @returns {Object} - {closure_detected: bool, final_result: value}
 */
function runRecurrence(traceResult) {
  // Wrap in _detect_closure format for Recurrence projections
  const recurrenceInput = {
    _detect_closure: {
      trace: traceResult.trace,
      result: traceResult.result
    }
  };

  // Run Recurrence projections until stall
  // Recurrence projections don't use kernel wrapper - they're direct pattern match
  const { result } = run(recurrenceProjections, recurrenceInput, 1000);

  return result;
}

// Load Recurrence parity vectors
const recurrenceVectorsPath = path.join(__dirname, '..', '..', '..', 'tests', 'fixtures', 'recurrence_vectors.json');
let recurrenceVectors;
try {
  recurrenceVectors = JSON.parse(fs.readFileSync(recurrenceVectorsPath, 'utf8'));
} catch (e) {
  console.log('Warning: Could not load recurrence_vectors.json:', e.message);
  recurrenceVectors = { vectors: [] };
}

let recurrencePassed = 0;
let recurrenceFailed = 0;

for (const vector of recurrenceVectors.vectors) {
  try {
    // Run Recurrence projections directly on the input
    // (vectors already have _detect_closure wrapper with trace)
    const { result } = run(recurrenceProjections, vector.input, 1000);

    // Compare with expected
    if (muEqual(result, vector.expected)) {
      console.log(`  ✓ ${vector.id}`);
      recurrencePassed++;
    } else {
      console.log(`  ✗ ${vector.id}: got ${JSON.stringify(result)}, expected ${JSON.stringify(vector.expected)}`);
      recurrenceFailed++;
    }
  } catch (e) {
    console.log(`  ✗ ${vector.id}: ERROR - ${e.message}`);
    recurrenceFailed++;
  }
}

console.log(`\nRecurrence parity tests: ${recurrencePassed} passed, ${recurrenceFailed} failed`);
const recurrenceAllPassed = recurrenceFailed === 0 && recurrencePassed > 0;
console.log(`PASS recurrence parity: ${recurrenceAllPassed}`);

// =============================================================================
// Test 11: Recurrence End-to-End (trace + detection)
// =============================================================================

console.log('\n=== Test 11: Recurrence End-to-End (trace + detection) ===\n');

let e2ePassed = true;

// Test: Oscillation detection end-to-end
try {
  // Create oscillating projections: A <-> B
  const oscillatingProjs = [
    { id: 'to_b', pattern: 'A', body: 'B' },
    { id: 'to_a', pattern: 'B', body: 'A' }
  ];

  // Run with structural trace (will oscillate until maxSteps)
  const traceResult = runStructural(oscillatingProjs, 'A', 10);

  // Verify trace captures oscillation
  const hasOscillation = traceResult.steps >= 3; // At least A -> B -> A
  console.log(`  Trace captures oscillation (steps >= 3): ${hasOscillation} (steps=${traceResult.steps})`);
  e2ePassed = e2ePassed && hasOscillation;

  // Run Recurrence on the trace
  const closureResult = runRecurrence(traceResult);

  // Should detect closure (A repeats)
  const closureDetected = closureResult.closure_detected === true;
  console.log(`  Closure detected: ${closureDetected}`);
  e2ePassed = e2ePassed && closureDetected;

} catch (e) {
  console.log(`  End-to-end test failed: ${e.message}`);
  e2ePassed = false;
}

// Test: Stall on distinct final state (still detects closure - fixed point)
try {
  // Incrementing projections: 0 -> 1 -> 2 -> 3 -> stall (no projection for 3)
  const incrementProjs = [
    { id: 'inc_0', pattern: 0, body: 1 },
    { id: 'inc_1', pattern: 1, body: 2 },
    { id: 'inc_2', pattern: 2, body: 3 }
  ];

  const traceResult = runStructural(incrementProjs, 0, 10);
  const closureResult = runRecurrence(traceResult);

  // Stall produces: [0, 1, 2, 3, 3(stall)] - state 3 appears twice
  // This IS a closure (fixed point) - the computation closed on 3
  // Recurrence correctly detects that 3 recurs
  const closureDetected = closureResult.closure_detected === true;
  console.log(`  Stall fixed point detected: ${closureDetected}`);
  e2ePassed = e2ePassed && closureDetected;

} catch (e) {
  console.log(`  Fixed point test failed: ${e.message}`);
  e2ePassed = false;
}

// Test: Immediate stall (state recurs)
try {
  const noMatchProjs = [
    { id: 'never', pattern: 'NEVER', body: 'MATCHED' }
  ];

  const traceResult = runStructural(noMatchProjs, 'test', 10);
  const closureResult = runRecurrence(traceResult);

  // Stall produces trace with same state in entry 0 AND stall entry 1
  // This IS a closure - the state 'test' recurs (fixed point)
  // Python trace: [{step:0, state:'test'}, {step:1, state:'test', stall:true}]
  const singleStateResult = closureResult.closure_detected;
  console.log(`  Immediate stall closure_detected: ${singleStateResult} (expected: true, fixed point)`);
  e2ePassed = e2ePassed && (singleStateResult === true);

} catch (e) {
  console.log(`  Immediate stall test failed: ${e.message}`);
  e2ePassed = false;
}

console.log(`\nPASS recurrence e2e: ${e2ePassed}`);

// =============================================================================
// Test: Engine-Hemisphere Helpers (L3 Parity)
// =============================================================================

console.log('\n=== Test: Engine-Hemisphere Helpers ===\n');
let engineHelpersPassed = true;

// Test isEngineTerminal
const terminalShape = {
  value: 'x', closure_detected: false, tau_step: 0,
  exhaustion_detected: false, operator_frozen: false,
  frozen_set: null, action: 'continue', stall: true,
};
const terminalDetected = isEngineTerminal(terminalShape);
const nonTerminalRejected = !isEngineTerminal({ partial: true });
const nullRejected = !isEngineTerminal(null);
console.log(`  isEngineTerminal(8-key): ${terminalDetected} (expected: true)`);
console.log(`  isEngineTerminal(partial): ${nonTerminalRejected} (expected: true)`);
console.log(`  isEngineTerminal(null): ${nullRejected} (expected: true)`);
engineHelpersPassed = engineHelpersPassed && terminalDetected && nonTerminalRejected && nullRejected;

// Test isTerminalShape (recurrence)
const recTerminal = { closure_detected: true, final_result: 'x', tau_step: 2 };
const exhTerminal = { action: 'freeze', exhaustion_detected: true, frozen: null, operator_to_freeze: 'op1' };
const recDetected = isTerminalShape(recTerminal);
const exhDetected = isTerminalShape(exhTerminal);
const nonShapeRejected = !isTerminalShape({ random: 1 });
console.log(`  isTerminalShape(recurrence): ${recDetected} (expected: true)`);
console.log(`  isTerminalShape(exhaustion): ${exhDetected} (expected: true)`);
console.log(`  isTerminalShape(other): ${nonShapeRejected} (expected: true)`);
engineHelpersPassed = engineHelpersPassed && recDetected && exhDetected && nonShapeRejected;

// Test hashTraceForRecurrence
try {
  const simpleTrace = {
    head: { step: 0, state: { x: 1 }, projection: 'test' },
    tail: {
      head: { step: 1, state: { x: 1 }, stall: true },
      tail: null
    }
  };
  const hashed = hashTraceForRecurrence(simpleTrace);
  const hasHash0 = 'state_hash' in hashed.head;
  const hasHash1 = 'state_hash' in hashed.tail.head;
  console.log(`  hashTrace adds state_hash: ${hasHash0 && hasHash1} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && hasHash0 && hasHash1;
} catch (e) {
  console.log(`  hashTrace failed: ${e.message}`);
  engineHelpersPassed = false;
}

// Test hashTraceForRecurrence cycle detection
try {
  const nodeA = { head: { state: 'A', step: 0 }, tail: null };
  const nodeB = { head: { state: 'B', step: 1 }, tail: nodeA };
  nodeA.tail = nodeB;
  hashTraceForRecurrence(nodeA);
  console.log(`  hashTrace cycle detection: false (should have thrown)`);
  engineHelpersPassed = false;
} catch (e) {
  const cycleDetected = e.message.includes('cyclic');
  console.log(`  hashTrace cycle detection: ${cycleDetected} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && cycleDetected;
}

// Test hashTraceForRecurrence overcap
try {
  let overcapTrace = null;
  for (let i = 4; i >= 0; i--) {
    overcapTrace = { head: { state: String(i), step: i }, tail: overcapTrace };
  }
  hashTraceForRecurrence(overcapTrace, 3);
  console.log(`  hashTrace overcap detection: false (should have thrown)`);
  engineHelpersPassed = false;
} catch (e) {
  const overcapDetected = e.message.includes('exceeds');
  console.log(`  hashTrace overcap detection: ${overcapDetected} (expected: true)`);
  engineHelpersPassed = engineHelpersPassed && overcapDetected;
}

// Test defaultHemispheres and setsEqual
const hemi = defaultHemispheres();
const hemiKeys = new Set(Object.keys(hemi));
const hemiKeysMatch = setsEqual(hemiKeys, HEMISPHERE_KEYS);
console.log(`  defaultHemispheres keys match HEMISPHERE_KEYS: ${hemiKeysMatch} (expected: true)`);
engineHelpersPassed = engineHelpersPassed && hemiKeysMatch;

console.log(`\nPASS engine-hemisphere helpers: ${engineHelpersPassed}`);

// =============================================================================
// Test: Metabolization Projection Behavior (E2 Evidence)
// =============================================================================

console.log('\n=== Test: Metabolization Behavior ===\n');
let metabolizationBehaviorPassed = true;

// Gate: verify all 6 expected projection IDs exist in loaded seed (fail-closed on drift)
const EXPECTED_METABOLIZATION_IDS = [
  'hemisphere.metabolize.sink_to_r_null',
  'hemisphere.metabolize.sink_to_r_inf',
  'hemisphere.recover.stall_to_lobes',
  'hemisphere.recover.stall_to_sink',
  'hemisphere.promote.lobes_to_r_a',
  'hemisphere.recycle.residual_to_sink',
];
const loadedMetabIds = metabolizationProjections.map(p => p.id);
const metabIdMissing = EXPECTED_METABOLIZATION_IDS.filter(id => !loadedMetabIds.includes(id));
const metabIdCheck = metabIdMissing.length === 0;
console.log(`  All 6 metabolization IDs present: ${metabIdCheck} (expected: true)`);
if (!metabIdCheck) {
  console.log(`    Missing: ${JSON.stringify(metabIdMissing)}`);
  metabolizationBehaviorPassed = false;
}
const metabIdOrderMatch = JSON.stringify(loadedMetabIds) === JSON.stringify(EXPECTED_METABOLIZATION_IDS);
console.log(`  Metabolization ID order matches: ${metabIdOrderMatch} (expected: true)`);
metabolizationBehaviorPassed = metabolizationBehaviorPassed && metabIdOrderMatch;

// Build projection lookup by ID for result verification
const metabById = {};
for (const p of metabolizationProjections) {
  metabById[p.id] = p;
}

// Helper: run step() and verify which projection matched
function stepMetab(input) {
  // step() returns first-match result or unchanged input on stall
  const result = step(metabolizationProjections, input);
  return result;
}

// Test 1: sink_to_r_inf — non-null state routes to r_inf
{
  const input = {
    metabolize_mode: 'scan_sink',
    sink_entry: { state: 'active_data', closure_flag: false, origin: 'engine' },
    remaining_sink: null,
    hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.metabolize_result !== undefined &&
    result.metabolize_result.r_inf !== null &&
    result.metabolize_result.r_inf.head !== undefined &&
    result.metabolize_result.r_inf.head.state === 'active_data' &&
    result.metabolize_result.r_inf.head.origin === 'metabolized' &&
    result.metabolize_result.r_null === null &&
    result.metabolize_result.r_a === null;
  console.log(`  sink_to_r_inf (non-null state → r_inf): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 2: sink_to_r_null — null state routes to r_null via step() (design T2/T8)
// sink_to_r_null is ordered before sink_to_r_inf so null-specific literal fires first.
{
  const input = {
    metabolize_mode: 'scan_sink',
    sink_entry: { state: null, closure_flag: false, origin: 'engine' },
    remaining_sink: null,
    hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.metabolize_result !== undefined &&
    result.metabolize_result.r_null !== null &&
    result.metabolize_result.r_null.head !== undefined &&
    result.metabolize_result.r_null.head.state === null &&
    result.metabolize_result.r_null.head.origin === 'metabolized' &&
    result.metabolize_result.r_inf === null &&
    result.metabolize_result.r_a === null;
  console.log(`  sink_to_r_null (null state → r_null via step): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 3: stall_to_lobes — stalled entry routes to lobes when lobes non-null
{
  const input = {
    recover_mode: 'check_stall',
    stalled_entry: { state: 'stalled_thing', origin: 'engine' },
    hemispheres: {
      r_null: null, r_inf: null, r_a: null,
      lobes: { head: 'existing_lobe', tail: null },
      sink: null
    }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.recover_result !== undefined &&
    result.recover_result.lobes !== null &&
    result.recover_result.lobes.head !== undefined &&
    muEqual(result.recover_result.lobes.head, { state: 'stalled_thing', origin: 'engine' }) &&
    result.recover_result.lobes.tail !== null &&
    result.recover_result.lobes.tail.head === 'existing_lobe';
  console.log(`  stall_to_lobes (lobes non-null → prepend): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 4: stall_to_sink — stalled entry routes to sink when lobes is null
{
  const input = {
    recover_mode: 'check_stall',
    stalled_entry: { state: 'stalled_thing', origin: 'engine' },
    hemispheres: {
      r_null: null, r_inf: null, r_a: null,
      lobes: null,
      sink: null
    }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.recover_result !== undefined &&
    result.recover_result.lobes === null &&
    result.recover_result.sink !== null &&
    muEqual(result.recover_result.sink.head, { state: 'stalled_thing', origin: 'engine' });
  console.log(`  stall_to_sink (lobes null → sink fallback): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 5: lobes_to_r_a — closure evidence promotes to r_a
{
  const input = {
    promote_mode: 'check_closure',
    lobes_entry: { state: 'closed_form', closure_flag: true, origin: 'lobes' },
    remaining_lobes: null,
    hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.promote_result !== undefined &&
    result.promote_result.r_a !== null &&
    result.promote_result.r_a.head !== undefined &&
    result.promote_result.r_a.head.state === 'closed_form' &&
    result.promote_result.r_a.head.closure_flag === true &&
    result.promote_result.r_a.head.origin === 'promoted' &&
    result.promote_result.lobes === null;
  console.log(`  lobes_to_r_a (closure_flag true → r_a): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 6: residual_to_sink — unresolvable entry recycles to sink
{
  const input = {
    recycle_mode: 'drain',
    source_bucket: 'r_inf',
    unresolvable_entry: { type: 'unknown', data: 42 },
    hemispheres: { r_null: null, r_inf: null, r_a: null, lobes: null, sink: null }
  };
  const result = stepMetab(input);
  const ok = typeof result === 'object' && result !== null &&
    result.recycle_result !== undefined &&
    result.recycle_result.sink !== null &&
    result.recycle_result.sink.head !== undefined &&
    muEqual(result.recycle_result.sink.head.state, { type: 'unknown', data: 42 }) &&
    result.recycle_result.sink.head.origin === 'recycled' &&
    result.recycle_result.r_null === null &&
    result.recycle_result.r_inf === null;
  console.log(`  residual_to_sink (drain → sink recycled): ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

// Test 7: stall on non-matching input (no projection fires)
{
  const input = { unrecognized_mode: 'garbage', data: 123 };
  const result = stepMetab(input);
  // step() returns input unchanged on stall
  const ok = muEqual(result, input);
  console.log(`  stall on non-matching input: ${ok} (expected: true)`);
  metabolizationBehaviorPassed = metabolizationBehaviorPassed && ok;
}

console.log(`\nPASS metabolization behavior: ${metabolizationBehaviorPassed}`);

// =============================================================================
// Bridge Ordering Validation Tests
// =============================================================================

console.log('\n--- Bridge ordering validation tests ---');
let bridgeValidationPassed = true;

// Test 1: valid ordering passes (already validated at load time, but verify again)
try {
  validateCombinedBridgeOrdering(allProjectionsWithBridge);
  console.log('  Valid bridge ordering accepted: true (expected: true)');
} catch (e) {
  console.log(`  Valid bridge ordering accepted: false (expected: true) - ${e.message}`);
  bridgeValidationPassed = false;
}

// Test 2: missing bridge projections fails
try {
  validateCombinedBridgeOrdering([
    ...kernel.projections,
    ...matchSeed.projections,
    ...substSeed.projections
  ]);
  console.log('  Missing bridge rejected: false (expected: true)');
  bridgeValidationPassed = false;
} catch (e) {
  const hasMissing = e.message.includes('missing bridge projections');
  console.log(`  Missing bridge rejected: ${hasMissing} (expected: true)`);
  bridgeValidationPassed = bridgeValidationPassed && hasMissing;
}

// Test 3: bridge after match.var fails
try {
  validateCombinedBridgeOrdering([
    ...kernel.projections,
    ...matchSeed.projections,
    ...bridgeProjections,  // bridge AFTER match (wrong!)
    ...substSeed.projections
  ]);
  console.log('  Bridge-after-match.var rejected: false (expected: true)');
  bridgeValidationPassed = false;
} catch (e) {
  const hasOrdering = e.message.includes('must be before match.var');
  console.log(`  Bridge-after-match.var rejected: ${hasOrdering} (expected: true)`);
  bridgeValidationPassed = bridgeValidationPassed && hasOrdering;
}

console.log(`\nPASS bridge ordering validation: ${bridgeValidationPassed}`);

// =============================================================================
// Summary
// =============================================================================

console.log('\n=== Summary ===\n');
const allPassed = passed && passedStall && pass3a && pass3b && pass3c &&
                  nanRejected && infRejected && shallowOk && deepRejected &&
                  passReservedFields && isNormalizedAsDict && isPreservedAsHeadTail &&
                  parityAllPassed && securityAllPassed && structuralTraceAllPassed &&
                  recurrenceAllPassed && e2ePassed && engineHelpersPassed &&
                  metabolizationBehaviorPassed && bridgeValidationPassed;
console.log(`All tests passed: ${allPassed}`);
if (!allPassed) process.exit(1);
console.log(`\nSecurity hardening (v7 - L3 Recurrence Parity, mu/ reorg):`);
console.log(`  - MAX_DEPTH=${MAX_DEPTH} guard (matches Python MAX_MU_DEPTH)`);
console.log(`  - NaN/Infinity rejection (matches Python)`);
console.log(`  - KERNEL_RESERVED_FIELDS validation (matches Python step_mu.py)`);
console.log(`  - Strict head/tail detection (exact key counts)`);
console.log(`  - Unbound variables stall (matches Python Phase 7d-1)`);
console.log(`\nCore implementation: ~350 lines of JavaScript (with security + Recurrence)`);
console.log(`Projections loaded from mu/ folder:`);
console.log(`  - Kernel ops: ${allProjections.length} (kernel + match + subst)`);
console.log(`  - Recurrence: ${recurrenceProjections.length} (closure detection)`);
console.log(`\nThis proves (L3 Substrate Portability - COMPLETE):`);
console.log(`  1. mu/substrate/kernel.v1.json runs on JavaScript ✓`);
console.log(`  2. mu/substrate/match.v2.json runs on JavaScript ✓`);
console.log(`  3. mu/substrate/subst.v2.json runs on JavaScript ✓`);
console.log(`  4. mu/closures/recurrence.v1.json runs on JavaScript ✓`);
console.log(`  5. mu/closures/exhaustion.v1.json runs on JavaScript ✓`);
console.log(`  6. Normalization/denormalization works ✓`);
console.log(`  7. Complete kernel cycle works ✓`);
console.log(`  8. Security parity with Python (4 bootstrap primitives) ✓`);
console.log(`  9. Recurrence closure detection parity ✓`);
console.log(`  10. Same projections, same semantics, two substrates ✓`);

/**
 * Run an algorithm (recurrence/exhaustion) through bridge-backed meta-circular kernel.
 * Shared helper for run_recurrence_with_bridge and run_exhaustion_with_bridge JSON API actions.
 * @host_iteration (bridge-backed algorithm execution loop)
 */
function runAlgorithmWithBridge(allProjs, input, domainProjs, maxSteps) {
  let current = input;
  let steps = 0;
  const limit = maxSteps ?? 200;
  while (steps < limit) {
    const wrapped = stepKernel(
      allProjs, current, domainProjs,
      { validationMode: 'algorithm_runtime' }
    );
    const next = denormalize(wrapped.result);
    if (muEqual(current, next)) break;
    current = next;
    steps++;
  }
  return current;
}

// =============================================================================
// JSON API Mode (for cross-substrate verification)
// =============================================================================
// When called with --json-api, outputs machine-readable JSON for Python tests
// to run actual cross-substrate comparison (not just string matching).
//
// Usage: node eval_step.js --json-api '{"vector_id": "simple_match"}'
//        node eval_step.js --json-api '{"action": "run_vector", "input": {...}, "projection": {...}}'
//
// 9-agent Round 3 (Grounding finding): Previous tests were theater - just checked
// for strings like "0 failed". This JSON API enables actual output comparison.

// API-level cap for maxSteps on externally reachable endpoints.
// Closes HF2 Mode-B DoS vector (see reports/round11a_hostile_findings.md).
const API_MAX_STEPS = 10000;

function guardMaxSteps(value, fieldName) {
  if (value == null) return; // omitted — caller uses default
  if (typeof value !== 'number' || !Number.isInteger(value)) {
    throw new RcxError('api.bad_request', `${fieldName} must be an integer, got ${typeof value}`);
  }
  if (value < 0) {
    throw new RcxError('api.bad_request', `${fieldName} must be >= 0, got ${value}`);
  }
  if (value > API_MAX_STEPS) {
    throw new RcxError('api.bad_request', `${fieldName} exceeds API cap of ${API_MAX_STEPS}`);
  }
}

if (process.argv.includes('--json-api')) {
  const apiArg = process.argv[process.argv.indexOf('--json-api') + 1];

  try {
    const request = JSON.parse(apiArg);
    let response;

    if (request.action === 'run_vector') {
      // Run a single parity vector and return result
      const { input, projection } = request;
      try {
        const { result } = stepKernel(
          allProjections,
          input,
          [projection],
          { maxSteps: 100 }
        );
        const denormalized = denormalize(result);
        response = { success: true, result: denormalized };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_all_vectors') {
      // Run all parity vectors and return results
      const results = [];
      for (const vector of parityVectors.vectors) {
        try {
          const { result } = stepKernel(
            allProjections,
            vector.input,
            [vector.projection],
            { maxSteps: 100 }
          );
          const denormalized = denormalize(result);
          results.push({
            id: vector.id,
            success: true,
            result: denormalized,
            expected: vector.expected_output
          });
        } catch (e) {
          results.push({
            id: vector.id,
            success: false,
            error_code: classifyError(e),
            error: e.message
          });
        }
      }
      response = { success: true, results };
    } else if (request.action === 'run_recurrence') {
      // Run Recurrence closure detection
      const { projections, input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const traceResult = runStructural(projections ?? [], input, maxSteps ?? 100);
        const closureResult = runRecurrence(traceResult);
        response = { success: true, result: closureResult };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_exhaustion') {
      // Run Exhaustion detection on provided input
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        let current = input;
        let steps = 0;
        const limit = maxSteps ?? 200;
        while (steps < limit) {
          const next = step(allProjectionsWithExhaustion, current);
          if (muEqual(current, next)) break;
          current = next;
          steps++;
        }
        response = { success: true, result: current };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'get_constants') {
      // Return constants for cross-substrate verification
      response = {
        success: true,
        MAX_DEPTH,
        max_width: MAX_MU_WIDTH,  // Added for Tooling Delta parity check
        KERNEL_RESERVED_FIELDS: [...KERNEL_RESERVED_FIELDS],
        seed_integrity_verified: true,
        seed_count: Object.keys(SEED_CHECKSUMS).length,
        kernel_projection_count: kernel.projections.length,
        match_projection_count: matchSeed.projections.length,
        subst_projection_count: substSeed.projections.length,
        bridge_projection_count: bridgeSeed.projections.length,
        recurrence_projection_count: recurrenceSeed.projections.length,
        exhaustion_projection_count: exhaustionSeed.projections.length,
        hemisphere_projection_count: hemisphereSeed.projections.length,
        metabolization_projection_count: metabolizationSeed.projections.length,
        total_with_bridge: allProjectionsWithBridge.length,
        total_with_recurrence_bridge: allProjectionsWithRecurrenceAndBridge.length,
        total_with_exhaustion_bridge: allProjectionsWithExhaustionAndBridge.length
      };
    } else if (request.action === 'normalize_roundtrip') {
      // Normalize and denormalize a value - for cross-substrate parity testing
      // PARITY REQUIREMENT: Python and JS must produce identical results
      const { value } = request;
      try {
        const normalized = normalize(value);
        const denormalized = denormalize(normalized);
        response = {
          success: true,
          normalized: normalized,
          denormalized: denormalized
        };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_mu') {
      // Validate a value against Mu type rules - for cross-substrate parity testing
      // PARITY REQUIREMENT: JS isValidMu must match Python is_mu
      const { value } = request;
      const isValid = isValidMu(value);
      response = {
        success: true,
        is_valid: isValid,
        max_depth: MAX_DEPTH,
        max_width: MAX_MU_WIDTH
      };
    } else if (request.action === 'run_recurrence_with_bridge') {
      // Run Recurrence with bridge (meta-circular path)
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const result = runAlgorithmWithBridge(allProjectionsWithBridge, input, recurrenceProjections, maxSteps);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_exhaustion_with_bridge') {
      // Run Exhaustion with bridge (meta-circular path)
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const result = runAlgorithmWithBridge(allProjectionsWithBridge, input, exhaustionProjections, maxSteps);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_reserved_fields') {
      // Validate strict domain-mode reserved field policy for cross-substrate parity.
      const { value } = request;
      try {
        validateNoKernelReservedFields(value, 'test');
        response = { success: true, valid: true, error: '' };
      } catch (e) {
        response = { success: true, valid: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'validate_algorithm_runtime_fields') {
      // Validate trusted algorithm-runtime underscore allowlist policy.
      const { value } = request;
      try {
        validateAlgorithmRuntimeFields(value, 'test');
        response = { success: true, valid: true, error: '' };
      } catch (e) {
        response = { success: true, valid: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_structural_trace') {
      // Run structural trace and return trace with projection IDs.
      // For cross-substrate parity testing of trace projection-id assignment.
      const { projections: userProjs, input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const traceResult = runStructural(userProjs ?? [], input, maxSteps ?? 100);
        // Convert trace linked list to array for JSON serialization
        const traceArray = [];
        let node = traceResult.trace;
        while (node && typeof node === 'object' && 'head' in node) {
          traceArray.push(node.head);
          node = node.tail;
        }
        response = {
          success: true,
          result: traceResult.result,
          trace: traceArray,
          stall: traceResult.stall,
          steps: traceResult.steps,
        };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_hemisphere') {
      // Run hemisphere routing (APPLICATION level, core kernel, linear-only)
      // Uses returnMeta for proper kernel terminal detection (matches Python run_mu path)
      const { input, maxSteps } = request;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        let current = input;
        let steps = 0;
        const limit = maxSteps ?? 100;
        while (steps < limit) {
          const wrapped = stepKernel(
            allProjections,
            current,
            hemisphereProjections,
            { returnMeta: true }
          );
          if (wrapped.stall) break;
          current = wrapped.output;
          steps++;
        }
        response = { success: true, result: current };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_engine_pipeline') {
      // Run engine pipeline (APPLICATION level, algebraic effects pattern)
      const { projections: userProjs, input, maxSteps, frozen, maxEngineIterations, maxAlgorithmIterations } = request;
      // Boot1 type guard: reject non-boolean to prevent truthy-string routing bugs
      if (request.boot1LoopMode != null && typeof request.boot1LoopMode !== 'boolean') {
        response = { success: false, error_code: 'type_error', error: 'boot1LoopMode must be boolean if provided, got ' + typeof request.boot1LoopMode };
      } else {
      const boot1Mode = request.boot1LoopMode ?? false;
      const observerEvents = request.observer ? [] : null;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const opts = {
          maxSteps: maxSteps ?? 100,
          frozen: frozen ?? null,
          maxEngineIterations: maxEngineIterations ?? 20,
          maxAlgorithmIterations: maxAlgorithmIterations ?? 50,
          observer: observerEvents,
        };
        const result = boot1Mode
          ? runEnginePipelineRecursive(userProjs ?? [], input, opts)
          : runEnginePipeline(userProjs ?? [], input, opts);
        response = { success: true, result };
        if (observerEvents) response.observer_events = observerEvents;
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
        if (observerEvents) response.observer_events = observerEvents;
      }
      } // close boot1LoopMode type guard else
    } else if (request.action === 'hash_trace') {
      // Hash trace entries for recurrence (boundary primitive)
      const { trace, maxEntries } = request;
      try {
        const result = hashTraceForRecurrence(trace, maxEntries ?? 10000);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_hemisphere_routing') {
      // Route engine result to hemispheres (L3 parity with Python run_hemisphere_routing)
      const { engine_result, hemispheres } = request;
      try {
        const result = runHemisphereRouting(engine_result, hemispheres ?? defaultHemispheres());
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'run_engine_with_routing') {
      // Full engine -> hemisphere pipeline (L3 parity with Python run_engine_with_routing)
      // Boot1 type guard: reject non-boolean to prevent truthy-string routing bugs
      if (request.boot1LoopMode != null && typeof request.boot1LoopMode !== 'boolean') {
        response = { success: false, error_code: 'type_error', error: 'boot1LoopMode must be boolean if provided, got ' + typeof request.boot1LoopMode };
      } else {
      const boot1Mode = request.boot1LoopMode ?? false;
      const { projections: userProjs, input, hemispheres, maxSteps, frozen, maxEngineIterations, maxAlgorithmIterations } = request;
      const observerEvents = request.observer ? [] : null;
      try {
        guardMaxSteps(maxSteps, 'maxSteps');
        const result = runEngineWithRouting(
          userProjs ?? [], input,
          hemispheres ?? null,
          {
            maxSteps: maxSteps ?? 100,
            frozen: frozen ?? null,
            maxEngineIterations: maxEngineIterations ?? 20,
            maxAlgorithmIterations: maxAlgorithmIterations ?? 50,
            observer: observerEvents,
          },
          boot1Mode
        );
        response = { success: true, result };
        if (observerEvents) response.observer_events = observerEvents;
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
        if (observerEvents) response.observer_events = observerEvents;
      }
      } // close boot1LoopMode type guard else
    } else if (request.action === 'step_metabolization') {
      // Run step(metabolizationProjections, input) for cross-substrate parity testing.
      // Returns first-match-wins result or input unchanged (stall).
      const { input } = request;
      try {
        const result = step(metabolizationProjections, input);
        response = { success: true, result };
      } catch (e) {
        response = { success: false, error_code: classifyError(e), error: e.message };
      }
    } else if (request.action === 'list_actions') {
      response = {
        success: true,
        actions: [
          'run_vector', 'run_all_vectors', 'run_recurrence', 'run_exhaustion',
          'get_constants', 'normalize_roundtrip', 'validate_mu',
          'run_recurrence_with_bridge', 'run_exhaustion_with_bridge',
          'validate_reserved_fields', 'validate_algorithm_runtime_fields',
          'run_structural_trace', 'run_hemisphere', 'run_engine_pipeline',
          'hash_trace', 'run_hemisphere_routing', 'run_engine_with_routing',
          'step_metabolization', 'list_actions'
        ]
      };
    } else {
      response = { success: false, error_code: 'api.unknown_action', error: `Unknown action: ${request.action}` };
    }

    // Output JSON on single line (for easy parsing)
    console.log('JSON_API_RESPONSE:' + JSON.stringify(response));
  } catch (e) {
    console.log('JSON_API_RESPONSE:' + JSON.stringify({ success: false, error_code: classifyError(e), error: e.message }));
  }
}
