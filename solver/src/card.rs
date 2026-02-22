/// Card encoding: u8 where bits [5:4] = suit, bits [3:0] = value.
/// Suit: S=0, H=1, D=2, C=3
/// Value: A=0, 2=1, 3=2, ..., 10=9, J=10, Q=11, K=12
/// NO_CARD = 0xFF sentinel for empty slots.

pub type Card = u8;
pub type CardSet = u64;

pub const NO_CARD: Card = 0xFF;

pub const SUIT_SPADES: u8 = 0;
pub const SUIT_HEARTS: u8 = 1;
pub const SUIT_DIAMONDS: u8 = 2;
pub const SUIT_CLUBS: u8 = 3;

pub const COLOR_BLACK: u8 = 0;
pub const COLOR_RED: u8 = 1;

pub const NUM_SUITS: usize = 4;
pub const NUM_VALUES: usize = 13;
pub const DECK_SIZE: usize = 52;

#[inline]
pub fn make_card(suit: u8, value: u8) -> Card {
    debug_assert!(suit < 4, "suit must be 0..3");
    debug_assert!(value < 13, "value must be 0..12");
    (suit << 4) | value
}

#[inline]
pub fn card_suit(c: Card) -> u8 {
    c >> 4
}

#[inline]
pub fn card_value(c: Card) -> u8 {
    c & 0x0F
}

/// Color: 0 = black (S, C), 1 = red (H, D)
#[inline]
pub fn card_color(c: Card) -> u8 {
    // Spades=0 (black), Hearts=1 (red), Diamonds=2 (red), Clubs=3 (black)
    // Black: suit 0 or 3 → color 0. Red: suit 1 or 2 → color 1.
    match card_suit(c) {
        SUIT_SPADES | SUIT_CLUBS => COLOR_BLACK,
        _ => COLOR_RED,
    }
}

/// Index of the card in the 52-card deck: suit * 13 + value.
#[inline]
pub fn card_index(c: Card) -> usize {
    (card_suit(c) as usize) * NUM_VALUES + (card_value(c) as usize)
}

/// Construct a Card from its deck index.
#[inline]
pub fn card_from_index(idx: usize) -> Card {
    make_card((idx / NUM_VALUES) as u8, (idx % NUM_VALUES) as u8)
}

// ── CardSet operations ────────────────────────────────────────────────────────

pub const FULL_DECK: CardSet = (1u64 << DECK_SIZE) - 1;

#[inline]
pub fn cardset_contains(set: CardSet, c: Card) -> bool {
    (set >> card_index(c)) & 1 == 1
}

#[inline]
pub fn cardset_add(set: CardSet, c: Card) -> CardSet {
    set | (1u64 << card_index(c))
}

#[inline]
pub fn cardset_remove(set: CardSet, c: Card) -> CardSet {
    set & !(1u64 << card_index(c))
}

#[inline]
pub fn cardset_count(set: CardSet) -> u32 {
    set.count_ones()
}

/// Iterate all cards in the set in ascending index order.
pub fn cardset_iter(set: CardSet) -> impl Iterator<Item = Card> {
    CardSetIter { set }
}

pub struct CardSetIter {
    set: CardSet,
}

impl Iterator for CardSetIter {
    type Item = Card;
    fn next(&mut self) -> Option<Card> {
        if self.set == 0 {
            return None;
        }
        let idx = self.set.trailing_zeros() as usize;
        self.set &= self.set - 1; // clear lowest set bit
        Some(card_from_index(idx))
    }
}

// ── String conversion ─────────────────────────────────────────────────────────

const SUIT_CHARS: [char; 4] = ['S', 'H', 'D', 'C'];
const VALUE_STRS: [&str; 13] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];

/// Format a card as e.g. "SA", "H10", "CK". Panics on NO_CARD.
pub fn card_to_string(c: Card) -> String {
    debug_assert_ne!(c, NO_CARD);
    format!("{}{}", SUIT_CHARS[card_suit(c) as usize], VALUE_STRS[card_value(c) as usize])
}

/// Parse a card string like "SA", "H10", "CK". Returns None on parse failure.
pub fn parse_card(s: &str) -> Option<Card> {
    if s.len() < 2 {
        return None;
    }
    let suit = match s.chars().next()? {
        'S' => SUIT_SPADES,
        'H' => SUIT_HEARTS,
        'D' => SUIT_DIAMONDS,
        'C' => SUIT_CLUBS,
        _ => return None,
    };
    let value_str = &s[1..];
    let value = VALUE_STRS.iter().position(|&v| v == value_str)? as u8;
    Some(make_card(suit, value))
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_all_cards() {
        for suit in 0u8..4 {
            for value in 0u8..13 {
                let c = make_card(suit, value);
                assert_eq!(card_suit(c), suit);
                assert_eq!(card_value(c), value);
                assert_ne!(c, NO_CARD);
            }
        }
    }

    #[test]
    fn card_index_round_trip() {
        for suit in 0u8..4 {
            for value in 0u8..13 {
                let c = make_card(suit, value);
                let idx = card_index(c);
                assert_eq!(card_from_index(idx), c);
            }
        }
    }

    #[test]
    fn parse_and_format() {
        let cases = [("SA", 0, 0), ("H10", 1, 9), ("CK", 3, 12), ("D2", 2, 1)];
        for (s, suit, value) in cases {
            let c = parse_card(s).expect(s);
            assert_eq!(card_suit(c), suit);
            assert_eq!(card_value(c), value);
            assert_eq!(card_to_string(c), s);
        }
    }

    #[test]
    fn colors() {
        assert_eq!(card_color(make_card(SUIT_SPADES, 0)), COLOR_BLACK);
        assert_eq!(card_color(make_card(SUIT_CLUBS, 0)), COLOR_BLACK);
        assert_eq!(card_color(make_card(SUIT_HEARTS, 0)), COLOR_RED);
        assert_eq!(card_color(make_card(SUIT_DIAMONDS, 0)), COLOR_RED);
    }

    #[test]
    fn cardset_ops() {
        let mut set: CardSet = 0;
        let sa = make_card(SUIT_SPADES, 0);
        let hk = make_card(SUIT_HEARTS, 12);
        assert!(!cardset_contains(set, sa));
        set = cardset_add(set, sa);
        set = cardset_add(set, hk);
        assert!(cardset_contains(set, sa));
        assert!(cardset_contains(set, hk));
        assert_eq!(cardset_count(set), 2);
        set = cardset_remove(set, sa);
        assert!(!cardset_contains(set, sa));
        assert_eq!(cardset_count(set), 1);
    }

    #[test]
    fn cardset_iter_order() {
        let sa = make_card(SUIT_SPADES, 0);
        let s2 = make_card(SUIT_SPADES, 1);
        let ha = make_card(SUIT_HEARTS, 0);
        let mut set: CardSet = 0;
        set = cardset_add(set, ha);
        set = cardset_add(set, s2);
        set = cardset_add(set, sa);
        let cards: Vec<Card> = cardset_iter(set).collect();
        // Should be in index order: SA(0), S2(1), HA(13)
        assert_eq!(cards[0], sa);
        assert_eq!(cards[1], s2);
        assert_eq!(cards[2], ha);
    }

    #[test]
    fn full_deck_count() {
        assert_eq!(cardset_count(FULL_DECK), 52);
        assert_eq!(cardset_iter(FULL_DECK).count(), 52);
    }
}
