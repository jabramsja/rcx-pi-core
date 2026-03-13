'use strict';
/**
 * Stage0 VM: data-driven execution of Stage0 IR bundles.
 *
 * JS parity port of mu/host/python/rcx_pi/selfhost/stage0_vm.py.
 * This VM executes derived bundles using a tiny set of opcodes.
 * The VM is intentionally dumb — all semantic knowledge lives in the
 * bundle data, not in the VM.
 *
 * P7-a prototype. NOT wired into production step/run.
 */

// ---------------------------------------------------------------------------
// Resource bounds
// ---------------------------------------------------------------------------
const MAX_VM_PROGRAMS = 64;
const MAX_VM_OPS_PER_STEP = 1024;
const MAX_TEMPLATE_DEPTH = 32;

// ---------------------------------------------------------------------------
// Opcode / kind / template enums
// ---------------------------------------------------------------------------
const KNOWN_OPCODES = new Set([
  'assert_focus_kind', 'assert_key_profile', 'check_equal',
  'check_captured_equal', 'capture_path', 'write_path',
  'return_projection_success', 'return_projection_fail',
  'check_exists',
]);

const TEMPLATE_KINDS = new Set([
  'literal', 'capture_ref', 'object', 'list',
]);

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
// Path resolution
// ---------------------------------------------------------------------------
function resolvePath(root, path) {
  if (path.length < 2 || path[0] !== 'focus' || path[1] !== 'root') {
    throw new Stage0VMError(
      `Path must start with ['focus', 'root'], got ${JSON.stringify(path)}`);
  }
  let current = root;
  for (let i = 2; i < path.length; i++) {
    if (current === null || typeof current !== 'object' || Array.isArray(current)) {
      return [null, false];
    }
    if (!Object.hasOwn(current, path[i])) {
      return [null, false];
    }
    current = current[path[i]];
  }
  return [current, true];
}

// ---------------------------------------------------------------------------
// Kind classification
// ---------------------------------------------------------------------------
function classifyKind(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return 'bool';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? 'int' : 'float';
  }
  if (typeof value === 'string') return 'string';
  if (Array.isArray(value)) return 'list';
  if (typeof value === 'object') return 'dict';
  return null;
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
    return a === b;
  }
  if (Array.isArray(a)) {
    if (!Array.isArray(b) || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!muDeepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  if (ta === 'object') {
    if (Array.isArray(b)) return false;
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

// ---------------------------------------------------------------------------
// Template materialization
// ---------------------------------------------------------------------------
function materializeTemplate(template, captures, depth = 0) {
  if (depth > MAX_TEMPLATE_DEPTH) {
    throw new Stage0VMError(`Template depth exceeded (${MAX_TEMPLATE_DEPTH})`);
  }
  if (typeof template !== 'object' || template === null || !template.kind) {
    throw new Stage0VMError(`Invalid template node: ${JSON.stringify(template)}`);
  }
  const kind = template.kind;
  if (!TEMPLATE_KINDS.has(kind)) {
    throw new Stage0VMError(`Unknown template kind: '${kind}'`);
  }
  if (kind === 'literal') return template.value;
  if (kind === 'capture_ref') {
    const name = template.name;
    if (!Object.hasOwn(captures, name)) {
      throw new Stage0VMError(
        `Template references uncaptured variable: '${name}'`);
    }
    return captures[name];
  }
  if (kind === 'object') {
    const result = Object.create(null);
    for (const [key, val] of Object.entries(template.fields)) {
      result[key] = materializeTemplate(val, captures, depth + 1);
    }
    return result;
  }
  // kind === 'list'
  return template.items.map(item =>
    materializeTemplate(item, captures, depth + 1));
}

// ---------------------------------------------------------------------------
// Bundle validation (fail-closed)
// ---------------------------------------------------------------------------
function validateBundle(bundle) {
  const required = [
    'stage0_ir_version', 'bundle_id', 'source_seed',
    'machine_profile', 'program_order', 'programs',
  ];
  for (const field of required) {
    if (!Object.hasOwn(bundle, field)) {
      throw new Error(`Missing required bundle field: '${field}'`);
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
  if (!Array.isArray(programs)) throw new Error("'programs' must be an array");
  if (!Array.isArray(order)) throw new Error("'program_order' must be an array");
  if (programs.length > MAX_VM_PROGRAMS) {
    throw new Error(
      `Too many programs: ${programs.length} > ${MAX_VM_PROGRAMS}`);
  }
  const seenIds = new Set();
  const actualOrder = [];
  for (const prog of programs) {
    if (typeof prog !== 'object' || prog === null) {
      throw new Error('Each program must be an object');
    }
    if (!Object.hasOwn(prog, 'id')) throw new Error("Program missing 'id'");
    if (!Object.hasOwn(prog, 'ops')) throw new Error(`Program '${prog.id}' missing 'ops'`);
    const pid = prog.id;
    const ops = prog.ops;
    if (!Array.isArray(ops) || ops.length === 0) {
      throw new Error(`Program '${pid}' has empty or non-array ops`);
    }
    if (seenIds.has(pid)) throw new Error(`Duplicate program ID: '${pid}'`);
    seenIds.add(pid);
    actualOrder.push(pid);
    for (let i = 0; i < ops.length; i++) {
      const opSpec = ops[i];
      if (typeof opSpec !== 'object' || !opSpec.op) {
        throw new Error(`Op ${i} in program '${pid}' missing 'op' field`);
      }
      if (!KNOWN_OPCODES.has(opSpec.op)) {
        throw new Error(
          `Unknown opcode '${opSpec.op}' in program '${pid}'`);
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
function stage0VmStep(bundle, inputValue, maxOps = MAX_VM_OPS_PER_STEP) {
  const programs = bundle.programs;
  const programMap = Object.create(null);
  for (const p of programs) programMap[p.id] = p;
  const order = bundle.program_order;

  let opCount = 0;
  let attemptCount = 0;

  for (const programId of order) {
    const program = programMap[programId];
    const ops = program.ops;

    // T1: Begin attempt
    const inputRoot = inputValue;
    const captures = Object.create(null);
    let pendingRoot = null;
    attemptCount++;
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
        if (!ok || val === null || typeof val !== 'object' || Array.isArray(val)) {
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
            if (!allowed.some(av => muDeepEqual(val[k], av))) {
              failed = true; break;
            }
          }
        }
        if (failed) break;
      }

      // ---- check_equal ----
      else if (op === 'check_equal') {
        const [val, ok] = resolvePath(inputRoot, opSpec.path);
        if (!ok || !muDeepEqual(val, opSpec.value)) {
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
        if (!muDeepEqual(val, captures[cname])) {
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
        captures[name] = val;
      }

      // ---- write_path ----
      else if (op === 'write_path') {
        pendingRoot = materializeTemplate(opSpec.template, captures);
      }

      // ---- return_projection_success ----
      else if (op === 'return_projection_success') {
        return {
          status: 'match',
          matched_program_id: programId,
          root: pendingRoot,
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
    metrics: { program_attempts: attemptCount, op_steps: opCount },
  };
}

// ---------------------------------------------------------------------------
// VM run — multi-step until stall
// ---------------------------------------------------------------------------
function stage0VmRun(bundle, inputValue, maxSteps = 100) {
  let current = inputValue;
  const steps = [];
  let totalAttempts = 0;
  let totalOps = 0;

  for (let i = 0; i < maxSteps; i++) {
    const result = stage0VmStep(bundle, current);
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
  stage0VmRun,
  resolvePath,
  classifyKind,
  muDeepEqual,
  materializeTemplate,
  MAX_VM_PROGRAMS,
  MAX_VM_OPS_PER_STEP,
  MAX_TEMPLATE_DEPTH,
};
