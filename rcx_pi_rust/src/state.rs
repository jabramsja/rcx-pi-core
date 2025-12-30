// src/state.rs
use crate::trace::{RouteKind, TraceEvent};
use crate::types::Mu;

#[derive(Debug, Clone)]
pub struct RCXState {
    pub current: Option<Mu>,
    pub ra: Vec<Mu>,
    pub lobes: Vec<Mu>,
    pub sink: Vec<Mu>,
    pub null_reg: Vec<Mu>,
    pub inf_reg: Vec<Mu>,

    // Trace of what the engine did over time
    pub trace: Vec<TraceEvent>,
    pub step_counter: usize,
}

impl RCXState {
    pub fn new() -> Self {
        Self {
            current: None,
            ra: Vec::new(),
            lobes: Vec::new(),
            sink: Vec::new(),
            null_reg: Vec::new(),
            inf_reg: Vec::new(),
            trace: Vec::new(),
            step_counter: 0,
        }
    }

    pub fn with_seed(mu: Mu) -> Self {
        let mut s = Self::new();
        s.current = Some(mu);
        s
    }

    /// Log a trace event into this state.
    pub fn log_event(&mut self, phase: &str, route: RouteKind, payload: Mu) {
        self.step_counter += 1;
        self.trace.push(TraceEvent {
            step_index: self.step_counter,
            phase: phase.to_string(),
            route,
            payload,
        });
    }
}
