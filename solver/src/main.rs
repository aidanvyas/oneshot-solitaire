/// OneShot Solitaire exact expectimax solver.
/// Reads JSON requests from stdin, writes JSON responses to stdout.
/// One request per line; one response per line.

mod card;
mod expectimax;
mod hash;
mod moves;
mod protocol;
mod state;
mod ttable;

use std::io::{self, BufRead, Write};

use expectimax::solve;
use hash::ZobristTable;
use protocol::{move_to_json, parse_game_state, SolverRequest, SolverResponse};
use state::BeliefState;
use ttable::TranspositionTable;

const TTABLE_SIZE: usize = 2_000_000;

fn handle_request(req: SolverRequest, zt: &ZobristTable, tt: &mut TranspositionTable) -> SolverResponse {
    let gs = match parse_game_state(&req.game_state) {
        Ok(gs) => gs,
        Err(e) => return SolverResponse::error_response(format!("Failed to parse game state: {}", e)),
    };

    let belief = BeliefState::from_game_state(gs);

    // Quick terminal checks before spinning up the full search.
    if belief.is_won() {
        return SolverResponse {
            best_move: None,
            win_probability: 1.0,
            nodes_visited: 0,
            depth_reached: 0,
            timed_out: false,
            error: None,
        };
    }

    let legal = belief.legal_moves();
    if legal.is_empty() {
        return SolverResponse {
            best_move: None,
            win_probability: 0.0,
            nodes_visited: 0,
            depth_reached: 0,
            timed_out: false,
            error: None,
        };
    }

    let timeout_ms = req.timeout_ms.max(1);
    let (best_move, win_prob, nodes, depth) = solve(&belief, tt, zt, timeout_ms);

    let timed_out = depth == 0; // no complete iteration finished

    // If we timed out before completing depth 1, pick first legal move as fallback.
    let effective_move = if best_move.is_none() && !legal.is_empty() {
        Some(legal[0])
    } else {
        best_move
    };

    SolverResponse {
        best_move: effective_move.map(|mv| move_to_json(mv, &belief.visible)),
        win_probability: win_prob,
        nodes_visited: nodes,
        depth_reached: depth,
        timed_out,
        error: None,
    }
}

fn run() {
    let stdin = io::stdin();
    let stdout = io::stdout();

    let zt = ZobristTable::new();
    let mut tt = TranspositionTable::new(TTABLE_SIZE);

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(e) => {
                eprintln!("Error reading stdin: {}", e);
                break;
            }
        };

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        // Support a simple cache-clear command.
        if trimmed == r#"{"type":"clear_cache"}"# {
            tt.clear();
            let resp = r#"{"cleared":true}"#;
            writeln!(stdout.lock(), "{}", resp).ok();
            continue;
        }

        let response = match serde_json::from_str::<SolverRequest>(trimmed) {
            Ok(req) => handle_request(req, &zt, &mut tt),
            Err(e) => SolverResponse::error_response(format!("JSON parse error: {}", e)),
        };

        let json = match serde_json::to_string(&response) {
            Ok(j) => j,
            Err(e) => {
                eprintln!("Failed to serialize response: {}", e);
                continue;
            }
        };

        let mut out = stdout.lock();
        if let Err(e) = writeln!(out, "{}", json) {
            eprintln!("Failed to write response: {}", e);
            break;
        }
        let _ = out.flush();
    }
}

fn main() {
    // Spawn the main logic on a thread with a larger stack (64 MB)
    // to support deep recursion from the dynamic depth limit.
    let builder = std::thread::Builder::new().stack_size(64 * 1024 * 1024);
    let handler = builder.spawn(run).expect("Failed to spawn solver thread");
    handler.join().expect("Solver thread panicked");
}
