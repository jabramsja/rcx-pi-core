use std::env;

use rcx_pi_rust::{
    formatter::mu_to_string,
    mu_loader::load_mu_file,
    orbit::orbit,
    parser::parse_mu,
    types::{Mu, RcxProgram},
};

/// Classify an orbit sequence into a simple ω-limit description.
/// This is a copy of the REPL's local classifier, but made standalone for the CLI.
fn classify_orbit(seq: &[Mu]) -> String {
    if seq.is_empty() {
        return "empty orbit (no states produced)".to_string();
    }
    if seq.len() == 1 {
        return "no detected cycle up to 1 steps".to_string();
    }

    // 1) Try "pure cycle from the seed" detection.
    let seed = &seq[0];
    let mut found_period: Option<usize> = None;

    for i in 1..seq.len() {
        if &seq[i] == seed {
            found_period = Some(i);
            break;
        }
    }

    if let Some(period) = found_period {
        // Verify that the whole sequence respects this period.
        let mut pure = true;
        for (idx, mu) in seq.iter().enumerate() {
            if mu != &seq[idx % period] {
                pure = false;
                break;
            }
        }

        if pure {
            if period == 1 {
                return "fixed point".to_string();
            } else {
                return format!("pure limit cycle (period = {period})");
            }
        }
    }

    // 2) Fallback: transient + cycle detection using last state (your current logic, but with rposition).
    let last = &seq[seq.len() - 1];

    if let Some(prev_idx) = seq[..seq.len() - 1].iter().rposition(|m| m == last) {
        let transient_len = prev_idx;
        let period = seq.len() - 1 - prev_idx;

        if period == 1 {
            if transient_len == 0 {
                "fixed point".to_string()
            } else {
                format!("transient of length {transient_len} then fixed point")
            }
        } else if transient_len == 0 {
            format!("pure limit cycle (period = {period})")
        } else {
            format!("transient of length {transient_len} then limit cycle (period = {period})")
        }
    } else {
        format!("no detected cycle up to {} steps", seq.len())
    }
}
fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage:");
        eprintln!("  cargo run --example orbit_cli -- <world> <Mu> [max_steps]");
        eprintln!();
        eprintln!("examples:");
        eprintln!("  cargo run --example orbit_cli -- pingpong ping 12");
        eprintln!("  cargo run --example orbit_cli -- rcx_core \"[omega,[a,b]]\" 16");
        std::process::exit(1);
    }

    let world_name = &args[1];
    let mu_src = &args[2];
    let max_steps: usize = if args.len() >= 4 {
        args[3].parse().unwrap_or(12)
    } else {
        12
    };

    // 1) Load world
    let program: RcxProgram = match load_mu_file(world_name) {
        Ok(p) => {
            let display_name = if world_name.ends_with(".mu") {
                world_name.to_string()
            } else {
                format!("{world_name}.mu")
            };
            println!("[world] loaded mu_programs/{}", display_name);
            p
        }
        Err(e) => {
            eprintln!("[world] error loading {world_name}: {e}");
            std::process::exit(1);
        }
    };

    // 2) Parse seed Mu
    let seed: Mu = match parse_mu(mu_src) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("[ω] parse error for {mu_src}: {e}");
            std::process::exit(1);
        }
    };

    // 3) Compute orbit under rewrite rules of this world
    let seq = orbit(&program, seed.clone(), max_steps);

    println!();
    println!("[ω] seed: {}", mu_to_string(&seed));
    println!("[ω] max steps: {}", max_steps);
    println!("[ω] orbit ({} states):", seq.len());
    for (i, m) in seq.iter().enumerate() {
        println!("  {:>3}: {}", i, mu_to_string(m));
    }

    let classification = classify_orbit(&seq);
    println!();
    println!("[ω] classification: {}", classification);
}
