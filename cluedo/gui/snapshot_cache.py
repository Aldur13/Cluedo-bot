"""Caches history.build_replay_snapshots() results keyed off
GameState._mutation_seq, so the change-tracking ledger, the graphs panel, and
pattern analysis -- all of which replay the whole game -- share one replay
per mutation instead of each independently re-replaying it."""
from __future__ import annotations

from cluedo.game import GameState
from cluedo.history import ReplaySnapshot, build_replay_snapshots


class SnapshotCache:
    def __init__(self) -> None:
        self._key: tuple[int, int] | None = None
        self._snapshots: list[ReplaySnapshot] = []

    def get(self, game_state: GameState) -> list[ReplaySnapshot]:
        # Keyed on (identity, mutation_seq) rather than mutation_seq alone --
        # loading a different save resets mutation_seq back to 0, and without
        # the identity check that would collide with a still-cached seq==0
        # entry from the *previous* game and silently return stale snapshots.
        key = (id(game_state), game_state.mutation_seq)
        if key != self._key:
            self._snapshots = build_replay_snapshots(game_state)
            self._key = key
        return self._snapshots
