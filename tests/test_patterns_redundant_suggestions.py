"""Tests for cluedo.analysis.patterns.find_redundant_suggestions -- the
public per-turn list extracted from the private `_redundant_suggestion_count`
scalar so the Warnings sidebar card can reuse the same detection logic.
Behavior-preserving refactor: `analyze_player_patterns(...).
redundant_suggestion_count` must still equal `len(find_redundant_suggestions(...))`.
"""
from cluedo.analysis.patterns import analyze_player_patterns, find_redundant_suggestions
from cluedo.game import GameState
from cluedo.models import CardType, SuggestionResponse


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_no_redundant_suggestions_for_a_fresh_game(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert find_redundant_suggestions(gs, 0) == []


def test_scalar_count_matches_length_of_turn_list(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]

    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "shown_unseen"), SuggestionResponse(2, "no_show")],
    )
    # Re-ask the identical triple -- redundant only if the first suggestion
    # actually confirmed one of the three cards for seat 1.
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )

    turns = find_redundant_suggestions(gs, 0)
    stats = analyze_player_patterns(gs, seat=0)
    assert stats.redundant_suggestion_count == len(turns)


def test_redundant_turn_indices_point_to_suggestions_by_that_seat(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]

    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "shown_unseen"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )

    for turn_index in find_redundant_suggestions(gs, 0):
        assert gs.history[turn_index].suggester_seat == 0


def test_seat_with_no_suggestions_has_no_redundant_turns(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert find_redundant_suggestions(gs, 1) == []
