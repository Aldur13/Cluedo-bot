"""Tests for cluedo/gui/suggestion_comparison_screen.py."""
import tkinter as tk

from cluedo.advisor import rank_candidates_detailed
from cluedo.game import GameState
from cluedo.gui import suggestion_comparison_screen
from cluedo.gui.theme import LIGHT, ThemeManager


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
    raise AssertionError("open_suggestion_comparison did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def _checkbuttons(widget):
    found = []
    if isinstance(widget, tk.Checkbutton):
        found.append(widget)
    for child in widget.winfo_children():
        found.extend(_checkbuttons(child))
    return found


def test_lists_top_candidates(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    expected = rank_candidates_detailed(gs, top_k=5)
    app = _FakeApp(root, gs)

    suggestion_comparison_screen.open_suggestion_comparison(app)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        for dc in expected:
            assert dc.candidate.suspect.name in text
    finally:
        win.destroy()


def test_checking_two_shows_compare_columns(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    suggestion_comparison_screen.open_suggestion_comparison(app)
    win = _find_toplevel(root)
    try:
        checks = _checkbuttons(win)
        assert len(checks) >= 2
        checks[0].invoke()
        checks[1].invoke()
        text = _all_text(win)
        assert "Select exactly two" not in text
    finally:
        win.destroy()
