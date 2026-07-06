import itertools

import pytest

from cluedo.models import ENVELOPE, Card, CardType
from cluedo.probability import (
    AmbiguousCard,
    CountingInput,
    TooManyAmbiguousCardsError,
    capacity_key,
    compute_probabilities,
    full_probabilities,
)


def _make_ci():
    s1, s2 = Card("s1", CardType.SUSPECT), Card("s2", CardType.SUSPECT)
    w1, w2 = Card("w1", CardType.WEAPON), Card("w2", CardType.WEAPON)
    r1, r2 = Card("r1", CardType.ROOM), Card("r2", CardType.ROOM)
    cards = [s1, s2, w1, w2, r1, r2]
    owners = ("seat_0", "seat_1", ENVELOPE)
    ambiguous = tuple(AmbiguousCard(c, owners) for c in cards)
    capacities = {
        "seat_0": 2,
        "seat_1": 1,
        capacity_key(ENVELOPE, CardType.SUSPECT): 1,
        capacity_key(ENVELOPE, CardType.WEAPON): 1,
        capacity_key(ENVELOPE, CardType.ROOM): 1,
    }
    ci = CountingInput(ambiguous=ambiguous, capacities=capacities, at_least_one=())
    return ci, cards


def _valid_assignments(ci):
    for assignment in itertools.product(*[ac.domain for ac in ci.ambiguous]):
        owner_of = dict(zip((ac.card for ac in ci.ambiguous), assignment))
        counts = {}
        for card, owner in owner_of.items():
            key = capacity_key(owner, card.type)
            counts[key] = counts.get(key, 0) + 1
        if all(counts.get(key, 0) == cap for key, cap in ci.capacities.items()):
            if all(
                any(owner_of[c] == owner for c in cards_)
                for owner, cards_ in ci.at_least_one
            ):
                yield owner_of


def _brute_force_tallies(ci, cards):
    valid = list(_valid_assignments(ci))
    tallies = {c: {} for c in cards}
    for assignment in valid:
        for card, owner in assignment.items():
            tallies[card][owner] = tallies[card].get(owner, 0) + 1
    return tallies, len(valid)


def test_exact_probabilities_match_brute_force_oracle():
    ci, cards = _make_ci()
    probs = compute_probabilities(ci)
    tallies, total = _brute_force_tallies(ci, cards)
    assert probs.total_worlds == total
    for card in cards:
        for owner, count in tallies[card].items():
            assert probs.per_card[card][owner] == pytest.approx(count / total)


def test_probabilities_sum_to_one_per_card():
    ci, _ = _make_ci()
    probs = compute_probabilities(ci)
    for card_probs in probs.per_card.values():
        assert sum(card_probs.values()) == pytest.approx(1.0)


def test_at_least_one_reduces_and_matches_oracle():
    ci, cards = _make_ci()
    s1, w1, r1 = cards[0], cards[2], cards[4]
    ci_with_alo = CountingInput(
        ambiguous=ci.ambiguous,
        capacities=ci.capacities,
        at_least_one=(("seat_1", frozenset((s1, w1, r1))),),
    )
    probs_plain = compute_probabilities(ci)
    probs_alo = compute_probabilities(ci_with_alo)
    assert probs_alo.total_worlds < probs_plain.total_worlds

    _, expected_total = _brute_force_tallies(ci_with_alo, cards)
    assert probs_alo.total_worlds == expected_total


def test_too_many_ambiguous_cards_raises_instead_of_hanging():
    ci, _ = _make_ci()
    with pytest.raises(TooManyAmbiguousCardsError):
        compute_probabilities(ci, max_ambiguous=3)


def test_full_probabilities_gives_confirmed_cards_probability_one():
    class FakeEngine:
        def __init__(self, ci, confirmed):
            self._ci = ci
            self.confirmed = confirmed

        def counting_input(self):
            return self._ci

    ci, cards = _make_ci()
    s1 = cards[0]
    remaining = tuple(ac for ac in ci.ambiguous if ac.card != s1)
    reduced_capacities = dict(ci.capacities)
    reduced_capacities["seat_0"] -= 1
    reduced_ci = CountingInput(ambiguous=remaining, capacities=reduced_capacities, at_least_one=())

    engine = FakeEngine(reduced_ci, {s1: "seat_0"})
    result = full_probabilities(engine)

    assert result[s1] == {"seat_0": 1.0}
    for card in cards:
        if card != s1:
            assert sum(result[card].values()) == pytest.approx(1.0)


def test_probability_engine_stays_fast_on_realistic_state(cfg, cards_by_name, three_players):
    import time

    from cluedo.engine import ConstraintEngine
    from cluedo.probability import compute_probabilities as cp

    engine = ConstraintEngine(cfg.all_cards(), three_players)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    for name in hand:
        engine.add_owned(cards_by_name[name], "seat_0")
    engine.recompute()

    start = time.perf_counter()
    ci = engine.counting_input()
    if len(ci.ambiguous) <= 14:
        cp(ci)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, "probability computation is far slower than expected for this small a state"
