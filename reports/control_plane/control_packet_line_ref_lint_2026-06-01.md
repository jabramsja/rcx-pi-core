# Control Packet Line Ref Lint 2026-06-01

Date: 2026-06-01
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: control-packet-line-ref-lint-2026-06-01
Phase-A-Lock: LOCKED
Purpose: Add a pre-dispatch lint that rejects code line-number references (the form <path>.<ext>:<line>, e.g. a source file followed by a colon and a line number) inside control packets under reports/control_plane/, so a packet that cites code by line number is caught at authoring/dispatch time instead of after a multi-minute Codex bridge round. Root motivation (learning.md 2026-06-01): a lane wave's original failure was a control packet citing code by line number; the Codex pre-commit supervisor rejected it as stale line references only after a full review cycle. doc-governance already forbids line numbers in docs as a written rule with NO mechanical enforcement at packet-authoring/dispatch time. This wave mechanizes that rule. Use a SPECIFIC lexical pattern (file-extension immediately followed by colon and digits) -- NOT a general heuristic -- so the matcher has a closed, tiny edge surface and does not false-positive on URLs (host:port), clock times, or ranges.

## Scope

New checker mu/tools/checks/check_control_packet_line_refs.py: given a control-packet path, scan the body for source line-number references matching a specific extension-anchored pattern (a file extension such as py/js/md/sh/json/yaml/txt immediately followed by a colon and one or more digits), exit non-zero and list each offending line when found, exit zero when clean. Must NOT flag host:port (no file extension before the colon), clock times, or numeric ranges. Wire it into phase_a_executor's plan-load pre-flight so a packet carrying such references fails closed BEFORE the first bridge round, with a clear message instructing the author to cite code by function name instead of file:line. Tooling-only under mu/tools/, touches no runtime dir (L4_ENABLER). Validation gate: a regression test at mu/tests/tools/test_check_control_packet_line_refs.py proving (a) a packet containing a source-file line reference is REJECTED, (b) a clean packet PASSES, and (c) a packet with a host:port or clock-time string is NOT a false positive. Cite code by function name only; do not put any literal file-and-line reference in the packet prose.

- `reports/deferred/non_blocking/control-packet-line-ref-lint-2026-06-01_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks (grounded in the evidence_delta of the TASKS.md tracker sync note for this wave; see Grounding / Authorization):

1. Implement the checker `mu/tools/checks/check_control_packet_line_refs.py` with a `main()` entrypoint that accepts one or more control-packet paths, a matcher helper that detects the extension-anchored colon-digit pattern over a closed extension set (py, js, md, sh, json, yaml, txt), per-offense reporting (path plus the offending line text) to stderr, a non-zero exit when any match is found, and a zero exit when clean. The matcher must reject host-and-port, clock-time, and numeric-range forms by construction (require a known file extension immediately before the colon).
2. Wire the checker into the `phase_a_executor` plan-load pre-flight so loading a packet with an offending reference fails closed before the first bridge round, surfacing the offending lines and a "cite code by function name" remediation message. No other dispatch or bridge behavior changes.
3. Add the regression test `mu/tests/tools/test_check_control_packet_line_refs.py` proving (a) a packet containing a source file-and-line reference is REJECTED (non-zero), (b) a clean packet PASSES (zero), and (c) a packet containing a host-and-port string or a clock-time string is NOT a false positive.
4. If the growth-cap gate flags the two new files, bump `CAP_TOOL_SCRIPTS` and `CAP_TEST_FILES` by one each in the growth-cap test with a wave-bound FOUNDER_OVERRIDE note (same pattern as prior tooling waves).

## Constraints (NOT in scope)

- No runtime/substrate edits: nothing under `mu/host/`, `rcx_pi/selfhost/`, seeds, registries, Stage0, scheduler, loader, or binary/checksum/integrity paths. Touching any runtime dir would void the L4_ENABLER class.
- No general-heuristic matcher. Only the closed extension-anchored colon-digit pattern is allowed, so the false-positive surface stays tiny.
- No broadening of the gate beyond control packets under `reports/control_plane/` (the checker may accept any path argument, but the executor wiring targets control packets only).
- No changes to dispatcher, commit, push, PR, or merge surfaces beyond the single `phase_a_executor` plan-load pre-flight hook.
- No edit to the written doc-governance policy text itself; this wave mechanizes the existing rule, it does not rewrite it.
- No Claude-related file edits, and no ratchet baseline edits other than the growth-cap bump for the two new files.
- Do not rewrite or "fix" unrelated existing control packets to satisfy the new checker in this wave.

## Stop conditions

1. STOP and re-scope if implementing the lint requires touching any runtime/substrate directory (it would no longer be an L4_ENABLER).
2. STOP and return to Phase A with a narrower pattern if the extension-anchored matcher cannot be made false-positive-free against host-and-port, clock-time, and numeric-range strings without degrading into a general heuristic.
3. STOP before the first bridge round if this packet itself contains any extension-anchored file-and-line reference; the new checker must pass on its own governing packet (dogfood).
4. STOP if wiring into the `phase_a_executor` plan-load pre-flight would alter bridge or dispatch behavior beyond fail-closed rejection of offending packets.
5. STOP and request a founder decision (POLICY_BOUND) if the gate would reject any existing in-tree control packet that legitimately requires a colon-digit form; do not silently rewrite unrelated packets.
6. Phase A is done only when the write set, focused tests, and these stop conditions are locked; implementation must not begin before Phase-A-Lock flips to LOCKED.

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_control_packet_line_refs.py` passes.
- The checker exits non-zero and lists each offending line for a packet containing an extension-anchored file-and-line reference, and exits zero for a clean packet.
- No false positive on host-and-port or clock-time strings, proven by the regression test.
- The `phase_a_executor` plan-load pre-flight fails closed on an offending packet before the first bridge round and emits the "cite code by function name" remediation message.
- L4_ENABLER contract satisfied: no runtime dir touched; target gate G8; evidence_command and evidence_delta present in the tracker note.
- Indicator artifact collected via `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id control-packet-line-ref-lint-2026-06-01 --output reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json`.
- This governing packet passes the new checker (no extension-anchored file-and-line reference in its prose).

## Grounding / Authorization

- TASKS.md authorization: the tracker sync note (2026-06-01, control-packet-line-ref-lint-2026-06-01) under `[NEXT-CODEX-POST-REDTEAM]` carries the same-wave tracker authority for this packet and binds it to gate G8.
- Governing packet: this file, `reports/control_plane/control_packet_line_ref_lint_2026-06-01.md`.
- Parent task packet: `[NEXT-CODEX-POST-REDTEAM]` tracked packet `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- Class: L4_ENABLER. target_gate_id: G8.
- Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md, recorded as the wave-bound override `FOUNDER_OVERRIDE:control-packet-line-ref-lint-2026-06-01` so commit automation derives the same-wave override mechanically for commit-gate and pre-push adjacency-cap clearance.
- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_control_packet_line_refs.py`.
- evidence_delta: (1) new `mu/tools/checks/check_control_packet_line_refs.py` rejects extension-anchored line-number references in control packets and passes clean packets; (2) `phase_a_executor` plan-load pre-flight fails closed on such references before the first bridge round; (3) new regression test covers reject / pass / no-false-positive (host-and-port, clock time).
- primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
- indicator_artifact_ref: reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json.
- indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id control-packet-line-ref-lint-2026-06-01 --output reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json.
- bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

## Request from Post-Merge Supervisor

Add a pre-dispatch lint that rejects code line-number references (the form <path>.<ext>:<line>, e.g. a source file followed by a colon and a line number) inside control packets under reports/control_plane/, so a packet that cites code by line number is caught at authoring/dispatch time instead of after a multi-minute Codex bridge round. Root motivation (learning.md 2026-06-01): a lane wave's original failure was a control packet citing code by line number; the Codex pre-commit supervisor rejected it as stale line references only after a full review cycle. doc-governance already forbids line numbers in docs as a written rule with NO mechanical enforcement at packet-authoring/dispatch time. This wave mechanizes that rule. Use a SPECIFIC lexical pattern (file-extension immediately followed by colon and digits) -- NOT a general heuristic -- so the matcher has a closed, tiny edge surface and does not false-positive on URLs (host:port), clock times, or ranges.

Routed next-candidate:
control-packet-line-ref-lint-2026-06-01

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `control-packet-line-ref-lint-2026-06-01`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/control-packet-line-ref-lint-2026-06-01_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `control-packet-line-ref-lint-2026-06-01`
- Active packet: `reports/control_plane/control_packet_line_ref_lint_2026-06-01.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f95e26977c65903f92dc496020a93ba2de26f1f0a4cf312dab5f49227dbb5c1c`
- Indicator artifact: `reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_check_control_packet_line_refs.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/control_packet_line_ref_lint_2026-06-01.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_check_control_packet_line_refs.py`
  - `mu/tools/checks/check_control_packet_line_refs.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `reports/control_plane/control_packet_line_ref_lint_2026-06-01.md`
  - `reports/deferred/non_blocking/control-packet-line-ref-lint-2026-06-01_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/control-packet-line-ref-lint-2026-06-01.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
