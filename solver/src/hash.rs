/// Zobrist hashing for visible game state.
/// Uses a compile-time fixed seed LCG to generate independent random u64s.
/// Only the visible state is hashed — hidden card counts are hashed by count, not identity.

use crate::card::*;
use crate::state::*;

// ── LCG for generating Zobrist table entries at startup ───────────────────────

const LCG_MULTIPLIER: u64 = 6364136223846793005;
const LCG_INCREMENT: u64 = 1442695040888963407;
const LCG_SEED: u64 = 0xDEAD_BEEF_CAFE_BABE;

struct Lcg(u64);

impl Lcg {
    fn new(seed: u64) -> Self { Lcg(seed) }
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_mul(LCG_MULTIPLIER).wrapping_add(LCG_INCREMENT);
        self.0
    }
}

// ── Zobrist table ─────────────────────────────────────────────────────────────

/// Table dimensions:
/// - waste_pile[pos][card]: card at position pos in waste pile (bottom=0, pos < 24)
/// - tableau_top[col][card+1]: face-up top card (card=0..51 → index 1..52, 0=NO_CARD)
/// - tableau_hidden[col][count]: count of hidden cards in col (0..=28 max)
/// - foundation_top[suit][value+1]: top foundation card (value=0..12, 0=NO_CARD)
/// - storage[slot][card+1]: storage card (0=NO_CARD)
/// - stock_count[count]: stock count (0..=24)
pub struct ZobristTable {
    pub waste_pile: Box<[[u64; DECK_SIZE]; 24]>,
    pub waste_empty: u64,
    pub tableau_top: Box<[[u64; DECK_SIZE + 1]; NUM_TABLEAU_COLS]>,  // index 0 = NO_CARD
    pub tableau_hidden: Box<[[u64; 29]; NUM_TABLEAU_COLS]>,           // max 7 hidden per col
    pub foundation_top: Box<[[u64; 14]; NUM_FOUNDATION_PILES]>,       // index 0 = NO_CARD, 1..=13 = A..K
    pub storage: Box<[[u64; DECK_SIZE + 1]; NUM_STORAGE_SLOTS]>,      // index 0 = NO_CARD
    pub stock_count: Box<[u64; 25]>,                                   // 0..=24
}

impl ZobristTable {
    pub fn new() -> Self {
        let mut lcg = Lcg::new(LCG_SEED);
        let mut g = move || lcg.next();

        let mut waste_pile = Box::new([[0u64; DECK_SIZE]; 24]);
        for pos in 0..24 {
            for card in 0..DECK_SIZE {
                waste_pile[pos][card] = g();
            }
        }
        let waste_empty = g();

        let mut tableau_top = Box::new([[0u64; DECK_SIZE + 1]; NUM_TABLEAU_COLS]);
        for col in 0..NUM_TABLEAU_COLS {
            for card_idx in 0..=DECK_SIZE {
                tableau_top[col][card_idx] = g();
            }
        }

        let mut tableau_hidden = Box::new([[0u64; 29]; NUM_TABLEAU_COLS]);
        for col in 0..NUM_TABLEAU_COLS {
            for count in 0..29 {
                tableau_hidden[col][count] = g();
            }
        }

        let mut foundation_top = Box::new([[0u64; 14]; NUM_FOUNDATION_PILES]);
        for suit in 0..NUM_FOUNDATION_PILES {
            for val_idx in 0..14 {
                foundation_top[suit][val_idx] = g();
            }
        }

        let mut storage = Box::new([[0u64; DECK_SIZE + 1]; NUM_STORAGE_SLOTS]);
        for slot in 0..NUM_STORAGE_SLOTS {
            for card_idx in 0..=DECK_SIZE {
                storage[slot][card_idx] = g();
            }
        }

        let mut stock_count = Box::new([0u64; 25]);
        for count in 0..25 {
            stock_count[count] = g();
        }

        ZobristTable {
            waste_pile,
            waste_empty,
            tableau_top,
            tableau_hidden,
            foundation_top,
            storage,
            stock_count,
        }
    }

    /// Map a card to its table index (1-based so 0 = NO_CARD).
    #[inline]
    fn card_idx(c: Card) -> usize {
        if c == NO_CARD { 0 } else { card_index(c) + 1 }
    }

    /// Compute the full Zobrist hash of a GameState from scratch.
    pub fn hash_state(&self, gs: &GameState) -> u64 {
        let mut h: u64 = 0;

        // Waste pile
        if gs.waste_len == 0 {
            h ^= self.waste_empty;
        } else {
            for (pos, &card) in gs.waste[..gs.waste_len as usize].iter().enumerate() {
                h ^= self.waste_pile[pos][card_index(card)];
            }
        }

        // Tableau
        for col in 0..NUM_TABLEAU_COLS {
            h ^= self.tableau_top[col][Self::card_idx(gs.tableau_top[col])];
            h ^= self.tableau_hidden[col][gs.tableau_hidden_count[col] as usize];
        }

        // Foundations
        for suit in 0..NUM_FOUNDATION_PILES {
            let top = gs.foundation_top[suit];
            let val_idx = if top == NO_CARD { 0 } else { card_value(top) as usize + 1 };
            h ^= self.foundation_top[suit][val_idx];
        }

        // Storage
        for slot in 0..NUM_STORAGE_SLOTS {
            h ^= self.storage[slot][Self::card_idx(gs.storage[slot])];
        }

        // Stock count
        h ^= self.stock_count[gs.stock_count as usize];

        h
    }
}

impl Default for ZobristTable {
    fn default() -> Self { Self::new() }
}

// ── Incremental hash update builders ─────────────────────────────────────────
// These are helpers to XOR out old state and XOR in new state for O(1) updates.
// For now we recompute from scratch after each move (correct, just not O(1)).
// Incremental updates can be added as an optimization pass later.

/// Recompute hash for a new GameState (O(1) amortized is possible but not yet implemented).
pub fn recompute_hash(zt: &ZobristTable, gs: &GameState) -> u64 {
    zt.hash_state(gs)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

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
    fn hash_is_deterministic() {
        let zt = ZobristTable::new();
        let gs = empty_gs();
        let h1 = zt.hash_state(&gs);
        let h2 = zt.hash_state(&gs);
        assert_eq!(h1, h2);
    }

    #[test]
    fn hash_differs_on_different_states() {
        let zt = ZobristTable::new();
        let mut gs1 = empty_gs();
        let mut gs2 = empty_gs();
        gs1.stock_count = 5;
        gs2.stock_count = 6;
        assert_ne!(zt.hash_state(&gs1), zt.hash_state(&gs2));
    }

    #[test]
    fn hash_differs_waste_vs_no_waste() {
        let zt = ZobristTable::new();
        let mut gs1 = empty_gs();
        let mut gs2 = empty_gs();
        gs2.waste_push(make_card(SUIT_SPADES, 0));
        assert_ne!(zt.hash_state(&gs1), zt.hash_state(&gs2));
        // Also: empty waste uses waste_empty, non-empty uses positional hashes
        let h_empty = zt.hash_state(&gs1);
        gs1.waste_push(make_card(SUIT_HEARTS, 5));
        let h_nonempty = zt.hash_state(&gs1);
        assert_ne!(h_empty, h_nonempty);
    }

    #[test]
    fn hash_same_visible_state_different_order_differs() {
        // Two states with same top of waste but different waste history
        // must have different hashes (different unknown pool).
        let zt = ZobristTable::new();
        let sa = make_card(SUIT_SPADES, 0);
        let h2 = make_card(SUIT_HEARTS, 1);

        let mut gs1 = empty_gs();
        gs1.waste_push(sa);
        gs1.waste_push(h2);

        let mut gs2 = empty_gs();
        gs2.waste_push(h2);
        gs2.waste_push(sa);

        assert_ne!(zt.hash_state(&gs1), zt.hash_state(&gs2));
    }

    #[test]
    fn hash_foundation_count() {
        let zt = ZobristTable::new();
        let mut gs = empty_gs();
        let h0 = zt.hash_state(&gs);
        gs.foundation_top[0] = make_card(SUIT_SPADES, 0); // SA
        let h1 = zt.hash_state(&gs);
        gs.foundation_top[0] = make_card(SUIT_SPADES, 1); // S2
        let h2 = zt.hash_state(&gs);
        assert_ne!(h0, h1);
        assert_ne!(h1, h2);
        assert_ne!(h0, h2);
    }

    #[test]
    fn tableau_hidden_count_affects_hash() {
        let zt = ZobristTable::new();
        let mut gs1 = empty_gs();
        let mut gs2 = empty_gs();
        let card = make_card(SUIT_HEARTS, 10);
        gs1.tableau_top[0] = card;
        gs1.tableau_hidden_count[0] = 2;
        gs1.tableau_empty[0] = false;
        gs2.tableau_top[0] = card;
        gs2.tableau_hidden_count[0] = 3;
        gs2.tableau_empty[0] = false;
        assert_ne!(zt.hash_state(&gs1), zt.hash_state(&gs2));
    }
}
