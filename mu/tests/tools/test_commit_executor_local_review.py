"""Step15 quota fallback: real Git/classification/CI flow, fake remote/model I/O.

Each disposable carrier has TWO PR commits. No real gh, Codex, merge wrapper,
supervisor or post-merge cleanup process is launched by this module.
Separate candidate fixtures exercise native generated governance in isolated
Git repositories without launching the commit pipeline.
"""
from __future__ import annotations

import copy
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from mu.tests.tools.module_loader import load_module
from tests.repo_root import REPO_ROOT


commit = load_module("commit_executor_local_review", REPO_ROOT / "mu/tools/executors/commit_executor.py")
BUS = ".agent_bus-local-review-test"
QUOTA = "You have reached your Codex usage limits for code reviews."
# Exact complete service notice from the archived live compatibility diagnostic.
SERVICE_QUOTA = (
    "You have reached your Codex usage limits for code reviews. You can see your limits in the "
    "[Codex usage dashboard](https://chatgpt.com/codex/cloud/settings/usage).\n"
    "To continue using code reviews, add credits to your account and enable them for code reviews "
    "in your [settings](https://chatgpt.com/codex/cloud/settings/code-review)."
)
BOT = "chatgpt-codex-connector[bot]"

# PR1332 service payload, saved 2026-10-07. Keep raw bytes (including blank lines).
SERVICE_ACTIVITY_RUNNING = (
    '<!-- codex-pull-request-review-summary -->\n'
    '\n'
    '## Codex Review Summary\n'
    '\n'
    'This comment shows the latest Codex review activity on this pull request.\n'
    '\n'
    '| Review | Status | Commit | Review trigger |\n'
    '| --- | --- | --- | --- |\n'
    '| 📝 **Code Review** | 🔄 **Running** since <relative-time datetime="2026-10-07T21:44:31.317178Z">2026-10-07T21:44:31.317178Z</relative-time> | `b27d1d8` | Manual request |\n'
    '\n'
    '\n'
    '\n'
    '<details> <summary>ℹ️ About Codex in GitHub</summary>\n'
    '<br/>\n'
    '\n'
    '[Your team has set up Codex to review pull requests in this repo](https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you\n'
    '- Open a pull request for review\n'
    '- Mark a draft as ready\n'
    '- Comment "@codex review" or "@codex security review".\n'
    '\n'
    'Codex reacts with 👀 while any review is running, comments if it has suggestions, and reacts with 👍 once all reviews finish with no findings.\n'
    '\n'
    '</details>'
)
SERVICE_ACTIVITY_RUNNING_SHA256 = "618ca236e14153dda36ca9900c48228253d725d31498831bdcb5bb534f0c9321"

# Model the recorded Completed row; the rest is the same exact service body.
SERVICE_ACTIVITY_COMPLETED = SERVICE_ACTIVITY_RUNNING.replace(
    '🔄 **Running** since <relative-time datetime="2026-10-07T21:44:31.317178Z">2026-10-07T21:44:31.317178Z</relative-time>',
    '✅ **Completed** <relative-time datetime="2026-10-07T21:56:09.654997Z">2026-10-07T21:56:09.654997Z</relative-time>',
)

# Complete no-issues response from the same saved completed-control observation.
SERVICE_CLEAR = (
    "Codex Review: Didn't find any major issues. Nice work!\n"
    '\n'
    '**Reviewed commit:** `b27d1d8861`\n'
    '\n'
    '<details> <summary>ℹ️ About Codex in GitHub</summary>\n'
    '<br/>\n'
    '\n'
    '[Your team has set up Codex to review pull requests in this repo](https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you\n'
    '- Open a pull request for review\n'
    '- Mark a draft as ready\n'
    '- Comment "@codex review".\n'
    '\n'
    'If Codex has suggestions, it will comment; otherwise it will react with 👍.\n'
    '\n'
    '\n'
    '\n'
    '\n'
    'Codex can also answer questions or update the PR. Try commenting "@codex address that feedback".\n'
    '            \n'
    '</details>'
)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, text=True,
                          capture_output=True).stdout.strip()


def thread(author=BOT, *, outdated=False):
    return {"id": "thread-1", "isResolved": False, "isOutdated": outdated,
            "comments": {"pageInfo": {"hasPreviousPage": False}, "nodes": [{
                "id": "comment-1", "author": {"login": author, "__typename": "Bot" if author == BOT else "User"}, "body": "P1 still broken",
                "path": "earlier.py", "line": 1, "createdAt": "2026-10-04T13:00:00Z",
            }]}}


class Carrier:
    def __init__(self, root, monkeypatch):
        self.root = root
        self.bus = root / BUS
        self.bus.mkdir()
        self.config_path = root / "mu/tools/executors/executor_config.json"
        self.config_path.parent.mkdir(parents=True)
        self.config = {
            "github_review_quota_fallback": {"enabled": True},
            "role_agents": {"implementer": "codex", "reviewer": "codex"},
            "bridge_agent_defaults": {"codex": {"model": "gpt-6-astra", "reasoning_effort": "max"}},
            "bridge_turn_timeouts": {"phase_b": 900},
        }
        self.config_path.write_text(json.dumps(self.config))
        self.bridge = {"agents": {"codex": {
            "cmd": ["codex", "exec", "-", "--json", "-m", "gpt-6-astra", "-c",
                    'model_reasoning_effort="max"', "--sandbox", "danger-full-access"],
            "timeout_s": 1200, "prompt_via_stdin": True, "env": {}, "mode": "live",
        }}}
        self.bridge_path = self.bus / "bridge_config.json"
        self.bridge_path.write_text(json.dumps(self.bridge))
        (root / ".gitignore").write_text(".agent_bus*/\n.scratch/\n")
        (root / "earlier.py").write_text("value = 0\n")
        (root / "latest.py").write_text("value = 0\n")
        merge_script = root / "mu/tools/hooks/merge_pr.sh"
        merge_script.parent.mkdir(parents=True)
        merge_script.write_text("# Fixture sentinel; must never execute.\n")
        git(root, "init", "-b", "dev")
        git(root, "config", "user.name", "Fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        git(root, "config", "commit.gpgsign", "false")
        git(root, "config", "core.hooksPath", str(root / ".git/fixture-hooks"))
        git(root, "remote", "add", "origin", "https://github.com/fixture/repo.git")
        git(root, "add", ".")
        git(root, "commit", "-m", "base")
        self.base = git(root, "rev-parse", "HEAD")
        git(root, "checkout", "-b", "fixture/quota")
        (root / "earlier.py").write_text("value = 1\n")
        git(root, "add", "earlier.py")
        git(root, "commit", "-m", "earlier PR change")
        (root / "latest.py").write_text("value = 2\n")
        git(root, "add", "latest.py")
        git(root, "commit", "-m", "latest PR change")
        self.head = git(root, "rev-parse", "HEAD")
        self.pr = {
            "number": 1331, "url": "https://github.com/fixture/repo/pull/1331",
            "state": "OPEN", "headRefOid": self.head, "headRefName": "fixture/quota",
            "baseRefOid": self.base, "baseRefName": "dev", "isDraft": False,
            "headRepository": {"nameWithOwner": "fixture/repo"},
            "baseRepository": {"nameWithOwner": "fixture/repo"}, "reviewDecision": "",
            "latestReviews": {"pageInfo": {"hasNextPage": False}, "nodes": []},
            "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": []},
            "comments": {"pageInfo": {"hasPreviousPage": False}, "nodes": [
                {"databaseId": 1, "author": {"login": "founder", "__typename": "User"},
                 "body": "@codex review", "createdAt": "2026-10-04T13:08:00Z"},
                {"databaseId": 2, "author": {"login": BOT, "__typename": "Bot"},
                 "body": QUOTA, "createdAt": "2026-10-04T13:08:19Z"},
            ]},
        }
        self.continuation = self.bus / "continuation.json"
        self.continuation.write_text(json.dumps({"bot_review_request_sha": self.head,
                                                 "bot_review_request_comment_id": 1}))
        self.result = {"pr_number": "1331", "commit_sha": self.head,
                       "steps_completed": ["git_commit", "run_pre_push_script", "git_push", "ensure_pr", "wait_ci"]}
        self.commands, self.reviews, self.landed = [], [], []
        self.on_query = self.after_review = self.after_ci = None
        self.verdict_change = self.output_change = None
        self.adapter_error = None
        self.terminal = "turn.completed"
        self.ci_failure = self.merge_failure = self.merge_queued = False
        self.query_count = 0
        real_run = commit._run  # ANTICHEAT_OK: intercept only subprocess execution boundary
        self.real_run = real_run
        monkeypatch.setattr(commit, "_run", self.run_command)
        monkeypatch.setattr(commit, "_ACTIVE_BUS_DIR", ContextVar("test_bus", default=Path(BUS)))
        adapters = commit._bridge_adapters  # ANTICHEAT_OK: independent model execution boundary
        monkeypatch.setattr(adapters, "run_adapter", self.run_reviewer)
        monkeypatch.setattr(adapters, "_codex_home_is_writable", lambda _: True)
        # Lifecycle and landed closeout are outer-pipeline owners; capture entry.
        monkeypatch.setattr(commit, "record_commit_pr_lifecycle", lambda *a, **k: None)
        monkeypatch.setattr(commit, "_complete_post_merge_pipeline", self.complete)
        for name in ("RCX_REVIEWER_AGENT_OVERRIDE", "RCX_BRIDGE_REVIEWER_OVERRIDE"):
            monkeypatch.delenv(name, raising=False)

    def complete(self, **kwargs):
        self.landed.append(kwargs)
        return {**kwargs["result"], "status": "success", "landed_owner_entered": True}

    def run_command(self, args, **kwargs):
        self.commands.append(list(args))
        if args[0] == "git":
            assert args[1] not in {"push", "fetch", "merge", "commit", "reset", "checkout", "add"}, args
            return self.real_run(args, **kwargs)
        if args[:3] == ["gh", "api", "graphql"]:
            assert "mutation" not in " ".join(args)
            assert "owner=fixture" in args and "repo=repo" in args and "number=1331" in args
            self.query_count += 1
            if self.on_query:
                self.on_query(self.query_count)
            text = json.dumps({"data": {"repository": {"pullRequest": copy.deepcopy(self.pr)}}})
        elif args == ["gh", "api", "repos/fixture/repo/issues/comments/1/reactions"]:
            text = "[]"
        elif args[:3] == ["gh", "pr", "checks"]:
            if "--json" in args:
                text = json.dumps([{"name": "test", "state": "FAILURE" if self.ci_failure else "SUCCESS",
                                    "bucket": "fail" if self.ci_failure else "pass"}])
            else:
                text = "test\tpass\n"
        elif args[:3] == ["gh", "pr", "comment"]:
            assert args[-1] == "@codex review"
            text = "https://github.com/fixture/repo/pull/1331#issuecomment-1\n"
        elif args[:3] == ["gh", "pr", "view"] and "statusCheckRollup" in args:
            if self.after_ci:
                self.after_ci()
                self.after_ci = None
            text = json.dumps({"statusCheckRollup": [
                {"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                for name in commit.EXPECTED_PR_CHECK_SURFACE]})
        elif args[:3] == ["gh", "pr", "merge"]:
            if self.merge_failure:
                raise subprocess.CalledProcessError(1, args, stderr="branch protection blocked merge")
            if not self.merge_queued:
                self.pr.update(state="MERGED", mergeCommit={"oid": "f" * 40})
            text = ""
        elif args[:3] == ["gh", "pr", "ready"]:
            self.pr["isDraft"] = False
            text = ""
        elif args[0] == "bash" and args[1].endswith("merge_pr.sh"):
            text = ""
        else:
            raise AssertionError(f"Unexpected external execution: {args}")
        return subprocess.CompletedProcess(args, 0, text, "")

    def run_reviewer(self, spec, **kwargs):
        self.reviews.append((spec, kwargs))
        if self.adapter_error:
            raise self.adapter_error
        envelope_text = kwargs["prompt_text"].split("BEGIN_AGENT_ENVELOPE\n", 1)[1].split("\nEND_AGENT_ENVELOPE", 1)[0]
        envelope = json.loads(envelope_text)
        envelope.update(decision="GO", summary="Checked the entire two-commit PR diff; no blocking findings.",
                        validations_claimed=[{"command": "read full pr.diff and both changed files", "result": "pass"}])
        if self.verdict_change:
            self.verdict_change(envelope)
        output = "BEGIN_AGENT_ENVELOPE\n" + json.dumps(envelope) + "\nEND_AGENT_ENVELOPE"
        if self.output_change:
            output = self.output_change(output)
        raw = [{"type": "item.completed", "item": {"type": "agent_message", "text": output}},
               {"type": self.terminal}]
        kwargs["raw_output_path"].write_text("\n".join(json.dumps(e) for e in raw) + "\n")
        if self.after_review:
            self.after_review()
        return output

    def execute(self):
        return commit._run_post_commit_pipeline(  # ANTICHEAT_OK: production Step15 entry, not a mocked classifier
            handoff={"wave_id": "quota-fixture"}, repo_root=self.root, result=self.result,
            target_branch="fixture/quota", base_branch="dev", continuation_path=self.continuation,
            log=lambda _: None)

    def receipts(self):
        return [json.loads(p.read_text()) for p in self.bus.glob("meta/local_pr_reviews/*/receipt.json")]

    def assert_stopped(self, outcome, *, reviews=None):
        assert outcome["status"] != "success", outcome
        assert not self.landed
        assert not any(a[:3] == ["gh", "pr", "merge"] or a[0] == "bash" for a in self.commands)
        assert not any("resolveReviewThread" in " ".join(a) for a in self.commands)
        if reviews is not None:
            assert len(self.reviews) == reviews


@pytest.fixture
def carrier(tmp_path, monkeypatch):
    return Carrier(tmp_path, monkeypatch)


@pytest.mark.parametrize("body", [SERVICE_ACTIVITY_RUNNING, SERVICE_ACTIVITY_COMPLETED],
                         ids=["recorded-running", "modeled-completed"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_recorded_activity_survives_each_real_quota_gate(carrier, phase, body):
    assert hashlib.sha256(SERVICE_ACTIVITY_RUNNING.encode()).hexdigest() == SERVICE_ACTIVITY_RUNNING_SHA256
    assert hashlib.sha256(SERVICE_ACTIVITY_COMPLETED.encode()).hexdigest() == (
        "de5ad7c034880671b02814dd349fc3c003267907f90ced43b5b6f15a94f7c9a5")
    comment = {"databaseId": 6047467226, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": "2026-10-04T13:08:20Z"}
    before = carrier.continuation.read_bytes()

    def arrive():
        carrier.pr["comments"]["nodes"].append(copy.deepcopy(comment))

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    outcome = carrier.execute()

    assert outcome["status"] == "success", outcome
    assert carrier.pr["comments"]["nodes"][-1] == comment
    assert carrier.continuation.read_bytes() == before
    # Activity is metadata even for a different commit. Only the genuine,
    # separately authenticated current quota response admits this review.
    assert len(carrier.reviews) == len(carrier.landed) == 1
    assert carrier.receipts()[0]["quota_comment"]["body"] == QUOTA
    assert carrier.receipts()[0]["status"] == "APPROVED"
    merges = [a for a in carrier.commands if a[:3] == ["gh", "pr", "merge"]]
    assert merges == [["gh", "pr", "merge", "1331", "--repo", "fixture/repo", "--merge",
                       "--delete-branch", "--match-head-commit", carrier.head]]
    assert not any(a[0] == "bash" or "--admin" in a for a in carrier.commands)


def _prior_review_bytes(carrier):
    """Pre-existing receipts are immutable on every success and hold path."""
    paths = [carrier.bus / "meta/pre_commit_receipt.json",
             carrier.bus / "meta/pre_commit_receipts/prior.json",
             carrier.bus / "meta/prior_local_review/receipt.json"]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'{"status": "historical", "authority": "spent"}\n')
    return {p: p.read_bytes() for p in [carrier.continuation, *paths]}


def _cloud_clearance(carrier, form="service"):
    carrier.pr["comments"]["nodes"][-1].update(body=SERVICE_QUOTA, createdAt="2026-10-04T13:07:00Z")
    carrier.pr["comments"]["nodes"].append({
        "databaseId": 6047467226, "author": {"login": BOT, "__typename": "Bot"},
        "body": SERVICE_ACTIVITY_COMPLETED, "createdAt": "2026-10-04T13:08:01Z"})
    if form == "formal":
        carrier.pr["latestReviews"]["nodes"] = [{
            "author": {"login": BOT, "__typename": "Bot"}, "state": "APPROVED", "body": "",
            "commit": {"oid": carrier.head}, "submittedAt": "2026-10-04T13:09:00Z"}]
    else:
        # Only this modeled per-carrier commit changes; SERVICE_CLEAR remains
        # the exact offline body captured from PR1332.
        body = (SERVICE_CLEAR.replace("`b27d1d8861`", f"`{carrier.head[:10]}`")
                if form == "service" else "Codex Review: didn't find any major issues.")
        carrier.pr["comments"]["nodes"].append({
            "databaseId": 6047647915, "author": {"login": BOT, "__typename": "Bot"},
            "body": body, "createdAt": "2026-10-04T13:09:00Z"})


@pytest.mark.parametrize("form", ["service", "compact", "formal"])
def test_quota_history_cloud_clearance_uses_protected_exact_head_merge(carrier, form):
    assert hashlib.sha256(SERVICE_CLEAR.encode()).hexdigest() == (
        "7d939bab6b6089e0ea89d069a9e3d8cb37e3df052fa58c7c54dee81a228e816b")
    _cloud_clearance(carrier, form)
    before = _prior_review_bytes(carrier)
    comments = copy.deepcopy(carrier.pr["comments"])

    outcome = carrier.execute()

    assert outcome["status"] == "success", outcome
    assert not carrier.reviews and not carrier.receipts()
    assert carrier.pr["comments"] == comments
    assert all(p.read_bytes() == value for p, value in before.items())
    assert [a for a in carrier.commands if a[:3] == ["gh", "pr", "merge"]] == [
        ["gh", "pr", "merge", "1331", "--repo", "fixture/repo", "--merge",
         "--delete-branch", "--match-head-commit", carrier.head]]
    assert not any(a[0] == "bash" or "--admin" in a or "resolveReviewThread" in " ".join(a)
                   for a in carrier.commands)
    checks = [a for a in carrier.commands if a[:3] == ["gh", "pr", "checks"]]
    assert any("--watch" in a for a in checks) and any("--json" in a for a in checks)
    assert carrier.landed[0]["verified_merge_sha"] == "f" * 40
    assert carrier.landed[0]["review_state"]["headRefOid"] == carrier.head


@pytest.mark.parametrize("mutation", [
    "leading", "trailing", "quoted", "cell", "details", "unknown-row", "header", "separator",
    "unknown-details", "extra-html", "bad-time", "mismatched-time", "bad-commit", "empty-table",
    "completed-cell", "completed-details", "clear-leading", "clear-trailing", "clear-quoted",
    "clear-details", "clear-unknown-details",
])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_complete_activity_with_unknown_content_remains_a_full_finding(carrier, phase, mutation):
    body = SERVICE_ACTIVITY_RUNNING
    defect = "Retained defect in earlier.py. " * 30
    if mutation.startswith("clear-"):
        body = SERVICE_CLEAR
        if mutation == "clear-leading":
            body = defect + "\n" + body
        elif mutation == "clear-trailing":
            body += "\n" + defect
        elif mutation == "clear-quoted":
            body = "> " + body.replace("\n", "\n> ")
        elif mutation == "clear-details":
            body = body.replace("</details>", defect + "\n</details>")
        else:
            body = body.replace("If Codex has suggestions", "If Codex overlooks findings")
    elif mutation == "completed-cell":
        body = SERVICE_ACTIVITY_COMPLETED.replace("Manual request", defect)
    elif mutation == "completed-details":
        body = SERVICE_ACTIVITY_COMPLETED.replace("</details>", defect + "\n</details>")
    elif mutation == "leading":
        body = defect + "\n" + body
    elif mutation == "trailing":
        body += "\n" + defect
    elif mutation == "quoted":
        body = "> " + body.replace("\n", "\n> ")
    elif mutation == "cell":
        body = body.replace("Manual request", "Manual request: " + defect)
    elif mutation == "details":
        body = body.replace("</details>", defect + "\n</details>")
    elif mutation == "unknown-row":
        body = body.replace("**Running**", "**Approved**")
    elif mutation == "header":
        body = body.replace("| Review | Status |", "| Finding | Status |")
    elif mutation == "separator":
        body = body.replace("| --- | --- | --- | --- |", "| --- | --- |")
    elif mutation == "unknown-details":
        body = body.replace("while any review is running", "and clears all findings")
    elif mutation == "extra-html":
        body = body.replace('<relative-time datetime=', '<relative-time data-finding="hidden" datetime=')
    elif mutation == "bad-time":
        body = body.replace("2026-10-07T21:44:31.317178Z", "2026-99-07T21:44:31.317178Z")
    elif mutation == "mismatched-time":
        body = body.replace('>2026-10-07T21:44:31.317178Z', '>2026-10-07T21:44:32.317178Z')
    elif mutation == "bad-commit":
        body = body.replace("`b27d1d8`", "`wrong-head`")
    else:
        body = "\n".join(line for line in body.split("\n") if not line.startswith("| 📝"))
    finding = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": "2026-10-04T13:08:20Z"}
    prior = _prior_review_bytes(carrier)

    def arrive():
        prior.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["comments"]["nodes"].append(copy.deepcopy(finding))

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=int(phase != "initial"))
    assert all(p.read_bytes() == value for p, value in prior.items())
    assert carrier.pr["comments"]["nodes"][-1] == finding
    assert outcome["pr_number"] == "1331"
    if phase == "initial":
        assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
        assert not carrier.receipts()
    else:
        assert repr(body) in outcome["errors"][0]
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")


@pytest.mark.parametrize("phase", ["initial", "ci"])
@pytest.mark.parametrize("failure", [
    "running-only", "completed-only", "stale-clear", "wrong-reviewed-head", "pending-review",
    "empty-commented-review", "stale-formal-approval", "unauthenticated", "wrong-request-id",
    "head-moved", "branch-moved", "repository-moved", "pr-moved", "base-moved",
    "incomplete-comments", "missing-page-info", "new-quota",
    "human-thread", "human-changes", "newer-wrong-head-clear-after-approval",
])
def test_quota_history_cloud_merge_requires_live_clearance(carrier, monkeypatch, phase, failure):
    _cloud_clearance(carrier)
    # The recorded request is fresh; advance only the polling clock, keeping
    # the real freshness/classification functions and all remote I/O fixtures.
    clock = iter([0, 0, *range(10000, 1000000, 10000)])
    monkeypatch.setattr(commit, "time", SimpleNamespace(
        time=lambda: next(clock), sleep=lambda _: None, monotonic=commit.time.monotonic))
    expected_pr = {}

    def invalidate():
        clear = carrier.pr["comments"]["nodes"][-1]
        if failure in {"running-only", "completed-only"}:
            carrier.pr["comments"]["nodes"].pop()
            carrier.pr["comments"]["nodes"][-1]["body"] = (
                SERVICE_ACTIVITY_RUNNING if failure == "running-only" else SERVICE_ACTIVITY_COMPLETED)
        elif failure == "stale-clear":
            clear["createdAt"] = "2026-10-04T13:07:30Z"
        elif failure == "wrong-reviewed-head":
            clear["body"] = SERVICE_CLEAR.replace("`b27d1d8861`", f"`{carrier.base[:10]}`")
        elif failure in {"pending-review", "empty-commented-review", "stale-formal-approval"}:
            carrier.pr["comments"]["nodes"].pop()
            carrier.pr["latestReviews"]["nodes"] = [{
                "author": {"login": BOT, "__typename": "Bot"}, "body": "",
                "state": {"pending-review": "PENDING", "empty-commented-review": "COMMENTED",
                          "stale-formal-approval": "APPROVED"}[failure],
                "commit": {"oid": carrier.base if failure == "stale-formal-approval" else carrier.head},
                "submittedAt": "2026-10-04T13:09:00Z"}]
        elif failure == "unauthenticated":
            clear["author"]["__typename"] = "User"
        elif failure == "wrong-request-id":
            carrier.pr["comments"]["nodes"][0]["databaseId"] = 99
        elif failure == "head-moved":
            carrier.pr["headRefOid"] = carrier.base
        elif failure == "branch-moved":
            carrier.pr["headRefName"] = "fixture/wrong"
        elif failure == "repository-moved":
            carrier.pr["headRepository"]["nameWithOwner"] = "another/repo"
        elif failure == "pr-moved":
            carrier.pr["number"] = 1332
        elif failure == "base-moved":
            carrier.pr["baseRefName"] = "main"
        elif failure == "incomplete-comments":
            carrier.pr["comments"]["pageInfo"]["hasPreviousPage"] = True
        elif failure == "missing-page-info":
            carrier.pr["latestReviews"].pop("pageInfo")
        elif failure == "human-thread":
            carrier.pr["reviewThreads"]["nodes"] = [thread(author="maintainer", outdated=True)]
        elif failure == "human-changes":
            carrier.pr["reviewDecision"] = "CHANGES_REQUESTED"
        elif failure == "newer-wrong-head-clear-after-approval":
            carrier.pr["latestReviews"]["nodes"] = [{
                "author": {"login": BOT, "__typename": "Bot"}, "state": "APPROVED", "body": "",
                "commit": {"oid": carrier.head}, "submittedAt": "2026-10-04T13:08:30Z"}]
            clear["body"] = SERVICE_CLEAR.replace("`b27d1d8861`", f"`{carrier.base[:10]}`")
        elif failure == "new-quota":
            clear["body"] = SERVICE_QUOTA
            # It is not the response to the recorded request: no local-review
            # authority may be inferred from an old request ID.
            carrier.pr["comments"]["nodes"][0]["databaseId"] = 99
        expected_pr.update(copy.deepcopy(carrier.pr))

    before = _prior_review_bytes(carrier)
    if phase == "initial":
        invalidate()
    else:
        carrier.after_ci = invalidate
    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=0)
    assert all(p.read_bytes() == value for p, value in before.items())
    assert carrier.pr == expected_pr
    assert not carrier.receipts()
    assert outcome["step"] == "ensure_review_clear_and_merge"


@pytest.mark.parametrize("changed", ["local-head", "base-object"])
def test_quota_history_rechecks_local_head_and_exact_base_after_ci(carrier, changed):
    _cloud_clearance(carrier)
    prior = _prior_review_bytes(carrier)

    def arrive():
        if changed == "local-head":
            git(carrier.root, "update-ref", "HEAD", carrier.base)
        else:
            carrier.pr["baseRefOid"] = git(carrier.root, "rev-parse", "HEAD^")

    carrier.after_ci = arrive
    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=0)
    assert all(p.read_bytes() == value for p, value in prior.items())
    assert "changed" in " ".join(outcome["errors"])


@pytest.mark.parametrize("mode", ["ci-failure", "blocked", "queued"])
def test_quota_history_protected_merge_never_falls_back_to_admin(carrier, mode):
    _cloud_clearance(carrier)
    carrier.ci_failure = mode == "ci-failure"
    carrier.merge_failure = mode == "blocked"
    carrier.merge_queued = mode == "queued"
    before = _prior_review_bytes(carrier)

    outcome = carrier.execute()

    assert outcome["status"] != "success" and not carrier.landed
    assert not carrier.reviews and not carrier.receipts()
    assert not any(a[0] == "bash" or "--admin" in a for a in carrier.commands)
    merges = [a for a in carrier.commands if a[:3] == ["gh", "pr", "merge"]]
    assert len(merges) == int(mode != "ci-failure")
    if merges:
        assert merges[0][-2:] == ["--match-head-commit", carrier.head]
    assert all(p.read_bytes() == value for p, value in before.items())


@pytest.mark.parametrize("truncated,has_finding,quota_history", [
    (True, True, True), (False, True, True), (False, False, True), (True, False, True),
    (False, False, False),  # Retain the original wrapper assertion on the unrelated legacy lane.
])
@pytest.mark.parametrize("phase", ["initial", "ci"])
def test_later_clear_requires_complete_31_comment_history(carrier, phase, truncated, has_finding, quota_history):
    """The newest 30 comments must not hide the unresolved first comment."""
    clear = {"databaseId": 31, "author": {"login": BOT, "__typename": "Bot"},
             "body": "Codex Review: didn't find any major issues.", "createdAt": "2026-10-04T13:09:00Z"}
    first = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
             "body": "Unresolved defect in earlier.py" if has_finding else clear["body"],
             "createdAt": "2026-10-04T13:07:59Z"}
    controls = [{**clear, "databaseId": n} for n in range(4, 31)]
    history = [first, *copy.deepcopy(carrier.pr["comments"]["nodes"]), *controls, clear]
    history[2]["body"] = SERVICE_QUOTA
    if not quota_history:
        history[2].update(author={"login": "founder", "__typename": "User"}, body="Prior context")
        carrier.pr["comments"]["nodes"][-1] = copy.deepcopy(history[2])
    assert len(history) == 31

    def arrive():
        carrier.pr["comments"] = {"nodes": history[-30:] if truncated else history,
                                  "pageInfo": {"hasPreviousPage": truncated}}

    before = carrier.continuation.read_bytes()
    if phase == "initial":
        arrive()
    else:
        carrier.pr["comments"]["nodes"].append(clear)
        carrier.after_ci = arrive
    outcome = carrier.execute()
    assert carrier.continuation.read_bytes() == before
    assert not carrier.reviews and not carrier.receipts()
    merges = [a for a in carrier.commands if a[0] == "bash" or a[:3] == ["gh", "pr", "merge"]]
    if truncated or has_finding:
        assert not merges, {"outcome": outcome, "merge_commands": merges, "local_reviews": len(carrier.reviews)}
        carrier.assert_stopped(outcome, reviews=0)
        assert outcome["step"] == "ensure_review_clear_and_merge"
        if truncated:
            assert outcome["status"] == "error"
            assert "complete comments evidence" in " ".join(outcome["errors"])
        else:
            assert outcome["status"] == "bot_findings_pending"
            assert [f["body"] for f in outcome["bot_findings"]] == [first["body"]]
    else:
        assert outcome["status"] == "success"
        if quota_history:
            assert merges == [["gh", "pr", "merge", "1331", "--repo", "fixture/repo", "--merge",
                               "--delete-branch", "--match-head-commit", carrier.head]]
            assert carrier.landed[0]["verified_merge_sha"] == "f" * 40
        else:
            assert len(merges) == 1 and merges[0][-1] == "--sweep"


@pytest.mark.parametrize("connection", ["comments", "latestReviews", "reviewThreads", "thread-comments"])
@pytest.mark.parametrize("phase", ["initial", "ci"])
@pytest.mark.parametrize("quota_notice", [False, True])
def test_known_incomplete_evidence_blocks_without_local_review_eligibility(carrier, connection, phase, quota_notice):
    clear = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
             "body": "Codex Review: didn't find any major issues.", "createdAt": "2026-10-04T13:09:00Z"}
    if not quota_notice:
        carrier.pr["comments"]["nodes"].pop()
    carrier.pr["comments"]["nodes"].append(clear)

    def truncate():
        if connection == "thread-comments":
            item = thread()
            item["isResolved"] = True
            item["comments"]["pageInfo"]["hasPreviousPage"] = True
            carrier.pr["reviewThreads"]["nodes"] = [item]
        else:
            flag = "hasPreviousPage" if connection == "comments" else "hasNextPage"
            carrier.pr[connection]["pageInfo"][flag] = True

    if phase == "initial":
        truncate()
    else:
        carrier.after_ci = truncate
    outcome = carrier.execute()
    carrier.assert_stopped(outcome, reviews=0)
    assert outcome["status"] == "error"
    assert "complete" in " ".join(outcome["errors"])


def test_enabled_local_review_full_pr_diff_and_native_ci_merge(carrier):
    quota_before = copy.deepcopy(carrier.pr["comments"])
    continuation_before = carrier.continuation.read_bytes()
    outcome = carrier.execute()
    assert outcome["status"] == "success", outcome
    assert len(carrier.reviews) == len(carrier.landed) == 1
    spec, invocation = carrier.reviews[0]
    assert spec.name == "codex" and spec.timeout_s == 900
    assert spec.cmd[spec.cmd.index("--sandbox") + 1] == "read-only"
    assert spec.cmd[spec.cmd.index("-m") + 1] == "gpt-6-astra"
    assert 'model_reasoning_effort="max"' in spec.cmd and 'approval_policy="never"' in spec.cmd
    assert not invocation.get("stop_after_envelope") and not invocation.get("post_result_exit_timeout_s")
    receipt = carrier.receipts()[0]
    assert receipt["status"] == "APPROVED" and receipt["process_exit_code"] == 0
    assert receipt["identity"]["head_sha"] == carrier.head
    assert receipt["identity"]["base_sha"] == receipt["identity"]["merge_base_sha"] == carrier.base
    diff = invocation["prompt_path"].with_name("pr.diff").read_text()
    assert "earlier.py" in diff and "latest.py" in diff
    assert "+value = 1" in diff and "+value = 2" in diff
    assert receipt["identity"]["diff_sha256"] == hashlib.sha256(diff.encode()).hexdigest()
    assert receipt["envelope"]["decision"] == "GO" and receipt["reviewer"]["effort"] == "max"
    assert receipt["quota_comment"]["databaseId"] == 2
    assert carrier.pr["comments"] == quota_before and carrier.continuation.read_bytes() == continuation_before
    checks = [a for a in carrier.commands if a[:3] == ["gh", "pr", "checks"]]
    assert any("--watch" in a for a in checks) and any("--json" in a for a in checks)
    merge = [a for a in carrier.commands if a[:3] == ["gh", "pr", "merge"]]
    assert merge == [["gh", "pr", "merge", "1331", "--repo", "fixture/repo", "--merge",
                      "--delete-branch", "--match-head-commit", carrier.head]]
    assert carrier.query_count >= 5
    assert not any(a[0] == "bash" or "--admin" in a for a in carrier.commands)
    assert carrier.landed[0]["verified_merge_sha"] == "f" * 40


@pytest.mark.parametrize("policy", [None, {"enabled": False}, {"enabled": "true"}, {"enabled": 1}])
def test_missing_disabled_or_malformed_policy_cannot_review_or_merge(carrier, policy):
    if policy is None:
        carrier.config.pop("github_review_quota_fallback")
    else:
        carrier.config["github_review_quota_fallback"] = policy
    carrier.config_path.write_text(json.dumps(carrier.config))
    carrier.assert_stopped(carrier.execute(), reviews=0)


@pytest.mark.parametrize("decision", ["NO_GO", "REQUEST_CHANGES", "QUESTION", "STALE", "ERROR"])
def test_local_nonapproval_stops_even_on_zero_exit(carrier, decision):
    carrier.verdict_change = lambda e: e.update(decision=decision)
    carrier.assert_stopped(carrier.execute(), reviews=1)
    assert carrier.receipts()[0]["status"] == "ERROR"


@pytest.mark.parametrize("failure", ["nonzero", "timeout", "refusal"])
def test_local_execution_failure_is_terminal_without_retry(carrier, failure):
    adapters = commit._bridge_adapters  # ANTICHEAT_OK: failed model process fixture
    carrier.adapter_error = adapters.BridgeAdapterError(
        {"nonzero": "exited 1", "timeout": "timed out", "refusal": "provider safety refusal"}[failure],
        returncode=1 if failure != "timeout" else -9,
    )
    carrier.assert_stopped(carrier.execute(), reviews=1)
    assert carrier.receipts()[0]["process_exit_code"] != 0


@pytest.mark.parametrize("malformed", ["no_envelope", "two_envelopes", "duplicate_key", "missing_key", "failed_turn", "no_terminal"])
def test_malformed_or_incomplete_review_is_not_approval(carrier, malformed):
    if malformed == "no_envelope":
        carrier.output_change = lambda _: "Review process finished successfully."
    elif malformed == "two_envelopes":
        carrier.output_change = lambda s: s + "\n" + s
    elif malformed == "duplicate_key":
        carrier.output_change = lambda s: s.replace('"decision": "GO"', '"decision": "NO_GO", "decision": "GO"')
    elif malformed == "missing_key":
        carrier.verdict_change = lambda e: e.pop("findings")
    else:
        carrier.terminal = "turn.failed" if malformed == "failed_turn" else "item.completed"
    carrier.assert_stopped(carrier.execute(), reviews=1)


@pytest.mark.parametrize("key", ["repository", "pr_number", "head_sha", "base_sha", "merge_base_sha", "diff_sha256"])
def test_stale_envelope_identity_is_blocking(carrier, key):
    carrier.verdict_change = lambda e: e["review_identity"].update({key: "stale"})
    carrier.assert_stopped(carrier.execute(), reviews=1)


@pytest.mark.parametrize("finding", [
    {"disposition": "blocking", "severity": "medium", "title": "defect"},
    {"disposition": "non_blocking", "severity": "critical", "title": "defect"},
    {"severity": "low", "title": "missing disposition"},
])
def test_findings_cannot_be_hidden_by_go(carrier, finding):
    carrier.verdict_change = lambda e: e.update(findings=[finding])
    carrier.assert_stopped(carrier.execute(), reviews=1)
    receipt = carrier.receipts()[0]
    assert receipt["status"] == "ERROR"
    assert receipt["envelope"]["findings"] == [finding]


@pytest.mark.parametrize("decision", ["GO", "NO_GO", "REQUEST_CHANGES"])
@pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
def test_local_blocking_findings_keep_their_dispositions_without_approval(carrier, decision, severity):
    findings = [
        {"class": "DEFECT", "severity": severity, "disposition": "blocking",
         "title": "retained defect", "file": "earlier.py", "line_start": 1, "line_end": 1,
         "evidence_cmd": "read earlier.py", "evidence_result": "defect remains", "status": "persisting"},
        {"class": "DOC_ACCURACY", "severity": "high", "disposition": "non_blocking",
         "title": "deferred example", "file": "latest.py", "line_start": 1, "line_end": 1,
         "evidence_cmd": "read latest.py", "evidence_result": "example wording", "status": "new"},
    ]
    carrier.verdict_change = lambda e: e.update(decision=decision, findings=copy.deepcopy(findings))
    continuation_before = carrier.continuation.read_bytes()

    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=1)
    receipt = carrier.receipts()[0]
    assert receipt["status"] == "ERROR" and receipt["process_exit_code"] == 0
    assert receipt["envelope"]["decision"] == decision
    assert receipt["envelope"]["findings"] == findings
    assert carrier.continuation.read_bytes() == continuation_before
    assert not any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands)


@pytest.mark.parametrize("kind", ["decision", "human_changes", "human_thread", "human_outdated", "human_then_bot",
                                   "bot_thread", "bot_review", "bot_issue", "plain_bot_issue", "sweep", "malformed_sweep"])
def test_quota_never_masks_existing_human_or_bot_findings(carrier, kind):
    if kind == "decision":
        carrier.pr["reviewDecision"] = "CHANGES_REQUESTED"
    elif kind in {"human_changes", "bot_review"}:
        carrier.pr["latestReviews"]["nodes"] = [{
            "author": {"login": "maintainer" if kind == "human_changes" else BOT,
                       "__typename": "User" if kind == "human_changes" else "Bot"},
            "state": "CHANGES_REQUESTED" if kind == "human_changes" else "COMMENTED",
            "commit": {"oid": carrier.head}, "submittedAt": "2026-10-04T13:07:00Z",
            "body": "![P1 Badge](badge/P1-red) retained finding",
        }]
    elif "thread" in kind or kind in {"human_outdated", "human_then_bot"}:
        value = thread(author=BOT if kind == "bot_thread" else "maintainer", outdated=kind == "human_outdated")
        if kind == "human_then_bot":
            reply = copy.deepcopy(value["comments"]["nodes"][0])
            reply.update(author={"login": BOT, "__typename": "Bot"}, createdAt="2026-10-04T13:01:00Z")
            value["comments"]["nodes"].append(reply)
        carrier.pr["reviewThreads"]["nodes"] = [value]
    elif kind in {"bot_issue", "plain_bot_issue"}:
        old = copy.deepcopy(carrier.pr["comments"]["nodes"][-1])
        old.update(databaseId=3, createdAt="2026-10-04T12:00:00Z", body="![P1 Badge](badge/P1-red) still broken")
        if kind == "plain_bot_issue":
            old.update(createdAt="2026-10-04T13:08:10Z", body="A blocking defect remains in earlier.py")
        carrier.pr["comments"]["nodes"].insert(0, old)
    else:
        path = carrier.bus / "meta/sweep_findings.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"pr": 1200, "path": "earlier.py", "body": "P1 retained"}) + "\n")
        if kind == "malformed_sweep":
            path.write_text("{invalid retained findings\n")
    before = copy.deepcopy(carrier.pr)
    carrier.assert_stopped(carrier.execute(), reviews=0)
    assert carrier.pr == before


@pytest.mark.parametrize("badged", [False, True], ids=["plain", "badged"])
@pytest.mark.parametrize("created_at", [
    "2026-10-04T13:07:59Z", "2026-10-04T13:08:00Z", "2026-10-04T13:08:10Z",
], ids=["before-request", "at-request", "after-request"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_quota_preserves_issue_findings_across_review_requests(carrier, phase, created_at, badged):
    body = ("![P1 Badge](badge/P1-red) " if badged else "") + "A blocking defect remains in earlier.py"
    finding = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": created_at}
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["comments"]["nodes"].insert(0, copy.deepcopy(finding))

    expected_pr = copy.deepcopy(carrier.pr)
    expected_pr["comments"]["nodes"].insert(0, finding)
    continuation_before = carrier.continuation.read_bytes()
    if phase == "initial":
        arrive()
    else:
        # A delayed query result must retain the original finding timestamp.
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr["comments"] == expected_pr["comments"]
    assert carrier.continuation.read_bytes() == continuation_before
    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert carrier.pr == expected_pr
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert body in outcome["errors"][0]
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("body", [
    'A blocking defect remains in earlier.py; the previous response said '
    '"Codex Review: didn\'t find any major issues."',
    "Codex Review: didn't find any major issues.\nA blocking defect remains in earlier.py",
    "A blocking defect remains in earlier.py\nCodex Review: didn't find any major issues.",
    "Codex Review: A blocking defect remains in earlier.py; previously didn't find any major issues.",
    "<!-- codex-pull-request-review-summary -->\nA blocking defect remains in earlier.py",
    "A blocking defect remains in earlier.py",
], ids=["quoted-clear", "clear-prefix", "clear-suffix", "clear-middle", "summary-prefix", "plain"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_later_mixed_clear_cannot_disable_quota_finding_retention(carrier, phase, body):
    finding = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": "2026-10-04T13:08:20Z"}
    expected_pr = copy.deepcopy(carrier.pr)
    expected_pr["comments"]["nodes"].append(finding)
    continuation_before = carrier.continuation.read_bytes()
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["comments"]["nodes"].append(copy.deepcopy(finding))

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr == expected_pr
    assert carrier.continuation.read_bytes() == continuation_before
    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert repr(body) in outcome["errors"][0]
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("service_control", [False, True], ids=["compact", "complete-service"])
@pytest.mark.parametrize("channel", ["issue", "formal", "outdated-thread", "sweep", "malformed-sweep"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci", "ci-after-clear"])
def test_later_clear_preserves_each_quota_finding_channel(carrier, phase, channel, service_control):
    clear = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
             "body": "Codex Review: didn't find any major issues.", "createdAt": "2026-10-04T13:08:20Z"}
    body = "A blocking defect remains in earlier.py"
    if service_control:
        clear["body"] = SERVICE_CLEAR.replace("`b27d1d8861`", f"`{carrier.head[:10]}`")
        body += "\nFull retained finding detail." * 40
        carrier.pr["comments"]["nodes"].append({
            "databaseId": 6047467226, "author": {"login": BOT, "__typename": "Bot"},
            "body": SERVICE_ACTIVITY_COMPLETED, "createdAt": "2026-10-04T13:08:01Z"})
    sweep = carrier.bus / "meta/sweep_findings.json"
    prior_receipts = {}
    expected_pr = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        if phase != "ci-after-clear":
            carrier.pr["comments"]["nodes"].append(copy.deepcopy(clear))
        if channel == "issue":
            carrier.pr["comments"]["nodes"].append({
                "databaseId": 4, "author": {"login": BOT, "__typename": "Bot"},
                "body": body, "createdAt": "2026-10-04T13:07:59Z"})
        elif channel == "formal":
            carrier.pr["latestReviews"]["nodes"].append({
                "author": {"login": BOT, "__typename": "Bot"}, "state": "COMMENTED", "body": body,
                "commit": {"oid": carrier.base}, "submittedAt": "2026-10-04T13:07:59Z"})
        elif channel == "outdated-thread":
            item = thread(outdated=True)
            item["comments"]["nodes"][0]["body"] = body
            carrier.pr["reviewThreads"]["nodes"].append(item)
        else:
            sweep.parent.mkdir(parents=True, exist_ok=True)
            sweep.write_text("{invalid retained findings\n" if channel == "malformed-sweep" else
                             json.dumps({"pr": 1200, "path": "earlier.py", "body": body}) + "\n")
        expected_pr.update(copy.deepcopy(carrier.pr))

    continuation_before = carrier.continuation.read_bytes()
    if phase == "initial":
        arrive()
    else:
        if phase == "ci-after-clear":
            carrier.pr["comments"]["nodes"].append(copy.deepcopy(clear))
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr == expected_pr
    assert carrier.continuation.read_bytes() == continuation_before
    carrier.assert_stopped(outcome, reviews=1 if phase in {"review", "ci"} else 0)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase in {"initial", "ci-after-clear"}:
        assert not carrier.receipts()
        if channel == "malformed-sweep":
            assert outcome["status"] == "error"
            assert "retained sweep findings" in outcome["errors"][0]
        else:
            assert outcome["status"] == "bot_findings_pending"
            assert [f["body"] for f in outcome["bot_findings"]] == [body]
    else:
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")
        assert "retained sweep" in outcome["errors"][0] if "sweep" in channel else (
            repr(body) in outcome["errors"][0] if service_control else body in outcome["errors"][0])
    if "sweep" in channel:
        expected = "{invalid retained findings\n" if channel == "malformed-sweep" else json.dumps({
            "pr": 1200, "path": "earlier.py", "body": body}) + "\n"
        assert sweep.read_text() == expected
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == phase.startswith("ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("body", [
    'A blocking defect remains in earlier.py; the previous response said '
    '"Codex Review: didn\'t find any major issues."',
    "Codex Review: didn't find any major issues.\nA blocking defect remains in earlier.py",
    "A blocking defect remains in earlier.py\nCodex Review: didn't find any major issues.",
    "Codex Review: A blocking defect remains in earlier.py; previously didn't find any major issues.",
    "> Codex Review: didn't find any major issues.\nA blocking defect remains in earlier.py",
    "<!-- codex-pull-request-review-summary -->\nA blocking defect remains in earlier.py",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Completed** | Manual request |\nA blocking defect remains in earlier.py",
    "A blocking defect remains in earlier.py\n<!-- codex-pull-request-review-summary -->\n"
    "## Codex Review Summary\n| Code Review | **Completed** | Manual request |",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Completed** | Manual request: A blocking defect remains in earlier.py |",
], ids=["quoted-clear", "clear-prefix", "clear-suffix", "clear-middle", "quoted-clear-prefix",
        "summary-prefix", "summary-trailing-finding", "summary-leading-finding", "summary-cell-finding"])
@pytest.mark.parametrize("created_at", [
    "2026-10-04T13:07:59Z", "2026-10-04T13:08:10Z",
], ids=["before-request", "after-request"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_quota_mixed_clear_and_summary_comments_keep_findings(carrier, phase, created_at, body):
    finding = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": created_at}
    expected_pr = copy.deepcopy(carrier.pr)
    expected_pr["comments"]["nodes"].append(finding)
    continuation_before = carrier.continuation.read_bytes()
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["comments"]["nodes"].append(copy.deepcopy(finding))

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr["comments"] == expected_pr["comments"]
    assert carrier.continuation.read_bytes() == continuation_before
    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert carrier.pr == expected_pr
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert repr(body) in outcome["errors"][0]
        receipt = carrier.receipts()[0]
        assert receipt["status"] == ("ERROR" if phase == "review" else "APPROVED")
        assert receipt["envelope"]["decision"] == "GO"
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("control_body", [
    "Codex Review: didn't find any major issues",
    "\n CODEX Review:\n did not find any major issues. \n",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Completed** | Manual request |",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Running** | `bbbbbbb` | Manual request |",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Completed** | `bbbbbbb` | Manual request |\n"
    "| Code Review | **Running** | `ccccccc` | Manual request |",
    SERVICE_ACTIVITY_RUNNING,
    SERVICE_ACTIVITY_COMPLETED,
], ids=["clear-no-period", "clear-case-whitespace", "summary", "summary-running", "summary-multiple-jobs",
        "recorded-running", "modeled-completed"])
@pytest.mark.parametrize("has_finding", [False, True])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_standalone_clear_and_activity_controls_preserve_separate_findings(carrier, phase, has_finding, control_body):
    comments = [{"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
                 "body": control_body, "createdAt": "2026-10-04T13:08:10Z"}]
    body = "A blocking defect remains in earlier.py"
    if has_finding:
        comments.append({"databaseId": 4, "author": {"login": BOT, "__typename": "Bot"},
                         "body": body, "createdAt": "2026-10-04T13:07:59Z"})
    expected_comments = copy.deepcopy(carrier.pr["comments"]["nodes"]) + comments
    continuation_before = carrier.continuation.read_bytes()

    def arrive():
        carrier.pr["comments"]["nodes"].extend(copy.deepcopy(comments))

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr["comments"]["nodes"] == expected_comments
    assert carrier.continuation.read_bytes() == continuation_before
    if not has_finding:
        assert outcome["status"] == "success", outcome
        assert len(carrier.reviews) == len(carrier.landed) == 1
        assert carrier.receipts()[0]["status"] == "APPROVED"
    else:
        carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
        if phase == "initial":
            assert outcome["status"] == "bot_findings_pending"
            assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
            assert not carrier.receipts()
        else:
            assert "GitHub findings still block local approval" in outcome["errors"][0]
            assert body in outcome["errors"][0]
            assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")


@pytest.mark.parametrize("body", [
    f'A blocking defect remains in earlier.py; the response says "{QUOTA}"',
    f"{QUOTA}\n\nA blocking defect remains in earlier.py.",
    f"A blocking defect remains in earlier.py.\n\n{QUOTA}",
    f"> {QUOTA}\n\nA blocking defect remains in earlier.py.",
    f'A blocking defect remains in earlier.py; the response says "{SERVICE_QUOTA}"',
    f"{SERVICE_QUOTA}\n\nA blocking defect remains in earlier.py.",
    f"A blocking defect remains in earlier.py.\n\n{SERVICE_QUOTA}",
    f"> {SERVICE_QUOTA}\n\nA blocking defect remains in earlier.py.",
], ids=["quoted", "notice-prefix", "notice-suffix", "blockquote",
        "service-quoted", "service-notice-prefix", "service-notice-suffix", "service-blockquote"])
@pytest.mark.parametrize("created_at", [
    "2026-10-04T13:07:59Z", "2026-10-04T13:08:10Z", "2026-10-04T13:08:20Z",
], ids=["before-request", "before-notice", "after-notice"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_quota_text_inside_issue_findings_never_clears_them(carrier, phase, created_at, body):
    finding = {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
               "body": body, "createdAt": created_at}
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["comments"]["nodes"].append(copy.deepcopy(finding))

    comments_before = copy.deepcopy(carrier.pr["comments"])
    continuation_before = carrier.continuation.read_bytes()
    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)

    outcome = carrier.execute()

    assert carrier.pr["comments"]["nodes"] == comments_before["nodes"] + [finding]
    assert carrier.continuation.read_bytes() == continuation_before
    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{"author": BOT, "body": body, "path": "", "line": None}]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert repr(body) in outcome["errors"][0]
        receipt = carrier.receipts()[0]
        assert receipt["status"] == ("ERROR" if phase == "review" else "APPROVED")
        assert receipt["envelope"]["decision"] == "GO"
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("body", [
    f'A blocking defect remains in earlier.py; the response says "{QUOTA}"',
    f"{QUOTA}\n\nA blocking defect remains in earlier.py.",
    f"A blocking defect remains in earlier.py.\n\n{QUOTA}",
    f"> {QUOTA}\n\nA blocking defect remains in earlier.py.",
    f'A blocking defect remains in earlier.py; the response says "{SERVICE_QUOTA}"',
    f"{SERVICE_QUOTA}\n\nA blocking defect remains in earlier.py.",
    f"A blocking defect remains in earlier.py.\n\n{SERVICE_QUOTA}",
    f"> {SERVICE_QUOTA}\n\nA blocking defect remains in earlier.py.",
])
def test_local_review_entry_rejects_findings_containing_quota_text(carrier, body):
    carrier.pr["comments"]["nodes"][-1]["body"] = body
    before = copy.deepcopy(carrier.pr)
    continuation_before = carrier.continuation.read_bytes()

    with pytest.raises(ValueError, match="authenticated explicit GitHub code-review exhaustion"):
        commit._run_local_quota_review(  # ANTICHEAT_OK: production eligibility boundary
            repo_root=carrier.root, pr_data=carrier.pr, result=carrier.result,
            wave_id="quota-fixture", repo_owner="fixture", repo_name="repo", pr_number="1331",
            head_sha=carrier.head, target_branch="fixture/quota", base_branch="dev",
            continuation_path=carrier.continuation)

    assert carrier.pr == before
    assert carrier.continuation.read_bytes() == continuation_before
    assert not carrier.commands and not carrier.reviews and not carrier.receipts()


@pytest.mark.parametrize("control_body", [
    QUOTA,
    "\n " + QUOTA.lower() + " \n",
    "Codex Review: didn't find any major issues.",
    SERVICE_QUOTA,
    "\n " + SERVICE_QUOTA.lower().replace(".\n", ".\r\n\r\n") + " \n",
], ids=["quota", "quota-case-whitespace", "explicit-clear", "service-quota", "service-case-whitespace"])
@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_standalone_control_messages_remain_valid_at_each_quota_gate(carrier, phase, control_body):
    def arrive():
        carrier.pr["comments"]["nodes"].append({
            "databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
            "body": control_body, "createdAt": "2026-10-04T13:08:20Z",
        })

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    continuation_before = carrier.continuation.read_bytes()

    outcome = carrier.execute()

    assert outcome["status"] == "success", outcome
    assert carrier.pr["comments"]["nodes"][-1]["body"] == control_body
    assert carrier.continuation.read_bytes() == continuation_before
    assert len(carrier.landed) == 1
    local_review_expected = not (phase == "initial" and control_body.startswith("Codex Review:"))
    assert len(carrier.reviews) == int(local_review_expected)
    if local_review_expected:
        assert carrier.receipts()[0]["status"] == "APPROVED"
    else:
        assert not carrier.receipts()


@pytest.mark.parametrize("control_body", [
    QUOTA,
    "Codex Review: didn't find any major issues.",
    "<!-- codex-pull-request-review-summary -->\n## Codex Review Summary\n"
    "| Code Review | **Completed** | Manual request |",
], ids=["quota", "explicit-clear", "activity"])
@pytest.mark.parametrize("has_finding", [False, True])
def test_quota_control_comments_do_not_clear_separate_issue_findings(carrier, control_body, has_finding):
    comments = carrier.pr["comments"]["nodes"]
    comments.insert(0, {"databaseId": 3, "author": {"login": BOT, "__typename": "Bot"},
                        "body": control_body, "createdAt": "2026-10-04T13:08:10Z"})
    if has_finding:
        comments.insert(0, {"databaseId": 4, "author": {"login": BOT, "__typename": "Bot"},
                            "body": "A blocking defect remains in earlier.py",
                            "createdAt": "2026-10-04T13:07:59Z"})
    comments_before = copy.deepcopy(carrier.pr["comments"])
    continuation_before = carrier.continuation.read_bytes()

    outcome = carrier.execute()

    assert carrier.pr["comments"] == comments_before
    assert carrier.continuation.read_bytes() == continuation_before
    if has_finding:
        carrier.assert_stopped(outcome, reviews=0)
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{
            "author": BOT, "body": "A blocking defect remains in earlier.py", "path": "", "line": None,
        }]
        assert not carrier.receipts()
    else:
        assert outcome["status"] == "success", outcome
        assert len(carrier.reviews) == len(carrier.landed) == 1
        assert carrier.receipts()[0]["status"] == "APPROVED"


@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
@pytest.mark.parametrize("prior_commit", [False, True], ids=["current-head", "prior-commit"])
@pytest.mark.parametrize("badged", [False, True], ids=["plain", "badged"])
def test_quota_preserves_formal_bot_findings_at_every_gate(carrier, phase, prior_commit, badged):
    reviewed_head = git(carrier.root, "rev-parse", "HEAD^") if prior_commit else carrier.head
    if prior_commit:
        assert git(carrier.root, "diff", f"{reviewed_head}..{carrier.head}", "--", "earlier.py") == ""
    # Keep evidence beyond the old 500-character cutoff in the returned finding.
    body = ("![P1 Badge](badge/P1-red) " if badged else "") + (
        "A blocking defect remains in earlier.py; fix it before merge. " * 10
    ) + "Retain this final evidence."
    review = {
        "id": "formal-review-1", "author": {"login": BOT, "__typename": "Bot"},
        "state": "COMMENTED", "commit": {"oid": reviewed_head}, "body": body,
        "submittedAt": "2026-10-04T13:08:10Z" if phase == "initial" else "2026-10-04T14:00:00Z",
    }
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["latestReviews"]["nodes"] = [copy.deepcopy(review)]

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    expected_pr = copy.deepcopy(carrier.pr)
    expected_pr["latestReviews"]["nodes"] = [review]
    continuation_before = carrier.continuation.read_bytes()

    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert carrier.pr == expected_pr
    assert carrier.continuation.read_bytes() == continuation_before
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{
            "author": BOT, "body": body, "path": "", "line": None,
            "reviewed_head": reviewed_head, "review_snapshot": review,
        }]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert body in outcome["errors"][0]
        assert reviewed_head in outcome["errors"][0]
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("state,body", [
    ("APPROVED", "Reviewed changes; ready to merge."),
    ("DISMISSED", "A blocking defect remains in earlier.py."),
    ("DISMISSED", "![P1 Badge](badge/P1-red) Dismissed finding."),
    ("COMMENTED", ""),
])
@pytest.mark.parametrize("unresolved_thread", [False, True])
def test_quota_formal_dispositions_do_not_clear_unresolved_threads(carrier, state, body, unresolved_thread):
    carrier.pr["latestReviews"]["nodes"] = [{
        "author": {"login": BOT, "__typename": "Bot"}, "state": state, "body": body,
        "commit": {"oid": git(carrier.root, "rev-parse", "HEAD^")},
        "submittedAt": "2026-10-04T13:08:10Z",
    }]
    if unresolved_thread:
        carrier.pr["reviewThreads"]["nodes"] = [thread(outdated=True)]
    before = copy.deepcopy(carrier.pr)

    outcome = carrier.execute()

    assert carrier.pr["latestReviews"] == before["latestReviews"]
    assert carrier.pr["reviewThreads"] == before["reviewThreads"]
    if unresolved_thread:
        carrier.assert_stopped(outcome, reviews=0)
        assert outcome["status"] == "bot_findings_pending"
        assert not carrier.receipts()
    else:
        assert outcome["status"] == "success", outcome
        assert len(carrier.reviews) == 1 and carrier.receipts()[0]["status"] == "APPROVED"


@pytest.mark.parametrize("state,body", [
    ("CHANGES_REQUESTED", ""),
    ("APPROVED", "![P1 Badge](badge/P1-red) Unresolved finding despite approval."),
])
def test_quota_retains_formal_blockers_despite_empty_body_or_approval(carrier, state, body):
    review = {"author": {"login": BOT, "__typename": "Bot"}, "state": state, "body": body,
              "commit": {"oid": git(carrier.root, "rev-parse", "HEAD^")},
              "submittedAt": "2026-10-04T13:08:10Z"}
    carrier.pr["latestReviews"]["nodes"] = [copy.deepcopy(review)]

    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=0)
    assert outcome["status"] == "bot_findings_pending"
    assert outcome["bot_findings"][0]["review_snapshot"] == review
    assert not carrier.receipts()


@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
def test_quota_preserves_unresolved_outdated_bot_threads(carrier, phase):
    finding_thread = thread(outdated=True)
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        carrier.pr["reviewThreads"]["nodes"] = [copy.deepcopy(finding_thread)]

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    expected_pr = copy.deepcopy(carrier.pr)
    expected_pr["reviewThreads"]["nodes"] = [finding_thread]
    continuation_before = carrier.continuation.read_bytes()
    outcome = carrier.execute()

    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert carrier.pr == expected_pr
    assert carrier.continuation.read_bytes() == continuation_before
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    if phase == "initial":
        assert outcome["status"] == "bot_findings_pending"
        assert outcome["bot_findings"] == [{
            "author": BOT, "body": "P1 still broken", "path": "earlier.py", "line": 1,
            "thread_id": "thread-1", "comment_id": "comment-1",
            "reviewed_head": carrier.head, "thread_snapshot": finding_thread,
        }]
        assert not carrier.receipts()
    else:
        assert "GitHub findings still block local approval" in outcome["errors"][0]
        assert "P1 still broken" in outcome["errors"][0]
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands) == (phase == "ci")
    if phase == "ci":
        assert prior_receipts


@pytest.mark.parametrize("quota_fallback", [False, True])
def test_outdated_bot_threads_keep_existing_clearance_rules(carrier, quota_fallback):
    finding_thread = thread(outdated=True)
    if quota_fallback:
        finding_thread["isResolved"] = True
    else:
        carrier.pr["comments"]["nodes"][-1]["body"] = "Codex Review: didn't find any major issues."
    carrier.pr["reviewThreads"]["nodes"] = [finding_thread]
    before = copy.deepcopy(carrier.pr["reviewThreads"])

    outcome = carrier.execute()

    assert outcome["status"] == "success", outcome
    assert len(carrier.reviews) == int(quota_fallback)
    assert carrier.pr["reviewThreads"] == before


@pytest.mark.parametrize("phase", ["review", "ci"])
@pytest.mark.parametrize("initially_empty", [False, True])
def test_retained_sweep_findings_arriving_during_review_or_ci_block(carrier, phase, initially_empty):
    path = carrier.bus / "meta/sweep_findings.json"
    path.parent.mkdir()
    if initially_empty:
        path.write_text("")
    finding = {"pr": 1200, "path": "earlier.py", "body": "P1 late retained finding",
               "thread_id": "retained-thread"}
    evidence = json.dumps(finding) + "\n"
    prior_receipts = {}

    def arrive():
        prior_receipts.update({p: p.read_bytes() for p in carrier.bus.glob("meta/local_pr_reviews/*/receipt.json")})
        path.write_text(evidence)

    setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    pr_before = copy.deepcopy(carrier.pr)
    continuation_before = carrier.continuation.read_bytes()
    outcome = carrier.execute()
    carrier.assert_stopped(outcome, reviews=1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert "retained sweep findings" in outcome["errors"][0]
    assert path.read_text() == evidence and carrier.pr == pr_before
    assert carrier.continuation.read_bytes() == continuation_before
    assert all(p.read_bytes() == content for p, content in prior_receipts.items())
    receipt = carrier.receipts()[0]
    assert receipt["status"] == ("ERROR" if phase == "review" else "APPROVED")
    if phase == "review":
        assert not any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands)
    else:
        assert prior_receipts
        assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands)


@pytest.mark.parametrize("phase", ["initial", "review", "ci"])
@pytest.mark.parametrize("kind", ["invalid_json", "non_object", "invalid_body", "invalid_utf8",
                                   "unreadable_directory", "dangling_symlink"])
def test_unreadable_or_malformed_retained_sweep_stops_at_each_quota_gate(carrier, phase, kind):
    path = carrier.bus / "meta/sweep_findings.json"
    path.parent.mkdir()
    payload = {
        "invalid_json": b'{"pr": 1200,\n',
        "non_object": b'[]\n',
        "invalid_body": b'{"pr": 1200, "path": "earlier.py", "body": null}\n',
        "invalid_utf8": b'\xff\n',
    }.get(kind)

    def arrive():
        if kind == "unreadable_directory":
            path.mkdir()
        elif kind == "dangling_symlink":
            path.symlink_to("unavailable-sweep-evidence")
        else:
            path.write_bytes(payload)

    if phase == "initial":
        arrive()
    else:
        setattr(carrier, "after_review" if phase == "review" else "after_ci", arrive)
    outcome = carrier.execute()
    carrier.assert_stopped(outcome, reviews=0 if phase == "initial" else 1)
    assert outcome["step"] == "ensure_review_clear_and_merge"
    assert "cannot read retained sweep findings" in outcome["errors"][0]
    if payload is not None:
        assert path.read_bytes() == payload
    elif kind == "dangling_symlink":
        assert path.is_symlink() and path.readlink() == Path("unavailable-sweep-evidence")
    else:
        assert path.is_dir()
    if phase == "initial":
        assert not carrier.receipts()
    else:
        assert carrier.receipts()[0]["status"] == ("ERROR" if phase == "review" else "APPROVED")


def test_empty_retained_sweep_evidence_allows_local_approval(carrier):
    path = carrier.bus / "meta/sweep_findings.json"
    path.parent.mkdir()
    path.write_text("\n \n")
    assert carrier.execute()["status"] == "success"
    assert len(carrier.reviews) == 1 and carrier.receipts()[0]["status"] == "APPROVED"
    assert path.read_text() == "\n \n"


@pytest.mark.parametrize("kind", ["head", "base", "base_branch", "repo", "source", "index", "reviewer_config", "diff", "prompt"])
def test_mutation_during_review_stops_without_cleanup(carrier, kind):
    def mutate():
        if kind in {"head", "base", "base_branch"}:
            carrier.pr[{"head": "headRefOid", "base": "baseRefOid", "base_branch": "baseRefName"}[kind]] = (
                carrier.head if kind == "base" else "a" * 40)
        elif kind == "repo":
            carrier.pr["baseRepository"]["nameWithOwner"] = "other/repo"
        elif kind in {"source", "index"}:
            (carrier.root / "earlier.py").write_text("mutation retained\n")
            if kind == "index":
                git(carrier.root, "add", "earlier.py")
        elif kind == "reviewer_config":
            carrier.bridge_path.write_text(carrier.bridge_path.read_text() + "\n")
        else:
            prompt = carrier.reviews[-1][1]["prompt_path"]
            path = prompt.with_name("pr.diff") if kind == "diff" else prompt
            path.write_text("changed evidence\n")
    carrier.after_review = mutate
    carrier.assert_stopped(carrier.execute(), reviews=1)
    assert carrier.receipts()[0]["status"] == "ERROR"
    if kind in {"source", "index"}:
        assert (carrier.root / "earlier.py").read_text() == "mutation retained\n"


@pytest.mark.parametrize("kind", ["head", "base", "human", "bot", "source", "receipt", "reviewer_config", "request"])
def test_requery_after_ci_invalidates_late_changes(carrier, kind):
    def mutate():
        if kind in {"head", "base"}:
            carrier.pr["headRefOid" if kind == "head" else "baseRefOid"] = (
                "a" * 40 if kind == "head" else carrier.head)
        elif kind in {"human", "bot"}:
            carrier.pr["reviewThreads"]["nodes"] = [thread("maintainer" if kind == "human" else BOT)]
        elif kind == "source":
            (carrier.root / "earlier.py").write_text("late mutation\n")
        elif kind == "reviewer_config":
            carrier.bridge_path.write_text("invalid changed registry")
        elif kind == "request":
            request = copy.deepcopy(carrier.pr["comments"]["nodes"][0])
            request.update(databaseId=999, createdAt="2026-10-04T14:00:00Z")
            carrier.pr["comments"]["nodes"].append(request)
        else:
            path = next(carrier.bus.glob("meta/local_pr_reviews/*/receipt.json"))
            path.write_text(path.read_text() + "\n")
    carrier.after_ci = mutate
    carrier.assert_stopped(carrier.execute(), reviews=1)
    assert any(a[:3] == ["gh", "pr", "checks"] for a in carrier.commands)


@pytest.mark.parametrize("kind", ["reviewer", "model", "effort", "adapter_flag", "adapter_env", "home"])
def test_reviewer_policy_mismatch_never_substitutes_or_repairs(carrier, monkeypatch, kind):
    if kind == "reviewer":
        carrier.config["role_agents"]["reviewer"] = "claude"
    elif kind in {"model", "effort"}:
        carrier.config["bridge_agent_defaults"]["codex"]["model" if kind == "model" else "reasoning_effort"] = "other"
    elif kind == "adapter_flag":
        carrier.bridge["agents"]["codex"]["cmd"].append("--dangerously-bypass-approvals-and-sandbox")
    elif kind == "adapter_env":
        carrier.bridge["agents"]["codex"]["env"] = {"CODEX_HOME": "/alternate/account"}
    else:
        adapters = commit._bridge_adapters  # ANTICHEAT_OK: unavailable execution account fixture
        monkeypatch.setattr(adapters, "_codex_home_is_writable", lambda _: False)
    carrier.config_path.write_text(json.dumps(carrier.config))
    carrier.bridge_path.write_text(json.dumps(carrier.bridge))
    before = carrier.bridge_path.read_bytes()
    carrier.assert_stopped(carrier.execute(), reviews=0)
    assert carrier.bridge_path.read_bytes() == before


@pytest.mark.parametrize("kind", ["request", "request_id", "author", "type", "id", "generic_quota", "pagination", "thread_pagination"])
def test_only_authenticated_current_head_code_review_quota_is_eligible(carrier, kind):
    notice = carrier.pr["comments"]["nodes"][-1]
    if kind == "request":
        carrier.continuation.write_text(json.dumps({"bot_review_request_sha": "a" * 40}))
        # A fresh current-head formal review avoids posting a new request, while
        # the stale native request marker remains ineligible for local authority.
        carrier.pr["latestReviews"]["nodes"] = [{"author": {"login": BOT},
            "commit": {"oid": carrier.head}, "state": "COMMENTED", "body": "",
            "submittedAt": "2026-10-04T13:08:01Z"}]
    elif kind == "request_id":
        carrier.continuation.write_text(json.dumps({"bot_review_request_sha": carrier.head,
                                                   "bot_review_request_comment_id": 99}))
    elif kind == "author":
        # Generic quota prose from a human is not a connector outcome.
        notice["author"]["login"] = "maintainer"
        extracted = commit._current_head_connector_issue_comment_outcome(  # ANTICHEAT_OK: production author classifier
            carrier.pr, carrier.head)
        assert extracted is None
        return
    elif kind == "type":
        notice["author"]["__typename"] = "User"
    elif kind == "id":
        notice["databaseId"] = None
    elif kind == "generic_quota":
        notice["body"] = "You have reached your Codex usage limits."
    elif kind == "pagination":
        carrier.pr["reviewThreads"]["pageInfo"]["hasNextPage"] = True
    else:
        item = thread()
        item["isResolved"] = True
        item["comments"]["pageInfo"]["hasPreviousPage"] = True
        carrier.pr["reviewThreads"]["nodes"] = [item]
    carrier.assert_stopped(carrier.execute(), reviews=0)


def test_ci_failure_still_blocks_after_local_approval(carrier):
    carrier.ci_failure = True
    outcome = carrier.execute()
    carrier.assert_stopped(outcome, reviews=1)
    assert outcome["step"] == "wait_ci"


@pytest.mark.parametrize("mode", ["blocked", "queued"])
def test_merge_failure_or_queued_merge_does_not_claim_landing_or_retry(carrier, mode):
    carrier.merge_failure = mode == "blocked"
    carrier.merge_queued = mode == "queued"
    outcome = carrier.execute()
    assert outcome["status"] == "error" and not carrier.landed
    assert len(carrier.reviews) == 1
    assert len([a for a in carrier.commands if a[:3] == ["gh", "pr", "merge"]]) == 1
    assert not any(a[0] == "bash" or "--admin" in a for a in carrier.commands)


@pytest.mark.parametrize("signal", ["clear_comment", "formal_review"])
def test_existing_github_only_success_does_not_invoke_local_review(carrier, signal):
    if signal == "clear_comment":
        carrier.pr["comments"]["nodes"][-1]["body"] = "Codex Review: didn't find any major issues."
    else:
        carrier.pr["comments"]["nodes"].pop()
        carrier.pr["latestReviews"]["nodes"] = [{
            "author": {"login": BOT}, "state": "APPROVED", "body": "", "commit": {"oid": carrier.head},
            "submittedAt": "2026-10-04T13:08:19Z"}]
    outcome = carrier.execute()
    assert outcome["status"] == "success" and not carrier.reviews
    assert any(a[0] == "bash" and a[-1] == "--sweep" for a in carrier.commands)
    assert not carrier.receipts()


def test_default_classifier_quota_behavior_unchanged(carrier):
    outcome = commit._extract_review_findings(  # ANTICHEAT_OK: existing strict classifier contract
        carrier.pr, carrier.head, result=carrier.result, pr_number="1331")
    assert outcome["outcome"] == "error"
    assert "usage-limit exhaustion" in outcome["response"]["errors"][0]


@pytest.mark.parametrize("prior_commit,badged", [(False, False), (True, True)])
def test_github_only_formal_review_classification_unchanged(carrier, prior_commit, badged):
    carrier.pr["comments"]["nodes"][-1]["body"] = "Codex Review: didn't find any major issues."
    carrier.pr["latestReviews"]["nodes"] = [{
        "author": {"login": BOT, "__typename": "Bot"}, "state": "COMMENTED",
        "commit": {"oid": git(carrier.root, "rev-parse", "HEAD^") if prior_commit else carrier.head},
        "submittedAt": "2026-10-04T13:08:10Z",
        "body": ("![P1 Badge](badge/P1-red) " if badged else "") + "A retained formal finding.",
    }]
    outcome = commit._extract_review_findings(  # ANTICHEAT_OK: preserve the existing GitHub-only classifier contract.
        carrier.pr, carrier.head, result=carrier.result, pr_number="1331")
    assert outcome["outcome"] == "clean"


def test_receipt_from_prior_attempt_is_not_reused(carrier):
    assert carrier.execute()["status"] == "success"
    first_receipt = next(carrier.bus.glob("meta/local_pr_reviews/*/receipt.json"))
    first_bytes = first_receipt.read_bytes()
    carrier.pr["state"] = "OPEN"
    carrier.pr.pop("mergeCommit")
    carrier.verdict_change = lambda e: e.update(decision="NO_GO")
    carrier.commands.clear()
    carrier.landed.clear()
    carrier.assert_stopped(carrier.execute(), reviews=2)
    assert first_receipt.read_bytes() == first_bytes
    assert sorted(r["status"] for r in carrier.receipts()) == ["APPROVED", "ERROR"]


def test_native_request_comment_id_binds_new_head_and_survives_checkpoint(carrier):
    carrier.continuation.write_text(json.dumps({"commit_sha": carrier.head}))
    assert commit._maybe_request_current_head_bot_review(  # ANTICHEAT_OK: real native request producer at fake gh boundary
        carrier.root, pr_number="1331", head_sha=carrier.head,
        continuation_path=carrier.continuation)
    recorded = json.loads(carrier.continuation.read_text())
    assert recorded["bot_review_request_comment_id"] == 1
    assert recorded["bot_review_request_sha"] == carrier.head
    commit._write_continuation_record(  # ANTICHEAT_OK: native checkpoint preserves exact request authority
        carrier.continuation, handoff_sha="f" * 64, target_branch="fixture/quota",
        commit_sha=carrier.head, receipt_decision="COMMIT_GO", steps_completed=carrier.result["steps_completed"])
    assert json.loads(carrier.continuation.read_text())["bot_review_request_comment_id"] == 1
    assert carrier.execute()["status"] == "success"
    commit._write_continuation_record(  # ANTICHEAT_OK: new head cannot inherit an old request
        carrier.continuation, handoff_sha="f" * 64, target_branch="fixture/quota",
        commit_sha="a" * 40, receipt_decision="COMMIT_GO", steps_completed=carrier.result["steps_completed"])
    assert "bot_review_request_comment_id" not in json.loads(carrier.continuation.read_text())


def test_assume_unchanged_source_is_not_exact_head_authority(carrier):
    git(carrier.root, "update-index", "--assume-unchanged", "earlier.py")
    (carrier.root / "earlier.py").write_text("hidden preexisting mutation\n")
    assert not git(carrier.root, "status", "--porcelain")
    carrier.assert_stopped(carrier.execute(), reviews=0)
    assert (carrier.root / "earlier.py").read_text() == "hidden preexisting mutation\n"


@pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
def test_nonblocking_findings_retained_in_native_receipt(carrier, severity):
    finding = {"class": "DOC_ACCURACY", "severity": severity, "disposition": "non_blocking",
               "title": "clarify example", "file": "earlier.py", "line_start": 1, "line_end": 1,
               "evidence_cmd": "read earlier.py", "evidence_result": "example wording", "status": "new"}
    carrier.verdict_change = lambda e: e.update(findings=[finding])
    assert carrier.execute()["status"] == "success"
    assert carrier.receipts()[0]["envelope"]["findings"] == [finding]


def test_missing_connector_signal_retains_existing_timeout_policy(carrier, monkeypatch):
    carrier.pr["comments"]["nodes"].pop()
    ticks = iter(range(1_800_000_000, 1_800_020_000, 100))
    monkeypatch.setattr(commit.time, "time", lambda: next(ticks))
    outcome = carrier.execute()
    assert outcome["status"] == "success" and not carrier.reviews
    assert any(a[:3] == ["gh", "pr", "comment"] for a in carrier.commands)
    assert any(a[0] == "bash" for a in carrier.commands)


def test_full_pr_review_uses_merge_base_of_verified_advanced_base(carrier):
    git(carrier.root, "checkout", "dev")
    (carrier.root / "base-only.txt").write_text("concurrent base change\n")
    git(carrier.root, "add", "base-only.txt")
    git(carrier.root, "commit", "-m", "advance base")
    advanced_base = git(carrier.root, "rev-parse", "HEAD")
    git(carrier.root, "checkout", "fixture/quota")
    carrier.pr["baseRefOid"] = advanced_base
    assert carrier.execute()["status"] == "success"
    receipt = carrier.receipts()[0]
    assert receipt["identity"]["base_sha"] == advanced_base
    assert receipt["identity"]["merge_base_sha"] == carrier.base
    diff = carrier.reviews[0][1]["prompt_path"].with_name("pr.diff").read_text()
    assert "earlier.py" in diff and "latest.py" in diff and "base-only.txt" not in diff


def test_outdated_human_thread_with_bot_like_login_remains_blocking(carrier):
    carrier.pr["reviewThreads"]["nodes"] = [thread("maintainer-bot", outdated=True)]
    outcome = carrier.execute()
    carrier.assert_stopped(outcome, reviews=0)
    assert "human" in outcome["errors"][0]


@pytest.fixture
def generated_governance_candidate(tmp_path, monkeypatch, request):
    """Real Step 5e and committed candidate builder in an isolated repository."""
    root = tmp_path
    bus = Path(".agent_bus-generated-candidate")
    wave = "generated-candidate-wave"
    branch = f"fixture/{wave}"
    packet = f"reports/control_plane/{wave}.md"
    growth = commit.GROWTH_CAP_TEST_RELPATH
    new_test = "mu/tests/tools/test_candidate_addition.py"
    (root / ".gitignore").write_text(".agent_bus*/\n.scratch/\n")
    (root / "allowed.py").write_text("value = 0\n")
    cap = root / growth
    cap.parent.mkdir(parents=True)
    cap.write_text("BASELINE_TEST_FILES = 1\nCAP_TEST_FILES = 0\n")
    (root / packet).parent.mkdir(parents=True)
    (root / packet).write_text(
        f"# Candidate preparation\n\nWave ID: {wave}\nFOUNDER_OVERRIDE:{wave}\n"
    )
    git(root, "init", "-b", "dev")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.hooksPath", str(root / ".git/fixture-hooks"))
    git(root, "add", ".")
    git(root, "commit", "-m", "candidate baseline")
    base = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "-b", branch)

    monkeypatch.setattr(commit, "_ACTIVE_BUS_DIR", ContextVar("generated_bus", default=bus))
    authority, _common = commit._landed_commit_candidate_authority()  # ANTICHEAT_OK: use the same committed builder as native preparation.
    allowlist = ["allowed.py", new_test, packet]
    if getattr(request, "param", False):
        allowlist.append(growth)
    spec = authority.CandidateAuthoritySpec.from_mapping({
        "wave_id": wave, "comparison_commit": base,
        "candidate_allowlist": allowlist, "plan_path": packet,
    })
    spec_path = authority.write_authority_spec(root, spec, bus_dir=bus)
    route_path = root / bus / "meta/post_merge_routing.json"
    route_path.write_text(json.dumps({
        "decision": "ROUTE_PHASE_B", "summary": "generated governance fixture",
        "wave_name": wave, "candidate_authority_required": True,
        "candidate_authority": {
            "required": True, "spec_path": str(spec_path),
            "spec_identity": authority.authority_spec_identity(root, spec, authority_required=True),
        },
    }))
    (root / "allowed.py").write_text("value = 1\n")
    (root / new_test).parent.mkdir(parents=True)
    (root / new_test).write_text("def test_candidate_addition():\n    assert 2 + 2 == 4\n")
    git(root, "add", "--", "allowed.py", new_test)
    outcome = commit.maybe_autobump_growth_cap_for_founder_override(
        root, wave_id=wave, base_branch="dev", founder_override_token=wave, log=lambda _: None,
    )
    assert outcome["reason"] == "bumped", outcome
    assert outcome["previous_cap"] == 0 and outcome["new_cap"] == 1
    return SimpleNamespace(
        root=root, bus=bus, wave=wave, base=base, cap=cap, growth=growth, new_test=new_test,
        spec=spec, spec_path=spec_path, route_path=route_path, outcome=outcome,
        receipt_path=authority.receipt_path_for(
            root, bus_dir=bus, wave_id=wave, phase="commit", review_round="pre-supervisor",
        ),
        handoff={
            "wave_id": wave, "base_branch": "dev", "target_branch": branch,
            "tracked_packet": packet, "files_to_stage": ["allowed.py", new_test, growth],
            "force_add_files": [], "scope_items": ["allowed.py", new_test, growth],
        },
    )


def assert_generated_candidate_rejected(case, outcome, diagnostic):
    preserved = {p: p.read_bytes() for p in (case.cap, case.spec_path, case.route_path)}
    staged = git(case.root, "diff", "--cached", "--binary")
    head = git(case.root, "rev-parse", "HEAD")
    with pytest.raises((ValueError, RuntimeError), match=diagnostic):
        commit._prepare_commit_candidate_authority(  # ANTICHEAT_OK: exercise real validation and scope rejection before staging.
            case.root, case.handoff, growth_cap_outcome=outcome,
        )
    assert {p: p.read_bytes() for p in preserved} == preserved
    assert git(case.root, "diff", "--cached", "--binary") == staged
    assert git(case.root, "rev-parse", "HEAD") == head
    assert not case.receipt_path.exists()


@pytest.mark.parametrize("generated_governance_candidate", [False, True], indirect=True,
                         ids=["outside-launch-allowlist", "already-in-launch-allowlist"])
@pytest.mark.parametrize("state", ["bumped", "retry_settled", "already_recorded"])
def test_commit_candidate_admits_only_validated_native_growth_cap(generated_governance_candidate, state):
    case = generated_governance_candidate
    outcome = case.outcome
    if state == "already_recorded":
        git(case.root, "commit", "-m", "record native growth cap")
    if state != "bumped":
        outcome = commit.maybe_autobump_growth_cap_for_founder_override(
            case.root, wave_id=case.wave, base_branch="dev",
            founder_override_token=case.wave, log=lambda _: None,
        )
    assert outcome["reason"] == state, outcome
    preserved = {p: p.read_bytes() for p in (case.cap, case.spec_path, case.route_path)}
    staged = git(case.root, "diff", "--cached", "--binary")
    head = git(case.root, "rev-parse", "HEAD")

    binding = commit._prepare_commit_candidate_authority(  # ANTICHEAT_OK: real candidate inventory, launch identity, native provenance and receipt.
        case.root, case.handoff, growth_cap_outcome=outcome,
    )

    assert binding is not None
    assert binding["spec"].to_dict() == {
        **case.spec.to_dict(), "phase": "commit", "review_round": "pre-supervisor",
        "candidate_allowlist": sorted({*case.spec.candidate_allowlist, case.growth}),
    }
    receipt = json.loads(binding["receipt_path"].read_text())
    for key in ("literal_base_inventory", "staged_literal_base_inventory"):
        assert {entry["path"] for entry in receipt[key]} == {"allowed.py", case.new_test, case.growth}
    commit._verify_commit_candidate_authority(case.root, binding)  # ANTICHEAT_OK: the native final verifier must accept the derived trusted spec.
    assert {p: p.read_bytes() for p in preserved} == preserved
    assert git(case.root, "diff", "--cached", "--binary") == staged
    assert git(case.root, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("state", ["untracked", "staged", "committed", "index-only"])
def test_generated_candidate_still_rejects_arbitrary_handoff_paths(generated_governance_candidate, state):
    case = generated_governance_candidate
    outsider = "outside.py"
    path = case.root / outsider
    path.write_text("unauthorized = True\n")
    if state != "untracked":
        git(case.root, "add", "--", outsider)
    if state == "committed":
        git(case.root, "commit", "--only", "-m", "outside launch scope", "--", outsider)
    elif state == "index-only":
        path.unlink()
    for key in ("files_to_stage", "force_add_files", "scope_items"):
        case.handoff[key].append(outsider)
    assert_generated_candidate_rejected(case, case.outcome, "outside allowlist: outside.py")
    assert path.exists() is (state != "index-only")


@pytest.mark.parametrize("untrusted_path", [
    "outside.py", "mu/tests/docs/not_growth_caps.py", "../outside.py", "/tmp/outside.py",
])
def test_generated_candidate_rejects_unverified_generated_path_lists(
    generated_governance_candidate, untrusted_path,
):
    case = generated_governance_candidate
    outcome = {**case.outcome, "commit_generated_governance_paths": [case.growth, untrusted_path]}
    assert_generated_candidate_rejected(case, outcome, "commit-generated governance path")


@pytest.mark.parametrize("fault, diagnostic", [
    ("handoff-only", "outside allowlist"),
    ("missing-provenance", "without bumped or same-wave already_recorded provenance"),
    ("unsupported-provenance", "unsupported commit-generated governance provenance"),
    ("retry-error", "native retry authority rejected"),
    ("unstaged-cap", "not staged"),
    ("wrong-wave", "not the exact staged postimage"),
    ("staged-edit", "not the exact staged postimage"),
    ("worktree-edit", "not the exact staged postimage"),
    ("false-already-recorded", "index/HEAD mismatch"),
])
def test_generated_candidate_rejects_invalid_cap_provenance(generated_governance_candidate, fault, diagnostic):
    case = generated_governance_candidate
    outcome = copy.deepcopy(case.outcome)
    if fault == "handoff-only":
        case.handoff["commit_generated_governance_paths"] = [case.growth]
        case.handoff["growth_cap_autobump_outcome"] = outcome
        outcome = None
    elif fault == "missing-provenance":
        outcome = {"commit_generated_governance_paths": [case.growth]}
    elif fault == "unsupported-provenance":
        outcome["reason"] = "unverified"
    elif fault == "retry-error":
        outcome["retry_authority_error"] = "native retry authority rejected"
    elif fault == "unstaged-cap":
        git(case.root, "restore", "--staged", "--", case.growth)
    elif fault == "false-already-recorded":
        outcome.update(bumped=False, reason="already_recorded")
    else:
        contents = case.cap.read_text()
        case.cap.write_text(
            contents.replace(case.wave, "other-wave") if fault == "wrong-wave"
            else contents + "# unauthorized generated content\n"
        )
        if fault != "worktree-edit":
            git(case.root, "add", "--", case.growth)
    assert_generated_candidate_rejected(case, outcome, diagnostic)


@pytest.mark.parametrize("generated_governance_candidate", [False, True], indirect=True,
                         ids=["outside-launch-allowlist", "already-in-launch-allowlist"])
@pytest.mark.parametrize("fault, diagnostic", [
    ("wrong-wave", "lacks same-wave HEAD/index provenance"),
    ("staged-edit", "index/HEAD mismatch"),
    ("worktree-edit", "unstaged delta"),
])
def test_generated_candidate_rejects_stale_recorded_cap_provenance(
    generated_governance_candidate, fault, diagnostic,
):
    case = generated_governance_candidate
    git(case.root, "commit", "-m", "record native growth cap")
    outcome = commit.maybe_autobump_growth_cap_for_founder_override(
        case.root, wave_id=case.wave, base_branch="dev",
        founder_override_token=case.wave, log=lambda _: None,
    )
    assert outcome["reason"] == "already_recorded", outcome
    contents = case.cap.read_text()
    case.cap.write_text(
        contents.replace(case.wave, "other-wave") if fault == "wrong-wave"
        else contents + "# unauthorized recorded content\n"
    )
    if fault != "worktree-edit":
        git(case.root, "add", "--", case.growth)
    if fault == "wrong-wave":
        git(case.root, "commit", "-m", "replace recorded provenance")
    assert_generated_candidate_rejected(case, outcome, diagnostic)


@pytest.mark.parametrize("state, diagnostic", [
    ("bumped", "not the exact staged postimage"),
    ("already_recorded", "index/HEAD mismatch"),
])
def test_generated_candidate_rechecks_provenance_after_native_preparation(
    generated_governance_candidate, monkeypatch, state, diagnostic,
):
    case = generated_governance_candidate
    outcome = case.outcome
    if state == "already_recorded":
        git(case.root, "commit", "-m", "record native growth cap")
        outcome = commit.maybe_autobump_growth_cap_for_founder_override(
            case.root, wave_id=case.wave, base_branch="dev",
            founder_override_token=case.wave, log=lambda _: None,
        )
    assert outcome["reason"] == state, outcome
    authority, common = commit._landed_commit_candidate_authority()  # ANTICHEAT_OK: keep the committed candidate builder and validators real.
    prepare = authority.prepare_candidate_authority
    altered_cap = case.cap.read_text() + "# content changed during candidate preparation\n"

    def prepare_with_cap_drift(repo_root, spec, *, bus_dir):
        case.cap.write_text(altered_cap)
        return prepare(repo_root, spec, bus_dir=bus_dir)

    monkeypatch.setattr(authority, "prepare_candidate_authority", prepare_with_cap_drift)
    monkeypatch.setattr(commit, "_landed_commit_candidate_authority", lambda: (authority, common))  # ANTICHEAT_OK: inject a timing fault before real candidate staging, not a validation result.
    preserved = {p: p.read_bytes() for p in (case.spec_path, case.route_path)}
    head = git(case.root, "rev-parse", "HEAD")
    with pytest.raises(ValueError, match=diagnostic):
        commit._prepare_commit_candidate_authority(  # ANTICHEAT_OK: no trusted binding may escape after native preparation stages invalid generated bytes.
            case.root, case.handoff, growth_cap_outcome=outcome,
        )
    assert case.receipt_path.exists(), "the real candidate builder did not complete"
    assert git(case.root, "show", f":{case.growth}") == altered_cap.strip()
    assert {p: p.read_bytes() for p in preserved} == preserved
    assert git(case.root, "rev-parse", "HEAD") == head


@pytest.mark.parametrize("fault, diagnostic", [
    ("spec", "launch-bound identity"),
    ("route-wave", "wave/packet does not match"),
    ("handoff-packet", "wave/packet does not match"),
])
def test_generated_candidate_preserves_launch_identity_checks(generated_governance_candidate, fault, diagnostic):
    case = generated_governance_candidate
    if fault == "spec":
        spec = json.loads(case.spec_path.read_text())
        spec["candidate_allowlist"].append(case.growth)
        case.spec_path.write_text(json.dumps(spec))
    elif fault == "route-wave":
        route = json.loads(case.route_path.read_text())
        route["wave_name"] = "other-wave"
        case.route_path.write_text(json.dumps(route))
    else:
        case.handoff["tracked_packet"] = "reports/control_plane/other-wave.md"
    assert_generated_candidate_rejected(case, case.outcome, diagnostic)


def test_generated_candidate_retains_committed_auto_deferred_authority(generated_governance_candidate):
    case = generated_governance_candidate
    git(case.root, "commit", "-m", "record native candidate")
    findings = [{"path": "allowed.py", "body": "Retained non-blocking finding."}]
    report = commit._write_auto_deferred_bot_findings_report(  # ANTICHEAT_OK: use the native report producer in the disposable repository.
        case.root, findings, case.wave, "1331", lambda _: None,
    )
    report_rel = report.relative_to(case.root).as_posix()
    git(case.root, "add", "--", report_rel)
    commit._mint_bot_remediation_receipt(  # ANTICHEAT_OK: authorize only the real report-only staged diff using the native producer.
        repo_root=case.root, findings_addressed=findings, scoped_files=[report_rel],
        round_num=1, wave_id=case.wave,
    )
    git(case.root, "commit", "-m", "receipted report-only child")
    commit._write_continuation_record(  # ANTICHEAT_OK: bind the native child receipt to this same-wave continuation.
        case.root / case.bus / "executors" / f"commit_executor_{case.wave}.json",
        handoff_sha="fixture-handoff", target_branch=case.handoff["target_branch"],
        commit_sha=git(case.root, "rev-parse", "HEAD"), receipt_decision="COMMIT_GO",
        steps_completed=["git_commit"], pr_number="1331",
    )
    outcome = commit.maybe_autobump_growth_cap_for_founder_override(
        case.root, wave_id=case.wave, base_branch="dev",
        founder_override_token=case.wave, log=lambda _: None,
    )
    assert outcome["reason"] == "already_recorded", outcome
    preserved = {p: p.read_bytes() for p in (case.cap, case.spec_path, case.route_path, report)}

    binding = commit._prepare_commit_candidate_authority(  # ANTICHEAT_OK: both native provenance paths must compose in real candidate preparation.
        case.root, case.handoff, growth_cap_outcome=outcome,
    )

    assert binding is not None
    assert set(binding["spec"].candidate_allowlist) == {
        *case.spec.candidate_allowlist, case.growth, report_rel,
    }
    receipt = json.loads(binding["receipt_path"].read_text())
    assert {case.growth, report_rel} <= {entry["path"] for entry in receipt["literal_base_inventory"]}
    commit._verify_commit_candidate_authority(case.root, binding)  # ANTICHEAT_OK: verify the combined generated and committed-report authority.
    assert {p: p.read_bytes() for p in preserved} == preserved
