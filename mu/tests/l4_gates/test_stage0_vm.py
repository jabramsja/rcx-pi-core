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
    MAX_PATH_DEPTH,
    MAX_TEMPLATE_DEPTH,
    OPCODE_SCHEMAS,
    SUPPORTED_KINDS,
    Stage0VMError,
    _classify_kind,  # ANTICHEAT_OK: unit testing VM kind classification
    _materialize_template,  # ANTICHEAT_OK: unit testing VM template engine
    _mu_deep_equal,  # ANTICHEAT_OK: parity comparator for type-strict equality
    _resolve_path,  # ANTICHEAT_OK: unit testing VM path resolution
    _safe_mu_deep_equal,  # ANTICHEAT_OK: unit testing safe wrapper
    _safe_mu_copy,  # ANTICHEAT_OK: unit testing safe wrapper
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
    """Run the source path (_step_trusted) on input_value.

    Delegates to shared helper (tests/l4_gates/stage0_test_helpers.py).
    """
    from tests.l4_gates.stage0_test_helpers import source_step
    return source_step(projections, input_value)


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

    def test_dict_subclass_rejected(self):
        """Dict subclasses must not classify as 'dict' — they can override
        __contains__, __getitem__, __iter__ and inject behavior."""
        class D(dict):
            pass
        assert _classify_kind(D({"x": 1})) is None

    def test_list_subclass_rejected(self):
        """List subclasses must not classify as 'list' — they can override
        __iter__, __getitem__ and inject behavior."""
        class L(list):
            pass
        assert _classify_kind(L([1, 2])) is None

    def test_str_subclass_rejected(self):
        """Str subclasses must not classify as 'string' — they can override
        __eq__ and inject behavior during equality checks."""
        class S(str):
            pass
        assert _classify_kind(S("hello")) is None

    def test_int_subclass_rejected(self):
        """Int subclasses must not classify as 'int' — they can override
        __eq__ and inject behavior during equality checks."""
        class I(int):
            pass
        assert _classify_kind(I(42)) is None

    def test_bool_subclass_rejected(self):
        """Bool subclasses must not classify as 'bool'."""
        # bool is final in CPython, but the exact-type check handles
        # any hypothetical subclass consistently.
        assert _classify_kind(True) == "bool"
        assert _classify_kind(False) == "bool"

    def test_float_subclass_rejected(self):
        """Float subclasses must not classify as 'float'."""
        class F(float):
            pass
        assert _classify_kind(F(3.14)) is None


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

    def test_negative_zero_not_equal_positive_zero(self):
        assert _mu_deep_equal(-0.0, -0.0)
        assert not _mu_deep_equal(0.0, -0.0)

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
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
            "program_order": [], "programs": [],
        }
        with pytest.raises(ValueError, match="Unsupported IR"):
            validate_bundle(bundle)

    def test_unknown_opcode(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
            "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [{"op": "explode"}]}],
        }
        with pytest.raises(ValueError, match="Unknown opcode"):
            validate_bundle(bundle)

    def test_duplicate_program_id(self):
        prog = {"id": "p1", "ops": [{"op": "return_projection_fail"}]}
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
            "program_order": ["p1", "p1"],
            "programs": [prog, prog],
        }
        with pytest.raises(ValueError, match="Duplicate program ID"):
            validate_bundle(bundle)

    def test_empty_ops(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
            "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": []}],
        }
        with pytest.raises(ValueError, match="empty"):
            validate_bundle(bundle)

    def test_program_order_mismatch(self):
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "x", "source_seed": "x",
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
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


class TestAttemptTrace:
    """Stage0 step results expose deterministic attempted-program trace."""

    @staticmethod
    def _trace_bundle():
        return {
            "stage0_ir_version": 1,
            "bundle_id": "attempt-trace-test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": ["p.fail", "p.match", "p.untried"],
            "programs": [
                {
                    "id": "p.fail",
                    "ops": [{"op": "return_projection_fail"}],
                },
                {
                    "id": "p.match",
                    "ops": [
                        {
                            "op": "write_path",
                            "template": {"kind": "literal", "value": "matched"},
                        },
                        {"op": "return_projection_success"},
                    ],
                },
                {
                    "id": "p.untried",
                    "ops": [{"op": "return_projection_fail"}],
                },
            ],
        }

    def test_attempt_trace_match_stops_at_winner(self):
        r = stage0_vm_step(self._trace_bundle(), "input")
        assert r["attempt_trace"] == {
            "attempted_program_ids": ["p.fail", "p.match"],
            "outcome": "match",
            "matched_program_id": "p.match",
        }
        assert r["metrics"]["program_attempts"] == 2

    def test_attempt_trace_stall_records_all_attempts(self):
        bundle = self._trace_bundle()
        bundle["program_order"] = ["p.fail", "p.untried"]
        bundle["programs"] = [bundle["programs"][0], bundle["programs"][2]]

        r = stage0_vm_step(bundle, "input")
        assert r["attempt_trace"] == {
            "attempted_program_ids": ["p.fail", "p.untried"],
            "outcome": "stall",
            "matched_program_id": None,
        }
        assert r["metrics"]["program_attempts"] == 2


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
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
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
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
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
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
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
            "machine_profile": "rcx.stage0.v1", "hand_authored": True,
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
    """Call JS Stage0 VM via subprocess and return parsed result.

    Delegates to shared helper (tests/l4_gates/stage0_test_helpers.py).
    """
    from tests.l4_gates.stage0_test_helpers import run_js_stage0
    return run_js_stage0(action, bundle_path, input_value)


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
        assert py_result["attempt_trace"] == js_result["attempt_trace"], (
            f"Attempt trace mismatch:\npy={py_result['attempt_trace']}\n"
            f"js={js_result['attempt_trace']}")
        assert _mu_deep_equal(py_result["root"], js_result["root"]), (
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
        assert _mu_deep_equal(py_result["root"], js_result["root"]), (
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


# =========================================================================
# P7-b.1: Hardening Floor Tests
# =========================================================================

def _make_bundle(ops, pid="p1"):
    """Helper: minimal valid bundle with one program."""
    return {
        "stage0_ir_version": 1,
        "bundle_id": "test",
        "source_seed": "test",
        "machine_profile": "rcx.stage0.v1",
        "hand_authored": True,
        "program_order": [pid],
        "programs": [{"id": pid, "ops": ops}],
    }


class TestCapturePathProvenance:
    """Capture values must be Mu-domain values before they enter captures."""

    def _capture_echo_bundle(self):
        return _make_bundle([
            {"op": "capture_path", "path": ["focus", "root", "x"], "name": "x"},
            {"op": "write_path",
             "template": {"kind": "capture_ref", "name": "x"}},
            {"op": "return_projection_success"},
        ])

    def _run_node_direct(self, script):
        completed = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30,
        )
        assert completed.returncode == 0, (
            f"node exited {completed.returncode}\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        assert lines, f"node produced no stdout; stderr: {completed.stderr}"
        return json.loads(lines[-1])

    def test_valid_mu_capture_matches_python_and_node_direct(self):
        bundle = self._capture_echo_bundle()
        inp = {"x": {"a": [1, 3.5, True, None, "ok"]}}

        py_result = stage0_vm_step(bundle, inp)
        script = """
const { stage0VmStep } = require('./mu/host/js/core/stage0_vm.js');
const bundle = __BUNDLE__;
const input = __INPUT__;
const result = stage0VmStep(bundle, input);
console.log(JSON.stringify({ok: true, result}));
""".replace("__BUNDLE__", json.dumps(bundle)).replace(
            "__INPUT__", json.dumps(inp))
        js_payload = self._run_node_direct(script)

        assert js_payload["ok"] is True
        assert py_result["status"] == "match"
        assert js_payload["result"]["status"] == "match"
        assert _mu_deep_equal(py_result["root"], js_payload["result"]["root"])
        assert _mu_deep_equal(py_result["root"], inp["x"])

    def test_python_non_mu_direct_capture_fails_at_capture_path(self):
        class NonMuLeaf:
            pass

        bundle = self._capture_echo_bundle()
        with pytest.raises(Stage0VMError, match="capture_path"):
            stage0_vm_step(bundle, {"x": NonMuLeaf()})

    @pytest.mark.parametrize("value", [
        float("nan"),
        float("inf"),
        {1: "non-string-key", "ok": "yes"},
    ])
    def test_python_direct_capture_rejects_non_mu_values(self, value):
        bundle = self._capture_echo_bundle()
        with pytest.raises(Stage0VMError, match="capture_path"):
            stage0_vm_step(bundle, {"x": value})

    def test_node_non_mu_direct_capture_fails_at_capture_path(self):
        bundle = self._capture_echo_bundle()
        script = """
const { stage0VmStep } = require('./mu/host/js/core/stage0_vm.js');
const bundle = __BUNDLE__;
const symbolKeyObject = {ok: 'yes'};
symbolKeyObject[Symbol('non-mu-key')] = 'secret';
const sparse = [];
sparse[1] = 'value';
const cases = [
  ['symbol_leaf', Symbol('non-mu')],
  ['nan', NaN],
  ['infinity', Infinity],
  ['symbol_key', symbolKeyObject],
  ['sparse_array', sparse],
];
const results = [];
for (const [label, value] of cases) {
  try {
    stage0VmStep(bundle, {x: value});
    results.push({label, ok: false, accepted: true});
  } catch (err) {
    results.push({
      label,
      ok: err && err.name === 'Stage0VMError' &&
          String(err.message).includes('capture_path'),
      name: err && err.name,
      message: err && err.message
    });
  }
}
console.log(JSON.stringify({
  ok: results.every(item => item.ok),
  results
}));
""".replace("__BUNDLE__", json.dumps(bundle))
        payload = self._run_node_direct(script)
        assert payload["ok"] is True, payload


# ---------------------------------------------------------------------------
# Per-opcode schema validation
# ---------------------------------------------------------------------------

class TestOpcodeSchemaValidation:
    """P7-b.1 Item 1: per-opcode field validation with unknown-key rejection."""

    @pytest.mark.parametrize("opcode,schema", list(OPCODE_SCHEMAS.items()))
    def test_missing_required_field(self, opcode, schema):
        """Each required field, when missing, must raise ValueError."""
        for missing_key in schema["required"]:
            op_spec = {"op": opcode}
            for k in schema["required"]:
                if k != missing_key:
                    # Provide a placeholder value
                    if k == "path":
                        op_spec[k] = ["focus", "root"]
                    elif k == "kind":
                        op_spec[k] = "dict"
                    elif k == "value":
                        op_spec[k] = 1
                    elif k == "name":
                        op_spec[k] = "x"
                    elif k == "capture_name":
                        op_spec[k] = "x"
                    elif k == "required":
                        op_spec[k] = ["a"]
                    elif k == "template":
                        op_spec[k] = {"kind": "literal", "value": 1}
                    else:
                        op_spec[k] = "placeholder"
            bundle = _make_bundle([op_spec])
            with pytest.raises(ValueError, match="missing required field"):
                validate_bundle(bundle)

    @pytest.mark.parametrize("opcode", list(OPCODE_SCHEMAS.keys()))
    def test_unknown_key_rejected(self, opcode):
        """Unknown keys on any op_spec must raise ValueError."""
        schema = OPCODE_SCHEMAS[opcode]
        op_spec = {"op": opcode, "UNKNOWN_EXTRA": True}
        for k in schema["required"]:
            if k == "path":
                op_spec[k] = ["focus", "root"]
            elif k == "kind":
                op_spec[k] = "dict"
            elif k == "value":
                op_spec[k] = 1
            elif k == "name":
                op_spec[k] = "x"
            elif k == "capture_name":
                op_spec[k] = "x"
            elif k == "required":
                op_spec[k] = ["a"]
            elif k == "template":
                op_spec[k] = {"kind": "literal", "value": 1}
            else:
                op_spec[k] = "placeholder"
        bundle = _make_bundle([op_spec])
        with pytest.raises(ValueError, match="unknown field"):
            validate_bundle(bundle)

    def test_source_map_accepted(self):
        """source_map is a global optional and must be accepted on any op."""
        ops = [{"op": "return_projection_fail", "source_map": {"line": 1}}]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise

    def test_valid_ops_pass(self, match_bundle, subst_bundle):
        """Existing hand-authored bundles with source_map pass validation."""
        validate_bundle(match_bundle)
        validate_bundle(subst_bundle)

    def test_assert_focus_kind_unsupported_kind(self):
        """assert_focus_kind with kind='float' must be rejected."""
        ops = [{"op": "assert_focus_kind", "path": ["focus", "root"], "kind": "float"}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="unsupported kind"):
            validate_bundle(bundle)

    def test_assert_focus_kind_supported_kinds(self):
        """All SUPPORTED_KINDS must be accepted."""
        for kind in SUPPORTED_KINDS:
            ops = [
                {"op": "assert_focus_kind", "path": ["focus", "root"], "kind": kind},
                {"op": "return_projection_fail"},
            ]
            bundle = _make_bundle(ops)
            validate_bundle(bundle)  # should not raise

    def test_path_exceeding_max_depth(self):
        """Path longer than MAX_PATH_DEPTH must be rejected."""
        long_path = ["focus", "root"] + ["k"] * (MAX_PATH_DEPTH + 1)
        ops = [{"op": "check_exists", "path": long_path}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="MAX_PATH_DEPTH"):
            validate_bundle(bundle)

    def test_path_at_max_depth_accepted(self):
        """Path at exactly MAX_PATH_DEPTH must be accepted."""
        ok_path = ["focus", "root"] + ["k"] * (MAX_PATH_DEPTH - 2)
        ops = [
            {"op": "check_exists", "path": ok_path},
            {"op": "return_projection_fail"},
        ]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise


# ---------------------------------------------------------------------------
# Float rejection
# ---------------------------------------------------------------------------

class TestFloatRejection:
    """P7-b.1 Item 3: float values rejected in IR v1."""

    def test_check_equal_float_value(self):
        ops = [{"op": "check_equal", "path": ["focus", "root"], "value": 1.5}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Float values unsupported"):
            validate_bundle(bundle)

    def test_check_equal_nested_float(self):
        """Float nested inside a dict value must be caught."""
        ops = [{"op": "check_equal", "path": ["focus", "root"], "value": {"a": 1.5}}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Float values unsupported"):
            validate_bundle(bundle)

    def test_template_literal_float(self):
        tmpl = {"kind": "literal", "value": 3.14}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Float values unsupported"):
            validate_bundle(bundle)

    def test_allowed_values_float(self):
        ops = [{
            "op": "assert_key_profile",
            "path": ["focus", "root"],
            "required": ["mode"],
            "optional": [{"key": "x", "allowed_values": [1.5]}],
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Float values unsupported"):
            validate_bundle(bundle)

    def test_check_equal_int_accepted(self):
        """Integer values must pass float check."""
        ops = [
            {"op": "check_equal", "path": ["focus", "root"], "value": 42},
            {"op": "return_projection_fail"},
        ]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise

    def test_deeply_nested_value_depth_exceeded(self):
        """Deeply nested literal value exceeds depth bound → ValueError."""
        # Build a deeply nested dict exceeding MAX_TEMPLATE_DEPTH
        val = 1
        for _ in range(MAX_TEMPLATE_DEPTH + 5):
            val = {"x": val}
        ops = [{"op": "check_equal", "path": ["focus", "root"], "value": val}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="depth exceeded"):
            validate_bundle(bundle)


# ---------------------------------------------------------------------------
# String-typing of identifiers (Bridge R4)
# ---------------------------------------------------------------------------

class TestStringTypingIdentifiers:
    """P7-b.1 Bridge R4: all semantically active identifiers must be strings."""

    def test_path_non_string_segment(self):
        ops = [{"op": "check_exists", "path": ["focus", "root", 1]}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="path segment must be a string"):
            validate_bundle(bundle)

    def test_capture_path_name_non_string(self):
        ops = [{"op": "capture_path", "path": ["focus", "root"], "name": 42}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'name' must be a string"):
            validate_bundle(bundle)

    def test_check_captured_equal_capture_name_non_string(self):
        ops = [{
            "op": "check_captured_equal",
            "path": ["focus", "root"],
            "capture_name": 42,
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'capture_name' must be a string"):
            validate_bundle(bundle)

    def test_program_id_non_string(self):
        bundle = {
            "stage0_ir_version": 1,
            "bundle_id": "test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": [1],
            "programs": [{"id": 1, "ops": [{"op": "return_projection_fail"}]}],
        }
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_program_order_entry_non_string(self):
        bundle = {
            "stage0_ir_version": 1,
            "bundle_id": "test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": [1],
            "programs": [{"id": "1", "ops": [{"op": "return_projection_fail"}]}],
        }
        with pytest.raises(ValueError, match="program_order entry must be a string"):
            validate_bundle(bundle)

    def test_assert_key_profile_required_non_string(self):
        ops = [{
            "op": "assert_key_profile",
            "path": ["focus", "root"],
            "required": [1],
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'required' items must be strings"):
            validate_bundle(bundle)

    def test_assert_key_profile_optional_key_non_string(self):
        ops = [{
            "op": "assert_key_profile",
            "path": ["focus", "root"],
            "required": ["a"],
            "optional": [{"key": 1}],
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'key' must be a string"):
            validate_bundle(bundle)

    def test_all_string_identifiers_pass(self):
        """Bundle with all-string identifiers must pass validation."""
        ops = [
            {"op": "capture_path", "path": ["focus", "root", "x"], "name": "cap"},
            {"op": "check_captured_equal",
             "path": ["focus", "root", "x"], "capture_name": "cap"},
            {"op": "return_projection_fail"},
        ]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise

    def test_capture_ref_name_non_string_in_template(self):
        """Template capture_ref with non-string name must be rejected."""
        tmpl = {"kind": "capture_ref", "name": 42}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'name' must be a string"):
            validate_bundle(bundle)

    def test_assert_focus_kind_non_string_kind(self):
        """kind=[] must raise ValueError (not TypeError: unhashable type)."""
        ops = [{"op": "assert_focus_kind", "path": ["focus", "root"], "kind": []}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'kind' must be a string"):
            validate_bundle(bundle)

    def test_assert_focus_kind_non_string_kind_int(self):
        """kind=42 must raise ValueError, not silently pass."""
        ops = [{"op": "assert_focus_kind", "path": ["focus", "root"], "kind": 42}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'kind' must be a string"):
            validate_bundle(bundle)


# ---------------------------------------------------------------------------
# Optional entry closure (Bridge R5)
# ---------------------------------------------------------------------------

class TestOptionalEntryClosure:
    """P7-b.1 Bridge R5: optional entry dicts are closed IR nodes."""

    def test_optional_entry_unknown_key_rejected(self):
        """Typo like 'allowed_value' (missing 's') must be caught."""
        ops = [{
            "op": "assert_key_profile",
            "path": ["focus", "root"],
            "required": ["a"],
            "optional": [{"key": "x", "allowed_value": ["safe"]}],
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="unknown key"):
            validate_bundle(bundle)

    def test_optional_entry_valid_keys_accepted(self):
        """Valid optional entry with both key and allowed_values passes."""
        ops = [
            {
                "op": "assert_key_profile",
                "path": ["focus", "root"],
                "required": ["a"],
                "optional": [{"key": "x", "allowed_values": ["safe", "fast"]}],
            },
            {"op": "return_projection_fail"},
        ]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise

    def test_allowed_values_non_list_rejected(self):
        ops = [{
            "op": "assert_key_profile",
            "path": ["focus", "root"],
            "required": ["a"],
            "optional": [{"key": "x", "allowed_values": "not_a_list"}],
        }]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="'allowed_values' must be a list"):
            validate_bundle(bundle)


# ---------------------------------------------------------------------------
# Template validation at bundle time
# ---------------------------------------------------------------------------

class TestTemplateValidation:
    """P7-b.1 Item 1: template validation with closed-IR key checks."""

    def test_template_unknown_key_rejected(self):
        tmpl = {"kind": "literal", "value": 1, "extra": True}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="unknown key"):
            validate_bundle(bundle)

    def test_template_missing_required_key(self):
        tmpl = {"kind": "literal"}  # missing 'value'
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="missing required key"):
            validate_bundle(bundle)

    def test_template_invalid_kind(self):
        tmpl = {"kind": "BOGUS", "value": 1}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Unknown template kind"):
            validate_bundle(bundle)

    def test_template_deeply_nested_exceeds_depth(self):
        """Template tree exceeding MAX_TEMPLATE_DEPTH must be rejected."""
        tmpl = {"kind": "literal", "value": 1}
        for _ in range(MAX_TEMPLATE_DEPTH + 5):
            tmpl = {"kind": "object", "fields": {"x": tmpl}}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="Template depth exceeded"):
            validate_bundle(bundle)

    def test_template_object_non_dict_fields(self):
        tmpl = {"kind": "object", "fields": "not_dict"}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="must be a dict"):
            validate_bundle(bundle)

    def test_template_list_non_list_items(self):
        tmpl = {"kind": "list", "items": "not_list"}
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="must be a list"):
            validate_bundle(bundle)

    def test_valid_template_passes(self):
        """Valid nested template passes validation."""
        tmpl = {
            "kind": "object",
            "fields": {
                "a": {"kind": "literal", "value": 1},
                "b": {"kind": "capture_ref", "name": "x"},
                "c": {"kind": "list", "items": [
                    {"kind": "literal", "value": "hello"},
                ]},
            },
        }
        ops = [{"op": "write_path", "template": tmpl}]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # should not raise


# ---------------------------------------------------------------------------
# Template error normalization (defense-in-depth, Item 2)
# ---------------------------------------------------------------------------

class TestTemplateErrorNormalization:
    """P7-b.1 Item 2: runtime template errors yield Stage0VMError, not raw host errors.

    These test _materialize_template directly (defense-in-depth layer).
    validate_bundle also catches these at validation time, but
    _materialize_template is the last line of defense for any template
    that somehow bypasses validation.
    """

    def test_literal_missing_value(self):
        with pytest.raises(Stage0VMError, match="missing 'value'"):
            _materialize_template({"kind": "literal"}, {})

    def test_capture_ref_missing_name(self):
        with pytest.raises(Stage0VMError, match="missing 'name'"):
            _materialize_template({"kind": "capture_ref"}, {})

    def test_object_missing_fields(self):
        with pytest.raises(Stage0VMError, match="missing or invalid 'fields'"):
            _materialize_template({"kind": "object"}, {})

    def test_object_non_dict_fields(self):
        with pytest.raises(Stage0VMError, match="missing or invalid 'fields'"):
            _materialize_template({"kind": "object", "fields": "bad"}, {})

    def test_list_missing_items(self):
        with pytest.raises(Stage0VMError, match="missing or invalid 'items'"):
            _materialize_template({"kind": "list"}, {})

    def test_list_non_list_items(self):
        with pytest.raises(Stage0VMError, match="missing or invalid 'items'"):
            _materialize_template({"kind": "list", "items": "bad"}, {})

    def test_valid_template_still_works(self):
        """Defense-in-depth guards don't break valid templates."""
        result = _materialize_template({"kind": "literal", "value": 42}, {})
        assert result == 42


# ---------------------------------------------------------------------------
# Safe wrappers for recursion overflow (Item 4)
# ---------------------------------------------------------------------------

class TestSafeWrappers:
    """P7-b.1 Item 4: _safe_mu_deep_equal and _safe_mu_copy wrappers."""

    def test_safe_deep_equal_shallow(self):
        """Shallow structures work normally."""
        assert _safe_mu_deep_equal({"a": 1}, {"a": 1}) is True
        assert _safe_mu_deep_equal({"a": 1}, {"a": 2}) is False

    def test_safe_deep_equal_overflow(self):
        """Deeply nested structures raise Stage0VMError, not RecursionError."""
        # Build structure deeper than Python recursion limit
        a = {"x": None}
        b = {"x": None}
        cur_a, cur_b = a, b
        for _ in range(600):
            new_a = {"x": None}
            new_b = {"x": None}
            cur_a["x"] = new_a
            cur_b["x"] = new_b
            cur_a = new_a
            cur_b = new_b
        with pytest.raises(Stage0VMError, match="recursion overflow"):
            _safe_mu_deep_equal(a, b)

    def test_safe_mu_copy_shallow(self):
        """Shallow copy works normally."""
        original = {"a": [1, 2]}
        copied = _safe_mu_copy(original)
        assert copied == original
        assert copied is not original

    def test_safe_mu_copy_overflow(self):
        """Deeply nested copy raises Stage0VMError, not RecursionError."""
        val = {"x": None}
        cur = val
        for _ in range(1500):
            new = {"x": None}
            cur["x"] = new
            cur = new
        with pytest.raises(Stage0VMError, match="recursion overflow"):
            _safe_mu_copy(val)

    def test_check_equal_deep_value_overflow(self):
        """check_equal with deeply nested value overflows → Stage0VMError."""
        # Build deep value
        val = {"x": None}
        cur = val
        for _ in range(600):
            new = {"x": None}
            cur["x"] = new
            cur = new

        ops = [
            {"op": "check_equal", "path": ["focus", "root"], "value": 42},
            {"op": "return_projection_fail"},
        ]
        bundle = _make_bundle(ops)
        # Feed the deep structure as input — check_equal uses _safe_mu_deep_equal
        # This should NOT overflow because the comparison short-circuits on type mismatch
        result = stage0_vm_step(bundle, val)
        assert result["status"] == "stall"

    def test_literal_deep_copy_overflow(self):
        """Deeply nested value overflows _safe_mu_copy (defense-in-depth)."""
        val = {"x": None}
        cur = val
        for _ in range(1500):
            new = {"x": None}
            cur["x"] = new
            cur = new

        with pytest.raises(Stage0VMError, match="recursion overflow"):
            _safe_mu_copy(val)

    def test_safe_deep_equal_hostile_eq_fail_closed(self):
        """Hostile __eq__ on primitive subclass must fail-closed (return False)."""
        class EvilStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__
        # Same type, same value — but __eq__ throws
        a = EvilStr("hello")
        b = EvilStr("hello")
        # Must NOT raise — catch-all returns False
        assert _safe_mu_deep_equal(a, b) is False

    def test_safe_deep_equal_hostile_eq_in_dict_leaf(self):
        """Hostile __eq__ on leaves inside plain dict must fail-closed."""
        class EvilStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__
        a = {"x": EvilStr("hello")}
        b = {"x": EvilStr("hello")}
        assert _safe_mu_deep_equal(a, b) is False

    def test_check_captured_equal_hostile_leaf_fails_at_capture_path(self):
        """EvilStr leaves in plain dict fail closed before capture storage."""
        class EvilStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__
        bundle = _make_bundle([
            {"op": "assert_focus_kind", "path": ["focus", "root"], "kind": "dict"},
            {"op": "capture_path", "path": ["focus", "root", "x"], "name": "cx"},
            {"op": "check_captured_equal",
             "path": ["focus", "root", "y"], "capture_name": "cx"},
            {"op": "write_path",
             "template": {"kind": "literal", "value": "matched"}},
            {"op": "return_projection_success"},
        ])
        evil = EvilStr("hello")
        with pytest.raises(Stage0VMError, match="capture_path"):
            stage0_vm_step(bundle, {"x": evil, "y": evil})


# ---------------------------------------------------------------------------
# P7-b.1 Adversary hardening: null sentinel, closed bundle/program
# ---------------------------------------------------------------------------

class TestNullSentinel:
    """Adversary finding: write_path producing null must not conflate with 'no write'."""

    def test_null_literal_write_path_accepted(self):
        """write_path with null literal + return_projection_success should succeed."""
        ops = [
            {"op": "write_path", "template": {"kind": "literal", "value": None}},
            {"op": "return_projection_success"},
        ]
        bundle = _make_bundle(ops)
        result = stage0_vm_step(bundle, {"any": "input"})
        assert result["status"] == "match"
        assert result["root"] is None

    def test_return_without_write_still_errors(self):
        """return_projection_success without any write_path still raises."""
        ops = [
            {"op": "return_projection_success"},
        ]
        bundle = _make_bundle(ops)
        with pytest.raises(Stage0VMError, match="return_projection_success without write_path"):
            stage0_vm_step(bundle, {"any": "input"})


class TestClosedBundleProgram:
    """Adversary finding: bundle and program top-level must reject unknown keys."""

    def test_bundle_unknown_key_rejected(self):
        """Extra top-level key in bundle rejected."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "test",
            "source_seed": "test", "machine_profile": "rcx.stage0.v1",
            "hand_authored": True, "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [
                {"op": "write_path", "template": {"kind": "literal", "value": 1}},
                {"op": "return_projection_success"},
            ]}],
            "EVIL_EXTRA": "payload",
        }
        with pytest.raises(ValueError, match="Unknown bundle-level key"):
            validate_bundle(bundle)

    def test_program_unknown_key_rejected(self):
        """Extra key on program dict rejected."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "test",
            "source_seed": "test", "machine_profile": "rcx.stage0.v1",
            "hand_authored": True, "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [
                {"op": "write_path", "template": {"kind": "literal", "value": 1}},
                {"op": "return_projection_success"},
            ], "EVIL_EXTRA": "payload"}],
        }
        with pytest.raises(ValueError, match="unknown key"):
            validate_bundle(bundle)

    def test_program_source_map_accepted(self):
        """source_map on program is an allowed optional key."""
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "test",
            "source_seed": "test", "machine_profile": "rcx.stage0.v1",
            "hand_authored": True, "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [
                {"op": "write_path", "template": {"kind": "literal", "value": 1}},
                {"op": "return_projection_success"},
            ], "source_map": {"info": "test"}}],
        }
        validate_bundle(bundle)  # Should not raise

    def test_valid_bundle_no_extra_keys(self):
        """Clean bundle with only allowed keys passes."""
        ops = [
            {"op": "write_path", "template": {"kind": "literal", "value": 1}},
            {"op": "return_projection_success"},
        ]
        bundle = _make_bundle(ops)
        validate_bundle(bundle)  # Should not raise


class TestPrototypeKeyHardening:
    """Bridge R1: JS prototype-key pollution must not bypass validation."""

    def test_proto_opcode_rejected(self):
        """__proto__ as opcode name must raise ValueError, not host TypeError."""
        bundle = _make_bundle([{"op": "__proto__"}])
        with pytest.raises(ValueError, match="Unknown opcode"):
            validate_bundle(bundle)

    def test_proto_template_kind_rejected(self):
        """__proto__ as template kind must raise ValueError, not host TypeError."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {"kind": "__proto__"}},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Unknown template kind"):
            validate_bundle(bundle)

    def test_constructor_opcode_rejected(self):
        """constructor as opcode name must be rejected."""
        bundle = _make_bundle([{"op": "constructor"}])
        with pytest.raises(ValueError, match="Unknown opcode"):
            validate_bundle(bundle)

    def test_step_validates_before_execution(self):
        """stage0_vm_step enforces validate_bundle before executing."""
        # Float in check_equal.value — Python catches at validation
        bundle = {
            "stage0_ir_version": 1, "bundle_id": "test",
            "source_seed": "test", "machine_profile": "rcx.stage0.v1",
            "hand_authored": True, "program_order": ["p1"],
            "programs": [{"id": "p1", "ops": [
                {"op": "check_equal", "path": ["focus", "root"],
                 "value": 3.14},
                {"op": "return_projection_fail"},
            ]}],
        }
        with pytest.raises(ValueError, match="Float values unsupported"):
            stage0_vm_step(bundle, 1)

    def test_validate_bundle_none_raises(self):
        """validate_bundle(None) must raise ValueError, not TypeError."""
        with pytest.raises(ValueError, match="Bundle must be a dict"):
            validate_bundle(None)

    def test_validate_bundle_list_raises(self):
        """validate_bundle([]) must raise ValueError, not TypeError."""
        with pytest.raises(ValueError, match="Bundle must be a dict"):
            validate_bundle([])

    def test_validate_bundle_string_raises(self):
        """validate_bundle('foo') must raise ValueError, not TypeError."""
        with pytest.raises(ValueError, match="Bundle must be a dict"):
            validate_bundle("foo")

    def test_opcode_non_string_op_rejected(self):
        """op=[] must raise ValueError, not TypeError: unhashable type."""
        bundle = _make_bundle([{"op": []}])
        with pytest.raises(ValueError, match="'op' must be a string"):
            validate_bundle(bundle)

    def test_template_kind_non_string_rejected(self):
        """Template with kind=[] must raise ValueError, not TypeError."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {"kind": []}},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="'kind' must be a string"):
            validate_bundle(bundle)

    def test_path_invalid_namespace_rejected(self):
        """Path not starting with ['focus', 'root'] must be caught at validation."""
        bundle = _make_bundle([
            {"op": "check_exists", "path": ["not_focus", "root"]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="path must start with"):
            validate_bundle(bundle)

    def test_template_object_non_string_field_key_rejected(self):
        """Template object with int field key must be rejected for parity."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "object",
                "fields": {1: {"kind": "literal", "value": "v"}},
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="field key must be a string"):
            validate_bundle(bundle)


# ---------------------------------------------------------------------------
# Hostile subclass adversarial tests (Bridge R8/R9)
# ---------------------------------------------------------------------------

class TestHostileStrSubclasses:
    """Hostile str subclasses must be rejected at all validation-boundary
    string checks.  These subclasses override __hash__/__eq__ to leak
    raw RuntimeError through isinstance(x, str) checks."""

    def _evil_hash_str(self, value):
        """Return a str subclass whose __hash__ raises RuntimeError."""
        class EvilHashStr(str):
            def __hash__(self):
                raise RuntimeError("evil-hash")
        return EvilHashStr(value)

    def _evil_eq_str(self, value):
        """Return a str subclass whose __eq__ raises RuntimeError."""
        class EvilEqStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__  # restore hashability (Python unsets on __eq__ override)
        return EvilEqStr(value)

    def test_hostile_str_program_order_entry(self):
        """program_order entry with hostile str subclass must be rejected."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["program_order"] = [self._evil_hash_str("p1")]
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_program_id(self):
        """Program id with hostile str subclass must be rejected."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["programs"][0]["id"] = self._evil_hash_str("p1")
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_op_field(self):
        """Op 'op' field with hostile str subclass must be rejected."""
        bundle = _make_bundle([{"op": self._evil_eq_str("return_projection_fail")}])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_assert_focus_kind(self):
        """assert_focus_kind 'kind' with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "assert_focus_kind",
             "path": ["focus", "root"],
             "kind": self._evil_eq_str("dict")},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_capture_path_name(self):
        """capture_path 'name' with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "capture_path",
             "path": ["focus", "root"],
             "name": self._evil_hash_str("x")},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_check_captured_equal_capture_name(self):
        """check_captured_equal 'capture_name' with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "check_captured_equal",
             "path": ["focus", "root"],
             "capture_name": self._evil_eq_str("x")},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_path_segment(self):
        """Path segment with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "check_exists",
             "path": ["focus", "root", self._evil_hash_str("key")]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_required_item(self):
        """assert_key_profile required item with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "assert_key_profile",
             "path": ["focus", "root"],
             "required": [self._evil_hash_str("k")]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be strings"):
            validate_bundle(bundle)

    def test_hostile_str_optional_entry_key(self):
        """assert_key_profile optional entry key with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "assert_key_profile",
             "path": ["focus", "root"],
             "required": ["k"],
             "optional": [{"key": self._evil_hash_str("x")}]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_template_kind(self):
        """Template 'kind' with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": self._evil_eq_str("literal"),
                "value": 1,
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_template_capture_ref_name(self):
        """Template capture_ref 'name' with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "capture_ref",
                "name": self._evil_hash_str("x"),
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_hostile_str_template_object_field_key(self):
        """Template object field key with hostile str must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "object",
                "fields": {self._evil_eq_str("k"): {
                    "kind": "literal", "value": 1}},
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="field key must be a string"):
            validate_bundle(bundle)


class TestHostileNestedLiteralSubclasses:
    """Hostile dict/list subclasses nested inside literal values must not
    leak raw exceptions through _check_no_floats traversal."""

    def test_hostile_dict_in_check_equal_value(self):
        """EvilDict nested in check_equal.value rejected as non-Mu type."""
        class EvilDict(dict):
            def values(self):
                raise RuntimeError("evil-values")
        bundle = _make_bundle([
            {"op": "check_equal",
             "path": ["focus", "root"],
             "value": EvilDict({"a": 1})},
            {"op": "return_projection_fail"},
        ])
        # Mu-domain validation rejects EvilDict (not type(v) is dict)
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_list_in_check_equal_value(self):
        """EvilList nested in check_equal.value rejected as non-Mu type."""
        class EvilList(list):
            def __iter__(self):
                raise RuntimeError("evil-iter")
        bundle = _make_bundle([
            {"op": "check_equal",
             "path": ["focus", "root"],
             "value": EvilList([1, 2])},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_dict_in_template_literal_value(self):
        """EvilDict nested in template literal value rejected as non-Mu type."""
        class EvilDict(dict):
            def values(self):
                raise RuntimeError("evil-values")
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "literal",
                "value": EvilDict({"a": 1}),
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_list_in_template_literal_value(self):
        """EvilList nested in template literal value rejected as non-Mu type."""
        class EvilList(list):
            def __iter__(self):
                raise RuntimeError("evil-iter")
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "literal",
                "value": EvilList([1, 2]),
            }},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_dict_in_allowed_values(self):
        """EvilDict nested in allowed_values rejected as non-Mu type."""
        class EvilDict(dict):
            def values(self):
                raise RuntimeError("evil-values")
        bundle = _make_bundle([
            {"op": "assert_key_profile",
             "path": ["focus", "root"],
             "required": ["k"],
             "optional": [{"key": "x",
                           "allowed_values": [EvilDict({"a": 1})]}]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_list_in_allowed_values(self):
        """EvilList nested in allowed_values rejected as non-Mu type."""
        class EvilList(list):
            def __iter__(self):
                raise RuntimeError("evil-iter")
        bundle = _make_bundle([
            {"op": "assert_key_profile",
             "path": ["focus", "root"],
             "required": ["k"],
             "optional": [{"key": "x",
                           "allowed_values": [EvilList([1, 2])]}]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_hostile_dict_subclass_outer_bundle_rejected(self):
        """EvilDict at outer bundle level must be rejected (not just nested)."""
        class EvilDict(dict):
            def __getitem__(self, key):
                raise RuntimeError("evil-getitem")
        base = _make_bundle([{"op": "return_projection_fail"}])
        with pytest.raises(ValueError, match="Bundle must be a dict"):
            validate_bundle(EvilDict(base))

    def test_hostile_list_subclass_outer_programs_rejected(self):
        """EvilList at program_order level must be rejected."""
        class EvilList(list):
            def __iter__(self):
                raise RuntimeError("evil-iter")
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["program_order"] = EvilList(["p1"])
        with pytest.raises(ValueError, match="must be a list"):
            validate_bundle(bundle)


class TestHostileDictKeys:
    """Hostile str subclass dict KEYS (not values) must be rejected before
    any membership/equality checks can trigger __eq__/__hash__ leaks."""

    def _make_hostile_key_dict(self, real_key, real_value):
        """Create a plain dict with a hostile str subclass key."""
        class EvilEqStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__
        d = {}
        d.__setitem__(EvilEqStr(real_key), real_value)
        return d, EvilEqStr

    def test_hostile_bundle_key(self):
        """Hostile str subclass as bundle dict key must be rejected."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        d, _ = self._make_hostile_key_dict("stage0_ir_version", 1)
        for k, v in bundle.items():
            if k != "stage0_ir_version":
                d[k] = v
        with pytest.raises(ValueError, match="Bundle key must be a string"):
            validate_bundle(d)

    def test_hostile_program_key(self):
        """Hostile str subclass as program dict key must be rejected."""
        d, _ = self._make_hostile_key_dict("id", "p1")
        d["ops"] = [{"op": "return_projection_fail"}]
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["programs"] = [d]
        with pytest.raises(ValueError, match="Program key must be a string"):
            validate_bundle(bundle)

    def test_hostile_op_key(self):
        """Hostile str subclass as op dict key must be rejected."""
        d, _ = self._make_hostile_key_dict("op", "return_projection_fail")
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["programs"][0]["ops"] = [d]
        with pytest.raises(ValueError, match="key must be a string"):
            validate_bundle(bundle)

    def test_hostile_optional_entry_key(self):
        """Hostile str subclass as optional entry dict key must be rejected."""
        d, _ = self._make_hostile_key_dict("key", "x")
        bundle = _make_bundle([
            {"op": "assert_key_profile",
             "path": ["focus", "root"],
             "required": ["k"],
             "optional": [d]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="optional entry key must be a string"):
            validate_bundle(bundle)

    def test_hostile_template_node_key(self):
        """Hostile str subclass as template node dict key must be rejected."""
        d, _ = self._make_hostile_key_dict("kind", "literal")
        d["value"] = 1
        bundle = _make_bundle([
            {"op": "write_path", "template": d},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Template node key must be a string"):
            validate_bundle(bundle)


class TestVersionTypeParity:
    """stage0_ir_version must be exact int — reject bool (Python: True==1) and float."""

    def test_bool_version_rejected(self):
        """stage0_ir_version=True must be rejected (True == 1 in Python but !== in JS)."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["stage0_ir_version"] = True
        with pytest.raises(ValueError, match="must be an int"):
            validate_bundle(bundle)

    def test_float_version_rejected(self):
        """stage0_ir_version=1.0 must be rejected (Python-only: JS 1.0===1)."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["stage0_ir_version"] = 1.0
        with pytest.raises(ValueError, match="must be an int"):
            validate_bundle(bundle)

    def test_int_version_accepted(self):
        """stage0_ir_version=1 must be accepted."""
        bundle = _make_bundle([{"op": "return_projection_fail"}])
        bundle["stage0_ir_version"] = 1
        validate_bundle(bundle)  # Must not raise


class TestNonMuLiteralRejection:
    """Non-Mu types in literal values must be rejected by Mu-domain validation."""

    def test_tuple_rejected(self):
        """Python tuple in literal value must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "literal", "value": (1, 2)}},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_set_rejected(self):
        """Python set in literal value must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "literal", "value": {1, 2}}},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_bytes_rejected(self):
        """Python bytes in literal value must be rejected."""
        bundle = _make_bundle([
            {"op": "write_path", "template": {
                "kind": "literal", "value": b"data"}},
            {"op": "return_projection_success"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_nested_tuple_in_dict_rejected(self):
        """Tuple nested inside a dict literal value must be rejected."""
        bundle = _make_bundle([
            {"op": "check_equal",
             "path": ["focus", "root"],
             "value": {"key": (1,)}},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_nested_tuple_in_list_rejected(self):
        """Tuple nested inside a list literal value must be rejected."""
        bundle = _make_bundle([
            {"op": "check_equal",
             "path": ["focus", "root"],
             "value": [(1,)]},
            {"op": "return_projection_fail"},
        ])
        with pytest.raises(ValueError, match="Non-Mu value type"):
            validate_bundle(bundle)

    def test_valid_mu_literals_accepted(self):
        """All valid Mu literal types must be accepted."""
        for value in [None, True, False, 0, 42, -1, "", "hello",
                      {}, {"a": 1}, [], [1, 2], {"nested": [1, None, "x"]}]:
            bundle = _make_bundle([
                {"op": "check_equal",
                 "path": ["focus", "root"],
                 "value": value},
                {"op": "return_projection_fail"},
            ])
            validate_bundle(bundle)  # Must not raise


# ---------------------------------------------------------------------------
# P7-b.1 bot-finding tests: safe repr + pid ordering
# ---------------------------------------------------------------------------


class TestValidateTemplateSafeRepr:
    """PR #569 bot finding: _validate_template must not leak __repr__ errors."""

    def test_missing_kind_shows_repr_not_crash(self):
        """Template node missing 'kind' produces ValueError, not __repr__ crash."""
        bad_node = {"value": 42}  # no 'kind' key
        ops = [{"op": "write_path", "template": bad_node}]
        bundle = _make_bundle(ops)
        with pytest.raises(ValueError, match="missing 'kind'"):
            validate_bundle(bundle)

    def test_materialize_hostile_repr_produces_unrepresentable(self):
        """Non-dict template at runtime produces Stage0VMError with safe repr."""
        # _materialize_template wraps repr() in try/except
        with pytest.raises(Stage0VMError, match="Invalid template node"):
            _materialize_template(42, {})


class TestValidateBundlePidOrdering:
    """PR #569 bot finding: pid must be type-checked before use in error msgs."""

    def test_non_string_pid_rejected(self):
        """Program with non-string 'id' must be rejected with clear message."""
        bundle = {
            "stage0_ir_version": 1,
            "bundle_id": "test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": ["p1"],
            "programs": [{"id": 123, "ops": []}],
        }
        with pytest.raises(ValueError, match="must be a string"):
            validate_bundle(bundle)

    def test_missing_ops_uses_pid_in_error(self):
        """Program missing 'ops' must show pid in error message."""
        bundle = {
            "stage0_ir_version": 1,
            "bundle_id": "test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": ["p1"],
            "programs": [{"id": "p1"}],
        }
        with pytest.raises(ValueError, match="'p1' missing 'ops'"):
            validate_bundle(bundle)


class TestHostileRootInputs:
    """Root input classification must reject non-plain host types.

    P7-b.1 follow-up: _classify_kind must use exact-type checks for dict/list
    so that host subclasses at the input root level produce stall, not match.
    """

    def _make_kind_check_bundle(self, kind):
        """Bundle that checks root kind and returns success if matched."""
        return {
            "stage0_ir_version": 1,
            "bundle_id": "hostile-root-test",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "hand_authored": True,
            "program_order": ["p1"],
            "programs": [{
                "id": "p1",
                "ops": [
                    {"op": "assert_focus_kind",
                     "path": ["focus", "root"], "kind": kind},
                    {"op": "write_path",
                     "template": {"kind": "literal", "value": "matched"}},
                    {"op": "return_projection_success"},
                ],
            }],
        }

    def test_dict_subclass_root_produces_stall(self):
        """Dict subclass as input root must produce stall, not match."""
        class EvilDict(dict):
            def __contains__(self, key):
                raise RuntimeError("evil-contains")
        bundle = self._make_kind_check_bundle("dict")
        result = stage0_vm_step(bundle, EvilDict({"x": 1}))
        assert result["status"] == "stall", (
            f"Dict subclass root should stall, got: {result['status']}")

    def test_list_subclass_root_produces_stall(self):
        """List subclass as input root must produce stall, not match."""
        class EvilList(list):
            def __iter__(self):
                raise RuntimeError("evil-iter")
        bundle = self._make_kind_check_bundle("list")
        result = stage0_vm_step(bundle, EvilList([1, 2, 3]))
        assert result["status"] == "stall", (
            f"List subclass root should stall, got: {result['status']}")

    def test_str_subclass_root_produces_stall(self):
        """Str subclass as input root must produce stall, not match."""
        class EvilStr(str):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = str.__hash__
        bundle = self._make_kind_check_bundle("string")
        result = stage0_vm_step(bundle, EvilStr("hello"))
        assert result["status"] == "stall", (
            f"Str subclass root should stall, got: {result['status']}")

    def test_int_subclass_root_produces_stall(self):
        """Int subclass as input root must produce stall, not match."""
        class EvilInt(int):
            def __eq__(self, other):
                raise RuntimeError("evil-eq")
            __hash__ = int.__hash__
        bundle = self._make_kind_check_bundle("int")
        result = stage0_vm_step(bundle, EvilInt(42))
        assert result["status"] == "stall", (
            f"Int subclass root should stall, got: {result['status']}")
