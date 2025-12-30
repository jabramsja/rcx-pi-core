use rcx_pi_rust::{runtime::step, state::RCXState, types::Mu};

fn main() {
    // 1) Simple atom → r_a
    let mut state = RCXState::with_seed(Mu::Sym("ATOM".to_string()));
    println!("=== Phase 1: ATOM (should go to r_a) ===");
    step(&mut state);
    println!("{state:#?}");

    // 2) Coherent node → lobe
    //    Node of identical symbols is treated as "coherent but incomplete".
    state.current = Some(Mu::Node(vec![
        Mu::Sym("X".to_string()),
        Mu::Sym("X".to_string()),
        Mu::Sym("X".to_string()),
    ]));
    println!("\n=== Phase 2: Node[X, X, X] (should go to lobe) ===");
    step(&mut state);
    println!("{state:#?}");

    // 3) Conflicting node → sink
    //    Mixed symbols (X, Y) are treated as contradictory/tensional.
    state.current = Some(Mu::Node(vec![
        Mu::Sym("X".to_string()),
        Mu::Sym("Y".to_string()),
    ]));
    println!("\n=== Phase 3: Node[X, Y] (should go to sink) ===");
    step(&mut state);
    println!("{state:#?}");

    println!("\n=== Final summary ===");
    println!("r_a:   {:#?}", state.ra);
    println!("lobes: {:#?}", state.lobes);
    println!("sink:  {:#?}", state.sink);
}
