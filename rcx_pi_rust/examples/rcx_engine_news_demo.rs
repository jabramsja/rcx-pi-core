use rcx_pi_rust::{
    engine::Engine,
    state::RCXState,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

fn sym(s: &str) -> Mu {
    Mu::Sym(s.to_string())
}

/// Helper: build a simple NEWS-tagged node like [NEWS, STABLE]
fn news_node(tags: &[&str]) -> Mu {
    Mu::Node(tags.iter().map(|t| sym(t)).collect())
}

fn main() {
    // Tiny "RCXEngineNews" program:
    //
    //   [NEWS, STABLE]   → r_a      (fully integrated)
    //   [NEWS, UNSTABLE] → lobe     (held for later integration)
    //   [NEWS, PARADOX]  → sink     (contradiction / needs other context)
    //
    // Anything else falls back to the existing structural classifier.
    let program = RcxProgram {
        rules: vec![
            RcxRule {
                pattern: news_node(&["NEWS", "STABLE"]),
                action: RuleAction::ToRa,
            },
            RcxRule {
                pattern: news_node(&["NEWS", "UNSTABLE"]),
                action: RuleAction::ToLobe,
            },
            RcxRule {
                pattern: news_node(&["NEWS", "PARADOX"]),
                action: RuleAction::ToSink,
            },
        ],
    };

    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    // Four “headlines”:
    let inputs = vec![
        news_node(&["NEWS", "STABLE"]),
        news_node(&["NEWS", "UNSTABLE"]),
        news_node(&["NEWS", "PARADOX"]),
        news_node(&["NEWS", "UNKNOWN"]), // no explicit rule → fallback structural route
    ];

    println!("=== RCXEngineNews demo ===\n");

    for (i, mu) in inputs.into_iter().enumerate() {
        println!("--- Input {i}: {mu:#?} ---");
        let route = engine.process_input(&mut state, mu);
        println!("Route: {route:?}\n");
    }

    println!("=== Final state ===");
    println!("{state:#?}");
}
