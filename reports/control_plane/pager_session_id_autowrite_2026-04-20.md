Phase-A-Lock: LOCKED

# Pager orchestrator session id auto-write via SessionStart hook — 2026-04-20

wave_id: pager-session-id-autowrite-2026-04-20
phase: A
task_id: [NEXT-CODEX-POST-REDTEAM]
wave_class: L4_ENABLER
target_gate_id: G8

## Problem statement

`mu/tools/observability/pipeline_agent_pager.py:656-693 _read_orchestrator_session_id()` reads a file at `<repo_root>/.agent_bus/observability/orchestrator_session_id` (constant `ORCHESTRATOR_SESSION_ID_PATH` at `pipeline_agent_pager.py:51`) to resolve the current Claude Code orchestrator session for `claude --resume <id>` deterministic dispatch. The docstring at `:659-668` explicitly states: "The file at `ORCHESTRATOR_SESSION_ID_PATH` is authored by a follow-on orchestrator-side writer and is absent in the current repo state." Verified 2026-04-20: file was missing in all 7 live worktrees during recent mechanization sessions, so the pager fell back to plain `claude -p` — spawning a fresh session that never woke the orchestrator that started the pipeline. The read path already tolerates every absent/malformed case with `None` return, so this wave is a pure writer addition with no reader contract change.

This wave closes the gap by adding a `SessionStart` hook that writes the active `session_id` (from the hook's JSON stdin, per [Claude Code hooks docs](https://code.claude.com/docs/en/hooks.md)) to `$CLAUDE_PROJECT_DIR/.agent_bus/observability/orchestrator_session_id` on every session start (all 4 sources: `startup`, `resume`, `clear`, `compact`). Result: subsequent pager dispatch events in the same repo root read a current session id and invoke `claude --resume <id>` deterministically instead of `claude -p`, waking the orchestrator session that the founder is actually attending.

## Scope (files in scope)

- `.claude/hooks/session-start.sh` (new, ~55 LOC + header) — SessionStart hook that reads JSON on stdin, extracts `.session_id` via `jq -r`, validates it contains no whitespace, and atomically writes it (via `.tmp + mv -f`) to `$CLAUDE_PROJECT_DIR/.agent_bus/observability/orchestrator_session_id`. Fail-OPEN on every error (missing jq, missing stdin, empty session_id, whitespace in session_id, missing `$CLAUDE_PROJECT_DIR`, mkdir failure, write failure) — a missing or corrupt file is tolerated by the reader, so we never block session start on pager-wiring mechanics. Pipeline-subprocess bypass `RCX_PIPELINE_SESSION=1 && exit 0` at line 2 mirrors existing hook pattern (per `.claude/rules/learning.md` 2026-04-12 `RCX_PIPELINE_SESSION env var bypass` entry).
- `.claude/settings.json` — append `$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh` (timeout 3) to the existing `SessionStart` matcher's `hooks` array. Preserve the existing hard-rules + MEMORY.md injection hook unchanged. No new matcher entry — attach to the same source-less (all-sources) matcher.
- `mu/tests/tools/test_pipeline_agent_pager.py` — 1 new regression test `test_session_start_hook_writes_orchestrator_session_id_for_pager_read` that pipes a sample JSON payload into the hook with `CLAUDE_PROJECT_DIR=<tmp>` and asserts (i) the file at `<tmp>/.agent_bus/observability/orchestrator_session_id` exists with the session_id as content (stripped), (ii) `_read_orchestrator_session_id(tmp)` on that file returns the same session_id. Integration test — exercises both the hook and the pager's reader end-to-end. No mocking.

## Constraints (out of scope)

- Any change to `_read_orchestrator_session_id()` at `pipeline_agent_pager.py:656` or `ORCHESTRATOR_SESSION_ID_PATH` at `pipeline_agent_pager.py:51` — those are the reader contract; this wave is writer-only.
- Dispatcher-side pre-step that writes per-worktree session IDs (another option described in memory `project_next_wave_context.md:24`) — deferred. SessionStart hook covers the primary case (main repo + interactive sessions). Worktree sessions are a follow-on slice.
- Automatic `session_id` rotation when a session is interrupted (e.g., /clear) — the `source=clear` matcher run already overwrites the file with the new post-clear session id, so rotation is implicit. Explicit GC of stale worktree files is deferred.
- Migrating existing worktrees' missing files — first `SessionStart` in each worktree produces the file; no bulk migration.
- Any change to `pipeline_agent_pager.py` source — the read path already tolerates the writer's eventual behavior; the wave closes the write gap only.

## Work items

1. At `.claude/hooks/session-start.sh` (new file), implement the SessionStart hook per the Scope description. Make executable (`chmod +x`).
2. At `.claude/settings.json`, append the new hook entry to the existing `SessionStart` matcher's `hooks` array. The existing hook (hard-rules + MEMORY.md injection) must remain first; the new session-id-writer hook is appended second. Preserve JSON formatting (2-space indent).
3. At `mu/tests/tools/test_pipeline_agent_pager.py`, add a growth-cap-aware regression test (no new test file). Invoke the hook as a subprocess with `subprocess.run(["bash", hook_path], input=payload, env={..., "CLAUDE_PROJECT_DIR": tmp_path}, capture_output=True, check=False)`. Verify the target file exists, contents match the `session_id` from the payload (after `.strip()`), and `_read_orchestrator_session_id(tmp_path)` returns the same id.

## Stop conditions

- Any change to a file outside the 3-file scope → HALT, escalate.
- Any change to `pipeline_agent_pager.py` → HALT (reader contract is fixed).
- Plan body > 100 lines → HALT, re-scope.
- Founder amends directive before Phase B → HALT, re-plan.

## Acceptance criteria

- `bash .claude/hooks/session-start.sh` with JSON stdin `{"session_id":"<uuid>","hook_event_name":"SessionStart","source":"startup"}` and `CLAUDE_PROJECT_DIR=<tmp>` exits 0 and writes `<uuid>` to `<tmp>/.agent_bus/observability/orchestrator_session_id` (demonstrated by the new regression test).
- `python3 -c "import json; s = json.load(open('.claude/settings.json')); ss = s['hooks']['SessionStart']; assert any(any('session-start.sh' in h.get('command','') for h in m.get('hooks',[])) for m in ss), 'hook not registered'"` reports success.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py` passes with 1 new test case green.
- `mu/tests/docs/test_growth_caps.py` still passes (no new test file created; regression test added to existing `test_pipeline_agent_pager.py`).
- Fail-open discipline: piping malformed JSON, missing `session_id` field, session_id with internal whitespace, or empty `CLAUDE_PROJECT_DIR` all produce exit 0 and NO file write — demonstrated by parametrized assertions inside the single regression test.

## Grounding / Authorization

- **Governing tracked packet:** `reports/control_plane/pager_session_id_autowrite_2026-04-20.md` (this file). Sibling narrow control-surface pipeline-hardening wave pattern — precedent: `FOUNDER_OVERRIDE:plan-lock-header-normalization-2026-04-18` at TASKS.md:204 + `FOUNDER_OVERRIDE:routing-api-plus-write-gate-2026-04-20` landed via PR #803 in this same session. Parallel bucket-level governing packet in the pager lane: `[PIPELINE-AGENT-PAGER]` at TASKS.md:199 (governing packet `reports/control_plane/pipeline_agent_pager_2026-04-16.md`). This wave's scope (SessionStart hook + settings.json registration + regression test) is disjoint from the in-flight pager packet, which focused on dispatch-path hardening — no overlap on `_read_orchestrator_session_id()` or the file-write side.
- **`task_id` is a procedural Gate 8 anchor.** `meta_bridge_supervisor.check_tasks_authorization` at `meta_bridge_supervisor.py:559-600` accepts any bracketed token matching an active NOW/NEXT entry. `[NEXT-CODEX-POST-REDTEAM]` at TASKS.md:241 is UNPARKED and founder-authorized. Direct precedents using this anchor on control-surface pipeline-hardening waves disjoint from the structural-gap-sweep queue: PR #802 `supervisor-prompt-override-2026-04-20` + PR #803 `routing-api-plus-write-gate-2026-04-20` (both merged same session).
- **Memory context** `project_next_wave_context.md:24` (session 2026-04-20 prior): this wave is queued as the K-2 follow-on after pager route-flip landed in PR #794. Verified 2026-04-20: file missing in all 7 live worktrees; pager fell back to plain `claude -p`. This wave closes the writer gap.
- **Founder in-session autonomous directive 2026-04-20**: "standing automated authorization is if pipeline fails, to do structural fix, and add to either API, recovery or other needed way for mechanical if fails again. Also, after this wave, automatically do next valuable highest roi wave autonomously. If override needed give override." — explicit autonomy for this next-wave launch.
- **Standing pipeline-bug-fix authorization** per memory `feedback_autonomous_executor_fix.md` (founder, 2026-04-06): autonomous authority for mechanical executor/governance fixes — precisely this class (closing a write-side gap in an existing pager reader path).
- **`FOUNDER_OVERRIDE:pager-session-id-autowrite-2026-04-20`** — wave-specific single-use token, auto-appended by the `founder_override_token` mechanization landed in PR #803 (`_build_default_tracker_note_text` at `commit_executor.py:558-669`). This wave self-tests the mechanization on itself.
- **Lane: control-surface (agent automation / observability)** — same lane as [PIPELINE-AGENT-PAGER] (TASKS.md:198-205) and [PIPELINE-RECOVERY] (TASKS.md:220-232).
- **Bootstrap classification: NOT bootstrap.** Touches `.claude/hooks/session-start.sh` (new) + `.claude/settings.json` (config) + `test_pipeline_agent_pager.py` (tests). No substrate code; no implementer/bridge/adapter surface changed.
