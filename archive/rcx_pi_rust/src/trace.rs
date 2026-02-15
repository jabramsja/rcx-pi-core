use crate::types::Mu;

/// Where did a Mu end up?
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RouteKind {
    Ra,
    Lobe,
    Sink,
    Rewrite,
    Structural,
}

/// Single log entry of “what just happened”
#[derive(Debug, Clone)]
pub struct TraceEvent {
    pub step_index: usize,
    pub phase: String,
    pub route: RouteKind,
    pub payload: Mu,
}

/// Helper: append a trace event to the state’s log.
pub fn log_event(state: &mut crate::state::RCXState, phase: &str, route: RouteKind, payload: Mu) {
    state.step_counter += 1;
    let idx = state.step_counter;

    state.trace.push(TraceEvent {
        step_index: idx,
        phase: phase.to_string(),
        route,
        payload,
    });
}
