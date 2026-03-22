# Deferred: Post-Merge Supervisor Phase A Non-Blockers

**Source:** SDK agent review (5 agents, --depth full) + 9 bridge rounds (2026-03-21)
**Classification:** NON-BLOCKING (design hardening and pre-existing issues)

## Pre-Existing: Envelope Injection via Regex First-Match

**Source:** Adversary agent (Phase A review)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:785`
**Issue:** `META_ENVELOPE_RE` uses `re.search()` which returns the FIRST match.
If Codex includes an example `BEGIN_META_ENVELOPE` block in its preamble text
(reasoning, quoting the template), that example block is parsed as the real
decision instead of the actual decision block.
**Impact:** Pre-existing in the pre-commit supervisor. Not introduced by the
post-merge design. Affects both modes.
**Recommended fix:** Parse the LAST match instead of the first, or require the
envelope at the end of output with no trailing content.
**Classification:** Pre-existing, not blocking post-merge implementation.

## Design-Level: Sandbox Trust Boundary

**Source:** Adversary agent (Phase A review)
**File:** `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md:49`
**Issue:** `--sandbox danger-full-access` with prompt-enforced read-only is
not a security boundary. The design documents this honestly as "prompt-enforced,
not sandbox-enforced; this is an acknowledged trust boundary, not a security
boundary." No implementation change needed — the constraint model is the same
as the pre-commit supervisor.
**Classification:** Acknowledged limitation, not blocking.

## Design-Level: Ignore Prefix Tuple Consolidation

**Source:** Expert agent (Phase A review), corrected by structural-proof (Phase B review)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:40-58`
**Issue:** Two near-duplicate constants: `DIRTY_STATE_IGNORE_PREFIXES` (line 40)
and `STATE_IGNORE_PREFIXES` (line 51). They contain the same prefixes but in
different ordering. Should be consolidated into a single
`TRANSIENT_PATH_PREFIXES` constant with a canonical ordering.
**Classification:** Code quality improvement. Can land in the post-merge
implementation wave or as a separate follow-on.
