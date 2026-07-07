"""Tests for cluedo/gui/movement_screen.py: graceful no-data / no-position
early returns, and the full rankings/route-preview/simulator/canvas path
against the real bundled swedish_2012 movement data."""
import tkinter as tk

from cluedo.config import load_bundled_edition
from cluedo.game import GameState
from cluedo.gui import movement_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import Player


class _FakeApp:
    def __init__(self, root, game_state, edition_key):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self._edition_key = edition_key
        self._graph_cache = None

    def current_movement_graph(self):
        if self.game_state is None or self._edition_key is None:
            return None
        if self._graph_cache is None:
            from cluedo.movement.graph import MovementGraph

            self._graph_cache = MovementGraph.from_edition(self._edition_key, self.game_state.config.rooms)
        return self._graph_cache


def _swedish_game():
    cfg = load_bundled_edition("swedish_2012")
    players = [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]
    gs = GameState(cfg, players, user_seat=0)
    hand = cfg.suspects[:2] + cfg.weapons[:2] + cfg.rooms[:2]
    gs.set_user_hand([c for c in cfg.all_cards() if c.name in hand])
    return gs


def _classic_uk_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_movement_screen did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    if isinstance(widget, tk.Canvas):
        for item in widget.find_all():
            if widget.type(item) == "text":
                chunks.append(str(widget.itemcget(item, "text")))
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_no_movement_data_shows_graceful_message(root, cfg, cards_by_name, three_players):
    gs = _classic_uk_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs, edition_key="classic_uk")

    movement_screen.open_movement_screen(app)
    win = _find_toplevel(root)
    try:
        root.update_idletasks()
        assert "No movement data for this edition yet." in _all_text(win)
        assert _find_button_with_text(win, "Close") is not None
    finally:
        win.destroy()


def test_no_current_room_shows_graceful_message(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    movement_screen.open_movement_screen(app)
    win = _find_toplevel(root)
    try:
        root.update_idletasks()
        assert "Set your current position" in _all_text(win)
        assert _find_button_with_text(win, "Close") is not None
    finally:
        win.destroy()


def test_full_screen_renders_rankings_route_and_board(root):
    gs = _swedish_game()
    gs.set_current_room("Köket")
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    movement_screen.open_movement_screen(app)
    win = _find_toplevel(root)
    try:
        root.update_idletasks()
        text = _all_text(win)
        assert "Move:" in text
        for room in gs.config.rooms:
            assert room in text
    finally:
        win.destroy()


def test_sorting_rankings_by_column_does_not_crash(root):
    gs = _swedish_game()
    gs.set_current_room("Köket")
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    movement_screen.open_movement_screen(app)
    win = _find_toplevel(root)
    try:
        root.update_idletasks()
        # _render_rankings() destroys and rebuilds the header buttons on
        # every sort -- re-find the button by text each time rather than
        # reusing a Python reference, which goes stale (invalid Tcl command)
        # the moment the row it belongs to is torn down.
        assert _find_button_with_text(win, "Distance") is not None
        _find_button_with_text(win, "Distance").invoke()
        root.update_idletasks()
        _find_button_with_text(win, "Distance").invoke()  # toggle direction
        root.update_idletasks()
    finally:
        win.destroy()


def test_movement_simulator_updates_reachable_rooms(root):
    gs = _swedish_game()
    gs.set_current_room("Köket")
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    movement_screen.open_movement_screen(app)
    win = _find_toplevel(root)
    try:
        root.update_idletasks()
        roll_button = _find_button_with_text(win, "6")
        assert roll_button is not None
        roll_button.invoke()
        root.update_idletasks()
        assert "Rolling 6" in _all_text(win)
    finally:
        win.destroy()


def _find_button_with_text(widget, text):
    if isinstance(widget, tk.Button) and str(widget.cget("text")).startswith(text):
        return widget
    for child in widget.winfo_children():
        found = _find_button_with_text(child, text)
        if found is not None:
            return found
    return None
