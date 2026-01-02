use rcx_pi_rust::{
    engine::Engine,
    formatter::bucket_to_string,
    mu_loader::load_mu_file,
    parser::parse_mu,
    state::RCXState,
    types::{Mu, RcxProgram, RuleAction},
};

fn classify_seeds(label: &str, program: &RcxProgram, seeds_src: &[&str]) {
    println!("\n=== {label} world classification ===");

    let mut engine = Engine::new(program.clone());
    let mut state = RCXState::new();

    for src in seeds_src {
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
}

fn make_mutant(program: &RcxProgram) -> RcxProgram {
    let mut mutant = program.clone();

    // Simple mutation: change [omega,_] from whatever it is now → ra
    for rule in &mut mutant.rules {
        if let Mu::Node(children) = &rule.pattern {
            if children.len() == 2 {
                if let Mu::Sym(tag) = &children[0] {
                    if tag == "omega" {
                        println!("\n[mutate] changing rule `[omega,_]` action to ra");
                        rule.action = RuleAction::ToRa;
                    }
                }
            }
        }
    }

    mutant
}

fn main() {
    println!("=== RCX-π apply-mutation demo ===");

    let base_program: RcxProgram = match load_mu_file("rcx_core") {
        Ok(p) => {
            println!("[world] loaded rcx_core.mu");
            p
        }
        Err(e) => {
            eprintln!("[world] error loading rcx_core: {e}");
            return;
        }
    };

    let seeds = ["[null,a]", "[inf,a]", "[paradox,a]", "[omega,[a,b]]"];

    // 1) Classify under the base world
    classify_seeds("base (rcx_core)", &base_program, &seeds);

    // 2) Build a mutated world where [omega,_] routes to ra
    let mutant_program = make_mutant(&base_program);

    // 3) Classify the same seeds under the mutant
    classify_seeds("mutant (omega→ra)", &mutant_program, &seeds);

    println!("\n=== done ===");
}
