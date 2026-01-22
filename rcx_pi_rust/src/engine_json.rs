use crate::engine::Engine;
use crate::formatter::mu_to_string;
use crate::parser::parse_mu;
use crate::schemas::ENGINE_RUN_SCHEMA_V1;
use crate::trace::RouteKind;
use crate::types::{Mu, RcxProgram};

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

fn route_to_string(r: RouteKind) -> &'static str {
    match r {
        RouteKind::Ra => "ra",
        RouteKind::Lobe => "lobe",
        RouteKind::Sink => "sink",
        RouteKind::Rewrite => "rewrite",
        RouteKind::Structural => "structural",
    }
}

/// Run an Engine over a list of inputs and export the full run as JSON.
///
/// Schema v1:
/// {
///   "schema": "rcx.engine_run.v1","schema_version":"rcx.engine_run.v1",
///   "world": "<world_name>",
///   "inputs": [ {"i":0,"mu":"..."}, ... ],
///   "buckets": { "ra":[...], "lobes":[...], "sink":[...] },
///   "trace": [ {"step":1,"phase":"...","route":"ra|lobe|...","payload":"..."} , ... ]
/// }
pub fn engine_run_to_json(world_name: &str, program: &RcxProgram, inputs: &[Mu]) -> String {
    let mut engine = Engine::new(program.clone());
    let mut state = crate::state::RCXState::new();

    // Run
    for mu in inputs {
        let _ = engine.process_input(&mut state, mu.clone());
    }

    // Build JSON (no external deps)
    let mut out = String::new();
    out.push('{');
    out.push_str(&format!(
        r#""schema":{},"#,
        json_escape(ENGINE_RUN_SCHEMA_V1)
    ));
    out.push_str(&format!(r#""world":{},"#, json_escape(world_name)));

    // inputs
    out.push_str(r#""inputs":["#);
    for (i, m) in inputs.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""i":{},"#, i));
        out.push_str(&format!(r#""mu":{}"#, json_escape(&mu_to_string(m))));
        out.push('}');
    }
    out.push_str("],");

    // buckets
    out.push_str(r#""buckets":{"ra":["#);
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
    out.push_str("]},");

    // trace
    out.push_str(r#""trace":["#);
    for (i, evt) in state.trace.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""step":{},"#, evt.step_index));
        out.push_str(&format!(r#""phase":{},"#, json_escape(&evt.phase)));
        out.push_str(&format!(
            r#""route":{},"#,
            json_escape(route_to_string(evt.route))
        ));
        out.push_str(&format!(
            r#""payload":{}"#,
            json_escape(&mu_to_string(&evt.payload))
        ));
        out.push('}');
    }
    out.push_str("]");

    out.push('}');
    out
}

/// Convenience: parse multiple Mu sources (strings) into a Vec<Mu>.

/// Run an Engine starting from an existing RCXState (e.g. restored from a snapshot)
/// and export the full run as JSON.
///
/// This is the bridge for "snapshot -> replay -> deterministic engine_run".
pub fn engine_run_from_state_to_json(
    world_name: &str,
    program: &RcxProgram,
    state: &mut crate::state::RCXState,
    inputs: &[Mu],
) -> String {
    let mut engine = Engine::new(program.clone());

    // Run from existing state
    for mu in inputs {
        let _ = engine.process_input(state, mu.clone());
    }

    // Build JSON (no external deps) - mirrors engine_run_to_json schema.
    let mut out = String::new();
    out.push('{');
    out.push_str(&format!(
        r#""schema":{},"#,
        json_escape(ENGINE_RUN_SCHEMA_V1)
    ));
    out.push_str(&format!(r#""world":{},"#, json_escape(world_name)));

    // inputs
    out.push_str(r#""inputs":["#);
    for (i, m) in inputs.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""i":{},"#, i));
        out.push_str(&format!(r#""mu":{}"#, json_escape(&mu_to_string(m))));
        out.push('}');
    }
    out.push_str("],");

    // buckets
    out.push_str(r#""buckets":{"ra":["#);
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
    out.push_str("]},");

    // trace
    out.push_str(r#""trace":["#);
    for (i, ev) in state.trace.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push('{');
        out.push_str(&format!(r#""step":{},"#, ev.step_index));
        out.push_str(&format!(r#""phase":{},"#, json_escape(&ev.phase)));
        out.push_str(&format!(
            r#""route":{},"#,
            json_escape(&format!("{:?}", ev.route))
        ));
        out.push_str(&format!(
            r#""payload":{}"#,
            json_escape(&mu_to_string(&ev.payload))
        ));
        out.push('}');
    }
    out.push_str("]");

    out.push('}');
    out
}

pub fn parse_inputs(mu_srcs: &[String]) -> Result<Vec<Mu>, String> {
    let mut out = Vec::new();
    for s in mu_srcs {
        let m = parse_mu(s).map_err(|e| format!("parse mu `{s}`: {e}"))?;
        out.push(m);
    }
    Ok(out)
}
