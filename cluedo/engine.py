"""The core deduction engine: constraint propagation + bounded exhaustive
confirmation over whatever small set of cards propagation alone can't resolve.

Recomputes from scratch on every call to recompute() rather than patching state
incrementally -- deliberate, since the problem is tiny (21 cards, <=6 owners)
and this makes the engine far easier to reason about and test than trying to
keep incremental invalidation correct under undo/edit/replay.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from cluedo.explain import (
    Explanation,
    ExplanationRegistry,
    Fact,
    FactKind,
    FactSource,
)
from cluedo.models import ENVELOPE, Card, CardType, Player
from cluedo.probability import (
    AmbiguousCard,
    CountingInput,
    capacity_key,
    count_worlds,
    has_any_valid_world,
)


class ContradictionError(Exception):
    def __init__(self, kind: str, message: str, detail: Optional[dict] = None):
        self.kind = kind
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


@dataclass
class SolverStats:
    propagation_iterations: int = 0
    backtracking_nodes_visited: int = 0
    valid_worlds_last_counted: Optional[int] = None
    wall_clock_seconds: float = 0.0
    ambiguous_card_count_last: int = 0
    backtracking_skipped: bool = False


@dataclass
class _RawFact:
    kind: str  # "owned" | "not_owned" | "at_least_one"
    card: Optional[Card]
    owner: str
    cards: Optional[tuple[Card, Card, Card]]
    source: FactSource


class ConstraintEngine:
    def __init__(self, cards: list[Card], players: list[Player], *, max_confirmation_ambiguous: int = 16):
        self.cards = list(cards)
        self.players = list(players)
        self.owners = [p.owner_id for p in players] + [ENVELOPE]
        self.hand_size = {p.owner_id: p.hand_size for p in players}
        self._max_confirmation_ambiguous = max_confirmation_ambiguous

        self._facts: list[_RawFact] = []

        self.possible: dict[Card, set] = {}
        self.confirmed: dict[Card, str] = {}
        self.explanations = ExplanationRegistry()
        self.last_stats = SolverStats()

        self.recompute()

    # ------------------------------------------------------------------ facts

    def add_owned(self, card: Card, owner: str, source: Optional[FactSource] = None) -> None:
        self._facts.append(_RawFact("owned", card, owner, None, source or FactSource("derived")))

    def add_not_owned(self, card: Card, owner: str, source: Optional[FactSource] = None) -> None:
        self._facts.append(_RawFact("not_owned", card, owner, None, source or FactSource("derived")))

    def add_at_least_one(
        self, owner: str, cards: tuple[Card, Card, Card], source: Optional[FactSource] = None
    ) -> None:
        self._facts.append(_RawFact("at_least_one", None, owner, cards, source or FactSource("derived")))

    # -------------------------------------------------------------- queries

    def owner_of(self, card: Card) -> Optional[str]:
        return self.confirmed.get(card)

    def possible_owners(self, card: Card) -> set:
        return set(self.possible.get(card, set()))

    def is_solved(self) -> bool:
        return self.solution() is not None

    def solution(self):
        by_type = {}
        for card, owner in self.confirmed.items():
            if owner == ENVELOPE:
                by_type[card.type] = card
        if CardType.SUSPECT in by_type and CardType.WEAPON in by_type and CardType.ROOM in by_type:
            return (by_type[CardType.SUSPECT], by_type[CardType.WEAPON], by_type[CardType.ROOM])
        return None

    def counting_input(self) -> CountingInput:
        ambiguous_cards = [c for c in self.cards if c not in self.confirmed]
        ambiguous_cards.sort(key=lambda c: len(self.possible[c]))
        ambiguous = tuple(
            AmbiguousCard(c, tuple(sorted(self.possible[c]))) for c in ambiguous_cards
        )

        capacities: dict[str, int] = {}
        for p in self.players:
            confirmed_count = sum(1 for owner in self.confirmed.values() if owner == p.owner_id)
            capacities[p.owner_id] = p.hand_size - confirmed_count
        for ct in CardType:
            confirmed_count = sum(
                1 for card, owner in self.confirmed.items() if owner == ENVELOPE and card.type == ct
            )
            capacities[capacity_key(ENVELOPE, ct)] = 1 - confirmed_count

        at_least_one = tuple(
            (f.owner, frozenset(f.cards))
            for f in self._facts
            if f.kind == "at_least_one" and not self._at_least_one_satisfied(f.owner, f.cards)
        )

        return CountingInput(ambiguous=ambiguous, capacities=capacities, at_least_one=at_least_one)

    def _at_least_one_satisfied(self, owner: str, cards: tuple[Card, Card, Card]) -> bool:
        return any(self.confirmed.get(c) == owner for c in cards)

    # ---------------------------------------------------------------- solve

    def recompute(self) -> SolverStats:
        start = time.perf_counter()
        stats = SolverStats()

        self.possible = {c: set(self.owners) for c in self.cards}
        self.confirmed = {}
        self.explanations.clear()

        card_facts: dict[Card, list[Fact]] = {c: [] for c in self.cards}

        for f in self._facts:
            if f.kind == "owned":
                self.possible[f.card] &= {f.owner}
                card_facts[f.card].append(
                    Fact(FactKind.OWNED, f.card, f.owner, f.source, f"{f.owner} owns {f.card.name}.")
                )
            elif f.kind == "not_owned":
                self.possible[f.card].discard(f.owner)
                card_facts[f.card].append(
                    Fact(FactKind.NOT_OWNED, f.card, f.owner, f.source, f"{f.owner} could not own {f.card.name}.")
                )

        changed = True
        iterations = 0
        while changed:
            changed = False
            iterations += 1

            for card in self.cards:
                if card in self.confirmed:
                    continue
                if len(self.possible[card]) == 1:
                    owner = next(iter(self.possible[card]))
                    facts = card_facts[card]
                    if any(f.kind == FactKind.AT_LEAST_ONE for f in facts):
                        rule = FactKind.TWO_OF_THREE
                    elif any(f.kind == FactKind.HAND_FULL for f in facts):
                        rule = FactKind.HAND_FULL
                    else:
                        rule = FactKind.NOT_OWNED
                    self._confirm(card, owner, rule, facts, "chain of eliminations")
                    changed = True

            if self._apply_capacity_groups(card_facts):
                changed = True

            if self._resolve_two_of_three(card_facts):
                changed = True

        stats.propagation_iterations = iterations

        ci = self.counting_input()
        stats.ambiguous_card_count_last = len(ci.ambiguous)
        if ci.ambiguous:
            if len(ci.ambiguous) <= self._max_confirmation_ambiguous:
                if self._confirm_via_world_search(ci):
                    # a cascade may have unlocked more cheap propagation
                    return self.recompute()
            else:
                stats.backtracking_skipped = True

        self._check_contradictions()

        stats.wall_clock_seconds = time.perf_counter() - start
        self.last_stats = stats
        return stats

    def _confirm(self, card: Card, owner: str, rule: FactKind, premises: list[Fact], reason_label: str) -> None:
        if card in self.confirmed:
            return
        self.confirmed[card] = owner
        conclusion = Fact(FactKind.OWNED, card, owner, FactSource("derived"), f"{owner} owns {card.name}.")
        narrative = [p.label for p in premises]
        narrative.append(f"Therefore {card.name} must belong to {owner}.")
        self.explanations.record(Explanation(conclusion, tuple(premises), rule, tuple(narrative)))

    def _capacity_groups(self):
        """Yields (owner_value, group_members, capacity) for both player-hand
        groups (capacity spans all categories) and envelope-per-category groups."""
        for p in self.players:
            confirmed_count = sum(1 for owner in self.confirmed.values() if owner == p.owner_id)
            capacity = p.hand_size - confirmed_count
            members = [c for c in self.cards if c not in self.confirmed and p.owner_id in self.possible[c]]
            yield p.owner_id, members, capacity
        for ct in CardType:
            confirmed_count = sum(
                1 for card, owner in self.confirmed.items() if owner == ENVELOPE and card.type == ct
            )
            capacity = 1 - confirmed_count
            members = [
                c
                for c in self.cards
                if c.type == ct and c not in self.confirmed and ENVELOPE in self.possible[c]
            ]
            yield ENVELOPE, members, capacity

    def _apply_capacity_groups(self, card_facts: dict[Card, list[Fact]]) -> bool:
        changed = False
        for owner, members, capacity in self._capacity_groups():
            if capacity <= 0 and members:
                for card in members:
                    if owner in self.possible[card]:
                        self.possible[card].discard(owner)
                        card_facts[card].append(
                            Fact(
                                FactKind.HAND_FULL,
                                card,
                                owner,
                                FactSource("derived"),
                                f"{owner} already has all {self.hand_size.get(owner, 1)} of their cards accounted for."
                                if owner != ENVELOPE
                                else f"The envelope's slot for this category is already filled.",
                            )
                        )
                        if len(self.possible[card]) == 1:
                            changed = True
            elif capacity > 0 and 0 < len(members) == capacity:
                for card in members:
                    self.possible[card] &= {owner}
                    card_facts[card].append(
                        Fact(
                            FactKind.HAND_FULL,
                            card,
                            owner,
                            FactSource("derived"),
                            f"Exactly {capacity} card(s) remain for {owner}'s remaining slot(s), "
                            f"and {card.name} is one of the only {capacity} candidate(s) left.",
                        )
                    )
                changed = True
        return changed

    def _resolve_two_of_three(self, card_facts: dict[Card, list[Fact]]) -> bool:
        changed = False
        for f in self._facts:
            if f.kind != "at_least_one":
                continue
            owner, trio = f.owner, f.cards
            if self._at_least_one_satisfied(owner, trio):
                continue
            excluded = [c for c in trio if owner not in self.possible[c] or self.confirmed.get(c) not in (None, owner)]
            remaining = [c for c in trio if c not in excluded]
            if len(excluded) == 2 and len(remaining) == 1:
                target = remaining[0]
                if owner in self.possible[target] and self.confirmed.get(target) is None:
                    self.possible[target] &= {owner}
                    premises = list(card_facts.get(target, []))
                    others = ", ".join(c.name for c in trio)
                    premises.append(
                        Fact(
                            FactKind.AT_LEAST_ONE,
                            None,
                            owner,
                            f.source,
                            f"{owner} had to own one of: {others}",
                        )
                    )
                    for c in excluded:
                        premises.append(
                            Fact(FactKind.NOT_OWNED, c, owner, FactSource("derived"), f"{c.name} was impossible.")
                        )
                    card_facts[target] = premises
                    if len(self.possible[target]) == 1:
                        changed = True
        return changed

    def _confirm_via_world_search(self, ci: CountingInput) -> bool:
        total = count_worlds(ci)
        self.last_stats.valid_worlds_last_counted = total
        if total == 0:
            return False  # a contradiction check will report this properly

        any_confirmed = False
        for ac in ci.ambiguous:
            if len(ac.domain) <= 1:
                continue
            nonzero_owners = []
            for owner in ac.domain:
                pinned = CountingInput(
                    ambiguous=tuple(
                        AmbiguousCard(other.card, (owner,)) if other.card == ac.card else other
                        for other in ci.ambiguous
                    ),
                    capacities=ci.capacities,
                    at_least_one=ci.at_least_one,
                )
                if count_worlds(pinned) > 0:
                    nonzero_owners.append(owner)
                if len(nonzero_owners) > 1:
                    break
            if len(nonzero_owners) == 1:
                owner = nonzero_owners[0]
                self._confirm(
                    ac.card,
                    owner,
                    FactKind.WORLD_ARGUMENT,
                    [
                        Fact(
                            FactKind.WORLD_ARGUMENT,
                            ac.card,
                            owner,
                            FactSource("derived"),
                            f"In every remaining valid arrangement consistent with all known facts, "
                            f"{ac.card.name} belongs to {owner}.",
                        )
                    ],
                    "world argument",
                )
                any_confirmed = True
        return any_confirmed

    def _check_contradictions(self) -> None:
        for card in self.cards:
            if card not in self.confirmed and len(self.possible[card]) == 0:
                raise ContradictionError(
                    "domain_empty",
                    f"No valid owner remains for {card.name} -- every possible owner has been ruled out. "
                    "This usually means two logged facts conflict.",
                    {"card": card},
                )

        for p in self.players:
            count = sum(1 for owner in self.confirmed.values() if owner == p.owner_id)
            if count > p.hand_size:
                raise ContradictionError(
                    "hand_size_exceeded",
                    f"{p.name} would have {count} cards but should only have {p.hand_size}.",
                    {"player": p, "count": count, "hand_size": p.hand_size},
                )

        for ct in CardType:
            cards_in_envelope = [
                c for c, owner in self.confirmed.items() if owner == ENVELOPE and c.type == ct
            ]
            if len(cards_in_envelope) > 1:
                raise ContradictionError(
                    "envelope_category_exceeded",
                    f"Two cards are forced into the envelope for {ct.value}: "
                    f"{', '.join(c.name for c in cards_in_envelope)}.",
                    {"category": ct, "cards": cards_in_envelope},
                )

        ci = self.counting_input()
        if ci.ambiguous and len(ci.ambiguous) <= self._max_confirmation_ambiguous:
            if not has_any_valid_world(ci):
                raise ContradictionError(
                    "zero_valid_worlds",
                    "No valid arrangement of cards satisfies all known facts -- "
                    "please review recent entries for an error.",
                    {},
                )
