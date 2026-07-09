"""Structural validation of the real bundled movement data file. Deliberately
asserts nothing about the *specific* estimated distance numbers (those are
photo-derived best-effort estimates the user may correct later) -- only that
the file's shape is internally consistent."""
import pytest

from cluedo.config import load_bundled_edition
from cluedo.movement.data import MovementData, MovementDataError, load_movement_data


def test_swedish_2012_movement_data_is_structurally_valid():
    cfg = load_bundled_edition("swedish_2012")
    data = load_movement_data("swedish_2012", cfg.rooms)
    assert data is not None
    assert isinstance(data, MovementData)
    assert data.edition_key == "swedish_2012"

    assert set(data.distances_to_hub) == set(cfg.rooms)
    assert all(isinstance(d, int) and d > 0 for d in data.distances_to_hub.values())

    room_set = set(cfg.rooms)
    seen_pairs = set()
    for a, b in data.secret_passages:
        assert a in room_set and b in room_set
        assert a != b
        pair = frozenset((a, b))
        assert pair not in seen_pairs, "duplicate secret passage pair"
        seen_pairs.add(pair)


def test_classic_editions_have_no_movement_data_yet():
    for edition_key in ("classic_uk", "classic_us"):
        cfg = load_bundled_edition(edition_key)
        assert load_movement_data(edition_key, cfg.rooms) is None


def test_unknown_edition_key_returns_none():
    assert load_movement_data("totally_unknown_edition", ("A", "B")) is None


def test_missing_room_in_distances_raises():
    cfg = load_bundled_edition("swedish_2012")
    incomplete_rooms = cfg.rooms + ("Extra Room",)
    with pytest.raises(MovementDataError):
        load_movement_data("swedish_2012", incomplete_rooms)


def test_fewer_rooms_than_configured_raises():
    cfg = load_bundled_edition("swedish_2012")
    with pytest.raises(MovementDataError):
        load_movement_data("swedish_2012", cfg.rooms[:-1])


def test_room_in_two_secret_passages_raises(tmp_path, monkeypatch):
    # Regression: MovementGraph models passages as a one-to-one dict
    # (_passage_partner[a] = b, _passage_partner[b] = a); validation only
    # rejected exact-duplicate pairs, not a room appearing in two distinct
    # pairs, so ["A","B"] + ["A","C"] used to load without error and
    # silently overwrite A's partner, corrupting route("A","B").
    import json

    from cluedo.movement import data as data_module

    cfg = load_bundled_edition("swedish_2012")
    rooms = cfg.rooms
    raw = {
        "edition_key": "swedish_2012",
        "hub": "hallway_core",
        "distances_to_hub": {room: 3 for room in rooms},
        "secret_passages": [[rooms[0], rooms[1]], [rooms[0], rooms[2]]],
    }
    override_dir = tmp_path / "movement_overrides"
    override_dir.mkdir()
    (override_dir / "swedish_2012.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(data_module, "user_movement_data_dir", lambda: override_dir)

    with pytest.raises(MovementDataError):
        load_movement_data("swedish_2012", rooms)
