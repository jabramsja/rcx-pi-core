use rcx_pi_rust::{
    formatter::mu_to_string,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

/// Apply exactly one rewrite step if there is a matching Rewrite rule.
/// If no Rewrite rule matches, return None.
fn apply_rewrite_once(program: &RcxProgram, term: &Mu) -> Option<Mu> {
    for rule in &program.rules {
        if &rule.pattern == term {
            if let RuleAction::Rewrite(mu) = &rule.action {
                return Some(mu.clone());
            }
        }
    }
    None
}

/// Run an "orbit" of at most `max_steps` starting from `seed`,
/// using Rewrite rules only. We don't classify into r_a/lobes/sink here;
/// this is pure Mu → Mu rewriting.
///
/// Returns the full sequence: [seed, step1, step2, ..., final].
fn run_orbit(program: &RcxProgram, seed: Mu, max_steps: usize) -> Vec<Mu> {
    let mut seq = Vec::new();
    let mut current = seed;
    seq.push(current.clone());

    for _ in 0..max_steps {
        if let Some(next) = apply_rewrite_once(program, &current) {
            current = next;
            seq.push(current.clone());
        } else {
            // No more rewrites possible: we've hit a fixpoint / ω-limit candidate.
            break;
        }
    }

    seq
}

fn main() {
    // Tiny "ω-orbit" toy program:
    //
    //   X           -> rewrite([X,X])
    //   [X,X]       -> rewrite([X,X,X])
    //   [X,X,X]     -> rewrite(STABLE)
    //
    //   Y           -> (no rule) => orbit is just [Y]
    //
    // Semantics:
    //   - Some seeds spiral into a stable symbol STABLE
    //   - Others just sit there (no rewrite)
    let program = RcxProgram {
        rules: vec![
            // X -> [X,X]
            RcxRule {
                pattern: Mu::Sym("X".to_string()),
                action: RuleAction::Rewrite(Mu::Node(vec![
                    Mu::Sym("X".to_string()),
                    Mu::Sym("X".to_string()),
                ])),
            },
            // [X,X] -> [X,X,X]
            RcxRule {
                pattern: Mu::Node(vec![Mu::Sym("X".to_string()), Mu::Sym("X".to_string())]),
                action: RuleAction::Rewrite(Mu::Node(vec![
                    Mu::Sym("X".to_string()),
                    Mu::Sym("X".to_string()),
                    Mu::Sym("X".to_string()),
                ])),
            },
            // [X,X,X] -> STABLE
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("X".to_string()),
                    Mu::Sym("X".to_string()),
                    Mu::Sym("X".to_string()),
                ]),
                action: RuleAction::Rewrite(Mu::Sym("STABLE".to_string())),
            },
        ],
    };

    let seeds = vec![
        Mu::Sym("X".to_string()),
        Mu::Node(vec![Mu::Sym("X".to_string()), Mu::Sym("X".to_string())]),
        Mu::Sym("Y".to_string()),
    ];

    for (i, seed) in seeds.into_iter().enumerate() {
        println!("=== Orbit {i} from {} ===", mu_to_string(&seed));
        let orbit = run_orbit(&program, seed.clone(), 10);

        for (step, term) in orbit.iter().enumerate() {
            println!("  step {step}: {}", mu_to_string(term));
        }
        println!();
    }
}
