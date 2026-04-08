# Wave 2 (Tooling) Active Residue

Archived source snapshot:

- `reports/archive/deferred/redteam_2026-03-09_wave2.md`

Archived from the source snapshot as stale:

- item 14 (`JS parity NOT hard-gated in CI`) no longer belongs in the active
  residue because `scripts/green_gate.sh` still runs JS parity checks in the
  merge path

## Open Items

### 1. GitHub Actions are still tag-pinned rather than SHA-pinned — RESOLVED (2026-03-14)
SHA-pinned all 5 actions across 8 workflow files (27 replacements). Version comments preserved.

### 2. `$WAVE_ID_FLAG` is still passed unquoted in several shell/CI paths — PARTIALLY RESOLVED (2026-03-14)
CI workflows (ci.yml, green_gate.yml) now use `--wave-id=<suffix>` via derive_wave_id.sh. pre-push-fast and audit_fast.sh still use inline unquoted pattern.
**Why remaining parts deferred:** pre-push-fast and audit_fast.sh are local-only scripts
(not CI). The unquoted pattern is correct shell — `$WAVE_ID_FLAG` intentionally
word-splits into `--wave-id <suffix>` when set and vanishes when empty. Git branch names
cannot contain spaces. The `=` syntax fix in CI (derive_wave_id.sh) handles the `--prefix`
edge case. Local scripts don't need the same defense because branch names are developer-controlled.
**Target wave:** CI refactor wave (migrate pre-push-fast to source derive_wave_id.sh too).

### 3. Tooling exemptions from host-semantics scanning still rely on convention
**Why deferred:** The ratchet scanner (`check_host_semantics_ratchet.py`) scans
`rcx_pi/selfhost/` and `mu/host/js/` — these paths are hardcoded, not convention-based.
The "convention" concern is about tools/scripts that ALSO contain host patterns but are
not scanned. This is by design — tools/ are tooling, not runtime. Scanning them would
cause false positives (tool scripts legitimately use Python builtins, loops, etc.).
**No fix needed** — the scope boundary (selfhost/ + mu/host/js/) is the correct scanning surface.

### 4. Wrapper scripts still lack staleness detection
**Why deferred:** Wrapper scripts (e.g., `tools/debt_dashboard.sh` → `tools/util/debt_dashboard.sh`)
are 2-line `exec` redirects. They become stale only if the canonical script is deleted, which
would cause an immediate runtime error. Adding staleness detection (e.g., checking if the target
exists before exec) adds complexity for a failure mode that's already fail-fast.
**What would help:** A CI check that validates all wrapper targets exist. Low priority — the
failure mode is obvious and immediate. **Target wave:** CI refactor wave.

### 5. Wave-ID branch-prefix coupling is still under-defended
**Why deferred:** The wave-ID is derived from branch name prefix (`codex/X` → `X`,
`jabramsja/X` → `X`). If someone pushes from an unrecognized prefix, wave-ID is
simply empty and the L4 contract runs without it (permissive, not restrictive).
The risk is low — this is a single-developer repo. Adding more prefixes or a
configurable list adds complexity without reducing risk.
**Target wave:** Only if additional developers are onboarded.

### 6. Wave-ID derivation logic is still duplicated across CI workflows — RESOLVED (2026-03-14)
Extracted to `tools/checks/derive_wave_id.sh`, sourced by ci.yml and green_gate.yml.

### 7. Fixture gates still use repeated near-identical jobs instead of a matrix
**Why deferred:** 5 jobs in fixture_gates.yml share checkout + setup-python but differ in:
(a) which gate script they run, (b) whether they need Graphviz installed, (c) whether they
need jsonschema. A matrix would need conditional steps for Graphviz/jsonschema, which makes
the YAML harder to read for minimal DRY benefit (each job is 5-10 lines).
**Risk of change:** CI workflow refactors can break in ways that are hard to test locally.
The current pattern is explicit and works. **Target wave:** CI refactor wave (low priority).

### 8. Environment/setup repetition still lacks a shared composite action
**Why deferred:** Creating a `.github/actions/setup-rcx/action.yml` composite action would
reduce ~15 lines of setup repetition across 8 workflows. However: (a) composite actions add
a layer of indirection that makes CI debugging harder, (b) the setup steps differ slightly
between workflows (some need Node.js, some need Graphviz, some need ripgrep), (c) the
current explicit setup is easy to audit. **Net: diminishing returns.** The SHA-pinning
already addressed the main security concern. **Target wave:** CI refactor wave (low priority).

### 9. Range-derivation logic still differs across workflows
**Why deferred:** ci.yml and green_gate.yml handle different event types (ci.yml only handles
push, green_gate.yml handles push + pull_request + schedule + workflow_dispatch). The range
derivation MUST differ because the base SHA comes from different GitHub event contexts.
The tracker-sync step has its own range logic (separate from L4 contract) because it serves
a different purpose. **This is not duplication — it's correctly different logic for different
inputs.** Extracting would require a script that handles all event types, adding complexity.
**No fix planned** — the current per-workflow logic is correct for its context.

### 10. `check_simulated_production_logic.py` still has the fallback parser path — RESOLVED (2026-03-14)
### 11. `agent-review.yml` still lacks strict numeric validation for PR input — RESOLVED (2026-03-14)
### 12. `agent-review.yml` permissions are still broader than necessary — RESOLVED (2026-03-14)

Note:

- the older dead-script item for `check_boot1_merge2_readiness.sh` was already
  resolved by a later cleanup wave and is no longer part of the active residue
