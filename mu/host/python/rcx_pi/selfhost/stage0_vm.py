"""Stage0 VM: data-driven execution of Stage0 IR bundles.

This VM executes derived bundles (hand-authored or compiled from seeds)
using a tiny set of opcodes. The VM is intentionally dumb — all semantic
knowledge lives in the bundle data, not in the VM.

P7-a prototype origin. Wired into the production shadow path via _step_kernel_with_vm(); cutover remains flag-gated.
Design plan: .scratch/p7a_design_plan.md

Opcodes (9):
  assert_focus_kind        — type-check value at path
  assert_key_profile       — key-set check at path (required + optional)
  check_equal              — literal equality at path
  check_captured_equal     — non-linear variable equality check
  capture_path             — bind value at path to name
  write_path               — materialize template to pending root
  return_projection_success— commit pending root, stop dispatch
  return_projection_fail   — explicit fail, advance to next program
  check_exists             — path existence check (provisional, unused in P7-a)

Transaction model:
  T1: Begin attempt — snapshot input, clear captures + pending
  T2: Check/capture phase — all reads from input snapshot
  T3: Write phase — write_path writes to pending root
  T4: Projection fail — discard pending + captures, advance
  T5: Projection success — commit pending root, return result

Stage0 IR v1 numeric contract: int supported, float UNSUPPORTED.
Float rejection enforced by validate_bundle. classifyKind retains
float classification for future IR versions but v1 bundles must
not rely on it. JS Number.isInteger(1.0) === true means int/float
distinction is not portable — hence float exclusion in v1.
Bundle JSON must use integer literals (1 not 1.0).
"""

# Zero stdlib imports — bootstrap-pure module.


# ---------------------------------------------------------------------------
# Resource bounds
# ---------------------------------------------------------------------------

MAX_VM_PROGRAMS = 64
MAX_VM_OPS_PER_STEP = 1024
MAX_TEMPLATE_DEPTH = 32
MAX_PATH_DEPTH = 64

# ---------------------------------------------------------------------------
# Opcode schemas (single source of truth for per-opcode field validation)
# ---------------------------------------------------------------------------

OPCODE_SCHEMAS = {  # AST_OK: key comparison schema for closed-IR op validation
    "assert_focus_kind":         {"required": frozenset({"path", "kind"}),         "optional": frozenset()},  # AST_OK: key
    "assert_key_profile":        {"required": frozenset({"path", "required"}),     "optional": frozenset({"optional"})},  # AST_OK: key
    "check_equal":               {"required": frozenset({"path", "value"}),        "optional": frozenset()},  # AST_OK: key
    "check_captured_equal":      {"required": frozenset({"path", "capture_name"}), "optional": frozenset()},  # AST_OK: key
    "capture_path":              {"required": frozenset({"path", "name"}),         "optional": frozenset()},  # AST_OK: key
    "write_path":                {"required": frozenset({"template"}),             "optional": frozenset()},
    "return_projection_success": {"required": frozenset(),                         "optional": frozenset()},
    "return_projection_fail":    {"required": frozenset(),                         "optional": frozenset()},
    "check_exists":              {"required": frozenset({"path"}),                 "optional": frozenset()},
}

GLOBAL_OP_OPTIONAL = frozenset({"source_map"})  # AST_OK: key — metadata keys allowed on all ops

KNOWN_OPCODES = frozenset(OPCODE_SCHEMAS.keys())  # AST_OK: key — derived from OPCODE_SCHEMAS

# ---------------------------------------------------------------------------
# Kind / template enums
# ---------------------------------------------------------------------------

SUPPORTED_KINDS = frozenset({  # AST_OK: key — v1 supported kinds (float excluded)
    "null", "bool", "int", "string", "dict", "list",
})

TEMPLATE_KINDS = frozenset({  # AST_OK: key comparison set for O(1) template kind validation
    "literal", "capture_ref", "object", "list",
})

TEMPLATE_SCHEMAS = {  # AST_OK: key — closed template kind → required keys mapping
    "literal":     frozenset({"value"}),
    "capture_ref": frozenset({"name"}),
    "object":      frozenset({"fields"}),
    "list":        frozenset({"items"}),
}

# Closed key set for assert_key_profile optional entry dicts
_OPT_ENTRY_ALLOWED_KEYS = frozenset({"key", "allowed_values"})  # AST_OK: key — closed inner IR node


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class Stage0VMError(Exception):
    """Machine error — bug in the bundle or VM, not a normal projection fail."""


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_path(root, path):
    """Navigate a VM path relative to focus.root.

    All bundle paths start with ["focus", "root", ...].  This strips the
    namespace prefix and walks the remaining keys through *root*.

    Returns (value, True) on success, (None, False) when any segment is
    missing or an intermediate is not a dict.
    """
    if len(path) < 2 or path[0] != "focus" or path[1] != "root":
        raise Stage0VMError(
            f"Path must start with ['focus', 'root'], got {path!r}")
    current = root
    for key in path[2:]:
        if type(current) is not dict or key not in current:
            return None, False
        current = current[key]
    return current, True


# ---------------------------------------------------------------------------
# Kind classification
# ---------------------------------------------------------------------------

def _classify_kind(value):
    """Map a Mu value to its Stage0 kind string.

    Uses exact-type checks for ALL types to reject host subclasses.
    Subclasses can override __eq__, __contains__, __getitem__, __iter__
    and inject behavior — they are not plain Mu values.
    """
    if value is None:
        return "null"
    t = type(value)
    if t is bool:
        return "bool"
    if t is int:
        return "int"
    if t is float:
        return "float"
    if t is str:
        return "string"
    if t is dict:
        return "dict"
    if t is list:
        return "list"
    return None


# ---------------------------------------------------------------------------
# Structural equality
# ---------------------------------------------------------------------------

def _mu_deep_equal(a, b):
    """Deep structural equality for Mu values.

    Handles None, bool, int, float, str, dict, list.
    bool and int are distinct types (True != 1).
    Uses exact-type checks throughout — subclasses are non-Mu.
    """
    if a is None:
        return b is None
    if b is None:
        return False
    t = type(a)
    if t is not type(b):
        return False
    if t is float:
        return a == b and (a != 0.0 or str(a) == str(b))
    if t is bool or t is int or t is str:
        return a == b  # Safe: exact-type means plain primitive __eq__
    if t is dict:
        if a.keys() != b.keys():
            return False
        return all(_mu_deep_equal(a[k], b[k]) for k in a)
    if t is list:
        if len(a) != len(b):
            return False
        return all(_mu_deep_equal(x, y) for x, y in zip(a, b))
    return False


def _safe_mu_deep_equal(a, b):
    # AST_OK: error boundary — translates host errors to Stage0VMError or fail-closed
    """Structural equality with recursion overflow and hostile-input protection."""
    try:
        return _mu_deep_equal(a, b)
    except RecursionError:
        raise Stage0VMError(
            "Structural equality depth exceeded (recursion overflow)")
    except Exception:
        # Hostile __eq__, __hash__, __iter__ etc. — treat as not-equal (fail-closed)
        return False


# ---------------------------------------------------------------------------
# Structural deep copy (no stdlib — Mu values only)
# ---------------------------------------------------------------------------

def _mu_copy(value, reject_non_mu=False, context="Deep copy"):
    """Deep-copy a Mu value using only primitives (no copy/json imports)."""
    if type(value) is dict:
        if reject_non_mu:
            for k in value:
                if type(k) is not str:
                    raise Stage0VMError(
                        f"{context}: non-Mu value cannot be captured")
        return {k: _mu_copy(v, reject_non_mu, context) for k, v in value.items()}  # AST_OK: bootstrap structural copy of Mu dict
    if type(value) is list:
        return [_mu_copy(item, reject_non_mu, context) for item in value]  # AST_OK: bootstrap structural copy of Mu list
    # Exact-type check for primitives: reject subclasses (EvilStr, etc.)
    if type(value) in (str, int, bool, type(None)):
        return value
    if type(value) is float:
        if reject_non_mu and value - value != 0.0:
            raise Stage0VMError(f"{context}: non-Mu value cannot be captured")
        return value
    if reject_non_mu:
        raise Stage0VMError(f"{context}: non-Mu value cannot be captured")
    # Non-Mu type (subclass or unknown) — fail-closed: return None
    # This prevents hostile leaf passthrough from capture_ref
    return None


def _safe_mu_copy(value, reject_non_mu=False, context="Deep copy"):
    # AST_OK: error boundary — translates ALL host errors to Stage0VMError (fail-closed)
    """Deep-copy with error boundary protection (parity: JS safeMuCopy)."""
    try:
        return _mu_copy(value, reject_non_mu, context)
    except Stage0VMError:
        raise
    except RecursionError:
        msg = "Deep copy depth exceeded (recursion overflow)"
        if context != "Deep copy":
            msg = f"{context}: {msg}"
        raise Stage0VMError(msg)
    except Exception as e:
        # Fail-closed: hostile dict keys, __iter__ traps, etc. → VM error
        # Do NOT stringify e — hostile __str__ can throw secondary exceptions
        msg = "Deep copy failed on hostile input"
        if context != "Deep copy":
            msg = f"{context}: {msg}"
        raise Stage0VMError(msg)


# ---------------------------------------------------------------------------
# Float scanner (iterative, depth-bounded)
# ---------------------------------------------------------------------------

def _check_no_floats(value):
    """Validate literal values: Mu-domain only, no floats. Iterative + depth-bounded.

    Mu value domain: None, bool, int, str, dict, list. Float rejected in IR v1.
    Non-Mu types (tuple, set, bytes, custom objects, etc.) are rejected.
    """
    stack = [(value, 0)]
    while stack:
        v, depth = stack.pop()
        if depth > MAX_TEMPLATE_DEPTH:
            raise ValueError(
                f"Literal value depth exceeded ({MAX_TEMPLATE_DEPTH})")
        if isinstance(v, float):
            raise ValueError(
                f"Float values unsupported in Stage0 IR v1: {v!r}")
        if type(v) is dict:
            for child in v.values():
                stack.append((child, depth + 1))
        elif type(v) is list:
            for child in v:
                stack.append((child, depth + 1))
        elif v is not None and type(v) is not bool and type(v) is not int and type(v) is not str:
            raise ValueError(
                f"Non-Mu value type in literal: {type(v).__name__}")


# ---------------------------------------------------------------------------
# Template validation (iterative, depth-bounded, closed-IR)
# ---------------------------------------------------------------------------

def _validate_template(template):
    """Validate template structure at bundle-validation time.

    Iterative, depth-bounded, closed-IR: rejects unknown keys and
    validates types for all template nodes.
    """
    stack = [(template, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_TEMPLATE_DEPTH:
            raise ValueError(
                f"Template depth exceeded ({MAX_TEMPLATE_DEPTH})")
        if type(node) is not dict:
            try:
                desc = repr(node)
            except Exception:
                desc = "<unrepresentable>"
            raise ValueError(f"Invalid template node: {desc}")
        # Validate template node keys before membership checks
        for tk in node:
            if type(tk) is not str:
                raise ValueError(
                    f"Template node key must be a string, "
                    f"got {type(tk).__name__}")
        if "kind" not in node:
            try:
                desc = repr(node)
            except Exception:
                desc = "<unrepresentable>"
            raise ValueError(f"Invalid template node (missing 'kind'): {desc}")
        kind = node["kind"]
        if type(kind) is not str:
            raise ValueError(
                f"Template 'kind' must be a string, "
                f"got {type(kind).__name__}")
        if kind not in TEMPLATE_SCHEMAS:
            raise ValueError(f"Unknown template kind: '{kind}'")
        required = TEMPLATE_SCHEMAS[kind]
        allowed = {"kind"} | required
        for k in required:
            if k not in node:
                raise ValueError(
                    f"Template '{kind}' missing required key '{k}'")
        for k in node:
            if k not in allowed:
                raise ValueError(
                    f"Template '{kind}' has unknown key '{k}'")
        # Type checks + recurse into child templates
        if kind == "object":
            if type(node["fields"]) is not dict:
                raise ValueError("Template 'object' 'fields' must be a dict")
            for fk in node["fields"]:
                if type(fk) is not str:
                    raise ValueError(
                        f"Template 'object' field key must be a string, "
                        f"got {type(fk).__name__}")
            for child in node["fields"].values():
                stack.append((child, depth + 1))
        elif kind == "list":
            if type(node["items"]) is not list:
                raise ValueError("Template 'list' 'items' must be a list")
            for child in node["items"]:
                stack.append((child, depth + 1))
        elif kind == "capture_ref":
            if type(node["name"]) is not str:
                raise ValueError(
                    "Template 'capture_ref' 'name' must be a string")
        elif kind == "literal":
            _check_no_floats(node["value"])  # Float scan on literal values


# ---------------------------------------------------------------------------
# Template materialization
# ---------------------------------------------------------------------------

def _materialize_template(template, captures, _depth=0):
    """Expand a write_path template using captured values.

    Template language (CLOSED — no extensions without explicit governance):
      {"kind": "literal",     "value": <any Mu>}
      {"kind": "capture_ref", "name": "<name>"}
      {"kind": "object",      "fields": {<key>: <template>, ...}}
      {"kind": "list",        "items": [<template>, ...]}
    """
    if _depth > MAX_TEMPLATE_DEPTH:
        raise Stage0VMError(
            f"Template depth exceeded ({MAX_TEMPLATE_DEPTH})")

    if type(template) is not dict or "kind" not in template:
        try:
            desc = repr(template)
        except Exception:
            desc = "<unrepresentable>"
        raise Stage0VMError(f"Invalid template node: {desc}")

    kind = template["kind"]
    if kind not in TEMPLATE_KINDS:
        raise Stage0VMError(f"Unknown template kind: '{kind}'")

    if kind == "literal":
        if "value" not in template:
            raise Stage0VMError("Template 'literal' missing 'value' key")
        value = template["value"]
        # Deep-copy mutable literals to prevent bundle mutation across runs
        if type(value) is dict:
            return _safe_mu_copy(value)
        if type(value) is list:
            return _safe_mu_copy(value)
        return value

    if kind == "capture_ref":
        if "name" not in template:
            raise Stage0VMError("Template 'capture_ref' missing 'name' key")
        name = template["name"]
        if name not in captures:
            raise Stage0VMError(
                f"Template references uncaptured variable: '{name}'")
        # N1 fix: deep-copy captured value to prevent reference leakage
        # and host-tainted leaf passthrough (parity: JS safeMuCopy)
        return _safe_mu_copy(captures[name])

    if kind == "object":
        if "fields" not in template or type(template["fields"]) is not dict:
            raise Stage0VMError(
                "Template 'object' missing or invalid 'fields' key")
        return {  # AST_OK: bootstrap materialization builds output dict from fields
            key: _materialize_template(val, captures, _depth + 1)
            for key, val in template["fields"].items()
        }

    # kind == "list"
    if "items" not in template or type(template["items"]) is not list:
        raise Stage0VMError(
            "Template 'list' missing or invalid 'items' key")
    return [  # AST_OK: bootstrap materialization builds output list from items
        _materialize_template(item, captures, _depth + 1)
        for item in template["items"]
    ]


# ---------------------------------------------------------------------------
# Path validation helper
# ---------------------------------------------------------------------------

def _validate_path(path, context):
    """Validate a path field: must be a list of strings, bounded length,
    and must start with ['focus', 'root']."""
    if type(path) is not list:
        raise ValueError(f"{context}: 'path' must be a list")
    if len(path) > MAX_PATH_DEPTH:
        raise ValueError(
            f"{context}: path length {len(path)} exceeds "
            f"MAX_PATH_DEPTH ({MAX_PATH_DEPTH})")
    if len(path) < 2 or path[0] != "focus" or path[1] != "root":
        raise ValueError(
            f"{context}: path must start with ['focus', 'root']")
    for seg in path:
        if type(seg) is not str:
            raise ValueError(
                f"{context}: path segment must be a string, "
                f"got {type(seg).__name__}")


# ---------------------------------------------------------------------------
# Bundle validation (fail-closed)
# ---------------------------------------------------------------------------

_BUNDLE_ALLOWED_KEYS = frozenset({  # AST_OK: key — closed bundle-level key validation
    "stage0_ir_version", "bundle_id", "source_seed",
    "machine_profile", "program_order", "programs",
    # Integrity keys (required for compiler-produced bundles)
    "source_digest", "lowering_version",
    # Metadata keys (documentation, not semantically active)
    "source_seed_version", "hand_authored", "note",
})
_PROGRAM_ALLOWED_KEYS = frozenset({  # AST_OK: key — closed program-level key validation
    "id", "ops", "source_map",
    # Metadata keys (documentation, not semantically active)
    "description",
})


def validate_bundle(bundle):
    """Validate bundle structure.  Raises ValueError on any defect."""
    if type(bundle) is not dict:
        raise ValueError(
            f"Bundle must be a dict, got {type(bundle).__name__}")
    # Validate all dict keys are plain str before any membership checks
    # (hostile str subclass keys leak __eq__/__hash__ on `field in bundle`)
    for k in bundle:
        if type(k) is not str:
            raise ValueError(
                f"Bundle key must be a string, got {type(k).__name__}")
    required = (
        "stage0_ir_version", "bundle_id", "source_seed",
        "machine_profile", "program_order", "programs",
    )
    for field in required:
        if field not in bundle:
            raise ValueError(f"Missing required bundle field: '{field}'")

    # Closed-IR: reject unknown bundle-level keys
    for k in bundle:
        if k not in _BUNDLE_ALLOWED_KEYS:
            raise ValueError(f"Unknown bundle-level key: '{k}'")

    # Integrity fields: required for compiler-produced bundles
    if bundle.get("hand_authored") is not True:
        if "lowering_version" not in bundle:
            raise ValueError(
                "Missing 'lowering_version' (required for "
                "compiler-produced bundles)")
        if "source_digest" not in bundle:
            raise ValueError(
                "Missing 'source_digest' (required for "
                "compiler-produced bundles)")
        # N2 fix: validate source_digest format (sha256:<64-hex-chars>)
        sd = bundle["source_digest"]
        if (type(sd) is not str or not sd.startswith("sha256:")
                or len(sd) != 71
                or not all(c in '0123456789abcdef' for c in sd[7:])):
            raise ValueError(
                f"source_digest must be 'sha256:<64-hex-chars>', got: {sd!r}")

    # Exact int type: reject bool (True == 1 in Python but true !== 1 in JS)
    if type(bundle["stage0_ir_version"]) is not int or isinstance(bundle["stage0_ir_version"], bool):
        raise ValueError(
            f"stage0_ir_version must be an int, got {type(bundle['stage0_ir_version']).__name__}")
    if bundle["stage0_ir_version"] != 1:
        raise ValueError(
            f"Unsupported IR version: {bundle['stage0_ir_version']}")
    if bundle["machine_profile"] != "rcx.stage0.v1":
        raise ValueError(
            f"Unsupported machine profile: {bundle['machine_profile']}")

    programs = bundle["programs"]
    order = bundle["program_order"]

    if type(programs) is not list:
        raise ValueError("'programs' must be a list")
    if type(order) is not list:
        raise ValueError("'program_order' must be a list")
    if len(programs) > MAX_VM_PROGRAMS:
        raise ValueError(
            f"Too many programs: {len(programs)} > {MAX_VM_PROGRAMS}")

    # String-type program_order entries (Bridge R4: JS coercion divergence)
    for entry in order:
        if type(entry) is not str:
            raise ValueError(
                f"program_order entry must be a string, "
                f"got {type(entry).__name__}")

    seen_ids = set()
    actual_order = []
    for prog in programs:
        if type(prog) is not dict:
            raise ValueError("Each program must be a dict")
        # Validate program dict keys before any membership checks
        for pk in prog:
            if type(pk) is not str:
                raise ValueError(
                    f"Program key must be a string, got {type(pk).__name__}")
        if "id" not in prog:
            raise ValueError("Program missing 'id'")
        pid = prog["id"]
        if type(pid) is not str:
            raise ValueError(
                f"Program 'id' must be a string, got {type(pid).__name__}")
        if "ops" not in prog:
            raise ValueError(f"Program '{pid}' missing 'ops'")
        # Closed-IR: reject unknown program-level keys
        for pk in prog:
            if pk not in _PROGRAM_ALLOWED_KEYS:
                raise ValueError(
                    f"Program '{pid}' has unknown key '{pk}'")
        ops = prog["ops"]
        if type(ops) is not list or not ops:
            raise ValueError(f"Program '{pid}' has empty or non-list ops")
        if pid in seen_ids:
            raise ValueError(f"Duplicate program ID: '{pid}'")
        seen_ids.add(pid)
        actual_order.append(pid)

        for i, op_spec in enumerate(ops):
            if type(op_spec) is not dict:
                raise ValueError(
                    f"Op {i} in program '{pid}' must be a dict, "
                    f"got {type(op_spec).__name__}")
            # Validate op dict keys before any membership checks
            for ok in op_spec:
                if type(ok) is not str:
                    raise ValueError(
                        f"Op {i} in program '{pid}': "
                        f"key must be a string, got {type(ok).__name__}")
            if "op" not in op_spec:
                raise ValueError(
                    f"Op {i} in program '{pid}' missing 'op' field")
            op = op_spec["op"]
            if type(op) is not str:
                raise ValueError(
                    f"Op {i} in program '{pid}': "
                    f"'op' must be a string, got {type(op).__name__}")
            if op not in OPCODE_SCHEMAS:
                raise ValueError(
                    f"Unknown opcode '{op}' in program '{pid}'")

            # Per-opcode schema validation (closed IR)
            schema = OPCODE_SCHEMAS[op]
            op_required = schema["required"]
            op_optional = schema["optional"]
            actual_keys = set(op_spec.keys())
            allowed_keys = {"op"} | op_required | op_optional | GLOBAL_OP_OPTIONAL
            for k in op_required:
                if k not in op_spec:
                    raise ValueError(
                        f"Op '{op}' in program '{pid}' missing "
                        f"required field '{k}'")
            for k in actual_keys:
                if k not in allowed_keys:
                    raise ValueError(
                        f"Op '{op}' in program '{pid}' has "
                        f"unknown field '{k}'")

            # Semantic checks per opcode
            if op == "assert_focus_kind":
                kind_val = op_spec["kind"]
                if type(kind_val) is not str:
                    raise ValueError(
                        f"Op 'assert_focus_kind' in program '{pid}': "
                        f"'kind' must be a string, got "
                        f"{type(kind_val).__name__}")
                if kind_val not in SUPPORTED_KINDS:
                    raise ValueError(
                        f"Op 'assert_focus_kind' in program '{pid}': "
                        f"unsupported kind '{kind_val}'")

            # Path validation for all ops that have 'path'
            if "path" in op_required:
                _validate_path(
                    op_spec["path"],
                    f"Op '{op}' in program '{pid}'")

            # capture_path.name must be a string
            if op == "capture_path":
                if type(op_spec["name"]) is not str:
                    raise ValueError(
                        f"Op 'capture_path' in program '{pid}': "
                        "'name' must be a string")

            # check_captured_equal.capture_name must be a string
            if op == "check_captured_equal":
                if type(op_spec["capture_name"]) is not str:
                    raise ValueError(
                        f"Op 'check_captured_equal' in program '{pid}': "
                        "'capture_name' must be a string")

            # check_equal.value: float scan
            if op == "check_equal":
                _check_no_floats(op_spec["value"])

            # assert_key_profile semantic checks
            if op == "assert_key_profile":
                req_field = op_spec["required"]
                if type(req_field) is not list:
                    raise ValueError(
                        f"Op 'assert_key_profile' in program '{pid}': "
                        "'required' must be a list")
                for item in req_field:
                    if type(item) is not str:
                        raise ValueError(
                            f"Op 'assert_key_profile' in program '{pid}': "
                            "'required' items must be strings")
                if "optional" in op_spec:
                    opt_field = op_spec["optional"]
                    if type(opt_field) is not list:
                        raise ValueError(
                            f"Op 'assert_key_profile' in program '{pid}': "
                            "'optional' must be a list")
                    for opt_entry in opt_field:
                        if type(opt_entry) is not dict:
                            raise ValueError(
                                f"Op 'assert_key_profile' in program '{pid}': "
                                "optional entry must be a dict")
                        # Validate opt_entry keys before membership checks
                        for ek in opt_entry:
                            if type(ek) is not str:
                                raise ValueError(
                                    f"Op 'assert_key_profile' in program "
                                    f"'{pid}': optional entry key must be "
                                    f"a string, got {type(ek).__name__}")
                        if "key" not in opt_entry:
                            raise ValueError(
                                f"Op 'assert_key_profile' in program '{pid}': "
                                "optional entry missing 'key'")
                        # Closed inner dict: only {key, allowed_values} allowed
                        for ek in opt_entry:
                            if ek not in _OPT_ENTRY_ALLOWED_KEYS:
                                raise ValueError(
                                    f"Op 'assert_key_profile' in program "
                                    f"'{pid}': optional entry has unknown "
                                    f"key '{ek}'")
                        if type(opt_entry["key"]) is not str:
                            raise ValueError(
                                f"Op 'assert_key_profile' in program '{pid}': "
                                "optional entry 'key' must be a string")
                        if "allowed_values" in opt_entry:
                            av = opt_entry["allowed_values"]
                            if type(av) is not list:
                                raise ValueError(
                                    f"Op 'assert_key_profile' in program "
                                    f"'{pid}': 'allowed_values' must be a list")
                            for av_item in av:
                                _check_no_floats(av_item)

            # write_path: validate template
            if op == "write_path":
                _validate_template(op_spec["template"])

    if order != actual_order:
        raise ValueError(
            f"program_order mismatch: order={order}, actual={actual_order}")


# Sentinel for "no write_path executed yet" (distinct from null, a valid Mu value)
_UNSET = object()


# ---------------------------------------------------------------------------
# VM step — single dispatch cycle
# ---------------------------------------------------------------------------


def _stage0_vm_step_trusted(bundle, input_value, max_ops=MAX_VM_OPS_PER_STEP):
    """Internal: full dispatch body. Caller must prove loader-cached bundle.

    W6A fast path: skips validate_bundle for trusted callers. All production
    call sites route through step_mu._step_kernel_with_vm or match_mu dispatch
    loop, which use loader-cached bundles from make_compiled_bundle_loader.

    Source-lock enforced by tests/l4_gates/test_stage0_vm_trusted_path_gate.py.
    """
    programs = bundle["programs"]
    program_map = {p["id"]: p for p in programs}  # AST_OK: infra index programs by ID for dispatch
    order = bundle["program_order"]

    op_count = 0
    attempt_count = 0

    for program_id in order:
        program = program_map[program_id]
        ops = program["ops"]

        # T1: Begin attempt — no deep copy needed (no op mutates input_root)
        input_root = input_value
        captures = {}
        pending_root = _UNSET
        attempt_count += 1
        failed = False

        for op_spec in ops:
            op_count += 1
            if op_count > max_ops:
                raise Stage0VMError(
                    f"Op limit exceeded ({max_ops}) "
                    f"during program '{program_id}'")

            op = op_spec["op"]

            # ---- assert_focus_kind ----
            if op == "assert_focus_kind":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok or _classify_kind(val) != op_spec["kind"]:
                    failed = True
                    break

            # ---- assert_key_profile ----
            elif op == "assert_key_profile":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok or type(val) is not dict:
                    failed = True
                    break

                required = set(op_spec["required"])
                optional_specs = op_spec.get("optional", [])
                optional_keys = set()
                optional_constraints = {}
                for opt in optional_specs:
                    k = opt["key"]
                    optional_keys.add(k)
                    av = opt.get("allowed_values")
                    if av is not None:
                        optional_constraints[k] = av

                actual = set(val.keys())
                if not required.issubset(actual):
                    failed = True
                    break
                if not actual.issubset(required | optional_keys):
                    failed = True
                    break

                for k, allowed in optional_constraints.items():
                    if k in actual:
                        if not any(_safe_mu_deep_equal(val[k], a) for a in allowed):
                            failed = True
                            break
                if failed:
                    break

            # ---- check_equal ----
            elif op == "check_equal":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok or not _safe_mu_deep_equal(val, op_spec["value"]):
                    failed = True
                    break

            # ---- check_captured_equal ----
            elif op == "check_captured_equal":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok:
                    failed = True
                    break
                cname = op_spec["capture_name"]
                if cname not in captures:
                    raise Stage0VMError(
                        f"check_captured_equal: '{cname}' not yet captured "
                        f"in program '{program_id}'")
                if not _safe_mu_deep_equal(val, captures[cname]):
                    failed = True
                    break

            # ---- capture_path ----
            elif op == "capture_path":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok:
                    failed = True
                    break
                name = op_spec["name"]
                if name in captures:
                    raise Stage0VMError(
                        f"capture_path: duplicate capture '{name}' "
                        f"in program '{program_id}'")
                captures[name] = _safe_mu_copy(
                    val, reject_non_mu=True, context="capture_path")

            # ---- write_path ----
            elif op == "write_path":
                pending_root = _materialize_template(
                    op_spec["template"], captures)

            # ---- return_projection_success ----
            elif op == "return_projection_success":
                if pending_root is _UNSET:
                    raise Stage0VMError(
                        f"return_projection_success without write_path "
                        f"in program '{program_id}'")
                return {
                    "status": "match",
                    "matched_program_id": program_id,
                    "root": pending_root,
                    "metrics": {
                        "program_attempts": attempt_count,
                        "op_steps": op_count,
                    },
                }

            # ---- return_projection_fail ----
            elif op == "return_projection_fail":
                failed = True
                break

            # ---- check_exists (provisional) ----
            elif op == "check_exists":
                _, ok = _resolve_path(input_root, op_spec["path"])
                if not ok:
                    failed = True
                    break

            else:
                # Should never reach here if validate_bundle was called
                raise Stage0VMError(f"Unknown opcode: '{op}'")

        # Post-ops: if we didn't return (success) and didn't fail, the
        # program is malformed — ops exhausted without terminal opcode.
        if not failed:
            raise Stage0VMError(
                f"Program '{program_id}' exhausted ops without "
                "return_projection_success or projection failure")

        # T4: Discard attempt — captures + pending discarded implicitly
        # by loop variable rebinding on next iteration.

    # No program matched — stall
    return {
        "status": "stall",
        "matched_program_id": None,
        "root": input_value,
        "metrics": {
            "program_attempts": attempt_count,
            "op_steps": op_count,
        },
    }


def stage0_vm_step(bundle, input_value, max_ops=MAX_VM_OPS_PER_STEP):
    """Execute one dispatch cycle: try each program, first-match-wins.

    Public wrapper: validates then delegates to _stage0_vm_step_trusted.
    Unchanged signature for backward compatibility.

    Returns::

        {"status": "match" | "stall",
         "matched_program_id": str | None,
         "root": <Mu>,
         "metrics": {"program_attempts": int, "op_steps": int}}

    On "match": root is the committed pending_root from the winning program.
    On "stall": root is the unchanged input_value (no program matched).
    """
    validate_bundle(bundle)
    return _stage0_vm_step_trusted(bundle, input_value, max_ops)


# ---------------------------------------------------------------------------
# VM run — multi-step until stall
# ---------------------------------------------------------------------------

def stage0_vm_run(bundle, input_value, max_steps=100, max_ops=None):
    """Run VM in a loop until stall (no program matches).

    Each iteration calls stage0_vm_step and feeds the committed root
    back as the next input.  Terminates when the VM stalls.

    Args:
        max_ops: Per-step op limit forwarded to stage0_vm_step.
            None uses default MAX_VM_OPS_PER_STEP.

    Returns::

        {"status": "complete",
         "root": <final Mu>,
         "steps": [{"program_id": str, "root": <Mu>}, ...],
         "metrics": {"total_steps": int, "total_attempts": int,
                     "total_ops": int}}
    """
    current = input_value
    steps = []
    total_attempts = 0
    total_ops = 0

    # Build kwargs for stage0_vm_step; omit max_ops if None to use default
    step_kwargs = {"max_ops": max_ops} if max_ops is not None else {}

    for _ in range(max_steps):
        result = stage0_vm_step(bundle, current, **step_kwargs)
        total_attempts += result["metrics"]["program_attempts"]
        total_ops += result["metrics"]["op_steps"]

        if result["status"] == "stall":
            return {
                "status": "complete",
                "root": current,
                "steps": steps,
                "metrics": {
                    "total_steps": len(steps),
                    "total_attempts": total_attempts,
                    "total_ops": total_ops,
                },
            }

        steps.append({
            "program_id": result["matched_program_id"],
            "root": result["root"],
        })
        current = result["root"]

    raise Stage0VMError(f"Run step limit exceeded ({max_steps})")


# ---------------------------------------------------------------------------
# VM bounded run — structured outcome (no exceptions on exhaustion)
# ---------------------------------------------------------------------------

def _run_bounded_impl(step_fn, bundle, input_value, *,
                      max_steps=1000,
                      terminal_field="mode",
                      terminal_value=None):
    """Internal: shared bounded-run loop logic.

    W6A refactor: parameterized by step_fn to allow both trusted and public
    callers without duplicating loop code. Does NOT validate bundle — that is
    the caller's responsibility.

    Args:
        step_fn: Step function to call (stage0_vm_step or _stage0_vm_step_trusted).
        bundle: Stage0 bundle (validation is caller's responsibility).
        input_value: Initial Mu state.
        max_steps: Maximum VM dispatch cycles.
        terminal_field: Dict key for terminal detection.
        terminal_value: Value indicating terminal state.

    Returns:
        {"status": "terminal" | "stall" | "exhaustion",
         "root": <final Mu state>,
         "steps": int}
    """
    current = input_value

    def _is_terminal(state):
        return (terminal_value is not None
                and type(state) is dict
                and state.get(terminal_field) == terminal_value)

    steps = 0

    for _ in range(max_steps):
        # Pre-step terminal fast path.
        # Avoids unnecessary VM dispatch for already-terminal input.
        if _is_terminal(current):
            return {
                "status": "terminal",
                "root": current,
                "steps": steps,
            }

        result = step_fn(bundle, current)

        if result["status"] == "match":
            current = result["root"]
            steps += 1
            continue

        # VM stall — no projection matched.
        # Check if state is terminal (VM stall IS the terminal signal).
        if _is_terminal(current):
            return {
                "status": "terminal",
                "root": current,
                "steps": steps,
            }

        return {
            "status": "stall",
            "root": current,
            "steps": steps,
        }

    # Exhaustion — terminal-on-last-step check
    if _is_terminal(current):
        return {
            "status": "terminal",
            "root": current,
            "steps": steps,
        }

    return {
        "status": "exhaustion",
        "root": current,
        "steps": steps,
    }


def stage0_vm_run_bounded(bundle, input_value, *,
                          max_steps=1000,
                          terminal_field="mode",
                          terminal_value=None):
    """Bounded VM run with structured outcome for Python boundary callers.

    Public wrapper: validates UPFRONT then delegates to _run_bounded_impl
    with _stage0_vm_step_trusted. This ensures fail-closed validation even
    for the immediate-terminal fast path (B2.1 fix).

    Unlike stage0_vm_run (which raises on step-limit exhaustion), this
    function returns a structured result for all three outcomes: terminal,
    stall, and exhaustion. Designed as a shared bootstrap helper for
    classify_mu, subst_mu, and other callers that need
    bounded-run semantics on top of stage0_vm_step.

    Terminal detection is declarative: checks
        type(state) is dict and state.get(terminal_field) == terminal_value
    after each VM stall. Under VM dispatch, terminal states don't match any
    compiled projection, so stage0_vm_step returns "stall". The terminal
    check distinguishes "done" from "genuinely stuck."

    Does NOT consume the global step budget. Budget accounting is a caller
    concern — different callers have different accounting needs.

    This is a Python-only boundary helper, NOT a JS parity target.
    stage0_vm_run() remains the JS-mirrored contract.

    Args:
        bundle: Validated Stage0 bundle.
        input_value: Initial Mu state.
        max_steps: Maximum VM dispatch cycles (default 1000).
        terminal_field: Dict key to check for terminal state (default "mode").
        terminal_value: Value that indicates terminal (e.g., "classify_done").
            If None, terminal detection is disabled (run to stall/exhaustion).

    Returns::

        {"status": "terminal" | "stall" | "exhaustion",
         "root": <final Mu state>,
         "steps": int}

    Outcome semantics:
        terminal:   state.get(terminal_field) == terminal_value detected
                    on VM stall or after max_steps. steps = successful matches.
        stall:      VM stall and state is NOT terminal. steps < max_steps.
        exhaustion: max_steps reached without terminal or stall.
                    steps == max_steps.
    """
    validate_bundle(bundle)
    return _run_bounded_impl(
        _stage0_vm_step_trusted, bundle, input_value,
        max_steps=max_steps,
        terminal_field=terminal_field,
        terminal_value=terminal_value,
    )


def _stage0_vm_run_bounded_trusted(bundle, input_value, *,
                                   max_steps=1000,
                                   terminal_field="mode",
                                   terminal_value=None):
    """Internal: bounded run without validation. Caller must prove loader-cached bundle.

    W6A fast path: for classify_mu, subst_mu, and other trusted callers that
    use loader-cached bundles. Skips validate_bundle entirely.

    Source-lock enforced by tests/l4_gates/test_stage0_vm_trusted_path_gate.py.
    """
    return _run_bounded_impl(
        _stage0_vm_step_trusted, bundle, input_value,
        max_steps=max_steps,
        terminal_field=terminal_field,
        terminal_value=terminal_value,
    )


# =============================================================================
# Compiled Bundle Loader Factory (Wave 3C — consolidates duplicate loaders)
# =============================================================================

def make_compiled_bundle_loader(bundle_name: str):
    """Create a compiled-bundle loader with validation + N15 provenance.

    Returns (load_fn, clear_fn) pair. The load_fn caches after first load.
    Importable from any module without circular dependencies.

    Args:
        bundle_name: e.g. "subst_v2", "match_v2", "kernel_v1", "bootstrap_structural_v1"
                     Maps to mu/stage0/compiled/{bundle_name}.compiled.v1.json

    Returns:
        (load_fn, clear_fn) where:
            load_fn() -> dict: loads, validates, verifies provenance, caches
            clear_fn() -> None: clears the cache
    """
    _cache = [None]  # mutable container for closure

    def _load() -> dict:
        if _cache[0] is not None:
            return _cache[0]

        from .seed_integrity import SEED_CHECKSUMS, get_mu_dir  # ANTICHEAT_OK: infra — provenance

        import json as _json
        bundle_path = get_mu_dir() / "stage0" / "compiled" / f"{bundle_name}.compiled.v1.json"
        if not bundle_path.exists():
            raise FileNotFoundError(f"Compiled bundle not found: {bundle_path}")

        with open(bundle_path, encoding="utf-8") as f:
            bundle = _json.load(f)

        validate_bundle(bundle)

        # N15 provenance verification
        source_seed = bundle.get("source_seed")
        source_digest = bundle.get("source_digest")
        if source_seed and source_digest:
            seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
            if seed_filename in SEED_CHECKSUMS:
                expected = "sha256:" + SEED_CHECKSUMS[seed_filename]
                if source_digest != expected:  # AST_OK:infra — type guard
                    raise ValueError(
                        f"SECURITY: Bundle provenance mismatch for '{seed_filename}'. "
                        f"Bundle claims source_digest={source_digest}, "
                        f"but SEED_CHECKSUMS says {expected}."
                    )

        _cache[0] = bundle
        return bundle

    def _clear() -> None:
        _cache[0] = None

    return _load, _clear
