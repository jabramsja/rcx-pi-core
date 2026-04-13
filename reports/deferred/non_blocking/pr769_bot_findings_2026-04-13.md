# PR #769 Bot Findings — False Positives (2026-04-13) [CLOSED]

Triage status: CLOSED (2026-04-13). Both findings confirmed as false positives
with empirical evidence. No code change needed.

## P2: Guard descendant snapshot (executor_dispatch.py:978)

**Bot claim:** `process_descendants` "only suppresses CalledProcessError" so if `ps` fails with another error, cleanup is skipped.

**Evidence it's a false positive:** The CALL SITE at `executor_dispatch.py:978-981` wraps with `try: ... except Exception: pre_kill_descendants = set()`. `except Exception` catches ALL runtime errors including `FileNotFoundError`/`OSError`. The bot analyzed the HELPER internally but missed the guard at the call site.

**Verified:** `gh pr diff 769` shows `+try: / +pre_kill_descendants = process_descendants(...) / +except Exception: / +pre_kill_descendants = set()`.

**Pipeline impact verification:**
- File: `executor_dispatch.py` — YES, affects executors (timeout kill path in `_run_executor_in_group`)
- Silent regression risk: NO — the `except Exception` at the call site ensures cleanup ALWAYS runs regardless of what `process_descendants` throws. The kill sequence (`os.killpg` → descendant kill → `terminate_process_tree` → `proc.kill`) executes unconditionally after the try/except block.
- Verified via: `gh pr diff 769` showing the guard in the pushed commit

**Action:** No code change needed. Deferred with evidence.

## P1: Match repo-relative artifact paths (artifact-edit-gate.sh:63)

**Bot claim:** "The artifact matcher only uses patterns prefixed with `*/`" so repo-relative paths bypass the gate.

**Evidence it's a false positive:** The pushed code at lines 61-64 already includes BOTH forms:
- `*/reports/control_plane/*|reports/control_plane/*`
- `*/.agent_bus/*|.agent_bus/*`
- `*/.scratch/*|.scratch/*`
- `*/post_merge_package.json|post_merge_package.json`

Line 58 comment: "Match both absolute (*/reports/...) and root-relative (reports/...) paths."

**Verified:** `gh pr diff 769 | grep "Artifact detection" -A 10` confirms both pattern forms present.

**Pipeline impact verification:**
- File: `artifact-edit-gate.sh` — YES, this is a PreToolUse:Edit hook
- Silent regression risk: NO — empirical test of all 8 path forms (repo-relative and absolute for all 4 artifact types) returned `IS_ARTIFACT=true` for every case. Test run:
  - `reports/control_plane/test.md` → true
  - `/absolute/path/reports/control_plane/test.md` → true
  - `.agent_bus/executors/handoff.json` → true
  - `/tmp/worktree/.agent_bus/meta/receipt.json` → true
  - `.scratch/output.txt` → true
  - `/tmp/worktree/.scratch/log.txt` → true
  - `post_merge_package.json` → true
  - `/tmp/worktree/post_merge_package.json` → true
- Verified via: bash case-statement reproduction with all path variants

**Action:** No code change needed. Deferred with evidence.
