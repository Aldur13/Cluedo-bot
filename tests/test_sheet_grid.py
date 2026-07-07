"""Tests for cluedo/gui/sheet_grid.py and cluedo/gui/toolbar.py.

These need a real Tk display (this machine has a real Windows desktop, not
headless), so we build a real `tk.Tk()` root, a real GameState via the
cfg/cards_by_name/three_players fixtures, and assert render_sheet_grid /
build_toolbar don't raise -- plus a couple of direct checks on the
"recently changed" highlight logic against scripted suggestion sequences.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file: creating/tearing down many independent `tk.Tk()`
interpreters -- even one module-scoped root per file, once several such
files exist in one run -- was observed to intermittently fail with
`_tkinter.TclError: Can't find a usable tk.tcl`, a Tcl-interpreter-startup
flake unrelated to the sheet grid itself. A single root shared across the
whole test session eliminates it.
"""
import tkinter as tk

import pytest

from cluedo.game import GameState
from cluedo.gui.sheet_grid import (
    HIGHLIGHT_BORDER_THICKNESS,
    NORMAL_BORDER_THICKNESS,
    render_sheet_grid,
)
from cluedo.gui.toolbar import build_toolbar
from cluedo.gui.theme import DARK, HIGH_CONTRAST, LIGHT
from cluedo.models import SuggestionResponse


def _basic_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


class _FakeApp:
    """Minimal stand-in for the App controller -- toolbar buttons just need
    zero-arg callables to bind to; we never click them in these tests."""

    def __init__(self):
        for name in (
            "open_suggestion_dialog", "undo", "open_timeline", "open_replay",
            "open_whatif", "open_graphs", "save", "load", "open_export", "open_settings",
        ):
            setattr(self, name, lambda: None)


def _all_cells(container):
    """Recursively collect every widget under the returned frame that carries
    the cluedo_card marker set by render_sheet_grid."""
    cells = []
    stack = [container]
    while stack:
        widget = stack.pop()
        if hasattr(widget, "cluedo_card"):
            cells.append(widget)
        stack.extend(widget.winfo_children())
    return cells


@pytest.mark.parametrize("theme", [LIGHT, DARK, HIGH_CONTRAST])
def test_render_sheet_grid_fresh_unsolved_game(root, cfg, cards_by_name, three_players, theme):
    gs = _basic_game(cfg, cards_by_name, three_players)
    frame = render_sheet_grid(root, gs, theme)
    try:
        assert isinstance(frame, tk.Frame)
        cells = _all_cells(frame)
        # players + envelope columns, times every card
        assert len(cells) == len(gs.cards) * (len(gs.players) + 1)
        # Fresh game: no suggestions yet, nothing should be flagged "recently changed".
        assert all(not c.cluedo_recently_changed for c in cells)
        assert all(int(c.cget("highlightthickness")) == NORMAL_BORDER_THICKNESS for c in cells)
    finally:
        frame.destroy()


@pytest.mark.parametrize("theme", [LIGHT, DARK, HIGH_CONTRAST])
def test_render_sheet_grid_solved_game(root, cfg, cards_by_name, three_players, theme):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )
    # Sanity: this scripted sequence solves the game (mirrors test_change_tracking.py).
    assert gs.is_solved()

    frame = render_sheet_grid(root, gs, theme)
    try:
        cells = _all_cells(frame)
        assert len(cells) == len(gs.cards) * (len(gs.players) + 1)
    finally:
        frame.destroy()


def test_render_sheet_grid_click_callback(root, cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    clicked = []
    frame = render_sheet_grid(root, gs, LIGHT, on_cell_click=clicked.append)
    try:
        frame.pack()
        root.update()
        cells = _all_cells(frame)
        # Invoke the bound <Button-1> handler directly rather than relying on
        # event_generate's synthetic-event delivery (unreliable for an unmapped,
        # off-screen test window across Tk versions).
        cells[0].event_generate("<Button-1>", x=1, y=1, when="now")
        root.update()
        assert clicked == [cells[0].cluedo_card]
    finally:
        frame.destroy()


def test_render_sheet_grid_no_click_callback_is_noninteractive(root, cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    frame = render_sheet_grid(root, gs, LIGHT)  # on_cell_click defaults to None
    try:
        frame.pack()
        root.update()
        cells = _all_cells(frame)
        # Should not raise even though nothing is bound.
        cells[0].event_generate("<Button-1>", x=1, y=1, when="now")
        root.update()
    finally:
        frame.destroy()


def test_recently_changed_highlight_matches_last_suggestion(root, cfg, cards_by_name, three_players):
    """The rule: a card is highlighted iff its last-changed turn (from
    compute_last_changed_turns) equals len(game_state.history) -- i.e. it
    changed on the most recent suggestion. Reuses the exact scripted
    3-suggestion sequence from tests/test_change_tracking.py, where turn 3
    (the most recent) changes exactly Mrs. Peacock/Revolver/Ballroom."""
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    gs.record_suggestion(
        1, cards_by_name["Professor Plum"], cards_by_name["Wrench"], cards_by_name["Study"],
        [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
    )
    gs.record_suggestion(
        2, cards_by_name["Mrs. Peacock"], cards_by_name["Revolver"], cards_by_name["Ballroom"],
        [SuggestionResponse(0, "no_show"), SuggestionResponse(1, "no_show")],
    )

    frame = render_sheet_grid(root, gs, LIGHT)
    try:
        cells = _all_cells(frame)

        highlighted_cards = {c.cluedo_card for c in cells if c.cluedo_recently_changed}
        expected_cards = {cards_by_name[n] for n in ("Mrs. Peacock", "Revolver", "Ballroom")}
        assert highlighted_cards == expected_cards

        for c in cells:
            expected_thickness = (
                HIGHLIGHT_BORDER_THICKNESS if c.cluedo_card in expected_cards else NORMAL_BORDER_THICKNESS
            )
            assert int(c.cget("highlightthickness")) == expected_thickness
    finally:
        frame.destroy()


def test_recently_changed_highlight_after_undo_is_empty(root, cfg, cards_by_name, three_players):
    gs = _basic_game(cfg, cards_by_name, three_players)
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "shown_to_me", cards_by_name["Rope"])],
    )
    gs.undo_last_suggestion()

    frame = render_sheet_grid(root, gs, LIGHT)
    try:
        cells = _all_cells(frame)
        assert all(not c.cluedo_recently_changed for c in cells)
    finally:
        frame.destroy()


@pytest.mark.parametrize("theme", [LIGHT, DARK, HIGH_CONTRAST])
def test_build_toolbar_renders_without_error(root, theme):
    app = _FakeApp()
    toolbar = build_toolbar(root, app, theme)
    try:
        assert isinstance(toolbar, tk.Frame)
        buttons = [w for w in toolbar.winfo_children() if isinstance(w, tk.Button)]
        assert len(buttons) == 10
        labels = {b.cget("text") for b in buttons}
        assert labels == {
            "Log Suggestion (Ctrl+N)", "Undo (Ctrl+Z)", "Timeline (Ctrl+E)", "Replay (Ctrl+R)",
            "What-If", "Trends", "Save (Ctrl+S)", "Load (Ctrl+O)", "Export", "Settings",
        }
    finally:
        toolbar.destroy()
