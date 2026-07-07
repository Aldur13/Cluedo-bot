"""Mystery Progress: a small read-only summary of how far the deduction has
come, plus a "chance of solving next turn" estimate.

Everything here is a consumer of the existing exact-solver primitives
(`engine.py`/`probability.py`/`advisor.py`/`history.py`) -- this module never
feeds anything back into the solver and never modifies those files.

"Chance of solving next turn" follows the locked-in product definition: the
arithmetic mean, across the advisor's top-3 ranked candidate suggestions, of
P(that suggestion's responses would fully solve the mystery). This mirrors
the same whatif/probability-weighting pattern `advisor._expected_info_gain`
already uses to compute expected info gain -- the only difference is what we
do with each resulting scratch GameState (check `.is_solved()` instead of
counting remaining worlds).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from cluedo.history import whatif_game_state
from cluedo.models import Suggestion, SuggestionResponse, seat_id
from cluedo.probability import probability_of_response_outcome

if TYPE_CHECKING:
    from cluedo.game import GameState


@dataclass(frozen=True)
class MysteryProgress:
    known_cards: int
    total_cards: int
    remaining_valid_worlds: Optional[int]
    turns_played: int
    deductions_made: int
    chance_of_solving_next_turn: Optional[float]


def _p_candidate_solves(game_state: "GameState", suspect, weapon, room) -> float:
    """P(this suggestion's responses fully solve the mystery), by simulating
    every possible response outcome (no_show from everyone, or each responder
    in turn showing something) and weighting `.is_solved()` on the resulting
    scratch GameState by that outcome's exact probability."""
    responder_order = game_state.responders_in_order(game_state.user_seat)
    ci = game_state.engine.counting_input()
    confirmed_owner_of = {c: game_state.engine.owner_of(c) for c in (suspect, weapon, room)}

    try:
        outcome_probs = probability_of_response_outcome(
            ci, confirmed_owner_of, suspect, weapon, room, [seat_id(s) for s in responder_order]
        )
    except Exception:
        return 0.0

    total = 0.0
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

        if scratch.is_solved():
            total += p

    return total


def _chance_of_solving_next_turn(game_state: "GameState") -> Optional[float]:
    if game_state.is_solved():
        return None

    candidates = game_state.best_suggestions(top_k=3)[:3]
    if not candidates:
        return None

    per_candidate = [
        _p_candidate_solves(game_state, c.suspect, c.weapon, c.room) for c in candidates
    ]
    return sum(per_candidate) / len(per_candidate)


def compute_mystery_progress(game_state: "GameState") -> MysteryProgress:
    engine = game_state.engine
    known_cards = len(engine.confirmed)

    stats = game_state.last_solver_stats
    remaining_valid_worlds = stats.valid_worlds_last_counted

    return MysteryProgress(
        known_cards=known_cards,
        total_cards=len(game_state.cards),
        remaining_valid_worlds=remaining_valid_worlds,
        turns_played=len(game_state.history),
        # Same source as known_cards: every confirmed card is a deduction the
        # solver has made. No separate "deduction log" exists yet, so this is
        # intentionally the same count rather than a second, divergent metric.
        deductions_made=known_cards,
        chance_of_solving_next_turn=_chance_of_solving_next_turn(game_state),
    )
