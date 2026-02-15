use rcx_pi_rust::{
    engine::Engine,
    state::RCXState,
    trace::RouteKind,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

fn main() {
    // A tiny non-empty program:
    //
    // 1. PING  → rewrite to PONG, and classify to r_a
    // 2. [U,U] → lobe (explicit rule)
    // 3. [U,V] → sink (explicit rule)
    //
    // Anything else falls back to structural routing.
    let program = RcxProgram {
        rules: vec![
            // PING → PONG (rewrite), then treat the result as stable (r_a)
            RcxRule {
                pattern: Mu::Sym("PING".into()),
                action: RuleAction::Rewrite(Mu::Sym("PONG".into())),
            },
            // Explicit lobe pattern
            RcxRule {
                pattern: Mu::Node(vec![Mu::Sym("U".into()), Mu::Sym("U".into())]),
                action: RuleAction::ToLobe,
            },
            // Explicit sink pattern
            RcxRule {
                pattern: Mu::Node(vec![Mu::Sym("U".into()), Mu::Sym("V".into())]),
                action: RuleAction::ToSink,
            },
        ],
    };

    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let inputs = vec![
        Mu::Sym("PING".to_string()),
        Mu::Node(vec![Mu::Sym("U".into()), Mu::Sym("U".into())]),
        Mu::Node(vec![Mu::Sym("U".into()), Mu::Sym("V".into())]),
        Mu::Node(vec![Mu::Sym("A".into()), Mu::Sym("B".into())]), // falls back to structural
    ];

    println!("=== Engine demo (RTM-style wrapper, with program) ===\n");

    for (i, mu) in inputs.into_iter().enumerate() {
        println!("--- Input {i}: {mu:#?} ---");

        let route: Option<RouteKind> = engine.process_input(&mut state, mu);
        println!("Route: {route:?}\n");
    }

    println!("=== Final engine state ===");
    println!("{state:#?}");
}
