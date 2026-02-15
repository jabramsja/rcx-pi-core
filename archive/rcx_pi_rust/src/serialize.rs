use std::fs::File;
use std::io::{BufRead, BufReader, Write};

use crate::{
    formatter::mu_to_string,
    parser::parse_mu,
    state::RCXState,
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

/// Save program rules + buckets (r_a / lobes / sink) to a snapshot file.
///
/// Format example:
///
///   # RCX-π snapshot v1
///   PROGRAM:
///   RULE: [news,stable] -> ra
///   RULE: [PING,PING] -> rewrite [PONG,PING]
///   STATE:
///   RA: [null,a]
///   LOBE: [inf,a]
///   SINK: [paradox,a]
///
pub fn save_state(path: &str, state: &RCXState, program: &RcxProgram) -> Result<(), String> {
    let mut file = File::create(path).map_err(|e| format!("create {path}: {e}"))?;

    write_line(&mut file, "# RCX-π snapshot v1")?;
    write_line(&mut file, "PROGRAM:")?;

    // Rules
    for rule in &program.rules {
        let pat = mu_to_string(&rule.pattern);
        let line = match &rule.action {
            RuleAction::ToRa => format!("RULE: {pat} -> ra"),
            RuleAction::ToLobe => format!("RULE: {pat} -> lobe"),
            RuleAction::ToSink => format!("RULE: {pat} -> sink"),
            RuleAction::Rewrite(mu) => {
                let rhs = mu_to_string(mu);
                format!("RULE: {pat} -> rewrite {rhs}")
            }
        };
        write_line(&mut file, &line)?;
    }

    write_line(&mut file, "STATE:")?;

    // r_a / lobes / sink
    for mu in &state.ra {
        write_line(&mut file, &format!("RA: {}", mu_to_string(mu)))?;
    }
    for mu in &state.lobes {
        write_line(&mut file, &format!("LOBE: {}", mu_to_string(mu)))?;
    }
    for mu in &state.sink {
        write_line(&mut file, &format!("SINK: {}", mu_to_string(mu)))?;
    }

    Ok(())
}

fn write_line(file: &mut File, line: &str) -> Result<(), String> {
    writeln!(file, "{line}").map_err(|e| format!("write error: {e}"))
}

/// Load a snapshot created by `save_state`.
/// Returns (RCXState, RcxProgram).
pub fn load_state(path: &str) -> Result<(RCXState, RcxProgram), String> {
    let file = File::open(path).map_err(|e| format!("open {path}: {e}"))?;
    let reader = BufReader::new(file);

    let mut program = RcxProgram { rules: Vec::new() };
    let mut ra: Vec<Mu> = Vec::new();
    let mut lobes: Vec<Mu> = Vec::new();
    let mut sink: Vec<Mu> = Vec::new();

    for line_res in reader.lines() {
        let raw = line_res.map_err(|e| format!("read {path}: {e}"))?;
        let line = raw.trim();
        if line.is_empty() {
            continue;
        }
        if line.starts_with('#') {
            continue;
        }
        if line == "PROGRAM:" || line == "STATE:" {
            continue;
        }

        // RULE: <pattern> -> <action>
        if let Some(rest) = line.strip_prefix("RULE: ") {
            let parts: Vec<&str> = rest.split("->").collect();
            if parts.len() != 2 {
                return Err(format!("bad RULE line in {path}: `{line}`"));
            }
            let pat_src = parts[0].trim();
            let rhs_src = parts[1].trim();

            let pattern = parse_mu(pat_src)
                .map_err(|e| format!("parse pattern `{pat_src}` in {path}: {e}"))?;

            let rhs_lower = rhs_src.to_lowercase();

            let action = if rhs_lower.starts_with("rewrite ") {
                let payload_src = &rhs_src["rewrite".len()..].trim();
                let mu = parse_mu(payload_src)
                    .map_err(|e| format!("parse rewrite payload `{payload_src}` in {path}: {e}"))?;
                RuleAction::Rewrite(mu)
            } else {
                match rhs_lower.as_str() {
                    "ra" => RuleAction::ToRa,
                    "lobe" | "lobes" => RuleAction::ToLobe,
                    "sink" => RuleAction::ToSink,
                    other => return Err(format!("unknown rule target `{other}` in {path}")),
                }
            };

            program.rules.push(RcxRule { pattern, action });
            continue;
        }

        // Buckets
        if let Some(rest) = line.strip_prefix("RA: ") {
            let mu = parse_mu(rest).map_err(|e| format!("parse RA mu `{rest}` in {path}: {e}"))?;
            ra.push(mu);
            continue;
        }

        if let Some(rest) = line.strip_prefix("LOBE: ") {
            let mu =
                parse_mu(rest).map_err(|e| format!("parse LOBE mu `{rest}` in {path}: {e}"))?;
            lobes.push(mu);
            continue;
        }

        if let Some(rest) = line.strip_prefix("SINK: ") {
            let mu =
                parse_mu(rest).map_err(|e| format!("parse SINK mu `{rest}` in {path}: {e}"))?;
            sink.push(mu);
            continue;
        }

        return Err(format!("unrecognized line in {path}: `{line}`"));
    }

    let state = RCXState {
        current: None,
        ra,
        lobes,
        sink,
        null_reg: Vec::new(),
        inf_reg: Vec::new(),
        trace: Vec::new(),
        step_counter: 0,
    };

    Ok((state, program))
}
