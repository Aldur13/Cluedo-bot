"""Combines MovementGraph reachability with cluedo.advisor's expected
information gain into a per-room ranking and a single best-turn
recommendation. This module -- not cluedo.advisor -- is the one place that
depends on both the movement engine and the solver-adjacent advisor; the
import direction is one-way (scoring -> advisor, never the reverse), so
advisor.py itself stays untouched and solver-module boundaries
(tests/test_architecture_boundaries.py) aren't affected."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from cluedo.movement.dice import probability_sum_at_least, reachable_this_turn
from cluedo.movement.graph import MovementGraph
from cluedo.movement.models import RoomRanking, TurnRecommendation

if TYPE_CHECKING:
    from cluedo.game import GameState

# Cap on how many triples the advisor exact-scores for our per-room
# aggregation. Exact scoring (whatif_game_state per candidate x per
# responder) is the expensive part of advisor.rank_candidates -- this cap
# keeps every room a fair shot at appearing without paying for exhaustive
# scoring of all ~324 possible triples every time a ranking is requested.
_ADVISOR_TOP_K = 24


def _combine(reach_probability: float, info_gain: Optional[float]) -> float:
    """overall_score = P(reach this turn) x expected_info_gain. A room with
    no advisor data yet (info_gain is None) contributes 0, not a guess."""
    return reach_probability * (info_gain if info_gain is not None else 0.0)


def _rationale(distance: int, via_secret_passage: bool, moves_saved: Optional[int],
               reach_probability: float, info_gain: Optional[float]) -> str:
    if distance == 0:
        location = "You're already here."
    elif via_secret_passage:
        location = f"Reachable instantly via secret passage ({moves_saved} tile(s) saved vs. the hallway route)."
    else:
        location = f"{round(reach_probability * 100)}% chance to reach this turn (distance {distance})."
    if info_gain is None:
        gain = "No advisor data available for this room yet."
    else:
        gain = f"Expected to eliminate approximately {round(info_gain * 100)}% of remaining possibilities."
    return f"{location} {gain}"


def _info_gain_by_room(game_state: "GameState") -> dict[str, float]:
    from cluedo.advisor import rank_candidates  # local import avoids a circular dependency

    by_room: dict[str, float] = {}
    for candidate in rank_candidates(game_state, top_k=_ADVISOR_TOP_K):
        if candidate.expected_info_gain is None:
            continue
        room_name = candidate.room.name
        current_best = by_room.get(room_name)
        if current_best is None or candidate.expected_info_gain > current_best:
            by_room[room_name] = candidate.expected_info_gain
    return by_room


def rank_rooms(game_state: "GameState", graph: Optional[MovementGraph]) -> TurnRecommendation:
    """Full room-by-room ranking + best-move recommendation for the app
    user's own current turn, combining movement reachability with the
    existing advisor's information-gain scoring."""
    current_room = getattr(game_state, "current_room", None)

    if graph is None:
        return TurnRecommendation(
            current_room=current_room, rankings=(), best=None,
            unsupported_reason="No movement data for this edition yet.",
        )
    if current_room is None:
        return TurnRecommendation(
            current_room=None, rankings=(), best=None,
            unsupported_reason="Set your current position to see movement recommendations.",
        )

    info_gain_by_room = _info_gain_by_room(game_state)

    rankings = []
    for room in graph.all_rooms():
        route = graph.route(current_room, room)
        reach_probability = 1.0 if route.via_secret_passage else probability_sum_at_least(route.distance)
        info_gain = info_gain_by_room.get(room)
        overall_score = _combine(reach_probability, info_gain)
        rankings.append(
            RoomRanking(
                room=room,
                distance=route.distance,
                reachable_this_turn=route.via_secret_passage or reachable_this_turn(route.distance),
                reach_probability=reach_probability,
                expected_info_gain=info_gain,
                overall_score=overall_score,
                rationale=_rationale(route.distance, route.via_secret_passage, route.moves_saved,
                                      reach_probability, info_gain),
            )
        )

    rankings.sort(key=lambda r: (-r.overall_score, r.distance, r.room))
    best = rankings[0] if rankings else None
    return TurnRecommendation(current_room=current_room, rankings=tuple(rankings), best=best, unsupported_reason=None)
