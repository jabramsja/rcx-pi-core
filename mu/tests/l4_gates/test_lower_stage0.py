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
    _mu_deep_equal,  # ANTICHEAT_OK: type-strict Mu value comparison
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
        assert _mu_deep_equal(compiled_result, hand_result), (
            f"Divergence on input: {test_input}\n"
            f"Compiled: {compiled_result}\n"
            f"Hand: {hand_result}"
        )

    @pytest.mark.parametrize("test_input", SUBST_TEST_VECTORS,
                             ids=[f"subst_vec_{i}" for i in range(len(SUBST_TEST_VECTORS))])
    def test_subst_parity(self, subst_compiled, subst_hand, test_input):
        compiled_result = _run_vm_to_completion(subst_compiled, test_input)
        hand_result = _run_vm_to_completion(subst_hand, test_input)
        assert _mu_deep_equal(compiled_result, hand_result), (
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

from tests.l4_gates.stage0_test_helpers import (
    run_js_stage0 as _run_js_stage0,
    source_step as _source_step,
)


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
        assert _mu_deep_equal(py_final, js_final), (
            f"Final state mismatch:\npy={py_final}\njs={js_final}")
        # Verify the run actually did something (not a stall on first step)
        assert len(js_result["steps"]) > 0, "JS run produced zero steps"


# ---------------------------------------------------------------------------
# P7-c: Three-way parity harness — host Stage0 vs compiled Python vs compiled JS
#
# Evidence: compiler-produced bundles execute identically to the host Stage0
# path (_step_trusted) across both substrates for all 21 projection IDs.
#
# Scope assumptions:
# - Gate-3 normalize/denormalize does NOT trigger (no _type:"dict" literals
#   in match.v2/subst.v2 patterns — they use _type: {"var": ...}).
# - Test vectors use integers within JS safe-integer range.
# ---------------------------------------------------------------------------


def _run_source_to_completion(projections, input_value, max_steps=50):
    """Run host Stage0 path until stall, returning final state."""
    state = input_value
    for _ in range(max_steps):
        result = _source_step(projections, state)
        if result is state:  # identity check = stall (no projection matched)
            return state
        state = result
    return state


def _match_ctx():
    return {"caller": "p7c_parity"}


def _subst_ctx():
    return {"caller": "p7c_parity"}


# Load seed projections for source path comparison
def _load_seed_projections(seed_path):
    """Load projections list from a seed JSON file."""
    with open(seed_path) as f:
        seed = json.load(f)
    return seed["projections"]


# ---------------------------------------------------------------------------
# Single-step parity vectors: one per projection ID
# ---------------------------------------------------------------------------

# match.v2 single-step vectors (8 projections)
MATCH_PARITY_VECTORS = [
    # match.wrap — entry point
    ("match.wrap", {
        "match": {"pattern": "hello", "value": "hello"},
        "_match_ctx": _match_ctx(),
    }),
    # match.equal — pattern_focus == value_focus
    ("match.equal", {
        "mode": "match", "pattern_focus": "hello", "value_focus": "hello",
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
    # match.var — variable bind
    ("match.var", {
        "mode": "match", "pattern_focus": {"var": "x"},
        "value_focus": "forty_two", "bindings": None,
        "stack": None, "_match_ctx": _match_ctx(),
    }),
    # match.done — terminal (focus null, stack null)
    ("match.done", {
        "mode": "match", "pattern_focus": None, "value_focus": None,
        "bindings": {"name": "x", "value": "forty_two", "rest": None},
        "stack": None, "_match_ctx": _match_ctx(),
    }),
    # match.sibling — stack pop
    ("match.sibling", {
        "mode": "match", "pattern_focus": None, "value_focus": None,
        "bindings": None,
        "stack": {
            "head": {"type": "pair", "pattern_rest": "a", "value_rest": "b"},
            "tail": None,
        },
        "_match_ctx": _match_ctx(),
    }),
    # match.typed.descend — type-tagged structure
    ("match.typed.descend", {
        "mode": "match",
        "pattern_focus": {"_type": "list", "head": {"var": "h"}, "tail": {"var": "t"}},
        "value_focus": {"_type": "list", "head": "one", "tail": None},
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
    # match.dict.descend — head/tail structure (no _type)
    ("match.dict.descend", {
        "mode": "match",
        "pattern_focus": {"head": {"var": "h"}, "tail": {"var": "t"}},
        "value_focus": {"head": "a", "tail": "b"},
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
    # match.fail — catch-all (pattern != value, no special structure)
    ("match.fail", {
        "mode": "match", "pattern_focus": "a", "value_focus": "b",
        "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
    }),
]

# subst.v2 single-step vectors (13 projections)
SUBST_PARITY_VECTORS = [
    # subst.wrap — entry point
    ("subst.wrap", {
        "subst": {"body": {"var": "x"}, "bindings": {"name": "x", "value": "forty_two", "rest": None}},
        "_subst_ctx": _subst_ctx(),
    }),
    # subst.primitive — traverse literal
    ("subst.primitive", {
        "mode": "subst", "phase": "traverse", "focus": "literal",
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.var — traverse variable site
    ("subst.var", {
        "mode": "subst", "phase": "traverse",
        "focus": {"var": "x"},
        "bindings": {"name": "x", "value": "forty_two", "rest": None},
        "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.lookup.found — name matches
    ("subst.lookup.found", {
        "mode": "subst", "phase": "lookup",
        "lookup_name": "x",
        "lookup_bindings": {"name": "x", "value": "forty_two", "rest": None},
        "bindings": {"name": "x", "value": "forty_two", "rest": None},
        "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.lookup.next — name doesn't match, continue
    ("subst.lookup.next", {
        "mode": "subst", "phase": "lookup",
        "lookup_name": "x",
        "lookup_bindings": {"name": "y", "value": "ninety_nine", "rest": None},
        "bindings": {"name": "y", "value": "ninety_nine", "rest": None},
        "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.lookup.exhausted — bindings null
    ("subst.lookup.exhausted", {
        "mode": "subst", "phase": "lookup",
        "lookup_name": "z", "lookup_bindings": None,
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.done — terminal (phase=result, context=null)
    ("subst.done", {
        "mode": "subst", "phase": "result", "focus": "forty_two",
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.descend — traverse head/tail
    ("subst.descend", {
        "mode": "subst", "phase": "traverse",
        "focus": {"head": "one", "tail": "two"},
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.ascend — both head and tail done, reconstruct
    ("subst.ascend", {
        "mode": "subst", "phase": "result", "focus": "tail_val",
        "bindings": None,
        "context": {
            "head": {"type": "tail_done", "head_result": "head_val"},
            "tail": None,
        },
        "_subst_ctx": _subst_ctx(),
    }),
    # subst.sibling — head done, move to tail
    ("subst.sibling", {
        "mode": "subst", "phase": "result", "focus": "head_val",
        "bindings": None,
        "context": {
            "head": {"type": "head_done", "tail": "tail_body"},
            "tail": None,
        },
        "_subst_ctx": _subst_ctx(),
    }),
    # subst.typed.descend — type-tagged traverse
    ("subst.typed.descend", {
        "mode": "subst", "phase": "traverse",
        "focus": {"_type": "pair", "head": "one", "tail": "two"},
        "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
    }),
    # subst.typed.sibling — type-tagged head done, move to tail
    ("subst.typed.sibling", {
        "mode": "subst", "phase": "result", "focus": "hd_result",
        "bindings": None,
        "context": {
            "head": {"type": "typed_head_done", "_type": "pair", "tail": "tl"},
            "tail": None,
        },
        "_subst_ctx": _subst_ctx(),
    }),
    # subst.typed.ascend — type-tagged reconstruct
    ("subst.typed.ascend", {
        "mode": "subst", "phase": "result", "focus": "tl_result",
        "bindings": None,
        "context": {
            "head": {"type": "typed_tail_done", "_type": "pair", "head_result": "hd_result"},
            "tail": None,
        },
        "_subst_ctx": _subst_ctx(),
    }),
]

# Negative control vectors (should stall on both paths)
MATCH_NEGATIVE_VECTORS = [
    # Extra key — exact-key matching rejects
    ("extra_key", {
        "match": {"pattern": "a", "value": "a"},
        "_match_ctx": _match_ctx(),
        "extra": 1,
    }),
    # Missing key — no _match_ctx
    ("missing_key", {
        "match": {"pattern": "a", "value": "a"},
    }),
    # Wrong type — not a dict
    ("wrong_type_str", "not_a_dict"),
    ("wrong_type_int", 42),
]

SUBST_NEGATIVE_VECTORS = [
    # Extra key
    ("extra_key", {
        "subst": {"body": 1, "bindings": None},
        "_subst_ctx": _subst_ctx(),
        "extra": 1,
    }),
    # Wrong type
    ("wrong_type_int", 42),
]


class TestCompilerBundleParityVsHostStage0:
    """P7-c.1: Compiler-produced bundles execute identically to host Stage0 path.

    Three-way comparison is split: this class covers host-stage0 vs compiled-py.
    TestCompilerBundleCrossSubstrate covers compiled-py vs compiled-js.
    """

    # --- Helpers ---

    def _check_match_parity(self, bundle, projections, inp, expected_proj_id):
        """Assert host Stage0 and compiled Python agree on a match input."""
        source_result = _source_step(projections, inp)
        compiled_result = stage0_vm_step(bundle, inp)

        assert compiled_result["status"] == "match", (
            f"Expected compiled path to match projection '{expected_proj_id}', "
            f"but got stall. Input: {inp!r}")
        assert compiled_result["matched_program_id"] == expected_proj_id, (
            f"Expected program '{expected_proj_id}', "
            f"got '{compiled_result['matched_program_id']}'")
        assert _mu_deep_equal(source_result, compiled_result["root"]), (
            f"Host Stage0 and compiled Python disagree on '{expected_proj_id}'.\n"
            f"host_stage0={source_result!r}\n"
            f"compiled_py={compiled_result['root']!r}")

    def _check_stall_parity(self, bundle, projections, inp):
        """Assert both paths agree: no projection matches (stall)."""
        source_result = _source_step(projections, inp)
        compiled_result = stage0_vm_step(bundle, inp)

        # Source path stall: returns input_value unchanged (identity)
        assert source_result is inp, (
            f"Expected host Stage0 stall (identity return), "
            f"but got different object: {source_result!r}")
        assert compiled_result["status"] == "stall", (
            f"Expected compiled path stall, got: {compiled_result['status']}")

    # --- match.v2 single-step parity ---

    @pytest.mark.parametrize("proj_id,inp", MATCH_PARITY_VECTORS,
                             ids=[v[0] for v in MATCH_PARITY_VECTORS])
    def test_match_single_step_parity(self, proj_id, inp):
        """Host Stage0 and compiled Python agree on single-step match output."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        projections = _load_seed_projections(MATCH_SEED)
        self._check_match_parity(bundle, projections, inp, proj_id)

    # --- subst.v2 single-step parity ---

    @pytest.mark.parametrize("proj_id,inp", SUBST_PARITY_VECTORS,
                             ids=[v[0] for v in SUBST_PARITY_VECTORS])
    def test_subst_single_step_parity(self, proj_id, inp):
        """Host Stage0 and compiled Python agree on single-step subst output."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        projections = _load_seed_projections(SUBST_SEED)
        self._check_subst_parity(bundle, projections, inp, proj_id)

    def _check_subst_parity(self, bundle, projections, inp, expected_proj_id):
        """Assert host Stage0 and compiled Python agree on a subst input."""
        source_result = _source_step(projections, inp)
        compiled_result = stage0_vm_step(bundle, inp)

        assert compiled_result["status"] == "match", (
            f"Expected compiled path to match projection '{expected_proj_id}', "
            f"but got stall. Input: {inp!r}")
        assert compiled_result["matched_program_id"] == expected_proj_id, (
            f"Expected program '{expected_proj_id}', "
            f"got '{compiled_result['matched_program_id']}'")
        assert _mu_deep_equal(source_result, compiled_result["root"]), (
            f"Host Stage0 and compiled Python disagree on '{expected_proj_id}'.\n"
            f"host_stage0={source_result!r}\n"
            f"compiled_py={compiled_result['root']!r}")

    # --- Negative controls (stall parity) ---

    @pytest.mark.parametrize("name,inp", MATCH_NEGATIVE_VECTORS,
                             ids=[v[0] for v in MATCH_NEGATIVE_VECTORS])
    def test_match_negative_stall_parity(self, name, inp):
        """Both paths agree: input matches no match.v2 projection (stall)."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        projections = _load_seed_projections(MATCH_SEED)
        self._check_stall_parity(bundle, projections, inp)

    @pytest.mark.parametrize("name,inp", SUBST_NEGATIVE_VECTORS,
                             ids=[v[0] for v in SUBST_NEGATIVE_VECTORS])
    def test_subst_negative_stall_parity(self, name, inp):
        """Both paths agree: input matches no subst.v2 projection (stall)."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        projections = _load_seed_projections(SUBST_SEED)
        self._check_stall_parity(bundle, projections, inp)

    # --- Multi-step run-to-completion parity ---

    def test_match_run_to_completion_success(self):
        """Full match pipeline: host Stage0 and compiled Python reach same terminal state."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        projections = _load_seed_projections(MATCH_SEED)
        inp = {
            "match": {"pattern": "hello", "value": "hello"},
            "_match_ctx": _match_ctx(),
        }
        source_final = _run_source_to_completion(projections, inp)
        compiled_final = _run_vm_to_completion(bundle, inp)
        assert _mu_deep_equal(source_final, compiled_final), (
            f"Multi-step match divergence:\n"
            f"host_stage0={source_final!r}\ncompiled_py={compiled_final!r}")
        # Verify terminal state shape
        assert source_final.get("_mode") == "match_done"
        assert source_final.get("_status") == "success"

    def test_match_run_to_completion_failure(self):
        """Full match pipeline: mismatch → both reach no_match terminal."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        projections = _load_seed_projections(MATCH_SEED)
        inp = {
            "match": {"pattern": "hello", "value": "world"},
            "_match_ctx": _match_ctx(),
        }
        source_final = _run_source_to_completion(projections, inp)
        compiled_final = _run_vm_to_completion(bundle, inp)
        assert _mu_deep_equal(source_final, compiled_final), (
            f"Multi-step match-fail divergence:\n"
            f"host_stage0={source_final!r}\ncompiled_py={compiled_final!r}")
        assert source_final.get("_mode") == "match_done"
        assert source_final.get("_status") == "no_match"

    def test_subst_run_to_completion(self):
        """Full subst pipeline: host Stage0 and compiled Python reach same terminal."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        projections = _load_seed_projections(SUBST_SEED)
        inp = {
            "subst": {
                "body": {"var": "x"},
                "bindings": {"name": "x", "value": "forty_two", "rest": None},
            },
            "_subst_ctx": _subst_ctx(),
        }
        source_final = _run_source_to_completion(projections, inp)
        compiled_final = _run_vm_to_completion(bundle, inp)
        assert _mu_deep_equal(source_final, compiled_final), (
            f"Multi-step subst divergence:\n"
            f"host_stage0={source_final!r}\ncompiled_py={compiled_final!r}")
        assert source_final.get("_mode") == "subst_done"
        assert source_final.get("_result") == "forty_two"

    def test_subst_run_to_completion_structured(self):
        """Full subst with head/tail body: exercises descend/sibling/ascend chain."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        projections = _load_seed_projections(SUBST_SEED)
        inp = {
            "subst": {
                "body": {"head": {"var": "a"}, "tail": {"var": "b"}},
                "bindings": {
                    "name": "a", "value": "one",
                    "rest": {"name": "b", "value": "two", "rest": None},
                },
            },
            "_subst_ctx": _subst_ctx(),
        }
        source_final = _run_source_to_completion(projections, inp)
        compiled_final = _run_vm_to_completion(bundle, inp)
        assert _mu_deep_equal(source_final, compiled_final), (
            f"Multi-step subst-structured divergence:\n"
            f"host_stage0={source_final!r}\ncompiled_py={compiled_final!r}")
        assert source_final.get("_mode") == "subst_done"
        assert _mu_deep_equal(source_final.get("_result"), {"head": "one", "tail": "two"})


class TestCompilerBundleCrossSubstrate:
    """P7-c.2: Compiled Python and compiled JS agree on same corpus.

    Uses the same vectors as TestCompilerBundleParityVsHostStage0,
    exercised through both Python stage0_vm_step and JS stage0VmStep.
    """

    # --- Helpers ---

    def _check_cross_substrate_step(self, bundle, bundle_rel, inp, expected_proj_id):
        """Assert compiled Python and JS agree on a single-step result."""
        py_result = stage0_vm_step(bundle, inp)
        js_result = _run_js_stage0("step", bundle_rel, inp)

        assert py_result["status"] == "match", (
            f"Expected compiled Python to match projection '{expected_proj_id}', "
            f"but got stall. Input: {inp!r}")
        assert js_result["status"] == "match", (
            f"Expected compiled JS to match projection '{expected_proj_id}', "
            f"but got stall. Input: {inp!r}")
        if py_result["status"] == "match":
            assert py_result["matched_program_id"] == js_result["matched_program_id"], (
                f"Program ID mismatch: py={py_result['matched_program_id']}, "
                f"js={js_result['matched_program_id']}")
            assert _mu_deep_equal(py_result["root"], js_result["root"]), (
                f"Output mismatch for '{expected_proj_id}':\n"
                f"compiled_py={py_result['root']!r}\n"
                f"compiled_js={js_result['root']!r}")

    def _check_cross_substrate_stall(self, bundle, bundle_rel, inp):
        """Assert both substrates agree on stall."""
        py_result = stage0_vm_step(bundle, inp)
        js_result = _run_js_stage0("step", bundle_rel, inp)
        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"

    # --- match.v2 cross-substrate ---

    @pytest.mark.parametrize("proj_id,inp", MATCH_PARITY_VECTORS,
                             ids=[v[0] for v in MATCH_PARITY_VECTORS])
    def test_match_cross_substrate_step(self, proj_id, inp):
        """Compiled Python and JS agree on single-step match output."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        self._check_cross_substrate_step(bundle, MATCH_COMPILED_REL, inp, proj_id)

    # --- subst.v2 cross-substrate ---

    @pytest.mark.parametrize("proj_id,inp", SUBST_PARITY_VECTORS,
                             ids=[v[0] for v in SUBST_PARITY_VECTORS])
    def test_subst_cross_substrate_step(self, proj_id, inp):
        """Compiled Python and JS agree on single-step subst output."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        self._check_cross_substrate_step(bundle, SUBST_COMPILED_REL, inp, proj_id)

    # --- Negative controls cross-substrate ---

    @pytest.mark.parametrize("name,inp", MATCH_NEGATIVE_VECTORS,
                             ids=[v[0] for v in MATCH_NEGATIVE_VECTORS])
    def test_match_negative_cross_substrate(self, name, inp):
        """Both substrates agree: input matches no match.v2 projection."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        self._check_cross_substrate_stall(bundle, MATCH_COMPILED_REL, inp)

    @pytest.mark.parametrize("name,inp", SUBST_NEGATIVE_VECTORS,
                             ids=[v[0] for v in SUBST_NEGATIVE_VECTORS])
    def test_subst_negative_cross_substrate(self, name, inp):
        """Both substrates agree: input matches no subst.v2 projection."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        self._check_cross_substrate_stall(bundle, SUBST_COMPILED_REL, inp)

    # --- Multi-step cross-substrate ---

    def test_match_run_cross_substrate(self):
        """Full match pipeline: compiled Python and JS reach same terminal."""
        bundle = _load_bundle(MATCH_COMPILED_PATH)
        inp = {
            "match": {"pattern": "hello", "value": "hello"},
            "_match_ctx": _match_ctx(),
        }
        py_final = _run_vm_to_completion(bundle, inp)
        js_result = _run_js_stage0("run", MATCH_COMPILED_REL, inp)
        assert _mu_deep_equal(py_final, js_result["root"]), (
            f"Cross-substrate match divergence:\n"
            f"compiled_py={py_final!r}\ncompiled_js={js_result['root']!r}")
        assert len(js_result["steps"]) > 0

    def test_subst_run_cross_substrate(self):
        """Full subst pipeline: compiled Python and JS reach same terminal."""
        bundle = _load_bundle(SUBST_COMPILED_PATH)
        inp = {
            "subst": {
                "body": {"var": "x"},
                "bindings": {"name": "x", "value": 42, "rest": None},
            },
            "_subst_ctx": _subst_ctx(),
        }
        py_final = _run_vm_to_completion(bundle, inp)
        js_result = _run_js_stage0("run", SUBST_COMPILED_REL, inp)
        assert _mu_deep_equal(py_final, js_result["root"]), (
            f"Cross-substrate subst divergence:\n"
            f"compiled_py={py_final!r}\ncompiled_js={js_result['root']!r}")
        assert len(js_result["steps"]) > 0
