import pytest

from cluedo.engine import ContradictionError
from cluedo.game import GameState
from cluedo.history import build_replay_snapshots, whatif_game_state
from cluedo.models import Suggestion, SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_undo_removes_last_entry_and_recomputes(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    assert gs.engine.owner_of(cards_by_name["Rope"]) == "seat_2"
    gs.undo_last_suggestion()
    assert len(gs.history) == 0
    assert gs.engine.owner_of(cards_by_name["Rope"]) is None


def test_delete_preserves_order_and_ids(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    s1 = gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    s2 = gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    s3 = gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )
    gs.delete_suggestion(s2.suggestion_id)
    ids = [s.suggestion_id for s in gs.history]
    assert ids == [s1.suggestion_id, s3.suggestion_id]


def test_edit_that_creates_contradiction_leaves_state_unchanged(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    s1 = gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    # A second, independent suggestion also directly pins Rope to seat_2, so
    # editing s1 below conflicts with *this* still-standing fact rather than
    # just undoing its own prior effect.
    gs.record_suggestion(
        0, cards_by_name["Mrs. Peacock"], cards_by_name["Rope"], cards_by_name["Ballroom"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    history_before = list(gs.history)
    engine_before = gs.engine

    with pytest.raises(ContradictionError):
        # Editing s1 to claim seat_1 shows Rope directly conflicts with seat_2
        # still owning it via the second suggestion above.
        gs.edit_suggestion(
            s1.suggestion_id, 0,
            cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(1, "shown_to_me", cards_by_name["Rope"]), SuggestionResponse(2, "no_show")],
        )

    assert gs.history == history_before
    assert gs.engine is engine_before


def test_replay_snapshots_match_direct_rebuild(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "shown_unseen")],
    )

    snapshots = build_replay_snapshots(gs)
    assert len(snapshots) == 3  # prefixes of length 0, 1, 2

    for i, snap in enumerate(snapshots):
        direct = GameState.from_history(gs.config, gs.players, gs.user_seat, gs._initial_hand, gs.history[:i])
        assert snap.game_state.detective_sheet().keys() == direct.detective_sheet().keys()
        for card in gs.cards:
            assert snap.game_state.engine.owner_of(card) == direct.engine.owner_of(card)

    # Final snapshot matches the live state.
    for card in gs.cards:
        assert snapshots[-1].game_state.engine.owner_of(card) == gs.engine.owner_of(card)


def test_whatif_does_not_mutate_live_state(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    history_before = list(gs.history)
    hypothetical = Suggestion(
        "__whatif__", 0,
        cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        (SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")),
    )
    scratch = whatif_game_state(gs, hypothetical)
    assert gs.history == history_before
    assert len(scratch.history) == len(history_before) + 1


def test_two_independent_whatif_branches_do_not_interfere(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    hypo_a = Suggestion(
        "__a__", 0, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        (SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")),
    )
    hypo_b = Suggestion(
        "__b__", 0, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        (SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")),
    )
    scratch_a = whatif_game_state(gs, hypo_a)
    scratch_b = whatif_game_state(gs, hypo_b)
    assert scratch_a.history[-1].suggestion_id == "__a__"
    assert scratch_b.history[-1].suggestion_id == "__b__"
    assert gs.history == []
