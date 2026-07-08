"""Tests for cluedo/gui/envelope_explorer_screen.py."""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import envelope_explorer_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.models import CardType, SuggestionResponse


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


def _find_toplevel(root) -> tk.Toplevel:
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel):
            return child
    raise AssertionError("open_envelope_explorer did not create a Toplevel")


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_default_tab_shows_top_3_suspects(root, cfg, cards_by_name, three_players):
    from cluedo.models import ENVELOPE

    gs = _game_with_suggestions(cfg, cards_by_name, three_players)
    probs = gs.card_probabilities()
    suspects = sorted(
        (c for c in gs.cards if c.type == CardType.SUSPECT),
        key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), reverse=True,
    )
    app = _FakeApp(root, gs)

    envelope_explorer_screen.open_envelope_explorer(app)
    win = _find_toplevel(root)
    try:
        text = _all_text(win)
        for card in suspects[:3]:
            assert card.name in text
    finally:
        win.destroy()
