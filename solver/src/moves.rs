/// Move types and apply_move logic for the OneShot Solitaire solver.

use crate::card::*;
use crate::state::*;

/// All move types, mirroring the Python engine's move format.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Move {
    Draw,
    WasteToFoundation,
    WasteToTableau(u8),        // dest col index
    WasteToStorage(u8),        // dest slot (always first empty)
    TableauToFoundation(u8),   // src col
    TableauToTableau(u8, u8),  // src col, dest col
    TableauToStorage(u8, u8),  // src col, dest slot (always first empty)
    StorageToFoundation(u8),   // src slot
    StorageToTableau(u8, u8),  // src slot, dest col
}

/// Result of applying a move to a BeliefState.
/// Some moves are fully deterministic (no hidden card revealed).
/// Others require branching over the unknown pool.
pub enum ApplyResult {
    /// Move applied fully — new belief state and updated Zobrist hash.
    Complete(BeliefState, u64),
    /// Move applied partially; a face-down tableau card must be revealed.
    /// The caller branches over unknown_pool and assigns the flipped card.
    NeedsFlip {
        partial: BeliefState,
        hash: u64,
        col: u8,
    },
    /// Move is a Draw; the drawn card is unknown.
    /// The caller branches over unknown_pool and assigns the drawn card.
    NeedsDraw {
        partial: BeliefState,
        hash: u64,
    },
}

/// Apply a move to a belief state, returning an ApplyResult.
/// The hash parameter is the current Zobrist hash; it will be updated incrementally.
/// Pass `hash = 0` and ignore the returned hash if you don't use Zobrist hashing yet.
pub fn apply_move(belief: &BeliefState, mv: Move, hash: u64) -> ApplyResult {
    match mv {
        Move::Draw => apply_draw(belief, hash),
        Move::WasteToFoundation => apply_waste_to_foundation(belief, hash),
        Move::WasteToTableau(col) => apply_waste_to_tableau(belief, col, hash),
        Move::WasteToStorage(slot) => apply_waste_to_storage(belief, slot, hash),
        Move::TableauToFoundation(src) => apply_tableau_to_foundation(belief, src, hash),
        Move::TableauToTableau(src, dest) => apply_tableau_to_tableau(belief, src, dest, hash),
        Move::TableauToStorage(src, slot) => apply_tableau_to_storage(belief, src, slot, hash),
        Move::StorageToFoundation(slot) => apply_storage_to_foundation(belief, slot, hash),
        Move::StorageToTableau(slot, dest) => apply_storage_to_tableau(belief, slot, dest, hash),
    }
}

// ── Individual move applications ──────────────────────────────────────────────

fn apply_draw(belief: &BeliefState, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    debug_assert!(b.visible.stock_count > 0);
    b.visible.stock_count -= 1;
    // The drawn card is unknown — caller must branch over unknown_pool.
    ApplyResult::NeedsDraw { partial: b, hash }
}

fn apply_waste_to_foundation(belief: &BeliefState, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.waste_pop();
    let suit = card_suit(card);
    gs.foundation_top[suit as usize] = card;
    ApplyResult::Complete(b, hash)
}

fn apply_waste_to_tableau(belief: &BeliefState, dest_col: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.waste_pop();
    place_on_tableau(gs, card, dest_col);
    ApplyResult::Complete(b, hash)
}

fn apply_waste_to_storage(belief: &BeliefState, slot: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.waste_pop();
    debug_assert_eq!(gs.storage[slot as usize], NO_CARD);
    gs.storage[slot as usize] = card;
    ApplyResult::Complete(b, hash)
}

fn apply_tableau_to_foundation(belief: &BeliefState, src_col: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.tableau_top[src_col as usize];
    debug_assert_ne!(card, NO_CARD);
    let suit = card_suit(card);
    gs.foundation_top[suit as usize] = card;
    gs.tableau_top[src_col as usize] = NO_CARD;
    if gs.tableau_hidden_count[src_col as usize] > 0 {
        gs.tableau_hidden_count[src_col as usize] -= 1;
        ApplyResult::NeedsFlip { partial: b, hash, col: src_col }
    } else {
        gs.tableau_empty[src_col as usize] = true;
        ApplyResult::Complete(b, hash)
    }
}

fn apply_tableau_to_tableau(belief: &BeliefState, src_col: u8, dest_col: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.tableau_top[src_col as usize];
    gs.tableau_top[src_col as usize] = NO_CARD; // tentatively remove
    let needs_flip = if gs.tableau_hidden_count[src_col as usize] > 0 {
        gs.tableau_hidden_count[src_col as usize] -= 1;
        true
    } else {
        gs.tableau_empty[src_col as usize] = true;
        false
    };
    place_on_tableau(gs, card, dest_col);

    if needs_flip {
        ApplyResult::NeedsFlip { partial: b, hash, col: src_col }
    } else {
        ApplyResult::Complete(b, hash)
    }
}

fn apply_tableau_to_storage(belief: &BeliefState, src_col: u8, slot: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.tableau_top[src_col as usize];
    debug_assert_ne!(card, NO_CARD);
    debug_assert_eq!(gs.storage[slot as usize], NO_CARD);
    gs.storage[slot as usize] = card;
    gs.tableau_top[src_col as usize] = NO_CARD;
    if gs.tableau_hidden_count[src_col as usize] > 0 {
        gs.tableau_hidden_count[src_col as usize] -= 1;
        ApplyResult::NeedsFlip { partial: b, hash, col: src_col }
    } else {
        gs.tableau_empty[src_col as usize] = true;
        ApplyResult::Complete(b, hash)
    }
}

fn apply_storage_to_foundation(belief: &BeliefState, slot: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.storage[slot as usize];
    debug_assert_ne!(card, NO_CARD);
    let suit = card_suit(card);
    gs.foundation_top[suit as usize] = card;
    gs.storage[slot as usize] = NO_CARD;
    ApplyResult::Complete(b, hash)
}

fn apply_storage_to_tableau(belief: &BeliefState, slot: u8, dest_col: u8, hash: u64) -> ApplyResult {
    let mut b = belief.clone();
    let gs = &mut b.visible;
    let card = gs.storage[slot as usize];
    debug_assert_ne!(card, NO_CARD);
    gs.storage[slot as usize] = NO_CARD;
    place_on_tableau(gs, card, dest_col);
    ApplyResult::Complete(b, hash)
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/// Place a card on a tableau column, updating the visible state.
fn place_on_tableau(gs: &mut GameState, card: Card, col: u8) {
    gs.tableau_top[col as usize] = card;
    gs.tableau_empty[col as usize] = false;
    // hidden_count stays as-is — we're placing on top of existing face-up card
}

// ── Chance node: assign a revealed card ───────────────────────────────────────

/// Complete a NeedsDraw result by assigning `drawn_card` as the new waste top.
/// Removes drawn_card from the unknown pool.
pub fn assign_drawn_card(partial: &BeliefState, drawn_card: Card, hash: u64) -> (BeliefState, u64) {
    debug_assert!(cardset_contains(partial.unknown_pool, drawn_card));
    let mut b = partial.clone();
    b.visible.waste_push(drawn_card);
    b.unknown_pool = cardset_remove(b.unknown_pool, drawn_card);
    b.check_invariant();
    (b, hash)
}

/// Complete a NeedsFlip result by assigning `flipped_card` as the new face-up top of `col`.
/// Removes flipped_card from the unknown pool.
pub fn assign_flipped_card(partial: &BeliefState, col: u8, flipped_card: Card, hash: u64) -> (BeliefState, u64) {
    debug_assert!(cardset_contains(partial.unknown_pool, flipped_card));
    debug_assert_eq!(partial.visible.tableau_top[col as usize], NO_CARD,
        "col {} should have NO_CARD top when flip needed", col);
    let mut b = partial.clone();
    b.visible.tableau_top[col as usize] = flipped_card;
    b.visible.tableau_empty[col as usize] = false;
    b.unknown_pool = cardset_remove(b.unknown_pool, flipped_card);
    b.check_invariant();
    (b, hash)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_belief(gs: GameState) -> BeliefState {
        BeliefState::from_game_state(gs)
    }

    fn empty_gs() -> GameState {
        GameState {
            tableau_top: [NO_CARD; NUM_TABLEAU_COLS],
            tableau_hidden_count: [0; NUM_TABLEAU_COLS],
            tableau_empty: [true; NUM_TABLEAU_COLS],
            foundation_top: [NO_CARD; NUM_FOUNDATION_PILES],
            storage: [NO_CARD; NUM_STORAGE_SLOTS],
            waste: [NO_CARD; MAX_WASTE],
            waste_len: 0,
            stock_count: 0,
        }
    }

    #[test]
    fn draw_returns_needs_draw() {
        let mut gs = empty_gs();
        gs.stock_count = 5;
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::Draw, 0);
        match result {
            ApplyResult::NeedsDraw { partial, .. } => {
                assert_eq!(partial.visible.stock_count, 4);
            }
            _ => panic!("Expected NeedsDraw"),
        }
    }

    #[test]
    fn waste_to_foundation_complete() {
        let mut gs = empty_gs();
        let sa = make_card(SUIT_SPADES, 0);
        gs.waste_push(sa);
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::WasteToFoundation, 0);
        match result {
            ApplyResult::Complete(new_belief, _) => {
                assert!(new_belief.visible.waste_is_empty());
                assert_eq!(new_belief.visible.foundation_top[SUIT_SPADES as usize], sa);
            }
            _ => panic!("Expected Complete"),
        }
    }

    #[test]
    fn waste_to_tableau_complete() {
        let mut gs = empty_gs();
        let sk = make_card(SUIT_SPADES, 12); // King → can go to empty col
        gs.waste_push(sk);
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::WasteToTableau(0), 0);
        match result {
            ApplyResult::Complete(new_belief, _) => {
                assert!(new_belief.visible.waste_is_empty());
                assert_eq!(new_belief.visible.tableau_top[0], sk);
                assert!(!new_belief.visible.tableau_empty[0]);
            }
            _ => panic!("Expected Complete"),
        }
    }

    #[test]
    fn tableau_to_storage_no_hidden_complete() {
        let mut gs = empty_gs();
        let sq = make_card(SUIT_SPADES, 11);
        gs.tableau_top[0] = sq;
        gs.tableau_empty[0] = false;
        gs.tableau_hidden_count[0] = 0;
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::TableauToStorage(0, 0), 0);
        match result {
            ApplyResult::Complete(new_belief, _) => {
                assert_eq!(new_belief.visible.tableau_top[0], NO_CARD);
                assert!(new_belief.visible.tableau_empty[0]);
                assert_eq!(new_belief.visible.storage[0], sq);
            }
            _ => panic!("Expected Complete"),
        }
    }

    #[test]
    fn tableau_to_foundation_no_hidden_complete() {
        let mut gs = empty_gs();
        let sa = make_card(SUIT_SPADES, 0); // Ace → goes to empty foundation
        gs.tableau_top[0] = sa;
        gs.tableau_empty[0] = false;
        gs.tableau_hidden_count[0] = 0;
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::TableauToFoundation(0), 0);
        match result {
            ApplyResult::Complete(new_belief, _) => {
                assert_eq!(new_belief.visible.tableau_top[0], NO_CARD);
                assert!(new_belief.visible.tableau_empty[0]);
                assert_eq!(new_belief.visible.foundation_top[SUIT_SPADES as usize], sa);
            }
            _ => panic!("Expected Complete"),
        }
    }

    #[test]
    fn tableau_to_foundation_with_hidden_needs_flip() {
        let mut gs = empty_gs();
        let sa = make_card(SUIT_SPADES, 0); // Ace → goes to empty foundation
        gs.tableau_top[1] = sa;
        gs.tableau_empty[1] = false;
        gs.tableau_hidden_count[1] = 2; // 2 face-down cards below
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::TableauToFoundation(1), 0);
        match result {
            ApplyResult::NeedsFlip { partial, col, .. } => {
                assert_eq!(col, 1);
                assert_eq!(partial.visible.tableau_top[1], NO_CARD);
                assert_eq!(partial.visible.tableau_hidden_count[1], 1);
                assert_eq!(partial.visible.foundation_top[SUIT_SPADES as usize], sa);
                // unknown_pool must be preserved (not zeroed)
                assert_eq!(partial.unknown_pool, belief.unknown_pool);
            }
            _ => panic!("Expected NeedsFlip"),
        }
    }

    #[test]
    fn tableau_to_storage_with_hidden_needs_flip() {
        let mut gs = empty_gs();
        let sq = make_card(SUIT_SPADES, 11);
        gs.tableau_top[2] = sq;
        gs.tableau_empty[2] = false;
        gs.tableau_hidden_count[2] = 3; // 3 face-down cards below
        let belief = make_belief(gs);
        let result = apply_move(&belief, Move::TableauToStorage(2, 1), 0);
        match result {
            ApplyResult::NeedsFlip { partial, col, .. } => {
                assert_eq!(col, 2);
                assert_eq!(partial.visible.tableau_top[2], NO_CARD);
                assert_eq!(partial.visible.tableau_hidden_count[2], 2);
                assert_eq!(partial.visible.storage[1], sq);
            }
            _ => panic!("Expected NeedsFlip"),
        }
    }

    #[test]
    fn assign_drawn_card_updates_pool() {
        // Build a partial state simulating a post-Draw state:
        // stock_count=0, waste empty, pool contains exactly the one drawn card (SA).
        let sa = make_card(SUIT_SPADES, 0);
        let gs = empty_gs(); // stock_count=0
        let mut partial = BeliefState {
            visible: gs,
            unknown_pool: cardset_add(0, sa), // pool = {SA} only
        };
        // stock_count=0, hidden_count all 0 → invariant: pool must have 0 cards.
        // But we're simulating a Draw that hasn't resolved yet — stock already decremented,
        // pool still contains the drawn card. After assign_drawn_card removes it, pool=0.
        // We need stock_count=0 for the post-assign invariant (pool=0, stock=0, hidden=0).
        partial.visible.stock_count = 0;
        assert!(cardset_contains(partial.unknown_pool, sa));
        let (new_belief, _) = assign_drawn_card(&partial, sa, 0);
        assert_eq!(new_belief.visible.waste_top(), sa);
        assert!(!cardset_contains(new_belief.unknown_pool, sa));
    }

    #[test]
    fn assign_flipped_card_updates_pool() {
        // Build a partial state simulating a post-remove state for a tableau flip:
        // col 0 has NO_CARD top (just removed), hidden_count=1, pool contains {H5} only.
        // After assign_flipped_card, pool=0, hidden_count stays 1 (already decremented
        // before the flip call), so invariant: pool=0 == stock_count(0) + hidden(0).
        // Wait: after flip, hidden_count is already decremented. Let's use hidden_count=0
        // and pool={H5} so that after removing H5, pool=0 == stock(0)+hidden(0).
        let h5 = make_card(SUIT_HEARTS, 4);
        let mut gs = empty_gs();
        gs.tableau_top[0] = NO_CARD;
        gs.tableau_empty[0] = false;
        gs.tableau_hidden_count[0] = 0; // already decremented before flip
        let partial = BeliefState {
            visible: gs,
            unknown_pool: cardset_add(0, h5), // pool = {H5} only
        };
        // pre-invariant: pool=1, stock=0, hidden=0 → invariant would fail (1 != 0).
        // check_invariant is only called AFTER assign_flipped_card removes h5 from pool.
        // Post: pool=0, stock=0, hidden=0 → invariant satisfied.
        assert!(cardset_contains(partial.unknown_pool, h5));
        let (new_belief, _) = assign_flipped_card(&partial, 0, h5, 0);
        assert_eq!(new_belief.visible.tableau_top[0], h5);
        assert!(!cardset_contains(new_belief.unknown_pool, h5));
    }
}
