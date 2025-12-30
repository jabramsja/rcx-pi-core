use std::fs;

use crate::formatter::mu_to_string;
use crate::types::{RcxProgram, RcxRule, RuleAction};

/// Escape a Rust string so it is safe inside a JSON string literal.
fn escape_json_string(s: &str) -> String {
    let mut out = String::new();
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(c),
        }
    }
    out
}

/// Export the current program (rules only) to `worlds_json/<name>.json`.
///
/// JSON shape:
/// {
///   "rules": [
///     {
///       "pattern": "<mu-as-text>",
///       "action": "ra" | "lobe" | "sink" | "rewrite",
///       "rewrite": "<mu-as-text>"   // only for rewrite rules
///     },
///     ...
///   ]
/// }
pub fn export_world_json(name: &str, program: &RcxProgram) -> Result<String, String> {
    // Ensure directory exists
    fs::create_dir_all("worlds_json").map_err(|e| e.to_string())?;
    let path = format!("worlds_json/{}.json", name);

    let mut out = String::new();
    out.push_str("{\n  \"rules\": [\n");

    for (i, RcxRule { pattern, action }) in program.rules.iter().enumerate() {
        if i > 0 {
            out.push_str(",\n");
        }

        let pat_str = escape_json_string(&mu_to_string(pattern));

        let (action_str, rewrite_str_opt) = match action {
            RuleAction::ToRa => ("ra", None),
            RuleAction::ToLobe => ("lobe", None),
            RuleAction::ToSink => ("sink", None),
            RuleAction::Rewrite(mu) => {
                let rw = escape_json_string(&mu_to_string(mu));
                ("rewrite", Some(rw))
            }
        };

        out.push_str("    {\n");
        out.push_str(&format!("      \"pattern\": \"{}\",\n", pat_str));
        out.push_str(&format!("      \"action\": \"{}\"", action_str));

        if let Some(rw) = rewrite_str_opt {
            out.push_str(&format!(",\n      \"rewrite\": \"{}\"", rw));
        }

        out.push_str("\n    }");
    }

    out.push_str("\n  ]\n}\n");

    fs::write(&path, out).map_err(|e| e.to_string())?;

    Ok(path)
}
