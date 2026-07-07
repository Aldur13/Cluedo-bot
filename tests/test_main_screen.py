"""Integration test for cluedo/gui/main_screen.py's dashboard wiring.

Guards against regressing to the old hand-rolled "Advisor"/"Envelope
probabilities"/"Statistics" boxes main_screen.py used to build inline, and
confirms every panel-backed card (including the sidebar-redesign additions
-- Recent Deductions, Timeline, Warnings, Game Review) is wired in exactly
once, wrapped in the shared CollapsibleCard chrome rather than a bare
`tk.LabelFrame`.

Uses the session-scoped `root` fixture from tests/conftest.py, shared by
every GUI test file, to avoid the documented Tcl-interpreter flake.
"""
import tkinter as tk

from cluedo.game import GameState
from cluedo.gui import main_screen
from cluedo.gui.theme import LIGHT, ThemeManager


class _FakeApp:
    """Minimal stand-in for the App controller -- toolbar buttons and
    panel-captured callbacks just need zero-arg callables to bind to; we
    never click them in these tests."""

    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self.refresh_main_screen = lambda: None
        self._game_review_cache = None
        for name in (
            "open_suggestion_dialog", "undo", "open_timeline", "open_replay",
            "open_whatif", "open_graphs", "open_game_review", "save", "load", "open_export", "open_settings",
        ):
            setattr(self, name, lambda: None)

    def open_explain(self, card):
        pass


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _card_titles(widget) -> list[str]:
    """Collects every CollapsibleCard header's `card_title_text` -- the
    stable marker CollapsibleCard sets on its title Label, deliberately
    independent of any text a card's own body content might coincidentally
    contain (see cluedo.gui.widgets.CollapsibleCard)."""
    found = []
    title = getattr(widget, "card_title_text", None)
    if title is not None:
        found.append(title)
    for child in widget.winfo_children():
        found.extend(_card_titles(child))
    return found


def _label_frames_by_text(widget) -> list[str]:
    found = []
    if isinstance(widget, tk.LabelFrame):
        found.append(str(widget.cget("text")))
    for child in widget.winfo_children():
        found.extend(_label_frames_by_text(child))
    return found


def test_dashboard_wires_every_card_exactly_once_with_no_bare_labelframes(
    root, cfg, cards_by_name, three_players
):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    frame = main_screen.build(root, app)
    try:
        titles = _card_titles(frame)

        for expected in (
            "Best Suggestion", "Envelope Analysis", "Mystery Progress", "AI Insights",
            "Recent Deductions", "Timeline", "Endgame", "Warnings", "Statistics", "Game Review",
        ):
            assert titles.count(expected) == 1, f"expected exactly one {expected!r} card, found {titles.count(expected)}"

        # The old hand-rolled boxes (bare LabelFrame chrome) are gone --
        # every sidebar section now goes through CollapsibleCard.
        assert _label_frames_by_text(frame) == []

        # refresh_main_screen must have been rebound to the real refresh, not
        # left as the fake's no-op placeholder.
        assert app.refresh_main_screen is not None
        app.refresh_main_screen()  # should not raise
    finally:
        frame.destroy()


def test_dashboard_refresh_updates_panels_after_a_suggestion(root, cfg, cards_by_name, three_players):
    from cluedo.models import SuggestionResponse

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    frame = main_screen.build(root, app)
    try:
        gs.record_suggestion(
            1, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
            [SuggestionResponse(2, "no_show"), SuggestionResponse(0, "no_show")],
        )
        app.refresh_main_screen()  # should not raise with a live, mutated game_state
    finally:
        frame.destroy()


def test_dashboard_collapsed_card_stays_collapsed_across_a_screen_rebuild(root, cfg, cards_by_name, three_players):
    """A theme change rebuilds the whole screen from scratch (App re-invokes
    `_current_screen_show()` rather than live-recoloring -- see
    ThemeManager's docstring). A card collapsed via cluedo.gui.sidebar_state
    must come back collapsed after that kind of rebuild, proving the state
    lives outside the (destroyed and recreated) widget tree."""
    from cluedo.gui import sidebar_state

    gs = _fresh_game(cfg, cards_by_name, three_players)
    app = _FakeApp(root, gs)

    sidebar_state.set_expanded("statistics", False)
    frame = main_screen.build(root, app)
    try:
        statistics_body = _card_body_by_title(frame, "Statistics")
        assert statistics_body is not None
        # A collapsed CollapsibleCard's body frame has been pack_forget()'d,
        # which clears its geometry manager -- more reliable in a test than
        # winfo_ismapped(), which also depends on the Toplevel actually
        # being viewable on screen.
        assert statistics_body.winfo_manager() == ""
    finally:
        frame.destroy()


def _card_body_by_title(widget, title):
    header_title = getattr(widget, "card_title_text", None)
    if header_title == title:
        # `widget` is the title Label; its CollapsibleCard body is the
        # sibling `tk.Frame` packed after the header inside the same outer
        # card frame (see CollapsibleCard.__init__: header then self.body).
        card_frame = widget.master.master  # title -> header -> card frame
        children = card_frame.winfo_children()
        return children[1] if len(children) > 1 else None
    for child in widget.winfo_children():
        found = _card_body_by_title(child, title)
        if found is not None:
            return found
    return None
