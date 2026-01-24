//! Trace event canonicalization matching Python's trace_canon.py.
//! Frozen semantics (v1) - bit-for-bit compatible with Python output.
//!
//! IMPORTANT: This is a MIRROR of frozen Python v1 semantics, not authoritative.
//! Python (`rcx_pi/trace_canon.py`) remains the canonical reference implementation.

use crate::json_value::JsonValue;

/// Trace event schema version.
pub const TRACE_EVENT_V: i64 = 1;

/// Canonical key order for trace events.
pub const TRACE_EVENT_KEY_ORDER: &[&str] = &["v", "type", "i", "t", "mu", "meta"];

/// A canonicalized trace event.
#[derive(Debug, Clone)]
pub struct CanonEvent {
    pub v: i64,
    pub event_type: String,
    pub i: i64,
    pub t: Option<String>,
    pub mu: Option<JsonValue>,
    pub meta: Option<JsonValue>,
}

/// Parse and canonicalize a single trace event from JSON.
pub fn canon_event(ev: &JsonValue) -> Result<CanonEvent, String> {
    let obj = match ev {
        JsonValue::Object(o) => o,
        _ => return Err("event must be an object".to_string()),
    };

    // v: required, must be 1
    let v = match obj.get("v") {
        Some(JsonValue::Number(n)) => {
            let v = *n as i64;
            if v != TRACE_EVENT_V {
                return Err(format!("event.v must be {}, got {}", TRACE_EVENT_V, v));
            }
            v
        }
        None => TRACE_EVENT_V, // default
        _ => return Err("event.v must be an integer".to_string()),
    };

    // type: required, non-empty string
    let event_type = match obj.get("type") {
        Some(JsonValue::String(s)) if !s.trim().is_empty() => s.clone(),
        Some(JsonValue::String(_)) => {
            return Err("event.type must be a non-empty string".to_string())
        }
        _ => return Err("event.type must be a non-empty string".to_string()),
    };

    // i: required, integer >= 0
    let i = match obj.get("i") {
        Some(JsonValue::Number(n)) => {
            let i = *n as i64;
            if i < 0 {
                return Err("event.i must be >= 0".to_string());
            }
            i
        }
        _ => return Err("event.i must be an integer >= 0".to_string()),
    };

    // t: optional, non-empty string
    let t = match obj.get("t") {
        Some(JsonValue::String(s)) if !s.trim().is_empty() => Some(s.clone()),
        Some(JsonValue::String(_)) => {
            return Err("event.t must be a non-empty string when provided".to_string())
        }
        Some(JsonValue::Null) | None => None,
        _ => return Err("event.t must be a string when provided".to_string()),
    };

    // mu: optional, any JSON (deep-sorted if dict/list)
    let mu = match obj.get("mu") {
        Some(JsonValue::Null) | None => None,
        Some(v) => Some(v.deep_sorted()),
    };

    // meta: optional, must be object (deep-sorted)
    let meta = match obj.get("meta") {
        Some(JsonValue::Null) | None => None,
        Some(v @ JsonValue::Object(_)) => Some(v.deep_sorted()),
        Some(_) => return Err("event.meta must be an object when provided".to_string()),
    };

    Ok(CanonEvent {
        v,
        event_type,
        i,
        t,
        mu,
        meta,
    })
}

/// Canonicalize a sequence of events and enforce contiguous index ordering.
pub fn canon_events(events: &[JsonValue]) -> Result<Vec<CanonEvent>, String> {
    let mut out = Vec::with_capacity(events.len());
    for ev in events {
        out.push(canon_event(ev)?);
    }

    // Enforce contiguity
    if !out.is_empty() {
        let expected: Vec<i64> = (0..out.len() as i64).collect();
        let got: Vec<i64> = out.iter().map(|e| e.i).collect();
        if got != expected {
            return Err(format!(
                "event.i must be contiguous 0..n-1 in-order; got {:?}, expected {:?}",
                got, expected
            ));
        }
    }

    Ok(out)
}

/// Serialize one canonical event as compact JSON with stable key order.
pub fn canon_event_json(ev: &CanonEvent) -> String {
    let mut out = String::new();
    out.push('{');

    // v
    out.push_str(&format!(r#""v":{}"#, ev.v));

    // type
    out.push(',');
    out.push_str(&format!(r#""type":{}"#, json_escape_string(&ev.event_type)));

    // i
    out.push(',');
    out.push_str(&format!(r#""i":{}"#, ev.i));

    // t (optional)
    if let Some(ref t) = ev.t {
        out.push(',');
        out.push_str(&format!(r#""t":{}"#, json_escape_string(t)));
    }

    // mu (optional)
    if let Some(ref mu) = ev.mu {
        out.push(',');
        out.push_str(&format!(r#""mu":{}"#, mu.to_canonical_json()));
    }

    // meta (optional)
    if let Some(ref meta) = ev.meta {
        out.push(',');
        out.push_str(&format!(r#""meta":{}"#, meta.to_canonical_json()));
    }

    out.push('}');
    out
}

fn json_escape_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
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

/// Read JSONL file and return parsed events.
pub fn read_jsonl(content: &str) -> Result<Vec<JsonValue>, String> {
    let mut events = Vec::new();
    for (idx, line) in content.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let val = JsonValue::parse(line)
            .map_err(|e| format!("line {}: invalid JSON: {}", idx + 1, e))?;
        if !matches!(val, JsonValue::Object(_)) {
            return Err(format!("line {}: expected object/dict per line", idx + 1));
        }
        events.push(val);
    }
    Ok(events)
}

/// Canonicalize events and serialize to JSONL.
pub fn canon_jsonl(events: &[JsonValue]) -> Result<String, String> {
    let canon = canon_events(events)?;
    let mut out = String::new();
    for ev in canon {
        out.push_str(&canon_event_json(&ev));
        out.push('\n');
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_canon_minimal() {
        let input = r#"{"v":1,"type":"trace.start","i":0,"t":"test"}"#;
        let val = JsonValue::parse(input).unwrap();
        let ev = canon_event(&val).unwrap();
        assert_eq!(ev.v, 1);
        assert_eq!(ev.event_type, "trace.start");
        assert_eq!(ev.i, 0);
        assert_eq!(ev.t, Some("test".to_string()));
    }

    #[test]
    fn test_canon_json_output() {
        let input = r#"{"i":0,"type":"trace.start","v":1}"#;
        let val = JsonValue::parse(input).unwrap();
        let ev = canon_event(&val).unwrap();
        let json = canon_event_json(&ev);
        // Keys should be in canonical order: v, type, i
        assert_eq!(json, r#"{"v":1,"type":"trace.start","i":0}"#);
    }

    #[test]
    fn test_contiguity_check() {
        let events = vec![
            JsonValue::parse(r#"{"v":1,"type":"a","i":0}"#).unwrap(),
            JsonValue::parse(r#"{"v":1,"type":"b","i":2}"#).unwrap(), // gap!
        ];
        let result = canon_events(&events);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("contiguous"));
    }
}
