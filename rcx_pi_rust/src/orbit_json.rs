use crate::formatter::mu_to_string;
use crate::orbit::orbit_with_provenance;
use crate::schemas::ORBIT_SCHEMA_V1;
use crate::types::{Mu, RcxProgram};

/// Classify an orbit sequence into a simple ω-limit description.
/// Mirrors the logic used in examples/orbit_cli.rs and examples/repl.rs.
fn classify_orbit(seq: &[Mu]) -> String {
    if seq.is_empty() {
        return "empty orbit (no states produced)".to_string();
    }
    if seq.len() == 1 {
        return "no detected cycle up to 1 steps".to_string();
    }

    // 1) Try "pure cycle from the seed" detection.
    let seed = &seq[0];
    let mut found_period: Option<usize> = None;

    for i in 1..seq.len() {
        if &seq[i] == seed {
            found_period = Some(i);
            break;
        }
    }

    if let Some(period) = found_period {
        let mut pure = true;
        for (idx, mu) in seq.iter().enumerate() {
            if mu != &seq[idx % period] {
                pure = false;
                break;
            }
        }

        if pure {
            if period == 1 {
                return "fixed point".to_string();
            } else {
                return format!("pure limit cycle (period = {period})");
            }
        }
    }

    // 2) Fallback: transient + cycle detection using last state.
    let last = &seq[seq.len() - 1];

    if let Some(prev_idx) = seq[..seq.len() - 1].iter().rposition(|m| m == last) {
        let transient_len = prev_idx;
        let period = seq.len() - 1 - prev_idx;

        if period == 1 {
            if transient_len == 0 {
                "fixed point".to_string()
            } else {
                format!("transient of length {transient_len} then fixed point")
            }
        } else if transient_len == 0 {
            format!("pure limit cycle (period = {period})")
        } else {
            format!("transient of length {transient_len} then limit cycle (period = {period})")
        }
    } else {
        format!("no detected cycle up to {} steps", seq.len())
    }
}

/// Produce a JSON string describing an orbit run.
/// Output schema (stable v1; additive optional fields allowed):
///
/// {
///   "schema": "rcx.orbit.v1",
///   "seed": "<Mu>",
///   "max_steps": N,
///   "states": [ { "i": 0, "mu": "<Mu>" }, ... ],
///   "provenance": [ { "i": 1, "rule_i": 0, "pattern": "<Mu>", "template": "<Mu>", "bindings": { ... } }, ... ],
///   "classification": "<string>"
/// }
pub fn orbit_to_json(program: &RcxProgram, seed: Mu, max_steps: usize) -> String {
    let (seq, prov) = orbit_with_provenance(program, seed.clone(), max_steps);
    let classification = classify_orbit(&seq);

    let mut out = String::new();
    out.push('{');

    out.push_str(&format!(r#""schema":{},"#, json_escape(ORBIT_SCHEMA_V1)));
    out.push_str(&format!(r#""seed":{},"#, json_escape(&mu_to_string(&seed))));
    out.push_str(&format!(r#""max_steps":{},"#, max_steps));

    // states
    out.push_str(r#""states":["#);
    for (i, m) in seq.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""i":{},"#, i));
        out.push_str(&format!(r#""mu":{}"#, json_escape(&mu_to_string(m))));
        out.push('}');
    }
    out.push_str("],");

    // provenance (additive, tool-facing)
    out.push_str(r#""provenance":["#);
    for (j, p) in prov.iter().enumerate() {
        if j > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""i":{},"#, p.i));
        out.push_str(&format!(r#""rule_i":{},"#, p.rule_i));
        out.push_str(&format!(
            r#""pattern":{},"#,
            json_escape(&mu_to_string(&p.pattern))
        ));
        out.push_str(&format!(
            r#""template":{}"#,
            json_escape(&mu_to_string(&p.template))
        ));

        if !p.bindings.is_empty() {
            out.push_str(r#","bindings":{"#);
            for (k, (name, mu)) in p.bindings.iter().enumerate() {
                if k > 0 {
                    out.push(',');
                }
                out.push_str(&format!(
                    r#"{}:{}"#,
                    json_escape(name),
                    json_escape(&mu_to_string(mu))
                ));
            }
            out.push('}');
        }

        out.push('}');
    }
    out.push_str("],");

    // classification
    out.push_str(&format!(
        r#""classification":{}"#,
        json_escape(&classification)
    ));

    out.push('}');
    out
}

/// Minimal JSON string escaper (no external deps).
fn json_escape(s: &str) -> String {
    let mut out = String::new();
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
