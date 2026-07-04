#!/usr/bin/env bash
# RCX SESSION PROTOCOL — cross-orchestrator startup surface (READ-ONLY, polymorphic)
#
# Run by BOTH orchestrators: the Claude preflight, the hourly protocol cron, and
# Codex startup. This script is committed to the tracked repo precisely so EITHER
# orchestrator can discover and run it — Codex reads the repo + the founder
# bootstrap, not any provider-private config dir, so a local-only copy would be
# invisible to it.
#
# CONTRACT — STRICTLY READ-ONLY. This script only:
#   (a) POINTS at the canonical surfaces,
#   (b) ENUMERATES the shared cross-orchestrator standing imperatives,
#   (c) LISTS the key pipeline commands as founder-chosen placeholders, and
#   (d) PRINTS the live role/mode state for verification.
# It APPLIES nothing and MUTATES nothing — the preflight Step 0 owns any apply.
# It never edits or duplicates FOUNDER_SESSION_BOOTSTRAP.md. It hardcodes no
# provider for any role or mode: roles/orchestrator are polymorphic and verified
# live (section d).
set -uo pipefail

# --- repo root: CLAUDE_PROJECT_DIR, else the enclosing git toplevel -----------
RCX_ROOT="${CLAUDE_PROJECT_DIR:-}"
if [ -z "${RCX_ROOT}" ]; then
    RCX_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi
if [ -z "${RCX_ROOT}" ] || [ ! -d "${RCX_ROOT}" ]; then
    echo "ERROR: cannot resolve repo root (set CLAUDE_PROJECT_DIR or run inside the git repo)" >&2
    exit 2
fi
cd "${RCX_ROOT}" || exit 2

echo "================================================================"
echo "RCX SESSION PROTOCOL  (cross-orchestrator, read-only)"
echo "repo: ${RCX_ROOT}"
echo "================================================================"
echo ""

# --- (a) canonical surfaces ---------------------------------------------------
echo "(a) CANONICAL SURFACES — read these first (current state lives here, never in memory):"
for surface in STATUS.md TASKS.md CLAUDE.md FOUNDER_SESSION_BOOTSTRAP.md; do
    if [ -f "${surface}" ]; then
        echo "    - ${surface}"
    else
        echo "    - ${surface}   (MISSING)"
    fi
done
echo "    STATUS.md + TASKS.md are the only owners of current state."
echo "    FOUNDER_SESSION_BOOTSTRAP.md is the founder bootstrap — read-only here; this script never edits or duplicates it."
echo ""

# --- (b) shared cross-orchestrator standing imperatives -----------------------
echo "(b) SHARED STANDING IMPERATIVES — apply to EVERY orchestrator, every session:"
echo "    - POLYMORPHIC roles/orchestrator: the founder assigns the LLM for each"
echo "      pipeline role (implementer, reviewer, ...) and the orchestrator mode in"
echo "      ANY combination, and changes them at will. NEVER hardcode or assume a"
echo "      provider for any role or mode — VERIFY LIVE (see section d)."
echo "    - PIPELINE / BUILDERS ONLY: all wave code, commits, merges and conflict"
echo "      resolution go through the executor pipeline / builders — never manual git."
echo "    - MOST-STRUCTURAL / NEVER HOST-SEMANTICS: prefer the best structural"
echo "      reduction; never add host-only capabilities to the bootstrap."
echo "    - NEVER BEHIND DEV: the working repo and its PRs must never fall behind dev."
echo "    - EDIT-OWNERSHIP: Claude edits the claude-owned files and never the founder"
echo "      bootstrap; Codex edits the founder bootstrap and never the claude-owned"
echo "      files; each treats the other's files as read-only."
echo "    - AUTONOMOUS: continue autonomously to the best structural outcome; do not"
echo "      stall for confirmation the founder has already granted."
echo "    - AUTOMATE THE GRUNT WORK: you orchestrate; the pipeline/recovery does"
echo "      the grunt work. Land every recurring manual op into the AUTOMATIC"
echo "      pipeline layer (recovery_gate / commit_executor / a deterministic"
echo "      script) so BOTH orchestrators inherit it — never a hand-run one-off."
echo ""

# --- (c) key pipeline commands (founder-chosen placeholders, no hardcoded provider) ---
echo "(c) KEY PIPELINE COMMANDS — run via the pipeline. <X>/<Y>/<mode> are"
echo "    founder-chosen placeholders, never a hardcoded provider:"
echo "    - python3 mu/tools/executors/set_roles.py --implementer <X> --reviewer <Y>"
echo "    - python3 mu/tools/session/set_orchestrator_mode.py --mode <mode> --apply"
echo "    This protocol script NEVER runs the apply form — preflight Step 0 owns it."
echo ""

# --- (d) live state verification (read-only — nothing is changed) -------------
echo "(d) LIVE STATE — read-only verification; nothing is applied or changed:"
echo "    role_agents / derived backends / bridge_reviewers (set_roles.py --show):"
if command -v python3 >/dev/null 2>&1; then
    # Capture --show, but DO NOT let the command substitution swallow a non-zero
    # exit. Testing the assignment in `if` propagates set_roles.py's status (a plain
    # `var=$(...)` assignment, unlike `local var=$(...)`, preserves it). A failed
    # --show — missing/invalid executor_config.json, or a stale CLAUDE_PROJECT_DIR
    # that left us cd'd outside the repo so the relative script path is absent —
    # means live state is UNVERIFIED: surface it and FAIL, never print the error
    # indented as if it were the real live-state block and then exit 0.
    if show_out="$(python3 mu/tools/executors/set_roles.py --show 2>&1)"; then
        if [ -n "${show_out}" ]; then
            printf '%s\n' "${show_out}" | sed 's/^/        /'
        else
            echo "        (set_roles.py --show produced no output; inspect mu/tools/executors/executor_config.json)"
        fi
    else
        show_status=$?
        echo "        ERROR: set_roles.py --show exited ${show_status}; live role/backend state is UNVERIFIED. Captured output:"
        printf '%s\n' "${show_out}" | sed 's/^/        | /'
        echo "ERROR: rcx_session_protocol.sh: live-state verification failed (set_roles.py --show exit ${show_status}); inspect CLAUDE_PROJECT_DIR and mu/tools/executors/executor_config.json." >&2
        exit 3
    fi
else
    echo "        (python3 unavailable; inspect mu/tools/executors/executor_config.json)"
fi
echo ""

ORCH_MODE_FILE=".agent_bus/observability/orchestrator_mode.json"
echo "    orchestrator mode (${ORCH_MODE_FILE}):"
if [ -f "${ORCH_MODE_FILE}" ]; then
    mode_line=""
    if command -v python3 >/dev/null 2>&1; then
        mode_line="$(python3 -c 'import json,sys; print("mode =", json.load(open(sys.argv[1])).get("mode", "<unset>"))' "${ORCH_MODE_FILE}" 2>/dev/null || true)"
    fi
    if [ -n "${mode_line}" ]; then
        echo "        ${mode_line}"
    else
        sed 's/^/        /' "${ORCH_MODE_FILE}"
    fi
else
    echo "        (not materialized yet — created by set_orchestrator_mode.py --mode <mode> --apply)"
fi
echo ""

echo "RCX SESSION PROTOCOL — end (read-only; applied nothing, mutated nothing)."
exit 0
