"""Real-Git native-v1 interruptions and public recovery/postcommit boundaries.

Preservation fixtures live outside the disposable worktree, without a mounted
drive. Only provider/GitHub I/O is modeled. The historical writer, current
admission, complete PR Git diff, recovery CLI, locks and publication are real.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from mu.tests.tools import test_commit_executor_local_review as local
from mu.tests.tools.test_commit_executor_local_review import (
    carrier_repository,
    historical_local_review_producer,
    local_review_timing_origin,
    trace_local_review_case,
)
from tests.repo_root import REPO_ROOT
import local_review_history_recovery as recovery


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {str(p.relative_to(directory)): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in directory.rglob("*") if p.is_file()}


# Literal progress messages from preserved a705 raw SHA256 caf80424...c5a5e0.
# Keep fixture evidence independent of both the mounted store and source constants.
PRESERVED_PROGRESS = (
    "I’ll verify the supplied base, head, and diff hash, then read the complete change set and relevant source. "
    "I’ll keep all probes narrow and read-only and return the requested envelope with findings and proof limits.\n",
    "The supplied diff matches the verified base and HEAD byte for byte, and the worktree is clean. It spans 53 files. "
    "I’m applying the rcx-redteam-runtime skill’s evidence checks to the review, merge, and dispatcher paths while reading the complete diff.\n",
    "The merge path binds approval to the full PR diff and preserves a durable record of each merge request. "
    "I’m checking whether reloads and late review evidence preserve those guarantees. The added tests cover many negative cases; "
    "I haven’t yet completed the source and evidence review.\n",
)


class History:
    def __init__(self, carrier, monkeypatch, producer, preservation, *, support=None):
        self.support = support or local
        self.lane = carrier
        # Recovery consumes a locally verified origin base, as production does.
        # Only this recovery fixture needs the tracking ref; ordinary review
        # fixtures and their original admission expectations remain unchanged.
        self.support.git(carrier.root, "update-ref", "refs/remotes/origin/dev", carrier.base)
        self.preservation = preservation.resolve()
        self.preservation.mkdir()
        self.binding = self.preservation / "binding.json"
        self.manifest = self.preservation / "preservation.json"
        self.restored = self.preservation / "restored"
        self.restored.mkdir()
        self.support._native_continuation(carrier)  # ANTICHEAT_OK: native public-resume record writer
        adapters = self.support.commit._bridge_adapters  # ANTICHEAT_OK: isolate provider transport only
        monkeypatch.setitem(sys.modules, "commit_executor", self.support.commit)

        def interrupt(spec, **kwargs):
            carrier.reviews.append((spec, kwargs))
            raw = [
                {"type": "thread.started", "thread_id": "01234567-89ab-cdef-0123-456789abcdef"},
                {"type": "turn.started"},
                {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message",
                 "text": "I haven't yet completed the source and evidence review."}},
            ]
            kwargs["raw_output_path"].write_text("".join(json.dumps(e) + "\n" for e in raw))
            raise KeyboardInterrupt("modeled interrupted native-v1 process; cause not inferred")

        # Execute the actual pre-marker native writer. No fabricated old receipt,
        # deletion of metadata, or replacement of current admission predicates.
        def interrupt_receipt(path, payload):
            assert path.name == "receipt.json"
            raise KeyboardInterrupt("interrupted before original receipt publication")

        with monkeypatch.context() as transport:
            transport.setattr(adapters, "run_adapter", interrupt)
            transport.setattr(self.support.commit, "_atomic_write_fsynced_json", interrupt_receipt)
            with pytest.raises(KeyboardInterrupt):
                producer(repo_root=carrier.root, pr_data=carrier.pr, result=carrier.result,
                         wave_id=carrier.handoff["wave_id"], repo_owner="fixture", repo_name="repo",
                         pr_number="1331", head_sha=carrier.head, target_branch="fixture/quota",
                         base_branch="dev", continuation_path=carrier.continuation)
        self.attempt = next(carrier.bus.glob("meta/local_pr_reviews/local-pr-review-*"))
        assert {p.name for p in self.attempt.iterdir()} == {"prompt.md", "pr.diff", "raw.jsonl"}
        self.expected = {"repository": "fixture/repo", "pr_number": 1331,
                         "head_branch": "fixture/quota", "base_branch": "dev",
                         "head_sha": carrier.head, "base_sha": carrier.base}
        self.preserve()
        self.original = inventory(self.attempt)
        self.forbidden = []

        def forbidden(*args, **kwargs):
            self.forbidden.append((args, kwargs))
            raise AssertionError("Recovery/remediation must not spend legacy review authority")

        monkeypatch.setattr(self.support.commit, "_attempt_bot_finding_remediation", forbidden)
        monkeypatch.setattr(self.support.commit, "_load_repo_recovery_symbols", forbidden)

    def preserve(self):
        """Independent fixture preservation, before pinning caller authority."""
        entries = []
        for path in sorted(self.attempt.iterdir()):
            target = self.restored / path.relative_to(path.anchor)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            target.chmod(path.stat().st_mode & 0o777)
            entries.append({"path": str(path), "size": path.stat().st_size,
                            "mode": path.stat().st_mode & 0o777, "sha256": digest(path)})
        self.manifest.write_text(json.dumps({
            "original_path": str(self.lane.root), "head": self.expected["head_sha"],
            "entries": entries, "snapshot": "8" * 64,
            "restored_and_verified": {"files": len(entries), "hashes_and_modes": True, "restic_verify": True},
        }))
        self.binding.write_text(json.dumps({
            "manifest_path": str(self.manifest), "manifest_sha256": digest(self.manifest),
            "snapshot": "8" * 64, "restored_root": str(self.restored), "entries": entries,
        }))

    def plan(self):
        return recovery.plan_recovery(repo_root=self.lane.root,
                                      attempt=str(self.attempt.relative_to(self.lane.root)),
                                      provenance=str(self.binding), provenance_sha256=digest(self.binding),
                                      expected=self.expected)

    def apply(self, document=None):
        document = document or self.plan()
        return recovery.apply_recovery(repo_root=self.lane.root, document=document,
                                       plan_sha256=document["plan_sha256"])

    def verify(self):
        return recovery.verify_recovery(repo_root=self.lane.root, job_id=self.attempt.name)

    def resume(self):
        return self.support._resume_native(self.lane, bus_dir=self.lane.bus.name)  # ANTICHEAT_OK: public pipeline driver

    def corrected(self, *, empty=False):
        if empty:
            self.support.git(self.lane.root, "commit", "--allow-empty", "-m", "unchanged content")
        else:
            (self.lane.root / "earlier.py").write_text("value = 3  # material correction\n")
            self.support.git(self.lane.root, "add", "earlier.py")
            self.support.git(self.lane.root, "commit", "-m", "correct review input")
        self.lane.head = self.support.git(self.lane.root, "rev-parse", "HEAD")
        self.lane.result["commit_sha"] = self.lane.pr["headRefOid"] = self.lane.head
        self.support._native_continuation(self.lane)  # ANTICHEAT_OK: new native current-head checkpoint

    def assert_hold(self):
        self.lane.commands.clear()
        reviews = len(self.lane.reviews)
        outcome = self.resume()
        assert outcome["status"] == "held", outcome
        assert outcome["failure_class"] == "local_review_evidence_hold", outcome
        assert outcome["retry_allowed"] is False
        self.lane.assert_stopped(outcome, reviews=reviews)
        assert not any(c[0] == "gh" for c in self.lane.commands)
        assert not self.forbidden
        return outcome

    def cli(self, operation, *extra):
        command = [sys.executable, str(REPO_ROOT / "mu/tools/executors/local_review_history_recovery.py"),
                   operation, "--repo-root", str(self.lane.root), *extra]
        return subprocess.run(command, text=True, capture_output=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=30)

    def cli_plan_args(self):
        return ["--attempt", str(self.attempt.relative_to(self.lane.root)),
                "--provenance", str(self.binding), "--provenance-sha256", digest(self.binding),
                "--repository", "fixture/repo", "--pr", "1331", "--head-branch", "fixture/quota",
                "--base-branch", "dev", "--head", self.expected["head_sha"], "--base", self.expected["base_sha"]]


@pytest.fixture
def history(tmp_path, monkeypatch, historical_local_review_producer, carrier_repository):
    root = (tmp_path / "repo").resolve()
    root.mkdir()
    return History(local.Carrier(root, monkeypatch, repository=carrier_repository),
                   monkeypatch, historical_local_review_producer,
                   tmp_path / "independent-preservation")


def test_public_cli_plan_apply_verify_is_read_only_then_append_only(history):
    h = history
    h.assert_hold()
    before = inventory(h.lane.root)
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 0, response.stdout + response.stderr
    assert inventory(h.lane.root) == before
    document = json.loads(response.stdout)
    assert document == h.plan() and document["plan"]["approval"] is False
    path = h.preservation / "plan.json"
    path.write_text(response.stdout)
    response = h.cli("apply", "--plan-file", str(path), "--plan-sha256", document["plan_sha256"])
    assert response.returncode == 0, response.stdout + response.stderr
    proof = json.loads(response.stdout)
    assert proof["history"]["kind"] == "recovered_legacy_review_interruption"
    assert proof["history"]["approval"] is False and "receipt" not in proof
    response = h.cli("verify", "--job-id", h.attempt.name)
    assert response.returncode == 0, response.stdout + response.stderr
    assert json.loads(response.stdout) == proof
    assert inventory(h.attempt) == h.original
    after = inventory(h.lane.root)
    assert {k: after[k] for k in before} == before
    assert all(k.startswith(".agent_bus/meta/local_pr_review_admissions/") for k in after.keys() - before.keys())
    assert h.apply(document) == proof
    assert inventory(h.lane.root) == after
    h.assert_hold()


@pytest.mark.parametrize("empty,bus_change", [(False, False), (False, True), (True, False), (True, True)])
def test_original_and_empty_commit_remain_held_across_buses(history, monkeypatch, empty, bus_change):
    h = history
    h.apply()
    if empty:
        h.corrected(empty=True)
    if bus_change:
        local._change_review_bus(h.lane, monkeypatch)  # ANTICHEAT_OK: new native bus and checkpoint
    outcome = h.assert_hold()
    assert "unchanged PR content" in " ".join(outcome["errors"])
    assert inventory(h.attempt) == h.original


@pytest.mark.parametrize("bus_change", [False, True])
def test_material_correction_has_zero_inherited_approval_and_gets_fresh_full_review(history, monkeypatch, bus_change):
    h = history
    h.apply()
    h.corrected()
    if bus_change:
        local._change_review_bus(h.lane, monkeypatch)  # ANTICHEAT_OK: native cross-bus continuation
    outcome = h.resume()
    assert outcome["status"] == "success", outcome
    assert len(h.lane.reviews) == 2 and len(h.lane.landed) == 1
    receipt = h.lane.receipts()[0]
    assert receipt["status"] == "APPROVED" and receipt["job_id"] != h.attempt.name
    assert receipt["identity"]["head_sha"] == h.lane.head
    assert receipt["request_comment"]["databaseId"] == 1
    assert receipt["identity"]["diff_sha256"] != h.verify()["history"]["document"]["plan"]["inputs"]["identity"]["diff_sha256"]
    assert any(c[:3] == ["gh", "pr", "checks"] for c in h.lane.commands)
    assert all("--admin" not in c for c in h.lane.commands)
    assert inventory(h.attempt) == h.original and not h.forbidden


@pytest.mark.parametrize("field", ["repository", "pr_number", "head_branch", "base_branch", "base_sha", "head_sha"])
def test_wrong_explicit_scope_is_held_without_publication(history, field):
    h = history
    h.expected[field] = 1332 if field == "pr_number" else "a" * 40 if field.endswith("sha") else "foreign/other"
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        h.plan()
    assert not (h.lane.root / ".agent_bus/meta/local_pr_review_admissions/legacy_interruptions").exists()
    h.assert_hold()


@pytest.mark.parametrize("artifact", ["prompt.md", "pr.diff", "raw.jsonl", "binding", "manifest", "restored", "mode"])
def test_changed_evidence_after_planning_cannot_publish(history, artifact):
    h = history
    document = h.plan()
    path = {"binding": h.binding, "manifest": h.manifest,
            "restored": h.restored / (h.attempt / "raw.jsonl").relative_to(h.attempt.anchor),
            "mode": h.attempt / "raw.jsonl"}.get(artifact, h.attempt / artifact)
    if artifact == "mode":
        path.chmod(0o600)
    else:
        path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises((ValueError, OSError)):
        h.apply(document)
    h.assert_hold()


@pytest.mark.parametrize("fault", [
    "completed", "failed", "refused", "capacity", "quota", "verdict", "partial-envelope",
    "two-threads", "two-turns", "duplicate-json", "truncated-json", "blank-line", "unknown-event",
    "unknown-item", "raw-job", "raw-turn", "raw-identity", "finished-prose", "ambiguous-items",
    "foreign-pr-prose", "foreign-job-prose", "foreign-head-prose",
])
def test_even_preserved_terminal_or_ambiguous_raw_is_not_recoverable(history, fault):
    h = history
    path = h.attempt / "raw.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    if fault in {"completed", "failed", "two-turns", "unknown-event"}:
        events.append({"type": {"completed": "turn.completed", "failed": "turn.failed",
                               "two-turns": "turn.started", "unknown-event": "future.event"}[fault]})
    elif fault == "two-threads":
        events.append(events[0])
    elif fault in {"refused", "capacity", "quota", "verdict", "partial-envelope", "finished-prose"}:
        events[-1]["item"]["text"] = {
            "refused": "I cannot review this because of safety policy.",
            "capacity": "Review unfinished; provider capacity unavailable.",
            "quota": "Review unfinished; usage limit reached.", "verdict": '{"decision":"GO"}',
            "partial-envelope": "BEGIN_AGENT_ENVELOPE\n", "finished-prose": "The review is complete.",
        }[fault]
    elif fault == "unknown-item":
        events[-1]["item"]["type"] = "refusal"
    elif fault.startswith("raw-"):
        events[-1][{"raw-job": "job_id", "raw-turn": "turn_id", "raw-identity": "review_identity"}[fault]] = "foreign"
    elif fault == "ambiguous-items":
        events.append(events[-1])
    elif fault.startswith("foreign-"):
        events[-1]["item"]["text"] += {
            "foreign-pr-prose": " This is PR999.",
            "foreign-job-prose": " Job local-pr-review-" + "f" * 32,
            "foreign-head-prose": " Head " + "f" * 40,
        }[fault]
    raw = "".join(json.dumps(e) + "\n" for e in events)
    if fault == "duplicate-json":
        raw = raw.replace('"type": "turn.started"', '"type": "turn.completed", "type": "turn.started"')
    elif fault == "truncated-json":
        raw = raw[:-3]
    elif fault == "blank-line":
        raw += "\n"
    path.write_text(raw)
    h.preserve()
    with pytest.raises(ValueError):
        h.plan()
    h.assert_hold()


@pytest.mark.parametrize("message", [
    pytest.param("I decline this request for safety reasons; the review remains unfinished.",
                 id="declined-for-safety"),
    pytest.param("I must DECLINE to comply with this request; the review remains unfinished.",
                 id="declined-to-comply"),
    pytest.param("I’m unable to assist with this request; the review remains unfinished.",
                 id="unable-to-assist"),
    pytest.param("I am not able to help with this request; the review remains unfinished.",
                 id="not-able-to-help"),
    pytest.param("I am not allowed to fulfill this request; the review remains unfinished.",
                 id="not-allowed-to-fulfill"),
    pytest.param("I am not permitted to proceed with this request; the review remains unfinished.",
                 id="not-permitted-to-proceed"),
    pytest.param("We cannot comply with this request; the review remains unfinished.",
                 id="collective-refusal"),
    pytest.param("I\nwill not review this request; the review remains unfinished.",
                 id="multiline-refusal"),
    pytest.param("I refuse to review this request; the review remains unfinished.",
                 id="explicit-refusal"),
])
@pytest.mark.parametrize("later_unfinished_message", [False, True])
def test_public_plan_rejects_preserved_refusal_even_with_unfinished_commentary(
        history, message, later_unfinished_message):
    h = history
    path = h.attempt / "raw.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    unfinished = events[-1]["item"]["text"]
    events[-1]["item"]["text"] = message
    if later_unfinished_message:
        events.append({"type": "item.completed", "item": {
            "id": "item_1", "type": "agent_message", "text": unfinished}})
    path.write_text("".join(json.dumps(event) + "\n" for event in events))
    h.preserve()
    before = inventory(h.lane.root)
    preserved = inventory(h.preservation)

    response = h.cli("plan", *h.cli_plan_args())

    assert response.returncode == 1, response.stdout + response.stderr
    result = json.loads(response.stdout)
    assert result["status"] == "held"
    assert result["approval"] is False and result["retry_allowed"] is False
    assert result["error"] == "Legacy refusal/capacity history is not recoverable"
    assert inventory(h.lane.root) == before
    assert inventory(h.preservation) == preserved


@pytest.mark.parametrize("messages", [
    ("I haven't yet completed the source and evidence review.",),
    PRESERVED_PROGRESS,
], ids=["neutral", "original-a705-progress"])
def test_public_bounded_commentary_recovers_only_negative_history(history, messages):
    h = history
    raw = h.attempt / "raw.jsonl"
    events = [json.loads(line) for line in raw.read_text().splitlines()][:2]
    events.extend({"type": "item.completed", "item": {
        "id": f"item_{i}", "type": "agent_message", "text": text}}
        for i, text in enumerate(messages))
    raw.write_text("".join(json.dumps(event) + "\n" for event in events))
    h.preserve()
    original = inventory(h.attempt)
    before = inventory(h.lane.root)
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 0, response.stdout + response.stderr
    assert inventory(h.lane.root) == before
    document = json.loads(response.stdout)
    assert document["plan"]["approval"] is False
    assert document["plan"]["inputs"]["unfinished"]["interruption_cause"] == "unknown"
    proof = h.apply(document)
    assert h.verify() == proof
    assert proof["history"]["approval"] is False and "receipt" not in proof
    assert inventory(h.attempt) == original
    h.assert_hold()


@pytest.mark.parametrize("message", [
    "I am not going to review this request for safety reasons; the review remains unfinished.",
    "I offer no assistance with this request for safety reasons; the review remains unfinished.",
    "This request is outside what I can support; the review remains unfinished.",
    "Someone said the review remains unfinished, but its disposition is unknown.",
    "The review remains unfinished.",
    "I haven't yet completed the source and evidence review. Further assistance is prohibited.",
])
@pytest.mark.parametrize("suffix", [(), ("I haven't yet completed the source and evidence review.",), PRESERVED_PROGRESS],
                         ids=["last-message", "before-neutral", "before-original-progress"])
def test_public_plan_holds_unknown_or_refusal_adjacent_commentary(history, message, suffix):
    h = history
    raw = h.attempt / "raw.jsonl"
    events = [json.loads(line) for line in raw.read_text().splitlines()][:2]
    events.extend({"type": "item.completed", "item": {
        "id": f"item_{i}", "type": "agent_message", "text": text}}
        for i, text in enumerate((message, *suffix)))
    raw.write_text("".join(json.dumps(event) + "\n" for event in events))
    h.preserve()
    before, preserved = inventory(h.lane.root), inventory(h.preservation)
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 1, response.stdout + response.stderr
    result = json.loads(response.stdout)
    assert result["status"] == "held"
    assert result["approval"] is False and result["retry_allowed"] is False
    assert inventory(h.lane.root) == before
    assert inventory(h.preservation) == preserved
    h.assert_hold()


@pytest.mark.parametrize("messages", [
    PRESERVED_PROGRESS[-1:],
    (PRESERVED_PROGRESS[1], PRESERVED_PROGRESS[0], PRESERVED_PROGRESS[2]),
    (*PRESERVED_PROGRESS, PRESERVED_PROGRESS[-1]),
    (*PRESERVED_PROGRESS[:2], PRESERVED_PROGRESS[-1] + "The requested review is approved.\n"),
])
def test_public_plan_holds_incomplete_reordered_or_extended_progress(history, messages):
    h = history
    raw = h.attempt / "raw.jsonl"
    events = [json.loads(line) for line in raw.read_text().splitlines()][:2]
    events.extend({"type": "item.completed", "item": {
        "id": f"item_{i}", "type": "agent_message", "text": text}}
        for i, text in enumerate(messages))
    raw.write_text("".join(json.dumps(event) + "\n" for event in events))
    h.preserve()
    before = inventory(h.lane.root)
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 1, response.stdout + response.stderr
    assert json.loads(response.stdout)["approval"] is False
    assert inventory(h.lane.root) == before
    h.assert_hold()


@pytest.mark.parametrize("fault", ["root", "pr", "base", "job", "turn", "extra-envelope", "extra-prose", "diff-path"])
def test_preserved_prompt_contradictions_are_held(history, fault):
    h = history
    path = h.attempt / "prompt.md"
    text = path.read_text()
    if fault in {"root", "pr", "base", "job", "turn"}:
        before, separator, tail = text.partition("BEGIN_AGENT_ENVELOPE\n")
        value, end, after = tail.partition("\nEND_AGENT_ENVELOPE\n")
        envelope = json.loads(value)
        if fault in {"job", "turn"}:
            envelope[fault + "_id"] += "-foreign"
        else:
            key = {"root": "repo_root", "pr": "pr_number", "base": "base_sha"}[fault]
            envelope["review_identity"][key] = 999 if fault == "pr" else "/wrong/root" if fault == "root" else "c" * 40
        text = before + separator + json.dumps(envelope) + end + after
    elif fault == "extra-envelope":
        text += text[text.index("BEGIN_AGENT_ENVELOPE"):]
    elif fault == "extra-prose":
        text = "This actually reviews another PR.\n" + text
    else:
        text = text.replace(str(h.attempt / "pr.diff"), "/wrong/root/pr.diff")
    path.write_text(text)
    h.preserve()
    with pytest.raises(ValueError):
        h.plan()


@pytest.mark.parametrize("fault", ["symlink-file", "symlink-parent", "symlink-loop", "traversal", "foreign-root", "missing-history", "unreadable"])
def test_paths_and_missing_local_history_fail_closed(history, fault):
    h = history
    args = h.cli_plan_args()
    path = h.attempt / "raw.jsonl"
    if fault == "symlink-file":
        saved = h.preservation / "raw.saved"
        path.rename(saved)
        path.symlink_to(saved)
    elif fault == "symlink-parent":
        saved = h.attempt.with_name("saved")
        h.attempt.rename(saved)
        h.attempt.symlink_to(saved, target_is_directory=True)
    elif fault == "symlink-loop":
        path.unlink()
        path.symlink_to(path)
    elif fault == "traversal":
        args[1] = "../" + h.lane.root.name + "/" + args[1]
    elif fault == "foreign-root":
        h.lane.root = h.preservation
    elif fault == "missing-history":
        sha = h.expected["base_sha"]
        (h.lane.root / ".git/objects" / sha[:2] / sha[2:]).unlink()
    else:
        path.chmod(0)
    response = h.cli("plan", *args)
    assert response.returncode == 1, response.stdout + response.stderr
    assert json.loads(response.stdout)["status"] == "held"


@pytest.mark.parametrize("damaged", ["intent", "seal", "both", "original", "restore", "provenance", "unknown"])
def test_later_resumes_reject_missing_or_changed_recovery_and_originals(history, damaged):
    h = history
    h.apply()
    h.corrected()
    directory = h.lane.root / ".agent_bus/meta/local_pr_review_admissions/legacy_interruptions"
    if damaged in {"intent", "seal", "both"}:
        suffixes = ["intent", "published"] if damaged == "both" else ["published" if damaged == "seal" else "intent"]
        for suffix in suffixes:
            (directory / (h.attempt.name + "." + suffix + ".json")).unlink()
    elif damaged == "original":
        (h.attempt / "raw.jsonl").unlink()
    elif damaged == "restore":
        (h.restored / (h.attempt / "pr.diff").relative_to(h.attempt.anchor)).unlink()
    elif damaged == "provenance":
        h.binding.write_text("{}")
    else:
        (directory / "unknown.json").write_text("{}")
    h.assert_hold()


@pytest.mark.parametrize("when", ["before-intent", "partial-intent", "after-intent", "after-seal"])
def test_interrupted_publication_and_identical_replay(history, monkeypatch, when):
    h = history
    document = h.plan()
    real_write = os.write
    real_fsync = os.fsync
    # Inject at the durable publication boundary, never into the validator.
    publish = recovery._publish  # ANTICHEAT_OK: fault injection at exclusive file publication

    def interrupted(path, raw):
        if path.name.endswith(".intent.json"):
            if when == "before-intent":
                raise KeyboardInterrupt("before publication")
            if when == "partial-intent":
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    real_write(fd, raw[:31])
                    real_fsync(fd)
                finally:
                    os.close(fd)
                raise KeyboardInterrupt("partial publication")
        publish(path, raw)
        if (when == "after-intent" and path.name.endswith(".intent.json")) or (
                when == "after-seal" and path.name.endswith(".published.json")):
            raise KeyboardInterrupt("after durable publication")

    with monkeypatch.context() as crash:
        crash.setattr(recovery, "_publish", interrupted)
        with pytest.raises(KeyboardInterrupt):
            h.apply(document)
    h.assert_hold()
    if when == "partial-intent":
        with pytest.raises(ValueError):
            h.apply(document)
    else:
        h.apply(document)
        before = inventory(h.lane.root)
        h.apply(document)
        assert inventory(h.lane.root) == before
    assert inventory(h.attempt) == h.original


def test_canonical_lock_stops_concurrent_plan_and_apply_in_other_process(history):
    h = history
    document = h.plan()
    path = h.preservation / "plan.json"
    path.write_text(json.dumps(document))
    lock = h.lane.root / ".agent_bus/meta/local_pr_review_admissions/admission.lock"
    lock.parent.mkdir(parents=True)
    with lock.open("wb") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = inventory(h.lane.root)
        for operation, args in [("plan", h.cli_plan_args()),
                                ("apply", ["--plan-file", str(path), "--plan-sha256", document["plan_sha256"]])]:
            response = h.cli(operation, *args)
            assert response.returncode == 1, response.stdout + response.stderr
            assert json.loads(response.stdout)["status"] == "held"
        assert inventory(h.lane.root) == before
    h.apply(document)


def test_conflicting_replay_and_dirty_or_moved_source_cannot_publish(history):
    h = history
    document = h.plan()
    (h.lane.root / "earlier.py").write_text("uncommitted correction\n")
    with pytest.raises(ValueError, match="clean"):
        h.apply(document)
    h.corrected()
    with pytest.raises(ValueError, match="HEAD/content"):
        h.apply(document)
    corrected_plan = h.plan()
    h.apply(corrected_plan)
    with pytest.raises(ValueError, match="Conflicting"):
        h.apply(document)


@pytest.mark.parametrize("fault", ["no-request", "wrong-request", "no-clearance", "refusal", "capacity", "ci"])
def test_recovery_never_clears_fresh_request_review_provider_or_ci_gates(history, fault):
    h = history
    h.apply()
    h.corrected()
    if fault in {"no-request", "wrong-request"}:
        h.lane.pr["comments"]["nodes"][0]["databaseId"] = 99
        if fault == "no-request":
            h.lane.pr["comments"]["nodes"][0]["author"]["__typename"] = "Bot"
    elif fault == "no-clearance":
        # No historical quota notice survives. Recovery must still select the
        # strict current-request clearance path, never elapsed-time approval.
        h.lane.pr["comments"]["nodes"] = []
        h.lane.pr["latestReviews"]["nodes"] = [{
            "author": {"login": local.BOT, "__typename": "Bot"}, "state": "COMMENTED",
            "body": "", "commit": {"oid": h.lane.head}, "submittedAt": "2026-10-04T14:00:00Z"}]
    elif fault in {"refusal", "capacity"}:
        adapters = local.commit._bridge_adapters  # ANTICHEAT_OK: provider transport fixture
        h.lane.adapter_error = adapters.BridgeAdapterError(
            "provider safety refusal" if fault == "refusal" else "provider capacity unavailable", returncode=1)
    else:
        h.lane.ci_failure = True
    outcome = h.resume()
    h.lane.assert_stopped(outcome)
    assert not h.forbidden and inventory(h.attempt) == h.original
    if fault in {"refusal", "capacity"}:
        reviews = len(h.lane.reviews)
        again = h.resume()
        h.lane.assert_stopped(again, reviews=reviews)


def test_changed_recovery_before_protected_merge_stops_without_merge(history):
    h = history
    proof = h.apply()
    h.corrected()
    h.lane.after_ci = lambda: Path(proof["record_path"]).write_text("{}")
    outcome = h.resume()
    assert outcome["failure_class"] == "local_review_evidence_hold", outcome
    h.lane.assert_stopped(outcome, reviews=2)
    assert inventory(h.attempt) == h.original


def test_git_replacement_cannot_disguise_same_content_as_a_correction(history):
    h = history
    h.apply()
    h.corrected(empty=True)
    path = h.lane.root / "earlier.py"
    path.write_text("value = 42  # replacement object, not corrected HEAD content\n")
    local.git(h.lane.root, "add", "earlier.py")
    tree = local.git(h.lane.root, "write-tree")
    replacement = local.git(h.lane.root, "commit-tree", tree, "-p", h.expected["head_sha"], "-m", "replacement")
    local.git(h.lane.root, "restore", "--source=HEAD", "--staged", "--worktree", "earlier.py")
    local.git(h.lane.root, "replace", h.lane.head, replacement)
    outcome = h.lane.execute()
    assert outcome["failure_class"] == "local_review_evidence_hold", outcome
    assert "unchanged PR content" in " ".join(outcome["errors"])
    h.lane.assert_stopped(outcome, reviews=1)
    assert inventory(h.attempt) == h.original


@pytest.mark.parametrize("local_base", ["stale", "absent"])
def test_public_recovery_uses_verified_remote_base_without_moving_local_refs(history, local_base):
    h = history
    if local_base == "stale":
        tree = local.git(h.lane.root, "rev-parse", h.lane.base + "^{tree}")
        stale = local.git(h.lane.root, "commit-tree", tree, "-m", "old local branch tip")
        local.git(h.lane.root, "update-ref", "refs/heads/dev", stale)
    else:
        local.git(h.lane.root, "update-ref", "-d", "refs/heads/dev")
    before = inventory(h.lane.root)
    refs = local.git(h.lane.root, "show-ref")
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 0, response.stdout + response.stderr
    assert inventory(h.lane.root) == before
    document = json.loads(response.stdout)
    assert document["plan"]["approval"] is False
    h.apply(document)
    assert h.verify()["history"]["document"] == document
    h.assert_hold()
    assert local.git(h.lane.root, "show-ref") == refs
    h.corrected(empty=True)
    h.assert_hold()
    h.corrected()
    outcome = h.resume()
    assert outcome["status"] == "success", outcome
    assert len(h.lane.reviews) == 2 and len(h.lane.landed) == 1
    assert h.lane.receipts()[0]["identity"]["head_sha"] == h.lane.head
    assert inventory(h.attempt) == h.original


@pytest.mark.parametrize("fault", [
    "missing-ref", "wrong-ref", "symbolic-ref", "tag-ref", "missing-origin",
    "wrong-repository", "wrong-host", "multiple-urls", "rewritten-url",
    "missing-fetch", "wrong-fetch-source", "wrong-fetch-target", "ambiguous-fetch",
    "competing-remote",
])
def test_public_recovery_rejects_missing_wrong_or_ambiguous_remote_base(history, fault):
    h = history
    root = h.lane.root
    ref = "refs/remotes/origin/dev"
    if fault == "missing-ref":
        local.git(root, "update-ref", "-d", ref)
    elif fault == "wrong-ref":
        local.git(root, "update-ref", ref, h.lane.head)
    elif fault == "symbolic-ref":
        local.git(root, "symbolic-ref", ref, "refs/heads/dev")
    elif fault == "tag-ref":
        local.git(root, "tag", "-a", "base-alias", h.lane.base, "-m", "not an exact base commit ref")
        local.git(root, "update-ref", ref, local.git(root, "rev-parse", "refs/tags/base-alias"))
    elif fault == "missing-origin":
        local.git(root, "remote", "remove", "origin")
    elif fault in {"wrong-repository", "wrong-host"}:
        url = "https://github.com/other/repo.git" if fault == "wrong-repository" else "https://foreign.invalid/fixture/repo.git"
        local.git(root, "remote", "set-url", "origin", url)
    elif fault == "multiple-urls":
        local.git(root, "config", "--add", "remote.origin.url", "https://github.com/fixture/repo.git")
    elif fault == "rewritten-url":
        local.git(root, "config", "url.https://foreign.invalid/.insteadOf", "https://github.com/")
    elif fault == "missing-fetch":
        local.git(root, "config", "--unset-all", "remote.origin.fetch")
    elif fault in {"wrong-fetch-source", "wrong-fetch-target", "ambiguous-fetch"}:
        spec = {"wrong-fetch-source": "+refs/heads/other:refs/remotes/origin/dev",
                "wrong-fetch-target": "+refs/heads/dev:refs/remotes/untrusted/dev",
                "ambiguous-fetch": "+refs/heads/dev:refs/remotes/origin/dev"}[fault]
        local.git(root, "config", "--add" if fault == "ambiguous-fetch" else "--replace-all",
                  "remote.origin.fetch", spec)
    else:
        local.git(root, "remote", "add", "foreign", "https://github.com/foreign/repo.git")
        local.git(root, "config", "--replace-all", "remote.foreign.fetch", "+refs/heads/*:refs/remotes/origin/*")
    before = inventory(root)
    response = h.cli("plan", *h.cli_plan_args())
    assert response.returncode == 1, response.stdout + response.stderr
    assert json.loads(response.stdout)["status"] == "held"
    assert inventory(root) == before


@pytest.mark.parametrize("operation", ["apply", "verify", "resume"])
def test_remote_base_authority_is_revalidated_after_plan_and_publication(history, operation):
    h = history
    document = h.plan()
    if operation != "apply":
        h.apply(document)
        h.corrected()
    local.git(h.lane.root, "update-ref", "refs/remotes/origin/dev", h.lane.head)
    if operation == "apply":
        with pytest.raises(ValueError):
            h.apply(document)
    elif operation == "verify":
        with pytest.raises(ValueError):
            h.verify()
    else:
        h.assert_hold()
    assert inventory(h.attempt) == h.original
