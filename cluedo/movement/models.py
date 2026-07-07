"""Plain, immutable result types for the movement/dice engine -- mirrors the
frozen-dataclass convention used throughout cluedo/models.py and advisor.py."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class RouteResult:
    origin: str
    destination: str
    distance: int
    path: tuple[str, ...]
    via_secret_passage: bool
    moves_saved: Optional[int]  # only meaningful when via_secret_passage is True


@dataclass(frozen=True)
class DiceProbability:
    distance: int
    # roll threshold n (2..12) -> P(sum of 2d6 >= n). probabilities[distance]
    # is "chance of reaching this room this turn" for a non-passage route.
    probabilities: Mapping[int, float]


@dataclass(frozen=True)
class RoomRanking:
    room: str
    distance: int
    reachable_this_turn: bool
    reach_probability: float
    expected_info_gain: Optional[float]
    overall_score: float
    rationale: str


@dataclass(frozen=True)
class TurnRecommendation:
    current_room: Optional[str]
    rankings: tuple[RoomRanking, ...]
    best: Optional[RoomRanking]
    unsupported_reason: Optional[str]
