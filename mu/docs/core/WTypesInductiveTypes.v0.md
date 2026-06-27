<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-06-26
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/l4_gates/test_w_types_inductive_foundation_gate.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest mu/tests/l4_gates/test_w_types_inductive_foundation_gate.py -v
-->

# W-Types And Inductive ASTs For RCX (WTypesInductiveTypes.v0)

**Status:** REFERENCE - first bounded foundation contract for representing
W-types, inductive constructors, and AST-as-inductive-structure as Mu data.
This v0 is not a host algebraic data type API, not a host typeclass API, not a
host parser API, not a TypeScript interface authority, and not a host
class/dataclass authority. It does not authorize production W-type runtime
semantics.

**Authority:** `TASKS.md` carries the 2026-06-26 tracker sync note for
`w-types-inductive-types-ast-as-inductive-structure-2026-06-26`. That same-wave
tracker note is the authority for this bounded W-types / inductive-types first
step. `STATUS.md` keeps Phase 8c, the L4 bounded-reduction posture, and the
current debt ledgers unchanged unless separately revalidated.

## Purpose

WTypesInductiveTypes records the first representation boundary for inductive
data families that can later support self-hosting building blocks such as
AST-as-data, syntax trees, and structurally checked constructors. The first
step is deliberately small: define signature nodes, constructor nodes,
parameter and child positions, linked child lists, recursive subtree
containment, AST node representation, finite examples, later induction and
structural recursion obligations, and proof limits.

This document is a structural-data proposal, not an implementation plan for a
host W-type library. It states what later waves must prove before W-type or
inductive AST values can become production runtime facts.

## Representation Boundary

The v0 representation uses explicit Mu nodes and linked lists:

```text
w_signature     ::= {"_w_signature": {"name": string,
                                      "parameters": parameter_list,
                                      "constructors": constructor_list}}

constructor     ::= {"_w_constructor": {"name": string,
                                        "parameters": parameter_list,
                                        "children": child_list,
                                        "result": signature_ref}}

parameter_list  ::= {"_w_parameters": null}
                  | {"_w_parameters": {"position": position,
                                       "name": string,
                                       "sort": mu_shape_ref,
                                       "rest": parameter_list}}

constructor_list ::= {"_w_constructors": null}
                   | {"_w_constructors": {"constructor": constructor,
                                          "rest": constructor_list}}

child_list      ::= {"_w_children": null}
                  | {"_w_children": {"position": position,
                                     "name": string,
                                     "sort": mu_shape_ref,
                                     "recursive": bool,
                                     "rest": child_list}}

inductive_node  ::= {"_w_node": {"signature": signature_ref,
                                 "constructor": string,
                                 "parameters": value_list,
                                 "children": value_list}}

value_list      ::= {"_w_values": null}
                  | {"_w_values": {"position": position,
                                   "name": string,
                                   "value": Mu,
                                   "rest": value_list}}

position        ::= {"_position": {"path": position_path}}
position_path   ::= {"_position_path": null}
                  | {"_position_path": {"step": string,
                                        "rest": position_path}}
```

The linked shapes are intentional. They use ordinary Mu dictionaries, strings,
booleans, and `null`. They do not require host arrays, host tuples, host enum
variants, host classes, host dataclasses, host parser objects, host object
identity, TypeScript interfaces, or host type-system authority.

The `_w_signature`, `_w_constructor`, `_w_children`, `_w_node`, and
`_position` tags name the representation family only. They do not make a
constructor well-formed, execute a recursor, typecheck a program, parse source
text, evaluate an AST, or close self-hosting by host authority.

## Constructor And Signature Obligations

A proposed WTypesInductiveTypes datum is a candidate structural signature only
when these obligations are met:

1. A signature node names one inductive family and carries a linked parameter
   list plus a linked constructor list.
2. Each constructor node names one introduction form for that signature and
   carries its own parameter list, linked child list, and result signature
   reference.
3. Parameter positions are explicit structural positions; they are not Python
   parameter indexes, JavaScript argument indexes, host array offsets, or host
   type variables.
4. Child positions are explicit structural positions; they are not host tuple
   fields, host object properties, TypeScript member declarations, or parser
   child indexes.
5. Child lists must be linked Mu lists. The first implementation wave must not
   rely on host arrays to define constructor arity.
6. A recursive child marks recursive subtree containment with
   `"recursive": true`; non-recursive payload children mark `"recursive":
   false`.
7. Recursive subtree containment is founded for finite values: every recursive
   child value must be another `inductive_node` for the same family or a
   structurally declared mutually inductive family.
8. Mutual induction, indexed families, dependent arities, constructor
   disjointness, and global canonicalization are later obligations.

These rules define representation obligations. They are not Python
constructors, JavaScript constructors, host algebraic data types, host parser
productions, host class hierarchies, or host typeclass instances.
They are explicitly not host algebraic data types.

## Induction And Structural Recursion Obligations

Induction and structural recursion are later implementation obligations. A
future Phase A must narrow a falsifiable slice before any production recursor,
eliminator, fold, induction principle, pattern compiler, or AST evaluator is
implemented.

Later waves must prove at least these obligations before claiming production
semantics:

1. **Constructor coverage:** every constructor in the signature has a branch in
   the recursor or eliminator proof object.
2. **Child decrease:** every recursive call consumes a declared recursive
   child, not an arbitrary host reference.
3. **Parameter preservation:** parameter values flow through recursive
   subtrees as Mu data and are not recovered from host closure state.
4. **Branch result shape:** every branch result is a Mu value whose shape is
   declared by the recursor target.
5. **Deterministic traversal:** linked child traversal is deterministic across
   substrates without host object ordering.
6. **Fail-closed malformed nodes:** unknown constructors, missing child
   positions, duplicate structural positions, and recursive children with the
   wrong signature fail closed.

This v0 records those obligations only. It does not claim induction principle
execution, structural recursion execution, eliminator closure, recursive AST
evaluator closure, pattern compiler closure, or self-hosting closure.

## Small Foundation Examples

The examples below use aliases so the shapes stay readable:

```text
P0 := {"_w_parameters": null}
K0 := {"_w_children": null}
C0 := {"_w_constructors": null}
V0 := {"_w_values": null}
Pos(name) := {"_position": {"path": {"_position_path": {"step": name,
               "rest": {"_position_path": null}}}}}
```

### Bool

```text
BoolSig := {"_w_signature": {"name": "Bool",
                             "parameters": P0,
                             "constructors": BoolCtors}}
TrueCtor := {"_w_constructor": {"name": "true",
                                "parameters": P0,
                                "children": K0,
                                "result": "Bool"}}
FalseCtor := {"_w_constructor": {"name": "false",
                                 "parameters": P0,
                                 "children": K0,
                                 "result": "Bool"}}
BoolTrue := {"_w_node": {"signature": "Bool",
                         "constructor": "true",
                         "parameters": V0,
                         "children": V0}}
BoolFalse := {"_w_node": {"signature": "Bool",
                          "constructor": "false",
                          "parameters": V0,
                          "children": V0}}
```

Required proof facts: `true` and `false` are nullary constructors for `Bool`;
neither constructor authorizes host booleans as inductive values.

### List

```text
ListSig(A) has constructors:
nil  : List(A)
cons : head:A, tail:List(A) -> List(A)

ConsChildren :=
{"_w_children": {"position": Pos("head"),
                 "name": "head",
                 "sort": "A",
                 "recursive": false,
                 "rest": {"_w_children": {"position": Pos("tail"),
                                           "name": "tail",
                                           "sort": "List(A)",
                                           "recursive": true,
                                           "rest": K0}}}}
```

Required proof facts: tail is the recursive subtree (`tail` slot); `head` is payload data;
constructor arity comes from the linked child list, not from a host tuple or
host array.

### Binary Tree

```text
TreeSig(A) has constructors:
leaf : value:A -> Tree(A)
node : left:Tree(A), right:Tree(A) -> Tree(A)
```

Required proof facts: `left` and `right` are recursive subtree children;
`value` is a non-recursive payload child; finite trees are founded by recursive
subtree containment.

### Tiny Expression AST

An AST node is an inductive node whose signature records syntax constructors
as structural data. This v0 uses a tiny expression family:

```text
ExprSig has constructors:
zero : Expr
var  : name:String -> Expr
add  : left:Expr, right:Expr -> Expr

ZeroExpr := {"_w_node": {"signature": "Expr",
                         "constructor": "zero",
                         "parameters": V0,
                         "children": V0}}

VarX := {"_w_node": {"signature": "Expr",
                     "constructor": "var",
                     "parameters": V0,
                     "children": {"_w_values": {"position": Pos("name"),
                                                "name": "name",
                                                "value": "x",
                                                "rest": V0}}}}

AddZeroX := {"_w_node": {"signature": "Expr",
                         "constructor": "add",
                         "parameters": V0,
                         "children": {"_w_values": {"position": Pos("left"),
                                                    "name": "left",
                                                    "value": ZeroExpr,
                                                    "rest": {"_w_values": {
                                                      "position": Pos("right"),
                                                      "name": "right",
                                                      "value": VarX,
                                                      "rest": V0}}}}}}
```

This is AST-as-inductive-structure: syntax nodes are Mu values with signature,
constructor, parameter, and linked child-list evidence. It is not a host AST
parser, not a Python `ast.AST` adapter, not a TypeScript interface, and not an
AST evaluator.

## Canonical Boundary

WTypesInductiveTypes v0 has two identities that must not be conflated:

- **Representation identity:** the exact Mu shape and content hash of a
  signature, constructor, child list, or node.
- **Inductive well-formedness:** the proof that a node's constructor belongs to
  the referenced signature and that its parameter and child values satisfy the
  declared positions and recursive containment obligations.

Representation identity is enough for the hand-authored finite fixtures in
this document only because the examples fix one local spelling. It is not a
global constructor equality proof, not a parser equivalence proof, and not a
normal-form proof.

## Deferred Queue Boundaries

Coinduction remains the next later queue item for non-termination as structure.
This wave does not advance coinduction.

Fixpoint remains the later queue item for evaluator-as-structure and the
meta-circular payoff. This wave does not advance fixpoint.

Optimization remains LAST. This wave does not authorize optimization work,
performance-first rewrites, cached W-type normal forms, AST evaluator
optimization, or production projection optimization.

## Explicit Proof Limits

This v0 does not prove or authorize:

- production W-type runtime semantics;
- production inductive type runtime semantics;
- a production constructor checker, recursor, eliminator, induction principle,
  fold, structural recursion engine, pattern compiler, AST parser, or AST
  evaluator;
- recursive AST evaluator closure, W-type semantic closure, eliminator closure,
  induction principle execution, or self-hosting closure;
- coinduction closure, fixpoint closure, or optimization closure;
- changes to runtime, substrate, seed, registry, projection, JavaScript parity,
  pager/autoping, tmux, evaluator, parser, or production AST files;
- host algebraic data type behavior, host typeclass authority, host parser
  authority, host class/dataclass authority, TypeScript interface authority, or
  host-only inductive semantics.

The only closure claimed by this wave is a docs-backed foundation boundary:
W-types and inductive ASTs can be described as structural Mu signatures,
constructors, linked child lists, recursive subtree obligations, and finite
examples with falsifiable representation criteria.

## First Foundation Gate Criteria

The focused foundation gate for this v0 must prove:

1. This document exists in `mu/docs/core/` with a DOC_STATUS header and names
   `mu/tests/l4_gates/test_w_types_inductive_foundation_gate.py` as its
   grounding test.
2. The wave config, governing packet, and tracker note reference this document
   and the foundation gate, making the v0 discoverable without relying on an
   untracked side channel.
3. The text states the representation boundary as structural data, not a host
   algebraic data type API, host typeclass API, host parser API, host
   class/dataclass authority, or TypeScript interface authority.
4. The text defines signature node, constructor node, parameter positions,
   child positions, linked child lists, recursive subtree containment, and
   inductive AST node representation.
5. The text records induction and structural recursion obligations as later
   implementation obligations without authorizing a production recursor,
   eliminator, AST evaluator, pattern compiler, or self-hosting closure.
6. The text records finite examples for Bool, List, binary Tree, and a tiny
   expression AST.
7. The text explicitly defers coinduction, fixpoint, and optimization, and
   keeps optimization LAST.
8. The text withholds runtime, substrate, seed, registry, projection, parity,
   pager/autoping, tmux, evaluator, parser, and optimization edits.

Passing that gate is evidence that the first WTypesInductiveTypes step is
bounded and falsifiable. It is not evidence of W-type semantic closure,
induction principle execution, AST evaluator closure, or self-hosting closure.

## Relationship To Existing Structural Work

`MuType.v0.md` remains the base value contract: every representation above is
ordinary JSON-compatible Mu.

`SelfHosting.v0.md` and `MetaCircularKernel.v0.md` remain the current
self-hosting and kernel-loop references. This v0 adds representation
obligations only; it does not change match, substitution, kernel selection, or
Stage0 execution.

`StructuralPurity.v0.md` remains the guardrail: computation should be expressed
as Mu transformations, not host object-model behavior.

`NorthStarSemantics.v0.md` remains the semantic policy lock: structural facts
must not be smuggled through host numeric, parser, or type-system behavior.

`OntologyPromotionContract.v0.md` remains the promotion discipline: no host
code can mint ontology tokens, and later inductive-family tokens require
structural provenance.

`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference: Python
and JavaScript parity is bridge evidence, while L4 bounded reductions must
avoid adding host authority.
