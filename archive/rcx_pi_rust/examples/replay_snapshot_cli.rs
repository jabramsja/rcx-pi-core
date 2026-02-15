use std::env;
use std::fs;

use rcx_pi_rust::{
    engine_json::engine_run_from_state_to_json, parser::parse_mu,
    snapshot_json::snapshot_from_json, types::Mu,
};

fn usage() -> ! {
    eprintln!("usage: replay_snapshot_cli <snapshot_json_path> <world_name> [mu ...]");
    eprintln!("example:");
    eprintln!(
        "  replay_snapshot_cli ../docs/fixtures/snapshot_rcx_core_v1.json rcx_core \"[omega,[a,b]]\""
    );
    std::process::exit(2);
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        usage();
    }

    let snapshot_path = &args[1];
    let world_name = &args[2];
    let mu_srcs: Vec<String> = args[3..].to_vec();

    let json = fs::read_to_string(snapshot_path)
        .unwrap_or_else(|e| panic!("read {}: {}", snapshot_path, e));

    let (_world_echo, program, mut state) =
        snapshot_from_json(world_name, &json).unwrap_or_else(|e| panic!("snapshot_from_json: {e}"));

    let mut inputs: Vec<Mu> = Vec::new();
    for s in mu_srcs {
        inputs.push(parse_mu(&s).unwrap_or_else(|e| panic!("parse_mu `{}`: {}", s, e)));
    }

    let out = engine_run_from_state_to_json(world_name, &program, &mut state, &inputs);
    print!("{}", out);
}
