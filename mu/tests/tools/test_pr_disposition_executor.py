"""Focused, fully mocked GitHub tests for the fixed PR disposition executor."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from mu.tests.tools.module_loader import load_module


REPO_ROOT = Path(__file__).resolve().parents[3]
EXECUTOR_PATH = REPO_ROOT / "mu" / "tools" / "executors" / "pr_disposition_executor.py"
MANIFEST_PATH = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "pr-disposition-executor-enabler-r1-2026-09-09_targets.json"
)
disposition = load_module("pr_disposition_executor", EXECUTOR_PATH)

GOLDEN_REPOSITORY = {
    "id": "R_kgDOQvy8bg",
    "nameWithOwner": "jabramsja/rcx-pi-core",
    "url": "https://github.com/jabramsja/rcx-pi-core",
}
GOLDEN_HEAD_REPOSITORY = {
    "id": "R_kgDOQvy8bg",
    "owner": {"id": "MDQ6VXNlcjI3MjU3NDg3", "login": "jabramsja"},
}
GOLDEN_TARGET_ROWS = (
    (1219, "PR_kwDOQvy8bs74MpV0", "jabramsja/roles-all-codex-current-dev-2026-07-29", "28081acd74c549a7afd4292351b214228d45f451"),
    (1213, "PR_kwDOQvy8bs7wx1P-", "jabramsja/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12", "28b9beed3b8fbc793058446bf9854f363b82ead5"),
    (1212, "PR_kwDOQvy8bs7wnEHo", "jabramsja/codex-reviewer-56sol-ultra-2026-07-11", "b6eb91a61439c2cb3a08f377d0d07a69546fd7db"),
    (1211, "PR_kwDOQvy8bs7t2Sw3", "jabramsja/never-behind-checkignore-fence-2026-07-04", "10d157c4eb5b667b07006686fea86d88af268646"),
    (1210, "PR_kwDOQvy8bs7t02-L", "jabramsja/never-behind-stash-ff-hold-surface-2026-07-04", "b846d2e93be9ffbd3e25b30c1b7983ceb52c4ae7"),
    (1203, "PR_kwDOQvy8bs7tral-", "jabramsja/post-reentry-defer-not-loop-2026-07-03", "4c466d1001b838e69ce141801fbbbe35f410d466"),
    (1197, "PR_kwDOQvy8bs7tS-PM", "jabramsja/pager-route-claude-2026-07-01", "02d6900ec39c3bd9da1e95e7cf0ae5507e4c7f92"),
    (1196, "PR_kwDOQvy8bs7s8IjQ", "jabramsja/roles-claude-opus-2026-07-01", "1131ae748dc373f0a96f0d0875a40d4e3ccc68ba"),
)


def _golden_targets() -> list[dict]:
    return [
        {
            "baseRefName": "dev",
            "headRefName": branch,
            "headRefOid": head,
            "headRepository": copy.deepcopy(GOLDEN_HEAD_REPOSITORY),
            "id": node_id,
            "mergedAt": None,
            "number": number,
            "state": "OPEN",
        }
        for number, node_id, branch, head in GOLDEN_TARGET_ROWS
    ]


def _canonical_bytes(value: object, *, pretty: bool = True) -> bytes:
    options = {"allow_nan": False, "ensure_ascii": False, "sort_keys": True}
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return (json.dumps(value, **options) + ("\n" if pretty else "")).encode()


def _seal(value: dict, field: str) -> dict:
    sealed = copy.deepcopy(value)
    sealed.pop(field, None)
    digest = hashlib.sha256(_canonical_bytes(sealed, pretty=False)).hexdigest()
    sealed[field] = digest
    return sealed


def _write_canonical(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _exact_snapshot(target: dict, *, state: str) -> dict:
    pr = copy.deepcopy(target)
    pr["state"] = state
    pr["mergedAt"] = None
    pr["headRepository"]["nameWithOwner"] = "jabramsja/rcx-pi-core"
    return {
        "node": {
            "headRef": {
                "name": target["headRefName"],
                "prefix": "refs/heads/",
                "target": {"oid": target["headRefOid"], "type": "Commit"},
            },
            "pullRequest": copy.deepcopy(pr),
            "repository": copy.deepcopy(GOLDEN_REPOSITORY),
            "type": "PullRequest",
        },
        "pr": pr,
        "repository": copy.deepcopy(GOLDEN_REPOSITORY),
    }


def _git(args: list[str], *, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=False, text=True
    )
    assert proc.returncode == 0, (args, proc.stdout, proc.stderr)
    return proc.stdout.strip()


def _init_apply_repo(tmp_path: Path) -> tuple[Path, Path, str, Path]:
    repo = tmp_path / "apply-repo"
    repo.mkdir()
    _git(["init"], cwd=repo)
    _git(["config", "user.email", "tests@example.invalid"], cwd=repo)
    _git(["config", "user.name", "Disposition Tests"], cwd=repo)
    manifest = repo / disposition.MANIFEST_RELATIVE_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(MANIFEST_PATH.read_bytes())
    _git(["add", str(disposition.MANIFEST_RELATIVE_PATH)], cwd=repo)
    _git(["commit", "-m", "manifest comparison"], cwd=repo)
    comparison = _git(["rev-parse", "HEAD"], cwd=repo)
    common = (repo / _git(["rev-parse", "--git-common-dir"], cwd=repo)).resolve()
    receipts = tmp_path / "receipts"
    return repo, manifest, comparison, common


def _filesystem_identity(path: Path) -> dict:
    info = path.stat()
    return {"device": info.st_dev, "inode": info.st_ino, "path": str(path.resolve())}


class FakeBind:
    def __init__(self, *, common: Path, comparison: str, events: list[str]):
        self.common = common
        self.comparison = comparison
        self.events = events
        self.calls = 0

    def __call__(self, repo_root: Path, *, base_branch: str) -> dict:
        self.calls += 1
        self.events.append(f"bind:{self.calls}")
        return {
            "authority": "identity_only_not_terminal_authority",
            "base_branch": base_branch,
            "base_ref": f"origin/{base_branch}",
            "bound": True,
            "common_dir_identity": _filesystem_identity(self.common),
            "expected_branch": "apply-wave",
            "expected_head": self.comparison,
            "operation_id": f"{self.calls:032x}",
            "reason": None,
            "version": 2,
            "worktree_identity": _filesystem_identity(repo_root),
        }


class FakeBoundary:
    def __init__(self, *, common: Path, events: list[str]):
        self.common = common
        self.events = events
        self.calls = 0
        self.inside_callback = False
        self.crash_before_callback = False
        self.crash_before_callback_on_call: int | None = None
        self.crash_after_callback = False
        self.hold_before_callback = False

    def _intent_for(self, operation_id: str) -> tuple[Path, dict]:
        root = self.common / disposition.INTENT_ROOT_NAME / disposition.WAVE_ID
        matches = []
        for path in root.glob("pr-*.json"):
            value = json.loads(path.read_text())
            if value.get("operation_id") == operation_id:
                matches.append((path, value))
        assert len(matches) == 1
        return matches[0]

    def __call__(
        self,
        repo_root: Path,
        identity: dict,
        *,
        terminal_action,
        log,
    ) -> dict:
        del repo_root, log
        self.calls += 1
        path, intent = self._intent_for(identity["operation_id"])
        assert intent["state"] == "PREPARED"
        self.events.append(
            f"execute:{intent['target']['number']}:{intent['state']}:{path.name}"
        )
        if self.hold_before_callback:
            return {
                "action_error": None,
                "action_invoked": False,
                "action_succeeded": None,
                "authority_consumed": False,
                "decision": "HOLD",
                "operation_id": identity["operation_id"],
                "reason": "mock terminal readiness hold",
            }
        if self.crash_before_callback or self.crash_before_callback_on_call == self.calls:
            raise SimulatedCrash("interrupted before authority callback")
        self.inside_callback = True
        try:
            outcome = terminal_action()
            if self.crash_after_callback:
                raise SimulatedCrash("interrupted after authority callback")
        finally:
            self.inside_callback = False
        return {
            "action_error": None,
            "action_invoked": True,
            "action_outcome": outcome,
            "action_succeeded": True,
            "authority_consumed": True,
            "decision": "ACTION_COMPLETED",
            "operation_id": identity["operation_id"],
            "reason": None,
        }


class SimulatedCrash(BaseException):
    pass


class FakeGh:
    def __init__(
        self,
        *,
        boundary: FakeBoundary,
        common: Path,
        events: list[str],
    ):
        self.boundary = boundary
        self.common = common
        self.events = events
        self.states = {target["number"]: "OPEN" for target in disposition.EXPECTED_TARGETS}
        self.head_overrides: dict[int, str] = {}
        self.close_calls: list[int] = []
        self.close_assignments: list[list[str]] = []
        self.close_queries: list[str] = []
        self.crash_after_close_for: int | None = None
        self.postverify_failure_for: int | None = None
        self.remote_snapshot_overrides: dict[tuple[str, ...], object] = {}
        self._postverify_failure_pending = False

    @staticmethod
    def _completed(args, value: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, json.dumps(value), "")

    @staticmethod
    def _assignment(args: tuple[str, ...], name: str) -> str:
        prefix = f"{name}="
        return next(item[len(prefix) :] for item in args if item.startswith(prefix))

    def _actual_target(self, target: dict) -> dict:
        actual = copy.deepcopy(target)
        actual["state"] = self.states[target["number"]]
        actual["mergedAt"] = None
        if target["number"] in self.head_overrides:
            actual["headRefOid"] = self.head_overrides[target["number"]]
        return actual

    def _apply_remote_snapshot_overrides(self, source: str, payload: dict) -> None:
        for path, value in self.remote_snapshot_overrides.items():
            if not path or path[0] != source:
                continue
            raw_path = list(path[1:])
            if source == "node" and raw_path[:1] == ["pullRequest"]:
                raw_path = raw_path[1:]
            if raw_path[:2] == ["headRepository", "owner"]:
                raw_path = ["headRepositoryOwner", *raw_path[2:]]
            cursor = payload
            for key in raw_path[:-1]:
                cursor = cursor[key]
            cursor[raw_path[-1]] = value

    def _pr_payload(self, target: dict, *, apply_overrides: bool = True) -> dict:
        actual = self._actual_target(target)
        owner = actual["headRepository"]["owner"]
        payload = {
            "baseRefName": actual["baseRefName"],
            "headRefName": actual["headRefName"],
            "headRefOid": actual["headRefOid"],
            "headRepository": {
                "id": actual["headRepository"]["id"],
                # This matches the live `gh pr view --json headRepository`
                # payload: the number-addressed view can omit the repository
                # name even though the node-addressed GraphQL view supplies it.
                "nameWithOwner": "",
            },
            "headRepositoryOwner": copy.deepcopy(owner),
            "id": actual["id"],
            "mergedAt": actual["mergedAt"],
            "number": actual["number"],
            "state": actual["state"],
        }
        if apply_overrides:
            self._apply_remote_snapshot_overrides("pr", payload)
        return payload

    def _node_payload(self, target: dict) -> dict:
        actual = self._actual_target(target)
        pr = self._pr_payload(target, apply_overrides=False)
        payload = {
            "__typename": "PullRequest",
            **pr,
            "headRepository": {
                "id": actual["headRepository"]["id"],
                "nameWithOwner": disposition.REPOSITORY_NAME,
                "ref": {
                    "name": actual["headRefName"],
                    "prefix": "refs/heads/",
                    "target": {"__typename": "Commit", "oid": actual["headRefOid"]},
                },
            },
            "repository": copy.deepcopy(disposition.EXPECTED_REPOSITORY),
        }
        self._apply_remote_snapshot_overrides("node", payload)
        return payload

    def _target_from_node(self, node_id: str) -> dict:
        return next(target for target in disposition.EXPECTED_TARGETS if target["id"] == node_id)

    def __call__(self, args, cwd: Path) -> subprocess.CompletedProcess[str]:
        del cwd
        args = tuple(args)
        location = "callback" if self.boundary.inside_callback else "post"
        if args[:3] == ("gh", "repo", "view"):
            self.events.append(f"gh-repo:{location}")
            if location == "post" and self._postverify_failure_pending:
                self._postverify_failure_pending = False
                return subprocess.CompletedProcess(args, 1, "", "mock postverify failure")
            return self._completed(args, copy.deepcopy(disposition.EXPECTED_REPOSITORY))
        if args[:3] == ("gh", "pr", "view"):
            number = int(args[3])
            assert args[args.index("--repo") + 1] == disposition.REPOSITORY_NAME
            self.events.append(f"gh-pr:{number}:{location}")
            return self._completed(args, self._pr_payload(disposition.TARGET_BY_NUMBER[number]))
        assert args[:3] == ("gh", "api", "graphql")
        query = next(item[6:] for item in args if item.startswith("query="))
        node_id = self._assignment(args, "id")
        target = self._target_from_node(node_id)
        assert self._assignment(args, "headRef") == f"refs/heads/{target['headRefName']}"
        if "closePullRequest" in query:
            assert self.boundary.inside_callback
            assignments = [item for item in args if item.startswith(("id=", "headRef=", "number="))]
            assert assignments == [
                f"id={target['id']}",
                f"headRef=refs/heads/{target['headRefName']}",
            ]
            intent_path = (
                self.common
                / disposition.INTENT_ROOT_NAME
                / disposition.WAVE_ID
                / f"pr-{target['number']}.json"
            )
            assert json.loads(intent_path.read_text())["state"] == (
                "CALLBACK_VALIDATED_CLOSE_PENDING"
            )
            self.events.append(f"close-node:{target['number']}")
            self.close_calls.append(target["number"])
            self.close_assignments.append(assignments)
            self.close_queries.append(query)
            self.states[target["number"]] = "CLOSED"
            if self.postverify_failure_for == target["number"]:
                self._postverify_failure_pending = True
            if self.crash_after_close_for == target["number"]:
                raise SimulatedCrash("interrupted after close reached remote")
            return self._completed(
                args,
                {"data": {"closePullRequest": {"pullRequest": self._node_payload(target)}}},
            )
        self.events.append(f"gh-node:{target['number']}:{location}")
        return self._completed(args, {"data": {"node": self._node_payload(target)}})


def _apply_fixture(tmp_path: Path):
    repo, manifest, comparison, common = _init_apply_repo(tmp_path)
    events: list[str] = []
    boundary = FakeBoundary(common=common, events=events)
    binder = FakeBind(common=common, comparison=comparison, events=events)
    gh = FakeGh(boundary=boundary, common=common, events=events)
    receipts = tmp_path / "receipts"
    return repo, manifest, comparison, common, receipts, events, binder, boundary, gh


def _run_apply(fixture):
    repo, manifest, comparison, _common, receipts, _events, binder, boundary, gh = fixture
    result = disposition.apply_dispositions(
        manifest,
        comparison_commit=comparison,
        repo_root=repo,
        receipts_dir=receipts,
        gh_runner=gh,
        bind_target_identity=binder,
        execute_terminal_once=boundary,
        log=lambda _message: None,
    )
    return result


def test_contract_check_accepts_only_literal_self_hashed_manifest(tmp_path):
    result = disposition.contract_check(MANIFEST_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert result["decision"] == "CONTRACT_OK"
    assert result["targets"] == [1219, 1213, 1212, 1211, 1210, 1203, 1197, 1196]
    assert result["target_count"] == 8
    assert disposition.EXPECTED_REPOSITORY == GOLDEN_REPOSITORY
    assert list(disposition.EXPECTED_TARGETS) == _golden_targets()
    assert manifest["repository"] == GOLDEN_REPOSITORY
    assert manifest["targets"] == _golden_targets()

    original = manifest
    for name, mutate in (
        (
            "ninth",
            lambda value: value["targets"].append(
                {**copy.deepcopy(value["targets"][-1]), "number": 1195}
            ),
        ),
        (
            "substituted",
            lambda value: value["targets"][0].update({"headRefOid": "f" * 40}),
        ),
        (
            "boolean-schema",
            lambda value: value.update({"schema_version": True}),
        ),
        (
            "float-number",
            lambda value: value["targets"][0].update({"number": 1219.0}),
        ),
    ):
        changed = copy.deepcopy(original)
        mutate(changed)
        changed = _seal(changed, "manifest_sha256")
        path = tmp_path / f"{name}.json"
        _write_canonical(path, changed)
        with pytest.raises(disposition.ContractError, match="literal repository"):
            disposition.validate_manifest_contract(path)

    with pytest.raises(disposition.ContractError, match="repository must be exactly"):
        disposition.contract_check(MANIFEST_PATH, repository="someone/else")


def test_apply_rejects_manifest_not_committed_at_comparison(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], cwd=repo)
    _git(["config", "user.email", "tests@example.invalid"], cwd=repo)
    _git(["config", "user.name", "Disposition Tests"], cwd=repo)
    (repo / "marker").write_text("comparison without manifest\n")
    _git(["add", "marker"], cwd=repo)
    _git(["commit", "-m", "comparison"], cwd=repo)
    comparison = _git(["rev-parse", "HEAD"], cwd=repo)
    manifest = repo / disposition.MANIFEST_RELATIVE_PATH
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(MANIFEST_PATH.read_bytes())

    def forbidden(*_args, **_kwargs):
        raise AssertionError("no bind or mutation may follow ancestry rejection")

    with pytest.raises(disposition.ContractError, match="not tracked"):
        disposition.apply_dispositions(
            manifest,
            comparison_commit=comparison,
            repo_root=repo,
            receipts_dir=tmp_path / "receipts",
            gh_runner=forbidden,
            bind_target_identity=forbidden,
            execute_terminal_once=forbidden,
        )


def test_apply_rejects_a_live_peer_before_bind_or_network(tmp_path):
    fixture = _apply_fixture(tmp_path)
    repo, manifest, comparison, _common, receipts, _events, _binder, _boundary, _gh = fixture
    entered = threading.Event()
    release = threading.Event()
    background_errors: list[BaseException] = []

    def blocking_bind(*_args, **_kwargs):
        entered.set()
        if not release.wait(timeout=5):
            raise AssertionError("timed out waiting to release the live-peer fixture")
        raise SimulatedCrash("release the live-peer fixture without creating an intent")

    def hold_lock():
        try:
            disposition.apply_dispositions(
                manifest,
                comparison_commit=comparison,
                repo_root=repo,
                receipts_dir=receipts,
                gh_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("background live-peer fixture reached GitHub")
                ),
                bind_target_identity=blocking_bind,
                execute_terminal_once=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    AssertionError("background live-peer fixture reached execution")
                ),
            )
        except BaseException as exc:  # expected simulated stop after lock proof
            background_errors.append(exc)

    peer = threading.Thread(target=hold_lock)
    peer.start()
    assert entered.wait(timeout=5), "background apply did not acquire the wave lock"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("live-peer rejection reached a dependency seam")

    try:
        with pytest.raises(disposition.ContractError, match="another fixed-wave"):
            disposition.apply_dispositions(
                manifest,
                comparison_commit=comparison,
                repo_root=repo,
                receipts_dir=receipts,
                gh_runner=forbidden,
                bind_target_identity=forbidden,
                execute_terminal_once=forbidden,
            )
    finally:
        release.set()
        peer.join(timeout=5)
    assert not peer.is_alive()
    assert len(background_errors) == 1
    assert isinstance(background_errors[0], SimulatedCrash)


def test_apply_rejects_out_of_order_durable_state_before_mutation(tmp_path):
    fixture = _apply_fixture(tmp_path)
    repo, manifest, comparison, common, receipts, events, binder, boundary, gh = fixture
    boundary.crash_before_callback_on_call = 2
    with pytest.raises(SimulatedCrash):
        _run_apply(fixture)
    assert binder.calls == boundary.calls == 2
    assert gh.close_calls == [1219]

    intent_root = common / disposition.INTENT_ROOT_NAME / disposition.WAVE_ID
    (intent_root / "pr-1219.json").unlink()
    (receipts / "pr-1219.json").unlink()

    def forbidden_bind(*_args, **_kwargs):
        raise AssertionError("out-of-order preflight must not bind or mutate")

    with pytest.raises(disposition.ContractError, match="out of manifest order"):
        disposition.apply_dispositions(
            manifest,
            comparison_commit=comparison,
            repo_root=repo,
            receipts_dir=receipts,
            gh_runner=gh,
            bind_target_identity=forbidden_bind,
            execute_terminal_once=boundary,
        )
    assert boundary.calls == 2
    assert gh.close_calls == [1219]
    assert events.count("bind:1") == 1
    assert events.count("bind:2") == 1


def test_apply_orders_callback_local_reads_intent_and_exact_node_close(tmp_path):
    fixture = _apply_fixture(tmp_path)
    result = _run_apply(fixture)
    _repo, _manifest, _comparison, common, receipts, events, binder, boundary, gh = fixture

    assert result["decision"] == "VERIFIED"
    assert result["has_hold"] is False
    assert set(result["statuses"].values()) == {"CLOSED"}
    assert binder.calls == boundary.calls == 8
    assert gh.close_calls == list(disposition.EXPECTED_NUMBERS)
    assert len(gh.close_assignments) == 8
    assert len(gh.close_queries) == 8
    assert all(query.count("closePullRequest(") == 1 for query in gh.close_queries)
    assert all("pullRequestId: $id" in query for query in gh.close_queries)
    for forbidden_field in (
        "addComment(",
        "createPullRequestReview(",
        "deleteRef(",
        "mergePullRequest(",
        "updatePullRequest(",
    ):
        assert all(forbidden_field not in query for query in gh.close_queries)

    first_execute = events.index("execute:1219:PREPARED:pr-1219.json")
    first_repo_read = events.index("gh-repo:callback")
    first_pr_read = events.index("gh-pr:1219:callback")
    first_node_read = events.index("gh-node:1219:callback")
    first_close = events.index("close-node:1219")
    first_post = events.index("gh-pr:1219:post")
    assert first_execute < first_repo_read < first_pr_read < first_node_read < first_close < first_post
    assert not any(event.startswith("gh-") for event in events[:first_execute])

    intent = json.loads(
        (
            common
            / disposition.INTENT_ROOT_NAME
            / disposition.WAVE_ID
            / "pr-1219.json"
        ).read_text()
    )
    assert intent["state"] == "CLOSE_RESPONSE_OBSERVED"
    assert intent["target"] == disposition.TARGET_BY_NUMBER[1219]
    assert intent["manifest_sha256"] == result["manifest_sha256"]
    assert (
        intent["callback_snapshot"]["pr"]["headRepository"]["nameWithOwner"]
        == ""
    )
    node_head_repository = intent["callback_snapshot"]["node"]["pullRequest"][
        "headRepository"
    ]
    assert node_head_repository["nameWithOwner"] == disposition.REPOSITORY_NAME
    assert (receipts / "pr-1219.json").is_file()


@pytest.mark.parametrize(
    ("path", "invalid_value", "expected_error"),
    [
        (
            ("pr", "headRepository", "nameWithOwner"),
            None,
            "number-addressed PR immutable or expected-state drift",
        ),
        (
            ("pr", "headRepository", "nameWithOwner"),
            "someone/else",
            "number-addressed PR immutable or expected-state drift",
        ),
        (
            ("pr", "headRepository", "id"),
            "R_foreign",
            "number-addressed PR immutable or expected-state drift",
        ),
        (
            ("pr", "headRepository", "owner", "login"),
            "someone-else",
            "number-addressed PR immutable or expected-state drift",
        ),
        (
            ("node", "pullRequest", "headRepository", "nameWithOwner"),
            "",
            "node-addressed PR immutable or expected-state drift",
        ),
    ],
)
def test_number_addressed_head_repository_name_exception_is_exact(
    tmp_path, path, invalid_value, expected_error
):
    fixture = _apply_fixture(tmp_path)
    gh = fixture[-1]
    gh.remote_snapshot_overrides[path] = invalid_value

    result = _run_apply(fixture)

    receipt = json.loads((fixture[4] / "pr-1219.json").read_text())
    assert result["statuses"]["1219"] == "HOLD_REMOTE_DRIFT"
    assert expected_error in receipt["terminal"]["drift"]
    assert gh.close_calls == []


def test_remote_drift_consumes_no_close_and_shared_stops_peers(tmp_path):
    fixture = _apply_fixture(tmp_path)
    gh = fixture[-1]
    gh.head_overrides[1219] = "f" * 40
    result = _run_apply(fixture)
    receipts = fixture[4]
    boundary = fixture[-2]

    assert result["has_hold"] is True
    assert result["statuses"]["1219"] == "HOLD_REMOTE_DRIFT"
    assert set(result["statuses"].values()) == {
        "HOLD_REMOTE_DRIFT",
        "HOLD_SHARED_UNATTEMPTED",
    }
    assert gh.close_calls == []
    assert boundary.calls == 1
    first = json.loads((receipts / "pr-1219.json").read_text())
    assert first["intent"]["state"] == "REMOTE_DRIFT_NO_ACTION"
    for number in disposition.EXPECTED_NUMBERS[1:]:
        peer = json.loads((receipts / f"pr-{number}.json").read_text())
        assert peer["status"] == "HOLD_SHARED_UNATTEMPTED"
        assert peer["operation_id"] is None
        assert peer["intent_path"] is None


def test_postverify_failure_holds_consumed_action_and_shared_stops_peers(tmp_path):
    fixture = _apply_fixture(tmp_path)
    gh = fixture[-1]
    gh.postverify_failure_for = 1219
    result = _run_apply(fixture)
    receipts = fixture[4]
    boundary = fixture[-2]

    assert result["statuses"]["1219"] == "HOLD_ACTION_OR_POSTVERIFY"
    assert all(
        result["statuses"][str(number)] == "HOLD_SHARED_UNATTEMPTED"
        for number in disposition.EXPECTED_NUMBERS[1:]
    )
    assert gh.close_calls == [1219]
    assert boundary.calls == 1
    root = json.loads((receipts / "pr-1219.json").read_text())
    assert root["intent"]["state"] == "CLOSE_RESPONSE_OBSERVED"
    assert root["terminal"]["boundary"]["authority_consumed"] is True
    assert root["after"]["error"] == root["terminal"]["postverify_error"]

    tampered = tmp_path / "postverify-error-tamper"
    shutil.copytree(receipts, tampered)
    path = tampered / "pr-1219.json"
    changed = json.loads(path.read_text())
    changed["terminal"]["postverify_error"] = "different error"
    _write_canonical(path, _seal(changed, "receipt_sha256"))
    with pytest.raises(disposition.ContractError, match="does not match after"):
        disposition.verify_receipts(
            fixture[1], comparison_commit=fixture[2], receipts_dir=tampered
        )


def test_boundary_hold_never_enters_callback_and_shared_stops_peers(tmp_path):
    fixture = _apply_fixture(tmp_path)
    boundary = fixture[-2]
    gh = fixture[-1]
    boundary.hold_before_callback = True
    result = _run_apply(fixture)

    assert result["statuses"]["1219"] == "HOLD_ACTION_OR_POSTVERIFY"
    assert all(
        result["statuses"][str(number)] == "HOLD_SHARED_UNATTEMPTED"
        for number in disposition.EXPECTED_NUMBERS[1:]
    )
    assert boundary.calls == 1
    assert gh.close_calls == []
    assert not any(event.startswith("gh-") and ":callback" in event for event in fixture[5])
    root = json.loads((fixture[4] / "pr-1219.json").read_text())
    assert root["intent"]["state"] == "PREPARED"
    assert root["before"] is None
    assert root["terminal"]["boundary"]["authority_consumed"] is False


def test_restart_never_replays_prepared_intent_and_emits_complete_holds(tmp_path):
    fixture = _apply_fixture(tmp_path)
    boundary = fixture[-2]
    boundary.crash_before_callback = True
    with pytest.raises(SimulatedCrash):
        _run_apply(fixture)

    common = fixture[3]
    intent_path = (
        common / disposition.INTENT_ROOT_NAME / disposition.WAVE_ID / "pr-1219.json"
    )
    assert json.loads(intent_path.read_text())["state"] == "PREPARED"
    assert not (fixture[4] / "pr-1219.json").exists()

    repo, manifest, comparison, _common, receipts, events, _binder, _boundary, _gh = fixture
    restart_boundary = FakeBoundary(common=common, events=events)
    restart_gh = FakeGh(boundary=restart_boundary, common=common, events=events)

    def forbidden_bind(*_args, **_kwargs):
        raise AssertionError("shared no-replay restart must not allocate another operation")

    result = disposition.apply_dispositions(
        manifest,
        comparison_commit=comparison,
        repo_root=repo,
        receipts_dir=receipts,
        gh_runner=restart_gh,
        bind_target_identity=forbidden_bind,
        execute_terminal_once=restart_boundary,
        log=lambda _message: None,
    )
    assert restart_boundary.calls == 0
    assert restart_gh.close_calls == []
    assert result["statuses"]["1219"] == "HOLD_ACTION_OR_POSTVERIFY"
    assert all(
        result["statuses"][str(number)] == "HOLD_SHARED_UNATTEMPTED"
        for number in disposition.EXPECTED_NUMBERS[1:]
    )


def test_restart_reconciles_close_after_interruption_without_replay(tmp_path):
    fixture = _apply_fixture(tmp_path)
    gh = fixture[-1]
    gh.crash_after_close_for = 1219
    with pytest.raises(SimulatedCrash):
        _run_apply(fixture)
    assert gh.close_calls == [1219]

    repo, manifest, comparison, common, receipts, events, _binder, _boundary, _gh = fixture
    restart_boundary = FakeBoundary(common=common, events=events)
    restart_binder = FakeBind(common=common, comparison=comparison, events=events)
    restart_binder.calls = 1
    restart_gh = FakeGh(boundary=restart_boundary, common=common, events=events)
    restart_gh.states[1219] = "CLOSED"
    result = disposition.apply_dispositions(
        manifest,
        comparison_commit=comparison,
        repo_root=repo,
        receipts_dir=receipts,
        gh_runner=restart_gh,
        bind_target_identity=restart_binder,
        execute_terminal_once=restart_boundary,
        log=lambda _message: None,
    )

    assert result["has_hold"] is False
    assert result["statuses"]["1219"] == "CLOSED_RECONCILED"
    assert restart_gh.close_calls == list(disposition.EXPECTED_NUMBERS[1:])
    assert 1219 not in restart_gh.close_calls
    assert restart_boundary.calls == 7
    reconciled = json.loads((receipts / "pr-1219.json").read_text())
    assert reconciled["terminal"]["kind"] == "RESTART_INTENT_RECONCILIATION"
    assert reconciled["after"]["pr"]["state"] == "CLOSED"

    tampered = tmp_path / "reconciled-before-tamper"
    shutil.copytree(receipts, tampered)
    path = tampered / "pr-1219.json"
    changed = json.loads(path.read_text())
    changed["before"] = None
    _write_canonical(path, _seal(changed, "receipt_sha256"))
    with pytest.raises(disposition.ContractError, match="before proof differs"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=tampered
        )


def test_restart_remote_drift_intent_reconciles_external_exact_close_without_replay(tmp_path):
    fixture = _apply_fixture(tmp_path)
    boundary = fixture[-2]
    gh = fixture[-1]
    gh.head_overrides[1219] = "f" * 40
    boundary.crash_after_callback = True
    with pytest.raises(SimulatedCrash):
        _run_apply(fixture)
    assert gh.close_calls == []

    repo, manifest, comparison, common, receipts, events, _binder, _boundary, _gh = fixture
    intent = json.loads(
        (
            common
            / disposition.INTENT_ROOT_NAME
            / disposition.WAVE_ID
            / "pr-1219.json"
        ).read_text()
    )
    assert intent["state"] == "REMOTE_DRIFT_NO_ACTION"

    restart_boundary = FakeBoundary(common=common, events=events)
    restart_binder = FakeBind(common=common, comparison=comparison, events=events)
    restart_binder.calls = 1
    restart_gh = FakeGh(boundary=restart_boundary, common=common, events=events)
    restart_gh.states[1219] = "CLOSED"

    result = disposition.apply_dispositions(
        manifest,
        comparison_commit=comparison,
        repo_root=repo,
        receipts_dir=receipts,
        gh_runner=restart_gh,
        bind_target_identity=restart_binder,
        execute_terminal_once=restart_boundary,
        log=lambda _message: None,
    )
    assert restart_boundary.calls == 7
    assert restart_gh.close_calls == list(disposition.EXPECTED_NUMBERS[1:])
    assert result["statuses"]["1219"] == "CLOSED_RECONCILED"
    root = json.loads((receipts / "pr-1219.json").read_text())
    assert root["terminal"]["kind"] == "RESTART_INTENT_RECONCILIATION"
    assert root["after"]["pr"]["state"] == "CLOSED"


def test_verify_rejects_missing_tamper_duplicate_and_contradiction(tmp_path):
    fixture = _apply_fixture(tmp_path)
    result = _run_apply(fixture)
    manifest, comparison, receipts = fixture[1], fixture[2], fixture[4]
    assert result["has_hold"] is False

    missing = tmp_path / "missing"
    shutil.copytree(receipts, missing)
    (missing / "pr-1196.json").unlink()
    with pytest.raises(disposition.ContractError, match="not exactly eight"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=missing
        )

    tampered = tmp_path / "tampered"
    shutil.copytree(receipts, tampered)
    value = json.loads((tampered / "pr-1219.json").read_text())
    value["status"] = "HOLD_ACTION_OR_POSTVERIFY"
    _write_canonical(tampered / "pr-1219.json", value)
    with pytest.raises(disposition.ContractError, match="self-hash mismatch"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=tampered
        )

    duplicate = tmp_path / "duplicate"
    shutil.copytree(receipts, duplicate)
    first = json.loads((duplicate / "pr-1219.json").read_text())
    second_path = duplicate / "pr-1213.json"
    second = json.loads(second_path.read_text())
    second["operation_id"] = first["operation_id"]
    second["intent"]["operation_id"] = first["operation_id"]
    second["intent"]["terminal_target_identity"]["operation_id"] = first["operation_id"]
    second["terminal"]["boundary"]["operation_id"] = first["operation_id"]
    _write_canonical(second_path, _seal(second, "receipt_sha256"))
    with pytest.raises(disposition.ContractError, match="duplicate operation id"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=duplicate
        )

    spliced = tmp_path / "spliced-common-dir"
    shutil.copytree(receipts, spliced)
    second_path = spliced / "pr-1213.json"
    second = json.loads(second_path.read_text())
    foreign_common = Path("/foreign-pr-disposition-common-dir")
    second["intent"]["terminal_target_identity"]["common_dir_identity"][
        "path"
    ] = str(foreign_common)
    second["intent_path"] = str(
        foreign_common
        / disposition.INTENT_ROOT_NAME
        / disposition.WAVE_ID
        / "pr-1213.json"
    )
    _write_canonical(second_path, _seal(second, "receipt_sha256"))
    with pytest.raises(disposition.ContractError, match="one common-dir identity"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=spliced
        )

    contradictory = tmp_path / "contradictory"
    shutil.copytree(receipts, contradictory)
    receipt_path = contradictory / "pr-1219.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["after"]["pr"]["state"] = "OPEN"
    _write_canonical(receipt_path, _seal(receipt, "receipt_sha256"))
    with pytest.raises(disposition.ContractError, match="after:"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=contradictory
        )


def test_verify_rejects_resealed_hold_tamper_and_invalid_shared_suffix(tmp_path):
    work = tmp_path / "drift-source"
    work.mkdir()
    fixture = _apply_fixture(work)
    source_result = _run_apply(fixture)
    assert source_result["has_hold"] is False
    attempted_after_root = json.loads(
        (fixture[4] / "pr-1213.json").read_text()
    )

    shutil.rmtree(
        fixture[3] / disposition.INTENT_ROOT_NAME / disposition.WAVE_ID
    )
    shutil.rmtree(fixture[4])
    repo, manifest, comparison, common, receipts = fixture[:5]
    events: list[str] = []
    boundary = FakeBoundary(common=common, events=events)
    binder = FakeBind(common=common, comparison=comparison, events=events)
    gh = FakeGh(boundary=boundary, common=common, events=events)
    fixture = (
        repo,
        manifest,
        comparison,
        common,
        receipts,
        events,
        binder,
        boundary,
        gh,
    )
    fixture[-1].head_overrides[1219] = "f" * 40
    result = _run_apply(fixture)
    manifest, comparison, receipts = fixture[1], fixture[2], fixture[4]
    assert result["statuses"]["1219"] == "HOLD_REMOTE_DRIFT"

    def rejected_copy(name, number, mutate, match):
        directory = tmp_path / name
        shutil.copytree(receipts, directory)
        path = directory / f"pr-{number}.json"
        receipt = json.loads(path.read_text())
        mutate(receipt)
        _write_canonical(path, _seal(receipt, "receipt_sha256"))
        with pytest.raises(disposition.ContractError, match=match):
            disposition.verify_receipts(
                manifest, comparison_commit=comparison, receipts_dir=directory
            )

    rejected_copy(
        "bad-hold-observation",
        1219,
        lambda receipt: receipt.update({"after": {}}),
        "remote-drift after",
    )
    rejected_copy(
        "foreign-intent",
        1219,
        lambda receipt: receipt["intent"].update({"wave_id": "foreign-wave"}),
        "intent wave_id mismatch",
    )
    rejected_copy(
        "numeric-boundary-boolean",
        1219,
        lambda receipt: receipt["terminal"]["boundary"].update(
            {"action_invoked": 1}
        ),
        "action_invoked is invalid",
    )
    rejected_copy(
        "orphan-shared-trigger",
        1213,
        lambda receipt: receipt["terminal"].update({"trigger_pr": 1213}),
        "contradicts the root HOLD",
    )

    extra = tmp_path / "extra-receipt"
    shutil.copytree(receipts, extra)
    (extra / "unexpected.txt").write_text("not a governed receipt\n")
    with pytest.raises(disposition.ContractError, match="not exactly eight"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=extra
        )

    attempted = tmp_path / "attempted-after-root"
    shutil.copytree(receipts, attempted)
    _write_canonical(attempted / "pr-1213.json", attempted_after_root)
    with pytest.raises(disposition.ContractError, match="attempted after shared-stop"):
        disposition.verify_receipts(
            manifest, comparison_commit=comparison, receipts_dir=attempted
        )


def test_contract_check_and_verify_never_invoke_subprocess_or_gh(tmp_path, monkeypatch):
    fixture = _apply_fixture(tmp_path)
    result = _run_apply(fixture)
    assert result["decision"] == "VERIFIED"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("read-only contract/verify mode invoked subprocess")

    monkeypatch.setattr(disposition.subprocess, "run", forbidden)
    assert disposition.contract_check(MANIFEST_PATH)["decision"] == "CONTRACT_OK"
    verified = disposition.verify_receipts(
        fixture[1], comparison_commit=fixture[2], receipts_dir=fixture[4]
    )
    assert verified["decision"] == "VERIFIED"
    assert verified["receipt_count"] == 8


def _terminal_sweep_fixture(tmp_path: Path):
    fixture = _apply_fixture(tmp_path)
    result = _run_apply(fixture)
    assert result["has_hold"] is False
    repo, manifest, comparison, common, receipts, _events, _binder, _boundary, gh = fixture
    _git(["branch", "apply-r2-carrier", comparison], cwd=repo)
    packet = repo / "reports" / "control_plane" / "apply-r2-packet.md"
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text("# exact Apply R2 packet\n", encoding="utf-8")
    packet_sha = hashlib.sha256(packet.read_bytes()).hexdigest()
    candidate_sha = "a" * 64
    prepared = disposition.prepare_terminal_sweep_receipt(
        repo,
        carrier_root=repo,
        wave_id=disposition.TERMINAL_SWEEP_WAVE_ID,
        merge_sha=comparison,
        carrier_commit_sha=comparison,
        target_branch="apply-r2-carrier",
        base_branch="master",
        candidate_sha256=candidate_sha,
        manifest_path=manifest,
        packet_path=packet,
        receipts_dir=receipts,
        comparison_commit=comparison,
        expected_packet_sha256=packet_sha,
        expected_candidate_sha256=candidate_sha,
        gh_runner=gh,
    )
    return fixture, prepared


def test_terminal_sweep_pass_survives_carrier_cleanup_and_binds_exact_evidence(
    tmp_path,
):
    fixture, prepared = _terminal_sweep_fixture(tmp_path)
    repo, _manifest, comparison, common, _receipts, _events, _binder, _boundary, gh = fixture
    _git(["branch", "-D", "apply-r2-carrier"], cwd=repo)
    finalized = disposition.finalize_terminal_sweep_receipt(
        repo,
        prepared,
        cleanup_result={
            "branch_deleted": True,
            "worktree_removed": False,
            "stashes_dropped": 0,
            "warnings": [],
        },
        gh_runner=gh,
    )

    assert finalized["receipt"]["decision"] == "PASS"
    assert finalized["receipt"]["route_candidate"] == "fleet-cleanup-builder"
    assert finalized["receipt"]["merge_sha"] == comparison
    assert len(finalized["receipt"]["post_cleanup_evidence"]["intents"]) == 8
    assert len(finalized["receipt"]["post_cleanup_evidence"]["receipts"]) == 8
    assert len(finalized["receipt"]["post_cleanup_evidence"]["remote_observations"]) == 8
    receipt_path = Path(finalized["receipt_path"])
    assert receipt_path.is_relative_to(common)
    assert receipt_path.exists()
    authority = disposition.validate_terminal_receipt_authority(
        repo,
        finalized["binding"],
        expected_merge_sha=comparison,
        expected_candidate="fleet-cleanup-builder",
    )
    assert authority["valid"] is True, authority
    assert authority["decision"] == "PASS"


@pytest.mark.parametrize(
    "evidence_key", ("pre_cleanup_evidence", "post_cleanup_evidence")
)
def test_terminal_receipt_authority_rejects_resealed_non_equivalent_intent(
    tmp_path,
    evidence_key,
):
    fixture, prepared = _terminal_sweep_fixture(tmp_path)
    (
        repo,
        _manifest,
        comparison,
        _common,
        _receipts,
        _events,
        _binder,
        _boundary,
        gh,
    ) = fixture
    _git(["branch", "-D", "apply-r2-carrier"], cwd=repo)
    finalized = disposition.finalize_terminal_sweep_receipt(
        repo,
        prepared,
        cleanup_result={
            "branch_deleted": True,
            "worktree_removed": False,
            "stashes_dropped": 0,
            "warnings": [],
        },
        gh_runner=gh,
    )

    contradictory = copy.deepcopy(finalized["receipt"])
    assert contradictory["decision"] == "PASS"
    contradictory[evidence_key]["intents"][0]["binding_equivalent"] = False
    contradictory = _seal(contradictory, "receipt_sha256")
    receipt_path = Path(finalized["receipt_path"])
    _write_canonical(receipt_path, contradictory)
    resealed_binding = {
        **finalized["binding"],
        "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }

    authority = disposition.validate_terminal_receipt_authority(
        repo,
        resealed_binding,
        expected_merge_sha=comparison,
        expected_candidate="fleet-cleanup-builder",
    )
    assert authority["valid"] is False
    assert authority["decision"] == ""
    assert "intent" in authority["error"]
    assert "binding" in authority["error"]


def test_terminal_sweep_cleanup_mismatch_persists_actual_hold_for_reconciliation(
    tmp_path,
):
    fixture, prepared = _terminal_sweep_fixture(tmp_path)
    repo, _manifest, comparison, _common, _receipts, _events, _binder, _boundary, gh = fixture
    finalized = disposition.finalize_terminal_sweep_receipt(
        repo,
        prepared,
        cleanup_result={
            "branch_deleted": False,
            "worktree_removed": False,
            "stashes_dropped": 0,
            "warnings": ["branch remained"],
        },
        gh_runner=gh,
    )

    assert finalized["receipt"]["decision"] == "HOLD"
    assert finalized["receipt"]["route_candidate"] == "pr-disposition-reconciliation"
    assert any("branch" in error for error in finalized["receipt"]["errors"])
    authority = disposition.validate_terminal_receipt_authority(
        repo,
        finalized["binding"],
        expected_merge_sha=comparison,
        expected_candidate="pr-disposition-reconciliation",
    )
    assert authority["valid"] is True, authority
    assert authority["decision"] == "HOLD"


def test_terminal_receipt_authority_rejects_missing_receipt_and_binding_mismatch(
    tmp_path,
):
    fixture, prepared = _terminal_sweep_fixture(tmp_path)
    repo, _manifest, comparison, _common, _receipts, _events, _binder, _boundary, _gh = fixture
    path = Path(prepared["receipt_path"])
    path.unlink()
    missing_binding = {
        "decision": "PASS",
        "merge_sha": comparison,
        "path": str(
            Path(disposition.TERMINAL_RECEIPT_ROOT_NAME)
            / disposition.TERMINAL_SWEEP_WAVE_ID
            / f"{comparison}.json"
        ),
        "sha256": "b" * 64,
        "wave_id": disposition.TERMINAL_SWEEP_WAVE_ID,
    }
    missing = disposition.validate_terminal_receipt_authority(
        repo, missing_binding, expected_merge_sha=comparison
    )
    assert missing["valid"] is False
    assert "unavailable" in missing["error"]

    mismatched = dict(missing_binding)
    mismatched["merge_sha"] = "c" * 40
    mismatch = disposition.validate_terminal_receipt_authority(
        repo, mismatched, expected_merge_sha=comparison
    )
    assert mismatch["valid"] is False
    assert "merge SHA mismatch" in mismatch["error"]
