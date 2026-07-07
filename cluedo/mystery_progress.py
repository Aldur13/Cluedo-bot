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

from cluedo.engine import ContradictionError
from cluedo.history import whatif_game_state
from cluedo.models import Suggestion, SuggestionResponse, seat_id
from cluedo.probability import TooManyAmbiguousCardsError, probability_of_response_outcome

if TYPE_CHECKING:
    from cluedo.game import GameState

# Above this many still-ambiguous cards, computing an exact "chance of
# solving next turn" becomes intractable: _p_candidate_solves rebuilds a
# whatif GameState (which itself runs the engine's own bounded exhaustive
# world-search) for every candidate x every possible responder, so the cost
# multiplies rather than just adding. Mirrors advisor.py's
# _MAX_AMBIGUOUS_FOR_EXACT_GAIN gate -- same "never guess, just admit
# exactness isn't cheap yet" philosophy, applied to this module's own
# repeated whatif/probability calls.
_MAX_AMBIGUOUS_FOR_SOLVE_CHANCE = 15


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
    except TooManyAmbiguousCardsError:
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
        except ContradictionError:
            continue  # this outcome turned out to be impossible; contributes 0

        if scratch.is_solved():
            total += p

    return total


def _chance_of_solving_next_turn(game_state: "GameState") -> Optional[float]:
    if game_state.is_solved():
        return None

    ci = game_state.engine.counting_input()
    if len(ci.ambiguous) > _MAX_AMBIGUOUS_FOR_SOLVE_CHANCE:
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
