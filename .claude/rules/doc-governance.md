---
description: "Documentation governance: three laws, lifecycle, verification"
globs: ["mu/docs/**", "STATUS.md", "TASKS.md", "CHANGELOG.md", "reports/**"]
---

**Full policy:** `mu/docs/core/DocGovernance.v0.md`

**Three Laws:**
1. Two files own current state (STATUS.md, TASKS.md only)
2. Every doc has a lifecycle (DOC_STATUS header)
3. Design docs describe WHAT, not progress

**When modifying code:** Update DOC_CONTRACTS if you change function names. Add DOC_STATUS header to new docs. Don't use line numbers in docs. Don't hardcode counts.

**Verify:** `pytest tests/docs/test_doc_contracts.py -v` and `python3 -m tools.docs.add_doc_headers --check`

**Governance & Invariants:** See `TASKS.md` for North Star invariants (15 items), governance rules, and promotion criteria. TASKS.md is the authority.
