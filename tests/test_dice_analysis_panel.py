"""Dedicated tests for the Dice Analysis panel beyond the shared
"every panel survives build+refresh" loop in test_panels.py: graceful
no-movement-data messaging, and the room-picker's real update-and-refresh
path against the real bundled swedish_2012 movement data."""
import tkinter as tk

from cluedo.config import load_bundled_edition
from cluedo.game import GameState
from cluedo.gui.panels import dice_analysis_panel
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import Player


class _FakeApp:
    def __init__(self, root, game_state, edition_key):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self.mutations = 0
        self._edition_key = edition_key
        self._graph_cache = None

    def after_mutation(self):
        self.mutations += 1

    def current_movement_graph(self):
        if self.game_state is None or self._edition_key is None:
            return None
        if self._graph_cache is None:
            from cluedo.movement.graph import MovementGraph

            self._graph_cache = MovementGraph.from_edition(self._edition_key, self.game_state.config.rooms)
        return self._graph_cache


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def _swedish_game():
    cfg = load_bundled_edition("swedish_2012")
    players = [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]
    gs = GameState(cfg, players, user_seat=0)
    hand = cfg.suspects[:2] + cfg.weapons[:2] + cfg.rooms[:2]
    gs.set_user_hand([c for c in cfg.all_cards() if c.name in hand])
    return gs


def test_classic_uk_shows_no_movement_data_message(root, cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    app = _FakeApp(root, gs, edition_key="classic_uk")

    frame = dice_analysis_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        assert "No movement data for this edition yet." in _all_text(frame)
    finally:
        frame.destroy()


def test_swedish_2012_prompts_for_position_when_unset(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    frame = dice_analysis_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "Set your current position" in text
    finally:
        frame.destroy()


def test_picking_a_room_sets_current_room_and_triggers_mutation(root):
    gs = _swedish_game()
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    frame = dice_analysis_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()

        button = _find_button_with_text(frame, "Köket")
        assert button is not None
        button.invoke()
        root.update_idletasks()

        assert gs.current_room == "Köket"
        assert app.mutations == 1
    finally:
        frame.destroy()


def test_shows_best_destination_and_route_once_position_set(root):
    gs = _swedish_game()
    gs.set_current_room("Köket")
    app = _FakeApp(root, gs, edition_key="swedish_2012")

    frame = dice_analysis_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "Best destination:" in text
        # Garaget is directly passage-connected from Köket -- instant.
        assert "Garaget" in text or "Distance:" in text
    finally:
        frame.destroy()


def _find_button_with_text(widget, text):
    if isinstance(widget, tk.Button) and widget.cget("text") == text:
        return widget
    for child in widget.winfo_children():
        found = _find_button_with_text(child, text)
        if found is not None:
            return found
    return None
