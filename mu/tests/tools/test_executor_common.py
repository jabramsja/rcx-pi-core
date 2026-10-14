"""Typed transport of the immutable launch override sibling."""

import copy
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
            records.append({"complete": result.complete, "error": result.error,
                            "owned": [dict(pid=item.pid, ppid=item.ppid, started=item.started)
                                      for item in result.identities.values() if item.owned]})
            return result
        return coherent

    with ExitStack() as stack:
        for module in dict.fromkeys(modules):
            stack.enter_context(patch.object(module, "observe_executor_processes",
                                            side_effect=wrap(module.observe_executor_processes)))
        yield records


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


def test_real_reparenting_between_queries_is_uncertain(owned_process, monkeypatch, tmp_path):
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

    def reparent(args, **kwargs):
        result = real_run(args, **kwargs)
        if args == ["ps", "-axo", "pid=,ppid="] and not graphs:
            graphs.append(result.stdout)
            assert f"{child}" in result.stdout
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
                      "owned_pid": proc.pid, "reparented_pid": child}
        print(json.dumps(diagnostic, sort_keys=True))
        assert graphs and not observation.complete, diagnostic
        assert observation.error == "process ancestry changed between observations", diagnostic
        assert proc.poll() is None
        os.kill(child, 0)
    finally:
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
    proc, owner = owned_process
    real_run = subprocess.run
    born = []
    graphs = []

    def observe(args, *a, **kw):
        result = real_run(args, *a, **kw)
        if args[0] == "ps" and "-axo" in args:
            graphs.append(result.stdout)
            if not born:
                born.append(subprocess.Popen(
                    [sys.executable, "-B", "-c", "import time; time.sleep(60)"],
                    start_new_session=True,
                ))
        return result

    monkeypatch.setattr(subprocess, "run", observe)
    try:
        observation = common.observe_executor_processes(owner)
        assert len(graphs) > 1
        assert born[0].pid not in {int(row.split()[0]) for row in graphs[0].splitlines()}
        assert observation.complete, observation.error
        assert {proc.pid, born[0].pid} <= observation.parents.keys() & observation.identities.keys()
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
