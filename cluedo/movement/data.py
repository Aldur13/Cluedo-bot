"""Loading and validation of movement-graph data (distances-to-hub and
secret passages) for editions that have a physical board mapped out.
Board topology data lives separately from CardConfig (cluedo/config.py)
since not every edition has it -- absence of a file is a normal, expected
state (an unsupported edition), not an error.

Two sources, checked in this order:
1. A user override under %APPDATA%/CluedoAssistant/movement_overrides/ --
   written by the in-app "Edit Board Data" dialog (cluedo.gui.
   movement_edit_dialog) when the player corrects an estimated distance or
   secret passage. This lives outside the installed/bundled app on
   purpose: the packaged .exe is a PyInstaller *onefile* build (see
   CluedoAssistant.spec -- EXE() is handed a.binaries/a.datas directly,
   not routed through COLLECT()), which extracts cluedo/data/*.json into a
   temp _MEI* directory that's deleted when the process exits. Writing a
   correction back into that bundled file would silently vanish the next
   time the app runs; %APPDATA% is the same durable, per-user location
   cluedo.game.default_autosave_path() already uses for the exact same
   reason.
2. The bundled cluedo/data/movement_<edition_key>.json shipped with the
   app -- the photo-derived best-effort estimate, used whenever no
   override exists yet.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping, Optional

from cluedo.config import movement_data_filename


class MovementDataError(ValueError):
    """Raised when a movement-data file exists (bundled or user override)
    but is structurally invalid. Never raised for a missing file -- that's
    a normal "no movement data for this edition" state, signaled by
    returning None."""


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


def _to_raw_dict(data: MovementData) -> dict:
    return {
        "edition_key": data.edition_key,
        "hub": data.hub,
        "distances_to_hub": dict(data.distances_to_hub),
        "secret_passages": [list(pair) for pair in data.secret_passages],
        "_comment": "Corrected in-app via Movement Strategy -> Edit Board Data. "
                    "Delete this file (or use 'Reset to bundled defaults' in the app) to revert to the shipped estimate.",
    }


def user_movement_data_dir() -> Path:
    """Same durable per-user location cluedo.game.default_autosave_path()
    uses, in its own subfolder so overrides don't collide with the
    autosave file."""
    base = Path(os.environ.get("APPDATA") or Path.home() / ".cluedo_assistant")
    return base / "CluedoAssistant" / "movement_overrides"


def override_path(edition_key: str) -> Path:
    return user_movement_data_dir() / f"{edition_key}.json"


def has_override(edition_key: str) -> bool:
    return override_path(edition_key).exists()


def save_movement_override(data: MovementData) -> None:
    """Persists a user-corrected MovementData so it survives app restarts
    (and a onefile .exe's bundled-data extraction being wiped on exit).
    Atomic write (temp file + os.replace), matching cluedo.game.save_game's
    own pattern, so a crash mid-write can't corrupt a previously-good
    override."""
    path = override_path(data.edition_key)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_to_raw_dict(data), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def delete_override(edition_key: str) -> None:
    """Removes a user override, reverting back to the bundled estimate.
    Safe to call even if no override exists."""
    path = override_path(edition_key)
    if path.exists():
        path.unlink()


def load_movement_data(edition_key: str, rooms: tuple[str, ...]) -> Optional[MovementData]:
    """Returns the effective MovementData for this edition key: a user
    override if one has been saved, otherwise the bundled default, or None
    if neither exists (an expected, non-error "no movement data for this
    edition" state callers must handle gracefully). Raises
    MovementDataError if a file exists (either source) but is structurally
    invalid."""
    override = override_path(edition_key)
    if override.exists():
        raw_text = override.read_text(encoding="utf-8")
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MovementDataError(f"invalid JSON in movement override file {override}: {exc}") from exc
        if not isinstance(raw, dict):
            raise MovementDataError(f"movement override file {override} must contain a JSON object")
        return _validate(raw, edition_key, rooms)

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
