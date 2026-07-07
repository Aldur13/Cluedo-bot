"""Rule-based behavioral pattern extraction for a single player's suggestion
history, built entirely from `GameState.history` + `history.build_replay_snapshots`.

Read-only consumer of `cluedo.game`/`cluedo.models`/`cluedo.history`: nothing
here is ever imported back into `engine.py`/`probability.py`/`advisor.py`/
`explain.py` (enforced by tests/test_architecture_boundaries.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cluedo.game import GameState
from cluedo.history import build_replay_snapshots
from cluedo.models import Card, CardType, Suggestion, seat_id


@dataclass(frozen=True)
class PlayerPatternStats:
    seat: int
    total_suggestions: int
    card_frequency: dict[Card, int]
    pair_frequency: dict[frozenset, int]
    triple_frequency: dict[frozenset, int]
    never_suggested: frozenset
    always_suggested: frozenset
    category_lock_streaks: dict[CardType, int]
    favorite_room: Optional[Card]
    favorite_suspect: Optional[Card]
    favorite_weapon: Optional[Card]
    redundant_suggestion_count: int


def _category_map(suggestion: Suggestion) -> dict[CardType, Card]:
    return {
        CardType.SUSPECT: suggestion.suspect,
        CardType.WEAPON: suggestion.weapon,
        CardType.ROOM: suggestion.room,
    }


def _category_lock_streaks(suggestions: list[Suggestion]) -> dict[CardType, int]:
    """Longest run of consecutive suggestions (in chronological order, for
    this player only) where one category's card stays fixed while *both*
    other categories change. A single suggestion trivially "holds every
    category fixed" against nothing, so it counts as a streak of 1; the
    streak only grows past 1 when the fixed card repeats AND the other two
    categories actually differ from the immediately preceding suggestion --
    an exact repeat of the whole triple is not "hunting" a category, it's
    just a repeat, so it resets the run instead of extending it.
    """
    streaks: dict[CardType, int] = {}
    for cat in CardType:
        best = 0
        current = 0
        prev: Optional[dict[CardType, Card]] = None
        for suggestion in suggestions:
            triple = _category_map(suggestion)
            if prev is None:
                current = 1
            else:
                fixed_matches = triple[cat] == prev[cat]
                others_varied = all(triple[c] != prev[c] for c in CardType if c != cat)
                current = current + 1 if (fixed_matches and others_varied) else 1
            best = max(best, current)
            prev = triple
        streaks[cat] = best
    return streaks


def _favorite(card_frequency: dict[Card, int], card_type: CardType) -> Optional[Card]:
    candidates = [(card, freq) for card, freq in card_frequency.items() if card.type == card_type]
    if not candidates:
        return None
    # max() returns the first maximum in iteration order on ties, and
    # card_frequency preserves first-suggested-first insertion order, so
    # ties are broken deterministically by "whichever this player suggested
    # first" rather than arbitrarily.
    return max(candidates, key=lambda pair: pair[1])[0]


def find_redundant_suggestions(game_state: GameState, seat: int) -> list[int]:
    """Turn indices (into `game_state.history`) of suggestions by `seat`
    where, AT THE TIME the suggestion was made (i.e. using the replay
    snapshot for the history *prefix before* that suggestion, never the
    live/final state), at least one of the three suggested cards was
    already confirmed owned by someone other than the suggester. This is
    the module's one hard correctness requirement: using the final
    game_state here instead would make suggestions look redundant only
    because of information learned afterward.
    """
    snapshots = build_replay_snapshots(game_state)
    own_owner_id = seat_id(seat)
    redundant: list[int] = []
    for index, suggestion in enumerate(game_state.history):
        if suggestion.suggester_seat != seat:
            continue
        # snapshots[index] reflects history[:index] -- i.e. everything known
        # strictly *before* this suggestion was made.
        prior_state = snapshots[index].game_state
        for card in suggestion.triple:
            owner = prior_state.engine.confirmed.get(card)
            if owner is not None and owner != own_owner_id:
                redundant.append(index)
                break
    return redundant


def _redundant_suggestion_count(game_state: GameState, seat: int) -> int:
    return len(find_redundant_suggestions(game_state, seat))


def analyze_player_patterns(game_state: GameState, seat: int) -> PlayerPatternStats:
    suggestions = [s for s in game_state.history if s.suggester_seat == seat]
    total = len(suggestions)

    card_frequency: dict[Card, int] = {}
    pair_frequency: dict[frozenset, int] = {}
    triple_frequency: dict[frozenset, int] = {}

    for suggestion in suggestions:
        triple = suggestion.triple
        for card in triple:
            card_frequency[card] = card_frequency.get(card, 0) + 1
        for a, b in ((triple[0], triple[1]), (triple[0], triple[2]), (triple[1], triple[2])):
            pair = frozenset((a, b))
            pair_frequency[pair] = pair_frequency.get(pair, 0) + 1
        triple_key = frozenset(triple)
        triple_frequency[triple_key] = triple_frequency.get(triple_key, 0) + 1

    never_suggested = frozenset(card for card in game_state.cards if card not in card_frequency)

    if total > 0:
        always_suggested = frozenset(suggestions[0].triple)
        for suggestion in suggestions[1:]:
            always_suggested &= frozenset(suggestion.triple)
    else:
        always_suggested = frozenset()

    category_lock_streaks = _category_lock_streaks(suggestions)

    return PlayerPatternStats(
        seat=seat,
        total_suggestions=total,
        card_frequency=card_frequency,
        pair_frequency=pair_frequency,
        triple_frequency=triple_frequency,
        never_suggested=never_suggested,
        always_suggested=always_suggested,
        category_lock_streaks=category_lock_streaks,
        favorite_room=_favorite(card_frequency, CardType.ROOM),
        favorite_suspect=_favorite(card_frequency, CardType.SUSPECT),
        favorite_weapon=_favorite(card_frequency, CardType.WEAPON),
        redundant_suggestion_count=_redundant_suggestion_count(game_state, seat),
    )


def analyze_all_players(game_state: GameState) -> dict[int, PlayerPatternStats]:
    return {player.seat_index: analyze_player_patterns(game_state, player.seat_index) for player in game_state.players}
