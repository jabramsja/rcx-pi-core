use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;

use crate::formatter::bucket_to_string;
use crate::parser::parse_mu;
use crate::state::RCXState;
use crate::types::Mu;

/// Save only the bucket state (r_a, lobes, sink) to a simple text file.
///
/// Format:
///   # RCX state snapshot
///   ra = [ ... ]
///   lobes = [ ... ]
///   sink = [ ... ]
pub fn save_state<P: AsRef<Path>>(path: P, state: &RCXState) -> Result<(), String> {
    let path = path.as_ref();

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("create state dir {}: {e}", parent.display()))?;
    }

    let mut file =
        File::create(path).map_err(|e| format!("create state file {}: {e}", path.display()))?;

    writeln!(file, "# RCX state snapshot").map_err(|e| e.to_string())?;
    writeln!(file, "ra = {}", bucket_to_string(&state.ra)).map_err(|e| e.to_string())?;
    writeln!(file, "lobes = {}", bucket_to_string(&state.lobes)).map_err(|e| e.to_string())?;
    writeln!(file, "sink = {}", bucket_to_string(&state.sink)).map_err(|e| e.to_string())?;

    Ok(())
}

/// Load bucket state (r_a, lobes, sink) from a text file created by `save_state`.
///
/// Does NOT touch program rules. Clears trace/step counter so the run is fresh.
pub fn load_state<P: AsRef<Path>>(path: P, state: &mut RCXState) -> Result<(), String> {
    let path = path.as_ref();

    let file = File::open(path).map_err(|e| format!("open state file {}: {e}", path.display()))?;
    let reader = BufReader::new(file);

    let mut ra_str: Option<String> = None;
    let mut lobes_str: Option<String> = None;
    let mut sink_str: Option<String> = None;

    for line_res in reader.lines() {
        let line = line_res.map_err(|e| e.to_string())?;
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        if let Some(rest) = line.strip_prefix("ra =") {
            ra_str = Some(rest.trim().to_string());
        } else if let Some(rest) = line.strip_prefix("lobes =") {
            lobes_str = Some(rest.trim().to_string());
        } else if let Some(rest) = line.strip_prefix("sink =") {
            sink_str = Some(rest.trim().to_string());
        }
    }

    fn parse_bucket(src_opt: Option<String>) -> Result<Vec<Mu>, String> {
        let src = src_opt.unwrap_or_else(|| "[]".to_string());
        let mu = parse_mu(&src).map_err(|e| format!("parse bucket `{}`: {e}", src))?;
        match mu {
            Mu::Node(children) => Ok(children),
            other => Ok(vec![other]),
        }
    }

    state.ra = parse_bucket(ra_str)?;
    state.lobes = parse_bucket(lobes_str)?;
    state.sink = parse_bucket(sink_str)?;

    // Reset transient stuff to keep things sane.
    state.current = None;
    state.trace.clear();
    state.step_counter = 0;
    state.null_reg.clear();
    state.inf_reg.clear();

    Ok(())
}
