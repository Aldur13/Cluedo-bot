"""Tests for cluedo.explain.build_explanation_tree -- the nested
restructuring of the same DFS walk full_derivation_chain already performs."""
from cluedo.explain import build_explanation_tree, full_derivation_chain
from cluedo.game import GameState
from cluedo.models import CardType, Player


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


def _count_tree_nodes(node) -> int:
    return 1 + sum(_count_tree_nodes(c) for c in node.children)


def test_tree_root_matches_top_level_explanation(cfg):
    gs = _solved_game(cfg)
    suspect, _weapon, _room = gs.solution()
    explanation = gs.explain_card(suspect)
    assert explanation is not None

    tree = build_explanation_tree(explanation, gs.engine.explanations)
    assert tree.explanation is explanation


def test_tree_node_count_matches_flattened_chain_length(cfg):
    gs = _solved_game(cfg)
    for card in gs.cards:
        explanation = gs.explain_card(card)
        if explanation is None:
            continue
        chain = full_derivation_chain(explanation, gs.engine.explanations)
        tree = build_explanation_tree(explanation, gs.engine.explanations)
        assert _count_tree_nodes(tree) == len(chain)


def test_tree_never_infinite_loops_on_cycles(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    for card in gs.cards:
        explanation = gs.explain_card(card)
        if explanation is not None:
            tree = build_explanation_tree(explanation, gs.engine.explanations)
            assert _count_tree_nodes(tree) >= 1
