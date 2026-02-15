//! Replay CLI binary matching Python's `python -m rcx_pi.rcx_cli replay`.
//! Frozen semantics (v1) - bit-for-bit compatible with Python output.

use rcx_pi_rust::replay_cli;
use std::env;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let rc = replay_cli::replay_main(&args);
    std::process::exit(rc);
}
