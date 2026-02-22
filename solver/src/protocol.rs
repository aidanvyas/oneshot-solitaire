/// JSON serialization/deserialization for the solver's stdin/stdout protocol.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::card::*;
use crate::moves::Move;
use crate::state::{GameState, NUM_FOUNDATION_PILES, NUM_STORAGE_SLOTS, NUM_TABLEAU_COLS};

// ── Input types ───────────────────────────────────────────────────────────────

#[derive(Deserialize, Debug)]
pub struct SolverRequest {
    pub game_state: GameStateJson,
    pub timeout_ms: u64,
}

#[derive(Deserialize, Debug)]
pub struct TableauColJson {
    pub hidden_count: u8,
    pub top: Option<String>, // card string or null
}

#[derive(Deserialize, Debug)]
pub struct GameStateJson {
    pub tableau: Vec<TableauColJson>,
    /// Map from suit letter ("S","H","D","C") to top card string or null.
    pub foundations: HashMap<String, Option<String>>,
    /// Storage slots (null = empty).
    pub storage: Vec<Option<String>>,
    /// Waste pile from bottom to top.
    pub waste: Vec<String>,
    pub stock_count: u8,
}

// ── Output types ──────────────────────────────────────────────────────────────

#[derive(Serialize, Debug)]
pub struct SolverResponse {
    pub best_move: Option<MoveJson>,
    pub win_probability: f32,
    pub nodes_visited: u64,
    pub depth_reached: u16,
    pub timed_out: bool,
    pub error: Option<String>,
}

impl SolverResponse {
    pub fn error_response(msg: impl Into<String>) -> Self {
        SolverResponse {
            best_move: None,
            win_probability: 0.0,
            nodes_visited: 0,
            depth_reached: 0,
            timed_out: false,
            error: Some(msg.into()),
        }
    }
}

/// JSON representation of a move — matches Python engine move format.
#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum MoveJson {
    Draw,
    Foundation,
    Tableau { col: u8 },
    Storage { slot: u8 },
    Move { src: [serde_json::Value; 2], dest: [serde_json::Value; 2] },
}

// ── Conversion: JSON → GameState ──────────────────────────────────────────────

pub fn parse_game_state(json: &GameStateJson) -> Result<GameState, String> {
    if json.tableau.len() != NUM_TABLEAU_COLS {
        return Err(format!("Expected {} tableau columns, got {}", NUM_TABLEAU_COLS, json.tableau.len()));
    }
    if json.storage.len() != NUM_STORAGE_SLOTS {
        return Err(format!("Expected {} storage slots, got {}", NUM_STORAGE_SLOTS, json.storage.len()));
    }

    let mut tableau_top = [NO_CARD; NUM_TABLEAU_COLS];
    let mut tableau_hidden_count = [0u8; NUM_TABLEAU_COLS];
    let mut tableau_empty = [false; NUM_TABLEAU_COLS];

    for (i, col) in json.tableau.iter().enumerate() {
        tableau_hidden_count[i] = col.hidden_count;
        match &col.top {
            Some(s) => {
                tableau_top[i] = parse_card(s)
                    .ok_or_else(|| format!("Invalid tableau card: {}", s))?;
                tableau_empty[i] = false;
            }
            None => {
                tableau_top[i] = NO_CARD;
                // Empty if no hidden cards either
                tableau_empty[i] = col.hidden_count == 0;
            }
        }
    }

    // Foundations: map suit letter → foundation index (S=0,H=1,D=2,C=3)
    let suit_order = ["S", "H", "D", "C"];
    let mut foundation_top = [NO_CARD; NUM_FOUNDATION_PILES];
    for (i, suit) in suit_order.iter().enumerate() {
        match json.foundations.get(*suit) {
            Some(Some(s)) => {
                foundation_top[i] = parse_card(s)
                    .ok_or_else(|| format!("Invalid foundation card: {}", s))?;
            }
            Some(None) | None => {
                foundation_top[i] = NO_CARD;
            }
        }
    }

    // Storage
    let mut storage = [NO_CARD; NUM_STORAGE_SLOTS];
    for (i, slot) in json.storage.iter().enumerate() {
        storage[i] = match slot {
            Some(s) => parse_card(s).ok_or_else(|| format!("Invalid storage card: {}", s))?,
            None => NO_CARD,
        };
    }

    // Waste pile
    let mut waste = Vec::with_capacity(json.waste.len());
    for s in &json.waste {
        waste.push(parse_card(s).ok_or_else(|| format!("Invalid waste card: {}", s))?);
    }

    Ok(GameState {
        tableau_top,
        tableau_hidden_count,
        tableau_empty,
        foundation_top,
        storage,
        waste,
        stock_count: json.stock_count,
    })
}

// ── Conversion: Move → MoveJson ───────────────────────────────────────────────

/// Convert a Move to its JSON representation.
/// `gs` is needed to look up the actual suit of tableau cards for foundation moves.
pub fn move_to_json(mv: Move, gs: &GameState) -> MoveJson {
    use serde_json::json;
    match mv {
        Move::Draw => MoveJson::Draw,
        Move::WasteToFoundation => MoveJson::Foundation,
        Move::WasteToTableau(col) => MoveJson::Tableau { col },
        Move::WasteToStorage(slot) => MoveJson::Storage { slot },
        Move::TableauToFoundation(src) => {
            let card = gs.tableau_top[src as usize];
            let suit_idx = card_suit(card);
            MoveJson::Move {
                src: [json!("tableau"), json!(src)],
                dest: [json!("foundation"), json!(suit_idx)],
            }
        }
        Move::TableauToTableau(src, dest) => MoveJson::Move {
            src: [json!("tableau"), json!(src)],
            dest: [json!("tableau"), json!(dest)],
        },
        Move::TableauToStorage(src, slot) => MoveJson::Move {
            src: [json!("tableau"), json!(src)],
            dest: [json!("storage"), json!(slot)],
        },
        Move::StorageToFoundation(slot) => {
            let card = gs.storage[slot as usize];
            let suit_idx = card_suit(card);
            MoveJson::Move {
                src: [json!("storage"), json!(slot)],
                dest: [json!("foundation"), json!(suit_idx)],
            }
        }
        Move::StorageToTableau(slot, dest) => MoveJson::Move {
            src: [json!("storage"), json!(slot)],
            dest: [json!("tableau"), json!(dest)],
        },
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_request_json(stock_count: u8, waste: Vec<&str>) -> GameStateJson {
        GameStateJson {
            tableau: (0..NUM_TABLEAU_COLS).map(|_| TableauColJson { hidden_count: 0, top: None }).collect(),
            foundations: [("S", None), ("H", None), ("D", None), ("C", None)]
                .iter()
                .map(|(s, v)| (s.to_string(), v.clone()))
                .collect(),
            storage: vec![None; NUM_STORAGE_SLOTS],
            waste: waste.iter().map(|s| s.to_string()).collect(),
            stock_count,
        }
    }

    #[test]
    fn parse_empty_state() {
        let json = make_request_json(24, vec![]);
        let gs = parse_game_state(&json).unwrap();
        assert_eq!(gs.stock_count, 24);
        assert!(gs.waste.is_empty());
        assert!(gs.foundation_top.iter().all(|&t| t == NO_CARD));
    }

    #[test]
    fn parse_waste() {
        let json = make_request_json(0, vec!["SA", "H10"]);
        let gs = parse_game_state(&json).unwrap();
        assert_eq!(gs.waste.len(), 2);
        assert_eq!(gs.waste[0], parse_card("SA").unwrap());
        assert_eq!(gs.waste[1], parse_card("H10").unwrap());
    }

    #[test]
    fn parse_foundation() {
        let mut json = make_request_json(0, vec![]);
        json.foundations.insert("S".to_string(), Some("S3".to_string()));
        let gs = parse_game_state(&json).unwrap();
        let s3 = parse_card("S3").unwrap();
        assert_eq!(gs.foundation_top[SUIT_SPADES as usize], s3);
    }

    #[test]
    fn parse_tableau_with_hidden() {
        let mut json = make_request_json(0, vec![]);
        json.tableau[2] = TableauColJson { hidden_count: 3, top: Some("HK".to_string()) };
        let gs = parse_game_state(&json).unwrap();
        assert_eq!(gs.tableau_hidden_count[2], 3);
        assert_eq!(gs.tableau_top[2], parse_card("HK").unwrap());
        assert!(!gs.tableau_empty[2]);
    }

    fn empty_gs() -> GameState {
        use crate::state::{NUM_FOUNDATION_PILES, NUM_STORAGE_SLOTS, NUM_TABLEAU_COLS};
        use crate::card::NO_CARD;
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
    fn move_to_json_draw() {
        let gs = empty_gs();
        let j = move_to_json(Move::Draw, &gs);
        assert!(matches!(j, MoveJson::Draw));
    }

    #[test]
    fn move_to_json_waste_foundation() {
        let gs = empty_gs();
        let j = move_to_json(Move::WasteToFoundation, &gs);
        assert!(matches!(j, MoveJson::Foundation));
    }

    #[test]
    fn move_to_json_waste_tableau() {
        let gs = empty_gs();
        let j = move_to_json(Move::WasteToTableau(3), &gs);
        assert!(matches!(j, MoveJson::Tableau { col: 3 }));
    }
}
