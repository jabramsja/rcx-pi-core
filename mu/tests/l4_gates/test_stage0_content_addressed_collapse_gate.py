"""Stage 0 Content-Addressed Collapse — Gate Tests.

Wave: stage0-content-addressed-symmetric-fence-2026-06-21c
Task: [NEXT-CODEX-POST-REDTEAM]
Authorization: FOUNDER_OVERRIDE:stage0-content-addressed-symmetric-fence-2026-06-21c
L4 class: L4_STRUCTURAL (host-debt reduction).

Proves the founder-approved (2026-06-20, option 1) symmetric-fence collapse:

  - The four scalar ``isinstance(bool/int/float/str)`` branches in
    ``_stage0_match`` (Python) and the ``typeof !== 'object'`` ``===`` scalar
    branch in ``stage0Match`` (JS) are replaced by ONE content-addressed
    ``mu_hash_cached`` / ``muHashCached`` equality.
  - Exactly ONE input-side raw-list fail-close per substrate restores NO_MATCH
    for raw lists (Python ``isinstance(input_value, list)``; JS
    ``Array.isArray(input)``). Pattern-side list dispatch stays forbidden.
  - Invalid/unsupported host values (tuple, non-Mu) fall through to NO_MATCH
    WITHOUT reaching assert_mu/mu_hash_cached/muHashCached (no raise).

Behavior deltas (authorized, identical in BOTH substrates):
  - +0.0 vs -0.0 flips from MATCH to NO_MATCH (pure content-addressed equality;
    NO -0->+0 canonicalization — that needs a host primitive, rejected
    2026-06-16). See memory ``reference_stage0_signed_zero_divergence``.

Evidence for: P7 Host Semantics Reduction, target gate G8.
"""

import ast
import inspect
import json
import subprocess
import textwrap

import pytest

from rcx_pi.selfhost.eval_seed import NO_MATCH, _stage0_match  # ANTICHEAT_OK: content-addressed collapse gate

from tests.repo_root import REPO_ROOT

JS_BOOTSTRAP_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"

SCALAR_TYPE_NAMES = frozenset({"bool", "int", "float", "str"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stage0_match_ast() -> ast.AST:
    source = textwrap.dedent(inspect.getsource(_stage0_match))
    return ast.parse(source)


def _isinstance_calls(tree: ast.AST):
    """Yield (subject_name, [type_names]) for each isinstance(...) call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "isinstance"):
            continue
        if len(node.args) < 2:
            continue
        subject = node.args[0]
        subject_name = subject.id if isinstance(subject, ast.Name) else "<expr>"
        type_arg = node.args[1]
        if isinstance(type_arg, ast.Name):
            type_names = [type_arg.id]
        elif isinstance(type_arg, ast.Tuple):
            type_names = [e.id for e in type_arg.elts if isinstance(e, ast.Name)]
        else:
            type_names = []
        yield subject_name, type_names


def _call_names_with_arg(tree: ast.AST, func_name: str):
    """Yield the first-arg Name.id for each call to func_name(<Name>, ...)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == func_name):
            continue
        if node.args and isinstance(node.args[0], ast.Name):
            yield node.args[0].id


def _has_content_hash_equality(tree: ast.AST) -> bool:
    """True if a Compare equates mu_hash_cached(pattern) with mu_hash_cached(input_value)."""
    def _hash_subject(call):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "mu_hash_cached" and call.args
                and isinstance(call.args[0], ast.Name)):
            return call.args[0].id
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        subjects = {_hash_subject(op) for op in operands}
        if {"pattern", "input_value"}.issubset(subjects):
            return True
    return False


def _stage0_js_source() -> str:
    """Return just the stage0Match function body text (brace-matched)."""
    lines = JS_BOOTSTRAP_PATH.read_text().splitlines()
    out, in_fn, depth = [], False, 0
    for line in lines:
        if "function stage0Match(" in line:
            in_fn = True
            depth = 0
        if in_fn:
            out.append(line)
            depth += line.count("{") - line.count("}")
            if depth <= 0 and len(out) > 1:
                break
    return "\n".join(out)


def _run_js_stage0(cases_js: str) -> dict:
    """Run a node snippet that fills a `results` object; return parsed JSON.

    `cases_js` receives `stage0Match`, `NO_MATCH`, `tag(label, pat, inp)` and a
    `results` object in scope. `tag` records 'MATCH' / 'NO_MATCH' / 'THROW:<msg>'.
    """
    script = (
        "const { stage0Match, NO_MATCH } = require('./mu/host/js/core/bootstrap_core');\n"
        "const results = {};\n"
        "function tag(label, pat, inp) {\n"
        "  try {\n"
        "    const r = stage0Match(pat, inp);\n"
        "    results[label] = (r === NO_MATCH) ? 'NO_MATCH' : 'MATCH';\n"
        "  } catch (e) { results[label] = 'THROW:' + (e.code || e.message); }\n"
        "}\n"
        f"{cases_js}\n"
        "console.log(JSON.stringify(results));\n"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
    )
    assert proc.returncode == 0, f"JS driver failed: {proc.stderr}"
    return json.loads(proc.stdout.strip())


# ===========================================================================
# Python behavior — content-addressed scalar equality
# ===========================================================================

class TestPyScalarContentHash:
    def test_equal_scalars_match(self):
        assert _stage0_match(5, 5) == {}
        assert _stage0_match("a", "a") == {}
        assert _stage0_match(True, True) == {}
        assert _stage0_match(3.14, 3.14) == {}

    def test_unequal_scalars_no_match(self):
        assert _stage0_match(5, 6) is NO_MATCH
        assert _stage0_match("a", "b") is NO_MATCH

    def test_cross_type_no_match_via_content_hash(self):
        # int vs float and bool vs int stay distinct (content hash encodes type).
        assert _stage0_match(5, 5.0) is NO_MATCH
        assert _stage0_match(True, 1) is NO_MATCH
        assert _stage0_match(1, True) is NO_MATCH
        assert _stage0_match(False, 0) is NO_MATCH


class TestPySignedZeroDelta:
    """+0.0 vs -0.0 -> NO_MATCH (authorized content-addressed delta)."""

    def test_positive_vs_negative_zero_no_match(self):
        assert _stage0_match(0.0, -0.0) is NO_MATCH
        assert _stage0_match(-0.0, 0.0) is NO_MATCH

    def test_same_signed_zero_matches(self):
        assert _stage0_match(0.0, 0.0) == {}
        assert _stage0_match(-0.0, -0.0) == {}


class TestPyRawListFailClose:
    """Raw lists never match at a scalar/non-dict site (input-side fail-close)."""

    def test_equal_raw_lists_no_match(self):
        assert _stage0_match([1, 2], [1, 2]) is NO_MATCH
        assert _stage0_match([], []) is NO_MATCH

    def test_scalar_pattern_raw_list_input_no_match(self):
        assert _stage0_match(5, [1, 2]) is NO_MATCH

    def test_raw_list_pattern_scalar_input_no_match(self):
        # Pattern-side raw list is NOT dispatched on; it simply fails to match.
        assert _stage0_match([1], 5) is NO_MATCH


class TestPyInvalidHostValueFailClose:
    """Unsupported/non-Mu host values return NO_MATCH WITHOUT raising."""

    def test_tuple_pattern_and_input_no_match_no_raise(self):
        assert _stage0_match((1, 2), (1, 2)) is NO_MATCH

    def test_scalar_pattern_tuple_input_no_match_no_raise(self):
        assert _stage0_match(5, (1, 2)) is NO_MATCH

    def test_set_input_no_match_no_raise(self):
        assert _stage0_match(5, {1, 2}) is NO_MATCH

    def test_custom_object_input_no_match_no_raise(self):
        assert _stage0_match(5, object()) is NO_MATCH


class TestPyCompoundUnchanged:
    """Dict/var/None branches keep binding through the worklist."""

    def test_dict_var_bind(self):
        assert _stage0_match({"a": {"var": "x"}}, {"a": 1}) == {"x": 1}

    def test_gate3_type_list_pattern_omits_type(self):
        result = _stage0_match(
            {"head": {"var": "x"}, "tail": {"var": "y"}},
            {"head": 1, "tail": None, "_type": "list"},
        )
        assert result == {"x": 1, "y": None}

    def test_none_matches_none(self):
        assert _stage0_match(None, None) == {}
        assert _stage0_match(None, 5) is NO_MATCH


# ===========================================================================
# Python AST shape — reduction thesis
# ===========================================================================

class TestPyAstShape:
    def test_no_scalar_isinstance_in_stage0_match(self):
        """No isinstance(x, bool/int/float/str) — scalar dispatch collapsed."""
        tree = _stage0_match_ast()
        for subject_name, type_names in _isinstance_calls(tree):
            offenders = SCALAR_TYPE_NAMES.intersection(type_names)
            assert not offenders, (
                f"_stage0_match still has scalar isinstance({subject_name}, "
                f"{sorted(offenders)}) — scalar dispatch must collapse to a content hash"
            )

    def test_has_content_hash_equality(self):
        """The collapsed scalar branch compares mu_hash_cached(pattern) vs input_value."""
        assert _has_content_hash_equality(_stage0_match_ast()), (
            "_stage0_match must compare mu_hash_cached(pattern) == mu_hash_cached(input_value)"
        )

    def test_exactly_one_input_side_list_fail_close(self):
        """Exactly one isinstance(input_value, list); none on pattern."""
        tree = _stage0_match_ast()
        input_side = 0
        for subject_name, type_names in _isinstance_calls(tree):
            if "list" not in type_names:
                continue
            assert subject_name != "pattern", (
                "_stage0_match has a forbidden pattern-side isinstance(pattern, list)"
            )
            assert subject_name == "input_value", (
                f"_stage0_match has isinstance({subject_name}, list) on an unexpected subject"
            )
            input_side += 1
        assert input_side == 1, (
            f"_stage0_match must have exactly one input-side list fail-close, found {input_side}"
        )

    def test_validity_guard_present(self):
        """is_mu guards both pattern and input_value before the content hash."""
        guarded = set(_call_names_with_arg(_stage0_match_ast(), "is_mu"))
        assert {"pattern", "input_value"}.issubset(guarded), (
            f"_stage0_match must guard the content hash with is_mu(pattern) and "
            f"is_mu(input_value); found is_mu on {sorted(guarded)}"
        )


# ===========================================================================
# JS behavior + source shape (parity)
# ===========================================================================

class TestJsParity:
    def test_js_behavior_matches_python(self):
        results = _run_js_stage0(
            "tag('int_eq', 5, 5);\n"
            "tag('int_neq', 5, 6);\n"
            "tag('str_eq', 'a', 'a');\n"
            "tag('bool_int', true, 1);\n"
            "tag('signed_zero', 0, -0);\n"
            "tag('same_pos_zero', 0, 0);\n"
            "tag('raw_list_eq', [1, 2], [1, 2]);\n"
            "tag('empty_list', [], []);\n"
            "tag('scalar_rawlist_in', 5, [1, 2]);\n"
            "tag('scalar_undefined', 5, undefined);\n"
            "tag('undefined_pat', undefined, 5);\n"
            "tag('scalar_rawobj_in', 5, {a: 1});\n"
            "tag('null_null', null, null);\n"
            "tag('null_int', null, 5);\n"
        )
        expected = {
            "int_eq": "MATCH",
            "int_neq": "NO_MATCH",
            "str_eq": "MATCH",
            "bool_int": "NO_MATCH",
            "signed_zero": "NO_MATCH",      # authorized delta, parity with Python
            "same_pos_zero": "MATCH",
            "raw_list_eq": "NO_MATCH",
            "empty_list": "NO_MATCH",
            "scalar_rawlist_in": "NO_MATCH",   # no THROW
            "scalar_undefined": "NO_MATCH",    # no THROW
            "undefined_pat": "NO_MATCH",       # no THROW
            "scalar_rawobj_in": "NO_MATCH",    # no THROW
            "null_null": "MATCH",
            "null_int": "NO_MATCH",
        }
        assert results == expected, f"JS stage0Match divergence: {results}"

    def test_js_no_throw_on_invalid_inputs(self):
        """Invalid/non-Mu inputs must yield NO_MATCH, never THROW."""
        results = _run_js_stage0(
            "tag('rawlist', 5, [1, 2]);\n"
            "tag('undef', 5, undefined);\n"
            "tag('rawobj', 5, {a: 1});\n"
        )
        for label, verdict in results.items():
            assert verdict == "NO_MATCH", f"{label}: expected NO_MATCH, got {verdict}"

    def test_js_source_has_content_hash_and_guard(self):
        body = _stage0_js_source()
        assert "muHashCached(pattern)" in body and "muHashCached(input)" in body, (
            "stage0Match must use muHashCached(pattern) === muHashCached(input)"
        )
        assert "isValidMu(pattern)" in body and "isValidMu(input)" in body, (
            "stage0Match must guard the content hash with isValidMu(pattern) && isValidMu(input)"
        )

    def test_js_keeps_input_side_array_guard_no_pattern_side(self):
        body = _stage0_js_source()
        assert "Array.isArray(input)" in body, (
            "stage0Match must KEEP the input-side Array.isArray(input) fail-close"
        )
        assert "Array.isArray(pattern)" not in body, (
            "stage0Match must NOT have a pattern-side Array.isArray(pattern) branch"
        )
