"""Tests for cluedo/gui/recommendation_simulator_screen.py."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import recommendation_simulator_screen
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
    raise AssertionError("open_recommendation_simulator did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_shows_one_row_per_outcome(root, cfg, cards_by_name, three_players):
    from cluedo.advisor import rank_candidates_detailed

    gs = _fresh_game(cfg, cards_by_name, three_players)
    detailed = rank_candidates_detailed(gs, top_k=1)[0]
    app = _FakeApp(root, gs)

    recommendation_simulator_screen.open_recommendation_simulator(app, detailed)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        assert "Probability" in text
        assert "Worlds remaining" in text
        assert "Resulting confidence" in text
    finally:
        win.destroy()


def test_defaults_to_top_candidate_when_none_given(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    recommendation_simulator_screen.open_recommendation_simulator(app)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        assert "No candidate suggestion available" not in text
    finally:
        win.destroy()
