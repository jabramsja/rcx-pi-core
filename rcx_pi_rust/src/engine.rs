use crate::state::RCXState;
use crate::trace::RouteKind;
use crate::traits::{Classification, classify};
use crate::types::{Mu, RcxProgram, RuleAction};

/// Simple pattern matcher with `_` as a wildcard symbol.
///
/// Rules:
///   - `Sym("_")` matches any Mu (symbol or node).
///   - `Sym("foo")` matches only `Sym("foo")`.
///   - `Node([...])` matches `Node([...])` of the same length, elementwise.
fn pattern_matches(pattern: &Mu, value: &Mu) -> bool {
    match (pattern, value) {
        // `_` wildcard: matches anything
        (Mu::Sym(p), _) if p == "_" => true,

        // Symbol must match exactly
        (Mu::Sym(p), Mu::Sym(v)) => p == v,

        // Node: same length, all children must match
        (Mu::Node(p_children), Mu::Node(v_children)) => {
            if p_children.len() != v_children.len() {
                return false;
            }
            p_children
                .iter()
                .zip(v_children.iter())
                .all(|(p_child, v_child)| pattern_matches(p_child, v_child))
        }

        // Anything else does not match
        _ => false,
    }
}

/// RCX-π Engine: wraps a program + structural classifier
/// and routes each Mu into r_a / lobes / sink,
/// while also logging a trace event.
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
    /// Returns the final route (Ra / Lobe / Sink / Structural).
    pub fn process_input(&mut self, state: &mut RCXState, input: Mu) -> Option<RouteKind> {
        // 1) Try explicit program rules first.
        if let Some(route) = self.apply_program_rules(state, &input) {
            return Some(route);
        }

        // 2) Fallback: structural classification on the raw input.
        let route = structural_classify(state, input);
        Some(route)
    }

    /// Apply program rules (ToRa / ToLobe / ToSink / Rewrite).
    /// If a rule fires, we log an event and return the resulting route.
    /// If nothing matches, return None and let the caller fall back.
    fn apply_program_rules(&mut self, state: &mut RCXState, input: &Mu) -> Option<RouteKind> {
        for rule in &self.program.rules {
            // IMPORTANT: use pattern_matches instead of equality
            if !pattern_matches(&rule.pattern, input) {
                continue;
            }

            match &rule.action {
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
                RuleAction::Rewrite(new_mu) => {
                    // Rewrite input → new_mu, then structurally classify that.
                    let rewritten = new_mu.clone();
                    let route = structural_classify(state, rewritten.clone());
                    state.log_event("engine_rule_rewrite", route, rewritten);
                    return Some(route);
                }
            }
        }

        None
    }
}

/// Structural classifier used both as fallback and after Rewrite.
/// This mirrors your Ra / Lobe / Sink semantics and logs a trace event.
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
