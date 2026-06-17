<!--
DOC_STATUS
TYPE: DESIGN_SPEC
LAST_VERIFIED: 2026-06-17
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py, mu/tests/l4_gates/ (StructuralNumbers gates, added per staged program)

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Structural Numbers for RCX (StructuralNumbers.v0)

**Status:** DESIGN_SPEC — architectural intent for the staged migration of RCX numbers
from host scalars to structural Mu. Adopted 2026-06-17 (founder-directed: "the BEST
STRUCTURAL FIX as a production, research-grade runtime ... with Mu, as
self-hosting/meta-circular running on Mu, not host semantics").

**Supersedes the easy paths:** the float-ban-keep-host-int path and the
`TypedNumericEnvelopes.v0` "Option A (no envelopes, keep host int/float)" decision of
2026-03-01. P6 is re-opened here by **founder direction** (the override authority), as a
structural-purity reframing of the whole numeric-representation question, prompted by the
Stage0 content-addressed-Mu reduction escalation (2026-06-17). This is a founder-directed
reopening, **not** a firing of P6's original mechanical promotion triggers — those are
mixed-int/float-workload specific (e.g. "first real workload requiring mixed numeric forms
(int + float)"), whereas this direction is integer-first with no host floats. The
integer-only `RCXEngineNew` seed motivates structural integers but does not by itself
constitute the original "mixed int + float" trigger.

---

## 1. Purpose and thesis

RCX is a structural VM pursuing self-hosting / meta-circularity: data is JSON-like
structural values ("Mu") and computation is pattern-matching projections. Today,
**numbers are the one domain where RCX still computes on host primitives** — Python
`int`/`float` and JavaScript `number`, with host operators (`==`, `+`) and host
type-dispatch (`isinstance`/`typeof`). That is host semantics, not Mu.

**Thesis:** numbers should *be Mu* — structural values whose arithmetic and equality
are RCX projections — exactly as every mature self-hosting / meta-circular / proof
system represents them (Coq `positive`/`N`/`Z`, Scheme's exact numeric tower, Agda/Idris
inductive `Nat` compiled to GMP, Smalltalk's `Integer` object hierarchy). This makes
RCX's number domain parity-safe by construction, removes the last host type-dispatch
from the Stage0 matcher, and unifies the runtime's numbers with the `RCXEngineNew`
engine's emergent von Neumann ordinals.

This is a research+production design, so it is held to both bars: **structural honesty**
(arithmetic is Mu, "not Python did it") *and* **usable performance** (O(log n), not the
O(n) toy). The reconciliation — structural semantics with a proven-equivalent
host-accelerated representation — is the heart of the design (§7).

---

## 2. The problem, pinned to code

Three code facts make the current representation untenable for "numbers as Mu":

1. **Host scalar type-dispatch in the matcher.** `mu/host/python/rcx_pi/selfhost/eval_seed.py`
   `_stage0_match` dispatches on `isinstance(pattern, bool/int/float/str)`; the JS mirror
   `mu/host/js/core/bootstrap_core.js` `stage0Match` uses `typeof`. This is the residual
   `@host_builtin` marker — pure host type semantics.

2. **Content-hash equality is not parity-safe for host floats.** `mu_hash_cached`
   serializes via `json.dumps`. Command-verified: `json.dumps(42.0) == "42.0"` while JS
   `JSON.stringify(42.0) == "42"`, and `json.dumps(-0.0) == "-0.0"` while
   `JSON.stringify(-0) == "0"` (JS `types.js` then special-cases `-0`→`"-0.0"`). So a
   naive "replace type-dispatch with `mu_hash` equality" collapse trades a host type-check
   for a JSON-float-formatting parity leak (`match([x,x],[1.0,1])` diverges Py vs JS).
   This is precisely why the 2026-06-16 collapse attempt was escalated, not landed.

3. **The runtime's number domain is host, the engine's is structural — and they don't
   meet.** `RCXEngineNew` reconstructs ZFC from recursive containment: numbers are von
   Neumann ordinals (`0=∅`, `n+1 = n∪{n}`), identity by content hash. The runtime cannot
   run that engine "genuinely on Mu" while its own integers are host `int`.

---

## 3. The decision

**Canonical integer = binary-positional structural numeral (Coq `positive`/`N`/`Z`
shape). Arithmetic, comparison, and the numeric forms are Mu projections. Equality is
free via content-addressed hashing. Rationals are pairs of structural integers; reals are
lazy signed-digit streams. Host floats are forbidden. A host-accelerated `int`/`BigInt`
codec provides production speed and is held equivalent by a cross-substrate gate. Von
Neumann ordinals remain the engine's foundation, bridged to the runtime numeral by a
proven isomorphism.**

### 3.1 Representation (binary, least-significant-bit first; mirrors Coq `BinNums`)

```
positive ::= xH                  -- 1
           | xO positive         -- 2·p   (append low bit 0)
           | xI positive         -- 2·p+1 (append low bit 1)
N        ::= N0 | Npos positive  -- 0, or a positive
Z        ::= Z0 | Zpos positive | Zneg positive   -- 0, +p, -p
```

As Mu (valid `is_mu` dicts; parity-identical across substrates because no host int/float
is ever serialized):

```json
0   →  {"_num": null}
1   →  {"_num": {"xH": null}}
6   →  {"_num": {"xO": {"xI": {"xH": null}}}}          // 6 = 110b, bits 0,1,1 LSB-first
-6  →  {"_num": {"neg": {"xO": {"xI": {"xH": null}}}}}
```

Depth is **O(log n)**: `2^300` nests only 300 deep. This is the decisive property — see §4.

### 3.2 Equality is free (content-addressed, O(1))

RCX already eliminated `mu_equal` as a primitive: equality is `mu_hash_cached(a) ==
mu_hash_cached(b)`, and non-linear pattern matching (binding the same variable twice) *is*
structural equality (`ContentAddressedMu.md`; JS `constants.js` "mu_equal eliminated").
For structural numerals the hash is over `xI/xO/xH/neg/null` dict structure only — **no
host float string ever enters the hash**, so it is parity-safe by construction, and `=` is
O(1) hash comparison. The entire control-hash canonicalization apparatus
(`mu_hash_control`, the `0.0→0` / `+0/−0` special cases) becomes unnecessary *for numbers*,
because the structural form is already canonical and substrate-independent.

### 3.3 Arithmetic as Mu projections (the meta-circular core)

`+`, `*`, `<`, `=` are confluent, terminating **RCX projections**, bit-recursive on the
binary structure — the same projection mechanism that already drives `recurrence.v1.json`
/ `match.v2.json`, and the direct analogue of Coq's `Pos.add`/`Pos.add_carry` and the
standard terminating+confluent term-rewriting systems for binary integer arithmetic. New
seeds (`numerals.v1.json`, then `rational.v1.json`, optionally `real_stream.v1.json`),
each SHA-checksummed with cross-substrate parity vectors like existing seeds. Arithmetic
logic lives in projections, not host operators → the North Star "emergence is RCX
dynamics, not 'Python did it'" constraint is satisfied for numbers.

### 3.4 Rationals and reals (exact; no host floats, ever)

- **Rationals** = `{num: Z, den: positive}`, reduced to lowest terms by a structural gcd
  projection (Scheme's exact tower; denominator always a `positive`).
- **Reals** (only when a workload needs them) = lazy coinductive streams of signed digits
  `{−1, 0, 1}` (constructive / exact-real arithmetic), i.e. a Mu thunk/stream producing
  digits — structural, parity-safe, host-float-free.
- **Floats** are forbidden. They are mathematically unnecessary in a research VM and are
  the exact `json.dumps`≠`JSON.stringify` parity bug. (Non-numeric float *inputs* at the
  boundary, if any remain, are a separate boundary-policy question and out of scope here.)

---

## 4. Why not the alternatives (each ruled out by evidence)

| Option | Structural? | Size of *n* | Verdict |
|---|---|---|---|
| **Float-ban, keep host `int`** | No | — | **Rejected.** Still host integers + host `==`/`+`. The easy fix the founder explicitly excluded. |
| **Unary / Peano (`0`/`succ`)** | Yes (purest) | **O(n) depth** | **Rejected.** `mu_type.py` `MAX_MU_DEPTH = 300` → cannot represent n ≥ ~300. |
| **Literal von Neumann set (`n = {0..n-1}`)** | Yes (foundational) | **O(n) depth *and* O(n) width** | **Rejected as runtime rep.** `n` is a set with n members → detonates both `MAX_MU_DEPTH=300` and `MAX_MU_WIDTH=1000`; ordinal `+` is non-commutative. Kept as the *engine foundation* (§6). |
| **Scott / Church encodings** | Yes (λ-encoded) | O(n) | **Rejected.** RCX is data-structural (JSON Mu), not λ-calculus; encodings buy nothing here. |
| **Binary-positional (Coq `positive`)** | **Yes** | **O(log n) depth** | **Adopted.** Structural *and* O(log n); clean 3-constructor pattern matching. Coq's documented choice: binary `N` for computation, unary `nat` only for proofs. |

The depth/width limits (`MAX_MU_DEPTH = 300`, `MAX_MU_WIDTH = 1000`, both verified in
`mu/host/python/rcx_pi/selfhost/mu_type.py`) are not abstract — they make unary and von
Neumann *representations* impossible for any realistic integer. Binary is the only
structural form that fits.

---

## 5. North Star alignment

- **No new host capability in the bootstrap.** Arithmetic moves *out* of host operators
  into projections; the structural numeral is ordinary Mu. The only host touch is the §7
  boundary codec, which is the *same class* of boundary scaffolding RCX already sanctions
  for `mu_hash` and JSON parsing (not a kernel primitive) — and it strictly *reduces* net
  host authority (it removes the `_stage0_match` scalar type-dispatch).
- **Cross-substrate parity (`INV_CROSS_SUBSTRATE_PARITY`).** The structural form is
  substrate-independent; the accelerator uses Python `int` / JS `BigInt`, both exact
  arbitrary-precision (command-verified: `2^70` identical on both) — no float, no
  divergence.
- **Reduction, not addition (`rule_11`).** This collapses host type-dispatch + host
  arithmetic into structural Mu; it is a structural reduction, the parity-preserving
  boundary tightening the behavioral protocol prefers.
- **`NorthStarSemantics.v0.md` reconciliation.** §B ("Zero Canonicalization") is stale —
  it claims `json.dumps` canonicalizes `+0/−0` and `mu_hash_cached(+0)==mu_hash_cached(−0)`,
  both false in code; §B.1 (the two-hash control/data split) is accurate. Under structural
  numbers, signed-zero is simply not representable as a distinct integer (`0 = {"_num":
  null}` is unique), so the zero-canonicalization problem dissolves for numbers. NorthStar
  §B should be corrected in the matcher-cutover wave.

---

## 6. Engine unification (von Neumann ordinals ↔ binary `N`)

`RCXEngineNew` is built on von Neumann ordinals emerging from recursive containment —
that *is* the research thesis (numbers emerge from structural pressure) and must stay as
the **foundation layer**. The unification the founder wants is **not** "make every runtime
integer a nested set" (fatal, §4), but a **proven structural isomorphism**:

```
ord_to_N : VonNeumannOrdinal → N      N_to_ord : N → VonNeumannOrdinal
```

defined as projections, with a gate proving they are mutually inverse and homomorphic for
`+`/`*`/`<` on the finite ordinals. Then the engine's emergent number and the runtime's
computational number are *the same number in two provably-equivalent structural forms* —
von Neumann for "where numbers come from," binary-`N` for "how we compute." This is exactly
Coq's `nat` (foundational/proof) ↔ `N` (computational) relationship. With the isomorphism
gated, `RCXEngineNew` runs genuinely on Mu: domain objects and runtime numbers unify with
zero host-int bridge.

---

## 7. Performance reconciliation (what makes this production-grade)

**Claim:** you can have structural *semantics* (parity-safe, host-free) with a
host-accelerated *representation* that is *provably equivalent*. This is how every
production proof assistant ships, and RCX adopts it.

1. **Canonical semantics layer** — the binary-positive `N`/`Z` Mu structure + the
   arithmetic/equality projections. This is what the kernel matches, what hashes, what
   guarantees parity. All correctness/parity proofs live here.
2. **Accelerated boundary representation** — at the existing host boundary (where
   `mu_hash`/JSON already live), a codec `structural_to_host` / `host_to_structural` using
   Python `int` / JS `BigInt` (both exact — no float). A fast path may compute on the host
   bignum and re-encode to canonical structure.
3. **Equivalence obligation (this is what makes it honest, not a cheat)** — a
   property/fuzz gate proving, on **both** substrates, that
   `structural_add(a,b) ≡ host_to_structural(to_host(a) + to_host(b))` (and likewise for
   `*`, `<`, `=`, round-trip), exactly as RCX already proves `mu_equal ≡ mu_hash_cached`
   and runs cross-substrate parity vectors. The accelerator is *only ever* a
   proven-equivalent optimization of the structural projections; if the proof fails, the
   structural path is the source of truth.

Precedents: Agda `{-# BUILTIN NATURAL #-}` maps inductive `ℕ` to GMP ("space proportional
to log n" vs unary's "proportional to n"); Idris erases `Nat` indices and uses GMP; the
"Custom Representations of Inductive Families" line formalizes "represent Nat as GMP
bigints with computationally-irrelevant isomorphisms"; Smalltalk transparently promotes
`SmallInteger`→`LargeInteger`. Structural meaning, fast representation, provably equal.

---

## 8. The staged program

Each stage is a separate pipeline wave with its own gate; later stages depend on earlier.

1. **Foundation (first wave, L4_STRUCTURAL).** Define the binary-positive numeral as Mu in
   both substrates (a numeral module: validate / round-trip), its free content-addressed
   equality, and the host-accelerated `int`/`BigInt` codec, with a **cross-substrate
   equivalence gate** (`structural ↔ exact int/BigInt` round-trip + structural equality
   parity). No `_stage0_match` change yet, no seed migration — this proves "numbers can be
   Mu, parity-safe, production-fast" in isolation.
2. **Arithmetic projections.** `numerals.v1.json` — `add`/`mul`/`sub`/`cmp` as bit-recursive
   projections + the accelerated fast path + the arithmetic equivalence gate.
3. **Rationals (+ optional reals).** `rational.v1.json` (`{num, den}` reduced) and, if a
   workload needs it, `real_stream.v1.json` (signed-digit streams).
4. **Matcher cutover.** Replace the `_stage0_match` / `stage0Match` scalar type-dispatch
   with structural matching over numerals; clear the `@host_builtin` scalar marker (a real
   reduction, not net-delta-0); correct `NorthStarSemantics.v0.md` §B.
5. **Engine isomorphism.** `ord_to_N` / `N_to_ord` projections + the isomorphism gate;
   demonstrate `RCXEngineNew` running on structural runtime numbers.

P6 (`TypedNumericEnvelopes.v0.md`) is reopened: this doc is the structural answer its
re-evaluation anticipated; the envelope tags `{"_mu_int": ...}` were a thinner version of
the same idea, but a full numeral structure (with arithmetic-as-projection) is the
production-grade form.

---

## 9. References

**Precedents.** Coq `BinNums` (`positive`/`N`/`Z`, binary for computation) ·
Agda built-ins (`BUILTIN NATURAL` → GMP; log-n vs n space) · Idris erasure (`Nat` → GMP) ·
"Custom Representations of Inductive Families" (arXiv:2505.21225) · R7RS numeric tower
(exact integers/rationals) · Smalltalk `SmallInteger`→`LargeInteger` promotion ·
term-rewriting Peano/binary integer arithmetic (confluent + terminating) · hash consing
(O(1) structural equality) · constructive / exact-real arithmetic (signed-digit streams) ·
von Neumann ordinals (`n = n ∪ {n}`; ordinal arithmetic).

**Local files.** `mu/host/python/rcx_pi/selfhost/eval_seed.py` (`_stage0_match`) ·
`mu/host/js/core/bootstrap_core.js` (`stage0Match`) ·
`mu/host/python/rcx_pi/selfhost/mu_type.py` (`MAX_MU_DEPTH=300`, `MAX_MU_WIDTH=1000`,
`mu_hash_cached`) · `mu/host/js/core/types.js` (`muHashCached`, `-0` special case) ·
`mu/docs/core/TypedNumericEnvelopes.v0.md` (P6, the easy path superseded) ·
`roadmap/ContentAddressedMu.md` (hash-identity = free equality) ·
`mu/docs/core/NorthStarSemantics.v0.md` (§B stale; §B.1 two-hash accurate) ·
`mu/docs/core/RCXEngine.v0.md` + `RCXEngineNew.pdf` (von Neumann ordinals — engine
foundation to bridge by isomorphism).
