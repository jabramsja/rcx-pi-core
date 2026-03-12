'use strict';
/**
 * RCX Constants and Configuration
 *
 * All shared constants, error types, and classification functions.
 * Zero dependencies (leaf module).
 *
 * =============================================================================
 * DEBT SUMMARY (L3 Parity - must match Python bootstrap primitives)
 * =============================================================================
 *
 * NORTH STAR: See mu/docs/core/Why_RCX_PI_VM_EXISTS.md
 * Host languages (Python, JavaScript) are bootstrap scaffolding, NOT the
 * semantic destination. Every host operation below is tracked debt that must
 * eventually be replaced by structural Mu projections. We program IN RCX,
 * not ABOUT RCX. Meaning lives in the projections (data), not the host (code).
 *
 * BOOTSTRAP PRIMITIVES (4 — named set, gate-enforced):
 *   eval_step       - step()           - applies first matching projection
 *   max_steps       - maxSteps param   - termination guard
 *   stack_guard     - MAX_DEPTH        - recursion depth limit
 *   projection_loader - fs.readFileSync  - loads JSON seeds
 *   (mu_equal eliminated: now derivable from muHashCached, Content-Addressed Mu Level 1)
 *
 * SEMANTIC DEBT (host operations that would need structural replacement):
 *   iteration debt: 10
 *     - step()                    - for loop over projections
 *     - run()                     - for loop until stall
 *     - runStructural()           - for loop until stall (Gate 5: routes through stepKernel)
 *     - normalize()               - for loop for array conversion
 *     - denormalize()             - while loop for linked list
 *     - listToLinked()            - for loop for conversion
 *     - runAlgorithmWithBridge()  - bridge-backed algorithm execution loop
 *     - collectOntologyEvidence() - Mu linked-list traversal for evidence collection
 *     - runEnginePipeline()       - engine state machine effect handler loop
 *     - runEnginePipelineRecursive() - Boot1 engine loop (iterative re-entry)
 *
 *   recursion debt: 6
 *     - match()             - recursive pattern matching
 *     - substitute()        - recursive substitution
 *     - stage0Match()       - Stage 0 recursive pattern matching (bootstrap primitive)
 *     - stage0Substitute()  - Stage 0 recursive substitution (bootstrap primitive)
 *     - normalize()         - recursive normalization
 *     - denormalize()       - recursive denormalization
 *
 *   builtin debt: 2
 *     - muHash()            - SHA-256 hash (BOOTSTRAP_PRIMITIVE, hash-accelerated closure detection)
 *     - isValidMu()         - type validation
 *     (muEqual demoted: test-only convenience wrapper, delegates to muHashCached — P7 Wave 2)
 *
 * TOTAL DEBT: 18 (10 iteration + 6 recursion + 2 builtin)
 * Ratchet baseline: tools/checks/host_semantics_baseline.json (canonical counts)
 *
 * This debt represents the IRREDUCIBLE BOOTSTRAP - the same operations
 * exist in Python (JS requires additional normalize/denormalize; see STATUS.md for canonical counts).
 * =============================================================================
 */

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
  '_tail_call',
  // Boundary effect dispatch field (adversary hardening, 2026-02-24)
  '_boundary_request'
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
  '_m',         // sentinel-skip: max_steps value (exhaustion.v1.json v1.3.0)
  '_maxsteps',
  '_op_ids',
  '_operator',
  '_other',
  '_rest',
  '_s',         // sentinel-skip: state value (exhaustion.v1.json v1.3.0)
  '_st',        // sentinel-skip: step value (exhaustion.v1.json v1.3.0)
  '_state',
  '_stl',       // sentinel-skip: stall value (exhaustion.v1.json v1.3.0)
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

// Maximum iterations for linked-list denormalization (matches Python MAX_DENORM_ITER=10000)
// Separate from MAX_DEPTH because wide structures (up to MAX_MU_WIDTH=1000 elements)
// produce linked lists longer than MAX_DEPTH=300.
const MAX_DENORM_ITER = 10000;

// Maximum depth for validation traversal (fail closed, must cover full MAX_DEPTH)
const MAX_VALIDATION_DEPTH = MAX_DEPTH;

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
  if (msg.includes('numeric_hash_unsupported')) return 'input.numeric_hash_unsupported';
  if (msg.includes('not valid mu') || msg.includes('max depth exceeded')) return 'input.malformed_normalized';
  return 'api.bad_request';
}

module.exports = {
  MAX_DEPTH,
  NO_MATCH,
  VALID_TYPE_TAGS,
  KERNEL_RESERVED_FIELDS,
  ALGORITHM_ENTRYPOINT_KEYS,
  ALGORITHM_INTERNAL_UNRESERVED_FIELDS,
  ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
  MAX_DENORM_ITER,
  MAX_VALIDATION_DEPTH,
  RcxError,
  classifyError,
};
