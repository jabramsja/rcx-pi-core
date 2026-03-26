#!/usr/bin/env python3
"""Commit executor: 15-step mechanical commit pipeline.

Same command every time. Script infers state. No caller memory. No resume mode.

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
import json
import os
import re
import subprocess
import sys
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
}

VALID_CALLERS = {"phase_b", "phase_a", "update_tracker_only"}

# GraphQL query for PR review state
PR_REVIEW_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewDecision
      latestReviews(first: 20) {
        nodes {
          author { login }
          state
        }
      }
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes {
              author { login }
              body
              path
              line
            }
          }
        }
      }
    }
  }
}
"""


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


def run_commit_pipeline(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute the 15-step commit pipeline.

    Same command every time. No resume mode. No special flags.
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

    def log(msg: str) -> None:
        if verbose:
            print(f"[commit-executor] {msg}", flush=True)

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

    result["steps_completed"].append("ensure_feature_branch")

    # ── Step 3: ensure_tracker_note ──────────────────────────────────
    tracker_note_text = handoff["tracker_note_text"]
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": ["TASKS.md not found"],
                "steps_completed": result["steps_completed"]}

    tasks_content = tasks_path.read_text(encoding="utf-8")
    wave_id_count = _count_exact_wave_id_mentions(tasks_content, wave_id)

    if wave_id_count > 1:
        return {"status": "error", "step": "ensure_tracker_note",
                "errors": [f"wave_id '{wave_id}' appears {wave_id_count} times in TASKS.md (duplicate)"],
                "steps_completed": result["steps_completed"]}

    tasks_modified = False
    if wave_id_count == 0:
        # Insert after last "^- Tracker sync note" in Ra section
        lines = tasks_content.splitlines(keepends=True)
        ra_idx = None
        ra_end_idx = None
        last_tracker_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("## Ra"):
                ra_idx = i
            if ra_idx is not None and i > ra_idx:
                if line.strip().startswith("- Tracker sync note"):
                    last_tracker_idx = i
                if line.strip() == "---" and i > ra_idx + 1:
                    ra_end_idx = i
                    break

        if ra_idx is None:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["## Ra section not found in TASKS.md"],
                    "steps_completed": result["steps_completed"]}

        if last_tracker_idx is not None:
            insert_idx = last_tracker_idx + 1
        else:
            # No tracker notes yet — insert after Ra header + description
            insert_idx = ra_idx + 2 if ra_end_idx and ra_end_idx > ra_idx + 2 else ra_idx + 1

        note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"
        lines.insert(insert_idx, note_line)
        tasks_path.write_text("".join(lines), encoding="utf-8")

        # Verify
        verify_content = tasks_path.read_text(encoding="utf-8")
        if _count_exact_wave_id_mentions(verify_content, wave_id) == 0:
            return {"status": "error", "step": "ensure_tracker_note",
                    "errors": ["wave_id not found in TASKS.md after write"],
                    "steps_completed": result["steps_completed"]}
        tasks_modified = True
        log(f"Step 3: tracker note inserted for {wave_id}")
    else:
        log(f"Step 3: tracker note for {wave_id} already present, skipping")

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

    supervisor_package = {
        "task_id": handoff["task_id"],
        "wave_name": wave_id,
        "lane": handoff.get("supervisor_lane", handoff["caller"]),
        "changed_files": changed_files,
        "scope_items": handoff["files_to_stage"],
        "fixes_implemented": handoff["fixes_implemented"],
        "deferred_items": handoff.get("deferred_items", []),
        "bridge_status": handoff.get("bridge_status", {}),
        "evidence_handles": {"indicator": indicator_path} if "collect_and_stage_indicator" in result["steps_completed"] else {},
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
        result["steps_completed"].append("git_commit")
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
        try:
            sha = _run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        except subprocess.CalledProcessError:
            sha = "unknown"
        result["steps_completed"].append("hold_check")
        return {
            "status": "held",
            "commit_sha": sha,
            "steps_completed": result["steps_completed"],
            "message": f"Committed locally. Pipeline held before push per COMMIT_GO_HOLD_PUSH.",
        }

    result["steps_completed"].append("hold_check")
    log("Step 10: COMMIT_GO, continuing to push")

    # ── Step 11: run_pre_push_script ──────────────────────────────────
    pre_push_script = repo_root / "mu" / "tools" / "hooks" / "pre-push-fast"
    if pre_push_script.exists():
        try:
            _run(["bash", str(pre_push_script)], cwd=repo_root, timeout=300)
        except subprocess.CalledProcessError as exc:
            return {"status": "error", "step": "run_pre_push_script",
                    "errors": [f"pre-push-fast failed: {exc.stderr.strip()[:500]}"],
                    "steps_completed": result["steps_completed"]}
        except subprocess.TimeoutExpired:
            return {"status": "error", "step": "run_pre_push_script",
                    "errors": ["pre-push-fast timed out"],
                    "steps_completed": result["steps_completed"]}
    result["steps_completed"].append("run_pre_push_script")
    log("Step 11: pre-push script passed")

    # ── Step 12: git_push ─────────────────────────────────────────────
    try:
        _run(
            ["git", "push", "-u", "origin", target_branch],
            cwd=repo_root, timeout=300,
        )
        result["steps_completed"].append("git_push")
        log(f"Step 12: pushed to origin/{target_branch}")
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "step": "git_push",
                "errors": [f"git push failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "step": "git_push",
                "errors": ["git push timed out"],
                "steps_completed": result["steps_completed"]}

    # ── Step 13: ensure_pr ────────────────────────────────────────────
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
        # Reuse existing PR, sync metadata
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
        # Create new PR
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

    # ── Step 14: wait_ci ──────────────────────────────────────────────
    log(f"Step 14: waiting for CI on PR #{pr_number}...")
    try:
        _run(
            ["gh", "pr", "checks", pr_number, "--watch", "--required"],
            cwd=repo_root, timeout=600,
        )
        result["steps_completed"].append("wait_ci")
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

    # ── Step 15: ensure_review_clear_and_merge ────────────────────────
    log(f"Step 15: checking review state for PR #{pr_number}...")

    # Get repo owner/name
    try:
        remote_url = _run(
            ["git", "remote", "get-url", "origin"], cwd=repo_root
        ).stdout.strip()
        # Parse owner/repo from URL
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]
        parts = remote_url.rstrip("/").split("/")
        repo_owner = parts[-2]
        repo_name = parts[-1]
        # Handle ssh URLs (git@github.com:owner/repo)
        if ":" in repo_owner:
            repo_owner = repo_owner.split(":")[-1]
    except (subprocess.CalledProcessError, IndexError):
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["Cannot determine repo owner/name from git remote"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    try:
        review_result = _run(
            ["gh", "api", "graphql", "-f",
             f"query={PR_REVIEW_QUERY}",
             "-F", f"owner={repo_owner}",
             "-F", f"repo={repo_name}",
             "-F", f"number={pr_number}"],
            cwd=repo_root, timeout=30,
        )
        review_data = json.loads(review_result.stdout)
        pr_data = review_data.get("data", {}).get("repository", {}).get("pullRequest", {})
    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Review query failed: {exc}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    # Check reviewDecision
    review_decision = pr_data.get("reviewDecision", "")
    if review_decision == "CHANGES_REQUESTED":
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": ["reviewDecision is CHANGES_REQUESTED"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

    # Check individual reviews (exclude bots)
    latest_reviews = pr_data.get("latestReviews", {}).get("nodes", [])
    for review in latest_reviews:
        author = review.get("author", {}).get("login", "")
        state = review.get("state", "")
        is_bot = author.endswith("[bot]") or author.endswith("-bot")
        if not is_bot and state == "CHANGES_REQUESTED":
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Human reviewer {author} requested changes"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}

    # Check review threads
    threads = pr_data.get("reviewThreads", {}).get("nodes", [])
    bot_findings = []
    for thread in threads:
        if thread.get("isResolved"):
            continue
        comments = thread.get("comments", {}).get("nodes", [])
        if not comments:
            continue
        author = comments[0].get("author", {}).get("login", "")
        is_bot = author.endswith("[bot]") or author.endswith("-bot")
        if not is_bot:
            # Unresolved human thread blocks
            return {"status": "error", "step": "ensure_review_clear_and_merge",
                    "errors": [f"Unresolved human review thread from {author}"],
                    "steps_completed": result["steps_completed"],
                    "pr_number": pr_number}
        else:
            # Unresolved bot thread — collect as finding
            bot_findings.append({
                "author": author,
                "body": comments[0].get("body", "")[:500],
                "path": comments[0].get("path", ""),
                "line": comments[0].get("line"),
            })

    if bot_findings:
        return {
            "status": "bot_findings_pending",
            "bot_findings": bot_findings,
            "pr_number": pr_number,
            "steps_completed": result["steps_completed"],
        }

    # Review state is clear — merge
    merge_script = repo_root / "mu" / "tools" / "hooks" / "merge_pr.sh"
    if not merge_script.exists():
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"merge_pr.sh not found"],
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

    # Post-merge verify: checkout dev, pull, verify HEAD and clean tree
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
        result["steps_completed"].append("ensure_review_clear_and_merge")
        log(f"Step 15: merged, HEAD={head_sha[:8]}, clean tree verified")
    except subprocess.CalledProcessError as exc:
        # FAIL-CLOSED on verify failure
        return {"status": "error", "step": "ensure_review_clear_and_merge",
                "errors": [f"Post-merge verify failed: {exc.stderr.strip()}"],
                "steps_completed": result["steps_completed"],
                "pr_number": pr_number}

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
