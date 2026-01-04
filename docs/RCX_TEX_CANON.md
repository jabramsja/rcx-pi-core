# RCX TeX Canon Contract (Machine-Ingestible Spec)

This document defines the **binding contract** for `wrapper.tex` (and any included TeX files) as a
**machine-ingestible** RCX specification source.

Human readability is secondary. Canonical structure comes first.

------------------------------------------------------------
## 0) Scope

This contract governs:

- `wrapper.tex`
- Any `\input{...}` / `\include{...}` files that `wrapper.tex` uses
- Any future “RCX spec TeX” intended to be parsed/consumed by RCX

This contract does NOT:

- Define RCX philosophy
- Define runtime behavior of RCX-Ω code
- Guarantee self-hosting today

------------------------------------------------------------
## 1) Canonical Intent

`wrapper.tex` is treated as:

- A stable semantic surface
- A future RCX-readable artifact
- A source of *structural meaning*, not merely typeset output

Therefore:

- Every meaningful construct must have a stable, parseable anchor.
- Formatting-only changes are allowed if anchors remain stable.

------------------------------------------------------------
## 2) Stable Anchors (MUST)

The following are **required canonical anchors**:

### 2.1 Section Anchors
Every top-level section that contains semantic content MUST begin with exactly one of:

- `\section{...}` (preferred)
- `\section*{...}` if it is intentionally unnumbered

Each such section MUST contain one stable machine anchor line near its start, using one of:

- `\label{sec:<slug>}` (preferred)
- or a dedicated macro line: `% RCX-ANCHOR: sec:<slug>`

Slugs MUST be lowercase and use `a-z0-9-` only.

### 2.2 Rule Anchors
Every rule that must be referencable MUST be presented with a stable anchor.

Allowed forms:

- `\paragraph*{Rule <id>: <name>}\label{rule:<id>}`
- or `% RCX-RULE: <id> <name>` directly above the rule block

Rule IDs MUST be stable and unique within the document.

### 2.3 Definition Anchors
Definitions intended for machine use MUST be anchored:

- `\subsection{...}\label{def:<slug>}`
- or `% RCX-DEF: <slug>`

------------------------------------------------------------
## 3) Prohibited Drift (MUST NOT)

The following are prohibited without explicit version bump + contract update:

- Renaming or removing existing `sec:` / `rule:` / `def:` anchors
- Reusing an anchor for a different meaning
- Changing a rule’s ID
- Changing the meaning of an anchored construct without noting it

If meaning changes: update the surrounding text AND add a short “Change Note” comment.

------------------------------------------------------------
## 4) Allowed Change Classes

### 4.1 Safe changes (no bump)
- Spacing / line wrapping
- Typography / packages that do not alter anchors
- Rewording that does not change semantics

### 4.2 Semantic changes (requires bump)
- Adding/removing rules
- Changing rule preconditions/effects
- Modifying any anchored definition meaningfully
- Altering any canonical macro that RCX will parse

------------------------------------------------------------
## 5) Canonical Macros

Macros fall into two classes:

### 5.1 Semantic macros (CANON)
These encode meaning that RCX may later parse. Examples:
- rule tags, operator names, engine parameters, closure operators

CANON macros MUST:
- Be declared in one obvious block (near top of wrapper)
- Have stable names
- Avoid clever expansion tricks

### 5.2 Presentation macros (NON-CANON)
These exist only to style the PDF.
They may change freely so long as anchors and CANON macros remain stable.

------------------------------------------------------------
## 6) Versioning

This contract has a version:

- `RCX_TEX_CANON_VERSION = 0.1.0`

Bump rules:
- Patch: wording/clarification only
- Minor: new allowed anchor forms, new required anchors
- Major: breaking changes to anchor requirements

Current version:
- 0.1.0

------------------------------------------------------------
## 7) Minimal Lint Checklist (manual for now)

Before committing any wrapper/TeX spec change:

- [ ] No existing `sec:` anchors changed or removed
- [ ] No existing `rule:` IDs changed
- [ ] New semantic items have anchors
- [ ] If semantics changed, note it near the change
- [ ] `python3 -m pytest -q` remains green (repo truth gate)

------------------------------------------------------------
## 8) Relationship to Governance Rails

This document is governed by:
- `docs/RCX_OMEGA_GOVERNANCE.md`

If there is any ambiguity:
- Governance overrides enthusiasm
- Tests override documentation
- Repo state overrides conversation state

