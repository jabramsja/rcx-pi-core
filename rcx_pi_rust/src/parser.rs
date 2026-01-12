use crate::types::Mu;

/// Minimal Mu parser with nesting:
/// - `A`            → Sym("A")
/// - `[A,A]`        → Node([Sym("A"), Sym("A")])
/// - `[omega,[a,b]]`→ Node([Sym("omega"), Node([Sym("a"), Sym("b")])])
///
/// Notes:
/// - We treat tokens as raw symbols (no quoting/escaping yet).
/// - Commas split only at bracket-depth 0.
/// - Whitespace is trimmed around tokens.
pub fn parse_mu(input: &str) -> Result<Mu, String> {
    let s = input.trim();
    if s.is_empty() {
        return Err("empty input".to_string());
    }
    parse_term(s)
}

fn parse_term(s: &str) -> Result<Mu, String> {
    let s = s.trim();
    if s.is_empty() {
        return Err("empty term".to_string());
    }

    if s.starts_with('[') {
        if !s.ends_with(']') {
            return Err(format!("unbalanced '[': `{}`", s));
        }
        parse_list(s)
    } else {
        Ok(Mu::Sym(s.to_string()))
    }
}

fn parse_list(s: &str) -> Result<Mu, String> {
    // s starts with '[' and ends with ']'
    if s == "[]" {
        return Err("empty list [] is not supported yet".to_string());
    }
    let inner = &s[1..s.len() - 1]; // strip [ and ]
    let inner = inner.trim();
    if inner.is_empty() {
        return Err("empty list [] is not supported yet".to_string());
    }

    let parts = split_top_level_commas(inner)?;
    let mut children = Vec::with_capacity(parts.len());
    for part in parts {
        let tok = part.trim();
        if tok.is_empty() {
            return Err(format!("empty symbol in list: `{}`", s));
        }
        children.push(parse_term(tok)?);
    }
    Ok(Mu::Node(children))
}

/// Split `s` by commas that occur at bracket depth 0.
/// Example:
///   "omega,[a,b],x" -> ["omega", "[a,b]", "x"]
fn split_top_level_commas(s: &str) -> Result<Vec<String>, String> {
    let mut out: Vec<String> = Vec::new();
    let mut buf = String::new();
    let mut depth: i32 = 0;

    for ch in s.chars() {
        match ch {
            '[' => {
                depth += 1;
                buf.push(ch);
            }
            ']' => {
                depth -= 1;
                if depth < 0 {
                    return Err(format!("unbalanced ']': `{}`", s));
                }
                buf.push(ch);
            }
            ',' if depth == 0 => {
                out.push(buf.trim().to_string());
                buf.clear();
            }
            _ => buf.push(ch),
        }
    }

    if depth != 0 {
        return Err(format!("unbalanced brackets in `{}`", s));
    }

    if !buf.trim().is_empty() {
        out.push(buf.trim().to_string());
    }

    Ok(out)
}
