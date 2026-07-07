"""Tests for cluedo/analysis/live_events.py -- confirmed-card diffs shared
by the Recent Deductions and Timeline sidebar cards."""
from cluedo.analysis.live_events import confirmed_card_events, owner_display_name, turns_with_new_confirmations
from cluedo.game import GameState
from cluedo.models import CardType, Player, SuggestionResponse


_HAND_NAMES = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    gs.set_user_hand([cards_by_name[n] for n in _HAND_NAMES])
    return gs


def _not_in_hand(cards):
    # Claiming an opponent "shows" a card already known to be in Alice's
    # (the user's) hand is an immediate contradiction -- every test that
    # fabricates a shown_to_me response must pick cards outside her hand.
    return [c for c in cards if c.name not in _HAND_NAMES]


def test_no_events_for_a_fresh_game_with_no_suggestions(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert confirmed_card_events(gs) == []
    assert turns_with_new_confirmations(gs) == set()


def test_starting_hand_confirmations_are_not_events(cfg, cards_by_name, three_players):
    # set_user_hand() alone confirms the user's own 6 cards, but that's not
    # a deduction from a suggestion -- it must not appear as an event.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    events = confirmed_card_events(gs)
    assert all(e.turn >= 1 for e in events)
    assert events == []  # no suggestions logged yet either


def test_solved_from_hand_set_alone_produces_no_turn_events(cfg):
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

    # This fixture solves on hand-set alone (no suggestions), so there are
    # no *turn* events -- confirms the "no suggestion, no event" invariant
    # even when the game ends up solved.
    assert confirmed_card_events(gs) == []


def test_events_are_ordered_by_turn(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = _not_in_hand([c for c in gs.cards if c.type == CardType.WEAPON])
    rooms = _not_in_hand([c for c in gs.cards if c.type == CardType.ROOM])

    # shown_to_me directly names the card for each suggestion -- an
    # immediate, unambiguous ownership fact that can't create the kind of
    # cross-suggestion contradiction a weaker shown_unseen/no_show mix can.
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "shown_to_me", shown_card=weapons[0]), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        0, suspects[1], weapons[1], rooms[1],
        [SuggestionResponse(2, "shown_to_me", shown_card=rooms[1]), SuggestionResponse(1, "no_show")],
    )

    events = confirmed_card_events(gs)
    turns = [e.turn for e in events]
    assert turns == sorted(turns)
    assert set(turns) <= {1, 2}
    assert 1 in turns and 2 in turns


def test_owner_display_name_maps_envelope_and_players(cfg, cards_by_name, three_players):
    from cluedo.models import ENVELOPE

    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert owner_display_name(gs, ENVELOPE) == "the envelope"
    assert owner_display_name(gs, gs.players[0].owner_id) == gs.players[0].name


def test_owner_display_name_falls_back_to_raw_id_for_unknown_owner(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    assert owner_display_name(gs, "not_a_real_owner") == "not_a_real_owner"
