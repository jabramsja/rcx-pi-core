<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-10-02
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_coinduction_prefix_gate.py mu/tests/parity/test_coinduction_prefix_parity.py mu/tests/structural/test_execution_layer_truth_contract.py
-->

# Guarded finite Coinduction prefixes

**Implementation: bounded guarded prefixes; native review and landing pending.**

This contract describes one bounded slice of
`[MU-COINDUCTION-PRODUCTION-PROOF]`: the registered
`mu/programs/coinduction_prefix.v1.json` program expresses guarded transitions
to construct a finite observation window and a reusable open tail. The shared fixtures
exercise the actual Python and JavaScript structural kernels, including the
preserved malformed-machine continuation replay workload. The original
[Coinduction.v0.md](Coinduction.v0.md) remains a representation-only foundation;
its historical claims and tests are unchanged.

## Decision card

| Field | Decision |
| --- | --- |
| Wave | `mu-coinduction-guarded-prefix-r10-2026-10-02` |
| Class / target | `L4_STRUCTURAL` / G8 |
| Workload | workload_target: execution_layer_truth |
| Structural artifact | Ordered, linear Mu projections in `coinduction_prefix.v1.json`; exact IDs and counts are pinned by `mu/seed_registry_manifest.v1.json` and `mu/tests/structural/test_seed_counts.py` |
| Small supported representation | Finite linked transition table, positional structural references, linked finite demand, next-only position paths |
| Progress witness | Each emitted observation has a selected guarded transition, source, next reference and structural position |
| Failure witness | Explicit `coinduction_prefix_result` with `status: rejected` and a reason |
| Causal control | Require removal of `co_prefix.emit` to prevent a successful semantic result on both substrates |
| Resource control | A one-step driver budget leaves an unfinished state with `stall: false` |
| Authority | Existing `domain` validation; no `run_algorithm` registration or reserved-field policy expansion |
| Remaining obligations | Infinite productivity, observation equivalence, bisimulation, scheduler, stream runtime, general corecursion and self-hosting |

This slice does not prove infinite productivity or bisimulation.

The governing operational packet and measured L4 indicator are owned by native
Phase A and the collector/commit path. The same-wave TASKS tracker note owns
their L4 metadata. Local kernel evidence does not assert review, landing or
full Coinduction completion. Fixpoint follows the remaining Coinduction work;
Optimization remains LAST. TASKS owns the intervening operational priorities.

## Input domain

All values must first satisfy the existing kernel's Mu and domain-field
validation. Within that boundary, the public entry is exactly:

```text
{"coinduction_prefix": {
  "tail": {"_co_tail": {"open": true, "obligation": {
    "machine": Machine, "next": Ref, "position": Position
  }}},
  "window": {"_co_window": {"demand": Demand, "finite": true}}
}}

Machine  := null | {"transition": Mu, "rest": Machine}
Ref      := null | {"next": Ref}
Demand   := null | {"take": Demand}
Position := {"_co_position": {"path": Path}}
Path     := {"_co_position_path": null}
          | {"_co_position_path": {"step": "next", "rest": Path}}
Transition := {
  "guard": "observed-before-tail",
  "observation": {"label": "state", "payload": Mu},
  "next": Ref
}
```

Each demanded table entry must satisfy `Transition`. `null` is the first table
reference; each `next` moves one table cell. References
are finite descriptions even when transitions refer back to an earlier row.
The observation label is deliberately fixed to `state`; payloads are opaque
domain-valid Mu. The seed materializes the observation's position and the full
guarded-step witness from the selected row. No caller-supplied prefix is accepted.

The active Stage 4 matcher additionally excludes bare host integer/float leaves
before variable capture, including leaves nested inside a payload or request.
Numeric data must use canonical [StructuralNumbers.v0.md](StructuralNumbers.v0.md)
values. The two numeric malformed-request fixtures retain their original IDs,
expected rejections and zero-emission assertions with these admitted inputs:

| Fixture | Canonical numeric value | Unchanged rejection |
| --- | --- | --- |
| `numeric_demand` | `{"_num":{"xO":{"xH":null}}}` (2) as demand | `malformed_demand` |
| `malformed_next_reference` | `{"_num":{"xI":{"xI":{"xH":null}}}}` (7) as the nested next-reference suffix | `malformed_reference` |

These are valid Mu numerals but invalid demand/reference structures. Numeric
payloads also use canonical Mu numerals. Raw host integers remain unsupported:
they cannot reach the seed's rejection projections through matcher capture.
The original raw-host examples and R3's failed execution remain preserved in the
stopped-source manifest and diagnosis referenced below. Their kernel exhaustion
is not a semantic rejection. A fast fixture-domain regression uses the existing
matcher admission rule on every input and resume window; reinserting either raw
integer fails that rule without running the expensive kernel workload.

The `transition`/`rest` cell names are deliberate: the existing kernel treats
bare `head`/`tail` records as legacy list encodings and denormalizes them to host
arrays. The table uses ordinary domain records, preserving malformed suffixes
as data that projections can reject.

The entire demand, position path, starting-reference syntax and machine spine
are checked before execution. Transition contents are checked when demanded.
An undemanded row may remain unresolved or malformed as an open obligation.
The selected row's next-reference syntax is checked before emitting; whether
that reference resolves is checked only if more demand follows. An empty demand
therefore produces no observations and does not resolve the tail reference.
It still rejects malformed reference syntax or table spines.

The initial position is caller-supplied structural data. For a fresh request,
use the empty path. Resume by passing the actual returned `tail` unchanged with
a new finite window. The program validates its shape again. The tail is a full
structural continuation, without a host iterator or process identity; it is
not a signed provenance token and does not certify earlier history supplied by
an external caller.

Internal `co_*` machine states are reduction intermediates, not public request
or resume envelopes. Kernel stepping is a general Mu facility, so direct
injection of an internal state is outside this entry contract. Unsupported
matcher-admissible values *inside* the `coinduction_prefix` envelope are explicitly
rejected. Existing Mu/security/resource failures and kernel exhaustion are
boundary outcomes and cannot count as a semantic result.

## Execution and result

`co_prefix.take` consumes one demand cell and starts table lookup. The
`lookup_next` and `lookup_here` projections resolve the positional reference.
`guarded` requires the exact guard and observation recipe, then the reference
validator checks next-reference syntax. Only `co_prefix.emit` constructs an
observation and its guarded witness and advances the reference and position.
The next position prepends one `next` path cell. The reverse projections restore
chronological order at the finite boundary.

```text
{"coinduction_prefix_result": {
  "status": "ok",
  "window": {"_co_window": {
    "from": Position,
    "through": LastEmittedPositionOrNull,
    "prefix": Prefix,
    "finite": true
  }},
  "tail": {"_co_tail": {"open": true, "obligation": {
    "machine": Machine, "next": Ref, "position": NextPosition
  }}}
}}

Prefix := {"_co_prefix": null}
        | {"_co_prefix": {"observation": Observation,
                           "step": GuardedStep, "rest": Prefix}}
Observation := {"_co_observation": {
  "label": "state", "payload": Mu, "position": Position
}}
GuardedStep := {"_co_guarded_step": {
  "source": Ref, "observation": Observation, "next": Ref,
  "guard": "observed-before-tail"
}}
```

`through` is null for empty demand; otherwise it is the final emitted position.
The returned position is the next observation position. If a later demanded
transition fails, the final result is a rejection, with no successful partial
window. Earlier executed observations remain visible in the kernel trace.

```json
{"coinduction_prefix_result":{"status":"rejected","reason":"unresolved_reference"}}
```

Rejection reasons and precedence follow the seed's ordered projections:

| Reason | Trigger |
| --- | --- |
| `unsupported_request` | Unsupported payload or wrong field set inside the entry envelope |
| `malformed_window` | Wrong window shape, extra fields, or `finite` other than true |
| `malformed_demand` | Any demand cell or suffix other than null / exact `take` |
| `malformed_tail` | Missing or unsupported open-tail, obligation or position envelope |
| `malformed_position` | Malformed path or step outside the `next` alphabet |
| `malformed_reference` | Starting or selected next-reference syntax is invalid |
| `malformed_machine` | Any table spine cell has an unsupported shape |
| `unresolved_reference` | A demanded reference runs past the table |
| `missing_guard` | Selected row contains only observation and next |
| `missing_observation` | Selected row contains only guard and next |
| `malformed_observation` | Correct guard, but observation lacks the exact label/payload shape |
| `unguarded_transition` | Exact row field set with an unsupported guard |
| `malformed_transition` | Any other demanded row shape, including additional fields |

For example, a row missing both guard and observation is a
`malformed_transition`; the specific missing-field rules require their stated
remaining fields. No timeout, recursion limit, stall or process liveness fact
is mapped to success or to one of these structural reasons.

## Actual entrypoints and dependencies

Python loads the seed using `get_seed_path` and
`load_verified_seed(..., verify=True)` from `rcx_pi.selfhost.seed_integrity`,
then calls `rcx_pi.selfhost.step_mu.run_mu_structural` with
`kernel_mode="core"`, `validation_mode="domain"`, `trace_output=True` and
`reject_nonlinear=True`. That driver invokes production `step_kernel_mu`,
which loads the verified kernel/match/substitution seeds through its existing
loaders and uses the existing Stage0 cutover. All domain patterns are linear; the canonical registry and seed-count tests pin their exact inventory.

JavaScript loads the new program using
`mu/host/js/core/seed_loader.loadVerifiedSeed(name, "programs")`.
The parity harness loads `kernel.v1.json`, `match.v2.json`, and `subst.v2.json`
with `loadVerifiedSeedImage(..., SEED_IMAGE_VERIFICATION_MODES.CLI)` and invokes
`mu/host/js/engine/kernel.runStructural(kernelProjections, domainProjections,
input, maxSteps, vmConfig)`. The configuration supplies the existing compiled
kernel/match/substitution bundles, validates them and checks their source digests
against the verified seed registry. This selects the active Stage0 cutover path.
`muCopy` provides the existing container boundary for request data.

The new seed has no companion domain-projection dependencies, matching the
registry's execution-time dependency meaning. The structural substrate
kernel depends on match/substitution as already registered. Both CLI and core
verification views pin the new seed's bytes and ordered IDs. The manifest has
22 seeds, with 17 in the JS CLI view. No new algorithm-dispatch authority is
granted. The Python integrity module and JS seed loader change only their manifest
digest pins. The only other host delta is the bounded JS continuation replay
integration described below.

## Executable examples and falsifiable evidence

The shared JSON vectors provide complete input and asserted output values:

- `constant_three`: revisit one transition to emit three structural zero
  payloads at distinct positions. No input prefix is supplied.
- `alternating_three`: start at row 2, then visit rows 0 and 2 to emit B, A, B.
  Row 1 is undemanded malformed data. Table order cannot produce this result.
- `empty_demand`: produce an empty window and retain an unresolved open tail.
- `finite_open_tail`: expose one transition whose next reference is outside the
  table; the bounded window succeeds, while demanding that next row rejects.
- `split_resumed`: expose B, pass the actual returned tail into a second demand,
  and expose A, B with positions and guarded witnesses equal to the uninterrupted
  three-observation result.
- Rejection vectors exercise all documented reason classes, malformed demand
  suffixes, extra fields, invalid reference syntax and later demanded failure.

Tests compare complete results and kernel traces, including step count and stall
metadata, across Python and JS. Expected results never enter either execution
harness. The mutation control requires removal of the emission projection after
verified loading to leave a stalled `co_emit` intermediate in both substrates.
The one-step driver control requires an unfinished result with `stall: false`.
The cross-substrate controls and complete vector suite are required proof;
a partial or interrupted suite cannot establish success. The existing
`mu/tests/structural/test_execution_layer_truth_contract.py` additionally runs
the verified program directly through `run_mu_structural`, observes B, A, B and
its guarded transitions, and removes `co_prefix.emit` on the same input to
require loss of the result. Its finite trace contains selected projection IDs
and states, not the `step_boundary` / `engine_terminal` observer events produced
by `run_engine_pipeline`. An open returned tail establishes a resumable finite
obligation, not engine observability, bisimulation or infinite productivity.

The bounded driver limit is 96 domain reductions per request. Tests measure
kernel wall time with `perf_counter` / `performance.now` and record it as pytest
properties; time is evidence only. The alternating three-observation request
requires 42 reductions including final stall detection; the constant example
requires 32. These bounds cover the checked vectors, not arbitrary input sizes.
Every valid finite demand decreases during execution; each reference lookup,
validation walk and prefix reversal also traverses finite input structure.
Larger requests can exhaust existing host limits and require separate evidence.

### Two bounded continuation integration corrections

The preserved R2 source and evidence identify two independent JS integration
failures. R2 repaired the actual `malformed_machine_tail` substitution replay:
`_stepKernelCore` now calls the existing `_stage0VmRunTrusted` helper with the
paired Python bound of 1000 steps instead of 100. The direct regression obtains
an actual `co_prefix.position_end` continuation from the vector's Python trace,
measures more than 100 and fewer than 1000 substitution steps, compares complete
resumed packets and requires altered input/projection rejection in both hosts.
Replay must still reach `subst_done`; resource exhaustion is not a Mu result.

R2's full vector attempt subsequently exceeded 900 seconds on `missing_payload`
and `finite_open_tail`. Its diagnosis found domain binding replay on every
private internal continuation, including all registered domain projections.
R3 avoided that repeated work using the private continuation proof; R8 carried
that implementation. The proof binds continuation identity, input, normalized
input, projection authority and watchdog, but did not establish the semantics
of caller-supplied VM slots. R8's existing VM-order selector reproduced a
failure: three configurations that previously raised the original binding
SECURITY error were accepted. A private origin alone was insufficient.

R9 retains the shortcut only when the immutable VM snapshot has full content
hashes equal to the existing checked-in compiled kernel, bridge (if supplied),
match and substitution bundles in their respective slots. Hashing uses the
existing Mu copy/hash boundary and compiler artifacts, not bundle IDs or
caller-supplied source-digest labels. The private continuation proof also binds
that exact snapshot identity. Canonical core and bridge configurations retain
finite progress without replaying every projection on every internal step.
Other structurally valid configurations retain the existing binding replay,
including its original errors, stall outcomes and watchdog behavior. With no
VM configuration, domain replay is also retained. Public packets omit private
proof; external continuations always replay binding. No new trusted export,
semantic algorithm, domain policy or host authority site is added.

`test_internal_domain_continuations_do_not_replay_external_binding` instruments
only counters in a disposable copy of the real kernel module. It requires
actual private progress in both `runStructural` and `stepKernel` with zero
internal replays for canonical content, and one public resume replay. A valid
custom bundle with identical executable behavior but different metadata still
replays and returns the same complete result, even if the caller sets a trust
flag. `test_js_vm_bridge_parity.py` retains every original ordered/bridge-absent
causal assertion and wrong-order error. Additional core controls substitute
programs while retaining canonical provenance labels, and swap match/subst
slots without a bridge; both must raise the original SECURITY binding error.
Full kernel and trusted-path tests retain forged continuation, altered input,
projection, watchdog and private-export rejection coverage.

R10 replaces R9's four compiled-JSON engine imports with data-only SHA-256 pins
of the complete canonical Mu bundle content. Runtime hashing still uses the
existing `core/types.muHash` boundary after copying and validating the bundle;
neither the dependency set nor loader/core/VM semantics changes. The original
engine dependency, dynamic-import, cycle/direction and seed-derived boundary
assertions remain intact in `test_engine_pipeline_discipline.py`.
Its added content-anchor controls independently recompile all four verified
seeds, compare the complete checked-in artifacts and both hosts' canonical
hashes, then exercise actual kernel continuations. Changing any slot's content
while retaining its provenance labels and a caller-supplied trust flag restores
replay. Corrupting each pin in a disposable test module also restores replay
with identical complete results. These are integrity pins, not semantic oracles.

Current reconstruction hashes, actual validation outcomes, timings and proof
limits live in
`reports/control_plane/mu-coinduction-guarded-prefix-r10-2026-10-02_implementation_evidence.json`.
The locked native packet is not an implementation log. Direct continuation
regressions alone do not prove the complete registered-seed workload.
R10 reconstructs only R9 commit `e5753108b7195f210fdfd0cc3f3d3a6142f4134f`'s Mu
implementation delta from `cefb39d113bc7c2db3ac289fec8e302cdede5cbe`, preserving
all 24 vectors byte-for-byte. R9 already contains R7's corrected numeric inputs
and substantive execution-layer proof, and R8's independent manifest/registry
seed-count and fully-locked membership repairs. All behavior and negative controls
remain required. R9, R8 and PR1325 remain preserved under the same production
owner until a passing replacement's exact semantic comparison permits native
disposition. No older retired source directory is an execution dependency.

PR1326's seven-source physical retirement was independently verified after its
`cefb39d` landing. Its recovery roots and five new plus four prior pending
useful-work owners remain recorded in the archived
`pr1326_landed_live_cleanup_20261002.json`. Physical retirement and recoverability
do not establish semantic landing or fleet completion. Those existing owners
remain open without becoming new Mu prerequisites.
Their nine explicit recovery locations are recorded in
`remaining_nine_landing_owner_recovery_paths_20261002.json` in that same archive.

Historical R3 evidence remains in
`reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/mu_coinduction_r3_stopped_candidate_20260928.json`
and `mu_r3_input_domain_and_workload_binding_root_causes_20260928.json` in the same
archive. Its full suite reported 413 passed and two failed in 168.26s. The focused
raw `numeric_demand` diagnostic returned identical Python/JS metadata:
`stall: true`, `termination_reason: max_steps_exhausted`, `steps_used: 10000`,
with the original input as output (18.56s Python / 30.90s JS). Both numeric
fixtures failed their expected-result assertions; that failure is retained,
not reclassified as success. R4 corrects only their input encodings to equivalent
canonical numerals, preserves all 24 expected outcomes and emission assertions,
and binds real workload execution in the required existing contract module.

Phase B evidence command (including the substantive execution-layer proof):

```bash
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/l4_gates/test_coinduction_prefix_gate.py mu/tests/parity/test_coinduction_prefix_parity.py mu/tests/structural/test_seed_counts.py mu/tests/engine/test_seed_integrity.py mu/tests/engine/test_seed_registry_consistency.py mu/tests/parity/test_seed_loading_parity.py mu/tests/l4_gates/test_coinduction_foundation_gate.py mu/tests/docs/test_coinduction_foundation_gate.py mu/tests/docs/test_manifest_discoverability.py mu/tests/structural/test_execution_layer_truth_contract.py --tb=short
```

Kernel tests carry `slow` markers and in-function `SPEED_OK` annotations.
The parity module also carries `l4_expensive` for the complete structural
kernel workload, retaining its existing classification. The harness allows 900 seconds per JS
invocation, independently of the unchanged 96-domain-reduction limit. A process
timeout fails the test and supplies no semantic result.
Native review, full commit/pre-push/CI gates, indicator collection and landing
remain executor-owned. No full L4 completion or reduction in host debt follows
from this finite slice.
