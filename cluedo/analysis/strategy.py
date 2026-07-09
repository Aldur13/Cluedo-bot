"""Rule-based strategy classification on top of `patterns.PlayerPatternStats`.

Every rule below is a plain, explainable threshold over `PlayerPatternStats`
fields -- never a black-box score. `classify_strategy` always returns the
actual computed values alongside the label so a caller (or a test) can see
exactly why a given classification fired.
"""
from __future__ import annotations

import statistics
from enum import Enum
from typing import Optional

from cluedo.analysis.patterns import PlayerPatternStats
from cluedo.models import CardType


class PlayerStrategy(Enum):
    ROOM_HUNTER = "room_hunter"
    WEAPON_HUNTER = "weapon_hunter"
    SUSPECT_HUNTER = "suspect_hunter"
    BALANCED = "balanced"
    AGGRESSIVE_ELIMINATOR = "aggressive_eliminator"
    RANDOM_EXPLORER = "random_explorer"
    BLUFFER = "bluffer"
    INFORMATION_MAXIMIZER = "information_maximizer"


# With fewer than this many logged suggestions there simply isn't enough
# evidence to tell "hunting a category" apart from coincidence -- e.g. 2
# suggestions in a row can share a room purely by chance out of a handful of
# rooms. Below this floor we return BALANCED with an explicit
# "insufficient_data" reason instead of overfitting a label to noise.
MIN_SUGGESTIONS_FOR_CLASSIFICATION = 3

# A player who reveals, at suggestion time, that they're re-asking about a
# card already confirmed to belong to someone else is either sloppy or
# deliberately masking their real target behind a "safe" already-answered
# question. Requiring roughly a third or more of their suggestions to show
# this (rather than "any at all") avoids labeling a single early-game
# coincidence -- with few cards eliminated yet, occasional accidental
# redundancy is normal and shouldn't itself read as bluffing.
BLUFF_RATIO_THRESHOLD = 1.0 / 3.0

# A "hunter" needs their best category's lock-streak to cover at least half
# of all their suggestions -- i.e. more suggestions than not were spent
# holding that category fixed while probing the other two. The margin below
# additionally requires the leading category to beat the runner-up by at
# least one full extra suggestion, so a near-tie between two categories
# (e.g. streaks of 3 vs 3) falls through to a different label rather than
# arbitrarily picking whichever CardType enum member sorts first.
LOCK_RATIO_THRESHOLD = 0.5
LOCK_DOMINANCE_MARGIN = 1

# "Aggressive eliminator": has suggested at least this fraction of every
# distinct card in the deck at least once. Trying almost everything is a
# breadth-first elimination strategy, distinct from the narrow, repeated
# focus of a category hunter.
AGGRESSIVE_COVERAGE_THRESHOLD = 0.85

# "Random explorer": no category shows a meaningfully dominant lock streak
# (best streak covers less than the hunter threshold above) AND the spread
# of how often individual cards are suggested is low -- measured as the
# coefficient of variation (population stdev / mean) of card_frequency
# values. A low CV means cards are suggested roughly equally often, i.e. no
# discernible favorites, which is the signature of an unstructured player
# rather than one following a hidden pattern our other rules just missed.
UNIFORMITY_CV_THRESHOLD = 0.25

# "Information maximizer": never re-suggests the same two-card pairing.
# Repeating a pair burns a suggestion re-confirming something already
# probed; a player who always introduces at least one fresh pairing is
# systematically maximizing new information per suggestion.
MAX_PAIR_REPEAT_FOR_INFO_MAXIMIZER = 1

_CATEGORY_TO_STRATEGY = {
    CardType.ROOM: PlayerStrategy.ROOM_HUNTER,
    CardType.WEAPON: PlayerStrategy.WEAPON_HUNTER,
    CardType.SUSPECT: PlayerStrategy.SUSPECT_HUNTER,
}


def _coefficient_of_variation(values: list[int]) -> Optional[float]:
    if not values:
        return None
    mean = statistics.fmean(values)
    if mean == 0:
        return None
    if len(values) == 1:
        return 0.0
    return statistics.pstdev(values) / mean


def classify_strategy(stats: PlayerPatternStats) -> tuple[PlayerStrategy, dict]:
    total = stats.total_suggestions

    if total < MIN_SUGGESTIONS_FOR_CLASSIFICATION:
        return PlayerStrategy.BALANCED, {
            "reason": "insufficient_data",
            "total_suggestions": total,
            "min_required": MIN_SUGGESTIONS_FOR_CLASSIFICATION,
        }

    # 1. Bluffer -- checked first because it's the strongest, most specific
    # behavioral signal (it directly observes a player asking a question
    # they should already know the answer to).
    redundant_ratio = stats.redundant_suggestion_count / total
    if redundant_ratio >= BLUFF_RATIO_THRESHOLD:
        return PlayerStrategy.BLUFFER, {
            "redundant_ratio": redundant_ratio,
            "threshold": BLUFF_RATIO_THRESHOLD,
            "redundant_suggestion_count": stats.redundant_suggestion_count,
            "total_suggestions": total,
        }

    # 2. Category hunters -- whichever category has the longest lock streak,
    # provided it clearly dominates both the player's own suggestion count
    # and the runner-up category.
    streaks = stats.category_lock_streaks
    ranked = sorted(streaks.items(), key=lambda item: item[1], reverse=True)
    best_category, best_streak = ranked[0]
    runner_up_streak = ranked[1][1] if len(ranked) > 1 else 0
    best_ratio = best_streak / total
    if best_ratio >= LOCK_RATIO_THRESHOLD and (best_streak - runner_up_streak) >= LOCK_DOMINANCE_MARGIN:
        return _CATEGORY_TO_STRATEGY[best_category], {
            "category": best_category.value,
            "lock_streak": best_streak,
            "lock_ratio": best_ratio,
            "threshold": LOCK_RATIO_THRESHOLD,
            "runner_up_streak": runner_up_streak,
            "dominance_margin": LOCK_DOMINANCE_MARGIN,
        }

    # 3. Aggressive eliminator -- has tried almost every card in the deck.
    deck_size = len(stats.card_frequency) + len(stats.never_suggested)
    coverage = (len(stats.card_frequency) / deck_size) if deck_size else 0.0
    if coverage >= AGGRESSIVE_COVERAGE_THRESHOLD:
        return PlayerStrategy.AGGRESSIVE_ELIMINATOR, {
            "coverage": coverage,
            "threshold": AGGRESSIVE_COVERAGE_THRESHOLD,
            "distinct_cards_suggested": len(stats.card_frequency),
            "deck_size": deck_size,
        }

    # 4. Random explorer -- no category dominates (best_ratio stayed below
    # the hunter threshold above) and card choice is roughly uniform. CV must
    # be computed over the *full deck*, including cards never suggested (as
    # explicit zeros) -- otherwise a player fixated on the same 3 cards over
    # and over has a card_frequency of just {X: N, Y: N, Z: N}, which is
    # perfectly uniform *among itself* (CV=0) and gets mislabeled as this
    # rule's "no discernible favorites" signature, the opposite of the truth.
    card_frequencies = list(stats.card_frequency.values()) + [0] * len(stats.never_suggested)
    cv = _coefficient_of_variation(card_frequencies)
    if cv is not None and cv <= UNIFORMITY_CV_THRESHOLD:
        return PlayerStrategy.RANDOM_EXPLORER, {
            "card_frequency_cv": cv,
            "threshold": UNIFORMITY_CV_THRESHOLD,
            "best_lock_ratio": best_ratio,
        }

    # 5. Information maximizer -- never repeats a two-card pairing.
    max_pair_repeat = max(stats.pair_frequency.values(), default=0)
    if max_pair_repeat <= MAX_PAIR_REPEAT_FOR_INFO_MAXIMIZER:
        return PlayerStrategy.INFORMATION_MAXIMIZER, {
            "max_pair_repeat": max_pair_repeat,
            "threshold": MAX_PAIR_REPEAT_FOR_INFO_MAXIMIZER,
            "total_suggestions": total,
        }

    # 6. No rule fired conclusively -- balanced/mixed play, with the
    # computed diagnostics included so this is still explainable rather than
    # a silent default.
    return PlayerStrategy.BALANCED, {
        "reason": "no_dominant_pattern",
        "best_lock_ratio": best_ratio,
        "coverage": coverage,
        "redundant_ratio": redundant_ratio,
        "max_pair_repeat": max_pair_repeat,
    }
