"""Stage0 lowering compiler: seed JSON → Stage0 IR bundle.

Mechanical translation of readable seed projections (match.v2.json,
subst.v2.json) into deterministic Stage0 IR bundles that pass
validate_bundle.

Usage:
    python tools/compilers/lower_stage0.py mu/substrate/match.v2.json
    python tools/compilers/lower_stage0.py mu/substrate/match.v2.json -o out.json
    python tools/compilers/lower_stage0.py mu/substrate/match.v2.json --validate-only

Design plan: .scratch/p7b2_design_plan.md
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

# Import validate_bundle from the VM (self-validation layer 2)
# tools/ is a symlink to mu/tools/, so resolve() goes through it.
# Walk up from resolved path until we find pyproject.toml (repo root marker).
def _find_repo_root():
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise RuntimeError("Cannot find repo root (pyproject.toml)")

_REPO_ROOT = _find_repo_root()
sys.path.insert(0, str(_REPO_ROOT / "mu" / "host" / "python"))
from rcx_pi.selfhost.stage0_vm import validate_bundle  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_COMPILE_DEPTH = 64  # Compiler recursion cap; effective path depth is lower due to ["focus","root"] prefix
COMPILER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CompilerError(Exception):
    """Raised when the compiler encounters an invalid or unsupported seed."""


# ---------------------------------------------------------------------------
# Seed loading (fail-closed: rejects duplicate JSON keys)
# ---------------------------------------------------------------------------

def _reject_duplicate_keys(pairs):
    """object_pairs_hook that raises on duplicate JSON keys."""
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise CompilerError(f"Duplicate JSON key: '{key}'")
        seen[key] = value
    return seen


def load_seed(path):
    """Load and validate a seed file. Returns (seed_dict, filename_str, source_digest)."""
    p = Path(path)
    raw_bytes = p.read_bytes()
    source_digest = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()

    seed = json.loads(raw_bytes.decode("utf-8"),
                      object_pairs_hook=_reject_duplicate_keys)

    if not isinstance(seed, dict):
        raise CompilerError("Seed must be a JSON object")
    if "meta" not in seed:
        raise CompilerError("Seed missing 'meta' field")
    if "projections" not in seed:
        raise CompilerError("Seed missing 'projections' field")
    meta = seed["meta"]
    if not isinstance(meta, dict):
        raise CompilerError("Seed 'meta' must be a JSON object")
    if "version" not in meta:
        raise CompilerError("Seed meta missing 'version' field")
    projections = seed["projections"]
    if not isinstance(projections, list):
        raise CompilerError("Seed 'projections' must be a JSON array")

    return seed, p.name, source_digest


# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------

def _is_var_ref(node):
    """Check if a node is a variable reference: {"var": <string>}."""
    return (
        isinstance(node, dict)
        and len(node) == 1
        and "var" in node
        and type(node["var"]) is str
    )


def _check_float(value, context):
    """Reject float literals (unsupported in Stage0 IR v1)."""
    if type(value) is float:
        raise CompilerError(
            f"Float literals unsupported in Stage0 IR v1 ({context})")


def compile_pattern(pattern, base_path, captured_vars, source_path, depth=0):
    """Compile a pattern node to a list of Stage0 ops.

    Args:
        pattern: The pattern node to compile.
        base_path: VM path prefix (e.g., ["focus", "root"]).
        captured_vars: Set of variable names already captured (mutated).
        source_path: Source map path within the seed projection.
        depth: Current recursion depth.

    Returns:
        List of op dicts.
    """
    if depth > MAX_COMPILE_DEPTH:
        raise CompilerError(
            f"Pattern depth exceeds {MAX_COMPILE_DEPTH} at path {base_path}")

    ops = []

    # Literal: null, bool, int, str
    if pattern is None or type(pattern) is bool:
        ops.append({
            "op": "check_equal",
            "path": base_path,
            "value": pattern,
            "source_map": {"section": "pattern", "path": source_path},
        })
        return ops

    if type(pattern) is int:
        ops.append({
            "op": "check_equal",
            "path": base_path,
            "value": pattern,
            "source_map": {"section": "pattern", "path": source_path},
        })
        return ops

    if type(pattern) is str:
        ops.append({
            "op": "check_equal",
            "path": base_path,
            "value": pattern,
            "source_map": {"section": "pattern", "path": source_path},
        })
        return ops

    _check_float(pattern, f"pattern at {source_path}")

    # Variable reference: {"var": <string>}
    if _is_var_ref(pattern):
        var_name = pattern["var"]
        if var_name in captured_vars:
            ops.append({
                "op": "check_captured_equal",
                "path": base_path,
                "capture_name": var_name,
                "source_map": {"section": "pattern", "path": source_path},
            })
        else:
            captured_vars.add(var_name)
            ops.append({
                "op": "capture_path",
                "path": base_path,
                "name": var_name,
                "source_map": {"section": "pattern", "path": source_path},
            })
        return ops

    # Dict (structural pattern)
    if isinstance(pattern, dict):
        # assert_focus_kind dict
        ops.append({
            "op": "assert_focus_kind",
            "path": base_path,
            "kind": "dict",
            "source_map": {"section": "pattern", "path": source_path},
        })

        # assert_key_profile with source-order keys
        keys = list(pattern.keys())
        ops.append({
            "op": "assert_key_profile",
            "path": base_path,
            "required": keys,
            "optional": [],
            "source_map": {"section": "pattern", "path": source_path},
        })

        # Recurse into each field in source order
        for key in keys:
            child_path = base_path + [key]
            child_source = source_path + [key]
            child_ops = compile_pattern(
                pattern[key], child_path, captured_vars,
                child_source, depth + 1,
            )
            ops.extend(child_ops)

        return ops

    # List patterns not supported (no seed uses them)
    if isinstance(pattern, list):
        raise CompilerError(
            f"List patterns unsupported at {source_path}")

    raise CompilerError(
        f"Unsupported pattern node type: {type(pattern).__name__} "
        f"at {source_path}")


# ---------------------------------------------------------------------------
# Body compilation
# ---------------------------------------------------------------------------

def compile_body(body, depth=0):
    """Compile a body node to a Stage0 template.

    Args:
        body: The body node to compile.
        depth: Current recursion depth.

    Returns:
        A template dict (kind + fields/value/name/items).
    """
    if depth > MAX_COMPILE_DEPTH:
        raise CompilerError(
            f"Body template depth exceeds {MAX_COMPILE_DEPTH}")

    # Literal: null, bool, int, str
    if body is None or type(body) is bool:
        return {"kind": "literal", "value": body}

    if type(body) is int:
        return {"kind": "literal", "value": body}

    if type(body) is str:
        return {"kind": "literal", "value": body}

    _check_float(body, "body template")

    # Variable reference: {"var": <string>}
    if _is_var_ref(body):
        return {"kind": "capture_ref", "name": body["var"]}

    # Dict (object template)
    if isinstance(body, dict):
        fields = {}
        for key, value in body.items():
            fields[key] = compile_body(value, depth + 1)
        return {"kind": "object", "fields": fields}

    # List template
    if isinstance(body, list):
        items = [compile_body(item, depth + 1) for item in body]
        return {"kind": "list", "items": items}

    raise CompilerError(
        f"Unsupported body node type: {type(body).__name__}")


# ---------------------------------------------------------------------------
# Semantic reference validation (compiler-side, layer 1)
# ---------------------------------------------------------------------------

def _collect_template_refs(template, refs=None):
    """Collect all capture_ref names from a template."""
    if refs is None:
        refs = set()
    kind = template.get("kind")
    if kind == "capture_ref":
        refs.add(template["name"])
    elif kind == "object":
        for child in template["fields"].values():
            _collect_template_refs(child, refs)
    elif kind == "list":
        for child in template["items"]:
            _collect_template_refs(child, refs)
    return refs


def validate_references(program):
    """Validate capture-ref integrity within a single program.

    Checks:
    1. Every check_captured_equal references a PRIOR capture_path
    2. No duplicate capture_path names
    3. Every template capture_ref maps to a capture_path
    4. Program ends with return_projection_success
    """
    pid = program["id"]
    ops = program["ops"]
    captured = set()
    capture_order = []

    for i, op_spec in enumerate(ops):
        op = op_spec["op"]

        if op == "capture_path":
            name = op_spec["name"]
            if name in captured:
                raise CompilerError(
                    f"Program '{pid}': duplicate capture_path "
                    f"name '{name}' at op {i}")
            captured.add(name)
            capture_order.append(name)

        elif op == "check_captured_equal":
            name = op_spec["capture_name"]
            if name not in captured:
                raise CompilerError(
                    f"Program '{pid}': check_captured_equal "
                    f"references '{name}' at op {i} but no prior "
                    f"capture_path for '{name}'")

        elif op == "write_path":
            template_refs = _collect_template_refs(op_spec["template"])
            for ref_name in template_refs:
                if ref_name not in captured:
                    raise CompilerError(
                        f"Program '{pid}': template capture_ref "
                        f"'{ref_name}' has no corresponding "
                        f"capture_path")

    # Terminal op check
    if not ops or ops[-1]["op"] != "return_projection_success":
        raise CompilerError(
            f"Program '{pid}': last op must be "
            f"return_projection_success")


# ---------------------------------------------------------------------------
# Program and bundle assembly
# ---------------------------------------------------------------------------

def compile_projection(projection, index, seed_filename):
    """Compile a single seed projection to a Stage0 program."""
    proj_id = projection["id"]
    if "pattern" not in projection:
        raise CompilerError(
            f"Projection '{proj_id}' missing 'pattern' field")
    if "body" not in projection:
        raise CompilerError(
            f"Projection '{proj_id}' missing 'body' field")
    pattern = projection["pattern"]
    body = projection["body"]

    # Compile pattern → ops
    captured_vars = set()
    pattern_ops = compile_pattern(
        pattern,
        base_path=["focus", "root"],
        captured_vars=captured_vars,
        source_path=[],
        depth=0,
    )

    # Compile body → template
    body_template = compile_body(body, depth=0)

    # Assemble program
    ops = [
        *pattern_ops,
        {
            "op": "write_path",
            "template": body_template,
            "source_map": {"section": "body", "path": []},
        },
        {
            "op": "return_projection_success",
            "source_map": {"section": "body", "path": []},
        },
    ]

    program = {
        "id": proj_id,
        "description": projection.get("description", ""),
        "ops": ops,
        "source_map": {
            "seed_file": seed_filename,
            "projection_id": proj_id,
            "projection_index": index,
        },
    }

    # Layer 1: semantic reference validation
    validate_references(program)

    return program


def compile_seed(seed, seed_filename, source_digest=None):
    """Compile a full seed to a Stage0 bundle.

    Args:
        seed: Parsed seed dict.
        seed_filename: Original seed filename (for provenance).
        source_digest: Optional SHA-256 digest of the raw seed file
            (format: "sha256:<hex>"). Required for production bundles;
            omit only for in-memory test seeds.
    """
    if not isinstance(seed.get("meta"), dict):
        raise CompilerError("Seed 'meta' must be a JSON object")
    if "version" not in seed["meta"]:
        raise CompilerError("Seed meta missing 'version' field")
    if not isinstance(seed.get("projections"), list):
        raise CompilerError("Seed 'projections' must be a JSON array")
    projections = seed["projections"]
    programs = []
    program_order = []

    for i, proj in enumerate(projections):
        if not isinstance(proj, dict):
            raise CompilerError(
                f"Projection {i} must be a JSON object, "
                f"got {type(proj).__name__}")
        if "id" not in proj:
            raise CompilerError(
                f"Projection {i} missing 'id' field")
        program = compile_projection(proj, i, seed_filename)
        programs.append(program)
        program_order.append(proj["id"])

    # Derive bundle_id: strip .json, replace . with _
    seed_stem = seed_filename
    if seed_stem.endswith(".json"):
        seed_stem = seed_stem[:-5]
    seed_name = seed_stem.replace(".", "_")

    bundle = {
        "stage0_ir_version": 1,
        "bundle_id": f"rcx.stage0.{seed_name}.compiled.v1",
        "source_seed": seed_filename,
        "source_seed_version": seed["meta"]["version"],
        "lowering_version": COMPILER_VERSION,
        "machine_profile": "rcx.stage0.v1",
        "hand_authored": False,
        "note": (
            f"Compiler-derived from {seed_filename} "
            f"by lower_stage0.py v{COMPILER_VERSION}"
        ),
        "program_order": program_order,
        "programs": programs,
    }

    if source_digest is not None:
        bundle["source_digest"] = source_digest

    # Layer 2: structural schema validation
    validate_bundle(bundle)

    return bundle


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_bundle(bundle):
    """Serialize bundle to deterministic JSON (byte-identical across runs).

    Includes trailing newline for POSIX compliance and consistent
    output between stdout and file modes.
    """
    return json.dumps(
        bundle, sort_keys=True, indent=2, ensure_ascii=True,
    ) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(
            "Usage: python tools/compilers/lower_stage0.py <seed.json> "
            "[-o output.json] [--validate-only]",
            file=sys.stderr,
        )
        sys.exit(0 if args else 1)

    seed_path = args[0]
    output_path = None
    validate_only = False

    i = 1
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        elif args[i] == "--validate-only":
            validate_only = True
            i += 1
        else:
            print(f"Unknown argument: {args[i]}", file=sys.stderr)
            sys.exit(1)

    try:
        seed, seed_filename, source_digest = load_seed(seed_path)
        bundle = compile_seed(seed, seed_filename, source_digest)
    except (OSError, CompilerError, ValueError) as e:
        print(f"Compiler error: {e}", file=sys.stderr)
        sys.exit(1)

    if validate_only:
        proj_count = len(bundle["programs"])
        print(
            f"OK: {seed_filename} → {proj_count} programs, "
            f"validate_bundle passed",
            file=sys.stderr,
        )
        sys.exit(0)

    output = serialize_bundle(bundle)

    if output_path:
        try:
            # Atomic write: temp file + rename to prevent truncated artifacts
            out_dir = os.path.dirname(os.path.abspath(output_path))
            fd, tmp_path = tempfile.mkstemp(
                dir=out_dir, suffix=".tmp", prefix=".lower_stage0_")
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(output)
                os.replace(tmp_path, output_path)
            except BaseException:
                os.unlink(tmp_path)
                raise
        except OSError as e:
            print(f"Compiler error: {e}", file=sys.stderr)
            sys.exit(1)
        print(
            f"Wrote {output_path} "
            f"({len(bundle['programs'])} programs)",
            file=sys.stderr,
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
