"""Tests for cluedo.analysis.patterns: rule-based per-player suggestion
pattern extraction, including the historical-snapshot regression test for
redundant_suggestion_count.
"""
from cluedo.analysis.patterns import analyze_all_players, analyze_player_patterns
from cluedo.game import GameState
from cluedo.models import CardType, SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_card_pair_triple_frequency_and_never_always_suggested(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # Seat 1 repeats the exact same triple twice, giving a clean, hand-
    # verifiable triple/pair/card frequency table.
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show")],
    )

    stats = analyze_player_patterns(gs, seat=1)

    assert stats.total_suggestions == 2
    assert stats.card_frequency[cards_by_name["Reverend Green"]] == 2
    assert stats.card_frequency[cards_by_name["Wrench"]] == 2
    assert stats.card_frequency[cards_by_name["Kitchen"]] == 2

    pair = frozenset((cards_by_name["Reverend Green"], cards_by_name["Wrench"]))
    assert stats.pair_frequency[pair] == 2

    triple = frozenset((cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"]))
    assert stats.triple_frequency[triple] == 2

    # Suggesting the identical triple every time means all three cards are
    # present in *every* suggestion this player made.
    assert stats.always_suggested == frozenset(
        (cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"])
    )
    assert cards_by_name["Reverend Green"] not in stats.never_suggested
    assert cards_by_name["Miss Scarlett"] in stats.never_suggested


def test_category_lock_streak_captures_fixed_category_while_others_vary(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # Seat 1 holds WEAPON fixed at Wrench across four suggestions while
    # suspect and room both change every time -- a textbook "weapon hunter"
    # pattern. category_lock_streaks is keyed by the *fixed* category (per
    # the field's own contract), so WEAPON should show the long streak here,
    # not SUSPECT or ROOM (which both change every single suggestion and so
    # never exceed a streak of 1).
    suggestions = [
        ("Reverend Green", "Wrench", "Kitchen"),
        ("Mrs. Peacock", "Wrench", "Ballroom"),
        ("Professor Plum", "Wrench", "Conservatory"),
        ("Reverend Green", "Wrench", "Dining Room"),
    ]
    for suspect, weapon, room in suggestions:
        gs.record_suggestion(
            1, cards_by_name[suspect], cards_by_name[weapon], cards_by_name[room],
            [SuggestionResponse(2, "no_show")],
        )

    stats = analyze_player_patterns(gs, seat=1)

    assert stats.category_lock_streaks[CardType.WEAPON] == 4
    assert stats.category_lock_streaks[CardType.SUSPECT] == 1
    assert stats.category_lock_streaks[CardType.ROOM] == 1
    assert stats.favorite_weapon == cards_by_name["Wrench"]


def test_redundant_suggestion_count_uses_snapshot_at_time_not_final_state(cfg, cards_by_name, three_players):
    """Regression test for the plan's critical correctness detail: a
    suggestion must only be flagged "redundant" using what was known *at the
    time it was made* (via build_replay_snapshots), never using the final
    game state. Here, seat 1's first suggestion mentions Rope before anyone
    knows who owns it -- fine, not redundant. Only *after* that does a
    separate suggestion (by seat 2) reveal, via a shown_to_me response, that
    Rope belongs to seat 0. A buggy implementation that checked the final
    engine.confirmed instead of the per-suggestion snapshot would incorrectly
    flag seat 1's first suggestion as redundant too, purely because of
    information learned afterward. A later, third suggestion by seat 1 that
    mentions Rope *after* that reveal genuinely is redundant, and must still
    be counted -- proving the detector isn't just blind to Rope entirely.
    """
    gs = _basic_game(cfg, cards_by_name, three_players)

    # S1: seat 1 asks about Rope while its owner is still completely unknown.
    # (Alice/seat 0's known hand has neither Rope nor Reverend Green nor any
    # room, so her "no_show" here is trivially consistent.)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(0, "no_show")],
    )
    # S2: seat 0 suggests Rope too, and seat 2 (Carol) shows it to them,
    # confirming Rope belongs to seat 2 -- but only *after* S1 was made.
    gs.record_suggestion(
        0, cards_by_name["Mrs. Peacock"], cards_by_name["Rope"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    # S3: seat 1 asks about Rope again, now genuinely redundant since its
    # ownership (seat 2, not seat 1) was already confirmed before this point.
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Rope"], cards_by_name["Study"],
        [SuggestionResponse(0, "no_show")],
    )

    stats = analyze_player_patterns(gs, seat=1)

    assert stats.total_suggestions == 2
    assert stats.redundant_suggestion_count == 1  # only S3, never S1


def test_analyze_all_players_covers_every_seat(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show")],
    )

    all_stats = analyze_all_players(gs)

    assert set(all_stats.keys()) == {0, 1, 2}
    assert all_stats[1].total_suggestions == 1
    assert all_stats[0].total_suggestions == 0
    assert all_stats[0].never_suggested == frozenset(gs.cards)
