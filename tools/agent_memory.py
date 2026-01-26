#!/usr/bin/env python3
"""
Agent Memory - Store and retrieve agent findings across sessions.

Stores findings in .agent_memory/ directory as JSON files.

Usage:
    # Store a finding
    python tools/agent_memory.py store verifier "Missing @host_* markers" --file eval_seed.py --severity high

    # List all findings
    python tools/agent_memory.py list

    # List findings for a file
    python tools/agent_memory.py list --file eval_seed.py

    # Check for regressions (previously-fixed issues reappearing)
    python tools/agent_memory.py check-regressions

    # Clear old findings
    python tools/agent_memory.py clear --before 7d
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path(".agent_memory")


def ensure_memory_dir():
    """Create the memory directory if it doesn't exist."""
    MEMORY_DIR.mkdir(exist_ok=True)
    gitignore = MEMORY_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Agent memory is local\n*\n!.gitignore\n")


def get_findings_file() -> Path:
    """Get the path to the findings file."""
    ensure_memory_dir()
    return MEMORY_DIR / "findings.json"


def load_findings() -> list[dict]:
    """Load all findings from disk."""
    path = get_findings_file()
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_findings(findings: list[dict]):
    """Save findings to disk."""
    path = get_findings_file()
    path.write_text(json.dumps(findings, indent=2, default=str))


def store_finding(
    agent: str,
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    severity: str = "info",
    fixed: bool = False,
    pr: Optional[int] = None,
):
    """Store a new finding."""
    findings = load_findings()

    finding = {
        "id": len(findings) + 1,
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "message": message,
        "file": file,
        "line": line,
        "severity": severity,
        "fixed": fixed,
        "pr": pr,
    }

    findings.append(finding)
    save_findings(findings)

    print(f"✓ Stored finding #{finding['id']}: {message[:50]}...")
    return finding


def list_findings(
    agent: Optional[str] = None,
    file: Optional[str] = None,
    severity: Optional[str] = None,
    fixed: Optional[bool] = None,
    limit: int = 50,
):
    """List findings with optional filters."""
    findings = load_findings()

    # Apply filters
    if agent:
        findings = [f for f in findings if f.get("agent") == agent]
    if file:
        findings = [f for f in findings if f.get("file") and file in f.get("file")]
    if severity:
        findings = [f for f in findings if f.get("severity") == severity]
    if fixed is not None:
        findings = [f for f in findings if f.get("fixed") == fixed]

    # Sort by timestamp descending
    findings = sorted(findings, key=lambda f: f.get("timestamp", ""), reverse=True)

    # Apply limit
    findings = findings[:limit]

    if not findings:
        print("No findings match the criteria.")
        return

    print(f"═══ Agent Findings ({len(findings)} shown) ═══\n")

    for f in findings:
        status = "✓" if f.get("fixed") else "○"
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}.get(
            f.get("severity", "info"), "⚪"
        )

        print(f"{status} #{f['id']} [{f['agent']}] {severity_icon} {f['severity']}")
        print(f"  {f['message']}")
        if f.get("file"):
            loc = f"{f['file']}"
            if f.get("line"):
                loc += f":{f['line']}"
            print(f"  📍 {loc}")
        print(f"  🕐 {f.get('timestamp', '?')[:19]}")
        if f.get("pr"):
            print(f"  🔗 PR #{f['pr']}")
        print()


def mark_fixed(finding_id: int):
    """Mark a finding as fixed."""
    findings = load_findings()

    for f in findings:
        if f.get("id") == finding_id:
            f["fixed"] = True
            f["fixed_at"] = datetime.now().isoformat()
            save_findings(findings)
            print(f"✓ Marked finding #{finding_id} as fixed")
            return

    print(f"❌ Finding #{finding_id} not found")


def check_regressions(files: Optional[list[str]] = None):
    """Check if any fixed findings might have regressed."""
    findings = load_findings()

    # Get fixed findings
    fixed = [f for f in findings if f.get("fixed")]

    if not fixed:
        print("No fixed findings to check.")
        return

    print(f"═══ Regression Check ═══\n")
    print(f"Checking {len(fixed)} previously-fixed findings...\n")

    # Group by file
    by_file = {}
    for f in fixed:
        file = f.get("file", "unknown")
        if files and not any(pat in file for pat in files):
            continue
        if file not in by_file:
            by_file[file] = []
        by_file[file].append(f)

    for file, findings_for_file in sorted(by_file.items()):
        print(f"📄 {file}")
        for f in findings_for_file:
            print(f"   ⚠️  #{f['id']}: {f['message'][:60]}...")
        print()

    print("Review these files for potential regressions.")


def clear_old(days: int = 30):
    """Clear findings older than specified days."""
    findings = load_findings()
    cutoff = datetime.now() - timedelta(days=days)

    original_count = len(findings)
    findings = [
        f for f in findings
        if datetime.fromisoformat(f.get("timestamp", datetime.now().isoformat())) > cutoff
    ]

    removed = original_count - len(findings)
    save_findings(findings)
    print(f"✓ Removed {removed} findings older than {days} days")


def main():
    parser = argparse.ArgumentParser(description="Agent Memory - Store and retrieve findings")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Store command
    store_parser = subparsers.add_parser("store", help="Store a new finding")
    store_parser.add_argument("agent", help="Agent name (verifier, adversary, etc.)")
    store_parser.add_argument("message", help="Finding message")
    store_parser.add_argument("--file", "-f", help="Related file path")
    store_parser.add_argument("--line", "-l", type=int, help="Line number")
    store_parser.add_argument("--severity", "-s", default="info",
                              choices=["critical", "high", "medium", "low", "info"])
    store_parser.add_argument("--pr", type=int, help="Related PR number")

    # List command
    list_parser = subparsers.add_parser("list", help="List findings")
    list_parser.add_argument("--agent", "-a", help="Filter by agent")
    list_parser.add_argument("--file", "-f", help="Filter by file")
    list_parser.add_argument("--severity", "-s", help="Filter by severity")
    list_parser.add_argument("--fixed", action="store_true", help="Show only fixed")
    list_parser.add_argument("--unfixed", action="store_true", help="Show only unfixed")
    list_parser.add_argument("--limit", "-n", type=int, default=50, help="Limit results")

    # Fix command
    fix_parser = subparsers.add_parser("fix", help="Mark a finding as fixed")
    fix_parser.add_argument("id", type=int, help="Finding ID")

    # Check regressions
    regress_parser = subparsers.add_parser("check-regressions", help="Check for regressions")
    regress_parser.add_argument("files", nargs="*", help="Files to check")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear old findings")
    clear_parser.add_argument("--days", "-d", type=int, default=30, help="Days to keep")

    args = parser.parse_args()

    if args.command == "store":
        store_finding(
            agent=args.agent,
            message=args.message,
            file=args.file,
            line=args.line,
            severity=args.severity,
            pr=args.pr,
        )
    elif args.command == "list":
        fixed = True if args.fixed else (False if args.unfixed else None)
        list_findings(
            agent=args.agent,
            file=args.file,
            severity=args.severity,
            fixed=fixed,
            limit=args.limit,
        )
    elif args.command == "fix":
        mark_fixed(args.id)
    elif args.command == "check-regressions":
        check_regressions(args.files if args.files else None)
    elif args.command == "clear":
        clear_old(args.days)


if __name__ == "__main__":
    main()
