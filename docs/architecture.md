# Architecture

## Why the split

`cluedo/` (everything except `cluedo/gui/`) has zero Tkinter imports. Every
module in it is a plain, deterministic function/class over dataclasses, and is
unit-tested without ever creating a window. `cluedo/gui/` is a thin
presentation layer: every screen/dialog reads from and calls into a
`GameState`, and none of the deduction logic lives there. This means the whole
solver can be verified (and re-verified after any change) in well under a
second via `pytest`, independent of whether the GUI happens to render
correctly on a given machine.

## Module map

```
cluedo/
  models.py       Card, CardType, Player, Suggestion, SuggestionResponse — the
                   plain data types every other module shares.
  config.py       Loads and validates a card-set edition from JSON into a
                   CardConfig (suspects/weapons/rooms).
  engine.py       ConstraintEngine — the core solver. Owns constraint
                   propagation, the bounded exhaustive confirmation step, and
                   contradiction detection. Everything else built on it is a
                   fresh instance recomputed from scratch, never patched
                   in place.
  probability.py  Exact model counting (memoized DP) over the small set of
                   still-ambiguous cards. Powers envelope probabilities, the
                   zero-valid-worlds contradiction check, and the advisor's
                   expected-information-gain scoring.
  explain.py      Fact/Explanation/ExplanationRegistry — records *why* each
                   confirmed card is true, as a small proof citing the
                   specific prior facts that forced the conclusion.
  history.py      rebuild_game_state's GUI-facing conveniences: precomputed
                   replay snapshots and a scratch what-if branch. (The
                   rebuild-from-scratch primitive itself lives as a
                   classmethod on GameState, since history.py needs to
                   construct GameState instances and GameState's own
                   undo/edit/delete need the same primitive — putting it on
                   GameState avoids a circular import between the two
                   modules.)
  game.py         GameState — the facade the GUI actually talks to. Owns the
                   atomic "build a candidate, only adopt it if it doesn't
                   raise ContradictionError" pattern used by every mutation:
                   setting your hand, recording/editing/deleting a
                   suggestion, undo. Also owns save/load (atomic writes with
                   a rolling backup) and delegates to probability.py/
                   explain.py/advisor.py for reads.
  advisor.py      Ranks candidate suggestions: a cheap uncertainty heuristic
                   prunes ~324 possible triples down to a handful, then those
                   survivors are scored exactly by expected information gain
                   using probability.py's model counting and history.py's
                   what-if primitive.
  gui/            Tkinter screens and dialogs. Only imports from cluedo.* and
                   tkinter; owns no deduction logic.
```

## The atomic-mutation pattern

Every mutation to a live game — setting your hand, logging a suggestion,
editing or deleting a past one, undo — goes through the same path:

1. Build a brand-new `GameState` by replaying the (possibly modified) history
   through a fresh `ConstraintEngine`, via `GameState.from_history(...)`.
2. If that replay raises `ContradictionError` at any point, the exception
   propagates straight to the caller. Nothing about the *live* `GameState` has
   been touched — the candidate was a separate object the whole time.
3. Only if the replay succeeds does the caller copy the candidate's engine,
   history, and hand back onto `self`.

This is why a rejected edit can never leave the app in a half-mutated state:
there is no "half," only "the old live state" or "the new live state,"
never both partially merged.

## Data flow for a logged suggestion

`suggestion_dialog.py` collects who suggested what and how each other player
responded → `GameState.record_suggestion(...)` → builds a candidate via
`from_history` → each `SuggestionResponse` becomes one or more `ConstraintEngine`
facts (`Owned`, `NotOwned`, or `AtLeastOne`) → `engine.recompute()` propagates
to a fixpoint, runs the bounded confirmation search, and checks for
contradictions → on success, the candidate is adopted as the live state and
the main screen refreshes its detective sheet, advisor panel, and probability
panel from it.

## Additions since the original split (analysis / persistence / review)

Two new top-level packages sit alongside the solver core, both explicitly
guarded by `tests/test_architecture_boundaries.py` from ever being imported
back into `engine.py`/`probability.py`/`advisor.py`/`explain.py` — they are
read-only consumers of the solver, never inputs to it:

```
cluedo/
  analysis/
    patterns.py       Rule-based per-player suggestion-pattern stats
                       (redundancy, category-lock streaks, favorites).
    strategy.py        Threshold classification on top of patterns.py
                       (Room Hunter, Bluffer, Aggressive Eliminator, ...).
    endgame.py          "Safe to accuse yet?" advisory -- never names a
                       specific accusation before is_solved() is true.
    game_review.py     Full post-game report (difficulty, grade, key
                       turning point, missed opportunities, timeline,
                       performance metrics). See
                       docs/game_review_explained.md for every algorithm.
  persistence/
    player_store.py    Local SQLite cross-game history (opt-out via
                       Settings), powering AI Insights across games.
  timeseries.py         Pure per-turn series (valid worlds, info gain,
                       confirmed-card count, envelope probability) computed
                       from history.build_replay_snapshots -- no matplotlib
                       import here; rendering lives in gui/graph_screen.py.
  gui/
    panels/            Reusable dashboard side-panels (best_suggestion,
                       mystery_progress, envelope_probabilities,
                       ai_insights, endgame, game_statistics), each a
                       `build(parent, theme) -> Frame` with `.refresh(gs)`
                       attached, composed by main_screen.py.
    graph_screen.py     "Trends" Toplevel -- matplotlib (TkAgg) charts over
                       timeseries.py output.
    game_review_screen.py  "Game Review" Toplevel -- opens automatically
                       once per solved game (App._maybe_auto_open_review),
                       or manually via the toolbar.
    game_review_export.py  PDF/HTML/Markdown/JSON export of a GameReview
                       (matplotlib's headless "Agg" backend, not "TkAgg" --
                       no Tk root required).
    settings_screen.py  Theme picker (wires the pre-existing ThemeManager)
                       + the cross-game learning opt-out toggle.
```

`App` (`gui/app.py`) owns a `PlayerStore` instance and a per-game `game_id`
(a fresh `uuid4` assigned in `_start_tracking_game`, not persisted in the
JSON save format -- cross-game history is a separate, optional local
database, not part of a single game's save file). It also stamps a
wall-clock start time for the *current session's* "time played" figure shown
in Game Review; that figure is intentionally not part of the save format
either, so old saves keep loading unchanged.
