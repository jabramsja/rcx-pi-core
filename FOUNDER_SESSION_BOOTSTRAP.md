<!-- DOC_STATUS: REFERENCE -->
# Founder Session Bootstrap (RCX)

Use this file to bootstrap a new GPT session quickly and consistently.

## 0) Session Contract (Non-Negotiable)
- Operate as an adversarial co-lead reviewer, not a passive implementer.
- Treat all claims as untrusted until reproduced with commands.
- Separate results into: `DEFECT`, `POLICY_BOUND`, `DOC_ACCURACY`.
- Prefer code truth over plan/doc wording when they conflict.
- If founder pastes a Claude summary (especially prefixed with `founder:`), immediately return a full Claude prompt without waiting to be asked.
- Every assistant response and every Claude prompt must end with this exact line:

`Questions? Concerns? Thoughts? -- Think hard`

## 1) Project Snapshot (As Of 2026-03-03)
- Track: L4 governance/red-team hardening and gate integrity.
- G8 status: `PASS (classification gate, caveated)`.
- L4 overall: still blocked by remaining stop conditions (G8 pass is not L4 completion).
- Semantic debt baseline: `11`.
- Host semantics baseline: `Py:13 / JS:19` (total 32).

## 2) Recently Landed Waves (Context)
- D010 merged (`projection_loader` research evidence) and G8 adjudication closed.
- RT1 + RT2 merged (seed parsing parity hardening + anti-theater guardrails).
- RT3 merged (residual anti-theater checker hardening + CI path locks).
- RT4/RT4.1/RT4.2 merged (quote/escape parsing hardening in checker).

## 3) Current Working State (Must Re-verify At Session Start)
Run immediately:

```bash
git status --short
```

Current local context (from latest verified snapshot):
- W1-GATE + W1.1 changes are mixed in working tree/index.
- This can create L4 contract auto-class ambiguity if MAINTENANCE is inferred while runtime files are present.

## 4) Known Active Issue: L4 Contract Ambiguity
Repro:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged
```

Observed failure mode:
- Auto-detected `MAINTENANCE` while runtime/substrate files were part of staged/working diff.

Known pass path (when bound correctly):

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id w1-gate-blindness-remediation
```

## 5) Known Baseline Failure (Pre-existing, Not Introduced By W1)
```bash
PYTHONHASHSEED=0 pytest -q mu/tests/docs/test_doc_governance.py::TestGovernanceCoverage::test_governance_coverage_minimum
```
Expected:
- Fails at ~28.0% governed docs vs required 30%.
- Treat as baseline debt unless explicitly fixed in wave scope.

## 6) W1 Scope Intent (What Must Stay True)
### W1-GATE (Structural)
Targets:
- F-01 parity canary in merge-time gate path.
- F-04 fail-closed parity vectors loading.
- F-20 JS linters scan full substrate by default and support line-local marker bypass.
- F-21 remove nondeterministic `new Date()` behavior from affected JS path.

### W1.1 (Maintenance)
Targets:
- Tool invocation contract tests (default/no-arg scan, single-file mode, path lock, symlink/realpath, marker locality).
- Tracker + indicator artifact updates.
- No runtime behavior change.

## 7) Tool Invocation Contract Block (Must Hold)
1. Default/no-arg invocation scans full JS substrate.
2. Directory-scan + single-file mode both work for both linters.
3. Gate-invoked path lock is test-covered.
4. Symlink/realpath paths are test-covered.
5. Marker suppression is line-local.

## 8) Mandatory Validation Set
Run at minimum (adjust for split-wave validation as needed):

```bash
PYTHONHASHSEED=0 pytest -q mu/tests/l4_gates/test_w1_gate_blindness_gate.py
PYTHONHASHSEED=0 pytest -q mu/tests/parity/test_js_parity_automated.py::test_parity_canary
PYTHONHASHSEED=0 pytest -q mu/tests/tools/test_contraband_js_detection.py
PYTHONHASHSEED=0 pytest -q mu/tests/tools/test_ast_police_js_detection.py
PYTHONHASHSEED=0 pytest -q mu/tests/tools/test_js_tool_invocation_contract.py
bash tools/checks/linters/contraband_js.sh
bash tools/checks/linters/ast_police_js.sh
python3 tools/checks/enforce_l4_execution_contract.py --staged
python3 mu/tools/checks/check_host_semantics_ratchet.py
./tools/checks/check_docs_consistency.sh
```

## 9) Required Reporting Format (Any GO/NO-GO)
Always include:
1. Exact changed file list by wave/class.
2. Exact L4 contract command + output for each wave.
3. Validation table (`command` + `result`).
4. Invariant tuple:
   - debt before/after
   - host semantics before/after
   - runtime/substrate delta
5. Explicit `GO` or `NO-GO` with one-line rationale.
6. If relevant, postmortem for path/enforcement misses.

## 10) Prompting Rules For Claude (When GPT Is Acting As Prompt Author)
Any full prompt should include:
- Adversarial/dialectic framing.
- Reproduction-first requirement.
- Clear scope + stop conditions.
- Required validation commands.
- Output contract for closeout.
- The exact footer line below.

`Questions? Concerns? Thoughts? -- Think hard`

## 11) First 5 Minutes Playbook For New Session
1. Read `mu/docs/agents/AgentRunbook.v0.md` and honor skill/trigger rules.
2. Run `git status --short`.
3. Run L4 contract check on actual candidate diff.
4. Decide if wave must be split by class.
5. Run targeted validations and issue GO/NO-GO.

## 12) Canonical Paths
- Repo root: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX`
- L4 contract checker: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/tools/checks/enforce_l4_execution_contract.py`
- Host semantics ratchet: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/mu/tools/checks/check_host_semantics_ratchet.py`
- Docs consistency check: `/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/tools/checks/check_docs_consistency.sh`
