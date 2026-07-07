"""Tests for cluedo/analysis/endgame.py. The one hard rule: never recommend
a specific suspect/weapon/room accusation while the game isn't solved --
only report confidence percentages, never a named candidate card.
"""
from cluedo.analysis.endgame import suggest_accusation_readiness
from cluedo.game import GameState
from cluedo.models import CardType, Player


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_unsolved_game_reports_not_safe_and_no_named_card(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    advice = suggest_accusation_readiness(gs)

    assert advice.safe_to_accuse is False
    assert advice.solution is None
    # Never names a specific unconfirmed card as a likely accusation target.
    for card in gs.cards:
        if gs.engine.owner_of(card) is None:
            assert card.name not in advice.message


def test_solved_game_reports_safe_with_the_actual_solution(cfg):
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

    advice = suggest_accusation_readiness(gs)

    assert advice.safe_to_accuse is True
    assert advice.solution == gs.solution()
    suspect, weapon, room = gs.solution()
    assert suspect.name in advice.message
    assert weapon.name in advice.message
    assert room.name in advice.message
    assert advice.category_confidence == {
        CardType.SUSPECT: 1.0, CardType.WEAPON: 1.0, CardType.ROOM: 1.0,
    }


def test_early_game_too_ambiguous_reports_unknown_confidence_not_a_guess(cfg, three_players):
    # No hand set at all: every card ambiguous, well past probability.py's
    # exact-computation gate -- must degrade to "too many unknowns", never a
    # fabricated confidence number.
    gs = GameState(cfg, three_players, user_seat=0)
    advice = suggest_accusation_readiness(gs)

    assert advice.safe_to_accuse is False
    assert advice.solution is None
    assert all(v is None for v in advice.category_confidence.values())
