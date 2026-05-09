# Archived Founder Ordered Redteam Repo Code Audit - Non-Blocking Findings

Archive status: CLOSED by `deferred-active-mu-structural-nonblocking-cleanup-2026-05-09`.
Closure evidence: PR #915 implemented the selected proof-class outcome for
`N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally
Executed`; `TASKS.md` records the wave as implemented/local evidence and
separately tracker-synced. The current governing packet for
`founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
states the selected outcome as intentionally Python-only `evidence_walker.v1`
runtime with JS source-lock-only registry proof. This audit source packet is
therefore closed and must not remain in the active deferred lane.

Original packet follows.

# Founder Ordered Redteam Repo Code Audit - Non-Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - NON-BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-repo-code-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_repo_code_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-repo-code-audit-2026-05-05

This packet records non-blocking repo-code findings only. The audit wave did
not implement remediation.

## Scope Executed

- Python/JavaScript substrate sync under `mu/host/python/` and `mu/host/js/`.
- Stage0, lowering, runtime, and execution-boundary paths under `mu/`.
- Structural `/mu` seed, registry, bridge, program, projection, and runtime
  wiring that carries current production, parity, Stage0, or L4 claims.
- Narrow tests/docs/tooling reads only where needed to prove or disprove the
  code claim.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## N1 - JS Ontology Evidence Collection Is Source-Locked, Not Structurally Executed

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: JavaScript engine pipeline, evidence-walker seed wiring, ontology
promotion evidence collection.

Evidence:

- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:597` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:600` state that trace
  walking is structural via `evidence_walker.v1.json`, with boundary
  post-processing after walker output.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:609` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:614` load
  `evidence_walker.v1.json` and execute it through `run_mu`.
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:619` through
  `mu/host/python/rcx_pi/selfhost/engine_pipeline.py:653` still contain a
  boundary fallback for walker stalls and boundary post-processing.
- `mu/host/js/engine/pipeline.js:785` defines `collectOntologyEvidence` in JS,
  and `mu/host/js/engine/pipeline.js:792` through
  `mu/host/js/engine/pipeline.js:811` drain the trace with host `while`,
  `Set`, and `sort` operations.
- `mu/host/js/cli/main.js:39` registers `evidence_walker.v1.json` with the
  inline note that it is "registered but not loaded at runtime". The projection
  ID entry at `mu/host/js/cli/main.js:154` repeats that it is registered but
  not loaded at runtime.
- `mu/tests/l4_gates/test_evidence_walker_gate.py:46` through
  `mu/tests/l4_gates/test_evidence_walker_gate.py:47` classify the JS gate as
  registry source-lock, not runtime parity.
- `mu/docs/core/L3SubstrateArchitecture.v0.md:47` marks
  `evidence_walker.v1` as Python-only, so the current repository documentation
  does not claim JS runtime parity for this seed.

Why this is non-blocking:

- The code and tests are explicit that JS only source-locks/registers the
  evidence walker today. The live docs also mark `evidence_walker.v1` as
  Python-only.
- This does not currently contradict the documented JS production surface, but
  it remains open advisory residue for any future claim that ontology evidence
  collection has cross-substrate structural execution or that JS has eliminated
  the host trace-drain path for this operation.

Remediation is not authorized in this audit wave. Follow-up remediation must be
ordered by the founder remediation rule after all four audit waves classify
findings, with `/mu` structural remediation ordered last and hard-stopped before
implementation.
