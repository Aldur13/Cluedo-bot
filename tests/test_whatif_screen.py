"""Tests for cluedo/gui/whatif_screen.py, focused on the ChoiceGrid-instead-
of-OptionMenu fix (matching suggestion_dialog.py's one-click button grids)
and that simulating a hypothetical still works end-to-end.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import whatif_screen
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
    raise AssertionError("open_whatif did not create a Toplevel")


def test_no_optionmenu_widgets_used(root, cfg, cards_by_name, three_players):
    # The whole point of this fix: suggester/suspect/weapon/room pickers must
    # be ChoiceGrid button grids, not the old two-click tk.OptionMenu dropdowns.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    whatif_screen.open_whatif(app)
    win = _find_toplevel(root)
    try:
        def _all_widgets(widget):
            found = [widget]
            for child in widget.winfo_children():
                found.extend(_all_widgets(child))
            return found

        assert not any(isinstance(w, tk.OptionMenu) for w in _all_widgets(win))
        # Every option should be a single-click Button (ChoiceGrid's building block).
        assert any(isinstance(w, tk.Button) for w in _all_widgets(win))
    finally:
        win.destroy()


def test_simulate_no_show_outcome_reports_result(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    whatif_screen.open_whatif(app)
    win = _find_toplevel(root)
    try:
        simulate_button = next(
            w for w in win.winfo_children()
            if isinstance(w, tk.Button) and "Simulate" in str(w.cget("text"))
        )
        simulate_button.invoke()

        result_label = next(
            w for w in win.winfo_children()
            if isinstance(w, tk.Label) and w.cget("wraplength") not in (0, "0")
        )
        text = str(result_label.cget("text"))
        assert text  # some result was reported, without raising
    finally:
        win.destroy()
