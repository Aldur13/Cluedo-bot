"""Tests for cluedo.analysis.live_stats.compute_live_stats / confidence_tier."""
import pytest

from cluedo.analysis.live_stats import compute_live_stats, confidence_tier
from cluedo.game import GameState
from cluedo.models import CardType, Player, SuggestionResponse


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _solved_game(cfg):
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


def test_solved_game_is_certain_with_zero_entropy(cfg):
    gs = _solved_game(cfg)
    stats = compute_live_stats(gs)
    assert stats.confidence_tier == "Certain"
    assert stats.entropy_bits == 0.0
    assert stats.expected_turns_to_solve == 0.0
    assert stats.unknown_cards == 0


def test_fresh_game_has_confirmed_and_unknown_counts(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    stats = compute_live_stats(gs)
    assert stats.confirmed_cards == len(gs.engine.confirmed)
    assert stats.confirmed_cards + stats.unknown_cards == len(gs.cards)
    assert stats.confidence_tier in ("Very Low", "Low", "Medium", "High", "Certain")


def test_confidence_tier_thresholds():
    assert confidence_tier(None, is_solved=False)[0] == "Very Low"
    assert confidence_tier(1, is_solved=False)[0] == "Certain"
    assert confidence_tier(3, is_solved=False)[0] == "High"
    assert confidence_tier(30, is_solved=False)[0] == "Medium"
    assert confidence_tier(300, is_solved=False)[0] == "Low"
    assert confidence_tier(3000, is_solved=False)[0] == "Very Low"
    assert confidence_tier(5, is_solved=True)[0] == "Certain"


def test_probability_stability_none_for_a_fresh_game_with_no_history(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    stats = compute_live_stats(gs)
    assert stats.probability_stability is None


def test_probability_stability_is_a_fraction_once_turns_exist(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    stats = compute_live_stats(gs)
    assert stats.probability_stability is not None
    assert 0.0 <= stats.probability_stability <= 1.0
