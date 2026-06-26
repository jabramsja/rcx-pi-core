<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-06-26
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_surreal_numbers_foundation_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest mu/tests/l4_gates/test_surreal_numbers_foundation_gate.py -v
-->

# Surreal Numbers for RCX (SurrealNumbers.v0)

**Status:** REFERENCE - first bounded foundation contract for representing
SurrealNumbers as structural data. This v0 is not a host numeric API. It does
not authorize production Surreals runtime semantics.

**Authority:** `TASKS.md` makes Surreals as structure the next autonomous
structural wave after the 2026-06-26 queue refresh. `STATUS.md` keeps Phase 8c,
the L4 bounded-reduction posture, and the current debt ledgers unchanged.

## Purpose

SurrealNumbers extend the existing StructuralNumbers direction from finite
computational numerals toward structural cuts. The first step is deliberately
small: define the representation boundary, the construction discipline, the
equality and order proof obligations, and tiny examples suitable for later
gates.

This document is a foundation contract, not an implementation plan for a
runtime operator. It records what later waves must prove before any production
Surreals arithmetic, matcher behavior, substrate code, seed registry, projection
set, or optimization path can change.

## Representation Boundary

The v0 representation is a structural cut:

```text
surreal_cut ::= {"_surreal": {"left": option_set, "right": option_set}}
option_set  ::= {"_options": null}
              | {"_options": {"member": surreal_cut, "rest": option_set}}
```

The `left` and `right` fields are finite structural option sets. The linked-set
shape is intentional: it uses ordinary Mu dictionaries and `null`, and does not
require host arrays, host sets, host numeric literals, or host-language
container identity.

The `_surreal` tag names the representation family only. It does not make a
surreal value, order result, equality result, arithmetic result, or canonical
normal form by host authority.

## Construction Rules

A proposed SurrealNumbers datum is a candidate number only when these
obligations are met:

1. The datum has exactly the `_surreal.left` and `_surreal.right` option-set
   fields described above.
2. Every option member is itself a previously constructed surreal cut or a
   reference to one in an explicit structural proof context.
3. The construction is founded: option membership cannot form a cycle.
4. Every left option is proven less than every right option.
5. Duplicate options are eliminated or proven harmless by structural equality
   before a canonical fixture claims set identity.

Rule 4 is a proof obligation, not a host comparison. A later gate may discharge
it with structural proof objects or projection evidence. This v0 only fixes the
shape of the obligation.

## Canonical Boundary

SurrealNumbers have two identities that must not be conflated:

- **Representation identity:** the exact Mu shape and content hash of a cut.
- **Surreal equality:** the mathematical equivalence relation proven from the
  order obligations.

Representation identity is not enough for surreal equality. For example,
`{ | }` and `{ {-1} | {1} }` are extensionally equal as surreal numbers when the
required order proofs exist, but they are not the same structural datum.

The v0 canonical boundary is therefore narrow:

- The empty option set is exactly `{"_options": null}`.
- The first hand-authored fixtures may use only founded finite cuts.
- A fixture may call itself canonical only for the local example set named in
  this document.
- No global canonicalizer, simplifier, quotient, or normal-form selector is
  specified here.

Future canonicalization must prove that option ordering, duplicate spelling,
and equivalent cuts do not change the represented surreal value. Until that
proof exists, serialized shape is a construction witness, not semantic closure.

## Equality And Order Obligations

Later Surreals gates must implement or prove the standard Conway obligations
structurally:

```text
x <= y  iff no left option x_l of x satisfies y <= x_l
       and no right option y_r of y satisfies y_r <= x

x == y  iff x <= y and y <= x
x < y   iff x <= y and not y <= x
```

These clauses are recursive over option sets and must be justified by founded
construction evidence. They are not Python `<=`, JavaScript `<=`, content-hash
equality, JSON serialization order, or a call into host set theory.

The first implementation-grade proof surface should be able to reject an
invalid cut such as `{0 | 0}` because the left option is not strictly less than
the right option.

## Foundation Examples

The initial bounded examples are:

| Name | Cut | Required proof fact |
|------|-----|---------------------|
| `0` | `{ | }` | Empty left and right option sets. |
| `1` | `{0 | }` | `0 < 1`. |
| `-1` | `{ | 0}` | `-1 < 0`. |
| `1/2` | `{0 | 1}` | `0 < 1`, then `0 < 1/2 < 1`. |
| invalid | `{0 | 0}` | Must fail because `0 < 0` is false. |

These examples are intentionally tiny. They bind the first falsifiable
foundation criteria without claiming arithmetic closure, total ordering
execution, global normalization, or runtime integration.

## Explicit Proof Limits

This v0 does not prove or authorize:

- production Surreals runtime semantics;
- Surreals arithmetic such as addition, multiplication, negation, reciprocals,
  or exponentiation;
- global canonicalization or quotienting of equivalent cuts;
- recursive ordinals, W-types / inductive types, coinduction, fixpoint, or
  optimization work;
- changes to runtime, substrate, seed, registry, projection, JavaScript parity,
  pager/autoping, tmux, or StructuralNumbers semantic files;
- host numeric API behavior or host numeric coercion.

The only closure claimed by this wave is a docs-backed foundation boundary:
SurrealNumbers can be described as structural data with falsifiable construction
and proof obligations.

## First Foundation Gate Criteria

The focused foundation gate for this v0 must prove:

1. This document exists in `mu/docs/core/` with a DOC_STATUS header and names
   `mu/tests/l4_gates/test_surreal_numbers_foundation_gate.py` as its grounding
   test.
2. The wave config and tracker note reference this document and the foundation
   gate, making the v0 discoverable without relying on an untracked side channel.
3. The text states the representation boundary as structural data, not a host
   numeric API.
4. The text names the construction rules for left and right option sets.
5. The text distinguishes representation identity from surreal equality.
6. The text records bounded examples including `0`, `1`, `-1`, `1/2`, and the
   invalid `{0 | 0}` negative case.
7. The text explicitly withholds production runtime semantics, arithmetic
   closure, optimization, and later structural waves.

Passing that gate is evidence that the first Surreals step is bounded and
falsifiable. It is not evidence of Surreals semantic closure.

## Relationship To Existing Numeric Work

`StructuralNumbers.v0.md` remains the active structural integer foundation for
matcher-facing numeric facts. SurrealNumbers does not replace it and does not
change its semantics.

`NorthStarSemantics.v0.md` remains the semantic policy lock: host numeric leaves
are not matcher-facing numeric authority, and structural identity must not rely
on Python or JavaScript numeric formatting.

`OntologyPromotionContract.v0.md` remains the promotion discipline: no host code
can mint ontology tokens, and later Surreals tokens require structural
provenance.

`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference: Python and
JavaScript parity is bridge evidence, while L4 bounded reductions must avoid
adding host authority.
