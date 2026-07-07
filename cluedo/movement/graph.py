"""MovementGraph: shortest-path/reachability queries over a board's movement
data. Never hardcodes room layout -- everything is derived from the
MovementData loaded for a given edition (hub + per-room distance-to-hub +
secret passages).

A single turn's move is exactly ONE of:
  - the hub route: roll the dice and walk through the shared hallway, cost
    `distances_to_hub[origin] + distances_to_hub[destination]`;
  - a secret passage: instead of rolling, instantly move to the other room
    a passage connects to your *current* room -- cost 0, but only when
    `(origin, destination)` is itself exactly one of the configured
    secret-passage pairs.

These two options are never combined or chained within one turn -- using a
passage takes the place of rolling, so a route can't roll dice to reach a
passage's doorway and then also step through it the same turn, and a
passage can't be chained into a second passage either. (An earlier version
of this module modeled passages as zero-weight graph edges and ran
all-pairs shortest paths over the whole graph; with two or more passages
sharing the same hub, that let a path incorrectly "hub-hop then passage-hop"
through an unrelated passage to shave a tile off routes that don't touch
either configured pair -- caught via manual testing, not by the synthetic
single-passage unit tests, which is why this direct O(1)-per-pair formula
replaced it instead of a general graph traversal.)

All-pairs results are still precomputed once at construction and cached --
trivially fast for a board this size, satisfying the "<100ms, never
recompute unnecessarily" requirement."""
from __future__ import annotations

from typing import Optional

from cluedo.movement.data import MovementData, load_movement_data
from cluedo.movement.models import RouteResult


class MovementGraph:
    def __init__(self, data: MovementData, rooms: tuple[str, ...]):
        self._data = data
        self._rooms = rooms
        self._room_set = set(rooms)
        self._passage_partner: dict[str, str] = {}
        for a, b in data.secret_passages:
            self._passage_partner[a] = b
            self._passage_partner[b] = a
        self._routes = self._compute_all_pairs()

    @classmethod
    def from_edition(cls, edition_key: str, rooms: tuple[str, ...]) -> Optional["MovementGraph"]:
        """None if no movement data is bundled for this edition yet -- the
        expected, graceful "unsupported" state, not an error."""
        data = load_movement_data(edition_key, rooms)
        if data is None:
            return None
        return cls(data, rooms)

    def _hub_only_distance(self, a: str, b: str) -> int:
        if a == b:
            return 0
        return self._data.distances_to_hub[a] + self._data.distances_to_hub[b]

    def _compute_route(self, a: str, b: str) -> RouteResult:
        hub_only = self._hub_only_distance(a, b)
        if a == b:
            return RouteResult(a, b, 0, (a,), False, None)
        if self._passage_partner.get(a) == b:
            return RouteResult(a, b, 0, (a, b), True, hub_only)
        return RouteResult(a, b, hub_only, (a, self._data.hub, b), False, None)

    def _compute_all_pairs(self) -> dict[tuple[str, str], RouteResult]:
        return {(a, b): self._compute_route(a, b) for a in self._rooms for b in self._rooms}

    def _check_room(self, room: str) -> None:
        if room not in self._room_set:
            raise ValueError(f"Unknown room: {room!r}")

    def distance(self, a: str, b: str) -> int:
        self._check_room(a)
        self._check_room(b)
        return self._routes[(a, b)].distance

    def route(self, a: str, b: str) -> RouteResult:
        self._check_room(a)
        self._check_room(b)
        return self._routes[(a, b)]

    def reachable_rooms(self, origin: str, max_distance: int) -> list[RouteResult]:
        self._check_room(origin)
        routes = [self.route(origin, room) for room in self._rooms if room != origin]
        routes = [r for r in routes if r.distance <= max_distance]
        routes.sort(key=lambda r: (r.distance, r.destination))
        return routes

    def all_rooms(self) -> tuple[str, ...]:
        return self._rooms

    @property
    def hub(self) -> str:
        return self._data.hub

    @property
    def secret_passages(self) -> tuple[tuple[str, str], ...]:
        return self._data.secret_passages
