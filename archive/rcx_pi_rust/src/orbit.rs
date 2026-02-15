use crate::matching::{Env, match_pattern, substitute_template};
use crate::types::{Mu, RcxProgram, RcxRule, RuleAction};

/// Per-step provenance for a Rewrite transition inside an orbit run.
/// Additive + tool-facing: does not change rewrite semantics.
#[derive(Debug, Clone)]
pub struct RewriteProvenance {
    /// Step index in the orbit sequence (seed is i=0, first rewrite produces i=1).
    pub i: usize,
    /// Index into program.rules (0-based).
    pub rule_i: usize,
    /// Pattern that matched (as Mu).
    pub pattern: Mu,
    /// Rewrite template fired (as Mu).
    pub template: Mu,
    /// Variable bindings captured during matching. Empty if none.
    pub bindings: Vec<(String, Mu)>,
}

/// Compute the rewrite orbit for a seed under the program’s Rewrite rules.
///
/// Behavior:
///   • Only `RuleAction::Rewrite` rules are applied.
///   • At each step, we look for the *first* rewrite rule whose pattern matches
///     the current Mu (using pattern variables).
///   • If found, we substitute the template and continue.
///   • If no rule matches, we stop.
///
/// The returned Vec includes the seed as the first element.
pub fn orbit(program: &RcxProgram, seed: Mu, max_steps: usize) -> Vec<Mu> {
    orbit_with_provenance(program, seed, max_steps).0
}

/// Same as `orbit`, but also returns per-step rewrite provenance.
/// The provenance Vec has one entry per successful rewrite step (i = 1..).
pub fn orbit_with_provenance(
    program: &RcxProgram,
    seed: Mu,
    max_steps: usize,
) -> (Vec<Mu>, Vec<RewriteProvenance>) {
    let mut seq: Vec<Mu> = Vec::new();
    let mut prov: Vec<RewriteProvenance> = Vec::new();
    let mut current = seed.clone();

    // Always include the starting point.
    seq.push(current.clone());

    for step_i in 1..=max_steps {
        if let Some((next, p)) = step_once(program, &current, step_i) {
            current = next;
            seq.push(current.clone());
            prov.push(p);
        } else {
            break;
        }
    }

    (seq, prov)
}

fn step_once(program: &RcxProgram, current: &Mu, step_i: usize) -> Option<(Mu, RewriteProvenance)> {
    for (rule_i, RcxRule { pattern, action }) in program.rules.iter().enumerate() {
        if let RuleAction::Rewrite(template) = action {
            let mut env: Env = Env::new();
            if !match_pattern(pattern, current, &mut env) {
                continue;
            }

            let rewritten = substitute_template(template, &env);

            // Best-effort bindings capture: Env is expected to be map-like.
            let bindings: Vec<(String, Mu)> =
                env.iter().map(|(k, v)| (k.clone(), v.clone())).collect();

            let p = RewriteProvenance {
                i: step_i,
                rule_i,
                pattern: pattern.clone(),
                template: template.clone(),
                bindings,
            };

            return Some((rewritten, p));
        }
    }
    None
}
