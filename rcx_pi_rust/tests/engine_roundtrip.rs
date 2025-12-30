use rcx_pi_rust::{
    engine::Engine,
    parser::parse_mu,
    state::RCXState,
    trace::RouteKind,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

fn make_news_program() -> RcxProgram {
    RcxProgram {
        rules: vec![
            // [NEWS,STABLE] -> r_a
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("NEWS".to_string()),
                    Mu::Sym("STABLE".to_string()),
                ]),
                action: RuleAction::ToRa,
            },
            // [NEWS,UNSTABLE] -> lobe
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("NEWS".to_string()),
                    Mu::Sym("UNSTABLE".to_string()),
                ]),
                action: RuleAction::ToLobe,
            },
            // [NEWS,PARADOX] -> sink
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("NEWS".to_string()),
                    Mu::Sym("PARADOX".to_string()),
                ]),
                action: RuleAction::ToSink,
            },
        ],
    }
}

#[test]
fn news_program_routes_as_expected() {
    let program = make_news_program();
    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let stable = parse_mu("[NEWS,STABLE]").unwrap();
    let unstable = parse_mu("[NEWS,UNSTABLE]").unwrap();
    let paradox = parse_mu("[NEWS,PARADOX]").unwrap();
    let unknown = parse_mu("[NEWS,UNKNOWN]").unwrap();

    // STABLE → r_a
    let r1 = engine.process_input(&mut state, stable.clone());
    assert_eq!(r1, Some(RouteKind::Ra));
    assert_eq!(state.ra, vec![stable.clone()]);
    assert!(state.lobes.is_empty());
    assert!(state.sink.is_empty());

    // UNSTABLE → lobe
    let r2 = engine.process_input(&mut state, unstable.clone());
    assert_eq!(r2, Some(RouteKind::Lobe));
    assert_eq!(state.lobes, vec![unstable.clone()]);
    assert_eq!(state.ra, vec![stable.clone()]);
    assert!(state.sink.is_empty());

    // PARADOX → sink
    let r3 = engine.process_input(&mut state, paradox.clone());
    assert_eq!(r3, Some(RouteKind::Sink));
    assert_eq!(state.sink, vec![paradox.clone()]);
    assert_eq!(state.ra, vec![stable.clone()]);
    assert_eq!(state.lobes, vec![unstable.clone()]);

    // UNKNOWN → structural fallback (should go to Sink structurally)
    let r4 = engine.process_input(&mut state, unknown.clone());
    assert_eq!(r4, Some(RouteKind::Sink));
    assert_eq!(state.sink.len(), 2);
}

#[test]
fn rewrite_rule_pings_to_pong() {
    // PING → PONG (rewrite), then structurally RA
    let program = RcxProgram {
        rules: vec![RcxRule {
            pattern: Mu::Sym("PING".to_string()),
            action: RuleAction::Rewrite(Mu::Sym("PONG".to_string())),
        }],
    };

    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let ping = parse_mu("PING").unwrap();
    let route = engine.process_input(&mut state, ping);

    // After rewrite, structural classification makes PONG go to Ra.
    assert_eq!(route, Some(RouteKind::Ra));
    assert_eq!(state.ra, vec![Mu::Sym("PONG".to_string())]);
    assert!(state.lobes.is_empty());
    assert!(state.sink.is_empty());
}
