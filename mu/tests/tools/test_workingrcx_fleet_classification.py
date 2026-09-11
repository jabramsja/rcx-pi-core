"""Public classification CLI proof using disposable repositories and records."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tests.repo_root import REPO_ROOT


CLI = REPO_ROOT / "mu/tools/executors/workingrcx_fleet_classification.py"
SOURCE = REPO_ROOT / "reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json"
LANDED_HASH = "ac6f61337081c9adb7c100bac061270f6c7864aaed55d48912f50b8473d0cd81"
LANDED_BASE = "c209bf29841425305003eeceddfd567a93874742"
STAMP = "2026-09-11T18:34:09+00:00"
ZERO_COUNTS = dict(entries=0, tracked=0, untracked=0, staged=0, unstaged=0, unmerged=0)


def git(fixture, root, *args):
    result = subprocess.run(
        [fixture.git, "-c", "init.defaultBranch=dev", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", "-c", "user.name=Classification Fixture",
         "-c", "user.email=classification@example.invalid", "-C", str(root), *args],
        env=fixture.env, capture_output=True, check=True,
    )
    return os.fsdecode(result.stdout).removesuffix("\n")


def row(fixture, name="WorkingRCX-merged", **changes):
    path = str(fixture.fleet / name)
    branch = "refs/heads/fixture/" + name
    result = {
        "path": path, "sources": ["fleet_root", "anchor_worktrees"],
        "registered_worktrees": [{"path": path, "HEAD": fixture.base, "branch": branch}],
        "classification": "UNCLASSIFIED", "observed_started_at": STAMP,
        "observed_finished_at": STAMP, "registration_status": "registered",
        "entry_kind": "directory", "availability_status": "present",
        "repository_kind": "linked_worktree", "inspection_status": "ok", "errors": [],
        "git": {"root": path, "git_dir": str(fixture.primary / ".git/worktrees" / name),
                "common_dir": str(fixture.primary / ".git"), "HEAD": fixture.base,
                "branch": branch, "branch_status": "symbolic", "dirty_status": "clean",
                "dirty_counts": dict(ZERO_COUNTS)},
    }
    result.update(changes)
    return result


def inventory(fixture, rows):
    return {
        "schema_version": 1, "observation_kind": "read_only_fleet_census",
        "started_at": "2026-09-11T18:34:08+00:00", "finished_at": "2026-09-11T18:34:25+00:00",
        "fleet_root": str(fixture.fleet), "anchor_repo": str(fixture.primary),
        "coverage_complete": True, "entry_count": len(rows), "entries": rows,
        "enumeration": {
            "fleet_root": {"status": "complete", "errors": [],
                           "matching_entries": sum("fleet_root" in r["sources"] for r in rows)},
            "anchor_worktrees": {"status": "complete", "errors": [],
                                 "records": sum(len(r["registered_worktrees"]) for r in rows)},
        },
        "limitations": ["Disposable recorded evidence; ignored files excluded from dirty counts."],
    }


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path.resolve()
    home = root / "home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, PYTHONDONTWRITEBYTECODE="1", LC_ALL="C")
    f = SimpleNamespace(root=root, fleet=root / "fleet", primary=root / "fleet/WorkingRCX",
                        carrier=root / "carrier", env=env, git=shutil.which("git"),
                        census=root / "census.json", output=root / "classification.json")
    assert f.git
    f.primary.mkdir(parents=True)
    git(f, f.primary, "init", "-q")
    (f.primary / "tracked.txt").write_text("valuable tracked evidence\n")
    (f.primary / ".gitignore").write_text("ignored*\n")
    git(f, f.primary, "add", "tracked.txt", ".gitignore")
    git(f, f.primary, "commit", "-qm", "disposable base")
    f.base = git(f, f.primary, "rev-parse", "HEAD")
    git(f, f.primary, "worktree", "add", "-qb", "fixture/carrier", str(f.carrier), f.base)
    f.target = f.fleet / "WorkingRCX-merged"
    git(f, f.primary, "worktree", "add", "-qb", "fixture/WorkingRCX-merged", str(f.target), f.base)
    (f.target / "ignored-evidence.txt").write_text("ignored but valuable evidence\n")
    f.data = inventory(f, [row(f)])
    return f


@pytest.fixture
def legacy_git_env(fixture):
    f = fixture
    bindir = f.root / "bin"
    bindir.mkdir()
    wrapper = bindir / "git"
    wrapper.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        "if '--no-lazy-fetch' in sys.argv:\n"
        "    sys.stderr.write('unknown option: --no-lazy-fetch\\nusage: git <command> [<args>]\\n'); sys.exit(129)\n"
        "args = sys.argv[sys.argv.index('-C') + 2:]\n"
        f"with open({str(f.root / 'legacy-git-queries.jsonl')!r}, 'a') as out: out.write(json.dumps(args) + '\\n')\n"
        # Emulate Git 2.43 ignoring the newer environment switch as well.
        "os.environ.pop('GIT_NO_LAZY_FETCH', None)\n"
        f"os.execv({f.git!r}, [{f.git!r}, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    return {**f.env, "PATH": str(bindir) + os.pathsep + f.env["PATH"],
            "GIT_PROTOCOL_FROM_USER": "0"}


def run_cli(f, data=None, *, expected=None, extra=(), output=None, base=None, env=None):
    if data is not None:
        f.census.write_text(json.dumps(data, ensure_ascii=True) + "\n", encoding="ascii")
    elif not f.census.exists():
        f.census.write_text(json.dumps(f.data) + "\n")
    digest = hashlib.sha256(f.census.read_bytes()).hexdigest()
    result = subprocess.run(
        [sys.executable, str(CLI), "--census", str(f.census), "--base-commit", base or f.base,
         "--output", str(output or f.output), "--expected-census-sha256", expected or digest, *extra],
        cwd=f.carrier, env=env or f.env, capture_output=True, text=True,
    )
    return result


def report(f):
    return json.loads(f.output.read_text(encoding="ascii"))


def snapshot(root):
    result = {}
    for path in [root, *root.rglob("*")]:
        info = path.lstat()
        content = (hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode)
                   else os.readlink(path) if stat.S_ISLNK(info.st_mode) else None)
        result[str(path.relative_to(root))] = (info.st_mode, info.st_mtime_ns, content)
    return result


def test_cli_clean_merged_deterministic_and_no_target_mutation(fixture):
    f = fixture
    before = snapshot(f.fleet), snapshot(f.carrier)
    first = run_cli(f)
    assert first.returncode == 0, first.stderr
    initial_bytes, initial_mtime = f.output.read_bytes(), f.output.stat().st_mtime_ns
    second = run_cli(f, env={**f.env, "PYTHONHASHSEED": "78", "GIT_DIR": "/nonexistent",
                             "GIT_INDEX_FILE": str(f.root / "wrong-index"), "GIT_OPTIONAL_LOCKS": "1"})
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert f.output.read_bytes() == initial_bytes
    assert f.output.stat().st_mtime_ns == initial_mtime
    assert (snapshot(f.fleet), snapshot(f.carrier)) == before
    assert not (f.root / "wrong-index").exists()
    result = report(f)
    assert result["decision_counts"] == {"HOLD": 0, "CONDITIONAL_RETIRE_CANDIDATE": 1}
    assert result["comparison_commit"] == f.base
    assert result["source_sha256"] == hashlib.sha256(f.census.read_bytes()).hexdigest()
    entry = result["entries"][0]
    assert entry["source"] == f.data["entries"][0]
    assert entry["source_index"] == 0 and entry["path"] == str(f.target)
    assert entry["ancestry"]["status"] == "ANCESTOR"
    assert not result["mutation_authorized"] and not entry["mutation_authorized"]
    prerequisites = " ".join(entry["apply_prerequisites"])
    for requirement in ("UNMET", "idle", "ignored", "branch/history", "never-behind", "WIP",
                        "bind_terminal_target_identity", "execute_terminal_mutation_once",
                        "fresh fetch", "behind(origin/dev)=0", "no reusable mutation authority",
                        "without blocking unrelated"):
        assert requirement in prerequisites


@pytest.mark.parametrize("case,reason", [
    ("dirty", "dirty_or_unknown"), ("unknown_counts", "dirty_or_unknown"),
    ("false_zero", "dirty_or_unknown"), ("missing", "unavailable_or_non_directory"),
    ("symlink", "unavailable_or_non_directory"), ("non_repository", "not_linked_worktree"),
    ("standalone", "not_linked_worktree"), ("unknown_git", "head_or_branch_uncertain"),
    ("detached", "head_or_branch_uncertain"), ("wrong_common", "repository_identity_uncertain"),
    ("wrong_root", "repository_identity_uncertain"), ("error", "inspection_uncertain"),
    ("locked", "registration_uncertain"), ("prunable", "registration_uncertain"),
    ("registration_drift", "registration_uncertain"), ("registration_unknown", "registration_uncertain"),
    ("unregistered", "registration_uncertain"), ("outside", "outside_direct_fleet"),
    ("bad_observation", "observation_uncertain"),
])
def test_cli_uncertain_and_ineligible_rows_hold(fixture, case, reason):
    f = fixture
    entry = row(f)
    if case == "dirty":
        (f.target / "untracked-evidence").write_text("WIP\n")
        entry["git"].update(dirty_status="dirty", dirty_counts={**ZERO_COUNTS, "entries": 1, "untracked": 1})
    elif case == "unknown_counts":
        entry["git"]["dirty_counts"] = None
    elif case == "false_zero":
        entry["git"]["dirty_counts"]["tracked"] = False
    elif case in ("missing", "symlink"):
        entry.update(availability_status="missing" if case == "missing" else "present", entry_kind=case)
    elif case in ("non_repository", "standalone"):
        entry["repository_kind"] = "standalone_repository" if case == "standalone" else case
    elif case == "unknown_git":
        entry["git"] = None
    elif case == "detached":
        entry["git"].update(branch=None, branch_status="detached")
    elif case in ("wrong_common", "wrong_root"):
        entry["git"]["common_dir" if case == "wrong_common" else "root"] = str(f.root / "other")
    elif case == "error":
        entry["errors"] = [{"operation": "status", "message": "unknown configured filter evidence"}]
    elif case in ("locked", "prunable"):
        entry["registered_worktrees"][0][case] = True
    elif case == "registration_drift":
        entry["registered_worktrees"][0]["HEAD"] = "1" * 40
    elif case == "registration_unknown":
        entry["registered_worktrees"][0]["unknown_future_flag"] = True
    elif case == "unregistered":
        entry.update(sources=["fleet_root"], registered_worktrees=[], registration_status="not_registered")
    elif case == "outside":
        entry.update(path=str(f.root / "outside"), sources=["anchor_worktrees"])
        entry["registered_worktrees"][0]["path"] = entry["path"]
        entry["git"]["root"] = entry["path"]
    elif case == "bad_observation":
        entry["observed_finished_at"] = "unknown"
    before = snapshot(f.fleet)
    result = run_cli(f, inventory(f, [entry, row(f, "WorkingRCX-unrelated-merged")]))
    assert result.returncode == 0, result.stderr
    rows = report(f)["entries"]
    assert rows[0]["decision"] == "HOLD"
    assert reason in {r["code"] for r in rows[0]["reasons"]}
    assert rows[0]["source"] == entry
    assert rows[0]["ancestry"]["status"] == "NOT_PROBED"
    assert rows[1]["decision"] == "CONDITIONAL_RETIRE_CANDIDATE"
    assert snapshot(f.fleet) == before


@pytest.mark.parametrize("name", [
    "WorkingRCX", "WorkingRCX-preservation", "WorkingRCX-preservation/child",
    "WorkingRCX-audit-origin-dev-20260729", "WorkingRCX-admin-source",
    "WorkingRCX-fleet-classification-r1-20260911", "WorkingRCX-fleet-census-r3-20260911",
    "WorkingRCX-workingrcx-fleet-census-builder-r1-20260910",
    "WorkingRCX-workingrcx-fleet-census-builder-r2-20260910",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r1-20260910",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r2-20260911",
    "WorkingRCX-native-stub-phase-b-same-config-relaunch-repair-r3-20260911",
    "WorkingRCX-commit-governance-retry-idempotency-r1-20260910",
    "WorkingRCX-commit-governance-retry-idempotency-r2-20260910",
    "WorkingRCX-commit-supervisor-needs-phase-a-terminal-retry-fence-r1-20260911",
    "WorkingRCX-pr1219-p0ibrrcp-codex-defaults-20260826-r1",
    "WorkingRCX-roles-all-codex-pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-20260823-r2",
    "workingrcx_pr_preservation_20260630", "workingrcx_nbfence",
])
def test_cli_protected_evidence_holds_even_when_clean_and_merged(fixture, name):
    entry = row(fixture, name)
    if "/" in name:
        entry["sources"] = ["anchor_worktrees"]
    result = run_cli(fixture, inventory(fixture, [entry]))
    assert result.returncode == 0, result.stderr
    actual = report(fixture)["entries"][0]
    assert actual["decision"] == "HOLD"
    assert "protected_evidence" in {r["code"] for r in actual["reasons"]}


@pytest.mark.parametrize("branch", ["dev", "main", "master"])
def test_cli_protected_branch_holds(fixture, branch):
    entry = row(fixture)
    entry["git"]["branch"] = entry["registered_worktrees"][0]["branch"] = "refs/heads/" + branch
    result = run_cli(fixture, inventory(fixture, [entry]))
    assert result.returncode == 0, result.stderr
    assert "protected_branch" in {r["code"] for r in report(fixture)["entries"][0]["reasons"]}


def test_cli_unmerged_unavailable_and_protected_history_remain_hold(fixture):
    f = fixture
    (f.target / "tracked.txt").write_text("unique unmerged work\n")
    git(f, f.target, "add", "tracked.txt")
    git(f, f.target, "commit", "-qm", "unmerged evidence")
    heads = [git(f, f.target, "rev-parse", "HEAD"), "1" * 40,
             "28081acd74c549a7afd4292351b214228d45f451"]
    rows = [row(f, f"WorkingRCX-history-{i}") for i in range(3)]
    for entry, head in zip(rows, heads):
        entry["git"]["HEAD"] = entry["registered_worktrees"][0]["HEAD"] = head
    before = snapshot(f.fleet)
    result = run_cli(f, inventory(f, rows))
    assert result.returncode == 0, result.stderr
    actual = report(f)["entries"]
    assert all(r["decision"] == "HOLD" for r in actual)
    assert [r["ancestry"]["status"] for r in actual] == ["NOT_ANCESTOR", "UNKNOWN", "NOT_PROBED"]
    assert snapshot(f.fleet) == before


@pytest.mark.parametrize("change", [
    "coverage", "schema", "count", "entries", "duplicate", "path", "sources",
    "registration_count", "fleet_count", "enumeration", "enumeration_error", "observation",
])
def test_cli_rejects_malformed_or_incomplete_inventory(fixture, change):
    f = fixture
    data = deepcopy(f.data)
    if change == "coverage":
        data["coverage_complete"] = False
    elif change == "schema":
        data["schema_version"] = True
    elif change == "count":
        data["entry_count"] += 1
    elif change == "entries":
        data.pop("entries")
    elif change == "duplicate":
        data["entries"].append(deepcopy(data["entries"][0]))
        data["entry_count"] += 1
    elif change == "path":
        data["entries"][0]["path"] = ""
    elif change == "sources":
        data["entries"][0]["sources"] = []
    elif change == "registration_count":
        data["enumeration"]["anchor_worktrees"]["records"] += 1
    elif change == "fleet_count":
        data["enumeration"]["fleet_root"]["matching_entries"] = 0
    elif change == "enumeration":
        data["enumeration"].pop("anchor_worktrees")
    elif change == "enumeration_error":
        data["enumeration"]["fleet_root"]["errors"] = [{"error": "incomplete"}]
    elif change == "observation":
        data.pop("finished_at")
    result = run_cli(f, data)
    assert result.returncode == 2 and "classification refused:" in result.stderr
    assert not f.output.exists()


def test_cli_binds_raw_bytes_exact_base_and_landed_source(fixture):
    f = fixture
    assert run_cli(f, expected="0" * 64).returncode == 2
    assert not f.output.exists()
    assert run_cli(f, base="HEAD").returncode == 2
    assert run_cli(f, base="2" * 40).returncode == 2
    f.census = f.root / SOURCE.name
    result = run_cli(f, f.data)  # An explicit fixture hash cannot override the landed filename.
    assert result.returncode == 2 and "SHA-256" in result.stderr
    f.census.write_bytes(SOURCE.read_bytes())  # Read the tracked artifact only, never fleet paths.
    assert hashlib.sha256(f.census.read_bytes()).hexdigest() == LANDED_HASH
    result = run_cli(f, base=f.base, expected=LANDED_HASH)
    assert result.returncode == 2
    assert not f.output.exists()


@pytest.mark.parametrize("kind", ["unrelated", "different_report", "symlink", "hardlink", "target", "git_metadata"])
def test_cli_refuses_output_clobber_or_target_write(fixture, kind):
    f = fixture
    victim = f.root / "unrelated.txt"
    victim.write_text("unrelated valuable evidence\n")
    if kind == "unrelated":
        f.output.write_text("do not overwrite\n")
    elif kind == "different_report":
        assert run_cli(f).returncode == 0
        f.data["entries"][0]["errors"] = [{"message": "new uncertainty"}]
    elif kind == "symlink":
        f.output.symlink_to(victim)
    elif kind == "hardlink":
        os.link(victim, f.output)
    elif kind == "target":
        f.output = f.target / "new-classification.json"
    elif kind == "git_metadata":
        f.output = f.primary / ".git/new-classification.json"
    before = snapshot(f.fleet), victim.read_bytes()
    old_output = f.output.read_bytes() if f.output.exists() else None
    result = run_cli(f, f.data)
    assert result.returncode == 2
    assert (snapshot(f.fleet), victim.read_bytes()) == before
    assert (f.output.read_bytes() if f.output.exists() else None) == old_output


@pytest.mark.parametrize("probe_failure", ["none", "ancestry", "config"])
@pytest.mark.parametrize("legacy_git", [False, True], ids=["current-git", "git-2.43"])
def test_cli_queries_only_local_carrier_with_fetch_and_writes_disabled(fixture, probe_failure, legacy_git):
    f = fixture
    bindir = f.root / "bin"
    bindir.mkdir()
    log = f.root / "git-queries.jsonl"
    wrapper = bindir / "git"
    wrapper.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        f"if {legacy_git!r} and '--no-lazy-fetch' in sys.argv:\n"
        "    sys.stderr.write('unknown option: --no-lazy-fetch\\nusage: git <command> [<args>]\\n'); sys.exit(129)\n"
        f"assert sys.argv[sys.argv.index('-C') + 1] == {str(f.carrier)!r}\n"
        "args = sys.argv[sys.argv.index('-C') + 2:]\n"
        "assert args[0] in ('rev-parse', 'config', 'cat-file', 'merge-base')\n"
        "assert '--no-optional-locks' in sys.argv\n"
        "assert 'protocol.allow=never' in sys.argv\n"
        "assert os.environ['GIT_ALLOW_PROTOCOL'] == ''\n"
        "assert os.environ['GIT_NO_LAZY_FETCH'] == '1'\n"
        "assert os.environ['GIT_OPTIONAL_LOCKS'] == '0'\n"
        "assert os.environ['GIT_NO_REPLACE_OBJECTS'] == '1'\n"
        "assert os.environ['GIT_CONFIG_NOSYSTEM'] == '1'\n"
        "assert os.environ['GIT_CONFIG_GLOBAL'] == os.devnull\n"
        f"with open({str(log)!r}, 'a') as out: out.write(json.dumps(args) + '\\n')\n"
        f"if {probe_failure == 'config'!r} and args[0] == 'config':\n"
        "    sys.stderr.write('inconclusive local configuration query\\n'); sys.exit(128)\n"
        f"if {probe_failure == 'ancestry'!r} and args == ['merge-base', '--is-ancestor', {f.base!r}, {f.base!r}]:\n"
        "    sys.stderr.write('inconclusive local object query\\n'); sys.exit(128)\n"
        f"if {legacy_git!r}: os.environ.pop('GIT_NO_LAZY_FETCH', None)\n"
        f"os.execv({f.git!r}, [{f.git!r}, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o700)
    marker = f.root / "ambient-filter-ran"
    home = f.root / "ambient-home"
    home.mkdir()
    (home / ".gitconfig").write_text(f'[filter "ambient"]\n clean = touch {marker}\n process = touch {marker}\n')
    before = snapshot(f.fleet), snapshot(f.carrier)
    result = run_cli(f, env={**f.env, "PATH": str(bindir) + os.pathsep + f.env["PATH"],
                             "GIT_ALLOW_PROTOCOL": "file:https", "GIT_NO_LAZY_FETCH": "0",
                             "HOME": str(home), "XDG_CONFIG_HOME": str(home)})
    assert not marker.exists() and (snapshot(f.fleet), snapshot(f.carrier)) == before
    queries = [json.loads(line) for line in log.read_text().splitlines()]
    assert [query[0] for query in queries[:2]] == ["rev-parse", "config"]
    if probe_failure == "config":
        assert result.returncode == 2
        assert "read-only, no-fetch carrier" in result.stderr
        assert not f.output.exists()
        assert len(queries) == 2
        return
    assert result.returncode == 0, result.stderr
    assert ["merge-base", "--is-ancestor", f.base, f.base] in queries
    entry = report(f)["entries"][0]
    assert entry["decision"] == ("HOLD" if probe_failure == "ancestry" else "CONDITIONAL_RETIRE_CANDIDATE")
    assert entry["ancestry"]["status"] == ("UNKNOWN" if probe_failure == "ancestry" else "ANCESTOR")


@pytest.mark.parametrize("settings", [
    [("extensions.partialClone", "missing")],
    [("remote.missing.partialCloneFilter", "blob:none")],
    [("remote.missing.promisor", "false")],
    [("remote.missing.promisor", "true"), ("remote.missing.promisor", "false")],
], ids=["extension", "filter-only", "false-promisor", "duplicate-promisor"])
def test_cli_legacy_git_refuses_promisor_configuration_before_object_queries(fixture, legacy_git_env, settings):
    f = fixture
    for key, value in settings:
        git(f, f.carrier, "config", "--add", key, value)
    before = snapshot(f.fleet), snapshot(f.carrier)
    result = run_cli(f, env=legacy_git_env)
    assert result.returncode == 2
    assert "read-only, no-fetch carrier" in result.stderr
    assert not f.output.exists()
    queries = [json.loads(line) for line in (f.root / "legacy-git-queries.jsonl").read_text().splitlines()]
    assert [query[0] for query in queries] == ["rev-parse", "config"]
    assert (snapshot(f.fleet), snapshot(f.carrier)) == before


@pytest.mark.parametrize("missing_comparison_base", [False, True], ids=["recorded-head", "comparison-base"])
def test_cli_legacy_git_cannot_lazy_fetch_through_protocol_override(fixture, legacy_git_env, missing_comparison_base):
    f = fixture
    bindir = f.root / "bin"
    marker = f.root / "fetch-helper-ran"
    helper = bindir / "git-remote-classification"
    helper.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('implicit fetch attempted\\n')\n"
        "raise SystemExit(1)\n"
    )
    helper.chmod(0o700)
    git(f, f.carrier, "config", "remote.missing.url", "classification::missing")
    git(f, f.carrier, "config", "remote.missing.promisor", "true")
    git(f, f.carrier, "config", "protocol.classification.allow", "always")
    missing_head = "1" * 40
    # Prove this fixture attempts a fetch despite the generic protocol ban.
    probe = subprocess.run(
        [f.git, "-c", "protocol.allow=never", "-C", str(f.carrier), "cat-file", "-t", missing_head],
        env=legacy_git_env, stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
    )
    assert probe.returncode != 0 and marker.exists(), probe.stderr
    marker.unlink()
    entry = row(f)
    entry["git"]["HEAD"] = entry["registered_worktrees"][0]["HEAD"] = missing_head
    before = snapshot(f.fleet), snapshot(f.carrier)
    result = run_cli(f, inventory(f, [entry, row(f, "WorkingRCX-local-merged")]),
                     base=missing_head if missing_comparison_base else f.base, env=legacy_git_env)
    assert not marker.exists()
    assert (snapshot(f.fleet), snapshot(f.carrier)) == before
    assert result.returncode == 2
    assert "read-only, no-fetch carrier" in result.stderr
    assert not f.output.exists()


def test_cli_legacy_git_does_not_import_objects_from_local_promisor(fixture, legacy_git_env):
    f = fixture
    remote = f.root / "remote"
    remote.mkdir()
    git(f, remote, "init", "-q")
    (remote / "remote-only.txt").write_text("object absent from the carrier\n")
    git(f, remote, "add", "remote-only.txt")
    git(f, remote, "commit", "-qm", "remote-only evidence")
    remote_head = git(f, remote, "rev-parse", "HEAD")
    git(f, remote, "config", "uploadpack.allowFilter", "true")
    git(f, f.carrier, "config", "remote.missing.url", remote.as_uri())
    git(f, f.carrier, "config", "remote.missing.promisor", "true")
    git(f, f.carrier, "config", "protocol.file.allow", "always")
    entry = row(f)
    entry["git"]["HEAD"] = entry["registered_worktrees"][0]["HEAD"] = remote_head
    before = snapshot(f.fleet), snapshot(f.carrier), snapshot(remote)
    result = run_cli(f, inventory(f, [entry, row(f, "WorkingRCX-local-merged")]),
                     env={**legacy_git_env, "GIT_ALLOW_PROTOCOL": "file", "GIT_NO_LAZY_FETCH": "0"})
    assert result.returncode == 2
    assert "read-only, no-fetch carrier" in result.stderr
    assert not f.output.exists()
    assert (snapshot(f.fleet), snapshot(f.carrier), snapshot(remote)) == before


def test_cli_accounts_for_all_recorded_categories_in_remapped_disposable_inventory(fixture):
    f = fixture
    source = json.loads(SOURCE.read_bytes())
    real_root = source["fleet_root"]
    def remap(value):
        if isinstance(value, str):
            return value.replace(real_root, str(f.fleet)).replace("/private/tmp/", str(f.root / "outside") + "/")
        if isinstance(value, list):
            return [remap(v) for v in value]
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        return value
    data = remap(source)
    # Keep recorded shapes/categories/errors; use only disposable local objects.
    for entry in data["entries"]:
        for identity in [entry["git"], *entry["registered_worktrees"]]:
            if identity.get("HEAD"):
                identity["HEAD"] = f.base
    before = snapshot(f.fleet)
    result = run_cli(f, data)
    assert result.returncode == 0, result.stderr
    actual = report(f)
    assert actual["entry_count"] == 411
    assert sum(actual["decision_counts"].values()) == 411
    assert [r["source_index"] for r in actual["entries"]] == list(range(411))
    assert [r["source"] for r in actual["entries"]] == data["entries"]
    assert sum(r["source"]["availability_status"] == "missing" for r in actual["entries"]) == 89
    assert {r["source"]["repository_kind"] for r in actual["entries"]} == {
        "linked_worktree", "standalone_repository", "non_repository", "unknown"}
    assert all(r["decision"] == "HOLD" for r in actual["entries"]
               if r["source"]["availability_status"] == "missing"
               or r["source"]["git"]["dirty_status"] != "clean")
    assert snapshot(f.fleet) == before
