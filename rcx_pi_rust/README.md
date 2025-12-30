# RCX-π Rust Engine

Minimal executable RCX runtime implemented in Rust.  
This project is the *structural core* — the organism from which richer RCX behavior can evolve.

It includes:  
- Mu term language  
- Ra / Lobe / Sink projection buckets  
- Rewrite programs  
- Worlds system (`.mu` rule-sets)  
- REPL with `:why`, `:orbit`, `:omega`

---

## 1. Purpose

This crate provides the minimal organism that RCX runs on:

`input Mu → reduction → classification → rₐ / lobes / sink`  
with a trace log for every step.

- Atoms stabilize.
- Coherent structures form lobes.
- Contradictions fall into sink.
- Nothing is forgotten.

It is deliberately small, inspectable, and buildable-forward.

---

## 2. Mu Language

Mu terms:

```text
a                # symbol
[news,stable]    # node
[omega,[a,b]]    # nested
_                # wildcard in patterns (only in rules), e.g. [news,_]
'''

⸻

3. Core Types

3.1 Symbol space

pub enum Mu {
    Sym(String),        // atomic symbol, “stable enough to project”
    Node(Vec<Mu>),      // nested structure of symbols
}

3.2 Runtime state

pub struct RCXState {
    pub current: Option<Mu>,  // active item being processed
    pub ra: Vec<Mu>,          // stable projection
    pub lobes: Vec<Mu>,       // coherent but not stable
    pub sink: Vec<Mu>,        // paradox/contradiction storage

    pub null_reg: Vec<Mu>,    // reserved null hemisphere
    pub inf_reg: Vec<Mu>,     // reserved infinity hemisphere

    pub trace: Vec<TraceEvent>,
    pub step_counter: u64,
}

Interpretation:

Region	Meaning
rₐ	stable projection / accepted structure
lobes	coherent but incomplete / held for potential merge
sink	contradictory or undefined, preserved without forcing
null/inf	future hemispheric routing


⸻

4. Structural Classification

Default classifier:

Input Mu	Route
Sym(_)	rₐ
Node([...]) all elements equal	lobe
Node([...]) mixed symbols	sink

Ontology mapping:
	•	atoms → stabilized truth
	•	coherence → potential truth
	•	contradiction → tension retained

⸻

5. Programs & Rules

pub struct RcxProgram {
    pub rules: Vec<RcxRule>,
}

pub struct RcxRule {
    pub pattern: Mu,
    pub action: RuleAction,
}

pub enum RuleAction {
    ToRa,
    ToLobe,
    ToSink,
    Rewrite(Mu),
}

Rules are checked before structural classification.
If no rule matches, fallback handles the routing.

⸻

6. Trace Logging

pub struct TraceEvent {
    pub step_index: u64,
    pub phase: String,
    pub route: RouteKind,
    pub payload: Mu,
}

Example:

step 2 | phase=engine_structural_lobe | route=Lobe | payload=[A,A]


⸻

7. Worlds

Stored in /mu_programs/:

# mu_programs/rcx_core.mu

[null,_]    -> ra
[inf,_]     -> lobe
[paradox,_] -> sink
[ra,_]      -> ra
[lobe,_]    -> lobe
[sink,_]    -> sink
[shadow,_]  -> sink
[omega,_]   -> lobe

Example:

:load-world rcx_core
[null,a] → ra
[inf,a]  → lobe

Wildcards _ match any symbol in that slot.

⸻

8. REPL

Run:

cargo run --example repl

You’ll see:

RCX-π REPL — Mu → [r_a | lobes | sink]
Commands:
  <mu>             evaluate expression
  :load FILE       load rules
  :rules           list rules
  :why MU          show trace
  :learn           add rule
  :orbit MU [n]    rewrite orbit
  :omega MU [n]    ω-limit summary
  :worlds          list .mu files
  :save-world      save world
  :load-world      reset + load world
  :trace           view trace
  :clear           reset buckets only
  :reset           full reset
  :q               exit

Rewrite / ω-limit example:

:load pingpong.mu
:learn ping rewrite pong
:learn pong rewrite ping
:omega ping 12
→ pure limit cycle (period = 2)


⸻

9. Status

Component	Status
Mu symbolic space	✔
rₐ / lobes / sink	✔
Structural routing	✔
Rules + rewrite	✔
Trace logging	✔
REPL + worlds	✔
null / inf hemispheres	placeholder ready


⸻

10. Roadmap
	•	Serialization (JSON/TOML)
	•	Save/load full RCX state
	•	Lobe merge strategies
	•	Null/∞ hemisphere recursion
	•	ω-limit visual explorer

⸻

11. Philosophy

RCX-π is:
	•	small enough to grasp in one sitting
	•	extensible without rewriting the core
	•	deterministic at the base
	•	paradox-preserving, reflective
	•	designed to grow into RCX-proper

It is not all of RCX — it is the spine that everything grows from.
