import pytest

from cluedo.engine import ConstraintEngine, ContradictionError
from cluedo.explain import FactKind
from cluedo.models import ENVELOPE


def test_notowned_chain_confirms_singleton(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Knife"]
    engine.add_not_owned(card, "seat_0")
    engine.add_not_owned(card, "seat_1")
    engine.add_not_owned(card, ENVELOPE)
    engine.recompute()
    assert engine.owner_of(card) == "seat_2"


def test_owned_fact_confirms_immediately(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Rope"]
    engine.add_owned(card, "seat_1")
    engine.recompute()
    assert engine.owner_of(card) == "seat_1"


def test_hand_full_removes_owner_from_other_cards(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    for name in hand:
        engine.add_owned(cards_by_name[name], "seat_0")
    engine.recompute()
    other = cards_by_name["Rope"]
    assert "seat_0" not in engine.possible_owners(other)


def test_hand_full_hidden_singles_confirms_remaining_cards(cfg, cards_by_name, three_players):
    # Give seat_0 5 of their 6 cards; if only 1 undetermined candidate remains
    # for their last slot, it must be confirmed to them.
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife"]
    for name in hand:
        engine.add_owned(cards_by_name[name], "seat_0")
    last_card = cards_by_name["Lead Pipe"]
    # Rule out every other owner for this card, leaving seat_0 as the only candidate.
    engine.add_not_owned(last_card, "seat_1")
    engine.add_not_owned(last_card, "seat_2")
    engine.add_not_owned(last_card, ENVELOPE)
    engine.recompute()
    assert engine.owner_of(last_card) == "seat_0"


def test_two_of_three_disjunction_resolves(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    trio = (cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"])
    engine.add_at_least_one("seat_2", trio)
    engine.add_not_owned(cards_by_name["Professor Plum"], "seat_2")
    engine.add_not_owned(cards_by_name["Wrench"], "seat_2")
    engine.recompute()
    assert engine.owner_of(cards_by_name["Study"]) == "seat_2"
    explanation = engine.explanations.explanation_for(cards_by_name["Study"])
    assert explanation is not None
    assert "Study must belong to seat_2" in explanation.narrative[-1]


def test_solution_detection_partial_forces_last_category(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    engine.add_owned(cards_by_name["Miss Scarlett"], ENVELOPE)
    engine.add_owned(cards_by_name["Rope"], ENVELOPE)
    rooms = list(cfg.rooms)
    for name in rooms[:-1]:
        engine.add_not_owned(cards_by_name[name], ENVELOPE)
    engine.recompute()
    assert engine.is_solved()
    suspect, weapon, room = engine.solution()
    assert suspect.name == "Miss Scarlett"
    assert weapon.name == "Rope"
    assert room.name == rooms[-1]


def test_no_information_leaves_cards_unknown(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    engine.recompute()
    assert engine.owner_of(cards_by_name["Knife"]) is None
    assert not engine.is_solved()


def test_contradiction_domain_empty(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Knife"]
    for owner in ("seat_0", "seat_1", "seat_2", ENVELOPE):
        engine.add_not_owned(card, owner)
    with pytest.raises(ContradictionError) as exc_info:
        engine.recompute()
    assert exc_info.value.kind == "domain_empty"


def test_contradiction_hand_size_exceeded(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    hand = [
        "Miss Scarlett", "Colonel Mustard", "Mrs. White",
        "Candlestick", "Knife", "Lead Pipe", "Revolver",
    ]
    for name in hand:
        engine.add_owned(cards_by_name[name], "seat_0")
    with pytest.raises(ContradictionError) as exc_info:
        engine.recompute()
    assert exc_info.value.kind == "hand_size_exceeded"
    assert exc_info.value.detail["count"] == 7
    assert exc_info.value.detail["hand_size"] == 6


def test_contradiction_envelope_category_exceeded(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    engine.add_owned(cards_by_name["Miss Scarlett"], ENVELOPE)
    engine.add_owned(cards_by_name["Colonel Mustard"], ENVELOPE)
    with pytest.raises(ContradictionError) as exc_info:
        engine.recompute()
    assert exc_info.value.kind == "envelope_category_exceeded"


def test_contradiction_zero_valid_worlds_from_impossible_at_least_one(cfg, cards_by_name, three_players):
    # Cheap two-of-three propagation only fires when exactly 2 of 3 are
    # excluded; excluding all 3 has no single-card/single-player symptom and
    # can only be caught by the joint model-counting check.
    engine = ConstraintEngine(cfg.all_cards(), three_players, max_confirmation_ambiguous=25)
    x, y, z = cards_by_name["Knife"], cards_by_name["Rope"], cards_by_name["Wrench"]
    engine.add_at_least_one("seat_0", (x, y, z))
    engine.add_not_owned(x, "seat_0")
    engine.add_not_owned(y, "seat_0")
    engine.add_not_owned(z, "seat_0")
    with pytest.raises(ContradictionError) as exc_info:
        engine.recompute()
    assert exc_info.value.kind == "zero_valid_worlds"


def test_world_search_confirmation_narrows_possible_owners(cfg, cards_by_name, three_players):
    """Regression: _confirm() used to set engine.confirmed[card] without
    narrowing engine.possible[card] to {owner}. Cheap-propagation confirms
    only ever fire once possible[card] is already a singleton, so this only
    showed up for cards confirmed via _confirm_via_world_search, where the
    domain can still have other members at confirmation time. Consumers like
    probability.py/advisor.py query possible_owners() directly (not gated on
    `card in engine.confirmed`), so a stale multi-owner domain fed wrong
    envelope-eligibility into World Explorer probabilities and advisor
    rankings for any card confirmed this way."""
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Knife"]
    assert len(engine.possible_owners(card)) > 1  # nothing has narrowed it yet

    engine._confirm(card, "seat_1", FactKind.WORLD_ARGUMENT, [], "test")

    assert engine.owner_of(card) == "seat_1"
    assert engine.possible_owners(card) == {"seat_1"}
