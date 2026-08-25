# PR 1219 P0IBRRCP Shared Envelope Framing R4A2 2026-08-25

Date: 2026-08-25
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-SHARED-ENVELOPE-FRAMING-R4A2]
Wave ID: pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25
Phase-A-Lock: LOCKED
Purpose: Land one shared marker-safe agent-envelope framing and nine-key completeness boundary across adapter early-stop detection and authoritative supervisor parsing from exact PR 1243 merge authority, breaking the reciprocal one-sided blockers proved by preserved envelope R2 and adapter-framing R4A.

## Scope

Fresh atomic shared-framing reconstruction from exact PR 1243 merge authority. Phase A reviews only the adapter/supervisor framing contract and adapter nine-key stop completeness. R4B provider-terminal authority, R4C root-exit cleanup, and the remaining nested-shape/persistence envelope validation stay serialized and excluded.

Files and surfaces in scope:

- mu/tools/agents/bridge_adapters.py (MODIFY) -- own one dependency-neutral decoded marker/fence candidate extractor and require all nine existing envelope keys plus an authorized string decision before adapter early-stop is complete.
- mu/tools/agents/bridge_supervisor.py (MODIFY) -- replace only authoritative envelope regex framing with reuse of the same adapter-owned extractor while preserving current required-key, decision, duplicate, ambiguity, stderr, persistence, and lifecycle policy.
- mu/tests/tools/test_agent_bridge_supervisor.py (MODIFY) -- add focused direct extractor/adapter-detection and run_turn/parse_envelope regressions proving shared framing boundaries, supervisor-safe decoded-value gates, fail-closed candidate ordering, nested findings, braces and marker text in strings, optional fences, malformed openings, later valid candidates, and ambiguity.
- TASKS.md (MODIFY) -- preserve every stopped R1/R2/R3/R4A attempt as noncomplete evidence; make R4A2 sole CURRENT; make provider-terminal R4B sole immediate NEXT; serialize root-exit R4C and remaining envelope-validation R3; preserve every task, all five TODO-bearing lines, and the PR/fleet cleanup order.
- reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md (GENERATED) -- sole canonical R4A2 packet.
- reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json (PHASE B GENERATED GOVERNANCE) -- absence during Phase A is expected and is not a Phase A blocker; Phase B creates and stages it after implementation and before Phase B review.
- reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct from exact merge 926aee9de7b5cdd00c0fd72176ed7038b6ff89a0. Do not copy, resume, diff-apply, import, or mutate any preserved envelope or adapter candidate, including R2, R3, or R4A.
2. Implement one adapter-owned dependency-neutral framed-candidate extractor that scans each exact BEGIN_AGENT_ENVELOPE marker and returns every syntactically complete raw-decoded JSON value with its exact source span. A begin or end token immediately prefixed or suffixed by an ASCII identifier character (`[A-Za-z0-9_]`) is a lookalike, not a delimiter. Accept JSON whitespace and either no fence, an exact bare fence, or an exact `json` fence. After the JSONDecoder.raw_decode consumed extent, permit only JSON whitespace before the required next token: END_AGENT_ENVELOPE for an unfenced candidate, or the closing fence followed by JSON whitespace and then END_AGENT_ENVELOPE for a fenced candidate. Reject junk in that interval, an unmatched or stray fence, a missing/reordered closer, and begin/end lookalikes, then continue scanning later exact openings.
3. Return the decoded value and enough exact-span information for both consumers to use the identical syntactic candidate boundary without reparsing with a non-greedy object regex. The extractor is framing-only and may return any JSON type; braces, fences, BEGIN_AGENT_ENVELOPE, and END_AGENT_ENVELOPE text inside a successfully decoded JSON string remain payload data. Alongside that extractor, define the one adapter-owned shared placeholder constant `AGENT_DECISION_PLACEHOLDER = "GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR|SYNTHETIC"` and the type-safe predicate `is_agent_decision_placeholder(decision)`, true if and only if `isinstance(decision, str) and decision == AGENT_DECISION_PLACEHOLDER`. Use that same exported constant in the supervisor's `JSON_SCHEMA_STUB`, and require adapter early-stop detection and supervisor `parse_envelope` to call the same predicate; merely containing `|` never makes a decision a placeholder. Both consumers must gate `isinstance(decoded, Mapping)` before required-key operations and gate `isinstance(decision, str)` before authorized-decision set membership.
4. Use the shared extractor in the agent-envelope branch of adapter early-stop detection. A candidate can arm stop authority only when it is a mapping containing all nine existing envelope keys and its decision is an authorized string. Non-mappings, missing-key mappings, malformed openings, and complete mappings whose decision satisfies the exact shared placeholder predicate are non-authoritative and may be skipped in favor of a later valid candidate. A complete mapping whose decision is non-string or is any unauthorized string that fails that predicate, including every other pipe-bearing string, is fail-closed: it poisons that accumulated agent transcript, so adapter detection returns false even if a valid candidate follows. Preserve the separate meta-envelope branch unchanged.
5. Use the same extractor in supervisor parse_envelope. Before `required.difference`, key access, decision membership, canonicalization, or duplicate/ambiguity handling, reject non-mappings from semantic processing; if no valid mapping remains, raise BridgeError rather than leaking TypeError. After all-nine-key completeness is established, check that decision is a string before set membership. Skip a complete mapping only when its decision satisfies the exact shared placeholder predicate. Raise BridgeError immediately for a complete mapping with a non-string decision or any unauthorized string that fails that predicate, including every pipe-bearing near miss, even when a later candidate is valid. Preserve the existing stdout/stderr authority, missing-key draft recovery, identical-duplicate acceptance, differing-candidate fail-closed ambiguity, raw-output, turn persistence, and downstream semantics. Do not add the remaining nested findings shape or persisted-envelope validation in this wave.
6. Add focused direct extractor/adapter-detection and run_turn/parse_envelope regressions for unfenced, bare-fenced, and json-fenced payloads; nested finding objects; braces/fences/marker text inside strings; malformed openings followed by a valid candidate; every missing key; authorized decisions; delayed complete candidates; identical duplicates; and differing ambiguity. Add standalone semantic-gate cases for framed scalar, null, and list values and for complete mappings with non-string decisions, including a hashable non-string value and an unhashable list: adapter detection must not arm, and supervisor parsing must produce controlled BridgeError rather than TypeError when no authoritative candidate remains. Add mixed-order cases through both consumers that distinguish skip from poison: each framed scalar, null, and list followed by a complete valid authorized mapping must be skipped, so adapter detection returns true and `parse_envelope` accepts the later valid mapping; each complete all-nine-key mapping whose decision is a hashable non-string value or an unhashable list followed by a complete valid authorized mapping must poison arbitration, so adapter detection remains false and `parse_envelope` raises BridgeError on the first complete mapping without accepting the later candidate. Also require the exact placeholder literal followed by a valid candidate to recover to that valid candidate, while each pipe-bearing near miss followed by a valid candidate, including `BOGUS|GO` and `GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR|SYNTHETIC|BOGUS`, must poison arbitration: adapter detection remains false and `parse_envelope` raises BridgeError before accepting the later candidate. Retain the mixed complete unauthorized pipe-free string followed by valid case with the same fatal outcomes. Add negative acceptance cases for identifier-prefixed and identifier-suffixed begin markers, identifier-prefixed and identifier-suffixed end markers, unmatched opening fences, stray closing fences in unfenced form, missing or reordered fence/end delimiters, and non-whitespace junk between the decoded extent and the required closer; assert rejection through direct extraction/detection and parse_envelope, while a separate later exact valid opening remains recoverable where applicable.
7. Update TASKS.md atomically with exact PR 1243 landed truth; truthful preservation of envelope R1/R2, adapter R1/R2/R3, and framing R4A; R4A2 as sole CURRENT; R4B as sole immediate NEXT; R4C then remaining envelope-validation R3; every existing task; all five TODO-bearing lines unchanged; and preservation-first cleanup after PR1219 landing.
8. After implementation, allow normal Phase B packaging to stage only wave-owned files, create and stage the exact indicator, refresh packet scope, bind candidate authority, review, validate, and hand off to providerless commit, push, PR, CI, and merge.
9. After the exact R4A2 merge, create and builder-launch fresh provider-terminal R4B from the actual merge SHA.

## Constraints

- Functional scope is exactly bridge_adapters.py, bridge_supervisor.py, and the existing focused test, plus TASKS.md and same-wave generated governance. Add no functional or test file.
- Do not change provider-terminal recognition or success/error policy, EOF authority, reader callbacks, wait loops, final drains, process-group teardown, root-exit behavior, watchdog semantics, stderr promotion, raw-output format, meta-envelope behavior, or buffered/streaming selection. Those remain R4B/R4C.
- Do not add nested findings container/member validation, persisted-envelope validation, per-field typing, identity binding, migration logic, semantic severity/disposition validation, or generic JSON schema. Those remain in the narrowed envelope-validation successor.
- Do not edit provider configuration, Phase B, recovery, commit, launcher, dispatcher, receipt, runtime, substrate, hosts, seeds, projections, registries, Claude-owned files, or any preserved candidate.
- Malformed scalar provider JSONL remains deferred and cannot block R4A2. Framed scalar, null, or list agent-envelope values are distinct and are in scope only to prove the shared extractor cannot drive adapter or supervisor semantic operations without mapping/string gates. Review only the staged shared-framing/completeness delta and its declared preservation boundary.
- Use launch_wave.py and the normal immutable-source dispatcher, Phase A, Phase B, providerless commit, push, PR, CI, and merge chain. No manual candidate patch, staging, commit, push, PR mutation, merge, or source substitution.
- All implementation and review roles remain Codex; commit remains providerless. Do not weaken candidate authority, staged L4, commit verification, CI, or merge gates.

## Stop conditions

- Stop before launch if exact merge 926aee9de7b5cdd00c0fd72176ed7038b6ff89a0 is unavailable, the fresh target is not clean, an identity collides, or the Codex or providerless path is unavailable.
- Stop as NEEDS_RESCOPING if shared framing/completeness requires any functional or test file outside bridge_adapters.py, bridge_supervisor.py, and test_agent_bridge_supervisor.py.
- Stop and preserve if the same active Phase A blocker repeats after one packet-only correction; do not enter another rewrite loop.
- Stop and preserve if a Phase B reviewer exits without a final verdict; do not let recovery restart Phase A on the same packet.
- Do not stop or widen for provider-terminal policy, root-exit lifecycle, remaining nested/persisted envelope validation, scalar JSONL, preserved nonblockers, docs polish, dynamic fleet counts, later unbuilt configs, or any non-occurring edge case.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- Phase A GO means only the bounded shared-framing/completeness design, scope, stop conditions, acceptance criteria, TASKS authority, and founder override are coherent; no implementation artifact or staged indicator is expected before Phase A GO.
- Only the seven allowlisted paths change and no packet-name normalization alias is created.
- One adapter-owned extractor determines each candidate's raw-decoded JSON extent and exact marker/fence span; adapter early-stop and supervisor parse_envelope both reuse that syntactic stream, and no second non-greedy object framing regex remains authoritative for agent envelopes. Exact token boundaries and opener-selected closer sequencing reject identifier-adjacent marker lookalikes, unmatched or stray fences, missing/reordered delimiters, and non-whitespace post-JSON junk.
- Both consumers apply mapping guards before required-key or key operations and string guards before decision set membership. Framed scalar, null, and list values and unhashable/non-string decisions cannot leak TypeError. Adapter stop completeness requires a mapping containing all nine existing keys and an authorized string decision; malformed, missing-key, and non-object candidates do not arm stop authority, and only a decision satisfying the exact shared placeholder predicate is a skippable placeholder.
- Candidate arbitration is explicit: malformed, non-object, missing-key, and exact-placeholder candidates may be skipped for a later valid candidate, but a complete mapping with a non-string decision or any unauthorized string that fails the exact placeholder predicate, including every other pipe-bearing string, is fatal. A fatal candidate followed by a valid candidate leaves adapter detection false and makes supervisor `parse_envelope` raise BridgeError before accepting the later candidate.

  | First candidate | Later candidate | Adapter early-stop result | Supervisor parsing result |
  | --- | --- | --- | --- |
  | Each framed scalar, null, and list | Complete valid authorized mapping | `true`; skip the non-mapping and arm on the later mapping | Accept the later valid mapping |
  | Complete all-nine-key mapping with the exact placeholder literal | Complete valid authorized mapping | `true`; skip only the exact placeholder and arm on the later mapping | Accept the later valid mapping |
  | Complete all-nine-key mapping with hashable non-string `decision = 0` or unhashable `decision = []` | Complete valid authorized mapping | `false`; the first complete mapping poisons the transcript | Raise BridgeError on the first complete mapping; do not accept the later mapping |
  | Complete all-nine-key mapping with `BOGUS|GO` or `GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR|SYNTHETIC|BOGUS` | Complete valid authorized mapping | `false`; the pipe-bearing near miss poisons the transcript | Raise BridgeError on the near miss; do not accept the later mapping |
- Supervisor parsing preserves existing required-key, decision, stdout/stderr, identical-duplicate, differing-ambiguity, persistence, and downstream behavior after the new safe type gates and explicit fatal-decision ordering.
- Focused tests prove direct extractor/adapter-detection and run_turn/parse_envelope behavior for nested findings, optional fences, braces/fences/marker text inside strings, malformed-opening recovery, each missing key, authorized decisions, delayed complete candidates, identical duplicates, differing ambiguity, standalone framed non-object and non-string-decision cases, scalar/null/list-then-valid recovery through both consumers, complete hashable-non-string-decision/unhashable-list-decision-then-valid poisoning through both consumers, exact-placeholder-then-valid recovery, pipe-bearing-near-miss-then-valid poisoning for both named near misses, unauthorized-pipe-free-string-then-valid poisoning, prefixed/suffixed begin and end lookalikes, unmatched/stray/reordered fences, and non-whitespace junk between the decoded extent and closer.
- No provider-terminal, EOF, callback, wait-loop, final-drain, root-exit, watchdog, stderr-promotion, raw-output, meta-envelope, process-cleanup, nested-shape, or persisted-envelope-validation policy changes in R4A2.
- TASKS truthfully preserves all stopped attempts, selects R4A2 as sole CURRENT and R4B as sole immediate NEXT, serializes R4C before remaining envelope-validation R3, preserves every task and all five TODO-bearing lines, and keeps fleet cleanup ordered after PR1219 landing.
- After implementation and before every Phase B review, normal Phase B packaging stages the candidate, creates and stages the exact same-wave indicator, refreshes packet scope, passes strict staged L4 enforcement, and binds current candidate authority.
- The focused suite, compilation, diff checks, relevant control and receipt checks, providerless commit, push, PR, CI, and merge complete normally.
- After merge, fresh provider-terminal R4B launches from the exact R4A2 merge SHA without resuming or mutating a preserved candidate.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IBRRCP-SHARED-ENVELOPE-FRAMING-R4A2]; wave id `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`.
- TASKS.md authority: the 2026-08-25 tracker sync note for wave `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25` is canonical for this packet's L4 fields.
- Authorization: PR 1243 landed the disposition prerequisite. Envelope R2 proved supervisor-only framing cannot land before adapter alignment; adapter-framing R4A proved adapter-only framing cannot land before supervisor alignment. R4A's one allowed correction identified the atomic shared boundary but its immutable candidate allowlist omitted bridge_supervisor.py, so it was stopped and preserved before another cycle. The founder-directed convergence path is this fresh shared-framing R4A2, then provider-terminal R4B, root-exit R4C, and remaining envelope validation, all builder-launched and serialized.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6586390985f5200e887784338d7d8e1b64a2a8056952881306533312ea879ea3`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`
- Current staged files:
  - `reports/control_plane/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25_2026-08-25.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-shared-envelope-framing-r4a2-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
