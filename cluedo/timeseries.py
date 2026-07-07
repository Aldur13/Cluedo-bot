"""Pure time-series data computed from a already-built list of replay
snapshots (`cluedo.history.build_replay_snapshots`). This module is a
read-only consumer of `GameState`/`SolverStats`/`card_probabilities()` -- it
never feeds anything back into the solver and never modifies `game.py`,
`engine.py`, or `probability.py`.

Deliberately decoupled from *how* the snapshot list was produced: callers
pass in `snapshots: list[ReplaySnapshot]` directly rather than a `GameState`
this module would replay itself. In particular this module must never import
`cluedo.gui.snapshot_cache` (or anything else under `cluedo.gui`) -- that
would be a backwards layering dependency from pure core into the GUI layer.
The GUI's `SnapshotCache` is exactly what's expected to build/cache the list
these functions consume.

No matplotlib import anywhere in this file -- rendering lives in the
(separately built) `cluedo/gui/graph_panel.py`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from cluedo.models import ENVELOPE, Card
from cluedo.probability import TooManyAmbiguousCardsError

if TYPE_CHECKING:
    from cluedo.history import ReplaySnapshot


def worlds_over_time(snapshots: list["ReplaySnapshot"]) -> list[Optional[int]]:
    """One entry per snapshot (index 0..N, inclusive of the pre-suggestion-0
    snapshot), each snapshot's
    `game_state.last_solver_stats.valid_worlds_last_counted`.

    `last_solver_stats` itself is never `None` -- `ConstraintEngine.recompute()`
    always runs during `GameState.__init__`/`from_history`, so every replayed
    snapshot has a `SolverStats` instance. `valid_worlds_last_counted` is the
    part that's `Optional[int]`: it stays `None` when the solver never reached
    the world-counting step for that snapshot (e.g. too many ambiguous cards
    to enumerate, per `probability.TooManyAmbiguousCardsError`'s gate). We
    pass that `None` straight through rather than guessing a substitute value,
    since "unknown" is a more honest signal to a graph than a fabricated
    number.
    """
    return [snap.game_state.last_solver_stats.valid_worlds_last_counted for snap in snapshots]


def envelope_probability_over_time(snapshots: list["ReplaySnapshot"], card: Card) -> list[Optional[float]]:
    """One probability-of-being-in-the-envelope value per snapshot for the
    given card, i.e. `game_state.card_probabilities().get(card, {}).get(ENVELOPE, 0.0)`
    evaluated at each historical point.

    `card_probabilities()` raises `TooManyAmbiguousCardsError` when a snapshot
    doesn't have few enough ambiguous cards left to compute exact
    probabilities. Fallback choice (documented here since the caller/grapher
    needs to know it): on that error we append `None` for that snapshot,
    exactly like `worlds_over_time`'s existing `Optional[int]` convention for
    "not computed" -- rather than repeating the last known value, which would
    silently invent data and could make a graph look like the probability
    plateaued when really it was simply never computed. Callers that want a
    connected line (e.g. the matplotlib panel) can interpolate/forward-fill
    on their side, but this module never does that itself so the "real value"
    vs "we don't know" distinction survives.
    """
    values: list[Optional[float]] = []
    for snap in snapshots:
        try:
            probs = snap.game_state.card_probabilities()
        except TooManyAmbiguousCardsError:
            values.append(None)
            continue
        values.append(probs.get(card, {}).get(ENVELOPE, 0.0))
    return values


def info_gained_per_turn(snapshots: list["ReplaySnapshot"]) -> list[float]:
    """One value per turn transition (length N for an N-snapshot-transition
    list, i.e. one less than `len(snapshots)`): the fraction of valid worlds
    eliminated by that turn's suggestion,
    `1 - (worlds_after / worlds_before)`, when both `worlds_before` and
    `worlds_after` are known (not `None`) and `worlds_before > 0`; else `0.0`.

    This is the same "expected info gain" concept `advisor.py` uses for its
    rationale text, but computed after the fact from what the responses
    actually revealed, rather than as a pre-suggestion hypothetical average
    over possible outcomes.
    """
    worlds = worlds_over_time(snapshots)
    gains: list[float] = []
    for before, after in zip(worlds, worlds[1:]):
        if before is None or after is None or before <= 0:
            gains.append(0.0)
        else:
            gains.append(1.0 - (after / before))
    return gains


def solver_progress_over_time(snapshots: list["ReplaySnapshot"]) -> list[int]:
    """One entry per snapshot: how many cards are confirmed at that point
    (`len(snapshot.game_state.engine.confirmed)`). Monotonically
    non-decreasing across a real game, since `ConstraintEngine.confirmed`
    only ever grows (see `engine.py`'s own carried-forward-facts comment) and
    each snapshot is an independent from-scratch rebuild of a longer history
    prefix.
    """
    return [len(snap.game_state.engine.confirmed) for snap in snapshots]
