# Session Handoff — 2026-04-06 (second session)

## PRs Created This Session

| PR | Branch | Status | Content |
|----|--------|--------|---------|
| #738 | recovery-tier3-wiring-v2-2026-04-06 | CI pending (force-pushed with tracker note fix) | 8-layer denylist, executor governance fixes, bridge adapter JSONL fix |
| #739 | recovery-tier3-remaining-2026-04-06 | CI failed (L4 checker) | CLAUDE.md split (238→56), 6 conditional rule files, test updates |

## Instruction Architecture Overhaul (session-only + persistent)

**Persistent (survive sessions):**
- Output style: `~/.claude/output-styles/rcx-adversarial.md` (`keep-coding-instructions: false`)
- Shell alias: `~/.bashrc` — `--append-system-prompt-file ~/.claude/hard-rules.txt`
- SessionStart hook: `.claude/settings.local.json` — reinjects hard-rules.txt + MEMORY.md
- Rules files: `.claude/rules/` — 6 conditional rule files
- CLAUDE.md: 56 lines (lean core)
- Memory: `feedback_instruction_architecture.md` — governs where new rules go

**Reviewer swap (temporary):**
- All reviewers changed from Codex to Claude opus 4.6 max
- Config: `executor_config.json` + `meta_bridge_supervisor.py` (2 adapter_name lines)
- Backups: `executor_config.json.codex_backup`, `meta_bridge_supervisor.py.codex_backup`
- Restore: `cp mu/tools/executors/executor_config.json.codex_backup mu/tools/executors/executor_config.json && cp mu/tools/agents/meta_bridge_supervisor.py.codex_backup mu/tools/agents/meta_bridge_supervisor.py`

## Executor Governance Fixes (in PR #738)

12 bugs found in executor pipeline that caused repeated NEEDS_PHASE_B:
1. Tracked packet Status never updated from Phase A to COMPLETED
2. indicator_artifact_ref speculative, not reconciled with actual indicator
3. Empty evidence_handles in phase_b supervisor package
4. scope_items not passed to commit_executor handoff
5. evidence_handles not passed to commit_executor handoff
6. bridge_status missing total_rounds
7. Deferred packet lacks governance metadata header
8. Double supervisor invocation with divergent packages (ROOT CAUSE — not fully fixed)
9. Tracker note frozen before indicator exists
10. bridge_status missing total_rounds in handoff
11. Deferred packet lacks governance metadata
12. Count mismatches in evidence_delta

Bugs 1-7,9-11 fixed. Bug 8 (double supervisor) partially mitigated but not eliminated.

## Known Issues

1. L4 tracker note format: the commit executor Step 3 "repair" can break the bold-title format that the L4 checker requires. The note needs `**bold title**` after the wave_id.
2. Supervisor NEEDS_PHASE_B loop: even with governance fixes, the supervisor on historical multi-round waves finds accumulated staleness. Future waves should converge faster.
3. PR #739 CI failure: same L4 checker issue (CLAUDE.md split branch doesn't have the tracker note fix)

## Main Repo Dirty Files

14 uncommitted changes from previous sessions (already merged via PRs #734-737):
- mu/tools/executors/executor_dispatch.py, recovery_gate.py, phase_b_executor.py
- mu/tools/agents/bridge_adapters.py, meta_bridge_supervisor.py
- mu/tools/observability/*.sh
- Plus reviewer swap (executor_config.json, meta_bridge_supervisor.py)
