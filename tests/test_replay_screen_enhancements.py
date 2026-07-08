"""Tests for the v4.5 additions to cluedo/gui/replay_screen.py: world count,
envelope probability summary, largest-deduction/missed-opportunities-so-far,
and next/previous-deduction jump buttons.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import replay_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import SuggestionResponse


class _FakeApp:
    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self._game_review_cache = None


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_replay did not create a Toplevel")


def test_shows_world_count_and_envelope_candidates(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    replay_screen.open_replay(app)
    win = _find_toplevel(root)
    try:
        label = next(w for w in win.winfo_children() if isinstance(w, tk.Label) and "After turn" in str(w.cget("text")))
        text = str(label.cget("text"))
        assert "Valid worlds remaining" in text
        assert "Top envelope candidate per category" in text
    finally:
        win.destroy()


def test_jump_to_next_deduction_button_exists(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "shown_to_me", shown_card=cards_by_name["Rope"]), SuggestionResponse(2, "no_show")],
    )
    app = _FakeApp(root, gs)

    replay_screen.open_replay(app, initial_index=0)
    win = _find_toplevel(root)
    try:
        buttons = [w for w in win.winfo_children() if isinstance(w, tk.Frame) for w in w.winfo_children() if isinstance(w, tk.Button)]
        labels = {b.cget("text") for b in buttons}
        assert any("Next deduction" in t for t in labels)
        assert any("Prev deduction" in t for t in labels)
    finally:
        win.destroy()
