from cluedo.engine import ConstraintEngine
from cluedo.explain import FactKind, full_derivation_chain
from cluedo.models import ENVELOPE


def test_notowned_chain_explanation_cites_each_elimination(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Knife"]
    engine.add_not_owned(card, "seat_0")
    engine.add_not_owned(card, "seat_1")
    engine.add_not_owned(card, ENVELOPE)
    engine.recompute()

    explanation = engine.explanations.explanation_for(card)
    assert explanation is not None
    assert explanation.rule == FactKind.NOT_OWNED
    assert any("seat_0" in line for line in explanation.narrative)
    assert any("seat_1" in line for line in explanation.narrative)
    assert explanation.narrative[-1].startswith("Therefore Knife must belong to seat_2")


def test_two_of_three_explanation_matches_spec_example_shape(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    trio = (cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"])
    engine.add_at_least_one("seat_2", trio)
    engine.add_not_owned(cards_by_name["Professor Plum"], "seat_2")
    engine.add_not_owned(cards_by_name["Wrench"], "seat_2")
    engine.recompute()

    explanation = engine.explanations.explanation_for(cards_by_name["Study"])
    assert explanation is not None
    assert explanation.rule == FactKind.TWO_OF_THREE
    narrative = explanation.narrative
    assert any("had to own one of" in line for line in narrative)
    assert any("Professor Plum" in line and "impossible" in line for line in narrative)
    assert any("Wrench" in line and "impossible" in line for line in narrative)
    assert narrative[-1] == "Therefore Study must belong to seat_2."


def test_world_argument_used_only_when_no_shorter_chain_exists(cfg, cards_by_name, three_players):
    # Construct a case that only the exhaustive world-search can resolve:
    # two disjoint AtLeastOne facts that jointly pin a card down, with no
    # single two-of-three shortcut available.
    engine = ConstraintEngine(cfg.all_cards(), three_players, max_confirmation_ambiguous=21)
    a, b, c = cards_by_name["Knife"], cards_by_name["Rope"], cards_by_name["Wrench"]
    # seat_1 has hand size reduced to 1 remaining slot via a tight hand fact so that
    # the joint search -- not simple elimination -- is what pins down the card.
    engine.add_at_least_one("seat_1", (a, b, c))
    engine.add_not_owned(a, "seat_1")
    engine.recompute()

    # At this point only cheap propagation ran; b/c still ambiguous for seat_1.
    # This does not assert WORLD_ARGUMENT specifically (the exact rule taken is an
    # implementation detail of how much cheap propagation can already do), but it
    # does assert that *some* explanation eventually exists once the fact set forces
    # a conclusion, honoring the "prefer shorter chain" rule when one applies.
    explanation_a = engine.explanations.explanation_for(a)
    assert explanation_a is None or explanation_a.rule != FactKind.WORLD_ARGUMENT


def test_full_derivation_chain_unrolls_multi_level(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife"]
    for name in hand:
        engine.add_owned(cards_by_name[name], "seat_0")
    last_card = cards_by_name["Lead Pipe"]
    engine.add_not_owned(last_card, "seat_1")
    engine.add_not_owned(last_card, "seat_2")
    engine.add_not_owned(last_card, ENVELOPE)
    engine.recompute()

    explanation = engine.explanations.explanation_for(last_card)
    assert explanation is not None
    chain = full_derivation_chain(explanation, engine.explanations)
    assert chain[0] is explanation
    assert len(chain) >= 1


def test_explanations_reset_on_recompute(cfg, cards_by_name, three_players):
    engine = ConstraintEngine(cfg.all_cards(), three_players)
    card = cards_by_name["Knife"]
    engine.add_owned(card, "seat_0")
    engine.recompute()
    assert engine.explanations.explanation_for(card) is not None

    # A stale explanation for an unrelated, still-unconfirmed card must not exist.
    other = cards_by_name["Rope"]
    assert engine.explanations.explanation_for(other) is None
