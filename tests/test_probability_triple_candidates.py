"""Tests for cluedo.probability.triple_probabilities/WorldCandidate --
World Explorer's data source."""
import pytest

from cluedo.game import GameState
from cluedo.models import ENVELOPE, CardType, Player
from cluedo.probability import TooManyAmbiguousCardsError, triple_probabilities


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


def test_probabilities_sum_to_one(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    worlds = triple_probabilities(gs.engine, max_ambiguous=21)
    assert worlds
    total = sum(w.probability for w in worlds)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_sorted_descending_by_probability(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    worlds = triple_probabilities(gs.engine, max_ambiguous=21)
    probs = [w.probability for w in worlds]
    assert probs == sorted(probs, reverse=True)


def test_solved_game_has_exactly_one_world_at_100_percent(cfg):
    gs = _solved_game(cfg)
    worlds = triple_probabilities(gs.engine, max_ambiguous=21)
    assert len(worlds) == 1
    assert worlds[0].probability == pytest.approx(1.0)
    suspect, weapon, room = gs.solution()
    assert (worlds[0].suspect, worlds[0].weapon, worlds[0].room) == (suspect, weapon, room)


def test_supporting_facts_are_real_possible_owners(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    worlds = triple_probabilities(gs.engine, max_ambiguous=21)
    for w in worlds[:5]:
        for card, owner_id in w.supporting_owner_facts:
            assert owner_id in gs.engine.possible_owners(card)
            assert card not in (w.suspect, w.weapon, w.room)


def test_too_many_ambiguous_raises(cfg, cards_by_name):
    from cluedo.models import Player

    players = [Player("Alice", 0, 3), Player("Bob", 1, 3), Player("Carol", 2, 3), Player("Dan", 3, 3), Player("Eve", 4, 3), Player("Fred", 5, 3)]
    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand([cards_by_name[n] for n in ["Miss Scarlett", "Colonel Mustard", "Mrs. White"]])
    with pytest.raises(TooManyAmbiguousCardsError):
        triple_probabilities(gs.engine, max_ambiguous=1)
