# Solver Optimizations

Tracking each optimization's impact on search depth and node throughput.

Benchmark position (opening): 7 tableau columns with hidden cards, empty foundations, 24 stock cards, 45 total unknowns.

Mid-game position: 12 total unknowns (stock=10, 2 hidden tableau cards), 4 aces on foundations.

## Baseline (naive expectimax, no pruning)

All chance node children evaluated. Alpha passed as 0.0 to children (no window tightening).

| Timeout | Depth | Nodes (opening) |
|---------|-------|-----------------|
| 100ms   | 2     | 85,740          |
| 500ms   | 3     | 409,803         |
| 1,000ms | 3     | 917,018         |
| 5,000ms | 3     | 4,122,065       |

## 1. Star1/Star2 chance-node pruning

**Star1**: After evaluating k of n chance-node children, compute upper bound = (sum + remaining) / n. If upper bound <= alpha, prune remaining children. Also prune if lower bound >= 1.0.

**Star2**: Pass tightened alpha to each child: child_alpha = (n * alpha - sum - remaining_after) clamped to [0, 1]. Causes more cutoffs inside each child's subtree.

| Timeout | Depth | Nodes (opening) | vs baseline         |
|---------|-------|-----------------|----------------------|
| 100ms   | 3     | 424,184         | depth 2->3 at 100ms  |
| 500ms   | 3     | 1,723,576       | 4.2x more nodes      |
| 1,000ms | 3     | 3,754,342       | 4.1x more nodes      |
| 5,000ms | 3     | 16,852,680      | 4.1x more nodes      |

Mid-game (12 unknowns):

| Timeout | Depth | Nodes   |
|---------|-------|---------|
| 100ms   | 3     | 287,251 |
| 500ms   | 4     | 761,154 |
| 1,000ms | 4     | 1,372,127 |
| 5,000ms | 4     | 7,895,139 |

**Impact**: ~4x node throughput improvement. Depth 2->3 at 100ms (opening), depth 3->4 at 500ms (mid-game).

## 2. TT move ordering + optimized legal_moves order (reverted)

**TT move ordering**: Put the transposition table's best move from the previous iteration first. This sets a strong alpha early, causing more cutoffs in sibling subtrees.

**legal_moves() reorder**: Generate moves in static priority order (foundation first, draw last) so no sort is needed at each node. TT best move is swapped to position 0 with a single `swap()` — no Vec allocation or sort.

**Auto-draw (forced)**: When draw is the only legal move, skip the depth level entirely. It's a forced move with no decision, so don't waste depth on it.

| Timeout | Depth | Nodes (opening) | vs Star1/Star2      |
|---------|-------|-----------------|----------------------|
| 100ms   | 2     | 347,758         | ~same throughput     |
| 500ms   | 3     | 1,652,537       | ~same throughput     |
| 1,000ms | 3     | 3,326,613       | ~same throughput     |
| 5,000ms | 3     | 14,775,242      | ~same throughput     |

**Impact**: TT move ordering adds per-node overhead (HashMap lookup) but doesn't improve pruning enough to offset. Net throughput similar or slightly worse. `best_move` field removed from TTableEntry; TT is now value-cache only.

**Status**: TT move ordering removed. Static legal_moves priority order and forced-draw auto-draw retained.

## 3. Auto-draw chaining + auto-complete + remove effective_depth_limit

Three changes applied together:

**Auto-draw chaining**: After any move that empties the waste while stock > 0, auto-chain a draw at the same depth (free action — no depth cost). Mirrors the web UI behavior where playing a waste card auto-draws the next. The drawn card is unknown, so it branches into a chance node. The forced-draw check (draw-only-move skips depth) is retained separately.

**Auto-complete**: When `is_endgame()` is true (stock empty, all tableau face-up, waste ≤ 1 card, at least one card outside foundation), immediately return 1.0. The position is trivially winnable — all cards are directly accessible, so they can always be moved to foundation in rank order. Checked at the top of `max_node` and `max_node_root`, before any search.

**Remove effective_depth_limit**: Previously, positions with 0 unknowns got unlimited depth (u16::MAX/2). This is now unnecessary — auto-complete handles the endgame case directly (returns 1.0 with zero search), and the base depth limit is sufficient for all other cases.

Opening position (SA/H3/D5/CJ/S8/H10/DK tableau tops, 0-6 hidden, 24 stock):

| Timeout | Depth | Nodes (opening) | vs Star1/Star2      |
|---------|-------|-----------------|----------------------|
| 100ms   | 2     | 147,000         | new benchmark pos    |
| 500ms   | 3     | 598,000         | new benchmark pos    |
| 1,000ms | 3     | 1,109,000       | new benchmark pos    |
| 5,000ms | 3     | 5,220,000       | new benchmark pos    |

Mid-game (S5/H7/D9/CJ/SK tops, 2 hidden, 10 stock, 4 aces on foundation):

| Timeout | Depth | Nodes   |
|---------|-------|---------|
| 100ms   | 3     | 95,000  |
| 500ms   | 3     | 367,000 |
| 1,000ms | 4     | 1,250,000 |
| 5,000ms | 4     | 9,062,000 |

**Impact**: Raw node throughput is lower because auto-draw chains an extra `apply_move` + chance-node evaluation for every move that empties the waste, making each "node" do more work. But effective depth is equivalent or better — the solver covers the same search space with fewer depth levels since play-waste-card + draw counts as one action, not two. Auto-complete eliminates all endgame search (0 nodes for trivially winnable positions). Note: opening-position node counts are not directly comparable to previous benchmarks because the specific card arrangement differs and significantly affects branching.

## Attempted: Auto-foundation sweep (reverted)

**Idea**: Automatically move all eligible cards to foundation inside the search tree, collapsing obvious foundation moves into zero depth. Tried aggressive (all eligible) and safe (FreeCell rule: only when no card needs it for stacking).

**Result**: Both versions regressed performance — the sweep runs at every node in the tree, adding overhead that far exceeds savings from skipping foundation moves. Aggressive version also removes strategic choices from the solver (keeping cards for tableau building can be better than auto-founding).

| Version | 100ms nodes | 500ms nodes |
|---------|-------------|-------------|
| Star1/Star2 only | 424k | 1.7M |
| + aggressive auto-found | 327k | 1.6M |
| + safe auto-found | 261k | 850k |

**Status**: Removed. Auto-foundation is not free — the per-node overhead dominates.

## Not yet implemented

### Suit isomorphism

At chance nodes, group unknown cards whose suits are in perfectly symmetric positions. Evaluate one representative per group, weight by group size.

Requirements for two suits to be interchangeable:
- Same color (black: spades/clubs, red: hearts/diamonds)
- Same foundation height
- Every visible card of suit A has a mirror card of suit B at the same position

**Expected impact**: 10-20% reduction in chance-node evaluations in favorable positions. Limited by how quickly suit symmetry breaks as cards are revealed.

## Game results (10 games, 200ms timeout)

| Solver version | Win rate | Avg foundation cards |
|----------------|----------|---------------------|
| Baseline       | 0%       | 5.6/52              |
| Star1/Star2    | TBD      | TBD                 |
