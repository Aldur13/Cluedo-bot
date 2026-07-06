# Developer guide

## Setup

```bash
pip install -r requirements-dev.txt
```

## Running tests

```bash
python -m pytest
```

`tests/` mirrors the module list under `cluedo/`: `test_engine.py`,
`test_probability.py`, `test_explain.py`, `test_history.py`, `test_game.py`,
`test_advisor.py`, plus `test_property.py` for randomized whole-game
correctness checks. All of it runs headless in well under a minute — none of
it touches Tkinter.

`tests/conftest.py` provides shared fixtures: `cfg` (the Classic UK edition),
`cards_by_name`, and `three_players` (a standard 3-player, 6-cards-each setup)
used across most tests.

## Adding a new edition

Drop a new JSON file under `cluedo/data/` with `edition`, `suspects` (6),
`weapons` (6), `rooms` (9) — see [json_schemas.md](json_schemas.md) — and
register it in `BUNDLED_EDITIONS` in `cluedo/config.py`. No engine changes are
needed; the solver only ever deals with however many cards the loaded config
defines split across three categories.

## Extending the solver

`ConstraintEngine` recomputes fully from scratch on every `recompute()` call
rather than patching state incrementally — this is deliberate given how small
the problem is (21 cards, at most 6 owners), and it means new propagation
rules can be added to the fixpoint loop in `engine.py` without worrying about
invalidation bugs. If you add a new rule, also add a matching `Explanation`
so confirmations it produces stay explainable (see `explain.py` and the
existing rules in `engine.py` for the pattern), and a unit test showing a
case propagation *couldn't* solve without it.

## Extending the GUI

Every screen/dialog in `cluedo/gui/` takes the `App` controller (or a
`GameState` reached through it) and never holds solver state of its own.
`app.after_mutation()` is the single hook that autosaves and refreshes the
main screen after any change — call it after any new mutation you add rather
than refreshing widgets by hand.

## Manual smoke test

Since Tkinter isn't covered by the automated test suite, after any GUI change
run through: edition select → setup → hand → log a suggestion (including a
"shown to someone else" case) → open the explain dialog on a confirmed card →
undo → edit/delete via the timeline → replay → what-if → export (PNG/PDF/
JSON/CSV) → save/quit/relaunch to confirm autosave recovery.
