"""P7-a Gate Tests: Stage0 VM Prototype + Parity Evidence.

Tests the Stage0 VM against hand-authored bundles (match_v2, subst_v2)
and verifies parity with the source path (_step_trusted with v2 seeds).

Evidence gate (from .scratch/p7a_design_plan.md):
  1. Bundles execute on Python VM with correct results on all vectors
  2. VM results match _step_trusted() on same inputs for >= 20 vectors
  3. Transaction model: failed programs don't mutate focus
  4. Malformed bundles rejected (fail-closed)
  5. Bundle audit trail: every op traces to source seed via source_map
"""

import json
import os
import subprocess
import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.stage0_vm import (
    Stage0VMError,
    _classify_kind,  # ANTICHEAT_OK: unit testing VM kind classification
    _materialize_template,  # ANTICHEAT_OK: unit testing VM template engine
    _mu_deep_equal,  # ANTICHEAT_OK: parity comparator for type-strict equality
    _resolve_path,  # ANTICHEAT_OK: unit testing VM path resolution
    stage0_vm_run,
    stage0_vm_step,
    validate_bundle,
)

# ---------------------------------------------------------------------------
# Fixtures: load bundles and v2 seed projections
# ---------------------------------------------------------------------------

REPO_ROOT = str(REPO_ROOT)


def _load_json(rel_path):
    with open(os.path.join(REPO_ROOT, rel_path)) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def match_bundle():
    return _load_json("mu/stage0/examples/match_v2_bundle.v1.json")


@pytest.fixture(scope="module")
def subst_bundle():
    return _load_json("mu/stage0/examples/subst_v2_bundle.v1.json")


@pytest.fixture(scope="module")
def match_v2_projections():
    seed = _load_json("mu/substrate/match.v2.json")
    return seed["projections"]


@pytest.fixture(scope="module")
def subst_v2_projections():
    seed = _load_json("mu/substrate/subst.v2.json")
    return seed["projections"]


def _match_ctx():
    return {"projection_id": "test"}


def _subst_ctx():
    return {"projection_id": "test"}


# ---------------------------------------------------------------------------
# Source-path parity helper
# ---------------------------------------------------------------------------

def _source_step(projections, input_value):
    """Run the source path (_step_trusted) on input_value."""
    from rcx_pi.selfhost.eval_seed import _step_trusted  # ANTICHEAT_OK: parity evidence against source path
    return _step_trusted(projections, input_value)


# =========================================================================
# 1. Helper unit tests
# =========================================================================


class TestResolvePathHelper:
    def test_root_only(self):
        val, ok = _resolve_path(42, ["focus", "root"])
        assert ok and val == 42

    def test_nested_key(self):
        root = {"a": {"b": 99}}
        val, ok = _resolve_path(root, ["focus", "root", "a", "b"])
        assert ok and val == 99

    def test_missing_key(self):
        val, ok = _resolve_path({"a": 1}, ["focus", "root", "b"])
        assert not ok

    def test_non_dict_intermediate(self):
        val, ok = _resolve_path({"a": 42}, ["focus", "root", "a", "b"])
        assert not ok

    def test_null_value(self):
        val, ok = _resolve_path({"x": None}, ["focus", "root", "x"])
        assert ok and val is None

    def test_invalid_prefix(self):
        with pytest.raises(Stage0VMError):
            _resolve_path({}, ["bad", "path"])


class TestClassifyKind:
    @pytest.mark.parametrize("value,expected", [
        (None, "null"), (True, "bool"), (False, "bool"),
        (0, "int"), (42, "int"), (-1, "int"),
        (3.14, "float"), (0.0, "float"),
        ("", "string"), ("hello", "string"),
        ({}, "dict"), ({"a": 1}, "dict"),
        ([], "list"), ([1, 2], "list"),
    ])
    def test_kinds(self, value, expected):
        assert _classify_kind(value) == expected

    def test_unknown(self):
        assert _classify_kind(object()) is None


class TestMuDeepEqual:
    def test_none_equal(self):
        assert _mu_deep_equal(None, None)

    def test_none_vs_int(self):
        assert not _mu_deep_equal(None, 0)

    def test_bool_vs_int(self):
        # True == 1 in Python, but they are different Mu types
        assert not _mu_deep_equal(True, 1)

    def test_int_equal(self):
        assert _mu_deep_equal(42, 42)

    def test_float_equal(self):
        assert _mu_deep_equal(3.14, 3.14)

    def test_string_equal(self):
        assert _mu_deep_equal("hello", "hello")

    def test_dict_equal(self):
        assert _mu_deep_equal({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_dict_key_mismatch(self):
        assert not _mu_deep_equal({"a": 1}, {"b": 1})

    def test_dict_nested(self):
        a = {"x": {"y": [1, 2]}}
        b = {"x": {"y": [1, 2]}}
        assert _mu_deep_equal(a, b)

    def test_list_equal(self):
        assert _mu_deep_equal([1, "a", None], [1, "a", None])

    def test_list_length_mismatch(self):
        assert not _mu_deep_equal([1, 2], [1, 2, 3])

    def test_type_mismatch(self):
        assert not _mu_deep_equal(42, "42")


class TestMaterializeTemplate:
    def test_literal(self):
        t = {"kind": "literal", "value": 42}
        assert _materialize_template(t, {}) == 42

    def test_capture_ref(self):
        t = {"kind": "capture_ref", "name": "x"}
        assert _materialize_template(t, {"x": 99}) == 99

    def test_capture_ref_missing(self):
        t = {"kind": "capture_ref", "name": "missing"}
        with pytest.raises(Stage0VMError):
            _materialize_template(t, {})

    def test_object(self):
        t = {"kind": "object", "fields": {
            "a": {"kind": "literal", "value": 1},
            "b": {"kind": "capture_ref", "name": "x"},
        }}
        assert _materialize_template(t, {"x": 2}) == {"a": 1, "b": 2}

    def test_list(self):
        t = {"kind": "list", "items": [
            {"kind": "literal", "value": 1},
            {"kind": "capture_ref", "name": "y"},
        ]}
        assert _materialize_template(t, {"y": 2}) == [1, 2]

    def test_nested_object(self):
        t = {"kind": "object", "fields": {
            "outer": {"kind": "object", "fields": {
                "inner": {"kind": "literal", "value": "deep"},
            }},
        }}
        assert _materialize_template(t, {}) == {"outer": {"inner": "deep"}}

    def test_unknown_kind(self):
        with pytest.raises(Stage0VMError):
            _materialize_template({"kind": "bad"}, {})


# =========================================================================
# 2. Bundle validation (fail-closed)
# =========================================================================


class TestBundleValidation:
    def test_valid_match_bundle(self, match_bundle):
        validate_bundle(match_bundle)  # should not raise

    def test_valid_subst_bundle(self, subst_bundle):
        validate_bundle(subst_bundle)  # should not raise

    def test_missing_required_field(self):
        bundle = {"stage0_ir_version": 1, "bundle_id": "x"}
        with pytest.raises(ValueError, match="Missing required"):
            validate_bundle(bundle)

    def test_bad_ir_version(self):
        bundle = {
            "stage0_ir_version": 99, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1", "program_order": [],
            "programs": [],
        }
        with pytest.raises(ValueError, match="Unsupported IR"):
            validate_bundle(bundle)

    def test_unknown_opcode(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [{"op": "explode"}]}],
        }
        with pytest.raises(ValueError, match="Unknown opcode"):
            validate_bundle(bundle)

    def test_duplicate_program_id(self):
        prog = {"id": "p1", "ops": [{"op": "return_projection_fail"}]}
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1", "p1"],
            "programs": [prog, prog],
        }
        with pytest.raises(ValueError, match="Duplicate program ID"):
            validate_bundle(bundle)

    def test_empty_ops(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": []}],
        }
        with pytest.raises(ValueError, match="empty"):
            validate_bundle(bundle)

    def test_program_order_mismatch(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p2", "p1"],
            "programs": [
                {"id": "p1", "ops": [{"op": "return_projection_fail"}]},
                {"id": "p2", "ops": [{"op": "return_projection_fail"}]},
            ],
        }
        with pytest.raises(ValueError, match="program_order mismatch"):
            validate_bundle(bundle)


# =========================================================================
# 3. Match bundle — individual program vectors
# =========================================================================


class TestMatchVMStep:
    """Test each match program fires on its designed input."""

    def test_match_wrap(self, match_bundle):
        """match.wrap: entry point wraps raw request into state."""
        inp = {"match": {"pattern": 42, "value": 42}, "_match_ctx": _match_ctx()}
        r = stage0_vm_step(match_bundle, inp)
        assert r["status"] == "match"
        assert r["matched_program_id"] == "match.wrap"
        root = r["root"]
        assert root["mode"] == "match"
        assert root["pattern_focus"] == 42
        assert root["value_focus"] == 42
        assert root["bindings"] is None
        assert root["stack"] is None
        assert root["_match_ctx"] == _match_ctx()

    def test_match_equal_same(self, match_bundle):
        """match.equal: non-linear check passes (same value)."""
        inp = {
            "mode": "match", "pattern_focus": 42, "value_focus": 42,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.equal"
        root = r["root"]
        assert root["mode"] == "match"
        assert root["pattern_focus"] is None
        assert root["value_focus"] is None

    def test_match_equal_mismatch_falls_to_fail(self, match_bundle):
        """match.equal fails, match.fail catches."""
        inp = {
            "mode": "match", "pattern_focus": 42, "value_focus": 99,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.fail"
        root = r["root"]
        assert root["_mode"] == "match_done"
        assert root["_status"] == "no_match"

    def test_match_var(self, match_bundle):
        """match.var: variable site binds any value."""
        inp = {
            "mode": "match", "pattern_focus": {"var": "x"},
            "value_focus": 42, "bindings": None, "stack": None,
            "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.var"
        root = r["root"]
        assert root["mode"] == "match"
        assert root["pattern_focus"] is None
        assert root["value_focus"] is None
        assert root["bindings"]["name"] == "x"
        assert root["bindings"]["value"] == 42
        assert root["bindings"]["rest"] is None

    def test_match_typed_descend(self, match_bundle):
        """match.typed.descend: type-tagged head/tail descent.

        Uses different pattern/value heads so match.equal (index 2)
        fails first — typed.descend (index 4) must win.
        """
        inp = {
            "mode": "match",
            "pattern_focus": {"_type": "list", "head": {"var": "h"}, "tail": {"var": "t"}},
            "value_focus": {"_type": "list", "head": 1, "tail": None},
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.typed.descend"
        root = r["root"]
        assert root["pattern_focus"] == {"var": "h"}
        assert root["value_focus"] == 1
        assert root["stack"]["head"]["type"] == "pair"

    def test_match_typed_descend_type_mismatch(self, match_bundle):
        """Type mismatch: typed.descend fails, falls to fail."""
        inp = {
            "mode": "match",
            "pattern_focus": {"_type": "list", "head": 1, "tail": None},
            "value_focus": {"_type": "dict", "head": 1, "tail": None},
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.fail"

    def test_match_dict_descend(self, match_bundle):
        """match.dict.descend: plain head/tail descent.

        Uses different pattern/value heads so match.equal (index 2)
        fails first — dict.descend (index 5) must win.
        """
        inp = {
            "mode": "match",
            "pattern_focus": {"head": {"var": "h"}, "tail": {"var": "t"}},
            "value_focus": {"head": "a", "tail": "b"},
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.dict.descend"
        root = r["root"]
        assert root["pattern_focus"] == {"var": "h"}
        assert root["value_focus"] == "a"

    def test_match_sibling(self, match_bundle):
        """match.sibling: null focuses + stack → advance to tail."""
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": None,
            "stack": {
                "head": {"type": "pair", "pattern_rest": "pt", "value_rest": "vt"},
                "tail": None,
            },
            "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.sibling"
        root = r["root"]
        assert root["pattern_focus"] == "pt"
        assert root["value_focus"] == "vt"
        assert root["stack"] is None

    def test_match_done(self, match_bundle):
        """match.done: null focuses, null stack → success."""
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": {"name": "x", "value": 42, "rest": None},
            "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.done"
        root = r["root"]
        assert root["_mode"] == "match_done"
        assert root["_status"] == "success"
        assert root["_bindings"]["name"] == "x"

    def test_match_fail_catchall(self, match_bundle):
        """match.fail: any match state that nothing else catches."""
        # Non-null pattern_focus that isn't a var, typed, or dict pattern
        inp = {
            "mode": "match", "pattern_focus": "literal_string",
            "value_focus": "different_string", "bindings": None,
            "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.fail"
        assert r["root"]["_status"] == "no_match"


# =========================================================================
# 4. Subst bundle — individual program vectors
# =========================================================================


class TestSubstVMStep:
    """Test each subst program fires on its designed input."""

    def test_subst_wrap(self, subst_bundle):
        """subst.wrap: entry point wraps raw request into state."""
        inp = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.wrap"
        root = r["root"]
        assert root["mode"] == "subst"
        assert root["phase"] == "traverse"
        assert root["focus"] == 42

    def test_subst_var(self, subst_bundle):
        """subst.var: variable site creates lookup marker."""
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"var": "x"}, "bindings": bindings,
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.var"
        root = r["root"]
        assert root["phase"] == "lookup"
        assert root["lookup_name"] == "x"

    def test_subst_lookup_found(self, subst_bundle):
        """subst.lookup.found: name matches (non-linear check)."""
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "x",
            "lookup_bindings": {"name": "x", "value": 42, "rest": None},
            "bindings": {"name": "x", "value": 42, "rest": None},
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.lookup.found"
        root = r["root"]
        assert root["phase"] == "result"
        assert root["focus"] == 42

    def test_subst_lookup_next(self, subst_bundle):
        """subst.lookup.next: name doesn't match, advance."""
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "x",
            "lookup_bindings": {"name": "y", "value": 99, "rest": None},
            "bindings": {"name": "y", "value": 99, "rest": None},
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.lookup.next"
        root = r["root"]
        assert root["phase"] == "lookup"
        assert root["lookup_bindings"] is None

    def test_subst_lookup_exhausted(self, subst_bundle):
        """subst.lookup.exhausted: bindings exhausted (null)."""
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "z", "lookup_bindings": None,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.lookup.exhausted"
        root = r["root"]
        assert root["phase"] == "result"
        assert root["focus"]["_error"] == "unbound_variable"
        assert root["focus"]["_name"] == "z"

    def test_subst_typed_descend(self, subst_bundle):
        """subst.typed.descend: type-tagged head/tail."""
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"_type": "list", "head": 1, "tail": None},
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.typed.descend"
        root = r["root"]
        assert root["phase"] == "traverse"
        assert root["focus"] == 1
        ctx_head = root["context"]["head"]
        assert ctx_head["type"] == "typed_head_done"
        assert ctx_head["_type"] == "list"

    def test_subst_typed_sibling(self, subst_bundle):
        """subst.typed.sibling: head done, move to tail."""
        inp = {
            "mode": "subst", "phase": "result", "focus": 1,
            "bindings": None,
            "context": {
                "head": {"type": "typed_head_done", "_type": "list", "tail": None},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.typed.sibling"
        root = r["root"]
        assert root["phase"] == "traverse"
        assert root["focus"] is None
        ctx_head = root["context"]["head"]
        assert ctx_head["type"] == "typed_tail_done"
        assert ctx_head["head_result"] == 1

    def test_subst_typed_ascend(self, subst_bundle):
        """subst.typed.ascend: both done, reconstruct with _type."""
        inp = {
            "mode": "subst", "phase": "result", "focus": None,
            "bindings": None,
            "context": {
                "head": {"type": "typed_tail_done", "_type": "list", "head_result": 1},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.typed.ascend"
        root = r["root"]
        assert root["phase"] == "result"
        assert root["focus"] == {"_type": "list", "head": 1, "tail": None}

    def test_subst_descend(self, subst_bundle):
        """subst.descend: plain head/tail descent."""
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"head": "a", "tail": "b"},
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.descend"
        root = r["root"]
        assert root["phase"] == "traverse"
        assert root["focus"] == "a"
        ctx_head = root["context"]["head"]
        assert ctx_head["type"] == "head_done"
        assert ctx_head["tail"] == "b"

    def test_subst_sibling(self, subst_bundle):
        """subst.sibling: head done → move to tail."""
        inp = {
            "mode": "subst", "phase": "result", "focus": "a_done",
            "bindings": None,
            "context": {
                "head": {"type": "head_done", "tail": "b"},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.sibling"
        root = r["root"]
        assert root["phase"] == "traverse"
        assert root["focus"] == "b"
        ctx_head = root["context"]["head"]
        assert ctx_head["type"] == "tail_done"
        assert ctx_head["head_result"] == "a_done"

    def test_subst_ascend(self, subst_bundle):
        """subst.ascend: both done → reconstruct parent."""
        inp = {
            "mode": "subst", "phase": "result", "focus": "b_done",
            "bindings": None,
            "context": {
                "head": {"type": "tail_done", "head_result": "a_done"},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.ascend"
        root = r["root"]
        assert root["phase"] == "result"
        assert root["focus"] == {"head": "a_done", "tail": "b_done"}

    def test_subst_primitive(self, subst_bundle):
        """subst.primitive: non-dict/non-var value → pass through."""
        inp = {
            "mode": "subst", "phase": "traverse", "focus": 42,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.primitive"
        root = r["root"]
        assert root["phase"] == "result"
        assert root["focus"] == 42

    def test_subst_done(self, subst_bundle):
        """subst.done: context null, result phase → final result."""
        inp = {
            "mode": "subst", "phase": "result", "focus": 42,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        r = stage0_vm_step(subst_bundle, inp)
        assert r["matched_program_id"] == "subst.done"
        root = r["root"]
        assert root["_mode"] == "subst_done"
        assert root["_result"] == 42


# =========================================================================
# 5. Transaction model tests
# =========================================================================


class TestTransactionModel:
    """Verify T1-T5 transaction semantics."""

    def test_failed_program_leaves_focus_unchanged(self, match_bundle):
        """Failed match programs must not alter the input value."""
        inp = {
            "mode": "match", "pattern_focus": 42, "value_focus": 99,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        # match.equal will fail (42 != 99), then match.fail catches.
        # The input dict must not be mutated.
        import copy
        inp_copy = copy.deepcopy(inp)
        stage0_vm_step(match_bundle, inp)
        assert inp == inp_copy

    def test_first_match_wins(self, match_bundle):
        """Earlier program wins over later when both could match."""
        # match.done (index 0) should win over match.sibling (index 1)
        # when stack is null (both check pattern_focus=null, value_focus=null)
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        r = stage0_vm_step(match_bundle, inp)
        assert r["matched_program_id"] == "match.done"

    def test_stall_on_no_match(self, match_bundle):
        """Unrecognized input stalls (no program matches)."""
        inp = {"completely": "unrelated", "structure": True}
        r = stage0_vm_step(match_bundle, inp)
        assert r["status"] == "stall"
        assert r["matched_program_id"] is None
        assert r["root"] is inp

    def test_stall_returns_input_unchanged(self, subst_bundle):
        """Stall returns original input object identity."""
        inp = {"not_a_subst_state": True}
        r = stage0_vm_step(subst_bundle, inp)
        assert r["status"] == "stall"
        assert r["root"] is inp


# =========================================================================
# 6. Multi-step sequences
# =========================================================================


class TestMultiStepSequences:
    """End-to-end sequences exercising multiple programs in sequence."""

    def test_match_literal_sequence(self, match_bundle):
        """match.wrap → match.equal → match.done (literal 42 == 42)."""
        inp = {"match": {"pattern": 42, "value": 42}, "_match_ctx": _match_ctx()}
        result = stage0_vm_run(match_bundle, inp)
        assert result["status"] == "complete"
        steps = result["steps"]
        assert len(steps) == 3
        assert steps[0]["program_id"] == "match.wrap"
        assert steps[1]["program_id"] == "match.equal"
        assert steps[2]["program_id"] == "match.done"
        final = result["root"]
        assert final["_mode"] == "match_done"
        assert final["_status"] == "success"

    def test_match_literal_mismatch_sequence(self, match_bundle):
        """match.wrap → match.fail (literal 42 != 99)."""
        inp = {"match": {"pattern": 42, "value": 99}, "_match_ctx": _match_ctx()}
        result = stage0_vm_run(match_bundle, inp)
        steps = result["steps"]
        assert len(steps) == 2
        assert steps[0]["program_id"] == "match.wrap"
        assert steps[1]["program_id"] == "match.fail"
        assert result["root"]["_status"] == "no_match"

    def test_match_var_sequence(self, match_bundle):
        """match.wrap → match.var → match.done (bind x=42)."""
        inp = {
            "match": {"pattern": {"var": "x"}, "value": 42},
            "_match_ctx": _match_ctx(),
        }
        result = stage0_vm_run(match_bundle, inp)
        steps = result["steps"]
        assert len(steps) == 3
        assert steps[0]["program_id"] == "match.wrap"
        assert steps[1]["program_id"] == "match.var"
        assert steps[2]["program_id"] == "match.done"
        final = result["root"]
        assert final["_status"] == "success"
        assert final["_bindings"]["name"] == "x"
        assert final["_bindings"]["value"] == 42

    def test_subst_primitive_sequence(self, subst_bundle):
        """subst.wrap → subst.primitive → subst.done (literal body)."""
        inp = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": _subst_ctx(),
        }
        result = stage0_vm_run(subst_bundle, inp)
        steps = result["steps"]
        assert len(steps) == 3
        assert steps[0]["program_id"] == "subst.wrap"
        assert steps[1]["program_id"] == "subst.primitive"
        assert steps[2]["program_id"] == "subst.done"
        assert result["root"]["_result"] == 42

    def test_subst_var_lookup_sequence(self, subst_bundle):
        """subst.wrap → subst.var → subst.lookup.found → subst.done."""
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "subst": {"body": {"var": "x"}, "bindings": bindings},
            "_subst_ctx": _subst_ctx(),
        }
        result = stage0_vm_run(subst_bundle, inp)
        steps = result["steps"]
        assert len(steps) == 4
        assert steps[0]["program_id"] == "subst.wrap"
        assert steps[1]["program_id"] == "subst.var"
        assert steps[2]["program_id"] == "subst.lookup.found"
        assert steps[3]["program_id"] == "subst.done"
        assert result["root"]["_result"] == 42

    def test_subst_dict_traversal_sequence(self, subst_bundle):
        """Traverse a plain {head: ..., tail: ...} structure."""
        bindings = None
        inp = {
            "subst": {"body": {"head": 1, "tail": 2}, "bindings": bindings},
            "_subst_ctx": _subst_ctx(),
        }
        result = stage0_vm_run(subst_bundle, inp)
        # wrap → descend → primitive(1) → sibling → primitive(2) → ascend → done
        program_ids = [s["program_id"] for s in result["steps"]]
        assert program_ids[0] == "subst.wrap"
        assert "subst.descend" in program_ids
        assert "subst.primitive" in program_ids
        assert "subst.sibling" in program_ids
        assert "subst.ascend" in program_ids
        assert program_ids[-1] == "subst.done"
        assert result["root"]["_result"] == {"head": 1, "tail": 2}

    def test_subst_typed_traversal_sequence(self, subst_bundle):
        """Traverse a typed {_type: ..., head: ..., tail: ...} structure."""
        inp = {
            "subst": {
                "body": {"_type": "list", "head": 10, "tail": 20},
                "bindings": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        result = stage0_vm_run(subst_bundle, inp)
        program_ids = [s["program_id"] for s in result["steps"]]
        assert program_ids[0] == "subst.wrap"
        assert "subst.typed.descend" in program_ids
        assert "subst.typed.sibling" in program_ids
        assert "subst.typed.ascend" in program_ids
        assert program_ids[-1] == "subst.done"
        assert result["root"]["_result"] == {"_type": "list", "head": 10, "tail": 20}


# =========================================================================
# 7. Parity tests: VM vs source path (_step_trusted with v2 seeds)
# =========================================================================


class TestParityVsSourcePath:
    """VM must produce identical results to _step_trusted on same inputs.

    This is the core evidence for P7-a: the VM is a faithful executor
    of the lowered bundle, producing the same results as the source path
    on real inputs.
    """

    # --- Match parity vectors ---

    def _check_match_parity(self, match_bundle, match_v2_projections, inp):
        """Compare VM step vs source-path step on a match input."""
        vm_result = stage0_vm_step(match_bundle, inp)
        source_result = _source_step(match_v2_projections, inp)
        if vm_result["status"] == "match":
            assert _mu_deep_equal(vm_result["root"], source_result), (
                f"VM program {vm_result['matched_program_id']} produced "
                f"{vm_result['root']!r}, source path produced {source_result!r}"
            )
        else:
            assert _mu_deep_equal(inp, source_result)  # both stall

    def test_parity_match_wrap(self, match_bundle, match_v2_projections):
        inp = {"match": {"pattern": 42, "value": 42}, "_match_ctx": _match_ctx()}
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_equal_same(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": "hello", "value_focus": "hello",
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_equal_mismatch(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": "hello", "value_focus": "world",
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_var(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": {"var": "x"},
            "value_focus": {"nested": True}, "bindings": None,
            "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_typed_descend(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match",
            "pattern_focus": {"_type": "list", "head": {"var": "h"}, "tail": {"var": "t"}},
            "value_focus": {"_type": "list", "head": 1, "tail": None},
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_dict_descend(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match",
            "pattern_focus": {"head": {"var": "h"}, "tail": {"var": "t"}},
            "value_focus": {"head": "a", "tail": "b"},
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_sibling(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": None,
            "stack": {
                "head": {"type": "pair", "pattern_rest": 10, "value_rest": 20},
                "tail": None,
            },
            "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_done(self, match_bundle, match_v2_projections):
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": bindings, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_done_empty_bindings(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": None, "value_focus": None,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    def test_parity_match_fail(self, match_bundle, match_v2_projections):
        inp = {
            "mode": "match", "pattern_focus": "a", "value_focus": "b",
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_match_parity(match_bundle, match_v2_projections, inp)

    # --- Subst parity vectors ---

    def _check_subst_parity(self, subst_bundle, subst_v2_projections, inp):
        """Compare VM step vs source-path step on a subst input."""
        vm_result = stage0_vm_step(subst_bundle, inp)
        source_result = _source_step(subst_v2_projections, inp)
        if vm_result["status"] == "match":
            assert _mu_deep_equal(vm_result["root"], source_result), (
                f"VM program {vm_result['matched_program_id']} produced "
                f"{vm_result['root']!r}, source path produced {source_result!r}"
            )
        else:
            assert _mu_deep_equal(inp, source_result)

    def test_parity_subst_wrap(self, subst_bundle, subst_v2_projections):
        inp = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_var(self, subst_bundle, subst_v2_projections):
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"var": "x"}, "bindings": bindings,
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_lookup_found(self, subst_bundle, subst_v2_projections):
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "x",
            "lookup_bindings": {"name": "x", "value": 42, "rest": None},
            "bindings": bindings, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_lookup_next(self, subst_bundle, subst_v2_projections):
        bindings = {"name": "y", "value": 99, "rest": None}
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "x",
            "lookup_bindings": {"name": "y", "value": 99, "rest": None},
            "bindings": bindings, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_lookup_exhausted(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "lookup",
            "lookup_name": "z", "lookup_bindings": None,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_primitive(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "traverse", "focus": 42,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_descend(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"head": 1, "tail": 2},
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_typed_descend(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"_type": "list", "head": 1, "tail": None},
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_done(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "result", "focus": 42,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_sibling(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "result", "focus": "hd",
            "bindings": None,
            "context": {
                "head": {"type": "head_done", "tail": "tl"},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)

    def test_parity_subst_ascend(self, subst_bundle, subst_v2_projections):
        inp = {
            "mode": "subst", "phase": "result", "focus": "tl",
            "bindings": None,
            "context": {
                "head": {"type": "tail_done", "head_result": "hd"},
                "tail": None,
            },
            "_subst_ctx": _subst_ctx(),
        }
        self._check_subst_parity(subst_bundle, subst_v2_projections, inp)


# =========================================================================
# 8. Source map audit trail
# =========================================================================


class TestSourceMapAudit:
    """Every op in every program must have a source_map tracing to seed."""

    def _check_source_maps(self, bundle, seed_name):
        for prog in bundle["programs"]:
            # Program-level source map
            assert "source_map" in prog, f"Program {prog['id']} missing source_map"
            sm = prog["source_map"]
            assert sm["seed_file"] == seed_name
            assert sm["projection_id"] == prog["id"]
            assert isinstance(sm["projection_index"], int)

            # Op-level source maps
            for i, op_spec in enumerate(prog["ops"]):
                assert "source_map" in op_spec, (
                    f"Op {i} ({op_spec['op']}) in {prog['id']} missing source_map"
                )

    def test_match_bundle_source_maps(self, match_bundle):
        self._check_source_maps(match_bundle, "match.v2.json")

    def test_subst_bundle_source_maps(self, subst_bundle):
        self._check_source_maps(subst_bundle, "subst.v2.json")


# =========================================================================
# 9. Metrics and resource bounds
# =========================================================================


class TestMetrics:
    def test_step_reports_metrics(self, match_bundle):
        inp = {"match": {"pattern": 1, "value": 1}, "_match_ctx": _match_ctx()}
        r = stage0_vm_step(match_bundle, inp)
        m = r["metrics"]
        assert m["program_attempts"] >= 1
        assert m["op_steps"] >= 1

    def test_run_reports_total_metrics(self, match_bundle):
        inp = {"match": {"pattern": 1, "value": 1}, "_match_ctx": _match_ctx()}
        r = stage0_vm_run(match_bundle, inp)
        m = r["metrics"]
        assert m["total_steps"] >= 3  # wrap + equal + done
        assert m["total_attempts"] >= 3
        assert m["total_ops"] >= 3

    def test_op_limit_enforced(self, match_bundle):
        inp = {"match": {"pattern": 1, "value": 1}, "_match_ctx": _match_ctx()}
        with pytest.raises(Stage0VMError, match="Op limit"):
            stage0_vm_step(match_bundle, inp, max_ops=1)

    def test_run_step_limit_enforced(self):
        """stage0_vm_run raises on step limit exceeded."""
        # A bundle that always matches and rewrites (infinite loop)
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "loop", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{
                "id": "p1",
                "ops": [
                    {"op": "write_path", "template": {
                        "kind": "literal", "value": {"loop": True}}},
                    {"op": "return_projection_success"},
                ],
            }],
        }
        with pytest.raises(Stage0VMError, match="Run step limit"):
            stage0_vm_run(bundle, {"start": True}, max_steps=5)


# =========================================================================
# 10. Machine error detection
# =========================================================================


class TestMachineErrors:
    def test_duplicate_capture_raises(self):
        """Duplicate capture_path name is a lowering bug."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{
                "id": "p1",
                "ops": [
                    {"op": "capture_path", "path": ["focus", "root"], "name": "a"},
                    {"op": "capture_path", "path": ["focus", "root"], "name": "a"},
                    {"op": "return_projection_success"},
                ],
            }],
        }
        with pytest.raises(Stage0VMError, match="duplicate capture"):
            stage0_vm_step(bundle, {"anything": True})

    def test_uncaptured_check_raises(self):
        """check_captured_equal on uncaptured variable is a lowering bug."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{
                "id": "p1",
                "ops": [
                    {"op": "check_captured_equal",
                     "path": ["focus", "root"], "capture_name": "missing"},
                    {"op": "return_projection_success"},
                ],
            }],
        }
        with pytest.raises(Stage0VMError, match="not yet captured"):
            stage0_vm_step(bundle, 42)

    def test_exhausted_ops_without_terminal(self):
        """Program that has no terminal opcode is malformed."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["p1"],
            "programs": [{
                "id": "p1",
                "ops": [
                    {"op": "capture_path", "path": ["focus", "root"], "name": "a"},
                ],
            }],
        }
        with pytest.raises(Stage0VMError, match="exhausted ops"):
            stage0_vm_step(bundle, {"anything": True})


# =========================================================================
# 11. Cross-substrate parity: Python VM vs JS VM
# =========================================================================


def _run_js_vm(action, bundle_path, input_value=None):
    """Call JS Stage0 VM via subprocess and return parsed result."""
    request = {"action": action, "bundle_path": bundle_path}
    if input_value is not None:
        request["input"] = input_value
    runner = os.path.join(REPO_ROOT, "tests", "l4_gates",
                          "stage0_vm_runner.js")
    result = subprocess.run(
        ["node", runner, json.dumps(request)],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"No JSON_API_RESPONSE from JS VM:\nstdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}")


MATCH_BUNDLE_PATH = "mu/stage0/examples/match_v2_bundle.v1.json"
SUBST_BUNDLE_PATH = "mu/stage0/examples/subst_v2_bundle.v1.json"


class TestCrossSubstrateParity:
    """Same bundle + same input must produce same result on Python and JS."""

    def _check_parity(self, bundle, bundle_path, inp):
        """Run Python VM and JS VM, compare results."""
        py_result = stage0_vm_step(bundle, inp)
        js_result = _run_js_vm("step", bundle_path, inp)
        assert py_result["status"] == js_result["status"], (
            f"Status mismatch: py={py_result['status']}, js={js_result['status']}")
        assert py_result["matched_program_id"] == js_result["matched_program_id"], (
            f"Program mismatch: py={py_result['matched_program_id']}, "
            f"js={js_result['matched_program_id']}")
        assert py_result["root"] == js_result["root"], (
            f"Root mismatch:\npy={json.dumps(py_result['root'], indent=2)}\n"
            f"js={json.dumps(js_result['root'], indent=2)}")

    def _check_run_parity(self, bundle, bundle_path, inp):
        """Run Python VM and JS VM multi-step, compare results."""
        py_result = stage0_vm_run(bundle, inp)
        js_result = _run_js_vm("run", bundle_path, inp)
        py_ids = [s["program_id"] for s in py_result["steps"]]
        js_ids = [s["program_id"] for s in js_result["steps"]]
        assert py_ids == js_ids, (
            f"Step sequence mismatch:\npy={py_ids}\njs={js_ids}")
        assert py_result["root"] == js_result["root"], (
            f"Final root mismatch:\npy={py_result['root']}\njs={js_result['root']}")

    # --- Match cross-substrate ---

    def test_xsub_match_wrap(self, match_bundle):
        inp = {"match": {"pattern": 42, "value": 42}, "_match_ctx": _match_ctx()}
        self._check_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_match_equal(self, match_bundle):
        inp = {
            "mode": "match", "pattern_focus": "x", "value_focus": "x",
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_match_var(self, match_bundle):
        inp = {
            "mode": "match", "pattern_focus": {"var": "a"},
            "value_focus": 99, "bindings": None,
            "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_match_fail(self, match_bundle):
        inp = {
            "mode": "match", "pattern_focus": 1, "value_focus": 2,
            "bindings": None, "stack": None, "_match_ctx": _match_ctx(),
        }
        self._check_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_match_stall(self, match_bundle):
        inp = {"unrelated": True}
        self._check_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    # --- Subst cross-substrate ---

    def test_xsub_subst_wrap(self, subst_bundle):
        inp = {"subst": {"body": 42, "bindings": None}, "_subst_ctx": _subst_ctx()}
        self._check_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)

    def test_xsub_subst_var(self, subst_bundle):
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"var": "x"}, "bindings": bindings,
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)

    def test_xsub_subst_lookup_found(self, subst_bundle):
        inp = {
            "mode": "subst", "phase": "lookup", "lookup_name": "x",
            "lookup_bindings": {"name": "x", "value": 42, "rest": None},
            "bindings": {"name": "x", "value": 42, "rest": None},
            "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)

    def test_xsub_subst_done(self, subst_bundle):
        inp = {
            "mode": "subst", "phase": "result", "focus": 42,
            "bindings": None, "context": None, "_subst_ctx": _subst_ctx(),
        }
        self._check_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)

    # --- Multi-step cross-substrate ---

    def test_xsub_match_literal_run(self, match_bundle):
        inp = {"match": {"pattern": 42, "value": 42}, "_match_ctx": _match_ctx()}
        self._check_run_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_match_mismatch_run(self, match_bundle):
        inp = {"match": {"pattern": 42, "value": 99}, "_match_ctx": _match_ctx()}
        self._check_run_parity(match_bundle, MATCH_BUNDLE_PATH, inp)

    def test_xsub_subst_var_run(self, subst_bundle):
        bindings = {"name": "x", "value": 42, "rest": None}
        inp = {
            "subst": {"body": {"var": "x"}, "bindings": bindings},
            "_subst_ctx": _subst_ctx(),
        }
        self._check_run_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)

    def test_xsub_subst_primitive_run(self, subst_bundle):
        inp = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": _subst_ctx(),
        }
        self._check_run_parity(subst_bundle, SUBST_BUNDLE_PATH, inp)
