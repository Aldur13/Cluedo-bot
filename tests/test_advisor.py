from cluedo.advisor import rank_candidates
from cluedo.game import GameState
from cluedo.models import SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_rank_candidates_returns_scored_list(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    candidates = rank_candidates(gs, top_k=6)
    assert len(candidates) > 0
    for c in candidates:
        assert 0.0 <= c.expected_info_gain <= 1.0 + 1e-9
        assert "eliminate" in c.rationale


def test_rank_candidates_sorted_descending_by_info_gain(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    candidates = rank_candidates(gs, top_k=6)
    gains = [c.expected_info_gain for c in candidates]
    assert gains == sorted(gains, reverse=True)


def test_rank_candidates_empty_once_solved(cfg):
    from cluedo.models import CardType, Player

    # A 2-player game where Alice's hand is every card except exactly one
    # suspect/weapon/room leaves those three forced straight into the
    # envelope -- solved immediately, with nothing left to advise about.
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
    assert rank_candidates(gs) == []


def test_top_k_pruning_limits_full_evaluation(cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    small = rank_candidates(gs, top_k=1)
    large = rank_candidates(gs, top_k=20)
    assert len(small) == 1
    assert len(large) >= len(small)
    # The single top-1 result must also appear among the top-20 results.
    assert small[0].suspect in {c.suspect for c in large}
