use rcx_pi_rust::{
    formatter::mu_to_string,
    mu_loader::load_mu_file,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

/// Generate simple wildcard-based variants of a rule.
///
/// Strategy (conservative, easy to reason about):
/// - Only touch patterns of the form [sym, sym].
/// - Produce:
///     [sym,_] with same action
///     [_,sym] with same action
fn wildcard_variants(rule: &RcxRule) -> Vec<RcxRule> {
    let mut out = Vec::new();

    // Only mutate Node([a,b]) where both are Sym(...)
    if let Mu::Node(children) = &rule.pattern {
        if children.len() == 2 {
            if let (Mu::Sym(_a), Mu::Sym(_b)) = (&children[0], &children[1]) {
                // Variant 1: wildcard in slot 0 -> [_, b]
                let mut v1_children = children.clone();
                v1_children[0] = Mu::Sym("_".to_string());
                out.push(RcxRule {
                    pattern: Mu::Node(v1_children),
                    action: rule.action.clone(),
                });

                // Variant 2: wildcard in slot 1 -> [a, _]
                let mut v2_children = children.clone();
                v2_children[1] = Mu::Sym("_".to_string());
                out.push(RcxRule {
                    pattern: Mu::Node(v2_children),
                    action: rule.action.clone(),
                });
            }
        }
    }

    out
}

fn main() {
    println!("=== RCX-π mutation demo (wildcard variants) ===");

    // 1) Load a world (rcx_core by default).
    let program: RcxProgram = match load_mu_file("rcx_core") {
        Ok(p) => {
            println!("[world] loaded rcx_core.mu\n");
            p
        }
        Err(e) => {
            eprintln!("[world] error loading rcx_core: {e}");
            return;
        }
    };

    println!("[original rules]");
    for (idx, rule) in program.rules.iter().enumerate() {
        let pat = mu_to_string(&rule.pattern);
        let action = match &rule.action {
            RuleAction::ToRa => "ra".to_string(),
            RuleAction::ToLobe => "lobe".to_string(),
            RuleAction::ToSink => "sink".to_string(),
            RuleAction::Rewrite(mu) => format!("rewrite({})", mu_to_string(mu)),
        };
        println!("  {idx}: {pat} -> {action}");
    }

    println!("\n[proposed wildcard variants]");
    for (idx, rule) in program.rules.iter().enumerate() {
        let variants = wildcard_variants(rule);
        if variants.is_empty() {
            continue;
        }

        println!("  from rule {idx}: {}", mu_to_string(&rule.pattern));
        for (vidx, v) in variants.iter().enumerate() {
            let pat = mu_to_string(&v.pattern);
            let action = match &v.action {
                RuleAction::ToRa => "ra".to_string(),
                RuleAction::ToLobe => "lobe".to_string(),
                RuleAction::ToSink => "sink".to_string(),
                RuleAction::Rewrite(mu) => format!("rewrite({})", mu_to_string(mu)),
            };
            println!("    variant {vidx}: {pat} -> {action}");
        }
        println!();
    }

    println!("=== end mutation demo (no rules were changed) ===");
}
