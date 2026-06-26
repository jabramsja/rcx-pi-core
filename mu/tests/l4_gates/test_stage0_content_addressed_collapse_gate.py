"""Stage 0 StructuralNumbers numeric cutover — Gate Tests.

Wave: stage4-loop-struct-2026-06-22
Task: [NEXT-CODEX-POST-REDTEAM]
Authorization: FOUNDER_OVERRIDE:stage4-loop-struct-2026-06-22
L4 class: L4_STRUCTURAL (host-debt reduction).

Proves the Stage 4 StructuralNumbers matcher-domain cutover:

  - Host ``int``/``float`` leaves fail closed in the real Python
    ``_stage0_match`` and JS ``stage0Match`` paths, including variable sites.
  - StructuralNumbers numerals route through dict/object matching and bind
    structurally in both substrates.
  - Non-numeric bool/string leaves retain the collapsed content-addressed
    ``mu_hash_cached`` / ``muHashCached`` equality until their later
    structuralization wave.
  - Exactly ONE input-side raw-list fail-close per substrate restores NO_MATCH
    for raw lists (Python ``isinstance(input_value, list)``; JS
    ``Array.isArray(input)``). Pattern-side list dispatch stays forbidden.
  - Invalid/unsupported host values (tuple, non-Mu) fall through to NO_MATCH
    WITHOUT reaching assert_mu/mu_hash_cached/muHashCached (no raise).

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

ZERO = {"_num": None}
ONE = {"_num": {"xH": None}}


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
# Python behavior — numeric cutover plus non-numeric scalar equality
# ===========================================================================

class TestPyNumericCutoverAndScalarHash:
    def test_host_numeric_leaves_fail_closed(self):
        assert _stage0_match(5, 5) is NO_MATCH
        assert _stage0_match(3.14, 3.14) is NO_MATCH
        assert _stage0_match(0.0, 0.0) is NO_MATCH
        assert _stage0_match(-0.0, -0.0) is NO_MATCH

    def test_host_numeric_variable_binding_fails_closed(self):
        assert _stage0_match({"var": "x"}, 5) is NO_MATCH
        assert _stage0_match({"var": "x"}, {"a": 5}) is NO_MATCH
        assert _stage0_match({"a": {"var": "x"}}, {"a": 5}) is NO_MATCH
        assert _stage0_match({"a": 5}, {"a": 5}) is NO_MATCH

    def test_nonnumeric_equal_scalars_match(self):
        assert _stage0_match("a", "a") == {}
        assert _stage0_match(True, True) == {}

    def test_unequal_scalars_no_match(self):
        assert _stage0_match("a", "b") is NO_MATCH
        assert _stage0_match(True, False) is NO_MATCH

    def test_cross_type_no_match_via_cutover_or_content_hash(self):
        assert _stage0_match(5, 5.0) is NO_MATCH
        assert _stage0_match(True, 1) is NO_MATCH
        assert _stage0_match(1, True) is NO_MATCH
        assert _stage0_match(False, 0) is NO_MATCH

    def test_structural_numbers_route_through_dict_matching(self):
        assert _stage0_match(ZERO, ZERO) == {}
        assert _stage0_match({"outer": {"_num": {"var": "n"}}}, {"outer": ONE}) == {
            "n": {"xH": None}
        }

class TestPySignedZeroCutover:
    """All host float zero leaves fail closed after StructuralNumbers cutover."""

    def test_signed_zero_no_match(self):
        assert _stage0_match(0.0, -0.0) is NO_MATCH
        assert _stage0_match(-0.0, 0.0) is NO_MATCH


class TestPyRawListFailClose:
    """Raw lists never match at a scalar/non-dict site (input-side fail-close)."""

    def test_equal_raw_lists_no_match(self):
        assert _stage0_match([1, 2], [1, 2]) is NO_MATCH
        assert _stage0_match([], []) is NO_MATCH

    def test_scalar_pattern_raw_list_input_no_match(self):
        assert _stage0_match("leaf", [1, 2]) is NO_MATCH

    def test_raw_list_pattern_scalar_input_no_match(self):
        # Pattern-side raw list is NOT dispatched on; it simply fails to match.
        assert _stage0_match(["leaf"], "leaf") is NO_MATCH


class TestPyInvalidHostValueFailClose:
    """Unsupported/non-Mu host values return NO_MATCH WITHOUT raising."""

    def test_tuple_pattern_and_input_no_match_no_raise(self):
        assert _stage0_match(("a", "b"), ("a", "b")) is NO_MATCH

    def test_scalar_pattern_tuple_input_no_match_no_raise(self):
        assert _stage0_match("leaf", ("a", "b")) is NO_MATCH

    def test_set_input_no_match_no_raise(self):
        assert _stage0_match("leaf", {"a", "b"}) is NO_MATCH

    def test_custom_object_input_no_match_no_raise(self):
        assert _stage0_match("leaf", object()) is NO_MATCH


class TestPyCompoundUnchanged:
    """Dict/var/None branches keep binding through the worklist."""

    def test_dict_var_bind(self):
        assert _stage0_match({"a": {"var": "x"}}, {"a": ONE}) == {"x": ONE}

    def test_gate3_type_list_pattern_omits_type(self):
        result = _stage0_match(
            {"head": {"var": "x"}, "tail": {"var": "y"}},
            {"head": ONE, "tail": None, "_type": "list"},
        )
        assert result == {"x": ONE, "y": None}

    def test_none_matches_none(self):
        assert _stage0_match(None, None) == {}
        assert _stage0_match(None, ONE) is NO_MATCH


# ===========================================================================
# Python AST shape — reduction thesis
# ===========================================================================

class TestPyAstShape:
    def test_numeric_fail_closed_behavior_is_real_matcher_path(self):
        """Host numerics fail through _stage0_match itself, not a private test hook."""
        assert _stage0_match({"var": "x"}, 1) is NO_MATCH
        assert _stage0_match({"_num": {"var": "n"}}, ONE) == {"n": {"xH": None}}

    def test_active_vm_matcher_paths_reject_host_numeric_leaves(self):
        """Host numerics fail through active Stage0 VM/Mu matcher paths."""
        from rcx_pi.selfhost.match_mu import match_mu
        from rcx_pi.selfhost.stage0_vm import stage0_vm_run
        from rcx_pi.selfhost.step_mu import apply_mu, step_mu

        bundle = json.loads(
            (REPO_ROOT / "mu" / "stage0" / "compiled" / "match_v2.compiled.v1.json").read_text()
        )
        state = {"match": {"pattern": {"var": "x"}, "value": 1}, "_match_ctx": None}
        vm_result = stage0_vm_run(bundle, state)

        assert vm_result["steps"] == []
        assert vm_result["root"] == state
        assert match_mu({"var": "x"}, 1) is NO_MATCH
        assert apply_mu({"pattern": {"var": "x"}, "body": "matched"}, 1) is NO_MATCH
        assert step_mu([{"pattern": {"var": "x"}, "body": "matched"}], 1) == 1

    def test_active_vm_matcher_paths_accept_structural_numerals(self):
        """StructuralNumbers numerals still bind through active VM/Mu paths."""
        from rcx_pi.selfhost.match_mu import match_mu
        from rcx_pi.selfhost.stage0_vm import stage0_vm_run
        from rcx_pi.selfhost.step_mu import apply_mu, step_mu

        bundle = json.loads(
            (REPO_ROOT / "mu" / "stage0" / "compiled" / "match_v2.compiled.v1.json").read_text()
        )
        state = {"match": {"pattern": {"var": "x"}, "value": ONE}, "_match_ctx": None}
        vm_result = stage0_vm_run(bundle, state)

        assert vm_result["root"]["_mode"] == "match_done"
        assert vm_result["root"]["_status"] == "success"
        assert match_mu({"var": "x"}, ONE) == {"x": ONE}
        assert apply_mu({"pattern": {"var": "x"}, "body": {"var": "x"}}, ONE) == ONE
        assert step_mu([{"pattern": {"var": "x"}, "body": {"var": "x"}}], ONE) == ONE

    def test_has_content_hash_equality(self):
        """The remaining non-numeric scalar branch compares content hashes."""
        assert _has_content_hash_equality(_stage0_match_ast()), (
            "_stage0_match must compare mu_hash_cached(pattern) == mu_hash_cached(input_value)"
        )

    def test_exactly_one_input_side_list_fail_close(self):
        """Exactly one top-level isinstance(input_value, list); none on pattern."""
        tree = _stage0_match_ast()
        input_side = 0
        for subject_name, type_names in _isinstance_calls(tree):
            if "list" not in type_names:
                continue
            assert subject_name != "pattern", (
                "_stage0_match has a forbidden pattern-side isinstance(pattern, list)"
            )
            if subject_name == "candidate":
                continue
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
            "tag('float_eq', 3.14, 3.14);\n"
            "tag('str_eq', 'a', 'a');\n"
            "tag('bool_eq', true, true);\n"
            "tag('bool_int', true, 1);\n"
            "tag('signed_zero', 0, -0);\n"
            "tag('same_pos_zero', 0, 0);\n"
            "tag('struct_zero', {_num: null}, {_num: null});\n"
            "tag('struct_one_var', {_num: {var: 'n'}}, {_num: {xH: null}});\n"
            "tag('nested_num_var', {var: 'x'}, {a: 5});\n"
            "const b = stage0Match({outer: {_num: {var: 'n'}}}, {outer: {_num: {xH: null}}});\n"
            "results['struct_nested_binding'] = (b === NO_MATCH) ? 'NO_MATCH' : JSON.stringify(b.n);\n"
            "tag('raw_list_eq', [1, 2], [1, 2]);\n"
            "tag('empty_list', [], []);\n"
            "tag('scalar_rawlist_in', 'leaf', [1, 2]);\n"
            "tag('scalar_undefined', 'leaf', undefined);\n"
            "tag('undefined_pat', undefined, 'leaf');\n"
            "tag('scalar_rawobj_in', 'leaf', {a: 'b'});\n"
            "tag('null_null', null, null);\n"
            "tag('null_int', null, 5);\n"
        )
        expected = {
            "int_eq": "NO_MATCH",
            "int_neq": "NO_MATCH",
            "float_eq": "NO_MATCH",
            "str_eq": "MATCH",
            "bool_eq": "MATCH",
            "bool_int": "NO_MATCH",
            "signed_zero": "NO_MATCH",
            "same_pos_zero": "NO_MATCH",
            "struct_zero": "MATCH",
            "struct_one_var": "MATCH",
            "nested_num_var": "NO_MATCH",
            "struct_nested_binding": "{\"xH\":null}",
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

    def test_js_active_vm_matcher_paths_reject_host_numeric_leaves(self):
        script = """
        const fs = require('fs');
        const path = require('path');
        const { stage0VmRun } = require('./mu/host/js/core/stage0_vm');
        const { stepKernel } = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');
        function trust(v) {
          if (Array.isArray(v)) return muContainers.list(v.map(trust));
          if (v !== null && typeof v === 'object') {
            return muContainers.record(Object.keys(v).map(k => [k, trust(v[k])]));
          }
          return v;
        }
        const compiledDir = path.join(process.cwd(), 'mu', 'stage0', 'compiled');
        const kernelBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'kernel_v1.compiled.v1.json'), 'utf8'));
        const matchBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'match_v2.compiled.v1.json'), 'utf8'));
        const substBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'subst_v2.compiled.v1.json'), 'utf8'));
        const vmConfig = { kernelBundle, bridgeBundle: null, matchBundle, substBundle };
        const directState = { match: { pattern: { var: 'x' }, value: 1 }, _match_ctx: null };
        const direct = stage0VmRun(matchBundle, directState);
        const legacyPacket = stepKernel(
          [], 1, [{ pattern: trust({ var: 'x' }), body: 'matched' }],
          { maxSteps: 10, vmConfig }
        );
        const meta = stepKernel(
          [], 1, [{ pattern: trust({ var: 'x' }), body: 'matched' }],
          { maxSteps: 10, vmConfig, returnMeta: true }
        );
        console.log(JSON.stringify({
          directSteps: direct.steps.length,
          directRoot: direct.root,
          stepResult: legacyPacket.result,
          metaOutput: meta.output,
          metaStall: meta.stall
        }));
        """
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
        )
        assert proc.returncode == 0, f"JS active matcher probe failed: {proc.stderr}"
        result = json.loads(proc.stdout.strip())
        assert result == {
            "directSteps": 0,
            "directRoot": {"match": {"pattern": {"var": "x"}, "value": 1}, "_match_ctx": None},
            "stepResult": 1,
            "metaOutput": 1,
            "metaStall": True,
        }

    def test_js_active_vm_matcher_paths_accept_structural_numerals(self):
        script = """
        const fs = require('fs');
        const path = require('path');
        const { stage0VmRun } = require('./mu/host/js/core/stage0_vm');
        const { stepKernel } = require('./mu/host/js/engine/kernel');
        const muContainers = require('./mu/host/js/core/container_factory');
        function trust(v) {
          if (Array.isArray(v)) return muContainers.list(v.map(trust));
          if (v !== null && typeof v === 'object') {
            return muContainers.record(Object.keys(v).map(k => [k, trust(v[k])]));
          }
          return v;
        }
        const compiledDir = path.join(process.cwd(), 'mu', 'stage0', 'compiled');
        const kernelBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'kernel_v1.compiled.v1.json'), 'utf8'));
        const matchBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'match_v2.compiled.v1.json'), 'utf8'));
        const substBundle = JSON.parse(fs.readFileSync(path.join(compiledDir, 'subst_v2.compiled.v1.json'), 'utf8'));
        const vmConfig = { kernelBundle, bridgeBundle: null, matchBundle, substBundle };
        const one = { _num: { xH: null } };
        const direct = stage0VmRun(matchBundle, { match: { pattern: { var: 'x' }, value: one }, _match_ctx: null });
        const meta = stepKernel(
          [], trust(one), [{ pattern: trust({ var: 'x' }), body: 'matched' }],
          { maxSteps: 10, vmConfig, returnMeta: true }
        );
        console.log(JSON.stringify({
          directMode: direct.root._mode,
          directStatus: direct.root._status,
          stepOutput: meta.output,
          stepStall: meta.stall
        }));
        """
        proc = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
        )
        assert proc.returncode == 0, f"JS structural matcher probe failed: {proc.stderr}"
        result = json.loads(proc.stdout.strip())
        assert result == {
            "directMode": "match_done",
            "directStatus": "success",
            "stepOutput": "matched",
            "stepStall": False,
        }

    def test_js_no_throw_on_invalid_inputs(self):
        """Invalid/non-Mu inputs must yield NO_MATCH, never THROW."""
        results = _run_js_stage0(
            "tag('rawlist', 'leaf', [1, 2]);\n"
            "tag('undef', 'leaf', undefined);\n"
            "tag('rawobj', 'leaf', {a: 'b'});\n"
        )
        for label, verdict in results.items():
            assert verdict == "NO_MATCH", f"{label}: expected NO_MATCH, got {verdict}"

    def test_js_source_has_content_hash_and_guard(self):
        body = _stage0_js_source()
        assert "muHashCached(pattern)" in body and "muHashCached(input)" in body, (
            "stage0Match must keep non-numeric muHashCached(pattern) === muHashCached(input)"
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
