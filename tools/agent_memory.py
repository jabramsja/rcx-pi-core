#!/usr/bin/env python3
"""
Agent Memory - Store and retrieve agent findings across sessions.

Stores findings in .agent_memory/ directory as JSON files.

Features:
    - Finding storage with severity, file, line tracking
    - Resolution tracking (confirmed/false_positive) for accuracy measurement
    - Accuracy scores per agent based on resolution data
    - File risk scores based on historical findings
    - Past findings injection for agent prompts
    - Pattern library for institutional knowledge

Usage:
    # Store a finding
    python tools/agent_memory.py store verifier "Missing @host_* markers" --file eval_seed.py --severity high

    # List all findings
    python tools/agent_memory.py list

    # Confirm a finding was accurate
    python tools/agent_memory.py confirm 42

    # Mark a finding as false positive
    python tools/agent_memory.py false-positive 42

    # Show accuracy scores per agent
    python tools/agent_memory.py accuracy

    # Show risk score for a file
    python tools/agent_memory.py risk rcx_pi/selfhost/step_mu.py

    # Get context for agent prompt injection
    python tools/agent_memory.py context rcx_pi/selfhost/step_mu.py

    # Pattern library
    python tools/agent_memory.py pattern add "unmarked isinstance" --always-real
    python tools/agent_memory.py pattern list
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

if os.name == "nt":
    import msvcrt
else:
    import fcntl

MEMORY_DIR = Path(".agent_memory")


@contextmanager
def _exclusive_lock(lock_file):
    """Cross-platform exclusive file lock for lock sidecar files."""
    if os.name == "nt":
        # Windows msvcrt.locking() locks a byte range from current file position.
        lock_file.seek(0)
        lock_file.write("0")
        lock_file.flush()
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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


def get_patterns_file() -> Path:
    """Get the path to the patterns file."""
    ensure_memory_dir()
    return MEMORY_DIR / "patterns.json"


def load_findings() -> list[dict]:
    """Load all findings from disk."""
    path = get_findings_file()
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_findings(findings: list[dict]):
    """Save findings to disk with file locking to prevent race conditions."""
    path = get_findings_file()
    # Open with 'r+' or create, then lock BEFORE truncating to prevent race
    # Use a lock file to avoid truncation before lock acquired
    lock_path = path.with_suffix('.lock')
    with open(lock_path, 'w') as lock_file:
        with _exclusive_lock(lock_file):
            # Now safe to write the actual file
            content = json.dumps(findings, indent=2, default=str)
            path.write_text(content)


def load_patterns() -> list[dict]:
    """Load patterns from disk."""
    path = get_patterns_file()
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_patterns(patterns: list[dict]):
    """Save patterns to disk with file locking to prevent race conditions."""
    path = get_patterns_file()
    lock_path = path.with_suffix('.lock')
    with open(lock_path, 'w') as lock_file:
        with _exclusive_lock(lock_file):
            content = json.dumps(patterns, indent=2, default=str)
            path.write_text(content)


def store_finding(
    agent: str,
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    severity: str = "info",
    fixed: bool = False,
    pr: Optional[int] = None,
):
    """Store a new finding.

    Fields:
        - resolution: None (pending), "confirmed", "false_positive"
        - resolved_at: timestamp when resolution was set
        - resolved_by: who resolved it (human or agent name)
    """
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
        "resolution": None,  # None, "confirmed", "false_positive"
        "resolved_at": None,
        "resolved_by": None,
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
    resolution: Optional[str] = None,
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
    if resolution is not None:
        findings = [f for f in findings if f.get("resolution") == resolution]

    # Sort by timestamp descending
    findings = sorted(findings, key=lambda f: f.get("timestamp", ""), reverse=True)

    # Apply limit
    findings = findings[:limit]

    if not findings:
        print("No findings match the criteria.")
        return

    print(f"═══ Agent Findings ({len(findings)} shown) ═══\n")

    for f in findings:
        # Status indicators
        if f.get("resolution") == "confirmed":
            status = "✓✓"  # Double check = confirmed real
        elif f.get("resolution") == "false_positive":
            status = "✗"   # X = false positive
        elif f.get("fixed"):
            status = "✓"   # Single check = fixed
        else:
            status = "○"   # Open circle = pending

        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}.get(
            f.get("severity", "info"), "⚪"
        )

        resolution_str = ""
        if f.get("resolution"):
            resolution_str = f" [{f['resolution']}]"

        print(f"{status} #{f['id']} [{f['agent']}] {severity_icon} {f['severity']}{resolution_str}")
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


def resolve_finding(finding_id: int, resolution: str, resolved_by: str = "human"):
    """Set the resolution status of a finding.

    Args:
        finding_id: ID of the finding
        resolution: "confirmed" or "false_positive"
        resolved_by: who resolved it (default: "human")
    """
    if resolution not in ("confirmed", "false_positive"):
        print(f"❌ Invalid resolution: {resolution}. Use 'confirmed' or 'false_positive'")
        return

    findings = load_findings()

    for f in findings:
        if f.get("id") == finding_id:
            f["resolution"] = resolution
            f["resolved_at"] = datetime.now().isoformat()
            f["resolved_by"] = resolved_by
            save_findings(findings)

            icon = "✓✓" if resolution == "confirmed" else "✗"
            print(f"{icon} Marked finding #{finding_id} as {resolution}")
            return

    print(f"❌ Finding #{finding_id} not found")


def show_accuracy():
    """Show accuracy scores per agent based on resolution data."""
    findings = load_findings()

    # Only consider findings with resolutions
    resolved = [f for f in findings if f.get("resolution")]

    if not resolved:
        print("No resolved findings yet. Use 'confirm' or 'false-positive' to mark findings.")
        return

    # Group by agent
    by_agent: dict[str, dict] = {}
    for f in resolved:
        agent = f.get("agent", "unknown")
        if agent not in by_agent:
            by_agent[agent] = {"confirmed": 0, "false_positive": 0, "total": 0}

        by_agent[agent]["total"] += 1
        by_agent[agent][f["resolution"]] += 1

    print(f"═══ Agent Accuracy Scores ═══\n")
    print(f"{'Agent':<20} {'Confirmed':>10} {'False Pos':>10} {'Accuracy':>10}")
    print("-" * 54)

    total_confirmed = 0
    total_fp = 0

    for agent, stats in sorted(by_agent.items(), key=lambda x: x[1]["total"], reverse=True):
        confirmed = stats["confirmed"]
        false_pos = stats["false_positive"]
        total = stats["total"]
        accuracy = (confirmed / total * 100) if total > 0 else 0

        total_confirmed += confirmed
        total_fp += false_pos

        # Color code accuracy
        if accuracy >= 80:
            acc_str = f"{accuracy:.0f}% 🟢"
        elif accuracy >= 60:
            acc_str = f"{accuracy:.0f}% 🟡"
        else:
            acc_str = f"{accuracy:.0f}% 🔴"

        print(f"{agent:<20} {confirmed:>10} {false_pos:>10} {acc_str:>10}")

    print("-" * 54)
    total = total_confirmed + total_fp
    overall_accuracy = (total_confirmed / total * 100) if total > 0 else 0
    print(f"{'OVERALL':<20} {total_confirmed:>10} {total_fp:>10} {overall_accuracy:.0f}%")
    print(f"\n{total} findings resolved out of {len(findings)} total.")


def get_file_risk_score(file_path: str, days: int = 30) -> dict:
    """Calculate risk score for a file based on historical findings.

    Returns dict with:
        - score: weighted score (critical=5, high=3, medium=2, low=1)
        - finding_count: total findings
        - confirmed_count: confirmed findings
        - severity_breakdown: counts by severity
        - agents: which agents found issues
    """
    findings = load_findings()
    cutoff = datetime.now() - timedelta(days=days)

    # Filter to file and recent
    # Security: Use path normalization for proper matching, not loose substrings
    file_findings = []
    try:
        query_path = Path(file_path).resolve()
    except (OSError, ValueError):
        query_path = None

    for f in findings:
        if not f.get("file"):
            continue

        # Match by normalized absolute path (preferred) or basename match (fallback)
        finding_file = f.get("file", "")
        try:
            finding_path = Path(finding_file).resolve()
            if query_path and finding_path == query_path:
                pass  # Exact match - include
            elif Path(file_path).name == Path(finding_file).name:
                pass  # Same filename - include (useful for relative paths)
            else:
                continue  # No match
        except (OSError, ValueError):
            # Fallback: exact string match only
            if file_path != finding_file:
                continue
        try:
            ts = datetime.fromisoformat(f.get("timestamp", ""))
            if ts > cutoff:
                file_findings.append(f)
        except (ValueError, TypeError):
            pass

    if not file_findings:
        return {
            "score": 0,
            "finding_count": 0,
            "confirmed_count": 0,
            "severity_breakdown": {},
            "agents": set(),
            "recent_issues": [],
        }

    # Calculate metrics
    # Note: info gets weight 0.5 so files with only info findings still get context
    severity_weights = {"critical": 5, "high": 3, "medium": 2, "low": 1, "info": 0.5}
    severity_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    agents = set()
    confirmed_count = 0
    score = 0

    for f in file_findings:
        sev = f.get("severity", "info")
        severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
        agents.add(f.get("agent", "unknown"))

        if f.get("resolution") == "confirmed":
            confirmed_count += 1
            # Confirmed findings count double
            score += severity_weights.get(sev, 0) * 2
        elif f.get("resolution") != "false_positive":
            # Unresolved findings count normal
            score += severity_weights.get(sev, 0)
        # False positives don't count

    # Get recent issues for context
    recent_issues = []
    for f in sorted(file_findings, key=lambda x: x.get("timestamp", ""), reverse=True)[:5]:
        if f.get("resolution") != "false_positive":
            recent_issues.append({
                "message": f.get("message", "")[:80],
                "severity": f.get("severity", "info"),
                "agent": f.get("agent", "unknown"),
                "confirmed": f.get("resolution") == "confirmed",
            })

    return {
        "score": score,
        "finding_count": len(file_findings),
        "confirmed_count": confirmed_count,
        "severity_breakdown": severity_breakdown,
        "agents": agents,
        "recent_issues": recent_issues,
    }


def show_file_risk(file_path: str, days: int = 30):
    """Display risk score for a file."""
    risk = get_file_risk_score(file_path, days)

    print(f"═══ Risk Score: {file_path} ═══\n")

    if risk["score"] == 0:
        print(f"No findings in last {days} days. Risk: LOW 🟢")
        return

    # Risk level
    score = risk["score"]
    if score >= 20:
        level = "CRITICAL 🔴"
    elif score >= 10:
        level = "HIGH 🟠"
    elif score >= 5:
        level = "MEDIUM 🟡"
    else:
        level = "LOW 🟢"

    print(f"Risk Score: {score} ({level})")
    print(f"Findings: {risk['finding_count']} ({risk['confirmed_count']} confirmed)")
    print(f"Agents: {', '.join(sorted(risk['agents']))}")
    print()

    # Severity breakdown
    print("Severity Breakdown:")
    for sev in ["critical", "high", "medium", "low", "info"]:
        count = risk["severity_breakdown"].get(sev, 0)
        if count:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}[sev]
            print(f"  {icon} {sev}: {count}")

    # Recent issues
    if risk["recent_issues"]:
        print("\nRecent Issues:")
        for issue in risk["recent_issues"]:
            conf = " ✓✓" if issue["confirmed"] else ""
            print(f"  - [{issue['agent']}] {issue['message']}{conf}")


def _sanitize_for_prompt(text: str, max_len: int = 60) -> str:
    """Sanitize text before injecting into agent prompts.

    Prevents prompt injection attacks via malicious finding messages.
    Security: Includes Unicode normalization to prevent lookalike bypasses.
    """
    import unicodedata
    if not text:
        return ""
    # Unicode normalization first - converts lookalikes (Greek omicron → Latin o)
    text = unicodedata.normalize('NFKC', text)
    # Truncate
    text = text[:max_len]
    # Escape markdown/prompt injection patterns
    text = (text
            .replace('\\', '\\\\')
            .replace('`', '\\`')
            .replace('---', '\\-\\-\\-')
            .replace('```', '\\`\\`\\`')
            .replace('\n', ' ')
            .replace('\r', ' '))
    # Remove any instruction-like patterns (matched with run_skeptic.py patterns)
    for pattern in ['ignore previous', 'disregard', 'new instructions', 'system prompt', 'forget everything']:
        text = text.replace(pattern.lower(), '[REDACTED]')
        text = text.replace(pattern.upper(), '[REDACTED]')
        text = text.replace(pattern.title(), '[REDACTED]')
    return text


def get_context_for_files(files: list[str], days: int = 30) -> str:
    """Generate context string for agent prompt injection.

    This is injected into agent prompts to give them awareness of past findings.
    Security: All text is sanitized to prevent prompt injection.
    """
    if not files:
        return ""

    context_parts = []

    for file_path in files:
        risk = get_file_risk_score(file_path, days)

        if risk["score"] == 0:
            continue

        # Build context for this file (sanitize file path too)
        safe_path = _sanitize_for_prompt(file_path, max_len=200)
        file_context = f"\n📋 MEMORY: {safe_path}"
        file_context += f"\n   Risk Score: {risk['score']} ({risk['finding_count']} findings, {risk['confirmed_count']} confirmed)"

        if risk["recent_issues"]:
            file_context += "\n   Previous issues (check for regressions):"
            for issue in risk["recent_issues"][:3]:
                conf = " [CONFIRMED]" if issue["confirmed"] else ""
                # Sanitize message to prevent prompt injection
                safe_message = _sanitize_for_prompt(issue['message'], max_len=60)
                safe_agent = _sanitize_for_prompt(issue['agent'], max_len=20)
                file_context += f"\n   - [{safe_agent}] {safe_message}{conf}"

        context_parts.append(file_context)

    if not context_parts:
        return ""

    header = "\n" + "=" * 60
    header += "\n## AGENT MEMORY CONTEXT"
    header += "\nThe following files have historical findings. Check for regressions."
    header += "\n" + "=" * 60

    return header + "\n".join(context_parts) + "\n"


def show_context(files: list[str], days: int = 30):
    """Display context that would be injected for these files."""
    context = get_context_for_files(files, days)

    if not context:
        print("No historical findings for these files.")
        return

    print("Context that will be injected into agent prompts:")
    print(context)


# =============================================================================
# Pattern Library
# =============================================================================

def add_pattern(
    pattern: str,
    description: str = "",
    always_real: bool = False,
    usually_false: bool = False,
    agent: Optional[str] = None,
):
    """Add a pattern to the library.

    Patterns are text snippets that indicate known issues.
    - always_real: This pattern is always a real issue (reduces false negatives)
    - usually_false: This pattern is usually a false positive (reduces noise)
    """
    patterns = load_patterns()

    new_pattern = {
        "id": len(patterns) + 1,
        "pattern": pattern,
        "description": description,
        "always_real": always_real,
        "usually_false": usually_false,
        "agent": agent,
        "created_at": datetime.now().isoformat(),
        "match_count": 0,
        "confirmed_matches": 0,
    }

    patterns.append(new_pattern)
    save_patterns(patterns)

    tag = "[ALWAYS REAL]" if always_real else "[USUALLY FALSE]" if usually_false else ""
    print(f"✓ Added pattern #{new_pattern['id']}: '{pattern}' {tag}")
    return new_pattern


def list_patterns():
    """List all patterns in the library."""
    patterns = load_patterns()

    if not patterns:
        print("No patterns in library. Use 'pattern add' to add patterns.")
        return

    print(f"═══ Pattern Library ({len(patterns)} patterns) ═══\n")

    for p in patterns:
        tag = ""
        if p.get("always_real"):
            tag = " 🔴 ALWAYS REAL"
        elif p.get("usually_false"):
            tag = " 🟡 USUALLY FALSE"

        agent_str = f" [{p['agent']}]" if p.get("agent") else ""

        print(f"#{p['id']}{agent_str}: \"{p['pattern']}\"{tag}")
        if p.get("description"):
            print(f"   {p['description']}")
        print(f"   Matches: {p.get('match_count', 0)} ({p.get('confirmed_matches', 0)} confirmed)")
        print()


def match_patterns(text: str) -> list[dict]:
    """Find patterns that match in the given text.

    Returns list of matching patterns with their classifications.
    """
    patterns = load_patterns()
    matches = []

    for p in patterns:
        if p["pattern"].lower() in text.lower():
            matches.append(p)

    return matches


def get_pattern_context() -> str:
    """Get pattern library context for agent prompts.

    Security: All pattern data is sanitized to prevent prompt injection.
    """
    patterns = load_patterns()

    if not patterns:
        return ""

    always_real = [p for p in patterns if p.get("always_real")]
    usually_false = [p for p in patterns if p.get("usually_false")]

    if not always_real and not usually_false:
        return ""

    context = "\n## PATTERN LIBRARY\n"

    if always_real:
        context += "\n🔴 ALWAYS REAL (flag these without hesitation):\n"
        for p in always_real:
            # Security: Sanitize pattern and description before injection
            safe_pattern = _sanitize_for_prompt(p.get('pattern', ''), max_len=100)
            context += f"  - \"{safe_pattern}\""
            if p.get("description"):
                safe_desc = _sanitize_for_prompt(p['description'], max_len=200)
                context += f" - {safe_desc}"
            context += "\n"

    if usually_false:
        context += "\n🟡 USUALLY FALSE POSITIVE (skip unless strong evidence):\n"
        for p in usually_false:
            # Security: Sanitize pattern and description before injection
            safe_pattern = _sanitize_for_prompt(p.get('pattern', ''), max_len=100)
            context += f"  - \"{safe_pattern}\""
            if p.get("description"):
                safe_desc = _sanitize_for_prompt(p['description'], max_len=200)
                context += f" - {safe_desc}"
            context += "\n"

    return context


# =============================================================================
# Existing Functions (with resolution support)
# =============================================================================

def check_regressions(files: Optional[list[str]] = None):
    """Check if any fixed findings might have regressed."""
    findings = load_findings()

    # Get fixed findings (exclude false positives)
    fixed = [f for f in findings if f.get("fixed") and f.get("resolution") != "false_positive"]

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
            conf = " [CONFIRMED]" if f.get("resolution") == "confirmed" else ""
            print(f"   ⚠️  #{f['id']}: {f['message'][:60]}...{conf}")
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


def show_hotspots(limit: int = 10, include_fixed: bool = False):
    """Show files with the most findings (hotspots)."""
    findings = load_findings()

    if not include_fixed:
        findings = [f for f in findings if not f.get("fixed")]

    # Exclude false positives
    findings = [f for f in findings if f.get("resolution") != "false_positive"]

    if not findings:
        print("No findings in memory.")
        return

    # Group by file
    by_file: dict[str, dict] = {}
    for f in findings:
        file_path = f.get("file", "unknown")
        if file_path not in by_file:
            by_file[file_path] = {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
                "confirmed": 0,
                "agents": set(),
            }

        by_file[file_path]["total"] += 1
        severity = f.get("severity", "info")
        by_file[file_path][severity] = by_file[file_path].get(severity, 0) + 1
        by_file[file_path]["agents"].add(f.get("agent", "unknown"))
        if f.get("resolution") == "confirmed":
            by_file[file_path]["confirmed"] += 1

    # Sort by weighted score (critical=5, high=3, medium=2, low=1, info=0)
    # Confirmed findings count double
    def score(stats):
        base = (stats["critical"] * 5 + stats["high"] * 3 +
                stats["medium"] * 2 + stats["low"] * 1)
        # Boost for confirmed issues
        return base + stats["confirmed"] * 2

    sorted_files = sorted(by_file.items(), key=lambda x: score(x[1]), reverse=True)

    print(f"═══ Hotspot Report ({len(findings)} findings across {len(by_file)} files) ═══\n")

    # Summary by severity
    total_critical = sum(s["critical"] for s in by_file.values())
    total_high = sum(s["high"] for s in by_file.values())
    total_medium = sum(s["medium"] for s in by_file.values())

    if total_critical or total_high:
        print(f"🔴 Critical: {total_critical}  🟠 High: {total_high}  🟡 Medium: {total_medium}\n")

    print(f"Top {min(limit, len(sorted_files))} hotspots:\n")

    for i, (file_path, stats) in enumerate(sorted_files[:limit], 1):
        # Build severity indicators
        indicators = []
        if stats["critical"]:
            indicators.append(f"🔴{stats['critical']}")
        if stats["high"]:
            indicators.append(f"🟠{stats['high']}")
        if stats["medium"]:
            indicators.append(f"🟡{stats['medium']}")
        if stats["low"]:
            indicators.append(f"🟢{stats['low']}")

        severity_str = " ".join(indicators) if indicators else "⚪ info only"
        agents_str = ", ".join(sorted(stats["agents"]))
        conf_str = f" ({stats['confirmed']} confirmed)" if stats["confirmed"] else ""

        print(f"{i:2}. {file_path}")
        print(f"    {stats['total']} findings{conf_str}  {severity_str}")
        print(f"    Agents: {agents_str}")
        print()

    if len(sorted_files) > limit:
        print(f"... and {len(sorted_files) - limit} more files with findings")


def show_agent_stats():
    """Show statistics by agent."""
    findings = load_findings()

    if not findings:
        print("No findings in memory.")
        return

    # Group by agent
    by_agent: dict[str, dict] = {}
    for f in findings:
        agent = f.get("agent", "unknown")
        if agent not in by_agent:
            by_agent[agent] = {"total": 0, "fixed": 0, "open": 0, "confirmed": 0, "false_pos": 0}

        by_agent[agent]["total"] += 1
        if f.get("fixed"):
            by_agent[agent]["fixed"] += 1
        else:
            by_agent[agent]["open"] += 1

        if f.get("resolution") == "confirmed":
            by_agent[agent]["confirmed"] += 1
        elif f.get("resolution") == "false_positive":
            by_agent[agent]["false_pos"] += 1

    print(f"═══ Agent Statistics ═══\n")
    print(f"{'Agent':<20} {'Total':>8} {'Open':>8} {'Fixed':>8} {'Conf':>8} {'FP':>8}")
    print("-" * 64)

    for agent, stats in sorted(by_agent.items(), key=lambda x: x[1]["total"], reverse=True):
        print(f"{agent:<20} {stats['total']:>8} {stats['open']:>8} {stats['fixed']:>8} {stats['confirmed']:>8} {stats['false_pos']:>8}")

    print("-" * 64)
    total = sum(s["total"] for s in by_agent.values())
    open_count = sum(s["open"] for s in by_agent.values())
    fixed = sum(s["fixed"] for s in by_agent.values())
    confirmed = sum(s["confirmed"] for s in by_agent.values())
    false_pos = sum(s["false_pos"] for s in by_agent.values())
    print(f"{'TOTAL':<20} {total:>8} {open_count:>8} {fixed:>8} {confirmed:>8} {false_pos:>8}")


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
    list_parser.add_argument("--confirmed", action="store_true", help="Show only confirmed")
    list_parser.add_argument("--false-positive", action="store_true", help="Show only false positives")
    list_parser.add_argument("--limit", "-n", type=int, default=50, help="Limit results")

    # Fix command
    fix_parser = subparsers.add_parser("fix", help="Mark a finding as fixed")
    fix_parser.add_argument("id", type=int, help="Finding ID")

    # Confirm command
    confirm_parser = subparsers.add_parser("confirm", help="Confirm a finding was accurate")
    confirm_parser.add_argument("id", type=int, help="Finding ID")

    # False positive command
    fp_parser = subparsers.add_parser("false-positive", help="Mark a finding as false positive")
    fp_parser.add_argument("id", type=int, help="Finding ID")

    # Accuracy command
    subparsers.add_parser("accuracy", help="Show accuracy scores per agent")

    # Risk command
    risk_parser = subparsers.add_parser("risk", help="Show risk score for a file")
    risk_parser.add_argument("file", help="File path")
    risk_parser.add_argument("--days", "-d", type=int, default=30, help="Days to consider")

    # Context command
    context_parser = subparsers.add_parser("context", help="Show context for agent injection")
    context_parser.add_argument("files", nargs="+", help="Files to get context for")
    context_parser.add_argument("--days", "-d", type=int, default=30, help="Days to consider")

    # Check regressions
    regress_parser = subparsers.add_parser("check-regressions", help="Check for regressions")
    regress_parser.add_argument("files", nargs="*", help="Files to check")

    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear old findings")
    clear_parser.add_argument("--days", "-d", type=int, default=30, help="Days to keep")

    # Hotspots command
    hotspot_parser = subparsers.add_parser("hotspots", help="Show files with most findings")
    hotspot_parser.add_argument("--limit", "-n", type=int, default=10, help="Number of files to show")
    hotspot_parser.add_argument("--include-fixed", action="store_true", help="Include fixed findings")

    # Stats command
    subparsers.add_parser("stats", help="Show statistics by agent")

    # Pattern commands
    pattern_parser = subparsers.add_parser("pattern", help="Pattern library commands")
    pattern_sub = pattern_parser.add_subparsers(dest="pattern_command", required=True)

    # Pattern add
    pattern_add = pattern_sub.add_parser("add", help="Add a pattern")
    pattern_add.add_argument("pattern", help="Pattern text to match")
    pattern_add.add_argument("--description", "-d", default="", help="Description")
    pattern_add.add_argument("--always-real", action="store_true", help="Mark as always a real issue")
    pattern_add.add_argument("--usually-false", action="store_true", help="Mark as usually false positive")
    pattern_add.add_argument("--agent", "-a", help="Specific agent this pattern applies to")

    # Pattern list
    pattern_sub.add_parser("list", help="List all patterns")

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
        resolution = None
        if args.confirmed:
            resolution = "confirmed"
        elif args.false_positive:
            resolution = "false_positive"
        list_findings(
            agent=args.agent,
            file=args.file,
            severity=args.severity,
            fixed=fixed,
            resolution=resolution,
            limit=args.limit,
        )
    elif args.command == "fix":
        mark_fixed(args.id)
    elif args.command == "confirm":
        resolve_finding(args.id, "confirmed")
    elif args.command == "false-positive":
        resolve_finding(args.id, "false_positive")
    elif args.command == "accuracy":
        show_accuracy()
    elif args.command == "risk":
        show_file_risk(args.file, args.days)
    elif args.command == "context":
        show_context(args.files, args.days)
    elif args.command == "check-regressions":
        check_regressions(args.files if args.files else None)
    elif args.command == "clear":
        clear_old(args.days)
    elif args.command == "hotspots":
        show_hotspots(limit=args.limit, include_fixed=args.include_fixed)
    elif args.command == "stats":
        show_agent_stats()
    elif args.command == "pattern":
        if args.pattern_command == "add":
            add_pattern(
                pattern=args.pattern,
                description=args.description,
                always_real=args.always_real,
                usually_false=args.usually_false,
                agent=args.agent,
            )
        elif args.pattern_command == "list":
            list_patterns()


if __name__ == "__main__":
    main()
