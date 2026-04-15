#!/usr/bin/env python3
"""Dialectic executor: narrows unbounded proposals through Codex deliberation.

Invoked by CONTINUE_DIALECTIC routing token from the post-merge supervisor.
Takes an unbounded next-step proposal and narrows it into something bounded
enough for Phase A planning.

Control flow:
1. Read routing record with unbounded proposal
2. Send proposal + repo context to Codex for dialectic narrowing
3. Codex proposes a bounded scope with explicit files, constraints, stop conditions
4. Write narrowed proposal to .agent_bus/executors/dialectic_result.json
5. Trigger post-merge supervisor with narrowed proposal

See: reports/archive/control_plane/executor_surfaces_plan_2026-03-22.md Section B.1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Import canonical load_routing_record from shared module
try:
    from executor_common import load_routing_record, ExecutorCommonError, run_bridge_subprocess
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    load_routing_record = _mod.load_routing_record
    ExecutorCommonError = _mod.ExecutorCommonError
    run_bridge_subprocess = _mod.run_bridge_subprocess


class DialecticExecutorError(RuntimeError):
    """Raised when dialectic executor cannot proceed."""


def extract_proposal(routing_record: dict[str, Any]) -> dict[str, Any]:
    """Extract the unbounded proposal from the routing record."""
    candidates = routing_record.get("next_candidates", [])
    unbounded = [c for c in candidates if not c.get("bounded", True)]
    if unbounded:
        return unbounded[0]
    # If all are bounded, use the first candidate
    return candidates[0] if candidates else {"candidate": "", "bounded": False}


def build_dialectic_prompt(
    proposal: dict[str, Any],
    routing_record: dict[str, Any],
    repo_root: Path,
) -> str:
    """Build the Codex dialectic narrowing prompt."""
    # Read rollout packet for context
    rollout_path = repo_root / routing_record.get("rollout_packet_path",
        "reports/control_plane/archive/meta_bridge_rollout_2026-03-20.md")
    rollout_content = ""
    if rollout_path.exists():
        try:
            rollout_content = rollout_path.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            rollout_content = "(unreadable)"

    return f"""REQUIRED PREFLIGHT: Read FOUNDER_SESSION_BOOTSTRAP.md first.

You are the DIALECTIC NARROWING agent for RCX.

## Unbounded Proposal

{json.dumps(proposal, indent=2)}

## Routing Context

Summary: {routing_record.get('summary', '')}
Request: {routing_record.get('request_for_claude', '')}

## Rollout Context (first 2000 chars)

{rollout_content}

## Your Task

Narrow this unbounded proposal into a BOUNDED scope suitable for Phase A planning.

A bounded scope must have:
1. Explicit list of files/directories in scope
2. Clear constraints (what is NOT in scope)
3. Stop conditions (when to stop)
4. Success criteria (how to know it's done)
5. Estimated complexity (small/medium/large)

Emit your narrowed proposal in this JSON envelope:

BEGIN_DIALECTIC_ENVELOPE
{{
  "candidate": "narrowed description",
  "bounded": true,
  "files_in_scope": ["file1", "file2"],
  "constraints": ["not X", "not Y"],
  "stop_conditions": ["when A", "when B"],
  "success_criteria": ["criterion 1", "criterion 2"],
  "complexity": "small|medium|large"
}}
END_DIALECTIC_ENVELOPE

Questions? Concerns? Thoughts? -- Think hard
"""


def parse_dialectic_envelope(output: str) -> dict[str, Any]:
    """Parse Codex dialectic narrowing response."""
    import re
    match = re.search(
        r"BEGIN_DIALECTIC_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_DIALECTIC_ENVELOPE",
        output, re.DOTALL,
    )
    if not match:
        raise DialecticExecutorError(
            "Codex output missing BEGIN_DIALECTIC_ENVELOPE / END_DIALECTIC_ENVELOPE block"
        )
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise DialecticExecutorError(f"Dialectic envelope not valid JSON: {exc}") from exc


def run_dialectic(
    repo_root: Path,
    *,
    max_rounds: int = 1,  # Currently single-pass; multi-round narrowing not yet implemented
    verbose: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """Execute dialectic narrowing.

    Returns a result dict with the narrowed proposal.
    """
    result: dict[str, Any] = {
        "status": "success",
        "rounds": 0,
        "narrowed_proposal": None,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[dialectic] {msg}")

    # Load routing record
    try:
        routing_record = load_routing_record(repo_root)
    except (DialecticExecutorError, ExecutorCommonError) as exc:
        return {"status": "error", "errors": [str(exc)]}

    if routing_record.get("decision") != "CONTINUE_DIALECTIC":
        log(f"Warning: expected CONTINUE_DIALECTIC, got {routing_record.get('decision')}")

    proposal = extract_proposal(routing_record)
    log(f"Unbounded proposal: {proposal.get('candidate', '(none)')}")

    if not proposal.get("candidate"):
        return {"status": "error", "errors": ["No candidate found in routing record"]}

    # Build prompt and send to Codex via bridge
    prompt = build_dialectic_prompt(proposal, routing_record, repo_root)

    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / "dialectic_task.md"
    task_path.write_text(prompt, encoding="utf-8")

    dialectic_job_id = f"dialectic-{uuid.uuid4().hex[:8]}"

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
        "review",
        "--task-file", str(task_path),
        "--summary", "Dialectic narrowing",
        "--reviewer", "codex",
        "-v", "--no-diff",
        "--job-id", dialectic_job_id,
    ]

    log("Sending to Codex for dialectic narrowing...")
    try:
        bridge_result = run_bridge_subprocess(cmd, cwd=repo_root, timeout=timeout)
    except ExecutorCommonError:
        return {"status": "timeout", "errors": ["Codex dialectic timed out"]}

    result["rounds"] = 1

    # Try to find and parse the rendered output — bound to exact job_id
    rendered_path = repo_root / ".agent_bus" / "rendered" / f"{dialectic_job_id}.md"
    if rendered_path.exists():
        content = rendered_path.read_text(encoding="utf-8")
        try:
            narrowed = parse_dialectic_envelope(content)
            result["narrowed_proposal"] = narrowed
            result["status"] = "narrowed"
            log(f"Narrowed: {narrowed.get('candidate', '(none)')}")
        except DialecticExecutorError:
            pass

    if result["status"] != "narrowed":
        # Check raw output for this job_id
        raw_job_dir = repo_root / ".agent_bus" / "raw" / dialectic_job_id
        if raw_job_dir.is_dir():
            for raw_file in raw_job_dir.iterdir():
                try:
                    content = raw_file.read_text(encoding="utf-8")
                    narrowed = parse_dialectic_envelope(content)
                    result["narrowed_proposal"] = narrowed
                    result["status"] = "narrowed"
                    log(f"Narrowed (from raw): {narrowed.get('candidate', '(none)')}")
                    break
                except (DialecticExecutorError, OSError):
                    continue

    if result["status"] != "narrowed":
        result["status"] = "no_envelope"
        result["errors"] = ["Could not parse dialectic envelope from Codex output"]

    # Write result
    result_dir = repo_root / ".agent_bus" / "executors"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / "dialectic_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    log(f"Result written: {result_path}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dialectic executor: narrow unbounded proposals through Codex",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string (from dispatcher)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=1,
        help="Max narrowing rounds (default: 1, multi-round not yet implemented)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
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

    result = run_dialectic(
        repo_root,
        max_rounds=args.max_rounds,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[dialectic] Status: {result.get('status')}")
        if result.get("narrowed_proposal"):
            print(f"[dialectic] Narrowed: {result['narrowed_proposal'].get('candidate', '')}")

    return 0 if result.get("status") in ("success", "narrowed") else 1


if __name__ == "__main__":
    sys.exit(main())
