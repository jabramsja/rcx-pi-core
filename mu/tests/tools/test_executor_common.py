"""Typed transport of the immutable launch override sibling."""

import copy
import ctypes
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT

common = load_module("executor_common", REPO_ROOT / "mu/tools/executors/executor_common.py")


@pytest.mark.parametrize("signal_fields", [
    {"status": "budget_hold", "validation_budget_hold": True},
    {"status": "ownership_hold", "validation_budget_hold": True},
    {"status": "interrupted", "validation_budget_hold": True},
    {"status": "validation_budget_hold"},
    {"status": "error", "error_code": "VALIDATION_BUDGET_HOLD"},
])
def test_validation_hold_survives_nested_callers(signal_fields):
    from mu.tools.executors.recovery_gate import FailureClass, classify_failure

    validation = {
        **signal_fields, "passed": False, "exit_code": 125,
        "stdout": "partial validation output\n", "stderr": "HOLD: ownership uncertain\n",
        "receipt_path": "validation/receipt.json", "rcx_process_released": False,
    }
    before = copy.deepcopy(validation)
    gate = common.validation_hold_result(validation, step="pytest_gate")
    outer = common.validation_hold_result(gate, step="bot_remediation_validation")
    for result in (gate, outer):
        assert result["status"] == "validation_budget_hold"
        assert result["validation_budget_hold"] is True
        assert result["passed"] is False
        assert result["stdout"] == validation["stdout"]
        assert result["stderr"] == validation["stderr"]
        assert result["errors"] == [validation["stderr"]]
        assert classify_failure(result) == FailureClass.TERMINAL_POLICY
        wrapped = {"status": "error", "stdout": json.dumps(result), "exit_code": 1}
        assert classify_failure(wrapped) == FailureClass.TERMINAL_POLICY
    assert outer["validation"]["validation"] == before
    assert validation == before


@pytest.mark.parametrize("validation", [
    {"passed": True, "exit_code": 0},
    {"passed": False, "exit_code": 1, "stderr": "test assertion mentions HOLD"},
    {"status": "held", "validation_budget_hold": False},
    {"status": "error", "validation_budget_hold": "true"},
    {"status": "error", "error_code": "VALIDATION_FAILED", "error_detail": "mentions VALIDATION_BUDGET_HOLD"},
    {"status": "error", "error_code": "validation_budget_hold"},
])
def test_validation_hold_requires_structured_signal(validation):
    assert common.validation_hold_result(validation, step="pytest_gate") is None


@pytest.mark.parametrize("key", ["phase_b_executor", "pre_push_fast", "unknown"])
def test_admitted_budget_rejects_scalar_recovery_key_changes(tmp_path, monkeypatch, key):
    monkeypatch.setenv(common.NATIVE_STAGE_BUDGET_ENV, "sealed invocation")
    monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_KEY", key)
    monkeypatch.setenv("RCX_RECOVERY_TIMEOUT_OVERRIDE", "999999")
    config = copy.deepcopy(common.DEFAULT_EXECUTOR_CONFIG)
    before = copy.deepcopy(config)
    with pytest.raises(common.ValidationBudgetError, match="baseline"):
        common.apply_recovery_config_env_overrides(config)
    assert config == before


@contextmanager
def complete_process_observation(*modules):
    """Give positive release fixtures one real OS snapshot per observation.

    Derive the graph from the same full ps result as its identities so unrelated
    machine churn cannot invalidate the fixture's complete-observation premise.
    Each signal/release recheck still obtains a fresh OS snapshot. The production
    parser, ownership checks, signals and absence probes remain real; failed and
    partial two-query controls deliberately do not use this boundary.
    """
    real_run = subprocess.run
    records = []

    def wrap(observe):
        def coherent(owner, *, cwd=None):
            snapshot = None

            def query(args, **kwargs):
                nonlocal snapshot
                if args == ["ps", "-axo", "pid=,ppid="]:
                    snapshot = real_run(
                        ["ps", "axeww", "-o", "pid=,ppid=,lstart=,stat=,command="],
                        **{**kwargs, "env": {**os.environ, "LC_ALL": "C"}},
                    )
                    graph = "\n".join(" ".join(row.split(None, 2)[:2])
                                      for row in snapshot.stdout.splitlines()) + "\n"
                    return subprocess.CompletedProcess(args, snapshot.returncode, graph, "")
                if args == ["ps", "axeww", "-o", "pid=,ppid=,lstart=,stat=,command="]:
                    assert snapshot is not None
                    return snapshot
                return real_run(args, **kwargs)

            with patch.object(subprocess, "run", side_effect=query):
                result = observe(owner, cwd=cwd)
            # Preserve real state/ancestry diagnostics without serializing
            # command lines or environment values from the full OS census.
            rows = [row.split(None, 8) for row in snapshot.stdout.splitlines()] if snapshot else []
            records.append({"observed_ns": time.monotonic_ns(),
                            "snapshot_sha256": hashlib.sha256(snapshot.stdout.encode()).hexdigest()
                            if snapshot else None,
                            "process_states": [row[:8] for row in rows],
                            "complete": result.complete, "error": result.error,
                            "owned": [dict(pid=item.pid, ppid=item.ppid, started=item.started)
                                      for item in result.identities.values() if item.owned]})
            return result
        return coherent

    with ExitStack() as stack:
        for module in dict.fromkeys(modules):
            stack.enter_context(patch.object(module, "observe_executor_processes",
                                            side_effect=wrap(module.observe_executor_processes)))
        yield records


@contextmanager
def fixture_orphan_reaper():
    """Own Linux fixture orphans until explicit, PID-specific teardown waits.

    This never reaps during a release observation. Negative reparented-child
    tests still see a live process outside the root tree. On macOS launchd owns
    orphans; callers must still prove their actual absence during teardown.
    """
    previous = ctypes.c_int()
    libc = None
    if sys.platform == "linux":
        libc = ctypes.CDLL(None, use_errno=True)
        assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0, ctypes.get_errno()
        assert libc.prctl(36, 1, 0, 0, 0) == 0, ctypes.get_errno()
    receipt = dict(linux_subreaper=libc is not None, previous=previous.value, restored=False)
    try:
        yield receipt
    finally:
        if libc is not None:
            assert libc.prctl(36, previous.value, 0, 0, 0) == 0, ctypes.get_errno()
            current = ctypes.c_int()
            assert libc.prctl(37, ctypes.byref(current), 0, 0, 0) == 0, ctypes.get_errno()
            assert current.value == previous.value
        receipt["restored"] = True


@pytest.mark.parametrize("turns", [None, 1, 1000])
@pytest.mark.parametrize("roles", [("", ""), ("codex", "claude")])
def test_launch_override_transport_copies_exact_typed_values(turns, roles):
    value = dict(version=1, implementer_agent=roles[0], reviewer_agent=roles[1],
                 pager_route="", max_turns=turns)
    route = {"launch_wave_override_authority": value}
    original = copy.deepcopy(route)
    carried = common.copy_launch_wave_override_authority(route, required=True)
    assert carried == original
    assert carried["launch_wave_override_authority"] is not value
    carried["launch_wave_override_authority"]["reviewer_agent"] = "changed"
    assert route == original


@pytest.mark.parametrize("field,value", [
    ("version", True), ("version", 1.0), ("version", 2),
    ("implementer_agent", None), ("implementer_agent", 1),
    ("reviewer_agent", False), ("reviewer_agent", []),
    ("reviewer_agent", " codex"), ("pager_route", "foreign"),
    ("pager_route", False), ("max_turns", True), ("max_turns", 1.0),
    ("max_turns", "20"), ("max_turns", 0), ("max_turns", 1001),
    ("unknown", "extra"),
])
def test_launch_override_transport_rejects_invalid_schema_without_mutation(field, value):
    authority = dict(version=1, implementer_agent="codex", reviewer_agent="claude",
                     pager_route="both", max_turns=20)
    authority[field] = value
    route = {"launch_wave_override_authority": authority}
    before = copy.deepcopy(route)
    with pytest.raises(common.ExecutorCommonError, match="launch_wave_override_authority"):
        common.copy_launch_wave_override_authority(route, required=True)
    assert route == before


@pytest.mark.parametrize("value", [None, True, [], {}, {"version": 1}])
def test_launch_override_transport_rejects_partial_or_malformed_authority(value):
    with pytest.raises(common.ExecutorCommonError, match="launch_wave_override_authority"):
        common.copy_launch_wave_override_authority({"launch_wave_override_authority": value}, required=True)


def test_missing_launch_override_authority_never_mints_defaults():
    assert common.copy_launch_wave_override_authority({}) == {}
    with pytest.raises(common.ExecutorCommonError, match="launch_wave_override_authority"):
        common.copy_launch_wave_override_authority({}, required=True)


@pytest.fixture
def owned_process():
    owner = uuid.uuid4().hex
    proc = subprocess.Popen(
        [sys.executable, "-B", "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        env={**os.environ, common.EXECUTOR_PROCESS_OWNER_ENV: owner},
    )
    try:
        yield proc, owner
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


def test_complete_owned_process_observation_and_release(owned_process, tmp_path):
    proc, owner = owned_process
    with complete_process_observation(common) as records:
        observation = common.observe_executor_processes(owner, cwd=tmp_path)
        assert observation.complete, records
        identity = observation.identities[proc.pid]
        assert identity.owned and identity.ppid == os.getpid()
        assert proc.pid in observation.parents
        evidence = common.terminate_owned_executor(proc, owner, cwd=tmp_path)
        assert evidence is not None, records
        assert evidence["members"] == [{"pid": proc.pid, "started": identity.started}]
        assert common.executor_release_evidence_error(evidence, cwd=tmp_path) is None
    with pytest.raises(ProcessLookupError):
        os.kill(proc.pid, 0)


def test_real_unreaped_process_is_present_until_parent_wait(owned_process, tmp_path):
    proc, owner = owned_process
    with complete_process_observation(common) as records:
        observed = common.observe_executor_processes(owner, cwd=tmp_path)
        assert observed.complete, records
        identity = observed.identities[proc.pid]
        # Only exercise the validator with metadata from the real live census.
        # This is not a dispatcher release receipt or permission to resume.
        candidate = dict(version=1, owner=owner, root_pid=proc.pid,
                         members=[dict(pid=identity.pid, started=identity.started)])
        os.kill(proc.pid, signal.SIGKILL)  # Do not poll/wait: preserve the zombie.
        deadline = time.monotonic() + 5
        while True:
            state = common.observe_executor_processes(owner, cwd=tmp_path)
            assert state.complete, records
            row = next(row for row in records[-1]["process_states"] if int(row[0]) == proc.pid)
            if row[7].startswith("Z"):
                break
            assert time.monotonic() < deadline, row
            time.sleep(0.01)
        os.kill(proc.pid, 0)
        assert common.executor_release_evidence_error(candidate, cwd=tmp_path) is not None
        assert proc.returncode is None
        assert proc.wait(timeout=5) == -signal.SIGKILL
        with pytest.raises(ProcessLookupError):
            os.kill(proc.pid, 0)
        assert common.executor_release_evidence_error(candidate, cwd=tmp_path) is None
    (tmp_path / "unreaped-process-observations.json").write_text(json.dumps(records) + "\n")


@pytest.mark.parametrize("birth_between_queries", [False, True])
def test_real_reparenting_between_queries_is_uncertain(
    owned_process, monkeypatch, tmp_path, birth_between_queries,
):
    """An unrelated real lifetime change legitimately invalidates a full census."""
    proc, owner = owned_process
    parent = subprocess.Popen(
        [sys.executable, "-B", "-c", "import subprocess,sys,time; "
         "p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(60)']); "
         "print(p.pid,flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE, text=True, start_new_session=True,
    )
    child = int(parent.stdout.readline())
    real_run = subprocess.run
    graphs = []
    born = []
    query_parents = []

    def reparent(args, **kwargs):
        result = real_run(args, **kwargs)
        if args[0] == "ps":
            query_parents.append({int(row.split()[0]): int(row.split()[1])
                                  for row in result.stdout.splitlines()})
        if args == ["ps", "-axo", "pid=,ppid="] and not graphs:
            graphs.append(result.stdout)
            assert query_parents[0][child] == parent.pid
            if birth_between_queries:
                born.append(subprocess.Popen(
                    [sys.executable, "-B", "-c", "import time; time.sleep(60)"],
                    start_new_session=True,
                ))
            parent.kill()
            parent.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                current = real_run(["ps", "-p", str(child), "-o", "ppid="],
                                   capture_output=True, text=True, check=True)
                if int(current.stdout.strip()) != parent.pid:
                    break
                time.sleep(0.01)
            else:
                pytest.fail("fixture child did not reparent")
        return result

    try:
        monkeypatch.setattr(subprocess, "run", reparent)
        observation = common.observe_executor_processes(owner, cwd=tmp_path)
        diagnostic = {"complete": observation.complete, "error": observation.error,
                      "owned_pid": proc.pid, "reparented_pid": child,
                      "parents": [rows.get(child) for rows in query_parents],
                      "born_pids": [item.pid for item in born]}
        print(json.dumps(diagnostic, sort_keys=True))
        assert graphs and not observation.complete, diagnostic
        assert observation.error == "process ancestry changed between observations", diagnostic
        assert query_parents[0][child] != query_parents[1][child], diagnostic
        assert not observation.parents and not observation.identities
        assert proc.poll() is None
        os.kill(child, 0)
        if birth_between_queries:
            assert born[0].pid not in query_parents[0]
            assert born[0].pid in query_parents[1]
            assert born[0].poll() is None
    finally:
        for item in born:
            if item.poll() is None:
                item.kill()
            item.wait(timeout=5)
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)
        parent.stdout.close()
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.mark.parametrize("query", ["graph", "identities"])
@pytest.mark.parametrize("failure", [
    "failed", "timeout", "unavailable", "empty", "malformed", "duplicate", "partial", "missing-root",
    "oversized-pid",
])
def test_incomplete_observation_never_grants_release(
    owned_process, monkeypatch, tmp_path, query, failure,
):
    proc, owner = owned_process
    real_run = subprocess.run
    failures = []

    def observe(args, *a, **kw):
        if args[0] != "ps" or ("-axo" in args) != (query == "graph"):
            return real_run(args, *a, **kw)
        failures.append(args)
        if failure == "failed":
            raise subprocess.CalledProcessError(1, args)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 5)
        if failure == "unavailable":
            raise FileNotFoundError("test query unavailable")
        result = real_run(args, *a, **kw)
        rows = result.stdout.splitlines(keepends=True)
        if failure == "empty": result.stdout = ""
        elif failure == "malformed": result.stdout += "not a process row\n"
        elif failure == "duplicate": result.stdout += rows[0]
        elif failure == "partial": result.stdout = rows[0]
        elif failure == "missing-root":
            result.stdout = "".join(row for row in rows if int(row.split()[0]) != proc.pid)
        elif failure == "oversized-pid":
            result.stdout += str(2 ** 64) + " " + rows[0].split(None, 1)[1]
        return result

    monkeypatch.setattr(subprocess, "run", observe)
    assert common.terminate_owned_executor(proc, owner, cwd=tmp_path) is None
    assert failures
    assert proc.returncode is not None


@pytest.mark.parametrize("fault", ["start-reused", "owner-lost", "query-failed", "permission"])
def test_identity_uncertainty_never_signals_an_actor(owned_process, monkeypatch, fault):
    proc, owner = owned_process
    # Capture the real initial identity coherently, then leave this boundary
    # before injecting adverse identity/query/permission behavior below.
    with complete_process_observation(common) as records:
        observed = common.observe_executor_processes(owner)
    assert observed.complete, records
    identity = observed.identities[proc.pid]
    real_run, real_kill = subprocess.run, os.kill
    signals = []

    def observe(args, *a, **kw):
        if args[0] == "ps" and fault == "query-failed":
            raise subprocess.CalledProcessError(1, args)
        result = real_run(args, *a, **kw)
        if args[0] == "ps" and "axeww" in args:
            lines = []
            for row in result.stdout.splitlines():
                if int(row.split()[0]) == proc.pid:
                    if fault == "start-reused":
                        fields = row.split(None, 8)
                        fields[2:7] = ["Mon", "Jan", "1", "00:00:00", "2001"]
                        row = " ".join(fields)
                    elif fault == "owner-lost":
                        row = row.replace(owner, "0" * 32)
                lines.append(row)
            result.stdout = "\n".join(lines) + "\n"
        return result

    def signal_actor(pid, signum):
        if pid == proc.pid and signum:
            if fault == "permission":
                raise PermissionError("test actor permission denial")
            signals.append((pid, signum))
        return real_kill(pid, signum)

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "run", observe)
        patch.setattr(os, "kill", signal_actor)
        assert common.signal_owned_executor_process(identity, owner, signal.SIGKILL) is False
        assert not signals
        assert proc.poll() is None


@pytest.mark.parametrize("query", ["graph", "identities"])
@pytest.mark.parametrize("fault", ["omitted", "parent-mismatch"])
@pytest.mark.parametrize("owned", [False, True])
def test_live_query_gaps_are_incomplete(owned_process, monkeypatch, query, fault, owned):
    proc, owner = owned_process
    real_run = subprocess.run
    changed = []

    def partial_query(args, *a, **kw):
        result = real_run(args, *a, **kw)
        if args[0] != "ps" or (("-axo" in args) != (query == "graph")):
            return result
        rows = []
        for row in result.stdout.splitlines():
            if int(row.split()[0]) == proc.pid:
                changed.append(proc.pid)
                if fault == "omitted":
                    continue
                fields = row.split(None, 2)
                fields[1] = "1"
                row = " ".join(fields)
            rows.append(row)
        result.stdout = "\n".join(rows) + "\n"
        return result

    monkeypatch.setattr(subprocess, "run", partial_query)
    observation = common.observe_executor_processes(owner if owned else uuid.uuid4().hex)
    assert changed and set(changed) == {proc.pid}
    assert proc.poll() is None
    assert observation.complete is False
    assert observation.error
    assert not observation.parents and not observation.identities


def test_later_partial_tables_cannot_erase_an_unresolved_live_pid(owned_process, monkeypatch):
    proc, owner = owned_process
    real_run = subprocess.run
    queries = []

    def partial_query(args, *a, **kw):
        result = real_run(args, *a, **kw)
        if args[0] == "ps":
            queries.append(args)
            if len(queries) > 1:
                result.stdout = "".join(row for row in result.stdout.splitlines(keepends=True)
                                        if int(row.split()[0]) != proc.pid)
        return result

    monkeypatch.setattr(subprocess, "run", partial_query)
    observation = common.observe_executor_processes(owner)
    assert len(queries) > 2
    assert proc.poll() is None
    assert observation.complete is False
    assert observation.error


def test_process_born_between_queries_requires_complete_resampling(owned_process, monkeypatch):
    """Isolate a birth from unrelated machine ancestry/identity changes.

    Replay an immutable real census, adding only the new real child's row at
    the first identity query. These are controlled parser/resampling inputs,
    never release evidence. The live gap probe and direct-child teardown stay
    real. The adjacent two-query reparenting controls exercise the unmodified
    OS queries and must still refuse, including when a child is also born.
    """
    proc, owner = owned_process
    real_run = subprocess.run
    real_kill = os.kill
    identity_command = ["ps", "axeww", "-o", "pid=,ppid=,lstart=,stat=,command="]
    snapshot = real_run(identity_command, capture_output=True, text=True, check=True,
                        timeout=5, env={**os.environ, "LC_ALL": "C"}).stdout
    born = []
    graphs = []
    probes = []
    identity_queries = []

    def observe(args, *a, **kw):
        nonlocal snapshot
        if args == ["ps", "-axo", "pid=,ppid="]:
            graph = "\n".join(" ".join(row.split(None, 2)[:2])
                              for row in snapshot.splitlines()) + "\n"
            graphs.append(graph)
            if not born:
                born.append(subprocess.Popen(
                    [sys.executable, "-B", "-c", "import time; time.sleep(60)"],
                    start_new_session=True,
                ))
            return subprocess.CompletedProcess(args, 0, graph, "")
        if args == identity_command:
            if not identity_queries:
                live = real_run(args, *a, **kw)
                rows = [row for row in live.stdout.splitlines()
                        if int(row.split()[0]) == born[0].pid]
                assert len(rows) == 1
                assert int(rows[0].split()[1]) == os.getpid()
                snapshot += rows[0] + "\n"
            identity_queries.append(snapshot)
            return subprocess.CompletedProcess(args, 0, snapshot, "")
        return real_run(args, *a, **kw)

    def probe(pid, signum):
        probes.append((pid, signum))
        return real_kill(pid, signum)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(subprocess, "run", observe)
            patch.setattr(os, "kill", probe)
            observation = common.observe_executor_processes(owner)
        assert len(graphs) > 1
        assert born[0].pid not in {int(row.split()[0]) for row in graphs[0].splitlines()}
        assert observation.complete, observation.error
        assert {proc.pid, born[0].pid} <= observation.parents.keys() & observation.identities.keys()
        assert len(graphs) == len(identity_queries) == 2
        assert probes == [(born[0].pid, 0)]  # Real live gap forces the second census.
        assert observation.identities[proc.pid].owned
        assert observation.parents[born[0].pid] == os.getpid()
        assert born[0].poll() is None
    finally:
        for child in born:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


@pytest.mark.parametrize("failed", [False, True])
def test_legacy_descendant_cleanup_keeps_best_effort_contract(monkeypatch, failed):
    def query(args, **kwargs):
        assert args == ["ps", "-axo", "pid=,ppid="]
        if failed:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "12 10\n13 12\nmalformed\n14 nope\n", "")

    monkeypatch.setattr(subprocess, "run", query)
    assert common.process_descendants(10) == (set() if failed else {12, 13})
    assert common.process_descendants(0) == set()


def test_legacy_tree_cleanup_still_terminates_and_kills_observed_children(monkeypatch):
    signals = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw:
                        subprocess.CompletedProcess(args, 0, "12 10\n13 12\n", ""))
    monkeypatch.setattr(os, "kill", lambda pid, signum: signals.append((pid, signum)))
    common.terminate_process_tree(10, settle_seconds=0)
    assert signals == [(pid, signum) for signum in (signal.SIGTERM, signal.SIGKILL)
                       for pid in (13, 12, 10)]
