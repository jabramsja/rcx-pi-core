use std::env;

use rcx_pi_rust::{
    engine::Engine,
    formatter::bucket_to_string,
    mu_loader::load_mu_file,
    parser::parse_mu,
    state::RCXState,
    types::{Mu, RcxProgram},
};

fn usage() {
    eprintln!("usage:");
    eprintln!("  cargo run --example classify_cli -- <world_name> <Mu> [<Mu> ...]");
    eprintln!();
    eprintln!("examples:");
    eprintln!("  cargo run --example classify_cli -- rcx_core [null,a] [inf,a] [paradox,a]");
    eprintln!("  cargo run --example classify_cli -- news [news,stable] [news,paradox]");
}

fn main() {
    let mut args = env::args().skip(1).collect::<Vec<String>>();

    if args.len() < 2 {
        usage();
        return;
    }

    // First arg: world name (e.g. "rcx_core", "news", "pingpong")
    let world_name = args.remove(0);

    // Load world from mu_programs/<world_name>.mu
    let program: RcxProgram = match load_mu_file(&world_name) {
        Ok(p) => {
            let display = if world_name.ends_with(".mu") {
                world_name.clone()
            } else {
                format!("{world_name}.mu")
            };
            println!("[world] loaded mu_programs/{display}");
            p
        }
        Err(e) => {
            eprintln!("[world] error loading {world_name}: {e}");
            return;
        }
    };

    // Initialize engine + fresh state
    let mut engine = Engine::new(program.clone());
    let mut state = RCXState::new();

    // Remaining args are Mu terms to classify
    println!();
    println!("[classify] {} input(s):", args.len());
    for src in &args {
        let mu: Mu = match parse_mu(src) {
            Ok(m) => m,
            Err(e) => {
                eprintln!("  [parse error] `{}`: {}", src, e);
                continue;
            }
        };

        let route = engine.process_input(&mut state, mu.clone());
        println!("  input: {:<16} → route: {:?}", src, route);
        println!("    r_a:   {}", bucket_to_string(&state.ra));
        println!("    lobes: {}", bucket_to_string(&state.lobes));
        println!("    sink:  {}", bucket_to_string(&state.sink));
    }
}
