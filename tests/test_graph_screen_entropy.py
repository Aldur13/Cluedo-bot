"""Tests for the v4.5 additions to cluedo/gui/graph_screen.py: entropy and
top-3 envelope-probability-over-time subplots."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import graph_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import SuggestionResponse


class _FakeApp:
    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_graphs did not create a Toplevel")


def test_figure_has_five_subplots(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    app = _FakeApp(root, gs)

    graph_screen.open_graphs(app)
    win = _find_toplevel(root)
    try:
        fig = win.cluedo_figure
        assert len(fig.axes) == 5
        titles = [ax.get_title() for ax in fig.axes]
        assert any("entropy" in t.lower() for t in titles)
        assert any("envelope probability" in t.lower() for t in titles)
    finally:
        win.destroy()
