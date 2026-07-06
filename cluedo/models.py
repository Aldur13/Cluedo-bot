"""Core data types shared by the engine, history, advisor, and GUI layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

ENVELOPE = "__envelope__"

ResponseOutcome = Literal["no_show", "shown_to_me", "shown_unseen"]


class CardType(Enum):
    SUSPECT = "suspect"
    WEAPON = "weapon"
    ROOM = "room"


@dataclass(frozen=True)
class Card:
    name: str
    type: CardType

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


def seat_id(seat_index: int) -> str:
    """Canonical owner-id string for a player seat, distinct from ENVELOPE."""
    return f"seat_{seat_index}"


@dataclass(frozen=True)
class Player:
    name: str
    seat_index: int
    hand_size: int

    @property
    def owner_id(self) -> str:
        return seat_id(self.seat_index)


@dataclass(frozen=True)
class SuggestionResponse:
    responder_seat: int
    outcome: ResponseOutcome
    shown_card: Optional[Card] = None

    def __post_init__(self) -> None:
        if self.outcome == "shown_to_me" and self.shown_card is None:
            raise ValueError("shown_to_me responses must specify shown_card")
        if self.outcome != "shown_to_me" and self.shown_card is not None:
            raise ValueError("only shown_to_me responses may specify shown_card")


@dataclass(frozen=True)
class Suggestion:
    suggestion_id: str
    suggester_seat: int
    suspect: Card
    weapon: Card
    room: Card
    responses: tuple[SuggestionResponse, ...] = field(default_factory=tuple)

    @property
    def triple(self) -> tuple[Card, Card, Card]:
        return (self.suspect, self.weapon, self.room)
