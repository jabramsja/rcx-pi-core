#!/usr/bin/env python3
"""Mechanical invariant checker for Phase B / commit control surfaces.

Verifies that the exact class of defects that recently slipped through
reviewer blind spots are not present:

1. Implementer does not route through review-mode bridge_supervisor
2. Bridge loop re-invokes implementer on REQUEST_CHANGES/NO_GO
3. Receipt writer returns per-invocation path, not canonical
4. Receipt client does not heuristically discover receipts
5. Protocol docs do not present manual commit fallback as normal path

This checker activates when any control-surface file is in the changed set.
It is wired as a validation gate in meta_bridge_supervisor.py.

Exit codes:
    0 — all invariants hold (or no control-surface files touched)
    1 — one or more invariants violated
"""

from __future__ import annotations

import argparse
import ast
import json
import posixpath
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# SINGLE SOURCE OF TRUTH: Files that constitute the Phase B / commit control surface.
# If ANY of these are in the changed file set, invariants must be checked.
# Both `mu/` and `tools/` spellings included for hardlinked/symlinked mirrors.
# Other modules (shared_agent_utils, check_closeout_attestation, meta_bridge_supervisor,
# bridge_supervisor) MUST import this set instead of maintaining their own copy.
CONTROL_SURFACE_FILES = frozenset({
    # Executors
    "mu/tools/executors/phase_b_executor.py",
    "mu/tools/executors/phase_b_implementer.py",
    "mu/tools/executors/commit_executor.py",
    # Agents (both path spellings for hardlinked bridge_supervisor)
    "mu/tools/agents/meta_bridge_supervisor.py",
    "mu/tools/agents/meta_bridge_client.py",
    "mu/tools/agents/verify_pre_commit_receipt.py",
    "mu/tools/agents/bridge_supervisor.py",
    "tools/agents/bridge_supervisor.py",
    "mu/tools/agents/bridge_adapters.py",
    "tools/agents/bridge_adapters.py",
    # Runners (both path spellings)
    "mu/tools/runners/run_review.py",
    "tools/runners/run_review.py",
    "mu/tools/runners/shared_agent_utils.py",
    "tools/runners/shared_agent_utils.py",
    # Checkers (both path spellings)
    "mu/tools/checks/check_control_surface_invariants.py",
    "tools/checks/check_control_surface_invariants.py",
    "mu/tools/checks/check_closeout_attestation.py",
    "tools/checks/check_closeout_attestation.py",
    # Executor config and shared utilities
    "mu/tools/executors/executor_config.json",
    "mu/tools/executors/executor_common.py",
    "mu/tools/executors/executor_dispatch.py",
    # Templates (bridge reviewer and meta-bridge task prompts)
    "mu/tools/agents/templates/bridge_reviewer_prompt.txt",
    "mu/tools/agents/templates/meta_bridge_task.txt",
    # Protocol docs that govern Phase B / commit behavior
    "CLAUDE.md",
})


@lru_cache(maxsize=1)
def _git_toplevel() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    toplevel = result.stdout.strip()
    return toplevel or None


def normalize_repo_relative_path(p: str) -> str:
    """Normalize a path to canonical repo-relative form for membership checks."""
    p = p.replace("\\", "/")
    toplevel = _git_toplevel()
    if toplevel:
        normalized_root = toplevel.replace("\\", "/").rstrip("/")
        if p == normalized_root:
            p = ""
        elif p.startswith(normalized_root + "/"):
            p = p[len(normalized_root) + 1:]
    normalized = posixpath.normpath(p)
    return "" if normalized == "." else normalized


def _normalize_path(p: str) -> str:
    """Backwards-compatible wrapper for tests and existing callers."""
    return normalize_repo_relative_path(p)


def _touches_control_surface(changed_files: list[str]) -> bool:
    """Check if any changed file is a control-surface file."""
    normalized = {_normalize_path(f) for f in changed_files}
    return bool(normalized & CONTROL_SURFACE_FILES)


def check_implementer_not_review_mode(repo_root: Path) -> tuple[bool, str]:
    """INV-1: phase_b_implementer.py must use bridge_adapters.run_adapter(), not bridge_supervisor review."""
    path = repo_root / "mu" / "tools" / "executors" / "phase_b_implementer.py"
    if not path.exists():
        return True, "phase_b_implementer.py not found (skip)"
    src = path.read_text(encoding="utf-8")
    # Must not construct a "review" command or import bridge_supervisor
    if "bridge_supervisor" in src:
        return False, "phase_b_implementer.py references bridge_supervisor (must use bridge_adapters directly)"
    if '"review"' in src and "subprocess" in src:
        return False, "phase_b_implementer.py constructs a review subprocess command"
    # Must positively reference bridge_adapters and call run_adapter
    if "bridge_adapters" not in src:
        return False, "phase_b_implementer.py does not reference bridge_adapters (must use bridge_adapters.run_adapter())"
    if "run_adapter" not in src:
        return False, "phase_b_implementer.py does not call run_adapter() (must use bridge_adapters.run_adapter())"
    return True, "implementer uses bridge_adapters.run_adapter(), not review mode"


def check_bridge_loop_reinvokes_implementer(repo_root: Path) -> tuple[bool, str]:
    """INV-2: bridge loop must re-invoke implementer on REQUEST_CHANGES/NO_GO (AST-aware).

    Uses Python AST to find the for-loop in run_phase_b that contains the bridge
    convergence loop, then verifies that the REQUEST_CHANGES/NO_GO branch contains
    a call to invoke_implementer, and that QUESTION leads to a return statement.
    """
    import ast

    path = repo_root / "mu" / "tools" / "executors" / "phase_b_executor.py"
    if not path.exists():
        return True, "phase_b_executor.py not found (skip)"
    src = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as exc:
        return False, f"phase_b_executor.py has syntax error: {exc}"

    # Find run_phase_b function
    run_phase_b_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_phase_b":
            run_phase_b_func = node
            break
    if run_phase_b_func is None:
        return False, "run_phase_b function not found"

    # Helper: check if an AST subtree contains a Call to a function matching name
    def _has_call(subtree: ast.AST, func_name: str) -> bool:
        for n in ast.walk(subtree):
            if isinstance(n, ast.Call):
                # Handle both Name("invoke_implementer") and Attribute(*.invoke_implementer)
                if isinstance(n.func, ast.Name) and n.func.id == func_name:
                    return True
                if isinstance(n.func, ast.Attribute) and n.func.attr == func_name:
                    return True
        return False

    def _has_return(subtree: ast.AST) -> bool:
        for n in ast.walk(subtree):
            if isinstance(n, ast.Return):
                return True
        return False

    # Find If nodes in run_phase_b that test bridge_decision against known values.
    # AST-structural: inspect the test expression, not the full source text.
    found_rc_with_implementer = False
    found_question_failclosed = False

    def _if_tests_variable_against(test_node: ast.AST, var_name: str, values: set[str]) -> bool:
        """Check if an If test compares `var_name` to string constants in `values` (AST-structural)."""
        if isinstance(test_node, ast.Compare):
            if isinstance(test_node.left, ast.Name) and test_node.left.id == var_name:
                for op, comparator in zip(test_node.ops, test_node.comparators):
                    if isinstance(op, ast.In) and isinstance(comparator, (ast.Tuple, ast.List)):
                        const_vals = {
                            e.value for e in comparator.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        }
                        if values <= const_vals:
                            return True
                    if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant):
                        if comparator.value in values:
                            return True
        # Handle: BoolOp(Or, [Compare(...), Compare(...)])
        if isinstance(test_node, ast.BoolOp) and isinstance(test_node.op, ast.Or):
            matched = set()
            for v in test_node.values:
                if isinstance(v, ast.Compare) and isinstance(v.left, ast.Name) and v.left.id == var_name:
                    for op, comp in zip(v.ops, v.comparators):
                        if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and comp.value in values:
                            matched.add(comp.value)
            if values <= matched:
                return True
        return False

    # Find ALL for-loops in run_phase_b that contain bridge_decision checks.
    # Both the initial bridge loop and the re-entry loop must be verified.
    # A loop qualifies if it contains an If testing bridge_decision against RC/NO_GO.
    # invoke_implementer must be called INSIDE the RC/NO_GO branch specifically,
    # not just anywhere in the loop body.
    def _has_continue(subtree: ast.AST) -> bool:
        for n in ast.walk(subtree):
            if isinstance(n, ast.Continue):
                return True
        return False

    bridge_loops_found = 0
    bridge_loops_with_implementer = 0

    for node in ast.walk(run_phase_b_func):
        # Check for-loops that contain bridge_decision checks
        if isinstance(node, ast.For):
            loop_has_rc_check = False
            loop_has_question_failclosed = False
            loop_rc_has_implementer = False
            rc_has_continue = False
            loop_body_has_implementer = False
            for child in ast.walk(node):
                if isinstance(child, ast.If):
                    if _if_tests_variable_against(child.test, "bridge_decision", {"REQUEST_CHANGES", "NO_GO"}):
                        loop_has_rc_check = True
                        # Pattern A: invoke_implementer INSIDE the RC/NO_GO if-branch
                        if _has_call(child, "invoke_implementer"):
                            loop_rc_has_implementer = True
                        # Pattern B: RC/NO_GO branch continues; implementer at loop top
                        if _has_continue(child):
                            rc_has_continue = True
                    if _if_tests_variable_against(child.test, "bridge_decision", {"QUESTION"}):
                        if _has_return(child):
                            loop_has_question_failclosed = True
            # Check if invoke_implementer is a DIRECT statement in the for-loop body
            # (not nested inside an unrelated if-branch). For Pattern B, the
            # implementer must be at the loop top, re-executed on every iteration.
            for stmt in node.body:
                if _has_call(stmt, "invoke_implementer") and not isinstance(stmt, ast.If):
                    loop_body_has_implementer = True
                    break
            if loop_has_rc_check:
                bridge_loops_found += 1
                # Accept Pattern A (inside RC branch) or Pattern B (loop-top + continue in RC)
                if loop_rc_has_implementer or (loop_body_has_implementer and rc_has_continue):
                    bridge_loops_with_implementer += 1
                if loop_has_question_failclosed:
                    found_question_failclosed = True

        # Also check top-level If nodes (non-loop RC/NO_GO branches)
        if isinstance(node, ast.If):
            if _if_tests_variable_against(node.test, "bridge_decision", {"REQUEST_CHANGES", "NO_GO"}):
                # invoke_implementer must be INSIDE this branch
                if _has_call(node, "invoke_implementer"):
                    found_rc_with_implementer = True
            if _if_tests_variable_against(node.test, "bridge_decision", {"QUESTION"}):
                if _has_return(node):
                    found_question_failclosed = True

    # Accept if EITHER: (a) at least one If-level RC/NO_GO has invoke_implementer,
    # OR (b) all for-loops with bridge_decision checks use one of the two valid patterns.
    if bridge_loops_found > 0 and bridge_loops_with_implementer >= bridge_loops_found:
        found_rc_with_implementer = True

    errors = []
    if not found_rc_with_implementer:
        errors.append(
            f"REQUEST_CHANGES/NO_GO branch does not call invoke_implementer "
            f"(AST-verified: {bridge_loops_with_implementer}/{bridge_loops_found} loops have it)"
        )
    if not found_question_failclosed:
        errors.append("QUESTION branch does not return/fail-closed (AST-verified)")

    if errors:
        return False, "; ".join(errors)
    return True, "bridge loop re-invokes implementer on REQUEST_CHANGES/NO_GO, QUESTION fails closed (AST-verified)"


def check_receipt_writer_returns_per_invocation(repo_root: Path) -> tuple[bool, str]:
    """INV-3: write_pre_commit_receipt must return per-invocation path."""
    path = repo_root / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
    if not path.exists():
        return True, "meta_bridge_supervisor.py not found (skip)"
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return False, f"meta_bridge_supervisor.py parse error: {exc}"

    func = next(
        (
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "write_pre_commit_receipt"
        ),
        None,
    )
    if func is None:
        return False, "write_pre_commit_receipt function not found"

    canonical_written = False
    per_invocation_assigned = False
    per_invocation_written = False
    returns_per_invocation = False

    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "per_invocation_path":
                    per_invocation_assigned = True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and node.func.attr == "write_text":
                if owner.id == "canonical_path":
                    canonical_written = True
                if owner.id == "per_invocation_path":
                    per_invocation_written = True
        if isinstance(node, ast.Return):
            if isinstance(node.value, ast.Name) and node.value.id == "per_invocation_path":
                returns_per_invocation = True

    if returns_per_invocation and per_invocation_assigned and per_invocation_written:
        return True, "receipt writer returns exact per-invocation path"
    if canonical_written and not returns_per_invocation:
        return False, "receipt writer returns canonical or ambiguous path instead of per-invocation artifact"
    return False, "write_pre_commit_receipt does not prove exact per-invocation return path"


def check_client_no_heuristic_discovery(repo_root: Path) -> tuple[bool, str]:
    """INV-4: meta_bridge_client must not discover receipts by directory listing."""
    path = repo_root / "mu" / "tools" / "agents" / "meta_bridge_client.py"
    if not path.exists():
        return True, "meta_bridge_client.py not found (skip)"
    src = path.read_text(encoding="utf-8")
    src_lower = src.lower()

    # Check all forms of heuristic receipt discovery
    heuristic_patterns = [
        ("iterdir", "iterdir()"),
        ("listdir", "os.listdir()"),
        ("glob", "glob/Path.glob()"),
        ("scandir", "os.scandir()"),
    ]
    for pattern, desc in heuristic_patterns:
        if pattern in src and "receipt" in src_lower:
            # Check if it's in a context that sorts or picks from directory listing
            if "sorted(" in src and pattern in src:
                return False, f"meta_bridge_client.py heuristically discovers receipts via sorted({desc})"
            if pattern in src:
                return False, f"meta_bridge_client.py uses {desc} near receipt handling — heuristic discovery"

    if "receipts[0]" in src or "receipts[-1]" in src:
        return False, "meta_bridge_client.py picks receipt by index from directory listing"
    return True, "client captures exact receipt path from writer, no heuristic"


def _check_single_doc_no_manual_fallback(path: Path, label: str) -> tuple[bool, str]:
    """Check a single protocol doc for manual commit/merge fallback."""
    if not path.exists():
        return True, f"{label} not found (skip)"
    src = path.read_text(encoding="utf-8")

    # For CLAUDE.md: check the Wave Protocol / Workflow / Commit sections
    # For memory files: check the Commit Protocol section
    # Generic: look for manual merge/push/PR recipes in protocol-relevant sections
    manual_patterns = [
        ("git push -u origin", "manual git push"),
        ("gh pr create --base dev", "manual gh pr create"),
        ("merge_pr.sh", "manual merge_pr.sh invocation"),
    ]

    for pattern, desc in manual_patterns:
        if pattern in src:
            # Check context: is this in a "manual fallback" or "do this" section,
            # or just describing what the executor does internally?
            lines = src.splitlines()
            for i, line in enumerate(lines):
                if pattern in line:
                    # If the line is a comment inside a code block describing executor behavior, skip
                    # If it's a direct instruction to the user, flag it
                    context_start = max(0, i - 3)
                    context = "\n".join(lines[context_start:i + 1]).lower()
                    if "executor" in context and ("handles" in context or "internally" in context or "script" in context):
                        continue  # Describing executor internals, not manual fallback
                    return False, f"{label} has {desc} as manual instruction (line {i + 1})"
    return True, f"{label} clean"


def check_docs_no_manual_commit_fallback(repo_root: Path) -> tuple[bool, str]:
    """INV-5: protocol docs must not present manual commit/merge as normal path.

    Checks repo-tracked CLAUDE.md only. External Claude memory is not a repo artifact
    and should not be a hard validation gate dependency.
    """
    failures: list[str] = []

    # Check repo-tracked protocol docs
    protocol_docs = [
        (repo_root / "CLAUDE.md", "CLAUDE.md"),
        (repo_root / "mu" / "tools" / "agents" / "templates" / "meta_bridge_task.txt", "meta_bridge_task.txt"),
    ]
    for doc_path, label in protocol_docs:
        passed, msg = _check_single_doc_no_manual_fallback(doc_path, label)
        if not passed:
            failures.append(msg)

    if failures:
        return False, "; ".join(failures)
    return True, "no manual commit/merge fallback in repo protocol docs"


def check_commit_executor_receipt_authority(repo_root: Path) -> tuple[bool, str]:
    """INV-6: commit_executor step 7 must verify both receipts in the authority chain.

    The corrected receipt-chain model requires step 7 to:
    1. Verify the Phase B handoff receipt for continuity/provenance (it was the
       authority that authorized the commit pipeline to begin).
    2. Read the fresh supervisor receipt (from step 6) for the final commit
       decision — this is the only receipt minted after steps 3-5 mutated staging.

    Both must be present. The supervisor receipt is the commit-decision authority.
    The handoff receipt is the provenance proof that Phase B authorized entry.
    """
    path = repo_root / "mu" / "tools" / "executors" / "commit_executor.py"
    if not path.exists():
        return True, "commit_executor.py not found (skip)"
    src = path.read_text(encoding="utf-8")

    # Step 7 section: look for the receipt file sources
    in_step7 = False
    uses_supervisor_path = False
    uses_handoff_path = False
    for line in src.splitlines():
        if "Step 7" in line and "validate_receipt" in line:
            in_step7 = True
        if in_step7 and "Step 8" in line:
            break
        if in_step7:
            stripped = line.strip()
            # Check what paths are used to open receipts
            if "receipt_path_from_supervisor" in stripped and ("repo_root" in stripped or "receipt_file" in stripped):
                uses_supervisor_path = True
            if 'handoff["pre_commit_receipt_path"]' in stripped or "handoff['pre_commit_receipt_path']" in stripped:
                if not stripped.startswith("#"):
                    uses_handoff_path = True

    if uses_supervisor_path and uses_handoff_path:
        return True, "commit_executor step 7 verifies both receipts (handoff provenance + supervisor authority)"
    if uses_supervisor_path and not uses_handoff_path:
        return False, "commit_executor step 7 reads only supervisor receipt (missing handoff provenance check)"
    if uses_handoff_path and not uses_supervisor_path:
        return False, "commit_executor step 7 reads only handoff receipt (missing supervisor authority)"
    return False, "commit_executor step 7 receipt source could not be determined"


ALL_CHECKS = [
    ("INV-1: implementer-not-review-mode", check_implementer_not_review_mode),
    ("INV-2: bridge-loop-reimplements", check_bridge_loop_reinvokes_implementer),
    ("INV-3: receipt-writer-per-invocation", check_receipt_writer_returns_per_invocation),
    ("INV-4: client-no-heuristic", check_client_no_heuristic_discovery),
    ("INV-5: docs-no-manual-fallback", check_docs_no_manual_commit_fallback),
    ("INV-6: commit-receipt-authority-chain", check_commit_executor_receipt_authority),
]


def run_all(repo_root: Path, changed_files: list[str] | None = None, verbose: bool = False) -> tuple[list[dict], bool]:
    """Run all control-surface invariant checks.

    If changed_files is provided and none are control-surface files,
    all checks pass (not applicable).

    Returns (results, all_passed).
    """
    if changed_files is not None and not _touches_control_surface(changed_files):
        return [{"name": "control_surface_skip", "passed": True, "message": "No control-surface files touched"}], True

    results = []
    for name, check_fn in ALL_CHECKS:
        passed, message = check_fn(repo_root)
        results.append({"name": name, "passed": passed, "message": message})
        if verbose:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}: {message}")

    all_passed = all(r["passed"] for r in results)
    return results, all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Phase B control-surface invariants")
    parser.add_argument("--files", nargs="*", help="Changed files (skip if none are control-surface)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("Not in a git repo", file=sys.stderr)
        return 1

    results, all_passed = run_all(repo_root, args.files, verbose=args.verbose)

    if args.json:
        print(json.dumps({"results": results, "all_passed": all_passed}, indent=2))
    else:
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"[{status}] {r['name']}: {r['message']}")
        print(f"\n{'All invariants hold.' if all_passed else 'INVARIANT VIOLATIONS DETECTED.'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
