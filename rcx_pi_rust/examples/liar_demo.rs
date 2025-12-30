use rcx_pi_rust::{
    engine::Engine, mu_loader::load_mu_file, parser::parse_mu, state::RCXState, trace::RouteKind,
};

fn main() {
    // 1) Load the liar rewrite program
    let program = load_mu_file("liar_rewrite.mu").expect("failed to load liar_rewrite.mu");
    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    // 2) Seed: classic liar saying "TRUE"
    let mut current = parse_mu("[LIAR,SAYS_TRUE]").expect("parse seed [LIAR,SAYS_TRUE]");

    println!("=== Liar rewrite demo ===");

    // 3) Do a small finite number of steps so we can see the oscillation
    for step in 0..8 {
        println!("--- step {step} ---");
        println!("input mu: {:?}", current);

        let route = engine.process_input(&mut state, current.clone());
        println!("route: {:?}", route);
        println!("  r_a:   {:?}", state.ra);
        println!("  lobes: {:?}", state.lobes);
        println!("  sink:  {:?}", state.sink);
        println!();

        // Look for the *most recent* Rewrite event in the trace
        let next = state
            .trace
            .iter()
            .rev()
            .find(|evt| matches!(evt.route, RouteKind::Rewrite))
            .map(|evt| evt.payload.clone());

        match next {
            Some(mu) => {
                current = mu;
            }
            None => {
                println!("(no further rewrite; stopping)");
                break;
            }
        }
    }

    println!("=== Final trace ===");
    for evt in &state.trace {
        println!(
            "step {} | phase={} | route={:?} | payload={:?}",
            evt.step_index, evt.phase, evt.route, evt.payload
        );
    }
}
