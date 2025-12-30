use crate::types::Mu;

/// Very small Mu parser:
/// - `A`          → Sym("A")
/// - `[A,A]`      → Node([Sym("A"), Sym("A")])
/// - `[NEWS,STABLE]` → Node([Sym("NEWS"), Sym("STABLE")])
///
/// No nesting yet, just flat lists of symbols.
pub fn parse_mu(input: &str) -> Result<Mu, String> {
    let s = input.trim();

    // List form: [A,B,C]
    if s.starts_with('[') && s.ends_with(']') {
        let inner = &s[1..s.len() - 1]; // strip [ and ]
        if inner.trim().is_empty() {
            return Err("empty list [] is not supported yet".to_string());
        }

        let parts: Vec<&str> = inner.split(',').collect();
        let mut children = Vec::with_capacity(parts.len());

        for raw in parts {
            let sym = raw.trim();
            if sym.is_empty() {
                return Err(format!("empty symbol in list: `{input}`"));
            }
            // For now we treat every token as a plain symbol.
            children.push(Mu::Sym(sym.to_string()));
        }

        Ok(Mu::Node(children))
    } else {
        // Atom form: "A", "NEWS", "q", etc.
        if s.is_empty() {
            return Err("empty input".to_string());
        }
        Ok(Mu::Sym(s.to_string()))
    }
}
