"""
Grounding tests for ast_police_js.sh - verifies JS AST patterns actually get caught.

These tests create temporary JS files with known violations and verify ast_police_js.sh
detects them. Without these tests, the script could have broken regex patterns.

Created based on grounding agent finding (2026-01-30): ast_police_js.sh at 0% grounded.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "checks" / "ast_police_js.sh"


def run_ast_police_on_code(code: str) -> subprocess.CompletedProcess:
    """Write JS code to temp file and run ast_police_js.sh on it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        f.flush()
        return subprocess.run(
            ["bash", str(SCRIPT), f.name],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestAstPoliceDetectsIndirectEval:
    """Verify ast_police_js.sh catches indirect eval patterns."""

    def test_detects_window_bracket_eval(self):
        """ast_police_js.sh must fail when window['eval'] found."""
        code = "const fn = window['eval'];"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on window['eval']"
        assert "eval" in result.stdout.lower()

    def test_detects_globalThis_bracket_eval(self):
        """ast_police_js.sh must fail when globalThis['eval'] found."""
        code = "const fn = globalThis['eval'];"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on globalThis['eval']"

    def test_detects_comma_operator_eval(self):
        """ast_police_js.sh must fail when (0,eval) found."""
        code = "const result = (0, eval)('1+1');"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on (0,eval)"

    def test_detects_this_bracket_eval(self):
        """ast_police_js.sh must fail when this['eval'] found."""
        code = "const fn = this['eval'];"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on this['eval']"


class TestAstPoliceDetectsStringConcatenation:
    """Verify ast_police_js.sh catches string concatenation bypasses."""

    def test_detects_eval_concatenation(self):
        """ast_police_js.sh must fail when 'ev'+'al' pattern found."""
        code = "const fn = window['ev' + 'al'];"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on string concat for eval"

    def test_detects_setTimeout_concatenation(self):
        """ast_police_js.sh must fail when 'set'+'Timeout' pattern found."""
        code = "const fn = window['set' + 'Timeout'];"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on string concat for setTimeout"


class TestAstPoliceDetectsFunctionConstructor:
    """Verify ast_police_js.sh catches Function constructor variants."""

    def test_detects_new_function(self):
        """ast_police_js.sh must fail when new Function() found."""
        code = "const fn = new Function('x', 'return x');"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on new Function()"

    def test_detects_function_prototype_constructor(self):
        """ast_police_js.sh must fail when Function.prototype.constructor found."""
        code = "const fn = Function.prototype.constructor;"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Function.prototype.constructor"

    def test_detects_constructor_call(self):
        """ast_police_js.sh must fail when .constructor( found."""
        code = "const fn = (() => {}).constructor('return 1')();"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on .constructor()"


class TestAstPoliceDetectsScopeManipulation:
    """Verify ast_police_js.sh catches scope manipulation patterns."""

    def test_detects_with_statement(self):
        """ast_police_js.sh must fail when with() found."""
        code = "with (obj) { x = 1; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on with()"
        assert "with" in result.stdout.lower()

    def test_detects_debugger(self):
        """ast_police_js.sh must fail when debugger statement found."""
        code = "function test() { debugger; return 1; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on debugger"


class TestAstPoliceDetectsNonStrictMode:
    """Verify ast_police_js.sh catches non-strict mode patterns."""

    def test_detects_arguments_callee(self):
        """ast_police_js.sh must fail when arguments.callee found."""
        code = "function f() { return arguments.callee; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on arguments.callee"

    def test_detects_arguments_caller(self):
        """ast_police_js.sh must fail when arguments.caller found."""
        code = "function f() { return arguments.caller; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on arguments.caller"


class TestAstPoliceDetectsPrototypePollution:
    """Verify ast_police_js.sh catches prototype pollution patterns."""

    def test_detects_proto(self):
        """ast_police_js.sh must fail when __proto__ found."""
        code = "obj.__proto__ = malicious;"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on __proto__"

    def test_detects_setPrototypeOf(self):
        """ast_police_js.sh must fail when Object.setPrototypeOf found."""
        code = "Object.setPrototypeOf(obj, proto);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Object.setPrototypeOf"


class TestAstPoliceDetectsReflection:
    """Verify ast_police_js.sh catches Reflect API patterns."""

    def test_detects_reflect_construct(self):
        """ast_police_js.sh must fail when Reflect.construct found."""
        code = "const obj = Reflect.construct(Array, [1, 2, 3]);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Reflect.construct"

    def test_detects_reflect_apply(self):
        """ast_police_js.sh must fail when Reflect.apply found."""
        code = "const result = Reflect.apply(fn, null, args);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Reflect.apply"

    def test_detects_reflect_get(self):
        """ast_police_js.sh must fail when Reflect.get found (eval bypass)."""
        code = "const e = Reflect.get(globalThis, 'eval');"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Reflect.get"


class TestAstPoliceDetectsDynamicImport:
    """Verify ast_police_js.sh catches dynamic import/require patterns."""

    def test_detects_dynamic_import(self):
        """ast_police_js.sh must fail when import() found."""
        code = "const mod = await import('./module.js');"
        result = run_ast_police_on_code(code)
        # This should fail for both import() and await
        assert result.returncode != 0, "Should fail on dynamic import()"

    def test_detects_dynamic_require(self):
        """ast_police_js.sh must fail when require(variable) found."""
        code = "const mod = require(moduleName);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on dynamic require"


class TestAstPoliceDetectsAsync:
    """Verify ast_police_js.sh catches async patterns."""

    def test_detects_async_function(self):
        """ast_police_js.sh must fail when async function found."""
        code = "async function fetchData() { return data; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on async function"

    def test_detects_await(self):
        """ast_police_js.sh must fail when await found."""
        code = "const data = await fetch(url);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on await"

    def test_detects_generator_function(self):
        """ast_police_js.sh must fail when generator function found."""
        code = "function* gen() { yield 1; yield 2; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on generator function"

    def test_detects_yield(self):
        """ast_police_js.sh must fail when yield found."""
        code = "function* gen() { yield 1; }"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on yield"


class TestAstPoliceDetectsProxy:
    """Verify ast_police_js.sh catches Proxy usage."""

    def test_detects_new_proxy(self):
        """ast_police_js.sh must fail when new Proxy found."""
        code = "const proxy = new Proxy(target, handler);"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on new Proxy"


class TestAstPoliceDetectsWeakCollections:
    """Verify ast_police_js.sh catches WeakMap/WeakSet usage."""

    def test_detects_weakmap(self):
        """ast_police_js.sh must fail when new WeakMap found."""
        code = "const wm = new WeakMap();"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on new WeakMap"

    def test_detects_weakset(self):
        """ast_police_js.sh must fail when new WeakSet found."""
        code = "const ws = new WeakSet();"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on new WeakSet"


class TestAstPoliceDetectsSymbol:
    """Verify ast_police_js.sh catches dangerous Symbol patterns."""

    def test_detects_symbol_for(self):
        """ast_police_js.sh must fail when Symbol.for found."""
        code = "const sym = Symbol.for('key');"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Symbol.for"

    def test_detects_symbol_iterator(self):
        """ast_police_js.sh must fail when Symbol.iterator found."""
        code = "obj[Symbol.iterator] = function() {};"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Symbol.iterator"

    def test_detects_symbol_as_key(self):
        """ast_police_js.sh must fail when [Symbol. used as key found."""
        code = "obj[Symbol.toStringTag] = 'Custom';"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on Symbol as key"

    def test_allows_sentinel_symbol(self):
        """ast_police_js.sh must allow const FOO = Symbol('FOO') for sentinels."""
        code = "const NO_MATCH = Symbol('NO_MATCH');"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, f"Sentinel Symbol should be allowed: {result.stdout}"


class TestAstPoliceCleanCode:
    """Verify clean JS code passes ast_police_js.sh."""

    def test_clean_code_passes(self):
        """Normal JS code should pass."""
        code = '''
function add(a, b) {
    return a + b;
}

const result = add(1, 2);
console.log(result);
'''
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, f"Clean code should pass: {result.stdout}"

    def test_allowed_patterns_pass(self):
        """Allowed patterns (JSON, Object, Array methods) should pass."""
        code = '''
const data = JSON.parse('{"a": 1}');
const keys = Object.keys(data);
const values = Object.values(data);
const mapped = keys.map(k => k.toUpperCase());
const filtered = values.filter(v => v > 0);
const reduced = values.reduce((a, b) => a + b, 0);
'''
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, f"Allowed patterns should pass: {result.stdout}"
