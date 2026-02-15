//! Generic JSON value type for arbitrary payloads.
//! Hand-rolled parsing/serialization matching frozen Python semantics.

use std::collections::BTreeMap;

/// Generic JSON value - supports arbitrary nesting.
#[derive(Debug, Clone, PartialEq)]
pub enum JsonValue {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<JsonValue>),
    Object(BTreeMap<String, JsonValue>), // BTreeMap for deterministic key order
}

impl JsonValue {
    /// Parse JSON from string. Returns (value, bytes_consumed).
    pub fn parse(s: &str) -> Result<JsonValue, String> {
        let s = s.trim();
        if s.is_empty() {
            return Err("empty input".to_string());
        }
        let (val, _) = parse_value(s)?;
        Ok(val)
    }

    /// Serialize to compact canonical JSON (no spaces, sorted keys).
    pub fn to_canonical_json(&self) -> String {
        match self {
            JsonValue::Null => "null".to_string(),
            JsonValue::Bool(b) => if *b { "true" } else { "false" }.to_string(),
            JsonValue::Number(n) => {
                // Match Python: integers without decimal, floats with
                if n.fract() == 0.0 && n.abs() < 1e15 {
                    format!("{}", *n as i64)
                } else {
                    format!("{}", n)
                }
            }
            JsonValue::String(s) => json_escape_string(s),
            JsonValue::Array(arr) => {
                let items: Vec<String> = arr.iter().map(|v| v.to_canonical_json()).collect();
                format!("[{}]", items.join(","))
            }
            JsonValue::Object(obj) => {
                // BTreeMap already sorted lexicographically
                let items: Vec<String> = obj
                    .iter()
                    .map(|(k, v)| format!("{}:{}", json_escape_string(k), v.to_canonical_json()))
                    .collect();
                format!("{{{}}}", items.join(","))
            }
        }
    }

    /// Deep sort: recursively sort all object keys (already done via BTreeMap)
    /// and deep-sort nested values.
    pub fn deep_sorted(&self) -> JsonValue {
        match self {
            JsonValue::Array(arr) => {
                JsonValue::Array(arr.iter().map(|v| v.deep_sorted()).collect())
            }
            JsonValue::Object(obj) => {
                let sorted: BTreeMap<String, JsonValue> = obj
                    .iter()
                    .map(|(k, v)| (k.clone(), v.deep_sorted()))
                    .collect();
                JsonValue::Object(sorted)
            }
            other => other.clone(),
        }
    }
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

fn parse_value(s: &str) -> Result<(JsonValue, &str), String> {
    let s = skip_ws(s);
    if s.is_empty() {
        return Err("unexpected end of input".to_string());
    }

    match s.chars().next().unwrap() {
        'n' => parse_null(s),
        't' => parse_true(s),
        'f' => parse_false(s),
        '"' => parse_string(s),
        '[' => parse_array(s),
        '{' => parse_object(s),
        c if c == '-' || c.is_ascii_digit() => parse_number(s),
        c => Err(format!("unexpected character: {}", c)),
    }
}

fn skip_ws(s: &str) -> &str {
    s.trim_start()
}

fn parse_null(s: &str) -> Result<(JsonValue, &str), String> {
    if s.starts_with("null") {
        Ok((JsonValue::Null, &s[4..]))
    } else {
        Err("expected 'null'".to_string())
    }
}

fn parse_true(s: &str) -> Result<(JsonValue, &str), String> {
    if s.starts_with("true") {
        Ok((JsonValue::Bool(true), &s[4..]))
    } else {
        Err("expected 'true'".to_string())
    }
}

fn parse_false(s: &str) -> Result<(JsonValue, &str), String> {
    if s.starts_with("false") {
        Ok((JsonValue::Bool(false), &s[5..]))
    } else {
        Err("expected 'false'".to_string())
    }
}

fn parse_string(s: &str) -> Result<(JsonValue, &str), String> {
    if !s.starts_with('"') {
        return Err("expected '\"'".to_string());
    }
    let s = &s[1..];
    let mut result = String::new();
    let mut chars = s.chars().peekable();
    let mut consumed = 1; // opening quote

    loop {
        match chars.next() {
            None => return Err("unterminated string".to_string()),
            Some('"') => {
                consumed += 1;
                break;
            }
            Some('\\') => {
                consumed += 1;
                match chars.next() {
                    Some('"') => {
                        result.push('"');
                        consumed += 1;
                    }
                    Some('\\') => {
                        result.push('\\');
                        consumed += 1;
                    }
                    Some('/') => {
                        result.push('/');
                        consumed += 1;
                    }
                    Some('n') => {
                        result.push('\n');
                        consumed += 1;
                    }
                    Some('r') => {
                        result.push('\r');
                        consumed += 1;
                    }
                    Some('t') => {
                        result.push('\t');
                        consumed += 1;
                    }
                    Some('u') => {
                        consumed += 1;
                        let mut hex = String::new();
                        for _ in 0..4 {
                            match chars.next() {
                                Some(c) if c.is_ascii_hexdigit() => {
                                    hex.push(c);
                                    consumed += 1;
                                }
                                _ => return Err("invalid unicode escape".to_string()),
                            }
                        }
                        let code = u32::from_str_radix(&hex, 16)
                            .map_err(|_| "invalid unicode escape")?;
                        if let Some(c) = char::from_u32(code) {
                            result.push(c);
                        }
                    }
                    Some(c) => {
                        result.push(c);
                        consumed += 1;
                    }
                    None => return Err("unterminated escape".to_string()),
                }
            }
            Some(c) => {
                result.push(c);
                consumed += c.len_utf8();
            }
        }
    }

    Ok((JsonValue::String(result), &s[consumed - 1..]))
}

fn parse_number(s: &str) -> Result<(JsonValue, &str), String> {
    let mut end = 0;
    let chars: Vec<char> = s.chars().collect();

    // Optional minus
    if end < chars.len() && chars[end] == '-' {
        end += 1;
    }

    // Integer part
    if end >= chars.len() {
        return Err("expected digit".to_string());
    }
    if chars[end] == '0' {
        end += 1;
    } else if chars[end].is_ascii_digit() {
        while end < chars.len() && chars[end].is_ascii_digit() {
            end += 1;
        }
    } else {
        return Err("expected digit".to_string());
    }

    // Fraction
    if end < chars.len() && chars[end] == '.' {
        end += 1;
        if end >= chars.len() || !chars[end].is_ascii_digit() {
            return Err("expected digit after decimal".to_string());
        }
        while end < chars.len() && chars[end].is_ascii_digit() {
            end += 1;
        }
    }

    // Exponent
    if end < chars.len() && (chars[end] == 'e' || chars[end] == 'E') {
        end += 1;
        if end < chars.len() && (chars[end] == '+' || chars[end] == '-') {
            end += 1;
        }
        if end >= chars.len() || !chars[end].is_ascii_digit() {
            return Err("expected digit in exponent".to_string());
        }
        while end < chars.len() && chars[end].is_ascii_digit() {
            end += 1;
        }
    }

    let num_str: String = chars[..end].iter().collect();
    let byte_len: usize = num_str.len();
    let num: f64 = num_str
        .parse()
        .map_err(|_| format!("invalid number: {}", num_str))?;

    Ok((JsonValue::Number(num), &s[byte_len..]))
}

fn parse_array(s: &str) -> Result<(JsonValue, &str), String> {
    if !s.starts_with('[') {
        return Err("expected '['".to_string());
    }
    let mut s = skip_ws(&s[1..]);
    let mut items = Vec::new();

    if s.starts_with(']') {
        return Ok((JsonValue::Array(items), &s[1..]));
    }

    loop {
        let (val, rest) = parse_value(s)?;
        items.push(val);
        s = skip_ws(rest);

        if s.starts_with(']') {
            return Ok((JsonValue::Array(items), &s[1..]));
        } else if s.starts_with(',') {
            s = skip_ws(&s[1..]);
        } else {
            return Err("expected ',' or ']'".to_string());
        }
    }
}

fn parse_object(s: &str) -> Result<(JsonValue, &str), String> {
    if !s.starts_with('{') {
        return Err("expected '{'".to_string());
    }
    let mut s = skip_ws(&s[1..]);
    let mut obj = BTreeMap::new();

    if s.starts_with('}') {
        return Ok((JsonValue::Object(obj), &s[1..]));
    }

    loop {
        // Parse key
        let (key_val, rest) = parse_string(s)?;
        let key = match key_val {
            JsonValue::String(k) => k,
            _ => return Err("object key must be string".to_string()),
        };
        s = skip_ws(rest);

        // Expect colon
        if !s.starts_with(':') {
            return Err("expected ':'".to_string());
        }
        s = skip_ws(&s[1..]);

        // Parse value
        let (val, rest) = parse_value(s)?;
        obj.insert(key, val);
        s = skip_ws(rest);

        if s.starts_with('}') {
            return Ok((JsonValue::Object(obj), &s[1..]));
        } else if s.starts_with(',') {
            s = skip_ws(&s[1..]);
        } else {
            return Err("expected ',' or '}'".to_string());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_primitives() {
        assert_eq!(JsonValue::parse("null").unwrap(), JsonValue::Null);
        assert_eq!(JsonValue::parse("true").unwrap(), JsonValue::Bool(true));
        assert_eq!(JsonValue::parse("false").unwrap(), JsonValue::Bool(false));
        assert_eq!(JsonValue::parse("42").unwrap(), JsonValue::Number(42.0));
        assert_eq!(JsonValue::parse("-3.14").unwrap(), JsonValue::Number(-3.14));
        assert_eq!(
            JsonValue::parse("\"hello\"").unwrap(),
            JsonValue::String("hello".to_string())
        );
    }

    #[test]
    fn test_parse_array() {
        let arr = JsonValue::parse("[1,2,3]").unwrap();
        if let JsonValue::Array(items) = arr {
            assert_eq!(items.len(), 3);
        } else {
            panic!("expected array");
        }
    }

    #[test]
    fn test_parse_object() {
        let obj = JsonValue::parse(r#"{"a":1,"b":2}"#).unwrap();
        if let JsonValue::Object(map) = obj {
            assert_eq!(map.len(), 2);
            assert_eq!(map.get("a"), Some(&JsonValue::Number(1.0)));
        } else {
            panic!("expected object");
        }
    }

    #[test]
    fn test_canonical_json() {
        // Object keys should be sorted
        let obj = JsonValue::parse(r#"{"z":1,"a":2}"#).unwrap();
        assert_eq!(obj.to_canonical_json(), r#"{"a":2,"z":1}"#);
    }
}
