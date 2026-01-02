use std::collections::HashMap;

use crate::state::RCXState;
use crate::trace::RouteKind;
use crate::traits::{Classification, classify};
use crate::types::{Mu, RcxProgram, RcxRule, RuleAction};

/// Match a pattern against a value, with:
///   - `_`  = wildcard
///   - `$x` = variable binder (must be consistent if reused)
///
/// Returns `true` on success and fills `subst` with any `$var -> Mu` bindings.
fn match_with_vars(pattern: &Mu, value: &Mu, subst: &mut HashMap<String, Mu>) -> bool {
    match (pattern, value) {
        // `_` matches anything
        (Mu::Sym(p), _) if p == "_" => true,

        // `$x` style variable
        (Mu::Sym(p), v) if p.starts_with('$') => {
            let name = &p[1..]; // strip leading '$'
            if let Some(bound) = subst.get(name) {
                // Must match previous binding
                bound == v
            } else {
                // First time we see this var: bind it
                subst.insert(name.to_string(), v.clone());
                true
            }
        }

        // Plain symbol: must match exactly another symbol
        (Mu::Sym(p), Mu::Sym(v)) => p == v,

        // Node: same arity, all children must match
        (Mu::Node(ps), Mu::Node(vs)) if ps.len() == vs.len() => {
            for (p_child, v_child) in ps.iter().zip(vs.iter()) {
                if !match_with_vars(p_child, v_child, subst) {
                    return false;
                }
            }
            true
        }

        _ => false,
    }
}

/// Apply a `$var` substitution to a Mu template.
///
/// Any `Sym("$x")` is replaced by the bound Mu in `subst` if present.
/// Everything else is passed through unchanged.
fn apply_subst(term: &Mu, subst: &HashMap<String, Mu>) -> Mu {
    match term {
        Mu::Sym(s) => {
            if s.starts_with('$') {
                let name = &s[1..];
                if let Some(v) = subst.get(name) {
                    v.clone()
                } else {
                    // Unbound variable: leave as-is
                    Mu::Sym(s.clone())
                }
            } else {
                Mu::Sym(s.clone())
            }
        }
        Mu::Node(children) => {
            let mapped = children.iter().map(|c| apply_subst(c, subst)).collect();
            Mu::Node(mapped)
        }
    }
}

/// Structural classifier used both as fallback and after Rewrite.
/// This mirrors the Ra / Lobe / Sink semantics and logs a trace event.
fn structural_classify(state: &mut RCXState, mu: Mu) -> RouteKind {
    match classify(&mu) {
        Classification::Ra => {
            state.ra.push(mu.clone());
            state.log_event("engine_structural_ra", RouteKind::Ra, mu);
            RouteKind::Ra
        }
        Classification::Lobe => {
            state.lobes.push(mu.clone());
            state.log_event("engine_structural_lobe", RouteKind::Lobe, mu);
            RouteKind::Lobe
        }
        Classification::Sink => {
            state.sink.push(mu.clone());
            state.log_event("engine_structural_sink", RouteKind::Sink, mu);
            RouteKind::Sink
        }
    }
}

/// RCX-π Engine: wraps a program + structural classifier
/// and routes each Mu into r_a / lobes / sink,
/// while also logging trace events.
pub struct Engine {
    pub program: RcxProgram,
}

impl Engine {
    pub fn new(program: RcxProgram) -> Self {
        Self { program }
    }

    /// Process a single input Mu:
    /// 1) Try explicit program rules (including Rewrite).
    /// 2) If no rule matches, fall back to structural classification.
    pub fn process_input(&mut self, state: &mut RCXState, input: Mu) -> Option<RouteKind> {
        if let Some(route) = self.apply_program_rules(state, &input) {
            return Some(route);
        }

        let route = structural_classify(state, input);
        Some(route)
    }

    /// Apply program rules (ToRa / ToLobe / ToSink / Rewrite) with `$var` support.
    ///
    /// If a rule fires, we:
    ///   - perform any rewrite with substitution
    ///   - structurally classify the result into r_a / lobes / sink
    ///   - log trace events
    fn apply_program_rules(&mut self, state: &mut RCXState, input: &Mu) -> Option<RouteKind> {
        for RcxRule { pattern, action } in &self.program.rules {
            let mut subst: HashMap<String, Mu> = HashMap::new();

            if !match_with_vars(pattern, input, &mut subst) {
                continue;
            }

            match action {
                RuleAction::ToRa => {
                    state.ra.push(input.clone());
                    state.log_event("engine_rule_to_ra", RouteKind::Ra, input.clone());
                    return Some(RouteKind::Ra);
                }
                RuleAction::ToLobe => {
                    state.lobes.push(input.clone());
                    state.log_event("engine_rule_to_lobe", RouteKind::Lobe, input.clone());
                    return Some(RouteKind::Lobe);
                }
                RuleAction::ToSink => {
                    state.sink.push(input.clone());
                    state.log_event("engine_rule_to_sink", RouteKind::Sink, input.clone());
                    return Some(RouteKind::Sink);
                }
                RuleAction::Rewrite(template) => {
                    // 1) Instantiate template with `$var` bindings.
                    let rewritten = apply_subst(template, &subst);

                    // 2) Let structural classifier decide where it lives.
                    let route = structural_classify(state, rewritten.clone());

                    // 3) Log a rewrite event on top.
                    state.log_event("engine_rule_rewrite", route, rewritten);

                    return Some(route);
                }
            }
        }

        None
    }
}
