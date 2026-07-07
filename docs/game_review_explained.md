# How the Game Review works

This is a plain-English explanation of every algorithm behind the Game
Review screen (`cluedo/analysis/game_review.py`). As with the solver itself
(see [solver_explained.md](solver_explained.md)), nothing here guesses: every
number is derived from data the app already recorded or computed, and
anything that sounds probabilistic (expected information gain, difficulty)
traces back to the solver's own exact math, not a heuristic layered on top
of a guess.

## The one hard rule

**Never invent a hypothetical response that wasn't actually given at the
table.** This app has no oracle access to hidden hands — it only knows what
responses real players actually gave during real physical play. So every
"missed opportunity" or "better suggestion" claim is grounded in one of two
things:

1. The exact same real `(suggestion, response)` pairs, replayed in a
   different *order* — never with a different suggestion or a different
   response substituted in.
2. The advisor's own probability-weighted expected-information-gain math
   (`cluedo/advisor.py`) over the real set of possible outcomes *given what's
   already known* — the same computation the live advisor already runs
   during play, just run retrospectively against a historical snapshot.

## Shared foundation

Every review is built from one call to `history.build_replay_snapshots`,
producing one `GameState` per history prefix length (0..N). That single list
of snapshots is threaded through every calculation below rather than
rebuilt per-section — this is the single biggest cost in generating a
review (the same O(turns²) replay cost every other full-game analysis in
this codebase already accepts) and must only be paid once.

From those snapshots, three existing `cluedo.timeseries` functions supply
most of the raw numbers:

- `worlds_over_time` — valid remaining worlds after each turn (`None` when
  too ambiguous to count exactly).
- `info_gained_per_turn` — fraction of valid worlds each turn eliminated.
- `solver_progress_over_time` — confirmed-card count after each turn (always
  available, never gated behind an ambiguity cap).

## Actual Solve Turn

The first snapshot index at which `GameState.is_solved()` is true. `0` means
the game was already solved from the initial hand alone, before any
suggestion — the fastest possible outcome.

## Estimated Optimal Solve Turn

A greedy heuristic: the same real suggestions are re-sorted by their own
actual recorded *confirmed-card delta* (how many cards that turn caused to
be confirmed), descending, and replayed once in that new order. The earliest
prefix length at which the mystery is solved in that reordering is the
estimate.

Two deliberate design choices, both worth knowing about:

- **Sorted by confirmed-card delta, not by `info_gained_per_turn`.** Exact
  world-counting is gated behind an ambiguous-card cap
  (`probability.TooManyAmbiguousCardsError`) and reports `0.0` whenever that
  cap is exceeded — which is the common case early in a real game, exactly
  when reordering matters most. Confirmed-card count has no such cap, so
  it's the more robust (if coarser) signal.
- **This is a heuristic, not a proof of the true minimum.** Finding the true
  minimum would mean trying every permutation of suggestions, which is
  combinatorially infeasible. That's why every field built from this is
  named "estimated".

Reordering a real, already-consistent fact set can never introduce a
contradiction — any subset of a satisfiable constraint set is itself
satisfiable — so this calculation never raises.

## Turns Lost / Efficiency / Overall Rating

- `turns_lost = max(0, actual_solve_turn - estimated_optimal_solve_turn)`
- `efficiency_pct = 100 * estimated_optimal_solve_turn / actual_solve_turn`,
  capped at 100% (and defined as exactly 100% when `actual_solve_turn == 0`,
  since nothing beats an instant solve).
- The letter grade (`A+` down to `F`) is a fixed lookup table against
  `efficiency_pct` — see `_GRADE_THRESHOLDS` in `game_review.py`.

Both fields are `None` until the game is solved — grading an unsolved game
isn't meaningful yet.

## Final Accuracy

`100 * len(engine.confirmed) / len(cards)`, evaluated at whatever point the
review is generated. Unlike the other solve-dependent fields, this is always
available and not always 100% even for a *solved* game: `is_solved()` only
requires the envelope's three cards to be confirmed, not every player's
entire hand. A game can be fully solved while plenty of individual cards
remain ambiguous — Final Accuracy reflects that difference.

## Difficulty

A small, explainable threshold score (see `_estimate_difficulty`), not a
black-box model:

- **Base score** from player count: more seats means more hidden hands and
  slower convergence even with identical suggestion quality.
- **+1** if the game averaged more than `_DIFFICULTY_AMBIGUOUS_THRESHOLD`
  ambiguous cards per turn (more branching to work through at any moment).
- **+1** if the game averaged less than `_DIFFICULTY_LOW_GAIN_THRESHOLD`
  info gain per turn (progress was slow regardless of player count).

The score maps onto Easy → Medium → Hard → Expert, and the returned
explanation string names exactly which factors fired.

## Key Turning Point / Best Suggestion

Both are the same underlying turn — whichever one has the highest
`info_gained_per_turn` value — framed two ways (a narrative moment vs. a
suggestion's own numbers). If that turn happens to be the actual solve
turn, its narrative says so explicitly ("...made the final solution
logically inevitable"); otherwise it's described as "the single most
informative move of the game."

## Largest Deduction

The turn with the single largest jump in confirmed-card count
(`solver_progress_over_time`'s biggest single-step delta) — a different
lens from Key Turning Point on purpose: a turn can have a small *direct*
world-elimination fraction yet still trigger a large *cascading* deduction
once propagation runs, and that distinction is exactly what these two
metrics are for.

The specific card shown is whichever newly-confirmed card that turn has the
richest derivation chain (`GameState.explain_card_full_chain`), rendered
through the same `explain.py` narrative machinery the in-app "why?" dialog
uses — nothing here is a new explanation system, it's the existing one
applied retrospectively.

## Missed Opportunities

Four kinds, all evidence-based:

- **`earlier_accusation`** — reported when `turns_lost > 0`, citing the
  estimated optimal turn.
- **`redundant_suggestion`** — a suggestion where, at the time it was made,
  at least one of its three cards was already confirmed to someone other
  than the suggester. Mirrors `cluedo.analysis.patterns`'
  `_redundant_suggestion_count` definition exactly, but scanned once across
  every player using the review's already-shared snapshots (avoiding that
  module's own per-call snapshot rebuild).
- **`low_information`** — a turn whose real `info_gained_per_turn` value
  fell under `_LOW_INFO_GAIN_THRESHOLD`.
- **`better_suggestion`** — a turn where `advisor.rank_candidates`, run
  retrospectively against that turn's *prior* snapshot, shows the best
  available candidate's expected info gain beat what was actually achieved
  by more than `_BETTER_SUGGESTION_MARGIN`. This is the one place a
  probability appears that isn't a "what actually happened" number — but
  it's still never invented: `expected_info_gain` is the advisor's own
  exact, probability-weighted average over the real set of possible
  outcomes given what was already known at that point, the same number the
  live advisor would have shown the player in the moment.

The turn that actually achieved the solve is never flagged by any of the
last three kinds, regardless of its narrow metrics — nothing beats
immediately solving the mystery.

## Timeline

Chronologically sorted events: the first turn each category's envelope card
was confirmed ("Suspect/Weapon/Room identified"), the Largest Deduction
turn, the Key Turning Point turn, the Estimated Optimal Solve Turn
("Optimal accusation became available"), and the Actual Solve Turn ("Game
solved"). Each event is clickable in the UI and jumps Replay Mode straight
to that turn.

## Performance Metrics

Mostly direct pass-throughs of the shared `cluedo.timeseries` data
(`info_gain_per_turn`, `valid_worlds_per_turn`) plus:

- **Redundant / unique suggestion counts** — one shared pass over the
  snapshots (see Missed Opportunities above).
- **Envelope certainty progression** — `envelope_probability_over_time` for
  each of the three actual solution cards, only computed once the game is
  solved (there's no "the" solution to track probability toward before
  then).

## Time Played / Average Time Per Turn

The only fields not derived purely from `GameState`. `App` (the GUI
controller) stamps a wall-clock start time (`time.monotonic()`) when it
begins tracking a game and passes the elapsed seconds into
`compute_game_review` as `time_played_seconds`. This is deliberately *not*
persisted in the save file (no save-format change, full backward
compatibility with old saves) — it's "how long you've been playing since
you (re)opened this game this session," not a cumulative total across
save/load boundaries. `compute_game_review` itself never calls the system
clock; it only accepts this value as an optional parameter, keeping the
whole analysis module pure and deterministic for testing.

## Personalized Feedback

A short list of plain-English observations, each traceable to a specific
computed value above: efficiency-based praise/critique, a redundant-ratio
check, an average-info-gain check, and a "fastest category" compliment
naming the turn it was identified by. No feedback rule fires without citing
the number behind it.
