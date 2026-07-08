"""Tests for cluedo/gui/turn_inspector_screen.py."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import turn_inspector_screen
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
    raise AssertionError("open_turn_inspector did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_shows_suggestion_and_responses(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    app = _FakeApp(root, gs)

    turn_inspector_screen.open_turn_inspector(app)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        assert "Reverend Green" in text
        assert "Rope" in text
        assert "Kitchen" in text
        assert "no show" in text
    finally:
        win.destroy()


def test_no_history_shows_info_message_and_no_toplevel(root, cfg, cards_by_name, three_players, monkeypatch):
    from tkinter import messagebox

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)
    before = set(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))

    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: None)
    turn_inspector_screen.open_turn_inspector(app)

    after = set(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
    assert after == before


def test_navigates_to_specific_turn(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Wrench"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )
    app = _FakeApp(root, gs)

    turn_inspector_screen.open_turn_inspector(app, turn_index=1)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        assert "Turn 1 of 2" in text
    finally:
        win.destroy()
