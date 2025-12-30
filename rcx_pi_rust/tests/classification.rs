use rcx_pi_rust::{runtime::step, state::RCXState, types::Mu};

#[test]
fn atom_goes_to_ra() {
    let mut state = RCXState::with_seed(Mu::Sym("ATOM".into()));
    step(&mut state);

    assert_eq!(state.ra.len(), 1);
    assert!(matches!(state.ra[0], Mu::Sym(ref s) if s == "ATOM"));
    assert!(state.lobes.is_empty());
    assert!(state.sink.is_empty());
}

#[test]
fn coherent_node_goes_to_lobe() {
    let mut state = RCXState::with_seed(Mu::Node(vec![
        Mu::Sym("X".into()),
        Mu::Sym("X".into()),
        Mu::Sym("X".into()),
    ]));
    step(&mut state);

    assert!(state.ra.is_empty());
    assert_eq!(state.lobes.len(), 1);
    assert!(state.sink.is_empty());
}

#[test]
fn conflicting_node_goes_to_sink() {
    let mut state = RCXState::with_seed(Mu::Node(vec![Mu::Sym("X".into()), Mu::Sym("Y".into())]));
    step(&mut state);

    assert!(state.ra.is_empty());
    assert!(state.lobes.is_empty());
    assert_eq!(state.sink.len(), 1);
}
