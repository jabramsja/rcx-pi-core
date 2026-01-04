# RCX Session Boot (paste into a new chat)

**Repo:** `jabramsja/rcx-pi-core` (branch: `dev`)

## Hard rules (do not violate)
- **Closed-world:** do not assert RCX theory/implementation details unless supported by repo files I point to or paste.
- **No “done” claims without evidence:** show command output or CI run link.
- **Deliver changes as ONE copy-paste terminal block** (heredoc/full replacements), unless I ask otherwise.

## First actions (ground truth)
1) Generate a repo manifest:
   - `scripts/rcx_manifest.sh`
   - This produces `.rcx_manifest.json` with file hashes and a `manifest_sha256`.

2) Ask me for the goal of the session in ONE sentence.
3) Then propose the smallest verifiable next step with a pass/fail check.

## Canon lanes (when present)
- THEORY: `.rcx_library/CANON`
- IMPLEMENTATION: `.rcx_library/CANON_EXEC`
