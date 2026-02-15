use rcx_pi_rust::{
    engine::Engine,
    formatter::{bucket_to_string, mu_to_string},
    mu_loader::load_mu_file,
    parser::parse_mu,
    serialize::{load_state, save_state},
    state::RCXState,
    types::{Mu, RcxProgram},
};

fn main() {
    println!("=== RCX-π state snapshot demo ===");

    // 1) Load the rcx_core world (null / inf / paradox / shadow / omega routing)
    let mut program: RcxProgram = match load_mu_file("rcx_core") {
        Ok(p) => {
            println!("[world] loaded rcx_core.mu");
            p
        }
        Err(e) => {
            eprintln!("[world] error loading rcx_core: {e}");
            return;
        }
    };

    let mut engine = Engine::new(program.clone());
    let mut state = RCXState::new();

    // 2) Feed a small sequence of Mu terms
    let seeds_src = vec!["[null,a]", "[inf,a]", "[paradox,a]", "[omega,[a,b]]"];

    println!("\n[phase 1] classify seeds under rcx_core:");
    for src in &seeds_src {
        let mu: Mu = match parse_mu(src) {
            Ok(m) => m,
            Err(e) => {
                eprintln!("  parse error for {src}: {e}");
                continue;
            }
        };

        let route = engine.process_input(&mut state, mu.clone());
        println!("  input: {:<14} → route: {:?}", src, route);
        println!("    r_a:   {}", bucket_to_string(&state.ra));
        println!("    lobes: {}", bucket_to_string(&state.lobes));
        println!("    sink:  {}", bucket_to_string(&state.sink));
    }

    // 3) Save a snapshot of rules + buckets
    if let Err(e) = std::fs::create_dir_all("snapshots") {
        eprintln!("\n[save-state] could not create snapshots/ dir: {e}");
        return;
    }

    let path = "snapshots/state_demo.state";
    match save_state(path, &state, &program) {
        Ok(()) => {
            println!(
                "\n[save-state] wrote snapshot to {} (rules: {}, r_a: {}, lobes: {}, sink: {})",
                path,
                program.rules.len(),
                state.ra.len(),
                state.lobes.len(),
                state.sink.len()
            );
        }
        Err(e) => {
            eprintln!("[save-state] error: {e}");
            return;
        }
    }

    // 4) Wipe everything to prove restore actually does something
    state = RCXState::new();
    program = RcxProgram { rules: vec![] };

    println!("\n[phase 2] after wipe:");
    println!("  rules: {}", program.rules.len());
    println!("  r_a:   {}", bucket_to_string(&state.ra));
    println!("  lobes: {}", bucket_to_string(&state.lobes));
    println!("  sink:  {}", bucket_to_string(&state.sink));

    // 5) Restore from snapshot
    match load_state(path) {
        Ok((restored_state, restored_program)) => {
            state = restored_state;
            program = restored_program;
            engine = Engine::new(program.clone());

            println!("\n[phase 3] after restore from {}:", path);
            println!("  rules: {}", program.rules.len());
            println!("  r_a:   {}", bucket_to_string(&state.ra));
            println!("  lobes: {}", bucket_to_string(&state.lobes));
            println!("  sink:  {}", bucket_to_string(&state.sink));
        }
        Err(e) => {
            eprintln!("[load-state] error: {e}");
            return;
        }
    }

    // 6) Optional sanity check: classify one more term after restore
    let extra = "[null,z]";
    let mu_extra = match parse_mu(extra) {
        Ok(m) => m,
        Err(e) => {
            eprintln!("[extra] parse error for {extra}: {e}");
            return;
        }
    };

    println!("\n[phase 4] extra classification after restore:");
    let route = engine.process_input(&mut state, mu_extra.clone());
    println!("  input: {} → route: {:?}", mu_to_string(&mu_extra), route);
    println!("  r_a:   {}", bucket_to_string(&state.ra));
    println!("  lobes: {}", bucket_to_string(&state.lobes));
    println!("  sink:  {}", bucket_to_string(&state.sink));

    println!("\n=== done ===");
}
