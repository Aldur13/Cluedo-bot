"""Loading and validation of bundled movement-graph data (distances-to-hub
and secret passages) for editions that have a physical board mapped out.
Board topology data lives separately from CardConfig (cluedo/config.py)
since not every edition has it -- absence of a file is a normal, expected
state (an unsupported edition), not an error."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Mapping, Optional

from cluedo.config import movement_data_filename


class MovementDataError(ValueError):
    """Raised when a bundled movement-data file exists but is structurally
    invalid. Never raised for a missing file -- that's a normal "no
    movement data for this edition" state, signaled by returning None."""


@dataclass(frozen=True)
class MovementData:
    edition_key: str
    hub: str
    distances_to_hub: Mapping[str, int]
    secret_passages: tuple[tuple[str, str], ...]


def _validate(raw: dict, edition_key: str, rooms: tuple[str, ...]) -> MovementData:
    required_keys = {"edition_key", "hub", "distances_to_hub", "secret_passages"}
    missing = required_keys - raw.keys()
    if missing:
        raise MovementDataError(f"movement data missing required keys: {sorted(missing)}")

    if raw["edition_key"] != edition_key:
        raise MovementDataError(
            f"movement data edition_key {raw['edition_key']!r} does not match requested {edition_key!r}"
        )

    hub = raw["hub"]
    if not isinstance(hub, str) or not hub.strip():
        raise MovementDataError("'hub' must be a non-empty string")

    distances_to_hub = raw["distances_to_hub"]
    if not isinstance(distances_to_hub, dict):
        raise MovementDataError("'distances_to_hub' must be an object mapping room -> int")

    room_set = set(rooms)
    configured_rooms = set(distances_to_hub.keys())
    if configured_rooms != room_set:
        missing_rooms = room_set - configured_rooms
        extra_rooms = configured_rooms - room_set
        details = []
        if missing_rooms:
            details.append(f"missing distances for: {sorted(missing_rooms)}")
        if extra_rooms:
            details.append(f"distances given for unknown rooms: {sorted(extra_rooms)}")
        raise MovementDataError("movement data rooms don't match edition rooms (" + "; ".join(details) + ")")

    for room, dist in distances_to_hub.items():
        if not isinstance(dist, int) or isinstance(dist, bool) or dist <= 0:
            raise MovementDataError(f"distance for {room!r} must be a positive integer, got {dist!r}")

    secret_passages_raw = raw["secret_passages"]
    if not isinstance(secret_passages_raw, list):
        raise MovementDataError("'secret_passages' must be a list of [room, room] pairs")

    seen_pairs = set()
    secret_passages = []
    for pair in secret_passages_raw:
        if not isinstance(pair, list) or len(pair) != 2:
            raise MovementDataError(f"each secret passage must be a [room, room] pair, got {pair!r}")
        a, b = pair
        if a not in room_set or b not in room_set:
            raise MovementDataError(f"secret passage references unknown room(s): {pair!r}")
        if a == b:
            raise MovementDataError(f"a room cannot have a secret passage to itself: {a!r}")
        key = frozenset((a, b))
        if key in seen_pairs:
            raise MovementDataError(f"duplicate secret passage: {pair!r}")
        seen_pairs.add(key)
        secret_passages.append((a, b))

    return MovementData(
        edition_key=edition_key,
        hub=hub,
        distances_to_hub=dict(distances_to_hub),
        secret_passages=tuple(secret_passages),
    )


def load_movement_data(edition_key: str, rooms: tuple[str, ...]) -> Optional[MovementData]:
    """Returns the bundled MovementData for this edition key, or None if no
    movement data file is bundled for it (e.g. classic_uk/classic_us) --
    that's an expected, non-error state callers must handle gracefully.
    Raises MovementDataError if a file exists but is structurally invalid."""
    filename = movement_data_filename(edition_key)
    if filename is None:
        return None
    try:
        raw_text = resources.files("cluedo.data").joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise MovementDataError(f"invalid JSON in movement data file {filename!r}: {exc}") from exc
    if not isinstance(raw, dict):
        raise MovementDataError(f"movement data file {filename!r} must contain a JSON object")
    return _validate(raw, edition_key, rooms)
