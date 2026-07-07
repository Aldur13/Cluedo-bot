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
    game_review_card_panel,
    game_statistics_panel,
    mystery_progress_panel,
    recent_deductions_panel,
    timeline_panel,
    warnings_panel,
)
from cluedo.gui.theme import DARK, HIGH_CONTRAST, LIGHT, ThemeManager
from cluedo.models import CardType, Player, SuggestionResponse

PANEL_MODULES = [
    best_suggestion_panel,
    envelope_probabilities_panel,
    mystery_progress_panel,
    ai_insights_panel,
    recent_deductions_panel,
    timeline_panel,
    endgame_panel,
    warnings_panel,
    game_statistics_panel,
    game_review_card_panel,
]
THEMES = [LIGHT, DARK, HIGH_CONTRAST]


class _FakeApp:
    """Minimal stand-in for the App controller -- just enough for panels
    that capture `app` via closure (Timeline's replay jump, Game Review's
    "Open Full Review" button and `_game_review_cache` read)."""

    def __init__(self, root, game_state):
        self.root = root
        self.theme_manager = ThemeManager(LIGHT)
        self.game_state = game_state
        self._game_review_cache = None
        self.open_game_review = lambda: None


def _fake_app(root, game_state=None):
    return _FakeApp(root, game_state)


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
    app = _fake_app(root, game_state)
    frame = module.build(root, theme, app)
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

    frame = best_suggestion_panel.build(root, LIGHT, _fake_app(root, gs))
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

    frame = best_suggestion_panel.build(root, LIGHT, _fake_app(root, gs))
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
    frame = best_suggestion_panel.build(root, LIGHT, _fake_app(root))
    try:
        frame.refresh(None)
        root.update_idletasks()
        text = _all_text(frame)
        assert "Not enough information" in text
    finally:
        frame.destroy()


def test_best_suggestion_panel_show_why_reveals_rationale(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    candidates = gs.best_suggestions(top_k=5)
    rationale = candidates[0].rationale

    frame = best_suggestion_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        assert rationale not in _all_text(frame)

        show_why = next(
            w for w in frame.winfo_children() if _find_button_with_text(w, "Show Why") is not None
        )
        button = _find_button_with_text(show_why, "Show Why")
        button.invoke()
        root.update_idletasks()
        assert rationale in _all_text(frame)
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


def test_mystery_progress_panel_shows_known_and_total(root, cfg, cards_by_name, three_players):
    from cluedo.mystery_progress import compute_mystery_progress

    gs = _fresh_game(cfg, cards_by_name, three_players)
    progress = compute_mystery_progress(gs)

    frame = mystery_progress_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert str(progress.known_cards) in text
        assert str(progress.total_cards) in text
        assert f"Turns played: {progress.turns_played}" in text
    finally:
        frame.destroy()


def test_envelope_probabilities_panel_top3_by_default_then_show_all(root, cfg, cards_by_name, three_players):
    from cluedo.models import ENVELOPE

    # A fresh game with zero suggestions logged is too ambiguous for exact
    # probabilities (TooManyAmbiguousCardsError) -- _game_with_suggestions
    # logs enough real facts to make card_probabilities() computable.
    gs = _game_with_suggestions(cfg, cards_by_name, three_players)
    probs = gs.card_probabilities()
    suspects = sorted(
        (c for c in gs.cards if c.type == CardType.SUSPECT),
        key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), reverse=True,
    )

    frame = envelope_probabilities_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        # Default tab is Suspects; only the top 3 are shown by default.
        for card in suspects[:3]:
            assert card.name in text
        if len(suspects) > 3:
            assert suspects[-1].name not in text

            show_all = _find_button_with_text(frame, f"Show All ({len(suspects)})")
            assert show_all is not None
            show_all.invoke()
            root.update_idletasks()
            text = _all_text(frame)
            for card in suspects:
                assert card.name in text
    finally:
        frame.destroy()


def test_envelope_probabilities_panel_not_computable_message(root, cfg, cards_by_name, three_players, monkeypatch):
    from cluedo.probability import TooManyAmbiguousCardsError

    gs = _fresh_game(cfg, cards_by_name, three_players)

    def _raise(*args, **kwargs):
        raise TooManyAmbiguousCardsError(ambiguous_count=99, threshold=14)

    monkeypatch.setattr(gs, "card_probabilities", _raise)

    frame = envelope_probabilities_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "not enough information" in text.lower()
    finally:
        frame.destroy()


def test_envelope_probabilities_panel_solved_game_all_certain(root, cfg):
    gs = _solved_game(cfg)

    frame = envelope_probabilities_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        # Solved game: every category has few enough cards that top-3
        # already covers all of them (2-player minimal fixture).
        text = _all_text(frame)
        suspect, weapon, room = gs.solution()
        assert suspect.name in text
    finally:
        frame.destroy()


def test_game_statistics_panel_shows_history_length(root, cfg, cards_by_name, three_players):
    gs = _game_with_suggestions(cfg, cards_by_name, three_players)

    frame = game_statistics_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert str(len(gs.history)) in text
    finally:
        frame.destroy()


def test_recent_deductions_panel_shows_confirmed_card_from_a_suggestion(root, cfg, cards_by_name, three_players):
    # _solved_game solves purely from set_user_hand() (no suggestions in
    # history), which produces zero *turn* events by design (see
    # tests/test_live_events.py) -- this test needs an actual suggestion
    # that confirms a card to exercise the panel's real content path.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    # Claiming a card already in Alice's (the user's) known hand is an
    # immediate contradiction -- pick a weapon outside her starting hand
    # (["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick",
    # "Knife", "Lead Pipe"]).
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON and c.name not in ("Candlestick", "Knife", "Lead Pipe")]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]
    # shown_to_me directly names the card, an immediate, deterministic
    # confirmation -- unlike shown_unseen, which only yields a weak
    # at-least-one fact that may not resolve to a single card right away.
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "shown_to_me", shown_card=weapons[0]), SuggestionResponse(2, "no_show")],
    )

    from cluedo.analysis.live_events import confirmed_card_events

    events = confirmed_card_events(gs)
    assert events, "expected this suggestion to confirm at least one card"

    frame = recent_deductions_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "No deductions yet." not in text
        assert events[0].card.name in text
    finally:
        frame.destroy()


def test_recent_deductions_panel_empty_state(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)

    frame = recent_deductions_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "No deductions yet." in text
    finally:
        frame.destroy()


def test_timeline_panel_row_click_opens_replay_at_solve_turn(root, cfg, monkeypatch):
    from cluedo.gui.panels import timeline_panel as timeline_panel_module

    gs = _solved_game(cfg)
    app = _fake_app(root, gs)

    # timeline_panel calls the real cluedo.gui.replay_screen.open_replay
    # directly (matching game_review_screen.py's established pattern), not
    # app.open_replay -- monkeypatch the module-level function it actually
    # calls, and never let a real Toplevel open in this test.
    calls = []
    monkeypatch.setattr(
        timeline_panel_module.replay_screen, "open_replay",
        lambda app, initial_index=None: calls.append(initial_index),
    )

    frame = timeline_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        solve_turn = len(gs.history)
        button = _find_button_containing(frame, "SOLVED")
        assert button is not None
        button.invoke()
        assert calls == [solve_turn]
    finally:
        frame.destroy()


def _find_button_containing(widget, substring):
    if isinstance(widget, tk.Button) and substring in str(widget.cget("text")):
        return widget
    for child in widget.winfo_children():
        found = _find_button_containing(child, substring)
        if found is not None:
            return found
    return None


def test_timeline_panel_empty_state(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)

    frame = timeline_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "No suggestions logged yet." in text
    finally:
        frame.destroy()


def test_warnings_panel_flags_a_redundant_suggestion(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    suspects = [c for c in gs.cards if c.type == CardType.SUSPECT]
    weapons = [c for c in gs.cards if c.type == CardType.WEAPON]
    rooms = [c for c in gs.cards if c.type == CardType.ROOM]

    # First suggestion confirms a card is owned by seat 1 (shown_unseen).
    gs.record_suggestion(
        0, suspects[0], weapons[0], rooms[0],
        [SuggestionResponse(1, "shown_unseen"), SuggestionResponse(2, "no_show")],
    )
    from cluedo.analysis.patterns import find_redundant_suggestions

    frame = warnings_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        # Re-ask the same triple by the same suggester -- redundant only if
        # the solver actually confirmed one of those three cards already;
        # skip gracefully if this particular deal didn't produce that.
        gs.record_suggestion(
            0, suspects[0], weapons[0], rooms[0],
            [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
        )
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        if find_redundant_suggestions(gs, 0):
            assert "already confirmed" in text
        else:
            assert "No warnings." in text
    finally:
        frame.destroy()


def test_warnings_panel_empty_state(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)

    frame = warnings_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "No warnings." in text
    finally:
        frame.destroy()


def test_game_review_card_hidden_before_solve(root, cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)

    frame = game_review_card_panel.build(root, LIGHT, _fake_app(root, gs))
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert "Available once the mystery is solved." in text
        assert "Grade:" not in text
    finally:
        frame.destroy()


def test_game_review_card_shows_grade_from_app_cache(root, cfg):
    from cluedo.analysis.game_review import compute_game_review

    gs = _solved_game(cfg)
    app = _fake_app(root, gs)
    app._game_review_cache = compute_game_review(gs)

    frame = game_review_card_panel.build(root, LIGHT, app)
    try:
        frame.refresh(gs)
        root.update_idletasks()
        text = _all_text(frame)
        assert f"Grade: {app._game_review_cache.overall_rating or 'N/A'}" in text
    finally:
        frame.destroy()
