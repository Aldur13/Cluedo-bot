"""Tests for App's Game Review wiring (cluedo/gui/app.py):
_maybe_auto_open_review's one-shot behavior and
_game_review_time_played_seconds's wall-clock bookkeeping.

Bypasses App.__init__ (via App.__new__) for the same reason
tests/test_app_player_store.py does -- __init__ creates a real Tk root and
may pop a real "recover autosave?" messagebox dialog. Uses the session-scoped
`root` fixture from conftest.py for the one real Tk root every GUI test file
shares, since _maybe_auto_open_review legitimately opens a real Toplevel.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui.app import App
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import SuggestionResponse


class _FakeStore:
    def __init__(self):
        self.game_starts = []
        self.suggestions = []
        self.game_ends = []

    def record_game_start(self, game_id, edition, players):
        self.game_starts.append((game_id, edition, tuple(players)))

    def record_suggestion(self, game_id, index, suggestion):
        self.suggestions.append((game_id, index, suggestion))

    def record_game_end(self, game_id, solved, solved_turn, solution):
        self.game_ends.append((game_id, solved, solved_turn, solution))


def _bare_app(root, game_state):
    app = App.__new__(App)
    app.root = root
    app.theme_manager = ThemeManager(LIGHT)
    app.game_state = game_state
    app.player_store = _FakeStore()
    app._game_id = None
    app._game_end_recorded = False
    app._game_start_wall_clock = None
    app._game_review_shown = False
    app._game_review_cache = None
    app._mutation_listeners = []
    app.refresh_main_screen = lambda: None
    return app


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def test_auto_open_review_fires_exactly_once_when_solved(root, cfg, cards_by_name, three_players, tmp_path, monkeypatch):
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(root, gs)
    app._start_tracking_game()
    before = set(_toplevels(root))

    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()

    app.after_mutation()
    first_round = [w for w in _toplevels(root) if w not in before]
    try:
        assert len(first_round) == 1  # exactly one Game Review window opened
        assert app._game_review_shown is True

        app.after_mutation()  # calling again post-solve must not open a second one
        second_round = [w for w in _toplevels(root) if w not in before]
        assert len(second_round) == 1  # still just the one
    finally:
        for w in first_round:
            w.destroy()


def test_undo_after_solve_rearms_review_for_a_later_different_solve(
    root, cfg, cards_by_name, three_players, tmp_path, monkeypatch
):
    # Regression: _game_review_shown/_game_review_cache were only ever reset
    # in _start_tracking_game(), never when a solved game goes back to
    # unsolved (undo). Re-solving differently after an undo used to leave
    # the sidebar's Game Review card showing the *first* solve's stale
    # grade/efficiency/turns-played data, since _maybe_auto_open_review()
    # no-ops once _game_review_shown is already True.
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(root, gs)
    app._start_tracking_game()
    before = set(_toplevels(root))
    opened = []

    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()
    app.after_mutation()
    opened.extend(w for w in _toplevels(root) if w not in before and w not in opened)
    first_review = app._game_review_cache
    assert first_review is not None
    assert first_review.turns_played == 1

    gs.undo_last_suggestion()
    assert not gs.is_solved()
    app.after_mutation()
    try:
        assert app._game_review_shown is False
        assert app._game_review_cache is None

        gs.record_suggestion(
            1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
            [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
        )
        gs.record_suggestion(
            0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
        )
        assert gs.is_solved()
        app.after_mutation()
        opened.extend(w for w in _toplevels(root) if w not in before and w not in opened)

        second_review = app._game_review_cache
        assert second_review is not None
        assert second_review.turns_played == 2
        assert second_review is not first_review
    finally:
        for w in opened:
            w.destroy()


def test_no_auto_open_while_unsolved(root, cfg, cards_by_name, three_players, tmp_path, monkeypatch):
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(root, gs)
    app._start_tracking_game()
    before = set(_toplevels(root))

    app.after_mutation()

    assert app._game_review_shown is False
    assert [w for w in _toplevels(root) if w not in before] == []


def test_time_played_uses_wall_clock_since_tracking_started(cfg, cards_by_name, three_players, monkeypatch):
    import cluedo.gui.app as app_module

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = App.__new__(App)
    app.game_state = gs
    app.player_store = _FakeStore()
    app._game_id = None
    app._game_end_recorded = False
    app._game_start_wall_clock = None
    app._game_review_shown = False

    clock = iter([100.0, 137.5])
    monkeypatch.setattr(app_module.time, "monotonic", lambda: next(clock))

    app._start_tracking_game()  # consumes 100.0 as the start time
    assert app._game_review_time_played_seconds() == 37.5  # 137.5 (now) - 100.0 (start)


def test_time_played_none_before_tracking_starts():
    app = App.__new__(App)
    app._game_start_wall_clock = None
    assert app._game_review_time_played_seconds() is None
