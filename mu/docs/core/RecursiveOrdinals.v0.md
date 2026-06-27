<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-06-26
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_recursive_ordinals_foundation_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest mu/tests/l4_gates/test_recursive_ordinals_foundation_gate.py -v
-->

# Recursive Ordinals for RCX (RecursiveOrdinals.v0)

**Status:** REFERENCE - first bounded foundation contract for representing
recursive ordinals as structural data. This v0 is not a host ordinal API, not a
host set-theory API, and not a host numeric execution API. It does not
authorize production recursive ordinal runtime semantics.

**Authority:** `TASKS.md` makes recursive ordinals as structure the next
autonomous structural wave after the 2026-06-26 queue refresh. `STATUS.md`
keeps Phase 8c, the L4 bounded-reduction posture, and the current debt ledgers
unchanged.

## Purpose

RecursiveOrdinals records the first finite ordinal representation boundary that
can later bridge the recursive-containment foundation to `StructuralNumbers.v0`.
The first step is deliberately small: define zero, successor, finite recursive
containment, membership/order obligations, bridge obligations, and proof limits
without changing runtime, substrate, seeds, registries, projections, parity, or
optimization behavior.

This document is a foundation contract, not an implementation plan for a host
ordinal library. It states what later waves must prove before recursive
ordinal values can become production runtime facts.

## Representation Boundary

The v0 representation is a finite structural membership object:

```text
ordinal     ::= {"_ord": {"members": member_list}}
member_list ::= {"_ord_members": null}
              | {"_ord_members": {"member": ordinal, "rest": member_list}}
```

The `members` field is a finite linked membership list. The linked shape is
intentional: it uses ordinary Mu dictionaries and `null`, and does not require
host arrays, host sets, host numeric literals, host object identity, or
host-language container semantics.

The `_ord` tag names the representation family only. It does not make an
ordinal value, membership result, order result, arithmetic result, bridge
projection, or canonical normal form by host authority.

## Construction Rules

A proposed RecursiveOrdinals datum is a candidate finite ordinal only when
these obligations are met:

1. Zero is the unique empty-member candidate:
   `{"_ord": {"members": {"_ord_members": null}}}`.
2. `successor(alpha)` is represented by finite recursive containment: its
   member list contains `alpha` and every member already contained by `alpha`.
3. Every member is itself a previously constructed recursive ordinal or a
   reference to one in an explicit structural proof context.
4. Construction is founded: member containment cannot form a cycle.
5. The v0 finite examples use an explicit member-list order as construction
   evidence, but host list order is not semantic set authority.
6. Duplicate members, alternative member-list spellings, and quotienting of
   extensionally equal membership structures are deferred canonicalization
   obligations.

These rules define construction obligations. They are not Python constructors,
JavaScript constructors, host set insertions, host integer increments, or host
object graph operations.

## Membership And Order Obligations

For the finite v0 boundary, membership and order are structural proof
obligations:

```text
beta member_of alpha  iff beta is present in alpha.members with structural proof
beta < alpha          iff beta member_of alpha for canonical finite examples
alpha <= beta         iff alpha < beta or alpha == beta, when both facts are proven
```

The later implementation surface must prove these facts by structural
membership traversal, proof objects, or projections. It must not rely on
Python `in`, JavaScript `includes`, host set membership, host numeric `<`,
content-hash equality alone, or JSON serialization order.

Finite ordinal membership must also preserve the von Neumann containment
shape:

- every member of an ordinal is itself an ordinal;
- every member of a member is also a member of the containing ordinal;
- `successor(alpha)` contains `alpha`;
- `successor(alpha)` contains every prior member of `alpha`.

This v0 fixes those obligations. It does not discharge them as production
runtime semantics.

## Finite Foundation Examples

The initial bounded examples use aliases so the shapes stay readable:

```text
E  := {"_ord_members": null}
O0 := {"_ord": {"members": E}}
O1 := {"_ord": {"members": {"_ord_members": {"member": O0, "rest": E}}}}
O2 := {"_ord": {"members": {"_ord_members": {"member": O0, "rest": {"_ord_members": {"member": O1, "rest": E}}}}}}
```

| Name | Shape | Required proof facts |
|------|-------|----------------------|
| `0` | `O0` | Empty members; no `beta member_of O0`. |
| `1` | `O1 = successor(O0)` | `0 member_of 1`; `0 < 1`. |
| `2` | `O2 = successor(O1)` | `0 member_of 2`; `1 member_of 2`; `0 < 1 < 2`. |

These examples are intentionally tiny. They bind the first falsifiable
foundation criteria without claiming runtime integration, transfinite closure,
ordinal arithmetic closure, global canonicalization, or bridge closure.

## Canonical Boundary

RecursiveOrdinals v0 has two identities that must not be conflated:

- **Representation identity:** the exact Mu shape and content hash of a
  membership object.
- **Ordinal equality:** the extensional ordinal equality proven from founded
  membership/order obligations.

Representation identity is enough for the hand-authored finite fixtures in
this document only because the examples fix one local spelling. It is not a
global ordinal equality proof. A later canonicalizer must prove duplicate
handling, member-list spelling, and extensionally equal containment before it
can claim semantic ordinal equality.

## Bridge Obligations To StructuralNumbers

`StructuralNumbers.v0.md` remains the computational integer representation for
matcher-facing numeric facts. RecursiveOrdinals is the finite containment
foundation that later waves must bridge to that representation.

Later implementation waves must define structural projections:

```text
ord_to_N : RecursiveOrdinal -> StructuralNumbers N
N_to_ord : StructuralNumbers N -> RecursiveOrdinal
```

For finite ordinals, those projections must prove:

1. **Zero round trip:** `ord_to_N(O0)` is the StructuralNumbers zero
   `{"_num": null}`, and `N_to_ord({"_num": null})` is `O0`.
2. **Mutual inverse:** `N_to_ord(ord_to_N(alpha)) == alpha` for canonical
   finite recursive ordinals, and `ord_to_N(N_to_ord(n)) == n` for finite
   StructuralNumbers `N`.
3. **Successor homomorphism:** `ord_to_N(successor(alpha))` equals the
   StructuralNumbers successor of `ord_to_N(alpha)`, and `N_to_ord(successor_N(n))`
   equals `successor(N_to_ord(n))`.
4. **Order preservation:** `beta member_of alpha` iff
   `ord_to_N(beta) < ord_to_N(alpha)` for finite examples and later finite
   fixtures.

This wave records the obligations only. It must not claim production bridge
closure, implemented `ord_to_N`, implemented `N_to_ord`, ordinal arithmetic
closure, or runtime numeric authority.

## Transfinite Boundary

Transfinite constructors such as `omega` are deferred. A future wave may only
promote `omega` after Phase A narrows a falsifiable criterion that does not
require host lazy generators, host infinite sets, production runtime ordinal
semantics, coinduction, fixpoint, or optimization work.

This v0 makes no claim about transfinite closure, limit ordinals, ordinal
addition, ordinal multiplication, exponentiation, cofinality, or higher-order
set theory.

## Explicit Proof Limits

This v0 does not prove or authorize:

- production recursive ordinal runtime semantics;
- implemented `ord_to_N` or `N_to_ord` projections;
- recursive ordinal arithmetic such as addition, multiplication, exponentiation,
  or comparison execution;
- transfinite constructors such as `omega`;
- global canonicalization or quotienting of equivalent ordinal spellings;
- W-types / inductive types, coinduction, fixpoint, or optimization work;
- changes to runtime, substrate, seed, registry, projection, JavaScript parity,
  pager/autoping, tmux, or StructuralNumbers semantic files;
- host ordinal API behavior, host set-theory authority, host numeric coercion,
  or host-only ordinal semantics.

The only closure claimed by this wave is a docs-backed foundation boundary:
RecursiveOrdinals can be described as finite structural containment data with
falsifiable construction, membership, order, and bridge obligations.

## First Foundation Gate Criteria

The focused foundation gate for this v0 must prove:

1. This document exists in `mu/docs/core/` with a DOC_STATUS header and names
   `mu/tests/l4_gates/test_recursive_ordinals_foundation_gate.py` as its
   grounding test.
2. The wave config and tracker note reference this document and the foundation
   gate, making the v0 discoverable without relying on an untracked side
   channel.
3. The text states the representation boundary as structural data, not a host
   ordinal API, host set-theory API, or host numeric execution API.
4. The text names zero, successor, finite recursive containment, and founded
   construction rules.
5. The text records membership/order obligations without authorizing host
   membership or host numeric comparison.
6. The text records finite examples for `0`, `1`, and `2`.
7. The text records `ord_to_N` and `N_to_ord` bridge obligations to
   StructuralNumbers as later implementation work and withholds production
   bridge closure.
8. The text explicitly defers transfinite constructors, runtime semantics,
   later structural waves, and optimization.

Passing that gate is evidence that the first RecursiveOrdinals step is bounded
and falsifiable. It is not evidence of recursive ordinal semantic closure.

## Relationship To Existing Structural Work

`StructuralNumbers.v0.md` remains the active structural integer foundation for
matcher-facing numeric facts. RecursiveOrdinals does not replace it and does
not change its semantics.

`NorthStarSemantics.v0.md` remains the semantic policy lock: host numeric
leaves are not matcher-facing numeric authority, and structural identity must
not rely on Python or JavaScript numeric formatting.

`OntologyPromotionContract.v0.md` remains the promotion discipline: no host
code can mint ontology tokens, and later ordinal tokens require structural
provenance.

`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference: Python
and JavaScript parity is bridge evidence, while L4 bounded reductions must
avoid adding host authority.
