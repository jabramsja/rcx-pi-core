#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Mu {
    /// A symbolic atom, e.g. "FACT_MARKER", "MULT_MARKER", "x"
    Sym(String),

    /// A generic node: μ(...) style; order matters, children are arbitrary Mu terms
    Node(Vec<Mu>),
}

impl Mu {
    /// Convenience constructor for a symbol &args => μ(sym, args...)
    pub fn with_head<S: Into<String>>(head: S, args: Vec<Mu>) -> Mu {
        let mut v = Vec::with_capacity(args.len() + 1);
        v.push(Mu::Sym(head.into()));
        v.extend(args);
        Mu::Node(v)
    }
}

#[derive(Clone, Debug)]
pub enum RuleAction {
    ToRa,
    ToLobe,
    ToSink,
    Rewrite(Mu), // <-- New! Allows Mu → Mu transformations
}

#[derive(Debug, Clone)]
pub struct RcxRule {
    pub pattern: Mu,
    pub action: RuleAction,
}

#[derive(Debug, Clone, Default)]
pub struct RcxProgram {
    pub rules: Vec<RcxRule>,
}

impl RcxProgram {
    pub fn new(rules: Vec<RcxRule>) -> Self {
        Self { rules }
    }
}
