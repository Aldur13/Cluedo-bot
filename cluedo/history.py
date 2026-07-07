"""Replay-snapshot and what-if helpers built on GameState.from_history.

GameState itself already owns the core rebuild-from-scratch primitive (used
internally for undo/edit/delete). This module adds the two GUI-facing
conveniences layered on top of it: precomputed replay snapshots for scrubbing
through a finished game, and a scratch what-if branch that never touches the
live game.
"""
from __future__ import annotations

from dataclasses import dataclass

from cluedo.game import GameState
from cluedo.models import Suggestion


@dataclass
class ReplaySnapshot:
    step_index: int
    game_state: GameState


def build_replay_snapshots(game_state: GameState) -> list[ReplaySnapshot]:
    """Precompute one GameState per history prefix length 0..len(history), once,
    up front. Scrubbing afterward is then O(1) array indexing -- no
    recomputation while the user drags the timeline slider.

    Deliberately uncached here: an earlier version of this function added a
    module-level (id(game_state), mutation_seq) cache slot, but `id()` gets
    reused once a garbage-collected GameState's memory is freed -- in a
    long-lived process (or a test suite creating many short-lived
    GameStates) that let an unrelated, later GameState collide on the same
    (id, mutation_seq) key and silently receive another game's stale
    snapshots. cluedo.gui.snapshot_cache.SnapshotCache solves this correctly
    with a *per-instance* cache (each consumer owns its own slot, so there's
    no cross-object collision risk) -- callers that want caching should use
    that, not a global here.
    """
    snapshots = []
    for i in range(len(game_state.history) + 1):
        snap = GameState.from_history(
            game_state.config,
            game_state.players,
            game_state.user_seat,
            game_state._initial_hand,
            game_state.history[:i],
        )
        snapshots.append(ReplaySnapshot(i, snap))

    return snapshots


def whatif_game_state(live: GameState, hypothetical: Suggestion) -> GameState:
    """Builds a scratch GameState reflecting live.history + one hypothetical
    suggestion, without mutating `live` in any way. Raises ContradictionError
    if the hypothetical is logically impossible given prior facts -- which is
    itself useful information (it proves a player *must* show)."""
    return GameState.from_history(
        live.config,
        live.players,
        live.user_seat,
        live._initial_hand,
        live.history + [hypothetical],
    )
