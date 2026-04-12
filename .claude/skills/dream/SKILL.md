---
name: dream
description: Memory consolidation — prune stale entries, resolve contradictions, deduplicate, rebuild index
---

# /dream — Memory Consolidation

Perform a reflective pass over memory files. Synthesize recent signal into durable, well-organized memories so future sessions orient quickly.

## When to Auto-Invoke

- When `autoDreamEnabled` is true and 24+ hours have passed since last consolidation
- When the user runs `/dream` manually
- At session end if significant new memories were created during the session

## Phase 1 — Orient

1. List all files in the memory directory:
   ```
   ls ~/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory/
   ```

2. Read `MEMORY.md` (the index file) in full.

3. Skim each memory file referenced in the index. For each file, note:
   - Last modified date (from frontmatter or file stat)
   - Whether the description still matches the content
   - Whether the content references files, functions, or state that may have changed

## Phase 2 — Gather Recent Signal

Search for new information worth persisting, in priority order:

1. **Stale fact detection** — For each memory that names a specific file path, function, or flag:
   - Verify the file still exists (use Glob)
   - Verify the function/flag still exists (use Grep)
   - If not found, mark the memory for update or removal

2. **Contradiction detection** — Compare memory claims against:
   - Current `STATUS.md` and `TASKS.md`
   - Current `CLAUDE.md` rules
   - Git log for recent changes that may invalidate memories

3. **Relative date decay** — Find any memories with relative dates ("yesterday", "last week", "recently") and convert to absolute dates or remove if the date is no longer meaningful.

4. **Duplicate detection** — Identify memories with overlapping content that should be merged.

Do NOT exhaustively read session transcripts. Look only for things you already suspect matter based on the orient phase.

## Phase 3 — Consolidate

For each issue found in Phase 2:

- **Stale facts**: Update the memory with current truth, or delete if the entire memory is obsolete.
- **Contradictions**: Trust current code/repo state over memory. Update the memory.
- **Relative dates**: Convert to absolute dates (e.g., "yesterday" -> "2026-03-27") or remove if no longer relevant.
- **Duplicates**: Merge into the stronger/more complete memory file. Delete the weaker one.
- **New signal**: If the orient phase revealed important patterns not yet captured, create new memory files following the standard frontmatter format.

Rules:
- **PROTECTED FILES**: Memory files with `protected: true` in frontmatter or `DREAM-PROTECTED` comments MUST NOT be merged, deleted, or marked stale. They reference external artifacts (binary patches, external tools) that grep cannot find in repo code. Skip them entirely during stale fact detection.
- Merge new signal into existing topic files rather than creating near-duplicates
- Prefer updating over deleting — only delete if the entire memory is wrong or obsolete
- Preserve the founder's voice and intent in feedback memories
- Do not create memories for things derivable from code, git history, or CLAUDE.md

## Phase 4 — Prune and Rebuild Index

1. Ensure `MEMORY.md` stays under 200 lines and ~25KB.
2. Each entry: one line, under ~150 characters: `- [Title](file.md) -- one-line hook`
3. Remove pointers to deleted memory files.
4. Add pointers to newly created memory files.
5. Reorder entries by importance/frequency of use (protocols and feedback first, references last).
6. Verify every file referenced in `MEMORY.md` actually exists.
7. **Update the `.last_dream` sentinel — CANONICAL FORMAT REQUIRED.**
   Run this exact command (no alternatives):
   ```bash
   date +%Y-%m-%d > ~/.claude/projects/-Users-jeffabrams-Desktop-RCX-X-RCXStack-RCXStackminimal-WorkingRCX/memory/.last_dream
   ```
   **DO NOT** freelance another format (no ISO 8601, no epoch seconds, no `date -u`, no timestamps with `T`/`Z`). The `should-dream.sh` Stop hook only parses `YYYY-MM-DD`, all-digit epoch, and ISO 8601 — any other format blocks session end with "overdue by 493,292h". Canonical format is `YYYY-MM-DD`. Parallel worktree sessions that write to the same memory directory must use the same format. See `.claude/rules/learning.md` 2026-04-10 entries for the prior regressions this rule prevents.

## Output Format

```
DREAM COMPLETE
Memories scanned: <N>
Stale facts fixed: <N>
Contradictions resolved: <N>
Duplicates merged: <N>
New memories created: <N>
Memories deleted: <N>
Index entries: <N> (limit: 200)
```

Then list each change made, one line per change:
```
- Updated <file.md>: <what changed>
- Merged <file_a.md> into <file_b.md>
- Deleted <file.md>: <reason>
- Created <file.md>: <topic>
```
