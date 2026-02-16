"""
Grounding tests for contraband.sh - verifies the script actually catches violations.

These tests create temporary files with known violations and verify contraband.sh
detects them. Without these tests, contraband.sh could have broken patterns and
we wouldn't know until a human manually tests them.

Created based on 7-agent review finding (2026-01-30): security checks had no grounding tests.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRABAND_SCRIPT = REPO_ROOT / "tools" / "checks" / "linters" / "contraband.sh"


def run_contraband_on_code(code: str) -> subprocess.CompletedProcess:
    """Write code to temp file and run contraband.sh on it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal package structure
        pkg_dir = Path(tmpdir) / "test_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        test_file = pkg_dir / "test_code.py"
        test_file.write_text(code)

        return subprocess.run(
            ["bash", str(CONTRABAND_SCRIPT), str(pkg_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestContrabanDetectsEval:
    """Verify contraband.sh catches eval() calls."""

    def test_detects_direct_eval(self):
        """contraband.sh must fail when eval() found."""
        code = 'result = eval("1 + 1")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on eval()"
        assert "eval" in result.stdout.lower()

    def test_allows_eval_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = 'result = eval("1 + 1")  # CONTRABAND_OK: test case'
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsExec:
    """Verify contraband.sh catches exec() calls."""

    def test_detects_direct_exec(self):
        """contraband.sh must fail when exec() found."""
        code = 'exec("print(1)")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on exec()"
        assert "exec" in result.stdout.lower()

    def test_allows_exec_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = 'exec("x = 1")  # CONTRABAND_OK: test case'
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsLambda:
    """Verify contraband.sh catches lambda expressions (not in sort keys)."""

    def test_detects_lambda_assignment(self):
        """contraband.sh must fail when lambda assigned to variable."""
        code = "fn = lambda x: x + 1"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on lambda assignment"
        assert "lambda" in result.stdout.lower()

    def test_allows_lambda_in_sort_key(self):
        """Lambda in sort key is allowed (idiomatic Python)."""
        code = "data.sort(key=lambda x: x.name)"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "Lambda in sort key should be allowed"

    def test_allows_lambda_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass lambda check."""
        code = "fn = lambda x: x  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsGlobals:
    """Verify contraband.sh catches globals()/locals() calls."""

    def test_detects_globals(self):
        """contraband.sh must fail when globals() found."""
        code = "g = globals()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on globals()"
        assert "globals" in result.stdout.lower()

    def test_detects_locals(self):
        """contraband.sh must fail when locals() found."""
        code = "l = locals()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on locals()"
        assert "locals" in result.stdout.lower()


class TestContrabanDetectsDunders:
    """Verify contraband.sh catches dangerous dunder access."""

    def test_detects_class_dunder(self):
        """contraband.sh must fail when __class__ accessed."""
        code = "x.__class__.__bases__"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __class__"
        assert "__class__" in result.stdout or "dunder" in result.stdout.lower()

    def test_detects_mro_dunder(self):
        """contraband.sh must fail when __mro__ accessed."""
        code = "x.__class__.__mro__"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __mro__"

    def test_detects_code_dunder(self):
        """contraband.sh must fail when __code__ accessed."""
        code = "fn.__code__.co_code"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __code__"
        assert "__code__" in result.stdout or "dunder" in result.stdout.lower()

    def test_detects_closure_dunder(self):
        """contraband.sh must fail when __closure__ accessed."""
        code = "fn.__closure__[0].cell_contents"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __closure__"

    def test_detects_globals_dunder(self):
        """contraband.sh must fail when __globals__ accessed."""
        code = "fn.__globals__['secret']"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __globals__"


class TestContrabanDetectsPickle:
    """Verify contraband.sh catches pickle imports."""

    def test_detects_pickle_import(self):
        """contraband.sh must fail when pickle imported."""
        code = "import pickle"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on pickle import"
        assert "pickle" in result.stdout.lower()

    def test_detects_pickle_from_import(self):
        """contraband.sh must fail when from pickle import used."""
        code = "from pickle import loads"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from pickle import"


class TestContrabanDetectsCompile:
    """Verify contraband.sh catches compile() calls."""

    def test_detects_compile(self):
        """contraband.sh must fail when compile() found."""
        code = 'code = compile("x = 1", "<string>", "exec")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on compile()"
        assert "compile" in result.stdout.lower()

    def test_allows_re_compile(self):
        """re.compile() is allowed (regex, not code)."""
        code = "import re\npattern = re.compile(r'\\d+')"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "re.compile should be allowed"


class TestContrabanDetectsGetattrBuiltins:
    """Verify contraband.sh catches dynamic __builtins__ access."""

    def test_detects_getattr_builtins(self):
        """contraband.sh must fail when getattr(__builtins__) found."""
        code = 'fn = getattr(__builtins__, "eval")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on getattr(__builtins__)"
        assert "__builtins__" in result.stdout

    def test_detects_builtins_subscript(self):
        """contraband.sh must fail when __builtins__[...] found."""
        code = 'fn = __builtins__["eval"]'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __builtins__[...]"


class TestContrabanDetectsImportBuiltins:
    """Verify contraband.sh catches import builtins (eval/exec bypass)."""

    def test_detects_import_builtins(self):
        """contraband.sh must fail when import builtins found."""
        code = "import builtins\nfn = builtins.eval"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import builtins"
        assert "builtins" in result.stdout.lower()

    def test_detects_from_builtins_import(self):
        """contraband.sh must fail when from builtins import used."""
        code = "from builtins import eval as safe_eval"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from builtins import"

    def test_allows_import_builtins_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import builtins  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsDunderImport:
    """Verify contraband.sh catches __import__() calls."""

    def test_detects_dunder_import(self):
        """contraband.sh must fail when __import__() found."""
        code = 'mod = __import__("os")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __import__()"
        assert "__import__" in result.stdout

    def test_allows_dunder_import_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = 'mod = __import__("os")  # CONTRABAND_OK: test case'
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsVars:
    """Verify contraband.sh catches vars() calls."""

    def test_detects_vars(self):
        """contraband.sh must fail when vars() found."""
        code = "v = vars()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on vars()"
        assert "vars" in result.stdout.lower()

    def test_allows_vars_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "v = vars()  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsSetattr:
    """Verify contraband.sh catches setattr/delattr calls."""

    def test_detects_setattr(self):
        """contraband.sh must fail when setattr() found."""
        code = "setattr(obj, 'x', 1)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on setattr()"
        assert "setattr" in result.stdout.lower() or "delattr" in result.stdout.lower()

    def test_detects_delattr(self):
        """contraband.sh must fail when delattr() found."""
        code = "delattr(obj, 'x')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on delattr()"
        assert "setattr" in result.stdout.lower() or "delattr" in result.stdout.lower()

    def test_allows_setattr_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "setattr(obj, 'x', 1)  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsMarshal:
    """Verify contraband.sh catches marshal imports."""

    def test_detects_marshal_import(self):
        """contraband.sh must fail when marshal imported."""
        code = "import marshal"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on marshal import"
        assert "marshal" in result.stdout.lower()

    def test_detects_marshal_from_import(self):
        """contraband.sh must fail when from marshal import used."""
        code = "from marshal import loads"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from marshal import"


class TestContrabanDetectsCtypes:
    """Verify contraband.sh catches ctypes imports."""

    def test_detects_ctypes_import(self):
        """contraband.sh must fail when ctypes imported."""
        code = "import ctypes"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on ctypes import"
        assert "ctypes" in result.stdout.lower()

    def test_detects_ctypes_from_import(self):
        """contraband.sh must fail when from ctypes import used."""
        code = "from ctypes import c_int"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from ctypes import"


class TestContrabanDetectsSubprocess:
    """Verify contraband.sh catches subprocess imports."""

    def test_detects_subprocess_import(self):
        """contraband.sh must fail when subprocess imported."""
        code = "import subprocess"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on subprocess import"
        assert "subprocess" in result.stdout.lower()

    def test_detects_subprocess_from_import(self):
        """contraband.sh must fail when from subprocess import used."""
        code = "from subprocess import run"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from subprocess import"


class TestContrabanDetectsOsExec:
    """Verify contraband.sh catches os.system/popen/spawn calls."""

    def test_detects_os_system(self):
        """contraband.sh must fail when os.system() found."""
        code = "import os\nos.system('ls')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.system()"
        assert "os.system" in result.stdout or "popen" in result.stdout or "spawn" in result.stdout

    def test_detects_os_popen(self):
        """contraband.sh must fail when os.popen() found."""
        code = "import os\nos.popen('ls')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.popen()"

    def test_detects_os_spawn(self):
        """contraband.sh must fail when os.spawn*() found."""
        code = "import os\nos.spawnl(os.P_WAIT, '/bin/ls')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.spawn*()"


class TestContrabanDetectsSysModules:
    """Verify contraband.sh catches sys.modules manipulation."""

    def test_detects_sys_modules_subscript(self):
        """contraband.sh must fail when sys.modules[] found."""
        code = "import sys\nsys.modules['os'] = None"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on sys.modules[]"
        assert "sys.modules" in result.stdout

    def test_detects_getattr_sys_modules_bypass(self):
        """contraband.sh must fail when getattr(sys, 'modules') found."""
        code = "import sys\nmods = getattr(sys, 'modules')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on getattr(sys, 'modules')"
        assert "sys.modules" in result.stdout or "modules" in result.stdout.lower()

    def test_allows_sys_modules_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import sys\nsys.modules['os']  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsImportlib:
    """Verify contraband.sh catches importlib usage."""

    def test_detects_importlib_import(self):
        """contraband.sh must fail when importlib imported."""
        code = "import importlib"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on importlib import"
        assert "importlib" in result.stdout.lower()

    def test_detects_importlib_from_import(self):
        """contraband.sh must fail when from importlib import used."""
        code = "from importlib import import_module"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from importlib import"

    def test_detects_importlib_import_module(self):
        """contraband.sh must fail when importlib.import_module used."""
        code = "import importlib\nimportlib.import_module('os')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on importlib.import_module()"


class TestContrabanDetectsThreading:
    """Verify contraband.sh catches threading/multiprocessing."""

    def test_detects_threading_import(self):
        """contraband.sh must fail when threading imported."""
        code = "import threading"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on threading import"
        assert "threading" in result.stdout.lower() or "multiprocessing" in result.stdout.lower()

    def test_detects_multiprocessing_import(self):
        """contraband.sh must fail when multiprocessing imported."""
        code = "import multiprocessing"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on multiprocessing import"

    def test_detects_threading_from_import(self):
        """contraband.sh must fail when from threading import used."""
        code = "from threading import Thread"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from threading import"


class TestContrabanDetectsAsyncio:
    """Verify contraband.sh catches asyncio."""

    def test_detects_asyncio_import(self):
        """contraband.sh must fail when asyncio imported."""
        code = "import asyncio"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on asyncio import"
        assert "asyncio" in result.stdout.lower()

    def test_detects_asyncio_from_import(self):
        """contraband.sh must fail when from asyncio import used."""
        code = "from asyncio import run"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from asyncio import"


class TestContrabanDetectsSocket:
    """Verify contraband.sh catches socket."""

    def test_detects_socket_import(self):
        """contraband.sh must fail when socket imported."""
        code = "import socket"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on socket import"
        assert "socket" in result.stdout.lower()

    def test_detects_socket_from_import(self):
        """contraband.sh must fail when from socket import used."""
        code = "from socket import socket"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from socket import"


class TestContrabanDetectsOsExecVariants:
    """Verify contraband.sh catches all os.exec* variants."""

    def test_detects_os_execl(self):
        """contraband.sh must fail when os.execl found."""
        code = "import os\nos.execl('/bin/ls', 'ls')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.execl"

    def test_detects_os_execv(self):
        """contraband.sh must fail when os.execv found."""
        code = "import os\nos.execv('/bin/ls', ['ls'])"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.execv"

    def test_detects_os_fork(self):
        """contraband.sh must fail when os.fork found."""
        code = "import os\nos.fork()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on os.fork"


class TestContrabanDetectsLambdaVariants:
    """Verify contraband.sh catches lambda variants without spaces."""

    def test_detects_lambda_no_space(self):
        """contraband.sh must fail when lambda has no space after =."""
        code = "fn=lambda x:x"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on lambda without space"

    def test_detects_lambda_in_parens(self):
        """contraband.sh must fail when lambda in parentheses."""
        code = "(lambda x: x)(1)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on (lambda ...)"

    def test_detects_lambda_in_list(self):
        """contraband.sh must fail when lambda in list literal."""
        code = "fns = [lambda x: x]"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on [lambda ...]"


class TestContrabanDetectsBase64:
    """Verify contraband.sh catches base64/codecs (encoding can hide contraband)."""

    def test_detects_base64_import(self):
        """contraband.sh must fail when base64 imported."""
        code = "import base64"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on base64 import"
        # Must specifically mention base64 (not codecs - that's a different violation)
        assert "base64" in result.stdout.lower(), f"Output should mention base64: {result.stdout}"

    def test_detects_base64_from_import(self):
        """contraband.sh must fail when from base64 import used."""
        code = "from base64 import b64decode"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from base64 import"

    def test_detects_base64_b64decode_call(self):
        """contraband.sh must fail when base64.b64decode called."""
        code = "data = base64.b64decode(encoded)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on base64.b64decode"

    def test_detects_codecs_import(self):
        """contraband.sh must fail when from codecs import used."""
        code = "from codecs import decode"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from codecs import"

    def test_detects_codecs_decode_call(self):
        """contraband.sh must fail when codecs.decode called."""
        code = "data = codecs.decode(encoded, 'base64')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on codecs.decode"

    def test_allows_base64_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import base64  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsChrOrd:
    """Verify contraband.sh catches chr()/ord() bypass attempts (9-agent review 2026-01-30)."""

    def test_detects_chr_call(self):
        """contraband.sh must fail when chr() found."""
        code = "fn_name = chr(101) + chr(118) + chr(97) + chr(108)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on chr()"
        assert "chr" in result.stdout.lower()

    def test_detects_ord_call(self):
        """contraband.sh must fail when ord() found."""
        code = "code_point = ord('e')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on ord()"
        assert "ord" in result.stdout.lower() or "chr" in result.stdout.lower()

    def test_allows_chr_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "x = chr(65)  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsOperator:
    """Verify contraband.sh catches operator module bypass (9-agent review 2026-01-30)."""

    def test_detects_attrgetter(self):
        """contraband.sh must fail when operator.attrgetter found."""
        code = "import operator\nget_dict = operator.attrgetter('__dict__')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on operator.attrgetter"
        assert "operator" in result.stdout.lower() or "attrgetter" in result.stdout.lower()

    def test_detects_itemgetter(self):
        """contraband.sh must fail when operator.itemgetter found."""
        code = "import operator\nget_eval = operator.itemgetter('eval')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on operator.itemgetter"

    def test_allows_operator_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import operator\nget = operator.attrgetter('x')  # CONTRABAND_OK: test"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsMethodcaller:
    """Verify contraband.sh catches operator.methodcaller bypass (Round 4 adversary 2026-01-30)."""

    def test_detects_methodcaller(self):
        """contraband.sh must fail when operator.methodcaller found."""
        code = "import operator\ncall_it = operator.methodcaller('__getattribute__', '__dict__')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on operator.methodcaller"
        assert "methodcaller" in result.stdout.lower() or "operator" in result.stdout.lower()


class TestContrabanDetectsBytesConstruction:
    """Verify contraband.sh catches bytes/bytearray string construction (Round 4 adversary 2026-01-30)."""

    def test_detects_bytes_call(self):
        """contraband.sh must fail when bytes() used for string construction."""
        code = "fn_name = bytes([101, 118, 97, 108]).decode()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on bytes()"
        assert "bytes" in result.stdout.lower()

    def test_detects_bytearray_call(self):
        """contraband.sh must fail when bytearray() used for string construction."""
        code = "fn_name = bytearray([101, 118, 97, 108]).decode()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on bytearray()"
        assert "bytearray" in result.stdout.lower() or "bytes" in result.stdout.lower()

    def test_allows_bytes_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "data = bytes([1, 2, 3])  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsInspect:
    """Verify contraband.sh catches inspect module bypass (Round 4 adversary 2026-01-30)."""

    def test_detects_inspect_import(self):
        """contraband.sh must fail when inspect imported."""
        code = "import inspect"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import inspect"
        assert "inspect" in result.stdout.lower()

    def test_detects_inspect_from_import(self):
        """contraband.sh must fail when from inspect import used."""
        code = "from inspect import currentframe"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from inspect import"

    def test_allows_inspect_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import inspect  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsSysGetframe:
    """Verify contraband.sh catches sys._getframe bypass (Round 4 adversary 2026-01-30)."""

    def test_detects_sys_getframe(self):
        """contraband.sh must fail when sys._getframe found."""
        code = "import sys\nframe = sys._getframe()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on sys._getframe"
        assert "_getframe" in result.stdout.lower() or "frame" in result.stdout.lower()

    def test_detects_sys_current_frames(self):
        """contraband.sh must fail when sys._current_frames found."""
        code = "import sys\nframes = sys._current_frames()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on sys._current_frames"

    def test_allows_sys_getframe_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "frame = sys._getframe()  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsTypes:
    """Verify contraband.sh catches types module bypass (Round 4 adversary 2026-01-30)."""

    def test_detects_types_import(self):
        """contraband.sh must fail when types imported."""
        code = "import types"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import types"
        assert "types" in result.stdout.lower()

    def test_detects_types_from_import(self):
        """contraband.sh must fail when from types import used."""
        code = "from types import FunctionType"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from types import"

    def test_allows_types_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import types  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsGc:
    """Verify contraband.sh catches gc module bypass (Round 4 adversary 2026-01-30)."""

    def test_detects_gc_import(self):
        """contraband.sh must fail when gc imported."""
        code = "import gc"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import gc"
        assert "gc" in result.stdout.lower()

    def test_detects_gc_from_import(self):
        """contraband.sh must fail when from gc import used."""
        code = "from gc import get_objects"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from gc import"

    def test_allows_gc_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import gc  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsFrombytes:
    """Verify contraband.sh catches from_bytes/fromhex bypass (Round 5 adversary 2026-01-30)."""

    def test_detects_int_from_bytes(self):
        """contraband.sh must fail when int.from_bytes found."""
        code = "num = int.from_bytes(b'eval', 'big')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on int.from_bytes"
        assert "from_bytes" in result.stdout.lower() or "fromhex" in result.stdout.lower()

    def test_detects_bytes_fromhex(self):
        """contraband.sh must fail when bytes.fromhex found."""
        code = "data = bytes.fromhex('6576616c').decode()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on bytes.fromhex"
        assert "fromhex" in result.stdout.lower() or "from_bytes" in result.stdout.lower()

    def test_allows_frombytes_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "num = int.from_bytes(b'x', 'big')  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsFunctoolsPartial:
    """Verify contraband.sh catches functools.partial bypass (Round 6 verifier 2026-01-30)."""

    def test_detects_functools_partial(self):
        """contraband.sh must fail when functools.partial found."""
        code = "import functools\ndelayed = functools.partial(print, 'test')"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on functools.partial"
        assert "partial" in result.stdout.lower()

    def test_detects_partial_from_import(self):
        """contraband.sh must fail when from functools import partial used."""
        code = "from functools import partial"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from functools import partial"

    def test_allows_partial_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "from functools import partial  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsStruct:
    """Verify contraband.sh catches struct module bypass (Round 6 adversary 2026-01-30)."""

    def test_detects_struct_import(self):
        """contraband.sh must fail when struct imported."""
        code = "import struct"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import struct"
        assert "struct" in result.stdout.lower()

    def test_detects_struct_from_import(self):
        """contraband.sh must fail when from struct import used."""
        code = "from struct import pack"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from struct import"

    def test_allows_struct_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import struct  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsArray:
    """Verify contraband.sh catches array module bypass (Round 6 adversary 2026-01-30)."""

    def test_detects_array_import(self):
        """contraband.sh must fail when array imported."""
        code = "import array"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import array"
        assert "array" in result.stdout.lower()

    def test_detects_array_from_import(self):
        """contraband.sh must fail when from array import used."""
        code = "from array import array"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from array import"

    def test_allows_array_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import array  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsCffi:
    """Verify contraband.sh catches cffi module (Round 7 adversary 2026-01-30)."""

    def test_detects_cffi_import(self):
        """contraband.sh must fail when cffi imported."""
        code = "import cffi"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import cffi"
        assert "cffi" in result.stdout.lower()

    def test_detects_cffi_from_import(self):
        """contraband.sh must fail when from cffi import used."""
        code = "from cffi import FFI"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from cffi import"

    def test_allows_cffi_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import cffi  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsShelve:
    """Verify contraband.sh catches shelve module (Round 7 adversary 2026-01-30)."""

    def test_detects_shelve_import(self):
        """contraband.sh must fail when shelve imported."""
        code = "import shelve"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import shelve"
        assert "shelve" in result.stdout.lower()

    def test_detects_shelve_from_import(self):
        """contraband.sh must fail when from shelve import used."""
        code = "from shelve import open"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from shelve import"

    def test_allows_shelve_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import shelve  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsSettrace:
    """Verify contraband.sh catches sys.settrace/setprofile (Round 7 adversary 2026-01-30)."""

    def test_detects_sys_settrace(self):
        """contraband.sh must fail when sys.settrace found."""
        code = "import sys\nsys.settrace(tracer)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on sys.settrace"
        assert "settrace" in result.stdout.lower() or "setprofile" in result.stdout.lower()

    def test_detects_sys_setprofile(self):
        """contraband.sh must fail when sys.setprofile found."""
        code = "import sys\nsys.setprofile(profiler)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on sys.setprofile"

    def test_allows_settrace_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "sys.settrace(tracer)  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsMemoryview:
    """Verify contraband.sh catches memoryview (Round 7 adversary 2026-01-30)."""

    def test_detects_memoryview(self):
        """contraband.sh must fail when memoryview found."""
        code = "mv = memoryview(bytearray(b'test'))"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on memoryview"
        assert "memoryview" in result.stdout.lower()

    def test_allows_memoryview_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "mv = memoryview(b'test')  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsMmap:
    """Verify contraband.sh catches mmap module (Round 7 adversary 2026-01-30)."""

    def test_detects_mmap_import(self):
        """contraband.sh must fail when mmap imported."""
        code = "import mmap"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import mmap"
        assert "mmap" in result.stdout.lower()

    def test_detects_mmap_from_import(self):
        """contraband.sh must fail when from mmap import used."""
        code = "from mmap import mmap"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from mmap import"

    def test_allows_mmap_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import mmap  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsAtexit:
    """Verify contraband.sh catches atexit module (Round 7 adversary 2026-01-30)."""

    def test_detects_atexit_import(self):
        """contraband.sh must fail when atexit imported."""
        code = "import atexit"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import atexit"
        assert "atexit" in result.stdout.lower()

    def test_detects_atexit_from_import(self):
        """contraband.sh must fail when from atexit import used."""
        code = "from atexit import register"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from atexit import"

    def test_allows_atexit_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import atexit  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsSignal:
    """Verify contraband.sh catches signal module (Round 7 adversary 2026-01-30)."""

    def test_detects_signal_import(self):
        """contraband.sh must fail when signal imported."""
        code = "import signal"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import signal"
        assert "signal" in result.stdout.lower()

    def test_detects_signal_signal(self):
        """contraband.sh must fail when signal.signal used."""
        code = "signal.signal(signal.SIGALRM, handler)"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on signal.signal"

    def test_allows_signal_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import signal  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestCleanCodePasses:
    """Verify clean code passes contraband check."""

    def test_clean_code_passes(self):
        """Normal Python code should pass."""
        code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

result = add(1, 2)
'''
        result = run_contraband_on_code(code)
        assert result.returncode == 0, f"Clean code should pass: {result.stdout}"
