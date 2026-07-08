"""Tests for cluedo/gui/world_explorer_screen.py -- including the
background-thread enumeration + `.after()` poll completion pattern, the one
async code path in this codebase.
"""
import time
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import world_explorer_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import CardType, Player, SuggestionResponse


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


def _game_with_suggestions(cfg, cards_by_name, three_players):
    # A fresh game with zero suggestions logged is too ambiguous for exact
    # probabilities (TooManyAmbiguousCardsError) -- log a couple of real
    # facts first, same fixture shape used in tests/test_panels.py.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_unseen")],
    )
    gs.record_suggestion(
        0, suspects[1], weapons[1], rooms[1],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_unseen")],
    )
    return gs


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
    raise AssertionError("open_world_explorer did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def _wait_until_computed(win, root, timeout=5.0) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        root.update()
        if "Computing" not in _all_text(win):
            return True
        time.sleep(0.02)
    return False


def test_world_explorer_solved_game_shows_one_world(root, cfg):
    gs = _solved_game(cfg)
    app = _FakeApp(root, gs)

    world_explorer_screen.open_world_explorer(app)
    win = _find_toplevel(root)
    try:
        assert _wait_until_computed(win, root)
        text = _all_text(win)
        assert "1 candidate world" in text
        suspect, weapon, room = gs.solution()
        assert suspect.name in text
        assert weapon.name in text
        assert room.name in text
        assert "100%" in text
    finally:
        win.destroy()


def test_world_explorer_fresh_game_populates_multiple_worlds(root, cfg, cards_by_name, three_players):
    gs = _game_with_suggestions(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    world_explorer_screen.open_world_explorer(app)
    win = _find_toplevel(root)
    try:
        assert _wait_until_computed(win, root)
        text = _all_text(win)
        assert "candidate world" in text
        assert "Reason still valid" in text
    finally:
        win.destroy()
