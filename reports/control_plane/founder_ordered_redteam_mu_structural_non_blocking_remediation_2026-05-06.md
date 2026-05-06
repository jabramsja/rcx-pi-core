# Founder Ordered Redteam Mu Structural Non-Blocking Remediation

Date: 2026-05-06
Status: QUEUED - HARD STOP BEFORE IMPLEMENTATION
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: /mu structural
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`
Queue order: `/mu` structural remediation, ordered last after all non-`/mu` blocking and non-blocking remediation packets and after `/mu` structural blocking packet creation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the non-blocking `/mu` structural follow-up from the founder
ordered redteam audit output. It is a hard stop before implementation. The
queue-organization wave may create this packet and its tracker entry, but must
not dispatch or implement the `/mu` structural remediation.

## Source Finding

### N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally Executed

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: JavaScript engine pipeline, evidence-walker seed wiring, ontology
promotion evidence collection.

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`:

- Lines 36-45: `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:597`
  through `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:600` state trace
  walking is structural via `evidence_walker.v1.json`;
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:609` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:614` load the seed and
  execute it through `run_mu`; `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:619`
  through `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:653` retain a
  boundary fallback for walker stalls and boundary post-processing.
- Lines 46-49: `mu/host/js/engine/pipeline.js:785` defines
  `collectOntologyEvidence`, and `mu/host/js/engine/pipeline.js:792` through
  `mu/host/js/engine/pipeline.js:811` drain the trace with host `while`, `Set`,
  and `sort` operations.
- Lines 50-53: `mu/host/js/cli/main.js:39` registers
  `evidence_walker.v1.json` with the note that it is "registered but not
  loaded at runtime"; the projection ID entry at `mu/host/js/cli/main.js:154`
  repeats that it is registered but not loaded at runtime.
- Lines 54-56: `mu/tests/l4_gates/test_evidence_walker_gate.py:46` through
  `mu/tests/l4_gates/test_evidence_walker_gate.py:47` classify the JS gate as
  registry source-lock, not runtime parity.
- Lines 57-59: `mu/docs/core/L3SubstrateArchitecture.v0.md:47` marks
  `evidence_walker.v1` as Python-only, so current repository documentation does
  not claim JS runtime parity for this seed.

## Remediation Scope For Future Wave

- Resolve or explicitly bound the JS ontology evidence proof-class mismatch.
- Do not treat the current finding as a live JS production parity contradiction
  unless fresh source evidence proves the repository now claims JS structural
  execution for `evidence_walker.v1`.
- Preserve the audit classification: non-blocking proof-class mismatch, not a
  blocking runtime defect.

## Hard Stop

Do not implement this `/mu` structural remediation from the queue-organization
wave. Stop after creating this packet and the matching tracker entry. A later
founder-authorized implementation wave must explicitly re-enter the dispatcher
pipeline before editing `/mu` structural code or tests.

## Stop Conditions

- Stop if current docs/tests/source truth proves the proof-class mismatch has
  already been resolved or intentionally scoped; update the tracker instead of
  implementing stale work.
- Stop if remediation would widen JS production claims without adding matching
  structural execution proof.
- Stop if Python/JS substrate parity or proof-class honesty cannot be preserved.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- JS ontology evidence collection claims, tests, and source behavior are aligned
  as source-lock-only, Python-only, or structurally executed in JS with proof.
- Any future runtime parity claim is backed by behavioral or structural
  execution evidence rather than registry source-lock alone.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the
`[FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NON-BLOCKING-REMEDIATION]` entry under
`[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID, category
`/mu structural`, severity `non-blocking`, source audit packet path, the
hard-stop marker, and the acceptance evidence once a later authorized
implementation wave runs.
