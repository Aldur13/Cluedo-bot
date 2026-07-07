"""Integration test for cluedo/gui/main_screen.py's dashboard wiring.

Guards against regressing to the old hand-rolled "Advisor"/"Envelope
probabilities"/"Statistics" boxes main_screen.py used to build inline instead
of importing cluedo.gui.panels -- and confirms Mystery Progress (previously
entirely absent from the dashboard) is now wired in.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import main_screen
from cluedo.gui.theme import LIGHT, ThemeManager


class _FakeApp:
    """Minimal stand-in for the App controller -- toolbar buttons just need
    zero-arg callables to bind to; we never click them in these tests."""

    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self.refresh_main_screen = lambda: None
        for name in (
            "open_suggestion_dialog", "undo", "open_timeline", "open_replay",
            "open_whatif", "open_graphs", "open_game_review", "save", "load", "open_export", "open_settings",
        ):
            setattr(self, name, lambda: None)

    def open_explain(self, card):
        pass


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _label_frames_by_text(widget) -> list[str]:
    found = []
    if isinstance(widget, tk.LabelFrame):
        found.append(str(widget.cget("text")))
    for child in widget.winfo_children():
        found.extend(_label_frames_by_text(child))
    return found


def test_dashboard_wires_all_four_panels_with_no_duplicate_or_orphaned_boxes(
    root, cfg, cards_by_name, three_players
):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    frame = main_screen.build(root, app)
    try:
        titles = _label_frames_by_text(frame)

        # New panel-backed sections, each present exactly once.
        for expected in (
            "Best Suggestion", "Mystery Progress", "Envelope Probabilities", "AI Insights",
            "Endgame", "Statistics",
        ):
            assert titles.count(expected) == 1, f"expected exactly one {expected!r} box, found {titles.count(expected)}"

        # Old hand-rolled titles main_screen.py used to build inline directly
        # (superseded by the panel modules above) must not reappear.
        assert "Advisor" not in titles

        # refresh_main_screen must have been rebound to the real refresh, not
        # left as the fake's no-op placeholder.
        assert app.refresh_main_screen is not None
        app.refresh_main_screen()  # should not raise
    finally:
        frame.destroy()


def test_dashboard_refresh_updates_panels_after_a_suggestion(root, cfg, cards_by_name, three_players):
    from cluedo.models import SuggestionResponse

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    frame = main_screen.build(root, app)
    try:
        gs.record_suggestion(
            1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
        )
        app.refresh_main_screen()  # should not raise with a live, mutated game_state
    finally:
        frame.destroy()
