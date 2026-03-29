#!/usr/bin/env python3
"""Commit executor: 15-step mechanical commit pipeline.

Same command every time. Script infers state. No caller memory.
Bounded post-commit continuation only; no separate caller-managed resume mode.

Steps:
 1  validate_inputs           All handoff fields present + correct types
 2  ensure_feature_branch     Create or verify target branch
 3  ensure_tracker_note       Append tracker note to TASKS.md if missing
 4  stage_files               git add files_to_stage + force_add_files
 5  collect_and_stage_indicator  Run indicator collector, force-add artifact
 6  build_and_run_supervisor  Build 11-field package, run supervisor
 7  validate_receipt          Read receipt JSON, check decision
 8  run_pre_commit_script     Explicit pre-commit-doc-check run
 9  git_commit                git commit -m <message>
10  hold_check                COMMIT_GO_HOLD_PUSH = terminal stop
11  run_pre_push_script       Explicit pre-push-fast run
12  git_push                  Push to origin
13  ensure_pr                 Create or reuse PR
14  wait_ci                   gh pr checks --watch --required
15  ensure_review_clear_and_merge  Query reviews, merge if clear

See: reports/control_plane/commit_pipeline_automation_plan_2026-03-22.md
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        MAX_WAVE_ID_LEN,
        WAVE_ID_RE,
        normalize_wave_id,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    MAX_WAVE_ID_LEN = _mod.MAX_WAVE_ID_LEN
    WAVE_ID_RE = _mod.WAVE_ID_RE
    normalize_wave_id = _mod.normalize_wave_id
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError

BRANCH_PREFIX_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

FORCE_ADD_DENYLIST = (".git/", ".env", ".agent_bus/")

REQUIRED_HANDOFF_FIELDS = {
    "wave_id", "wave_class", "target_gate_id", "branch_prefix",
    "tracker_note_text", "fixes_implemented", "files_to_stage",
    "force_add_files", "commit_message", "pr_title", "pr_body",
    "base_branch", "pre_commit_receipt_path", "task_id", "caller",
}
OPTIONAL_HANDOFF_FIELDS = {
    "supervisor_lane",
    "deferred_items",
    "bridge_status",
    "scope_items",
    "evidence_handles",
}

VALID_CALLERS = {"phase_b", "phase_a", "update_tracker_only"}

# GraphQL query for PR review state
PR_REVIEW_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      headRefOid
      reviewDecision
      latestReviews(first: 20) {
        nodes {
          author { login }
          state
          submittedAt
          commit { oid }
        }
      }
      reviewThreads(first: 100) {
        nodes {
          isResolved
          isOutdated
          comments(last: 20) {
            nodes {
              author { login }
              body
              path
              line
              createdAt
            }
          }
        }
      }
      comments(last: 30) {
        nodes {
          databaseId
          author { login }
          body
          createdAt
        }
      }
    }
  }
}
"""

BOT_REVIEW_LOGIN = "chatgpt-codex-connector"
BOT_REVIEW_TRIGGER_COMMENT = "@codex review"
BOT_REVIEW_WAIT_SECONDS = 210
BOT_REVIEW_ACK_WAIT_SECONDS = 900
BOT_REVIEW_POLL_SECONDS = 15
BOT_REVIEW_ACK_REACTION = "eyes"
CI_CHECK_REGISTRATION_WAIT_SECONDS = 120
CI_CHECK_REGISTRATION_POLL_SECONDS = 5
BOT_NO_ISSUES_COMMENT_RE = re.compile(
    r"Codex Review:\s*.*did(?:n't| not) find any major issues",
    re.IGNORECASE | re.DOTALL,
)
BOT_USAGE_LIMIT_COMMENT_RE = re.compile(
    r"reached your Codex usage limits",
    re.IGNORECASE,
)
COMMIT_CONTINUATION_VERSION = 1
CONTINUATION_ACTIVE_STATUS = "post_commit_pending"
TRANSIENT_STATUS_PREFIXES = (".agent_bus/", ".scratch/")


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sanitized env."""
    run_env = env
    if run_env is None:
        run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=check,
        timeout=timeout, env=run_env,
    )


def _handoff_sha(handoff: dict[str, Any]) -> str:
    canonical = json.dumps(handoff, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _continuation_record_path(repo_root: Path, wave_id: str) -> Path:
    return repo_root / ".agent_bus" / "executors" / f"commit_executor_{wave_id}.json"


def _write_continuation_record(
    path: Path,
    *,
    handoff_sha: str,
    target_branch: str,
    commit_sha: str,
    receipt_decision: str,
    steps_completed: list[str],
    pr_number: str | None = None,
    bot_review_request_sha: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_payload = _read_continuation_record(path) or {}
    payload: dict[str, Any] = {
        "version": COMMIT_CONTINUATION_VERSION,
        "status": CONTINUATION_ACTIVE_STATUS,
        "handoff_sha": handoff_sha,
        "target_branch": target_branch,
        "commit_sha": commit_sha,
        "receipt_decision": receipt_decision,
        "steps_completed": list(steps_completed),
        "updated_at_unix": int(time.time()),
    }
    if pr_number:
        payload["pr_number"] = pr_number
    preserved_bot_review_request_sha = existing_payload.get("bot_review_request_sha")
    if bot_review_request_sha:
        payload["bot_review_request_sha"] = bot_review_request_sha
    elif isinstance(preserved_bot_review_request_sha, str) and preserved_bot_review_request_sha:
        payload["bot_review_request_sha"] = preserved_bot_review_request_sha
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _clear_continuation_record(path: Path) -> None:
    if path.exists():
        path.unlink()


def _read_continuation_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _load_post_commit_continuation(
    path: Path,
    *,
    repo_root: Path,
    handoff_sha: str,
    target_branch: str,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _read_continuation_record(path)
    if payload is None:
        return None
    if payload.get("version") != COMMIT_CONTINUATION_VERSION:
        return None
    if payload.get("status") != CONTINUATION_ACTIVE_STATUS:
        return None
    if payload.get("handoff_sha") != handoff_sha:
        return None
    if payload.get("target_branch") != target_branch:
        return None

    commit_sha = payload.get("commit_sha")
    if not isinstance(commit_sha, str) or not commit_sha.strip():
        return None
    receipt_decision = payload.get("receipt_decision")
    if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return None
    steps_completed = payload.get("steps_completed")
    if not isinstance(steps_completed, list) or "git_commit" not in steps_completed:
        return None

    try:
        head_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        branch_name = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
        ).stdout.strip()
        status_output = _run(["git", "status", "--short"], cwd=repo_root).stdout.splitlines()
    except subprocess.CalledProcessError:
        return None

    if branch_name != target_branch:
        return None
    if head_sha != commit_sha:
        return None
    non_transient_status = []
    for line in status_output:
        path_text = line[3:] if len(line) > 3 else line
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        if path_text.startswith(TRANSIENT_STATUS_PREFIXES):
            continue
        non_transient_status.append(line)
    if non_transient_status:
        return None

    return payload


def _checkpoint_post_commit_progress(
    result: dict[str, Any],
    *,
    continuation_path: Path,
    target_branch: str,
) -> None:
    commit_sha = result.get("commit_sha")
    receipt_decision = result.get("receipt_decision")
    handoff_sha = result.get("handoff_sha")
    steps_completed = result.get("steps_completed")
    if not isinstance(commit_sha, str) or not commit_sha:
        return
    if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return
    if not isinstance(handoff_sha, str) or not handoff_sha:
        return
    if not isinstance(steps_completed, list) or "git_commit" not in steps_completed:
        return

    pr_number_val = result.get("pr_number")
    pr_number = str(pr_number_val) if pr_number_val else None
    bot_review_request_sha = result.get("bot_review_request_sha")
    _write_continuation_record(
        continuation_path,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
        commit_sha=commit_sha,
        receipt_decision=receipt_decision,
        steps_completed=steps_completed,
        pr_number=pr_number,
        bot_review_request_sha=bot_review_request_sha if isinstance(bot_review_request_sha, str) else None,
    )


def _decode_untrusted_path(path_str: str) -> str | None:
    """Decode percent escapes and normalize compatibility characters."""
    normalized = path_str.replace("\\", "/")
    for _ in range(4):
        if "%" not in normalized:
            break
        try:
            next_normalized = unquote(normalized, errors="strict")
        except UnicodeDecodeError:
            return None
        if next_normalized == normalized:
            break
        normalized = next_normalized
    return unicodedata.normalize("NFKC", normalized)


def _is_absolute_untrusted_path(path_str: str) -> bool:
    """Reject absolute POSIX, UNC, or Windows drive-rooted paths."""
    normalized = _decode_untrusted_path(path_str)
    if normalized is None:
        return True
    if "\x00" in normalized:
        return True
    normalized = normalized.replace("\\", "/")
    if normalized.startswith("//"):
        return True
    if normalized.startswith("/"):
        return True
    return bool(re.match(r"^[A-Za-z]:/", normalized))


def _has_path_traversal(path_str: str) -> bool:
    """Check for decoded traversal components and hostile separators."""
    normalized = _decode_untrusted_path(path_str)
    if normalized is None:
        return True
    if "\x00" in normalized:
        return True
    parts = Path(normalized.replace("\\", "/")).parts
    return ".." in parts


def _count_exact_wave_id_mentions(text: str, wave_id: str) -> int:
    """Count lines containing an exact wave_id without substring false positives."""
    pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(wave_id)}(?![a-z0-9-])")
    return sum(1 for line in text.splitlines() if pattern.search(line))


def _is_canonical_tracker_note_line(line: str, wave_id: str) -> bool:
    """Return True when *line* is a parseable canonical tracker note for *wave_id*."""
    return bool(re.match(
        rf"^- Tracker sync note \(([^,]+),\s*{re.escape(wave_id)}\):\s*\*\*[^*]+\*\*.*\bClass:\s*",
        line,
    ))


def _matching_tracker_note_indices(lines: list[str], wave_id: str) -> list[int]:
    """Return line indices for tracker-note-shaped lines that reference *wave_id*."""
    pattern = re.compile(rf"(?<![a-z0-9-]){re.escape(wave_id)}(?![a-z0-9-])")
    indices: list[int] = []
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("- Tracker sync note"):
            continue
        if pattern.search(line):
            indices.append(i)
    return indices


def _matching_tracker_note_indices_in_range(
    lines: list[str],
    wave_id: str,
    *,
    start_idx: int,
    end_idx: int,
) -> list[int]:
    """Return tracker-note-shaped line indices for *wave_id* inside one section."""
    return [
        idx for idx in _matching_tracker_note_indices(lines, wave_id)
        if start_idx <= idx < end_idx
    ]


def _find_ra_section_range(lines: list[str]) -> tuple[int | None, int | None]:
    """Return [start, end) indices for the active ## Ra section."""
    ra_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Ra"):
            ra_idx = i
            break
    if ra_idx is None:
        return None, None

    ra_end_idx = len(lines)
    for i in range(ra_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped == "---" and i > ra_idx + 1:
            ra_end_idx = i
            break
        if stripped.startswith("## ") and i > ra_idx:
            ra_end_idx = i
            break
    return ra_idx, ra_end_idx


def _force_add_denied_match(path_str: str) -> str | None:
    """Return the denylist token matched by a force-add path, if any."""
    normalized = path_str.replace("\\", "/")
    lowered = normalized.lower()
    parts = [part.lower() for part in Path(normalized).parts]
    if ".git" in parts:
        return ".git/"
    if any(
        part == ".env"
        or part == ".envrc"
        or part.startswith(".env.")
        or part.startswith(".envrc.")
        for part in parts
    ):
        return ".env*"
    if ".agent_bus" in parts:
        return ".agent_bus/"
    for denied in FORCE_ADD_DENYLIST:
        if lowered.startswith(denied.lower()):
            return denied
    return None


def _parse_origin_owner_repo(repo_root: Path) -> tuple[str, str]:
    remote_url = _run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_root,
    ).stdout.strip()
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.rstrip("/").split("/")
    repo_owner = parts[-2]
    repo_name = parts[-1]
    if ":" in repo_owner:
        repo_owner = repo_owner.split(":")[-1]
    return repo_owner, repo_name


def _query_pr_review_state(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
) -> dict[str, Any]:
    review_result = _run(
        ["gh", "api", "graphql", "-f",
         f"query={PR_REVIEW_QUERY}",
         "-F", f"owner={repo_owner}",
         "-F", f"repo={repo_name}",
         "-F", f"number={pr_number}"],
        cwd=repo_root,
        timeout=30,
    )
    review_data = json.loads(review_result.stdout)
    pr_data = review_data.get("data", {}).get("repository", {}).get("pullRequest", {})
    if not isinstance(pr_data, dict):
        raise ValueError("PR review query returned no pullRequest object")
    return pr_data


def _pr_head_matches_expected(pr_data: dict[str, Any], head_sha: str) -> bool:
    pr_head = pr_data.get("headRefOid", "")
    return isinstance(pr_head, str) and pr_head == head_sha


def _assert_expected_pr_head(pr_data: dict[str, Any], head_sha: str) -> None:
    pr_head = pr_data.get("headRefOid", "")
    if not isinstance(pr_head, str) or not pr_head:
        raise ValueError("PR review query missing headRefOid")
    if pr_head != head_sha:
        raise ValueError(
            f"PR head moved from expected {head_sha[:8]} to {pr_head[:8]} "
            f"while waiting for {BOT_REVIEW_LOGIN}"
        )


def _has_fresh_connector_review(pr_data: dict[str, Any], head_sha: str) -> bool:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return False
    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    if not isinstance(latest_reviews, list):
        return False
    for review in latest_reviews:
        if not isinstance(review, dict):
            continue
        author = review.get("author", {}).get("login", "")
        commit_oid = review.get("commit", {}).get("oid", "")
        if _is_connector_review_author(author) and commit_oid == head_sha:
            return True
    return False


def _iter_pr_issue_comments(pr_data: dict[str, Any]) -> list[dict[str, Any]]:
    comments = pr_data.get("comments", {}).get("nodes", [])
    if not isinstance(comments, list):
        return []
    return [comment for comment in comments if isinstance(comment, dict)]


def _latest_bot_review_request_comment(pr_data: dict[str, Any]) -> dict[str, Any] | None:
    latest_request: dict[str, Any] | None = None
    for comment in _iter_pr_issue_comments(pr_data):
        author = comment.get("author", {}).get("login", "")
        body = (comment.get("body") or "").strip()
        created_at = comment.get("createdAt", "")
        if _is_bot_review_author(author):
            continue
        if body != BOT_REVIEW_TRIGGER_COMMENT:
            continue
        if not isinstance(created_at, str) or not created_at:
            continue
        if latest_request is None or created_at > latest_request.get("createdAt", ""):
            latest_request = comment
    return latest_request


def _latest_bot_review_request_timestamp(pr_data: dict[str, Any]) -> str | None:
    latest_request = _latest_bot_review_request_comment(pr_data)
    if latest_request is None:
        return None
    created_at = latest_request.get("createdAt", "")
    if not isinstance(created_at, str) or not created_at:
        return None
    return created_at


def _latest_current_head_connector_review_timestamp(
    pr_data: dict[str, Any],
    head_sha: str,
) -> str | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    latest_timestamp: str | None = None
    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    if not isinstance(latest_reviews, list):
        return None
    for review in latest_reviews:
        if not isinstance(review, dict):
            continue
        author = review.get("author", {}).get("login", "")
        commit_oid = review.get("commit", {}).get("oid", "")
        submitted_at = review.get("submittedAt", "")
        if not _is_connector_review_author(author) or commit_oid != head_sha:
            continue
        if not isinstance(submitted_at, str) or not submitted_at:
            continue
        if latest_timestamp is None or submitted_at > latest_timestamp:
            latest_timestamp = submitted_at
    return latest_timestamp


def _current_review_cycle_floor_timestamp(
    pr_data: dict[str, Any],
    head_sha: str,
) -> str | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    latest_request_at = _latest_bot_review_request_timestamp(pr_data)
    latest_review_at = _latest_current_head_connector_review_timestamp(pr_data, head_sha)
    if latest_request_at is None:
        return latest_review_at
    if latest_review_at is None:
        return latest_request_at
    request_seconds = _parse_github_timestamp_seconds(latest_request_at)
    review_seconds = _parse_github_timestamp_seconds(latest_review_at)
    if request_seconds is None or review_seconds is None:
        return latest_review_at if latest_review_at >= latest_request_at else latest_request_at
    return latest_review_at if review_seconds >= request_seconds else latest_request_at


def _parse_github_timestamp_seconds(timestamp: str) -> float | None:
    if not isinstance(timestamp, str) or not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _is_bot_no_issues_issue_comment(body: str) -> bool:
    return bool(BOT_NO_ISSUES_COMMENT_RE.search(body or ""))


def _latest_relevant_thread_comment(
    thread: dict[str, Any],
    *,
    floor_timestamp: str | None,
) -> dict[str, Any] | None:
    comments = thread.get("comments", {}).get("nodes", [])
    if not isinstance(comments, list):
        return None
    floor_seconds = _parse_github_timestamp_seconds(floor_timestamp or "")
    latest_comment: dict[str, Any] | None = None
    latest_seconds: float | None = None
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        created_at = comment.get("createdAt", "")
        created_seconds = _parse_github_timestamp_seconds(created_at)
        if floor_seconds is not None and (created_seconds is None or created_seconds < floor_seconds):
            continue
        if latest_comment is None:
            latest_comment = comment
            latest_seconds = created_seconds
            continue
        if created_seconds is None:
            continue
        if latest_seconds is None or created_seconds >= latest_seconds:
            latest_comment = comment
            latest_seconds = created_seconds
    return latest_comment


def _current_head_connector_issue_comment_outcome(
    pr_data: dict[str, Any],
    head_sha: str,
) -> dict[str, Any] | None:
    if not _pr_head_matches_expected(pr_data, head_sha):
        return None
    floor_timestamp = _current_review_cycle_floor_timestamp(pr_data, head_sha)
    if floor_timestamp is None:
        return None

    latest_bot_comment: dict[str, Any] | None = None
    for comment in _iter_pr_issue_comments(pr_data):
        author = comment.get("author", {}).get("login", "")
        created_at = comment.get("createdAt", "")
        if not _is_connector_review_author(author):
            continue
        if not isinstance(created_at, str) or not created_at or created_at <= floor_timestamp:
            continue
        if latest_bot_comment is None or created_at > latest_bot_comment.get("createdAt", ""):
            latest_bot_comment = comment

    if latest_bot_comment is None:
        return None

    body = latest_bot_comment.get("body", "") or ""
    if BOT_USAGE_LIMIT_COMMENT_RE.search(body):
        kind = "usage_limit"
    elif _is_bot_no_issues_issue_comment(body):
        kind = "clear"
    else:
        kind = "other"

    return {
        "kind": kind,
        "author": latest_bot_comment.get("author", {}).get("login", ""),
        "body": body,
        "createdAt": latest_bot_comment.get("createdAt", ""),
    }


def _bot_review_request_acknowledged(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_data: dict[str, Any],
) -> bool:
    latest_request = _latest_bot_review_request_comment(pr_data)
    if latest_request is None:
        return False
    comment_id = latest_request.get("databaseId")
    if not isinstance(comment_id, int) or comment_id <= 0:
        return False
    try:
        response = _run(
            ["gh", "api", f"repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}/reactions"],
            cwd=repo_root,
            timeout=30,
        )
        reactions = json.loads(response.stdout or "[]")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return False
    if not isinstance(reactions, list):
        return False
    for reaction in reactions:
        if not isinstance(reaction, dict):
            continue
        content = reaction.get("content", "")
        author = reaction.get("user", {}).get("login", "")
        if content == BOT_REVIEW_ACK_REACTION and _is_connector_review_author(author):
            return True
    return False


def _normalize_bot_login(author: str) -> str:
    if author.endswith("[bot]"):
        return author[:-5]
    return author


def _is_connector_review_author(author: str) -> bool:
    if not author:
        return False
    return _normalize_bot_login(author) == BOT_REVIEW_LOGIN


def _is_bot_review_author(author: str) -> bool:
    if not author:
        return False
    normalized = _normalize_bot_login(author)
    return (
        normalized == BOT_REVIEW_LOGIN
        or author.endswith("[bot]")
        or author.endswith("-bot")
    )


def _wait_for_bot_review_freshness(
    query_pr_state: Any,
    *,
    head_sha: str,
    wait_seconds: int = BOT_REVIEW_WAIT_SECONDS,
    request_acknowledged: Any = None,
    acknowledged_wait_seconds: int = BOT_REVIEW_ACK_WAIT_SECONDS,
    poll_interval: int = BOT_REVIEW_POLL_SECONDS,
    log: Any = None,
) -> dict[str, Any]:
    start_time = time.time()
    deadline = start_time + wait_seconds
    last_pr_data: dict[str, Any] | None = None
    acknowledgement_logged = False
    while True:
        pr_data = query_pr_state()
        last_pr_data = pr_data
        _assert_expected_pr_head(pr_data, head_sha)
        if _has_fresh_connector_review(pr_data, head_sha):
            if log is not None:
                log(f"Fresh {BOT_REVIEW_LOGIN} review observed for {head_sha[:8]}")
            return pr_data
        issue_comment_outcome = _current_head_connector_issue_comment_outcome(pr_data, head_sha)
        if issue_comment_outcome is not None:
            if log is not None:
                if issue_comment_outcome["kind"] == "clear":
                    log(
                        f"Fresh {BOT_REVIEW_LOGIN} no-issues issue comment observed "
                        f"for {head_sha[:8]}"
                    )
                else:
                    log(
                        f"Fresh {BOT_REVIEW_LOGIN} issue comment observed for "
                        f"{head_sha[:8]} ({issue_comment_outcome['kind']})"
                    )
            return pr_data
        if request_acknowledged is not None and request_acknowledged(pr_data):
            acknowledged_deadline = start_time + acknowledged_wait_seconds
            request_started = _parse_github_timestamp_seconds(
                _latest_bot_review_request_timestamp(pr_data) or ""
            )
            if request_started is not None:
                acknowledged_deadline = request_started + acknowledged_wait_seconds
            deadline = max(deadline, acknowledged_deadline)
            if log is not None and not acknowledgement_logged:
                log(
                    f"{BOT_REVIEW_LOGIN} acknowledged the current-head review request "
                    f"for {head_sha[:8]}; extending wait to {acknowledged_wait_seconds}s"
                )
            acknowledgement_logged = True
        if time.time() >= deadline:
            effective_wait_seconds = int(max(wait_seconds, deadline - start_time))
            raise TimeoutError(
                f"No current-head {BOT_REVIEW_LOGIN} review or issue-comment clearance "
                f"for {head_sha[:8]} within {effective_wait_seconds}s"
            )
        if log is not None:
            log(
                f"Waiting for {BOT_REVIEW_LOGIN} review signal on {head_sha[:8]} "
                f"({poll_interval}s poll)"
            )
        time.sleep(poll_interval)


def _maybe_request_current_head_bot_review(
    repo_root: Path,
    *,
    pr_number: str,
    head_sha: str,
    continuation_path: Path,
    log: Any = None,
) -> bool:
    continuation = _read_continuation_record(continuation_path)
    if continuation and continuation.get("bot_review_request_sha") == head_sha:
        # Re-request if the original request is older than the wait timeout —
        # the connector may have dropped the webhook and a fresh comment gives
        # the delivery system another chance.
        updated_at = continuation.get("updated_at_unix", 0)
        if time.time() - updated_at < BOT_REVIEW_WAIT_SECONDS:
            return False
    _run(
        ["gh", "pr", "comment", pr_number, "--body", BOT_REVIEW_TRIGGER_COMMENT],
        cwd=repo_root,
        timeout=30,
    )
    if continuation:
        continuation["bot_review_request_sha"] = head_sha
        continuation["updated_at_unix"] = int(time.time())
        continuation_path.write_text(json.dumps(continuation, indent=2) + "\n", encoding="utf-8")
    if log is not None:
        log(
            f"Requested current-head {BOT_REVIEW_LOGIN} review for {head_sha[:8]} "
            f"via PR comment"
        )
    return True


def _has_recorded_current_head_bot_request(
    continuation_path: Path,
    head_sha: str,
) -> bool:
    continuation = _read_continuation_record(continuation_path)
    return bool(
        isinstance(continuation, dict)
        and continuation.get("bot_review_request_sha") == head_sha
    )


def _wait_for_required_checks_to_register(
    repo_root: Path,
    *,
    pr_number: str,
    wait_seconds: int = CI_CHECK_REGISTRATION_WAIT_SECONDS,
    poll_interval: int = CI_CHECK_REGISTRATION_POLL_SECONDS,
    log: Any = None,
) -> None:
    deadline = time.time() + wait_seconds
    while True:
        result = _run(
            ["gh", "pr", "checks", pr_number, "--required"],
            cwd=repo_root,
            timeout=30,
            check=False,
        )
        detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
        if "no checks reported" not in detail.lower():
            if result.returncode not in (0, 8):
                raise subprocess.CalledProcessError(
                    result.returncode,
                    result.args,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            return
        if time.time() >= deadline:
            raise TimeoutError(
                f"Required checks did not register for PR #{pr_number} within {wait_seconds}s"
            )
        if log is not None:
            log(
                f"Waiting for required checks to register on PR #{pr_number} "
                f"({poll_interval}s poll)"
            )
        time.sleep(poll_interval)


def prepare_handoff_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Prepare a commit handoff from a routing record.

    Used when the dispatcher routes UPDATE_TRACKER_ONLY or COMMIT_GO
    to commit_executor without a pre-prepared handoff file.

    The routing record must contain enough information to build a valid
    handoff. Returns (handoff_dict, errors). If errors is non-empty,
    handoff_dict is None.
    """
    errors: list[str] = []

    wave_name = record.get("wave_name") or record.get("wave_id", "")
    if not wave_name:
        errors.append("Routing record missing wave_name/wave_id")

    summary = record.get("summary", "")
    if not summary:
        errors.append("Routing record missing summary")

    decision = record.get("decision", "")

    # Look for handoff fields in the record itself (supervisor may embed them)
    embedded_handoff = record.get("handoff")
    if isinstance(embedded_handoff, dict):
        embedded_copy = copy.deepcopy(embedded_handoff)
        valid, handoff_errors = validate_handoff(embedded_copy)
        if valid:
            return embedded_copy, []
        return None, [f"Embedded handoff invalid: {err}" for err in handoff_errors]

    # COMMIT_GO / COMMIT_GO_HOLD_PUSH require a pre-prepared handoff with
    # an exact Phase B receipt chain.  Synthesizing one here would point at
    # the canonical hook receipt instead of the per-invocation Phase B
    # receipt, breaking the authority chain.  Only embedded handoffs
    # (validated above) are accepted for these decisions.
    if decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return None, [
            f"{decision} requires a pre-prepared Phase B handoff (or valid "
            f"embedded handoff). Cannot synthesize a handoff from a routing "
            f"record — the receipt chain would be broken."
        ]

    # For UPDATE_TRACKER_ONLY: construct a minimal tracker-only handoff
    candidates = record.get("next_candidates", [])
    files_to_stage = record.get("files_to_stage", [])
    tracker_note = record.get("tracker_note_text", "")

    # Try to derive files_to_stage from candidates if not directly provided
    if not files_to_stage:
        for c in candidates:
            cf = c.get("files", [])
            if cf:
                files_to_stage.extend(cf)

    # For UPDATE_TRACKER_ONLY, at minimum we need the tracker note
    if decision == "UPDATE_TRACKER_ONLY" and not tracker_note:
        # Try to derive from summary
        wave_id_safe = wave_name.replace(" ", "-").lower()
        tracker_note = f"- Tracker sync note ({wave_id_safe}): {summary}"

    if not files_to_stage:
        # Default to TASKS.md for tracker-only updates
        if decision == "UPDATE_TRACKER_ONLY":
            files_to_stage = ["TASKS.md"]
        else:
            errors.append("Cannot derive files_to_stage from routing record")

    if errors:
        return None, errors

    # Normalize wave_id for branch naming
    wave_id = normalize_wave_id(wave_name)

    handoff = {
        "wave_id": wave_id,
        "task_id": record.get("task_id", f"[{wave_name}]"),
        "wave_class": record.get("wave_class", "MAINTENANCE"),
        "target_gate_id": record.get("target_gate_id", "NONE"),
        "caller": "update_tracker_only" if decision == "UPDATE_TRACKER_ONLY" else "phase_b",
        "branch_prefix": "jabramsja",
        "tracker_note_text": tracker_note,
        "fixes_implemented": record.get("fixes_implemented", [summary]),
        "files_to_stage": files_to_stage,
        "force_add_files": record.get("force_add_files", []),
        "commit_message": record.get("commit_message", f"chore: {summary}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"),
        "pr_title": record.get("pr_title", f"chore: {summary}"[:70]),
        "pr_body": record.get("pr_body", f"## Summary\n\n- {summary}"),
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
    }

    return handoff, []


def build_commit_handoff(
    *,
    wave_id: str,
    task_id: str,
    files_to_stage: list[str],
    commit_message: str,
    fixes_implemented: list[str],
    wave_class: str = "L4_ENABLER",
    target_gate_id: str = "G8",
    caller: str = "phase_b",
    base_branch: str = "dev",
    branch_prefix: str = "jabramsja",
    force_add_files: list[str] | None = None,
    pr_title: str | None = None,
    pr_body: str | None = None,
    tracker_note_text: str | None = None,
    supervisor_lane: str | None = None,
    deferred_items: list[str] | None = None,
    scope_items: list[str] | None = None,
    evidence_handles: dict[str, str] | None = None,
    pre_commit_receipt_path: str | None = None,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a validated commit handoff from essential fields.

    Fills in defaults for optional fields, auto-detects .gitignored files
    for force_add_files, finds the latest COMMIT_GO receipt if not provided,
    and validates the result against the handoff schema.

    Returns (handoff_dict, errors). If errors is non-empty, the handoff is invalid.
    """
    errors: list[str] = []

    if not wave_id:
        errors.append("wave_id is required")
    if not task_id:
        errors.append("task_id is required")
    if not files_to_stage:
        errors.append("files_to_stage is required")
    if not commit_message:
        errors.append("commit_message is required")
    if not fixes_implemented:
        errors.append("fixes_implemented is required")
    if errors:
        return {}, errors

    # Auto-detect .gitignored files and move to force_add_files
    effective_files = list(files_to_stage)
    effective_force = list(force_add_files or [])
    if repo_root:
        for f in list(effective_files):
            try:
                result = subprocess.run(
                    ["git", "check-ignore", "-q", f],
                    cwd=repo_root, capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    effective_files.remove(f)
                    if f not in effective_force:
                        effective_force.append(f)
            except (subprocess.SubprocessError, OSError):
                pass

    # Auto-find latest COMMIT_GO receipt if not provided
    # Use the canonical receipt path — no directory-sort discovery.
    # The commit executor's Step 6 runs the supervisor and gets a fresh
    # per-invocation receipt. This handoff receipt is provenance only.
    effective_receipt = pre_commit_receipt_path or ".agent_bus/meta/pre_commit_receipt.json"

    handoff = {
        "wave_id": wave_id,
        "task_id": task_id,
        "wave_class": wave_class,
        "target_gate_id": target_gate_id,
        "caller": caller,
        "branch_prefix": branch_prefix,
        "tracker_note_text": tracker_note_text or (
            f"- Tracker sync note ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}, {wave_id}): "
            f"**{commit_message}**. Class: {wave_class}. "
            f"target_gate_id: {target_gate_id}. "
            f"primary_blocker_class: INTEGRATION. "
            f"primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            f"boot0_track_id: V1. boot0_progress_state: HOLD."
        ),
        "fixes_implemented": fixes_implemented,
        "files_to_stage": effective_files,
        "force_add_files": effective_force,
        "commit_message": commit_message,
        "pr_title": pr_title or commit_message[:70],
        "pr_body": pr_body or f"## Summary\n\n" + "\n".join(f"- {f}" for f in fixes_implemented),
        "base_branch": base_branch,
        "pre_commit_receipt_path": effective_receipt,
    }

    # Add optional fields if provided
    if supervisor_lane:
        handoff["supervisor_lane"] = supervisor_lane
    if deferred_items is not None:
        handoff["deferred_items"] = deferred_items
    if scope_items:
        handoff["scope_items"] = scope_items
    if evidence_handles:
        handoff["evidence_handles"] = evidence_handles

    # Validate against schema
    valid, validation_errors = validate_handoff(handoff)
    if not valid:
        return handoff, validation_errors

    return handoff, []


def validate_handoff(handoff: dict[str, Any]) -> tuple[bool, list[str]]:
    """Step 1: Validate all handoff fields."""
    if not isinstance(handoff, dict):
        return False, ["Handoff must be a JSON object"]

    errors: list[str] = []

    allowed_fields = REQUIRED_HANDOFF_FIELDS | OPTIONAL_HANDOFF_FIELDS
    unexpected = sorted(set(handoff.keys()) - allowed_fields)
    if unexpected:
        errors.extend(f"Unexpected field: {field}" for field in unexpected)

    # Required fields
    missing = REQUIRED_HANDOFF_FIELDS - set(handoff.keys())
    if missing:
        errors.extend(f"Missing field: {f}" for f in sorted(missing))
        return False, errors

    # base_branch must be dev
    if handoff.get("base_branch") != "dev":
        errors.append(f"base_branch must be 'dev', got '{handoff.get('base_branch')}'")

    # wave_id regex
    wave_id = handoff.get("wave_id", "")
    if not isinstance(wave_id, str) or not WAVE_ID_RE.fullmatch(wave_id):
        errors.append(f"wave_id must match {WAVE_ID_RE.pattern}, got '{wave_id}'")

    # pre_commit_receipt_path: must be string, relative, within repo
    receipt_path_val = handoff.get("pre_commit_receipt_path")
    if not isinstance(receipt_path_val, str):
        errors.append(f"pre_commit_receipt_path must be a string, got {type(receipt_path_val).__name__}")
    elif not receipt_path_val.strip():
        errors.append("pre_commit_receipt_path must be non-empty")
    else:
        if os.path.isabs(receipt_path_val):
            errors.append(f"pre_commit_receipt_path must be relative, got absolute: {receipt_path_val}")
        elif _is_absolute_untrusted_path(receipt_path_val):
            errors.append(f"pre_commit_receipt_path must stay within repo, got absolute-like path: {receipt_path_val}")
        if _has_path_traversal(receipt_path_val):
            errors.append(f"Path traversal in pre_commit_receipt_path: {receipt_path_val}")

    # files_to_stage must be non-empty list of strings
    fts = handoff.get("files_to_stage")
    if not isinstance(fts, list) or not fts:
        errors.append("files_to_stage must be a non-empty list")
    elif not all(isinstance(f, str) for f in fts):
        errors.append("files_to_stage entries must be strings")
    else:
        for f in fts:
            if _is_absolute_untrusted_path(f):
                errors.append(f"Absolute path in files_to_stage: {f}")
            if _has_path_traversal(f):
                errors.append(f"Path traversal in files_to_stage: {f}")

    # force_add_files validation + denylist (case-insensitive for macOS)
    faf = handoff.get("force_add_files", [])
    if not isinstance(faf, list):
        errors.append("force_add_files must be a list")
    else:
        for f in faf:
            if not isinstance(f, str):
                errors.append("force_add_files entries must be strings")
                continue
            if _is_absolute_untrusted_path(f):
                errors.append(f"Absolute path in force_add_files: {f}")
            if _has_path_traversal(f):
                errors.append(f"Path traversal in force_add_files: {f}")
            denied = _force_add_denied_match(f)
            if denied:
                errors.append(f"force_add_files denied: {f} (matches {denied})")

    supervisor_lane = handoff.get("supervisor_lane")
    if supervisor_lane is not None:
        if not isinstance(supervisor_lane, str) or not supervisor_lane.strip():
            errors.append("supervisor_lane must be a non-empty string when provided")

    deferred_items = handoff.get("deferred_items")
    if deferred_items is not None:
        if not isinstance(deferred_items, list):
            errors.append("deferred_items must be a list when provided")
        else:
            for item in deferred_items:
                if not isinstance(item, str):
                    errors.append("deferred_items entries must be strings")
                    continue
                if _is_absolute_untrusted_path(item):
                    errors.append(f"Absolute path in deferred_items: {item}")
                if _has_path_traversal(item):
                    errors.append(f"Path traversal in deferred_items: {item}")

    bridge_status = handoff.get("bridge_status")
    if bridge_status is not None and not isinstance(bridge_status, dict):
        errors.append("bridge_status must be an object when provided")

    scope_items = handoff.get("scope_items")
    if scope_items is not None:
        if not isinstance(scope_items, list):
            errors.append("scope_items must be a list when provided")
        else:
            for item in scope_items:
                if not isinstance(item, str):
                    errors.append("scope_items entries must be strings")
                    continue
                if _is_absolute_untrusted_path(item):
                    errors.append(f"Absolute path in scope_items: {item}")
                if _has_path_traversal(item):
                    errors.append(f"Path traversal in scope_items: {item}")

    evidence_handles = handoff.get("evidence_handles")
    if evidence_handles is not None:
        if not isinstance(evidence_handles, dict):
            errors.append("evidence_handles must be an object when provided")
        else:
            for key, value in evidence_handles.items():
                if not isinstance(key, str) or not key.strip():
                    errors.append("evidence_handles keys must be non-empty strings")
                if not isinstance(value, str):
                    errors.append(f"evidence_handles['{key}'] must be a string")

    # tracker_note_text must be non-empty string
    tnt = handoff.get("tracker_note_text", "")
    if not isinstance(tnt, str) or not tnt.strip():
        errors.append("tracker_note_text must be a non-empty string")

    # fixes_implemented must be non-empty list of strings
    fi = handoff.get("fixes_implemented")
    if not isinstance(fi, list) or not fi:
        errors.append("fixes_implemented must be a non-empty list")
    elif not all(isinstance(f, str) for f in fi):
        errors.append("fixes_implemented entries must be strings")

    # String fields
    for fld in ("commit_message", "pr_title", "pr_body", "task_id", "caller",
                "branch_prefix", "wave_class", "target_gate_id"):
        val = handoff.get(fld)
        if not isinstance(val, str) or not val.strip():
            errors.append(f"{fld} must be a non-empty string")

    branch_prefix = handoff.get("branch_prefix", "")
    if isinstance(branch_prefix, str) and branch_prefix and not BRANCH_PREFIX_RE.fullmatch(branch_prefix):
        errors.append(f"branch_prefix contains unsafe characters: {branch_prefix}")

    # Caller validation
    caller = handoff.get("caller", "")
    if caller and caller not in VALID_CALLERS:
        errors.append(f"caller must be one of {sorted(VALID_CALLERS)}, got: {caller}")

    return len(errors) == 0, errors


def _run_post_commit_pipeline(
    *,
    handoff: dict[str, Any],
    repo_root: Path,
    result: dict[str, Any],
    target_branch: str,
    base_branch: str,
    continuation_path: Path,
    log: Any,
) -> dict[str, Any]:
    pr_number = str(result.get("pr_number") or "")

    # ── Step 11: run_pre_push_script ──────────────────────────────────
    if "run_pre_push_script" not in result["steps_completed"]:
        pre_push_script = repo_root / "mu" / "tools" / "hooks" / "pre-push-fast"
        if pre_push_script.exists():
            try:
                _run(["bash", str(pre_push_script)], cwd=repo_root, timeout=300)
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or "").strip()
                if not detail:
                    detail = f"exit {exc.returncode}"
                return {"status": "error", "step": "run_pre_push_script",
                        "errors": [f"pre-push-fast failed: {detail[:500]}"],
                        "steps_completed": result["steps_completed"]}
            except subprocess.TimeoutExpired:
                return {"status": "error", "step": "run_pre_push_script",
                        "errors": ["pre-push-fast timed out"],
                        "steps_completed": result["steps_completed"]}
        result["steps_completed"].append("run_pre_push_script")
        _checkpoint_post_commit_progress(
            result,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
        log("Step 11: pre-push script passed")
    else:
        log("Step 11: pre-push script already passed, skipping")

    # ── Step 12: git_push ─────────────────────────────────────────────
    if "git_push" not in result["steps_completed"]:
        try:
            _run(
                # Step 11 already ran the exact pre-push gate for this local head.
                ["git", "push", "--no-verify", "-u", "origin", target_branch],
                cwd=repo_root, timeout=300,
            )
            result["steps_completed"].append("git_push")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
            log(f"Step 12: pushed to origin/{target_branch}")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "git_push",
                    "errors": [f"git push failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "git_push",
                    "errors": ["git push timed out"],
                    "steps_completed": result["steps_completed"]}
    else:
        log(f"Step 12: push already completed for {target_branch}, skipping")

    # ── Step 13: ensure_pr ────────────────────────────────────────────
    if "ensure_pr" not in result["steps_completed"]:
        try:
            existing_prs = _run(
                ["gh", "pr", "list", "--head", target_branch, "--base", base_branch,
                 "--state", "open", "--json", "number"],
                cwd=repo_root, timeout=30,
            ).stdout.strip()
            pr_list = json.loads(existing_prs) if existing_prs else []
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pr_list = []

        if len(pr_list) > 1:
            return {"status": "error", "step": "ensure_pr",
                    "errors": [f"Multiple open PRs for {target_branch}: {[p['number'] for p in pr_list]}"],
                    "steps_completed": result["steps_completed"]}

        if len(pr_list) == 1:
            pr_number = str(pr_list[0]["number"])
            if not pr_number.isdigit():
                return {"status": "error", "step": "ensure_pr",
                        "errors": [f"PR number non-numeric: {pr_number}"],
                        "steps_completed": result["steps_completed"]}
            try:
                _run(
                    ["gh", "pr", "edit", pr_number,
                     "--title", handoff["pr_title"],
                     "--body", handoff["pr_body"]],
                    cwd=repo_root, timeout=30,
                )
                log(f"Step 13: reused PR #{pr_number}, synced metadata")
            except subprocess.CalledProcessError as exc:
                log(f"Step 13: PR edit warning: {exc.stderr.strip()[:200]}")
        else:
            try:
                pr_create_result = _run(
                    ["gh", "pr", "create",
                     "--base", base_branch,
                     "--head", target_branch,
                     "--title", handoff["pr_title"],
                     "--body", handoff["pr_body"]],
                    cwd=repo_root, timeout=30,
                )
                pr_url = pr_create_result.stdout.strip()
                pr_number = pr_url.rstrip("/").split("/")[-1]
                if not pr_number.isdigit():
                    return {"status": "error", "step": "ensure_pr",
                            "errors": [f"PR number non-numeric from URL: {pr_url}"],
                            "steps_completed": result["steps_completed"]}
                log(f"Step 13: created PR #{pr_number}")
            except subprocess.CalledProcessError as exc:
                return {"status": "error", "step": "ensure_pr",
                        "errors": [f"gh pr create failed: {exc.stderr.strip()}"],
                        "steps_completed": result["steps_completed"]}
            except subprocess.TimeoutExpired:
                return {"status": "error", "step": "ensure_pr",
                        "errors": ["gh pr create timed out"],
                        "steps_completed": result["steps_completed"]}

        result["pr_number"] = pr_number
        result["steps_completed"].append("ensure_pr")
        _checkpoint_post_commit_progress(
            result,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
    else:
        pr_number = str(result.get("pr_number") or pr_number)
        log(f"Step 13: PR #{pr_number or 'unknown'} already ensured, skipping")

    # ── Step 14: wait_ci ──────────────────────────────────────────────
    if "wait_ci" not in result["steps_completed"]:
        log(f"Step 14: waiting for CI on PR #{pr_number}...")
        try:
            _wait_for_required_checks_to_register(
                repo_root,
                pr_number=pr_number,
                log=log,
            )
            _run(
                ["gh", "pr", "checks", pr_number, "--watch", "--required"],
                cwd=repo_root, timeout=600,
            )
            result["steps_completed"].append("wait_ci")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
            log("Step 14: CI passed")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "wait_ci",
                    "errors": [f"CI checks failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "wait_ci",
                    "errors": ["CI wait timed out after 600s"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        except TimeoutError as exc:
            return {"status": "error", "step": "wait_ci",
                    "errors": [str(exc)],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
    else:
        log(f"Step 14: required checks already passed for PR #{pr_number}, skipping")

    # ── Step 15: ensure_review_clear_and_merge ────────────────────────
    log(f"Step 15: checking review state for PR #{pr_number}...")

    try:
        repo_owner, repo_name = _parse_origin_owner_repo(repo_root)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError):
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["Cannot determine repo owner/name from git remote"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        head_sha_before_merge = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
        ).stdout.strip()
        pr_data = _query_pr_review_state(
            repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
        )
        _assert_expected_pr_head(pr_data, head_sha_before_merge)
        existing_issue_comment_outcome = None
        if _has_recorded_current_head_bot_request(continuation_path, head_sha_before_merge):
            existing_issue_comment_outcome = _current_head_connector_issue_comment_outcome(
                pr_data,
                head_sha_before_merge,
            )
        if (
            not _has_fresh_connector_review(pr_data, head_sha_before_merge)
            and existing_issue_comment_outcome is None
        ):
            _maybe_request_current_head_bot_review(
                repo_root,
                pr_number=pr_number,
                head_sha=head_sha_before_merge,
                continuation_path=continuation_path,
                log=log,
            )
            pr_data = _wait_for_bot_review_freshness(
                lambda: _query_pr_review_state(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                ),
                head_sha=head_sha_before_merge,
                request_acknowledged=lambda pr_data: _bot_review_request_acknowledged(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_data=pr_data,
                ),
                log=log,
            )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
        TimeoutError,
    ) as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Review query failed: {exc}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    _assert_expected_pr_head(pr_data, head_sha_before_merge)
    issue_comment_outcome = _current_head_connector_issue_comment_outcome(
        pr_data,
        head_sha_before_merge,
    )
    if issue_comment_outcome is not None:
        if issue_comment_outcome["kind"] == "usage_limit":
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"{BOT_REVIEW_LOGIN} issue comment reported usage-limit exhaustion"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        if issue_comment_outcome["kind"] == "other":
            return {
                "status": "bot_findings_pending",
                "bot_findings": [{
                    "author": issue_comment_outcome["author"],
                    "body": issue_comment_outcome["body"][:500],
                    "path": "",
                    "line": None,
                }],
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
            }

    review_decision = pr_data.get("reviewDecision", "")
    if review_decision == "CHANGES_REQUESTED":
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["reviewDecision is CHANGES_REQUESTED"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    for review in latest_reviews:
        author = review.get("author", {}).get("login", "")
        state = review.get("state", "")
        is_bot = _is_bot_review_author(author)
        if not is_bot and state == "CHANGES_REQUESTED":
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Human reviewer {author} requested changes"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}

    threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    current_review_cycle_floor = _current_review_cycle_floor_timestamp(
        pr_data,
        head_sha_before_merge,
    )
    bot_findings = []
    for thread in threads:
        if thread.get("isResolved"):
            continue
        latest_comment = _latest_relevant_thread_comment(
            thread,
            floor_timestamp=current_review_cycle_floor,
        )
        if latest_comment is None:
            continue
        author = latest_comment.get("author", {}).get("login", "")
        is_bot = _is_bot_review_author(author)
        if not is_bot:
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Unresolved human review thread from {author}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        if thread.get("isOutdated"):
            continue
        bot_findings.append({
            "author": author,
            "body": latest_comment.get("body", "")[:500],
            "path": latest_comment.get("path", ""),
            "line": latest_comment.get("line"),
        })

    if bot_findings:
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    merge_script = repo_root / "mu" / "tools" / "hooks" / "merge_pr.sh"
    if not merge_script.exists():
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["merge_pr.sh not found"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        _run(
            ["bash", str(merge_script), pr_number, "--sweep"],
            cwd=repo_root, timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"merge_pr.sh failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        current_after = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
        ).stdout.strip()
        if current_after != base_branch:
            _run(["git", "checkout", base_branch], cwd=repo_root)
            _run(["git", "pull"], cwd=repo_root, timeout=60)

        head_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        status_output = _run(["git", "status", "--short"], cwd=repo_root).stdout.strip()
        if status_output:
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Post-merge working tree is dirty:\n{status_output}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        result["merge_sha"] = head_sha
        if "ensure_review_clear_and_merge" not in result["steps_completed"]:
            result["steps_completed"].append("ensure_review_clear_and_merge")
        _clear_continuation_record(continuation_path)
        log(f"Step 15: merged, HEAD={head_sha[:8]}, clean tree verified")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Post-merge verify failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    return result


def run_commit_pipeline(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute the 15-step commit pipeline.

    Same command every time. Automatic bounded continuation after a local
    commit is allowed; no extra resume flags.
    """
    try:
        ensure_not_agent_review_mode("commit_executor.run_commit_pipeline")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "step": "review_mode_guard",
            "errors": [str(exc)],
            "steps_completed": [],
        }

    result: dict[str, Any] = {
        "status": "success",
        "steps_completed": [],
        "pr_number": None,
        "merge_sha": None,
    }

    # Tee log to file for pipeline monitor observability
    _log_path = repo_root / ".scratch" / "commit_executor_live.log"
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_fp = open(_log_path, "w", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[commit-executor] {msg}"
        if verbose:
            print(line, flush=True)
        try:
            _log_fp.write(line + "\n")
            _log_fp.flush()
        except (OSError, ValueError):
            pass

    # ── Step 1: validate_inputs ──────────────────────────────────────
    valid, errors = validate_handoff(handoff)
    if not valid:
        return {"status": "error", "step": "validate_inputs", "errors": errors}
    result["steps_completed"].append("validate_inputs")
    log("Step 1: inputs validated")

    wave_id = handoff["wave_id"]
    branch_prefix = handoff["branch_prefix"]
    target_branch = f"{branch_prefix}/{wave_id}"
    base_branch = handoff["base_branch"]
    handoff_sha = _handoff_sha(handoff)
    result["handoff_sha"] = handoff_sha
    continuation_path = _continuation_record_path(repo_root, wave_id)
    continuation = _load_post_commit_continuation(
        continuation_path,
        repo_root=repo_root,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
    )
    if continuation:
        result["steps_completed"] = list(continuation.get("steps_completed", []))
        result["commit_sha"] = continuation["commit_sha"]
        result["pr_number"] = continuation.get("pr_number")
        log(
            "Resuming post-commit pipeline from local commit "
            f"{continuation['commit_sha'][:8]}"
        )

    # ── Step 2: ensure_feature_branch ────────────────────────────────
    try:
        current = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        return {"status": "error", "step": "ensure_feature_branch",
                "errors": ["Cannot determine current branch"],
                "steps_completed": result["steps_completed"]}

    if current == base_branch:
        # On dev — check for collisions, then create
        try:
            local_check = _run(
                ["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"],
                cwd=repo_root, check=False,
            )
            if local_check.returncode == 0:
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Local branch {target_branch} already exists"],
                        "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": ["Timeout checking local branches"],
                    "steps_completed": result["steps_completed"]}

        try:
            remote_check = _run(
                ["git", "ls-remote", "--heads", "origin", target_branch],
                cwd=repo_root, check=False, timeout=30,
            )
            if remote_check.stdout.strip():
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Remote branch {target_branch} already exists"],
                        "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": ["Timeout checking remote branches"],
                    "steps_completed": result["steps_completed"]}

        try:
            _run(["git", "checkout", "-b", target_branch], cwd=repo_root)
            log(f"Step 2: created branch {target_branch}")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": [f"git checkout -b failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"]}
    elif current == target_branch:
        log(f"Step 2: already on {target_branch}")
    else:
        return {"status": "error", "step": "ensure_feature_branch",
                "errors": [f"On branch {current}, expected {base_branch} or {target_branch}"],
                "steps_completed": result["steps_completed"]}

    if "ensure_feature_branch" not in result["steps_completed"]:
        result["steps_completed"].append("ensure_feature_branch")

    if continuation:
        result["receipt_decision"] = continuation["receipt_decision"]
        if continuation["receipt_decision"] == "COMMIT_GO_HOLD_PUSH":
            _clear_continuation_record(continuation_path)
            return {
                "status": "held",
                "commit_sha": continuation["commit_sha"],
                "steps_completed": result["steps_completed"],
                "message": "Committed locally. Pipeline held before push per COMMIT_GO_HOLD_PUSH.",
            }
        log("Continuation record valid; skipping steps 3-10 and resuming at push")
        return _run_post_commit_pipeline(
            handoff=handoff,
            repo_root=repo_root,
            result=result,
            target_branch=target_branch,
            base_branch=base_branch,
            continuation_path=continuation_path,
            log=log,
        )

    # ── Step 3: ensure_tracker_note ──────────────────────────────────
    tracker_note_text = handoff["tracker_note_text"]
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": ["TASKS.md not found"],
                "steps_completed": result["steps_completed"]}

    tasks_content = tasks_path.read_text(encoding="utf-8")
    lines = tasks_content.splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": ["## Ra section not found in TASKS.md"],
                "steps_completed": result["steps_completed"]}

    ra_content = "".join(lines[ra_idx:ra_end_idx])
    ra_wave_id_count = _count_exact_wave_id_mentions(ra_content, wave_id)
    matching_tracker_indices = _matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_tracker_indices = [
        idx for idx in matching_tracker_indices
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"

    if ra_wave_id_count > 1 and not matching_tracker_indices:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": [f"wave_id '{wave_id}' appears {ra_wave_id_count} times in active ## Ra section of TASKS.md (duplicate)"],
                "steps_completed": result["steps_completed"]}
    if len(canonical_tracker_indices) > 1:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": [f"wave_id '{wave_id}' has {len(canonical_tracker_indices)} canonical tracker notes in TASKS.md (duplicate)"],
                "steps_completed": result["steps_completed"]}

    tasks_modified = False
    if canonical_tracker_indices:
        canonical_idx = canonical_tracker_indices[0]
        if lines[canonical_idx] != note_line:
            lines[canonical_idx] = note_line
            tasks_path.write_text("".join(lines), encoding="utf-8")
            tasks_modified = True
            log(f"Step 3: tracker note updated for {wave_id}")
        else:
            log(f"Step 3: tracker note for {wave_id} already present, skipping")
    elif matching_tracker_indices:
        # Insert after the last tracker note in Ra, or repair a single malformed
        # tracker-note-shaped line for this wave in place.
        last_tracker_idx = None
        for i in range(ra_idx + 1, ra_end_idx):
            if lines[i].strip().startswith("- Tracker sync note"):
                last_tracker_idx = i

        if len(matching_tracker_indices) == 1:
            lines[matching_tracker_indices[0]] = note_line
            log(f"Step 3: tracker note repaired for {wave_id}")
        else:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": [f"wave_id '{wave_id}' has {len(matching_tracker_indices)} malformed tracker notes in TASKS.md (duplicate)"],
                    "steps_completed": result["steps_completed"]}
        tasks_path.write_text("".join(lines), encoding="utf-8")

        # Verify
        verify_content = tasks_path.read_text(encoding="utf-8")
        if _count_exact_wave_id_mentions(verify_content, wave_id) == 0:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["wave_id not found in TASKS.md after write"],
                    "steps_completed": result["steps_completed"]}
        tasks_modified = True
    elif ra_wave_id_count == 1:
        log(f"Step 3: wave_id {wave_id} already referenced outside tracker notes, skipping")
    else:
        # Insert after the last tracker note in Ra section
        last_tracker_idx = None
        for i in range(ra_idx + 1, ra_end_idx):
            if lines[i].strip().startswith("- Tracker sync note"):
                last_tracker_idx = i

        if last_tracker_idx is not None:
            insert_idx = last_tracker_idx + 1
        else:
            # No tracker notes yet — insert after Ra header + description
            insert_idx = ra_idx + 2 if ra_end_idx and ra_end_idx > ra_idx + 2 else ra_idx + 1

        lines.insert(insert_idx, note_line)
        tasks_path.write_text("".join(lines), encoding="utf-8")

        verify_content = tasks_path.read_text(encoding="utf-8")
        if _count_exact_wave_id_mentions(verify_content, wave_id) == 0:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["wave_id not found in TASKS.md after write"],
                    "steps_completed": result["steps_completed"]}
        tasks_modified = True
        log(f"Step 3: tracker note inserted for {wave_id}")

    result["steps_completed"].append("ensure_tracker_note")

    # ── Step 4: stage_files ──────────────────────────────────────────
    files_to_stage = list(handoff["files_to_stage"])
    force_files = list(handoff.get("force_add_files", []))

    # Auto-add TASKS.md if modified in step 3
    if tasks_modified and "TASKS.md" not in files_to_stage:
        files_to_stage.append("TASKS.md")

    try:
        if files_to_stage:
            _run(["git", "add", "--", *files_to_stage], cwd=repo_root)
        if force_files:
            _run(["git", "add", "-f", "--", *force_files], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "stage_files",
                "errors": [f"git add failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"]}

    # Verify something is staged (do NOT auto-add indicator — step 5 handles)
    try:
        staged_output = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        staged_output = ""

    if not staged_output:
        return {"status": "error", "step": "stage_files",
                "errors": ["Nothing staged after git add (nothing to commit)"],
                "steps_completed": result["steps_completed"]}

    result["steps_completed"].append("stage_files")
    log(f"Step 4: staged {len(staged_output.splitlines())} files")

    # ── Step 5: collect_and_stage_indicator ───────────────────────────
    indicator_script = repo_root / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"

    if indicator_script.exists():
        try:
            _run(
                ["python3", str(indicator_script), "--wave-id", wave_id,
                 "--output", indicator_path],
                cwd=repo_root, timeout=30,
            )
            indicator_full = repo_root / indicator_path
            if not indicator_full.exists():
                return {"status": "error", "step": "collect_and_stage_indicator",
                        "errors": [f"Indicator artifact not created: {indicator_path}"],
                        "steps_completed": result["steps_completed"]}
            _run(["git", "add", "-f", "--", indicator_path], cwd=repo_root)
            result["steps_completed"].append("collect_and_stage_indicator")
            log(f"Step 5: indicator collected and staged at {indicator_path}")
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "collect_and_stage_indicator",
                    "errors": [f"Indicator collection failed: {exc.stderr.strip()[:300]}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "collect_and_stage_indicator",
                    "errors": ["Indicator collection timed out"],
                    "steps_completed": result["steps_completed"]}
    else:
        log("Step 5: indicator script not found, skipping")
        result["steps_completed"].append("collect_and_stage_indicator")

    # ── Step 6: build_and_run_supervisor ──────────────────────────────
    try:
        changed_files = _run(
            ["git", "diff", "--cached", "--name-only"], cwd=repo_root
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        changed_files = []

    if not changed_files:
        return {"status": "error", "step": "build_and_run_supervisor",
                "errors": ["changed_files empty — nothing staged for supervisor"],
                "steps_completed": result["steps_completed"]}

    # Discover blockers
    blocking_dir = repo_root / "reports" / "deferred" / "blocking"
    blocker_paths = sorted(
        str(p.relative_to(repo_root))
        for p in blocking_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and p.name != "README.md"
    ) if blocking_dir.is_dir() else []

    scope_items = handoff.get("scope_items")
    if isinstance(scope_items, list) and scope_items:
        supervisor_scope_items = list(dict.fromkeys([*scope_items, *handoff["files_to_stage"]]))
    else:
        supervisor_scope_items = list(handoff["files_to_stage"])

    evidence_handles: dict[str, str] = {}
    handoff_evidence_handles = handoff.get("evidence_handles")
    if isinstance(handoff_evidence_handles, dict):
        evidence_handles.update(handoff_evidence_handles)
    if "collect_and_stage_indicator" in result["steps_completed"]:
        evidence_handles.setdefault("indicator", indicator_path)

    supervisor_package = {
        "task_id": handoff["task_id"],
        "wave_name": wave_id,
        "lane": handoff.get("supervisor_lane", handoff["caller"]),
        "changed_files": changed_files,
        "scope_items": supervisor_scope_items,
        "fixes_implemented": handoff["fixes_implemented"],
        "deferred_items": handoff.get("deferred_items", []),
        "bridge_status": handoff.get("bridge_status", {}),
        "evidence_handles": evidence_handles,
        "blocker_report_paths": blocker_paths,
        "current_judgment": "COMMIT_GO",
    }

    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    pkg_path = scratch_dir / "auto_supervisor_package.json"
    pkg_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

    # Run supervisor via structured client
    try:
        agents_dir = str(repo_root / "mu" / "tools" / "agents")
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)
        from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
        sup_result = run_meta_bridge_package(pkg_path, wait_for_lock_seconds=30, verbose=verbose)
        if sup_result.decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Supervisor returned {sup_result.decision}: {sup_result.summary[:200]}"],
                    "steps_completed": result["steps_completed"]}
        receipt_path_from_supervisor = sup_result.receipt_path
        receipt_decision = sup_result.decision

        # Validate supervisor receipt path is non-empty, relative, within repo.
        # The supervisor-returned receipt path is the runtime authority — it
        # reflects the actual staged state post-injection that the supervisor reviewed.
        if not receipt_path_from_supervisor:
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": ["Supervisor returned empty receipt_path — fail closed"],
                    "steps_completed": result["steps_completed"]}
        if os.path.isabs(receipt_path_from_supervisor):
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Supervisor returned absolute receipt_path — fail closed: {receipt_path_from_supervisor}"],
                    "steps_completed": result["steps_completed"]}
        if _has_path_traversal(receipt_path_from_supervisor):
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Path traversal in supervisor receipt_path — fail closed: {receipt_path_from_supervisor}"],
                    "steps_completed": result["steps_completed"]}
        # Verify the receipt resolves inside repo_root
        resolved_repo = repo_root.resolve()
        resolved_receipt = (repo_root / receipt_path_from_supervisor).resolve()
        if not resolved_receipt.is_relative_to(resolved_repo):
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Supervisor receipt_path escapes repo — fail closed: {receipt_path_from_supervisor}"],
                    "steps_completed": result["steps_completed"]}

        result["steps_completed"].append("build_and_run_supervisor")
        log(f"Step 6: supervisor {receipt_decision}, receipt: {receipt_path_from_supervisor}")
    except ImportError as exc:
        return {"status": "error", "step": "build_and_run_supervisor",
                "errors": [f"Cannot import meta_bridge_client: {exc}"],
                "steps_completed": result["steps_completed"]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "step": "build_and_run_supervisor",
                "errors": ["Supervisor timed out"],
                "steps_completed": result["steps_completed"]}
    except Exception as exc:
        return {"status": "error", "step": "build_and_run_supervisor",
                "errors": [f"Supervisor failed: {exc}"],
                "steps_completed": result["steps_completed"]}

    # ── Step 7: validate_receipt ──────────────────────────────────────
    # Preserve the exact Phase B receipt chain first, then read the fresh
    # step-6 supervisor receipt for the final commit decision. The handoff
    # receipt path remains required authority provenance even though the
    # supervisor receipt is the only receipt minted after tracker/indicator
    # mutations in steps 3-5.
    handoff_receipt_rel = handoff["pre_commit_receipt_path"]
    # Containment check: handoff receipt must resolve inside the repo root.
    # Reject path traversal and symlinks that escape the repo boundary.
    if _has_path_traversal(handoff_receipt_rel):
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Path traversal in handoff receipt path: {handoff_receipt_rel}"],
                "steps_completed": result["steps_completed"]}
    handoff_receipt_file = (repo_root / handoff_receipt_rel).resolve()
    if not handoff_receipt_file.is_relative_to(repo_root.resolve()):
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Handoff receipt escapes repo root: {handoff_receipt_rel}"],
                "steps_completed": result["steps_completed"]}
    if not handoff_receipt_file.exists():
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Phase B handoff receipt not found at: {handoff_receipt_rel}"],
                "steps_completed": result["steps_completed"]}

    try:
        handoff_receipt_data = json.loads(handoff_receipt_file.read_text(encoding="utf-8"))
        handoff_receipt_decision = handoff_receipt_data.get("decision", "")
        if handoff_receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            return {"status": "error", "step": "validate_receipt",
                    "errors": [f"Phase B handoff receipt decision '{handoff_receipt_decision}' does not authorize commit"],
                    "steps_completed": result["steps_completed"]}
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Phase B handoff receipt unreadable: {exc}"],
                "steps_completed": result["steps_completed"]}

    receipt_file = repo_root / receipt_path_from_supervisor
    if not receipt_file.exists():
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Supervisor receipt not found at: {receipt_path_from_supervisor}"],
                "steps_completed": result["steps_completed"]}

    try:
        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
        receipt_decision = receipt_data.get("decision", "")
        if receipt_decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            return {"status": "error", "step": "validate_receipt",
                    "errors": [f"Receipt decision '{receipt_decision}' does not authorize commit"],
                    "steps_completed": result["steps_completed"]}
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "step": "validate_receipt",
                "errors": [f"Supervisor receipt unreadable: {exc}"],
                "steps_completed": result["steps_completed"]}

    result["handoff_receipt_path"] = handoff_receipt_rel
    result["handoff_receipt_decision"] = handoff_receipt_decision
    result["receipt_decision"] = receipt_decision
    result["handoff_sha"] = handoff_sha
    result["steps_completed"].append("validate_receipt")
    log(
        "Step 7: receipt chain verified "
        f"(handoff={handoff_receipt_decision}, supervisor={receipt_decision})"
    )

    # ── Step 8: run_pre_commit_script ─────────────────────────────────
    pre_commit_script = repo_root / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
    if pre_commit_script.exists():
        try:
            _run(["bash", str(pre_commit_script)], cwd=repo_root, timeout=30)
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": [f"pre-commit-doc-check failed: {exc.stderr.strip()[:300]}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": ["pre-commit-doc-check timed out"],
                    "steps_completed": result["steps_completed"]}
    result["steps_completed"].append("run_pre_commit_script")
    log("Step 8: pre-commit script passed")

    # ── Step 9: git_commit ────────────────────────────────────────────
    try:
        commit_out = _run(
            ["git", "commit", "-m", handoff["commit_message"]],
            cwd=repo_root, timeout=60,
        )
        commit_sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        result["commit_sha"] = commit_sha
        result["steps_completed"].append("git_commit")
        _write_continuation_record(
            continuation_path,
            handoff_sha=handoff_sha,
            target_branch=target_branch,
            commit_sha=commit_sha,
            receipt_decision=receipt_decision,
            steps_completed=result["steps_completed"],
        )
        log(f"Step 9: committed")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "git_commit",
                "errors": [f"git commit failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "step": "git_commit",
                "errors": ["git commit timed out"],
                "steps_completed": result["steps_completed"]}

    # ── Step 10: hold_check ───────────────────────────────────────────
    if receipt_decision == "COMMIT_GO_HOLD_PUSH":
        sha = result.get("commit_sha", "unknown")
        result["steps_completed"].append("hold_check")
        _clear_continuation_record(continuation_path)
        return {
            "status": "held",
            "commit_sha": sha,
            "steps_completed": result["steps_completed"],
            "message": f"Committed locally. Pipeline held before push per COMMIT_GO_HOLD_PUSH.",
        }

    result["steps_completed"].append("hold_check")
    log("Step 10: COMMIT_GO, continuing to push")
    return _run_post_commit_pipeline(
        handoff=handoff,
        repo_root=repo_root,
        result=result,
        target_branch=target_branch,
        base_branch=base_branch,
        continuation_path=continuation_path,
        log=log,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit executor: 15-step mechanical commit pipeline",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        help="Path to handoff JSON file",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string — commit_executor prepares handoff internally",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1

    if not args.handoff and not args.routing_record:
        print("[error] Provide --handoff <path> or --routing-record <json>", file=sys.stderr)
        return 1

    if args.handoff:
        try:
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[error] Cannot load handoff: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            record = json.loads(args.routing_record)
        except json.JSONDecodeError as exc:
            print(f"[error] Invalid routing record JSON: {exc}", file=sys.stderr)
            return 1
        handoff, prep_errors = prepare_handoff_from_routing_record(record, repo_root)
        if prep_errors or handoff is None:
            print(f"[error] Cannot prepare handoff from routing record: {prep_errors}", file=sys.stderr)
            return 1

    result = run_commit_pipeline(handoff, repo_root=repo_root, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "unknown")
        steps = result.get("steps_completed", [])
        print(f"[commit-executor] Status: {status}")
        print(f"[commit-executor] Steps: {', '.join(steps)}")
        if result.get("pr_number"):
            print(f"[commit-executor] PR: #{result['pr_number']}")
        if result.get("merge_sha"):
            print(f"[commit-executor] Merge SHA: {result['merge_sha'][:8]}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"[commit-executor] Error: {e}")
        if result.get("message"):
            print(f"[commit-executor] {result['message']}")
        if result.get("bot_findings"):
            print(f"[commit-executor] Bot findings: {len(result['bot_findings'])}")
            for bf in result["bot_findings"]:
                print(f"  - {bf['author']}: {bf['body'][:100]}...")

    return 0 if result.get("status") in ("success", "held") else 1


if __name__ == "__main__":
    sys.exit(main())
