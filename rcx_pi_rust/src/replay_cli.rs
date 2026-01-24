//! Replay CLI matching Python's replay_cli.py (frozen semantics v1).
//! Bit-for-bit compatible with Python output.

use crate::trace_canon::{canon_jsonl, read_jsonl};
use std::fs;
use std::path::Path;

/// Exit codes matching Python semantics.
pub const EXIT_OK: i32 = 0;
pub const EXIT_MISMATCH: i32 = 1;
pub const EXIT_ERROR: i32 = 2;

/// Parsed CLI arguments.
pub struct ReplayArgs {
    pub trace: String,
    pub out: Option<String>,
    pub expect: Option<String>,
    pub check_canon: bool,
}

/// Parse CLI arguments.
pub fn parse_args(args: &[String]) -> Result<ReplayArgs, String> {
    let mut trace: Option<String> = None;
    let mut out: Option<String> = None;
    let mut expect: Option<String> = None;
    let mut check_canon = false;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--trace" => {
                i += 1;
                if i >= args.len() {
                    return Err("--trace requires a path".to_string());
                }
                trace = Some(args[i].clone());
            }
            "--out" => {
                i += 1;
                if i >= args.len() {
                    return Err("--out requires a path".to_string());
                }
                out = Some(args[i].clone());
            }
            "--expect" => {
                i += 1;
                if i >= args.len() {
                    return Err("--expect requires a path".to_string());
                }
                expect = Some(args[i].clone());
            }
            "--check-canon" => {
                check_canon = true;
            }
            "--help" | "-h" => {
                print_help();
                return Err("".to_string()); // Signal help was shown
            }
            arg => {
                return Err(format!("unknown argument: {}", arg));
            }
        }
        i += 1;
    }

    let trace = trace.ok_or("--trace is required")?;

    Ok(ReplayArgs {
        trace,
        out,
        expect,
        check_canon,
    })
}

fn print_help() {
    eprintln!("Usage: replay --trace <path> [--out <path>] [--expect <path>] [--check-canon]");
    eprintln!();
    eprintln!("Options:");
    eprintln!("  --trace <path>     Input trace JSONL path (required)");
    eprintln!("  --out <path>       Output path for canonicalized JSONL");
    eprintln!("  --expect <path>    Expected canonical JSONL path for comparison");
    eprintln!("  --check-canon      Fail if input is not already canonical");
    eprintln!("  --help, -h         Show this help");
}

/// Main replay entry point. Returns exit code.
pub fn replay_main(args: &[String]) -> i32 {
    match replay_main_inner(args) {
        Ok(code) => code,
        Err(msg) => {
            if !msg.is_empty() {
                eprintln!("ERROR: {}", msg);
            }
            EXIT_ERROR
        }
    }
}

fn replay_main_inner(args: &[String]) -> Result<i32, String> {
    let args = match parse_args(args) {
        Ok(a) => a,
        Err(msg) if msg.is_empty() => return Ok(EXIT_OK), // --help
        Err(msg) => return Err(msg),
    };

    let trace_path = Path::new(&args.trace);
    if !trace_path.exists() {
        return Err(format!("missing --trace file: {}", args.trace));
    }

    // Read original content
    let original = fs::read_to_string(trace_path)
        .map_err(|e| format!("failed to read {}: {}", args.trace, e))?;

    // Parse JSONL
    let raw_events = read_jsonl(&original)?;

    // Canonicalize
    let canon_text = canon_jsonl(&raw_events)?;

    // --check-canon: fail if input != canonical
    if args.check_canon {
        if original != canon_text {
            eprintln!("REPLAY_MISMATCH: input trace is not canonical (diff vs canonicalized form).");
            return Ok(EXIT_MISMATCH);
        }
    }

    // --out: write canonical artifact
    if let Some(ref out_path) = args.out {
        fs::write(out_path, &canon_text)
            .map_err(|e| format!("failed to write {}: {}", out_path, e))?;
    }

    // --expect: compare to expected
    if let Some(ref expect_path) = args.expect {
        let exp_path = Path::new(expect_path);
        if !exp_path.exists() {
            return Err(format!("missing --expect file: {}", expect_path));
        }
        let expected = fs::read_to_string(exp_path)
            .map_err(|e| format!("failed to read {}: {}", expect_path, e))?;
        if expected != canon_text {
            eprintln!("REPLAY_MISMATCH: canonical replay output differs from --expect.");
            return Ok(EXIT_MISMATCH);
        }
    }

    Ok(EXIT_OK)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_args_minimal() {
        let args = vec!["--trace".to_string(), "test.jsonl".to_string()];
        let parsed = parse_args(&args).unwrap();
        assert_eq!(parsed.trace, "test.jsonl");
        assert!(parsed.out.is_none());
        assert!(parsed.expect.is_none());
        assert!(!parsed.check_canon);
    }

    #[test]
    fn test_parse_args_full() {
        let args = vec![
            "--trace".to_string(),
            "in.jsonl".to_string(),
            "--out".to_string(),
            "out.jsonl".to_string(),
            "--expect".to_string(),
            "exp.jsonl".to_string(),
            "--check-canon".to_string(),
        ];
        let parsed = parse_args(&args).unwrap();
        assert_eq!(parsed.trace, "in.jsonl");
        assert_eq!(parsed.out, Some("out.jsonl".to_string()));
        assert_eq!(parsed.expect, Some("exp.jsonl".to_string()));
        assert!(parsed.check_canon);
    }
}
