use std::env;

use rcx_pi_rust::{
    engine::Engine,
    mu_loader::load_mu_file,
    parser::parse_mu,
    snapshot_json::snapshot_to_json,
    state::RCXState,
    types::{Mu, RcxProgram},
};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("usage:");
        eprintln!("  cargo run --example snapshot_json_cli -- <world> <Mu1> [Mu2 ...]");
        std::process::exit(1);
    }

    let world = &args[1];
    let mu_srcs: Vec<String> = args[2..].to_vec();

    let program: RcxProgram = match load_mu_file(world) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("[world] error loading {world}: {e}");
            std::process::exit(1);
        }
    };

    let mut engine = Engine::new(program.clone());
    let mut state = RCXState::new();

    for s in mu_srcs {
        let mu: Mu = parse_mu(&s).unwrap_or_else(|e| {
            eprintln!("[parse] {s}: {e}");
            std::process::exit(1);
        });
        let _ = engine.process_input(&mut state, mu);
    }

    let json = snapshot_to_json(world, &program, &state);
    println!("{json}");
}
