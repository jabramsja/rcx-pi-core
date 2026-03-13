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
"""

# Zero stdlib imports — bootstrap-pure module.


# ---------------------------------------------------------------------------
# Resource bounds
# ---------------------------------------------------------------------------

MAX_VM_PROGRAMS = 64
MAX_VM_OPS_PER_STEP = 1024
MAX_TEMPLATE_DEPTH = 32

# ---------------------------------------------------------------------------
# Opcode / kind / template enums
# ---------------------------------------------------------------------------

KNOWN_OPCODES = frozenset({  # AST_OK: key comparison set for O(1) opcode validation
    "assert_focus_kind",
    "assert_key_profile",
    "check_equal",
    "check_captured_equal",
    "capture_path",
    "write_path",
    "return_projection_success",
    "return_projection_fail",
    "check_exists",
})

TEMPLATE_KINDS = frozenset({  # AST_OK: key comparison set for O(1) template kind validation
    "literal", "capture_ref", "object", "list",
})


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
        if not isinstance(current, dict) or key not in current:
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

    if not isinstance(template, dict) or "kind" not in template:
        raise Stage0VMError(f"Invalid template node: {template!r}")

    kind = template["kind"]
    if kind not in TEMPLATE_KINDS:
        raise Stage0VMError(f"Unknown template kind: '{kind}'")

    if kind == "literal":
        value = template["value"]
        # Deep-copy mutable literals to prevent bundle mutation across runs
        if isinstance(value, dict):
            return _mu_copy(value)
        if isinstance(value, list):
            return _mu_copy(value)
        return value

    if kind == "capture_ref":
        name = template["name"]
        if name not in captures:
            raise Stage0VMError(
                f"Template references uncaptured variable: '{name}'")
        return captures[name]

    if kind == "object":
        return {  # AST_OK: bootstrap materialization builds output dict from fields
            key: _materialize_template(val, captures, _depth + 1)
            for key, val in template["fields"].items()
        }

    # kind == "list"
    return [  # AST_OK: bootstrap materialization builds output list from items
        _materialize_template(item, captures, _depth + 1)
        for item in template["items"]
    ]


# ---------------------------------------------------------------------------
# Bundle validation (fail-closed)
# ---------------------------------------------------------------------------

def validate_bundle(bundle):
    """Validate bundle structure.  Raises ValueError on any defect."""
    required = (
        "stage0_ir_version", "bundle_id", "source_seed",
        "machine_profile", "program_order", "programs",
    )
    for field in required:
        if field not in bundle:
            raise ValueError(f"Missing required bundle field: '{field}'")

    if bundle["stage0_ir_version"] != 1:
        raise ValueError(
            f"Unsupported IR version: {bundle['stage0_ir_version']}")
    if bundle["machine_profile"] != "rcx.stage0.v1":
        raise ValueError(
            f"Unsupported machine profile: {bundle['machine_profile']}")

    programs = bundle["programs"]
    order = bundle["program_order"]

    if not isinstance(programs, list):
        raise ValueError("'programs' must be a list")
    if not isinstance(order, list):
        raise ValueError("'program_order' must be a list")
    if len(programs) > MAX_VM_PROGRAMS:
        raise ValueError(
            f"Too many programs: {len(programs)} > {MAX_VM_PROGRAMS}")

    seen_ids = set()
    actual_order = []
    for prog in programs:
        if not isinstance(prog, dict):
            raise ValueError("Each program must be a dict")
        if "id" not in prog:
            raise ValueError("Program missing 'id'")
        if "ops" not in prog:
            raise ValueError(f"Program '{prog['id']}' missing 'ops'")
        pid = prog["id"]
        ops = prog["ops"]
        if not isinstance(ops, list) or not ops:
            raise ValueError(f"Program '{pid}' has empty or non-list ops")
        if pid in seen_ids:
            raise ValueError(f"Duplicate program ID: '{pid}'")
        seen_ids.add(pid)
        actual_order.append(pid)

        for i, op_spec in enumerate(ops):
            if not isinstance(op_spec, dict) or "op" not in op_spec:
                raise ValueError(
                    f"Op {i} in program '{pid}' missing 'op' field")
            if op_spec["op"] not in KNOWN_OPCODES:
                raise ValueError(
                    f"Unknown opcode '{op_spec['op']}' in program '{pid}'")

    if order != actual_order:
        raise ValueError(
            f"program_order mismatch: order={order}, actual={actual_order}")


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
        pending_root = None
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
                if not ok or not isinstance(val, dict):
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
                        if not any(_mu_deep_equal(val[k], a) for a in allowed):
                            failed = True
                            break
                if failed:
                    break

            # ---- check_equal ----
            elif op == "check_equal":
                val, ok = _resolve_path(input_root, op_spec["path"])
                if not ok or not _mu_deep_equal(val, op_spec["value"]):
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
                if not _mu_deep_equal(val, captures[cname]):
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
                if pending_root is None:
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
