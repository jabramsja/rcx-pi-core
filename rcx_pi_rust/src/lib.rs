pub fn add(left: u64, right: u64) -> u64 {
    left + right
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_works() {
        let result = add(2, 2);
        assert_eq!(result, 4);
    }
}

pub mod engine;
pub mod engine_json;
pub mod eval;
pub mod fold;
pub mod formatter;
pub mod lobes;
pub mod matching;
pub mod mu_loader;
pub mod orbit;
pub mod orbit_json;
pub mod parser;
pub mod pattern;
pub mod runtime;
pub mod serialize;
pub mod serialize_json;
pub mod sink;
pub mod state;
pub mod state_io;
pub mod trace;
pub mod traits;
pub mod types;
pub mod unify;
