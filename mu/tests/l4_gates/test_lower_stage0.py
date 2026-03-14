"""Tests for the Stage0 lowering compiler (tools/compilers/lower_stage0.py).

Tests verify:
1. Compilation smoke (validate_bundle passes)
2. Program count parity (seed projections == bundle programs)
3. Program ID parity (IDs match in order)
4. Semantic parity (VM execution identical to hand-authored bundles)
5. Non-linear variable correctness (check_captured_equal emitted correctly)
6. Deterministic regeneration (compile twice → byte-identical)
7. Float/unsupported rejection
8. Source map completeness
9. Capture reference integrity (validate_references catches defects)
"""

import json
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

_REPO_ROOT = REPO_ROOT
sys.path.insert(0, str(_REPO_ROOT / "mu" / "host" / "python"))

# lower_stage0 lives at tools/compilers/lower_stage0.py (symlinked from mu/tools/)
_COMPILER_DIR = _REPO_ROOT / "tools" / "compilers"
sys.path.insert(0, str(_COMPILER_DIR))

from rcx_pi.selfhost.stage0_vm import (  # noqa: E402
    stage0_vm_step,
    validate_bundle,
)

from lower_stage0 import (  # noqa: E402
    CompilerError,
    compile_body,
    compile_pattern,
    compile_seed,
    load_seed,
    serialize_bundle,
    validate_references,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEED_DIR = _REPO_ROOT / "mu" / "substrate"
EXAMPLE_DIR = _REPO_ROOT / "mu" / "stage0" / "examples"

MATCH_SEED = SEED_DIR / "match.v2.json"
SUBST_SEED = SEED_DIR / "subst.v2.json"
MATCH_HAND = EXAMPLE_DIR / "match_v2_bundle.v1.json"
SUBST_HAND = EXAMPLE_DIR / "subst_v2_bundle.v1.json"


def _load_bundle(path):
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def match_compiled():
    seed, filename, digest = load_seed(MATCH_SEED)
    return compile_seed(seed, filename, digest)


@pytest.fixture
def subst_compiled():
    seed, filename, digest = load_seed(SUBST_SEED)
    return compile_seed(seed, filename, digest)


@pytest.fixture
def match_hand():
    return _load_bundle(MATCH_HAND)


@pytest.fixture
def subst_hand():
    return _load_bundle(SUBST_HAND)


# ---------------------------------------------------------------------------
# Test 1: Compilation smoke (validate_bundle passes)
# ---------------------------------------------------------------------------

class TestCompilationSmoke:
    def test_match_v2_compiles(self, match_compiled):
        """match.v2.json compiles and passes validate_bundle."""
        validate_bundle(match_compiled)

    def test_subst_v2_compiles(self, subst_compiled):
        """subst.v2.json compiles and passes validate_bundle."""
        validate_bundle(subst_compiled)


# ---------------------------------------------------------------------------
# Test 2: Program count parity
# ---------------------------------------------------------------------------

class TestProgramCount:
    def test_match_count(self, match_compiled):
        assert len(match_compiled["programs"]) == 8

    def test_subst_count(self, subst_compiled):
        assert len(subst_compiled["programs"]) == 13


# ---------------------------------------------------------------------------
# Test 3: Program ID parity
# ---------------------------------------------------------------------------

class TestProgramIDParity:
    def test_match_ids(self, match_compiled, match_hand):
        compiled_ids = [p["id"] for p in match_compiled["programs"]]
        hand_ids = [p["id"] for p in match_hand["programs"]]
        assert compiled_ids == hand_ids

    def test_subst_ids(self, subst_compiled, subst_hand):
        compiled_ids = [p["id"] for p in subst_compiled["programs"]]
        hand_ids = [p["id"] for p in subst_hand["programs"]]
        assert compiled_ids == hand_ids

    def test_match_program_order(self, match_compiled, match_hand):
        assert match_compiled["program_order"] == match_hand["program_order"]

    def test_subst_program_order(self, subst_compiled, subst_hand):
        assert subst_compiled["program_order"] == subst_hand["program_order"]


# ---------------------------------------------------------------------------
# Test 4: Semantic parity (VM execution)
# ---------------------------------------------------------------------------

# Test vectors: inputs that exercise different match/subst projections

MATCH_TEST_VECTORS = [
    # match.wrap → match.equal → match.done (literal match)
    {
        "match": {"pattern": "hello", "value": "hello"},
        "_match_ctx": {"caller": "test"},
    },
    # match.wrap → match.var → match.done (variable bind)
    {
        "match": {"pattern": {"var": "x"}, "value": 42},
        "_match_ctx": {"caller": "test"},
    },
    # match.wrap → match.fail (mismatch)
    {
        "match": {"pattern": "a", "value": "b"},
        "_match_ctx": {"caller": "test"},
    },
    # match.wrap → match.dict.descend → match.equal → ... (dict structure)
    {
        "match": {
            "pattern": {"head": "a", "tail": "b"},
            "value": {"head": "a", "tail": "b"},
        },
        "_match_ctx": {"caller": "test"},
    },
    # match.wrap → match.typed.descend (type-tagged)
    {
        "match": {
            "pattern": {"_type": "list", "head": {"var": "h"}, "tail": {"var": "t"}},
            "value": {"_type": "list", "head": 1, "tail": 2},
        },
        "_match_ctx": {"caller": "test"},
    },
    # match.wrap → null match (both null)
    {
        "match": {"pattern": None, "value": None},
        "_match_ctx": {"caller": "test"},
    },
]

SUBST_TEST_VECTORS = [
    # subst.wrap → subst.primitive → subst.done (literal passthrough)
    {
        "subst": {"body": "hello", "bindings": None},
        "_subst_ctx": {"caller": "test"},
    },
    # subst.wrap → subst.var → subst.lookup.found → subst.done
    {
        "subst": {
            "body": {"var": "x"},
            "bindings": {"name": "x", "value": 42, "rest": None},
        },
        "_subst_ctx": {"caller": "test"},
    },
    # subst.wrap → subst.var → subst.lookup.exhausted → subst.done (unbound)
    {
        "subst": {
            "body": {"var": "missing"},
            "bindings": None,
        },
        "_subst_ctx": {"caller": "test"},
    },
    # subst.wrap → subst.descend → subst.primitive → subst.sibling → ...
    {
        "subst": {
            "body": {"head": {"var": "x"}, "tail": "lit"},
            "bindings": {"name": "x", "value": 99, "rest": None},
        },
        "_subst_ctx": {"caller": "test"},
    },
    # subst.wrap → subst.typed.descend (type-tagged)
    {
        "subst": {
            "body": {"_type": "pair", "head": {"var": "a"}, "tail": {"var": "b"}},
            "bindings": {
                "name": "a", "value": 1,
                "rest": {"name": "b", "value": 2, "rest": None},
            },
        },
        "_subst_ctx": {"caller": "test"},
    },
]


def _run_vm_to_completion(bundle, input_value, max_steps=50):
    """Run the VM until stall or max steps, returning the final state."""
    state = input_value
    for _ in range(max_steps):
        result = stage0_vm_step(bundle, state)
        if result["status"] == "stall":
            return state
        state = result["root"]
    return state


class TestSemanticParity:
    """VM execution on same test vectors must produce identical results."""

    @pytest.mark.parametrize("test_input", MATCH_TEST_VECTORS,
                             ids=[f"match_vec_{i}" for i in range(len(MATCH_TEST_VECTORS))])
    def test_match_parity(self, match_compiled, match_hand, test_input):
        compiled_result = _run_vm_to_completion(match_compiled, test_input)
        hand_result = _run_vm_to_completion(match_hand, test_input)
        assert compiled_result == hand_result, (
            f"Divergence on input: {test_input}\n"
            f"Compiled: {compiled_result}\n"
            f"Hand: {hand_result}"
        )

    @pytest.mark.parametrize("test_input", SUBST_TEST_VECTORS,
                             ids=[f"subst_vec_{i}" for i in range(len(SUBST_TEST_VECTORS))])
    def test_subst_parity(self, subst_compiled, subst_hand, test_input):
        compiled_result = _run_vm_to_completion(subst_compiled, test_input)
        hand_result = _run_vm_to_completion(subst_hand, test_input)
        assert compiled_result == hand_result, (
            f"Divergence on input: {test_input}\n"
            f"Compiled: {compiled_result}\n"
            f"Hand: {hand_result}"
        )


# ---------------------------------------------------------------------------
# Test 5: Non-linear variable correctness
# ---------------------------------------------------------------------------

class TestNonLinearVariables:
    def test_match_equal_has_check_captured_equal(self, match_compiled):
        """match.equal must use check_captured_equal for non-linear var 'same'."""
        prog = next(p for p in match_compiled["programs"]
                     if p["id"] == "match.equal")
        ops = prog["ops"]
        # Find capture_path for "same"
        capture_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "capture_path" and op["name"] == "same"
        )
        # Find check_captured_equal for "same"
        check_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "check_captured_equal"
            and op["capture_name"] == "same"
        )
        assert capture_idx < check_idx, (
            f"capture_path for 'same' (idx {capture_idx}) must precede "
            f"check_captured_equal (idx {check_idx})"
        )

    def test_subst_lookup_found_has_check_captured_equal(self, subst_compiled):
        """subst.lookup.found must use check_captured_equal for non-linear var 'n'."""
        prog = next(p for p in subst_compiled["programs"]
                     if p["id"] == "subst.lookup.found")
        ops = prog["ops"]
        capture_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "capture_path" and op["name"] == "n"
        )
        check_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "check_captured_equal"
            and op["capture_name"] == "n"
        )
        assert capture_idx < check_idx

    def test_match_typed_descend_has_check_captured_equal(self, match_compiled):
        """match.typed.descend must use check_captured_equal for non-linear var 'type'."""
        prog = next(p for p in match_compiled["programs"]
                     if p["id"] == "match.typed.descend")
        ops = prog["ops"]
        capture_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "capture_path" and op["name"] == "type"
        )
        check_idx = next(
            i for i, op in enumerate(ops)
            if op["op"] == "check_captured_equal"
            and op["capture_name"] == "type"
        )
        assert capture_idx < check_idx


# ---------------------------------------------------------------------------
# Test 6: Deterministic regeneration
# ---------------------------------------------------------------------------

class TestDeterministicRegeneration:
    def test_match_deterministic(self):
        seed, filename, digest = load_seed(MATCH_SEED)
        bundle1 = compile_seed(seed, filename, digest)
        bundle2 = compile_seed(seed, filename, digest)
        assert serialize_bundle(bundle1) == serialize_bundle(bundle2)

    def test_subst_deterministic(self):
        seed, filename, digest = load_seed(SUBST_SEED)
        bundle1 = compile_seed(seed, filename, digest)
        bundle2 = compile_seed(seed, filename, digest)
        assert serialize_bundle(bundle1) == serialize_bundle(bundle2)


# ---------------------------------------------------------------------------
# Test 7: Float/unsupported rejection
# ---------------------------------------------------------------------------

class TestRejection:
    def test_float_in_pattern_rejected(self):
        """Compiler rejects float literals in patterns."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [{
                "id": "test.float",
                "pattern": {"mode": 3.14},
                "body": {"var": "x"},
            }],
        }
        with pytest.raises(CompilerError, match="Float literals unsupported"):
            compile_seed(fake_seed, "test.json")

    def test_float_in_body_rejected(self):
        """Compiler rejects float literals in body templates."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [{
                "id": "test.float_body",
                "pattern": {"mode": "test"},
                "body": {"result": 2.718},
            }],
        }
        with pytest.raises(CompilerError, match="Float literals unsupported"):
            compile_seed(fake_seed, "test.json")

    def test_list_pattern_rejected(self):
        """Compiler rejects list patterns (unsupported)."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [{
                "id": "test.list_pattern",
                "pattern": [1, 2, 3],
                "body": "done",
            }],
        }
        with pytest.raises(CompilerError, match="List patterns unsupported"):
            compile_seed(fake_seed, "test.json")


# ---------------------------------------------------------------------------
# Test 8: Source map completeness
# ---------------------------------------------------------------------------

class TestSourceMaps:
    def test_every_op_has_source_map(self, match_compiled):
        for prog in match_compiled["programs"]:
            for i, op_spec in enumerate(prog["ops"]):
                assert "source_map" in op_spec, (
                    f"Program '{prog['id']}' op {i} ({op_spec['op']}) "
                    f"missing source_map"
                )

    def test_every_program_has_source_map(self, subst_compiled):
        for prog in subst_compiled["programs"]:
            assert "source_map" in prog, (
                f"Program '{prog['id']}' missing source_map"
            )
            sm = prog["source_map"]
            assert "seed_file" in sm
            assert "projection_id" in sm
            assert "projection_index" in sm


# ---------------------------------------------------------------------------
# Test 9: Capture reference integrity (validate_references)
# ---------------------------------------------------------------------------

class TestCaptureReferenceIntegrity:
    def test_undefined_capture_ref_rejected(self):
        """Template referencing undefined capture is rejected."""
        bad_program = {
            "id": "test.bad_ref",
            "ops": [
                {"op": "capture_path", "path": ["focus", "root", "x"],
                 "name": "a"},
                {"op": "write_path", "template": {
                    "kind": "capture_ref", "name": "nonexistent",
                }},
                {"op": "return_projection_success"},
            ],
        }
        with pytest.raises(CompilerError, match="capture_ref 'nonexistent'"):
            validate_references(bad_program)

    def test_check_captured_equal_before_capture_rejected(self):
        """check_captured_equal before capture_path is rejected."""
        bad_program = {
            "id": "test.bad_order",
            "ops": [
                {"op": "check_captured_equal",
                 "path": ["focus", "root", "x"],
                 "capture_name": "v"},
                {"op": "capture_path", "path": ["focus", "root", "y"],
                 "name": "v"},
                {"op": "write_path", "template": {
                    "kind": "capture_ref", "name": "v",
                }},
                {"op": "return_projection_success"},
            ],
        }
        with pytest.raises(CompilerError,
                           match="check_captured_equal references 'v'"):
            validate_references(bad_program)

    def test_duplicate_capture_name_rejected(self):
        """Duplicate capture_path names are rejected."""
        bad_program = {
            "id": "test.dup_capture",
            "ops": [
                {"op": "capture_path", "path": ["focus", "root", "x"],
                 "name": "a"},
                {"op": "capture_path", "path": ["focus", "root", "y"],
                 "name": "a"},
                {"op": "write_path", "template": {
                    "kind": "capture_ref", "name": "a",
                }},
                {"op": "return_projection_success"},
            ],
        }
        with pytest.raises(CompilerError,
                           match="duplicate capture_path name 'a'"):
            validate_references(bad_program)

    def test_missing_terminal_op_rejected(self):
        """Program without return_projection_success is rejected."""
        bad_program = {
            "id": "test.no_terminal",
            "ops": [
                {"op": "capture_path", "path": ["focus", "root", "x"],
                 "name": "a"},
                {"op": "write_path", "template": {
                    "kind": "capture_ref", "name": "a",
                }},
            ],
        }
        with pytest.raises(CompilerError,
                           match="last op must be return_projection_success"):
            validate_references(bad_program)


# ---------------------------------------------------------------------------
# Test 10: Malformed seed shape rejection (bridge finding #1)
# ---------------------------------------------------------------------------

class TestMalformedSeedRejection:
    def test_meta_null_rejected(self):
        """Seed with meta=null is rejected with CompilerError."""
        fake_seed = {"meta": None, "projections": []}
        with pytest.raises(CompilerError, match="'meta' must be a JSON object"):
            compile_seed(fake_seed, "test.json")

    def test_projections_null_rejected(self):
        """Seed with projections=null is rejected with CompilerError."""
        fake_seed = {"meta": {"version": "1.0.0"}, "projections": None}
        with pytest.raises(CompilerError, match="'projections' must be a JSON array"):
            compile_seed(fake_seed, "test.json")

    def test_projection_missing_pattern_rejected(self):
        """Projection missing 'pattern' is rejected with CompilerError."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [{"id": "test.no_pattern", "body": "done"}],
        }
        with pytest.raises(CompilerError, match="missing 'pattern' field"):
            compile_seed(fake_seed, "test.json")

    def test_projection_missing_body_rejected(self):
        """Projection missing 'body' is rejected with CompilerError."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [{"id": "test.no_body", "pattern": "x"}],
        }
        with pytest.raises(CompilerError, match="missing 'body' field"):
            compile_seed(fake_seed, "test.json")

    def test_meta_not_dict_rejected(self):
        """Seed with meta as a string is rejected."""
        fake_seed = {"meta": "not-a-dict", "projections": []}
        with pytest.raises(CompilerError, match="'meta' must be a JSON object"):
            compile_seed(fake_seed, "test.json")

    def test_projections_not_list_rejected(self):
        """Seed with projections as a dict is rejected."""
        fake_seed = {"meta": {"version": "1.0.0"}, "projections": {}}
        with pytest.raises(CompilerError, match="'projections' must be a JSON array"):
            compile_seed(fake_seed, "test.json")

    def test_meta_missing_version_rejected(self):
        """Seed with meta dict missing 'version' is rejected."""
        fake_seed = {"meta": {}, "projections": []}
        with pytest.raises(CompilerError, match="missing 'version' field"):
            compile_seed(fake_seed, "test.json")

    def test_non_dict_projection_rejected(self):
        """Projection that is not a dict (e.g. int) is rejected."""
        fake_seed = {
            "meta": {"version": "1.0.0"},
            "projections": [123],
        }
        with pytest.raises(CompilerError, match="must be a JSON object"):
            compile_seed(fake_seed, "test.json")


# ---------------------------------------------------------------------------
# Test 11: Fixture lock (checked-in bundles match fresh compiler output)
# ---------------------------------------------------------------------------

COMPILED_DIR = _REPO_ROOT / "mu" / "stage0" / "compiled"
MATCH_COMPILED_PATH = COMPILED_DIR / "match_v2.compiled.v1.json"
SUBST_COMPILED_PATH = COMPILED_DIR / "subst_v2.compiled.v1.json"


class TestFixtureLock:
    def test_match_bundle_matches_checked_in(self):
        """Compiled match.v2 bundle is byte-identical to checked-in artifact."""
        seed, filename, digest = load_seed(MATCH_SEED)
        bundle = compile_seed(seed, filename, digest)
        fresh = serialize_bundle(bundle)
        checked_in = MATCH_COMPILED_PATH.read_text()
        assert fresh == checked_in, (
            f"Checked-in {MATCH_COMPILED_PATH.name} differs from fresh "
            f"compiler output. Regenerate with:\n"
            f"  python tools/compilers/lower_stage0.py "
            f"mu/substrate/match.v2.json -o {MATCH_COMPILED_PATH}"
        )

    def test_subst_bundle_matches_checked_in(self):
        """Compiled subst.v2 bundle is byte-identical to checked-in artifact."""
        seed, filename, digest = load_seed(SUBST_SEED)
        bundle = compile_seed(seed, filename, digest)
        fresh = serialize_bundle(bundle)
        checked_in = SUBST_COMPILED_PATH.read_text()
        assert fresh == checked_in, (
            f"Checked-in {SUBST_COMPILED_PATH.name} differs from fresh "
            f"compiler output. Regenerate with:\n"
            f"  python tools/compilers/lower_stage0.py "
            f"mu/substrate/subst.v2.json -o {SUBST_COMPILED_PATH}"
        )


# ---------------------------------------------------------------------------
# Test 12: Integrity metadata (source_digest + lowering_version)
# ---------------------------------------------------------------------------

class TestIntegrityMetadata:
    def test_compiler_bundle_has_source_digest(self, match_compiled):
        assert "source_digest" in match_compiled
        assert match_compiled["source_digest"].startswith("sha256:")

    def test_compiler_bundle_has_lowering_version(self, match_compiled):
        assert "lowering_version" in match_compiled
        assert match_compiled["lowering_version"] == "1.0.0"

    def test_hand_authored_bundles_validate_without_integrity(self):
        """Hand-authored bundles (hand_authored=true) pass validation
        without source_digest or lowering_version."""
        validate_bundle(_load_bundle(MATCH_HAND))
        validate_bundle(_load_bundle(SUBST_HAND))

    def test_compiler_bundle_missing_digest_rejected(self):
        """Compiler-produced bundle without source_digest is rejected."""
        seed, filename, digest = load_seed(MATCH_SEED)
        bundle = compile_seed(seed, filename, digest)
        del bundle["source_digest"]
        with pytest.raises(ValueError, match="source_digest"):
            validate_bundle(bundle)


# ---------------------------------------------------------------------------
# Test 13: JS cross-substrate parity for compiled bundles
# ---------------------------------------------------------------------------

import os
import subprocess


def _run_js_stage0(action, bundle_path, input_value=None):
    """Call JS Stage0 VM via subprocess and return parsed result."""
    request = {"action": action, "bundle_path": bundle_path}
    if input_value is not None:
        request["input"] = input_value
    runner = os.path.join(str(_REPO_ROOT), "tests", "l4_gates",
                          "stage0_vm_runner.js")
    result = subprocess.run(
        ["node", runner, json.dumps(request)],
        capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=30,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"JS runner produced no JSON response.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}")


MATCH_COMPILED_REL = "mu/stage0/compiled/match_v2.compiled.v1.json"
SUBST_COMPILED_REL = "mu/stage0/compiled/subst_v2.compiled.v1.json"


class TestJSCompiledBundleParity:
    """JS Stage0 VM must accept and execute compiler-produced bundles."""

    def test_js_validates_match_compiled_bundle(self):
        """JS validateBundle accepts the compiled match bundle."""
        result = _run_js_stage0("validate", MATCH_COMPILED_REL)
        assert result.get("ok") is True, (
            f"JS validateBundle rejected compiled match bundle: {result}")

    def test_js_validates_subst_compiled_bundle(self):
        """JS validateBundle accepts the compiled subst bundle."""
        result = _run_js_stage0("validate", SUBST_COMPILED_REL)
        assert result.get("ok") is True, (
            f"JS validateBundle rejected compiled subst bundle: {result}")

    def test_js_compiled_match_execution_parity(self):
        """JS VM run on compiled match bundle produces same final state as Python."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        # Use the real wrapped seed input form (same as MATCH_TEST_VECTORS[0])
        inp = {
            "match": {"pattern": "hello", "value": "hello"},
            "_match_ctx": {"caller": "test"},
        }
        # Run to completion on both substrates
        py_final = _run_vm_to_completion(bundle, inp)
        js_result = _run_js_stage0("run", MATCH_COMPILED_REL, inp)
        # JS run returns {steps: [...], root: ...}
        js_final = js_result["root"]
        assert py_final == js_final, (
            f"Final state mismatch:\npy={py_final}\njs={js_final}")
        # Verify the run actually did something (not a stall on first step)
        assert len(js_result["steps"]) > 0, "JS run produced zero steps"
