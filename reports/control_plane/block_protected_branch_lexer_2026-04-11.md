# Block-Protected-Branch Lexer Rewrite

Date: 2026-04-11
Status: Phase B (locked, implementing)
2026-04-11 on grounding, lexer contract, fail-closed behavior).
Not yet agent-reviewed or bridge-converged after this rewrite.
Phase-A-Lock: LOCKED
Parent task: `[ANTI-DRIFT-ENFORCEMENT]` (TASKS.md:152-155)
Sub-wave ID: block-protected-branch-lexer-2026-04-11

## 1. Scope

Replace the sed-regex comment-and-quote stripping logic in
`.claude/hooks/block-protected-branch.sh` with a bash-aware
state-machine tokenizer that correctly handles:

- **POSIX word-boundary comments** — `#` is a comment start only when
  the cursor is at the beginning of a new word (start-of-input, after
  whitespace/newline, or after an unquoted shell operator `;`, `&`,
  `|`, `(`, `)`). `#` embedded in a word (e.g. `foo#bar`) is literal.
  `#` immediately following a closed quote (e.g. `'abc'#xyz`) is
  literal, because closing a quote does NOT create a word boundary.
- **Single-quoted strings** (`'...'`) — content is literal; `#`,
  whitespace, and `\` inside single quotes are literal; word
  boundaries and comment detection are suppressed.
- **Double-quoted strings** (`"..."`) — content is literal for
  token-boundary purposes; `\` honors a limited escape set (`\"`,
  `\\`, `\$`, `` \` ``, `\<newline>`), other `\x` sequences keep the
  `\` literal.
- **Unquoted backslash escapes** — `\<newline>` is a line
  continuation (skip both); `\x` for any other x is a literal `x`.
- **Explicit fail-closed behavior on malformed input** — unclosed
  quote or trailing backslash at end-of-input → helper exits
  non-zero → hook emits a BLOCK decision with an attributable reason.

This fixes the PR #754 post-merge P1 bot finding submitted
2026-04-11T18:18:31Z and closes the recursive sed-regex fix cycle:

- v1 (pre-PR #746): `#[^;|&]*(;|&&|\|\||$)` — handled `foo#bar` but
  bypassed on multiline leading comment (PR #746 P1).
- v2 (PR #754 first attempt): `s/#.*$//g` — handled multiline but
  bypassed on `echo foo#bar; git commit -m x` (PR #754 first P1).
- v3 (PR #754 second attempt, current dev commit `24e630c` at
  `.claude/hooks/block-protected-branch.sh:54`):
  `s/(^|[[:space:]])#.*$/\1/g` — handled both above, but bypasses on
  `echo ' #foo'; git commit -m x` because a whitespace-preceded `#`
  inside a quoted string is indistinguishable from an unquoted
  comment under a regex that does not track quote state (PR #754
  post-merge P1).

Founder directive (session 2026-04-11): stop the recursive sed-regex
fix cycle; switch to a structural tokenizer.

### Files in scope

- `.claude/hooks/block-protected-branch.sh` — rewrite lines 54, 57,
  and 61 (current commit `24e630c`) to delegate tokenization to the
  Python helper below and read tokens into the existing
  git-subcommand detection loop at line 68. Add fail-closed handling
  when the helper exits non-zero (before the existing
  `CLAUDE_PROJECT_DIR` fail-closed check at lines 101-104).
- `.claude/hooks/_block_protected_branch_tokenize.py` (NEW) — small
  Python helper implementing the state-machine contract in Work
  Item 1. Reads stdin, emits tokens one-per-line to stdout, exits 0
  on success and exits 2 on any parser error.
- `.claude/hooks/test_block_protected_branch.sh` (NEW) — smoke test
  suite covering the 8 known scenarios plus the new malformed-input
  fail-closed scenario.

### Directories in scope

- `.claude/hooks/` — hook file + Python helper + smoke test

## 2. Work items

1. **Implement Python tokenizer helper** with the following lexer
   contract (authoritative — this is what the helper MUST implement,
   regardless of which standard-library building blocks it uses):

   **States:** `UNQUOTED`, `SINGLE_QUOTED`, `DOUBLE_QUOTED`,
   `ESCAPE_UNQUOTED`, `ESCAPE_DOUBLE`, `COMMENT`. Track a boolean
   `at_word_boundary` that is true at start-of-input and after each
   emitted word boundary, false after any char that is appended to
   the current token (including on entering/exiting quotes).

   **Transitions:**
   - `UNQUOTED` + whitespace/newline → emit current token if any;
     set `at_word_boundary = true`; stay `UNQUOTED`.
   - `UNQUOTED` + `;` / `&` / `|` / `(` / `)` → same as
     whitespace (word boundary; stay `UNQUOTED`).
   - `UNQUOTED` + `'` → `SINGLE_QUOTED`; `at_word_boundary = false`.
   - `UNQUOTED` + `"` → `DOUBLE_QUOTED`; `at_word_boundary = false`.
   - `UNQUOTED` + `\` → `ESCAPE_UNQUOTED`; `at_word_boundary = false`.
   - `UNQUOTED` + `#` when `at_word_boundary == true` → `COMMENT`
     (do not append `#`; discard until newline).
   - `UNQUOTED` + `#` when `at_word_boundary == false` → append `#`
     to current token; stay `UNQUOTED`.
   - `UNQUOTED` + any other char → append to current token;
     `at_word_boundary = false`; stay `UNQUOTED`.
   - `SINGLE_QUOTED` + `'` → `UNQUOTED` (quotes are invisible in the
     emitted token; do NOT set `at_word_boundary = true`).
   - `SINGLE_QUOTED` + any other char (including `\`, `#`, `\n`,
     whitespace) → append literally; stay `SINGLE_QUOTED`.
   - `DOUBLE_QUOTED` + `"` → `UNQUOTED` (quotes invisible; do NOT set
     `at_word_boundary = true`).
   - `DOUBLE_QUOTED` + `\` → `ESCAPE_DOUBLE`.
   - `DOUBLE_QUOTED` + any other char → append literally; stay
     `DOUBLE_QUOTED`.
   - `ESCAPE_UNQUOTED` + newline → line continuation (skip both);
     return to `UNQUOTED` (do NOT set `at_word_boundary = true`).
   - `ESCAPE_UNQUOTED` + any other char → append that char literally
     (drop the `\`); return to `UNQUOTED`.
   - `ESCAPE_DOUBLE` + one of `"`, `\`, `$`, `` ` ``, newline →
     append that char literally (drop the `\`); return to
     `DOUBLE_QUOTED`.
   - `ESCAPE_DOUBLE` + any other char → append BOTH `\` and that
     char literally; return to `DOUBLE_QUOTED`.
   - `COMMENT` + newline → emit any pending token (there should be
     none, since `at_word_boundary` was true on entry); set
     `at_word_boundary = true`; return to `UNQUOTED`.
   - `COMMENT` + any other char → discard; stay `COMMENT`.
   - End-of-input in `UNQUOTED` or `COMMENT` → emit any pending
     token; normal termination (exit 0).

   **Fail-closed parser-error contract:**
   - End-of-input in `SINGLE_QUOTED` → raise
     `ValueError("unclosed single quote")`.
   - End-of-input in `DOUBLE_QUOTED` → raise
     `ValueError("unclosed double quote")`.
   - End-of-input in `ESCAPE_UNQUOTED` or `ESCAPE_DOUBLE` → raise
     `ValueError("trailing backslash at end of input")`.

   The helper's top-level must catch `ValueError` (and any
   unexpected `Exception`), print one diagnostic line to `stderr`
   with the error text, and exit with status code `2`. On error it
   must NOT emit any tokens to `stdout` — the hook reads stdout as
   the token stream, and a partial stream must never be treated as
   a successful tokenization. Success path exits with status `0`.

   **Rejected implementation — plain `shlex.shlex(posix=True)`.**
   Direct probe evidence (reviewer, 2026-04-11) on scenarios B, G, H
   showed:
   - B `echo hello # git commit` → `['echo', 'hello']` (OK)
   - G `echo foo#bar; git commit -m x` → `['echo', 'foo']` (REGRESS
     — truncates at `#` inside the word `foo#bar`, dropping
     `git commit` and reintroducing the v2 bypass class).
   - H `echo ' #foo'; git commit -m x` →
     `['echo', ' #foo;', 'git', 'commit', '-m', 'x']` (surprising
     token boundary — `;` attaches to the quoted token — but the
     `git`/`commit` subcommand IS present, so the hook would block.
     This confirms shlex does respect single quotes, but scenario G
     still regresses, so plain shlex is not acceptable).
   - Malformed probe `echo 'unclosed` → `ValueError: No closing
     quotation` raised (unhandled in a plain shlex design).

   A `shlex.shlex` instance configured with `commenters = ''` would
   disable shlex's non-POSIX comment handling and could be used as an
   implementation detail IF comment stripping is handled by the
   state machine above in a preceding pass. But the minimal
   state-machine tokenizer specified in this Work Item is the
   authoritative contract — Phase B must implement it directly, with
   or without shlex as an internal helper, and must match the
   contract exactly rather than delegating to plain shlex.

2. **Replace the sed pipeline** in
   `.claude/hooks/block-protected-branch.sh` (current commit
   `24e630c`):
   - Remove lines 54 (`CMD_NOCOMMENTS=$(echo "$CMD" | sed -E
     's/(^|[[:space:]])#.*$/\1/g')`), 57 (`CMD_ONELINE=$(echo
     "$CMD_NOCOMMENTS" | tr '\n' ' ')`), and 61 (`CMD_STRIPPED=$(echo
     "$CMD_ONELINE" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g")`).
   - Insert an invocation pattern that fails closed on helper error.
     Recommended form (Phase B may refine path resolution):

     ```bash
     HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
     if ! CMD_TOKENS=$(printf '%s' "$CMD" \
           | python3 "$HOOK_DIR/_block_protected_branch_tokenize.py" \
           2>/dev/null); then
       jq -n '{"decision": "block", "reason": "block-protected-branch: tokenizer parser error - blocking for safety"}'
       exit 0
     fi
     ```

     The hook MUST emit a BLOCK decision (not an allow, not a silent
     exit 0 with no decision) on helper non-zero exit, so malformed
     input cannot turn into an allow path.
   - Rewrite the downstream loop at line 68 from
     `for word in $CMD_STRIPPED; do ... done` to
     `while IFS= read -r word; do ... done <<< "$CMD_TOKENS"`, since
     token boundaries are now newlines.
   - For Patterns 1 (cd-into-worktree, line 113) and Pattern 2
     (`git -C <path>`, line 126): retain a comment-unaware,
     raw-one-line view of the command for these regexes. These are
     best-effort worktree-path detectors, not the safety gate; the
     safety gate is the `BLOCKED` check which now uses the
     tokenizer. Recommended form:

     ```bash
     CMD_ONELINE=$(printf '%s' "$CMD" | tr '\n' ' ')
     ```

     An over-detection in Patterns 1/2 only causes the branch check
     to run in the "wrong" worktree, whose branch will typically be
     protected (`dev`/`main`), triggering BLOCK — fail-closed.

3. **Preserve downstream logic unchanged** (lines refer to commit
   `24e630c`):
   - Git subcommand extraction (`NEXT_IS_GIT_SUB` state machine,
     lines 66-94)
   - Flag handling (`-C`, `-c`, `--git-dir`, `--work-tree`,
     `--namespace`, `--super-prefix`, lines 80-85)
   - Branch detection via `git rev-parse --abbrev-ref HEAD` (line
     145)
   - cd-into-worktree support (Pattern 1, lines 113-123)
   - `git -C <path>` support (Pattern 2, lines 126-133)
   - Fail-closed on empty `CLAUDE_PROJECT_DIR` (lines 101-104) —
     remains unchanged; the new helper-error fail-closed is an
     ADDITIONAL gate inserted before it.
   - Protected-branch decision emission (lines 147-152)

4. **Add smoke test suite** at
   `.claude/hooks/test_block_protected_branch.sh` covering:

   **Pre-existing scenarios** (verified by this wave, not introduced
   by it):
   - **A**: `# comment\ngit commit -m x` → EXPECT BLOCK
   - **B**: `echo hello # git commit` → EXPECT NO BLOCK
   - **C**: `echo "git commit"` → EXPECT NO BLOCK
   - **D**: `git commit -m test` → EXPECT BLOCK
   - **F**: `git checkout -b pre-commit-fix` → EXPECT NO BLOCK
   - **G**: `echo foo#bar; git commit -m x` → EXPECT BLOCK
     (regression case for the v2 bypass; rejects the plain-shlex
     design from Work Item 1)
   - **H**: `echo ' #foo'; git commit -m x` → EXPECT BLOCK
     (regression case for the v3 bypass; the PR #754 post-merge
     bot finding)

   **New scenarios added by this wave:**
   - **I**: `cat <<EOF\n# git commit\nEOF` → EXPECT NO BLOCK.
     The tokenizer's view of this input is: `cat`, `<<`, `EOF`, then
     at newline-start in UNQUOTED it sees `#` at word-boundary and
     strips to end-of-line, leaving `EOF`. Final tokens:
     `cat`, `<<`, `EOF`, `EOF`. No `git` subcommand follows a `git`
     token, so NO BLOCK. This is correct behavior — a heredoc body
     containing the literal text `# git commit` is not a real
     command.
   - **J** (NEW — parser-error fail-closed): `echo 'unclosed` →
     EXPECT BLOCK with reason containing `tokenizer parser error`.
     The helper raises `ValueError("unclosed single quote")` and
     exits 2; the hook must emit a `decision=block` response and
     NOT silently allow the command.

5. **Verify pre-push-fast passes** end-to-end with the new hook
   logic, including exercising the protected-branch detection path
   on a feature-branch worktree (the normal happy-path during this
   wave's own commit) and verifying the hook does NOT over-block on
   routine commands (`git status`, `git log`, `git diff`, `git
   fetch`).

## 3. Constraints (what is NOT in scope)

- **No changes to `TASKS.md`.** This wave inherits authorization
  from `[ANTI-DRIFT-ENFORCEMENT]` at TASKS.md:152-155 — the parent
  task explicitly names "block-protected-branch false-positive fix"
  in its scope (TASKS.md:153). Adding a new `[BLOCK-PROTECTED-BRANCH-LEXER]`
  task id to the `## NEXT` section would be self-authorizing; the
  Phase A bridge reviewer flagged the previous packet revision for
  exactly this anti-pattern on 2026-04-11.
- No changes to `mu/` runtime or Python source beyond the new hook
  helper.
- No changes to `recovery_gate.py`, `commit_executor.py`, or other
  pipeline executors.
- No changes to other `.claude/hooks/` files (this wave is narrowly
  scoped to `block-protected-branch.sh` + its tokenizer + its smoke
  test).
- Hook must remain a bash script wrapper (it is invoked as a bash
  hook by Claude Code); the Python helper is an INTERNAL delegation,
  not a full rewrite of the hook in Python.
- Python invocation overhead must be `<200ms` so it does not
  noticeably slow interactive Bash tool use (measured via `time` on
  a typical command).

## 4. Stop conditions

Stop when ALL of the following are true:

1. `.claude/hooks/_block_protected_branch_tokenize.py` exists and
   implements the state-machine lexer contract from Work Item 1,
   including the fail-closed parser-error contract (exits 2 on any
   parser error, prints one diagnostic line to stderr, emits no
   tokens to stdout on error).
2. `.claude/hooks/block-protected-branch.sh` invokes the helper,
   reads tokens into the git-subcommand detection loop via a
   newline-delimited `while IFS= read -r word; do ... done` form,
   and emits a BLOCK decision (not an allow) when the helper exits
   non-zero.
3. All 9 smoke scenarios (A, B, C, D, F, G, H, I, J) pass when run
   against the new hook via
   `.claude/hooks/test_block_protected_branch.sh`. Scenario J in
   particular must yield a BLOCK decision whose reason contains
   `tokenizer parser error`.
4. `./tools/pre-push-fast` passes end-to-end on this wave's own
   commit.
5. `./tools/checks/check_docs_consistency.sh` passes.
6. `python3 tools/checks/enforce_l4_execution_contract.py --staged`
   passes, inheriting
   `FOUNDER_OVERRIDE:anti-drift-enforcement-2026-04-07` from the
   parent task at TASKS.md:155 for the non-structural adjacency cap.
7. `TASKS.md` has NOT been modified by this wave (verify with
   `git diff TASKS.md` returning empty).

## 5. Acceptance criteria

1. **Smoke suite green:** `bash .claude/hooks/test_block_protected_branch.sh`
   → all 9 scenarios (A, B, C, D, F, G, H, I, J) pass.
2. **Pre-push green:** `bash tools/pre-push-fast` →
   `Pre-push check passed`.
3. **Overhead bound:** `time printf '%s' "git status" | python3
   .claude/hooks/_block_protected_branch_tokenize.py` completes in
   `<200ms` on the developer's Mac; `stdout` contains exactly two
   lines: `git` and `status`; exit status is 0.
4. **Regression H (v3 bypass closed):** the new hook MUST BLOCK
   `echo ' #foo'; git commit -m x`, reproducing the bot's PR #754
   reproduction as a passing safety gate.
5. **Regression G (v2 bypass stays closed, plain-shlex rejection
   verified):** the new hook MUST BLOCK `echo foo#bar; git commit
   -m x`. The `foo#bar` token must be preserved as a single token
   with the `#` literal — this is the exact case the reviewer's
   probe showed plain `shlex.shlex(posix=True)` regressing to
   `['echo', 'foo']`.
6. **Fail-closed J (parser error → BLOCK):** the new hook MUST
   BLOCK `echo 'unclosed`. The emitted decision must have
   `decision == "block"` and `reason` containing the substring
   `tokenizer parser error`, so the failure is attributable to the
   helper, not to the branch detection path. The helper's stderr
   must contain `unclosed single quote`. The helper's stdout must
   be empty (no partial token stream).
7. **Downstream-loop invariance:** for scenarios D, F, `git
   status`, and `git -C /some/path status`, the BLOCK decision
   before/after this wave is identical (D → BLOCK, F → NO BLOCK,
   `git status` → NO BLOCK, `git -C /some/path status` → NO BLOCK),
   confirming the git-subcommand-detection and flag-handling logic
   is untouched.

## 6. Grounding / Authorization

### Parent TASKS.md authorization

This wave is a sub-scope of **`[ANTI-DRIFT-ENFORCEMENT]`** at
**TASKS.md:152-155**, which is marked `**NEXT**` and
founder-authorized 2026-04-07. The parent task's scope explicitly
lists (TASKS.md:153):

> "hook hardening (cron evidence gate, test-result claim gate,
> PostCompact comprehensive reinject, **block-protected-branch
> false-positive fix**), ..."

The current wave is a direct continuation of the parent's
"block-protected-branch false-positive fix" sub-scope — it fixes a
new false-positive class (v3 quoted-whitespace-hash bypass) in the
same hook file that the parent task authorizes hardening on.

**Inherited authorization tokens:**
- `FOUNDER_OVERRIDE:anti-drift-enforcement-2026-04-07` (TASKS.md:155)
  — covers the consecutive non-structural-adjacency cap. Founder
  rationale in parent: "prerequisite for all future structural work,
  cannot defer."
- Lane: `control-surface (enforcement hardening)` (TASKS.md:154).
- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`
  (TASKS.md:155) — same structural unblocker chain.

### This packet is the governing sub-wave artifact

This file,
`reports/control_plane/block_protected_branch_lexer_2026-04-11.md`,
is the governing packet for this sub-wave. It does NOT register a
new task id in `TASKS.md`. The previous revision of this packet
proposed inserting `[BLOCK-PROTECTED-BRANCH-LEXER]` as a new NEXT
item — the Phase A bridge reviewer flagged this on 2026-04-11 as
self-authorizing (a wave cannot grant itself authorization by adding
itself to the canonical task list during its own execution). This
rewrite removes that anti-pattern and grounds the wave entirely in
the parent task above.

### Founder directive driver (2026-04-11 session)

> "Option B..let's just get it done. set the task as first next,
> make a packet..send to pipeline"

This directive authorized a structural resolution of the recursive
sed-regex fix cycle (v1 → v2 → v3, three consecutive P1 regressions
on PR #754) within the parent `[ANTI-DRIFT-ENFORCEMENT]` scope. The
"set as first next" language was the session-level prioritization of
the work inside the parent task, not a directive to mint a new top-
level task id — Phase A correctly interprets this as "do this work
next under the parent task's authorization", consistent with the
reviewer finding.

### Bot finding driver (PR #754 post-merge P1)

- **Submitter:** chatgpt-codex-connector
- **Timestamp:** 2026-04-11T18:18:31Z
- **Title:** "Preserve quoted `#` when stripping comments"
- **Inline location:** `.claude/hooks/block-protected-branch.sh:54`
  on dev commit `24e630c` (the line that applies the v3 sed regex
  `s/(^|[[:space:]])#.*$/\1/g`).
- **Reproduction from bot:** `echo ' #foo'; git commit -m x` was
  allowed by the hook on a temporary `main`-branch repo, while the
  pre-PR-754 version blocked it. Classification: safety regression
  in the protected-branch gate.

### Reviewer finding driver (Phase A rewrite, 2026-04-11)

The bridge reviewer returned REQUEST_CHANGES on the previous
revision of this packet with three blocking findings:

1. **Grounding did not anchor the wave to canonical TASKS
   authorization.** Resolved by the parent-task anchoring above:
   `[ANTI-DRIFT-ENFORCEMENT]` at TASKS.md:152-155, which already
   explicitly names "block-protected-branch false-positive fix" in
   its scope. No new task id is added by this wave.
2. **Plain `shlex.shlex(posix=True)` does not meet the packet's own
   lexer contract.** Resolved by replacing "plain shlex" with the
   explicit state-machine lexer contract in Work Item 1, and by
   documenting the reviewer's probe results (scenario G →
   `['echo', 'foo']`) as the concrete rejection rationale for plain
   shlex.
3. **Safety-hook design omitted a fail-closed parser-error
   contract.** Resolved by adding a fail-closed parser-error contract
   at both the helper level (exit 2, no stdout tokens, stderr
   diagnostic) and the hook level (BLOCK decision with attributable
   reason), and by adding smoke scenario J
   (`echo 'unclosed` → EXPECT BLOCK) to the acceptance suite.

### Historical regressions this wave closes

- **PR #746 P1** (multiline comment bypass): fixed by v2 (per-line
  strip-first), regressed v3 — v3 fixes it correctly (word-boundary
  anchor) but introduces scenario H. The new tokenizer handles
  multiline comments via the `COMMENT` state + newline transition.
- **PR #754 first P1** (`foo#bar` literal `#`): fixed by v3
  (word-boundary anchor), but v2 re-regressed it. The new
  tokenizer handles this via `at_word_boundary == false` when
  reading `#` mid-word.
- **PR #754 second P1** (`' #...'` whitespace+hash inside a quoted
  string): UNADDRESSED by v3. The new tokenizer handles this via
  the `SINGLE_QUOTED` state — whitespace and `#` inside single
  quotes are literal and cannot trigger comment detection.

### Design rationale (structural vs regex)

sed-regex has fundamental limitations for bash parsing: regular
languages cannot balance quotes, cannot distinguish quoted vs
unquoted content, and cannot enforce POSIX word-boundary comment
rules across line-oriented vs flattened processing passes. A
state-machine tokenizer with a fail-closed parser-error contract
handles all of these at the lexical level, eliminating the entire
class of edge cases in one structural change — which is the
parent task's "cannot defer" mandate applied at the code level.

### Wave class

`L4_ENABLER` (not `MAINTENANCE`). The wave has real evidence:
- bot-finding fix for PR #754 post-merge P1,
- 9-scenario smoke suite including the new parser-error scenario J,
- pre-push-fast end-to-end verification,
- direct probe of plain shlex producing `['echo','foo']` on G
  (documented rejection of the alternative design).

Inherits
`FOUNDER_OVERRIDE:anti-drift-enforcement-2026-04-07` from the parent
task for the non-structural adjacency cap.

### Lane

`control-surface (safety hook hardening)` — inherited from parent
task `[ANTI-DRIFT-ENFORCEMENT]` (TASKS.md:154).

### Wave chain context

6th consecutive non-structural wave since the last STRUCTURAL wave,
following #751 (learning store), #752 (run-review turn budget +
compliance), #753 (bot findings + hook deny-list), #754 (pipeline
followups with the v3 bug). FOUNDER_OVERRIDE required and inherited
from the parent task per the above.
