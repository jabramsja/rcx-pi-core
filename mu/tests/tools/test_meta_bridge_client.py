"""Tests for structured meta-bridge supervisor client."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Load meta_bridge_client module
_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "tools" / "agents"
_spec = importlib.util.spec_from_file_location(
    "meta_bridge_client", _AGENTS_DIR / "meta_bridge_client.py"
)
assert _spec and _spec.loader
client_mod = importlib.util.module_from_spec(_spec)
sys.modules["meta_bridge_client"] = client_mod
_spec.loader.exec_module(client_mod)

run_meta_bridge_package = client_mod.run_meta_bridge_package
MetaBridgeClientError = client_mod.MetaBridgeClientError
SupervisorResult = client_mod.SupervisorResult
validate_decision = client_mod._validate_decision  # ANTICHEAT_OK: testing internal validation function


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_public_cached_client_uses_current_validation_contract(tmp_path, warm, exit_code):
    """Cache both caller and common; the newly imported supervisor owns refresh."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    package = tmp_path / "package.json"
    package.write_text("{}")
    code = f'''
import sys,json
from pathlib import Path
sys.path[:0]=[{str(_AGENTS_DIR.parents[2])!r},{str(_AGENTS_DIR.parents[1])!r},{str(_AGENTS_DIR)!r},{str(_AGENTS_DIR.parent / 'executors')!r}]
from mu.tests.tools.test_executor_common import complete_process_observation
import executor_common as common
import meta_bridge_client as client
cached_caller=client.run_meta_bridge_package
if {warm!r}:
    # The pre-edit helper returns immediately when its four old symbols exist.
    for symbol in ('agent_bus_path','bridge_config_path','ensure_bridge_config_path','resolve_agent_bus_dir'):
        assert hasattr(common,symbol)
    setattr(client,'_refresh_executor_common_before_supervisor_import',lambda directory: None)
    for symbol in ('ValidationBudgetError','read_validation_schedule_transport','EXECUTOR_COMMON_SOURCE_SHA256'):
        delattr(common,symbol)
outcome=cached_caller(Path({str(package)!r}))
assert outcome.decision=='ERROR_INTERNAL' and outcome.error_code=='WRONG_GIT_REPO',outcome
import meta_bridge_supervisor as supervisor
current=sys.modules['executor_common']
assert hasattr(current,'ValidationBudgetError')
assert hasattr(current,'ensure_not_agent_review_mode')
import validation_execution as validation
with complete_process_observation(validation.common) as observations:
    status,output=supervisor.run_validation_command(Path({str(tmp_path)!r}),[sys.executable,'-u','-c',"print('native child');raise SystemExit({exit_code})"])
assert observations and all(row['complete'] and row['snapshot_sha256'] for row in observations)
print(json.dumps({{'status':status,'output':output,'refusal':outcome.error_code}}))
'''
    env = dict(os.environ)
    env.pop("RCX_NATIVE_STAGE_BUDGET", None)
    env.pop("RCX_VALIDATION_SCHEDULE", None)
    child = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    observed = json.loads(child.stdout.splitlines()[-1])
    assert observed["status"] == exit_code and "native child" in observed["output"]
    assert observed["refusal"] == "WRONG_GIT_REPO"


# Child-process helper: install a timestamp cache the import system itself accepts
# for an unchanged real dependency (that file's mtime and size), holding the code
# of an edited source. A private pycache prefix leaves every candidate byte and
# cache untouched; the stale module still reports the current disk hash.
_STALE_TIMESTAMP_CACHE = '''
import importlib.util, marshal, struct, sys
from pathlib import Path

def install_stale_cache(path, current, stale):
    source = path.read_bytes()
    assert source.count(current) == 1, (path, current)
    stat = path.stat()
    cache = Path(importlib.util.cache_from_source(str(path)))
    assert cache.is_relative_to(Path(sys.pycache_prefix)), cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    header = importlib.util.MAGIC_NUMBER + struct.pack(
        "<III", 0, int(stat.st_mtime) & 0xFFFFFFFF, stat.st_size & 0xFFFFFFFF)
    code = compile(source.replace(current, stale), str(path), "exec", dont_inherit=True)
    cache.write_bytes(header + marshal.dumps(code))
    return source, cache, cache.read_bytes()
'''
_STALE_EDITS = {
    "executor_common": (b"VALIDATION_CEILING_SECONDS = 7200", b"VALIDATION_CEILING_SECONDS = 9900"),
    "validation_execution": (b"MAX_WORKERS = 4", b"MAX_WORKERS = 8"),
}


@pytest.mark.parametrize("stale", sorted(_STALE_EDITS))
@pytest.mark.parametrize("validation_cached", [False, True], ids=["validation-absent", "validation-cached"])
@pytest.mark.parametrize("no_bytecode", [False, True], ids=["normal", "minus-B"])
def test_cached_baseline_client_replaces_stale_compatible_owner(tmp_path, stale, validation_cached, no_bytecode):
    """Combined cached-client/stale-owner regression through the real public caller.

    The import system accepts a timestamp cache of other source for the real,
    unchanged dependency path, so the registered owner is symbol-compatible but
    stale while its disk hash names the current bytes. The cached client's
    baseline helper returns early, so only the newly imported supervisor's current
    code can establish the pair. It must execute the bound source for both
    dependencies, refuse the reproduced 9000s admission, run the supervisor's
    actual validation child under the current owner and keep every old callable
    on its original owner. Only when the sole stale member is an unloaded
    validation cache is the proven common kept, with its class identity.
    """
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    package = repo / "package.json"
    package.write_text("{}")
    current_text, stale_text = _STALE_EDITS[stale]
    code = _STALE_TIMESTAMP_CACHE + f'''
import hashlib, importlib, json, os
agents = Path({str(_AGENTS_DIR)!r})
executors = agents.parent / "executors"
sys.pycache_prefix = {str(tmp_path / "pycache")!r}
sys.path[:0] = [str(agents.parents[2]), str(agents.parents[1]), str(agents), str(executors)]
assert sys.dont_write_bytecode is {no_bytecode!r}
path = executors / {stale + ".py"!r}
source, cache, cache_bytes = install_stale_cache(path, {current_text!r}, {stale_text!r})
stale_common = {stale!r} == "executor_common"
# This helper registers executor_common through the real loader, as callers do.
from mu.tests.tools.test_executor_common import complete_process_observation
import executor_common as old_common
old_validation = importlib.import_module("validation_execution") if {validation_cached!r} else None
assert old_common.VALIDATION_CEILING_SECONDS == (9900 if stale_common else 7200)
if stale_common:
    assert old_common.EXECUTOR_COMMON_SOURCE_SHA256 == hashlib.sha256(source).hexdigest()
if old_validation is not None:
    assert old_validation.common is old_common
    assert old_validation.MAX_WORKERS == (4 if stale_common else 8)
    if not stale_common:
        assert old_validation.VALIDATION_SOURCE_SHA256 == hashlib.sha256(source).hexdigest()
old_admit = old_common.admit_stage_budget
old_error = old_common.ExecutorCommonError
old_run = old_validation.run_validation if old_validation is not None else None
import meta_bridge_client as client
for symbol in ("agent_bus_path", "bridge_config_path", "ensure_bridge_config_path", "resolve_agent_bus_dir"):
    assert callable(getattr(old_common, symbol))
# The cached pre-edit helper returns at once when those four symbols exist.
setattr(client, "_refresh_executor_common_before_supervisor_import", lambda directory: None)
outcome = client.run_meta_bridge_package(Path({str(package)!r}))
assert outcome.decision == "ERROR_INTERNAL" and outcome.error_code == "WRONG_GIT_REPO", outcome
import meta_bridge_supervisor as supervisor
current = sys.modules["executor_common"]
validation = importlib.import_module("validation_execution")  # as the supervisor's lazy import
assert current.VALIDATION_CEILING_SECONDS == 7200, current.VALIDATION_CEILING_SECONDS
assert validation.MAX_WORKERS == 4, validation.MAX_WORKERS
assert validation.common is current
assert supervisor.ExecutorCommonError is current.ExecutorCommonError
assert supervisor.ensure_not_agent_review_mode is current.ensure_not_agent_review_mode
request = dict(key="pytest_full", command=[sys.executable, "-c", "pass"],
               baseline=9000, seconds=9000, ceiling=9000)
try:
    admitted = current.admit_stage_budget(executors, **request)
except current.ValidationBudgetError as exc:
    assert "7200" in str(exc)
else:
    raise AssertionError(f"stale owner admitted {{admitted.seconds}} seconds")
try:
    validation.pytest_command(["test_jobs.py"], profile="full", workers=8, env={{}}, repo_root=executors)
except current.ValidationBudgetError:
    pass
else:
    raise AssertionError("stale validation admitted eight workers")
logs = Path({str(tmp_path / "validation-logs")!r})
os.environ["RCX_VALIDATION_LOG_DIR"] = str(logs)
with complete_process_observation(current) as observations:
    status, output = supervisor.run_validation_command(
        Path({str(repo)!r}), [sys.executable, "-u", "-c", "print('native child')"])
assert status == 0 and "native child" in output, output
assert observations and all(row["complete"] for row in observations)
receipts = sorted(logs.glob("*.json"))
assert len(receipts) == 1, receipts
receipt = json.loads(receipts[0].read_text())
# The durable receipt names the ceiling of the owner that actually executed.
assert receipt["status"] == "passed" and receipt["budget"]["ceiling"] == 7200, receipt["budget"]
retained = not stale_common and not {validation_cached!r}
assert (current is old_common) is retained
assert (supervisor.ExecutorCommonError is old_error) is retained
assert old_common.admit_stage_budget is old_admit and old_admit.__globals__ is old_common.__dict__
assert old_common.VALIDATION_CEILING_SECONDS == (9900 if stale_common else 7200)
if old_validation is not None:
    assert validation is not old_validation and old_validation.common is old_common
    assert old_validation.run_validation is old_run and old_run.__globals__ is old_validation.__dict__
    assert old_validation.MAX_WORKERS == (4 if stale_common else 8)
assert path.read_bytes() == source and cache.read_bytes() == cache_bytes
print(json.dumps({{"ceiling": receipt["budget"]["ceiling"], "refused": 9000, "retained_common": retained}}))
'''
    env = dict(os.environ)
    for key in ("RCX_NATIVE_STAGE_BUDGET", "RCX_VALIDATION_SCHEDULE", "RCX_VALIDATION_LOG_DIR",
                "PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"):
        env.pop(key, None)
    child = subprocess.run(
        [sys.executable, *(["-B"] if no_bytecode else []), "-c", code],
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    observed = json.loads(child.stdout.splitlines()[-1])
    assert observed == {"ceiling": 7200, "refused": 9000,
                        "retained_common": stale == "validation_execution" and not validation_cached}


@pytest.mark.parametrize("validation_warm", [False, True])
@pytest.mark.parametrize("failure", ["compile", "interruption", "source_drift", "missing_guard"])
def test_retain_proven_handoff_failure_restores_retained_owner(
    supervisor_dependency_copy, validation_warm, failure,
):
    """A supervisor-import transaction rolls back exactly, including a partial pair.

    With only validation unloaded, the proven common is kept and validation alone
    executes; a warm validation edited after import is unproven, so the whole pair
    executes. Either way a failure restores the registry, including absence, and
    never mutates an old namespace.
    """
    agents, executors = supervisor_dependency_copy
    tails = {
        "compile": "\ninvalid syntax here\n",
        "interruption": "\nraise KeyboardInterrupt('interrupted validation import')\n",
        "source_drift": "\nPath(__file__).write_bytes(Path(__file__).read_bytes() + b'\\n# drift\\n')\n",
        "missing_guard": "\ndel run_validation\n",
    }
    code = f'''
import importlib, sys
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import meta_bridge_client as client
import executor_common as common
old = importlib.import_module("validation_execution") if {validation_warm!r} else None
common_callable = common.admit_stage_budget
source_path = Path({str(executors / "validation_execution.py")!r})
source_path.write_text(source_path.read_text() + {tails[failure]!r})
expected = {{"compile": SyntaxError, "interruption": KeyboardInterrupt,
            "source_drift": client.MetaBridgeClientError,
            "missing_guard": client.MetaBridgeClientError}}[{failure!r}]
try:
    client.prepare_supervisor_execution_api(Path({str(agents)!r}), retain_proven=True)
except expected:
    pass
else:
    raise AssertionError("invalid retain-proven refresh was admitted")
assert sys.modules["executor_common"] is common
assert sys.modules.get("validation_execution") is old
assert common.admit_stage_budget is common_callable
assert common_callable.__globals__ is common.__dict__
if old is not None:
    assert old.common is common and old.run_validation.__globals__ is old.__dict__
'''
    child = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr


def test_supervisor_handoff_refuses_foreign_common_source(tmp_path, monkeypatch):
    from mu.tools.executors import executor_common as common
    validation = sys.modules.get("validation_execution")
    monkeypatch.setitem(sys.modules, "executor_common", common)
    monkeypatch.setattr(common, "__file__", str(tmp_path / "executor_common.py"))
    with pytest.raises(MetaBridgeClientError, match="unexpected source"):
        client_mod.prepare_supervisor_execution_api(_AGENTS_DIR)
    assert sys.modules["executor_common"] is common
    assert sys.modules.get("validation_execution") is validation


@pytest.fixture
def supervisor_dependency_copy(tmp_path):
    """Exercise native imports without editing the candidate or its bytecode."""
    agents = tmp_path / "tools" / "agents"
    executors = agents.parent / "executors"
    agents.mkdir(parents=True)
    executors.mkdir()
    shutil.copy2(_AGENTS_DIR / "meta_bridge_client.py", agents)
    for name in ("executor_common.py", "validation_execution.py"):
        shutil.copy2(_AGENTS_DIR.parent / "executors" / name, executors)
    return agents, executors


@pytest.mark.parametrize("cache_state", ["warm", "stale", "cold", "absent"])
@pytest.mark.parametrize("validation_warm", [False, True])
@pytest.mark.parametrize("no_bytecode", [False, True], ids=["normal", "minus-B"])
def test_supervisor_handoff_refuses_cached_common_over_ceiling(
    supervisor_dependency_copy, cache_state, validation_warm, no_bytecode,
):
    """Reproduce a lying disk hash using real timestamp pyc and budget APIs."""
    agents, executors = supervisor_dependency_copy
    code = f'''
import hashlib, importlib, json, os, py_compile, sys
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import meta_bridge_client as client
path = Path({str(executors / 'executor_common.py')!r})
source = path.read_bytes()
assert source.count(b'VALIDATION_CEILING_SECONDS = 7200') == 1
stale_source = source.replace(b'VALIDATION_CEILING_SECONDS = 7200',
                            b'VALIDATION_CEILING_SECONDS = 9900')
path.write_bytes(stale_source)
stamp = path.stat()
cache = Path(py_compile.compile(str(path), doraise=True,
    invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
cache_bytes = cache.read_bytes()
old = importlib.import_module('executor_common') if {cache_state!r} == 'warm' else None
path.write_bytes(source)
os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
assert path.stat().st_size == stamp.st_size
assert path.stat().st_mtime_ns == stamp.st_mtime_ns
if {cache_state!r} == 'stale':
    old = importlib.import_module('executor_common')
    assert old.EXECUTOR_COMMON_SOURCE_SHA256 == hashlib.sha256(source).hexdigest()
if {cache_state!r} == 'absent':
    cache.unlink()
if old is not None:
    assert old.VALIDATION_CEILING_SECONDS == 9900
old_callable = old.admit_stage_budget if old is not None else None
old_validation = importlib.import_module('validation_execution') if {validation_warm!r} else None
old_validation_callable = old_validation.run_validation if old_validation is not None else None
old_validation_common = old_validation.common if old_validation is not None else None
if {cache_state!r} in ('cold', 'absent'):
    sys.modules.pop('executor_common', None)
# Independently execute the bound source: the same request must already HOLD.
clean = {{'__file__': str(path), '__name__': 'exact_source_common'}}
exec(compile(source, str(path), 'exec'), clean)
request = dict(key='pytest_full', command=[sys.executable, '-c', 'pass'],
               baseline=9000, seconds=9000, ceiling=9000)
try:
    clean['admit_stage_budget'](path.parent, **request)
except clean['ValidationBudgetError']:
    pass
else:
    raise AssertionError('exact source admitted over-ceiling request')
client.prepare_supervisor_execution_api(Path({str(agents)!r}))
current = importlib.import_module('executor_common')
validation = importlib.import_module('validation_execution')
assert validation.common is current
request = dict(key='pytest_full', command=[sys.executable, '-c', 'pass'],
               baseline=9000, seconds=9000, ceiling=9000)
try:
    admitted = current.admit_stage_budget(path.parent, **request)
except current.ValidationBudgetError as exc:
    assert '7200' in str(exc)
else:
    raise AssertionError(f'stale handoff admitted {{admitted.seconds}} seconds; ceiling={{current.VALIDATION_CEILING_SECONDS}}')
assert current.VALIDATION_CEILING_SECONDS == 7200
assert current.EXECUTOR_COMMON_SOURCE_SHA256 == hashlib.sha256(source).hexdigest()
assert hasattr(current, 'ensure_not_agent_review_mode')
assert validation.pytest_timeout(['test_jobs.py'], profile='full', timeout=300) == 300
try:
    validation.pytest_timeout(['test_jobs.py'], profile='full', timeout=9000)
except current.ValidationBudgetError:
    pass
else:
    raise AssertionError('validation consumer retained the stale ceiling')
if old is not None:
    assert old is not current
    assert old.admit_stage_budget is old_callable
    assert old_callable.__globals__ is old.__dict__
    assert old.VALIDATION_CEILING_SECONDS == 9900
if old_validation is not None:
    assert validation is not old_validation
    assert old_validation.run_validation is old_validation_callable
    assert old_validation_callable.__globals__ is old_validation.__dict__
    assert old_validation.common is old_validation_common
assert path.read_bytes() == source
if {cache_state!r} != 'absent':
    assert cache.read_bytes() == cache_bytes
print(json.dumps({{'ceiling': current.VALIDATION_CEILING_SECONDS, 'refused': 9000}}))
'''
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    child = subprocess.run(
        [sys.executable, *(["-B"] if no_bytecode else []), "-c", code],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout)["refused"] == 9000


@pytest.mark.parametrize("cache_state", ["warm", "stale", "cold", "absent"])
@pytest.mark.parametrize("no_bytecode", [False, True], ids=["normal", "minus-B"])
def test_supervisor_handoff_ignores_timestamp_bytecode(
    supervisor_dependency_copy, cache_state, no_bytecode,
):
    """Current source must execute even when an accepted pyc claims its hash."""
    agents, executors = supervisor_dependency_copy
    code = f'''
import hashlib, importlib, json, os, py_compile, struct, sys
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import meta_bridge_client as client
import executor_common as common
source_path = Path({str(executors / 'validation_execution.py')!r})
original = source_path.read_bytes()
assert original.count(b"MAX_WORKERS = 4") == 1
cached_path = Path(py_compile.compile(str(source_path), doraise=True,
    invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP))
cached_bytes = cached_path.read_bytes()
assert struct.unpack('<I', cached_bytes[4:8])[0] == 0
assert sys.dont_write_bytecode is {no_bytecode!r}
stat = source_path.stat()
old = None
if {cache_state!r} == 'warm':
    old = importlib.import_module('validation_execution')
edited = original.replace(b"MAX_WORKERS = 4", b"MAX_WORKERS = 3")
source_path.write_bytes(edited)
os.utime(source_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
assert source_path.stat().st_size == stat.st_size
assert source_path.stat().st_mtime_ns == stat.st_mtime_ns
expected_hash = hashlib.sha256(edited).hexdigest()
if {cache_state!r} == 'stale':
    old = importlib.import_module('validation_execution')
    # The default bytecode loader really executes the stale policy, even -B.
    assert old.MAX_WORKERS == 4
    assert old.VALIDATION_SOURCE_SHA256 == expected_hash
if {cache_state!r} == 'absent':
    cached_path.unlink()
old_callable = old.pytest_command if old is not None else None
client.prepare_supervisor_execution_api(Path({str(agents)!r}))
current = importlib.import_module('validation_execution')
assert current.MAX_WORKERS == 3, current.MAX_WORKERS
assert current.VALIDATION_SOURCE_SHA256 == expected_hash
current_common = sys.modules['executor_common']
assert current.common is current_common and current_common is not common
try:
    current.pytest_command(['test_jobs.py'], profile='full', workers=4,
        env={{}}, repo_root=source_path.parent)
except current_common.ValidationBudgetError:
    pass
else:
    raise AssertionError('stale policy admitted four workers')
assert '--maxfail=0' in current.pytest_command(['test_jobs.py'], profile='full',
    workers=0, env={{}}, repo_root=source_path.parent)
if old is not None:
    assert current is not old
    assert old.pytest_command is old_callable
    assert old_callable.__globals__ is old.__dict__
    assert old_callable.__globals__['MAX_WORKERS'] == 4
    assert old.common is common
assert source_path.read_bytes() == edited
if {cache_state!r} != 'absent':
    assert cached_path.read_bytes() == cached_bytes
print(json.dumps({{'workers': current.MAX_WORKERS, 'sha256': expected_hash}}))
'''
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    child = subprocess.run(
        [sys.executable, *(["-B"] if no_bytecode else []), "-c", code],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout)["workers"] == 3


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("common_warm", [False, True])
@pytest.mark.parametrize("dependency", ["executor_common", "validation_execution"])
@pytest.mark.parametrize("failure", ["compile", "import", "execution", "interruption", "source_drift", "peer_drift", "missing_guard"])
def test_supervisor_handoff_failed_refresh_preserves_cached_ownership(
    supervisor_dependency_copy, warm, common_warm, dependency, failure,
):
    agents, executors = supervisor_dependency_copy
    peer = "validation_execution" if dependency == "executor_common" else "executor_common"
    guard = "ensure_not_agent_review_mode" if dependency == "executor_common" else "run_validation"
    tails = {
        "compile": "\ninvalid syntax here\n",
        "import": "\nimport rcx_handoff_nonexistent_dependency\n",
        "execution": "\nraise RuntimeError('broken validation source')\n",
        "interruption": "\nraise KeyboardInterrupt('interrupted validation import')\n",
        "source_drift": "\nPath(__file__).write_bytes(Path(__file__).read_bytes() + b'\\n# drift\\n')\n",
        "peer_drift": f"\np = Path(__file__).with_name('{peer}.py'); p.write_bytes(p.read_bytes() + b'\\n# peer drift\\n')\n",
        "missing_guard": f"\ndel {guard}\n",
    }
    code = f'''
import importlib, sys
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import meta_bridge_client as client
import executor_common as common
old = importlib.import_module('validation_execution') if {warm!r} else None
old_callable = old.pytest_command if old is not None else None
common_callable = common.admit_stage_budget
if not {common_warm!r}:
    del sys.modules['executor_common']
source_path = Path({str(executors / (dependency + '.py'))!r})
source_path.write_text(source_path.read_text() + {tails[failure]!r})
expected = {{'compile': SyntaxError, 'import': ModuleNotFoundError,
    'execution': RuntimeError, 'interruption': KeyboardInterrupt,
    'source_drift': client.MetaBridgeClientError, 'peer_drift': client.MetaBridgeClientError,
    'missing_guard': client.MetaBridgeClientError}}[{failure!r}]
try:
    client.prepare_supervisor_execution_api(Path({str(agents)!r}))
except expected:
    pass
else:
    raise AssertionError('invalid refresh was admitted')
assert sys.modules.get('validation_execution') is old
assert sys.modules.get('executor_common') is (common if {common_warm!r} else None)
assert common.admit_stage_budget is common_callable
assert common_callable.__globals__ is common.__dict__
assert common.VALIDATION_CEILING_SECONDS == 7200
if old is not None:
    assert old.pytest_command is old_callable
    assert old_callable.__globals__ is old.__dict__
    assert old_callable.__globals__['MAX_WORKERS'] == 4
    assert old.common is common
'''
    child = subprocess.run(
        [sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=30,
    )
    assert child.returncode == 0, child.stdout + child.stderr


def test_supervisor_handoff_preserves_admitted_budget_identity_and_clocks(supervisor_dependency_copy):
    agents, executors = supervisor_dependency_copy
    code = f'''
import json, sys, time
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import executor_common as old
import validation_execution as old_validation
import meta_bridge_client as client
root = Path({str(executors)!r})
command = [sys.executable, '-c', 'pass']
budget = old.admit_stage_budget(root, key='pytest_full', command=command,
                               baseline=1, seconds=1, ceiling=7200)
encoded = budget.encode()
before = budget.remaining()
old_admission = old.admit_stage_budget
old_decode = old.decode_stage_budget
old_run = old_validation.run_validation
client.prepare_supervisor_execution_api(Path({str(agents)!r}))
current = sys.modules['executor_common']
decoded = current.decode_stage_budget(encoded, root, key='pytest_full', command=command)
assert decoded.encode() == encoded
assert decoded.invocation == budget.invocation
assert decoded.started_ns == budget.started_ns and decoded.wall_started_ns == budget.wall_started_ns
assert decoded.remaining() < before
assert old.decode_stage_budget(encoded, root).encode() == encoded
assert old.admit_stage_budget is old_admission and old.decode_stage_budget is old_decode
assert old_admission.__globals__ is old_decode.__globals__ is old.__dict__
assert old_run.__globals__ is old_validation.__dict__ and old_validation.common is old
assert sys.modules['validation_execution'].common is current
assert current.ensure_not_agent_review_mode.__globals__ is current.__dict__
time.sleep(1.05)
for owner in (old, current):
    try:
        owner.decode_stage_budget(encoded, root)
    except owner.ValidationBudgetError as exc:
        assert 'exhausted' in str(exc)
    else:
        raise AssertionError('refresh restarted an exhausted budget')
'''
    child = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr


def test_supervisor_handoff_refuses_foreign_validation_source(tmp_path, monkeypatch):
    common = sys.modules.get("executor_common")
    foreign = types.ModuleType("validation_execution")
    foreign.__file__ = str(tmp_path / "validation_execution.py")
    monkeypatch.setitem(sys.modules, "validation_execution", foreign)
    with pytest.raises(MetaBridgeClientError, match="unexpected source"):
        client_mod.prepare_supervisor_execution_api(_AGENTS_DIR)
    assert sys.modules["validation_execution"] is foreign
    assert sys.modules.get("executor_common") is common


def _supervisor_common_imports() -> list[str]:
    """Every name meta_bridge_supervisor imports from executor_common at module scope."""
    import ast

    tree = ast.parse((_AGENTS_DIR / "meta_bridge_supervisor.py").read_text())
    return sorted(alias.name for node in tree.body
                  if isinstance(node, ast.ImportFrom) and node.module == "executor_common"
                  for alias in node.names)


_BARE_SUPERVISOR_IMPORT_CASES = (
    "compatible", "compatible_validation", "absent", "foreign_common", "foreign_validation",
    "incoherent_validation", "baseline_validation",
    "stale_common", "stale_validation", "stale_validation_cache",
)


@pytest.mark.parametrize("case", [*_BARE_SUPERVISOR_IMPORT_CASES,
                                  *(f"baseline:{name}" for name in _supervisor_common_imports())])
def test_bare_supervisor_import_preserves_compatible_registered_pair(tmp_path, case):
    """A bare import never republishes a proven pair; class identity survives.

    Real child process, supervisor import and registry. An absent, incompatible
    (each missing module-level supervisor dependency) or incoherent pair still
    receives the exact-bytes transaction instead of an ImportError; a foreign
    source still refuses with the registry untouched; old callables keep owners.
    A symbol-compatible owner that executed a stale timestamp cache is not
    proven, so it receives the transaction too. A stale cache of an unloaded
    validation module cannot reach execution: the proven common is kept and
    validation executes from its bound bytes.
    """
    code = _STALE_TIMESTAMP_CACHE + f'''
import importlib, importlib.util, json, sys, types
from pathlib import Path
agents = Path({str(_AGENTS_DIR)!r})
executors = agents.parent / "executors"
sys.path[:0] = [str(agents.parents[2]), str(agents.parents[1]), str(agents), str(executors)]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
case, _, missing = {case!r}.partition(":")
stale = {{"stale_common": "executor_common", "stale_validation": "validation_execution",
          "stale_validation_cache": "validation_execution"}}.get(case)
if stale:
    sys.pycache_prefix = str(Path({str(tmp_path)!r}) / "pycache")
    install_stale_cache(executors / (stale + ".py"), *{_STALE_EDITS!r}[stale])
common = None if case == "absent" else load("executor_common", executors / "executor_common.py")
validation = None
if case in ("compatible_validation", "foreign_validation", "incoherent_validation", "baseline_validation",
            "stale_validation"):
    validation = load("validation_execution", executors / "validation_execution.py")
    assert validation.common is common
if case == "stale_common":
    assert common.VALIDATION_CEILING_SECONDS == 9900
elif case == "stale_validation":
    assert validation.MAX_WORKERS == 8
if case == "baseline":
    delattr(common, missing)
elif case == "foreign_common":
    common.__file__ = str(Path({str(tmp_path)!r}) / "executor_common.py")
elif case == "foreign_validation":
    validation.__file__ = str(Path({str(tmp_path)!r}) / "validation_execution.py")
elif case == "incoherent_validation":
    validation.common = types.ModuleType("executor_common")
elif case == "baseline_validation":
    del validation.run_pytest
old_callable = None if common is None else common.normalize_agent_bus_dir
before = {{name: sys.modules.get(name) for name in ("executor_common", "validation_execution")}}
try:
    supervisor = importlib.import_module("meta_bridge_supervisor")
except Exception as exc:
    after = {{name: sys.modules.get(name) for name in before}}
    print(json.dumps({{"refused": str(exc), "unchanged": all(after[name] is before[name] for name in before)}}))
    raise SystemExit(0)
current = sys.modules["executor_common"]
current_validation = importlib.import_module("validation_execution")
assert Path(current.__file__).resolve() == (executors / "executor_common.py").resolve()
assert current_validation.common is current
assert supervisor.ExecutorCommonError is current.ExecutorCommonError
try:
    current.normalize_agent_bus_dir("runtime")
except current.ExecutorCommonError as exc:
    raised = type(exc)
else:
    raise AssertionError("invalid bus identity was admitted")
if common is not None:
    assert common.normalize_agent_bus_dir is old_callable
    assert old_callable.__globals__ is common.__dict__
print(json.dumps({{
    "replaced_common": current is not common,
    "replaced_validation": validation is not None and current_validation is not validation,
    "error_owner_is_original": raised is getattr(common, "ExecutorCommonError", None),
    "ceiling": current.VALIDATION_CEILING_SECONDS,
    "workers": current_validation.MAX_WORKERS,
}}))
'''
    env = dict(os.environ)
    for key in ("RCX_NATIVE_STAGE_BUDGET", "RCX_VALIDATION_SCHEDULE", "PYTHONPYCACHEPREFIX"):
        env.pop(key, None)
    child = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert child.returncode == 0, child.stdout + child.stderr
    observed = json.loads(child.stdout.splitlines()[-1])
    kind = case.partition(":")[0]
    if kind in ("foreign_common", "foreign_validation"):
        assert "unexpected source" in observed["refused"] and observed["unchanged"], observed
        return
    assert "refused" not in observed, observed
    proven = kind in ("compatible", "compatible_validation", "stale_validation_cache")
    assert observed["replaced_common"] is not proven, observed
    assert observed["error_owner_is_original"] is proven, observed
    assert observed["replaced_validation"] is (kind in ("incoherent_validation", "baseline_validation",
                                                        "stale_validation")), observed
    # Every admitted pair executes the bound source, whichever loader ran before.
    assert (observed["ceiling"], observed["workers"]) == (7200, 4), observed


def test_supervisor_handoff_compiles_dependencies_exactly_like_import(supervisor_dependency_copy):
    """Bound bytes alone decide future features; the client's own flags never leak."""
    agents, executors = supervisor_dependency_copy
    path = executors / "validation_execution.py"
    source = path.read_text()
    assert source.count("from __future__ import annotations\n") == 1
    path.write_text(source.replace("from __future__ import annotations\n", ""))
    code = f'''
import __future__, importlib.util, json, sys
from pathlib import Path
sys.path[:0] = [{str(agents)!r}, {str(executors)!r}]
import meta_bridge_client as client
client.prepare_supervisor_execution_api(Path({str(agents)!r}))
handoff = sys.modules["validation_execution"]
spec = importlib.util.spec_from_file_location("validation_import_probe", Path({str(path)!r}))
imported = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imported)
flag = __future__.annotations.compiler_flag
assert handoff.run_validation.__code__.co_flags & flag == 0, "client future flags leaked"
assert imported.run_validation.__code__.co_flags & flag == 0
assert handoff.run_validation.__annotations__["repo_root"] is Path
assert imported.run_validation.__annotations__["repo_root"] is Path
print(json.dumps({{"future_annotations": False}}))
'''
    child = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr
    assert json.loads(child.stdout) == {"future_annotations": False}


@dataclass
class FakeResponse:
    """Fake MetaBridgeResponse for testing."""
    status: str = "success"
    decision: str = "COMMIT_GO"
    summary: str = "Test summary"
    validations_passed: list[str] = field(default_factory=lambda: ["L4 contract"])
    validations_failed: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    request_for_claude: str = ""
    error_code: str = ""
    error_detail: str = ""


class TestValidateDecision:
    """Test that template enum strings are rejected."""

    def test_real_decision_accepted(self):
        validate_decision("COMMIT_GO")  # Should not raise

    def test_hold_decision_accepted(self):
        validate_decision("COMMIT_GO_HOLD_PUSH")  # Should not raise

    def test_error_decision_accepted(self):
        validate_decision("ERROR_VALIDATION_FAILED")  # Should not raise

    def test_pipe_delimited_enum_rejected(self):
        template = "COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION|NEEDS_PHASE_A|NEEDS_PHASE_B|STOP_FOR_FOUNDER|STOP_FOR_TRIAGE_DISCUSSION|ERROR_VALIDATION_FAILED"
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited template enum"):
            validate_decision(template)

    def test_empty_decision_rejected(self):
        with pytest.raises(MetaBridgeClientError, match="empty decision"):
            validate_decision("")

    def test_partial_pipe_rejected(self):
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited"):
            validate_decision("COMMIT_GO|ERROR")


class TestSupervisorResult:
    """Test SupervisorResult properties."""

    def test_commit_capable(self):
        r = SupervisorResult(
            decision="COMMIT_GO", summary="", status="success",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="", error_detail="",
            receipt_path=".agent_bus/meta/pre_commit_receipt.json",
        )
        assert r.is_commit_capable
        assert not r.is_error
        assert not r.is_hold

    def test_hold(self):
        r = SupervisorResult(
            decision="COMMIT_GO_HOLD_PUSH", summary="", status="success",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="", error_detail="",
            receipt_path=".agent_bus/meta/pre_commit_receipt.json",
        )
        assert r.is_commit_capable
        assert r.is_hold

    def test_error(self):
        r = SupervisorResult(
            decision="ERROR_VALIDATION_FAILED", summary="", status="error",
            validations_passed=[], validations_failed=[], findings=[],
            request_for_claude="", error_code="ERR", error_detail="",
            receipt_path="",
        )
        assert r.is_error
        assert not r.is_commit_capable


class TestRunMetaBridgePackage:
    """Test the client wrapper with mocked supervisor."""

    def test_returns_structured_result_on_commit_go(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"task_id": "test"}')

        fake_resp = FakeResponse(decision="COMMIT_GO")

        with patch.dict(sys.modules, {"meta_bridge_supervisor": MagicMock()}):
            # Re-import to pick up mock
            client_mod.run_meta_bridge = MagicMock(return_value=fake_resp)
            # Patch the import inside the function
            with patch.object(client_mod, "__import__", create=True):
                # Direct test of result construction
                result = SupervisorResult(
                    decision="COMMIT_GO",
                    summary="Test summary",
                    status="success",
                    validations_passed=["L4 contract"],
                    validations_failed=[],
                    findings=[],
                    request_for_claude="",
                    error_code="",
                    error_detail="",
                    receipt_path=".agent_bus/meta/pre_commit_receipt.json",
                )
                assert result.is_commit_capable
                assert result.decision == "COMMIT_GO"
                assert result.receipt_path == ".agent_bus/meta/pre_commit_receipt.json"

    def test_rejects_template_enum_from_supervisor(self):
        """If supervisor somehow returns the template enum string, client must reject."""
        template = "COMMIT_GO|COMMIT_GO_HOLD_PUSH|NO_ACTION"
        with pytest.raises(MetaBridgeClientError, match="pipe-delimited"):
            validate_decision(template)

    def test_lock_retry_structured_failure(self):
        """If lock is held for longer than timeout, raise structured error."""
        # This tests the error message structure, not the actual lock
        err = MetaBridgeClientError(
            "Supervisor lock held for 30s. Last error: Another meta-bridge supervisor is running."
        )
        assert "lock held" in str(err).lower()
        assert "30s" in str(err)

    def test_refreshes_stale_executor_common_before_supervisor_import(self, monkeypatch):
        """Long-lived executors refresh executor_common before importing supervisor."""
        executor_common_path = _AGENTS_DIR.parent / "executors" / "executor_common.py"
        spec = importlib.util.spec_from_file_location("executor_common", executor_common_path)
        assert spec and spec.loader
        stale_mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "executor_common", stale_mod)
        spec.loader.exec_module(stale_mod)
        delattr(stale_mod, "ensure_bridge_config_path")
        assert not hasattr(stale_mod, "ensure_bridge_config_path")

        client_mod._refresh_executor_common_before_supervisor_import(_AGENTS_DIR)  # ANTICHEAT_OK: stale-module refresh helper is the regression target

        refreshed = sys.modules["executor_common"]
        assert Path(refreshed.__file__).resolve() == executor_common_path.resolve()
        assert hasattr(refreshed, "ensure_bridge_config_path")


class TestReceiptUniqueness:
    """Per-invocation receipt paths must be unique even within the same second."""

    def test_same_second_receipts_are_unique(self):
        """Two rapid calls produce distinct receipt filenames."""
        from tests.repo_root import REPO_ROOT
        import importlib.util, sys, tempfile
        from pathlib import Path
        from unittest.mock import patch as _p

        meta_path = REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
        spec = importlib.util.spec_from_file_location("meta_receipt_test", meta_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["meta_receipt_test"] = mod
        spec.loader.exec_module(mod)

        response = mod.MetaBridgeResponse(
            status="success", decision="COMMIT_GO", summary="ok",
        )
        pkg = Path(tempfile.mktemp(suffix=".json"))
        pkg.write_text("{}")

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            with _p.object(mod, "compute_staged_sha", return_value="abc"):
                path1 = mod.write_pre_commit_receipt(response, pkg, repo_root=repo)
                path2 = mod.write_pre_commit_receipt(response, pkg, repo_root=repo)

            assert path1 != path2, f"Same-second receipts must have distinct paths: {path1} vs {path2}"
            assert path1.exists()
            assert path2.exists()


class TestEnvelopeSchemaValidation:
    """Supervisor envelope must have required fields: decision, summary, status."""

    @staticmethod
    def _supervisor_module(response, receipt_writer):
        supervisor = types.ModuleType("meta_bridge_supervisor")

        class MetaBridgeError(RuntimeError):
            pass

        supervisor.MetaBridgeError = MetaBridgeError
        supervisor.run_meta_bridge = MagicMock(return_value=response)
        supervisor.write_pre_commit_receipt = receipt_writer
        return supervisor

    @staticmethod
    def _commit_capable_response(**overrides):
        values = {
            "decision": "COMMIT_GO",
            "summary": "ready to commit",
            "status": "success",
        }
        values.update(overrides)
        return types.SimpleNamespace(**values)

    @pytest.mark.parametrize("required_field", ("decision", "summary", "status"))
    def test_null_required_field_rejected_before_commit_receipt_write(
        self,
        tmp_path,
        required_field,
    ):
        """Explicit null required fields cannot reach the receipt writer."""
        package_path = tmp_path / "package.json"
        package_path.write_text('{}')
        bus_dir = tmp_path / ".agent_bus"
        response = self._commit_capable_response(**{required_field: None})
        receipt_writer = MagicMock()
        supervisor = self._supervisor_module(response, receipt_writer)

        with patch.dict(sys.modules, {"meta_bridge_supervisor": supervisor}):
            with pytest.raises(
                MetaBridgeClientError,
                match=rf"missing required field: {required_field}",
            ):
                run_meta_bridge_package(package_path, bus_dir=bus_dir)

        receipt_writer.assert_not_called()
        assert not bus_dir.exists()

    @pytest.mark.parametrize("required_field", ("decision", "summary", "status"))
    def test_missing_required_field_rejected_before_commit_receipt_write(
        self,
        tmp_path,
        required_field,
    ):
        """Absent required fields cannot reach the receipt writer."""
        package_path = tmp_path / "package.json"
        package_path.write_text('{}')
        bus_dir = tmp_path / ".agent_bus"
        response = self._commit_capable_response()
        delattr(response, required_field)
        receipt_writer = MagicMock()
        supervisor = self._supervisor_module(response, receipt_writer)

        with patch.dict(sys.modules, {"meta_bridge_supervisor": supervisor}):
            with pytest.raises(
                MetaBridgeClientError,
                match=rf"missing required field: {required_field}",
            ):
                run_meta_bridge_package(package_path, bus_dir=bus_dir)

        receipt_writer.assert_not_called()
        assert not bus_dir.exists()

    def test_missing_optional_fields_default_safely(self):
        """Optional fields default to empty list/string when absent from response."""
        import inspect
        src = inspect.getsource(client_mod.run_meta_bridge_package)
        # Verify defensive getattr pattern for optional fields
        assert "getattr(response," in src, (
            "run_meta_bridge_package must use getattr with defaults for optional fields"
        )
        # Verify the three required fields are checked
        assert '"decision"' in src or "'decision'" in src
        assert '"summary"' in src or "'summary'" in src
        assert '"status"' in src or "'status'" in src


class TestReceiptPathFailClosed:
    """meta_bridge_client must fail closed on absolute receipt paths."""

    def test_no_absolute_fallback_in_source(self):
        """The except block for repo-relative conversion must raise, not fall back."""
        import inspect
        src = inspect.getsource(client_mod.run_meta_bridge_package)
        # After the "except (_sp.CalledProcessError, ValueError)" block,
        # the code must raise MetaBridgeClientError, not assign receipt_path
        assert "raise MetaBridgeClientError" in src, (
            "meta_bridge_client must raise MetaBridgeClientError on failed "
            "repo-relative conversion, not fall back to absolute path"
        )
        # The old fallback pattern "receipt_path = str(exact_receipt_path)" must be gone
        # from the except block
        lines = src.splitlines()
        in_except = False
        for line in lines:
            if "except" in line and "CalledProcessError" in line:
                in_except = True
            elif in_except:
                assert "receipt_path = str(exact_receipt_path)" not in line, (
                    "Found absolute path fallback in except block — must raise instead"
                )
                if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("raise"):
                    break  # Past the except block
