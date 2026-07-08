"""Replay-snapshot and what-if helpers built on GameState.from_history.

GameState itself already owns the core rebuild-from-scratch primitive (used
internally for undo/edit/delete). This module adds the two GUI-facing
conveniences layered on top of it: precomputed replay snapshots for scrubbing
through a finished game, and a scratch what-if branch that never touches the
live game.
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass

from cluedo.game import GameState
from cluedo.models import Suggestion


@dataclass
class ReplaySnapshot:
    step_index: int
    game_state: GameState

# GameState -> (mutation_seq, snapshots). Weak keys, so an entry dies with its
# GameState -- unlike an id()-keyed cache (tried and reverted once), where a
# garbage-collected GameState's reused memory address could collide with a
# later, unrelated GameState and silently serve it another game's snapshots.
# Weak references cannot collide that way: the key IS the live object.
_snapshot_cache: "weakref.WeakKeyDictionary[GameState, tuple[int, list[ReplaySnapshot]]]" = (
    weakref.WeakKeyDictionary()
)


def build_replay_snapshots(game_state: GameState) -> list[ReplaySnapshot]:
    """Precompute one GameState per history prefix length 0..len(history), once,
    up front. Scrubbing afterward is then O(1) array indexing -- no
    recomputation while the user drags the timeline slider.

    Cached per GameState instance, invalidated by `mutation_seq` (which exists
    exactly for this -- see its docstring in game.py). Many independent
    consumers replay the whole game on every dashboard refresh (sheet-grid
    change highlights, recent deductions, timeline, live stats, per-opponent
    pattern analysis); sharing one replay per mutation here keeps a
    mid/late-game refresh from costing several seconds of redundant solver
    reruns on the Tk main thread. Returns a fresh list each call (the
    ReplaySnapshot entries themselves are shared and treated as read-only).
    """
    cached = _snapshot_cache.get(game_state)
    if cached is not None and cached[0] == game_state.mutation_seq:
        return list(cached[1])

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

    _snapshot_cache[game_state] = (game_state.mutation_seq, snapshots)
    return list(snapshots)


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
