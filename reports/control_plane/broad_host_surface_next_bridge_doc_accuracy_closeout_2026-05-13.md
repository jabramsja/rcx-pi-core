# Broad Host-Surface Next Bridge Doc Accuracy Closeout

Date: 2026-05-13
Status: Phase B (implementation-complete, bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13
Class: L4_ENABLER
Category: docs/control-plane doc accuracy cleanup
Phase-A-Lock: LOCKED
Source residue: reports/deferred/non_blocking/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers.md
Parent structural wave: broad-host-surface-next-boundary-slice-2026-05-13
FOUNDER_OVERRIDE:broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13

## Scope

Files in scope for the implementation wave:

- `TASKS.md`, only for the same-wave tracker note and to correct the cited lax-copy overclaim.
- `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`, only for the cited lax-copy overclaim.
- `reports/deferred/README.md`, only to refresh the active deferred inventory after archive cleanup.
- `reports/deferred/non_blocking/README.md`, only if needed to keep active non-blocking inventory truthful.
- `reports/deferred/non_blocking/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers.md`, only as the generated bridge packet to close and archive.
- `reports/archive/deferred/`, only as the closed-by archive destination for
  generated bridge packets resolved by this closeout, including the re-entry
  same-wave closeout bridge residue.
- This governing packet.

No runtime, Stage0 implementation, seed, scheduler, registry, parity, production
`/mu`, host-oracle, or Claude-related files are in scope.

## Work Items

1. Correct the parent control-plane packet so it no longer claims every lax
   array trap case returns `null`. The bridge residue names
   `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`
   and the direct probe evidence shows strict trap cases convert to
   `Stage0VMError`, while lax `array_ownKeys` and `array_descriptor` copied
   `[1]` instead of returning `null`.
2. Correct the matching `TASKS.md` tracker wording so it no longer repeats
   "lax copy returns null" as an unqualified claim.
3. Preserve the strict boundary claim: exported JS Stage0 `muCopy(..., true, ...)`
   must still fail closed to `Stage0VMError` without leaking host trap messages.
4. After targeted evidence proves both wording fixes, archive
   `reports/deferred/non_blocking/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers.md`
   under `reports/archive/deferred/` with a
   `closed-by-broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13`
   suffix.
5. Refresh deferred lane indexes so the active deferred inventory matches the
   direct `find reports/deferred/...` output after the archive move.
6. Leave N3 broad host-surface boundary active in
   `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`.
   This closeout does not implement or close N3.

## Constraints

- Do not implement broad host-surface reduction in this wave.
- Do not edit JS/Python runtime, Stage0 implementation, parity tests, seed
  registries, scheduler code, production `/mu`, host-oracle code, or
  Claude-related files.
- Do not create a new active deferred packet from this closeout.
- Do not archive N3 or represent PR #945 as broad host-surface elimination.
- Do not claim a behavior is fixed from docs alone; reproduce the targeted
  strict/lax proxy matrix or preserve the bridge evidence as the reason for the
  wording change.

## Stop Conditions

- Stop if targeted source evidence shows either cited DOC_ACCURACY finding is
  already corrected in current repo truth.
- Stop if the correction would require runtime or Stage0 implementation changes.
- Stop if active deferred inventory contains additional non-README files beyond
  the generated bridge residue and the retained N3 packet; route those
  separately instead of broadening this wave.
- Stop before archive cleanup if either cited wording fix has not landed.
- Stop before commit if same-wave `TASKS.md` tracker authority is not
  detector-visible for this wave id and packet.

## Acceptance Criteria

- The parent control-plane packet and `TASKS.md` no longer claim all lax array
  trap cases return `null`.
- The strict `muCopy(..., true, ...)` fail-closed claim remains intact and is
  supported by the focused Stage0 test or an equivalent direct Node probe.
- The generated PR #945 bridge residue packet is absent from
  `reports/deferred/non_blocking/` and present under `reports/archive/deferred/`
  with a same-wave closed-by name.
- No same-wave generated closeout bridge packet remains active in
  `reports/deferred/non_blocking/`.
- `reports/deferred/README.md` and `reports/deferred/non_blocking/README.md`
  match current active deferred inventory after the archive move.
- N3 broad host-surface boundary remains active and hard-stopped.

Required validation:

```bash
git status --short
find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' -print | sort
rg -n "broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13|FOUNDER_OVERRIDE:broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13" TASKS.md
rg -n "lax.*null|array trap|broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers" TASKS.md reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md reports/deferred reports/archive/deferred
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance::test_node_mu_copy_proxy_traps_fail_closed_without_native_error --tb=short -p no:cacheprovider
./tools/checks/check_docs_consistency.sh
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13
```

## Grounding / Authorization

- `TASKS.md` carries `[NEXT-CODEX-POST-REDTEAM]` as the active founder-ordered
  post-redteam queue and records this wave as
  `FOUNDER-ORDERED-REDTEAM-BRIDGE-DOC-ACCURACY-CLOSEOUT`.
- Source residue packet:
  `reports/deferred/non_blocking/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers.md`.
- Parent structural packet:
  `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`.
- Same-wave authority:
  `FOUNDER_OVERRIDE:broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13`.

## Re-entry Resolution

- Re-entry found same-wave generated active deferred packets for indicator
  byte-reproducibility review and stale staged-file list review:
  `reports/deferred/non_blocking/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13_bridge_nonblockers.md`.
- The L4 indicator collector documents environment-dependent timing provenance,
  so a repeated run is expected to produce fresh timing and timestamp values.
  This closeout keeps the indicator as the required L4 contract receipt and uses
  the focused Stage0 pytest command above as the behavioral proof for the strict
  `muCopy(..., true, ...)` fail-closed claim.
- The generated same-wave bridge findings are archived under
  `reports/archive/deferred/` and are not active deferred work.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_next_bridge_doc_accuracy_closeout_2026-05-13.md`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/archive/deferred/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers_closed-by-broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.md`
  - `reports/archive/deferred/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13_bridge_nonblockers_closed-by-broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.md`
  - `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`
  - `reports/control_plane/broad_host_surface_next_bridge_doc_accuracy_closeout_2026-05-13.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_next_bridge_doc_accuracy_closeout_2026-05-13.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `eb3b01daece2b54809727fe4b18c9a42e5d95b0e79a9a1197f0759af72f79b6d`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13 --output reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/broad_host_surface_next_bridge_doc_accuracy_closeout_2026-05-13.md. (2) Pre-commit supervisor package is staged at .scratch/phase_b_supervisor_package.json with 8 wave-owned file(s). (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`
- Current staged files:
  - `TASKS.md`
  - `reports/archive/deferred/broad-host-surface-next-boundary-slice-2026-05-13_bridge_nonblockers_closed-by-broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.md`
  - `reports/archive/deferred/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13_bridge_nonblockers_closed-by-broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.md`
  - `reports/control_plane/broad_host_surface_next_boundary_slice_2026-05-13.md`
  - `reports/control_plane/broad_host_surface_next_bridge_doc_accuracy_closeout_2026-05-13.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/l4_wave_indicators/broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
