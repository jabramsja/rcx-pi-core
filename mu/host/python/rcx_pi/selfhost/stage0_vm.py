"""Stage0 VM: data-driven execution of Stage0 IR bundles.

This VM executes derived bundles (hand-authored or compiled from seeds)
using a tiny set of opcodes. The VM is intentionally dumb — all semantic
knowledge lives in the bundle data, not in the VM.

P7-a prototype. NOT wired into production step_kernel_mu().
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
    """Map a Mu value to its Stage0 kind string."""
    if value is None:
        return "null"
    if isinstance(value, bool):      # bool before int (Python subclass)
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    return None


# ---------------------------------------------------------------------------
# Structural equality
# ---------------------------------------------------------------------------

def _mu_deep_equal(a, b):
    """Deep structural equality for Mu values.

    Handles None, bool, int, float, str, dict, list.
    bool and int are distinct types (True != 1).
    """
    if a is None:
        return b is None
    if b is None:
        return False
    if type(a) is not type(b):
        return False
    if isinstance(a, (bool, int, float, str)):
        return a == b
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_mu_deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(_mu_deep_equal(x, y) for x, y in zip(a, b))
    return False


def _safe_mu_deep_equal(a, b):
    # AST_OK: error boundary — translates host RecursionError to Stage0VMError
    """Structural equality with recursion overflow protection."""
    try:
        return _mu_deep_equal(a, b)
    except RecursionError:
        raise Stage0VMError(
            "Structural equality depth exceeded (recursion overflow)")


# ---------------------------------------------------------------------------
# Structural deep copy (no stdlib — Mu values only)
# ---------------------------------------------------------------------------

def _mu_copy(value):
    """Deep-copy a Mu value using only primitives (no copy/json imports)."""
    if isinstance(value, dict):
        return {k: _mu_copy(v) for k, v in value.items()}  # AST_OK: bootstrap structural copy of Mu dict
    if isinstance(value, list):
        return [_mu_copy(item) for item in value]  # AST_OK: bootstrap structural copy of Mu list
    # Primitives (str, int, float, bool, None) are immutable — return as-is
    return value


def _safe_mu_copy(value):
    # AST_OK: error boundary — translates host RecursionError to Stage0VMError
    """Deep-copy with recursion overflow protection."""
    try:
        return _mu_copy(value)
    except RecursionError:
        raise Stage0VMError(
            "Deep copy depth exceeded (recursion overflow)")


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
            raise ValueError(f"Invalid template node: {node!r}")
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
        return captures[name]

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
        if "ops" not in prog:
            raise ValueError(f"Program '{prog['id']}' missing 'ops'")
        # Closed-IR: reject unknown program-level keys
        for pk in prog:
            if pk not in _PROGRAM_ALLOWED_KEYS:
                raise ValueError(
                    f"Program '{prog['id']}' has unknown key '{pk}'")
        pid = prog["id"]
        if type(pid) is not str:
            raise ValueError(
                f"Program 'id' must be a string, got {type(pid).__name__}")
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

def stage0_vm_step(bundle, input_value, max_ops=MAX_VM_OPS_PER_STEP):
    """Execute one dispatch cycle: try each program, first-match-wins.

    Returns::

        {"status": "match" | "stall",
         "matched_program_id": str | None,
         "root": <Mu>,
         "metrics": {"program_attempts": int, "op_steps": int}}

    On "match": root is the committed pending_root from the winning program.
    On "stall": root is the unchanged input_value (no program matched).
    """
    validate_bundle(bundle)
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
                captures[name] = val

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


# ---------------------------------------------------------------------------
# VM run — multi-step until stall
# ---------------------------------------------------------------------------

def stage0_vm_run(bundle, input_value, max_steps=100):
    """Run VM in a loop until stall (no program matches).

    Each iteration calls stage0_vm_step and feeds the committed root
    back as the next input.  Terminates when the VM stalls.

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

    for _ in range(max_steps):
        result = stage0_vm_step(bundle, current)
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
