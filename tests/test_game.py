import tempfile
from pathlib import Path

import pytest

from cluedo.engine import ContradictionError
from cluedo.game import GameState, load_game, save_game
from cluedo.models import SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_responders_in_order_wraps_around(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    assert gs.responders_in_order(0) == [1, 2]
    assert gs.responders_in_order(1) == [2, 0]
    assert gs.responders_in_order(2) == [0, 1]


def test_no_show_translates_to_not_owned_for_all_three(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    suspect, weapon, room = cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"]
    gs.record_suggestion(0, suspect, weapon, room, [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")])
    assert "seat_1" not in gs.engine.possible_owners(suspect)
    assert "seat_2" not in gs.engine.possible_owners(room)


def test_shown_to_me_translates_to_owned(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    suspect, weapon, room = cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"]
    gs.record_suggestion(
        0, suspect, weapon, room,
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", room)],
    )
    assert gs.engine.owner_of(room) == "seat_2"


def test_shown_unseen_translates_to_at_least_one(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    suspect, weapon, room = cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"]
    gs.record_suggestion(1, suspect, weapon, room, [SuggestionResponse(2, "shown_unseen")])
    # Not yet resolvable to a single card, but should have narrowed the trio's
    # ambiguity (an AtLeastOne constraint recorded against seat_2).
    ci = gs.engine.counting_input()
    assert any(owner == "seat_2" for owner, _ in ci.at_least_one)


def test_failed_mutation_leaves_live_state_untouched(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    history_before = list(gs.history)
    engine_before = gs.engine

    with pytest.raises(ContradictionError):
        # Rope is already seat_2's; claiming seat_1 has it too is contradictory.
        gs.record_suggestion(
            0, cards_by_name["Miss Scarlett"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(1, "shown_to_me", cards_by_name["Rope"])],
        )

    assert gs.history == history_before
    assert gs.engine is engine_before


def test_save_load_round_trip(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "game.json"
        save_game(gs, path)
        loaded = load_game(path)
        assert len(loaded.history) == len(gs.history)
        assert loaded.engine.owner_of(cards_by_name["Rope"]) == gs.engine.owner_of(cards_by_name["Rope"])
        assert loaded.detective_sheet().keys() == gs.detective_sheet().keys()


def test_load_missing_file_raises_save_file_error():
    from cluedo.game import SaveFileError

    with pytest.raises(SaveFileError):
        load_game("/no/such/path/does-not-exist.json")


def test_load_corrupted_json_raises_save_file_error():
    from cluedo.game import SaveFileError

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(SaveFileError):
            load_game(path)


def test_atomic_save_creates_backup_of_previous(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "game.json"
        save_game(gs, path)
        gs.record_suggestion(
            0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
        )
        save_game(gs, path)
        backup = path.with_name(path.name + ".bak")
        assert backup.exists()
