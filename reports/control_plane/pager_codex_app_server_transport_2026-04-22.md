# Pager Codex App Server Transport

Task: `[PIPELINE-AGENT-PAGER]`
Wave ID: `pager-codex-app-server-transport`
Date: `2026-04-22`
Status: `implemented (Phase B local)`

## Outcome

This wave replaces the fake REST-shaped Codex pager transport with the bounded
loopback App Server websocket JSON-RPC path in
`mu/tools/observability/pipeline_agent_pager.py`.

The landed adapter now:

- accepts one authoritative listener surface: `RCX_CODEX_APP_SERVER_URL`,
  validated as a loopback `ws://` URL
- uses a repo-local helper that shells to `node` and relies on the built-in
  `WebSocket` client rather than adding third-party Python websocket packages
- sends `initialize` first on each fresh connection with
  `clientInfo = {name: "pipeline_agent_pager", version: "1.0"}`
- uses `thread/start` only when pager state has no stored `codex_thread_id`
- uses direct `turn/start` on the stored `threadId` for fresh-connection reuse
  and does not route the success path through `thread/resume`
- encodes `turn/start.params.input` as the minimal schema-compliant
  `[{type: "text", text: _event_prompt(event)}]` payload
- treats delivery as successful only after the accepted-turn response carries an
  explicit `turn.id`, using the already-authoritative requested or newly created
  thread id when the server omits `thread.id`
- keeps one shared `pipeline_agent_pager_codex_ack` budget across the full
  `initialize` / `thread/start?` / `turn/start` handshake
- clears a stale persisted thread id on explicit `thread not found` /
  `no rollout found`, reseeds once under the same deadline, and leaves the
  target pending if that reseed still cannot produce a usable thread identity
  plus `turn.id`

## Code Truth

Changed files:

- `TASKS.md`
- `mu/tools/observability/pipeline_agent_pager.py`
- `mu/tests/tools/test_pipeline_agent_pager.py`
- `reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`
- `reports/l4_wave_indicators/pager-codex-app-server-transport-clean-2026-04-22.json`

Why those stayed untouched:

- `mu/tests/docs/test_growth_caps.py` stayed untouched because this slice did not
  add new repo-tracked files beyond the active packet, tracker note, and staged
  indicator artifact, so the growth-cap fallback was not needed

## Regression Coverage

`mu/tests/tools/test_pipeline_agent_pager.py` now locks the transport contract
at the adapter boundary:

- request sequencing for `initialize`, `thread/start`, and `turn/start`
- concrete `clientInfo` and `turn/start.input` payload shape
- accepted-turn ACK only after explicit `turn.id`, with fallback to the
  requested/created thread identity when `thread.id` is absent
- rejection of mismatched accepted-turn `thread.id`
- rejection of thread-start responses that omit `thread.id`
- one-budget stale-thread reseed behavior
- pager-state clearing when dispatch returns `clear_codex_thread_id`

These are unit-level proofs for the pager adapter and state contract. The
derived provisioning follow-up at
`reports/control_plane/pager_codex_app_server_provisioning_2026-04-22.md`
owns only the fail-closed handling for invalid or unavailable
`RCX_CODEX_APP_SERVER_URL` provisioning; live listener startup/orchestration
still remains out of scope for this transport slice.

## Control-Surface Note

The canonical Phase B bridge artifact for this slice is reviewer turn
`phase-b-r1-3e5c1657--r1-reviewer-632c8680`, recorded in
`.agent_bus/rendered/phase-b-r1-3e5c1657.md` as `Status: stale`. That reviewer
did emit an authoritative envelope and correctly found the accepted-turn
`thread.id` contract defect that this packet now fixes.

Grounded evidence from the canonical bridge render:

- `.agent_bus/rendered/phase-b-r1-3e5c1657.md` lists reviewer
  `phase-b-r1-3e5c1657--r1-reviewer-632c8680` with `Status: stale`
- the same render records three findings: the blocking pager protocol defect,
  its matching regression-test defect, and the packet-language defect
- `.agent_bus/raw/phase-b-r1-3e5c1657/phase-b-r1-3e5c1657--r1-reviewer-632c8680.txt`
  contains a `BEGIN_AGENT_ENVELOPE ... END_AGENT_ENVELOPE` block with those
  findings

The manual standalone continuation used here is therefore not a claim that the
canonical bridge turn lacked an envelope. It is a bounded continuation choice
after applying the stale turn's grounded findings locally. The broader retry /
recovery mechanization follow-on remains queued in `TASKS.md`, but it is not
used here as commit evidence for this wave.

## Validation

Executed:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py`
- `python3 tools/checks/enforce_l4_execution_contract.py --files mu/tools/observability/pipeline_agent_pager.py mu/tests/tools/test_pipeline_agent_pager.py reports/control_plane/pager_codex_app_server_transport_2026-04-22.md`

Results:

- pager test file: `26 passed`
- L4 execution contract: `PASS`
