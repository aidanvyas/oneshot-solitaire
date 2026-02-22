/// Transposition table for the expectimax solver.
/// Stores win probability bounds per visible game state hash.

use std::collections::HashMap;

#[derive(Clone, Copy, Debug)]
pub struct TTableEntry {
    /// Zobrist hash of the state (for collision detection).
    pub hash: u64,
    /// Lower bound on win probability from this state.
    pub lower: f32,
    /// Upper bound on win probability from this state.
    pub upper: f32,
    /// Search depth at which this entry was computed.
    pub depth: u16,
}

pub struct TranspositionTable {
    table: HashMap<u64, TTableEntry>,
    max_entries: usize,
    hits: u64,
    stores: u64,
}

impl TranspositionTable {
    pub fn new(max_entries: usize) -> Self {
        TranspositionTable {
            table: HashMap::with_capacity(max_entries.min(1 << 20)),
            max_entries,
            hits: 0,
            stores: 0,
        }
    }

    pub fn lookup(&mut self, hash: u64) -> Option<&TTableEntry> {
        if let Some(entry) = self.table.get(&hash) {
            self.hits += 1;
            Some(entry)
        } else {
            None
        }
    }

    /// Store an entry. Uses depth-preferred replacement: keep deeper entries.
    pub fn store(&mut self, entry: TTableEntry) {
        // Always prefer deeper entries over shallower ones.
        if let Some(existing) = self.table.get(&entry.hash) {
            if existing.depth >= entry.depth {
                return; // keep the deeper existing entry
            }
        } else if self.table.len() >= self.max_entries {
            // Table full and no existing entry for this hash — skip to avoid
            // unbounded memory growth. A real implementation would use a fixed-size
            // array with open addressing.
            return;
        }
        self.table.insert(entry.hash, entry);
        self.stores += 1;
    }

    pub fn clear(&mut self) {
        self.table.clear();
        self.hits = 0;
        self.stores = 0;
    }

    pub fn len(&self) -> usize {
        self.table.len()
    }

    pub fn hits(&self) -> u64 { self.hits }
    pub fn stores(&self) -> u64 { self.stores }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_and_lookup() {
        let mut tt = TranspositionTable::new(1000);
        let entry = TTableEntry {
            hash: 12345,
            lower: 0.3,
            upper: 0.8,
            depth: 5,
        };
        tt.store(entry);
        let found = tt.lookup(12345);
        assert!(found.is_some());
        let e = found.unwrap();
        assert!((e.lower - 0.3).abs() < 1e-6);
        assert!((e.upper - 0.8).abs() < 1e-6);
        assert_eq!(e.depth, 5);
    }

    #[test]
    fn lookup_missing() {
        let mut tt = TranspositionTable::new(1000);
        assert!(tt.lookup(99999).is_none());
    }

    #[test]
    fn depth_preferred_replacement() {
        let mut tt = TranspositionTable::new(1000);
        let e1 = TTableEntry { hash: 1, lower: 0.1, upper: 0.9, depth: 10 };
        let e2 = TTableEntry { hash: 1, lower: 0.5, upper: 0.5, depth: 5 };
        tt.store(e1);
        tt.store(e2); // shallower — should be ignored
        let found = tt.lookup(1).unwrap();
        assert_eq!(found.depth, 10); // original kept
    }

    #[test]
    fn clear_resets() {
        let mut tt = TranspositionTable::new(1000);
        tt.store(TTableEntry { hash: 1, lower: 0.0, upper: 1.0, depth: 1 });
        tt.clear();
        assert_eq!(tt.len(), 0);
        assert!(tt.lookup(1).is_none());
    }
}
