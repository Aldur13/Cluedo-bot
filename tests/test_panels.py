"""Real-Tkinter tests for the cluedo/gui/panels/ modules. Follows this
project's established pattern of building real `tk.Tk()` roots and real
`GameState` objects rather than mocking Tkinter -- this is a real desktop app
on a real Windows display, so there's no benefit to faking the toolkit.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file: creating/tearing down many independent `tk.Tk()`
interpreters in rapid succession was observed to intermittently fail with
`_tkinter.TclError: Can't find a usable tk.tcl` on this machine -- a
Tcl-interpreter-startup flake unrelated to the panels themselves -- and one
root shared across the whole session eliminates it.
"""
import tkinter as tk

import pytest

from cluedo.game import GameState
from cluedo.gui.panels import (
    ai_insights_panel,
    best_suggestion_panel,
    endgame_panel,
    envelope_probabilities_panel,
    game_statistics_panel,
    mystery_progress_panel,
)
from cluedo.gui.theme import DARK, HIGH_CONTRAST, LIGHT
from cluedo.models import CardType, Player, SuggestionResponse

PANEL_MODULES = [
    best_suggestion_panel,
    mystery_progress_panel,
    envelope_probabilities_panel,
    ai_insights_panel,
    endgame_panel,
    game_statistics_panel,
]
THEMES = [LIGHT, DARK, HIGH_CONTRAST]


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _game_with_suggestions(cfg, cards_by_name, three_players):
    # Second responder (Carol) shows a card for the first suggestion instead
    # of everyone saying no_show for every suggestion -- logging two all-no_show
    # suggestions on cards Alice doesn't hold forces *both* suggested rooms
    # into the envelope (only one room slot exists there), which is a
    # contradiction, not a realistic mid-game state.
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


@pytest.fixture(params=["fresh", "with_suggestions", "solved"])
def game_state(request, cfg, cards_by_name, three_players):
    if request.param == "fresh":
        return _fresh_game(cfg, cards_by_name, three_players)
    if request.param == "with_suggestions":
        return _game_with_suggestions(cfg, cards_by_name, three_players)
    return _solved_game(cfg)


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("module", PANEL_MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_panel_builds_and_refreshes_without_crashing(root, module, theme, game_state):
    frame = module.build(root, theme)
    try:
        assert isinstance(frame, tk.Frame)
        assert hasattr(frame, "refresh")
        frame.refresh(game_state)
        root.update_idletasks()
    finally:
        frame.destroy()


def test_best_suggestion_panel_shows_top_candidate_names(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    candidates = gs.best_suggestions(top_k=5)
    assert candidates, "expected at least one candidate for a fresh game"
    best = candidates[0]

    frame = best_suggestion_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert best.suspect.name in text
        assert best.weapon.name in text
        assert best.room.name in text
    finally:
        frame.destroy()


def test_best_suggestion_panel_shows_solved_message(root, cfg):
    gs = _solved_game(cfg)
    suspect, weapon, room = gs.solution()

    frame = best_suggestion_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "SOLVED" in text
        assert suspect.name in text
        assert weapon.name in text
        assert room.name in text
    finally:
        frame.destroy()


def test_best_suggestion_panel_no_candidates_message(root):
    frame = best_suggestion_panel.build(root, LIGHT)
    try:
        frame.refresh(None)
        root.update_idletasks()
        text = _all_text(frame)
        assert "Not enough information" in text
    finally:
        frame.destroy()


def test_mystery_progress_panel_shows_known_and_total(root, cfg, cards_by_name, three_players):
    from cluedo.mystery_progress import compute_mystery_progress

    gs = _fresh_game(cfg, cards_by_name, three_players)
    progress = compute_mystery_progress(gs)

    frame = mystery_progress_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert str(progress.known_cards) in text
        assert str(progress.total_cards) in text
        assert f"Turns played: {progress.turns_played}" in text
    finally:
        frame.destroy()


def test_envelope_probabilities_panel_lists_all_cards_when_computable(root, cfg, cards_by_name, three_players):
    from cluedo.probability import TooManyAmbiguousCardsError

    gs = _fresh_game(cfg, cards_by_name, three_players)

    frame = envelope_probabilities_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        try:
            gs.card_probabilities()
        except TooManyAmbiguousCardsError:
            assert "not enough information" in text.lower()
        else:
            for card in gs.cards:
                assert card.name in text
    finally:
        frame.destroy()


def test_envelope_probabilities_panel_solved_game_all_certain(root, cfg):
    gs = _solved_game(cfg)

    frame = envelope_probabilities_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        for card in gs.cards:
            assert card.name in text
    finally:
        frame.destroy()


def test_game_statistics_panel_shows_history_length(root, cfg, cards_by_name, three_players):
    gs = _game_with_suggestions(cfg, cards_by_name, three_players)

    frame = game_statistics_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert str(len(gs.history)) in text
    finally:
        frame.destroy()
