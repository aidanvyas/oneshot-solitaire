/// Exact expectimax solver for OneShot Solitaire.
/// Maximises win probability under imperfect information.
/// Chance nodes branch uniformly over all cards in the unknown pool.

use std::time::{Duration, Instant};

use crate::card::*;
use crate::hash::{recompute_hash, ZobristTable};
use crate::moves::{apply_move, assign_drawn_card, assign_flipped_card, ApplyResult, Move};
use crate::state::BeliefState;
use crate::ttable::{TTableEntry, TranspositionTable};

/// Context shared across the entire search tree.
pub struct SearchContext<'a> {
    pub ttable: &'a mut TranspositionTable,
    pub zobrist: &'a ZobristTable,
    pub deadline: Instant,
    pub timed_out: bool,
    pub nodes_visited: u64,
    pub max_depth: u16,
}

impl<'a> SearchContext<'a> {
    pub fn new(
        ttable: &'a mut TranspositionTable,
        zobrist: &'a ZobristTable,
        timeout_ms: u64,
        max_depth: u16,
    ) -> Self {
        SearchContext {
            ttable,
            zobrist,
            deadline: Instant::now() + Duration::from_millis(timeout_ms),
            timed_out: false,
            nodes_visited: 0,
            max_depth,
        }
    }
}

/// Entry point: find the best move and its win probability.
/// Uses iterative deepening — searches at depth 1, 2, 3... until timeout.
/// Returns the best (move, win_probability) found at the deepest complete iteration.
pub fn solve(
    belief: &BeliefState,
    ttable: &mut TranspositionTable,
    zobrist: &ZobristTable,
    timeout_ms: u64,
) -> (Option<Move>, f32, u64, u16) {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);

    let mut best_move: Option<Move> = None;
    let mut best_prob: f32 = 0.0;
    let mut total_nodes: u64 = 0;
    let mut best_depth: u16 = 0;

    for max_depth in 1u16..=u16::MAX {
        if Instant::now() >= deadline {
            break;
        }

        let mut ctx = SearchContext {
            ttable,
            zobrist,
            deadline,
            timed_out: false,
            nodes_visited: 0,
            max_depth,
        };

        let hash = recompute_hash(zobrist, &belief.visible);
        let (mv, prob) = max_node_root(belief, hash, &mut ctx);

        total_nodes += ctx.nodes_visited;

        if !ctx.timed_out {
            best_move = mv;
            best_prob = prob;
            best_depth = max_depth;
        }

        if best_prob >= 1.0 - 1e-6 {
            break; // certain win found
        }
        if best_prob <= 1e-6 && best_depth > 4 {
            break; // likely a forced loss, deeper search won't help
        }
    }

    (best_move, best_prob, total_nodes, best_depth)
}

/// Root max node: returns (best_move, win_probability).
fn max_node_root(belief: &BeliefState, hash: u64, ctx: &mut SearchContext) -> (Option<Move>, f32) {
    if belief.is_won() || belief.is_endgame() {
        return (None, 1.0);
    }

    let moves = belief.legal_moves();
    if moves.is_empty() {
        return (None, 0.0);
    }

    let mut best_move: Option<Move> = moves.first().copied();
    let mut best_prob: f32 = 0.0;

    for &mv in &moves {
        if ctx.timed_out || Instant::now() >= ctx.deadline {
            ctx.timed_out = true;
            break;
        }

        let prob = eval_move(belief, mv, hash, 1, best_prob, ctx);

        if prob > best_prob {
            best_prob = prob;
            best_move = Some(mv);
        }

        if best_prob >= 1.0 - 1e-6 {
            break;
        }
    }

    (best_move, best_prob)
}

/// Max node (solver's choice): returns win probability of the best move.
/// alpha = best win probability found so far among siblings of this node's parent.
fn max_node(belief: &BeliefState, hash: u64, depth: u16, alpha: f32, ctx: &mut SearchContext) -> f32 {
    if ctx.timed_out || Instant::now() >= ctx.deadline {
        ctx.timed_out = true;
        return alpha;
    }

    ctx.nodes_visited += 1;

    // Terminal checks.
    if belief.is_won() || belief.is_endgame() {
        return 1.0;
    }

    let moves = belief.legal_moves();
    if moves.is_empty() {
        return 0.0;
    }

    // Auto-draw: if draw is the only legal move, skip the depth level.
    // It's a forced move — no decision to make, so don't waste depth on it.
    if moves.len() == 1 && moves[0] == Move::Draw {
        let result = apply_move(belief, Move::Draw, hash);
        return match result {
            ApplyResult::NeedsDraw { partial, .. } => {
                chance_node_draw(&partial, depth, alpha, ctx)
            }
            _ => unreachable!("Draw must return NeedsDraw"),
        };
    }

    if depth >= ctx.max_depth {
        return depth_limit_heuristic(belief);
    }

    // Transposition table lookup.
    if let Some(entry) = ctx.ttable.lookup(hash) {
        let e = *entry;
        if e.depth >= ctx.max_depth - depth {
            if e.lower >= 1.0 - 1e-6 {
                return 1.0;
            }
            if e.upper <= 1e-6 {
                return 0.0;
            }
            if e.lower >= alpha {
                return e.lower;
            }
        }
    }

    let mut local_best: f32 = 0.0;

    for &mv in &moves {
        if ctx.timed_out {
            break;
        }

        let prob = eval_move(belief, mv, hash, depth, local_best.max(alpha), ctx);

        if prob > local_best {
            local_best = prob;
        }

        if local_best >= 1.0 - 1e-6 {
            break; // prune: can't do better than a certain win
        }
    }

    // Store in transposition table.
    if !ctx.timed_out {
        ctx.ttable.store(TTableEntry {
            hash,
            lower: local_best,
            upper: local_best,
            depth: ctx.max_depth - depth,
        });
    }

    local_best
}

/// Evaluate a single move from a max node, handling chance nodes if needed.
fn eval_move(
    belief: &BeliefState,
    mv: Move,
    hash: u64,
    depth: u16,
    alpha: f32,
    ctx: &mut SearchContext,
) -> f32 {
    match apply_move(belief, mv, hash) {
        ApplyResult::Complete(new_belief, _) => {
            // Auto-draw: if waste is empty and stock has cards, chain a draw.
            // This mirrors the web UI where playing a waste card auto-draws the next.
            if new_belief.visible.waste.is_empty() && new_belief.visible.stock_count > 0 {
                let draw_result = apply_move(&new_belief, Move::Draw, 0);
                match draw_result {
                    ApplyResult::NeedsDraw { partial, .. } => {
                        chance_node_draw(&partial, depth, alpha, ctx) // same depth — free action
                    }
                    _ => unreachable!(),
                }
            } else {
                let new_hash = recompute_hash(ctx.zobrist, &new_belief.visible);
                max_node(&new_belief, new_hash, depth + 1, alpha, ctx)
            }
        }
        ApplyResult::NeedsDraw { partial, .. } => {
            chance_node_draw(&partial, depth, alpha, ctx)
        }
        ApplyResult::NeedsFlip { partial, col, .. } => {
            chance_node_flip(&partial, col, depth, alpha, ctx)
        }
    }
}

/// Chance node for a stock draw — Star1/Star2 pruning.
/// Branches over all cards in the unknown pool, weighted uniformly.
/// Star1: prune when the upper/lower bound on the average can't affect the parent.
/// Star2: pass tightened alpha to each child for deeper cutoffs inside subtrees.
fn chance_node_draw(
    partial: &BeliefState,
    depth: u16,
    alpha: f32,
    ctx: &mut SearchContext,
) -> f32 {
    let pool = partial.unknown_pool;
    let n = cardset_count(pool);
    if n == 0 {
        return 0.0;
    }

    let cards: Vec<Card> = cardset_iter(pool).collect();
    let n_f64 = n as f64;
    let alpha_f64 = alpha as f64;
    let mut win_sum: f64 = 0.0;
    let mut cards_done: u32 = 0;

    for &drawn_card in &cards {
        if ctx.timed_out {
            break;
        }

        // Star2: derive tightened alpha for this child.
        // For the average to beat alpha, we need:
        //   (win_sum + child_val + remaining_max) / n > alpha
        // So child_val > n*alpha - win_sum - remaining_max
        let remaining_after = (n - cards_done - 1) as f64;
        let child_alpha = (n_f64 * alpha_f64 - win_sum - remaining_after).max(0.0);
        // Clamp to [0, 1] — values outside this range are impossible.
        let child_alpha = child_alpha.min(1.0) as f32;

        let (child_belief, _) = assign_drawn_card(partial, drawn_card, 0);
        let child_hash = recompute_hash(ctx.zobrist, &child_belief.visible);
        let child_prob = max_node(&child_belief, child_hash, depth + 1, child_alpha, ctx) as f64;
        win_sum += child_prob;
        cards_done += 1;

        // Star1 upper-bound prune: even if all remaining children return 1.0,
        // can the average still beat alpha?
        let remaining = (n - cards_done) as f64;
        let upper_bound = (win_sum + remaining) / n_f64;
        if upper_bound <= alpha_f64 + 1e-9 {
            break;
        }

        // Star1 lower-bound prune: even if all remaining children return 0.0,
        // the average is already above 1.0 (guaranteed win — no need to continue).
        let lower_bound = win_sum / n_f64;
        if lower_bound >= 1.0 - 1e-9 {
            break;
        }
    }

    (win_sum / n_f64) as f32
}

/// Chance node for a tableau flip — Star1/Star2 pruning.
/// Branches over all cards in the unknown pool, weighted uniformly.
fn chance_node_flip(
    partial: &BeliefState,
    col: u8,
    depth: u16,
    alpha: f32,
    ctx: &mut SearchContext,
) -> f32 {
    let pool = partial.unknown_pool;
    let n = cardset_count(pool);
    if n == 0 {
        return 0.0;
    }

    let cards: Vec<Card> = cardset_iter(pool).collect();
    let n_f64 = n as f64;
    let alpha_f64 = alpha as f64;
    let mut win_sum: f64 = 0.0;
    let mut cards_done: u32 = 0;

    for &flipped_card in &cards {
        if ctx.timed_out {
            break;
        }

        // Star2: tightened alpha for this child.
        let remaining_after = (n - cards_done - 1) as f64;
        let child_alpha = (n_f64 * alpha_f64 - win_sum - remaining_after).max(0.0);
        let child_alpha = child_alpha.min(1.0) as f32;

        let (child_belief, _) = assign_flipped_card(partial, col, flipped_card, 0);
        let child_hash = recompute_hash(ctx.zobrist, &child_belief.visible);
        let child_prob = max_node(&child_belief, child_hash, depth + 1, child_alpha, ctx) as f64;
        win_sum += child_prob;
        cards_done += 1;

        // Star1 upper-bound prune.
        let remaining = (n - cards_done) as f64;
        let upper_bound = (win_sum + remaining) / n_f64;
        if upper_bound <= alpha_f64 + 1e-9 {
            break;
        }

        // Star1 lower-bound prune.
        let lower_bound = win_sum / n_f64;
        if lower_bound >= 1.0 - 1e-9 {
            break;
        }
    }

    (win_sum / n_f64) as f32
}

/// Heuristic win probability estimate at depth limit.
/// Returns foundation progress as a fraction of 52.
fn depth_limit_heuristic(belief: &BeliefState) -> f32 {
    belief.foundation_count() as f32 / 52.0
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::{GameState, NUM_FOUNDATION_PILES, NUM_STORAGE_SLOTS, NUM_TABLEAU_COLS};
    use crate::ttable::TranspositionTable;

    fn empty_gs() -> GameState {
        GameState {
            tableau_top: [NO_CARD; NUM_TABLEAU_COLS],
            tableau_hidden_count: [0; NUM_TABLEAU_COLS],
            tableau_empty: [true; NUM_TABLEAU_COLS],
            foundation_top: [NO_CARD; NUM_FOUNDATION_PILES],
            storage: [NO_CARD; NUM_STORAGE_SLOTS],
            waste: vec![],
            stock_count: 0,
        }
    }

    #[test]
    fn already_won_returns_1() {
        let mut gs = empty_gs();
        for suit in 0..4u8 {
            gs.foundation_top[suit as usize] = make_card(suit, 12); // King
        }
        let belief = BeliefState::from_game_state(gs);
        let zt = ZobristTable::new();
        let mut tt = TranspositionTable::new(10000);
        let (mv, prob, _, _) = solve(&belief, &mut tt, &zt, 1000);
        assert!(mv.is_none());
        assert!((prob - 1.0).abs() < 1e-6);
    }

    #[test]
    fn dead_position_returns_0() {
        // No moves, not won → loss
        let gs = empty_gs();
        let belief = BeliefState::from_game_state(gs);
        let zt = ZobristTable::new();
        let mut tt = TranspositionTable::new(10000);
        let (mv, prob, _, _) = solve(&belief, &mut tt, &zt, 1000);
        assert!(mv.is_none());
        assert!((prob - 0.0).abs() < 1e-6);
    }

    #[test]
    fn trivial_win_one_move() {
        // All 51 cards on foundations, one card (SK) left in waste, foundations have S through Q
        // This is an endgame position — auto-complete detects it immediately.
        let mut gs = empty_gs();
        gs.foundation_top[0] = make_card(SUIT_SPADES, 11); // SQ
        gs.foundation_top[1] = make_card(SUIT_HEARTS, 12); // HK
        gs.foundation_top[2] = make_card(SUIT_DIAMONDS, 12); // DK
        gs.foundation_top[3] = make_card(SUIT_CLUBS, 12); // CK
        let sk = make_card(SUIT_SPADES, 12);
        gs.waste.push(sk);
        gs.stock_count = 0;
        let belief = BeliefState::from_game_state(gs);
        let zt = ZobristTable::new();
        let mut tt = TranspositionTable::new(10000);
        let (mv, prob, _, _) = solve(&belief, &mut tt, &zt, 5000);
        // Endgame detected at root — no move returned, but win probability is 1.0.
        assert!(mv.is_none());
        assert!((prob - 1.0).abs() < 1e-6);
    }

    #[test]
    fn endgame_returns_1() {
        // All cards face-up, stock empty, waste has 1 card — trivially winnable.
        let mut gs = empty_gs();
        gs.foundation_top[0] = make_card(SUIT_SPADES, 11); // SQ on foundation
        gs.foundation_top[1] = make_card(SUIT_HEARTS, 12); // HK
        gs.foundation_top[2] = make_card(SUIT_DIAMONDS, 12); // DK
        gs.foundation_top[3] = make_card(SUIT_CLUBS, 12); // CK
        gs.tableau_top[0] = make_card(SUIT_SPADES, 12); // SK on tableau, no hidden
        gs.tableau_empty[0] = false;
        let belief = BeliefState::from_game_state(gs);
        assert!(belief.is_endgame());
        let zt = ZobristTable::new();
        let mut tt = TranspositionTable::new(10000);
        let (_, prob, nodes, _) = solve(&belief, &mut tt, &zt, 1000);
        assert!((prob - 1.0).abs() < 1e-6);
        assert_eq!(nodes, 0); // Should detect endgame before any search
    }
}
