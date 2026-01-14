use std::env;

use rcx_pi_rust::{
    mu_loader::load_mu_file,
    orbit_json::orbit_to_json,
    parser::parse_mu,
    types::{Mu, RcxProgram},
};

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage:");
        eprintln!("  cargo run --example orbit_json_cli -- <world> <Mu> [max_steps]");
        eprintln!();
        eprintln!("examples:");
        eprintln!("  cargo run --example orbit_json_cli -- pingpong ping 12");
        eprintln!("  cargo run --example orbit_json_cli -- rcx_core \"[omega,[a,b]]\" 16");
        std::process::exit(1);
    }

    let world_name = &args[1];
    let mu_src = &args[2];
    let max_steps: usize = if args.len() >= 4 {
        args[3].parse().unwrap_or(12)
    } else {
        12
    };

    let program: RcxProgram = match load_mu_file(world_name) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("[world] error loading {world_name}: {e}");
            std::process::exit(1);
        }
    };

    let seed: Mu = match parse_mu(mu_src) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("[ω] parse error for {mu_src}: {e}");
            std::process::exit(1);
        }
    };

    let json = orbit_to_json(&program, seed, max_steps);
    println!("{json}");
}
