# Archived Partial: redteam_2026-03-14_repo_non_blockers.md

Date archived: 2026-05-07
Archive reason: resolved Claude-referencing section extracted from the active
deferred lane by `deferred-non-mu-deferred-lane-truth-sweep-2026-05-07`.
No Claude-related files were edited.
Source packet: `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`

## N3 `DOC_ACCURACY` - the canonical doctrine map is still split across startup surfaces - RESOLVED 2026-03-15

2026-05-06 cleanup note: retained because this resolved section references
Claude surfaces; it was not re-adjudicated or extracted by that cleanup.

Fixed: added `Why_RCX_PI_VM_EXISTS.md` and `StructuralPurity.v0.md` to MANIFEST.md
canonical reading order (items 14-15). ROADMAP.md updated to reference 15-doc order.

Evidence:

- founder bootstrap requires:
  - `FOUNDER_SESSION_BOOTSTRAP.md:115`
- Claude startup depends on:
  - `CLAUDE.md:19`
  - `CLAUDE.md:37-38`
  - `CLAUDE.md:61`
- `mu/docs/README.md` presents those doctrine docs as core references:
  - `mu/docs/README.md:66`
  - `mu/docs/README.md:68`
- `roadmap/MANIFEST.md` still claims canonical reading order without including
  `StructuralPurity.v0.md` or `Why_RCX_PI_VM_EXISTS.md` in the ordered list:
  - `roadmap/MANIFEST.md:6-13`

Direct repro:

```bash
wc -l ROADMAP.md roadmap/MANIFEST.md
rg -n "StructuralPurity\\.v0\\.md|Why_RCX_PI_VM_EXISTS\\.md" \
  FOUNDER_SESSION_BOOTSTRAP.md CLAUDE.md mu/docs/README.md roadmap/MANIFEST.md
```

Observed:

- `ROADMAP.md` remains a shorter duplicate/pointer layer beside `roadmap/MANIFEST.md`
- doctrine-doc references appear in bootstrap/Claude/`mu/docs/README.md` but not
  in the manifest's ordered list

Why this remains advisory:

- This is sync burden and onboarding ambiguity, not a reproduced runtime break.
