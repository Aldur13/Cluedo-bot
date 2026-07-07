"""Widget-level tests for cluedo/gui/game_review_screen.py.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import game_review_screen, replay_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import SuggestionResponse


class _FakeApp:
    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state


def _solved_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()
    return gs


def _unsolved_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _toplevels(root):
    return [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]


def test_opens_a_toplevel_for_a_solved_game(root, cfg, cards_by_name, three_players):
    before = set(_toplevels(root))
    app = _FakeApp(root, _solved_game(cfg, cards_by_name, three_players))

    game_review_screen.open_game_review(app)
    new_windows = [w for w in _toplevels(root) if w not in before]
    try:
        assert len(new_windows) == 1
        assert new_windows[0].title() == "Game Review"
    finally:
        for w in new_windows:
            w.destroy()


def test_opens_without_crashing_for_an_unsolved_game(root, cfg, cards_by_name, three_players):
    before = set(_toplevels(root))
    app = _FakeApp(root, _unsolved_game(cfg, cards_by_name, three_players))

    game_review_screen.open_game_review(app)
    new_windows = [w for w in _toplevels(root) if w not in before]
    try:
        assert len(new_windows) == 1
    finally:
        for w in new_windows:
            w.destroy()


def test_timeline_click_opens_replay_at_that_turn(root, cfg, cards_by_name, three_players, monkeypatch):
    app = _FakeApp(root, _solved_game(cfg, cards_by_name, three_players))
    before = set(_toplevels(root))

    game_review_screen.open_game_review(app)
    review_window = next(w for w in _toplevels(root) if w not in before)
    try:
        calls = []
        monkeypatch.setattr(
            replay_screen, "open_replay",
            lambda app, initial_index=None: calls.append(initial_index),
        )

        def _find_buttons(widget):
            found = []
            if isinstance(widget, tk.Button):
                found.append(widget)
            for child in widget.winfo_children():
                found.extend(_find_buttons(child))
            return found

        timeline_buttons = [
            b for b in _find_buttons(review_window) if str(b.cget("text")).startswith("Turn 1")
        ]
        assert timeline_buttons, "expected at least one clickable timeline entry for turn 1"
        timeline_buttons[0].invoke()
        assert calls == [1]
    finally:
        review_window.destroy()


def test_export_buttons_present(root, cfg, cards_by_name, three_players):
    app = _FakeApp(root, _solved_game(cfg, cards_by_name, three_players))
    before = set(_toplevels(root))

    game_review_screen.open_game_review(app)
    review_window = next(w for w in _toplevels(root) if w not in before)
    try:
        def _all_text(widget):
            texts = []
            try:
                texts.append(str(widget.cget("text")))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                texts.extend(_all_text(child))
            return texts

        texts = _all_text(review_window)
        for label in ("PDF", "HTML", "Markdown", "JSON"):
            assert label in texts
    finally:
        review_window.destroy()


def test_precomputed_review_is_used_when_supplied(root, cfg, cards_by_name, three_players):
    from cluedo.analysis.game_review import compute_game_review

    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs, time_played_seconds=42.0)
    app = _FakeApp(root, gs)
    before = set(_toplevels(root))

    game_review_screen.open_game_review(app, review=review)
    new_windows = [w for w in _toplevels(root) if w not in before]
    try:
        assert len(new_windows) == 1
    finally:
        for w in new_windows:
            w.destroy()
