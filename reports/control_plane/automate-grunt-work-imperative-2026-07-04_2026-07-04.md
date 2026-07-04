# Add a standing imperative (AUTOMATE THE GRUNT WORK) to rcx_session_protocol.sh so both orchestrators automate recurring manual ops into the pipeline

Date: 2026-07-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: automate-grunt-work-imperative-2026-07-04
Phase-A-Lock: LOCKED
Purpose: FOUNDER emphatic directive 2026-07-04: 'you orchestrate; the pipeline/recovery does the grunt work'. The claude-side is persisted (CLAUDE.md rule 8 + memory feedback_automate_grunt_work + hourly cron), but the SHARED cross-orchestrator surface `mu/tools/session/rcx_session_protocol.sh` (which runs on the hourly protocol cron, preflight, AND at CODEX startup) does not yet carry it -- so orchestrator=codex would not see it. Add the directive as a NEW standing imperative in section `(b) SHARED STANDING IMPERATIVES` of that script so BOTH orchestrators enumerate it, and a hermetic test that asserts the new imperative is present.

## Code-truth note (supersedes stale packet/tracker prose)

Verified against current dev (`mu/tools/session/rcx_session_protocol.sh`, lines ~51-67):

- Section `(b) SHARED STANDING IMPERATIVES` currently has **6 UNNUMBERED dash bullets** rendered as `echo "    - <LABEL>: ..."`, in this order: `POLYMORPHIC` (1st), `PIPELINE / BUILDERS ONLY` (2nd), `MOST-STRUCTURAL / NEVER HOST-SEMANTICS` (3rd), `NEVER BEHIND DEV` (4th), `EDIT-OWNERSHIP` (5th), `AUTONOMOUS` (6th / last).
- The section that follows is `(c) KEY PIPELINE COMMANDS` (not "KEY COMMANDS").
- The script uses **no numbering** anywhere in section (b) (`grep -cE '(imperative|IMPERATIVE) *(1[01]|10|numbered)' = 0`).

Therefore the earlier framing -- "10 numbered imperatives", "EDIT OWNERSHIP as #10", "add an 11th / numbered 11 imperative", "KEY COMMANDS section" -- is FALSE and is superseded here by code truth. The same stale framing lives in the TASKS.md tracker-sync note (`TASKS.md`: "enumerates 10 standing imperatives" / "numbered 11" / "imperative 11"); that prose is out of this packet's write scope (this wave writes ONLY the packet, the script, and a test), so it is flagged as superseded rather than edited. The note's **deterministic `evidence_command`** (the `bash -n` + marker `grep` below) is unaffected by the stale prose and remains the authority; it is fully satisfiable by this plan.

The correct change: append AUTOMATE THE GRUNT WORK as the **7th, UNNUMBERED dash bullet** at the end of section (b) (after the `AUTONOMOUS` bullet, before the section-terminating blank line and section `(c)`), matching the existing `echo "    - <LABEL>: ..."` style. No renumbering; the founder-facing text of the existing 6 bullets is not touched.

## Scope

Files and surfaces in scope:

- `mu/tools/session/rcx_session_protocol.sh` -- append one new UNNUMBERED dash bullet (label `AUTOMATE THE GRUNT WORK`) as the final bullet of section `(b) SHARED STANDING IMPERATIVES`, in the existing `echo "    - ..."` continuation style, positioned after the `AUTONOMOUS` bullet (script line ~66) and before the `echo ""` that closes section (b) (script line ~67) / section `(c) KEY PIPELINE COMMANDS`. The bullet body carries the automate-grunt-work directive: you orchestrate; the pipeline/recovery does the grunt work -- land any recurring manual op into the AUTOMATIC pipeline layer (recovery_gate / commit_executor / a deterministic script) so BOTH orchestrators inherit it, never a hand-run one-off.
- A hermetic test under `tests/tools/` (e.g. `tests/tools/test_session_protocol_imperatives.py`) that reads the script file and asserts: (a) the literal marker `AUTOMATE THE GRUNT WORK` is present, and (b) it appears inside section `(b)` -- i.e. after the `(b) SHARED STANDING IMPERATIVES` header and before the `(c) KEY PIPELINE COMMANDS` header -- as a dash bullet. The test is hermetic (reads the file; no subprocess, network, bridge, or DB).
- `TASKS.md` -- tracker-sync authority (READ-ONLY here). The 2026-07-04 tracker sync note for wave `automate-grunt-work-imperative-2026-07-04` (`TASKS.md`) is the single source of truth for this packet's L4 fields (Class `L4_ENABLER`, `target_gate_id: G8`, `evidence_command`, indicator refs, `primary_blocker_class`, `primary_invariant_id`, `boot0_*`, `FOUNDER_OVERRIDE`). Its numbering-related PROSE is superseded per the Code-truth note above; its L4 fields and deterministic `evidence_command` are consumed as-is. This wave does NOT edit TASKS.md.

Out of scope (see Constraints): no runtime/substrate files; L4_ENABLER; edit only the script + the test.

- `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Append the new bullet to `mu/tools/session/rcx_session_protocol.sh`, section `(b)`, as one or more `echo "    - AUTOMATE THE GRUNT WORK: ..."` lines (matching the existing dash-bullet + wrapped-continuation style), placed after the `AUTONOMOUS` bullet's lines and before the section-terminating `echo ""` / section `(c)`. The rendered line MUST contain the literal uppercase marker `AUTOMATE THE GRUNT WORK`. Do not renumber or reword the existing 6 bullets; do not introduce numbering.
2. Add a hermetic test under `tests/tools/` asserting the marker is present AND located within section `(b)` (between the `(b) SHARED STANDING IMPERATIVES` and `(c) KEY PIPELINE COMMANDS` headers). The placement assertion gives the test teeth beyond a bare marker grep, so it fails if the bullet is added in the wrong section.
3. Verify: `bash -n mu/tools/session/rcx_session_protocol.sh` is clean, the marker `grep` passes, and the new test passes (`pytest tests/tools/test_session_protocol_imperatives.py`).

## Constraints

- NOT in scope: any numbering of section (b), and any renumbering / rewording / reordering of the existing 6 bullets (POLYMORPHIC, PIPELINE / BUILDERS ONLY, MOST-STRUCTURAL / NEVER HOST-SEMANTICS, NEVER BEHIND DEV, EDIT-OWNERSHIP, AUTONOMOUS). The change is additive only.
- NOT in scope: runtime/substrate files (`rcx_pi/selfhost/`, `mu/host/`, engine/kernel). This is `L4_ENABLER`; touching runtime dirs is forbidden for this class.
- NOT in scope: editing `TASKS.md` (including its stale numbering prose), `FOUNDER_SESSION_BOOTSTRAP.md`, CLAUDE.md, memory, cron/preflight scripts, section `(a)`/`(c)`/`(d)` of the protocol script, or the `KEY PIPELINE COMMANDS` block.
- NOT in scope: any semantic/behavioral change to the script's control flow -- it stays a read-only, echo-only protocol script; no new commands, exits, or state mutations.

## Stop conditions

- STOP and request founder decision if landing the imperative appears to require numbering / renumbering the existing bullets (rewrites founder-facing text) -- that is explicitly out of the packet scope; do not silently expand it.
- STOP if the change would touch any runtime/substrate dir (`rcx_pi/selfhost/`, `mu/host/`, engine/kernel) -- an `L4_ENABLER` must not.
- STOP if `bash -n` fails, the marker `grep` fails, or the hermetic test fails after the edit -- diagnose and fix before proceeding; do not weaken the test to force green.
- STOP if section (b)/(c) header markers are not found as expected (script structure drifted from this packet's Code-truth note) -- re-verify against current code before editing rather than editing blind.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_session_protocol_imperatives.py`
- hermetic test: `pytest tests/tools/test_session_protocol_imperatives.py -q` (asserts marker present AND within section (b)).

## Acceptance criteria

- `mu/tools/session/rcx_session_protocol.sh` section `(b) SHARED STANDING IMPERATIVES` enumerates a 7th, UNNUMBERED dash bullet whose rendered line contains the literal marker `AUTOMATE THE GRUNT WORK`, in the existing `echo "    - ..."` style, positioned after the `AUTONOMOUS` bullet and before section `(c) KEY PIPELINE COMMANDS`.
- The existing 6 bullets are byte-unchanged (no renumbering, no reordering, no reword); the script introduces no numbering.
- `bash -n mu/tools/session/rcx_session_protocol.sh` exits 0, and the marker `grep` in the evidence_command succeeds.
- A hermetic test under `tests/tools/` passes and asserts BOTH that the marker is present AND that it sits inside section (b) (between the `(b)` and `(c)` headers) -- so a correct-but-misplaced or numbered variant fails.
- No runtime/substrate files are touched; the diff is limited to the script + the new test. `bash -n`-clean, echo-only control flow preserved.
- NOTE: "numbered 11" from the stale tracker/packet prose is intentionally NOT an acceptance criterion -- it is unimplementable against a script that carries no numbering and would require rewriting the 6 existing founder-facing bullets (out of scope). Acceptance is the marker-present-and-correctly-placed criteria above, which the deterministic `evidence_command` + hermetic test fully cover.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `automate-grunt-work-imperative-2026-07-04`.
- Governing packet: this file, `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`.
- TASKS.md authority: the 2026-07-04 tracker sync note for wave `automate-grunt-work-imperative-2026-07-04` (`TASKS.md`) is canonical for this packet's L4 fields (`L4_ENABLER`, `target_gate_id: G8`, `evidence_command`, indicator artifact + collection command, `primary_blocker_class: INTEGRATION`, `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`, `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`, `boot0_track_id: V1`, `boot0_progress_state: HOLD`). Its numbering PROSE is superseded per the Code-truth note; its L4 fields and deterministic `evidence_command` are consumed as-is.
- Authorization: Founder emphatic directive 2026-07-04 (automate-grunt-work must reach codex via the shared session-protocol script). This is a control-surface `L4_ENABLER`; commit automation derives the same-wave override from the line below. FOUNDER_OVERRIDE:automate-grunt-work-imperative-2026-07-04.

FOUNDER_OVERRIDE:automate-grunt-work-imperative-2026-07-04

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `automate-grunt-work-imperative-2026-07-04`
- Active packet: `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`
- Indicator artifact: `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_session_protocol_imperatives.py`
  - `mu/tools/session/rcx_session_protocol.sh`
  - `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `automate-grunt-work-imperative-2026-07-04`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id automate-grunt-work-imperative-2026-07-04 --output reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_session_protocol_imperatives.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/docs/test_growth_caps.py`, `mu/tests/tools/test_session_protocol_imperatives.py`, `mu/tools/session/rcx_session_protocol.sh`, `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: automate-grunt-work-imperative-2026-07-04.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `automate-grunt-work-imperative-2026-07-04`
- Active packet: `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `28884b10212ca42b99f355d45b2969afa85b5ece7b723b004203a37c6f4a0e13`
- Indicator artifact: `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_session_protocol_imperatives.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/docs/test_growth_caps.py`, `mu/tests/tools/test_session_protocol_imperatives.py`, `mu/tools/session/rcx_session_protocol.sh`, `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`, `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`, `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_session_protocol_imperatives.py`
  - `mu/tools/session/rcx_session_protocol.sh`
  - `reports/control_plane/automate-grunt-work-imperative-2026-07-04_2026-07-04.md`
  - `reports/deferred/non_blocking/automate-grunt-work-imperative-2026-07-04_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/automate-grunt-work-imperative-2026-07-04.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
