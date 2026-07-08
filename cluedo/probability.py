"""Exact model counting over the small set of still-ambiguous cards.

The engine already reduces most of the 21 cards to a single confirmed owner via
propagation; only the remaining "ambiguous" cards (those with more than one
candidate owner) need to be branched over here. That keeps this module's search
space tiny in realistic play, while still producing *exact* counts/probabilities
(no sampling, no approximation) as required by the product spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from cluedo.models import ENVELOPE, Card, CardType


def capacity_key(owner: str, card_type: CardType) -> str:
    """Players share one capacity across all categories (their total hand size);
    the envelope has an independent capacity of 1 *per category*. This maps a
    (owner, card-category) pair to the right capacity bucket for the DP, while
    the domain/output value for "who owns this card" stays the plain owner id
    (player seat id or ENVELOPE) throughout."""
    if owner == ENVELOPE:
        return f"{ENVELOPE}:{card_type.value}"
    return owner


@dataclass(frozen=True)
class AmbiguousCard:
    card: Card
    domain: tuple[str, ...]


@dataclass(frozen=True)
class CountingInput:
    """Everything the DP needs, already reduced to just the ambiguous cards."""

    ambiguous: tuple[AmbiguousCard, ...]
    capacities: Mapping[str, int]  # capacity_key(owner, category) -> remaining slots among `ambiguous`
    at_least_one: tuple[tuple[str, frozenset], ...]  # (owner, {card,card,card}) not yet satisfied


class TooManyAmbiguousCardsError(Exception):
    """Raised instead of attempting an intractable exact count.

    This is purely a UX gate on *when* to attempt exact computation (e.g. before
    the first suggestion is logged, when nearly all 21 cards are still ambiguous)
    -- it never causes an approximate/wrong answer to be returned.
    """

    def __init__(self, ambiguous_count: int, threshold: int):
        self.ambiguous_count = ambiguous_count
        self.threshold = threshold
        super().__init__(
            f"{ambiguous_count} cards are still ambiguous (limit {threshold}) -- "
            "not enough information yet to compute exact probabilities."
        )


@dataclass(frozen=True)
class Probabilities:
    per_card: dict  # Card -> {owner_id: probability}, sums to 1.0 per card
    total_worlds: int
    ambiguous_card_count: int


def _owner_order(capacities: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(sorted(capacities.keys()))


def count_worlds(ci: CountingInput) -> int:
    """Exact count of valid completions of the ambiguous cards.

    DP state = (index into `ambiguous`, remaining-capacity tuple, bitmask of which
    AtLeastOne constraints are already satisfied). Reachable states stay small
    because capacities only decrease and most branches prune immediately via a
    full owner or an already-satisfied AtLeastOne bit.
    """
    owners = _owner_order(ci.capacities)
    owner_index = {o: i for i, o in enumerate(owners)}
    cap_tuple = tuple(ci.capacities[o] for o in owners)
    alo_list = list(ci.at_least_one)
    full_mask = (1 << len(alo_list)) - 1 if alo_list else 0
    memo: dict = {}

    def rec(index: int, cap: tuple, mask: int) -> int:
        if index == len(ci.ambiguous):
            return 1 if mask == full_mask else 0
        key = (index, cap, mask)
        cached = memo.get(key)
        if cached is not None:
            return cached
        ac = ci.ambiguous[index]
        total = 0
        for owner in ac.domain:
            oi = owner_index[capacity_key(owner, ac.card.type)]
            if cap[oi] <= 0:
                continue
            new_cap = cap[:oi] + (cap[oi] - 1,) + cap[oi + 1 :]
            new_mask = mask
            for i, (alo_owner, cards) in enumerate(alo_list):
                if alo_owner == owner and ac.card in cards:
                    new_mask |= 1 << i
            total += rec(index + 1, new_cap, new_mask)
        memo[key] = total
        return total

    return rec(0, cap_tuple, 0)


def has_any_valid_world(ci: CountingInput) -> bool:
    """Existence check. Implemented via count_worlds for simplicity/correctness;
    the ambiguous-set cap upstream keeps this cheap regardless."""
    return count_worlds(ci) > 0


def _pin(ci: CountingInput, card: Card, owner: str) -> CountingInput:
    new_ambiguous = tuple(
        AmbiguousCard(ac.card, (owner,)) if ac.card == card else ac for ac in ci.ambiguous
    )
    return CountingInput(ambiguous=new_ambiguous, capacities=ci.capacities, at_least_one=ci.at_least_one)


def _pin_many(ci: CountingInput, cards: Sequence[Card], owner: str) -> CountingInput:
    card_set = set(cards)
    new_ambiguous = tuple(
        AmbiguousCard(ac.card, (owner,)) if ac.card in card_set else ac for ac in ci.ambiguous
    )
    return CountingInput(ambiguous=new_ambiguous, capacities=ci.capacities, at_least_one=ci.at_least_one)


def compute_probabilities(ci: CountingInput, *, max_ambiguous: int = 14) -> Probabilities:
    """Exact per-card, per-owner probabilities, derived only from valid worlds."""
    if len(ci.ambiguous) > max_ambiguous:
        raise TooManyAmbiguousCardsError(len(ci.ambiguous), max_ambiguous)

    total = count_worlds(ci)
    per_card: dict = {}
    if total == 0:
        # A contradictory state should have already been caught by the engine's
        # own contradiction checks before probabilities are requested.
        for ac in ci.ambiguous:
            per_card[ac.card] = {owner: 0.0 for owner in ac.domain}
        return Probabilities(per_card=per_card, total_worlds=0, ambiguous_card_count=len(ci.ambiguous))

    for ac in ci.ambiguous:
        tallies = {}
        for owner in ac.domain:
            tallies[owner] = count_worlds(_pin(ci, ac.card, owner))
        per_card[ac.card] = {owner: count / total for owner, count in tallies.items()}

    return Probabilities(per_card=per_card, total_worlds=total, ambiguous_card_count=len(ci.ambiguous))


def full_probabilities(engine, *, max_ambiguous: int = 14) -> dict:
    """Merges trivial probability-1.0 entries for already-confirmed cards with
    the exact DP-derived probabilities for the remaining ambiguous cards, so
    callers (GUI, advisor) get one complete per-card view without needing to
    special-case confirmed cards themselves."""
    result: dict = {card: {owner: 1.0} for card, owner in engine.confirmed.items()}
    ci = engine.counting_input()
    if ci.ambiguous:
        probs = compute_probabilities(ci, max_ambiguous=max_ambiguous)
        result.update(probs.per_card)
    return result


@dataclass(frozen=True)
class WorldCandidate:
    """One still-possible envelope triple ("world" in the product spec's
    sense -- a candidate solution, not a full per-card assignment; see
    triple_probabilities' docstring for why). `supporting_owner_facts` is a
    real, structured (card, owner_id) fact list -- who else may still hold
    which other ambiguous card in a world consistent with this triple --
    left un-rendered (raw owner ids, no display names) so the GUI layer
    decides phrasing/name-mapping, matching this module's existing
    name-agnostic convention (see probability_of_response_outcome)."""

    suspect: Card
    weapon: Card
    room: Card
    probability: float
    supporting_owner_facts: tuple[tuple[Card, str], ...]


def triple_probabilities(engine, *, max_ambiguous: int = 14) -> list["WorldCandidate"]:
    """Every still-possible (suspect, weapon, room) envelope triple with its
    exact joint probability -- the World Explorer's data source.

    Deliberately triple-level, not a full per-card world enumeration:
    `count_worlds` is an exact DP counter that never materializes individual
    full assignments (enumerating those would be combinatorially large and
    mostly irrelevant to a player choosing between candidate solutions).
    This instead mirrors `advisor.py::_candidate_triples`'s own
    envelope-eligible enumeration, then computes each triple's exact
    probability by pinning all three cards to the envelope and re-running
    the same `count_worlds` DP used everywhere else in this module -- same
    `max_ambiguous` gate and exception as `compute_probabilities`, so this
    is exact whenever it doesn't raise, never an approximation.

    Results are sorted by probability descending; only triples with a
    nonzero world count are returned (a triple every remaining fact has
    already ruled out isn't a "candidate").
    """
    ci = engine.counting_input()
    if len(ci.ambiguous) > max_ambiguous:
        raise TooManyAmbiguousCardsError(len(ci.ambiguous), max_ambiguous)

    def _envelope_eligible(card_type: CardType) -> list[Card]:
        return [c for c in engine.cards if c.type == card_type and ENVELOPE in engine.possible_owners(c)]

    suspects = _envelope_eligible(CardType.SUSPECT)
    weapons = _envelope_eligible(CardType.WEAPON)
    rooms = _envelope_eligible(CardType.ROOM)

    total = count_worlds(ci)
    if total == 0:
        return []

    candidates: list[WorldCandidate] = []
    for suspect in suspects:
        for weapon in weapons:
            for room in rooms:
                trio = (suspect, weapon, room)
                pinned = _pin_many(ci, trio, ENVELOPE)
                count = count_worlds(pinned)
                if count == 0:
                    continue

                trio_set = set(trio)
                facts: list[tuple[Card, str]] = []
                for ac in pinned.ambiguous:
                    if ac.card in trio_set or len(ac.domain) <= 1:
                        continue
                    facts.append((ac.card, ac.domain[0]))
                    if len(facts) >= 3:
                        break

                candidates.append(
                    WorldCandidate(suspect, weapon, room, count / total, tuple(facts))
                )

    candidates.sort(key=lambda w: w.probability, reverse=True)
    return candidates


def envelope_probability(probabilities: Probabilities, card: Card) -> float:
    """Convenience accessor: probability a (possibly-confirmed) card is in the
    envelope. Cards not present in `probabilities.per_card` are assumed already
    confirmed by the caller and should be handled before calling this."""
    return probabilities.per_card.get(card, {}).get(ENVELOPE, 0.0)


def _exclude_owner_for_cards(ci: CountingInput, owner: str, cards: Sequence[Card]) -> CountingInput:
    """Transiently remove `owner` from the domain of the given ambiguous cards."""
    card_set = set(cards)
    new_ambiguous = tuple(
        AmbiguousCard(ac.card, tuple(o for o in ac.domain if o != owner)) if ac.card in card_set else ac
        for ac in ci.ambiguous
    )
    return CountingInput(ambiguous=new_ambiguous, capacities=ci.capacities, at_least_one=ci.at_least_one)


def probability_of_response_outcome(
    ci: CountingInput,
    confirmed_owner_of: Mapping[Card, str],
    suspect: Card,
    weapon: Card,
    room: Card,
    responder_order: Sequence[str],
) -> dict:
    """Probability distribution over who (if anyone, in responder_order) would be
    first to show one of the three suggested cards, given the current possible-world
    distribution. Returns {"no_show": p, responder_id: p, ...} summing to 1.0.
    """
    trio = (suspect, weapon, room)

    # First responder in order confirmed to hold one of the trio: they are
    # certain to show *if reached*, but responders earlier in the order may
    # still show one of their own (ambiguous) cards first, so this only caps
    # the chain -- it doesn't make that responder's probability 1.0 outright.
    guaranteed_index = None
    for i, responder in enumerate(responder_order):
        if any(confirmed_owner_of.get(card) == responder for card in trio):
            guaranteed_index = i
            break

    total = count_worlds(ci)
    if total == 0:
        # Contradictory state; caller should not normally reach this.
        dist = {r: 0.0 for r in responder_order}
        dist["no_show"] = 0.0
        return dist

    def f(k: int) -> float:
        """P(first k responders all hold none of the trio)."""
        restricted = ci
        for responder in responder_order[:k]:
            restricted = _exclude_owner_for_cards(restricted, responder, trio)
        return count_worlds(restricted) / total

    last = len(responder_order) if guaranteed_index is None else guaranteed_index
    f_values = [f(k) for k in range(last + 1)]
    dist = {r: 0.0 for r in responder_order}
    for i in range(last):
        dist[responder_order[i]] = max(0.0, f_values[i] - f_values[i + 1])
    if guaranteed_index is None:
        dist["no_show"] = f_values[-1]
    else:
        # Confirmed cards aren't in ci.ambiguous, so the DP can't see them;
        # everything not shown by an earlier responder lands here.
        dist[responder_order[guaranteed_index]] = f_values[last]
        dist["no_show"] = 0.0
    return dist
