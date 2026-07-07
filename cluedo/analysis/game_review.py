"""Post-game review: a comprehensive, evidence-based summary of a finished
(or in-progress) game.

Everything here is built entirely from data the solver/analysis layers
already produce -- `history.build_replay_snapshots`, `cluedo.timeseries`,
`cluedo.advisor`, `cluedo.explain`, and the redundancy-detection logic
`cluedo.analysis.patterns` established. Nothing here is ever imported back
into `engine.py`/`probability.py`/`advisor.py`/`explain.py` (enforced by
tests/test_architecture_boundaries.py).

Hard rule this module exists to enforce, matching cluedo.analysis.endgame's
own rule: never invent a hypothetical response that wasn't actually given at
the table. Every "missed opportunity" or "better suggestion" claim is
grounded in either (a) the SAME real recorded (suggestion, response) pairs
replayed in a different order, or (b) the advisor's own probability-weighted
expected-information-gain math over real possible outcomes -- the same math
the live advisor already uses during play, just run retrospectively against
a historical snapshot. Nothing is ever asked "what if a different question
had been asked", because this app has no oracle access to hidden hands and
can't know what response that would have produced.

See docs/game_review_explained.md for the algorithm write-up.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from cluedo.advisor import rank_candidates
from cluedo.explain import render_narrative
from cluedo.game import GameState
from cluedo.models import ENVELOPE, Card, CardType, Suggestion, seat_id
from cluedo.timeseries import (
    envelope_probability_over_time,
    info_gained_per_turn,
    solver_progress_over_time,
    worlds_over_time,
)
from cluedo.history import build_replay_snapshots

# ---------------------------------------------------------------- data types


@dataclass(frozen=True)
class TimelineEvent:
    turn: int
    label: str
    description: str


@dataclass(frozen=True)
class SuggestionHighlight:
    turn: int
    player: str
    suspect: Card
    weapon: Card
    room: Card
    info_gain: float  # fraction of valid worlds eliminated, 0.0-1.0
    explanation: str


@dataclass(frozen=True)
class DeductionHighlight:
    turn: int
    card: Optional[Card]
    narrative: list[str]
    newly_confirmed_count: int


@dataclass(frozen=True)
class MissedOpportunity:
    kind: str  # "earlier_accusation" | "better_suggestion" | "low_information" | "redundant_suggestion"
    turn: int
    message: str


@dataclass(frozen=True)
class PerformanceMetrics:
    info_gain_per_turn: list[float]
    average_info_gain: float
    highest_info_gain: float
    lowest_info_gain: float
    redundant_suggestion_count: int
    unique_suggestion_count: int
    total_suggestion_count: int
    valid_worlds_per_turn: list[Optional[int]]
    envelope_certainty_progression: dict = field(default_factory=dict)  # CardType -> list[Optional[float]]


@dataclass(frozen=True)
class GameReview:
    is_solved: bool
    difficulty: str  # "Easy" | "Medium" | "Hard" | "Expert"
    difficulty_explanation: str
    overall_rating: Optional[str]  # letter grade, None until solved
    efficiency_pct: Optional[float]
    turns_played: int
    estimated_optimal_solve_turn: Optional[int]
    actual_solve_turn: Optional[int]
    turns_lost: Optional[int]
    time_played_seconds: Optional[float]
    average_time_per_turn_seconds: Optional[float]
    final_accuracy_pct: float
    key_turning_point: Optional[SuggestionHighlight]
    best_suggestion: Optional[SuggestionHighlight]
    largest_deduction: Optional[DeductionHighlight]
    missed_opportunities: list[MissedOpportunity]
    timeline: list[TimelineEvent]
    performance: PerformanceMetrics
    feedback: list[str]


# ------------------------------------------------------------------ tunables

# Letter-grade cutoffs against efficiency_pct (estimated_optimal_solve_turn /
# actual_solve_turn * 100, capped at 100). Ordered highest-first; the first
# threshold the score clears wins.
_GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (97.0, "A+"), (93.0, "A"), (90.0, "A-"),
    (87.0, "B+"), (83.0, "B"), (80.0, "B-"),
    (77.0, "C+"), (73.0, "C"), (70.0, "C-"),
    (60.0, "D"),
)

# A turn eliminating under this fraction of remaining valid worlds contributed
# little new information -- flagged as "low information" and considered when
# looking for a meaningfully better alternative.
_LOW_INFO_GAIN_THRESHOLD = 0.05

# "Better suggestion" is only flagged when the best available EXPECTED gain
# (from advisor.rank_candidates, real probability-weighted math) beat what was
# actually achieved by at least this many percentage points -- avoids noise
# from trivial differences that aren't actually actionable feedback.
_BETTER_SUGGESTION_MARGIN = 0.10

# Player-count baseline difficulty index into _DIFFICULTY_LEVELS. More seats
# at the table means more hidden hands and slower convergence even with
# identical suggestion quality, so it's the primary driver.
_DIFFICULTY_LEVELS = ("Easy", "Medium", "Hard", "Expert")
_DIFFICULTY_PLAYER_COUNT_BASE = {2: 0, 3: 0, 4: 1, 5: 1, 6: 2}
_DIFFICULTY_PLAYER_COUNT_DEFAULT = 2

# Difficulty escalates by one level if the game averaged more ambiguous cards
# per turn than this (more branching for the solver to work through at any
# given moment) or averaged less info gain per turn than this (progress was
# slow regardless of player count).
_DIFFICULTY_AMBIGUOUS_THRESHOLD = 9
_DIFFICULTY_LOW_GAIN_THRESHOLD = 0.12


# ----------------------------------------------------------------- top level


def compute_game_review(
    game_state: GameState, *, time_played_seconds: Optional[float] = None
) -> GameReview:
    """Builds a full GameReview from `game_state`'s history. Works on any
    game state, solved or not -- fields that only make sense once solved
    (actual_solve_turn, efficiency, letter grade, turns_lost) are None until
    then, but the rest (performance metrics, missed opportunities so far,
    final_accuracy so far) are always available, so this can also power an
    in-progress "how am I doing" view, not only a post-game report.

    Builds `build_replay_snapshots` exactly once and threads it through every
    sub-computation below, rather than each one rebuilding its own -- this is
    the single biggest cost in the whole function (O(turns^2) by design, same
    as every other full-game analysis in this codebase) and must not be paid
    twice.
    """
    snapshots = build_replay_snapshots(game_state)
    gains = info_gained_per_turn(snapshots)
    worlds = worlds_over_time(snapshots)
    confirmed_counts = solver_progress_over_time(snapshots)
    turns_played = len(game_state.history)
    solved = game_state.is_solved()

    actual_solve_turn = _first_solved_turn(snapshots)
    estimated_optimal_solve_turn = _estimate_optimal_solve_turn(game_state, snapshots)
    turns_lost = None
    if actual_solve_turn is not None and estimated_optimal_solve_turn is not None:
        turns_lost = max(0, actual_solve_turn - estimated_optimal_solve_turn)

    efficiency_pct = None
    overall_rating = None
    if actual_solve_turn is not None and estimated_optimal_solve_turn is not None:
        # actual_solve_turn == 0 means the game was already solved from the
        # initial hand alone, before any suggestion -- the fastest possible
        # outcome, so efficiency is trivially 100% rather than a division by
        # zero (explicit `is not None` checks throughout this function are
        # deliberate: 0 is a legitimate value for these turn-count fields,
        # not an absence of one).
        efficiency_pct = 100.0 if actual_solve_turn == 0 else min(
            100.0, 100.0 * estimated_optimal_solve_turn / actual_solve_turn
        )
        overall_rating = _letter_grade(efficiency_pct)

    final_accuracy_pct = 100.0 * len(game_state.engine.confirmed) / len(game_state.cards)

    difficulty, difficulty_explanation = _estimate_difficulty(game_state, snapshots, gains)

    key_turning_point = _key_turning_point(game_state, gains, actual_solve_turn)
    # "Best Suggestion" and "Key Turning Point" are the same underlying
    # largest-info-gain turn, framed differently (a narrative moment vs. a
    # suggestion's own numbers) -- see module docstring on never inventing a
    # second, different "best" without evidence for it.
    best_suggestion = key_turning_point
    largest_deduction = _largest_deduction(game_state, snapshots, confirmed_counts)

    redundant_count, unique_count, redundant_details = _scan_redundancy(game_state, snapshots)
    missed_opportunities = _find_missed_opportunities(
        gains, snapshots, redundant_details, actual_solve_turn, estimated_optimal_solve_turn
    )

    timeline = _build_timeline(
        game_state, snapshots, actual_solve_turn, estimated_optimal_solve_turn,
        largest_deduction, key_turning_point,
    )

    performance = PerformanceMetrics(
        info_gain_per_turn=gains,
        average_info_gain=statistics.fmean(gains) if gains else 0.0,
        highest_info_gain=max(gains) if gains else 0.0,
        lowest_info_gain=min(gains) if gains else 0.0,
        redundant_suggestion_count=redundant_count,
        unique_suggestion_count=unique_count,
        total_suggestion_count=turns_played,
        valid_worlds_per_turn=worlds,
        envelope_certainty_progression=_envelope_certainty_progression(game_state, snapshots, solved),
    )

    average_time_per_turn = (
        time_played_seconds / turns_played if (time_played_seconds is not None and turns_played) else None
    )

    feedback = _generate_feedback(
        game_state, snapshots, efficiency_pct, turns_lost, redundant_count, turns_played,
        performance.average_info_gain,
    )

    return GameReview(
        is_solved=solved,
        difficulty=difficulty,
        difficulty_explanation=difficulty_explanation,
        overall_rating=overall_rating,
        efficiency_pct=efficiency_pct,
        turns_played=turns_played,
        estimated_optimal_solve_turn=estimated_optimal_solve_turn,
        actual_solve_turn=actual_solve_turn,
        turns_lost=turns_lost,
        time_played_seconds=time_played_seconds,
        average_time_per_turn_seconds=average_time_per_turn,
        final_accuracy_pct=final_accuracy_pct,
        key_turning_point=key_turning_point,
        best_suggestion=best_suggestion,
        largest_deduction=largest_deduction,
        missed_opportunities=missed_opportunities,
        timeline=timeline,
        performance=performance,
        feedback=feedback,
    )


# ------------------------------------------------------------------ helpers


def _first_solved_turn(snapshots) -> Optional[int]:
    for i, snap in enumerate(snapshots):
        if snap.game_state.is_solved():
            return i
    return None


def _estimate_optimal_solve_turn(game_state: GameState, snapshots) -> Optional[int]:
    """Greedy heuristic, never inventing a hypothetical response: reorders
    the SAME real (suggestion, response) pairs by their own actual recorded
    marginal increase in confirmed-card count (descending, ties broken by
    original chronological order for determinism), replays that single
    reordering once, and reports the earliest prefix length at which the
    mystery would already be solved.

    Sorts by confirmed-card delta (`solver_progress_over_time`) rather than
    `info_gained_per_turn`'s exact-probability world count deliberately:
    exact world-counting is gated behind an ambiguous-card cap
    (probability.py's TooManyAmbiguousCardsError gate) and reports 0.0
    whenever that cap is exceeded -- which is the common case early in a
    real game, exactly when reordering matters most. Confirmed-card count has
    no such cap; it's always a real, cheap, always-available signal of "how
    much progress did this turn cause", so it's the more robust choice here
    even though it's coarser (it won't distinguish between two turns that
    both confirm zero cards but differ in how much they narrowed the
    remaining possibility space).

    This is safe to do: a reordering of an already-internally-consistent
    fact set can never introduce a contradiction (any subset of a
    satisfiable constraint set is itself satisfiable), so this never raises.

    Explicitly a heuristic, not a proof of the true minimum -- finding the
    true minimum would mean trying every permutation, which is
    combinatorially infeasible and unnecessary for an honest estimate. That's
    why every field/label built from this says "estimated".
    """
    if not game_state.history:
        # No suggestions to reorder -- either already solved from the initial
        # hand alone (0 turns needed, the fastest possible outcome), or
        # there's simply nothing yet to estimate from.
        return 0 if game_state.is_solved() else None
    confirmed_counts = solver_progress_over_time(snapshots)
    deltas = [confirmed_counts[i + 1] - confirmed_counts[i] for i in range(len(game_state.history))]
    order = sorted(range(len(game_state.history)), key=lambda i: (-deltas[i], i))
    reordered = [game_state.history[i] for i in order]
    reordered_state = GameState.from_history(
        game_state.config, game_state.players, game_state.user_seat, game_state._initial_hand, reordered
    )
    reordered_snapshots = build_replay_snapshots(reordered_state)
    return _first_solved_turn(reordered_snapshots)


def _letter_grade(efficiency_pct: float) -> str:
    for threshold, grade in _GRADE_THRESHOLDS:
        if efficiency_pct >= threshold:
            return grade
    return "F"


def _estimate_difficulty(game_state: GameState, snapshots, gains: list[float]) -> tuple[str, str]:
    player_count = len(game_state.players)
    score = _DIFFICULTY_PLAYER_COUNT_BASE.get(player_count, _DIFFICULTY_PLAYER_COUNT_DEFAULT)

    ambiguous_counts = [
        snap.game_state.last_solver_stats.ambiguous_card_count_last for snap in snapshots
    ]
    avg_ambiguous = statistics.fmean(ambiguous_counts) if ambiguous_counts else 0.0
    avg_gain = statistics.fmean(gains) if gains else 0.0

    reasons = [f"{player_count} players"]
    if avg_ambiguous > _DIFFICULTY_AMBIGUOUS_THRESHOLD:
        score += 1
        reasons.append(f"averaged {avg_ambiguous:.0f} ambiguous cards per turn")
    if gains and avg_gain < _DIFFICULTY_LOW_GAIN_THRESHOLD:
        score += 1
        reasons.append(f"averaged only {avg_gain * 100:.0f}% info gain per turn")

    score = min(score, len(_DIFFICULTY_LEVELS) - 1)
    level = _DIFFICULTY_LEVELS[score]
    explanation = ", ".join(reasons) + "."
    return level, explanation


def _key_turning_point(
    game_state: GameState, gains: list[float], actual_solve_turn: Optional[int]
) -> Optional[SuggestionHighlight]:
    if not gains:
        return None
    best_idx = max(range(len(gains)), key=lambda i: gains[i])
    suggestion = game_state.history[best_idx]
    turn_number = best_idx + 1
    player = game_state.players[suggestion.suggester_seat].name
    gain = gains[best_idx]
    if actual_solve_turn is not None and turn_number == actual_solve_turn:
        explanation = (
            f"{player}'s suggestion eliminated {gain * 100:.0f}% of all remaining valid worlds "
            "and made the final solution logically inevitable."
        )
    else:
        explanation = (
            f"{player}'s suggestion eliminated {gain * 100:.0f}% of all remaining valid worlds -- "
            "the single most informative move of the game."
        )
    return SuggestionHighlight(
        turn_number, player, suggestion.suspect, suggestion.weapon, suggestion.room, gain, explanation
    )


def _largest_deduction(game_state: GameState, snapshots, confirmed_counts: list[int]) -> Optional[DeductionHighlight]:
    if len(confirmed_counts) < 2:
        return None
    deltas = [confirmed_counts[i] - confirmed_counts[i - 1] for i in range(1, len(confirmed_counts))]
    if not deltas or max(deltas) <= 0:
        return None
    best_idx = max(range(len(deltas)), key=lambda i: deltas[i])
    turn_number = best_idx + 1
    before_state = snapshots[best_idx].game_state
    after_state = snapshots[best_idx + 1].game_state
    newly_confirmed = [
        c for c in game_state.cards
        if before_state.engine.owner_of(c) is None and after_state.engine.owner_of(c) is not None
    ]
    if not newly_confirmed:
        return None
    # The card with the richest derivation chain is the most "valuable" one
    # to show -- it's the one whose explanation actually demonstrates why
    # this turn mattered, rather than a trivially-forced card that happened
    # to be confirmed in the same batch.
    best_card = max(newly_confirmed, key=lambda c: len(after_state.explain_card_full_chain(c)))
    chain = after_state.explain_card_full_chain(best_card)
    narrative: list[str] = []
    for explanation in chain:
        narrative.extend(render_narrative(explanation))
    return DeductionHighlight(turn_number, best_card, narrative, deltas[best_idx])


def _scan_redundancy(game_state: GameState, snapshots) -> tuple[int, int, list[tuple[int, Suggestion]]]:
    """Single pass over the shared snapshots, mirroring
    cluedo.analysis.patterns._redundant_suggestion_count's exact definition
    (a suggestion is redundant if, at the time it was made, any of its three
    cards was already confirmed owned by someone other than the suggester)
    but applied across every player at once and without patterns.py's own
    per-call snapshot rebuild, since the snapshots here are already shared
    across this whole review."""
    redundant_count = 0
    unique_count = 0
    seen_triples: set[frozenset] = set()
    details: list[tuple[int, object]] = []

    for index, suggestion in enumerate(game_state.history):
        prior_state = snapshots[index].game_state
        own_owner_id = seat_id(suggestion.suggester_seat)
        is_redundant = False
        for card in suggestion.triple:
            owner = prior_state.engine.confirmed.get(card)
            if owner is not None and owner != own_owner_id:
                is_redundant = True
                break
        if is_redundant:
            redundant_count += 1
            details.append((index + 1, suggestion))

        triple_key = frozenset(suggestion.triple)
        if triple_key not in seen_triples:
            unique_count += 1
            seen_triples.add(triple_key)

    return redundant_count, unique_count, details


def _find_missed_opportunities(
    gains: list[float], snapshots, redundant_details, actual_solve_turn, estimated_optimal_solve_turn
) -> list[MissedOpportunity]:
    opportunities: list[MissedOpportunity] = []

    if (
        actual_solve_turn is not None
        and estimated_optimal_solve_turn is not None
        and actual_solve_turn > estimated_optimal_solve_turn
    ):
        opportunities.append(
            MissedOpportunity(
                "earlier_accusation", estimated_optimal_solve_turn,
                f"You could have safely accused on Turn {estimated_optimal_solve_turn}.",
            )
        )

    redundant_turns = {turn for turn, _ in redundant_details}
    for turn_number, suggestion in redundant_details:
        card_names = ", ".join(c.name for c in suggestion.triple)
        opportunities.append(
            MissedOpportunity(
                "redundant_suggestion", turn_number,
                f"Turn {turn_number}: this suggestion ({card_names}) re-asked about a card "
                "already known -- no new information.",
            )
        )

    for i, gain in enumerate(gains):
        turn_number = i + 1
        if turn_number in redundant_turns:
            continue  # already explained by the redundant-suggestion note above
        if turn_number == actual_solve_turn:
            continue  # nothing beats immediately solving, regardless of its narrow world-elimination %
        if gain < _LOW_INFO_GAIN_THRESHOLD:
            opportunities.append(
                MissedOpportunity(
                    "low_information", turn_number,
                    f"Turn {turn_number} eliminated only {gain * 100:.0f}% of remaining "
                    "possibilities -- a low-information suggestion.",
                )
            )

    # "Better suggestions": retrospectively compare the ACTUAL gain to the
    # best available EXPECTED gain at that point, using advisor.py's own
    # probability-weighted math over real possible outcomes. Never a
    # fabricated number -- rank_candidates' expected_info_gain is exact
    # whenever it isn't None (advisor.py gates that itself).
    for i, gain in enumerate(gains):
        turn_number = i + 1
        if turn_number == actual_solve_turn:
            continue  # nothing beats immediately solving, regardless of its narrow world-elimination %
        prior_state = snapshots[i].game_state
        if prior_state.is_solved():
            continue
        candidates = rank_candidates(prior_state, top_k=1)
        if not candidates or candidates[0].expected_info_gain is None:
            continue
        best_expected = candidates[0].expected_info_gain
        if best_expected - gain > _BETTER_SUGGESTION_MARGIN:
            extra_pct = (best_expected - gain) * 100
            opportunities.append(
                MissedOpportunity(
                    "better_suggestion", turn_number,
                    f"Optimal suggestion on Turn {turn_number} would have reduced the search "
                    f"space by an additional {extra_pct:.0f}%.",
                )
            )

    opportunities.sort(key=lambda o: o.turn)
    return opportunities


def _build_timeline(
    game_state: GameState, snapshots, actual_solve_turn, estimated_optimal_solve_turn,
    largest_deduction, key_turning_point,
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []

    for card_type, label in (
        (CardType.SUSPECT, "Suspect"), (CardType.WEAPON, "Weapon"), (CardType.ROOM, "Room")
    ):
        category_cards = [c for c in game_state.cards if c.type == card_type]
        for i in range(1, len(snapshots)):
            now_confirmed = any(snapshots[i].game_state.engine.owner_of(c) == ENVELOPE for c in category_cards)
            was_confirmed = any(
                snapshots[i - 1].game_state.engine.owner_of(c) == ENVELOPE for c in category_cards
            )
            if now_confirmed and not was_confirmed:
                confirmed_card = next(
                    c for c in category_cards if snapshots[i].game_state.engine.owner_of(c) == ENVELOPE
                )
                events.append(
                    TimelineEvent(i, f"{label} identified", f"{confirmed_card.name} confirmed as the envelope {label.lower()}.")
                )
                break

    if largest_deduction is not None:
        events.append(
            TimelineEvent(largest_deduction.turn, "Largest deduction", "The most significant single deduction of the game.")
        )
    if key_turning_point is not None:
        events.append(TimelineEvent(key_turning_point.turn, "Key turning point", key_turning_point.explanation))
    if estimated_optimal_solve_turn is not None:
        events.append(
            TimelineEvent(
                estimated_optimal_solve_turn, "Optimal accusation became available",
                "The earliest point at which the mystery was logically solvable.",
            )
        )
    if actual_solve_turn is not None:
        events.append(TimelineEvent(actual_solve_turn, "Game solved", "The mystery was fully confirmed."))

    events.sort(key=lambda e: e.turn)
    return events


def _envelope_certainty_progression(game_state: GameState, snapshots, solved: bool) -> dict:
    if not solved:
        return {}
    suspect, weapon, room = game_state.solution()
    return {
        CardType.SUSPECT: envelope_probability_over_time(snapshots, suspect),
        CardType.WEAPON: envelope_probability_over_time(snapshots, weapon),
        CardType.ROOM: envelope_probability_over_time(snapshots, room),
    }


def _generate_feedback(
    game_state: GameState, snapshots, efficiency_pct, turns_lost, redundant_count, turns_played,
    average_info_gain: float,
) -> list[str]:
    feedback: list[str] = []

    if efficiency_pct is not None:
        if efficiency_pct >= 90.0:
            feedback.append("Excellent information gathering -- close to optimal play.")
        elif turns_lost:
            feedback.append(f"You solved {turns_lost} turn(s) later than the estimated optimal.")

    if turns_played and redundant_count / turns_played > 0.2:
        feedback.append("You frequently repeated suggestions that had already been answered.")

    if average_info_gain > 0.3:
        feedback.append("Your suggestions were highly efficient at narrowing down the possibilities.")

    category_confirm_turn: dict[CardType, int] = {}
    for card_type in (CardType.SUSPECT, CardType.WEAPON, CardType.ROOM):
        category_cards = [c for c in game_state.cards if c.type == card_type]
        for i, snap in enumerate(snapshots):
            if any(snap.game_state.engine.owner_of(c) == ENVELOPE for c in category_cards):
                category_confirm_turn[card_type] = i
                break

    if category_confirm_turn:
        fastest = min(category_confirm_turn, key=lambda ct: category_confirm_turn[ct])
        feedback.append(
            f"Your {fastest.value} deductions were excellent -- identified by turn {category_confirm_turn[fastest]}."
        )

    return feedback
