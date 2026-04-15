#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import stat
import subprocess
import sys
from pathlib import Path


LEARNING_MD_REL = Path(".claude") / "rules" / "learning.md"
CAPTURE_HOOK_REL = Path(".claude") / "hooks" / "capture-learning.sh"
LEARNED_PATTERNS_REL = Path(".agent_bus") / "recovery" / "learned_patterns.json"

ENTRY_RE = re.compile(
    r"^-\s*\[(\d{4}-\d{2}-\d{2})\]\s*([A-Z]+)\s*\|\s*fingerprint:\s*`([^`]*)`"
)
FIXED_RE = re.compile(
    r"^-\s*\[(\d{4}-\d{2}-\d{2})\]\s*FIXED\s*\|\s*fingerprint:\s*`([^`]*)`\s*\|\s*action:\s*`([^`]*)`"
)


def _repo_root() -> Path:
    return Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )


def _mode_string(path: Path) -> str:
    try:
        return stat.filemode(path.stat().st_mode)
    except OSError:
        return "missing"


def _load_learning_entries(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    entries: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        fixed_match = FIXED_RE.match(line)
        if fixed_match:
            entries.append(
                {
                    "date": fixed_match.group(1),
                    "category": "FIXED",
                    "fingerprint": fixed_match.group(2),
                }
            )
            continue
        entry_match = ENTRY_RE.match(line)
        if not entry_match or "SUPERSEDED BY:" in line:
            continue
        entries.append(
            {
                "date": entry_match.group(1),
                "category": entry_match.group(2),
                "fingerprint": entry_match.group(3),
            }
        )
    return entries


def _load_pattern_store(path: Path) -> tuple[int, int, str]:
    if not path.exists():
        return 0, 0, "missing"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0, 0, "unreadable"

    patterns = payload.get("patterns", {})
    if not isinstance(patterns, dict):
        return 0, 0, "invalid"

    promoted = 0
    for record in patterns.values():
        if not isinstance(record, dict):
            continue
        tier = record.get("promoted_tier")
        if isinstance(tier, int) and tier <= 2:
            promoted += 1
    return len(patterns), promoted, "present"


def main() -> int:
    repo_root = _repo_root()
    learning_md = repo_root / LEARNING_MD_REL
    capture_hook = repo_root / CAPTURE_HOOK_REL
    learned_patterns = repo_root / LEARNED_PATTERNS_REL

    entries = _load_learning_entries(learning_md)
    dated_entries = [entry for entry in entries if entry.get("date")]
    dated_entries.sort(
        key=lambda entry: (entry.get("date", ""), entry.get("category", "")),
        reverse=True,
    )
    last_date = dated_entries[0]["date"] if dated_entries else "none"

    total_patterns, promoted_patterns, store_status = _load_pattern_store(
        learned_patterns
    )

    print("RCX shared learning snapshot (Codex reuses Claude/pipeline surfaces):")
    print(
        f"  - {LEARNING_MD_REL}: entries={len(entries)} last_date={last_date} perms={_mode_string(learning_md)}"
    )
    print(
        "  - "
        f"{CAPTURE_HOOK_REL}: executable={'yes' if capture_hook.is_file() and capture_hook.stat().st_mode & 0o111 else 'no'} "
        f"perms={_mode_string(capture_hook)}"
    )
    print(
        "  - "
        f"{LEARNED_PATTERNS_REL}: status={store_status} patterns={total_patterns} promoted={promoted_patterns}"
    )
    print(
        "  - Codex carry-over: use the shared Claude/pipeline learning surfaces above; "
        "no separate Codex learning store is required."
    )

    if dated_entries:
        print("  - Recent shared learnings:")
        for entry in dated_entries[:3]:
            fingerprint = entry["fingerprint"][:80]
            print(
                f"    [{entry['date']}] {entry['category']} | fingerprint: {fingerprint}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
