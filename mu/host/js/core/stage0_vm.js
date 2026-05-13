'use strict';
/**
 * Stage0 VM: data-driven execution of Stage0 IR bundles.
 *
 * JS parity port of mu/host/python/rcx_pi/selfhost/stage0_vm.py.
 * This VM executes derived bundles using a tiny set of opcodes.
 * The VM is intentionally dumb — all semantic knowledge lives in the
 * bundle data, not in the VM.
 *
 * P7-a prototype origin. S1-B: VM path is now primary for match.v2/subst.v2 (cutover active, shadow disabled).
 *
 * Stage0 IR v1 numeric contract: int supported, float UNSUPPORTED.
 * Float rejection enforced by validateBundle. classifyKind retains
 * float classification for future IR versions but v1 bundles must
 * not rely on it. JS Number.isInteger(1.0) === true means int/float
 * distinction is not portable — hence float exclusion in v1.
 * Bundle JSON must use integer literals (1 not 1.0).
 */

// ---------------------------------------------------------------------------
// Resource bounds
// ---------------------------------------------------------------------------
const MAX_VM_PROGRAMS = 64;
const MAX_VM_OPS_PER_STEP = 1024;
const MAX_TEMPLATE_DEPTH = 32;
const MAX_PATH_DEPTH = 64;
const muContainers = require('./container_factory');

// ---------------------------------------------------------------------------
// Opcode schemas (single source of truth for per-opcode field validation)
// ---------------------------------------------------------------------------
const OPCODE_SCHEMAS = Object.freeze({
  'assert_focus_kind':         { required: new Set(['path', 'kind']),          optional: new Set() },
  'assert_key_profile':        { required: new Set(['path', 'required']),      optional: new Set(['optional']) },
  'check_equal':               { required: new Set(['path', 'value']),         optional: new Set() },
  'check_captured_equal':      { required: new Set(['path', 'capture_name']),  optional: new Set() },
  'capture_path':              { required: new Set(['path', 'name']),          optional: new Set() },
  'write_path':                { required: new Set(['template']),              optional: new Set() },
  'return_projection_success': { required: new Set(),                          optional: new Set() },
  'return_projection_fail':    { required: new Set(),                          optional: new Set() },
  'check_exists':              { required: new Set(['path']),                  optional: new Set() },
});

const GLOBAL_OP_OPTIONAL = new Set(['source_map']);

const KNOWN_OPCODES = new Set(Object.keys(OPCODE_SCHEMAS));

// ---------------------------------------------------------------------------
// Kind / template enums
// ---------------------------------------------------------------------------
const SUPPORTED_KINDS = new Set(['null', 'bool', 'int', 'string', 'dict', 'list']);

const TEMPLATE_KINDS = new Set([
  'literal', 'capture_ref', 'object', 'list',
]);

const TEMPLATE_SCHEMAS = Object.freeze({
  'literal':     new Set(['value']),
  'capture_ref': new Set(['name']),
  'object':      new Set(['fields']),
  'list':        new Set(['items']),
});

const _OPT_ENTRY_ALLOWED_KEYS = new Set(['key', 'allowed_values']);

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------
class Stage0VMError extends Error {
  constructor(message) {
    super(message);
    this.name = 'Stage0VMError';
  }
}

// ---------------------------------------------------------------------------
// Plain-object check (accepts both Object.prototype and null prototype)
// muCopy uses Object.create(null) for security, JSON.parse uses Object.prototype.
// Both are valid Mu dicts. Non-plain objects (Set, Map, Date, etc.) are rejected.
// ---------------------------------------------------------------------------
function _isPlainObject(v) {
  if (v === null || typeof v !== 'object') return false;
  try {
    if (Array.isArray(v)) return false;
    const proto = Object.getPrototypeOf(v);
    return proto === Object.prototype || proto === null;
  } catch (_) {
    return false;
  }
}

// Plain-array check (rejects Array subclasses — parity with Python type(x) is list)
// JSON.parse only produces plain arrays; Array subclasses are non-Mu host artifacts.
function _isPlainArray(v) {
  try {
    return Array.isArray(v) && Object.getPrototypeOf(v) === Array.prototype;
  } catch (_) {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------
function resolvePath(root, path) {
  if (path.length < 2 || path[0] !== 'focus' || path[1] !== 'root') {
    throw new Stage0VMError(
      `Path must start with ['focus', 'root'], got ${JSON.stringify(path)}`);
  }
  let current = root;
  // Hostile input roots (Proxy, accessor-backed) can throw during property
  // access. Treat any host error as "path not found" rather than leaking it.
  try {
    for (let i = 2; i < path.length; i++) {
      if (!_isPlainObject(current)) {
        return [null, false];
      }
      if (!Object.hasOwn(current, path[i])) {
        return [null, false];
      }
      current = current[path[i]];
    }
  } catch (_) {
    return [null, false];
  }
  return [current, true];
}

// ---------------------------------------------------------------------------
// Kind classification
// ---------------------------------------------------------------------------
function classifyKind(value) {
  // Wrapped in try-catch: _isPlainObject/_isPlainArray call
  // Object.getPrototypeOf which can throw on hostile Proxies.
  // Same discipline as resolvePath — fail-closed on host errors.
  try {
    if (value === null) return 'null';
    if (typeof value === 'boolean') return 'bool';
    if (typeof value === 'number') {
      return Number.isInteger(value) ? 'int' : 'float';
    }
    if (typeof value === 'string') return 'string';
    if (_isPlainArray(value)) return 'list';
    if (_isPlainObject(value)) return 'dict';
    return null;
  } catch (_) {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Structural equality
// ---------------------------------------------------------------------------
function muDeepEqual(a, b) {
  if (a === null) return b === null;
  if (b === null) return false;
  const ta = typeof a;
  const tb = typeof b;
  if (ta !== tb) return false;
  if (ta === 'boolean' || ta === 'string') return a === b;
  if (ta === 'number') {
    // int vs float distinction: both are 'number' in JS.
    // Use Number.isInteger to distinguish.
    if (Number.isInteger(a) !== Number.isInteger(b)) return false;
    return a === b && Object.is(a, b);
  }
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!muDeepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  if (ta === 'object') {
    // Both must be plain objects (not Set, Map, Date, etc.)
    if (!_isPlainObject(a)) return false;
    if (!_isPlainObject(b)) return false;
    const aKeys = Object.keys(a);
    const bKeys = Object.keys(b);
    if (aKeys.length !== bKeys.length) return false;
    for (const k of aKeys) {
      if (!Object.hasOwn(b, k)) return false;
      if (!muDeepEqual(a[k], b[k])) return false;
    }
    return true;
  }
  return false;
}

function safeMuDeepEqual(a, b) {
  // AST_OK: error boundary — translates host errors to Stage0VMError or fail-closed
  try {
    return muDeepEqual(a, b);
  } catch (e) {
    if (e instanceof RangeError) {
      throw new Stage0VMError(
        'Structural equality depth exceeded (recursion overflow)');
    }
    // Hostile Proxy traps, toString, getPrototypeOf etc. — treat as not-equal
    return false;
  }
}

// ---------------------------------------------------------------------------
// Structural deep copy (Mu values only, no external deps)
// ---------------------------------------------------------------------------
function muCopy(value, rejectNonMu = false, context = 'Deep copy') {
  if (value === null) return null;
  if (value === undefined) {
    if (rejectNonMu) {
      throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
    }
    return null;  // Mu has no undefined — canonicalize to null
  }
  if (_isPlainArray(value)) {
    try {
      if (rejectNonMu) {
        if (Object.getOwnPropertySymbols(value).length > 0) {
          throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
        }
        if (Object.keys(value).length !== value.length ||
            Object.getOwnPropertyNames(value).length !== value.length + 1) {
          throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
        }
        for (let i = 0; i < value.length; i++) {
          const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
          if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) {
            throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
          }
        }
      }
      return muContainers.list(value.map(item => muCopy(item, rejectNonMu, context)));  // Reject Array subclasses
    } catch (e) {
      if (e instanceof Stage0VMError) throw e;
      if (e instanceof RangeError) {
        let msg = 'Deep copy depth exceeded (recursion overflow)';
        if (context !== 'Deep copy') msg = `${context}: ${msg}`;
        throw new Stage0VMError(msg);
      }
      if (rejectNonMu) {
        throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
      }
      return null;
    }
  }
  if (_isPlainObject(value)) {
    try {
      const keys = Object.keys(value);
      if (rejectNonMu) {
        if (Object.getOwnPropertySymbols(value).length > 0 ||
            Object.getOwnPropertyNames(value).length !== keys.length) {
          throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
        }
        for (const k of keys) {
          const descriptor = Object.getOwnPropertyDescriptor(value, k);
          if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) {
            throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
          }
        }
      }
      const result = muContainers.record();
      for (const k of keys) {
        result[k] = muCopy(value[k], rejectNonMu, context);
      }
      return result;
    } catch (e) {
      if (e instanceof Stage0VMError) throw e;
      if (e instanceof RangeError) {
        let msg = 'Deep copy depth exceeded (recursion overflow)';
        if (context !== 'Deep copy') msg = `${context}: ${msg}`;
        throw new Stage0VMError(msg);
      }
      if (rejectNonMu) {
        throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
      }
      return null;
    }
  }
  // Exact-type check for Mu primitives (parity: Python _mu_copy)
  const t = typeof value;
  if (t === 'string' || t === 'boolean') return value;
  if (t === 'number') {
    if (rejectNonMu && value - value !== 0) {
      throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
    }
    return value;
  }
  if (rejectNonMu) {
    throw new Stage0VMError(`${context}: non-Mu value cannot be captured`);
  }
  // Non-Mu type (host object, Symbol, etc.) — fail-closed: return null
  return null;
}

function safeMuCopy(value, rejectNonMu = false, context = 'Deep copy') {
  // AST_OK: error boundary — translates ALL host errors to Stage0VMError (fail-closed)
  try {
    return muCopy(value, rejectNonMu, context);
  } catch (e) {
    if (e instanceof Stage0VMError) throw e;
    if (e instanceof RangeError) {
      let msg = 'Deep copy depth exceeded (recursion overflow)';
      if (context !== 'Deep copy') msg = `${context}: ${msg}`;
      throw new Stage0VMError(msg);
    }
    // Fail-closed: hostile getters, Proxy traps, etc. → VM error
    // Do NOT stringify e — hostile toString() can throw secondary exceptions
    let msg = 'Deep copy failed on hostile input';
    if (context !== 'Deep copy') msg = `${context}: ${msg}`;
    throw new Stage0VMError(msg);
  }
}

// ---------------------------------------------------------------------------
// Float scanner (iterative, depth-bounded)
// ---------------------------------------------------------------------------
function checkNoFloats(value) {
  // Validate literal values: Mu-domain only, no floats. Iterative + depth-bounded.
  // Mu value domain: null, boolean, number (integer), string, plain object, array.
  // Non-Mu types (BigInt, Symbol, function, undefined, Set, Map, etc.) are rejected.
  const stack = [[value, 0]];
  while (stack.length > 0) {
    const [v, depth] = stack.pop();
    if (depth > MAX_TEMPLATE_DEPTH) {
      throw new Error(
        `Literal value depth exceeded (${MAX_TEMPLATE_DEPTH})`);
    }
    if (typeof v === 'number' && !Number.isInteger(v)) {
      throw new Error(
        `Float values unsupported in Stage0 IR v1: ${v}`);
    }
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      // Reject non-plain objects (Set, Map, Date, boxed primitives, etc.)
      if (!_isPlainObject(v)) {
        throw new Error(
          `Non-Mu value type in literal: ${v.constructor ? v.constructor.name : 'object'}`);
      }
      // Reject symbol keys (invisible to Object.keys/values)
      if (Object.getOwnPropertySymbols(v).length > 0) {
        throw new Error(
          'Non-Mu value type in literal: object with symbol keys');
      }
      for (const child of Object.values(v)) {
        stack.push([child, depth + 1]);
      }
    } else if (Array.isArray(v)) {
      // Reject array subclasses (parity with Python type(x) is list)
      if (Object.getPrototypeOf(v) !== Array.prototype) {
        throw new Error(
          `Non-Mu value type in literal: ${v.constructor ? v.constructor.name : 'Array subclass'}`);
      }
      for (const child of v) {
        stack.push([child, depth + 1]);
      }
    } else if (v !== null && typeof v !== 'boolean' &&
               typeof v !== 'number' && typeof v !== 'string') {
      throw new Error(
        `Non-Mu value type in literal: ${typeof v}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Template validation (iterative, depth-bounded, closed-IR)
// ---------------------------------------------------------------------------
function validateTemplate(template) {
  const stack = [[template, 0]];
  while (stack.length > 0) {
    const [node, depth] = stack.pop();
    if (depth > MAX_TEMPLATE_DEPTH) {
      throw new Error(`Template depth exceeded (${MAX_TEMPLATE_DEPTH})`);
    }
    if (!_isPlainObject(node)) {
      throw new Error(`Template node must be a plain object: ${_safeStringify(node)}`);
    }
    if (!Object.hasOwn(node, 'kind')) {
      throw new Error(`Invalid template node (missing 'kind'): ${_safeStringify(node)}`);
    }
    _rejectSymbolKeys(node, 'Template node');
    const kind = node.kind;
    if (typeof kind !== 'string') {
      throw new Error(
        `Template 'kind' must be a string, got ${typeof kind}`);
    }
    if (!TEMPLATE_KINDS.has(kind)) {
      throw new Error(`Unknown template kind: '${kind}'`);
    }
    const required = TEMPLATE_SCHEMAS[kind];
    const allowed = new Set(['kind', ...required]);
    for (const k of required) {
      if (!Object.hasOwn(node, k)) {
        throw new Error(`Template '${kind}' missing required key '${k}'`);
      }
    }
    for (const k of Object.getOwnPropertyNames(node)) {
      if (!allowed.has(k)) {
        throw new Error(`Template '${kind}' has unknown key '${k}'`);
      }
    }
    if (kind === 'object') {
      if (!_isPlainObject(node.fields)) {
        throw new Error("Template 'object' 'fields' must be a plain object");
      }
      // JS Object.keys() always returns strings (numeric keys are pre-coerced).
      // Symbol keys are invisible to Object.keys() — reject them explicitly.
      if (Object.getOwnPropertySymbols(node.fields).length > 0) {
        throw new Error(
          "Template 'object' field key must be a string, got symbol");
      }
      for (const child of Object.values(node.fields)) {
        stack.push([child, depth + 1]);
      }
    } else if (kind === 'list') {
      if (!_isPlainArray(node.items)) {
        throw new Error("Template 'list' 'items' must be an array");
      }
      for (const child of node.items) {
        stack.push([child, depth + 1]);
      }
    } else if (kind === 'capture_ref') {
      if (typeof node.name !== 'string') {
        throw new Error("Template 'capture_ref' 'name' must be a string");
      }
    } else if (kind === 'literal') {
      checkNoFloats(node.value);
    }
  }
}

// ---------------------------------------------------------------------------
// Template materialization
// ---------------------------------------------------------------------------
function materializeTemplate(template, captures, depth = 0) {
  if (depth > MAX_TEMPLATE_DEPTH) {
    throw new Stage0VMError(`Template depth exceeded (${MAX_TEMPLATE_DEPTH})`);
  }
  if (!_isPlainObject(template) || !Object.hasOwn(template, 'kind')) {
    throw new Stage0VMError(`Invalid template node: ${_safeStringify(template)}`);
  }
  const kind = template.kind;
  if (!TEMPLATE_KINDS.has(kind)) {
    throw new Stage0VMError(`Unknown template kind: '${kind}'`);
  }
  if (kind === 'literal') {
    if (!Object.hasOwn(template, 'value')) {
      throw new Stage0VMError("Template 'literal' missing 'value' key");
    }
    const v = template.value;
    // Deep-copy mutable literals to prevent bundle mutation across runs
    if (Array.isArray(v) || _isPlainObject(v)) return safeMuCopy(v);
    return v;
  }
  if (kind === 'capture_ref') {
    if (!Object.hasOwn(template, 'name')) {
      throw new Stage0VMError("Template 'capture_ref' missing 'name' key");
    }
    const name = template.name;
    if (!Object.hasOwn(captures, name)) {
      throw new Stage0VMError(
        `Template references uncaptured variable: '${name}'`);
    }
    // N1 fix: deep-copy captured value to prevent reference leakage
    // and host-tainted leaf passthrough (parity: Python _safe_mu_copy)
    return safeMuCopy(captures[name]);
  }
  if (kind === 'object') {
    if (!Object.hasOwn(template, 'fields') || !_isPlainObject(template.fields)) {
      throw new Stage0VMError(
        "Template 'object' missing or invalid 'fields' key");
    }
    const result = muContainers.record();
    for (const [key, val] of Object.entries(template.fields)) {
      result[key] = materializeTemplate(val, captures, depth + 1);
    }
    return result;
  }
  // kind === 'list'
  if (!Object.hasOwn(template, 'items') || !_isPlainArray(template.items)) {
    throw new Stage0VMError(
      "Template 'list' missing or invalid 'items' key");
  }
  return muContainers.list(template.items.map(item =>
    materializeTemplate(item, captures, depth + 1)));
}

// ---------------------------------------------------------------------------
// Path validation helper
// ---------------------------------------------------------------------------
function validatePath(path, context) {
  if (!_isPlainArray(path)) {
    throw new Error(`${context}: 'path' must be an array`);
  }
  if (path.length > MAX_PATH_DEPTH) {
    throw new Error(
      `${context}: path length ${path.length} exceeds ` +
      `MAX_PATH_DEPTH (${MAX_PATH_DEPTH})`);
  }
  if (path.length < 2 || path[0] !== 'focus' || path[1] !== 'root') {
    throw new Error(
      `${context}: path must start with ['focus', 'root']`);
  }
  for (const seg of path) {
    if (typeof seg !== 'string') {
      throw new Error(
        `${context}: path segment must be a string, ` +
        `got ${typeof seg}`);
    }
  }
}

const _BUNDLE_ALLOWED_KEYS = new Set([
  'stage0_ir_version', 'bundle_id', 'source_seed',
  'machine_profile', 'program_order', 'programs',
  // Integrity keys (required for compiler-produced bundles)
  'source_digest', 'lowering_version',
  // Metadata keys (documentation, not semantically active)
  'source_seed_version', 'hand_authored', 'note',
]);
const _PROGRAM_ALLOWED_KEYS = new Set([
  'id', 'ops', 'source_map',
  // Metadata keys (documentation, not semantically active)
  'description',
]);

// Sentinel for "no write_path executed yet" (distinct from null, a valid Mu value)
const _UNSET = Symbol('unset');

// ---------------------------------------------------------------------------
// Safe string representation (avoids BigInt TypeError from JSON.stringify)
// ---------------------------------------------------------------------------
function _safeStringify(value) {
  try {
    return JSON.stringify(value);
  } catch (_) {
    try {
      return String(value);
    } catch (_2) {
      return '<unstringifiable>';
    }
  }
}

// ---------------------------------------------------------------------------
// Symbol-key rejection helper (Object.keys() ignores Symbol keys)
// ---------------------------------------------------------------------------
function _rejectSymbolKeys(obj, context) {
  if (Object.getOwnPropertySymbols(obj).length > 0) {
    throw new Error(`${context}: Symbol keys are not allowed`);
  }
}

// ---------------------------------------------------------------------------
// Bundle validation (fail-closed)
// ---------------------------------------------------------------------------
function validateBundle(bundle) {
  if (!_isPlainObject(bundle)) {
    const desc = bundle === null ? 'null'
      : bundle === undefined ? 'undefined'
      : Array.isArray(bundle) ? 'Array'
      : typeof bundle !== 'object' ? typeof bundle
      : bundle.constructor ? bundle.constructor.name : 'non-plain object';
    throw new Error(`Bundle must be a plain object, got ${desc}`);
  }
  _rejectSymbolKeys(bundle, 'Bundle');
  const required = [
    'stage0_ir_version', 'bundle_id', 'source_seed',
    'machine_profile', 'program_order', 'programs',
  ];
  for (const field of required) {
    if (!Object.hasOwn(bundle, field)) {
      throw new Error(`Missing required bundle field: '${field}'`);
    }
  }
  // Closed-IR: reject unknown bundle-level keys (getOwnPropertyNames catches non-enumerable)
  for (const k of Object.getOwnPropertyNames(bundle)) {
    if (!_BUNDLE_ALLOWED_KEYS.has(k)) {
      throw new Error(`Unknown bundle-level key: '${k}'`);
    }
  }
  // Integrity fields: required for compiler-produced bundles
  if (bundle.hand_authored !== true) {
    if (!Object.hasOwn(bundle, 'lowering_version')) {
      throw new Error(
        "Missing 'lowering_version' (required for compiler-produced bundles)");
    }
    if (!Object.hasOwn(bundle, 'source_digest')) {
      throw new Error(
        "Missing 'source_digest' (required for compiler-produced bundles)");
    }
    // N2 fix: validate source_digest format (sha256:<64-hex-chars>, parity: Python)
    const sd = bundle.source_digest;
    if (typeof sd !== 'string' || !/^sha256:[0-9a-f]{64}$/.test(sd)) {
      throw new Error(
        `source_digest must be 'sha256:<64-hex-chars>', got: '${sd}'`);
    }
  }
  if (bundle.stage0_ir_version !== 1) {
    throw new Error(`Unsupported IR version: ${bundle.stage0_ir_version}`);
  }
  if (bundle.machine_profile !== 'rcx.stage0.v1') {
    throw new Error(`Unsupported machine profile: ${bundle.machine_profile}`);
  }
  const programs = bundle.programs;
  const order = bundle.program_order;
  if (!_isPlainArray(programs)) throw new Error("'programs' must be an array");
  if (!_isPlainArray(order)) throw new Error("'program_order' must be an array");
  if (programs.length > MAX_VM_PROGRAMS) {
    throw new Error(
      `Too many programs: ${programs.length} > ${MAX_VM_PROGRAMS}`);
  }

  // String-type program_order entries (Bridge R4: JS coercion divergence)
  for (const entry of order) {
    if (typeof entry !== 'string') {
      throw new Error(
        `program_order entry must be a string, got ${typeof entry}`);
    }
  }

  const seenIds = new Set();
  const actualOrder = [];
  for (const prog of programs) {
    if (!_isPlainObject(prog)) {
      throw new Error('Each program must be a plain object');
    }
    _rejectSymbolKeys(prog, 'Program');
    if (!Object.hasOwn(prog, 'id')) throw new Error("Program missing 'id'");
    const pid = prog.id;
    if (typeof pid !== 'string') {
      throw new Error(`Program 'id' must be a string, got ${typeof pid}`);
    }
    if (!Object.hasOwn(prog, 'ops')) throw new Error(`Program '${pid}' missing 'ops'`);
    // Closed-IR: reject unknown program-level keys (getOwnPropertyNames catches non-enumerable)
    for (const pk of Object.getOwnPropertyNames(prog)) {
      if (!_PROGRAM_ALLOWED_KEYS.has(pk)) {
        throw new Error(
          `Program '${pid}' has unknown key '${pk}'`);
      }
    }
    const ops = prog.ops;
    if (!_isPlainArray(ops) || ops.length === 0) {
      throw new Error(`Program '${pid}' has empty or non-array ops`);
    }
    if (seenIds.has(pid)) throw new Error(`Duplicate program ID: '${pid}'`);
    seenIds.add(pid);
    actualOrder.push(pid);

    for (let i = 0; i < ops.length; i++) {
      const opSpec = ops[i];
      if (!_isPlainObject(opSpec)) {
        throw new Error(`Op ${i} in program '${pid}' must be a plain object`);
      }
      if (!Object.hasOwn(opSpec, 'op')) {
        throw new Error(`Op ${i} in program '${pid}' missing 'op' field`);
      }
      _rejectSymbolKeys(opSpec, `Op ${i} in program '${pid}'`);
      const op = opSpec.op;
      if (typeof op !== 'string') {
        throw new Error(
          `Op ${i} in program '${pid}': ` +
          `'op' must be a string, got ${typeof op}`);
      }
      if (!KNOWN_OPCODES.has(op)) {
        throw new Error(
          `Unknown opcode '${op}' in program '${pid}'`);
      }

      // Per-opcode schema validation (closed IR)
      const schema = OPCODE_SCHEMAS[op];
      const opRequired = schema.required;
      const opOptional = schema.optional;
      const actualKeys = new Set(Object.getOwnPropertyNames(opSpec));
      for (const k of opRequired) {
        if (!actualKeys.has(k)) {
          throw new Error(
            `Op '${op}' in program '${pid}' missing required field '${k}'`);
        }
      }
      for (const k of actualKeys) {
        if (k !== 'op' && !opRequired.has(k) && !opOptional.has(k) &&
            !GLOBAL_OP_OPTIONAL.has(k)) {
          throw new Error(
            `Op '${op}' in program '${pid}' has unknown field '${k}'`);
        }
      }

      // Semantic checks per opcode
      if (op === 'assert_focus_kind') {
        if (typeof opSpec.kind !== 'string') {
          throw new Error(
            `Op 'assert_focus_kind' in program '${pid}': ` +
            `'kind' must be a string, got ${typeof opSpec.kind}`);
        }
        if (!SUPPORTED_KINDS.has(opSpec.kind)) {
          throw new Error(
            `Op 'assert_focus_kind' in program '${pid}': ` +
            `unsupported kind '${opSpec.kind}'`);
        }
      }

      // Path validation for all ops that have 'path'
      if (opRequired.has('path')) {
        validatePath(
          opSpec.path,
          `Op '${op}' in program '${pid}'`);
      }

      // capture_path.name must be a string
      if (op === 'capture_path') {
        if (typeof opSpec.name !== 'string') {
          throw new Error(
            `Op 'capture_path' in program '${pid}': 'name' must be a string`);
        }
      }

      // check_captured_equal.capture_name must be a string
      if (op === 'check_captured_equal') {
        if (typeof opSpec.capture_name !== 'string') {
          throw new Error(
            `Op 'check_captured_equal' in program '${pid}': ` +
            `'capture_name' must be a string`);
        }
      }

      // check_equal.value: float scan
      if (op === 'check_equal') {
        checkNoFloats(opSpec.value);
      }

      // key-profile semantic checks
      if (op === 'assert_key_profile') {
        const reqField = opSpec.required;
        if (!_isPlainArray(reqField)) {
          throw new Error(
            `Op 'assert_key_profile' in program '${pid}': ` +
            `'required' must be an array`);
        }
        for (const item of reqField) {
          if (typeof item !== 'string') {
            throw new Error(
              `Op 'assert_key_profile' in program '${pid}': ` +
              `'required' items must be strings`);
          }
        }
        if (Object.hasOwn(opSpec, 'optional')) {
          const optField = opSpec.optional;
          if (!_isPlainArray(optField)) {
            throw new Error(
              `Op 'assert_key_profile' in program '${pid}': ` +
              `'optional' must be an array`);
          }
          for (const optEntry of optField) {
            if (!_isPlainObject(optEntry)) {
              throw new Error(
                `Op 'assert_key_profile' in program '${pid}': ` +
                `optional entry must be a plain object`);
            }
            _rejectSymbolKeys(optEntry,
              `Op 'assert_key_profile' in program '${pid}': optional entry`);
            if (!Object.hasOwn(optEntry, 'key')) {
              throw new Error(
                `Op 'assert_key_profile' in program '${pid}': ` +
                `optional entry missing 'key'`);
            }
            // Closed inner dict: only {key, allowed_values} allowed (getOwnPropertyNames catches non-enumerable)
            for (const ek of Object.getOwnPropertyNames(optEntry)) {
              if (!_OPT_ENTRY_ALLOWED_KEYS.has(ek)) {
                throw new Error(
                  `Op 'assert_key_profile' in program '${pid}': ` +
                  `optional entry has unknown key '${ek}'`);
              }
            }
            if (typeof optEntry.key !== 'string') {
              throw new Error(
                `Op 'assert_key_profile' in program '${pid}': ` +
                `optional entry 'key' must be a string`);
            }
            if (Object.hasOwn(optEntry, 'allowed_values')) {
              const av = optEntry.allowed_values;
              if (!_isPlainArray(av)) {
                throw new Error(
                  `Op 'assert_key_profile' in program '${pid}': ` +
                  `'allowed_values' must be an array`);
              }
              for (const avItem of av) {
                checkNoFloats(avItem);
              }
            }
          }
        }
      }

      // write_path: validate template
      if (op === 'write_path') {
        validateTemplate(opSpec.template);
      }
    }
  }

  if (JSON.stringify(order) !== JSON.stringify(actualOrder)) {
    throw new Error(
      `program_order mismatch: order=${JSON.stringify(order)}, ` +
      `actual=${JSON.stringify(actualOrder)}`);
  }
}

// ---------------------------------------------------------------------------
// VM step — single dispatch cycle
// ---------------------------------------------------------------------------

/**
 * Internal: full dispatch body. Caller must prove loader-cached bundle.
 *
 * W6A fast path: skips validateBundle for trusted callers. All production
 * call sites route through kernel.js._stepKernelWithVM, which uses bundles
 * loaded at module level in main.js (validated once at load).
 *
 * Source-lock enforced by tests/l4_gates/test_stage0_vm_trusted_path_gate.py.
 */
function _stage0VmStepTrusted(bundle, inputValue, maxOps = MAX_VM_OPS_PER_STEP) {
  const programs = bundle.programs;
  const programMap = Object.create(null);
  for (const p of programs) programMap[p.id] = p;
  const order = bundle.program_order;

  let opCount = 0;
  let attemptCount = 0;
  const attemptedProgramIds = [];

  for (const programId of order) {
    const program = programMap[programId];
    const ops = program.ops;

    // T1: Begin attempt
    const inputRoot = inputValue;
    const captures = Object.create(null);
    let pendingRoot = _UNSET;
    attemptCount++;
    attemptedProgramIds.push(programId);
    let failed = false;

    for (const opSpec of ops) {
      opCount++;
      if (opCount > maxOps) {
        throw new Stage0VMError(
          `Op limit exceeded (${maxOps}) during program '${programId}'`);
      }

      const op = opSpec.op;

      // ---- assert_focus_kind ----
      if (op === 'assert_focus_kind') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok || classifyKind(val) !== opSpec.kind) {
          failed = true; break;
        }
      }

      // ---- assert_key_profile ----
      else if (op === 'assert_key_profile') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok || !_isPlainObject(val)) {
          failed = true; break;
        }
        const required = new Set(opSpec.required);
        const optionalSpecs = opSpec.optional || [];
        const optionalKeys = new Set();
        const optionalConstraints = {};
        for (const opt of optionalSpecs) {
          optionalKeys.add(opt.key);
          if (opt.allowed_values != null) {
            optionalConstraints[opt.key] = opt.allowed_values;
          }
        }
        const actual = new Set(Object.keys(val));
        for (const r of required) {
          if (!actual.has(r)) { failed = true; break; }
        }
        if (failed) break;
        for (const a of actual) {
          if (!required.has(a) && !optionalKeys.has(a)) { failed = true; break; }
        }
        if (failed) break;
        for (const [k, allowed] of Object.entries(optionalConstraints)) {
          if (actual.has(k)) {
            if (!allowed.some(av => safeMuDeepEqual(val[k], av))) {
              failed = true; break;
            }
          }
        }
        if (failed) break;
      }

      // ---- check_equal ----
      else if (op === 'check_equal') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok || !safeMuDeepEqual(val, opSpec.value)) {
          failed = true; break;
        }
      }

      // ---- check_captured_equal ----
      else if (op === 'check_captured_equal') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok) { failed = true; break; }
        const cname = opSpec.capture_name;
        if (!Object.hasOwn(captures, cname)) {
          throw new Stage0VMError(
            `check_captured_equal: '${cname}' not yet captured ` +
            `in program '${programId}'`);
        }
        if (!safeMuDeepEqual(val, captures[cname])) {
          failed = true; break;
        }
      }

      // ---- capture_path ----
      else if (op === 'capture_path') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok) { failed = true; break; }
        const name = opSpec.name;
        if (Object.hasOwn(captures, name)) {
          throw new Stage0VMError(
            `capture_path: duplicate capture '${name}' ` +
            `in program '${programId}'`);
        }
        captures[name] = safeMuCopy(val, true, 'capture_path');
      }

      // ---- write_path ----
      else if (op === 'write_path') {
        pendingRoot = materializeTemplate(opSpec.template, captures);
      }

      // ---- return_projection_success ----
      else if (op === 'return_projection_success') {
        if (pendingRoot === _UNSET) {
          throw new Stage0VMError(
            `return_projection_success without write_path in program '${programId}'`);
        }
        return {
          status: 'match',
          matched_program_id: programId,
          root: pendingRoot,
          attempt_trace: {
            attempted_program_ids: attemptedProgramIds,
            outcome: 'match',
            matched_program_id: programId,
          },
          metrics: { program_attempts: attemptCount, op_steps: opCount },
        };
      }

      // ---- return_projection_fail ----
      else if (op === 'return_projection_fail') {
        failed = true; break;
      }

      // ---- check_exists (provisional) ----
      else if (op === 'check_exists') {
        const [, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok) { failed = true; break; }
      }

      else {
        throw new Stage0VMError(`Unknown opcode: '${op}'`);
      }
    }

    if (!failed) {
      throw new Stage0VMError(
        `Program '${programId}' exhausted ops without ` +
        'return_projection_success or projection failure');
    }
    // T4: Discard attempt, advance to next program
  }

  // No program matched — stall
  return {
    status: 'stall',
    matched_program_id: null,
    root: inputValue,
    attempt_trace: {
      attempted_program_ids: attemptedProgramIds,
      outcome: 'stall',
      matched_program_id: null,
    },
    metrics: { program_attempts: attemptCount, op_steps: opCount },
  };
}

/**
 * Public wrapper: validates then delegates to _stage0VmStepTrusted.
 * Unchanged signature for backward compatibility.
 */
function stage0VmStep(bundle, inputValue, maxOps = MAX_VM_OPS_PER_STEP) {
  validateBundle(bundle);
  return _stage0VmStepTrusted(bundle, inputValue, maxOps);
}

// ---------------------------------------------------------------------------
// VM run — multi-step until stall
// ---------------------------------------------------------------------------
function stage0VmRun(bundle, inputValue, maxSteps = 100, maxOps = undefined) {
  let current = inputValue;
  const steps = [];
  let totalAttempts = 0;
  let totalOps = 0;

  for (let i = 0; i < maxSteps; i++) {
    const result = maxOps !== undefined
      ? stage0VmStep(bundle, current, maxOps)
      : stage0VmStep(bundle, current);
    totalAttempts += result.metrics.program_attempts;
    totalOps += result.metrics.op_steps;

    if (result.status === 'stall') {
      return {
        status: 'complete',
        root: current,
        steps,
        metrics: {
          total_steps: steps.length,
          total_attempts: totalAttempts,
          total_ops: totalOps,
        },
      };
    }

    steps.push({
      program_id: result.matched_program_id,
      root: result.root,
    });
    current = result.root;
  }

  throw new Stage0VMError(`Run step limit exceeded (${maxSteps})`);
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
module.exports = {
  Stage0VMError,
  validateBundle,
  stage0VmStep,
  _stage0VmStepTrusted,  // W6A: exported for kernel.js, source-lock enforced
  stage0VmRun,
  resolvePath,
  classifyKind,
  muDeepEqual,
  muCopy,
  materializeTemplate,
  MAX_VM_PROGRAMS,
  MAX_VM_OPS_PER_STEP,
  MAX_TEMPLATE_DEPTH,
  MAX_PATH_DEPTH,
  OPCODE_SCHEMAS,
  SUPPORTED_KINDS,
};
