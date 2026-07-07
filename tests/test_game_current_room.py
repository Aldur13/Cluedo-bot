"""GameState.current_room: the app user's own board position, added in
v4.6. Bypasses the from_history/_adopt atomic-mutation pattern (movement
has no bearing on card deduction) but still bumps mutation_seq and
round-trips through save/load."""
import pytest

from cluedo.game import GameState


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_new_game_has_no_current_room(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert gs.current_room is None


def test_set_current_room_accepts_valid_room(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    assert gs.current_room == "Kitchen"


def test_set_current_room_rejects_unknown_room(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    with pytest.raises(ValueError):
        gs.set_current_room("Not A Real Room")
    assert gs.current_room is None


def test_set_current_room_accepts_none_to_clear(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    gs.set_current_room(None)
    assert gs.current_room is None


def test_set_current_room_bumps_mutation_seq(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    before = gs.mutation_seq
    gs.set_current_room("Kitchen")
    assert gs.mutation_seq == before + 1


def test_set_current_room_does_not_bump_seq_on_rejection(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    before = gs.mutation_seq
    with pytest.raises(ValueError):
        gs.set_current_room("Not A Real Room")
    assert gs.mutation_seq == before


def test_to_dict_from_dict_round_trips_current_room(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    data = gs.to_dict()
    assert data["current_room"] == "Kitchen"

    reloaded = GameState.from_dict(data)
    assert reloaded.current_room == "Kitchen"


def test_to_dict_from_dict_round_trips_none(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    data = gs.to_dict()
    assert data["current_room"] is None

    reloaded = GameState.from_dict(data)
    assert reloaded.current_room is None


def test_old_format_dict_without_current_room_key_loads_as_none(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    data = gs.to_dict()
    del data["current_room"]  # simulate a pre-v4.6 save file

    reloaded = GameState.from_dict(data)
    assert reloaded.current_room is None


def test_save_naming_a_room_not_in_config_degrades_to_none(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    data = gs.to_dict()
    data["current_room"] = "Some Room That No Longer Exists"

    reloaded = GameState.from_dict(data)
    assert reloaded.current_room is None


def test_undo_does_not_clear_current_room(cfg, cards_by_name, three_players):
    from cluedo.models import CardType, SuggestionResponse

    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_unseen")],
    )
    gs.undo_last_suggestion()
    assert gs.current_room == "Kitchen"
