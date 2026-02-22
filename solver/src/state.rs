/// Game state and belief state for the OneShot Solitaire solver.
/// GameState holds only what a human player can observe.
/// BeliefState adds the unknown card pool for probabilistic reasoning.

use crate::card::*;
use crate::moves::Move;

pub const NUM_TABLEAU_COLS: usize = 7;
pub const NUM_STORAGE_SLOTS: usize = 4;
pub const NUM_FOUNDATION_PILES: usize = 4;
pub const CARDS_PER_SUIT: u8 = 13;

/// Maximum cards in the waste pile (24 stock + up to 7 from initial deal top = 24 max drawn).
/// Actually stock has exactly 24 cards, so waste can have at most 24 cards.
pub const MAX_WASTE: usize = 24;

/// Visible game state — everything a human player can observe.
#[derive(Clone, Debug)]
pub struct GameState {
    /// Face-up top card of each tableau column. NO_CARD if column is completely empty.
    pub tableau_top: [Card; NUM_TABLEAU_COLS],
    /// Number of face-down cards below the face-up top in each column.
    /// 0 means the column has only the face-up top (or is empty).
    pub tableau_hidden_count: [u8; NUM_TABLEAU_COLS],
    /// True if the column has no cards at all (neither face-up nor face-down).
    pub tableau_empty: [bool; NUM_TABLEAU_COLS],
    /// Top card of each foundation pile indexed by suit (S=0,H=1,D=2,C=3).
    /// NO_CARD if the foundation is empty.
    pub foundation_top: [Card; NUM_FOUNDATION_PILES],
    /// Storage slot contents. NO_CARD if slot is empty.
    pub storage: [Card; NUM_STORAGE_SLOTS],
    /// Full waste pile, bottom→top. Last element is the currently visible waste top.
    pub waste: Vec<Card>,
    /// Number of cards remaining in the stock (hidden).
    pub stock_count: u8,
}

impl GameState {
    /// Total number of cards on foundations (all piles combined).
    pub fn foundation_count(&self) -> u32 {
        self.foundation_top.iter().map(|&top| {
            if top == NO_CARD { 0 } else { card_value(top) as u32 + 1 }
        }).sum()
    }

    /// True if all four foundations are complete (K on top of each).
    pub fn is_won(&self) -> bool {
        self.foundation_top.iter().all(|&top| {
            top != NO_CARD && card_value(top) == CARDS_PER_SUIT - 1
        })
    }

    /// The visible waste top card, or NO_CARD if waste is empty.
    pub fn waste_top(&self) -> Card {
        self.waste.last().copied().unwrap_or(NO_CARD)
    }
}

/// Belief state: visible state + the pool of cards whose identity is unknown.
/// unknown_pool is the set of all cards in the stock + face-down tableau positions.
/// Invariant: unknown_pool.count_ones() == stock_count + sum(tableau_hidden_count)
#[derive(Clone, Debug)]
pub struct BeliefState {
    pub visible: GameState,
    /// Bit set of all cards not yet revealed to the player.
    pub unknown_pool: CardSet,
}

impl BeliefState {
    /// Build a BeliefState from a GameState by computing the unknown pool.
    /// unknown_pool = all 52 cards minus all currently visible cards.
    pub fn from_game_state(gs: GameState) -> Self {
        let pool = build_unknown_pool(&gs);
        BeliefState { visible: gs, unknown_pool: pool }
    }

    /// Assert the invariant: unknown_pool count must equal total hidden cards.
    #[cfg(debug_assertions)]
    pub fn check_invariant(&self) {
        let expected: u32 = self.visible.stock_count as u32
            + self.visible.tableau_hidden_count.iter().map(|&c| c as u32).sum::<u32>();
        assert_eq!(
            cardset_count(self.unknown_pool), expected,
            "Belief state invariant violated: pool={}, expected={}",
            cardset_count(self.unknown_pool), expected
        );
    }

    #[cfg(not(debug_assertions))]
    pub fn check_invariant(&self) {}

    /// True when the game is trivially winnable: stock empty, all tableau
    /// face-up, waste has at most 1 card, and there is at least one card
    /// outside foundation to play. Matches Python engine's is_endgame().
    pub fn is_endgame(&self) -> bool {
        let gs = &self.visible;
        if gs.stock_count > 0 { return false; }
        if gs.waste.len() > 1 { return false; }
        if !gs.tableau_hidden_count.iter().all(|&c| c == 0) { return false; }
        // Must have at least one card outside foundation (otherwise it's a
        // dead position, not an endgame). is_won() is checked separately.
        !gs.waste.is_empty()
            || gs.tableau_top.iter().any(|&c| c != NO_CARD)
            || gs.storage.iter().any(|&c| c != NO_CARD)
    }

    /// Total foundation cards.
    pub fn foundation_count(&self) -> u32 {
        self.visible.foundation_count()
    }

    /// True if game is won.
    pub fn is_won(&self) -> bool {
        self.visible.is_won()
    }

    /// Generate all legal moves from this belief state (mirrors Python engine exactly).
    pub fn legal_moves(&self) -> Vec<Move> {
        let mut moves = Vec::new();
        let gs = &self.visible;

        // Order: foundation moves first (best), then tableau/storage moves, draw last.
        // This avoids needing an expensive sort in the search.

        // 1. All foundation moves (highest priority — always good)
        let waste_top = gs.waste_top();
        if waste_top != NO_CARD {
            let suit = card_suit(waste_top);
            if is_valid_foundation_move(waste_top, suit, gs) {
                moves.push(Move::WasteToFoundation);
            }
        }
        for src_col in 0..NUM_TABLEAU_COLS as u8 {
            let card = gs.tableau_top[src_col as usize];
            if card != NO_CARD {
                let suit = card_suit(card);
                if is_valid_foundation_move(card, suit, gs) {
                    moves.push(Move::TableauToFoundation(src_col));
                }
            }
        }
        for slot in 0..NUM_STORAGE_SLOTS as u8 {
            let card = gs.storage[slot as usize];
            if card != NO_CARD {
                let suit = card_suit(card);
                if is_valid_foundation_move(card, suit, gs) {
                    moves.push(Move::StorageToFoundation(slot));
                }
            }
        }

        // 2. Tableau → tableau (may uncover hidden cards)
        for src_col in 0..NUM_TABLEAU_COLS as u8 {
            let card = gs.tableau_top[src_col as usize];
            if card == NO_CARD {
                continue;
            }
            let is_lone = gs.tableau_hidden_count[src_col as usize] == 0;
            for dest_col in 0..NUM_TABLEAU_COLS as u8 {
                if src_col == dest_col {
                    continue;
                }
                if !is_valid_tableau_move(card, dest_col, gs) {
                    continue;
                }
                if is_lone
                    && card_value(card) == CARDS_PER_SUIT - 1
                    && gs.tableau_top[dest_col as usize] == NO_CARD
                    && gs.tableau_empty[dest_col as usize]
                {
                    continue;
                }
                moves.push(Move::TableauToTableau(src_col, dest_col));
            }
        }

        // 3. Storage → tableau
        for slot in 0..NUM_STORAGE_SLOTS as u8 {
            let card = gs.storage[slot as usize];
            if card == NO_CARD {
                continue;
            }
            for dest_col in 0..NUM_TABLEAU_COLS as u8 {
                if is_valid_tableau_move(card, dest_col, gs) {
                    moves.push(Move::StorageToTableau(slot, dest_col));
                }
            }
        }

        // 4. Tableau → storage (first empty slot only)
        for src_col in 0..NUM_TABLEAU_COLS as u8 {
            let card = gs.tableau_top[src_col as usize];
            if card == NO_CARD {
                continue;
            }
            for slot in 0..NUM_STORAGE_SLOTS as u8 {
                if gs.storage[slot as usize] == NO_CARD {
                    moves.push(Move::TableauToStorage(src_col, slot));
                    break;
                }
            }
        }

        // 5. Waste → tableau
        if waste_top != NO_CARD {
            for col in 0..NUM_TABLEAU_COLS as u8 {
                if is_valid_tableau_move(waste_top, col, gs) {
                    moves.push(Move::WasteToTableau(col));
                }
            }
            // Waste → first empty storage slot only
            for slot in 0..NUM_STORAGE_SLOTS as u8 {
                if gs.storage[slot as usize] == NO_CARD {
                    moves.push(Move::WasteToStorage(slot));
                    break;
                }
            }
        }

        // 6. Draw (lowest priority — only if stock non-empty)
        if gs.stock_count > 0 {
            moves.push(Move::Draw);
        }

        moves
    }
}

// ── Move validation helpers ───────────────────────────────────────────────────

/// Check if a card can go to the foundation of its suit.
/// foundation_idx must equal the card's suit (suit-specific foundations).
pub fn is_valid_foundation_move(card: Card, foundation_idx: u8, gs: &GameState) -> bool {
    debug_assert_ne!(card, NO_CARD);
    if foundation_idx as usize >= NUM_FOUNDATION_PILES {
        return false;
    }
    // Foundation index must match card's suit
    if card_suit(card) != foundation_idx {
        return false;
    }
    let top = gs.foundation_top[foundation_idx as usize];
    if top == NO_CARD {
        card_value(card) == 0 // Ace starts the pile
    } else {
        card_suit(card) == card_suit(top) && card_value(card) == card_value(top) + 1
    }
}

/// Check if a card can be placed on a tableau column.
pub fn is_valid_tableau_move(card: Card, dest_col: u8, gs: &GameState) -> bool {
    debug_assert_ne!(card, NO_CARD);
    if dest_col as usize >= NUM_TABLEAU_COLS {
        return false;
    }
    let top = gs.tableau_top[dest_col as usize];
    if top == NO_CARD {
        // Empty column: only Kings
        gs.tableau_empty[dest_col as usize] && card_value(card) == CARDS_PER_SUIT - 1
    } else {
        // Opposite color, one rank lower
        card_color(card) != card_color(top) && card_value(card) + 1 == card_value(top)
    }
}

// ── Unknown pool construction ─────────────────────────────────────────────────

/// Build the unknown card pool from a visible game state.
/// unknown_pool = all 52 cards − visible cards (foundations, waste, tableau tops, storage).
pub fn build_unknown_pool(gs: &GameState) -> CardSet {
    let mut known: CardSet = 0;

    // Foundation contents: for suit s with top value v, cards A..=v of suit s are known.
    for suit in 0..NUM_FOUNDATION_PILES as u8 {
        let top = gs.foundation_top[suit as usize];
        if top != NO_CARD {
            let top_val = card_value(top);
            for v in 0..=top_val {
                known = cardset_add(known, make_card(suit, v));
            }
        }
    }

    // Full waste pile — all cards are visible.
    for &c in &gs.waste {
        known = cardset_add(known, c);
    }

    // Tableau face-up tops.
    for col in 0..NUM_TABLEAU_COLS {
        let top = gs.tableau_top[col];
        if top != NO_CARD {
            known = cardset_add(known, top);
        }
    }

    // Storage slots.
    for &c in &gs.storage {
        if c != NO_CARD {
            known = cardset_add(known, c);
        }
    }

    FULL_DECK & !known
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_game_state() -> GameState {
        GameState {
            tableau_top: [NO_CARD; NUM_TABLEAU_COLS],
            tableau_hidden_count: [0; NUM_TABLEAU_COLS],
            tableau_empty: [true; NUM_TABLEAU_COLS],
            foundation_top: [NO_CARD; NUM_FOUNDATION_PILES],
            storage: [NO_CARD; NUM_STORAGE_SLOTS],
            waste: vec![],
            stock_count: 52,
        }
    }

    #[test]
    fn unknown_pool_empty_game() {
        // All 52 cards in stock → unknown pool = full deck
        let gs = empty_game_state();
        let pool = build_unknown_pool(&gs);
        assert_eq!(cardset_count(pool), 52);
        assert_eq!(pool, FULL_DECK);
    }

    #[test]
    fn unknown_pool_with_visible_cards() {
        let mut gs = empty_game_state();
        // Put SA on waste
        let sa = make_card(SUIT_SPADES, 0);
        gs.waste.push(sa);
        gs.stock_count = 51;
        // Put H2 on tableau top col 0
        let h2 = make_card(SUIT_HEARTS, 1);
        gs.tableau_top[0] = h2;
        gs.tableau_empty[0] = false;

        let pool = build_unknown_pool(&gs);
        assert_eq!(cardset_count(pool), 50);
        assert!(!cardset_contains(pool, sa));
        assert!(!cardset_contains(pool, h2));
    }

    #[test]
    fn unknown_pool_with_foundation() {
        let mut gs = empty_game_state();
        // Spades foundation up to 3 (A,2,3 are known = 3 cards)
        let s3 = make_card(SUIT_SPADES, 2); // value index 2 = "3"
        gs.foundation_top[SUIT_SPADES as usize] = s3;
        gs.stock_count = 49;

        let pool = build_unknown_pool(&gs);
        assert_eq!(cardset_count(pool), 49); // 52 - 3
        assert!(!cardset_contains(pool, make_card(SUIT_SPADES, 0))); // SA
        assert!(!cardset_contains(pool, make_card(SUIT_SPADES, 1))); // S2
        assert!(!cardset_contains(pool, make_card(SUIT_SPADES, 2))); // S3
        assert!(cardset_contains(pool, make_card(SUIT_SPADES, 3)));  // S4 unknown
    }

    #[test]
    fn is_won_all_kings() {
        let mut gs = empty_game_state();
        gs.stock_count = 0;
        for suit in 0..4u8 {
            gs.foundation_top[suit as usize] = make_card(suit, 12); // King
        }
        assert!(gs.is_won());
    }

    #[test]
    fn foundation_count() {
        let mut gs = empty_game_state();
        // Spades: A,2,3 (3 cards), Hearts: A (1 card)
        gs.foundation_top[0] = make_card(SUIT_SPADES, 2);
        gs.foundation_top[1] = make_card(SUIT_HEARTS, 0);
        assert_eq!(gs.foundation_count(), 4);
    }

    #[test]
    fn tableau_move_empty_col_only_king() {
        let gs = empty_game_state();
        let king = make_card(SUIT_SPADES, 12);
        let queen = make_card(SUIT_HEARTS, 11);
        assert!(is_valid_tableau_move(king, 0, &gs));
        assert!(!is_valid_tableau_move(queen, 0, &gs));
    }

    #[test]
    fn tableau_move_stacking_rules() {
        let mut gs = empty_game_state();
        // Col 0 has red 7 on top
        let rh7 = make_card(SUIT_HEARTS, 6); // Hearts 7, red
        gs.tableau_top[0] = rh7;
        gs.tableau_empty[0] = false;

        let black6 = make_card(SUIT_SPADES, 5); // Spades 6, black → valid
        let red6 = make_card(SUIT_HEARTS, 5);   // Hearts 6, red → invalid
        let black8 = make_card(SUIT_CLUBS, 7);  // Clubs 8, black → invalid (not one lower)

        assert!(is_valid_tableau_move(black6, 0, &gs));
        assert!(!is_valid_tableau_move(red6, 0, &gs));
        assert!(!is_valid_tableau_move(black8, 0, &gs));
    }

    #[test]
    fn foundation_move_ace_only_on_empty() {
        let gs = empty_game_state();
        let sa = make_card(SUIT_SPADES, 0);
        let s2 = make_card(SUIT_SPADES, 1);
        assert!(is_valid_foundation_move(sa, SUIT_SPADES, &gs));
        assert!(!is_valid_foundation_move(s2, SUIT_SPADES, &gs));
    }

    #[test]
    fn foundation_move_sequential() {
        let mut gs = empty_game_state();
        gs.foundation_top[SUIT_SPADES as usize] = make_card(SUIT_SPADES, 0); // SA
        let s2 = make_card(SUIT_SPADES, 1);
        let s3 = make_card(SUIT_SPADES, 2);
        assert!(is_valid_foundation_move(s2, SUIT_SPADES, &gs));
        assert!(!is_valid_foundation_move(s3, SUIT_SPADES, &gs));
    }

    #[test]
    fn legal_moves_draw_only() {
        let mut gs = empty_game_state();
        gs.stock_count = 5;
        let belief = BeliefState::from_game_state(gs);
        let moves = belief.legal_moves();
        assert_eq!(moves, vec![Move::Draw]);
    }

    #[test]
    fn legal_moves_no_draw_when_stock_empty() {
        let mut gs = empty_game_state();
        gs.stock_count = 0; // no stock, no waste, all empty → no moves
        let belief = BeliefState::from_game_state(gs);
        let moves = belief.legal_moves();
        assert!(moves.is_empty());
    }

    #[test]
    fn legal_moves_waste_to_foundation() {
        let mut gs = empty_game_state();
        gs.stock_count = 0;
        let sa = make_card(SUIT_SPADES, 0);
        gs.waste.push(sa);
        let belief = BeliefState::from_game_state(gs);
        let moves = belief.legal_moves();
        assert!(moves.contains(&Move::WasteToFoundation));
    }

    #[test]
    fn legal_moves_only_first_empty_storage() {
        let mut gs = empty_game_state();
        gs.stock_count = 0;
        let hq = make_card(SUIT_HEARTS, 11); // Hearts Queen — won't go to foundation or tableau
        gs.waste.push(hq);
        // All storage empty
        let belief = BeliefState::from_game_state(gs);
        let moves = belief.legal_moves();
        // Should have exactly one storage move: slot 0 (first empty)
        let storage_moves: Vec<_> = moves.iter()
            .filter(|m| matches!(m, Move::WasteToStorage(_)))
            .collect();
        assert_eq!(storage_moves.len(), 1);
        assert_eq!(*storage_moves[0], Move::WasteToStorage(0));
    }
}
