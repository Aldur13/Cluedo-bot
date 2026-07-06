"""Suggestion advisor: a cheap uncertainty heuristic prunes the ~324 possible
(suspect, weapon, room) triples down to a handful, then those survivors get
fully scored by expected information gain -- the probability-weighted
fraction of currently-valid game states each outcome would eliminate. This
keeps the advisor both fast and, for the triples it actually reports,
mathematically exact about the "eliminates ~X%" claim it displays.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from cluedo.history import whatif_game_state
from cluedo.models import ENVELOPE, Card, CardType, Suggestion, SuggestionResponse, seat_id
from cluedo.probability import count_worlds, probability_of_response_outcome

if TYPE_CHECKING:
    from cluedo.game import GameState


@dataclass(frozen=True)
class AdvisorCandidate:
    suspect: Card
    weapon: Card
    room: Card
    cheap_score: float
    expected_info_gain: Optional[float]
    rationale: str


def _cheap_score(game_state: "GameState", suspect: Card, weapon: Card, room: Card, responder_order: list[int]) -> float:
    engine = game_state.engine
    uncertainty = sum(len(engine.possible_owners(c)) for c in (suspect, weapon, room))
    bonus = 0.0
    for i, seat in enumerate(responder_order):
        owner = seat_id(seat)
        weight = max(0.0, 1.0 - 0.15 * i)
        for c in (suspect, weapon, room):
            if owner in engine.possible_owners(c):
                bonus += weight
    return uncertainty + bonus


def _candidate_triples(game_state: "GameState") -> list[tuple[Card, Card, Card]]:
    engine = game_state.engine

    def envelope_eligible(cards):
        return [c for c in cards if ENVELOPE in engine.possible_owners(c)]

    suspects = envelope_eligible([c for c in game_state.cards if c.type == CardType.SUSPECT])
    weapons = envelope_eligible([c for c in game_state.cards if c.type == CardType.WEAPON])
    rooms = envelope_eligible([c for c in game_state.cards if c.type == CardType.ROOM])
    return list(itertools.product(suspects, weapons, rooms))


def rank_candidates(game_state: "GameState", *, top_k: int = 8) -> list[AdvisorCandidate]:
    """Best suggestions to make next, ranked by expected information gain
    (with turn-order-soonest, then raw uncertainty, as tie-breaks). Returns
    an empty list once the game is already solved."""
    if game_state.is_solved():
        return []

    responder_order = game_state.responders_in_order(game_state.user_seat)
    triples = _candidate_triples(game_state)
    if not triples:
        return []

    scored = [(t, _cheap_score(game_state, *t, responder_order)) for t in triples]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = scored[:top_k]

    current_total = count_worlds(game_state.engine.counting_input())

    results = []
    for (suspect, weapon, room), cheap in top:
        gain, rationale = _expected_info_gain(
            game_state, suspect, weapon, room, responder_order, current_total
        )
        results.append(AdvisorCandidate(suspect, weapon, room, cheap, gain, rationale))

    results.sort(
        key=lambda c: (c.expected_info_gain if c.expected_info_gain is not None else -1.0, c.cheap_score),
        reverse=True,
    )
    return results


def _expected_info_gain(
    game_state: "GameState",
    suspect: Card,
    weapon: Card,
    room: Card,
    responder_order: list[int],
    current_total: int,
) -> tuple[float, str]:
    if current_total == 0:
        return 0.0, "No valid worlds remain -- the current facts are contradictory."

    ci = game_state.engine.counting_input()
    confirmed_owner_of = {c: game_state.engine.owner_of(c) for c in (suspect, weapon, room)}
    outcome_probs = probability_of_response_outcome(
        ci, confirmed_owner_of, suspect, weapon, room, [seat_id(s) for s in responder_order]
    )

    total_gain = 0.0
    for i, seat in enumerate(list(responder_order) + [None]):
        if seat is None:
            key = "no_show"
            responses = [SuggestionResponse(s, "no_show") for s in responder_order]
        else:
            key = seat_id(seat)
            responses = [SuggestionResponse(s, "no_show") for s in responder_order[:i]]
            responses.append(SuggestionResponse(seat, "shown_unseen"))

        p = outcome_probs.get(key, 0.0)
        if p <= 0.0:
            continue

        hypothetical = Suggestion("__whatif__", game_state.user_seat, suspect, weapon, room, tuple(responses))
        try:
            scratch = whatif_game_state(game_state, hypothetical)
        except Exception:
            continue  # this outcome turned out to be impossible; contributes 0

        resulting_total = count_worlds(scratch.engine.counting_input())
        fraction_eliminated = 1.0 - (resulting_total / current_total if current_total else 0.0)
        total_gain += p * fraction_eliminated

    pct = round(total_gain * 100)
    rationale = f"Expected to eliminate approximately {pct}% of remaining valid game states."
    return total_gain, rationale
