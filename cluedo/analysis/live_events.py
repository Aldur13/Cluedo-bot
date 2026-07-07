"""Live, in-game (not post-game) event extraction shared by the Recent
Deductions and Timeline sidebar cards.

Built only from real solver facts -- confirmed-card diffs between
consecutive replay snapshots -- never an invented probability or guess,
matching this project's "never invent information" rule (see
cluedo.analysis.game_review's docstring for the same rule applied
post-game). Read-only consumer of cluedo.game/cluedo.models/cluedo.history,
kept under the cluedo.analysis prefix so tests/test_architecture_boundaries.py
continues to guarantee the solver core never depends on it.
"""
from __future__ import annotations

from dataclasses import dataclass

from cluedo.game import GameState
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE, Card


@dataclass(frozen=True)
class ConfirmedCardEvent:
    turn: int  # 1-indexed suggestion number that produced this confirmation
    card: Card
    owner_id: str


def owner_display_name(game_state: GameState, owner_id: str) -> str:
    """Human-readable name for a raw owner-id string (a seat's `owner_id`
    or the ENVELOPE sentinel) -- a plain lookup, never a guess."""
    if owner_id == ENVELOPE:
        return "the envelope"
    for player in game_state.players:
        if player.owner_id == owner_id:
            return player.name
    return owner_id


def confirmed_card_events(game_state: GameState) -> list[ConfirmedCardEvent]:
    """One event per (turn, card) where `card` became confirmed for the
    first time strictly after that turn's suggestion, in turn order. A
    single suggestion can confirm several cards at once (e.g. pigeonhole
    forcing); each becomes its own event. Cards already confirmed before
    any suggestion was made (i.e. purely from the user's starting hand) are
    not events -- there is no deduction to report for those.
    """
    snapshots = build_replay_snapshots(game_state)
    if not snapshots:
        return []

    known: set[Card] = set(snapshots[0].game_state.engine.confirmed.keys())
    events: list[ConfirmedCardEvent] = []
    for turn in range(1, len(snapshots)):
        confirmed = snapshots[turn].game_state.engine.confirmed
        for card, owner_id in confirmed.items():
            if card not in known:
                known.add(card)
                events.append(ConfirmedCardEvent(turn, card, owner_id))
    return events


def turns_with_new_confirmations(game_state: GameState) -> set[int]:
    """Turn numbers (1-indexed) that produced at least one new confirmed
    card -- the "major events" a Timeline card should show, as opposed to
    every single suggestion."""
    return {event.turn for event in confirmed_card_events(game_state)}
