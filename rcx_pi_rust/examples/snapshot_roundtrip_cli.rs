use rcx_pi_rust::{
    engine::Engine,
    engine_json::engine_run_to_json,
    mu_loader::load_mu_file,
    parser::parse_mu,
    snapshot_json::{snapshot_from_json, snapshot_to_json},
    state::RCXState,
    types::{Mu, RcxProgram},
};

fn main() {
    // Hard-coded small proof to avoid "cargo test" on macOS.
    // Phase A: run seeds, snapshot.
    let world = "rcx_core";
    let program: RcxProgram = load_mu_file(world).expect("load world");
    let seeds = vec!["[null,a]", "[inf,a]", "[paradox,a]", "[omega,[a,b]]"];
    let seeds_mu: Vec<Mu> = seeds.iter().map(|s| parse_mu(s).unwrap()).collect();

    let mut engine_a = Engine::new(program.clone());
    let mut state_a = RCXState::new();
    for mu in &seeds_mu {
        let _ = engine_a.process_input(&mut state_a, mu.clone());
    }
    let snap = snapshot_to_json(world, &program, &state_a);

    // Phase B: reload snapshot, then run one extra input.
    let (_w, program_b, mut state_b) = snapshot_from_json(world, &snap).expect("load snapshot");
    let mut engine_b = Engine::new(program_b.clone());

    let extra = parse_mu("[null,z]").unwrap();
    let _ = engine_b.process_input(&mut state_b, extra.clone());

    // Baseline: do the same without snapshotting.
    let mut engine_c = Engine::new(program.clone());
    let mut state_c = RCXState::new();
    for mu in &seeds_mu {
        let _ = engine_c.process_input(&mut state_c, mu.clone());
    }
    let _ = engine_c.process_input(&mut state_c, extra);

    // Compare full engine-run JSON (buckets + trace) after the same ops.
    let got = engine_run_to_json(world, &program_b, &[]); // not used for inputs; engine_run_to_json runs its own state, so instead compare buckets directly.
    let _ = got;

    if state_b.ra != state_c.ra || state_b.lobes != state_c.lobes || state_b.sink != state_c.sink {
        eprintln!("[FAIL] roundtrip mismatch:");
        eprintln!(
            "  after snapshot: ra={:?} lobes={:?} sink={:?}",
            state_b.ra, state_b.lobes, state_b.sink
        );
        eprintln!(
            "  baseline:       ra={:?} lobes={:?} sink={:?}",
            state_c.ra, state_c.lobes, state_c.sink
        );
        std::process::exit(1);
    }

    println!("[OK] snapshot roundtrip preserved buckets for rcx_core + extra input.");
}
