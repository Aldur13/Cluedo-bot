"""Tests for cluedo/analysis/game_review.py."""
from types import SimpleNamespace

import pytest

from cluedo.analysis.game_review import (
    _estimate_difficulty,
    _letter_grade,
    compute_game_review,
)
from cluedo.game import GameState
from cluedo.models import Card, CardType, Player, SuggestionResponse
from cluedo.timeseries import info_gained_per_turn
from cluedo.history import build_replay_snapshots


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _solve_immediately_game(cfg, cards_by_name, three_players):
    """One suggestion, by itself, fully solves the game -- verified by hand:
    Reverend Green/Rope/Kitchen asked by Alice, no_show from both other
    players, forces all three into the envelope via the two-of-three rule."""
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()
    return gs


def _two_player_instant_solve(cfg):
    """A 2-player game solved from the initial hand alone, zero suggestions
    needed -- mirrors tests/test_advisor.py's fixture."""
    all_cards = cfg.all_cards()
    withheld = {
        next(c for c in all_cards if c.type == CardType.SUSPECT),
        next(c for c in all_cards if c.type == CardType.WEAPON),
        next(c for c in all_cards if c.type == CardType.ROOM),
    }
    hand = [c for c in all_cards if c not in withheld]
    gs = GameState(cfg, [Player("Alice", 0, len(hand)), Player("Bob", 1, 0)], user_seat=0)
    gs.set_user_hand(hand)
    assert gs.is_solved()
    return gs


# --------------------------------------------------------------- unit tests


def test_letter_grade_thresholds():
    assert _letter_grade(100.0) == "A+"
    assert _letter_grade(97.0) == "A+"
    assert _letter_grade(96.9) == "A"
    assert _letter_grade(90.0) == "A-"
    assert _letter_grade(80.0) == "B-"
    assert _letter_grade(70.0) == "C-"
    assert _letter_grade(60.0) == "D"
    assert _letter_grade(59.9) == "F"
    assert _letter_grade(0.0) == "F"


def test_difficulty_scales_with_player_count(cfg, cards_by_name, three_players):
    gs3 = _basic_game(cfg, cards_by_name, three_players)
    snapshots3 = build_replay_snapshots(gs3)
    level3, _ = _estimate_difficulty(gs3, snapshots3, [])

    six_players = [Player(f"P{i}", i, 3) for i in range(6)]
    gs6 = GameState(cfg, six_players, user_seat=0)
    gs6.set_user_hand([c for c in cfg.all_cards()][:3])
    snapshots6 = build_replay_snapshots(gs6)
    level6, _ = _estimate_difficulty(gs6, snapshots6, [])

    from cluedo.analysis.game_review import _DIFFICULTY_LEVELS
    assert _DIFFICULTY_LEVELS.index(level6) >= _DIFFICULTY_LEVELS.index(level3)


def _stub_snapshots(ambiguous_counts: list[int]):
    """Minimal stand-in for build_replay_snapshots' output -- _estimate_difficulty
    only ever reads snap.game_state.last_solver_stats.ambiguous_card_count_last."""
    return [
        SimpleNamespace(game_state=SimpleNamespace(last_solver_stats=SimpleNamespace(ambiguous_card_count_last=n)))
        for n in ambiguous_counts
    ]


def test_difficulty_escalates_on_high_ambiguity_and_low_gain(cfg, three_players):
    gs = GameState(cfg, three_players, user_seat=0)

    calm_snapshots = _stub_snapshots([2, 3, 2])
    level_calm, explanation_calm = _estimate_difficulty(gs, calm_snapshots, [0.5, 0.6])
    assert level_calm == "Easy"
    assert "ambiguous" not in explanation_calm

    ambiguous_snapshots = _stub_snapshots([15, 16, 15])
    level_ambiguous, explanation_ambiguous = _estimate_difficulty(gs, ambiguous_snapshots, [0.5, 0.6])
    assert level_ambiguous == "Medium"  # one level up from the 3-player Easy baseline
    assert "ambiguous" in explanation_ambiguous

    low_gain_snapshots = _stub_snapshots([15, 16, 15])
    level_both, explanation_both = _estimate_difficulty(gs, low_gain_snapshots, [0.02, 0.01])
    assert level_both == "Hard"  # both penalties stack: two levels up from Easy
    assert "ambiguous" in explanation_both and "info gain" in explanation_both


# --------------------------------------------------------------- end-to-end


def test_optimal_turn_estimate_finds_earlier_solve_via_reordering(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # Turn 1: genuinely low-value filler. Bob shows ONE of the three cards
    # unseen (real Cluedo rule: the response chain stops there, so Carol is
    # never even asked) -- this only establishes the weak "Bob has at least
    # one of these three" disjunctive fact, not a definitive per-card
    # elimination. (A uniform no_show from *both* other players in a 3-player
    # game is actually maximally powerful, not weak: with only two other
    # seats, ruling both out for a card outside the asker's own hand leaves
    # the envelope as the only remaining owner, instantly solving everything
    # -- confirmed by hand while writing this test, which is why this filler
    # deliberately uses a partial-response turn instead.)
    gs.record_suggestion(
        0, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(1, "shown_unseen")],
    )
    assert not gs.is_solved()
    # Turn 2: the single suggestion proven (see _solve_immediately_game) to
    # fully solve the game on its own, regardless of what preceded it.
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()

    review = compute_game_review(gs)

    assert review.actual_solve_turn == 2
    assert review.estimated_optimal_solve_turn == 1
    assert review.turns_lost == 1
    assert review.efficiency_pct == pytest.approx(50.0)
    # An earlier-accusation opportunity must be reported at the estimated turn.
    assert any(
        m.kind == "earlier_accusation" and m.turn == 1 for m in review.missed_opportunities
    )


def test_missed_opportunities_never_flags_the_solving_turn(cfg, cards_by_name, three_players):
    gs = _solve_immediately_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    assert review.actual_solve_turn == 1
    assert not any(m.turn == 1 for m in review.missed_opportunities)


def test_zero_turn_instant_solve_gets_perfect_efficiency(cfg):
    gs = _two_player_instant_solve(cfg)
    review = compute_game_review(gs)

    assert review.is_solved is True
    assert review.turns_played == 0
    assert review.actual_solve_turn == 0
    assert review.estimated_optimal_solve_turn == 0
    assert review.turns_lost == 0
    assert review.efficiency_pct == pytest.approx(100.0)
    assert review.overall_rating == "A+"
    assert review.key_turning_point is None  # no suggestions were ever made
    assert review.largest_deduction is None


def test_unsolved_game_leaves_solve_dependent_fields_none(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)

    assert review.is_solved is False
    assert review.actual_solve_turn is None
    assert review.overall_rating is None
    assert review.efficiency_pct is None
    assert review.turns_lost is None
    # Still meaningful even unsolved:
    assert 0.0 <= review.final_accuracy_pct <= 100.0
    assert review.difficulty in ("Easy", "Medium", "Hard", "Expert")


def test_final_accuracy_reflects_partial_confirmation(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    expected = 100.0 * len(gs.engine.confirmed) / len(gs.cards)
    assert review.final_accuracy_pct == pytest.approx(expected)
    assert 0.0 < review.final_accuracy_pct < 100.0  # Alice's own hand is known, but not everything


def test_largest_deduction_matches_biggest_confirmed_jump(cfg, cards_by_name, three_players):
    gs = _solve_immediately_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)

    assert review.largest_deduction is not None
    assert review.largest_deduction.turn == 1
    assert review.largest_deduction.narrative  # non-empty, real explain.py narrative
    assert review.largest_deduction.newly_confirmed_count > 0


def test_timeline_is_chronologically_sorted_and_includes_game_solved(cfg, cards_by_name, three_players):
    gs = _solve_immediately_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)

    turns = [event.turn for event in review.timeline]
    assert turns == sorted(turns)
    assert any(event.label == "Game solved" for event in review.timeline)


def test_performance_metrics_lengths_match_turns_played(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )

    review = compute_game_review(gs)
    snapshots = build_replay_snapshots(gs)

    assert review.performance.total_suggestion_count == 2
    assert review.performance.info_gain_per_turn == info_gained_per_turn(snapshots)
    assert len(review.performance.valid_worlds_per_turn) == len(snapshots)
    assert review.performance.unique_suggestion_count == 2
    assert review.performance.redundant_suggestion_count == 0


def test_redundant_suggestion_is_detected_and_flagged(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    # S1: Bob asks about Rope before anyone knows who owns it.
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(0, "no_show")],
    )
    # S2: Carol shows Rope to Alice, confirming its owner is Carol.
    gs.record_suggestion(
        0, cards_by_name["Mrs. Peacock"], cards_by_name["Rope"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    # S3: Bob asks about Rope again -- now genuinely redundant.
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Rope"], cards_by_name["Study"],
        [SuggestionResponse(0, "no_show")],
    )

    review = compute_game_review(gs)
    assert review.performance.redundant_suggestion_count == 1
    assert any(m.kind == "redundant_suggestion" and m.turn == 3 for m in review.missed_opportunities)


def test_time_played_produces_average_per_turn(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )

    review = compute_game_review(gs, time_played_seconds=600.0)
    assert review.time_played_seconds == 600.0
    assert review.average_time_per_turn_seconds == pytest.approx(300.0)


def test_time_played_omitted_when_not_supplied(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    assert review.time_played_seconds is None
    assert review.average_time_per_turn_seconds is None
