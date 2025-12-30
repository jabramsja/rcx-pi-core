use crate::types::Mu;

/// Simple structural pattern matching for Mu.
///
/// Conventions:
///   - Sym("_") is a wildcard that matches *any* Mu node.
///   - Sym("foo") matches only the symbol "foo".
///   - Node([...]) must match shape and recursively match children.
pub fn mu_matches(pattern: &Mu, value: &Mu) -> bool {
    match (pattern, value) {
        // Wildcard: "_" matches anything.
        (Mu::Sym(p), _) if p == "_" => true,

        // Symbol must match exactly.
        (Mu::Sym(p), Mu::Sym(v)) => p == v,

        // Node: must have same length, and each child must match.
        (Mu::Node(ps), Mu::Node(vs)) => {
            if ps.len() != vs.len() {
                return false;
            }
            ps.iter().zip(vs.iter()).all(|(pp, vv)| mu_matches(pp, vv))
        }

        // Anything else does not match.
        _ => false,
    }
}
