# N3-Projection-Loader-Numeric-Domain-Policy-2026-05-14

Date: 2026-05-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-projection-loader-numeric-domain-policy-2026-05-14
Class: L4_STRUCTURAL phase plan for /mu host-debt reduction
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md

## Scope

Phase A wrote only this packet:

- reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md

The Phase B implementation is limited to the N3 projection_loader / seed-image numeric-domain boundary. Candidate write set:

- mu/host/python/rcx_pi/selfhost/seed_integrity.py
- mu/host/js/core/seed_loader.js
- mu/tests/engine/test_seed_integrity.py
- mu/tests/parity/test_seed_loading_parity.py
- mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py, only for a production-boundary L4 gate that proves this numeric-domain policy through the real seed-image loaders
- TASKS.md, only for a same-wave L4_STRUCTURAL tracker sync note binding this staged runtime/test diff to the L4 execution contract
- reports/l4_wave_indicators/n3-projection-loader-numeric-domain-policy-2026-05-14.json, only as the same-wave indicator artifact produced by the repo indicator collector
- mu/docs/core/L4ExitChecklist.v0.md, only if current docs need a factual policy update
- mu/docs/core/TypedNumericEnvelopes.v0.md, only if current docs need a factual policy update without reopening P6

No other files are in scope without a new packet or explicit founder authorization.

The Phase B corpus scan gate must read the exact production seed-image corpus paths named by P6 Typed Numeric Envelopes containment discipline (`mu/docs/core/TypedNumericEnvelopes.v0.md:32`). The canonical corpus path set is:

- mu/substrate/
- mu/closures/
- mu/bridge/
- mu/programs/

The scan must cover all four paths above. A generic scan of the "existing seed corpus" or any command/output that omits one of these paths cannot authorize integer-only rejection.

## Work items

1. Ground the Phase B decision in current repo truth before implementation. Read the founder bootstrap contract, STATUS.md, TASKS.md, the N3 autonomous host-debt reduction governing packet, the cited core docs, and the current Python/JS seed loader code before deciding. Prefer current code truth over stale packet wording; if a listed item is already implemented, remove it from pending work and acceptance instead of re-listing it as unresolved.

2. Run a focused corpus scan over exactly the current production seed-image / projection_loader corpus paths: `mu/substrate/`, `mu/closures/`, `mu/bridge/`, and `mu/programs/`. The scan must answer only whether the production seed-image numeric domain is integer-only today. Record the exact command and output, and the command must visibly name all four canonical corpus paths. If the scan omits any canonical path, stop with NO-GO and revise the packet before implementation. If the scan finds non-integer numeric values required by current production seeds, stop with NO-GO and do not implement an integer-only rejection policy in this wave.

3. If the corpus evidence supports integer-only production seed images, narrow the loader boundary policy to reject non-integer JSON numeric values in both Python and JavaScript seed-image loading paths. Preserve existing NaN/Inf rejection behavior and make rejection parity explicit across substrates. This is a boundary-validity rule for production seed images, not a new Mu semantic layer.

4. Add or adjust focused tests for Python/JS rejection parity. Required coverage includes current NaN/Inf rejection, finite non-integer JSON numbers, integer acceptance for existing seed corpus, and parity of failure class/message expectations where the existing test style requires it.

5. Update docs only if needed to keep governing policy truthful. Any doc change must preserve the existing P6 decision that canonical seeds remain integer-only unless the founder reopens P6, and must preserve the L4ExitChecklist productionization blockers for int-range, NaN/Inf, JS decoder, migration, and integrity-chain policy until separately closed by evidence.

6. Keep ratchets and rollback bounded. Do not update ratchet baselines for this policy lock unless a separate blocker proves the ratchet model is wrong. Rollback must be a straight revert of the future Phase B write set, with no migration or baseline unwind required.

7. Bind the staged runtime/test diff to L4 closeout governance. Add a same-wave `TASKS.md` tracker sync note, add or extend a real L4 gate under `mu/tests/l4_gates/` that proves Python/JS seed-image numeric-domain rejection through production loaders, and collect the same-wave indicator artifact with `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-projection-loader-numeric-domain-policy-2026-05-14 --output reports/l4_wave_indicators/n3-projection-loader-numeric-domain-policy-2026-05-14.json`. The tracker note must include the exact L4_STRUCTURAL fields required by `tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-numeric-domain-policy-2026-05-14`.

8. Record the structural automation debt created by Bridge Round 2 as a follow-up pipeline/root-fix wave. The follow-up must mechanize Phase A / packet generation or review so future L4_STRUCTURAL runtime packets cannot omit `TASKS.md`, an L4 gate path, and a same-wave indicator artifact from the candidate write set. This follow-up is control-plane automation only; it must not add host semantics or broaden Mu runtime behavior.

## Phase B Corpus Scan Evidence

Focused scan command:

```bash
python3 - mu/substrate/ mu/closures/ mu/bridge/ mu/programs/ <<'PY'
import json
import re
import sys
from pathlib import Path
paths = [Path(p) for p in sys.argv[1:]]
number_re = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
non_finite_re = re.compile(r'(?<![A-Za-z0-9_])(?:NaN|Infinity|-Infinity)(?![A-Za-z0-9_])')
json_files = []
non_integer = []
non_finite = []
for root in paths:
    for path in sorted(root.rglob('*.json')):
        json_files.append(path)
        text = path.read_text(encoding='utf-8')
        in_string = False
        escaped = False
        i = 0
        while i < len(text):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
                i += 1
                continue
            m_nf = non_finite_re.match(text, i)
            if m_nf:
                non_finite.append((str(path), m_nf.group(0)))
                i = m_nf.end()
                continue
            m = number_re.match(text, i)
            if m:
                literal = m.group(0)
                if '.' in literal or 'e' in literal.lower():
                    non_integer.append((str(path), literal))
                i = m.end()
                continue
            i += 1
print('paths=' + ' '.join(str(p) + '/' if not str(p).endswith('/') else str(p) for p in paths))
print(f'json_files={len(json_files)}')
print(f'non_integer_numeric_literals={len(non_integer)}')
for path, literal in non_integer:
    print(f'non_integer {path}: {literal}')
print(f'non_finite_numeric_literals={len(non_finite)}')
for path, literal in non_finite:
    print(f'non_finite {path}: {literal}')
PY
```

Focused scan output:

```text
paths=mu/substrate/ mu/closures/ mu/bridge/ mu/programs/
json_files=17
non_integer_numeric_literals=0
non_finite_numeric_literals=0
```

Decision: GO for the bounded loader-boundary integer-only rejection policy. The command visibly names and scans all four canonical production seed-image corpus paths from `mu/docs/core/TypedNumericEnvelopes.v0.md:32`, and the current corpus does not require non-integer or non-finite numeric JSON literals.

## Phase B Local Evidence

- Grounding readback completed for `FOUNDER_SESSION_BOOTSTRAP.md`, `STATUS.md`, `TASKS.md`, `CHANGELOG.md`, `reports/README.md`, `mu/docs/core/TypedNumericEnvelopes.v0.md`, `mu/docs/core/L4ExitChecklist.v0.md`, the N3 seed-image boundary governing packet lineage, and the current Python/JavaScript seed loader code.
- Python seed-image loading now rejects JSON decimal/exponent numeric syntax and non-standard NaN/Infinity constants at the byte-boundary parse step without adding a Mu semantic numeric layer.
- JavaScript seed-image loading now scans the checksum-verified JSON image text before `JSON.parse` so decimal/exponent numeric syntax is rejected before JS collapses `1.0` or `1e0` into `1`.
- Focused tests cover finite non-integer rejection, retained NaN/Infinity rejection, integer seed-image acceptance, and Python/JS byte-boundary parity for the canonical production corpus.
- Docs were not changed because P6 already states canonical seeds remain integer-only unless founder sign-off reopens P6, and the L4 exit checklist already preserves the projection-loader productionization blockers for int range, NaN/Inf, JS decoder, migration, and integrity-chain policy.

Focused local validation:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/engine/test_seed_integrity.py mu/tests/parity/test_seed_loading_parity.py --tb=short
```

```text
82 passed in 2.26s
```

## Closeout Governance Binding

Bridge Round 1 and Round 2 reproduced that same-wave L4 tracker/indicator binding is required before this runtime package can be merge-ready:

- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-numeric-domain-policy-2026-05-14` failed because the wave id was not found in any tracker sync note.
- The required closeout files are now authorized in this same packet: `TASKS.md`, `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`, and `reports/l4_wave_indicators/n3-projection-loader-numeric-domain-policy-2026-05-14.json`.
- The governance binding must not change runtime semantics beyond the already-reviewed numeric-domain boundary policy. It must bind the existing staged runtime/test behavior to the L4 execution contract and record the follow-up automation wave for preventing this packet-generation omission.

## Constraints

- Do not make Python or JavaScript smarter as semantic layers.
- Do not add host-only interpretation, lambda/theater, new bootstrap primitives, typed numeric envelopes, binary/TLV productionization claims, N3 closure claims, D010 production-readiness claims, or ratchet baseline changes.
- Do not widen from production seed-image numeric-domain policy into smaller-image work, registry redesign, scheduler behavior, engine semantics, seed semantics, projection semantics, host authority inventory redesign, or pipeline machinery.
- Do not claim TASKS.md authorization proves every pending work item is still unlanded. Current code truth decides whether a listed item remains pending.
- Do not edit docs merely to echo implementation. Docs are in scope only for factual policy alignment or retained stop-condition wording.
- Do not create new files outside the authorized same-wave indicator artifact path.

## Stop conditions

- STOP with NO-GO if the focused corpus scan shows current production seed images require non-integer numeric values.
- STOP with NO-GO if the focused corpus scan command/output does not explicitly include all four canonical production seed-image corpus paths: `mu/substrate/`, `mu/closures/`, `mu/bridge/`, and `mu/programs/`.
- STOP with NO-GO if the implementation would require reopening P6 Typed Numeric Envelopes, adding typed numeric envelopes, or accepting substrate-specific numeric semantics.
- STOP with NO-GO if Python and JavaScript cannot enforce the same loader-boundary rejection policy without host-only interpretation.
- STOP with NO-GO if the change requires new host authority sites, new bootstrap primitives, binary/TLV productionization, or ratchet baseline updates.
- STOP and revise the plan if current code truth proves the requested policy is already fully landed or proves a listed acceptance criterion is obsolete.
- STOP if any needed edit falls outside the candidate write set above.
- STOP with NO-GO if the L4 governance binding would require changing runtime behavior, adding host semantics, or claiming D010/N3/L4 closure.

## Acceptance criteria

Phase A packet acceptance, retained for lineage:

- This packet contains Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The packet names the exact governing packet path and same-wave id.
- The packet includes a detector-visible same-wave authorization line: FOUNDER_OVERRIDE:n3-projection-loader-numeric-domain-policy-2026-05-14.
- The packet records the Phase A file-only boundary separately from the Phase B implementation write set.
- The packet names the exact production seed-image corpus path set required for the Phase B corpus scan gate: `mu/substrate/`, `mu/closures/`, `mu/bridge/`, and `mu/programs/`.

Phase B local acceptance:

- The focused corpus scan is recorded with the command/output used to prove the current production seed-image numeric domain, and the command/output explicitly covers all four canonical corpus paths: `mu/substrate/`, `mu/closures/`, `mu/bridge/`, and `mu/programs/`.
- Python and JavaScript seed-image loaders either both reject finite non-integer JSON numbers and NaN/Inf at the boundary, or the wave exits NO-GO with the exact reason.
- Existing integer-only production seed images continue to load on both substrates.
- Parity tests cover accepted integers and rejected non-integers/NaN/Inf without relying on host-only semantic interpretation.
- The same-wave `TASKS.md` tracker note binds this diff as `Class: L4_STRUCTURAL`, includes `host_semantics_delta_before`, `host_semantics_delta_after`, `structural_artifact_ref`, `evidence_command`, `post_gate_contract_sweep`, `workload_target: host_debt_reduction`, `indicator_artifact_ref`, and `indicator_collection_command`, and includes `FOUNDER_OVERRIDE:n3-projection-loader-numeric-domain-policy-2026-05-14`.
- The L4 gate proves the numeric-domain policy through production Python and JS seed-image loader entry points rather than inline parser simulation.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-numeric-domain-policy-2026-05-14` passes before closeout.
- The packet or tracker records a follow-up automation wave that mechanizes L4_STRUCTURAL packet write-set completeness for future runtime waves.
- Any doc update is limited to factual policy alignment and does not close D010, N3, P6, or L4 productionization gates.
- Host semantics and authority ratchets remain unchanged unless a separate accepted packet authorizes a ratchet repair.
- Proof limits are explicit: this wave may prove a bounded loader-domain policy only; it does not prove smaller-image readiness, binary/TLV readiness, D010 production readiness, N3 closure, or full bootstrap primitive elimination.

## Grounding / Authorization

TASKS.md is the single source of truth for authorized work, and unlisted work is not to be implemented (`TASKS.md:3-4`). TASKS.md also requires explicit VECTOR/NEXT promotion discipline: NEXT mode permits only bounded, testable slices with mirrored Python/JS semantics (`TASKS.md:75-80`), and VECTOR to NEXT promotion requires complete design, locked semantics, bounded testable implementation scope, and observability before mechanics (`TASKS.md:83-88`).

The active N3 projection_loader / seed-image lane is grounded in `[NEXT-CODEX-POST-REDTEAM]` tracker notes for the production boundary and test surface (`TASKS.md:340-344`), the seed-image boundary adapter implementation and runtime retry (`TASKS.md:357-358`), the N3 autonomous host-debt reduction governing packet (`TASKS.md:346`), and the current N3 manifest reduction host-debt lane with zero host-semantics-delta / baseline-preservation obligations (`TASKS.md:362`). The retained numeric policy boundary is also consistent with the TASKS P6 decision that seeds remain integer-only unless P6 is reopened (`TASKS.md:666`) and with P6 Typed Numeric Envelopes containment discipline naming canonical seed paths `mu/substrate/`, `mu/closures/`, `mu/bridge/`, and `mu/programs/` (`mu/docs/core/TypedNumericEnvelopes.v0.md:32`).

Governing packet for this Phase A plan:

- reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md

Required same-wave authorization for control-surface automation:

FOUNDER_OVERRIDE:n3-projection-loader-numeric-domain-policy-2026-05-14

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-projection-loader-numeric-domain-policy-2026-05-14`
- Active packet: `reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-projection-loader-numeric-domain-policy-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
  - `mu/tests/engine/test_seed_integrity.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md`
  - `reports/l4_wave_indicators/n3-projection-loader-numeric-domain-policy-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
