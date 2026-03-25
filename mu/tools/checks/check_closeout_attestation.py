#!/usr/bin/env python3
"""Machine-generated closeout attestation checker.

Validates that a closeout/GO claim is supported by machine-generated evidence,
not just Claude narration. Compares claimed closeout fields against actual
artifacts and validation results.

Proof classes:
  - BEHAVIORAL: test executed, command ran, exit code captured
  - SOURCE_LOCK: file content inspected, pattern matched/absent
  - INFERENCE: claim derived from narrative, not machine-verified

A GO closeout must not have INFERENCE-only proof for required invariants.

Exit codes:
    0 — attestation valid
    1 — attestation rejected (missing/overclaimed proof)
    2 — attestation input invalid

Usage:
    python3 tools/checks/check_closeout_attestation.py --attestation <path.json>
    python3 tools/checks/check_closeout_attestation.py --generate --files <f1> <f2> ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Import canonical control-surface file set from single source of truth.
_SCRIPT_DIR = Path(__file__).resolve().parent
try:
    if str(_SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPT_DIR))
    from check_control_surface_invariants import CONTROL_SURFACE_FILES as _CS_FILES
except ImportError:
    _CS_FILES = frozenset({
        "mu/tools/executors/phase_b_executor.py",
        "mu/tools/agents/meta_bridge_supervisor.py",
    })


def generate_attestation(
    repo_root: Path,
    changed_files: list[str] | None = None,
    validation_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate a machine-readable closeout attestation from actual repo state.

    This is the evidence package that constrains what a GO claim can say.
    """
    # Determine changed files and their proof strength.
    # Git-derived = BEHAVIORAL (machine-verified). Caller-supplied = DECLARED (unverified input).
    files_from_git = False
    if changed_files is None:
        try:
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip().splitlines()
            unstaged = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip().splitlines()
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip().splitlines()
            changed_files = sorted(set(f for f in staged + unstaged + untracked if f))
            files_from_git = True
        except subprocess.CalledProcessError:
            changed_files = []
    # else: caller-supplied — files_from_git stays False

    # Determine if this is a control-surface wave
    is_control_surface = bool(set(changed_files) & _CS_FILES)

    # Run control-surface invariants if applicable
    cs_results: list[dict[str, Any]] = []
    cs_checker = repo_root / "tools" / "checks" / "check_control_surface_invariants.py"
    if is_control_surface and cs_checker.exists():
        try:
            result = subprocess.run(
                ["python3", str(cs_checker), "--files"] + changed_files + ["--json"],
                cwd=repo_root, capture_output=True, text=True, check=False,
                timeout=30,
            )
            if result.stdout.strip():
                cs_data = json.loads(result.stdout)
                cs_results = cs_data.get("results", [])
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            cs_results = [{"name": "control_surface_check", "passed": False, "message": "checker failed"}]

    # Build proof inventory
    proofs: list[dict[str, Any]] = []

    # Changed files — proof class depends on source
    if files_from_git:
        proofs.append({
            "claim": "changed_files",
            "proof_class": "BEHAVIORAL",
            "source": "git diff + git ls-files",
            "value": changed_files,
        })
    else:
        proofs.append({
            "claim": "changed_files",
            "proof_class": "DECLARED",
            "source": "caller-supplied (not verified against git)",
            "value": changed_files,
        })

    # Control-surface invariants — SOURCE_LOCK proof
    if is_control_surface:
        for r in cs_results:
            proofs.append({
                "claim": r.get("name", "unknown"),
                "proof_class": "SOURCE_LOCK",
                "source": "check_control_surface_invariants.py",
                "passed": r.get("passed", False),
                "message": r.get("message", ""),
            })

    # Validation commands — BEHAVIORAL proof
    if validation_commands:
        for vc in validation_commands:
            proofs.append({
                "claim": f"validation: {vc.get('command', 'unknown')}",
                "proof_class": "BEHAVIORAL",
                "source": "validation command",
                "passed": vc.get("exit_code", -1) == 0,
                "exit_code": vc.get("exit_code"),
                "output_summary": str(vc.get("output", ""))[:200],
            })

    # Compute blockers
    blockers = [p for p in proofs if p.get("passed") is False]
    unproved = []
    if is_control_surface and not cs_results:
        unproved.append("control-surface invariants not checked (checker missing or failed)")

    attestation = {
        "changed_files": changed_files,
        "is_control_surface_wave": is_control_surface,
        "proofs": proofs,
        "blockers": blockers,
        "unproved": unproved,
    }
    # Derive go_authorized through validate_attestation() — single source of truth
    authorized, issues = validate_attestation(attestation)
    attestation["go_authorized"] = authorized
    attestation["validation_issues"] = issues
    return attestation


def validate_attestation(attestation: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a closeout attestation for GO authorization.

    Returns (authorized, issues).
    """
    issues: list[str] = []

    if not isinstance(attestation, dict):
        return False, ["Attestation must be a JSON object"]

    # Must have changed_files from machine source
    if "changed_files" not in attestation:
        issues.append("Missing changed_files (must be machine-generated)")

    # changed_files proof must exist and be BEHAVIORAL (git-derived)
    proofs_pre = attestation.get("proofs", [])
    cf_proof = next((p for p in proofs_pre if p.get("claim") == "changed_files"), None)
    if cf_proof is None:
        issues.append("No changed_files proof entry — GO requires machine-verified changed files.")
    elif cf_proof.get("proof_class") == "DECLARED":
        issues.append(
            "changed_files proof is DECLARED (caller-supplied), not BEHAVIORAL (git-derived). "
            "GO requires machine-verified changed files. Run without --files to derive from git."
        )

    # Must have proofs
    proofs = attestation.get("proofs", [])
    if not proofs:
        issues.append("No proofs present — GO requires machine evidence")

    # Check for blockers
    blockers = attestation.get("blockers", [])
    if blockers:
        for b in blockers:
            issues.append(f"Blocker: {b.get('claim', 'unknown')} — {b.get('message', 'failed')}")

    # Check for unproved areas
    unproved = attestation.get("unproved", [])
    for u in unproved:
        issues.append(f"Unproved: {u}")

    # Control-surface waves need invariant proofs
    if attestation.get("is_control_surface_wave"):
        has_cs_proof = any(
            p.get("proof_class") == "SOURCE_LOCK"
            and "INV-" in str(p.get("claim", ""))
            for p in proofs
        )
        if not has_cs_proof:
            issues.append("Control-surface wave but no invariant proofs present — GO not authorized")

        # Control-surface waves also need BEHAVIORAL test proof (validation command executed).
        # Gate-style validation ("validation: gate:...") does NOT count — those are
        # invariant checks already represented as SOURCE_LOCK proofs.  Actual test
        # execution (pytest, scripts) is required.
        has_behavioral_test = any(
            p.get("proof_class") == "BEHAVIORAL"
            and "validation" in str(p.get("claim", "")).lower()
            and "gate:" not in str(p.get("claim", "")).lower()
            and p.get("passed") is True
            for p in proofs
        )
        if not has_behavioral_test:
            issues.append(
                "Control-surface wave requires BEHAVIORAL validation-command proof "
                "(gate-style checks do not count) — run actual tests and pass "
                "results to generate_attestation()"
            )

        # Control-surface waves that touch receipt/commit chain files need
        # RECEIPT_CHAIN behavioral proof — a test that exercises the Phase B
        # → commit_executor receipt handoff end-to-end.
        receipt_chain_files = {
            "mu/tools/executors/commit_executor.py",
            "mu/tools/executors/phase_b_executor.py",
            "mu/tools/agents/meta_bridge_client.py",
            "mu/tools/agents/meta_bridge_supervisor.py",
        }
        changed_set = set(attestation.get("changed_files", []))
        if changed_set & receipt_chain_files:
            has_receipt_chain_proof = any(
                p.get("proof_class") == "BEHAVIORAL"
                and "receipt_chain" in str(p.get("claim", "")).lower()
                and p.get("passed") is True
                for p in proofs
            )
            if not has_receipt_chain_proof:
                issues.append(
                    "Control-surface wave touches receipt-chain files but no "
                    "BEHAVIORAL receipt_chain proof present — run the receipt "
                    "chain end-to-end test and include results in attestation"
                )

    # Check for INFERENCE-only claims on required invariants
    inference_only = [
        p for p in proofs
        if p.get("proof_class") == "INFERENCE"
        and p.get("required", False)
    ]
    for p in inference_only:
        issues.append(f"Inference-only proof for required claim: {p.get('claim')}")

    authorized = len(issues) == 0
    return authorized, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Closeout attestation checker")
    parser.add_argument("--attestation", type=Path, help="Path to attestation JSON")
    parser.add_argument("--generate", action="store_true", help="Generate attestation from repo state")
    parser.add_argument("--files", nargs="*", help="Changed files (for --generate)")
    parser.add_argument("--validation-commands", type=Path, help="JSON file with validation command results")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("Not in a git repo", file=sys.stderr)
        return 2

    # Load validation commands from file if provided
    val_cmds: list[dict[str, Any]] | None = None
    if args.validation_commands and args.validation_commands.exists():
        try:
            val_cmds = json.loads(args.validation_commands.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            val_cmds = None

    if args.generate:
        attestation = generate_attestation(repo_root, args.files, validation_commands=val_cmds)
        if args.json:
            print(json.dumps(attestation, indent=2))
        else:
            print(f"Changed files: {len(attestation['changed_files'])}")
            print(f"Control-surface wave: {attestation['is_control_surface_wave']}")
            print(f"Proofs: {len(attestation['proofs'])}")
            print(f"Blockers: {len(attestation['blockers'])}")
            print(f"Unproved: {len(attestation['unproved'])}")
            print(f"GO authorized: {attestation['go_authorized']}")
        return 0 if attestation["go_authorized"] else 1

    if args.attestation:
        try:
            attestation = json.loads(args.attestation.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Cannot read attestation: {exc}", file=sys.stderr)
            return 2
        authorized, issues = validate_attestation(attestation)
        if args.json:
            print(json.dumps({"authorized": authorized, "issues": issues}, indent=2))
        else:
            for issue in issues:
                print(f"  [ISSUE] {issue}")
            print(f"\n{'GO authorized.' if authorized else 'GO NOT authorized.'}")
        return 0 if authorized else 1

    # Default: generate + validate
    attestation = generate_attestation(repo_root, args.files, validation_commands=val_cmds)
    authorized, issues = validate_attestation(attestation)
    if args.json:
        print(json.dumps({"attestation": attestation, "authorized": authorized, "issues": issues}, indent=2))
    else:
        if args.verbose:
            for p in attestation["proofs"]:
                status = "PASS" if p.get("passed", True) else "FAIL"
                print(f"  [{p['proof_class']}] [{status}] {p['claim']}")
        for issue in issues:
            print(f"  [ISSUE] {issue}")
        print(f"\n{'GO authorized.' if authorized else 'GO NOT authorized.'}")
    return 0 if authorized else 1


if __name__ == "__main__":
    sys.exit(main())
