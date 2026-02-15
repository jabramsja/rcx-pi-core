use std::env;

use rcx_pi_rust::{
    engine_json::{engine_run_to_json, parse_inputs},
    mu_loader::load_mu_file,
    types::RcxProgram,
};

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage:");
        eprintln!("  cargo run --example engine_json_cli -- <world> <Mu1> [Mu2 ...]");
        eprintln!();
        eprintln!("examples:");
        eprintln!(
            "  cargo run --example engine_json_cli -- rcx_core \"[null,a]\" \"[inf,a]\" \"[paradox,a]\""
        );
        eprintln!("  cargo run --example engine_json_cli -- pingpong ping ping ping");
        std::process::exit(1);
    }

    let world_name = &args[1];
    let mu_srcs: Vec<String> = args[2..].to_vec();

    let program: RcxProgram = match load_mu_file(world_name) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("[world] error loading {world_name}: {e}");
            std::process::exit(1);
        }
    };

    let inputs = match parse_inputs(&mu_srcs) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("[inputs] {e}");
            std::process::exit(1);
        }
    };

    let json = engine_run_to_json(world_name, &program, &inputs);
    println!("{json}");
}
