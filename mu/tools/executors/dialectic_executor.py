#!/usr/bin/env python3
"""Dialectic executor: narrows unbounded proposals through Codex deliberation.

Invoked by CONTINUE_DIALECTIC routing token from the post-merge supervisor.
Takes an unbounded next-step proposal and narrows it into something bounded
enough for Phase A planning.

Control flow:
1. Read routing record with unbounded proposal
2. Send proposal + repo context to Codex for dialectic narrowing
3. Codex proposes a bounded scope with explicit files, constraints, stop conditions
4. Write narrowed proposal to the active agent bus executor result path
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
    from executor_common import (
        agent_bus_path,
        load_routing_record,
        ExecutorCommonError,
        resolve_agent_bus_dir,
        run_bridge_subprocess,
        configured_role_agents,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    agent_bus_path = _mod.agent_bus_path
    load_routing_record = _mod.load_routing_record
    ExecutorCommonError = _mod.ExecutorCommonError
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    run_bridge_subprocess = _mod.run_bridge_subprocess
    configured_role_agents = _mod.configured_role_agents


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
    *,
    round_number: int = 1,
    max_rounds: int = 1,
    prior_feedback: list[str] | None = None,
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

    feedback_block = ""
    if prior_feedback:
        feedback = "\n".join(f"- {item}" for item in prior_feedback)
        feedback_block = f"""
## Prior Round Feedback

{feedback}
"""

    return f"""REQUIRED PREFLIGHT: Read FOUNDER_SESSION_BOOTSTRAP.md first.

You are the DIALECTIC NARROWING agent for RCX.

## Round

Round {round_number} of {max_rounds}.

## Unbounded Proposal

{json.dumps(proposal, indent=2)}

## Routing Context

Summary: {routing_record.get('summary', '')}
Request: {routing_record.get('request_for_claude', '')}

## Rollout Context (first 2000 chars)

{rollout_content}
{feedback_block}

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


def _read_dialectic_envelope(
    repo_root: Path,
    bus_dir: str | Path | None,
    dialectic_job_id: str,
) -> dict[str, Any] | None:
    """Read the dialectic envelope for one exact bridge job id."""
    rendered_path = agent_bus_path(repo_root, bus_dir, "rendered", f"{dialectic_job_id}.md")
    if rendered_path.exists():
        try:
            return parse_dialectic_envelope(rendered_path.read_text(encoding="utf-8"))
        except (DialecticExecutorError, OSError):
            pass

    raw_job_dir = agent_bus_path(repo_root, bus_dir, "raw", dialectic_job_id)
    if raw_job_dir.is_dir():
        for raw_file in sorted(raw_job_dir.iterdir()):
            try:
                return parse_dialectic_envelope(raw_file.read_text(encoding="utf-8"))
            except (DialecticExecutorError, OSError):
                continue
    return None


def _proposal_for_next_round(
    narrowed: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Carry the latest candidate forward without trusting malformed envelopes."""
    candidate = narrowed.get("candidate")
    if isinstance(candidate, str) and candidate.strip():
        return narrowed
    return fallback


def resolve_dialectic_reviewer(repo_root: Path) -> str:
    """Reviewer agent for dialectic narrowing rounds.

    Follows the configured reviewer role (``role_agents.reviewer``, env-aware) so a
    ``set_roles --reviewer X`` switch propagates to CONTINUE_DIALECTIC rounds instead
    of being pinned to a hardcoded provider. Falls back to ``"codex"`` if resolution
    fails for any reason (missing/invalid config), preserving prior behavior.
    """
    try:
        return configured_role_agents(repo_root)["reviewer"]["agent"]
    except Exception:
        return "codex"


def run_dialectic(
    repo_root: Path,
    *,
    max_rounds: int = 1,
    verbose: bool = False,
    timeout: int = 600,
    bus_dir: str | Path | None = None,
    routing_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute dialectic narrowing.

    Returns a result dict with the narrowed proposal.
    """
    result: dict[str, Any] = {
        "status": "success",
        "rounds": 0,
        "narrowed_proposal": None,
    }
    if max_rounds < 1:
        result["status"] = "error"
        result["errors"] = ["max_rounds must be >= 1"]
        return result

    def log(msg: str) -> None:
        if verbose:
            print(f"[dialectic] {msg}")

    # Validate the active bus before any bus-owned files are read or written.
    try:
        resolve_agent_bus_dir(repo_root, bus_dir)
        if routing_record is None:
            routing_record = load_routing_record(repo_root, bus_dir=bus_dir)
    except (DialecticExecutorError, ExecutorCommonError) as exc:
        return {"status": "error", "errors": [str(exc)]}

    if routing_record.get("decision") != "CONTINUE_DIALECTIC":
        log(f"Warning: expected CONTINUE_DIALECTIC, got {routing_record.get('decision')}")

    proposal = extract_proposal(routing_record)
    log(f"Unbounded proposal: {proposal.get('candidate', '(none)')}")

    if not proposal.get("candidate"):
        return {"status": "error", "errors": ["No candidate found in routing record"]}

    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    dialectic_reviewer = resolve_dialectic_reviewer(repo_root)
    current_proposal = proposal
    round_feedback: list[str] = []
    errors: list[str] = []
    last_failure_kind = ""

    for round_number in range(1, max_rounds + 1):
        dialectic_job_id = f"dialectic-r{round_number}-{uuid.uuid4().hex[:8]}"
        prompt = build_dialectic_prompt(
            current_proposal,
            routing_record,
            repo_root,
            round_number=round_number,
            max_rounds=max_rounds,
            prior_feedback=round_feedback,
        )
        task_path = scratch_dir / f"{dialectic_job_id}.md"
        task_path.write_text(prompt, encoding="utf-8")

        cmd = [
            sys.executable, str(bridge_script),
        ]
        if bus_dir is not None:
            cmd.extend(["--bus-dir", str(bus_dir)])
        cmd.extend([
            "review",
            "--task-file", str(task_path),
            "--summary", f"Dialectic narrowing round {round_number}/{max_rounds}",
            "--reviewer", dialectic_reviewer,
            "-v", "--no-diff",
            "--job-id", dialectic_job_id,
        ])

        log(f"Sending to Codex for dialectic narrowing round {round_number}/{max_rounds}...")
        try:
            run_bridge_subprocess(cmd, cwd=repo_root, timeout=timeout)
        except ExecutorCommonError:
            result["status"] = "timeout"
            result["rounds"] = round_number
            result["errors"] = [f"Codex dialectic timed out in round {round_number}"]
            break

        result["rounds"] = round_number
        narrowed = _read_dialectic_envelope(repo_root, bus_dir, dialectic_job_id)
        if narrowed is None:
            errors = [
                f"Round {round_number} did not produce a parseable dialectic envelope"
            ]
            last_failure_kind = "no_envelope"
            round_feedback = errors
            continue

        result["narrowed_proposal"] = narrowed
        if narrowed.get("bounded") is True:
            result["status"] = "narrowed"
            log(f"Narrowed: {narrowed.get('candidate', '(none)')}")
            break

        current_proposal = _proposal_for_next_round(narrowed, current_proposal)
        errors = [f"Round {round_number} returned bounded=false"]
        last_failure_kind = "bounded_false"
        round_feedback = errors
        log(errors[0])

    if result["status"] == "success":
        if last_failure_kind == "no_envelope":
            result["status"] = "no_envelope"
            result["errors"] = errors or ["Could not parse dialectic envelope from Codex output"]
        elif result["rounds"] >= max_rounds:
            result["status"] = "max_rounds_reached"
            result["errors"] = errors or ["Dialectic narrowing exhausted max_rounds"]
        else:
            result["status"] = "no_envelope"
            result["errors"] = errors or ["Could not parse dialectic envelope from Codex output"]

    # Write result
    result_dir = agent_bus_path(repo_root, bus_dir, "executors")
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
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=1,
        help="Max narrowing rounds (default: 1)",
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

    routing_record = None
    if args.routing_record:
        try:
            parsed_record = json.loads(args.routing_record)
        except json.JSONDecodeError as exc:
            print(f"[error] --routing-record is not valid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(parsed_record, dict):
            print("[error] --routing-record must decode to a JSON object", file=sys.stderr)
            return 1
        routing_record = parsed_record

    result = run_dialectic(
        repo_root,
        max_rounds=args.max_rounds,
        verbose=args.verbose,
        bus_dir=args.bus_dir,
        routing_record=routing_record,
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
