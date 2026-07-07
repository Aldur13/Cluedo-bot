"""Content-specific tests for cluedo/gui/panels/ai_insights_panel.py.

Generic "builds and refreshes without crashing" coverage across
themes/game-states lives in tests/test_panels.py (ai_insights_panel is
included in its PANEL_MODULES list); this file checks the panel's actual
per-player output and its "advisory, never certain" visual contract.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui.panels import ai_insights_panel
from cluedo.gui.theme import LIGHT
from cluedo.models import SuggestionResponse


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _all_text(widget) -> str:
    chunks = []
    try:
        chunks.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        chunks.append(_all_text(child))
    return "\n".join(chunks)


def test_disclaimer_is_always_shown(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    frame = ai_insights_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        assert "advisory" in _all_text(frame).lower()
    finally:
        frame.destroy()


def test_opponents_below_min_suggestions_show_insufficient_data(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    frame = ai_insights_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        text = _all_text(frame)
        # Fresh game: seat 1 (Bob) and seat 2 (Carol) have made 0 suggestions.
        assert text.count("not enough data yet") == 2
        assert "Bob:" in text
        assert "Carol:" in text
    finally:
        frame.destroy()


def test_qualifying_player_shows_a_strategy_label(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    # Exact fixed-weapon "hunter" scenario from
    # tests/test_analysis_strategy.py::test_weapon_hunter_classification,
    # logged for seat 1 (Bob) to clear MIN_SUGGESTIONS_FOR_CLASSIFICATION and
    # produce a dominant lock streak. Deliberately avoids any card in Alice's
    # (seat 0, the user) known hand -- reusing one of her own cards here would
    # make that suggestion read as redundant (already confirmed hers) and tip
    # the classification to BLUFFER instead, as discovered while fixing
    # tests/test_analysis_strategy.py's stale aggressive-eliminator fixture.
    suggestions = [
        ("Reverend Green", "Wrench", "Kitchen"),
        ("Mrs. Peacock", "Wrench", "Ballroom"),
        ("Professor Plum", "Wrench", "Conservatory"),
        ("Reverend Green", "Wrench", "Dining Room"),
    ]
    for suspect, weapon, room in suggestions:
        gs.record_suggestion(
            1, cards_by_name[suspect], cards_by_name[weapon], cards_by_name[room],
            [SuggestionResponse(2, "no_show")],
        )

    frame = ai_insights_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)
        text = _all_text(frame)
        assert "Weapon Hunter" in text
        assert "Bob:" in text
    finally:
        frame.destroy()


def test_no_solved_fact_color_used_anywhere_in_panel(root, cfg, cards_by_name, three_players):
    # theme.confirmed is reserved across this app for "the solver has proven
    # this" -- an AI Insights label is never allowed to borrow it, since that
    # would visually claim certainty the underlying rule-based guess doesn't
    # have.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    frame = ai_insights_panel.build(root, LIGHT)
    try:
        frame.refresh(gs)

        def _collect_fg(widget):
            fgs = []
            try:
                fgs.append(str(widget.cget("fg")))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                fgs.extend(_collect_fg(child))
            return fgs

        assert LIGHT.confirmed not in _collect_fg(frame)
    finally:
        frame.destroy()


def test_no_game_in_progress(root):
    frame = ai_insights_panel.build(root, LIGHT)
    try:
        frame.refresh(None)
        assert "No game in progress." in _all_text(frame)
    finally:
        frame.destroy()
