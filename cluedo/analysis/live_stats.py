"""Live, always-available solver statistics -- "Solver Confidence" and
"Live Solver Statistics" from the product spec. Every field here is derived
from numbers the solver core already computes exactly
(`mystery_progress.py`, `timeseries.py`, `game_state.detective_sheet()`);
nothing is sampled or guessed. Where a figure is genuinely an estimate
(`expected_turns_to_solve`, which projects `chance_of_solving_next_turn`
forward assuming a similar chance persists), that is stated plainly in the
field's own name/docstring, matching this project's "AI predictions must be
clearly labeled as estimates" rule.

Read-only consumer of `cluedo.game`/`cluedo.history`/`cluedo.mystery_progress`/
`cluedo.timeseries`; kept under the `cluedo.analysis` prefix so
`tests/test_architecture_boundaries.py` continues to guarantee the solver
core never depends on it.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from cluedo.history import build_replay_snapshots
from cluedo.mystery_progress import compute_mystery_progress
from cluedo.timeseries import info_gained_per_turn

if TYPE_CHECKING:
    from cluedo.game import GameState

_STABILITY_WINDOW = 3


@dataclass(frozen=True)
class LiveStats:
    confidence_tier: str  # "Very Low" | "Low" | "Medium" | "High" | "Certain"
    confidence_explanation: str
    remaining_valid_worlds: Optional[int]
    confirmed_cards: int
    unknown_cards: int
    entropy_bits: Optional[float]
    expected_turns_to_solve: Optional[float]
    probability_stability: Optional[float]


def confidence_tier(remaining_valid_worlds: Optional[int], *, is_solved: bool = False) -> tuple[str, str]:
    """Public so other screens (e.g. the Recommendation Simulator, which
    derives a resulting confidence per simulated outcome) can reuse the
    exact same tiering `compute_live_stats` uses, instead of re-deriving
    their own thresholds."""
    if is_solved:
        return "Certain", "The mystery is fully solved -- every envelope card is confirmed."
    if remaining_valid_worlds is None:
        return "Very Low", "Too many cards are still ambiguous to even count remaining valid worlds exactly."
    if remaining_valid_worlds <= 1:
        return "Certain", "Only one valid world remains -- every card is logically determined."
    if remaining_valid_worlds <= 5:
        return "High", f"Only {remaining_valid_worlds} valid worlds remain."
    if remaining_valid_worlds <= 50:
        return "Medium", f"{remaining_valid_worlds:,} valid worlds remain -- narrowing down."
    if remaining_valid_worlds <= 500:
        return "Low", f"{remaining_valid_worlds:,} valid worlds remain -- still quite open."
    return "Very Low", f"{remaining_valid_worlds:,} valid worlds remain -- very little is pinned down yet."


def _entropy_bits(game_state: "GameState", remaining_valid_worlds: Optional[int]) -> Optional[float]:
    if game_state.is_solved():
        return 0.0
    if not remaining_valid_worlds or remaining_valid_worlds <= 0:
        return None
    # The solver's own probability model treats every valid world as equally
    # likely (see probability.py's docstring), so this is the standard
    # Shannon entropy of a uniform distribution over `remaining_valid_worlds`
    # outcomes -- not a new modeling assumption, just log2 of a number the
    # solver already produced exactly.
    return math.log2(remaining_valid_worlds)


def _expected_turns_to_solve(game_state: "GameState", chance_of_solving_next_turn: Optional[float]) -> Optional[float]:
    if game_state.is_solved():
        return 0.0
    if not chance_of_solving_next_turn or chance_of_solving_next_turn <= 0:
        return None
    # Geometric-distribution mean: an ESTIMATE that assumes a similar
    # per-turn solving chance persists going forward, not a guarantee --
    # the real chance changes every turn as more is learned.
    return 1.0 / chance_of_solving_next_turn


def _probability_stability(game_state: "GameState") -> Optional[float]:
    """1.0 = no recent change in per-turn information gain (a settled
    picture), 0.0 = highly volatile. Computed from the population standard
    deviation of the last few turns' `info_gained_per_turn` values -- real
    replayed history, never a forecast."""
    if not game_state.history:
        return None
    snapshots = build_replay_snapshots(game_state)
    gains = info_gained_per_turn(snapshots)
    if not gains:
        return None
    recent = gains[-_STABILITY_WINDOW:]
    spread = statistics.pstdev(recent) if len(recent) > 1 else 0.0
    return max(0.0, min(1.0, 1.0 - spread))


def compute_live_stats(game_state: "GameState") -> LiveStats:
    progress = compute_mystery_progress(game_state)
    tier, explanation = confidence_tier(progress.remaining_valid_worlds, is_solved=game_state.is_solved())

    return LiveStats(
        confidence_tier=tier,
        confidence_explanation=explanation,
        remaining_valid_worlds=progress.remaining_valid_worlds,
        confirmed_cards=progress.known_cards,
        unknown_cards=progress.total_cards - progress.known_cards,
        entropy_bits=_entropy_bits(game_state, progress.remaining_valid_worlds),
        expected_turns_to_solve=_expected_turns_to_solve(game_state, progress.chance_of_solving_next_turn),
        probability_stability=_probability_stability(game_state),
    )
