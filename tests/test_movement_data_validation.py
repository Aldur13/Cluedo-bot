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
