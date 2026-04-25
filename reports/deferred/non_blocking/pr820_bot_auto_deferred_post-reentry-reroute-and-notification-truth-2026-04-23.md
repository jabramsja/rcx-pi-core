# PR #820 Bot Findings (Auto-Deferred)

Date: 2026-04-25
Wave: post-reentry-reroute-and-notification-truth-2026-04-23
Classification: NON-BLOCKING (auto-deferred — remediation adapter produced no changes)

## Finding 1: `mu/tools/session/codex_autoping_watch.py`

**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Scope autoping attention checks to the active bridge job**

`_read_bridge_state` fetches the latest `jobs` row and the latest `turns` row independently, so `_attention_required_summary` can combine a new job with a failed turn from an older job. This happens when a new job is created before its first turn is written, and it causes false `attention_required` alerts that suppress normal autoping resume behavior

## Finding 2: `mu/tools/observability/pipeline_agent_pager.py`

**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Reject foreign CODEX_THREAD_ID before pager dispatch**

The new thread selection logic prioritizes `CODEX_THREAD_ID` over repo-matched autoping state (`live_thread_id = env_thread_id or autoping_thread_id`) but only filters paused threads, not cross-repo threads. In a shell with `CODEX_THREAD_ID` exported from another workspace, this repo’s pager events are sent to the wrong Codex thread even when a correct l
