use rcx_pi_rust::{
    engine::Engine, formatter::bucket_to_string, mu_loader::load_mu_file, parser::parse_mu,
    state::RCXState,
};

fn main() {
    // Load the core RCX world from mu_programs/rcx_core.mu
    let program = load_mu_file("rcx_core.mu").expect("failed to load rcx_core.mu");
    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let samples = [
        "[null,a]",
        "[inf,a]",
        "[paradox,a]",
        "[omega,[a,b]]",
        "[shadow,[a,b]]",
    ];

    println!("=== rcx_core demo ===");
    for s in &samples {
        let mu = parse_mu(s).expect("parse error in sample");
        let route = engine.process_input(&mut state, mu.clone());
        println!("input: {:<15} → route: {:?}", s, route);
        println!("  r_a:   {}", bucket_to_string(&state.ra));
        println!("  lobes: {}", bucket_to_string(&state.lobes));
        println!("  sink:  {}", bucket_to_string(&state.sink));
        println!();
    }
}
