"""Tests for cluedo.analysis.strategy: explainable threshold-based
classification on top of PlayerPatternStats.
"""
from cluedo.analysis.patterns import analyze_player_patterns
from cluedo.analysis.strategy import PlayerStrategy, classify_strategy
from cluedo.game import GameState
from cluedo.models import SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_insufficient_data_returns_balanced(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Wrench"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Mrs. Peacock"], cards_by_name["Rope"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "no_show")],
    )

    stats = analyze_player_patterns(gs, seat=1)
    strategy, evidence = classify_strategy(stats)

    assert stats.total_suggestions == 2  # below MIN_SUGGESTIONS_FOR_CLASSIFICATION
    assert strategy is PlayerStrategy.BALANCED
    assert evidence["reason"] == "insufficient_data"


def test_weapon_hunter_classification(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # Same "fixed weapon, varying suspect/room" pattern as
    # test_analysis_patterns.test_category_lock_streak_captures_fixed_category_while_others_vary.
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
    strategy, evidence = classify_strategy(stats)

    assert strategy is PlayerStrategy.WEAPON_HUNTER
    assert evidence["category"] == "weapon"
    assert evidence["lock_streak"] == 4
    assert evidence["lock_ratio"] == 1.0


def test_bluffer_classification(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # S1: seat 1 asks about Rope before anyone knows who owns it. (Alice's
    # known hand has none of Reverend Green/Rope/Kitchen, so her no_show is
    # trivially consistent.)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(0, "no_show")],
    )
    # S2: seat 0 suggests Rope too, and seat 2 shows it to them, confirming
    # its owner (seat 2) -- but only after S1 was already made.
    gs.record_suggestion(
        0, cards_by_name["Mrs. Peacock"], cards_by_name["Rope"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    # S3: seat 1 asks about Rope again -- genuinely redundant this time,
    # since Rope's ownership (seat 2, not seat 1) is now confirmed.
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Rope"], cards_by_name["Study"],
        [SuggestionResponse(0, "no_show")],
    )
    # S4: a third, unrelated suggestion by seat 1 to reach the classification
    # floor of 3 suggestions with a clean 1-in-3 redundant ratio. Uses only
    # cards outside Alice's known hand so it doesn't accidentally count as
    # redundant too.
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Revolver"], cards_by_name["Library"],
        [SuggestionResponse(0, "no_show")],
    )

    stats = analyze_player_patterns(gs, seat=1)
    strategy, evidence = classify_strategy(stats)

    assert stats.total_suggestions == 3
    assert stats.redundant_suggestion_count == 1
    assert strategy is PlayerStrategy.BLUFFER
    assert evidence["redundant_ratio"] == 1 / 3


def test_aggressive_eliminator_classification(cfg, cards_by_name, three_players):
    # User seat is Carol (seat 2) this time, holding all 6 rooms that are
    # *not* among the 3 rooms our aggressive suggester leaves untouched
    # (Dining Room/Billiard Room/Library). In a 21-card deck, a 6-card known
    # hand can never be fully disjoint from an 18-card "tried nearly
    # everything" suggestion set (pigeonhole: 6 + 18 > 21 forces at least 3
    # cards to overlap) -- so 3 of seat 1's suggestions below are genuinely,
    # correctly flagged redundant (they mention a room Carol already holds).
    #
    # There's a second, less obvious overlap too: by the time suggestion #3
    # (Reverend Green/Revolver/Dining Room) has been answered, seat 0 (Alice)
    # has had 9 of her 15 non-Carol candidate cards ruled out via no_show
    # responses, and 15 - 9 == 6 == her exact hand size -- the solver's
    # world-search pigeonholes her whole hand at that point, which is why
    # suggestion #4 (Mrs. Peacock/Rope/Billiard Room) also comes back
    # genuinely redundant (all three already confirmed hers). That's 4
    # redundant suggestions out of the first 6, not 3.
    #
    # Seven filler repeats (rather than four) of an already-non-redundant
    # triple dilute the redundant ratio comfortably below the bluffer
    # threshold (4/13 ≈ 0.31 < 1/3) without adding new distinct cards, so
    # coverage still reads 18/21 and AGGRESSIVE_ELIMINATOR fires as intended.
    gs = GameState(cfg, three_players, user_seat=2)
    carols_hand = ["Kitchen", "Ballroom", "Conservatory", "Lounge", "Hall", "Study"]
    gs.set_user_hand([cards_by_name[n] for n in carols_hand])

    suggestions = [
        ("Miss Scarlett", "Candlestick", "Kitchen"),
        ("Colonel Mustard", "Knife", "Ballroom"),
        ("Mrs. White", "Lead Pipe", "Conservatory"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Mrs. Peacock", "Rope", "Billiard Room"),
        ("Professor Plum", "Wrench", "Library"),
        # Filler repeats of an already-non-redundant triple: adds no new
        # distinct cards (coverage unchanged) and never extends a
        # category-lock streak (repeating a whole triple always resets a
        # streak, per _category_lock_streaks' "others must vary" rule).
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
        ("Reverend Green", "Revolver", "Dining Room"),
    ]
    for suspect, weapon, room in suggestions:
        gs.record_suggestion(
            1, cards_by_name[suspect], cards_by_name[weapon], cards_by_name[room],
            [SuggestionResponse(0, "no_show")],
        )

    stats = analyze_player_patterns(gs, seat=1)
    strategy, evidence = classify_strategy(stats)

    assert stats.total_suggestions == 13
    # Kitchen/Ballroom/Conservatory (already Carol's) plus Mrs. Peacock/Rope/
    # Billiard Room (pigeonholed onto Alice right after suggestion #3).
    assert stats.redundant_suggestion_count == 4
    assert strategy is PlayerStrategy.AGGRESSIVE_ELIMINATOR
    assert evidence["coverage"] == 18 / 21
