"""User-corrected movement data (Edit Board Data dialog) persistence:
override_path/save_movement_override/delete_override/has_override, and
load_movement_data's override-over-bundled precedence. Every test
monkeypatches user_movement_data_dir() into tmp_path so it never touches
the real user's %APPDATA%, matching the established pattern for
default_autosave_path() in tests/test_app_player_store.py."""
import pytest

from cluedo.config import load_bundled_edition
from cluedo.movement import data as movement_data
from cluedo.movement.data import MovementData, MovementDataError


@pytest.fixture(autouse=True)
def _redirect_override_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(movement_data, "user_movement_data_dir", lambda: tmp_path)


def _swedish_rooms():
    return load_bundled_edition("swedish_2012").rooms


def test_no_override_by_default():
    rooms = _swedish_rooms()
    assert movement_data.has_override("swedish_2012") is False
    bundled = movement_data.load_movement_data("swedish_2012", rooms)
    assert bundled is not None


def test_save_override_takes_precedence_over_bundled():
    rooms = _swedish_rooms()
    bundled = movement_data.load_movement_data("swedish_2012", rooms)
    corrected_distances = dict(bundled.distances_to_hub)
    a_room = rooms[0]
    corrected_distances[a_room] = corrected_distances[a_room] + 5

    override = MovementData(
        edition_key="swedish_2012", hub=bundled.hub,
        distances_to_hub=corrected_distances, secret_passages=bundled.secret_passages,
    )
    movement_data.save_movement_override(override)

    assert movement_data.has_override("swedish_2012") is True
    loaded = movement_data.load_movement_data("swedish_2012", rooms)
    assert loaded.distances_to_hub[a_room] == bundled.distances_to_hub[a_room] + 5


def test_delete_override_reverts_to_bundled():
    rooms = _swedish_rooms()
    bundled = movement_data.load_movement_data("swedish_2012", rooms)
    override = MovementData(
        edition_key="swedish_2012", hub=bundled.hub,
        distances_to_hub=dict(bundled.distances_to_hub), secret_passages=(),
    )
    movement_data.save_movement_override(override)
    assert movement_data.has_override("swedish_2012") is True

    movement_data.delete_override("swedish_2012")
    assert movement_data.has_override("swedish_2012") is False
    reloaded = movement_data.load_movement_data("swedish_2012", rooms)
    assert reloaded.secret_passages == bundled.secret_passages  # back to the bundled pair(s)


def test_delete_override_is_safe_when_none_exists():
    movement_data.delete_override("swedish_2012")  # must not raise


def test_saved_override_round_trips_secret_passages():
    rooms = _swedish_rooms()
    bundled = movement_data.load_movement_data("swedish_2012", rooms)
    new_pair = (rooms[0], rooms[1])
    override = MovementData(
        edition_key="swedish_2012", hub=bundled.hub,
        distances_to_hub=dict(bundled.distances_to_hub), secret_passages=(new_pair,),
    )
    movement_data.save_movement_override(override)

    loaded = movement_data.load_movement_data("swedish_2012", rooms)
    assert loaded.secret_passages == (new_pair,)


def test_invalid_override_file_raises(tmp_path):
    rooms = _swedish_rooms()
    override_file = movement_data.override_path("swedish_2012")
    override_file.parent.mkdir(parents=True, exist_ok=True)
    override_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(MovementDataError):
        movement_data.load_movement_data("swedish_2012", rooms)


def test_override_for_edition_with_no_bundled_data_still_works():
    # classic_uk has no bundled file, but a saved override should still be
    # usable -- movement data doesn't strictly require a bundled base.
    cfg = load_bundled_edition("classic_uk")
    assert movement_data.load_movement_data("classic_uk", cfg.rooms) is None

    override = MovementData(
        edition_key="classic_uk", hub="hallway_core",
        distances_to_hub={room: 3 for room in cfg.rooms}, secret_passages=(),
    )
    movement_data.save_movement_override(override)

    loaded = movement_data.load_movement_data("classic_uk", cfg.rooms)
    assert loaded is not None
    assert all(d == 3 for d in loaded.distances_to_hub.values())
