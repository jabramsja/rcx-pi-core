// src/runtime.rs

use crate::eval::reduce_step;
use crate::state::RCXState;
use crate::trace::RouteKind;
use crate::traits::{Classification, classify};
use crate::types::{Mu, RcxProgram, RcxRule, RuleAction};

/// Pure structural step (no explicit program):
/// - tries to reduce the current term
/// - classifies the result into r_a / lobes / sink
/// - logs a trace event
pub fn step(state: &mut RCXState) {
    if let Some(mu) = reduce_step(state) {
        let route = match classify(&mu) {
            Classification::Ra => {
                state.ra.push(mu.clone());
                RouteKind::Ra
            }
            Classification::Lobe => {
                state.lobes.push(mu.clone());
                RouteKind::Lobe
            }
            Classification::Sink => {
                state.sink.push(mu.clone());
                RouteKind::Sink
            }
        };

        state.log_event("step(structural)", route, mu);
    } else {
        // No-op / stall; we don't log anything for now.
    }
}

/// Program-aware classification:
/// 1. Try explicit RcxRule patterns
/// 2. If no rule matches, fall back to structural classification (same as `step`)
/// Returns the route used, if any.
pub fn classify_with_program(state: &mut RCXState, program: &RcxProgram) -> Option<RouteKind> {
    let current = match &state.current {
        Some(mu) => mu.clone(),
        None => return None,
    };

    // 1) Try explicit rules first
    for RcxRule { pattern, action } in &program.rules {
        if &current == pattern {
            let route = match action {
                RuleAction::ToRa => {
                    state.ra.push(current.clone());
                    RouteKind::Ra
                }
                RuleAction::ToLobe => {
                    state.lobes.push(current.clone());
                    RouteKind::Lobe
                }
                RuleAction::ToSink => {
                    state.sink.push(current.clone());
                    RouteKind::Sink
                }
                RuleAction::Rewrite(target) => {
                    // Rewrite the current Mu and keep it in-flight.
                    state.current = Some(target.clone());
                    RouteKind::Rewrite
                }
            };

            state.log_event("classify_with_program(rule)", route, current);

            // If we projected, clear current; if we rewrote, it's already updated.
            if !matches!(action, RuleAction::Rewrite(_)) {
                state.current = None;
            }

            return Some(route);
        }
    }

    // 2) Fallback: structural classification, same semantics as `step`
    let route = match current.clone() {
        Mu::Sym(_) => {
            state.ra.push(current.clone());
            RouteKind::Ra
        }
        Mu::Node(children) => {
            let all_same = children.iter().all(|c| c == children.first().unwrap());
            if all_same {
                state.lobes.push(Mu::Node(children));
                RouteKind::Lobe
            } else {
                state.sink.push(Mu::Node(children));
                RouteKind::Sink
            }
        }
    };

    state.log_event("classify_with_program(structural)", route, current);
    state.current = None;
    Some(route)
}

/// Run a program to quiescence on whatever is in `state.current`:
/// keep applying `classify_with_program` until nothing is left in-flight.
pub fn run_program(state: &mut RCXState, program: &RcxProgram) {
    loop {
        if state.current.is_none() {
            break;
        }
        let _ = classify_with_program(state, program);
    }
}
