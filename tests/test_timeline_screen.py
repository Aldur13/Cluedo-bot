"""Tests for cluedo/gui/timeline_screen.py."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import timeline_screen
from cluedo.gui.app import App
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import SuggestionResponse


class _FakeStore:
    def record_suggestion(self, *a, **k):
        pass

    def record_game_end(self, *a, **k):
        pass


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


def test_timeline_reflects_mutations_made_while_still_open(root, cfg, cards_by_name, three_players, tmp_path, monkeypatch):
    # Regression: Timeline's refresh() was only ever called by its own
    # edit/delete actions, never registered with app's mutation notifications
    # -- logging a new suggestion via a different, non-modal dialog while
    # Timeline stayed open left its listbox showing the pre-mutation history.
    monkeypatch.setattr("cluedo.gui.app.default_autosave_path", lambda: tmp_path / "autosave.json")
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(root, gs)

    timeline_screen.open_timeline(app)
    win = next(w for w in _toplevels(root) if w.title() == "Timeline")
    try:
        listbox = next(w for w in win.winfo_children() if isinstance(w, tk.Listbox))
        assert listbox.size() == 0

        # A partial, non-solving suggestion -- keeps this test scoped to the
        # mutation-listener wiring rather than also exercising Game Review's
        # auto-open-on-solve path (covered separately in test_app_game_review.py).
        gs.record_suggestion(
            1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
            [SuggestionResponse(2, "shown_unseen")],
        )
        assert not gs.is_solved()
        app.after_mutation()

        assert listbox.size() == 1
    finally:
        win.destroy()


def test_closing_timeline_unregisters_its_mutation_listener(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _bare_app(root, gs)

    timeline_screen.open_timeline(app)
    win = next(w for w in _toplevels(root) if w.title() == "Timeline")
    assert len(app._mutation_listeners) == 1

    win.destroy()
    root.update()
    assert len(app._mutation_listeners) == 0
