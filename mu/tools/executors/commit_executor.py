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
 8  run_pre_commit_script     Explicit pre-commit-doc-check + targeted pytest gate
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
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import unquote

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        DEFAULT_EXECUTOR_CONFIG,
        MAX_WAVE_ID_LEN,
        WAVE_ID_RE,
        ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY,
        ROLE_AGENT_ENV_VARS,
        ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
        agent_bus_path,
        agent_bus_relpath,
        bridge_config_path,
        ensure_bridge_config_path,
        is_agent_bus_runtime_path,
        load_executor_config,
        normalize_wave_id,
        packet_status_is_completed,
        read_control_plane_packet_status,
        read_control_plane_packet_wave_id,
        resolve_agent_bus_dir,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        emit_pipeline_agent_event,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    MAX_WAVE_ID_LEN = _mod.MAX_WAVE_ID_LEN
    WAVE_ID_RE = _mod.WAVE_ID_RE
    ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY = _mod.ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY
    ROLE_AGENT_ENV_VARS = _mod.ROLE_AGENT_ENV_VARS
    ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV = _mod.ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
    bridge_config_path = _mod.bridge_config_path
    ensure_bridge_config_path = _mod.ensure_bridge_config_path
    is_agent_bus_runtime_path = _mod.is_agent_bus_runtime_path
    load_executor_config = _mod.load_executor_config
    normalize_wave_id = _mod.normalize_wave_id
    packet_status_is_completed = _mod.packet_status_is_completed
    read_control_plane_packet_status = _mod.read_control_plane_packet_status
    read_control_plane_packet_wave_id = _mod.read_control_plane_packet_wave_id
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event

_ACTIVE_BUS_DIR: ContextVar[Path | None] = ContextVar("commit_executor_bus_dir", default=None)


def _active_bus_dir() -> Path | None:
    return _ACTIVE_BUS_DIR.get()

_bridge_adapters = None
_bridge_import_error = None
try:
    _agents_dir = str(Path(__file__).resolve().parent.parent / "agents")
    if _agents_dir not in sys.path:
        sys.path.insert(0, _agents_dir)
    import bridge_adapters as _bridge_adapters
except ImportError as _exc:
    _bridge_import_error = _exc

_tracker_sync_note = None
_tracker_sync_import_error = None
try:
    _executors_dir = str(SCRIPT_DIR)
    if _executors_dir not in sys.path:
        sys.path.insert(0, _executors_dir)
    import tracker_sync_note as _tracker_sync_note
except ImportError as _exc:
    _tracker_sync_import_error = _exc

BRANCH_PREFIX_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
TARGET_BRANCH_SUFFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,190}$")
TARGET_GATE_ID_RE = re.compile(r"^G[1-8]$")
PACKET_TARGET_GATE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?:Target Gate|Target gate|target_gate_id)"
    r"(?:\*\*)?\s*:\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?",
    re.IGNORECASE,
)
VALID_WAVE_CLASSES = frozenset({"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"})
PACKET_WAVE_CLASS_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?Class(?:\*\*)?\s*:\s*`?([A-Za-z0-9_ -]+)`?",
    re.IGNORECASE,
)

PRE_COMMIT_DOC_CHECK_TIMEOUT_SECONDS = 120

FORCE_ADD_DENYLIST = tuple(d.lower() for d in (".git/", ".env", ".agent_bus/"))

REQUIRED_HANDOFF_FIELDS = {
    "wave_id", "wave_class", "target_gate_id", "branch_prefix",
    "tracker_note_text", "fixes_implemented", "files_to_stage",
    "force_add_files", "commit_message", "pr_title", "pr_body",
    "base_branch", "pre_commit_receipt_path", "task_id", "caller",
}
OPTIONAL_HANDOFF_FIELDS = {
    "target_branch",
    "tracked_packet",
    "supervisor_lane",
    "deferred_items",
    "bridge_status",
    "scope_items",
    "evidence_handles",
    "pager_route",
}

ALLOWED_HANDOFF_PAGER_ROUTES = frozenset({"codex", "claude", "both", "notify-only"})

VALID_CALLERS = {"phase_b", "phase_a", "update_tracker_only", "standalone"}

# Fields that may be empty/missing when caller is "standalone"
STANDALONE_OPTIONAL_FIELDS = {"pre_commit_receipt_path"}
_STANDALONE_RECOVERY_TERMINAL_STATUSES = frozenset({
    "success",
    "held",
    "question_for_founder",
    "max_rounds_reached",
    "supervisor_rejected",
})
_STANDALONE_RECOVERY_STATUSES = frozenset({
    "bot_findings_pending",
    "needs_phase_b",
    "pre_push_failed",
    "stage_failed",
    "implementer_error",
    "bridge_error",
    "l4_contract_violation",
})
_STANDALONE_RECOVERY_ERROR_STEPS = frozenset({
    "run_pre_push_script",
    "run_pre_commit_script",
    "private_attr_gate",
    "stage_files",
    "implementer",
    "implementer_bridge_fix",
    "implementer_reentry",
    "pytest_fix",
    "bridge_subprocess",
    "reentry_bridge_subprocess",
})


@contextmanager
def _prepend_sys_path(path: Path | str):
    """Temporarily prepend a path for a bounded import without leaking it globally."""
    entry = str(path)
    inserted = False
    if entry and entry not in sys.path:
        sys.path.insert(0, entry)
        inserted = True
    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(entry)
            except ValueError:
                pass


def _load_repo_meta_bridge_client(repo_root: Path) -> tuple[Any, Any]:
    """Import the repo-local meta_bridge_client without leaving temp agent paths on sys.path."""
    try:
        from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
    except ImportError:
        with _prepend_sys_path(repo_root / "mu" / "tools" / "agents"):
            from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
    return run_meta_bridge_package, MetaBridgeClientError


def _load_repo_recovery_symbols(repo_root: Path) -> tuple[Any, Any]:
    """Import standalone recovery helpers without leaking repo_root onto sys.path."""
    try:
        from mu.tools.executors.recovery_gate import attempt_recovery
        from mu.tools.executors.executor_common import normalize_wave_id
    except ImportError:
        with _prepend_sys_path(repo_root):
            from mu.tools.executors.recovery_gate import attempt_recovery
            from mu.tools.executors.executor_common import normalize_wave_id
    return attempt_recovery, normalize_wave_id


def _should_attempt_standalone_recovery(result: dict[str, Any]) -> bool:
    """Return true when a standalone non-success result is recoverable."""
    status = str(result.get("status", "") or "").strip().lower()
    if status in _STANDALONE_RECOVERY_TERMINAL_STATUSES:
        return False
    if status in _STANDALONE_RECOVERY_STATUSES:
        return True
    if str(result.get("failure_class") or "").strip().lower() == "needs_phase_b":
        return True
    step = str(result.get("step", "") or "").strip().lower()
    return status in {"error", "failed", "timeout", "stale"} and (
        step in _STANDALONE_RECOVERY_ERROR_STEPS
    )

# GraphQL query for PR review state
PR_REVIEW_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      headRefOid
      headRefName
      isDraft
      reviewDecision
      latestReviews(first: 20) {
        nodes {
          author { login }
          body
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
BOT_REVIEW_WAIT_SECONDS = 45
BOT_REVIEW_ACK_WAIT_SECONDS = 60
BOT_REVIEW_POLL_SECONDS = 5
BOT_REVIEW_ACK_REACTION = "eyes"
BOT_REVIEW_QUERY_TRANSIENT_ERRORS = (
    subprocess.CalledProcessError,
    subprocess.TimeoutExpired,
    json.JSONDecodeError,
)
CI_CHECK_REGISTRATION_WAIT_SECONDS = 120
CI_CHECK_REGISTRATION_POLL_SECONDS = 5
CI_REQUIRED_PASSING_BUCKETS = {"pass", "skipping"}
CI_REQUIRED_FAILING_BUCKETS = {"fail", "cancel"}
CI_REQUIRED_PENDING_BUCKETS = {"pending"}
CI_REQUIRED_PASSING_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL"}
CI_REQUIRED_FAILING_STATES = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
CI_REQUIRED_PENDING_STATES = {"PENDING", "IN_PROGRESS", "QUEUED", "REQUESTED", "WAITING", "EXPECTED"}
EXPECTED_PR_CHECK_SURFACE = (
    "engine-run-schema",
    "green-gate",
    "orbit-dot",
    "orbit-index",
    "orbit-provenance",
    "orbit-svg",
    "test",
)
_COMMIT_EXECUTOR_CONFIG = load_executor_config(SCRIPT_DIR.parent.parent.parent)
_COMMIT_EXECUTOR_TIMEOUTS = _COMMIT_EXECUTOR_CONFIG.get("timeouts", {})
COMMIT_EXECUTOR_OUTER_BUDGET_S = _COMMIT_EXECUTOR_TIMEOUTS.get(
    "commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"]
)
PRE_PUSH_FAST_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get("pre_push_fast", 900)
COMMIT_CI_WATCH_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get(
    "commit_ci_watch", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_ci_watch"]
)
COMMIT_CI_POLL_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get(
    "commit_ci_poll", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_ci_poll"]
)
COMMIT_CI_VERIFY_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get(
    "commit_ci_verify", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_ci_verify"]
)
BOT_NO_ISSUES_COMMENT_RE = re.compile(
    r"Codex Review:\s*.*did(?:n't| not) find any major issues",
    re.IGNORECASE | re.DOTALL,
)
BOT_USAGE_LIMIT_COMMENT_RE = re.compile(
    r"reached your Codex usage limits",
    re.IGNORECASE,
)
BOT_BLOCKING_REVIEW_BADGE_RE = re.compile(
    r"!\[\s*P[0-2]\s+Badge\s*\]\(|badge/P[0-2]-",
    re.IGNORECASE,
)
COMMIT_CONTINUATION_VERSION = 1
CONTINUATION_ACTIVE_STATUS = "post_commit_pending"
TRANSIENT_STATUS_PREFIXES = (".agent_bus/", ".scratch/")
COMMIT_PATH_REFRESH_START = "<!-- COMMIT_PATH_TRUTH_REFRESH:start -->"
COMMIT_PATH_REFRESH_END = "<!-- COMMIT_PATH_TRUTH_REFRESH:end -->"
DEFERRED_AUTH_REFRESH_START = "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->"
DEFERRED_AUTH_REFRESH_END = "<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->"
COMMIT_GENERATED_GOVERNANCE_AUTH_START = "<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->"
COMMIT_GENERATED_GOVERNANCE_AUTH_END = "<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->"
COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY = "commit_time_generated_governance"
COMMIT_GENERATED_GOVERNANCE_GROWTH_CAP_PATH = "mu/tests/docs/test_growth_caps.py"
COMMIT_GENERATED_GOVERNANCE_STEP5E_PROVENANCES = frozenset(
    ("bumped", "already_recorded")
)

BOT_REMEDIATION_MAX_ROUNDS = 2
_COMMIT_EXECUTOR_BACKENDS = _COMMIT_EXECUTOR_CONFIG.get("backends", {})
BOT_REMEDIATION_ADAPTER = _COMMIT_EXECUTOR_BACKENDS.get(
    "bot_remediation", DEFAULT_EXECUTOR_CONFIG["backends"]["bot_remediation"]
)
BOT_REMEDIATION_TIMEOUT_S = _COMMIT_EXECUTOR_TIMEOUTS.get("bot_remediation", 600)
BOT_REMEDIATION_STALE_TIMEOUT_S = 300.0


def _is_transient_status_path(path: str) -> bool:
    return bool(path) and (
        is_agent_bus_runtime_path(path)
        or any(path.startswith(prefix) for prefix in TRANSIENT_STATUS_PREFIXES)
    )


def _runtime_bus_artifact_match(path: str) -> str | None:
    return ".agent_bus*" if is_agent_bus_runtime_path(path) else None

# Validate sub-timeouts fit within outer budget at import time
for _sub_name, _sub_val in [
    ("pre_push_fast", PRE_PUSH_FAST_TIMEOUT_S),
    ("commit_ci_watch", COMMIT_CI_WATCH_TIMEOUT_S),
    ("commit_ci_poll", COMMIT_CI_POLL_TIMEOUT_S),
    ("commit_ci_verify", COMMIT_CI_VERIFY_TIMEOUT_S),
    ("bot_remediation", BOT_REMEDIATION_TIMEOUT_S),
]:
    if _sub_val > COMMIT_EXECUTOR_OUTER_BUDGET_S:
        raise ExecutorCommonError(
            f"commit_executor sub-timeout {_sub_name}={_sub_val}s exceeds "
            f"outer budget commit_executor={COMMIT_EXECUTOR_OUTER_BUDGET_S}s"
        )


def _extract_founder_override_token(text: Any) -> str:
    """Extract a bounded FOUNDER_OVERRIDE token from untrusted text."""
    if not isinstance(text, str) or not text:
        return ""
    match = re.search(r"FOUNDER_OVERRIDE:\s*(\S+)", text)
    if not match:
        return ""
    return match.group(1).strip().rstrip("`.,;")


def _extract_founder_override_tokens(text: Any) -> list[str]:
    """Extract every bounded FOUNDER_OVERRIDE token from untrusted text."""
    if not isinstance(text, str) or not text:
        return []
    tokens: list[str] = []
    for match in re.finditer(r"FOUNDER_OVERRIDE:\s*(\S+)", text):
        token = _normalize_founder_override_token(match.group(1))
        if token:
            tokens.append(token)
    return tokens


def _extract_same_wave_founder_override_token(text: str, wave_id: str) -> str:
    """Return the first token in text that is bound to wave_id."""
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id:
        return ""
    for token in _extract_founder_override_tokens(text):
        if normalize_wave_id(token) == normalized_wave_id:
            return token
    return ""


def _extract_founder_override_from_tracker_note(text: str) -> str:
    """Extract wave-bound FOUNDER_OVERRIDE token from stored tracker-note text."""
    return _extract_founder_override_token(text)


def _normalize_founder_override_token(token: str | None) -> str:
    """Canonicalize bare or prefixed override input to the bare token id."""
    if not isinstance(token, str):
        return ""
    clean = token.strip()
    if not clean:
        return ""
    extracted = _extract_founder_override_token(clean)
    if extracted:
        return extracted
    return clean.split()[0].strip().rstrip("`.,;")


def _replace_founder_override_token(text: str, token: str) -> str:
    """Replace the first existing override token, or append one if absent."""
    normalized = _normalize_founder_override_token(token)
    if not normalized or not isinstance(text, str):
        return text
    if _extract_founder_override_from_tracker_note(text):
        return re.sub(
            r"FOUNDER_OVERRIDE:\s*\S+",
            f"FOUNDER_OVERRIDE:{normalized}",
            text,
            count=1,
        )
    return _append_founder_override_to_tracker_note(text, normalized)


def _repair_handoff_same_wave_founder_override(
    handoff: dict[str, Any],
    repo_root: Path,
) -> dict[str, Any]:
    """Repair stale override text before tracker sync or supervisor packaging."""
    wave_id = str(handoff.get("wave_id") or "")
    wave_class = str(handoff.get("wave_class") or "")
    if not wave_id or not _wave_class_allows_founder_override(wave_class):
        return handoff
    tracker_note_text = handoff.get("tracker_note_text")
    if not isinstance(tracker_note_text, str) or not tracker_note_text.strip():
        return handoff
    existing = _extract_founder_override_from_tracker_note(tracker_note_text)
    if existing and normalize_wave_id(existing) == normalize_wave_id(wave_id):
        return handoff

    replacement = _extract_same_wave_founder_override_from_tasks(repo_root, wave_id)
    if not replacement:
        replacement = _resolve_control_surface_founder_override_token(
            {
                "wave_id": wave_id,
                "wave_name": wave_id,
                "tracked_packet": handoff.get("tracked_packet", ""),
                "tracker_note_text": tracker_note_text,
            },
            repo_root,
            embedded_handoff=handoff,
            wave_id=wave_id,
            wave_class=wave_class,
        )
    if not replacement:
        return handoff
    repaired = _replace_founder_override_token(tracker_note_text, replacement)
    if repaired == tracker_note_text:
        return handoff
    return {**handoff, "tracker_note_text": repaired}


def _wave_class_allows_founder_override(wave_class: Any) -> bool:
    """Return true only for wave classes allowed to carry founder override tokens."""
    return str(wave_class or "").strip() in ("L4_ENABLER", "MAINTENANCE")


def _extract_maintenance_bypass_fields_from_text(text: str) -> tuple[str, str]:
    """Extract optional consecutive-maintenance bypass fields from text."""
    if not text:
        return "", ""
    unblocks_wave_id = ""
    unblocks_runtime_blocker = ""
    unblocks_wave_pattern = re.compile(
        r"(?<![A-Za-z0-9_])(?:Unblocks wave id:|unblocks_wave_id:)\s*([A-Za-z0-9_-]+)"
    )
    unblocks_runtime_blocker_pattern = re.compile(
        r"(?<![A-Za-z0-9_])(?:Unblocks runtime blocker:|unblocks_runtime_blocker:)\s*(.+?)(?:\.\s|$)"
    )
    for raw_line in text.splitlines():
        clean = str(raw_line or "").strip()
        if not unblocks_wave_id:
            match = unblocks_wave_pattern.search(clean)
            if match:
                unblocks_wave_id = match.group(1).strip().strip("`").rstrip(".,;")
        if not unblocks_runtime_blocker:
            match = unblocks_runtime_blocker_pattern.search(clean)
            if match:
                unblocks_runtime_blocker = match.group(1).strip().strip("`").rstrip(".,;")
        if unblocks_wave_id and unblocks_runtime_blocker:
            return unblocks_wave_id, unblocks_runtime_blocker
    return unblocks_wave_id, unblocks_runtime_blocker


def _dedupe_repo_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_path in paths:
        normalized = _normalize_repo_relpath(raw_path)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _current_staged_diff_paths(repo_root: Path) -> list[str]:
    try:
        proc = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    except subprocess.CalledProcessError:
        return []
    return _dedupe_repo_paths(proc.stdout.splitlines())


def _collect_commit_fenced_dirty_files(
    repo_root: Path,
    commit_bound_files: list[str],
) -> list[str]:
    """Collect dirty paths that belong outside the current commit package."""
    commit_bound = set(_dedupe_repo_paths(commit_bound_files))
    try:
        proc = _run(["git", "status", "--porcelain"], cwd=repo_root, timeout=30)
    except subprocess.CalledProcessError:
        return []

    fenced: list[str] = []
    for raw_line in proc.stdout.splitlines():
        parsed = _parse_porcelain_status_line(raw_line)
        if parsed is None:
            continue
        _, raw_path = parsed
        path = _normalize_repo_relpath(raw_path)
        if not path or path in commit_bound or _is_transient_status_path(path):
            continue
        fenced.append(path)
    return sorted(set(fenced))


def _canonicalize_stage_path(repo_root: Path, raw_path: str) -> str:
    """Resolve repo-local symlink aliases before passing paths to git add."""
    normalized = _normalize_repo_relpath(raw_path)
    if not normalized:
        return normalized
    if _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return normalized
    try:
        repo_resolved = repo_root.resolve()
        resolved = (repo_root / normalized).resolve(strict=False)
        return resolved.relative_to(repo_resolved).as_posix()
    except (OSError, RuntimeError, ValueError):
        return normalized


def _canonicalize_stage_paths(repo_root: Path, paths: list[str]) -> list[str]:
    return _dedupe_repo_paths([
        _canonicalize_stage_path(repo_root, path)
        for path in paths
        if isinstance(path, str)
    ])


def _path_deleted_in_branch_history(repo_root: Path, relpath: str) -> bool:
    branch_refs: list[str] = []

    upstream = _run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    upstream_ref = upstream.stdout.strip()
    if upstream.returncode == 0 and upstream_ref:
        branch_refs.append(upstream_ref)

    for candidate in ("origin/dev", "dev"):
        if candidate in branch_refs:
            continue
        exists = _run(
            ["git", "rev-parse", "--verify", "--quiet", candidate],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if exists.returncode == 0:
            branch_refs.append(candidate)

    for branch_ref in branch_refs:
        merge_base = _run(
            ["git", "merge-base", branch_ref, "HEAD"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        base_sha = merge_base.stdout.strip()
        if merge_base.returncode != 0 or not base_sha:
            continue

        committed_delete = _run(
            [
                "git", "diff", "--name-only", "--diff-filter=D",
                f"{base_sha}..HEAD", "--", relpath,
            ],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if committed_delete.returncode == 0 and bool(committed_delete.stdout.strip()):
            return True
    return False


def _stage_handoff_paths(
    repo_root: Path,
    *,
    files_to_stage: list[str],
    force_files: list[str],
    scope_files: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    canonical_files = _canonicalize_stage_paths(repo_root, files_to_stage)
    canonical_force = _canonicalize_stage_paths(repo_root, force_files)
    # scope_files bounds branch-rebind context only. Commit staging authority
    # stays with files_to_stage and force_files.
    stage_files = canonical_files
    existing_files: list[str] = []
    missing_files: list[str] = []
    for relpath in stage_files:
        path = repo_root / relpath
        if path.exists() or path.is_symlink():
            existing_files.append(relpath)
        else:
            missing_files.append(relpath)
    if existing_files:
        _run(["git", "add", "--", *existing_files], cwd=repo_root)
    for relpath in missing_files:
        staged_delete = _run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=D", "--", relpath],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if staged_delete.returncode == 0 and staged_delete.stdout.strip():
            continue
        deleted = _run(
            ["git", "ls-files", "--deleted", "--", relpath],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
        if deleted.returncode == 0 and deleted.stdout.strip():
            _run(["git", "add", "-u", "--", relpath], cwd=repo_root)
        else:
            committed_delete = _run(
                [
                    "git", "diff", "--name-only", "--diff-filter=D",
                    "HEAD^..HEAD", "--", relpath,
                ],
                cwd=repo_root,
                check=False,
                timeout=30,
            )
            if committed_delete.returncode == 0 and committed_delete.stdout.strip():
                continue
            if _path_deleted_in_branch_history(repo_root, relpath):
                continue
            _run(["git", "add", "--", relpath], cwd=repo_root)
    if canonical_force:
        _run(["git", "add", "-f", "--", *canonical_force], cwd=repo_root)
    return canonical_files, canonical_force


def _git_index_contains_repo_path(repo_root: Path, relpath: str) -> bool:
    """Return true when relpath is bound to Git's tracked/staged index."""
    normalized = _normalize_repo_relpath(str(relpath or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return False
    try:
        result = _run(
            ["git", "ls-files", "--error-unmatch", "--", normalized],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _git_index_text_for_repo_path(repo_root: Path, relpath: str) -> str | None:
    """Read relpath from Git's index instead of the mutable working tree."""
    normalized = _normalize_repo_relpath(str(relpath or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return None
    if not _git_index_contains_repo_path(repo_root, normalized):
        return None
    try:
        result = _run(
            ["git", "show", f":{normalized}"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git_head_text_for_repo_path(repo_root: Path, relpath: str) -> str | None:
    """Read relpath from HEAD without trusting the mutable working tree."""
    normalized = _normalize_repo_relpath(str(relpath or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return None
    try:
        result = _run(
            ["git", "show", f"HEAD:{normalized}"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _tracked_packet_paths_from_record(record: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    def add_candidate(raw_path: Any) -> None:
        tracked_packet = _normalize_repo_relpath(str(raw_path or ""))
        if not tracked_packet:
            return
        if _is_absolute_untrusted_path(tracked_packet) or _has_path_traversal(tracked_packet):
            return
        if tracked_packet not in paths:
            paths.append(tracked_packet)

    add_candidate(record.get("tracked_packet"))
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return paths
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        add_candidate(candidate.get("tracked_packet"))
    return paths


def _tracked_packet_text_from_record(record: dict[str, Any], repo_root: Path) -> str:
    repo_root_resolved = repo_root.resolve()
    for tracked_packet in _tracked_packet_paths_from_record(record):
        packet_path = (repo_root / tracked_packet).resolve()
        if repo_root_resolved not in packet_path.parents:
            continue
        packet_text = _git_index_text_for_repo_path(repo_root, tracked_packet)
        if packet_text is not None:
            return packet_text
    return ""


def _tracked_packet_path_from_record(record: dict[str, Any]) -> str:
    paths = _tracked_packet_paths_from_record(record)
    return paths[0] if paths else ""


def _discover_staged_same_wave_control_packet(repo_root: Path, wave_id: str) -> str:
    """Find a staged control-plane packet that declares the current wave id."""
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id:
        return ""
    for path in _current_staged_diff_paths(repo_root):
        normalized = _normalize_repo_relpath(path)
        if not normalized.startswith("reports/control_plane/") or not normalized.endswith(".md"):
            continue
        packet_text = _git_index_text_for_repo_path(repo_root, normalized)
        if packet_text and _packet_declares_same_wave_id(packet_text, normalized_wave_id):
            return normalized
    return ""


def _normalize_target_gate_id(value: Any) -> str:
    gate = str(value or "").strip().strip("`.,;")
    return gate if TARGET_GATE_ID_RE.fullmatch(gate) else ""


def _extract_target_gate_id_from_text(text: str) -> str:
    for line in str(text or "").splitlines():
        match = PACKET_TARGET_GATE_RE.match(line)
        if match:
            gate = _normalize_target_gate_id(match.group(1))
            if gate:
                return gate
    return ""


def _normalize_wave_class(value: Any) -> str:
    clean = str(value or "").strip().strip("`.,;")
    normalized = re.sub(r"[\s-]+", "_", clean).upper()
    return normalized if normalized in VALID_WAVE_CLASSES else ""


def _extract_wave_class_from_text(text: str) -> str:
    for line in str(text or "").splitlines():
        match = PACKET_WAVE_CLASS_RE.match(line)
        if match:
            wave_class = _normalize_wave_class(match.group(1))
            if wave_class:
                return wave_class
    return ""


def _resolve_wave_class(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> str:
    for value in (
        (embedded_handoff or {}).get("wave_class"),
        record.get("wave_class"),
    ):
        wave_class = _normalize_wave_class(value)
        if wave_class:
            return wave_class
    wave_class = _extract_wave_class_from_text(_tracked_packet_text_from_record(record, repo_root))
    return wave_class or "MAINTENANCE"


def _resolve_target_gate_id(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> str:
    for value in (
        (embedded_handoff or {}).get("target_gate_id"),
        record.get("target_gate_id"),
    ):
        gate = _normalize_target_gate_id(value)
        if gate:
            return gate
    gate = _extract_target_gate_id_from_text(_tracked_packet_text_from_record(record, repo_root))
    return gate or "G8"


def _extract_founder_override_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> str:
    for key in ("founder_override_token", "founder_override"):
        token = _normalize_founder_override_token(record.get(key))
        if token:
            return token
    for text in [
        str(record.get("tracker_note_text") or ""),
        str((embedded_handoff or {}).get("tracker_note_text") or ""),
        _tracked_packet_text_from_record(record, repo_root),
    ]:
        token = _extract_founder_override_token(text)
        if token:
            return token
    return ""


def _extract_same_wave_founder_override_from_tasks(repo_root: Path, wave_id: str) -> str:
    """Return a same-wave founder override already staged or written in TASKS.md."""
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id:
        return ""

    candidates: list[str] = []
    staged_tasks = _git_index_text_for_repo_path(repo_root, "TASKS.md")
    if staged_tasks is not None:
        candidates.append(staged_tasks)
    try:
        working_tasks = (repo_root / "TASKS.md").read_text(encoding="utf-8")
    except OSError:
        working_tasks = ""
    if working_tasks and working_tasks not in candidates:
        candidates.append(working_tasks)

    for text in candidates:
        for line in text.splitlines():
            token = _extract_founder_override_token(line)
            if token and normalize_wave_id(token) == normalized_wave_id:
                return token
    return ""


def _extract_existing_canonical_tracker_note_from_tasks(
    repo_root: Path,
    wave_id: str,
    *,
    wave_class: str = "",
    target_gate_id: str = "",
) -> str:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.is_file():
        return ""
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return ""
    indices = _matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical = [
        idx
        for idx in indices
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    if len(canonical) != 1:
        return ""
    note = lines[canonical[0]].rstrip("\n")
    if wave_class and target_gate_id:
        validation_errors = _validate_tracker_note_text(
            tracker_note_text=note,
            wave_id=wave_id,
            wave_class=wave_class,
            target_gate_id=target_gate_id,
        )
        if validation_errors:
            return ""
    return note


def _packet_declares_same_wave_id(packet_text: str, normalized_wave_id: str) -> bool:
    """Return true when packet metadata declares exactly normalized_wave_id."""
    if not packet_text or not normalized_wave_id:
        return False
    wave_id_pattern = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:Wave ID|wave_id)(?:\*\*)?\s*:\s*`?([A-Za-z0-9][A-Za-z0-9._-]*)`?",
        re.IGNORECASE,
    )
    for line in packet_text.splitlines():
        match = wave_id_pattern.match(line)
        if not match:
            continue
        if normalize_wave_id(match.group(1)) == normalized_wave_id:
            return True
    return False


_CONTROL_SURFACE_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])control-surface(?![A-Za-z0-9_-])"
)
_NEGATED_CONTROL_SURFACE_RE = re.compile(
    r"(?i)\b(?:anti|no|non|not|without)[-\s]+control-surface\b"
)
_PACKET_LANE_RE = re.compile(
    r"(?i)^\s*(?:[-*]\s*)?(?:\*\*)?Lane(?:\*\*)?\s*:\s*(.+?)\s*$"
)
_PACKET_AUTHORIZATION_RE = re.compile(
    r"(?i)^\s*(?:[-*]\s*)?(?:\*\*)?(?:Founder authorization|Authorization|Authority)"
    r"(?:\*\*)?\s*:\s*(.+?)\s*$"
)
_NEGATED_AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?:authorization\s+(?:is\s+)?(?:denied|not|rejected|revoked)|"
    r"denied|not\s+(?:authorized|approved|granted)|no\s+(?:standing\s+pipeline-bug-fix\s+)?"
    r"authorization|rejected|revoked|without\s+authorization)\b"
)
_STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])standing pipeline-bug-fix authorization(?![A-Za-z0-9_-])"
)
_AUTHORIZED_CONTROL_SURFACE_L4_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])authorized\s+control-surface\s+l4[_ -]?enabler"
    r"(?![A-Za-z0-9_-])"
)


def _packet_declares_positive_control_surface_lane(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        lane_match = _PACKET_LANE_RE.match(line)
        if not lane_match:
            continue
        lane = lane_match.group(1)
        if _NEGATED_CONTROL_SURFACE_RE.search(lane):
            continue
        if _CONTROL_SURFACE_TOKEN_RE.search(lane):
            return True
    return False


def _packet_contains_negative_authorization(packet_text: str) -> bool:
    return any(_NEGATED_AUTHORIZATION_RE.search(line) for line in packet_text.splitlines())


def _packet_declares_explicit_control_surface_l4_authorization(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        if _NEGATED_AUTHORIZATION_RE.search(line):
            continue
        if _AUTHORIZED_CONTROL_SURFACE_L4_RE.search(line):
            return True
    return False


def _packet_declares_positive_standing_authorization(packet_text: str) -> bool:
    for line in packet_text.splitlines():
        if _NEGATED_AUTHORIZATION_RE.search(line):
            continue
        auth_match = _PACKET_AUTHORIZATION_RE.match(line)
        if not auth_match:
            continue
        if _STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE.search(auth_match.group(1)):
            return True
    return False


def _packet_authorizes_control_surface_l4(packet_text: str) -> bool:
    if _packet_contains_negative_authorization(packet_text):
        return False
    if _packet_declares_explicit_control_surface_l4_authorization(packet_text):
        return True
    return (
        _packet_declares_positive_control_surface_lane(packet_text)
        and _packet_declares_positive_standing_authorization(packet_text)
    )


def _control_surface_packet_authorized(
    record: dict[str, Any],
    repo_root: Path,
    *,
    wave_id: str,
) -> bool:
    """Return true only when packet content declares control-surface authority."""
    normalized_wave_id = normalize_wave_id(wave_id or str(record.get("wave_name") or record.get("wave_id") or ""))
    if not normalized_wave_id:
        return False
    repo_resolved = repo_root.resolve()
    for tracked_packet in _tracked_packet_paths_from_record(record):
        if not tracked_packet.startswith("reports/control_plane/"):
            continue
        packet_path = (repo_root / tracked_packet).resolve()
        if repo_resolved not in packet_path.parents:
            continue
        packet_text = _git_index_text_for_repo_path(repo_root, tracked_packet)
        if packet_text is None:
            continue
        if not _packet_declares_same_wave_id(packet_text, normalized_wave_id):
            continue
        if _packet_authorizes_control_surface_l4(packet_text):
            return True
    return False


def _is_authorized_control_surface_l4_enabler(
    record: dict[str, Any],
    *,
    embedded_handoff: dict[str, Any] | None,
    wave_id: str,
    wave_class: str,
    repo_root: Path,
) -> bool:
    if str(wave_class or "").strip() != "L4_ENABLER":
        return False
    _ = embedded_handoff
    return _control_surface_packet_authorized(record, repo_root, wave_id=str(wave_id or ""))


def _resolve_control_surface_founder_override_token(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
    wave_id: str,
    wave_class: str,
) -> str:
    if not _wave_class_allows_founder_override(wave_class):
        return ""
    text_candidates = [
        str(record.get("founder_override_token") or ""),
        str(record.get("founder_override") or ""),
        str(record.get("tracker_note_text") or ""),
        str((embedded_handoff or {}).get("tracker_note_text") or ""),
        _tracked_packet_text_from_record(record, repo_root),
    ]
    for text in text_candidates:
        token = _extract_same_wave_founder_override_token(text, wave_id)
        if token:
            return token
    if _is_authorized_control_surface_l4_enabler(
        record,
        embedded_handoff=embedded_handoff,
        wave_id=wave_id,
        wave_class=wave_class,
        repo_root=repo_root,
    ):
        return normalize_wave_id(wave_id)
    token = _extract_founder_override_from_routing_record(
        record,
        repo_root,
        embedded_handoff=embedded_handoff,
    )
    if token and normalize_wave_id(token) == normalize_wave_id(wave_id):
        return token
    return ""


def _missing_founder_override_error(wave_id: str) -> str:
    return (
        "Missing FOUNDER_OVERRIDE token for standalone L4_ENABLER commit handoff "
        f"before supervisor Step 6 (wave_id={wave_id}). Expected source: "
        "routing_record.tracker_note_text, embedded handoff tracker_note_text, "
        "tracked packet text, or authorized reports/control_plane packet text "
        "declaring same-wave control-surface authorization that permits deriving "
        "FOUNDER_OVERRIDE:<wave_id>."
    )


def _resolve_standalone_founder_override_token(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None,
    wave_id: str,
    wave_class: str,
) -> tuple[str, str | None]:
    token = _resolve_control_surface_founder_override_token(
        record,
        repo_root,
        embedded_handoff=embedded_handoff,
        wave_id=wave_id,
        wave_class=wave_class,
    )
    if token:
        return token, None
    token = _extract_same_wave_founder_override_from_tasks(repo_root, wave_id)
    if token and _wave_class_allows_founder_override(wave_class):
        return token, None
    if str(wave_class or "").strip() == "L4_ENABLER":
        return "", _missing_founder_override_error(wave_id)
    return "", None


def _extract_maintenance_bypass_from_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    *,
    embedded_handoff: dict[str, Any] | None = None,
) -> tuple[str, str]:
    unblocks_wave_id = str(record.get("unblocks_wave_id") or "").strip().strip("`").rstrip(".,;")
    unblocks_runtime_blocker = (
        str(record.get("unblocks_runtime_blocker") or "").strip().strip("`").rstrip(".,;")
    )
    for text in [
        str(record.get("tracker_note_text") or ""),
        str((embedded_handoff or {}).get("tracker_note_text") or ""),
        _tracked_packet_text_from_record(record, repo_root),
    ]:
        extracted_wave_id, extracted_runtime_blocker = _extract_maintenance_bypass_fields_from_text(text)
        if extracted_wave_id and not unblocks_wave_id:
            unblocks_wave_id = extracted_wave_id
        if extracted_runtime_blocker and not unblocks_runtime_blocker:
            unblocks_runtime_blocker = extracted_runtime_blocker
        if unblocks_wave_id and unblocks_runtime_blocker:
            break
    return unblocks_wave_id, unblocks_runtime_blocker


def _summarize_path_preview(paths: list[str]) -> str:
    preview = ", ".join(paths[:3])
    remainder = len(paths) - min(len(paths), 3)
    if remainder > 0:
        preview = f"{preview}, +{remainder} more"
    return preview


def _build_standalone_staged_diff_fixes(paths: list[str]) -> list[str]:
    preview = _summarize_path_preview(paths)
    return [f"Resume standalone continuation for current staged diff: {preview}."]


def _build_standalone_commit_message(wave_id: str) -> str:
    return f"chore: continue {wave_id} staged diff"


def _is_wave_bound_target_branch(
    target_branch: str,
    *,
    branch_prefix: str,
    wave_id: str,
) -> bool:
    """Allow only the canonical wave branch or its restart descendants."""
    if not target_branch or not branch_prefix or not wave_id:
        return False
    prefix = f"{branch_prefix}/"
    if not target_branch.startswith(prefix):
        return False
    suffix = target_branch[len(prefix):]
    if not TARGET_BRANCH_SUFFIX_RE.fullmatch(suffix):
        return False
    return (
        suffix == wave_id
        or suffix == f"{wave_id}-restart"
        or suffix.startswith(f"{wave_id}-restart-")
    )


def _is_authorized_control_surface_repair_target_branch(
    handoff: dict[str, Any],
    repo_root: Path | None,
    target_branch: str,
    *,
    branch_prefix: str,
    wave_id: str,
) -> bool:
    """Allow standalone repair waves to land on an existing PR branch.

    This is intentionally narrower than generic target-branch override support:
    only standalone or Phase B L4_ENABLER handoffs with an indexed same-wave
    control-plane packet that declares control-surface authorization may target a
    non-wave branch under the caller's branch prefix.
    """
    if handoff.get("caller") not in {"standalone", "phase_b"}:
        return False
    if str(handoff.get("wave_class") or "").strip() != "L4_ENABLER":
        return False
    if repo_root is None:
        return False
    if not target_branch or not branch_prefix or not wave_id:
        return False
    prefix = f"{branch_prefix}/"
    if not target_branch.startswith(prefix):
        return False
    suffix = target_branch[len(prefix):]
    if not TARGET_BRANCH_SUFFIX_RE.fullmatch(suffix):
        return False
    return _control_surface_packet_authorized(
        {
            "wave_id": wave_id,
            "wave_name": wave_id,
            "tracked_packet": handoff.get("tracked_packet", ""),
            "tracker_note_text": handoff.get("tracker_note_text", ""),
        },
        repo_root,
        wave_id=wave_id,
    )


def _handoff_plan_path(handoff: dict[str, Any]) -> str | None:
    tracked_packet = handoff.get("tracked_packet")
    if isinstance(tracked_packet, str) and tracked_packet.strip():
        return _normalize_repo_relpath(tracked_packet)
    scope_items = handoff.get("scope_items")
    if not isinstance(scope_items, list):
        return None
    for item in scope_items:
        text = str(item or "").strip()
        if text.endswith(".md"):
            return text
    return None


def _path_field_error(field_name: str, path: str) -> str | None:
    if not path:
        return f"{field_name} is required"
    if _is_absolute_untrusted_path(path):
        return f"{field_name} must be repo-relative: {path}"
    if _has_path_traversal(path):
        return f"Path traversal in {field_name}: {path}"
    return None


def _commit_refresh_packet_path(handoff: dict[str, Any]) -> tuple[str, str | None]:
    """Resolve the builder-owned control-plane packet path from the canonical handoff."""
    tracked_packet = handoff.get("tracked_packet")
    if tracked_packet is not None:
        if not isinstance(tracked_packet, str) or not tracked_packet.strip():
            return "", "tracked_packet must be a non-empty string when provided"
        packet = _normalize_repo_relpath(tracked_packet)
        error = _path_field_error("tracked_packet", packet)
        if error:
            return "", error
        if not packet.startswith("reports/control_plane/") or not packet.endswith(".md"):
            return "", f"tracked_packet must name a reports/control_plane/*.md packet: {packet}"
        return packet, None

    return "", None


def _tracker_marker_value(
    note: str,
    marker: str,
    *,
    marker_names: "tuple[str, ...] | list[str] | None" = None,
) -> str:
    # Default boundary set kept byte-for-byte: every existing caller (incl. the
    # fail-closed evidence_command path and the byte-identical meta_bridge_supervisor
    # parity contract) passes no marker_names and gets exactly this list. A caller
    # may pass a wider boundary set (see _BUILDER_TRACKER_MARKER_NAMES) to stop a
    # value at builder fields absent from this default list.
    if marker_names is None:
        marker_names = [
            "Class",
            "target_gate_id",
            "no_op_proof",
            "defer_reason_code",
            "evidence_command",
            "evidence_delta",
            "progress_proof_before",
            "progress_proof_after",
            "primary_blocker_class",
            "primary_invariant_id",
            "indicator_artifact_ref",
            "indicator_collection_command",
            "bootstrap_endgame_policy",
            "boot0_track_id",
            "boot0_progress_state",
            "FOUNDER_OVERRIDE",
            "unblocks_wave_id",
            "unblocks_runtime_blocker",
        ]
    pattern = re.compile(
        rf"(?:^|\s){re.escape(marker)}:\s*"
    )
    text = note or ""
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    in_inline_code = False
    for idx in range(start, len(text)):
        if text[idx] == "`":
            in_inline_code = not in_inline_code
            continue
        if in_inline_code or not text[idx].isspace():
            continue
        marker_start = idx + 1
        if any(
            text.startswith(f"{name}:", marker_start)
            for name in marker_names
            if name != marker
        ):
            return text[start:idx].strip().rstrip()
    return text[start:].strip().rstrip()


# Fail-closed sentinel for a NON-canonical (un-backtick-wrapped) evidence_command.
# The canonical tracker-note builder (tracker_sync_note.render_tracker_sync_note)
# ALWAYS backtick-wraps the evidence_command value, so an un-wrapped value is
# non-canonical. There is no reliable text-only way to tell an embedded
# ". marker:" inside a shell command from a real next-field boundary, so rather
# than silently truncating an un-wrapped value at that substring and running a
# passing prefix (a fail-OPEN), the extractor returns this always-failing command.
# The #52 pre-commit supervisor RUNS the extracted evidence_command and gates on
# exit==0, so an always-failing command forces the wave_evidence gate to FAIL ->
# NEEDS_PHASE_B (fail-CLOSED). A plain empty value is NOT sufficient: the supervisor
# skips the wave_evidence gate entirely when BOTH the declared and transported
# evidence_command are empty, which would re-open the hole. Kept byte-identical with
# the meta_bridge_supervisor copy.
_NONCANONICAL_EVIDENCE_COMMAND = (
    "echo 'rcx: un-backtick-wrapped evidence_command is non-canonical and is "
    "rejected fail-closed (backtick-wrap the value in the tracker note)' >&2; exit 1"
)


def _strip_tracker_inline_code(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("`") and text.endswith("`."):
        return text[1:-2].strip()
    if text.startswith("`") and text.endswith("`"):
        return text[1:-1].strip()
    # An empty value means the evidence_command marker was absent: stay empty so
    # the supervisor's "no evidence declared" path is preserved. A NON-empty value
    # that is NOT backtick-wrapped is a non-canonical evidence_command: fail closed
    # (return _NONCANONICAL_EVIDENCE_COMMAND) instead of returning a truncated /
    # un-wrapped value the supervisor would run as a passing prefix.
    if not text:
        return ""
    return _NONCANONICAL_EVIDENCE_COMMAND


def _tracker_evidence_command_value(note: str) -> str:
    return _strip_tracker_inline_code(_tracker_marker_value(note, "evidence_command"))


# Public test seam. Tracker-note evidence_command extraction is a tested contract
# shared with meta_bridge_supervisor: the #52 pre-commit supervisor RUNS the
# extracted evidence_command, so its fail-closed behavior on a non-canonical
# (un-backtick-wrapped) value is regression-pinned by
# mu/tests/tools/test_tracker_marker_codespan_extraction.py. These public names
# delegate to the canonical underscore-prefixed implementations above so the suite
# can exercise the contract without reaching into a module-private helper (the
# test-integrity gate forbids private-attr access in tests).
NONCANONICAL_EVIDENCE_COMMAND = _NONCANONICAL_EVIDENCE_COMMAND


def tracker_marker_value(
    note: str,
    marker: str,
    *,
    marker_names: "tuple[str, ...] | list[str] | None" = None,
) -> str:
    """Public seam over :func:`_tracker_marker_value`.

    ``marker_names`` defaults to None (the canonical boundary set); pass a wider
    set to stop a value at builder fields the default list omits.
    """
    return _tracker_marker_value(note, marker, marker_names=marker_names)


def tracker_evidence_command_value(note: str) -> str:
    """Public seam over :func:`_tracker_evidence_command_value`."""
    return _tracker_evidence_command_value(note)


# --- Single-source L4-field derivation from the canonical tracker note --------
#
# A control-plane packet's L4-field block AUTO-DERIVES from the wave's TASKS.md
# tracker note so the packet can never declare an L4 value that diverges from the
# note. The pre-commit supervisor + bot read the TRACKER NOTE as the source of
# truth, so a packet/note mismatch costs a DOC_ACCURACY / NEEDS_PHASE_B round.
# Rendering the block straight from the shared tracker-note marker extractor makes
# "note wins" deterministic: the block is a pure function of the note text, so no
# independently-supplied value can survive. The renderer lives here -- the module
# that owns the extractors -- and is called from BOTH render points
# (phase_a_executor at draft time, refresh_commit_path_packet_truth at commit time)
# so the two paths emit an identical block. Derivation passes the COMPLETE builder
# marker set (_BUILDER_TRACKER_MARKER_NAMES) so a value stops at the next builder
# field even when that field is absent from the default boundary list (the default
# 2-arg extractor over-captures `target_gate_id` past the un-listed `Packet:`).
#
# The field set mirrors tracker_sync_note.TrackerSyncNoteFields exactly -- no more,
# no less. Each entry maps a packet label to the marker name the canonical builder
# (tracker_sync_note.render_tracker_sync_note) emits into the note; founder_override
# is emitted as the bare "FOUNDER_OVERRIDE" marker, hence the label/marker split.
L4_FIELDS_FROM_TRACKER_START = "<!-- L4_FIELDS_FROM_TRACKER:start -->"
L4_FIELDS_FROM_TRACKER_END = "<!-- L4_FIELDS_FROM_TRACKER:end -->"

_L4_FIELDS_FROM_TRACKER: tuple[tuple[str, str], ...] = (
    ("primary_blocker_class", "primary_blocker_class"),
    ("primary_invariant_id", "primary_invariant_id"),
    ("indicator_artifact_ref", "indicator_artifact_ref"),
    ("indicator_collection_command", "indicator_collection_command"),
    ("target_gate_id", "target_gate_id"),
    ("evidence_command", "evidence_command"),
    ("evidence_delta", "evidence_delta"),
    ("bootstrap_endgame_policy", "bootstrap_endgame_policy"),
    ("boot0_track_id", "boot0_track_id"),
    ("boot0_progress_state", "boot0_progress_state"),
    ("founder_override", "FOUNDER_OVERRIDE"),
)


def _validate_l4_field_labels() -> None:
    """Fail closed if a packet label is not a real TrackerSyncNoteFields field.

    Reuses tracker_sync_note.TrackerSyncNoteFields as the single definition of
    WHICH L4-fields exist, so a rename there cannot silently drift this mapping.
    No-op when tracker_sync_note is unavailable (commit_executor already degrades
    gracefully when that optional import fails).
    """
    if _tracker_sync_note is None:
        return
    valid = set(
        getattr(_tracker_sync_note.TrackerSyncNoteFields, "__dataclass_fields__", {})
    )
    if not valid:
        return
    unknown = sorted(
        label for label, _marker in _L4_FIELDS_FROM_TRACKER if label not in valid
    )
    if unknown:
        raise RuntimeError(
            "L4-field labels absent from tracker_sync_note.TrackerSyncNoteFields: "
            + ", ".join(unknown)
        )


_validate_l4_field_labels()


# Marker spellings that are authorization TOKENS, not field declarations. The
# founder_override field's marker slot holds the uppercase same-wave override token
# ``FOUNDER_OVERRIDE:<wave_id>`` -- a distinct entity commit automation reads to derive
# the override, which the tracker note does NOT govern (the note's optional
# founder_override value, when present, fills the lowercase field DECLARATION). When the
# note OMITS a field, conform-to-absence clears the field-declaration spelling (the
# lowercase label) but MUST preserve these token spellings, so a packet's canonical
# ``FOUNDER_OVERRIDE:<wave_id>`` survives a note that carries no override. Derived
# structurally as the markers whose spelling differs from the field label, so a future
# label/marker split is classified automatically rather than by a hardcoded name.
_L4_AUTH_TOKEN_MARKERS: frozenset[str] = frozenset(
    marker for label, marker in _L4_FIELDS_FROM_TRACKER if marker != label
)


# Complete set of markers the canonical tracker-note builder
# (tracker_sync_note.render_tracker_sync_note) can emit. Used as the boundary set
# when DERIVING the packet L4-field block so a value stops at the NEXT builder
# field even when that field is absent from the default extractor list. Concretely:
# render_tracker_sync_note emits `Packet:` immediately after `target_gate_id:` in
# every packet-bearing note, and `Packet` is not in the default boundary list, so
# the default extractor over-captures the packet path into target_gate_id; this
# superset stops it at `Packet:`. A superset only TIGHTENS boundaries for canonical
# builder output -- every field still ends at the first following builder marker.
_BUILDER_TRACKER_MARKER_NAMES: tuple[str, ...] = (
    "Class",
    "contract_path",
    "target_gate_id",
    "Packet",
    "workload_target",
    "host_semantics_delta_before",
    "host_semantics_delta_after",
    "structural_artifact_ref",
    "no_op_proof",
    "defer_reason_code",
    "evidence_command",
    "evidence_delta",
    "progress_proof_before",
    "progress_proof_after",
    "post_gate_contract_sweep",
    "FOUNDER_OVERRIDE",
    "unblocks_wave_id",
    "unblocks_runtime_blocker",
    "primary_blocker_class",
    "primary_invariant_id",
    "indicator_artifact_ref",
    "indicator_collection_command",
    "bootstrap_endgame_policy",
    "boot0_track_id",
    "boot0_progress_state",
)


def derive_l4_fields_from_tracker_note(tracker_note_text: str) -> dict[str, str]:
    """Parse the packet L4-field set from the canonical tracker note (single source).

    Each value is the output of the shared tracker-note marker extractor (the public
    :func:`tracker_marker_value` seam) bounded by the COMPLETE builder marker set, so
    a field the note does not declare yields "" and a field followed by a builder
    marker absent from the default list (e.g. target_gate_id -> `Packet:`) is NOT
    over-captured. Returns one entry per label in ``_L4_FIELDS_FROM_TRACKER`` in
    stable order -- no more, no less than the field set.
    """
    note = str(tracker_note_text or "")
    return {
        label: tracker_marker_value(note, marker, marker_names=_BUILDER_TRACKER_MARKER_NAMES)
        for label, marker in _L4_FIELDS_FROM_TRACKER
    }


def render_l4_fields_block_from_tracker_note(tracker_note_text: str) -> str:
    """Render the machine-owned, note-derived L4-field block for a control packet."""
    fields = derive_l4_fields_from_tracker_note(tracker_note_text)
    lines = [
        L4_FIELDS_FROM_TRACKER_START,
        "**L4 fields (auto-derived from the canonical TASKS.md tracker note -- "
        "single source of truth; do not hand-edit):**",
        "",
    ]
    for label, _marker in _L4_FIELDS_FROM_TRACKER:
        value = fields[label]
        lines.append(f"- `{label}`: {value}" if value else f"- `{label}`:")
    lines.append(L4_FIELDS_FROM_TRACKER_END)
    return "\n".join(lines) + "\n"


def _find_block_marker_line(text: str, marker: str, *, search_from: int = 0) -> int:
    """Return the offset of ``marker`` standing alone on its own line, or -1.

    A control packet may MENTION a block marker inline in prose -- e.g. a meta-packet
    documenting the machine-owned ``L4_FIELDS_FROM_TRACKER`` block quotes the start/end
    delimiters in a backtick-wrapped sentence, so the marker text appears more than
    once. Only the occurrence that owns its WHOLE line delimits the real machine block
    (:func:`render_l4_fields_block_from_tracker_note` always emits the start/end markers
    on their own lines). A raw :meth:`str.find` binds to the FIRST occurrence, so an
    earlier inline prose mention is mistaken for the block boundary; this returns the
    first occurrence at or after ``search_from`` whose line holds only the marker
    (whitespace before and after on the line is allowed; non-whitespace -- a backtick or
    a word -- means it is an inline mention, not a delimiter). For a packet whose only
    occurrence IS the own-line block marker the result equals :meth:`str.find`, so the
    behavior changes only for packets that ALSO mention the marker inline.
    """
    idx = text.find(marker, search_from)
    while idx != -1:
        line_start = text.rfind("\n", 0, idx) + 1  # 0 when no preceding newline
        after = idx + len(marker)
        next_nl = text.find("\n", after)
        line_end = next_nl if next_nl != -1 else len(text)
        if text[line_start:idx].strip() == "" and text[after:line_end].strip() == "":
            return idx
        idx = text.find(marker, idx + 1)
    return -1


def _replace_l4_fields_block(packet_text: str, block: str) -> str:
    """Insert or replace the marker-delimited L4-field block (idempotent).

    The markers are located by :func:`_find_block_marker_line` so a packet that also
    quotes the marker text inline in prose cannot bind the replacement to that prose
    mention -- only the markers standing alone on their own lines delimit the block.
    """
    start = _find_block_marker_line(packet_text, L4_FIELDS_FROM_TRACKER_START)
    end = _find_block_marker_line(
        packet_text,
        L4_FIELDS_FROM_TRACKER_END,
        search_from=start + 1 if start != -1 else 0,
    )
    if start != -1 and end != -1 and end > start:
        end += len(L4_FIELDS_FROM_TRACKER_END)
        trailing_newline = (
            "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        )
        return (
            packet_text[:start].rstrip()
            + "\n\n"
            + block.rstrip()
            + trailing_newline
            + packet_text[end:]
        )
    if start != -1 or end != -1:
        raise ValueError("existing L4_FIELDS_FROM_TRACKER markers are unbalanced")
    return packet_text.rstrip() + "\n\n" + block


def _clean_l4_body_value(value: str) -> str:
    """Normalize a note-derived L4 value for an inline-code body declaration.

    The tracker-note extractor returns each value carrying the note's trailing
    sentence period (e.g. ``INTEGRATION.``) and, for the backtick-wrapped markers
    (evidence_command / post_gate_contract_sweep), the note's surrounding backticks
    (e.g. ```<cmd>`.``). Strip both so the value drops into a packet's
    backtick-delimited declaration without a nested backtick or a doubled period.
    """
    text = str(value or "").strip()
    if text.startswith("`") and text.endswith("`."):
        text = text[1:-2].strip()
    elif text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    if text.endswith("."):
        text = text[:-1].rstrip()
    return text


def clean_l4_body_value(value: str) -> str:
    """Public seam over :func:`_clean_l4_body_value`.

    The packet-L4 regression in ``mu/tests/tools/test_phase_a_executor.py`` asserts
    the cleaned, body-declaration form of each note-derived value (the form the
    out-of-block conformer writes), so the suite needs this normalization without
    reaching into a module-private helper -- the test-integrity gate
    (``tools/checks/linters/check_private_attr_access.py``) forbids private-attr
    access in tests. Delegates to the canonical underscore-prefixed implementation
    above; this is the only normalization contract, so the seam stays a pure pass-through.
    """
    return _clean_l4_body_value(value)


def _conform_l4_decl_in_text(text: str, field_token: str, clean_value: str) -> str:
    """Rewrite backtick-delimited ``field_token`` declarations to ``clean_value``.

    Two canonical packet authoring forms carry an L4 field's value inside an
    inline-code span, so the value extent is unambiguous and the rewrite is safe:
    ```field: VALUE``` (field and value share one span) and
    ```field`: `VALUE``` (separate spans). Both are rewritten to
    the note-derived value; the value's closing backtick bounds the replacement, so a
    prose mention of the field name (not in declaration form) is never touched, and
    the original colon spacing is preserved so a no-space token (``FOUNDER_OVERRIDE:``)
    keeps its shape. The machine-owned block uses ```field`: VALUE`` (plain,
    unwrapped value), which neither form matches -- and the block region is sliced out
    before this runs anyway -- so the derived block is never altered here.
    """
    escaped = re.escape(field_token)
    # Form A: `field: VALUE`
    text = re.sub(
        rf"`{escaped}:(\s*)[^`\n]*`",
        lambda m: f"`{field_token}:{m.group(1)}{clean_value}`",
        text,
    )
    # Form B: `field`: `VALUE`
    text = re.sub(
        rf"`{escaped}`:(\s*)`[^`\n]*`",
        lambda m: f"`{field_token}`:{m.group(1)}`{clean_value}`",
        text,
    )
    return text


def _clear_l4_decl_in_text(text: str, field_token: str) -> str:
    """Clear a stale inline-code declaration of ``field_token`` to the bare-colon form.

    Conform-to-absence counterpart of :func:`_conform_l4_decl_in_text` for a field the
    note OMITS. The two canonical inline-code declaration forms lose their value,
    collapsing to the machine block's bare ``- `field`:`` shape (the key is kept, no
    value, no trailing whitespace): ```field: VALUE``` becomes ```field:``` and
    ```field`: `VALUE``` becomes ```field`:```. So a stale out-of-block value cannot
    outlive the note's omission. Only the lowercase field-DECLARATION spelling is ever
    passed here; the uppercase authorization-token marker (``FOUNDER_OVERRIDE:<wave_id>``)
    is never cleared -- the case-sensitive token bounds the match, so a no-space token
    spelling is left untouched. A span already at the bare-colon form is matched and
    re-emitted unchanged, so a second pass is a no-op.
    """
    escaped = re.escape(field_token)
    # Form A: `field: VALUE` -> `field:`
    text = re.sub(rf"`{escaped}:[ \t]*[^`\n]*`", f"`{field_token}:`", text)
    # Form B: `field`: `VALUE` -> `field`:
    text = re.sub(rf"`{escaped}`:[ \t]*`[^`\n]*`", f"`{field_token}`:", text)
    return text


# Substitution counterpart of PACKET_TARGET_GATE_RE (the extractor at module top).
# A packet may declare the gate as a plain-text header LINE -- "Target gate: G8",
# "Target Gate: G8", or "target_gate_id: G8", each with an optional list-marker/bold
# prefix and an optional backtick-wrapped value -- rather than as an inline-code
# span. _conform_l4_decl_in_text only rewrites inline-code spans, so on its own it
# lets a divergent plain header survive the refresh (bridge round 3 NO_GO: a packet's
# "Target gate: G3" header outlived a G8 tracker note while the backtick form
# conformed). target_gate_id is the one L4-block field with such a dedicated
# plain-header extractor, so its header is a real, tooling-read drift vector. Group 1
# captures the label + colon + spacing + optional opening backtick; group 2 the
# optional closing backtick -- both preserved so only the single safe gate token is
# rewritten. The within-line whitespace uses [ \t] (never a newline) so the rewrite
# is strictly line-local, and the recognized forms are exactly those the extractor
# reads, keeping "what the tooling parses as the gate" and "what the refresh
# conforms" the same set; a mid-line backtick declaration and prose are never matched.
_PACKET_TARGET_GATE_HEADER_SUB_RE = re.compile(
    r"^([ \t]*(?:[-*][ \t]*)?(?:\*\*)?"
    r"(?:Target Gate|Target gate|target_gate_id)"
    r"(?:\*\*)?[ \t]*:[ \t]*`?)"
    r"[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(`?)",
    re.IGNORECASE | re.MULTILINE,
)


def _conform_target_gate_header_in_text(text: str, clean_gate: str) -> str:
    """Rewrite plain-text ``Target gate:``/``target_gate_id:`` header lines to ``clean_gate``.

    The inline-code conformer (:func:`_conform_l4_decl_in_text`) only rewrites
    backtick spans; the gate additionally appears as a plain-text packet header that
    PACKET_TARGET_GATE_RE / :func:`_extract_target_gate_id_from_text` read as the
    declared gate, so a divergent header is a drift vector it cannot reach. Only the
    gate token is replaced; the label, colon spacing, and any backticks are kept.
    """
    return _PACKET_TARGET_GATE_HEADER_SUB_RE.sub(
        lambda m: f"{m.group(1)}{clean_gate}{m.group(2)}",
        text,
    )


# --- Plain / bold list-item L4 declarations (the most common packet form) ------
#
# Bridge round 4 DEFECT: the inline-code conformer (_conform_l4_decl_in_text) only
# rewrites declarations whose value is wrapped in a backtick span; the plain-text
# packet authoring forms survived. Control packets overwhelmingly declare L4 fields
# as plain or bold list items, e.g. `- primary_blocker_class: INTEGRATION`,
# `- **target_gate_id:** G8`, `- indicator_artifact_ref: reports/...json` (a plain
# value containing periods), `- evidence_command: \`...\`.` (plain label, backtick
# value), and the compact multi-field line
# `- bootstrap_endgame_policy: X. boot0_track_id: Y. boot0_progress_state: Z.`. Every
# such out-of-block declaration is a drift vector the supervisor/bot read, so each is
# conformed to the note value here. Detection is anchored to a LINE that *begins*
# (after indent + optional list marker) with an L4 field token, so a prose mention of
# a field name mid-sentence is never rewritten; on such a line, every grouped field
# (separated by `. `/`; `) is conformed, and a token inside a backtick span is treated
# as value text, not a key. The block region is sliced out before this runs, so the
# machine-owned block (which uses a backtick-wrapped label `- \`field\`: value`, never
# a plain label) is never matched here either.
_PLAIN_L4_TOKENS: tuple[str, ...] = tuple(
    sorted({tok for pair in _L4_FIELDS_FROM_TRACKER for tok in pair}, key=len, reverse=True)
)
_PLAIN_L4_TOKEN_ALT = "|".join(re.escape(tok) for tok in _PLAIN_L4_TOKENS)
# One L4 field declaration "key": an optional bold-open, the field token, an optional
# bold-close, the colon, and an optional bold-close after the colon -- covering plain
# (`field:`), `**field:**`, and `**field**:`. The value follows the match end.
_PLAIN_L4_KEY_RE = re.compile(
    rf"(?:\*\*)?(?P<field>{_PLAIN_L4_TOKEN_ALT})(?:\*\*)?[ \t]*:(?:\*\*)?"
)
# A qualifying line carries only indent + an optional list marker before its first
# key; this is what distinguishes a declaration list item from a prose line that
# merely mentions a field name. A mid-word false token match (e.g. `xtarget_gate_id:`)
# leaves a non-empty, non-marker prefix and so fails this guard.
_PLAIN_L4_LEAD_PREFIX_RE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?$")
# Grouping separators that introduce a *subsequent* field on the same line. The
# compact multi-field authoring forms always separate with a sentence period or a
# semicolon (optionally after a backtick-closed value), so a following key is only
# accepted when the text immediately before it ends with one of these; a bare word
# before a `token:` is prose and is left intact.
_PLAIN_L4_GROUP_BOUNDARY_CHARS = (".", ";", ",", "`")


def _backtick_spans(line: str) -> list[tuple[int, int]]:
    """Return (open, close) index pairs for the inline-code spans on a single line."""
    ticks = [i for i, ch in enumerate(line) if ch == "`"]
    return [(ticks[j], ticks[j + 1]) for j in range(0, len(ticks) - 1, 2)]


def _pos_in_backtick_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(open_i < pos < close_i for open_i, close_i in spans)


def _build_clean_l4_lookup(
    note_values: dict[str, str],
    *,
    exact_evidence_command: str | None = None,
) -> dict[str, str]:
    """Map every field token (label AND marker form) to its cleaned note value."""
    lookup: dict[str, str] = {}
    for label, marker in _L4_FIELDS_FROM_TRACKER:
        clean = (
            exact_evidence_command
            if label == "evidence_command" and exact_evidence_command is not None
            else _clean_l4_body_value(note_values.get(label, ""))
        )
        lookup[label] = clean
        lookup[marker] = clean
    return lookup


def _rewrite_plain_l4_value_region(
    raw: str, clean_value: str, *, clear_on_absence: bool = True,
) -> str:
    """Rewrite one plain/backtick value region to ``clean_value`` (decoration kept).

    ``raw`` is the text from just after a field's colon to the start of the next
    field on the line (or end of line). The colon spacing, a backtick wrapper, and a
    trailing separator/sentence punctuation are preserved; only the value core is
    replaced.

    When ``clean_value`` is empty the note OMITS this field, so a value the packet
    still declares out of block is stale drift relative to the single-source note and
    is CLEARED (conform-to-absence): the value collapses to the bare colon
    (``founder_override:``), mirroring how the machine-owned block renders an omitted
    field as ``- `field`:``. A region that is already empty (the packet declared the
    field with no value) is returned unchanged, so a second pass is a no-op. The
    grouped case -- a note-omitted field FOLLOWED by another L4 field on the same line
    -- is handled by the caller, NOT here: a bare value region still owns the grouping
    separator that introduces the next field, so collapsing it to the bare colon would
    leave a ``field:.`` punctuation residue (the orphaned separator). The caller drops
    that whole stale declaration instead, so this clear path is only ever reached for a
    last/standalone omitted field.

    ``clear_on_absence`` is False when the matched token is an authorization-token
    marker (``FOUNDER_OVERRIDE:<wave_id>``): the note does not govern it, so its
    omission must not blank the value -- the region is left exactly as authored.
    """
    if not clean_value:
        if not clear_on_absence:
            return raw  # authorization-token marker: note omission must not blank it
        if raw.strip() == "":
            return raw  # nothing declared to clear (idempotent no-op)
        return ""  # last/standalone omitted field: collapse to the bare colon
    lead_ws = re.match(r"[ \t]*", raw).group(0)
    rest = raw[len(lead_ws):]
    if rest.strip() == "":
        return raw
    if rest.startswith("`"):
        close = rest.find("`", 1)
        if close == -1:
            return raw  # malformed inline-code span: leave as authored
        trailing = rest[close + 1:]
        return f"{lead_ws}`{clean_value}`{trailing}"
    trailing_match = re.search(r"[ \t]*[.;,]?[ \t]*$", rest)
    trailing = trailing_match.group(0) if trailing_match else ""
    return f"{lead_ws}{clean_value}{trailing}"


def _conform_plain_l4_list_item_line(line: str, clean_lookup: dict[str, str]) -> str:
    """Conform plain/bold L4 declarations on a single qualifying list-item line.

    Returns ``line`` unchanged unless it begins (after indent + optional list marker)
    with an L4 field token. On a qualifying line, the leading field and every grouped
    field after a `. `/`; ` separator are rewritten to their note values; a token
    inside a backtick span, or one not at a grouping separator, is treated as value
    text rather than a key. A field the note OMITS is conformed to absence: a
    last/standalone declaration collapses to a bare ``field:``; a declaration FOLLOWED
    by another grouped L4 field is dropped whole (key + value + its grouping separator)
    so the line collapses to the surviving fields with no ``field:.`` residue and the
    next field stays a detected, conformable declaration. An authorization-token marker
    (``FOUNDER_OVERRIDE:<wave_id>`` in :data:`_L4_AUTH_TOKEN_MARKERS`), which the note
    does not govern, is left exactly as authored either way.
    """
    accepted = _plain_l4_declaration_matches(line)
    if not accepted:
        return line

    out = [line[:accepted[0].start()]]
    for i, key in enumerate(accepted):
        followed_by_field = i + 1 < len(accepted)
        value_end = accepted[i + 1].start() if followed_by_field else len(line)
        field = key.group("field")
        clean_value = clean_lookup.get(field, "")
        clearable = field not in _L4_AUTH_TOKEN_MARKERS
        if followed_by_field and clearable and not clean_value:
            # The note OMITS this field and another grouped L4 field follows on the
            # same line. Drop the whole stale declaration -- the key, its value, AND
            # the grouping separator that introduced the next field (all of which live
            # in ``line[key.start():value_end]``). The line collapses to the surviving
            # fields, so there is no orphaned ``field:.`` punctuation residue, and the
            # next field stays a detected, conformable declaration (its own preceding
            # separator, if any, is the prior field's and is untouched). Collapsing to a
            # bare ``field:`` here instead would strand that separator as residue, which
            # is why this case cannot be handled inside _rewrite_plain_l4_value_region.
            # A last/standalone omitted field keeps a bare ``field:`` (below); an
            # authorization-token marker is never clearable, so it is never dropped.
            continue
        out.append(line[key.start():key.end()])
        out.append(
            _rewrite_plain_l4_value_region(
                line[key.end():value_end],
                clean_value,
                clear_on_absence=clearable,
            )
        )
    return "".join(out)


def _conform_out_of_block_l4_decls(
    packet_text: str,
    note_values: dict[str, str],
    *,
    exact_evidence_command: str | None = None,
) -> str:
    """Conform out-of-block L4 declarations to the note (note wins).

    The marker block is the machine-owned single source; any OTHER packet declaration
    of an L4 field is a drift vector, because the pre-commit supervisor + bot read the
    tracker note as truth and flag a packet that declares a value the note does not.
    Each such out-of-block declaration is rewritten to the note's value so the packet,
    not just its block, cannot diverge. Three authoring surfaces are covered: a plain
    or bold list-item declaration in any field (incl. compact multi-field lines) via
    :func:`_conform_plain_l4_list_item_line`; a backtick-delimited inline-code span in
    any field via :func:`_conform_l4_decl_in_text`; and the plain-text ``Target gate:``
    header form for target_gate_id (the one L4-block field with a dedicated
    plain-header extractor) via :func:`_conform_target_gate_header_in_text`. The block
    region is sliced out and left byte-identical. A field the note OMITS (empty value)
    has any stale out-of-block declaration of its field spelling CLEARED (conform-to-
    absence) -- the plain/bold list item via :func:`_conform_plain_l4_list_item_line`
    and the inline-code span via :func:`_clear_l4_decl_in_text`. A standalone declaration
    collapses to the block's bare ``- `field`:`` form; a plain declaration grouped with a
    following L4 field on one line is dropped whole so the line collapses to the surviving
    fields with no ``field:.`` residue. The clear targets the field-DECLARATION spelling
    (the lowercase label) only, so the uppercase authorization-token marker
    ``FOUNDER_OVERRIDE:<wave_id>`` (which the note does not govern) is preserved, not
    blanked, in either the plain or the inline-code authoring form.
    """
    clean_lookup = _build_clean_l4_lookup(
        note_values,
        exact_evidence_command=exact_evidence_command,
    )

    def _rewrite(segment: str) -> str:
        # Plain / bold list-item declarations (the most common packet form), conformed
        # line by line so a prose mention of a field name is never rewritten.
        segment = "\n".join(
            _conform_plain_l4_list_item_line(line, clean_lookup)
            for line in segment.split("\n")
        )
        for label, marker in _L4_FIELDS_FROM_TRACKER:
            clean_value = clean_lookup.get(label, "")
            if not clean_value:
                # The note OMITS this field. Clear any stale inline-code declaration of
                # the field-DECLARATION spelling (the lowercase label) to the bare-colon
                # form (conform-to-absence) -- matching what the plain/bold conformer
                # above does for list items and what the machine block renders for an
                # omitted field. The marker spelling is deliberately NOT cleared: for
                # founder_override the marker is the uppercase authorization token
                # `FOUNDER_OVERRIDE:<wave_id>` commit automation reads (the note does not
                # govern it); for every other field the marker equals the label and is
                # handled by this same call. The plain-text `Target gate:` header is left
                # to the conform-to-value path below -- target_gate_id is structurally
                # present in every canonical note, so its absence path is unreachable, and
                # clearing the header would leave end-of-line trailing whitespace.
                segment = _clear_l4_decl_in_text(segment, label)
                continue
            for field_token in dict.fromkeys((label, marker)):
                segment = _conform_l4_decl_in_text(segment, field_token, clean_value)
            if label == "target_gate_id":
                # The gate also appears as a plain-text packet header
                # ("Target gate: G8") that the inline-code conformer above does not
                # reach; conform it too so the note wins on a divergent header.
                segment = _conform_target_gate_header_in_text(segment, clean_value)
        return segment

    # Locate the block by the markers that stand alone on their own lines, so the
    # sliced-out (kept byte-identical) region is the real machine block and not an
    # inline prose mention of the marker text -- see :func:`_find_block_marker_line`.
    start = _find_block_marker_line(packet_text, L4_FIELDS_FROM_TRACKER_START)
    end = _find_block_marker_line(
        packet_text,
        L4_FIELDS_FROM_TRACKER_END,
        search_from=start + 1 if start != -1 else 0,
    )
    if start != -1 and end != -1 and end > start:
        end += len(L4_FIELDS_FROM_TRACKER_END)
        return (
            _rewrite(packet_text[:start])
            + packet_text[start:end]
            + _rewrite(packet_text[end:])
        )
    return _rewrite(packet_text)


def reconcile_packet_l4_fields_block(
    packet_text: str,
    tracker_note_text: str,
    *,
    exact_evidence_command: str | None = None,
) -> str:
    """Reconcile a packet's L4-field block to the canonical tracker note (note wins).

    The machine-owned block is rendered solely from the note's marker values, and any
    L4 declaration OUTSIDE the block -- a plain or bold list-item declaration (incl.
    compact multi-field lines), a backtick-delimited inline-code span, or the
    plain-text ``Target gate:`` header form for target_gate_id -- is rewritten to the
    same note-derived value, so no independently-supplied packet value (in the block
    or in the body) can survive divergence. The reverse never occurs. Idempotent.
    """
    note_values = derive_l4_fields_from_tracker_note(tracker_note_text)
    block = render_l4_fields_block_from_tracker_note(tracker_note_text)
    reconciled = _replace_l4_fields_block(packet_text, block)
    return _conform_out_of_block_l4_decls(
        reconciled,
        note_values,
        exact_evidence_command=exact_evidence_command,
    )


def reconcile_packet_l4_fields_block_for_wave(
    repo_root: Path,
    wave_id: str,
    packet_text: str,
) -> str:
    """Reconcile ``packet_text``'s L4-field block to wave_id's canonical TASKS.md note.

    Returns ``packet_text`` unchanged when no canonical note exists yet -- the
    initial Phase A ``create_plan_draft`` can run before the note is written, and
    the commit-path refresh reconciles later. This is the seam phase_a_executor
    calls so the note-derived block stays centralized in the module that owns the
    tracker-note marker extractors (one-way dependency: commit_executor does not
    import phase_a_executor, so there is no import cycle).
    """
    note = _extract_existing_canonical_tracker_note_from_tasks(repo_root, str(wave_id or ""))
    if not note.strip():
        return packet_text
    return reconcile_packet_l4_fields_block(packet_text, note)


_PACKET_INLINE_EVIDENCE_COMMAND_FORM_A_RE = re.compile(
    r"`evidence_command:(?P<spacing>[ \t]*)(?P<value>[^`\r\n]*)`"
)
_PACKET_INLINE_EVIDENCE_COMMAND_FORM_B_RE = re.compile(
    r"`evidence_command`:[ \t]*`(?P<value>[^`\r\n]*)`"
)
_PACKET_INLINE_EVIDENCE_COMMAND_SHAPE_RE = re.compile(
    r"`evidence_command(?:[ \t]*:|`[ \t]*:)"
)
_PACKET_PLAIN_EVIDENCE_COMMAND_VALUE_RE = re.compile(
    r"^[ \t]*`(?P<value>[^`\r\n]*)`[ \t]*[.;,]?[ \t]*$"
)
_TRACKER_FIELD_MARKER_RE = re.compile(
    r"(?<!\S)(?P<field>"
    + "|".join(
        re.escape(marker)
        for marker in sorted(_BUILDER_TRACKER_MARKER_NAMES, key=len, reverse=True)
    )
    + r"):"
)
_TRACKER_CANONICAL_EVIDENCE_COMMAND_VALUE_RE = re.compile(
    r"^[ \t]*`(?P<value>[^`\r\n]*)`(?:\.)?[ \t]*$"
)


def _own_line_marker_positions(text: str, marker: str) -> list[int]:
    positions: list[int] = []
    search_from = 0
    while True:
        position = _find_block_marker_line(text, marker, search_from=search_from)
        if position == -1:
            return positions
        positions.append(position)
        search_from = position + len(marker)


def _packet_text_without_generated_evidence_blocks(packet_text: str) -> str:
    """Return packet-authored text, excluding commit-generated evidence replicas."""
    text = str(packet_text or "")
    ranges: list[tuple[int, int]] = []
    for start_marker, end_marker, unbalanced_error in (
        (
            L4_FIELDS_FROM_TRACKER_START,
            L4_FIELDS_FROM_TRACKER_END,
            "existing L4_FIELDS_FROM_TRACKER markers are unbalanced",
        ),
        (
            COMMIT_PATH_REFRESH_START,
            COMMIT_PATH_REFRESH_END,
            "existing Commit Path Truth Refresh markers are unbalanced",
        ),
    ):
        starts = _own_line_marker_positions(text, start_marker)
        ends = _own_line_marker_positions(text, end_marker)
        pairs = list(zip(starts, ends))
        if (
            len(starts) != len(ends)
            or any(start >= end for start, end in pairs)
            or any(
                previous_end >= start
                for (_previous_start, previous_end), (start, _end) in zip(
                    pairs,
                    pairs[1:],
                )
            )
        ):
            raise ValueError(unbalanced_error)
        for start, end in pairs:
            end += len(end_marker)
            ranges.append((start, end))
    if not ranges:
        return text

    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start < merged[-1][1]:
            # The checks above validate each marker family independently.  A
            # block of one type can therefore still be nested in (or cross)
            # a block of the other type.  Do not merge that malformed shape:
            # reconciliation replaces the block types separately, so an outer
            # replacement could otherwise erase the already-reconciled inner
            # block after tracker state has been refreshed.
            raise ValueError(
                "existing generated evidence blocks overlap across block types"
            )
        if merged and start == merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    authored: list[str] = []
    cursor = 0
    for start, end in merged:
        authored.append(text[cursor:start])
        authored.append("\n" * max(1, text[start:end].count("\n")))
        cursor = end
    authored.append(text[cursor:])
    return "".join(authored)


def _plain_l4_declaration_matches(line: str) -> list[re.Match[str]]:
    """Return the plain/bold L4 keys that the packet conformer treats as declarations."""
    keys = list(_PLAIN_L4_KEY_RE.finditer(line))
    if not keys:
        return []
    spans = _backtick_spans(line)
    first = keys[0]
    if _pos_in_backtick_span(first.start(), spans):
        return []
    if not _PLAIN_L4_LEAD_PREFIX_RE.fullmatch(line[:first.start()]):
        return []

    accepted = [first]
    for key in keys[1:]:
        if _pos_in_backtick_span(key.start(), spans):
            continue
        before = line[:key.start()].rstrip(" \t")
        if before[-1:] in _PLAIN_L4_GROUP_BOUNDARY_CHARS:
            accepted.append(key)
    return accepted


def _packet_authored_evidence_command(
    packet_text: str,
    *,
    active_packet_path: str,
) -> tuple[str | None, str | None]:
    """Resolve one exact authored packet command without consulting generated replicas."""
    values: set[str] = set()
    malformed = False
    try:
        authored_text = _packet_text_without_generated_evidence_blocks(packet_text)
    except ValueError as exc:
        return None, str(exc)
    for line in authored_text.splitlines():
        plain_keys = _plain_l4_declaration_matches(line)
        for index, key in enumerate(plain_keys):
            if key.group("field") != "evidence_command":
                continue
            value_end = plain_keys[index + 1].start() if index + 1 < len(plain_keys) else len(line)
            match = _PACKET_PLAIN_EVIDENCE_COMMAND_VALUE_RE.fullmatch(
                line[key.end():value_end]
            )
            if match is None or not match.group("value").strip():
                malformed = True
            else:
                values.add(match.group("value"))

        for shape in _PACKET_INLINE_EVIDENCE_COMMAND_SHAPE_RE.finditer(line):
            match = _PACKET_INLINE_EVIDENCE_COMMAND_FORM_B_RE.match(line, shape.start())
            if match is None:
                match = _PACKET_INLINE_EVIDENCE_COMMAND_FORM_A_RE.match(line, shape.start())
            if match is None or not match.group("value").strip():
                malformed = True
            else:
                values.add(match.group("value"))

    if malformed:
        return None, (
            "active L4_ENABLER packet has a malformed authored evidence_command "
            f"declaration before commit packet truth refresh: {active_packet_path}"
        )
    if len(values) > 1:
        return None, (
            "active L4_ENABLER packet has conflicting authored evidence_command "
            f"declarations before commit packet truth refresh: {active_packet_path}"
        )
    if values:
        for start_marker, block_name in (
            (L4_FIELDS_FROM_TRACKER_START, "L4_FIELDS_FROM_TRACKER"),
            (COMMIT_PATH_REFRESH_START, "Commit Path Truth Refresh"),
        ):
            if len(_own_line_marker_positions(packet_text, start_marker)) > 1:
                return None, (
                    f"active L4_ENABLER packet has multiple {block_name} blocks "
                    f"before commit packet truth refresh: {active_packet_path}"
                )
    return (next(iter(values)) if values else None), None


def _tracker_field_matches_outside_inline_code(
    note: str,
) -> tuple[list[re.Match[str]], bool]:
    text = str(note or "")
    matches: list[re.Match[str]] = []
    cursor = 0
    while cursor < len(text):
        marker = _TRACKER_FIELD_MARKER_RE.search(text, cursor)
        tick = text.find("`", cursor)
        if tick != -1 and (marker is None or tick < marker.start()):
            close = text.find("`", tick + 1)
            if close == -1:
                return matches, True
            cursor = close + 1
            continue
        if marker is None:
            break
        matches.append(marker)
        cursor = marker.end()
    return matches, False


def _tracker_evidence_command_values_exact(note: str) -> tuple[set[str], bool]:
    """Decode canonical tracker commands without normalizing any payload byte."""
    text = str(note or "")
    values: set[str] = set()
    fields, malformed = _tracker_field_matches_outside_inline_code(text)
    for index, field in enumerate(fields):
        if field.group("field") != "evidence_command":
            continue
        value_end = fields[index + 1].start() if index + 1 < len(fields) else len(text)
        match = _TRACKER_CANONICAL_EVIDENCE_COMMAND_VALUE_RE.fullmatch(
            text[field.end():value_end]
        )
        if match is None or not match.group("value").strip():
            malformed = True
            continue
        values.add(match.group("value"))
    return values, malformed


def _resolve_explicit_l4_enabler_evidence_command(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    packet_text: str,
    active_packet_path: str,
) -> tuple[str | None, str | None]:
    """Bind packet intent to matching TASKS/handoff authority before any mutation."""
    packet_command, packet_error = _packet_authored_evidence_command(
        packet_text,
        active_packet_path=active_packet_path,
    )
    if packet_error or packet_command is None:
        return packet_command, packet_error

    wave_id = str(handoff.get("wave_id") or "")
    tasks_note = _extract_existing_canonical_tracker_note_from_tasks(repo_root, wave_id)
    if not tasks_note:
        return None, (
            "explicit L4_ENABLER evidence_command preservation requires one canonical "
            f"same-wave TASKS.md tracker note before commit packet truth refresh: {wave_id}"
        )
    handoff_note = str(handoff.get("tracker_note_text") or "")
    if len(handoff_note.splitlines()) != 1 or not _is_canonical_tracker_note_line(
        handoff_note,
        wave_id,
    ):
        return None, (
            "explicit L4_ENABLER evidence_command preservation requires a canonical "
            f"same-wave incoming handoff tracker note before commit packet truth refresh: {wave_id}"
        )

    tasks_values, tasks_malformed = _tracker_evidence_command_values_exact(tasks_note)
    handoff_values, handoff_malformed = _tracker_evidence_command_values_exact(handoff_note)
    if tasks_malformed or len(tasks_values) != 1:
        return None, (
            "current same-wave TASKS.md tracker note has a missing, malformed, or "
            f"conflicting evidence_command before explicit preservation: {wave_id}"
        )
    if handoff_malformed or len(handoff_values) != 1:
        return None, (
            "incoming same-wave handoff tracker note has a missing, malformed, or "
            f"conflicting evidence_command before explicit preservation: {wave_id}"
        )

    tasks_command = next(iter(tasks_values))
    handoff_command = next(iter(handoff_values))
    if tasks_command != handoff_command or packet_command != tasks_command:
        return None, (
            "explicit L4_ENABLER evidence_command mismatch before commit packet truth "
            "refresh; packet, TASKS.md, and incoming handoff commands must be "
            f"byte-identical: {wave_id}"
        )
    return packet_command, None


def _commit_supervisor_reentry_plan_path(handoff: dict[str, Any]) -> str:
    tracked_packet = _normalize_repo_relpath(str(handoff.get("tracked_packet") or ""))
    if tracked_packet:
        return tracked_packet
    for field in ("scope_items", "files_to_stage"):
        value = handoff.get(field)
        if not isinstance(value, list):
            continue
        for item in value:
            candidate = _normalize_repo_relpath(str(item or ""))
            if candidate.startswith("reports/control_plane/") and candidate.endswith(".md"):
                return candidate
    return ""


def _commit_supervisor_rejection_result(
    *,
    decision: str,
    summary: str,
    steps_completed: list[Any],
    handoff: dict[str, Any],
    wave_id: str,
    changed_files: list[str],
) -> dict[str, Any]:
    decision_text = str(decision or "UNKNOWN").strip() or "UNKNOWN"
    summary_text = str(summary or "").strip()
    message = f"Supervisor returned {decision_text}"
    if summary_text:
        message += f": {summary_text}"
    result: dict[str, Any] = {
        "status": "error",
        "step": "build_and_run_supervisor",
        "errors": [message],
        "steps_completed": list(steps_completed),
        "pre_commit_decision": decision_text,
        "pre_commit_summary": summary_text,
        "wave_id": wave_id,
    }
    if changed_files:
        result["changed_files"] = sorted(
            {
                _normalize_repo_relpath(str(path))
                for path in changed_files
                if _normalize_repo_relpath(str(path))
            }
        )
    if decision_text == "NEEDS_PHASE_B":
        plan_path = _commit_supervisor_reentry_plan_path(handoff)
        result.update({
            "failure_class": "needs_phase_b",
            "resume_after": "needs_phase_b_reentry",
            "detail": message,
            "reason": message,
        })
        if plan_path:
            result["plan_path"] = plan_path
            result["tracked_packet"] = plan_path
    return result


def _refresh_tracker_note_wave_file_count(note: str, file_count: int) -> str:
    """Align generated tracker-note file counts with the rebuilt staged scope."""
    if file_count < 0:
        return note

    replacements = [
        (
            r"Routed commit handoff scopes \d+ wave-owned file\(s\)",
            f"Routed commit handoff scopes {file_count} wave-owned file(s)",
        ),
        (
            r"handoff for ([^.;]+?) is now bound to \d+ wave-owned file\(s\)",
            rf"handoff for \1 is now bound to {file_count} wave-owned file(s)",
        ),
        (
            r"handoff for ([^.;]+?) now carries \d+ wave-owned file\(s\)",
            rf"handoff for \1 now carries {file_count} wave-owned file(s)",
        ),
        (
            r"handoff now carries \d+ wave-owned file\(s\)",
            f"handoff now carries {file_count} wave-owned file(s)",
        ),
        (
            r"Phase B emitted a commit-ready handoff for ([^.;]+?) with \d+ wave-owned file\(s\)",
            rf"Phase B emitted a commit-ready handoff for \1 with {file_count} wave-owned file(s)",
        ),
    ]
    refreshed = note
    for pattern, replacement in replacements:
        refreshed = re.sub(pattern, replacement, refreshed)
    return refreshed


def _refresh_tracker_note_bridge_rounds(
    note: str,
    bridge_status: dict[str, Any] | None,
) -> str:
    """Align generated tracker-note bridge rounds with the supervisor package."""
    if not isinstance(bridge_status, dict):
        return note
    rounds = max(
        _bridge_status_round_value(bridge_status.get("rounds")),
        _bridge_status_round_value(bridge_status.get("total_rounds")),
    )
    if rounds <= 0:
        return note
    return re.sub(r"bridge rounds=\d+", f"bridge rounds={rounds}", note)


_STRUCTURAL_WORKLOAD_EVIDENCE_MODULES = {
    "seed_auto_execution": (
        "test_seed_auto_execution_contract",
        "test_check_seed_auto_execution_contract",
    ),
    "rcx_engine_cycle": ("test_rcx_engine_workload_contract",),
    "execution_layer_truth": ("test_execution_layer_truth_contract",),
}


def _tracker_note_declares_l4_structural(note: str) -> bool:
    return re.search(r"\bClass:\s*`?L4_STRUCTURAL`?", note or "") is not None


def _tracker_note_declares_l4_enabler(note: str) -> bool:
    return re.search(r"\bClass:\s*`?L4_ENABLER`?", note or "") is not None


def _should_preserve_structural_tracker_note_for_control_refresh(
    existing_note: str,
    replacement_note: str,
) -> bool:
    return (
        _tracker_note_declares_l4_structural(existing_note)
        and _tracker_note_declares_l4_enabler(replacement_note)
    )


def _has_l4_gate_test_path(test_files: list[str]) -> bool:
    return any(
        path.startswith(("mu/tests/l4_gates/", "tests/l4_gates/"))
        for path in test_files
    )


def _structural_workload_evidence_modules(note: str) -> tuple[str, ...]:
    workload_target = _tracker_marker_value(note, "workload_target").strip("` .")
    return _STRUCTURAL_WORKLOAD_EVIDENCE_MODULES.get(workload_target, ())


def _test_files_cover_structural_tracker_evidence(note: str, test_files: list[str]) -> bool:
    """Return whether replacement pytest files still satisfy L4 structural evidence."""
    if not _has_l4_gate_test_path(test_files):
        return False
    required_modules = _structural_workload_evidence_modules(note)
    if required_modules and not any(
        module in path for module in required_modules for path in test_files
    ):
        return False
    return True


_PRESERVED_EVIDENCE_COMMAND_PLACEHOLDER = "__RCX_PRESERVED_EVIDENCE_COMMAND__"
_TRACKER_EVIDENCE_COMMAND_FIELD_RE = re.compile(
    r"(?<!\S)evidence_command:[ \t]*`[^`\r\n]+`"
)


def _replace_tracker_note_evidence_command_exact(note: str, command: str) -> str:
    """Replace only canonical tracker command fields without interpreting payload bytes."""
    return _TRACKER_EVIDENCE_COMMAND_FIELD_RE.sub(
        lambda _match: f"evidence_command: `{command}`",
        note,
    )


def _refresh_tracker_note_test_evidence(
    note: str,
    staged_paths: list[str],
    *,
    preserved_evidence_command: str | None = None,
) -> str:
    """Align generated tracker evidence, or retain an authorized explicit command."""
    test_files = _collect_wave_test_files(staged_paths)
    if not test_files:
        if preserved_evidence_command is not None:
            return _replace_tracker_note_evidence_command_exact(
                note,
                preserved_evidence_command,
            )
        return note
    refreshed = note
    if preserved_evidence_command is not None:
        # Keep the command opaque while the legacy global prose/count rewrites run.
        refreshed = _replace_tracker_note_evidence_command_exact(
            refreshed,
            _PRESERVED_EVIDENCE_COMMAND_PLACEHOLDER,
        )
    if (
        _tracker_note_declares_l4_structural(refreshed)
        and not _test_files_cover_structural_tracker_evidence(refreshed, test_files)
    ):
        if preserved_evidence_command is not None:
            return _replace_tracker_note_evidence_command_exact(
                refreshed,
                preserved_evidence_command,
            )
        return refreshed
    if preserved_evidence_command is None:
        evidence_command = (
            "evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            + " ".join(test_files)
            + "`"
        )
        refreshed = re.sub(
            r"evidence_command:\s*`PYTHONHASHSEED=0 python3 -m pytest -x --tb=short [^`]+`",
            evidence_command,
            refreshed,
        )
    refreshed = re.sub(
        r"Final pytest gate covered \d+ test file\(s\)",
        f"Final pytest gate covered {len(test_files)} test file(s)",
        refreshed,
    )
    refreshed = re.sub(
        r"Evidence gate exercises \d+ wave-owned test module\(s\)",
        f"Evidence gate exercises {len(test_files)} wave-owned test module(s)",
        refreshed,
    )
    refreshed = re.sub(
        r", \d+ wave-owned test module\(s\),",
        f", {len(test_files)} wave-owned test module(s),",
        refreshed,
    )
    if preserved_evidence_command is not None:
        refreshed = _replace_tracker_note_evidence_command_exact(
            refreshed,
            preserved_evidence_command,
        )
    return refreshed


def _tracker_field_span(note: str, marker: str) -> tuple[int, int] | None:
    match = re.search(rf"\b{re.escape(marker)}:\s*", note)
    if match is None:
        return None
    start = match.end()
    end = len(note)
    for candidate in _BUILDER_TRACKER_MARKER_NAMES:
        if candidate == marker:
            continue
        candidate_match = re.search(rf"\b{re.escape(candidate)}:", note[start:])
        if candidate_match is not None:
            end = min(end, start + candidate_match.start())
    return start, end


def _tracker_scope_ref_paths(evidence_delta: str) -> set[str]:
    match = re.search(r"\bscope_refs:\s*", evidence_delta)
    if match is None:
        return set()
    refs: set[str] = set()
    pos = match.end()
    while pos < len(evidence_delta):
        while pos < len(evidence_delta) and evidence_delta[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(evidence_delta) or evidence_delta[pos] in ".;":
            break
        if evidence_delta[pos] != "`":
            break
        close = evidence_delta.find("`", pos + 1)
        if close == -1:
            break
        ref = evidence_delta[pos + 1 : close].strip()
        if ref:
            refs.add(ref)
        pos = close + 1
    return refs


def _append_tracker_scope_refs(note: str, paths: list[str]) -> str:
    scoped_paths = _dedupe_repo_paths(paths)
    if not scoped_paths:
        return note
    span = _tracker_field_span(note, "evidence_delta")
    if span is None:
        return note
    start, end = span
    raw_value = note[start:end]
    stripped_value = raw_value.rstrip()
    suffix = raw_value[len(stripped_value):]
    registered_scope_refs = _tracker_scope_ref_paths(stripped_value)
    missing = [path for path in scoped_paths if path not in registered_scope_refs]
    if not missing:
        return note
    refs = ", ".join(f"`{path}`" for path in missing)
    base = stripped_value.rstrip(".")
    if "scope_refs:" in base:
        refreshed_value = f"{base}, {refs}."
    elif base:
        refreshed_value = f"{base}. scope_refs: {refs}."
    else:
        refreshed_value = f"scope_refs: {refs}."
    return note[:start] + refreshed_value + suffix + note[end:]


def _validate_commit_generated_governance_paths(
    repo_root: Path,
    paths: list[str],
    *,
    provenance: str,
    wave_id: str,
) -> tuple[list[str], str | None]:
    if not isinstance(paths, list):
        return [], "commit-generated governance paths must be a list"
    if not paths:
        return [], None
    normalized_paths: list[str] = []
    for raw_path in paths:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return [], "commit-generated governance paths must be non-empty strings"
        if _is_absolute_untrusted_path(raw_path):
            return [], f"commit-generated governance path is absolute or malformed: {raw_path}"
        if _has_path_traversal(raw_path):
            return [], f"commit-generated governance path contains traversal: {raw_path}"
        normalized = _normalize_repo_relpath(raw_path)
        if normalized != COMMIT_GENERATED_GOVERNANCE_GROWTH_CAP_PATH:
            return [], (
                "unsupported commit-generated governance path before supervisor: "
                f"{normalized}"
            )
        normalized_paths.append(normalized)
    settled_paths = _dedupe_repo_paths(normalized_paths)
    for path in settled_paths:
        full_path = (repo_root / path).resolve(strict=False)
        try:
            full_path.relative_to(repo_root.resolve())
        except ValueError:
            return [], f"commit-generated governance path escapes repo root: {path}"
    if provenance == "bumped":
        staged = set(_current_staged_diff_paths(repo_root))
        for path in settled_paths:
            if path not in staged:
                return [], (
                    "commit-generated governance path is not staged before supervisor: "
                    f"{path}"
                )
        return settled_paths, None
    if provenance == "already_recorded":
        for path in settled_paths:
            error = _validate_clean_already_recorded_commit_generated_governance_path(
                repo_root,
                path=path,
                wave_id=wave_id,
            )
            if error:
                return [], error
        return settled_paths, None
    return [], (
        "unsupported commit-generated governance provenance before supervisor: "
        f"{provenance}"
    )


def _validate_clean_already_recorded_commit_generated_governance_path(
    repo_root: Path,
    *,
    path: str,
    wave_id: str,
) -> str | None:
    """Validate same-wave already_recorded growth-cap reuse from HEAD/index truth."""
    if path != COMMIT_GENERATED_GOVERNANCE_GROWTH_CAP_PATH:
        return (
            "unsupported already_recorded commit-generated governance path before "
            f"supervisor: {path}"
        )
    if not wave_id:
        return "commit-generated governance already_recorded reuse requires wave_id"
    head_text = _git_head_text_for_repo_path(repo_root, path)
    if head_text is None:
        return (
            "commit-generated governance already_recorded path is missing from "
            f"HEAD before supervisor: {path}"
        )
    index_text = _git_index_text_for_repo_path(repo_root, path)
    if index_text is None:
        return (
            "commit-generated governance already_recorded path is missing from "
            f"the index before supervisor: {path}"
        )
    if head_text != index_text:
        return (
            "commit-generated governance already_recorded path has index/HEAD "
            f"mismatch before supervisor: {path}"
        )
    if not _extract_same_wave_founder_override_token(head_text, wave_id):
        return (
            "commit-generated governance already_recorded path lacks same-wave "
            f"HEAD/index provenance before supervisor: {path}"
        )

    staged_delta = _run(
        ["git", "diff", "--cached", "--quiet", "--", path],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    if staged_delta.returncode not in (0, 1):
        return (
            "commit-generated governance already_recorded path staged-delta "
            f"state is ambiguous before supervisor: {path}"
        )
    if staged_delta.returncode == 1:
        return (
            "commit-generated governance already_recorded path has staged delta "
            f"before supervisor: {path}"
        )

    unstaged_delta = _run(
        ["git", "diff", "--quiet", "--", path],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    if unstaged_delta.returncode not in (0, 1):
        return (
            "commit-generated governance already_recorded path unstaged-delta "
            f"state is ambiguous before supervisor: {path}"
        )
    if unstaged_delta.returncode == 1:
        return (
            "commit-generated governance already_recorded path has unstaged "
            f"delta before supervisor: {path}"
        )
    return None


def _validate_commit_generated_governance_provenance(
    provenance: Any,
) -> tuple[str, str | None]:
    normalized = str(provenance or "").strip()
    if not normalized:
        return "", "commit-generated governance provenance is required before supervisor"
    if normalized not in COMMIT_GENERATED_GOVERNANCE_STEP5E_PROVENANCES:
        return "", (
            "unsupported commit-generated governance provenance before supervisor: "
            f"{normalized}"
        )
    return normalized, None


def _render_commit_generated_governance_authorization_block(
    *,
    wave_id: str,
    paths: list[str],
    provenance: str,
) -> str:
    lines = [
        COMMIT_GENERATED_GOVERNANCE_AUTH_START,
        "## Commit-Time Generated Governance Authorization",
        "",
        f"- Refresh wave: `{wave_id}`",
        f"- Step-5e provenance: `{provenance}`",
        "- Purpose: commit automation may bind the exact same-wave growth-cap "
        "governance file after Phase B review; first bumps require staged-index "
        "proof, while already-recorded reuse requires clean HEAD/index proof.",
        "- Authorized generated governance path(s):",
    ]
    for path in paths:
        lines.append(f"  - `{path}`")
    lines.extend([
        "- Scope binding: the path above is in scope only as the Step-5e "
        "same-wave growth-cap governance mutation or exact clean same-wave "
        "continuation evidence.",
        "- Pre-review boundary: this block does not add the path to the locked "
        "Phase B/pre-review candidate allowlist and cannot authorize arbitrary "
        "implementation files.",
        "- Acceptance binding: unsupported, malformed, outside-repo, dirty, "
        "wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free "
        "generated governance paths fail before supervisor.",
        COMMIT_GENERATED_GOVERNANCE_AUTH_END,
    ])
    return "\n".join(lines) + "\n"


def _replace_commit_generated_governance_authorization_block(
    packet_text: str,
    block: str,
) -> str:
    start = packet_text.find(COMMIT_GENERATED_GOVERNANCE_AUTH_START)
    end = packet_text.find(COMMIT_GENERATED_GOVERNANCE_AUTH_END)
    if start != -1 and end != -1 and end > start:
        end += len(COMMIT_GENERATED_GOVERNANCE_AUTH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Commit-Time Generated Governance Authorization markers are unbalanced")
    for marker in (
        DEFERRED_AUTH_REFRESH_START,
        COMMIT_PATH_REFRESH_START,
        L4_FIELDS_FROM_TRACKER_START,
    ):
        insert_at = packet_text.find(marker)
        if insert_at != -1:
            return (
                packet_text[:insert_at].rstrip()
                + "\n\n"
                + block.rstrip()
                + "\n\n"
                + packet_text[insert_at:]
            )
    return packet_text.rstrip() + "\n\n" + block


def _refresh_commit_generated_governance_authorization(
    packet_text: str,
    *,
    wave_id: str,
    paths: list[str],
    provenance: str,
) -> str:
    if not paths:
        return packet_text
    block = _render_commit_generated_governance_authorization_block(
        wave_id=wave_id,
        paths=paths,
        provenance=provenance,
    )
    return _replace_commit_generated_governance_authorization_block(packet_text, block)


def _render_commit_path_truth_refresh_block(
    *,
    wave_id: str,
    active_packet_path: str,
    tracker_note_text: str,
    staged_paths: list[str],
    indicator_path: str,
    commit_status: str,
    evidence_handles: dict[str, str],
    pre_commit_receipt_path: str,
    commit_generated_governance_paths: list[str] | None = None,
) -> str:
    tracker_note_sha = hashlib.sha256(tracker_note_text.encode("utf-8")).hexdigest()
    evidence_command = _tracker_marker_value(tracker_note_text, "evidence_command")
    evidence_delta = _tracker_marker_value(tracker_note_text, "evidence_delta")
    lines = [
        COMMIT_PATH_REFRESH_START,
        "## Commit Path Truth Refresh",
        "",
        f"- Refresh wave: `{wave_id}`",
        f"- Active packet: `{active_packet_path}`",
        f"- Commit status: `{commit_status}`",
        f"- Tracker note sha256: `{tracker_note_sha}`",
        f"- Indicator artifact: `{indicator_path}`",
    ]
    if pre_commit_receipt_path:
        lines.append(f"- Pre-commit receipt handle: `{pre_commit_receipt_path}`")
    if evidence_command:
        lines.append(f"- Evidence command: {evidence_command}")
    if evidence_delta:
        lines.append(f"- Evidence delta: {evidence_delta}")
    if commit_generated_governance_paths:
        lines.append("- Commit-generated governance paths:")
        for path in commit_generated_governance_paths:
            lines.append(f"  - `{path}`")
    lines.append("- Evidence handles:")
    if evidence_handles:
        for key in sorted(evidence_handles):
            lines.append(f"  - `{key}`: `{evidence_handles[key]}`")
    else:
        lines.append("  - none")
    lines.append("- Current staged files:")
    for path in staged_paths:
        lines.append(f"  - `{path}`")
    lines.append(COMMIT_PATH_REFRESH_END)
    return "\n".join(lines) + "\n"


def _replace_commit_path_truth_refresh_block(packet_text: str, block: str) -> str:
    start = packet_text.find(COMMIT_PATH_REFRESH_START)
    end = packet_text.find(COMMIT_PATH_REFRESH_END)
    if start != -1 and end != -1 and end > start:
        end += len(COMMIT_PATH_REFRESH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Commit Path Truth Refresh markers are unbalanced")
    return packet_text.rstrip() + "\n\n" + block


def _same_wave_deferred_non_blocking_paths(wave_id: str, paths: list[str]) -> list[str]:
    normalized_wave = normalize_wave_id(str(wave_id or ""))
    if not normalized_wave:
        return []
    expected = f"reports/deferred/non_blocking/{normalized_wave}_bridge_nonblockers.md"
    return [expected] if expected in set(_dedupe_repo_paths(paths)) else []


def _is_staged_deletion(repo_root: Path, rel_path: str) -> bool:
    """Return whether rel_path is already staged as a deletion."""
    normalized = _normalize_repo_relpath(str(rel_path or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return False
    try:
        staged_delete = _run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=D", "--", normalized],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False
    return staged_delete.returncode == 0 and normalized in set(
        _dedupe_repo_paths(staged_delete.stdout.splitlines())
    )


def _is_absent_from_worktree_and_index(repo_root: Path, rel_path: str) -> bool:
    """Return true when repo truth has no live worktree or index entry."""
    normalized = _normalize_repo_relpath(str(rel_path or ""))
    if not normalized or _is_absolute_untrusted_path(normalized) or _has_path_traversal(normalized):
        return False
    path = repo_root / normalized
    if path.exists() or path.is_symlink():
        return False
    return not _git_index_contains_repo_path(repo_root, normalized)


def _same_wave_active_deferred_non_blocking_paths(
    wave_id: str,
    paths: list[str],
    *,
    repo_root: Path | None = None,
) -> list[str]:
    active_paths = _same_wave_deferred_non_blocking_paths(wave_id, paths)
    if repo_root is None:
        return active_paths
    return [
        path for path in active_paths
        if not (
            _is_staged_deletion(repo_root, path)
            or _is_absent_from_worktree_and_index(repo_root, path)
        )
    ]


def _same_wave_closed_deferred_archive_paths(wave_id: str, paths: list[str]) -> list[str]:
    normalized_wave = normalize_wave_id(str(wave_id or ""))
    if not normalized_wave:
        return []
    prefix = f"reports/archive/deferred/{normalized_wave}_bridge_nonblockers"
    return sorted(
        path for path in _dedupe_repo_paths(paths)
        if path.startswith(prefix)
        and "_closed-by-" in Path(path).name
        and path.endswith(".md")
    )


def _render_same_wave_deferred_authorization_block(wave_id: str, paths: list[str]) -> str:
    lines = [
        DEFERRED_AUTH_REFRESH_START,
        "## Same-Wave Deferred Non-Blocking Authorization",
        "",
        f"- Refresh wave: `{wave_id}`",
        "- Purpose: Phase B and commit automation may stage the same-wave "
        "non-blocking bridge findings packet as deferred follow-up instead of "
        "blocking an otherwise commit-ready wave.",
        "- Authorized deferred packet(s):",
    ]
    for path in paths:
        lines.append(f"  - `{path}`")
    lines.extend([
        "- Scope binding: the packet(s) above are in scope only as generated "
        "same-wave non-blocking bridge findings packets.",
        "- Acceptance binding: the final touched-file set may include the packet(s) "
        "above when they are also present in `deferred_items` or current staged files.",
        DEFERRED_AUTH_REFRESH_END,
    ])
    return "\n".join(lines) + "\n"


def _render_no_same_wave_deferred_authorization_block(wave_id: str) -> str:
    lines = [
        DEFERRED_AUTH_REFRESH_START,
        "## Same-Wave Deferred Non-Blocking Authorization",
        "",
        f"- Refresh wave: `{wave_id}`",
        "- Purpose: no active same-wave deferred non-blocking bridge findings "
        "packet is authorized for this commit package.",
        "- Authorized deferred packet(s): none",
        "- Scope binding: no generated bridge packet for this wave is authorized "
        "in `reports/deferred/non_blocking/` unless it exists as a staged file "
        "and is listed in `deferred_items`.",
        "- Acceptance binding: generated bridge packet paths for this wave must "
        "remain absent from active deferred lanes unless the package carries an "
        "existing staged deferred packet.",
        DEFERRED_AUTH_REFRESH_END,
    ]
    return "\n".join(lines) + "\n"


def _replace_same_wave_deferred_authorization_block(packet_text: str, block: str) -> str:
    start = packet_text.find(DEFERRED_AUTH_REFRESH_START)
    end = packet_text.find(DEFERRED_AUTH_REFRESH_END)
    if start != -1 and end != -1 and end > start:
        end += len(DEFERRED_AUTH_REFRESH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Same-Wave Deferred Non-Blocking Authorization markers are unbalanced")
    commit_refresh_start = packet_text.find(COMMIT_PATH_REFRESH_START)
    if commit_refresh_start != -1:
        return (
            packet_text[:commit_refresh_start].rstrip()
            + "\n\n"
            + block.rstrip()
            + "\n\n"
            + packet_text[commit_refresh_start:]
        )
    return packet_text.rstrip() + "\n\n" + block


def _section_bounds(lines: list[str], heading: str) -> tuple[int, int] | None:
    start = next((idx for idx, line in enumerate(lines) if line.strip() == heading), None)
    if start is None:
        return None
    end = next(
        (idx for idx in range(start + 1, len(lines)) if lines[idx].startswith("## ")),
        len(lines),
    )
    return start, end


def _append_paths_to_bounded_packet_line(line: str, paths: list[str]) -> str:
    missing = [path for path in paths if f"`{path}`" not in line]
    if not missing:
        return line
    addition = ", " + ", ".join(f"`{path}`" for path in missing)
    for anchor in (
        ", or a canonical",
        ", and the same-wave canonical",
        ", or returns",
        " or returns",
    ):
        if anchor in line:
            return line.replace(anchor, addition + anchor, 1)
    return line.rstrip(".") + addition + "."


def _refresh_same_wave_deferred_packet_authorization(
    packet_text: str,
    *,
    wave_id: str,
    deferred_paths: list[str],
) -> str:
    paths = _same_wave_deferred_non_blocking_paths(wave_id, deferred_paths)
    if not paths:
        if (
            DEFERRED_AUTH_REFRESH_START in packet_text
            or DEFERRED_AUTH_REFRESH_END in packet_text
        ):
            block = _render_no_same_wave_deferred_authorization_block(wave_id)
            return _replace_same_wave_deferred_authorization_block(packet_text, block)
        return packet_text

    had_final_newline = packet_text.endswith("\n")
    lines = packet_text.splitlines()
    scope_bounds = _section_bounds(lines, "## Scope")
    if scope_bounds is not None:
        scope_start, scope_end = scope_bounds
        scope_text = "\n".join(lines[scope_start:scope_end])
        scope_bullets: list[str] = []
        for path in paths:
            if f"`{path}`" in scope_text:
                continue
            scope_bullets.extend([
                f"- `{path}`",
                "  - Same-wave Phase B/commit generated deferred non-blocking "
                "bridge findings packet only; no unrelated deferred report is "
                "authorized by this wave.",
            ])
        if scope_bullets:
            insert_at = next(
                (
                    idx
                    for idx in range(scope_start + 1, scope_end)
                    if lines[idx].startswith("Only files under ")
                ),
                scope_end,
            )
            if insert_at > 0 and lines[insert_at - 1].strip():
                scope_bullets.insert(0, "")
            if insert_at < len(lines) and lines[insert_at].strip():
                scope_bullets.append("")
            lines[insert_at:insert_at] = scope_bullets

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- The required fix resolves to files outside "):
            lines[idx] = _append_paths_to_bounded_packet_line(line, paths)
        elif stripped.startswith("- The final touched-file set stays within "):
            lines[idx] = _append_paths_to_bounded_packet_line(line, paths)

    refreshed = "\n".join(lines)
    if had_final_newline:
        refreshed += "\n"
    block = _render_same_wave_deferred_authorization_block(wave_id, paths)
    return _replace_same_wave_deferred_authorization_block(refreshed, block)


def _commit_refresh_evidence_handles(
    handoff: dict[str, Any],
    *,
    indicator_path: str,
    include_pre_commit_receipt: bool = True,
) -> dict[str, str]:
    evidence_handles: dict[str, str] = {}
    raw = handoff.get("evidence_handles")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "pre_commit_receipt" and not include_pre_commit_receipt:
                continue
            if isinstance(key, str) and isinstance(value, str):
                evidence_handles[key] = value
    evidence_handles.setdefault("indicator", indicator_path)
    receipt = handoff.get("pre_commit_receipt_path")
    if include_pre_commit_receipt and isinstance(receipt, str) and receipt.strip():
        evidence_handles.setdefault("pre_commit_receipt", receipt.strip())
    return evidence_handles


_PENDING_PRE_COMMIT_RECEIPT_RE = re.compile(
    r"\.agent_bus(?:-[A-Za-z0-9_.-]+)?/meta/pre_commit_receipts/[^\s`]+?\.json"
)


def _mark_tracker_note_pre_commit_receipt_pending(tracker_note_text: str) -> str:
    """Remove stale exact receipt claims while pre-commit supervisor is pending."""
    receipt_path = _PENDING_PRE_COMMIT_RECEIPT_RE.pattern
    refreshed = tracker_note_text.replace(
        "commit-ready Phase B handoff",
        "pre-commit supervisor package refresh",
    )
    refreshed = re.sub(
        r"Phase B emitted a commit-ready handoff for ([^.;]+?) with (\d+) wave-owned file\(s\)",
        r"Phase B refreshed the pre-commit supervisor package for \1 with \2 wave-owned file(s)",
        refreshed,
    )
    refreshed = re.sub(
        rf"\(3\)\s+Commit handoff carries explicit receipt authority at\s+{receipt_path}\.*",
        "(3) Pre-commit supervisor receipt remains pending for the current staged package.",
        refreshed,
    )
    refreshed = re.sub(
        rf"\(2\)\s+Commit handoff carries (\d+) wave-owned file\(s\) with explicit "
        rf"receipt authority at\s+{receipt_path}\.*",
        r"(2) Commit handoff carries \1 wave-owned file(s) with pre-commit supervisor "
        r"receipt pending for the current staged package.",
        refreshed,
    )
    refreshed = refreshed.replace(
        "explicit receipt authority, and an L4-compliant tracker note.",
        "package-bound L4 authority pending pre-commit supervisor validation.",
    )
    return refreshed


def _rebuild_handoff_after_packet_truth_refresh(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    active_packet_path: str,
    staged_paths: list[str],
    evidence_handles: dict[str, str],
    commit_generated_governance_paths: list[str] | None = None,
    preserved_evidence_command: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    scope_items = handoff.get("scope_items")
    generated_scope_paths = commit_generated_governance_paths or []
    rebuilt_scope_items = _dedupe_repo_paths([
        *(scope_items if isinstance(scope_items, list) else []),
        active_packet_path,
        *generated_scope_paths,
    ])
    bridge_status = _effective_commit_bridge_status(
        repo_root=repo_root,
        handoff=handoff,
        active_packet_path=active_packet_path,
    )
    tracker_note_text = str(handoff.get("tracker_note_text") or "")
    if preserved_evidence_command is not None:
        # build_commit_handoff performs several global tracker-note repairs. Hide
        # command payload bytes from those rewrites, then restore the authorized
        # value after the rebuilt handoff has passed its existing validation.
        tracker_note_text = _replace_tracker_note_evidence_command_exact(
            tracker_note_text,
            _PRESERVED_EVIDENCE_COMMAND_PLACEHOLDER,
        )
    tracker_note_text = _refresh_tracker_note_wave_file_count(
        tracker_note_text,
        len(staged_paths),
    )
    rebuilt, errors = build_commit_handoff(
        wave_id=str(handoff.get("wave_id") or ""),
        task_id=str(handoff.get("task_id") or ""),
        files_to_stage=staged_paths,
        commit_message=str(handoff.get("commit_message") or ""),
        fixes_implemented=list(handoff.get("fixes_implemented") or []),
        wave_class=str(handoff.get("wave_class") or "L4_ENABLER"),
        target_gate_id=str(handoff.get("target_gate_id") or "G8"),
        caller=str(handoff.get("caller") or "phase_b"),
        base_branch=str(handoff.get("base_branch") or "dev"),
        branch_prefix=str(handoff.get("branch_prefix") or "jabramsja"),
        target_branch=handoff.get("target_branch") if isinstance(handoff.get("target_branch"), str) else None,
        force_add_files=[],
        pr_title=str(handoff.get("pr_title") or ""),
        pr_body=str(handoff.get("pr_body") or ""),
        tracker_note_text=tracker_note_text,
        supervisor_lane=(
            str(handoff.get("supervisor_lane"))
            if isinstance(handoff.get("supervisor_lane"), str)
            else None
        ),
        deferred_items=(
            list(handoff.get("deferred_items"))
            if isinstance(handoff.get("deferred_items"), list)
            else None
        ),
        bridge_status=bridge_status,
        scope_items=rebuilt_scope_items,
        evidence_handles=evidence_handles,
        pre_commit_receipt_path=(
            str(handoff.get("pre_commit_receipt_path") or "")
            if "pre_commit_receipt_path" in handoff
            else None
        ),
        repo_root=repo_root,
        tracked_packet=active_packet_path,
    )
    if not errors and preserved_evidence_command is not None:
        rebuilt = {
            **rebuilt,
            "tracker_note_text": _replace_tracker_note_evidence_command_exact(
                str(rebuilt.get("tracker_note_text") or ""),
                preserved_evidence_command,
            ),
        }
        valid, restored_errors = validate_handoff(rebuilt, repo_root=repo_root)
        if not valid:
            return rebuilt, restored_errors
    return rebuilt, errors


def _bridge_status_round_value(raw_value: Any) -> int:
    try:
        return max(int(raw_value or 0), 0)
    except (TypeError, ValueError):
        return 0


_BRIDGE_ROUND_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_BRIDGE_ROUND_WORD_PATTERN = "|".join(
    sorted((re.escape(word) for word in _BRIDGE_ROUND_WORDS), key=len, reverse=True)
)
_BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE = re.compile(
    r"\b(?:such\s+as|for\s+example|e\.g\.|examples?\s*(?:include|:)|sample)\b",
    flags=re.IGNORECASE,
)


def _documented_bridge_round_value(raw_value: str) -> int:
    normalized = raw_value.strip().lower()
    if normalized.isdigit():
        return int(normalized)
    return _BRIDGE_ROUND_WORDS.get(normalized, 0)


def _bridge_round_match_is_illustrative(text: str, match_start: int) -> bool:
    line_start = text.rfind("\n", 0, match_start) + 1
    prefix = text[line_start:match_start]
    return bool(_BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE.search(prefix))


def _documented_bridge_round_floor_from_text(text: str) -> int:
    round_floor = 0
    for match in re.finditer(r"\bBridge\s+Round\s+(\d+)\b", text, flags=re.IGNORECASE):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, int(match.group(1)))
    for match in re.finditer(
        rf"\b(\d+|{_BRIDGE_ROUND_WORD_PATTERN})\s+"
        r"(?:Phase\s+[AB]\s+)?bridge\s+rounds?\b",
        text,
        flags=re.IGNORECASE,
    ):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, _documented_bridge_round_value(match.group(1)))
    return round_floor


def _same_wave_document_bridge_round_floor(
    repo_root: Path,
    *,
    wave_id: str,
    active_packet_path: str,
    handoff: dict[str, Any],
) -> int:
    """Return highest same-wave Bridge Round mention in packet/deferred truth."""
    candidate_paths = _dedupe_repo_paths(
        [
            active_packet_path,
            *(
                list(handoff.get("deferred_items"))
                if isinstance(handoff.get("deferred_items"), list)
                else []
            ),
        ]
    )
    round_floor = 0
    for rel_path in candidate_paths:
        if not rel_path or rel_path.startswith("<") or not rel_path.endswith(".md"):
            continue
        full_path = (repo_root / rel_path).resolve()
        try:
            if not full_path.is_relative_to(repo_root.resolve()):
                continue
            text = full_path.read_text(encoding="utf-8")
        except OSError:
            continue
        normalized_wave_id = normalize_wave_id(wave_id)
        same_wave = (
            rel_path == active_packet_path
            and _packet_declares_same_wave_id(text, normalized_wave_id)
        ) or bool(
            re.search(
                rf"(?im)^\s*(?:Wave|Wave ID):\s*{re.escape(normalized_wave_id)}\s*$",
                text,
            )
        )
        if not same_wave:
            continue
        round_floor = max(round_floor, _documented_bridge_round_floor_from_text(text))
    return round_floor


def _effective_commit_bridge_status(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    active_packet_path: str,
) -> dict[str, Any] | None:
    raw_status = handoff.get("bridge_status")
    if not isinstance(raw_status, dict):
        raw_status = {}
    current_rounds = max(
        _bridge_status_round_value(raw_status.get("rounds")),
        _bridge_status_round_value(raw_status.get("total_rounds")),
    )
    documented_rounds = _same_wave_document_bridge_round_floor(
        repo_root,
        wave_id=str(handoff.get("wave_id") or ""),
        active_packet_path=active_packet_path,
        handoff=handoff,
    )
    effective_rounds = max(current_rounds, documented_rounds)
    if effective_rounds == 0 and not raw_status:
        return None
    refreshed = dict(raw_status)
    refreshed["rounds"] = effective_rounds
    refreshed["total_rounds"] = max(
        effective_rounds,
        _bridge_status_round_value(raw_status.get("total_rounds")),
    )
    return refreshed


def _persist_phase_b_handoff_for_commit_path(
    repo_root: Path,
    handoff: dict[str, Any],
) -> str | None:
    """Persist the Phase B handoff after commit-path rebinding.

    The commit executor may refresh the in-memory handoff from current staged
    truth before supervisor review. Keep the durable Phase B handoff in sync so
    retry/review surfaces do not read stale files_to_stage or receipt authority.
    """
    if str(handoff.get("caller") or "") != "phase_b":
        return None
    handoff_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "executors",
        "phase_b_handoff.json",
    )
    try:
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return f"failed to persist refreshed Phase B handoff at {handoff_path}: {exc}"
    return None


def _can_rekey_continuation_to_refreshed_handoff(handoff: dict[str, Any]) -> bool:
    """Return true when reruns read a refreshed handoff persisted by this executor."""
    return str(handoff.get("caller") or "") == "phase_b"


def _can_rekey_post_commit_continuation_to_handoff(
    handoff: dict[str, Any] | None,
    *,
    wave_id: str,
    target_branch: str,
) -> bool:
    """Allow Phase B handoff refreshes to resume an existing post-commit record."""
    if not isinstance(handoff, dict):
        return False
    if not _can_rekey_continuation_to_refreshed_handoff(handoff):
        return False
    if str(handoff.get("wave_id") or "").strip() != wave_id:
        return False
    handoff_target_branch = str(handoff.get("target_branch") or "").strip()
    if handoff_target_branch and handoff_target_branch != target_branch:
        return False
    tracked_packet = _normalize_repo_relpath(str(handoff.get("tracked_packet") or ""))
    if not tracked_packet.startswith("reports/control_plane/"):
        return False
    if wave_id not in Path(tracked_packet).name:
        return False
    return True


def _refresh_tasks_tracker_note_after_packet_truth(
    repo_root: Path,
    *,
    wave_id: str,
    tracker_note_text: str,
) -> str | None:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return None

    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None

    matching_tracker_indices = _matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_tracker_indices = [
        idx
        for idx in matching_tracker_indices
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    if len(canonical_tracker_indices) > 1:
        return (
            f"wave_id '{wave_id}' has {len(canonical_tracker_indices)} canonical "
            "tracker notes in TASKS.md during commit packet truth refresh"
        )
    if not canonical_tracker_indices:
        return None

    note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"
    canonical_idx = canonical_tracker_indices[0]
    if lines[canonical_idx] == note_line:
        return None
    if _should_preserve_structural_tracker_note_for_control_refresh(
        lines[canonical_idx],
        note_line,
    ):
        return None

    lines[canonical_idx] = note_line
    tasks_path.write_text("".join(lines), encoding="utf-8")
    try:
        _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        retry, detail = _git_index_lock_self_cleared_without_owner(repo_root, stderr)
        if not retry:
            return f"git add failed for refreshed TASKS.md tracker note ({detail}): {stderr}"
        try:
            _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
        except subprocess.CalledProcessError as retry_exc:
            return (
                "git add failed for refreshed TASKS.md tracker note after "
                f"self-cleared index.lock retry ({detail}): {retry_exc.stderr.strip()}"
            )
    return None


def refresh_tasks_tracker_note_after_packet_truth(
    repo_root: Path,
    *,
    wave_id: str,
    tracker_note_text: str,
) -> str | None:
    """Public seam for commit-packet truth refresh tests and callers."""
    return _refresh_tasks_tracker_note_after_packet_truth(
        repo_root,
        wave_id=wave_id,
        tracker_note_text=tracker_note_text,
    )


def _git_index_lock_candidates_from_diagnostic(repo_root: Path, diagnostic: str) -> list[Path]:
    """Return candidate index.lock paths mentioned by git diagnostics."""
    candidates: list[Path] = []

    def add(raw: str) -> None:
        text = raw.strip().strip("'\"`:,.;")
        if not text or "index.lock" not in text:
            return
        path = Path(text)
        if not path.is_absolute():
            path = repo_root / path
        resolved = path.resolve(strict=False)
        if resolved not in candidates:
            candidates.append(resolved)

    for match in re.finditer(r"['\"]([^'\"]*index\.lock)['\"]", diagnostic):
        add(match.group(1))
    for match in re.finditer(r"(?<!\S)(\S*index\.lock)(?!\S)", diagnostic):
        add(match.group(1))
    add(str(repo_root / ".git" / "index.lock"))
    return candidates


def _path_contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _looks_like_git_process(command: str) -> bool:
    if not command:
        return False
    argv0 = command.strip().split(None, 1)[0]
    base = Path(argv0).name
    return base == "git" or base.startswith("git-")


def _process_cwd(pid: int) -> tuple[Path | None, str | None]:
    proc_cwd = Path("/proc") / str(pid) / "cwd"
    if proc_cwd.exists():
        try:
            return proc_cwd.resolve(strict=True), None
        except FileNotFoundError:
            return None, None
        except OSError as exc:
            return None, str(exc)

    try:
        proc = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except FileNotFoundError:
        return None, "lsof unavailable"
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, str(exc)

    if proc.returncode != 0 and not proc.stdout:
        return None, None
    for line in proc.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            return Path(line[1:]).resolve(strict=False), None
    return None, None


def _git_owner_processes_for_repo(repo_root: Path) -> list[str]:
    """Return live git processes that appear to own the current repo."""
    repo = repo_root.resolve(strict=False)
    git_dir = (repo / ".git").resolve(strict=False)
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return [f"git owner process probe unavailable: {exc}"]
    if proc.returncode != 0:
        return [f"git owner process probe failed: {(proc.stderr or '').strip() or proc.returncode}"]

    owners: list[str] = []
    current_pid = os.getpid()
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        parts = text.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid == current_pid:
            continue
        command = parts[1]
        if not _looks_like_git_process(command):
            continue
        if str(repo) in command or str(git_dir) in command:
            owners.append(f"pid={pid} command={command[:180]}")
            continue
        cwd, cwd_error = _process_cwd(pid)
        if cwd is not None:
            cwd = cwd.resolve(strict=False)
            if _path_contains(repo, cwd):
                owners.append(f"pid={pid} cwd={cwd} command={command[:180]}")
            continue
        if cwd_error:
            owners.append(f"pid={pid} cwd_probe_error={cwd_error} command={command[:180]}")
    return owners


def _git_index_lock_self_cleared_without_owner(
    repo_root: Path,
    diagnostic: str,
) -> tuple[bool, str]:
    """Classify git index.lock failures without touching .git internals.

    Git's index writer owns the lock by keeping index.lock present. Retry is
    allowed only when the failure named index.lock and every candidate lock path
    has already disappeared before recovery code runs.
    """
    if "index.lock" not in diagnostic:
        return False, "git add failure did not name index.lock"

    candidates = _git_index_lock_candidates_from_diagnostic(repo_root, diagnostic)
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        return (
            False,
            "index.lock still exists or an active git owner remains: "
            + ", ".join(existing),
        )
    owners = _git_owner_processes_for_repo(repo_root)
    if owners:
        return (
            False,
            "index.lock self-cleared but active git owner remains: "
            + "; ".join(owners[:3]),
        )
    return True, "index.lock self-cleared before retry; no lock owner remained"


def _run_git_commit_with_self_cleared_index_lock_retry(
    repo_root: Path,
    commit_message: str,
    *,
    env: dict[str, str],
) -> tuple[subprocess.CompletedProcess[str], str | None]:
    """Run git commit, retrying once only when index.lock already self-cleared."""
    cmd = ["git", "commit", "-m", commit_message]
    try:
        return _run(cmd, cwd=repo_root, timeout=60, env=env), None
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        retry, detail = _git_index_lock_self_cleared_without_owner(repo_root, stderr)
        if not retry:
            raise
        try:
            return _run(cmd, cwd=repo_root, timeout=60, env=env), detail
        except subprocess.CalledProcessError as retry_exc:
            retry_stderr = retry_exc.stderr.strip()
            augmented_stderr = (
                f"{retry_stderr} "
                f"(after self-cleared index.lock retry: {detail})"
            ).strip()
            raise subprocess.CalledProcessError(
                retry_exc.returncode,
                retry_exc.cmd,
                output=retry_exc.output,
                stderr=augmented_stderr,
            ) from retry_exc


def refresh_commit_path_packet_truth(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    indicator_path: str,
    commit_status: str,
    commit_generated_governance_paths: list[str] | None = None,
    commit_generated_governance_provenance: str = "",
) -> tuple[dict[str, Any], list[str], str | None]:
    """Refresh the wave packet from current commit-path facts before supervisor review."""
    wave_id = str(handoff.get("wave_id") or "")
    settled_generated_provenance = ""
    if commit_generated_governance_paths:
        settled_generated_provenance, generated_provenance_error = (
            _validate_commit_generated_governance_provenance(
                commit_generated_governance_provenance
            )
        )
        if generated_provenance_error:
            return handoff, [], generated_provenance_error
    settled_generated_paths, generated_path_error = _validate_commit_generated_governance_paths(
        repo_root,
        commit_generated_governance_paths or [],
        provenance=settled_generated_provenance,
        wave_id=wave_id,
    )
    if generated_path_error:
        return handoff, [], generated_path_error
    active_packet_path, packet_error = _commit_refresh_packet_path(handoff)
    if packet_error:
        return handoff, [], packet_error
    if not active_packet_path:
        if settled_generated_paths:
            return handoff, [], (
                "commit-generated governance settlement requires an active "
                "tracked_packet before supervisor"
            )
        return handoff, _current_staged_diff_paths(repo_root), None

    handoff_wave_class = str(handoff.get("wave_class") or "").strip()
    if settled_generated_paths:
        if not _wave_class_allows_founder_override(handoff_wave_class):
            return handoff, [], (
                "commit-generated governance settlement requires an L4_ENABLER "
                "or MAINTENANCE handoff before supervisor"
            )
    elif handoff_wave_class != "L4_ENABLER":
        return handoff, _current_staged_diff_paths(repo_root), None

    tracker_note_text = str(handoff.get("tracker_note_text") or "")
    if not tracker_note_text.strip():
        return handoff, [], "tracker_note_text is required for commit packet truth refresh"
    if not indicator_path:
        return handoff, [], "indicator_path is required for commit packet truth refresh"

    packet_full = (repo_root / active_packet_path).resolve()
    repo_resolved = repo_root.resolve()
    if repo_resolved not in packet_full.parents:
        return handoff, [], f"active packet escapes repo root: {active_packet_path}"
    if not packet_full.exists():
        return handoff, [], f"active packet not found for commit packet truth refresh: {active_packet_path}"
    packet_text = packet_full.read_text(encoding="utf-8")
    original_packet_text = packet_text
    if not _packet_declares_same_wave_id(packet_text, normalize_wave_id(wave_id)):
        return handoff, [], (
            "active packet missing matching Wave ID for commit packet truth refresh: "
            f"{active_packet_path} (wave_id={wave_id})"
        )

    preserved_evidence_command: str | None = None
    if handoff_wave_class == "L4_ENABLER":
        preserved_evidence_command, explicit_evidence_error = (
            _resolve_explicit_l4_enabler_evidence_command(
                repo_root=repo_root,
                handoff=handoff,
                packet_text=packet_text,
                active_packet_path=active_packet_path,
            )
        )
        if explicit_evidence_error:
            return handoff, [], explicit_evidence_error

    staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
    if indicator_path not in staged_paths_before:
        return handoff, [], (
            "indicator artifact is not staged before commit packet truth refresh: "
            f"{indicator_path}"
        )
    staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    effective_bridge_status = _effective_commit_bridge_status(
        repo_root=repo_root,
        handoff=handoff,
        active_packet_path=active_packet_path,
    )
    refreshed_tracker_note_text = _refresh_tracker_note_wave_file_count(
        tracker_note_text,
        len(staged_paths_for_block),
    )
    refreshed_tracker_note_text = _refresh_tracker_note_bridge_rounds(
        refreshed_tracker_note_text,
        effective_bridge_status,
    )
    refreshed_tracker_note_text = _refresh_tracker_note_test_evidence(
        refreshed_tracker_note_text,
        staged_paths_for_block,
        preserved_evidence_command=preserved_evidence_command,
    )
    pending_pre_commit_supervisor = commit_status == "pre_commit_supervisor_pending"
    if pending_pre_commit_supervisor:
        if preserved_evidence_command is not None:
            refreshed_tracker_note_text = _replace_tracker_note_evidence_command_exact(
                refreshed_tracker_note_text,
                _PRESERVED_EVIDENCE_COMMAND_PLACEHOLDER,
            )
        refreshed_tracker_note_text = _mark_tracker_note_pre_commit_receipt_pending(
            refreshed_tracker_note_text
        )
        if preserved_evidence_command is not None:
            refreshed_tracker_note_text = _replace_tracker_note_evidence_command_exact(
                refreshed_tracker_note_text,
                preserved_evidence_command,
            )
    tracker_refresh_error = _refresh_tasks_tracker_note_after_packet_truth(
        repo_root,
        wave_id=wave_id,
        tracker_note_text=refreshed_tracker_note_text,
    )
    if tracker_refresh_error:
        return handoff, [], tracker_refresh_error
    # TASKS.md may have been staged by the tracker refresh; render from
    # the settled scope.
    staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
    staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    tracker_note_after_staging = _refresh_tracker_note_wave_file_count(
        refreshed_tracker_note_text,
        len(staged_paths_for_block),
    )
    tracker_note_after_staging = _refresh_tracker_note_bridge_rounds(
        tracker_note_after_staging,
        effective_bridge_status,
    )
    tracker_note_after_staging = _refresh_tracker_note_test_evidence(
        tracker_note_after_staging,
        staged_paths_for_block,
        preserved_evidence_command=preserved_evidence_command,
    )
    if preserved_evidence_command is not None:
        tracker_note_after_staging = _replace_tracker_note_evidence_command_exact(
            tracker_note_after_staging,
            _PRESERVED_EVIDENCE_COMMAND_PLACEHOLDER,
        )
    tracker_note_after_staging = _append_tracker_scope_refs(
        tracker_note_after_staging,
        settled_generated_paths,
    )
    if pending_pre_commit_supervisor:
        tracker_note_after_staging = _mark_tracker_note_pre_commit_receipt_pending(
            tracker_note_after_staging
        )
    if preserved_evidence_command is not None:
        tracker_note_after_staging = _replace_tracker_note_evidence_command_exact(
            tracker_note_after_staging,
            preserved_evidence_command,
        )
    if tracker_note_after_staging != refreshed_tracker_note_text:
        refreshed_tracker_note_text = tracker_note_after_staging
        tracker_refresh_error = _refresh_tasks_tracker_note_after_packet_truth(
            repo_root,
            wave_id=wave_id,
            tracker_note_text=refreshed_tracker_note_text,
        )
        if tracker_refresh_error:
            return handoff, [], tracker_refresh_error
        staged_paths_before = sorted(_current_staged_diff_paths(repo_root))
        staged_paths_for_block = sorted(_dedupe_repo_paths([*staged_paths_before, active_packet_path]))
    if refreshed_tracker_note_text != tracker_note_text:
        handoff = {**handoff, "tracker_note_text": refreshed_tracker_note_text}
        tracker_note_text = refreshed_tracker_note_text
    evidence_handles = _commit_refresh_evidence_handles(
        handoff,
        indicator_path=indicator_path,
        include_pre_commit_receipt=not pending_pre_commit_supervisor,
    )
    if settled_generated_paths:
        evidence_handles[COMMIT_GENERATED_GOVERNANCE_EVIDENCE_KEY] = ", ".join(
            settled_generated_paths
        )
    block = _render_commit_path_truth_refresh_block(
        wave_id=wave_id,
        active_packet_path=active_packet_path,
        tracker_note_text=tracker_note_text,
        staged_paths=staged_paths_for_block,
        indicator_path=indicator_path,
        commit_status=commit_status,
        evidence_handles=evidence_handles,
        pre_commit_receipt_path=(
            ""
            if pending_pre_commit_supervisor
            else str(handoff.get("pre_commit_receipt_path") or "")
        ),
        commit_generated_governance_paths=settled_generated_paths,
    )
    try:
        raw_deferred_path_candidates = [
            *staged_paths_for_block,
            *(
                list(handoff.get("deferred_items"))
                if isinstance(handoff.get("deferred_items"), list)
                else []
            ),
        ]
        # Commit contents come from the staged index; worktree presence can
        # drift after a deferred packet has already been staged.
        deferred_path_candidates = [
            path
            for path in _dedupe_repo_paths(raw_deferred_path_candidates)
            if not path.startswith("reports/deferred/non_blocking/")
            or _git_index_contains_repo_path(repo_root, path)
        ]
        packet_text = _refresh_same_wave_deferred_packet_authorization(
            packet_text,
            wave_id=wave_id,
            deferred_paths=deferred_path_candidates,
        )
        packet_text = _refresh_commit_generated_governance_authorization(
            packet_text,
            wave_id=wave_id,
            paths=settled_generated_paths,
            provenance=settled_generated_provenance,
        )
        # Single-source the packet's L4-field block from the canonical tracker
        # note (the #52 supervisor + bot read the note as truth). The settled
        # tracker_note_text wins on any divergence, establishing the invariant
        # "at supervisor time, packet L4-fields == tracker note L4-fields".
        packet_text = reconcile_packet_l4_fields_block(
            packet_text,
            tracker_note_text,
            exact_evidence_command=preserved_evidence_command,
        )
        refreshed_text = _replace_commit_path_truth_refresh_block(packet_text, block)
    except ValueError as exc:
        return handoff, [], str(exc)
    packet_changed = refreshed_text != original_packet_text
    if packet_changed:
        packet_full.write_text(refreshed_text, encoding="utf-8")
    try:
        _run(["git", "add", "--", active_packet_path], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        return handoff, [], f"git add failed for refreshed packet {active_packet_path}: {exc.stderr.strip()}"

    final_staged_paths = sorted(_current_staged_diff_paths(repo_root))
    if not final_staged_paths:
        return handoff, [], "staged file set empty after commit packet truth refresh"
    if packet_changed and active_packet_path not in final_staged_paths:
        return handoff, [], f"refreshed packet is not staged: {active_packet_path}"
    if indicator_path not in final_staged_paths:
        return handoff, [], f"indicator artifact is not staged after commit packet truth refresh: {indicator_path}"

    refreshed_handoff, errors = _rebuild_handoff_after_packet_truth_refresh(
        handoff,
        repo_root=repo_root,
        active_packet_path=active_packet_path,
        staged_paths=final_staged_paths,
        evidence_handles=evidence_handles,
        commit_generated_governance_paths=settled_generated_paths,
        preserved_evidence_command=preserved_evidence_command,
    )
    if errors:
        return handoff, [], "rebuilt commit handoff invalid after packet truth refresh: " + "; ".join(errors)
    return refreshed_handoff, final_staged_paths, None


def _emit_commit_ready_event(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
    receipt_path_from_supervisor: str,
    receipt_decision: str,
    handoff_receipt_rel: str,
) -> dict[str, Any]:
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type="commit_ready",
        # normalize_wave_id keeps emission resilient if a handoff lacks a wave_id now
        # that the pager defaults ON: normalize_wave_id("") -> "wave-unknown" instead of
        # raising PipelineAgentPagerError. Consistent with recovery_gate._emit_recovery_event.
        wave_id=normalize_wave_id(str(handoff.get("wave_id") or "").strip()),
        task_id=str(handoff.get("task_id") or "[COMMIT-EXECUTOR]").strip(),
        plan_path=_handoff_plan_path(handoff),
        phase="commit_executor",
        state="commit_ready",
        transition_key=receipt_path_from_supervisor,
        summary=f"Commit path reached {receipt_decision}",
        reason=f"Commit-ready receipt validated at {receipt_path_from_supervisor}",
        artifact_paths={
            "supervisor_receipt": receipt_path_from_supervisor,
            "handoff_receipt": handoff_receipt_rel,
        },
        route=_handoff_pager_route(handoff),
    )


def _emit_commit_lifecycle_event(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
    event_type: str,
    state: str,
    transition_key: str,
    summary: str,
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type=event_type,
        # normalize_wave_id keeps emission resilient if a handoff lacks a wave_id now
        # that the pager defaults ON: normalize_wave_id("") -> "wave-unknown" instead of
        # raising PipelineAgentPagerError. Consistent with recovery_gate._emit_recovery_event.
        wave_id=normalize_wave_id(str(handoff.get("wave_id") or "").strip()),
        task_id=str(handoff.get("task_id") or "[COMMIT-EXECUTOR]").strip(),
        plan_path=_handoff_plan_path(handoff),
        phase="commit_executor",
        state=state,
        transition_key=transition_key,
        summary=summary,
        reason=summary,
        artifact_paths=artifact_paths,
        route=_handoff_pager_route(handoff),
    )


def _handoff_pager_route(handoff: dict[str, Any]) -> str | None:
    route = str(handoff.get("pager_route") or "").strip()
    return route or None


def _emit_pre_commit_supervisor_lifecycle_event(
    repo_root: Path,
    package_path: Path,
    *,
    event_type: str,
    state: str,
    decision: str = "pending",
    summary: str | None = None,
    route: str | None = None,
) -> dict[str, Any]:
    """Emit the structured pre-commit supervisor lifecycle from package facts."""
    package: dict[str, Any] = {}
    try:
        loaded = json.loads(package_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            package = loaded
    except (json.JSONDecodeError, OSError):
        package = {}

    try:
        rel_package = str(package_path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        rel_package = str(package_path)

    try:
        package_digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
    except OSError:
        package_digest = package_path.name

    wave_id = normalize_wave_id(str(package.get("wave_name") or package_path.stem))
    task_id = str(package.get("task_id") or "[PRE-COMMIT-SUPERVISOR]").strip()
    event_summary = summary or (
        f"Pre-commit supervisor {state}"
        if decision == "pending"
        else f"Pre-commit supervisor {state}: {decision}"
    )
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type=event_type,
        wave_id=wave_id,
        task_id=task_id,
        plan_path=rel_package,
        phase="pre_commit_supervisor",
        state=state,
        transition_key=f"pre-commit-supervisor:{package_digest}:{state}:{decision}",
        summary=event_summary,
        reason=event_summary,
        artifact_paths={"package": rel_package},
        route=str(route or package.get("pager_route") or "").strip() or None,
    )


def _safe_emit_pre_commit_supervisor_lifecycle_event(
    repo_root: Path,
    package_path: Path,
    *,
    event_type: str,
    state: str,
    decision: str = "pending",
    summary: str | None = None,
    route: str | None = None,
) -> dict[str, Any]:
    try:
        return _emit_pre_commit_supervisor_lifecycle_event(
            repo_root,
            package_path,
            event_type=event_type,
            state=state,
            decision=decision,
            summary=summary,
            route=route,
        )
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


def _commit_outcome_event_type(status: str) -> str:
    if status == "success":
        return "commit_succeeded"
    if status == "held":
        return "commit_held"
    return "commit_failed"


def _commit_lifecycle_pager_enabled(repo_root: Path) -> bool:
    try:
        config = load_executor_config(repo_root)
    except Exception:
        return False
    return bool(config.get("pipeline_agent_pager", {}).get("enabled", False))


class _BotRemediationTargetConfigError(RuntimeError):
    pass


def _nonempty_config_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _strict_target_bot_remediation_adapter(repo_root: Path) -> str:
    """Resolve Step-15 bot remediation authority from the target worktree only."""
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    if not config_path.exists():
        raise _BotRemediationTargetConfigError(
            f"target executor config missing: {config_path}"
        )
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _BotRemediationTargetConfigError(
            f"target executor config is not valid JSON: {exc}"
        ) from exc
    if not isinstance(raw_config, dict):
        raise _BotRemediationTargetConfigError(
            "target executor config must be a JSON object"
        )
    raw_backends = raw_config.get("backends")
    if not isinstance(raw_backends, dict):
        raise _BotRemediationTargetConfigError(
            "target executor config missing object backends"
        )
    committed_adapter = _nonempty_config_string(raw_backends.get("bot_remediation"))
    if committed_adapter is None:
        raise _BotRemediationTargetConfigError(
            "target executor config missing non-empty string backends.bot_remediation"
        )

    # Only after the target file has proved its existence and shape may Step 15
    # ask the shared loader to materialize target-scoped role env overrides.
    materialized = load_executor_config(repo_root)
    scoped_env_overrides_apply = materialized.get(
        ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY,
        True,
    )
    implementer_env_override_present = any(
        _nonempty_config_string(os.environ.get(env_name)) is not None
        for env_name in ROLE_AGENT_ENV_VARS.get("implementer", ())
    )
    if scoped_env_overrides_apply and implementer_env_override_present:
        materialized_backends = materialized.get("backends")
        if not isinstance(materialized_backends, dict):
            raise _BotRemediationTargetConfigError(
                "materialized target executor config missing object backends"
            )
        materialized_adapter = _nonempty_config_string(
            materialized_backends.get("bot_remediation")
        )
        if materialized_adapter is None:
            raise _BotRemediationTargetConfigError(
                "materialized target executor config missing non-empty string "
                "backends.bot_remediation"
            )
        return materialized_adapter

    return committed_adapter


def _run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess with sanitized env."""
    run_env = env
    if run_env is None:
        run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=check,
        timeout=timeout, env=run_env, input=input_text,
    )


def _commit_subprocess_env(*, skip_receipt_check: bool = False) -> dict[str, str] | None:
    """Build subprocess env for commit hooks while preserving active bus authority."""
    active_bus_dir = _active_bus_dir()
    if active_bus_dir is None and not skip_receipt_check:
        return None
    run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    if active_bus_dir is not None:
        run_env["RCX_AGENT_BUS_DIR"] = str(active_bus_dir)
    if skip_receipt_check:
        run_env["RCX_SKIP_RECEIPT_CHECK"] = "1"
    return run_env


# Canonical env var that overrides the pipeline agent pager route. Defined here as
# a literal for parity with the dispatcher launcher
# (launch_wave._PAGER_ROUTE_OVERRIDE_ENV); the canonical source is
# pipeline_agent_pager.PAGER_ROUTE_OVERRIDE_ENV. Kept a literal so commit_executor
# does not import the observability layer just to name one key.
_PAGER_ROUTE_OVERRIDE_ENV = "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE"


def _commit_validation_protected_env_keys() -> frozenset[str]:
    """Env keys a commit-owned validation child must never inherit or be handed.

    These are the live pipeline lane bus, every invocation-owned role/pager
    routing override, and the exact bridge-turn recovery-timeout override/key
    pair the dispatcher resolves from the environment. Validation children run
    the repository's OWN test suite, which mints its own temporary ``.agent_bus``
    and asserts DEFAULT role/pager routing; inheriting live control state can
    make those hermetic tests resolve pipeline-owned state instead of their
    fixtures (reproduced by
    ``test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus``, which
    fails when ``RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE=codex`` leaks in).

    The role keys are read from the SAME canonical role configuration the
    dispatcher launcher uses (``ROLE_AGENT_ENV_VARS`` + the repo-root guard
    ``ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV``), read at call time so a later
    independent role (e.g. a supervisor) added to that config is sanitized here
    automatically -- the leak cannot silently reopen. ``RCX_SKIP_*`` is handled by
    prefix in ``_commit_validation_env`` rather than enumerated here.
    """
    keys = {
        "RCX_AGENT_BUS_DIR",
        "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY",
        "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE",
        ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV,
        _PAGER_ROUTE_OVERRIDE_ENV,
    }
    for env_names in ROLE_AGENT_ENV_VARS.values():
        keys.update(env_names)
    return frozenset(keys)


def _commit_validation_env(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the environment for commit-owned validation children (pre-push-fast).

    Validation children run the repository's OWN test suite, and those tests
    create their own temporary ``.agent_bus`` authority and assert default role
    and pager routing. They MUST NOT inherit -- or be handed -- the live pipeline
    lane (``RCX_AGENT_BUS_DIR``), any invocation-owned role/pager override, or
    the bridge-turn recovery-timeout override/key pair: a namespaced live lane
    (e.g. ``.agent_bus-fix37``) would override the temporary repository bus, and
    a live ``RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE`` would override the
    temporary repository's pager config
    (``test_pager_persists_event_delivery_state_and_lock_in_namespaced_bus`` --
    the pipeline-fix-37b Step 11 failure that pipeline-fix-37b's bus-only strip
    did not close).

    Every other parent variable (PATH, credentials, locale, pytest pins,
    unrelated recovery state such as ``RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY``,
    and any unrelated var) is preserved byte-for-byte. ``RCX_SKIP_*`` is stripped
    for parity with the ``_run`` default env, and ``os.environ`` is never mutated.

    Caller ``overrides`` (e.g. the pytest determinism pins) are applied BEFORE the
    protected keys are removed, so that neither a malicious parent env nor a
    caller override can route a commit-owned validation child at the live lane bus
    or a live role/pager override.

    This is deliberately distinct from ``_commit_subprocess_env`` (commit / amend
    hooks), which MUST retain the active lane ``RCX_AGENT_BUS_DIR`` so the
    pre-commit hook resolves the same lane bus the receipt was minted to. Live
    commit, hook, adapter, pager, supervisor, push, merge, and recovery children
    keep their invocation authority; only validation children are sanitized.
    """
    run_env = {k: v for k, v in os.environ.items() if not k.startswith("RCX_SKIP_")}
    if overrides:
        run_env.update(overrides)
    # Remove protected keys AFTER overrides so a caller cannot re-inject them.
    for key in _commit_validation_protected_env_keys():
        run_env.pop(key, None)
    # Final RCX_SKIP_* sweep: a caller override could otherwise re-add a skip key.
    for key in [k for k in run_env if k.startswith("RCX_SKIP_")]:
        run_env.pop(key, None)
    return run_env


def _tail_failure_excerpt(text: str, *, limit: int = 1000, max_lines: int = 20) -> str:
    """Keep the actionable tail of noisy hook output."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    lines = [line for line in cleaned.splitlines() if line.strip()]
    tail = "\n".join(lines[-max_lines:]).strip() if lines else cleaned
    if len(tail) <= limit:
        return tail
    return tail[-limit:]


def _is_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized.startswith("mu/tests/")
        or normalized.startswith("tests/")
        or "/test_" in normalized
        or normalized.endswith("_test.py")
    )


_RUNTIME_TARGETED_TESTS = {
    "mu/host/js/core/bootstrap_core.js": (
        "tests/l4_gates/test_bootstrap_core_carveout_gate.py",
    ),
    "mu/tools/executors/commit_executor.py": (
        "mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate",
    ),
    "mu/tests/tools/test_commit_executor_receipt.py": (
        "mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate",
    ),
    "mu/tools/executors/phase_b_executor.py": (
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_skips_missing_targeted_executor_tests",
    ),
    "mu/tests/tools/test_phase_b_executor.py": (
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_skips_missing_targeted_executor_tests",
    ),
}

_PYTEST_DIFF_SELECTOR_HINTS = {
    "mu/tests/parity/test_js_parity_automated.py": (
        (
            ("_MAX_STEPS_GUARDED_ACTIONS", "_GUARDED_ACTION_BASE_ARGS"),
            (
                "maxEngineIterations",
                "Engine actions use one outer iteration",
                "API cap validation",
                "deeper engine convergence",
                "parity coverage with small structural budgets below",
                "Base args for each guarded action",
                "API guard acceptance/rejection",
                "full engine convergence behavior",
            ),
            ("mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard",),
        ),
    ),
}


def _pytest_selector_path(selector: str) -> str:
    return selector.split("::", 1)[0]


def _canonical_repo_test_path(repo_root: Path, path: str) -> str:
    """Canonicalize repo-relative test paths so symlink mirrors dedupe cleanly."""
    normalized = path.replace("\\", "/")
    try:
        resolved = (repo_root / normalized).resolve(strict=False)
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return normalized


def _canonical_repo_test_selector(repo_root: Path, selector: str) -> str:
    path, separator, suffix = selector.partition("::")
    canonical_path = _canonical_repo_test_path(repo_root, path)
    if not separator:
        return canonical_path
    return f"{canonical_path}{separator}{suffix}"


def _pytest_gate_diff_text(repo_root: Path, path: str) -> str:
    diff_parts: list[str] = []
    for args in (
        ("git", "diff", "--cached", "--", path),
        ("git", "diff", "--", path),
    ):
        result = subprocess.run(
            args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            diff_parts.append(result.stdout)
    return "\n".join(diff_parts)


def _changed_diff_hunks(diff_text: str) -> list[str]:
    hunks: list[str] = []
    current_hunk: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("@@ "):
            if current_hunk:
                hunks.append("\n".join(current_hunk))
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)
    if current_hunk:
        hunks.append("\n".join(current_hunk))
    return [
        hunk
        for hunk in hunks
        if any(
            (line.startswith("+") and not line.startswith("+++"))
            or (line.startswith("-") and not line.startswith("---"))
            for line in hunk.splitlines()
        )
    ]


def _changed_diff_lines(hunk: str) -> list[str]:
    return [
        line[1:].strip()
        for line in hunk.splitlines()
        if (
            (line.startswith("+") and not line.startswith("+++"))
            or (line.startswith("-") and not line.startswith("---"))
        )
    ]


def _diff_hunks_match_only_markers(
    diff_text: str,
    hunk_markers: tuple[str, ...],
    changed_line_markers: tuple[str, ...],
) -> bool:
    changed_hunks = _changed_diff_hunks(diff_text)
    if not changed_hunks:
        return False
    if not all(any(marker in hunk for marker in hunk_markers) for hunk in changed_hunks):
        return False
    effective_changed_line_markers = changed_line_markers or hunk_markers
    return all(
        any(marker in changed_line for marker in effective_changed_line_markers)
        for hunk in changed_hunks
        for changed_line in _changed_diff_lines(hunk)
    )


def _pytest_selector_hints_for_diff(path: str, diff_text: str) -> list[str]:
    selectors: list[str] = []
    for hunk_markers, changed_line_markers, hinted_selectors in _PYTEST_DIFF_SELECTOR_HINTS.get(path, ()):
        if _diff_hunks_match_only_markers(diff_text, hunk_markers, changed_line_markers):
            selectors.extend(hinted_selectors)
    return selectors


def _runtime_targeted_tests_for_path(repo_root: Path, path: str) -> tuple[str, ...]:
    candidates = _RUNTIME_TARGETED_TESTS.get(path, ())
    return tuple(
        selector
        for selector in candidates
        if (repo_root / _pytest_selector_path(selector)).exists()
    )


def _collect_commit_test_files(repo_root: Path, staged_files: list[str]) -> list[str]:
    """Collect staged test files and mirrored test files for staged Python code."""
    candidates: set[str] = set()
    for path in staged_files:
        normalized = path.replace("\\", "/")
        if _is_test_file(normalized) and normalized.endswith(".py"):
            selector_hints = _pytest_selector_hints_for_diff(
                normalized,
                _pytest_gate_diff_text(repo_root, normalized),
            )
            if selector_hints:
                candidates.update(
                    _canonical_repo_test_selector(repo_root, selector)
                    for selector in selector_hints
                    if (repo_root / _pytest_selector_path(selector)).exists()
                )
            else:
                candidates.add(_canonical_repo_test_path(repo_root, normalized))
            continue
        targeted_tests = _runtime_targeted_tests_for_path(repo_root, normalized)
        for test_path in targeted_tests:
            candidates.add(_canonical_repo_test_selector(repo_root, test_path))
        if targeted_tests:
            continue
        if not normalized.endswith(".py"):
            continue
        stem = Path(normalized).stem
        for test_root in ("mu/tests", "tests"):
            root_path = repo_root / test_root
            if not root_path.is_dir():
                continue
            for match in root_path.rglob(f"test_{stem}*.py"):
                if match.is_file():
                    candidates.add(
                        _canonical_repo_test_path(
                            repo_root,
                            match.relative_to(repo_root).as_posix(),
                        )
                    )
    return sorted(candidates)


def _collect_private_attr_gate_files(repo_root: Path, staged_files: list[str]) -> list[str]:
    """Return staged Python test files that should trigger the private-attr gate."""
    candidates: set[str] = set()
    for path in staged_files:
        normalized = path.replace("\\", "/")
        if _is_test_file(normalized) and normalized.endswith(".py"):
            candidates.add(_canonical_repo_test_path(repo_root, normalized))
    return sorted(candidates)


def _resolve_private_attr_checker(repo_root: Path) -> Path | None:
    """Resolve the tracked private-attr checker from repo or executor paths."""
    candidates = [
        repo_root / "mu" / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        repo_root / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        SCRIPT_DIR.parents[1] / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        SCRIPT_DIR.parents[2] / "tools" / "checks" / "linters" / "check_private_attr_access.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _resolve_underscore_import_checker(repo_root: Path) -> Path | None:
    """Resolve the tracked test underscored-import checker."""
    candidates = [
        repo_root / "mu" / "tools" / "checks" / "linters" / "check_underscore_imports.py",
        repo_root / "tools" / "checks" / "linters" / "check_underscore_imports.py",
        SCRIPT_DIR.parents[1] / "tools" / "checks" / "linters" / "check_underscore_imports.py",
        SCRIPT_DIR.parents[2] / "tools" / "checks" / "linters" / "check_underscore_imports.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_private_attr_test_gate(
    repo_root: Path,
    staged_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run test anti-cheat checkers when staged Python tests changed."""
    gate_files = _collect_private_attr_gate_files(repo_root, staged_files)
    if not gate_files:
        return {
            "passed": True,
            "skipped": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [],
        }
    checker_specs = [
        ("private-attr checker", _resolve_private_attr_checker(repo_root)),
        ("underscored-import checker", _resolve_underscore_import_checker(repo_root)),
    ]
    missing = [name for name, checker in checker_specs if checker is None]
    if missing:
        return {
            "passed": False,
            "skipped": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{', '.join(missing)} not found",
            "test_files": gate_files,
        }
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    exit_code = 0
    try:
        for checker_name, checker in checker_specs:
            assert checker is not None
            completed = subprocess.run(
                [sys.executable, str(checker), str(repo_root), *gate_files],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                # Commit-owned validation child: strip live invocation state
                # through the same boundary used by the other validation gates.
                env=_commit_validation_env(),
            )
            if completed.stdout:
                stdout_parts.append(completed.stdout)
            if completed.stderr:
                stderr_parts.append(completed.stderr)
            if completed.returncode != 0 and exit_code == 0:
                exit_code = completed.returncode
        return {
            "passed": exit_code == 0,
            "skipped": False,
            "exit_code": exit_code,
            "stdout": "\n".join(part.rstrip("\n") for part in stdout_parts),
            "stderr": "\n".join(part.rstrip("\n") for part in stderr_parts),
            "test_files": gate_files,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "skipped": False,
            "exit_code": -1,
            "stdout": "\n".join(part.rstrip("\n") for part in stdout_parts),
            "stderr": f"test anti-cheat checker timed out after {timeout}s",
            "test_files": gate_files,
        }


def _private_attr_gate_error(gate_result: dict[str, Any]) -> str:
    detail = _tail_failure_excerpt(
        "\n".join(
            part
            for part in (
                str(gate_result.get("stdout") or ""),
                str(gate_result.get("stderr") or ""),
            )
            if part
        ),
        limit=1500,
        max_lines=30,
    )
    test_files = gate_result.get("test_files") or []
    file_summary = ", ".join(str(path) for path in test_files[:8])
    if len(test_files) > 8:
        file_summary += f", ... (+{len(test_files) - 8} more)"
    message = (
        "private-attr test-integrity gate failed before local commit creation "
        f"(exit={gate_result.get('exit_code')})"
    )
    if file_summary:
        message += f" for staged test file(s): {file_summary}"
    if detail:
        message += f": {detail}"
    return message


def _run_pytest_on_files(
    repo_root: Path,
    test_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run pytest on specific test files. Returns exit_code and output."""
    if not test_files:
        return {"exit_code": 0, "stdout": "", "stderr": "", "passed": True}
    # Control-plane executor tests are integration-heavy. The real 2-file gate
    # for `test_phase_b_executor.py test_recovery_gate.py` took 198.857s on
    # 2026-04-21, and the same commit gate exhausted the old 300s budget on
    # 2026-05-05. Keep enough slack that the gate fails on test truth, not an
    # undersized commit-executor budget.
    effective_timeout = max(timeout, 240 * len(test_files))
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-x",
                "--tb=short",
                "--import-mode=importlib",
                "-m",
                "not slow and not fuzzer",
                *test_files,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=effective_timeout,
            # Validation child: build the env through the commit-owned validation
            # constructor so the live pipeline lane bus and every invocation-owned
            # role/pager override are dropped (AFTER the pytest determinism pins
            # are applied) and the repository's own tests resolve their temporary
            # .agent_bus and default routing instead of the live pipeline lane.
            # This helper backs the Step 8b pre-commit targeted pytest gate and
            # the Step 15 bot-remediation targeted pytest gate -- both commit-owned
            # validation children reproduced leaking a namespaced live lane and a
            # live pager route override.
            env=_commit_validation_env(
                {
                    "PYTHONHASHSEED": "0",
                    "RCX_CI": "1",
                    "HYPOTHESIS_PROFILE": "ci_fast",
                }
            ),
        )
        passed = result.returncode == 0 or _pytest_only_deselected_by_marker_filter(
            result.returncode,
            result.stdout,
            result.stderr,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": passed,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"pytest timed out after {effective_timeout}s",
            "passed": False,
        }


def _pytest_only_deselected_by_marker_filter(returncode: int, stdout: str, stderr: str) -> bool:
    """Return True when the fast-shard marker filter selected no tests by design."""
    if returncode != 5 or stderr.strip():
        return False
    return "0 selected" in stdout and "deselected" in stdout


def _run_bot_remediation_staged_test_gate(
    repo_root: Path,
    *,
    log: Any = None,
) -> dict[str, Any]:
    """Validate staged test changes before creating a bot-remediation commit."""
    try:
        staged_files = _run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            timeout=30,
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError as exc:
        detail = _tail_failure_excerpt(exc.stderr or exc.stdout or "", limit=1000)
        return {
            "passed": False,
            "errors": [f"bot-remediation staged-file discovery failed: {detail or exc}"],
            "staged_files": [],
            "test_files": [],
        }

    test_files = _collect_commit_test_files(repo_root, staged_files)
    result: dict[str, Any] = {
        "passed": True,
        "errors": [],
        "staged_files": staged_files,
        "test_files": test_files,
    }

    if test_files:
        if log is not None:
            log(
                "Step 15: running bot-remediation pytest gate on "
                f"{len(test_files)} affected test file(s)"
            )
        pytest_result = _run_pytest_on_files(repo_root, test_files)
        result["pytest_gate"] = pytest_result
        if not pytest_result["passed"]:
            stderr = (pytest_result.get("stderr") or "").strip()
            stdout = (pytest_result.get("stdout") or "").strip()
            failure_detail = _tail_failure_excerpt(
                stderr if stderr else stdout,
                limit=1500,
                max_lines=30,
            )
            result["passed"] = False
            result["errors"] = [
                "bot-remediation targeted pytest gate failed before local "
                f"remediation commit (exit={pytest_result['exit_code']}): "
                f"{failure_detail}"
            ]
            return result

    private_attr_gate = run_private_attr_test_gate(repo_root, staged_files)
    result["private_attr_gate"] = private_attr_gate
    if not private_attr_gate["passed"]:
        result["passed"] = False
        result["errors"] = [_private_attr_gate_error(private_attr_gate)]
        return result
    if log is not None and not private_attr_gate.get("skipped"):
        log(
            "Step 15: bot-remediation private-attr/import gate passed for "
            f"{len(private_attr_gate.get('test_files') or [])} staged test file(s)"
        )
    return result


def _run_bot_remediation_pre_push_guard(
    repo_root: Path,
    *,
    log: Any = None,
) -> dict[str, Any]:
    """Run the local pre-push gate for the newly created remediation head."""
    pre_push_script = repo_root / "mu" / "tools" / "hooks" / "pre-push-fast"
    if not pre_push_script.exists():
        return {"passed": True, "skipped": True, "errors": []}
    try:
        # Validation child: strip the live pipeline lane bus and every
        # invocation-owned role/pager override so the repository's own tests
        # resolve their temporary .agent_bus and default routing instead of the
        # live lane.
        _run(
            ["bash", str(pre_push_script)],
            cwd=repo_root,
            timeout=PRE_PUSH_FAST_TIMEOUT_S,
            env=_commit_validation_env(),
        )
    except subprocess.CalledProcessError as exc:
        detail = _tail_failure_excerpt(
            exc.stderr or exc.stdout or "",
            limit=4000,
            max_lines=80,
        )
        if not detail:
            detail = f"exit {exc.returncode}"
        return {
            "passed": False,
            "skipped": False,
            "errors": [f"bot-remediation pre-push-fast failed: {detail}"],
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "skipped": False,
            "errors": ["bot-remediation pre-push-fast timed out"],
        }
    if log is not None:
        log("Step 15: bot-remediation pre-push-fast passed")
    return {"passed": True, "skipped": False, "errors": []}


def _parse_worktree_list(output: str) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into entry dicts."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                entries.append(current)
                current = {}
            current["worktree"] = value
            continue
        current[key] = value or "true"
    if current:
        entries.append(current)
    return entries


def _find_linked_worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Return the linked worktree path for `branch`, if exactly one exists."""
    try:
        worktree_proc = _run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None
    if worktree_proc.returncode != 0:
        return None
    target_ref = f"refs/heads/{branch}"
    matches = [
        Path(entry["worktree"])
        for entry in _parse_worktree_list(worktree_proc.stdout)
        if entry.get("worktree")
        and entry.get("bare") != "true"
        and entry.get("prunable") is None
        and entry.get("branch") == target_ref
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _git_common_dir(cwd: Path) -> Path | None:
    """Resolve the shared git common dir for the repository at `cwd`.

    Every linked worktree of one repository reports the SAME common dir (the
    primary repo's git dir); an unrelated repository reports its own. This is
    the identity used to decide whether a path belongs to `repo_root`'s repo.
    Returns None when `cwd` is not inside any git worktree. `--git-common-dir`
    is relative to `cwd` in the primary worktree ('.git') and absolute in a
    linked worktree, so the raw value is re-anchored to `cwd` before resolving.
    """
    try:
        probe = _run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if probe.returncode != 0:
        return None
    raw = probe.stdout.strip()
    if not raw:
        return None
    common = Path(raw)
    if not common.is_absolute():
        common = cwd / common
    return common.resolve()


def _is_usable_worktree(repo_root: Path, path: Path) -> bool:
    """Return True only if `path` is a live linked worktree of `repo_root`'s repo.

    Guards `_resolve_post_merge_verify_root` against handing a non-live path to
    the post-merge verify, where running git in a broken or foreign directory
    fails AFTER the merge already landed -- surfacing an already-merged PR as
    Status: error (and, under the dispatcher, a spurious recovery cascade).

    Three independent rejections, each closing a distinct false positive that
    `_find_linked_worktree_for_branch` (which reads only git's worktree
    metadata, not on-disk state) would otherwise re-admit:
      1. dir missing -- a removed worktree (e.g. a pruned nightly-ci-repair
         worktree). Checked first: `_run` with a missing `cwd` raises before git.
      2. `--show-toplevel` must resolve back to `path`. `git rev-parse` walks UP
         to an enclosing repository, so a dead worktree whose `.git` pointer was
         removed while its directory still sits inside another repo resolves to
         that ancestor, not to itself -- rejected.
      3. `path`'s git common dir must equal `repo_root`'s. A foreign, unrelated
         repository squatting the linked path is its own toplevel (so it passes
         rejection 2) but reports its own common dir, not repo_root's -- the
         reused-path false positive the round-2 bridge demonstrated -- rejected.
    """
    if not path.is_dir():
        return False
    try:
        toplevel_probe = _run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if toplevel_probe.returncode != 0:
        return False
    toplevel = toplevel_probe.stdout.strip()
    if not toplevel or Path(toplevel).resolve() != path.resolve():
        return False
    repo_common = _git_common_dir(repo_root)
    path_common = _git_common_dir(path)
    return repo_common is not None and path_common == repo_common


def _worktree_head_branch(path: Path) -> str | None:
    """Return the branch `path`'s on-disk HEAD points at, or None.

    `_find_linked_worktree_for_branch` reads only git's worktree-list metadata,
    which records the branch a worktree was REGISTERED on -- not the branch a
    `cd` into the path actually lands on. When the path's directory has been
    replaced (e.g. by a symlink to a different same-repo worktree), the metadata
    still names base_branch while the on-disk HEAD is another branch, so the
    branch the post-merge verify would really run against must be probed at the
    path itself. `_is_usable_worktree` proves the path is a live same-repo
    worktree but is branch-agnostic; this closes the remaining metadata-vs-disk
    gap. Returns None on a detached HEAD (`--abbrev-ref` yields 'HEAD') or any
    git failure, so the caller treats an unverifiable branch as a mismatch.
    """
    try:
        probe = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if probe.returncode != 0:
        return None
    branch = probe.stdout.strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def _resolve_post_merge_verify_root(repo_root: Path, base_branch: str, *, log: Any) -> Path:
    """Choose a safe worktree for post-merge verification of the base branch."""
    current_after = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
    ).stdout.strip()
    if current_after == base_branch:
        return repo_root
    branch_worktree = _find_linked_worktree_for_branch(repo_root, base_branch)
    if (
        branch_worktree is not None
        and branch_worktree != repo_root
        and _is_usable_worktree(repo_root, branch_worktree)
        and _worktree_head_branch(branch_worktree) == base_branch
    ):
        log(
            f"Step 15: using linked {base_branch} worktree for verification: {branch_worktree}"
        )
        return branch_worktree
    # No verify-ready linked worktree. An entry can still squat base_branch in
    # git's metadata — `_find_linked_worktree_for_branch` only ever returns
    # worktrees git records as checked out on base_branch — which would make a
    # bare `git checkout base_branch` fail 'already checked out at <path>' and
    # surface an already-merged PR as Status: error. We reach this fallback when
    # that recorded entry is NOT verify-ready: its directory is gone, it is a
    # foreign/dead repo squatting the path, or it is a live same-repo worktree
    # whose on-disk HEAD is no longer base_branch (metadata spoofed, e.g. the
    # path replaced by a symlink to another worktree). `git worktree prune`
    # clears entries whose directory is gone (self-healing that case), but a
    # directory that still exists is NOT prunable, so prune cannot free
    # base_branch there. `--ignore-other-worktrees` lets repo_root check out
    # base_branch regardless: safe because the rejected entry is never our
    # verify target, and any directory on disk (foreign repo or another
    # worktree) is left untouched (not removed).
    _run(["git", "worktree", "prune"], cwd=repo_root, check=False)
    _run(
        ["git", "checkout", "--ignore-other-worktrees", base_branch],
        cwd=repo_root,
    )
    return repo_root


def _preferred_branch_creation_base(repo_root: Path, base_branch: str) -> str:
    """Prefer the fetched remote base for new feature branches when available."""
    try:
        fetch_proc = _run(
            ["git", "fetch", "origin", base_branch],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return base_branch
    if fetch_proc.returncode != 0:
        return base_branch
    remote_ref = f"refs/remotes/origin/{base_branch}"
    remote_check = _run(
        ["git", "rev-parse", "--verify", remote_ref],
        cwd=repo_root,
        check=False,
    )
    if remote_check.returncode == 0:
        return f"origin/{base_branch}"
    return base_branch


def _collect_branch_rebind_dirty_scope(
    repo_root: Path,
    *,
    handoff: dict[str, Any],
) -> tuple[set[str], set[str], list[str]]:
    """Return tracked, untracked, and out-of-scope dirty paths for branch rebinding."""
    allowed_pathspecs = [
        path for path in [
            *handoff.get("files_to_stage", []),
            *handoff.get("force_add_files", []),
            *handoff.get("scope_items", []),
        ]
        if isinstance(path, str) and path.strip()
    ]
    tracked_dirty = {
        path for path in _tracked_dirty_paths(repo_root)
        if not _is_transient_status_path(path)
    }
    untracked_dirty = {
        path for path in _untracked_worktree_paths(repo_root)
        if not _is_transient_status_path(path)
    }
    dirty_paths = tracked_dirty | untracked_dirty
    # Handoff scope entries are Git pathspecs, not just literal file paths.
    # Re-resolve dirty files through Git so `.` and directory pathspecs are
    # treated as in-scope during branch rebinding the same way staging does.
    scoped_dirty = set()
    if allowed_pathspecs:
        scoped_dirty = {
            path for path in (
                _tracked_dirty_paths(repo_root, pathspecs=allowed_pathspecs)
                | _untracked_worktree_paths(repo_root, pathspecs=allowed_pathspecs)
            )
            if not _is_transient_status_path(path)
        }
    outside_scope = sorted(dirty_paths - scoped_dirty)
    return tracked_dirty, untracked_dirty, outside_scope


def _probe_feature_branch_existence(repo_root: Path, target_branch: str) -> tuple[bool, bool]:
    """Return local/remote existence for the canonical target branch."""
    local_check = _run(
        ["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"],
        cwd=repo_root,
        check=False,
    )
    remote_check = _run(
        ["git", "ls-remote", "--heads", "origin", target_branch],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    return local_check.returncode == 0, bool(remote_check.stdout.strip())


def _tracked_dirty_paths(
    repo_root: Path,
    pathspecs: list[str] | None = None,
    *,
    no_renames: bool = False,
) -> set[str]:
    """Return tracked paths that differ from HEAD.

    With ``no_renames=True`` git's DEFAULT rename detection is disabled, so a
    tracked rename (``git mv a b``) is reported as BOTH its deleted source and
    added destination instead of collapsed into the destination alone. Callers
    that build a path-limited stash need both sides: otherwise the omitted
    source-deletion survives the operation and corrupts the later restore.
    """
    dirty: set[str] = set()
    cmd = ["git", "diff", "--name-only", "HEAD"]
    if no_renames:
        cmd.append("--no-renames")
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    diff_proc = _run(cmd, cwd=repo_root, check=False)
    if diff_proc.returncode == 0:
        dirty.update(
            path.strip()
            for path in diff_proc.stdout.splitlines()
            if path.strip()
        )
    return dirty


def _untracked_worktree_paths(repo_root: Path, pathspecs: list[str] | None = None) -> set[str]:
    """Return untracked repo-relative paths."""
    dirty: set[str] = set()
    cmd = ["git", "ls-files", "--others", "--exclude-standard"]
    if pathspecs:
        cmd.extend(["--", *pathspecs])
    untracked_proc = _run(cmd, cwd=repo_root, check=False)
    if untracked_proc.returncode == 0:
        dirty.update(
            path.strip()
            for path in untracked_proc.stdout.splitlines()
            if path.strip()
        )
    return dirty


def _dirty_worktree_paths(repo_root: Path) -> set[str]:
    """Return repo-relative dirty/untracked paths, excluding transient executor state."""
    dirty = _tracked_dirty_paths(repo_root) | _untracked_worktree_paths(repo_root)
    return {
        path for path in dirty
        if path and not _is_transient_status_path(path)
    }


def _primary_sync_changed_paths_in_range(
    repo_root: Path,
    old_sha: str,
    new_sha: str,
    paths: list[str],
) -> tuple[set[str], str | None]:
    """Return stashed paths touched by the pending ff range."""
    if not paths:
        return set(), None
    proc = _run(
        ["git", "diff", "--name-only", old_sha, new_sha, "--", *paths],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return set(), (
            "could not compare primary sync range against tracked WIP paths: "
            f"{detail[:200] or proc.returncode}"
        )
    changed = {
        path.strip()
        for path in proc.stdout.splitlines()
        if path.strip()
    }
    return changed & set(paths), None


def _stash_primary_sync_tracked_wip(
    repo_root: Path,
    paths: list[str],
    *,
    log: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    """Isolate exact tracked dirty paths before primary ff-sync."""
    if not paths:
        return None, None
    # `paths` may carry BOTH sides of a tracked rename (deleted source + added
    # destination). Git's default rename detection collapses those into the
    # destination alone, so a rename-detected `_tracked_dirty_paths` would
    # report the source as "missing" and wrongly abort the stash. Disable
    # rename detection here to match the caller's rename-complete path set.
    current_tracked = _tracked_dirty_paths(repo_root, no_renames=True)
    missing_paths = sorted(set(paths) - current_tracked)
    if missing_paths:
        return None, (
            "primary tracked WIP paths changed before stash creation: "
            + ", ".join(missing_paths)
        )

    marker = f"commit_executor:primary_ffsync_tracked_wip:{uuid.uuid4().hex}"
    result = _run(
        ["git", "stash", "push", "-m", marker, "--", *paths],
        cwd=repo_root,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return None, (
            "git stash push failed before primary ff-sync: "
            f"{detail[:200] or result.returncode}"
        )
    stash_ref = _find_stash_ref_by_marker(repo_root, marker)
    if stash_ref is None:
        return None, (
            "git stash push reported saved changes before primary ff-sync, "
            "but the created stash ref could not be found"
        )
    ref, oid = stash_ref
    log(
        "Step 15b: isolated tracked primary WIP in "
        f"{ref} ({oid}) for path(s): {', '.join(paths)}"
    )
    return {
        "marker": marker,
        "stash_ref": ref,
        "stash_oid": oid,
        "paths": list(paths),
    }, None


def _resolve_primary_sync_stash_record(
    repo_root: Path,
    stash_record: dict[str, Any] | None,
) -> tuple[tuple[str, str] | None, str | None]:
    """Resolve and validate an executor-owned primary-sync WIP stash."""
    if not stash_record:
        return None, None
    marker = str(stash_record.get("marker") or "")
    expected_oid = str(stash_record.get("stash_oid") or "")
    resolved = _find_stash_ref_by_marker(repo_root, marker)
    if resolved is None:
        return None, f"primary ff-sync tracked-WIP stash missing for marker {marker}"
    stash_ref, stash_oid = resolved
    if expected_oid and stash_oid != expected_oid:
        return None, (
            "primary ff-sync tracked-WIP stash object id mismatch: "
            f"expected {expected_oid}, found {stash_oid}"
        )
    return (stash_ref, stash_oid), None


def _restore_primary_sync_tracked_wip(
    repo_root: Path,
    stash_record: dict[str, Any] | None,
    *,
    log: Any,
) -> str | None:
    """Restore executor-owned primary-sync WIP and fail closed on stash drift."""
    resolved, resolve_error = _resolve_primary_sync_stash_record(
        repo_root,
        stash_record,
    )
    if resolve_error:
        return resolve_error
    if resolved is None:
        return None
    stash_ref, _stash_oid = resolved
    pop = _run(
        ["git", "stash", "pop", "--index", stash_ref],
        cwd=repo_root,
        check=False,
        timeout=120,
    )
    if pop.returncode != 0:
        detail = (pop.stderr or pop.stdout or "").strip()
        return (
            f"git stash pop --index {stash_ref} failed after primary ff-sync: "
            f"{detail[:200] or pop.returncode}"
        )
    log(f"Step 15b: restored tracked primary WIP from {stash_ref}")
    return None


def _restore_primary_sync_tracked_wip_paths(
    repo_root: Path,
    stash_record: dict[str, Any] | None,
    paths: list[str],
    *,
    log: Any,
) -> str | None:
    """Restore selected tracked WIP paths from an executor-owned stash."""
    restore_paths = sorted(path for path in dict.fromkeys(paths) if path)
    if not restore_paths:
        return None
    resolved, resolve_error = _resolve_primary_sync_stash_record(repo_root, stash_record)
    if resolve_error:
        return resolve_error
    if resolved is None:
        return None
    stash_ref, stash_oid = resolved
    # Stash commits keep HEAD at ^1, the saved index at ^2, and the saved
    # worktree as the stash tree. Applying both deltas mirrors `stash pop
    # --index` for only these paths.
    patch_steps = [
        (
            f"{stash_oid}^1",
            f"{stash_oid}^2",
            ["--index", "--binary"],
            "staged",
        ),
        (
            f"{stash_oid}^2",
            stash_oid,
            ["--binary"],
            "unstaged",
        ),
    ]
    for before_ref, after_ref, apply_args, label in patch_steps:
        diff = _run(
            [
                "git",
                "diff",
                "--binary",
                "--no-ext-diff",
                before_ref,
                after_ref,
                "--",
                *restore_paths,
            ],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
        if diff.returncode != 0:
            detail = (diff.stderr or diff.stdout or "").strip()
            return (
                f"git diff for {label} tracked-WIP restore failed: "
                f"{detail[:200] or diff.returncode}"
            )
        if not diff.stdout:
            continue
        apply = _run(
            ["git", "apply", *apply_args],
            cwd=repo_root,
            check=False,
            timeout=120,
            input_text=diff.stdout,
        )
        if apply.returncode != 0:
            detail = (apply.stderr or apply.stdout or "").strip()
            return (
                f"git apply for {label} tracked-WIP restore failed: "
                f"{detail[:200] or apply.returncode}"
            )
    log(
        "Step 15b: restored non-overlapping tracked primary WIP from "
        f"{stash_ref} for path(s): {', '.join(restore_paths)}"
    )
    return None


def _sync_primary_worktree_to_base(
    repo_root: Path,
    base_branch: str,
    *,
    log: Any,
) -> dict[str, Any]:
    """Fast-forward a clean founder PRIMARY working copy up to origin/base_branch.

    PULL-ONLY and fully fail-open. The existing post-merge verify-root ff
    (`_resolve_post_merge_verify_root` + `git merge --ff-only`) only ever
    advances a worktree that is ALREADY on base_branch; the founder's primary
    checkout normally rests on a FEATURE branch, so it is never that target and
    drifts behind base_branch as waves merge. This helper independently
    identifies the primary worktree (the FIRST non-bare `git worktree list`
    entry, whose git dir IS the common dir) and brings origin/{base_branch}
    DOWN into the primary's CURRENT feature branch via `git fetch` +
    `git merge --ff-only`. It NEVER pushes, NEVER checks out base_branch, and
    NEVER force/resets -- real merges to base stay on the PR path.

    Every unmet guard or error is a clean SKIP (logged), never an exception out
    of `_run_post_commit_pipeline`: the PR has already merged and this sync must
    never regress the pipeline or change the wave Status.

    Guards (any miss -> SKIP):
      GUARD-A primary is on a FEATURE branch (not base_branch/main/master).
      GUARD-B visible dirty founder WIP is preserved, never clobbered. TRACKED
              dirty WIP is stash-isolated across the ff and restored in place;
              UNTRACKED-only dirty WIP attempts the ff directly (non-colliding
              founder scratch rides through byte-identical on disk). Either path
              falls back to durable behind_dev observability on the
              primary-worktree bus -- a clean SKIP instead of fast-forwarding --
              when the ff cannot proceed safely (a tracked-WIP overlap with the
              ff range, or a real untracked/ignored collision that git aborts on).
              The ff merge additionally runs `--no-overwrite-ignore` to ABORT
              rather than silently overwrite locally-ignored founder WIP.
      GUARD-C primary HEAD is an ANCESTOR of origin/{base_branch} (a real
              fast-forward; divergent local commits are landed via a PR).
      GUARD-D a NON-BLOCKING file lock under the common git dir is acquired
              (concurrent lanes do not race on the primary's index).

    Returns an outcome dict (for observability / test assertions).
    """
    outcome: dict[str, Any] = {
        "synced": False,
        "skipped": True,
        "reason": None,
        "primary": None,
        "old_sha": None,
        "new_sha": None,
        "behind_count": None,
        "ahead_count": None,
        "dirty_paths": [],
        "behind_dev_signal_path": None,
        "behind_dev_signal_written": False,
        "behind_dev_signal_cleared": False,
        "tracked_wip_paths": [],
        "tracked_wip_stash_marker": None,
        "tracked_wip_stash_ref": None,
        "tracked_wip_stash_oid": None,
        "tracked_wip_overlap_paths": [],
        "tracked_wip_restored": False,
        "tracked_wip_left_stashed": False,
        "tracked_wip_restore_error": None,
    }

    def _skip(reason: str) -> dict[str, Any]:
        outcome["synced"] = False
        outcome["skipped"] = True
        outcome["reason"] = reason
        log(f"Step 15b: primary worktree base-sync skipped: {reason}")
        return outcome

    def _behind_dev_signal_path(primary_path: Path) -> Path:
        # Durable founder-primary bus only. The active lane's repo_root can be a
        # temporary linked worktree removed by post-merge cleanup.
        return agent_bus_path(primary_path, None, "behind_dev.json")

    def _commit_count(primary_path: Path, rev_range: str) -> int | None:
        try:
            proc = _run(
                ["git", "rev-list", "--count", rev_range],
                cwd=primary_path,
                check=False,
                timeout=30,
            )
        except Exception:  # noqa: BLE001 - observability must not break sync
            return None
        if proc.returncode != 0:
            return None
        try:
            return int((proc.stdout or "").strip())
        except (TypeError, ValueError):
            return None

    def _clear_behind_dev_signal(primary_path: Path) -> None:
        try:
            signal_path = _behind_dev_signal_path(primary_path)
            existed = signal_path.exists()
            signal_path.unlink(missing_ok=True)
            outcome["behind_dev_signal_path"] = str(signal_path)
            if existed:
                outcome["behind_dev_signal_cleared"] = True
        except Exception as exc:  # noqa: BLE001 - clear must not regress sync
            try:
                log(f"Step 15b: behind_dev signal clear failed (non-fatal): {exc}")
            except Exception:
                pass

    def _write_behind_dev_signal(
        primary_path: Path,
        *,
        base_ref: str,
        reason: str,
        dirty_paths: list[str] | None = None,
    ) -> None:
        behind_count = _commit_count(primary_path, f"HEAD..{base_ref}")
        ahead_count = _commit_count(primary_path, f"{base_ref}..HEAD")
        outcome["behind_count"] = behind_count
        outcome["ahead_count"] = ahead_count
        if behind_count is None or behind_count <= 0:
            _clear_behind_dev_signal(primary_path)
            log(
                "Step 15b: behind_dev signal not written because primary is "
                f"not behind {base_ref} (behind_count={behind_count})"
            )
            return

        signal_path = _behind_dev_signal_path(primary_path)
        payload: dict[str, Any] = {
            "primary": str(primary_path),
            "base_ref": base_ref,
            "behind_count": behind_count,
            "ahead_count": ahead_count,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if dirty_paths is not None:
            payload["dirty_paths"] = list(dirty_paths)
        try:
            signal_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
            tmp_fd, tmp_name = tempfile.mkstemp(
                dir=str(signal_path.parent),
                prefix=".behind_dev.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
                    tmp_file.write(serialized)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                os.replace(tmp_name, signal_path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
            outcome["behind_dev_signal_path"] = str(signal_path)
            outcome["behind_dev_signal_written"] = True
            log(
                "Step 15b: WARNING behind_dev primary worktree "
                f"{primary_path} is behind {base_ref} by {behind_count} "
                f"commit(s), ahead by {ahead_count} commit(s), "
                f"reason={reason}; wrote {signal_path}"
            )
        except Exception as exc:  # noqa: BLE001 - signal write must not regress sync
            try:
                log(f"Step 15b: behind_dev signal write failed (non-fatal): {exc}")
            except Exception:
                pass

    try:
        # Identify the PRIMARY worktree: the FIRST non-bare `git worktree list`
        # entry. git always lists the main worktree before any linked worktree.
        try:
            worktree_proc = _run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo_root,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return _skip(f"git worktree list unavailable: {exc}")
        if worktree_proc.returncode != 0:
            return _skip("git worktree list failed")
        primary_entry = next(
            (
                entry
                for entry in _parse_worktree_list(worktree_proc.stdout)
                if entry.get("worktree") and entry.get("bare") != "true"
            ),
            None,
        )
        if primary_entry is None:
            return _skip("no non-bare primary worktree found")
        primary = Path(primary_entry["worktree"])

        # Confirm primary identity: its git dir IS the common dir
        # (`<primary>/.git`). A linked worktree reports the SAME common dir but
        # lives elsewhere, so only the primary's parent-of-common-dir equals
        # itself. This makes "we only ever ff the primary" independent of the
        # verify-root resolver's internals: a DIFFERENT worktree than repo_root.
        common_dir = _git_common_dir(primary)
        if common_dir is None or common_dir.parent.resolve() != primary.resolve():
            return _skip(f"could not confirm primary worktree at {primary}")

        # Read the primary's ON-DISK HEAD branch (not just git's metadata).
        primary_branch = _worktree_head_branch(primary)
        if primary_branch is None:
            return _skip("primary worktree HEAD branch unresolved (detached?)")

        # GUARD-A: never sync a base-branch checkout.  When Step 15 used this
        # same primary as the verify root, it may already have fast-forwarded
        # the base branch; clear any stale primary-bus behind_dev signal only
        # after proving the local base checkout is current with origin/base.
        if primary_branch in {base_branch, "main", "master"}:
            remote_ref = f"origin/{base_branch}"
            old_sha = ""
            new_sha = ""
            try:
                old_sha = _run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=primary,
                    check=False,
                    timeout=30,
                ).stdout.strip()
                new_sha = _run(
                    ["git", "rev-parse", remote_ref],
                    cwd=primary,
                    check=False,
                    timeout=30,
                ).stdout.strip()
            except Exception:  # noqa: BLE001 - stale-signal clear is best-effort
                old_sha = ""
                new_sha = ""
            if old_sha:
                outcome["old_sha"] = old_sha
            if new_sha:
                outcome["new_sha"] = new_sha
            if old_sha and new_sha and old_sha == new_sha:
                outcome["primary"] = str(primary)
                _clear_behind_dev_signal(primary)
                return _skip(
                    f"primary worktree on base branch '{primary_branch}' "
                    f"already current at {new_sha[:8]}; "
                    "PULL-ONLY helper never syncs a base-branch checkout"
                )
            return _skip(
                f"primary worktree on base branch '{primary_branch}'; "
                "PULL-ONLY helper never syncs a base-branch checkout"
            )

        # GUARD-D: parallel-lane safety. Take a NON-BLOCKING exclusive lock on a
        # lockfile under the shared common git dir so concurrent lane waves do
        # not race on the primary's index. Lock held -> another wave is already
        # syncing -> SKIP.
        lock_path = common_dir / "rcx_primary_worktree_sync.lock"
        lock_handle = None
        lock_acquired = False
        try:
            try:
                lock_handle = open(lock_path, "w")
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired = True
            except OSError:
                lock_acquired = False
            if not lock_acquired:
                return _skip(
                    "primary worktree sync lock held (another lane is syncing)"
                )

            # PULL-ONLY: fetch origin/{base_branch} so GUARD-C and the ff see the
            # just-merged PR. fetch only updates the remote-tracking ref; it
            # never touches the primary's branch or working tree.
            fetch_proc = _run(
                ["git", "fetch", "origin", base_branch],
                cwd=primary,
                check=False,
                timeout=60,
            )
            if fetch_proc.returncode != 0:
                detail = (fetch_proc.stderr or fetch_proc.stdout or "").strip()
                return _skip(f"fetch origin {base_branch} failed: {detail[:200]}")

            remote_ref = f"origin/{base_branch}"
            old_sha = _run(
                ["git", "rev-parse", "HEAD"], cwd=primary, check=False, timeout=30,
            ).stdout.strip()
            new_sha = _run(
                ["git", "rev-parse", remote_ref], cwd=primary, check=False, timeout=30,
            ).stdout.strip()

            # GUARD-C: primary HEAD must be an ANCESTOR of origin/{base_branch}
            # (a real fast-forward, no divergent local commits). Else SKIP --
            # the founder lands those commits via a PR.
            ancestor_proc = _run(
                ["git", "merge-base", "--is-ancestor", "HEAD", remote_ref],
                cwd=primary,
                check=False,
                timeout=30,
            )
            if ancestor_proc.returncode != 0:
                _write_behind_dev_signal(
                    primary,
                    base_ref=remote_ref,
                    reason="divergent_local_commits",
                )
                return _skip(
                    f"primary worktree HEAD is not an ancestor of {remote_ref} "
                    "(divergent local commits; founder lands those via a PR)"
                )

            if old_sha and new_sha and old_sha == new_sha:
                outcome["primary"] = str(primary)
                outcome["old_sha"] = old_sha
                outcome["new_sha"] = new_sha
                _clear_behind_dev_signal(primary)
                return _skip(f"primary worktree already current at {new_sha[:8]}")

            dirty_paths = sorted(_dirty_worktree_paths(primary))
            if dirty_paths:
                outcome["primary"] = str(primary)
                outcome["old_sha"] = old_sha
                outcome["new_sha"] = new_sha
                outcome["dirty_paths"] = list(dirty_paths)

                def _behind_dev_dirty_skip(
                    reason_text: str,
                    *,
                    signal_reason: str = "dirty_primary_worktree",
                ) -> dict[str, Any]:
                    _write_behind_dev_signal(
                        primary,
                        base_ref=remote_ref,
                        reason=signal_reason,
                        dirty_paths=dirty_paths,
                    )
                    return _skip(reason_text)

                # Only TRACKED dirty WIP blocks a fast-forward: git refuses to ff
                # over locally-modified tracked files. Untracked/ignored founder
                # WIP is NEVER stashed -- `_dirty_worktree_paths` already excludes
                # ignored (`ls-files --others --exclude-standard`), the ff runs
                # `--no-overwrite-ignore` (aborts rather than clobber ignored WIP),
                # and non-colliding untracked files ride through the ff untouched
                # (a colliding one aborts the ff, handled below). Isolate ONLY the
                # tracked-dirty subset.
                # `dirty_paths` (via `_dirty_worktree_paths`) uses git's DEFAULT
                # rename detection: a tracked rename (`git mv a b`) collapses
                # into the destination `b` alone, hiding the deleted source `a`.
                # A path-limited stash built from that set would leave the
                # staged source-deletion behind, so it rides through the ff and
                # breaks the post-ff `stash pop --index` restore -- and the
                # source is invisible to the overlap check below. Recompute the
                # tracked-WIP set with rename detection OFF so BOTH sides of
                # every rename are isolated together; drop transient executor
                # state to mirror `_dirty_worktree_paths`' filtering (the old
                # `& dirty_paths` intersection did that double duty).
                tracked_wip_paths = sorted(
                    path
                    for path in _tracked_dirty_paths(primary, no_renames=True)
                    if not _is_transient_status_path(path)
                )
                outcome["tracked_wip_paths"] = list(tracked_wip_paths)

                if not tracked_wip_paths:
                    # FIX-NEVERBEHIND-FF-UNTRACKED: untracked-only dirty WIP no
                    # longer forces a behind_dev skip. Skipping on the mere
                    # PRESENCE of untracked founder scratch (reports/handoffs)
                    # was TOO CONSERVATIVE: `git merge --ff-only
                    # --no-overwrite-ignore` does NOT clobber untracked files --
                    # git ABORTS the ff ONLY when an untracked/ignored path would
                    # be OVERWRITTEN (a real collision). Non-colliding untracked
                    # scratch rides through the ff byte-identical on disk. So
                    # ATTEMPT the ff to stay never-behind while git's own
                    # collision-abort (plus --no-overwrite-ignore) preserves
                    # never-clobber. A real collision returns non-zero and falls
                    # back to the existing safe behind_dev skip.
                    merge_proc = _run(
                        ["git", "merge", "--ff-only", "--no-overwrite-ignore", remote_ref],
                        cwd=primary,
                        check=False,
                        timeout=60,
                    )
                    if merge_proc.returncode != 0:
                        # Real untracked/ignored collision: git aborted rather
                        # than overwrite founder WIP. Fall back to the existing
                        # safe skip + behind_dev signal -- never clobber.
                        detail = (merge_proc.stderr or merge_proc.stdout or "").strip()
                        return _behind_dev_dirty_skip(
                            f"ff-only merge of {remote_ref} into '{primary_branch}' "
                            "aborted on an untracked/ignored collision; wrote "
                            "behind_dev signal instead of clobbering founder WIP: "
                            f"{detail[:200]}",
                            signal_reason="ff_only_merge_failed",
                        )

                    synced_sha = _run(
                        ["git", "rev-parse", "HEAD"], cwd=primary, check=False, timeout=30,
                    ).stdout.strip()
                    outcome["synced"] = True
                    outcome["skipped"] = False
                    outcome["reason"] = None
                    outcome["new_sha"] = synced_sha
                    _clear_behind_dev_signal(primary)
                    log(
                        f"Step 15b: synced primary worktree {primary} on "
                        f"'{primary_branch}' {(old_sha or '?')[:8]} -> "
                        f"{(synced_sha or '?')[:8]} (ff-only {remote_ref}; left "
                        f"{len(dirty_paths)} non-colliding untracked founder "
                        "path(s) in place)"
                    )
                    return outcome

                # A fast-forward whose range TOUCHES a tracked-WIP path would turn
                # the post-ff `stash pop --index` restore into a conflicting 3-way
                # merge (founder WIP vs origin content). Detect that overlap BEFORE
                # stashing or fast-forwarding and skip -- never risk corrupting
                # founder WIP with conflict markers.
                overlap_paths, overlap_error = _primary_sync_changed_paths_in_range(
                    primary, old_sha, new_sha, tracked_wip_paths,
                )
                if overlap_error:
                    return _behind_dev_dirty_skip(
                        "primary worktree is behind base with tracked dirty WIP "
                        f"but the ff range could not be compared safely: "
                        f"{overlap_error}"
                    )
                if overlap_paths:
                    outcome["tracked_wip_overlap_paths"] = sorted(overlap_paths)
                    return _behind_dev_dirty_skip(
                        "primary worktree is behind base with tracked dirty WIP "
                        "overlapping the fast-forward range; wrote behind_dev "
                        "signal instead of risking a conflicting restore"
                    )

                # Non-overlapping tracked WIP: isolate it, fast-forward, restore.
                stash_record, stash_error = _stash_primary_sync_tracked_wip(
                    primary, tracked_wip_paths, log=log,
                )
                if stash_error or stash_record is None:
                    # Stash creation failed -> DO NOT fast-forward; keep the WIP in
                    # place and fall back to the behind_dev skip.
                    return _behind_dev_dirty_skip(
                        "primary worktree is behind base with tracked dirty WIP "
                        "that could not be isolated for a safe fast-forward"
                        + (f": {stash_error}" if stash_error else "")
                    )
                outcome["tracked_wip_stash_marker"] = stash_record.get("marker")
                outcome["tracked_wip_stash_ref"] = stash_record.get("stash_ref")
                outcome["tracked_wip_stash_oid"] = stash_record.get("stash_oid")

                # PULL-ONLY ff with the tracked WIP isolated. --ff-only refuses any
                # non-fast-forward; --no-overwrite-ignore aborts rather than clobber
                # locally-ignored founder WIP. We never push, checkout base, force,
                # or reset.
                merge_proc = _run(
                    ["git", "merge", "--ff-only", "--no-overwrite-ignore", remote_ref],
                    cwd=primary,
                    check=False,
                    timeout=60,
                )
                if merge_proc.returncode != 0:
                    # ff failed after stashing -> restore WIP before returning so
                    # founder WIP is never left only in the stash on a skip path.
                    detail = (merge_proc.stderr or merge_proc.stdout or "").strip()
                    restore_error = _restore_primary_sync_tracked_wip(
                        primary, stash_record, log=log,
                    )
                    if restore_error:
                        outcome["tracked_wip_left_stashed"] = True
                        outcome["tracked_wip_restore_error"] = restore_error
                    else:
                        outcome["tracked_wip_restored"] = True
                    return _behind_dev_dirty_skip(
                        f"ff-only merge of {remote_ref} into '{primary_branch}' "
                        f"failed after isolating tracked dirty WIP: {detail[:200]}",
                        signal_reason="ff_only_merge_failed",
                    )

                # ff succeeded -> restore the isolated tracked WIP in place.
                restore_error = _restore_primary_sync_tracked_wip(
                    primary, stash_record, log=log,
                )
                synced_sha = _run(
                    ["git", "rev-parse", "HEAD"], cwd=primary, check=False, timeout=30,
                ).stdout.strip()
                if restore_error:
                    # HEAD advanced but the WIP restore drifted. The WIP is safe in
                    # the executor-owned stash; surface the drift and skip so the
                    # founder recovers it -- never silently drop or overwrite it.
                    outcome["tracked_wip_left_stashed"] = True
                    outcome["tracked_wip_restore_error"] = restore_error
                    outcome["new_sha"] = synced_sha
                    _clear_behind_dev_signal(primary)
                    return _skip(
                        "primary worktree fast-forwarded but tracked dirty WIP "
                        f"restore drifted; WIP preserved in stash: {restore_error}"
                    )

                outcome["tracked_wip_restored"] = True
                outcome["synced"] = True
                outcome["skipped"] = False
                outcome["reason"] = None
                outcome["new_sha"] = synced_sha
                _clear_behind_dev_signal(primary)
                log(
                    f"Step 15b: synced primary worktree {primary} on "
                    f"'{primary_branch}' {(old_sha or '?')[:8]} -> "
                    f"{(synced_sha or '?')[:8]} (ff-only {remote_ref}; preserved "
                    f"tracked WIP: {', '.join(tracked_wip_paths)})"
                )
                return outcome

            # PULL-ONLY ff: bring origin/{base_branch} DOWN into the primary's
            # CURRENT feature branch. --ff-only is the backstop that refuses any
            # non-fast-forward; we never push, checkout base, force, or reset.
            # --no-overwrite-ignore closes the remaining gap for IGNORED founder
            # WIP: _dirty_worktree_paths uses `ls-files --others
            # --exclude-standard`, which excludes ignored files. git merge can
            # silently overwrite ignored files by default; --no-overwrite-ignore
            # makes it abort instead, preserving that WIP.
            merge_proc = _run(
                ["git", "merge", "--ff-only", "--no-overwrite-ignore", remote_ref],
                cwd=primary,
                check=False,
                timeout=60,
            )
            if merge_proc.returncode != 0:
                detail = (merge_proc.stderr or merge_proc.stdout or "").strip()
                _write_behind_dev_signal(
                    primary,
                    base_ref=remote_ref,
                    reason="ff_only_merge_failed",
                )
                return _skip(
                    f"ff-only merge of {remote_ref} into '{primary_branch}' "
                    f"failed: {detail[:200]}"
                )

            synced_sha = _run(
                ["git", "rev-parse", "HEAD"], cwd=primary, check=False, timeout=30,
            ).stdout.strip()
            outcome["synced"] = True
            outcome["skipped"] = False
            outcome["reason"] = None
            outcome["primary"] = str(primary)
            outcome["old_sha"] = old_sha
            outcome["new_sha"] = synced_sha
            _clear_behind_dev_signal(primary)
            log(
                f"Step 15b: synced primary worktree {primary} on "
                f"'{primary_branch}' {(old_sha or '?')[:8]} -> "
                f"{(synced_sha or '?')[:8]} (ff-only {remote_ref})"
            )
            return outcome
        finally:
            if lock_handle is not None:
                if lock_acquired:
                    try:
                        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                try:
                    lock_handle.close()
                except OSError:
                    pass
    except Exception as exc:  # noqa: BLE001 - fail-open: never raise into the pipeline
        outcome["synced"] = False
        outcome["skipped"] = True
        outcome["reason"] = f"error: {exc}"
        try:
            log(f"Step 15b: primary worktree base-sync error (skipped): {exc}")
        except Exception:
            pass
        return outcome


# Public seam for the PULL-ONLY primary-worktree base sync. The sync is an
# internal post-merge pipeline step, but its outcome dict is a supported
# observability surface (the pipeline records it as
# result["primary_worktree_sync"]). Tests and callers exercise the behavior
# through this public name instead of reaching past the leading underscore:
# the private-attr test-integrity policy forbids `ANTICHEAT_OK` bypass comments
# in tests and requires a real public seam.
sync_primary_worktree_to_base = _sync_primary_worktree_to_base


def _find_stash_ref_by_marker(
    repo_root: Path,
    marker: str,
) -> tuple[str, str] | None:
    """Return (stash_ref, stash_oid) for an exact stash marker."""
    proc = _run(
        ["git", "stash", "list", "--format=%gd%x00%H%x00%s"],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    for raw_line in proc.stdout.splitlines():
        parts = raw_line.split("\x00", 2)
        if len(parts) != 3:
            continue
        ref, oid, subject = parts
        if subject.strip().endswith(marker):
            return ref, oid
    return None


PRE_PUSH_ISOLATION_VERIFIED_VALUE = "pre_push_passed"
PRE_PUSH_ISOLATION_STASH_PENDING_VALUE = "stash_pending"


def _prepare_post_commit_pre_push_dirty_isolation(
    repo_root: Path,
    *,
    wave_id: str,
) -> dict[str, Any] | None:
    """Build a durable pre-stash record for unrelated dirty work."""
    dirty_paths = sorted(_dirty_worktree_paths(repo_root))
    if not dirty_paths:
        return None
    return {
        "marker": f"commit_executor:post_commit_pre_push:{wave_id}:{uuid.uuid4().hex}",
        "paths": "\n".join(dirty_paths),
        "pre_push_state": PRE_PUSH_ISOLATION_STASH_PENDING_VALUE,
    }


def _stash_post_commit_pre_push_dirty_paths(
    repo_root: Path,
    *,
    wave_id: str,
    log: Any,
    isolation: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Temporarily isolate unrelated dirty work before running pre-push-fast."""
    dirty_paths = sorted(_pre_push_isolation_paths(isolation))
    if not dirty_paths:
        dirty_paths = sorted(_dirty_worktree_paths(repo_root))
    if not dirty_paths:
        return None, None

    marker = str((isolation or {}).get("marker") or "").strip()
    if not marker:
        marker = f"commit_executor:post_commit_pre_push:{wave_id}:{uuid.uuid4().hex}"
    stash_ref = _find_stash_ref_by_marker(repo_root, marker)
    if stash_ref is None:
        current_dirty_paths = _dirty_worktree_paths(repo_root)
        missing_paths = sorted(set(dirty_paths) - current_dirty_paths)
        if missing_paths:
            return None, (
                "pre-push dirty isolation paths changed before stash creation: "
                + ", ".join(missing_paths)
            )
        result = _run(
            ["git", "stash", "push", "--include-untracked", "-m", marker, "--", *dirty_paths],
            cwd=repo_root,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return None, f"git stash push failed before pre-push isolation: {detail or result.returncode}"
        stash_ref = _find_stash_ref_by_marker(repo_root, marker)
        if stash_ref is None:
            return None, (
                "git stash push reported saved changes before pre-push isolation, "
                "but the created stash ref could not be found"
            )

    ref, oid = stash_ref
    isolated = dict(isolation or {})
    isolated.update({
        "marker": marker,
        "stash_ref": ref,
        "stash_oid": oid,
        "paths": "\n".join(dirty_paths),
    })
    if isolated.get("pre_push_state") == PRE_PUSH_ISOLATION_STASH_PENDING_VALUE:
        isolated.pop("pre_push_state", None)
    log(
        "Step 11: isolated "
        f"{len(dirty_paths)} dirty out-of-scope path(s) in {ref} before pre-push"
    )
    return isolated, None


def _pre_push_isolation_paths(isolation: dict[str, Any] | None) -> set[str]:
    if not isolation:
        return set()
    return {
        path.strip()
        for path in str(isolation.get("paths") or "").splitlines()
        if path.strip()
    }


def _pre_push_isolation_verified(isolation: dict[str, Any] | None) -> bool:
    if not isolation:
        return False
    return isolation.get("pre_push_state") == PRE_PUSH_ISOLATION_VERIFIED_VALUE


def _mark_pre_push_isolation_verified(isolation: dict[str, Any]) -> None:
    isolation["pre_push_state"] = PRE_PUSH_ISOLATION_VERIFIED_VALUE


def _pre_push_isolation_already_restored(
    repo_root: Path,
    isolation: dict[str, Any] | None,
) -> bool:
    expected_paths = _pre_push_isolation_paths(isolation)
    if not expected_paths:
        return False
    return expected_paths <= _dirty_worktree_paths(repo_root)


def _classify_pre_push_isolation_resume(
    repo_root: Path,
    isolation: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Classify durable pre-push isolation state before Step 11 resumes."""
    marker = str(isolation.get("marker") or "")
    expected_paths = _pre_push_isolation_paths(isolation)
    resolved = _find_stash_ref_by_marker(repo_root, marker)
    dirty_isolated_paths = expected_paths & _dirty_worktree_paths(repo_root)
    verified = _pre_push_isolation_verified(isolation)
    if dirty_isolated_paths:
        if verified and resolved is None and _pre_push_isolation_already_restored(
            repo_root,
            isolation,
        ):
            return "already_restored", None
        dirty_list = ", ".join(sorted(dirty_isolated_paths))
        return None, (
            "pre-push isolation paths are dirty before Step 11 can run safely: "
            f"{dirty_list}"
        )
    if resolved is None:
        return None, f"pre-push isolation stash missing for marker {marker}"
    _stash_ref, stash_oid = resolved
    expected_oid = str(isolation.get("stash_oid") or "")
    if expected_oid and stash_oid != expected_oid:
        return None, (
            "pre-push isolation stash object id mismatch: "
            f"expected {expected_oid}, found {stash_oid}"
        )
    if verified:
        return "restore_only", None
    return "run_pre_push", None


def _restore_post_commit_pre_push_dirty_paths(
    repo_root: Path,
    isolation: dict[str, Any] | None,
    *,
    log: Any,
) -> str | None:
    """Restore a pre-push isolation stash and fail closed on ref drift."""
    if not isolation:
        return None
    marker = isolation.get("marker", "")
    expected_oid = isolation.get("stash_oid", "")
    resolved = _find_stash_ref_by_marker(repo_root, marker)
    if resolved is None:
        if _pre_push_isolation_verified(isolation) and _pre_push_isolation_already_restored(
            repo_root,
            isolation,
        ):
            log(
                "Step 11: pre-push isolation stash already restored for "
                f"marker {marker}"
            )
            return None
        return f"pre-push isolation stash missing for marker {marker}"
    stash_ref, stash_oid = resolved
    if expected_oid and stash_oid != expected_oid:
        return (
            "pre-push isolation stash object id mismatch: "
            f"expected {expected_oid}, found {stash_oid}"
        )
    pop = _run(
        ["git", "stash", "pop", "--index", stash_ref],
        cwd=repo_root,
        check=False,
        timeout=120,
    )
    if pop.returncode != 0:
        detail = (pop.stderr or pop.stdout or "").strip()
        return f"git stash pop --index {stash_ref} failed after pre-push isolation: {detail}"
    log(f"Step 11: restored pre-push isolation stash {stash_ref}")
    return None


def _capture_scope_snapshot(
    repo_root: Path,
    pathspecs: list[str],
) -> dict[str, Any]:
    """Capture exact worktree bytes and staged deletion state for wave-owned files."""
    snapshot: dict[str, Any] = {}
    for path in pathspecs:
        full_path = repo_root / path
        payload = full_path.read_bytes() if full_path.exists() else None
        snapshot[path] = {
            "payload": payload,
            "staged_delete": _is_staged_deletion(repo_root, path),
        }
    return snapshot


def _clear_scope_for_branch_rebind(
    repo_root: Path,
    *,
    tracked_paths: list[str],
    untracked_paths: list[str],
) -> None:
    """Temporarily clear a bounded dirty scope so the target checkout can proceed."""
    if tracked_paths:
        _run(
            ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", *tracked_paths],
            cwd=repo_root,
            timeout=120,
        )
    for path in untracked_paths:
        full_path = repo_root / path
        if full_path.exists():
            full_path.unlink()


def _restore_scope_snapshot(repo_root: Path, snapshot: dict[str, Any]) -> None:
    """Restore the captured bounded scope onto the rebound branch."""
    for path, entry in snapshot.items():
        if isinstance(entry, dict) and "payload" in entry:
            payload = entry.get("payload")
            staged_delete = bool(entry.get("staged_delete"))
        else:
            payload = entry
            staged_delete = False
        full_path = repo_root / path
        if payload is None:
            if full_path.exists():
                full_path.unlink()
        else:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(payload)
        if staged_delete:
            if full_path.exists():
                _run(["git", "rm", "--cached", "--", path], cwd=repo_root, check=False, timeout=30)
            else:
                _run(["git", "add", "-u", "--", path], cwd=repo_root, check=False, timeout=30)


def _restore_scope_snapshot_on_branch_failure(
    repo_root: Path,
    *,
    snapshot: dict[str, Any],
    expected_branch: str,
) -> None:
    """Restore a captured bounded scope when checkout failed before branch switch."""
    if not snapshot:
        return
    current_after_failure = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        check=False,
    ).stdout.strip()
    if current_after_failure != expected_branch:
        return
    try:
        _restore_scope_snapshot(repo_root, snapshot)
    except subprocess.CalledProcessError:
        pass


def _handoff_sha(handoff: dict[str, Any]) -> str:
    canonical = json.dumps(handoff, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _collect_wave_test_files(paths: list[str]) -> list[str]:
    """Return deduplicated pytest-style module paths from staged wave files."""
    test_files: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        if not isinstance(raw_path, str):
            continue
        normalized = raw_path.replace("\\", "/")
        if not normalized.endswith(".py"):
            continue
        if not (normalized.startswith("mu/tests/") or normalized.startswith("tests/")):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        test_files.append(normalized)
    return test_files


_STRUCTURAL_ARTIFACT_PREFIXES = (
    "mu/host/",
    "mu/programs/",
    "mu/substrate/",
    "mu/closures/",
    "mu/tests/l4_gates/",
    "tests/l4_gates/",
)

_RUNTIME_SUBSTRATE_PREFIXES = (
    "mu/host/",
    "mu/substrate/",
    "mu/closures/",
    "mu/bridge/",
    "mu/programs/",
    "rcx_pi/selfhost/",
    "mu/tools/compilers/",
)

_NON_GATE_TEST_DOMAINS = (
    "tests/engine/",
    "tests/parity/",
    "tests/structural/",
    "tests/tools/",
    "tests/docs/",
    "mu/tests/engine/",
    "mu/tests/parity/",
    "mu/tests/structural/",
    "mu/tests/tools/",
    "mu/tests/docs/",
)


def _select_l4_gate_test_files(paths: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if path.startswith(("tests/l4_gates/", "mu/tests/l4_gates/"))
    ]


def _select_non_gate_test_files(paths: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if path.startswith(_NON_GATE_TEST_DOMAINS)
    ]


def _summarize_structural_artifacts(changed_files: list[str], *, limit: int = 8) -> str:
    artifacts = [
        path for path in changed_files
        if path.startswith(_STRUCTURAL_ARTIFACT_PREFIXES)
    ]
    if not artifacts:
        artifacts = list(changed_files)
    visible = artifacts[:limit]
    suffix = ""
    if len(artifacts) > limit:
        suffix = f"; +{len(artifacts) - limit} more structural artifact(s)"
    return "; ".join(visible) + suffix


def _build_structural_post_gate_sweep(test_files: list[str], changed_files: list[str]) -> str:
    non_gate_tests = _select_non_gate_test_files(test_files) or _select_non_gate_test_files(changed_files)
    if non_gate_tests:
        return "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short " + " ".join(non_gate_tests)
    return "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/engine/ mu/tests/parity/ mu/tests/structural/"


def _contains_runtime_or_substrate_path(paths: list[str]) -> bool:
    for raw_path in paths:
        if not isinstance(raw_path, str):
            continue
        normalized = raw_path.replace("\\", "/")
        if normalized.startswith(_RUNTIME_SUBSTRATE_PREFIXES):
            return True
    return False


def _range_diff_paths_for_base(repo_root: Path, base_branch: str) -> list[str]:
    candidates: list[str] = []
    if base_branch:
        candidates.append(f"origin/{base_branch}")
        candidates.append(base_branch)
    candidates.append("origin/dev")
    candidates.append("dev")

    seen: set[str] = set()
    for ref in candidates:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        try:
            _run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=repo_root, timeout=10)
            proc = _run(["git", "diff", "--name-only", f"{ref}...HEAD"], cwd=repo_root, timeout=30)
        except subprocess.CalledProcessError:
            continue
        return _dedupe_repo_paths(proc.stdout.splitlines())
    return []


def _supervisor_wave_class_for_staged_scope(
    wave_class: str,
    *,
    staged_changed_files: list[str],
    branch_range_files: list[str],
) -> str:
    """Retarget post-structural staged repairs without faking runtime deltas."""
    normalized = str(wave_class or "").strip()
    if (
        normalized == "L4_STRUCTURAL"
        and not _contains_runtime_or_substrate_path(staged_changed_files)
        and _contains_runtime_or_substrate_path(branch_range_files)
    ):
        return "L4_ENABLER"
    return normalized


def _normalize_repo_relpath(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


def _is_tracker_relevant_path(path: str) -> bool:
    normalized = _normalize_repo_relpath(path)
    if not normalized or normalized in {"STATUS.md", "TASKS.md"}:
        return False
    if normalized.startswith(".github/workflows/"):
        return True
    if normalized.startswith("tools/checks/"):
        return True
    if normalized.startswith(
        (
            "mu/tools/agents/",
            "mu/tools/executors/",
            "mu/tools/checks/",
            "mu/tools/hooks/",
            "mu/tools/observability/",
            "mu/tools/recovery/",
        )
    ):
        return True
    if normalized.startswith("rcx_pi/selfhost/"):
        return True
    if normalized.startswith("mu/"):
        return not normalized.startswith(
            ("mu/docs/", "mu/tools/", "mu/scripts/", "mu/tests/")
        )
    return False


def _tracker_relevant_paths_for_handoff(
    files_to_stage: list[str],
    force_add_files: list[str] | None = None,
) -> list[str]:
    seen: set[str] = set()
    tracker_paths: list[str] = []
    for raw_path in [*(files_to_stage or []), *((force_add_files or []))]:
        if not isinstance(raw_path, str):
            continue
        normalized = _normalize_repo_relpath(raw_path)
        if not _is_tracker_relevant_path(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        tracker_paths.append(normalized)
    return tracker_paths


def _dirty_tracker_relevant_paths_for_handoff(
    repo_root: Path,
    files_to_stage: list[str],
    force_add_files: list[str] | None = None,
) -> list[str]:
    candidate_paths = _dedupe_repo_paths([*(files_to_stage or []), *((force_add_files or []))])
    if not candidate_paths:
        return []
    try:
        proc = _run(
            ["git", "status", "--porcelain", "--", *candidate_paths],
            cwd=repo_root,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        return _tracker_relevant_paths_for_handoff(files_to_stage, force_add_files)

    dirty_paths: set[str] = set()
    for line in proc.stdout.splitlines():
        parsed = _parse_porcelain_status_line(line)
        if parsed is None:
            continue
        _, raw_path = parsed
        path = _normalize_repo_relpath(raw_path)
        if path:
            dirty_paths.add(path)

    dirty_ordered = [path for path in candidate_paths if path in dirty_paths]
    return _tracker_relevant_paths_for_handoff(dirty_ordered, [])


def _staged_tracker_relevant_paths(repo_root: Path) -> list[str]:
    try:
        proc = _run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=repo_root,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        return []
    return _tracker_relevant_paths_for_handoff(proc.stdout.splitlines(), [])


def _tracker_file_will_be_staged(
    repo_root: Path,
    files_to_stage: list[str],
    force_add_files: list[str] | None = None,
) -> bool:
    tracker_paths = {"STATUS.md", "TASKS.md"}
    try:
        staged = _run(
            ["git", "diff", "--cached", "--name-only", "--", *sorted(tracker_paths)],
            cwd=repo_root,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        staged = None
    if staged is not None:
        for line in staged.stdout.splitlines():
            if _normalize_repo_relpath(line) in tracker_paths:
                return True

    candidate_paths = {
        _normalize_repo_relpath(path)
        for path in [*(files_to_stage or []), *((force_add_files or []))]
        if isinstance(path, str)
    }
    if not (candidate_paths & tracker_paths):
        return False

    try:
        proc = _run(
            ["git", "status", "--porcelain", "--", *sorted(tracker_paths)],
            cwd=repo_root,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        return False
    for line in proc.stdout.splitlines():
        parsed = _parse_porcelain_status_line(line)
        if parsed is None:
            continue
        _, raw_path = parsed
        if _normalize_repo_relpath(raw_path) in tracker_paths:
            return True
    return False


def _build_tracker_followup_note(*, wave_id: str, tracker_paths: list[str]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    preview = ", ".join(tracker_paths[:3])
    remainder = len(tracker_paths) - min(len(tracker_paths), 3)
    if remainder > 0:
        preview = f"{preview}, +{remainder} more"
    return (
        f"- Tracker sync follow-up ({stamp}, {wave_id}): same-wave follow-up commit touched "
        f"tracker-relevant file(s) without phase/task-state change: {preview}.\n"
    )


def _tracker_followup_mentions_paths(line: str, tracker_paths: list[str]) -> bool:
    return bool(tracker_paths) and all(path in line for path in tracker_paths)


def _tracker_followup_insert_index(canonical_idx: int, tracker_followup_indices: list[int]) -> int:
    following = [idx for idx in tracker_followup_indices if idx > canonical_idx]
    return max(following) if following else canonical_idx


def _sync_tracker_followup_line(
    lines: list[str],
    *,
    wave_id: str,
    canonical_idx: int,
    tracker_followup_indices: list[int],
    tracker_paths: list[str],
    tracker_file_staged: bool,
) -> tuple[bool, str | None, str | None]:
    followup_idx = tracker_followup_indices[0] if len(tracker_followup_indices) == 1 else None
    should_emit_followup = bool(tracker_paths) and (
        not tracker_file_staged or bool(tracker_followup_indices)
    )
    if not should_emit_followup:
        if followup_idx is None:
            return False, None, None
        del lines[followup_idx]
        return True, None, "removed"

    followup_line = _build_tracker_followup_note(
        wave_id=wave_id,
        tracker_paths=tracker_paths,
    )
    if len(tracker_followup_indices) > 1:
        existing_followup_covers_scope = any(
            _tracker_followup_mentions_paths(lines[idx], tracker_paths)
            for idx in tracker_followup_indices
        )
        if existing_followup_covers_scope and tracker_file_staged:
            return False, None, None
        insert_idx = _tracker_followup_insert_index(canonical_idx, tracker_followup_indices)
        lines.insert(insert_idx + 1, followup_line)
        return True, None, "inserted"

    if followup_idx is None:
        lines.insert(canonical_idx + 1, followup_line)
        return True, None, "inserted"

    if followup_idx == canonical_idx + 1:
        if lines[followup_idx] == followup_line:
            return False, None, None
        lines[followup_idx] = followup_line
        return True, None, "refreshed"

    del lines[followup_idx]
    if followup_idx < canonical_idx:
        canonical_idx -= 1
    lines.insert(canonical_idx + 1, followup_line)
    return True, None, "refreshed"


def _append_founder_override_to_tracker_note(
    note: Any,
    founder_override_token: str | None,
) -> Any:
    if not isinstance(note, str):
        return note
    token = _normalize_founder_override_token(founder_override_token)
    if not token:
        return note
    if _extract_founder_override_from_tracker_note(note):
        return note
    return note.rstrip() + (
        f" FOUNDER_OVERRIDE:{token} (standing pipeline-bug-fix authorization "
        "per memory feedback_autonomous_executor_fix.md; auto-appended by "
        "build_commit_handoff for commit-gate + pre-push adjacency-cap clearance)"
    )


def _build_default_tracker_note_text(
    *,
    wave_id: str,
    wave_class: str,
    target_gate_id: str,
    commit_message: str,
    files_to_stage: list[str],
    founder_override_token: str | None = None,
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    tracked_packet: str = "",
) -> str:
    """Render a contract-complete tracker note for ad hoc commit handoffs.

    When ``founder_override_token`` is provided (non-empty string), the token
    is auto-appended to the rendered note as
    ``FOUNDER_OVERRIDE:<token> (reason)`` so pre-push-fast L4 adjacency/rolling
    caps + supervisor Gate 8 can consume it without callers hand-crafting the
    append. Mirrors the manual-append pattern used repeatedly during
    2026-04-20 standalone commit work; mechanizes the skip-pattern.
    """
    summary = (commit_message or "").splitlines()[0].strip() or f"update {wave_id}"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    indicator_cmd = (
        f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
        f"--output {indicator_path}"
    )
    wave_files = [path for path in files_to_stage if isinstance(path, str)]
    test_files = _collect_wave_test_files(wave_files)
    packet_ref = _normalize_repo_relpath(tracked_packet) if tracked_packet else ""
    packet_text = f"Packet: `{packet_ref}`. " if packet_ref else ""

    if wave_class == "MAINTENANCE":
        if _tracker_sync_note is not None:
            fields = _tracker_sync_note.TrackerSyncNoteFields(
                wave_id=wave_id,
                title=summary,
                wave_class=wave_class,
                target_gate_id=target_gate_id,
                packet_ref=packet_ref,
                no_op_proof=(
                    "control-surface/docs/test-only wave-owned scope; no runtime/substrate files "
                    "declared in this handoff"
                ),
                defer_reason_code="PIPELINE_HARDENING",
                primary_blocker_class="INTEGRATION",
                primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
                indicator_artifact_ref=indicator_path,
                indicator_collection_command=indicator_cmd,
                unblocks_wave_id=(unblocks_wave_id or "").strip(),
                unblocks_runtime_blocker=(unblocks_runtime_blocker or "").strip(),
            )
            return _append_founder_override_to_tracker_note(
                _tracker_sync_note.render_tracker_sync_note(fields),
                founder_override_token,
            )
        note = (
            f"- Tracker sync note ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}, {wave_id}): "
            f"**{summary}.**. Class: {wave_class}. target_gate_id: {target_gate_id}. "
            f"{packet_text}"
            "no_op_proof: control-surface/docs/test-only wave-owned scope; no runtime/substrate files "
            "declared in this handoff. defer_reason_code: PIPELINE_HARDENING. "
        )
        if unblocks_wave_id:
            note += f"unblocks_wave_id: {unblocks_wave_id}. "
        if unblocks_runtime_blocker:
            note += f"unblocks_runtime_blocker: {unblocks_runtime_blocker}. "
        note += (
            "primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
            f"indicator_artifact_ref: {indicator_path}. indicator_collection_command: {indicator_cmd}. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD."
        )
        return _append_founder_override_to_tracker_note(note, founder_override_token)

    structural_kwargs: dict[str, str] = {}
    if wave_class == "L4_STRUCTURAL":
        gate_tests = _select_l4_gate_test_files(test_files)
        evidence_targets = gate_tests or ["mu/tests/l4_gates/"]
        contract_files: list[str] = []
        for path in [*wave_files, indicator_path]:
            normalized = str(path or "").strip()
            if normalized and normalized not in contract_files:
                contract_files.append(normalized)
        evidence_command = (
            "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            + " ".join(evidence_targets)
            + " && python3 tools/checks/enforce_l4_execution_contract.py --files "
            + " ".join(contract_files)
            + f" --wave-id {wave_id} --wave-class {wave_class}"
        )
        evidence_delta = (
            f"(1) Routed standalone commit handoff scopes {len(wave_files)} wave-owned file(s). "
            "(2) Evidence gate targets the L4 gate domain for structural runtime/substrate scope. "
            f"(3) Indicator artifact binds the wave to {indicator_path}."
        )
        progress_before = (
            "Standalone commit handoff regeneration had not yet bound the staged structural diff "
            "to a complete L4 tracker note, so pre-commit governance could misclassify it."
        )
        progress_after = (
            f"Standalone commit handoff for {wave_id} preserves L4_STRUCTURAL class, "
            f"{len(wave_files)} wave-owned file(s), and contract-complete structural metadata."
        )
        structural_kwargs = {
            "workload_target": "host_debt_reduction",
            "host_semantics_delta_before": (
                "staged runtime/substrate split requires governance as host-debt reduction, "
                "not a maintenance no-op"
            ),
            "host_semantics_delta_after": (
                "standalone regeneration preserves structural classification and leaves "
                "semantic authority checks to the L4 ratchets and post-gate sweep"
            ),
            "structural_artifact_ref": _summarize_structural_artifacts(wave_files),
            "post_gate_contract_sweep": _build_structural_post_gate_sweep(
                test_files,
                wave_files,
            ),
        }
    elif test_files:
        evidence_command = (
            "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short " + " ".join(test_files)
        )
        evidence_delta = (
            f"(1) Routed commit handoff scopes {len(wave_files)} wave-owned file(s). "
            f"(2) Evidence gate exercises {len(test_files)} wave-owned test module(s). "
            f"(3) Indicator artifact binds the wave to {indicator_path}."
        )
    else:
        evidence_command = indicator_cmd
        evidence_delta = (
            f"(1) Routed commit handoff scopes {len(wave_files)} wave-owned file(s). "
            "(2) No wave-owned pytest module was staged in this ad hoc handoff, so indicator collection is "
            "the mechanical evidence surface. "
            f"(3) Indicator artifact binds the wave to {indicator_path}."
        )
    progress_before = (
        "The routed commit handoff had not yet been bound to a contract-complete tracker note, so "
        "downstream L4 governance could fail during pre-push."
    )
    progress_after = (
        f"The routed commit handoff for {wave_id} is now bound to {len(wave_files)} wave-owned file(s), "
        f"{len(test_files)} wave-owned test module(s), and a canonical indicator artifact."
    )

    if _tracker_sync_note is not None:
        fields = _tracker_sync_note.TrackerSyncNoteFields(
            wave_id=wave_id,
            title=summary,
            wave_class="L4_ENABLER" if wave_class == "MAINTENANCE" else wave_class,
            target_gate_id=target_gate_id,
            packet_ref=packet_ref,
            evidence_command=evidence_command,
            evidence_delta=evidence_delta,
            progress_proof_before=progress_before,
            progress_proof_after=progress_after,
            primary_blocker_class="INTEGRATION",
            primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
            indicator_artifact_ref=indicator_path,
            indicator_collection_command=indicator_cmd,
            **structural_kwargs,
        )
        return _append_founder_override_to_tracker_note(
            _tracker_sync_note.render_tracker_sync_note(fields),
            founder_override_token,
        )

    structural_text = ""
    if structural_kwargs:
        structural_text = (
            f"workload_target: {structural_kwargs['workload_target']}. "
            f"host_semantics_delta_before: {structural_kwargs['host_semantics_delta_before']}. "
            f"host_semantics_delta_after: {structural_kwargs['host_semantics_delta_after']}. "
            f"structural_artifact_ref: {structural_kwargs['structural_artifact_ref']}. "
        )
    sweep_text = ""
    if structural_kwargs:
        sweep_text = (
            f"post_gate_contract_sweep: `{structural_kwargs['post_gate_contract_sweep']}`. "
        )
    return _append_founder_override_to_tracker_note(
        f"- Tracker sync note ({datetime.now(timezone.utc).strftime('%Y-%m-%d')}, {wave_id}): "
        f"**{summary}.**. Class: {wave_class}. target_gate_id: {target_gate_id}. "
        f"{packet_text}"
        f"{structural_text}"
        f"evidence_command: `{evidence_command}`. evidence_delta: {evidence_delta}. "
        f"progress_proof_before: {progress_before}. progress_proof_after: {progress_after}. "
        f"{sweep_text}"
        "primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. "
        f"indicator_artifact_ref: {indicator_path}. indicator_collection_command: {indicator_cmd}. "
        "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
        "boot0_track_id: V1. boot0_progress_state: HOLD.",
        founder_override_token,
    )


def _validate_tracker_note_text(
    *,
    tracker_note_text: str,
    wave_id: str,
    wave_class: str,
    target_gate_id: str,
) -> list[str]:
    """Reject incomplete tracker notes before the executor makes a local commit."""
    errors: list[str] = []
    note = tracker_note_text.strip()
    header_re = re.compile(
        rf"^- Tracker sync note \([^,]+,\s*{re.escape(wave_id)}\):"
    )
    if not header_re.search(note):
        errors.append(f"tracker_note_text must start with a canonical tracker note header for wave_id '{wave_id}'")

    required_literals = [
        "Class:",
        f"target_gate_id: {target_gate_id}",
        "primary_blocker_class:",
        "primary_invariant_id:",
        "indicator_artifact_ref:",
        "indicator_collection_command:",
        "bootstrap_endgame_policy:",
        "boot0_track_id:",
        "boot0_progress_state:",
    ]
    if wave_class in ("L4_ENABLER", "L4_STRUCTURAL"):
        required_literals.extend([
            "evidence_command:",
            "evidence_delta:",
            "progress_proof_before:",
            "progress_proof_after:",
        ])
    elif wave_class == "MAINTENANCE":
        required_literals.extend([
            "no_op_proof:",
            "defer_reason_code:",
        ])

    for literal in required_literals:
        if literal not in note:
            errors.append(f"tracker_note_text missing required field marker: {literal}")

    # 2026-06-01 (commit-evidence-guard-setroles-show): reject a tracker-note
    # evidence_command that reads env-AWARE EFFECTIVE role state instead of the
    # COMMITTED config. The 2026-05-30 standalone NEEDS_PHASE_B footgun paired a
    # committed-config claim with `python3 mu/tools/executors/set_roles.py --show`,
    # whose env-aware output (effective reviewer + an env-shadow warning)
    # contradicted the claim -- so the pre-commit supervisor rejected the package
    # only AFTER gates 1-10 had already passed, wasting a full supervisor cycle.
    # This is a NARROW literal-pattern guard scoped to the exact observed footgun
    # (an evidence_command containing BOTH `set_roles.py` AND `--show`), NOT a
    # general env-aware-command detector.
    evidence_command_value = _tracker_marker_value(note, "evidence_command")
    if "set_roles.py" in evidence_command_value and "--show" in evidence_command_value:
        errors.append(
            "tracker_note_text evidence_command reads env-aware EFFECTIVE role "
            "state (`set_roles.py --show`); use a committed-state read instead "
            "(e.g. `grep -A2 role_agents mu/tools/executors/executor_config.json` "
            "or `git diff`) so the evidence matches the committed-config claim"
        )

    return errors


def _continuation_record_path(repo_root: Path, wave_id: str) -> Path:
    return agent_bus_path(repo_root, _active_bus_dir(), "executors", f"commit_executor_{wave_id}.json")


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
    pre_push_isolation: dict[str, Any] | None = None,
    pre_push_restored_paths: list[str] | None = None,
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
    if pre_push_isolation:
        payload["pre_push_isolation"] = dict(pre_push_isolation)
    if pre_push_restored_paths:
        payload["pre_push_restored_paths"] = sorted(set(pre_push_restored_paths))
    preserved_bot_review_request_sha = existing_payload.get("bot_review_request_sha")
    preserved_commit_sha = existing_payload.get("commit_sha")
    if bot_review_request_sha:
        payload["bot_review_request_sha"] = bot_review_request_sha
    elif (
        preserved_commit_sha == commit_sha
        and isinstance(preserved_bot_review_request_sha, str)
        and preserved_bot_review_request_sha
    ):
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
    wave_id: str | None = None,
    handoff: dict[str, Any] | None = None,
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
        expected_wave_id = str(wave_id or "").strip()
        if not expected_wave_id or not _can_rekey_post_commit_continuation_to_handoff(
            handoff,
            wave_id=expected_wave_id,
            target_branch=target_branch,
        ):
            return None
        payload["handoff_sha"] = handoff_sha
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
        # HEAD may have moved forward from remediation commits.
        # Accept if commit_sha is an ancestor of current HEAD.
        try:
            merge_base = _run(
                ["git", "merge-base", "--is-ancestor", commit_sha, head_sha],
                cwd=repo_root, check=False,
            )
            if merge_base.returncode != 0:
                return None
            payload["commit_sha"] = head_sha
            reset_steps = _continuation_steps_for_new_commit(steps_completed)
            if reset_steps is None:
                return None
            payload["steps_completed"] = reset_steps
            payload.pop("bot_review_request_sha", None)
            payload.pop("pre_push_isolation", None)
            payload.pop("pre_push_restored_paths", None)
        except subprocess.CalledProcessError:
            return None
    non_transient_status = []
    non_transient_paths: list[str] = []
    for line in status_output:
        path_text = line[3:] if len(line) > 3 else line
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        if _is_transient_status_path(path_text):
            continue
        normalized_path = _normalize_repo_relpath(path_text)
        if normalized_path:
            non_transient_paths.append(normalized_path)
        non_transient_status.append(line)
    if non_transient_status:
        active_isolation = (
            payload.get("pre_push_isolation")
            if isinstance(payload.get("pre_push_isolation"), dict)
            else None
        )
        restored_paths_raw = payload.get("pre_push_restored_paths")
        restored_paths: set[str] = set()
        if isinstance(restored_paths_raw, list):
            restored_paths = {
                normalized
                for path in restored_paths_raw
                if (normalized := _normalize_repo_relpath(str(path)))
            }
        allowed_dirty_paths = restored_paths | _pre_push_isolation_paths(active_isolation)
        if not non_transient_paths or not set(non_transient_paths) <= allowed_dirty_paths:
            return None

    return payload


def _load_continuation_for_resume(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    """Load the persisted post-commit continuation record for ``--resume-continuation``.

    Mirrors the continuation-key derivation in the ``_run_commit_pipeline_impl``
    preamble (founder-override tracker-note append, ``target_branch``,
    ``handoff_sha``, bus-scoped record path) so this guard's verdict matches what
    the driver would actually resume from. Returns the continuation payload, or
    ``None`` when no valid resumable record exists. ``None`` is the fail-closed
    signal for ``--resume-continuation``: missing/foreign record, HEAD not at the
    recorded commit, wrong branch, or a worktree dirty outside the recorded
    isolation.

    Keep this derivation in sync with the ``_run_commit_pipeline_impl``
    continuation preamble; the driver owns the authoritative load and re-runs it
    once this guard falls through.
    """
    if not isinstance(handoff, dict):
        return None
    wave_id = str(handoff.get("wave_id") or "").strip()
    branch_prefix = str(handoff.get("branch_prefix") or "").strip()
    if not wave_id or not branch_prefix:
        return None
    # Mirror the driver's founder-override tracker-note append so the resume
    # handoff_sha matches the record the original run wrote (the override is
    # part of handoff_sha for derived control-surface L4_ENABLER handoffs).
    founder_override_token = _resolve_control_surface_founder_override_token(
        {
            "wave_id": wave_id,
            "wave_name": wave_id,
            "tracked_packet": handoff.get("tracked_packet", ""),
            "tracker_note_text": handoff.get("tracker_note_text", ""),
        },
        repo_root,
        embedded_handoff=handoff,
        wave_id=wave_id,
        wave_class=str(handoff.get("wave_class") or ""),
    )
    if founder_override_token:
        tracker_note_text = _append_founder_override_to_tracker_note(
            handoff.get("tracker_note_text", ""),
            founder_override_token,
        )
        if tracker_note_text != handoff.get("tracker_note_text", ""):
            handoff = {**handoff, "tracker_note_text": tracker_note_text}
    explicit_target_branch = handoff.get("target_branch")
    if isinstance(explicit_target_branch, str) and explicit_target_branch.strip():
        target_branch = explicit_target_branch.strip()
    else:
        target_branch = f"{branch_prefix}/{wave_id}"
    handoff_sha = _handoff_sha(handoff)

    def _load() -> dict[str, Any] | None:
        return _load_post_commit_continuation(
            _continuation_record_path(repo_root, wave_id),
            repo_root=repo_root,
            handoff_sha=handoff_sha,
            target_branch=target_branch,
            wave_id=wave_id,
            handoff=handoff,
        )

    if bus_dir is None:
        return _load()
    # Resolve the continuation path under the same bus the driver will use.
    try:
        resolve_agent_bus_dir(repo_root, bus_dir)
    except ExecutorCommonError:
        return None
    token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
    try:
        return _load()
    finally:
        _ACTIVE_BUS_DIR.reset(token)


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
    pre_push_isolation = result.get("pre_push_isolation")
    if not isinstance(pre_push_isolation, dict):
        pre_push_isolation = None
    pre_push_restored_paths_raw = result.get("pre_push_restored_paths")
    pre_push_restored_paths = (
        [
            _normalize_repo_relpath(str(path))
            for path in pre_push_restored_paths_raw
            if _normalize_repo_relpath(str(path))
        ]
        if isinstance(pre_push_restored_paths_raw, list)
        else None
    )
    _write_continuation_record(
        continuation_path,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
        commit_sha=commit_sha,
        receipt_decision=receipt_decision,
        steps_completed=steps_completed,
        pr_number=pr_number,
        bot_review_request_sha=bot_review_request_sha if isinstance(bot_review_request_sha, str) else None,
        pre_push_isolation=pre_push_isolation,
        pre_push_restored_paths=pre_push_restored_paths,
    )


def _continuation_steps_for_new_commit(steps_completed: Any) -> list[str] | None:
    """Return the bounded-resume baseline for a newly created local HEAD."""
    if not isinstance(steps_completed, list):
        return None
    try:
        git_commit_idx = steps_completed.index("git_commit")
    except ValueError:
        return None
    return list(steps_completed[:git_commit_idx + 1])


def _parse_porcelain_status_line(line: str) -> tuple[str, str] | None:
    raw_line = line.rstrip("\n")
    if not raw_line.strip():
        return None
    if len(raw_line) < 4:
        return None
    status_code = raw_line[:2]
    path_text = raw_line[3:]
    if " -> " in path_text:
        path_text = path_text.split(" -> ", 1)[1]
    if not path_text:
        return None
    return status_code, path_text


def _discard_worktree_path(
    repo_root: Path,
    *,
    status_code: str,
    file_path: str,
) -> None:
    if status_code == "??":
        _run(
            ["git", "clean", "-fd", "--", file_path],
            cwd=repo_root,
            timeout=10,
            check=False,
        )
        return
    _run(
        ["git", "checkout", "--", file_path],
        cwd=repo_root,
        timeout=10,
        check=False,
    )


def _discard_failed_adapter_partial_changes(
    repo_root: Path,
    *,
    log: Any,
) -> list[str]:
    """Discard partial index/worktree changes left by a failed remediation adapter.

    The bot-remediation adapter can raise (e.g. a timeout) AFTER it has already
    staged or modified files. The shared auto-defer helper
    (:func:`_classify_and_auto_defer_unremediated_bot_findings`) stages its
    report into a normal child commit, which would otherwise silently include
    any such partial edits. The no-change path
    reaches that helper only after ``git status`` proves the worktree clean; this
    restores the SAME precondition on the adapter-error/timeout path.

    The index is reset to HEAD so the child commit includes ONLY the deferred
    report the helper stages itself, then non-transient worktree residue is
    discarded (tracked files restored, untracked files removed). Transient bus
    runtime paths are left on disk so the pipeline's runtime state survives.
    Returns the discarded non-transient paths (for logging/tests).
    """
    # Unstage everything: a staged partial edit would otherwise enter the child commit.
    _run(["git", "reset", "-q", "HEAD"], cwd=repo_root, timeout=30, check=False)
    status_out = _run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        timeout=30,
        check=False,
    ).stdout
    discarded: list[str] = []
    for raw_line in status_out.splitlines():
        parsed = _parse_porcelain_status_line(raw_line)
        if parsed is None:
            continue
        _status_code, file_path = parsed
        if _is_transient_status_path(file_path):
            continue
        # Restore tracked files; remove untracked residue (incl. unstaged-new).
        _run(
            ["git", "checkout", "--", file_path],
            cwd=repo_root,
            timeout=10,
            check=False,
        )
        _run(
            ["git", "clean", "-fd", "--", file_path],
            cwd=repo_root,
            timeout=10,
            check=False,
        )
        discarded.append(file_path)
    if discarded:
        log(
            f"Step 15: discarded {len(discarded)} partial path(s) left by a "
            f"failed remediation adapter before auto-defer: {discarded}"
        )
    return discarded


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
    header_match = re.match(
        rf"^- Tracker sync note \(([^,]+),\s*{re.escape(wave_id)}\):\s*\*\*[^*]+\*\*",
        line,
    )
    if not header_match:
        return False
    return (
        bool(re.search(r"\bClass:\s*", line))
        or (
            "contract_path: classless FOUNDER_OVERRIDE comment-only runtime override" in line
            and f"FOUNDER_OVERRIDE:{wave_id}" in line
        )
    )


def _is_tracker_followup_note_line(line: str, wave_id: str) -> bool:
    return bool(re.match(
        rf"^- Tracker sync follow-up \(([^,]+),\s*{re.escape(wave_id)}\):",
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


def _matching_tracker_followup_indices_in_range(
    lines: list[str],
    wave_id: str,
    *,
    start_idx: int,
    end_idx: int,
) -> list[int]:
    return [
        idx
        for idx in range(start_idx, end_idx)
        if _is_tracker_followup_note_line(lines[idx].rstrip("\n"), wave_id)
    ]


def ensure_bot_remediation_tracker_followup(
    repo_root: Path,
    *,
    wave_id: str,
    scoped_files: list[str],
) -> dict[str, Any]:
    """Stage a same-wave TASKS follow-up when bot remediation touches tracked surfaces."""
    tracker_paths = _tracker_relevant_paths_for_handoff(scoped_files, [])
    if not tracker_paths:
        return {"updated": False, "tracker_paths": []}
    if any(path in {"TASKS.md", "STATUS.md"} for path in scoped_files):
        return {"updated": False, "tracker_paths": tracker_paths}

    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return {"updated": False, "tracker_paths": tracker_paths, "errors": ["TASKS.md not found"]}

    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return {
            "updated": False,
            "tracker_paths": tracker_paths,
            "errors": ["## Ra section not found in TASKS.md"],
        }

    canonical_tracker_indices = [
        idx
        for idx in _matching_tracker_note_indices_in_range(
            lines,
            wave_id,
            start_idx=ra_idx,
            end_idx=ra_end_idx,
        )
        if _is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    if len(canonical_tracker_indices) != 1:
        return {
            "updated": False,
            "tracker_paths": tracker_paths,
            "errors": [
                f"wave_id '{wave_id}' must have exactly one canonical tracker note before bot-remediation follow-up"
            ],
        }

    tracker_followup_indices = _matching_tracker_followup_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )

    followup_line = _build_tracker_followup_note(
        wave_id=wave_id,
        tracker_paths=tracker_paths,
    )
    updated = False
    if len(tracker_followup_indices) > 1:
        if any(
            _tracker_followup_mentions_paths(lines[idx], tracker_paths)
            for idx in tracker_followup_indices
        ):
            return {
                "updated": False,
                "tracker_paths": tracker_paths,
                "path": "TASKS.md",
            }
        insert_idx = _tracker_followup_insert_index(
            canonical_tracker_indices[0],
            tracker_followup_indices,
        )
        lines.insert(insert_idx + 1, followup_line)
        updated = True
    elif tracker_followup_indices:
        followup_idx = tracker_followup_indices[0]
        if lines[followup_idx] != followup_line:
            lines[followup_idx] = followup_line
            updated = True
    else:
        lines.insert(canonical_tracker_indices[0] + 1, followup_line)
        updated = True

    if updated:
        tasks_path.write_text("".join(lines), encoding="utf-8")
    return {
        "updated": updated,
        "tracker_paths": tracker_paths,
        "path": "TASKS.md",
    }


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
    if is_agent_bus_runtime_path(normalized):
        return ".agent_bus-*"
    for denied in FORCE_ADD_DENYLIST:
        if lowered.startswith(denied):
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


def _assert_current_pr_identity(
    pr_data: dict[str, Any],
    *,
    head_sha: str,
    target_branch: str,
) -> None:
    _assert_expected_pr_head(pr_data, head_sha)
    head_ref_name = pr_data.get("headRefName", "")
    if not isinstance(head_ref_name, str) or not head_ref_name:
        raise ValueError("PR review query missing headRefName")
    if head_ref_name != target_branch:
        raise ValueError(
            f"PR head branch moved from expected {target_branch!r} "
            f"to {head_ref_name!r}"
        )


def _refresh_pr_head_after_executor_update(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    previous_head_sha: str,
    target_branch: str,
    log: Any = None,
) -> tuple[str, dict[str, Any]]:
    refreshed_head_sha = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        timeout=10,
    ).stdout.strip()
    if not refreshed_head_sha:
        raise ValueError("local HEAD refresh returned an empty SHA")
    refreshed_pr_data = _query_pr_review_state(
        repo_root,
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number,
    )
    _assert_current_pr_identity(
        refreshed_pr_data,
        head_sha=refreshed_head_sha,
        target_branch=target_branch,
    )
    if log is not None and refreshed_head_sha != previous_head_sha:
        log(
            f"Step 15: refreshed PR head after bot remediation/auto-defer "
            f"{previous_head_sha[:8]} -> {refreshed_head_sha[:8]}"
        )
    return refreshed_head_sha, refreshed_pr_data


def _pr_is_draft(pr_data: dict[str, Any]) -> bool:
    is_draft = pr_data.get("isDraft")
    if not isinstance(is_draft, bool):
        raise ValueError("PR review query missing boolean isDraft")
    return is_draft


def _draft_pr_ready_failure_response(
    *,
    pr_number: str,
    result: dict[str, Any],
    detail: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "step": "ensure_review_clear_and_merge",
        "failure_class": "draft_pr_ready_failed",
        "errors": [f"Failed to mark draft PR #{pr_number} ready before merge_pr.sh: {detail}"],
        "steps_completed": result["steps_completed"],
        "pr_number": pr_number,
    }


def _ensure_current_draft_pr_ready_for_review(
    repo_root: Path,
    *,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    head_sha: str,
    target_branch: str,
    result: dict[str, Any],
    log: Any = None,
) -> dict[str, Any] | None:
    """Mark only the current executor-owned draft PR ready before final merge."""
    try:
        pr_data = _query_pr_review_state(
            repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
        )
        _assert_expected_pr_head(pr_data, head_sha)
        draft_state = pr_data.get("isDraft")
        if not isinstance(draft_state, bool):
            if log is not None:
                log(
                    f"Step 15: PR #{pr_number} draft state absent from review "
                    "payload; skipping draft-ready transition"
                )
            return None
        if not draft_state:
            return None
        _assert_current_pr_identity(
            pr_data,
            head_sha=head_sha,
            target_branch=target_branch,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return _draft_pr_ready_failure_response(
            pr_number=pr_number,
            result=result,
            detail=f"post-CI draft state refresh failed: {exc}",
        )

    if log is not None:
        log(
            f"Step 15: PR #{pr_number} is draft; marking ready for review "
            "before merge_pr.sh"
        )

    try:
        _run(["gh", "pr", "ready", pr_number], cwd=repo_root, timeout=30)
    except subprocess.CalledProcessError as exc:
        detail = _tail_failure_excerpt(
            exc.stderr or exc.stdout or "",
            limit=1200,
            max_lines=20,
        ) or f"exit {exc.returncode}"
        return _draft_pr_ready_failure_response(
            pr_number=pr_number,
            result=result,
            detail=f"gh pr ready failed: {detail}",
        )
    except subprocess.TimeoutExpired:
        return _draft_pr_ready_failure_response(
            pr_number=pr_number,
            result=result,
            detail="gh pr ready timed out",
        )

    try:
        refreshed_pr_data = _query_pr_review_state(
            repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
        )
        _assert_current_pr_identity(
            refreshed_pr_data,
            head_sha=head_sha,
            target_branch=target_branch,
        )
        if _pr_is_draft(refreshed_pr_data):
            return _draft_pr_ready_failure_response(
                pr_number=pr_number,
                result=result,
                detail="gh pr ready completed but GitHub still reports isDraft=true",
            )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return _draft_pr_ready_failure_response(
            pr_number=pr_number,
            result=result,
            detail=f"ready transition verification failed: {exc}",
        )

    if log is not None:
        log(f"Step 15: PR #{pr_number} marked ready for review")
    return None


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


def _is_blocking_connector_review_body(body: str) -> bool:
    return bool(BOT_BLOCKING_REVIEW_BADGE_RE.search(body or ""))


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
        try:
            pr_data = query_pr_state()
        except BOT_REVIEW_QUERY_TRANSIENT_ERRORS as exc:
            if time.time() >= deadline:
                effective_wait_seconds = int(max(wait_seconds, deadline - start_time))
                raise TimeoutError(
                    f"No current-head {BOT_REVIEW_LOGIN} review or issue-comment clearance "
                    f"for {head_sha[:8]} within {effective_wait_seconds}s; "
                    f"last review query error: {exc}"
                ) from exc
            if log is not None:
                log(
                    f"Waiting for {BOT_REVIEW_LOGIN} review signal on {head_sha[:8]} "
                    f"({poll_interval}s poll); review query failed transiently: {exc}"
                )
            time.sleep(poll_interval)
            continue
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


def _mint_bot_remediation_receipt(
    *,
    repo_root: Path,
    findings_addressed: list[dict[str, str]],
    scoped_files: list[str],
    round_num: int,
    wave_id: str,
) -> Path:
    """Mint a type-B (bot remediation) pre-commit receipt for the current staged state.

    Writes both the canonical hook-compatible receipt and a per-invocation
    receipt.  The hook checks decision + staged_sha — both are present.
    The receipt_type field distinguishes this from a full supervisor receipt
    (type A) for audit purposes.
    """
    staged_diff = subprocess.run(
        ["git", "diff", "--cached", "--binary"],
        capture_output=True, cwd=repo_root, check=True,
    ).stdout
    staged_sha = hashlib.sha256(staged_diff).hexdigest()

    receipt = {
        "decision": "COMMIT_GO",
        "staged_sha": staged_sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "receipt_type": "bot_remediation",
        "wave_id": wave_id,
        "remediation_round": round_num,
        "findings_addressed": findings_addressed,
        "scoped_files": scoped_files,
    }

    meta_dir = agent_bus_path(repo_root, _active_bus_dir(), "meta")
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Write canonical hook-compatible receipt
    canonical = meta_dir / "pre_commit_receipt.json"
    canonical.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    # Write per-invocation receipt for audit trail
    receipts_dir = meta_dir / "pre_commit_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    ts_slug = receipt["timestamp_utc"].replace(":", "-").replace("+", "p")
    unique_suffix = uuid.uuid4().hex[:8]
    per_invocation = receipts_dir / f"receipt_{ts_slug}_{unique_suffix}.json"
    per_invocation.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    return per_invocation


def _invalidate_bot_remediation_hook_receipt(repo_root: Path, *, reason: str) -> bool:
    """Invalidate the canonical bot-remediation hook receipt if one exists."""
    canonical = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "meta",
        "pre_commit_receipt.json",
    )
    try:
        receipt = json.loads(canonical.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(receipt, dict):
        return False
    if receipt.get("receipt_type") != "bot_remediation":
        return False
    receipt["decision"] = "COMMIT_BLOCKED"
    receipt["invalidated_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["invalidation_reason"] = reason
    canonical.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return True


def _extract_review_findings(
    pr_data: dict[str, Any],
    head_sha: str,
    *,
    result: dict[str, Any],
    pr_number: str,
) -> dict[str, Any]:
    """Extract bot review findings from PR data.

    Returns dict with 'outcome' key:
      'clean'        — no findings, safe to merge
      'bot_findings' — bot findings found (includes 'bot_findings' list)
      'error'        — hard error (includes 'response' dict)
    """
    _assert_expected_pr_head(pr_data, head_sha)
    issue_comment_outcome = _current_head_connector_issue_comment_outcome(
        pr_data, head_sha,
    )
    if issue_comment_outcome is not None:
        if issue_comment_outcome["kind"] == "usage_limit":
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"{BOT_REVIEW_LOGIN} issue comment reported usage-limit exhaustion"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
        if issue_comment_outcome["kind"] == "other":
            return {"outcome": "bot_findings", "bot_findings": [{
                "author": issue_comment_outcome["author"],
                "body": issue_comment_outcome["body"][:500],
                "path": "", "line": None,
            }]}

    review_decision = pr_data.get("reviewDecision", "")
    if review_decision == "CHANGES_REQUESTED":
        return {"outcome": "error", "response": {
            "status": "error", "step": "ensure_review_clear_and_merge",
            "errors": ["reviewDecision is CHANGES_REQUESTED"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number}}

    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    bot_review_findings: list[dict[str, Any]] = []
    for review in latest_reviews:
        author = review.get("author", {}).get("login", "")
        state = review.get("state", "")
        is_bot = _is_bot_review_author(author)
        commit_oid = review.get("commit", {}).get("oid", "")
        body = str(review.get("body") or "")
        if is_bot and commit_oid == head_sha and _is_blocking_connector_review_body(body):
            bot_review_findings.append({
                "author": author,
                "body": body[:500],
                "path": "", "line": None,
            })
        if not is_bot and state == "CHANGES_REQUESTED":
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Human reviewer {author} requested changes"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
    if bot_review_findings:
        return {"outcome": "bot_findings", "bot_findings": bot_review_findings}

    threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    current_review_cycle_floor = _current_review_cycle_floor_timestamp(
        pr_data, head_sha,
    )
    bot_findings: list[dict[str, Any]] = []
    for thread in threads:
        if thread.get("isResolved"):
            continue
        latest_comment = _latest_relevant_thread_comment(
            thread, floor_timestamp=current_review_cycle_floor,
        )
        if latest_comment is None:
            continue
        author = latest_comment.get("author", {}).get("login", "")
        is_bot = _is_bot_review_author(author)
        if not is_bot:
            return {"outcome": "error", "response": {
                "status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Unresolved human review thread from {author}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}}
        if thread.get("isOutdated"):
            continue
        bot_findings.append({
            "author": author,
            "body": latest_comment.get("body", "")[:500],
            "path": latest_comment.get("path", ""),
            "line": latest_comment.get("line"),
        })

    if bot_findings:
        return {"outcome": "bot_findings", "bot_findings": bot_findings}
    return {"outcome": "clean"}


def _extract_timeout_verified_current_head_findings(
    pr_data: dict[str, Any],
    head_sha: str,
    *,
    result: dict[str, Any],
    pr_number: str,
) -> dict[str, Any]:
    """Extract findings after review-wait timeout only with current-head proof."""
    _assert_expected_pr_head(pr_data, head_sha)
    issue_comment_outcome = _current_head_connector_issue_comment_outcome(
        pr_data, head_sha,
    )
    has_current_head_bot_signal = (
        _has_fresh_connector_review(pr_data, head_sha)
        or issue_comment_outcome is not None
    )
    findings_result = _extract_review_findings(
        pr_data, head_sha, result=result, pr_number=pr_number,
    )
    if (
        not has_current_head_bot_signal
        and findings_result["outcome"] == "bot_findings"
    ):
        return {"outcome": "unverified"}
    return findings_result


def _build_bot_remediation_prompt(
    bot_findings: list[dict[str, Any]],
    *,
    wave_id: str,
    pr_number: str,
    remediation_round: int,
) -> str:
    """Build a prompt for the bridge adapter to fix bot review findings."""
    lines = [
        f"You are a code-fix agent. A bot reviewer found issues on PR #{pr_number} "
        f"(wave: {wave_id}). Fix each issue directly in the files.",
        "",
        "Rules:",
        "- Edit the files mentioned in the findings. You may also create new files",
        "  in the SAME directories as the finding paths if the fix requires a helper.",
        "  Do NOT create files in unrelated directories — the staging guard will reject them.",
        "- Do NOT run git commands, tests, or hooks. Just edit files.",
        f"- This is remediation round {remediation_round}/{BOT_REMEDIATION_MAX_ROUNDS}.",
        "",
        "## Findings",
        "",
    ]
    for i, finding in enumerate(bot_findings, 1):
        path = finding.get("path", "(unknown)")
        line = finding.get("line")
        body = finding.get("body", "")
        loc = f"{path}:{line}" if line else path
        lines.append(f"### Finding {i}: `{loc}`")
        lines.append("")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def _check_pr_conflict_state(
    repo_root: Path,
    *,
    pr_number: str,
    log: Any = None,
) -> str | None:
    """Return a human-readable indicator if a PR needs base-branch refresh.

    2026-04-17 learning: when a PR has ``mergeable: CONFLICTING`` or
    ``mergeStateStatus: DIRTY``, GitHub Actions silently skips
    ``pull_request``-triggered workflows (no merge-ref computable), so the
    required-checks list is permanently incomplete. Polling such a PR
    wastes the full CI timeout without a chance of success.

    2026-05-27 learning: GitHub can also report a PR as behind the base
    branch via REST ``mergeable_state=behind`` while the GraphQL fields used by
    ``gh pr view`` do not expose that exact state. That stale-base state must
    take the same merge-base refresh path as CONFLICTING/DIRTY so the executor
    does not wait on or merge a stale head.

    Returns a short state string when the PR cannot complete the intended
    merge path until dev is merged in; returns ``None`` when the PR is either
    mergeable or in a transient state that should be polled normally. Fails
    open on any ``gh`` error so that the normal Step 14 path still runs: the
    pre-check is a performance optimization, not a correctness guard.
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "mergeable,mergeStateStatus"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        if log is not None:
            log(f"Step 14 pre-check: gh pr view error ({exc}); skipping")
        return None
    if proc.returncode != 0:
        if log is not None:
            log(
                f"Step 14 pre-check: gh pr view exit={proc.returncode}; "
                "skipping"
            )
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        if log is not None:
            log("Step 14 pre-check: malformed gh pr view JSON; skipping")
        return None
    mergeable = data.get("mergeable")
    merge_state = data.get("mergeStateStatus")
    if mergeable == "CONFLICTING":
        return "mergeable=CONFLICTING"
    if merge_state == "DIRTY":
        return "mergeStateStatus=DIRTY"
    if merge_state == "BEHIND":
        return "mergeStateStatus=BEHIND"

    try:
        repo_owner, repo_name = _parse_origin_owner_repo(repo_root)
    except (subprocess.SubprocessError, OSError, IndexError) as exc:
        if log is not None:
            log(f"Step 14 pre-check: cannot determine repo for REST PR state ({exc}); skipping")
        return None
    try:
        rest_proc = subprocess.run(
            ["gh", "api", f"repos/{repo_owner}/{repo_name}/pulls/{pr_number}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        if log is not None:
            log(f"Step 14 pre-check: gh api PR state error ({exc}); skipping")
        return None
    if rest_proc.returncode != 0:
        if log is not None:
            log(
                f"Step 14 pre-check: gh api PR state exit={rest_proc.returncode}; "
                "skipping"
            )
        return None
    try:
        rest_data = json.loads(rest_proc.stdout or "{}")
    except json.JSONDecodeError:
        if log is not None:
            log("Step 14 pre-check: malformed gh api PR state JSON; skipping")
        return None
    mergeable_state = str(rest_data.get("mergeable_state") or "").lower()
    if mergeable_state == "behind":
        return "mergeable_state=behind"
    return None


def _resolve_tasks_md_tracker_note_conflict(path: Path) -> bool:
    """Resolve a TASKS.md merge conflict IFF every conflict block contains
    only tracker-note lines on both sides.

    Returns ``True`` if the file was successfully resolved (all conflict
    markers removed; both sides' tracker-note lines preserved in
    chronological order: origin block first, HEAD block second — matches
    the 2026-04-17 learning recipe "keeping both notes in chronological
    merge order; merged-first wave's note first, then this wave's").

    Returns ``False`` WITHOUT modifying the file if any conflict block
    contains non-tracker-note content or if conflict markers are
    malformed (nested / dangling). Caller must abort the merge in that
    case.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "<<<<<<<" not in text:
        return True  # no conflict to resolve
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    head_buf: list[str] = []
    origin_buf: list[str] = []
    state = "normal"  # 'normal' | 'head' | 'origin'
    for line in lines:
        if line.startswith("<<<<<<<"):
            if state != "normal":
                return False  # nested / malformed
            head_buf = []
            origin_buf = []
            state = "head"
            continue
        if line.startswith("=======") and state == "head":
            state = "origin"
            continue
        if line.startswith(">>>>>>>"):
            if state != "origin":
                return False
            if not _is_tracker_note_only(head_buf) or not _is_tracker_note_only(
                origin_buf
            ):
                return False
            new_lines.extend(origin_buf)
            new_lines.extend(head_buf)
            state = "normal"
            continue
        if state == "head":
            head_buf.append(line)
        elif state == "origin":
            origin_buf.append(line)
        else:
            new_lines.append(line)
    if state != "normal":
        return False  # dangling conflict marker
    path.write_text("".join(new_lines), encoding="utf-8")
    return True


def _is_tracker_note_only(buf: list[str]) -> bool:
    """Every non-blank line in *buf* must be a tracker-sync line.

    Tracker-sync lines include canonical notes and same-wave follow-ups,
    including strike-through closed notes. Leading whitespace is allowed
    (indented continuation lines inside a note).
    """
    for raw in buf:
        stripped = raw.rstrip("\n").strip()
        if not stripped:
            continue
        if not (
            stripped.startswith("- Tracker sync note (")
            or stripped.startswith("- Tracker sync follow-up (")
            or stripped.startswith("- ~~Tracker sync note (")
            or stripped.startswith("- ~~Tracker sync follow-up (")
        ):
            return False
    return True


_P0IA_BASE_AUTHORITY_WAVE_ID = (
    "roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20"
)
_P0IA_BASE_AUTHORITY_PR_NUMBER = "1223"
_P0IA_BASE_AUTHORITY_BASE_BRANCH = "dev"
_P0IA_BASE_AUTHORITY_TARGET_BRANCH = (
    "jabramsja/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-"
    "2026-08-20-restart-2026-08-21"
)
_P0IA_BASE_AUTHORITY_PACKET = (
    "reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-"
    "authority-2026-08-20_2026-08-20.md"
)
_P0IA_BASE_AUTHORITY_INDICATOR = (
    "reports/l4_wave_indicators/"
    "roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json"
)
_P0IA_BASE_AUTHORITY_ALLOWED_SCOPE = frozenset(
    {
        "TASKS.md",
        "mu/tests/docs/test_growth_caps.py",
        "mu/tests/tools/test_candidate_authority.py",
        "mu/tests/tools/test_launch_wave.py",
        "mu/tests/tools/test_phase_b_executor.py",
        "mu/tools/executors/candidate_authority.py",
        "mu/tools/executors/launch_wave.py",
        "mu/tools/executors/phase_b_executor.py",
        _P0IA_BASE_AUTHORITY_PACKET,
        (
            "reports/deferred/non_blocking/"
            "roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-"
            "2026-08-20_bridge_nonblockers.md"
        ),
        _P0IA_BASE_AUTHORITY_INDICATOR,
    }
)
_P0IC4R_QUEUE_LABELS = (
    "ROLES-ALL-CODEX-PR1219-P0IC0-THEATER-ALLOWLIST-EXPIRY-RENEWAL",
    "ROLES-ALL-CODEX-PR1219-P0IC1-LINKED-WORKTREE-REPO-IDENTITY",
    "ROLES-ALL-CODEX-PR1219-P0IC2-COMMIT-GENERATED-GOVERNANCE-AUTHORITY",
    "ROLES-ALL-CODEX-PR1219-P0IC3-IDEMPOTENT-GENERATED-GOVERNANCE-CONTINUATION",
    "ROLES-ALL-CODEX-PR1219-P0IC4R-TASKS-BASE-AUTHORITY-RECOVERY",
    "ROLES-ALL-CODEX-PR1219-P0IA-PRE-REVIEW-CANDIDATE-AUTHORITY",
    "ROLES-ALL-CODEX-PR1219-P0IAH-CANDIDATE-AUTHORITY-TRUST-ORDERING-HARDENING",
    "ROLES-ALL-CODEX-PR1219-P0IM-CODEX-MODEL-BOOTSTRAP",
    "ROLES-ALL-CODEX-PR1219-P0IB-PRECOMMIT-INVENTORY-AUTHORITY",
    "ROLES-ALL-CODEX-PR1219-P0T1-TERMINAL-IDENTITY-QUESTION-JOURNAL",
    "ROLES-ALL-CODEX-PR1219-P0T2-PRIVATE-REVIEW-DURABILITY",
    "ROLES-ALL-CODEX-PR1219-P0T3-PROCESS-TREE-CLOSURE",
    "ROLES-ALL-CODEX-PR1219-P0T4-INV2-SEMANTIC-PROOF",
    "ROLES-ALL-CODEX-PR1219-P0R2-ROLE-MODEL-AUTHORITY",
    "ROLES-ALL-CODEX-PR1219-P1-BRIDGE-TERMINAL-REFUSAL",
    "ROLES-ALL-CODEX-PR1219-P2-REVIEW-BINDING",
    "ROLES-ALL-CODEX-PR1219-P3-RECOVERY-CHECKPOINTS",
    "ROLES-ALL-CODEX-PR1219-P4-RECOVERY-AUTHORITY-ISOLATION",
    "ROLES-ALL-CODEX-PR1219-P5-FINAL-RECONCILIATION",
    "LAUNCH-WAVE-DETERMINISTIC-CANDIDATE-CARRY-FORWARD-BUILDER",
    "PHASE-A-POST-REMEDIATION-LINE-REF-PREBRIDGE-GUARD",
    "PIPELINE-FIX-61",
    "PIPELINE-FIX-54A3",
    "PIPELINE-FIX-60B",
    "PIPELINE-FIX-60C",
    "PIPELINE-FIX-60D",
    "CANONICAL-DOCS-TRUTH-INTEGRATION",
    "PBNOGO-INTEGRATION",
    "PREPUSH-RECOVERY-CONTEXT-AUTHORITY",
    "PIPELINE-FIX-56",
    "PIPELINE-FIX-52",
    "PIPELINE-FIX-55",
    "PIPELINE-FIX-53",
    "OBSERVER-DURABILITY",
    "PIPELINE-FIX-50",
    "PIPELINE-FIX-57",
    "PAGER-ORCHESTRATOR-LABEL-TRUTH",
    "L4-GROWTH-CAP-PREBUMP-BUILDER",
    "BRIDGE-REVIEW-PRESERVATION-ARTIFACT-BOUNDS",
    "BOT-REMEDIATION-PREPUSH-SELECTOR-BOUNDS",
    "PIPELINE-NR5-DEFECT-HANDOFF-TRUTH",
    "ORCHESTRATOR-SWITCH-DRIFT-FIX",
    "PRECOMMIT-L4-AUTH-ANCHOR-RETENTION-FIX",
    "GENERIC-NEXT-ROUTE-RECONCILIATION",
    "RECEIPT-COMMIT-ROBUSTNESS-BOUNDED-SUCCESSORS",
    "DIALECTIC-CONTINUATION-DELIVERY-AND-LINEAGE",
    "PR-LIVE-CENSUS-RECONCILIATION",
    "PR-DISPOSITION-EXECUTION",
    "NEVER-BEHIND-FLEET-AUTHORITY",
    "NIGHTLY-ADMISSION-INTEGRATION",
    "NIGHTLY-DEADLINE-TELEMETRY-PROOF",
    "PIPELINE-AGENT-MODEL-EFFORT-BUILDER",
    "QUESTION-CHECKPOINT-AND-INV2-AUTHORITY",
    "CODEX-EFFECTIVE-MODEL-CATALOG-AUTHORITY",
    "PIPELINE-FIX-62C",
    "LEGACY-N3-LOCAL-EVIDENCE-ADJUDICATION",
    "MU-COINDUCTION-PRODUCTION-PROOF",
    "MU-FIXPOINT-PRODUCTION-PROOF",
    "MU-EVIDENCE-RESIDUES",
    "MU-OPTIMIZATION-LAST",
)
_PROGRAM_QUEUE_ROW_RE = re.compile(r"^(?P<num>\d+)\.\s+\*\*\[(?P<label>[^\]]+)\]")


def _is_p0ia_base_authority_identity(
    *,
    wave_id: str | None,
    pr_number: str,
    base_branch: str,
    branch_name: str,
) -> bool:
    return (
        str(wave_id or "") == _P0IA_BASE_AUTHORITY_WAVE_ID
        and str(pr_number or "").strip().lstrip("#") == _P0IA_BASE_AUTHORITY_PR_NUMBER
        and str(base_branch or "") == _P0IA_BASE_AUTHORITY_BASE_BRANCH
        and str(branch_name or "") == _P0IA_BASE_AUTHORITY_TARGET_BRANCH
    )


def _well_formed_conflict_markers(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "<<<<<<<" not in text:
        return False
    state = "normal"
    for line in text.splitlines():
        if line.startswith("<<<<<<<"):
            if state != "normal":
                return False
            state = "head"
            continue
        if line.startswith("======="):
            if state != "head":
                return False
            state = "origin"
            continue
        if line.startswith(">>>>>>>"):
            if state != "origin":
                return False
            state = "normal"
    return state == "normal"


def _read_tasks_merge_stage_texts(repo_root: Path) -> tuple[str, str] | None:
    try:
        ls_proc = subprocess.run(
            ["git", "ls-files", "-u", "--", "TASKS.md"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if ls_proc.returncode != 0:
        return None
    stages: dict[int, tuple[str, str]] = {}
    for raw in (ls_proc.stdout or "").splitlines():
        if "\t" not in raw:
            return None
        meta, path = raw.split("\t", 1)
        fields = meta.split()
        if len(fields) != 3:
            return None
        mode, oid, stage_text = fields
        if path != "TASKS.md" or mode not in {"100644", "100755"}:
            return None
        try:
            stage = int(stage_text)
        except ValueError:
            return None
        if stage in stages:
            return None
        stages[stage] = (mode, oid)
    if 2 not in stages or 3 not in stages:
        return None
    texts: list[str] = []
    for stage in (2, 3):
        try:
            blob = subprocess.run(
                ["git", "show", f":{stage}:TASKS.md"],
                cwd=repo_root,
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if blob.returncode != 0:
            return None
        try:
            texts.append(blob.stdout.decode("utf-8"))
        except UnicodeDecodeError:
            return None
    return texts[0], texts[1]


def _tracker_value(note: str, marker: str) -> str:
    return _tracker_marker_value(
        note,
        marker,
        marker_names=_BUILDER_TRACKER_MARKER_NAMES,
    ).strip()


def _tracker_path_value(note: str, marker: str) -> str:
    value = _tracker_value(note, marker)
    if value.startswith("`"):
        return _strip_tracker_inline_code(value).strip()
    return value.strip("` .")


def _p0ia_tracker_note_valid(note_line: str) -> bool:
    note = note_line.rstrip("\n")
    if _validate_tracker_note_text(
        tracker_note_text=note,
        wave_id=_P0IA_BASE_AUTHORITY_WAVE_ID,
        wave_class="L4_ENABLER",
        target_gate_id="G8",
    ):
        return False
    if _tracker_value(note, "Class").rstrip(".") != "L4_ENABLER":
        return False
    if _tracker_value(note, "target_gate_id").strip("` .") != "G8":
        return False
    if _tracker_path_value(note, "Packet").rstrip(".") != _P0IA_BASE_AUTHORITY_PACKET:
        return False
    if (
        _tracker_path_value(note, "indicator_artifact_ref").rstrip(".")
        != _P0IA_BASE_AUTHORITY_INDICATOR
    ):
        return False
    if _extract_founder_override_from_tracker_note(note) != _P0IA_BASE_AUTHORITY_WAVE_ID:
        return False
    return f"FOUNDER_OVERRIDE:{_P0IA_BASE_AUTHORITY_WAVE_ID}" in note


_P0IA_FOLLOWUP_RE = re.compile(
    rf"^- Tracker sync follow-up \([^,]+,\s*"
    rf"{re.escape(_P0IA_BASE_AUTHORITY_WAVE_ID)}\): "
    r"same-wave follow-up commit touched tracker-relevant file\(s\) "
    r"without phase/task-state change: (?P<paths>.+)\.$"
)


def _p0ia_followup_valid(line: str) -> bool:
    match = _P0IA_FOLLOWUP_RE.match(line.rstrip("\n"))
    if match is None:
        return False
    raw_paths = match.group("paths")
    if "(+" in raw_paths:
        return False
    paths = [_normalize_repo_relpath(part) for part in raw_paths.split(",")]
    if not paths:
        return False
    for path in paths:
        if (
            not path
            or path.startswith("/")
            or path == "."
            or path.startswith("../")
            or "/../" in path
            or path not in _P0IA_BASE_AUTHORITY_ALLOWED_SCOPE
        ):
            return False
    return True


def _p0ia_records_from_stage2_tasks(text: str) -> list[str] | None:
    lines = text.splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None
    matching_notes = _matching_tracker_note_indices_in_range(
        lines,
        _P0IA_BASE_AUTHORITY_WAVE_ID,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_notes = [
        idx
        for idx in matching_notes
        if _is_canonical_tracker_note_line(
            lines[idx].rstrip("\n"),
            _P0IA_BASE_AUTHORITY_WAVE_ID,
        )
    ]
    if len(matching_notes) != 1 or len(canonical_notes) != 1:
        return None
    note_idx = canonical_notes[0]
    note_line = lines[note_idx]
    if not note_line.endswith("\n") or not _p0ia_tracker_note_valid(note_line):
        return None
    records = [note_line]
    followup_indices = _matching_tracker_followup_indices_in_range(
        lines,
        _P0IA_BASE_AUTHORITY_WAVE_ID,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    for idx in sorted(followup_indices):
        if idx <= note_idx:
            return None
        line = lines[idx]
        if not line.endswith("\n") or not _p0ia_followup_valid(line):
            return None
        records.append(line)
    if len(set(records)) != len(records):
        return None
    return records


def _p0ia_records_from_stage3_tasks(text: str) -> list[str] | None:
    lines = text.splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None
    records: list[str] = []
    note_indices = _matching_tracker_note_indices_in_range(
        lines,
        _P0IA_BASE_AUTHORITY_WAVE_ID,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    followup_indices = _matching_tracker_followup_indices_in_range(
        lines,
        _P0IA_BASE_AUTHORITY_WAVE_ID,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    if len(note_indices) > 1:
        return None
    if note_indices:
        records.append(lines[note_indices[0]])
    records.extend(lines[idx] for idx in sorted(followup_indices))
    if len(set(records)) != len(records):
        return None
    return records


def _program_queue_text(text: str) -> str | None:
    start = text.find("## PROGRAM QUEUE")
    if start == -1:
        return None
    end = text.find("## NON-LAUNCHABLE PROGRAM GOVERNANCE AND HISTORY", start)
    if end == -1:
        return None
    return text[start:end]


def _queue_entry_texts(program_queue_text: str) -> dict[int, str] | None:
    lines = program_queue_text.splitlines(keepends=True)
    starts: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        match = _PROGRAM_QUEUE_ROW_RE.match(line)
        if match is not None:
            starts.append((idx, int(match.group("num")), match.group("label")))
    if len(starts) != len(_P0IC4R_QUEUE_LABELS):
        return None
    entries: dict[int, str] = {}
    for ordinal, (line_idx, row_num, _label) in enumerate(starts):
        next_idx = starts[ordinal + 1][0] if ordinal + 1 < len(starts) else len(lines)
        entries[row_num] = "".join(lines[line_idx:next_idx])
    return entries


def _stage3_program_queue_is_p0ic4r_contract(text: str) -> bool:
    queue = _program_queue_text(text)
    if queue is None:
        return False
    entries = _queue_entry_texts(queue)
    if entries is None:
        return False
    rows: list[tuple[int, str, str]] = []
    for row_num in sorted(entries):
        first_line = entries[row_num].splitlines()[0]
        match = _PROGRAM_QUEUE_ROW_RE.match(first_line)
        if match is None:
            return False
        rows.append((row_num, match.group("label"), entries[row_num]))
    if [row for row, _label, _entry in rows] != list(range(len(_P0IC4R_QUEUE_LABELS))):
        return False
    labels = [label for _row, label, _entry in rows]
    if labels != list(_P0IC4R_QUEUE_LABELS) or len(set(labels)) != len(labels):
        return False
    for row_num in range(4):
        if "LANDED" not in rows[row_num][2]:
            return False
    row5 = rows[5][2]
    if "BLOCKED" not in row5 or "P0IC4R" not in row5 or "LANDED" in row5:
        return False
    builder_entry = rows[19][2]
    required_builder_fragments = (
        "one canonical Phase-A-safe packet identity",
        "fail before dispatch",
        "reviewed lock authority",
        "Phase B handoff",
        "normalized alias/source files",
        "must not enter or delay P0IC4R/P0IA",
    )
    return all(fragment in builder_entry for fragment in required_builder_fragments)


def _stage3_p0ia_insert_index(stage3_text: str, *, note_already_present: bool) -> int | None:
    lines = stage3_text.splitlines(keepends=True)
    ra_idx, ra_end_idx = _find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None
    if note_already_present:
        note_indices = _matching_tracker_note_indices_in_range(
            lines,
            _P0IA_BASE_AUTHORITY_WAVE_ID,
            start_idx=ra_idx,
            end_idx=ra_end_idx,
        )
        if len(note_indices) != 1:
            return None
        insert_idx = note_indices[0] + 1
        while (
            insert_idx < ra_end_idx
            and _is_tracker_followup_note_line(
                lines[insert_idx].rstrip("\n"),
                _P0IA_BASE_AUTHORITY_WAVE_ID,
            )
        ):
            insert_idx += 1
    else:
        tracker_note_indices = [
            idx
            for idx in range(ra_idx + 1, ra_end_idx)
            if lines[idx].lstrip().startswith("- Tracker sync note")
        ]
        insert_idx = (tracker_note_indices[-1] + 1) if tracker_note_indices else ra_idx + 1
    return len("".join(lines[:insert_idx]))


def _resolve_tasks_md_p0ia_base_authority_conflict(repo_root: Path) -> bool:
    tasks_path = repo_root / "TASKS.md"
    if not _well_formed_conflict_markers(tasks_path):
        return False
    stage_texts = _read_tasks_merge_stage_texts(repo_root)
    if stage_texts is None:
        return False
    stage2_text, stage3_text = stage_texts
    if not _stage3_program_queue_is_p0ic4r_contract(stage3_text):
        return False
    stage2_records = _p0ia_records_from_stage2_tasks(stage2_text)
    if stage2_records is None:
        return False
    stage3_records = _p0ia_records_from_stage3_tasks(stage3_text)
    if stage3_records is None:
        return False
    source_record_set = set(stage2_records)
    if any(record not in source_record_set for record in stage3_records):
        return False
    note_already_present = bool(stage3_records and stage3_records[0] == stage2_records[0])
    if stage3_records and not note_already_present:
        return False
    missing_records = [record for record in stage2_records if record not in stage3_records]
    insert_at = _stage3_p0ia_insert_index(
        stage3_text,
        note_already_present=note_already_present,
    )
    if insert_at is None:
        return False
    inserted_text = "".join(missing_records)
    final_text = stage3_text[:insert_at] + inserted_text + stage3_text[insert_at:]
    if _program_queue_text(final_text) != _program_queue_text(stage3_text):
        return False
    if final_text[:insert_at] + final_text[insert_at + len(inserted_text):] != stage3_text:
        return False
    tmp_path = tasks_path.with_name(f".{tasks_path.name}.p0ia-base-authority.tmp")
    try:
        tmp_path.write_text(final_text, encoding="utf-8")
        tmp_path.replace(tasks_path)
    except OSError:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        return False
    return True


# ── Growth-cap conflict resolution (mechanical CAP_* base+union + comment union) ──
# A second known-mechanical merge conflict, alongside TASKS.md tracker notes:
# when two waves each bump a CAP_* growth cap in mu/tests/docs/test_growth_caps.py,
# the cap line collides every time the base branch advances. Like the TASKS.md
# resolver, this is gated in TWO layers — the filename gate inside
# _try_auto_resolve_pr_conflict (the conflicted set must be a subset of the known
# files) AND this content-level guard (every conflict block on BOTH sides must be
# purely CAP_* assignment lines, comment lines, and/or blanks). Any other line
# fails closed WITHOUT modifying the file, exactly as
# _resolve_tasks_md_tracker_note_conflict does.
_GROWTH_CAP_ASSIGN_RE = re.compile(
    r"^[ \t]*CAP_[A-Za-z0-9_]+[ \t]*=[ \t]*\d+[ \t]*(?:#.*)?$"
)
_GROWTH_CAP_PARSE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<name>CAP_[A-Za-z0-9_]+)[ \t]*=[ \t]*"
    r"(?P<value>\d+)[ \t]*(?:#(?P<comment>.*))?$"
)
_GROWTH_CAP_COMMENT_RE = re.compile(r"^[ \t]*#.*$")
# Each per-wave inline annotation is ``+N for <files> (...)``; the leading ``+N``
# is the file count that wave added above the previous cap.
_GROWTH_CAP_INCREMENT_RE = re.compile(r"^\+(\d+)\b")


def _annotation_increment(annotation: str) -> int:
    """File-count one inline growth-cap increment annotation contributes.

    Returns ``N`` for a ``+N for …`` annotation, else ``0`` (a non-increment note
    — e.g. a bare policy remark — contributes no file count). The conflict
    resolver sums these over the UNIONed annotations so a resolved CAP_* COVERS
    every distinct file EITHER side added, instead of taking the MAX of either
    side's total (which silently drops a file one side added that the other lacks
    — the confirmed ``land_stranded_pr`` bring-current undercount).
    """
    match = _GROWTH_CAP_INCREMENT_RE.match(annotation.strip())
    return int(match.group(1)) if match else 0


def _annotation_identity(annotation: str) -> str:
    """Dedup identity for one inline growth-cap increment annotation.

    Two annotations that name the SAME added file(s) are the SAME increment even
    when their parenthetical provenance differs (e.g. the same wave re-annotated
    the cap on the two merge sides). Identity is the ``+N for <subject>`` SUBJECT
    — the text after ``for`` up to the provenance ``(`` — whitespace-normalized;
    the leading ``+N`` count and the trailing ``( … )`` provenance are dropped. A
    non-increment note (no leading ``+N``) keys on its OWN full text, so genuinely
    distinct notes still union.

    The UNION must dedup by this identity, NOT by the full annotation string: a
    file BOTH sides added but annotated with different wording (origin's
    ``+1 for test_x.py (wave, note-a)`` vs HEAD's ``+1 for test_x.py (wave,
    note-b)``) is two distinct full strings but ONE file. Summing ``+N`` over a
    full-string-deduped union double-counts that file and over-bumps the cap
    (e.g. ``+1`` + ``+1`` → ``146`` where the merged tree only grew by one to
    ``145``). Keying on file identity counts each distinct file ONCE.
    """
    stripped = annotation.strip()
    match = _GROWTH_CAP_INCREMENT_RE.match(stripped)
    if match is None:
        return stripped  # non-increment note keys on its own full text
    rest = stripped[match.end():].lstrip()  # drop the leading "+N"
    if rest[:4].lower() == "for ":
        rest = rest[4:].lstrip()  # drop an optional leading "for "
    paren = rest.find("(")
    if paren != -1:
        rest = rest[:paren]  # drop the trailing "( … )" provenance
    return " ".join(rest.split())  # whitespace-normalized file subject


def _is_growth_cap_line_only(buf: list[str]) -> bool:
    """Every non-blank line in *buf* must be a CAP_* assignment line or a
    standalone comment line — the only known-mechanical content of a
    test_growth_caps.py conflict block. Blank lines are allowed.

    Any other line (code, a ``BASELINE_*`` assignment, prose) marks the block as
    a real semantic conflict, so the caller must fail closed. Mirrors
    :func:`_is_tracker_note_only`.
    """
    for raw in buf:
        stripped = raw.rstrip("\n")
        if not stripped.strip():
            continue
        if _GROWTH_CAP_ASSIGN_RE.match(stripped) or _GROWTH_CAP_COMMENT_RE.match(
            stripped
        ):
            continue
        return False
    return True


def _merge_growth_cap_block(
    origin_buf: list[str], head_buf: list[str]
) -> list[str] | None:
    """Merge the two sides of ONE growth-cap conflict block.

    Per-``CAP_*`` BASE+UNION value + UNION of per-wave inline-comment annotations
    (origin annotations first, then HEAD's not-yet-seen — the same origin-first
    keep-both order :func:`_resolve_tasks_md_tracker_note_conflict` uses), plus
    any unioned standalone comment lines. The union dedups by FILE IDENTITY
    (:func:`_annotation_identity`), NOT by full annotation string, so a file BOTH
    sides added with different wording counts ONCE — summing ``+N`` over a
    full-string-deduped union would over-bump the cap by re-counting that file.

    The resolved value COVERS the actual merged file count, NOT ``max(totals)``.
    Each side's cap = an undocumented BASE (the cap value minus the file counts
    its own inline ``+N for …`` annotations enumerate) plus that side's documented
    increments. Because the annotation log is append-only across the shared
    history, ``cap_value - own_increment_sum`` is the SAME undocumented base on
    both sides, so the resolved value is that base plus the file count of the
    UNIONed annotations — base + every distinct file EITHER side added. ``max`` of
    the two totals instead drops any file one side added that the other lacks
    (head adds 1, origin adds 3 distinct ⇒ the merged tree needs +4 but ``max``
    grants only +3), which stranded the bring-current commit at the growth-cap
    gate (the confirmed PR #1107 ``assert 336 <= 335``). The base is taken as the
    LARGER of the two per-side bases so a non-append-only history still never
    resolves BELOW either side's own cap; a side that annotates no files degrades
    to its full value as base (i.e. ``max`` for that side — the safe floor).

    Returns the merged, newline-terminated lines, or ``None`` if a CAP_* line
    cannot be parsed (malformed) so the caller fails closed. A resolved value that
    STILL cannot cover the merged tree (undocumented files unique to each side) is
    caught downstream WITHOUT new machinery: the bring-current ``git commit``
    re-runs the growth-cap gate, which fails closed and aborts the merge.
    """
    cap_order: list[str] = []
    cap_anns: dict[str, list[str]] = {}
    cap_ann_ids: dict[str, set[str]] = {}  # file-identity dedup keys per CAP_*
    cap_indent: dict[str, str] = {}
    cap_has_comment: dict[str, bool] = {}
    cap_bases: dict[str, list[int]] = {}  # per-side (value - own increment sum)
    comment_lines: list[str] = []
    seen_comments: set[str] = set()
    for buf in (origin_buf, head_buf):  # origin (merged-first) before HEAD
        for raw in buf:
            stripped = raw.rstrip("\n")
            if not stripped.strip():
                continue
            match = _GROWTH_CAP_PARSE_RE.match(stripped)
            if match is not None:
                name = match.group("name")
                value = int(match.group("value"))
                if name not in cap_anns:
                    cap_order.append(name)
                    cap_anns[name] = []
                    cap_ann_ids[name] = set()
                    cap_indent[name] = match.group("indent")
                    cap_has_comment[name] = False
                    cap_bases[name] = []
                comment = match.group("comment")
                side_increment_sum = 0
                if comment is not None:
                    cap_has_comment[name] = True
                    side_seen_ids: set[str] = set()
                    for ann in comment.split(";"):
                        ann = ann.strip()
                        if not ann:
                            continue
                        identity = _annotation_identity(ann)
                        # This side's own documented increment: count each distinct
                        # file ONCE even if the side lists it twice, so the per-side
                        # base (value - increment) stays the true undocumented base.
                        if identity not in side_seen_ids:
                            side_seen_ids.add(identity)
                            side_increment_sum += _annotation_increment(ann)
                        # UNION across sides, deduped by FILE IDENTITY (not full
                        # string): a file both sides annotated with different wording
                        # is one file, counted once below.
                        if identity not in cap_ann_ids[name]:
                            cap_ann_ids[name].add(identity)
                            cap_anns[name].append(ann)
                # This side's undocumented base = its cap value minus the files its
                # OWN annotations enumerate. Append-only history ⇒ the same base on
                # both sides; keeping a per-side list lets us take the safe (larger)
                # base when the two diverge.
                cap_bases[name].append(value - side_increment_sum)
                continue
            if _GROWTH_CAP_COMMENT_RE.match(stripped):
                key = stripped.strip()
                if key not in seen_comments:
                    seen_comments.add(key)
                    comment_lines.append(stripped)
                continue
            # _is_growth_cap_line_only already filtered to cap/comment/blank, so a
            # parse miss here means a malformed CAP_* line — fail closed.
            return None
    merged: list[str] = []
    for name in cap_order:
        indent = cap_indent[name]
        # base + UNION of both sides' added files (the +N sum over the UNIONed
        # annotations) — COVERS every distinct file either side added, unlike
        # max(totals), which drops the files unique to the lower-total side.
        base = max(cap_bases[name]) if cap_bases[name] else 0
        union_increment = sum(
            _annotation_increment(ann) for ann in cap_anns[name]
        )
        resolved_value = base + union_increment
        if cap_has_comment[name] and cap_anns[name]:
            merged.append(
                f"{indent}{name} = {resolved_value}  # {'; '.join(cap_anns[name])}\n"
            )
        else:
            merged.append(f"{indent}{name} = {resolved_value}\n")
    merged.extend(f"{line}\n" for line in comment_lines)
    return merged


def _resolve_growth_caps_conflict(path: Path) -> bool:
    """Resolve a mu/tests/docs/test_growth_caps.py merge conflict IFF every
    conflict block on BOTH sides contains only CAP_* assignment lines, comment
    lines, and/or blanks.

    Rewrites each block as per-``CAP_*`` BASE+UNION value (covering the merged
    file count, not ``max(totals)``) + UNION of per-wave inline-comment
    annotations. Returns ``False`` WITHOUT modifying the file on any
    non-mechanical line or malformed / nested / dangling markers, so the caller
    aborts the merge. Mirrors :func:`_resolve_tasks_md_tracker_note_conflict`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "<<<<<<<" not in text:
        return True  # no conflict to resolve
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    head_buf: list[str] = []
    origin_buf: list[str] = []
    state = "normal"  # 'normal' | 'head' | 'origin'
    for line in lines:
        if line.startswith("<<<<<<<"):
            if state != "normal":
                return False  # nested / malformed
            head_buf = []
            origin_buf = []
            state = "head"
            continue
        if line.startswith("=======") and state == "head":
            state = "origin"
            continue
        if line.startswith(">>>>>>>"):
            if state != "origin":
                return False
            if not _is_growth_cap_line_only(head_buf) or not _is_growth_cap_line_only(
                origin_buf
            ):
                return False
            merged = _merge_growth_cap_block(origin_buf, head_buf)
            if merged is None:
                return False
            new_lines.extend(merged)
            state = "normal"
            continue
        if state == "head":
            head_buf.append(line)
        elif state == "origin":
            origin_buf.append(line)
        else:
            new_lines.append(line)
    if state != "normal":
        return False  # dangling conflict marker
    path.write_text("".join(new_lines), encoding="utf-8")
    return True


# Public test seams. The growth-cap conflict resolver and the two annotation
# helpers behind its BASE+UNION cap value — the ``+N`` file count an inline
# annotation carries (:func:`_annotation_increment`) and the file-identity dedup
# key the cross-side UNION counts by (:func:`_annotation_identity`) — are
# exercised directly by the stranded-PR-landing regression suite. These public
# names delegate to the canonical underscore-prefixed implementations above so
# the suite can exercise the contract without reaching into a module-private
# helper (the test-integrity gate forbids private-attr access in tests).
def annotation_increment(annotation: str) -> int:
    """Public seam over :func:`_annotation_increment`."""
    return _annotation_increment(annotation)


def annotation_identity(annotation: str) -> str:
    """Public seam over :func:`_annotation_identity`."""
    return _annotation_identity(annotation)


def resolve_growth_caps_conflict(path: Path) -> bool:
    """Public seam over :func:`_resolve_growth_caps_conflict`."""
    return _resolve_growth_caps_conflict(path)


def _try_auto_resolve_pr_conflict(
    repo_root: Path,
    *,
    pr_number: str,
    base_branch: str,
    branch_name: str,
    wave_id: str | None = None,
    log: Any = None,
) -> dict[str, Any]:
    """Attempt automatic merge-base resolution for a stale-base PR.

    2026-04-17 learning recipe mechanized: on detection of a conflicting
    PR, fetch the base branch, merge it in, resolve the KNOWN-MECHANICAL
    conflicts, commit via ``RCX_SKIP_RECEIPT_CHECK=1``, and push.

    Two-layer fail-closed gate (the filename subset is necessary but NOT
    sufficient):
      (i)  FILENAME GATE — the conflicted set must be a NON-EMPTY SUBSET of
           {``TASKS.md``, ``mu/tests/docs/test_growth_caps.py``}; any other file
           aborts the merge.
      (ii) PER-FILE CONTENT-LEVEL GUARD — each conflicted file is dispatched to
           its own resolver (TASKS.md → tracker-note keep-both;
           test_growth_caps.py → per-CAP_* BASE+UNION value (covering the merged
           file count) + UNION of per-wave inline comments). A resolver that finds
           non-mechanical content in any block returns ``False`` WITHOUT modifying
           the file, so the merge aborts.

    Any other file (filename gate), a non-mechanical/semantic conflict inside an
    allowed file (content guard), or a subprocess error aborts the merge and
    returns an error for the caller to surface. The caller (bring-current AND the
    Step-14 pre-CI gate / CI-wait midpoll / late merge retry) shares this one path.

    Returns a dict:
      resolved: bool — True if no refresh needed OR auto-resolve succeeded + pushed
      action: str — 'no_action' | 'clean_merge' | 'tasks_md_resolved'
                    | 'mechanical_conflict_resolved' | 'aborted'
      detail: str — human-readable explanation
    """
    conflict_state = _check_pr_conflict_state(
        repo_root, pr_number=pr_number, log=log
    )
    if conflict_state is None:
        return {
            "resolved": True,
            "action": "no_action",
            "detail": "PR not in CONFLICTING/DIRTY/BEHIND state",
        }
    if log is not None:
        log(
            f"Step 14 auto-resolve: PR #{pr_number} {conflict_state}; "
            f"attempting merge of origin/{base_branch} into {branch_name}"
        )
    try:
        subprocess.run(
            ["git", "fetch", "origin", base_branch],
            cwd=repo_root,
            check=True,
            timeout=60,
            capture_output=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git fetch origin {base_branch} failed: {exc}",
        }
    try:
        merge_proc = subprocess.run(
            ["git", "merge", f"origin/{base_branch}", "--no-edit"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git merge origin/{base_branch} subprocess error: {exc}",
        }
    if merge_proc.returncode == 0:
        push_ok, push_err = _push_branch(repo_root, branch_name)
        if push_ok:
            if log is not None:
                log(
                    f"Step 14 auto-resolve: clean merge of origin/{base_branch} + pushed"
                )
            return {
                "resolved": True,
                "action": "clean_merge",
                "detail": f"merged origin/{base_branch} cleanly and pushed",
            }
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"clean merge but push failed: {push_err}",
        }
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"git diff failed after merge conflict: {exc}",
        }
    conflicted = [
        line.strip() for line in diff_proc.stdout.splitlines() if line.strip()
    ]
    # Known-mechanical conflict files, each mapped to its content-level resolver.
    # GROWTH_CAP_TEST_RELPATH is the canonical growth-cap relpath (defined with
    # the growth-cap auto-bump section); it resolves at call time.
    content_resolvers = {
        "TASKS.md": _resolve_tasks_md_tracker_note_conflict,
        GROWTH_CAP_TEST_RELPATH: _resolve_growth_caps_conflict,
    }
    # (i) FILENAME GATE: the conflicted set must be a NON-EMPTY SUBSET of the two
    # known-mechanical files. A conflict in ANY other file fails closed — the
    # subset is necessary but NOT sufficient (the per-file content guard below is
    # the second layer). Generalizes the prior conflicted == ["TASKS.md"] gate.
    disallowed = [rel for rel in conflicted if rel not in content_resolvers]
    if not conflicted or disallowed:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": (
                f"conflict in non-TASKS.md/non-growth-cap files: "
                f"{disallowed or conflicted}; manual recovery required"
            ),
        }
    # (ii) PER-FILE CONTENT-LEVEL GUARD: dispatch each conflicted file to its own
    # resolver. Each returns False WITHOUT modifying the file on any non-mechanical
    # content or malformed markers, so the helper aborts the WHOLE merge — a
    # semantic conflict INSIDE an allowed file still fails closed.
    tasks_md_base_authority_resolved = False
    for rel in conflicted:
        resolved = content_resolvers[rel](repo_root / rel)
        if (
            not resolved
            and rel == "TASKS.md"
            and conflicted == ["TASKS.md"]
            and _is_p0ia_base_authority_identity(
                wave_id=wave_id,
                pr_number=pr_number,
                base_branch=base_branch,
                branch_name=branch_name,
            )
        ):
            resolved = _resolve_tasks_md_p0ia_base_authority_conflict(repo_root)
            tasks_md_base_authority_resolved = resolved
        if not resolved:
            _abort_merge(repo_root, log=log)
            if rel == "TASKS.md":
                if _is_p0ia_base_authority_identity(
                    wave_id=wave_id,
                    pr_number=pr_number,
                    base_branch=base_branch,
                    branch_name=branch_name,
                ):
                    detail = (
                        "TASKS.md conflict is neither tracker-note-only nor the exact "
                        "P0IA stage-3 base-authority shape; manual recovery required"
                    )
                else:
                    detail = (
                        "TASKS.md conflict includes non-tracker-note content; "
                        "manual recovery required"
                    )
            else:
                detail = (
                    f"{rel} conflict includes non-CAP/non-comment content; "
                    "manual recovery required"
                )
            return {
                "resolved": False,
                "action": "aborted",
                "detail": detail,
            }
    try:
        subprocess.run(
            ["git", "add", "--", *conflicted],
            cwd=repo_root,
            check=True,
            timeout=20,
            capture_output=True,
        )
        commit_env = {**os.environ, "RCX_SKIP_RECEIPT_CHECK": "1"}
        subprocess.run(
            ["git", "commit", "--no-edit"],
            cwd=repo_root,
            check=True,
            timeout=60,
            capture_output=True,
            env=commit_env,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        _abort_merge(repo_root, log=log)
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"known-mechanical conflict resolved but commit failed: {exc}",
        }
    push_ok, push_err = _push_branch(repo_root, branch_name)
    if not push_ok:
        return {
            "resolved": False,
            "action": "aborted",
            "detail": f"merge + resolve succeeded but push failed: {push_err}",
        }
    # Preserve the pre-existing action label for the TASKS.md-only path so the
    # established Step-14 auto-resolve contract stays green; the growth-cap (or
    # combined) path reports the generalized mechanical-resolve action.
    if tasks_md_base_authority_resolved:
        action = "tasks_md_base_authority_resolved"
    elif conflicted == ["TASKS.md"]:
        action = "tasks_md_resolved"
    else:
        action = "mechanical_conflict_resolved"
    if log is not None:
        log(
            "Step 14 auto-resolve: merged origin/"
            + base_branch
            + f" + resolved known-mechanical conflict(s) {conflicted} + pushed"
        )
    return {
        "resolved": True,
        "action": action,
        "detail": (
            f"merged origin/{base_branch}, resolved {conflicted} "
            "(TASKS.md keep-both or exact P0IA stage-3 base authority / "
            "growth-cap base+union), committed with "
            "RCX_SKIP_RECEIPT_CHECK, pushed"
        ),
    }


def _abort_merge(repo_root: Path, *, log: Any = None) -> None:
    """Best-effort `git merge --abort` — swallows errors."""
    try:
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=repo_root,
            timeout=20,
            capture_output=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        pass
    if log is not None:
        log("Step 14 auto-resolve: merge aborted")


def _push_branch(repo_root: Path, branch_name: str) -> tuple[bool, str]:
    """`git push --no-verify origin <branch>` with error capture."""
    # --no-verify: same rationale as step 12 — pre-push gate already ran in step 11.
    try:
        subprocess.run(
            ["git", "push", "--no-verify", "origin", branch_name],
            cwd=repo_root,
            check=True,
            timeout=120,
            capture_output=True,
        )
        return True, ""
    except subprocess.CalledProcessError as exc:
        return False, f"exit={exc.returncode}: {exc.stderr.decode('utf-8', errors='replace') if exc.stderr else ''}"
    except (subprocess.SubprocessError, OSError) as exc:
        return False, str(exc)


def _extract_ci_failure_excerpt(text: str, *, max_lines: int = 12) -> str:
    """Return compact failure lines from GitHub Actions log text."""
    interesting: list[str] = []
    markers = (
        "assertionerror",
        "failed ",
        " failures ",
        "==== failures",
        "##[error]",
        "error:",
        "traceback",
    )
    for raw_line in (text or "").splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", raw_line).strip()
        lowered = line.lower()
        if not line or not any(marker in lowered for marker in markers):
            continue
        interesting.append(line[-500:])
    return "\n".join(interesting[-max_lines:])


def _summarize_required_ci_failures(repo_root: Path, pr_number: str) -> dict[str, Any]:
    """Gather failed required check names and short GitHub Actions failure excerpts."""
    summary: dict[str, Any] = {"checks_output": "", "failures": []}
    try:
        checks = _run(
            ["gh", "pr", "checks", pr_number, "--required"],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        summary["checks_output"] = f"gh pr checks failed while summarizing CI: {exc}"
        return summary

    checks_output = (checks.stdout or checks.stderr or "").strip()
    summary["checks_output"] = checks_output
    failing_names: list[str] = []
    for line in checks_output.splitlines():
        fields = [field.strip() for field in line.split("\t") if field.strip()]
        lowered = line.lower()
        if len(fields) >= 2 and fields[1].lower() in {"fail", "failed", "failure"}:
            failing_names.append(fields[0])
        elif any(token in lowered for token in ("\tfail\t", "\tfailed\t", "\tfailure\t")) and fields:
            failing_names.append(fields[0])

    try:
        view = _run(
            ["gh", "pr", "view", pr_number, "--json", "statusCheckRollup"],
            cwd=repo_root,
            check=False,
            timeout=60,
        )
        payload = json.loads(view.stdout or "{}")
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        payload = {}

    failures: list[dict[str, str]] = []
    for check in payload.get("statusCheckRollup", []) or []:
        if not isinstance(check, dict):
            continue
        conclusion = str(check.get("conclusion") or "").upper()
        name = str(check.get("name") or "")
        if conclusion not in {"FAILURE", "TIMED_OUT", "CANCELLED"}:
            continue
        if failing_names and name and name not in failing_names:
            continue
        details_url = str(check.get("detailsUrl") or "")
        failure = {
            "name": name,
            "workflow": str(check.get("workflowName") or ""),
            "conclusion": conclusion,
            "details_url": details_url,
            "excerpt": "",
        }
        match = re.search(r"/actions/runs/(\d+)", details_url)
        if match:
            try:
                run_log = _run(
                    ["gh", "run", "view", match.group(1), "--log-failed"],
                    cwd=repo_root,
                    check=False,
                    timeout=90,
                )
                failure["excerpt"] = _extract_ci_failure_excerpt(run_log.stdout or run_log.stderr or "")
            except (subprocess.SubprocessError, OSError):
                failure["excerpt"] = ""
        failures.append(failure)

    if not failures:
        failures = [
            {"name": name, "workflow": "", "conclusion": "FAILURE", "details_url": "", "excerpt": ""}
            for name in failing_names
        ]
    summary["failures"] = failures
    if failures:
        compact = []
        for failure in failures[:3]:
            line = failure.get("name", "") or "unknown-check"
            if failure.get("workflow"):
                line = f"{line} ({failure['workflow']})"
            excerpt = str(failure.get("excerpt") or "").splitlines()
            if excerpt:
                line = f"{line}: {excerpt[-1]}"
            compact.append(line)
        summary["summary"] = "Failed required CI: " + "; ".join(compact)
    elif checks_output:
        summary["summary"] = "Required CI failed; gh pr checks output: " + checks_output.replace("\n", " | ")[:1000]
    else:
        summary["summary"] = "Required CI failed; no failed check details available"
    return summary


def _wait_ci_failure_class(ci_failure: dict[str, Any]) -> str:
    failures = ci_failure.get("failures", [])
    if not isinstance(failures, list):
        return "unknown_error"
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        conclusion = str(failure.get("conclusion") or "").upper()
        if conclusion == "FAILURE" or failure.get("excerpt"):
            return "test_failure"
    return "unknown_error"


def _rollup_check_name(check: dict[str, Any]) -> str:
    return str(
        check.get("name")
        or check.get("context")
        or check.get("workflowName")
        or "unknown"
    ).strip()


def _rollup_check_state(check: dict[str, Any]) -> tuple[str, str]:
    for field in ("conclusion", "state", "status"):
        value = check.get(field)
        if value:
            return field, str(value).upper()
    return "", ""


def _summarize_pr_check_surface(checks: Any) -> dict[str, Any]:
    if not isinstance(checks, list):
        missing = list(EXPECTED_PR_CHECK_SURFACE)
        return {
            "status": "pending",
            "summary": (
                "statusCheckRollup was not a list; "
                "missing expected check(s): " + ", ".join(missing)
            ),
            "present_checks": [],
            "missing_expected_checks": missing,
            "pending_checks": ["statusCheckRollup=invalid"],
            "failing_checks": [],
        }

    present_names: set[str] = set()
    pending: list[str] = []
    failing: list[str] = []

    for check in checks:
        if not isinstance(check, dict):
            pending.append(f"{check}=invalid")
            continue
        name = _rollup_check_name(check)
        if name:
            present_names.add(name)
        state_field, state = _rollup_check_state(check)
        label = f"{name}={state or 'PENDING'}"
        if state in CI_REQUIRED_PASSING_STATES:
            continue
        if state_field == "conclusion" or state in CI_REQUIRED_FAILING_STATES:
            failing.append(label)
        else:
            pending.append(label)

    missing = sorted(set(EXPECTED_PR_CHECK_SURFACE) - present_names)
    if failing:
        status = "failed"
        summary = "failing PR check(s): " + ", ".join(failing)
    elif missing or pending:
        status = "pending"
        summary_parts = []
        if missing:
            summary_parts.append("missing expected check(s): " + ", ".join(missing))
        if pending:
            summary_parts.append("pending PR check(s): " + ", ".join(pending))
        summary = "; ".join(summary_parts)
    else:
        status = "passed"
        summary = "expected PR check surface green"

    return {
        "status": status,
        "summary": summary,
        "present_checks": sorted(present_names),
        "missing_expected_checks": missing,
        "pending_checks": pending,
        "failing_checks": failing,
    }


def _fetch_pr_check_surface_rollup(repo_root: Path, pr_number: str) -> Any:
    result = _run(
        ["gh", "pr", "view", pr_number, "--json", "statusCheckRollup"],
        cwd=repo_root,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    payload = json.loads(result.stdout or "{}")
    if not isinstance(payload, dict):
        return []
    return payload.get("statusCheckRollup", [])


def _surface_failure_is_stale_cancellation(snapshot: dict[str, Any]) -> bool:
    """True iff a ``failed`` surface's failing checks are ALL concurrent-merge
    ``CANCELLED`` runs of EXPECTED REQUIRED checks -- the stale artifact the
    post-resolve await waits to be refreshed -- and NOT a genuine failure.

    After a successful mid-poll conflict resolve the base-merge repush
    re-triggers the previously-skipped REQUIRED ``pull_request`` gate workflows
    (the ``EXPECTED_PR_CHECK_SURFACE`` set), but until they re-register the
    surface still shows THEIR concurrent-merge ``CANCELLED`` runs (classified
    ``failed`` by ``_summarize_pr_check_surface``). Only those required-check
    cancellations are the stale artifact that is non-terminal while awaiting the
    refresh.

    Masking is constrained to actual stale REQUIRED checks: inspecting the
    parsed conclusion text alone is NOT enough, because a ``CANCELLED`` failing
    check can belong to a refreshed run or an unrelated non-essential check that
    is NOT one of the required gate workflows. The following failing surfaces are
    therefore NOT stale cancellations and MUST terminate the wait (return
    ``False``):

    * ANY non-``CANCELLED`` failing conclusion (``FAILURE``/``ERROR``/
      ``TIMED_OUT``/``ACTION_REQUIRED``) -- a genuine failure on the refreshed
      surface is real.
    * ANY ``CANCELLED`` failing check whose name is NOT in
      ``EXPECTED_PR_CHECK_SURFACE`` -- a refreshed/unrelated non-required run is
      never the awaited stale required-check artifact, so its cancellation is
      surfaced rather than masked.

    Fail-closed: an empty/absent failing set, or a label that cannot be parsed
    into a ``<name>=<STATE>`` pair, returns ``False`` so an unclassifiable
    ``failed`` surface is surfaced, never masked.
    """
    failing = snapshot.get("failing_checks") or []
    if not failing:
        return False
    for label in failing:
        # _summarize_pr_check_surface formats each failing check as
        # "<name>=<STATE>" with STATE upper-cased; the expected check names never
        # contain "=", so the name is everything before the final "=" and the
        # conclusion is the segment after it.
        name, sep, state = str(label).rpartition("=")
        if not sep:
            # Unparseable label (no "="): cannot confirm a required-check
            # cancellation -- fail closed and surface it.
            return False
        if state.strip().upper() != "CANCELLED":
            return False
        if name.strip() not in EXPECTED_PR_CHECK_SURFACE:
            # A CANCELLED run of a non-required (unrelated / non-essential /
            # refreshed auxiliary) check is NOT the stale required-check artifact
            # the post-resolve await waits on; surface it rather than mask it.
            return False
    return True


def _surface_shows_refreshed_required_checks(snapshot: dict[str, Any]) -> bool:
    """True iff the surface positively proves the re-triggered ``pull_request``
    workflows re-registered after a mid-poll conflict resolve: a non-``failed``
    surface whose expected required-check set is fully present (empty
    ``missing_expected_checks``).

    This is the ONLY condition that clears the persistent
    ``awaiting_refreshed_surface`` post-resolve await. A merely non-``failed``
    surface is NOT enough: while GitHub processes the resolve repush the rollup
    can transiently go pending/unavailable or still be missing the expected
    checks BEFORE the re-triggered runs re-register, and clearing the await on
    such a transient surface would let the very next stale concurrent-merge
    ``CANCELLED`` poll (still classified ``failed``) false-fail the wait. A
    ``failed`` surface is likewise never proof (a stale CANCELLED set is still
    ``failed``). Fail-closed: an absent/``None`` or non-list
    ``missing_expected_checks`` returns ``False`` (keep awaiting), so an
    unclassifiable surface never clears the await early.
    """
    if snapshot.get("status") == "failed":
        return False
    missing = snapshot.get("missing_expected_checks")
    return isinstance(missing, list) and not missing


def _wait_for_expected_pr_check_surface_to_pass(
    repo_root: Path,
    pr_number: str,
    *,
    timeout: int = 900,
    poll_interval: int = 15,
    log: Any = None,
    midpoll_autoresolve: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Poll until the expected PR check surface goes green / fails / times out.

    ``midpoll_autoresolve`` is the conflict-aware mid-poll re-check context
    (``{"base_branch", "branch_name"}``) shared by the Step-14 CI wait and the
    Step-15 bot-remediation CI wait, defaulting to ``None`` (disabled) so the
    non-conflict-aware ``_wait_for_pr_ci`` call sites keep the poll unchanged.
    It mirrors ``_wait_for_required_checks_to_register`` for the
    window AFTER the required checks register: a concurrent lane that merges
    before this surface reaches green flips the PR to CONFLICTING/DIRTY/BEHIND,
    and GitHub then skips/cancels its ``pull_request`` workflows. A cancelled
    required check is classified ``failed`` by ``_summarize_pr_check_surface``,
    so this re-check runs BEFORE the ``status=="failed"`` early-return (and after
    the ``status=="passed"`` return); otherwise a concurrent-merge cancellation
    would be returned as a stale CI failure without the conflict ever being
    probed. On a fresh transition to a conflicting state (edge-guarded by
    ``midpoll_prev_conflicting``) ``_try_auto_resolve_pr_conflict`` is re-fired
    once: on ``resolved=true`` the base-merge repush re-triggers the skipped
    workflows, but they take TIME to re-register, so a PERSISTENT
    ``awaiting_refreshed_surface`` marker (set on the resolve and NOT reset per
    iteration) keeps a STALE ``failed`` surface -- one whose failing checks are
    only the concurrent-merge ``CANCELLED`` runs
    (``_surface_failure_is_stale_cancellation``) -- non-terminal ACROSS
    iterations until the surface REFRESHES (a non-``failed`` surface shows the
    full expected required-check set re-registered --
    ``_surface_shows_refreshed_required_checks``; a transient pending/unavailable
    or still-missing surface is NOT proof of re-registration and does NOT clear
    the marker) OR the deadline below elapses. A GENUINE failure on the refreshed surface (any
    non-``CANCELLED`` failing conclusion) is NOT masked by the marker: the failed
    early-return still fires immediately so a real CI break is never suppressed
    until the deadline. This avoids both false-failing while the re-triggered
    workflows are still registering AND masking a refreshed real failure; on
    ``resolved=false`` the snapshot is returned with a ``midpoll_conflict_aborted``
    marker so ``_wait_for_pr_ci`` converts it into the SAME structured
    ``pr_conflicting`` fail-closed envelope the Step-14-START guard emits. The
    timeout/deadline check is evaluated every iteration (including the
    resolved-conflict iteration) so the wait still terminates at the deadline,
    and the conflict re-check itself is deadline-guarded so the conflict probe
    and ``_try_auto_resolve_pr_conflict`` never run once the deadline has
    already passed.
    """
    deadline = time.monotonic() + timeout
    last_snapshot: dict[str, Any] | None = None
    midpoll_prev_conflicting = False
    # Persistent across iterations (NOT a per-iteration one-shot): set on a
    # successful mid-poll resolve and held until the re-triggered pull_request
    # workflows re-register (surface no longer "failed") or the deadline elapses.
    awaiting_refreshed_surface = False

    while True:
        try:
            checks = _fetch_pr_check_surface_rollup(repo_root, pr_number)
            snapshot = _summarize_pr_check_surface(checks)
            snapshot["checks_output"] = json.dumps(
                {"statusCheckRollup": checks},
                sort_keys=True,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
            OSError,
        ) as exc:
            missing = list(EXPECTED_PR_CHECK_SURFACE)
            snapshot = {
                "status": "pending",
                "summary": (
                    f"statusCheckRollup unavailable ({type(exc).__name__}: {exc}); "
                    "missing expected check(s): " + ", ".join(missing)
                ),
                "present_checks": [],
                "missing_expected_checks": missing,
                "pending_checks": ["statusCheckRollup=unavailable"],
                "failing_checks": [],
                "checks_output": "",
            }

        last_snapshot = snapshot
        if snapshot["status"] == "passed":
            snapshot["ok"] = True
            return snapshot
        # Clear the persistent post-resolve await ONLY on positive proof the
        # re-triggered pull_request workflows re-registered: a non-"failed"
        # surface whose expected required-check set is fully present
        # (_surface_shows_refreshed_required_checks). A merely non-"failed" but
        # pending/unavailable or still-missing surface is NOT such proof -- it can
        # be a transient GitHub state while the resolve repush is processed, and
        # clearing the await on it would let the very next stale concurrent-merge
        # CANCELLED poll (still "failed") false-fail the wait. A genuine CI failure
        # observed AFTER a real refresh still terminates the wait normally: the
        # failed early-return below fires for any non-CANCELLED failing conclusion
        # regardless of the marker.
        if _surface_shows_refreshed_required_checks(snapshot):
            awaiting_refreshed_surface = False
        # Step-14 mid-poll conflict re-check runs BEFORE the status=="failed"
        # early-return (and after the status=="passed" return). The required
        # checks already registered, but a concurrent lane that merges first can
        # flip this PR to CONFLICTING/DIRTY/BEHIND; GitHub then skips/cancels its
        # pull_request workflows, and a cancelled required check is classified
        # *failed* by _summarize_pr_check_surface. If this re-check ran after the
        # failed-return, that concurrent-merge cancellation would be returned as
        # a stale CI failure without the conflict ever being probed. Re-fire the
        # SAME auto-resolve the Step-14-START guard uses, exactly once per
        # detected transition. The re-check is deadline-guarded: once the
        # surface-wait deadline has passed, the conflict probe and auto-resolve
        # are skipped so auto-resolve never starts after the deadline has
        # expired; the failed/timeout early-returns below still terminate the
        # wait.
        if midpoll_autoresolve is not None and time.monotonic() < deadline:
            conflict_state = _check_pr_conflict_state(
                repo_root, pr_number=pr_number, log=log
            )
            currently_conflicting = conflict_state is not None
            if currently_conflicting and not midpoll_prev_conflicting:
                if log is not None:
                    log(
                        f"Step 14 mid-poll: PR #{pr_number} became {conflict_state} "
                        "during expected check-surface wait; re-firing auto-resolve"
                    )
                resolve_kwargs = {
                    "pr_number": pr_number,
                    "base_branch": midpoll_autoresolve["base_branch"],
                    "branch_name": midpoll_autoresolve["branch_name"],
                    "log": log,
                }
                if "wave_id" in midpoll_autoresolve:
                    resolve_kwargs["wave_id"] = midpoll_autoresolve.get("wave_id")
                resolve_result = _try_auto_resolve_pr_conflict(
                    repo_root,
                    **resolve_kwargs,
                )
                if not resolve_result.get("resolved"):
                    # Fail closed: a non-tracker-note conflict or a fetch/
                    # merge/push failure. Do NOT spin to the surface deadline.
                    # The marker is converted by _wait_for_pr_ci into the
                    # Step-14-START pr_conflicting envelope.
                    snapshot["ok"] = False
                    snapshot["midpoll_conflict_aborted"] = True
                    snapshot["auto_resolve_action"] = resolve_result.get(
                        "action", "aborted"
                    )
                    snapshot["detail"] = resolve_result.get("detail", "unknown")
                    return snapshot
                # resolved=true: the base-merge repush re-triggers the
                # previously-skipped pull_request workflows, but they take TIME
                # to re-register. PERSIST the awaiting-refreshed-surface marker
                # ACROSS iterations (not a one-shot re-poll) so a stale "failed"
                # surface -- the concurrent-merge CANCELLED checks, still the
                # latest runs until the re-triggered ones register -- stays
                # non-terminal (ONLY while its failing checks are those CANCELLED
                # runs; a genuine refreshed failure still terminates below) until
                # the surface shows the re-registered required checks (cleared
                # above via _surface_shows_refreshed_required_checks; a transient
                # pending/unavailable surface does NOT clear it) or the deadline
                # below elapses, rather than false-failing on the very next
                # still-"failed" poll.
                awaiting_refreshed_surface = True
            midpoll_prev_conflicting = currently_conflicting
        # The post-resolve await holds a STALE failed surface (failing checks are
        # only the concurrent-merge CANCELLED runs) non-terminal until it
        # refreshes or the deadline elapses. A refreshed GENUINE failure (any
        # non-CANCELLED failing conclusion) is surfaced immediately -- the marker
        # never masks a real CI break until the deadline.
        if snapshot["status"] == "failed" and not (
            awaiting_refreshed_surface
            and _surface_failure_is_stale_cancellation(snapshot)
        ):
            snapshot["ok"] = False
            return snapshot
        if time.monotonic() >= deadline:
            snapshot["ok"] = False
            snapshot["timed_out"] = True
            snapshot["summary"] = (
                f"expected PR check surface did not reach green within {timeout}s: "
                + str(snapshot.get("summary", "unknown"))
            )
            return snapshot
        if log is not None:
            log(f"Waiting for expected PR check surface: {snapshot['summary']}")
        time.sleep(poll_interval)

    # Unreachable, but keeps static analyzers honest if the loop changes.
    assert last_snapshot is not None


def _wait_ci_surface_failure_response(
    surface: dict[str, Any],
    *,
    result: dict[str, Any],
    pr_number: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "step": "wait_ci",
        "failure_class": "test_failure" if surface.get("failing_checks") else "unknown_error",
        "errors": ["Expected PR check surface did not reach green. " + surface["summary"]],
        "ci_failures": [],
        "ci_checks_output": surface.get("checks_output", ""),
        "ci_check_surface": surface,
        "steps_completed": result["steps_completed"],
        "pr_number": pr_number,
    }


def _pr_conflicting_fail_closed_response(
    *,
    pr_number: str,
    base_branch: str,
    target_branch: str,
    steps_completed: list[str],
    action: str,
    detail: str,
) -> dict[str, Any]:
    """Build the fail-closed envelope for a CONFLICTING/DIRTY/BEHIND PR whose
    auto-resolve could not clear the conflict.

    Single source of truth shared by the Step-14-START guard and every Step-14
    mid-poll re-check (the required-checks registration wait AND the expected-
    check-surface wait) so all of them emit the identical ``pr_conflicting``
    ``failure_class`` and manual-recovery recipe — they must not drift.
    """
    return {
        "status": "error",
        "step": "wait_ci",
        "errors": [
            f"PR #{pr_number} CONFLICTING/DIRTY/BEHIND and auto-resolve "
            f"action={action}: {detail}. Manual recovery required: "
            f"`cd <worktree> && git fetch origin {base_branch} && "
            f"git merge origin/{base_branch} --no-edit` (resolve "
            f"conflicts manually if any) + "
            f"`RCX_SKIP_RECEIPT_CHECK=1 git commit --no-edit` + "
            f"`git push origin {target_branch}` + relaunch commit_executor."
        ],
        "steps_completed": steps_completed,
        "pr_number": pr_number,
        "failure_class": "pr_conflicting",
        "auto_resolve_action": action,
    }


def _midpoll_conflict_recheck_before_ci_failure(
    repo_root: Path,
    pr_number: str,
    *,
    midpoll_autoresolve: dict[str, Any] | None,
    target_branch: str,
    steps_completed: list[str],
    log: Any = None,
) -> dict[str, Any] | None:
    """Conflict-aware mid-poll re-check at the required-checks-not-passed
    boundary (the Step-14 + Step-15-bot-remediation CI waits) -- the wait stage
    BETWEEN the registration wait and the expected check-surface wait (both
    already mid-poll-aware).

    A concurrent lane that merges after the required checks register flips this
    PR to CONFLICTING/DIRTY/BEHIND; GitHub then cancels/skips the in-flight
    required workflows, so ``_wait_for_required_checks_to_pass`` reports them as
    not-passed even though the cause is a conflict, not a real CI break. Without
    this re-check the caller would mis-emit a ``ci_failure`` (which recovery
    treats as a genuine test break) instead of the resolvable ``pr_conflicting``
    class. Mirrors the register-wait + surface-wait re-checks: attempt the SAME
    auto-resolve once, and fail closed with the SAME envelope when unresolvable.

    Returns:
      * ``None`` -- not a mid-poll conflict (genuine CI state, or a
        non-conflict-aware caller where ``midpoll_autoresolve is None``): the
        caller emits its normal CI-failure response.
      * ``{"midpoll_conflict_resolved": True}`` -- a conflict was detected and
        the base-merge repush cleared it; the caller should re-verify the
        refreshed check surface (fall through to the surface-pass wait) instead
        of failing as CI.
      * a ``_pr_conflicting_fail_closed_response(...)`` envelope -- a conflict
        was detected but auto-resolve could not clear it; the caller returns it.
    """
    if midpoll_autoresolve is None:
        return None
    conflict_state = _check_pr_conflict_state(repo_root, pr_number=pr_number, log=log)
    if conflict_state is None:
        return None
    if log is not None:
        log(
            f"Step 14 mid-poll: PR #{pr_number} is {conflict_state} when required "
            "checks read as not-passed (a concurrent lane likely merged and "
            "cancelled the required workflows); re-firing auto-resolve before "
            "treating this as a CI failure"
        )
    resolve_kwargs = {
        "pr_number": pr_number,
        "base_branch": midpoll_autoresolve["base_branch"],
        "branch_name": midpoll_autoresolve["branch_name"],
        "log": log,
    }
    if "wave_id" in midpoll_autoresolve:
        resolve_kwargs["wave_id"] = midpoll_autoresolve.get("wave_id")
    resolve_result = _try_auto_resolve_pr_conflict(
        repo_root,
        **resolve_kwargs,
    )
    if resolve_result.get("resolved"):
        return {"midpoll_conflict_resolved": True}
    return _pr_conflicting_fail_closed_response(
        pr_number=pr_number,
        base_branch=midpoll_autoresolve.get("base_branch", ""),
        target_branch=target_branch,
        steps_completed=steps_completed,
        action=resolve_result.get("action", "aborted"),
        detail=resolve_result.get("detail", "unknown"),
    )


def _wait_for_pr_ci(
    repo_root: Path,
    *,
    pr_number: str,
    result: dict[str, Any],
    continuation_path: Path,
    target_branch: str,
    log: Any = None,
    step_label: str = "Step 14",
    midpoll_autoresolve: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Wait for required CI checks and checkpoint `wait_ci` once.

    ``midpoll_autoresolve`` is the conflict-aware mid-poll re-check context
    threaded into BOTH ``_wait_for_required_checks_to_register`` (the
    pre-registration window) AND ``_wait_for_expected_pr_check_surface_to_pass``
    (the post-registration check-surface window), so a concurrent lane that
    merges at ANY point before the surface goes green is caught instead of
    spinning to the verify timeout. It defaults to ``None`` (disabled); the
    Step-14 CI wait and the Step-15 bot-remediation CI wait populate it (with
    ``base_branch`` + the head ``target_branch`` as ``branch_name``). When either
    wait reports a mid-poll conflict it could not resolve, this converts that
    signal into the SAME structured ``pr_conflicting`` fail-closed envelope the
    Step-14-START guard emits.
    """
    if log is not None:
        log(f"{step_label}: waiting for CI on PR #{pr_number}...")
    try:
        register_signal = _wait_for_required_checks_to_register(
            repo_root,
            pr_number=pr_number,
            log=log,
            midpoll_autoresolve=midpoll_autoresolve,
        )
        if register_signal is not None:
            # Mid-poll CONFLICTING/DIRTY transition that auto-resolve could
            # not clear (conflict-aware callers only -- Step-14 + the Step-15
            # bot-remediation; the two non-conflict-aware call sites pass no
            # context, so the registration wait never returns this signal).
            # Fail closed with the SAME structured envelope the Step-14-START
            # guard emits -- do NOT proceed into the watch ceiling.
            return _pr_conflicting_fail_closed_response(
                pr_number=pr_number,
                base_branch=(midpoll_autoresolve or {}).get("base_branch", ""),
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                action=register_signal.get("auto_resolve_action", "aborted"),
                detail=register_signal.get("detail", "unknown"),
            )
        _run(
            ["gh", "pr", "checks", pr_number, "--watch", "--required"],
            cwd=repo_root, timeout=COMMIT_CI_WATCH_TIMEOUT_S,
        )
        if not _wait_for_required_checks_to_pass(
            repo_root,
            pr_number,
            timeout=COMMIT_CI_VERIFY_TIMEOUT_S,
            log=log,
        ):
            midpoll = _midpoll_conflict_recheck_before_ci_failure(
                repo_root,
                pr_number,
                midpoll_autoresolve=midpoll_autoresolve,
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                log=log,
            )
            if midpoll is None:
                ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
                return {
                    "status": "error",
                    "step": "wait_ci",
                    "failure_class": _wait_ci_failure_class(ci_failure),
                    "errors": [
                        "Required CI checks did not reach green after gh watch returned. "
                        + str(ci_failure.get("summary", ""))
                    ],
                    "ci_failures": ci_failure.get("failures", []),
                    "ci_checks_output": ci_failure.get("checks_output", ""),
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number,
                }
            if not midpoll.get("midpoll_conflict_resolved"):
                return midpoll
            # Mid-poll conflict resolved: the base-merge repush re-triggered the
            # cancelled required workflows; fall through to the surface-pass wait,
            # which re-verifies the refreshed check surface against the new head.
        surface = _wait_for_expected_pr_check_surface_to_pass(
            repo_root,
            pr_number,
            timeout=COMMIT_CI_VERIFY_TIMEOUT_S,
            log=log,
            midpoll_autoresolve=midpoll_autoresolve,
        )
        if surface.get("midpoll_conflict_aborted"):
            # Concurrent lane merged AFTER the required checks registered but
            # BEFORE the surface went green; the surface-wait re-fired the
            # Step-14 auto-resolve and it could not clear the conflict. Fail
            # closed with the SAME pr_conflicting envelope as the other guards.
            return _pr_conflicting_fail_closed_response(
                pr_number=pr_number,
                base_branch=(midpoll_autoresolve or {}).get("base_branch", ""),
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                action=surface.get("auto_resolve_action", "aborted"),
                detail=surface.get("detail", "unknown"),
            )
        if not surface.get("ok"):
            return _wait_ci_surface_failure_response(
                surface,
                result=result,
                pr_number=pr_number,
            )
        if "wait_ci" not in result["steps_completed"]:
            result["steps_completed"].append("wait_ci")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
        if log is not None:
            log(f"{step_label}: CI passed")
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, TimeoutError) as exc:
        if log is not None:
            log(
                f"{step_label}: gh pr checks exited ({exc.__class__.__name__}), "
                "polling CI as fallback"
            )
        if not _poll_ci_checks_fallback(
            repo_root,
            pr_number,
            timeout=COMMIT_CI_POLL_TIMEOUT_S,
            log=log,
        ):
            ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
            return {
                "status": "error",
                "step": "wait_ci",
                "failure_class": _wait_ci_failure_class(ci_failure),
                "errors": [
                    f"CI checks failed (confirmed by polling): {exc}. "
                    + str(ci_failure.get("summary", ""))
                ],
                "ci_failures": ci_failure.get("failures", []),
                "ci_checks_output": ci_failure.get("checks_output", ""),
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number,
            }
        if not _wait_for_required_checks_to_pass(
            repo_root,
            pr_number,
            timeout=COMMIT_CI_VERIFY_TIMEOUT_S,
            log=log,
        ):
            midpoll = _midpoll_conflict_recheck_before_ci_failure(
                repo_root,
                pr_number,
                midpoll_autoresolve=midpoll_autoresolve,
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                log=log,
            )
            if midpoll is None:
                ci_failure = _summarize_required_ci_failures(repo_root, pr_number)
                return {
                    "status": "error",
                    "step": "wait_ci",
                    "failure_class": _wait_ci_failure_class(ci_failure),
                    "errors": [
                        f"Required CI checks did not reach green after fallback polling: {exc}. "
                        + str(ci_failure.get("summary", ""))
                    ],
                    "ci_failures": ci_failure.get("failures", []),
                    "ci_checks_output": ci_failure.get("checks_output", ""),
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number,
                }
            if not midpoll.get("midpoll_conflict_resolved"):
                return midpoll
            # Mid-poll conflict resolved during the fallback path: fall through to
            # the surface-pass wait to re-verify the refreshed check surface.
        surface = _wait_for_expected_pr_check_surface_to_pass(
            repo_root,
            pr_number,
            timeout=COMMIT_CI_VERIFY_TIMEOUT_S,
            log=log,
            midpoll_autoresolve=midpoll_autoresolve,
        )
        if surface.get("midpoll_conflict_aborted"):
            # Concurrent lane merged AFTER the required checks registered but
            # BEFORE the surface went green; the surface-wait re-fired the
            # Step-14 auto-resolve and it could not clear the conflict. Fail
            # closed with the SAME pr_conflicting envelope as the other guards.
            return _pr_conflicting_fail_closed_response(
                pr_number=pr_number,
                base_branch=(midpoll_autoresolve or {}).get("base_branch", ""),
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                action=surface.get("auto_resolve_action", "aborted"),
                detail=surface.get("detail", "unknown"),
            )
        if not surface.get("ok"):
            return _wait_ci_surface_failure_response(
                surface,
                result=result,
                pr_number=pr_number,
            )
        if "wait_ci" not in result["steps_completed"]:
            result["steps_completed"].append("wait_ci")
            _checkpoint_post_commit_progress(
                result,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )
        if log is not None:
            log(f"{step_label}: CI passed (confirmed by polling fallback)")
        return None


def _prepare_result_for_late_conflict_retry(
    repo_root: Path,
    *,
    result: dict[str, Any],
    continuation_path: Path,
    target_branch: str,
) -> None:
    """Refresh continuation state after a late auto-resolve push changes HEAD."""
    result["commit_sha"] = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
    result["steps_completed"] = [
        step for step in result["steps_completed"] if step != "wait_ci"
    ]
    result.pop("bot_review_request_sha", None)
    _checkpoint_post_commit_progress(
        result,
        continuation_path=continuation_path,
        target_branch=target_branch,
    )


def _poll_ci_checks_fallback(
    repo_root: Path,
    pr_number: str,
    *,
    timeout: int = 900,
    poll_interval: int = 15,
    log: Any = None,
) -> bool:
    """Fallback CI poll when ``gh pr checks --watch`` exits prematurely.

    ``gh pr checks --watch --required`` exits 1 when checks are still
    pending (not started or in progress), which the caller interprets as
    CI failure.  This function polls ``gh pr view --json statusCheckRollup``
    until every check has a conclusion, then returns True iff none FAILED.
    """
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        try:
            out = subprocess.run(
                ["gh", "pr", "view", pr_number, "--json", "statusCheckRollup"],
                cwd=repo_root, capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            _time.sleep(poll_interval)
            continue
        if out.returncode != 0:
            _time.sleep(poll_interval)
            continue
        try:
            checks = json.loads(out.stdout).get("statusCheckRollup", [])
        except (json.JSONDecodeError, ValueError):
            _time.sleep(poll_interval)
            continue
        if not checks:
            _time.sleep(poll_interval)
            continue
        # Treat non-passing conclusions as failed.  GitHub considers SUCCESS,
        # SKIPPED and NEUTRAL as passing for required-check purposes.
        _PASSING = {"SUCCESS", "SKIPPED", "NEUTRAL"}
        _non_success = [
            c for c in checks
            if c.get("conclusion") and c["conclusion"] not in _PASSING
        ]
        if _non_success:
            if log:
                failed_names = [f"{c.get('name', '?')}={c['conclusion']}" for c in _non_success]
                log(f"CI check(s) not successful: {', '.join(failed_names)}")
            return False
        all_done = all(c.get("conclusion") for c in checks)
        if all_done:
            return True
        _time.sleep(poll_interval)
    if log:
        log(f"CI poll timed out after {timeout}s")
    return False


def _required_check_label(check: dict[str, Any]) -> str:
    name = str(check.get("name") or check.get("workflow") or "unknown")
    state = str(check.get("state") or "").upper()
    bucket = str(check.get("bucket") or "").lower()
    status = state or bucket or "unknown"
    return f"{name}={status}"


def _required_checks_green_snapshot(repo_root: Path, pr_number: str) -> tuple[bool, str, str]:
    result = _run(
        [
            "gh", "pr", "checks", pr_number,
            "--required",
            "--json", "name,state,bucket",
        ],
        cwd=repo_root,
        timeout=30,
        check=False,
    )
    if result.returncode not in (0, 8):
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    try:
        checks = json.loads(result.stdout or "[]")
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"required-check JSON decode failed: {exc}") from exc
    if not isinstance(checks, list):
        raise ValueError("required-check JSON was not a list")
    if not checks:
        return False, "pending", "no required checks reported"

    pending: list[str] = []
    failing: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            pending.append(str(check))
            continue
        bucket = str(check.get("bucket") or "").lower()
        state = str(check.get("state") or "").upper()
        label = _required_check_label(check)
        if bucket in CI_REQUIRED_FAILING_BUCKETS or state in CI_REQUIRED_FAILING_STATES:
            failing.append(label)
        elif bucket in CI_REQUIRED_PASSING_BUCKETS or state in CI_REQUIRED_PASSING_STATES:
            continue
        elif bucket in CI_REQUIRED_PENDING_BUCKETS or state in CI_REQUIRED_PENDING_STATES or not state:
            pending.append(label)
        else:
            pending.append(label)

    if failing:
        return False, "failed", "failing required check(s): " + ", ".join(failing)
    if pending:
        return False, "pending", "pending required check(s): " + ", ".join(pending)
    return True, "passed", "all required checks green"


def _wait_for_required_checks_to_pass(
    repo_root: Path,
    pr_number: str,
    *,
    timeout: int = 900,
    poll_interval: int = 15,
    log: Any = None,
) -> bool:
    """Verify current required PR checks are green after gh's watch command exits."""
    deadline = time.monotonic() + timeout
    last_detail = ""
    while True:
        green, status, detail = _required_checks_green_snapshot(repo_root, pr_number)
        last_detail = detail
        if green:
            return True
        if status == "failed":
            if log:
                log(f"Required checks failed for PR #{pr_number}: {detail}")
            return False
        if time.monotonic() >= deadline:
            if log:
                log(
                    f"Required checks did not pass for PR #{pr_number} "
                    f"within {timeout}s: {last_detail}"
                )
            return False
        if log:
            log(f"Waiting for required checks to pass on PR #{pr_number}: {detail}")
        time.sleep(poll_interval)


def _write_auto_deferred_bot_findings_report(
    repo_root: Path,
    findings: list[dict[str, Any]],
    wave_id: str,
    pr_number: str,
    log: Any,
) -> Path:
    """Write the local report for non-blocking auto-deferred bot findings."""
    from datetime import datetime, timezone

    deferred_dir = repo_root / "reports" / "deferred" / "non_blocking"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    report_name = f"pr{pr_number}_bot_auto_deferred_{wave_id}.md"
    report_path = deferred_dir / report_name
    lines = [
        f"# PR #{pr_number} Bot Findings (Auto-Deferred)\n\n",
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
        f"Wave: {wave_id}\n",
        "Classification: NON-BLOCKING (auto-deferred — remediation adapter produced no changes)\n\n",
    ]
    for i, finding in enumerate(findings, 1):
        body = finding.get("body", "")
        path = finding.get("path", "unknown")
        lines.append(f"## Finding {i}: `{path}`\n\n")
        lines.append(f"{body[:500]}\n\n")
    report_path.write_text("".join(lines), encoding="utf-8")
    log(f"Step 15: deferred report written to {report_name}")
    return report_path


def _resolve_auto_deferred_bot_threads(
    *,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    log: Any,
) -> None:
    """Resolve eligible bot-authored threads after the report commit is pushed."""
    try:
        query = (
            f'{{"query":"query{{repository(owner:\\"{repo_owner}\\",name:\\"{repo_name}\\")'
            f'{{pullRequest(number:{pr_number}){{reviewThreads(first:50){{nodes{{id isResolved comments(first:1){{nodes{{author{{login}}}}}}}}}}}}}}}}"}}'
        )
        query_result = subprocess.run(
            ["gh", "api", "graphql", "--input", "-"],
            input=query, capture_output=True, text=True, timeout=30,
        )
        if query_result.returncode == 0:
            data = json.loads(query_result.stdout)
            threads = (
                data.get("data", {})
                .get("repository", {})
                .get("pullRequest", {})
                .get("reviewThreads", {})
                .get("nodes", [])
            )
            resolved_count = 0
            for thread in threads:
                if not thread.get("isResolved"):
                    # Only resolve bot-authored threads — human threads must
                    # remain unresolved for manual review.
                    first_comments = thread.get("comments", {}).get("nodes", [])
                    if first_comments:
                        thread_author = first_comments[0].get("author", {}).get("login", "")
                        if not _is_bot_review_author(thread_author):
                            continue
                    tid = thread["id"]
                    mutation = (
                        f'{{"query":"mutation{{resolveReviewThread(input:{{threadId:\\"{tid}\\"}})'
                        f'{{thread{{isResolved}}}}}}"}}'
                    )
                    subprocess.run(
                        ["gh", "api", "graphql", "--input", "-"],
                        input=mutation, capture_output=True, text=True, timeout=30,
                    )
                    resolved_count += 1
            if resolved_count:
                log(f"Step 15: resolved {resolved_count} PR comment thread(s)")
    except Exception as exc:
        log(f"Step 15: failed to resolve comment threads (non-fatal): {exc}")


def _auto_defer_bot_findings(
    repo_root: Path,
    findings: list[dict[str, Any]],
    wave_id: str,
    pr_number: str,
    repo_owner: str,
    repo_name: str,
    log: Any,
    *,
    round_num: int,
    target_branch: str,
    continuation_path: Path,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Record auto-deferred findings in a guarded child commit before resolution.

    The report writer is intentionally local-only.  The eligible-thread resolver
    remains non-fatal, but is unreachable until the child commit has passed the
    explicit guard, the ordinary push has succeeded, and ``git_push`` has been
    checkpointed for that exact continuation head.
    """
    try:
        report_path = _write_auto_deferred_bot_findings_report(
            repo_root,
            findings,
            wave_id,
            pr_number,
            log,
        )
        report_rel = str(report_path.relative_to(repo_root))
        _run(
            ["git", "add", "-f", "--", report_rel],
            cwd=repo_root,
            timeout=30,
        )
        bot_receipt = _mint_bot_remediation_receipt(
            repo_root=repo_root,
            findings_addressed=[
                {"path": finding.get("path", ""), "body": finding.get("body", "")[:200]}
                for finding in findings
            ],
            scoped_files=[report_rel],
            round_num=round_num,
            wave_id=wave_id,
        )
        log(f"Step 15: bot-remediation receipt minted for deferred report: {bot_receipt.name}")

        msg = (
            f"docs: record auto-deferred bot findings (round {round_num})\n\n"
            "Co-Authored-By: Codex <noreply@openai.com>"
        )
        _run(
            ["git", "commit", "-m", msg],
            cwd=repo_root,
            timeout=60,
            env=_commit_subprocess_env(),
        )
        current_head = _run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            timeout=10,
        ).stdout.strip()
        if not current_head:
            return {
                "status": "bot_findings_pending",
                "bot_findings": findings,
                "pr_number": pr_number,
                "steps_completed": result.get("steps_completed", []),
                "remediation_rounds_attempted": round_num,
                "errors": ["auto-defer child commit produced an empty HEAD"],
            }

        reset_steps = _continuation_steps_for_new_commit(result.get("steps_completed"))
        if reset_steps is None:
            return {
                "status": "bot_findings_pending",
                "bot_findings": findings,
                "pr_number": pr_number,
                "steps_completed": result.get("steps_completed", []),
                "remediation_rounds_attempted": round_num,
                "errors": [
                    "auto-defer child commit could not reset continuation through git_commit"
                ],
            }

        auto_defer_checkpoint = dict(result)
        auto_defer_checkpoint["commit_sha"] = current_head
        auto_defer_checkpoint["steps_completed"] = reset_steps
        for stale_field in (
            "bot_review_request_sha",
            "pre_push_isolation",
            "pre_push_restored_paths",
        ):
            auto_defer_checkpoint.pop(stale_field, None)
        _checkpoint_post_commit_progress(
            auto_defer_checkpoint,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )

        result["commit_sha"] = current_head
        result["steps_completed"] = list(reset_steps)
        for stale_field in (
            "bot_review_request_sha",
            "pre_push_isolation",
            "pre_push_restored_paths",
        ):
            result.pop(stale_field, None)

        pre_push_guard = _run_bot_remediation_pre_push_guard(
            repo_root,
            log=log,
        )
        if not pre_push_guard["passed"]:
            gate_errors = list(pre_push_guard.get("errors") or [])
            log(
                "Step 15: bot-remediation pre-push gate failed before "
                f"auto-defer report push: {gate_errors}"
            )
            return {
                "status": "bot_findings_pending",
                "bot_findings": findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
                "errors": gate_errors,
                "bot_remediation_pre_push": pre_push_guard,
            }

        auto_defer_checkpoint["steps_completed"].append("run_pre_push_script")
        _checkpoint_post_commit_progress(
            auto_defer_checkpoint,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
        result["steps_completed"] = list(auto_defer_checkpoint["steps_completed"])

        _run(
            ["git", "push", "--no-verify", "origin", target_branch],
            cwd=repo_root,
            timeout=300,
        )
        auto_defer_checkpoint["steps_completed"].append("git_push")
        _checkpoint_post_commit_progress(
            auto_defer_checkpoint,
            continuation_path=continuation_path,
            target_branch=target_branch,
        )
        result["steps_completed"] = list(auto_defer_checkpoint["steps_completed"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            failure_detail = f"{exc.cmd!r} timed out"
        else:
            failure_detail = _tail_failure_excerpt(
                "\n".join(
                    str(part)
                    for part in (exc.stderr, exc.stdout)
                    if part
                ),
                limit=1200,
            ) or str(exc)
        log(
            "Step 15: auto-defer report child-commit strand failed with "
            f"{type(exc).__name__}: {failure_detail}"
        )
        return {
            "status": "bot_findings_pending",
            "bot_findings": findings,
            "pr_number": pr_number,
            "steps_completed": result.get("steps_completed", []),
            "remediation_rounds_attempted": round_num,
            "errors": [failure_detail],
            "auto_defer_failure_class": type(exc).__name__,
        }

    _resolve_auto_deferred_bot_threads(
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number,
        log=log,
    )
    log(
        f"Step 15: deferred report committed and pushed on {current_head[:8]} "
        "before eligible bot-thread resolution"
    )
    return None


def _classify_and_auto_defer_unremediated_bot_findings(
    current_findings: list[dict[str, Any]],
    *,
    round_num: int,
    repo_root: Path,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    wave_id: str,
    target_branch: str,
    continuation_path: Path,
    result: dict[str, Any],
    log: Any,
) -> dict[str, Any] | None:
    """Classify unremediated bot findings and auto-defer the deferrable set.

    Shared by both unremediated-findings exits of
    ``_attempt_bot_finding_remediation``: the no-change path (the adapter ran
    but produced no changes) AND the adapter-error/timeout path (the adapter
    raised ``BridgeAdapterError``). In both the bot findings were NOT fixed, so
    the disposition is identical:

    * P0/P1 findings (the bot's P-level badge, read from ``body``/``severity``)
      -> route to recovery (``bot_findings_pending``); never silently deferred.
    * Critical-path findings (hooks, executors, checks, preflight) -> route to
      recovery regardless of P-level; the badge measures code quality, not
      pipeline impact.
    * Otherwise (all P2+/non-critical) -> auto-defer the report through a normal
      guarded child commit, then return ``None`` so the caller proceeds to merge.

    Returns a ``bot_findings_pending`` response dict when any P0/P1 OR
    critical-path finding remains; ``None`` (auto-deferred) otherwise. This is
    the EXISTING no-change-path classifier verbatim -- the bot uses P-levels,
    NOT the bridge severity rule.
    """
    # Check if any finding is P0 or P1 (blocking) — these with no
    # adapter fix must still fail-close.  Only P2+ get auto-deferred.
    blocking_findings = [
        f for f in current_findings
        if any(
            sev in f.get("body", "") or sev in f.get("severity", "")
            for sev in ("P0", "P1")
        )
    ]
    if blocking_findings:
        log(
            f"Step 15: adapter produced no changes in round {round_num} — "
            f"{len(blocking_findings)} P0/P1 finding(s) remain, routing to recovery agent"
        )
        return {
            "status": "bot_findings_pending",
            "bot_findings": current_findings,
            "p1_unresolved": True,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
            "remediation_rounds_attempted": round_num,
        }
    # Critical-path guard: findings on hooks, executors, checks, or
    # preflight are ALWAYS blocking regardless of P-level — the bot's
    # severity badge measures code quality, not pipeline impact.
    _CRITICAL_PATH_PREFIXES = (
        ".claude/hooks/", ".claude/skills/preflight/", "mu/tools/executors/",
        "mu/tools/checks/", "tools/checks/", "mu/tools/hooks/",
    )
    critical_findings = [
        f for f in current_findings
        if any(f.get("path", "").startswith(pfx) for pfx in _CRITICAL_PATH_PREFIXES)
    ]
    if critical_findings:
        log(
            f"Step 15: adapter produced no changes in round {round_num} — "
            f"{len(critical_findings)} finding(s) on critical-path files, routing to recovery"
        )
        return {
            "status": "bot_findings_pending",
            "bot_findings": current_findings,
            "p1_unresolved": True,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
            "remediation_rounds_attempted": round_num,
        }
    log(f"Step 15: adapter produced no changes in round {round_num} — auto-deferring {len(current_findings)} non-blocking finding(s)")
    return _auto_defer_bot_findings(
        repo_root, current_findings, wave_id, pr_number,
        repo_owner, repo_name, log,
        round_num=round_num,
        target_branch=target_branch,
        continuation_path=continuation_path,
        result=result,
    )


def _attempt_bot_finding_remediation(
    bot_findings: list[dict[str, Any]],
    *,
    repo_root: Path,
    repo_owner: str,
    repo_name: str,
    pr_number: str,
    target_branch: str,
    base_branch: str | None = None,
    head_sha: str,
    wave_id: str,
    continuation_path: Path,
    result: dict[str, Any],
    log: Any,
) -> dict[str, Any] | None:
    """Attempt to fix bot findings via bridge adapter.

    ``base_branch`` is the wave's base branch (the same ``base_branch``
    ``_run_post_commit_pipeline`` threads to the Step-14 caller, i.e.
    ``handoff['base_branch']`` = ``dev``). It is the branch
    ``_try_auto_resolve_pr_conflict`` fetches and merges FROM, so it must carry
    the REAL base, never ``target_branch`` (which is the PR head this function
    pushes to). It defaults to ``None`` so the existing direct-call sites that do
    not thread it keep the prior (conflict-recheck disabled) behavior; the live
    pipeline caller threads it, enabling the Step-15-remediation CI-wait to be
    conflict-aware exactly like Step-14.

    Returns None on success (caller proceeds to merge).
    Returns a response dict on failure (bot_findings_pending or error).
    """
    if _bridge_adapters is None:
        log("Step 15: bridge_adapters unavailable, skipping remediation")
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    config_path = bridge_config_path(repo_root, _active_bus_dir())
    # Auto-heal: fresh worktrees created by `git worktree add` lack bus runtime
    # directories because .gitignore excludes them. Seed the active bus from a
    # trusted bridge_config.json source, including the canonical default bus for
    # namespaced runs. Preserves load_bridge_config's fail-closed contract: if
    # no trusted source exists, load_bridge_config raises BridgeAdapterError
    # unchanged.
    if not config_path.exists():
        try:
            config_path = ensure_bridge_config_path(repo_root, _active_bus_dir())
            if config_path.exists():
                relpath = agent_bus_relpath(_active_bus_dir(), "bridge_config.json")
                log(f"Step 15: auto-copied bridge_config.json into {relpath}")
        except Exception as heal_exc:
            log(f"Step 15: bridge_config.json auto-heal failed: {heal_exc}")
    try:
        bot_remediation_adapter = _strict_target_bot_remediation_adapter(repo_root)
        config = _bridge_adapters.load_bridge_config(config_path)
        adapter = _bridge_adapters.get_adapter(config, bot_remediation_adapter)
    except Exception as exc:
        log(f"Step 15: cannot load bridge adapter: {exc}")
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    current_findings = bot_findings
    current_head = head_sha

    for round_num in range(1, BOT_REMEDIATION_MAX_ROUNDS + 1):
        log(f"Step 15: bot-finding remediation round {round_num}/{BOT_REMEDIATION_MAX_ROUNDS}")

        prompt = _build_bot_remediation_prompt(
            current_findings,
            wave_id=wave_id,
            pr_number=pr_number,
            remediation_round=round_num,
        )

        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        job_id = f"bot-fix-{uuid.uuid4().hex[:8]}"
        prompt_path = scratch_dir / f"bot_remediation_prompt_r{round_num}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        raw_output_path = scratch_dir / f"bot_remediation_output_{job_id}.txt"

        final_adapter = _bridge_adapters.AdapterSpec(
            name=adapter.name,
            cmd=adapter.cmd,
            timeout_s=BOT_REMEDIATION_TIMEOUT_S,
            prompt_via_stdin=adapter.prompt_via_stdin,
            env=adapter.env,
            mode=adapter.mode,
        )

        try:
            _bridge_adapters.run_adapter(
                final_adapter,
                prompt_text=prompt,
                prompt_path=prompt_path,
                repo_root=repo_root,
                job_id=job_id,
                turn_id=f"bot-fix-r{round_num}",
                agent_role="bot_remediation",
                raw_output_path=raw_output_path,
                stale_timeout_s=BOT_REMEDIATION_STALE_TIMEOUT_S,
                bus_dir=_active_bus_dir(),
            )
        except _bridge_adapters.BridgeAdapterError as exc:
            log(f"Step 15: adapter error in round {round_num}: {exc}")
            # A remediation adapter TIMEOUT/error leaves the findings unfixed —
            # the SAME state as the adapter running but producing no changes
            # (the no-change path below). Route through the shared classifier so
            # an all-deferrable (P2+/non-critical) finding set AUTO-DEFERS and
            # the commit proceeds, while P0/P1 OR critical-path findings still
            # strand to recovery exactly as this path and the no-change path
            # already do for those classes. Previously this returned
            # bot_findings_pending UNCONDITIONALLY, stranding deferrable waves
            # (e.g. the slow bot_remediation=claude adapter hitting the 600s
            # timeout on an all-P2 finding set).
            #
            # The adapter may have raised AFTER staging or modifying files (a
            # timeout mid-edit). The no-change path below only reaches the
            # shared helper once `git status` proves the worktree clean; the
            # helper's deferrable branch then stages only its report into a
            # guarded child commit. So FIRST discard the adapter's partial work,
            # otherwise those unreviewed partial edits would be silently folded
            # into that commit. This restores the helper's clean-worktree
            # precondition.
            _discard_failed_adapter_partial_changes(repo_root, log=log)
            return _classify_and_auto_defer_unremediated_bot_findings(
                current_findings,
                round_num=round_num,
                repo_root=repo_root,
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
                wave_id=wave_id,
                target_branch=target_branch,
                continuation_path=continuation_path,
                result=result,
                log=log,
            )

        # Check if adapter produced changes
        status_out = _run(
            ["git", "status", "--porcelain"],
            cwd=repo_root, timeout=30,
        ).stdout
        if not status_out.strip():
            # The adapter ran but produced no changes — the findings are
            # unremediated. Classify + auto-defer via the shared helper (the
            # SAME helper the adapter-error/timeout path uses): P0/P1 OR
            # critical-path findings route to recovery; all-deferrable
            # (P2+/non-critical) findings auto-defer and the commit proceeds.
            return _classify_and_auto_defer_unremediated_bot_findings(
                current_findings,
                round_num=round_num,
                repo_root=repo_root,
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
                wave_id=wave_id,
                target_branch=target_branch,
                continuation_path=continuation_path,
                result=result,
                log=log,
            )

        # Stage finding-scoped files + same-directory helpers, fail closed on rest.
        # The remediation prompt allows creating helper files in the same
        # directories as finding paths, so the staging guard must match.
        finding_paths = {f.get("path") for f in current_findings if f.get("path")}
        allowed_dirs = {str(Path(p).parent) for p in finding_paths if p}
        allowed_paths = set(finding_paths)  # exact finding paths always allowed

        def _is_same_dir_helper(fp: str) -> bool:
            """Return True if fp is a new file in a finding's directory."""
            return any(str(Path(fp).parent) == d for d in allowed_dirs)
        changed_lines = [ln for ln in status_out.splitlines() if ln.strip()]
        scoped_entries: list[tuple[str, str]] = []
        out_of_scope_entries: list[tuple[str, str]] = []
        for ln in changed_lines:
            parsed_line = _parse_porcelain_status_line(ln)
            if parsed_line is None:
                log(f"Step 15: cannot parse git status line: {ln!r}")
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                }
            status_code, file_path = parsed_line
            if file_path in allowed_paths or _is_same_dir_helper(file_path):
                scoped_entries.append((status_code, file_path))
            elif not _is_transient_status_path(file_path):
                out_of_scope_entries.append((status_code, file_path))
        scoped_files = [file_path for _, file_path in scoped_entries]
        out_of_scope = [file_path for _, file_path in out_of_scope_entries]

        if out_of_scope:
            log(f"Step 15: out-of-scope changes detected: {out_of_scope}")
            # Discard only the scoped + out-of-scope files, not unrelated work
            for status_code, file_path in scoped_entries + out_of_scope_entries:
                _discard_worktree_path(
                    repo_root,
                    status_code=status_code,
                    file_path=file_path,
                )
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        if not scoped_files:
            log(f"Step 15: no in-scope file changes in round {round_num}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        try:
            # Split .claude/ paths into individual staging to avoid the git
            # multi-path pathspec resolver false-positive (learning.md 2026-04-11).
            _claude_files = [f for f in scoped_files if f.startswith(".claude/")]
            _other_files = [f for f in scoped_files if not f.startswith(".claude/")]
            if _other_files:
                _run(["git", "add", "--"] + _other_files, cwd=repo_root, timeout=30)
            for _cf in _claude_files:
                _run(["git", "add", "--", _cf], cwd=repo_root, timeout=30)
            tracker_followup = ensure_bot_remediation_tracker_followup(
                repo_root,
                wave_id=wave_id,
                scoped_files=scoped_files,
            )
            if tracker_followup.get("errors"):
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "errors": list(tracker_followup.get("errors") or []),
                }
            if tracker_followup.get("updated"):
                _run(["git", "add", "--", "TASKS.md"], cwd=repo_root, timeout=30)
                if "TASKS.md" not in scoped_files:
                    scoped_files = sorted({*scoped_files, "TASKS.md"})
                log(
                    "Step 15: tracker follow-up staged for bot remediation "
                    f"({len(tracker_followup.get('tracker_paths') or [])} tracker-relevant file(s))"
                )

            staged_test_gate = _run_bot_remediation_staged_test_gate(
                repo_root,
                log=log,
            )
            if not staged_test_gate["passed"]:
                gate_errors = list(staged_test_gate.get("errors") or [])
                invalidated = _invalidate_bot_remediation_hook_receipt(
                    repo_root,
                    reason="bot-remediation staged validation failed before commit",
                )
                log(
                    "Step 15: bot-remediation staged test gate failed before "
                    f"commit: {gate_errors}; receipt_invalidated={invalidated}"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "errors": gate_errors,
                    "bot_remediation_gate": staged_test_gate,
                }

            # Mint bot-remediation receipt (type B) only after local staged
            # validation passes so the hook never accepts rejected staged test
            # content.
            bot_receipt = _mint_bot_remediation_receipt(
                repo_root=repo_root,
                findings_addressed=[
                    {"path": f.get("path", ""), "body": f.get("body", "")[:200]}
                    for f in current_findings
                ],
                scoped_files=scoped_files,
                round_num=round_num,
                wave_id=wave_id,
            )
            log(f"Step 15: bot-remediation receipt minted: {bot_receipt.name}")

            msg = (
                f"fix: address bot review findings (round {round_num})\n\n"
                f"Co-Authored-By: Codex <noreply@openai.com>"
            )
            _run(["git", "commit", "-m", msg], cwd=repo_root, timeout=60, env=_commit_subprocess_env())
            current_head = _run(
                ["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=10,
            ).stdout.strip()
            result["commit_sha"] = current_head
            remediation_checkpoint = dict(result)
            remediation_checkpoint["steps_completed"] = (
                _continuation_steps_for_new_commit(result.get("steps_completed"))
                or list(result.get("steps_completed", []))
            )
            remediation_checkpoint.pop("bot_review_request_sha", None)
            _checkpoint_post_commit_progress(
                remediation_checkpoint,
                continuation_path=continuation_path,
                target_branch=target_branch,
            )

            result["steps_completed"] = list(remediation_checkpoint["steps_completed"])

            pre_push_guard = _run_bot_remediation_pre_push_guard(
                repo_root,
                log=log,
            )
            if not pre_push_guard["passed"]:
                gate_errors = list(pre_push_guard.get("errors") or [])
                log(
                    "Step 15: bot-remediation pre-push gate failed before "
                    f"push: {gate_errors}"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "errors": gate_errors,
                    "bot_remediation_pre_push": pre_push_guard,
                }
            if "run_pre_push_script" not in remediation_checkpoint["steps_completed"]:
                remediation_checkpoint["steps_completed"].append("run_pre_push_script")
                _checkpoint_post_commit_progress(
                    remediation_checkpoint,
                    continuation_path=continuation_path,
                    target_branch=target_branch,
                )
                result["steps_completed"] = list(remediation_checkpoint["steps_completed"])

            # --no-verify on push: same rationale as step 12 — pre-push-fast
            # just validated this new remediation head locally.
            _run(
                ["git", "push", "--no-verify", "origin", target_branch],
                cwd=repo_root, timeout=300,
            )
            if "git_push" not in remediation_checkpoint["steps_completed"]:
                remediation_checkpoint["steps_completed"].append("git_push")
                _checkpoint_post_commit_progress(
                    remediation_checkpoint,
                    continuation_path=continuation_path,
                    target_branch=target_branch,
                )
                result["steps_completed"] = list(remediation_checkpoint["steps_completed"])
        except subprocess.CalledProcessError as exc:
            failure_detail = _tail_failure_excerpt(
                "\n".join(part for part in (exc.stderr, exc.stdout) if part),
                limit=1200,
            )
            if failure_detail:
                log(
                    f"Step 15: git operation failed in round {round_num}: "
                    f"{failure_detail}"
                )
            else:
                log(f"Step 15: git operation failed in round {round_num}: {exc}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
            }

        log(f"Step 15: remediation round {round_num} pushed ({current_head[:8]})")

        ci_response = _wait_for_pr_ci(
            repo_root,
            pr_number=pr_number,
            result=result,
            continuation_path=continuation_path,
            target_branch=target_branch,
            log=log,
            step_label=f"Step 15 remediation round {round_num}",
            # Make the Step-15-remediation CI-wait conflict-aware, mirroring the
            # Step-14 caller EXACTLY: a sibling lane that merges during this poll
            # flips the PR to CONFLICTING/DIRTY/BEHIND, GitHub then skips the
            # pull_request required checks, and without this the poll doom-spins
            # to the 900s surface timeout and strands the PR. base_branch = the
            # wave base (threaded from _run_post_commit_pipeline), the branch
            # _try_auto_resolve_pr_conflict fetches+merges FROM; branch_name = the
            # PR head (target_branch) this function already pushes to. Falls back
            # to None when base_branch was not threaded, leaving non-remediation/
            # direct-call sites behaviorally unchanged.
            midpoll_autoresolve=(
                {"base_branch": base_branch, "branch_name": target_branch}
                if base_branch
                else None
            ),
        )
        if ci_response is not None:
            # _wait_for_pr_ci can return two distinct non-None envelopes here:
            #   1. failure_class == "pr_conflicting" -- a sibling lane merged
            #      mid-poll and the Step-15 midpoll_autoresolve could not clear
            #      the conflict (e.g. _try_auto_resolve_pr_conflict aborts on a
            #      non-TASKS.md conflict). This is the SAME structured fail-closed
            #      envelope the Step-14 caller receives: an auto-resolvable
            #      PR-state signal (recovery Tier 2: base-merge + repush), NOT a
            #      bot finding. Return it verbatim -- exactly like the Step-14
            #      caller's `if ci_response is not None: return ci_response` -- so
            #      classify_failure honors failure_class=pr_conflicting. Wrapping
            #      it into bot_findings_pending would erase failure_class (and
            #      bot_findings_pending is matched AHEAD of pr_conflicting in
            #      classify_failure), misrouting recovery to Tier 3 (re-invoke
            #      implementer), which cannot merge the base branch and strands
            #      the PR.
            #   2. any other failure_class (a genuine CI/test break) -- the
            #      remediation round ran but CI is still red, so the findings are
            #      still pending; wrap into bot_findings_pending (carrying the
            #      findings + round count) so recovery re-invokes the implementer
            #      for another remediation round.
            if ci_response.get("failure_class") == "pr_conflicting":
                log(
                    f"Step 15: remediation round {round_num} CI wait hit an "
                    f"unresolved concurrent-base conflict; preserving the "
                    f"pr_conflicting recovery envelope instead of wrapping it as "
                    f"bot_findings_pending: {ci_response.get('errors', [])}"
                )
                return ci_response
            log(f"Step 15: CI did not pass after remediation round {round_num}: {ci_response.get('errors', [])}")
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
                "ci_failure": ci_response.get("errors", []),
            }
        log(f"Step 15: CI passed on remediation commit {current_head[:8]}")

        # The Step-15-remediation CI-wait above is conflict-aware
        # (midpoll_autoresolve, mirroring Step 14): a sibling lane that merges
        # mid-poll flips this PR to CONFLICTING, and _wait_for_pr_ci's mid-poll
        # re-check fires _try_auto_resolve_pr_conflict, which merges
        # origin/{base_branch} into the local worktree and repushes -- ADVANCING
        # the PR head past the remediation commit captured above. Re-read HEAD so
        # the post-CI current-head bot-review request + freshness wait (and their
        # _assert_expected_pr_head guard) and the subsequent finding extraction
        # all target the REAL new head. Without this refresh a remediation-time
        # auto-resolve leaves current_head stale, _assert_expected_pr_head rejects
        # the moved PR head with ValueError, and the PR is stranded on
        # bot_findings_pending (#49 bridge round 2). When no auto-resolve fired
        # (the normal path, and every direct base_branch=None call site) HEAD is
        # unchanged and this is a no-op, so those callers stay behaviorally
        # unchanged.
        refreshed_head = _run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=10,
        ).stdout.strip()
        if refreshed_head and refreshed_head != current_head:
            log(
                f"Step 15: PR head advanced {current_head[:8]} -> "
                f"{refreshed_head[:8]} after a mid-poll auto-resolve repush; "
                "retargeting the current-head bot-review request to the new head"
            )
            current_head = refreshed_head
            result["commit_sha"] = current_head

        # Request fresh bot review and wait
        try:
            _maybe_request_current_head_bot_review(
                repo_root, pr_number=pr_number, head_sha=current_head,
                continuation_path=continuation_path, log=log,
            )
            pr_data = _wait_for_bot_review_freshness(
                lambda: _query_pr_review_state(
                    repo_root, repo_owner=repo_owner,
                    repo_name=repo_name, pr_number=pr_number),
                head_sha=current_head,
                request_acknowledged=lambda pd: _bot_review_request_acknowledged(
                    repo_root, repo_owner=repo_owner,
                    repo_name=repo_name, pr_data=pd),
                log=log,
            )
        except TimeoutError as exc:
            # The remediation commit at current_head is already pushed and CI
            # passed at step 14 before we got here. The bot simply did not post
            # a fresh review/clearance within the wait window. Old findings
            # cannot be auto-deferred unless a current-head bot review or
            # current-head connector issue comment proves they still apply.
            # Per feedback_bot_comments_not_gates.md: "Bot comments are signal,
            # not gates." A timeout with no current-head proof skips report
            # creation and proceeds without manufacturing stale evidence. Closes
            # reports/deferred/blocking/commit_executor_bot_findings_false_positive_2026-04-17.md.
            #
            # SAFETY NOTE (hotfix 2026-04-17, closes bot P1 on PR #789):
            # ONLY TimeoutError is safe to auto-defer. Other exception types
            # (CalledProcessError, TimeoutExpired, JSONDecodeError,
            # ValueError from _assert_expected_pr_head) indicate genuine
            # state uncertainty (PR head changed, gh API failed, malformed
            # JSON, etc.) where auto-merging could land unreviewed code or
            # new commits pushed during remediation. Those fall through to
            # the catch-all below which preserves the prior safe bail-out to
            # bot_findings_pending.
            log(f"Step 15: review wait failed after round {round_num}: {exc}")
            try:
                timeout_pr_data = _query_pr_review_state(
                    repo_root,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                )
                timeout_findings_result = (
                    _extract_timeout_verified_current_head_findings(
                        timeout_pr_data,
                        current_head,
                        result=result,
                        pr_number=pr_number,
                    )
                )
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
            ) as state_exc:
                log(
                    f"Step 15: review-wait-timeout recheck failed with "
                    f"{type(state_exc).__name__}: {state_exc}; "
                    f"falling back to bot_findings_pending"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": current_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "review_wait_timeout": True,
                    "review_wait_failure_class": type(state_exc).__name__,
                }

            if timeout_findings_result["outcome"] == "error":
                timeout_response = timeout_findings_result["response"]
                timeout_response["review_wait_timeout"] = True
                return timeout_response

            if timeout_findings_result["outcome"] == "unverified":
                log(
                    f"Step 15: remediation commit {current_head[:8]} already pushed + "
                    f"CI green at step 14; no current-head bot review/comment "
                    f"proved findings still apply after timeout, so skipping "
                    f"auto-defer report and proceeding to merge"
                )
                return None

            if timeout_findings_result["outcome"] != "bot_findings":
                log(
                    f"Step 15: remediation commit {current_head[:8]} already pushed + "
                    f"CI green at step 14; current-head review snapshot is clean "
                    f"after timeout, so skipping auto-defer report and proceeding "
                    f"to merge"
                )
                return None

            verified_findings = timeout_findings_result["bot_findings"]
            log(
                f"Step 15: remediation commit {current_head[:8]} already pushed + "
                f"CI green at step 14; current-head review snapshot still has "
                f"{len(verified_findings)} bot finding(s), auto-deferring verified "
                f"current-head findings"
            )
            try:
                auto_defer_response = _auto_defer_bot_findings(
                    repo_root=repo_root,
                    findings=verified_findings,
                    wave_id=wave_id,
                    pr_number=pr_number,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    log=log,
                    round_num=round_num,
                    target_branch=target_branch,
                    continuation_path=continuation_path,
                    result=result,
                )
            except Exception as defer_exc:
                log(
                    f"Step 15: auto-defer after review-wait-timeout failed "
                    f"({defer_exc}); falling back to bot_findings_pending"
                )
                return {
                    "status": "bot_findings_pending",
                    "bot_findings": verified_findings,
                    "pr_number": pr_number,
                    "steps_completed": result["steps_completed"],
                    "remediation_rounds_attempted": round_num,
                    "review_wait_timeout": True,
                }
            if auto_defer_response is not None:
                auto_defer_response["review_wait_timeout"] = True
                return auto_defer_response
            log(
                f"Step 15: auto-defer succeeded after review-wait-timeout; "
                f"verified current-head findings committed and pushed to "
                f"reports/deferred/non_blocking/ before bot-thread resolution. "
                f"Proceeding to merge."
            )
            return None
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            # Non-timeout failures (gh API error, subprocess hang, bad JSON,
            # PR head moved) indicate state uncertainty — bail safely to
            # bot_findings_pending so a human can verify the PR state before
            # merge. Do NOT auto-defer these; doing so risks merging
            # unreviewed/new code. Preserves the pre-hotfix bail-out shape.
            log(
                f"Step 15: review wait failed after round {round_num} with "
                f"non-timeout exception {type(exc).__name__}: {exc} — "
                f"bailing to bot_findings_pending (do not auto-defer on "
                f"state-uncertainty failures)"
            )
            return {
                "status": "bot_findings_pending",
                "bot_findings": current_findings,
                "pr_number": pr_number,
                "steps_completed": result["steps_completed"],
                "remediation_rounds_attempted": round_num,
                "review_wait_failure_class": type(exc).__name__,
            }

        # Re-check findings
        findings_result = _extract_review_findings(
            pr_data, current_head, result=result, pr_number=pr_number,
        )
        if findings_result["outcome"] == "error":
            return findings_result["response"]
        if findings_result["outcome"] == "clean":
            log(f"Step 15: bot findings resolved after {round_num} remediation round(s)")
            return None
        current_findings = findings_result["bot_findings"]

    log(f"Step 15: bot findings remain after {BOT_REMEDIATION_MAX_ROUNDS} remediation rounds")
    return {
        "status": "bot_findings_pending",
        "bot_findings": current_findings,
        "pr_number": pr_number,
        "steps_completed": result["steps_completed"],
        "remediation_rounds_attempted": BOT_REMEDIATION_MAX_ROUNDS,
    }


def _wait_for_required_checks_to_register(
    repo_root: Path,
    *,
    pr_number: str,
    wait_seconds: int = CI_CHECK_REGISTRATION_WAIT_SECONDS,
    poll_interval: int = CI_CHECK_REGISTRATION_POLL_SECONDS,
    log: Any = None,
    midpoll_autoresolve: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Poll until the required checks register on PR ``pr_number``.

    Returns ``None`` once the required checks register (or were already
    present); raises ``TimeoutError`` / ``CalledProcessError`` on the normal
    failure paths exactly as before.

    ``midpoll_autoresolve`` is the conflict-aware mid-poll re-check context
    (``{"base_branch", "branch_name"}``) and defaults to ``None`` (disabled),
    so the two non-conflict-aware ``_wait_for_pr_ci`` call sites keep the
    registration loop unchanged. When present, each poll iteration (while
    no required checks have registered) re-checks ``_check_pr_conflict_state``:
    GitHub silently skips ``pull_request`` workflows on a CONFLICTING/DIRTY
    PR, so a PR that becomes conflicting mid-wait (e.g. a concurrent lane
    merged first) would otherwise spin here until the registration deadline.
    On a fresh transition to CONFLICTING/DIRTY since the wait began,
    ``_try_auto_resolve_pr_conflict`` is re-fired ONCE for that transition
    (the ``midpoll_prev_conflicting`` edge guard prevents repeated re-fires
    while the conflict persists). On ``resolved=true`` the auto-resolve's
    base-merge repush re-triggers the skipped workflows, so the checks then
    register and the loop returns ``None`` normally. On ``resolved=false``
    (aborted) the loop fails closed by returning a marker dict for
    ``_wait_for_pr_ci`` to convert into the Step-14-START ``pr_conflicting``
    envelope.
    """
    deadline = time.time() + wait_seconds
    midpoll_prev_conflicting = False
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
            return None
        if midpoll_autoresolve is not None:
            # Step-14 mid-poll conflict re-check. While no required checks
            # have registered, a concurrent lane that merged first can flip
            # this PR to CONFLICTING/DIRTY; GitHub then skips its pull_request
            # workflows, so the checks would never register and this loop
            # would spin to the deadline. Re-fire the SAME auto-resolve the
            # Step-14-START guard uses, exactly once per detected transition.
            conflict_state = _check_pr_conflict_state(
                repo_root, pr_number=pr_number, log=log
            )
            currently_conflicting = conflict_state is not None
            if currently_conflicting and not midpoll_prev_conflicting:
                if log is not None:
                    log(
                        f"Step 14 mid-poll: PR #{pr_number} became {conflict_state} "
                        "during required-checks registration wait; re-firing auto-resolve"
                    )
                resolve_kwargs = {
                    "pr_number": pr_number,
                    "base_branch": midpoll_autoresolve["base_branch"],
                    "branch_name": midpoll_autoresolve["branch_name"],
                    "log": log,
                }
                if "wave_id" in midpoll_autoresolve:
                    resolve_kwargs["wave_id"] = midpoll_autoresolve.get("wave_id")
                resolve_result = _try_auto_resolve_pr_conflict(
                    repo_root,
                    **resolve_kwargs,
                )
                if not resolve_result.get("resolved"):
                    # Fail closed: a non-tracker-note conflict or a fetch/
                    # merge/push failure. Do NOT spin to the registration
                    # deadline or proceed into the watch ceiling.
                    return {
                        "midpoll_conflict_aborted": True,
                        "auto_resolve_action": resolve_result.get("action", "aborted"),
                        "detail": resolve_result.get("detail", "unknown"),
                    }
                # resolved=true: the base-merge repush re-triggers the
                # previously-skipped workflows; keep polling so the
                # now-registering checks are observed.
            midpoll_prev_conflicting = currently_conflicting
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
    *,
    standalone: bool = False,
    bus_dir: str | Path | None = None,
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
        record_pager_route = str(record.get("pager_route") or "").strip()
        if "pager_route" not in embedded_copy and record_pager_route:
            embedded_copy["pager_route"] = record_pager_route
        valid, handoff_errors = validate_handoff(embedded_copy, repo_root=repo_root)
        if valid and not standalone:
            return embedded_copy, []
        if not valid:
            return None, [f"Embedded handoff invalid: {err}" for err in handoff_errors]
    else:
        embedded_copy = None

    # COMMIT_GO / COMMIT_GO_HOLD_PUSH require a pre-prepared handoff with
    # an exact Phase B receipt chain.  The supervisor receipt (written in
    # step 6) is the runtime commit-decision authority; the Phase B handoff
    # receipt provides provenance traceability.  Synthesizing a handoff here
    # would lack both, so only embedded handoffs (validated above) are accepted.
    if not standalone and decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        return None, [
            f"{decision} requires a pre-prepared Phase B handoff (or valid "
            f"embedded handoff). Cannot synthesize a handoff from a routing "
            f"record — the receipt chain would be broken."
        ]

    # For UPDATE_TRACKER_ONLY: construct a minimal tracker-only handoff
    candidates = record.get("next_candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    files_to_stage = record.get("files_to_stage", [])
    tracker_note = record.get("tracker_note_text", "")

    def has_nonblank_list_item(value: Any) -> bool:
        return isinstance(value, list) and any(str(item).strip() for item in value)

    candidate_has_scope = any(
        isinstance(c, dict)
        and (
            str(c.get("tracked_packet") or "").strip()
            or has_nonblank_list_item(c.get("files"))
        )
        for c in candidates
    )
    if (
        decision == "UPDATE_TRACKER_ONLY"
        and not standalone
        and not (isinstance(tracker_note, str) and tracker_note.strip())
        and not has_nonblank_list_item(files_to_stage)
        and not has_nonblank_list_item(record.get("force_add_files"))
        and not candidate_has_scope
    ):
        return None, [
            "UPDATE_TRACKER_ONLY routing record has no actionable tracker scope "
            "(tracker_note_text, files_to_stage, force_add_files, tracked_packet, "
            "or candidate files). Refusing to synthesize a TASKS.md-only handoff."
        ]

    # Try to derive files_to_stage from candidates if not directly provided
    if not files_to_stage:
        for c in candidates:
            cf = c.get("files", [])
            if cf:
                files_to_stage.extend(cf)

    if not files_to_stage:
        # Default to TASKS.md for tracker-only updates
        if decision == "UPDATE_TRACKER_ONLY":
            files_to_stage = ["TASKS.md"]
        elif not standalone:
            errors.append("Cannot derive files_to_stage from routing record")

    if errors:
        return None, errors

    # Normalize wave_id for branch naming
    wave_id = normalize_wave_id(wave_name)
    if standalone and not _tracked_packet_path_from_record(record):
        staged_packet = _discover_staged_same_wave_control_packet(repo_root, wave_id)
        if staged_packet:
            record = copy.deepcopy(record)
            record["tracked_packet"] = staged_packet
    wave_class = _resolve_wave_class(
        record,
        repo_root,
        embedded_handoff=embedded_copy,
    )
    target_gate_id = _resolve_target_gate_id(
        record,
        repo_root,
        embedded_handoff=embedded_copy,
    )
    default_commit_message = (
        f"chore: {summary}\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
    )
    commit_message = record.get("commit_message", default_commit_message)
    if commit_message is None:
        commit_message = default_commit_message
    elif not isinstance(commit_message, str):
        commit_message = str(commit_message)
    raw_force_add_files = record.get("force_add_files")
    force_add_files = [] if raw_force_add_files is None else raw_force_add_files

    if standalone:
        staged_files = _current_staged_diff_paths(repo_root)
        if not staged_files:
            return None, [
                "Standalone routing-record regeneration requires a non-empty staged diff"
            ]
        standalone_target_branch = (embedded_copy or {}).get("target_branch")
        if not isinstance(standalone_target_branch, str) or not standalone_target_branch.strip():
            standalone_target_branch = record.get("target_branch")
        unblocks_wave_id, unblocks_runtime_blocker = _extract_maintenance_bypass_from_routing_record(
            record,
            repo_root,
            embedded_handoff=embedded_copy,
        )
        wave_id = normalize_wave_id(
            str(
                (embedded_copy or {}).get("wave_id")
                or wave_name
            )
        )
        standalone_wave_class = _resolve_wave_class(
            record,
            repo_root,
            embedded_handoff=embedded_copy,
        )
        founder_override_token, override_error = _resolve_standalone_founder_override_token(
            record,
            repo_root,
            embedded_handoff=embedded_copy,
            wave_id=wave_id,
            wave_class=standalone_wave_class,
        )
        if override_error:
            return None, [override_error]
        commit_message = _build_standalone_commit_message(wave_id)
        standalone_tracker_note = (
            str(record.get("tracker_note_text") or "").strip()
            or str((embedded_copy or {}).get("tracker_note_text") or "").strip()
            or _extract_existing_canonical_tracker_note_from_tasks(
                repo_root,
                wave_id,
                wave_class=standalone_wave_class,
                target_gate_id=target_gate_id,
            )
        )
        handoff, build_errors = build_commit_handoff(
            wave_id=wave_id,
            task_id=str((embedded_copy or {}).get("task_id") or record.get("task_id", f"[{wave_name}]")),
            files_to_stage=staged_files,
            commit_message=commit_message,
            fixes_implemented=_build_standalone_staged_diff_fixes(staged_files),
            wave_class=standalone_wave_class,
            target_gate_id=target_gate_id,
            caller="standalone",
            base_branch=str((embedded_copy or {}).get("base_branch") or "dev"),
            branch_prefix=str((embedded_copy or {}).get("branch_prefix") or "jabramsja"),
            pr_title=commit_message[:70],
            pr_body=None,
            tracker_note_text=standalone_tracker_note or None,
            tracked_packet=_tracked_packet_path_from_record(record) or None,
            supervisor_lane=(embedded_copy or {}).get("supervisor_lane"),
            deferred_items=(embedded_copy or {}).get("deferred_items"),
            bridge_status=(embedded_copy or {}).get("bridge_status"),
            scope_items=staged_files,
            evidence_handles=None,
            pre_commit_receipt_path="",
            target_branch=(
                standalone_target_branch.strip()
                if isinstance(standalone_target_branch, str) and standalone_target_branch.strip()
                else None
            ),
            repo_root=repo_root,
            bus_dir=bus_dir,
            founder_override_token=founder_override_token,
            unblocks_wave_id=unblocks_wave_id,
            unblocks_runtime_blocker=unblocks_runtime_blocker,
            pager_route=str(
                (embedded_copy or {}).get("pager_route")
                or record.get("pager_route")
                or ""
            ).strip() or None,
        )
        if build_errors:
            return None, build_errors
        return handoff, []

    # UPDATE_TRACKER_ONLY routing records may omit tracker_note_text. In that
    # case, synthesize the same contract-complete note shape that validate_handoff
    # now requires instead of the older one-line fallback.
    founder_override_token = ""
    unblocks_wave_id = ""
    unblocks_runtime_blocker = ""
    if decision == "UPDATE_TRACKER_ONLY" and not tracker_note:
        founder_override_token = _extract_founder_override_from_routing_record(
            record,
            repo_root,
        )
        if not founder_override_token:
            founder_override_token = _extract_same_wave_founder_override_from_tasks(
                repo_root,
                wave_id,
            )
        unblocks_wave_id, unblocks_runtime_blocker = _extract_maintenance_bypass_from_routing_record(
            record,
            repo_root,
        )

    handoff, build_errors = build_commit_handoff(
        wave_id=wave_id,
        task_id=str(record.get("task_id", f"[{wave_name}]")),
        files_to_stage=files_to_stage,
        commit_message=commit_message,
        fixes_implemented=record.get("fixes_implemented", [summary]),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        caller=_caller_for_synthesized_routing_handoff(
            decision,
            files_to_stage,
            force_add_files,
        ),
        base_branch="dev",
        branch_prefix="jabramsja",
        force_add_files=force_add_files,
        pr_title=record.get("pr_title", f"chore: {summary}"[:70]),
        pr_body=record.get("pr_body", f"## Summary\n\n- {summary}"),
        tracker_note_text=tracker_note or None,
        tracked_packet=_tracked_packet_path_from_record(record) or None,
        pre_commit_receipt_path=str(agent_bus_relpath(bus_dir, "meta", "pre_commit_receipt.json")),
        repo_root=repo_root,
        bus_dir=bus_dir,
        founder_override_token=founder_override_token or None,
        unblocks_wave_id=unblocks_wave_id,
        unblocks_runtime_blocker=unblocks_runtime_blocker,
        pager_route=str(record.get("pager_route") or "").strip() or None,
    )
    if build_errors:
        return None, build_errors
    return handoff, []


_TRACKER_ONLY_EXACT_PATHS = frozenset({"TASKS.md", "STATUS.md", "CHANGELOG.md"})
_TRACKER_ONLY_PREFIXES = (
    "reports/control_plane/",
    "reports/l4_wave_indicators/",
    "reports/deferred/",
    "reports/archive/",
)


def _is_tracker_only_handoff_path(path: Any) -> bool:
    normalized = _normalize_repo_relpath(str(path or ""))
    if not normalized:
        return True
    if normalized in _TRACKER_ONLY_EXACT_PATHS:
        return True
    return normalized.startswith(_TRACKER_ONLY_PREFIXES)


def _caller_for_synthesized_routing_handoff(
    decision: str,
    files_to_stage: list[str],
    force_add_files: list[str],
) -> str:
    if decision != "UPDATE_TRACKER_ONLY":
        return "phase_b"
    scoped_paths = [*files_to_stage, *force_add_files]
    if scoped_paths and all(_is_tracker_only_handoff_path(path) for path in scoped_paths):
        return "update_tracker_only"
    return "phase_b"


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
    target_branch: str | None = None,
    force_add_files: list[str] | None = None,
    pr_title: str | None = None,
    pr_body: str | None = None,
    tracker_note_text: str | None = None,
    tracked_packet: str | None = None,
    supervisor_lane: str | None = None,
    deferred_items: list[str] | None = None,
    bridge_status: dict[str, Any] | None = None,
    scope_items: list[str] | None = None,
    evidence_handles: dict[str, str] | None = None,
    pre_commit_receipt_path: str | None = None,
    repo_root: Path | None = None,
    founder_override_token: str | None = None,
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    bus_dir: str | Path | None = None,
    pager_route: str | None = None,
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
        effective_files = _canonicalize_stage_paths(repo_root, effective_files)
        effective_force = _canonicalize_stage_paths(repo_root, effective_force)
        for f in list(effective_files):
            try:
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", "-q", f],
                    cwd=repo_root, capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    effective_files.remove(f)
                    if f not in effective_force:
                        effective_force.append(f)
            except (subprocess.SubprocessError, OSError):
                pass

    # 2026-04-11 git multi-path .claude pathspec resolver workaround
    # (PR pipeline-followups-2026-04-11):
    # Move any `.claude/...` paths that slipped past the check-ignore probe
    # above into `force_add_files`. This works around a git quirk where
    # multi-path `git add -- .claude/hooks/foo.sh mu/tools/bar.py` fails
    # with "The following paths are ignored by one of your .gitignore
    # files: .claude" even though `git check-ignore -q .claude/hooks/foo.sh`
    # returns NOT ignored (the negation rule `!.claude/hooks/` at line 106
    # of .gitignore is honored by single-path add but the multi-path
    # resolver short-circuits at the parent `.claude/` ignore rule at line
    # 104 before walking the negation chain). `git add -f` bypasses the
    # short-circuit, and commit_executor's Step 4 uses `git add -f` for
    # `force_add_files`, so moving these paths there avoids the issue.
    #
    # Verified 2026-04-11 via 3 controlled tests in worktree
    # workingrcx_hook_denylist_1775885905:
    #   `git add -- .claude/hooks/check-reasoning-depth.sh` → exit 0
    #   `git add -- mu/tools/runners/run_review.py mu/tests/tools/test_run_review.py` → exit 0
    #   `git add -- .claude/hooks/check-reasoning-depth.sh mu/tools/runners/run_review.py` → exit 1
    #   `git add -f -- .claude/hooks/check-reasoning-depth.sh mu/tools/runners/run_review.py` → exit 0
    #
    # The fix is minimal: only `.claude/...` paths are affected (other
    # negation-rule directories under an ignored parent could have the
    # same issue but this is the only one currently in use). If the bug
    # is ever fixed in git or the project's .gitignore structure changes,
    # this workaround is safe to leave in place (force_add_files uses
    # `git add -f` which is a superset of `git add`).
    for f in list(effective_files):
        if f.startswith(".claude/") or f.startswith("./.claude/"):
            effective_files.remove(f)
            if f not in effective_force:
                effective_force.append(f)
    effective_files = _dedupe_repo_paths(effective_files)
    effective_force = _dedupe_repo_paths(effective_force)

    # Auto-find latest COMMIT_GO receipt if not provided
    # Use the canonical receipt path — no directory-sort discovery.
    # The commit executor's Step 6 runs the supervisor and gets a fresh
    # per-invocation receipt. This handoff receipt is provenance only.
    if caller == "standalone" and pre_commit_receipt_path == "":
        effective_receipt = ""
    else:
        effective_receipt = pre_commit_receipt_path or str(
            agent_bus_relpath(bus_dir, "meta", "pre_commit_receipt.json")
        )

    effective_founder_override_token = _normalize_founder_override_token(founder_override_token)
    tracker_note_founder_override_token = ""
    if isinstance(tracker_note_text, str):
        tracker_note_founder_override_token = _extract_founder_override_from_tracker_note(
            tracker_note_text
        )
        if (
            not effective_founder_override_token
            and normalize_wave_id(tracker_note_founder_override_token) == normalize_wave_id(wave_id)
        ):
            effective_founder_override_token = tracker_note_founder_override_token
    if (
        (
            not effective_founder_override_token
            or normalize_wave_id(effective_founder_override_token) != normalize_wave_id(wave_id)
        )
        and tracked_packet
        and repo_root is not None
        and str(wave_class or "").strip() == "L4_ENABLER"
    ):
        resolved_control_surface_token = _resolve_control_surface_founder_override_token(
            {
                "wave_id": wave_id,
                "wave_name": wave_id,
                "tracked_packet": tracked_packet,
                "tracker_note_text": tracker_note_text or "",
            },
            repo_root,
            wave_id=wave_id,
            wave_class=wave_class,
        )
        if resolved_control_surface_token:
            effective_founder_override_token = resolved_control_surface_token
    if not effective_founder_override_token and tracker_note_founder_override_token:
        effective_founder_override_token = tracker_note_founder_override_token

    if (
        caller == "standalone"
        and str(wave_class or "").strip() == "L4_ENABLER"
        and not effective_founder_override_token
    ):
        return {}, [_missing_founder_override_error(wave_id)]

    effective_tracker_note = tracker_note_text or _build_default_tracker_note_text(
        wave_id=wave_id,
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        commit_message=commit_message,
        files_to_stage=effective_files + effective_force,
        founder_override_token=effective_founder_override_token,
        unblocks_wave_id=unblocks_wave_id,
        unblocks_runtime_blocker=unblocks_runtime_blocker,
        tracked_packet=tracked_packet or "",
    )
    existing_tracker_override = _extract_founder_override_from_tracker_note(
        effective_tracker_note
    )
    if (
        effective_founder_override_token
        and existing_tracker_override
        and normalize_wave_id(existing_tracker_override) != normalize_wave_id(effective_founder_override_token)
    ):
        effective_tracker_note = _replace_founder_override_token(
            effective_tracker_note,
            effective_founder_override_token,
        )
    else:
        effective_tracker_note = _append_founder_override_to_tracker_note(
            effective_tracker_note,
            effective_founder_override_token,
        )

    handoff = {
        "wave_id": wave_id,
        "task_id": task_id,
        "wave_class": wave_class,
        "target_gate_id": target_gate_id,
        "caller": caller,
        "branch_prefix": branch_prefix,
        "tracker_note_text": effective_tracker_note,
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
    normalized_pager_route = str(pager_route or "").strip()
    if normalized_pager_route:
        handoff["pager_route"] = normalized_pager_route
    if supervisor_lane:
        handoff["supervisor_lane"] = supervisor_lane
    if deferred_items is not None:
        handoff["deferred_items"] = deferred_items
    if bridge_status is not None:
        handoff["bridge_status"] = bridge_status
    if scope_items:
        handoff["scope_items"] = scope_items
    if evidence_handles:
        handoff["evidence_handles"] = evidence_handles
    if tracked_packet:
        handoff["tracked_packet"] = _normalize_repo_relpath(tracked_packet)
    if isinstance(target_branch, str) and target_branch.strip():
        handoff["target_branch"] = target_branch.strip()

    # Validate against schema
    valid, validation_errors = validate_handoff(handoff, repo_root=repo_root)
    if not valid:
        return handoff, validation_errors

    return handoff, []


def validate_handoff(
    handoff: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """Step 1: Validate all handoff fields."""
    if not isinstance(handoff, dict):
        return False, ["Handoff must be a JSON object"]

    errors: list[str] = []

    allowed_fields = REQUIRED_HANDOFF_FIELDS | OPTIONAL_HANDOFF_FIELDS
    unexpected = sorted(set(handoff.keys()) - allowed_fields)
    if unexpected:
        errors.extend(f"Unexpected field: {field}" for field in unexpected)

    # Required fields (standalone caller relaxes some fields)
    is_standalone = handoff.get("caller") == "standalone"
    effective_required = REQUIRED_HANDOFF_FIELDS - (STANDALONE_OPTIONAL_FIELDS if is_standalone else set())
    missing = effective_required - set(handoff.keys())
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
    # Standalone caller may omit this (supervisor is skipped, no receipt needed)
    receipt_path_val = handoff.get("pre_commit_receipt_path")
    if is_standalone and (not receipt_path_val or receipt_path_val == ""):
        pass  # standalone: receipt path not required
    elif not isinstance(receipt_path_val, str):
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

    # files_to_stage must be a list. It can be EMPTY only when
    # force_add_files is non-empty (e.g. a `.claude/`-only commit
    # where build_commit_handoff's auto-move routed every path to
    # force_add_files via the string-startswith check). A commit with
    # zero total files (both lists empty) is still an error.
    #
    # Rationale: `git add -f` at commit_executor Step 4 correctly
    # handles force_add_files entries regardless of whether
    # files_to_stage is also populated. Requiring files_to_stage
    # non-empty INDEPENDENTLY would forbid an otherwise-valid class
    # of commits — any wave whose entire scope lives under `.claude/`
    # (hook/config/skill hardening waves). This was diagnosed during
    # the block-protected-branch-lexer follow-up wave 2026-04-11 when
    # the 3-file `.claude/hooks/*` commit could not produce a valid
    # handoff despite the dirty files being semantically commit-ready.
    fts = handoff.get("files_to_stage")
    _faf_preview = handoff.get("force_add_files")
    _has_force_add = isinstance(_faf_preview, list) and len(_faf_preview) > 0
    if not isinstance(fts, list):
        errors.append("files_to_stage must be a list")
    elif not fts and not _has_force_add:
        errors.append(
            "files_to_stage or force_add_files must be non-empty "
            "(commit must have at least one file)"
        )
    elif fts and not all(isinstance(f, str) for f in fts):
        errors.append("files_to_stage entries must be strings")
    else:
        for f in fts:
            if _is_absolute_untrusted_path(f):
                errors.append(f"Absolute path in files_to_stage: {f}")
            if _has_path_traversal(f):
                errors.append(f"Path traversal in files_to_stage: {f}")
            denied = _runtime_bus_artifact_match(f)
            if denied:
                errors.append(f"files_to_stage denied: {f} (matches {denied})")

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

    deferred_stage_paths = deferred_items if isinstance(deferred_items, list) else []
    same_wave_active = _same_wave_active_deferred_non_blocking_paths(
        wave_id,
        [*fts, *faf, *deferred_stage_paths],
        repo_root=repo_root,
    ) if isinstance(fts, list) and isinstance(faf, list) else []
    same_wave_archive = _same_wave_closed_deferred_archive_paths(
        wave_id,
        [*fts, *faf, *deferred_stage_paths],
    ) if isinstance(fts, list) and isinstance(faf, list) else []
    if same_wave_active and same_wave_archive:
        errors.append(
            "same-wave generated bridge packet is both active deferred "
            f"and archived closed for {wave_id}: active={same_wave_active}, "
            f"archive={same_wave_archive}. Remove the active deferred packet "
            "or reopen the archive before commit."
        )

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

    pager_route = handoff.get("pager_route")
    if pager_route is not None:
        if not isinstance(pager_route, str) or not pager_route.strip():
            errors.append("pager_route must be a non-empty string when provided")
        elif pager_route.strip() not in ALLOWED_HANDOFF_PAGER_ROUTES:
            errors.append(
                "pager_route must be one of "
                f"{sorted(ALLOWED_HANDOFF_PAGER_ROUTES)}, got: {pager_route}"
            )

    tracked_packet = handoff.get("tracked_packet")
    if tracked_packet is not None:
        if not isinstance(tracked_packet, str) or not tracked_packet.strip():
            errors.append("tracked_packet must be a non-empty string when provided")
        else:
            normalized_packet = _normalize_repo_relpath(tracked_packet)
            if _is_absolute_untrusted_path(normalized_packet):
                errors.append(f"Absolute path in tracked_packet: {tracked_packet}")
            if _has_path_traversal(normalized_packet):
                errors.append(f"Path traversal in tracked_packet: {tracked_packet}")
            if not normalized_packet.startswith("reports/control_plane/") or not normalized_packet.endswith(".md"):
                errors.append(
                    "tracked_packet must name a reports/control_plane/*.md packet, "
                    f"got: {tracked_packet}"
                )

    # tracker_note_text must be non-empty string
    tnt = handoff.get("tracker_note_text", "")
    if not isinstance(tnt, str) or not tnt.strip():
        errors.append("tracker_note_text must be a non-empty string")
    else:
        errors.extend(
            _validate_tracker_note_text(
                tracker_note_text=tnt,
                wave_id=str(handoff.get("wave_id", "")),
                wave_class=str(handoff.get("wave_class", "")),
                target_gate_id=str(handoff.get("target_gate_id", "")),
            )
        )

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
    target_gate_id = handoff.get("target_gate_id")
    if isinstance(target_gate_id, str) and target_gate_id.strip():
        normalized_gate = _normalize_target_gate_id(target_gate_id)
        if not normalized_gate:
            errors.append(f"target_gate_id must match G1-G8, got: {target_gate_id}")

    branch_prefix = handoff.get("branch_prefix", "")
    if isinstance(branch_prefix, str) and branch_prefix and not BRANCH_PREFIX_RE.fullmatch(branch_prefix):
        errors.append(f"branch_prefix contains unsafe characters: {branch_prefix}")
    target_branch = handoff.get("target_branch")
    if target_branch is not None:
        if not isinstance(target_branch, str) or not target_branch.strip():
            errors.append("target_branch must be a non-empty string when provided")
        else:
            normalized_target_branch = target_branch.strip()
            if not _is_wave_bound_target_branch(
                normalized_target_branch,
                branch_prefix=str(branch_prefix or ""),
                wave_id=str(wave_id or ""),
            ) and not _is_authorized_control_surface_repair_target_branch(
                handoff,
                repo_root,
                normalized_target_branch,
                branch_prefix=str(branch_prefix or ""),
                wave_id=str(wave_id or ""),
            ):
                errors.append(
                    "target_branch must equal the canonical wave branch or a "
                    "restart branch derived from wave_id, unless this is an "
                    "authorized standalone control-surface L4_ENABLER repair "
                    f"under the branch prefix for wave_id '{wave_id}': "
                    f"{normalized_target_branch}"
                )

    # Caller validation
    caller = handoff.get("caller", "")
    if caller and caller not in VALID_CALLERS:
        errors.append(f"caller must be one of {sorted(VALID_CALLERS)}, got: {caller}")

    return len(errors) == 0, errors


_STASH_REF_RE = re.compile(r"^stash@\{(\d+)\}")


def _is_pipeline_owned_cleanup_stash(
    stash_line: str,
    *,
    wave_id: str,
    target_branch: str,
) -> bool:
    """Return true only for executor-owned stash markers for this wave."""
    markers = [
        f"phase_b:{target_branch}:",
        f"phase_b:{wave_id}:",
    ]
    return any(marker in stash_line for marker in markers if marker)


def _post_merge_cleanup(
    *,
    cleanup_root: Path,
    repo_root: Path,
    target_branch: str,
    base_branch: str,
    wave_id: str,
    log: Any,
) -> dict[str, Any]:
    """Best-effort cleanup after a PR merge succeeds.

    Runs from *cleanup_root* (main repo after ff-only to origin/base_branch).
    Deletes the merged local branch, removes the wave worktree if distinct,
    and drops executor-owned Phase B branch-switch stashes for *wave_id*.

    All failures are logged and swallowed; the merge has already succeeded
    and cleanup must never regress the pipeline.

    Returns a dict with the per-substep outcomes (for test assertions).
    """
    outcome: dict[str, Any] = {
        "branch_deleted": False,
        "worktree_removed": False,
        "stashes_dropped": 0,
        "warnings": [],
    }

    try:
        cleanup_branch = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cleanup_root
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        outcome["warnings"].append(f"cannot resolve cleanup_root HEAD: {exc}")
        return outcome

    if cleanup_branch != base_branch:
        outcome["warnings"].append(
            f"cleanup_root {cleanup_root} is on '{cleanup_branch}', expected "
            f"'{base_branch}'; skipping cleanup to avoid deleting the wrong branch"
        )
        return outcome

    # 16b: remove worktree FIRST so the branch it holds is unlocked for 16a.
    # git rejects `branch -D` on a branch checked out by any linked worktree.
    try:
        repo_root_real = repo_root.resolve()
    except OSError:
        repo_root_real = repo_root
    try:
        cleanup_root_real = cleanup_root.resolve()
    except OSError:
        cleanup_root_real = cleanup_root
    # Refuse to touch the main worktree. Git refuses `worktree remove` on the
    # primary worktree, and attempting it would leave the branch checked out
    # so the subsequent `branch -D` also fails. Main worktree's `.git` is a
    # DIRECTORY; a linked worktree's `.git` is a FILE pointing at
    # `<main>/.git/worktrees/<name>/`. Only attempt removal when the path is
    # a linked worktree AND distinct from cleanup_root.
    repo_git_path = repo_root_real / ".git"
    is_linked_worktree = repo_git_path.is_file()
    if (
        repo_root_real != cleanup_root_real
        and repo_root_real.exists()
        and is_linked_worktree
    ):
        try:
            _run(
                ["git", "worktree", "remove", "--force", str(repo_root_real)],
                cwd=cleanup_root, timeout=30,
            )
            outcome["worktree_removed"] = True
            log(f"Step 16b: removed worktree {repo_root_real}")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            outcome["warnings"].append(f"worktree remove: {detail[:200]}")
            log(f"Step 16b worktree remove warning: {detail[:200]}")
        except subprocess.TimeoutExpired:
            outcome["warnings"].append("worktree remove timed out")
            log("Step 16b worktree remove timed out")

    # 16a: delete the merged local branch (now unlocked if step 16b ran)
    try:
        _run(["git", "branch", "-D", target_branch], cwd=cleanup_root, timeout=30)
        outcome["branch_deleted"] = True
        log(f"Step 16a: deleted local branch {target_branch}")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        outcome["warnings"].append(f"branch delete: {detail[:200]}")
        log(f"Step 16a branch delete warning: {detail[:200]}")
    except subprocess.TimeoutExpired:
        outcome["warnings"].append("branch delete timed out")
        log("Step 16a branch delete timed out")

    # 16c: drop executor-owned stashes for this wave. Do not drop arbitrary
    # user/operator stashes just because their description mentions the wave_id.
    # Drop highest-index first so remaining refs stay stable during loop.
    if wave_id:
        try:
            stash_out = _run(
                ["git", "stash", "list"], cwd=cleanup_root, timeout=30
            ).stdout
            refs_to_drop: list[tuple[int, str]] = []
            for line in stash_out.splitlines():
                if not _is_pipeline_owned_cleanup_stash(
                    line,
                    wave_id=wave_id,
                    target_branch=target_branch,
                ):
                    continue
                ref = line.split(":", 1)[0]
                m = _STASH_REF_RE.match(ref)
                if m is None:
                    continue
                refs_to_drop.append((int(m.group(1)), ref))
            refs_to_drop.sort(reverse=True)
            for _idx, ref in refs_to_drop:
                try:
                    _run(["git", "stash", "drop", ref], cwd=cleanup_root, timeout=30)
                    outcome["stashes_dropped"] += 1
                except subprocess.CalledProcessError as exc:
                    detail = (exc.stderr or exc.stdout or str(exc)).strip()
                    outcome["warnings"].append(f"stash drop {ref}: {detail[:200]}")
                    log(f"Step 16c stash drop {ref} warning: {detail[:200]}")
                except subprocess.TimeoutExpired:
                    outcome["warnings"].append(f"stash drop {ref} timed out")
                    log(f"Step 16c stash drop {ref} timed out")
            if outcome["stashes_dropped"]:
                log(
                    f"Step 16c: dropped {outcome['stashes_dropped']} stash(es) "
                    f"owned by pipeline markers for {wave_id}"
                )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            outcome["warnings"].append(f"stash list: {detail[:200]}")
            log(f"Step 16c stash list warning: {detail[:200]}")
        except subprocess.TimeoutExpired:
            outcome["warnings"].append("stash list timed out")
            log("Step 16c stash list timed out")

    return outcome


def _queue_entry_backtick_value(line: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*`([^`]+)`", line)
    return match.group(1).strip() if match else ""


def _tracker_note_wave_id(line: str) -> str:
    match = re.search(r"Tracker sync note\s*\([^,]+,\s*([^)]+)\)", line)
    return match.group(1).strip() if match else ""


def _line_is_next_codex_post_redteam_queue_entry(line: str) -> bool:
    return (
        "FOUNDER-ORDERED-REDTEAM-" in line
        or "NEXT-CODEX-POST-REDTEAM" in line
    )


_PROGRAM_QUEUE_HEADER_RE = re.compile(r"^##\s+PROGRAM QUEUE\b", re.IGNORECASE)
_PROGRAM_QUEUE_NUMBERED_ENTRY_RE = re.compile(
    r"^\s*(?P<order>\d+)\.\s+\*\*(?P<label>[^*]+?)\*\*\s*(?P<tail>.*?)\s*$"
)
_PROGRAM_QUEUE_UNNUMBERED_BATON_RE = re.compile(
    r"^\s*\*\*Unnumbered (?:prerequisite|reconstruction) baton — "
    r"(?P<label>[^*]+?)\*\*\s*$"
)
_WAVE_ID_DATE_SUFFIX_RE = re.compile(r"-\d{4}-\d{2}-\d{2}[a-z]?$")
_SIMPLE_QUEUE_TERMINAL_MARKER_RE = re.compile(
    r"\b(?:COMPLETED|LANDED|MERGED|CLOSED|CURRENT[-_\s]+DEV|POST[-_\s]+MERGE(?:D)?)\b",
    re.IGNORECASE,
)
_SIMPLE_QUEUE_PRECOMMIT_MARKER_RE = re.compile(
    r"\b(?:PRE[-_\s]*COMMIT|RECEIPT\s+PENDING|COMMIT[-_\s]*READY|"
    r"LOCAL\s+EVIDENCE|PACKAGE[-_\s]*BOUND|PENDING)\b",
    re.IGNORECASE,
)
_SIMPLE_QUEUE_STATE_TRAILER_RE = re.compile(
    r"(?:\s+|\s*[-\u2013\u2014]+\s*)"
    r"(?P<state>NEXT|AFTER\s+BOTH|LAST(?:\s*\([^)]*\))?|"
    r"LANDED(?:\s+in\s+PR\s+#?\d+(?:\s+\([^)]*\))?)?|"
    r"MERGED(?:\s+in\s+PR\s+#?\d+(?:\s+\([^)]*\))?)?|"
    r"COMPLETED|CLOSED|CURRENT[-_\s]+DEV|CURRENT)"
    r"\.?\s*$",
    re.IGNORECASE,
)
_EXPLICIT_BRACKETED_WAVE_LABEL_RE = re.compile(
    r"^\[(?P<wave_id>[A-Za-z0-9][A-Za-z0-9_-]*-\d{4}-\d{2}-\d{2}[a-z]?)\]$"
)


_MU_STRUCTURAL_PHASE_A_AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?:ROUTED\s*[-/]\s*)?PHASE\s+A\s+(?:REQUIRED|AUTHORIZED|LOCKED)\b"
)


def _queue_entry_category_is_mu_structural(category: Any) -> bool:
    category_lower = str(category or "").lower()
    return "structural" in category_lower and (
        "/mu" in category_lower or "mu structural" in category_lower
    )


def _queue_entry_has_explicit_mu_structural_authorization(
    *,
    category: Any,
    line: str,
    state: Any,
    status: Any,
    wave_id: str,
) -> bool:
    if not _queue_entry_category_is_mu_structural(category):
        return False
    if _extract_same_wave_founder_override_token(line, wave_id):
        return True
    explicit_state = "\n".join(str(value or "") for value in (state, status))
    return bool(_MU_STRUCTURAL_PHASE_A_AUTHORIZATION_RE.search(explicit_state))


_FULL_QUEUE_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_QUEUE_PACKET_SCAN_LIMIT = 40


class QueueCommitAuthorityError(RuntimeError):
    """Exact queue-object authority could not be read without fallback."""


def _queue_repo_relpath_error(field_name: str, raw_path: str) -> str | None:
    """Return an error for a path that is unsafe in a SHA-qualified object read."""
    path = _normalize_repo_relpath(raw_path)
    error = _path_field_error(field_name, path)
    if error:
        return error
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        return f"{field_name} contains control characters: {path!r}"
    if ":" in path:
        return f"{field_name} contains a Git revision separator: {path!r}"
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return f"{field_name} must be a normalized repo-relative path: {path!r}"
    return None


def _validated_queue_repo_relpath(field_name: str, raw_path: str) -> str:
    path = _normalize_repo_relpath(raw_path)
    error = _queue_repo_relpath_error(field_name, path)
    if error:
        raise QueueCommitAuthorityError(error)
    return path


def _queue_git_object_output(
    repo_root: Path,
    args: list[str],
    *,
    operation: str,
) -> str:
    """Run one fail-closed Git-object query and return its text output."""
    try:
        proc = _run(args, cwd=repo_root, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise QueueCommitAuthorityError(
            f"exact queue {operation} failed: {exc}"
        ) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
        raise QueueCommitAuthorityError(
            f"exact queue {operation} failed: {detail[:500]}"
        )
    return proc.stdout


def _validate_queue_commit_sha(repo_root: Path, queue_commit_sha: str) -> str:
    """Validate one immutable full commit SHA without resolving a symbolic ref."""
    commit_sha = str(queue_commit_sha or "").strip()
    if not commit_sha:
        return ""
    if not _FULL_QUEUE_COMMIT_SHA_RE.fullmatch(commit_sha):
        raise QueueCommitAuthorityError(
            "queue_commit_sha must be a full lowercase 40-hex commit SHA"
        )
    _queue_git_object_output(
        repo_root,
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        operation=f"commit validation at {commit_sha}",
    )
    return commit_sha


def _queue_commit_tree_paths(
    repo_root: Path,
    *,
    queue_commit_sha: str,
    tree_prefix: str,
) -> list[str]:
    """Enumerate validated paths below ``tree_prefix`` at one exact commit."""
    commit_sha = str(queue_commit_sha or "").strip()
    if not _FULL_QUEUE_COMMIT_SHA_RE.fullmatch(commit_sha):
        raise QueueCommitAuthorityError(
            "queue_commit_sha must be a full lowercase 40-hex commit SHA"
        )
    prefix = _validated_queue_repo_relpath("queue tree prefix", tree_prefix)
    output = _queue_git_object_output(
        repo_root,
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            "--name-only",
            commit_sha,
            "--",
            prefix,
        ],
        operation=f"tree enumeration at {commit_sha}:{prefix}",
    )
    paths: list[str] = []
    for raw_path in output.split("\0"):
        if not raw_path:
            continue
        path = _validated_queue_repo_relpath("queue tree path", raw_path)
        if path != prefix and not path.startswith(f"{prefix}/"):
            raise QueueCommitAuthorityError(
                f"exact queue tree returned path outside {prefix}: {path}"
            )
        paths.append(path)
    return paths


def _queue_commit_blob_text(
    repo_root: Path,
    relpath: str,
    *,
    queue_commit_sha: str,
    required: bool,
) -> str | None:
    """Read a blob from one exact commit, distinguishing absence from read failure."""
    commit_sha = str(queue_commit_sha or "").strip()
    if not _FULL_QUEUE_COMMIT_SHA_RE.fullmatch(commit_sha):
        raise QueueCommitAuthorityError(
            "queue_commit_sha must be a full lowercase 40-hex commit SHA"
        )
    path = _validated_queue_repo_relpath("queue blob path", relpath)
    if path not in _queue_commit_tree_paths(
        repo_root,
        queue_commit_sha=commit_sha,
        tree_prefix=path,
    ):
        if required:
            raise QueueCommitAuthorityError(
                f"required queue blob is absent at {commit_sha}:{path}"
            )
        return None
    return _queue_git_object_output(
        repo_root,
        ["git", "show", f"{commit_sha}:{path}"],
        operation=f"blob read at {commit_sha}:{path}",
    )


def _queue_tasks_lines(repo_root: Path, *, queue_commit_sha: str = "") -> list[str]:
    if queue_commit_sha:
        text = _queue_commit_blob_text(
            repo_root,
            "TASKS.md",
            queue_commit_sha=queue_commit_sha,
            required=True,
        )
        assert text is not None
        return text.splitlines()
    try:
        return (repo_root / "TASKS.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _queue_control_plane_packet_text(
    repo_root: Path,
    packet: str,
    *,
    queue_commit_sha: str,
) -> str | None:
    if not queue_commit_sha:
        return None
    safe_packet = _safe_config_tracked_packet(
        repo_root,
        packet,
        queue_commit_sha=queue_commit_sha,
    )
    if not safe_packet:
        if str(packet or "").strip():
            raise QueueCommitAuthorityError(
                f"invalid exact-queue control-plane packet path: {packet!r}"
            )
        return None
    return _queue_commit_blob_text(
        repo_root,
        safe_packet,
        queue_commit_sha=queue_commit_sha,
        required=False,
    )


def _queue_control_plane_packet_status(
    repo_root: Path,
    packet: str,
    *,
    queue_commit_sha: str = "",
) -> str | None:
    if not queue_commit_sha:
        return read_control_plane_packet_status(repo_root, packet)
    packet_text = _queue_control_plane_packet_text(
        repo_root,
        packet,
        queue_commit_sha=queue_commit_sha,
    )
    if packet_text is None:
        return None
    for line in packet_text.splitlines()[:_QUEUE_PACKET_SCAN_LIMIT]:
        clean = line.strip()
        if clean.lower().startswith("status:"):
            return clean.partition(":")[2].strip() or None
    return None


def _queue_control_plane_packet_wave_id(
    repo_root: Path,
    packet: str,
    *,
    queue_commit_sha: str = "",
) -> str | None:
    if not queue_commit_sha:
        return read_control_plane_packet_wave_id(repo_root, packet)
    packet_text = _queue_control_plane_packet_text(
        repo_root,
        packet,
        queue_commit_sha=queue_commit_sha,
    )
    if packet_text is None:
        return None
    for line in packet_text.splitlines()[:_QUEUE_PACKET_SCAN_LIMIT]:
        clean = line.strip()
        lower = clean.lower()
        if lower.startswith("wave id:") or lower.startswith("wave_id:"):
            value = clean.partition(":")[2].strip().strip("`")
            normalized = normalize_wave_id(value) if value else ""
            return normalized if normalized != "wave-unknown" else None
    return None


def _routed_tracker_queue_entries(
    repo_root: Path,
    *,
    existing_wave_ids: set[str],
    queue_commit_sha: str = "",
) -> list[dict[str, Any]]:
    lines = _queue_tasks_lines(repo_root, queue_commit_sha=queue_commit_sha)

    entries: list[dict[str, Any]] = []
    for line in lines:
        if "Tracker sync note" not in line or "Packet:" not in line:
            continue
        wave_id = normalize_wave_id(_tracker_note_wave_id(line))
        if not wave_id or wave_id in existing_wave_ids:
            continue
        packet = _queue_entry_backtick_value(line, "Packet")
        if queue_commit_sha:
            packet = _safe_config_tracked_packet(
                repo_root,
                packet,
                queue_commit_sha=queue_commit_sha,
            )
        if not packet:
            continue
        status = _queue_control_plane_packet_status(
            repo_root,
            packet,
            queue_commit_sha=queue_commit_sha,
        )
        status_upper = str(status or "").upper()
        if not status_upper.startswith("ROUTED - PHASE A"):
            continue
        category_match = re.search(r"Category:\s*([^.`]+)", line)
        category = (
            category_match.group(1).strip()
            if category_match
            else "routed remediation"
        )
        line_upper = line.upper()
        state = str(status or "Routed tracker note")
        entries.append(
            {
                "label": wave_id.upper(),
                "state": state,
                "wave_id": wave_id,
                "category": category,
                "packet": packet,
                "source_packet": "",
                "status": status,
                "hard_stop": "HARD STOP" in line_upper or "HARD STOP" in status_upper,
                "explicit_mu_structural_authorization": (
                    _queue_entry_has_explicit_mu_structural_authorization(
                        category=category,
                        line=line,
                        state=state,
                        status=status,
                        wave_id=wave_id,
                    )
                ),
            }
        )
        existing_wave_ids.add(wave_id)
    return entries


def _program_queue_section_lines(
    repo_root: Path,
    *,
    queue_commit_sha: str = "",
) -> list[str]:
    lines = _queue_tasks_lines(repo_root, queue_commit_sha=queue_commit_sha)

    section: list[str] = []
    in_program_queue = False
    for line in lines:
        if _PROGRAM_QUEUE_HEADER_RE.match(line):
            in_program_queue = True
            continue
        if in_program_queue and line.startswith("## "):
            break
        if in_program_queue:
            section.append(line)
    return section


def _strip_simple_program_queue_state_trailers(text: str) -> str:
    raw = str(text or "").strip()
    previous = None
    while raw and raw != previous:
        previous = raw
        raw = _SIMPLE_QUEUE_STATE_TRAILER_RE.sub("", raw).rstrip()
    return raw.strip()


def _simple_program_queue_state_trailer(text: str) -> str:
    """Return the trailing queue state without including the entry identity."""
    match = _SIMPLE_QUEUE_STATE_TRAILER_RE.search(str(text or "").strip())
    return match.group("state").strip() if match else ""


def _simple_program_queue_explicit_label_wave_id(label: str) -> str:
    stripped_label = _strip_simple_program_queue_state_trailers(label)
    match = _EXPLICIT_BRACKETED_WAVE_LABEL_RE.match(stripped_label)
    if not match:
        return ""
    wave_id = normalize_wave_id(match.group("wave_id"))
    if not _WAVE_ID_DATE_SUFFIX_RE.search(wave_id):
        return ""
    return wave_id


def _simple_program_queue_wave_id(label: str, queue_text: str) -> str:
    explicit_label_wave_id = _simple_program_queue_explicit_label_wave_id(label)
    if explicit_label_wave_id:
        return explicit_label_wave_id
    raw = " ".join(part.strip() for part in (label, queue_text) if part.strip())
    raw = _strip_simple_program_queue_state_trailers(raw)
    return normalize_wave_id(raw)


def _strip_wave_date_suffix(wave_id: str) -> str:
    return _WAVE_ID_DATE_SUFFIX_RE.sub("", normalize_wave_id(wave_id))


def _program_queue_identity_matches(*, candidate: str, derived_wave_id: str) -> bool:
    candidate_norm = normalize_wave_id(candidate)
    derived_norm = normalize_wave_id(derived_wave_id)
    if not candidate_norm or not derived_norm:
        return False
    if candidate_norm == derived_norm:
        return True
    if candidate_norm.startswith(f"{derived_norm}-"):
        return True

    candidate_base = _strip_wave_date_suffix(candidate_norm)
    derived_base = _strip_wave_date_suffix(derived_norm)
    if not candidate_base or not derived_base:
        return False
    if candidate_base == derived_base:
        return True
    if min(len(candidate_base), len(derived_base)) < 12:
        return False
    return candidate_base.startswith(f"{derived_base}-") or derived_base.startswith(
        f"{candidate_base}-"
    )


def _safe_config_tracked_packet(
    repo_root: Path,
    raw_packet: Any,
    *,
    queue_commit_sha: str = "",
) -> str:
    packet = _normalize_repo_relpath(str(raw_packet or ""))
    if not packet:
        return ""
    if _path_field_error("tracked_packet", packet):
        if queue_commit_sha:
            raise QueueCommitAuthorityError(
                _path_field_error("tracked_packet", packet)
                or f"invalid tracked_packet: {packet!r}"
            )
        return ""
    if queue_commit_sha:
        queue_path_error = _queue_repo_relpath_error("tracked_packet", packet)
        if queue_path_error:
            raise QueueCommitAuthorityError(queue_path_error)
    if not packet.startswith("reports/control_plane/") or not packet.endswith(".md"):
        return ""
    if queue_commit_sha:
        return packet
    packet_path = (repo_root / packet).resolve()
    control_plane_dir = (repo_root / "reports" / "control_plane").resolve()
    try:
        packet_path.relative_to(control_plane_dir)
    except ValueError:
        return ""
    return packet


def _wave_config_matches_program_queue_entry(
    repo_root: Path,
    config_path: Path,
    config: dict[str, Any],
    *,
    derived_wave_id: str,
    queue_commit_sha: str = "",
) -> bool:
    packet = _safe_config_tracked_packet(
        repo_root,
        config.get("tracked_packet"),
        queue_commit_sha=queue_commit_sha,
    )
    packet_wave_id = (
        _queue_control_plane_packet_wave_id(
            repo_root,
            packet,
            queue_commit_sha=queue_commit_sha,
        )
        if packet
        else ""
    )
    config_ids = [
        str(config.get("wave_id") or ""),
        config_path.name.removesuffix("_wave_config.json"),
        str(config.get("title") or ""),
        packet_wave_id or "",
    ]
    for raw in config_ids:
        if not raw.strip():
            continue
        if _program_queue_identity_matches(
            candidate=raw,
            derived_wave_id=derived_wave_id,
        ):
            return True
    return False


def _matching_program_queue_wave_config(
    repo_root: Path,
    *,
    derived_wave_id: str,
    queue_commit_sha: str = "",
) -> dict[str, Any]:
    control_plane_dir = repo_root / "reports" / "control_plane"
    if queue_commit_sha:
        config_paths = sorted(
            Path(path)
            for path in _queue_commit_tree_paths(
                repo_root,
                queue_commit_sha=queue_commit_sha,
                tree_prefix="reports/control_plane",
            )
            if path.startswith("reports/control_plane/")
            and "/" not in path.removeprefix("reports/control_plane/")
            and path.endswith("_wave_config.json")
        )
    else:
        if not control_plane_dir.is_dir():
            return {}
        config_paths = sorted(control_plane_dir.glob("*_wave_config.json"))

    exact_matches: list[tuple[str, dict[str, Any]]] = []
    prefix_matches: list[tuple[str, dict[str, Any]]] = []
    for config_path in config_paths:
        try:
            if queue_commit_sha:
                config_text = _queue_commit_blob_text(
                    repo_root,
                    config_path.as_posix(),
                    queue_commit_sha=queue_commit_sha,
                    required=True,
                )
                assert config_text is not None
            else:
                config_text = config_path.read_text(encoding="utf-8")
            config = json.loads(config_text)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(config, dict):
            continue
        raw_config_wave_id = str(config.get("wave_id") or "").strip()
        config_wave_id = (
            normalize_wave_id(raw_config_wave_id) if raw_config_wave_id else ""
        )
        if config_wave_id == derived_wave_id:
            exact_matches.append((config_path.name, config))
            continue
        if _wave_config_matches_program_queue_entry(
            repo_root,
            config_path,
            config,
            derived_wave_id=derived_wave_id,
            queue_commit_sha=queue_commit_sha,
        ):
            prefix_matches.append((config_path.name, config))
    matches = exact_matches or prefix_matches
    return matches[0][1] if matches else {}


def _program_queue_config_request(config: dict[str, Any]) -> str:
    for key in ("request_for_agent", "request_for_claude", "routing_summary", "purpose"):
        value = str(config.get(key) or "").strip()
        if value:
            return value
    return ""


def _program_queue_tracker_notes_for_wave_ids(
    repo_root: Path,
    *,
    wave_ids: set[str],
    queue_commit_sha: str = "",
) -> list[str]:
    if not wave_ids:
        return []
    lines = _queue_tasks_lines(repo_root, queue_commit_sha=queue_commit_sha)

    notes: list[str] = []
    for line in lines:
        if "Tracker sync note" not in line:
            continue
        note_wave_id = normalize_wave_id(_tracker_note_wave_id(line))
        if note_wave_id in wave_ids:
            notes.append(line.strip())
    return notes


def _simple_program_queue_text_has_post_merge_marker(text: Any) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return False
    if _SIMPLE_QUEUE_PRECOMMIT_MARKER_RE.search(clean):
        return False
    return bool(_SIMPLE_QUEUE_TERMINAL_MARKER_RE.search(clean))


def _git_merge_history_contains_wave_id(
    repo_root: Path,
    wave_id: str,
    *,
    queue_commit_sha: str = "",
) -> bool:
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id or normalized_wave_id == "wave-unknown":
        return False
    if queue_commit_sha:
        commit_sha = str(queue_commit_sha or "").strip()
        if not _FULL_QUEUE_COMMIT_SHA_RE.fullmatch(commit_sha):
            raise QueueCommitAuthorityError(
                "queue_commit_sha must be a full lowercase 40-hex commit SHA"
            )
        normalized_log = _queue_git_object_output(
            repo_root,
            [
                "git",
                "log",
                "--merges",
                "--format=%s%n%b",
                "-n",
                "400",
                commit_sha,
                "--",
            ],
            operation=f"merge history at {commit_sha}",
        ).lower()
        return bool(
            re.search(
                rf"(?<![a-z0-9_-]){re.escape(normalized_wave_id)}(?![a-z0-9_-])",
                normalized_log,
            )
        )
    try:
        result = _run(
            ["git", "log", "--merges", "--format=%s%n%b", "-n", "400"],
            cwd=repo_root,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    normalized_log = result.stdout.lower()
    return bool(
        re.search(
            rf"(?<![a-z0-9_-]){re.escape(normalized_wave_id)}(?![a-z0-9_-])",
            normalized_log,
        )
    )


def _program_queue_merge_log_wave_id_is_specific(wave_id: str) -> bool:
    normalized_wave_id = normalize_wave_id(wave_id)
    if not normalized_wave_id or normalized_wave_id == "wave-unknown":
        return False
    if _WAVE_ID_DATE_SUFFIX_RE.search(normalized_wave_id):
        return True
    parts = [part for part in normalized_wave_id.split("-") if part]
    return len(parts) >= 3 and len(normalized_wave_id) >= 16


def _simple_program_queue_merge_log_wave_ids(entry: dict[str, Any]) -> set[str]:
    """Return explicit, specific IDs eligible for merge-history completion proof."""
    derived_wave_id = normalize_wave_id(str(entry.get("derived_wave_id") or ""))
    merge_log_ids = {
        normalize_wave_id(str(raw or ""))
        for raw in (
            entry.get("config_wave_id"),
            entry.get("packet_wave_id"),
        )
        if str(raw or "").strip()
    }

    entry_wave_id = normalize_wave_id(str(entry.get("wave_id") or ""))
    if entry_wave_id and entry_wave_id != derived_wave_id:
        merge_log_ids.add(entry_wave_id)

    explicit_label_wave_id = normalize_wave_id(
        str(entry.get("explicit_label_wave_id") or "")
    )
    if explicit_label_wave_id:
        merge_log_ids.add(explicit_label_wave_id)

    return {
        wave_id
        for wave_id in merge_log_ids
        if _program_queue_merge_log_wave_id_is_specific(wave_id)
    }


def _simple_program_queue_entry_is_completed(
    repo_root: Path,
    entry: dict[str, Any],
    *,
    queue_commit_sha: str = "",
) -> bool:
    wave_ids = {
        normalize_wave_id(str(raw or ""))
        for raw in (
            entry.get("wave_id"),
            entry.get("derived_wave_id"),
            entry.get("config_wave_id"),
            entry.get("packet_wave_id"),
        )
        if str(raw or "").strip()
    }
    completion_texts: list[Any] = [
        entry.get("state"),
        entry.get("status"),
    ]
    completion_texts.extend(
        _program_queue_tracker_notes_for_wave_ids(
            repo_root,
            wave_ids=wave_ids,
            queue_commit_sha=queue_commit_sha,
        )
    )
    if any(
        _simple_program_queue_text_has_post_merge_marker(text)
        for text in completion_texts
    ):
        return True
    return any(
        _git_merge_history_contains_wave_id(
            repo_root,
            wave_id,
            queue_commit_sha=queue_commit_sha,
        )
        for wave_id in _simple_program_queue_merge_log_wave_ids(entry)
    )


def _simple_program_queue_entries(
    repo_root: Path,
    *,
    existing_wave_ids: set[str],
    queue_commit_sha: str = "",
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line in _program_queue_section_lines(
        repo_root,
        queue_commit_sha=queue_commit_sha,
    ):
        numbered_match = _PROGRAM_QUEUE_NUMBERED_ENTRY_RE.match(line)
        baton_match = _PROGRAM_QUEUE_UNNUMBERED_BATON_RE.match(line)
        if numbered_match:
            label = numbered_match.group("label").strip()
            tail = numbered_match.group("tail").strip()
        elif baton_match:
            label = baton_match.group("label").strip()
            tail = ""
        else:
            continue
        if "Wave ID:" in line or "Packet:" in line:
            continue
        queue_text = " ".join(part for part in (label, tail) if part).strip()
        if not queue_text:
            continue
        state = queue_text
        if baton_match:
            state = _simple_program_queue_state_trailer(label) or queue_text
        explicit_label_wave_id = _simple_program_queue_explicit_label_wave_id(label)
        wave_id = _simple_program_queue_wave_id(label, tail)
        if wave_id in existing_wave_ids:
            continue
        config = _matching_program_queue_wave_config(
            repo_root,
            derived_wave_id=wave_id,
            queue_commit_sha=queue_commit_sha,
        )
        raw_config_wave_id = str(config.get("wave_id") or "").strip()
        config_wave_id = (
            normalize_wave_id(raw_config_wave_id) if raw_config_wave_id else ""
        )
        if config_wave_id:
            wave_id = config_wave_id
        packet = _safe_config_tracked_packet(
            repo_root,
            config.get("tracked_packet"),
            queue_commit_sha=queue_commit_sha,
        )
        packet_wave_id = (
            _queue_control_plane_packet_wave_id(
                repo_root,
                packet,
                queue_commit_sha=queue_commit_sha,
            )
            if packet
            else None
        )
        entries.append(
            {
                "label": label,
                "state": state,
                "wave_id": wave_id,
                "derived_wave_id": _simple_program_queue_wave_id(label, tail),
                "explicit_label_wave_id": explicit_label_wave_id,
                "config_wave_id": config_wave_id,
                "packet_wave_id": packet_wave_id,
                "category": "PROGRAM QUEUE",
                "packet": packet,
                "source_packet": "",
                "status": _queue_control_plane_packet_status(
                    repo_root,
                    packet,
                    queue_commit_sha=queue_commit_sha,
                )
                if packet
                else None,
                "hard_stop": False,
                "explicit_mu_structural_authorization": True,
                "simple_program_queue": True,
                "queue_text": queue_text,
                "config_request": _program_queue_config_request(config),
            }
        )
        existing_wave_ids.add(wave_id)
    return entries


def _founder_ordered_queue_entries(
    repo_root: Path,
    *,
    queue_commit_sha: str = "",
) -> list[dict[str, Any]]:
    lines = _queue_tasks_lines(repo_root, queue_commit_sha=queue_commit_sha)

    entries: list[dict[str, Any]] = []
    seen_wave_ids: set[str] = set()
    for line in lines:
        if not _line_is_next_codex_post_redteam_queue_entry(line):
            continue
        if "Wave ID:" not in line or "Packet:" not in line:
            continue
        label_match = re.match(
            r"^\s*\d+\.\s+\*\*\[(?P<label>[^\]]+)\]\s*(?P<state>.*?)\*\*",
            line,
        )
        if not label_match:
            continue
        wave_id = _queue_entry_backtick_value(line, "Wave ID")
        packet = _queue_entry_backtick_value(line, "Packet")
        if not wave_id or not packet:
            continue
        normalized_wave_id = normalize_wave_id(wave_id)
        category_match = re.search(r"Category:\s*([^.`]+)", line)
        category = (
            category_match.group(1).strip()
            if category_match
            else "founder-ordered redteam"
        )
        source_packet = _queue_entry_backtick_value(line, "Source audit packet")
        if queue_commit_sha and source_packet:
            _validated_queue_repo_relpath("source_packet", source_packet)
        status = _queue_control_plane_packet_status(
            repo_root,
            packet,
            queue_commit_sha=queue_commit_sha,
        )
        state = label_match.group("state").strip()
        line_upper = line.upper()
        status_upper = str(status or "").upper()
        seen_wave_ids.add(normalized_wave_id)
        entries.append(
            {
                "label": label_match.group("label").strip(),
                "state": state,
                "wave_id": normalized_wave_id,
                "category": category,
                "packet": packet,
                "source_packet": source_packet,
                "status": status,
                "hard_stop": "HARD STOP" in line_upper or "HARD STOP" in status_upper,
                "explicit_mu_structural_authorization": (
                    _queue_entry_has_explicit_mu_structural_authorization(
                        category=category,
                        line=line,
                        state=state,
                        status=status,
                        wave_id=normalized_wave_id,
                    )
                ),
            }
        )
    entries.extend(
        _routed_tracker_queue_entries(
            repo_root,
            existing_wave_ids=seen_wave_ids,
            queue_commit_sha=queue_commit_sha,
        )
    )
    entries.extend(
        _simple_program_queue_entries(
            repo_root,
            existing_wave_ids=seen_wave_ids,
            queue_commit_sha=queue_commit_sha,
        )
    )
    return entries


def _next_open_founder_ordered_queue_entry(
    repo_root: Path,
    *,
    queue_commit_sha: str = "",
) -> dict[str, Any] | None:
    open_entries: list[dict[str, Any]] = []
    for entry in _founder_ordered_queue_entries(
        repo_root,
        queue_commit_sha=queue_commit_sha,
    ):
        if entry.get("simple_program_queue"):
            if _simple_program_queue_entry_is_completed(
                repo_root,
                entry,
                queue_commit_sha=queue_commit_sha,
            ):
                continue
            open_entries.append(entry)
            continue
        if packet_status_is_completed(entry.get("status")):
            continue
        if packet_status_is_completed(entry.get("state")):
            continue
        open_entries.append(entry)
    for entry in open_entries:
        if not entry.get("hard_stop"):
            return entry
    return open_entries[0] if open_entries else None


def _post_merge_blocker_report_paths(
    repo_root: Path,
    *,
    queue_commit_sha: str = "",
) -> list[str]:
    if queue_commit_sha:
        prefix = "reports/deferred/blocking/"
        return sorted(
            path
            for path in _queue_commit_tree_paths(
                repo_root,
                queue_commit_sha=queue_commit_sha,
                tree_prefix="reports/deferred/blocking",
            )
            if path.startswith(prefix)
            and "/" not in path.removeprefix(prefix)
            and path.endswith(".md")
            and path != f"{prefix}README.md"
        )
    blocking_dir = repo_root / "reports" / "deferred" / "blocking"
    if not blocking_dir.is_dir():
        return []
    return sorted(
        p.relative_to(repo_root).as_posix()
        for p in blocking_dir.glob("*.md")
        if p.name != "README.md"
    )


def _post_merge_request_for_queue_entry(entry: dict[str, Any]) -> str:
    packet = str(entry.get("packet") or "")
    source_packet = str(entry.get("source_packet") or "")
    category = str(entry.get("category") or "founder-ordered redteam")
    if entry.get("simple_program_queue"):
        queue_text = str(entry.get("queue_text") or entry.get("label") or "").strip()
        config_request = str(entry.get("config_request") or "").strip()
        packet_clause = f" Read {packet}." if packet else ""
        request_source = f" {config_request}" if config_request else ""
        return (
            f"Use mu/tools/executors/launch_wave.py for the active PROGRAM QUEUE "
            f"item '{queue_text}', then continue only through executor_dispatch.py, "
            "Phase A, Phase B, and commit_executor.py."
            f"{packet_clause}{request_source} "
            "If no launcher config or tracked packet exists yet, prepare that "
            "bounded queue item through launch_wave.py instead of reporting the "
            "post-merge queue empty. Do not implement the structural item directly "
            "from this post-merge package."
        )
    is_authorized_mu_structural = (
        _queue_entry_category_is_mu_structural(category)
        and bool(entry.get("explicit_mu_structural_authorization"))
    )
    read_targets = [packet]
    if source_packet:
        read_targets.append(source_packet)
    target_text = " and ".join(read_targets)
    if entry.get("hard_stop"):
        return (
            "Hard stop before implementation. The next open founder-ordered "
            f"candidate is {packet}; report that /mu structural work is queued "
            "and do not dispatch Phase A, Phase B, or commit implementation."
        )
    stop_clause = (
        "Stop if the packet requires work outside its bounded scope or founder input."
        if is_authorized_mu_structural
        else "Stop if the packet requires /mu structural work or founder input."
    )
    return (
        f"Use the full dispatcher pipeline for this {category} remediation wave: "
        "post-merge supervisor -> Phase A -> Phase B -> commit executor. "
        f"Read {target_text}. Do not edit Claude-related files. {stop_clause}"
    )


def _post_merge_summary_for_queue_entry(entry: dict[str, Any]) -> str:
    if entry.get("simple_program_queue"):
        queue_text = str(entry.get("queue_text") or entry.get("label") or "").strip()
        if entry.get("packet"):
            return f"Launch the active PROGRAM QUEUE item: {queue_text}."
        return (
            "Prepare or launch the active PROGRAM QUEUE item through "
            f"launch_wave.py: {queue_text}."
        )
    return f"Implement the queued {entry['category']} remediation packet only."


def _post_merge_tracker_summary_for_queue_entry(entry: dict[str, Any]) -> str:
    if not entry.get("simple_program_queue"):
        return (
            f"Next open queue packet is a hard stop: {entry['packet']}."
            if entry.get("hard_stop")
            else f"Next open queue packet: {entry['packet']}."
        )
    queue_text = str(entry.get("queue_text") or entry.get("label") or "").strip()
    if entry.get("packet"):
        return (
            f"Next open PROGRAM QUEUE item: {queue_text}; tracked packet: "
            f"{entry['packet']}."
        )
    return (
        f"Next open PROGRAM QUEUE item: {queue_text}. No matching launcher config "
        "or tracked packet exists yet."
    )


def _refresh_post_merge_package_for_next_open_queue(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    result: dict[str, Any],
    merge_sha: str,
    log: Any,
    queue_commit_sha: str = "",
) -> dict[str, Any]:
    """Write a fresh package, optionally sourcing queue truth from one commit."""
    exact_queue_commit = _validate_queue_commit_sha(repo_root, queue_commit_sha)
    if exact_queue_commit:
        recorded_merge_sha = str(merge_sha or "").strip()
        if recorded_merge_sha != exact_queue_commit:
            raise QueueCommitAuthorityError(
                "merge_sha must equal queue_commit_sha for exact queue authority: "
                f"{recorded_merge_sha or '<empty>'} != {exact_queue_commit}"
            )
        merge_sha = exact_queue_commit
    entry = _next_open_founder_ordered_queue_entry(
        repo_root,
        queue_commit_sha=exact_queue_commit,
    )
    queue_task_id = "[NEXT-CODEX-POST-REDTEAM]"
    pr_number_raw = result.get("pr_number")
    try:
        merged_pr = int(pr_number_raw)
    except (TypeError, ValueError):
        merged_pr = 0

    package_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "meta",
        "post_merge_package.json",
    )

    if entry is None:
        package = {
            "task_id": queue_task_id,
            "merged_pr": merged_pr,
            "merge_sha": merge_sha,
            "wave_name": "founder-ordered-post-merge-queue-empty",
            "lane": "founder-ordered remediation queue complete",
            "rollout_packet_path": "reports/control_plane/post_redteam_structural_queue_2026-03-20.md",
            "deferred_items": [],
            "tracker_state_summary": (
                "Post-merge package refreshed mechanically after commit merge. "
                "No open founder-ordered queue packets remain."
            ),
            "next_candidates": [],
            "blocker_report_paths": _post_merge_blocker_report_paths(
                repo_root,
                queue_commit_sha=exact_queue_commit,
            ),
        }
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
        result["post_merge_package_path"] = str(package_path.relative_to(repo_root))
        result["post_merge_next_wave"] = None
        result["post_merge_next_hard_stop"] = False
        result["post_merge_queue_empty"] = True
        log(
            "Step 15b: refreshed post-merge package with no open "
            "founder-ordered queue entry"
        )
        return package

    deferred_items = [
        p
        for p in (entry.get("source_packet"), entry.get("packet"))
        if isinstance(p, str) and p.strip()
    ]
    next_candidates: list[dict[str, Any]] = []
    if not entry.get("hard_stop"):
        entry_packet = entry.get("packet")
        tracked_packet = (
            entry_packet
            if isinstance(entry_packet, str) and entry_packet.strip()
            else None
        )
        next_candidates.append(
            {
                "candidate": entry["wave_id"],
                "bounded": True,
                "tracked_packet": tracked_packet,
                "summary": _post_merge_summary_for_queue_entry(entry),
                "request_for_claude": _post_merge_request_for_queue_entry(entry),
            }
        )

    package = {
        "task_id": queue_task_id,
        "merged_pr": merged_pr,
        "merge_sha": merge_sha,
        "wave_name": entry["wave_id"],
        "lane": f"{entry['category']} remediation",
        "rollout_packet_path": "reports/control_plane/post_redteam_structural_queue_2026-03-20.md",
        "deferred_items": deferred_items,
        "tracker_state_summary": (
            "Post-merge package refreshed mechanically after commit merge. "
            + _post_merge_tracker_summary_for_queue_entry(entry)
        ),
        "next_candidates": next_candidates,
        "blocker_report_paths": _post_merge_blocker_report_paths(
            repo_root,
            queue_commit_sha=exact_queue_commit,
        ),
    }
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    result["post_merge_package_path"] = str(package_path.relative_to(repo_root))
    result["post_merge_next_wave"] = entry["wave_id"]
    result["post_merge_next_hard_stop"] = bool(entry.get("hard_stop"))
    result["post_merge_queue_empty"] = False
    log(
        "Step 15b: refreshed post-merge package for "
        f"{entry['wave_id']}"
        + (" (hard stop)" if entry.get("hard_stop") else "")
    )
    return package


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
    late_conflict_retry_used = bool(result.pop("_late_conflict_retry_used", False))

    # ── Step 11: run_pre_push_script ──────────────────────────────────
    if "run_pre_push_script" not in result["steps_completed"]:
        pre_push_script = repo_root / "mu" / "tools" / "hooks" / "pre-push-fast"
        existing_isolation = result.get("pre_push_isolation")
        isolation: dict[str, Any] | None = (
            dict(existing_isolation) if isinstance(existing_isolation, dict) else None
        )
        isolation_error: str | None = None
        if pre_push_script.exists():
            if isolation:
                if isolation.get("pre_push_state") == PRE_PUSH_ISOLATION_STASH_PENDING_VALUE:
                    log(
                        "Step 11: resuming pending pre-push dirty isolation "
                        f"{isolation.get('marker')}"
                    )
                    isolation, isolation_error = _stash_post_commit_pre_push_dirty_paths(
                        repo_root,
                        wave_id=str(handoff.get("wave_id") or ""),
                        log=log,
                        isolation=isolation,
                    )
                    if isolation_error:
                        return {"status": "error", "step": "pre_push_dirty_isolation",
                                "errors": [isolation_error],
                                "steps_completed": result["steps_completed"]}
                    if isolation:
                        result["pre_push_isolation"] = isolation
                        result.pop("pre_push_restored_paths", None)
                        _checkpoint_post_commit_progress(
                            result,
                            continuation_path=continuation_path,
                            target_branch=target_branch,
                        )
                    resume_action = "run_pre_push"
                else:
                    resume_action, isolation_error = _classify_pre_push_isolation_resume(
                        repo_root,
                        isolation,
                    )
                    if isolation_error:
                        return {"status": "error", "step": "pre_push_dirty_isolation",
                                "errors": [isolation_error],
                                "steps_completed": result["steps_completed"]}
                    log(
                        "Step 11: resuming with durable pre-push dirty isolation "
                        f"{isolation.get('stash_ref') or isolation.get('marker')}"
                    )
                    if resume_action == "already_restored":
                        restored_paths = sorted(_pre_push_isolation_paths(isolation))
                        result.pop("pre_push_isolation", None)
                        if restored_paths:
                            result["pre_push_restored_paths"] = restored_paths
                        result["steps_completed"].append("run_pre_push_script")
                        _checkpoint_post_commit_progress(
                            result,
                            continuation_path=continuation_path,
                            target_branch=target_branch,
                        )
                        log(
                            "Step 11: pre-push already passed before dirty isolation "
                            "restore checkpoint; checkpoint refreshed"
                        )
                        log("Step 11: pre-push script passed")
                        resume_action = "complete"
            else:
                resume_action = "run_pre_push"
                isolation = _prepare_post_commit_pre_push_dirty_isolation(
                    repo_root,
                    wave_id=str(handoff.get("wave_id") or ""),
                )
                if isolation:
                    result["pre_push_isolation"] = isolation
                    result.pop("pre_push_restored_paths", None)
                    _checkpoint_post_commit_progress(
                        result,
                        continuation_path=continuation_path,
                        target_branch=target_branch,
                    )
                    isolation, isolation_error = _stash_post_commit_pre_push_dirty_paths(
                        repo_root,
                        wave_id=str(handoff.get("wave_id") or ""),
                        log=log,
                        isolation=isolation,
                    )
                    if isolation_error:
                        return {"status": "error", "step": "pre_push_dirty_isolation",
                                "errors": [isolation_error],
                                "steps_completed": result["steps_completed"]}
                    if isolation:
                        result["pre_push_isolation"] = isolation
                        _checkpoint_post_commit_progress(
                            result,
                            continuation_path=continuation_path,
                            target_branch=target_branch,
                        )
            if "run_pre_push_script" not in result["steps_completed"]:
                pre_push_error: dict[str, Any] | None = None
                if resume_action == "restore_only":
                    log(
                        "Step 11: pre-push already passed before prior restore "
                        "attempt; restoring isolated dirty work"
                    )
                else:
                    try:
                        # Validation child: strip the live pipeline lane bus and
                        # every invocation-owned role/pager override so the
                        # repository's own tests resolve their temporary .agent_bus
                        # and default routing instead of the live pipeline lane.
                        _run(
                            ["bash", str(pre_push_script)],
                            cwd=repo_root,
                            timeout=PRE_PUSH_FAST_TIMEOUT_S,
                            env=_commit_validation_env(),
                        )
                    except subprocess.CalledProcessError as exc:
                        detail = _tail_failure_excerpt(
                            exc.stderr or exc.stdout or "",
                            limit=4000,
                            max_lines=80,
                        )
                        if not detail:
                            detail = f"exit {exc.returncode}"
                        pre_push_error = {"status": "error", "step": "run_pre_push_script",
                                          "errors": [f"pre-push-fast failed: {detail}"],
                                          "steps_completed": result["steps_completed"]}
                    except subprocess.TimeoutExpired:
                        pre_push_error = {"status": "error", "step": "run_pre_push_script",
                                          "errors": ["pre-push-fast timed out"],
                                          "steps_completed": result["steps_completed"]}
                    if pre_push_error is None and isolation:
                        _mark_pre_push_isolation_verified(isolation)
                        result["pre_push_isolation"] = isolation
                        _checkpoint_post_commit_progress(
                            result,
                            continuation_path=continuation_path,
                            target_branch=target_branch,
                        )
                restore_error = _restore_post_commit_pre_push_dirty_paths(
                    repo_root,
                    isolation,
                    log=log,
                )
                if restore_error:
                    errors = [restore_error]
                    if pre_push_error:
                        errors.extend(pre_push_error.get("errors", []))
                    return {"status": "error", "step": "restore_pre_push_dirty_isolation",
                            "errors": errors,
                            "steps_completed": result["steps_completed"]}
                if isolation:
                    restored_paths = sorted(_pre_push_isolation_paths(isolation))
                    result.pop("pre_push_isolation", None)
                    if restored_paths:
                        result["pre_push_restored_paths"] = restored_paths
                    _checkpoint_post_commit_progress(
                        result,
                        continuation_path=continuation_path,
                        target_branch=target_branch,
                    )
                if pre_push_error:
                    return pre_push_error
        if "run_pre_push_script" not in result["steps_completed"]:
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
        # Auto-resolve CONFLICTING/DIRTY PRs before polling CI (2026-04-17
        # learning mechanized). On clean merge: fetch base + merge + push.
        # On TASKS.md-only tracker-note conflict: fetch + merge + resolve
        # chronologically + commit (RCX_SKIP_RECEIPT_CHECK=1) + push. Any
        # other conflict OR non-tracker-note TASKS.md conflict aborts the
        # merge and returns a structured fail-fast error pointing to the
        # manual recovery recipe.
        resolve_result = _try_auto_resolve_pr_conflict(
            repo_root,
            pr_number=pr_number,
            base_branch=base_branch,
            branch_name=target_branch,
            wave_id=str(handoff.get("wave_id") or ""),
            log=log,
        )
        if not resolve_result.get("resolved"):
            return _pr_conflicting_fail_closed_response(
                pr_number=pr_number,
                base_branch=base_branch,
                target_branch=target_branch,
                steps_completed=result["steps_completed"],
                action=resolve_result.get("action", "aborted"),
                detail=resolve_result.get("detail", "unknown"),
            )
        ci_response = _wait_for_pr_ci(
            repo_root,
            pr_number=pr_number,
            result=result,
            continuation_path=continuation_path,
            target_branch=target_branch,
            log=log,
            step_label="Step 14",
            midpoll_autoresolve={
                "base_branch": base_branch,
                "branch_name": target_branch,
                "wave_id": str(handoff.get("wave_id") or ""),
            },
        )
        if ci_response is not None:
            return ci_response
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

    review_wait_timed_out: TimeoutError | None = None
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
    except TimeoutError as exc:
        # Bot review timed out. Refresh PR state before merge evaluation so
        # human reviews/threads that appeared during the wait window cannot be
        # missed by stale pre-wait data.
        review_wait_timed_out = exc
        log(f"Step 15: bot review timed out ({exc}), refreshing PR state before merge")
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Review query failed: {exc}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    if review_wait_timed_out is not None:
        try:
            pr_data = _query_pr_review_state(
                repo_root,
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
            )
            _assert_expected_pr_head(pr_data, head_sha_before_merge)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Review refresh after timeout failed: {exc}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}

    findings_result = _extract_review_findings(
        pr_data, head_sha_before_merge, result=result, pr_number=pr_number,
    )
    if findings_result["outcome"] == "error":
        return findings_result["response"]

    # Inject sweep findings from prior merged PRs (merge_pr.sh --sweep writes
    # .agent_bus/meta/sweep_findings.json with unresolved bot finding content).
    sweep_file = agent_bus_path(repo_root, _active_bus_dir(), "meta", "sweep_findings.json")
    if sweep_file.exists():
        try:
            sweep_lines = [ln.strip() for ln in sweep_file.read_text().splitlines() if ln.strip()]
            sweep_findings = [json.loads(ln) for ln in sweep_lines]
            if sweep_findings:
                existing = findings_result.get("bot_findings", [])
                for sf in sweep_findings:
                    existing.append({
                        "author": "chatgpt-codex-connector[bot]",
                        "path": sf.get("path", ""),
                        "body": sf.get("body", "")[:500],
                        "source": f"sweep-pr-{sf.get('pr', '?')}",
                    })
                findings_result["bot_findings"] = existing
                if findings_result["outcome"] != "bot_findings":
                    findings_result["outcome"] = "bot_findings"
                log(f"Step 15: injected {len(sweep_findings)} sweep finding(s) from prior PRs")
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            log(f"Step 15: failed to load sweep findings (non-fatal): {exc}")

    if findings_result["outcome"] == "bot_findings" and review_wait_timed_out is None:
        # Only remediate bot findings if the bot actually reviewed the
        # current HEAD.  On timeout, stale threads from previous commits
        # are advisory — they get deferred, not remediated.
        remediation_response = _attempt_bot_finding_remediation(
            findings_result["bot_findings"],
            repo_root=repo_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
            target_branch=target_branch,
            base_branch=base_branch,
            head_sha=head_sha_before_merge,
            wave_id=handoff["wave_id"],
            continuation_path=continuation_path,
            result=result,
            log=log,
        )
        if remediation_response is not None:
            return remediation_response
        try:
            head_sha_before_merge, pr_data = _refresh_pr_head_after_executor_update(
                repo_root,
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
                previous_head_sha=head_sha_before_merge,
                target_branch=target_branch,
                log=log,
            )
            result["commit_sha"] = head_sha_before_merge
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "failure_class": "post_remediation_head_refresh_failed",
                    "errors": [f"Post-remediation PR head refresh failed: {exc}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}

    pre_merge_ci_response = _wait_for_pr_ci(
        repo_root,
        pr_number=pr_number,
        result=result,
        continuation_path=continuation_path,
        target_branch=target_branch,
        log=log,
        step_label="Step 15 pre-merge",
    )
    if pre_merge_ci_response is not None:
        return pre_merge_ci_response

    draft_ready_response = _ensure_current_draft_pr_ready_for_review(
        repo_root,
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number,
        head_sha=head_sha_before_merge,
        target_branch=target_branch,
        result=result,
        log=log,
    )
    if draft_ready_response is not None:
        return draft_ready_response

    merge_script = repo_root / "mu" / "tools" / "hooks" / "merge_pr.sh"
    if not merge_script.exists():
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["merge_pr.sh not found"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        _run(
            ["bash", str(merge_script), pr_number, "--sweep"],
            cwd=repo_root.parent, timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        if not late_conflict_retry_used:
            resolve_result = _try_auto_resolve_pr_conflict(
                repo_root,
                pr_number=pr_number,
                base_branch=base_branch,
                branch_name=target_branch,
                wave_id=str(handoff.get("wave_id") or ""),
                log=log,
            )
            if resolve_result.get("resolved") and resolve_result.get("action") != "no_action":
                result["_late_conflict_retry_used"] = True
                try:
                    _prepare_result_for_late_conflict_retry(
                        repo_root,
                        result=result,
                        continuation_path=continuation_path,
                        target_branch=target_branch,
                    )
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as retry_exc:
                    return {
                        "status": "error",
                        "step": "ensure_review_clear_and_merge",
                        "errors": [f"Late auto-resolve refresh failed: {retry_exc}"],
                        "steps_completed": result["steps_completed"],
                        "pr_number": pr_number,
                    }
                ci_response = _wait_for_pr_ci(
                    repo_root,
                    pr_number=pr_number,
                    result=result,
                    continuation_path=continuation_path,
                    target_branch=target_branch,
                    log=log,
                    step_label="Step 15 late auto-resolve",
                )
                if ci_response is not None:
                    return ci_response
                return _run_post_commit_pipeline(
                    handoff=handoff,
                    repo_root=repo_root,
                    result=result,
                    target_branch=target_branch,
                    base_branch=base_branch,
                    continuation_path=continuation_path,
                    log=log,
                )
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"merge_pr.sh failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    queue_commit_sha = ""
    try:
        verify_root = _resolve_post_merge_verify_root(repo_root, base_branch, log=log)
        _run(["git", "fetch", "origin", base_branch], cwd=verify_root, timeout=60)
        pre_verify_status = _run(["git", "status", "--short"], cwd=verify_root).stdout.strip()
        pre_verify_dirty = _dirty_worktree_paths(verify_root) if pre_verify_status else set()
        if pre_verify_dirty:
            head_sha = _run(
                ["git", "rev-parse", f"origin/{base_branch}"], cwd=verify_root
            ).stdout.strip()
            status_output = pre_verify_status or "\n".join(sorted(pre_verify_dirty))
            result["merge_sha"] = head_sha
            queue_commit_sha = head_sha
            if "ensure_review_clear_and_merge" not in result["steps_completed"]:
                result["steps_completed"].append("ensure_review_clear_and_merge")
            _clear_continuation_record(continuation_path)
            log(
                f"Step 15: WARN post-merge verify root {verify_root} was already dirty "
                f"before ff-only sync; using origin/{base_branch}={head_sha[:8]} as "
                f"merged tip and continuing to step 16:\n{status_output}"
            )
            result["post_merge_verify_warning"] = status_output
            log(f"Step 15: merged, HEAD={head_sha[:8]} (pre-verify dirty, continuing to step 16)")
        else:
            _run(["git", "merge", "--ff-only", f"origin/{base_branch}"], cwd=verify_root, timeout=60)
            head_sha = _run(["git", "rev-parse", "HEAD"], cwd=verify_root).stdout.strip()
            status_output = _run(["git", "status", "--short"], cwd=verify_root).stdout.strip()
            result["merge_sha"] = head_sha
            if "ensure_review_clear_and_merge" not in result["steps_completed"]:
                result["steps_completed"].append("ensure_review_clear_and_merge")
            _clear_continuation_record(continuation_path)
            if status_output:
                # Soft-warn on dirty verify instead of fail-closing the pipeline.
                # Step 16 cleanup is wave-scoped (worktree + branch + wave-named
                # stash) and does NOT depend on main-repo dirty state. Fail-closing
                # here previously blocked step 16 cleanup in parallel multi-wave
                # sessions when the main repo held transient dirt from an in-flight
                # sibling wave (observed 2026-04-17 PR #784 Wave B: step 16
                # prevented from running because PR #783 Wave A shadow files were
                # uncommitted in main repo). Closes
                # reports/deferred/blocking/commit_executor_step16_cascade_block_2026-04-17.md
                # (candidate #2: skip-cleanup-on-verify-fail — preserve signal via
                # warning, don't block wave-scoped cleanup).
                log(
                    f"Step 15: WARN post-merge verify found dirty tree at "
                    f"{verify_root} (not wave-owned; cleanup will still proceed):\n"
                    f"{status_output}"
                )
                result["post_merge_verify_warning"] = status_output
                log(f"Step 15: merged, HEAD={head_sha[:8]} (verify dirty, continuing to step 16)")
            else:
                log(f"Step 15: merged, HEAD={head_sha[:8]}, clean tree verified at {verify_root}")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Post-merge verify failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    # ── Step 15b: sync the founder's PRIMARY working copy to base ──────
    # The verify-root ff above only advances a worktree ALREADY on base_branch.
    # The founder's primary checkout normally rests on a FEATURE branch, so it
    # is never that target and drifts behind base_branch as waves merge. This
    # PULL-ONLY, fully fail-open helper brings origin/{base_branch} DOWN into the
    # primary's current feature branch (fetch + ff-only; never push, checkout
    # base, force, or reset). It runs BEFORE step 16 cleanup (which may remove
    # repo_root) and its failure must never affect the already-merged PR.
    result["primary_worktree_sync"] = _sync_primary_worktree_to_base(
        repo_root, base_branch, log=log,
    )

    queue_authority_error: str | None = None
    if queue_commit_sha:
        try:
            _refresh_post_merge_package_for_next_open_queue(
                repo_root=verify_root,
                handoff=handoff,
                result=result,
                merge_sha=str(result.get("merge_sha") or ""),
                log=log,
                queue_commit_sha=queue_commit_sha,
            )
        except QueueCommitAuthorityError as exc:
            queue_authority_error = str(exc)
            log(
                "Step 15b: exact post-merge queue refresh failed closed; "
                f"continuing to step 16 cleanup: {queue_authority_error}"
            )
    else:
        _refresh_post_merge_package_for_next_open_queue(
            repo_root=verify_root,
            handoff=handoff,
            result=result,
            merge_sha=str(result.get("merge_sha") or ""),
            log=log,
        )

    # ── Step 16: post_merge_cleanup ────────────────────────────────────
    # Best-effort cleanup of wave-local state that would otherwise
    # accumulate: local branch ref, linked worktree, wave-scoped stashes.
    # Failures are logged and swallowed — the merge already succeeded and
    # this step MUST NOT regress the pipeline.
    cleanup_outcome = _post_merge_cleanup(
        cleanup_root=verify_root,
        repo_root=repo_root,
        target_branch=target_branch,
        base_branch=base_branch,
        wave_id=str(handoff.get("wave_id") or ""),
        log=log,
    )
    result["post_merge_cleanup"] = cleanup_outcome
    result["steps_completed"].append("post_merge_cleanup")

    if queue_authority_error is not None:
        result["status"] = "error"
        result["step"] = "refresh_post_merge_package"
        result["errors"] = [
            "Exact post-merge queue refresh failed at "
            f"{queue_commit_sha}: {queue_authority_error}"
        ]

    return result


def _stranded_landing_authority(
    repo_root: Path,
    *,
    pr_number: str,
    head_ref: str,
    log: Any = None,
) -> dict[str, Any]:
    """Prove the target PR head went through the CANONICAL receipt chain.

    The stranded-PR landing op brings a PR current (a commit + push via the
    shared helper) and merges it, identifying the PR ONLY by number. Without a
    gate, that is a PR-number-only push/merge route OUTSIDE the receipt chain:
    any PR number — including a clean PR never produced by this executor — could
    drive a commit/push/merge. This gate closes that bypass (the bridge-flagged
    re-entry finding).

    Authority == an ACTIVE post-commit continuation record — the receipt-chain
    artifact the executor itself trusts to resume a held/stranded commit. Such a
    record is written ONLY after Step-6 supervisor receipt validation returned
    ``COMMIT_GO`` / ``COMMIT_GO_HOLD_PUSH`` and Step-9 committed (see the
    :func:`_write_continuation_record` call sites), and is CLEARED on a
    successful merge (:func:`_clear_continuation_record`). A record authorizes
    THIS landing IFF its recorded ``target_branch`` == the resolved PR head
    branch AND its ``pr_number`` == the PR being landed AND it carries a GO
    receipt + a ``git_commit`` step + a non-empty ``commit_sha``.

    This yields exactly the bridge's two fail-closed requirements:
      * A PR number ALONE cannot push/commit/merge — with no matching ACTIVE
        record the caller invokes neither the shared helper nor the merge phase.
      * A CLEAN, non-stranded PR is not landed by this path — a PR never
        committed through this executor has no record, and one already merged had
        its record cleared; either way there is no ACTIVE record ⇒ fail closed.

    Matches on the record's CONTENT (``target_branch`` + ``pr_number``), not its
    filename, so it is robust to the wave_id-vs-branch_prefix keying
    (``target_branch == f"{branch_prefix}/{wave_id}"`` while the file is keyed by
    bare ``wave_id``). Returns
    ``{authorized: bool, detail: str, record: dict|None, path: Path|None}``; the
    matched ``path`` is threaded back as the merge phase's ``continuation_path``
    so a successful land CLEARS the SAME record that authorized it (a re-land of
    the now-merged PR then fails closed).
    """
    try:
        executors_dir = agent_bus_path(repo_root, _active_bus_dir(), "executors")
        record_paths = sorted(executors_dir.glob("commit_executor_*.json"))
    except (OSError, ExecutorCommonError):
        record_paths = []
    for path in record_paths:
        payload = _read_continuation_record(path)
        if payload is None:
            continue
        if payload.get("version") != COMMIT_CONTINUATION_VERSION:
            continue
        # ACTIVE only — a merged PR had its record cleared (deleted), so a
        # non-ACTIVE / absent record proves the PR is NOT a stranded in-chain PR.
        if payload.get("status") != CONTINUATION_ACTIVE_STATUS:
            continue
        # GO receipt only — the commit must have passed Step-6 supervisor receipt
        # validation (the record is never written for a non-GO decision).
        if payload.get("receipt_decision") not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            continue
        if str(payload.get("target_branch") or "") != head_ref:
            continue
        if str(payload.get("pr_number") or "") != str(pr_number):
            continue
        steps = payload.get("steps_completed")
        if not isinstance(steps, list) or "git_commit" not in steps:
            continue
        commit_sha = str(payload.get("commit_sha") or "").strip()
        if not commit_sha:
            continue
        if log is not None:
            log(
                f"land-stranded: receipt-chain authority for PR #{pr_number} on "
                f"{head_ref} (receipt {payload.get('receipt_decision')}, commit "
                f"{commit_sha[:8]}, {path.name})"
            )
        return {
            "authorized": True,
            "detail": (
                f"active receipt chain proves PR #{pr_number} on {head_ref} was "
                f"committed through supervisor validation "
                f"({payload.get('receipt_decision')})"
            ),
            "record": payload,
            "path": path,
        }
    return {
        "authorized": False,
        "detail": (
            f"no ACTIVE post-commit receipt chain proves PR #{pr_number} on "
            f"{head_ref} was committed through supervisor validation "
            "(COMMIT_GO/COMMIT_GO_HOLD_PUSH); refusing to bring-current, push, or "
            "merge a PR identified by number alone (a clean non-stranded PR has no "
            "such record; a merged PR had its record cleared)"
        ),
        "record": None,
        "path": None,
    }


def land_stranded_pr(
    repo_root: Path,
    pr_number: str,
    *,
    base_branch: str = "dev",
    log: Any = None,
) -> dict[str, Any]:
    """Land an ALREADY-committed, stranded PR through the NORMAL gates.

    Closes the recurring stranded-PR-behind-base treadmill — a committed PR that
    re-conflicts on the shared ``TASKS.md`` / growth-cap files every time the base
    branch advances — WITHOUT ``--admin``, force-merge, or hand-resolving review
    threads. It REUSES the existing merge phase (:func:`_run_post_commit_pipeline`)
    and the shared conflict helper (:func:`_try_auto_resolve_pr_conflict`); it adds
    NO transactional/snapshot/rollback machinery.

    Sequence (FAIL CLOSED if any precondition cannot be PROVEN, BEFORE any
    bring-current merge/commit/push):
      (i)   resolve the PR head branch name + commit OID from GitHub
            (``gh pr view <PR#> --json headRefName,headRefOid``);
      (i-auth) PROVE receipt-chain authority for the PR head BEFORE any worktree
            mutation (:func:`_stranded_landing_authority`): require an ACTIVE
            committed-through-supervisor continuation record whose target_branch ==
            the PR head AND pr_number == this PR. No such record ⇒ FAIL CLOSED with
            NO fetch/checkout/helper — so a PR number ALONE never pushes/commits/
            merges and a clean non-stranded PR (no record, or merged so its record
            was cleared) is not landable by this path;
      (ii)  fetch the PR head, then PROVE — WITHOUT mutating the worktree — that
            the OID ``git checkout <headRefName>`` would land on equals
            ``headRefOid``, so a stale/divergent local branch FAILS CLOSED BEFORE
            any checkout (the mutating checkout never runs on a mismatch);
      (ii-auth) bind the receipt chain to the EXACT head OID — the proven-local PR
            head must EQUAL or DESCEND FROM the receipt-validated ``commit_sha``,
            so a branch force-pushed to an unrelated commit after its receipt was
            recorded FAILS CLOSED, still before any checkout;
      (iii) only once that OID is proven, check out that exact head branch and
            RE-VERIFY the checked-out branch == ``headRefName`` AND local ``HEAD``
            OID == ``headRefOid`` (defense in depth) — the shared helper merges
            ``origin/<base>`` into whatever worktree is current and pushes
            ``branch_name`` (it does NOT check out itself), so without this
            on-correct-head proof a literal run could merge the base into the
            wrong local branch or push a stale branch;
      (iv)  bring the PR current with ``origin/<base>`` via the EXTENDED shared
            helper (auto-resolving ONLY the two known mechanical conflicts,
            fail-closed otherwise);
      (v)   run the EXISTING Step 14-16 merge phase
            (:func:`_run_post_commit_pipeline` with Steps 11-13 pre-marked
            complete), which merges via ``merge_pr.sh`` WITHOUT ``--admin`` and
            re-invokes the same helper on any mid-gate re-conflict.

    Returns the merge-phase result dict on success, or a fail-closed error dict
    (``status == "error"``, ``resolved == False``, the shared helper NEVER
    invoked) when a precondition cannot be proven.
    """

    def _emit(message: str) -> None:
        if log is not None:
            log(message)

    def _fail_closed(step: str, detail: str) -> dict[str, Any]:
        _emit(f"land-stranded: FAIL CLOSED ({step}): {detail}")
        return {
            "status": "error",
            "step": step,
            "resolved": False,
            "pr_number": pr_number,
            "errors": [detail],
        }

    pr_number = str(pr_number or "").strip().lstrip("#")
    if not pr_number.isdigit():
        return _fail_closed(
            "resolve_pr_head", f"PR number is not numeric: {pr_number!r}"
        )

    # (i) Resolve the PR head branch name + commit OID from GitHub. No checkout or
    # worktree mutation has happened yet, so any failure here leaves the worktree
    # untouched and the shared helper uninvoked.
    try:
        view = _run(
            ["gh", "pr", "view", pr_number, "--json", "headRefName,headRefOid"],
            cwd=repo_root,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return _fail_closed("resolve_pr_head", f"gh pr view failed: {exc}")
    if view.returncode != 0:
        return _fail_closed(
            "resolve_pr_head",
            f"gh pr view exit={view.returncode}: {(view.stderr or '').strip()[:200]}",
        )
    try:
        head_data = json.loads(view.stdout or "{}")
    except json.JSONDecodeError:
        return _fail_closed("resolve_pr_head", "malformed gh pr view JSON")
    head_ref = str(head_data.get("headRefName") or "").strip()
    head_oid = str(head_data.get("headRefOid") or "").strip()
    if not head_ref or not head_oid:
        return _fail_closed(
            "resolve_pr_head",
            f"PR #{pr_number} head branch name / OID not resolved from GitHub",
        )

    # (i-auth) RECEIPT-CHAIN AUTHORITY GATE — prove the PR head went through the
    # canonical receipt chain BEFORE any worktree mutation. This closes the
    # bridge-flagged PR-number-only push/merge route: bring-current (iv) commits +
    # pushes and the merge phase (v) merges, so a PR number ALONE must never reach
    # them. Require an ACTIVE post-commit continuation record (written only after a
    # COMMIT_GO/COMMIT_GO_HOLD_PUSH supervisor receipt + commit, cleared on a
    # successful merge) whose target_branch == this PR head AND pr_number == this
    # PR. No such record ⇒ FAIL CLOSED here: no fetch, no checkout, no helper, no
    # push/merge. A clean non-stranded PR (never committed through this executor,
    # or already merged so its record was cleared) is therefore not landable here.
    authority = _stranded_landing_authority(
        repo_root, pr_number=pr_number, head_ref=head_ref, log=log
    )
    if not authority.get("authorized"):
        return _fail_closed(
            "authority", authority.get("detail") or "no receipt-chain authority"
        )
    authorized_commit_sha = str(
        (authority.get("record") or {}).get("commit_sha") or ""
    ).strip()
    authorized_record_path = authority.get("path")

    # (ii) Fetch the PR head. `git fetch` updates ONLY remote-tracking refs /
    # FETCH_HEAD — it does NOT touch the working tree, the index, or HEAD, so it is
    # not a worktree mutation. Best-effort (check=False): a head that exists only on
    # the remote is still checked out via DWIM below once its OID is proven.
    try:
        _run(["git", "fetch", "origin", head_ref], cwd=repo_root, check=False, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        return _fail_closed("checkout_pr_head", f"git fetch of PR head failed: {exc}")

    # (ii-pre) PROVE the would-be checkout OID matches the resolved head OID BEFORE
    # any worktree mutation. `git checkout <head_ref>` lands on the LOCAL branch if
    # one exists (which may be stale/divergent), else DWIM-creates a tracking branch
    # from the freshly-fetched remote-tracking ref — so resolve the OID checkout
    # WOULD produce (local first, then origin/<head_ref>) WITHOUT checking out, and
    # compare it to headRefOid. If it cannot be resolved OR does not match, FAIL
    # CLOSED here: NO checkout runs, the worktree is NOT mutated, and the shared
    # helper is NEVER invoked. A stale/divergent local branch is caught BEFORE, not
    # after, the mutating checkout (the prior code checked out first, then verified,
    # which mutated the worktree on a mismatch — the defect this proof closes).
    def _rev_parse_commit(ref: str) -> str:
        try:
            proc = _run(
                ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                cwd=repo_root,
                check=False,
                timeout=20,
            )
        except (subprocess.SubprocessError, OSError):
            return ""
        return proc.stdout.strip() if proc.returncode == 0 else ""

    checkout_target_oid = _rev_parse_commit(head_ref) or _rev_parse_commit(
        f"origin/{head_ref}"
    )
    if not checkout_target_oid:
        return _fail_closed(
            "verify_pr_head",
            f"PR head '{head_ref}' could not be resolved locally after fetch; "
            "refusing to mutate the worktree",
        )
    if checkout_target_oid != head_oid:
        return _fail_closed(
            "verify_pr_head",
            f"would-be checkout OID {checkout_target_oid[:8]} != resolved PR head "
            f"OID {head_oid[:8]} (stale/divergent local branch); refusing to check "
            f"it out, merge {base_branch} into it, or push it",
        )

    # (ii-auth) Bind the receipt chain to the EXACT current head OID: the
    # proven-local PR head must EQUAL or DESCEND FROM the receipt-validated commit
    # recorded in the continuation chain. A branch force-pushed to an UNRELATED
    # commit AFTER its receipt was recorded therefore fails closed here — still
    # BEFORE any checkout/merge/push. (The authority gate matched the branch + PR
    # number; this proves the head we are about to land is the one that chain
    # actually authorized, not a substituted one.) The fetch above made both
    # commits local; a non-ancestor — returncode != 0, including an unknown object
    # — fails closed.
    if authorized_commit_sha and authorized_commit_sha != head_oid:
        try:
            is_ancestor = _run(
                ["git", "merge-base", "--is-ancestor", authorized_commit_sha, head_oid],
                cwd=repo_root,
                check=False,
                timeout=20,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return _fail_closed(
                "authority",
                f"could not prove PR head descends from receipt-validated commit "
                f"{authorized_commit_sha[:8]}: {exc}",
            )
        if is_ancestor.returncode != 0:
            return _fail_closed(
                "authority",
                f"PR head {head_oid[:8]} does not descend from the receipt-validated "
                f"commit {authorized_commit_sha[:8]}; refusing to land a head outside "
                "its recorded receipt chain",
            )

    # (iii) The target OID is PROVEN to match — only now check out that exact head.
    try:
        _run(["git", "checkout", head_ref], cwd=repo_root, check=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        return _fail_closed(
            "checkout_pr_head", f"could not check out PR head '{head_ref}': {exc}"
        )

    # (iii-post) RE-VERIFY the checked-out branch + local HEAD OID match the
    # resolved PR head (defense in depth against a ref racing between the proof and
    # the checkout). Any mismatch fails closed — the shared helper is NEVER invoked,
    # so the base is never merged into the wrong branch and no stale branch is
    # pushed.
    try:
        current_branch = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            check=True,
            timeout=20,
        ).stdout.strip()
        current_oid = _run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, timeout=20
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        return _fail_closed(
            "verify_pr_head", f"could not read local HEAD after checkout: {exc}"
        )
    if current_branch != head_ref:
        return _fail_closed(
            "verify_pr_head",
            f"checked-out branch {current_branch!r} != resolved PR head "
            f"{head_ref!r}; refusing to proceed",
        )
    if current_oid != head_oid:
        return _fail_closed(
            "verify_pr_head",
            f"local HEAD {current_oid[:8]} != resolved PR head OID {head_oid[:8]} "
            f"(stale/divergent local branch); refusing to merge {base_branch} into "
            f"it or push it",
        )
    _emit(
        f"land-stranded: PR #{pr_number} head verified on {head_ref} "
        f"@ {head_oid[:8]}; bringing current with origin/{base_branch}"
    )

    # (iv) Bring-current via the EXTENDED shared helper. Only the two known
    # mechanical conflicts auto-resolve; anything else surfaces the helper's
    # structured abort and we fail closed WITHOUT running the merge phase.
    bring_current = _try_auto_resolve_pr_conflict(
        repo_root,
        pr_number=pr_number,
        base_branch=base_branch,
        branch_name=head_ref,
        log=log,
    )
    if not bring_current.get("resolved"):
        result = _fail_closed(
            "bring_current",
            f"bring-current failed ({bring_current.get('action')}): "
            f"{bring_current.get('detail')}",
        )
        result["bring_current"] = bring_current
        return result
    _emit(
        f"land-stranded: bring-current {bring_current.get('action')}; "
        "running Step 14-16 merge phase"
    )

    # (v) Run the EXISTING Step 14-16 merge phase. Steps 11-13 (pre-push, push,
    # ensure_pr) are marked complete because the stranded PR is already committed,
    # pushed, and has an open PR — so _run_post_commit_pipeline skips straight to
    # Step 14 (CI-wait, which re-invokes the shared helper as its pre-CI gate),
    # Step 15 (bot-review-wait + sanctioned auto-defer), and Step 16 (merge via
    # merge_pr.sh, NO --admin). The merge is NOT reimplemented here.
    handoff: dict[str, Any] = {
        "wave_id": head_ref,
        "task_id": f"land-stranded-pr-{pr_number}",
        "pr_title": "",
        "pr_body": "",
        "caller": "land_stranded",
    }
    result = {
        "status": "success",
        "steps_completed": ["run_pre_push_script", "git_push", "ensure_pr"],
        "pr_number": pr_number,
        "merge_sha": None,
        "bring_current": bring_current,
    }
    # Thread the SAME continuation record that authorized this landing (matched on
    # target_branch + pr_number above) so a successful merge CLEARS it
    # (_clear_continuation_record) — a re-land of the now-merged PR then fails
    # closed at the authority gate. authorized_record_path is always set once the
    # gate authorized; the fallback only guards an unexpected shape.
    continuation_path = authorized_record_path or _continuation_record_path(
        repo_root, head_ref
    )
    return _run_post_commit_pipeline(
        handoff=handoff,
        repo_root=repo_root,
        result=result,
        target_branch=head_ref,
        base_branch=base_branch,
        continuation_path=continuation_path,
        log=log if log is not None else (lambda _message: None),
    )


# ── Growth-cap auto-bump (FOUNDER_OVERRIDE-gated) ─────────────────────────
# A wave that adds a NEW test file or tool script can push the repo over the
# CAP_TEST_FILES / CAP_TOOL_SCRIPTS gates (mu/tests/docs/test_growth_caps.py),
# stranding the commit at Step 8 (pre-commit-doc-check). This automates the
# founder-authorized recovery — bump the relevant CAP_* value by exactly the cap
# shortfall the COMMITTED set implies (the git index, never untracked working-tree
# strays) — but ONLY for a wave that carries the same FOUNDER_OVERRIDE token Gate
# 8 already validates. No override -> do nothing (fail-closed; the gate strands
# the commit exactly as today). The bump never weakens the ratchet: it raises the
# cap by the minimal increment the committed count requires, never the raw
# new-file count, never the count of untracked/generated strays, and never when
# the cap already covers the count.

GROWTH_CAP_TEST_RELPATH = COMMIT_GENERATED_GOVERNANCE_GROWTH_CAP_PATH
_GROWTH_CAP_TEST_BASELINE_RE = re.compile(
    r"^BASELINE_TEST_FILES\s*=\s*(\d+)", re.MULTILINE
)
_GROWTH_CAP_TOOL_BASELINE_RE = re.compile(
    r"^BASELINE_TOOL_SCRIPTS\s*=\s*(\d+)", re.MULTILINE
)
_GROWTH_CAP_TEST_VALUE_RE = re.compile(
    r"^(?P<prefix>CAP_TEST_FILES\s*=\s*)(?P<value>\d+)(?P<rest>[^\n]*)$",
    re.MULTILINE,
)
_GROWTH_CAP_TOOL_VALUE_RE = re.compile(
    r"^(?P<prefix>CAP_TOOL_SCRIPTS\s*=\s*)(?P<value>\d+)(?P<rest>[^\n]*)$",
    re.MULTILINE,
)


def _is_mu_test_file_path(relpath: str) -> bool:
    """Mirror test_growth_caps rglob('test_*.py') under mu/tests for a relpath."""
    normalized = _normalize_repo_relpath(relpath)
    if not normalized.startswith("mu/tests/"):
        return False
    name = normalized.rsplit("/", 1)[-1]
    return name.startswith("test_") and name.endswith(".py")


def _is_mu_tool_script_path(relpath: str) -> bool:
    """Mirror test_growth_caps rglob('*.py') + rglob('*.sh') under mu/tools."""
    normalized = _normalize_repo_relpath(relpath)
    if not normalized.startswith("mu/tools/"):
        return False
    return normalized.endswith((".py", ".sh"))


def _count_tracked_mu_test_files(repo_root: Path) -> int:
    """Count TRACKED (committed + staged) mu/tests/**/test_*.py via the git index.

    Deliberately NOT the Step 8 gate's on-disk rglob. The auto-bump raises a cap
    value that is written to disk and COMMITTED, so it must reflect only the test
    files this commit actually carries: the git index (tracked files plus this
    wave's staged additions, minus staged deletions). The gate's rglob also counts
    UNTRACKED/generated working-tree strays; folding those into the bump would
    inflate the shortfall and permanently over-grant the cap for a file the commit
    never includes — an invariant-weakening cap bypass. Untracked strays therefore
    never contribute to the bump. If one is present, the disk-based gate simply
    strands the commit fail-closed (on-disk count > baseline + cap), exactly as any
    over-cap commit does today; the cap is never silently inflated to cover it.

    Returns 0 on any git failure (fail-safe: a low count yields shortfall <= 0, so
    the auto-bump no-ops and the unmodified gate stays the sole authority).
    """
    proc = _run(
        ["git", "ls-files", "--", "mu/tests"],
        cwd=repo_root, check=False, timeout=30,
    )
    if proc.returncode != 0:
        return 0
    return sum(
        1
        for line in proc.stdout.splitlines()
        if line.strip() and _is_mu_test_file_path(line)
    )


def _count_tracked_mu_tool_scripts(repo_root: Path) -> int:
    """Count TRACKED (committed + staged) mu/tools/**/*.{py,sh} via the git index."""
    proc = _run(
        ["git", "ls-files", "--", "mu/tools"],
        cwd=repo_root, check=False, timeout=30,
    )
    if proc.returncode != 0:
        return 0
    return sum(
        1
        for line in proc.stdout.splitlines()
        if line.strip() and _is_mu_tool_script_path(line)
    )


def _resolve_base_merge_base_sha(repo_root: Path, base_branch: str) -> str:
    """Resolve the merge base of origin/<base> (then <base>) with HEAD."""
    base = (base_branch or "").strip()
    if not base:
        return ""
    for ref in (f"origin/{base}", base):
        verify = _run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo_root, check=False, timeout=30,
        )
        if verify.returncode != 0 or not verify.stdout.strip():
            continue
        merge_base = _run(
            ["git", "merge-base", ref, "HEAD"],
            cwd=repo_root, check=False, timeout=30,
        )
        if merge_base.returncode == 0 and merge_base.stdout.strip():
            return merge_base.stdout.strip()
    return ""


def _new_mu_test_files_vs_merge_base(repo_root: Path, base_branch: str) -> list[str]:
    """Staged mu/tests/**/test_*.py paths ABSENT on the merge base.

    Compares the index against the merge base, so a same-wave retry (where the
    new file is committed but still absent on the merge base) re-detects it.
    Returns [] when the merge base cannot be resolved (fail-safe: no bump).
    """
    merge_base = _resolve_base_merge_base_sha(repo_root, base_branch)
    if not merge_base:
        return []
    proc = _run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", merge_base],
        cwd=repo_root, check=False, timeout=30,
    )
    if proc.returncode != 0:
        return []
    added = [
        _normalize_repo_relpath(line)
        for line in proc.stdout.splitlines()
        if line.strip()
    ]
    return sorted({path for path in added if _is_mu_test_file_path(path)})


def _new_mu_tool_scripts_vs_merge_base(repo_root: Path, base_branch: str) -> list[str]:
    """Staged mu/tools/**/*.{py,sh} paths ABSENT on the merge base."""
    merge_base = _resolve_base_merge_base_sha(repo_root, base_branch)
    if not merge_base:
        return []
    proc = _run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A", merge_base],
        cwd=repo_root, check=False, timeout=30,
    )
    if proc.returncode != 0:
        return []
    added = [
        _normalize_repo_relpath(line)
        for line in proc.stdout.splitlines()
        if line.strip()
    ]
    return sorted({path for path in added if _is_mu_tool_script_path(path)})


def _cap_provenance_records_wave(cap_comment: str, wave_id: str) -> bool:
    """True when a CAP_* comment already records THIS wave."""
    if not cap_comment:
        return False
    if _extract_same_wave_founder_override_token(cap_comment, wave_id):
        return True
    raw = (wave_id or "").strip()
    return bool(raw) and raw in cap_comment


def _restore_growth_cap_file(
    cap_file: Path, original_text: str, *, log: Any
) -> bool:
    """Roll the growth-cap file back to its pre-bump content after a staging failure.

    The auto-bump writes the CAP_TEST_FILES bump to disk BEFORE it stages the
    file. If staging then fails, the bump must NOT linger unstaged in the working
    tree: a working-tree-only cap edit would let the Step 8 growth-cap gate pass
    on a value the commit never includes (fail-open), and would also poison the
    same-wave idempotency guard on a retry (the unstaged provenance comment would
    make the next run skip a bump that was never committed). Restoring the
    original content makes the auto-bump a complete no-op, so the gate falls
    through to the unmodified (too-low) cap and strands the commit fail-closed.

    Returns True when the original content is back on disk.
    """
    try:
        cap_file.write_text(original_text, encoding="utf-8")
        return True
    except OSError as exc:
        log(
            f"Step 5e: CRITICAL — could not roll back {GROWTH_CAP_TEST_RELPATH} "
            f"after a staging failure ({exc}); it may carry an unstaged cap edit "
            f"that must be reverted manually"
        )
        return False


def _maybe_autobump_growth_cap_for_founder_override(
    repo_root: Path,
    *,
    wave_id: str,
    base_branch: str,
    founder_override_token: str,
    log: Any,
) -> dict[str, Any]:
    """Automate founder-authorized CAP_TEST_FILES/CAP_TOOL_SCRIPTS bumps.

    Returns a structured outcome. Mutates mu/tests/docs/test_growth_caps.py and
    stages it ONLY on a genuine bump: a wave that (1) adds >=1 new staged file
    for a governed growth cap absent on the merge base, (2) whose committed
    (git-index) count exceeds the relevant baseline + cap by a positive shortfall,
    (3) has no prior same-wave provenance on that cap, and (4) carries the
    FOUNDER_OVERRIDE token Gate 8 validates. Any other case is a no-op
    (fail-closed); the gate strands the commit exactly as today.
    """
    outcome: dict[str, Any] = {
        "bumped": False,
        "shortfall": 0,
        "bump_amount": 0,
        "new_test_files": [],
        "new_tool_scripts": [],
        "previous_cap": None,
        "new_cap": None,
        "cap_bumps": {},
        "commit_generated_governance_paths": [],
        "reason": "",
    }
    cap_file = repo_root / "mu" / "tests" / "docs" / "test_growth_caps.py"
    if not cap_file.exists():
        outcome["reason"] = "growth_cap_file_absent"
        return outcome

    # (1) Detect genuinely-new staged governed files (absent on the merge base).
    new_test_files = _new_mu_test_files_vs_merge_base(repo_root, base_branch)
    new_tool_scripts = _new_mu_tool_scripts_vs_merge_base(repo_root, base_branch)
    outcome["new_test_files"] = new_test_files
    outcome["new_tool_scripts"] = new_tool_scripts
    if not new_test_files and not new_tool_scripts:
        # Preserve the legacy reason for existing tests/callers. There are no
        # governed additions of any type here.
        outcome["reason"] = "no_new_test_files"
        return outcome

    # (2) Compute cap SHORTFALLS from COMMITTED (git-index) counts — NOT on-disk
    # rglob counts (which would fold in untracked working-tree strays and
    # permanently over-grant a cap) and NOT raw new-file counts.
    try:
        cap_text = cap_file.read_text(encoding="utf-8")
    except OSError:
        outcome["reason"] = "growth_cap_file_unreadable"
        return outcome

    target_specs = [
        {
            "cap_name": "CAP_TEST_FILES",
            "baseline_re": _GROWTH_CAP_TEST_BASELINE_RE,
            "cap_re": _GROWTH_CAP_TEST_VALUE_RE,
            "new_paths": new_test_files,
            "projected_count": _count_tracked_mu_test_files(repo_root),
            "noun": "test file(s)",
        },
        {
            "cap_name": "CAP_TOOL_SCRIPTS",
            "baseline_re": _GROWTH_CAP_TOOL_BASELINE_RE,
            "cap_re": _GROWTH_CAP_TOOL_VALUE_RE,
            "new_paths": new_tool_scripts,
            "projected_count": _count_tracked_mu_tool_scripts(repo_root),
            "noun": "tool script(s)",
        },
    ]
    bump_edits: list[dict[str, Any]] = []
    target_reasons: list[str] = []

    for spec in target_specs:
        new_paths = list(spec["new_paths"])
        if not new_paths:
            continue
        cap_name = str(spec["cap_name"])
        baseline_match = spec["baseline_re"].search(cap_text)
        cap_match = spec["cap_re"].search(cap_text)
        if baseline_match is None or cap_match is None:
            outcome["reason"] = "growth_cap_constants_unparsed"
            return outcome
        baseline = int(baseline_match.group(1))
        current_cap = int(cap_match.group("value"))
        projected_count = int(spec["projected_count"])
        shortfall = projected_count - (baseline + current_cap)
        cap_comment = cap_match.group("rest")
        target_outcome = {
            "bumped": False,
            "shortfall": shortfall,
            "bump_amount": 0,
            "new_paths": new_paths,
            "previous_cap": current_cap,
            "new_cap": None,
            "reason": "",
        }
        outcome["cap_bumps"][cap_name] = target_outcome
        if outcome["previous_cap"] is None or cap_name == "CAP_TEST_FILES":
            outcome["previous_cap"] = current_cap
            outcome["shortfall"] = shortfall

        # (3) Idempotency guard: this wave's provenance is already recorded on
        # this cap. Continue, because another cap in the same file may still need
        # a first-time bump on a retry.
        if _cap_provenance_records_wave(cap_comment, wave_id):
            target_outcome["reason"] = "already_recorded"
            target_reasons.append("already_recorded")
            log(
                f"Step 5e: {cap_name} already records FOUNDER_OVERRIDE wave "
                f"{wave_id}; no bump (idempotent retry)"
            )
            continue

        # (4) Headroom / consolidation: this cap already covers the count.
        if shortfall <= 0:
            target_outcome["reason"] = "zero_shortfall"
            target_reasons.append("zero_shortfall")
            log(
                f"Step 5e: {cap_name} auto-bump no-op for wave {wave_id} "
                f"(shortfall={shortfall} <= 0; headroom/consolidation)"
            )
            continue

        # (5) Fail-closed: a wave with no FOUNDER_OVERRIDE is never auto-bumped.
        if not (founder_override_token or "").strip():
            outcome["reason"] = "no_founder_override"
            target_outcome["reason"] = "no_founder_override"
            log(
                f"Step 5e: new {spec['noun']} push {cap_name} over cap "
                f"(shortfall={shortfall}) but wave {wave_id} carries no "
                f"FOUNDER_OVERRIDE; growth-cap gate will strand the commit "
                f"(fail-closed)"
            )
            return outcome

        new_cap = current_cap + shortfall
        target_outcome["bumped"] = True
        target_outcome["bump_amount"] = shortfall
        target_outcome["new_cap"] = new_cap
        target_outcome["reason"] = "bumped"
        if not outcome["bumped"]:
            outcome["new_cap"] = new_cap
        outcome["bumped"] = True
        outcome["bump_amount"] += shortfall
        target_reasons.append("bumped")
        bump_edits.append(
            {
                "cap_name": cap_name,
                "cap_match": cap_match,
                "cap_comment": cap_comment,
                "new_cap": new_cap,
                "shortfall": shortfall,
                "file_desc": ", ".join(Path(path).name for path in new_paths),
            }
        )

    if not bump_edits:
        if "already_recorded" in target_reasons:
            outcome["commit_generated_governance_paths"] = [GROWTH_CAP_TEST_RELPATH]
        if target_reasons and all(reason == "already_recorded" for reason in target_reasons):
            outcome["reason"] = "already_recorded"
        elif "zero_shortfall" in target_reasons:
            outcome["reason"] = "zero_shortfall"
        elif target_reasons:
            outcome["reason"] = target_reasons[0]
        else:
            outcome["reason"] = "no_new_test_files"
        return outcome

    def _clear_pending_growth_cap_bumps(reason: str) -> None:
        outcome["bumped"] = False
        outcome["bump_amount"] = 0
        outcome["new_cap"] = None
        for target in outcome["cap_bumps"].values():
            if isinstance(target, dict) and target.get("reason") == "bumped":
                target["bumped"] = False
                target["bump_amount"] = 0
                target["new_cap"] = None
                target["reason"] = reason

    new_text = cap_text
    for edit in sorted(bump_edits, key=lambda item: item["cap_match"].start(), reverse=True):
        cap_match = edit["cap_match"]
        cap_comment = edit["cap_comment"]
        provenance = (
            f"+{edit['shortfall']} for {edit['file_desc']} "
            f"({wave_id} wave, FOUNDER_OVERRIDE:{wave_id})"
        )
        if "#" in cap_comment:
            new_rest = f"{cap_comment}; {provenance}"
        else:
            new_rest = f"{cap_comment}  # {provenance}"
        new_line = f"{cap_match.group('prefix')}{edit['new_cap']}{new_rest}"
        new_text = new_text[: cap_match.start()] + new_line + new_text[cap_match.end():]
    try:
        cap_file.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        outcome["reason"] = f"growth_cap_write_failed: {exc}"
        _clear_pending_growth_cap_bumps("growth_cap_write_failed")
        return outcome
    # Stage the cap bump so the Step 8 growth-cap gate sees it. If staging fails
    # for ANY reason — git add raises, or the file is somehow not in the staged
    # set afterward — the bump MUST NOT linger unstaged in the working tree: a
    # working-tree-only cap edit would let the gate pass on a value the commit
    # never includes (fail-open) and would poison the same-wave idempotency guard
    # on retry. Roll the file back so the bump is a complete no-op and the gate
    # falls through to the unmodified (too-low) cap and strands the commit
    # fail-closed, exactly as if no auto-bump had been attempted.
    try:
        _run(["git", "add", "--", GROWTH_CAP_TEST_RELPATH], cwd=repo_root)
        staged = GROWTH_CAP_TEST_RELPATH in _current_staged_diff_paths(repo_root)
    except Exception as exc:
        _restore_growth_cap_file(cap_file, cap_text, log=log)
        outcome["reason"] = f"growth_cap_stage_failed: {exc}"
        _clear_pending_growth_cap_bumps("growth_cap_stage_failed")
        log(
            f"Step 5e: growth-cap auto-bump rolled back for wave {wave_id} "
            f"(staging failed: {exc}); cap left unchanged so the Step 8 gate "
            f"strands the commit (fail-closed)"
        )
        return outcome
    if not staged:
        _restore_growth_cap_file(cap_file, cap_text, log=log)
        outcome["reason"] = "growth_cap_not_staged"
        _clear_pending_growth_cap_bumps("growth_cap_not_staged")
        log(
            f"Step 5e: growth-cap auto-bump rolled back for wave {wave_id} "
            f"(cap edit did not stage); cap left unchanged so the Step 8 gate "
            f"strands the commit (fail-closed)"
        )
        return outcome
    outcome["reason"] = "bumped"
    outcome["commit_generated_governance_paths"] = [GROWTH_CAP_TEST_RELPATH]
    for edit in bump_edits:
        log(
            f"Step 5e: auto-bumped {edit['cap_name']} +{edit['shortfall']} "
            f"for FOUNDER_OVERRIDE wave {wave_id} ({edit['file_desc']})"
        )
    return outcome


# Public test seams. The growth-cap auto-bump is exercised directly by the
# regression suite, and its call ORDER in the commit pipeline (auto-bump before
# the supervisor/receipt) is pinned by static source inspection. These public
# names delegate to the canonical underscore-prefixed implementations so the
# suite can exercise the contract without reaching into a module-private helper
# (the test-integrity gate forbids private-attr access in tests).
def maybe_autobump_growth_cap_for_founder_override(
    repo_root: Path,
    *,
    wave_id: str,
    base_branch: str,
    founder_override_token: str,
    log: Any,
) -> dict[str, Any]:
    """Public seam over :func:`_maybe_autobump_growth_cap_for_founder_override`."""
    return _maybe_autobump_growth_cap_for_founder_override(
        repo_root,
        wave_id=wave_id,
        base_branch=base_branch,
        founder_override_token=founder_override_token,
        log=log,
    )


def _step5e_generated_governance_provenance(outcome: dict[str, Any]) -> str:
    reason = str(outcome.get("reason") or "").strip()
    if outcome.get("bumped") is True:
        return reason or "bumped"
    if reason == "already_recorded":
        return reason
    cap_bumps = outcome.get("cap_bumps")
    if isinstance(cap_bumps, dict):
        for target_outcome in cap_bumps.values():
            if (
                isinstance(target_outcome, dict)
                and str(target_outcome.get("reason") or "").strip() == "already_recorded"
            ):
                return "already_recorded"
    return ""


def _commit_generated_governance_paths_from_step5e_outcome(
    outcome: dict[str, Any] | None,
) -> tuple[list[str], str, str | None]:
    """Extract the bounded commit-time governance path set from Step 5e output."""
    if not isinstance(outcome, dict):
        return [], "", None
    reason = str(outcome.get("reason") or "").strip()
    provenance = _step5e_generated_governance_provenance(outcome)
    has_supported_provenance = bool(provenance)
    if (
        not has_supported_provenance
        and isinstance(outcome.get("commit_generated_governance_paths"), list)
        and outcome.get("commit_generated_governance_paths")
    ):
        return [], reason, (
            "Step 5e reported commit-generated governance paths without "
            "bumped or same-wave already_recorded provenance"
        )
    if not has_supported_provenance:
        return [], reason, None
    if "commit_generated_governance_paths" not in outcome:
        raw_paths: Any = [GROWTH_CAP_TEST_RELPATH]
    else:
        raw_paths = outcome.get("commit_generated_governance_paths")
    if not isinstance(raw_paths, list) or not raw_paths:
        return [], reason, (
            "Step 5e reported commit-generated governance provenance without "
            "a non-empty path list"
        )
    paths: list[str] = []
    for raw_path in raw_paths:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return [], reason, "Step 5e reported a malformed commit-generated governance path"
        paths.append(raw_path)
    return _dedupe_repo_paths(paths), provenance, None


def commit_pipeline_impl_source() -> str:
    """Public seam returning the source of :func:`_run_commit_pipeline_impl`.

    The auto-bump call-order regression pins that the bump runs BEFORE the
    supervisor writes the pre-commit receipt; the test reads this source rather
    than the private function object.
    """
    return inspect.getsource(_run_commit_pipeline_impl)


def _run_commit_pipeline_impl(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
    skip_supervisor: bool = False,
) -> dict[str, Any]:
    """Execute the 15-step commit pipeline.

    Same command every time. Automatic bounded continuation after a local
    commit is allowed; no extra resume flags.

    Args:
        skip_supervisor: Historical direct-bypass flag. It is retained only for
            API compatibility and now fails closed before supervisor authority.
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
    if skip_supervisor:
        return {
            "status": "error",
            "step": "skip_supervisor_forbidden",
            "errors": [
                "--skip-supervisor is disabled: commit execution requires "
                "pre-commit supervisor review and receipt validation"
            ],
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
    valid, errors = validate_handoff(handoff, repo_root=repo_root)
    if not valid:
        return {"status": "error", "step": "validate_inputs", "errors": errors}
    result["steps_completed"].append("validate_inputs")
    log("Step 1: inputs validated")

    wave_id = handoff["wave_id"]
    branch_prefix = handoff["branch_prefix"]
    founder_override_token = _resolve_control_surface_founder_override_token(
        {
            "wave_id": wave_id,
            "wave_name": wave_id,
            "tracked_packet": handoff.get("tracked_packet", ""),
            "tracker_note_text": handoff.get("tracker_note_text", ""),
        },
        repo_root,
        embedded_handoff=handoff,
        wave_id=wave_id,
        wave_class=str(handoff.get("wave_class") or ""),
    )
    if founder_override_token:
        tracker_note_text = _append_founder_override_to_tracker_note(
            handoff.get("tracker_note_text", ""),
            founder_override_token,
        )
        if tracker_note_text != handoff.get("tracker_note_text", ""):
            handoff = {**handoff, "tracker_note_text": tracker_note_text}
            valid, errors = validate_handoff(handoff, repo_root=repo_root)
            if not valid:
                return {"status": "error", "step": "validate_inputs", "errors": errors}
            log(
                "Step 1b: founder override derived from authorized tracked packet "
                f"for {wave_id}"
            )
    explicit_target_branch = handoff.get("target_branch")
    if isinstance(explicit_target_branch, str) and explicit_target_branch.strip():
        target_branch = explicit_target_branch.strip()
    else:
        target_branch = f"{branch_prefix}/{wave_id}"
    base_branch = handoff["base_branch"]
    # Continuation records bind to the caller-supplied handoff. Step 5c can
    # rebuild the in-memory handoff for supervisor packaging, but a rerun still
    # reloads the original --handoff payload.
    handoff_sha = _handoff_sha(handoff)
    result["handoff_sha"] = handoff_sha
    continuation_path = _continuation_record_path(repo_root, wave_id)
    continuation = _load_post_commit_continuation(
        continuation_path,
        repo_root=repo_root,
        handoff_sha=handoff_sha,
        target_branch=target_branch,
        wave_id=wave_id,
        handoff=handoff,
    )
    if continuation:
        result["steps_completed"] = list(continuation.get("steps_completed", []))
        result["commit_sha"] = continuation["commit_sha"]
        result["pr_number"] = continuation.get("pr_number")
        if isinstance(continuation.get("pre_push_isolation"), dict):
            result["pre_push_isolation"] = dict(continuation["pre_push_isolation"])
        if isinstance(continuation.get("pre_push_restored_paths"), list):
            result["pre_push_restored_paths"] = list(continuation["pre_push_restored_paths"])
        log(
            "Resuming post-commit pipeline from local commit "
            f"{continuation['commit_sha'][:8]}"
        )
        # If resuming after COMMIT_GO_HOLD_PUSH, skip directly to
        # post-commit pipeline (steps 11-15).  Steps 1-10 already ran.
        if "hold_check" in result["steps_completed"]:
            result["receipt_decision"] = continuation.get("receipt_decision", "COMMIT_GO")
            log("Prior run held at COMMIT_GO_HOLD_PUSH — continuing to push (steps 11-15)")
            return _run_post_commit_pipeline(
                handoff=handoff,
                repo_root=repo_root,
                result=result,
                target_branch=target_branch,
                base_branch=base_branch,
                continuation_path=continuation_path,
                log=log,
            )

    # ── Step 2: ensure_feature_branch ────────────────────────────────
    try:
        current = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root).stdout.strip()
    except subprocess.CalledProcessError:
        return {"status": "error", "step": "ensure_feature_branch",
                "errors": ["Cannot determine current branch"],
                "steps_completed": result["steps_completed"]}

    if current == target_branch:
        log(f"Step 2: already on {target_branch}")
    else:
        try:
            local_target_exists, remote_target_exists = _probe_feature_branch_existence(
                repo_root,
                target_branch,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "ensure_feature_branch",
                    "errors": ["Timeout checking target branch collisions"],
                    "steps_completed": result["steps_completed"]}
        branch_start_ref = _preferred_branch_creation_base(repo_root, base_branch)
        start_from_remote_base = branch_start_ref != base_branch

        if current == base_branch:
            if local_target_exists:
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Local branch {target_branch} already exists"],
                        "steps_completed": result["steps_completed"]}
            if remote_target_exists:
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Remote branch {target_branch} already exists"],
                        "steps_completed": result["steps_completed"]}
            try:
                if start_from_remote_base:
                    tracked_dirty, untracked_dirty, outside_scope = _collect_branch_rebind_dirty_scope(
                        repo_root,
                        handoff=handoff,
                    )
                    if outside_scope:
                        preview = ", ".join(outside_scope[:10])
                        if len(outside_scope) > 10:
                            preview += ", ..."
                        return {"status": "error", "step": "ensure_feature_branch",
                                "errors": [
                                    "Refusing branch creation from fetched base because dirty paths outside "
                                    f"the wave scope are present: {preview}"
                                ],
                                "steps_completed": result["steps_completed"]}
                    scoped_dirty = sorted((tracked_dirty | untracked_dirty) - set(outside_scope))
                    snapshot: dict[str, Any] = {}
                    if scoped_dirty:
                        snapshot = _capture_scope_snapshot(repo_root, scoped_dirty)
                        _clear_scope_for_branch_rebind(
                            repo_root,
                            tracked_paths=sorted(tracked_dirty),
                            untracked_paths=sorted(untracked_dirty),
                        )
                    _run(["git", "checkout", "-b", target_branch, branch_start_ref], cwd=repo_root)
                    if snapshot:
                        _restore_scope_snapshot(repo_root, snapshot)
                    log(f"Step 2: created branch {target_branch} from {branch_start_ref}")
                else:
                    _run(["git", "checkout", "-b", target_branch], cwd=repo_root)
                    log(f"Step 2: created branch {target_branch}")
            except subprocess.CalledProcessError as exc:
                _restore_scope_snapshot_on_branch_failure(
                    repo_root,
                    snapshot=locals().get("snapshot", {}),
                    expected_branch=current,
                )
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"git checkout -b failed: {exc.stderr.strip()}"],
                        "steps_completed": result["steps_completed"]}
        else:
            if local_target_exists or remote_target_exists:
                collisions: list[str] = []
                if local_target_exists:
                    collisions.append(f"local branch {target_branch}")
                if remote_target_exists:
                    collisions.append(f"remote branch origin/{target_branch}")
                collision_text = " and ".join(collisions)
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [
                            f"On branch {current}, expected {base_branch} or {target_branch}. "
                            f"Refusing auto-rebind because {collision_text} already exists"
                        ],
                        "steps_completed": result["steps_completed"]}
            tracked_dirty, untracked_dirty, outside_scope = _collect_branch_rebind_dirty_scope(
                repo_root,
                handoff=handoff,
            )
            if outside_scope:
                preview = ", ".join(outside_scope[:10])
                if len(outside_scope) > 10:
                    preview += ", ..."
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [
                            "Refusing auto-rebind because dirty paths outside the wave scope are present: "
                            f"{preview}"
                        ],
                        "steps_completed": result["steps_completed"]}
            scoped_dirty = sorted((tracked_dirty | untracked_dirty) - set(outside_scope))
            snapshot: dict[str, Any] = {}
            try:
                # When dev has diverged on wave-owned files, a raw checkout can fail
                # closed with "would be overwritten by checkout". Snapshot only the
                # bounded dirty scope, clear it, rebind to the fresh target branch
                # from dev, then restore the exact bytes onto the canonical branch.
                if scoped_dirty:
                    snapshot = _capture_scope_snapshot(
                        repo_root,
                        scoped_dirty,
                    )
                    _clear_scope_for_branch_rebind(
                        repo_root,
                        tracked_paths=sorted(tracked_dirty),
                        untracked_paths=sorted(untracked_dirty),
                    )
                _run(["git", "checkout", "-b", target_branch, branch_start_ref], cwd=repo_root)
                if snapshot:
                    _restore_scope_snapshot(repo_root, snapshot)
                log(
                    "Step 2: rebound worktree from "
                    f"{current} to {target_branch} using {branch_start_ref} as base"
                )
            except subprocess.CalledProcessError as exc:
                _restore_scope_snapshot_on_branch_failure(
                    repo_root,
                    snapshot=snapshot,
                    expected_branch=current,
                )
                failed_cmd = exc.cmd if isinstance(exc.cmd, list) else []
                detail = (exc.stderr or exc.stdout or "").strip()
                cmd_text = " ".join(str(part) for part in failed_cmd) or "step-2 rebind helper"
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Step 2 rebind failed while running `{cmd_text}`: {detail}"],
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
    repaired_handoff = _repair_handoff_same_wave_founder_override(
        handoff,
        repo_root,
    )
    if repaired_handoff is not handoff:
        handoff = repaired_handoff
        log(f"Step 3: repaired stale FOUNDER_OVERRIDE token for {wave_id}")
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
    tracker_followup_indices = _matching_tracker_followup_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    tracker_relevant_paths = _dedupe_repo_paths(
        [
            *_dirty_tracker_relevant_paths_for_handoff(
                repo_root,
                list(handoff["files_to_stage"]),
                list(handoff.get("force_add_files", [])),
            ),
            *_staged_tracker_relevant_paths(repo_root),
        ]
    )
    tracker_file_staged = _tracker_file_will_be_staged(
        repo_root,
        list(handoff["files_to_stage"]),
        list(handoff.get("force_add_files", [])),
    )
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
        preserve_structural_tracker_note = _should_preserve_structural_tracker_note_for_control_refresh(
            lines[canonical_idx],
            note_line,
        )
        if preserve_structural_tracker_note:
            log(
                "Step 3: preserving existing L4_STRUCTURAL tracker note for "
                f"{wave_id}; same-wave L4_ENABLER repair is represented as a follow-up"
            )
        elif lines[canonical_idx] != note_line:
            lines[canonical_idx] = note_line
            tasks_modified = True
            log(f"Step 3: tracker note updated for {wave_id}")
        else:
            log(f"Step 3: tracker note for {wave_id} already present, skipping")
        followup_modified, followup_error, followup_action = _sync_tracker_followup_line(
            lines,
            wave_id=wave_id,
            canonical_idx=canonical_idx,
            tracker_followup_indices=tracker_followup_indices,
            tracker_paths=tracker_relevant_paths,
            tracker_file_staged=tracker_file_staged,
        )
        if followup_error:
            return {
                "status": "error",
                "step": "ensure_tracker_note",
                "errors": [followup_error],
                "steps_completed": result["steps_completed"],
            }
        if followup_modified:
            tasks_modified = True
            if followup_action:
                log(f"Step 3: tracker follow-up {followup_action} for {wave_id}")
        if tasks_modified:
            tasks_path.write_text("".join(lines), encoding="utf-8")
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
    files_to_stage = _canonicalize_stage_paths(repo_root, list(handoff["files_to_stage"]))
    force_files = _canonicalize_stage_paths(repo_root, list(handoff.get("force_add_files", [])))
    scope_files = _canonicalize_stage_paths(repo_root, list(handoff.get("scope_items", [])))
    handoff = {
        **handoff,
        "files_to_stage": files_to_stage,
        "force_add_files": force_files,
        "scope_items": scope_files,
    }

    # Auto-add TASKS.md if modified in step 3
    if tasks_modified and "TASKS.md" not in files_to_stage:
        files_to_stage.append("TASKS.md")
        handoff["files_to_stage"] = files_to_stage

    runtime_bus_paths = [
        path for path in [*files_to_stage, *force_files]
        if isinstance(path, str) and is_agent_bus_runtime_path(path)
    ]
    if runtime_bus_paths:
        return {
            "status": "error",
            "step": "stage_files",
            "errors": [
                "Runtime agent bus paths cannot be staged or force-added: "
                + ", ".join(sorted(runtime_bus_paths))
            ],
            "steps_completed": result["steps_completed"],
        }

    try:
        files_to_stage, force_files = _stage_handoff_paths(
            repo_root,
            files_to_stage=files_to_stage,
            force_files=force_files,
            scope_files=scope_files,
        )
        handoff = {
            **handoff,
            "files_to_stage": files_to_stage,
            "force_add_files": force_files,
        }
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
    staged_runtime_bus = [
        path for path in staged_output.splitlines()
        if is_agent_bus_runtime_path(path)
    ]
    if staged_runtime_bus:
        return {
            "status": "error",
            "step": "stage_files",
            "errors": [
                "Runtime agent bus paths are staged and cannot be committed: "
                + ", ".join(sorted(staged_runtime_bus))
            ],
            "steps_completed": result["steps_completed"],
        }

    result["steps_completed"].append("stage_files")
    log(f"Step 4: staged {len(staged_output.splitlines())} files")
    pre_step5e_authorized_paths = set(
        _dedupe_repo_paths(
            [
                *list(handoff.get("files_to_stage") or []),
                *list(handoff.get("scope_items") or []),
            ]
        )
    )

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
        return {"status": "error", "step": "collect_and_stage_indicator",
                "errors": [f"Indicator collector script not found: {indicator_script}"],
                "steps_completed": result["steps_completed"]}

    # ── Step 5b: reconcile indicator_artifact_ref in TASKS.md ─────────
    # The tracker note (Step 3) may reference a speculative indicator path.
    # After Step 5 stages the real indicator, verify and patch the reference
    # so the supervisor sees a consistent staged state (Bug 2/9 fix, 2026-04-06).
    tasks_path = repo_root / "TASKS.md"
    if tasks_path.exists() and indicator_path:
        tasks_text = tasks_path.read_text(encoding="utf-8")
        expected_ref = f"indicator_artifact_ref: {indicator_path}"
        if wave_id in tasks_text and expected_ref not in tasks_text:
            # Find and patch the indicator_artifact_ref for this wave's tracker note
            import re as _re
            # Match indicator_artifact_ref lines near this wave_id's tracker note
            pattern = _re.compile(
                rf"(- Tracker sync note \([^)]*{_re.escape(wave_id)}[^)]*\).*?"
                rf"indicator_artifact_ref: )\S+",
                _re.DOTALL,
            )
            patched = pattern.sub(rf"\g<1>{indicator_path}", tasks_text)
            if patched != tasks_text:
                tasks_path.write_text(patched, encoding="utf-8")
                _run(["git", "add", "--", "TASKS.md"], cwd=repo_root)
                log("Step 5b: reconciled indicator_artifact_ref in TASKS.md")

    # ── Step 5c: refresh packet truth + rebound handoff scope ────────
    refreshed_handoff, refreshed_staged_paths, refresh_error = refresh_commit_path_packet_truth(
        repo_root=repo_root,
        handoff=handoff,
        indicator_path=indicator_path,
        commit_status="pre_commit_supervisor_pending",
    )
    if refresh_error:
        return {
            "status": "error",
            "step": "refresh_commit_packet_truth",
            "errors": [refresh_error],
            "steps_completed": result["steps_completed"],
        }
    if refreshed_handoff is not handoff:
        handoff = refreshed_handoff
        refreshed_handoff_sha = _handoff_sha(handoff)
        result["refreshed_handoff_sha"] = refreshed_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = refreshed_handoff_sha
            result["handoff_sha"] = handoff_sha
        try:
            refreshed_files, refreshed_force = _stage_handoff_paths(
                repo_root,
                files_to_stage=list(handoff["files_to_stage"]),
                force_files=list(handoff.get("force_add_files", [])),
                scope_files=list(handoff.get("scope_items", [])),
            )
            handoff = {
                **handoff,
                "files_to_stage": refreshed_files,
                "force_add_files": refreshed_force,
            }
            refreshed_staged_paths = _current_staged_diff_paths(repo_root)
            persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
            if persist_error:
                return {
                    "status": "error",
                    "step": "refresh_commit_packet_truth",
                    "errors": [persist_error],
                    "steps_completed": result["steps_completed"],
                }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "error",
                "step": "refresh_commit_packet_truth",
                "errors": [f"git add failed after commit packet truth refresh: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
            }
        result["steps_completed"].append("refresh_commit_packet_truth")
        log(f"Step 5c: refreshed commit packet truth for {handoff.get('tracked_packet')}")
        if refreshed_staged_paths:
            log(
                "Step 5c: rebound and re-staged handoff scope to "
                f"{len(refreshed_staged_paths)} file(s)"
            )

    # ── Step 5d: restore retry-demoted packet state before receipt ──────
    # Restore before the final supervisor package so the receipt binds the
    # exact staged content. If Step 6 or early Step 7 fails afterward, the
    # retry wrapper demotes again because restore_commit_retry_state is recorded.
    try:
        restore_outcome = _restore_pending_handoff_state_for_commit_ready(
            repo_root,
            handoff,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {
            "status": "error",
            "step": "restore_commit_retry_state",
            "errors": [f"commit retry state restoration failed: {exc}"],
            "steps_completed": result["steps_completed"],
        }
    if restore_outcome.get("errors"):
        return {
            "status": "error",
            "step": "restore_commit_retry_state",
            "errors": list(restore_outcome["errors"]),
            "steps_completed": result["steps_completed"],
        }
    if restore_outcome.get("changed"):
        result["commit_retry_state_restoration"] = restore_outcome
        result["steps_completed"].append("restore_commit_retry_state")
        changed_paths = [
            str(path)
            for path in restore_outcome.get("changed", [])
            if isinstance(path, str) and path.strip()
        ]
        staged_after_restore = _current_staged_diff_paths(repo_root)
        handoff = {
            **handoff,
            "files_to_stage": _dedupe_repo_paths(
                [
                    *list(handoff.get("files_to_stage") or []),
                    *changed_paths,
                    *staged_after_restore,
                ]
            ),
            "scope_items": _dedupe_repo_paths(
                [*list(handoff.get("scope_items") or []), *changed_paths]
            ),
        }
        restored_handoff_sha = _handoff_sha(handoff)
        result["commit_retry_restored_handoff_sha"] = restored_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = restored_handoff_sha
            result["handoff_sha"] = handoff_sha
        persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
        if persist_error:
            return {
                **result,
                "status": "error",
                "step": "restore_commit_retry_state",
                "errors": [persist_error],
            }
        log(
            "Step 5d: restored commit-retry packet/task state before "
            "receipt review"
        )

    # ── Step 5e: FOUNDER_OVERRIDE-gated growth-cap auto-bump (pre-receipt) ──
    # MUST run BEFORE the supervisor (Step 6) writes the pre-commit receipt. The
    # auto-bump stages test_growth_caps.py, mutating the staged set; the receipt
    # binds to compute_staged_sha(staged diff) at review time and the Step 8 hook
    # re-verifies that SHA. Bumping AFTER the receipt (the prior Step-7d
    # placement) invalidated it and stranded Step 8 ("staged content changed
    # since review"). Here the bump precedes both the supervisor's changed_files
    # snapshot (recomputed below from `git diff --cached`, so Gate 1 dirty-state
    # stays consistent) and the receipt, so Step 8 verification matches. Placed
    # OUTSIDE the skip_supervisor guard so it also covers the no-supervisor path
    # (the Step 8 gate runs regardless). No FOUNDER_OVERRIDE -> no bump (the gate
    # strands the commit exactly as today). An auto-bump error never regresses
    # the commit path: it falls through to the unmodified Step 8 gate.
    growth_cap_outcome: dict[str, Any] = {}
    try:
        growth_cap_outcome = _maybe_autobump_growth_cap_for_founder_override(
            repo_root,
            wave_id=wave_id,
            base_branch=base_branch,
            founder_override_token=founder_override_token,
            log=log,
        )
        result["growth_cap_autobump_outcome"] = growth_cap_outcome
    except Exception as exc:
        growth_cap_outcome = {
            "bumped": False,
            "shortfall": 0,
            "bump_amount": 0,
            "new_test_files": [],
            "new_tool_scripts": [],
            "previous_cap": None,
            "new_cap": None,
            "cap_bumps": {},
            "commit_generated_governance_paths": [],
            "reason": f"error: {exc}",
        }
        result["growth_cap_autobump_outcome"] = growth_cap_outcome
        log(f"Step 5e: growth-cap auto-bump skipped (non-fatal error: {exc})")

    generated_paths, generated_provenance, generated_path_error = (
        _commit_generated_governance_paths_from_step5e_outcome(growth_cap_outcome)
    )
    if generated_path_error:
        return {
            "status": "error",
            "step": "settle_commit_generated_governance",
            "errors": [generated_path_error],
            "steps_completed": result["steps_completed"],
        }
    staged_after_step5e = set(_current_staged_diff_paths(repo_root))
    if (
        GROWTH_CAP_TEST_RELPATH in staged_after_step5e
        and GROWTH_CAP_TEST_RELPATH not in generated_paths
        and GROWTH_CAP_TEST_RELPATH not in pre_step5e_authorized_paths
    ):
        return {
            "status": "error",
            "step": "settle_commit_generated_governance",
            "errors": [
                "mu/tests/docs/test_growth_caps.py is staged without Step-5e "
                "bumped or same-wave already_recorded provenance"
            ],
            "steps_completed": result["steps_completed"],
        }
    if generated_paths:
        generated_handoff, generated_staged_paths, generated_refresh_error = (
            refresh_commit_path_packet_truth(
                repo_root=repo_root,
                handoff=handoff,
                indicator_path=indicator_path,
                commit_status="pre_commit_supervisor_pending",
                commit_generated_governance_paths=generated_paths,
                commit_generated_governance_provenance=generated_provenance,
            )
        )
        if generated_refresh_error:
            return {
                "status": "error",
                "step": "settle_commit_generated_governance",
                "errors": [generated_refresh_error],
                "steps_completed": result["steps_completed"],
            }
        handoff = generated_handoff
        generated_handoff_sha = _handoff_sha(handoff)
        result["commit_generated_governance_paths"] = generated_paths
        result["commit_generated_governance_handoff_sha"] = generated_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = generated_handoff_sha
            result["handoff_sha"] = handoff_sha
        try:
            generated_files, generated_force = _stage_handoff_paths(
                repo_root,
                files_to_stage=list(handoff["files_to_stage"]),
                force_files=list(handoff.get("force_add_files", [])),
                scope_files=list(handoff.get("scope_items", [])),
            )
            handoff = {
                **handoff,
                "files_to_stage": generated_files,
                "force_add_files": generated_force,
            }
            generated_staged_paths = _current_staged_diff_paths(repo_root)
            persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
            if persist_error:
                return {
                    "status": "error",
                    "step": "settle_commit_generated_governance",
                    "errors": [persist_error],
                    "steps_completed": result["steps_completed"],
                }
        except subprocess.CalledProcessError as exc:
            return {
                "status": "error",
                "step": "settle_commit_generated_governance",
                "errors": [
                    "git add failed after commit-generated governance settlement: "
                    f"{exc.stderr.strip()}"
                ],
                "steps_completed": result["steps_completed"],
            }
        result["steps_completed"].append("settle_commit_generated_governance")
        log(
            "Step 5e: settled commit-generated governance authority for "
            f"{', '.join(generated_paths)}"
        )
        if generated_staged_paths:
            log(
                "Step 5e: rebound post-bump handoff scope to "
                f"{len(generated_staged_paths)} file(s)"
            )

    # ── Steps 6-7: supervisor review + receipt validation ───────────
    if not skip_supervisor:
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
        handoff_wave_class = str(handoff.get("wave_class", "") or "").strip()
        branch_range_files = _range_diff_paths_for_base(repo_root, base_branch)
        supervisor_wave_class = _supervisor_wave_class_for_staged_scope(
            handoff_wave_class,
            staged_changed_files=changed_files,
            branch_range_files=branch_range_files,
        )
        if supervisor_wave_class != handoff_wave_class:
            log(
                "Step 6: retargeted staged follow-up supervisor class "
                f"{handoff_wave_class}->{supervisor_wave_class} because the staged "
                "repair has no runtime/substrate delta while the branch range does"
            )
        supervisor_founder_override_token = ""
        if _wave_class_allows_founder_override(supervisor_wave_class):
            if tok := _extract_founder_override_from_tracker_note(
                handoff.get("tracker_note_text", "")
            ):
                supervisor_founder_override_token = f"FOUNDER_OVERRIDE:{tok}"
        supervisor_tracker_note_text = str(handoff.get("tracker_note_text") or "")
        supervisor_evidence_command = _tracker_evidence_command_value(
            supervisor_tracker_note_text
        )

        supervisor_package = {
            "task_id": handoff["task_id"],
            "wave_name": wave_id,
            "lane": handoff.get("supervisor_lane", handoff["caller"]),
            "changed_files": changed_files,
            "fenced_files": _collect_commit_fenced_dirty_files(repo_root, changed_files),
            "scope_items": supervisor_scope_items,
            "fixes_implemented": handoff["fixes_implemented"],
            "deferred_items": handoff.get("deferred_items", []),
            "bridge_status": handoff.get("bridge_status", {}),
            "evidence_handles": evidence_handles,
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
            "founder_override_token": supervisor_founder_override_token,
            "wave_class": supervisor_wave_class,
            "tracker_note_text": supervisor_tracker_note_text,
            "evidence_command": supervisor_evidence_command,
        }
        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        pkg_path = scratch_dir / "auto_supervisor_package.json"
        pkg_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        # Run supervisor via structured client
        supervisor_pager_route = _handoff_pager_route(handoff)
        _safe_emit_pre_commit_supervisor_lifecycle_event(
            repo_root,
            pkg_path,
            event_type="pre_commit_supervisor_started",
            state="started",
            route=supervisor_pager_route,
        )
        try:
            run_meta_bridge_package, MetaBridgeClientError = _load_repo_meta_bridge_client(repo_root)
            sup_result = run_meta_bridge_package(
                pkg_path,
                wait_for_lock_seconds=30,
                verbose=verbose,
                bus_dir=_active_bus_dir(),
            )
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state=str(getattr(sup_result, "status", "") or "success"),
                decision=str(getattr(sup_result, "decision", "") or "unknown"),
                summary=f"Pre-commit supervisor completed: {getattr(sup_result, 'decision', 'unknown')}",
                route=supervisor_pager_route,
            )
            if sup_result.decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                return _commit_supervisor_rejection_result(
                    decision=str(getattr(sup_result, "decision", "") or ""),
                    summary=str(getattr(sup_result, "summary", "") or ""),
                    steps_completed=result["steps_completed"],
                    handoff=handoff,
                    wave_id=wave_id,
                    changed_files=changed_files,
                )
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

            handoff_evidence = dict(handoff.get("evidence_handles") or {})
            handoff_evidence["pre_commit_receipt"] = receipt_path_from_supervisor
            handoff = {
                **handoff,
                "evidence_handles": handoff_evidence,
            }
            valid_handoff, validation_errors = validate_handoff(handoff, repo_root=repo_root)
            if not valid_handoff:
                return {"status": "error", "step": "build_and_run_supervisor",
                        "errors": [
                            "Refreshed Phase B handoff invalid after supervisor receipt evidence refresh: "
                            + "; ".join(validation_errors)
                        ],
                        "steps_completed": result["steps_completed"]}

            result["steps_completed"].append("build_and_run_supervisor")
            log(f"Step 6: supervisor {receipt_decision}, receipt: {receipt_path_from_supervisor}")
        except ImportError as exc:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_INTERNAL",
                summary=f"Pre-commit supervisor import failed: {exc}",
                route=supervisor_pager_route,
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Cannot import meta_bridge_client: {exc}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_CODEX_TIMEOUT",
                summary="Pre-commit supervisor timed out",
                route=supervisor_pager_route,
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": ["Supervisor timed out"],
                    "steps_completed": result["steps_completed"]}
        except Exception as exc:
            _safe_emit_pre_commit_supervisor_lifecycle_event(
                repo_root,
                pkg_path,
                event_type="pre_commit_supervisor_completed",
                state="error",
                decision="ERROR_INTERNAL",
                summary=f"Pre-commit supervisor failed: {exc}",
                route=supervisor_pager_route,
            )
            return {"status": "error", "step": "build_and_run_supervisor",
                    "errors": [f"Supervisor failed: {exc}"],
                    "steps_completed": result["steps_completed"]}

        # ── Step 7: validate_receipt ──────────────────────────────────────
        # The supervisor receipt (step 6) is the runtime authority — it reflects
        # the actual staged state after tracker/indicator mutations in steps 3-5.
        # The original handoff receipt remains a provenance check and must not be
        # overwritten by the supervisor receipt before validation.
        handoff_receipt_rel = (
            handoff["pre_commit_receipt_path"]
            if "pre_commit_receipt_path" in handoff
            else ""
        )
        handoff_receipt_decision = ""
        if handoff_receipt_rel:
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
        else:
            handoff_receipt_decision = "STANDALONE_NO_HANDOFF_RECEIPT"

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
        receipt_refreshed_handoff_sha = _handoff_sha(handoff)
        result["receipt_refreshed_handoff_sha"] = receipt_refreshed_handoff_sha
        if _can_rekey_continuation_to_refreshed_handoff(handoff):
            handoff_sha = receipt_refreshed_handoff_sha
            result["handoff_sha"] = handoff_sha
        persist_error = _persist_phase_b_handoff_for_commit_path(repo_root, handoff)
        if persist_error:
            return {"status": "error", "step": "validate_receipt",
                    "errors": [persist_error],
                    "steps_completed": result["steps_completed"]}
        result["steps_completed"].append("validate_receipt")
        try:
            _emit_commit_ready_event(
                repo_root,
                handoff=handoff,
                receipt_path_from_supervisor=receipt_path_from_supervisor,
                receipt_decision=receipt_decision,
                handoff_receipt_rel=handoff_receipt_rel,
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "commit_ready_pager",
                "errors": [f"Commit-ready pager emission failed: {exc}"],
                "steps_completed": result["steps_completed"],
            }
        log(
            "Step 7: receipt chain verified "
            f"(handoff={handoff_receipt_decision}, supervisor={receipt_decision})"
        )

    # ── Step 8: run_pre_commit_script ─────────────────────────────────
    pre_commit_script = repo_root / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
    if pre_commit_script.exists():
        # Propagate active bus authority to the hook verifier. Receipt checks
        # must remain active on the commit path.
        step8_env = _commit_subprocess_env(skip_receipt_check=False)
        try:
            _run(
                ["bash", str(pre_commit_script)],
                cwd=repo_root,
                timeout=PRE_COMMIT_DOC_CHECK_TIMEOUT_SECONDS,
                env=step8_env,
            )
        except subprocess.CalledProcessError as exc:
            failure_detail = _tail_failure_excerpt(exc.stderr or exc.stdout or "", limit=1000)
            error_text = "pre-commit-doc-check failed"
            if failure_detail:
                error_text = f"{error_text}: {failure_detail}"
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": [error_text],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "run_pre_commit_script",
                    "errors": ["pre-commit-doc-check timed out"],
                    "steps_completed": result["steps_completed"]}

    try:
        staged_python_files = _run(
            ["git", "diff", "--cached", "--name-only"], cwd=repo_root
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        staged_python_files = []

    commit_test_files = _collect_commit_test_files(repo_root, staged_python_files)
    if commit_test_files:
        log(f"Step 8b: running pytest on {len(commit_test_files)} affected test file(s)")
        pytest_result = _run_pytest_on_files(repo_root, commit_test_files)
        if not pytest_result["passed"]:
            stderr = (pytest_result.get("stderr") or "").strip()
            stdout = (pytest_result.get("stdout") or "").strip()
            failure_detail = stderr[:1000] if stderr else stdout[:1000]
            return {
                "status": "error",
                "step": "run_pre_commit_script",
                "errors": [
                    f"targeted pytest gate failed (exit={pytest_result['exit_code']}): {failure_detail}"
                ],
                "steps_completed": result["steps_completed"],
            }

    private_attr_gate = run_private_attr_test_gate(repo_root, staged_python_files)
    if not private_attr_gate["passed"]:
        return {
            "status": "error",
            "step": "private_attr_gate",
            "errors": [_private_attr_gate_error(private_attr_gate)],
            "private_attr_gate": private_attr_gate,
            "steps_completed": result["steps_completed"],
        }
    if not private_attr_gate.get("skipped"):
        log(
            "Step 8c: private-attr/import test-integrity gate passed for "
            f"{len(private_attr_gate.get('test_files') or [])} staged test file(s)"
        )

    result["steps_completed"].append("run_pre_commit_script")
    log("Step 8: pre-commit script passed")

    # ── Step 9: git_commit ────────────────────────────────────────────
    step9_env = _commit_subprocess_env(skip_receipt_check=False)
    try:
        _commit_out, retry_detail = _run_git_commit_with_self_cleared_index_lock_retry(
            repo_root,
            handoff["commit_message"],
            env=step9_env,
        )
        if retry_detail:
            log(
                "Step 9: git commit retried after self-cleared index.lock "
                f"({retry_detail})"
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
        # Write continuation record so re-run resumes at step 11.
        _write_continuation_record(
            continuation_path,
            handoff_sha=handoff_sha,
            target_branch=target_branch,
            commit_sha=sha,
            receipt_decision=receipt_decision,
            steps_completed=result["steps_completed"],
        )
        return {
            "status": "held",
            "commit_sha": sha,
            "steps_completed": result["steps_completed"],
            "message": (
                "Committed locally. Pipeline held before push per"
                " COMMIT_GO_HOLD_PUSH. Re-run with same --handoff to"
                " continue (steps 11-15)."
            ),
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


COMMIT_RETRY_PENDING_STATUS = "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT"
COMMIT_RETRY_RESTORED_STATUS = "IMPLEMENTED / LOCAL EVIDENCE"


def _safe_tracked_control_packet_path(
    repo_root: Path,
    tracked_packet: str,
) -> tuple[Path | None, str]:
    clean = str(tracked_packet or "").strip()
    if not clean:
        return None, "tracked_packet is empty"
    if os.path.isabs(clean) or ".." in clean.split("/"):
        return None, f"tracked_packet is unsafe: {clean}"
    if not clean.startswith("reports/control_plane/"):
        return None, f"tracked_packet is outside reports/control_plane: {clean}"
    packet_path = (repo_root / clean).resolve()
    control_dir = (repo_root / "reports" / "control_plane").resolve()
    try:
        packet_path.relative_to(control_dir)
    except ValueError:
        return None, f"tracked_packet escapes control plane: {clean}"
    if not packet_path.is_file():
        return None, f"tracked_packet is not a file: {clean}"
    return packet_path, ""


def _rewrite_packet_status_line(packet_path: Path, new_status: str) -> bool:
    text = packet_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for idx, line in enumerate(lines[:40]):
        clean = line.replace("**", "").strip()
        if clean.lower().startswith("status:"):
            replacement = f"Status: {new_status}"
            if lines[idx] == replacement:
                return False
            lines[idx] = replacement
            packet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
    return False


def _pending_commit_queue_state(current_state: str) -> str:
    upper = current_state.upper()
    evidence = " / LOCAL EVIDENCE" if "LOCAL EVIDENCE" in upper else ""
    date_match = re.search(r"\(\d{4}-\d{2}-\d{2}\)", current_state)
    date_suffix = f" {date_match.group(0)}" if date_match else ""
    return f"{COMMIT_RETRY_PENDING_STATUS}{evidence}{date_suffix}"


def _commit_ready_state_from_pending_retry(current_state: str) -> str:
    date_match = re.search(r"\(\d{4}-\d{2}-\d{2}\)", current_state)
    date_suffix = f" {date_match.group(0)}" if date_match else ""
    return f"{COMMIT_RETRY_RESTORED_STATUS}{date_suffix}"


def _is_commit_retry_pending_state(state: str | None) -> bool:
    return COMMIT_RETRY_PENDING_STATUS in str(state or "")


def _restore_tasks_queue_state_for_commit_ready(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
) -> bool:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.is_file():
        return False
    wanted_wave = normalize_wave_id(wave_id)
    wanted_packet = str(tracked_packet or "").strip()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    state_re = re.compile(
        r"^(?P<prefix>\s*\d+\.\s+\*\*\[[^\]]+\]\s+)"
        r"(?P<state>.*?)"
        r"(?P<suffix>\.\*\*.*)$"
    )
    for idx, line in enumerate(lines):
        if "FOUNDER-ORDERED-REDTEAM-" not in line:
            continue
        if "Wave ID:" not in line or "Packet:" not in line:
            continue
        entry_wave = normalize_wave_id(_queue_entry_backtick_value(line, "Wave ID"))
        entry_packet = _queue_entry_backtick_value(line, "Packet")
        if wanted_wave and entry_wave != wanted_wave:
            if not wanted_packet or entry_packet != wanted_packet:
                continue
        elif wanted_packet and entry_packet != wanted_packet:
            continue
        match = state_re.match(line.rstrip("\n"))
        if not match:
            continue
        state = match.group("state").strip()
        if not _is_commit_retry_pending_state(state):
            continue
        newline = "\n" if line.endswith("\n") else ""
        new_state = _commit_ready_state_from_pending_retry(state)
        lines[idx] = (
            f"{match.group('prefix')}{new_state}{match.group('suffix')}{newline}"
        )
        changed = True
        break
    if changed:
        tasks_path.write_text("".join(lines), encoding="utf-8")
    return changed


def _demote_tasks_queue_state_for_commit_retry(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
) -> bool:
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.is_file():
        return False
    wanted_wave = normalize_wave_id(wave_id)
    wanted_packet = str(tracked_packet or "").strip()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    state_re = re.compile(
        r"^(?P<prefix>\s*\d+\.\s+\*\*\[[^\]]+\]\s+)"
        r"(?P<state>.*?)"
        r"(?P<suffix>\.\*\*.*)$"
    )
    for idx, line in enumerate(lines):
        if "FOUNDER-ORDERED-REDTEAM-" not in line:
            continue
        if "Wave ID:" not in line or "Packet:" not in line:
            continue
        entry_wave = normalize_wave_id(_queue_entry_backtick_value(line, "Wave ID"))
        entry_packet = _queue_entry_backtick_value(line, "Packet")
        if wanted_wave and entry_wave != wanted_wave:
            if not wanted_packet or entry_packet != wanted_packet:
                continue
        elif wanted_packet and entry_packet != wanted_packet:
            continue
        match = state_re.match(line.rstrip("\n"))
        if not match:
            continue
        state = match.group("state").strip()
        if not packet_status_is_completed(state):
            continue
        newline = "\n" if line.endswith("\n") else ""
        new_state = _pending_commit_queue_state(state)
        lines[idx] = (
            f"{match.group('prefix')}{new_state}{match.group('suffix')}{newline}"
        )
        changed = True
        break
    if changed:
        tasks_path.write_text("".join(lines), encoding="utf-8")
    return changed


def _demote_completed_handoff_state_for_commit_retry(
    repo_root: Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Make pre-commit failures routable again before any local commit exists."""
    tracked_packet = str(handoff.get("tracked_packet") or "").strip()
    wave_id = str(handoff.get("wave_id") or "").strip()
    outcome: dict[str, Any] = {"changed": [], "errors": []}
    packet_path, packet_error = _safe_tracked_control_packet_path(
        repo_root,
        tracked_packet,
    )
    if packet_error:
        outcome["errors"].append(packet_error)
    elif packet_path is not None:
        status = read_control_plane_packet_status(repo_root, tracked_packet)
        if packet_status_is_completed(status):
            if _rewrite_packet_status_line(packet_path, COMMIT_RETRY_PENDING_STATUS):
                _run(["git", "add", "--", tracked_packet], cwd=repo_root, timeout=30)
                outcome["changed"].append(tracked_packet)

    if wave_id or tracked_packet:
        if _demote_tasks_queue_state_for_commit_retry(
            repo_root,
            wave_id=wave_id,
            tracked_packet=tracked_packet,
        ):
            _run(["git", "add", "--", "TASKS.md"], cwd=repo_root, timeout=30)
            outcome["changed"].append("TASKS.md")
    return outcome


def _restore_pending_handoff_state_for_commit_ready(
    repo_root: Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Restore retry-demoted packet/TASKS state for commit-ready staging."""
    tracked_packet = str(handoff.get("tracked_packet") or "").strip()
    wave_id = str(handoff.get("wave_id") or "").strip()
    outcome: dict[str, Any] = {"changed": [], "errors": []}
    if not tracked_packet:
        return outcome
    packet_path, packet_error = _safe_tracked_control_packet_path(
        repo_root,
        tracked_packet,
    )
    if packet_error:
        outcome["errors"].append(packet_error)
    elif packet_path is not None:
        status = read_control_plane_packet_status(repo_root, tracked_packet)
        if _is_commit_retry_pending_state(status):
            restored_status = _commit_ready_state_from_pending_retry(str(status or ""))
            if _rewrite_packet_status_line(packet_path, restored_status):
                _run(["git", "add", "--", tracked_packet], cwd=repo_root, timeout=30)
                outcome["changed"].append(tracked_packet)

    if wave_id or tracked_packet:
        if _restore_tasks_queue_state_for_commit_ready(
            repo_root,
            wave_id=wave_id,
            tracked_packet=tracked_packet,
        ):
            _run(["git", "add", "--", "TASKS.md"], cwd=repo_root, timeout=30)
            outcome["changed"].append("TASKS.md")
    return outcome


def _invalidate_durable_handoff_pre_commit_receipt_for_commit_retry(
    repo_root: Path,
    handoff: dict[str, Any],
) -> tuple[bool, str]:
    """Clear stale supervisor receipt evidence after staged retry demotion."""
    handoff_path = agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "executors",
        "phase_b_handoff.json",
    )
    if not handoff_path.is_file():
        return False, ""
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"failed to read durable Phase B handoff for receipt invalidation: {exc}"
    if not isinstance(payload, dict):
        return False, "durable Phase B handoff is not a JSON object"

    expected_wave = normalize_wave_id(str(handoff.get("wave_id") or ""))
    actual_wave = normalize_wave_id(str(payload.get("wave_id") or ""))
    if expected_wave and actual_wave and expected_wave != actual_wave:
        return False, ""
    expected_packet = str(handoff.get("tracked_packet") or "").strip()
    actual_packet = str(payload.get("tracked_packet") or "").strip()
    if expected_packet and actual_packet and expected_packet != actual_packet:
        return False, ""

    evidence_handles = payload.get("evidence_handles")
    if not isinstance(evidence_handles, dict) or "pre_commit_receipt" not in evidence_handles:
        return False, ""
    refreshed_evidence = {
        key: value
        for key, value in evidence_handles.items()
        if key != "pre_commit_receipt"
    }
    payload["evidence_handles"] = refreshed_evidence
    tracker_note_text = payload.get("tracker_note_text")
    if isinstance(tracker_note_text, str) and tracker_note_text.strip():
        payload["tracker_note_text"] = _mark_tracker_note_pre_commit_receipt_pending(
            tracker_note_text
        )

    valid_handoff, validation_errors = validate_handoff(payload, repo_root=repo_root)
    if not valid_handoff:
        return (
            False,
            "durable Phase B handoff invalid after retry receipt invalidation: "
            + "; ".join(validation_errors),
        )
    try:
        handoff_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return False, f"failed to persist durable Phase B handoff receipt invalidation: {exc}"
    return True, ""


def _maybe_demote_completed_handoff_state_for_commit_retry(
    *,
    repo_root: Path,
    handoff: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if str(result.get("status") or "") not in {"error", "needs_phase_b"}:
        return
    steps_completed = result.get("steps_completed")
    if not isinstance(steps_completed, list):
        return
    post_commit_pre_push_failure = (
        str(result.get("step") or "") == "run_pre_push_script"
        and "git_commit" in steps_completed
    )
    if (
        ("git_commit" in steps_completed or result.get("commit_sha"))
        and not post_commit_pre_push_failure
    ):
        return
    retry_state_restored = "restore_commit_retry_state" in steps_completed
    if "validate_receipt" not in steps_completed and not retry_state_restored:
        return
    try:
        outcome = _demote_completed_handoff_state_for_commit_retry(repo_root, handoff)
    except (OSError, subprocess.CalledProcessError) as exc:
        warnings = result.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(f"commit retry state demotion failed: {exc}")
        return
    if outcome.get("changed"):
        invalidated, invalidation_error = (
            _invalidate_durable_handoff_pre_commit_receipt_for_commit_retry(
                repo_root,
                handoff,
            )
        )
        if invalidated:
            outcome["handoff_receipt_invalidated"] = True
        if invalidation_error:
            outcome["handoff_receipt_invalidation_error"] = invalidation_error
    if outcome.get("changed") or outcome.get("errors"):
        result["commit_retry_state_demotion"] = outcome
    if outcome.get("changed"):
        warnings = result.setdefault("warnings", [])
        if isinstance(warnings, list):
            warnings.append(
                "Demoted completed packet/task state to pending commit after "
                "commit executor failed after retry-state restoration before "
                "git_commit."
            )


def run_commit_pipeline(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
    skip_supervisor: bool = False,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Execute the commit pipeline with pager lifecycle edges around the run."""
    if bus_dir is not None:
        try:
            resolve_agent_bus_dir(repo_root, bus_dir)
        except ExecutorCommonError as exc:
            return {"status": "error", "step": "bus_dir", "errors": [str(exc)], "steps_completed": []}
        token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
        try:
            return run_commit_pipeline(
                handoff,
                repo_root=repo_root,
                verbose=verbose,
                skip_supervisor=skip_supervisor,
            )
        finally:
            _ACTIVE_BUS_DIR.reset(token)
    try:
        ensure_not_agent_review_mode("commit_executor.run_commit_pipeline")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "step": "review_mode_guard",
            "errors": [str(exc)],
            "steps_completed": [],
        }
    if skip_supervisor:
        return {
            "status": "error",
            "step": "skip_supervisor_forbidden",
            "errors": [
                "--skip-supervisor is disabled: commit execution requires "
                "pre-commit supervisor review and receipt validation"
            ],
            "steps_completed": [],
        }

    wave_id = str(handoff.get("wave_id") or "unknown").strip() or "unknown"
    handoff_sha = _handoff_sha(handoff) if isinstance(handoff, dict) else "invalid"
    lifecycle_pager_enabled = _commit_lifecycle_pager_enabled(repo_root)
    if lifecycle_pager_enabled:
        try:
            _emit_commit_lifecycle_event(
                repo_root,
                handoff=handoff,
                event_type="commit_started",
                state="started",
                transition_key=f"{wave_id}:{handoff_sha}:started",
                summary=f"Commit executor started for {wave_id}",
                artifact_paths={"handoff_sha": handoff_sha},
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "commit_started_pager",
                "errors": [f"Commit-start pager emission failed: {exc}"],
                "steps_completed": [],
            }

    result = _run_commit_pipeline_impl(
        handoff,
        repo_root=repo_root,
        verbose=verbose,
        skip_supervisor=skip_supervisor,
    )
    _maybe_demote_completed_handoff_state_for_commit_retry(
        repo_root=repo_root,
        handoff=handoff,
        result=result,
    )
    status = str(result.get("status") or "error")
    event_type = _commit_outcome_event_type(status)
    commit_sha = str(result.get("commit_sha") or "").strip()
    transition_key = f"{wave_id}:{handoff_sha}:{status}:{commit_sha or result.get('step', '')}"
    if lifecycle_pager_enabled:
        try:
            _emit_commit_lifecycle_event(
                repo_root,
                handoff=handoff,
                event_type=event_type,
                state=status,
                transition_key=transition_key,
                summary=f"Commit executor finished with {status}",
                artifact_paths={
                    "commit_sha": commit_sha,
                    "handoff_sha": handoff_sha,
                    "step": str(result.get("step") or ""),
                },
            )
        except Exception as exc:
            pager_failure = f"Commit-outcome pager emission failed: {exc}"
            if status in ("success", "held"):
                # Side-channel pager failure must not flip a terminal-success verdict (deferred note 2026-05-29).
                warnings = result.setdefault("warnings", [])
                if isinstance(warnings, list):
                    warnings.append(pager_failure)
                result["commit_outcome_pager_warning"] = str(exc)
            else:
                outcome_errors = list(result.get("errors") or [])
                outcome_errors.append(pager_failure)
                result = {
                    **result,
                    "status": "error",
                    "step": "commit_outcome_pager",
                    "errors": outcome_errors,
                }
    return result


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
    # Modular direct flags. Standalone may relax handoff provenance for recovery
    # continuations, but supervisor and receipt authority are always required.
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Standalone mode: sets caller=standalone, relaxes receipt requirements",
    )
    parser.add_argument(
        "--resume-continuation",
        action="store_true",
        help=(
            "Stranded-PR recovery: finish the remaining post-commit steps for an "
            "already-committed wave that has a valid COMMIT_GO continuation record, "
            "driving them through the normal gates. Fails closed (no completion "
            "action) when no valid continuation record exists for this worktree."
        ),
    )
    parser.add_argument(
        "--skip-supervisor",
        action="store_true",
        help="Disabled: commit execution always requires supervisor receipt validation",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Override task_id in handoff (e.g., [TASK-NAME])",
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    parser.add_argument(
        "--land-stranded",
        type=str,
        default=None,
        metavar="PR_NUMBER",
        help=(
            "Land an ALREADY-committed, stranded PR (by number) through the "
            "normal gates: resolve+checkout+VERIFY the PR head OID, PROVE "
            "receipt-chain authority for it (an ACTIVE committed-through-supervisor "
            "continuation record for the exact PR head — fail-closed otherwise, so "
            "a PR number alone never pushes/commits/merges and a clean non-stranded "
            "PR is not landed), bring it current with the base branch via the "
            "shared conflict helper (auto-resolving ONLY the known mechanical "
            "TASKS.md / growth-cap conflicts, fail-closed otherwise), then run the "
            "existing Step 14-16 merge phase (NO --admin). Does not require "
            "--handoff/--routing-record, but honors --bus-dir for the receipt chain."
        ),
    )
    parser.add_argument(
        "--base-branch",
        type=str,
        default="dev",
        help="Base branch for --land-stranded bring-current + merge (default: dev)",
    )
    args = parser.parse_args()

    if args.skip_supervisor:
        print(
            "[error] --skip-supervisor is disabled: commit execution requires "
            "pre-commit supervisor review and receipt validation",
            file=sys.stderr,
        )
        return 1

    # Block direct standalone mode when called from dispatch (safety guard)
    if os.environ.get("RCX_EXECUTOR_DISPATCH_PID"):
        if args.standalone:
            print("[error] --standalone is blocked when called from dispatch", file=sys.stderr)
            return 1

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1

    # Stranded-PR landing op: resolve+checkout+VERIFY the PR head, prove
    # receipt-chain authority for it, bring it current with the base branch via the
    # shared conflict helper (known mechanical conflicts only, fail-closed
    # otherwise), then run the EXISTING Step 14-16 merge phase (NO --admin). Lands
    # an ALREADY-committed PR by number, so it does NOT require a
    # handoff/routing-record — but it DOES require an active receipt chain (a
    # committed-through-supervisor continuation record) for the exact PR head.
    if args.land_stranded:
        def _land_log(message: str) -> None:
            print(f"[land-stranded] {message}", file=sys.stderr, flush=True)

        # Activate the operator-specified bus (same as the normal commit flow) so
        # the receipt-chain authority gate scans the SAME executors bus the
        # original wave wrote its continuation record into. Without this, --bus-dir
        # would be ignored and the gate would fail closed against the default bus.
        bus_token = None
        if args.bus_dir is not None:
            try:
                resolve_agent_bus_dir(repo_root, args.bus_dir)
            except ExecutorCommonError as exc:
                print(f"[land-stranded] Error: invalid --bus-dir: {exc}", file=sys.stderr)
                return 1
            bus_token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(args.bus_dir))
        try:
            land_result = land_stranded_pr(
                repo_root,
                args.land_stranded,
                base_branch=args.base_branch,
                log=None if args.json else _land_log,
            )
        finally:
            if bus_token is not None:
                _ACTIVE_BUS_DIR.reset(bus_token)
        if args.json:
            print(json.dumps(land_result, indent=2))
        else:
            print(f"[land-stranded] Status: {land_result.get('status', 'unknown')}")
            if land_result.get("step"):
                print(f"[land-stranded] Step: {land_result['step']}")
            if land_result.get("merge_sha"):
                print(f"[land-stranded] Merge SHA: {str(land_result['merge_sha'])[:8]}")
            for err in land_result.get("errors", []) or []:
                print(f"[land-stranded] Error: {err}")
        return 0 if land_result.get("status") in ("success", "held") else 1

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
        handoff, prep_errors = prepare_handoff_from_routing_record(
            record,
            repo_root,
            standalone=args.standalone,
            bus_dir=args.bus_dir,
        )
        if prep_errors or handoff is None:
            print(f"[error] Cannot prepare handoff from routing record: {prep_errors}", file=sys.stderr)
            return 1

    # Apply modular flags to handoff
    if args.standalone:
        handoff["caller"] = "standalone"
        if not handoff.get("pre_commit_receipt_path"):
            handoff["pre_commit_receipt_path"] = ""
    if args.task_id:
        handoff["task_id"] = args.task_id

    # Stranded-PR recovery: --resume-continuation finishes the remaining
    # post-commit steps for an already-committed wave. Refuse to act unless a
    # valid post-commit continuation record exists for this worktree; on a valid
    # record fall through to the unchanged run_commit_pipeline call below, which
    # reloads the same record and drives the remaining steps (CI-surface wait,
    # the normal completion step, and bot-finding auto-defer) through the normal
    # gates. No privileged path is added; completion uses the standard step.
    if args.resume_continuation:
        continuation = _load_continuation_for_resume(
            handoff,
            repo_root=repo_root,
            bus_dir=args.bus_dir,
        )
        if continuation is None:
            print(
                "[error] --resume-continuation: no valid post-commit continuation "
                "record for this worktree (not committed, on the wrong branch, "
                "dirty tree, or missing/foreign record). No completion action taken.",
                file=sys.stderr,
            )
            return 1

    result = run_commit_pipeline(
        handoff,
        repo_root=repo_root,
        verbose=args.verbose,
        skip_supervisor=args.skip_supervisor,
        bus_dir=args.bus_dir,
    )

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

    # Standalone recovery: route recoverable non-success standalone exits
    # through recovery_gate so bounded repairs can be diagnosed and retried.
    if args.standalone and _should_attempt_standalone_recovery(result):
        try:
            attempt_recovery, normalize_wave_id = _load_repo_recovery_symbols(repo_root)
            wave_id = normalize_wave_id(handoff.get("wave_id", "unknown"))
            recovery = attempt_recovery(repo_root, result, wave_id, bus_dir=args.bus_dir)
            result["recovery"] = recovery
            if args.verbose or not args.json:
                print(f"[commit-executor] Recovery: class={recovery.get('failure_class')} "
                      f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}")
        except Exception as exc:
            if args.verbose or not args.json:
                print(f"[commit-executor] Recovery gate unavailable in standalone: {exc}")

    # Propagate recovery result: if recovery succeeded, treat as recoverable
    # (exit 0 so the caller can re-invoke).
    recovery = result.get("recovery", {})
    if recovery.get("recovered"):
        return 0
    return 0 if result.get("status") in ("success", "held") else 1


if __name__ == "__main__":
    sys.exit(main())
