use crate::{state::RCXState, types::Mu};

/// Perform one reduction step.
///
/// For now this is a structural demo:
/// - Whatever is in `current` is treated as the "result" of this step.
/// - The runtime will classify and route it into r_a / lobes / sink.
///
/// Later, this is where Δ (real rewrite rules) will live.
pub fn reduce_step(state: &mut RCXState) -> Option<Mu> {
    state.current.as_ref().cloned()
}
