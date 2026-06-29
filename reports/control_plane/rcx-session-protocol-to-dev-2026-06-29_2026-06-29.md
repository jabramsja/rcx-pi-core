# commit the cross-orchestrator rcx_session_protocol.sh (read-only, polymorphic) to dev so Codex can discover it

Date: 2026-06-29
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: rcx-session-protocol-to-dev-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Make the cross-orchestrator session-protocol script DISCOVERABLE to Codex by committing it to dev (it is currently local-only / untracked, so Codex -- which reads the repo + FOUNDER_SESSION_BOOTSTRAP.md, NOT .claude/ -- cannot see it). CREATE `mu/tools/session/rcx_session_protocol.sh`: a READ-ONLY bash script, run by BOTH orchestrators (Claude preflight + the hourly protocol cron + Codex startup), that (a) points to the canonical surfaces (STATUS.md, TASKS.md, CLAUDE.md, FOUNDER_SESSION_BOOTSTRAP.md); (b) enumerates the SHARED cross-orchestrator standing imperatives -- POLYMORPHIC roles/orchestrator (the founder assigns the LLM for each pipeline role in ANY combination and changes it at will; NEVER hardcode/assume a provider -- verify live), pipeline/builders-only, most-structural/never-host-semantics, never-behind-dev, edit-ownership (Claude edits claude-files & never the bootstrap; Codex edits the bootstrap & never claude-files; both read-only the other), autonomous; (c) lists the KEY COMMANDS run via the pipeline -- `set_roles.py --implementer <X> --reviewer <Y>` and `set_orchestrator_mode.py --mode <mode> --apply` (with <X>/<Y>/<mode> shown as founder-chosen placeholders, never a hardcoded provider); and (d) VERIFIES live state by running `set_roles.py --show` (printing CURRENT role_agents / derived backends / bridge_reviewers) and reading `.agent_bus/observability/orchestrator_mode.json` for the live mode. STRICTLY READ-ONLY: it must NOT apply any config (preflight Step 0 owns the apply), must NOT mutate anything, and must NOT duplicate or edit FOUNDER_SESSION_BOOTSTRAP.md. Resolve repo root from CLAUDE_PROJECT_DIR or `git rev-parse --show-toplevel`. Make it executable (chmod +x equivalent / 755). Use ONLY SHARED cross-orchestrator info -- NO provider-specific mechanics (no .claude/ or ~/.codex/ internals). Adding a new mu/tools/**/*.sh trips the test_growth_caps tool-script cap: PRE-BUMP CAP_TOOL_SCRIPTS +1 IN THIS WAVE in mu/tests/docs/test_growth_caps.py with an inline `FOUNDER_OVERRIDE:rcx-session-protocol-to-dev-2026-06-29` comment (do not rely on the commit-time auto-bump). No host semantics.

## Scope

This wave adds exactly one new cross-orchestrator surface plus the single cap bump that admits it -- nothing else. It introduces a read-only, polymorphic session-protocol script under `mu/tools/session/` so the shared startup protocol lives in the tracked repo (where Codex, which reads the repo + FOUNDER_SESSION_BOOTSTRAP.md and NOT `.claude/`, can discover and run it) instead of remaining local-only/untracked. The script only points at canonical surfaces, enumerates the shared imperatives, lists pipeline commands as founder-chosen placeholders, and prints live role/mode state; it applies and mutates nothing. The only other change is the in-wave `CAP_TOOL_SCRIPTS` bump that the new `mu/tools/**/*.sh` file requires. The full behavioral specification of the script lives in Purpose (line 8) and is decomposed into concrete deliverables under Work items below; this Scope governs which surfaces may change.

Files and surfaces in scope:

- `mu/tools/session/rcx_session_protocol.sh` -- CREATED (currently absent/untracked; verified `ls` + `git ls-files` empty). The primary deliverable: a new read-only, executable (mode 755), polymorphic cross-orchestrator session-protocol script.
- `mu/tests/docs/test_growth_caps.py` -- EDITED. `CAP_TOOL_SCRIPTS` pre-bumped +1 (56 -> 57) in this wave with an inline `FOUNDER_OVERRIDE:rcx-session-protocol-to-dev-2026-06-29` comment, because adding a `mu/tools/**/*.sh` trips the tool-script cap. (Verified current value: `CAP_TOOL_SCRIPTS = 56`, no entry yet for this wave.)
- `TASKS.md` -- tracker-sync authority (read-only here). The 2026-06-29 tracker sync note for wave `rcx-session-protocol-to-dev-2026-06-29` (TASKS.md:634) is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. CREATE `mu/tools/session/rcx_session_protocol.sh` -- a strictly read-only bash script, executable (mode 755), runnable by both orchestrators (Claude preflight + the hourly protocol cron + Codex startup). It MUST:
   - resolve repo root from `CLAUDE_PROJECT_DIR` or, failing that, `git rev-parse --show-toplevel`;
   - carry an `RCX SESSION PROTOCOL` header line (matched by the evidence_command);
   - (a) point to the canonical surfaces: STATUS.md, TASKS.md, CLAUDE.md, FOUNDER_SESSION_BOOTSTRAP.md;
   - (b) enumerate the shared cross-orchestrator standing imperatives: POLYMORPHIC roles/orchestrator (the founder assigns each pipeline role's LLM in any combination and changes it at will -- never hardcode/assume a provider, verify live), pipeline/builders-only, most-structural/never-host-semantics, never-behind-dev, edit-ownership (Claude edits claude-files & never the bootstrap; Codex edits the bootstrap & never claude-files; both read-only the other), autonomous;
   - (c) list the key pipeline commands with founder-chosen placeholders (never a hardcoded provider): `set_roles.py --implementer <X> --reviewer <Y>` and `set_orchestrator_mode.py --mode <mode> --apply`;
   - (d) verify live state read-only: run `set_roles.py --show` (printing current role_agents / derived backends / bridge_reviewers) and read `.agent_bus/observability/orchestrator_mode.json` for the live mode.
2. In `mu/tests/docs/test_growth_caps.py`, pre-bump `CAP_TOOL_SCRIPTS` +1 (56 -> 57) in this wave with an inline `FOUNDER_OVERRIDE:rcx-session-protocol-to-dev-2026-06-29` comment naming the new tool script. Do NOT rely on the commit-time auto-bump.

## Constraints

- Strictly read-only: the script MUST NOT apply any config (preflight Step 0 owns the apply), MUST NOT mutate any file or runtime state, and MUST NOT duplicate or edit FOUNDER_SESSION_BOOTSTRAP.md.
- No provider hardcoding: never name or assume a specific LLM provider for any role or mode. Roles/orchestrator are polymorphic and verified live; commands carry `<X>`/`<Y>`/`<mode>` placeholders only.
- Shared info only: use ONLY cross-orchestrator content. NO provider-specific mechanics or internals -- no `.claude/` paths and no `~/.codex/` paths/details.
- No host semantics and no runtime/substrate changes. This is an L4_ENABLER, so it MUST NOT touch runtime dirs (`mu/host/`, `rcx_pi/selfhost/`).
- Do not rely on the commit-time `CAP_TOOL_SCRIPTS` auto-bump; the cap is bumped explicitly in-wave (Work item 2).
- No files beyond the three listed in Scope are created or modified.

## Stop conditions

- STOP if satisfying the protocol would require the script to apply/mutate config or write any state -- the read-only contract is non-negotiable; re-scope rather than break it.
- STOP if the script would need a provider-specific path or a hardcoded provider name to function -- that violates the polymorphic / shared-only constraint.
- STOP if landing the change requires touching any runtime dir or any file beyond the three in Scope -- escalate to the founder, do not widen scope.
- STOP if the `CAP_TOOL_SCRIPTS` bump cannot be performed in-wave (e.g. only the commit-time auto-bump path is available) -- the bridge requires the explicit in-wave hand-bump.
- STOP and request founder input on any contradiction between this packet and the TASKS.md tracker note (TASKS.md:634) for this wave.

## Validation gates

- evidence_command: `grep -q 'RCX SESSION PROTOCOL' mu/tools/session/rcx_session_protocol.sh && grep -q -i polymorphic mu/tools/session/rcx_session_protocol.sh`

## Acceptance criteria

- evidence_command passes: `grep -q 'RCX SESSION PROTOCOL' mu/tools/session/rcx_session_protocol.sh && grep -q -i polymorphic mu/tools/session/rcx_session_protocol.sh`.
- `mu/tools/session/rcx_session_protocol.sh` exists, is git-tracked, and is executable (mode 755).
- The script is read-only by inspection: no config-apply, no file/state mutation, and no edit/duplication of FOUNDER_SESSION_BOOTSTRAP.md; it resolves repo root from `CLAUDE_PROJECT_DIR` or `git rev-parse --show-toplevel`.
- The script contains all four required blocks: (a) canonical surfaces; (b) shared imperatives including the polymorphic-roles statement; (c) placeholder pipeline commands (`set_roles.py --implementer <X> --reviewer <Y>`, `set_orchestrator_mode.py --mode <mode> --apply`) with no hardcoded provider; (d) live-state verification via `set_roles.py --show` + `.agent_bus/observability/orchestrator_mode.json`.
- No `.claude/` or `~/.codex/` provider internals appear anywhere in the script.
- `CAP_TOOL_SCRIPTS == 57` in `mu/tests/docs/test_growth_caps.py` (bumped from 56) with the inline `FOUNDER_OVERRIDE:rcx-session-protocol-to-dev-2026-06-29` comment, and `mu/tests/docs/test_growth_caps.py` passes.
- L4_ENABLER hygiene holds: no runtime dirs touched; only the three Scope files changed.
- L4 indicator collected: `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id rcx-session-protocol-to-dev-2026-06-29 --output reports/l4_wave_indicators/rcx-session-protocol-to-dev-2026-06-29.json`.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `rcx-session-protocol-to-dev-2026-06-29`.
- Governing packet: this file, `reports/control_plane/rcx-session-protocol-to-dev-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the 2026-06-29 tracker sync note for wave `rcx-session-protocol-to-dev-2026-06-29` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:rcx-session-protocol-to-dev-2026-06-29
