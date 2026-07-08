"""Human-readable derivation traces for every confirmed fact.

Each time engine.py's propagation rules confirm a card, they record an
Explanation citing the specific prior facts that forced the conclusion, so a
player can click any confirmed cell and see *why* it's true rather than just
being told the answer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from cluedo.models import Card


class FactKind(Enum):
    OWNED = "owned"
    NOT_OWNED = "not_owned"
    AT_LEAST_ONE = "at_least_one"
    HAND_FULL = "hand_full"
    ENVELOPE_CATEGORY_FULL = "envelope_category_full"
    TWO_OF_THREE = "two_of_three"
    WORLD_ARGUMENT = "world_argument"
    INITIAL_HAND = "initial_hand"


@dataclass(frozen=True)
class FactSource:
    origin: str  # "initial_hand" | "suggestion" | "derived"
    suggestion_id: Optional[str] = None


@dataclass(frozen=True)
class Fact:
    kind: FactKind
    card: Optional[Card]
    owner: Optional[str]
    source: FactSource
    label: str  # pre-rendered one-line description of this fact, e.g. "Lisa could not own Knife."


@dataclass(frozen=True)
class Explanation:
    conclusion: Fact
    premises: tuple[Fact, ...]
    rule: FactKind
    narrative: tuple[str, ...]


class ExplanationRegistry:
    """Holds explanations for the current recompute() cycle. Rebuilt from scratch
    every recompute(), consistent with the engine's overall recompute-from-scratch
    philosophy -- explanations always reflect the current full fact set."""

    def __init__(self) -> None:
        self._by_card: dict[Card, Explanation] = {}

    def clear(self) -> None:
        self._by_card.clear()

    def record(self, explanation: Explanation) -> None:
        # Prefer a shorter propagation-rule explanation over a WORLD_ARGUMENT one
        # if both would confirm the same card during this cycle.
        existing = self._by_card.get(explanation.conclusion.card)
        if existing is not None and existing.rule != FactKind.WORLD_ARGUMENT:
            return
        self._by_card[explanation.conclusion.card] = explanation

    def explanation_for(self, card: Card) -> Optional[Explanation]:
        return self._by_card.get(card)


def full_derivation_chain(explanation: Explanation, registry: ExplanationRegistry) -> list[Explanation]:
    """Depth-first unroll: if a premise is itself a derived fact with its own
    Explanation, include that recursively (avoiding infinite loops on cycles,
    which shouldn't occur but are guarded against defensively)."""
    seen: set[Card] = set()
    chain: list[Explanation] = []

    def walk(exp: Explanation) -> None:
        if exp.conclusion.card in seen:
            return
        seen.add(exp.conclusion.card)
        chain.append(exp)
        for premise in exp.premises:
            if premise.card is not None:
                sub = registry.explanation_for(premise.card)
                if sub is not None and sub is not exp:
                    walk(sub)

    walk(explanation)
    return chain


def render_narrative(explanation: Explanation) -> list[str]:
    return list(explanation.narrative)


@dataclass(frozen=True)
class ExplanationNode:
    """A real nested restructuring of the same DFS walk `full_derivation_chain`
    already performs -- that function flattens premise/sub-explanation links
    into one list in visitation order; this preserves the actual parent/child
    structure (a premise fact's own `Explanation`, if it has one, becomes a
    child node) for callers that need to render/expand it as a tree (the
    Deduction Graph) rather than just a linear chain."""

    explanation: Explanation
    children: tuple["ExplanationNode", ...]


def build_explanation_tree(explanation: Explanation, registry: ExplanationRegistry) -> ExplanationNode:
    """Same cycle-guard as `full_derivation_chain` (a card's explanation is
    expanded into a child node at most once per path), but returns the
    nested tree instead of a flattened list."""
    seen: set[Card] = set()

    def walk(exp: Explanation) -> ExplanationNode:
        seen.add(exp.conclusion.card)
        children = []
        for premise in exp.premises:
            if premise.card is not None and premise.card not in seen:
                sub = registry.explanation_for(premise.card)
                if sub is not None:
                    children.append(walk(sub))
        return ExplanationNode(exp, tuple(children))

    return walk(explanation)
