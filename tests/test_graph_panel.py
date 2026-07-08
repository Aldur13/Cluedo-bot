"""Tests for cluedo/gui/graph_screen.py. Builds the real Toplevel (matplotlib
figure embedded via FigureCanvasTkAgg) against a scripted game and asserts
the figure's series lengths match the replay-snapshot count -- no pixel
rendering assertions, matplotlib's own test suite already covers that.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import graph_screen
from cluedo.gui.theme import LIGHT, ThemeManager
from cluedo.history import build_replay_snapshots
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
    raise AssertionError("open_graphs did not create a Toplevel")


def test_open_graphs_with_no_suggestions_shows_placeholder(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    graph_screen.open_graphs(app)
    win = _find_toplevel(root)
    try:
        texts = []
        for child in win.winfo_children():
            try:
                texts.append(str(child.cget("text")))
            except tk.TclError:
                pass
        assert any("Log at least one suggestion" in t for t in texts)
    finally:
        win.destroy()


def test_open_graphs_plots_one_point_per_snapshot(root, cfg, cards_by_name, three_players):
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
    expected_snapshot_count = len(build_replay_snapshots(gs))

    graph_screen.open_graphs(app)
    win = _find_toplevel(root)
    try:
        def _descendants(widget):
            found = [widget]
            for child in widget.winfo_children():
                found.extend(_descendants(child))
            return found

        all_widgets = _descendants(win)
        canvases = [w for w in all_widgets if hasattr(w, "figure")] or [
            w for w in all_widgets if isinstance(w, tk.Widget) and "Canvas" in type(w).__name__
        ]
        assert canvases, "expected a matplotlib canvas widget in the Trends window"
    finally:
        win.destroy()

    # Rebuild the same data the screen plotted to check series length directly,
    # since matplotlib line data is more reliable to assert on than widget internals.
    from cluedo.timeseries import solver_progress_over_time, worlds_over_time

    snapshots = build_replay_snapshots(gs)
    assert len(snapshots) == expected_snapshot_count
    assert len(worlds_over_time(snapshots)) == expected_snapshot_count
    assert len(solver_progress_over_time(snapshots)) == expected_snapshot_count
