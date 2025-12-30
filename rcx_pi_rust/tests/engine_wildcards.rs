#![cfg(not(target_os = "macos"))]
use rcx_pi_rust::{
    engine::Engine,
    state::RCXState,
    trace::RouteKind,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

fn node2(a: &str, b: &str) -> Mu {
    Mu::Node(vec![Mu::Sym(a.to_string()), Mu::Sym(b.to_string())])
}

#[test]
fn wildcard_news_sends_any_payload_to_sink() {
    // [news,_] -> sink
    let program = RcxProgram {
        rules: vec![RcxRule {
            pattern: node2("news", "_"),
            action: RuleAction::ToSink,
        }],
    };

    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let input = node2("news", "stable");
    let route = engine.process_input(&mut state, input.clone());

    assert!(matches!(route, Some(RouteKind::Sink)));
    assert_eq!(state.sink.len(), 1);
    assert_eq!(state.ra.len(), 0);
    assert_eq!(state.lobes.len(), 0);
}

#[test]
fn wildcard_omega_matches_nested_payloads() {
    // [omega,_] -> lobe
    let program = RcxProgram {
        rules: vec![RcxRule {
            pattern: node2("omega", "_"),
            action: RuleAction::ToLobe,
        }],
    };

    let mut engine = Engine::new(program);
    let mut state = RCXState::new();

    let input = Mu::Node(vec![
        Mu::Sym("omega".to_string()),
        Mu::Node(vec![Mu::Sym("a".into()), Mu::Sym("b".into())]),
    ]);

    let route = engine.process_input(&mut state, input.clone());

    assert!(matches!(route, Some(RouteKind::Lobe)));
    assert_eq!(state.lobes.len(), 1);
    assert_eq!(state.ra.len(), 0);
    assert_eq!(state.sink.len(), 0);
}
