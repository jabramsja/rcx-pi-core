use crate::formatter::mu_to_string;
use crate::parser::parse_mu;
use crate::schemas::SNAPSHOT_SCHEMA_V1;
use crate::state::RCXState;
use crate::types::{Mu, RcxProgram};
use crate::types::{RcxRule, RuleAction};

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

/// Snapshot schema v1 (JSON):
/// {
///   "schema": "rcx.snapshot.v1",
///   "world": "<world_name>",
///   "program": { "rules": ["<mu_rule_src>", ...] },
///   "state": {
///     "current": "<mu>" | null,
///     "ra": ["<mu>", ...],
///     "lobes": ["<mu>", ...],
///     "sink": ["<mu>", ...],
///     "step_counter": <u64>,
///     "null_reg": ["<mu>", ...],
///     "inf_reg": ["<mu>", ...],
///     "trace": [ {"step":1,"phase":"...","route":"...","payload":"..."} , ... ]
///   }
/// }
///
/// Notes:
/// - Deterministic ordering: arrays emit in the order stored.
/// - This is intended as a stable artifact for tooling; avoid parsing console text.
pub fn snapshot_to_json(world_name: &str, program: &RcxProgram, state: &RCXState) -> String {
    let mut out = String::new();
    out.push('{');

    out.push_str(&format!(r#""schema":{},"#, json_escape(SNAPSHOT_SCHEMA_V1)));
    out.push_str(&format!(r#""world":{},"#, json_escape(world_name)));

    // program rules
    out.push_str(r#""program":{"rules":["#);
    for (i, rule) in program.rules.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&rule_to_string(rule)));
    }
    out.push_str("]},");

    // state
    out.push_str(r#""state":{"current":"#);
    match &state.current {
        Some(m) => out.push_str(&json_escape(&mu_to_string(m))),
        None => out.push_str("null"),
    }
    out.push_str(r#","ra":["#);
    for (i, m) in state.ra.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&mu_to_string(m)));
    }
    out.push_str(r#"],"lobes":["#);
    for (i, m) in state.lobes.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&mu_to_string(m)));
    }
    out.push_str(r#"],"sink":["#);
    for (i, m) in state.sink.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&mu_to_string(m)));
    }
    out.push_str("],");

    out.push_str(&format!(r#""step_counter":{},"#, state.step_counter));

    out.push_str(r#""null_reg":["#);
    for (i, m) in state.null_reg.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&mu_to_string(m)));
    }
    out.push_str(r#"],"inf_reg":["#);
    for (i, m) in state.inf_reg.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&json_escape(&mu_to_string(m)));
    }
    out.push_str("],");

    out.push_str(r#""trace":["#);
    for (i, evt) in state.trace.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""step":{},"#, evt.step_index));
        out.push_str(&format!(r#""phase":{},"#, json_escape(&evt.phase)));
        // route already stringified elsewhere; keep it stable via debug fallback if needed
        out.push_str(&format!(
            r#""route":{},"#,
            json_escape(&format!("{:?}", evt.route).to_lowercase())
        ));
        out.push_str(&format!(
            r#""payload":{}"#,
            json_escape(&mu_to_string(&evt.payload))
        ));
        out.push('}');
    }
    out.push_str("]");

    out.push_str("}}");
    out
}

// Minimal JSON extractor helpers (no deps). Assumes trusted-ish input (our own emitted JSON).
fn extract_array_strings(json: &str, key: &str) -> Result<Vec<String>, String> {
    let pat = format!(r#""{}":["#, key);
    let start = json
        .find(&pat)
        .ok_or_else(|| format!("missing key {key}"))?
        + pat.len();
    let mut i = start;
    let bytes = json.as_bytes();
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut in_str = false;
    let mut esc = false;
    while i < bytes.len() {
        let c = bytes[i] as char;
        if !in_str {
            if c == ']' {
                break;
            }
            if c == '"' {
                in_str = true;
                cur.clear();
            }
        } else {
            if esc {
                cur.push(match c {
                    'n' => '\n',
                    'r' => '\r',
                    't' => '\t',
                    '"' => '"',
                    '\\' => '\\',
                    other => other,
                });
                esc = false;
            } else if c == '\\' {
                esc = true;
            } else if c == '"' {
                in_str = false;
                out.push(cur.clone());
            } else {
                cur.push(c);
            }
        }
        i += 1;
    }
    Ok(out)
}

fn extract_nullable_string(json: &str, key: &str) -> Result<Option<String>, String> {
    let pat = format!(r#""{}":"#, key);
    let start = json
        .find(&pat)
        .ok_or_else(|| format!("missing key {key}"))?
        + pat.len();

    let rest = json[start..].trim_start();

    if rest.starts_with("null") {
        return Ok(None);
    }
    if !rest.starts_with('"') {
        return Err(format!("key {key} not string/null"));
    }

    // Parse one JSON string (minimal escapes, enough for our emitted JSON).
    // Supports: \" \\ \n \r \t
    let mut out = String::new();
    let mut esc = false;

    for ch in rest[1..].chars() {
        if esc {
            out.push(match ch {
                'n' => '\n',
                'r' => '\r',
                't' => '\t',
                '"' => '"',
                '\\' => '\\',
                other => other,
            });
            esc = false;
            continue;
        }

        if ch == '\\' {
            esc = true;
            continue;
        }

        if ch == '"' {
            return Ok(Some(out));
        }

        out.push(ch);
    }

    Err(format!("unterminated string for key {key}"))
}

fn extract_u64(json: &str, key: &str) -> Result<u64, String> {
    let pat = format!(r#""{}":"#, key);
    let start = json
        .find(&pat)
        .ok_or_else(|| format!("missing key {key}"))?
        + pat.len();
    let s = json[start..].trim_start();
    let mut n = String::new();
    for ch in s.chars() {
        if ch.is_ascii_digit() {
            n.push(ch);
        } else {
            break;
        }
    }
    n.parse::<u64>().map_err(|e| format!("parse {key}: {e}"))
}

/// Load snapshot JSON v1 produced by `snapshot_to_json`.
pub fn snapshot_from_json(
    world_name: &str,
    json: &str,
) -> Result<(String, RcxProgram, RCXState), String> {
    // world in JSON is informational; we return the supplied world_name separately.
    let rules = extract_array_strings(json, "rules")?;
    let mut program = RcxProgram { rules: Vec::new() };
    for r in rules {
        program
            .rules
            .push(parse_rule_line(&r).map_err(|e| format!("parse rule: {e}"))?);
    }

    let current_s = extract_nullable_string(json, "current")?;
    let current = match current_s {
        Some(s) => Some(parse_mu(&s).map_err(|e| format!("parse current: {e}"))?),
        None => None,
    };

    let ra_s = extract_array_strings(json, "ra")?;
    let lobes_s = extract_array_strings(json, "lobes")?;
    let sink_s = extract_array_strings(json, "sink")?;
    let null_reg_s = extract_array_strings(json, "null_reg")?;
    let inf_reg_s = extract_array_strings(json, "inf_reg")?;
    let step_counter = extract_u64(json, "step_counter")?;

    let mut state = RCXState::new();
    state.current = current;
    state.ra = ra_s
        .into_iter()
        .map(|s| parse_mu(&s).map_err(|e| format!("parse ra: {e}")))
        .collect::<Result<Vec<Mu>, _>>()?;
    state.lobes = lobes_s
        .into_iter()
        .map(|s| parse_mu(&s).map_err(|e| format!("parse lobes: {e}")))
        .collect::<Result<Vec<Mu>, _>>()?;
    state.sink = sink_s
        .into_iter()
        .map(|s| parse_mu(&s).map_err(|e| format!("parse sink: {e}")))
        .collect::<Result<Vec<Mu>, _>>()?;
    state.null_reg = null_reg_s
        .into_iter()
        .map(|s| parse_mu(&s).map_err(|e| format!("parse null_reg: {e}")))
        .collect::<Result<Vec<Mu>, _>>()?;
    state.inf_reg = inf_reg_s
        .into_iter()
        .map(|s| parse_mu(&s).map_err(|e| format!("parse inf_reg: {e}")))
        .collect::<Result<Vec<Mu>, _>>()?;
    state.step_counter = step_counter as usize;

    // trace import intentionally omitted in v1 loader (we can add later safely).
    // keeping it empty avoids coupling to trace internal changes.
    state.trace.clear();

    Ok((world_name.to_string(), program, state))
}
// -- snapshot_json: rule helpers (v1) --
fn rule_to_string(rule: &RcxRule) -> String {
    let pat = mu_to_string(&rule.pattern);
    match &rule.action {
        RuleAction::ToRa => format!("{pat} -> ra"),
        RuleAction::ToLobe => format!("{pat} -> lobe"),
        RuleAction::ToSink => format!("{pat} -> sink"),
        RuleAction::Rewrite(mu) => {
            let rhs = mu_to_string(mu);
            format!("{pat} -> rewrite {rhs}")
        }
    }
}

fn parse_rule_line(line: &str) -> Result<RcxRule, String> {
    // Accept: "<pattern> -> <action>"
    let parts: Vec<&str> = line.split("->").collect();
    if parts.len() != 2 {
        return Err(format!("bad rule line: `{}`", line));
    }
    let pat_src = parts[0].trim();
    let rhs_src = parts[1].trim();

    let pattern = parse_mu(pat_src).map_err(|e| format!("parse pattern `{pat_src}`: {e}"))?;

    let rhs_lower = rhs_src.to_lowercase();
    let action = if rhs_lower.starts_with("rewrite ") {
        let payload_src = rhs_src["rewrite".len()..].trim();
        let mu = parse_mu(payload_src)
            .map_err(|e| format!("parse rewrite payload `{payload_src}`: {e}"))?;
        RuleAction::Rewrite(mu)
    } else {
        match rhs_lower.as_str() {
            "ra" => RuleAction::ToRa,
            "lobe" | "lobes" => RuleAction::ToLobe,
            "sink" => RuleAction::ToSink,
            other => return Err(format!("unknown rule target `{other}`")),
        }
    };

    Ok(RcxRule { pattern, action })
}
