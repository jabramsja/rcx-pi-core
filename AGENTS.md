# WorkingRCX Session Start

Before any substantive work in this repo:

- Read `FOUNDER_SESSION_BOOTSTRAP.md` first.
- Use `./tools/session/founder_session_guard.sh <mode>` to operationalize the required docs, skill selection, and startup commands.
- Add `--run` when you want the guard to execute the command set instead of printing it.
- For long sessions, run `./tools/session/founder_session_heartbeat.sh <mode> --interval 300` in another terminal for recurring founder-protocol reminders.

Common modes:

- `redteam`
- `parity`
- `docs`
- `closeout`

Protocol notes:

- `FOUNDER_SESSION_BOOTSTRAP.md` is the detailed session contract. Do not duplicate it here.
- Re-verify volatile repo state from `STATUS.md`, `TASKS.md`, `CHANGELOG.md`, `reports/README.md`, and `git status --short` each session.
- Treat hidden/personal memory as non-canonical. Repo protocol must live in repo-tracked docs.
