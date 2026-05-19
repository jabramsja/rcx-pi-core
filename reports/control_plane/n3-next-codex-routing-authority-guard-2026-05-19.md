# N3 Next Codex Routing Authority Guard - 2026-05-19

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-next-codex-routing-authority-guard-2026-05-19
Class: L4_ENABLER
Category: tooling/control-plane pipeline authority repair
Target gate: G8
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-next-codex-routing-authority-guard-2026-05-19

## Scope

This bounded repair fixes a dispatcher drift path found while resuming the
autonomous N3 structural waves. The live dispatcher was still bound to
`reports/control_plane/n3-list-to-linked-iteration-marker-source-lock-2026-05-19_2026-05-19.md`,
but `TASKS.md` did not authorize that exact wave/packet pair.

Files in scope:

- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/executors/executor_common.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tests/tools/test_executor_dispatch.py`
- this packet
- `TASKS.md` only for the same-wave tracker note
- `reports/l4_wave_indicators/n3-next-codex-routing-authority-guard-2026-05-19.json`

## Work items

1. Teach the post-merge queue parsers to recognize N3 `[NEXT-CODEX-POST-REDTEAM]`
   entries that do not use a `FOUNDER-ORDERED-REDTEAM-` label.
2. Hold bounded `[NEXT-CODEX-POST-REDTEAM]` routing before Phase A when the
   selected packet lacks same-wave `TASKS.md` queue or tracker-note authority.
3. Preserve existing completed-candidate, stale-refresh, packet-wave-conflict,
   and Phase B tracker-gate behavior.
4. Remove the generated untracked old-path packet that caused the local dirty
   state.

## Constraints

- Do not edit runtime, substrate, Stage0, scheduler, seed, registry, loader,
  checksum, integrity, ratchet baseline, docs truth, Claude, Codex binary/cache,
  push, PR, or unrelated tooling surfaces.
- Do not route the old `n3-list...` packet unless a future same-wave `TASKS.md`
  entry authorizes that exact path.
- Do not add host semantics, host exception tables, smarter substrate behavior,
  or baseline-only proof.

## Stop conditions

- Stop if the dispatcher can still run Phase A for a bounded
  `[NEXT-CODEX-POST-REDTEAM]` packet that has no same-wave `TASKS.md` authority.
- Stop if N3 queue entries with `Task: [NEXT-CODEX-POST-REDTEAM]`, `Wave ID`,
  and `Packet` fields are still invisible to the post-merge queue parsers.
- Stop if any existing completed-candidate or Phase B tracker-guard regression
  fails.

## Acceptance criteria

- `executor_dispatch.py` rejects orphan bounded `[NEXT-CODEX-POST-REDTEAM]`
  packet routing before invoking `phase_a_executor.py`.
- `executor_dispatch.py`, `executor_common.py`, and `commit_executor.py` all
  recognize N3 queue lines that carry `NEXT-CODEX-POST-REDTEAM` authority even
  when the label is not prefixed `FOUNDER-ORDERED-REDTEAM-`.
- Focused regressions pass:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py::TestDispatcherFreshnessRefresh --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'tracker_guard or missing_tracker or orphan_packet or n3_entries' --tb=short`
  - `python3 -m py_compile mu/tools/executors/executor_dispatch.py mu/tools/executors/executor_common.py mu/tools/executors/commit_executor.py`

## Grounding / Authorization

- `TASKS.md:574` requires autonomous dispatcher/pipeline execution and says every
  wave requires both a control-plane packet and a `TASKS.md` tracker entry.
- The stale live routing record directly named the old packet path in
  `.agent_bus/meta/post_merge_routing.json` while `TASKS.md:583` named the
  authorized N3 source-lock packet instead.
- The old generated packet recorded the mismatch itself with
  `Phase-A-Lock-Reason: NO_GO_PATH_AUTHORITY_MISMATCH`; it was untracked and is
  removed by this repair.
- This packet is the same-wave authority for the bounded pipeline repair only.

Questions? Concerns? Thoughts? -- Think hard
