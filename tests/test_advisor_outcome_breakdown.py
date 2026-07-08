"""Tests for cluedo.advisor's per-outcome breakdown extension --
OutcomeBreakdown / DetailedAdvisorCandidate / rank_candidates_detailed --
and that rank_candidates itself is unaffected (behavior-preserving)."""
import pytest

from cluedo.advisor import rank_candidates, rank_candidates_detailed
from cluedo.game import GameState


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_rank_candidates_unaffected_by_the_refactor(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    candidates = rank_candidates(gs, top_k=5)
    assert candidates
    for c in candidates:
        assert hasattr(c, "expected_info_gain")
        assert hasattr(c, "rationale")


def test_detailed_candidates_match_plain_candidates(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    plain = rank_candidates(gs, top_k=5)
    detailed = rank_candidates_detailed(gs, top_k=5)
    assert len(plain) == len(detailed)
    for p, d in zip(plain, detailed):
        assert (p.suspect, p.weapon, p.room) == (d.candidate.suspect, d.candidate.weapon, d.candidate.room)
        assert p.expected_info_gain == d.candidate.expected_info_gain


def test_outcome_probabilities_sum_to_one(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    detailed = rank_candidates_detailed(gs, top_k=1)
    assert detailed
    outcomes = detailed[0].outcomes
    assert outcomes
    total = sum(o.probability for o in outcomes)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_outcome_worlds_remaining_never_exceeds_current_total(cfg, cards_by_name, three_players):
    from cluedo.probability import count_worlds

    gs = _fresh_game(cfg, cards_by_name, three_players)
    current_total = count_worlds(gs.engine.counting_input())
    detailed = rank_candidates_detailed(gs, top_k=1)
    for outcome in detailed[0].outcomes:
        assert outcome.worlds_remaining <= current_total


def test_solved_game_returns_empty_list(cfg):
    from cluedo.models import CardType, Player

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
    assert rank_candidates_detailed(gs, top_k=5) == []
