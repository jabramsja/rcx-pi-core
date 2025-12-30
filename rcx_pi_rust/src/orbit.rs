use crate::matching::{Env, match_pattern, substitute_template};
use crate::types::{Mu, RcxProgram, RcxRule, RuleAction};

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
    let mut seq: Vec<Mu> = Vec::new();
    let mut current = seed.clone();

    // Always include the starting point.
    seq.push(current.clone());

    for _ in 0..max_steps {
        if let Some(next) = step_once(program, &current) {
            current = next;
            seq.push(current.clone());
        } else {
            break;
        }
    }

    seq
}

fn step_once(program: &RcxProgram, current: &Mu) -> Option<Mu> {
    for RcxRule { pattern, action } in &program.rules {
        if let RuleAction::Rewrite(template) = action {
            let mut env: Env = Env::new();
            if !match_pattern(pattern, current, &mut env) {
                continue;
            }
            let rewritten = substitute_template(template, &env);
            return Some(rewritten);
        }
    }
    None
}
