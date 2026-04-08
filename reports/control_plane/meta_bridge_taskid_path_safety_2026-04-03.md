# Meta-Bridge Bounded Review Fix

Date: 2026-04-03
Status: Phase B (implementation-complete, bridge-converged)
Phase-A-Lock: LOCKED
Task: [META-BRIDGE-BOUNDED-REVIEW-FIX]
Wave ID: meta-bridge-taskid-path-safety-2026-04-03

## 1. Scope

TASKS.md authorizes two problems under [META-BRIDGE-BOUNDED-REVIEW-FIX]:

> Keep `FOUNDER_SESSION_BOOTSTRAP.md` reading required for Codex reviewers, but
> stop the pre-commit meta-review from rerunning founder guard/attest startup
> flows or self-aborting on clean zero-match probe commands before emitting an
> envelope.

**Problem A -- Startup-flow rerun:** The pre-commit meta-review path reruns
founder guard/attest startup flows that should only execute once during session
bootstrap, not on every supervisor invocation. This must be suppressed in the
meta-review entrypoint while preserving the requirement that Codex reviewers
still read `FOUNDER_SESSION_BOOTSTRAP.md`.

**Problem B -- Self-abort on clean zero-match probes:** The meta-review
self-aborts when probe commands return zero matches (clean state), treating a
clean result as an error rather than a valid "nothing to report" outcome. The
reviewer must emit an envelope even when probes find nothing.

**Problem C -- Slash-bearing task IDs (root cause of B):** Task IDs containing
`/` (e.g., `[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]`)
crash prompt/raw filename creation under `.agent_bus/meta/`, producing
`FileNotFoundError` before the reviewer can emit a decision. This is a direct
cause of the self-abort symptom in Problem B: the reviewer aborts not because
the probe found nothing wrong, but because the file-write for the envelope
itself fails on the slash character. Fixing the path sanitization resolves the
self-abort for slash-bearing IDs; any remaining zero-match abort paths must
also be identified and fixed.

### Files in scope

- `mu/tools/agents/meta_bridge_supervisor.py` -- reviewer entrypoints, path construction, probe handling
- `mu/tools/executors/phase_a_executor.py` -- lock_plan() Status-line hardening
- `mu/tests/tools/test_meta_bridge_supervisor.py` -- regression coverage
- `mu/tests/tools/test_executor_dispatch.py` -- lock_plan() test alignment

### Directories in scope

- `.agent_bus/meta/prompts/` -- prompt file outputs (path safety)
- `.agent_bus/meta/raw/` -- raw output files (path safety)

## 2. Work items

Concrete bounded tasks derived from the TASKS.md authorization:

1. **Sanitize task-ID paths:** Add a shared helper that replaces `/` (and any
   other OS-unsafe characters) in `task_id` before it is embedded in
   `job_id` / `turn_id` for prompt and raw-output filenames under
   `.agent_bus/meta/`. Exact tracker IDs like
   `[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]` must
   produce valid file paths.

2. **Suppress startup-flow rerun in meta-review:** Ensure the pre-commit
   meta-review entrypoint does not re-execute founder guard/attest startup
   flows. The `FOUNDER_SESSION_BOOTSTRAP.md` reading requirement for Codex
   reviewers must be preserved (it is injected via `bridge_reviewer_prompt.txt`
   template, not via the startup flows).

3. **Emit envelope on zero-match probes:** Ensure the reviewer emits a valid
   decision envelope even when all probe commands return zero matches (clean
   state). A clean probe result is not an error.

4. **Regression tests:** Cover all three problems:
   - Slash-bearing task IDs for pre-commit and post-merge entrypoints
   - Shared filename-token helper with OS-unsafe characters
   - Zero-match probe producing a valid envelope (not an abort)
   - Pre-commit path not invoking founder guard/attest startup flows

## 3. Constraints (what is NOT in scope)

- **No refactoring of the meta-bridge prompt template assembly.** The
  `bridge_reviewer_prompt.txt` template and its injection of
  `FOUNDER_SESSION_BOOTSTRAP.md` are not being restructured. Only the
  entrypoint behavior (what runs before the reviewer is invoked) is in scope.

- **No changes to the bridge protocol itself.** `AgentBridgeProtocol.v0.md`
  is not modified. This is a supervisor-hardening fix, not a protocol change.

- **No changes to `commit_executor.py` or `executor_dispatch.py`.** The
  pipeline executors are upstream callers; this fix is scoped to the
  meta-bridge supervisor layer they invoke.

- **No changes to `FOUNDER_SESSION_BOOTSTRAP.md` content or reading
  requirement.** Codex reviewers must still read it. Only the *rerunning*
  of startup flows is suppressed.

- **Deferred:** Any broader meta-bridge refactoring, reviewer prompt
  optimization, or bridge-protocol evolution is out of scope for this wave.

## 4. Stop conditions

Stop when ALL of the following are true:

1. Slash-bearing task IDs produce valid file paths under `.agent_bus/meta/`
   (no `FileNotFoundError`).
2. The pre-commit meta-review entrypoint does not re-execute founder
   guard/attest startup flows.
3. Zero-match probe commands result in a valid decision envelope, not a
   self-abort.
4. All validation commands pass (see section 6).

**Do NOT expand** to refactor reviewer prompt assembly, bridge protocol,
executor dispatch, or any surface not listed in section 1.

## 5. Acceptance criteria

1. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_meta_bridge_supervisor.py -q --tb=short` -- all tests pass, including new regression tests for slash IDs, zero-match probes, and startup-flow suppression.
2. `./tools/checks/check_docs_consistency.sh` -- clean.
3. `./tools/session/founder_session_attest.sh redteam` -- clean.
4. `python3 tools/checks/enforce_l4_execution_contract.py --staged` -- clean.
5. `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR PYTHONHASHSEED=0 python3 mu/tools/executors/executor_dispatch.py pre-commit-supervisor --package .scratch/auto_supervisor_package.json --json -v` -- supervisor completes without self-abort on a slash-bearing task ID.

## 6. Grounding / Authorization

- **TASKS.md authorization:** Lines 151-155, `[META-BRIDGE-BOUNDED-REVIEW-FIX]` **NEXT** (2026-04-01, founder-authorized).
- **Governing packet:** This file (`reports/control_plane/meta_bridge_taskid_path_safety_2026-04-03.md`).
- **Lane:** control-surface (supervisor hardening).
- **Related protocol:** `.claude/rules/wave-protocol.md` (bridge bootstrap, Phase B dispatch).
- **Bridge reviewer prompt contract:** `bridge_reviewer_prompt.txt` (injection of `FOUNDER_SESSION_BOOTSTRAP.md` for Codex).