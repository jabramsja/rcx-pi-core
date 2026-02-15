// src/unify.rs
use std::collections::HashMap;

use crate::types::Mu;

/// Substitution: maps variable names → Mu terms.
pub type Subst = HashMap<String, Mu>;

/// Convention:
///   - `_` is a wildcard (matches anything, no binding)
///   - Variables are symbols whose first char is ASCII uppercase (A–Z),
///     e.g. `X`, `Y`, `Pair`, etc.
///   - Everything else is a literal symbol.
fn is_var(name: &str) -> bool {
    name.chars()
        .next()
        .map(|c| c.is_ascii_uppercase())
        .unwrap_or(false)
}

/// Public entry: try to unify `pattern` with `value`.
/// Returns a substitution if successful, or None if they don't match.
pub fn unify(pattern: &Mu, value: &Mu) -> Option<Subst> {
    let mut subst = Subst::new();
    if unify_with(&mut subst, pattern, value) {
        Some(subst)
    } else {
        None
    }
}

fn unify_with(subst: &mut Subst, pattern: &Mu, value: &Mu) -> bool {
    match pattern {
        // `_` wildcard: matches anything, no binding.
        Mu::Sym(name) if name == "_" => true,

        // Variable: uppercase-leading symbol, binds or checks consistent binding.
        Mu::Sym(name) if is_var(name) => {
            if let Some(bound) = subst.get(name) {
                bound == value
            } else {
                subst.insert(name.clone(), value.clone());
                true
            }
        }

        // Non-variable symbol: must match exactly.
        Mu::Sym(name) => match value {
            Mu::Sym(v) => name == v,
            _ => false,
        },

        // Node: lengths must match; unify elementwise.
        Mu::Node(p_children) => match value {
            Mu::Node(v_children) => {
                if p_children.len() != v_children.len() {
                    return false;
                }
                for (p, v) in p_children.iter().zip(v_children.iter()) {
                    if !unify_with(subst, p, v) {
                        return false;
                    }
                }
                true
            }
            _ => false,
        },
    }
}

/// Apply a substitution to a template Mu:
///   - Variables replaced with their bound Mu if present
///   - `_` left as literal `_` (only special in patterns)
pub fn apply_subst(template: &Mu, subst: &Subst) -> Mu {
    match template {
        Mu::Sym(name) if name == "_" => Mu::Sym(name.clone()),
        Mu::Sym(name) if is_var(name) => subst
            .get(name)
            .cloned()
            .unwrap_or_else(|| Mu::Sym(name.clone())),
        Mu::Sym(name) => Mu::Sym(name.clone()),
        Mu::Node(children) => Mu::Node(children.iter().map(|c| apply_subst(c, subst)).collect()),
    }
}
