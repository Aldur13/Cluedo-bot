"""Tests for cluedo/gui/deduction_graph_screen.py."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import deduction_graph_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import CardType, Player


class _FakeApp:
    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state


def _solved_game(cfg):
    all_cards = cfg.all_cards()
    withheld = {
        next(c for c in all_cards if c.type == CardType.SUSPECT),
        next(c for c in all_cards if c.type == CardType.WEAPON),
        next(c for c in all_cards if c.type == CardType.ROOM),
    }
    hand = [c for c in all_cards if c not in withheld]
    gs = GameState(cfg, [Player("Alice", 0, len(hand)), Player("Bob", 1, 0)], user_seat=0)
    gs.set_user_hand(hand)
    assert gs.is_solved()
    return gs


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_deduction_graph did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_renders_a_row_per_confirmed_card(root, cfg):
    gs = _solved_game(cfg)
    suspect, _weapon, _room = gs.solution()
    app = _FakeApp(root, gs)

    deduction_graph_screen.open_deduction_graph(app, suspect)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        assert suspect.name in text
    finally:
        win.destroy()


def test_unconfirmed_card_shows_no_derivation_message(root, cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    app = _FakeApp(root, gs)

    ambiguous_card = next(c for c in gs.cards if c not in gs.engine.confirmed)
    deduction_graph_screen.open_deduction_graph(app, ambiguous_card)
    win = _find_toplevel(root)
    try:
        assert "No derivation is recorded" in _all_text(win)
    finally:
        win.destroy()
