"""Pure 2d6 probability math -- no board, no game state, just the real
combinatorics of two six-sided dice. A room at a given distance is reachable
this turn under standard Cluedo movement rules iff the roll is >= distance
(move up to the rolled number; must spend exactly `distance` of it to enter
a room at that distance)."""
from __future__ import annotations

from cluedo.movement.models import DiceProbability

# Number of ways (out of 36) two six-sided dice sum to each total 2..12.
_TWO_D6_SUM_COUNTS = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
_TOTAL_OUTCOMES = 36


def probability_sum_exactly(n: int) -> float:
    """P(2d6 total == n). 0.0 outside the possible range 2..12."""
    return _TWO_D6_SUM_COUNTS.get(n, 0) / _TOTAL_OUTCOMES


def probability_sum_at_least(n: int) -> float:
    """P(2d6 total >= n). 1.0 for n <= 2 (always true), 0.0 for n > 12
    (impossible in a single roll)."""
    if n <= 2:
        return 1.0
    if n > 12:
        return 0.0
    return sum(_TWO_D6_SUM_COUNTS[k] for k in range(n, 13)) / _TOTAL_OUTCOMES


def reachable_this_turn(distance: int) -> bool:
    """Whether a room at this distance can be reached with a single 2d6
    roll this turn (distance <= 0 trivially True -- already there)."""
    return distance <= 12


def full_distribution(distance: int) -> DiceProbability:
    """The full roll-threshold table (2..12) for a room at `distance`,
    e.g. the user-facing "Roll 7+: 58%, 8+: 42%, ..." breakdown."""
    probabilities = {n: probability_sum_at_least(n) for n in range(2, 13)}
    return DiceProbability(distance=distance, probabilities=probabilities)
