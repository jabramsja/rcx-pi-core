# Hybrid Recovery Agent

Date: 2026-04-16
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Phase-A-Lock: LOCKED
Task: [PIPELINE-RECOVERY]
Wave ID: hybrid-recovery-agent-2026-04-16
Wave class: L4_ENABLER
Target gate: G8
Packet path: This historical governing packet (`TASKS.md:191-193` originally routed the active wave here as the tracked packet; the packet is now completed and remains evidence for the landed hybrid-recovery slice)

## Purpose

Add a hybrid Tier 3 recovery path that preserves deterministic Tier 1 / Tier 2
auto-fix behavior and Tier 4 escalation, but stops treating all hard Tier 3
cases as either shell snippets or literal string replacement edits.

The intended end state for this slice is:

1. known deterministic recovery stays deterministic
2. terminal policy outcomes still fail closed
3. hard control-surface recovery cases can delegate to an existing repo-native
   code-writing actor only under a declared-scope contract plus recovery-owned
   enforcement that any observed delegated-run filesystem drift surviving to
   the recovery audit stays inside this packet's exact runtime-delegable file
   set
4. recovery owns scope audit, repo-local git-control immutability evidence,
   verification, and retry; it does not gain `.git/index`, `HEAD`, repo-local
   ref/config, commit, push, merge, or broad worktree authority, and this
   packet does not claim a broader preventive governance sandbox or per-write
   tracing proof than the local evidence it can actually produce

## Trigger

Current code truth from the reviewer-cited surfaces is narrower than the
packet's previous bounded-authority story:

1. `mu/tools/executors/phase_b_implementer.py:103-119` constrains scope only in
   prompt text (`Do NOT modify files outside the plan's scope`) and an optional
   `scope_hint`.
2. The cited implementer surface does not provide a deterministic file-write
   sandbox or a recovery-owned post-run changed-file check.
3. `mu/tools/executors/recovery_gate.py:1964-2026` is a 13-layer dangerous-
   command denylist, not an executor-owned positive verification contract.
4. `mu/tools/executors/recovery_gate.py:2436-2439` still executes approved Tier
   3 commands with `subprocess.run(..., shell=True, ...)`.
5. Hybrid recovery therefore cannot honestly claim bounded control-surface
   authority or deterministic observed-drift verification unless this wave
   adds recovery-owned changed-file enforcement and replaces raw model-authored
   validation shell with an executor-owned validator contract that explicitly
   suppresses repo-local pytest side effects.
6. The bridge reviewer also proved that this packet must distinguish between
   repo-local git-control immutability, which recovery can own within the cited
   surface, and blanket preventive blocking of stage/commit/push/branch/remote/
   PR activity, which the current implementer entrypoint does not honestly
   expose. The scope audit must also fail closed on symlink or file-type
   transitions.

## Architecture Decision (Locked For This Packet)

Repo-tracked founder authority now records a narrow 2026-04-16 exception for
this `[PIPELINE-RECOVERY]` wave allowing Tier 3 recovery to reuse
`phase_b_implementer` as the sole mutating actor for the bounded delegation
branch. For this packet, that exception retires the older
"no-Phase-B / no-bridge" constraint documented in
`mu/docs/agents/PipelineRecovery.v0.md:135-142` only for non-bootstrap
recovery targets. It does not retire the bootstrap boundary for bridge /
adapter / implementer infrastructure or adapter resolution itself, does not
pull the full Phase B bridge/meta-review loop into recovery, and does not
authorize widening the delegated writable scope beyond the exact
runtime-eligible files listed below. Landing work in this packet includes
bringing `mu/docs/agents/PipelineRecovery.v0.md` into sync with that recorded
exception.

This wave defines **hybrid recovery** as:

- Tier 1 and Tier 2 remain deterministic
- Tier 4 terminal policy remains a hard escalation boundary
- Tier 3 diagnosis remains JSON-planned and fail-closed
- when diagnosis concludes that a failure is too large for `shell` / literal
  `edit`, recovery may delegate to the existing `phase_b_implementer` only
  after validating declared scope against this packet's exact runtime-delegable
  file set and only if recovery can deterministically audit observed post-run
  filesystem drift against that scope before success; this packet does not
  describe snapshot-only manifest/inventory equality as proof that no
  transient out-of-scope touch occurred during the delegated run
- hybrid delegation remains runtime-ineligible for bridge / adapter /
  implementer bootstrap faults: if the failed surface is
  `mu/tools/executors/phase_b_implementer.py`, `.agent_bus/bridge_config.json`,
  bridge adapter loading / selection, or adapter invocation/bootstrap
  resolution, recovery must not select `delegate_implementer` and must
  escalate or split a separate packet
- hybrid verification is recovery-owned and executor-built: diagnosis may
  select only from a closed structured validator contract, and the
  `pytest_targeted` path must be repo-write-suppressed by fixed executor-owned
  argv/env construction rather than by prompt intent; diagnosis may not hand
  recovery shell strings, raw argv fragments, or unsupported flags for
  execution
- hybrid delegation is admitted only if recovery can deterministically prove
  that the checked git-control tuples do not drift from baseline for
  `.git/index`, `HEAD`, every repo-local ref returned by `git for-each-ref` at
  baseline, including branch refs, tag refs, remote refs, and any other local
  ref namespaces present, plus remote config, and does not rely on prompt text
  as proof of that repo-local git-control immutability
- this packet's governance claim is intentionally narrower than a full
  preventive interposer: the hybrid path must fail closed on observed local
  git-control drift, but stronger adapter-/network-/PR-side governance
  blocking is a separate packet if still required
- recovery performs scope audit after implementer return, runs only the
  executor-owned validators admitted by this packet, then reruns the full
  scope audit after validator execution and before any success outcome so
  any validator-caused surviving drift remains inside the same observed-drift
  contract
- scope audit is lexical plus physical: declared in-scope paths must stay
  regular files at stable repo-root `realpath` locations, and the admitted
  implementer-owned `.scratch` exception set is path-exact rather than
  subtree-wide: only the repo-root `.scratch/` directory node plus the exact
  prompt/output artifact paths are tolerated at their stable repo-root
  `realpath` locations, repo-root inventory must still descend into
  `.scratch/`, and any other `.scratch/*` descendant, symlink presence,
  `readlink` target change, or file/link/directory type transition fails
  closed
- recovery decides whether to retry or escalate

This wave does **not** define hybrid recovery as:

- treating prompt text (`Do NOT modify files outside the plan's scope`) or
  `scope_hint` as sufficient proof of bounded surviving drift
- treating allowlisted control-surface prefix membership as sufficient proof
  that delegated scope matches this packet's exact runtime-delegable file list
- leaving delegated-run local git/state authority at prompt level rather than
  requiring recovery-owned git-control tuple capture and re-check
- treating unchanged local git-control evidence as proof that every banned
  governance surface was preventively blocked inside the adapter; stronger
  preventive governance interposition is outside this packet
- treating implementer self-report as the sole authority for what changed
- treating the first post-implementer scope audit as sufficient once validators
  have executed; validator-caused writes remain inside the same audit contract
- treating a path-set-only dirty-file delta, or a manifest limited to
  in-scope plus already-dirty out-of-scope paths, as sufficient proof of
  bounded surviving drift, or as proof that no transient out-of-scope
  create-delete or modify-restore touch occurred
- accepting symlink-resolved paths, a symlinked or relocated `.scratch/`
  container, symlinked prompt/output artifacts, or file-type transitions as
  inside the observed-drift contract
- letting learned patterns invent new shell behavior
- giving the diagnosis actor tool-use rights
- routing recovery through commit / push / merge surfaces
- reopening runtime / substrate files under `mu/host/`, `rcx_pi/`, seed files,
  or other non-control-surface paths
- routing recovery back through the bridge-backed implementer to repair
  `mu/tools/executors/phase_b_implementer.py`, `.agent_bus/bridge_config.json`,
  bridge adapter selection, or adapter invocation/bootstrap faults
- passing model-authored `validation_commands` through a denylist and then
  executing them as shell text
- pulling the full bridge/meta-review loop into recovery on the first slice

The learning store remains routing + warming only. For this slice it may warm
diagnosis or implementation prompts, but it does not expand write or validation
authority.

## Scope

This packet is intentionally limited to the control-surface files required to
add the hybrid branch and document it honestly:

1. `mu/tools/executors/recovery_gate.py`
2. `mu/tools/executors/phase_b_implementer.py`
3. `mu/tools/executors/executor_common.py`
4. `mu/tools/executors/executor_config.json`
5. `mu/tests/tools/test_recovery_gate.py`
6. `mu/tests/tools/test_phase_b_executor.py`
7. `mu/docs/agents/PipelineRecovery.v0.md`

These seven implementation paths are the exact writable packet surface for
landing this wave.

Runtime `delegate_implementer` scope is intentionally narrower to preserve the
bootstrap boundary proved by the reviewer-cited surfaces.
`files_in_scope` may resolve only to this two-file runtime delegation allowlist:

1. `mu/tools/executors/recovery_gate.py`
2. `mu/tools/executors/executor_common.py`

`mu/tools/executors/executor_config.json` remains inside the packet's exact
landing-time implementation surface because this wave may still need to add or
document the recovery rollout gate, but it is not an admissible runtime
`files_in_scope` target. The current config file is shared executor routing
state (`backends`, `bridge_reviewers`, `bridge_turn_timeouts`,
`review_depths`, and `timeouts`), so admitting it at runtime would let hybrid
recovery rewrite broader bridge/backend policy than this packet claims.

`mu/tests/tools/test_recovery_gate.py` and
`mu/tests/tools/test_phase_b_executor.py` also remain inside the packet's
landing-time implementation surface, but they are not admissible runtime
`files_in_scope` targets for this slice. Recovery may still use them as the
packet-owned `pytest_targeted` validator modules, and keeping them outside
runtime delegation prevents the delegated run from rewriting the exact tests it
later uses as proof.

`mu/tools/executors/phase_b_implementer.py` remains inside the packet's exact
landing-time implementation surface because this wave may need to adapt the
shared entrypoint, but it is not an admissible runtime `files_in_scope` target;
bridge-backed delegation may not be used to repair implementer / adapter /
bootstrap infrastructure or adapter resolution itself. Allowlisted
control-surface prefixes are only a secondary shape check; they may not admit
additional sibling files under the same tree.

`mu/docs/agents/PipelineRecovery.v0.md` also remains inside the packet's
landing-time implementation surface, but it is not an admissible runtime
`files_in_scope` target for this slice because the hybrid validator contract is
intentionally limited to packet-bounded `pytest_targeted` checks over the two
landing-surface-only validator modules and does not admit a packet-bounded doc
validator.

The packet draft itself remains authority-only. It may be rewritten during
Phase A review, but it is not part of the delegated hybrid implementation write
surface and may not be mutated by the runtime implementer branch.

A narrow execution-artifact exception is required because the current
implementer unconditionally ensures `repo_root/.scratch` exists and then writes
`.scratch/phase_b_implementer_prompt.md` plus
`.scratch/phase_b_implementer_output_<job>.txt` on every invocation. The scope
audit must therefore exempt only this exact implementer-owned `.scratch`
exception set: the repo-root `.scratch/` directory node as the container for
those artifacts, `.scratch/phase_b_implementer_prompt.md`, and
`.scratch/phase_b_implementer_output_<job>.txt`. Those exact paths/patterns are
executor-owned transient byproducts, not packet-scope product writes. This
allowance is path-exact, not a subtree exclusion: repo-root inventory must keep
the `.scratch/` container visible as a directory node, descend into it, and
surface any other `.scratch/*` descendant as out of scope. Recovery may
tolerate first-run creation of the repo-root `.scratch/` directory or reuse of
a pre-existing directory at that exact `realpath`, but no other `.scratch/`
descendant, rename, symlink, or file-type transition is exempt. The container
must remain a directory at the stable repo-root `realpath`; the prompt/output
paths must remain regular files at their stable repo-root `realpath`
locations.

Although `.git/` remains outside the broad repo-root inventory, hybrid recovery
must separately capture and re-check a delegated-run git-control baseline over
`.git/index`, `HEAD`, every repo-local ref returned by `git for-each-ref` at
baseline, including branch refs, tag refs, remote refs, and any other local
ref namespaces present, plus remote config. Any delta in that git-control
tuple fails closed.

That git-control tuple is intentionally repo-local evidence, not a transport or
network sandbox. It can prove local `.git` / ref immutability and fail closed
on observed drift, but it does not by itself prove that every remote or PR-side
governance attempt was preemptively blocked.

If implementation discovers that deterministic changed-file enforcement or
executor-owned validation requires widening into dispatcher, commit, or other
non-listed surfaces, stop and spin a separate packet rather than widening this
wave silently.

## Work Items

### A. Add a structured `delegate_implementer` Tier 3 action

Extend the Tier 3 diagnosis contract so the recovery agent may return a bounded
delegation payload with declared scope and structured validation selection, for
example:

```json
{
  "action": "delegate_implementer",
  "commands": [{
    "summary": "...",
    "files_in_scope": ["mu/tools/executors/recovery_gate.py"],
    "validation_spec": [{
      "validator": "pytest_targeted",
      "targets": ["mu/tests/tools/test_recovery_gate.py"]
    }],
    "why_not_shell_edit": "requires coordinated multi-file code change"
  }],
  "explanation": "..."
}
```

For compatibility with the current Tier 3 response envelope,
`delegate_implementer` continues to use a top-level `commands` array. For this
action that array is singleton-only: it must contain exactly one object, and
recovery defines no merge, union, or ordered-composition semantics across
multiple entries.

Requirements:

1. `delegate_implementer.commands` must contain exactly one object; zero
   entries, multiple entries, or non-object members fail closed before any
   scope or validation evaluation
2. malformed payloads fail closed before any implementer launch
3. recovery status / log entries distinguish diagnosis, implementer delegation,
   post-run scope audit, and verification
4. existing `shell`, `edit`, `skip`, and `escalate` actions remain supported
5. raw shell `validation_commands` are not accepted for
   `delegate_implementer`
6. `validation_spec` is a closed schema for this wave:
   - allowed `validator` value is only `pytest_targeted`
   - `pytest_targeted` accepts only a non-empty `targets` list drawn from
     `mu/tests/tools/test_recovery_gate.py` and
     `mu/tests/tools/test_phase_b_executor.py`; those packet-owned validator
     modules remain outside runtime `files_in_scope`, and executor builds the
     fixed pytest argv/env internally, including `-p no:cacheprovider`,
     `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, and isolated `TMPDIR` /
     `XDG_CACHE_HOME` roots outside repo root so repo-local validator side
     effects are suppressed by contract
7. targetless repo-global validators, including `docs_consistency`, are
   intentionally outside the hybrid runtime contract for this slice because the
   current docs-consistency command validates repo-wide tracker/doc state
   rather than the packet-bounded recovery surface
8. `args` is not part of the hybrid contract; any supplied `args`, unknown
   validator id, unsupported field, duplicate/empty target list, or
   out-of-allowlist target fails closed before verification

### B. Enforce observed delegated-run drift against declared scope

Before recovery launches the implementer, validate the returned plan:

1. `files_in_scope` must be non-empty and capped to the exact two-path runtime
   delegation allowlist defined in `## Scope`;
   `mu/tools/executors/phase_b_implementer.py` remains packet-implementation-
   scope only and is not an admissible runtime delegated target
2. every file must normalize under repo root, match one of the exact runtime-
   delegable paths listed in `## Scope`, and only secondarily fall under an
   allowlisted control-surface prefix
3. recovery must validate declared scope both lexically and physically: each
   declared in-scope path and each member of the admitted implementer-owned
   `.scratch` exception set must be checked with `lstat` plus `realpath`, and
   recovery must fail closed if any declared in-scope path is a symlink or
   non-regular file, if repo-root `.scratch/` is not a directory at the exact
   admitted `realpath`, if any prompt/output exception path is a symlink or
   non-regular file once materialized, if any resolved path escapes repo root,
   or if any resolved path no longer matches the exact repo-relative path
   admitted by this packet
4. if diagnosis needs any control-surface file outside the runtime delegation
   allowlist in `## Scope`, including landing-surface-only files such as
   `mu/tools/executors/executor_config.json`,
   `mu/tests/tools/test_recovery_gate.py`, or
   `mu/tests/tools/test_phase_b_executor.py`, or needs to repair bridge / adapter /
   implementer bootstrap surfaces such as
   `mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, or adapter selection / invocation itself,
   hybrid delegation must fail closed and leave that edit to non-delegated
   landing work or a separate packet rather than silently widening within the
   same prefix tree
5. hard denylist:
   - `mu/host/`
   - `rcx_pi/`
   - `.git/`
   - `.agent_bus/`
   - `.claude/`
   - `archive/`
   - repo-escape paths such as `../...`
6. admit only the current implementer-owned `.scratch` exception set as an
   exact-node scope-audit exception: the repo-root `.scratch/` directory node
   plus
   `.scratch/phase_b_implementer_prompt.md` and
   `.scratch/phase_b_implementer_output_<job>.txt`; they are executor-owned
   byproducts, not packet-scope writes, the allowance does not exempt the
   `.scratch/` subtree from traversal, and no other `.scratch/` path is exempt

Before implementer launch, recovery must also capture a run-local scope-audit
baseline:

7. record a deterministic manifest for every pre-existing file path in the
   worktree outside `.git/`, including every validated in-scope path plus every
   pre-existing out-of-scope file path not covered by that exact
   implementer-owned `.scratch` exception set, capturing at least relative
   path, existence state, scope classification, file type, stable `realpath`,
   `readlink` target when applicable, and content fingerprint
8. record a deterministic repo-root path inventory for the full worktree,
   excluding only `.git/` from traversal; keep the repo-root `.scratch/`
   container visible as a directory node, descend into it, and classify only
   the exact admitted `.scratch` container/prompt/output nodes as exception
   entries, capturing path, file type, and `readlink` target when applicable
   so the post-run audit can discover created/deleted/type-changed paths that
   were not part of the pre-run file manifest
9. define this manifest + inventory mechanism as surviving-drift evidence only:
   it can detect persisted out-of-scope file/path/type/link changes that remain
   at the pre-validation and post-validation checkpoints, but it cannot by
   itself prove the absence of transient create-delete or modify-restore
   touches that leave no trace by the time the post-run snapshot is taken
10. record a deterministic delegated-run git-control baseline because `.git/`
    is excluded from the broad path inventory; capture at least `HEAD`
    target/oid, current branch symbolic-ref or detached state, `.git/index`
    fingerprint, full repo-local ref inventory/fingerprints as returned by
    `git for-each-ref` at baseline, including branch refs, tag refs, remote
    refs, and any other local ref namespaces present, plus `.git/config`
    remote-stanza fingerprint

After implementer delegation, recovery must:

11. recompute the full pre-existing-file manifest, the filtered repo-root path
    inventory, and the delegated-run git-control tuple immediately after
    implementer return and before any verification run
12. define the pre-validation observed-drift set as: (a) manifest paths whose
    existence state, file type, stable `realpath`, or content fingerprint
    changed during this run, including any pre-existing clean or dirty
    out-of-scope file, plus (b) any created, deleted, or type-changed path
    discovered from the pre/post repo-root inventory diff after filtering only
    the exact admitted `.scratch` container/prompt/output nodes while
    preserving `.scratch/` traversal
13. require that pre-validation observed-drift set be a subset of the
    validated `files_in_scope` before any verification run, and require the
    post-implementer git-control tuple to match the pre-launch baseline
    exactly
14. after validator execution, recompute the same full manifest, filtered
    repo-root path inventory, and delegated-run git-control tuple again against
    the original pre-launch baseline and define the final observed-drift set
    for the entire delegated run, including validator-caused writes that still
    survive to the final checkpoint
15. require that final observed-drift set be a subset of the validated
    `files_in_scope` and that the final git-control tuple still match the
    original pre-launch baseline before any success outcome; validation success
    alone is insufficient, and snapshot equality is not described as proof
    against transient out-of-scope touches that leave no post-run trace
16. fail closed if scope-audit evidence cannot be produced, if any pre-existing
    out-of-scope file not on that exact exception set changes during the run
    whether it was clean or dirty at baseline, if any symlink appears or any
    `readlink` target or file type changes for a declared or discovered path,
    if either the pre-validation or post-validation repo-root inventory diff,
    including traversal under repo-root `.scratch/`, reveals any created,
    deleted, or type-changed out-of-scope path outside the exact admitted
    container/prompt/output nodes, or if either checked git-control tuple
    differs from baseline for `.git/index`, `HEAD`, any repo-local ref
    returned by `git for-each-ref`, or remote config
17. treat prompt-level scope instructions and implementer self-attestation as
    advisory only; they do not satisfy the bounded-authority requirement

### C. Reuse the existing Phase B implementer as the mutating actor

Do not invent a new code-writing surface.

Instead:

1. invoke `phase_b_implementer.invoke_implementer()` from recovery only for
   valid `delegate_implementer` plans whose repair surface is outside bridge /
   adapter / implementer bootstrap infrastructure and only after
   recovery-owned scope audit plus delegated-run git-control baseline capture
   are active for the delegated run
2. reject `delegate_implementer` before launch if the failed surface or
   declared scope touches `mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, bridge adapter loading / selection, or
   adapter invocation/bootstrap resolution; those cases preserve the older
   no-bridge bootstrap boundary and must escalate or spin a separate packet
3. reuse the configured code-writing backend already used by
   `phase_b_executor` rather than introducing a separate hardcoded CLI path
4. keep the existing implementer prompt as an instruction surface, but pair it
   with recovery-owned changed-file and git-control immutability checks rather
   than treating prompt text or `scope_hint` as enforcement
5. pair the hybrid path with a repo-local git-control immutability guard sized
   to the current implementer surface. At minimum, the hybrid path must:
   - reject success if `.git/index`, `HEAD`, any repo-local ref returned by
     `git for-each-ref` at baseline, including branch refs, tag refs, remote
     refs, and any other local ref namespaces present, or remote config drift
     from the captured recovery-owned baseline
   - treat prompt-level no-stage/commit/push/branch/remote/PR language as
     advisory only; this packet does not claim repo-local recovery can preempt
     every governance attempt before the adapter runs
   - fail closed and split a separate packet if stronger preventive governance
     interposition is required at the adapter / bridge boundary
6. reuse or adapt the existing pre/post changed-file collection pattern already
   present in `phase_b_executor.py:2378-2454`, but tighten it for recovery into
   run-local existence/fingerprint evidence for every pre-existing file path
   outside `.git/` plus a repo-root pre/post path inventory that detects
   surviving created/deleted out-of-scope paths; do not rely on implementer
   self-report as the sole authority and do not describe snapshot-only
   evidence as a per-write trace for transient touches that leave no post-run
   trace
7. inject `load_relevant_learnings("implementer", files_in_scope, repo_root)`
   into the recovery implementer prompt so learned pipeline fixes can warm the
   delegated code writer without expanding authority

This slice reuses the existing implementer entrypoint and backend. It does not
inherit the current prompt-only scope model as sufficient authority control.

### D. Replace model-authored shell validation with executor-owned verification

After implementer delegation:

1. recovery accepts only structured `validation_spec` data that maps to an
   executor-owned closed validator allowlist with repo-write suppression
   defined by contract; for this wave that allowlist is only
   `pytest_targeted`
2. executor, not diagnosis, owns argv construction:
   - `pytest_targeted` maps only to a fixed pytest builder over the packet-
     owned validator modules
     `mu/tests/tools/test_recovery_gate.py` and
     `mu/tests/tools/test_phase_b_executor.py`, which remain outside runtime
     `files_in_scope`, with at minimum
     `[sys.executable, "-m", "pytest", "-x", "--tb=short",
     "-p", "no:cacheprovider", *targets]` plus fixed env
     `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, and isolated `TMPDIR` /
     `XDG_CACHE_HOME` roots outside repo root
3. targetless repo-global validators such as `docs_consistency` are not
   admitted in the hybrid runtime path for this slice
4. any supplied `args`, unsupported flag/profile surrogate, unknown validator
   id, unsupported field, or out-of-allowlist target fails closed before
   verification
5. any current dangerous-command denylist helpers remain defense in depth, not
   the primary verification contract for this slice
6. validation pass returns the same recovery semantics used today for
   "fix applied, retry requested" only after the post-validation scope audit
   passes
7. validation failure feeds the new stdout/stderr back into the next Tier 3
   diagnosis iteration
8. no `shell=True` execution of model-authored validation text is allowed in
   the hybrid path
9. the structured validator contract itself admits no commit, stage, push,
   fetch, branch-switch, PR, or merge surface, and recovery reuses the same
   repo-local git-control audit around validator execution; this packet does
   not claim that local audit alone is a full preventive interposer for
   implementer-side remote/PR attempts

### E. Roll out behind an explicit config gate

Add a recovery-specific rollout flag in executor config:

- `hybrid_recovery_enabled: false` by default

Optionally add a dedicated timeout key if implementation proves the
`phase_b_executor` timeout budget is too broad for recovery:

- `timeouts.recovery_implementer`

Because `mu/tools/executors/executor_config.json` carries shared backend /
bridge / timeout routing, this rollout gate remains landing-surface-only for
the packet and may not be mutated by the runtime `delegate_implementer`
branch.

Do not enable hybrid recovery by default in the same wave that first lands the
code. Land the mechanism behind the flag first.
Acceptance must prove two rollout invariants: the loaded
`hybrid_recovery_enabled` default resolves to `false`, and a
`delegate_implementer` diagnosis cannot launch the implementer or reach a
hybrid success path while that gate is `false` or absent.

### F. Update the design doc to match the new branch honestly

`mu/docs/agents/PipelineRecovery.v0.md` must reflect:

1. deterministic tiers unchanged
2. learning store remains routing/warming only
3. Tier 3 gains a bounded implementer-delegation branch only if recovery
   enforces surviving-drift scope via the packet's manifest/inventory
   checkpoints and owns verification without overstating that snapshot audit as
   proof against transient out-of-scope touches
4. the previous bootstrap boundary remains in force for bridge / adapter /
   implementer bootstrap failures and adapter resolution; those surfaces are
   not eligible for `delegate_implementer`
5. hybrid delegation is guarded by recovery-owned repo-local git-control
   immutability evidence, not a claimed full preventive sandbox over
   adapter/remote/PR governance surfaces
6. hybrid verification uses executor-owned validators with explicit
   repo-write suppression for `pytest_targeted`, not model-authored shell text
7. full bridge/meta-review integration remains a separate follow-on if still
   wanted after the bounded implementer slice proves useful

## Constraints

1. Do not weaken Tier 1 / Tier 2 deterministic fixes.
2. Do not allow learned patterns to emit new shell commands or arbitrary edits.
3. Do not give the diagnosis prompt tool-use rights in this slice.
4. Do not widen into runtime/substrate files (`mu/host/`, `rcx_pi/`, seeds,
   JS parity surfaces, or host-semantics policy docs).
5. Do not widen this slice into adapter / bridge transport hardening to
   preempt every stage, commit, push, fetch, switch-branch, remote, or PR
   attempt. This packet is limited to repo-local git-control immutability
   evidence plus a closed validator contract.
6. Do not use `delegate_implementer` to repair
   `mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, bridge adapter loading / selection, or
   adapter invocation/bootstrap failures; those surfaces remain outside
   runtime hybrid eligibility for this wave.
7. Do not treat prompt text or unchanged worktree file paths as sufficient
   proof that git index / `HEAD` / repo-local ref / remote-config state stayed
   unchanged; hybrid recovery must separately enforce delegated-run git-control
   immutability over the local tuple it can actually measure, including tag
   refs and any other repo-local refs surfaced by `git for-each-ref`.
8. Do not treat prompt text, `scope_hint`, allowlisted-prefix membership, or
   implementer self-report as sufficient proof that the observable delegated-
   run drift stayed inside this packet's exact runtime-delegable scope. For
   this slice that runtime scope is code-only and does not admit shared
   `mu/tools/executors/executor_config.json` or the validator modules
   `mu/tests/tools/test_recovery_gate.py` /
   `mu/tests/tools/test_phase_b_executor.py`.
9. Do not treat a path-set-only dirty-file delta, or a manifest that omits
   pre-existing clean out-of-scope files, as sufficient proof of bounded
   surviving drift, and do not describe the packet's pre/post
   manifest/inventory snapshots as proof that no transient out-of-scope
   create-delete or modify-restore touch occurred.
10. Do not admit symlinked in-scope paths, a symlinked or relocated `.scratch/`
    container, symlinked prompt/output exceptions, `readlink` target changes, or
    file/link/directory type transitions as inside the observed-drift contract.
11. Do not let hybrid verification accept raw shell strings, free-form `args`,
    unknown validator ids, targetless repo-global validators such as
    `docs_consistency`, unsupported fields, or depend on `shell=True`
    execution of model-authored text. Do not describe `pytest_targeted` as
    read-only unless executor-owned argv/env disables pytest cacheprovider,
    suppresses bytecode writes, and isolates temp/cache roots outside repo
    root. Do not let the delegated run rewrite the same validator modules that
    `pytest_targeted` later executes.
12. Do not treat the first post-implementer scope audit as sufficient for
    success; recovery must rerun the manifest/inventory audit after validator
    execution and before any hybrid success classification, and the same rule
    applies to the git-control tuple.
13. Do not add a new review/supervisor subsystem in this slice. Reuse existing
    implementer infrastructure only.
14. Do not silently change dispatcher semantics. If dispatcher support is
    needed, stop and split a dedicated packet.
15. Do not broaden the `.scratch/` exception beyond the exact repo-root
    `.scratch/` container node plus the `phase_b_implementer.py` prompt/output
    artifacts already created by the current implementer, and do not treat that
    allowance as a subtree exclusion; repo-root inventory must still descend
    into `.scratch/` so any other descendant mutation remains out of scope.
16. Do not give `delegate_implementer` merge, union, or ordered-composition
    semantics across multiple `commands` entries; this action is singleton-only
    and must fail closed on zero or multiple payload objects.

## Stop Conditions

1. Tier 3 accepts `delegate_implementer` only when the payload is structurally
   valid, `commands` contains exactly one delegation object with no
   merge/composition semantics, `validation_spec` matches the closed executor-
   owned validator schema for `pytest_targeted` only, and recovery can verify
   that both the pre-validation and final observed-drift sets stay within the
   validated code-only runtime-delegable declared scope, not merely an
   allowlisted prefix, while delegated-run git-control state
   (`.git/index`, `HEAD`, repo-local refs observed via `git for-each-ref`,
   and remote config) remains unchanged in the checked tuples and no symlink
   or file-type drift appears. This packet treats that as surviving-drift
   evidence, not as proof against transient out-of-scope touches that leave no
   post-run trace.
2. Any malformed, dangerous, out-of-scope, unauditable, git-state-mutating, or
   symlink/type-transitioning hybrid payload/run
   fails closed before success classification, including runs that begin from a
   clean or dirty worktree where any pre-existing out-of-scope file outside
   the exact admitted implementer-owned `.scratch` exception set changes during
   delegation other than first-run creation or reuse of the repo-root
   `.scratch/` container plus the exact prompt/output artifacts, where either
   the pre-validation or post-validation repo-root inventory diff, with
   `.scratch/` traversal preserved, reveals a created/deleted/type-changed
   out-of-scope path outside the exact admitted container/prompt/output nodes,
   or where either checked git-control tuple drifts from the captured
   baseline.
3. Any diagnosis or declared scope that reaches bridge / adapter /
   implementer bootstrap infrastructure, including
   `mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, or adapter resolution / invocation faults,
   is not eligible for `delegate_implementer`; recovery must fail closed out of
   the hybrid branch and escalate or split a separate packet without launching
   the implementer.
4. Recovery can reuse the existing code-writing actor without introducing a new
   mutating subsystem, but prompt-only scope or git/governance language is not
   treated as enforcement, and this packet's governance proof is limited to
   repo-local git-control immutability evidence rather than a blanket
   preventive interposer over remote/PR surfaces.
5. Validation is recovery-owned, executor-built, and repo-write-suppressed
   after implementer delegation; the hybrid branch does not execute
   model-authored shell text, raw argv fragments, or unsupported validator
   specs, and it does not let the delegated run rewrite the validator modules
   that `pytest_targeted` later executes.
6. Tier 1 / Tier 2 / Tier 4 behavior is unchanged by the hybrid addition.
7. The learning store remains advisory (routing + warming), not behavior-
   defining.
8. The feature lands disabled by default behind an explicit config gate, and
   when `hybrid_recovery_enabled` is `false` or absent the hybrid branch cannot
   launch `delegate_implementer` or classify a hybrid success.

## Acceptance Criteria

1. `mu/tests/tools/test_recovery_gate.py` proves a valid
   `delegate_implementer` response invokes the reused implementer path, passes
   both the pre-validation scope audit and the post-validation scope audit
   derived from run-local pre/post existence/fingerprint evidence for every
   pre-existing file path outside `.git/` plus a repo-root pre/post path
   inventory, keeps the delegated-run git-control tuples unchanged against the
   captured baseline, including `.git/index`, `HEAD`, repo-local refs returned
   by `git for-each-ref`, and remote config, and returns a retry-requested
   recovery result only after verification passes and the second audit remains
   in scope.
2. `mu/tests/tools/test_recovery_gate.py` proves invalid `files_in_scope`
   entries are rejected fail-closed before any implementer launch, including
   paths under an otherwise allowlisted control-surface prefix that are not one
   of this packet's exact runtime-delegable files, the landing-surface-only
   shared config `mu/tools/executors/executor_config.json`, the landing-surface-
   only validator modules `mu/tests/tools/test_recovery_gate.py` and
   `mu/tests/tools/test_phase_b_executor.py`, plus `mu/host/...`, `.git/...`,
   `.claude/...`, repo-escape paths, and symlink-resolved or non-regular-file
   targets that fail the `lstat` / `realpath` contract.
3. `mu/tests/tools/test_recovery_gate.py` proves bridge-backed hybrid
   delegation is rejected before any implementer launch when the failed
   surface or declared scope touches
   `mu/tools/executors/phase_b_implementer.py`,
   `.agent_bus/bridge_config.json`, bridge adapter loading / selection, or
   adapter invocation/bootstrap resolution.
4. `mu/tests/tools/test_recovery_gate.py` proves a conforming delegated run
   may create repo-root `.scratch/` on first use and create or update only
   `.scratch/phase_b_implementer_prompt.md` plus
   `.scratch/phase_b_implementer_output_<job>.txt` without self-failing the
   scope audit when the container remains a directory and those exact artifacts
   remain regular files at stable `realpath` locations, while repo-root
   inventory still descends into `.scratch/` and any other `.scratch/`
   create/delete/symlink/type change still fails closed as out of scope.
5. `mu/tests/tools/test_recovery_gate.py` proves a delegated implementer run
   that mutates a pre-existing clean out-of-scope file, mutates an
   already-dirty out-of-scope path, or creates/deletes an out-of-scope path
   discovered from the pre/post repo-root inventory diff, or introduces a
   symlink / `readlink` target change / file-type transition, is detected and
   fails closed before verification or success classification.
6. `mu/tests/tools/test_recovery_gate.py` proves any delegated implementer or
   validator run that produces observed drift in `.git/index`, moves `HEAD`,
   changes any repo-local ref returned by `git for-each-ref` at baseline,
   including branch refs, tag refs, remote refs, or other present local ref
   namespaces, or changes remote config fails closed before hybrid success, and
   hybrid success is never classified on prompt text alone when that
   git-control tuple drifts.
7. `mu/tests/tools/test_recovery_gate.py` proves hybrid delegation rejects raw
   shell `validation_commands`, free-form `args`, zero-entry or multi-entry
   `commands` envelopes, unsupported validator ids including targetless
   repo-global validators such as `docs_consistency`, unsupported fields, and
   out-of-allowlist targets, and accepts only a singleton-object `commands`
   envelope plus the structured executor-owned `validation_spec` contract.
8. `mu/tests/tools/test_recovery_gate.py` proves hybrid validation is executed
   only through executor-owned `pytest_targeted` argv/env construction,
   including `pytest_targeted` cacheprovider disablement, bytecode suppression,
   isolated temp/cache roots outside repo root, and validator targets that stay
   outside runtime `files_in_scope`, not through model-authored `shell=True`
   text, and that any residual validator-caused out-of-scope write is detected
   by the post-validation audit before success classification.
9. `mu/tests/tools/test_recovery_gate.py` proves validation failure after a
   delegated implementer run feeds new stdout/stderr back into the next Tier 3
   iteration instead of falsely succeeding.
10. `mu/tests/tools/test_recovery_gate.py` proves terminal-policy outcomes still
   escalate and never route into the hybrid branch.
11. `mu/tests/tools/test_recovery_gate.py` proves the loaded executor config
   defaults `hybrid_recovery_enabled` to `false` and that a
   `delegate_implementer` diagnosis cannot launch the implementer or reach the
   hybrid success path while that gate is `false` or absent.
12. `mu/tests/tools/test_phase_b_executor.py` proves the reused implementer
   prompt path still behaves as a code-writing actor and still accepts
   injected learning context, while the recovery audit layer upgrades existing
   pre/post path-set tracking into worktree-wide authority evidence and
   git-control immutability checks rather than prompt-only enforcement.
13. `mu/docs/agents/PipelineRecovery.v0.md` is updated so the scope-audit
   requirement is described honestly as pre/post manifest + repo-root
   inventory surviving-drift evidence rather than proof against transient
   create-delete/modify-restore touches, and the seven-file packet landing
   surface, two-file runtime delegation allowlist with shared executor config
   plus validator test modules kept landing-surface-only and the design doc
   also kept landing-surface-only, singleton `delegate_implementer.commands`
   contract, exact admitted `.scratch` nodes plus mandatory `.scratch/`
   traversal rule, executor-owned `pytest_targeted`-only validation contract
   with pytest side-effect suppression over runtime-immutable validator
   targets, delegated-run git-control contract over `.git/index`, `HEAD`,
   every repo-local ref returned by `git for-each-ref`, including tags, plus
   remote config, retained bootstrap boundary for bridge / adapter /
   implementer faults, symlink/type fail-closed rules, and retained learning-
   store constraint are all explicit.

## Grounding / Authorization

Current authorization remains the active `[PIPELINE-RECOVERY]` task in
`TASKS.md:183-194`, which authorizes the recovery lane, records the explicit
2026-04-16 founder exception for this wave, and points at
`mu/docs/agents/PipelineRecovery.v0.md` and
`mu/tools/executors/recovery_gate.py` as the governing design/file anchors.
`TASKS.md:191-194` routes the active 2026-04-16 hybrid-recovery wave to this
packet path and labels it the `Tracked packet`. Reviewer-cited git evidence
shows that `reports/control_plane/hybrid_recovery_agent_2026-04-16.md` is
present in the index at stage 0 but absent from `HEAD`. This rewrite therefore
treats that path as the active tracked packet for
`hybrid-recovery-agent-2026-04-16`, while not overstating it as a landed
governing packet in `HEAD`.

Repo-grounded evidence for this blocking rewrite:

1. `TASKS.md:183-194` is the active parent authorization for the
   `[PIPELINE-RECOVERY]` control-surface lane and points at
   `mu/docs/agents/PipelineRecovery.v0.md` plus
   `mu/tools/executors/recovery_gate.py` as the governing design/file anchors.
2. That same TASKS block now records the explicit 2026-04-16 founder exception
   authorizing this wave's narrow non-bootstrap reuse of
   `phase_b_implementer` while preserving the bootstrap boundary for bridge /
   adapter / implementer infrastructure and adapter resolution itself.
3. `TASKS.md:191-194` records this path as the active packet location for the
   2026-04-16 hybrid-recovery wave and explicitly labels it the `Tracked
   packet`; reviewer-cited git evidence shows the path is staged in the index
   at stage 0 but absent from `HEAD`, so this rewrite treats it as the active
   tracked packet for the in-flight wave rather than denying tracking or
   overstating it as a landed governing packet in `HEAD`.
4. Within that parent authorization, this draft packet scopes bounded reuse of
   `phase_b_implementer` for the hybrid branch, but only within the narrower
   runtime eligibility rules stated above.
5. `mu/docs/agents/PipelineRecovery.v0.md:123-142` still documents Tier 3 as a
   direct `claude --print` recovery loop specifically to avoid Phase B / bridge
   stack bootstrap paradox, which is why this packet must update that design
   doc as part of landing the now-recorded exception.
6. `mu/tools/executors/phase_b_implementer.py:289-293` shows that
   `invoke_implementer()` unconditionally ensures repo-root `.scratch/` exists
   via `mkdir(exist_ok=True)` before writing the prompt/output artifacts, so
   the packet's exception set must admit the exact `.scratch/` container in
   addition to those two artifact paths.
7. `mu/tools/executors/phase_b_executor.py:797-815` shows that the current
   targeted pytest helper still runs plain
   `[sys.executable, "-m", "pytest", "-x", "--tb=short", *test_files]` with
   only `PYTHONHASHSEED=0`, so this packet must require explicit
   cache/bytecode/temp suppression before it can honestly describe
   `pytest_targeted` as repo-write-suppressed.
8. `mu/tools/executors/executor_config.json:1-40` shows shared `backends`,
   `bridge_reviewers`, `bridge_turn_timeouts`, `review_depths`, and
   `timeouts`, so this rewrite keeps the file in packet landing scope only and
   removes it from runtime `files_in_scope` rather than claiming hybrid
   recovery may rewrite shared executor routing.
9. The bridge-reviewer evidence for this rewrite proved that treating
   `mu/tests/tools/test_recovery_gate.py` and
   `mu/tests/tools/test_phase_b_executor.py` as both runtime-delegable writes
   and the only `pytest_targeted` validators would make hybrid verification
   self-certifying. This rewrite therefore keeps those test modules packet-
   owned but runtime-immutable.
10. `mu/tools/executors/recovery_gate.py:2068-2076` and `:2360-2423` still
   define and consume a plural `commands` envelope, so this packet must pin
   `delegate_implementer` to a singleton `commands` object rather than leaving
   multi-entry composition ambiguous.
11. `tools/checks/check_docs_consistency.sh:13-184` validates repo-wide
   `STATUS.md`, `TASKS.md`, README, roadmap, and cross-tracker tests, so it is
   not a packet-bounded runtime validator and is removed from the hybrid
   `validation_spec` allowlist for this slice.
12. Repo-local `git for-each-ref --format='%(refname)' refs/tags` returns
    existing tag refs in this repository, so the packet's git-control tuple
    must cover tag refs and, more generally, the repo-local ref inventory
    returned by `git for-each-ref` rather than only branch/remote refs.

## Validation

Minimum doc / control-surface validation for the packet draft itself. These are
packet-draft checks, not the hybrid runtime `validation_spec` allowlist:

- `./tools/checks/check_docs_consistency.sh`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/docs/test_status_tasks_consistency.py -q --tb=short`

Implementation-wave validation is intentionally deferred until the packet is
routed and the code slice exists.
