use std::collections::HashMap;

use crate::types::Mu;

/// Simple environment: variable name → bound Mu
pub type Env = HashMap<String, Mu>;

/// Our convention:
///   • A symbol is a *pattern variable* iff it is a single lowercase ASCII letter,
///     e.g. "x", "y", "z".
///   • Everything else ("ping", "pong", "news", "stable", "A", "LIAR") is a concrete symbol.
fn is_var(name: &str) -> bool {
    name.len() == 1 && name.chars().next().unwrap_or(' ').is_ascii_lowercase()
}

/// Try to match `pattern` against `term`, filling `env` as we go.
/// Returns true on successful match.
///
/// Rules:
///   • Variable (e.g. x) matches anything. If already bound, it must match the same Mu again.
///   • Concrete symbol matches only identical concrete symbol.
///   • Node([...]) matches Node([...]) elementwise.
pub fn match_pattern(pattern: &Mu, term: &Mu, env: &mut Env) -> bool {
    match pattern {
        // Variable case: single lowercase letter
        Mu::Sym(name) if is_var(name) => {
            if let Some(bound) = env.get(name) {
                // Variable seen before: must match previous binding
                bound == term
            } else {
                // First time we see this variable: bind it
                env.insert(name.clone(), term.clone());
                true
            }
        }

        // Concrete symbol: must match exactly
        Mu::Sym(name) => match term {
            Mu::Sym(other) => other == name,
            _ => false,
        },

        // Node pattern: nodes must have same arity, then match children pairwise
        Mu::Node(p_children) => match term {
            Mu::Node(t_children) => {
                if p_children.len() != t_children.len() {
                    return false;
                }
                for (p, t) in p_children.iter().zip(t_children.iter()) {
                    if !match_pattern(p, t, env) {
                        return false;
                    }
                }
                true
            }
            _ => false,
        },
    }
}

/// Substitute variables inside `template` using `env`.
/// Any unbound variable is left as-is (defensive default).
pub fn substitute_template(template: &Mu, env: &Env) -> Mu {
    match template {
        Mu::Sym(name) if is_var(name) => env
            .get(name)
            .cloned()
            .unwrap_or_else(|| Mu::Sym(name.clone())),
        Mu::Sym(name) => Mu::Sym(name.clone()),
        Mu::Node(children) => Mu::Node(
            children
                .iter()
                .map(|c| substitute_template(c, env))
                .collect(),
        ),
    }
}
