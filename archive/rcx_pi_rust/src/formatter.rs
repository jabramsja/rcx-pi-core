use crate::types::Mu;

/// Pretty-print a single Mu in RCX-ish syntax:
///   Sym("A")            -> "A"
///   Node([A,B])         -> "[A,B]"
///   Node([A,[B,C]])     -> "[A,[B,C]]"
pub fn mu_to_string(mu: &Mu) -> String {
    match mu {
        Mu::Sym(s) => s.clone(),
        Mu::Node(children) => {
            let inner = children
                .iter()
                .map(mu_to_string)
                .collect::<Vec<_>>()
                .join(",");
            format!("[{}]", inner)
        }
    }
}

/// Format a bucket of Mu values (like r_a / lobes / sink) as a single string:
///   [A, [B,C]] -> " [A, [B,C]] " etc.
pub fn bucket_to_string(bucket: &[Mu]) -> String {
    if bucket.is_empty() {
        "[]".to_string()
    } else {
        let inner = bucket
            .iter()
            .map(mu_to_string)
            .collect::<Vec<_>>()
            .join(", ");
        format!("[{}]", inner)
    }
}
