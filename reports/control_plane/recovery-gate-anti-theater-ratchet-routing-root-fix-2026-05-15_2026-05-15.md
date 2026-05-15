# Recovery-Gate-Anti-Theater-Ratchet-Routing-Root-Fix-2026-05-15

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15
Class: L4_ENABLER
Phase-A-Lock: LOCKED

Purpose: define the bounded control-surface root-fix plan for the manual recovery defect observed after `n3-seed-dependency-registry-source-lock-2026-05-15`. This packet is a Phase A plan only; it does not implement the recovery-gate changes.

## Scope

Files and directories in scope for the downstream implementation wave:

- `mu/tools/executors/recovery_gate.py` for bounded recovery routing, Tier 3 prompt context, and delegate-scope validation changes.
- `mu/tests/tools/test_recovery_gate.py` for focused recovery-gate regression coverage.
- `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md` as the governing packet.
- Same-wave `TASKS.md` tracker note and `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json` only during downstream implementation/commit packaging.
- Same-wave generated deferred report only if recovery automation actually produces one.

Evidence inputs in scope for downstream implementation decisions:

- Recovery status for predecessor wave `n3-seed-dependency-registry-source-lock-2026-05-15`: step `run_pre_push_script`, failure class `l4_contract_violation`, state `tier3_exhausted`, current iteration `3`, recovered `false`.
- Recovery log sequence for the predecessor failure: iteration 1 routed toward anti-theater allowlist expansion for `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py::TestSeedDependencyParity::test_js_seed_dependencies_match_python`; iteration 2 referenced missing `reports/deferred/n3-seed-dependency-registry-source-lock-2026-05-15.md`; iteration 3 had no file contents available and requested shell inspection.
- Current packet reviewer evidence: the previous packet had only `## Scope` and `## Request from Post-Merge Supervisor`, and lacked required plan sections plus same-wave L4_ENABLER authorization text.

- `reports/deferred/non_blocking/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Replace the stub packet with a real Phase A plan carrying the required sections, explicit scope, constraints, stop conditions, acceptance criteria, and same-wave authorization.
2. In downstream implementation, add bounded anti-theater ratchet diagnostic context or routing so Tier 3 can identify the named failing pytest method and the policy direction without broad prompt dumping.
3. Encode recovery policy that new anti-theater ratchet failures must not be fixed by allowlist expansion unless an explicit founder or user directive authorizes that path. Default direction is proof-quality behavioral test repair or clear escalation.
4. Prevent `delegate_implementer` from inventing missing deferred paths for this failure shape. If delegation is used, `files_in_scope` must be existing, bounded, and tied to the failing artifact or recovery tooling.
5. Add focused regression tests proving the new recovery route rejects allowlist-first recovery, does not reference missing deferred paths, preserves prompt-size caps, preserves dangerous-command restrictions, and preserves normal delegate validation for existing control-surface paths.
6. Keep commit packaging mechanically grounded with same-wave tracker and indicator artifacts when the downstream implementation proceeds.

## Constraints

- This Phase A rewrite changes only this packet.
- No runtime, substrate, seed, loader, Stage0, scheduler, projection, checksum, generated seed artifact, production `/mu` semantic, or ratchet-baseline changes are authorized by this packet.
- Do not edit anti-theater allowlists as part of this root fix.
- Do not touch predecessor wave test files unless Phase A/bridge convergence later proves a narrow anti-theater test-file delegate route is required and locks non-runtime rejection tests.
- Do not use broad prompt dumping, contextless shell-command diagnosis, or guessed file paths as the recovery strategy.
- Do not bypass pre-push, CI, git safeguards, receipt checks, or L4 execution-contract enforcement.
- Do not treat TASKS predecessor evidence as proof that every future work item remains unlanded; downstream implementation must prefer current code truth if a blocking finding proves a work item already landed.

## Stop conditions

Stop and return for bridge/founder review if any of the following occurs:

- The repair requires runtime, substrate, seed, Stage0, scheduler, projection, generated seed, production `/mu`, checksum, or ratchet-baseline edits.
- The only available recovery path is anti-theater allowlist expansion without an explicit founder or user directive.
- The design requires broad prompt dumping or contextless shell inspection rather than bounded diagnostic context.
- Delegate scoping requires nonexistent deferred files or paths not tied to the failing artifact/recovery tooling.
- Focused tests cannot preserve existing prompt-size caps, dangerous-command restrictions, or delegate validation behavior.
- Same-wave authorization cannot be represented mechanically for L4_ENABLER control-surface enforcement.

## Acceptance criteria

- This packet contains the required Phase A sections: `Scope`, `Work items`, `Constraints`, `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization`.
- This packet contains detector-visible same-wave L4_ENABLER authorization for `recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15`.
- Downstream implementation keeps the write set bounded to recovery tooling/tests plus same-wave governance artifacts listed in `Scope`.
- Downstream implementation makes Tier 3 recovery for the named anti-theater ratchet failure route away from allowlist-first repair and away from missing deferred-path invention.
- Required downstream validations:
  - `python3 -m py_compile mu/tools/executors/recovery_gate.py`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py --tb=short`
  - Focused regressions for anti-theater ratchet guidance rejecting allowlist-first recovery, avoiding missing deferred paths, preserving prompt caps, preserving dangerous-command restrictions, and preserving normal delegate validation.
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `./tools/checks/check_docs_consistency.sh`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15`

## Grounding / Authorization

- Governing packet: `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md`.
- TASKS targeted evidence: the current `[NEXT-CODEX-POST-REDTEAM]` predecessor context appears at `TASKS.md:359` for `n3-seed-dependency-registry-source-lock-2026-05-15`, including its pre-commit supervisor package refresh, recovery-adjacent validation command, and standing pipeline-bug-fix override pattern. That predecessor tracker note does not itself provide same-wave authorization for this new packet.
- Reviewer evidence for this rewrite is authoritative: the prior packet lacked the required plan sections and lacked a same-wave L4_ENABLER authorization token.
- FOUNDER_OVERRIDE:recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15
- Authorization: standing pipeline-bug-fix authorization for recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15 as a control-surface L4_ENABLER root fix for the predecessor recovery failure.

Human-facing output footer: `Questions? Concerns? Thoughts? -- Think hard`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15`
- Active packet: `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md`
  - `reports/deferred/non_blocking/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15`
- Active packet: `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `fc0ce82aa1c88e2ab102c400e548cd39bfe92a5f62fe8eeeedf56a3b6c64f8a6`
- Indicator artifact: `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_2026-05-15.md`
  - `reports/deferred/non_blocking/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-gate-anti-theater-ratchet-routing-root-fix-2026-05-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
