use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

use crate::formatter::mu_to_string;
use crate::parser::parse_mu;
use crate::types::{Mu, RcxProgram, RcxRule, RuleAction};

/// Normalize a world filename into a concrete path under `mu_programs/`.
///
/// Accepts things like:
///   - "rcx_core"
///   - "rcx_core.mu"
///   - "mu_programs/rcx_core.mu"
fn normalize_world_path(name: &str) -> PathBuf {
    let p = Path::new(name);

    // If it already has a directory component, respect it as-is.
    if p.components().count() > 1 {
        return p.to_path_buf();
    }

    // Bare name: add ".mu" if missing.
    let fname = if name.ends_with(".mu") {
        name.to_string()
    } else {
        format!("{name}.mu")
    };

    Path::new("mu_programs").join(fname)
}

/// Load a `.mu` program file into an RcxProgram.
///
/// Lines look like:
///   [null,_]    -> ra
///   [inf,_]     -> lobe
///   [paradox,_] -> sink
///   PING        -> rewrite(PONG)
///   [PING,PING] -> rewrite([PONG,PING])
pub fn load_mu_file(name: &str) -> Result<RcxProgram, String> {
    let path = {
        let p = Path::new(name);
        if p.exists() {
            p.to_path_buf()
        } else {
            normalize_world_path(name)
        }
    };

    let file = File::open(&path).map_err(|e| format!("open {}: {e}", path.display()))?;
    let reader = BufReader::new(file);

    let mut rules: Vec<RcxRule> = Vec::new();

    for line_res in reader.lines() {
        let raw = line_res.map_err(|e| format!("read {}: {e}", path.display()))?;
        let line = raw.trim();

        // skip empty / comment lines
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        let parts: Vec<&str> = line.split("->").collect();
        if parts.len() != 2 {
            return Err(format!(
                "parse {}: expected `lhs -> rhs`, got `{}`",
                path.display(),
                line
            ));
        }

        let pattern_src = parts[0].trim();
        let target_src = parts[1].trim();

        // left side is always a Mu pattern
        let pattern: Mu = parse_mu(pattern_src)
            .map_err(|e| format!("parse pattern in {}: {e}", path.display()))?;

        // right side can be:
        //   ra | lobe | sink | rewrite(<Mu>)
        let action: RuleAction = if target_src.eq_ignore_ascii_case("ra") {
            RuleAction::ToRa
        } else if target_src.eq_ignore_ascii_case("lobe") {
            RuleAction::ToLobe
        } else if target_src.eq_ignore_ascii_case("sink") {
            RuleAction::ToSink
        } else if target_src.to_lowercase().starts_with("rewrite") {
            // Expect rewrite(<Mu>)
            let maybe_arg = target_src
                .split_once('(')
                .and_then(|(_, rest)| rest.strip_suffix(')'));

            let arg_src = maybe_arg.ok_or_else(|| {
                format!(
                    "parse {}: expected `rewrite(<Mu>)`, got `{}`",
                    path.display(),
                    target_src
                )
            })?;

            let mu = parse_mu(arg_src.trim())
                .map_err(|e| format!("parse rewrite payload in {}: {e}", path.display()))?;

            RuleAction::Rewrite(mu)
        } else {
            return Err(format!(
                "parse {}: unknown target `{}` (expected ra|lobe|sink|rewrite(...))",
                path.display(),
                target_src
            ));
        };

        rules.push(RcxRule { pattern, action });
    }

    Ok(RcxProgram { rules })
}

/// Save the current program into `mu_programs/NAME.mu`.
///
/// Returns the normalized filename (e.g. "test_w.mu") on success.
pub fn save_mu_file(name: &str, program: &RcxProgram) -> Result<String, String> {
    // Ensure directory exists.
    let dir = Path::new("mu_programs");
    if !dir.exists() {
        std::fs::create_dir_all(dir).map_err(|e| format!("create mu_programs: {e}"))?;
    }

    // Normalize name to "<name>.mu".
    let fname = if name.ends_with(".mu") {
        name.to_string()
    } else {
        format!("{name}.mu")
    };

    let path = dir.join(&fname);
    let mut file = File::create(&path).map_err(|e| format!("create {}: {e}", path.display()))?;

    for rule in &program.rules {
        let lhs = mu_to_string(&rule.pattern);
        let rhs = match &rule.action {
            RuleAction::ToRa => "ra".to_string(),
            RuleAction::ToLobe => "lobe".to_string(),
            RuleAction::ToSink => "sink".to_string(),
            RuleAction::Rewrite(mu) => format!("rewrite({})", mu_to_string(mu)),
        };

        writeln!(file, "{} -> {}", lhs, rhs)
            .map_err(|e| format!("write {}: {e}", path.display()))?;
    }

    Ok(fname)
}
