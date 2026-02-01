#!/bin/bash
# The "Dumb" Linter - Catches dangerous Python patterns.
# A regex never hallucinates. Run this BEFORE waking up the AI agents.
#
# Philosophy: Block the dangerous stuff, allow the necessary scaffolding.
# Add "# CONTRABAND_OK: reason" to whitelist specific lines.

set -e

RCX_DIR="${1:-./rcx_pi}"
EXIT_CODE=0

echo "Scanning $RCX_DIR for contraband..."
echo ""

# Exclude experimental and CLI directories
EXCLUDE="--exclude-dir=worlds --exclude-dir=prototypes --exclude-dir=core"
# Exclude CLI files (they need subprocess/dynamic imports for error handling)
EXCLUDE_FILES="--exclude=*_cli.py --exclude=cli_*.py --exclude=programs.py"

# 1. Ban 'eval(' - NO EXCEPTIONS
EVAL_HITS=$(grep -rn "\beval(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$EVAL_HITS" ]; then
    echo "CRITICAL: Found 'eval()'. Code injection risk:"
    echo "$EVAL_HITS"
    echo ""
    EXIT_CODE=1
fi

# 2. Ban 'exec(' - NO EXCEPTIONS
EXEC_HITS=$(grep -rn "\bexec(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$EXEC_HITS" ]; then
    echo "CRITICAL: Found 'exec()'. Code injection risk:"
    echo "$EXEC_HITS"
    echo ""
    EXIT_CODE=1
fi

# 3. Ban 'globals()' and 'locals()' (Scope Leakage)
GLOBALS_HITS=$(grep -rn "\bglobals(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$GLOBALS_HITS" ]; then
    echo "CRITICAL: Found 'globals()'. Scope leakage:"
    echo "$GLOBALS_HITS"
    echo ""
    EXIT_CODE=1
fi

LOCALS_HITS=$(grep -rn "\blocals(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$LOCALS_HITS" ]; then
    echo "CRITICAL: Found 'locals()'. Scope leakage:"
    echo "$LOCALS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 4. Ban dangerous dunder access (Metaclass Smuggling + Code Object Introspection)
# __class__, __bases__, __mro__, __subclasses__ - metaclass traversal
# __code__, __closure__, __globals__ - function introspection (can extract secrets)
DUNDER_HITS=$(grep -rn "__class__\|__bases__\|__mro__\|__subclasses__\|__code__\|__closure__\|__globals__" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$DUNDER_HITS" ]; then
    echo "CRITICAL: Found dangerous dunder access:"
    echo "$DUNDER_HITS"
    echo ""
    EXIT_CODE=1
fi

# 5. Ban 'pickle' (Arbitrary Code Execution)
PICKLE_HITS=$(grep -rn "import pickle\|from pickle" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$PICKLE_HITS" ]; then
    echo "CRITICAL: Found 'pickle'. Arbitrary code execution risk:"
    echo "$PICKLE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 6. Ban 'compile(' except re.compile (Code generation)
COMPILE_HITS=$(grep -rn "\bcompile(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "re.compile" | grep -v "CONTRABAND_OK" || true)
if [ -n "$COMPILE_HITS" ]; then
    echo "CRITICAL: Found 'compile()'. Code generation risk:"
    echo "$COMPILE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 7. Ban actual lambda USAGE (not just the word in comments)
# Look for "= lambda" or ": lambda" or "(lambda" patterns that indicate actual lambda expressions
# Catches: x = lambda:, x = lambda x:, (lambda x: x), [lambda: 1]
LAMBDA_HITS=$(grep -rn "=lambda\|= lambda\|:lambda\|: lambda\|(lambda\|\[lambda" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "key=lambda" | grep -v "CONTRABAND_OK" || true)
if [ -n "$LAMBDA_HITS" ]; then
    echo "CRITICAL: Found lambda expression (not in sort key):"
    echo "$LAMBDA_HITS"
    echo ""
    EXIT_CODE=1
fi

# 8. Ban getattr(__builtins__) - Dynamic builtin access bypass
# This catches attempts to access eval/exec via getattr to bypass direct checks
GETATTR_BUILTINS_HITS=$(grep -rn "getattr.*__builtins__\|__builtins__\[" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$GETATTR_BUILTINS_HITS" ]; then
    echo "CRITICAL: Found dynamic __builtins__ access (eval/exec bypass attempt):"
    echo "$GETATTR_BUILTINS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 9. Ban 'import builtins' - Alternative dynamic builtin access bypass
# This catches attempts to access eval/exec via the builtins module
IMPORT_BUILTINS_HITS=$(grep -rn "import builtins\|from builtins import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$IMPORT_BUILTINS_HITS" ]; then
    echo "CRITICAL: Found 'import builtins' (eval/exec bypass attempt):"
    echo "$IMPORT_BUILTINS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 10. Ban '__import__(' - Dynamic import bypasses static import analysis
DUNDER_IMPORT_HITS=$(grep -rn "\b__import__(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$DUNDER_IMPORT_HITS" ]; then
    echo "CRITICAL: Found '__import__()'. Dynamic import bypass:"
    echo "$DUNDER_IMPORT_HITS"
    echo ""
    EXIT_CODE=1
fi

# 11. Ban 'vars(' - Equivalent to globals()/locals() but often missed
VARS_HITS=$(grep -rn "\bvars(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$VARS_HITS" ]; then
    echo "CRITICAL: Found 'vars()'. Scope leakage (like globals/locals):"
    echo "$VARS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 12. Ban 'setattr(' and 'delattr(' - Dynamic attribute manipulation
SETATTR_HITS=$(grep -rn "\bsetattr(\|\bdelattr(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SETATTR_HITS" ]; then
    echo "CRITICAL: Found 'setattr/delattr'. Dynamic attribute manipulation:"
    echo "$SETATTR_HITS"
    echo ""
    EXIT_CODE=1
fi

# 13. Ban 'marshal' - Code serialization like pickle
MARSHAL_HITS=$(grep -rn "import marshal\|from marshal" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$MARSHAL_HITS" ]; then
    echo "CRITICAL: Found 'marshal'. Code serialization risk:"
    echo "$MARSHAL_HITS"
    echo ""
    EXIT_CODE=1
fi

# 14. Ban 'ctypes' - Memory manipulation
CTYPES_HITS=$(grep -rn "import ctypes\|from ctypes" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$CTYPES_HITS" ]; then
    echo "CRITICAL: Found 'ctypes'. Memory manipulation risk:"
    echo "$CTYPES_HITS"
    echo ""
    EXIT_CODE=1
fi

# 15. Ban 'subprocess' - Command execution
SUBPROCESS_HITS=$(grep -rn "import subprocess\|from subprocess" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SUBPROCESS_HITS" ]; then
    echo "CRITICAL: Found 'subprocess'. Command execution risk:"
    echo "$SUBPROCESS_HITS"
    echo ""
    EXIT_CODE=1
fi

# 16. Ban 'os.system', 'os.popen', 'os.spawn', 'os.exec*', 'os.fork' - Direct command/process execution
OS_EXEC_HITS=$(grep -rn "os\.system\|os\.popen\|os\.spawn\|os\.exec\|os\.fork" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$OS_EXEC_HITS" ]; then
    echo "CRITICAL: Found 'os.system/popen/spawn/exec/fork'. Command execution risk:"
    echo "$OS_EXEC_HITS"
    echo ""
    EXIT_CODE=1
fi

# 17. Ban 'sys.modules' manipulation - Module cache hijacking
# Also catch getattr(sys, 'modules') bypass
SYS_MODULES_HITS=$(grep -rn "sys\.modules\[\|getattr.*sys.*modules" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SYS_MODULES_HITS" ]; then
    echo "CRITICAL: Found 'sys.modules' access. Module cache manipulation:"
    echo "$SYS_MODULES_HITS"
    echo ""
    EXIT_CODE=1
fi

# 18. Ban 'importlib' - Dynamic module loading
IMPORTLIB_HITS=$(grep -rn "import importlib\|from importlib\|importlib\.import_module" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$IMPORTLIB_HITS" ]; then
    echo "CRITICAL: Found 'importlib'. Dynamic module loading:"
    echo "$IMPORTLIB_HITS"
    echo ""
    EXIT_CODE=1
fi

# 19. Ban 'threading' and 'multiprocessing' - Concurrency breaks determinism
THREADING_HITS=$(grep -rn "import threading\|from threading\|import multiprocessing\|from multiprocessing" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$THREADING_HITS" ]; then
    echo "CRITICAL: Found 'threading/multiprocessing'. Concurrency breaks determinism:"
    echo "$THREADING_HITS"
    echo ""
    EXIT_CODE=1
fi

# 20. Ban 'asyncio' - Async runtime breaks determinism
ASYNCIO_HITS=$(grep -rn "import asyncio\|from asyncio" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$ASYNCIO_HITS" ]; then
    echo "CRITICAL: Found 'asyncio'. Async runtime breaks determinism:"
    echo "$ASYNCIO_HITS"
    echo ""
    EXIT_CODE=1
fi

# 21. Ban 'socket' - Network access
SOCKET_HITS=$(grep -rn "import socket\|from socket" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SOCKET_HITS" ]; then
    echo "CRITICAL: Found 'socket'. Network access:"
    echo "$SOCKET_HITS"
    echo ""
    EXIT_CODE=1
fi

# 22. Ban 'base64' and 'codecs' - Encoding can hide contraband patterns
# Defense-in-depth: Even though exec/eval are blocked, encoded code could bypass pattern matching
BASE64_HITS=$(grep -rn "import base64\|from base64\|base64\.b64decode\|from codecs import\|codecs\.decode" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$BASE64_HITS" ]; then
    echo "CRITICAL: Found 'base64/codecs'. Encoding can hide contraband:"
    echo "$BASE64_HITS"
    echo ""
    EXIT_CODE=1
fi

# 23. Ban 'chr(' and 'ord(' - Can bypass string pattern detection
# Attack vector: chr(101)+chr(118)+chr(97)+chr(108) = "eval"
# Defense-in-depth: Block character-level string construction (9-agent adversary finding 2026-01-30)
CHR_HITS=$(grep -rn "\bchr(\|\bord(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$CHR_HITS" ]; then
    echo "CRITICAL: Found 'chr()/ord()'. Can bypass pattern detection via char-by-char construction:"
    echo "$CHR_HITS"
    echo ""
    EXIT_CODE=1
fi

# 24. Ban 'operator.attrgetter', 'operator.itemgetter', 'operator.methodcaller' - Indirect access
# Attack vector: operator.attrgetter("__dict__")(__builtins__).get("eval")
# Defense-in-depth: Block operator module introspection (9-agent adversary finding 2026-01-30)
OPERATOR_HITS=$(grep -rn "operator\.attrgetter\|operator\.itemgetter\|operator\.methodcaller" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$OPERATOR_HITS" ]; then
    echo "CRITICAL: Found 'operator.attrgetter/itemgetter/methodcaller'. Indirect access bypass:"
    echo "$OPERATOR_HITS"
    echo ""
    EXIT_CODE=1
fi

# 25. Ban 'bytes(' and 'bytearray(' - Alternative to chr() for string construction
# Attack vector: bytes([101, 118, 97, 108]).decode() = "eval"
# Defense-in-depth: Block byte-level string construction (Round 4 adversary finding 2026-01-30)
BYTES_HITS=$(grep -rn "\bbytes(\|\bbytearray(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$BYTES_HITS" ]; then
    echo "CRITICAL: Found 'bytes()/bytearray()'. String construction bypass:"
    echo "$BYTES_HITS"
    echo ""
    EXIT_CODE=1
fi

# 26. Ban 'import inspect' - Frame introspection bypasses scope protection
# Attack vector: inspect.currentframe().f_back.f_locals gives access to caller's scope
# Defense-in-depth: Block frame introspection (Round 4 adversary finding 2026-01-30)
INSPECT_HITS=$(grep -rn "import inspect\|from inspect" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$INSPECT_HITS" ]; then
    echo "CRITICAL: Found 'inspect' module. Frame introspection bypass:"
    echo "$INSPECT_HITS"
    echo ""
    EXIT_CODE=1
fi

# 27. Ban 'sys._getframe' - Direct frame access without importing inspect
# Attack vector: sys._getframe().f_globals gives access to global scope
# Defense-in-depth: Block frame access (Round 4 adversary finding 2026-01-30)
SYS_GETFRAME_HITS=$(grep -rn "sys\._getframe\|sys\._current_frames" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SYS_GETFRAME_HITS" ]; then
    echo "CRITICAL: Found 'sys._getframe'. Frame introspection bypass:"
    echo "$SYS_GETFRAME_HITS"
    echo ""
    EXIT_CODE=1
fi

# 28. Ban 'import types' - Can create code objects and functions from raw data
# Attack vector: types.FunctionType(types.CodeType(...), globals())
# Defense-in-depth: Block code object creation (Round 4 adversary finding 2026-01-30)
TYPES_HITS=$(grep -rn "import types\|from types import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$TYPES_HITS" ]; then
    echo "CRITICAL: Found 'types' module. Code object creation bypass:"
    echo "$TYPES_HITS"
    echo ""
    EXIT_CODE=1
fi

# 29. Ban 'import gc' - Can traverse object graph to find builtins
# Attack vector: [obj for obj in gc.get_objects() if hasattr(obj, '__name__') and obj.__name__ == 'eval']
# Defense-in-depth: Block object graph traversal (Round 4 adversary finding 2026-01-30)
GC_HITS=$(grep -rn "import gc\|from gc import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$GC_HITS" ]; then
    echo "CRITICAL: Found 'gc' module. Object graph traversal bypass:"
    echo "$GC_HITS"
    echo ""
    EXIT_CODE=1
fi

# 30. Ban '.from_bytes' and '.fromhex' - Alternative to bytes() for string construction
# Attack vector: int.from_bytes(b'eval', 'big') -> number -> construct string indirectly
# Attack vector: bytes.fromhex('6576616c').decode() = "eval"
# Defense-in-depth: Block byte-level string construction bypasses (Round 5 adversary finding 2026-01-30)
FROMBYTES_HITS=$(grep -rn "\.from_bytes\|\.fromhex" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$FROMBYTES_HITS" ]; then
    echo "CRITICAL: Found '.from_bytes/.fromhex'. String construction bypass:"
    echo "$FROMBYTES_HITS"
    echo ""
    EXIT_CODE=1
fi

# 31. Ban 'functools.partial' - Can smuggle lambda semantics via partial application
# Attack vector: partial(eval, {'__builtins__': {}}) - delayed function binding
# Defense-in-depth: Block lambda-equivalent constructs (Round 6 verifier finding 2026-01-30)
PARTIAL_HITS=$(grep -rn "functools\.partial\|from functools import.*partial" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$PARTIAL_HITS" ]; then
    echo "CRITICAL: Found 'functools.partial'. Lambda smuggling bypass:"
    echo "$PARTIAL_HITS"
    echo ""
    EXIT_CODE=1
fi

# 32. Ban 'struct' module - Low-level binary packing can construct arbitrary bytes
# Attack vector: struct.pack('4s', b'eval') -> binary construction
# Defense-in-depth: Block binary manipulation (Round 6 adversary finding 2026-01-30)
STRUCT_HITS=$(grep -rn "import struct\|from struct import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$STRUCT_HITS" ]; then
    echo "CRITICAL: Found 'struct' module. Binary manipulation bypass:"
    echo "$STRUCT_HITS"
    echo ""
    EXIT_CODE=1
fi

# 33. Ban 'array' module - Efficient binary arrays can manipulate bytes
# Attack vector: array.array('b', [101,118,97,108]).tobytes() = b'eval'
# Defense-in-depth: Block binary array construction (Round 6 adversary finding 2026-01-30)
ARRAY_HITS=$(grep -rn "import array\|from array import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$ARRAY_HITS" ]; then
    echo "CRITICAL: Found 'array' module. Binary array bypass:"
    echo "$ARRAY_HITS"
    echo ""
    EXIT_CODE=1
fi

# 34. Ban 'cffi' - Foreign function interface allows C code execution
# Attack vector: from cffi import FFI; ffi.dlopen() bypasses all Python sandboxing
# Defense-in-depth: Block memory manipulation via C (Round 7 adversary finding 2026-01-30)
CFFI_HITS=$(grep -rn "import cffi\|from cffi import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$CFFI_HITS" ]; then
    echo "CRITICAL: Found 'cffi' module. C code execution bypass:"
    echo "$CFFI_HITS"
    echo ""
    EXIT_CODE=1
fi

# 35. Ban 'shelve' - Pickle-based persistence (uses pickle internally)
# Attack vector: shelve.open('malicious.db') executes arbitrary code on load
# Defense-in-depth: Block indirect pickle (Round 7 adversary finding 2026-01-30)
SHELVE_HITS=$(grep -rn "import shelve\|from shelve import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SHELVE_HITS" ]; then
    echo "CRITICAL: Found 'shelve' module. Indirect pickle bypass:"
    echo "$SHELVE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 36. Ban sys.settrace/sys.setprofile - Execution hooks
# Attack vector: sys.settrace(lambda *args: evil()) injects code at every line
# Defense-in-depth: Block execution hook injection (Round 7 adversary finding 2026-01-30)
TRACE_HITS=$(grep -rn "sys\.settrace\|sys\.setprofile" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$TRACE_HITS" ]; then
    echo "CRITICAL: Found sys.settrace/setprofile. Execution hook bypass:"
    echo "$TRACE_HITS"
    echo ""
    EXIT_CODE=1
fi

# 37. Ban 'memoryview' - Direct memory access
# Attack vector: memoryview(bytearray(b'eval')) can manipulate bytes directly
# Defense-in-depth: Block byte-level memory manipulation (Round 7 adversary finding 2026-01-30)
MEMVIEW_HITS=$(grep -rn "\bmemoryview(" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$MEMVIEW_HITS" ]; then
    echo "CRITICAL: Found 'memoryview'. Memory manipulation bypass:"
    echo "$MEMVIEW_HITS"
    echo ""
    EXIT_CODE=1
fi

# 38. Ban 'mmap' - Memory-mapped files
# Attack vector: import mmap; m = mmap.mmap(...) gives direct memory access
# Defense-in-depth: Block memory-mapped file manipulation (Round 7 adversary finding 2026-01-30)
MMAP_HITS=$(grep -rn "import mmap\|from mmap import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$MMAP_HITS" ]; then
    echo "CRITICAL: Found 'mmap' module. Memory-mapped file bypass:"
    echo "$MMAP_HITS"
    echo ""
    EXIT_CODE=1
fi

# 39. Ban 'atexit' - Exit handlers
# Attack vector: import atexit; atexit.register(evil) deferred execution
# Defense-in-depth: Block deferred code execution (Round 7 adversary finding 2026-01-30)
ATEXIT_HITS=$(grep -rn "import atexit\|from atexit import" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$ATEXIT_HITS" ]; then
    echo "CRITICAL: Found 'atexit' module. Deferred execution bypass:"
    echo "$ATEXIT_HITS"
    echo ""
    EXIT_CODE=1
fi

# 40. Ban signal handlers - Can hijack execution
# Attack vector: import signal; signal.signal(signal.SIGALRM, evil) execution hook
# Defense-in-depth: Block signal handler injection (Round 7 adversary finding 2026-01-30)
SIGNAL_HITS=$(grep -rn "import signal\|signal\.signal" "$RCX_DIR" --include="*.py" $EXCLUDE $EXCLUDE_FILES 2>/dev/null | grep -v "CONTRABAND_OK" || true)
if [ -n "$SIGNAL_HITS" ]; then
    echo "CRITICAL: Found 'signal' module. Signal handler bypass:"
    echo "$SIGNAL_HITS"
    echo ""
    EXIT_CODE=1
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "No contraband syntax found in core RCX code."
    echo ""
    echo "Excluded from scan:"
    echo "  - worlds/, prototypes/, core/ directories"
    echo "  - *_cli.py files (CLI wrappers)"
    echo ""
    echo "ALLOWED patterns (not contraband):"
    echo "  - lambda in sort keys: .sort(key=lambda ...)"
    echo "  - set() for key comparison or cycle detection"
    echo "  - id() for cycle detection"
    echo "  - Lines marked with # CONTRABAND_OK"
else
    echo "CONTRABAND DETECTED - Fix before running AI agents."
    exit 1
fi
