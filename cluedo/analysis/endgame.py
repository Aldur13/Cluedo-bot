"""Endgame assistant: a small, correctness-safe "are we ready to accuse yet?"
summary built only from the solver's own exact outputs
(`GameState.is_solved()`/`solution()`/`card_probabilities()`).

Lives under `cluedo.analysis` (already guarded by
tests/test_architecture_boundaries.py, so the solver core can never come to
depend on it) even though, unlike patterns.py/strategy.py, it makes no
behavioral guesses -- it's included here because it's advisory framing over
solver output, not a fact the sheet displays directly.

Hard rule this module exists to enforce: never suggest a specific
suspect/weapon/room accusation while the game isn't solved. Guessing wrong
ends a real game of Cluedo, so "not solved yet" only ever reports how far
off the least-certain category is -- it never names a candidate as the
likely answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from cluedo.models import ENVELOPE, Card, CardType
from cluedo.probability import TooManyAmbiguousCardsError

if TYPE_CHECKING:
    from cluedo.game import GameState


@dataclass(frozen=True)
class EndgameAdvice:
    safe_to_accuse: bool
    solution: Optional[tuple[Card, Card, Card]]
    message: str
    # Per-category top-candidate confidence (0.0-1.0), when computable --
    # None per category while too many cards are still ambiguous to compute
    # exact probabilities. Never used to name *which* card is the top
    # candidate, only how confident the solver is in whichever one it is.
    category_confidence: dict[CardType, Optional[float]]


def suggest_accusation_readiness(game_state: "GameState") -> EndgameAdvice:
    if game_state.is_solved():
        suspect, weapon, room = game_state.solution()
        return EndgameAdvice(
            safe_to_accuse=True,
            solution=(suspect, weapon, room),
            message=f"Solved — {suspect.name} / {weapon.name} / {room.name}. Safe to accuse.",
            category_confidence={CardType.SUSPECT: 1.0, CardType.WEAPON: 1.0, CardType.ROOM: 1.0},
        )

    try:
        probs = game_state.card_probabilities()
    except TooManyAmbiguousCardsError:
        return EndgameAdvice(
            safe_to_accuse=False,
            solution=None,
            message="Too many unknowns remain to gauge accusation readiness yet.",
            category_confidence={CardType.SUSPECT: None, CardType.WEAPON: None, CardType.ROOM: None},
        )

    category_confidence: dict[CardType, Optional[float]] = {}
    for card_type in (CardType.SUSPECT, CardType.WEAPON, CardType.ROOM):
        cards = [c for c in game_state.cards if c.type == card_type]
        best_p = max((probs.get(c, {}).get(ENVELOPE, 0.0) for c in cards), default=0.0)
        category_confidence[card_type] = best_p

    weakest_category, weakest_p = min(category_confidence.items(), key=lambda item: item[1])
    message = (
        f"Not yet solved -- least certain category is {weakest_category.value} "
        f"at {weakest_p * 100:.0f}% confidence. Not safe to accuse yet."
    )
    return EndgameAdvice(
        safe_to_accuse=False,
        solution=None,
        message=message,
        category_confidence=category_confidence,
    )
