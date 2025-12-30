use std::fs;
use std::io::{self, Write};

use rcx_pi_rust::{
    engine::Engine,
    formatter::{bucket_to_string, mu_to_string},
    mu_loader::{load_mu_file, save_mu_file},
    orbit::orbit,
    parser::parse_mu,
    state::RCXState,
    state_io::{load_state, save_state},
    types::{Mu, RcxProgram, RcxRule, RuleAction},
};

/// Classify an orbit purely from its state sequence.
/// This is local to the REPL and does *not* depend on orbit::OmegaKind.
fn classify_orbit(seq: &[Mu]) -> String {
    if seq.is_empty() {
        return "empty orbit (no states produced)".to_string();
    }

    let last = &seq[seq.len() - 1];

    if let Some(prev_idx) = seq[..seq.len() - 1].iter().position(|m| m == last) {
        let transient_len = prev_idx;
        let period = seq.len() - 1 - prev_idx;

        if period == 1 {
            if transient_len == 0 {
                "fixed point".to_string()
            } else {
                format!("transient of length {transient_len} then fixed point")
            }
        } else if transient_len == 0 {
            format!("pure limit cycle (period = {period})")
        } else {
            format!("transient of length {transient_len} then limit cycle (period = {period})")
        }
    } else {
        format!("no detected cycle up to {} steps", seq.len())
    }
}

fn default_news_program() -> RcxProgram {
    RcxProgram {
        rules: vec![
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("news".to_string()),
                    Mu::Sym("stable".to_string()),
                ]),
                action: RuleAction::ToRa,
            },
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("news".to_string()),
                    Mu::Sym("unstable".to_string()),
                ]),
                action: RuleAction::ToLobe,
            },
            RcxRule {
                pattern: Mu::Node(vec![
                    Mu::Sym("news".to_string()),
                    Mu::Sym("paradox".to_string()),
                ]),
                action: RuleAction::ToSink,
            },
        ],
    }
}

fn main() {
    // Boot with default NEWS program.
    let mut program = default_news_program();
    let mut engine = Engine::new(program.clone());
    let mut state = RCXState::new();

    println!("RCX-π REPL — Mu → [r_a | lobes | sink]");
    println!("Commands:");
    println!("  <mu>             evaluate expression (e.g. A, [A,A], [news,stable])");
    println!("  :load FILE       load rules from ./mu_programs/FILE (merge into program)");
    println!("  :rules           list current program rules");
    println!("  :why MU          show trace for classifying MU");
    println!("  :learn ...       learn a rule, e.g. `:learn ping rewrite pong`");
    println!("  :orbit MU [n]    show rewrite orbit for MU up to n steps");
    println!("  :omega MU [n]    summarize ω-limit behavior for MU");
    println!("  :worlds          list available .mu worlds");
    println!("  :save-world NAME save current rules as mu_programs/NAME.mu");
    println!("  :load-world NAME reset + load mu_programs/NAME.mu as the world");
    println!("  :save-state NAME save current buckets to snapshots/NAME.state");
    println!("  :load-state NAME load buckets from snapshots/NAME.state");
    println!("  :trace           dump trace log");
    println!("  :clear           reset state (r_a, lobes, sink, trace)");
    println!("  :reset           reset rules + state to default NEWS world");
    println!("  :q               exit\n");

    let stdin = io::stdin();

    loop {
        print!("rcx> ");
        io::stdout().flush().unwrap();

        let mut line = String::new();
        if stdin.read_line(&mut line).is_err() {
            println!("(input error, exiting)");
            break;
        }

        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        // --- Commands -------------------------------------------------------

        // quit
        if line == ":q" || line == ":quit" || line == ":exit" {
            println!("bye.");
            break;
        }

        // :clear -> reset RA / lobes / sink / trace
        if line == ":clear" {
            state = RCXState::new();
            println!("[state cleared]");
            continue;
        }

        // :reset -> restore default NEWS program + clear state
        if line == ":reset" {
            program = default_news_program();
            engine = Engine::new(program.clone());
            state = RCXState::new();
            println!("[RESET] rules + state restored to default NEWS world");
            continue;
        }

        // :trace -> dump trace log
        if line == ":trace" {
            if state.trace.is_empty() {
                println!("[trace] (empty)");
            } else {
                println!("[trace log]");
                for evt in &state.trace {
                    println!(
                        "  step {} | phase={} | route={:?} | payload={}",
                        evt.step_index,
                        evt.phase,
                        evt.route,
                        mu_to_string(&evt.payload),
                    );
                }
            }
            continue;
        }

        // :rules -> list current rules
        if line == ":rules" {
            println!("[rules]");
            for (idx, rule) in program.rules.iter().enumerate() {
                let pat = mu_to_string(&rule.pattern);
                let tgt = match &rule.action {
                    RuleAction::ToRa => "ra".to_string(),
                    RuleAction::ToLobe => "lobe".to_string(),
                    RuleAction::ToSink => "sink".to_string(),
                    RuleAction::Rewrite(mu) => {
                        format!("rewrite({})", mu_to_string(mu))
                    }
                };
                println!("  {idx}: {pat} -> {tgt}");
            }
            continue;
        }

        // :why MU  -> run a one-off classification with fresh state + trace
        if line.starts_with(":why ") {
            let mu_src = line[5..].trim();
            if mu_src.is_empty() {
                println!("usage: :why <Mu>");
                continue;
            }

            let mu = match parse_mu(mu_src) {
                Ok(mu) => mu,
                Err(e) => {
                    println!("[why] parse error: {e}");
                    continue;
                }
            };

            let mut tmp_state = RCXState::new();
            let mut tmp_engine = Engine::new(program.clone());
            let route = tmp_engine.process_input(&mut tmp_state, mu.clone());

            println!("[why] probing {}", mu_to_string(&mu));
            println!("[why] route: {:?}", route);
            if tmp_state.trace.is_empty() {
                println!("[why] (no trace events)");
            } else {
                println!("[why] trace for this classification:");
                for evt in &tmp_state.trace {
                    println!(
                        "  step {} | phase={} | route={:?} | payload={}",
                        evt.step_index,
                        evt.phase,
                        evt.route,
                        mu_to_string(&evt.payload),
                    );
                }
            }
            continue;
        }

        // :load FILE   -> always from ./mu_programs/FILE
        if line.starts_with(":load ") {
            let filename = line[6..].trim();
            if filename.is_empty() {
                println!("usage: :load <filename.mu>");
                continue;
            }

            match load_mu_file(filename) {
                Ok(p) => {
                    let n = p.rules.len();
                    program.rules.extend(p.rules.into_iter());
                    engine = Engine::new(program.clone());
                    println!("Loaded {n} rules from mu_programs/{filename}");
                }
                Err(e) => {
                    println!("load error: {e}");
                }
            }
            continue;
        }

        // :worlds -> list available .mu files in ./mu_programs
        if line == ":worlds" {
            match fs::read_dir("mu_programs") {
                Ok(entries) => {
                    let mut names: Vec<String> = entries
                        .filter_map(|e| e.ok())
                        .filter_map(|e| {
                            let path = e.path();
                            if path.extension().and_then(|s| s.to_str()) == Some("mu") {
                                path.file_name()
                                    .and_then(|n| n.to_str())
                                    .map(|s| s.to_string())
                            } else {
                                None
                            }
                        })
                        .collect();
                    names.sort();
                    println!("[worlds]");
                    if names.is_empty() {
                        println!("  (no .mu files in mu_programs/)");
                    } else {
                        for name in names {
                            println!("  {name}");
                        }
                    }
                }
                Err(e) => {
                    println!("[worlds] error reading mu_programs/: {e}");
                }
            }
            continue;
        }

        // :save-world NAME -> save current rules as mu_programs/NAME.mu
        if line.starts_with(":save-world ") {
            let name = line[12..].trim();
            if name.is_empty() {
                println!("usage: :save-world NAME");
                continue;
            }

            match save_mu_file(name, &program) {
                Ok(fname) => {
                    println!(
                        "[save-world] wrote {} rules to mu_programs/{}",
                        program.rules.len(),
                        fname
                    );
                }
                Err(e) => {
                    println!("[save-world] error: {e}");
                }
            }

            continue;
        }

        // :load-world NAME -> reset + load mu_programs/NAME.mu as the world
        if line.starts_with(":load-world ") {
            let name = line[12..].trim();
            if name.is_empty() {
                println!("usage: :load-world NAME");
                continue;
            }

            match load_mu_file(name) {
                Ok(p) => {
                    let count = p.rules.len();

                    // Replace the whole program with what we just loaded
                    program = p;
                    engine = Engine::new(program.clone());
                    state = RCXState::new();

                    // For display: normalize like :save-world
                    let display_name = if name.ends_with(".mu") {
                        name.to_string()
                    } else {
                        format!("{name}.mu")
                    };

                    println!(
                        "[load-world] loaded {count} rules from mu_programs/{} and reset state",
                        display_name
                    );
                }
                Err(e) => {
                    println!("[load-world] error: {e}");
                }
            }

            continue;
        }

        // :learn pattern rewrite target
        // :learn pattern ra|lobe|sink
        //
        // examples:
        //   :learn ping rewrite pong
        //   :learn [x,x] lobe
        if line.starts_with(":learn ") {
            let rest = line[7..].trim();
            if rest.is_empty() {
                println!("usage:");
                println!("  :learn MU rewrite MU");
                println!("  :learn MU {{ra|lobe|sink}}");
                continue;
            }

            let parts: Vec<&str> = rest.split_whitespace().collect();
            if parts.len() < 2 {
                println!("usage:");
                println!("  :learn MU rewrite MU");
                println!("  :learn MU {{ra|lobe|sink}}");
                continue;
            }

            // pattern
            let pat_src = parts[0];
            let pattern: Mu = match parse_mu(pat_src) {
                Ok(mu) => mu,
                Err(e) => {
                    println!("[learn] pattern parse error: {e}");
                    continue;
                }
            };

            if parts.len() == 2 {
                // bucket form: :learn MU bucket
                let target = parts[1].to_lowercase();
                let action = match target.as_str() {
                    "ra" => RuleAction::ToRa,
                    "lobe" | "lobes" => RuleAction::ToLobe,
                    "sink" => RuleAction::ToSink,
                    _ => {
                        println!(
                            "[learn] unknown target `{}` (use ra|lobe|sink or `rewrite`)",
                            target
                        );
                        continue;
                    }
                };

                program.rules.push(RcxRule { pattern, action });
                engine = Engine::new(program.clone());
                println!("[learn] rule added.");
                continue;
            }

            // at least 3 tokens: pattern keyword rhs...
            let keyword = parts[1].to_lowercase();
            if keyword == "rewrite" {
                if parts.len() < 3 {
                    println!("[learn] usage: :learn MU rewrite MU");
                    continue;
                }
                let rhs_src = parts[2];
                let rhs_mu: Mu = match parse_mu(rhs_src) {
                    Ok(mu) => mu,
                    Err(e) => {
                        println!("[learn] rewrite payload parse error: {e}");
                        continue;
                    }
                };
                let action = RuleAction::Rewrite(rhs_mu);
                program.rules.push(RcxRule { pattern, action });
                engine = Engine::new(program.clone());
                println!("[learn] rule added.");
                continue;
            }

            println!(
                "[learn] unknown directive `{}` (use rewrite|ra|lobe|sink)",
                keyword
            );
            continue;
        }

        // :orbit MU [n]
        if line.starts_with(":orbit") {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() < 2 {
                println!("usage: :orbit <Mu> [max_steps]");
                continue;
            }

            let mu_src = parts[1];
            let max_steps = if parts.len() >= 3 {
                parts[2].parse::<usize>().unwrap_or(12)
            } else {
                12
            };

            let seed = match parse_mu(mu_src) {
                Ok(mu) => mu,
                Err(e) => {
                    println!("[orbit] parse error: {e}");
                    continue;
                }
            };

            let seq = orbit(&program, seed.clone(), max_steps);
            println!("[ω] seed: {}", mu_to_string(&seed));
            println!(
                "[ω] orbit ({} states): {}",
                seq.len(),
                bucket_to_string(&seq)
            );
            continue;
        }

        // :omega MU [n]
        if line.starts_with(":omega") {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() < 2 {
                println!("usage: :omega <Mu> [max_steps]");
                continue;
            }

            let mu_src = parts[1];
            let max_steps = if parts.len() >= 3 {
                parts[2].parse::<usize>().unwrap_or(12)
            } else {
                12
            };

            let seed = match parse_mu(mu_src) {
                Ok(mu) => mu,
                Err(e) => {
                    println!("[ω] parse error: {e}");
                    continue;
                }
            };

            let seq = orbit(&program, seed.clone(), max_steps);
            let classification = classify_orbit(&seq);

            println!("[ω] seed: {}", mu_to_string(&seed));
            println!(
                "[ω] orbit ({} states): {}",
                seq.len(),
                bucket_to_string(&seq)
            );
            println!("[ω] classification: {}", classification);

            continue;
        }

        // :save-state NAME  -> save r_a / lobes / sink to snapshots/NAME.state
        if line.starts_with(":save-state ") {
            let name = line[12..].trim();
            if name.is_empty() {
                println!("usage: :save-state NAME");
                continue;
            }

            let path = format!("snapshots/{}.state", name);
            match save_state(&path, &state) {
                Ok(()) => {
                    println!("[save-state] wrote state (r_a/lobes/sink) to {}", path);
                }
                Err(e) => {
                    println!("save-state error: {e}");
                }
            }
            continue;
        }

        // :load-state NAME  -> load r_a / lobes / sink from snapshots/NAME.state
        if line.starts_with(":load-state ") {
            let name = line[12..].trim();
            if name.is_empty() {
                println!("usage: :load-state NAME");
                continue;
            }

            let path = format!("snapshots/{}.state", name);
            match load_state(&path, &mut state) {
                Ok(()) => {
                    println!("[load-state] restored state (r_a/lobes/sink) from {}", path);
                }
                Err(e) => {
                    println!("load-state error: {e}");
                }
            }
            continue;
        }

        // --- Mu evaluation --------------------------------------------------

        match parse_mu(line) {
            Ok(mu) => {
                let route = engine.process_input(&mut state, mu);
                println!("→ route: {:?}", route);
                println!("  r_a:   {}", bucket_to_string(&state.ra));
                println!("  lobes: {}", bucket_to_string(&state.lobes));
                println!("  sink:  {}", bucket_to_string(&state.sink));
            }
            Err(err) => {
                println!("parse error: {err}");
            }
        }
    }
}
