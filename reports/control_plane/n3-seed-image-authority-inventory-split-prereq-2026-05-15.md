# N3 Seed-Image Authority Inventory Split Prerequisite

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-image-authority-inventory-split-prereq-2026-05-15
Class: L4_ENABLER
Category: /mu structural host-debt reduction prerequisite
Target gate: G8
Phase-A-Lock: LOCKED

FOUNDER_OVERRIDE:n3-seed-image-authority-inventory-split-prereq-2026-05-15

## Grounding / Authorization

`TASKS.md` is the canonical authorization surface: `TASKS.md:3-4` says work
not listed there is not authorized. This packet is grounded in the open
`[NEXT-CODEX-POST-REDTEAM]` task rather than in a pre-existing same-wave tracker
line:

- `TASKS.md:518-522` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked and open,
  records that the Phase A structural gap sweep and first bounded
  engine-state/scheduler reduction have landed, and says remaining structural
  reduction requires separate bounded packets.
- `TASKS.md:526` carries the founder directive to proceed through the
  dispatcher/pipeline with a control-plane packet plus a `TASKS.md` tracker entry
  for every wave.
- `TASKS.md:533` records the prior N3 broad-host-surface structural slice as
  landed and preserves the rule that N3 follow-up must be a source-grounded
  bounded boundary slice, not baseline-only cleanup as a substitute for
  reduction.

The exact wave id
`n3-seed-image-authority-inventory-split-prereq-2026-05-15` is now present in
`TASKS.md:350`, with the same-wave tracker follow-up recorded at
`TASKS.md:352`. The wave-bound automation override for this control-surface L4
enabler is:

`FOUNDER_OVERRIDE:n3-seed-image-authority-inventory-split-prereq-2026-05-15`

Governing packet and root-cause references:

- this packet,
  `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
- predecessor NO-GO packet,
  `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:339-345`,
  `:359-384`, and `:457-464`
- checker fail-closed behavior in
  `tools/checks/check_host_authority_inventory_ratchet.py:13-18`, `:289-337`,
  `:460-470`, and `:611-684`
- current path-coupled loader evidence in
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:593-636`,
  `mu/host/js/core/seed_loader.js:186-242`, and
  `mu/host/js/cli/main.js:245-252`
- target L4 ABI boundary in `mu/docs/core/L4MicroAbi.v0.md:29-45`

## Purpose

Mechanize the prerequisite identified by the N3 seed-image boundary
implementation NO-GO: the host-authority inventory checker must either support
an exact, fail-closed accounting model for a public path-wrapper to seed-image
byte-boundary split, or it must reject that split with a smaller next packet.

This is a checker/policy wave only. It must not edit the Python or JavaScript
runtime seed loaders. Runtime implementation of `rcx_load(image_bytes)` remains
the successor wave after this prerequisite lands.

## Root-Cause Evidence

The preceding runtime packet stopped before commit readiness because the honest
named byte-boundary shape created new detector-visible host sites while current
path-based loader wrappers still had to remain public compatibility surfaces.

Direct evidence:

- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:339-345`
  records the Phase B NO-GO before commit readiness.
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:359-384`
  identifies the ratchet blocker: `loadVerifiedSeedImage` became a new total and
  authority site, and hiding the boundary behind lambda/arrow/overload/object
  shapes would evade the detector instead of reducing authority.
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:457-464`
  names the smallest next prerequisite: decide whether public wrapper inventory
  sites may be added, or mechanize an explicit same-wave relocation/split model.
- `tools/checks/check_host_authority_inventory_ratchet.py:13-18` says the
  checker fails closed on any new total-inventory or authority-subset site.
- `tools/checks/check_host_authority_inventory_ratchet.py:289-337` records every
  Python `FunctionDef` or `AsyncFunctionDef` as a total site and records
  authority when host-authority signals are present.
- `tools/checks/check_host_authority_inventory_ratchet.py:460-470` records
  top-level JS `function`, block-arrow assignment, and `const ... = function`
  forms as inventory sites.
- `tools/checks/check_host_authority_inventory_ratchet.py:611-684` compares
  inventories by `(substrate, file, name)` and passes only when there are zero new
  total sites and zero new authority sites.
- Current Python loader code is path-coupled at
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:593-636`: it reads bytes,
  verifies checksum, parses JSON, and validates structure/projection IDs inside
  `load_verified_seed(seed_path, verify=True)`.
- Current JS core loader code is path-coupled at
  `mu/host/js/core/seed_loader.js:186-242`: it builds a path, reads a file,
  verifies checksum, parses JSON, and validates projection IDs inside
  `loadVerifiedSeed(seedName, subdir)`.
- Current JS CLI loader code is path-coupled at
  `mu/host/js/cli/main.js:245-252`: it reads a path, verifies checksum, parses
  JSON, and validates structure/projection IDs inside
  `loadVerifiedSeed(seedPath, seedName)`.
- `mu/docs/core/L4MicroAbi.v0.md:29-45` defines the target
  `rcx_load(image_bytes) -> state` boundary and records current implementation
  truth as `seed_integrity.py:load_verified_seed()` plus `projection_loader.py`.

Therefore this wave must not make Python or JavaScript loaders smarter. It must
make the detector/policy honest enough to distinguish structural narrowing from
authority growth, or prove that the split is not admissible under the current
ratchet contract.

## Scope

Allowed implementation write set:

- `tools/checks/check_host_authority_inventory_ratchet.py`
- `mu/tools/checks/check_host_authority_inventory_ratchet.py`
- `tests/tools/test_check_host_authority_inventory_ratchet.py`
- `mu/tests/tools/test_check_host_authority_inventory_ratchet.py`
- `tools/checks/host_authority_inventory_split_allowances.json` only if Phase B
  proves a checker-owned policy file is required for an exact, fail-closed split
  model
- `mu/tools/checks/host_authority_inventory_split_allowances.json` only if Phase
  B proves a checker-owned policy file is required for an exact, fail-closed
  split model
- `TASKS.md` same-wave tracker note
- `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
- `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
- same-wave generated deferred non-blocking bridge findings packet, if any

Read-only grounding:

- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- `reports/control_plane/phase-b-no-go-package-classification-repair-2026-05-15.md`
- `mu/docs/core/Why_RCX_PI_VM_EXISTS.md`
- `mu/docs/core/SelfHosting.v0.md`
- `mu/docs/core/MetaCircularKernel.v0.md`
- `mu/docs/core/StructuralPurity.v0.md`
- `mu/docs/core/BootstrapPrimitives.v0.md`
- `mu/docs/core/L3SubstrateArchitecture.v0.md`
- `mu/docs/core/Boot0Architecture.v0.md`
- `mu/docs/core/L4MicroAbi.v0.md`

Out of scope:

- runtime loader edits in `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- runtime loader edits in `mu/host/js/core/seed_loader.js`
- runtime loader edits in `mu/host/js/cli/main.js`
- seed JSON, checksum registry, projection-ID registry, or Stage0 bundle edits
- baseline updates used as proof of progress
- generic inventory exemptions
- any checker policy/allowance file other than the two explicit split-allowance
  JSON paths named in the allowed implementation write set
- hidden adapters, Python lambdas, JS arrow adapters, optional overloads, object
  method hiding, or dynamic callable workarounds
- any claim that this wave implements `rcx_load(image_bytes)`, eliminates
  `projection_loader`, closes N3, completes L4, or productionizes binary/TLV seed
  images

- `reports/deferred/non_blocking/n3-seed-image-authority-inventory-split-prereq-2026-05-15_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Required Direction

Phase B must implement or reject a fail-closed split accounting model for this
specific structural transition:

- Old path-coupled public loader remains as a filesystem wrapper.
- New public seed-image boundary may be introduced later as a named function only
  if the checker can distinguish that split from host-authority expansion.
- The detector must keep default behavior strict: arbitrary new total sites and
  arbitrary new authority sites still fail.
- Any split allowance must be exact, explicit, auditable, and bounded to named
  old/new site pairs. It must not be a broad file-level, name-pattern, substrate,
  or signal-class exemption.
- A valid split must require evidence that authority moved or narrowed. It must
  reject incomplete transitions such as new byte-boundary site without a paired
  old wrapper, wrong file/name, wrong substrate, unrelated signals, increased
  authority signals, or added semantic control.
- The checker must emit human and JSON output that names accepted split pairs
  separately from ordinary removed/new sites, so bridge and commit review can see
  exactly what was accepted.

If Phase B determines that a public split cannot be represented honestly without
weakening the ratchet, it must route a NO-GO package with a smaller next packet.
Acceptable smaller next packets include a source-lock-only design decision,
projection-loader API contraction before byte-boundary naming, or another
detector-visible narrowing prerequisite. A baseline update alone is not an
acceptable next step.

## Stop Conditions

Stop and route NO-GO instead of commit handoff if any of these are true:

- any Phase B implementer, bridge fixer, reviewer, recovery turn, or commit path
  tries to launch `executor_dispatch.py`, `phase_a_executor.py`,
  `phase_b_executor.py`, `commit_executor.py`, or `bridge_supervisor.py` as a
  nested pipeline from inside this already-dispatched wave
- the checker cannot represent the path-wrapper to byte-boundary split without
  weakening default fail-closed behavior for ordinary new total or authority
  sites
- the model needs a broad file-level, name-pattern, substrate, signal-class, or
  baseline-update exemption
- the implementation requires edits to runtime seed-loader files or seed /
  checksum / projection registries
- one substrate can pass without an equivalent policy and regression path in the
  other checker copy
- accepted split evidence cannot be made visible in both JSON and human output
- Phase B cannot add the same-wave `TASKS.md` tracker note and L4 indicator
  before commit handoff

## Constraints / Hard No-Go

Do not accept or stage any implementation that:

- edits runtime seed-loader files
- updates `tools/checks/host_authority_inventory_baseline.json`
- updates another baseline to hide added host authority
- exempts all new sites in a file, substrate, name prefix, signal class, or wave
- treats removed baseline sites as proof that unrelated new sites are acceptable
- lets lambda, arrow, optional overload, object-method hiding, dynamic dispatch,
  or unscanned function shapes satisfy the split
- weakens malformed baseline, underscan, parse-error, generic new-site, or
  generic authority-site failures
- permits a split when only one substrate has a corresponding policy/test path
- adds host semantic authority to Python or JavaScript under the label of
  "bootstrap"

## Work Items

These are the bounded Phase B tasks derived from the open
`[NEXT-CODEX-POST-REDTEAM]` authorization in `TASKS.md:518-526` and the N3
follow-up boundary-slice rule in `TASKS.md:533`. They do not reopen or relist
the already-landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, or seed-registration work called out in `TASKS.md:522`.

1. Re-open the checker implementation and tests named in the allowed write set.
2. Decide the smallest honest detector model for path-wrapper to byte-boundary
   splits.
3. If the split model is sound, implement it in both checker copies without
   changing default new-site failure behavior.
4. If policy/allowance data is required, use only the two explicit
   `host_authority_inventory_split_allowances.json` paths named in the allowed
   write set, make them checker-owned, schema-validated, exact-pair-only,
   fail-closed, and explicitly document them as not baselines.
5. Add focused regression tests in both test copies proving default failures and
   accepted/rejected split cases.
6. Add the same-wave `TASKS.md` tracker note and same-wave L4 indicator.
7. If the split model is not sound, produce a NO-GO package and route the
   smallest next prerequisite with direct file:line evidence.

## Required Tests

Phase B / commit handoff must run and record at minimum:

```bash
python3 -m py_compile tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
python3 -m py_compile mu/tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  tests/tools/test_check_host_authority_inventory_ratchet.py \
  mu/tests/tools/test_check_host_authority_inventory_ratchet.py
```

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
python3 mu/tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-image-authority-inventory-split-prereq-2026-05-15
```

```bash
./tools/checks/check_docs_consistency.sh
```

Focused tests must prove:

- generic new total-inventory sites still fail
- generic new authority-subset sites still fail
- malformed or stale split policy data fails closed, if either explicit
  split-allowance JSON file exists
- incomplete split pairs fail
- wrong old/new path, name, substrate, or signal-shape pairs fail
- accepted split output is visible in JSON and human reports
- `tools/` and `mu/tools/` checker paths have identical behavior

## Acceptance Criteria

- Pipeline owns the implementation; manual checker edits from the operator
  session are not completion for this packet.
- Runtime seed-loader files remain untouched by this wave.
- Default ratchet semantics remain fail-closed for ordinary new total and
  authority sites.
- Any accepted path-wrapper to byte-boundary split is exact-pair, bounded,
  detector-visible, and reviewer-visible in output.
- The ratchet baseline is not updated as proof.
- The staged L4 execution contract passes for this exact wave ID.
- The packet and tracker note explicitly state that this is an L4 enabler for
  the next runtime seed-image boundary attempt, not the runtime boundary itself.

## Phase B Implementation Result

Phase B selected the smallest sound detector model: an explicit checker-owned,
empty-by-default split-allowance policy. The policy files are not baselines and
do not reduce the ordinary ratchet. They only let the checker account for a
future public path-wrapper to seed-image byte-boundary split when every listed
old/new pair is exact and detector-visible.

Implemented behavior:

- default new total-inventory sites still fail
- default new authority-subset sites still fail
- split allowance JSON is schema-validated and fail-closed
- every allowance is exact-pair-only: `old` and `new` must each name
  `substrate`, `file`, and `name`
- old and new sites must be in the same substrate and must differ
- the paired old wrapper must exist in baseline total, baseline authority, and
  current total inventories
- the new boundary must be a current new total site and a current new authority
  site, and must not already be in baseline
- `moved_signals` must be explicit, non-empty, non-duplicated, and bounded by
  the old baseline authority signals
- the old wrapper must no longer carry moved signals and must not gain new
  authority signals
- the new boundary may carry only the listed moved signals, allowing narrowing
  but not unrelated or increased signal shape
- accepted split output is exposed as `accepted_split_pairs` in JSON and as an
  `ACCEPTED SPLITS` block in human output
- non-empty accepted split policy data must produce accepted split evidence for
  both Python and JavaScript substrates

Files implementing the model:

- `tools/checks/check_host_authority_inventory_ratchet.py`
- `mu/tools/checks/check_host_authority_inventory_ratchet.py`
- `tools/checks/host_authority_inventory_split_allowances.json`
- `mu/tools/checks/host_authority_inventory_split_allowances.json`
- `tests/tools/test_check_host_authority_inventory_ratchet.py`
- `mu/tests/tools/test_check_host_authority_inventory_ratchet.py`

The two split-allowance JSON files are intentionally empty in this prerequisite
wave. The successor runtime wave must add exact same-wave allowance entries only
for the detector-visible Python and JavaScript boundary split it implements.

This wave did not edit Python or JavaScript runtime seed-loader files, did not
update `tools/checks/host_authority_inventory_baseline.json`, did not update any
other baseline, did not edit seed JSON, checksum registries, projection-ID
registries, or Stage0 bundles, and does not claim to implement
`rcx_load(image_bytes)`.

Same-wave tracker and indicator artifacts:

- `TASKS.md` tracker sync note:
  `n3-seed-image-authority-inventory-split-prereq-2026-05-15`
- `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`

## Phase B Local Validation

Required Phase B-local commands were run after staging the same-wave files:

| Command | Result |
| --- | --- |
| `python3 -m py_compile tools/checks/check_host_authority_inventory_ratchet.py` | PASS, exit 0 |
| `python3 -m py_compile mu/tools/checks/check_host_authority_inventory_ratchet.py` | PASS, exit 0 |
| `PYTHONHASHSEED=0 python3 -m pytest -q tests/tools/test_check_host_authority_inventory_ratchet.py mu/tests/tools/test_check_host_authority_inventory_ratchet.py` | PASS, `50 passed in 3.55s` |
| `python3 tools/checks/check_host_authority_inventory_ratchet.py` | PASS, no new total-inventory or authority-subset sites detected |
| `python3 mu/tools/checks/check_host_authority_inventory_ratchet.py` | PASS, no new total-inventory or authority-subset sites detected |
| `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` | PASS, `passed: true`, no increases, no decreases |
| `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-image-authority-inventory-split-prereq-2026-05-15` | PASS, `L4_ENABLER compliant` |
| `./tools/checks/check_docs_consistency.sh` | PASS, docs consistent |

Known non-blocking output preserved from the inventory checker:

- baseline site removals are detected and may be reviewed in a separate baseline
  update packet
- 9 existing authority sites have changed signal shape

## Successor Wave

After this prerequisite lands, route the successor runtime wave that retries the
seed-image boundary implementation with the new checker/policy truth:

`n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`

That successor must still obey the previous NO-GO constraints: no lambdas, no JS
arrow adapters, no optional overloads, no hidden adapters, no one-substrate
implementation, no registry/checksum/projection-ID authority expansion, and no
claim that JSON seed-image boundary narrowing eliminates the full
`projection_loader` primitive.

## Pipeline Requirement

This packet is routed by the operator-visible dispatcher before Phase A starts.
Once Phase A or Phase B is running, agents are already inside the pipeline and
must not launch or relaunch `executor_dispatch.py`, `phase_a_executor.py`,
`phase_b_executor.py`, `commit_executor.py`, or `bridge_supervisor.py`.

Manual runtime implementation from the operator session is out of scope. If the
pipeline breaks, diagnose the root cause with direct evidence. Manual unblock is
allowed only as a bounded operator-visible repair, and the same wave or a
follow-up wave must mechanize the root fix in dispatcher, builder, recovery,
commit, pre-commit, pager/autoping, or another appropriate pipeline surface so
the same failure does not require another manual repair.

Same-wave operator correction note:

- During the first Phase B attempt for this packet, the implementer interpreted
  the old "Launch this work through" wording as an instruction to start a nested
  dispatcher from inside Phase B. That created a nested
  `executor_dispatch.py -> phase_a_executor.py -> bridge_supervisor.py` process
  tree while the primary dispatcher was already active. This packet text now
  separates operator-visible routing from in-pipeline implementation and makes
  nested pipeline launch a stop condition.
- A follow-up pipeline root-fix wave must mechanize a source-lock or prompt guard
  so Phase B implementers cannot treat packet-level routing snippets as commands
  to launch a nested dispatcher.

Same-wave authorization line for detector-visible L4 handling:

`FOUNDER_OVERRIDE:n3-seed-image-authority-inventory-split-prereq-2026-05-15`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-seed-image-authority-inventory-split-prereq-2026-05-15`
- Active packet: `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_host_authority_inventory_ratchet.py`
  - `mu/tools/checks/check_host_authority_inventory_ratchet.py`
  - `mu/tools/checks/host_authority_inventory_split_allowances.json`
  - `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
  - `reports/deferred/non_blocking/n3-seed-image-authority-inventory-split-prereq-2026-05-15_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-seed-image-authority-inventory-split-prereq-2026-05-15`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-seed-image-authority-inventory-split-prereq-2026-05-15_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-seed-image-authority-inventory-split-prereq-2026-05-15`
- Active packet: `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `78dccb235ffad521118c00512dd56eddf1fe68d4c72b605ee6a26a2adfffb599`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_host_authority_inventory_ratchet.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_host_authority_inventory_ratchet.py`
  - `mu/tools/checks/check_host_authority_inventory_ratchet.py`
  - `mu/tools/checks/host_authority_inventory_split_allowances.json`
  - `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`
  - `reports/deferred/non_blocking/n3-seed-image-authority-inventory-split-prereq-2026-05-15_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-seed-image-authority-inventory-split-prereq-2026-05-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
