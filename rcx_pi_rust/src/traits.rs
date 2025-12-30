use crate::types::Mu;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Classification {
    Ra,
    Lobe,
    Sink,
}

/// Heuristic structural classifier:
/// 1. Tag overrides (if present)
///    - Node(head = "UNSTABLE", ...) → Lobe
///    - Node(head = "PARADOX",  ...) → Sink
/// 2. Structural defaults:
///    - Sym(_)                              → Ra (stable)
///    - Node with 0 or 1 child              → Lobe (incomplete / embryonic)
///    - Node where all children are same Sym→ Lobe (coherent cluster)
///    - Node with mixed or complex children → Sink (conflict / tension)
pub fn classify(mu: &Mu) -> Classification {
    // Tag overrides if first child is a Sym
    if let Mu::Node(children) = mu {
        if let Some(Mu::Sym(head)) = children.first() {
            match head.as_str() {
                "UNSTABLE" => return Classification::Lobe,
                "PARADOX" => return Classification::Sink,
                _ => {}
            }
        }
    }

    // Structural fallbacks
    match mu {
        Mu::Sym(_) => Classification::Ra,

        Mu::Node(children) => {
            match children.len() {
                0 | 1 => Classification::Lobe, // incomplete / embryonic
                _ => {
                    // Check if all children are Sym with same string
                    let mut sym_head: Option<&str> = None;
                    let mut all_syms = true;

                    for c in children {
                        match c {
                            Mu::Sym(s) => {
                                if let Some(h) = sym_head {
                                    if h != s {
                                        // conflicting symbols → sink
                                        return Classification::Sink;
                                    }
                                } else {
                                    sym_head = Some(s.as_str());
                                }
                            }
                            Mu::Node(_) => {
                                // mix of atoms and nodes → treat as paradox for now
                                all_syms = false;
                                break;
                            }
                        }
                    }

                    if all_syms {
                        // all children same Sym → coherent cluster → lobe
                        Classification::Lobe
                    } else {
                        Classification::Sink
                    }
                }
            }
        }
    }
}
